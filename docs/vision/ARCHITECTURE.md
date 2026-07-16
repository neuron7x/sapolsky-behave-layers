# Executable Architecture

## 1. System boundary

CWK is a research kernel, not a production assistant. Its first implementation is deliberately small enough to execute locally and inspect completely. Scale is introduced only after causal value is demonstrated at smaller matched budgets.

## 2. Runtime data flow

```text
Typed Observation
      │
      ▼
World Coupling Port ──► Input Encoder
      │                    │
      │                    ▼
      │             Working-State Tokens
      │                    │
      │          ┌─────────┴─────────┐
      │          ▼                   ▼
      │   Sparse Local/Global   Memory Reader
      │       Communication          │
      │          └─────────┬─────────┘
      │                    ▼
      │             Transit Governor
      │                    │ route + confidence + budget
      │                    ▼
      │              Expert Ecology
      │                    │
      │                    ▼
      │        Metacognitive Budget Governor
      │          ┌─────────┴─────────┐
      │          ▼                   ▼
      │      continue            terminate
      │          │                   │
      └──────────┴──────────────► Output / Action
                                   │
                                   ▼
                           Evidence Spine
```

## 3. Typed contracts

### CognitivePacket

```text
packet_id, modality, payload, timestamp, source, confidence, permissions
```

### ActivationBudget

```text
max_active_experts
max_attention_density
max_memory_reads
max_memory_writes
max_depth
max_latency_ms
max_peak_memory_bytes
```

### RouteDecision

```text
selected_experts
normalized_weights
route_entropy
capacity_pressure
overflow_count
fallback_used
router_version
```

### MemoryTrace

```text
trace_id
key
value
source_packet_ids
write_policy
retention_class
created_at
expires_at
content_hash
```

### TopologyDelta

```text
base_topology_hash
proposed_edges_added
proposed_edges_removed
utility_evidence
constraint_checks
commit_hash
rollback_pointer
```

## 4. Topology model

The fabric is represented by `G=(V,E,X,T)`:

- `V`: functional nodes;
- `E`: directed weighted communication edges;
- `X`: optional coordinates or learned placement vectors;
- `T`: node and edge types.

The reference implementation begins with a ring-local graph plus sparse deterministic long-range bridges. This is a test substrate, not a claim that this topology is optimal.

Normalized wiring cost:

```text
C_wire = Σ_(i,j in E) a_ij · d(x_i, x_j) / C_wire_baseline
```

Communication cost:

```text
C_comm = Σ routed_messages bytes(message) · edge_cost / baseline
```

Topological value SHALL be measured separately through path length, reachability, robustness and task performance.

## 5. Routing model

The router computes scores `s = f_router(h)` and applies a dynamically maintained non-gradient bias `b` before Top-K selection:

```text
I = TopK(s + b, k)
p = softmax((s_I + b_I) / τ)
```

The bias may be updated from recent expert load to reduce collapse without injecting a task-loss gradient. The reference implementation exposes this mechanism but does not claim equivalence to any external model.

## 6. Expert ecology

Each layer contains:

- one shared expert, always available;
- `N` routed experts;
- a residual path;
- capacity and overflow accounting.

Output:

```text
y = residual(x) + α_shared E_shared(x) + Σ_i∈I p_i E_i(x)
```

Specialization is evaluated by route mutual information, intervention effects and representational similarity—not by utilization alone.

## 7. Memory stratigraphy

The local reference kernel implements bounded episodic key–value memory. Retrieval is cosine Top-K. Writes are explicit and disabled during evaluation unless preregistered. Future layers may add trainable test-time memory, but they must preserve separation between immutable model parameters and mutable session state.

## 8. Structural plasticity

The first plasticity controller operates between training phases:

1. collect edge utility and route statistics;
2. propose removal of persistently low-utility edges;
3. propose growth toward under-connected or high-demand regions;
4. validate connectivity, budget and regression constraints;
5. commit a versioned topology only if validation passes.

No topology mutation occurs silently inside a benchmark.

## 9. Metacognitive budget control

The budget governor receives uncertainty, route entropy, memory confidence and remaining resource budget. Initial implementation supports fixed budgets; learned budget selection is Phase 3 work. This ordering prevents an unvalidated controller from confounding evaluation of the kernel.

## 10. Evidence and claim architecture

Every run produces:

```text
manifest.json
config.resolved.yaml
environment.json
metrics.jsonl
topology.json
stdout.log
artifacts.sha256
claim_candidate.json (optional)
```

The Claim Firewall validates these files against schemas and policy before any result is labeled beyond `observation`.
