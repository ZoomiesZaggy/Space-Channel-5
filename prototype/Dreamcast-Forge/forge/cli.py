import argparse
import json
from pathlib import Path
from .sh4 import BASE,discover,translate
from .disc import Disc
from .build import compile_c,suffix

def main():
    p=argparse.ArgumentParser(description="Dreamcast Forge experimental SH-4 compiler")
    sub=p.add_subparsers(dest="command",required=True)
    inspect=sub.add_parser("inspect");inspect.add_argument("image",type=Path)
    for name in ("analyze","translate","build"):
        cmd=sub.add_parser(name);cmd.add_argument("binary",type=Path)
        cmd.add_argument("--base",type=lambda s:int(s,0),default=BASE)
        cmd.add_argument("--entry",type=lambda s:int(s,0),action="append")
        if name!="analyze":cmd.add_argument("--out",type=Path,required=True)
        if name=="build":cmd.add_argument("--console",action="store_true")
    args=p.parse_args()
    try:
        if args.command=="inspect":
            meta,blob=Disc(args.image).boot();print(json.dumps(meta,indent=2));return 0
        blob=args.binary.read_bytes()
        found,issues=discover(blob,args.base,args.entry)
        if args.command=="analyze":
            print(json.dumps({"instructions":len(found),"issues":issues,"retail_compatibility":"not established"},indent=2));return int(bool(issues))
        args.out.mkdir(parents=True,exist_ok=True)
        source=args.out/"recompiled.c";source.write_text(translate(blob,args.base,args.entry),encoding="utf-8")
        print(source)
        if args.command=="build":
            import sys
            name="program"+(".exe" if sys.platform=="win32" else "") if args.console else "program"+suffix()
            print(compile_c(source,args.out/name,args.console))
        return 0
    except (OSError,ValueError) as e:
        p.exit(1,str(e)+"\n")

if __name__=="__main__":raise SystemExit(main())
