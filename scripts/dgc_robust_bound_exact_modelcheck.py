from __future__ import annotations

from fractions import Fraction
import itertools


def simplex_grid(den):
    for a in range(den+1):
        for b in range(den-a+1):
            yield (Fraction(a,den),Fraction(b,den),Fraction(den-a-b,den))


def expectation(p,f): return sum((pi*fi for pi,fi in zip(p,f,strict=True)),Fraction(0))
def tv(p,q): return sum((abs(a-b) for a,b in zip(p,q,strict=True)),Fraction(0))/2

def w1_line(p,q): return abs(p[0]-q[0])+abs((p[0]+p[1])-(q[0]+q[1]))


def main():
    ps=tuple(simplex_grid(6)); fgrid=(Fraction(0),Fraction(1,2),Fraction(1)); tv_checks=0; w_checks=0
    for p,q in itertools.product(ps,repeat=2):
        t=tv(p,q)
        for f in itertools.product(fgrid,repeat=3):
            ep,eq=expectation(p,f),expectation(q,f); width=max(f)-min(f)
            if abs(ep-eq)>t*width: raise AssertionError(("TV",p,q,f,ep,eq,t,width))
            tv_checks+=1
        w=w1_line(p,q)
        for f in itertools.product((Fraction(0),Fraction(1,2),Fraction(1),Fraction(3,2),Fraction(2)),repeat=3):
            if any(abs(f[i]-f[j])>abs(i-j) for i in range(3) for j in range(3)): continue
            ep,eq=expectation(p,f),expectation(q,f)
            if abs(ep-eq)>w: raise AssertionError(("W1",p,q,f,ep,eq,w))
            w_checks+=1
    print(f"DGC-ROBUST-BOUND-EXACT: PASS distributions={len(ps)} tv_checks={tv_checks} wasserstein_checks={w_checks}")
    return 0

if __name__=="__main__": raise SystemExit(main())
