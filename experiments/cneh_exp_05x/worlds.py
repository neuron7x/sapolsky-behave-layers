"""Frozen architecture-independent public OOD manifest."""
from __future__ import annotations

import hashlib
import itertools
import json
import math

N=1000
SHARDS=40
PER_SHARD=25
END=51.2
STRATA=("OFF_GRID","BURST","NEAR_PAIR","COINCIDENT")
ARMS=("WAIT","G0","G1","ALTERNATE")
MODES=((1,0),(0,1),(1,1),(0,0))
CURRENT=tuple(k/10. for k in range(64,512,64))


def need(c,msg):
    if not c:
        raise ValueError(msg)


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(canonical(value))


def hx(x):
    v=float(x)
    need(math.isfinite(v),"nonfinite float")
    return v.hex()


def f(x):
    need(type(x) is str,"float type")
    v=float.fromhex(x)
    need(math.isfinite(v) and v.hex()==x,"noncanonical float")
    return v


def coord(i,tag,n):
    return int.from_bytes(hashlib.sha256(f"CNEH-EXP-05X-V1:{i}:{tag}".encode()).digest(),"big")%n


def world(i):
    need(type(i) is int and 0<=i<N,"world identity")
    stratum=i//250
    mode_order=list(itertools.permutations(range(4)))[coord(i,"routes",24)]
    switches=[12.8,25.6,38.4] if stratum==3 else [(base+coord(i,"switch"+str(j),1023))/1024. for j,base in enumerate((12288,25344,38400))]
    initial=[[],[],[],[],[]]
    external=[]
    for j in range(32):
        v=-74.+coord(i,f"V:{j}",1121)/64.
        w=coord(i,f"w:{j}",1281)/64.
        # Source activation remains inside the frozen AdEx model and below Vpeak.
        if j in (24,28) and stratum in (1,2,3):
            v=-54.+coord(i,f"hot:{j}",257)/64.
        for k,x in enumerate((v,w,0.,0.,0.)):
            initial[k].append(hx(x))
        times=set()
        t=(1024+coord(i,f"syn:{j}",49152))/1024.
        times.add(t)
        if stratum==1:
            for k in range(1,6):
                times.add(t+k/1024.)
        elif stratum==2:
            times.add(t+2.**-20)
            times.add(t+2.**-19)
        elif stratum==3:
            times.add(switches[(i+j)%3])
            times.add(CURRENT[(i+j)%len(CURRENT)])
        need(all(0<t<END for t in times),"external impulse domain")
        external.append([hx(t) for t in sorted(times)])
    return {"id":i,"stratum":STRATA[stratum],"arm":ARMS[i%4],"initial":initial,
            "external":external,"mode_order":list(mode_order),"switches":[hx(t) for t in switches],
            "current_switches":[hx(t) for t in CURRENT]}


def manifest():
    worlds=[world(i) for i in range(N)]
    need(len({digest({k:v for k,v in w.items() if k!="id"}) for w in worlds})==N,"duplicate physical world")
    return {"schema":"CNEH-EXP-05X-INPUT-V1","worlds":worlds}


def validate_manifest(value):
    need(value==manifest(),"input roster or frozen generator drift")
