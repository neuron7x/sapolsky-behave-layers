"""Frozen UCI MONK's transfer. Training inputs never reach held-out scoring."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from fractions import Fraction
from itertools import product
from pathlib import Path
from zipfile import ZipFile

from cwc.epistemics.evidence_sequential import ObservationBranch, Tree, select_evidence_trees
from cwc.epistemics.evidence_value import EvidenceProbe

ARCHIVE_SHA256 = "7501acef87251b1d427726d7c381a2488c166fbbf70ac4096e09f05951c30a29"
DOMAINS = ((1, 2, 3), (1, 2, 3), (1, 2), (1, 2, 3), (1, 2, 3, 4), (1, 2))
COST = Fraction(1, 10)
Features = tuple[int, ...]


def _rows(raw: bytes) -> dict[Features, int]:
    expected = set(product(*DOMAINS))
    rows = {}
    ids = set()
    for line in raw.decode("ascii").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        label, *attributes = map(int, fields[:-1])
        features = tuple(attributes)
        if (label not in (0, 1) or features not in expected or features in rows
                or fields[-1] in ids or not fields[-1].startswith("data_")):
            raise ValueError("invalid MONK labels, attributes or identity")
        rows[features] = label
        ids.add(fields[-1])
    return rows


def _label(task: int, features: Features) -> int:
    a1, a2, _, a4, a5, _ = features
    if task == 1:
        return int(a1 == a2 or a5 == 1)
    if task == 2:
        return int(sum(a == 1 for a in features) == 2)
    return int((a5 == 3 and a4 == 1) or (a5 != 4 and a2 != 3))


def _utility(label: int) -> tuple[int, int, int]:
    return (0, 1, -1) if label == 0 else (0, -1, 1)


def _rank(task: int, features: Features) -> bytes:
    columns = ",".join(map(str, features))
    return hashlib.sha256(f"monk-evidence-v1|{task}|{columns}".encode()).digest()


def _fit(task: int, train: dict[Features, int]) -> dict[str, Tree]:
    nominal = []
    stress = []
    for label in (0, 1):
        ordered = sorted((x for x, y in train.items() if y == label), key=lambda row: (_rank(task, row), row))
        if len(ordered) < 4:
            raise ValueError("inadequate training roster")
        nominal.extend(ordered[:2])
        stress.extend(ordered[2:4])
    worlds = (*nominal, *stress)
    utilities = tuple(_utility(train[row]) for row in worlds)
    probes = [
        EvidenceProbe(str(index), COST, tuple((0, 1) if row[index] == 1 else (1, 0) for row in worlds))
        for index in range(3)
    ]
    result = select_evidence_trees(
        utilities=utilities, weights=(Fraction(1, 4),)*4 + (0,)*4,
        probes=probes, target=Fraction(1, 5),
    )
    fallback = max(range(3), key=lambda a: sum(row[a] for row in utilities[:4]))
    return {name: choice.tree if choice is not None else fallback
            for name, choice in zip(("adaptive", "fixed", "greedy"),
                                    (result.adaptive, result.fixed, result.greedy), strict=True)}


def _execute(tree: Tree, row: Features) -> tuple[int, int]:
    seen: set[str] = set()
    while isinstance(tree, ObservationBranch):
        if tree.probe_id in seen or len(seen) >= 2:
            raise ValueError("tree exceeds the frozen observation budget")
        seen.add(tree.probe_id)
        tree = tree.one if row[int(tree.probe_id)] == 1 else tree.zero
    return tree, len(seen)


def _measure(tree: Tree, rows: dict[Features, int]) -> dict[str, int | str]:
    correct = wrong = abstained = spent = 0
    for features, truth in rows.items():
        action, units = _execute(tree, features)
        spent += units
        correct += int(action == truth + 1)
        wrong += int(action != 0 and action != truth + 1)
        abstained += int(action == 0)
    if correct + wrong + abstained != len(rows):
        raise ValueError("incomplete held-out replay")
    net = (correct - wrong - COST * spent) / len(rows)
    return {"correct": correct, "wrong": wrong, "abstained": abstained,
            "probes": spent, "mean_net_utility": str(net)}


def run(source: Path) -> dict:
    if hashlib.sha256(source.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("unexpected UCI archive digest")
    tasks = []
    differences: dict[str, list[Fraction]] = {"fixed": [], "greedy": []}
    with ZipFile(source) as archive:
        for task in (1, 2, 3):
            train = _rows(archive.read(f"monks-{task}.train"))
            test = _rows(archive.read(f"monks-{task}.test"))
            if set(test) != set(product(*DOMAINS)) or not set(train) <= set(test):
                raise ValueError("incomplete UCI universe")
            if any(_label(task, features) != label for features, label in test.items()):
                raise ValueError("test labels differ from CMU rules")
            held = {x: y for x, y in test.items() if x not in train}
            policies = _fit(task, train)
            scores = {name: _measure(tree, held) for name, tree in policies.items()}
            for alternative in differences:
                differences[alternative].append(
                    Fraction(scores["adaptive"]["mean_net_utility"]) -
                    Fraction(scores[alternative]["mean_net_utility"])
                )
            tasks.append({"task": task, "train": len(train), "held_out": len(held), "results": scores,
                          "policies": {name: asdict(tree) if isinstance(tree, ObservationBranch) else tree
                                       for name, tree in policies.items()}})
    passed = all(min(values) >= 0 and max(values) > 0 for values in differences.values())
    return {"schema": "cwc-evidence-monk-v1", "source_sha256": ARCHIVE_SHA256, "tasks": tasks,
            "transfer": "SUPPORTED_ON_PANEL" if passed else "NOT_SUPPORTED_ON_PANEL"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.source), sort_keys=True, indent=2))
