"""Independent high-precision synthetic electrode generator and fixed panel."""
from __future__ import annotations

import copy
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import hashlib
import itertools

from experiments.cneh_exp_06c import algebra as a,estimator as e

ERRORS=(F(1,1024),F(1,64),F(1,4))
SIGNS=tuple(itertools.product((-1,1),repeat=5))
GRID=2**30


def decimal(x):
    q=F(x)
    return D(q.numerator)/D(q.denominator)


def current(t,x,tau_n=F(100),nmda_gain=F(1)):
    """Independent direct KCL implementation, not inverse matrix code."""
    with localcontext() as c:
        c.prec=90
        t=decimal(t)
        w,ga,gn,gg=(decimal(v)*s for v,s in zip(x,(D(24),D(".1"),D(".1"),D(".5")),strict=True))
        adapt=D(20)+(w-D(20))*(-t/D(200)).exp()
        ampa=ga*(-t/D("2.5")).exp()
        nmda=gn*(-t/decimal(tau_n)).exp()
        gaba=gg*(-t/D(6)).exp()
        block=1/(1+D("3.72").exp()/D("3.57"))
        value=D(100)-D(20)*D("-2.5").exp()+adapt-D(60)*ampa-D(60)*block*decimal(nmda_gain)*nmda+D(10)*gaba
        return F(value)


def quantize(x):
    return F(round(x*GRID),GRID)


def truth(index):
    a.need(type(index) is int and 0<=index<32,"truth index")
    if index<16:
        x=tuple(F((index>>i)&1) for i in range(4))
    else:
        x=tuple(F(1+int.from_bytes(hashlib.sha256(f"CNEH-06C-V1:{index}:{i}".encode()).digest()[:4],"big")%255,256) for i in range(4))
    v=F(-74)+F(index%17,16)*6
    return v,x


def record(voltage,ideal,eps,signs):
    a.need(len(ideal)==len(signs)==5,"sensor fixture roster")
    return {"schema":e.SCHEMA,"voltage_mV":a.q(voltage+F(signs[0],128)),
            "voltage_error_mV":a.q(a.V_ERROR),"current_error_pA":a.q(eps),
            "samples":[{"t_ms":t,"current_pA":a.q(quantize(y+F(3*s,4)*eps))}
                       for t,y,s in zip(a.TIMES,ideal,signs,strict=True)]}


def contains(result,v,x):
    if result["normalized_bounds"] is None:
        return False
    vb=tuple(map(a.decode,result["voltage_bounds_mV"]))
    return vb[0]<=v<=vb[1] and all(lo<=value<=hi for value,(lo,hi) in zip(x,(
        tuple(map(a.decode,b)) for b in result["normalized_bounds"]),strict=True))


def independent_coefficients():
    rows,offsets,*_=a.model()
    checked=0
    for i,t in enumerate(a.TIMES):
        zero=current(t,(F(0),)*4)
        a.need(offsets[i][0]<=zero<=offsets[i][1],"independent offset disagreement")
        checked+=1
        # Compare independent unit-current differences with the
        # original coefficient enclosure, allowing only the explicit
        # Decimal rounding uncertainty (<10^-80 pA).
        for j in range(4):
            x=tuple(F(k==j) for k in range(4))
            v=current(t,x)-zero
            lo,hi=rows[i][j]
            tolerance=F(1,10**80)
            a.need(lo-tolerance<=v<=hi+tolerance,"independent coefficient disagreement")
            checked+=1
    return checked


def nominal():
    records=[]
    reports=[]
    for eps in ERRORS:
        stats={"error_pA":a.q(eps),"cases":0,"truth_enclosed":0,"narrow":0,"unresolved":0,"max_normalized_width":F(0)}
        for index in range(32):
            v,x=truth(index)
            ideal=tuple(current(t,x) for t in a.TIMES)
            for t,y in zip(a.TIMES,ideal,strict=True):
                lo,hi=a.current_interval(t,x)
                a.need(lo-F(1,10**80)<=y<=hi+F(1,10**80),"independent nominal physical current")
            for signs in SIGNS:
                m=record(v,ideal,eps,signs)
                _,_,_,observed=e.parse(m)
                # Every fixture is verified to obey the mathematical error
                # model, even at both interval endpoints of the true current.
                for t,y in zip(a.TIMES,observed,strict=True):
                    lo,hi=a.current_interval(t,x)
                    a.need(max(abs(y-lo),abs(y-hi))<=eps,"measurement outside declared uncertainty")
                result=e.estimate(m)
                a.need(contains(result,v,x),"compatible truth excluded")
                a.need(result["source_action_authorized"] is False and result["closed_loop_authorized"] is False,"inverse authority leak")
                widths=[a.decode(b[1])-a.decode(b[0]) for b in result["normalized_bounds"]]
                narrow=max(widths)<=a.WIDTH
                a.need(result["status"]==("CONDITIONAL_NARROW_ENCLOSURE" if narrow else "UNRESOLVED_WIDTH"),"width disposition")
                stats["cases"]+=1;stats["truth_enclosed"]+=1
                stats["narrow"]+=int(narrow);stats["unresolved"]+=int(not narrow)
                stats["max_normalized_width"]=max(stats["max_normalized_width"],max(widths))
                records.append({"truth_index":index,"signs":list(signs),"measurement":m,"result":result})
        stats["max_normalized_width"]=a.q(stats["max_normalized_width"])
        reports.append(stats)
    a.need(len(records)==3072 and all(x["cases"]==x["truth_enclosed"]==1024 for x in reports),"nominal complete roster")
    return records,reports


def reject(fn):
    try:
        fn()
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return str(exc)
    raise ValueError("negative control escaped")


def negative_controls():
    v,x=truth(23)
    good=record(v,tuple(current(t,x) for t in a.TIMES),ERRORS[0],(1,)*5)
    checks={}
    def attack(label,change):
        bad=copy.deepcopy(good)
        change(bad)
        checks[label]=reject(lambda:e.estimate(bad))
    attack("MISSING",lambda m:m["samples"].pop())
    attack("DUPLICATE",lambda m:m["samples"].__setitem__(1,copy.deepcopy(m["samples"][0])))
    attack("REORDERED",lambda m:m["samples"].reverse())
    attack("STALE_TIMESTAMP",lambda m:m["samples"][2].update(t_ms=17))
    attack("BOOLEAN_TIMESTAMP",lambda m:m["samples"][0].update(t_ms=False))
    attack("FLOAT_TIMESTAMP",lambda m:m["samples"][0].update(t_ms=0.))
    attack("HIDDEN_STATE",lambda m:m.update(w0=a.q(F(12))))
    attack("BAD_ENCODING",lambda m:m["samples"][0].update(current_pA="100.0"))
    attack("NONCANONICAL_RATIONAL",lambda m:m["samples"][0].update(current_pA="2/2"))
    attack("NEGATIVE_ERROR",lambda m:m.update(current_error_pA="-1/1"))
    attack("EXCESS_ERROR",lambda m:m.update(current_error_pA="1/1"))
    attack("INJECTED_AUTHORITY",lambda m:m.update(closed_loop_authorized=True))
    bad=copy.deepcopy(good);bad["voltage_mV"]="-50/1"
    a.need(e.estimate(bad)["status"]=="INCONSISTENT_VOLTAGE","impossible voltage admitted")
    checks["IMPOSSIBLE_VOLTAGE"]="INCONSISTENT_VOLTAGE"
    bad=copy.deepcopy(good);y=a.decode(bad["samples"][3]["current_pA"])
    bad["samples"][3]["current_pA"]=a.q(y+40)
    a.need(e.estimate(bad)["status"]=="INCONSISTENT_HELDOUT","heldout corruption admitted")
    checks["CORRUPTED_HELDOUT"]="INCONSISTENT_HELDOUT"
    a.need(len(checks)==14,"negative control roster")
    return checks


def aliases():
    v=F(-71)
    x=(F(1,2),)*4
    eps=ERRORS[0]
    signs=(1,-1,1,-1,1)
    nominal_current=tuple(current(t,x) for t in a.TIMES)
    nominal_record=record(v,nominal_current,eps,signs)
    doubled=(x[0],x[1],x[2]/2,x[3])
    alias_current=tuple(current(t,doubled,nmda_gain=F(2)) for t in a.TIMES)
    a.need(max(abs(a-b) for a,b in zip(nominal_current,alias_current,strict=True))<=F(1,10**80),"NMDA gain alias")
    gain_record=record(v,alias_current,eps,signs)
    a.need(gain_record==nominal_record,"gain alias record")
    gain_est=e.estimate(gain_record)
    a.need(contains(gain_est,v,x) and not contains(gain_est,v,doubled),"parameter alias not exposed")
    with localcontext() as c:
        c.prec=90
        shifted=(F((D(20)+(decimal(x[0])*24-D(20))*(-D(1)/200).exp())/24),
                 *(F(decimal(y)*(-D(1)/decimal(tau)).exp()) for y,tau in zip(x[1:],(F(5,2),F(100),F(6)),strict=True)))
    delayed_current=tuple(current(t+1,x) for t in a.TIMES)
    shifted_current=tuple(current(t,shifted) for t in a.TIMES)
    a.need(max(abs(a-b) for a,b in zip(delayed_current,shifted_current,strict=True))<=F(1,10**80),"unknown time origin alias")
    delay_record=record(v,delayed_current,eps,signs)
    a.need(delay_record==record(v,shifted_current,eps,signs),"delay alias record")
    delay_est=e.estimate(delay_record)
    a.need(contains(delay_est,v,shifted) and not contains(delay_est,v,x),"timing alias not exposed")
    changed=record(v,tuple(current(t,x,tau_n=F(120)) for t in a.TIMES),eps,signs)
    changed_est=e.estimate(changed)
    return {"unknown_nmda_gain":{"status":"EXACT_STRUCTURAL_ALIAS_CONDITIONAL_MODEL",
                                "nominal_normalized_state":[a.q(q) for q in x],
                                "alternate_normalized_state":[a.q(q) for q in doubled],
                                "same_quantized_record":True,"alternate_truth_excluded_by_nominal_inverse":True,
                                "measurement":gain_record,"estimate":gain_est},
            "unknown_clock_origin":{"status":"EXACT_STRUCTURAL_ALIAS_CONDITIONAL_MODEL",
                                    "delay_ms":1,"same_quantized_record":True,
                                    "nominal_origin_truth_excluded":True,
                                    "measurement":delay_record,"estimate":delay_est},
            "altered_tau_nmda":{"tau_ms":120,"measurement":changed,"estimate":changed_est,
                               "original_truth_enclosed":contains(changed_est,v,x)},
            "ood_model_qualification":"FAIL_COUNTEREXAMPLE"}


def probe(group,bit,err,s1,s2,epoch="fixture",fixed=True):
    before=F(100)+F(3*s1,4)*err
    after=F(100+5*bit)+F(3*s2,4)*err
    return {"group":group,"event_id":f"{epoch}:{group}","epoch":epoch,
            "pre_pA":a.q(before),"post_pA":a.q(after),"error_pA":a.q(err),"drift_pA":"1/10",
            "isolated":True,"clock_calibrated":True,"fixed_mode":fixed}


def graph_panel():
    modes=((1,0),(0,1),(1,1),(0,0))
    signs=tuple(itertools.product((-1,1),repeat=4))
    rows=[]
    stats=[]
    for err in (F(1,4),F(3)):
        narrow=0
        for m,bits in enumerate(modes):
            for s in signs:
                records=[probe(i,bits[i],err,*s[2*i:2*i+2]) for i in (0,1)]
                result=e.graph_pair(records)
                a.need(m in result["hypothetical_fixed_epoch_mode_support"],"true graph excluded")
                a.need(result["action_time_mode_support"]==[0,1,2,3] and not result["source_action_authorized"],"action-time authority leak")
                if len(result["hypothetical_fixed_epoch_mode_support"])==1:
                    narrow+=1
                rows.append({"mode":m,"signs":list(s),"records":records,"result":result})
        stats.append({"error_pA":a.q(err),"cases":64,"fixed_epoch_singletons":narrow,"action_time_singletons":0})
    a.need(stats[0]["fixed_epoch_singletons"]==64,"low-noise conditional graph separation")
    ambiguous=probe(0,0,F(3),1,1)
    ambiguous["pre_pA"]="100/1";ambiguous["post_pA"]="205/2"
    a.need(e.graph_probe(ambiguous)["event_edge_support"]==[0,1],"overlap witness")
    low=[probe(0,1,F(1,4),1,1),probe(1,0,F(1,4),1,1)]
    attacks={}
    for field in ("isolated","clock_calibrated"):
        changed=copy.deepcopy(low);changed[0][field]=False
        result=e.graph_pair(changed)
        a.need(len(result["hypothetical_fixed_epoch_mode_support"])>=2,"untrusted single probe narrowed")
        attacks[field]=result
    for field in ("fixed_mode","epoch"):
        changed=copy.deepcopy(low)
        changed[0][field]=False if field=="fixed_mode" else "other"
        result=e.graph_pair(changed)
        a.need(result["hypothetical_fixed_epoch_mode_support"]==[0,1,2,3],"untrusted dwell narrowed")
        attacks[field]=result
    changed=copy.deepcopy(low);changed[1]["event_id"]=changed[0]["event_id"]
    attacks["duplicate_event"]=reject(lambda:e.graph_pair(changed))
    return rows,{"profiles":stats,"ambiguous_jump_support":[0,1],"assumption_attacks":attacks,
                 "future_action_time_support":[0,1,2,3],"scientific_promotion_authorized":False}
