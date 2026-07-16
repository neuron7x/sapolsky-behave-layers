import torch
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch, deterministic_output_parser, L_OUT
from experiments.wp2_routing_v2.src.contracts import TaskKind, POS

def test_canonical_target_matches_state():
    g = torch.Generator().manual_seed(0)
    tok, st, canon, kind = generate_batch(32, g, "train", 0.5)
    assert canon.shape[1] == L_OUT
    assert torch.equal(canon[:, 0], st.subject)
    assert torch.equal(canon[:, 1], st.relation)
    assert torch.equal(canon[:, 2], st.object)

def test_easy_is_canonical_prefix():
    g = torch.Generator().manual_seed(1)
    tok, st, canon, kind = generate_batch(64, g, "train", 1.0)  # all hard? no, p=1
    g2 = torch.Generator().manual_seed(1)
    tok, st, canon, kind = generate_batch(64, g2, "train", 0.0)  # all easy
    easy = kind == int(TaskKind.EASY_DIRECT)
    assert easy.all()
    assert torch.equal(tok[:, :3], canon[:, :3])  # easy surface == canonical prefix

def test_deterministic_output_parser_roundtrip():
    g = torch.Generator().manual_seed(2)
    tok, st, canon, kind = generate_batch(16, g, "train", 0.5)
    rec = deterministic_output_parser(canon)
    assert torch.equal(rec.subject, st.subject)
    assert torch.equal(rec.relation, st.relation)

def test_compositional_split_disjoint():
    from experiments.wp2_routing_v2.src.task_semantic_route import _tuple_in_split
    # a tuple cannot be in both train and test
    for s in range(10, 26):
        for r in range(30, 38):
            for o in range(10, 26):
                if _tuple_in_split(s, r, o, "test"):
                    assert not _tuple_in_split(s, r, o, "train")
