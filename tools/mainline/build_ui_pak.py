#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 汉化：把仓库 fix1 locres 注入本机 pakchunk0-Windows.pak（只改 .pak 一个文件）。

流程（与 carnal-instinct-hans 的路线 E 一致，适配本机 build 的差异）：
  1. 用 AES key 解包本机原版 pakchunk0-Windows.pak（只读源文件）
  2. 只把包内 Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres 换成 data/Game.locres.fix1
  3. 用本机原 pak 的参数重新打包：mount ../../../ / V11 / Oodle / seed 0x464517FC
  4. 四项复核：文件清单一致、除 locres 外逐字节相同、包内 locres SHA == fix1、repak info 参数一致

用法:
  python build_ui_pak.py                 # 构建 + 复核
  python build_ui_pak.py --keep-work     # 保留临时解包目录
"""
import argparse
import hashlib
import shutil
import struct
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:\AI项目\CarnalInstinct")
REPAK = BASE / "tools/repak/repak.exe"
KEY = (BASE / "notes/lead/forum-key.txt").read_text(encoding="utf-8").strip()
GAME_PAK = Path(r"E:\SteamLibrary\steamapps\common\CarnalInstinct\Carnal_Instinct_UE5\Content\Paks\pakchunk0-Windows.pak")
FIX1 = Path(r"E:\AI项目\carnal-instinct-hans\data\Game.locres.fix1")
FIX1_SHA = "85F28F91088C263675E6A23DE0CBB38E4749FE86E460D1552349590B0F522CDC"

OUT = BASE / "build/ui-locres"
WORK = OUT / "work"
TMP_ORIG = WORK / "unpack_orig"
TMP_NEW = WORK / "unpack_new"
NEW_PAK = OUT / "pakchunk0-Windows.hans.pak"

INNER_LOCRES = "Carnal_Instinct_UE5/Content/Localization/Game/en/Game.locres"
MOUNT = "../../../"
VERSION = "V11"
COMPRESSION = "Oodle"
SEED = 0x464517FC  # 本机 pakchunk0 的 path hash seed（repak info 显示 464517FC）


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return r


def rel_list(root: Path):
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--locres", default=str(FIX1), help="要注入的 locres 文件（默认 fix1）")
    ap.add_argument("--out-pak", default=str(NEW_PAK), help="输出 pak 路径")
    args = ap.parse_args()
    locres = Path(args.locres)
    out_pak = Path(args.out_pak)
    locres_sha = sha256(locres)
    if locres == FIX1 and locres_sha != FIX1_SHA:
        sys.exit(f"[FAIL] fix1 locres SHA256 不符: {locres_sha}")
    if not GAME_PAK.exists():
        sys.exit(f"[FAIL] 找不到游戏 pak: {GAME_PAK}")
    print(f"[源] 游戏 pak : {GAME_PAK}")
    print(f"[源] 原 pak SHA256: {sha256(GAME_PAK)}")
    print(f"[源] 注入 locres : {locres}  {locres.stat().st_size:,} 字节  SHA256 {locres_sha}")
    print(f"[参数] mount={MOUNT} version={VERSION} compression={COMPRESSION} seed=0x{SEED:08X} ({SEED})")

    OUT.mkdir(parents=True, exist_ok=True)
    for d in (TMP_ORIG, TMP_NEW):
        if d.exists():
            shutil.rmtree(d)
    WORK.mkdir(parents=True, exist_ok=True)
    NEW_PAK.unlink(missing_ok=True)
    out_pak.parent.mkdir(parents=True, exist_ok=True)
    out_pak.unlink(missing_ok=True)


    # 1) 解包原 pak
    print("\n[1/4] 解包原 pak ...")
    r = run([REPAK, "-a", KEY, "unpack", GAME_PAK, "--output", TMP_ORIG, "-q"])
    if r.returncode != 0:
        print("stdout:", (r.stdout or "")[-800:])
        print("stderr:", (r.stderr or "")[-1200:])
        sys.exit("[FAIL] repak unpack 失败")
    files_orig = rel_list(TMP_ORIG)
    print(f"      解包 {len(files_orig)} 个文件")
    inner = TMP_ORIG / INNER_LOCRES
    if not inner.exists():
        # 兼容路径分隔符/前缀差异
        cand = [p for p in TMP_ORIG.rglob("Game.locres") if "Localization" in str(p)]
        if not cand:
            sys.exit("[FAIL] 解包树里找不到 Game.locres")
        inner = cand[0]
    rel_inner = str(inner.relative_to(TMP_ORIG)).replace("\\", "/")
    print(f"      包内 locres: {rel_inner}  {inner.stat().st_size:,} 字节  SHA256 {sha256(inner)}")
    hash_orig = {f: sha256(TMP_ORIG / f) for f in files_orig}

    # 2) 替换 locres
    print("\n[2/4] 替换包内 locres ...")
    shutil.copyfile(locres, inner)
    got = sha256(inner)
    if got != locres_sha:
        sys.exit(f"[FAIL] 替换后包内 locres 哈希不符: {got}")
    print(f"      已替换（其余 {len(files_orig)-1} 个文件未动）")

    # 3) 重打包
    print("\n[3/4] repak 重打包 ...")
    r = run([REPAK, "pack", TMP_ORIG, out_pak, "-m", MOUNT, "--version", VERSION,
             "--compression", COMPRESSION, "-p", str(SEED), "-q"])
    if r.returncode != 0:
        print("stdout:", (r.stdout or "")[-800:])
        print("stderr:", (r.stderr or "")[-1200:])
        sys.exit("[FAIL] repak pack 失败")
    print(f"      新 pak: {out_pak}  {out_pak.stat().st_size:,} 字节  SHA256 {sha256(out_pak)}")

    # 4) 复核
    print("\n[4/4] 覆盖前四项复核 ...")
    r = run([REPAK, "unpack", out_pak, "--output", TMP_NEW, "-q"])
    if r.returncode != 0:
        sys.exit(f"[FAIL] 新 pak 解包失败: {(r.stderr or '')[-800:]}")
    files_new = rel_list(TMP_NEW)
    ok = True
    if files_new != files_orig:
        only_o = sorted(set(files_orig) - set(files_new))
        only_n = sorted(set(files_new) - set(files_orig))
        print(f"  [X] 复核1 文件清单不一致: 缺 {only_o[:5]} 多 {only_n[:5]}")
        ok = False
    else:
        print(f"  [OK] 复核1 文件清单一致（{len(files_new)} 个）")

    same = 0
    bad = []
    for f in files_new:
        if f == rel_inner:
            continue
        if sha256(TMP_NEW / f) != hash_orig[f]:
            bad.append(f)
        else:
            same += 1
    if bad:
        print(f"  [X] 复核2 非 locres 文件被改动 {len(bad)} 个: {bad[:5]}")
        ok = False
    else:
        print(f"  [OK] 复核2 除 locres 外 {same} 个文件逐字节相同")

    loc = TMP_NEW / INNER_LOCRES
    if not loc.exists():
        cand = [p for p in TMP_NEW.rglob("Game.locres") if "Localization" in str(p)]
        loc = cand[0] if cand else None
    loc_sha = sha256(loc) if loc else "MISSING"
    if loc_sha != locres_sha:
        print(f"  [X] 复核3 包内 locres SHA256 不符: {loc_sha}")
        ok = False
    else:
        print(f"  [OK] 复核3 包内 locres SHA256 == 注入数据")

    info = run([REPAK, "info", out_pak])
    info_txt = (info.stdout or "") + (info.stderr or "")
    checks = {"版本 V11": "Fnv64BugFix" in info_txt or "V11" in info_txt,
              "压缩 Oodle": "Oodle" in info_txt,
              "seed": "464517FC" in info_txt.upper()}
    for k, v in checks.items():
        print(f"  [{'OK' if v else 'X'}] 复核4 repak info: {k}")
        ok = ok and v
    print("\n--- repak info 新 pak ---")
    for line in info_txt.splitlines():
        if line.strip():
            print("   ", line.strip())

    if not args.keep_work:
        shutil.rmtree(WORK)
        print("\n[清理] 已删除临时解包目录")
    print("\n" + ("[完成] 全部复核通过，可部署。" if ok else "[失败] 复核未通过，不要部署。"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
