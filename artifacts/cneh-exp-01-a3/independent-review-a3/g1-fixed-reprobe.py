import hashlib,importlib.util,json,subprocess
from pathlib import Path
from unittest.mock import patch
root=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43/repo')
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
import sys
sys.path.insert(0,str(root))
testmod=load('acceptance_tests',root/'tests/test_cneh_exp_01_acceptance.py');results=[]
for label,path in [('original',root.parent/'evidence/acceptance-a3-implementation/acceptance-pre-v9.py'),('fixed',root/'experiments/cneh_exp_01/acceptance.py')]:
 gate=load('gate_'+label,path);testmod.gate=gate;case=testmod.AcceptanceTests();case.setUp();rows=[]
 try:
  case.git_fixture();case.git('remote','add','origin','https://github.com/'+gate.REPOSITORY+'.git');case.git('update-ref','refs/remotes/origin/'+gate.BRANCH,case.final_sha);case.git('config','branch.'+gate.BRANCH+'.remote','origin');case.git('config','branch.'+gate.BRANCH+'.merge','refs/heads/'+gate.BRANCH)
  audit=gate.Audit(case.args());tree=case.git('rev-parse','HEAD^{tree}')
  pr={'head':{'sha':case.final_sha,'ref':gate.BRANCH,'repo':{'full_name':gate.REPOSITORY}},'base':{'ref':'main','sha':case.final_sha,'repo':{'full_name':gate.REPOSITORY}},'merge_commit_sha':case.final_sha,'mergeable':True,'mergeable_state':'clean'}
  def api(label,endpoint):return {'pr-merge-commit':{'tree':{'sha':tree}},'github-actor':{'login':'neuron7x'},'canonical-repository':{'full_name':gate.REPOSITORY},'pr-head':pr,'remote-branch':{'object':{'sha':case.final_sha}}}[label]
  original=audit.command
  def command(label,args,**kw):
   if label=='origin-ls-remote':return (case.final_sha+'\trefs/heads/'+gate.BRANCH+'\n').encode()
   if label=='canonical-fetch':return b''
   if label=='fetched-head':return case.final_sha.encode()
   return original(label,args,**kw)
  with patch.object(audit,'api',side_effect=api),patch.object(audit,'command',side_effect=command),patch.object(audit,'collect_provenance',return_value={'status':'PASS','scope':'network collector mocked'}):
   for mergeable,state in [(True,'clean'),(False,'dirty'),(None,'unknown')]:
    pr.update(mergeable=mergeable,mergeable_state=state);result=audit.g1();rows.append({'mergeable':mergeable,'mergeable_state':state,'observed_status':result['status'],'base_is_ancestor':result['base_is_ancestor'],'merge_tree_equals_final':result['merge_tree_sha']==result['final_tree_sha']})
 finally:case.doCleanups()
 results.append({'label':label,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'results':rows})
passed=[r['observed_status'] for r in results[0]['results']]==['PASS','PASS','UNKNOWN'] and [r['observed_status'] for r in results[1]['results']]==['PASS','FAIL','UNKNOWN']
report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'scope':'Actual isolated Git; mocked GitHub API/download boundaries and provenance collector; no live PR writes','status':'REPRODUCED_THEN_FIXED' if passed else 'FAIL','results':results}
out=root.parent/'evidence/redteam-a3-final/g1-fixed-reprobe.json';out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':report['status'],'receipt':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}));raise SystemExit(0 if passed else 1)
