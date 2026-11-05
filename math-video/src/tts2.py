import os,sys,base64,requests,time,wave,difflib,re
from script import SCENES
KEY=os.environ['GEMINI_API_KEY']
def tts(text,out,mode):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-lite-tts:generateContent?key={KEY}"
    body={"contents":[{"parts":[{"text":text}]}],"generationConfig":{"responseModalities":["AUDIO"],
      "speechConfig":{"voiceConfig":{"prebuiltVoiceConfig":{"voiceName":"Puck"}}}}}
    if mode=="sys":
        body["systemInstruction"]={"parts":[{"text":"你是台灣高中數學老師，用輕鬆有活力的語氣朗讀使用者給的台詞。只朗讀台詞本身。"}]}
    for i in range(10):
        r=requests.post(url,json=body,timeout=300)
        if r.ok:
            open(out,"wb").write(base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])); return True
        print(" tts",r.status_code,r.text[:120].replace("\n"," "),file=sys.stderr)
        if r.status_code==400: return False
        time.sleep(15+15*i)
    return False
def stt(f):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={KEY}"
    b=base64.b64encode(open(f,"rb").read()).decode()
    body={"contents":[{"parts":[{"inlineData":{"mimeType":"audio/wav","data":b}},{"text":"請逐字聽寫這段音訊，用繁體中文、數字用中文字寫出。只輸出聽到的文字，不要任何說明。"}]}]}
    for i in range(10):
        r=requests.post(url,json=body,timeout=300)
        if r.ok: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        time.sleep(10+10*i)
    return ""
norm=lambda s: re.sub(r"[^\w]","",s)
mode=sys.argv[1]; ids=sys.argv[2:]
for sid,segs,_ in SCENES:
    if ids and sid not in ids: continue
    text="".join(s for s,_ in segs)
    for attempt in range(3):
        out=f"aud/{sid}.wav"
        if not tts(text,out,mode): print(sid,"TTS 失敗"); break
        w=wave.open(out); d=w.getnframes()/24000; rate=len(norm(text))/d
        heard=stt(out); sim=difflib.SequenceMatcher(None,norm(text),norm(heard)).ratio()
        extra=len(norm(heard))-len(norm(text))
        ok= rate>3.3 and sim>0.8 and extra<8
        print(f"{sid:7} 第{attempt+1}次 {d:5.1f}s 每秒{rate:.1f}字 相似度{sim:.2f} 多出{extra}字 {'OK' if ok else 'NG'}")
        open(f"aud/{sid}.stt.txt","w").write(heard)
        if ok: break
        if not ok and attempt==2: print("   聽寫:",heard[:200])
