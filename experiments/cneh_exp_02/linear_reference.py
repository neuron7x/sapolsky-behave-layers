"""Exact 2x2 finite-horizon discrete-time control reference, stdlib-only.

Verification oracle for the CNEH mathematical *boundaries*, NOT a biological
model, a trained controller or a post-hoc scientific endpoint for CNEH-EXP-02.
All claims here require LTI dynamics with correctly specified matrices.
"""
from __future__ import annotations
import math
from typing import Sequence

Mat = tuple[tuple[float, float], tuple[float, float]]
Vec = tuple[float, float]
ZERO: Mat = ((0.0, 0.0), (0.0, 0.0))
EYE: Mat = ((1.0, 0.0), (0.0, 1.0))


def mm(a: Mat, b: Mat) -> Mat:
    return (
        (a[0][0]*b[0][0]+a[0][1]*b[1][0], a[0][0]*b[0][1]+a[0][1]*b[1][1]),
        (a[1][0]*b[0][0]+a[1][1]*b[1][0], a[1][0]*b[0][1]+a[1][1]*b[1][1]),
    )


def mt(a: Mat) -> Mat:
    return ((a[0][0],a[1][0]),(a[0][1],a[1][1]))


def ma(a: Mat,b: Mat) -> Mat:
    return (
        (a[0][0]+b[0][0],a[0][1]+b[0][1]),
        (a[1][0]+b[1][0],a[1][1]+b[1][1]),
    )


def mv(a: Mat, v: Vec) -> Vec:
    return (a[0][0]*v[0]+a[0][1]*v[1], a[1][0]*v[0]+a[1][1]*v[1])


def det(a: Mat) -> float:
    return a[0][0]*a[1][1]-a[0][1]*a[1][0]


def eig_sym(a: Mat) -> tuple[float,float]:
    if abs(a[0][1]-a[1][0])>1e-9:
        raise ValueError("symmetric eigenvalues require symmetric Gramian")
    tr=a[0][0]+a[1][1]
    gap=math.sqrt(max(0.0,(a[0][0]-a[1][1])**2+4*a[0][1]*a[1][0]))
    return ((tr-gap)/2,(tr+gap)/2)


def finite_gramians(
    a: Mat, b: Mat, c_a: Mat, c_b: Mat, *, horizon: int,
    observation_variance: float,
) -> dict[str,Mat]:
    """Compute Wc and Wo_i on [0,H) from A,B,C_i without black-box solvers.

    Sensors C_i are 2x2 (use a zero row for a one-dimensional sensor).
    Independent equal observation variances are assumed. Rank-one in a
    single observation does NOT imply rank-one over a temporal horizon.
    """
    if horizon<1 or observation_variance<=0:
        raise ValueError("invalid finite horizon or observation variance")
    ak=EYE
    wc=ZERO
    wa=ZERO
    wb=ZERO
    bbt=mm(b,mt(b))
    weight=1/observation_variance
    q_a=mm(mt(c_a),c_a)
    q_b=mm(mt(c_b),c_b)
    for _ in range(horizon):
        wc=ma(wc,mm(mm(ak,bbt),mt(ak)))
        wa=ma(wa,mm(mm(mt(ak),q_a),ak))
        wb=ma(wb,mm(mm(mt(ak),q_b),ak))
        ak=mm(ak,a)
    wa=tuple(tuple(weight*v for v in row) for row in wa)  # type: ignore[assignment]
    wb=tuple(tuple(weight*v for v in row) for row in wb)  # type: ignore[assignment]
    return {"Wc":wc,"Wo_A":wa,"Wo_B":wb,"Wo_joint":ma(wa,wb)}


def hankel_singular_values(wc: Mat,wo: Mat) -> tuple[float,float]:
    """Similarity-invariant square roots of eig(Wc*Wo) for positive Gramians."""
    if eig_sym(wc)[0]<-1e-8 or eig_sym(wo)[0]<-1e-8:
        raise ValueError("non-PSD Gramian")
    product=mm(wc,wo)
    tr=product[0][0]+product[1][1]
    discr=max(0.0,tr*tr-4*det(product))
    hi=(tr+math.sqrt(discr))/2
    lo=(tr-math.sqrt(discr))/2
    return math.sqrt(max(0.0,lo)), math.sqrt(max(0.0,hi))


def theta_regression_information_open_loop(
    *, theta: float, a0: float, a1: float, actuator_gain: float,
    initial: Vec, fixed_actions: Sequence[Vec],
    observation_variance: float,
) -> float:
    """Exact Gaussian-location Fisher information for a *fixed* action sequence
    in a known 2x2 deterministic plant with full-state independent Gaussian
    measurements. It is NOT a closed-loop/adaptive-controller FIM.
    """
    if observation_variance<=0:
        raise ValueError("observation variance must be positive")
    a:Mat=((a0,theta),(-theta,a1))
    x=initial
    sensitivity:Vec=(0.0,0.0)
    info=0.0
    for u0,u1 in fixed_actions:
        # derivative dA/dtheta applied to x is (+x1, -x0)
        ds=mv(a,sensitivity)
        sensitivity=(ds[0]+x[1],ds[1]-x[0])
        xs=mv(a,x)
        x=(xs[0]+actuator_gain*u0,xs[1]+actuator_gain*u1)
        info+=(sensitivity[0]**2+sensitivity[1]**2)/observation_variance
    return info


def reference_report(protocol: dict) -> dict:
    p=protocol["model"]
    variants={}
    for theta in [p["theta_nominal"],*p["theta_ood"]]:
        a:Mat=((p["a0"],theta),(-theta,p["a1"]))
        b:Mat=((p["control_gain"],0.0),(0.0,p["control_gain"]))
        sensor_a:Mat=((1.0,0.0),(0.0,0.0))
        sensor_b:Mat=((0.0,0.0),(0.0,1.0))
        matrices=finite_gramians(
            a,b,sensor_a,sensor_b,horizon=12,
            observation_variance=p["observation_sd"]**2,
        )
        wc,wa,wb,wj=(matrices[k] for k in ("Wc","Wo_A","Wo_B","Wo_joint"))
        hs=hankel_singular_values(wc,wj)
        variants[f"{theta:+.5f}"]={
            "Wo_A_lambda_min":max(0.0,eig_sym(wa)[0]),
            "Wo_B_lambda_min":max(0.0,eig_sym(wb)[0]),
            "Wo_joint_lambda_min":max(0.0,eig_sym(wj)[0]),
            "Wc_lambda_min":max(0.0,eig_sym(wc)[0]),
            "Hankel_singular_values":list(hs),
        }
    return {
        "scientific_authority":"EXPLORATORY_REFERENCE_LTI_ONLY",
        "source":"finite discrete-time Gramian and Gaussian open-loop parameter-FIM formulas",
        "horizon":12,
        "variants":variants,
        "caveat":"This is evaluator-side known-A math, not learned belief, biological dynamics or PID",
    }
