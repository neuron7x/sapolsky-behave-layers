from __future__ import annotations

from cwc.governance.causal_transport import find_minimal_s_admissible_adjustments


def main():
    killed=0
    direct=find_minimal_s_admissible_adjustments(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","y"),),treatment=("x",),outcome=("y",),source_interventional_available=True,target_adjustment_distribution_available=True)
    if direct.transportable_count: raise AssertionError("SURVIVED SEARCH_HALLUCINATED_TRANSPORT")
    print("KILLED SEARCH_HALLUCINATED_TRANSPORT"); killed+=1
    no_source=find_minimal_s_admissible_adjustments(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),source_interventional_available=False,target_adjustment_distribution_available=True)
    if no_source.transportable_count: raise AssertionError("SURVIVED MISSING_SOURCE_INTERVENTION")
    print("KILLED MISSING_SOURCE_INTERVENTION"); killed+=1
    post=find_minimal_s_admissible_adjustments(causal_nodes=("x","m","z","y"),causal_edges=(("x","m"),("m","y"),("z","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),source_interventional_available=True,target_adjustment_distribution_available=True)
    if any("m" in c.adjustment for c in post.certificates): raise AssertionError("SURVIVED POST_TREATMENT_SEARCH_CANDIDATE")
    print("KILLED POST_TREATMENT_SEARCH_CANDIDATE"); killed+=1
    print(f"DGC-MATH-V2I-ATTACK: PASS ({killed}/3 killed)")
    return 0

if __name__=="__main__": raise SystemExit(main())
