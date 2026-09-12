"""Read-only raw Mode-1 GDI audit and bounded ISO9660 extraction."""
import argparse, collections, hashlib, json, pathlib, re, struct, zlib

def u32(b, o):
    a = struct.unpack_from('<I', b, o)[0]
    assert a == struct.unpack_from('>I', b, o+4)[0], 'ISO endian mismatch'
    return a

class Track:
    def __init__(self, path, lba, offset=0):
        self.path, self.lba, self.offset = path, lba, offset
        self.f = path.open('rb')
        self.sectors = (path.stat().st_size-offset)//2352
    def read(self, lba, size):
        rel = lba-self.lba
        assert rel >= 0 and rel+(size+2047)//2048 <= self.sectors, (lba,size)
        out = bytearray()
        while len(out) < size:
            self.f.seek(self.offset+rel*2352)
            b = self.f.read(2352)
            assert b[:12] == b'\0'+b'\xff'*10+b'\0' and b[15] == 1, 'Not Mode 1'
            out.extend(b[16:2064]); rel += 1
        return bytes(out[:size])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('gdi',type=pathlib.Path); ap.add_argument('--out',type=pathlib.Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'reports').mkdir(exist_ok=True); (a.out/'extracted').mkdir(exist_ok=True)
    lines=a.gdi.read_text().splitlines(); tracks=[]
    for line in lines[1:]:
        if not line.strip(): continue
        m=re.fullmatch(r'\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"([^"]+)"\s+(\d+)\s*',line); assert m,line
        n,lba,kind,ss,name,off=m.groups(); p=a.gdi.parent/name
        assert pathlib.Path(name).name == name
        size=p.stat().st_size; assert (size-int(off))%int(ss)==0
        hashes={k:hashlib.new(k) for k in ['md5','sha1','sha256']}; crc=0; bad=0; sectors=0
        with p.open('rb') as f:
            while b:=f.read(2352*4096):
                for h in hashes.values(): h.update(b)
                crc=zlib.crc32(b,crc)
                if int(kind)==4:
                    for i in range(0,len(b),2352):
                        s=b[i:i+2352]; sectors+=1
                        bad+=s[:12] != b'\0'+b'\xff'*10+b'\0' or s[15]!=1
        rec=dict(number=int(n),lba=int(lba),kind=int(kind),sector_size=int(ss),name=name,offset=int(off),bytes=size,sectors=(size-int(off))//int(ss),hashes={k:h.hexdigest() for k,h in hashes.items()},crc32=f'{crc:08x}',bad_mode1_headers=bad)
        assert not bad,rec
        tracks.append(rec); print(json.dumps(rec),flush=True)
    assert len(tracks)==int(lines[0])
    t=Track(a.gdi.parent/tracks[-1]['name'],tracks[-1]['lba'],tracks[-1]['offset'])
    ip=t.read(t.lba,32768); (a.out/'extracted/IP.BIN').write_bytes(ip)
    fields={'hardware':(0,16),'maker':(16,32),'device':(32,48),'area':(48,56),'peripherals':(56,64),'product':(64,74),'version':(74,80),'date':(80,96),'boot_file':(96,112),'publisher':(112,128),'title':(128,256)}
    metadata={k:ip[s:e].decode('ascii',errors='replace').strip() for k,(s,e) in fields.items()}
    pvd=t.read(t.lba+16,2048); assert pvd[:7]==b'\x01CD001\x01'
    assert struct.unpack_from('<H',pvd,128)[0]==2048
    files=[]; visited=set()
    def walk(ext,size,parent=''):
        assert (ext,size) not in visited,'Directory cycle'; visited.add((ext,size))
        data=t.read(ext,size); pos=0
        while pos<len(data):
            length=data[pos]
            if not length: pos=(pos//2048+1)*2048; continue
            r=data[pos:pos+length]; assert len(r)==length and length>=34
            pos+=length; name=r[33:33+r[32]]
            if name in (b'\0',b'\1'): continue
            name=name.decode('ascii').split(';')[0]; assert name not in ('.','..') and not any(c in name for c in '/\\:')
            path=parent+name; ext=u32(r,2); size=u32(r,10); flags=r[25]
            assert not flags&128,'Multi-extent file unsupported'
            if flags&2: walk(ext,size,path+'/'); continue
            head=t.read(ext,min(size,4096))
            files.append(dict(path=path,lba=ext,bytes=size,head_hex=head[:32].hex(),head_ascii=''.join(chr(c) if 32<=c<127 else '.' for c in head[:64])))
            if path.upper()==metadata['boot_file'].upper():
                binary=t.read(ext,size); (a.out/'extracted'/name).write_bytes(binary)
                files[-1]['sha256']=hashlib.sha256(binary).hexdigest()
    walk(u32(pvd,158),u32(pvd,166))
    report=dict(tracks=tracks,boot=metadata,volume=pvd[40:72].decode('ascii').strip(),files=files,extensions=dict(collections.Counter(pathlib.Path(f['path']).suffix for f in files)))
    (a.out/'reports/disc.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','tracks')},indent=2)); print('Files:',len(files))

if __name__=='__main__': main()
