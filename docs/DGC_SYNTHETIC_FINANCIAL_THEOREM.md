# DGC-01 Synthetic Financial Theorem

Status: **ANCHORED to the frozen synthetic workload; not a production/client savings claim**.

DGC-01 samples five regimes A-E with equal mixture weight `1/5`.

## 1. Compute decision over the frozen support

### A and D

`same_optimal_action=True`. Therefore immediate decision regret is identically zero under every admitted world and the perfect diagnostic has

\[
VOC = 0 - Cost < 0.
\]

DGC stops; B0 fixed-compute buys the diagnostic.

### B

For any parameter realization in the frozen support,

\[
p_B L_B \ge 0.10\cdot0.95 = 0.095
\]

and

\[
(1-p_B)L_A \ge (1-0.16)\cdot0.14 = 0.1176.
\]

Hence expected baseline regret is at least `0.095`, while diagnostic cost is at most `0.045`. Therefore `VOC >= 0.050 > 0`: DGC always buys.

### C

Both action-error branches are bounded below by

\[
0.44\cdot0.80=0.352,
\]

while diagnostic cost is at most `0.12`. Therefore `VOC >= 0.232 > 0`: DGC always buys.

### E

\[
p_BL_B \ge 0.045\cdot1.40=0.063,
\]

\[
(1-p_B)L_A \ge 0.95\cdot0.15=0.1425,
\]

while diagnostic cost is at most `0.060`. Therefore `VOC >= 0.003 > 0`: DGC always buys.

Thus DGC and B0 have exactly equal decision quality on the frozen synthetic support: DGC only skips compute in regimes where the external action is invariant.

## 2. Closed-form expected cost

The diagnostic-cost expectations (uniform midpoint) are:

- A = `0.1000`;
- B = `0.0350`;
- C = `0.1000`;
- D = `0.1000`;
- E = `0.0575`.

Therefore

\[
E[C_{B0}] = \frac{0.1000+0.0350+0.1000+0.1000+0.0575}{5}=0.0785.
\]

DGC buys only B/C/E:

\[
E[C_{DGC,core}] = \frac{0.0350+0.1000+0.0575}{5}=0.0385.
\]

Core-compute savings are therefore

\[
S_{core}=1-\frac{0.0385}{0.0785}=0.5095541401\ldots
\]

or **50.9554% inside this synthetic model**.

This is not estimated from the development run; it follows from the already-frozen generator support and equal regime mixture.

## 3. 30% threshold and overhead budget

Let `h` be total mean DGC governance/monitoring overhead in the same cost units. Then

\[
S_{net}(h)=1-\frac{0.0385+h}{0.0785}.
\]

The target `S_net >= 0.30` is equivalent to

\[
h \le 0.70\cdot0.0785-0.0385=0.01645.
\]

Thus the frozen synthetic model supports the exact conditional statement:

> DGC exceeds the 30% net-savings target **iff mean added governance overhead is at most 0.01645 normalized cost units per decision**, while preserving the frozen quality/coverage contract.

Equivalently, the permitted overhead is about `0.20955` of B0's mean inference cost in this synthetic workload.

The unresolved real-world question is not the algebra. It is whether live, fully metered DGC overhead and estimator error remain inside this budget on actual inference traces.
