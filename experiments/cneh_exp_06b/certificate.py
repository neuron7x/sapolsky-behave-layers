"""Rational first-exit certificates for the frozen realized AdEx plant.

The argument is for continuous trajectories and the actual discrete count
projection, not a linearization of smooth voltage readout.
"""
from __future__ import annotations

from fractions import Fraction as F
import math

N=32
DIM=160
T=F(2)
ACTIVE_T=F(1,10)
INITIAL=((F(-74),F(-68)),(F(0),F(24)),(F(0),F(1,10)),(F(0),F(1,10)),(F(0),F(1,2)))
QUIET=((F(-80),F(-58)),(F(-1),F(32)),*INITIAL[2:])
FIELDS=("V","w","AMPA","NMDA","GABA")


def need(ok,message):
    if not ok:
        raise ValueError(message)


def enc(q):
    q=F(q)
    return [q.numerator,q.denominator]


def pair(lo,hi):
    return [enc(lo),enc(hi)]


def add(a,b):
    return a[0]+b[0],a[1]+b[1]


def mul(a,b):
    values=[x*y for x in a for y in b]
    return min(values),max(values)


def scale(a,c):
    return mul(a,(F(c),F(c)))


def interval_rhs(box,current):
    """Outward interval arithmetic with exp/block bounded independently."""
    V,w,ga,gn,gg=box
    dv=add(V,(F(70),F(70)))
    need(V[1]<=-55 and V[1]<0,"quiet exponential/reversal envelope")
    leak=scale(dv,-10)
    adaptation=scale(w,-1)
    excitation=(F(0),F(20))
    ampa=scale(mul(ga,V),-1)
    nmda=scale(mul(mul(gn,(F(0),F(1))),V),-1)
    gaba=scale(mul(gg,dv),-1)
    total=(F(0),F(0))
    for term in (leak,adaptation,excitation,ampa,nmda,gaba,current):
        total=add(total,term)
    return scale(total,F(1,150)),scale(add(scale(dv,2),adaptation),F(1,200))


def reachable(initial,derivative,T):
    # Valid also at each earlier t in [0,T], even if derivative sign is fixed.
    return (initial[0]+min(F(0),derivative[0]*T),
            initial[1]+max(F(0),derivative[1]*T))


def strict_interior(bounds,box):
    return box[0]<bounds[0]<=bounds[1]<box[1]


def quiet_certificate():
    dv,dw=interval_rhs(QUIET,(F(0),F(500)))
    # Independent explicit component-bound summation as frozen in protocol.
    manual_dv=(F(-120-32-6,150),F(100+20+1+16+5+500,150))
    manual_dw=(F(-20-32,200),F(24+1,200))
    need(dv==manual_dv and dw==manual_dw,"quiet interval derivation")
    v,w=reachable(INITIAL[0],dv,T),reachable(INITIAL[1],dw,T)
    need(strict_interior(v,QUIET[0]) and strict_interior(w,QUIET[1]),"quiet first-exit contradiction")
    need(QUIET[0][1]<30,"threshold excluded")
    # With no external tape and no threshold exit, all conductances
    # follow dg/dt=-g/tau and cannot leave their nonnegative ranges.
    return {"horizon_ms":enc(T),"frames":20,"action_strings":3**20,
            "allowed_action_grammar":["WAIT","G0","G1"],"arbitrary_allowed_route_switches":True,
            "initial_box":{k:pair(*v) for k,v in zip(FIELDS,INITIAL,strict=True)},
            "first_exit_box":{k:pair(*v) for k,v in zip(FIELDS,QUIET,strict=True)},
            "dV_bounds":pair(*dv),"dw_bounds":pair(*dw),"reachable_V":pair(*v),"reachable_w":pair(*w),
            "first_exit_excluded":True,"public_count_sequence":[[0,0]]*20,
            "local_observation_map":"CONSTANT_ON_OPEN_CONTINUOUS_STATE_SET",
            "sensitivity_gramian_rank":0,"continuous_state_nullity":DIM,
            "gramian_scope":"FIXED_KNOWN_ACTIONS_ON_OPEN_SILENT_SET_ONLY"}


def active_certificate():
    # e^10 >= finite positive Taylor sum. e < 3 via n!>=2^(n-1),
    # strict for n>=4. Therefore exp(min(x,20)) <= exp(20)<3^20.
    exp10=sum((F(10)**n/F(math.factorial(n)) for n in range(21)),F(0))
    need(exp10>20000,"exp lower bound")
    pre_v=(F(-35),F(30));pre_w=(F(-1),F(1))
    pre_dw=scale(add(scale(add(pre_v,(F(70),F(70))),2),scale(pre_w,-1)),F(1,200))
    w_pre=reachable((F(0),F(0)),pre_dw,ACTIVE_T)
    need(strict_interior(w_pre,pre_w),"active pre-reset adaptation enclosure")
    dv_min=F(400000-1000-1,150)
    dv_max=F(20*3**20+501,150)
    need(dv_min>0 and dv_max>dv_min,"active crossing slope")
    time_lo=F(65)/dv_max
    time_hi=F(65)/dv_min
    need(F(1,10**9)<time_lo<time_hi<F(1,40)<ACTIVE_T-F(1,10**9),"active crossing time enclosure")
    # Reset -58, w jump exactly +80; conductances are zero in source.
    post_v=(F(-65),F(-55));post_w=(F(78),F(82))
    post_dv,post_dw=interval_rhs((post_v,post_w,(F(0),F(0)),(F(0),F(0)),(F(0),F(0))),(F(0),F(500)))
    post_V=reachable((F(-58),F(-58)),post_dv,ACTIVE_T)
    post_W=reachable((F(79),F(81)),post_dw,ACTIVE_T)
    need(strict_interior(post_V,post_v) and strict_interior(post_W,post_w) and post_v[1]<30,
         "post-reset first exit excluded")
    # Other cells stay in QUIET for .1 ms, including the receiver GABA
    # jump 0 -> .5 if the active edge exists.
    qv,qw=interval_rhs(QUIET,(F(0),F(500)))
    need(strict_interior(reachable((F(-70),F(-70)),qv,ACTIVE_T),QUIET[0])
         and strict_interior(reachable((F(0),F(0)),qw,ACTIVE_T),QUIET[1]),"other cells quiet")
    # exp(-z)>=1-z, strict for z>0. Arrival time >0 and decay interval <.1.
    g_lower=F(1,2)*(1-ACTIVE_T/F(6))
    need(g_lower==F(59,120)>0,"active conductance difference")
    return {"horizon_ms":enc(ACTIVE_T),"exp10_taylor_lower":enc(exp10),
            "source":24,"exact_source_spike_count":1,"receiver_spike_count":0,
            "source_event_time_bounds_ms":pair(time_lo,time_hi),
            "post_reset_V_bounds":pair(*post_V),"post_reset_w_bounds":pair(*post_W),
            "connected_modes":[0,2],"disconnected_modes":[1,3],
            "connected_GABA_strict_lower_nS":enc(g_lower),"disconnected_GABA_nS":enc(F(0)),
            "all_actions_same_public_counts":True,"active_graph_counterexample":True}


def certify_silent_inputs(initial,frames,actions):
    need(len(initial)==5 and all(len(row)==32 for row in initial),"initial roster")
    for bounds,row in zip(INITIAL,initial,strict=True):
        for value in row:
            x=F(float.fromhex(value))
            need(bounds[0]<=x<=bounds[1],"initial outside certified box")
    need(len(frames)==len(actions)==20,"silent horizon roster")
    for k,(frame,action) in enumerate(zip(frames,actions,strict=True)):
        need(frame.tick==k and action in ("WAIT","G0","G1"),"unsupported decision")
        need(all(not seq for seq in frame.external),"external impulse outside silent certificate")
        need(type(frame.mode) is int and 0<=frame.mode<4,"hidden route domain")


def certify_result(value):
    need(value=={"quiet":quiet_certificate(),"active":active_certificate()},"forged mathematical certificate/rank")
    return value


def certificate():
    return certify_result({"quiet":quiet_certificate(),"active":active_certificate()})
