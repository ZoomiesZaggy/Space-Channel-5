"""Compile and run asset-free calibration contracts with the local build toolchain."""
import os
import argparse
import shutil
import subprocess
from build_paths import ROOT, WORK, compiler

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', help='C++ compiler path or command; useful for asset-free Linux/macOS checks')
    args = parser.parse_args()
    if args.compiler or os.name != 'nt':
        from pathlib import Path
        selected = shutil.which(args.compiler or 'c++')
        if not selected: raise SystemExit('C++ compiler not found')
        cxx = Path(selected)
    else:
        cxx = compiler(True)
    WORK.mkdir(parents=True, exist_ok=True)
    destination = WORK / ('calibration-contracts.exe' if os.name == 'nt' else 'calibration-contracts')
    environment = dict(os.environ, PATH=str(cxx.parent) + os.pathsep + os.environ.get('PATH', ''))
    flags = ['-static'] if os.name == 'nt' else []
    subprocess.run([str(cxx), '-std=c++17', '-O2', *flags, str(ROOT / 'tools/test_native_calibration.cpp'), '-o', str(destination)], env=environment, check=True)
    subprocess.run([str(destination)], env=environment, check=True)
