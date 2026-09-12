"""Local compiler discovery; no downloads, shell interpolation, or profile scripts."""
import ctypes
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

FAULTS={0:"Returned normally",1:"Instruction budget exhausted",2:"Jumped to untranslated code",3:"Unmapped or misaligned memory access",4:"Write into the input image (self-modifying code is unsupported)"}

def compiler():
    for name in ("gcc","clang","cl"):
        found=shutil.which(name)
        if found: return found
    if sys.platform=="win32":
        # An installed MSVC toolchain can be used directly for this freestanding
        # DLL: no Windows SDK headers or C runtime library is needed.
        for var in ("ProgramFiles","ProgramFiles(x86)"):
            root=Path(os.environ.get(var,"C:/Program Files"))/"Microsoft Visual Studio"
            candidates=sorted(root.glob("*/BuildTools/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"),reverse=True)
            candidates+=sorted(root.glob("*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"),reverse=True)
            if candidates: return str(candidates[0])
    return None

def compile_c(source, output, exe=False):
    cc=compiler()
    if not cc: raise ValueError("To rebuild native code, install Visual Studio Build Tools with 'Desktop development with C++' on Windows, or GCC/Clang on Linux. The bundled demo does not need a compiler on Windows x64/Linux x64.")
    source,output=Path(source).resolve(),Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    if Path(cc).name.lower()=="cl.exe":
        if exe: raise ValueError("Console builds with MSVC require the Developer Command Prompt; use a GCC/Clang toolchain for this CLI option.")
        cmd=[cc,"/nologo","/Od","/Oi-","/GS-","/LD","/TC",str(source),"/Fo"+str(output.with_suffix(".obj")),"/link","/NOENTRY","/NODEFAULTLIB","/OUT:"+str(output)]
    else:
        cmd=[cc,"-O2","-fno-builtin","-std=c99",str(source),"-o",str(output)]
        cmd+= ["-DFORGE_CONSOLE"] if exe else (["-dynamiclib"] if sys.platform=="darwin" else ["-shared","-fPIC"])
    env=os.environ.copy();env["PATH"]=str(Path(cc).parent)+os.pathsep+env.get("PATH","")
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=120,cwd=output.parent,env=env)
    if result.returncode: raise ValueError("Compiler failed:\n"+(result.stdout+result.stderr)[-5000:])
    if not output.is_file(): raise ValueError("Compiler produced no output.")
    return output

def suffix(): return ".dll" if sys.platform=="win32" else ".dylib" if sys.platform=="darwin" else ".so"

class Native:
    # Windows port change, 2026-09-11: explicit lifetime releases loaded DLLs.
    def __init__(self,path):
        self.lib=ctypes.CDLL(str(Path(path).resolve()))
        for name,args,result in (("forge_reset",[],None),("forge_set",[ctypes.c_uint32]*2,None),
                ("forge_get",[ctypes.c_uint32],ctypes.c_uint32),("forge_begin",[ctypes.c_uint32],None),
                ("forge_run",[ctypes.c_uint32],ctypes.c_uint32),("forge_pc",[],ctypes.c_uint32),
                ("forge_fault",[],ctypes.c_uint32),("forge_peek",[ctypes.c_uint32]*2,ctypes.c_uint32)):
            f=getattr(self.lib,name);f.argtypes=args;f.restype=result
        self.lib.forge_reset()
    def close(self):
        if self.lib is None: return
        import _ctypes
        handle=self.lib._handle
        if sys.platform=="win32": _ctypes.FreeLibrary(handle)
        else: _ctypes.dlclose(handle)
        self.lib=None
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def set(self,r,value): self.lib.forge_set(r,value)
    def get(self,r): return self.lib.forge_get(r)
    def run(self,entry,budget=100000):
        self.lib.forge_begin(entry)
        return self.lib.forge_run(budget)

def bundled_name():
    arch=platform.machine().lower()
    if arch in ("amd64","x86_64") and ctypes.sizeof(ctypes.c_void_p)==8:
        if sys.platform=="win32": return "orbit-windows-x64.dll"
        if sys.platform=="linux": return "orbit-linux-x64.so"
    return None
