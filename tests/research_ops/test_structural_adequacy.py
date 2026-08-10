from __future__ import annotations

from dataclasses import replace

import numpy as np

from cwc.counterfactual.model import FeatureTerm, FittedCounterfactualModel
from cwc.counterfactual.structural_adequacy import (
    EmpiricalInterventionProbe,
    best_family_audit,
    context_effect_audits,
    interventional_divergence_audit,
)


def _model(coef_a=1.0, coef_c=0.0, *, family="LINEAR"):
    terms = (FeatureTerm("intercept"), FeatureTerm("A", ("A",)), FeatureTerm("C", ("C",)))
    return FittedCounterfactualModel(
        model_id="m", family=family, version="t", terms=terms,
        coefficients=(0.0, coef_a, coef_c), train_config_counts=(), train_rows=32,
    )


def _probes(true_a=1.0, true_c=0.0):
    probes=[]
    for cand,true in (("A",true_a),("C",true_c)):
        for context in (-1.0,1.0):
            for i in range(8):
                base={"A":1.0,"C":1.0,"D":-1.0,"B":1.0,"context":context}
                noise=(i-3.5)*0.002
                probes.append(EmpiricalInterventionProbe(cand,context,base,true+noise,true-noise))
    return probes


def test_idr_prefers_interventionally_correct_family():
    probes=_probes()
    good=_model(1.0,0.0,family="GOOD")
    bad=_model(0.1,0.9,family="BAD")
    audits=interventional_divergence_audit((good,bad),probes)
    assert best_family_audit(audits).family == "GOOD"
    assert {a.family:a.idr for a in audits}["BAD"] > {a.family:a.idr for a in audits}["GOOD"]


def test_context_audit_detects_sign_flip():
    probes=[]
    for context in (-1.0,1.0):
        for i in range(16):
            base={"A":1.0,"C":1.0,"D":-1.0,"B":1.0,"context":context}
            effect=context
            probes.append(EmpiricalInterventionProbe("A",context,base,effect+0.01,effect-0.01))
    audit={x.candidate:x for x in context_effect_audits(probes)}["A"]
    assert audit.sign_flip
    assert audit.effect_negative_context < 0 < audit.effect_positive_context
