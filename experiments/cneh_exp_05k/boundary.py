"""Analytical reachability and scope-bound blind admission; no positive authority."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import itertools
import json
import re

EXPERIMENT = "CNEH-EXP-05K"
MODES = ((1,0),(0,1),(1,1),(0,0))
HORIZONS = (Fraction(64,5),Fraction(192,5),Fraction(256,5),Fraction(320))
PRE = ("DISCRETE_EQUATION_REPLAY","DETERMINISTIC_REPLAY","EVIDENCE_INTEGRITY",
       "CONTINUOUS_TIME_NUMERICAL","BIOPHYSICAL_VALIDITY","MULTISCALE_COHERENCE","STATISTICAL_DESIGN")
POST = ("STATISTICAL_GENERALIZATION","CLOSED_LOOP_CAUSAL_EFFICACY")
STATUSES = ("PASS","FAIL","UNKNOWN","NOT_TESTED","INVALID")
SUBJECT_FIELDS = {"backend_sha256","policy_sha256","protocol_sha256","evaluator_sha256",
                  "metrics_schema_sha256","cohort_commitment"}
RECEIPT_FIELDS = {"subject_sha256","gate","status","evidence_sha256","issuer"}
# Enrollment is a separately reviewed change, not data provided by the caller.
# No scientific or blind-cohort issuer has been authenticated for this lineage.
TRUSTED_RECEIPTS = ()


def need(c,msg):
    if not c:
        raise ValueError(msg)


def canonical(x):
    return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def sha(x):
    return hashlib.sha256(x).hexdigest()


def is_digest(x):
    return type(x) is str and re.fullmatch("[0-9a-f]{64}",x) is not None


def duration_interval():
    # 6 ln(3/2) = 12 atanh(1/5). Positive series, bounded tail.
    z=Fraction(1,5)
    n=40
    lo=12*sum((z**(2*k+1)/(2*k+1) for k in range(n)),Fraction(0))
    hi=lo+12*z**(2*n+1)/((2*n+1)*(1-z*z))
    return lo,hi


def upper_occupancy(T):
    need(type(T) is Fraction and T>0,"positive rational horizon required")
    lo,hi=duration_interval()
    # n visits, n-1 gaps; use conservative outward duration bounds.
    result=max(min(n*hi,T-(n-1)*lo) for n in range(1,int(T/lo)+2))
    # Independent closed-form packing envelope for durations <=hi, gaps >=lo.
    cycles=T//(hi+lo)
    envelope=cycles*hi+min(hi,T-cycles*(hi+lo))
    need(result==envelope and 0<result<=T,"packing envelope mismatch")
    return result


def fraction(x):
    return {"numerator":x.numerator,"denominator":x.denominator}


def reachability():
    lo,hi=duration_interval()
    reports=[]
    for T in HORIZONS:
        bound=upper_occupancy(T)
        reports.append({"horizon_ms":float(T),"upper_band_time":fraction(bound),
                        "upper_fraction":fraction(bound/T),"approx_upper_fraction":float(bound/T)})
    support_cases=0
    for mask in range(1,16):
        modes=[m for m in range(4) if mask&(1<<m)]
        common=[g for g in (0,1) if all(MODES[m][g] for m in modes)]
        expected=set.intersection(*(set(g for g in (0,1) if MODES[m][g]) for m in modes))
        need(set(common)==expected,"mode support intersection")
        support_cases+=1
    # Exact finite simplex fixture; general min(p0,p1)<=1/2 follows
    # from p0+p1<=1, including abstention.
    cases=0
    for a in range(101):
        for b in range(101-a):
            p0,p1=Fraction(a,100),Fraction(b,100)
            probabilities=[p0*m[0]+p1*m[1] for m in MODES]
            need(min(probabilities)==0 and min(probabilities[:3])==min(p0,p1)<=Fraction(1,2),
                 "randomized robust connectivity bound")
            cases+=1
    return {"dwell_lower_ms":fraction(lo),"dwell_upper_ms":fraction(hi),
            "asymptotic_upper_fraction":fraction(Fraction(1,2)),"finite_horizons":reports,
            "support_subsets":support_cases,"probability_simplex_cases":cases,
            "disconnected_source_to_GABA_control":"ZERO",
            "unrestricted_action_time_mode_support":[0,1,2,3],"guaranteed_common_source_groups":[],
            "connected_only_worst_case_single_group_probability_upper":fraction(Fraction(1,2)),
            "scope":"RELAXED_INSTANTANEOUS_SCALAR_CONDUCTANCE_NOT_NEURAL_ATTAINABILITY"}


def subject_digest(subject):
    need(type(subject) is dict and set(subject)==SUBJECT_FIELDS
         and all(is_digest(v) for v in subject.values()),"invalid exact subject")
    return sha(canonical(subject))


def commit_worlds(manifest,nonce):
    need(type(nonce) is str and re.fullmatch("[0-9a-f]{64}",nonce) is not None,"invalid 256-bit nonce encoding")
    need(type(manifest) is dict and set(manifest)=={"schema","worlds"} and manifest["schema"]=="CNEH-BLIND-WORLDS-V1",
         "manifest schema")
    worlds=manifest["worlds"]
    need(type(worlds) is list and bool(worlds),"empty world roster")
    ids=[]
    for w in worlds:
        need(type(w) is dict and set(w)=={"world_id","latent_manifest_sha256"} and
             type(w["world_id"]) is str and bool(w["world_id"]) and is_digest(w["latent_manifest_sha256"]),"world binding")
        ids.append(w["world_id"])
    need(ids==sorted(set(ids)),"duplicate or unordered worlds")
    return sha(b"CNEH-BLIND-COMMIT-V1\x00"+bytes.fromhex(nonce)+canonical(manifest))


def verify_reveal(subject,manifest,nonce):
    subject_digest(subject)
    need(commit_worlds(manifest,nonce)==subject["cohort_commitment"],"commitment mismatch")
    return {"commitment_equality":True,"independent_custody":"NOT_ESTABLISHED_BY_HASH"}


def conjunction(statuses):
    return len(statuses)==len(PRE) and all(x=="PASS" for x in statuses)


def _review(subject,receipts,anchors):
    # Pure contract semantics. Injected anchors in tests are synthetic, not
    # accepted by the production entry point.
    sid=subject_digest(subject)
    need(type(receipts) is list,"receipt roster")
    by={}
    for receipt in receipts:
        need(type(receipt) is dict and set(receipt)==RECEIPT_FIELDS,"receipt schema")
        gate=receipt["gate"]
        need(type(gate) is str and gate in PRE+POST and gate not in by,"unknown or duplicate gate")
        need(receipt["subject_sha256"]==sid and is_digest(receipt["evidence_sha256"]),"stale subject/evidence")
        need(type(receipt["issuer"]) is str and bool(receipt["issuer"]) and
             type(receipt["status"]) is str and receipt["status"] in STATUSES,"receipt issuer/status")
        by[gate]=receipt
    status={}
    for gate in PRE+POST:
        r=by.get(gate)
        if r is None:
            status[gate]="NOT_TESTED"
        elif (gate,r["issuer"],sha(canonical(r))) not in anchors:
            status[gate]="UNTRUSTED"
        else:
            status[gate]=r["status"]
    pre=conjunction(tuple(status[k] for k in PRE))
    # A result cannot grant admission retroactively; actual governance still
    # has to establish chronology and custody externally.
    post=pre and all(status[k]=="PASS" for k in POST)
    return {"subject_sha256":sid,"gate_status":status,
            "prerequisites_satisfied":pre,"all_scoped_receipts_satisfied":post,
            "first_blocking_gate":next((k for k in PRE+POST if status[k]!="PASS"),None)}


def admission(subject,receipts):
    try:
        review=_review(subject,receipts,TRUSTED_RECEIPTS)
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return {"blind_cohort_admission":"BLOCKED","scientific_promotion":"BLOCKED",
                "scientific_promotion_authorized":False,"reason":str(exc)}
    # No issuer and no live custody proof in this lineage. Never promote,
    # even if an external process later presents all necessary receipts.
    return {**review,"blind_cohort_admission":"BLOCKED",
            "scientific_promotion":"BLOCKED","scientific_promotion_authorized":False,
            "reason":"NO_AUTHENTICATED_BLIND_CUSTODIAN_OR_PROMOTION_ISSUER"}


def synthetic_contract_tests():
    manifest={"schema":"CNEH-BLIND-WORLDS-V1","worlds":[{"world_id":"fixture",
              "latent_manifest_sha256":"1"*64}]}
    nonce="a"*64
    subject={k:"2"*64 for k in SUBJECT_FIELDS}
    subject["cohort_commitment"]=commit_worlds(manifest,nonce)
    need(verify_reveal(subject,manifest,nonce)["commitment_equality"],"commitment fixture")
    sid=subject_digest(subject)
    rs=[{"subject_sha256":sid,"gate":gate,"status":"PASS","evidence_sha256":"3"*64,
         "issuer":"synthetic-fixture-only"} for gate in PRE+POST]
    anchors=tuple((r["gate"],r["issuer"],sha(canonical(r))) for r in rs)
    need(_review(subject,rs,anchors)["all_scoped_receipts_satisfied"],"synthetic conjunction")
    need(admission(subject,rs)["blind_cohort_admission"]=="BLOCKED","synthetic trust leaked")
    cases=0
    for statuses in itertools.product(STATUSES,repeat=len(PRE)):
        need(conjunction(statuses)==(set(statuses)=={"PASS"}),"status lattice disagreement")
        cases+=1
    attacks={}
    def denied(label,bad,anchor=anchors):
        try:
            result=_review(subject,bad,anchor)
            ok=not result["prerequisites_satisfied"]
        except (ValueError,TypeError,KeyError,OverflowError):
            ok=True
        need(ok,"premature admission: "+label)
        attacks[label]=True
    denied("missing",rs[1:])
    denied("duplicate",rs+[rs[0]])
    denied("unknown_gate",rs+[{**rs[0],"gate":"UNKNOWN"}])
    denied("stale_subject",[{**rs[0],"subject_sha256":"4"*64}]+rs[1:])
    denied("bad_digest",[{**rs[0],"evidence_sha256":"bad"}]+rs[1:])
    denied("wrong_issuer",[{**rs[0],"issuer":"other"}]+rs[1:])
    denied("locally_rehashed",[{**rs[0],"evidence_sha256":"4"*64}]+rs[1:])
    denied("unknown_status",[{**rs[0],"status":"GREEN"}]+rs[1:])
    denied("no_trust_root",rs,())
    denied("downstream_only",rs[len(PRE):])
    for status in STATUSES[1:]:
        changed={**rs[0],"status":status}
        auth=((changed["gate"],changed["issuer"],sha(canonical(changed))),)+anchors[1:]
        denied("authenticated_"+status,[changed]+rs[1:],auth)
    for label,m,n in (("wrong_nonce",manifest,"b"*64),("short_nonce",manifest,"a"*32),
                      ("changed_world",{"schema":manifest["schema"],"worlds":[{"world_id":"other","latent_manifest_sha256":"1"*64}]},nonce)):
        try:
            verify_reveal(subject,m,n)
        except ValueError:
            attacks[label]=True
        else:
            raise ValueError("invalid reveal accepted")
    return {"status_assignments":cases,"attacks_rejected":attacks,
            "synthetic_all_pass_production_admission":admission(subject,rs)["blind_cohort_admission"]}


def report():
    return {"experiment":EXPERIMENT,"scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "blind_cohort_admission":"BLOCKED","historical_native_replay":"FAIL_PRESERVED",
            "reachability":reachability(),"contract_tests":synthetic_contract_tests(),
            "real_trust_roots":len(TRUSTED_RECEIPTS),"scope":"ANALYTICAL_AND_SYNTHETIC_CONTRACT_ONLY"}
