import argparse, concurrent.futures, contextlib, copy, hashlib, importlib.util, io, json, os, subprocess, tempfile, threading
from pathlib import Path
os.umask(0o022)
repo=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo'); source=repo/'experiments/cneh_exp_01/acceptance.py'
spec=importlib.util.spec_from_file_location('acceptance_candidate',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
initial=sha(source); head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();results=[]
def record(name,passed,**data):
 results.append({'id':name,'negative_control_passed':passed,**data})
 if not passed:raise AssertionError(name)
with tempfile.TemporaryDirectory(prefix='redteam-a3-',dir=repo.parent/'evidence') as raw:
 base=Path(raw);fix=base/'fixture';fix.mkdir()
 def git(*args):return subprocess.check_output(['git',*args],cwd=fix,stderr=subprocess.PIPE).decode().strip()
 git('init','-q','--initial-branch='+mod.BRANCH)
 local=fix/mod.AUDITOR_PATH;local.parent.mkdir(parents=True);local.write_bytes(source.read_bytes());git('add','.')
 git('-c','user.name=Redteam fixture','-c','user.email=redteam@example.invalid','-c','commit.gpgsign=false','commit','-qm','isolated acceptance fixture'); target=git('rev-parse','HEAD')
 def args(out):return argparse.Namespace(repo=str(fix),out=str(out),final_sha=target)
 def cli(out,extra=()):return subprocess.run([os.sys.executable,'-B',source,'--repo',fix,'--final-sha',target,'--out',out,*extra],capture_output=True,text=True)
 oldout=base/'forged';oldout.mkdir();(oldout/'checkout').mkdir()
 (oldout/'local-replay-receipt.json').write_bytes(mod.canonical({'final_sha':target,'auditor_sha256':initial,'G3':{'status':'PASS'},'G4':{'status':'PASS','scientific_promotion_authorized':True}}))
 (oldout/'final-source-manifest.json').write_bytes(mod.canonical({'commit':'0'*40,'files':{}}))
 before={str(p.relative_to(oldout)):sha(p) for p in oldout.rglob('*') if p.is_file()}
 p=cli(oldout);after={str(q.relative_to(oldout)):sha(q) for q in oldout.rglob('*') if q.is_file()}
 record('old_cached_forgery_cli_rejected_unchanged',p.returncode==1 and not json.loads(p.stdout)['ENGINEERING_QUALIFIED'] and before==after,exit_code=p.returncode,stdout=p.stdout,unchanged=before==after)
 p=cli(base/'refresh',('--refresh',));record('removed_refresh_cli',p.returncode==2 and not (base/'refresh').exists(),exit_code=p.returncode,stderr=p.stderr)
 link=base/'dangling';link.symlink_to(base/'must-not-exist',target_is_directory=True);p=cli(link)
 record('dangling_symlink_cli',p.returncode==1 and link.is_symlink() and not (base/'must-not-exist').exists(),exit_code=p.returncode,stdout=p.stdout)
 barrier=threading.Barrier(2);shared=base/'concurrent'
 def reserve():
  barrier.wait()
  try:mod.Audit(args(shared));return 'reserved'
  except FileExistsError:return 'rejected'
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:outcomes=list(ex.map(lambda _:reserve(),range(2)))
 record('concurrent_writer',sorted(outcomes)==['rejected','reserved'],outcomes=outcomes)
 audit=mod.Audit(args(base/'fresh-incomplete'))
 try:audit.run();error=None
 except Exception as exc:error={'type':type(exc).__name__,'text':str(exc)}
 labels=[r['label'] for r in audit.records]
 record('fresh_reconstruction_executes_and_incomplete_source_rejected',error is not None and 'fresh-detached-worktree' in labels and 'auditor-source-binding' in labels and not list(audit.out.glob('acceptance-*.json')),exception=error,executed_labels=labels,fixture_worktree_count=git('worktree','list','--porcelain').count('worktree '))
 local.write_bytes(source.read_bytes()+b'\n# mismatched fixture source\n');git('add','.')
 git('-c','user.name=Redteam fixture','-c','user.email=redteam@example.invalid','-c','commit.gpgsign=false','commit','-qm','different bytes');target=git('rev-parse','HEAD')
 audit=mod.Audit(args(base/'source-mismatch'))
 try:audit.verify_auditor_binding();error=None
 except Exception as exc:error={'type':type(exc).__name__,'text':str(exc)}
 record('executing_source_mismatch',error is not None and error['type']=='ValueError',exception=error)
manifest=mod.read(repo/mod.CHECKS_PATH);checks=[];runs=[]
for i,row in enumerate(manifest['required_contexts'],1):
 checks.append({'id':i,'name':row['name'],'head_sha':head,'status':'completed','conclusion':'success','app':{'id':row['app_id'],'slug':row['app_slug']},'check_suite':{'id':100+i},'details_url':f'https://github.com/{mod.REPOSITORY}/actions/runs/{200+i}/job/{i}'})
 if row['workflow_path'] is not None:runs.append({'id':200+i,'check_suite_id':100+i,'head_sha':head,'path':row['workflow_path'],'event':row['event'],'status':'completed','conclusion':'success'})
record('ci_positive_control',mod.ci_provenance(checks,runs,manifest,head)['status']=='PASS' and mod.classify_ci(checks,[])['status']=='PASS')
for name,field,value,expected in [('pending_workflow','status','in_progress','UNKNOWN'),('failed_workflow','conclusion','failure','FAIL'),('neutral_workflow','conclusion','neutral','FAIL'),('other_workflow_sha','head_sha','0'*40,'FAIL'),('other_workflow_path','path','.github/workflows/invented.yml','FAIL')]:
 changed=copy.deepcopy(runs);changed[0][field]=value;observed=mod.ci_provenance(checks,changed,manifest,head)['status'];record(name,observed==expected,observed=observed,expected=expected)
changed=copy.deepcopy(runs)
for run in changed:
 if run['path']=='.github/workflows/cwc-doc-gates.yml':run['event']='pull_request'
observed=mod.ci_provenance(checks,changed,manifest,head)['status'];record('duplicate_job_name_does_not_substitute_push_event',observed=='FAIL',observed=observed)
changed=copy.deepcopy(checks);changed[0]['app']={'id':0,'slug':'invented'};observed=mod.ci_provenance(changed,runs,manifest,head)['status'];record('wrong_app_identity',observed=='FAIL',observed=observed)
record('source_unchanged_during_probe',sha(source)==initial)
report={'schema':'cneh-a3-independent-redteam-v1','source_commit':head,'auditor_sha256':initial,'tests_sha256':sha(repo/'tests/test_cneh_exp_01_acceptance.py'),'required_checks_manifest_sha256':sha(repo/mod.CHECKS_PATH),'scope':'bounded independent local probes; no network; isolated fresh reconstruction deliberately incomplete and rejected; no production source edits','status':'SCOPED_PROBES_PASSED','results':results,'not_run':['actual final committed fresh complete G3/G4','actual GitHub G1/G2','broad scientific suites','external replication'],'scientific_promotion_authorized':False,'ENGINEERING_QUALIFIED':False}
p=repo.parent/'evidence/redteam-a3-final/replacement-probes.json';p.write_bytes(mod.canonical(report));print(json.dumps({'receipt':str(p),'sha256':sha(p),'probes':len(results),'status':report['status']}))
