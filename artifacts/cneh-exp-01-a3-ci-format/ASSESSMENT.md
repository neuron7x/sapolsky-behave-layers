# A6: lossless data-artifact layout correction

Candidate 5d579a20 remained BLOCKED because CodeQL correctly parsed a `.py` file
as Python. That file contained opaque bytes from a deliberate installed-wheel
corruption fixture, not an executable module. The check failure and all annotations
are retained here. No CodeQL rule, path exclusion or alert threshold changed.

Only the data-file suffix changes to `.bin`; its SHA256 remains
4428268f19678db65706c3308d336cd642ba6cee7ec895a961ed3862d83d1a73.
The historical RECORD is unchanged. Both original manifests are retained as
`PROVENANCE_ORIGINAL_SHA256SUMS_5d579a2.txt`; the original complete layout remains
in the immutable 5d579a20 Git tree. LAYOUT_PROVENANCE_A6.json records the transition.

The supplied restoration command reads the migrated bytes, not replacement payloads
from Git. It reconstructs all 434 original paths in a new external directory,
compares every byte and executable mode against trusted historical Git blobs,
and checks all ten restored manifests:

```sh
python3 -B artifacts/cneh-exp-01-a3-ci-format/restore_original_layout.py \
  --repo . --out /tmp/cneh-a3-original-layout-UNUSED
```

The first reconstruction wrapper rejected a relative external path because it
retained lexical `..`; its failed execution is preserved and is not a PASS.
The corrected wrapper normalizes the output path and completed the full restoration.
The current checkout's Python files were syntax-parsed without executing them.

A1, A2, PRIMARY, frozen scientific inputs and all verdicts are unchanged. The
layout correction does not retrospectively qualify 5d579a20. New exact-SHA hosted
checks and fresh final G1–G4 execution remain required.
