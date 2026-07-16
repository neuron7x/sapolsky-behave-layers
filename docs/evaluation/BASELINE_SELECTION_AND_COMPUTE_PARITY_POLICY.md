# Baseline Selection and Compute-Parity Policy

## Minimum baseline set (for any advantage claim)
dense · best-fixed policy · static prune · random depth · **Mixture-of-Depths** ·
budget-conditioned dynamic depth · recursive/shared-parameter · static MoE · sparse MoE
· CWC. (Current mechanism experiments include dense/best-fixed/random/frozen/shuffled
controls; MoD/MoE are cloud-blocked and marked `NOT_TESTED`.)

## Parity requirements
Every compared system shares: task, dataset, training token budget, evaluation corpus,
optimizer family, precision, hardware class, and **hyperparameter-search budget**. The
CWC controller + dispatch cost is always counted. Operating point chosen on validation.

## Prohibited
- no arbitrary "CWC score";
- no hiding latency behind a FLOP number;
- no excluding controller/parameter/optimizer cost;
- no best-seed selection.
