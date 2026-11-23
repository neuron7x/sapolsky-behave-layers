# Source-pinned BN-Syn interface qualification

The actual `neuron7x/bnsyn-phase-controlled-emergent-dynamics` repository at commit `c1de425ce4ece362e7f2feb2d9f24da5d3231014` is executed in a separate GitHub Actions job. `bnsyn_bridge.py` directly instantiates its `Network`/AdEx classes, reads two disjoint population voltage/spike outputs and feeds two bounded CNEH cortex actions into neuron-specific external currents. It checks exact central-emulation parity, deterministic replay and SHA256SUMS, including a negative test where an attacker edits the trace and re-signs every checksum.

The intervention at tick 24 is a hidden **additive input-current disturbance**. It is NOT a structural `Delta A` shift and therefore cannot confirm the CNEH-04-DC structural-OOD hypothesis. Voltage scaling and local controllers are an engineering interface, not calibrated biological state estimation; no PID, information geometry, neuroemergence, safety, energy optimization or real-world neuroscience result follows. Spiking may be absent, which is a measured null rather than a sign of failure if voltage dynamics are still valid.

Source SHA and full output are preserved in the evidence artifact. The original BN-Syn project is not modified. This interface is a new engineering capability, distinct from the preregistered synthetic CNEH-EXP-02 PRIMARY endpoints.
