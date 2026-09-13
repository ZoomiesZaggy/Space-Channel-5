"""Run the native regression suite for every module and a fresh, isolated boot."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
from build_paths import ROOT, WORK, compiler

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gdi', required=True, type=pathlib.Path)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items() if not k.startswith('SC5_')}
    env['PATH'] = str(compiler().parent) + os.pathsep + env['PATH']
    env.update(SC5_GDI=str(args.gdi.resolve()), SC5_IMAGE=str(ROOT / 'extracted/1ST_READ.BIN'), SC5_IGNORE_SETTINGS='1')
    results = []
    report = ROOT / 'reports/build-validation.json'
    (WORK / 'validation').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK / 'validation') as temporary:
        assert pathlib.Path(temporary).resolve().is_relative_to(WORK.resolve())
        env['SC5_RUNTIME_DATA'] = temporary + '/'
        for number in range(1, 5):
            dll = ROOT / f'build/native-diff-round{number}.dll'
            env['SC5_NATIVE_DLL'] = str(dll)
            test = WORK / 'flycast-build/flycast.exe'
            command = [str(test), '--gtest_filter=Sc5NativeDifferential.*-Sc5NativeDifferential.NativeExecutionUsesDeviceBus:Sc5NativeDifferential.OfflineReferenceCoverageOnly']
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
            log = result.stdout + result.stderr
            (ROOT / f'reports/build-round{number}-tests.txt').write_text(log)
            passed = re.search(r'\[  PASSED  \] (\d+) tests?', log)
            skipped = re.search(r'\[  SKIPPED \] (\d+) tests?', log)
            if result.returncode or not passed: raise RuntimeError(log)
            item = dict(round=number, passed=int(passed[1]), skipped=int(skipped[1]) if skipped else 0, dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest())
            results.append(item); print(item, flush=True)
        exe = ROOT / 'build/sc5-native-dev.exe'
        command = [str(exe), '--gdi', str(args.gdi.resolve()), '--data', temporary, '--hidden', '--silent', '--budget', '1000000000']
        # Fresh boot starts in the round 1 module regardless of the previous test.
        env['SC5_NATIVE_DLL'] = str(ROOT / 'build/native-diff-round1.dll')
        env['SC5_MODULE_DLL_DIR'] = str(ROOT / 'build')
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        (ROOT / 'reports/build-fresh-boot.txt').write_text(result.stdout + result.stderr)
        if result.returncode: raise RuntimeError(result.stdout + result.stderr)
        report.write_text(json.dumps(dict(modules=results, fresh_boot_exit=0, fresh_boot_budget=1000000000, frontend_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), scope='Synthetic regression tests and bounded fresh boot; no physical latency or complete manual playthrough claim.'), indent=2) + '\n')
    print('Validation passed:', report)

if __name__ == '__main__': main()
