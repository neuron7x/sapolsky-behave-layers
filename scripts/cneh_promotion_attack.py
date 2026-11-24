"""Triple independent mutation campaigns against the CNEH promotion gate.

A mutant is killed only by a failed assertion in an otherwise executable suite.
Import errors, timeouts and empty/partial suites are invalid, never kills.
The original green suite and exact previous implementation are retained as
negative controls. Every candidate is executed in its own Python process.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL="f8677f5b744e7a3e826f167b6b8abfc4045ffcc9"
GUARD="scripts/cneh_promotion_gate.py"
BASE_TEST="tests/test_cneh_promotion_gate.py"
EXTRA_TEST="tests/test_cneh_promotion_adversarial.py"
MUTANTS=(
    ("L01_OMIT_MULTISCALE","blockers=[k for k in GATES if result[k]!=\"PASS\"]",
     "blockers=[k for k in GATES if result[k]!=\"PASS\" and k!=\"MULTISCALE_COHERENCE\"]"),
    ("L02_OMIT_REPLAY","blockers=[k for k in GATES if result[k]!=\"PASS\"]",
     "blockers=[k for k in GATES if result[k]!=\"PASS\" and k!=\"DETERMINISTIC_REPLAY\"]"),
    ("L03_OMIT_INTEGRITY","blockers=[k for k in GATES if result[k]!=\"PASS\"]",
     "blockers=[k for k in GATES if result[k]!=\"PASS\" and k!=\"EVIDENCE_INTEGRITY\"]"),
    ("L04_OR_INSTEAD_OF_AND",'"necessary_gates_pass":not blockers','"necessary_gates_pass":len(blockers)<3'),
    ("L05_MISSING_IS_PASS",'else "INVALID" if k in statuses else "NOT_TESTED" for k in GATES}',
     'else "INVALID" if k in statuses else "PASS" for k in GATES}'),
    ("L06_SHRINK_SELF_DERIVED_ORACLE",'STATUSES=("PASS","FAIL","NOT_TESTED","UNKNOWN","INVALID")',
     'STATUSES=("PASS","FAIL","NOT_TESTED","INVALID")'),
    ("A01_GREEN_EQUALS_AUTHORITY",'"scientific_promotion":"BLOCKED",FLAG:False,\n            "authorization_blocker"',
     '"scientific_promotion":"BLOCKED",FLAG:checks["necessary_gates_pass"],\n            "authorization_blocker"'),
    ("A02_DROP_ISSUER_BLOCKER",'"authorization_blocker":"NO_AUTHENTICATED_PROMOTION_ISSUER"',
     '"authorization_blocker":"NONE"'),
    ("A03_UNBOUND_SUBJECT",'or value.get("experiment")!=experiment or value.get(FLAG) is not False:',
     'or value.get(FLAG) is not False:'),
    ("A04_BOOL_INTEGER_ALIAS",'if k==FLAG and v is not False:','if k==FLAG and v != False:'),
    ("A05_SKIP_NESTED_CLAIMS",'            reject_positive_claims(v)\n    elif isinstance(value,list):',
     '            pass\n    elif isinstance(value,list):'),
    ("A06_ACCEPT_POSITIVE_DISPOSITION",'and v!="BLOCKED":','and v not in ("BLOCKED","PASS"):'),
    ("A07_CLI_PROMOTION_ZERO",'return 2 if args.command=="promotion" else 0','return 0'),
    ("I01_DUPLICATE_LAST_WINS",'object_pairs_hook=pairs','object_pairs_hook=dict'),
    ("I02_EXPONENT_OVERFLOW",'parse_float=finite_float','parse_float=float'),
    ("I03_DIRECT_NONFINITE",'elif type(value) is float and not math.isfinite(value):','elif False:'),
    ("I04_MUTABLE_REGISTRY_ALIAS",'"historical_record":copy.deepcopy(record),','"historical_record":record,'),
    ("I05_IGNORE_HISTORICAL_BYTES",'    verify_anchored_lineage(repo)\n','    pass\n'),
    ("I06_IGNORE_ANCESTRY",'    require_commit(repo,BASE,head)\n','    pass\n'),
    ("I07_FOLLOW_SYMLINK",'        actual=regular_file(repo,name)\n','        actual=repo/name\n'),
    ("I08_IGNORE_JSON_AUTHORITY",'            reject_positive_claims(strict_json(actual.read_bytes()))',
     '            strict_json(actual.read_bytes())'),
    ("I09_IGNORE_SOURCE_AUTHORITY",'writes+=check_source(actual.read_text(encoding="utf-8"),name)','writes+=1'),
    ("I10_UNCHECKED_LITERAL_WRITE",'        if not literal_false(value):','        if False:'),
    ("I11_UNCHECKED_DESTRUCTURING",'return any(authority_target(x) for x in node.elts)','return False'),
)


def require(condition,reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    require(spec is not None and spec.loader is not None,"missing module loader")
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def flatten(suite):
    out=[]
    for item in suite:
        if isinstance(item,unittest.TestSuite):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out


def probe(candidate,suite_name,seed):
    import scripts
    module=load("scripts.cneh_promotion_gate",candidate)
    scripts.cneh_promotion_gate=module
    suite=unittest.TestSuite()
    for name in (BASE_TEST,EXTRA_TEST) if suite_name=="expanded" else (BASE_TEST,):
        test=load("isolated_"+Path(name).stem,ROOT/name)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test))
    ordered=flatten(suite)
    random.Random(seed).shuffle(ordered)
    expected=len(ordered)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=0).run(unittest.TestSuite(ordered))
    return {"tests":result.testsRun,"expected":expected,
            "failures":[x.id() for x,_ in result.failures],
            "errors":[{"test":x.id(),"traceback":msg} for x,msg in result.errors],
            "skipped":len(result.skipped),"expected_failures":len(result.expectedFailures),
            "unexpected_successes":len(result.unexpectedSuccesses)}


def classification(result):
    if (result["tests"]!=result["expected"] or result["tests"]<9 or result["errors"]
        or result["skipped"] or result["expected_failures"] or result["unexpected_successes"]):
        return "INVALID"
    return "KILLED" if result["failures"] else "SURVIVED"


def execute(source,suite,seed,folder):
    candidate=folder/"candidate.py"
    candidate.write_text(source,encoding="utf-8")
    proc=subprocess.run([sys.executable,"-B","-m","scripts.cneh_promotion_attack","probe",
                         "--candidate",str(candidate),"--suite",suite,"--seed",str(seed)],
                         cwd=ROOT,capture_output=True,text=True,timeout=150,check=False)
    require(proc.returncode==0,"probe crashed: "+proc.stderr[-3000:])
    result=json.loads(proc.stdout)
    return {**result,"disposition":classification(result)}


def git_bytes(*args):
    return subprocess.run(["git","-C",str(ROOT),*args],check=True,capture_output=True).stdout


def campaign(seed):
    original=git_bytes("show",ORIGINAL+":"+GUARD)
    test_original=git_bytes("show",ORIGINAL+":"+BASE_TEST)
    require((ROOT/BASE_TEST).read_bytes()==test_original,"original green suite was rewritten")
    current=(ROOT/GUARD).read_bytes()
    source=current.decode()
    records=[]
    with tempfile.TemporaryDirectory(prefix="cneh-mutation-") as tmp:
        folder=Path(tmp)
        old_green=execute(original.decode(),"original",seed,folder)
        old_attack=execute(original.decode(),"expanded",seed,folder)
        new_clean=execute(source,"expanded",seed,folder)
        for name,old,new in MUTANTS:
            require(source.count(old)==1,"mutation anchor not unique: "+name)
            changed=source.replace(old,new,1)
            compile(changed,name,"exec")
            old_suite=execute(changed,"original",seed,folder)
            new_suite=execute(changed,"expanded",seed,folder)
            records.append({"mutant":name,"sha256":sha(changed.encode()),
                            "original_suite":old_suite,"expanded_suite":new_suite})
    complete=len(records)==len(MUTANTS)
    killed=sum(row["expanded_suite"]["disposition"]=="KILLED" for row in records)
    old_killed=sum(row["original_suite"]["disposition"]=="KILLED" for row in records)
    survivors=[row["mutant"] for row in records if row["original_suite"]["disposition"]=="SURVIVED"]
    success=(complete and old_green["disposition"]=="SURVIVED"
             and old_attack["disposition"]=="KILLED" and new_clean["disposition"]=="SURVIVED"
             and killed==len(MUTANTS))
    return {"schema":"cneh-promotion-adversarial-campaign-v1","seed":seed,
            "python":sys.version.split()[0],"original_commit":ORIGINAL,
            "original_guard_sha256":sha(original),"current_guard_sha256":sha(current),
            "original_tests_sha256":sha(test_original),"expanded_tests_sha256":sha((ROOT/EXTRA_TEST).read_bytes()),
            "original_green_baseline":old_green,"original_implementation_under_expanded_attack":old_attack,
            "hardened_clean_baseline":new_clean,"mutant_count":len(MUTANTS),
            "original_suite_killed":old_killed,"original_suite_survivors":survivors,
            "expanded_suite_killed":killed,"mutants":records,"all_attacks_pass":success,
            "scientific_promotion_authorized":False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    cmd=sub.add_parser("probe")
    cmd.add_argument("--candidate",type=Path,required=True)
    cmd.add_argument("--suite",choices=("original","expanded"),required=True)
    cmd.add_argument("--seed",type=int,required=True)
    run=sub.add_parser("campaign")
    run.add_argument("--seed",type=int,required=True)
    run.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.command=="probe":
        print(json.dumps(probe(args.candidate,args.suite,args.seed),sort_keys=True))
        return 0
    require(not args.out.exists() and not args.out.is_symlink(),"immutable campaign output")
    report=campaign(args.seed)
    with args.out.open("xb") as output:
        output.write((json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode())
    summary={k:v for k,v in report.items() if k!="mutants"}
    summary["expanded_failed_mutants"]=[{"mutant":row["mutant"],"result":row["expanded_suite"]}
                                        for row in report["mutants"] if row["expanded_suite"]["disposition"]!="KILLED"]
    print(json.dumps(summary,sort_keys=True,separators=(",",":"),allow_nan=False))
    return 0 if report["all_attacks_pass"] else 2


if __name__=="__main__":
    raise SystemExit(main())
