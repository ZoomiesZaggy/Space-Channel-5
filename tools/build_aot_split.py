"""Build the same generated AOT program in cached address-range objects.

No instruction discovery or runtime translation occurs here. Shared-state
linkage and clock setup are optimized; instruction bodies and guards remain.
"""
import argparse, concurrent.futures, gzip, hashlib, json, pathlib, re, subprocess, time, shutil
from boot_probe import ROOT, RUNTIME

def build(cc, output, jobs=4, opt='1', source_path=None, object_dir=None, cpu=None, math_errno=True, profile_generate=False, profile_use=None):
    started=time.monotonic(); cc=str(pathlib.Path(shutil.which(str(cc)) or cc).resolve())
    target=subprocess.check_output([cc,"-dumpmachine"],text=True).strip()
    windows=any(word in target for word in ("mingw", "windows"))
    darwin="darwin" in target
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
        # COFF extern data otherwise goes through .refptr on every instruction.
        # COMDAT data definitions still coalesce to one state per loaded module.
        if windows:
            common=common.replace(original,'__declspec(selectany) '+declaration+';')
        else:
            common=common.replace(original,'extern __attribute__((visibility("hidden"))) '+external+';')
            definitions.append('__attribute__((visibility("hidden"))) '+declaration+';')
    # The host configures callbacks between chunks. Keep the initialized clock
    # in a page-local pointer, instead of reloading and checking three globals
    # for every guest instruction. The startup/no-clock path is unchanged.
    retire=common[common.index('static inline __attribute__((always_inline)) void native_retire'):common.index('\ntypedef int (*Service)')]
    page_retire=retire.replace('void native_retire(u32 opcode,u32 slot,u32 count)', 'void native_page_retire(NativeFastClock *clock,u32 opcode,u32 slot,u32 count)')
    page_retire=page_retire.replace(' if(!external_retire)return;\n NativeFastClock *clock=external_clock;\n if(!clock || clock->initial_mem_ops<3){external_retire(opcode,slot,count);return;}', ' if(!clock){native_retire(opcode,slot,count);return;}')
    assert page_retire != retire and 'clock->initial_mem_ops' not in page_retire
    common += '\n'+page_retire
    common=common.replace('static int translated(u32 physical);','int translated(u32 physical);')
    common=common.replace('../tools/',(ROOT/'tools').as_posix()+'/')
    header='#pragma once\n'+common
    (directory/'native-shared.h').write_text(header)
    pages=list(re.finditer(r'^static int page_([0-9a-f]+).*?(?=^static int page_|^static void run)',source,re.M|re.S))
    assert pages
    groups={}
    for page in pages:
        group=int(page[1],16)>>6
        body=page[0].replace('static int page_','int page_',1)
        body=body.replace('(u32 budget){', '(u32 budget){NativeFastClock *const page_clock=(external_retire && external_clock && external_clock->initial_mem_ops>=3)?external_clock:0;',1)
        body=body.replace('native_retire(', 'native_page_retire(page_clock,')
        groups.setdefault(group,[]).append(body)
    prototypes='\n'.join('int page_'+p[1]+'(u32 budget);' for p in pages)
    prefix=source[len(RUNTIME):pages[0].start()].replace('static int translated(', 'int translated(')
    suffix=source[pages[-1].end():]
    exports=(ROOT/'tools/native_diff_exports.c').read_text()
    assert '#include "sc5-boot-probe.c"' in exports
    core='#include "native-shared.h"\n'+'\n'.join(definitions)+'\n'+prefix+prototypes+'\n'+suffix
    units={'core':exports.replace('#include "sc5-boot-probe.c"',core)}
    units.update({f'pages_{group:x}':'#include "native-shared.h"\n'+''.join(bodies) for group,bodies in groups.items()})
    identity=subprocess.check_output([cc,'--version'],text=True)
    shipped_profile=ROOT/'tools/profiles/windows-x64.profdata.gz'
    if profile_use is None and not profile_generate and windows and target.startswith('x86_64') and opt=='2' and cpu is None and math_errno and shipped_profile.exists():
        profile_use=shipped_profile
    if profile_generate and profile_use:raise ValueError('Choose profile generation or use')
    if profile_use and pathlib.Path(profile_use).suffix=='.gz':
        with gzip.open(profile_use,'rb') as handle:data=handle.read(64*1024*1024+1)
        if len(data)>64*1024*1024:raise ValueError('LLVM profile exceeds 64 MiB')
        profile_directory=ROOT/'build/profiles';profile_directory.mkdir(exist_ok=True)
        profile_use=profile_directory/(hashlib.sha256(data).hexdigest()+'.profdata')
        if not profile_use.exists():profile_use.write_bytes(data)
    profile_flags=['-fprofile-generate'] if profile_generate else ['-fprofile-use='+str(pathlib.Path(profile_use).resolve())] if profile_use else []
    profile_digest=hashlib.sha256(pathlib.Path(profile_use).read_bytes()).hexdigest() if profile_use else ''
    dependency_hash=hashlib.sha256((ROOT/'tools/native_state.h').read_bytes()+(ROOT/'tools/native_fsca_table.inc').read_bytes()+(ROOT/'tools/native_fast_clock.h').read_bytes()+(ROOT/'tools/native_static_timing.h').read_bytes()+(ROOT/'tools/native_fp_control.h').read_bytes()).hexdigest()
    shared_cache=ROOT/'build/aot-shared-objects';shared_cache.mkdir(exist_ok=True)
    def compile_unit(item):
        name,body=item; path=directory/(name+'.c'); obj=directory/(name+'.obj'); stamp=directory/(name+'.sha256')
        visibility='' if windows else '-fvisibility=hidden'
        digest=hashlib.sha256((identity+target+opt+str(cpu)+str(math_errno)+str(profile_flags)+profile_digest+visibility+'no-fp-contract-v1'+dependency_hash+header+body).encode()).hexdigest()
        if obj.exists() and stamp.exists() and stamp.read_text()==digest:return str(obj),False
        cached=shared_cache/(digest+'.obj')
        if cached.exists():
            shutil.copy2(cached,obj);stamp.write_text(digest);return str(obj),False
        path.write_text(body)
        # Relative source names keep internal-function profile keys portable
        # across checkout paths and across round-specific object directories.
        command=[cc,'-O'+opt,'-std=c99','-ffp-contract=off',*profile_flags,'-c',path.name if profile_flags else str(path),'-o',str(obj)]
        if not windows:command+=['-fPIC',visibility]
        if cpu:command+=['-march='+cpu]
        if not math_errno:command+=['-fno-math-errno']
        result=subprocess.run(command,capture_output=True,text=True,cwd=directory if profile_flags else None)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        for line in result.stderr.splitlines():
            if ': warning:' in line:print(line,flush=True)
        shutil.copy2(obj,cached)
        stamp.write_text(digest);print(f'Compiled {name}',flush=True);return str(obj),True
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        results=list(pool.map(compile_unit,units.items()))
    command=[cc,'-dynamiclib' if darwin else '-shared',*profile_flags,*[obj for obj,changed in results],'-o',str(pathlib.Path(output).resolve())]
    if not windows:command+=['-lm']
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report=dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),pages=len(pages),objects=len(results),compiled_objects=sum(changed for obj,changed in results),seconds=time.monotonic()-started,cpu=cpu,math_errno=math_errno,profile_generate=profile_generate,profile_sha256=profile_digest or None,command=command)
    (ROOT/'reports/native-split-build.json').write_text(json.dumps(report,indent=2))
    print({k:v for k,v in report.items() if k!='command'},flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cc',required=True);parser.add_argument('--output',required=True);parser.add_argument('--jobs',type=int,default=4);parser.add_argument('--opt',choices=['0','1','2'],default='1');parser.add_argument('--source');parser.add_argument('--object-dir')
    parser.add_argument('--cpu',choices=['x86-64','x86-64-v3']);parser.add_argument('--no-math-errno',action='store_true')
    profile=parser.add_mutually_exclusive_group();profile.add_argument('--profile-generate',action='store_true');profile.add_argument('--profile-use',type=pathlib.Path);profile.add_argument('--no-profile',dest='profile_use',action='store_const',const='')
    args=parser.parse_args();build(args.cc,args.output,args.jobs,args.opt,args.source,args.object_dir,args.cpu,not args.no_math_errno,args.profile_generate,args.profile_use)
