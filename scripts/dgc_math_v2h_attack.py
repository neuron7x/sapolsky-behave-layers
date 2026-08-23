from __future__ import annotations

from cwc.governance.drift_sensitivity import certify_drift_detection_sensitivity


def must_raise(name,fn):
    try: fn()
    except ValueError: print(f"KILLED {name}"); return 1
    raise AssertionError(f"SURVIVED {name}")


def main():
    killed=0
    weak=certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.6,direction="UP",horizon=200,minimum_required_power=.8)
    if weak.deployment_guard_satisfied: raise AssertionError("SURVIVED UNDERPOWERED_DRIFT_GUARD")
    print("KILLED UNDERPOWERED_DRIFT_GUARD"); killed+=1
    killed+=must_raise("WRONG_SHIFT_DIRECTION",lambda:certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.5,tolerance=.05,alternative_mean=.4,direction="UP",horizon=200))
    killed+=must_raise("INVALID_TOLERANCE_BAND",lambda:certify_drift_detection_sensitivity(lower=0,upper=1,baseline_mean=.95,tolerance=.1,alternative_mean=.1,direction="DOWN",horizon=200))
    print(f"DGC-MATH-V2H-ATTACK: PASS ({killed}/3 killed)")
    return 0

if __name__=="__main__": raise SystemExit(main())
