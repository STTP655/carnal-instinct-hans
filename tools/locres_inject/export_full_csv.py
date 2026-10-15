# -*- coding: utf-8 -*-
"""步骤 4：生成全量翻译对照表 out/全量翻译对照表.csv（UTF-8 BOM）。

列：key | src英文 | 中文译文 | 来源(词表/新翻) | 所在资产数 | 所在资产 | 注入动作 | 备注
每个 baseline 家族 A key 一行（含 SKIP 行），供人工审校。
"""
import csv
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXP = r"D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"
OUT = EXP + r"\out\全量翻译对照表.csv"

fs = json.load(open(EXP + r"\out\full_srcs.json", encoding="utf-8"))
rep = json.load(open(EXP + r"\out\inject_report_full.json", encoding="utf-8"))
act = {a["key"]: a for a in rep["actions"]}
resolved = {r["src"]: r for r in fs["rows"]}

KIND_ZH = {
    "vocab_exact": "词表(精确)",
    "vocab_strip": "词表(去首尾空格)",
    "vocab_norm": "词表(归一化匹配)",
    "vocab_norm_override": "词表(归一化+保留原文换行)",
    "new": "新翻",
}
ACT_ZH = {"add": "新增", "update": "更新", "kept": "保留已有中文"}

rows_out = []
for e in fs["baseline_entries"]:
    key, src = e["key"], e["src"]
    r = resolved[src]
    a = act.get(key)
    if a is None:
        kind, zh, actz = r["vocab_hit"] or "none", "", "未注入"
        note = "SKIP：纯数字/符号/品牌缩写/占位乱码，保留内联原文"
        if kind == "none":
            note = "SKIP：" + note.split("：", 1)[1]
        kind_zh = "SKIP"
    else:
        kind_zh = KIND_ZH[a["src_kind"]]
        actz = ACT_ZH[a["action"]]
        if a["action"] == "kept":
            zh = a["old_value"]
            note = f"原值已是中文，保留；本次备选译文={a['zh']}"
        elif a["action"] == "update":
            zh = a["zh"]
            note = f"覆盖原值 {a['old_value']!r}"
        else:
            zh = a["zh"]
            note = ""
    rows_out.append([key, src, zh, kind_zh, len(e["files"]), "; ".join(e["files"]), actz, note])

order = {"SKIP": 0, "新翻": 1, "词表(归一化+保留原文换行)": 2, "词表(归一化匹配)": 3,
         "词表(去首尾空格)": 4, "词表(精确)": 5}
rows_out.sort(key=lambda x: (order.get(x[3], 9), x[6], x[1]))

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["key", "src英文", "中文译文", "来源(词表/新翻)", "所在资产数",
                "所在资产", "注入动作", "备注"])
    w.writerows(rows_out)

c1 = Counter(r[3] for r in rows_out)
c2 = Counter(r[6] for r in rows_out)
print(f"对照表 {len(rows_out)} 行 → {OUT}")
print("来源分布:", dict(c1))
print("动作分布:", dict(c2))
