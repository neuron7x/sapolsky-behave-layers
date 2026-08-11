from experiments.real_transfer_01.semantic_gate import self_test


def test_real_transfer01_semantic_gate_kills_every_frozen_mutation():
    results = self_test()
    assert len(results) == 13
    assert all(r.killed for r in results), [r for r in results if not r.killed]
