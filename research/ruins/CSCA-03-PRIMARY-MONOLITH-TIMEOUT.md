# CSCA-03 monolithic PRIMARY timeout

The original monolithic 128-seed PRIMARY execution exceeded the execution window before writing an authoritative cohort artifact. The protocol was not changed; execution was partitioned into deterministic 8-seed chunks and merged in seed order. Partial monolithic output was not used.
