from cwc.credit.envelope import CreditAuthorityDecision
from cwc.replay.causal_governor import ReplayCandidate, choose_replay_candidate


def test_replay_requires_accepted_causal_credit():
    candidates = [ReplayCandidate("A", 1.0), ReplayCandidate("C", 2.0)]
    denied = CreditAuthorityDecision("ABSTAIN_UNCERTAIN_MODEL", None, "x", "v")
    assert choose_replay_candidate(denied, candidates).candidate_id is None
    accepted = CreditAuthorityDecision("ACCEPT_CAUSAL_CREDIT", "A", "x", "v")
    assert choose_replay_candidate(accepted, candidates).candidate_id == "A"
