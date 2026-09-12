"""Import byte-verified offline trace roots; never treat reference execution as native progress."""
import hashlib,json,re,struct
from boot_probe import ROOT,BASE,EXPECTED,RELOCATIONS,load_modules,decode
blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
assert hashlib.sha256(blob).hexdigest()==EXPECTED
trace=(ROOT/'reports/offline-reference-pcs.txt').read_text()
valid={};rejected=[]
modules=load_modules()
for line in trace.splitlines():
    address,word=(int(x,16) for x in line.split())
    offset=address-BASE if BASE<=address<BASE+len(blob)-1 else None
    for dest,source,size in RELOCATIONS:
        if dest<=address<dest+size-1:offset=source+address-dest
    data=blob[offset:offset+2] if offset is not None else None
    if data is None:
        for name,base,image in modules:
            if base<=address<base+len(image)-1:data=image[address-base:address-base+2]
    if data is None or address%2 or struct.unpack('<H',data)[0]!=word:
        rejected.append(f'{address:08x}');continue
    valid[address]=word
covered={int(x,16) for x in re.findall(r'case 0x([0-9a-f]{8})u: /\*',(ROOT/'build/sc5-boot-probe.c').read_text())}
path=ROOT/'reports/observed-roots.json';records=json.loads(path.read_text());known={int(x['pc'],16) for x in records};added=[]
for address,word in sorted(valid.items()):
    if address in covered or address in known:continue
    previous=valid.get(address-2)
    if previous is not None and decode(address-2,previous).kind=='normal':continue
    record=dict(pc=f'{address:08x}',evidence='Offline reference trace only; opcode verified against pinned original image. Must still be executed and verified natively.',image_sha256=EXPECTED)
    records.append(record);added.append(record['pc'])
path.write_text(json.dumps(records,indent=2))
report=dict(added_roots=added,verified_addresses=len(valid),rejected_addresses=rejected,trace_sha256=hashlib.sha256(trace.encode()).hexdigest(),scope='Offline code discovery, not native gameplay evidence')
(ROOT/'reports/offline-coverage-import.json').write_text(json.dumps(report,indent=2))
print(f'Imported {len(added)} verified offline roots; rejected {len(rejected)} addresses')
