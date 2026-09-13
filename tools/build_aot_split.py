"""Build the same generated AOT program in cached address-range objects.

No instruction discovery or runtime translation occurs here. The emitted page
bodies are copied verbatim, apart from external linkage between object files.
"""
import argparse, concurrent.futures, hashlib, json, pathlib, re, subprocess, time
from boot_probe import ROOT, RUNTIME

def build(cc, output, jobs=4, opt='1', source_path=None, object_dir=None, cpu=None, math_errno=True):
    started=time.monotonic(); cc=str(pathlib.Path(cc).resolve())
    source_file=pathlib.Path(source_path) if source_path else ROOT/'build/sc5-boot-probe.c'
    source=source_file.read_text()
    assert source.startswith(RUNTIME)
    directory=ROOT/'build'/(object_dir or 'aot-objects'); directory.mkdir(exist_ok=True)
    declarations=[
        'State s', 'unsigned char internal_ram[0x1000000]',
        'unsigned char *ram=internal_ram', 'BusRead external_read',
        'BusWrite external_write', 'Retire external_retire',
        'Service external_service', 'QueueWrite external_queue_write __attribute__((unused))',
        'NativeFastClock *external_clock',
        'u32 deferred_code_guard',
        'u32 fault_address,ccr,model_ccr,steps,cable=3,host_services,intc[4]',
    ]
    common=RUNTIME
    definitions=[]
    for declaration in declarations:
        original='static '+declaration+';'; assert original in common, original
        external=re.sub(r'=[^,;]+','',declaration)
        common=common.replace(original,'extern '+external+';')
        definitions.append(declaration+';')
    common=common.replace('static int translated(u32 physical);','int translated(u32 physical);')
    common=common.replace('../tools/',(ROOT/'tools').as_posix()+'/')
    header='#pragma once\n'+common
    (directory/'native-shared.h').write_text(header)
    pages=list(re.finditer(r'^static int page_([0-9a-f]+).*?(?=^static int page_|^static void run)',source,re.M|re.S))
    assert pages
    groups={}
    for page in pages:
        group=int(page[1],16)>>6
        groups.setdefault(group,[]).append(page[0].replace('static int page_','int page_',1))
    prototypes='\n'.join('int page_'+p[1]+'(u32 budget);' for p in pages)
    prefix=source[len(RUNTIME):pages[0].start()].replace('static int translated(', 'int translated(')
    suffix=source[pages[-1].end():]
    exports=(ROOT/'tools/native_diff_exports.c').read_text()
    assert '#include "sc5-boot-probe.c"' in exports
    core='#include "native-shared.h"\n'+'\n'.join(definitions)+'\n'+prefix+prototypes+'\n'+suffix
    units={'core':exports.replace('#include "sc5-boot-probe.c"',core)}
    units.update({f'pages_{group:x}':'#include "native-shared.h"\n'+''.join(bodies) for group,bodies in groups.items()})
    identity=subprocess.check_output([cc,'--version'],text=True)
    dependency_hash=hashlib.sha256((ROOT/'tools/native_state.h').read_bytes()+(ROOT/'tools/native_fsca_table.inc').read_bytes()+(ROOT/'tools/native_fast_clock.h').read_bytes()+(ROOT/'tools/native_static_timing.h').read_bytes()).hexdigest()
    def compile_unit(item):
        name,body=item; path=directory/(name+'.c'); obj=directory/(name+'.obj'); stamp=directory/(name+'.sha256')
        digest=hashlib.sha256((identity+opt+str(cpu)+str(math_errno)+dependency_hash+header+body).encode()).hexdigest()
        if obj.exists() and stamp.exists() and stamp.read_text()==digest:return str(obj),False
        path.write_text(body)
        command=[cc,'-O'+opt,'-std=c99','-c',str(path),'-o',str(obj)]
        if cpu:command+=['-march='+cpu]
        if not math_errno:command+=['-fno-math-errno']
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        stamp.write_text(digest);print(f'Compiled {name}',flush=True);return str(obj),True
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        results=list(pool.map(compile_unit,units.items()))
    command=[cc,'-shared',*[obj for obj,changed in results],'-o',str(pathlib.Path(output).resolve())]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report=dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),pages=len(pages),objects=len(results),compiled_objects=sum(changed for obj,changed in results),seconds=time.monotonic()-started,cpu=cpu,math_errno=math_errno,command=command)
    (ROOT/'reports/native-split-build.json').write_text(json.dumps(report,indent=2))
    print({k:v for k,v in report.items() if k!='command'},flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cc',required=True);parser.add_argument('--output',required=True);parser.add_argument('--jobs',type=int,default=4);parser.add_argument('--opt',choices=['0','1','2'],default='1');parser.add_argument('--source');parser.add_argument('--object-dir')
    parser.add_argument('--cpu',choices=['x86-64','x86-64-v3']);parser.add_argument('--no-math-errno',action='store_true')
    args=parser.parse_args();build(args.cc,args.output,args.jobs,args.opt,args.source,args.object_dir,args.cpu,not args.no_math_errno)
