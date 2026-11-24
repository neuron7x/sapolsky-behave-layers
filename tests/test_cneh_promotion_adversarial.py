"""Independent adversarial controls against a previously green promotion guard."""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import cneh_history_guard as history
from scripts import cneh_promotion_gate as g

GATES=("MULTISCALE_COHERENCE","DETERMINISTIC_REPLAY","EVIDENCE_INTEGRITY")
STATES=("PASS","FAIL","NOT_TESTED","UNKNOWN","INVALID")
FLAG="scientific_promotion_authorized"
DENIED=(g.PromotionViolation,history.HistoryViolation)


class IndependentAuthorityTests(unittest.TestCase):
    def test_independent_lattice_oracle(self):
        self.assertEqual(tuple(g.GATES),GATES)
        self.assertEqual(tuple(g.STATUSES),STATES)
        for values in itertools.product(STATES,repeat=3):
            answer=g.necessary_gates(dict(zip(GATES,values,strict=True)))
            expected=[name for name,value in zip(GATES,values,strict=True) if value!="PASS"]
            self.assertIs(answer["necessary_gates_pass"],not expected)
            self.assertEqual(answer["blocking_gates"],expected)

    def test_single_missing_gate_blocks(self):
        for missing in GATES:
            values={k:"PASS" for k in GATES if k!=missing}
            self.assertIs(g.necessary_gates(values)["necessary_gates_pass"],False)
            self.assertEqual(g.necessary_gates(values)["blocking_gates"],[missing])

    def test_no_authority_even_with_green_receipt(self):
        with patch.dict(g.RECORDS,{"CNEH-TEST":{"gates":dict.fromkeys(GATES,"PASS")}}):
            result=g.decision("CNEH-TEST")
        self.assertIs(result[FLAG],False)
        self.assertEqual(result["scientific_promotion"],"BLOCKED")
        self.assertEqual(result["authorization_blocker"],"NO_AUTHENTICATED_PROMOTION_ISSUER")

    def test_returned_record_cannot_change_registry(self):
        record=g.decision("CNEH-EXP-05")
        try:
            record["historical_record"]["gates"]["DETERMINISTIC_REPLAY"]="PASS"
            self.assertEqual(g.decision("CNEH-EXP-05")["gates"]["DETERMINISTIC_REPLAY"],"FAIL")
        finally:
            # A deliberately vulnerable candidate must not poison later tests.
            g.RECORDS["CNEH-EXP-05"]["gates"]["DETERMINISTIC_REPLAY"]="FAIL"

    def test_json_exponent_overflow_denied(self):
        for raw in (b'{"x":1e400}',b'{"x":-1e400}',b'{"a":[{"x":1e10000}]}'):
            with self.subTest(raw=raw),self.assertRaises(g.PromotionViolation):
                g.strict_json(raw)
        self.assertEqual(g.strict_json(b'{"x":1e2}'),{"x":100.})

    def test_programmatic_nonfinite_verdict_denied(self):
        with self.assertRaises(g.PromotionViolation):
            g.check_verdict("CNEH-EXP-05",{"experiment":"CNEH-EXP-05",FLAG:False,"x":[float("inf")]})

    def test_nested_authority_and_bool_type(self):
        for field,value in ((FLAG,0),(FLAG,None),("scientific_promotion","PASS"),("SCIENTIFIC_PROMOTION","AUTHORIZED")):
            with self.subTest(field=field,value=value),self.assertRaises(g.PromotionViolation):
                g.check_verdict("CNEH-EXP-05",{"experiment":"CNEH-EXP-05",FLAG:False,
                                              "nested":[{"result":{field:value}}]})

    def test_literal_assignment_variants_denied(self):
        for code in (
            "x['scientific_promotion_authorized'], other = True, 0",
            "(scientific_promotion_authorized := True)",
            "del x['scientific_promotion_authorized']",
            "setattr(x,'scientific_promotion_authorized',True)",
            "delattr(x,'scientific_promotion_authorized')",
        ):
            with self.subTest(code=code),self.assertRaises(g.PromotionViolation):
                g.check_source(code,"adversarial_fixture.py")

    def test_subject_binding_and_identifier(self):
        for name in ("CNEH-EXP-05 ", "cneh-exp-05", "CNEH-", "CNEH-EXP-05/../x"):
            with self.assertRaises(g.PromotionViolation):
                g.decision(name)
        with self.assertRaises(g.PromotionViolation):
            g.check_verdict("CNEH-EXP-05",{"experiment":"CNEH-EXP-04G",FLAG:False})


class RealGitEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="cneh-adversarial-")
        self.addCleanup(temp.cleanup)
        self.repo=Path(temp.name)
        self.git("init","-q")
        self.git("config","user.name","CNEH Test Fixture")
        self.git("config","user.email","fixture@example.invalid")
        self.git("config","commit.gpgsign","false")
        self.parent_paths=["experiments/cneh_exp_04g/run.py","experiments/cneh_exp_05/run.py"]
        self.future="experiments/cneh_exp_future/run.py"
        self.manifest="experiments/cneh_exp_future/manifest.json"
        for name in self.parent_paths+[self.future]:
            self.write(name,'result={"scientific_promotion_authorized":False}\n')
        self.write(self.manifest,json.dumps({FLAG:False})+"\n")
        self.git("add",".")
        self.git("commit","-qm","fixture baseline")
        self.base=self.git("rev-parse","HEAD")
        p=patch.object(g,"BASE",self.base)
        p.start()
        self.addCleanup(p.stop)

    def git(self,*args):
        return subprocess.run(["git","-C",str(self.repo),*args],check=True,
                              capture_output=True,text=True).stdout.strip()

    def write(self,name,content):
        path=self.repo/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content,encoding="utf-8")
        return path

    def test_clean_fixture_positive_control(self):
        try:
            report=g.audit_repository(self.repo)
        except DENIED as exc:
            # A clean, authenticated fixture must be admitted. A typed denial
            # is an observable contract violation; unrelated exceptions still
            # remain unittest errors, never mutation kills.
            self.fail(f"valid evidence fixture rejected: {exc}")
        self.assertEqual(report["engineering_gate"],"PASS")
        self.assertIs(report[FLAG],False)
        self.assertEqual(report["source_files"],3)
        self.assertEqual(report["json_files"],1)

    def test_hidden_assume_unchanged_history_tamper(self):
        name=self.parent_paths[0]
        self.git("update-index","--assume-unchanged",name)
        self.write(name,'result={"scientific_promotion_authorized":False}\n# altered physical implementation\n')
        self.assertEqual(self.git("diff","--name-only",self.base,"--",name),"")
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_hidden_skip_worktree_history_tamper(self):
        name=self.parent_paths[1]
        self.git("update-index","--skip-worktree",name)
        self.write(name,'result={"scientific_promotion_authorized":False}\n# altered protocol code\n')
        self.assertEqual(self.git("diff","--name-only",self.base,"--",name),"")
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_anchored_roster_not_extendable(self):
        path="experiments/cneh_exp_04g/new.py"
        self.write(path,'result={"scientific_promotion_authorized":False}\n')
        self.git("add",path)
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_reconstructed_same_tree_unrelated_history_denied(self):
        tree=self.git("rev-parse","HEAD^{tree}")
        orphan=self.git("commit-tree",tree,"-m","unrelated identical tree")
        self.git("update-ref","HEAD",orphan,self.base)
        self.assertEqual(self.git("diff","--name-only",self.base),"")
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_future_literal_positive_denied(self):
        self.write(self.future,'result={"scientific_promotion_authorized":True}\n')
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_future_nested_positive_json_denied(self):
        self.write(self.manifest,json.dumps({FLAG:False,"nested":[{FLAG:True}]}))
        with self.assertRaises(DENIED):
            g.audit_repository(self.repo)

    def test_tracked_symlink_denied_even_with_safe_contents(self):
        target=self.write("safe.py",'result={"scientific_promotion_authorized":False}\n')
        path=self.repo/self.future
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises((g.PromotionViolation,history.HistoryViolation,OSError)):
            g.audit_repository(self.repo)
