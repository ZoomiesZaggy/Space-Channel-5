"""Small, explicit SH-4 integer translator. Unsupported instructions fail closed.

This is a static code translator, not a Dreamcast hardware emulator. Code is
discovered from entry points. No opcode decoder is present in generated code.
"""
from dataclasses import dataclass
import struct

BASE = 0x8C010000
MAX_IMAGE = 4 * 1024 * 1024

def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value

@dataclass
class Instruction:
    pc: int
    word: int
    name: str
    code: str = ""
    kind: str = "normal"
    target: int | None = None
    expr: str = ""
    delayed: bool = False

def decode(pc, w):
    n, m, imm = (w >> 8) & 15, (w >> 4) & 15, w & 255
    rn, rm = f"s.r[{n}]", f"s.r[{m}]"
    def ins(name, code="", **kw):
        return Instruction(pc, w, name, code, **kw)
    if w == 0x0009: return ins("nop")
    if w == 0x0008: return ins("clrt", "s.t=0;")
    if w == 0x0018: return ins("sett", "s.t=1;")
    if w == 0x000B: return ins("rts", kind="return", expr="s.pr", delayed=True)
    if w & 0xF000 == 0xE000: return ins("mov #imm", f"{rn}=(u32){signed(imm,8)};")
    if w & 0xF000 == 0x7000: return ins("add #imm", f"{rn}+=(u32){signed(imm,8)};")
    if w & 0xF000 in (0xA000, 0xB000):
        return ins("bra" if w >> 12 == 10 else "bsr", kind="branch" if w >> 12 == 10 else "call",
                   target=(pc+4+signed(w&4095,12)*2)&0xFFFFFFFF, delayed=True)
    if w & 0xFF00 in (0x8900, 0x8B00, 0x8D00, 0x8F00):
        return ins({0x89:"bt",0x8B:"bf",0x8D:"bt/s",0x8F:"bf/s"}[w>>8],
                   kind="conditional", target=(pc+4+signed(imm,8)*2)&0xFFFFFFFF,
                   expr="s.t" if w&0x0200 == 0 else "!s.t", delayed=bool(w&0x0400))
    if w & 0xF0FF in (0x402B, 0x400B):
        return ins("jmp" if w&0x20 else "jsr", kind="indirect" if w&0x20 else "icall", expr=rn, delayed=True)
    if w & 0xF000 == 0xD000:
        return ins("mov.l PC-relative", f"{rn}=rd(0x{((pc+4)&~3)+imm*4:08x}u,4);")
    if w & 0xF000 == 0x9000:
        return ins("mov.w PC-relative", f"{rn}=sx(rd(0x{pc+4+imm*2:08x}u,2),16);")
    if w & 0xFF00 == 0xC700: return ins("mova", f"s.r[0]=0x{((pc+4)&~3)+imm*4:08x}u;")
    if w & 0xFF00 == 0x8800: return ins("cmp/eq #imm", f"s.t=(s.r[0]==(u32){signed(imm,8)});")
    if w & 0xFF00 in (0xC800,0xC900,0xCA00,0xCB00):
        code = {0xC8:f"s.t=((s.r[0]&{imm}u)==0);",0xC9:f"s.r[0]&={imm}u;",
                0xCA:f"s.r[0]^={imm}u;",0xCB:f"s.r[0]|={imm}u;"}[w>>8]
        return ins("immediate logic",code)
    ops = {
        0x6003:("mov",f"{rn}={rm};"),0x300C:("add",f"{rn}+={rm};"),
        0x3008:("sub",f"{rn}-={rm};"),0x2009:("and",f"{rn}&={rm};"),
        0x200A:("xor",f"{rn}^={rm};"),0x200B:("or",f"{rn}|={rm};"),
        0x2008:("tst",f"s.t=(({rn}&{rm})==0);"),0x6007:("not",f"{rn}=~{rm};"),
        0x600B:("neg",f"{rn}=0u-{rm};"),0x3000:("cmp/eq",f"s.t=({rn}=={rm});"),
        0x3002:("cmp/hs",f"s.t=({rn}>={rm});"),0x3006:("cmp/hi",f"s.t=({rn}>{rm});"),
        0x3003:("cmp/ge",f"s.t=(({rn}^0x80000000u)>=({rm}^0x80000000u));"),
        0x3007:("cmp/gt",f"s.t=(({rn}^0x80000000u)>({rm}^0x80000000u));"),
        0x600C:("extu.b",f"{rn}={rm}&255u;"),0x600D:("extu.w",f"{rn}={rm}&65535u;"),
        0x600E:("exts.b",f"{rn}=sx({rm}&255u,8);"),0x600F:("exts.w",f"{rn}=sx({rm}&65535u,16);"),
    }
    if w & 0xF00F in ops:
        return ins(*ops[w & 0xF00F])
    one = {
        0x4010:("dt",f"--{rn};s.t=({rn}==0);"),0x4011:("cmp/pz",f"s.t=({rn}<0x80000000u);"),
        0x4015:("cmp/pl",f"s.t=({rn}>0 && {rn}<0x80000000u);"),
        0x4000:("shll",f"s.t={rn}>>31;{rn}<<=1;"),0x4020:("shal",f"s.t={rn}>>31;{rn}<<=1;"),
        0x4001:("shlr",f"s.t={rn}&1;{rn}>>=1;"),
        0x4021:("shar",f"s.t={rn}&1;{rn}=({rn}>>1)|({rn}&0x80000000u);"),
        0x4008:("shll2",f"{rn}<<=2;"),0x4009:("shlr2",f"{rn}>>=2;"),
        0x4018:("shll8",f"{rn}<<=8;"),0x4019:("shlr8",f"{rn}>>=8;"),
        0x4028:("shll16",f"{rn}<<=16;"),0x4029:("shlr16",f"{rn}>>=16;"),
        0x0029:("movt",f"{rn}=s.t;"),0x002A:("sts pr",f"{rn}=s.pr;"),
        0x402A:("lds pr",f"s.pr={rn};"),
    }
    if w & 0xF0FF in one: return ins(*one[w & 0xF0FF])
    # Byte/word loads sign extend; postincrement suppresses increment if m==n.
    if w & 0xF00F in (0x6000,0x6001,0x6002,0x6004,0x6005,0x6006):
        size = 1 << (w & 3)
        value = f"rd({rm},{size})"
        if size < 4: value = f"sx({value},{size*8})"
        return ins("mov load",f"{rn}={value};" + (f"{rm}+={size};" if w&4 and m!=n else ""))
    if w & 0xF00F in (0x2000,0x2001,0x2002,0x2004,0x2005,0x2006):
        size = 1 << (w & 3)
        # Sample source before predecrement, including the m==n case.
        return ins("mov store", f"v={rm};" + (f"{rn}-={size};" if w&4 else "") + f"wr({rn},v,{size});")
    if w & 0xF000 == 0x5000: return ins("mov.l displacement load",f"{rn}=rd({rm}+{(w&15)*4}u,4);")
    if w & 0xF000 == 0x1000: return ins("mov.l displacement store",f"wr({rn}+{(w&15)*4}u,{rm},4);")
    return ins("unsupported",kind="unsupported")

def discover(blob, base=BASE, entries=None):
    if not blob or len(blob)%2: raise ValueError("SH-4 input must have a nonzero, even byte length.")
    if len(blob)>MAX_IMAGE: raise ValueError("This experimental compiler accepts binaries up to 4 MiB.")
    if base&1 or not 0x8C000000 <= base <= 0x8D000000-len(blob):
        raise ValueError("Load address must be aligned and fit in Dreamcast's 16 MiB RAM (0x8C000000–0x8CFFFFFF).")
    pending=list(entries or [base]); found={}; issues=[]
    def at(pc):
        if pc&1 or not base<=pc<base+len(blob)-1: return None
        return decode(pc,struct.unpack_from("<H",blob,pc-base)[0])
    while pending:
        pc=pending.pop()
        if pc in found: continue
        i=at(pc)
        if not i:
            issues.append(f"Target 0x{pc:08X} is outside this image or misaligned."); continue
        found[pc]=i
        if len(found)>150000: raise ValueError("Analysis limit reached: split the program into smaller entry-point regions.")
        if i.kind=="unsupported":
            issues.append(f"Unsupported opcode 0x{i.word:04X} at 0x{pc:08X}."); continue
        if i.delayed:
            slot=at(pc+2)
            if not slot or slot.kind!="normal" or "PC-relative" in slot.name or slot.name=="mova":
                issues.append(f"Unsupported delay slot at 0x{pc+2:08X}."); continue
        if i.kind=="normal": pending.append(pc+2)
        if i.target is not None: pending.append(i.target)
        if i.kind in ("conditional","call","icall"): pending.append(pc+(4 if i.delayed else 2))
    return found, sorted(set(issues))

RUNTIME = r'''
typedef unsigned int u32;
typedef unsigned char u8;
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API
#endif
typedef struct { u32 r[16],pc,pr,t,fault; } State;
static State s;
static u8 ram[0x1000000];
static u32 sx(u32 x,u32 bits) {u32 b=1u<<(bits-1);return (x^b)-b;}
static u32 offset(u32 a,u32 z) {
 u32 p=a&0x1fffffffu;
 if((a&0xe0000000u)!=0x80000000u && (a&0xe0000000u)!=0xa0000000u && (a&0xe0000000u)!=0) {s.fault=3;return 0;}
 if(p<0x0c000000u || p>0x0d000000u-z || a&(z-1)) {s.fault=3;return 0;}
 return p-0x0c000000u;
}
static u32 rd(u32 a,u32 z) {u32 o=offset(a,z),v=0,j;if(s.fault)return 0;for(j=0;j<z;j++)v|=(u32)ram[o+j]<<(j*8);return v;}
static void wr(u32 a,u32 v,u32 z) {u32 o=offset(a,z),j;if(s.fault)return;
 if(o<IMAGE_OFFSET+sizeof(image) && o+z>IMAGE_OFFSET){s.fault=4;return;}
 for(j=0;j<z;j++)ram[o+j]=(u8)(v>>(j*8));}
API void forge_reset(void) {u32 j;for(j=0;j<sizeof(ram);j++)ram[j]=0;for(j=0;j<16;j++)s.r[j]=0;
 for(j=0;j<sizeof(image);j++)ram[IMAGE_OFFSET+j]=image[j];
 s.pc=IMAGE_BASE;s.pr=0xffffffffu;s.t=0;s.fault=0;s.r[15]=0x8cfffff0u;}
API void forge_set(u32 r,u32 v){if(r<16)s.r[r]=v;}
API u32 forge_get(u32 r){return r<16?s.r[r]:0;}
API u32 forge_pc(void){return s.pc;}
API u32 forge_fault(void){return s.fault;}
API u32 forge_peek(u32 a,u32 z){if(z!=1 && z!=2 && z!=4)return 0;return rd(a,z);}
API void forge_begin(u32 pc){s.pc=pc;s.pr=0xffffffffu;s.fault=0;}
'''

def translate(blob, base=BASE, entries=None):
    found,issues=discover(blob,base,entries)
    if issues: raise ValueError("Cannot generate this binary:\n"+"\n".join(issues[:16]))
    rows=["/* Generated from SH-4 machine code by Dreamcast Forge 0.1. */",
          "static const unsigned char image[]={"+",".join(str(b) for b in blob)+"};",
          f"#define IMAGE_BASE 0x{base:08x}u\n#define IMAGE_OFFSET 0x{base-0x8c000000:x}u",RUNTIME,
          "API unsigned int forge_run(unsigned int budget){u32 steps=0,v=0,target=0;while(steps<budget){",
          "if(s.fault)return s.fault;if(s.pc==0xffffffffu)return 0;switch(s.pc){"]
    for pc,i in sorted(found.items()):
        rows.append(f"case 0x{pc:08x}u: /* {i.name} : {i.word:04x} */")
        cost=2 if i.delayed else 1
        rows.append(f"if(budget-steps<{cost})return 1;steps+={cost};")
        if i.kind=="normal": rows.append(i.code+f"s.pc=0x{pc+2:08x}u;break;"); continue
        target=f"0x{i.target:08x}u" if i.target is not None else i.expr
        if i.kind=="conditional": target=f"({i.expr})?{target}:0x{pc+(4 if i.delayed else 2):08x}u"
        rows.append(f"target={target};")
        if i.kind in ("call","icall"): rows.append(f"s.pr=0x{pc+4:08x}u;")
        if i.delayed: rows.append(decode(pc+2,struct.unpack_from("<H",blob,pc+2-base)[0]).code)
        rows.append("s.pc=target;break;")
    rows.append("default:s.fault=2;return 2;}if(s.fault)return s.fault;}return s.pc==0xffffffffu?0:1;}")
    rows.append(r'''
#ifdef FORGE_CONSOLE
#include <stdio.h>
int main(void){unsigned int i,result;forge_reset();result=forge_run(1000000);
 printf("status=%u pc=%08X\n",result,forge_pc());
 for(i=0;i<16;i++)printf("r%u=%u\n",i,forge_get(i));return result?1:0;}
#endif
''')
    return "\n".join(rows)
