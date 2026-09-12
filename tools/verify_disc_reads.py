import os
"""Compare native completion checksums with independent read-only track extraction."""
import hashlib,json,pathlib,re
from inspect_disc import Track
ROOT=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'reports/disc.json').read_text())
history=json.loads((ROOT/'reports/native-bus-expansion.json').read_text())
track=Track(pathlib.Path(os.environ['SC5_GDI']).resolve().parent/manifest['tracks'][2]['name'],45000)
results=[]
try:
    for match in re.finditer(r'Completed disc read FAD=(\d+) sectors=(\d+) FNV64=([a-f0-9]+)',history[-1]['stdout']):
        fad,sectors=int(match[1]),int(match[2]);data=track.read(fad-150,sectors*2048)
        value=14695981039346656037
        for byte in data:value=((value^byte)*1099511628211)&0xffffffffffffffff
        files=[f['path'] for f in manifest['files'] if f['lba']<=fad-150<f['lba']+(f['bytes']+2047)//2048]
        results.append(dict(fad=fad,sectors=sectors,bytes=len(data),files=files,fnv64=f'{value:016x}',native_fnv64=match[3],matches=value==int(match[3],16),source_sha256=hashlib.sha256(data).hexdigest()))
finally:track.f.close()
assert results,'No native completion checksums found'
(ROOT/'reports/native-disc-read-verification.json').write_text(json.dumps(results,indent=2))
assert all(r['matches'] for r in results),'Native disc-read checksum mismatch'
print(f'Verified {len(results)} native read completions, {sum(r["bytes"] for r in results)} bytes including sector padding')
