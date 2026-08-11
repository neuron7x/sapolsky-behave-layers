import json
import numpy as np
import pytest
from experiments.cwc_flagship_route_02 import core
from experiments.cwc_flagship_route_02.semantic_gate import self_test


def test_seed_contract_and_hashes():
    core.validate_seed_contract(); assert len(core.verify_data_hashes()) == 12


def test_r2_windows_are_disjoint_from_r1():
    assert core.assert_no_r1_overlap()['overlaps'] == 0


def test_fixed_frontier_same_contract_as_r1():
    f=core.flop_contract(); assert f.fixed_depth1 < f.fixed_depth2
    assert core.fixed_frontier_loss(3.0,2.0,f.fixed_depth1)==pytest.approx(3.0)


def test_policy_rejects_wrong_seed():
    fake={'experiment':core.EXPERIMENT_ID,'seed':1}
    with pytest.raises(core.ProtocolViolation):
        core.evaluate_cell([], fake, expected_seed=2)


def test_semantic_gate():
    r=self_test(); assert r['passed'] and r['killed']==r['expected']==5
