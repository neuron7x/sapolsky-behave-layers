"""Real-source BN-Syn ↔ CNEH Cortex data-plane integration (RESEARCH ONLY).

This is a bounded engineer's interface/smoke test with a pinned external BN-Syn
checkout. It demonstrates two feedback signals and two controlled input
channels on an AdEx network, NOT neural intelligence or CNEH emergence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent
EXPECTED_BNSYN_SHA="c1de425ce4ece362e7f2feb2d9f24da5d3231014"
N_NEURONS=32
STEPS=48
DT_MS=0.25


def canon(v:Any)->bytes:
    return (json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def sha(v:bytes)->str:
    return hashlib.sha256(v).hexdigest()


def assert_bn_source(source:Path)->dict[str,str]:
    if not (source/"src/bnsyn/sim/network.py").is_file():
        raise FileNotFoundError("BN-Syn source boundary not present")
    commit=subprocess.run(
        ["git","-C",str(source),"rev-parse","HEAD"],
        check=True,capture_output=True,text=True,
    ).stdout.strip()
    if commit!=EXPECTED_BNSYN_SHA:
        raise ValueError("unpinned BN-Syn version; refuse scientific replay")
    dirty=subprocess.run(
        ["git","-C",str(source),"status","--porcelain","--untracked-files=no"],
        check=True,capture_output=True,text=True,
    ).stdout
    if dirty.strip():
        raise ValueError("BN-Syn working source modified")
    return {
        "repository":"neuron7x/bnsyn-phase-controlled-emergent-dynamics",
        "source_sha":commit,
        "module":"src/bnsyn/sim/network.py",
        "module_sha256":sha((source/"src/bnsyn/sim/network.py").read_bytes()),
    }


def finite(value:Any)->float|None:
    try:
        number=float(value)
    except (TypeError,ValueError):
        return None
    return round(number,9) if math.isfinite(number) else None


def run_cortex_bnsyn(seed:int,arm:str,source:Path)->dict[str,Any]:
    if arm not in ("COUPLED","CENTRAL_EMULATOR","DISCONNECTED"):
        raise ValueError("not a qualified BN-Syn bridge arm")
    assert_bn_source(source)
    sys.path.insert(0,str(source/"src"))
    import numpy as np
    from bnsyn.config import AdExParams, CriticalityParams, SynapseParams
    from bnsyn.sim.network import Network, NetworkParams
    from experiments.cneh_exp_02.run import Cortex, null_packet
    proto=json.loads((HERE/"protocol.json").read_text(encoding="utf-8"))
    adex=AdExParams()
    net=Network(
        NetworkParams(N=N_NEURONS,frac_inhib=0.25,p_conn=0.1,ext_rate_hz=2.0),
        adex,SynapseParams(),CriticalityParams(),
        dt_ms=DT_MS,rng=np.random.default_rng(seed),backend="reference",
    )
    ca,cb=Cortex(0,proto),Cortex(1,proto)
    records=[]
    total_current_proxy=0.0
    spike_count_a=spike_count_b=0
    for tick in range(STEPS):
        # Independent *real* AdEx population telemetry is observed by each
        # cortex, centered at the reference resting potential (not a BCI).
        v0=float(np.mean(net.state.V_mV[:N_NEURONS//2]))
        v1=float(np.mean(net.state.V_mV[N_NEURONS//2:]))
        y0=(v0-adex.EL_mV)/15.0
        y1=(v1-adex.EL_mV)/15.0
        out_a,out_b=ca.observe(y0,tick),cb.observe(y1,tick)
        if arm=="DISCONNECTED":
            in_a=in_b=null_packet(tick)
        else:
            in_a,in_b=out_b,out_a
        u0=ca.act(tick,in_a,(0.0,0.0),arm)
        u1=cb.act(tick,in_b,(0.0,0.0),arm)
        # OOD additive-drive shock at t=24; NOT a claimed structural ΔA.
        shock=32.0 if tick>=24 else 0.0
        current=np.empty(N_NEURONS,dtype=np.float64)
        current[:N_NEURONS//2]=120.0+28.0*u0+shock
        current[N_NEURONS//2:]=120.0+28.0*u1-shock
        metric=net.step(external_current_pA=current)
        spikes=net.state.spiked
        a_spk=int(np.sum(spikes[:N_NEURONS//2]))
        b_spk=int(np.sum(spikes[N_NEURONS//2:]))
        spike_count_a+=a_spk
        spike_count_b+=b_spk
        total_current_proxy+=float(np.sum(current*current))*DT_MS
        records.append({
            "tick":tick,
            "uA":round(u0,9),"uB":round(u1,9),
            "mean_voltage_A_mV":round(v0,9),"mean_voltage_B_mV":round(v1,9),
            "spikesA":a_spk,"spikesB":b_spk,
            "branching_sigma":finite(metric.get("sigma")),
            "gain":finite(metric.get("gain")),
            "spike_rate_hz":finite(metric.get("spike_rate_hz")),
            "shock_active":tick>=24,
            "incoming_A_sha256":sha(in_a),"incoming_B_sha256":sha(in_b),
        })
    return {
        "seed":seed, "arm":arm, "n_neurons":N_NEURONS,"steps":STEPS,
        "dt_ms":DT_MS,"neuron_model":"BN-Syn AdEx",
        "source_commit":EXPECTED_BNSYN_SHA,
        "total_spikes_A":spike_count_a, "total_spikes_B":spike_count_b,
        "current_squared_pA2ms_proxy":round(total_current_proxy,8),
        "traces":records,"trace_sha256":sha(canon(records)),
        "biological_validation_claimed":False,
        "causal_emergence_claimed":False,
    }


def bundle(source:Path)->dict[str,bytes]:
    lock=assert_bn_source(source)
    arms={}
    for arm in ("COUPLED","CENTRAL_EMULATOR","DISCONNECTED"):
        arms[arm]=run_cortex_bnsyn(31001,arm,source)
    exact = arms["COUPLED"]["trace_sha256"] == arms["CENTRAL_EMULATOR"]["trace_sha256"]
    differential = arms["COUPLED"]["trace_sha256"] != arms["DISCONNECTED"]["trace_sha256"]
    if not exact:
        raise ValueError("monolith-emulator trace parity violated on physical simulator")
    data={
        "source":lock,
        "world":{"seed":31001,"N":N_NEURONS,"steps":STEPS,"dt_ms":DT_MS,
                 "shock_kind":"unannounced additive current disturbance, NOT structural DeltaA",
                 "shock_tick":24},
        "result":{
            "central_exact":exact,
            "disconnection_changes_trajectory":differential,
            "real_bnsyn_network_executed":True,
            "neural_emergence_established":False,
            "independent_replication":False,
            "scientific_tier":"SOURCE_PINNED_SIMULATOR_INTEGRATION_SMOKE_ONLY",
        },
    }
    return {
        "bnsyn_source_lock.json":canon(lock),
        "bridge_protocol.json":canon(data),
        "neural_trace.json":canon(arms),
        "verdict.json":canon({
            "verdict":"INTEGRATION_INTERFACE_QUALIFIED"
                      if differential else "INTEGRATION_NEEDS_SENSITIVITY",
            "scientific_authority":"ENGINEERING_ONLY",
            "CNEH_formal_hypothesis":"FORMALIZED / EMPIRICAL VALIDATION PENDING",
            "physical_safety_evidence":False,"independent_replication":False,
            "CNEH_emergence_supported":False,
        }),
    }


def write(out:Path,payload:dict[str,bytes])->None:
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("refuse overwriting immutable proof")
    out.mkdir(parents=True,exist_ok=True)
    for k,v in payload.items():
        (out/k).write_bytes(v)
    (out/"SHA256SUMS").write_text(
        "".join(f"{sha(payload[k])}  {k}\n" for k in sorted(payload)),
        encoding="ascii",
    )


def verify(out:Path,source:Path)->None:
    if out.is_symlink() or not out.is_dir():
        raise ValueError("missing proof directory")
    items=list(out.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in items):
        raise ValueError("nonfile bundle payload")
    expected=bundle(source)
    actual={p.name for p in items}
    if actual!=set(expected)|{"SHA256SUMS"}:
        raise ValueError("artifact membership mismatch")
    checksum="".join(f"{sha(expected[k])}  {k}\n" for k in sorted(expected))
    if (out/"SHA256SUMS").read_text(encoding="ascii")!=checksum:
        raise ValueError("SHA256 manifest does not match rerun")
    for k,content in expected.items():
        if (out/k).read_bytes()!=content:
            raise ValueError(f"resigned evidence mismatch: {k}")


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--bnsyn-root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if args.verify:
        verify(args.out,args.bnsyn_root)
        print("CNEH↔BN-Syn source-pinned simulator interface: replay PASS")
    else:
        write(args.out,bundle(args.bnsyn_root))
        verify(args.out,args.bnsyn_root)
        print("CNEH↔BN-Syn source-pinned simulator interface: sealed ENGINEERING-ONLY")


if __name__=="__main__":
    main()
