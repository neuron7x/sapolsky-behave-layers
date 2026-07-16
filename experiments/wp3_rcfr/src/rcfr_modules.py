"""RCFR module + baselines (Act F). One shared LINEAR operator whose effective
weight is role-modulated by a FIXED low-rank primitive bank:

    ΔW(r) = Σ_m c_m(r) · U_m V_mᵀ ,   controller emits only c(r) ∈ R^{K_r}.

A fixed W cannot be R distinct permutations, so role-conditioned modulation is
the mechanism under test. Baselines vary ONLY how the role affects the module.
"""
from __future__ import annotations

import enum

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.wp3_rcfr.src.task_ops import N_ROLES, N_SYMBOLS, VOCAB

D_MODEL = 64
K_R = 8          # number of low-rank primitives
PRIM_RANK = 2    # rank per primitive


class Mode(enum.Enum):
    SHARED_NO_ROLE = "shared_no_role"      # fixed W, role only in input embedding
    STATIC_LORA = "static_lora"            # W + fixed low-rank delta (no role)
    FIXED_ROLE = "fixed_role"              # ΔW(r0) with a constant role
    DISEL_GATED = "disel_gated"            # rank gates from INPUT (prior-art baseline)
    SEPARATE_MODULES = "separate_modules"  # one W per role (capacity baseline)
    RCFR = "rcfr"                          # ΔW(r) role-conditioned (candidate)


class OperatorModel(nn.Module):
    def __init__(self, mode: Mode):
        super().__init__()
        self.mode = mode
        self.embed = nn.Embedding(VOCAB, D_MODEL)
        self.base = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.head = nn.Linear(D_MODEL, N_SYMBOLS, bias=False)
        # fixed low-rank primitive bank (shared across modes that use it)
        self.U = nn.Parameter(torch.randn(K_R, D_MODEL, PRIM_RANK) * 0.1)
        self.V = nn.Parameter(torch.randn(K_R, D_MODEL, PRIM_RANK) * 0.1)
        if mode == Mode.RCFR:
            self.role_net = nn.Sequential(nn.Linear(D_MODEL, 64), nn.ReLU(), nn.Linear(64, K_R))
        if mode == Mode.FIXED_ROLE:
            self.fixed_coeff = nn.Parameter(torch.zeros(K_R))
        if mode == Mode.STATIC_LORA:
            self.lora_coeff = nn.Parameter(torch.zeros(K_R))
        if mode == Mode.DISEL_GATED:
            # fair strong baseline: gates the fixed rank bank from the FULL input
            # (operand content + the role signal), matching RCFR's information.
            self.gate_net = nn.Sequential(nn.Linear(2 * D_MODEL, 64), nn.ReLU(), nn.Linear(64, K_R))
        if mode == Mode.SEPARATE_MODULES:
            self.bases = nn.ModuleList([nn.Linear(D_MODEL, D_MODEL, bias=False) for _ in range(N_ROLES)])
        self._last_coeff: torch.Tensor | None = None

    def _delta(self, coeff: torch.Tensor) -> torch.Tensor:
        # coeff (B, K_R); primitives -> ΔW (B, d, d) = Σ_m c_m U_m V_m^T
        prim = torch.einsum("kdr,ker->kde", self.U, self.V)   # (K, d, d)
        return torch.einsum("bk,kde->bde", coeff, prim)

    def _coeff(self, role_emb: torch.Tensor, input_pool: torch.Tensor, roles) -> torch.Tensor:
        B = role_emb.shape[0]
        if self.mode == Mode.RCFR:
            return self.role_net(role_emb)
        if self.mode == Mode.FIXED_ROLE:
            return self.fixed_coeff.unsqueeze(0).expand(B, -1)
        if self.mode == Mode.STATIC_LORA:
            return self.lora_coeff.unsqueeze(0).expand(B, -1)
        if self.mode == Mode.DISEL_GATED:
            return self.gate_net(torch.cat([input_pool, role_emb], dim=-1))
        return torch.zeros(B, K_R, device=role_emb.device)

    def forward(self, tokens: torch.Tensor, forced_role: torch.Tensor | None = None,
                swap_module: bool = False):
        # tokens (B, 1+L): [role_token, operands...]
        role_tok = tokens[:, 0]
        roles = role_tok - N_SYMBOLS
        if forced_role is not None:
            roles = forced_role
            role_tok = roles + N_SYMBOLS
        operands = tokens[:, 1:]
        x = self.embed(operands)                       # (B, L, d)
        role_emb = self.embed(role_tok)                # (B, d)
        if self.mode == Mode.SHARED_NO_ROLE:
            x = x + role_emb.unsqueeze(1)              # role only in input
        input_pool = x.mean(dim=1)

        if self.mode == Mode.SEPARATE_MODULES:
            # per-example base weight selected by role
            Ws = torch.stack([m.weight for m in self.bases])   # (R, d, d)
            sel = roles if not swap_module else (roles + 1) % N_ROLES
            W = Ws[sel]                                         # (B, d, d)
            h = torch.einsum("bld,bde->ble", x, W.transpose(1, 2))
        else:
            coeff = self._coeff(role_emb, input_pool, roles)
            self._last_coeff = coeff.detach()
            base_w = self.base.weight                          # (d, d)
            delta = self._delta(coeff)                         # (B, d, d)
            eff = base_w.unsqueeze(0) + delta                  # (B, d, d)
            if swap_module:
                eff = base_w.unsqueeze(0) - delta              # corrupt the module
            h = torch.einsum("bld,bde->ble", x, eff.transpose(1, 2))
        # NO nonlinearity: a linear operator makes role-conditioned weight
        # modulation NECESSARY — one fixed linear map cannot be R distinct
        # permutations (needs a role×symbol interaction), so shared_no_role and
        # static_lora fail by construction, isolating the RCFR mechanism.
        return self.head(h)                                    # (B, L, S)
