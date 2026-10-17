#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""枚举识别：找出全库所有 UserDefinedEnum 资产，导出其显示名。

为什么需要：UE 的枚举显示名（E_Menus.Main、E_InputBufferKey.LightAttack、
E_CombatType.Melee……）会被游戏代码反读出来当逻辑键。把 locres 里这些键翻成
中文会导致功能异常（环形菜单失效、普通攻击失效等），因此必须保持英文。

识别方式：遍历 raw chunk 解包目录（retoc unpack-raw 产物）的 manifest，
按路径模式匹配枚举资产：
  /Enums/  /Enumerations/  /09_enums/  /enum/  （大小写不敏感）
  文件名 E_*.uasset 或 enum_*.uasset
注意：**不能只匹配 /Enums/**——实测会漏掉 /Enumerations/、/09_enums/ 等目录下的
枚举（本项目曾因此漏掉 108 个枚举，导致战斗枚举被翻译、普通攻击失效）。

用法：
  python protect_all_enums.py --scan-dir <asset-scan 目录> --out-json enum_all.json
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

TAG = b"\xc1\x83\x2a\x9e"
GUID_RE = re.compile(rb"\x21\x00\x00\x00([0-9A-F]{32})\x00")
MODULE_HINT = b"UserDefinedEnum"


def _read_fs(b, pos):
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


def is_enum_path(path):
    low = path.lower()
    if any(seg in low for seg in ("/enums/", "/enumerations/", "/09_enums/", "/enum/", "/enums")):
        return True
    name = low.rsplit("/", 1)[-1]
    return bool(re.match(r"^(e_[a-z0-9_]+|enum[a-z0-9_]+)\.uasset$", name))


def scan(scan_dir):
    root = Path(scan_dir)
    enums = {}
    for cdir in sorted(p for p in root.iterdir() if p.is_dir()):
        man = cdir / "manifest.json"
        if not man.exists():
            continue
        data = json.loads(man.read_text(encoding="utf-8"))
        chunks = cdir / "chunks"
        for cid, path in data["chunk_paths"].items():
            if not is_enum_path(path):
                continue
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
            payload = b[h:]
            exp = payload[:-4] if payload[-4:] == TAG else payload
            hits = []
            for m in GUID_RE.finditer(exp):
                r = _read_fs(exp, m.end())
                if r and r[1]:
                    hits.append([m.group(1).decode(), r[1]])
            if hits:
                enums[path] = hits
    return enums


def main():
    ap = argparse.ArgumentParser(description="识别全库枚举资产并导出显示名")
    ap.add_argument("--scan-dir", required=True,
                    help="retoc unpack-raw 产出的目录（内含 <container>/manifest.json 与 chunks/）")
    ap.add_argument("--out-json", required=True, help="输出 enum_all.json")
    args = ap.parse_args()
    enums = scan(args.scan_dir)
    total = sum(len(v) for v in enums.values())
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(enums, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[enum] 识别枚举资产 {len(enums)} 个，显示名 {total} 条 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
