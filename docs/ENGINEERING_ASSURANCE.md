# Engineering assurance capabilities

This repository treats engineering level as demonstrated system capability, not
as a title. Seven mandatory controls raise the project from a tested research
prototype to a machine-audited research engineering system.

1. **Architecture contract.** `engineering/architecture_contract.json` declares
   package boundaries. `architecture_gate.py` parses the real Python import graph
   and rejects undeclared cross-boundary coupling.
2. **Hermetic reproduction contract.** Canonical evidence and reproduction
   scripts are statically denied network clients and must preserve their
   isolation, explicit seeds and hash-seed controls.
3. **Assurance fault injection.** `assurance_attack.py` corrupts disposable
   repository copies with a cross-layer import, network dependency, complexity
   regression and SBOM tamper. A green result requires every injected fault to
   be detected.
4. **Deterministic software bill of materials.** `SBOM.cdx.json` is generated
   exactly from `uv.lock`, merges duplicate lock records without dropping
   hashes, and carries the lock SHA-256 in CycloneDX metadata.
5. **Algorithmic complexity budgets.** Critical falsification and verification
   functions have explicit AST-derived cyclomatic and statement-count ceilings.
   These are structural regression limits, not flaky wall-clock benchmarks.
6. **Commit-bound assurance report.** `assurance_report.py` records the Git
   commit, Git tree, lock digest and result of each independent engineering gate
   in a machine-readable JSON artifact.
7. **Mandatory admission enforcement.** `engineering-assurance` is a required
   fail-closed GitLab job and part of the canonical `pr-security` target.

Run all seven controls locally:

```bash
make -f Makefile.cwc engineering-assurance
```

## Claim boundary

These controls show that declared boundaries and frozen supply-chain metadata
match the repository and that known attacks are rejected. They do not prove the
absence of every architectural defect, vulnerability, performance regression or
scientific error. New failure classes must become new attacks or contracts.
