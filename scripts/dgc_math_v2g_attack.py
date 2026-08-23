from __future__ import annotations

from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample
from cwc.governance.pareto import PairedBaselineEvidence, certify_multi_baseline_pareto_improvement
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy
from cwc.governance.sequential_risk_control import certify_anytime_adaptive_risk


def must_raise(name, fn):
    try: fn()
    except ValueError: print(f"KILLED {name}"); return 1
    raise AssertionError(f"SURVIVED {name}")


def ev(name, digest="tasks", coverage=1.0, quality=.2):
    return PairedBaselineEvidence(name,digest,coverage,(.4,)*100,(quality,)*100,(0.0,)*100,(.4,.4),(quality,quality),(0.0,0.0))


def main():
    killed=0
    killed += must_raise("SELECTIVE_COVERAGE",lambda:certify_multi_baseline_pareto_improvement([ev("a"),ev("b",coverage=.9)]))
    killed += must_raise("MISMATCHED_BENCHMARK_POPULATION",lambda:certify_multi_baseline_pareto_improvement([ev("a"),ev("b",digest="other")]))
    cert=certify_multi_baseline_pareto_improvement([ev("a"),ev("bad",quality=-.2)])
    if cert.all_baselines_certified: raise AssertionError("SURVIVED QUALITY_DEGRADED_BASELINE")
    print("KILLED QUALITY_DEGRADED_BASELINE"); killed+=1
    policy=certify_restricted_adaptive_policy(target_distribution={"a":.5,"b":.5},minimum_propensity=.5)
    samples=(AdaptiveImportanceSample("a",0.0,.5),AdaptiveImportanceSample("b",0.0,.5))
    killed += must_raise("OUTCOME_DEPENDENT_RISK_LAMBDA",lambda:certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="t",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,.5),predictable_lambda_attested=False))
    killed += must_raise("MISSING_RISK_TRACE",lambda:certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,.5),predictable_lambda_attested=True))
    print(f"DGC-MATH-V2G-ATTACK: PASS ({killed}/5 killed)")
    return 0

if __name__=="__main__": raise SystemExit(main())
