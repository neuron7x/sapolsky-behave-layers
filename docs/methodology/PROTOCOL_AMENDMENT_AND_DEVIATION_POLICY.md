# Protocol Amendment and Deviation Policy

## Amendments
A protocol may be changed only by a recorded **amendment**: a new commit that appends to
the protocol's `amendments` list with (date, reason, diff-of-intent). The original
preregistration is never edited in place.

**Hard rule:** a claim may NOT be *raised* after inspecting test/holdout evidence
without an amendment. **Narrowing** a claim (adding limitations, restricting scope) is
always permitted and is recorded in `claim_registry.json` and the changelog — as done
for the routing-v2 narrowing.

## Deviations
Any departure from the executed protocol is a **deviation** and is logged in the
experiment's `deviations.jsonl` and its `EXPERIMENT_CLOSEOUT`. A run with an unlogged
material deviation is `INVALID_PROTOCOL_DEVIATION`.

## Superseding results
When a later experiment overturns an earlier interpretation (e.g. CWC-L2a showing the
CWC-L2c straight-through collapse was an estimator artifact), the earlier claim is kept
with a `note` linking the superseding claim — negatives are never deleted.

## Fail-closed
Ambiguous, under-powered, or measurement-invalid outcomes resolve to
`BLOCKED`/`INVALID`, never a silent pass.
