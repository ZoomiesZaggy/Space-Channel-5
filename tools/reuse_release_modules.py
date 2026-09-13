"""Reuse native modules from a matching-platform build artifact for frontend updates."""
import argparse
from pathlib import Path
import shutil
import sys
import tarfile
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory',type=Path,required=True)
args=parser.parse_args()
archives=list(args.directory.glob('*.tar.gz'))+list(args.directory.glob('*.zip'))
if len(archives)!=1:raise SystemExit('Expected one platform archive')
mac=sys.platform=='darwin';suffix='.dylib' if mac else '.so'
prefix='SpaceChannel5/SpaceChannel5.app/Contents/MacOS/build/' if mac else 'SpaceChannel5/build/'
output=Path('build');output.mkdir(exist_ok=True)
archive=zipfile.ZipFile(archives[0]) if mac else tarfile.open(archives[0])
with archive:
    for number in range(1,5):
        name=f'native-diff-round{number}{suffix}'
        if mac:
            info=archive.getinfo(prefix+name)
            if info.file_size>200_000_000:raise RuntimeError('Unexpected module size')
            data=archive.read(info)
        else:
            info=archive.getmember(prefix+name)
            if not info.isfile() or info.size>200_000_000:raise RuntimeError('Unexpected module entry')
            with archive.extractfile(info) as handle:data=handle.read()
        (output/name).write_bytes(data)
shutil.copy2(output/f'native-diff-round1{suffix}',output/f'native-diff{suffix}')
