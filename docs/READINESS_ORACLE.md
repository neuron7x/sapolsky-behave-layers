# Readiness Oracle

The readiness oracle answers “what level is this system actually at?” from
repository evidence. It separates an engineering-control score from the release
status. Blocking facts dominate the status even when the technical score is
100/100.

The score measures implemented architecture, inference integrity,
reproducibility, supply-chain inventory, adversarial testing, claim artifacts,
negative-result preservation and documentation traceability.

The current status is expected to remain
`LOCALLY_VERIFIED_RESEARCH_ENGINEERING` while registered supported claims lack
independent replication, no supported real-workload claim exists, or restricted
data remains intentionally quarantined. This is a technical positioning, not a
social title.

```bash
PYTHONPATH=. python scripts/readiness_oracle.py
```

The blocking-facts-first design was independently adapted from a readiness
pattern found during the local CTI-OS DATA audit. No implementation code was
copied. The oracle does not certify product-market fit, general intelligence,
scientific truth, or safety outside its enumerated evidence.
