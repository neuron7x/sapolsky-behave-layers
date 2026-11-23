# A6: preserve opaque negative evidence with its correct data type

Engineering packaging amendment, 2026-11-23. Delivery candidate
5d579a20a16700ae0cbec9daf8640edecf8603f3 remains BLOCKED: the aggregate CodeQL
check correctly reports a syntax error in a negative wheel-member data fixture
named `module.py`. The verifier writes and compares these opaque bytes; it never
executes them as Python. The payload SHA256 is
4428268f19678db65706c3308d336cd642ba6cee7ec895a961ed3862d83d1a73.

Correct only this artifact's data-file extension to `.bin`, preserving its exact
bytes and mode. Retain the historical RECORD unchanged, the original top-level and
nested manifests as inactive provenance sidecars, and the original layout in Git.
Record the three path mappings needed to reconstruct that exact historical layout.
Regenerate only the active export manifests and explicitly identify the layout
transition; do not recalculate experimental results or rewrite prior verdicts.

Execute a reconstruction into a new directory from the migrated bytes and saved
manifests. Compare every original path, mode and byte against the trusted 5d579a2
Git tree and verify the restored manifests. Independently repeat the reconstruction.
Check that all current Python artifacts parse as Python without executing them.

No CodeQL exclusion, alert dismissal, threshold relaxation, A1/A2 mutation or
scientific promotion is authorized. Informational findings in frozen historical
scripts remain historical. The corrected delivery requires new exact-SHA CI and
fresh final G1–G4 execution; successful checks on 5d579a2 cannot qualify it.
