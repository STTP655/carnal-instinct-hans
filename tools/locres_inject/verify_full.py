# -*- coding: utf-8 -*-
"""全量产物验证（可重跑，只读 + 打印）。

1) full_terms.json 的 (key, src) 与 dist.json baseline 逐字一致
2) out/Game.locres.full 自解析：条目数、round-trip、旧条目零丢失、中文条目数、key hash
3) 每个 term 在 locres 里读回（kept 项保留原值）
4) work/verify_unpack_full 中从 pak 解出的 locres 与注入产物 SHA256 一致；5 个 ufont 与原版一致
5) pak 文件大小 / SHA256 记录
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXP = r"D:\DSH工作区\CarnalInstinct_汉化\05_研究\bp_static\locres_experiment"
BASE = r"D:\DSH工作区\CarnalInstinct_汉化"
sys.path.insert(0, EXP)
import locres_lib as L

GUID = re.compile(r"^[0-9A-Fa-f]{32}$")
CJK = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef\u3000-\u303f]")
ok = True


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


# --- 1) terms vs baseline ---
dist = json.load(open(BASE + r"\05_研究\bp_static\scan_ftext\dist.json", encoding="utf-8"))
dmap = {}
for e in dist["baseline"]["keys"]:
    if e["ns"] == "" and GUID.match(e["key"]):
        dmap[e["key"]] = next(iter(e["sources"]))
spec = json.load(open(EXP + r"\out\full_terms.json", encoding="utf-8"))
terms = spec["terms"]
bad = [t["key"] for t in terms if dmap.get(t["key"]) != t["src"]]
print(f"[1] terms {len(terms)} 条 vs baseline {len(dmap)} 条："
      f"{'✓ key/src 逐字一致' if not bad else f'✗ {len(bad)} 条不一致'}")
ok &= not bad

# --- 2) 自解析全量 locres ---
p_full = EXP + r"\out\Game.locres.full"
raw = open(p_full, "rb").read()
d = L.loads(raw)
n = L.total_entries(d)
rt = L.dumps(d) == raw
print(f"[2] {p_full}")
print(f"    {len(raw)} 字节, version={d['version']}, {n} 条, "
      f"namespace={[ns.name for ns in d['namespaces']]} → {L.dumps(d) == raw and '✓ round-trip 一致' or '✗'}")
ok &= rt
old = L.load(EXP + r"\work\orig_pak\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres")
old_keys = [(ns.name, e.key.upper()) for ns in old["namespaces"] for e in ns.entries]
new_keys = [(ns.name, e.key.upper()) for ns in d["namespaces"] for e in ns.entries]
co, cn = Counter(old_keys), Counter(new_keys)
missing = co - cn
added = cn - co
exp_add = json.load(open(EXP + r"\out\inject_report_full.json", encoding="utf-8"))["action_stats"]["add"]
print(f"    旧条目 {L.total_entries(old)} 条 → 丢失 {sum(missing.values())} 条；"
      f"新增 {sum(added.values())} 条（预期 {exp_add}）"
      f"{'✓' if not missing and sum(added.values()) == exp_add else '✗'}")
ok &= (not missing and sum(added.values()) == exp_add and n == L.total_entries(old) + exp_add)
bad_hash = sum(1 for ns in d["namespaces"] for e in ns.entries
               if e.key_hash != L.cityhash64_utf16_to_uint32(e.key))
print(f"    key hash 复核 {bad_hash} 条不符 ✓" if bad_hash == 0 else f"    ✗ key hash {bad_hash} 条不符")
ok &= bad_hash == 0
nz = sum(1 for ns in d["namespaces"] for e in ns.entries if CJK.search(e.value))
print(f"    中文条目 {nz} / {n}")

# --- 3) 逐 term 读回 ---
live = {}
for ns in d["namespaces"]:
    for e in ns.entries:
        live.setdefault((ns.name, e.key.upper()), []).append(e)
rep = json.load(open(EXP + r"\out\inject_report_full.json", encoding="utf-8"))
bad3 = 0
stat = Counter()
for a in rep["actions"]:
    got = live.get(("", a["key"].upper()))
    if not got:
        bad3 += 1
        continue
    v = got[0].value
    if a["action"] == "kept":
        good = v == a["old_value"]
    else:
        good = v == a["zh"]
    stat[a["action"]] += 1
    if not good:
        bad3 += 1
        print(f"    ✗ {a['key']} 读回 {v!r} != 期望")
print(f"[3] 逐条读回：{dict(stat)}；失败 {bad3} 条 {'✓' if bad3 == 0 else '✗'}")
ok &= bad3 == 0

# --- 4) pak 解包比对 ---
p_unp = EXP + r"\work\verify_unpack_full\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres"
if os.path.exists(p_unp):
    same = sha(p_unp) == sha(p_full)
    print(f"[4] pak 解出的 locres SHA256 = {sha(p_unp)}")
    print(f"    注入产物 locres SHA256   = {sha(p_full)}  → {'✓ 一致' if same else '✗ 不一致'}")
    ok &= same
    same_font = True
    for f in ("RobotoBold.ufont", "RobotoBoldItalic.ufont", "RobotoItalic.ufont",
              "RobotoLight.ufont", "RobotoRegular.ufont"):
        a = EXP + r"\work\orig_pak\Carnal_Instinct_UE5\Content\MSL_Toolkit\localization_system\data\fonts\roboto\\" + f
        b = EXP + r"\work\verify_unpack_full\Carnal_Instinct_UE5\Content\MSL_Toolkit\localization_system\data\fonts\roboto\\" + f
        same_font &= sha(a) == sha(b)
    print(f"    5 个 ufont 与原版逐字节一致：{'✓' if same_font else '✗'}")
    ok &= same_font
else:
    print(f"[4] 未找到 {p_unp}（先跑 repak unpack 再验证）")

# --- 5) pak 文件 ---
p_pak = EXP + r"\out\pakchunk1013-Windows.full.pak"
p_oldloc = EXP + r"\work\orig_pak\Carnal_Instinct_UE5\Content\Localization\Game\en\Game.locres"
print(f"[5] {p_pak}\n    {os.path.getsize(p_pak):,} 字节  SHA256 = {sha(p_pak)}")
print(f"    原版 locres SHA256 = {sha(p_oldloc)}")
print("\n结论：" + ("全量产物验证全部通过 ✓" if ok else "存在问题 ✗"))
sys.exit(0 if ok else 1)
