# DGC Product v1 — Pre-execution Registration

Status: `FROZEN_INTERNAL_PROTOCOL / EXTERNAL_HARNESS_NOT_MATERIALIZED`
Date: 2026-08-22

Primary claim authority: `docs/DGC_PRODUCT_CLAIM_v1.md`.
Statistical-plan authority: `docs/DGC_PRODUCT_STATISTICAL_PLAN_v1.md`.
External source identities: `docs/DGC_EXTERNAL_WORKLOAD_PANEL_v1.md` and `external_workload_sources.json`.

The confirmatory experiment MUST NOT execute until:

1. external task/scorer/environment bytes are materialized and hash-sealed;
2. B0-B3 executable baseline panel is frozen, including the B2 calibration-only fitted model digest;
3. model/prompt/tool/budget/pricing/scorer manifests are frozen;
4. the deterministic calibration/confirmatory task split is sealed;
5. repeated-trial count is computed from calibration-only variance under the frozen power-sizing rule;
6. confirmatory task outcomes remain unseen before all preceding digests are sealed.

Any change after confirmatory outcome inspection creates a new preregistration generation. This file does not authorize a real-workload or product claim.
