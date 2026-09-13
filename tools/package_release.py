"""Package a prebuilt host, native modules and frozen disc-import launcher.

No original disc files, extracted game executables or personal data are copied.
The release includes translated native modules and requires the player's disc.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from build_paths import ROOT, WORK

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-dir', type=Path, required=True)
    parser.add_argument('--module-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Choose a new release output directory')
    suffix = '.dll' if os.name == 'nt' else '.dylib' if sys.platform == 'darwin' else '.so'
    executable = 'sc5-native-dev.exe' if os.name == 'nt' else 'sc5-native-dev'
    modules = [args.module_dir / f'native-diff-round{i}{suffix}' for i in range(1, 5)]
    for file in [args.host_dir / executable, *modules]:
        if not file.is_file():
            raise SystemExit('Missing release input: ' + str(file))
    stage = WORK / 'release-freeze'
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                    '--windowed', '--name', 'SpaceChannel5', '--distpath', str(stage / 'dist'),
                    '--workpath', str(stage / 'build'), '--specpath', str(stage),
                    str(ROOT / 'tools/launcher.py')], check=True)
    shutil.copytree(stage / 'dist/SpaceChannel5', output)
    binary = output / 'build'
    binary.mkdir()
    shutil.copy2(args.host_dir / executable, binary / executable)
    for module in modules:
        shutil.copy2(module, binary / module.name)
    shutil.copy2(modules[0], binary / ('native-diff' + suffix))
    if os.name == 'nt':
        shutil.copy2(args.host_dir / 'libwinpthread-1.dll', binary / 'libwinpthread-1.dll')
    shutil.copy2(ROOT / 'LICENSE', output / 'LICENSE')
    shutil.copytree(ROOT / 'licenses', output / 'licenses')
    (output / 'README.txt').write_text(
        'Space Channel 5 native port\n\n'
        'Run SpaceChannel5, select your original USA GDI, then Play.\n'
        'Keep the GDI and all its track files together. The disc remains read-only.\n'
        'No Python, Git or compiler installation is required.\n'
        'The release contains translated native code, but no original game assets.\n'
        'Imported files and saves are created locally. Keep userdata when updating.\n'
        'Source and validation: https://github.com/ZoomiesZaggy/Space-Channel-5\n', encoding='utf-8')
    files = {file.relative_to(output).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
             for file in output.rglob('*') if file.is_file()}
    (output / 'release-manifest.json').write_text(json.dumps(files, indent=2))
    print('Release directory:', output)

if __name__ == '__main__':
    main()
