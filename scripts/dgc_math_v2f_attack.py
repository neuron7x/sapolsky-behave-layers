from __future__ import annotations

from cwc.governance.causal_transport import certify_s_admissible_transport, d_separated


def must_raise(name, fn):
    try: fn()
    except ValueError: print(f"KILLED {name}"); return 1
    raise AssertionError(f"SURVIVED {name}")


def main():
    killed=0
    killed+=must_raise("CYCLIC_CAUSAL_GRAPH",lambda:d_separated(nodes=("a","b"),edges=(("a","b"),("b","a")),x=("a",),y=("b",)))
    killed+=must_raise("SELECTION_NODE_COLLISION",lambda:certify_s_admissible_transport(causal_nodes=("x","y"),causal_edges=(("x","y"),),selection_edges=(("x","y"),),treatment=("x",),outcome=("y",),adjustment=(),source_interventional_available=True,target_adjustment_distribution_available=True))
    direct=certify_s_admissible_transport(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","y"),),treatment=("x",),outcome=("y",),adjustment=("z",),source_interventional_available=True,target_adjustment_distribution_available=True)
    if direct.transportable: raise AssertionError("SURVIVED DIRECT_SELECTION_TO_OUTCOME")
    print("KILLED DIRECT_SELECTION_TO_OUTCOME"); killed+=1
    post=certify_s_admissible_transport(causal_nodes=("x","z","y"),causal_edges=(("x","z"),("z","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),adjustment=("z",),source_interventional_available=True,target_adjustment_distribution_available=True)
    if post.transportable: raise AssertionError("SURVIVED POST_TREATMENT_ADJUSTMENT")
    print("KILLED POST_TREATMENT_ADJUSTMENT"); killed+=1
    print(f"DGC-MATH-V2F-ATTACK: PASS ({killed}/4 killed)")

if __name__=="__main__": main()
