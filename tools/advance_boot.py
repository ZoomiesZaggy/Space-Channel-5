"""Offline trace-guided AOT expansion. Every run is freshly compiled native code.

Stops on CPU/device faults; never stubs an unresolved service to keep going.
"""
import argparse,json,pathlib,re,subprocess
from boot_probe import ROOT,BASE,generate
ap=argparse.ArgumentParser();ap.add_argument('--cc',required=True);ap.add_argument('--limit',type=int,default=12);a=ap.parse_args()
cc=str(pathlib.Path(a.cc).resolve());blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
records_path=ROOT/'reports/observed-roots.json'
records=json.loads(records_path.read_text()) if records_path.exists() else []
history_path=ROOT/'reports/boot-expansion.json'
history=json.loads(history_path.read_text()) if history_path.exists() else []
for iteration in range(a.limit):
    source,report=generate(blob,[int(x['pc'],16) for x in records])
    (ROOT/'build/sc5-boot-probe.c').write_text(source)
    (ROOT/'reports/boot-analysis.json').write_text(json.dumps(report,indent=2))
    command=[cc,'-O2','-std=c99','-Wall','-Wextra','-Werror',str(ROOT/'build/sc5-boot-probe.c'),'-o',str(ROOT/'build/sc5-boot-probe.exe')]
    build=subprocess.run(command,capture_output=True,text=True)
    if build.returncode:raise RuntimeError(build.stdout+build.stderr)
    run=subprocess.run([str(ROOT/'build/sc5-boot-probe.exe'),str(ROOT/'extracted/1ST_READ.BIN'),'--model-ccr','--host-services'],capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    m=re.search(r'HALT fault=(\d+) pc=([A-F0-9]+) address=([A-F0-9]+) retired=(\d+)',run.stdout);assert m,run.stdout
    fault,pc,address,retired=int(m[1]),int(m[2],16),int(m[3],16),int(m[4])
    print(f'{iteration}: {report["instructions"]} static instructions; fault={fault} pc={pc:08X} address={address:08X} retired={retired}',flush=True)
    history.append(dict(roots=report['roots'],instructions=report['instructions'],command=command,stdout=run.stdout))
    history_path.write_text(json.dumps(history,indent=2))
    if fault!=2 or pc%2 or not BASE<=pc<BASE+len(blob)-1:break
    assert pc not in [int(x['pc'],16) for x in records],'Repeated unresolved target'
    records.append(dict(pc=f'{pc:08x}',evidence='Native indirect branch reached this PC',retired=retired,image_sha256=report['image_sha256']))
    records_path.write_text(json.dumps(records,indent=2))
