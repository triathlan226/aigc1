# 內容：黃仁勳 BG2 Pod 訪談（逐字稿由使用者提供）。所有數字皆為訪談中受訪者／主持人口述。
META = {
    "series": "黃仁勳 BG2 訪談精華",
    "disclaimer": "數字為訪談口述・非投資建議",
    "brand_left": "科技", "brand_right": "人文", "tagline": "事實 ｜ 推論 ｜ 觀點",
}

SCENES = [
    {"type": "hook", "beats": 9, "color": "green",
     "label": "黃仁勳：AI 需要的算力將是過去的", "from": 1, "to": 10, "big": "10 億倍",
     "badge": "AI 從「背答案」走向「會思考」", "note": "推理、規劃、反覆試錯，都在燒算力"},

    {"type": "title", "beats": 10, "color": "green",
     "kicker": "Bg2 Pod × NVIDIA 執行長", "lines": ["黃仁勳", "8 個投資重點"],
     "sub": "AI 營收撐得起資本支出嗎？", "sub2": "主持：Brad Gerstner、Clark Tang（Altimeter）",
     "legend": [("數據", "cyan"), ("觀點", "amber"), ("風險", "red")]},

    {"type": "chapter", "beats": 26, "color": "green", "badge": "重點 01｜需求從哪來",
     "title": ["AI 從聊天", "走向「做事」"],
     "blocks": [
         {"type": "chain", "items": ["規劃", "試錯", "篩選", "反思"]},
         {"type": "text", "t": "會思考的 AI，每題都要更多算力", "size": "M"},
         {"type": "cards", "items": [
             {"head": "去年突破 ①", "body": "記憶管理", "color": "cyan"},
             {"head": "去年突破 ②", "body": "會用工具", "color": "cyan"}]},
         {"type": "compare", "left": ["GPT-1 訓練成本", "千萬美元"], "right": ["10 年後", "約 100 美元"],
          "cap": "成本越低 → 用量越大，需求越滾越多"},
     ]},

    {"type": "chapter", "beats": 26, "color": "cyan", "badge": "重點 02｜第二成長曲線",
     "title": "實體 AI 開始放量",
     "blocks": [
         {"type": "bars", "h": 460, "items": [
             ("前年", 5, "$50 億", "faint"), ("去年", 10, "$100 億", "cyan"), ("今年上半年", 10, "$100 億", "green")]},
         {"type": "tags", "items": ["自駕車", "機器人", "醫療影像", "電信", "工廠"]},
         {"type": "quote", "lines": ["說它是 1,000 億美元市場，", "其實是說少了"]},
     ]},

    {"type": "chapter", "beats": 26, "color": "amber", "badge": "重點 03｜真正的瓶頸",
     "title": ["缺的不是需求，", "是地、電、廠房"],
     "blocks": [
         {"type": "bignum", "v": "43 GW", "color": "amber", "sz": 170,
          "cap": "明年新增 AI 算力 > 全球現有總和（SemiAnalysis）"},
         {"type": "cards", "h": 210, "items": [
             {"head": "土地", "body": "許可", "color": "amber"},
             {"head": "電力", "body": "發電", "color": "amber"},
             {"head": "廠房", "body": "工人", "color": "amber"}]},
         {"type": "text", "t": "上游也缺：大尺寸基板、矽光子", "size": "S", "color": "dim"},
         {"type": "pill", "t": "黃仁勳：供需缺口幾年內難補上", "color": "amber"},
     ]},

    {"type": "chapter", "beats": 26, "color": "green", "badge": "重點 04｜份額還在變大",
     "title": ["每 1 GW 資料中心", "輝達拿走更多"],
     "blocks": [
         {"type": "bars", "h": 430, "vsz": 50, "items": [
             ("過去", 18, "~$180 億", "faint"), ("之後", 22, "$200 億+", "cyan"), ("現在", 40, "$400 億+", "green")]},
         {"type": "cards", "h": 220, "items": [
             {"head": "雲端大廠資本支出", "body": "約 40%", "sub": "6 年前僅個位數", "color": "cyan"},
             {"head": "新雲端、自建機房", "body": "約 80%", "sub": "成長更快的那一半", "color": "green"}]},
         {"type": "pill", "t": "電不夠 → 只能選每瓦產出最高的", "color": "green"},
     ]},

    {"type": "chapter", "beats": 26, "color": "cyan", "badge": "重點 05｜客戶結構",
     "title": ["不是只靠", "OpenAI、Anthropic"],
     "blocks": [
         {"type": "donut", "center": "營收", "center2": "約略三分", "items": [
             ("一般運算", 1, "資料處理、模擬・年增 30–40%", "cyan"),
             ("前沿 AI 實驗室", 1, "至少 5–6 家，約 1/4–1/3", "green"),
             ("新創、新雲端", 1, "上千家公司租用算力", "amber")]},
         {"type": "text", "t": "80% 新創用開源模型做垂直應用", "size": "M"},
         {"type": "pill", "t": "不必把實驗室營收外推到數兆美元", "color": "cyan"},
     ]},

    {"type": "chapter", "beats": 26, "color": "green", "badge": "重點 06｜長線市場規模",
     "title": ["2030 年 AI 基建", "每年 3–4 兆美元"],
     "blocks": [
         {"type": "bignum", "from": 0.5, "to": 1.5, "dec": 1, "pre": "$", "suf": " 兆", "sz": 170,
          "cap": "其中「算力」一年約 1.5 兆美元（AI 前約 0.5 兆）"},
         {"type": "compare", "left": ["傳統運算 / GW", "$50 億"], "right": ["Vera Rubin / GW", "$500 億"], "sz": 80},
         {"type": "text", "t": "摩爾定律已結束：算力要 2 倍，錢也要 2 倍", "size": "S", "color": "amber"},
         {"type": "text", "t": "長期每年 10 兆美元？「一點也不意外」", "size": "S", "color": "dim"},
     ]},

    {"type": "chapter", "beats": 27, "color": "amber", "badge": "重點 07｜市場低估了嗎",
     "title": ["華爾街預估", "一年內翻倍上修"],
     "blocks": [
         {"type": "compare", "left": ["一年前共識：2027 年", "持平或衰退"], "right": ["現在共識：2027 年", "成長 74%"],
          "sz": 72, "color": "green"},
         {"type": "cards", "h": 210, "items": [
             {"head": "營收預估上修", "body": "100–200%", "color": "green"},
             {"head": "同期股價只漲", "body": "約 20%", "color": "amber"}]},
         {"type": "text", "t": "以上為主持人 Brad Gerstner 說法", "size": "S", "color": "dim"},
         {"type": "quote", "lines": ["500 億美元的訂單、看不到實機，", "全世界只敢下給輝達"]},
     ]},

    {"type": "chapter", "beats": 26, "color": "green", "badge": "重點 08｜硬體以外的新引擎",
     "title": ["軟體授權＋營收分成", "股東回饋加碼"],
     "blocks": [
         {"type": "cards", "h": 240, "items": [
             {"head": "企業軟體授權", "body": "每顆 GPU", "sub": "每年收數千美元", "color": "cyan", "bsz": 56},
             {"head": "新雲端營收分成", "body": "投資＋分潤", "sub": "合作期 4–10 年", "color": "green", "bsz": 56}]},
         {"type": "text", "t": "年出貨約 2,000 萬顆 GPU，約一半進企業", "size": "S", "color": "dim"},
         {"type": "bignum", "from": 0, "to": 60, "suf": "%+", "sz": 180, "color": "green",
          "cap": "上季自由現金流用於買回庫藏股（原目標 50%）"},
     ]},

    {"type": "kinetic", "beats": 18, "color": "green", "label": "還有這些",
     "items": [
         {"word": "2 GW", "sub": ["澳洲新案", "黃仁勳：約等於 800 億美元商機"], "color": "green"},
         {"word": "太空", "sub": ["與 SpaceX 合作", "開發可上太空的資料中心伺服器"], "color": "cyan"},
         {"word": "零信任", "sub": ["AI 安全這樣做", "最小權限＋獨立監控，可隨時關機"], "color": "amber"},
         {"word": "99.99%", "sub": ["黃仁勳對 AI 前景的信心", "「我們會負責任地走到那裡」"], "color": "green", "sz": 180},
     ]},

    {"type": "chapter", "beats": 28, "color": "red", "badge": "投資人要留意",
     "title": "風險與反證條件",
     "blocks": [
         {"type": "list", "row": 140, "items": [
             ("地、電、廠房卡關", "資料中心延後完工 → 出貨遞延"),
             ("AI 實驗室營收要年年翻倍", "今年約 2,000 億 → 需 4,000 億美元"),
             ("基板、矽光子供應吃緊", "產能跟不上，營收認列受限"),
             ("多為業者自述", "請以財報、法說會數字為準")]},
         {"type": "pill", "t": "反證訊號：雲端大廠下修資本支出、輝達份額下滑", "color": "red", "outline": True, "sz": 36},
     ]},

    {"type": "outro", "beats": 14, "color": "green",
     "kicker": "一句話總結", "lines": ["需求不是問題", "供給才是"],
     "points": ["推理型 AI 讓算力需求持續放大", "瓶頸在地、電、廠房與關鍵材料",
                "輝達份額與每 GW 價值仍在提高", "留意：實驗室營收能否跟上資本支出"],
     "foot1": "資料：Bg2 Pod 黃仁勳訪談逐字稿",
     "foot2": "數字皆為受訪者／主持人口述，未經公司財報驗證",
     "foot3": "本影片僅供資訊分享，非投資建議"},

    {"type": "brand", "beats": 6, "color": "cyan",
     "tagline": "事實 ｜ 推論 ｜ 觀點", "sub": ""},
]
