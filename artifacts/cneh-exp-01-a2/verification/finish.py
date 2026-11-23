from pathlib import Path
import csv,hashlib,json,shutil,subprocess
out=Path(__file__).resolve().parent;root=out/'checkout';live=out.parent.parent/'repo'
def load(name):return json.loads((out/name).read_text())
commands=load('commands.json')
expected={'standard-tests','numeric-tests','mutations','numeric-mutations','math-generate','math-verify','metrology-measure','metrology-verify','metrology-qualified-cost','a1-primary-replay','science-readiness','a1-bnsyn-replay'}
assert {row['name'] for row in commands}==expected and len(commands)==len(expected)
for row in commands:
    assert row['exit_code']==row['expected_exit']
    assert hashlib.sha256((out/(row['name']+'.log')).read_bytes()).hexdigest()==row['log_sha256']
standard=json.loads((out/'standard-tests.log').read_text().splitlines()[-1]);numeric=json.loads((out/'numeric-tests.log').read_text().splitlines()[-1])
for counts,number in [(standard,74),(numeric,14)]:
    assert counts['tests_run']==number and all(v==0 for k,v in counts.items() if k!='tests_run')
mutations=load('mutations/report.json');math_mutations=load('numeric-mutations/report.json')
for report,number in [(mutations,11),(math_mutations,7)]:
    assert report['status']=='PASS' and report['killed']==report['total']==number
    assert report['source_unchanged_during_run'] is True
    assert all(m['status']=='KILLED' and not m['unittest']['error_test_ids'] for m in report['mutants'])
math=load('math-qualification.json');assert math['status']=='PASS' and len(math['checks'])==45 and all(c['pass'] for c in math['checks'].values())
metrology=load('metrology/report.json');assert metrology['admission']=='PASS' and not metrology['resource_parity_verified'] and not metrology['scientific_promotion_authorized']
assert len(metrology['workers'])==20 and len(metrology['inherited_timing']['raw'])==200 and all(s=='INSTRUMENT_INVALID' for s in metrology['instruments'].values())
science=json.loads((out/'science-readiness.log').read_text());assert science['scientific_readiness']=='BLOCKED' and not science['scientific_promotion_authorized']
frozen={}
for name in ('protocol.json','PREREGISTRATION.md','frozen_sources.lock','CNEH-04-DC_Formal_Specification.md'):
    relative='experiments/cneh_exp_01/'+name
    historical=subprocess.check_output(['git','show','4ccb02e7da16c4a65573e8e7c7e98a0b8456119b:'+relative],cwd=live)
    assert historical==(root/relative).read_bytes()
    frozen[name]=hashlib.sha256(historical).hexdigest()
state=load('reconstruction.json');cache=load('runtime-cache-adjudication.json')
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
assert actual==set(state['source_files'])|set(cache['known_runtime_cache_roster'])
for name,entry in state['source_files'].items():
    path=root/name;data=path.readlink().as_posix().encode() if entry['mode']=='120000' else path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==entry['sha256'],name
for name,entry in cache['known_runtime_cache_roster'].items():
    assert entry['exact_bytes_match'] and hashlib.sha256((root/name).read_bytes()).hexdigest()==entry['independently_compiled_pyc_sha256'],name
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=live,text=True).strip();status=subprocess.check_output(['git','status','--short'],cwd=live,text=True)
assert head==state['source_commit'] and not status
provenance=load('dependency-reference-integrity.json');assert provenance['status']=='PASS' and provenance['installed_record_mismatches']==[]
with (root/'artifacts/cneh-exp-01-a1/primary/primary.csv').open() as stream:rows=list(csv.DictReader(stream))
by={(int(r['seed']),r['arm']):r for r in rows}
assert len(rows)==1280 and sum(int(r['success']) for r in rows if r['arm']=='COUPLED')==122
assert all(by[s,'COUPLED']['trace_sha256']==by[s,'CENTRAL_EMULATOR']['trace_sha256'] for s in range(51001,51129))
report={'verdict':'PASS_WITH_CAVEATS','local_source_verification':'PASS','ENGINEERING_QUALIFIED':False,'acceptance_gates':{'G1':'PENDING_FINAL_PUSH_EQUALITY','G2':'PENDING_ALL_MANDATORY_FINAL_HEAD_CI','G3':'SOURCE_RECONSTRUCTION_AND_REPLAY_PASS_FINAL_HEAD_REPLAY_PENDING','G4':'BLOCKING_SCIENCE_STATUSES_PRESERVED'},'source_commit':head,'source_archive_sha256':state['archive_sha256'],'reconstructed_source_files':state['tracked_file_count'],'tracked_source_drift':False,'source_tree_exact_roster':'2961 pinned tracked files plus exactly two independently byte-reconstructed CPython caches','runtime_cache_adjudication':'runtime-cache-adjudication.json','initial_strict_roster_failure_preserved':'execution.log','origin_git_status':status,'origin_diff_sha256':state['origin_diff_sha256'],'standard_tests':standard,'numeric_tests':numeric,'targeted_mutations':{'killed':11,'total':11,'invalid':0},'numeric_mutations':{'killed':7,'total':7,'invalid':0},'math_checks':45,'metrology':{'admission':'PASS','workers':20,'samples':sum(len(w['samples']) for w in metrology['workers']),'timing_batches':200,'instruments':metrology['instruments'],'resource_parity_verified':False},'primary_replay':{'artifact_path':'artifacts/cneh-exp-01-a1/primary','manifest_sha256':hashlib.sha256((root/'artifacts/cneh-exp-01-a1/primary/SHA256SUMS').read_bytes()).hexdigest(),'rows':1280,'successes':122,'world_seeds':128,'emulator_divergences':0},'neural_replay':{'status':'PASS','artifact_path':'artifacts/cneh-exp-01-a1/bnsyn','manifest_sha256':hashlib.sha256((root/'artifacts/cneh-exp-01-a1/bnsyn/SHA256SUMS').read_bytes()).hexdigest()},'original_frozen_sha256':frozen,'installed_dependency_packages_verified':len(provenance['packages']),'installed_dependency_record_files_verified':provenance['installed_record_files_verified'],'pinned_pr44_source_matches_github':True,'scientific_promotion_authorized':False,'independent_external_replication':'NOT_TESTED','commands':commands,'additional_negative_controls':'independent-negative-controls.json','not_run':['final push equality','all mandatory hosted checks on final delivery SHA','clean final delivery SHA replay']}
(out/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
export=out/'export';export.mkdir(exist_ok=False)
for p in out.iterdir():
    if p.name in {'checkout','source.tar','export'}:continue
    if p.is_file():shutil.copy2(p,export/p.name)
    elif p.name in {'mutations','numeric-mutations','metrology'}:shutil.copytree(p,export/p.name)
    else:raise AssertionError('Unexpected export member '+p.name)
files=sorted(p for p in export.rglob('*') if p.is_file() and p!=export/'SHA256SUMS')
(export/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(export)}\n' for p in files))
print(json.dumps({'verdict':report['verdict'],'source_commit':head,'tests':standard['tests_run']+numeric['tests_run'],'targeted_mutants':18,'metrology_workers':20,'math_checks':45,'export_files':len(files),'export':str(export),'report_sha256':hashlib.sha256((export/'report.json').read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((export/'SHA256SUMS').read_bytes()).hexdigest()}))
