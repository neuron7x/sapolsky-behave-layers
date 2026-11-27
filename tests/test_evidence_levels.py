from __future__ import annotations

import unittest
from fractions import Fraction as F
from itertools import product

from cwc.epistemics.evidence_revision import (
    CountermodelCandidate,
    EvidenceCharge,
    EvidenceComponent,
    challenge_countermodels,
    compose_evidence_payoffs,
    invalidated_certificates,
)
from cwc.epistemics.evidence_sequential import (
    ObservationBranch,
    continuation_gain,
    mixture_certificate,
    mixture_radius_bounds,
    posterior_vertices,
    select_evidence_trees,
)
from cwc.epistemics.evidence_value import EvidenceProbe


class EvidenceLevels(unittest.TestCase):
    def test_01_exact_mixture_and_radius_bracket(self):
        self.assertIsNone(mixture_certificate(((2, 0),), 1))
        self.assertIsNone(mixture_certificate(((0, 2),), 1))
        self.assertEqual(mixture_certificate(((2, 0), (0, 2)), 1), (F(1, 2), F(1, 2)))
        self.assertIsNone(mixture_certificate(((2, 0), (0, 2)), F(11, 10)))
        self.assertEqual(mixture_certificate(((3, 0, 0), (0, 3, 0), (0, 0, 3)), 1), (F(1, 3),)*3)
        arguments = {"utilities": ((0, 2, -2), (0, -2, 2))*2,
                     "weights": (F(1, 2), F(1, 2), 0, 0), "target": F(1, 2)}
        combined = mixture_radius_bounds(
            **arguments, policy_payoffs=((F(8, 5), F(8, 5), F(8, 5), F(-2, 5)),
                                         (F(8, 5), F(8, 5), F(-2, 5), F(8, 5))),
        )
        self.assertIsNotNone(combined)
        self.assertLessEqual(combined.lower, F(11, 30))
        self.assertGreaterEqual(combined.upper, F(11, 30))
        self.assertLessEqual(combined.upper-combined.lower, F(1, 1024))

    def test_01_uninformative_coin_has_no_matching_advantage(self):
        utilities = ((0, 3, -1), (0, -1, 3))*2
        # Any randomized post-observation rule on a world-independent
        # coin is a mixture of these same free decisions, with a charge.
        payoffs = tuple(tuple(F(row[action])-F(1, 10) for row in utilities) for action in range(3))
        self.assertIsNone(mixture_radius_bounds(
            utilities=utilities, weights=(F(1, 2), F(1, 2), 0, 0),
            policy_payoffs=payoffs, target=F(1, 2),
        ))

    def test_02_adaptive_tree_and_direct_path_oracle(self):
        worlds = tuple(product((0, 1), repeat=3))
        utilities = tuple((0, 2, -2) if bit == 0 else (0, -2, 2) for _, _, bit in worlds)
        weights = (F(1, 4),)*4 + (0,)*4
        probes = [EvidenceProbe("R", F(1, 10),
                                tuple((0,1) if identity else (1,0) for _, identity, _ in worlds))]
        for index in (0, 1):
            probabilities = []
            for stress, identity, bit in worlds:
                if identity != index:
                    p = F(1, 2)
                elif stress:
                    p = F(9, 10) if bit else F(1, 10)
                else:
                    p = F(bit)
                probabilities.append((1-p, p))
            probes.append(EvidenceProbe(f"P{index}", F(1, 10), tuple(probabilities)))
        choice = select_evidence_trees(utilities=utilities, weights=weights, probes=probes, target=1)
        self.assertIsNone(choice.fixed)
        self.assertIsNotNone(choice.adaptive)
        self.assertEqual(choice.adaptive.tree, ObservationBranch(
            "R", ObservationBranch("P0", 1, 2), ObservationBranch("P1", 1, 2)))
        self.assertEqual(choice.adaptive.radius, F(1, 3))
        self.assertEqual(choice.adaptive.nominal_advantage, F(9, 5))

        def traverse(node, world, mass, accumulated):
            if not isinstance(node, ObservationBranch):
                return [(mass, utilities[world][node]-accumulated)]
            probe = next(p for p in probes if p.probe_id == node.probe_id)
            visits = []
            for child, branch_prob in zip((node.zero, node.one), probe.laws[world], strict=True):
                visits.extend(traverse(child, world, mass*branch_prob, accumulated+probe.cost))
            return visits

        net = []
        for world in range(8):
            leaves = traverse(choice.adaptive.tree, world, F(1), F(0))
            self.assertEqual(sum(mass for mass, _ in leaves), 1)
            net.append(sum(mass*value for mass, value in leaves))
        self.assertEqual(net, [F(9, 5)]*4 + [F(7, 5)]*4)

        erased = [probes[0], *(EvidenceProbe(p.probe_id, p.cost, ((F(1, 2),F(1, 2)),)*8)
                               for p in probes[1:])]
        no_signal = select_evidence_trees(utilities=utilities, weights=weights, probes=erased, target=1)
        self.assertIsNone(no_signal.adaptive)

    def test_03_persistent_countermodel_after_surprise(self):
        posterior = posterior_vertices((1, 0), (F(1, 100), 1), F(1, 10))
        self.assertEqual(max(vertex[1] for vertex in posterior), F(100, 109))
        self.assertEqual(continuation_gain((0, 0), (1, -1), posterior), F(-91, 109))
        self.assertEqual(posterior_vertices((1, 0), (0, 1), F(1, 10)), ((F(0), F(1)),))
        with self.assertRaises(ValueError):
            posterior_vertices((1, 0), (0, 1), 0)

    def test_04_joint_world_accounting_and_shared_evidence(self):
        receipt = EvidenceCharge("sensor", "a"*64, F(1, 2))
        left = EvidenceComponent((("w0", F(-1, 2)), ("w1", 1)), 0, (receipt,))
        right = EvidenceComponent((("w0", 1), ("w1", F(-1, 2))), 0, (receipt,))
        value, spend = compose_evidence_payoffs(("w0", "w1"), [left,right], F(1, 2))
        self.assertEqual(spend, F(1, 2))
        self.assertEqual(value, (0, 0))
        with self.assertRaises(ValueError):
            compose_evidence_payoffs(("w0", "w1"), [left,right], F(1, 4))
        conflict = EvidenceComponent(right.world_payoffs, 0, (EvidenceCharge("sensor", "b"*64, F(1, 2)),))
        with self.assertRaises(ValueError):
            compose_evidence_payoffs(("w0", "w1"), [left,conflict], F(1, 2))

    def test_05_guided_selection_can_win_and_lose_at_identical_budget(self):
        def check(key):
            if key == "excluded":
                self.fail("incompatible world reached the judge")
            return int(key in ("m0","m1"))
        candidates = [CountermodelCandidate(f"m{k}", "obs", -k) for k in range(8)]
        excluded = CountermodelCandidate("excluded","different",999)
        for flip in (False, True):
            signed = [CountermodelCandidate(c.candidate_id,c.signature,
                       -c.proxy_harm if flip else c.proxy_harm) for c in candidates]
            guided = challenge_countermodels(candidates=[*signed,excluded], observation_signature="obs",
                                            budget=2, inspect=check, mode="guided", seed=0)
            uniform = [challenge_countermodels(candidates=signed, observation_signature="obs",
                       budget=2, inspect=check, mode="uniform", seed=k) for k in range(16)]
            hits = sum(len(q.contradicted) for q in uniform)
            self.assertGreater(hits, 0)
            self.assertLess(hits, 32)
            self.assertEqual(len(guided.checked), 2)
            self.assertEqual(len(guided.contradicted), 0 if flip else 2)
            self.assertEqual(guided, challenge_countermodels(candidates=[excluded, *reversed(signed)],
                             observation_signature="obs", budget=2, inspect=check, mode="guided", seed=0))

    def test_06_selective_transitive_revocation(self):
        deps = {"plan": ("claim","independent"),"claim": ("shared",),
                "report": ("shared",),"independent": ("other",)}
        before = {"shared":"a"*64,"other":"b"*64,"unused":"c"*64}
        self.assertEqual(invalidated_certificates(deps,before,{**before,"shared":"e"*64}),
                         ("claim","plan","report"))
        self.assertEqual(invalidated_certificates(deps,before,{**before,"unused":"e"*64}), ())
        self.assertEqual(invalidated_certificates(deps,before,{"other":"b"*64,"unused":"c"*64}),
                         ("claim","plan","report"))
        with self.assertRaises(ValueError):
            invalidated_certificates({"cycle": ("cycle",)},before,before)
        with self.assertRaises(ValueError):
            invalidated_certificates({"invalid": ("unknown",)},before,before)


if __name__ == "__main__":
    unittest.main()
