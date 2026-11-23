"""Independent LQP43 provenance/CI-artifact collector; never an admission oracle.

Run only on an explicitly supplied final delivery SHA. Outputs must be new and
outside the repository. Authentication values and signed download URLs are never
recorded. All participants are internal same-session agents.
"""
from __future__ import annotations
import argparse, base64, csv, datetime, hashlib, io, json, math, os
import platform, re, shutil, stat, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath

REPO = 'neuron7x/sapolsky-behave-layers'
BRANCH = 'research/cneh-exp-01'
CNEH = 'experiments/cneh_exp_01/'
ORIGINAL = '4ccb02e7da16c4a65573e8e7c7e98a0b8456119b'
FROZEN = {'protocol.json','PREREGISTRATION.md','frozen_sources.lock','CNEH-04-DC_Formal_Specification.md'}
LEDGER = 'docs/lab/EXPERIMENT_LEDGER.jsonl'
EXPECTED_ARTIFACTS = {
 f'cneh-exp-01-{kind}-{py}'
 for kind in ('internal-primary-SHA256','synthetic-smoke','engineering-qualification','metrology')
 for py in ('3.11','3.12')
} | {'cneh-exp-01-pinned-neural-integration'}

def sha(data): return hashlib.sha256(data).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def strict_json(data):
 def pairs(items):
  result={}
  for key,value in items:
   if key in result: raise ValueError('duplicate JSON key')
   result[key]=value
  return result
 def bad(value): raise ValueError('nonfinite JSON value')
 def finite(value):
  value=float(value)
  if not math.isfinite(value): raise ValueError('nonfinite JSON value')
  return value
 return json.loads(data,object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)

def actor_scope_headers(raw):
 text=raw.decode().replace('\r\n','\n');headers,separator,body=text.partition('\n\n')
 if not separator: raise ValueError('missing API response header/body boundary')
 actor=strict_json(body).get('login')
 scopes=None
 for line in headers.splitlines():
  key,sep,value=line.partition(':')
  if sep and key.lower()=='x-oauth-scopes':
   scopes=sorted(v.strip() for v in value.split(',') if v.strip())
   if any(not re.fullmatch(r'[A-Za-z0-9_:.-]+',v) for v in scopes): raise ValueError('unexpected scope-name syntax')
 return {'actor':actor,'oauth_scope_names':scopes,'scope_metadata':'OBSERVED' if scopes is not None else 'UNKNOWN',
         'credential_values_collected':False}

def safe_relative(name):
 if not isinstance(name,str): raise ValueError('artifact path must be text')
 p=PurePosixPath(name)
 if (not name or not p.parts or p.is_absolute() or '..' in p.parts or '\\' in name
     or any(ord(c)<32 or ord(c)==127 for c in name) or ':' in name
     or str(p)!=name.rstrip('/')):
  raise ValueError('unsafe/noncanonical artifact path')
 return p

def canonical_remote(raw):
 value=raw.decode().strip()
 if value not in ('https://github.com/'+REPO+'.git','https://github.com/'+REPO,
                  'git@github.com:'+REPO+'.git'):
  raise ValueError('remote is not the allowed credential-free canonical repository')
 return {'url':value}

def reject_symlinks(path):
 for candidate in (path,*path.parents):
  if candidate.is_symlink(): raise ValueError('symlinked output/input path forbidden')

def extract_zip(blob,destination):
 """Validate the complete ZIP directory before bounded extraction; never execute it."""
 reject_symlinks(destination)
 if len(blob)>512*1024**2: raise ValueError('compressed ZIP size bound exceeded')
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  entries=z.infolist();names={};total=0
  if len(entries)>100000: raise ValueError('ZIP entry-count bound exceeded')
  for entry in entries:
   name=entry.filename.rstrip('/');safe_relative(entry.filename)
   if name in names: raise ValueError('duplicate ZIP member')
   mode=entry.external_attr >> 16;kind=stat.S_IFMT(mode)
   if kind not in (0,stat.S_IFREG,stat.S_IFDIR): raise ValueError('nonregular ZIP member')
   if kind==stat.S_IFDIR and not entry.is_dir(): raise ValueError('ZIP directory flag mismatch')
   names[name]=entry.is_dir()
   total+=entry.file_size
   if total>1024**3 or entry.file_size>512*1024**2: raise ValueError('ZIP size bound exceeded')
  for name in names:
   if any(str(parent) in names and not names[str(parent)] for parent in PurePosixPath(name).parents):
    raise ValueError('ZIP file/directory path conflict')
  destination.mkdir(exist_ok=False)
  for entry in entries:
   target=destination/entry.filename
   if entry.is_dir(): target.mkdir(parents=True,exist_ok=True)
   else:
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out: out.write(z.read(entry))
 return {'members':len(names),'uncompressed_bytes':total}

def manifests(root):
 reject_symlinks(root)
 paths=sorted(root.rglob('*'))
 if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in paths):
  raise ValueError('symlink or nonregular artifact member')
 receipts=[];covered=set()
 files={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in paths if p.is_file()}
 for manifest in sorted(p for p in root.rglob('*') if p.name in ('SHA256SUMS','VERIFIER_SHA256SUMS')):
  if not manifest.is_file() or manifest.is_symlink(): raise ValueError('manifest not regular')
  members={}
  for line in manifest.read_text().splitlines():
   match=re.fullmatch(r'([0-9a-f]{64}) [ *](.+)',line)
   if not match: raise ValueError('malformed SHA256 manifest')
   digest,name=match.groups();safe_relative(name)
   if name in members: raise ValueError('duplicate manifest member')
   path=manifest.parent/name
   if not path.is_file() or path.is_symlink() or sha(path.read_bytes())!=digest: raise ValueError('manifest member mismatch')
   members[name]=digest;covered.add(path.relative_to(root).as_posix())
  if not members: raise ValueError('empty claimed manifest')
  covered.add(manifest.relative_to(root).as_posix())
  actual={p.relative_to(manifest.parent).as_posix() for p in manifest.parent.rglob('*') if p.is_file() and p!=manifest}
  receipts.append({'path':manifest.relative_to(root).as_posix(),'sha256':sha(manifest.read_bytes()),
                   'listed_members':len(members),'all_listed_members_verified':True,
                   'roster_exact_within_manifest_directory':set(members)==actual,
                   'unlisted_in_manifest_directory':sorted(actual-set(members))})
 if not receipts: raise ValueError('artifact has no claimed checksum manifest')
 return {'manifests':receipts,'all_file_sha256':files,
         'archive_files_outside_manifests':[{'path':p,'sha256':files[p],
          'classification':'Not covered by an inner manifest; archive/API trust boundary recorded separately'} for p in sorted(set(files)-covered)]}


def verify_installed_records(packages):
 """Check installed bytes against distribution RECORD; this is not a signature."""
 import importlib.metadata as metadata
 prefix=Path(sys.prefix).resolve();verified={};unhashed=[];reports=[]
 expected={re.sub(r"[-_.]+","-",row["name"]).lower():row["version"] for row in packages}
 if len(expected)!=len(packages): raise ValueError('duplicate expected runtime package')
 for name,version in sorted(expected.items()):
  distribution=metadata.distribution(name)
  if distribution.version!=version: raise ValueError('installed dependency version mismatch')
  record=distribution.read_text('RECORD')
  if record is None: raise ValueError('installed dependency lacks RECORD')
  count=0;names=set()
  for row in csv.reader(io.StringIO(record)):
   if len(row)!=3 or not row[0] or row[0] in names: raise ValueError('invalid installed RECORD row')
   names.add(row[0]);relative=Path(row[0])
   if relative.is_absolute() or '\\' in row[0]: raise ValueError('unsafe installed RECORD path')
   path=Path(distribution.locate_file(row[0]))
   reject_symlinks(path)
   path=path.resolve()
   if not path.is_relative_to(prefix) or not path.is_file(): raise ValueError('installed RECORD path escapes environment or is absent')
   data=path.read_bytes();observed=sha(data);relative_name=path.relative_to(prefix).as_posix()
   if row[1]:
    algorithm,separator,encoded=row[1].partition('=')
    expected_encoding=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
    if algorithm!='sha256' or not separator or encoded!=expected_encoding or row[2]!=str(len(data)):
     raise ValueError('installed RECORD byte/hash/size mismatch')
    count+=1;verified[relative_name]=observed
   else:
    is_record=relative.name=='RECORD' and relative.parent.name.endswith('.dist-info')
    if row[2] or (relative.suffix!='.pyc' and not is_record): raise ValueError('unexpected unhashed installed RECORD member')
    unhashed.append({'path':relative_name,'sha256':observed,
                     'scope':'observed only; RECORD does not authenticate its own bytes or generated bytecode'})
  if count==0: raise ValueError('empty installed RECORD verification')
  reports.append({'name':name,'version':version,'hashed_files_verified':count,'record_sha256':sha(record.encode())})
 return {'status':'PASS','packages':reports,'hashed_files_verified':sum(r['hashed_files_verified'] for r in reports),
         'verified_file_sha256':verified,'unhashed_installer_outputs':unhashed,
         'authority':'CONSISTENCY_WITH_INSTALLED_DISTRIBUTION_RECORD_ONLY',
         'trust_boundary':'Wheel origins are separately bound by the committed hash lock and installation receipt; RECORD is not an authenticated signature.'}

def workflow_provenance(data):
 lines=data.decode().splitlines();permissions=[];actions=[];installs=[];gaps=[]
 for i,line in enumerate(lines):
  if re.match(r'^\s*permissions:',line):
   indent=len(line)-len(line.lstrip());block=[line]
   for following in lines[i+1:]:
    if following.strip() and len(following)-len(following.lstrip())<=indent: break
    block.append(following)
   permissions.append({'line':i+1,'literal_yaml':'\n'.join(block)})
  match=re.search(r'uses:\s*([^\s#]+)',line)
  if match:
   ref=match.group(1);actions.append({'line':i+1,'reference':ref,'commit_pinned':bool(re.search(r'@[0-9a-f]{40}$',ref))})
  if re.search(r'pipx? install|pip install|uv sync|uv pip install|curl ',line):
   installs.append({'line':i+1,'command':line.strip()})
  if re.search(r'pip install --upgrade pip(?:\s|$)',line):
   gaps.append({'line':i+1,'kind':'UNVERIFIED_EXECUTABLE_VERSION','detail':'pip upgrade has neither exact version nor required artifact hash'})
  if re.search(r'(?:uv )?pip install -r cwc-requirements-dev.txt',line) and '--require-hashes' not in line:
   gaps.append({'line':i+1,'kind':'VERSION_PINNED_NOT_HASH_AUTHENTICATED','detail':'direct devtool pins do not authenticate wheel bytes or freeze every transitive dependency'})
  if 'pipx install uv==' in line:
   gaps.append({'line':i+1,'kind':'VERSION_PINNED_NOT_HASH_AUTHENTICATED','detail':'uv bootstrap version pinned, wheel digest not independently required'})
 return {'sha256':sha(data),'permission_declarations':permissions,'actions':actions,'install_commands':installs,'supply_chain_limits':gaps}

class Collector:
 def __init__(self,args):
  self.args=args;self.repo=Path(args.repo).resolve();self.base=self.repo.parent
  self.inputs=Path(getattr(args,'inputs',None) or self.base/'inputs').absolute()
  self.out=Path(args.out).absolute()
  reject_symlinks(self.out)
  if self.repo==self.out or self.repo in self.out.resolve().parents: raise ValueError('output must be outside repository')
  self.out.mkdir(parents=True,exist_ok=False);self.sequence=0;self.records=[]
  self.implementation_sha256=sha(Path(__file__).read_bytes())
 def command(self,label,argv,cwd=None,allow_failure=False,binary=False,sanitize=None,timeout=180):
  self.sequence+=1;stem=f'command-{self.sequence:03d}-{label}';start=utc()
  env=dict(os.environ);env.pop('GH_DEBUG',None);env['PYTHONDONTWRITEBYTECODE']='1';env['GIT_TERMINAL_PROMPT']='0'
  run=subprocess.run([str(x) for x in argv],cwd=cwd or self.repo,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
  stdout=run.stdout
  stored=canonical(sanitize(stdout)) if sanitize and run.returncode==0 else stdout
  if sanitize and run.returncode!=0: stored=b''
  # GitHub response headers may contain redirect URLs. Only sanitizer output is retained.
  (self.out/(stem+('.bin' if binary else '.stdout'))).write_bytes(stored)
  stderr=run.stderr if not sanitize else b''
  (self.out/(stem+'.stderr')).write_bytes(stderr)
  receipt={'argv':[str(x) for x in argv],'cwd':str(cwd or self.repo),'start_utc':start,'end_utc':utc(),
           'exit_code':run.returncode,'stdout_recorded_sha256':sha(stored),'stderr_recorded_sha256':sha(stderr),
           'response_sanitized':sanitize is not None}
  (self.out/(stem+'.json')).write_bytes(canonical(receipt));self.records.append(receipt)
  if run.returncode and not allow_failure: raise RuntimeError(label+' failed: '+str(run.returncode))
  return run.returncode,stdout
 def git(self,*args): return self.command('git-'+args[0],['git',*args])[1]
 def api(self,label,path,allow_failure=False):
  rc,data=self.command(label,['gh','api','-H','X-GitHub-Api-Version: 2022-11-28',path],allow_failure=allow_failure)
  return {'available':False,'exit_code':rc,'status':'UNKNOWN'} if rc else strict_json(data)
 def start(self):
  _,remote=self.command('canonical-remote',['git','remote','get-url','origin'],sanitize=canonical_remote)
  self.remote=canonical_remote(remote)
  if Path(self.git('rev-parse','--show-toplevel').decode().strip()).resolve()!=self.repo:
   raise ValueError('repository path is not the Git checkout root')
  status=self.git('status','--porcelain=v1','--untracked-files=all');worktrees=self.git('worktree','list','--porcelain')
  head=self.git('rev-parse','HEAD').decode().strip()
  if status or head!=self.args.final_sha: raise ValueError('final source is dirty or HEAD differs')
  self.initial_worktrees=worktrees.decode()
  _,raw=self.command('actor-scope-names',['gh','api','--include','user'],sanitize=actor_scope_headers)
  self.actor=actor_scope_headers(raw)
  if self.actor['actor']!='neuron7x': raise ValueError('wrong authenticated actor')
 def finish(self,report,name):
  if sha(Path(__file__).read_bytes())!=self.implementation_sha256: raise ValueError('collector implementation changed during execution')
  if self.git('rev-parse','HEAD').decode().strip()!=self.args.final_sha or self.git('status','--porcelain=v1','--untracked-files=all'):
   raise ValueError('final source changed during collection')
  report.update(final_sha=self.args.final_sha,timestamp_utc=utc(),collector_sha256=self.implementation_sha256,
                source_unchanged=True,qualification_decision='NOT_PERFORMED',external_replication='NOT_TESTED')
  target=self.out/name;target.write_bytes(canonical(report))
  rows={p.relative_to(self.out).as_posix():sha(p.read_bytes()) for p in self.out.rglob('*') if p.is_file() and p!=self.out/'SHA256SUMS'}
  (self.out/'SHA256SUMS').write_text(''.join(f'{digest}  {p}\n' for p,digest in sorted(rows.items())))
  print(json.dumps({'receipt':str(target),'sha256':sha(target.read_bytes()),'qualification_decision':'NOT_PERFORMED'}))
 def tree(self):
  result={}
  for row in self.git('ls-tree','-r','-z',self.args.final_sha).split(b'\0'):
   if not row: continue
   meta,path=row.split(b'\t',1);mode,kind,blob=meta.decode().split()
   if kind!='blob': raise ValueError('unexpected nonblob source')
   result[path.decode()]={'mode':mode,'git_blob_sha1':blob}
  return result
 def l0(self):
  self.start();tree=self.tree();checkpath=CNEH+'required_checks_manifest.json'
  required=strict_json(self.git('show',self.args.final_sha+':'+checkpath))
  workflows=set(required['workflow_sources_sha256'])
  special={LEDGER,'Makefile.cwc','pyproject.toml','uv.lock','cwc-requirements-dev.txt','ruff.toml','mypy.ini',
           'scripts/build_experiment_ledger.py','scripts/verify_evidence.py','scripts/secret_scan_container.sh','scripts/cwc_dependency_audit.py','.gitleaksignore','.gitleaks.toml'}
  selected={p for p in tree if p.startswith((CNEH,'tests/cneh_math/','cwc/causal/','requirements/')) or re.fullmatch(r'tests/test_cneh.*\.py',p) or p in workflows|special}
  if CNEH+'acceptance.py' not in selected: raise ValueError('final acceptance entrypoint absent')
  additions={};commit=None
  for line in self.git('log','--reverse','--diff-filter=A','--format=@commit:%H','--name-only',self.args.final_sha,'--',*sorted(selected)).decode().splitlines():
   if line.startswith('@commit:'): commit=line[8:]
   elif line in selected: additions.setdefault(line,commit)
  inventory={};evidence={};all_hashes={}
  for name,entry in tree.items():
   path=self.repo/name;data=path.readlink().as_posix().encode() if entry['mode']=='120000' else path.read_bytes()
   if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=entry['git_blob_sha1']: raise ValueError('Git/disk byte mismatch '+name)
   all_hashes[name]=sha(data)
   if name.startswith('artifacts/'): evidence[name]=all_hashes[name]
   if name not in selected: continue
   roles=[];short=name.removeprefix(CNEH)
   if short in FROZEN: roles.append('FROZEN_SCIENTIFIC_PROTOCOL')
   if any(x in name for x in ('metrology','hardware')): roles.append('P4_RESOURCE_METROLOGY')
   if any(x in name for x in ('math_qualification','math_mutation','cneh_math','estimators','cwc/causal/')): roles.append('P2_MATHEMATICAL_QUALIFICATION')
   if name in workflows: roles.append('CI_WORKFLOW')
   if name==LEDGER: roles.append('HISTORICAL_EVIDENCE_LEDGER')
   if 'acceptance' in name.lower() or short=='required_checks_manifest.json': roles.append('ADMISSION_BOUNDARY')
   if name.endswith('.md'): roles.append('CONTRACT_OR_GUIDE')
   if name.startswith('tests/'): roles.append('TEST')
   if not roles: roles=['SOURCE_OR_DEPENDENCY_LOCK']
   if not additions.get(name): raise ValueError('missing path introduction commit '+name)
   inventory[name]={**entry,'sha256':all_hashes[name],'introduction_commit':additions[name],
                    'introduction_semantics':'first addition of this exact path in reachable history; not author identity',
                    'roles':roles,'verification_result':'GIT_BLOB_AND_WORKING_BYTES_MATCH'}
  source={'schema':'cneh-l0-source-inventory-v1','final_sha':self.args.final_sha,'files':inventory,
          'all_tracked_files':len(tree),'all_tracked_tree_sha256':sha(canonical(tree)),'all_tracked_file_sha256':all_hashes}
  (self.out/'source-manifest.json').write_bytes(canonical(source))
  (self.out/'evidence-root-manifest.json').write_bytes(canonical(evidence))
  ignored=self.git('ls-files','--others','--ignored','--exclude-standard','-z','--',CNEH,'tests','cwc','.github','docs').decode().split('\0')
  external=self.external_inputs()
  wf={p:workflow_provenance((self.repo/p).read_bytes()) for p in sorted(workflows)}
  for path,expected in required['workflow_sources_sha256'].items():
   if wf[path]['sha256']!=expected: raise ValueError('required-check workflow hash mismatch')
  _,version=self.command('python-version',[sys.executable,'--version'])
  versions={'python':version.decode().strip()}
  for name in ('git','gh','uv'):
   executable=shutil.which(name)
   if executable:
    rc,value=self.command(name+'-version',[executable,'--version'],allow_failure=True)
    versions[name]={'exit_code':rc,'observed':value.decode().strip()}
   else: versions[name]={'status':'NOT_INSTALLED'}
  permissions={}
  for label,endpoint in [('repository',''),('actions','/actions/permissions'),('default_workflow','/actions/permissions/workflow')]:
   value=self.api('permissions-'+label,'repos/'+REPO+endpoint,allow_failure=True)
   permissions[label]=value.get('permissions',{}) if label=='repository' and 'full_name' in value else value
  report={'schema':'cneh-l0-provenance-v1','protocol':'CNEH-LQP-43-v1.0','inventory_integrity':'PASS',
   'actor':self.actor,'canonical_remote':self.remote,'worktrees':self.initial_worktrees,
   'scoped_file_count':len(inventory),'source_manifest_sha256':sha((self.out/'source-manifest.json').read_bytes()),
   'evidence_root_sha256':sha(canonical(evidence)),'ledger_sha256':all_hashes[LEDGER],
   'required_checks_manifest_sha256':all_hashes[checkpath],'ignored_important_pathnames':sorted(p for p in ignored if p),
   'ignored_environment_directory_names':[name for name in ('.venv','.cneh-inputs') if (self.repo/name).exists()],
   'external_inputs':external,'environment':{'system':platform.system(),'release':platform.release(),'architecture':platform.machine(),'python_implementation':platform.python_implementation(),'versions':versions},
   'github_permission_metadata':permissions,'workflow_provenance':wf,
   'participants':{'implementer':'/root/harden_runner','verifier':'/root/independent_verification','reviewer':'/root/adversarial_review','integrator':'/root',
                   'identity_basis':'internal agent roles declared in this session; not external authenticated laboratory identities','all_internal_same_session':True},
   'supply_chain_scope':'CNEH seven runtime wheels and any separately declared CI hash locks are explicit scopes. Runner image and Python/pip bootstrap remain distinct trusted-platform boundaries; see per-workflow commands, pinned actions and recorded limits.'}
  self.finish(report,'provenance.json')
 def external_inputs(self):
  contract=strict_json((self.repo/(CNEH+'bnsyn_integration_contract.json')).read_bytes())
  source=self.inputs/'bnsyn';paths=[source/'LICENSE',source/'pyproject.toml']+sorted((source/'src').rglob('*'))
  reject_symlinks(source)
  if any(p.is_symlink() for p in paths): raise ValueError('external BN source symlink')
  files={p.relative_to(source).as_posix():sha(p.read_bytes()) for p in paths if p.is_file()}
  if len(files)!=contract['source']['file_count'] or sha(canonical(files))!=contract['source']['files_sha256']: raise ValueError('external BN source mismatch')
  (self.out/'bnsyn-source-manifest.json').write_bytes(canonical(files))
  mathc=strict_json((self.repo/(CNEH+'math_qualification_contract.json')).read_bytes())['pr44']
  reference=self.inputs/'pr44-linear-reference.py'
  if reference.is_symlink() or sha(reference.read_bytes())!=mathc['sha256']: raise ValueError('PR44 reference mismatch')
  python=self.inputs/'bnsyn-locked-venv/bin/python'
  _,freeze=self.command('locked-pip-freeze',[python,'-B','-m','pip','freeze','--all'])
  _,v=self.command('locked-python-version',[python,'--version'])
  lock=(self.repo/(CNEH+'bnsyn-requirements.lock')).read_bytes()
  report=self.repo/'artifacts/cneh-exp-01-a1/dependency-install-report.json';installation=strict_json(report.read_bytes())
  allowed=set(re.findall(rb'--hash=sha256:([0-9a-f]{64})',lock));installed=[]
  for package in installation['install']:
   digest=package['download_info']['archive_info']['hashes']['sha256']
   if digest.encode() not in allowed: raise ValueError('wheel install receipt not covered by lock')
   installed.append({'name':package['metadata']['name'],'version':package['metadata']['version'],'wheel_sha256':digest})
  if len(installed)!=7: raise ValueError('expected seven CNEH locked runtime wheels')
  script="import importlib.util,json,sys; s=importlib.util.spec_from_file_location('cneh_record_verifier',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.canonical(m.verify_installed_records(json.loads(sys.argv[2]))).decode(),end='')"
  _,record_data=self.command('installed-record-bytes',[python,'-B','-c',script,Path(__file__).resolve(),json.dumps(installed,sort_keys=True)])
  record_report=strict_json(record_data)
  if record_report['status']!='PASS' or len(record_report['packages'])!=7: raise ValueError('installed RECORD verification incomplete')
  (self.out/'installed-record-manifest.json').write_bytes(canonical(record_report))
  return {'bnsyn':{'contract':contract['source'],'verified_files':len(files),'manifest_sha256':sha(canonical(files))},
          'pr44':{**mathc,'verification_result':'PINNED_CONTRACT_SHA256_MATCH'},
          'locked_environment':{'python':v.decode().strip(),'pip_freeze_all':freeze.decode().splitlines(),
           'lock_sha256':sha(lock),'installation_receipt_sha256':sha(report.read_bytes()),'wheel_receipts':installed,
           'installed_record_manifest_sha256':sha(canonical(record_report)),
           'installed_record_hashed_files_verified':record_report['hashed_files_verified'],
           'installed_record_authority':record_report['authority'],
           'unhashed_installer_outputs':len(record_report['unhashed_installer_outputs']),
           'scope':'Committed installation receipt wheel hashes checked against committed lock; hashed installed RECORD entries checked byte-for-byte; generated bytecode/RECORD itself are observed but unauthenticated by RECORD. Pip/bootstrap is outside the seven-wheel scope.'}}
 def paginated(self,label,endpoint,key):
  rows=[];page=1;total=None
  while True:
   if page>1000: raise ValueError('API pagination bound exceeded')
   separator='&' if '?' in endpoint else '?'
   obj=self.api(label+'-'+str(page),endpoint+separator+f'per_page=100&page={page}')
   count=obj.get('total_count');part=obj.get(key)
   if type(count) is not int or count<0 or not isinstance(part,list): raise ValueError('invalid API pagination shape')
   if total is None: total=count
   if count!=total: raise ValueError('API pagination total changed during collection')
   rows.extend(part)
   if len(rows)>total: raise ValueError('API pagination exceeds declared total')
   if len(rows)==total: break
   if not part: raise ValueError('incomplete API pagination')
   page+=1
  ids=[row.get('id') for row in rows]
  if any(type(value) is not int or value<0 for value in ids) or len(set(ids))!=len(ids):
   raise ValueError('duplicate or invalid API IDs')
  return rows
 def ci_artifacts(self):
  self.start()
  runs=self.paginated('workflow-runs',f'repos/{REPO}/actions/runs?head_sha={self.args.final_sha}','workflow_runs')
  relevant=[r for r in runs if r['path']=='.github/workflows/cneh-exp-01.yml' and r['event']=='pull_request']
  if not relevant: raise ValueError('no exact-SHA CNEH pull-request workflow run')
  receipts=[];found=set()
  for run in relevant:
   if run['head_sha']!=self.args.final_sha or run['status']!='completed' or run['conclusion']!='success': raise ValueError('CNEH run not exact-final completed success')
   artifacts=self.paginated('artifacts-'+str(run['id']),f'repos/{REPO}/actions/runs/{run["id"]}/artifacts','artifacts')
   roster=[a.get('name') for a in artifacts]
   if len(roster)!=len(set(roster)) or set(roster)!=EXPECTED_ARTIFACTS:
    raise ValueError('missing or duplicate CNEH artifact roster for run '+str(run['id']))
   for artifact in artifacts:
    workflow=artifact.get('workflow_run',{})
    if workflow.get('head_sha')!=self.args.final_sha or workflow.get('id')!=run['id'] or workflow.get('head_branch')!=BRANCH or artifact['expired'] is not False:
     raise ValueError('artifact source identity/expiry mismatch')
    name=artifact['name']
    if name not in EXPECTED_ARTIFACTS: raise ValueError('unclassified CNEH workflow artifact '+name)
    found.add(name)
    if type(artifact.get('size_in_bytes')) is not int or not 0<artifact['size_in_bytes']<=512*1024**2:
     raise ValueError('artifact compressed size invalid')
    _,blob=self.command('artifact-zip-'+str(artifact['id']),['gh','api','--allow-escape-sequences',f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'],binary=True,timeout=180)
    digest=artifact.get('digest');measured=sha(blob)
    if digest is not None and (not isinstance(digest,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',digest)):
     raise ValueError('invalid GitHub artifact digest')
    if digest is not None and digest!='sha256:'+measured: raise ValueError('GitHub artifact digest mismatch')
    extraction=self.out/('artifact-'+str(artifact['id']));stats=extract_zip(blob,extraction);integrity=manifests(extraction)
    receipts.append({'artifact_id':artifact['id'],'name':name,'run_id':run['id'],'run_attempt':run['run_attempt'],'workflow_path':run['path'],'event':run['event'],
                     'head_sha':run['head_sha'],'run_url':run['html_url'],'remote_digest':digest,'archive_sha256':measured,
                     'remote_digest_verification':'PASS' if digest else 'UNKNOWN_NOT_PROVIDED',**stats,**integrity,
                     'semantic_replay':'NOT_RUN_BY_THIS_COLLECTOR','cross_host_neural_replay':'NOT_CLAIMED'})
  if found!=EXPECTED_ARTIFACTS: raise ValueError('missing CNEH workflow artifacts '+repr(sorted(EXPECTED_ARTIFACTS-found)))
  self.finish({'schema':'cneh-final-ci-artifacts-v1','artifact_integrity':'PASS','actor':self.actor,'artifacts':receipts,
               'all_final_workflow_runs':[{'id':r['id'],'path':r['path'],'event':r['event'],'head_sha':r['head_sha'],'status':r['status'],'conclusion':r['conclusion'],'url':r['html_url']} for r in runs],
               'scope':'GitHub API-bound archives and every declared inner manifest; no downloaded code execution or cross-host neural metadata replay claim'},'ci-artifacts.json')

def main():
 os.umask(0o022)
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--repo',required=True);parser.add_argument('--final-sha',required=True);parser.add_argument('--out',required=True)
 parser.add_argument('--inputs',help='External pinned input root; defaults to repository parent/inputs')
 parser.add_argument('--mode',choices=['l0','ci-artifacts'],required=True);args=parser.parse_args()
 if not re.fullmatch(r'[0-9a-f]{40}',args.final_sha): parser.error('explicit full final delivery SHA required')
 collector=Collector(args)
 try:
  getattr(collector,args.mode.replace('-','_'))();return 0
 except Exception as error:
  (collector.out/'failure.json').write_bytes(canonical({'status':'FAIL','final_sha':args.final_sha,'error_type':type(error).__name__,'error':str(error),'timestamp_utc':utc(),'qualification_decision':'NOT_PERFORMED'}))
  print(json.dumps({'status':'FAIL','error_type':type(error).__name__,'error':str(error)}));return 1
if __name__=='__main__': raise SystemExit(main())
