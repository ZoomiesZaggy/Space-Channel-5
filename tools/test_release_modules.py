"""Exercise the actual precompiled module ABI and floating point without game assets."""
import argparse
import ctypes as c
from pathlib import Path
import sys

Retire = c.CFUNCTYPE(None, c.c_uint32, c.c_uint32, c.c_uint32)
class OpcodeTiming(c.Structure):
    _fields_=[(name,c.c_uint8) for name in ('unit','issue','mem','padding')]
class FastClock(c.Structure):
    _fields_=[('counter',c.POINTER(c.c_int32)),('timing',c.POINTER(OpcodeTiming)),
              ('last_unit',c.c_uint32),('initial_mem_ops',c.c_uint32),('boundary',Retire)]

class State(c.Structure):
    _fields_=[('r',c.c_uint32*16), *[(n,c.c_uint32) for n in ('pc','pr','t','fault','sr')],
              ('bank',c.c_uint32*8), *[(n,c.c_uint32) for n in ('gbr','vbr','ssr','spc','sgr','dbr','fpul','fpscr')],
              ('fr',c.c_uint32*16),('xf',c.c_uint32*16),('mach',c.c_uint32),('macl',c.c_uint32)]

def check_clock_links(library):
    """Exercise real generated branch links with interrupt/fault/code changes.

    These four instructions already appear in the public generated source;
    this test needs no disc, assets, checkpoint or developer hardware.
    """
    table=(Path(__file__).parent/'native_static_timing.h').read_text().split('{',1)[1].split('}',1)[0]
    words=[int(word) for word in table.split(',') if word.strip()]
    assert len(words)==65536
    timing=(OpcodeTiming*65536)(*(OpcodeTiming(word&255,word>>8,0,0) for word in words))
    library.sc5_ram.restype=c.c_void_p
    library.sc5_set_retire.argtypes=[Retire]
    library.sc5_set_fast_clock.argtypes=[c.POINTER(FastClock)]
    library.sc5_run_chunk.argtypes=[c.c_uint32]
    library.sc5_run_chunk.restype=c.c_uint32
    ram=library.sc5_ram();state=library.sc5_context().contents
    counter=c.c_int32(0)
    calls=0
    @Retire
    def boundary(op,slot,count):
        nonlocal calls
        calls+=1;counter.value=1000
        if calls!=1:return
        if mode==1:state.pc=(state.pc&0xe0000000)|0x0c0100a2
        elif mode==2:state.fault=9
        elif mode==3:c.c_uint8.from_address(ram+(state.pc&0x1fffffff)-0x0c000000).value^=1
    clock=FastClock(c.pointer(counter),timing,5,3,boundary)
    try:
        for fast in (False,True):
            library.sc5_set_retire(boundary)
            library.sc5_set_fast_clock(c.pointer(clock) if fast else None)
            for segment in (0,0x80000000,0xa0000000):
                for taken in (0,1):
                    for mode in range(5):
                        for offset,word in ((0x10096,0x8902),(0x10098,0xe014),(0x1009e,0xf08d),(0x100a2,0x0009)):
                            c.memmove(ram+offset,word.to_bytes(2,'little'),2)
                        c.memset(c.addressof(state),0,c.sizeof(state))
                        state.pc=segment|0x0c010096;state.t=taken;state.r[0]=0x12345678;state.fr[0]=0x3f800000
                        calls=0;counter.value=0;clock.last_unit=5
                        retired=library.sc5_run_chunk(1 if mode==4 else 2)
                        target=segment|(0x0c01009e if taken else 0x0c010098)
                        if mode in (2,3):
                            assert (retired,state.fault,state.pc)==(1,9 if mode==2 else 7,target)
                        elif mode==4:assert (retired,state.fault,state.pc)==(1,0,target)
                        else:assert (retired,state.fault,state.pc)==(2,0,(segment|0x0c0100a4) if mode==1 else target+2)
                        assert state.r[0]==(20 if mode==0 and not taken else 0x12345678)
                        assert state.fr[0]==(0 if mode==0 and taken else 0x3f800000)
    finally:
        library.sc5_set_fast_clock(None);library.sc5_set_retire(Retire())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('build'))
    args=parser.parse_args()
    suffix='.dll' if sys.platform=='win32' else '.dylib' if sys.platform=='darwin' else '.so'
    assert c.sizeof(State)==284
    for number in range(1,5):
        library=c.CDLL(str((args.directory/f'native-diff-round{number}{suffix}').resolve()))
        library.sc5_context.restype=c.POINTER(State)
        library.sc5_reset.argtypes=[c.c_void_p]
        library.sc5_float.argtypes=[c.c_uint32,c.c_uint32,c.c_uint32]
        state=library.sc5_context().contents
        library.sc5_reset(c.create_string_buffer(0x260000))
        assert state.fault==12, 'Invalid disc must be rejected'
        cases=[(0,0x3f800000,0x34400000,0,0x3f800002,0x1004),
               (0,0x3f800000,0x34400000,1,0x3f800001,0x1005),
               (1,0x3fc00000,0x3f000000,0,0x3f800000,0),
               (2,0x3fc00000,0x40000000,0,0x40400000,0),
               (3,0x3f800000,0x40400000,0,0x3eaaaaab,0x1004),
               (3,0x3f800000,0x40400000,1,0x3eaaaaaa,0x1005)]
        for operation,left,right,rounding,expected,flags in cases:
            c.memset(c.addressof(state),0,c.sizeof(state))
            state.fr[0]=left;state.fr[1]=right;state.fpscr=rounding
            library.sc5_float(0,1,operation)
            assert state.fr[0]==expected and state.fpscr==flags and state.fault==0, (number,operation,rounding,hex(state.fr[0]),hex(state.fpscr))
        state.sr=0x8000;state.fr[0]=0x3f800000
        library.sc5_float(0,1,0)
        assert state.fault==10 and state.fr[0]==0x3f800000
        check_clock_links(library)
        print(f'ROUND{number}: module ABI, disc rejection, floating-point and 60 clock/branch checks passed',flush=True)

if __name__=='__main__':main()
