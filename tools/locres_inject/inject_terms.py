# -*- coding: utf-8 -*-
"""路线 E 实验：向当前生效的中文 Game.locres 注入实验词条（空 Namespace + GUID Key）。

- 已存在的 key → 只改 value（源串哈希保持原值）
- 不存在的 key → 追加新条目（sourceStringHash = str_crc32(英文原文)，key hash 由库计算）
- 其余条目顺序、字节语义完全不动（序列化器已通过 byte-identical round-trip 验证）

输入：work/orig_pak/.../en/Game.locres（从游戏 pak 解出的当前生效版本）
输出：out/Game.locres.experiment  +  out/inject_report.json

只写实验目录内文件，不碰游戏目录。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import locres_lib as L

BASE = r"D:\DSH工作区\CarnalInstinct_汉化"
EXP = HERE
SRC_LOCRES = EXP + r"\work\orig_pak\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres"
OUT_LOCRES = EXP + r"\out\Game.locres.experiment"
DIST = BASE + r"\05_研究\bp_static\scan_ftext\dist.json"
LUA = BASE + r"\05_研究\ue4ss_mod\UIZh\scripts\main.lua"
TERMS = EXP + r"\experiment_terms.json"
REPORT = EXP + r"\out\inject_report.json"

print("[1/6] 读入实验词条定义")
spec = json.load(open(TERMS, encoding="utf-8"))
terms = spec["terms"]
print(f"      {len(terms)} 条：")
for t in terms:
    print(f"        {t['key']}  {t['src']!r} → {t['zh']!r}  ({t.get('where','')})")

print("[2/6] 用 dist.json 校验每条 (key → 源串) 完全一致")
dist = json.load(open(DIST, encoding="utf-8"))
dmap = {}
for e in dist["primary"]["keys"]:
    if e["ns"] == "":
        dmap[(e["ns"], e["key"])] = e
for t in terms:
    e = dmap.get(("", t["key"]))
    assert e is not None, f"dist.json 里找不到 {t['key']}"
    srcs = list(e["sources"].keys())
    assert srcs == [t["src"]], f"{t['key']} 源串不一致: dist={srcs} spec={t['src']!r}"
    print(f"      ✓ {t['key']} → {t['src']!r}  (dist 出现 {e['count']} 次, 文件 {e['files']})")

print("[3/6] 核对 main.lua 词表状态（按每条 in_lua_vocab 标记核对）")
import re
lua_src = open(LUA, encoding="utf-8").read()
lua_pairs = [(m.group(1).replace('\\"', '"'), m.group(2)) for m in
             re.finditer(r'^\s*\["((?:[^"\\]|\\.)*)"\]\s*=\s*"((?:[^"\\]|\\.)*)"', lua_src, re.M)]
lua_keys = [k for k, _ in lua_pairs]


def norm(s):
    return re.sub(r"[\s\-_']", "", s.lower())


lua_norm = {norm(k): v for k, v in lua_pairs}
n_vocab = 0
for t in terms:
    declared = t.get("in_lua_vocab")
    hit = norm(t["src"]) in lua_norm
    assert declared in (True, False), f"{t['src']!r} 缺少 in_lua_vocab 标记"
    assert hit == declared, (f"{t['src']!r} 的 in_lua_vocab 标记={declared} 与实际={hit} 不符")
    if hit:
        n_vocab += 1
        print(f"      ⚠ {t['src']!r} 在 main.lua 词表内 → "
              f"{[v for k, v in lua_pairs if norm(k) == norm(t['src'])]}"
              f"  （mod 已关闭，不影响本次判读）")
    else:
        print(f"      ✓ {t['src']!r} 不在词表内")
print(f"      词表 {len(lua_keys)} 条；本次 {len(terms)} 条中 {n_vocab} 条与词表重合（已标注）")

print("[4/6] 载入当前生效的中文 locres")
raw = open(SRC_LOCRES, "rb").read()
d = L.loads(raw)
n_before = L.total_entries(d)
assert L.dumps(d) == raw, "序列化器 round-trip 校验失败，中止"
print(f"      {len(raw)} 字节, version={d['version']}, {len(d['namespaces'])} 个 namespace, "
      f"{n_before} 条条目, stringTable {len(d['string_table'])} 条（round-trip ✓）")

print("[5/6] 注入")
target_ns = next(ns for ns in d["namespaces"] if ns.name == "")
keys_before = {(ns.name, e.key) for ns in d["namespaces"] for e in ns.entries}
report = {"source_locres": SRC_LOCRES, "entries_before": n_before, "actions": []}
for t in terms:
    hit = next((e for e in target_ns.entries if e.key == t["key"]), None)
    if hit is not None:
        old = hit.value
        hit.value = t["zh"]
        act = "update"
        src_hash = hit.source_hash
        print(f"      [更新] {t['key']}  {old!r} → {t['zh']!r}   (源串哈希保持 0x{hit.source_hash:08X})")
    else:
        old = None
        src_hash = L.str_crc32(t["src"])
        target_ns.entries.append(L.Entry(t["key"], t["zh"], src_hash))
        act = "add"
        print(f"      [新增] {t['key']}  {t['src']!r} → {t['zh']!r}  "
              f"(sourceStringHash = str_crc32({t['src']!r}) = 0x{src_hash:08X})")
    report["actions"].append({
        "action": act, "key": t["key"], "ns": "", "src": t["src"], "zh": t["zh"],
        "where": t.get("where", ""), "file": dmap[("", t["key"])]["files"],
        "export": dmap[("", t["key"])]["exports"],
        "source_hash": src_hash, "key_hash": L.cityhash64_utf16_to_uint32(t["key"]),
        "old_value": old,
    })

out = L.dumps(d)
open(OUT_LOCRES, "wb").write(out)
print(f"      写出 {OUT_LOCRES}  ({len(out)} 字节, 原 {len(raw)} 字节, 差 {len(out)-len(raw):+d})")

print("[6/6] 离线自校验（重新解析产物 + round-trip + 旧条目不变）")
chk = L.loads(out)
n_after = L.total_entries(chk)
chk_ns = next(ns for ns in chk["namespaces"] if ns.name == "")
ok = True
print(f"      条目数 {n_before} → {n_after}（应为 {n_before + sum(1 for a in report['actions'] if a['action']=='add')}）")
if L.dumps(chk) != out:
    print("      ✗ 产物 round-trip 不一致"); ok = False
else:
    print("      ✓ 产物 round-trip 一致")
for a in report["actions"]:
    e = next((x for x in chk_ns.entries if x.key == a["key"]), None)
    if e is None or e.value != a["zh"]:
        print(f"      ✗ 读回失败: {a['key']}"); ok = False
    else:
        print(f"      ✓ 读回 {a['key']} → {e.value!r}  hash=0x{e.source_hash:08X}")
# 旧条目一个不少（同 key 集合包含关系）
new_keys = set()
for ns in chk["namespaces"]:
    for e in ns.entries:
        new_keys.add((ns.name, e.key))
missing = keys_before - new_keys
print(f"      旧条目丢失 {len(missing)} 条 {'✓' if not missing else '✗ ' + str(list(missing)[:3])}")
added = new_keys - keys_before
print(f"      新增条目 {len(added)} 条: {sorted(k for _, k in added)}")
# hash 全量复核
bad = sum(1 for ns in chk["namespaces"] for e in ns.entries
          if e.key_hash != L.cityhash64_utf16_to_uint32(e.key))
print(f"      key hash 复核: {'✓ 全部通过' if bad == 0 else f'✗ {bad} 条不符'}")

report.update({"entries_after": n_after, "output": OUT_LOCRES, "output_bytes": len(out),
               "added": sorted(k for _, k in added), "verified": bool(ok and not missing and not bad)})
json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n报告已写 {REPORT}")
print("结论：" + ("全部自校验通过 ✓" if report["verified"] else "存在问题 ✗"))
