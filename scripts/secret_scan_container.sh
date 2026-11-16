#!/bin/sh
# The pinned scanner can return zero after Git errors; its exit status alone
# cannot establish that any history was scanned.
set -eu

test "$(git rev-parse --verify HEAD)" = "$1"
commits="$(git rev-list --count --all)"
test "$commits" -gt 0
git fsck --full --no-reflogs --no-dangling
printf 'SECRET-SCAN-GIT-PREFLIGHT: %s commits\n' "$commits"

scan_log="$(mktemp)"
trap 'rm -f "$scan_log"' EXIT
scan_exit=0
gitleaks git --redact --no-banner --no-color --exit-code 1 --log-opts=--all >"$scan_log" 2>&1 || scan_exit=$?
cat "$scan_log"
if [ "$scan_exit" -ne 0 ]; then
    exit "$scan_exit"
fi

# --no-color gives the pinned v8.28.0 logger an unambiguous level/summary format.
# Reject error logs, absent/duplicate summaries and zero scanned commits.
if ! awk '
    $2 ~ /^(ERR|FTL|PNC)$/ { errors = 1 }
    NF == 5 && $2 == "INF" && $3 ~ /^[0-9]+$/ && $4 == "commits" && $5 == "scanned." {
        summaries++
        scanned = $3
    }
    END { exit !(errors == 0 && summaries == 1 && scanned > 0) }
' "$scan_log"; then
    printf '%s\n' 'SECRET-SCAN: scanner errors or missing nonzero scan evidence' >&2
    exit 1
fi
