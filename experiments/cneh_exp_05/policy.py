"""Certified relaxed GABA envelope and observation-only dual-control pilot."""
from __future__ import annotations

import itertools
import math

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04f import policy as f

ARMS=("DUAL","EXACT_EMULATOR","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
BLOCK=320
ON=160
WAVES=("EARLY","LATE","MIDDLE","SPLIT")
PLANS=tuple((g,w) for g in (0,1) for w in WAVES)
A=q.DECAY
MAX_RUN=25
MIN_GAP=24


def require(condition: bool,reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def upper_count(n: int) -> int:
    require(type(n) is int and n>=0,"invalid sample count")
    cycles,remainder=divmod(n,MAX_RUN+MIN_GAP)
    return MAX_RUN*cycles+min(MAX_RUN,remainder)


def abstract_dp(n: int) -> int:
    """Independent finite enumeration of allowable run placements."""
    require(type(n) is int and n>=0,"invalid horizon")
    best=[0]*(n+1)
    for m in range(1,n+1):
        best[m]=max([best[m-1]]+[length+best[max(0,m-length-MIN_GAP)]
                                  for length in range(1,min(MAX_RUN,m)+1)])
    return best[n]


def certificate() -> dict:
    require(.9*A>.6 and .6*A**24>=.4 and .6*A**25<.4
            and .9*A**24>.6 and .9*A**25<=.6,"structural certificate margin")
    require(all(upper_count(n)==abstract_dp(n) for n in range(201)),"abstract bound disagreement")
    return {"authority":"SOUND_RELAXED_OCCUPANCY_UPPER_ENVELOPE_NOT_ACTUATOR_REACHABILITY",
            "decay":A,"jump_nS":.5,"arrival_inside_band_min_next_nS":.9*A,
            "max_contiguous_samples":MAX_RUN,"min_inter_run_gap":MIN_GAP,
            "bound_320_samples":upper_count(320),"bound_3200_samples":upper_count(3200),
            "stationary_mean_arrivals_per_tick":(1-A)/A,
            "abstract_dp_horizons":201}


def certify_band(flags: list[bool]) -> int:
    run=0
    gap=0
    seen=False
    for flag in flags:
        if flag:
            if run==0 and seen:
                require(gap>=MIN_GAP,"inter-run gap violates certificate")
            run+=1
            require(run<=MAX_RUN,"continuous band run violates certificate")
            seen=True
            gap=0
        else:
            run=0
            gap+=1
    count=sum(flags)
    require(count<=upper_count(len(flags)),"occupancy violates certificate")
    return count


def action(plan: tuple[int,str],offset: int) -> int | None:
    require(plan in PLANS and type(offset) is int and 0<=offset<BLOCK,"invalid plan coordinates")
    group,wave=plan
    active=(offset<160 if wave=="EARLY" else offset>=160 if wave=="LATE" else
            80<=offset<240 if wave=="MIDDLE" else offset<80 or 160<=offset<240)
    return group if active else None


def shadow_step(cell: tuple[float,float,int],current: float,bit: int | None=None) -> tuple[float,float,int]:
    """Approximate native source state without synaptic input, corrected by public spike bit."""
    v,w,_=cell
    dv=(-10.*(v+70.)+20.*math.exp(min((v+55.)/2.,20.))-w+current)/150.
    vv=v+.1*dv
    ww=w+.1*(2.*(v+70.)-w)/200.
    spike=int(vv>=30.) if bit is None else bit
    if spike:
        return -58.,ww+80.,1
    return max(-100.,min(math.nextafter(30.,-math.inf),vv)),ww,0


def advance(shadow: tuple,group: int | None,bits: tuple | None=None) -> tuple:
    return tuple(shadow_step(cell,500. if group==i//4 else 0.,None if bits is None else bits[i])
                 for i,cell in enumerate(shadow))


def score_plans(shadow: tuple,candidates: tuple[int,...],gaba: tuple[float,...]) -> list[dict]:
    mean=math.fsum(gaba)/len(gaba)
    starts=(max(0.,mean-q.EPS),max(0.,mean+q.EPS))
    reachable=[m for m in candidates if m!=3]
    pairs=list(itertools.combinations(d.ALL,2))
    reports=[]
    for plan in PLANS:
        cells=shadow
        histories=[[] for _ in d.ALL]
        for offset in range(BLOCK):
            n0=sum(c[2] for c in cells[:4])
            n1=sum(c[2] for c in cells[4:])
            for mode,(a,b) in enumerate(q.MODES):
                histories[mode].append(a*n0+b*n1)
            cells=advance(cells,action(plan,offset))
        ks=[sum(x!=y for x,y in zip(histories[i],histories[j],strict=True)) for i,j in pairs]
        info=math.fsum(1.-(1.-.75**8)**k for k in ks)/len(ks)
        forecasts=[]
        for mode in reachable:
            for initial in starts:
                g=initial
                vals=[]
                for n in histories[mode]:
                    g=A*(g+.5*n)
                    vals.append(g)
                occupancy=certify_band([.4<=v<=.6 for v in vals])
                mae=math.fsum(abs(v-.5) for v in vals)/BLOCK
                loss=.5*(mae/(mae+.5)+1.-occupancy/upper_count(BLOCK))
                forecasts.append({"mode":mode,"initial_nS":initial,"mae_nS":mae,"in_band_samples":occupancy,"loss":loss})
        cost=max((v["loss"] for v in forecasts),default=0.)
        reports.append({"plan":list(plan),"control_cost":cost,"information_proxy":info,
                        "pair_distinguishing_ticks":ks,"forecasts":forecasts})
    return reports


def choose(arm: str,block: int,scores: list[dict]) -> tuple[int,str]:
    require(arm in ARMS and [tuple(x["plan"]) for x in scores]==list(PLANS),"invalid decision roster")
    if arm=="FIXED_ALTERNATE":
        return block%2,"EARLY"
    def key(s):
        c,i=s["control_cost"],s["information_proxy"]
        require(math.isfinite(c) and math.isfinite(i) and 0<=c<=1 and 0<=i<=1,"invalid objective")
        value=c+.25*(1-i) if arm in ARMS[:2] else c if arm=="CONTROL_ONLY" else 1-i
        group,wave=s["plan"]
        return value,group!=block%2,WAVES.index(wave),group
    return tuple(min(scores,key=key)["plan"])


class Policy:
    def __init__(self,arm: str):
        require(arm in ARMS,"unknown arm")
        self.arm=arm
        self.filter=f.Policy(f.ARMS[0])
        self.shadow=tuple((-70.,0.,0) for _ in range(8))
        self.plan=None

    def observe(self,obs: d.Observation) -> None:
        previous=self.filter.previous
        previous_group=self.filter.last_action_group
        self.filter.observe(obs)
        if previous is None:
            self.shadow=tuple((v,w,s if bit is None else bit)
                              for (v,w,s),bit in zip(self.shadow,obs.bits,strict=True))
        else:
            self.shadow=advance(self.shadow,previous_group,obs.bits)

    def snapshot(self) -> dict:
        return {"filter":self.filter.snapshot(),"shadow":[[v.hex(),w.hex(),s] for v,w,s in self.shadow],
                "plan":None if self.plan is None else list(self.plan),
                "last_action_tick":self.filter.last_action_tick,"last_action_group":self.filter.last_action_group}

    def act(self) -> tuple[int | None,dict | None]:
        obs=self.filter.previous
        require(obs is not None and obs.tick<d.STEPS and self.filter.last_action_tick!=obs.tick,"invalid action timing")
        offset=obs.tick%BLOCK
        decision=None
        if offset==0:
            scores=score_plans(self.shadow,self.filter.candidates,obs.gaba)
            self.plan=choose(self.arm,obs.tick//BLOCK,scores)
            decision={"selected":list(self.plan),"scores":scores}
        require(self.plan in PLANS,"missing block plan")
        group=action(self.plan,offset)
        self.filter.last_action_tick,self.filter.last_action_group=obs.tick,group
        return group,decision


def audit_tape(rows: list[dict],arm: str) -> None:
    require(len(rows)==d.STEPS+1 and [row["tick"] for row in rows]==list(range(d.STEPS+1)),"trace roster")
    p=Policy(arm)
    for row in rows:
        p.observe(d.parse_obs(row))
        require(p.snapshot()==row["policy"],"policy state mismatch")
        if row["tick"]<d.STEPS:
            require(p.act()==(row["group"],row["decision"]),"policy action mismatch")
