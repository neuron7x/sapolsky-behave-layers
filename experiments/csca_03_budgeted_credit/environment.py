from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Callable

PLAYERS = ("A", "B", "C", "D")


def stable_seed(*parts: object) -> int:
    payload = "|".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


@dataclass(frozen=True, slots=True)
class Case:
    family: str
    context: int
    A: int
    B: int
    C: int
    D: int
    U: int
    epsilon: float
    gamma: float

    @property
    def factual(self) -> dict[str, int]:
        return {"A": self.A, "B": self.B, "C": self.C, "D": self.D}


def make_evaluator(case: Case, *, model: str = "TRUE") -> Callable[[dict[str, int]], float]:
    def true_single(x: dict[str, int]) -> float:
        return 1.0 * x["A"] + case.gamma * case.U + case.epsilon

    def true_interaction(x: dict[str, int]) -> float:
        return (
            1.0 * x["A"]
            + 0.7 * x["B"]
            + 0.8 * case.context * x["A"] * x["B"]
            + case.gamma * case.U
            + case.epsilon
        )

    def true_sign_flip(x: dict[str, int]) -> float:
        return float(case.context) * x["A"] + case.gamma * case.U + case.epsilon

    if case.family in {"E0_SINGLE_CAUSE", "E3_PRECISELY_WRONG_MODEL"}:
        true = true_single
    elif case.family == "E1_TWO_CAUSE_INTERACTION":
        true = true_interaction
    elif case.family == "E2_CONTEXT_SIGN_FLIP":
        true = true_sign_flip
    else:
        raise ValueError(case.family)

    if model == "TRUE":
        return true
    if model == "WRONG_SHARED_SPURIOUS_EDGE":
        if case.family != "E3_PRECISELY_WRONG_MODEL":
            raise ValueError("wrong evaluator only valid for E3")
        alpha = 0.90

        def wrong(x: dict[str, int]) -> float:
            return (1.0 - alpha) * x["A"] + alpha * x["C"] + case.gamma * case.U + case.epsilon

        return wrong
    raise ValueError(model)


def generate_cases(*, family: str, seed: int, n: int = 64) -> list[Case]:
    cases: list[Case] = []
    contexts = (-1, 1) if family in {"E1_TWO_CAUSE_INTERACTION", "E2_CONTEXT_SIGN_FLIP"} else (-1, 1, 2)
    for context_label in contexts:
        rng = random.Random(stable_seed(family, seed, context_label, "data"))
        for _ in range(n):
            A = -1 if rng.random() < 0.5 else 1
            U = -1 if rng.random() < 0.5 else 1
            D = -1 if rng.random() < 0.5 else 1
            epsilon = rng.gauss(0.0, 0.20)
            if family == "E1_TWO_CAUSE_INTERACTION":
                B = -1 if rng.random() < 0.5 else 1
                C = U if rng.random() > 0.05 else -U
                gamma = 0.6
                context = int(context_label)
            elif family == "E2_CONTEXT_SIGN_FLIP":
                B = A if rng.random() < 0.80 else -A
                C = U if rng.random() > 0.08 else -U
                gamma = 0.5
                context = int(context_label)
            elif family == "E3_PRECISELY_WRONG_MODEL":
                B = A if rng.random() < 0.80 else -A
                C = A if rng.random() > 0.01 else -A
                gamma = 0.5
                context = 1 if context_label != -1 else -1
            else:
                B = A if rng.random() < 0.80 else -A
                if context_label == 2:
                    C = U if rng.random() > 0.08 else -U
                    gamma = 2.0
                    context = 1
                elif context_label == 1:
                    C = U if rng.random() > 0.08 else -U
                    gamma = 0.25
                    context = 1
                else:
                    C = -U if rng.random() > 0.08 else U
                    gamma = 1.5
                    context = -1
            cases.append(Case(family, context, A, B, C, D, U, epsilon, gamma))
    return cases
