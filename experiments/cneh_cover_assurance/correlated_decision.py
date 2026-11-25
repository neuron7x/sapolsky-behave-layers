"""Exact joint electronic support and conditional decision certificates.

Additive consumer of immutable COVER-01 and I proofs. No operational authority.
"""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, product

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as old
from experiments.cneh_cover_assurance import cover as c, verifier as v

SCOPE = "JOINT_ELECTRONIC_SUPPORT_AND_CONDITIONAL_AFFINE_REGRET"
GA, BA, DA = h.GAIN, old.PRIORS[5], old.PRIORS[6]
NEGATIVE = dict(c.NEGATIVE)


def electronics(refs):
    return tuple(refs[key] for key in ("zero_pA", "span_pA", "late_zero_pA"))


def offset_range(codes):
    r0, r1, r2 = codes
    return (max(BA[0], r0-h.R, r1-h.R-128*GA[1], r2-h.R-2*DA[1]),
            min(BA[1], r0+h.R, r1+h.R-128*GA[0], r2+h.R-2*DA[0]))


def support(codes, current, t):
    """Exact extrema for the product of intrinsic-current interval and joint electronics."""
    a.need(type(t) is int and t in h.TIMES and current[0] <= current[1], "support domain")
    lo, hi = offset_range(codes)
    if lo > hi:
        return None
    _, r1, r2 = codes
    switches = {lo, hi}
    switches.update(r1+sign*h.R-128*g for sign, g in product((-1,1), GA))
    switches.update(r2+sign*h.R-2*d for sign, d in product((-1,1), DA))
    values = []
    for b in sorted(x for x in switches if lo <= x <= hi):
        g = (max(GA[0], (r1-h.R-b)/128), min(GA[1], (r1+h.R-b)/128))
        d = (max(DA[0], (r2-h.R-b)/2), min(DA[1], (r2+h.R-b)/2))
        a.need(g[0] <= g[1] and d[0] <= d[1], "projected joint strips")
        values.extend(gain*I+b+drift*F(t,120)
                      for gain, I, drift in product(g,current,d))
    return min(values), max(values)


def dot(x, y):
    return sum((u*w for u,w in zip(x,y,strict=True)), F(0))


def det(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
            -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
            +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))


def planes(codes):
    """Independent half-space form, coordinates (g,b,d)."""
    r0,r1,r2 = codes
    strips = (((1,0,0), GA), ((0,1,0), BA), ((0,0,1), DA),
              ((0,1,0), (r0-h.R,r0+h.R)),
              ((128,1,0), (r1-h.R,r1+h.R)),
              ((0,1,2), (r2-h.R,r2+h.R)))
    return tuple((tuple(F(sign*x) for x in normal), F(bound))
                 for normal,(lo,hi) in strips for sign,bound in ((1,hi),(-1,-lo)))


@lru_cache(maxsize=128)
def vertices(codes):
    """Exhaustive exact vertex enumeration; independent of offset elimination."""
    constraints = planes(codes)
    points = set()
    for active in combinations(constraints,3):
        matrix = tuple(row for row,_ in active)
        rhs = tuple(value for _,value in active)
        denominator = det(matrix)
        if denominator == 0:
            continue
        point = tuple(det(tuple(tuple(rhs[i] if j==k else matrix[i][j]
                                      for j in range(3)) for i in range(3)))/denominator
                      for k in range(3))
        if all(dot(normal,point) <= bound for normal,bound in constraints):
            points.add(point)
    return tuple(sorted(points))


def vertex_support(codes, current, t):
    a.need(type(t) is int and t in h.TIMES and current[0] <= current[1], "support domain")
    values = [g*I+b+d*F(t,120) for (g,b,d),I in product(vertices(codes),current)]
    return (min(values),max(values)) if values else None


def cartesian(codes, current, t):
    lo, hi = offset_range(codes)
    if lo > hi:
        return None
    _,r1,r2 = codes
    gain = max(GA[0],(r1-h.R-hi)/128),min(GA[1],(r1+h.R-lo)/128)
    drift = max(DA[0],(r2-h.R-hi)/2),min(DA[1],(r2+h.R-lo)/2)
    return a.add(a.add(a.mul(gain,current),(lo,hi)),a.mul(drift,a.point(F(t,120))))


def decode_box(wire, size):
    a.need(type(wire) is list and len(wire)==size, "box roster")
    result=[]
    for item in wire:
        a.need(type(item) is list and len(item)==2, "interval roster")
        lo,hi=map(a.decode,item)
        a.need(lo<=hi,"reversed interval")
        result.append((lo,hi))
    return tuple(result)


def intrinsic(t, root, physical):
    _,_,_,gamma,delay,tau=root[4:]
    base,coef=old.coefficients(t,gamma,delay,tau,(F(0),h.J))
    return a.add(base,a.isum(a.mul(z,x) for z,x in zip(coef,physical,strict=True)))


def correlated(record, proof, profile, budget, oracle=support):
    a.need(v.verify(record,proof,profile,budget) is True,"parent cover verification")
    _,observed,refs=h.parse(record)
    frontier=[]; exclusions=[]
    if profile=="UNVERIFIED":
        frontier=proof["frontier"]
    elif proof["status"]!=c.EXCLUDED:
        root=decode_box(proof["root"],10)
        codes=electronics(refs)
        for index,wire in enumerate(proof["frontier"]):
            box=decode_box(wire,4)
            for t,y in zip(h.TIMES,observed,strict=True):
                interval=oracle(codes,intrinsic(t,root,box),t)
                a.need(interval is not None,"nonempty joint reference root")
                target=y-h.E,y+h.E
                if interval[1]<target[0] or target[1]<interval[0]:
                    exclusions.append({"leaf":index,"time_ms":t,
                                       "prediction":a.encode(interval),"target":a.encode(target)})
                    break
            else:
                frontier.append(wire)
    hull=c.hull(tuple(decode_box(box,4) for box in frontier))
    return {"scope":SCOPE,"profile":profile,"node_budget":budget,
            "record_sha256":sha(canonical(record)),"parent_cover_sha256":sha(canonical(proof)),
            "status":c.UNCALIBRATED if profile=="UNVERIFIED" else c.OUTER if frontier else c.EXCLUDED,
            "root":proof["root"],"frontier":frontier,"exclusions":exclusions,
            "physical_hull":None if hull is None else c.box_wire(hull),
            "max_width":None if hull is None else a.q(max(hi-lo for lo,hi in hull)),
            "joint_existence_established":False,**NEGATIVE}


def verify_cover(record,parent,proof,profile,budget):
    v.bounded(proof)
    expected=correlated(record,parent,profile,budget,vertex_support)
    a.need(canonical(proof)==canonical(expected),"correlated cover proof mismatch")
    return True


def contains(box, point):
    return len(box)==len(point) and all(lo<=x<=hi for (lo,hi),x in zip(box,point,strict=True))


def witness(record, proof, profile, outer):
    if proof is None:
        return None
    a.need(profile==h.BOUNDED and type(proof) is dict and proof.get("status")==old.WITNESS,
           "witness scope")
    v.bounded(proof)
    a.need(old.verify(record,proof,profile) is True,"I witness verification")
    cert=proof["certificate"]["witness"]
    world=tuple(a.decode(x) for x in cert["world"])
    _,observed,refs=h.parse(record)
    computed=old.witness_for(world,observed,refs)
    a.need(computed is not None and canonical(cert)==canonical(computed),"type-exact witness")
    a.need(outer["root"] is not None and contains(decode_box(outer["root"],10),world) and
           any(contains(decode_box(box,4),world[:4]) for box in outer["frontier"]),
           "valid witness outside verified outer cover")
    return world[:4]


def loss_contract(losses,epsilon):
    a.need(type(losses) is list and 2<=len(losses)<=4,"action roster")
    rows=[]
    for row in losses:
        a.need(type(row) is list and len(row)==5,"affine loss roster")
        values=tuple(a.decode(x) for x in row)
        a.need(all(abs(x)<=16 for x in values),"loss coefficient bound")
        rows.append(values)
    eps=a.decode(epsilon)
    a.need(eps>=0,"epsilon domain")
    return tuple(rows),eps


def differences(losses,k):
    return tuple(tuple(x-y for x,y in zip(losses[k],b,strict=True)) for b in losses)


def affine_max(row,box):
    return row[0]+sum((max(coef*lo,coef*hi) for coef,(lo,hi) in
                       zip(row[1:],box,strict=True)),F(0))


def corner_max(row,box):
    return max(dot(row,(F(1),*point)) for point in product(*box))


def decide(record,parent,outer,witness_proof,losses,epsilon,profile,budget,*,independent=False):
    a.need(verify_cover(record,parent,outer,profile,budget),"verified correlated cover")
    rows,eps=loss_contract(losses,epsilon)
    inner=witness(record,witness_proof,profile,outer)
    boxes=tuple(decode_box(box,4) for box in outer["frontier"])
    upper=corner_max if independent else affine_max
    bounds=[]
    for k in range(len(rows)):
        diff=differences(rows,k)
        lo=None if inner is None else max(dot(d,(F(1),*inner)) for d in diff)
        hi=None if not boxes else max(upper(d,box) for d,box in product(diff,boxes))
        a.need(lo is None or hi is not None and 0<=lo<=hi,"regret sandwich")
        bounds.append((lo,hi))
    certified=[k for k,(lo,hi) in enumerate(bounds)
               if inner is not None and hi is not None and hi<=eps]
    excluded=[k for k,(lo,_) in enumerate(bounds) if lo is not None and lo>eps]
    if outer["status"]==c.EXCLUDED:
        status="CONTRADICTION"
    elif certified:
        status="CERTIFIED_CONDITIONAL"
    elif len(excluded)==len(rows):
        status="NO_EPSILON_ACTION"
    else:
        status="UNKNOWN"
    return {"scope":SCOPE,"record_sha256":sha(canonical(record)),
            "parent_cover_sha256":sha(canonical(parent)),"outer_sha256":sha(canonical(outer)),
            "witness_sha256":None if witness_proof is None else sha(canonical(witness_proof)),
            "losses":losses,"epsilon":epsilon,"profile":profile,"node_budget":budget,
            "bounds":[[None if x is None else a.q(x) for x in pair] for pair in bounds],
            "status":status,"certified_actions":certified,"excluded_actions":excluded,
            "conditional_joint_witness_verified":inner is not None,**NEGATIVE}


def verify_decision(record,parent,outer,witness_proof,losses,epsilon,profile,budget,receipt):
    v.bounded(receipt)
    expected=decide(record,parent,outer,witness_proof,losses,epsilon,profile,budget,independent=True)
    a.need(canonical(receipt)==canonical(expected),"decision certificate mismatch")
    return True
