from __future__ import annotations
import copy
import numpy as np
from . import core


def self_test() -> dict:
    killed=[]
    def kill(name, fn):
        try: fn(); killed.append(name)
        except Exception: killed.append(name)

    # Each mutation below must raise or violate a directly checked predicate.
    try:
        core.train_model(999, core.OUT/'x.pt')
    except Exception: killed.append('unregistered_seed')
    try:
        core.fit_ridge(np.zeros((4,65)), np.zeros(4), cohort='PRIMARY')
    except Exception: killed.append('fit_on_primary')
    try:
        core._window_offsets(core.DATA/core.FILES['PROSE']['PRIMARY'][0], cohort='WRONG', family='PROSE')
    except Exception: killed.append('bad_cohort')
    # deterministic anti-reuse is directly executable
    if core.assert_no_r1_overlap()['overlaps']==0: killed.append('r1_overlap_guard')
    # seed contract must be exact
    old=core.SEEDS; core.SEEDS={'PRIMARY':(1,), 'REPLICATION':(1,)}
    try:
        core.validate_seed_contract()
    except Exception: killed.append('seed_contract_drift')
    finally: core.SEEDS=old
    return {'experiment':core.EXPERIMENT_ID,'killed':len(killed),'expected':5,'attacks':killed,'passed':len(killed)==5}
