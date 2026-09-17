"""Transfer this performance update's validated platform artifacts to its draft."""
from pathlib import Path, PurePosixPath
import hashlib, json, os, posixpath, stat, subprocess, tarfile, zipfile

def api(path):
    return json.loads(subprocess.check_output(['gh','api','repos/ZoomiesZaggy/Space-Channel-5'+path]))

def verify(path):
    is_zip=path.suffix=='.zip'
    archive=zipfile.ZipFile(path) if is_zip else tarfile.open(path)
    with archive:
        entries={item.filename if is_zip else item.name:item for item in (archive.infolist() if is_zip else archive.getmembers())}
        for name in entries:
            parts=PurePosixPath(name).parts
            assert not PurePosixPath(name).is_absolute() and '..' not in parts, name
            assert not {'userdata','extracted'}.intersection(parts), name
        manifests=[name for name in entries if name.endswith('/release-manifest.json')]
        assert manifests==['SpaceChannel5/release-manifest.json'],manifests
        root='SpaceChannel5/'
        def read(name,depth=0):
            assert depth<20 and name.startswith(root),name
            item=entries[name]
            if is_zip:
                data=archive.read(item)
                if stat.S_ISLNK(item.external_attr>>16):
                    return read(posixpath.normpath(posixpath.join(posixpath.dirname(name),data.decode())),depth+1)
                return data
            if item.issym():
                return read(posixpath.normpath(posixpath.join(posixpath.dirname(name),item.linkname)),depth+1)
            if item.islnk():
                return read(item.linkname,depth+1)
            assert item.isfile(),name
            return archive.extractfile(item).read()
        manifest=json.loads(read(manifests[0]))
        for name,digest in manifest.items():
            assert hashlib.sha256(read(root+name)).hexdigest()==digest,name
        module_extension='.dylib' if 'macOS' in path.name else '.so'
        assert all(any(name.endswith('/native-diff-round'+str(i)+module_extension) for name in manifest) for i in range(1,5))
        print('Verified',path.name,len(manifest),'file hashes',flush=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()

run_id=os.environ['BUILD_RUN_ID']
assert run_id.isdecimal()
run=api('/actions/runs/'+run_id)
assert run['head_sha']=='a10c189b0f4095d6c88a24fb2e60ce8a9a34316f'
assert run['conclusion']=='success'
release=next(r for r in api('/releases?per_page=30') if r['tag_name']=='v0.1.0-preview.2')
assert release['draft'], 'Only the unpublished draft may receive these packages'
expected={'SpaceChannel5-Linux-X64.tar.gz','SpaceChannel5-Linux-ARM64.tar.gz','SpaceChannel5-macOS-X64.zip','SpaceChannel5-macOS-ARM64.zip'}
packages=[p for p in Path('artifacts').rglob('*') if p.is_file()]
assert len(packages)==4 and {p.name for p in packages}==expected
stage=Path('validated');stage.mkdir(exist_ok=True)
for package in packages:
    digest='sha256:'+verify(package)
    destination=stage/package.name.replace('SpaceChannel5-','SpaceChannel5-v0.1.0-preview.2-',1)
    package.rename(destination)
    current=api('/releases/'+str(release['id']))
    assert current['draft']
    existing=next((a for a in current['assets'] if a['name']==destination.name),None)
    if existing:
        assert existing.get('digest')==digest
    else:
        subprocess.run(['gh','release','upload',release['tag_name'],str(destination)],check=True)
    asset=next(a for a in api('/releases/'+str(release['id']))['assets'] if a['name']==destination.name)
    assert asset['digest']==digest and asset['size']==destination.stat().st_size
    print('Uploaded and verified',destination.name,digest,flush=True)
