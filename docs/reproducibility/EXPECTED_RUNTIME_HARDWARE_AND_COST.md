# Expected Runtime, Hardware and Cost

## Local (all shipped results)
- **Hardware:** RTX 3050 4GiB + CPU (depth ≤ 12 caps the model on this GPU).
- **Runtime:** each mechanism experiment is seconds–minutes/seed on CPU; the 8-seed
  REINFORCE routing run is ~3 min total; surface-matched 4 arms × 8 seeds a few minutes.
- **Cost:** $0 (already run).
- **Disk/VRAM:** artifacts ~2 MB; peak VRAM well under 4 GiB at depth ≤ 12.

## Cloud (NOT_TESTED tiers G6–G8)
Anchored on the nanochat unit (`docs/upstream/NANOCHAT_README.md`): one GPT-2-grade
train (depth 20) ≈ 8×H100, ~1.5–2 h, ~$48 on-demand (~$15 spot), 4e19 FLOPs.
- **Decisive Act J (one scale):** ~8 systems × 8 seeds ≈ ~$1.5k spot / ~$4–5k on-demand,
  1–2 days on a few 8×H100 nodes.
- **Full checklist (2 workloads × 2–3 scales × 2 hardware classes + replication):**
  ~$20–50k, weeks. Second hardware class (e.g. RTX 4090 24 GB) for latency crossover.
- **Cheapest insurance first:** a ~$50–100 pilot measuring the cheap-probe-vs-oracle-probe
  route-decision-cost gap on the target workload, before committing the big spend.
