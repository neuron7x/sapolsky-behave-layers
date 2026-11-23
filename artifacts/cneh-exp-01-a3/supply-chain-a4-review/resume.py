"""Repeat archive-incompatible test in an isolated real Git checkout; retain attempt1."""
import importlib.util,json,hashlib,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__file__).with_name('review.py');spec=importlib.util.spec_from_file_location('a4review',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.records=json.loads((m.OUT/'commands.json').read_bytes())
clone=m.OUT/'git-checkout'
m.command('isolated-clone',['git','clone','--shared','--no-checkout',m.REPO,clone],cwd=m.OUT)
m.command('isolated-detached-head',['git','checkout','--detach',m.HEAD],cwd=clone)
m.CHECKOUT=clone
before=json.loads((m.OUT/'before.json').read_bytes())
for name,record in before['files'].items():
 if m.sha((clone/name).read_bytes())!=record['sha256']:raise ValueError('cloned A4 source differs')
m.save('attempt1-adjudication.json',{'status':'INVALID_VERIFIER_FIXTURE','cause':'git archive omitted .git required by assurance_report Git provenance test','observed_tests':{'passed':48,'failed':1,'subtests_passed':10},'raw_failure_preserved':'failure.json','production_source_changed':False,'test_selection_unchanged':True})
m.command('targeted-tests-r2',[m.PY,'-B','-m','pytest','-q','-p','no:cacheprovider','tests/test_dependency_integrity_gate.py','tests/test_cwc_dependency_audit.py','--junitxml='+str(m.OUT/'targeted-tests-r2.xml')])
suites=ET.parse(m.OUT/'targeted-tests-r2.xml').getroot();counts={k:sum(int(s.get(k,'0')) for s in suites.findall('testsuite')) for k in ('tests','failures','errors','skipped')}
if counts['tests']!=49 or any(counts[k] for k in ('failures','errors','skipped')):raise ValueError('test count/status mismatch')
m.command('real-advisory-audits',[m.PY,'-B','scripts/cwc_dependency_audit.py'])
actual=(m.OUT/'real-advisory-audits.stdout').read_text()
if [line for line in actual.splitlines() if line.startswith('AUDIT TARGET:')]!=['AUDIT TARGET: runtime.txt','AUDIT TARGET: dev-group.txt','AUDIT TARGET: cwc-dev.lock']:raise ValueError('audit target roster mismatch')
m.command('negative-env-create',[m.PY,'-B','-m','venv','--without-pip',m.OUT/'wrong-hash-venv'])
(m.OUT/'wrong-hash.lock').write_text('uv==0.10.12 --hash=sha256:'+'0'*64+'\n')
m.command('official-wheel-wrong-hash',['uv','pip','install','--python',m.OUT/'wrong-hash-venv/bin/python','--require-hashes','--only-binary',':all:','--default-index','https://pypi.org/simple','-r',m.OUT/'wrong-hash.lock'],expected=1)
m.command('wrong-hash-no-install',[m.OUT/'wrong-hash-venv/bin/python','-B','-c','import importlib.metadata; assert not any(d.metadata["Name"].lower()=="uv" for d in importlib.metadata.distributions())'])
prior=m.BASE/'evidence/ci-supplychain-a4';verified=[]
for line in (prior/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1)
 if m.sha((prior/name).read_bytes())!=digest:raise ValueError('executor evidence tampered '+name)
 verified.append(name)
m.save('executor-evidence-integrity.json',{'verified_manifest_members':len(verified),'sha256':m.sha((prior/'SHA256SUMS').read_bytes()),'scope':'byte integrity only; executor conclusions are not independent execution'})
for name,record in before['files'].items():
 if m.sha((m.REPO/name).read_bytes())!=record['sha256'] or m.sha((clone/name).read_bytes())!=record['sha256']:raise ValueError('scoped source drift')
final_head=m.command('final-head',['git','rev-parse','HEAD'],cwd=m.REPO).decode().strip()
final_status=m.command('final-status',['git','status','--porcelain=v1','--untracked-files=all'],cwd=m.REPO).decode()
m.command('unchanged-threshold-inputs',['git','diff','--exit-code',m.SOURCE+'^',m.SOURCE,'--','uv.lock','cwc-requirements-dev.txt','pyproject.toml','experiments/cneh_exp_01/protocol.json'],cwd=m.REPO)
m.command('clone-source-clean',['git','status','--porcelain=v1','--untracked-files=all'],cwd=clone)
if (m.OUT/'clone-source-clean.stdout').read_bytes():raise ValueError('isolated clone drift')
installed=json.loads((m.OUT/'installed-record-bytes.stdout').read_bytes());closure=json.loads((m.OUT/'installed-transitive-closure.stdout').read_bytes());official=json.loads((m.OUT/'official-wheel-provenance.json').read_bytes())
locks={p.name:m.locks(p) for p in (clone/'requirements').glob('*.lock') if p.name in ('ci-uv.lock','cwc-dev.lock','pip-audit.lock')}
report={'schema':'cneh-a4-independent-review-v1','status':'PASS_WITH_CAVEATS','scope_source_commit':m.SOURCE,'initial_head':before['head'],'final_head':final_head,'scoped_source_unchanged':True,'isolated_execution_head':m.HEAD,'isolated_execution_tree_clean':True,'scope_sha256':m.sha(json.dumps(before['files'],sort_keys=True,separators=(',',':')).encode()),'files':before['files'],'final_live_status':final_status,'scope_diff_sha256':before['scope_diff_sha256'],
'source_archive_sha256':m.sha((m.OUT/'source.tar').read_bytes()),'official_wheel_releases':official['unique_releases'],'official_allowed_wheel_entries':official['allowed_wheel_entries'],'lock_dependency_counts':{k:len(v) for k,v in locks.items()},'installed_record_files_checked':installed['record_files_checked'],'unhashed_record_entries':installed['unhashed_record_entries'],'transitive_edges_checked':closure['active_dependency_edges'],'targeted_tests':counts,'targeted_subtests_passed':10,'actual_advisory_audits':3,'wrong_official_wheel_hash_exit':1,'wrong_hash_package_installed':False,'findings':[],
'caveats':['Scoped A4 review only; concurrently edited A3 files excluded.','Final-SHA hosted CI and complete G1-G4 NOT RUN.','PyPI metadata/TLS and pre-existing Python/uv/OS are the bootstrap trust boundary.','Initial archive fixture failure is retained as INVALID_VERIFIER_FIXTURE; unchanged tests passed in a real isolated clone.','Historical unconfigured mutmut CLI failure remains preserved and is not a successful mutation run.'],'scientific_promotion_authorized':False,'external_replication':'NOT_TESTED'}
m.save('report.json',report)
manifest={p.relative_to(m.OUT).as_posix():m.sha(p.read_bytes()) for p in m.OUT.rglob('*') if p.is_file() and not any(x in p.relative_to(m.OUT).parts for x in ('checkout','git-checkout','tmp','uv-cache','pip-cache','wrong-hash-venv')) and p.name!='SHA256SUMS'}
(m.OUT/'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(manifest.items())))
print(json.dumps({'status':report['status'],'receipt':str(m.OUT/'report.json'),'sha256':m.sha((m.OUT/'report.json').read_bytes())}),flush=True)
