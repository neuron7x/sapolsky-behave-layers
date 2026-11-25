# AGENTS — CWC repository entry point

This is a research repository, not a deployed autonomous control system. These are repository conventions for authorized contributors; they do not override higher-priority instructions, access controls, or owner decisions.

## Recover context without previous conversations

1. Read `SYSTEM.md`, `claim_registry.json`, `docs/methodology/CWC_MASTER_METHODOLOGY.md` and `docs/vnv/CWC_PROGRAM_DECISION_2026-08-11.md`. The original learned adaptive-depth flagship is closed as NOT_SUPPORTED. Do not silently revive it.
2. Read `experiments/cneh_joint_lp/HANDOFF.json`, `PROTOCOL.md` and `BIBLIOGRAPHY.md` in that directory when present. The handoff is a dated snapshot, not live authority. Resolve actual main, PR heads, bases, checkout trees, frozen protocols, CI and artifact receipts before using any recorded result. Separate integrated from stacked or open work.
3. Follow the existing COG epistemic/memory/plan/info/self primitives, H/I/J experiments and current qualified extensions. Do not create another module merely because its name differs. Use the dependency and exit predicates in the handoff for the next concrete task.
4. Real external model transfer is governed by `experiments/real_transfer_01/PREREGISTRATION.md`, both pre-execution amendments and readiness gate. Source intake alone is not model performance; a synthetic fixture is not an external measurement.

## Engineering contract

- Work on an explicitly authorized branch; preserve historical source, protocol, claims and negative evidence. Freeze new scientific thresholds and cases before implementation/output. Keep each change set narrowly scoped. No direct main edits, merges, mark-ready or parent integration without owner authorization.
- Proposed evidence must bind exact input, assumptions, objective, model, head/base/checkout, run attempt and payload/receipt digests. A valid mathematical certificate is not authenticity of external measurements. Never treat nonempty outer relaxation as existence, timeout as UNSAT, or absence of a witness as a contradiction.
- Independent verification means a separate checker for the mathematical obligation, not just model agreement. Agent proposals, even from multiple models, are not proof. Distinguish checker independence, cross-process reproducibility, independent cohort replication and external scientific replication.
- A solver, optimizer, learned proposer or reviewer can suggest candidates; only a checked certificate may support the precisely scoped result. Unknown, malformed, stale or over-budget results remain non-authorizing. Revisions to assumptions invalidate dependent proof identities.
- Use existing canonical CI and native proof gates. Preserve failed receipts. Repair only demonstrated engineering defects; never tune away a scientific counterexample, weaken the invariant or alter thresholds to obtain green CI. Stop branch writes at complete verified qualification and leave merge to the owner.

## Reproduction and source traceability

For JOINT-LP-01, use CPython 3.12.16:

```bash
python -B -m unittest discover -s tests -p test_cneh_joint_lp.py -v
python -B -c 'from experiments.cneh_joint_lp import panel,run; from experiments.cneh_exp_06f.run import canonical; r=panel.report(); run.validate(r); print(canonical(r).decode("ascii"),end="")' > /tmp/cwc-joint-lp.json
sha256sum /tmp/cwc-joint-lp.json
```

Repeat in a separate process with a different PYTHONHASHSEED and `python -B -O`; compare canonical bytes. This local replay does not replace hosted exact-attempt receipts. The canonical CI invokes the full project verification and native workflow. Source selection and mathematical applicability arguments are in the module bibliography. Record a source identifier and specific obligation for every new mathematical method; no appeal to institution prestige as evidence.

## Handoff format for subsequent agents

Each completed task must record: exact source and evidence identities; observed result versus hypothesis; derivation or explicit counterexample; prerequisites; bounded next action; independent acceptance test; scope and negative outcomes. Preserve source attribution and uncertainty. Never announce scientific promotion, physical calibration, operational authority, broad novelty or independent replication merely because tests pass. Keep the next task small enough that another agent can reconstruct the result from the repository without private conversation history.
