# 生日問題（餘事件）影片原始檔

- 字型：Noto Sans CJK TC（Regular/Bold/Black）放在 src/ 同層
- `script.py`：台詞（配音文字, 字幕文字）
- `tts2.py plain <段落...>`：只送台詞配音，並逐字聽寫比對
- 待辦：answer、end 兩段尚未用新版稿配音（Gemini 免費額度用完）
- 配音後流程：atempo 1.08 → `render.py preview` → `render.py full` → `mix.py` → ffmpeg 合成
