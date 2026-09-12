"""Read-only GDI/ISO inspection and bounded ISO9660 boot-file extraction."""
from dataclasses import dataclass
from pathlib import Path
import shlex
import struct

@dataclass
class Track:
    number: int
    lba: int
    kind: int
    sector: int
    path: Path
    offset: int

class Disc:
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.tracks=[]
        if self.path.suffix.lower()==".gdi":
            if self.path.stat().st_size>65536: raise ValueError("GDI descriptor is too large.")
            lines=[line.strip() for line in self.path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            count=int(lines[0]) if lines else 0
            if not 1<=count<=99 or len(lines)!=count+1: raise ValueError("Invalid GDI track count.")
            for line in lines[1:]:
                fields=shlex.split(line)
                if len(fields)!=6: raise ValueError("Each GDI track must have six fields.")
                number,lba,kind,sector=map(int,fields[:4]); offset=int(fields[5])
                path=(self.path.parent/fields[4]).resolve()
                if not path.is_relative_to(self.path.parent): raise ValueError("GDI track paths must stay inside the game's folder.")
                if not path.is_file(): raise ValueError(f"Missing track: {path.name}. Keep all tracks beside the GDI.")
                if number!=len(self.tracks)+1 or lba<0 or kind not in (0,4) or sector not in (2048,2352) or offset<0:
                    raise ValueError("Unsupported GDI track layout.")
                if offset>=path.stat().st_size or (path.stat().st_size-offset)%sector: raise ValueError(f"Truncated track: {path.name}.")
                if self.tracks and lba<=self.tracks[-1].lba: raise ValueError("GDI track addresses must increase.")
                self.tracks.append(Track(number,lba,kind,sector,path,offset))
        elif self.path.suffix.lower()==".iso":
            if self.path.stat().st_size%2048: raise ValueError("Expected a 2048-byte-sector ISO.")
            self.tracks=[Track(1,0,4,2048,self.path,0)]
        else:
            raise ValueError("Disc inspection supports GDI and 2048-byte ISO. CHD/CDI can be launched with Flycast but are not extracted here.")

    def sector(self,lba):
        candidates=[t for t in self.tracks if t.lba<=lba]
        if not candidates: raise ValueError("Disc sector is outside the image.")
        t=candidates[-1]
        if t.kind!=4: raise ValueError("Expected a data track, found audio.")
        with t.path.open("rb") as f:
            f.seek(t.offset+(lba-t.lba)*t.sector); raw=f.read(t.sector)
        if len(raw)!=t.sector: raise ValueError("Truncated or unmapped disc sector.")
        if t.sector==2048: return raw
        if raw[:12]!=b"\x00"+b"\xff"*10+b"\x00": raise ValueError("Invalid raw CD sector header.")
        if raw[15]==1: return raw[16:2064]
        if raw[15]==2 and raw[16:20]==raw[20:24] and not raw[18]&0x20: return raw[24:2072]
        raise ValueError("Only Mode 1 and Mode 2 Form 1 data sectors are supported.")

    def read_extent(self,lba,size,limit=4*1024*1024):
        if not 0<size<=limit: raise ValueError("ISO extent exceeds the supported size limit.")
        return b"".join(self.sector(lba+i) for i in range((size+2047)//2048))[:size]

    def boot(self):
        # Prefer the high-density session. Extent addresses are disc LBAs.
        for t in reversed(self.tracks):
            if t.kind!=4: continue
            try: pvd=self.sector(t.lba+16)
            except ValueError: continue
            if pvd[:7]!=b"\x01CD001\x01": continue
            if struct.unpack_from("<H",pvd,128)[0]!=2048: raise ValueError("Unsupported ISO logical block size.")
            root=pvd[156:190]
            root_lba,size=struct.unpack_from("<I",root,2)[0],struct.unpack_from("<I",root,10)[0]
            data=self.read_extent(root_lba,size,1024*1024)
            header=self.sector(t.lba)
            is_dc=header.startswith(b"SEGA SEGAKATANA")
            text=lambda a,b:header[a:b].decode("ascii","replace").strip(" \x00")
            bootname=text(96,112) if is_dc else "1ST_READ.BIN"
            pos=0
            while pos<len(data):
                length=data[pos]
                if not length: pos=(pos//2048+1)*2048; continue
                if length<34 or pos+length>len(data) or pos%2048+length>2048: raise ValueError("Malformed ISO directory record.")
                rec=data[pos:pos+length]; pos+=length
                if 33+rec[32]>length: raise ValueError("Invalid ISO filename length.")
                name=rec[33:33+rec[32]].decode("ascii","replace").split(";")[0]
                if name.upper()==bootname.upper():
                    if rec[25]&(2|128): raise ValueError("Multi-extent or directory boot files are unsupported.")
                    blob=self.read_extent(struct.unpack_from("<I",rec,2)[0],struct.unpack_from("<I",rec,10)[0])
                    return {"title":text(128,256) if is_dc else self.path.stem,"product":text(64,74) if is_dc else "Unknown",
                            "boot_name":name,"bytes":len(blob),"tracks":len(self.tracks),"dreamcast_header":is_dc},blob
            raise ValueError(f"Boot file {bootname!r} was not found in the ISO root.")
        raise ValueError("No supported ISO9660 data session found.")
