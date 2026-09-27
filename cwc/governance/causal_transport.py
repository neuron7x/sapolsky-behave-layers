from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

Edge = tuple[str, str]


def _clean_nodes(nodes: Iterable[str]) -> tuple[str, ...]:
    out = tuple(sorted({str(n).strip() for n in nodes if str(n).strip()}))
    if not out:
        raise ValueError("non-empty node set required")
    return out


def _validate_dag(nodes: Sequence[str], edges: Sequence[Edge]) -> tuple[tuple[str, ...], tuple[Edge, ...]]:
    ns = _clean_nodes(nodes); node_set=set(ns); clean=[]; seen=set()
    for raw_u,raw_v in edges:
        u,v=str(raw_u).strip(),str(raw_v).strip()
        if not u or not v or u==v or u not in node_set or v not in node_set: raise ValueError("invalid DAG edge")
        if (u,v) not in seen: seen.add((u,v)); clean.append((u,v))
    parents={n:set() for n in ns}; children={n:set() for n in ns}
    for u,v in clean: parents[v].add(u); children[u].add(v)
    indeg={n:len(parents[n]) for n in ns}; ready=sorted(n for n in ns if indeg[n]==0); visited=0
    while ready:
        n=ready.pop(0); visited+=1
        for c in sorted(children[n]):
            indeg[c]-=1
            if indeg[c]==0: ready.append(c); ready.sort()
    if visited!=len(ns): raise ValueError("causal graph must be acyclic")
    return ns,tuple(sorted(clean))


def _ancestors(nodes:set[str],parents:Mapping[str,set[str]])->set[str]:
    anc=set(nodes); stack=list(nodes)
    while stack:
        n=stack.pop()
        for p in parents.get(n,()):
            if p not in anc: anc.add(p); stack.append(p)
    return anc


def _descendants(nodes:set[str],children:Mapping[str,set[str]])->set[str]:
    desc=set(); stack=list(nodes)
    while stack:
        n=stack.pop()
        for c in children.get(n,()):
            if c not in desc: desc.add(c); stack.append(c)
    return desc


def d_separated(*,nodes:Sequence[str],edges:Sequence[Edge],x:Sequence[str],y:Sequence[str],conditioned:Sequence[str]=())->bool:
    """Exact DAG d-separation via ancestral moralization."""
    ns,es=_validate_dag(nodes,edges); node_set=set(ns); X,Y=set(_clean_nodes(x)),set(_clean_nodes(y)); Z={str(z).strip() for z in conditioned}
    if not Z.issubset(node_set) or not X.issubset(node_set) or not Y.issubset(node_set): raise ValueError("query node outside DAG")
    if X&Y or X&Z or Y&Z: raise ValueError("X, Y and conditioned sets must be disjoint")
    parents={n:set() for n in ns}
    for u,v in es: parents[v].add(u)
    anc=_ancestors(X|Y|Z,parents); adj={n:set() for n in anc}
    for u,v in es:
        if u in anc and v in anc: adj[u].add(v); adj[v].add(u)
    for child in anc:
        ps=sorted(p for p in parents[child] if p in anc)
        for i,a in enumerate(ps):
            for b in ps[i+1:]: adj[a].add(b); adj[b].add(a)
    allowed=anc-Z; starts=X&allowed; targets=Y&allowed; seen=set(starts); stack=list(starts)
    while stack:
        n=stack.pop()
        if n in targets: return False
        for nxt in adj.get(n,()):
            if nxt in allowed and nxt not in seen: seen.add(nxt); stack.append(nxt)
    return True


@dataclass(frozen=True,slots=True)
class TransportabilityCertificate:
    treatment:tuple[str,...]; outcome:tuple[str,...]; adjustment:tuple[str,...]; selection_nodes:tuple[str,...]; s_admissible:bool; pre_treatment_adjustment:bool; source_interventional_available:bool; target_adjustment_distribution_available:bool; transportable:bool; formula:str|None; method:str="S_ADMISSIBLE_SELECTION_DIAGRAM_TRANSPORT_V1"


@dataclass(frozen=True,slots=True)
class TransportAdjustmentSearch:
    candidate_count:int
    transportable_count:int
    minimal_adjustments:tuple[tuple[str,...],...]
    certificates:tuple[TransportabilityCertificate,...]
    complete_for_declared_candidate_family:bool=True
    method:str="EXHAUSTIVE_MINIMAL_S_ADMISSIBLE_ADJUSTMENT_SEARCH_V1"


def certify_s_admissible_transport(*,causal_nodes:Sequence[str],causal_edges:Sequence[Edge],selection_edges:Sequence[Edge],treatment:Sequence[str],outcome:Sequence[str],adjustment:Sequence[str],source_interventional_available:bool,target_adjustment_distribution_available:bool)->TransportabilityCertificate:
    """Sound sufficient S-admissible transport certificate; not complete transportability."""
    c_nodes,c_edges=_validate_dag(causal_nodes,causal_edges); cset=set(c_nodes); X,Y=set(_clean_nodes(treatment)),set(_clean_nodes(outcome)); Z={str(z).strip() for z in adjustment if str(z).strip()}
    if not X.issubset(cset) or not Y.issubset(cset) or not Z.issubset(cset): raise ValueError("treatment/outcome/adjustment outside causal graph")
    if X&Y or X&Z or Y&Z: raise ValueError("treatment, outcome and adjustment must be disjoint")
    selection_nodes=set(); clean_selection=[]
    for raw_s,raw_v in selection_edges:
        s,v=str(raw_s).strip(),str(raw_v).strip()
        if not s or not v or v not in cset or s in cset: raise ValueError("selection edge must be S-node -> causal node")
        selection_nodes.add(s); clean_selection.append((s,v))
    if not selection_nodes: raise ValueError("at least one selection node required")
    children={n:set() for n in c_nodes}
    for u,v in c_edges: children[u].add(v)
    pre_treatment=not bool(Z&_descendants(X,children)); all_nodes=tuple(sorted(cset|selection_nodes)); mutilated=[e for e in c_edges if e[1] not in X]; mutilated.extend((s,v) for s,v in clean_selection if v not in X)
    s_admissible=d_separated(nodes=all_nodes,edges=mutilated,x=tuple(sorted(Y)),y=tuple(sorted(selection_nodes)),conditioned=tuple(sorted(X|Z)))
    transportable=bool(pre_treatment and s_admissible and source_interventional_available and target_adjustment_distribution_available)
    formula="P*(Y|do(X)) = sum_Z P_source(Y|do(X),Z) P_target(Z)" if transportable else None
    return TransportabilityCertificate(tuple(sorted(X)),tuple(sorted(Y)),tuple(sorted(Z)),tuple(sorted(selection_nodes)),s_admissible,pre_treatment,bool(source_interventional_available),bool(target_adjustment_distribution_available),transportable,formula)


def find_minimal_s_admissible_adjustments(*,causal_nodes:Sequence[str],causal_edges:Sequence[Edge],selection_edges:Sequence[Edge],treatment:Sequence[str],outcome:Sequence[str],source_interventional_available:bool,target_adjustment_distribution_available:bool)->TransportAdjustmentSearch:
    """Exhaust all legal pre-treatment Z subsets and return inclusion-minimal certificates."""
    c_nodes,c_edges=_validate_dag(causal_nodes,causal_edges); X,Y=set(_clean_nodes(treatment)),set(_clean_nodes(outcome)); children={n:set() for n in c_nodes}
    for u,v in c_edges: children[u].add(v)
    forbidden=X|Y|_descendants(X,children); candidates=tuple(sorted(set(c_nodes)-forbidden)); all_certs=[]
    for r in range(len(candidates)+1):
        for z in itertools.combinations(candidates,r):
            cert=certify_s_admissible_transport(causal_nodes=c_nodes,causal_edges=c_edges,selection_edges=selection_edges,treatment=tuple(sorted(X)),outcome=tuple(sorted(Y)),adjustment=z,source_interventional_available=source_interventional_available,target_adjustment_distribution_available=target_adjustment_distribution_available)
            if cert.transportable: all_certs.append(cert)
    sets=[set(c.adjustment) for c in all_certs]; minimal=[]
    for i,cert in enumerate(all_certs):
        if not any(sets[j] < sets[i] for j in range(len(sets)) if j!=i): minimal.append(cert.adjustment)
    return TransportAdjustmentSearch(2**len(candidates),len(all_certs),tuple(sorted(set(minimal),key=lambda z:(len(z),z))),tuple(all_certs))
