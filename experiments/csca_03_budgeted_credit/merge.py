from __future__ import annotations
import argparse,csv,hashlib,json,statistics
from pathlib import Path

def sha(path:Path)->str:
 h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()
def mean(xs): return statistics.fmean(xs) if xs else 0.0

def merge(chunks:list[Path],out:Path)->dict:
 out.mkdir(parents=True,exist_ok=True)
 case_rows=[]; auth_rows=[]; summaries=[]
 for ch in chunks:
  with (ch/'case_results.csv').open(newline='') as f: case_rows.extend(csv.DictReader(f))
  with (ch/'context_authority.csv').open(newline='') as f: auth_rows.extend(csv.DictReader(f))
  summaries.append(json.load(open(ch/'summary.json')))
 case_rows.sort(key=lambda r:(int(r['seed']),r['family'],int(r['case_index']),int(r['budget']),r['method']))
 auth_rows.sort(key=lambda r:(int(r['seed']),r['family'],r['method'],int(r['budget'])))
 cp=out/'case_results.csv'; ap=out/'context_authority.csv'
 with cp.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(case_rows[0])); w.writeheader(); w.writerows(case_rows)
 with ap.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(auth_rows[0])); w.writeheader(); w.writerows(auth_rows)
 groups={}
 for r in case_rows: groups.setdefault((r['family'],r['method'],int(r['budget'])),[]).append(r)
 agg=[]
 for (family,method,budget),rows in sorted(groups.items()):
  agg.append({'family':family,'method':method,'budget':budget,'n_rows':len(rows),
   'mean_rmse_true_teacher':mean([float(r['rmse_true_teacher']) for r in rows]),
   'mean_rmse_model_teacher':mean([float(r['rmse_model_teacher']) for r in rows]),
   'mean_false_credit_mass_true':mean([float(r['false_credit_mass_true']) for r in rows]),
   'max_false_credit_mass_true':max(float(r['false_credit_mass_true']) for r in rows),
   'topset_recovery':mean([float(r['topset_recovery']) for r in rows]),
   'mean_max_estimator_variance':mean([float(r['max_estimator_variance']) for r in rows]),
   'max_estimator_variance':max(float(r['max_estimator_variance']) for r in rows),
   'mean_actual_evaluations':mean([float(r['actual_evaluations']) for r in rows]),
   'mean_model_teacher_false_mass_true':mean([float(r['model_teacher_false_mass_true']) for r in rows])})
 gp=out/'aggregate.csv'
 with gp.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(agg[0])); w.writeheader(); w.writerows(agg)
 first=summaries[0]
 summary={'seed_start':min(s['seed_start'] for s in summaries),'seed_count':sum(s['seed_count'] for s in summaries),
  'rows_per_context':first['rows_per_context'],'budgets':first['budgets'],'families':first['families'],'methods':first['methods'],
  'case_records':len(case_rows),'context_authority_records':len(auth_rows),'chunk_count':len(chunks),
  'exact_structural_evaluations':sum(s['exact_structural_evaluations'] for s in summaries),
  'approx_structural_evaluations':sum(s['approx_structural_evaluations'] for s in summaries),
  'total_structural_evaluations':sum(s['total_structural_evaluations'] for s in summaries),
  'wall_seconds_sum_chunks':sum(s['wall_seconds'] for s in summaries),
  'artifacts':{'case_results_sha256':sha(cp),'aggregate_sha256':sha(gp),'context_authority_sha256':sha(ap)}}
 (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); return summary

def main():
 p=argparse.ArgumentParser(); p.add_argument('--chunks',type=Path,nargs='+',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(merge(a.chunks,a.out),indent=2,sort_keys=True))
if __name__=='__main__': main()
