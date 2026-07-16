import math

import torch

from experiments.common.metrics import auroc, mutual_information, symmetric_nmi, task_normalized_mi


def test_auroc_perfect_and_reversed():
    s=torch.tensor([0.1,0.2,0.3,0.4])
    y=torch.tensor([0,0,1,1])
    assert abs(auroc(s,y)-1.0)<1e-9
    assert abs(auroc(-s,y)-0.0)<1e-9                 # reversed

def test_auroc_all_tied_is_half():
    s=torch.zeros(6)
    y=torch.tensor([0,0,0,1,1,1])
    assert abs(auroc(s,y)-0.5)<1e-9                  # average ranks -> 0.5

def test_auroc_partial_ties():
    # scores [1,1,2,3], labels [0,1,1,1]; average-rank AUROC vs brute force
    s=torch.tensor([1.,1.,2.,3.])
    y=torch.tensor([0,1,1,1])
    # brute force: fraction of (pos,neg) pairs with pos>neg + 0.5*ties
    pos=s[y==1]
    neg=s[y==0]
    tot=0.0
    for p in pos:
        for nq in neg:
            tot += 1.0 if p>nq else (0.5 if p==nq else 0.0)
    assert abs(auroc(s,y)-tot/(len(pos)*len(neg)))<1e-9

def test_auroc_one_class_absent_is_nan():
    assert math.isnan(auroc(torch.tensor([0.1,0.2]), torch.tensor([1,1])))

def test_symmetric_nmi_bounds_and_identity():
    r=torch.tensor([0,0,1,1])
    t=torch.tensor([0,0,1,1])
    assert abs(symmetric_nmi(r,t)-1.0)<1e-6          # identical partitions -> 1
    ind_r=torch.tensor([0,1,0,1])
    assert symmetric_nmi(ind_r,t)<1e-9               # independent -> 0

def test_symmetric_differs_from_task_normalized_when_H_differ():
    # R has lower entropy than T -> the two normalizations differ
    r=torch.tensor([0,0,0,1])
    t=torch.tensor([0,1,0,1])
    assert abs(symmetric_nmi(r,t)-task_normalized_mi(r,t))>1e-6 or mutual_information(r,t,2,2)==0
