"""Outward rational interval arithmetic and independent matrix certificate."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
import itertools
import math
import re

SCALE=2**160
TIMES=(0,3,18,60,120)
PRIMARY=(0,1,2,4)
WIDTH=F(1,16)
MAX_ERROR=F(1,4)
V_ERROR=F(1,64)
TAU=(F(200),F(5,2),F(100),F(6))


def need(ok,msg):
    if not ok:
        raise ValueError(msg)


def q(x):
    x=F(x)
    return f"{x.numerator}/{x.denominator}"


def decode(s):
    need(type(s) is str and len(s)<=256 and re.fullmatch(r"-?(0|[1-9][0-9]*)/[1-9][0-9]*",s) is not None,"rational encoding")
    v=F(s)
    need(q(v)==s,"noncanonical rational")
    return v


def point(x):
    x=F(x)
    return x,x


def add(a,b):
    return a[0]+b[0],a[1]+b[1]


def neg(a):
    return -a[1],-a[0]


def sub(a,b):
    return add(a,neg(b))


def mul(a,b):
    p=[x*y for x in a for y in b]
    return min(p),max(p)


def reciprocal(a):
    need(a[0]*a[1]>0,"interval division through zero")
    return 1/a[1],1/a[0]


def div(a,b):
    return mul(a,reciprocal(b))


def isum(seq):
    out=point(0)
    for x in seq:
        out=add(out,x)
    return out


def outward(a,scale=SCALE):
    need(a[0]<=a[1] and type(scale) is int and scale>0,"outward interval")
    return F(math.floor(a[0]*scale),scale),F(math.ceil(a[1]*scale),scale)


def midpoint(a):
    return (a[0]+a[1])/2


def radius(a):
    return (a[1]-a[0])/2


def maxabs(a):
    return max(abs(a[0]),abs(a[1]))


def encode(a):
    return [q(x) for x in a]


@lru_cache(maxsize=128)
def exponential(x):
    """Taylor lower/upper bounds; no host libm used in the proof."""
    need(type(x) is F and abs(x)<=100,"exp proof domain")
    if x<0:
        return outward(reciprocal(exponential(-x)))
    if x==0:
        return point(1)
    n=0
    t=x
    while t>F(1,2):
        t/=2;n+=1
    term=F(1);total=term
    for k in range(1,33):
        term=term*t/k
        total+=term
    tail=(term*t/33)/(1-t/34)
    bound=outward((total,total+tail))
    for _ in range(n):
        bound=outward(mul(bound,bound))
    return bound


def inverse(matrix):
    n=len(matrix)
    need(n>0 and all(len(row)==n for row in matrix),"square inverse")
    ident=[[F(i==j) for j in range(n)] for i in range(n)]
    a=[list(row)+list(ident[i]) for i,row in enumerate(matrix)]
    for k in range(n):
        j=next((j for j in range(k,n) if a[j][k]),None)
        need(j is not None,"singular midpoint")
        a[k],a[j]=a[j],a[k]
        p=a[k][k];a[k]=[x/p for x in a[k]]
        for i in range(n):
            if i==k:
                continue
            p=a[i][k];a[i]=[x-p*y for x,y in zip(a[i],a[k],strict=True)]
    b=[row[n:] for row in a]
    for x,y in ((matrix,b),(b,matrix)):
        need([[sum((x[i][k]*y[k][j] for k in range(n)),F(0)) for j in range(n)] for i in range(n)]==ident,
             "inverse two-sided identity")
    return b


def determinant(matrix):
    n=len(matrix)
    need(n==4 and all(len(row)==4 for row in matrix),"determinant dimension")
    terms=[]
    for p in itertools.permutations(range(n)):
        sign=(-1)**sum(p[i]>p[j] for i in range(n) for j in range(i+1,n))
        term=point(sign)
        for i,j in enumerate(p):
            term=mul(term,matrix[i][j])
        terms.append(term)
    return isum(terms)


@lru_cache(maxsize=1)
def model():
    block=reciprocal(add(point(1),div(exponential(F(93,25)),point(F(357,100)))))
    knee=exponential(F(-5,2))
    rows=[];offsets=[]
    for t in TIMES:
        e=[exponential(-F(t)/tau) for tau in TAU]
        rows.append((mul(point(24),e[0]),mul(point(-6),e[1]),
                     mul(mul(point(-6),block),e[2]),mul(point(5),e[3])))
        offsets.append(add(sub(point(100),mul(point(20),knee)),mul(point(20),sub(point(1),e[0]))))
    a=[rows[i] for i in PRIMARY]
    mid=[[midpoint(x) for x in row] for row in a]
    inv=inverse(mid)
    det=determinant(a)
    need(det[0]*det[1]>0,"physical matrix rank not certified")
    hnorm=max(sum(map(maxabs,row)) for row in a)
    bnorm=max(sum(map(abs,row)) for row in inv)
    errornorm=max(sum(map(radius,row)) for row in a)
    contraction=bnorm*errornorm
    need(contraction<1,"inverse perturbation certificate failed")
    return tuple(rows),tuple(offsets),tuple(tuple(x) for x in inv),det,hnorm,bnorm,contraction


def matrix_certificate():
    rows,offsets,b,det,hnorm,bnorm,contraction=model()
    condition=hnorm*bnorm/(1-contraction)
    return {"primary_times_ms":[TIMES[i] for i in PRIMARY],"heldout_time_ms":60,
            "determinant_interval":encode(outward(det,2**40)),
            "inverse_infinity_norm_upper":q(outward((bnorm,bnorm),2**40)[1]),
            "condition_infinity_upper":q(outward((condition,condition),2**40)[1]),
            "inverse_perturbation_upper":q(outward((contraction,contraction),2**100)[1]),
            "conditional_current_rank":4,"conditional_cell_rank":5,
            "conditional_32_cell_rank":160,
            "scope":"IDEAL_INDEPENDENT_CELL_CLAMP_KNOWN_PARAMETERS_ONLY"}


def current_interval(t,x):
    need(type(t) is int and t in TIMES and len(x)==4 and all(type(v) is F and 0<=v<=1 for v in x),"nominal current domain")
    rows,offsets,*_=model()
    i=TIMES.index(t)
    return add(offsets[i],isum(mul(a,point(v)) for a,v in zip(rows[i],x,strict=True)))


def reachability():
    # Frozen EXP06B quiet domain, no impulses or resets during 2 ms.
    decay=exponential(F(-1,3))
    upper=mul(point(F(1,2)),decay)
    need(upper[1]<F(2,5),"quiet target bound")
    return {"horizon_ms":2,"max_terminal_GABA_nS":encode(outward(upper,2**40)),
            "target_band_nS":[q(F(2,5)),q(F(3,5))],
            "all_quiet_action_strings":3**20,"guaranteed_terminal_band":"IMPOSSIBLE_ON_QUIET_DOMAIN",
            "max_incremental_source_charge_pC":q(F(4)),
            "wait_incremental_source_charge_pC":q(F(0)),
            "unrestricted_action_time_support":[0,1,2,3],
            "guaranteed_common_source_groups":[],
            "scientific_promotion_authorized":False}
