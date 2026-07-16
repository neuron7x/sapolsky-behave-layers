import torch
from experiments.wp3_rcfr.src.task_ops import generate_batch, PERMS, N_SYMBOLS, N_ROLES
from experiments.wp3_rcfr.src.rcfr_modules import OperatorModel, Mode

def test_task_target_is_permutation():
    g = torch.Generator().manual_seed(0)
    tok, tgt, roles = generate_batch(16, g)
    ops = tok[:, 1:]
    for b in range(16):
        assert torch.equal(tgt[b], PERMS[roles[b]][ops[b]])

def test_task_deterministic():
    a = generate_batch(8, torch.Generator().manual_seed(3))
    b = generate_batch(8, torch.Generator().manual_seed(3))
    assert torch.equal(a[0], b[0]) and torch.equal(a[1], b[1])

def test_all_modes_forward():
    g = torch.Generator().manual_seed(0)
    tok, tgt, roles = generate_batch(8, g)
    for mode in Mode:
        torch.manual_seed(0)
        m = OperatorModel(mode).eval()
        with torch.no_grad():
            out = m(tok)
        assert out.shape == (8, tok.shape[1]-1, N_SYMBOLS)
        assert torch.isfinite(out).all()

def test_forced_role_changes_output():
    g = torch.Generator().manual_seed(1)
    tok, tgt, roles = generate_batch(8, g)
    torch.manual_seed(0)
    m = OperatorModel(Mode.RCFR).eval()
    with torch.no_grad():
        a = m(tok)
        b = m(tok, forced_role=(roles+1) % N_ROLES)
    assert not torch.equal(a.argmax(-1), b.argmax(-1))

def test_operator_is_linear_no_relu():
    # shared_no_role must be UNABLE to solve (linear operator); sanity: forward runs
    torch.manual_seed(0)
    m = OperatorModel(Mode.SHARED_NO_ROLE).eval()
    g = torch.Generator().manual_seed(0)
    tok, tgt, roles = generate_batch(8, g)
    with torch.no_grad():
        assert torch.isfinite(m(tok)).all()

def test_rcfr_fewer_params_than_separate():
    torch.manual_seed(0)
    rcfr = sum(p.numel() for p in OperatorModel(Mode.RCFR).parameters())
    sep = sum(p.numel() for p in OperatorModel(Mode.SEPARATE_MODULES).parameters())
    assert rcfr < sep  # one shared operator + bank vs R full operators
