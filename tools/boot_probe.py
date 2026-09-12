"""Generate ahead-of-time C for observed native paths; unsupported targets trap.

Generation is offline. Forge's MIT notice is retained in prototype/.
"""
import argparse, hashlib, json, pathlib, struct, sys, zlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype/Dreamcast-Forge'))
from forge.sh4 import decode as forge_decode, Instruction
BASE=0x8c010000
EXPECTED='4bf74525eb2e4922c732c8b708d7a542a3a8f33693afa62019abf241df56dfe5'
# Observed exception trampoline copied by the game from 8c0bcde0 to VBR+600.
# Literals can be patched by the game; instruction bytes remain guarded at use.
RELOCATIONS=((0x8c00f400,0xace3c,0x34),(0x8c00f500,0xacda8,0x3c),(0x8c00f800,0xacda8,0x3c),(0x8c00fa00,0xacde0,0x60))
CODE_MODULES=(('ROUND1.BIN',0x8c270000,0x80000,'dce16d49c0943f5c96fdc8e7bbe18359997c52c241fc471a0bc0e81b555b8bd6'),)

def load_modules():
    result=[]
    for name,base,size,sha in CODE_MODULES:
        data=(ROOT/'extracted'/name).read_bytes()
        assert len(data)==size and hashlib.sha256(data).hexdigest()==sha,'Wrong code module revision: '+name
        result.append((name,base,data))
    return result

def decode(pc,w):
    n,m=(w>>8)&15,(w>>4)&15
    if w&0xf0ff==0xf07d:return Instruction(pc,w,'native reciprocal square root',f'float_extended({n},0,2);')
    if w&0xf1ff==0xf0fd:return Instruction(pc,w,'native fixed-angle sine/cosine',f'float_sincos({n&14});')
    if w&0xf0ff==0xf0ed:return Instruction(pc,w,'native vector inner product',f'float_inner({n&12},{(n&3)*4});')
    if w&0xf0ff in (0xf0ad,0xf0bd):return Instruction(pc,w,'native precision conversion',f'float_precision({n},{1 if w&0x10 else 0});')
    if w&0xf0ff==0x00c3:return Instruction(pc,w,'movca.l coherent store',f'wr(s.r[{n}],s.r[0],4);')
    if w&0xf3ff==0xf1fd:return Instruction(pc,w,'native matrix transform',f'float_transform({n&12});')
    if w&0xf00f==0x200d:return Instruction(pc,w,'xtrct',f's.r[{n}]=(s.r[{n}]>>16)|(s.r[{m}]<<16);')
    if w&0xf0ff==0xf06d:return Instruction(pc,w,'native floating square root',f'float_extended({n},0,0);')
    if w&0xf00f==0xf00e:return Instruction(pc,w,'native fused multiply-add',f'float_extended({n},{m},1);')
    if w&0xf08f in (0x0082,0x408e,0x4083,0x4087):
        bank=m&7;kind=w&0xf08f
        if kind==0x0082:code=f's.r[{n}]=s.bank[{bank}];'
        elif kind==0x408e:code=f's.bank[{bank}]=s.r[{n}];'
        elif kind==0x4083:code=f's.r[{n}]-=4;wr(s.r[{n}],s.bank[{bank}],4);'
        else:code=f'v=rd(s.r[{n}],4);if(!s.fault){{s.r[{n}]+=4;s.bank[{bank}]=v;}}'
        return Instruction(pc,w,'banked control transfer','if(!(s.sr&0x40000000u))s.fault=8;else {'+code+'}')
    if w&0xf0ff==0x0083:return Instruction(pc,w,'prefetch / store-queue flush',f'if((s.r[{n}]>>26)==0x38u){{if(external_queue_write)external_queue_write(s.r[{n}]);else s.fault=3;}}')
    if w&0xf0ff==0x4004:return Instruction(pc,w,'rotl',f's.t=s.r[{n}]>>31;s.r[{n}]=(s.r[{n}]<<1)|s.t;')
    if w&0xf0ff==0x4005:return Instruction(pc,w,'rotr',f's.t=s.r[{n}]&1u;s.r[{n}]=(s.r[{n}]>>1)|(s.t<<31);')
    if w&0xf00f in (0x200e,0x200f):
        value=f'(s.r[{n}]&0xffffu)*(s.r[{m}]&0xffffu)' if w&15==14 else f'(u32)((int32_t)(int16_t)s.r[{n}]*(int32_t)(int16_t)s.r[{m}])'
        return Instruction(pc,w,'multiply words',f's.macl={value};')
    if w&0xf00f in (0x3005,0x300d):
        value=f'(uint64_t)s.r[{n}]*s.r[{m}]' if w&15==5 else f'(uint64_t)((int64_t)(int32_t)s.r[{n}]*(int32_t)s.r[{m}])'
        return Instruction(pc,w,'multiply double long',f'{{uint64_t product={value};s.macl=(u32)product;s.mach=(u32)(product>>32);}}')
    if w&0xf0ff==0x401b:return Instruction(pc,w,'tas.b',f'v=rd(s.r[{n}],1);if(!s.fault){{s.t=(v==0);wr(s.r[{n}],v|0x80u,1);}}')
    if w==0x002b:return Instruction(pc,w,'rte',kind='return',expr='s.spc',delayed=True)
    if w in (0xfbfd,0xf3fd):
        return Instruction(pc,w,'floating bank/size toggle',f'if(s.sr&0x8000u)s.fault=10;else if(s.fpscr&0x80000u)s.fault=11;else set_fpscr(s.fpscr^0x{0x200000 if w==0xfbfd else 0x100000:x}u);')
    stack_controls={0x4003:'sr',0x4013:'gbr',0x4023:'vbr',0x4033:'ssr',0x4043:'spc',0x4002:'mach',0x4012:'macl',0x4022:'pr',0x4052:'fpul',0x4062:'fpscr'}
    key=w&0xf0ff
    is_load=key in {x+4 for x in stack_controls}
    if key in stack_controls or is_load:
        reg=stack_controls[key-4 if is_load else key];value='get_sr()' if reg=='sr' else f's.{reg}'
        if is_load:
            assign=f'set_{reg}(v);' if reg in ('sr','fpscr') else f's.{reg}=v;'
            code=f'v=rd(s.r[{n}],4);if(!s.fault){{s.r[{n}]+=4;{assign}}}'
        else:code=f'v={value};s.r[{n}]-=4;wr(s.r[{n}],v,4);'
        if reg in ('sr','vbr','ssr','spc'):code='if(!(s.sr&0x40000000u))s.fault=8;else {'+code+'}'
        if reg in ('fpul','fpscr'):code='if(s.sr&0x8000u)s.fault=10;else {'+code+'}'
        return Instruction(pc,w,'control stack transfer '+reg,code)
    if w&0xf0ff in (0xf00d,0xf01d,0xf02d,0xf03d):
        return Instruction(pc,w,'floating conversion/transfer',f'float_convert({n},{(w>>4)&15});')
    if w&0xf0ff in (0x0003,0x0023):
        return Instruction(pc,w,'braf' if w&0x20 else 'bsrf',kind='indirect' if w&0x20 else 'icall',expr=f's.pc+4u+s.r[{n}]',delayed=True)
    if w&0xf0ff in (0xf04d,0xf05d):
        operation='^=0x80000000u' if w&0xff==0x4d else '&=0x7fffffffu'
        return Instruction(pc,w,'floating sign',f'if(s.sr&0x8000u)s.fault=10;else if(s.fpscr&0x80000u)s.fault=11;else s.fr[{n}]{operation};')
    if w&0xf000==0xf000 and w&15<6:
        return Instruction(pc,w,'native floating arithmetic',f'float_arithmetic({n},{m},{w&15});')
    if w==0x0019:return Instruction(pc,w,'div0u','s.sr&=~0x300u;s.t=0;')
    if w&0xf00f==0x2007:return Instruction(pc,w,'div0s',f's.sr=(s.sr&~0x300u)|((s.r[{n}]>>31)<<8)|((s.r[{m}]>>31)<<9);s.t=((s.sr>>8)^(s.sr>>9))&1u;')
    if w&0xf00f==0x3004:return Instruction(pc,w,'div1',f'divide_step({n},{m});')
    if w&0xf0ff==0x4024:return Instruction(pc,w,'rotcl',f'v=s.r[{n}]>>31;s.r[{n}]=(s.r[{n}]<<1)|s.t;s.t=v;')
    if w&0xf0ff==0x4025:return Instruction(pc,w,'rotcr',f'v=s.r[{n}]&1u;s.r[{n}]=(s.r[{n}]>>1)|(s.t<<31);s.t=v;')
    if w&0xf00f in (0x300a,0x300b,0x300e,0x300f):
        return Instruction(pc,w,'carry/overflow arithmetic',f'arithmetic_flags({n},{m},{w&15});')
    if w&0xf00f==0x0007:return Instruction(pc,w,'mul.l',f's.macl=s.r[{n}]*s.r[{m}];')
    if w&0xf0ff in (0x000a,0x001a,0x400a,0x401a):
        reg='macl' if w&0x10 else 'mach'
        return Instruction(pc,w,f'MAC register {reg}',f's.{reg}=s.r[{n}];' if w&0x4000 else f's.r[{n}]=s.{reg};')
    if w&0xf00f in (0x400c,0x400d):
        return Instruction(pc,w,'shad' if w&15==12 else 'shld',f's.r[{n}]=dynamic_shift(s.r[{n}],s.r[{m}],{1 if w&15==12 else 0});')
    if w&0xf00f==0x200c:
        tests='||'.join(f'(((s.r[{n}]^s.r[{m}])&0x{255<<(8*j):08x}u)==0)' for j in range(4))
        return Instruction(pc,w,'cmp/str',f's.t=({tests});')
    if w&0xf00f==0x6008:
        return Instruction(pc,w,'swap.b',f's.r[{n}]=(s.r[{m}]&0xffff0000u)|((s.r[{m}]&255u)<<8)|((s.r[{m}]>>8)&255u);')
    if w&0xf00f==0x6009:
        return Instruction(pc,w,'swap.w',f's.r[{n}]=(s.r[{m}]<<16)|(s.r[{m}]>>16);')
    if w&0xf0ff in (0x005a,0x006a,0x405a,0x406a):
        reg='fpscr' if w&0x20 else 'fpul'
        code=f's.r[{n}]=s.{reg};' if not w&0x4000 else f's.{reg}=s.r[{n}];'
        if w&0x4000 and reg=='fpscr':code=f'set_fpscr(s.r[{n}]);'
        return Instruction(pc,w,f'floating control {reg}',f'if(s.sr&0x8000u)s.fault=10;else {{{code}}}')
    if w&0xf000==0xf000 and w&15 in (6,7,8,9,10,11,12):
        return Instruction(pc,w,'fmov',f'fmov_single({n},{m},{w&15});')
    if w&0xf0ff in (0xf08d,0xf09d):
        value=0x3f800000 if w&0x10 else 0
        return Instruction(pc,w,'fldi constant',f'if((s.sr&0x8000u)||(s.fpscr&0x80000u))s.fault=10;else s.fr[{n}]=0x{value:x}u;')
    if w&0xf0ff in (0x0093,0x00a3,0x00b3):
        return Instruction(pc,w,'operand-cache line operation',f'coherent_cache_line(s.r[{n}]);')
    controls={0x0012:'gbr',0x0022:'vbr',0x0032:'ssr',0x0042:'spc',0x003a:'sgr',0x00fa:'dbr'}
    if w&0xf0ff in controls:
        reg=controls[w&0xf0ff]
        code=f's.r[{n}]=s.{reg};'
        if reg!='gbr':code='if(!(s.sr&0x40000000u))s.fault=8;else '+code
        return Instruction(pc,w,f'stc {reg}',code)
    control_loads={0x401e:'gbr',0x402e:'vbr',0x403e:'ssr',0x404e:'spc',0x40fa:'dbr'}
    if w&0xf0ff in control_loads:
        reg=control_loads[w&0xf0ff];code=f's.{reg}=s.r[{n}];'
        if reg!='gbr':code='if(!(s.sr&0x40000000u))s.fault=8;else '+code
        return Instruction(pc,w,f'ldc {reg}',code)
    if w&0xff00 in (0x8000,0x8100,0x8400,0x8500):
        size=2 if w&0x100 else 1;addr=f's.r[{m}]+{(w&15)*size}u'
        code=f's.r[0]=sx(rd({addr},{size}),{size*8});' if w&0x400 else f'wr({addr},s.r[0],{size});'
        return Instruction(pc,w,'mov small displacement',code)
    if w&0xf00f in (0x0004,0x0005,0x0006,0x000c,0x000d,0x000e):
        size=1<<(w&3)
        code=f'wr(s.r[0]+s.r[{n}],s.r[{m}],{size});'
        if w&8:
            value=f'rd(s.r[0]+s.r[{m}],{size})'
            if size<4:value=f'sx({value},{size*8})'
            code=f's.r[{n}]={value};'
        return Instruction(pc,w,'mov R0 indexed',code)
    if w&0xf0ff==0x0002:
        return Instruction(pc,w,'stc SR,Rn',f'if(!(s.sr&0x40000000u))s.fault=8;else s.r[{n}]=get_sr();')
    if w&0xf0ff==0x400e:
        return Instruction(pc,w,'ldc Rn,SR',f'if(!(s.sr&0x40000000u))s.fault=8;else set_sr(s.r[{n}]);')
    if w&0xf0ff==0x4022:
        return Instruction(pc,w,'sts.l PR,@-Rn',f's.r[{n}]-=4;wr(s.r[{n}],s.pr,4);')
    if w&0xf0ff==0x4026:
        return Instruction(pc,w,'lds.l @Rn+,PR',f's.pr=rd(s.r[{n}],4);s.r[{n}]+=4;')
    return forge_decode(pc,w)

RUNTIME=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fenv.h>
#include <xmmintrin.h>
#include <math.h>
#pragma STDC FENV_ACCESS ON
#define OPTIONAL static inline __attribute__((unused))
typedef uint32_t u32;
#include "../tools/native_state.h"
static State s;
static u32 get_sr(void){return (s.sr&~1u)|s.t;}
static double get_dr(u32 index){uint64_t bits=((uint64_t)s.fr[index*2]<<32)|s.fr[index*2+1];double value;memcpy(&value,&bits,8);return value;}
static void set_dr(u32 index,double value){uint64_t bits;memcpy(&bits,&value,8);s.fr[index*2]=(u32)(bits>>32);s.fr[index*2+1]=(u32)bits;}
static void set_sr(u32 v){
 v&=0x700083f3u;
 u32 oldbank=(s.sr&0x60000000u)==0x60000000u,newbank=(v&0x60000000u)==0x60000000u;
 if(oldbank!=newbank)for(u32 j=0;j<8;j++){u32 tmp=s.r[j];s.r[j]=s.bank[j];s.bank[j]=tmp;}
 s.sr=v;s.t=v&1u;
}
static void set_fpscr(u32 v){
 v&=0x003fffffu;
 if((v^s.fpscr)&0x00200000u)for(u32 j=0;j<16;j++){u32 tmp=s.fr[j];s.fr[j]=s.xf[j];s.xf[j]=tmp;}
 s.fpscr=v;
}
static unsigned char internal_ram[0x1000000];
static unsigned char *ram=internal_ram;
typedef u32 (*BusRead)(u32,u32);
typedef void (*BusWrite)(u32,u32,u32);
static BusRead external_read;
static BusWrite external_write;
typedef void (*Retire)(u32,u32,u32);
static Retire external_retire;
#include "../tools/native_fast_clock.h"
#include "../tools/native_static_timing.h"
static NativeFastClock *external_clock;
static inline __attribute__((always_inline)) void native_static_count(NativeFastClock *clock,u32 opcode){
 const u32 info=native_static_timing[opcode],unit=info&255u,issue=info>>8;
 if(clock->last_unit==5 || unit==5 || (clock->last_unit==unit && unit!=0)){
  clock->last_unit=unit;*clock->counter-=issue;
 }else clock->last_unit=5;
}
static inline __attribute__((always_inline)) void native_retire(u32 opcode,u32 slot,u32 count){
 if(!external_retire)return;
 NativeFastClock *clock=external_clock;
 if(!clock || clock->initial_mem_ops<3){external_retire(opcode,slot,count);return;}
 native_static_count(clock,opcode);if(count==2)native_static_count(clock,slot);
 if(*clock->counter<=0 || opcode==0x002bu || (opcode&0xf0ffu)==0x400eu || (opcode&0xf0ffu)==0x4007u ||
    (count==2 && (slot==0x002bu || (slot&0xf0ffu)==0x400eu || (slot&0xf0ffu)==0x4007u)))clock->boundary(opcode,slot,count);
}
typedef int (*Service)(u32);
static Service external_service;
typedef void (*QueueWrite)(u32);
static QueueWrite external_queue_write __attribute__((unused));
static u32 deferred_code_guard;
/* Windows x64 scalar arithmetic uses SSE. Save and restore MXCSR directly;
   the generic MinGW fenv API also synchronizes x87 on every guest operation. */
static unsigned native_fp_begin(void){
 unsigned previous=_mm_getcsr();
 _mm_setcsr((previous&~0x603fu)|((s.fpscr&1u)?0x6000u:0u));
 return previous;
}
static int native_fp_flags(void){return (_mm_getcsr()&0x20u)?FE_INEXACT:0;}
static void native_fp_end(unsigned previous){_mm_setcsr(previous);}
/* Restricted single precision arithmetic. Unsupported exceptional values trap
   rather than silently substituting host-specific SH4 exception behavior. */
OPTIONAL void float_arithmetic(u32 n,u32 m,u32 kind){
 if(s.sr&0x8000u){s.fault=10;return;}
 if(s.fpscr&0x80000u){
  double x=get_dr(n>>1),y=get_dr(m>>1);
  if(kind==4){s.t=x==y;s.fpscr&=~0x3f000u;return;}
  if(kind==5){s.t=x>y;s.fpscr&=~0x3f000u;return;}
  if(kind>3){s.fault=11;return;}
  unsigned previous=native_fp_begin();
  volatile double result;switch(kind){case 0:result=x+y;break;case 1:result=x-y;break;case 2:result=x*y;break;default:result=x/y;break;}
  int flags=native_fp_flags();double value=result;native_fp_end(previous);(void)flags;set_dr(n>>1,value);s.fpscr&=~0x3f000u;return;
 }
 if((s.fpscr&3u)>1u){s.fault=11;return;}
 u32 a=s.fr[n],b=s.fr[m];
 float x,y;memcpy(&x,&a,4);memcpy(&y,&b,4);
 if(kind>=4){s.t=kind==4?x==y:x>y;s.fpscr&=~0x3f000u;return;}
 unsigned previous=native_fp_begin();
 volatile float result;
 switch(kind){case 0:result=x+y;break;case 1:result=x-y;break;case 2:result=x*y;break;default:result=x/y;break;}
 int flags=native_fp_flags();float value=result;native_fp_end(previous);
 /* Non-strict Flycast keeps IEEE exceptional results in the register file. */
 (void)flags;
 s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;
 memcpy(&s.fr[n],&value,4);
}
OPTIONAL void float_convert(u32 n,u32 kind){
 if(s.sr&0x8000u){s.fault=10;return;}
 if(kind<2){if(kind==0)s.fr[n]=s.fpul;else s.fpul=s.fr[n];return;}
 if((s.fpscr&3u)>1u){s.fault=11;return;}
 if(kind==2){
  if(s.fpscr&0x80000u){set_dr(n>>1,(double)(int32_t)s.fpul);return;}
  unsigned previous=native_fp_begin();
  volatile float result=(float)(int32_t)s.fpul;int flags=native_fp_flags();float value=result;native_fp_end(previous);
  (void)flags;s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;memcpy(&s.fr[n],&value,4);return;
 }
 if(kind==3){
  double x;
  if(s.fpscr&0x80000u)x=get_dr(n>>1);
  else {float q;memcpy(&q,&s.fr[n],4);x=(double)q;}
  if(!isfinite(x)||x>=2147483648.0||x< -2147483648.0){
   if(s.fpscr&0x800u){s.fault=11;return;} /* Enabled invalid-operation trap is not yet hosted. */
   s.fpul=(!isnan(x)&&x>0)?0x7fffffffu:0x80000000u;
   s.fpscr=(s.fpscr&~0x3f000u)|0x10040u;return;
  }
  int32_t result=(int32_t)x;int inexact=(double)result!=x;
  if(inexact&&(s.fpscr&0x80u)){s.fault=11;return;}
  s.fpul=(u32)result;s.fpscr&=~0x3f000u;if(inexact)s.fpscr|=0x1004u;
 }
}
OPTIONAL void float_transform(u32 n){
 if(s.sr&0x8000u){s.fault=10;return;}
 if((s.fpscr&0x80000u)||(s.fpscr&3u)>1u){s.fault=11;return;}
 float vector[4],matrix[16],result[4];
 for(u32 j=0;j<20;j++){
  u32 bits=j<4?s.fr[n+j]:s.xf[j-4];
  if(j<4)memcpy(&vector[j],&bits,4);else memcpy(&matrix[j-4],&bits,4);
 }
 unsigned previous=native_fp_begin();
 for(u32 row=0;row<4;row++){
  double sum=(double)matrix[row]*vector[0]+(double)matrix[row+4]*vector[1]+(double)matrix[row+8]*vector[2]+(double)matrix[row+12]*vector[3];
  result[row]=(float)sum;
 }
 int flags=native_fp_flags();native_fp_end(previous);
 (void)flags;
 s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;memcpy(s.fr+n,result,sizeof(result));
}
/* Table data from pinned Flycast sh4/fsca-table.h, GPL-2.0-or-later. */
static const u32 native_fsca_half[0x8000] __attribute__((unused))={
#include "../tools/native_fsca_table.inc"
};
OPTIONAL void float_sincos(u32 n){
 if(s.sr&0x8000u){s.fault=10;return;}if(s.fpscr&0x80000u){s.fault=11;return;}
 u32 angle=s.fpul&0xffffu,cosine=(angle+0x4000u)&0xffffu;
 s.fr[n]=native_fsca_half[angle&0x7fffu]^((angle&0x8000u)<<16);
 s.fr[n+1]=native_fsca_half[cosine&0x7fffu]^((cosine&0x8000u)<<16);
 s.fpscr&=~0x3f000u;
}
OPTIONAL void float_inner(u32 n,u32 m){
 if(s.sr&0x8000u){s.fault=10;return;}
 if((s.fpscr&0x80000u)||(s.fpscr&3u)>1u){s.fault=11;return;}
 float x[4],y[4];
 for(u32 j=0;j<4;j++){
  u32 a=s.fr[n+j],b=s.fr[m+j];
  memcpy(x+j,&a,4);memcpy(y+j,&b,4);
 }
 unsigned previous=native_fp_begin();
 double sum=(double)x[0]*y[0];for(u32 j=1;j<4;j++)sum+=(double)x[j]*y[j];volatile float converted=(float)sum;
 int flags=native_fp_flags();float result=converted;native_fp_end(previous);
 (void)flags;
 s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;memcpy(&s.fr[n+3],&result,4);
}
OPTIONAL void float_precision(u32 n,u32 to_single){
 if(s.sr&0x8000u){s.fault=10;return;}
 if(!(s.fpscr&0x80000u)||(n&1u)||(s.fpscr&3u)>1u){s.fault=11;return;}
 if(!to_single){
  u32 bits=s.fpul;float value;memcpy(&value,&bits,4);
  double result=value;uint64_t encoded;memcpy(&encoded,&result,8);s.fr[n]=(u32)(encoded>>32);s.fr[n+1]=(u32)encoded;s.fpscr&=~0x3f000u;
 }else{
  uint64_t bits=((uint64_t)s.fr[n]<<32)|s.fr[n+1];double value;memcpy(&value,&bits,8);
  unsigned previous=native_fp_begin();volatile float converted=(float)value;
  int flags=native_fp_flags();float result=converted;native_fp_end(previous);
  (void)flags;
  s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;memcpy(&s.fpul,&result,4);
 }
}
OPTIONAL void float_extended(u32 n,u32 m,u32 kind){
 if(s.sr&0x8000u){s.fault=10;return;}
 if((s.fpscr&0x80000u)||(s.fpscr&3u)>1u){s.fault=11;return;}
 u32 bits[3]={s.fr[n],s.fr[m],s.fr[0]};float values[3];
 for(u32 j=0;j<(kind==1?3u:1u);j++){
  memcpy(&values[j],&bits[j],4);
 }
 if(kind==2 && (!isfinite(values[0]) || values[0]<=0.0f)){
  volatile float special=1.0f/sqrtf(values[0]);memcpy(&s.fr[n],&special,4);s.fpscr&=~0x3f000u;return;
 }
 if(kind!=1&&values[0]<0){
  volatile float special=sqrtf(values[0]);memcpy(&s.fr[n],&special,4);s.fpscr&=~0x3f000u;return;
 }
 unsigned previous=native_fp_begin();
 volatile float result=kind==1?fmaf(values[2],values[1],values[0]):kind==2?1.f/sqrtf(values[0]):sqrtf(values[0]);
 int flags=native_fp_flags();float value=result;native_fp_end(previous);
 (void)flags;
 s.fpscr&=~0x3f000u;if(flags&FE_INEXACT)s.fpscr|=0x1004u;memcpy(&s.fr[n],&value,4);
}
static u32 fault_address,ccr,model_ccr,steps,cable=3,host_services,intc[4];
static u32 sx(u32 x,u32 bits){u32 b=1u<<(bits-1);return (x^b)-b;}
OPTIONAL u32 dynamic_shift(u32 value,u32 count,u32 arithmetic){
 if(!(count&0x80000000u))return value<<(count&31u);
 u32 amount=(0u-count)&31u,sign=0u-(value>>31);
 if(!amount)return arithmetic?sign:0;
 return (value>>amount)|(arithmetic?(sign<<(32u-amount)):0);
}
OPTIONAL void arithmetic_flags(u32 n,u32 m,u32 kind){
 u32 a=s.r[n],b=s.r[m],value;
 if(kind==14){uint64_t total=(uint64_t)a+b+s.t;value=(u32)total;s.t=(u32)(total>>32);}
 else if(kind==10){uint64_t sub=(uint64_t)b+s.t;value=a-(u32)sub;s.t=(uint64_t)a<sub;}
 else if(kind==15){value=a+b;s.t=((~(a^b)&(a^value))>>31);}
 else {value=a-b;s.t=(((a^b)&(a^value))>>31);}
 s.r[n]=value;
}
OPTIONAL void divide_step(u32 n,u32 m){
 u32 oldq=(s.sr>>8)&1u,mbit=(s.sr>>9)&1u,sign=s.r[n]>>31,operand=s.r[m];
 s.r[n]=(s.r[n]<<1)|s.t;
 u32 before=s.r[n],carry;
 if(oldq==mbit){s.r[n]-=operand;carry=s.r[n]>before;}
 else {s.r[n]+=operand;carry=s.r[n]<before;}
 u32 q=sign^carry^mbit;s.sr=(s.sr&~0x100u)|(q<<8);s.t=q==mbit;
}
static inline __attribute__((always_inline)) u32 offset(u32 a,u32 z){
 u32 p=a&0x1fffffffu,seg=a>>29;
 if((seg!=0 && seg!=4 && seg!=5)||p<0x0c000000u||p>0x0d000000u-z||(a&(z-1))){s.fault=3;fault_address=a;return 0;}
 return p-0x0c000000u;
}
static inline __attribute__((always_inline)) u32 rd(u32 a,u32 z){
 if(a&(z-1u)){s.fault=3;fault_address=a;return 0;}
 u32 physical=a&0x1fffffffu;
 if(external_read && !(physical>=0x0c000000u && physical<0x0d000000u))return external_read(a,z);
 if(model_ccr && a==0xff00001cu && z==4){printf("CCR read %08X at %08X\n",ccr,s.pc);return ccr;}
 /* Only cable-sense bits are modeled. This game's accessor masks 0x0300. */
 if(model_ccr && s.pc==0x8c0814e2u && a==0xff800030u && z==2){printf("Cable sense %u at %08X\n",cable,s.pc);return cable<<8;}
 if(host_services && z==2 && a>=0xffd00000u && a<=0xffd0000cu && !(a&3u))return intc[(a-0xffd00000u)/4];
 u32 o=offset(a,z),v=0;if(s.fault)return 0;
 /* Windows x64 is little-endian. Fixed-width memcpy avoids aliasing UB and
    lets the compiler use one load after the existing bounds/alignment check. */
 if(z==4){memcpy(&v,ram+o,4);return v;}
 if(z==2){uint16_t value;memcpy(&value,ram+o,2);return value;}
 for(u32 j=0;j<z;j++)v|=(u32)ram[o+j]<<(j*8);return v;
}
static int translated(u32 physical);
static inline __attribute__((always_inline)) void wr(u32 a,u32 v,u32 z){
 if(a&(z-1u)){s.fault=3;fault_address=a;return;}
 if(s.fault)return;
 u32 physical=a&0x1fffffffu;
 if(external_write && !(physical>=0x0c000000u && physical<0x0d000000u)){external_write(a,v,z);return;}
 if(model_ccr && a==0xff00001cu && z==4){ccr=v;printf("CCR write %08X at %08X\n",ccr,s.pc);return;}
 if(host_services && z==2 && a>=0xffd00000u && a<=0xffd0000cu && !(a&3u)){
  u32 index=(a-0xffd00000u)/4;intc[index]=v&(index?0xffffu:0x4380u);
  printf("INTC configuration %08X=%04X at %08X\n",a,intc[index],s.pc);return;
 }
 u32 o=offset(a,z);if(s.fault)return;
 if(!deferred_code_guard)for(u32 j=0;j<z;j++)if(translated((o+j+0x0c000000u)&~1u)){s.fault=4;fault_address=a;return;}
 if(z==4){memcpy(ram+o,&v,4);return;}
 if(z==2){uint16_t value=(uint16_t)v;memcpy(ram+o,&value,2);return;}
 for(u32 j=0;j<z;j++)ram[o+j]=(unsigned char)(v>>(j*8));
}
OPTIONAL void coherent_cache_line(u32 address){
 /* AOT RAM is coherent and has no separate dirty cache copy. Bounds are still
    enforced, and translated instruction bytes are checked at every execution. */
 (void)offset(address&~31u,4);
}
OPTIONAL void fmov_single(u32 n,u32 m,u32 kind){
 if(s.sr&0x8000u){s.fault=10;return;}
 if(s.fpscr&0x100000u){
  /* FMOV pairs preserve word order; double arithmetic has a separate layout.
     Odd encodings select XF pairs, not odd FR register indices. */
  u32 *dst=(n&1u)?s.xf:s.fr,*src=(m&1u)?s.xf:s.fr;
  u32 ni=n&14u,mi=m&14u,address,low,high;
  if(kind==12){low=src[mi];high=src[mi+1];dst[ni]=low;dst[ni+1]=high;return;}
  if(kind==6 || kind==8 || kind==9){
   address=s.r[m]+(kind==6?s.r[0]:0u);
   low=rd(address,4);high=rd(address+4,4);
   if(!s.fault){dst[ni]=low;dst[ni+1]=high;if(kind==9)s.r[m]+=8;}
  }else{
   address=s.r[n]+(kind==7?s.r[0]:0u)-(kind==11?8u:0u);
   low=src[mi];high=src[mi+1];wr(address,low,4);wr(address+4,high,4);
   if(!s.fault && kind==11)s.r[n]=address;
  }
  return;
 }
 u32 value;
 switch(kind){
 case 6:value=rd(s.r[0]+s.r[m],4);if(!s.fault)s.fr[n]=value;break;
 case 7:wr(s.r[0]+s.r[n],s.fr[m],4);break;
 case 8:value=rd(s.r[m],4);if(!s.fault)s.fr[n]=value;break;
 case 9:value=rd(s.r[m],4);if(!s.fault){s.fr[n]=value;s.r[m]+=4;}break;
 case 10:wr(s.r[n],s.fr[m],4);break;
 case 11:wr(s.r[n]-4,s.fr[m],4);if(!s.fault)s.r[n]-=4;break;
 case 12:s.fr[n]=s.fr[m];break;
 }
}
static void sysinfo(void){
 printf("SYSINFO function=%u r4=%08X r5=%08X pr=%08X\n",s.r[7],s.r[4],s.r[5],s.pr);
 if(s.r[7]==0){
  /* Virtual native-host identity, not a dump of a physical console's flash.
     Reserved/system property bytes are defined as zero in this dev profile. */
  static const unsigned char profile[24]={'S','C','5','N','A','T','I','V',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
  for(u32 j=0;j<24;j++)wr(0x8c000068u+j,profile[j],1);
  s.r[0]=0;
 }else if(s.r[7]==3)s.r[0]=0x8c000068u;
 else {s.fault=9;return;}
 s.pc=s.pr;
}
'''

def generate(blob, extra_roots=()):
    assert hashlib.sha256(blob).hexdigest()==EXPECTED,'Wrong executable revision'
    jump=struct.unpack_from('<I',blob,0x2c)[0]
    # Literal backing the JMP at 8c043754, observed in the native trace.
    init=struct.unpack_from('<I',blob,0x33878)[0]
    roots=list(dict.fromkeys([BASE,jump,init,*extra_roots]))
    pending=roots.copy(); found={}; slots=set(); jump_tables=[]
    modules=load_modules() if extra_roots else []
    prologue_roots=[]
    if extra_roots:
        def stack_push(word):return word&0xff0f in (0x2f06,0xff0b) or word==0x4f22
        for name,base,data in [('1ST_READ.BIN',BASE,blob),*modules]:
            words=struct.unpack('<'+'H'*(len(data)//2),data)
            for index in range(len(words)-1):
                saves_then_allocates=words[index]==0x4f22 and words[index+1]&0xff80==0x7f80
                interleaved_save=index+2<len(words) and words[index+1]&0xf000==0xd000 and stack_push(words[index+2])
                if stack_push(words[index]) and (stack_push(words[index+1]) or saves_then_allocates or interleaved_save) and (index==0 or not stack_push(words[index-1])):
                    address=base+index*2;pending.append(address);prologue_roots.append(address)
    def source_bytes(pc,size):
        if BASE<=pc and pc+size<=BASE+len(blob):return blob[pc-BASE:pc-BASE+size]
        for name,base,data in modules:
            if base<=pc and pc+size<=base+len(data):return data[pc-base:pc-base+size]
        for destination,source,length in RELOCATIONS:
            if destination<=pc and pc+size<=destination+length:return blob[source+pc-destination:source+pc-destination+size]
        return None
    def at(pc):
        if pc%2:return None
        data=source_bytes(pc,2)
        return decode(pc,struct.unpack('<H',data)[0]) if data is not None else None
    pointer_roots=set()
    if extra_roots:
        def short_leaf(address):
            todo=[address];seen=set();has_return=False
            while todo:
                pc=todo.pop()
                if pc in seen:continue
                if not address<=pc<address+96 or len(seen)>=40:return False
                seen.add(pc);instruction=at(pc)
                if instruction is None or instruction.kind in ('unsupported','call','icall','indirect'):return False
                if instruction.delayed:
                    slot=at(pc+2)
                    if slot is None or slot.kind!='normal':return False
                if instruction.word==0x000b:has_return=True;continue
                if instruction.kind=='return':return False
                if instruction.kind=='normal':todo.append(pc+2)
                elif instruction.target is not None:
                    todo.append(instruction.target)
                    if instruction.kind=='conditional':todo.append(pc+(4 if instruction.delayed else 2))
                else:return False
            return has_return
        # Aligned original-image pointers to stack-saving entries include small
        # callbacks without a multi-save prologue. These remain candidates;
        # execution still verifies every instruction against the original bytes.
        for name,base,data in [('1ST_READ.BIN',BASE,blob),*modules]:
            for (value,) in struct.iter_unpack('<I',data[:len(data)&~3]):
                if value>>29 not in (0,4,5) or value&1:continue
                address=(value&0x1fffffff)|0x80000000
                instruction=at(address)
                following=at(address+2) if instruction is not None else None
                saved_entry=instruction is not None and stack_push(instruction.word) and following is not None and following.kind=='normal'
                if instruction is not None and (saved_entry or short_leaf(address)):pointer_roots.add(address)
        pending.extend(sorted(pointer_roots))
    while pending:
        pc=pending.pop()
        if pc in found:continue
        i=at(pc)
        if i is None:continue
        found[pc]=i
        if len(found)>400000:raise ValueError('Analysis limit')
        if i.kind=='unsupported':continue
        if i.delayed:
            slot=at(pc+2)
            if slot is None or slot.kind!='normal' or slot.name=='mova' or 'PC-relative' in slot.name:continue
            slots.add(pc+2)
        if i.kind=='normal':pending.append(pc+2)
        if i.target is not None:pending.append(i.target)
        # Recognize the bounded SH compiler switch-table sequence observed at
        # 8c0459d6..8c0459e6. Table words are offsets, never executable roots.
        if extra_roots and i.word==0x0023 and source_bytes(pc-14,18) is not None:
            words=struct.unpack('<9H',source_bytes(pc-14,18))
            count=0
            if words[3:5]==(0x4000,0x6103) and words[5]&0xff00==0xc700 and words[6:]==(0x001d,0x0023,0x0009):
                if words[0]&0xff00==0xe100 and words[1]==0x3012 and words[2]&0xff00==0x8900:count=words[0]&255
                elif source_bytes(pc-18,10) is not None:
                    guard=struct.unpack('<5H',source_bytes(pc-18,10))
                    if guard[0]&0xff00==0xe100 and guard[1:3]==(0x3012,0x8b01) and guard[3]&0xf000==0xa000 and guard[4]==0x0009:count=guard[0]&255
                table=(pc&~3)+(words[5]&255)*4
                if 0<count<=127 and source_bytes(table,count*2) is not None:
                    targets=[pc+4+x for x in struct.unpack('<'+'h'*count,source_bytes(table,count*2))]
                    if all(at(target) is not None for target in targets):
                        pending.extend(targets);jump_tables.append(dict(branch=hex(pc),table=hex(table),targets=[hex(x) for x in targets]))
        # Resolve nearby literal-loaded call/jump targets offline. Stop at any
        # control-flow boundary or mention of that register; execution still
        # checks the destination bytes, including speculative coverage.
        if extra_roots and i.kind in ('icall','indirect'):
            match=re.fullmatch(r's\.r\[(\d+)\]',i.expr)
            if match:
                register=match[1]
                for distance in range(2,10,2):
                    previous=at(pc-distance)
                    if previous is None or previous.kind!='normal':break
                    literal=re.fullmatch(r's\.r\['+register+r'\]=rd\(0x([0-9a-f]+)u,4\);',previous.code)
                    if literal:
                        data=source_bytes(int(literal[1],16),4)
                        if data is not None:
                            candidate=struct.unpack('<I',data)[0];candidate=(candidate&0x1fffffff)|0x80000000
                            if at(candidate) is not None:pending.append(candidate)
                        break
                    if f's.r[{register}]' in previous.code:break
        if i.kind in ('conditional','call','icall'):pending.append(pc+(4 if i.delayed else 2))
    rows=[RUNTIME,f'#define EXPECTED_CRC32 0x{zlib.crc32(blob):08x}u','static int translated(u32 p){switch(p){']
    rows += [f'case 0x{p&0x1fffffff:08x}u:' for p in sorted(set(found)|slots)]
    rows += ['return 1;default:return 0;}}']
    pages=[];active_page=None
    for pc,i in sorted(found.items()):
        page=pc>>10
        if page!=active_page:
            if active_page is not None:rows.append('default:s.fault=2;break;}}return 1;}')
            pages.append(page);active_page=page
            rows.append(f'static int page_{page:x}(u32 budget){{u32 v,target,rte_old_sr,rte_new_sr;(void)v;(void)target;(void)rte_old_sr;(void)rte_new_sr;while(!s.fault && steps<budget && (s.pc&0x1ffffc01u)==0x{(page<<10)&0x1fffffff:x}u && (s.pc<0x20000000u || (s.pc&0xc0000000u)==0x80000000u)){{switch((s.pc&0x1fffffffu)|0x80000000u){{')
        rows.append(f'case 0x{pc:08x}u: label_{pc:x}: /* {i.word:04x} {i.name} */')
        # Executable roots are in the attached 16 MiB RAM image. Keep the same
        # per-instruction byte guard, but avoid the generic data-bus dispatcher.
        assert 0x0c000000 <= (pc & 0x1fffffff) < 0x0d000000-1
        code_offset=(pc&0x1fffffff)-0x0c000000
        rows.append(f'if((ram[0x{code_offset:x}u]|((u32)ram[0x{code_offset+1:x}u]<<8))!=0x{i.word:04x}u){{s.fault=7;break;}}')
        if i.kind=='unsupported':rows.append('s.fault=5;break;');continue
        slot=at(pc+2) if i.delayed else None
        if i.delayed and pc+2 not in slots:rows.append('s.fault=6;break;');continue
        cost=2 if i.delayed else 1
        rows.append(f'if(budget-steps<{cost})return 0;')
        if i.kind=='normal':
            code=i.code
            if i.name=='mova':code=f's.r[0]=(s.pc&0xe0000000u)|0x{(((pc+4)&~3)+(i.word&255)*4)&0x1fffffff:08x}u;'
            continuation=''
            if pc+2 in found and (pc+2)>>10==page:
                continuation=f'if(s.pc==0x{pc+2:08x}u&&!s.fault&&steps<budget)goto label_{pc+2:x};'
            rows.append(code+f'if(!s.fault){{s.pc+=2;steps++;native_retire(0x{i.word:04x},0,1);}}'+continuation+'break;');continue
        if slot:
            assert code_offset+3<0x1000000
            rows.append(f'if((ram[0x{code_offset+2:x}u]|((u32)ram[0x{code_offset+3:x}u]<<8))!=0x{slot.word:04x}u){{s.fault=7;break;}}')
        target=f'((s.pc&0xe0000000u)|0x{i.target&0x1fffffff:08x}u)' if i.target is not None else i.expr
        if i.kind=='conditional':target=f'({i.expr})?{target}:s.pc+{cost*2}u'
        rows.append(f'target={target};')
        if i.name=='rte':rows.append('if(!(s.sr&0x40000000u)){s.fault=8;break;}rte_old_sr=get_sr();s.sr=s.ssr&0x700083f3u;s.t=s.sr&1u;')
        if i.kind in ('call','icall'):rows.append('s.pr=s.pc+4u;')
        if slot:
            rows.append(slot.code)
        if i.name=='rte':rows.append('rte_new_sr=get_sr();s.sr=rte_old_sr;set_sr(rte_new_sr);')
        # Statically known intra-page branches can link directly too. Retire
        # may deliver an interrupt, so test the resulting PC before linking.
        successors=[]
        if i.target is not None:successors.append(i.target)
        if i.kind=='conditional':successors.append(pc+cost*2)
        continuation=''.join(f'if(s.pc==0x{next_pc:08x}u&&!s.fault&&steps<budget)goto label_{next_pc:x};'
                             for next_pc in dict.fromkeys(successors) if next_pc in found and next_pc>>10==page)
        rows.append(f'if(!s.fault){{s.pc=target;steps+={cost};native_retire(0x{i.word:04x},0x{slot.word if slot else 0:04x},{cost});}}'+continuation+'break;')
    rows.append('default:s.fault=2;break;}}return 1;}')
    rows.append('static void run(u32 budget){while(!s.fault && steps<budget){u32 segment=s.pc>>29;if((segment!=0&&segment!=4&&segment!=5)||(s.pc&1u)){s.fault=3;fault_address=s.pc;break;}if(external_service&&external_service(s.pc)){steps++;continue;}if(host_services && s.pc==0x8c000100u){sysinfo();steps++;continue;}switch(((s.pc&0x1fffffffu)|0x80000000u)>>10){')
    rows.extend(f'case 0x{page:x}:if(!page_{page:x}(budget))return;break;' for page in pages)
    rows+=['default:s.fault=2;break;}}}',r'''
int main(int argc,char**argv){
 if(argc<2){fprintf(stderr,"usage: sc5-boot-probe.exe 1ST_READ.BIN [--model-ccr]\n");return 2;}
 FILE*f=fopen(argv[1],"rb");if(!f)return 2;
 size_t n=fread(ram+0x10000,1,0x260000,f);int extra=fgetc(f);fclose(f);
 if(n!=0x260000||extra!=EOF){fprintf(stderr,"Wrong image size\n");return 2;}
 u32 crc=0xffffffffu;for(size_t j=0;j<n;j++){crc^=ram[0x10000+j];for(u32 k=0;k<8;k++)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);}
 if((crc^0xffffffffu)!=EXPECTED_CRC32){fprintf(stderr,"Wrong executable checksum\n");return 2;}
 model_ccr=argc>2&&!strcmp(argv[2],"--model-ccr");
 host_services=argc>3&&!strcmp(argv[3],"--host-services");
 if(host_services)wr(0x8c0000b0u,0x8c000100u,4);
 /* Canonical P1 entry. IP.BIN uses the P2 alias ac010000, same physical RAM.
    Stack and return address follow the inspected bootstrap handoff. */
 s.pc=0x8c010000;s.pr=0xac00e0b0;s.r[15]=0x8c00f400;s.vbr=0x8c00f400;set_sr(0x700000f0u);set_fpscr(0x40000);
 run(10000000);
 printf("HALT fault=%u pc=%08X address=%08X retired=%u ccr=%08X\n",s.fault,s.pc,fault_address,steps,ccr);
 for(u32 j=0;j<16;j++)printf("r%u=%08X%c",j,s.r[j],j==15?'\n':' ');
 return 0; /* Expected diagnostic halt; never means game boot succeeded. */
}
''']
    report=dict(image_sha256=EXPECTED,base=hex(BASE),roots=[hex(p) for p in roots],instructions=len(found),resolved_jump_tables=jump_tables,unsupported=[dict(pc=hex(p),opcode=hex(i.word)) for p,i in sorted(found.items()) if i.kind=='unsupported'],indirect=[hex(p) for p,i in found.items() if i.kind in ('indirect','icall','return')])
    report['code_modules']=[dict(name=name,base=hex(base),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,base,data in modules]
    report['static_prologue_candidates']=[hex(pc) for pc in prologue_roots]
    report['static_function_pointer_candidates']=[hex(pc) for pc in sorted(pointer_roots)]
    return '\n'.join(rows),report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',action='append',type=lambda x:int(x,0),default=[]);ap.add_argument('--recorded-roots',action='store_true');args=ap.parse_args()
    if args.recorded_roots:
        args.root += [int(x['pc'],16) for x in json.loads((ROOT/'reports/observed-roots.json').read_text())]
    blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes(); source,report=generate(blob,args.root)
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/sc5-boot-probe.c').write_text(source)
    (ROOT/'reports/boot-analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
