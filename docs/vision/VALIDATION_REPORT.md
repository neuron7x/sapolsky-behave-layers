# Local Validation Report

**Artifact:** Cognitive Weave Kernel 0.1.0  
**Validation date:** 2026-07-15 (initial), revalidated 2026-07-16 after bibliography integration  
**Environment:** Python 3.12.3, PyTorch 2.13.0+cu130 CPU, ruff 0.15.21, mypy 2.3.0

## Executed checks

| Check | Result |
|---|---|
| Unit and invariant tests | PASS — 11/11 (10 original + bibliography gate test) |
| Deterministic smoke training | PASS — finite outputs and losses, byte-identical to 2026-07-15 run |
| Repository structural validator | PASS |
| JSON Schema meta-validation | PASS |
| Python bytecode compilation | PASS |
| Claim Firewall negative test | PASS — unsupported claim rejected by unit test |
| `ruff check src tests scripts` | PASS — 0 errors (13 found and fixed 2026-07-16) |
| `mypy --strict src/cwk scripts` | PASS — 0 errors (13 found and fixed 2026-07-16) |
| `bibliography-verify` (`CWC-BIB-USCN-001`) | PASS — 35 primary sources, 10 claims |

## Smoke evidence

- active expert fraction: 0.50;
- attention density: 0.347222;
- route overflow: 0;
- fallback: false;
- memory size after controlled write: 16;
- initial loss: 4.486858;
- final loss: 4.261907;
- topology hash: `be93e580b5d7c40894884a2af273a9c85fdc413c4a57e7475e6b9cfd1a50377c`.

These values prove only that the reference contracts execute and emit evidence. They do not establish architectural superiority, energy efficiency or cognitive capability.

## 2026-07-16 remediation notes

`ruff` and `mypy --strict` were not executed in the 2026-07-15 artifact-generation environment. Running them
surfaced 13 ruff findings (import ordering, unused import, 6 line-length overruns) and 13 mypy-strict findings
(missing `types-jsonschema`/`types-PyYAML` stubs, three `nn.Module` buffer attributes mypy could not type through
`register_buffer`, four `Any`-returning calls through `nn.Module.__call__`, one genuine torch stub gap on
`Tensor.backward`). All were fixed in source; none required behavior changes to `forward()` numerics — the smoke
evidence above is unchanged byte-for-byte. `types-jsonschema` and `types-PyYAML` were added to the `dev` extra in
`pyproject.toml` so this gap cannot silently reopen.

## Bibliography integration

`docs/BIBLIOGRAPHY_US_CN.md`, `docs/claim_source_matrix.json`, `docs/SOURCE_AUDIT.csv`,
`scripts/check_claim_source_matrix.py`, `tests/test_claim_source_matrix.py` and
`.github/workflows/bibliography-claim-gate.yml` were merged from the external `CWC-BIB-USCN-001` package
(SHA256SUMS.txt verified intact before merge). `CLAIMS.md` was added to bind each `CWC-CLM-*` row to its
architecture component per `CLAUDE_CODE_INTEGRATION.md`. `CWC-*` identifiers and the author field were preserved
unchanged, per that directive's explicit instruction not to rename canonical identifiers.
