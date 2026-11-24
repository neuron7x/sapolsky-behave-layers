# CNEH-EXP-05S — finite synthetic charge-aware selector falsification

Scope: mathematical engineering fixture only; no native simulation, new efficacy cohort, historical replay repair, or scientific promotion. Parent main a2f9bc79c0e87f7316ba13441e83e5a05b52c95a; EXP05Q protocol b54d23254c5d06f01adfa19909fc602ecef150fc motivates this independent diagnostic. PR56–58 and frozen EXP05 remain untouched. Freeze this protocol before implementation.

## Exact finite model

Time t=10, horizon h=3 ticks. Initial admissible automaton states are explicitly declared public support (mode, used-switch flag), each with used=0. Enumerate all successor paths using EXP05I switch grammar, including the unobserved final action mode at t+h. Independently enumerate mode sequences and validate the allowed window and one-switch rule. Four routes ((1,0),(0,1),(1,1),(0,0)). Initial adaptation pairs from a declared finite Cartesian set; drive tapes and erasure tapes from declared finite rosters. All combinations retained, no probability assigned. One finite toy source event per group per tick: s_j=1[drive_j+6*1[a=j]>=4+w_j], w'_j=floor(w_j/2)+4*s_j. This is a deliberately non-native integer fixture of adaptation/recovery, NOT an AdEx forecast or physically calibrated model. Public observation of transition k is (group 0 bit or erased, group 1 bit or erased, exact route arrival count); each observation becomes available only after the transition. Same initial scenarios and exogenous tapes coupled across every plan. All 27 plans in lexicographic order WAIT, G0, G1 over three ticks. Source charge 200 pA ms per active tick, 0 for WAIT; finite cap. No control/safety guarantee in the toy fixture.

For each plan compute exact observational equivalence classes from complete synthetic scenario roster; each class projects to possible action modes at t+h, not t+h-1. No true-mode input to a deployed selector. Here latent mode is used only by the finite model generator/evaluator for constructing the classes. Verify the final true mode belongs to its class for every scenario. Independently cross-check every class by pairwise equality on the complete roster. A(S)=n(n-1)/2 unresolved pairs; G(a)=min over coupled scenarios [A(S_WAIT)-A(S_a)]. Rank positive G / charge exactly with fractions, then lower charge, then frozen plan order. Reject empty/duplicate scenario rosters, malformed support, missing plans, invalid costs or invalid budget. If no positive affordable candidate, WAIT. Do not assert physical safety or availability of this guarantee outside finite fixture; real public-only source uncertainty and native numerical qualification remain prerequisites. Under last-tick hidden switch, observational equivalence may expand after otherwise decisive data.

## Frozen fixture roster

All start mode supports are (0,1,2,3) except singleton fixture (0). All drive tapes are constant 3 ticks unless explicitly listed. Erasure flags 0=visible,1=erased. Fixture definitions (initial w values per group, drive tape, mask tape, switch windows, budget pA ms):
- INFORMATIVE: (0),(0); drive (0,0); mask (0,0); none; 600.
- SILENT: (20),(20); drive (0,0); mask (0,0); none; 600. Both sources stay below threshold even after two recovery ticks.
- RECOVERY: (8),(8); drive (0,0); mask (0,0); none; 200. Early stimulation silent, late stimulation informative.
- ALIAS_NO_BUDGET: (0),(0); drive (4,4); mask (0,0); none; 0.
- REVIVAL: (0),(0); drive (0,0); mask (0,0); [(13,13)]; 600.
- HIDDEN_WINDOW: (0,8),(0,8); drive tapes constant (0,0) and (4,0); mask tapes constant (0,0), (1,0), (0,1), (1,1); [(11,11)]; 400.
- SINGLETON: (0),(0); drive (0,0); mask (0,0); none; 600; initial singleton mode 0.
- ERASED: (0),(0); drive (0,0); mask (1,1); none; 600.

Report complete per-fixture per-plan min gain, charge and score, selected action, number of scenarios, independent equivalence cross-checks; record exact byte replay. Invariant tests: silence=>WAIT, final hidden switch=>WAIT, singleton=>WAIT, zero budget=>WAIT, recovery selects one late pulse (fixed menu tie order), no positive gain from removing already excluded hypotheses, all erasure still true-containing, input order invariance, exact rational ranking and tie, malformed/missing roster rejection; compare independent schedule enumeration. Preserve all negative outcomes; green CI proves only finite fixture implementation. No native efficacy inference, no promotion. Inherit PR59 promotion guard, explicit negative verdict and SHA256.
