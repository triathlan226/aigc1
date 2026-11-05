# 生日問題（餘事件）影片原始檔

- 字型：Noto Sans CJK TC（Regular/Bold/Black）放在 src/ 同層
- `script.py`：台詞（配音文字, 字幕文字）
- `tts2.py plain <段落...>`：只送台詞配音，並逐字聽寫比對
- 現行配音：Edge 雲哲男聲（zh-TW-YunJheNeural），`bash run_all.sh` 一鍵重配並輸出成片；有 GEMINI_API_KEY 時逐段聽寫比對
- 配音後流程：atempo 1.08 → `render.py preview` → `render.py full` → `mix.py` → ffmpeg 合成
