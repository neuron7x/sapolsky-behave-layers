"""Final G1/G2/G3/G4 auditor. Runs only with an explicitly supplied delivery SHA.

All outputs are outside the repository. Local replay is separate from published
CI and is never labeled external scientific replication. UNKNOWN cannot pass.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, math, os, re, subprocess, sys, tarfile
from pathlib import Path

SOURCE='f030a12b145bd8b43876c9e2d8b268e820e92b87'
ORIGINAL='4ccb02e7da16c4a65573e8e7c7e98a0b8456119b'
A1='a65ab49681bc748acb71cde9abe5bc99a4045ab3'
REPOSITORY='neuron7x/sapolsky-behave-layers'
BRANCH='research/cneh-exp-01'
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
 if failed or any(s['state'] in ('error','failure') for s in bad_statuses):state='FAIL'
 elif pending or bad_statuses:state='PENDING'
 elif missing or not checks:state='UNKNOWN'
 else:state='PASS'
 return {'status':state,'required_names':sorted(REQUIRED_CHECKS),'missing_required_names':missing,
         'observed_check_count':len(checks),'failed_checks':failed,'pending_checks':pending,
         'non_success_commit_statuses':bad_statuses,'all_observed_checks':checks,'commit_statuses':statuses}

class Audit:
 def __init__(self,args):
  self.args=args;self.repo=Path(args.repo).resolve();self.base=self.repo.parent
  self.out=Path(args.out).resolve();self.out.mkdir(parents=True,exist_ok=True)
  self.records=[];self.sequence=len(list(self.out.glob('command-*.json')))
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
  if p.returncode!=expected:raise RuntimeError(f'{label}: exit {p.returncode}, expected {expected}; see {stem}')
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
  status=self.command('local-porcelain',['git','status','--porcelain=v1','--untracked-files=all']).decode()
  head=self.git('rev-parse','HEAD');branch=self.git('branch','--show-current')
  remote_repo=self.api('canonical-repository','repos/'+REPOSITORY)
  if remote_repo['full_name'].lower()!=REPOSITORY.lower():raise ValueError('canonical owner changed')
  bare=self.out/'remote-proof.git'
  if not bare.exists():self.command('audit-bare-init',['git','init','--bare',bare],cwd=self.out)
  self.command('canonical-fetch',['git','-C',bare,'-c','credential.helper=','-c','credential.helper=!gh auth git-credential','fetch','--no-tags','--depth=1','https://github.com/'+REPOSITORY+'.git','refs/heads/'+BRANCH],cwd=self.out)
  fetched=self.command('fetched-head',['git','-C',bare,'rev-parse','FETCH_HEAD'],cwd=self.out).decode().strip()
  pr=self.api('pr-head','repos/'+REPOSITORY+'/pulls/43')
  remote_branch=self.api('remote-branch','repos/'+REPOSITORY+'/git/ref/heads/'+BRANCH)
  remote_tip=remote_branch['object']['sha'];pr_sha=pr['head']['sha']
  state='PASS' if not status and branch==BRANCH and head==fetched==remote_tip==pr_sha==self.args.final_sha else 'FAIL'
  unpublished=None
  if head==fetched:
   unpublished=int(self.command('unpublished-commits',['git','rev-list','--count',fetched+'..HEAD']).decode())
   if unpublished!=0:state='FAIL'
  return {'status':state,'actor':profile['login'],'local_status_porcelain':status,'local_branch':branch,'local_head':head,'fetched_canonical_head':fetched,'remote_api_head':remote_tip,'pr_head':pr_sha,'unpublished_commits_after_fetch':unpublished,'canonical_repository':REPOSITORY}
 def g2(self):
  checks=[];page=1;total=None
  while True:
   data=self.api('checks-'+str(page),f'repos/{REPOSITORY}/commits/{self.args.final_sha}/check-runs?filter=all&per_page=100&page={page}')
   if total is None:total=data['total_count']
   rows=data['check_runs'];checks.extend({k:c.get(k) for k in ('id','name','head_sha','status','conclusion','details_url','started_at','completed_at')} for c in rows)
   if len(checks)>=total:break
   if not rows:raise ValueError('incomplete check-run pagination')
   page+=1
  if len({c['id'] for c in checks})!=len(checks) or any(c['head_sha']!=self.args.final_sha for c in checks):raise ValueError('check-run identity mismatch')
  statuses=[];page=1
  while True:
   rows=self.api('statuses-'+str(page),f'repos/{REPOSITORY}/commits/{self.args.final_sha}/statuses?per_page=100&page={page}')
   statuses.extend({k:s.get(k) for k in ('id','context','state','target_url','updated_at')} for s in rows)
   if len(rows)<100:break
   page+=1
  return classify_ci(checks,statuses)
 def reconstruct(self):
  if self.checkout.exists():raise FileExistsError('fresh final archive required')
  archive=self.out/'final-source.tar'
  self.command('final-git-archive',['git','archive','--format=tar','--output='+str(archive),self.args.final_sha])
  embedded=self.command('archive-commit',['git','get-tar-commit-id'],input_bytes=archive.read_bytes()).decode().strip()
  if embedded!=self.args.final_sha:raise ValueError('archive commit mismatch')
  with tarfile.open(archive) as tf:
   if any(Path(m.name).is_absolute() or '..' in Path(m.name).parts or m.isdev() for m in tf.getmembers()):raise ValueError('unsafe archive')
   self.checkout.mkdir();tf.extractall(self.checkout,filter='data')
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
  actual={str(p.relative_to(self.checkout)) for p in self.checkout.rglob('*') if p.is_file() or p.is_symlink()}
  if actual!=set(self.source_tree):raise ValueError('final archive member drift')
  for relative,entry in self.source_tree.items():
   p=self.checkout/relative;data=p.readlink().as_posix().encode() if entry['mode']=='120000' else p.read_bytes()
   if sha(data)!=entry['sha256']:raise ValueError('final archive source drift '+relative)
 def manifests(self):
  receipts=[]
  roots=[self.checkout/'artifacts/cneh-exp-01-a1',self.checkout/'artifacts/cneh-exp-01-a2']
  for root in roots:
   if not root.is_dir():raise ValueError('missing delivery evidence root')
   for manifest in sorted(root.rglob('SHA256SUMS')):
    rows={}
    for line in manifest.read_text().splitlines():
     if not re.fullmatch(r'[0-9a-f]{64}  .+',line):raise ValueError('invalid manifest record')
     digest,relative=line.split('  ',1)
     if relative in rows:raise ValueError('duplicate manifest member')
     p=safe(manifest.parent,relative)
     if sha(p.read_bytes())!=digest:raise ValueError('manifest mismatch '+str(p))
     rows[relative]=digest
    actual={str(p.relative_to(manifest.parent)) for p in manifest.parent.rglob('*') if p.is_file() and p!=manifest}
    if not rows or set(rows)!=actual:raise ValueError('manifest roster mismatch '+str(manifest))
    receipts.append({'path':str(manifest.relative_to(self.checkout)),'sha256':sha(manifest.read_bytes()),'members':len(rows)})
  return receipts
 def g3(self):
  reconstruction=self.reconstruct();base=self.tree(SOURCE)
  def reused_scope(p):
   return p.startswith(('experiments/cneh_exp_01/','tests/cneh_math/','cwc/causal/')) or re.fullmatch(r'tests/test_cneh_exp_01.*\.py',p) or p in ('cwc/__init__.py','pyproject.toml','uv.lock','cwc-requirements-dev.txt')
  relevant={p for p in base if reused_scope(p)}
  if relevant!={p for p in self.source_tree if reused_scope(p)}:raise ValueError('tested implementation/lock/test roster changed')
  if any(self.source_tree[p]['git_blob_sha1']!=base[p]['git_blob_sha1'] or self.source_tree[p]['mode']!=base[p]['mode'] for p in relevant):raise ValueError('tested implementation/lock/test bytes changed')
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
  commands=[('primary-replay',[sys.executable,'-B','experiments/cneh_exp_01/run.py','--out','artifacts/cneh-exp-01-a1/primary','--verify'],0),
   ('math45-replay',[self.python,'-B','experiments/cneh_exp_01/math_qualification.py','--reference',self.reference,'--out','artifacts/cneh-exp-01-a2/verification/math-qualification.json','--verify'],0),
   ('neural-actual-replay',[self.python,'-B','experiments/cneh_exp_01/bnsyn_adapter.py','--source',self.base/'inputs/bnsyn','--out','artifacts/cneh-exp-01-a1/bnsyn','--verify'],0),
   ('metrology-semantic-replay',[sys.executable,'-B','experiments/cneh_exp_01/metrology.py','--out','artifacts/cneh-exp-01-a2/verification/metrology','--verify'],0),
   ('physical-cost-remains-blocked',[sys.executable,'-B','experiments/cneh_exp_01/metrology.py','--out','artifacts/cneh-exp-01-a2/verification/metrology','--verify','--require-qualified-cost'],2)]
  for label,args,expected in commands:self.command(label,args,cwd=self.checkout,expected=expected)
  math=read(a2/'verification/math-qualification.json')
  if len(math['checks'])!=45 or not all(v['pass'] is True for v in math['checks'].values()):raise ValueError('math fixture count or status mismatch')
  self.check_no_drift()
  return {'status':'PASS','final_archive_sha256':reconstruction['archive_sha256'],'final_archive_files':reconstruction['file_count'],'reused_source_commit':SOURCE,'unchanged_implementation_lock_test_files':len(relevant),'executed_final_sha_replay':True,'source_unchanged_after_replay':True,'nested_manifests':manifests,'evidence_map_rows':len(rows),'reused_independent_report_sha256':A2_REPORT_SHA}
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
  for commit,prefix in ((ORIGINAL,'artifacts'),(A1,'artifacts/cneh-exp-01-a1')):
   old=self.tree(commit,prefix)
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
 def save(self,report):
  report.update(timestamp_utc=now(),final_sha=self.args.final_sha,auditor_sha256=sha(Path(__file__).read_bytes()),external_replication='NOT_TESTED')
  path=self.out/('acceptance-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
  path.write_bytes(canonical(report))
  print(json.dumps({'receipt':str(path),'sha256':sha(path.read_bytes()),'ENGINEERING_QUALIFIED':report['ENGINEERING_QUALIFIED'],'gates':{k:v['status'] for k,v in report['gates'].items()}}))
  return 0 if report['ENGINEERING_QUALIFIED'] else 2
 def run(self):
  before_status=self.command('initial-status',['git','status','--porcelain=v1','--untracked-files=all'])
  self.command('initial-worktrees',['git','worktree','list','--porcelain'])
  if before_status:raise ValueError('initial live worktree is not clean')
  if self.git('rev-parse','HEAD')!=self.args.final_sha:raise ValueError('initial HEAD differs from final delivery SHA')
  local=self.out/'local-replay-receipt.json'
  if self.args.refresh:
   saved=read(local)
   if saved['final_sha']!=self.args.final_sha:raise ValueError('refresh SHA mismatch')
   proof=read(self.out/'final-source-manifest.json');self.source_tree=proof['files'];self.check_no_drift()
   if saved['auditor_sha256']!=sha(Path(__file__).read_bytes()):raise ValueError('auditor changed since local replay')
   g3,g4=saved['G3'],saved['G4']
  else:
   g3=self.g3();g4=self.g4()
   local.write_bytes(canonical({'final_sha':self.args.final_sha,'auditor_sha256':sha(Path(__file__).read_bytes()),'G3':g3,'G4':g4,'timestamp_utc':now()}))
  g1=self.g1();g2=self.g2()
  # Repeat local+remote identity after reading CI to close the audit window.
  g1_after=self.g1()
  if g1_after!=g1:g1={'status':'FAIL','reason':'Git/PR identity changed during audit','before':g1,'after':g1_after}
  gates={'G1':g1,'G2':g2,'G3':g3,'G4':g4}
  return self.save({'schema':'cneh-final-acceptance-v1','gates':gates,'ENGINEERING_QUALIFIED':all(g['status']=='PASS' for g in gates.values()),'scientific_promotion_authorized':False,'qualification_scope':'engineering harness only; no external independent scientific replication'})

def main():
 os.umask(0o022)
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--final-sha',required=True);p.add_argument('--out',required=True);p.add_argument('--refresh',action='store_true');args=p.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',args.final_sha):p.error('explicit exact delivery SHA required')
 audit=Audit(args)
 try:return audit.run()
 except Exception as error:
  failure={'schema':'cneh-final-acceptance-error-v1','timestamp_utc':now(),'final_sha':args.final_sha,'ENGINEERING_QUALIFIED':False,'error_type':type(error).__name__,'error':str(error),'auditor_sha256':sha(Path(__file__).read_bytes())}
  target=audit.out/('error-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json');target.write_bytes(canonical(failure));print(json.dumps(failure));return 1
if __name__=='__main__':raise SystemExit(main())
