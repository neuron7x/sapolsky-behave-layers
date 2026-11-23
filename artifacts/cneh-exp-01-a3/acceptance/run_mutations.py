"""Fixed A3 calibration; result errors/timeouts never count as assertion kills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CATALOG = [
    ('fresh_output_reservation_removed', 'self.out.mkdir(parents=True,exist_ok=False)', 'self.out.mkdir(parents=True,exist_ok=True)'),
    ('auditor_source_binding_removed', 'if sha(raw)!=self.auditor_sha256 or sha(Path(__file__).read_bytes())!=self.auditor_sha256:', 'if False:'),
    ('workflow_completion_guard_removed', "  if run.get('status')!='completed':pending=True\n  elif run.get('conclusion')!='success':errors.append('workflow did not succeed')", '  pass'),
    ('historical_row_preservation_removed', "if any(current.get(r['run_id'])!=canonical(r) for r in old_rows):raise ValueError('historical ledger row deleted or rewritten')", "if False:raise ValueError('historical ledger row deleted or rewritten')"),
]
PATHS = ['experiments/cneh_exp_01/acceptance.py', 'experiments/cneh_exp_01/required_checks_manifest.json',
         'tests/test_cneh_exp_01_acceptance.py', 'artifacts/cneh-exp-01-a2/acceptance-auditor.py',
         'docs/lab/EXPERIMENT_LEDGER.jsonl']
RUNNER = "import json,unittest; s=unittest.defaultTestLoader.discover('tests',pattern='test_cneh_exp_01_acceptance.py');r=unittest.TextTestRunner(verbosity=2).run(s);print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses)}));raise SystemExit(0 if r.wasSuccessful() and r.testsRun>=19 and not r.skipped and not r.expectedFailures and not r.unexpectedSuccesses else 1)"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    inputs = {p: (root / p).read_bytes() for p in PATHS}
    original = inputs[PATHS[0]].decode()
    results = []
    for name, before, after in [('baseline', None, None), *CATALOG]:
        with tempfile.TemporaryDirectory(prefix='cneh-a3-mutation-') as directory:
            target = Path(directory)
            for relative, raw in inputs.items():
                path = target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            if before is not None:
                if original.count(before) != 1:
                    raise ValueError('mutation anchor must match exactly once: ' + name)
                (target / PATHS[0]).write_text(original.replace(before, after))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            command = [sys.executable, '-B', '-c', RUNNER]
            completed = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True, timeout=30)
            for stream in ('stdout', 'stderr'):
                (out / (name + '.' + stream + '.log')).write_text(getattr(completed, stream))
            counts = json.loads(completed.stdout.strip().splitlines()[-1])
            valid = counts['tests'] >= 19 and all(counts[k] == 0 for k in ('errors', 'skips', 'expected_failures', 'unexpected_successes'))
            classification = 'SURVIVED_OR_INVALID'
            if name == 'baseline' and completed.returncode == 0 and valid and counts['failures'] == 0:
                classification = 'PASS'
            elif name != 'baseline' and completed.returncode == 1 and valid and counts['failures'] > 0:
                classification = 'KILLED_ASSERTION'
            patch = {'before': before, 'after': after}
            results.append({'name': name, 'command': command, 'patch': patch, 'patch_sha256': sha(json.dumps(patch, sort_keys=True).encode()),
                            'exit_code': completed.returncode, 'classification': classification, 'counts': counts,
                            'mutated_source_sha256': sha((target / PATHS[0]).read_bytes())})
    unchanged = all((root / p).read_bytes() == raw for p, raw in inputs.items())
    report = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'input_sha256': {p: sha(raw) for p, raw in inputs.items()}, 'source_unchanged': unchanged, 'results': results,
              'killed': sum(row['classification'] == 'KILLED_ASSERTION' for row in results), 'total_mutants': len(CATALOG),
              'driver_sha256': sha(Path(__file__).read_bytes())}
    report['status'] = 'PASS' if unchanged and results[0]['classification'] == 'PASS' and report['killed'] == len(CATALOG) else 'FAIL'
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    paths = sorted(path for path in out.iterdir() if path.is_file())
    (out / 'SHA256SUMS').write_text(''.join(f'{sha(path.read_bytes())}  {path.name}\n' for path in paths))
    print(json.dumps({'status': report['status'], 'killed': report['killed'], 'total': report['total_mutants']}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
