# Archival and persistent-identifier plan

The public [CWC repository](https://github.com/neuron7x/sapolsky-behave-layers) exposes Git
history and scoped Actions evidence. Git commit/tree and artifact digest identify
an exact object while it is accessible. As of the documentation audit, no GitHub
Release is published. Hosted experiment artifacts may expire. The archival
identifier and external restoration receipt remain open.

A citeable release requires a tagged reviewed commit, explicit source and evidence
rosters, archive hashes, permission-aware retention and a clean restoration from
the published package. Compare every restored tracked path, blob and mode against
the intended tree. Retain failed restores. The snapshot builder uses a clean tracked checkout, stages provenance-bound archives
from the commit, and publishes into a new or empty directory. The independent
[restoration checker](../../scripts/check_release_restoration.py) repeats the build
and compares restored Git blobs and executable modes. Public release, permission
review and external scientific reproduction remain separate acceptance obligations.

Deposit only artifacts authorized for redistribution. Record the archive identifier,
release tag, commit/tree, payload digest and instructions in the citation and artifact
guide after those records exist. The [external review protocol](../risk/EXTERNAL_REVIEW_AND_INDEPENDENCE_PROTOCOL.md)
specifies the separate reproduction obligation.
