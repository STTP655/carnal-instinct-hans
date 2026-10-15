# -*- coding: utf-8 -*-
"""路线 E 全量注入：把 baseline 家族 A 的全部内联 FText 译成中文写入 Game.locres。

策略（默认"安全模式"）：
  - key 不在 locres            → 追加新条目（source_hash = str_crc32(英文原文)）
  - key 已在 locres 且现值含中文 → 保留原值（kept，不覆盖已有汉化）
  - key 已在 locres 且现值无中文 → 更新为本次译文（update）
  加 --overwrite-existing 则连"已是中文"的也一律覆盖（可复现另一种口径）。

输入：out/full_terms.json（由 build_full_terms.py 生成，key/src 逐字来自 dist.json baseline）
      work/orig_pak/.../en/Game.locres（当前生效的中文 locres）
输出：out/Game.locres.full + out/inject_report_full.json + out/overlap_detail.csv
只写实验目录内文件。
"""
import csv
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import locres_lib as L

BASE = r"D:\DSH工作区\CarnalInstinct_汉化"
EXP = HERE
SRC_LOCRES = EXP + r"\work\orig_pak\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres"
OUT_LOCRES = EXP + r"\out\Game.locres.full"
DIST = BASE + r"\05_研究\bp_static\scan_ftext\dist.json"
TERMS = EXP + r"\out\full_terms.json"
REPORT = EXP + r"\out\inject_report_full.json"
OVERLAP = EXP + r"\out\overlap_detail.csv"
OVERWRITE = "--overwrite-existing" in sys.argv
CJK = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef\u3000-\u303f]")

print(f"[1/7] 读全量词条定义（模式：{'覆盖已有' if OVERWRITE else '安全（保留已有中文）'}）")
spec = json.load(open(TERMS, encoding="utf-8"))
terms = spec["terms"]
print(f"      {len(terms)} 条 terms；来源分布 {spec['term_stats']}")

print("[2/7] 用 dist.json baseline 逐字复核 (key → src)")
dist = json.load(open(DIST, encoding="utf-8"))
GUID = re.compile(r"^[0-9A-Fa-f]{32}$")
dmap = {}
for e in dist["baseline"]["keys"]:
    if e["ns"] == "" and GUID.match(e["key"]):
        assert len(e["sources"]) == 1
        dmap[e["key"]] = (next(iter(e["sources"])), e)
bad = 0
for t in terms:
    got = dmap.get(t["key"])
    assert got is not None, f"baseline 里找不到 {t['key']}"
    if got[0] != t["src"]:
        print(f"      ✗ {t['key']} src 不一致: baseline={got[0]!r} terms={t['src']!r}")
        bad += 1
assert bad == 0, f"{bad} 条 src 与 baseline 不一致，中止"
print(f"      ✓ 全部 {len(terms)} 条的 key/src 与 dist.json baseline 逐字一致")
n_baseline_keys = len(dmap)
print(f"      baseline 家族 A 共 {n_baseline_keys} key；本次注入 {len(terms)}，"
      f"未注入（SKIP 纯数字/符号/占位）{n_baseline_keys - len(terms)}")

print("[3/7] 载入当前生效的中文 locres")
raw = open(SRC_LOCRES, "rb").read()
d = L.loads(raw)
n_before = L.total_entries(d)
assert L.dumps(d) == raw, "序列化器 round-trip 校验失败，中止"
keys_before = {(ns.name, e.key.upper()) for ns in d["namespaces"] for e in ns.entries}
src_hash_before = {}
for ns in d["namespaces"]:
    for e in ns.entries:
        src_hash_before.setdefault((ns.name, e.key.upper()), []).append(e.source_hash)
print(f"      {len(raw)} 字节, version={d['version']}, {L.total_entries(d)} 条, "
      f"stringTable {len(d['string_table'])} 条（round-trip ✓）")

print("[4/7] 注入")
target_ns = next(ns for ns in d["namespaces"] if ns.name == "")
live = {e.key.upper(): e for e in target_ns.entries}
actions = []
overlap_rows = []
for t in terms:
    k = t["key"].upper()
    cur = live.get(k)
    if cur is None:
        sh = L.str_crc32(t["src"])
        target_ns.entries.append(L.Entry(t["key"], t["zh"], sh))
        live[k] = target_ns.entries[-1]
        act, old = "add", None
    else:
        old = cur.value
        if CJK.search(old) and not OVERWRITE:
            act = "kept"
            sh = cur.source_hash
        else:
            cur.value = t["zh"]
            act, sh = "update", cur.source_hash
    actions.append({"action": act, "key": t["key"], "src": t["src"], "zh": t["zh"],
                    "old_value": old, "src_kind": t["src_kind"], "n_refs": t["n_refs"],
                    "files": t["files"], "exports": t["exports"],
                    "source_hash": sh, "key_hash": L.cityhash64_utf16_to_uint32(t["key"])})

stat = Counter(a["action"] for a in actions)
print(f"      新增 {stat['add']} / 更新 {stat['update']} / 保留已有中文 {stat['kept']}")
# baseline ∩ locres 的 280 组里，被 SKIP（纯数字/符号）而没进 terms 的有 27 组
terms_keys = {t["key"].upper() for t in terms}
overlap_all = {k for k in dmap if k.upper() in {kk for _, kk in keys_before}}
overlap_in_terms = {k for k in overlap_all if k.upper() in terms_keys}
print(f"      baseline∩locres = {len(overlap_all)} 组；其中本次 terms 覆盖 "
      f"{len(overlap_in_terms)} 组（SKIP {len(overlap_all)-len(overlap_in_terms)} 组）")
assert stat["update"] + stat["kept"] == len(overlap_in_terms), \
    f"已存在条目数异常: {stat['update']+stat['kept']} != {len(overlap_in_terms)}"

# 已存在 280 条的现状明细（供审校）
live_all = {e.key.upper(): e for ns in d["namespaces"] for e in ns.entries}
for t in terms:
    k = t["key"].upper()
    if k in live_all:
        if not live_all[k].key == t["key"]:
            pass
seen = set()
for e in d["namespaces"][0].entries:
    if e.key.upper() in {t["key"].upper() for t in terms} and e.key.upper() not in seen:
        seen.add(e.key.upper())
for a in actions:
    if a["action"] in ("update", "kept"):
        overlap_rows.append([a["key"], a["src"], a["old_value"], a["zh"], a["action"],
                             a["src_kind"]])

out = L.dumps(d)
open(OUT_LOCRES, "wb").write(out)
print(f"      写出 {OUT_LOCRES}（{len(out)} 字节，原 {len(raw)} 字节，{len(out)-len(raw):+d}）")

print("[5/7] 离线自校验")
chk = L.loads(out)
n_after = L.total_entries(chk)
ok = True
expect = n_before + stat["add"]
print(f"      条目数 {n_before} → {n_after}（预期 {expect}）{'✓' if n_after == expect else '✗'}")
ok &= (n_after == expect)
if L.dumps(chk) != out:
    print("      ✗ 产物 round-trip 不一致"); ok = False
else:
    print("      ✓ 产物 round-trip 一致（逐字节）")
chk_ns = next(ns for ns in chk["namespaces"] if ns.name == "")
cmap = {}
for e in chk_ns.entries:
    if e.key.upper() in cmap:
        print(f"      ✗ 重复 key {e.key}"); ok = False
    cmap[e.key.upper()] = e
bad_read = 0
kept_ok = 0
for a in actions:
    e = cmap.get(a["key"].upper())
    if e is None:
        bad_read += 1
        continue
    if a["action"] == "kept":
        if e.value != a["old_value"]:
            print(f"      ✗ 保留项被改动 {a['key']}"); ok = False
        else:
            kept_ok += 1
    elif e.value != a["zh"]:
        print(f"      ✗ 读回不一致 {a['key']}: {e.value!r} != {a['zh']!r}"); ok = False
print(f"      ✓ 读回校验：新增/更新 {len(actions)-stat['kept']-bad_read} 条正确，"
      f"保留项 {kept_ok} 条未被改动" if bad_read == 0 and ok else f"      ✗ 读回失败 {bad_read} 条")
new_keys = {(ns.name, e.key.upper()) for ns in chk["namespaces"] for e in ns.entries}
missing = keys_before - new_keys
print(f"      旧条目丢失 {len(missing)} 条 {'✓' if not missing else '✗ ' + str(list(missing)[:3])}")
ok &= not missing
added = new_keys - keys_before
print(f"      新增条目 {len(added)} 条 {'✓' if len(added) == stat['add'] else '✗'}")
ok &= (len(added) == stat["add"])
bad_hash = sum(1 for ns in chk["namespaces"] for e in ns.entries
               if e.key_hash != L.cityhash64_utf16_to_uint32(e.key))
print(f"      key hash 复核: {'✓ 全部通过' if bad_hash == 0 else f'✗ {bad_hash} 条不符'}")
ok &= (bad_hash == 0)
bad_src = 0
new_hashes = {}
for ns in chk["namespaces"]:
    for e in ns.entries:
        new_hashes.setdefault((ns.name, e.key.upper()), []).append(e.source_hash)
for k, v in src_hash_before.items():
    if new_hashes.get(k) != v:
        bad_src += 1
        print(f"      ✗ sourceHash 变化 {k}: {v} → {new_hashes.get(k)}")
print(f"      已存在条目的 sourceStringHash 保持: {'✓' if bad_src == 0 else f'✗ {bad_src} 条被改'}"
      f"（注：CommonTermsUI/CORRUPTION 与 /OFF 原文件即各有 2 条重复 key，按多重集比对）")
ok &= (bad_src == 0)
n_cjk = sum(1 for ns in chk["namespaces"] for e in ns.entries if CJK.search(e.value))
print(f"      locres 内中文条目数: {n_cjk} / {n_after}")

print("[6/7] 写报告与重叠明细")
with open(OVERLAP, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["key", "src英文", "注入前现值", "本次译文", "动作", "译文来源"])
    for r in sorted(overlap_rows, key=lambda x: (x[4], x[1])):
        w.writerow(r)
print(f"      {len(overlap_rows)} 条已存在条目明细 → {OVERLAP}")
report = {"mode": "overwrite" if OVERWRITE else "safe(keep-existing-cjk)",
          "source_locres": SRC_LOCRES, "output": OUT_LOCRES,
          "entries_before": n_before, "entries_after": n_after,
          "baseline_family_a_keys": n_baseline_keys, "terms": len(terms),
          "skipped_keys": n_baseline_keys - len(terms),
          "action_stats": dict(stat), "output_bytes": len(out),
          "verified": bool(ok), "overlap_detail": OVERLAP,
          "actions": actions}
json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("[7/7] 结论：" + ("全部自校验通过 ✓" if ok else "存在问题 ✗"))
sys.exit(0 if ok else 1)
