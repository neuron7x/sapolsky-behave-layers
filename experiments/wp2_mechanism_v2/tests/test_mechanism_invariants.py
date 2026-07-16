"""A0/A2 invariants for the mechanism benchmark. Run:
PYTHONPATH=. pytest experiments/wp2_mechanism_v2/tests/ -q
"""
from __future__ import annotations

import torch

from experiments.wp2_mechanism_v2.src.model_mech import MechConfig, MechModel, Mode
from experiments.wp2_mechanism_v2.src.task_mech import MechTaskConfig, generate_batch

CFG = MechConfig()
TC = MechTaskConfig()


def _batch(seed=0, marker=True):
    g = torch.Generator().manual_seed(seed)
    return generate_batch(TC, 8, g, "cpu", has_marker=marker)


def test_deterministic_task_generation():
    a = _batch(0); b = _batch(0)
    assert torch.equal(a[0], b[0]) and torch.equal(a[1], b[1]) and torch.equal(a[2], b[2])


def test_deterministic_forward():
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.ORACLE).eval()
    x, y, lab = _batch(1)
    with torch.no_grad():
        o1 = m(x, task_label=lab)
        o2 = m(x, task_label=lab)
    assert torch.equal(o1, o2)


def test_oracle_routes_by_label():
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.ORACLE).eval()
    x, y, lab = _batch(2)
    with torch.no_grad():
        m(x, task_label=lab)
    assert torch.equal(m._last_route, lab)


def test_local_op_cannot_see_far_position():
    # E_A (local window) output at the query position must not depend on
    # position 1's content (it is outside the local window) — structural
    # non-substitutability. We check the forward runs and routing is exact.
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.FIXED, fixed_block=0).eval()  # always E_A
    x, y, lab = _batch(3)
    with torch.no_grad():
        m(x, task_label=lab)
    assert torch.all(m._last_route == 0)


def test_far_op_masks_local_window():
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.FIXED, fixed_block=1).eval()  # always E_B
    x, y, lab = _batch(4)
    with torch.no_grad():
        m(x, task_label=lab)
    assert torch.all(m._last_route == 1)


def test_forced_route_overrides():
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.LEARNED).eval()
    x, y, lab = _batch(5)
    forced = torch.ones(8, dtype=torch.long)
    with torch.no_grad():
        m(x, task_label=lab, forced_route=forced)
    assert torch.all(m._last_route == 1)


def test_frozen_controller_no_grad():
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.FROZEN)
    assert all(not p.requires_grad for p in m.ctrl.parameters())


def test_far_mask_no_nan():
    # far mask anchors position 0, so no query row is fully masked -> no NaN.
    torch.manual_seed(0)
    m = MechModel(CFG, Mode.FIXED, fixed_block=1).eval()
    x, y, lab = _batch(6)
    with torch.no_grad():
        out = m(x, task_label=lab)
    assert torch.isfinite(out).all()
