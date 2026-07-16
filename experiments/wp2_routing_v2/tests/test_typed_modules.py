import torch
from experiments.wp2_routing_v2.src.typed_modules import DirectPath, SemanticParser, SemanticRenderer, SemanticPath
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch
from experiments.wp2_routing_v2.src.contracts import VOCAB_SIZE

def test_shapes():
    g = torch.Generator().manual_seed(0)
    tok, st, canon, kind = generate_batch(8, g)
    assert DirectPath()(tok).shape == (8, 4, VOCAB_SIZE)
    state = SemanticParser()(tok)
    assert state.subject.shape == (8,)
    assert SemanticRenderer()(state).shape == (8, 4, VOCAB_SIZE)

def test_renderer_sees_no_raw_tokens():
    # renderer forward signature takes only SemanticState, not tokens
    import inspect
    params = list(inspect.signature(SemanticRenderer.forward).parameters)
    assert params == ["self", "state"]

def test_semantic_path_composes():
    g = torch.Generator().manual_seed(1)
    tok, st, canon, kind = generate_batch(8, g)
    out, state = SemanticPath()(tok)
    assert out.shape == (8, 4, VOCAB_SIZE)
