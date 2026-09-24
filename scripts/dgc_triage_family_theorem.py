from __future__ import annotations

import itertools

KNOWN=("A","H","C","S","I")
DGC04_NONEMPTY={("A",),("H",),("C",),("S",),("I",),("A","H"),("C","S"),("H","I"),("A","C","S"),KNOWN}
ANCHORED={"B0":160,"B1":85,"B2":36}


def hamming(a,b): return len(set(a)^set(b))
def path_calls(combo): return 5 if not combo else len(combo)
def dgc_calls(combo): return 5 if not combo else 1
def full_calls(combo): return 5
def removable(combo): return path_calls(combo)-dgc_calls(combo)


def main():
    all_combos=((),)+tuple(c for r in range(1,6) for c in itertools.combinations(KNOWN,r))
    unseen=tuple(c for c in all_combos if c and c not in DGC04_NONEMPTY)
    if len(all_combos)!=32 or len(DGC04_NONEMPTY)!=10 or len(unseen)!=21: raise AssertionError("DGC04/DGC05 partition no longer spans full family")
    b0=sum(full_calls(c) for c in all_combos); b1=sum(path_calls(c) for c in all_combos); b2=sum(dgc_calls(c) for c in all_combos)
    if {"B0":b0,"B1":b1,"B2":b2}!=ANCHORED: raise AssertionError((b0,b1,b2,ANCHORED))
    max_ratio=0.0
    for a,b in itertools.combinations(all_combos,2):
        dist=hamming(a,b); delta=abs(removable(a)-removable(b))
        if delta>dist: raise AssertionError(("non-Lipschitz",a,b,delta,dist))
        if dist: max_ratio=max(max_ratio,delta/dist)
    if max_ratio!=1.0: raise AssertionError("expected tight unit Lipschitz constant")
    print(f"DGC-TRIAGE-FAMILY-THEOREM: PASS tasks=32 B0={b0} B1={b1} B2={b2} savings_vs_full={1-b2/b0:.6f} savings_vs_router={1-b2/b1:.6f} lipschitz=1")
    return 0

if __name__=="__main__": raise SystemExit(main())
