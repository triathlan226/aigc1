import wave,numpy as np,glob,sys
def load(f):
    w=wave.open(f);return np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(float)
def runs(x,th=300,minf=12):
    e=np.sqrt(np.convolve(x**2,np.ones(480)/480,'same'))[::480]
    sil=e<th; out=[];s=None
    for i,v in enumerate(list(sil)+[False]):
        if v and s is None:s=i
        if not v and s is not None:
            if i-s>=minf: out.append((s*0.02,i*0.02))
            s=None
    return out,sil
if __name__=="__main__":
  for f in sys.argv[1:]:
    x=load(f);r,sil=runs(x)
    print(f, round(len(x)/24000,1), "speech%",round(100*(1-sil.mean())), [(round(a,1),round(b-a,1)) for a,b in r])
