# DGC-02 Financial Development Verification
**Authority:** DEVELOPMENT_ONLY / NON-PROMOTING. The 30% figure is a verification target, not a commercial claim.
Tasks: 100000 paired synthetic decisions. Reference: `B0_FIXED`.
## Zero-unmetered-overhead core-compute ceiling
- aggregate NetInferenceSavings: `0.509524617`
- conservative savings LCB: `0.461944941`
- DeltaQuality: `0.000000000`
- quality LCB: `0.000000000`
- 30% development threshold: `PASS`
- max mean governance overhead compatible with 30% point-estimate target: `0.016452388` normalized cost units/task

This result is a ceiling because live governor/monitor/provider overhead has not yet been metered in the synthetic scalar-cost model.
## Overhead sensitivity
| overhead/task | net savings | savings LCB | gate |
|---:|---:|---:|:---:|
| 0.0000 | 0.509525 | 0.461945 | PASS |
| 0.0025 | 0.477687 | 0.430316 | PASS |
| 0.0050 | 0.445849 | 0.398686 | PASS |
| 0.0075 | 0.414011 | 0.367057 | PASS |
| 0.0100 | 0.382173 | 0.335427 | PASS |
| 0.0125 | 0.350334 | 0.303798 | PASS |
| 0.0150 | 0.318496 | 0.272169 | FAIL |

## Interpretation boundary
- Development synthetic evidence only.
- No USD/client/ARR claim is authorized.
- Live accounting must include governor, monitoring, tools, retries, provider charges and latency penalties.
- Untouched confirmatory and client-trace replication remain mandatory.
