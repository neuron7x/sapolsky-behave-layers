# Author, Funding, COI and AI-Assistance Disclosure

## Author
Yaroslav Vasylenko — research direction, hypotheses, methodology, acceptance decisions,
and responsibility for all claims.

## Funding
No external funding. Compute is the author's local hardware (RTX 3050 4GiB).

## Conflicts of interest
None declared.

## AI assistance (full disclosure)
- **Model / tool:** Claude (Anthropic), via Claude Code, acting as an autonomous coding
  and analysis agent under the author's direction.
- **Task types:** experiment implementation, running experiments, statistical analysis
  scripts, artifact/verdict generation, and this documentation layer.
- **Code:** the large majority of `experiments/`, `scripts/`, and `cwc/` code was
  written by the AI agent; the author specified the hypotheses, review critiques, and
  acceptance gates.
- **Analysis:** metric computation, bootstrap CIs, and verdicts were produced by AI-written
  code and are fully reproducible from the committed scripts.
- **Documentation:** methodology, registries, cards, and reports in `docs/` were AI-drafted
  and grounded in the real repository state.
- **Verification status:** all claims are backed by committed code, tests, and
  checksummed evidence bundles. The author is responsible for the scientific claims.
  **Independent replication has NOT been performed** (CWC-L8 = NOT_TESTED); no third party
  has yet re-derived the results.
- **Not independently verified:** cross-hardware behaviour, scale generalization, and any
  cloud-tier result (all marked NOT_TESTED).
