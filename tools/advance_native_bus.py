"""Expand AOT coverage with the reference device bus; never executes its CPU."""
import argparse,json,os,pathlib,re,subprocess,time
from boot_probe import ROOT,BASE,RELOCATIONS,CODE_MODULES,generate
ap=argparse.ArgumentParser();ap.add_argument('--cc',required=True);ap.add_argument('--reference',required=True);ap.add_argument('--limit',type=int,default=20);ap.add_argument('--opt',choices=['0','1','2'],default='1');ap.add_argument('--timeout',type=int,default=60);ap.add_argument('--split',action='store_true');a=ap.parse_args()
cc=str(pathlib.Path(a.cc).resolve());reference=str(pathlib.Path(a.reference).resolve());blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
records_path=ROOT/'reports/observed-roots.json';records=json.loads(records_path.read_text())
history_path=ROOT/'reports/native-bus-expansion.json';history=json.loads(history_path.read_text()) if history_path.exists() else []
env=os.environ.copy();env['PATH']=str(pathlib.Path(cc).parent)+os.pathsep+env['PATH'];env['SC5_NATIVE_DLL']=str(ROOT/'build/native-diff.dll');env['SC5_IMAGE']=str(ROOT/'extracted/1ST_READ.BIN')
for iteration in range(a.limit):
    source,report=generate(blob,[int(x['pc'],16) for x in records]);(ROOT/'build/sc5-boot-probe.c').write_text(source);(ROOT/'reports/boot-analysis.json').write_text(json.dumps(report,indent=2))
    command=[cc,'-O'+a.opt,'-std=c99','-shared','-I',str(ROOT/'build'),str(ROOT/'tools/native_diff_exports.c'),'-o',str(ROOT/'build/native-diff.dll')]
    print(f'Compiling {report["instructions"]} discovered instructions (-O{a.opt})',flush=True);build_start=time.monotonic()
    if a.split:
        from build_aot_split import build as split_build
        command=split_build(cc,ROOT/'build/native-diff.dll',opt=a.opt)['command']
    else:
        build=subprocess.run(command,capture_output=True,text=True);assert build.returncode==0,build.stdout+build.stderr
    build_seconds=time.monotonic()-build_start;print(f'Build finished in {build_seconds:.1f}s; starting native device run',flush=True);run_start=time.monotonic()
    try:
        run=subprocess.run([reference,'--gtest_filter=Sc5NativeDifferential.NativeExecutionUsesDeviceBus'],env=env,capture_output=True,text=True,timeout=a.timeout)
    except subprocess.TimeoutExpired as error:
        def output(value):return value.decode(errors='replace') if isinstance(value,bytes) else (value or '')
        (ROOT/'reports/native-bus-failure.json').write_text(json.dumps(dict(command=command,timeout_seconds=a.timeout,stdout=output(error.stdout),stderr=output(error.stderr)),indent=2))
        raise RuntimeError(f'Native run exceeded {a.timeout} seconds; partial output retained') from error
    m=re.search(r'Native bus halt PC=([a-f0-9]+) fault=([a-f0-9]+) retired=(\d+) reads=(\d+) writes=(\d+)',run.stdout)
    if not m:
        (ROOT/'reports/native-bus-failure.json').write_text(json.dumps(dict(command=command,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2))
        raise RuntimeError(run.stdout+run.stderr)
    pc,fault,retired=int(m[1],16),int(m[2],16),int(m[3]);print(f'{iteration}: coverage={report["instructions"]} pc={pc:08x} fault={fault} retired={retired} bus writes={m[5]}',flush=True)
    history.append(dict(command=command,build_seconds=build_seconds,run_seconds=time.monotonic()-run_start,reference_returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,roots=report['roots']));history_path.write_text(json.dumps(history,indent=2))
    original_pc=pc;pc=(pc&0x1fffffff)|0x80000000
    known_range=BASE<=pc<BASE+len(blob)-1 or any(dest<=pc<dest+size-1 for dest,source,size in RELOCATIONS) or any(base<=pc<base+size-1 for name,base,size,sha in CODE_MODULES)
    if run.returncode or fault!=2 or pc%2 or not known_range:break
    assert pc not in [int(x['pc'],16) for x in records]
    records.append(dict(pc=f'{pc:08x}',guest_alias=f'{original_pc:08x}',evidence='Native AOT with reference device bus reached PC; reference CPU not executed',retired=retired,image_sha256=report['image_sha256']));records_path.write_text(json.dumps(records,indent=2))
