"""Fail-closed CNEH scientific-promotion boundary; engineering integration is separate.

This lineage has no authenticated positive scientific-promotion issuer. The
three necessary gates are not sufficient to grant positive authority. Historical
experiments remain byte-exact; their scoped receipts must not be inflated.
"""
from __future__ import annotations

import argparse
import ast
import itertools
import json
from pathlib import Path
import re
import sys

from scripts.cneh_history_guard import git, require_commit, regular_file

ROOT=Path(__file__).resolve().parents[1]
GATES=("MULTISCALE_COHERENCE","DETERMINISTIC_REPLAY","EVIDENCE_INTEGRITY")
STATUSES=("PASS","FAIL","NOT_TESTED","UNKNOWN","INVALID")
FLAG="scientific_promotion_authorized"
BASE="8cd266c51d9b0ae495e42557dd5da2d5a443dbbd"
G_HEAD="63846dba16b9a2646919bb6c6ce329de8a1a9d1b"
FIVE_HEAD="8c9b71f366af32fdfc5ffd8618198b4fe22af244"

# These are scoped, historically observed dispositions, not user-provided
# receipts and not a positive authorization mechanism. PASS for evidence means
# the recorded hosted manifest/replay and artifact metadata check passed, not
# fresh local materialization. Same-worker replay is not domain portability.
RECORDS={
    "CNEH-EXP-04G":{
        "head":G_HEAD,"merge":"711315bdbe6ff3f02030db572b58710e9d3f8365",
        "run":45325910845,"artifact":14889488512,
        "artifact_sha256":"03a5731775b7def8a9f09a9aab806737253a5431ea5e08ea10360ec1cf58b103",
        "gates":{"MULTISCALE_COHERENCE":"NOT_TESTED","DETERMINISTIC_REPLAY":"NOT_TESTED","EVIDENCE_INTEGRITY":"PASS"},
        "same_worker_replay":"PASS","cross_worker_replay":"NOT_TESTED",
        "scope":"A/B/C mechanism separation; no multiscale admission or execution-domain portability certificate",
    },
    "CNEH-EXP-05":{
        "head":FIVE_HEAD,"merge":BASE,"run":45327662515,"artifact":14890028886,
        "artifact_sha256":"db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8",
        "gates":{"MULTISCALE_COHERENCE":"NOT_TESTED","DETERMINISTIC_REPLAY":"FAIL","EVIDENCE_INTEGRITY":"PASS"},
        "same_worker_replay":"PASS","cross_worker_replay":"FAIL",
        "scope":"EXP05A forensic job 138234069147: unchanged runner differs from sealed native state on 16/16 DUAL episodes; EXP05M is diagnostic only",
    },
}


class PromotionViolation(ValueError):
    """A claim or audit input violates the immutable promotion boundary."""


def validate_id(experiment: str) -> None:
    if not isinstance(experiment,str) or re.fullmatch(r"CNEH-[A-Z0-9][A-Z0-9_-]{0,80}",experiment) is None:
        raise PromotionViolation("invalid CNEH experiment identifier")


def normalize(statuses: object) -> dict[str,str]:
    if not isinstance(statuses,dict) or any(k not in GATES for k in statuses):
        return dict.fromkeys(GATES,"INVALID")
    return {k:statuses[k] if k in statuses and type(statuses[k]) is str and statuses[k] in STATUSES
            else "INVALID" if k in statuses else "NOT_TESTED" for k in GATES}


def necessary_gates(statuses: object) -> dict:
    result=normalize(statuses)
    blockers=[k for k in GATES if result[k]!="PASS"]
    return {"gates":result,"necessary_gates_pass":not blockers,"blocking_gates":blockers}


def decision(experiment: str) -> dict:
    validate_id(experiment)
    record=RECORDS.get(experiment)
    checks=necessary_gates(record["gates"] if record is not None else {})
    # No trust-on-first-use or caller-supplied PASS. Positive authority requires
    # a future, separately audited issuer binding all three actual receipts to
    # the same subject, protocol, evidence, domain and scientific claim.
    return {"schema":"cneh-promotion-guard-v1","experiment":experiment,**checks,
            "scientific_promotion":"BLOCKED",FLAG:False,
            "authorization_blocker":"NO_AUTHENTICATED_PROMOTION_ISSUER",
            "historical_record":record,
            "engineering_integration":"SEPARATE_GATE_NOT_PROMOTION"}


def strict_json(raw: bytes) -> object:
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:
                raise PromotionViolation("duplicate JSON key")
            result[k]=v
        return result
    def nonfinite(token):
        raise PromotionViolation("nonfinite JSON token: "+token)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)


def reject_positive_claims(value: object) -> None:
    if isinstance(value,dict):
        for k,v in value.items():
            if k==FLAG and v is not False:
                raise PromotionViolation("positive, ambiguous or malformed scientific promotion flag")
            if k in ("scientific_promotion","SCIENTIFIC_PROMOTION") and v!="BLOCKED":
                raise PromotionViolation("unqualified scientific promotion disposition")
            reject_positive_claims(v)
    elif isinstance(value,list):
        for v in value:
            reject_positive_claims(v)


def check_verdict(experiment: str, value: object) -> dict:
    result=decision(experiment)
    if not isinstance(value,dict) or value.get("experiment")!=experiment or value.get(FLAG) is not False:
        raise PromotionViolation("verdict must identify exact experiment and explicitly deny promotion")
    reject_positive_claims(value)
    return {"verdict_admission":"NEGATIVE_EVIDENCE_ONLY",**result}


def literal_key(node: ast.AST | None) -> bool:
    return isinstance(node,ast.Constant) and node.value==FLAG


def literal_false(node: ast.AST) -> bool:
    return isinstance(node,ast.Constant) and node.value is False


def check_source(source: str, name: str) -> int:
    """Reject direct non-false writes; this is not arbitrary-code proof."""
    tree=ast.parse(source,filename=name)
    count=0
    def check(value,lineno):
        nonlocal count
        count+=1
        if not literal_false(value):
            raise PromotionViolation(f"{name}:{lineno}: direct promotion write must be literal False")
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            for key,value in zip(node.keys,node.values,strict=True):
                if literal_key(key):
                    check(value,node.lineno)
        elif isinstance(node,ast.keyword) and node.arg==FLAG:
            check(node.value,node.lineno)
        elif isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            for target in targets:
                if (isinstance(target,ast.Subscript) and literal_key(target.slice)
                    or isinstance(target,ast.Attribute) and target.attr==FLAG
                    or isinstance(target,ast.Name) and target.id==FLAG):
                    if isinstance(node,ast.AugAssign) or node.value is None:
                        raise PromotionViolation(f"{name}:{node.lineno}: ambiguous promotion write")
                    check(node.value,node.lineno)
    return count


def audit_repository(repo: Path) -> dict:
    repo=repo.resolve()
    if Path(git(repo,"rev-parse","--show-toplevel").decode().strip()).resolve()!=repo:
        raise PromotionViolation("repository root required")
    head=git(repo,"rev-parse","HEAD").decode().strip()
    require_commit(repo,BASE,head)
    # Byte-exact historical G and 05 code/protocol lineage. Governance is
    # additive, not a rewrite of already sealed experiment implementation.
    git(repo,"diff","--exit-code",BASE,"--","experiments/cneh_exp_04g","experiments/cneh_exp_05")
    paths=git(repo,"ls-files","-z","--","experiments").decode().split("\0")
    source_files=json_files=writes=0
    for name in sorted(set(paths)-{""}):
        path=Path(name)
        if len(path.parts)<3 or not path.parts[1].startswith("cneh_exp_"):
            continue
        if path.suffix not in (".py",".json"):
            continue
        actual=regular_file(repo,name)
        if path.suffix==".py":
            writes+=check_source(actual.read_text(encoding="utf-8"),name)
            source_files+=1
        else:
            reject_positive_claims(strict_json(actual.read_bytes()))
            json_files+=1
    if not source_files or not json_files or not writes:
        raise PromotionViolation("empty CNEH authority scan")
    if git(repo,"rev-parse","HEAD").decode().strip()!=head:
        raise PromotionViolation("HEAD changed during audit")
    # Exhaustively exercise the finite disposition lattice, not just all PASS.
    for values in itertools.product(STATUSES,repeat=len(GATES)):
        expected=all(v=="PASS" for v in values)
        if necessary_gates(dict(zip(GATES,values,strict=True)))["necessary_gates_pass"]!=expected:
            raise PromotionViolation("promotion conjunction falsified")
    return {"schema":"cneh-promotion-repository-audit-v1","engineering_gate":"PASS","head_sha":head,
            "source_files":source_files,"json_files":json_files,"direct_negative_writes":writes,
            "status_combinations":len(STATUSES)**len(GATES),
            "decisions":[decision(x) for x in RECORDS],
            "unregistered_contour_default":decision("CNEH-UNREGISTERED"),
            FLAG:False,"scientific_promotion":"BLOCKED"}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    audit=sub.add_parser("audit")
    audit.add_argument("--repo",type=Path,default=ROOT)
    for name in ("check-verdict","promotion"):
        cmd=sub.add_parser(name)
        cmd.add_argument("--experiment",required=True)
        if name=="check-verdict":
            cmd.add_argument("--verdict",type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=="audit":
            result=audit_repository(args.repo)
        elif args.command=="check-verdict":
            if args.verdict.is_symlink() or not args.verdict.is_file():
                raise PromotionViolation("verdict must be a regular file")
            result=check_verdict(args.experiment,strict_json(args.verdict.read_bytes()))
        else:
            result=decision(args.experiment)
        print(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False))
        return 2 if args.command=="promotion" else 0
    except (OSError,ValueError,TypeError,SyntaxError) as exc:
        print(json.dumps({"engineering_gate":"FAIL","scientific_promotion":"BLOCKED",
                          FLAG:False,"error":str(exc)},sort_keys=True),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
