"""CNEH-EXP-04: finite-family active structural reidentification pilot."""
from __future__ import annotations

import argparse
import itertools
import math
import random
from pathlib import Path
from typing import Any

from experiments.cneh_exp_01 import bnsyn_adapter as pinned

HERE = Path(__file__).resolve().parent
A = .6
NOISE = .005
EPS = NOISE * (2 + A) + 1e-12
GOAL = .3
BOUND = .5
STEPS = 80
MODES = ((.8, 0.), (-.8, 0.), (0., .8), (0., -.8))
ARMS = ("ACTIVE_REID", "EXACT_EMULATOR", "PERIODIC_REID", "STATIC_NOMINAL", "ORACLE")
GRID = tuple((i/8., j/8.) for i in range(-4,5) for j in range(-4,5) if abs(i)+abs(j) <= 4)
SEEDS = tuple(range(85001, 85065)) + tuple(range(85101, 85109))


def dot(b: tuple[float, float], u: tuple[float, float]) -> float:
    return b[0]*u[0] + b[1]*u[1]


def action_check(u: tuple[float, float]) -> None:
    if len(u) != 2 or not all(math.isfinite(v) for v in u) or sum(abs(v) for v in u) > BOUND:
        raise ValueError("invalid action envelope")


def compatible(candidates: tuple[int, ...], residual: float, u: tuple[float, float]) -> tuple[int, ...]:
    action_check(u)
    if not math.isfinite(residual) or not candidates or len(set(candidates)) != len(candidates):
        raise ValueError("invalid candidate update")
    if any(type(i) is not int or not 0 <= i < len(MODES) for i in candidates):
        raise ValueError("invalid model identity")
    return tuple(i for i in candidates if abs(residual - dot(MODES[i], u)) <= EPS)


def separation(candidates: tuple[int, ...], u: tuple[float, float]) -> float:
    if len(candidates) < 2:
        raise ValueError("ambiguity required")
    return min(abs(dot(MODES[i], u)-dot(MODES[j], u)) for i,j in itertools.combinations(candidates,2))


def active_probe(candidates: tuple[int, ...]) -> tuple[float, float]:
    u = min(GRID, key=lambda x: (-separation(candidates,x),sum(abs(v) for v in x),x))
    if separation(candidates,u) <= 2*EPS:
        raise ValueError("finite model family is not separable by admissible probe")
    return u


def sentinel(tick: int) -> tuple[float, float] | None:
    return ((.25,0.) if tick%8 == 0 else (0.,.25)) if tick%4 == 0 else None


def known_control(mode: int, y: float) -> tuple[float, float]:
    b = MODES[mode]
    k = 0 if b[0] else 1
    v = max(-BOUND,min(BOUND,(GOAL-A*y)/b[k]))
    return (v,0.) if k == 0 else (0.,v)


def robust_control(candidates: tuple[int, ...], y: float) -> tuple[float, float]:
    return min(GRID, key=lambda u: (max(abs(A*y+dot(MODES[i],u)-GOAL) for i in candidates),
                                    sum(abs(v) for v in u),u))


class Controller:
    """Only observations, previous own action, public parameters and time."""

    def __init__(self, active: bool, static: bool = False):
        self.active = active
        self.static = static
        self.candidates = (0,)
        self.detected = None
        self.identified = None
        self.previous_y = None
        self.previous_u = None

    def observe(self, tick: int, y: float) -> None:
        if not math.isfinite(y):
            raise ValueError("invalid observation")
        if self.previous_y is not None and not self.static:
            if self.previous_u is None:
                raise ValueError("missing executed action")
            r = y - A*self.previous_y
            if self.detected is None:
                if not compatible((0,), r, self.previous_u):
                    self.detected = tick
                    self.candidates = compatible(tuple(range(len(MODES))),r,self.previous_u)
            else:
                self.candidates = compatible(self.candidates,r,self.previous_u)
            if not self.candidates:
                raise ValueError("MODEL_SET_VIOLATION")
            if self.detected is not None and self.identified is None and len(self.candidates) == 1:
                self.identified = tick
        self.previous_y = y

    def act(self, tick: int) -> tuple[tuple[float,float], str]:
        if self.previous_y is None:
            raise ValueError("observation required")
        scheduled = sentinel(tick)
        if self.active and len(self.candidates)>1:
            u,kind = active_probe(self.candidates),"ACTIVE_PROBE"
        elif scheduled is not None:
            u,kind = scheduled,"SENTINEL"
        elif len(self.candidates)==1:
            u,kind = known_control(self.candidates[0],self.previous_y),"TRACK"
        else:
            u,kind = robust_control(self.candidates,self.previous_y),"ROBUST_TRACK"
        action_check(u)
        self.previous_u = u
        return u,kind


def world(seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("unregistered seed")
    rng = random.Random(seed)
    changed = seed < 85101
    tau = rng.randrange(20,40) if changed else None
    mode = rng.randrange(1,4) if changed else 0
    return {"seed":seed,"tau":tau,"mode":mode,
            "w":[rng.uniform(-NOISE,NOISE) for _ in range(STEPS)],
            "v":[rng.uniform(-NOISE,NOISE) for _ in range(STEPS+1)]}


def execute(w: dict[str, Any], arm: str) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError("unknown arm")
    ctrl = Controller(active=arm in ARMS[:2], static=arm==ARMS[3])
    x = 0.
    rows = []
    for t in range(STEPS+1):
        y = x+w["v"][t]
        ctrl.observe(t,y)
        # The true mode stays evaluator-side. Only the explicitly privileged
        # ORACLE can use it for an action. Ordinary controllers receive y/t.
        tau = w["tau"]
        active_mode = w["mode"] if tau is not None and t>=tau else 0
        previous_mode = w["mode"] if tau is not None and t>tau else 0
        if ctrl.detected is not None and previous_mode not in ctrl.candidates:
            raise ValueError("true mode eliminated under declared bounded noise")
        if not math.isfinite(x) or abs(x)>2.:
            raise ValueError("state safety invariant violated")
        row = {"tick":t,"x":x.hex(),"y":y.hex(),"candidates":list(ctrl.candidates),
               "detected":ctrl.detected,"identified":ctrl.identified}
        if t==STEPS:
            rows.append(row)
            break
        if arm=="ORACLE":
            u=sentinel(t)
            kind="SENTINEL" if u is not None else "ORACLE_TRACK"
            if u is None:
                u=known_control(active_mode,y)
            ctrl.previous_u=u
            # Oracle does not use the nominal change detector for admission.
            ctrl.static=True
        else:
            u,kind=ctrl.act(t)
        action_check(u)
        row.update(u=[q.hex() for q in u],action_kind=kind)
        rows.append(row)
        x=A*x+dot(MODES[active_mode],u)+w["w"][t]
    tau=w["tau"]
    start=0 if tau is None else tau+1
    xs=[float.fromhex(r["x"]) for r in rows[start:]]
    error=[abs(q-GOAL) for q in xs]
    post=[r for r in rows if "u" in r]
    l1=math.fsum(abs(float.fromhex(v)) for r in post for v in r["u"])
    l2=math.fsum(float.fromhex(v)**2 for r in post for v in r["u"])
    return {"seed":w["seed"],"arm":arm,"detect_tick":ctrl.detected,
            "identify_tick":ctrl.identified,"final_candidates":list(ctrl.candidates),
            "post_mean_abs_error":math.fsum(error)/len(error),
            "final16_mean_abs_error":math.fsum(error[-16:])/16,
            "post_goal_band_fraction":sum(e<=.05 for e in error)/len(error),
            "action_l1_proxy":l1,"action_l2_proxy":l2,
            "active_probes":sum(r.get("action_kind")=="ACTIVE_PROBE" for r in rows),
            "sentinels":sum(r.get("action_kind")=="SENTINEL" for r in rows),"trace":rows}


def pair(w: dict[str, Any], episodes: list[dict[str,Any]]) -> dict:
    by={e["arm"]:e for e in episodes}
    if len(episodes)!=len(ARMS) or set(by)!=set(ARMS):
        raise ValueError("incomplete arm set")
    if {k:v for k,v in by[ARMS[0]].items() if k!="arm"} != {k:v for k,v in by[ARMS[1]].items() if k!="arm"}:
        raise ValueError("exact centralized emulator mismatch")
    active=by[ARMS[0]]
    tau=w["tau"]
    for arm in ARMS[:3]:
        e=by[arm]
        if tau is None:
            if e["detect_tick"] is not None or e["identify_tick"] is not None:
                raise ValueError("false positive in no-change world")
        elif e["detect_tick"] is not None and e["detect_tick"]<=tau:
            raise ValueError("premature detection")
        if e["identify_tick"] is not None and e["final_candidates"] != [w["mode"]]:
            raise ValueError("incorrect singleton")
    if tau is not None:
        if active["detect_tick"] is None or active["identify_tick"] is None:
            raise ValueError("active identification absent")
        if active["detect_tick"]-tau>8 or active["identify_tick"]-tau>9 or active["final_candidates"]!=[w["mode"]]:
            raise ValueError("finite-family detection/identification theorem falsified")
    return {"seed":w["seed"],"tau":tau,"true_mode":w["mode"],
            "active_detect_delay":None if tau is None else active["detect_tick"]-tau,
            "active_identify_delay":None if tau is None else active["identify_tick"]-tau,
            "endpoints":{arm:{k:v for k,v in ep.items() if k not in ("trace","arm","seed")} for arm,ep in by.items()},
            "paired_active_tracking_error_advantage":{arm:by[arm]["post_mean_abs_error"]-active["post_mean_abs_error"] for arm in ARMS[2:4]},
            "exact_emulator_equal":True}


def payload() -> dict[str,bytes]:
    all_episodes, outcomes=[],[]
    for seed in SEEDS:
        w=world(seed)
        eps=[execute(w,arm) for arm in ARMS]
        outcomes.append(pair(w,eps))
        all_episodes.extend(eps)
    ood=[x for x in outcomes if x["tau"] is not None]
    report={"experiment":"CNEH-EXP-04","authority":"FINITE_MODEL_FAMILY_SYNTHETIC_ONLY",
            "worlds":len(outcomes),"ood_worlds":len(ood),"no_change_worlds":len(outcomes)-len(ood),
            "episodes":len(all_episodes),"max_detect_delay":max(x["active_detect_delay"] for x in ood),
            "max_identify_delay":max(x["active_identify_delay"] for x in ood),
            "exact_emulator_equal_worlds":sum(x["exact_emulator_equal"] for x in outcomes),
            "mean_post_error":{arm:math.fsum(x["endpoints"][arm]["post_mean_abs_error"] for x in ood)/len(ood) for arm in ARMS},
            "mean_paired_active_tracking_error_advantage":{arm:math.fsum(x["paired_active_tracking_error_advantage"][arm] for x in ood)/len(ood) for arm in ARMS[2:4]},
            "scientific_promotion_authorized":False,"independent_replication":"REPLICATION_NOT_TESTED",
            "physical_energy":"INSTRUMENT_INVALID"}
    return {"preregistration.md":(HERE/"PREREGISTRATION.md").read_bytes(),
            "implementation.json":pinned.canonical({"sha256":pinned.sha(Path(__file__).read_bytes())}),
            "episodes.json":pinned.canonical(all_episodes),"worlds.json":pinned.canonical(outcomes),
            "verdict.json":pinned.canonical(report)}


def manifest(files: dict[str,bytes]) -> bytes:
    return "".join(f"{pinned.sha(files[k])}  {k}\n" for k in sorted(files)).encode("ascii")


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify",action="store_true")
    args=p.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    files=payload()
    if not args.verify:
        args.out.mkdir(parents=True,exist_ok=False)
        for k,v in files.items():
            (args.out/k).write_bytes(v)
        (args.out/"SHA256SUMS").write_bytes(manifest(files))
    if args.out.is_symlink() or not args.out.is_dir():
        raise ValueError("invalid evidence directory")
    entries=list(args.out.iterdir())
    if any(x.is_symlink() or not x.is_file() for x in entries) or {x.name for x in entries}!=set(files)|{"SHA256SUMS"}:
        raise ValueError("evidence roster mismatch")
    if (args.out/"SHA256SUMS").read_bytes()!=manifest(files):
        raise ValueError("manifest differs from replay")
    for k,v in files.items():
        if (args.out/k).read_bytes()!=v:
            raise ValueError(f"replay mismatch: {k}")
    print(files["verdict.json"].decode().strip())


if __name__=="__main__":
    main()
