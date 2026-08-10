"""Exploratory robustness sweep for the qualified synthetic CDL-V2 control.

No confirmatory or claim-upgrade authority.  Sweeps acquisition size, true-outcome
noise, and observational descendant noise to test whether the V2 gain is confined
to one hand-picked parameter point.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from cwc.memory.causal_debt import CausalDebtLedger, ReplayEvidence
from cwc.replay.scheduler import choose_candidate, choose_least_covered_context

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "causal-debt-v2-stress"
SEEDS = [101,211,307,401,503,601,701,809,907,1009,1103,1201,1301,1409,1511,1601,1709,1801,1901,2003]
POLICIES = ["causal_debt_v2_cf", "uniform_cf", "rpe_cf"]
BUDGET = 16


@dataclass(frozen=True, slots=True)
class Unit:
    context: str
    c: int
    s: int
    n: int
    eps: int

    @property
    def y(self) -> int:
        return self.c ^ self.eps

    def feature(self, cid: str) -> int:
        return {"C": self.c, "S": self.s, "N": self.n}[cid]


def bern(rng: random.Random, p: float) -> int:
    return int(rng.random() < p)


def sample(rng: random.Random, *, context: str, outcome_noise: float, spur_noise: float) -> Unit:
    c = bern(rng, 0.5)
    n = bern(rng, 0.5)
    eps = bern(rng, outcome_noise)
    y = c ^ eps
    if context == "same":
        s = y ^ bern(rng, spur_noise)
    elif context == "decorrelated":
        s = bern(rng, 0.5)
    elif context == "reversed":
        s = (1 - y) ^ bern(rng, spur_noise)
    else:
        raise ValueError(context)
    return Unit(context, c, s, n, eps)


def obs_effect(units: list[Unit], cid: str) -> float:
    return sum((2*u.feature(cid)-1)*(2*u.y-1) for u in units)/len(units)


def cf_effect(unit: Unit, cid: str) -> float:
    if cid == "C":
        ycf = (1-unit.c) ^ unit.eps
    else:
        ycf = unit.y
    return float((unit.y-ycf)*(2*unit.feature(cid)-1))


def weights(policy: str, *, obs: dict[str,float], outcome_noise: float, spur_noise: float, rng: random.Random):
    ledger=CausalDebtLedger(min_replays=3,min_contexts=2,min_abs_credit=0.15,z_value=1.64)
    for cid,v in obs.items():
        ledger.register(cid,eligibility=abs(v),observational_credit=v)
    counts={cid:0 for cid in ledger.candidate_ids}
    contexts=("same","decorrelated","reversed")
    for step in range(BUDGET):
        cid=choose_candidate(policy,ledger=ledger,observational_strength=obs,replay_counts=counts,rng=rng,fifo_index=step)
        ctx=choose_least_covered_context(cid,contexts=contexts,ledger=ledger,rng=rng,randomize=policy!="causal_debt_v2_cf")
        u=sample(rng,context=ctx,outcome_noise=outcome_noise,spur_noise=spur_noise)
        eff=cf_effect(u,cid)
        ledger.append(ReplayEvidence(cid,ctx,eff,abs(eff)))
        counts[cid]+=1
    out={}
    for cid in ledger.candidate_ids:
        d=ledger.consolidation(cid)
        if d.consolidated: out[cid]=d.credit
    return out


def predict(u: Unit, w: dict[str,float]) -> int:
    score=sum(math.copysign(1.0,v)*(2*u.feature(cid)-1) for cid,v in w.items() if v)
    return int(score>0)


def main() -> int:
    rows=[]
    for acquisition_n in (64,256):
      for outcome_noise in (0.05,0.10,0.20,0.30):
       for spur_noise in (0.02,0.10):
        setting=f"n{acquisition_n}-y{outcome_noise:.2f}-s{spur_noise:.2f}"
        for seed in SEEDS:
          ar=random.Random(seed*100003+acquisition_n+int(outcome_noise*1000)+int(spur_noise*10000))
          acquisition=[sample(ar,context="same",outcome_noise=outcome_noise,spur_noise=spur_noise) for _ in range(acquisition_n)]
          obs={cid:obs_effect(acquisition,cid) for cid in ("C","S","N")}
          er=random.Random(seed*100019+acquisition_n)
          eval_units=[sample(er,context=ctx,outcome_noise=outcome_noise,spur_noise=spur_noise) for ctx in ("decorrelated","reversed") for _ in range(512)]
          for policy in POLICIES:
            pr=random.Random(seed*1000003+sum(map(ord,policy+setting)))
            w=weights(policy,obs=obs,outcome_noise=outcome_noise,spur_noise=spur_noise,rng=pr)
            acc=sum(predict(u,w)==u.y for u in eval_units)/len(eval_units)
            rows.append({"setting":setting,"seed":seed,"policy":policy,"oos":acc,"recall":int("C" in w),"false_credit":int("S" in w or "N" in w)})
    OUT.mkdir(parents=True,exist_ok=True)
    raw=OUT/'raw_results.jsonl'
    raw.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    settings=sorted(set(r['setting'] for r in rows))
    summary={}
    positive={"uniform_cf":0,"rpe_cf":0}
    for setting in settings:
      summary[setting]={}
      for policy in POLICIES:
        cell=[r for r in rows if r['setting']==setting and r['policy']==policy]
        summary[setting][policy]={"mean_oos":sum(r['oos'] for r in cell)/len(cell),"recall":sum(r['recall'] for r in cell)/len(cell),"false_credit":sum(r['false_credit'] for r in cell)/len(cell)}
      for control in ("uniform_cf","rpe_cf"):
        if summary[setting]["causal_debt_v2_cf"]["mean_oos"] > summary[setting][control]["mean_oos"]:
          positive[control]+=1
    result={
      "schema":"cwc-cdl-v2/stress-1",
      "confirmatory":False,
      "claim_upgrade_authority":False,
      "settings":len(settings),
      "budget":BUDGET,
      "positive_setting_count":positive,
      "summary":summary,
    }
    rp=OUT/'stress.json'; rp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (OUT/'SHA256SUMS').write_text('\n'.join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in (raw,rp))+'\n')
    print(json.dumps({"settings":len(settings),"positive_setting_count":positive},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
