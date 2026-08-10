from experiments.csca_06b_operator_robustness.run import score_pair


def test_robust_authority_requires_same_top_sign_and_margin():
    a={"A_RECENT":.8,"B_PREV":.1,"C_MIDDLE":0.,"D_EARLY":0.}
    b={"A_RECENT":.6,"B_PREV":.2,"C_MIDDLE":0.,"D_EARLY":0.}
    x=score_pair(a,b,delta=.1)
    assert x["robust_authority"] is True
    assert x["candidate"]=="A_RECENT"


def test_operator_top_change_abstains():
    a={"A_RECENT":.8,"B_PREV":.1,"C_MIDDLE":0.,"D_EARLY":0.}
    b={"A_RECENT":.1,"B_PREV":.8,"C_MIDDLE":0.,"D_EARLY":0.}
    x=score_pair(a,b,delta=.1)
    assert x["robust_authority"] is False
    assert x["state"]=="ABSTAIN_OPERATOR_DEPENDENT"


def test_sign_flip_abstains_even_same_top():
    a={"A_RECENT":.8,"B_PREV":.1,"C_MIDDLE":0.,"D_EARLY":0.}
    b={"A_RECENT":-.8,"B_PREV":.1,"C_MIDDLE":0.,"D_EARLY":0.}
    x=score_pair(a,b,delta=.1)
    assert x["robust_authority"] is False
