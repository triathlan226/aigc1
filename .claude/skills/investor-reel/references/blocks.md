# content 檔格式

```python
META = {
    "series": "黃仁勳 BG2 訪談精華",          # 左上角欄目名
    "disclaimer": "數字為訪談口述・非投資建議",  # 頁尾左側
    "brand_left": "科技", "brand_right": "人文", "tagline": "事實 ｜ 推論 ｜ 觀點",
    # "fonts": {...}  # 本機沒有 Noto CJK TC 時覆寫，見 render.py 開頭
}
SCENES = [ {...}, ... ]   # 依序播放；每個場景都要有 "type" 和 "beats"（1 拍 = 0.6 秒）
```
每個場景可加 `"color"`：green / cyan / amber / red（影響光暈、進度條、章節標籤）。

## 場景（type）

| type | 欄位 | 說明 |
|---|---|---|
| `hook` | `label`, `from`, `to`, `dec`, `pre`, `big`, `badge`, `note` | 數字由 from 滾到 to（2 秒），然後換成 `big` 大字重擊 |
| `title` | `kicker`, `lines`(2 行), `sub`, `sub2`, `legend`[(字, 色)] | 片名頁 |
| `chapter` | `badge`, `title`(字串或 2 行 list), `blocks`, `gap`(選填) | 主要內容頁；區塊由上往下自動排、依序出現 |
| `kinetic` | `label`, `items`[{`word`, `sub`[主句, 註解], `color`, `sz`}] | 快閃，每則平均分配時間 |
| `outro` | `kicker`, `lines`(2), `points`(4), `foot1..3` | 總結＋來源＋免責 |
| `brand` | `tagline`(選填) | 科技｜人文 Logo，6 拍，放最後 |

## chapter 區塊（blocks）
內容區高度約 1080px（y 560–1640）。`check` 會顯示每章總高 h，超過即「❌超出」。可加 `"at": 秒數` 指定出現時間。

| type | 高度 | 欄位 | 用途 |
|---|---|---|---|
| `text` | XL120/L96/M80/S64 | `t`, `size`, `color` | 一行字。L/XL 用 Black 字重 |
| `pill` | 110 | `t`, `color`, `outline`, `sz` | 結論標籤；風險用 red + outline |
| `quote` | 126+76×行數 | `lines`, `who`, `color` | 引言框（中文意譯，不要長段引用） |
| `cards` | h+20（預設 250） | `items`[{head, body, sub, color, bsz}], `h` | 2–3 張並列卡片 |
| `chain` | 130 | `items`(2–4), `last` | 因果／流程鏈，箭頭動畫 |
| `bignum` | 300 | `v` 或 `from`/`to`/`dec`/`pre`/`suf`, `cap`, `color`, `sz` | 大數字（可滾動） |
| `bars` | `h`（預設 470） | `items`[(標籤, 數值, 顯示字, 色)], `vsz` | 長條圖，逐根長出 |
| `donut` | 440 | `items`[(名稱, 比重, 說明, 色)], `center`, `center2` | 環圈圖＋圖例 |
| `compare` | 300 | `left`[小標, 值], `right`[小標, 值], `cap`, `sz`, `color` | 前後對比（舊 → 新） |
| `list` | 列數×`row` | `items`[(主句, 註解)], `row`, `color` | 編號清單（風險頁） |
| `tags` | 110 | `items`, `color` | 一排外框標籤 |
| `gap` | `h` | — | 空白 |
