#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主线工具：从上游全量 locres + 保护清单，生成最终可用的 UI locres。

原理
----
UMG 蓝图里的内联 FText = (空 namespace + 32 位 hex GUID key + 英文原文)。
运行时 FText 先查 locres、查不到才回落内联英文，所以只要往 Game.locres 注入
(空ns, GUID) -> 中文，即可覆盖 UI 文本，蓝图零改动。

但是：有一批条目的显示文本会被游戏代码反读出来当逻辑键（枚举显示名、环形菜单
DT_Menu、文本比较资产内的文本）。翻译它们会导致功能异常（普通攻击/环形菜单/存档），
所以这些键必须保持英文——见 data/protect_list.json。

用法
----
方式 A（推荐，直接用已整理好的保护清单）：
    python build_protected_locres.py \
        --fix1 data/Game.locres.fix1 \
        --protect data/protect_list.json \
        --out data/Game.locres.mainline

方式 B（从原始扫描产物重建保护集，--free 指定允许放开的显示型枚举资产名）：
    python build_protected_locres.py \
        --fix1 data/Game.locres.fix1 \
        --enum-all enum_all.json --dt-menu DT_Menu.chunk \
        --scan-report scan_report.json --asset-ftexts asset_ftexts.json \
        --free E_SaveType,E_StatType --out data/Game.locres.mainline
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "locres_inject"))
import locres_lib as L  # noqa: E402

TAG = b"\xc1\x83\x2a\x9e"
GUID_RE = None


def _read_fs(b, pos):
    """读取一个 UE FString，返回 (新位置, 字符串)；失败返回 None。"""
    if pos + 4 > len(b):
        return None
    n = struct.unpack_from("<i", b, pos)[0]
    if n <= 0 or n > (1 << 20):
        return None
    if pos + 4 + n > len(b) or b[pos + 4 + n - 1] != 0:
        return None
    try:
        return pos + 4 + n, b[pos + 4:pos + 4 + n - 1].decode("ascii")
    except UnicodeDecodeError:
        return None


def ftexts_from_chunk(chunk_path):
    """从 raw Zen chunk 的导出数据里扫描 (GUID, 源串) 列表。"""
    import re
    global GUID_RE
    if GUID_RE is None:
        GUID_RE = re.compile(rb"\x21\x00\x00\x00([0-9A-F]{32})\x00")
    b = Path(chunk_path).read_bytes()
    h = struct.unpack_from("<i", b, 4)[0]
    payload = b[h:]
    exp = payload[:-4] if payload[-4:] == TAG else payload
    out = {}
    for m in GUID_RE.finditer(exp):
        r = _read_fs(exp, m.end())
        if r and r[1]:
            out[m.group(1).decode()] = r[1]
    return out


def build_protect_from_scan(args):
    """从扫描产物重建保护集：{guid: 英文原文}。"""
    protect = {}
    free = {x.strip() for x in (args.free or "").split(",") if x.strip()}

    def add(guid, src, asset=""):
        if not src:
            return
        if asset and any(a == f for a in free):
            return
        protect.setdefault(guid, src)

    # 1) 全库枚举显示名
    enum_all = json.loads(Path(args.enum_all).read_text(encoding="utf-8"))
    for path, hits in enum_all.items():
        asset = Path(path).stem
        for guid, src in hits:
            add(guid, src, asset)
    # 2) 环形菜单 DT_Menu
    for guid, src in ftexts_from_chunk(args.dt_menu).items():
        protect.setdefault(guid, src)
    # 3) 文本参与逻辑比较的资产内文本
    if args.scan_report:
        rep = json.loads(Path(args.scan_report).read_text(encoding="utf-8"))
        wanted = {k[-1] for k in rep.get("protect_keys", [])}
        if args.asset_ftexts and wanted:
            assets = json.loads(Path(args.asset_ftexts).read_text(encoding="utf-8"))
            for _path, info in assets.items():
                for guid, src in info.get("ftexts", []):
                    if guid in wanted and src:
                        protect.setdefault(guid, src)
    return protect


def main():
    ap = argparse.ArgumentParser(description="生成带保护清单的最终 UI locres")
    ap.add_argument("--fix1", required=True, help="上游全量 locres（如 data/Game.locres.fix1）")
    ap.add_argument("--protect", help="已整理的保护清单 JSON（data/protect_list.json，优先）")
    ap.add_argument("--enum-all", help="全库枚举扫描结果 enum_all.json")
    ap.add_argument("--dt-menu", help="DT_Menu 的 raw chunk")
    ap.add_argument("--scan-report", help="scan_text_logic.py 产出的 scan_report.json")
    ap.add_argument("--asset-ftexts", help="scan_text_logic.py 产出的 asset_ftexts.json")
    ap.add_argument("--free", default="", help="允许放开的显示型枚举资产名，逗号分隔")
    ap.add_argument("--out", required=True, help="输出 locres 路径")
    args = ap.parse_args()

    if args.protect:
        doc = json.loads(Path(args.protect).read_text(encoding="utf-8"))
        protect = {e["key"]: e["source"] for e in doc.get("entries", [])}
        print(f"[protect] 从 {args.protect} 载入 {len(protect)} 条保护键")
    else:
        if not (args.enum_all and args.dt_menu):
            ap.error("--protect 之外还需 --enum-all 与 --dt-menu（或至少这些扫描产物）")
        protect = build_protect_from_scan(args)
        print(f"[protect] 扫描产物重建保护集 {len(protect)} 条（--free={args.free or '无'}）")

    data = L.load(args.fix1)
    total = changed = 0
    for ns in data["namespaces"]:
        if ns.name != "":
            continue
        for e in ns.entries:
            total += 1
            src = protect.get(e.key)
            if src and src.strip() and e.value != src:
                e.value = src
                changed += 1
    blob = L.dumps(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    chk = L.loads(blob)
    print(f"[out] {out}  {len(blob):,} B  条目 {L.total_entries(chk)}  保护回英文 {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
