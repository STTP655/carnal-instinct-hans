# -*- coding: utf-8 -*-
"""步骤 1：从 dist.json 的 baseline 提取全部家族 A（空 ns + 32hex GUID）内联 FText。

产出：
  out/full_famA_entries.json   全量 (key, src) 表（baseline 逐字）
  out/full_srcs.json           去重后的 src 列表 + 引用 key 数 + 词表命中情况 + 长度分布
只读 dist.json / main.lua，只写 out/ 下文件。
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"D:\DSH工作区\CarnalInstinct_汉化"
EXP = r"D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"
DIST = BASE + r"\05_研究\bp_static\scan_ftext\dist.json"
LUA = BASE + r"\05_研究\ue4ss_mod\UIZh\scripts\main.lua"
GUID = re.compile(r"^[0-9A-Fa-f]{32}$")

d = json.load(open(DIST, encoding="utf-8"))

# --- main.lua 词表：按 json.loads 语义解析 Lua 字符串转义 ---
lua_src = open(LUA, encoding="utf-8").read()
LUA_PAT = re.compile(r'^\s*\["((?:[^"\\]|\\.)*)"\]\s*=\s*"((?:[^"\\]|\\.)*)"', re.M)


def unesc(raw):
    """Lua 字符串字面量 → 真实字符串（按 json.loads 语义，失败则退回手工替换）。"""
    try:
        return json.loads('"' + raw + '"')
    except Exception:
        out = []
        i = 0
        while i < len(raw):
            c = raw[i]
            if c == "\\" and i + 1 < len(raw):
                n = raw[i + 1]
                out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'",
                            "\\": "\\"}.get(n, n))
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)


pairs = [(unesc(a), unesc(b)) for a, b in LUA_PAT.findall(lua_src)]
vocab_exact = OrderedDict()          # src -> zh（精确，大小写敏感）
for k, v in pairs:
    vocab_exact.setdefault(k, v)
vocab_exact_strip = OrderedDict()    # src.strip() -> zh
for k, v in pairs:
    vocab_exact_strip.setdefault(k.strip(), v)
print(f"main.lua 词表: {len(pairs)} 组，去重精确键 {len(vocab_exact)} 个")


def norm(s):
    return re.sub(r"[\s\-_']", "", s.lower())


vocab_norm = OrderedDict()
for k, v in pairs:
    vocab_norm.setdefault(norm(k), v)
print(f"          归一化键 {len(vocab_norm)} 个")


def lookup(src):
    """返回 (命中方式, 词表译文) 或 (None, None)。"""
    if src in vocab_exact:
        return "exact", vocab_exact[src]
    s = src.strip()
    if s and s in vocab_exact_strip:
        return "strip", vocab_exact_strip[s]
    n = norm(src.strip())
    if n and n in vocab_norm:
        return "norm", vocab_norm[n]
    return None, None


# --- 两个数据源的 key 集合比较 ---
def fam_a(seg):
    out = []
    for e in seg["keys"]:
        if e["ns"] == "" and GUID.match(e["key"]):
            assert len(e["sources"]) == 1, f"{e['key']} sources 非单源: {list(e['sources'])}"
            src = next(iter(e["sources"]))
            out.append({"key": e["key"], "src": src, "count": e["count"],
                        "files": e["files"], "n_files": e.get("n_files", len(e["files"])),
                        "exports": e.get("exports", [])})
    return out


pa = fam_a(d["primary"])
ba = fam_a(d["baseline"])
print(f"\n家族 A：primary {len(pa)} 条（唯一 key {len({x['key'] for x in pa})}），"
      f"baseline {len(ba)} 条（唯一 key {len({x['key'] for x in ba})}）")
pk = {x["key"] for x in pa}
bk = {x["key"] for x in ba}
print(f"key 集合: primary-only={len(pk-bk)} baseline-only={len(bk-pk)} 相同={len(pk&bk)==len(pk)==len(bk)}")
src_diff = [k for k in pk & bk
            if next(x["src"] for x in pa if x["key"] == k) != next(x["src"] for x in ba if x["key"] == k)]
print(f"同 key 但 src 不同: {len(src_diff)} 条 {src_diff[:5]}")

# 非家族 A 的那条
other = [e for e in d["baseline"]["keys"] if not (e["ns"] == "" and GUID.match(e["key"]))]
print(f"baseline 非家族 A 条目: {other}")

# --- 去重并统计 ---
by_src = OrderedDict()
for e in ba:
    by_src.setdefault(e["src"], []).append(e)

n_key = len(ba)
n_src = len(by_src)
hit = Counter()
rows = []
for src, es in by_src.items():
    how, zh = lookup(src)
    hit[how or "none"] += 1
    rows.append({"src": src, "n_keys": len(es), "keys": [x["key"] for x in es],
                 "files": sorted({f for x in es for f in x["files"]}),
                 "exports": [ex for x in es for ex in x["exports"]],
                 "n_refs": sum(x["count"] for x in es),
                 "vocab_hit": how, "vocab_zh": zh,
                 "len": len(src)})
rows.sort(key=lambda r: (r["vocab_hit"] is None, -r["n_keys"], r["src"]))

print(f"\nkey 总数 {n_key}；去重 src {n_src} 条")
print(f"词表命中: exact={hit['exact']} strip={hit['strip']} norm={hit['norm']} 未命中={hit['none']}")
print(f"未命中的唯一 src: {hit['none']} 条")
lens = [r["len"] for r in rows]
print(f"src 长度: min={min(lens)} max={max(lens)} 中位={sorted(lens)[len(lens)//2]}")

empty = [r for r in rows if not r["src"].strip()]
sym = [r for r in rows if r["src"].strip() and not re.search(r"[A-Za-z]", r["src"])]
print(f"空/纯空白 src: {len(empty)}；无拉丁字母的 src: {len(sym)} → {[r['src'] for r in sym][:20]}")
big = [r for r in rows if r["len"] > 400]
print(f"长度 > 400 的长文本: {len(big)} 条")

json.dump({"baseline_entries": ba, "n_keys": n_key, "n_src": n_src,
           "vocab_stats": dict(hit), "rows": rows},
          open(EXP + r"\out\full_srcs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n已写 {EXP}\\out\\full_srcs.json")
