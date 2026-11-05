import json, numpy as np, wave
from sil import load
SR=24000
d=json.load(open("timeline.json")); tl=d["tl"]; total=d["total"]
N=int(total*SR)+SR
voice=np.zeros(N); 
for s in tl:
    x=load(f"aud2/{s['id']}.wav")/32768; i=int(s["t0"]*SR+s["audio"]*0+0.25*SR)
    i=int((s["t0"]+0.25)*SR); voice[i:i+len(x)]+=x
# --- lo-fi BGM: Cmaj7 - Am7 - Fmaj7 - G6, 88 bpm
t=np.arange(N)/SR; bpm=88; beat=60/bpm; bar=beat*4
def note(f): return 440*2**((f-69)/12)
chords=[[48,52,55,59],[45,48,52,55],[41,45,48,52],[43,47,50,52]]
music=np.zeros(N)
nb=int(total/bar)+2
rng=np.random.default_rng(1)
for b in range(nb):
    ch=chords[b%4]; s0=int(b*bar*SR); L=int(bar*SR)
    if s0>=N: break
    tt=np.arange(min(L,N-s0))/SR
    env=np.minimum(1,tt/0.3)*np.minimum(1,(bar-tt)/0.4)
    pad=sum(np.sin(2*np.pi*note(m+12)*tt+0.3*np.sin(2*np.pi*0.5*tt)) for m in ch)/4
    music[s0:s0+len(tt)]+=0.18*pad*env
    bass=np.sin(2*np.pi*note(ch[0]-12)*tt)*np.exp(-tt*1.2)
    music[s0:s0+len(tt)]+=0.22*bass
    for k in range(8):  # pluck arpeggio 8ths
        ps=s0+int(k*beat/2*SR); pl=int(0.5*SR)
        if ps+pl>=N: break
        tp=np.arange(pl)/SR; m=ch[[0,2,1,3,2,1,3,2][k]]+24
        pk=(np.sin(2*np.pi*note(m)*tp)+0.3*np.sin(4*np.pi*note(m)*tp))*np.exp(-tp*7)
        music[ps:ps+pl]+=0.07*pk*(0.8+0.2*rng.random())
    for k in range(4):  # soft kick on 1,3 + hat
        ps=s0+int(k*beat*SR); pl=int(0.25*SR)
        if ps+pl>=N: break
        tp=np.arange(pl)/SR
        if k%2==0: music[ps:ps+pl]+=0.25*np.sin(2*np.pi*(50+80*np.exp(-tp*30))*tp)*np.exp(-tp*14)
        hs=ps+int(beat/2*SR); hl=int(0.05*SR)
        if hs+hl<N: music[hs:hs+hl]+=0.025*rng.standard_normal(hl)*np.exp(-np.arange(hl)/SR*80)
# ducking: music lower under speech
e=np.convolve(np.abs(voice),np.ones(SR//5)/(SR//5),'same')
duck=np.where(e>0.01,0.35,1.0); duck=np.convolve(duck,np.ones(SR//4)/(SR//4),'same')
music*=duck*0.55
_r=[s for s in tl if s['id']=='rhythm'][0]; _b0=_r['t0']+_r['len']-7.3
music[int(_b0*SR):int((_b0+6.8)*SR)]*=0.3
# fade in/out
fi=int(1.5*SR); music[:fi]*=np.linspace(0,1,fi); fo=int(3*SR); end=int(total*SR); music[end-fo:end]*=np.linspace(1,0,fo); music[end:]=0
# --- sfx
sfx=np.zeros(N)
def ding(t0,f=1320,v=0.25):
    i=int(t0*SR); L=int(0.8*SR); tp=np.arange(L)/SR
    sfx[i:i+L]+=v*(np.sin(2*np.pi*f*tp)+0.5*np.sin(2*np.pi*f*1.5*tp))*np.exp(-tp*5)
def tick(t0):
    i=int(t0*SR); L=int(0.08*SR); tp=np.arange(L)/SR
    sfx[i:i+L]+=0.35*np.sin(2*np.pi*1000*tp)*np.exp(-tp*60)
def whoosh(t0):
    i=int(t0*SR); L=int(0.35*SR); nz=np.random.default_rng(2).standard_normal(L)
    nz=np.convolve(nz,np.ones(20)/20,'same'); sfx[i:i+L]+=0.12*nz*np.sin(np.linspace(0,np.pi,L))
S={s["id"]:s for s in tl}
for s in tl: whoosh(s["t0"])
g=lambda sid,k,o=0: S[sid]["t0"]+S[sid]["seg"][k]+o
ding(g("hook",3,.2),880)
# 節拍器：rhythm 段配音後 110 bpm、約 12 拍（與 render.py sc_rhythm 同步）
rs=S["rhythm"]; b0=rs["t0"]+rs["len"]-7.3
for k in range(12): tick(b0+k*60/110)
ding(g("summary",0),1320)
mixd=voice*1.0+music+sfx
mixd=mixd[:int((total+0.2)*SR)]
mixd/=max(1,np.abs(mixd).max()/0.95)
with wave.open("mix.wav","wb") as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((mixd*32767).astype(np.int16).tobytes())
# srt
def ts(x): h=int(x//3600);m=int(x%3600//60);s=x%60; return f"{h:02}:{m:02}:{int(s):02},{int((s%1)*1000):03}"
out=[];n=1
for s in tl:
    for k,sub in enumerate(s["subs"]):
        a=s["t0"]+s["seg"][k]; b=s["t0"]+(s["segend"][k] if k<len(s["subs"])-1 else s["len"]-0.3)
        out.append(f"{n}\n{ts(a)} --> {ts(b)}\n{sub}\n");n+=1
open("subs.srt","w").write("\n".join(out))
print("ok",total)
