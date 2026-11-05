"""用 Edge 台灣男聲（雲哲）重配全部段落：python3 tts_edge.py [段落...]
只送台詞，不帶任何指示；配完逐字聽寫比對（stt 用 Gemini，可省略）。"""
import asyncio, sys, os, subprocess, re, difflib, wave
import edge_tts
from script import SCENES
VOICE = "zh-TW-YunJheNeural"
# edge-tts 固定用 certifi 憑證；在有 TLS 代理的環境（SSL_CERT_FILE）補上該 CA
if os.environ.get("SSL_CERT_FILE"):
    import edge_tts.communicate as _c
    _c._SSL_CTX.load_verify_locations(os.environ["SSL_CERT_FILE"])
norm = lambda s: re.sub(r"[^\w]", "", s)
async def one(sid, text):
    mp3 = f"aud/{sid}.mp3"
    await edge_tts.Communicate(text, VOICE, rate="+5%").save(mp3)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, "-ar", "24000", "-ac", "1", f"aud/{sid}.wav"], check=True)
async def main(ids):
    os.makedirs("aud", exist_ok=True)
    for sid, segs, _ in SCENES:
        if ids and sid not in ids: continue
        text = "".join(s for s, _ in segs)
        await one(sid, text)
        d = wave.open(f"aud/{sid}.wav").getnframes() / 24000
        msg = f"{sid:7} {d:5.1f}s 每秒{len(norm(text))/d:.1f}字"
        if os.environ.get("GEMINI_API_KEY"):
            from tts2 import stt
            h = stt(f"aud/{sid}.wav"); open(f"aud/{sid}.stt.txt", "w").write(h)
            msg += f" 相似度{difflib.SequenceMatcher(None, norm(text), norm(h)).ratio():.2f}"
        print(msg, flush=True)
asyncio.run(main(sys.argv[1:]))
