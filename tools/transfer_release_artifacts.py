"""Transfer this performance update's validated platform artifacts to its draft."""
from pathlib import Path, PurePosixPath
import hashlib, json, os, posixpath, stat, subprocess, tarfile, zipfile

def api(path):
    return json.loads(subprocess.check_output(['gh','api','repos/ZoomiesZaggy/Space-Channel-5'+path]))

def verify(path):
    is_zip=path.suffix=='.zip'
    hashes={};links={};manifest=None;root='SpaceChannel5/'
    def check_name(name):
        parts=PurePosixPath(name).parts
        assert not PurePosixPath(name).is_absolute() and '..' not in parts,name
        assert not {'userdata','extracted'}.intersection(parts),name
    def hash_file(name,handle):
        nonlocal manifest
        digest=hashlib.sha256()
        if name==root+'release-manifest.json':
            data=handle.read(1024*1024)
            assert not handle.read(1),'Oversized file manifest'
            manifest=json.loads(data);digest.update(data)
        else:
            for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
        hashes[name]=digest.hexdigest()
    if is_zip:
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                name=item.filename;check_name(name)
                if stat.S_ISLNK(item.external_attr>>16):
                    links[name]=posixpath.normpath(posixpath.join(posixpath.dirname(name),archive.read(item).decode()))
                elif not item.is_dir():
                    with archive.open(item) as handle:hash_file(name,handle)
    else:
        with tarfile.open(path,mode='r|gz') as archive:
            for item in archive:
                name=item.name;check_name(name)
                if item.issym():links[name]=posixpath.normpath(posixpath.join(posixpath.dirname(name),item.linkname))
                elif item.islnk():links[name]=item.linkname
                elif item.isfile():
                    with archive.extractfile(item) as handle:hash_file(name,handle)
    assert manifest is not None
    def resolve(name):
        for _ in range(20):
            assert name.startswith(root),name
            if name in hashes:return hashes[name]
            parts=name.split('/')
            for index in range(len(parts),0,-1):
                prefix='/'.join(parts[:index])
                if prefix in links:
                    name=posixpath.normpath(posixpath.join(links[prefix],*parts[index:]));break
            else:raise ValueError('Missing packaged file: '+name)
        raise ValueError('Symlink loop: '+name)
    for name,digest in manifest.items():
        assert resolve(root+name)==digest,name
    suffix='.dylib' if 'macOS' in path.name else '.so'
    assert all(any(name.endswith('/native-diff-round'+str(i)+suffix) for name in manifest) for i in range(1,5))
    print('Verified',path.name,len(manifest),'file hashes',flush=True)
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

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
