from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.p19_verifier_policy import (
    CANONICAL_POLICY_PATH,
    P19VerifierPolicyError,
    load_p19_verifier_trust_policy,
    resolve_allowed_signers,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed gate for the frozen external P19 verifier trust policy.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--policy", default=CANONICAL_POLICY_PATH)
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    try:
        policy = load_p19_verifier_trust_policy(policy_path)
        allowed = resolve_allowed_signers(policy, repository_root=root)
    except P19VerifierPolicyError as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc),
            "product_qualification_authorized": False,
        }, sort_keys=True))
        return 73

    print(json.dumps({
        "status": "PASS",
        "policy_generation": policy.policy_generation,
        "policy_digest": policy.policy_digest,
        "minimum_distinct_verifiers": policy.minimum_distinct_verifiers,
        "same_verifier_across_families_allowed": policy.same_verifier_across_families_allowed,
        "allowed_signers_path": str(allowed),
        "allowed_signers_sha256": policy.allowed_signers_sha256,
        "social_independence_machine_proven": False,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
