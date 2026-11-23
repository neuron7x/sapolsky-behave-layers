import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
os.umask(0o022);root=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo');evidence=root.parent/'evidence/redteam-a3-final';records=[]
def digest(data):return hashlib.sha256(data).hexdigest()
def execute(label,argv,cwd):
 p=subprocess.run([str(x) for x in argv],cwd=cwd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(cwd)},capture_output=True)
 for name,payload in [('stdout',p.stdout),('stderr',p.stderr)]: (evidence/(label+'.'+name)).write_bytes(payload)
 records.append({'label':label,'argv':[str(x) for x in argv],'exit_code':p.returncode,'stdout_sha256':digest(p.stdout),'stderr_sha256':digest(p.stderr)})
 return p
with tempfile.TemporaryDirectory(prefix='cneh-history-resign-',dir=root.parent/'evidence') as temp:
 clone=Path(temp)/'repo';p=execute('history-clone',['git','clone','--no-hardlinks','--quiet',root,clone],root)
 if p.returncode:raise RuntimeError('fixture clone failed')
 execute('history-frozen-base',['git','checkout','--detach','0d362a42edecd9fd654ca476602ab51f3fdaa715'],clone)
 for name in ['experiments/cneh_exp_01/acceptance.py','experiments/cneh_exp_01/provenance.py','tests/test_cneh_exp_01_acceptance.py','tests/test_cneh_exp_01_provenance.py']:
  shutil.copyfile(root/name,clone/name)
 execute('history-add-candidate',['git','add','experiments/cneh_exp_01/acceptance.py','experiments/cneh_exp_01/provenance.py','tests/test_cneh_exp_01_acceptance.py','tests/test_cneh_exp_01_provenance.py'],clone)
 execute('history-baseline-commit',['git','-c','user.name=Redteam fixture','-c','user.email=redteam@example.invalid','-c','commit.gpgsign=false','commit','-qm','isolated reviewed A3 candidate'],clone)
 baseline=execute('history-baseline-checksums',['make','-f','Makefile.cwc','verify-evidence'],clone)
 if baseline.returncode:raise RuntimeError('baseline checksums failed')
 target=clone/'artifacts/cneh-exp-01-a2/g4-a2-audit.py';before=target.read_bytes();after=before.replace(b'import copy\n',b'',1)
 if after==before:raise RuntimeError('mutation anchor absent')
 target.write_bytes(after)
 receipt=clone/'artifacts/cneh-exp-01-a2/g4-a2-epistemic.json';d=json.loads(receipt.read_text());d['audit_script_sha256']=digest(after);receipt.write_text(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n')
 for sums in sorted((clone/'artifacts/cneh-exp-01-a2').rglob('SHA256SUMS'),key=lambda p:len(p.parts),reverse=True):
  lines=[]
  for line in sums.read_text().splitlines():
   _,name=line.split('  ',1);lines.append(digest((sums.parent/name).read_bytes())+'  '+name)
  sums.write_text('\n'.join(lines)+'\n')
 execute('history-mutant-add',['git','add','artifacts/cneh-exp-01-a2'],clone)
 execute('history-mutant-commit',['git','-c','user.name=Redteam fixture','-c','user.email=redteam@example.invalid','-c','commit.gpgsign=false','commit','-qm','isolated historical rewrite with recomputed manifests'],clone)
 mutated_commit=execute('history-mutant-head',['git','rev-parse','HEAD'],clone).stdout.decode().strip()
 checksums=execute('history-resigned-checksums',['make','-f','Makefile.cwc','verify-evidence'],clone)
 semantic=execute('history-resigned-semantic',[root.parent/'inputs/lqp43-full-venv/bin/python','-B','scripts/validate_evidence.py'],clone)
 regen=execute('history-resigned-docs-regen',['make','-f','Makefile.cwc','docs-regen','PY='+os.sys.executable],clone)
 docdiff=execute('history-resigned-docs-diff',['git','diff','--exit-code','docs/lab/EXPERIMENT_LEDGER.jsonl','docs/vnv/DOCUMENT_STATUS_REGISTER.csv'],clone)
 tests=execute('history-resigned-acceptance-tests',[os.sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_cneh_exp_01_acceptance.py','-v'],clone)
 frozen=execute('history-gitblob-negative',['git','diff','--exit-code','f5625363f72be3652d6b6e6fbfad1ceeac57e857','HEAD','--','artifacts/cneh-exp-01-a2'],clone)
 result={'schema':'cneh-resigned-historical-evidence-negative-v1','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'candidate_acceptance_sha256':digest((root/'experiments/cneh_exp_01/acceptance.py').read_bytes()),'fixture_base_commit':'0d362a42edecd9fd654ca476602ab51f3fdaa715','fixture_mutated_commit':mutated_commit,'mutation':'Remove unused import copy from immutable A2 g4 audit, update declared audit-script hash, recompute every A2 SHA256SUMS bottom-up; commit only in isolated clone','before_sha256':digest(before),'after_sha256':digest(after),'components':{'checksum_gate':checksums.returncode,'semantic_validator':semantic.returncode,'docs_regeneration':regen.returncode,'docs_diff_gate':docdiff.returncode,'acceptance_unit_tests':tests.returncode,'frozen_git_blob_comparison':frozen.returncode},'records':records,'status':'REPRODUCED_CI_HISTORY_BOUNDARY_GAP' if all(p.returncode==0 for p in (checksums,semantic,regen,docdiff,tests)) and frozen.returncode==1 else 'PARTIAL_OR_FAILED_REPRODUCTION','not_run':['full hosted CI','bibliography','CodeQL','full unrelated scientific suite'],'scientific_promotion_authorized':False}
 out=evidence/'historical-resign-result.json';out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({'receipt':str(out),'sha256':digest(out.read_bytes()),'status':result['status'],'components':result['components']}))
