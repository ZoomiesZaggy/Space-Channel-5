"""Reproduce the pinned, patched Windows reference test build in work/."""
import json,pathlib,subprocess,sys,os
ROOT=pathlib.Path(__file__).resolve().parents[1];WORK=ROOT/'work'
SOURCE=WORK/'flycast-reference';BUILD=WORK/'flycast-build'
REV='eddf2635867f0f16f64bebd3185db151c99c551c'
logs=[]
def run(command,env=None):
    p=subprocess.run([str(x) for x in command],env=env,capture_output=True,text=True)
    logs.append(dict(command=[str(x) for x in command],returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    (ROOT/'reports/reference-setup-log.json').write_text(json.dumps(logs,indent=2))
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout
if not SOURCE.exists():
    run(['git','clone','--no-checkout','https://github.com/flyinghead/flycast.git',SOURCE])
    run(['git','-C',SOURCE,'checkout',REV])
assert run(['git','-C',SOURCE,'rev-parse','HEAD']).strip()==REV,'Reference checkout is not the pinned revision'
deps=['SDL','libchdr','googletest','asio','xbyak','libjuice','websocketpp','tinygettext','rcheevos','DreamPicoPort-API','freetype']
run(['git','-C',SOURCE,'submodule','update','--init','--depth','1',*['core/deps/'+x for x in deps]])
for dep in ['tinygettext','DreamPicoPort-API']:
    run(['git','-C',SOURCE/'core/deps'/dep,'submodule','update','--init','--recursive','--depth','1'])
patch=ROOT/'reports/flycast-reference.patch'
already=subprocess.run(['git','-C',str(SOURCE),'apply','--reverse','--check',str(patch)],capture_output=True).returncode==0
if not already:run(['git','-C',SOURCE,'apply',patch])
cmake=WORK/'build-tools/cmake/data/bin/cmake.exe';ninja=WORK/'build-tools/bin/ninja.exe'
if not cmake.exists() or not ninja.exists():run([sys.executable,'-m','pip','install','--target',WORK/'build-tools','cmake==4.4.3','ninja==1.13.2'])
compiler=next((WORK/'toolchain').glob('*/bin/clang.exe'));env=os.environ.copy();env['PATH']=str(compiler.parent)+os.pathsep+str(ninja.parent)+os.pathsep+env['PATH']
run([cmake,'-S',SOURCE,'-B',BUILD,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_C_COMPILER={compiler}',f'-DCMAKE_CXX_COMPILER={compiler.parent/"clang++.exe"}',f'-DSC5_NATIVE_TEST_SOURCE={ROOT/"tools/Sc5NativeDifferentialTest.cpp"}','-DENABLE_CTEST=ON','-DUSE_VULKAN=OFF','-DUSE_DX9=OFF','-DUSE_DX11=OFF','-DUSE_BREAKPAD=OFF','-DUSE_LUA=OFF','-DUSE_OPENMP=OFF','-DUSE_HOST_SDL=OFF','-DUSE_HOST_LIBZIP=OFF','-DCMAKE_POLICY_VERSION_MINIMUM=3.5'],env)
run([cmake,'--build',BUILD,'--parallel','6'],env)
print('Reference test build ready. This is not the playable native port.')
