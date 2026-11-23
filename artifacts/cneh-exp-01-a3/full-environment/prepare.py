"""Prepare the frozen CPU environment only; never run the full gate here."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess
os.umask(0o022)
BASE=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43')
OUT=BASE/'evidence/lqp43-full-env-preparation';SOURCE=BASE/'evidence/a4-independent-review/git-checkout'
TARGET=BASE/'inputs/lqp43-full-venv';UV=BASE/'inputs/ci-supplychain-a4/bootstrap-final/bin/uv'
if TARGET.exists() or TARGET.is_symlink():raise FileExistsError('refuse to alter existing environment')
names=('uv.lock','pyproject.toml','requirements/cwc-dev.lock','requirements/ci-uv.lock')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
before={name:sha(SOURCE/name) for name in names}
records=[]
env=dict(os.environ)
env.update(UV_PROJECT_ENVIRONMENT=str(TARGET),UV_CACHE_DIR=str(OUT/'uv-cache'),UV_PYTHON_DOWNLOADS='never',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
def run(label,args,timeout=900):
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (OUT/(label+'.stdout')).open('wb') as stdout,(OUT/(label+'.stderr')).open('wb') as stderr:
  p=subprocess.run([str(x) for x in args],cwd=SOURCE,env=env,stdout=stdout,stderr=stderr,timeout=timeout)
 record={'label':label,'argv':[str(x) for x in args],'cwd':str(SOURCE),'start_utc':started,'end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':p.returncode,'stdout_sha256':sha(OUT/(label+'.stdout')),'stderr_sha256':sha(OUT/(label+'.stderr'))}
 records.append(record);(OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps({'label':label,'exit_code':p.returncode}),flush=True)
 if p.returncode:raise RuntimeError(label+' failed')
run('bootstrap-version',[UV,'--version'])
run('source-status',['git','status','--porcelain=v1','--untracked-files=all'])
if (OUT/'source-status.stdout').read_bytes():raise ValueError('preparation source checkout not clean')
run('cpu-frozen-sync',[UV,'sync','--frozen','--extra','cpu','--python','/usr/bin/python3.11','--no-python-downloads','--no-build'])
run('dev-hash-locked-install',[UV,'pip','install','--python',TARGET/'bin/python','--require-hashes','--only-binary',':all:','--default-index','https://pypi.org/simple','-r','requirements/cwc-dev.lock'])
run('installed-dependency-check',[UV,'pip','check','--python',TARGET/'bin/python'])
run('installed-versions',[UV,'pip','freeze','--python',TARGET/'bin/python'])
run('runtime-inventory',[TARGET/'bin/python','-B','-c','import json,platform,torch,numpy; print(json.dumps({"python":platform.python_version(),"torch":torch.__version__,"cuda_available":torch.cuda.is_available(),"torch_cuda_build":torch.version.cuda,"numpy":numpy.__version__}))'])
run('final-source-status',['git','status','--porcelain=v1','--untracked-files=all'])
if (OUT/'final-source-status.stdout').read_bytes():raise ValueError('preparation source checkout changed')
after={name:sha(SOURCE/name) for name in names}
if before!=after:raise ValueError('preparation input drift')
if any(sha(BASE/'repo'/name)!=digest for name,digest in before.items()):raise ValueError('live dependency inputs differ from prepared frozen inputs')
receipt={'schema':'cneh-local-full-gate-environment-v1','status':'ENVIRONMENT_PREPARED','full_gate_executed':False,'environment_path':str(TARGET),'preparation_source_commit':'b2b1262c5903955a3eabb7a32936967bd0964784','dependency_inputs_sha256':before,'bootstrap_binary_sha256':sha(UV),'bootstrap_version':(OUT/'bootstrap-version.stdout').read_text().strip(),'environment_overrides':{k:env[k] for k in ('UV_PROJECT_ENVIRONMENT','UV_CACHE_DIR','UV_PYTHON_DOWNLOADS','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')},'input_bytes_unchanged':True,'scientific_promotion_authorized':False,'scope':'CPU environment only; final-source canonical pr-full still requires explicit final SHA and must not overlap metrology'}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
(OUT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
print(json.dumps({'receipt':str(OUT/'receipt.json'),'sha256':sha(OUT/'receipt.json')}),flush=True)
