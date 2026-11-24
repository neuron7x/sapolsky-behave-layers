"""Evaluator-only eight-plan native counterfactuals on sealed EXP05 anchors."""
from __future__ import annotations

import copy
import hashlib
import itertools
import math
import importlib

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04f import policy as f
from experiments.cneh_exp_04g import run as g
from experiments.cneh_exp_05 import policy as p
from experiments.cneh_exp_05a import bounds as b

pinned,parent,neural=d.pinned,d.parent,d.neural
require=p.require
UNIQUE=("DUAL","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
TOL=1e-9


def shadow_history(cells: tuple,plan: tuple) -> list[tuple[int,...]]:
    """Independent scalar transcription of the frozen open-loop shadow equations."""
    rows=[]
    for t in range(p.BLOCK):
        rows.append(tuple(s for _,_,s in cells))
        group=p.action(plan,t)
        next_cells=[]
        for j,(v,w,_) in enumerate(cells):
            current=500. if group==j//4 else 0.
            vv=v+.1*((-10.*(v+70.)+20.*math.exp(min((v+55.)/2.,20.))-w+current)/150.)
            ww=w+.1*(2.*(v+70.)-w)/200.
            spike=int(vv>=30.)
            next_cells.append((-58.,ww+80.,1) if spike else
                              (max(-100.,min(math.nextafter(30.,-math.inf),vv)),ww,0))
        cells=tuple(next_cells)
    return rows


def arrival_histories(bits: list[tuple[int,...]]) -> list[list[int]]:
    result=[[] for _ in d.ALL]
    for row in bits:
        require(len(row)==8 and all(type(x) is int and x in (0,1) for x in row),"invalid true source bits")
        counts=(sum(row[:4]),sum(row[4:]))
        for mode,(a,z) in enumerate(q.MODES):
            result[mode].append(a*counts[0]+z*counts[1])
    return result


def information(histories: list[list[int]],observed: list[tuple[int | None,...]] | None=None) -> dict:
    pairs=list(itertools.combinations(d.ALL,2))
    ks=[sum(x!=y for x,y in zip(histories[i],histories[j],strict=True)) for i,j in pairs]
    proxy=math.fsum(1.-(1.-.75**8)**k for k in ks)/len(ks)
    out={"proxy":proxy,"pair_distinguishing_ticks":ks,
         "full_directed_elimination":2*sum(k>0 for k in ks)/12}
    if observed is not None:
        require(len(observed)==len(histories[0]),"incomplete sensor mask history")
        survivors=[set(d.ALL) for _ in d.ALL]
        for t,bits in enumerate(observed):
            ranges=[q.possible_counts(mode,bits) for mode in d.ALL]
            for truth in d.ALL:
                n=histories[truth][t]
                require(n in ranges[truth],"sensor mask false exclusion")
                survivors[truth].intersection_update(i for i in d.ALL if n in ranges[i])
        require(all(mode in survivors[mode] for mode in d.ALL),"true hypothetical model lost")
        directed=sum(4-len(x) for x in survivors)
        require(directed<=2*sum(k>0 for k in ks),"erasure increased distinguishability")
        out.update(observed_directed_elimination=directed/12,
                   observed_singleton_modes=sum(len(x)==1 for x in survivors),
                   observed_survivors=[sorted(x) for x in survivors])
    return out


def costs(histories: list[list[int]],candidates: tuple[int,...],lo: float,hi: float) -> dict:
    reports=[{"mode":mode,**b.interval_sup(histories[mode],lo,hi)} for mode in candidates if mode!=3]
    return {"endpoint":max((x["endpoint_loss"] for x in reports),default=0.),
            "interval":max((x["supremum_loss"] for x in reports),default=0.),
            "mode_reports":reports}


def objective(arm: str,c: float,i: float) -> float:
    if arm=="CONTROL_ONLY":
        return c
    if arm=="INFO_ONLY":
        return 1-i
    return c+.25*(1-i)


def rank_stats(a: list[float],z: list[float]) -> dict:
    require(len(a)==len(z)==len(p.PLANS),"ranking roster")
    def sign(x):
        return 1 if x>TOL else -1 if x< -TOL else 0
    strict=inversions=ties=0
    for i,j in itertools.combinations(range(len(a)),2):
        x,y=sign(a[i]-a[j]),sign(z[i]-z[j])
        strict+=bool(x and y)
        inversions+=x*y==-1
        ties+=(x==0)!=(y==0)
    return {"strict_pairs":strict,"inversions":inversions,"tie_disagreements":ties}


def state_values(net) -> tuple[tuple[float,...],tuple[int,...]]:
    return tuple(float(net.g_gabaa[j]) for j in d.B),tuple(int(net.state.spiked[j]) for j in g.SOURCES)


def state_sha(net,np) -> str:
    return parent.physical_state_digest(net,np)


def rng_sha(net) -> str:
    return pinned.sha(pinned.canonical(net.rng.bit_generator.state))


def verify_selected(net,np,row: dict,filter_state) -> None:
    gaba,bits=state_values(net)
    require(state_sha(net,np)==row["state_sha256"] and rng_sha(net)==row["rng_sha256"],
            "selected native state/RNG replay mismatch")
    require(g.hx(gaba)==row["true_gaba"] and list(bits)==row["true_bits"] and
            g.hx(net.state.V_mV[list(g.SOURCES)])==row["source_V"] and
            g.hx(net.state.w_pA[list(g.SOURCES)])==row["source_w"],"selected latent observation replay mismatch")
    require(filter_state.snapshot()==row["policy"]["filter"] and
            filter_state.last_action_tick==row["policy"]["last_action_tick"] and
            filter_state.last_action_group==row["policy"]["last_action_group"],"selected public filter replay mismatch")
    require(d.obs_record(filter_state.previous)=={k:row[k] for k in ("tick","observed_gaba","observed_bits")},
            "selected public sensor replay mismatch")


def rollout(anchor,public_filter,plan: tuple,start: int,rows: list[dict],schedule: dict,
            rt: dict,tape: list,certificate: dict,selected: bool) -> tuple[dict,object,object]:
    np,network=rt["np"],rt["network"]
    net=copy.deepcopy(anchor)
    filt=copy.deepcopy(public_filter)
    require(state_sha(net,np)==state_sha(anchor,np) and rng_sha(net)==rng_sha(anchor),"clone state mismatch")
    require(not np.shares_memory(net.state.V_mV,anchor.state.V_mV) and
            not np.shares_memory(net.state.w_pA,anchor.state.w_pA) and
            not np.shares_memory(net.g_gabaa,anchor.g_gabaa) and net.rng is not anchor.rng,"clone aliasing")
    connectivity=importlib.import_module("bnsyn.connectivity").SparseConnectivity
    mode=0 if start==0 else rows[start]["transition_mode"]
    matrix=parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())
    vals,reachable,truth_bits,obs_bits=[],[],[],[]
    stale=ambiguous=correct=exclusions=used=0
    counts=[0,0]
    digest=hashlib.sha256()
    if selected:
        verify_selected(net,np,rows[start],filt)
    for offset in range(p.BLOCK):
        t=start+offset
        require(rng_sha(net)==rows[t]["rng_sha256"],"counterfactual exogenous RNG mismatch")
        if t in schedule:
            before=state_sha(net,np)
            mode=schedule[t]
            matrix=neural.apply_mode(net,mode,np,connectivity)
            require(state_sha(net,np)==before,"topology altered physical state")
        require(mode==rows[t]["next_mode"],"hidden schedule reconstruction mismatch")
        require(not np.any(net.W_exc.to_dense()[list(g.SOURCES)]) and
                not np.any(net.W_inh.to_dense()[list(g.SOURCES)]),"source topology not independent")
        gaba,bits=state_values(net)
        noise,mask=tape[t]
        public=d.public_observation(t,gaba,bits,noise,mask)
        require(public==filt.previous,"filter observation alignment")
        require(g.hx(noise)==rows[t]["noise"] and list(mask)==rows[t]["erasures"],"historical sensor tape mismatch")
        truth_bits.append(bits)
        obs_bits.append(public.bits)
        group=p.action(plan,offset)
        used+=group is not None
        if group is not None:
            counts[group]+=1
        u=np.zeros(32,dtype=np.float64)
        u[list(d.B)]=300.
        if group is not None:
            u[list(d.GROUPS[group])]=500.
        if selected:
            require(group==rows[t]["group"] and rows[t]["source_inputs_pA"]==[500. if group==j else 0. for j in range(2)]
                    and rows[t]["topology_sha256"]==matrix and rows[t]["applied_gain"]==1.,"selected action/topology mismatch")
        filt.last_action_tick,filt.last_action_group=t,group
        net.gain=1.
        metrics=net.step(external_current_pA=u)
        require(all(math.isfinite(float(v)) for v in metrics.values()) and np.isfinite(net.state.V_mV).all()
                and np.isfinite(net.state.w_pA).all() and not np.any(net.state.V_mV<net.np.V_min_mV)
                and not np.any(net.state.V_mV>net.np.V_max_mV),"native voltage/finite envelope")
        neural.gain.check_current(net._I_ext_buffer,u,1.,network.GAIN_CURRENT_SCALE_PA,np)
        require(parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())==matrix,"unexpected topology")
        after,spikes=state_values(net)
        arrival=sum(q.MODES[mode][j]*sum(bits[j*4:j*4+4]) for j in range(2))
        require(max(abs(x-q.DECAY*(y+.5*arrival)) for x,y in zip(after,gaba,strict=True))<=TOL,"native arrival recurrence")
        require(all(math.isfinite(v) and v>=0 for v in after),"invalid conductance")
        value=math.fsum(after)/len(after)
        vals.append(value)
        if mode!=3:
            reachable.append(value)
        next_noise,next_mask=tape[t+1]
        filt.observe(d.public_observation(t+1,after,spikes,next_noise,next_mask))
        require(mode in filt.instant,"instantaneous support exclusion")
        if not schedule:
            require(filt.event!=d.CONTRADICTION and 0 in filt.candidates,"no-change contradiction")
        stale+=mode not in filt.candidates
        ambiguous+=len(filt.candidates)>1
        correct+=filt.candidates==(mode,)
        exclusions+=4-len(filt.instant)
        s,r=state_sha(net,np),rng_sha(net)
        require(r==rows[t+1]["rng_sha256"],"counterfactual RNG diverged")
        digest.update(pinned.canonical({"tick":t+1,"state_sha256":s,"rng_sha256":r,
                         "group":group,"mode":mode,"gaba":g.hx(after),"spikes":list(spikes),
                         "filter":filt.snapshot()}))
        if selected:
            verify_selected(net,np,rows[t+1],filt)
    require(used==p.ON and counts[plan[0]]==p.ON,"counterfactual effort")
    b.trace_bounds(vals,certificate)
    report={"plan":list(plan),"trajectory_sha256":digest.hexdigest(),"stim_ticks":used,
            "reachable_samples":len(reachable),"physical_mae_nS":math.fsum(abs(v-.5) for v in reachable)/len(reachable) if reachable else None,
            "physical_band_fraction":sum(.4<=v<=.6 for v in reachable)/len(reachable) if reachable else None,
            "stale_fraction":stale/p.BLOCK,"ambiguous_fraction":ambiguous/p.BLOCK,
            "correct_fraction":correct/p.BLOCK,"instant_false_alternative_exclusions":exclusions,
            "source_spike_events":sum(sum(x) for x in truth_bits)}
    return {**report,"bits":truth_bits,"observed":obs_bits},net,filt


def evaluate_block(anchor,filter_state,rows: list[dict],start: int,arm: str,schedule: dict,rt: dict,tape: list,certificate: dict):
    row=rows[start]
    selected=tuple(row["decision"]["selected"])
    scores=row["decision"]["scores"]
    require([tuple(x["plan"]) for x in scores]==list(p.PLANS) and selected in p.PLANS,"archived plan roster")
    shadow=tuple((float.fromhex(v),float.fromhex(w),s) for v,w,s in row["policy"]["shadow"])
    candidates=tuple(row["policy"]["filter"]["candidates"])
    mean=math.fsum(float.fromhex(v) for v in row["observed_gaba"])/len(d.B)
    lo,hi=max(0.,mean-q.EPS),max(0.,mean+q.EPS)
    np=rt["np"]
    anchor_sha,anchor_rng=state_sha(anchor,np),rng_sha(anchor)
    results=[]
    chosen_net=chosen_filter=None
    for plan,old in zip(p.PLANS,scores,strict=True):
        sb=shadow_history(shadow,plan)
        sh=arrival_histories(sb)
        sc=costs(sh,candidates,lo,hi)
        si=information(sh)
        require(abs(sc["endpoint"]-old["control_cost"])<=TOL and
                abs(si["proxy"]-old["information_proxy"])<=TOL and
                si["pair_distinguishing_ticks"]==old["pair_distinguishing_ticks"],"independent shadow endpoint score mismatch")
        for forecast in old["forecasts"]:
            point=b.direct_loss(sh[forecast["mode"]],forecast["initial_nS"])
            require(abs(point["loss"]-forecast["loss"])<=TOL and point["occupancy"]==forecast["in_band_samples"]
                    and abs(point["mae"]-forecast["mae_nS"])<=TOL,"archived forecast mismatch")
        native,net,filt=rollout(anchor,filter_state,plan,start,rows,schedule,rt,tape,certificate,plan==selected)
        nb=native.pop("bits")
        observed=native.pop("observed")
        nh=arrival_histories(nb)
        nc=costs(nh,candidates,lo,hi)
        ni=information(nh,observed)
        count_mismatch=sum(tuple(sum(x[j*4:j*4+4]) for j in range(2))!=
                           tuple(sum(y[j*4:j*4+4]) for j in range(2)) for x,y in zip(sb,nb,strict=True))
        bit_errors=sum(a!=z for x,y in zip(sb,nb,strict=True) for a,z in zip(x,y,strict=True))
        sfirst=next((i for i,x in enumerate(sb) if any(x[plan[0]*4:plan[0]*4+4])),None)
        nfirst=next((i for i,x in enumerate(nb) if any(x[plan[0]*4:plan[0]*4+4])),None)
        results.append({**native,"shadow_cost":sc,"native_cost":nc,"shadow_info":si,"native_info":ni,
                        "source_count_mismatch_ticks":count_mismatch,"source_bit_errors":bit_errors,
                        "shadow_first_source_spike_sample":sfirst,"native_first_source_spike_sample":nfirst})
        if plan==selected:
            chosen_net,chosen_filter=net,filt
        require(state_sha(anchor,np)==anchor_sha and rng_sha(anchor)==anchor_rng,"counterfactual mutated anchor")
    require(chosen_net is not None and chosen_filter is not None,"selected branch absent")
    index=p.PLANS.index(selected)
    old_scores=[objective(arm,x["shadow_cost"]["endpoint"],x["shadow_info"]["proxy"]) for x in results]
    interval_scores=[objective(arm,x["shadow_cost"]["interval"],x["shadow_info"]["proxy"]) for x in results]
    native_scores=[objective(arm,x["native_cost"]["endpoint"],x["native_info"]["proxy"]) for x in results]
    native_interval=[objective(arm,x["native_cost"]["interval"],x["native_info"]["proxy"]) for x in results]
    observed_scores=[objective(arm,x["native_cost"]["interval"],x["native_info"]["observed_directed_elimination"]) for x in results]
    def regret(vals):
        return max(0.,vals[index]-min(vals))
    def best(vals):
        return list(p.PLANS[min(range(len(vals)),key=lambda i:(vals[i],p.PLANS[i][0]!=(start//p.BLOCK)%2,
                    p.WAVES.index(p.PLANS[i][1]),p.PLANS[i][0]))])
    chosen=results[index]
    if chosen["reachable_samples"]:
        require(all(x["reachable_samples"]==chosen["reachable_samples"] for x in results),"reachable sample mismatch")
        physical_mae=max(0.,chosen["physical_mae_nS"]-min(x["physical_mae_nS"] for x in results))
        physical_band=max(0.,max(x["physical_band_fraction"] for x in results)-chosen["physical_band_fraction"])
    else:
        physical_mae=physical_band=None
    mode_cases=[z for x in results for z in x["shadow_cost"]["mode_reports"]]
    max_gap=max((z["excess"] for z in mode_cases),default=0.)
    return {"start":start,"selected":list(selected),"candidates":list(candidates),"true_mode_at_action":row["next_mode"],
            "initial_interval_nS":[lo,hi],"stale_at_action":row["next_mode"] not in candidates,
            "rank_shadow_vs_native":rank_stats(old_scores,native_scores),
            "rank_info_proxy_vs_observed":rank_stats([x["shadow_info"]["proxy"] for x in results],
                                                   [x["native_info"]["observed_directed_elimination"] for x in results]),
            "selected_shadow_interval_regret":regret(interval_scores),"selected_native_endpoint_regret":regret(native_scores),
            "selected_native_interval_regret":regret(native_interval),"selected_observed_pair_regret":regret(observed_scores),
            "selected_physical_mae_regret_nS":physical_mae,"selected_physical_band_regret":physical_band,
            "shadow_endpoint_best":best(old_scores),"shadow_interval_best":best(interval_scores),
            "native_endpoint_best":best(native_scores),"native_interval_best":best(native_interval),"observed_pair_best":best(observed_scores),
            "mode_cases":len(mode_cases),"interior_excess_cases":sum(z["excess"]>TOL for z in mode_cases),
            "max_interior_excess":max_gap,"selected_interval_excess":chosen["shadow_cost"]["interval"]-chosen["shadow_cost"]["endpoint"],
            "plans":results},chosen_net,chosen_filter
