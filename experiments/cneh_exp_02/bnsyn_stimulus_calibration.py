"""Source-pinned BN-Syn AdEx stimulus-response CALIBRATION (not CNEH evidence).

After an initial 48-step 120pA bridge produced zero spikes, this separate
post-observation diagnostic maps excitability before any new preregistered
cognitive-neural experiment. No threshold was tuned to obtain CNEH support.
"""
from __future__ import annotations
import argparse
import math
import json
import sys
from pathlib import Path
from typing import Any

from experiments.cneh_exp_02.bnsyn_bridge import assert_bn_source,canon,sha

CURRENTS_PA=(0.0,120.0,240.0,360.0,480.0)
CALIB_SEEDS=(41001,41002,41003,41004)
CALIB_STEPS=192
CALIB_DT_MS=0.25
NEURONS=32


def evaluate(source:Path)->dict[str,Any]:
    pin=assert_bn_source(source)
    sys.path.insert(0,str(source/"src"))
    import numpy as np
    from bnsyn.config import AdExParams, SynapseParams, CriticalityParams
    from bnsyn.sim.network import Network,NetworkParams
    grid=[]
    for level in CURRENTS_PA:
        for seed in CALIB_SEEDS:
            adex=AdExParams()
            net=Network(
                NetworkParams(N=NEURONS,frac_inhib=0.25,p_conn=0.1,ext_rate_hz=2.0),
                adex,SynapseParams(),CriticalityParams(),dt_ms=CALIB_DT_MS,
                rng=np.random.default_rng(seed),backend="reference",
            )
            curr=np.full(NEURONS,level,dtype=np.float64)
            spike_a=0
            spike_b=0
            maxima=[]
            for _ in range(CALIB_STEPS):
                net.step(external_current_pA=curr)
                spike_a+=int(np.sum(net.state.spiked[:NEURONS//2]))
                spike_b+=int(np.sum(net.state.spiked[NEURONS//2:]))
                maxima.append(float(np.max(net.state.V_mV)))
            final_mean=float(np.mean(net.state.V_mV))
            max_voltage=float(max(maxima))
            if not math.isfinite(final_mean) or not math.isfinite(max_voltage):
                raise ValueError("nonfinite AdEx voltage in reference calibration")
            grid.append({
                "seed":seed,"injected_current_pA":level,
                "spike_count_population_A":spike_a,
                "spike_count_population_B":spike_b,
                "final_mean_voltage_mV":round(final_mean,9),
                "max_voltage_mV":round(max_voltage,9),
            })
    spike_coverage=any(
        x["spike_count_population_A"]+x["spike_count_population_B"]>0
        for x in grid
    )
    return {
        "source":pin,"purpose":"post-primary engineering stimulus calibration only",
        "calibration_grid_pA":list(CURRENTS_PA),"seeds":list(CALIB_SEEDS),
        "steps":CALIB_STEPS,"dt_ms":CALIB_DT_MS,"cells":grid,
        "at_least_one_spiking_cell":spike_coverage,
        "verdict":"SPIKING_RESPONSE_MEASURED" if spike_coverage else "NO_SPIKE_RESPONSE_AT_TESTED_STIMULI",
        "scientific_CNEH_promotion":False,
        "claim_boundary":"Stimulus-response calibration, not coupled neural intelligence, biology validation or causal emergence",
    }


def payload(source:Path)->dict[str,bytes]:
    v=evaluate(source)
    return {
        "stimulus_grid.json":canon(v),
        "verdict.json":canon({
            "stimulus_status":v["verdict"],
            "CNEH_supported":False,
            "primary_CNEH_EXP_02_modified":False,
            "independent_replication":False,
        }),
    }


def write(dest:Path,files:dict[str,bytes])->None:
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError("evidence immutable")
    dest.mkdir(parents=True,exist_ok=True)
    for name,content in files.items():
        (dest/name).write_bytes(content)
    (dest/"SHA256SUMS").write_text(
        "".join(f"{sha(files[k])}  {k}\n" for k in sorted(files)),encoding="ascii",
    )


def verify(dest:Path,source:Path)->None:
    if not dest.is_dir() or dest.is_symlink():
        raise ValueError("invalid source calibration evidence")
    files=payload(source)
    expected={*files,"SHA256SUMS"}
    if {p.name for p in dest.iterdir()}!=expected:
        raise ValueError("incomplete source calibration evidence")
    for name,content in files.items():
        if (dest/name).read_bytes()!=content:
            raise ValueError("replay mismatch in stimulus calibration")
    sha_lines="".join(f"{sha(files[k])}  {k}\n" for k in sorted(files))
    if (dest/"SHA256SUMS").read_text(encoding="ascii")!=sha_lines:
        raise ValueError("invalid calibration SHA256SUMS")


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--bnsyn-root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if not args.verify:
        write(args.out,payload(args.bnsyn_root))
    verify(args.out,args.bnsyn_root)
    status=json.loads((args.out/"verdict.json").read_text())["stimulus_status"]
    print("BN-Syn independent stimulus calibration:",status,"(CNEH scientific status unchanged)")


if __name__=="__main__":
    main()
