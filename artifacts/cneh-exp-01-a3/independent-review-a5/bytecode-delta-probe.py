import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
root=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo');out=root.parent/'evidence/redteam-a5-final';rows=[]
runner="import sys,unittest;sys.path.insert(0,'tests');from test_cneh_exp_01_acceptance import AcceptanceTests;r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([AcceptanceTests('test_original_false_pass_remains_reproducible')]));raise SystemExit(0 if r.wasSuccessful() and r.testsRun==1 and not r.skipped else 1)"
old='''        original = types.ModuleType("historical_acceptance")
        original.__file__ = str(OLD)
        # Loading frozen evidence must not create a bytecode sidecar in its bundle.
        exec(compile(OLD.read_bytes(), str(OLD), "exec"), original.__dict__)'''
new='''        import importlib.util
        spec = importlib.util.spec_from_file_location("historical_acceptance", OLD)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)'''
for mode in ['exact_committed_test','unsafe_loader_restored_in_fixture']:
 with tempfile.TemporaryDirectory(prefix='cneh-a5-bytecode-',dir=root.parent/'evidence') as raw:
  temp=Path(raw)
  for name in ['experiments/cneh_exp_01/acceptance.py','tests/test_cneh_exp_01_acceptance.py']:
   target=temp/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
  bundle=temp/'artifacts/cneh-exp-01-a2';shutil.copytree(root/'artifacts/cneh-exp-01-a2',bundle)
  def inventory():return {p.relative_to(bundle).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
  before=inventory()
  if mode!='exact_committed_test':
   test=temp/'tests/test_cneh_exp_01_acceptance.py';s=test.read_text();assert s.count(old)==1;test.write_text(s.replace(old,new))
  env=dict(os.environ);env.pop('PYTHONDONTWRITEBYTECODE',None);env.pop('PYTHONPYCACHEPREFIX',None);env.pop('PYTHONPATH',None)
  p=subprocess.run([sys.executable,'-c',runner],cwd=temp,env=env,capture_output=True)
  (out/(mode+'.stdout')).write_bytes(p.stdout);(out/(mode+'.stderr')).write_bytes(p.stderr)
  after=inventory();rows.append({'mode':mode,'exit_code':p.returncode,'bytecode_writes_enabled':True,'bundle_unchanged':before==after,'bundle_pyc_files':[n for n in after if n.endswith('.pyc')],'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
passed=rows[0]['exit_code']==0 and rows[0]['bundle_unchanged'] and rows[1]['exit_code']==1 and not rows[1]['bundle_unchanged']
report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'acceptance_source_sha256':hashlib.sha256((root/'experiments/cneh_exp_01/acceptance.py').read_bytes()).hexdigest(),'test_source_sha256':hashlib.sha256((root/'tests/test_cneh_exp_01_acceptance.py').read_bytes()).hexdigest(),'status':'PASS' if passed else 'FAIL','results':rows,'scope':'One changed historical-loader test only; actual bytecode enabled, isolated copied source and bundle; unsafe-loader intervention only in own temporary fixture'}
p=out/'bytecode-delta.json';p.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps({'receipt':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':report['status']}));raise SystemExit(0 if passed else 1)
