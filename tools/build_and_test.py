"""Build the native boot diagnostic and verify explicit observed boundaries."""
import argparse, hashlib, json, pathlib, subprocess, sys
from boot_probe import ROOT, EXPECTED
ap=argparse.ArgumentParser();ap.add_argument('--cc',type=pathlib.Path,required=True);a=ap.parse_args()
cc=str(a.cc.resolve()); logs=[]
def run(args,cwd=ROOT):
    p=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,text=True)
    logs.append(dict(command=[str(x) for x in args],cwd=str(cwd),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout
try:
    assert hashlib.sha256((ROOT/'extracted/1ST_READ.BIN').read_bytes()).hexdigest()==EXPECTED
    run([sys.executable,ROOT/'tools/boot_probe.py'])
    run([cc,'--version'])
    run([cc,'-O2','-std=c99','-Wall','-Wextra','-Werror',ROOT/'build/sc5-boot-probe.c','-o',ROOT/'build/sc5-boot-probe.exe'])
    strict=run([ROOT/'build/sc5-boot-probe.exe',ROOT/'extracted/1ST_READ.BIN'])
    assert 'fault=3 pc=8C01000E address=FF00001C retired=7' in strict
    modeled=run([ROOT/'build/sc5-boot-probe.exe',ROOT/'extracted/1ST_READ.BIN','--model-ccr'])
    assert 'fault=2 pc=8C032CFC address=00000000 retired=5090311' in modeled
    assert 'r15=8C00F3E0' in modeled and 'CCR write 00000800' in modeled
    damaged=bytearray((ROOT/'extracted/1ST_READ.BIN').read_bytes());damaged[0]^=1
    damaged_path=ROOT/'build/checksum-rejection-test.bin';damaged_path.write_bytes(damaged)
    try:
        rejected=subprocess.run([str(ROOT/'build/sc5-boot-probe.exe'),str(damaged_path)],capture_output=True,text=True)
        assert rejected.returncode==2 and 'Wrong executable checksum' in rejected.stderr
        logs.append(dict(test='Corrupted executable is rejected',returncode=rejected.returncode,stderr=rejected.stderr))
    finally:damaged_path.unlink()
    # Direct runtime checks: writable image data, executable-byte protection,
    # address aliases, alignment, unmapped IO, and delay-slot atomic budgeting.
    tests=r'''
#define main probe_main
#include "sc5-boot-probe.c"
#undef main
#include <assert.h>
int main(void){
 memset(&s,0,sizeof(s));wr(0x8c100000,0x12345678,4);assert(!s.fault);assert(rd(0xac100000,4)==0x12345678);assert(rd(0x0c100000,4)==0x12345678);
 wr(0x8c010000,0,2);assert(s.fault==4);
 s.fault=0;rd(0x8c100001,4);assert(s.fault==3);
 s.fault=0;rd(0xa05f8000,4);assert(s.fault==3);
 s.fault=0;model_ccr=0;rd(0xff00001c,4);assert(s.fault==3);
 s.fault=0;model_ccr=1;wr(0xff00001c,0x800,4);assert(rd(0xff00001c,4)==0x800);
 ram[0x1001c]=0x2b;ram[0x1001d]=0x40;ram[0x1001e]=9;ram[0x1001f]=0;
 s.fault=0;steps=0;s.pc=0x8c01001c;s.r[0]=0x8c043720;run(1);assert(steps==0&&s.pc==0x8c01001c);run(2);assert(steps==2&&s.pc==0x8c043720);
 s.pc=0x8c01001c;steps=0;ram[0x1001e]=8;run(2);assert(s.fault==7&&steps==0);
 puts("PASS: RAM aliases, writable image data, code guard, alignment, IO trap, CCR model, delay budget");return 0;
}
'''
    (ROOT/'build/runtime-tests.c').write_text(tests)
    run([cc,'-O2','-std=c99','-Wall','-Wextra','-Werror',ROOT/'build/runtime-tests.c','-o',ROOT/'build/runtime-tests.exe'])
    print(run([ROOT/'build/runtime-tests.exe']))
    print(strict,modeled)
finally:
    (ROOT/'reports/build-test-log.json').write_text(json.dumps(logs,indent=2))
