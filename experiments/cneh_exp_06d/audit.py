"""Independently generated synthetic measurements and adversarial identifiability witnesses."""
from __future__ import annotations

import copy
from fractions import Fraction as F
import itertools

from experiments.cneh_exp_06c import algebra as a,estimator as e,fixtures as f
from experiments.cneh_exp_06d import robust as r

IDS=(0,3,6,9,12,15,16,31)
SIGN_PATTERNS=((-1,)*5,(1,)*5,(-1,1,-1,1,-1),(1,-1,1,-1,1))
MODELS=tuple(itertools.product(*(q for q in r.PARAMETERS)))+((F(3,2),F(1,2),F(110)),)
ERRORS=(F(1,1024),F(1,64))
PROFILE="BOUNDED_SYNTHETIC_HYPOTHESIS"


def prove_noise_alias():
    eps=F(1,64)
    d=(F(1963,262144),F(35679,1048576),F(256901,524288),F(755,16384))
    left=tuple(F(1,2)-q/2 for q in d)
    right=tuple(F(1,2)+q/2 for q in d)
    a.need(all(0<=x<=1 for x in left+right) and max(d)>a.WIDTH,"distinct in-domain states")
    samples=[];distance=[]
    for t in a.TIMES:
        p=a.current_interval(t,left)
        q=a.current_interval(t,right)
        y=f.quantize((min(p[0],q[0])+max(p[1],q[1]))/2)
        err=max(abs(y-z) for z in (*p,*q))
        a.need(err<=eps,"noise witness not certified")
        samples.append({"t_ms":t,"current_pA":a.q(y)})
        distance.append(a.q(a.outward((err,err),2**50)[1]))
    record={"schema":e.SCHEMA,"voltage_mV":"-71/1","voltage_error_mV":"0/1",
            "current_error_pA":a.q(eps),"samples":samples}
    nominal=e.estimate(record)
    a.need(f.contains(nominal,F(-71),left) and f.contains(nominal,F(-71),right)
           and nominal["status"]=="UNRESOLVED_WIDTH","nominal enclosure misses noise alias")
    robust=r.estimate(record,PROFILE)
    a.need(r.contains_joint(robust,(F(1),F(0),F(100)),left)
           and r.contains_joint(robust,(F(1),F(0),F(100)),right),"robust noise witness")
    return {"status":"FAIL_WIDTH_IDENTIFIABILITY_COUNTEREXAMPLE","error_radius_pA":a.q(eps),
            "left":[a.q(q) for q in left],"right":[a.q(q) for q in right],
            "max_normalized_state_separation":a.q(max(d)),
            "required_minimum_enclosure_width":a.q(max(d)),
            "requested_max_width":a.q(a.WIDTH),"certified_distances_to_shared_record_pA":distance,
            "shared_measurement":record,"nominal_estimate":nominal,"robust_estimate":robust}


def uncertain_current(t,x,params):
    gain,delay,tau=params
    return f.current(F(t)+delay,x,tau_n=tau,nmda_gain=gain)


def model_cover_check():
    boxes=r.cover()
    a.need(len(boxes)==8,"cover count")
    points=tuple(itertools.product(*( (lo,(lo+hi)/2,hi) for lo,hi in r.PARAMETERS )))
    for params in points:
        possible=[box for box in boxes if all(lo<=p<=hi for (lo,hi),p in zip(box,params,strict=True))]
        a.need(possible,"parameter cover gap")
        for box in possible:
            rows,b,*_=r.model_box(box)
            for i,t in enumerate(a.TIMES):
                zero=uncertain_current(t,(F(0),)*4,params)
                tol=F(1,10**80)
                a.need(b[i][0]-tol<=zero<=b[i][1]+tol,"offset model coverage")
                for j in range(4):
                    x=tuple(F(k==j) for k in range(4))
                    actual=uncertain_current(t,x,params)-zero
                    a.need(rows[i][j][0]-tol<=actual<=rows[i][j][1]+tol,"coefficient model coverage")
    # Cover of the continuum follows exactly from two closed intervals
    # sharing the midpoint on each coordinate, not the finite point checks.
    for dim,(lo,hi) in enumerate(r.PARAMETERS):
        intervals=sorted(set(box[dim] for box in boxes))
        a.need(len(intervals)==2 and intervals[0][0]==lo and intervals[0][1]==intervals[1][0] and intervals[1][1]==hi,"continuous cover")
    return {"boxes":8,"boundary_midpoint_model_points":len(points),"continuous_rectangular_cover":True}


def panel():
    rows=[]
    stats=[]
    for eps in ERRORS:
        count=narrow=0
        maxwidth=F(0);minwidth=F(1);minsurvive=8
        for index in IDS:
            v,x=f.truth(index)
            for model_id,params in enumerate(MODELS):
                ideal=tuple(uncertain_current(t,x,params) for t in a.TIMES)
                for signs in SIGN_PATTERNS:
                    rec=f.record(v,ideal,eps,signs)
                    _,_,_,samples=e.parse(rec)
                    a.need(all(abs(y-z)+F(1,10**80)<=eps for y,z in zip(samples,ideal,strict=True)),"synthetic noise bound")
                    out=r.estimate(rec,PROFILE)
                    a.need(r.contains(out,x) and r.contains_joint(out,params,x),"compatible joint truth excluded")
                    vb=tuple(map(a.decode,out["voltage_bounds_mV"]))
                    a.need(vb[0]<=v<=vb[1] and out["real_calibration_verified"] is False
                           and out["source_action_authorized"] is False and out["closed_loop_authorized"] is False,"voltage/authority binding")
                    width=max(a.decode(q[1])-a.decode(q[0]) for q in out["normalized_bounds"])
                    a.need(out["status"]==("CONDITIONAL_NARROW_ENCLOSURE" if width<=a.WIDTH else "ABSTAIN_MODEL_STATE_AMBIGUITY"),"width disposition")
                    count+=1;narrow+=int(width<=a.WIDTH)
                    maxwidth=max(maxwidth,width);minwidth=min(minwidth,width)
                    minsurvive=min(minsurvive,len(out["surviving_boxes"]))
                    rows.append({"truth_index":index,"model_id":model_id,"signs":list(signs),"measurement":rec,"result":out})
        stats.append({"error_pA":a.q(eps),"cases":count,"joint_truth_enclosed":count,"narrow":narrow,
                      "abstained":count-narrow,"max_normalized_width":a.q(maxwidth),
                      "min_max_normalized_width":a.q(minwidth),"min_surviving_boxes":minsurvive})
    a.need(len(rows)==576 and all(x["cases"]==x["joint_truth_enclosed"]==288 for x in stats),"complete uncertain-model panel")
    return rows,stats


def recover_aliases():
    aliases=f.aliases()
    x=(F(1,2),)*4
    pairs=(("unknown_nmda_gain",(F(2),F(0),F(100)),(x[0],x[1],x[2]/2,x[3])),
           ("unknown_clock_origin",(F(1),F(1),F(100)),x),
           ("altered_tau_nmda",(F(1),F(0),F(120)),x))
    reports=[]
    for name,params,truth in pairs:
        record=aliases[name]["measurement"]
        out=r.estimate(record,PROFILE)
        a.need(r.contains_joint(out,params,truth),"original C alias truth excluded by robust inverse")
        unknown=r.estimate(record)
        a.need(unknown["status"]=="CALIBRATION_UNVERIFIED"
               and unknown["normalized_bounds"]==[["0/1","1/1"]]*4
               and unknown["source_action_authorized"] is False,"unverified calibration narrowing")
        reports.append({"alias":name,"true_parameters":[a.q(q) for q in params],
                        "true_normalized_state":[a.q(q) for q in truth],
                        "nominal_status":aliases[name]["estimate"]["status"],"model_set_estimate":out,
                        "unverified_estimate":unknown})
    return reports


def negatives():
    v,x=f.truth(23)
    rec=f.record(v,tuple(f.current(t,x) for t in a.TIMES),F(1,1024),(1,)*5)
    results={}
    for label,change in (
        ("MISSING_SAMPLE",lambda d:d["samples"].pop()),
        ("EXTRA_TRUTH",lambda d:d.update(latent_state=[0,0,0,0])),
        ("FORGED_CALIBRATION",lambda d:d.update(real_calibration_verified=True)),
        ("FORGED_CONTROL",lambda d:d.update(closed_loop_authorized=True)),
        ("WRONG_SCHEMA",lambda d:d.update(schema="OTHER")),
    ):
        bad=copy.deepcopy(rec);change(bad)
        results[label]=f.reject(lambda:r.estimate(bad,PROFILE))
    results["UNSUPPORTED_PROFILE"]=f.reject(lambda:r.estimate(rec,"CALIBRATED"))
    bad=copy.deepcopy(rec);y=a.decode(bad["samples"][3]["current_pA"])
    bad["samples"][3]["current_pA"]=a.q(y+200)
    out=r.estimate(bad,PROFILE)
    a.need(out["status"]=="INCONSISTENT_DECLARED_MODEL_SET","impossible heldout accepted")
    results["GROSS_HELDOUT"]=out["status"]
    return results
