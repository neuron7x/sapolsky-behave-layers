#!/usr/bin/env bash
set -euo pipefail
dest=/tmp/cneh05y
mkdir -p "$dest"
source=experiments/cneh_exp_05y/kernel.c
flags=(-std=c11 -O2 -fPIC -shared -ffp-contract=off -fno-fast-math -frounding-math -fno-tree-vectorize -fexcess-precision=standard -Wall -Wextra -Werror)
case "$(uname -m)" in
  x86_64) flags+=(-mno-fma);;
  aarch64) ;;
  *) exit 2;;
esac
gcc "${flags[@]}" "$source" -o "$dest/libdp.so" -lmpfr -lgmp -lm
objdump -d --no-show-raw-insn "$dest/libdp.so" > "$dest/disassembly.txt"
nm -D --undefined-only "$dest/libdp.so" > "$dest/imports.txt"
# Audit actual instruction mnemonics, not merely compiler arguments.
if grep -Ei '^[[:space:]]*[0-9a-f]+:[[:space:]]+(v?f(n?madd|n?msub|mla|mls)|vfmaddsub|vfmsubadd)[[:alnum:].]*[[:space:]]' "$dest/disassembly.txt"; then
  echo "forbidden FMA opcode"; exit 2
fi
if grep -Ei '[[:space:]](exp|exp2|expm1|pow|sqrt|fma|log|log2|log1p)(f|l)?(@|$)' "$dest/imports.txt"; then
  echo "forbidden native transcendental symbol"; exit 2
fi
export CNEH_FLAGS="${flags[*]}"
python - <<'PY'
import hashlib,json,os,platform,subprocess
from pathlib import Path
d=Path("/tmp/cneh05y")
def sha(p):return hashlib.file_digest(Path(p).open("rb"),"sha256").hexdigest()
out={"arch":platform.machine(),"flags":os.environ["CNEH_FLAGS"],"compiler":subprocess.check_output(["gcc","--version"],text=True).splitlines()[0],
     "packages":subprocess.check_output(["dpkg-query","-W","libmpfr-dev","libmpfr6","libgmp10"],text=True).splitlines(),
     "kernel_source_sha256":sha("experiments/cneh_exp_05y/kernel.c"),"library_sha256":sha(d/"libdp.so"),
     "disassembly_sha256":sha(d/"disassembly.txt"),"imports_sha256":sha(d/"imports.txt"),"forbidden_fma":0,"forbidden_transcendental_imports":0}
(d/"build.json").write_text(json.dumps(out,sort_keys=True,separators=(",",":"))+"\n")
print(out)
PY
