"""Compare installed BN-Syn runtime bytes with hash-authenticated official wheels.

No package import, installed RECORD authority, installation or environment mutation.
An --expected-head run re-reads every installed byte and binds a fresh receipt.
"""
from __future__ import annotations
import argparse,base64,csv,datetime,email.parser,hashlib,io,json,os,re,stat,subprocess,sys,urllib.request,zipfile
from pathlib import Path,PurePosixPath
BASE=Path('/home/neuro7/Documents/Codex/2026-11-23/cneh-pr43')
REPO=BASE/'repo';ENV=BASE/'inputs/bnsyn-locked-venv';SITE=ENV/'lib/python3.12/site-packages'
WHEELS=BASE/'inputs/final-wheel-bytecheck-downloads'
LOCK=REPO/'experiments/cneh_exp_01/bnsyn-requirements.lock'
LOCK_SHA='d9c45ebba2f23a14132ab196e7d2a5543259c307040e45882ab9d156372eb6fe'
def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(data):return (json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def normal(name):return re.sub(r'[-_.]+','-',name).lower()
def safe(name):
 p=PurePosixPath(name)
 if not name or p.is_absolute() or '..' in p.parts or '\\' in name or '\x00' in name or str(p)!=name.rstrip('/'):
  raise ValueError('unsafe wheel/member path')
 return p
def lock_versions():
 if sha(LOCK.read_bytes())!=LOCK_SHA:raise ValueError('frozen lock bytes changed')
 versions={}
 for line in LOCK.read_text().replace('\\\n',' ').splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*',line)
  if not match:raise ValueError('unhashed or nonexact lock entry')
  name=normal(match[1])
  if name in versions:raise ValueError('duplicate lock entry')
  versions[name]={'version':match[2],'hashes':set(re.findall(r'sha256:([0-9a-f]{64})',match[3]))}
 if len(versions)!=7:raise ValueError('expected seven pinned packages')
 return versions
def installed_path(member):
 p=safe(member);parts=p.parts
 if parts[0].endswith('.data'):
  if len(parts)<3:raise ValueError('invalid wheel data mapping')
  destinations={'purelib':SITE,'platlib':SITE,'scripts':ENV/'bin','data':ENV}
  if parts[1] not in destinations:raise ValueError('unsupported wheel install scheme '+parts[1])
  path=destinations[parts[1]].joinpath(*parts[2:])
 else:path=SITE.joinpath(*parts)
 if ENV not in path.parents:raise ValueError('installed path escapes environment')
 return path
def regular_bytes(path,root):
 if path.is_symlink() or not path.is_file():raise ValueError('missing/nonregular installed member '+str(path))
 for parent in path.parents:
  if parent==root:break
  if parent.is_symlink():raise ValueError('symlinked installed parent')
 with path.open('rb') as stream:
  first=os.fstat(stream.fileno());data=stream.read();last=os.fstat(stream.fileno())
 if (first.st_ino,first.st_size,first.st_mtime_ns)!=(last.st_ino,last.st_size,last.st_mtime_ns):raise ValueError('file changed during read')
 return data
def compare(expected,path,root):
 observed=regular_bytes(path,root)
 if observed!=expected:raise ValueError('installed bytes differ from authenticated wheel '+str(path))
 return sha(observed)
def record_digest(data,digest,size):
 algorithm,separator,encoded=digest.partition('=')
 if not separator or algorithm not in ('sha256','sha384','sha512'):raise ValueError('unapproved RECORD digest')
 actual=base64.urlsafe_b64encode(hashlib.new(algorithm,data).digest()).rstrip(b'=').decode()
 if actual!=encoded or not size.isdecimal() or int(size)!=len(data):raise ValueError('wheel RECORD hash/size mismatch')
def main(args):
 verifier_sha256=sha(Path(__file__).read_bytes())
 out=Path(args.out).absolute();out.mkdir(parents=True,exist_ok=False)
 records=[]
 def git(*argv):
  run=subprocess.run(['git',*argv],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  records.append({'argv':['git',*argv],'exit_code':run.returncode,'stdout_sha256':sha(run.stdout),'stderr_sha256':sha(run.stderr)})
  (out/'commands.json').write_bytes(canonical(records))
  if run.returncode:raise RuntimeError('Git provenance command failed')
  return run.stdout
 try:
  status=git('status','--porcelain=v1','--untracked-files=all').decode();worktrees=git('worktree','list','--porcelain').decode();head=git('rev-parse','HEAD').decode().strip()
  if args.expected_head and (head!=args.expected_head or status):raise ValueError('final HEAD mismatch or dirty tree')
  if git('show',head+':experiments/cneh_exp_01/bnsyn-requirements.lock')!=LOCK.read_bytes():raise ValueError('lock is not authenticated by current commit')
  locks=lock_versions();wheels=sorted(WHEELS.glob('*.whl'))
  if len(wheels)!=7 or {p.name for p in WHEELS.iterdir()}!={p.name for p in wheels}:raise ValueError('downloaded wheel roster differs from seven wheels')
  packages=[];seen=set();authenticated={};expected_installed=set();namespace_roots=set();unhashed=[];all_wheel_members=0
  for wheel in wheels:
   payload=wheel.read_bytes();wheel_hash=sha(payload)
   with zipfile.ZipFile(io.BytesIO(payload)) as z:
    infos=z.infolist();names=[i.filename for i in infos]
    if len(names)!=len(set(names)):raise ValueError('duplicate ZIP names')
    for info in infos:
     safe(info.filename);mode=info.external_attr>>16
     if stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode):raise ValueError('nonregular wheel member')
    members={i.filename for i in infos if not i.is_dir()};all_wheel_members+=len(members)
    metadata=[n for n in members if n.endswith('.dist-info/METADATA')]
    if len(metadata)!=1:raise ValueError('ambiguous wheel identity')
    parsed=email.parser.BytesParser().parsebytes(z.read(metadata[0]));name=normal(parsed['Name']);version=parsed['Version']
    if name in seen or name not in locks or version!=locks[name]['version'] or wheel_hash not in locks[name]['hashes']:raise ValueError('wheel lock identity/hash mismatch')
    seen.add(name)
    url=f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url,timeout=30) as response:release_bytes=response.read()
    (out/(name+'-official-release.json')).write_bytes(release_bytes)
    release=json.loads(release_bytes);candidates=[u for u in release['urls'] if u['filename']==wheel.name and u['digests']['sha256']==wheel_hash and u['packagetype']=='bdist_wheel']
    if len(candidates)!=1 or not candidates[0]['url'].startswith('https://files.pythonhosted.org/') or candidates[0].get('yanked'):raise ValueError('official wheel origin/hash/yank mismatch')
    dist_info=metadata[0].rsplit('/',1)[0];record=dist_info+'/RECORD'
    if record not in members:raise ValueError('wheel RECORD missing')
    rows={}
    for row in csv.reader(io.StringIO(z.read(record).decode())):
     if len(row)!=3:raise ValueError('malformed wheel RECORD row')
     member,digest,size=row;safe(member)
     if member in rows:raise ValueError('duplicate RECORD member')
     rows[member]=(digest,size)
    if set(rows)!=members:raise ValueError('wheel RECORD does not cover exact ZIP file roster')
    package_count=0;package_bytes=0
    for member,(digest,size) in rows.items():
     target=installed_path(member);relative=target.relative_to(ENV).as_posix();expected_installed.add(relative)
     if target.is_relative_to(SITE):namespace_roots.add(target.relative_to(SITE).parts[0])
     if not digest:
      if member!=record or size:raise ValueError('unexpected unhashed wheel member')
      unhashed.append({'wheel':wheel.name,'member':member,'installed_path':relative,'classification':'INSTALLER_REWRITES_RECORD; outside installed-byte authentication'})
      continue
     data=z.read(member);record_digest(data,digest,size)
     if relative in authenticated:raise ValueError('cross-wheel installed member collision')
     authenticated[relative]={'wheel':wheel.name,'member':member,'sha256':compare(data,target,ENV),'size':len(data)}
     package_count+=1;package_bytes+=len(data)
    packages.append({'name':name,'version':version,'wheel_basename':wheel.name,'wheel_sha256':wheel_hash,'wheel_url':candidates[0]['url'],'official_release_json_sha256':sha(release_bytes),'hashed_members_verified':package_count,'hashed_bytes_verified':package_bytes,'all_zip_files':len(members),'unhashed_wheel_record_members':1})
  if seen!=set(locks) or not authenticated:raise ValueError('incomplete/nonexistent authenticated package coverage')
  # Inventory extras without trusting the installed RECORD to define coverage.
  extras=[];unknown=[];bootstrap=[]
  for path in sorted(SITE.rglob('*')):
   if path.is_symlink():raise ValueError('installed site-packages symlink')
   if not path.is_file():continue
   relative=path.relative_to(ENV).as_posix();site_relative=path.relative_to(SITE);top=site_relative.parts[0]
   if relative in expected_installed:continue
   if top=='pip' or re.fullmatch(r'pip-[^/]+\.dist-info',top):bootstrap.append(site_relative.as_posix());continue
   if path.suffix=='.pyc' and '__pycache__' in site_relative.parts:kind='GENERATED_BYTECODE_OUTSIDE_AUTHENTICATED_SCOPE'
   elif top in namespace_roots and top.endswith('.dist-info') and path.name in ('INSTALLER','REQUESTED','direct_url.json'):kind='INSTALLER_OUTPUT_OUTSIDE_AUTHENTICATED_SCOPE'
   else:kind='UNCLASSIFIED';unknown.append(site_relative.as_posix())
   extras.append({'path':site_relative.as_posix(),'classification':kind,'sha256_informational_only':sha(path.read_bytes())})
  if unknown:raise ValueError('unclassified installed source files '+repr(unknown))
  # A self-consistent forged installed RECORD cannot replace wheel-byte equality.
  fixture=out/'negative-member';fixture.mkdir();sample=b'authentic wheel payload\n';target=fixture/'module.py';target.write_bytes(sample+b'# forged\n')
  forged_digest=sha(target.read_bytes());(fixture/'RECORD').write_text('module.py,sha256='+base64.urlsafe_b64encode(hashlib.sha256(target.read_bytes()).digest()).rstrip(b'=').decode()+','+str(target.stat().st_size)+'\n')
  record_row=next(csv.reader(io.StringIO((fixture/'RECORD').read_text())))
  record_digest(target.read_bytes(),record_row[1],record_row[2])
  negative=False
  try:compare(sample,target,fixture)
  except ValueError:negative=True
  if not negative:raise ValueError('changed payload plus re-signed installed RECORD survived')
  for path in ('../outside','/outside','a/../b'):
   try:safe(path)
   except ValueError:pass
   else:raise ValueError('unsafe path control survived')
  for relative,entry in authenticated.items():
   if sha(regular_bytes(ENV/relative,ENV))!=entry['sha256']:raise ValueError('installed byte drift during verification')
  after=git('rev-parse','HEAD').decode().strip();after_status=git('status','--porcelain=v1','--untracked-files=all').decode()
  if sha(LOCK.read_bytes())!=LOCK_SHA:raise ValueError('lock changed during verification')
  if args.expected_head and (after!=args.expected_head or after_status):raise ValueError('final source changed during verification')
  (out/'authenticated-members.json').write_bytes(canonical(authenticated));(out/'excluded-installed-files.json').write_bytes(canonical({'extras':extras,'bootstrap_pip_files':bootstrap,'unhashed_wheel_members':unhashed}))
  if sha(Path(__file__).read_bytes())!=verifier_sha256:raise ValueError('verifier source drift during execution')
  report={'command_argv':sys.argv,'verifier_source_unchanged':True,'schema':'cneh-pinned-wheel-installed-byte-verification-v1','status':'PASS_WITH_CAVEATS','binding':'EXACT_FINAL_HEAD' if args.expected_head else 'PRE_FINAL_ONLY','source_head_before':head,'source_head_after':after,'expected_final_sha':args.expected_head,'source_status_before':status,'source_status_after':after_status,'worktrees':worktrees,'lock_sha256':LOCK_SHA,'environment_path':str(ENV),'site_packages_path':str(SITE),'packages':packages,'authenticated_members':len(authenticated),'authenticated_bytes':sum(x['size'] for x in authenticated.values()),'hashed_wheel_members_coverage':1.0,'all_wheel_zip_files':all_wheel_members,'unhashed_wheel_members':len(unhashed),'generated_bytecode_excluded':sum(x['classification'].startswith('GENERATED_BYTECODE') for x in extras),'installer_outputs_excluded':sum(x['classification'].startswith('INSTALLER_OUTPUT') for x in extras),'bootstrap_pip_files_outside_scope':len(bootstrap),'unclassified_installed_files':unknown,'installed_record_used_as_authority':False,'negative_resigned_installed_record_rejected':negative,'source_and_environment_mutated':False,'runtime_execution_attestation':False,'hardware_attestation':False,'external_replication':'NOT_TESTED','scientific_promotion_authorized':False,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verifier_sha256':verifier_sha256,'authenticated_members_sha256':sha((out/'authenticated-members.json').read_bytes()),'limitations':['Generated installer outputs, bytecode, unhashed installed RECORD, Python/pip/OS bootstrap and dynamically loaded system libraries are outside wheel-member byte authentication.','This binds content to frozen Git lock SHA and official PyPI wheel digest; no fabricated signature or external hardware attestation.','Pre-final receipt must be rerun with --expected-head after source freeze; no cached verdict is reused.']}
  (out/'report.json').write_bytes(canonical(report));(out/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(out).as_posix()}\n' for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
  print(json.dumps({'receipt':str(out/'report.json'),'sha256':sha((out/'report.json').read_bytes()),'status':report['status'],'members':len(authenticated),'packages':len(packages)}))
 except Exception as error:
  (out/'failure.json').write_bytes(canonical({'status':'FAIL','error_type':type(error).__name__,'error':str(error),'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}));raise
if __name__=='__main__':
 os.umask(0o022);parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True);parser.add_argument('--expected-head');args=parser.parse_args()
 if args.expected_head and not re.fullmatch(r'[0-9a-f]{40}',args.expected_head):parser.error('full exact final SHA required')
 main(args)
