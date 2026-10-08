"""共用時間軸：畫面與音樂都從這裡取時間點。"""
DUR = 97.0
FPS = 30

# S3 爬升：(折數, 標題, 說明)
MILESTONES = [
    (7,   "約一個指甲寬", "還很普通……繼續折！"),
    (10,  "差不多一個手掌寬", "才 10 公分而已"),
    (14,  "跟一個大人一樣高！", "只折了 14 次"),
    (23,  "超過台北101，也比杜拜塔高", "第 22 次 419 m，再折一次就翻倍"),
    (27,  "超過聖母峰！", "比民航機巡航高度（約 10 公里）還高"),
    (42,  "抵達月球！", "地球到月球約 38.4 萬公里"),
    (51,  "飛到太陽了！", "地球到太陽約 1.5 億公里"),
    (83,  "橫跨整個銀河系！", "銀河系直徑約 10 萬光年"),
    (88,  "抵達仙女座星系！", "銀河系的鄰居，距離約 250 萬光年"),
]
TRAVEL = [1.5, 1.0, 1.0, 1.5, 1.0, 1.5, 1.2, 1.8, 1.5]
HOLD = 3.2
S3_START = 18.0
S3_INTRO = 1.2

# 建立 (t, n) 關鍵影格
KEYS = [(S3_START, 0.0), (S3_START + S3_INTRO, 0.0)]
MILESTONE_TIMES = []
_t, _n = S3_START + S3_INTRO, 0.0
for (n, *_), d in zip(MILESTONES, TRAVEL):
    _t += d
    KEYS.append((_t, float(n)))
    MILESTONE_TIMES.append(_t)
    _t += HOLD
    KEYS.append((_t, float(n)))
S3_END = _t  # 約 60 秒

S2_FOLDS = [8.0 + 1.6 * k for k in range(5)]
S5_FOLDS = [77.0 + 0.5 * k for k in range(7)]
FOLD_TIMES = S2_FOLDS + S5_FOLDS
RISER_START = 62.2
HIT_TIME = 66.0
