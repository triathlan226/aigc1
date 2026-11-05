import os,sys,base64,requests,wave,io
from concurrent.futures import ThreadPoolExecutor
from script import SCENES, STYLE
os.makedirs("aud",exist_ok=True)
def tts(text,out,voice="Puck",model="gemini-3.8-flash-tts"):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.environ['GEMINI_API_KEY']}"
    body={"contents":[{"parts":[{"text":STYLE+text}]}],"generationConfig":{"responseModalities":["AUDIO"],
      "speechConfig":{"voiceConfig":{"prebuiltVoiceConfig":{"voiceName":voice}}}}}
    import time
    for i in range(8):
        if i: time.sleep(20*i)
        try:
            r=requests.post(url,json=body,timeout=300)
            if r.ok:
                d=base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                open(out,"wb").write(d); return out
            print(r.status_code,r.text[:200],file=sys.stderr)
        except Exception as e: print(e,file=sys.stderr)
    raise SystemExit("fail "+out)
only=sys.argv[1:]
jobs=[(sid,"".join(s for s,_ in segs)) for sid,segs,_ in SCENES if not only or sid in only]
with ThreadPoolExecutor(1) as ex:
    for sid,f in zip([j[0] for j in jobs], ex.map(lambda j: tts(j[1],f"aud/{j[0]}.wav"), jobs)):
        w=wave.open(f); print(sid, round(w.getnframes()/w.getframerate(),2), w.getframerate())
