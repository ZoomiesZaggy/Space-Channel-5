"""Compare a finalized native WAV with an independently decoded original ADX WAV."""
import argparse,pathlib,wave,json,hashlib
import numpy as np
root=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--native',required=True);parser.add_argument('--reference',required=True);args=parser.parse_args()
def read(path):
    with wave.open(str(path)) as f:
        assert f.getframerate()==44100 and f.getnchannels()==2 and f.getsampwidth()==2
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).astype(np.float64)
native=read(args.native);reference=read(args.reference)
assert len(native)>=len(reference)>0,'Wait for a finalized full native opening capture before comparing'
a=native[::8,0];b=reference[::8,0]
size=1<<((len(a)+len(b)-1).bit_length())
correlation=np.fft.irfft(np.fft.rfft(a,size)*np.conj(np.fft.rfft(b,size)),size)
limit=max(1,len(a)-len(b)+1);coarse=int(np.argmax(correlation[:limit]))*8
best=None
for offset in range(max(0,coarse-16),coarse+17):
    length=min(len(native)-offset,len(reference));x=native[offset:offset+length];y=reference[:length]
    score=float(np.sum(x*y)/np.sqrt(np.sum(x*x)*np.sum(y*y)))
    if best is None or score>best['correlation']:
        gain=float(np.sum(x*y)/np.sum(y*y));error=x-gain*y
        best=dict(offset_samples=offset,offset_seconds=offset/44100,compared_frames=length,correlation=score,gain=gain,rms_error=float(np.sqrt(np.mean(error*error))),native_peak=int(np.max(np.abs(native))),native_seconds=len(native)/44100,reference_seconds=len(reference)/44100)
best['scope']='Native device audio mix versus independently FFmpeg-decoded original DANRAN.SFD ADX. Correlation is not full audio or audiovisual timing conformance.'
best['native_wav_sha256']=hashlib.sha256(pathlib.Path(args.native).read_bytes()).hexdigest()
best['reference_wav_sha256']=hashlib.sha256(pathlib.Path(args.reference).read_bytes()).hexdigest()
(root/'reports/native-opening-audio-comparison.json').write_text(json.dumps(best,indent=2));print(json.dumps(best,indent=2))
