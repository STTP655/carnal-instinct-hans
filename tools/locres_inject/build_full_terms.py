# -*- coding: utf-8 -*-
"""步骤 2-3：组装全量 terms。

输入：out/full_srcs.json（baseline 家族 A 全量 + 词表命中情况）
      new_translations.json（我的人工翻译 / skip 名单 / norm 覆盖）
输出：out/full_terms.json     全量注入清单（每个 key 一条）
      out/vocab_long_check.txt 词表命中的长文本抽样（供人工审查）
只写 out/ 内文件。
"""
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXP = r"D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"

fs = json.load(open(EXP + r"\out\full_srcs.json", encoding="utf-8"))
nt = json.load(open(EXP + r"\new_translations.json", encoding="utf-8"))
rows = fs["rows"]
new = nt["new"]
skip = set(nt["skip"])
override = nt["override_norm"]

# --- 1) 决定每个唯一 src 的译文与来源 ---
resolved = {}       # src -> (zh, source)
missing = []
for r in rows:
    src = r["src"]
    hit = r["vocab_hit"]
    if src in skip:
        resolved[src] = (None, "skip")
        continue
    if hit == "exact":
        resolved[src] = (r["vocab_zh"], "vocab_exact")
    elif hit in ("strip", "norm"):
        if src in override:
            resolved[src] = (override[src], "vocab_" + hit + "_override")
        else:
            resolved[src] = (r["vocab_zh"], "vocab_" + hit)
    else:
        if src in new:
            resolved[src] = (new[src], "new")
        else:
            missing.append(src)

if missing:
    print(f"✗ 有 {len(missing)} 条未命中词表、也未翻译、也未标 skip：")
    for s in missing:
        print(f"   {s!r}")
# 反向检查：new 里有但全量表用不到的（说明我多翻了/拼错了）
all_srcs = {r["src"] for r in rows}
extra_new = sorted(set(new) - all_srcs)
if extra_new:
    print(f"⚠ new_translations 里 {len(extra_new)} 条 src 在全量表中不存在（拼写差异？）：")
    for s in extra_new:
        print(f"   {s!r}")
extra_skip = sorted(skip - all_srcs)
if extra_skip:
    print(f"⚠ skip 名单里 {len(extra_skip)} 条 src 在全量表中不存在：{extra_skip}")

# --- 2) 空译文检查 ---
bad_empty = [s for s, (zh, k) in resolved.items() if zh is not None and zh.strip() == ""]
if bad_empty:
    print(f"✗ 译文为空的 src: {bad_empty}")

# --- 3) 组装 terms（按 key）---
terms = []
for e in fs["baseline_entries"]:
    src = e["src"]
    zh, kind = resolved[src]
    if kind == "skip":
        continue
    terms.append({
        "key": e["key"], "src": src, "zh": zh, "src_kind": kind,
        "n_refs": e["count"], "files": e["files"], "exports": e["exports"],
    })

stat = Counter(t["src_kind"] for t in terms)
src_stat = Counter(k for _, (zh, k) in resolved.items())
print(f"\n唯一 src {len(resolved)} 条：{dict(src_stat)}")
print(f"注入 terms {len(terms)} 条（按 key）：{dict(stat)}")
print(f"SKIP 的 key 数（不注入）: {fs['n_keys'] - len(terms)}")

json.dump({"source": "dist.json baseline 家族 A（空 ns + 32hex GUID）",
           "generated_for": "路线 E 全量铺开",
           "dist_baseline_keys": fs["n_keys"], "n_src": fs["n_src"],
           "n_terms": len(terms), "src_stats": dict(src_stat), "term_stats": dict(stat),
           "terms": terms},
          open(EXP + r"\out\full_terms.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# --- 4) 词表命中的长文本抽样（人工审查用）---
with open(EXP + r"\out\vocab_long_check.txt", "w", encoding="utf-8") as f:
    longs = [r for r in rows if r["vocab_hit"] and r["len"] >= 40]
    longs.sort(key=lambda r: -r["len"])
    f.write(f"# 词表命中的长文本（len>=40）：{len(longs)} 条\n\n")
    for r in longs:
        f.write(f"src({r['len']})={r['src']!r}\n  zh={r['vocab_zh']!r}\n  hit={r['vocab_hit']} "
                f"n_keys={r['n_keys']} files={r['files']}\n\n")
    # 译文异常（无 CJK 且原文很长 / 译文远短于原文）
    weird = [r for r in rows if r["vocab_hit"] and r["len"] >= 25 and r["vocab_zh"] is not None
             and len(r["vocab_zh"]) < max(4, r["len"] * 0.25)]
    f.write(f"\n# 译文长度异常偏短的命中项：{len(weird)} 条\n\n")
    for r in weird:
        f.write(f"src={r['src']!r}\n  zh={r['vocab_zh']!r} (len {len(r['vocab_zh'])} vs src {r['len']})\n\n")
print(f"已写 out/full_terms.json 与 out/vocab_long_check.txt")
