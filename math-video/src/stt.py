import os,sys,base64,requests
def stt(f,model="gemini-3.5-flash"):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={os.environ['GEMINI_API_KEY']}"
    b=base64.b64encode(open(f,"rb").read()).decode()
    body={"contents":[{"parts":[{"inlineData":{"mimeType":"audio/wav","data":b}},{"text":"逐字轉寫這段音訊（繁體中文），若有重複、多餘或唸錯的字句請特別指出，並說明哪裡有長時間停頓或拖長音。另外用一行評估口音：是台灣腔還是中國大陸腔？"}]}]}
    import time
    for i in range(6):
        r=requests.post(url,json=body,timeout=300)
        if r.ok: break
        time.sleep(10)
    if not r.ok: return r.text[:300]
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
for f in sys.argv[1:]: print("==",f); print(stt(f))
