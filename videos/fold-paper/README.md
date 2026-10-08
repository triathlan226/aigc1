# A4 紙對折 100 次｜動畫影片

直式 1080×1920、30 fps、97 秒，含程式合成的原創配樂（無版權素材）。

- 成品：`A4對折100次.mp4`
- 核心數字：0.1 mm × 2¹⁰⁰ ≈ 1.27 × 10²⁶ 公尺 ≈ 134 億光年

## 檔案

| 檔案 | 用途 |
|---|---|
| `timeline.py` | 共用時間軸：里程碑（折數、文字）、折紙與音效時間點 |
| `render.py` | 用 Pillow 逐格繪製畫面，交給 ffmpeg 編碼 |
| `music.py` | 用 numpy 合成配樂與音效，輸出 `music.wav` |

## 重新產生影片

需求：Python 3、`numpy`、`Pillow`、`ffmpeg`（含 libx264），以及中文字型
（`render.py` 的 `FONT` 預設為文泉驛正黑 `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`，可改成其他 CJK 字型路徑）。

```bash
cd videos/fold-paper
python3 music.py                                   # 產生 music.wav
for i in 0 1 2 3; do python3 render.py $i 4 & done; wait   # 分 4 段平行算圖
printf "file 'seg_0.mp4'\nfile 'seg_1.mp4'\nfile 'seg_2.mp4'\nfile 'seg_3.mp4'\n" > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -i music.wav -c:v copy -c:a aac -b:a 192k \
  -shortest -movflags +faststart A4對折100次.mp4
```

預覽單格：`python3 render.py still 21.5 68.5` → 輸出 `still_21.5.png` 等。

## 數字來源

- 紙厚 0.1 mm：一般 80 g/m² 影印紙的常見近似值
- 可觀測宇宙直徑約 930 億光年：[Wikipedia – Observable universe](https://en.wikipedia.org/wiki/Observable_universe)
- 對折世界紀錄 12 次（Britney Gallivan，2002）：[Guinness World Records](https://guinnessworldrecords.com/world-records/494571-most-times-to-fold-a-piece-of-paper)
- 宇宙年齡約 138 億年、仙女座星系約 250 萬光年、銀河系直徑約 10 萬光年、宇宙恆星數約 10²²～10²⁴：常見天文估計值
