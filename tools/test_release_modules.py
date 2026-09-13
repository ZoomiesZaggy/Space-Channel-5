"""Exercise the actual precompiled module ABI and floating point without game assets."""
import argparse
import ctypes as c
from pathlib import Path
import sys

class State(c.Structure):
    _fields_=[('r',c.c_uint32*16), *[(n,c.c_uint32) for n in ('pc','pr','t','fault','sr')],
              ('bank',c.c_uint32*8), *[(n,c.c_uint32) for n in ('gbr','vbr','ssr','spc','sgr','dbr','fpul','fpscr')],
              ('fr',c.c_uint32*16),('xf',c.c_uint32*16),('mach',c.c_uint32),('macl',c.c_uint32)]

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
        print(f'ROUND{number}: module ABI, disc rejection and floating-point checks passed',flush=True)

if __name__=='__main__':main()
