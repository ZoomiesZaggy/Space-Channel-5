"""Fetch the pinned portable toolchain with an independently pinned SHA-256."""
import hashlib
import pathlib
import tempfile
import urllib.request
import zipfile
from build_paths import WORK

NAME = 'llvm-mingw-20260908-ucrt-x86_64'
SHA256 = '1bcf74d06b724aeecaa6412ca85f5b26fb1da770e7cdcefa9263c9c5c3ad34b6'
URL = f'https://github.com/mstorsjo/llvm-mingw/releases/download/20260908/{NAME}.zip'

def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''): sha.update(chunk)
    return sha.hexdigest()

def ensure_toolchain():
    directory = (WORK / 'toolchain').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / NAME
    if (target / 'bin/clang.exe').is_file() and (target / '.verified-archive-sha256').is_file():
        if (target / '.verified-archive-sha256').read_text().strip() == SHA256: return target
    if target.exists():
        raise RuntimeError('Existing toolchain is not marked verified. Select it explicitly with --toolchain, or use a different SC5_WORK_DIR.')
    archive = directory / (NAME + '.zip')
    if not archive.is_file() or digest(archive) != SHA256:
        print('Downloading pinned LLVM-MinGW (about 191 MB)…', flush=True)
        partial = archive.with_suffix('.part')
        with urllib.request.urlopen(URL, timeout=60) as source, partial.open('wb') as output:
            while chunk := source.read(1024 * 1024): output.write(chunk)
        if digest(partial) != SHA256: raise RuntimeError('Toolchain checksum mismatch; archive was not extracted.')
        partial.replace(archive)
    with tempfile.TemporaryDirectory(prefix='extract-', dir=directory) as temporary:
        stage = pathlib.Path(temporary).resolve()
        assert stage.is_relative_to(directory)
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if not (stage / member.filename).resolve().is_relative_to(stage):
                    raise RuntimeError('Unsafe archive path')
            source.extractall(stage)
        extracted = (stage / NAME).resolve()
        assert extracted.is_relative_to(directory) and target.resolve().is_relative_to(directory)
        if not (extracted / 'bin/clang.exe').is_file(): raise RuntimeError('Compiler missing from archive')
        (extracted / '.verified-archive-sha256').write_text(SHA256 + '\n')
        extracted.rename(target)
    return target

if __name__ == '__main__': print(ensure_toolchain())
