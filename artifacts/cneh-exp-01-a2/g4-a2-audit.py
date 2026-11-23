"""Read-only G4 epistemic audit; writes only this evidence directory and temp fixtures."""
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path.cwd()
sys.path.insert(0,str(ROOT))
E=ROOT.parent/'evidence'
LOGS=E/'g4-a2-logs'
SOURCE='f030a12b145bd8b43876c9e2d8b268e820e92b87'
BASE='4ccb02e7da16c4a65573e8e7c7e98a0b8456119b'
A1='a65ab49681bc748acb71cde9abe5bc99a4045ab3'
P=ROOT/'experiments/cneh_exp_01'
B=ROOT/'artifacts/cneh-exp-01-a1/primary'
checks=[]

def digest(data): return hashlib.sha256(data).hexdigest()
def canonical(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def check(name,condition,evidence,falsifier):
    checks.append({'id':name,'status':'PASS' if condition else 'FAIL','evidence':evidence,'falsifier':falsifier})
def command(name,args,expected):
    completed=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=60)
    (LOGS/(name+'.stdout.log')).write_text(completed.stdout)
    (LOGS/(name+'.stderr.log')).write_text(completed.stderr)
    record={'argv':args,'exit_code':completed.returncode,'expected_exit_code':expected,
            'stdout_sha256':digest(completed.stdout.encode()),'stderr_sha256':digest(completed.stderr.encode())}
    check(name,completed.returncode==expected,record,'A different process exit code fails this gate.')
    return completed,record

def tree(revision,prefix):
    records=git('ls-tree','-r','-z',revision,'--',prefix).split(b'\0')
    return {record.split(b'\t',1)[1].decode():record.split(b'\t',1)[0].split()[2].decode()
            for record in records if record}

head=git('rev-parse','HEAD').decode().strip()
check('exact_source_commit',head==SOURCE,{'observed':head,'required':SOURCE},'HEAD differs from the reviewed source commit.')
check('clean_source_worktree',not git('status','--porcelain').strip(),{'git_status_porcelain':git('status','--porcelain').decode()},'Any uncommitted tracked or untracked repository change requires a new audit snapshot.')
source_paths=sorted([p for p in P.iterdir() if p.suffix in ('.py','.json','.md','.lock','.in')])
source_hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in source_paths}
source_matches={str(path.relative_to(ROOT)):path.read_bytes()==git('show',f'{SOURCE}:{path.relative_to(ROOT)}') for path in source_paths}
check('source_bytes_match_commit',all(source_matches.values()),{'sha256':source_hashes,'matches':source_matches},'Any audited source byte differs from the named commit.')

frozen={}
for name in ('protocol.json','PREREGISTRATION.md','CNEH-04-DC_Formal_Specification.md','frozen_sources.lock'):
    relative='experiments/cneh_exp_01/'+name
    before=git('show',f'{BASE}:{relative}');current=(ROOT/relative).read_bytes()
    frozen[relative]={'baseline_sha256':digest(before),'current_sha256':digest(current),'byte_identical':before==current}
check('four_original_files_unchanged',all(x['byte_identical'] for x in frozen.values()),frozen,'Any original protocol, preregistration, specification or source-lock byte changes.')

history={}
for label,revision,prefix in (
    ('all_preexisting_CWC_artifacts',BASE,'artifacts'),
    ('explicit_CWC_history',BASE,'artifacts/history'),
    ('A1_entire_evidence',A1,'artifacts/cneh-exp-01-a1'),
    ('A1_negative_evidence',A1,'artifacts/cneh-exp-01-a1/negative-evidence')):
    old,new=tree(revision,prefix),tree(SOURCE,prefix)
    changed=[path for path,blob in old.items() if new.get(path)!=blob]
    history[label]={'baseline_commit':revision,'scope':prefix,'baseline_blob_count':len(old),'changed_or_removed':changed,
                    'baseline_path_blob_manifest_sha256':digest(canonical(old)),'preservation_basis':'Git blob identity; historical results not rerun'}
    check(label+'_preserved',bool(old) and not changed,history[label],'A baseline evidence blob is removed or replaced.')
normative={}
for relative in ('claim_registry.json','SYSTEM.md','docs/methodology/CWC_MASTER_METHODOLOGY.md'):
    before=git('show',f'{BASE}:{relative}');now=(ROOT/relative).read_bytes()
    normative[relative]={'baseline_sha256':digest(before),'current_sha256':digest(now),'byte_identical':before==now}
check('CWC_normative_claim_boundaries_unchanged',all(row['byte_identical'] for row in normative.values()),normative,'An existing normative claim registry, system boundary or methodology changes.')
ledger='docs/lab/EXPERIMENT_LEDGER.jsonl'
old_rows=git('show',f'{BASE}:{ledger}').splitlines();new_rows=(ROOT/ledger).read_bytes().splitlines()
missing=Counter(old_rows)-Counter(new_rows)
check('historical_ledger_rows_preserved',not missing,{'baseline_rows':len(old_rows),'current_rows':len(new_rows),'removed_or_changed_old_rows':sum(missing.values()),'current_sha256':digest((ROOT/ledger).read_bytes())},'Any original ledger row is removed or changed; a new engineering row may be added.')

negative_hashes={str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in sorted((ROOT/'artifacts/cneh-exp-01-a1/negative-evidence').glob('*')) if path.is_file()}
check('A1_negative_files_present',len(negative_hashes)>=5,negative_hashes,'The archived baseline counterexamples or negative-control logs disappear.')

manifest_checks={}
for relative in ('artifacts/cneh-exp-01-a1/primary','artifacts/cneh-exp-01-a1/bnsyn'):
    directory=ROOT/relative
    entries=[]
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);path=directory/name
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()): raise ValueError('unsafe manifest path')
        entries.append({'path':name,'matches':digest(path.read_bytes())==expected})
    manifest_checks[relative]={'manifest_sha256':digest((directory/'SHA256SUMS').read_bytes()),'entries':entries}
    check(relative+'_manifest',all(row['matches'] for row in entries),manifest_checks[relative],'Any archived raw primary or neural evidence byte fails its manifest.')

completed,_=command('science_readiness', [sys.executable,str(P/'qualification.py'),'--bundle',str(B),'--require-scientific-readiness'],2)
readiness=json.loads(completed.stdout)
check('scientific_authority_locked',readiness['scientific_promotion_authorized'] is False and readiness['scientific_readiness']=='BLOCKED'
      and readiness['gates']['replication']=='REPLICATION_NOT_TESTED' and readiness['same_lineage_supported_narrow_reachable'] is False,
      readiness,'Any science promotion flag, supported reachability flag, or external replication assertion becomes positive.')

protocol=json.loads((P/'protocol.json').read_bytes())
rows=list(csv.DictReader((B/'primary.csv').open()))
by={(int(row['seed']),row['arm']):row for row in rows}
seeds=list(range(protocol['cohorts']['primary']['seed_first'],protocol['cohorts']['primary']['seed_last']+1))
parity=all(by[s,'COUPLED']['trace_sha256']==by[s,'CENTRAL_EMULATOR']['trace_sha256'] and by[s,'COUPLED']['success']==by[s,'CENTRAL_EMULATOR']['success'] for s in seeds)
lcb=-math.sqrt(2*math.log(protocol['number_family_tests']/protocol['alpha_fwer'])/len(seeds))
verdict=json.loads((B/'verdict.json').read_bytes())
structural={'paired_worlds':len(seeds),'all_exact_trace_and_outcome_pairs_equal':parity,'D_s':0,'central_lcb':lcb,
            'material_effect':protocol['material_effect'],'central_in_primary_conjunction':'CENTRAL_EMULATOR' in protocol['primary_contrasts'],
            'reported_central_lcb':verdict['primary_comparisons']['CENTRAL_EMULATOR']['one_sided_lcb'],
            'scope':'Current implementation exact expressivity parity; no physical cost-preserving simulation inferred.'}
check('structural_positive_conjunction_impossible',parity and structural['central_in_primary_conjunction'] and lcb<0<protocol['material_effect']
      and lcb==structural['reported_central_lcb'],structural,'A nonzero coupled-minus-faithful-emulator outcome or a removed central contrast invalidates this argument; it cannot license promotion.')

with tempfile.TemporaryDirectory(prefix='cneh-g4-forged-promotion-') as temporary:
    forged=Path(temporary)/'bundle';shutil.copytree(B,forged)
    data=json.loads((forged/'verdict.json').read_bytes());data['scientific_promotion_authorized']=True
    (forged/'verdict.json').write_bytes(canonical(data))
    (forged/'SHA256SUMS').write_text(''.join(f'{digest(path.read_bytes())}  {path.name}\n' for path in sorted(forged.iterdir()) if path.name!='SHA256SUMS'))
    rejected,_=command('resigned_positive_promotion_rejected',[sys.executable,str(P/'qualification.py'),'--bundle',str(forged),'--require-scientific-readiness'],1)
    rejected_result=json.loads(rejected.stdout)
    check('semantic_promotion_falsifier',rejected_result['engineering_validation']=='FAIL' and rejected_result['scientific_promotion_authorized'] is False,
          rejected_result,'A freshly rehashed sidecar scientific_promotion_authorized=true must never be admitted.')

cost_bundle=E/'metrology-a2-current'
cost=json.loads((cost_bundle/'report.json').read_bytes())
command('physical_cost_readiness',[sys.executable,str(P/'metrology.py'),'--out',str(cost_bundle),'--verify','--require-qualified-cost'],2)
check('physical_cost_unqualified',cost['resource_parity_verified'] is False and all(value=='INSTRUMENT_INVALID' for value in cost['instruments'].values()),
      {'source_sha256':cost['source_sha256'],'admission':cost['admission'],'resource_parity_verified':cost['resource_parity_verified'],'instruments':cost['instruments']},
      'Measured upper-ceiling compliance is relabelled resource parity or unavailable joule/FLOP/transport instruments become valid.')

neural=json.loads((ROOT/'artifacts/cneh-exp-01-a1/bnsyn/report.json').read_bytes())
guide=(P/'QUALIFICATION_GUIDE.md').read_text()
neural_statuses=[
 {'claim':'API integration','status':'EXECUTED_PINNED_INTEGRATION_SMOKE','evidence':{'source':neural['source'],'source_verified':neural['checks']['source_verified']}},
 {'claim':'Reproducible neural trajectories','status':'EXACT_REPLAY_WITHIN_RECORDED_ENVIRONMENT','evidence':{'all_arm_exact_replay':neural['checks']['all_arm_exact_replay'],'emulator_exact_parity':neural['checks']['emulator_exact_parity']}},
 {'claim':'Genuine spiking','status':'OBSERVED_IN_ENGINEERING_SMOKE','evidence':{'episodes':[{'seed':r['seed'],'arm':r['arm'],'total_spikes':r['total_spikes']} for r in neural['episodes']]}},
 {'claim':'Functional interpopulation coupling','status':'NOT_TESTED','evidence':'Zero-action responsiveness is not an isolated coupling intervention.'},
 {'claim':'Structural neural OOD response','status':'NOT_TESTED','evidence':'No structural neural OOD task in the frozen smoke.'},
 {'claim':'Causal improvement in neural goal task','status':'NOT_TESTED','evidence':{'neural_efficacy_qualified':neural['neural_efficacy_qualified']}},
]
check('six_neural_claim_boundaries',neural['status']=='INTEGRATION_SMOKE_ONLY' and neural['neural_efficacy_qualified'] is False
      and all(neural['checks'][key] is True for key in ('source_verified','all_arm_exact_replay','emulator_exact_parity','active_spiking'))
      and all(text in guide for text in ('| Functional interpopulation coupling | NOT_TESTED','| Structural neural OOD response | NOT_TESTED','| Causal improvement in a neural goal task | NOT_TESTED')),
      neural_statuses,'Integration/spiking/replay is promoted to functional coupling, neural OOD efficacy, or causal task improvement without a separate experiment.')

from experiments.cneh_exp_01 import replication
public,private=replication.create_commitment(list(range(990001,990129)),code_sha=SOURCE,operator_id='G4_INTERNAL_CONSISTENCY_FIXTURE')
roundtrip=replication.verify_reveal(public,private)
check('internal_commitment_cannot_prove_external_replication',roundtrip['independent_blind_replication'] is False and roundtrip['authority']=='EXTERNAL_ATTESTATION_REQUIRED'
      and roundtrip['chronology']=='NOT_AUTHENTICATED',roundtrip,'Self-issued commitment consistency grants external identity, authenticated chronology or independent replication.')

flag_names={'claim_promotion_allowed','scientific_promotion_authorized','independent_blind_replication','independent_replication',
            'causal_attribution_qualified','neural_estimators_qualified','physical_cost_qualified','resource_parity_verified','neural_efficacy_qualified',
            'physical_safety_qualified','chance_constraint_verified','hardware_flops_verified','physical_joules_verified','external_training_budget_verified'}
flag_sources=sorted(P.glob('*.json'))+sorted((ROOT/'artifacts/cneh-exp-01-a1').rglob('*.json'))+[E/'math-a2-qualification-v2.json',cost_bundle/'report.json']
flag_records=[]
def walk(value,pointer,source):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in flag_names:flag_records.append({'source':source,'pointer':pointer+'/'+key,'value':item,'is_exact_false':item is False})
            walk(item,pointer+'/'+key,source)
    elif isinstance(value,list):
        for i,item in enumerate(value):walk(item,pointer+'/'+str(i),source)
for path in flag_sources:walk(json.loads(path.read_bytes()),'',str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
check('all_scoped_promotion_and_unearned_authority_flags_false',bool(flag_records) and all(row['is_exact_false'] for row in flag_records),
      {'scope':'Current CNEH JSON contracts, published A1 JSON evidence, current A2 math/metrology reports; mutation patch strings are not authority assertions.',
       'files_examined':len(flag_sources),'authority_flag_occurrences':len(flag_records),'records':flag_records},
      'Any selected JSON authority flag differs from exact false. Engineering parity/replay/safety rates are distinct measurements, not promotion flags.')

math_report=json.loads((E/'math-a2-qualification-v2.json').read_bytes())
check('analytic_math_scope_unpromoted',math_report['authority']=='ANALYTIC_FIXTURES_ONLY' and math_report['causal_attribution_qualified'] is False
      and math_report['neural_estimators_qualified'] is False and math_report['reference_direct_use_qualified'] is False,
      {'status':math_report['status'],'authority':math_report['authority'],'source_sha256':math_report['source_sha256'],'known_raw_reference_failures':math_report['known_raw_reference_failures']},
      'Analytic fixture PASS is asserted to qualify direct unstable references, neural estimators, or empirical causal attribution.')
check('final_source_unchanged',git('rev-parse','HEAD').decode().strip()==SOURCE and not git('status','--porcelain').strip(),
      {'head':git('rev-parse','HEAD').decode().strip(),'git_status_porcelain':git('status','--porcelain').decode()},'Source revision or working tree changes during audit.')

report={'schema':'cneh-g4-epistemic-audit-v1','status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL',
        'source_commit':SOURCE,'original_pr43_commit':BASE,'a1_evidence_commit':A1,'authority':'READ_ONLY_EPISTEMIC_CONSISTENCY_AUDIT',
        'scientific_promotion_authorized':False,'independent_external_replication':False,
        'checks':checks,'neural_six_claim_statuses':neural_statuses,
        'not_tested':['independent external blinded execution','physical calibrated joules and hardware FLOPs','distributed transport parity',
                      'functional neural interpopulation coupling','structural neural OOD adaptation','causal improvement in a neural goal task',
                      'finite-sample neural estimator accuracy or coverage','real-world safety','hosted exact-head CI completeness in this audit'],
        'scope_limits':['Historical evidence preservation is a Git object/byte-integrity check; historical experiments were not rerun.',
                        'Current archived neural raw evidence and declared replay checks were inspected and manifest-verified; no neural rerun in G4.',
                        'Unsigned physical measurements remain internally consistent records, not externally authenticated metrology.',
                        'No SpaceX/xAI/national-academic certification; PASS applies only to the listed observed checks.'],
        'audit_script_sha256':digest(Path(__file__).read_bytes()),
        'execution_log_sha256':{path.name:digest(path.read_bytes()) for path in sorted(LOGS.iterdir()) if not path.name.startswith('audit.')}}
(E/'g4-a2-epistemic.json').write_bytes(canonical(report))
print(json.dumps({'status':report['status'],'checks':len(checks),'failed':[x['id'] for x in checks if x['status']!='PASS'],
                  'historical_counts':{k:v['baseline_blob_count'] for k,v in history.items()},'flags':len(flag_records),
                  'receipt_sha256':digest((E/'g4-a2-epistemic.json').read_bytes())},sort_keys=True))
raise SystemExit(0 if report['status']=='PASS' else 1)
