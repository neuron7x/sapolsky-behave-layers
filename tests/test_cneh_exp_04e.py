"""Falsifiers for retrospective attribution."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04e import audit as a


class TestAttribution(unittest.TestCase):
    def test_exhaustive_pair_partition_with_erasure(self):
        classes = set()
        for n0 in range(5):
            for n1 in range(5):
                true = (1,)*n0+(0,)*(4-n0)+(1,)*n1+(0,)*(4-n1)
                for mode in range(4):
                    n = q.MODES[mode][0]*n0+q.MODES[mode][1]*n1
                    for bits in (true,(None,)*8):
                        support = set(q.support(tuple(range(4)),bits,(q.QUANTUM*n,)*16))
                        for other in range(4):
                            if mode!=other:
                                label = a.classify(mode,other,(n0,n1),support)
                                classes.add(label)
                                if bits==true:
                                    self.assertNotEqual(label,"ERASURE_BLOCKED")
        self.assertEqual(classes,set(a.CLASSES))

    def test_impossible_equal_arrival_exclusion_rejected(self):
        with self.assertRaisesRegex(ValueError,"equal arrival"):
            a.classify(0,1,(1,1),{0})

    def test_missing_truth_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid pair"):
            a.classify(0,1,(1,0),{1})

    def test_streak(self):
        self.assertEqual(a.longest([True,False,True,True,False]),2)
        self.assertEqual(a.longest([]),0)

    def test_wrong_archive_rejected(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"wrong.zip"
            path.write_bytes(b"not the sealed archive")
            with self.assertRaisesRegex(ValueError,"archive digest"):
                a.load_archive(path)
