"""Frozen physical-time hybrid convergence diagnostic; not exact native replay."""
from __future__ import annotations

import argparse
from bisect import bisect_right
import gzip
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from experiments.cneh_exp_05v import audit as evidence
from experiments.cneh_exp_05v import oracle as oracle

EXPERIMENT = "CNEH-EXP-05H"
PANEL_SHA = "7596d4cf672474871ff3e8b08cc06363682b246a56213ee46489580be97b4208"
V_SHA = "f22afda8a548489d943f1f246575a64acbcb61c306b57cf71e6eb94e1f722725"
ROSTER = tuple(itertools.product((93001, 93002), ("WAIT", "G0", "G1", "ALTERNATE")))
KEYS = ("V", "w", "g_ampa", "g_nmda", "g_gabaa")
TIMES = np.arange(513, dtype=np.float64) / 10.
MODES = ((1, 0), (0, 1), (1, 1), (0, 0))
SWITCHES = (12.8, 25.6, 38.4)
WIDTHS = (1, 5, 10, 20, 40, 80, 160, 320)
END = 51.2
TAU = np.array((2.5, 100., 6.), dtype=np.float64)


def need(c, message):
    if not c:
        raise ValueError(message)


def canonical(x):
    return oracle.canonical(x)


def group(arm, t):
    return None if arm == "WAIT" else 0 if arm == "G0" else 1 if arm == "G1" else (t // 64) % 2


def group_time(arm, time):
    if arm != "ALTERNATE":
        return group(arm, 0)
    return bisect_right(tuple(k / 10. for k in range(64, 512, 64)), time) % 2


def currents(arm, t):
    result = np.zeros(32)
    result[:16] = 300.
    g = group(arm, t)
    if g is not None:
        result[24 + 4 * g:28 + 4 * g] = 500.
    return result


def load(root, index):
    raw, _ = evidence.panel_raw(evidence.load_zip(root, ("A", "DEFAULT")), ("A", "DEFAULT"), 1)
    need(evidence.sha(raw) == PANEL_SHA, "unique panel identity")
    panel = evidence.strict_json(raw)
    need(tuple((r["episode"]["seed"], r["episode"]["arm"]) for r in panel["records"]) == ROSTER,
         "sealed episode roster")
    vpath = root / "14897018650.zip"
    v = evidence.strict_json(evidence.read_zip(vpath.read_bytes(), V_SHA, {"report.json", "SHA256SUMS"})["report.json"])
    need(v["experiment"] == "CNEH-EXP-05V" and v["panel_sha256"] == PANEL_SHA
         and v["unique_transitions"] == 4096 and len(v["attacks"]["rejected"]) == 21
         and v["scientific_promotion_authorized"] is False, "independent audit anchor")
    rec = panel["records"][index]
    states = rec["full_states"]
    need(len(states) == 513, "state roster")
    for t, s in enumerate(states):
        oracle.validate_state(s, t)
    arr = np.array([[[oracle.f(x) for x in s["arrays"][k]] for k in KEYS] for s in states])
    bits = np.array([s["spikes"] for s in states], dtype=bool)
    need(not bits[0].any(), "nonempty initial spike tape")
    tape = []
    for t in range(512):
        vals, rng = oracle.random32(states[t]["rng"])
        need(rng == states[t+1]["rng"], "exogenous RNG mismatch")
        tape.append([x < 2.*(.1/1000.) for x in vals])
    return rec["episode"], arr, bits, np.array(tape, dtype=bool)


def grid(initial, tape, arm, j):
    r = 2**j
    h = .1/r
    V, w, ga, gn, gg = initial.copy()
    sp = np.zeros(32, dtype=bool)
    obs = [initial.copy()]
    macro_spikes = [sp.copy()]
    events = [[] for _ in range(32)]
    dec = [math.exp(-h/tau) for tau in TAU]
    for q in range(512*r):
        t = q//r
        mode = MODES[sum(t >= k for k in (128, 256, 384))]
        ext = tape[t]*.3 if q % r == 0 else 0.
        ga = (ga + .7*ext)*dec[0]
        gn = (gn + .3*ext)*dec[1]
        gg[:16] += .5*(mode[0]*np.count_nonzero(sp[24:28]) + mode[1]*np.count_nonzero(sp[28:32]))
        gg *= dec[2]
        syn = ga*V + gn*(1./(1.+(1./3.57)*np.exp(-.062*V)))*V + gg*(V+70.)
        dv = (-10.*(V+70.)+20.*np.exp(np.minimum((V+55.)/2.,20.))-w-syn+currents(arm,t))/150.
        dw = (2.*(V+70.)-w)/200.
        V, w = V+h*dv, w+h*dw
        sp = V >= 30.
        V[sp] = -58.
        w[sp] += 80.
        need(np.isfinite(V).all() and np.isfinite(w).all() and np.min(V) >= -100., "grid state envelope")
        for i in np.flatnonzero(sp):
            events[i].append((q+1)/(10*r))
        if (q+1) % r == 0:
            obs.append(np.stack((V,w,ga,gn,gg)))
            macro_spikes.append(sp.copy())
    return np.array(obs), events, np.array(macro_spikes)


def threshold(time, y):
    return y[0]-30.


threshold.terminal = True
threshold.direction = 1


def arrivals_for(events):
    out = {}
    for i in range(24,32):
        for time in events[i]:
            mode = MODES[bisect_right(SWITCHES, time)]
            if time < END and mode[(i-24)//4]:
                out[time] = out.get(time,0.)+.5
    return out


def reference_cell(initial, external, incoming, arm, i, strict):
    # Integrate between all forcing discontinuities; no native or grid step.
    change = set(SWITCHES)
    if arm == "ALTERNATE":
        change.update(k/10. for k in range(64,512,64))
    change.update(external)
    change.update(incoming)
    boundaries = sorted({0.,END} | change)
    samples = np.empty((513,5))
    y = np.array(initial[:2],dtype=float)
    g = np.array(initial[2:],dtype=float)
    samples[0] = initial
    slot = 1
    events = []
    rtol, atol, maxstep = (1e-11,1e-13,.0125) if strict else (1e-9,1e-11,.025)
    for start, end in zip(boundaries,boundaries[1:],strict=False):
        if start in external:
            g += np.array((.7*.3,.3*.3,0.))
        g[2] += incoming.get(start,0.)
        origin = start
        ugroup = group_time(arm,(start+end)/2.)
        u = 300. if i<16 else 500. if ugroup is not None and 24+4*ugroup <= i<28+4*ugroup else 0.
        g0 = g.copy()

        def conductance(time):
            dt = time-origin
            return (g0[0]*math.exp(-dt/2.5),g0[1]*math.exp(-dt/100.),g0[2]*math.exp(-dt/6.))

        def rhs(time, state):
            V,w=state
            ga,gn,gg=conductance(time)
            z=-.062*V
            # DOP853 may evaluate rejected trial stages far outside the
            # physical voltage envelope. Evaluate the identical sigmoid
            # without overflow there; do not clip V or change the ODE.
            if z>700.:
                e=math.exp(-z)
                block=e/(e+1./3.57)
            else:
                block=1./(1.+(1./3.57)*math.exp(z))
            syn=ga*V+gn*block*V+gg*(V+70.)
            return ((-10.*(V+70.)+20.*math.exp(min((V+55.)/2.,20.))-w-syn+u)/150.,
                    (2.*(V+70.)-w)/200.)

        time=start
        while time<end:
            sol=solve_ivp(rhs,(time,end),y,method="DOP853",rtol=rtol,atol=atol,
                          max_step=maxstep,events=threshold,dense_output=True)
            need(sol.success and sol.t[-1]>time,"hybrid ODE solver failed to advance")
            stop=float(sol.t[-1])
            hit=bool(len(sol.t_events[0]))
            y=sol.y[:,-1].copy()
            if hit:
                events.append(stop)
                y[0]=-58.
                y[1]+=80.
            while slot<len(TIMES) and TIMES[slot]<=stop:
                at=float(TIMES[slot])
                need(at>=time,"sample chronology")
                vw=y if hit and at==stop else sol.sol(at)
                samples[slot]=(*vw,*conductance(at))
                slot+=1
            time=stop
        g=np.array(conductance(end))
    need(slot==len(TIMES) and np.isfinite(samples).all(),"reference sample completeness")
    return samples,events


def reference(initial,tape,arm,strict):
    out=np.empty((513,5,32))
    events=[[] for _ in range(32)]
    # Causal source-first decomposition: only sources 24..31 have outgoing edges.
    for i in range(24,32):
        ext={float(TIMES[t]) for t in range(512) if tape[t,i]}
        out[:,:,i],events[i]=reference_cell(initial[:,i],ext,{},arm,i,strict)
    incoming=arrivals_for(events)
    for i in range(24):
        ext={float(TIMES[t]) for t in range(512) if tape[t,i]}
        out[:,:,i],events[i]=reference_cell(initial[:,i],ext,incoming if i<16 else {},arm,i,strict)
    return out,events


def near_events(events, eps):
    mask=np.zeros((len(TIMES),32),dtype=bool)
    for i,ev in enumerate(events):
        for time in ev:
            mask[:,i] |= np.abs(TIMES-time)<=eps
    return mask


def near_arrivals(events,eps):
    mask=np.zeros((len(TIMES),32),dtype=bool)
    for time in arrivals_for(events):
        mask[:,:16] |= (np.abs(TIMES-time)<=eps)[:,None]
    return mask


def maximum(x,mask=None):
    if mask is not None:
        x=x[~mask]
    need(x.size>0 and np.isfinite(x).all(),"empty/nonfinite comparison")
    return float(np.max(x))


def band(x):
    return (x>=.4)&(x<=.6)


def compare(a,ae,b,be,eps):
    difference=np.abs(a-b)
    count_a=[len(x) for x in ae]
    count_b=[len(x) for x in be]
    equal=count_a==count_b
    times=max((abs(x-y) for aa,bb in zip(ae,be,strict=True)
               for x,y in zip(aa,bb,strict=True)),default=0.) if equal else None
    spike_mask=near_events(ae,eps)|near_events(be,eps)
    arrival_mask=near_arrivals(ae,eps)|near_arrivals(be,eps)
    g1,g2=(np.mean(z[:,4,:16],axis=1) for z in (a,b))
    return {"per_neuron_spikes_a":count_a,"per_neuron_spikes_b":count_b,
            "spike_counts_equal":equal,"max_event_time_error_ms":times,
            "max_full_errors":{k:maximum(difference[:,i,:]) for i,k in enumerate(KEYS)},
            "max_V_outside_reset_mV":maximum(difference[:,0,:],spike_mask),
            "max_w_outside_reset_pA":maximum(difference[:,1,:],spike_mask),
            "max_GABA_outside_arrival_nS":maximum(difference[:,4,:],arrival_mask),
            "masked_reset_samples":int(spike_mask.sum()),
            "masked_arrival_samples":int(arrival_mask.sum()),
            "band_occupancy_a":float(band(g1).mean()),"band_occupancy_b":float(band(g2).mean()),
            "band_occupancy_error":float(abs(band(g1).mean()-band(g2).mean()))}


def gates(metrics,ref=False):
    return {"SPIKE_COUNT":metrics["spike_counts_equal"],
            "SPIKE_TIME":metrics["max_event_time_error_ms"] is not None and metrics["max_event_time_error_ms"] <= (.001 if ref else .1),
            "V":metrics["max_V_outside_reset_mV"] <= (.05 if ref else 1.),
            "W":metrics["max_full_errors"]["w"] <= (.05 if ref else 1.),
            "GABA":metrics["max_GABA_outside_arrival_nS"] <= (.005 if ref else .05),
            **({} if ref else {"BAND":metrics["band_occupancy_error"]<=.02})}


def multiscale(x):
    g=x[:,4,:16].mean(axis=1)[1:]  # physical samples t=.1..51.2 ms
    rows=[]
    for scope,start,stop in (("ALL",0,512),("REACHABLE",0,384),("DISCONNECTED",384,512)):
        values=g[start:stop]
        for width in WIDTHS:
            for phase in ((0,) if width==1 else (0,width//2)):
                n=(len(values)-phase)//width
                if n<=0:
                    rows.append({"scope":scope,"width_ticks":width,"phase_ticks":phase,"bins":0})
                    continue
                used=values[phase:phase+n*width]
                blocks=used.reshape(n,width)
                means=blocks.mean(axis=1)
                physical_loss=np.abs(blocks-.5).mean(axis=1)
                smooth_loss=np.abs(means-.5)
                need(np.all(smooth_loss<=physical_loss+1e-12),"Jensen violation")
                counts=band(blocks).sum(axis=1)
                need(int(counts.sum())==int(band(used).sum()),"occupancy reaggregation")
                need(abs(float(physical_loss.mean())-float(np.abs(used-.5).mean()))<=1e-12,
                     "loss reaggregation")
                rows.append({"scope":scope,"width_ticks":width,"phase_ticks":phase,"bins":n,
                             "physical_samples":len(used),"physical_mae":float(physical_loss.mean()),
                             "smoothed_mae":float(smooth_loss.mean()),
                             "physical_occupancy":float(band(used).mean()),
                             "smoothed_occupancy":float(band(means).mean()),
                             "false_in_band_bins":int((band(means)&(counts==0)).sum())})
    return rows


def run(root,index):
    episode,archive,bits,tape=load(root,index)
    arm=episode["arm"]
    grids=[grid(archive[0],tape,arm,j) for j in range(6)]
    coarse=grids[0]
    residual={k:maximum(np.abs(coarse[0][:,i,:]-archive[:,i,:])) for i,k in enumerate(KEYS)}
    need(all(v<=1e-9 for v in residual.values()) and np.array_equal(coarse[2],bits),
         "coarse-grid archived physical reproduction failed")
    loose=reference(archive[0],tape,arm,False)
    tight=reference(archive[0],tape,arm,True)
    refmetrics=compare(*loose,*tight,.02)
    refgates=gates(refmetrics,True)
    qualified=all(refgates.values())
    rows=[]
    raw=[]
    for j,(states,events,_) in enumerate(grids):
        metrics=compare(states,events,*tight,.1)
        tests=gates(metrics)
        rows.append({"j":j,"dt_ms":.1/(2**j),"metrics":metrics,"gates":tests,
                     "status":"INCONCLUSIVE_REFERENCE" if not qualified else "PASS_FINITE" if all(tests.values()) else "FAIL",
                     "multiscale":multiscale(states)})
        raw.append({"j":j,"states":states.tolist(),"events":events})
    charge=sum(float(np.abs(currents(arm,t)[24:]).sum())*.1 for t in range(512))
    report={"experiment":EXPERIMENT,"scientific_promotion_authorized":False,
            "scientific_promotion":"BLOCKED","seed":episode["seed"],"arm":arm,"index":index,
            "coarse_residual":residual,"reference_metrics":refmetrics,"reference_gates":refgates,
            "reference_status":"QUALIFIED_FINITE" if qualified else "INCONCLUSIVE",
            "source_charge_pA_ms":charge,"grids":rows,
            "reference_multiscale":multiscale(tight[0]),
            "historical_native_replay":"FAIL_PRESERVED"}
    return {"report":report,"grids":raw,"loose":{"states":loose[0].tolist(),"events":loose[1]},
            "tight":{"states":tight[0].tolist(),"events":tight[1]}}


def aggregate(root):
    reports=[]
    for i,key in enumerate(ROSTER):
        folder=root/f"cneh-exp-05h-{i}"
        need({p.name for p in folder.iterdir()}=={"report.json","raw.json.gz","SHA256SUMS"},"shard roster")
        hashes={name:evidence.sha((folder/name).read_bytes()) for name in ("report.json","raw.json.gz")}
        need((folder/"SHA256SUMS").read_text()=="".join(hashes[k]+"  "+k+"\n" for k in sorted(hashes)),"manifest")
        report=evidence.strict_json((folder/"report.json").read_bytes())
        raw=evidence.strict_json(gzip.decompress((folder/"raw.json.gz").read_bytes()))
        need(raw["report"]==report and (report["seed"],report["arm"])==key and report["index"]==i
             and [r["j"] for r in report["grids"]]==list(range(6)),"shard binding")
        reports.append(report)
    ref=sum(x["reference_status"]=="QUALIFIED_FINITE" for x in reports)
    native=sum(x["grids"][0]["status"]=="PASS_FINITE" for x in reports)
    fine=sum(x["grids"][5]["status"]=="PASS_FINITE" for x in reports)
    return {"experiment":EXPERIMENT,"scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "historical_native_replay":"FAIL_PRESERVED","reference_qualified":ref,"native_qualified":native,
            "finest_qualified":fine,"episode_count":len(reports),
            "continuous_time_numerical_gate":"PASS_FINITE_ONLY" if native==8 else "INCONCLUSIVE" if ref!=8 else "FAIL",
            "multiscale_scope":"FINITE_PHYSICAL_VERSUS_SMOOTHED_DIAGNOSTIC_ONLY",
            "unqualified":["biophysical_validity","statistical_generalization","multiscale_scientific_coherence","closed_loop_causal_efficacy"],
            "reports":reports}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run")
    r.add_argument("--archives",type=Path,required=True)
    r.add_argument("--index",type=int,choices=range(8),required=True)
    g=sub.add_parser("aggregate")
    g.add_argument("--profiles",type=Path,required=True)
    for p in (r,g):
        p.add_argument("--out",type=Path,required=True)
        p.add_argument("--verify",action="store_true")
    args=ap.parse_args()
    if args.command=="run":
        value=run(args.archives,args.index)
        files={"report.json":canonical(value["report"]),"raw.json.gz":gzip.compress(canonical(value),mtime=0)}
    else:
        value=aggregate(args.profiles)
        files={"report.json":canonical(value)}
    files["SHA256SUMS"]="".join(evidence.sha(files[k])+"  "+k+"\n" for k in sorted(files)).encode()
    if args.verify:
        need(set(p.name for p in args.out.iterdir())==set(files),"replay output roster")
        for k,v in files.items():
            need((args.out/k).read_bytes()==v,"replay mismatch: "+k)
    else:
        args.out.mkdir()
        for k,v in files.items():
            (args.out/k).write_bytes(v)
    if args.command=="aggregate":
        print(canonical({k:v for k,v in value.items() if k!="reports"}).decode(),end="")
        return 0 if value["continuous_time_numerical_gate"]=="PASS_FINITE_ONLY" else 2
    print(canonical({k:v for k,v in value["report"].items() if k not in ("grids","reference_multiscale")}).decode(),end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
