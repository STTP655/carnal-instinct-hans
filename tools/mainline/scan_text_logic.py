#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描游戏全部资产，找出「文本进入逻辑比较」的资产 + 建立 FText 键->资产 映射。

判据：资产 Zen 头部的名字表里出现以下函数名之一，即认为该资产存在"文本参与逻辑"：
  Conv_TextToString / EqualEqual_TextText / NotEqual_TextText / TextIsEmpty /
  GetDisplayNameTextByValue / Conv_StringToText
输出：
  build/ui-research/asset_ftexts.json   path -> {markers:[], ftexts:[[guid, src], ...]}
  build/ui-research/scan_report.json    extras 统计、逻辑资产清单、建议保护键
"""
import json
import re
import struct
import sys
import time
from pathlib import Path

BASE = Path(r"E:\AI项目\CarnalInstinct")
SCAN = BASE / "build/asset-scan"
OUT = BASE / "build/ui-research"
TAG = b"\xc1\x83\x2a\x9e"
MARKERS = [b"Conv_TextToString", b"EqualEqual_TextText", b"NotEqual_TextText",
           b"TextIsEmpty", b"GetDisplayNameTextByValue", b"Conv_StringToText"]
LOGIC_MARKERS = {"Conv_TextToString", "EqualEqual_TextText", "NotEqual_TextText",
                 "TextIsEmpty", "GetDisplayNameTextByValue"}
GUID = re.compile(rb"\x21\x00\x00\x00([0-9A-F]{32})\x00")

sys.path.insert(0, str(BASE.parent / "carnal-instinct-hans/tools/locres_inject"))
import locres_lib as L  # noqa: E402


def read_fs(b, pos):
    if pos + 4 > len(b):
        return None
    n = struct.unpack_from("<i", b, pos)[0]
    if n <= 0 or n > (1 << 20):
        return None
    if pos + 4 + n > len(b) or b[pos + 4 + n - 1] != 0:
        return None
    try:
        return b[pos + 4:pos + 4 + n - 1].decode("ascii")
    except UnicodeDecodeError:
        return None


def phase_scan():
    assets = {}
    t0 = time.time()
    for cdir in sorted(SCAN.iterdir()):
        man = cdir / "manifest.json"
        if not man.exists():
            continue
        data = json.loads(man.read_text(encoding="utf-8"))
        chunks = cdir / "chunks"
        n = 0
        for cid, path in data["chunk_paths"].items():
            f = chunks / cid
            if not f.exists():
                continue
            b = f.read_bytes()
            if len(b) < 16:
                continue
            try:
                h = struct.unpack_from("<i", b, 4)[0]
            except struct.error:
                continue
            if not (0 < h < len(b) - 4):
                continue
            header = b[:h]
            export = b[h:-4] if b[h:][-4:] == TAG else b[h:]
            marks = [m.decode() for m in MARKERS if m in header]
            fts = []
            for m in GUID.finditer(export):
                src = read_fs(export, m.end())
                fts.append([m.group(1).decode(), src])
            if marks or fts:
                assets[path] = {"markers": marks, "ftexts": fts}
            n += 1
        print(f"[scan] {cdir.name}: {n} assets, elapsed {time.time()-t0:.0f}s", flush=True)
    out = OUT / "asset_ftexts.json"
    out.write_text(json.dumps(assets, ensure_ascii=False), encoding="utf-8")
    print(f"[scan] 写出 {out}  ({out.stat().st_size/1e6:.1f} MB)", flush=True)
    return assets


def phase_report(assets):
    fix = L.load(str(BASE.parent / "carnal-instinct-hans/data/Game.locres.fix1"))
    full = L.load(str(BASE.parent / "carnal-instinct-hans/data/Game.locres.full"))
    def keys(d):
        return {(ns.name, e.key) for ns in d["namespaces"] for e in ns.entries}
    fixk, fullk = keys(fix), keys(full)
    extras = fixk - fullk
    guid2assets = {}
    for path, info in assets.items():
        for g, src in info["ftexts"]:
            guid2assets.setdefault(g, []).append(path)
    logic_assets = {p for p, i in assets.items() if LOGIC_MARKERS & set(i["markers"])}
    protect = set()
    nomap = 0
    per_marker = {}
    for k in extras:
        g = k[1]
        owners = guid2assets.get(g, [])
        if not owners:
            nomap += 1
            continue
        hit = [o for o in owners if o in logic_assets]
        if hit:
            protect.add(k)
            for o in hit:
                for mk in assets[o]["markers"]:
                    per_marker[mk] = per_marker.get(mk, 0) + 1
    report = {
        "assets_scanned_with_text": len(assets),
        "logic_assets": len(logic_assets),
        "fix1_entries": len(fixk),
        "full_entries": len(fullk),
        "extras": len(extras),
        "extras_without_asset_map": nomap,
        "suggest_protect": len(protect),
        "marker_hits_on_protect": per_marker,
        "logic_asset_list": sorted(logic_assets),
        "protect_keys": sorted([list(k) for k in protect]),
    }
    (OUT / "scan_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1))
    print("逻辑资产数:", len(logic_assets), " 建议保护键:", len(protect), " 无法映射:", nomap)
    print("--- 逻辑资产示例（前 30）")
    for p in sorted(logic_assets)[:30]:
        print("   ", p)
    print("--- 保护键样例（前 20）")
    for k in sorted(protect)[:20]:
        g = k[1]
        owners = guid2assets.get(g, [])
        print("   ", g, owners[:2], assets.get(owners[0], {}).get("markers") if owners else None)


def main():
    if (OUT / "asset_ftexts.json").exists() and "--reuse" in sys.argv:
        print("[scan] 复用已有 asset_ftexts.json")
        assets = json.loads((OUT / "asset_ftexts.json").read_text(encoding="utf-8"))
    else:
        assets = phase_scan()
    phase_report(assets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
