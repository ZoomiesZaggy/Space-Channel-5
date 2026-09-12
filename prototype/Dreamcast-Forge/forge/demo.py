"""Original SH-4 game-logic sample. Custom host ABI; not a retail game image."""
import struct
from .sh4 import BASE

def make_demo():
    words=[];labels={};fixups=[];listing=[]
    def emit(w,text): listing.append(f"{BASE+len(words)*2:08X}  {w:04X}  {text}");words.append(w)
    def label(name): labels[name]=len(words)*2;listing.append(name+":")
    def branch(op,name): fixups.append((len(words),op,name));emit(op<<8,name)
    def mov(n,v): emit(0xE000|n<<8|(v&255),f"mov #{v},r{n}")
    def add(n,v): emit(0x7000|n<<8|(v&255),f"add #{v},r{n}")
    def rr(op,n,m,text): emit(op|n<<8|m<<4,f"{text} r{m},r{n}")
    # Host: r0 input bitmask (1 left,2 right); r1 player x; r2 star x;
    # r3 star y; r4 score; r5 lives; r6 PRNG; r7 frames; r8 falling speed.
    # Persistent state is held in registers between calls.
    label("frame")
    emit(0x4515,"cmp/pl r5");branch(0x8B,"done")
    emit(0xC801,"tst #1,r0");branch(0x89,"right");add(1,-7)
    label("right");emit(0xC802,"tst #2,r0");branch(0x89,"bounds");add(1,7)
    label("bounds");mov(9,24);rr(0x3003,1,9,"cmp/ge");branch(0x89,"upper");rr(0x6003,1,9,"mov")
    label("upper");mov(9,77);emit(0x4908,"shll2 r9");emit(0x4900,"shll r9") # 616
    rr(0x3007,1,9,"cmp/gt");branch(0x8B,"fall");rr(0x6003,1,9,"mov")
    label("fall");add(7,1);rr(0x300C,3,8,"add")
    mov(9,100);emit(0x4908,"shll2 r9") # 400
    rr(0x3003,3,9,"cmp/ge");branch(0x8B,"done")
    rr(0x6003,10,1,"mov");rr(0x3008,10,2,"sub");emit(0x4A11,"cmp/pz r10")
    branch(0x89,"distance");rr(0x600B,10,10,"neg")
    label("distance");mov(9,32);rr(0x3007,9,10,"cmp/gt");branch(0x8B,"miss")
    add(4,1)
    # Increase speed at score multiples of 8; upper bound 14.
    rr(0x6003,10,4,"mov");mov(9,7);rr(0x2008,10,9,"tst");branch(0x8B,"respawn")
    mov(9,14);rr(0x3003,8,9,"cmp/ge");branch(0x89,"respawn");add(8,1)
    branch(0xA0,"respawn");emit(0x0009,"nop")
    label("miss");add(5,-1)
    label("respawn");mov(3,0)
    # xorshift-like integer generator; select x in [64,575].
    rr(0x6003,10,6,"mov");emit(0x4A08,"shll2 r10");rr(0x200A,6,10,"xor")
    rr(0x6003,10,6,"mov");emit(0x4A19,"shlr8 r10");rr(0x200A,6,10,"xor");add(6,17)
    rr(0x6003,2,6,"mov");mov(9,2);emit(0x4918,"shll8 r9");add(9,-1);rr(0x2009,2,9,"and");add(2,64)
    label("done");emit(0x000B,"rts");emit(0x0009,"nop")
    for index,op,name in fixups:
        disp=(labels[name]-(index*2+4))//2
        if op==0xA0:
            assert -2048<=disp<=2047;words[index]=0xA000|(disp&4095)
        else:
            assert -128<=disp<=127;words[index]=op<<8|(disp&255)
    blob=struct.pack("<"+"H"*len(words),*words)
    # Final machine-code listing is authoritative; labels aid maintenance.
    return blob,"\n".join(f"{BASE+i*2:08X}  {w:04X}" for i,w in enumerate(words))+"\n\n"+"\n".join(listing)

def initialize(native):
    native.lib.forge_reset()
    for r,v in {1:320,2:320,3:0,4:0,5:5,6:0x1234567,7:0,8:5}.items(): native.set(r,v)
