# CWC-VIA-02 — Opportunity/Observability Separation and Mechanism Admission

**Status:** PROTOCOL FROZEN BEFORE EXECUTION
**Programme:** Cognitive Wiring Core (CWC)
**Scientific frontier:** VIA-V1
**Ascension authority:** none by this act alone

## 1. First-principles correction

VIA must distinguish two logically different questions:

1. **Opportunity:** if every independent unit could receive its best action, is there any adaptive
   value over the best fixed action?
2. **Observability:** can a cheap pre-decision state expose enough of that opportunity to realize it?

The ordering is a theorem of the finite-action decision problem:

```
best fixed value <= coarse-context oracle <= instance oracle
```

A negative result for one chosen context representation therefore cannot establish that the
instance-level opportunity is zero. It establishes that the tested representation, mechanism, and
cost model did not expose certifiable value. This does **not** invalidate WP18/WP19: their frozen
claims remain exactly scoped to the tested tied-K / untied-depth mechanisms and tested context
partitions. The correction prevents VIA from confusing “wrong/weak state variable” with “no latent
heterogeneity” in future work.

## 2. Revised VIA semantics

### VIA-V1 — action opportunity

Primary object for a new mechanism is the exhaustive per-unit potential-outcome table when feasible.
Before choosing a learned router feature, compute:

```
G_instance = E_i max_a U_i(a) - max_a E_i U_i(a)
```

For a scientifically meaningful latent/task regime `Z`, also compute:

```
G_Z = E_Z max_a E[U(a)|Z] - max_a E[U(a)]
```

The mandatory invariant is `0 <= G_Z <= G_instance`.

### VIA-V2 — observability ceiling

Only after a new mechanism has non-zero, economically relevant VIA-V1 opportunity may VIA-V2 freeze
an observable-state family `X` and ask how much of `G_instance` it can capture. Feature search belongs
here, not in VIA-V1. This removes the incentive to repeatedly invent “difficulty proxies” until one
appears positive.

## 3. Quality/compute separation

Raw task quality and compute are not silently collapsed. Candidate mechanisms are first examined as a
Lagrangian family:

```
U_lambda = quality - lambda * compute,   lambda >= 0
```

For finite actions, action rankings change only at pairwise line crossings. CWC therefore computes
those critical lambdas exactly and evaluates one representative point per constant-ranking region.
No arbitrary lambda grid search is needed.

A controller with compute cost `c_ctrl` is admissible at a lambda only if:

```
G_Z(lambda) - lambda * c_ctrl > 0
```

The resulting `G_Z(lambda)/lambda` is an upper bound on tolerable controller compute for that lambda.
It is an economic screening quantity, not a GPU latency claim.

## 4. Candidate selected: adaptive attention horizon

The next candidate compute axis is **attention horizon**, not tied iteration count and not model depth.
This is scientifically distinct from WP18/WP19 and is already structurally meaningful in nanochat,
whose GPT configuration contains fixed short/long sliding-window attention patterns.

Actions for the controlled qualification are:

```
short: H=2 visible symbols
full:  H=8 visible symbols
```

Two exactly enumerable dependency regimes are used:

- `local`: target is the most recent symbol; both horizons contain the necessary information;
- `long`: target is the first symbol; only the full horizon contains the necessary information.

The controlled task does **not** claim that nanochat, a production GPU kernel, or a real-world corpus
has the same quality/compute surface. It asks one narrower question: does attention horizon have the
minimal mathematical structure required for adaptive value — a cost/quality trade-off whose optimal
action can change with regime?

## 5. Why this is the next admissible task

A new learned router is premature while VIA-V1 is blocked. A new “difficulty signal” would violate the
WP18 anti-fishing rule. Building hierarchy would violate the VIA ancestor gate.

A mechanism-qualification experiment is admissible because it:

- changes the **compute mechanism**, not the difficulty proxy;
- has no scientific ascension authority;
- uses an exactly enumerable controlled task with no benchmark selection;
- quantifies the maximum controller cost the mechanism could tolerate before any learned controller
  is attempted;
- can fail and permanently reject this candidate before expensive training/runtime work.

## 6. Qualification gate

The attention-horizon candidate is **qualified for a future prospective real pilot**, but does not
PASS VIA-V1, only if all conditions hold:

1. exhaustive action outcomes are complete and deterministic;
2. `fixed <= regime oracle <= instance oracle` at every evaluated lambda;
3. at least one positive-lambda region has `G_regime(lambda) > 0`;
4. the maximum tolerable controller-compute allowance is strictly positive;
5. both actions are optimal in at least one regime somewhere in the positive region;
6. the result artifact explicitly sets `scientific_pass=false` and `ascension_authorized=false`.

Any failure yields `ATTENTION_HORIZON_MECHANISM_REJECTED` and the candidate must not proceed to a real
pilot without a new act.

## 7. What remains prohibited after a qualification PASS

Even a successful controlled qualification does not authorize claims that:

- real language/model workloads benefit from adaptive attention horizon;
- an observable cheap controller state exists;
- physical GPU kernels skip unselected attention work;
- end-to-end latency, throughput, memory, or energy improves;
- VIA-V2 may start;
- CWC hierarchy is justified.

## 8. Next step after qualification

If and only if the controlled candidate qualifies, the next act is a **prospective real-workload
VIA-V1 pilot** with a frozen workload family, frozen split, fixed attention-horizon actions, exhaustive
counterfactual replay where feasible, and no learned controller. The pilot first measures
`G_instance`; only after a positive opportunity certificate may observability/state design begin.
