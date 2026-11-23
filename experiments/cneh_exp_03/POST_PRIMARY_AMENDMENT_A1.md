# EXP03 post-primary debt disposition (A1)

This amendment was written **after** the first successful primary run at
`b10981238d1c5dbace49650e141e4addfb648443` ([CI #45256132823](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45256132823)).
Do not amend the frozen primary protocol, seed list, endpoints or runner.
No new confirmatory cohort or scientific promotion is authorized.

## Preserved observations

All 8 worlds and 32 arms executed; all pre-intervention spiking checks passed.
Each B post-window arm had 16 population spikes (1 per neuron on aggregate,
not proof every individual neuron fired exactly once).
Primary factorial spike-count contrast: exactly 0 in every world.
Mean secondary voltage interaction: -0.03445054126113689 mV.
All eight secondary contrasts were negative. These are internal descriptive
observations from the fixed public fixture cohort, not a confidence statement.

## Debt T1 — endpoint sufficiency

For tick-level counts n(t), define d(t)=n_SP(t)-n_SB(t)-n_CP(t)+n_CB(t).
The primary endpoint is sum_t d(t)/16. Zero sum does not imply d(t)=0.
The new independent reduction checks both population count series, integer
integration, cumulative displacement and maximum cumulative magnitude.
It independently reconciles B's frozen endpoint to raw traces and reports
all worlds without exclusion. Population histograms cannot establish
neuron-specific timing, synchrony, PID, or mediation.

## Debt T2 — finite-window probe DC

600 post-intervention ticks at period 80 are 7.5 cycles. A sinusoidal probe
over this window is not necessarily mean-zero. Its signed input area and
mean offset must be reported. The separate mean-free reference subtracts
the discrete mean and rescales to match the original deviation sum of
squares, with bounds checked. This is not a change to EXP03, not physical
energy parity, and not proof of orthogonality to a stabilizing action.

## Debt T3 — causal scope and next prospective design

The existing structural x probe interaction is a well-defined total response
modification inside this simulator. It does not isolate the direct A-to-B
synaptic path: recurrent alternatives and the endogenous global gain channel
remain possible. A follow-on study should cross the same structural and
probe factors with endogenous versus externally fixed gain, using a common
predeclared gain schedule across arms and a mean-free bounded probe.
The change of interaction between gain policies is an intervention-defined
contrast, **not** a natural direct/indirect mediation estimate. To qualify
a direct-path claim, measure and independently validate the actual delivered
synaptic contributions and the alternate pathways. Record full per-neuron
spike vectors and relevant gain/conductance states in that new lineage.
Select all settings and endpoints before observing its new disjoint cohort.
No claim of active causal-model recovery or dual-controller efficacy follows
from a fixed open-loop probe.

## Engineering closure

Use the original runner to reconstruct the primary bundle, verify every
byte against the supplied evidence, then independently reduce the raw
traces. Write a separate sealed audit with source/manifest digests.
CI must run the original tests and the audit known-answer counterexamples.
No historical artifact is edited. Old cancellation #45255782921 was
superseded during branch construction; successful current-SHA jobs, not
reruns of obsolete revisions, determine release readiness.
