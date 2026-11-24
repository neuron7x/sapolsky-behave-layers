"""Public-only, fail-closed admission under unrestricted hidden switching.

No policy callable, privileged observation, estimated mode, or positive
authorization enters this interface. This is not a physiological safety gate.
"""
from __future__ import annotations

ACTIONS=("WAIT","G0","G1")
MODES=((1,0),(0,1),(1,1),(0,0))
OBSERVATION_FIELDS={"tick","receiver_spikes","population_spikes","last_action"}


def need(ok,message):
    if not ok:
        raise ValueError(message)


def common_groups(support):
    """Pure robust-connectivity calculation, not an authority issuer."""
    need(type(support) is tuple and bool(support)
         and all(type(m) is int and 0<=m<4 for m in support)
         and support==tuple(sorted(set(support))),"nonempty canonical mode support")
    return tuple(g for g in (0,1) if all(MODES[m][g]==1 for m in support))


def validate_history(history):
    need(type(history) in (tuple,list) and 1<=len(history)<=512,"public history roster")
    for k,obs in enumerate(history):
        need(type(obs) is dict and set(obs)==OBSERVATION_FIELDS
             and all(type(key) is str for key in obs),"public observation schema")
        tick=obs["tick"];r=obs["receiver_spikes"];p=obs["population_spikes"];a=obs["last_action"]
        need(type(tick) is int and tick==k,"public observation chronology")
        need(type(r) is int and type(p) is int and 0<=r<=p,"public spike counts")
        if k==0:
            need(a is None and r==p==0,"initial observation")
        else:
            need(type(a) is str and a in ACTIONS,"past action enum")
    return len(history)-1


def admit(history,requested_action):
    """Conservative action-time support, independent of past count values.

    Scope: an unknown mode can change before application of the next source
    stimulus, with no authenticated dwell/transition or sensor constraint.
    Even perfect inference of a previous mode cannot certify the next one.
    The result does not execute an action or authorize a blind experiment.
    """
    tick=validate_history(history)
    need(type(requested_action) is str and requested_action in ACTIONS,"requested action enum")
    support=(0,1,2,3)
    common=common_groups(support)
    need(not common,"unrestricted topology must not authorize a source")
    return {"scope":"UNRESTRICTED_HIDDEN_ACTION_TIME_SWITCHING_ONLY",
            "tick":tick,"requested_action":requested_action,
            "mode_support":list(support),"guaranteed_common_source_groups":list(common),
            "disposition":"NO_SOURCE_REQUEST" if requested_action=="WAIT" else "ABSTAIN_UNIDENTIFIED",
            "source_action_authorized":False,"closed_loop_authorized":False,
            "blind_causal_cohort":"BLOCKED","scientific_promotion_authorized":False,
            "scientific_promotion":"BLOCKED"}
