"""Surface-matched mechanism-separable task (G3 fix / defect #4). EASY and HARD
share identical length, identical first token, and identical token multiset
(histogram) BY CONSTRUCTION — they differ ONLY in a structural property that
determines which mechanism is needed, so a surface probe cannot classify them.

Task: a fixed-length sequence contains exactly one DUPLICATED value (appears
twice); all other positions are distinct fillers. The answer is the duplicated
value. Whether a LOCAL path suffices depends on the DISTANCE between the two
occurrences (structural, not surface):
  - NEAR (distance <= w): a local window can see both -> local mechanism suffices.
  - FAR  (distance >  w): needs a global search -> global mechanism required.
The histogram is identical for NEAR and FAR (one duplicate + the same filler
distribution), the length is fixed, and the first token is drawn identically.
"""
from __future__ import annotations

import torch

VOCAB = 40
SEQ_LEN = 16
LOCAL_W = 2   # local window; distance <= w is NEAR (local-solvable)


def generate_batch(batch_size: int, gen: torch.Generator, device: str = "cpu"):
    """Returns tokens (B, L), target (B,) = duplicated value, is_far (B,) bool
    (True = needs global). Surface-matched: identical length/histogram shape."""
    L = SEQ_LEN
    tokens = torch.zeros(batch_size, L, dtype=torch.long)
    target = torch.zeros(batch_size, dtype=torch.long)
    is_far = torch.zeros(batch_size, dtype=torch.bool)
    for b in range(batch_size):
        far = bool(torch.rand(1, generator=gen).item() < 0.5)
        is_far[b] = far
        distinct = torch.randperm(VOCAB, generator=gen)[:L - 1].tolist()  # L-1 distinct values
        dup = distinct[0]                                       # this value appears TWICE
        fillers = distinct[1:]                                  # L-2 values, once each
        # two positions for the duplicate, with the required distance class
        if far:
            i = int(torch.randint(0, L - LOCAL_W - 2, (1,), generator=gen).item())
            j = int(torch.randint(i + LOCAL_W + 1, L, (1,), generator=gen).item())
        else:
            i = int(torch.randint(0, L - LOCAL_W - 1, (1,), generator=gen).item())
            j = i + 1 + int(torch.randint(0, LOCAL_W, (1,), generator=gen).item())
        seq = [-1] * L
        seq[i] = dup
        seq[j] = dup
        fi = 0
        for pos in range(L):
            if seq[pos] == -1:
                seq[pos] = fillers[fi]
                fi += 1
        tokens[b] = torch.tensor(seq, dtype=torch.long)
        target[b] = dup
    return tokens.to(device), target.to(device), is_far.to(device)
