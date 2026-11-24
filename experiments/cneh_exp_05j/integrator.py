"""Adaptive event-resolved reference-plant candidate. No policy authority."""
from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction as F
import math

import numpy as np
from scipy.integrate import RK45

END=51.2
TIMES=np.arange(513,dtype=np.float64)/10.
MODES=((1,0),(0,1),(1,1),(0,0))
SWITCHES=(12.8,25.6,38.4)
CURRENT_SWITCHES=tuple(k/10. for k in range(64,512,64))
PROFILES={"LOOSE":(1e-9,1e-11,.05),"TIGHT":(1e-11,1e-13,.025)}
ROOT_WIDTH=F(1,2**70)


def need(c,msg):
    if not c:
        raise ValueError(msg)


def hx(x):
    x=float(x)
    need(math.isfinite(x),"nonfinite event datum")
    return x.hex()


def ratio(x):
    return [x.numerator,x.denominator]


def polynomial(p,x):
    y=F(0)
    for c in reversed(p):
        y=y*x+c
    return y


def derivative(p):
    return tuple(k*c for k,c in enumerate(p) if k)


def bernstein(p):
    n=len(p)-1
    return tuple(sum((p[k]*F(math.comb(i,k),math.comb(n,k))
                      for k in range(i+1)),F(0)) for i in range(n+1))


def split(b):
    left,right=[b[0]],[b[-1]]
    row=b
    while len(row)>1:
        row=tuple((a+c)/2 for a,c in zip(row[:-1],row[1:],strict=True))
        left.append(row[0]);right.append(row[-1])
    return tuple(left),tuple(reversed(right))


def first_upcross(p):
    """Exact rational root isolation of the numerical polynomial, not the ODE."""
    p=tuple(F(x) for x in p)
    need(len(p)>=2 and p[0]<0,"dense segment starts at/above threshold")
    dp=derivative(p)

    def search(b,l,u,depth):
        if max(b)<0 or (max(b)<=0 and b[0]<0 and b[-1]<0):
            return None
        if all(a<=c for a,c in zip(b[:-1],b[1:],strict=True)) and b[0]<0<=b[-1]:
            if b[-1]==0:
                l=u
            else:
                while u-l>ROOT_WIDTH:
                    m=(l+u)/2
                    v=polynomial(p,m)
                    if v==0:
                        l=u=m
                        break
                    if v<0:
                        l=m
                    else:
                        u=m
            m=(l+u)/2
            need(polynomial(dp,m)>0,"nontransverse numerical root")
            return l,u
        need(depth<80,"unresolved dense root/grazing")
        lb,rb=split(b)
        m=(l+u)/2
        found=search(lb,l,m,depth+1)
        return found if found is not None else search(rb,m,u,depth+1)

    return search(bernstein(p),F(0),F(1),0)


def dense_polynomials(dense):
    need(dense.Q.shape==(2,4) and dense.h>0 and np.isfinite(dense.Q).all()
         and np.isfinite(dense.y_old).all(),"unexpected RK45 dense contract")
    h=F(float(dense.h))
    return tuple((F(float(dense.y_old[i])),)+tuple(h*F(float(q)) for q in dense.Q[i])
                 for i in range(2))


def dense_crossing(dense):
    # Directed upper bound, using x^k in [0,1]. A negative upper bound
    # proves no threshold crossing for the represented dense polynomial.
    up=math.nextafter(float(dense.y_old[0])-30.,math.inf)
    for q in dense.Q[0]:
        if q>0:
            c=math.nextafter(float(dense.h)*float(q),math.inf)
            up=math.nextafter(up+c,math.inf)
    if up<0:
        return None
    V,w=dense_polynomials(dense)
    p=(V[0]-30,)+V[1:]
    found=first_upcross(p)
    if found is None:
        return None
    l,u=found
    m=(l+u)/2
    absolute=F(float(dense.t_old))+F(float(dense.h))*m
    t=float(absolute)
    vpre=float(polynomial(V,m))
    wpre=float(polynomial(w,m))
    slope=float(polynomial(derivative(p),m)/F(float(dense.h)))
    need(abs(vpre-30.)<=1e-6 and slope>0 and math.isfinite(slope),"root residual/derivative")
    return {"t_ms":hx(t),"t_old_ms":hx(dense.t_old),"h_ms":hx(dense.h),
            "y_old":[hx(x) for x in dense.y_old],"Q":[[hx(x) for x in row] for row in dense.Q],
            "x_lo":ratio(l),"x_hi":ratio(u),"threshold_derivative_mV_ms":hx(slope),
            "pre":[hx(vpre),hx(wpre)],"post":[hx(-58.),hx(wpre+80.)]}


def group_at(arm,time):
    need(arm in ("WAIT","G0","G1","ALTERNATE"),"arm")
    return None if arm=="WAIT" else 0 if arm=="G0" else 1 if arm=="G1" else bisect_right(CURRENT_SWITCHES,time)%2


def mode_at(time):
    return bisect_right(SWITCHES,time)


def routed_arrivals(ledgers):
    rows=[]
    for i in range(24,32):
        for event in ledgers[i]:
            t=float.fromhex(event["t_ms"])
            mode=mode_at(t)
            if t<END and MODES[mode][(i-24)//4]:
                rows.append({"t_ms":event["t_ms"],"source":i,"mode":mode,"increment_nS":.5})
    return sorted(rows,key=lambda x:(float.fromhex(x["t_ms"]),x["source"]))


def cell(initial,external,incoming,arm,i,profile):
    rtol,atol,maxstep=PROFILES[profile]
    changes=set(SWITCHES)|set(external)|set(incoming)
    if arm=="ALTERNATE":
        changes.update(CURRENT_SWITCHES)
    boundaries=sorted({0.,END}|changes)
    need(boundaries[0]==0. and boundaries[-1]==END,"invalid forcing boundary")
    samples=np.empty((513,5),dtype=np.float64)
    y=np.array(initial[:2],dtype=float)
    g=np.array(initial[2:],dtype=float)
    samples[0]=initial
    slot=1
    events=[]
    steps=0
    step_sizes=set()
    external=set(external)
    for start,end in zip(boundaries[:-1],boundaries[1:],strict=True):
        if start in external:
            g[0]+=.7*.3
            g[1]+=.3*.3
        g[2]+=incoming.get(start,0.)
        g0=g.copy()
        group=group_at(arm,(start+end)/2.)
        current=300. if i<16 else 500. if group is not None and 24+4*group<=i<28+4*group else 0.

        def conductance(time):
            dt=time-start
            return (g0[0]*math.exp(-dt/2.5),g0[1]*math.exp(-dt/100.),g0[2]*math.exp(-dt/6.))

        def rhs(time,state):
            v,w=state
            ga,gn,gg=conductance(time)
            z=-.062*v
            if z>700.:
                e=math.exp(-z);block=e/(e+1./3.57)
            else:
                block=1./(1.+math.exp(z)/3.57)
            syn=ga*v+gn*block*v+gg*(v+70.)
            return ((-10.*(v+70.)+20.*math.exp(min((v+55.)/2.,20.))-w-syn+current)/150.,
                    (2.*(v+70.)-w)/200.)

        time=start
        while time<end:
            need(y[0]<30. and np.isfinite(y).all(),"invalid segment initial state")
            solver=RK45(rhs,time,y,end,rtol=rtol,atol=atol,max_step=maxstep)
            hit=False
            while solver.status=="running":
                message=solver.step()
                need(solver.status!="failed","adaptive RK45 failed: "+str(message))
                dense=solver.dense_output()
                steps+=1
                need(steps<=1000000 and dense.t>dense.t_old,"no progress/step budget")
                step_sizes.add(hx(dense.h))
                event=dense_crossing(dense)
                stop=float.fromhex(event["t_ms"]) if event is not None else float(solver.t)
                need(dense.t_old<stop<=solver.t,"event outside accepted step")
                if event is not None:
                    # Coincident forcing/threshold events require a separate
                    # simultaneous-event contract, not a floating order guess.
                    need(all(abs(stop-b)>1e-9 for b in boundaries),"ambiguous threshold/forcing coincidence")
                    event["conductance"]=[hx(x) for x in conductance(stop)]
                    event["forcing_interval_ms"]=[hx(start),hx(end)]
                    y=np.array([float.fromhex(x) for x in event["post"]],dtype=float)
                    events.append(event)
                    need(len(events)==1 or float.fromhex(events[-2]["t_ms"])<stop,"nonmonotone events")
                while slot<len(TIMES) and TIMES[slot]<=stop:
                    at=float(TIMES[slot])
                    need(at>=dense.t_old,"sample chronology")
                    vw=y if event is not None and at==stop else dense(at)
                    samples[slot]=(*vw,*conductance(at))
                    slot+=1
                if event is not None:
                    time=stop
                    hit=True
                    break  # discard accepted overshoot, restart at reset
            if not hit:
                need(solver.status=="finished" and solver.t==end,"unfinished forcing interval")
                y=solver.y.copy()
                time=end
        g=np.array(conductance(end),dtype=float)
    need(slot==len(TIMES) and np.isfinite(samples).all(),"sample completeness")
    need(np.min(samples[:,0])>=-100. and np.max(samples[:,0])<30. and np.min(samples[:,2:])>=0.,"physical envelope")
    return samples,events,steps,step_sizes


def run(initial,tape,arm,profile):
    need(initial.shape==(5,32) and tape.shape==(512,32) and profile in PROFILES,"input roster")
    samples=np.empty((513,5,32),dtype=float)
    events=[[] for _ in range(32)]
    step_sizes=set()
    steps=[]
    for i in range(24,32):
        external=[float(TIMES[t]) for t in range(512) if tape[t,i]]
        samples[:,:,i],events[i],n,h=cell(initial[:,i],external,{},arm,i,profile)
        steps.append((i,n));step_sizes.update(h)
    arrivals=routed_arrivals(events)
    incoming={}
    for event in arrivals:
        t=float.fromhex(event["t_ms"])
        incoming[t]=incoming.get(t,0.)+event["increment_nS"]
    for i in range(24):
        external=[float(TIMES[t]) for t in range(512) if tape[t,i]]
        samples[:,:,i],events[i],n,h=cell(initial[:,i],external,incoming if i<16 else {},arm,i,profile)
        steps.append((i,n));step_sizes.update(h)
    need(len(step_sizes)>1 and sorted(i for i,n in steps)==list(range(32)),"adaptive step roster")
    return {"profile":profile,"samples":samples.tolist(),"events":events,"arrivals":arrivals,
            "accepted_steps":sum(n for _,n in steps),"steps_per_neuron":[n for _,n in sorted(steps)],
            "distinct_step_sizes":len(step_sizes)}
