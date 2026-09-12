"""Link the standalone native host against the pinned, locally built device objects.

No Google Test objects or reference CPU comparison fixture enter this executable.
The reusable device library still contains upstream CPU implementations; the
native host's execution path exclusively calls sc5_run_chunk from its AOT DLL.
"""
import argparse,ctypes,json,os,pathlib,subprocess,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];WORK=ROOT/'work';BUILD=WORK/'flycast-build'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=pathlib.Path,default=ROOT/'build/sc5-native-dev.exe',help='Optional staged executable path for rebuilding while the game is running')
args=parser.parse_args()
compiler=next((WORK/'toolchain').glob('*/bin/clang++.exe')).resolve()
env=os.environ.copy();env['PATH']=str(compiler.parent)+os.pathsep+env['PATH']
database=json.loads(subprocess.check_output([str(WORK/'build-tools/bin/ninja.exe'),'-C',str(BUILD),'-t','compdb','-x'],text=True))
shell=ctypes.windll.shell32;shell.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)];shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
kernel=ctypes.windll.kernel32;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
def argv(command):
    count=ctypes.c_int();pointer=shell.CommandLineToArgvW(command,ctypes.byref(count))
    if not pointer:raise OSError('Cannot parse compiler command')
    try:return [pointer[j] for j in range(count.value)]
    finally:kernel.LocalFree(pointer)
compile_entry=next(x for x in database if x['file'].endswith('Sc5NativeDifferentialTest.cpp'))
original=argv(compile_entry['command']);flags=[];skip=False
for item in original[1:]:
    if skip:skip=False;continue
    if item in ('-o','-c','-MT','-MF'):skip=True;continue
    if item=='-MD' or item.startswith('-DFLYCAST_TEST_FILES'):continue
    flags.append(item)
logs=[];objects=[]
def run(command):
    result=subprocess.run(command,cwd=BUILD,env=env,capture_output=True,text=True)
    logs.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    (ROOT/'reports/native-app-build.json').write_text(json.dumps(logs,indent=2))
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
for name in ('native_app_main','native_platform'):
    output=ROOT/'build'/f'{name}.obj';objects.append(str(output))
    run([str(compiler),*flags,'-c',str(ROOT/'tools'/f'{name}.cpp'),'-o',str(output)])
link_entry=next(x for x in database if x.get('output')=='flycast.exe')
segments=link_entry['command'].split(' && ');assert len(segments)==3 and 'clang++.exe' in segments[1]
original=argv(segments[1]);link=[];skip=False
for item in original[1:]:
    if skip:skip=False;continue
    if item=='-o':skip=True;continue
    normalized=item.replace('\\','/').lower()
    if normalized.endswith('.obj') and ('/tests/' in normalized or 'sc5nativedifferentialtest.cpp.obj' in normalized):continue
    if 'gtest' in normalized or item.startswith('-Wl,-Map=') or item.startswith('-Wl,--out-implib,'):continue
    link.append(item)
assert not any('/tests/' in x.replace('\\','/').lower() or 'sc5nativedifferentialtest' in x.lower() or 'gtest' in x.lower() for x in link)
output=args.output.resolve()
output.parent.mkdir(parents=True,exist_ok=True)
run([str(compiler),*objects,*link,'-Wl,-Map='+str(output.with_suffix('.map')),'-o',str(output)])
runtime_source=compiler.parent/'libwinpthread-1.dll'
runtime_target=output.parent/'libwinpthread-1.dll'
if not runtime_target.exists() or runtime_target.read_bytes()!=runtime_source.read_bytes():
    shutil.copy2(runtime_source,runtime_target)
licenses=ROOT/'licenses';licenses.mkdir(exist_ok=True)
shutil.copy2(compiler.parent.parent/'x86_64-w64-mingw32/share/mingw32/COPYING.winpthreads.txt',licenses/'COPYING.winpthreads.txt')
run([str(output),'--help'])
print(f'Standalone native development host built: {output}')
