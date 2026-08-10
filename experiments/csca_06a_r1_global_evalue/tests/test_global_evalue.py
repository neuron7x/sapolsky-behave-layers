from cwc.counterfactual.falsifiability import AlternativeComponent, FixedCheckpointCompositeEValue, InterventionDesign, NuisanceEnvelope


def test_checkpoint_threshold_and_no_optional_look():
    p=FixedCheckpointCompositeEValue(model_slope=0.0,nuisance=NuisanceEnvelope(-1,1,.5,2.5),alternative=[AlternativeComponent(.8,0,1)],alpha=.01,checkpoints_cost=(4.,8.),max_cost=8.)
    d=InterventionDesign({-1.:1,1.:1},{-1.:1.,1.:1.})
    r=p.add_block([0.,0.],d)
    assert r['checkpoint'] is False
    assert abs(p.threshold_log_e - __import__('math').log(200.0))<1e-12


def test_checkpoint_budget_fails_closed():
    p=FixedCheckpointCompositeEValue(model_slope=0.0,nuisance=NuisanceEnvelope(-1,1,.5,2.5),alternative=[AlternativeComponent(.8,0,1)],alpha=.01,checkpoints_cost=(2.,),max_cost=2.)
    d=InterventionDesign({-1.:1,1.:1},{-1.:1.,1.:1.})
    p.add_block([0.,0.],d)
    try:p.add_block([0.,0.],d)
    except RuntimeError: pass
    else: raise AssertionError('must reject budget overflow')
