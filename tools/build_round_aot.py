"""Build cached native AOT DLLs for the four round-specific code modules."""
import argparse, hashlib, json, pathlib, sys, re, subprocess, shutil
from boot_probe import ROOT, generate
from build_aot_split import build
from build_paths import keep_awake
keep_awake()

ap=argparse.ArgumentParser();ap.add_argument('--cc',required=True);ap.add_argument('--opt',choices=['0','1','2'],default='2');ap.add_argument('--round',type=int,action='append');ap.add_argument('--output-dir',type=pathlib.Path,default=ROOT/'build');ap.add_argument('--cpu',choices=['x86-64','x86-64-v3']);ap.add_argument('--no-math-errno',action='store_true');ap.add_argument('--cache-tag',default='');a=ap.parse_args()
if a.cache_tag and not re.fullmatch('[A-Za-z0-9_-]+',a.cache_tag):ap.error('cache tag must contain only letters, numbers, underscores, or hyphens')
target=subprocess.check_output([shutil.which(a.cc) or a.cc,'-dumpmachine'],text=True).strip()
suffix='.dll' if any(word in target for word in ('mingw','windows')) else '.dylib' if 'darwin' in target else '.so'
a.output_dir.mkdir(parents=True,exist_ok=True)
blob=(ROOT/'extracted/1ST_READ.BIN').read_bytes()
records=json.loads((ROOT/'reports/observed-roots.json').read_text())
roots=[int(x['pc'],16) for x in records]
rounds=a.round or [2,3,4]
reports=[]
for number in rounds:
 print(f'Generating ROUND{number} native code…',flush=True)
 data=(ROOT/'extracted'/f'ROUND{number}.BIN').read_bytes()
 digest=hashlib.sha256(data).hexdigest()
 import boot_probe as probe
 probe.CODE_MODULES=((f'ROUND{number}.BIN',0x8c270000,len(data),digest),)
 source,report=generate(blob,roots)
 source_path=ROOT/'build'/f'sc5-boot-probe-round{number}.c';source_path.write_text(source)
 (ROOT/'reports'/f'boot-analysis-round{number}.json').write_text(json.dumps(report,indent=2))
 output=a.output_dir/f'native-diff-round{number}{suffix}'
 result=build(a.cc,output,opt=a.opt,source_path=source_path,object_dir=f'aot-objects-round{number}'+(('-'+a.cpu) if a.cpu else '')+(('-'+a.cache_tag) if a.cache_tag else ''),cpu=a.cpu,math_errno=not a.no_math_errno)
 reports.append(dict(round=number,source_sha256=hashlib.sha256(source.encode()).hexdigest(),instructions=report['instructions'],unsupported=report['unsupported'],build=result))
 (ROOT/'reports/native-round-aot-build.json').write_text(json.dumps(reports,indent=2))
 print(f'ROUND{number}: {report["instructions"]} instructions -> {output}',flush=True)
