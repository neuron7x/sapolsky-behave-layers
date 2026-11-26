# Author, Funding, COI and AI-Assistance Disclosure

## Author
Yaroslav Vasylenko — research direction, hypotheses, methodology, acceptance decisions,
and responsibility for all claims.

## Historical funding, compute and conflicts disclosure
The earlier disclosure recorded no external funding, author-local compute on an RTX 3050
with 4 GiB, and no declared conflicts. The audit below used GitHub-hosted verification.
Current funding and conflicts require author confirmation for any submission.

## Historical AI assistance
- **Model / tool:** Claude (Anthropic), via Claude Code, acting as an autonomous coding
  and analysis agent under the author's direction.
- **Task types:** experiment implementation, running experiments, statistical analysis
  scripts, artifact/verdict generation, and this documentation layer.
- **Code:** the large majority of `experiments/`, `scripts/`, and `cwc/` code was
  written by the AI agent; the author specified the hypotheses, review critiques, and
  acceptance gates.
- **Analysis:** metric computation, bootstrap CIs, and verdicts were produced by AI-written
  code. Committed scripts support the results linked by the relevant evidence records.
- **Documentation:** methodology, registries, cards, and reports in `docs/` were AI-drafted
  and grounded in the real repository state.
- **Verification status:** the historical claims use the support levels and evidence
  named in the registry. The author is responsible for the scientific claims.
  **Independent replication has NOT been performed** (CWC-L8 = NOT_TESTED); no third party
  has yet re-derived the results.
- **Not independently verified:** cross-hardware behaviour, scale generalization, and any
  cloud-tier result (all marked NOT_TESTED).

## Documentation-audit assistance

Codex and delegated Codex reviewers performed source inspection, documentation
analysis, edits, and GitHub-hosted verification for this audit. Historical
statements above describe their recorded phase. Current funding, conflicts,
author contributions and method-specific AI usage for any submission require
the author's confirmation. Hosted CI and code review do not substitute for a
third-party experiment or an externally issued acceptance.
