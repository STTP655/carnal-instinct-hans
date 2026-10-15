# -*- coding: utf-8 -*-
"""只读分析：对"现值已是中文、本次默认保留"的 247 条，逐条给出择优选用的建议。

判定口径：
  覆盖 = 现值是明显错译/漏译/串位，或与同类条目不一致 → 建议采用本次译文
  保留 = 现值更贴合游戏语境、更完整，或只是措辞差异（不值得改动已有汉化）
输出：
  out/overwrite_plan.csv   （UTF-8 BOM，供人工审校）
  out/overwrite_plan.json  （建议覆盖的 key 列表，供后续注入脚本消费）
"""
import csv
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXP = r"D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"

# src -> (建议, 理由)  只列与本次译文不同的 34 条
PLAN = {
    "WEIGHT": ("覆盖", "排序窗口里 WEIGHT 是“重量”，现值“体重”是错译"),
    "Poison Damage": ("覆盖", "属性列表里与“流血伤害”等并列，应为“中毒伤害”"),
    "Bleed Damage": ("覆盖", "同上，属性列表统一“XX伤害”"),
    "Critical Damage Multiplier": ("覆盖", "词条名不完整，现值只写“暴击”"),
    "Critical Damage Chance": ("保留", "现值“暴击率 %”含百分号提示，实用"),
    "Added": ("覆盖", "现值“已立即添加”语义奇怪，应为“已添加”"),
    "Date": ("覆盖", "章节文本里 Date 是“日期”，现值“描述”是错译"),
    "Clothing": ("覆盖", "作弊菜单分类是“服装”，现值“形态”与 Form 混淆；覆盖后与 DSS2 的 2 条新增一致"),
    "GENERAL": ("覆盖", "背包分类是“通用”，现值“将军”是机器错译"),
    "MERCHANT": ("覆盖", "窗口切换是“商人”，现值“购买”是 Buy 的译文"),
    "FAST TRAVEL": ("覆盖", "现值“旅行”不完整，应为“快速旅行”"),
    "REST - NIGHT": ("覆盖", "营火休息选项，现值“进度时间”明显错译"),
    "Weight": ("覆盖", "拆分堆叠界面是“重量”，现值“体重”是错译"),
    "Total Value": ("覆盖", "现值“价值”不完整，应为“总价值”"),
    "Start your journey.": ("覆盖", "现值“我相信你”与原文无关，明显错译"),
    "Tome of the Ancients": ("覆盖", "现值“埃科斯：《沙漠王国指南》”疑似与别条串位"),
    "LOADING WORLD": ("覆盖", "覆盖后与其余 3 条新增（正在载入世界）统一，消除不一致"),
    "Are you sure to quit the game? Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?Are you sure to quit the game?":
        ("保留", "现值只显示一句，比原文重复 8 次更合理（原文是开发者占位）"),
    "YOU DIED": ("保留", "现值“你的旅程已结束”更贴合游戏气质"),
    "Gold Nubs": ("保留", "现值“你的金币”比“金币”更自然"),
    "These Cat Like People were the most": ("保留", "原文被截断，现值补出了人名“萨布”，信息更全"),
    "Manually load a save file.": ("保留", "现值是刻意风格化文案"),
    "Continue with your latest save.": ("保留", "现值更贴合主菜单语气"),
    "YOU HAVE UNLOCKED": ("保留", "现值指明是“形态”解锁，更具体"),
    "Attributes": ("保留", "现值“属性点”更具体"),
    "Interact": ("保留", "“互动”为游戏内惯用词"),
    "Visual Effects Quality": ("保留", "仅措辞差异（视觉效果/视觉特效）"),
    "Quest Objectives:": ("保留", "现值“目标：”更简洁"),
    "THIS IS A OPTIONAL CHAPTER DESCRIPTION.": ("保留", "仅措辞差异"),
    "Fixed a bug that caused the slider button text to be displayed incorrectly": ("保留", "仅“文字/文本”措辞差异"),
    "Fixed an issue where Localization was not possible with the State Buttons": ("保留", "仅“本地化/进行本地化”措辞差异"),
    "Fixed an issue where Intro Videos did not played properly": ("保留", "仅“影片/视频”措辞差异"),
    "Optimized the Sensitivities in the Demo ThirdPersonCharacter": ("保留", "仅“示例/演示用”措辞差异"),
    "Patreon Build - Version ": ("保留", "现值保留 Patreon 品牌名，可接受"),
}

rep = json.load(open(EXP + r"\out\inject_report_full.json", encoding="utf-8"))
kept = [a for a in rep["actions"] if a["action"] == "kept"]
diff = [a for a in kept if a["old_value"] != a["zh"]]
same_n = len(kept) - len(diff)
print(f"保留已有中文 {len(kept)} 条：与本次译文相同 {same_n} 条（无需决策）；不同 {len(diff)} 条（逐条择优）")

rows, cover_keys, missing_plan = [], [], []
for a in diff:
    sug, why = PLAN.get(a["src"], ("?", "未给出建议"))
    if sug == "?":
        missing_plan.append(a["src"])
    if sug == "覆盖":
        cover_keys.append(a["key"])
    rows.append([a["key"], a["src"], a["old_value"], a["zh"], sug, why, "; ".join(a["files"])])
rows.sort(key=lambda r: (r[4] != "覆盖", r[1]))

with open(EXP + r"\out\overwrite_plan.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["key", "src英文", "现值(已有中文)", "本次译文", "建议", "理由", "所在资产"])
    w.writerows(rows)
json.dump({"note": "择优覆盖名单（只影响现值已是中文、且与本次译文不同的条目）",
           "keep_unchanged": same_n, "diff_total": len(diff),
           "cover_count": len(cover_keys), "cover_keys": cover_keys},
          open(EXP + r"\out\overwrite_plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

n_cover = sum(1 for r in rows if r[4] == "覆盖")
n_keep = sum(1 for r in rows if r[4] == "保留")
print(f"建议：覆盖 {n_cover} 条 / 保留 {n_keep} 条")
if missing_plan:
    print(f"⚠ 未给建议的 src: {missing_plan}")
print(f"已写 out/overwrite_plan.csv 与 out/overwrite_plan.json")
print(f"\n覆盖后 locres 条目数不变（2065），只有这 {n_cover} 条的 value 会变。")
