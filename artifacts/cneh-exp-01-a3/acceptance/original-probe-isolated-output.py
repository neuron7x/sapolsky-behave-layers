import argparse, copy, hashlib, importlib.util, json, os, subprocess, tempfile
from pathlib import Path
os.umask(0o022)
root=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo')
source=root/'artifacts/cneh-exp-01-a2/acceptance-auditor.py'
spec=importlib.util.spec_from_file_location('auditor',source)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
final_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
results=[]
with tempfile.TemporaryDirectory(prefix='acceptance-redteam-',dir=root.parent/'evidence') as td:
 out=Path(td);(out/'checkout').mkdir()
 # No checkout source and no command/replay logs exist. Only caller-writable claims.
 (out/'final-source-manifest.json').write_bytes(m.canonical({'commit':'0'*40,'files':{}}))
 (out/'local-replay-receipt.json').write_bytes(m.canonical({'final_sha':final_sha,'auditor_sha256':source_sha,'G3':{'status':'PASS'},'G4':{'status':'PASS','scientific_promotion_authorized':True}}))
 a=m.Audit(argparse.Namespace(repo=str(root),out=str(out),final_sha=final_sha,refresh=True))
 # Isolate local trust-boundary test from live GitHub; explicitly assume G1/G2 success.
 a.g1=lambda:{'status':'PASS','fixture':'assumed G1 to isolate local refresh'}
 a.g2=lambda:{'status':'PASS','fixture':'assumed G2 to isolate local refresh'}
 code=a.run()
 receipt=m.read(sorted(out.glob('acceptance-*.json'))[-1])
 results.append({'id':'refresh_forged_empty_source_and_false_science','observed_exit':code,'expected_nonzero':True,'reproduced_false_pass':code==0 and receipt['ENGINEERING_QUALIFIED'] is True,'receipt':receipt,'actual_checkout_file_count':len(list((out/'checkout').rglob('*'))),'executed_commands':[r['label'] for r in a.records],'mocked_boundary':['G1','G2'],'unmocked_boundary':['initial real git status','initial real git worktree list','initial real HEAD','refresh manifest/receipt validation','final gate aggregation']})
checks=[{'id':i,'name':name,'head_sha':final_sha,'status':'completed','conclusion':'success'} for i,name in enumerate(sorted(m.REQUIRED_CHECKS),1)]
for label,mutate,expected in [
 ('missing_required_job',lambda c:c.pop(), 'UNKNOWN'),
 ('pending_required_job',lambda c:c[0].update(status='in_progress',conclusion=None),'PENDING'),
 ('failed_required_job',lambda c:c[0].update(conclusion='failure'),'FAIL')]:
 fixture=copy.deepcopy(checks);mutate(fixture);observed=m.classify_ci(fixture,[])['status']
 results.append({'id':label,'observed_status':observed,'expected_status':expected,'negative_control_passed':observed==expected})
report={'schema':'cneh-final-acceptance-redteam-v1','source_commit':final_sha,'auditor_sha256':source_sha,'review_scope':'acceptance auditor refresh receipt trust boundary and CI negative controls; no repository edits, no network calls','status':'REPRODUCED_DEFECT','results':results,'not_run':['actual GitHub G1/G2 refresh','fresh complete G3 replay','broad scientific/source suites'],'findings':[{'severity':'high','file':'artifacts/cneh-exp-01-a2/acceptance-auditor.py','line':247,'end_line':253,'trigger':'--refresh with caller-writable local-replay-receipt.json and final-source-manifest.json','mechanism':'saved G3/G4 statuses accepted without replay or digest-bound execution evidence; empty self-authored proof.files plus empty checkout passes check_no_drift; proof.commit ignored; G4 promotion true ignored','observed_consequence':'ENGINEERING_QUALIFIED true, exit0, despite zero checkout files/no replay and G4 scientific_promotion_authorized true; G1/G2 were explicitly isolated as assumed PASS'}]}
p=root.parent/'evidence/acceptance-a3-implementation/original-probe-result.json';p.write_bytes(m.canonical(report));print(json.dumps({'receipt':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':report['status']}))
