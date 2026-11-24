"""New scalar C/MPFR backend, integrated through frozen J/X event semantics."""
from __future__ import annotations

import ctypes as ct
import inspect
import math
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np

from experiments.cneh_exp_05j import integrator as j
from experiments.cneh_exp_05x import trace as xtrace
from experiments.cneh_exp_05x import worlds as w

LIBRARY=Path(os.environ.get("CNEH_PORTABLE_LIB","/tmp/cneh05y/libdp.so"))
LIB=ct.CDLL(str(LIBRARY))
D=ct.c_double
P=ct.POINTER(D)
for name,arguments in (("soft_exp",[D]),("soft_pow",[D,D]),("soft_sqrt",[D]),
                       ("separate_mul_add",[D,D,D])):
    fun=getattr(LIB,name);fun.argtypes=arguments;fun.restype=D
LIB.software_version.argtypes=[];LIB.software_version.restype=ct.c_char_p
LIB.numeric_environment.argtypes=[];LIB.numeric_environment.restype=ct.c_int
LIB.dp_trial.argtypes=[D,D,P,P,D,D,P,P,P,P,P];LIB.dp_trial.restype=ct.c_int
LIB.dp_dense.argtypes=[P,P];LIB.dp_dense.restype=None
LIB.dp_sample.argtypes=[P,P,D,D,P];LIB.dp_sample.restype=None
LIB.tableau.argtypes=[P];LIB.tableau.restype=None
w.need(LIB.software_version()==b"4.2.1" and LIB.numeric_environment()==1,"software arithmetic environment")


def ptr(x):
    return x.ctypes.data_as(P)


def finite_call(fun,*args):
    v=fun(*args)
    w.need(math.isfinite(v),"software rounding failed or nonfinite output")
    return v


def exp(x):
    return finite_call(LIB.soft_exp,float(x))


def power(x,p):
    return finite_call(LIB.soft_pow,float(x),float(p))


class MathProxy:
    def __getattr__(self,name):
        return exp if name=="exp" else getattr(math,name)


class Dense:
    def __init__(self,old,new,y,Q):
        self.t_old,self.t=old,new
        self.h=new-old
        self.y_old=y.copy()
        self.Q=Q.copy()

    def __call__(self,t):
        out=np.empty(2,dtype=np.float64)
        LIB.dp_sample(ptr(self.y_old),ptr(self.Q),self.h,(float(t)-self.t_old)/self.h,ptr(out))
        w.need(np.isfinite(out).all(),"nonfinite dense sample")
        return out


class PortableRK45:
    def __init__(self,fun,t0,y0,t_bound,*,rtol,atol,max_step,tracker=None):
        env=inspect.getclosurevars(fun).nonlocals
        w.need(set(("start","g0","current"))<=set(env),"frozen physical RHS closure drift")
        self.params=np.array([env["start"],*env["g0"],env["current"]],dtype=np.float64)
        self.t=float(t0);self.t_bound=float(t_bound)
        self.y=np.array(y0,dtype=np.float64,copy=True)
        self.rtol=float(rtol);self.atol=float(atol);self.max_step=float(max_step)
        self.h_abs=min(.001,self.max_step,self.t_bound-self.t)
        self.status="running";self.tracker=tracker
        self.K=np.empty((7,2),dtype=np.float64)
        self.Q=np.empty((2,4),dtype=np.float64)
        self.next=np.empty(2,dtype=np.float64)
        self.scale=np.empty(2,dtype=np.float64)
        self.times=np.empty(7,dtype=np.float64)
        self.error=ct.c_double()
        self._dense=None

    def step(self):
        w.need(self.status=="running","solver status")
        old=self.t
        minstep=10.*abs(math.nextafter(old,math.inf)-old)
        h=min(max(self.h_abs,minstep),self.max_step)
        rejected=False
        for _ in range(1000):
            if h<minstep:
                self.status="failed";return "adaptive step below representable minimum"
            end=min(self.t_bound,old+h)
            actual=end-old
            w.need(actual>0. and end<=self.t_bound,"forcing step progress")
            code=LIB.dp_trial(old,end,ptr(self.y),ptr(self.params),self.rtol,self.atol,
                              ptr(self.K),ptr(self.next),ptr(self.scale),ct.byref(self.error),ptr(self.times))
            w.need(code==0,"portable arithmetic fault "+str(code))
            error=self.error.value
            w.need(error>=0. and math.isfinite(error),"adaptive error norm")
            if self.tracker is not None:
                for t in self.times:
                    self.tracker.rhs(float(t))
                self.tracker.trial(self,self.K,actual,self.scale,error)
            if error<1.:
                factor=10. if error==0. else min(10.,.9*power(error,-.2))
                if rejected:
                    factor=min(1.,factor)
                self.h_abs=actual*factor
                LIB.dp_dense(ptr(self.K),ptr(self.Q))
                self._dense=Dense(old,end,self.y,self.Q)
                self.t=end;self.y=self.next.copy()
                if self.t==self.t_bound:
                    self.status="finished"
                return None
            h=actual*max(.2,.9*power(error,-.2))
            rejected=True
        self.status="failed";return "adaptive rejection budget"

    def dense_output(self):
        w.need(self._dense is not None,"no accepted step")
        return self._dense


class PortableTrace(xtrace.Trace):
    def solver_class(self):
        tracker=self
        class Traced(PortableRK45):
            def __init__(self,fun,t0,y0,t_bound,**kwargs):
                tracker.begin(fun,float(t0),y0,float(t_bound))
                super().__init__(fun,t0,y0,t_bound,tracker=tracker,**kwargs)
                tracker.solver=self
        return Traced


def simulate(world,trace=True):
    # No global NumPy/math mutation. The frozen parent cell controls
    # event chronology; candidate C/MPFR owns all RK stage arithmetic.
    with patch.object(j,"RK45",PortableRK45),patch.object(j,"math",MathProxy()),patch.object(xtrace,"Trace",PortableTrace):
        return xtrace.simulate(world,trace)


def probes():
    from scipy.integrate import RK45
    from experiments.cneh_exp_05v import oracle
    data=np.empty(77,dtype=np.float64)
    LIB.tableau(ptr(data))
    expected=np.concatenate([q.ravel() for q in (RK45.C,RK45.A,RK45.B,RK45.E,RK45.P)])
    w.need(data.tobytes()==expected.tobytes(),"DP tableau mismatch")
    xs=[-32.+i/32. for i in range(2049)]
    for x in xs:
        w.need(exp(x).hex()==oracle.certificate(x)[0].hex(),"independent exp enclosure disagreement")
    # Exact rational FMA counterexample, plus subnormal and tie fixtures.
    a,b=1.+2.**-27,1.-2.**-27
    w.need(LIB.separate_mul_add(a,b,-1.).hex()==(0.).hex(),"multiply-add contracted")
    fixtures={"zero":exp(0.).hex(),"underflow":exp(-1000.).hex(),
              "subnormal":exp(-744.).hex(),"sqrt4":finite_call(LIB.soft_sqrt,4.).hex(),
              "pow1":power(1.,-.2).hex(),"pow_exact":power(2.,3.).hex(),
              "sqrt_subnormal":finite_call(LIB.soft_sqrt,2.**-1074).hex()}
    w.need(fixtures["zero"]==(1.).hex() and fixtures["underflow"]==(0.).hex()
           and 0.<float.fromhex(fixtures["subnormal"])<2.**-1022
           and fixtures["sqrt4"]==(2.).hex() and fixtures["pow1"]==(1.).hex()
           and fixtures["pow_exact"]==(8.).hex() and fixtures["sqrt_subnormal"]==(2.**-537).hex(),"software arithmetic boundary probes")
    # Preserve overflow as a negative control rather than treating infinity as a value.
    try:
        exp(1000.)
    except ValueError:
        pass
    else:
        raise ValueError("overflow accepted")
    return {"software":"MPFR "+LIB.software_version().decode(),"exp_independent_fixtures":len(xs),
            "rounding_environment":"RN_EVEN_GRADUAL_UNDERFLOW","separate_fma_witness":(0.).hex(),
            "edge_fixtures":fixtures,"tableau_sha256":w.digest([w.hx(v) for v in data])}
