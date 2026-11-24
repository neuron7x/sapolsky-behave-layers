"""Frozen finite witnesses for the analytical observation counterexample."""
from __future__ import annotations

import itertools

from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_06a import runtime as rt

ACTIONS=("WAIT","G0","G1")
PREFIXES=tuple(itertools.product(ACTIONS,repeat=3))
VARIANTS=("BASE","V_ONLY","W_ONLY","GABA_ONLY","GRAPH_ONLY","COMBINED")
HORIZON=20
SHARDS=tuple([f"silent-{i}" for i in range(9)]+[f"gramian-{i}" for i in range(3)]+["active"])


def initial(values):
    return [[w.hx(x)]*32 for x in values]


def silent(variant):
    values=(-71.,12.,1./16.,1./16.,.25)
    if variant=="V_ONLY":
        values=(-72.,*values[1:])
    elif variant=="W_ONLY":
        values=(values[0],13.,*values[2:])
    elif variant=="GABA_ONLY":
        values=(*values[:4],.375)
    elif variant=="COMBINED":
        values=(-70.,10.,1./32.,1./32.,.125)
    elif variant not in ("BASE","GRAPH_ONLY"):
        raise ValueError("unknown variant")
    mode=1 if variant=="GRAPH_ONLY" else 2 if variant=="COMBINED" else 0
    return initial(values),mode


def active():
    values=initial((-70.,0.,0.,0.,0.))
    values[0][24]=w.hx(-35.)
    return values


def actions(index):
    prefix=PREFIXES[index]
    return [prefix[k%3] for k in range(HORIZON)]


def frame(tick,mode):
    return rt.Frame(tick,mode,(),((),)*32)


def perturbed(coordinate,sign):
    if type(coordinate) is not int or not 0<=coordinate<160 or sign not in (-1,1):
        raise ValueError("coordinate/sign")
    a,mode=silent("BASE")
    i,j=divmod(coordinate,32)
    step=1./64. if i<2 else 1./4096.
    a[i][j]=w.hx(w.f(a[i][j])+sign*step)
    return a,mode,step


def roster(shard):
    """Canonical input identity, independent of the executed result."""
    if shard not in SHARDS:
        raise ValueError("unknown shard")
    if shard=="active":
        return [(a,m) for a in ACTIONS for m in range(4)]
    kind,n=shard.split("-")
    n=int(n)
    if kind=="silent":
        return [(i,v) for i in range(3*n,3*n+3) for v in VARIANTS]
    return [(ACTIONS[n],-1,0)]+[(ACTIONS[n],i,s) for i in range(160) for s in (-1,1)]
