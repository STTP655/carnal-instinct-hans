#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全版保真构建器：raw Zen chunk 保真改写 + retoc pack-raw 成覆盖容器。

与旧 build_zenmod.py 的区别（这正是此前崩溃/乱码的三个根因）：
  1. 译文改用 translation/zh_safe.json（249 资产 / 9,092 条）——
     已剔除「二进制被误判成 FString」的条目和内部查找键；旧版用全量 zh.json 会写坏结构。
  2. 所有中文强制写 UTF-16（负长度前缀）——旧版优先 CP936/ANSI，引擎按 UTF-8 解，必乱码。
  3. 不再走 retoc to-zen 重新生成 Zen 包（那条路产出的包不合法，Bad export index）；
     这里保留原始 Zen 头部全部字节，只改「导出数据长度」这一个 int32。

原理（已实测）：
  Zen chunk = [头部 H 字节] + [导出数据] + [4B PACKAGE_FILE_TAG]
  - H = chunk[4:8] 的 int32
  - 头部里恰好有 1 个 4 字节对齐的 int32 == len(导出数据)，就是长度字段
  - 导出数据内部是顺序记录（固定长度行头 + 32 位 hex ID + 文本 FString），没有偏移依赖

用法:
  python build_zenmod_safe.py                # 构建 + 打包 + 离线自检
  python build_zenmod_safe.py --no-pack      # 只生成 tree，不打包
"""
import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:\AI项目\CarnalInstinct")
RETOC = BASE / "tools/retoc/retoc.exe"
WORK = BASE / "build/zenmod-work"
OUTDIR = BASE / "build/zzz-safe-utf16"
TREE = OUTDIR / "tree"
VER = OUTDIR / "verify-unpack"
UTOC = OUTDIR / "zzz_CarnalInstinct_CN_P.utoc"

TAG = b"\xc1\x83\x2a\x9e"
PREFIX = "../../../Carnal_Instinct_UE5/Content/"
MSL_REL = "MSL_Toolkit/localization_system/language_data/en/"
MAXLEN = 1 << 20


# ---------- FString ----------
def read_fstring(b: bytes, pos: int):
    """返回 (end, text, kind) 或 None。比 mslpatch 更严格：拒绝空串/控制字符。"""
    if pos + 4 > len(b):
        return None
    n = struct.unpack_from("<i", b, pos)[0]
    if n == 0:
        return None
    if n > 0:
        if n > MAXLEN or pos + 4 + n > len(b):
            return None
        raw = b[pos + 4:pos + 4 + n]
        if raw[-1] != 0 or any(c == 0 for c in raw[:-1]):
            return None
        body = raw[:-1]
        if not body or not all((0x20 <= c <= 0x7E) or c >= 0x80 for c in body):
            return None
        try:
            text = body.decode("cp936")
        except UnicodeDecodeError:
            return None
        if any(ord(ch) < 0x20 for ch in text):
            return None
        return pos + 4 + n, text, "ansi"
    units = -n
    if units > MAXLEN or pos + 4 + units * 2 > len(b):
        return None
    raw = b[pos + 4:pos + 4 + units * 2]
    if raw[-2:] != b"\x00\x00" or len(raw) % 2:
        return None
    try:
        text = raw[:-2].decode("utf-16-le")
    except UnicodeDecodeError:
        return None
    if not text or any(ord(c) < 0x20 for c in text):
        return None
    return pos + 4 + units * 2, text, "utf16"


def iter_fstrings(b: bytes):
    pos = 0
    while pos < len(b) - 4:
        r = read_fstring(b, pos)
        if r:
            end, text, kind = r
            yield pos, end, kind, text
            pos = end
        else:
            pos += 1


def encode_utf16(text: str) -> bytes:
    """FString 序列化：负长度前缀 + UTF-16LE + NUL。长度 = 码元数+1。"""
    raw = text.encode("utf-16-le")
    units = len(raw) // 2
    return struct.pack("<i", -(units + 1)) + raw + b"\x00\x00"


def has_cjk(text: str) -> bool:
    return any(ord(c) > 0x2FF for c in text)


# ---------- 构建 ----------
def patch_export(export: bytes, translations: dict) -> tuple:
    spans = {off: (end, text, kind) for off, end, kind, text in iter_fstrings(export)}
    pieces = []
    cursor = 0
    applied = 0
    errors = []
    for off in sorted(translations):
        dst = translations[off]
        if not isinstance(dst, str) or not dst.strip():
            errors.append((off, "译文为空"))
            continue
        if off not in spans:
            errors.append((off, "该偏移不是可识别的 FString"))
            continue
        end, _src, _kind = spans[off]
        pieces.append(export[cursor:off])
        pieces.append(encode_utf16(dst))
        cursor = end
        applied += 1
    pieces.append(export[cursor:])
    return b"".join(pieces), applied, errors


def collect_sources() -> tuple:
    """返回 (path -> 原始 chunk 路径, version, mount_point)。"""
    paths = {}
    version = mount = None
    for name in ("pakchunk1013-Windows", "pakchunk1014-Windows"):
        d = WORK / name
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        version = version or man.get("version")
        mount = mount or man.get("mount_point")
        for cid, path in man["chunk_paths"].items():
            paths[path] = d / "chunks" / cid
    return paths, version, mount


def build() -> dict:
    zh = json.loads((BASE / "translation/zh_safe.json").read_text(encoding="utf-8"))
    sources, version, mount = collect_sources()
    if TREE.exists():
        shutil.rmtree(TREE)
    (TREE / "chunks").mkdir(parents=True)

    newmap = {}
    applied_total = expected_total = 0
    built = 0
    problems = []
    per_asset = []

    for key, mapping in zh.items():
        if key.startswith("_"):
            continue
        path = PREFIX + MSL_REL + key + ".uasset"
        src = sources.get(path)
        if src is None:
            problems.append((key, "原始 chunk 未找到"))
            continue
        raw = src.read_bytes()
        if len(raw) < 16 or raw[-4:] != TAG:
            problems.append((key, "chunk 结构异常（长度/TAG）"))
            continue
        h = struct.unpack_from("<i", raw, 4)[0]
        if not (0 < h < len(raw) - 8):
            problems.append((key, f"头部长度不合理: {h}"))
            continue
        export = raw[h:-4]
        hits = [i for i in range(0, h - 3, 4) if struct.unpack_from("<i", raw, i)[0] == len(export)]
        if len(hits) != 1:
            problems.append((key, f"头部长度字段命中 {len(hits)} 处（应为 1）"))
            continue
        translations = {int(k): v for k, v in mapping.items()}
        new_export, applied, errors = patch_export(export, translations)
        if errors:
            problems.append((key, f"{len(errors)} 条失败，例: {errors[:3]}"))
        if applied == 0:
            problems.append((key, "0 条写入，跳过"))
            continue
        out = bytearray(raw[:h])
        struct.pack_into("<i", out, hits[0], len(new_export))
        out += new_export + TAG
        cid = src.name
        (TREE / "chunks" / cid).write_bytes(bytes(out))
        newmap[cid] = path
        built += 1
        applied_total += applied
        expected_total += len(translations)
        per_asset.append((key, applied, len(translations), len(export), len(new_export)))

    (TREE / "manifest.json").write_text(json.dumps(
        {"chunk_paths": newmap, "version": version, "mount_point": mount},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[构建] 资产 {built}，写入中文 {applied_total}/{expected_total} 条")
    delta = sum(a[4] - a[3] for a in per_asset)
    print(f"[构建] 导出数据总变化 {delta:+d} 字节；问题 {len(problems)} 条")
    for p, why in problems[:20]:
        print(f"   ! {p}: {why}")
    return {"built": built, "applied": applied_total, "expected": expected_total,
            "problems": problems, "newmap": newmap}


def pack_and_verify(newmap: dict) -> int:
    for suf in ("-Windows.utoc", "-Windows.ucas"):
        pass
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for f in (UTOC, UTOC.with_suffix(".ucas"), UTOC.with_suffix(".pak")):
        if f.exists():
            f.unlink()
    print(f"[pack-raw] {TREE} -> {UTOC.name}")
    r = subprocess.run([str(RETOC), "pack-raw", str(TREE), str(UTOC)],
                       capture_output=True, text=True)
    print((r.stdout or "").strip()[-300:])
    if r.returncode != 0:
        print((r.stderr or "")[-1200:])
        return 1
    for f in sorted(OUTDIR.glob("zzz_CarnalInstinct_CN_P*")):
        print(f"  {f.name}  {f.stat().st_size/1024:.1f} KB")

    # 回读验证
    if VER.exists():
        shutil.rmtree(VER)
    r = subprocess.run([str(RETOC), "unpack-raw", str(UTOC), str(VER)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[verify] unpack-raw 失败:", (r.stderr or "")[-800:])
        return 1
    man = json.loads((VER / "manifest.json").read_text(encoding="utf-8"))
    sources, _v, _m = collect_sources()

    bad = 0
    zh_total = 0
    checked = 0
    for cid, path in man["chunk_paths"].items():
        if path not in sources:
            print(f"   ! 回读出现未知路径: {path}")
            bad += 1
            continue
        a = sources[path].read_bytes()
        b = (VER / "chunks" / cid).read_bytes()
        ha = struct.unpack_from("<i", a, 4)[0]
        hb = struct.unpack_from("<i", b, 4)[0]
        ok = ha == hb
        if ok:
            diff = [i for i in range(ha) if a[i] != b[i]]
            aligned = sorted({i // 4 for i in diff})
            ok = len(aligned) <= 1
            if ok and aligned:
                off = aligned[0] * 4
                new_len = struct.unpack_from("<i", b, off)[0]
                ok = new_len == len(b[hb:-4])
        if not ok:
            bad += 1
            print(f"   ! 头部不一致: {path}")
            continue
        exp = b[hb:-4]
        cnt = sum(1 for _off, _e, kind, t in iter_fstrings(exp) if kind == "utf16" and has_cjk(t))
        zh_total += cnt
        checked += 1
        if man["chunk_paths"][cid] != path:
            bad += 1

    print(f"[verify] 回读 {checked} 个 chunk，头部保真失败 {bad} 个；UTF-16 中文串 {zh_total} 条")
    # chunk ID 与原包一致
    hit = sum(1 for cid in man["chunk_paths"] if cid in newmap)
    print(f"[verify] chunk ID 与原包一致: {hit}/{len(newmap)}")
    # retoc verify（未加密容器）
    r = subprocess.run([str(RETOC), "verify", str(UTOC)], capture_output=True, text=True)
    print(f"[verify] retoc verify rc={r.returncode}: {((r.stdout or '') + (r.stderr or '')).strip()[-300:]}")
    return 0 if bad == 0 and hit == len(newmap) else 1


# ---------- 全量替换容器（含原 ContainerHeader，可直接替换原 pakchunk1013） ----------
ORIG_1013 = WORK / "pakchunk1013-Windows"
FULL_OUT = OUTDIR / "full"
BASE_UTOC = BASE / "backup/containers-orig/pakchunk1013-Windows.utoc"
ORIG_CONTAINER_ID = 0xF7353BD047C79EB2  # 原 pakchunk1013 的 container_id（ContainerHeader chunk id 内嵌此值）


def collect_sources_tagged() -> dict:
    out = {}
    for name in ("pakchunk1013-Windows", "pakchunk1014-Windows"):
        d = WORK / name
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        for cid, path in man["chunk_paths"].items():
            out[path] = (name, d / "chunks" / cid)
    return out


def split_chunk(raw: bytes):
    if len(raw) < 16 or raw[-4:] != TAG:
        return None, "chunk 结构异常（长度/TAG）"
    h = struct.unpack_from("<i", raw, 4)[0]
    if not (0 < h < len(raw) - 8):
        return None, f"头部长度不合理: {h}"
    export = raw[h:-4]
    hits = [i for i in range(0, h - 3, 4) if struct.unpack_from("<i", raw, i)[0] == len(export)]
    if len(hits) != 1:
        return None, f"头部长度字段命中 {len(hits)} 处（应为 1）"
    return (h, hits[0], export), None


def build_full_1013() -> tuple:
    zh = json.loads((BASE / "translation/zh_safe.json").read_text(encoding="utf-8"))
    sources = collect_sources_tagged()
    d = ORIG_1013
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    tree = FULL_OUT / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    (tree / "chunks").mkdir(parents=True)

    copied = 0
    for f in (d / "chunks").iterdir():
        if f.is_file():
            shutil.copyfile(f, tree / "chunks" / f.name)
            copied += 1

    patched = applied = expected = 0
    problems = []
    patched_ids = set()
    for key, mapping in zh.items():
        if key.startswith("_"):
            continue
        path = PREFIX + MSL_REL + key + ".uasset"
        hit = sources.get(path)
        if hit is None:
            problems.append((key, "原始 chunk 未找到"))
            continue
        name, rawpath = hit
        if name != "pakchunk1013-Windows":
            problems.append((key, f"不在 1013（{name}），本步跳过"))
            continue
        parts, why = split_chunk(rawpath.read_bytes())
        if parts is None:
            problems.append((key, why))
            continue
        h, size_off, export = parts
        translations = {int(k): v for k, v in mapping.items()}
        new_export, n, errors = patch_export(export, translations)
        if errors:
            problems.append((key, f"{len(errors)} 条失败: {errors[:3]}"))
        if n == 0:
            problems.append((key, "0 条写入，跳过"))
            continue
        raw = rawpath.read_bytes()
        out = bytearray(raw[:h])
        struct.pack_into("<i", out, size_off, len(new_export))
        out += new_export + TAG
        cid = rawpath.name
        (tree / "chunks" / cid).write_bytes(bytes(out))
        patched_ids.add(cid)
        patched += 1
        applied += n
        expected += len(translations)

    (tree / "manifest.json").write_text(json.dumps(
        {"chunk_paths": man["chunk_paths"], "version": man["version"], "mount_point": man["mount_point"]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[full] 原始 chunk 复制 {copied}，改写 {patched} 个资产，写入中文 {applied}/{expected}，问题 {len(problems)}")
    for p, why in problems[:20]:
        print(f"   ! {p}: {why}")
    return patched_ids, applied, problems


def pack_full_and_verify(patched_ids: set) -> int:
    FULL_OUT.mkdir(parents=True, exist_ok=True)
    utoc = FULL_OUT / "pakchunk1013-Windows.utoc"
    for f in (utoc, utoc.with_suffix(".ucas")):
        if f.exists():
            f.unlink()
    r = subprocess.run([str(RETOC), "pack-raw", str(FULL_OUT / "tree"), str(utoc)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[full] pack-raw 失败:", (r.stderr or "")[-1200:])
        return 1

    # 把容器 container_id 改回原容器的值：ContainerHeader chunk id 内嵌的就是它，
    # 引擎按 container_id 派生 ContainerHeader chunk id，两者必须一致。
    orig = BASE_UTOC.read_bytes()
    orig_id = struct.unpack_from("<Q", orig, 56)[0]
    if orig_id != ORIG_CONTAINER_ID:
        print(f"[full] 警告: 备份容器 container_id=0x{orig_id:016x}，与预期 0x{ORIG_CONTAINER_ID:016x} 不同")
    b = bytearray(utoc.read_bytes())
    struct.pack_into("<Q", b, 56, orig_id)
    utoc.write_bytes(bytes(b))
    for f in sorted(FULL_OUT.glob("pakchunk1013-Windows*")):
        print(f"  {f.name}  {f.stat().st_size/1024:.1f} KB")

    r = subprocess.run([str(RETOC), "info", str(utoc)], capture_output=True, text=True)
    print("[info]")
    print((r.stdout or r.stderr or "").strip())

    ver = FULL_OUT / "verify-unpack"
    if ver.exists():
        shutil.rmtree(ver)
    r = subprocess.run([str(RETOC), "unpack-raw", str(utoc), str(ver)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[full] unpack-raw 失败:", (r.stderr or "")[-800:])
        return 1
    man = json.loads((ver / "manifest.json").read_text(encoding="utf-8"))
    orig_chunks = {p.name: p for p in (ORIG_1013 / "chunks").iterdir() if p.is_file()}
    bad = 0
    zh_total = 0
    checked = 0
    for f in (ver / "chunks").iterdir():
        cid = f.name
        if cid not in orig_chunks:
            bad += 1
            continue
        a = orig_chunks[cid].read_bytes()
        b = f.read_bytes()
        checked += 1
        if cid in patched_ids:
            ha = struct.unpack_from("<i", a, 4)[0]
            hb = struct.unpack_from("<i", b, 4)[0]
            ok = ha == hb
            if ok:
                diff = [i for i in range(ha) if a[i] != b[i]]
                ok = len({i // 4 for i in diff}) <= 1
            if not ok:
                bad += 1
                print(f"   ! 头部不一致: {cid}")
                continue
            exp = b[hb:-4]
            zh_total += sum(1 for _o, _e, k, t in iter_fstrings(exp) if k == "utf16" and has_cjk(t))
        else:
            if a != b:
                bad += 1
                print(f"   ! 未改写 chunk 不一致: {cid}")
    print(f"[full-verify] chunk 文件 {checked}（应为 293），异常 {bad}，中文串 {zh_total}")
    r = subprocess.run([str(RETOC), "verify", str(utoc)], capture_output=True, text=True)
    print(f"[full-verify] retoc verify rc={r.returncode}: {((r.stdout or '') + (r.stderr or '')).strip()[-200:]}")
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pack", action="store_true")
    ap.add_argument("--full-1013", action="store_true", help="构建可替换原 pakchunk1013 的完整容器")
    args = ap.parse_args()
    if args.full_1013:
        patched_ids, _applied, _problems = build_full_1013()
        if args.no_pack:
            return 0
        return pack_full_and_verify(patched_ids)
    info = build()
    if args.no_pack:
        print(f"[tree] {TREE}")
        return 0
    return pack_and_verify(info["newmap"])


if __name__ == "__main__":
    sys.exit(main())
