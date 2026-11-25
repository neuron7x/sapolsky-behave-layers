"""Exact linear proof checker and two formulations of the frozen H lift.

The checker has no dependency on the dual proposer. Validity follows from
nonnegative linear combinations of the independently reconstructed rows.
"""
from __future__ import annotations

from fractions import Fraction as F
import re

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as i

SCOPE = "CONDITIONAL_SHARED_SAMPLE_LINEAR_FRACTIONAL_OUTER_RELAXATION"
DIM = 7
MAX_DIM = 8
MAX_ROWS = 64
MAX_BITS = 2048
MAX_TEXT = 1024
NEGATIVE = dict(i.NEGATIVE)
OUTER = "CERTIFIED_OUTER_ONLY"
EXCLUDED = "CERTIFIED_INFEASIBLE"
UNVERIFIED = "CALIBRATION_UNVERIFIED"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def bounded(value):
    return (type(value) is F and value.numerator.bit_length() <= MAX_BITS
            and value.denominator.bit_length() <= MAX_BITS)


def encode(value):
    need(bounded(value), "rational bit budget")
    text = a.q(value)
    need(len(text) <= MAX_TEXT, "rational wire budget")
    return text


def decode(value):
    need(type(value) is str and len(value) <= MAX_TEXT and
         re.fullmatch(r"-?(0|[1-9][0-9]*)/[1-9][0-9]*", value) is not None,
         "rational wire schema")
    exact = F(value)
    need(bounded(exact) and encode(exact) == value, "noncanonical rational")
    return exact


def vector(value, dimension):
    need(type(value) is list and len(value) == dimension, "vector wire roster")
    return tuple(decode(x) for x in value)


def dot(left, right):
    return sum((x*y for x,y in zip(left,right,strict=True)),F(0))


def unit(dimension, coordinate, sign=1):
    return tuple(F(sign*int(j==coordinate)) for j in range(dimension))


def row(name, coefficients, rhs):
    return name, tuple(F(x) for x in coefficients), F(rhs)


def system(rows):
    need(type(rows) is tuple and 0 < len(rows) <= MAX_ROWS,"row roster")
    n=len(rows[0][1])
    need(0<n<=MAX_DIM,"dimension budget")
    seen=set()
    for name,coef,rhs in rows:
        need(type(name) is str and re.fullmatch(r"[A-Z0-9_]{1,40}",name) is not None
             and name not in seen,"row identity")
        seen.add(name)
        need(type(coef) is tuple and len(coef)==n and all(map(bounded,coef))
             and bounded(rhs),"rational row domain")
    return n


def system_digest(rows):
    system(rows)
    return sha(canonical([[name,[encode(x) for x in coef],encode(rhs)]
                          for name,coef,rhs in rows]))


def certificate(rows, objective, multipliers):
    n=system(rows)
    need(type(objective) is tuple and len(objective)==n and all(map(bounded,objective)),
         "objective domain")
    need(type(multipliers) is tuple and len(multipliers)==len(rows) and
         all(bounded(x) and x>=0 for x in multipliers),"nonnegative multiplier roster")
    combined=tuple(sum((lam*coef[j] for lam,(_,coef,_) in
                        zip(multipliers,rows,strict=True)),F(0)) for j in range(n))
    need(combined==objective,"dual equality violated")
    bound=dot(multipliers,tuple(rhs for _,_,rhs in rows))
    return {"system_sha256":system_digest(rows),
            "objective":[encode(x) for x in objective],
            "multipliers":[encode(x) for x in multipliers],
            "bound":encode(bound)}


def check(rows, objective, proof):
    n=system(rows)
    need(type(proof) is dict and set(proof)=={"system_sha256","objective","multipliers","bound"},
         "dual certificate schema")
    need(type(proof["system_sha256"]) is str and
         proof["system_sha256"]==system_digest(rows),"dual system identity")
    need(vector(proof["objective"],n)==objective,"dual target identity")
    multipliers=vector(proof["multipliers"],len(rows))
    observed=decode(proof["bound"])
    expected=certificate(rows,objective,multipliers)
    need(canonical(proof)==canonical(expected) and observed==decode(expected["bound"]),
         "dual bound mismatch")
    return observed


def check_infeasible(rows,proof):
    bound=check(rows,(F(0),)*system(rows),proof)
    need(bound<0,"Farkas proof must be strictly negative")
    return True


def row_proof(rows, index):
    n=system(rows)
    need(type(index) is int and 0<=index<len(rows),"row index")
    return certificate(rows,rows[index][1],unit(len(rows),index))


def combine_exclusion(rows, first, second):
    n=system(rows)
    left=vector(first["objective"],n)
    right=vector(second["objective"],n)
    check(rows,left,first); check(rows,right,second)
    need(tuple(x+y for x,y in zip(left,right,strict=True))==(F(0),)*n,
         "opposing objective required")
    multipliers=tuple(x+y for x,y in zip(vector(first["multipliers"],len(rows)),
                                         vector(second["multipliers"],len(rows)),strict=True))
    proof=certificate(rows,(F(0),)*n,multipliers)
    check_infeasible(rows,proof)
    return proof


def scalar_ranges(refs):
    need(type(refs) is dict and set(refs)==set(h.REFS),"reference roster")
    return tuple((name,(max(prior[0],refs[key]-h.R),min(prior[1],refs[key]+h.R)))
                 for name,key,prior in (("GAMMA","gamma",h.GAMMA),
                                       ("DELAY","delay_ms",h.DELAY),
                                       ("TAU","tau_ms",h.TAU)))


def compile(record):
    """Direct normalized inequalities in (x[0:4], b/g, d/g, 1/g)."""
    _,observed,refs=h.parse(record)
    ranges=scalar_ranges(refs)
    rows=[]
    for j in range(4):
        rows.extend((row(f"X{j}_LO",unit(DIM,j,-1),0),
                     row(f"X{j}_HI",unit(DIM,j),1)))
    rows.extend((row("S_LO",unit(DIM,6,-1),-1/h.GAIN[1]),
                 row("S_HI",unit(DIM,6),1/h.GAIN[0])))
    for name,j,prior in (("B",4,i.PRIORS[5]),("D",5,i.PRIORS[6])):
        for tag,sign,endpoint in (("LO",-1,prior[0]),("HI",1,prior[1])):
            v=list(unit(DIM,j,sign));v[6]=-sign*endpoint
            rows.append(row(name+"_"+tag,v,0))
    for name,key,constant,drift in (("R0","zero_pA",0,0),
                                    ("R1","span_pA",128,0),
                                    ("R2","late_zero_pA",0,2)):
        for tag,sign in (("LO",-1),("HI",1)):
            bound=refs[key]+sign*h.R
            rows.append(row(name+"_"+tag,(0,0,0,0,sign,sign*drift,-sign*bound),
                            -sign*constant))
    bad=[(name,lo,hi) for name,(lo,hi) in ranges if lo>hi]
    if bad:
        rows.extend(row(name+"_EMPTY",(0,)*DIM,hi-lo) for name,lo,hi in bad)
    else:
        gamma,delay,tau=(value for _,value in ranges)
        for t,y in zip(h.TIMES,observed,strict=True):
            base,coefs=i.coefficients(t,gamma,delay,tau,(F(0),h.J))
            rows.append(row(f"T{t}_LO",(*(-x[1] for x in coefs),-1,-F(t,120),y-h.E),base[1]))
            rows.append(row(f"T{t}_HI",(*(x[0] for x in coefs),1,F(t,120),-y-h.E),-base[0]))
    result=tuple(rows)
    system(result)
    return result


def reconstruct(record):
    """Independent raw lift (p=g*x,g,b,d), then divide by g>0."""
    _,ys,refs=h.parse(record)
    need(type(refs) is dict and set(refs)==set(h.REFS),"reference roster")
    raw=[]
    for j in range(4):
        v=[F(0)]*7;v[j]=F(-1)
        raw.append(row(f"X{j}_LO",v,0))
        v=[F(0)]*7;v[j]=F(1);v[4]=F(-1)
        raw.append(row(f"X{j}_HI",v,0))
    raw.extend((row("S_LO",(0,0,0,0,1,0,0),h.GAIN[1]),
                row("S_HI",(0,0,0,0,-1,0,0),-h.GAIN[0])))
    # Raw prior and reference strips. Division maps p/g to x,
    # the g coefficient to a constant, and the rhs to an s coefficient.
    for name,k,prior in (("B",5,i.PRIORS[5]),("D",6,i.PRIORS[6])):
        raw.extend((row(name+"_LO",unit(7,k,-1),-prior[0]),
                    row(name+"_HI",unit(7,k),prior[1])))
    for name,normal,key in (("R0",(0,0,0,0,0,1,0),"zero_pA"),
                            ("R1",(0,0,0,0,128,1,0),"span_pA"),
                            ("R2",(0,0,0,0,0,1,2),"late_zero_pA")):
        raw.extend((row(name+"_LO",tuple(-x for x in normal),-refs[key]+h.R),
                    row(name+"_HI",normal,refs[key]+h.R)))
    scalar=[]
    for name,key,prior in (("GAMMA","gamma",h.GAMMA),
                           ("DELAY","delay_ms",h.DELAY),
                           ("TAU","tau_ms",h.TAU)):
        lo=max(prior[0],refs[key]-h.R);hi=min(prior[1],refs[key]+h.R)
        scalar.append((name,lo,hi))
    impossible=[(name,lo,hi) for name,lo,hi in scalar if lo>hi]
    if impossible:
        raw.extend(row(name+"_EMPTY",(0,0,0,0,lo-hi,0,0),0)
                   for name,lo,hi in impossible)
    else:
        gamma,delay,tau=((lo,hi) for _,lo,hi in scalar)
        for t,y in zip(h.TIMES,ys,strict=True):
            b,columns=i.coefficients(t,gamma,delay,tau,(F(0),h.J))
            raw.append(row(f"T{t}_LO",(*(-cell[1] for cell in columns),-b[1],-1,-F(t,120)),
                           -y+h.E))
            raw.append(row(f"T{t}_HI",(*(cell[0] for cell in columns),b[0],1,F(t,120)),
                           y+h.E))
    normalized=[]
    for name,coef,rhs in raw:
        values=(*coef[:4],coef[5],coef[6],-rhs)
        bound=-coef[4]
        scale=abs(rhs) if name in ("S_LO","S_HI") else F(1)
        normalized.append(row(name,tuple(x/scale for x in values),bound/scale))
    result=tuple(normalized)
    system(result)
    return result


def checked_system(record):
    """Do not admit a relaxation when the two algebraic formulations disagree."""
    direct=compile(record)
    independent=reconstruct(record)
    need(direct==independent,"independent normalized row mismatch")
    return independent


def lift(world):
    need(type(world) is tuple and len(world)==10 and all(type(x) is F for x in world),
         "physical world roster")
    x=world[:4];g,b,d=world[4:7]
    need(g>0,"positive physical gain")
    return (*x,b/g,d/g,1/g)


def enclosure(rows, bound_proofs):
    need(type(bound_proofs) is list and len(bound_proofs)==4,"coordinate certificate roster")
    intervals=[]
    for k,pair in enumerate(bound_proofs):
        need(type(pair) is list and len(pair)==2,"coordinate pair roster")
        low,high=pair
        lo=F(0) if low is None else max(F(0),-check(rows,unit(DIM,k,-1),low))
        hi=F(1) if high is None else min(F(1),check(rows,unit(DIM,k),high))
        need(lo<=hi,"contradictory bounds require exclusion proof")
        intervals.append((lo,hi))
    return intervals


def receipt(record,profile,budget,rows,exclusion,bounds):
    need(type(profile) is str and profile in ("UNVERIFIED",h.BOUNDED),"reference profile")
    need(type(budget) is int and 0<=budget<=128,"proposal pivot budget")
    h.parse(record)
    if profile=="UNVERIFIED":
        need(rows is None and exclusion is None and bounds==[[None,None] for _ in range(4)],
             "unverified proof cannot constrain state")
        status=UNVERIFIED;intervals=[h.PRIOR]*4
    else:
        need(rows is not None,"missing reconstructed system")
        if budget==0:
            need(exclusion is None and bounds==[[None,None] for _ in range(4)],
                 "zero budget must not claim computed bounds")
        if exclusion is not None:
            need(bounds==[] and check_infeasible(rows,exclusion),"exclusion proof")
            status=EXCLUDED;intervals=None
        else:
            status=OUTER;intervals=enclosure(rows,bounds)
    return {"scope":SCOPE,"record_sha256":sha(canonical(record)),
            "system_sha256":None if rows is None else system_digest(rows),
            "profile":profile,"pivot_budget_per_solve":budget,"status":status,
            "coordinate_proofs":bounds,"exclusion":exclusion,
            "outer_bounds":None if intervals is None else [[encode(lo),encode(hi)] for lo,hi in intervals],
            "max_width":None if intervals is None else encode(max(hi-lo for lo,hi in intervals)),
            "joint_existence_established":False,**NEGATIVE}


def verify(record,proof,profile,budget):
    need(type(proof) is dict and set(proof)==set(NEGATIVE)|{
        "scope","record_sha256","system_sha256","profile","pivot_budget_per_solve","status",
        "coordinate_proofs","exclusion","outer_bounds","max_width","joint_existence_established"},
        "receipt schema")
    need(all(type(proof.get(k)) is type(value) and proof[k]==value
             for k,value in NEGATIVE.items()),"historical evidence changed")
    need(type(proof["pivot_budget_per_solve"]) is int and proof["pivot_budget_per_solve"]==budget,
         "budget identity")
    rows=None if profile=="UNVERIFIED" else checked_system(record)
    expected=receipt(record,profile,budget,rows,proof["exclusion"],proof["coordinate_proofs"])
    # Validate certificate payloads in receipt() before canonical comparison.
    need(canonical(proof)==canonical(expected),"receipt identity or disposition mismatch")
    return True
