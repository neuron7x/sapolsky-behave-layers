# Pull-request verification

The repository uses the same admission commands locally and in GitHub Actions.
Every gate is free and reproducible without a hosted commercial analysis service.

## Local cycle

```bash
make -f Makefile.cwc pr-fast      # lint, strict types, tests, evidence and docs
make -f Makefile.cwc pr-security  # workflows, Git history secrets, dependency CVEs
make -f Makefile.cwc pr-full      # complete verification + security
```

`pr-fast` is the development feedback loop. `pr-full` is the merge-grade cycle:
branch coverage, mutation falsification, all registered experiment suites,
evidence validation, bibliography resolution, and claim/hypothesis traceability.

The security target requires Docker and `uv`. Secret findings are redacted.

## GitHub PR gates

- `cwc-quality`: Ruff, strict mypy, CPU-portable tests, branch coverage, mutation.
- `cwc-doc-gates`: evidence checksums, bibliography, traceability, regenerated docs.
- `cwc-full-pr-gate`: the canonical full verification/validation/falsification cycle.
- `pr-audit`: Actionlint, Gitleaks, pip-audit, and dependency-diff review.
- `codeql`: Python security-and-quality analysis.

The default branch is protected. Required checks must be current with the base
branch; administrators cannot bypass the rule; force-push and deletion are disabled.
Human approval is not required because this is a solo-research repository, but all
review conversations must be resolved.

CUDA and physical-energy measurements are hardware gates. A CPU GitHub runner must
record them as skipped or `NOT_MEASURED`, never as a successful physical measurement.
