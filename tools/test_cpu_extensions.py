"""Independent value checks for newly added instructions, executed in a native DLL."""
import argparse,ctypes,json,pathlib,random,subprocess,struct
from boot_probe import ROOT,RUNTIME,decode
ap=argparse.ArgumentParser();ap.add_argument('--cc',required=True);a=ap.parse_args()
words=set()
for register in range(16):
    words.add(0x00c3|(register<<8))
    words.update(kind|(register<<8)|(bank<<4) for bank in range(8) for kind in (0x0082,0x408e,0x4083,0x4087))
    words.update(kind|(register<<8) for kind in (0x4004,0x4005,0x4024,0x4025))
    words.add(0x401b|(register<<8))
    words.update((kind+offset)|(register<<8) for kind in (0x4003,0x4013,0x4023,0x4033,0x4043,0x4002,0x4012,0x4022,0x4052,0x4062) for offset in (0,4))
    words.update(kind|(register<<8) for kind in (0xf00d,0xf01d,0xf02d,0xf03d,0xf04d,0xf05d))
    words.update([0x0002|(register<<8),0x400e|(register<<8)])
    words.update(kind|(register<<8) for kind in (0x0012,0x0022,0x0032,0x0042,0x003a,0x00fa,0x401e,0x402e,0x403e,0x404e,0x40fa,0x005a,0x006a,0x405a,0x406a,0xf08d,0xf09d))
    for disp in range(16):
        words.update(kind|(register<<4)|disp for kind in (0x8000,0x8100,0x8400,0x8500))
    for m in range(16):
        words.update(kind|(register<<8)|(m<<4) for kind in (4,5,6,12,13,14))
        words.update(0xf000|kind|(register<<8)|(m<<4) for kind in (6,7,8,9,10,11,12))
        words.update(kind|(register<<8)|(m<<4) for kind in (0x400c,0x400d,0x200c,0x200d,0x6008,0x6009))
        words.update(kind|(register<<8)|(m<<4) for kind in (0x300a,0x300b,0x300e,0x300f,0x0007))
        words.update(kind|(register<<8)|(m<<4) for kind in (0x200e,0x200f,0x3005,0x300d))
    words.update(kind|(register<<8) for kind in (0x000a,0x001a,0x400a,0x401a))
source=[RUNTIME,'static int translated(u32 a){(void)a;return 0;}']
source.append('__declspec(dllexport) void reset(void){memset(&s,0,sizeof(s));memset(ram,0,0x1000000);model_ccr=0;host_services=0;}')
source.append('__declspec(dllexport) void regset(u32 n,u32 x){s.r[n]=x;} __declspec(dllexport) u32 regget(u32 n){return s.r[n];}')
source.append('__declspec(dllexport) u32 status(u32 x){set_sr(x);return get_sr();} __declspec(dllexport) u32 fault(void){return s.fault;}')
source.append('__declspec(dllexport) void frset(u32 n,u32 v){s.fr[n]=v;} __declspec(dllexport) u32 frget(u32 n){return s.fr[n];} __declspec(dllexport) void fpscr(u32 v){set_fpscr(v);}')
source.append('__declspec(dllexport) void poke(u32 a,u32 v,u32 z){wr(a,v,z);} __declspec(dllexport) u32 peek(u32 a,u32 z){return rd(a,z);}')
source.append('__declspec(dllexport) void execute(u32 word){u32 v;(void)v;switch(word){')
for word in sorted(words):source.append(f'case {word}: {decode(0x8c010000,word).code}break;')
source.append('default:s.fault=5;}}')
(ROOT/'build/cpu-extension-tests.c').write_text('\n'.join(source))
cc=str(pathlib.Path(a.cc).resolve());dll=ROOT/'build/cpu-extension-tests.dll'
command=[cc,'-O2','-std=c99','-shared',str(ROOT/'build/cpu-extension-tests.c'),'-o',str(dll)]
subprocess.run(command,check=True)
lib=ctypes.CDLL(str(dll));u=ctypes.c_uint32
for name,count in [('reset',0),('regset',2),('regget',1),('status',1),('fault',0),('poke',3),('peek',2),('execute',1),('frset',2),('frget',1),('fpscr',1)]:
    getattr(lib,name).argtypes=[u]*count;getattr(lib,name).restype=u if name in ('regget','status','fault','peek','frget') else None
rng=random.Random(5095);checks=0
def signed(v,bits):return (v-(1<<bits) if v&(1<<(bits-1)) else v)&0xffffffff
try:
    for n in range(16):
        lib.reset();value=rng.getrandbits(32) if n else 0x8c100000
        lib.regset(0,value);lib.regset(n,0x8c100000);lib.execute(0x00c3|(n<<8))
        assert lib.peek(0x8c100000,4)==value and lib.fault()==0;checks+=1
    for n in range(16):
        for m in range(16):
            lib.reset();x,y=rng.getrandbits(32),rng.getrandbits(32)
            if n==m:y=x
            lib.regset(n,x);lib.regset(m,y);lib.execute(0x200d|(n<<8)|(m<<4))
            assert lib.regget(n)==((x>>16)|(y<<16))&0xffffffff and lib.fault()==0;checks+=1
    for mode in (0x40000000,0x70000000):
        for bank in range(8):
            lib.reset();lib.status(mode);lib.regset(1,0x12345678+bank);lib.regset(15,0x8c100004)
            lib.execute(0x418e|(bank<<4));lib.execute(0x0282|(bank<<4));assert lib.regget(2)==0x12345678+bank;checks+=1
            lib.execute(0x4f83|(bank<<4));assert lib.peek(0x8c100000,4)==0x12345678+bank
            lib.regset(1,0);lib.execute(0x418e|(bank<<4));lib.execute(0x4f87|(bank<<4));lib.execute(0x0282|(bank<<4))
            assert lib.regget(2)==0x12345678+bank and lib.regget(15)==0x8c100004 and lib.fault()==0;checks+=1
    for value in (0,1,0x7fffffff,0x80000000,0xffffffff,0x12345678):
        for t in (0,1):
            for kind in (0x4004,0x4005,0x4024,0x4025):
                lib.reset();lib.status(0x40000000|t);lib.regset(1,value);lib.execute(kind|0x100);lib.execute(0x0202)
                left=(kind&1)==0;carry=(value>>31) if left else value&1
                incoming=t if kind&0x20 else carry
                result=((value<<1)|incoming) if left else ((value>>1)|(incoming<<31))
                assert lib.regget(1)==result&0xffffffff and lib.regget(2)&1==carry;checks+=1
    for kind,bits,is_signed in ((0x200e,16,False),(0x200f,16,True),(0x3005,32,False),(0x300d,32,True)):
        for x in (0,1,0xffff,0x8000,0x7fffffff,0x80000000,0xffffffff):
            for y in (0,1,0xffff,0x8000,0x7fffffff,0x80000000,0xffffffff):
                lib.reset();lib.regset(1,x);lib.regset(2,y);lib.execute(kind|0x120);lib.execute(0x031a);lib.execute(0x040a)
                def operand(value):
                    value&=(1<<bits)-1
                    return value-(1<<bits) if is_signed and value&(1<<(bits-1)) else value
                product=operand(x)*operand(y)
                assert lib.regget(3)==product&0xffffffff
                if bits==32:assert lib.regget(4)==(product>>32)&0xffffffff
                checks+=1
    # Save/restore control state through the same stack sequence used by IRQs.
    for store,load,read,value in ((0x4f13,0x4f17,0x0212,0x12345678),(0x4f23,0x4f27,0x0222,0x8c00f400),(0x4f33,0x4f37,0x0232,0x40000000),(0x4f43,0x4f47,0x0242,0x8c123456),(0x4f02,0x4f06,0x020a,0x87654321),(0x4f12,0x4f16,0x021a,0xabcdef01),(0x4f52,0x4f56,0x025a,0x3f800000),(0x4f62,0x4f66,0x026a,0x40000)):
        lib.reset();lib.status(0x40000000);lib.regset(15,0x8c100000);lib.poke(0x8c100000,value,4);lib.execute(load);lib.execute(read)
        assert lib.regget(2)==value and lib.regget(15)==0x8c100004 and lib.fault()==0;checks+=1
        lib.execute(store);assert lib.regget(15)==0x8c100000 and lib.peek(0x8c100000,4)==value;checks+=1
    for value in (0,1,0x7f,0x80,0xff):
        lib.reset();lib.status(0x40000000);lib.regset(1,0x8c100000);lib.poke(0x8c100000,value,1);lib.execute(0x411b);lib.execute(0x0202)
        assert lib.peek(0x8c100000,1)==value|0x80 and lib.regget(2)&1==int(value==0);checks+=1
    # FTRC truncates toward zero and saturates out-of-range or invalid inputs.
    for value in (0.0,-0.0,1.0,-1.0,1.9,-1.9,255.9,-255.9,2147483520.0,-2147483648.0):
        bits=struct.unpack('<I',struct.pack('<f',value))[0]
        lib.reset();lib.frset(1,bits);lib.execute(0xf13d);lib.execute(0x025a)
        assert lib.regget(2)==int(value)&0xffffffff and lib.fault()==0;checks+=1
    for bits in (0x7fc00000,0x7f800000,0xff800000,0x4f000000,0xcf000001):
        lib.reset();lib.frset(1,bits);lib.execute(0xf13d);lib.execute(0x025a);assert lib.fault()==0;assert lib.regget(2)==(0x7fffffff if bits in (0x7f800000,0x4f000000) else 0x80000000);checks+=1
    for value in (0,1,-1,16777217,-16777217,2147483647,-2147483648):
        lib.reset();lib.regset(1,value&0xffffffff);lib.execute(0x415a);lib.execute(0xf22d)
        assert lib.frget(2)==struct.unpack('<I',struct.pack('<f',value))[0] and lib.fault()==0;checks+=1
    for bits in (0,0x80000000,0x3f800000,0xbf800000,0x7fc12345):
        lib.reset();lib.frset(1,bits);lib.execute(0xf14d);assert lib.frget(1)==bits^0x80000000;checks+=1
        lib.execute(0xf15d);assert lib.frget(1)==bits&0x7fffffff;checks+=1
    for width in (1,2):
        for reg in range(1,16):
            for disp in range(16):
                lib.reset();base=0x8c100000;value=rng.getrandbits(32)
                lib.regset(reg,base);lib.regset(0,value)
                lib.execute((0x8100 if width==2 else 0x8000)|(reg<<4)|disp)
                assert lib.peek(base+disp*width,width)==value&((1<<(width*8))-1)
                lib.execute((0x8500 if width==2 else 0x8400)|(reg<<4)|disp)
                assert lib.regget(0)==signed(value&((1<<(width*8))-1),width*8)
                assert lib.fault()==0;checks+=2
    for width,kind in [(1,4),(2,5),(4,6)]:
        for n in range(1,16):
            for m in range(1,16):
                lib.reset();base=0x8c100000;offset=32;value=rng.getrandbits(32)
                lib.regset(0,offset);lib.regset(n,base)
                if n!=m:lib.regset(m,value)
                else:value=base
                lib.execute(kind|(n<<8)|(m<<4))
                assert lib.peek(base+offset,width)==value&((1<<(width*8))-1)
                lib.regset(m,base);lib.execute((kind+8)|(n<<8)|(m<<4))
                expected=value&((1<<(width*8))-1)
                if width<4:expected=signed(expected,width*8)
                assert lib.regget(n)==expected and lib.fault()==0;checks+=2
    # T preservation, reserved-bit mask, bank swaps, user-mode privilege failure.
    lib.reset();lib.status(0x700000f0)
    for n in range(8):lib.regset(n,0xa000+n)
    assert lib.status(0x40000001)==0x40000001
    assert all(lib.regget(n)==0 for n in range(8))
    for n in range(8):lib.regset(n,0xb000+n)
    lib.status(0x60000001);assert all(lib.regget(n)==0xa000+n for n in range(8))
    lib.execute(0x0902);assert lib.regget(9)==0x60000001
    lib.regset(10,0xffffffff);lib.execute(0x4a0e);lib.execute(0x0902);assert lib.regget(9)==0x700083f3
    lib.status(0);lib.execute(0x0002);assert lib.fault()==8;checks+=7
    for n in range(16):
        for m in range(16):
            lib.reset();value=rng.getrandbits(32);lib.frset(m,value);lib.execute(0xf00c|(n<<8)|(m<<4));assert lib.frget(n)==value
            lib.regset(n,0x8c100004);lib.execute(0xf00b|(n<<8)|(m<<4));assert lib.peek(0x8c100000,4)==value and lib.regget(n)==0x8c100000
            lib.regset(m,0x8c100000);lib.execute(0xf009|(n<<8)|(m<<4));assert lib.frget(n)==value and lib.regget(m)==0x8c100004 and lib.fault()==0
            checks+=3
    lib.reset();lib.frset(2,0x7fa12345);lib.fpscr(0x200000);assert lib.frget(2)==0;lib.frset(2,0xdeadbeef);lib.fpscr(0);assert lib.frget(2)==0x7fa12345
    lib.fpscr(0x100000);lib.execute(0xf12c);assert lib.fault()==0
    lib.reset();lib.status(0x8000);lib.execute(0xf12c);assert lib.fault()==10
    lib.reset();lib.status(0x40000000);lib.regset(1,0x8c00f400);lib.execute(0x412e);lib.execute(0x0222);assert lib.regget(2)==0x8c00f400;checks+=5
    for arithmetic in (0,1):
        for count in (0,1,31,32,33,0xffffffff,0xffffffe0,0xffffffe1,0x80000000):
            for value in (0,1,0x80000000,0x7fffffff,0xffffffff,rng.getrandbits(32)):
                lib.reset();lib.regset(1,value);lib.regset(2,count);lib.execute(0x412c if arithmetic else 0x412d)
                if count<0x80000000:expected=value<<(count&31)
                else:
                    amount=(-count)&31;number=value-0x100000000 if arithmetic and value&0x80000000 else value
                    expected=(number>>amount) if amount else (-1 if arithmetic and value&0x80000000 else 0)
                assert lib.regget(1)==expected&0xffffffff;checks+=1
    for _ in range(256):
        x,y=rng.getrandbits(32),rng.getrandbits(32);lib.reset();lib.status(0x40000000);lib.regset(1,x);lib.regset(2,y);lib.execute(0x212c)
        # Observe CMP/STR's T result through STC, without modifying it.
        lib.execute(0x0302);assert lib.regget(3)&1==int(any(((x^y)>>(8*j))&255==0 for j in range(4)));checks+=1
    for kind in (10,11,14,15):
        for _ in range(256):
            x,y,t=rng.getrandbits(32),rng.getrandbits(32),rng.randrange(2)
            lib.reset();lib.status(0x40000000|t);lib.regset(1,x);lib.regset(2,y);lib.execute(0x3120|kind);lib.execute(0x0302)
            if kind in (10,14):
                total=x-y-t if kind==10 else x+y+t;flag=total<0 if kind==10 else total>0xffffffff
            else:
                sx=x-0x100000000 if x&0x80000000 else x;sy=y-0x100000000 if y&0x80000000 else y
                total=sx-sy if kind==11 else sx+sy;flag=not -0x80000000<=total<=0x7fffffff
            assert lib.regget(1)==total&0xffffffff and (lib.regget(3)&1)==flag;checks+=1
    for _ in range(256):
        x,y=rng.getrandbits(32),rng.getrandbits(32);lib.reset();lib.regset(1,x);lib.regset(2,y);lib.execute(0x0127);lib.execute(0x031a);assert lib.regget(3)==x*y&0xffffffff;checks+=1
    result=dict(passed=True,checks=checks,seed=5095,command=command,scope='Native value checks for register banks, control registers, load/store forms, FPU bit transfers, shifts, CMP/STR, MUL.L, carry and overflow; not full CPU conformance')
    (ROOT/'reports/cpu-extension-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:
    import _ctypes
    _ctypes.FreeLibrary(lib._handle)
