"""Asset-free checks of native host environment, clocks and atomic replacement."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from build_paths import ROOT, WORK, compiler

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler')
    args = parser.parse_args()
    if args.compiler or os.name != 'nt':
        selected = shutil.which(args.compiler or 'c++')
        if not selected:
            raise SystemExit('C++ compiler not found')
        cxx = Path(selected)
    else:
        cxx = compiler(True)
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='host-os-', dir=WORK) as temporary:
        destination = Path(temporary) / ('contracts.exe' if os.name == 'nt' else 'contracts')
        environment = dict(os.environ, PATH=str(cxx.parent) + os.pathsep + os.environ.get('PATH', ''))
        flags = ['-static'] if os.name == 'nt' else []
        subprocess.run([str(cxx), '-std=c++17', '-O2', '-frounding-math', *flags,
                        str(ROOT / 'tools/test_native_host_os.cpp'), '-o', str(destination)],
                       env=environment, check=True)
        subprocess.run([str(destination), temporary], env=environment, check=True)
