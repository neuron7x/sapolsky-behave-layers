"""Independent bounds and interval-event falsifiers."""
import itertools
import math
import unittest
from fractions import Fraction

from experiments.cneh_exp_05a import bounds as b


class TestBounds(unittest.TestCase):
    def test_interval_edges_sound_on_rational_fixtures(self):
        width=Fraction(1,100)
        edges,_,_=b.graph(width)
        for x in (Fraction(0),Fraction(1,100),Fraction(2,5),Fraction(1,2),Fraction(199,100),Fraction(2),Fraction(9)):
            for n in range(9):
                for perturb in (-b.TOL,Fraction(0),b.TOL):
                    y=max(Fraction(0),b.A*(x+n*b.TARGET)+perturb)
                    for i in b.cells_for(x,x,width,200):
                        self.assertTrue(set(b.cells_for(y,y,width,200))<=set(edges[i]))

    def test_bellman_matches_independent_bruteforce(self):
        edges=[(0,1),(1,2),(0,)]
        loss=[3,0,1]
        band=[0,1,0]
        lower,upper=b.bellman(edges,loss,band,5)
        for n in range(1,6):
            paths=[path for path in itertools.product(range(3),repeat=n+1)
                   if all(y in edges[x] for x,y in zip(path[:-1],path[1:]))]
            self.assertEqual(lower[n],min(sum(loss[i] for i in path[1:]) for path in paths))
            self.assertEqual(upper[n],max(sum(band[i] for i in path[1:]) for path in paths))

    def test_endpoint_counterexample(self):
        arrivals=[0]*320
        a=b.direct_loss(arrivals,.6068)["loss"]
        z=b.direct_loss(arrivals,.6268)["loss"]
        interior=b.direct_loss(arrivals,.6101)["loss"]
        report=b.interval_sup(arrivals,.6068,.6268)
        self.assertGreater(interior,max(a,z)+.0005)
        self.assertGreaterEqual(report["supremum_loss"]+1e-9,interior)
        self.assertAlmostEqual(report["endpoint_loss"],max(a,z))

    def test_event_envelope_dominates_dense_grid(self):
        for arrivals in ([0]*49,[1]+[0]*48,[0]*9+[2]+[0]*39):
            r=b.interval_sup(arrivals,.1,.9)
            vals=[b.direct_loss(arrivals,.1+.8*i/500)["loss"] for i in range(501)]
            self.assertGreaterEqual(r["supremum_loss"]+1e-9,max(vals))

    def test_degenerate_interval(self):
        r=b.interval_sup([0]*25,.5,.5)
        self.assertTrue(math.isclose(r["endpoint_loss"],r["supremum_loss"],abs_tol=1e-9))
