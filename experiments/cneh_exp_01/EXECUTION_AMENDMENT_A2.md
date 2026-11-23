# Engineering execution amendment A2

Date: 2026-11-23. Parent delivery: `a65ab49681bc748acb71cde9abe5bc99a4045ab3`.
Authority: engineering qualification only; no change to frozen science or PRIMARY.

This amendment implements the owner's execution directive using existing code.
The original four frozen files and all A1/raw negative artifacts remain unchanged.
New numerical qualification is prospective with respect to these new probes, not
prospective scientific validation: original outcomes and the reference implementations
have already been inspected. No threshold or comparator is rescued retrospectively.

## Reuse and scope

PR44 remains separate and draft. Read-only review pinned its actual code at
`d0eada284220c4dad759191f5a847139a2dcb999`. The math qualification bridge reuses its
`experiments/cneh_exp_02/linear_reference.py` and existing CWC causal modules through
source-authenticated boundaries; it does not duplicate the experimental adapter,
modify PR44, merge it, or move its base. Raw reference NaN/Inf acceptance and CWC
estimator precondition gaps are preserved as counterexamples, with strict guards in
the qualification boundary. An absent or altered pinned source fails admission.

`math_qualification_contract.json` freezes the analytic fixtures, exact finite causal
countermodels, covariance/coordinate transformations, numerical tolerances and scope
exclusions. Independent block/SVD/linear-solve oracles run in the existing hash-locked
optional numerical environment. No neural causal efficacy, finite-sample confidence,
global parameter identifiability or PID-mediated cognition follows from these checks.

`metrology_contract.json` freezes bounded local hardware measurement and engineering
ceilings before execution. It reuses the timing harness and isolates process peak
RSS, profiling and serialization fixtures. Real wall/CPU/RSS/bytes are named by their
actual measurement boundary. Synthetic policies still have no distributed transport;
serialization fixtures do not prove end-to-end communication parity. Missing physical
FLOP and calibrated energy instruments remain INSTRUMENT_INVALID. Ceiling compliance
never becomes paired resource equivalence.

## Repository-level closure

The A1 source and artifact commits reached GitHub. Hosted CNEH Python3.11/3.12 and
actual pinned BN-Syn jobs passed; repository admission did not pass. The failures are
retained: generated ledger missing an evidence row, CodeQL default file mode0644 and
an unexplained timeout race handler, and a secret-scanner false positive on the SHA256
of pinned `src/bnsyn/api.py`. Fixes preserve the gates. The scanner adjudication is
limited to the exact historical finding; an equivalent future finding must still fail.

No active Git hooks or configured hooksPath were found in this checkout. A reported
hook exit5 has no matching observed tool failure in the inspected active-session
records: status NOT_REPRODUCED, with no bypass. Distinguish that unknown report from
the observed OAuth workflow-scope push rejection and the reproduced hosted failures.

Final evidence must reconcile raw outputs, immutable source/dependency/configuration
digests, each frozen attack and full current-head hosted CI. The file-level evidence
map and separate scientific/engineering dispositions are required outputs. External
independent blind execution remains REPLICATION_NOT_TESTED.
