from cwc.counterfactual.structural_authority import (
    StructuralAdequacyEnvelope, StructuralAuthorityPolicy, decide_structural_authority,
)

P=StructuralAuthorityPolicy("t",4.0,8,16,0.1)


def e(**kw):
    base=dict(best_model_family="NONLINEAR",max_cell_idr=1.0,covered_cells=8,min_cell_support=16,max_empirical_leverage=1.0,context_shift_candidates=())
    base.update(kw)
    return StructuralAdequacyEnvelope(**base)


def test_fail_closed_order():
    assert decide_structural_authority(e(covered_cells=7),P).state=="ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE"
    assert decide_structural_authority(e(max_empirical_leverage=0.0),P).state=="FALSIFIED_NO_CAUSAL_LEVERAGE"
    assert decide_structural_authority(e(max_cell_idr=5.0),P).state=="ABSTAIN_STRUCTURAL_MISSPECIFICATION"
    assert decide_structural_authority(e(context_shift_candidates=("A",)),P).state=="CONTEXT_CONDITIONAL_ONLY"
    assert decide_structural_authority(e(),P).state=="STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC"
