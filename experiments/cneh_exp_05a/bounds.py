"""Independent interval-graph relaxation and piecewise control-loss attack."""
from __future__ import annotations

import bisect
import math
from fractions import Fraction

from experiments.cneh_exp_05 import policy as p

A=Fraction.from_float(p.A)
TOL=Fraction(1,10**9)
TARGET=Fraction(1,2)
BAND=(Fraction(2,5),Fraction(3,5))
HORIZONS=(1,10,25,49,320,3200)
require=p.require


def floor(x: Fraction) -> int:
    return x.numerator//x.denominator


def ceil(x: Fraction) -> int:
    return -floor(-x)


def cells_for(lo: Fraction,hi: Fraction | None,width: Fraction,cap: int) -> tuple[int,...]:
    require(lo>=0 and (hi is None or hi>=lo),"invalid interval")
    first=min(cap,max(0,ceil(lo/width)-1))
    last=cap if hi is None else min(cap,floor(hi/width))
    return tuple(range(first,last+1))


def graph(width: Fraction) -> tuple[list[tuple[int,...]],list[int],list[int]]:
    cap=int(2/width)
    require(width>0 and cap*width==2 and TARGET/width==int(TARGET/width),"grid contract")
    edges,cost,occupancy=[],[],[]
    for i in range(cap+1):
        lo=i*width
        hi=None if i==cap else (i+1)*width
        successors=set()
        for n in range(9):
            lower=max(Fraction(0),A*(lo+n*TARGET)-TOL)
            upper=None if hi is None else A*(hi+n*TARGET)+TOL
            successors.update(cells_for(lower,upper,width,cap))
        require(bool(successors),"empty abstract successor set")
        edges.append(tuple(sorted(successors)))
        distance=max(Fraction(0),lo-TARGET, Fraction(0) if hi is None else TARGET-hi)
        cost.append(int(distance/width))
        occupancy.append(int(lo<=BAND[1] and (hi is None or hi>=BAND[0])))
    return edges,cost,occupancy


def bellman(edges: list[tuple[int,...]],loss: list[int],band: list[int],horizon: int) -> tuple[list[int],list[int]]:
    require(horizon>=0 and len(edges)==len(loss)==len(band)>0,"invalid abstract graph")
    lower=[0]*len(edges)
    upper=[0]*len(edges)
    minimum,maximum=[0],[0]
    for _ in range(horizon):
        l=[loss[j]+lower[j] for j in range(len(edges))]
        u=[band[j]+upper[j] for j in range(len(edges))]
        lower=[min(l[j] for j in successors) for successors in edges]
        upper=[max(u[j] for j in successors) for successors in edges]
        minimum.append(min(lower))
        maximum.append(max(upper))
    return minimum,maximum


def bounds(horizon: int=3200) -> dict:
    result={}
    for width in (Fraction(1,100),Fraction(1,200)):
        edges,loss,band=graph(width)
        lo,hi=bellman(edges,loss,band,horizon)
        result[str(width)]={"cells":len(edges),"width_nS":str(width),
            "minimum_loss_units":lo,"maximum_occupancy":hi,
            "horizons":{str(n):{"mae_lower_nS":float(width*lo[n]/n),"occupancy_upper":hi[n],
               "structural_upper_exact_recurrence":p.upper_count(n)} for n in HORIZONS if n<=horizon}}
    return {"authority":"OUTER_INTERVAL_GRAPH_RELAXATION_NOT_ACTUATOR_OPTIMUM","recurrence_tolerance_nS":str(TOL),"grids":result}


def trace_bounds(values: list[float],certificate: dict) -> None:
    n=len(values)
    require(n>0 and all(math.isfinite(x) and x>=0 for x in values),"invalid native values")
    error=math.fsum(abs(x-.5) for x in values)
    occ=sum(.4<=x<=.6 for x in values)
    for key,row in certificate["grids"].items():
        lower=float(Fraction(key)*row["minimum_loss_units"][n])
        require(error+1e-8>=lower and occ<=row["maximum_occupancy"][n],"abstract bound violated")
    p.certify_band([.4<=x<=.6 for x in values])


def direct_loss(arrivals: list[int],initial: float) -> dict:
    x=initial
    vals=[]
    for n in arrivals:
        x=p.A*(x+.5*n)
        vals.append(x)
    mae=math.fsum(abs(x-.5) for x in vals)/len(vals)
    occ=p.certify_band([.4<=x<=.6 for x in vals])
    return {"mae":mae,"occupancy":occ,"loss":.5*(mae/(mae+.5)+1-occ/p.upper_count(len(vals)))}


def interval_sup(arrivals: list[int],lo: float,hi: float) -> dict:
    """Numerical evaluation of exact finite event-set argument; not interval arithmetic."""
    require(bool(arrivals) and 0<=lo<=hi and math.isfinite(hi),"invalid initial interval")
    a,b=1.,0.
    events={lo:[0,0],hi:[0,0]}
    terms=[]
    for n in arrivals:
        require(type(n) is int and 0<=n<=8,"invalid arrival")
        a*=p.A
        b=p.A*(b+.5*n)
        c=b-.5
        terms.append((-c/a,a,c))
        left=max(lo,(.4-b)/a)
        right=min(hi,(.6-b)/a)
        if left<=right:
            events.setdefault(left,[0,0])[0]+=1
            events.setdefault(right,[0,0])[1]+=1
    terms.sort()
    roots=[x[0] for x in terms]
    pa,pc=[0.],[0.]
    for _,a,c in terms:
        pa.append(pa[-1]+a)
        pc.append(pc[-1]+c)
    n=len(arrivals)
    upper=p.upper_count(n)
    endpoints=[direct_loss(arrivals,x) for x in (lo,hi)]
    best=max(({"x":x,"side":"endpoint",**v} for x,v in zip((lo,hi),endpoints,strict=True)),key=lambda x:x["loss"])
    def evaluate(x: float,side: str,occ: int) -> None:
        nonlocal best
        j=bisect.bisect_right(roots,x)
        mae=max(0.,(2*(pa[j]*x+pc[j])-(pa[-1]*x+pc[-1]))/n)
        require(0<=occ<=n,"invalid occupancy event count")
        loss=.5*(mae/(mae+.5)+1-occ/upper)
        if loss>best["loss"]:
            best={"x":x,"side":side,"mae":mae,"occupancy":occ,"loss":loss}
    active=0
    for x,(starts,ends) in sorted(events.items()):
        if x>lo:
            evaluate(x,"left_limit",active)
        at=active+starts
        evaluate(x,"point",at)
        active=at-ends
        if x<hi:
            evaluate(x,"right_limit",active)
        require(active>=0,"negative interval occupancy")
    require(active==0,"unclosed occupancy events")
    endpoint=max(v["loss"] for v in endpoints)
    return {"endpoint_loss":endpoint,"supremum_loss":best["loss"],"excess":best["loss"]-endpoint,"witness":best}
