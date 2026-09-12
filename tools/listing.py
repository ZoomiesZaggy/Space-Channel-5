import argparse,struct
from boot_probe import ROOT,BASE,decode,load_modules
ap=argparse.ArgumentParser();ap.add_argument('address',type=lambda s:int(s,16));ap.add_argument('--bytes',type=int,default=64);a=ap.parse_args()
blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
base=BASE
for name,start,data in load_modules():
    if start<=a.address<start+len(data):blob=data;base=start;break
for pc in range(a.address,a.address+a.bytes,2):
    word=struct.unpack_from('<H',blob,pc-base)[0];i=decode(pc,word)
    print(f'{pc:08x} {word:04x} {i.name:26s} {i.code or i.expr}'+(f' -> {i.target:08x}' if i.target is not None else ''))
