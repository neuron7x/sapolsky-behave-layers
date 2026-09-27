from __future__ import annotations

import itertools
import pytest

from cwc.governance.causal_transport import certify_s_admissible_transport, d_separated


def _all_simple_paths(nodes, edges, start, target):
    adj={n:set() for n in nodes}
    for u,v in edges: adj[u].add(v); adj[v].add(u)
    stack=[(start,[start])]
    while stack:
        n,path=stack.pop()
        if n==target:
            yield path; continue
        for nxt in adj[n]:
            if nxt not in path: stack.append((nxt,path+[nxt]))


def _brute_d_separated(nodes, edges, x, y, conditioned):
    directed=set(edges); z=set(conditioned)
    parents={n:set() for n in nodes}
    for u,v in edges: parents[v].add(u)
    anc_z=set(z); stack=list(z)
    while stack:
        n=stack.pop()
        for p in parents[n]:
            if p not in anc_z:
                anc_z.add(p); stack.append(p)
    def active(path):
        for i in range(1,len(path)-1):
            a,b,c=path[i-1],path[i],path[i+1]
            collider=(a,b) in directed and (c,b) in directed
            if collider:
                if b not in anc_z: return False
            elif b in z:
                return False
        return True
    return not any(active(path) for a in x for b in y for path in _all_simple_paths(nodes,edges,a,b))


def test_d_separation_matches_independent_active_path_oracle_exhaustively_on_order_dags():
    nodes=("a","b","c","d")
    possible=[(nodes[i],nodes[j]) for i in range(4) for j in range(i+1,4)]
    for mask in range(1<<len(possible)):
        edges=tuple(e for i,e in enumerate(possible) if mask&(1<<i))
        for xi,yi in itertools.permutations(nodes,2):
            rest=[n for n in nodes if n not in {xi,yi}]
            for r in range(len(rest)+1):
                for z in itertools.combinations(rest,r):
                    assert d_separated(nodes=nodes,edges=edges,x=(xi,),y=(yi,),conditioned=z) is _brute_d_separated(nodes,edges,(xi,),(yi,),z)


def test_collider_semantics():
    nodes=("x","m","y"); edges=(("x","m"),("y","m"))
    assert d_separated(nodes=nodes,edges=edges,x=("x",),y=("y",))
    assert not d_separated(nodes=nodes,edges=edges,x=("x",),y=("y",),conditioned=("m",))


def test_s_admissible_transport_succeeds_for_selection_on_adjustment_covariate():
    cert=certify_s_admissible_transport(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),adjustment=("z",),source_interventional_available=True,target_adjustment_distribution_available=True)
    assert cert.transportable and cert.s_admissible and cert.pre_treatment_adjustment and cert.formula


def test_direct_selection_into_outcome_blocks_transport():
    cert=certify_s_admissible_transport(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","y"),),treatment=("x",),outcome=("y",),adjustment=("z",),source_interventional_available=True,target_adjustment_distribution_available=True)
    assert not cert.s_admissible and not cert.transportable


def test_post_treatment_adjustment_blocks_transport():
    cert=certify_s_admissible_transport(causal_nodes=("x","z","y"),causal_edges=(("x","z"),("z","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),adjustment=("z",),source_interventional_available=True,target_adjustment_distribution_available=True)
    assert not cert.pre_treatment_adjustment and not cert.transportable


def test_transport_requires_source_intervention_and_target_distribution():
    kw=dict(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),adjustment=("z",))
    assert not certify_s_admissible_transport(**kw,source_interventional_available=False,target_adjustment_distribution_available=True).transportable
    assert not certify_s_admissible_transport(**kw,source_interventional_available=True,target_adjustment_distribution_available=False).transportable


def test_invalid_graphs_fail_closed():
    with pytest.raises(ValueError): d_separated(nodes=("a","b"),edges=(("a","b"),("b","a")),x=("a",),y=("b",))
    with pytest.raises(ValueError): certify_s_admissible_transport(causal_nodes=("x","y"),causal_edges=(("x","y"),),selection_edges=(("x","y"),),treatment=("x",),outcome=("y",),adjustment=(),source_interventional_available=True,target_adjustment_distribution_available=True)
