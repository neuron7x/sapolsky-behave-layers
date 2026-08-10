# CSCA-04-SA — Pre-primary Amendment 002

Frozen calibration exposed no PRIMARY outcomes. The preregistered context rule says authority becomes context-conditional when a mechanism **changes sign or cause across context**. The implementation initially serialized only significant sign flips, which would fail to represent cause-switching cases such as `A -> 0` while `D: 0 -> positive` without a sign reversal.

Before PRIMARY, the implementation is aligned to the frozen rule:

- `context_shift_candidates`: any candidate whose intervention effect differs across contexts beyond the already frozen calibration `context_z_threshold`;
- `context_sign_flip_candidates`: narrower subset with sign reversal;
- global authority is forbidden when `context_shift_candidates` is non-empty for a structurally adequate case.

No IDR threshold, calibration seed, budget, primary strategy, or qualification threshold is changed.
