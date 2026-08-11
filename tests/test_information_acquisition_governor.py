from __future__ import annotations

import math

from cwc.epistemics.information_acquisition import InformationAction, select_maximin_information_action


def test_governor_selects_robust_information_per_cost_not_raw_information():
    actions=[
        InformationAction('CHEAP_REGIME',1.0,{'M1':.08,'M2':.06},'CERTIFIED_LOWER_BOUND'),
        InformationAction('EXPENSIVE_SCAN',10.0,{'M1':.30,'M2':.25},'CERTIFIED_LOWER_BOUND'),
    ]
    d=select_maximin_information_action(actions=actions,unresolved_alternatives=['M1','M2'],alpha=.01,target_power=.95,available_budget=100.0)
    assert d.action_id == 'CHEAP_REGIME'
    assert d.state == 'ACQUIRE_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE'
    assert abs(d.guaranteed_information_per_cost-.06) < 1e-12


def test_zero_rate_blocks_compute_even_if_other_alternatives_are_easy():
    actions=[
        InformationAction('PASSIVE',1.0,{'M1':.2,'M_EQ':0.0},'CERTIFIED_LOWER_BOUND'),
        InformationAction('MORE_REPLAY',.1,{'M1':1.0,'M_EQ':0.0},'CERTIFIED_LOWER_BOUND'),
    ]
    d=select_maximin_information_action(actions=actions,unresolved_alternatives=['M1','M_EQ'],alpha=.01,target_power=.95,available_budget=1e9)
    assert d.state == 'NO_IDENTIFYING_INFORMATION_CHANNEL'
    assert math.isinf(d.necessary_cost_lower_bound)
    assert 'M_EQ' in d.bottleneck_alternatives


def test_budget_veto_is_fail_closed():
    action=InformationAction('R',2.0,{'M1':.02},'CERTIFIED_LOWER_BOUND')
    d=select_maximin_information_action(actions=[action],unresolved_alternatives=['M1'],alpha=.01,target_power=.95,available_budget=100.0)
    assert d.state == 'INSUFFICIENT_INFORMATION_BUDGET'
    assert d.necessary_cost_lower_bound > 100


def test_uncertified_rate_cannot_greenlight_compute():
    action=InformationAction('GUESS',1.0,{'M1':10.0},'POINT_ESTIMATE')
    d=select_maximin_information_action(actions=[action],unresolved_alternatives=['M1'],alpha=.01,target_power=.95,available_budget=1e6)
    assert d.state == 'NO_CERTIFIED_INFORMATION_RATE'


def test_action_capacity_can_veto_even_with_large_external_budget():
    action=InformationAction('FINITE_TRACE',1.0,{'M1':.01},'CERTIFIED_LOWER_BOUND',max_units=100)
    d=select_maximin_information_action(actions=[action],unresolved_alternatives=['M1'],alpha=.01,target_power=.95,available_budget=1e6)
    assert d.state == 'ACTION_CAPACITY_BELOW_NECESSARY_INFORMATION_BOUND'
