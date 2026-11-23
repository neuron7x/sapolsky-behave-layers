from __future__ import annotations
import concurrent.futures, datetime, hashlib, json, os, re, subprocess, sys, tarfile, urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET

os.umask(0o022)
BASE=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43')
REPO=BASE/'repo';OUT=BASE/'evidence/a4-independent-review';CHECKOUT=OUT/'checkout'
HEAD='b2b1262c5903955a3eabb7a32936967bd0964784';SOURCE='e9808dc27fef72826dc52966e1821a6e8c84a583'
PY=BASE/'inputs/ci-supplychain-a4/dev-final/bin/python'
records=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def save(name,data): (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def command(label,argv,cwd=None,expected=0,timeout=180):
 env=dict(os.environ);env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUT/'tmp'),UV_CACHE_DIR=str(OUT/'uv-cache'),PIP_CACHE_DIR=str(OUT/'pip-cache'))
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 run=subprocess.run([str(x) for x in argv],cwd=cwd or CHECKOUT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 (OUT/(label+'.stdout')).write_bytes(run.stdout);(OUT/(label+'.stderr')).write_bytes(run.stderr)
 row={'label':label,'argv':[str(x) for x in argv],'cwd':str(cwd or CHECKOUT),'start_utc':start,'exit_code':run.returncode,'expected_exit':expected,'stdout_sha256':sha(run.stdout),'stderr_sha256':sha(run.stderr)}
 records.append(row);save('commands.json',records)
 if run.returncode!=expected:raise RuntimeError(label+' unexpected exit '+str(run.returncode))
 return run.stdout
def locks(path):
 result={}
 for line in path.read_text().replace('\\\n',' ').splitlines():
  if not line.strip() or line.startswith('#'):continue
  m=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*',line)
  if not m:raise ValueError('nonhashlocked dependency '+path.name)
  name=re.sub(r'[-_.]+','-',m[1]).lower()
  if name in result:raise ValueError('duplicate dependency '+name)
  result[name]={'version':m[2],'hashes':re.findall(r'sha256:([0-9a-f]{64})',m[3])}
 return result
def release(pair):
 name,version=pair;url=f'https://pypi.org/pypi/{name}/{version}/json'
 with urllib.request.urlopen(url,timeout=30) as response:data=response.read()
 obj=json.loads(data);(OUT/'pypi'/(name+'-'+version+'.json')).write_bytes(data)
 wheels={x['digests']['sha256']:x for x in obj['urls'] if x['packagetype']=='bdist_wheel'}
 return pair,{'url':url,'response_sha256':sha(data),'wheel_hashes':wheels}
def run():
 (OUT/'tmp').mkdir();(OUT/'pypi').mkdir()
 command('source-archive',['git','archive','--format=tar','--output='+str(OUT/'source.tar'),HEAD],cwd=REPO)
 with tarfile.open(OUT/'source.tar') as t:t.extractall(CHECKOUT,filter='data')
 manifests={p.name:locks(p) for p in (CHECKOUT/'requirements').glob('*.lock') if p.name in ('ci-uv.lock','cwc-dev.lock','pip-audit.lock')}
 if set(manifests)!={'ci-uv.lock','cwc-dev.lock','pip-audit.lock'}:raise ValueError('lock roster')
 pairs=sorted({(n,e['version']) for rows in manifests.values() for n,e in rows.items()})
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:releases=dict(pool.map(release,pairs))
 bindings={};hash_count=0
 for lock,rows in manifests.items():
  for name,entry in rows.items():
   official=releases[name,entry['version']];bad=set(entry['hashes'])-set(official['wheel_hashes'])
   if bad:raise ValueError('hash not in official wheel release '+name)
   if any(not official['wheel_hashes'][h]['url'].startswith('https://files.pythonhosted.org/') for h in entry['hashes']):raise ValueError('unexpected wheel origin')
   hash_count+=len(entry['hashes']);bindings[lock+':'+name]={'version':entry['version'],'allowed_binary_wheels':len(entry['hashes']),'release_json_sha256':official['response_sha256']}
 save('official-wheel-provenance.json',{'unique_releases':len(releases),'allowed_wheel_entries':hash_count,'bindings':bindings})
 print('official wheel hashes authenticated',hash_count,flush=True)
 command('python-version',[PY,'--version']);command('uv-version',['uv','--version'])
 # Read the existing isolated verification environment, never modify it.
 metadata_code=r'''import base64,csv,hashlib,importlib.metadata,json
rows={};bad=[];checked=0;unhashed=0
for d in importlib.metadata.distributions():
 name=d.metadata['Name'];rows[name]={'version':d.version,'requires':d.requires or []}
 for f in d.files or []:
  if not f.hash:unhashed+=1;continue
  p=d.locate_file(f)
  actual=base64.urlsafe_b64encode(hashlib.new(f.hash.mode,p.read_bytes()).digest()).rstrip(b'=').decode()
  if actual!=f.hash.value:bad.append(str(f))
  checked+=1
print(json.dumps({'distributions':rows,'record_files_checked':checked,'unhashed_record_entries':unhashed,'mismatches':bad}))
'''
 installed=json.loads(command('installed-record-bytes',[PY,'-B','-c',metadata_code]))
 if installed['mismatches']:raise ValueError('installed RECORD mismatch')
 installed_names={re.sub(r'[-_.]+','-',n).lower():v for n,v in installed['distributions'].items()}
 for name,entry in manifests['cwc-dev.lock'].items():
  if installed_names.get(name,{}).get('version')!=entry['version']:raise ValueError('installed dev closure version mismatch '+name)
 # Dependency metadata closure uses the actual Python 3.11 environment markers.
 closure_code=r'''import importlib.metadata,json,re
from packaging.requirements import Requirement
from packaging.markers import default_environment
environment=default_environment();environment['extra']=''
installed={re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version for d in importlib.metadata.distributions()};bad=[];count=0
for d in importlib.metadata.distributions():
 for raw in d.requires or []:
  r=Requirement(raw)
  if r.marker and not r.marker.evaluate(environment):continue
  n=re.sub(r'[-_.]+','-',r.name).lower();count+=1
  if n not in installed or (r.specifier and not r.specifier.contains(installed[n])):bad.append([d.metadata['Name'],raw,installed.get(n)])
print(json.dumps({'active_dependency_edges':count,'unmet':bad,'environment':environment}))
'''
 closure=json.loads(command('installed-transitive-closure',[PY,'-B','-c',closure_code]))
 if closure['unmet']:raise ValueError('unmet installed transitive dependency')
 command('targeted-tests',[PY,'-B','-m','pytest','-q','-p','no:cacheprovider','tests/test_dependency_integrity_gate.py','tests/test_cwc_dependency_audit.py','--junitxml='+str(OUT/'targeted-tests.xml')])
 suites=ET.parse(OUT/'targeted-tests.xml').getroot();counts={k:sum(int(s.get(k,'0')) for s in suites.findall('testsuite')) for k in ('tests','failures','errors','skipped')}
 if counts['tests']!=49 or any(counts[k] for k in ('failures','errors','skipped')):raise ValueError('unexpected targeted test count/status '+repr(counts))
 command('real-advisory-audits',[PY,'-B','scripts/cwc_dependency_audit.py'])
 actual=(OUT/'real-advisory-audits.stdout').read_text()
 if [line for line in actual.splitlines() if line.startswith('AUDIT TARGET:')]!=['AUDIT TARGET: runtime.txt','AUDIT TARGET: dev-group.txt','AUDIT TARGET: cwc-dev.lock']:raise ValueError('actual audit target roster mismatch')
 command('negative-env-create',[PY,'-B','-m','venv','--without-pip',OUT/'wrong-hash-venv'])
 (OUT/'wrong-hash.lock').write_text('uv==0.10.12 --hash=sha256:'+'0'*64+'\n')
 command('official-wheel-wrong-hash',['uv','pip','install','--python',OUT/'wrong-hash-venv/bin/python','--require-hashes','--only-binary',':all:','--default-index','https://pypi.org/simple','-r',OUT/'wrong-hash.lock'],expected=1)
 command('wrong-hash-no-install',[OUT/'wrong-hash-venv/bin/python','-B','-c','import importlib.metadata; assert not any(d.metadata["Name"].lower()=="uv" for d in importlib.metadata.distributions())'])
 prior=BASE/'evidence/ci-supplychain-a4';verified=[]
 for line in (prior/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split('  ',1)
  if sha((prior/name).read_bytes())!=digest:raise ValueError('executor evidence manifest mismatch '+name)
  verified.append(name)
 save('executor-evidence-integrity.json',{'verified_manifest_members':len(verified),'source':'ci-supplychain-a4/SHA256SUMS','sha256':sha((prior/'SHA256SUMS').read_bytes()),'scope':'byte integrity only; executor conclusions are not substituted for independent execution'})
 before=json.loads((OUT/'before.json').read_bytes());after={}
 for p,v in before['files'].items():
  after[p]={'sha256':sha((REPO/p).read_bytes())}
  if after[p]['sha256']!=v['sha256']:raise ValueError('A4 scoped source drift '+p)
 final_head=command('final-head',['git','rev-parse','HEAD'],cwd=REPO).decode().strip()
 final_status=command('final-status',['git','status','--porcelain=v1','--untracked-files=all'],cwd=REPO).decode()
 command('unchanged-threshold-inputs',['git','diff','--exit-code',SOURCE+'^',SOURCE,'--','uv.lock','cwc-requirements-dev.txt','pyproject.toml','experiments/cneh_exp_01/protocol.json'],cwd=REPO)
 report={'schema':'cneh-a4-independent-review-v1','status':'PASS_WITH_CAVEATS','scope_source_commit':SOURCE,'initial_head':before['head'],'final_head':final_head,'scoped_source_unchanged':True,'scope_sha256':sha(json.dumps(before['files'],sort_keys=True,separators=(',',':')).encode()),'files':before['files'],'final_live_status':final_status,
 'source_archive_sha256':sha((OUT/'source.tar').read_bytes()),'official_wheel_releases':len(releases),'official_allowed_wheel_entries':hash_count,'lock_dependency_counts':{k:len(v) for k,v in manifests.items()},'installed_record_files_checked':installed['record_files_checked'],'unhashed_record_entries':installed['unhashed_record_entries'],'transitive_edges_checked':closure['active_dependency_edges'],'targeted_tests':counts,'actual_advisory_audits':3,'wrong_official_wheel_hash_exit':1,'wrong_hash_package_installed':False,
 'findings':[],'caveats':['Scoped A4 review only; untracked A3 files belong to concurrent agents and were not tested.','Hosted final-SHA CI and complete G1-G4 were not run.','PyPI registry metadata/TLS and pre-existing Python/uv/OS form the stated bootstrap trust boundary.','Historical unconfigured mutmut CLI failure remains preserved; not a successful mutation run.'],'scientific_promotion_authorized':False,'external_replication':'NOT_TESTED'}
 save('report.json',report)
 manifest={p.name:sha(p.read_bytes()) for p in OUT.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
 (OUT/'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(manifest.items())))
 print(json.dumps({'status':report['status'],'receipt':str(OUT/'report.json'),'sha256':sha((OUT/'report.json').read_bytes())}),flush=True)
if __name__=='__main__':
 try:run()
 except Exception as error:
  save('failure.json',{'status':'FAIL','error_type':type(error).__name__,'error':str(error),'scope_source_commit':SOURCE});raise
