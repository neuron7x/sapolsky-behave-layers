# A4: executable tooling provenance remediation

Engineering amendment, 2026-11-23; implements the owner's CNEH-LQP-43-v1.0
supply-chain requirement. No scientific specification, threshold, seed, comparator,
raw PRIMARY outcome or historical evidence is changed.

The current quality workflow installs an unversioned pip upgrade and installs
version-pinned direct development tools without a transitive hash lock. Other
required workflows bootstrap uv by a version-only install, and dependency-audit
uses a version-pinned pip-audit environment with unlocked transitive packages.
These boundaries cannot be described as hash-authenticated executable downloads.
The existing CNEH numerical/BN-Syn environment already has a seven-package hash lock.

Before final qualification, replace the affected required-workflow bootstrap,
quality/full-gate development install and audit-tool install with explicit binary
artifact hashes and complete transitive pins. Preserve all existing direct tool
versions and runtime uv.lock constraints. Remove the unpinned pip upgrade; retain
all lint/type/coverage/mutation/security gates and thresholds. Do not modify main,
external repositories, global Python/Git settings or the scientific frozen files.

Validate clean isolated installs, recorded versions and imported entrypoints;
reject a deliberately wrong artifact hash. Check all affected workflow syntax and
exercise the same full repository gates in hosted CI. Pin the resulting workflow
source hashes in a separate version of the required-check manifest before the final
qualification run. The prior manifest remains preserved in Git history; its old
source hashes must not be presented as authenticating the new workflows.

The trust boundary includes the pinned official GitHub Actions and runner-supplied
Python/bootstrap installer. No measured tool version or wheel checksum is a claim
of vulnerability freedom or of a hardware-rooted execution attestation.
