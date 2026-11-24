"""Independent explicit schedules, timing boundaries and witness falsifiers."""
import itertools
import unittest

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_05i import causal as c


def explicit_paths(n,windows):
    options=[[None]+[(t,m) for t in range(lo,min(hi,n-1)+1) for m in c.ALL] for lo,hi in windows]
    out=set()
    for changes in itertools.product(*options):
        schedule=dict(x for x in changes if x is not None)
        mode=0
        path=[]
        valid=True
        for t in range(n):
            if t in schedule:
                if schedule[t]==mode:
                    valid=False
                    break
                mode=schedule[t]
            path.append(mode)
        if valid:
            out.add(tuple(path))
    return out


class TestCausalSupport(unittest.TestCase):
    def test_exhaustive_ternary_and_count_domain(self):
        report=c.count_qualification()
        self.assertEqual(report["ternary_vectors"],6561)
        self.assertEqual(report["mode_count_cases"],236196)
        self.assertEqual(report["count_pairs"],{"NO_SPIKES":1,"ONE_GROUP":8,"EQUAL_NONZERO":4,"UNEQUAL_NONZERO":12})

    def test_decode_exact_disjoint_boundaries(self):
        for n in range(9):
            for error in (-q.RADIUS*.999,0.,q.RADIUS*.999):
                self.assertEqual(c.decode_count([q.QUANTUM*n+error]*16),n)
        with self.assertRaises(ValueError):
            c.decode_count([q.QUANTUM/2]*16)
        with self.assertRaises(ValueError):
            c.decode_count([0.]*15+[q.QUANTUM])

    def test_causal_order_even_perfect_past_does_not_certify_new_mode(self):
        o=c.Observer(((2,3),),retain_paths=True)
        self.assertEqual(o.step(0),(None,(0,)))
        self.assertEqual(o.step(1,(0,)),((0,),(0,)))
        self.assertEqual(o.step(2,(0,)),((0,),c.ALL))
        self.assertEqual(c.common_groups(c.ALL),())
        self.assertEqual(o.step(3,(0,)),((0,),c.ALL))
        self.assertEqual(o.step(4,(1,)),((1,),(1,)))
        self.assertEqual(c.common_groups((1,)),(1,))

    def test_independent_explicit_schedule_enumeration(self):
        windows=((1,2),(4,5))
        n=7
        paths=explicit_paths(n,windows)
        # Include silent, singleton, aliased, and contradictory histories.
        alphabet=((0,1,2,3),(0,),(1,),(0,2),(1,3))
        for supports in itertools.product(alphabet,repeat=4):
            tape=list(supports)+[c.ALL]*(n-1-len(supports))
            observer=c.Observer(windows,retain_paths=True)
            observer.step(0)
            feasible=set(paths)
            for t,s in enumerate(tape,1):
                feasible={path for path in feasible if path[t-1] in s}
                if not feasible:
                    with self.assertRaisesRegex(ValueError,"MODEL_CLASS_VIOLATION"):
                        observer.step(t,s)
                    break
                last,current=observer.step(t,s)
                self.assertEqual(last,tuple(sorted({x[t-1] for x in feasible})))
                self.assertEqual(current,tuple(sorted({x[t] for x in feasible})))
                if len(current)>1:
                    witness=observer.alternate(current[0])
                    self.assertNotEqual(witness[-1],current[0])
                    self.assertTrue(any(x[:t+1]==tuple(witness) for x in feasible))

    def test_witness_independent_count_verifier(self):
        bits=[(1,0,0,0,0,0,0,0),(0,)*8,(0,)*8]
        o=c.Observer(((2,3),),retain_paths=True)
        o.step(0)
        for t,(n,row) in enumerate(zip([1,0,0],bits,strict=True),1):
            o.step(t,c.compatible_count(n,row))
        path=o.alternate(0)
        self.assertNotEqual(path[-1],0)
        self.assertEqual(c.validate_path(path,[1,0,0],bits,((2,3),)),[[2,1]] if path[2]==1 else [[3,1]])
        with self.assertRaises(ValueError):
            c.validate_path([0,1,1,1],[1,0,0],bits,((2,3),))
        with self.assertRaises(ValueError):
            c.validate_path([0,0,1,2],[1,0,0],bits,((2,3),))

    def test_block_robust_route_requires_all_future_modes(self):
        self.assertEqual(c.block_feasibility({(0,0)},0,[0,0,0,0],((2,3),)),2)
        self.assertEqual(c.block_feasibility({(0,0)},0,[0,0,None,None],((2,3),)),2)
        self.assertEqual(c.block_feasibility({(2,0)},10,[0,1],((2,3),)),2)
        self.assertEqual(c.block_feasibility({(0,0),(1,0)},10,[0,1],((2,3),)),0)

    def test_support_separates_truth_from_erasure(self):
        full=(1,0,0,0,1,1,0,0)
        self.assertEqual(c.compatible_count(3,full),(2,))
        self.assertEqual(c.compatible_count(1,full),(0,))
        self.assertIn(2,c.compatible_count(3,(None,)*8))
        self.assertEqual(c.common_groups((0,2)),(0,))
        self.assertEqual(c.common_groups((0,1)),())

    def test_invalid_observer_timing_and_windows(self):
        with self.assertRaises(ValueError):
            c.Observer(((2,4),(4,6)))
        o=c.Observer()
        o.step(0)
        with self.assertRaises(ValueError):
            o.step(2,c.ALL)
