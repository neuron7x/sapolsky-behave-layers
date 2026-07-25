# Evidence Intake Firewall

External corpora are untrusted inputs, not evidence merely because they exist.
The intake firewall inventories every regular file without following symlinks,
streams every byte through SHA-256, and separates four non-overlapping classes:
candidate, restricted, vendor, and archive.

It produces:

- a deterministic corpus root committing to relative path, size and content;
- exact byte and file coverage with fail-closed read/change errors;
- content-duplicate counts and reclaimable bytes;
- aggregate privacy/vendor/archive quarantine statistics;
- an optional local JSONL manifest for forensic selection.

The aggregate summary contains no file content. The optional manifest contains
paths and must remain a local assurance artifact when paths themselves are
sensitive.

```bash
PYTHONPATH=. python scripts/data_asset_audit.py /path/to/corpus \
  --summary assurance-build/data-intake/summary.json \
  --manifest assurance-build/data-intake/manifest.jsonl \
  --require-complete
```

## Design provenance and boundary

The method adapts recurring design requirements observed in the local CTI-OS
falsifier lineage and PFC-CI content-addressed evidence ledger: fail closed,
preserve provenance, separate implementation correctness from scientific
validity, and keep negative/risky material visible without promoting it.
No source implementation was copied.

A successful intake proves byte coverage and deterministic classification under
the declared path policy. It does not grant a license, prove factual truth,
remove personal data, inspect archive members, or make a quarantined asset safe
to publish. Candidate assets require a second-stage license, schema, claim and
domain validation before integration.
