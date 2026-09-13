"""Shared locations for reproducible builds and isolated developer builds."""
import os
import pathlib

def keep_awake():
    """Allow the monitor to turn off while a Windows build keeps running."""
    if os.name == 'nt':
        import atexit
        import ctypes
        set_state = ctypes.windll.kernel32.SetThreadExecutionState
        set_state.argtypes = [ctypes.c_uint]
        set_state.restype = ctypes.c_uint
        set_state(0x80000001)
        atexit.register(set_state, 0x80000000)

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path(os.environ.get('SC5_WORK_DIR', ROOT / 'work')).resolve()

def compiler(cxx=False):
    explicit = os.environ.get('SC5_TOOLCHAIN')
    candidates = [pathlib.Path(explicit) / 'bin/clang.exe'] if explicit else list((WORK / 'toolchain').glob('*/bin/clang.exe'))
    candidates = [p for p in candidates if p.is_file()]
    if len(candidates) != 1:
        raise RuntimeError('Choose one LLVM-MinGW toolchain with --toolchain PATH or SC5_TOOLCHAIN.')
    return candidates[0].with_name('clang++.exe' if cxx else 'clang.exe').resolve()
