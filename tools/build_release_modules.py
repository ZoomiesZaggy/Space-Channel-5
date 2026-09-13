"""Build release modules from the corresponding generated-source archive."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from build_paths import ROOT, WORK
from build_aot_split import build

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--compiler',default='clang')
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args()
    if hashlib.sha256(args.archive.read_bytes()).hexdigest()!=args.sha256:
        raise RuntimeError('Source archive checksum mismatch')
    source=WORK/'release-module-source';source.mkdir(parents=True,exist_ok=True)
    output=ROOT/'build';output.mkdir(exist_ok=True)
    expected={f'sc5-boot-probe-round{i}.c' for i in range(1,5)}|{'manifest.json'}
    with tarfile.open(args.archive) as archive:
        members=archive.getmembers()
        if len(members)!=5 or {m.name for m in members}!=expected or any(not m.isfile() or m.size>150_000_000 for m in members):
            raise RuntimeError('Unexpected source archive contents')
        for member in members:
            with archive.extractfile(member) as handle:
                (source/member.name).write_bytes(handle.read())
    manifest=json.loads((source/'manifest.json').read_text())
    cc=shutil.which(args.compiler)
    if not cc:raise RuntimeError('Compiler not found')
    target=subprocess.check_output([cc,'-dumpmachine'],text=True).strip()
    suffix='.dll' if any(word in target for word in ('windows','mingw')) else '.dylib' if 'darwin' in target else '.so'
    for number in range(1,5):
        path=source/f'sc5-boot-probe-round{number}.c'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest[path.name]:
            raise RuntimeError('Generated source checksum mismatch')
        build(cc,output/f'native-diff-round{number}{suffix}',jobs=args.jobs,opt='2',source_path=path,object_dir=f'release-round{number}')
    shutil.copy2(output/f'native-diff-round1{suffix}',output/f'native-diff{suffix}')

if __name__=='__main__':main()
