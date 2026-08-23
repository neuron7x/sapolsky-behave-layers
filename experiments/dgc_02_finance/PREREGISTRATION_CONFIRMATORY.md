# DGC-02 Financial Verification — Prospective Synthetic Confirmation

Status: `PREREGISTERED_BEFORE_EXECUTION / SYNTHETIC_ONLY`.

This protocol is frozen **after** the development analysis and therefore is a prospective confirmation of a development-informed financial target, not an independent discovery experiment. No parameter may be changed after commit and before execution.

## Frozen hypothesis

On untouched DGC-01 generator seeds, DGC will satisfy the economic viability threshold

`NetInferenceSavings >= 0.30` with `DeltaQuality >= 0`

relative to `B0_FIXED`, under the same frozen A-E workload family.

## Frozen execution

- `per_regime = 20_000`;
- regimes = `A,B,C,D,E` with equal target weights;
- `seed_offset = 200_000_000`;
- total paired tasks = `100_000`;
- reference = `B0_FIXED`;
- DGC = `B3_DGC`;
- target = `0.30`;
- synthetic governance-overhead stress = `0.0125` normalized cost units per task;
- no task, seed, regime or row may be dropped after observing results.

The overhead stress value is explicitly development-informed: it was part of the frozen development sweep and is near the largest tested value whose development lower bound cleared 30%. It is **not** a measurement of production governor cost.

## Primary decision rule

`SYNTHETIC_CONFIRMATORY_THRESHOLD_MET` iff all are true:

1. point `NetInferenceSavings >= 0.30`;
2. stratified fixed-n Hoeffding/Bonferroni `LCB(NetInferenceSavings) >= 0.30`;
3. exact or bounded `DeltaQuality >= 0`;
4. 100% task coverage retained;
5. result is consistent with the closed-form theorem in `docs/DGC_SYNTHETIC_FINANCIAL_THEOREM.md` within Monte-Carlo tolerance.

Otherwise the result is `SYNTHETIC_CONFIRMATORY_THRESHOLD_NOT_MET`; no endpoint replacement or seed substitution is allowed.

## Claim boundary

Even a PASS does **not** authorize “DGC guarantees 30% savings.” It establishes only that the frozen synthetic workload reproduces the threshold under a declared synthetic overhead allowance. `CLIENT_VERIFIED` still requires live provider/model traces with fully metered model, token, tool, retrieval, governor, monitor, retry, GPU and latency costs.
