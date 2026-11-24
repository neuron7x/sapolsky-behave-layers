"""Finite-mode causal support, arrival decoding and constructive counterexamples."""
from __future__ import annotations

import itertools
import math

from experiments.cneh_exp_04c import qualification as q

MODES=((1,0),(0,1),(1,1),(0,0))
ALL=(0,1,2,3)
WINDOWS=((650,750),(1450,1550),(2250,2350))
TOL=1e-9


def need(condition,reason):
    if not condition:
        raise ValueError(reason)


def decode_count(residual):
    need(len(residual)==16 and all(math.isfinite(x) for x in residual),"invalid public residual")
    need(q.QUANTUM>2*q.RADIUS,"arrival bands overlap")
    matches=[n for n in range(9) if all(abs(x-q.QUANTUM*n)<=q.RADIUS for x in residual)]
    need(len(matches)==1,"arrival count not uniquely certified")
    return matches[0]


def count_interval(bits):
    need(len(bits)==4 and all(x is None or type(x) is int and x in (0,1) for x in bits),"invalid source symbols")
    ones=sum(x==1 for x in bits)
    return ones,ones+bits.count(None)


def compatible_count(count,bits):
    need(type(count) is int and 0<=count<=8 and len(bits)==8,"invalid count/support coordinates")
    a,b=count_interval(bits[:4]),count_interval(bits[4:])
    return tuple(m for m,(i,j) in enumerate(MODES)
                 if i*a[0]+j*b[0]<=count<=i*a[1]+j*b[1])


def native_count(mode,bits):
    need(mode in ALL and len(bits)==8 and all(type(x) is int and x in (0,1) for x in bits),"invalid full source bits")
    return MODES[mode][0]*sum(bits[:4])+MODES[mode][1]*sum(bits[4:])


def common_groups(modes):
    need(bool(modes) and set(modes)<=set(ALL),"empty or invalid support")
    return tuple(g for g in (0,1) if all(MODES[m][g] for m in modes))


def window_at(t,windows):
    return next((w for w in windows if w[0]<=t<=w[1]),None)


def successors(state,t,windows=WINDOWS):
    mode,used=state
    need(mode in ALL and used in (0,1) and type(t) is int and t>=0,"invalid automaton state")
    if t==0:
        need(state==(0,0),"unknown initial mode")
        return ((0,0),)
    w=window_at(t,windows)
    if w is None:
        return ((mode,0),)
    if t==w[0]:
        used=0
    if used:
        return ((mode,1),)
    return ((mode,0),)+tuple((m,1) for m in ALL if m!=mode)


def advance(states,t,windows=WINDOWS):
    need(bool(states),"empty causal support")
    parents={}
    for previous in sorted(states):
        for following in successors(previous,t,windows):
            parents.setdefault(following,previous)
    return parents


def project(states):
    return tuple(sorted({m for m,_ in states}))


class Observer:
    """Filters previous transition first; then branches before the next action."""
    def __init__(self,windows=WINDOWS,retain_paths=False):
        self.windows=tuple(windows)
        need(all(type(lo) is int and type(hi) is int and 1<=lo<=hi for lo,hi in self.windows)
             and all(a[1]<b[0] for a,b in zip(self.windows[:-1],self.windows[1:])),"invalid switch grammar")
        self.t=-1
        self.states={(0,0)}
        self.history=[] if retain_paths else None

    def step(self,t,transition_support=None):
        need(t==self.t+1,"nonconsecutive observer tick")
        if t==0:
            need(transition_support is None,"no previous transition at initialization")
            last=None
            parents={(0,0):None}
        else:
            need(transition_support and set(transition_support)<=set(ALL),"invalid previous-transition support")
            remaining={s for s in self.states if s[0] in transition_support}
            need(bool(remaining),"MODEL_CLASS_VIOLATION")
            last=project(remaining)
            parents=advance(remaining,t,self.windows)
        self.states=set(parents)
        self.t=t
        if self.history is not None:
            self.history.append(parents)
        return last,project(self.states)

    def alternate(self,truth):
        need(self.history is not None and self.t>=0 and truth in ALL,"witness context")
        alternatives=sorted(s for s in self.states if s[0]!=truth)
        if not alternatives:
            return None
        state=alternatives[0]
        path=[]
        for t in range(self.t,-1,-1):
            path.append(state[0])
            state=self.history[t][state]
        path.reverse()
        need(state is None and len(path)==self.t+1 and path[-1]!=truth,"invalid backtrack")
        return path


def validate_path(path,counts,full_bits,windows=WINDOWS):
    """Independent verifier; no automaton or predecessor table is consulted."""
    need(bool(path) and path[0]==0 and len(counts)==len(full_bits)==len(path)-1,"witness roster")
    changes=[]
    previous=path[0]
    used=set()
    for t,mode in enumerate(path):
        need(mode in ALL,"invalid witness mode")
        if t and mode!=previous:
            matching=[w for w in windows if w[0]<=t<=w[1]]
            need(len(matching)==1 and matching[0] not in used,"witness violates schedule class")
            used.add(matching[0])
            changes.append([t,mode])
        if t<len(counts):
            need(native_count(mode,full_bits[t])==counts[t],"witness changes public arrival count")
        previous=mode
    return changes


def block_feasibility(states,t,groups,windows=WINDOWS):
    """Open-loop route guarantees before any future observation is consumed."""
    current=set(states)
    count=0
    for offset,group in enumerate(groups):
        if offset:
            current=set(advance(current,t+offset,windows))
        if group is not None:
            need(group in (0,1),"invalid plan group")
            count+=group in common_groups(project(current))
    return count


def count_qualification():
    # Independent binary completion enumeration. Each ternary vector includes
    # exactly every completion; no probabilistic independence is assumed.
    vectors=cases=0
    patterns={"NO_SPIKES":0,"ONE_GROUP":0,"EQUAL_NONZERO":0,"UNEQUAL_NONZERO":0}
    for a,b in itertools.product(range(5),repeat=2):
        n=[i*a+j*b for i,j in MODES]
        key="NO_SPIKES" if a==b==0 else "ONE_GROUP" if a==0 or b==0 else "EQUAL_NONZERO" if a==b else "UNEQUAL_NONZERO"
        patterns[key]+=1
        need((len(set(n))==4)==(key=="UNEQUAL_NONZERO"),"arrival separation theorem falsified")
    for bits in itertools.product((None,0,1),repeat=8):
        vectors+=1
        erased=[i for i,v in enumerate(bits) if v is None]
        expected=[set() for _ in range(4)]
        for fill in itertools.product((0,1),repeat=len(erased)):
            full=list(bits)
            for i,v in zip(erased,fill,strict=True):
                full[i]=v
            for m in ALL:
                expected[m].add(native_count(m,full))
        for count in range(9):
            actual=compatible_count(count,bits)
            need(actual==tuple(m for m in ALL if count in expected[m]),"count support completion mismatch")
            cases+=4
    need(vectors==3**8 and cases==3**8*9*4,"count fixture roster")
    return {"ternary_vectors":vectors,"mode_count_cases":cases,"count_pairs":patterns}
