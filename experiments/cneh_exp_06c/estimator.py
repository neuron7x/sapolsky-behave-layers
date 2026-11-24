"""Sensor-only inverse enclosure; no truth-state or graph access."""
from __future__ import annotations

from fractions import Fraction as F
from experiments.cneh_exp_06c import algebra as a

FIELDS={"schema","voltage_mV","voltage_error_mV","current_error_pA","samples"}
SCHEMA="CNEH-IDEAL-CLAMP-V1"


def parse(record):
    a.need(type(record) is dict and set(record)==FIELDS and record["schema"]==SCHEMA,"sensor record schema")
    voltage=a.decode(record["voltage_mV"])
    ev=a.decode(record["voltage_error_mV"])
    ei=a.decode(record["current_error_pA"])
    a.need(0<=ev<=a.V_ERROR and 0<=ei<=a.MAX_ERROR,"error contract")
    rows=record["samples"]
    a.need(type(rows) is list and len(rows)==len(a.TIMES),"complete sample roster")
    y=[]
    for t,row in zip(a.TIMES,rows,strict=True):
        a.need(type(row) is dict and set(row)=={"t_ms","current_pA"}
               and type(row["t_ms"]) is int and row["t_ms"]==t,"sample chronology/schema")
        v=a.decode(row["current_pA"])
        a.need(abs(v)<=1000,"current envelope")
        y.append(v)
    return voltage,ev,ei,y


def intersect(a0,b):
    lo,hi=max(a0[0],b[0]),min(a0[1],b[1])
    return (lo,hi) if lo<=hi else None


def finish(status,bounds=None,voltage=None,heldout=None):
    return {"status":status,"normalized_bounds":None if bounds is None else [a.encode(x) for x in bounds],
            "voltage_bounds_mV":None if voltage is None else a.encode(voltage),
            "heldout_prediction_pA":None if heldout is None else a.encode(heldout),
            "scope":"CONDITIONAL_ENCLOSURE_NOT_PHYSICAL_CALIBRATION_OR_JOINT_FEASIBILITY",
            "source_action_authorized":False,"closed_loop_authorized":False,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}


def estimate(record):
    voltage,ev,eps,y=parse(record)
    vb=intersect((voltage-ev,voltage+ev),(F(-74),F(-68)))
    if vb is None:
        return finish("INCONSISTENT_VOLTAGE")
    rows,offsets,inv,*_=a.model()
    primary=a.PRIMARY
    # True H and b lie in the certified coefficient intervals, x in [0,1].
    residual=[y[i]-a.midpoint(offsets[i]) for i in primary]
    errors=[eps+a.radius(offsets[i])+sum(map(a.radius,rows[i])) for i in primary]
    bounds=[]
    for row in inv:
        center=sum((b*r for b,r in zip(row,residual,strict=True)),F(0))
        radius=sum((abs(b)*e for b,e in zip(row,errors,strict=True)),F(0))
        interval=intersect(a.outward((center-radius,center+radius),2**40),(F(0),F(1)))
        if interval is None:
            return finish("INCONSISTENT_PRIMARY")
        bounds.append(interval)
    i=a.TIMES.index(60)
    predicted=a.outward(a.add(offsets[i],a.isum(a.mul(h,x) for h,x in zip(rows[i],bounds,strict=True))),2**40)
    if intersect(predicted,(y[i]-eps,y[i]+eps)) is None:
        return finish("INCONSISTENT_HELDOUT")
    # Necessary held-out consistency does not prove there is a common x.
    narrow=all(hi-lo<=a.WIDTH for lo,hi in bounds)
    return finish("CONDITIONAL_NARROW_ENCLOSURE" if narrow else "UNRESOLVED_WIDTH",
                  bounds,a.outward(vb,2**40),predicted)


def graph_probe(record):
    """Hypothetical isolated event current-jump evidence, never live authority."""
    fields={"group","event_id","epoch","pre_pA","post_pA","error_pA","drift_pA",
            "isolated","clock_calibrated","fixed_mode"}
    a.need(type(record) is dict and set(record)==fields,"probe schema")
    group=record["group"]
    a.need(type(group) is int and group in (0,1),"source group")
    for k in ("event_id","epoch"):
        a.need(type(record[k]) is str and 0<len(record[k])<=64,"probe identity")
    for k in ("isolated","clock_calibrated","fixed_mode"):
        a.need(type(record[k]) is bool,"probe assumption type")
    before,after,err,drift=(a.decode(record[k]) for k in ("pre_pA","post_pA","error_pA","drift_pA"))
    a.need(abs(before)<=1000 and abs(after)<=1000 and 0<=err<=10 and 0<=drift<=10,"probe envelope")
    radius=2*err+drift
    center=after-before
    if not record["isolated"] or not record["clock_calibrated"]:
        support=(0,1)
    else:
        support=tuple(bit for bit in (0,1) if center-radius<=5*bit<=center+radius)
    return {"group":group,"event_id":record["event_id"],"epoch":record["epoch"],
            "fixed_mode_assumed":record["fixed_mode"],"event_edge_support":list(support),
            "status":"INCONSISTENT" if not support else "CONDITIONAL_EVENT_EDGE" if len(support)==1 else "AMBIGUOUS",
            "source_action_authorized":False,"scientific_promotion_authorized":False}


def graph_pair(records):
    a.need(type(records) is list and len(records)==2,"two group probes required")
    probes=[graph_probe(r) for r in records]
    a.need([p["group"] for p in probes]==[0,1] and probes[0]["event_id"]!=probes[1]["event_id"],"group/event roster")
    # The flags describe a synthetic hypothesis, not authenticated live dwell.
    same=probes[0]["epoch"]==probes[1]["epoch"] and all(p["fixed_mode_assumed"] for p in probes)
    modes=((1,0),(0,1),(1,1),(0,0))
    inconsistent=any(not p["event_edge_support"] for p in probes)
    historical=[] if inconsistent else [m for m,bits in enumerate(modes) if all(
        bits[i] in probes[i]["event_edge_support"] for i in (0,1))] if same else list(range(4))
    return {"hypothetical_fixed_epoch_mode_support":historical,
            "action_time_mode_support":[0,1,2,3],"guaranteed_common_source_groups":[],
            "status":"INCONSISTENT" if not historical else "CONDITIONAL_FIXED_EPOCH_ONLY" if len(historical)==1 else "ABSTAIN_UNIDENTIFIED",
            "source_action_authorized":False,"closed_loop_authorized":False,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
