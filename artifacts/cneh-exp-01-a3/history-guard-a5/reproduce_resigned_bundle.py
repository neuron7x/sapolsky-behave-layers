from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile

os.umask(0o022)
repo=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo')
out=repo.parent/'evidence/history-guard-a5'
guard=repo/'scripts/cneh_history_guard.py'
sha=lambda data:hashlib.sha256(data).hexdigest()
records=[]
def run(label,argv,cwd=repo):
    result=subprocess.run(argv,cwd=cwd,capture_output=True)
    stdout=out/(label+'.stdout.log');stderr=out/(label+'.stderr.log')
    stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
    records.append({'label':label,'command':argv,'cwd':str(cwd),'exit_code':result.returncode,
                    'stdout_sha256':sha(result.stdout),'stderr_sha256':sha(result.stderr)})
    return result
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo).decode().strip()
guard_before=sha(guard.read_bytes())
with tempfile.TemporaryDirectory(prefix='cneh-history-production-attack-') as temporary:
    clone=Path(temporary)/'repo'
    assert run('production-clone',['git','clone','--no-hardlinks','--no-checkout',str(repo),str(clone)]).returncode==0
    assert run('production-checkout',['git','checkout','--detach',head],clone).returncode==0
    command=[sys.executable,'-B',str(guard),'--repo',str(clone)]
    baseline=run('production-baseline',command,clone)
    assert baseline.returncode==0
    bundle=clone/'artifacts/cneh-exp-01-a2'
    target=bundle/'acceptance-auditor.py'
    original=target.read_bytes()
    forged=original+b'\n# Adversarial substituted historical evidence fixture.\n'
    target.write_bytes(forged)
    manifest=bundle/'SHA256SUMS'
    original_manifest=manifest.read_bytes()
    updated=[]
    for line in original_manifest.decode().splitlines():
        digest,relative=line.split('  ',1)
        updated.append(sha((bundle/relative).read_bytes())+'  '+relative+'\n')
    manifest.write_text(''.join(updated))
    checksums=run('production-forged-checksums',['sha256sum','-c','SHA256SUMS'],bundle)
    assert checksums.returncode==0,checksums.stderr.decode()
    attack=run('production-forged-history',command,clone)
    rejected=json.loads(attack.stdout)
    assert attack.returncode==1 and rejected['status']=='FAIL' and 'historical byte mismatch' in rejected['error']
    assert run('production-attack-diff',['git','diff','--','artifacts/cneh-exp-01-a2'],clone).returncode==0
    receipt={'schema':'cneh-history-production-negative-v1','source_commit':head,
             'guard_sha256':guard_before,'baseline_status':json.loads(baseline.stdout)['status'],
             'current_manifest_check_exit_code':checksums.returncode,'historical_guard_exit_code':attack.returncode,
             'attack_target':'artifacts/cneh-exp-01-a2/acceptance-auditor.py',
             'original_file_sha256':sha(original),'forged_file_sha256':sha(forged),
             'original_manifest_sha256':sha(original_manifest),'forged_manifest_sha256':sha(manifest.read_bytes()),
             'historical_error':rejected['error'],'commands':records,
             'source_unchanged':guard_before==sha(guard.read_bytes()),
             'independent_replication':'NOT_TESTED','scientific_promotion_authorized':False}
    assert receipt['source_unchanged']
    (out/'production-resign-negative.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps({'baseline':receipt['baseline_status'],'current_manifest_exit':checksums.returncode,'history_guard_exit':attack.returncode,'source_commit':head,'guard_sha256':guard_before}))
