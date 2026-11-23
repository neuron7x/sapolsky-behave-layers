"""Authoritative A3 G1/G2/G3/G4 auditor; every invocation performs fresh replay. Runs only with an explicitly supplied delivery SHA.

All outputs are outside the repository. Local replay is separate from published
CI and is never labeled external scientific replication. UNKNOWN cannot pass.
"""
from __future__ import annotations
import argparse, csv, datetime, gzip, hashlib, io, json, math, os, re, subprocess, sys, tarfile, uuid
from pathlib import Path

SOURCE='f030a12b145bd8b43876c9e2d8b268e820e92b87'
ORIGINAL='4ccb02e7da16c4a65573e8e7c7e98a0b8456119b'
A1='a65ab49681bc748acb71cde9abe5bc99a4045ab3'
A2='f5625363f72be3652d6b6e6fbfad1ceeac57e857'
A3_CONTRACT='ff4dc6a77124ae3575788a2b953cbbc2f4872d2a'
A4_CONTRACT='3c0feee217e22647997b3888173f372dbeb2f01f'
A4_PATH='experiments/cneh_exp_01/SUPPLY_CHAIN_AMENDMENT_A4.md'
REPOSITORY='neuron7x/sapolsky-behave-layers'
BRANCH='research/cneh-exp-01'
AUDITOR_PATH='experiments/cneh_exp_01/acceptance.py'
CHECKS_PATH='experiments/cneh_exp_01/required_checks_manifest.json'
PROVENANCE_PATH='experiments/cneh_exp_01/provenance.py'
PROVENANCE_TEST='tests/test_cneh_exp_01_provenance.py'
LEDGER_PATH='docs/lab/EXPERIMENT_LEDGER.jsonl'
A3_ADDITIONS={AUDITOR_PATH,CHECKS_PATH,A4_PATH,PROVENANCE_PATH,PROVENANCE_TEST,'experiments/cneh_exp_01/LABORATORY_QUALIFICATION_PROTOCOL.md','experiments/cneh_exp_01/ACCEPTANCE_AMENDMENT_A3.md','tests/test_cneh_exp_01_acceptance.py'}
A2_REPORT_SHA='90c36c2850a61411ea828c4cf03554c077bea560393cb91dedde2651cb1de059'
G4_RECEIPT_SHA='606bc900695c7b98c130ee53fd0a346a965afbf0d8bb69dca7027fbeb8a93412'
G4_CHECK_IDS={
 'exact_source_commit','clean_source_worktree','source_bytes_match_commit','four_original_files_unchanged',
 'all_preexisting_CWC_artifacts_preserved','explicit_CWC_history_preserved','A1_entire_evidence_preserved','A1_negative_evidence_preserved',
 'CWC_normative_claim_boundaries_unchanged','historical_ledger_rows_preserved','A1_negative_files_present',
 'artifacts/cneh-exp-01-a1/primary_manifest','artifacts/cneh-exp-01-a1/bnsyn_manifest',
 'science_readiness','scientific_authority_locked','structural_positive_conjunction_impossible',
 'resigned_positive_promotion_rejected','semantic_promotion_falsifier',
 'physical_cost_readiness','physical_cost_unqualified','six_neural_claim_boundaries',
 'internal_commitment_cannot_prove_external_replication',
 'all_scoped_promotion_and_unearned_authority_flags_false','analytic_math_scope_unpromoted','final_source_unchanged',
}
REQUIRED_CHECKS={
 'CodeQL','Audit Python tooling dependencies','Scan complete Git history for secrets',
 'Reject vulnerable dependency changes','Validate GitHub Actions',
 'Fractal multiscale verification','CodeQL Python analysis','doc-and-evidence-gates',
 'quality','Full verification, validation, and falsification',
 'preflight (3.11)','preflight (3.12)','Pinned BN-Syn integration smoke (no efficacy claim)',
}

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def read(path):
 def pairs(rows):
  out={}
  for key,val in rows:
   if key in out:raise ValueError('duplicate JSON key')
   out[key]=val
  return out
 def bad(value):raise ValueError('nonfinite JSON constant '+value)
 def finite(value):
  number=float(value)
  if not math.isfinite(number):raise ValueError('nonfinite JSON number')
  return number
 return json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)
def safe(root,relative):
 p=Path(relative)
 if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('unsafe relative path')
 out=root/p
 if out.is_symlink() or not out.is_file():raise ValueError('missing or symlinked evidence '+relative)
 if any(parent.is_symlink() for parent in out.parents if parent!=root and root in parent.parents):raise ValueError('symlink parent')
 return out

def classify_ci(checks,statuses):
 names={c['name'] for c in checks};missing=sorted(REQUIRED_CHECKS-names)
 failed=[c for c in checks if c['status']=='completed' and c['conclusion']!='success']
 pending=[c for c in checks if c['status']!='completed']
 bad_statuses=[s for s in statuses if s['state']!='success']
 if failed or missing or not checks or any(s['state'] in ('error','failure') for s in bad_statuses):state='FAIL'
 elif pending or bad_statuses:state='UNKNOWN'
 else:state='PASS'
 return {'status':state,'required_names':sorted(REQUIRED_CHECKS),'missing_required_names':missing,
         'observed_check_count':len(checks),'failed_checks':failed,'pending_checks':pending,
         'non_success_commit_statuses':bad_statuses,'all_observed_checks':checks,'commit_statuses':statuses}

def canonical_remote(url):
 return url in ('https://github.com/'+REPOSITORY+'.git','https://github.com/'+REPOSITORY,
                'git@github.com:'+REPOSITORY+'.git','ssh://git@github.com/'+REPOSITORY+'.git')

def ci_provenance(checks,runs,manifest,final_sha):
 """Bind required identities independently of their human-readable job names."""
 keys=('name','app_id','app_slug','workflow_path','event')
 def identity(row):return tuple(row[k] for k in keys)
 required={identity(row) for row in manifest['required_contexts']}
 allowed=required|{identity(row) for row in manifest['allowed_optional_contexts']}
 seen=set();errors=[];bindings=[];pending=False
 for run in runs:
  if run.get('head_sha')!=final_sha:errors.append('workflow SHA mismatch')
  if run.get('status')!='completed':pending=True
  elif run.get('conclusion')!='success':errors.append('workflow did not succeed')
 by_suite={}
 for run in runs:
  by_suite.setdefault(run['check_suite_id'],[]).append(run)
 for check in checks:
  app=check.get('app') or {};app_id=app.get('id');slug=app.get('slug')
  row={'name':check['name'],'app_id':app_id,'app_slug':slug,'workflow_path':None,'event':None}
  binding={'check_run_id':check['id'],'name':check['name'],'app_id':app_id,'app_slug':slug,'check_suite_id':(check.get('check_suite') or {}).get('id')}
  if check.get('head_sha')!=final_sha:errors.append('check SHA mismatch')
  if app_id==15368 and slug=='github-actions':
   candidates=[r for r in by_suite.get(binding['check_suite_id'],[]) if r.get('head_sha')==final_sha]
   match=re.fullmatch(r'https://github\.com/'+re.escape(REPOSITORY)+r'/actions/runs/([0-9]+)/job/([0-9]+)',check.get('details_url') or '')
   candidates=[r for r in candidates if match and r['id']==int(match.group(1))]
   if len(candidates)!=1:
    errors.append('unbound workflow/job identity');bindings.append(binding);continue
   run=candidates[0];row.update(workflow_path=run['path'],event=run['event'])
   binding.update(workflow_run_id=run['id'],workflow_path=run['path'],event=run['event'],job_url=check['details_url'])
  token=identity(row)
  if token not in allowed:errors.append('unregistered check source/event/app')
  else:seen.add(token)
  bindings.append(binding)
 missing=sorted(required-seen,key=repr)
 return {'status':'FAIL' if errors or missing else ('UNKNOWN' if pending else 'PASS'),'missing_required_contexts':[dict(zip(keys,row)) for row in missing],
         'source_binding_errors':errors,'source_bindings':bindings}

def preserved_ledger_inventory(rows,old_rows):
 if len({r['run_id'] for r in rows})!=len(rows):raise ValueError('duplicate historical ledger identity')
 current={r['run_id']:canonical(r) for r in rows}
 if any(current.get(r['run_id'])!=canonical(r) for r in old_rows):raise ValueError('historical ledger row deleted or rewritten')
 unchecked={r['run_id']:r for r in old_rows if r.get('has_checksums') is False}
 if len(unchecked)!=3:raise ValueError('unexpected historical checksum omission inventory')
 for row in rows:
  if row.get('experiment')=='CNEH-EXP-01' and row.get('verdict')!='REPLICATION_NOT_TESTED':raise ValueError('CNEH ledger authority promotion')
  if row.get('has_checksums') is False and canonical(row)!=canonical(unchecked.get(row['run_id'])):raise ValueError('new unchecked historical evidence')
 return unchecked

class Audit:
 def __init__(self,args):
  self.args=args;self.repo=Path(args.repo).resolve();self.base=self.repo.parent
  # Do not resolve the final component: a dangling symlink is an existing output.
  self.out=Path(os.path.abspath(args.out))
  if self.out.is_relative_to(self.repo):raise ValueError('outputs must be outside the repository')
  if any(p.is_symlink() for p in (self.out,*self.out.parents)):raise FileExistsError('symlinked output path forbidden')
  self.out.mkdir(parents=True,exist_ok=False)
  self.records=[];self.sequence=0
  self.auditor_sha256=sha(Path(__file__).read_bytes());self.replay_id=str(uuid.uuid4())
  self.gates={name:{'status':'UNKNOWN','reason':'not executed'} for name in ('G1','G2','G3','G4')};self.active_gate=None
  self.checkout=self.out/'checkout'
  self.python=self.base/'inputs/bnsyn-locked-venv/bin/python'
  self.reference=self.base/'inputs/pr44-linear-reference.py'
 def command(self,label,args,cwd=None,expected=0,input_bytes=None,timeout=180):
  self.sequence+=1;stem=f'command-{self.sequence:03d}-{label}';start=now()
  env=dict(os.environ);env.update(PYTHONDONTWRITEBYTECODE='1',CNEH_PR44_REFERENCE=str(self.reference))
  p=subprocess.run([str(x) for x in args],cwd=cwd or self.repo,env=env,input=input_bytes,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
  (self.out/(stem+'.stdout')).write_bytes(p.stdout);(self.out/(stem+'.stderr')).write_bytes(p.stderr)
  record={'label':label,'command':[str(x) for x in args],'cwd':str(cwd or self.repo),'start_utc':start,'end_utc':now(),'exit_code':p.returncode,'expected_exit_code':expected,'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr),'stdout_file':stem+'.stdout','stderr_file':stem+'.stderr'}
  (self.out/(stem+'.json')).write_bytes(canonical(record));self.records.append(record)
  if expected is not None and p.returncode!=expected:raise RuntimeError(f'{label}: exit {p.returncode}, expected {expected}; see {stem}')
  return p.stdout
 def api(self,label,endpoint):return json.loads(self.command(label,['gh','api',endpoint]))
 def git(self,*args):return self.command('git-'+args[0],['git',*args]).decode().strip()
 def tree(self,ref,prefix=None):
  args=['git','ls-tree','-r','-z',ref]
  if prefix:args+=['--',prefix]
  raw=self.command('tree-'+ref[:8],args);out={}
  for entry in raw.split(b'\0'):
   if not entry:continue
   meta,path=entry.split(b'\t',1);mode,kind,blob=meta.decode().split()
   if kind!='blob':raise ValueError('non-blob in reconstruction')
   out[path.decode()]={'mode':mode,'git_blob_sha1':blob}
  return out
 def g1(self):
  profile=self.api('github-actor','user')
  if profile['login']!='neuron7x':raise ValueError('GitHub actor is not neuron7x')
  origin=self.git('remote','get-url','origin')
  if not canonical_remote(origin):raise ValueError('origin is not the canonical neuron7x repository')
  status=self.command('local-porcelain',['git','status','--porcelain=v1','--untracked-files=all']).decode()
  head=self.git('rev-parse','HEAD');branch=self.git('branch','--show-current')
  upstream_name=self.git('rev-parse','--symbolic-full-name','@{upstream}');upstream=self.git('rev-parse','@{upstream}')
  worktrees=self.command('current-worktrees',['git','worktree','list','--porcelain']).decode()
  remote_repo=self.api('canonical-repository','repos/'+REPOSITORY)
  if remote_repo['full_name']!=REPOSITORY:raise ValueError('canonical owner changed')
  remote=self.command('origin-ls-remote',['git','ls-remote','--exit-code','origin','refs/heads/'+BRANCH]).decode().strip().split()
  if len(remote)!=2 or remote[1]!='refs/heads/'+BRANCH:raise ValueError('ambiguous remote branch')
  bare=self.out/'remote-proof.git'
  if not bare.exists():self.command('audit-bare-init',['git','init','--bare',bare],cwd=self.out)
  self.command('canonical-fetch',['git','-C',bare,'-c','credential.helper=','-c','credential.helper=!gh auth git-credential','fetch','--no-tags','--depth=1','https://github.com/'+REPOSITORY+'.git','refs/heads/'+BRANCH],cwd=self.out)
  fetched=self.command('fetched-head',['git','-C',bare,'rev-parse','FETCH_HEAD'],cwd=self.out).decode().strip()
  pr=self.api('pr-head','repos/'+REPOSITORY+'/pulls/43');remote_branch=self.api('remote-branch','repos/'+REPOSITORY+'/git/ref/heads/'+BRANCH)
  remote_tip=remote_branch['object']['sha'];pr_sha=pr['head']['sha']
  branches=(pr['head']['ref']==BRANCH and pr['base']['ref']=='main' and pr['head']['repo']['full_name']==REPOSITORY and pr['base']['repo']['full_name']==REPOSITORY)
  base_sha=pr['base']['sha'];merge_sha=pr.get('merge_commit_sha')
  self.command('base-object-available',['git','cat-file','-e',base_sha+'^{commit}'],expected=None)
  ancestry_repo=self.repo
  if self.records[-1]['exit_code']!=0:
   ancestry_repo=self.out/'replay.git'
   self.command('canonical-base-fetch',['git','-C',ancestry_repo,'-c','credential.helper=','-c','credential.helper=!gh auth git-credential','fetch','--no-tags','https://github.com/'+REPOSITORY+'.git',base_sha],cwd=self.out)
  self.command('base-is-ancestor',['git','-C',ancestry_repo,'merge-base','--is-ancestor',base_sha,self.args.final_sha],expected=None)
  ancestry_exit=self.records[-1]['exit_code']
  if ancestry_exit not in (0,1):raise ValueError('base ancestry could not be established')
  final_tree=self.git('rev-parse',self.args.final_sha+'^{tree}')
  merge_tree=None
  if merge_sha is not None:
   if not re.fullmatch('[0-9a-f]{40}',merge_sha):raise ValueError('invalid PR merge SHA')
   merge_tree=self.api('pr-merge-commit','repos/'+REPOSITORY+'/git/commits/'+merge_sha)['tree']['sha']
  state='PASS' if not status and branch==BRANCH and branches and upstream_name=='refs/remotes/origin/'+BRANCH and head==upstream==remote[0]==fetched==remote_tip==pr_sha==self.args.final_sha else 'FAIL'
  unpublished=int(self.command('unpublished-commits',['git','rev-list','--count',upstream+'..HEAD']).decode())
  if unpublished!=0 or ancestry_exit!=0 or (merge_tree is not None and merge_tree!=final_tree):state='FAIL'
  elif state=='PASS' and (merge_sha is None or pr.get('mergeable') is None):state='UNKNOWN'
  l0=self.collect_provenance('l0','l0-'+str(self.sequence))
  return {'status':state,'base_sha':base_sha,'base_is_ancestor':ancestry_exit==0,'merge_commit_sha':merge_sha,'merge_tree_sha':merge_tree,'final_tree_sha':final_tree,'l0_provenance':l0,'actor':profile['login'],'origin_url':origin,'local_status_porcelain':status,'local_branch':branch,'local_head':head,'upstream_name':upstream_name,'upstream_sha':upstream,'ls_remote_sha':remote[0],'fetched_canonical_head':fetched,'remote_api_head':remote_tip,'pr_head':pr_sha,'pr_head_branch':pr['head']['ref'],'pr_base_branch':pr['base']['ref'],'pr_mergeable':pr.get('mergeable'),'pr_mergeable_state':pr.get('mergeable_state'),'unpublished_commits_after_fetch':unpublished,'canonical_repository':REPOSITORY,'worktrees':worktrees}
 def g2(self):
  manifest=read(safe(self.checkout,CHECKS_PATH))
  if manifest['schema']!='cneh-required-checks-v1' or manifest['repository']!=REPOSITORY or manifest['scientific_promotion_authorized'] is not False:raise ValueError('invalid required checks contract')
  for path,digest in manifest['workflow_sources_sha256'].items():
   if sha(safe(self.checkout,path).read_bytes())!=digest:raise ValueError('workflow source drift')
  checks=[];page=1;total=None
  while True:
   data=self.api('checks-'+str(page),f'repos/{REPOSITORY}/commits/{self.args.final_sha}/check-runs?filter=all&per_page=100&page={page}')
   if total is None:total=data['total_count']
   if total!=data['total_count']:raise ValueError('check-run pagination changed')
   rows=data['check_runs'];checks.extend({k:c.get(k) for k in ('id','name','head_sha','status','conclusion','details_url','started_at','completed_at','app','check_suite')} for c in rows)
   if len(checks)>=total:break
   if not rows:raise ValueError('incomplete check-run pagination')
   page+=1
  if len(checks)!=total or len({c['id'] for c in checks})!=len(checks) or any(c['head_sha']!=self.args.final_sha for c in checks):raise ValueError('check-run identity mismatch')
  runs=[];page=1;total=None
  while True:
   data=self.api('workflow-runs-'+str(page),f'repos/{REPOSITORY}/actions/runs?head_sha={self.args.final_sha}&per_page=100&page={page}')
   if total is None:total=data['total_count']
   if total!=data['total_count']:raise ValueError('workflow pagination changed')
   rows=data['workflow_runs'];runs.extend({k:r.get(k) for k in ('id','check_suite_id','head_sha','path','event','html_url','status','conclusion')} for r in rows)
   if len(runs)>=total:break
   if not rows:raise ValueError('incomplete workflow pagination')
   page+=1
  if len(runs)!=total or len({r['id'] for r in runs})!=len(runs):raise ValueError('workflow identity mismatch')
  statuses=[];page=1
  while True:
   rows=self.api('statuses-'+str(page),f'repos/{REPOSITORY}/commits/{self.args.final_sha}/statuses?per_page=100&page={page}')
   statuses.extend({k:s.get(k) for k in ('id','context','state','target_url','updated_at','creator')} for s in rows)
   if len(rows)<100:break
   page+=1
  if len({r['id'] for r in statuses})!=len(statuses):raise ValueError('duplicate legacy status')
  result=classify_ci(checks,statuses);provenance=ci_provenance(checks,runs,manifest,self.args.final_sha)
  if provenance['status']=='FAIL':result['status']='FAIL'
  elif provenance['status']=='UNKNOWN' and result['status']=='PASS':result['status']='UNKNOWN'
  result.update(provenance=provenance,workflow_runs=runs,required_checks_manifest_sha256=sha(safe(self.checkout,CHECKS_PATH).read_bytes()))
  return result
 def collect_provenance(self,mode,label):
  helper=safe(self.checkout,PROVENANCE_PATH)
  original=self.command('provenance-source-binding',['git','show',self.args.final_sha+':'+PROVENANCE_PATH])
  if sha(helper.read_bytes())!=sha(original):raise ValueError('provenance helper source differs from final SHA')
  target=self.out/label
  self.command('collect-'+mode,[self.python,'-B',helper,'--repo',self.repo,'--final-sha',self.args.final_sha,'--out',target,'--mode',mode,'--inputs',self.base/'inputs'],cwd=self.checkout)
  filename,key=('provenance.json','inventory_integrity') if mode=='l0' else ('ci-artifacts.json','artifact_integrity')
  receipt=safe(target,filename);value=read(receipt)
  if value['final_sha']!=self.args.final_sha or value[key]!='PASS':raise ValueError('incomplete fresh provenance collection')
  return {'status':'PASS','scope':'COLLECTION_INTEGRITY_ONLY','path':str(receipt.relative_to(self.out)),'sha256':sha(receipt.read_bytes()),'helper_sha256':sha(original)}
 def verify_auditor_binding(self):
  raw=self.command('auditor-source-binding',['git','show',self.args.final_sha+':'+AUDITOR_PATH])
  if sha(raw)!=self.auditor_sha256 or sha(Path(__file__).read_bytes())!=self.auditor_sha256:
   raise ValueError('executing auditor differs from final SHA source')
  return self.auditor_sha256
 def reconstruct(self):
  if self.checkout.exists():raise FileExistsError('fresh final archive required')
  archive=self.out/'final-source.tar'
  self.command('final-git-archive',['git','archive','--format=tar','--output='+str(archive),self.args.final_sha])
  embedded=self.command('archive-commit',['git','get-tar-commit-id'],input_bytes=archive.read_bytes()).decode().strip()
  if embedded!=self.args.final_sha:raise ValueError('archive commit mismatch')
  bare=self.out/'replay.git'
  self.command('isolated-replay-clone',['git','clone','--bare','--no-hardlinks',self.repo,bare],cwd=self.out)
  self.command('fresh-detached-worktree',['git','--git-dir='+str(bare),'worktree','add','--detach',self.checkout,self.args.final_sha],cwd=self.out)
  head=self.command('replay-head',['git','rev-parse','HEAD'],cwd=self.checkout).decode().strip()
  branch=self.command('replay-detached',['git','branch','--show-current'],cwd=self.checkout).decode().strip()
  if head!=self.args.final_sha or branch:raise ValueError('replay is not detached at final SHA')
  self.worktree_git_pointer=(self.checkout/'.git').read_bytes()
  tree=self.tree(self.args.final_sha)
  for relative,entry in tree.items():
   p=self.checkout/relative
   payload=p.readlink().as_posix().encode() if entry['mode']=='120000' else p.read_bytes()
   if hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()!=entry['git_blob_sha1']:raise ValueError('Git blob mismatch '+relative)
   entry['sha256']=sha(payload)
  self.source_tree=tree
  self.check_no_drift()
  receipt={'commit':embedded,'archive_sha256':sha(archive.read_bytes()),'file_count':len(tree),'files':tree}
  (self.out/'final-source-manifest.json').write_bytes(canonical(receipt));return receipt
 def check_no_drift(self):
  if (self.checkout/'.git').read_bytes()!=self.worktree_git_pointer:raise ValueError('detached worktree metadata changed')
  head=self.command('replay-head-stable',['git','rev-parse','HEAD'],cwd=self.checkout).decode().strip()
  branch=self.command('replay-still-detached',['git','branch','--show-current'],cwd=self.checkout).decode().strip()
  if head!=self.args.final_sha or branch:raise ValueError('detached replay identity drift')
  actual={str(p.relative_to(self.checkout)) for p in self.checkout.rglob('*') if p.is_file() or p.is_symlink()}
  # A detached worktree has exactly one Git administrative pointer outside tracked source.
  actual.discard('.git')
  caches=actual-set(self.source_tree)
  allowed={'experiments/cneh_exp_01/__pycache__/run.cpython-312.pyc','experiments/cneh_exp_01/__pycache__/hardware.cpython-312.pyc'}
  if caches-allowed or set(self.source_tree)-actual:raise ValueError('final worktree member drift')
  if caches:
   code="""import hashlib,importlib.util,json,pathlib,py_compile,sys,tempfile
root=pathlib.Path(sys.argv[1]);evidence=[]
with tempfile.TemporaryDirectory(prefix='cneh-acceptance-cache-') as directory:
 for i,name in enumerate(json.loads(sys.argv[2])):
  p=root/name;source=importlib.util.source_from_cache(str(p));expected=pathlib.Path(directory)/str(i)
  py_compile.compile(source,cfile=str(expected),dfile=source,doraise=True,invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
  if p.read_bytes()!=expected.read_bytes():raise ValueError('runtime cache differs from canonical compile')
  evidence.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps(evidence))
"""
   self.command('runtime-cache-adjudication',[self.python,'-I','-B','-c',code,self.checkout,json.dumps(sorted(caches))])
  for relative,entry in self.source_tree.items():
   p=self.checkout/relative;data=p.readlink().as_posix().encode() if entry['mode']=='120000' else p.read_bytes()
   if sha(data)!=entry['sha256']:raise ValueError('final archive source drift '+relative)
 def manifests(self):
  receipts=[]
  roots=[self.checkout/('artifacts/'+name) for name in ('cneh-exp-01-a1','cneh-exp-01-a2-ci','cneh-exp-01-a2')]
  roots+=sorted((self.checkout/'artifacts').glob('cneh-exp-01-a3*'))
  for root in roots:
   if not root.is_dir():raise ValueError('missing delivery evidence root')
   for manifest in sorted([*root.rglob('SHA256SUMS'),*root.rglob('VERIFIER_SHA256SUMS')]):
    rows={}
    for line in manifest.read_text().splitlines():
     if not re.fullmatch(r'[0-9a-f]{64}  .+',line):raise ValueError('invalid manifest record')
     digest,relative=line.split('  ',1)
     if relative in rows:raise ValueError('duplicate manifest member')
     p=safe(manifest.parent,relative)
     if sha(p.read_bytes())!=digest:raise ValueError('manifest mismatch '+str(p))
     rows[relative]=digest
    actual={str(p.relative_to(manifest.parent)) for p in manifest.parent.rglob('*') if p.is_file() and p!=manifest}
    if not rows or (manifest.name=='SHA256SUMS' and set(rows)!=actual):raise ValueError('manifest roster mismatch '+str(manifest))
    receipts.append({'path':str(manifest.relative_to(self.checkout)),'sha256':sha(manifest.read_bytes()),'members':len(rows)})
  return receipts
 def g3(self):
  reconstruction=self.reconstruct();base=self.tree(SOURCE)
  def reused_scope(p):
   return p.startswith(('experiments/cneh_exp_01/','tests/cneh_math/','cwc/causal/')) or re.fullmatch(r'tests/test_cneh_exp_01.*\.py',p) or p in ('cwc/__init__.py','pyproject.toml','uv.lock','cwc-requirements-dev.txt')
  relevant={p for p in base if reused_scope(p)}
  final_relevant={p for p in self.source_tree if reused_scope(p)}
  if final_relevant!=relevant|A3_ADDITIONS:raise ValueError('tested implementation/lock/test roster changed')
  if sha(safe(self.checkout,AUDITOR_PATH).read_bytes())!=self.auditor_sha256:raise ValueError('final worktree auditor binding mismatch')
  if any(self.source_tree[p]['git_blob_sha1']!=base[p]['git_blob_sha1'] or self.source_tree[p]['mode']!=base[p]['mode'] for p in relevant):raise ValueError('tested implementation/lock/test bytes changed')
  for relative in sorted(A3_ADDITIONS-{AUDITOR_PATH,CHECKS_PATH,PROVENANCE_PATH,PROVENANCE_TEST,'tests/test_cneh_exp_01_acceptance.py'}):
   contract_commit=A4_CONTRACT if relative==A4_PATH else A3_CONTRACT
   frozen=self.command('a3-frozen-contract',['git','show',contract_commit+':'+relative])
   if frozen!=safe(self.checkout,relative).read_bytes():raise ValueError('A3 frozen normative contract changed')
  manifests=self.manifests()
  a2=self.checkout/'artifacts/cneh-exp-01-a2';report_path=a2/'verification/report.json'
  if sha(report_path.read_bytes())!=A2_REPORT_SHA:raise ValueError('independent source receipt differs from verified receipt')
  report=read(report_path)
  if report['source_commit']!=SOURCE or report['local_source_verification']!='PASS' or report['tracked_source_drift'] is not False:raise ValueError('invalid reused source verification')
  mapping=read(a2/'evidence-map.json');rows=mapping['rows']
  if mapping['source_commit']!=SOURCE or mapping['authority']!='ENGINEERING_ONLY' or len(rows)<16 or len({r['id'] for r in rows})!=len(rows):raise ValueError('invalid evidence map')
  for row in rows:
   for name in ('implementation','test'):
    binding=row[name];p=safe(self.checkout,binding['path'])
    if binding['git_commit']!=SOURCE or sha(p.read_bytes())!=binding['sha256'] or type(binding['line']) is not int or not 1<=binding['line']<=len(p.read_text().splitlines()):raise ValueError('source/test map binding mismatch')
   if sha(safe(self.checkout,row['artifact_path']).read_bytes())!=row['artifact_sha256']:raise ValueError('artifact map binding mismatch')
  generated=self.out/'generated';generated.mkdir()
  def execute(label,script,*options,expected=0):
   return self.command(label,[self.python,'-B','experiments/cneh_exp_01/'+script,*options],cwd=self.checkout,expected=expected)
  # Count each new module explicitly: unrelated tests cannot hide empty discovery.
  test_execution={}
  for label,directory,pattern,minimum in (
   ('stdlib-tests','tests','test_cneh_exp_01*.py',111),
   ('acceptance-tests','tests','test_cneh_exp_01_acceptance.py',19),
   ('provenance-tests','tests','test_cneh_exp_01_provenance.py',18),
   ('math14-tests','tests/cneh_math','qualification_cases.py',14)):
   unit="import json,unittest; s=unittest.defaultTestLoader.discover("+repr(directory)+",pattern="+repr(pattern)+"); r=unittest.TextTestRunner(verbosity=2).run(s); print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)})); raise SystemExit(0 if r.wasSuccessful() and r.testsRun>="+str(minimum)+" and not r.skipped and not r.expectedFailures and not r.unexpectedSuccesses else 1)"
   raw=self.command(label,[self.python,'-B','-c',unit],cwd=self.checkout)
   test_execution[label]=json.loads(raw.decode().strip().splitlines()[-1])
  execute('primary-generate','run.py','--phase','primary','--out',generated/'primary')
  execute('primary-verify','run.py','--out',generated/'primary','--verify')
  primary=(generated/'primary/primary.csv').read_bytes()
  if primary!=(self.checkout/'artifacts/cneh-exp-01-a1/primary/primary.csv').read_bytes():raise ValueError('PRIMARY exact replay mismatch')
  primary_records=list(csv.DictReader(io.StringIO(primary.decode())))
  primary_rows=len(primary_records);worlds=len({row['seed'] for row in primary_records})
  successes={arm:sum(row['success']==row['safe']==row['budget_ok']=='1' for row in primary_records if row['arm']==arm) for arm in ('COUPLED','CENTRAL_EMULATOR')}
  if primary_rows!=1280 or worlds!=128 or successes!={'COUPLED':122,'CENTRAL_EMULATOR':122}:raise ValueError('PRIMARY frozen replay counts mismatch')
  execute('math45-generate','math_qualification.py','--reference',self.reference,'--out',generated/'math.json')
  execute('math45-verify','math_qualification.py','--reference',self.reference,'--out',generated/'math.json','--verify')
  math=read(generated/'math.json')
  if len(math['checks'])!=45 or not all(v['pass'] is True for v in math['checks'].values()):raise ValueError('math fixture count or status mismatch')
  for folder,script,total in (('mutations','mutation_check.py',11),('math-mutations','math_mutation_check.py',7)):
   options=['--out',generated/folder]
   if total==7:options+=['--reference',self.reference]
   execute(folder,script,*options)
   mutation=read(generated/folder/'report.json')
   if mutation['status']!='PASS' or mutation['total']!=total or mutation['killed']!=total or mutation['source_unchanged_during_run'] is not True:raise ValueError('mutation calibration failed')
  execute('metrology-generate','metrology.py','--out',generated/'metrology')
  execute('metrology-verify','metrology.py','--out',generated/'metrology','--verify')
  execute('physical-cost-remains-blocked','metrology.py','--out',generated/'metrology','--verify','--require-qualified-cost',expected=2)
  execute('neural-generate','bnsyn_adapter.py','--source',self.base/'inputs/bnsyn','--out',generated/'bnsyn')
  execute('neural-verify','bnsyn_adapter.py','--source',self.base/'inputs/bnsyn','--out',generated/'bnsyn','--verify')
  neural=gzip.decompress((generated/'bnsyn/traces.json.gz').read_bytes())
  if neural!=gzip.decompress((self.checkout/'artifacts/cneh-exp-01-a1/bnsyn/traces.json.gz').read_bytes()):raise ValueError('neural exact replay mismatch')
  # Historical binary outcomes are replayed too; the saved verdict is never an admission input.
  execute('historical-primary-verify','run.py','--out',self.checkout/'artifacts/cneh-exp-01-a1/primary','--verify')
  history=self.historical_ledger()
  ci_artifacts=self.collect_provenance('ci-artifacts','ci-artifacts')
  self.check_no_drift()
  return {'status':'PASS','final_archive_sha256':reconstruction['archive_sha256'],'final_archive_files':reconstruction['file_count'],'reused_source_commit':SOURCE,'unchanged_implementation_lock_test_files':len(relevant),'executed_final_sha_replay':True,'source_unchanged_after_replay':True,'nested_manifests':manifests,'evidence_map_rows':len(rows),'reused_independent_report_sha256':A2_REPORT_SHA,
   'test_execution':test_execution,
   'source_integrity':{'status':'PASS','detached_worktree':str(self.checkout),'commit':self.args.final_sha,'a3_files':{p:sha(safe(self.checkout,p).read_bytes()) for p in sorted(A3_ADDITIONS)}},
   'primary_replay':{'status':'PASS','worlds':worlds,'rows':primary_rows,'safe_successes':successes,'sha256':sha(primary)},
   'artifact_replay':{'status':'PASS','manifest_count':len(manifests),'fresh_ci_artifacts':ci_artifacts},
   'historical_provenance':history,
   'mutation_coverage':{'status':'PASS','stdlib_killed':11,'numeric_killed':7},
   'mathematical_qualification':{'status':'PASS','tests':14,'checks':45,'scope':'ANALYTIC_FIXTURES_ONLY'},
   'neural_integration':{'status':'PASS','trace_payload_sha256':sha(neural),'scope':'INTEGRATION_ONLY'},
   'resource_metrology':{'status':'PASS','cost_status':'COST_INSTRUMENT_INVALID','qualified_cost_exit':2},
   'replication_tooling':{'status':'PASS','scope':'INTERNAL_COMMITMENT_CONSISTENCY_TESTS_ONLY'},
   'independent_replication':'NOT_TESTED','scientific_authority':'NOT_CLAIMED'}
 def historical_ledger(self):
  path=safe(self.checkout,LEDGER_PATH);rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
  if not rows:raise ValueError('empty historical ledger')
  selected=[row for row in rows if row.get('experiment')=='CNEH-EXP-01']
  if not selected:raise ValueError('missing CNEH historical ledger evidence')
  historical=self.command('original-ledger',['git','show',SOURCE+':'+LEDGER_PATH])
  old_rows=[json.loads(line) for line in historical.decode().splitlines() if line.strip()]
  old_missing=preserved_ledger_inventory(rows,old_rows)
  evidence=[]
  for row in rows:
   commit=row['evidence_commit']
   if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('invalid ledger commit')
   self.command('ledger-ancestor',['git','merge-base','--is-ancestor',commit,self.args.final_sha])
   if row.get('has_checksums') is False:
    if row!=old_missing.get(row['run_id']) or row.get('experiment')=='CNEH-EXP-01':raise ValueError('new or altered unchecked historical evidence')
    historical_tree=self.tree(commit,row['artifact_path'])
    current_tree={p:v for p,v in self.source_tree.items() if p.startswith(row['artifact_path']+'/')}
    if not historical_tree or set(historical_tree)!=set(current_tree) or any(current_tree[p]['git_blob_sha1']!=v['git_blob_sha1'] for p,v in historical_tree.items()):raise ValueError('unchecked historical source drift')
    evidence.append({'run_id':row['run_id'],'commit':commit,'checksum_verification':'UNKNOWN','scope':'UNCHANGED_LEGACY_PRESERVATION_ONLY'})
    continue
   manifest=safe(self.checkout,row['artifact_path']+'/SHA256SUMS')
   if row['has_checksums'] is not True or sha(manifest.read_bytes())!=row['sha256sums_hash']:raise ValueError('ledger checksum binding mismatch')
   original=self.command('ledger-historical-manifest',['git','show',commit+':'+row['artifact_path']+'/SHA256SUMS'])
   if sha(original)!=row['sha256sums_hash']:raise ValueError('ledger historical commit binding mismatch')
   evidence.append({'run_id':row['run_id'],'commit':commit,'sha256sums_hash':row['sha256sums_hash']})
  return {'status':'PASS','ledger_sha256':sha(path.read_bytes()),'rows':evidence}
 def g4(self):
  c=self.checkout;a2=c/'artifacts/cneh-exp-01-a2';receipt=read(a2/'g4-a2-epistemic.json')
  if sha((a2/'g4-a2-epistemic.json').read_bytes())!=G4_RECEIPT_SHA:raise ValueError('G4 receipt differs from independently pinned receipt')
  if receipt['status']!='PASS' or receipt['source_commit']!=SOURCE or len(receipt['checks'])!=25 or {x['id'] for x in receipt['checks']}!=G4_CHECK_IDS or any(x['status']!='PASS' for x in receipt['checks']):raise ValueError('G4 source receipt lacks exact 25 PASS checks')
  if receipt['scientific_promotion_authorized'] is not False or receipt['independent_external_replication'] is not False:raise ValueError('G4 authority overclaim')
  if sha((a2/'g4-a2-audit.py').read_bytes())!=receipt['audit_script_sha256']:raise ValueError('G4 audit script drift')
  for name,digest in receipt['execution_log_sha256'].items():
   if sha(safe(a2/'g4-execution',name).read_bytes())!=digest:raise ValueError('G4 log mismatch')
  checks={x['id']:x for x in receipt['checks']}
  for relative,digest in checks['source_bytes_match_commit']['evidence']['sha256'].items():
   if sha(safe(c,relative).read_bytes())!=digest:raise ValueError('G4 source binding drift')
  frozen={}
  for name in ('protocol.json','PREREGISTRATION.md','frozen_sources.lock','CNEH-04-DC_Formal_Specification.md'):
   rel='experiments/cneh_exp_01/'+name;old=self.command('original-'+name,['git','show',ORIGINAL+':'+rel])
   if old!=safe(c,rel).read_bytes():raise ValueError('frozen original changed')
   frozen[rel]=sha(old)
  preservation=[]
  for commit,prefix in ((ORIGINAL,'artifacts'),(A1,'artifacts/cneh-exp-01-a1'),(A2,'artifacts/cneh-exp-01-a2'),(A3_CONTRACT,'artifacts/cneh-exp-01-a2-ci')):
   old=self.tree(commit,prefix)
   if not old:raise ValueError('empty historical preservation source')
   if any(self.source_tree.get(p,{}).get('git_blob_sha1')!=v['git_blob_sha1'] for p,v in old.items()):raise ValueError('existing evidence changed')
   preservation.append({'commit':commit,'prefix':prefix,'preserved_blobs':len(old)})
  raw=self.command('science-still-blocked',[sys.executable,'-B','experiments/cneh_exp_01/qualification.py','--bundle','artifacts/cneh-exp-01-a1/primary','--require-scientific-readiness'],cwd=c,expected=2)
  science=json.loads(raw)
  if science['scientific_readiness']!='BLOCKED' or science['scientific_promotion_authorized'] is not False or science['same_lineage_supported_narrow_reachable'] is not False:raise ValueError('science boundary changed')
  cost=read(a2/'verification/metrology/report.json')
  if cost['resource_parity_verified'] is not False or cost['scientific_promotion_authorized'] is not False or set(cost['instruments'].values())!={'INSTRUMENT_INVALID'}:raise ValueError('cost authority changed')
  math=read(a2/'verification/math-qualification.json')
  if any(math[k] is not False for k in ('scientific_promotion_authorized','causal_attribution_qualified','neural_estimators_qualified','reference_direct_use_qualified')):raise ValueError('math authority changed')
  self.check_no_drift()
  return {'status':'PASS','source_bound_receipt_checks':25,'receipt_sha256':sha((a2/'g4-a2-epistemic.json').read_bytes()),'original_frozen_sha256':frozen,'historical_preservation':preservation,'scientific_promotion_authorized':False,'external_replication':'NOT_TESTED','physical_instruments':cost['instruments'],'same_lineage_supported_narrow_reachable':False}
 def evidence_bindings(self):
  roots={}
  names=['cneh-exp-01-a1','cneh-exp-01-a2-ci','cneh-exp-01-a2']
  names+=sorted(p.name for p in (self.checkout/'artifacts').glob('cneh-exp-01-a3*') if p.is_dir())
  for name in names:
   root=self.checkout/'artifacts'/name
   manifest=safe(root,'SHA256SUMS')
   roots['artifacts/'+name]={'manifest':'SHA256SUMS','sha256':sha(manifest.read_bytes())}
  excluded={'checkout','replay.git','remote-proof.git'}
  inventory={}
  for path in self.out.rglob('*'):
   relative=path.relative_to(self.out)
   if relative.parts[0] in excluded:continue
   if len(relative.parts)==1 and (relative.name=='executed-evidence-manifest.json' or relative.name.startswith('acceptance-') or relative.name.startswith('error-')):continue
   if path.is_symlink():raise ValueError('symlink in newly executed evidence')
   if path.is_file():inventory[relative.as_posix()]=sha(path.read_bytes())
  if not inventory:raise ValueError('empty executed evidence inventory')
  manifest=self.out/'executed-evidence-manifest.json'
  with manifest.open('xb') as stream:stream.write(canonical({'schema':'cneh-executed-evidence-v1','final_sha':self.args.final_sha,'replay_id':self.replay_id,'files_sha256':inventory}))
  binding={'historical_and_delivery_roots':roots,'generated_evidence_manifest_sha256':sha(manifest.read_bytes()),
           'ledger_sha256':sha(safe(self.checkout,LEDGER_PATH).read_bytes())}
  return binding
 def save(self,report):
  if sha(Path(__file__).read_bytes())!=self.auditor_sha256:raise ValueError('auditor source changed during execution')
  binding=self.evidence_bindings()
  report.update(timestamp_utc=now(),final_sha=self.args.final_sha,auditor_sha256=self.auditor_sha256,external_replication='NOT_TESTED',protocol='CNEH-LQP-43-v1.0',replay_id=self.replay_id,
   evidence_roots=binding['historical_and_delivery_roots'],evidence_root_sha256=sha(canonical(binding)),
   generated_evidence_manifest_sha256=binding['generated_evidence_manifest_sha256'],ledger_sha256=binding['ledger_sha256'],
   source_manifest_sha256=sha((self.out/'final-source-manifest.json').read_bytes()),required_checks_manifest_sha256=sha((self.checkout/CHECKS_PATH).read_bytes()),
   commands=self.records,independent_reviewer_attestation=None,independent_reviewer_scope='EXTERNAL_NOT_TESTED; internal review records are separately bound by delivery roots and final envelope',
   engineering_disposition='ENGINEERING_QUALIFIED' if report['ENGINEERING_QUALIFIED'] else 'BLOCKED')
  path=self.out/('acceptance-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
  with path.open('xb') as stream:stream.write(canonical(report))
  print(json.dumps({'receipt':str(path),'sha256':sha(path.read_bytes()),'ENGINEERING_QUALIFIED':report['ENGINEERING_QUALIFIED'],'gates':{k:v['status'] for k,v in report['gates'].items()}}))
  return 0 if report['ENGINEERING_QUALIFIED'] else 2
 def run(self):
  before_status=self.command('initial-status',['git','status','--porcelain=v1','--untracked-files=all'])
  self.command('initial-worktrees',['git','worktree','list','--porcelain'])
  if before_status:raise ValueError('initial live worktree is not clean')
  if self.git('rev-parse','HEAD')!=self.args.final_sha:raise ValueError('initial HEAD differs from final delivery SHA')
  self.verify_auditor_binding()
  self.active_gate='G3';g3=self.g3();self.gates['G3']=g3
  self.active_gate='G4';g4=self.g4();self.gates['G4']=g4
  self.active_gate='G1';g1=self.g1();self.gates['G1']=g1
  self.active_gate='G2';g2=self.g2();self.gates['G2']=g2
  # Repeat local+remote identity after reading CI to close the audit window.
  self.active_gate='G1';g1_after=self.g1()
  if {k:v for k,v in g1_after.items() if k!='l0_provenance'}!={k:v for k,v in g1.items() if k!='l0_provenance'}:g1={'status':'FAIL','reason':'Git/PR identity changed during audit','before':g1,'after':g1_after}
  else:g1['post_ci_l0_provenance']=g1_after['l0_provenance']
  gates={'G1':g1,'G2':g2,'G3':g3,'G4':g4}
  return self.save({'schema':'cneh-engineering-qualification-v1','gates':gates,'ENGINEERING_QUALIFIED':all(g['status']=='PASS' for g in gates.values()),'scientific_promotion_authorized':False,'qualification_scope':'engineering harness only; no external independent scientific replication'})

def main():
 os.umask(0o022)
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--final-sha',required=True);p.add_argument('--out',required=True);args=p.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',args.final_sha):p.error('explicit exact delivery SHA required')
 audit=None
 try:
  audit=Audit(args)
  return audit.run()
 except Exception as error:
  failure={'schema':'cneh-final-acceptance-error-v1','timestamp_utc':now(),'final_sha':args.final_sha,'ENGINEERING_QUALIFIED':False,'error_type':type(error).__name__,'error':str(error),'auditor_sha256':sha(Path(__file__).read_bytes())}
  failure.update(schema='cneh-engineering-qualification-v1',protocol='CNEH-LQP-43-v1.0',engineering_disposition='BLOCKED',scientific_promotion_authorized=False,external_replication='NOT_TESTED')
  if audit is not None:
   if audit.active_gate is not None:audit.gates[audit.active_gate]={'status':'FAIL','reason':str(error)}
   failure.update(gates=audit.gates,replay_id=audit.replay_id)
  else:failure['gates']={name:{'status':'UNKNOWN','reason':'output reservation failed'} for name in ('G1','G2','G3','G4')}
  if audit is not None:
   target=audit.out/('error-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
   with target.open('xb') as stream:stream.write(canonical(failure))
  print(json.dumps(failure));return 1
if __name__=='__main__':raise SystemExit(main())
