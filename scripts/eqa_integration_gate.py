"""Admit only the complete same-run CWC integration roster."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path

REQUIRED_JOBS = frozenset({
    "cneh-promotion-invariants",
    "cneh-promotion-adversarial",
    "full-verification",
    "fractal-verification",
})
LOCKS = ("uv.lock", "requirements/ci-uv.lock", "requirements/cwc-dev.lock", "experiments/fractal_multiscale/uv.lock")
WORKFLOW = ".github/workflows/cwc-full-pr-gate.yml"
OID = re.compile(r"[0-9a-f]{40}")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def roster_errors(needs: object) -> list[str]:
    if not isinstance(needs, dict) or set(needs) != REQUIRED_JOBS:
        return ["required job roster is missing or differs"]
    return [
        f"{job}: required success, observed {row.get('result') if isinstance(row, dict) else None}"
        for job, row in sorted(needs.items())
        if not isinstance(row, dict) or row.get("result") != "success"
    ]


def identity_errors(
    *, event: str, checkout: str, expected_checkout: str, parents: list[str],
    head: str | None, base: str | None,
) -> list[str]:
    if not OID.fullmatch(checkout) or checkout != expected_checkout:
        return ["actual checkout differs from the workflow revision"]
    if event == "pull_request":
        if not head or not base or parents != [base, head]:
            return ["PR checkout does not bind the exact base and head parents"]
    elif event != "workflow_dispatch" or head is not None or base is not None:
        return ["unsupported workflow event or unexpected PR identity"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt: dict[str, object] = {"schema": "CWC_INTEGRATION_RECEIPT_V1", "status": "FAIL"}
    try:
        env = os.environ
        event = env["GITHUB_EVENT_NAME"]
        envelope = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        pr = envelope.get("pull_request")
        head = pr["head"]["sha"] if pr is not None else None
        base = pr["base"]["sha"] if pr is not None else None
        checkout = _git("rev-parse", "HEAD")
        tree = _git("rev-parse", "HEAD^{tree}")
        needs = json.loads(env["CWC_REQUIRED_JOB_RESULTS"])
        failures = roster_errors(needs) + identity_errors(
            event=event, checkout=checkout, expected_checkout=env["GITHUB_SHA"],
            parents=_git("show", "-s", "--format=%P", "HEAD").split(), head=head, base=base,
        )
        if _git("status", "--porcelain=v1", "--untracked-files=no"):
            failures.append("tracked checkout is dirty")
        self_test = env.get("CWC_GATE_SELF_TEST_RESULT")
        if self_test != "success":
            failures.append(f"integration predicate self-test did not pass: {self_test}")
        receipt.update(
            repository=env["GITHUB_REPOSITORY"], event=event, run_id=env["GITHUB_RUN_ID"],
            run_attempt=env["GITHUB_RUN_ATTEMPT"], workflow_ref=env["GITHUB_WORKFLOW_REF"],
            workflow_commit=env["GITHUB_WORKFLOW_SHA"], checkout=checkout, tree=tree,
            head=head, base=base, runner_os=env["RUNNER_OS"], runner_arch=env["RUNNER_ARCH"],
            receipt_python=platform.python_version(), jobs=needs, self_test=self_test,
            tracked_sha256={name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (*LOCKS, WORKFLOW)},
            failures=failures,
            status="FAIL" if failures else "PASS",
        )
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, AttributeError, TypeError) as exc:
        receipt["failures"] = [f"could not establish integration receipt: {exc}"]
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"CWC-INTEGRATION: {receipt['status']}: {receipt.get('failures', [])}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
