#!/bin/bash
# 地理〈地圖投影〉一鍵出片：pip install edge-tts numpy pillow requests；需要 ffmpeg
# 國界資料：Natural Earth 1:110m（公有領域），countries.geojson
set -e; cd "$(dirname "$0")"
B=https://raw.githubusercontent.com/notofonts/noto-cjk/main
for w in Regular Bold Black; do [ -f NotoSansCJKtc-$w.otf ] || curl -sSL -o NotoSansCJKtc-$w.otf "$B/Sans/OTF/TraditionalChinese/NotoSansCJKtc-$w.otf"; done
python3 tts_edge.py
mkdir -p aud2
for f in aud/*.wav; do ffmpeg -loglevel error -y -i $f -af "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse" -ar 24000 -ac 1 aud2/$(basename $f); done
python3 render.py preview
rm -f part*.mp4; python3 render.py full
python3 mix.py
ffmpeg -loglevel error -y -i video.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -af "loudnorm=I=-16:TP=-1.5" -ar 48000 -c:a aac -b:a 192k -shortest final.mp4
cp final.mp4 "../地圖投影_格陵蘭真的那麼大.mp4"; cp subs.srt "../地圖投影_格陵蘭真的那麼大.srt"
echo ALLDONE
