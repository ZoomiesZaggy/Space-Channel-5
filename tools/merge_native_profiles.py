"""Merge native execution counts into a reproducible, path-free LLVM profile."""
import argparse
import gzip
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profiles',nargs='+',type=Path)
    parser.add_argument('--llvm-profdata',default='llvm-profdata')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        text_path=Path(temporary)/'counts.txt'
        subprocess.run([args.llvm_profdata,'merge','--text',*[str(p.resolve()) for p in args.profiles],'-o',str(text_path)],check=True)
        text=text_path.read_text()
        # Older instrumentation used absolute C filenames for internal helpers.
        # New builds compile with relative names so these keys travel with the source.
        text=re.sub(r'(?m)^[^\r\n;]*[/\\]((?:core|pages_[0-9a-f]+)\.c;)',r'\1',text)
        if re.search(r'(?m)^[^\r\n;]*[/\\][^\r\n;]*\.c;',text):
            raise ValueError('Profile has an unexpected source path; inspect before publishing')
        text_path.write_text(text)
        binary=Path(temporary)/'counts.profdata'
        subprocess.run([args.llvm_profdata,'merge',str(text_path),'-o',str(binary)],check=True)
        data=binary.read_bytes()
        if len(data)>64*1024*1024:raise ValueError('Profile exceeds the build reader limit')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
        print('Uncompressed SHA256:',hashlib.sha256(data).hexdigest())
        print('Compressed profile:',args.output)

if __name__=='__main__':main()
