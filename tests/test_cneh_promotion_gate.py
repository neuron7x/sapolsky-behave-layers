"""Fail-closed promotion boundary falsifiers."""
import itertools
import unittest

from scripts import cneh_promotion_gate as g


class PromotionGateTests(unittest.TestCase):
    def test_entire_lattice(self):
        for values in itertools.product(g.STATUSES,repeat=3):
            result=g.necessary_gates(dict(zip(g.GATES,values,strict=True)))
            self.assertEqual(result["necessary_gates_pass"],all(v=="PASS" for v in values))
            self.assertEqual(result["blocking_gates"],[k for k,v in zip(g.GATES,values,strict=True) if v!="PASS"])

    def test_missing_extra_malformed_never_pass(self):
        for values in ({},None,[],{"MULTISCALE_COHERENCE":"PASS"},
                       {**dict.fromkeys(g.GATES,"PASS"),"extra":"PASS"},
                       dict.fromkeys(g.GATES,True),dict.fromkeys(g.GATES,"pass"),
                       dict.fromkeys(g.GATES,[])):
            self.assertFalse(g.necessary_gates(values)["necessary_gates_pass"])

    def test_historical_dispositions_and_unknown_default(self):
        old=g.decision("CNEH-EXP-04G")
        self.assertEqual(old["gates"]["MULTISCALE_COHERENCE"],"NOT_TESTED")
        self.assertEqual(old["gates"]["DETERMINISTIC_REPLAY"],"NOT_TESTED")
        self.assertEqual(old["historical_record"]["same_worker_replay"],"PASS")
        self.assertEqual(g.decision("CNEH-EXP-05")["gates"]["DETERMINISTIC_REPLAY"],"FAIL")
        self.assertEqual(g.decision("CNEH-EXP-FUTURE")["blocking_gates"],list(g.GATES))

    def test_necessary_gates_not_sufficient(self):
        self.assertTrue(g.necessary_gates(dict.fromkeys(g.GATES,"PASS"))["necessary_gates_pass"])
        from unittest.mock import patch
        with patch.dict(g.RECORDS,{"CNEH-TEST":{"gates":dict.fromkeys(g.GATES,"PASS")}}):
            result=g.decision("CNEH-TEST")
        self.assertTrue(result["necessary_gates_pass"])
        self.assertFalse(result[g.FLAG])
        self.assertEqual(result["scientific_promotion"],"BLOCKED")

    def test_negative_evidence_admission(self):
        result=g.check_verdict("CNEH-EXP-04G",{"experiment":"CNEH-EXP-04G",g.FLAG:False,
                                              "all_instrument_checks_passed":True})
        self.assertEqual(result["verdict_admission"],"NEGATIVE_EVIDENCE_ONLY")
        self.assertFalse(result[g.FLAG])

    def test_forged_green_verdict_denied(self):
        for value in (True,1,"false",None):
            with self.assertRaises(g.PromotionViolation):
                g.check_verdict("CNEH-EXP-04G",{"experiment":"CNEH-EXP-04G",g.FLAG:value,
                                               "gates":dict.fromkeys(g.GATES,"PASS")})
        with self.assertRaises(g.PromotionViolation):
            g.check_verdict("CNEH-EXP-04G",{"experiment":"CNEH-EXP-05",g.FLAG:False})
        with self.assertRaises(g.PromotionViolation):
            g.check_verdict("CNEH-EXP-04G",{"experiment":"CNEH-EXP-04G"})

    def test_nested_positive_and_duplicate_json_denied(self):
        with self.assertRaises(g.PromotionViolation):
            g.reject_positive_claims({"nested":[{g.FLAG:True}]})
        with self.assertRaises(g.PromotionViolation):
            g.strict_json(b'{"scientific_promotion_authorized":true,"scientific_promotion_authorized":false}')
        with self.assertRaises(g.PromotionViolation):
            g.strict_json(b'{"x":NaN}')

    def test_direct_source_mutants(self):
        cases=[
            "x={'scientific_promotion_authorized':True}",
            "x={'scientific_promotion_authorized':all(gates)}",
            "x.update(scientific_promotion_authorized=True)",
            "x['scientific_promotion_authorized']=True",
            "x.scientific_promotion_authorized=True",
            "scientific_promotion_authorized=True",
            "x['scientific_promotion_authorized'] |= True",
        ]
        for source in cases:
            with self.subTest(source=source),self.assertRaises(g.PromotionViolation):
                g.check_source(source,"fixture.py")
        self.assertEqual(g.check_source("x={'scientific_promotion_authorized':False}","fixture.py"),1)
        self.assertEqual(g.check_source("if x['scientific_promotion_authorized'] is not False: raise ValueError()","fixture.py"),0)

    def test_scientific_request_is_nonzero(self):
        import contextlib
        import io
        import sys
        from unittest.mock import patch
        with patch.object(sys,"argv",["gate","promotion","--experiment","CNEH-EXP-04G"]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.main(),2)
