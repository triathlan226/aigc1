---
name: investor-reel
description: 把使用者貼上的文章、訪談逐字稿、財報摘要、研究報告，做成給投資人看、可傳 LINE 的 9:16 直式短影音 MP4（3 分鐘內、高清晰、只有配樂沒有人聲、片中與片尾有「科技｜人文」品牌）。只要使用者貼內容並說「做成影片」「做 MP4」「做短影音」「做成動畫」「給投資人看的影片」，就使用這個 skill，即使沒有明說 skill 名稱。
---

# 投資人短影音：內容 → 重點 → 逐格繪製 MP4

畫面由 `scripts/render.py` 以 pycairo 向量逐格繪製，配樂由 `scripts/music.py` 用 numpy 合成（無外部素材、無版權問題、無人聲）。
**你的工作是內容**：讀懂資料、挑重點、查證、寫一個 content 檔（Python）。版面、動畫、配樂、編碼都由腳本處理。
完整範例：`examples/jensen_bg2.py`（黃仁勳 BG2 訪談，176 秒）。區塊格式：`references/blocks.md`。

## 固定規格（使用者已定案，不要自行更動）
- 1080×1920、30fps、H.264 High、CRF 14、yuv420p、BT.709；總長 **3 分鐘內**（建議 150–178 秒）。
- 只有合成配樂與轉場音效，**不要人聲**。
- 品牌「科技｜人文」放兩處：每頁右下角小字（左下是免責聲明）＋片尾 3.6 秒 Logo 頁（`brand` 場景，標語「事實 ｜ 推論 ｜ 觀點」）。不要自創其他標語。
- 頁尾固定顯示 `META["disclaimer"]`（例如「數字為訪談口述・非投資建議」）。
- 顏色語意：green＝主結論／正向數據，cyan＝事實與數據，amber＝推論、觀點、引言，red＝只用在風險。
- 全部繁體中文、台灣用語；易混淆名詞首次出現可附英文。

## 清晰度規則（使用者曾抱怨「模糊、毛邊」，務必遵守）
- 字要大：內文 ≥ 40px、註解 ≥ 30px、標題 76px 以上、主數字 170–300px。LINE 會再壓縮一次，小字一定糊。
- 不要細線、細網格、噪點、密集紋理（壓縮後會糊成一片）；背景只用大面積柔和漸層。
- 不要畫面晃動（camera shake）——會讓字在壓縮後糊掉。
- 字型 hinting 關閉、灰階反鋸齒（腳本已設定）。不要改成先畫小圖再放大。
- 交付前一定要從**成品 MP4 解出畫面**檢查（見步驟 6），不是只看 PNG。

## 流程

### 0. 環境（第一次使用時）
需要 Python 3、`pycairo`、`numpy`、`scipy`、`Pillow`、`ffmpeg`、繁中字型。
- macOS：`brew install cairo pkg-config ffmpeg`，`pip3 install pycairo numpy scipy pillow`，字型 `brew install --cask font-noto-sans-cjk-tc font-noto-serif-cjk-tc`（裝不到就用 PingFang TC，見下）。
- Windows：建議在 WSL（Ubuntu）執行：`sudo apt install ffmpeg fonts-noto-cjk fonts-noto-cjk-extra python3-pip`，`pip install pycairo numpy scipy pillow`；或用 conda：`conda install -c conda-forge pycairo ffmpeg numpy scipy pillow`。
- 跑 `python3 scripts/render.py CONTENT.py fonttest font.png`，**打開圖片確認**：五行字都是中文、沒有方框、black 那行明顯比 med 粗。若字型不對，在 content 的 `META["fonts"]` 覆寫（macOS 用 PingFang TC / Songti TC，Windows 用 Microsoft JhengHei / MingLiU，見 render.py 開頭註解），再測一次。字型不對就不要渲染。

### 1. 讀內容、列候選重點
讀完整份資料（長逐字稿要分段讀完，不可只讀開頭）。列出所有對投資人有意義的重點：關鍵數字、誰說的、對營收／估值／供應鏈的意義。

### 2. 查證與標示
- 時事、財報、股價、規格先用網路查證；查到一手來源（公司公告、SEC、法說會、公開資訊觀測站）就以查證結果為準。
- 查不到的數字：仍可上片，但必須標明是誰說的（「黃仁勳表示」「主持人說法」「訪談口述」），並在 disclaimer 與片尾註明「未經財報驗證」。
- 主持人／分析師的說法不可包裝成公司數字；預估不可寫成實際。
- 逐字稿疑似語音辨識錯字（怪名詞）不要上片。
- 不給個股買賣建議、目標價、「買進／加碼」字眼。

### 3. 規劃結構（典型 170 秒）
| 場景 | 拍數 | 內容 |
|---|---|---|
| `hook` | 9 | 最震撼的一個數字，滾動後重擊 |
| `title` | 10 | 主題、來源、「數據／觀點／風險」圖例 |
| `chapter` × 6–8 | 各 26–28 | 重點 01…08，每章 3–4 個區塊 |
| `kinetic` | 18 | 4 則快閃補充 |
| `chapter`（紅色） | 28 | 風險與反證條件（必備） |
| `outro` | 14 | 一句話總結＋4 點摘要＋來源與免責 |
| `brand` | 6 | 科技｜人文 Logo（必備，放最後） |
1 拍 = 0.6 秒（100 BPM）。總拍數 ≤ 296（≈177.6 秒）。

### 4. 寫 content 檔
複製 `examples/jensen_bg2.py` 到工作資料夾（例如 `~/reels/YYYYMMDD_主題.py`），改 `META` 與 `SCENES`。
- 章節 `badge` 以「重點 0N｜」開頭才會計入右上角頁碼；風險頁 badge 用「投資人要留意」。
- 每章 3–4 個區塊，一個區塊只講一件事；大數字放 `bignum`/`bars`/`compare`，白話放 `text`，結論放 `pill`，名言放 `quote`。
- 字數上限：text L ≈ 12 字、M ≈ 18 字、S ≈ 24 字；卡片 body ≈ 6 字；kinetic word ≈ 4 字。超過就刪字，不要硬塞。

### 5. 檢查
```bash
python3 scripts/render.py CONTENT.py check            # 不可有「❌超出」，[過長] 要刪字
python3 scripts/render.py CONTENT.py stills sheet.png # 打開看：無重疊、無出界、無方框字
```
抽幾張全尺寸 `frame` 細看（特別是卡片與長句）。

### 6. 渲染與品管
```bash
python3 scripts/render.py CONTENT.py video OUT.mp4    # 4 核心約 3–5 分鐘；可放背景執行
ffmpeg -ss 90 -i OUT.mp4 -frames:v 1 check.png        # 從成品解一格，確認字邊銳利、無色邊
ffmpeg -i OUT.mp4 -af volumedetect -vn -f null -      # max_volume 約 -1 dB、mean 約 -20 dB
```
檔名：`主題_投資人精華.mp4`。

### 7. 交付
回報：影片長度、結構表、哪些數字查證過／哪些只是受訪者口述、刪掉了什麼。提醒時效性數字（股價、指引）發布前可能已變動。
