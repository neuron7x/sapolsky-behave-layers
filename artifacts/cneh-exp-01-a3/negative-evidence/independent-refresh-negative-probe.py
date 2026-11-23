"""Reproduces v1 refresh false PASS; G1/G2 explicitly mocked, no real qualification."""
import contextlib, hashlib, io, json, os, runpy, tempfile
from pathlib import Path
from types import SimpleNamespace
os.umask(0o022)
b = Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43')
root = b / 'evidence/final-acceptance'
source = root / 'audit.py'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
assert digest == 'fabdb74ac9572086a847c0486da10039f00ae4a89e46c08d9eeeff9bd26862d1'
m = runpy.run_path(str(source))
final = 'f5625363f72be3652d6b6e6fbfad1ceeac57e857'
out = Path(tempfile.mkdtemp(prefix='independent-refresh-negative-', dir=root))
(out / 'checkout').mkdir()
(out / 'final-source-manifest.json').write_bytes(m['canonical']({'commit': '0'*40, 'files': {}}))
(out / 'local-replay-receipt.json').write_bytes(m['canonical']({
    'final_sha': final, 'auditor_sha256': digest,
    'G3': {'status': 'PASS'},
    'G4': {'status': 'PASS', 'scientific_promotion_authorized': True},
}))
a = m['Audit'](SimpleNamespace(repo=str(b/'repo'), out=str(out), final_sha=final, refresh=True))
a.g1 = lambda: {'status': 'PASS', 'fixture': 'assumed_G1_for_isolated_boundary_test'}
a.g2 = lambda: {'status': 'PASS', 'fixture': 'assumed_G2_for_isolated_boundary_test'}
stream = io.StringIO()
with contextlib.redirect_stdout(stream):
    code = a.run()
result = {'observed_exit': code, 'false_PASS_reproduced': code == 0,
          'boundaries_mocked': ['G1', 'G2'], 'actual_checkout_file_count': len(list((out/'checkout').rglob('*'))),
          'receipt': json.loads(stream.getvalue()), 'auditor_sha256': digest,
          'source_commit': final, 'scope': 'adversarial isolated replay-gate test, not actual qualification'}
(out/'probe-stdout.log').write_text(stream.getvalue())
(out/'probe-result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
