"""Guaranteed outer state enclosures for a declared synthetic model set.

No calibration issuer or real actuator authority exists in this lineage.
"""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
import itertools

from experiments.cneh_exp_06c import algebra as a,estimator as e

PRIOR=(F(0),F(1))
PARAMETERS=((F(1),F(2)),(F(0),F(1)),(F(100),F(120)))
NAMES=("nmda_gain","clock_delay_ms","tau_nmda_ms")
PROFILES=("UNVERIFIED","BOUNDED_SYNTHETIC_HYPOTHESIS")
SWEEPS=6


def split(box):
    mid=a.midpoint(box)
    return (box[0],mid),(mid,box[1])


def cover():
    boxes=tuple(itertools.product(*(split(q) for q in PARAMETERS)))
    a.need(len(boxes)==8 and len(set(boxes))==8,"parameter cover")
    return boxes


def exp_range(box):
    a.need(box[0]<=box[1],"exp range")
    return a.exponential(box[0])[0],a.exponential(box[1])[1]


def decay(t,delay,tau):
    return exp_range(a.neg(a.div(a.add(a.point(t),delay),tau)))


@lru_cache(maxsize=8)
def model_box(box):
    gain,delay,tau_n=box
    block=a.reciprocal(a.add(a.point(1),a.div(a.exponential(F(93,25)),a.point(F(357,100)))))
    knee=a.exponential(F(-5,2))
    rows=[];offsets=[]
    for t in a.TIMES:
        ew=decay(t,delay,a.point(200))
        ea=decay(t,delay,a.point(F(5,2)))
        en=decay(t,delay,tau_n)
        eg=decay(t,delay,a.point(6))
        rows.append(tuple(a.outward(v,2**80) for v in (
            a.mul(a.point(24),ew),a.mul(a.point(-6),ea),
            a.mul(a.mul(a.mul(a.point(-6),block),gain),en),a.mul(a.point(5),eg))))
        offsets.append(a.outward(a.add(a.sub(a.point(100),a.mul(a.point(20),knee)),
                                    a.mul(a.point(20),a.sub(a.point(1),ew))),2**80))
    matrix=[[a.midpoint(q) for q in rows[i]] for i in a.PRIMARY]
    try:
        inv=a.inverse(matrix)
    except ValueError:
        # A singular preconditioner cannot exclude any possible truth.
        return tuple(rows),tuple(offsets),None,None
    m=[]
    for i in range(4):
        m.append(tuple(a.outward(a.sub(a.point(int(i==j)),a.isum(
            a.mul(a.point(inv[i][k]),rows[index][j]) for k,index in enumerate(a.PRIMARY))),2**60)
                       for j in range(4)))
    return tuple(rows),tuple(offsets),tuple(tuple(row) for row in inv),tuple(m)


def intersect(x,y):
    return e.intersect(x,y)


def narrow(x,y):
    return intersect(x,a.outward(y,2**40))


def prediction(row,b,x):
    return a.add(b,a.isum(a.mul(p,q) for p,q in zip(row,x,strict=True)))


def contract(box,observed):
    rows,b,inv,m=model_box(box)
    z=[a.sub(y,off) for y,off in zip(observed,b,strict=True)]
    x=[PRIOR]*4
    if inv is not None:
        c=[a.outward(a.isum(a.mul(a.point(q),z[i]) for q,i in zip(row,a.PRIMARY,strict=True)),2**60) for row in inv]
    for _ in range(SWEEPS):
        previous=tuple(x)
        if inv is not None:
            new=[]
            for i in range(4):
                q=narrow(x[i],prediction(m[i],c[i],previous))
                if q is None:
                    return None
                new.append(q)
            x=new
        for i,row in enumerate(rows):
            if intersect(prediction(row,b[i],x),observed[i]) is None:
                return None
            for j,coef in enumerate(row):
                if coef[0]*coef[1]<=0:
                    continue
                others=a.isum(a.mul(row[k],x[k]) for k in range(4) if k!=j)
                q=narrow(x[j],a.div(a.sub(z[i],others),coef))
                if q is None:
                    return None
                x[j]=q
        if tuple(x)==previous:
            break
    if any(intersect(prediction(row,b[i],x),observed[i]) is None for i,row in enumerate(rows)):
        return None
    return tuple(x)


def encode_box(box):
    return {name:a.encode(q) for name,q in zip(NAMES,box,strict=True)}


def result(status,voltage,bounds,survivors):
    return {"status":status,"voltage_bounds_mV":None if voltage is None else a.encode(voltage),
            "normalized_bounds":None if bounds is None else [a.encode(q) for q in bounds],
            "surviving_boxes":survivors,"scope":"OUTER_ENCLOSURE_CONDITIONAL_ON_DECLARED_SYNTHETIC_MODEL_SET",
            "joint_feasibility_proven":False,"real_calibration_verified":False,
            "source_action_authorized":False,"closed_loop_authorized":False,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}


def estimate(record,profile="UNVERIFIED"):
    a.need(type(profile) is str and profile in PROFILES,"unknown calibration profile")
    v,ev,eps,y=e.parse(record)
    if profile=="UNVERIFIED":
        return result("CALIBRATION_UNVERIFIED",(F(-74),F(-68)),(PRIOR,)*4,[])
    vb=intersect((v-ev,v+ev),(F(-74),F(-68)))
    if vb is None:
        return result("INCONSISTENT_VOLTAGE",None,None,[])
    measured=[(q-eps,q+eps) for q in y]
    survivors=[]
    for box in cover():
        x=contract(box,measured)
        if x is not None:
            survivors.append({"parameters":encode_box(box),"normalized_bounds":[a.encode(q) for q in x]})
    if not survivors:
        return result("INCONSISTENT_DECLARED_MODEL_SET",None,None,[])
    bounds=tuple((min(a.decode(s["normalized_bounds"][j][0]) for s in survivors),
                  max(a.decode(s["normalized_bounds"][j][1]) for s in survivors)) for j in range(4))
    return result("CONDITIONAL_NARROW_ENCLOSURE" if all(hi-lo<=a.WIDTH for lo,hi in bounds)
                  else "ABSTAIN_MODEL_STATE_AMBIGUITY",a.outward(vb,2**40),bounds,survivors)


def contains(value,x):
    return value["normalized_bounds"] is not None and all(
        a.decode(bounds[0])<=q<=a.decode(bounds[1]) for bounds,q in zip(value["normalized_bounds"],x,strict=True))


def contains_joint(value,params,x):
    return any(all(a.decode(s["parameters"][name][0])<=p<=a.decode(s["parameters"][name][1])
                   for name,p in zip(NAMES,params,strict=True))
               and all(a.decode(b[0])<=q<=a.decode(b[1])
                       for b,q in zip(s["normalized_bounds"],x,strict=True))
               for s in value["surviving_boxes"])
