# -*- coding: utf-8 -*-
"""在本地游戏容器上原地打 DataTable 文本补丁（chunk 内替换 uexp + 更新 SerialSize）。

本脚本只处理 DataTable/文本类资产；蓝图资产没有可更新的 SerialSize 字段，任何写入都会导致游戏崩溃。

用法示例：
  python patch_containers.py --jobs ../data/dt_jobs.json --paks "<游戏>/Content/Paks" \
      --retoc retoc.exe --oodle oo2core_9_win64.dll --key <AES密钥hex> --out ./build

  # 确认无误后安装（会先自动备份原始容器）
  python patch_containers.py ... --out ./build --install

参数：
  --jobs    替换数据（本仓库 data/dt_jobs.json）
  --paks    游戏 Content/Paks 目录（用本机路径覆盖 jobs 内的容器路径）
  --retoc   retoc.exe 路径
  --oodle   oo2core_9_win64.dll 路径
  --key     容器 AES-256 密钥（hex）。本仓库不提供，请自行获取
  --out     输出目录（默认 ./build）
  --install 把结果复制回 Paks（先备份到 --backupdir）
  --dry-run 只统计将要替换的条目，不写文件
"""
import argparse, ctypes, json, os, shutil, struct, subprocess, sys, time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------- AES-256-ECB（bcrypt） ----------------
_ALG = _HK = None
def _init_aes(key):
    global _ALG, _HK
    bcrypt = ctypes.WinDLL("bcrypt.dll")
    bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.ULONG]
    bcrypt.BCryptSetProperty.restype = ctypes.c_long
    bcrypt.BCryptSetProperty.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG]
    bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p, wintypes.ULONG, ctypes.c_char_p, wintypes.ULONG, wintypes.ULONG]
    bcrypt.BCryptEncrypt.restype = ctypes.c_long
    bcrypt.BCryptEncrypt.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG, ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, ctypes.c_char_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), wintypes.ULONG]
    bcrypt.BCryptDecrypt.restype = ctypes.c_long
    bcrypt.BCryptDecrypt.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.ULONG, ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG, ctypes.c_char_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), wintypes.ULONG]
    alg = wintypes.HANDLE(); assert bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0) == 0
    mode = ctypes.create_unicode_buffer("ChainingModeECB")
    assert bcrypt.BCryptSetProperty(alg, "ChainingMode", ctypes.cast(mode, ctypes.c_void_p), ctypes.sizeof(mode), 0) == 0
    hk = wintypes.HANDLE()
    assert bcrypt.BCryptGenerateSymmetricKey(alg, ctypes.byref(hk), None, 0, key, len(key), 0) == 0
    _ALG, _HK = alg, hk
    return bcrypt

def aes_dec(bcrypt, d):
    n = len(d) // 16 * 16
    if not n: return d
    out = ctypes.create_string_buffer(n + 16); got = wintypes.ULONG()
    assert bcrypt.BCryptDecrypt(_HK, d[:n], n, None, None, 0, out, len(out), ctypes.byref(got), 0) == 0
    return out.raw[:got.value] + d[n:]

def aes_enc(bcrypt, d):
    n = len(d) // 16 * 16
    if not n: return d
    out = ctypes.create_string_buffer(n + 16); got = wintypes.ULONG()
    assert bcrypt.BCryptEncrypt(_HK, d[:n], n, None, None, 0, out, len(out), ctypes.byref(got), 0) == 0
    return out.raw[:got.value] + d[n:]

# ---------------- Oodle ----------------
class Oodle:
    def __init__(self, dll):
        self.oo = ctypes.CDLL(dll)
        self.oo.OodleLZ_Decompress.restype = ctypes.c_longlong
        self.oo.OodleLZ_Decompress.argtypes = [ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p, ctypes.c_longlong,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_longlong,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_longlong, ctypes.c_int]
        self.oo.OodleLZ_Compress.restype = ctypes.c_longlong
        self.oo.OodleLZ_Compress.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_longlong, ctypes.c_char_p,
            ctypes.c_int, ctypes.c_void_p, ctypes.c_longlong, ctypes.c_void_p, ctypes.c_longlong]
    def decomp(self, c, usize):
        out = ctypes.create_string_buffer(usize)
        n = self.oo.OodleLZ_Decompress(c, len(c), out, usize, 1, 0, 0, None, 0, None, None, None, 0, 3)
        if n <= 0: raise RuntimeError("oodle 解压失败")
        return out.raw[:n]
    def comp(self, data):
        out = ctypes.create_string_buffer(len(data) + 65536)
        n = self.oo.OodleLZ_Compress(8, data, len(data), out, 9, None, 0, None, 0)
        if n <= 0: raise RuntimeError("oodle 压缩失败")
        return out.raw[:n]

def find_block_off(toc, count):
    """启发式定位 block 表：offset 非降、csize/usize<=65536、method in {0,1}"""
    for off in range(144, max(145, len(toc) - count * 12 - 1)):
        ok, last = True, -1
        for i in range(count):
            raw = toc[off + i * 12: off + i * 12 + 12]
            o = int.from_bytes(raw[0:5], "little"); cs = int.from_bytes(raw[5:8], "little")
            us = int.from_bytes(raw[8:11], "little"); m = raw[11]
            if cs == 0 or cs > 65536 or us == 0 or us > 65536 or m not in (0, 1) or o < last:
                ok = False; break
            last = o
        if ok: return off
    return None

def enc_fstring(s):
    if all(ord(c) < 128 for c in s):
        b = s.encode("latin1") + b"\x00"; return struct.pack("<i", len(b)) + b
    b = s.encode("utf-16-le") + b"\x00\x00"; return struct.pack("<i", -(len(b) // 2)) + b

def main():
    ap = argparse.ArgumentParser(description="在本地游戏容器上原地打 DataTable 文本补丁")
    ap.add_argument("--jobs", required=True, help="替换数据 json（本仓库 data/dt_jobs.json）")
    ap.add_argument("--paks", required=True, help="游戏 Content/Paks 目录")
    ap.add_argument("--retoc", required=True, help="retoc.exe 路径")
    ap.add_argument("--oodle", required=True, help="oo2core_9_win64.dll 路径")
    ap.add_argument("--key", required=True, help="容器 AES 密钥（hex，64 字符）")
    ap.add_argument("--out", default="build", help="输出目录（默认 ./build）")
    ap.add_argument("--work", default=None, help="中间文件目录（默认 <out>/work）")
    ap.add_argument("--install", action="store_true", help="把结果复制回 Paks（自动备份）")
    ap.add_argument("--backupdir", default=None, help="备份目录（默认 <paks>/../_hans_backup_<时间戳>）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    a = ap.parse_args()

    key = bytes.fromhex(a.key)
    if len(key) != 32: sys.exit("--key 必须是 32 字节（64 个 hex 字符）")
    work = a.work or os.path.join(a.out, "work")
    os.makedirs(work, exist_ok=True); os.makedirs(a.out, exist_ok=True)

    bcrypt = _init_aes(key)
    oo = Oodle(a.oodle)
    job = json.load(open(a.jobs, encoding="utf-8"))

    results = {}
    for cname, spec in job["containers"].items():
        utoc_p = os.path.join(a.paks, "pakchunk%s-Windows.utoc" % cname)
        ucas_p = os.path.join(a.paks, "pakchunk%s-Windows.ucas" % cname)
        if not (os.path.exists(utoc_p) and os.path.exists(ucas_p)):
            print("[跳过] 找不到容器 pakchunk%s-Windows.utoc/.ucas" % cname); continue
        utoc = bytearray(open(utoc_p, "rb").read()); ucas = bytearray(open(ucas_p, "rb").read())
        count = struct.unpack_from("<I", utoc, 28)[0]
        boff = find_block_off(utoc, count)
        print("\n===== chunk %s =====\n  utoc %dB  ucas %.1fMB  block_count=%d  block_off=%s" % (cname, len(utoc), len(ucas)/1048576, count, boff))
        if boff is None:
            print("  !! block 表未定位 —— 该容器很可能**已经打过补丁**（改动的块被追加到文件尾，偏移不再单调）。")
            print("     请对**原始容器**运行：首次打补丁请先备份原包；已打过补丁请先从 _hans_backup_* 恢复。")
            continue
        blocks, stream = [], bytearray()
        for i in range(count):
            raw = utoc[boff + i*12: boff + (i+1)*12]
            off = int.from_bytes(raw[0:5], "little"); cs = int.from_bytes(raw[5:8], "little")
            us = int.from_bytes(raw[8:11], "little"); m = raw[11]
            rl = (cs + 15)//16*16
            seg = aes_dec(bcrypt, bytes(ucas[off:off+rl]))[:cs]
            data = oo.decomp(seg, us) if m == 1 else seg[:us]
            blocks.append({"idx": i, "off": off, "csize": cs, "usize": us, "start": len(stream)})
            stream += data
        orig = bytes(stream); new_stream = bytearray(orig)
        total = 0
        for asset in [x for x in job["assets"] if x["container"] == cname]:
            cp = os.path.join(work, cname + "__" + asset["name"] + ".chunk")
            if not os.path.exists(cp):
                subprocess.run([a.retoc, "-a", key.hex(), "get", utoc_p, asset["id"], cp], capture_output=True)
            if not os.path.exists(cp): print("  !! %s: 取资产失败" % asset["name"]); continue
            chunk = open(cp, "rb").read()
            uexp_off = struct.unpack_from("<i", chunk, 4)[0]
            uexp = chunk[uexp_off:]; applied, probs = 0, []
            for en, zh in asset["tr"].items():
                pa = struct.pack("<i", len(en)+1) + en.encode("latin1") + b"\x00"
                pu = struct.pack("<i", -(len(en)+1)) + en.encode("utf-16-le") + b"\x00\x00"
                na, nu = uexp.count(pa), uexp.count(pu)
                if na == 1 and nu == 0: uexp = uexp.replace(pa, enc_fstring(zh)); applied += 1
                elif na == 0 and nu == 1: uexp = uexp.replace(pu, enc_fstring(zh)); applied += 1
                elif na + nu == 0: probs.append(("未找到", en[:40]))
                else: probs.append(("重复%d" % (na+nu), en[:40]))
            total += applied
            if len(uexp) > len(chunk) - uexp_off: print("  !! %s: 新 uexp 更大，跳过" % asset["name"]); continue
            new_chunk = bytearray(chunk[:uexp_off]) + bytearray(uexp)
            old_ssz = struct.pack("<q", len(chunk) - uexp_off - 4)
            h = new_chunk.find(old_ssz)
            if h < 0: print("  !! %s: SerialSize 未找到，跳过" % asset["name"]); continue
            struct.pack_into("<q", new_chunk, h, len(uexp) - 4)
            if len(new_chunk) < len(chunk): new_chunk += chunk[len(new_chunk):]
            new_chunk = bytes(new_chunk[:len(chunk)])
            pos = orig.find(chunk)
            if pos < 0 or orig.count(chunk) != 1: print("  !! %s: chunk 在流中不唯一" % asset["name"]); continue
            new_stream[pos:pos+len(new_chunk)] = new_chunk
            print("  %-34s 替换 %3d 条  uexp %d→%d%s" % (asset["name"].split("__")[-1], applied, len(chunk)-uexp_off, len(uexp), ("  问题:" + str(probs)) if probs else ""))
        if a.dry_run:
            print("  [dry-run] 共替换 %d 条，未写文件" % total); continue
        inplace = appended = touched = 0
        for b in blocks:
            s0 = b["start"]; seg = bytes(new_stream[s0:s0+b["usize"]])
            if seg == orig[s0:s0+b["usize"]]: continue
            touched += 1
            c = oo.comp(seg); aligned = (len(c)+15)//16*16
            if len(c) <= b["csize"] and b["off"]+aligned <= len(ucas): p = b["off"]; inplace += 1
            else:
                p = (len(ucas)+15)//16*16
                if p > len(ucas): ucas += b"\x00"*(p-len(ucas))
                appended += 1
            if p+aligned > len(ucas): ucas += b"\x00"*(p+aligned-len(ucas))
            ucas[p:p+aligned] = aes_enc(bcrypt, c + b"\x00"*(aligned-len(c)))
            utoc[boff+b["idx"]*12: boff+(b["idx"]+1)*12] = (p.to_bytes(5,"little") + len(c).to_bytes(3,"little")
                + b["usize"].to_bytes(3,"little") + (1).to_bytes(1,"little"))
        print("  改动块 %d（原地 %d，追加 %d）  替换 %d 条" % (touched, inplace, appended, total))
        ot = os.path.join(a.out, "pakchunk%s-Windows.utoc" % cname)
        oc = os.path.join(a.out, "pakchunk%s-Windows.ucas" % cname)
        open(ot, "wb").write(bytes(utoc)); open(oc, "wb").write(bytes(ucas))
        results[cname] = (ot, oc, utoc_p, ucas_p)
        print("  已写出 %s / %s" % (ot, oc))

    if a.install and results:
        bdir = a.backupdir or os.path.join(os.path.dirname(os.path.abspath(a.paks)), "_hans_backup_" + time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(bdir, exist_ok=True)
        for cname, (ot, oc, utoc_p, ucas_p) in results.items():
            for src_path, dst_path in ((utoc_p, ot), (ucas_p, oc)):
                shutil.copy2(src_path, os.path.join(bdir, os.path.basename(src_path)))
                shutil.copy2(dst_path, src_path)
            print("已安装 pakchunk%s（原始备份在 %s）" % (cname, bdir))

if __name__ == "__main__":
    main()
