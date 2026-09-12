import os
"""Inspect actual headers and extract executable candidates, preserving disc data."""
import collections, hashlib, json, pathlib, struct, re
from inspect_disc import Track
ROOT=pathlib.Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'reports/disc.json').read_text())
t=Track(pathlib.Path(os.environ['SC5_GDI']).resolve().parent/report['tracks'][2]['name'],45000)
assets=[]
for f in report['files']:
    ext=pathlib.Path(f['path']).suffix
    item=dict(path=f['path'],bytes=f['bytes'])
    if ext in ('.BIN','.DRV'):
        b=t.read(f['lba'],f['bytes']); (ROOT/'extracted'/f['path']).write_bytes(b)
        item['sha256']=hashlib.sha256(b).hexdigest()
        item['classification']='SH-4 code candidate; load address unresolved' if f['path'].startswith('ROUND') else 'boot executable' if f['path']=='1ST_READ.BIN' else 'SDRV sound-driver container; payload architecture not yet decoded'
    if ext=='.AFS':
        b=t.read(f['lba'],min(65536,f['bytes'])); assert b[:4]==b'AFS\0'
        count=struct.unpack_from('<I',b,4)[0]; assert 8+count*8<=len(b)
        members=[]
        for i in range(count):
            off,size=struct.unpack_from('<II',b,8+i*8); assert off+size<=f['bytes']
            skip=off%2048; head=t.read(f['lba']+off//2048,skip+min(size,64))[skip:]
            members.append(dict(index=i,offset=off,bytes=size,head_hex=head[:32].hex()))
        item['members']=members
    if ext=='.M1V':
        head=t.read(f['lba'],min(65536,f['bytes'])); k=head.find(b'\0\0\1\xb3')
        if 0<=k<=len(head)-8:
            v=int.from_bytes(head[k+4:k+8],'big');item['mpeg_sequence']=dict(offset=k,width=v>>20,height=(v>>8)&4095,aspect_code=(v>>4)&15,frame_rate_code=v&15)
    if ext in ('.BIN','.DRV','.AFS','.M1V'):assets.append(item)
boot=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
strings=[(m.start(),m.group().decode('ascii')) for m in re.finditer(rb'[ -~]{8,}',boot)]
(ROOT/'reports/strings.json').write_text(json.dumps(strings,indent=2))
deps=[dict(offset=hex(o),address=hex(0x8c010000+o),text=s) for o,s in strings if any(k in s for k in ['Ninja Ver','Shinobi Library','KAMUI Ver','ADXT Ver','ADXF Ver','CRI SFD','CRI SAN','CRI LSC','manatee.drv'])]
(ROOT/'reports/assets.json').write_text(json.dumps(dict(assets=assets,library_signatures=deps),indent=2))
print(json.dumps(dict(extracted_modules=[a['path'] for a in assets if 'sha256' in a],afs_members=sum(len(a.get('members',[])) for a in assets),mpeg_sequences=dict(collections.Counter(str(a['mpeg_sequence']) for a in assets if 'mpeg_sequence' in a)),dependencies=deps),indent=2))
