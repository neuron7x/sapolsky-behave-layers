from pathlib import Path
import csv,hashlib,json,os,subprocess,sys
out=Path(__file__).resolve().parent
root=out/'checkout'
base=out.parent.parent
live=base/'repo'
reference=base/'inputs/pr44-linear-reference.py'
python=base/'inputs/bnsyn-locked-venv/bin/python'
source_commit='f030a12b145bd8b43876c9e2d8b268e820e92b87'
records=[]
env=dict(os.environ)
env.update(PYTHONDONTWRITEBYTECODE='1',CNEH_PR44_REFERENCE=str(reference))
def execute(name,args,expected=0):
    proc=subprocess.run([str(x) for x in args],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    log=out/(name+'.log');log.write_text(proc.stdout)
    item={'name':name,'command':[str(x) for x in args],'cwd':str(root),'exit_code':proc.returncode,'expected_exit':expected,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
    records.append(item)
    (out/'commands.json').write_text(json.dumps(records,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'name':name,'exit_code':proc.returncode}),flush=True)
    assert proc.returncode==expected,proc.stdout[-5000:]
    return proc

def unittest_code(directory,pattern,minimum):
    return f'''import json,unittest
suite=unittest.defaultTestLoader.discover({directory!r},pattern={pattern!r})
result=unittest.TextTestRunner(verbosity=2).run(suite)
record={{'tests_run':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses)}}
print(json.dumps(record))
raise SystemExit(0 if result.wasSuccessful() and result.testsRun>={minimum} and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses else 1)
'''
standard=execute('standard-tests',[sys.executable,'-c',unittest_code('tests','test_cneh_exp_01*.py',74)])
standard=json.loads(standard.stdout.splitlines()[-1])
numeric=execute('numeric-tests',[python,'-c',unittest_code('tests/cneh_math','qualification_cases.py',14)])
numeric=json.loads(numeric.stdout.splitlines()[-1])
execute('mutations',[sys.executable,'experiments/cneh_exp_01/mutation_check.py','--out',out/'mutations'])
execute('numeric-mutations',[python,'experiments/cneh_exp_01/math_mutation_check.py','--reference',reference,'--out',out/'numeric-mutations'])
mutations=json.loads((out/'mutations/report.json').read_text());numeric_mutations=json.loads((out/'numeric-mutations/report.json').read_text())
for report,count in [(mutations,11),(numeric_mutations,7)]:
    assert report['status']=='PASS' and report['killed']==report['total']==count and report['source_unchanged_during_run'] is True
    assert all(m['status']=='KILLED' and m['unittest']['error_test_ids']==[] for m in report['mutants'])
execute('math-generate',[python,'experiments/cneh_exp_01/math_qualification.py','--reference',reference,'--out',out/'math-qualification.json'])
execute('math-verify',[python,'experiments/cneh_exp_01/math_qualification.py','--reference',reference,'--out',out/'math-qualification.json','--verify'])
math=json.loads((out/'math-qualification.json').read_text())
assert math['status']=='PASS' and len(math['checks'])==45 and all(v['pass'] for v in math['checks'].values())
assert math['scientific_promotion_authorized'] is False and math['causal_attribution_qualified'] is False
execute('metrology-measure',[sys.executable,'experiments/cneh_exp_01/metrology.py','--out',out/'metrology'])
execute('metrology-verify',[sys.executable,'experiments/cneh_exp_01/metrology.py','--out',out/'metrology','--verify'])
execute('metrology-qualified-cost',[sys.executable,'experiments/cneh_exp_01/metrology.py','--out',out/'metrology','--verify','--require-qualified-cost'],2)
metrology=json.loads((out/'metrology/report.json').read_text())
assert metrology['admission']=='PASS' and metrology['resource_parity_verified'] is False and metrology['scientific_promotion_authorized'] is False
assert all(v=='INSTRUMENT_INVALID' for v in metrology['instruments'].values())
assert len(metrology['workers'])==20 and len(metrology['inherited_timing']['raw'])==200
primary=root/'artifacts/cneh-exp-01-a1/primary'
execute('a1-primary-replay',[sys.executable,'experiments/cneh_exp_01/run.py','--out',primary,'--verify'])
execute('science-readiness',[sys.executable,'experiments/cneh_exp_01/qualification.py','--bundle',primary,'--require-scientific-readiness'],2)
science=json.loads((out/'science-readiness.log').read_text())
assert science['engineering_validation']=='PASS' and science['scientific_readiness']=='BLOCKED' and science['scientific_promotion_authorized'] is False
execute('a1-bnsyn-replay',[python,'experiments/cneh_exp_01/bnsyn_adapter.py','--source',base/'inputs/bnsyn','--out',root/'artifacts/cneh-exp-01-a1/bnsyn','--verify'])
with (primary/'primary.csv').open() as stream:rows=list(csv.DictReader(stream))
assert len(rows)==1280
by={(int(row['seed']),row['arm']):row for row in rows}
assert sum(int(row['success']) for row in rows if row['arm']=='COUPLED')==122
assert all(by[seed,'COUPLED']['trace_sha256']==by[seed,'CENTRAL_EMULATOR']['trace_sha256'] for seed in range(51001,51129))
frozen={}
for name in ('protocol.json','PREREGISTRATION.md','frozen_sources.lock','CNEH-04-DC_Formal_Specification.md'):
    relative='experiments/cneh_exp_01/'+name
    original=subprocess.check_output(['git','show','4ccb02e7da16c4a65573e8e7c7e98a0b8456119b:'+relative],cwd=live)
    assert original==(root/relative).read_bytes(),relative
    frozen[name]=hashlib.sha256(original).hexdigest()
reconstruction=json.loads((out/'reconstruction.json').read_text())
changed=[]
for name,entry in reconstruction['source_files'].items():
    path=root/name
    data=path.readlink().as_posix().encode() if entry['mode']=='120000' else path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:changed.append(name)
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
assert not changed and actual==set(reconstruction['source_files']),{'changed':changed,'unexpected':list(actual-set(reconstruction['source_files']))}
current_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=live,text=True).strip()
current_status=subprocess.check_output(['git','status','--short'],cwd=live,text=True)
assert current_head==source_commit and current_status=='',{'head':current_head,'status':current_status}
report={'verdict':'PASS_WITH_CAVEATS','local_source_verification':'PASS','ENGINEERING_QUALIFIED':False,'acceptance_gates':{'G1':'PENDING_FINAL_PUSH_EQUALITY','G2':'PENDING_ALL_MANDATORY_FINAL_HEAD_CI','G3':'SOURCE_RECONSTRUCTION_AND_REPLAY_PASS_FINAL_HEAD_REPLAY_PENDING','G4':'BLOCKING_SCIENCE_STATUSES_PRESERVED'},'source_commit':source_commit,'source_archive_sha256':reconstruction['archive_sha256'],'source_tree_file_count':reconstruction['tracked_file_count'],'reconstructed_source_drift':False,'origin_diff_sha256':reconstruction['origin_diff_sha256'],'origin_status':current_status,'standard_tests':standard,'numeric_tests':numeric,'targeted_mutations':{'killed':mutations['killed'],'total':mutations['total'],'invalid':sum(m['status']=='INVALID_MUTANT' for m in mutations['mutants'])},'numeric_mutations':{'killed':numeric_mutations['killed'],'total':numeric_mutations['total'],'invalid':sum(m['status']=='INVALID_MUTANT' for m in numeric_mutations['mutants'])},'math_checks':len(math['checks']),'metrology':{'admission':metrology['admission'],'workers':len(metrology['workers']),'samples':sum(len(row['samples']) for row in metrology['workers']),'timing_batches':len(metrology['inherited_timing']['raw']),'instruments':metrology['instruments'],'resource_parity_verified':False},'primary':{'rows':1280,'successes':122,'world_seeds':128,'emulator_divergences':0},'neural_replay':'PASS','original_frozen_sha256':frozen,'scientific_promotion_authorized':False,'independent_external_replication':'NOT_TESTED','commands':records}
(out/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('commands','original_frozen_sha256')}),flush=True)
