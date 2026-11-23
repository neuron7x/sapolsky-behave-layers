# Engineering qualification and integration guide

Authority: engineering evidence only. CNEH-04-DC remains
`FORMALIZED / EMPIRICAL VALIDATION PENDING`.

## Structural argument and statistical limits

Let a distributed policy's complete controller state, observation history and random
tape be available to a faithful central simulator. Inductively, identical initial
state and inputs yield identical controller transition, action and next plant state
at every step. Therefore the terminal binary outcomes agree for each paired world.
This is an expressivity statement. Membership in the same physical budget class
additionally requires an actual cost-preserving simulation; it does not follow from
the state-transition argument alone.

For this implementation `D_s=0` identically, so the frozen central contrast has
`LCB=-sqrt(2 ln(120)/128)≈-0.2735`, which cannot exceed `0.05`. Even an unlimited
number of samples only approaches zero. Neither more complex dynamics nor external
reproduction can make the original positive conjunction true. Keep this negative
control; preregister any restricted-comparator efficacy question separately.

The bound's sampling interpretation requires independent bounded world draws under
the declared data-generating model. A deterministic list of PRNG seeds does not by
itself prove those assumptions or population coverage. The fixed synthetic cohort
is an internal diagnostic. Its radius is about 0.2735: an observed mean contrast
must exceed about 0.3235 to cross the frozen threshold. A failed bound is not a
powered equivalence test or falsification of every restricted claim.

The three-step stale-message arm changes freshness and content together. It cannot
identify an isolated semantic-message effect. Analytic PID, Fisher or Gramian
qualification cannot repair that experimental confounding.

## Local commands

Run from the repository root, with new output paths and `umask 022`:

```sh
python -m unittest discover -s tests -p 'test_cneh_exp_01*.py' -v
python experiments/cneh_exp_01/mutation_check.py --out /tmp/cneh-mutations
python experiments/cneh_exp_01/run.py --phase primary --out /tmp/cneh-primary
python experiments/cneh_exp_01/run.py --out /tmp/cneh-primary --verify
python experiments/cneh_exp_01/qualification.py --bundle /tmp/cneh-primary
python experiments/cneh_exp_01/qualification.py --bundle /tmp/cneh-primary --require-scientific-readiness
```

The final command must exit **2**, with engineering PASS and scientific BLOCKED.
Exit 0 from ordinary bundle verification certifies internal evidence integrity only.
`verify_bundle(path)` can authenticate an honest INVALID bundle; admission requires
`verify_bundle(path, require_valid=True)`. A mutated verifier is not a trusted oracle:
source SHA binding must be anchored to the independently reviewed code revision.

```sh
python experiments/cneh_exp_01/estimators.py --out /tmp/cneh-estimators.json
python experiments/cneh_exp_01/hardware.py --out /tmp/cneh-timing.json --require-qualified-cost
```

Estimator output qualifies only Gaussian fixed-design mean Fisher, finite-horizon
LTI observability and Williams-Beer I_min on exact supplied discrete PMFs. It provides
known-answer fixtures, null/rank-deficiency checks, unit and coordinate checks, and
independent algebraic identities. No neural data estimator, finite-sample PID
uncertainty or interventional causal estimand is qualified.

Timing records all balanced randomized arm blocks and raw monotonic wall/CPU
boundaries. Every timed call is checked for deterministic replay; paired central
traces must agree. Cost qualification exits **2** and writes the measured report:
joules, FLOPs and attributable peak RAM remain null. Timings include batch result
capture and the complete synchronous simulator, including plant and hashing. They
do not establish controller-only or distributed end-to-end latency.

## Actual pinned neural integration

Prepare the source at the frozen commit without modifying any existing checkout:

```sh
git clone https://github.com/neuron7x/bnsyn-phase-controlled-emergent-dynamics.git /tmp/cneh-bnsyn
git -C /tmp/cneh-bnsyn checkout --detach c1de425ce4ece362e7f2feb2d9f24da5d3231014
python3.12 -m venv /tmp/cneh-neural-venv
/tmp/cneh-neural-venv/bin/python -m pip install --require-hashes --only-binary=:all: -r experiments/cneh_exp_01/bnsyn-requirements.lock --report /tmp/cneh-neural-install.json
/tmp/cneh-neural-venv/bin/python experiments/cneh_exp_01/bnsyn_adapter.py --source /tmp/cneh-bnsyn --out /tmp/cneh-neural
/tmp/cneh-neural-venv/bin/python experiments/cneh_exp_01/bnsyn_adapter.py --source /tmp/cneh-bnsyn --out /tmp/cneh-neural --verify
```

The adapter authenticates all 118 files in the source/metadata scope before import
and after execution; unknown additions, bytecode and symlinks are rejected. Source
SHA and complete installed-version inventory are retained. The hash-locked install
report binds downloaded dependency artifacts; local version labels alone do not
authenticate installed package bytes.

Observation is two partition-mean membrane voltages in mV. Action is bounded injected
current in pA. Controller inputs exclude latent parameter truth, future noise and
seed identity. The frozen smoke uses 32 AdEx neurons, 1000 steps of 0.1 ms and two
public exploratory seeds. It checks finite active spiking, exact emulator parity,
all-arm replay and a state-response difference under zero action. An ignored actuator
must fail even when action labels differ. It does not test task efficacy, adaptation
to OOD shifts, learned information gathering, communication semantics or criticality.

Neural bundle verification is exact within its recorded environment. A different
Python/platform or dependency inventory produces a separate bundle; do not relabel
that as a byte-identical replay of the original environment.

## Reused mathematics and bounded hardware metrology (A2)

PR44 is pinned at `d0eada284220c4dad759191f5a847139a2dcb999` for read-only
mathematical reuse. It remains a separate dependent experimental lineage. The
qualification bridge authenticates the reference file before loading it and uses
existing CWC causal estimators. Independent block/SVD/linear-solve oracles check
finite-horizon Wc/Wo, Hankel similarity invariance, covariance-weighted Fisher rank
and the distinction between state observability and parameter excitation.
Exact structural-equation interventions distinguish observationally equivalent
causal/confounded models. Leakage and OOD fixtures are analytic controls, not empirical
model-validity evidence. Raw reference failures remain visible; the bridge rejects
invalid input or numerical disagreement instead of silently repairing the reference.

```sh
curl --fail --silent --show-error --location https://raw.githubusercontent.com/neuron7x/sapolsky-behave-layers/d0eada284220c4dad759191f5a847139a2dcb999/experiments/cneh_exp_02/linear_reference.py --output /tmp/cneh-pr44-linear-reference.py
CNEH_PR44_REFERENCE=/tmp/cneh-pr44-linear-reference.py /tmp/cneh-neural-venv/bin/python -m unittest discover -s tests/cneh_math -p qualification_cases.py -v
/tmp/cneh-neural-venv/bin/python experiments/cneh_exp_01/math_qualification.py --reference /tmp/cneh-pr44-linear-reference.py --out /tmp/cneh-reused-math.json
/tmp/cneh-neural-venv/bin/python experiments/cneh_exp_01/math_qualification.py --reference /tmp/cneh-pr44-linear-reference.py --out /tmp/cneh-reused-math.json --verify
/tmp/cneh-neural-venv/bin/python experiments/cneh_exp_01/math_mutation_check.py --reference /tmp/cneh-pr44-linear-reference.py --out /tmp/cneh-math-mutations
python experiments/cneh_exp_01/metrology.py --out /tmp/cneh-metrology
python experiments/cneh_exp_01/metrology.py --out /tmp/cneh-metrology --verify --require-qualified-cost
```

The optional numerical cases run in the mandatory pinned numerical CI job; they are
not silently skipped in a dependency-free environment. Missing source or dependency
drift fails. The final metrology command must exit2 despite passing included
engineering ceilings. Fresh per-arm processes measure high-water RSS including the
interpreter/imports/warmup; separate profiling runs expose controller and serialization
fixture overhead; verification cost is measured separately. Every declared included
limit affects admission. Raw timings are validated for structure and arithmetic,
not authenticated as external metrology. Replay cannot recreate past wall-clock
intervals. Electrical energy, hardware FLOPs and physical transport remain invalid
instruments; matched upper ceilings do not demonstrate actual resource parity.

| BN-Syn obligation | Current PR43 evidence ceiling |
|---|---|
| Successful API integration | Executed pinned Network/AdEx source |
| Reproducible neural trajectories | Exact recorded state/action replay within the pinned environment |
| Genuine spiking | Measured spikes in the engineering smoke |
| Functional interpopulation coupling | NOT_TESTED: zero-action responsiveness is a different intervention |
| Structural neural OOD response | NOT_TESTED |
| Causal improvement in a neural goal task | NOT_TESTED; requires PR44/future prospective experiment |

## Sealed cohort workflow

The external operator prepares a private JSON array of 128 distinct 64-bit seeds,
excluding exposed PRIMARY and engineering cohorts, then runs:

```sh
python experiments/cneh_exp_01/replication.py prepare --seeds PRIVATE_SEEDS.json --code-sha REVIEWED_40_HEX_COMMIT --operator-id EXTERNAL_OPERATOR --out /tmp/cneh-commitment
python experiments/cneh_exp_01/replication.py seal --commitment /tmp/cneh-commitment/commitment.json --outputs RAW_OUTPUTS --out /tmp/cneh-output-seal.json
python experiments/cneh_exp_01/replication.py verify --commitment /tmp/cneh-commitment/commitment.json --reveal /tmp/cneh-commitment/private/reveal.json --output-seal /tmp/cneh-output-seal.json --outputs RAW_OUTPUTS --require-independent
```

Publish only the public commitment before execution; keep the reveal private until
outputs are published. Tooling creates the reveal with mode 0600 in a 0700 directory.
The final command must exit **2** even for a consistent commitment and output seal.
It verifies binding, not external publication time, operator independence, execution
provenance, untouched seeds or blind arm labels. Authenticated external records and
a separate execution protocol remain necessary. This CLI does not execute a
REPLICATION cohort or certify completeness/meaning of arbitrary sealed output bytes.

## Integration acceptance and unresolved gates

Merge review concerns the engineering substrate: source locks unchanged, actual
neural adapter executed, all targeted tests and calibrated mutations pass, adversarial
findings resolved, exact-head hosted checks green, negative evidence retained.
This is not scientific acceptance. Actual external independent blinded execution,
calibrated full physical resource vectors, qualified estimators on the intended
neural data and a prospective restricted-comparator study remain absent.

No SpaceX, xAI or US academic certification is claimed. These labels do not define
a single auditable standard. Acceptance is the set of explicit falsifiers above.

## Primary methodological sources

- [Linux Powercap](https://www.kernel.org/doc/html/latest/power/powercap/powercap.html): energy counters are power-domain measurements; package and child-domain totals overlap. Process attribution and wrap bounds are additional measurement obligations.
- [Intel PerfMon Skylake-X](https://perfmon-events.intel.com/platforms/skylakex/core-events/core/): event semantics are architecture-specific, including FMA counting. A guessed instruction-to-FLOP multiplier is not qualified.
- [NVIDIA Nsight Compute profiling guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/#overhead): profiling/replay introduces overhead and changed execution conditions. Keep profiling and unprofiled timing distinct.
- [NIST TN1297, Appendix A](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty): measurement models and uncertainty must include relevant contributions.
- [Williams and Beer, 2010, v1](https://arxiv.org/abs/1004.2515v1): I_min is a specified partial-information decomposition; its axioms do not supply intervention-based causal attribution.
- [Wieland et al., 2021, v2](https://arxiv.org/abs/2102.05100v2): local information and practical/structural identifiability require distinct qualifications.
- [Powel and Morgansen, 2020, v1](https://arxiv.org/abs/2006.07451v1): empirical nonlinear observability requires its own assumptions; LTI fixtures do not qualify neural observability.
