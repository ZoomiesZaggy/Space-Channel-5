"""Build a personal copy from an original USA GDI; no game data is downloaded."""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main():
    from build_paths import keep_awake
    keep_awake()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gdi', type=pathlib.Path, required=True)
    parser.add_argument('--toolchain', type=pathlib.Path, help='Existing LLVM-MinGW directory; omitted downloads the pinned portable toolchain')
    args = parser.parse_args()
    gdi = args.gdi.resolve()
    if not gdi.is_file() or gdi.suffix.lower() != '.gdi':
        parser.error('Select an existing GDI file.')
    if not shutil.which('git'):
        parser.error('Git must be installed and available on PATH.')
    if args.toolchain:
        toolchain = args.toolchain.resolve()
    else:
        from toolchain_setup import ensure_toolchain
        toolchain = ensure_toolchain()
    if not (toolchain / 'bin/clang.exe').is_file():
        parser.error('The toolchain directory must contain bin/clang.exe.')
    env = os.environ.copy()
    env.update(SC5_GDI=str(gdi), SC5_TOOLCHAIN=str(toolchain))
    (ROOT / 'build').mkdir(exist_ok=True)
    def run(*command):
        print('Running: ' + ' '.join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True)
    run(sys.executable, 'tools/inspect_disc.py', gdi, '--out', ROOT)
    run(sys.executable, 'tools/inspect_assets.py')
    run(sys.executable, 'tools/setup_reference.py')
    work = pathlib.Path(env.get('SC5_WORK_DIR', ROOT / 'work'))
    run(sys.executable, 'tools/generate_static_timing.py', '--reference', work / 'flycast-reference')
    run(sys.executable, 'tools/build_round_aot.py', '--cc', toolchain / 'bin/clang.exe', '--opt', '2', '--round', '1', '--round', '2', '--round', '3', '--round', '4')
    shutil.copy2(ROOT / 'build/native-diff-round1.dll', ROOT / 'build/native-diff.dll')
    run(sys.executable, 'tools/build_native_app.py')
    print('Build complete. Open the launcher to configure and play.', flush=True)

if __name__ == '__main__':
    main()
