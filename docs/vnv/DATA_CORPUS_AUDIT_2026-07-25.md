# DATA corpus intake audit — 2026-07-25

Source tree: local `DATA` corpus. No raw content or path manifest is committed.

| Measure | Result |
|---|---:|
| Regular files discovered | 145,655 |
| Regular files hashed | 145,655 |
| Read/change errors | 0 |
| Bytes hashed | 7,225,588,269 |
| Symlinks quarantined | 417 |
| Corpus SHA-256 | `313127c6bf7416dcefa29cd9e6c1cd36e6bace2f70d730b75cab2415940e97cf` |
| Exact duplicate paths beyond first copy | 52,766 |
| Potentially reclaimable duplicate bytes | 2,379,021,811 |

## Quarantine result

| Intake class | Files | Bytes |
|---|---:|---:|
| candidate | 24,189 | 426,489,487 |
| restricted | 1,886 | 339,552,125 |
| vendor/generated | 118,233 | 2,541,561,320 |
| archive/opaque | 1,347 | 3,917,985,337 |

The scan was executed twice after the final classification change and produced
the same corpus root. The root commits to path, size and content digest, while
classification does not alter identity.

## Integration decision

The reusable Evidence Intake Firewall was integrated. Raw DATA assets were not.
The strongest reusable requirements observed in the candidate set were:

1. content-addressed evidence lineage;
2. fail-closed falsifier and claim boundaries;
3. explicit separation of implementation correctness from scientific validity;
4. privacy/vendor/archive quarantine before selection;
5. duplicate-aware corpus economics.

CTI-OS and PFC-CI were used as local design-provenance examples. No source
implementation was copied.

## Claim boundary

This record proves complete successful hashing of regular files visible during
the scan and deterministic aggregate classification under the implemented path
policy. It does not inspect members inside opaque archives, establish licenses,
validate private content, or make candidate files scientifically true. The 417
symlinks were deliberately not followed, so external targets are outside the
byte-coverage claim.
