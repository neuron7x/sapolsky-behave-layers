# CSCA-03 calibration timeout

The original 32-seed ×64-row/context calibration exceeded the execution window before emitting an authoritative result. No PRIMARY data had been executed. The preregistered clause permitting a lower fail-closed row count before PRIMARY was used to freeze `rows_per_context=8` for all cohorts. The timed-out attempt has no scientific authority.
