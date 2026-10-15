# -*- coding: utf-8 -*-
"""locres 读写库（纯 Python，无第三方依赖）。

格式依据：UE 的 FTextLocalizationResource（见 TextLocalizationResourceVersion.h），
实现与 akintos/UnrealLocres v1.1.0 的 LocresLib 逐行对齐，便于交叉验证：

  magic[16] = 0E 14 74 75 67 4A 03 FC 4A 15 90 9D C3 37 7F 1B
  u8  version            (0=Legacy 1=Compact 2=Optimized 3=Optimized_CityHash64_UTF16)
  --- version >= 1 ---
  i64 localizedStringArrayOffset     (指向 stringTable)
  --- version >= 2 ---
  i32 localizedStringEntryCount      (= 全部条目数，含重复 value)
  i32 namespaceCount
  for each namespace:
      --- version >= 2 --- u32 namespaceKeyHash (v3: CityHash64_utf16->u32; v2: CRC32)
      UnrealString namespaceKey
      i32 keyCount
      for each key:
          --- version >= 2 --- u32 stringKeyHash
          UnrealString key
          u32 sourceStringHash           (v3: Crc.StrCrc32(SourceString))
          --- version >= 1 --- i32 stringTableIndex
          --- version == 0 --- UnrealString localizedString
  i32 stringTableCount
  for each stringTable entry:
      UnrealString text
      --- version >= 2 --- i32 refCount

UnrealString = i32 len + bytes；len > 0 为 ASCII（字节数含结尾 NUL），len < 0 为
UTF-16LE（码元数含结尾 NUL，字节数 = -len*2），len == 0 为空串。
"""

import struct
import sys

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF

LOCRES_MAGIC = bytes([0x0E, 0x14, 0x74, 0x75, 0x67, 0x4A, 0x03, 0xFC,
                      0x4A, 0x15, 0x90, 0x9D, 0xC3, 0x37, 0x7F, 0x1B])

V_LEGACY = 0
V_COMPACT = 1
V_OPTIMIZED = 2
V_OPTIMIZED_CITYHASH = 3


# --------------------------------------------------------------------------
# CRC32（UE FCrc::StrCrc32：逐字符取 4 字节，高 2 字节为 0）
# --------------------------------------------------------------------------
def _make_crc_table():
    tbl = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if (c & 1) else 0)
        tbl.append(c & M32)
    return tbl


_CRC_TABLE = _make_crc_table()


def str_crc32(value, crc=0):
    c = (~crc) & M32
    for ch in value:
        o = ord(ch)
        for shift in (0, 8, 16, 24):
            byte = (o >> shift) & 0xFF
            c = (c >> 8) ^ _CRC_TABLE[(c ^ byte) & 0xFF]
    return (~c) & M32


# --------------------------------------------------------------------------
# CityHash64（Atvaark 的 CityHash 1.0.3 C# 移植版，逐行对齐）
# --------------------------------------------------------------------------
_K0 = 0xC3A5C85C97CB3127
_K1 = 0xB492B66FBE98F273
_K2 = 0x9AE16A3B2F90404F
_K3 = 0xC949D7C7509E6557


def _fetch64(b, i):
    return struct.unpack_from("<Q", b, i)[0]


def _fetch32(b, i):
    return struct.unpack_from("<I", b, i)[0]


def _rotate(v, s):
    return v if s == 0 else (((v >> s) | (v << (64 - s))) & M64)


def _shiftmix(v):
    return (v ^ (v >> 47)) & M64


def _byteswap64(x):
    return int.from_bytes(x.to_bytes(8, "little"), "big")


def _hash128to64(low, high):
    k_mul = 0x9DDFEA08EB382D69
    a = ((low ^ high) * k_mul) & M64
    a ^= (a >> 47)
    b = ((high ^ a) * k_mul) & M64
    b ^= (b >> 47)
    b = (b * k_mul) & M64
    return b


def _hashlen16(u, v):
    return _hash128to64(u, v)


def _hashlen16_mul(u, v, mul):
    a = ((u ^ v) * mul) & M64
    a ^= (a >> 47)
    b = ((v ^ a) * mul) & M64
    b ^= (b >> 47)
    b = (b * mul) & M64
    return b


def _hashlen0to16(s, off=0):
    ln = len(s) - off
    if ln >= 8:
        mul = (_K2 + ln * 2) & M64
        a = (_fetch64(s, off) + _K2) & M64
        b = _fetch64(s, off + ln - 8)
        c = (_rotate(b, 37) * mul + a) & M64
        d = ((_rotate(a, 25) + b) * mul) & M64
        return _hashlen16_mul(c, d, mul)
    if ln >= 4:
        mul = (_K2 + ln * 2) & M64
        a = _fetch32(s, off)
        return _hashlen16_mul((ln + (a << 3)) & M64, _fetch32(s, off + ln - 4), mul)
    if ln > 0:
        a = s[off]
        b = s[off + (ln >> 1)]
        c = s[off + ln - 1]
        y = (a + (b << 8)) & M32
        z = (ln + (c << 2)) & M32
        return (_shiftmix((y * _K2 ^ z * _K0) & M64) * _K2) & M64
    return _K2


def _hashlen17to32(s):
    ln = len(s)
    mul = (_K2 + ln * 2) & M64
    a = (_fetch64(s, 0) * _K1) & M64
    b = _fetch64(s, 8)
    c = (_fetch64(s, ln - 8) * mul) & M64
    d = (_fetch64(s, ln - 16) * _K2) & M64
    return _hashlen16_mul(
        (_rotate((a + b) & M64, 43) + _rotate(c, 30) + d) & M64,
        (a + _rotate((b + _K2) & M64, 18) + c) & M64, mul)


def _weakhash32(w, x, y, z, a, b):
    a = (a + w) & M64
    b = _rotate((b + a + z) & M64, 21)
    c = a
    a = (a + x) & M64
    a = (a + y) & M64
    b = (b + _rotate(a, 44)) & M64
    return ((a + z) & M64, (b + c) & M64)


def _weak(s, off, a, b):
    return _weakhash32(_fetch64(s, off), _fetch64(s, off + 8),
                       _fetch64(s, off + 16), _fetch64(s, off + 24), a, b)


def _hashlen33to64(s):
    ln = len(s)
    mul = (_K2 + ln * 2) & M64
    a = (_fetch64(s, 0) * _K2) & M64
    b = _fetch64(s, 8)
    c = _fetch64(s, ln - 24)
    d = _fetch64(s, ln - 32)
    e = (_fetch64(s, 16) * _K2) & M64
    f = (_fetch64(s, 24) * 9) & M64
    g = _fetch64(s, ln - 8)
    h = (_fetch64(s, ln - 16) * mul) & M64
    u = (_rotate((a + g) & M64, 43) + ((_rotate(b, 30) + c) & M64) * 9) & M64
    v = ((((a + g) & M64) ^ d) + f + 1) & M64
    w = (_byteswap64(((u + v) & M64) * mul & M64) + h) & M64
    x = (_rotate((e + f) & M64, 42) + c) & M64
    y = ((_byteswap64((((v + w) & M64) * mul) & M64) + g) & M64) * mul & M64
    z = (e + f + c) & M64
    a = (_byteswap64((((x + z) & M64) * mul + y) & M64) + b) & M64
    b = (_shiftmix((((z + a) & M64) * mul + d + h) & M64) * mul) & M64
    return (b + x) & M64


def cityhash64(s):
    ln = len(s)
    if ln <= 32:
        return _hashlen0to16(s, 0) if ln <= 16 else _hashlen17to32(s)
    if ln <= 64:
        return _hashlen33to64(s)
    x = _fetch64(s, ln - 40)
    y = (_fetch64(s, ln - 16) + _fetch64(s, ln - 56)) & M64
    z = _hashlen16((_fetch64(s, ln - 48) + ln) & M64, _fetch64(s, ln - 24))
    v = _weak(s, ln - 64, ln, z)
    w = _weak(s, ln - 32, (y + _K1) & M64, x)
    x = (x * _K1 + _fetch64(s, 0)) & M64
    ln2 = (ln - 1) & ~63
    off = 0
    while True:
        x = (_rotate((x + y + v[0] + _fetch64(s, off + 8)) & M64, 37) * _K1) & M64
        y = (_rotate((y + v[1] + _fetch64(s, off + 48)) & M64, 42) * _K1) & M64
        x ^= w[1]
        y = (y + v[0] + _fetch64(s, off + 40)) & M64
        z = (_rotate((z + w[0]) & M64, 33) * _K1) & M64
        v = _weak(s, off, (v[1] * _K1) & M64, (x + w[0]) & M64)
        w = _weak(s, off + 32, (z + w[1]) & M64, (y + _fetch64(s, off + 16)) & M64)
        z, x = x, z
        off += 64
        ln2 -= 64
        if ln2 == 0:
            break
    return _hashlen16((_hashlen16(v[0], w[0]) + _shiftmix(y) * _K1 + z) & M64,
                      (_hashlen16(v[1], w[1]) + x) & M64)


def cityhash64_utf16_to_uint32(s):
    """UE 版：UTF-16LE 字节 → CityHash64 → 折叠成 uint32（高 32 位 * 23）。"""
    if len(s) == 0:
        return 0
    h = cityhash64(s.encode("utf-16-le"))
    return ((h & M32) + (((h >> 32) & M32) * 23)) & M32


# --------------------------------------------------------------------------
# UnrealString
# --------------------------------------------------------------------------
def read_unreal_string(b, i):
    (ln,) = struct.unpack_from("<i", b, i)
    i += 4
    if ln > 0:
        raw = b[i:i + ln]
        i += ln
        return raw.decode("ascii", "replace").rstrip("\x00"), i
    if ln < 0:
        nb = -ln * 2
        raw = b[i:i + nb]
        i += nb
        return raw.decode("utf-16-le").rstrip("\x00"), i
    return "", i


def write_unreal_string(out, value, force_unicode=False):
    v = value + "\x00"
    if not force_unicode and all(ord(c) <= 127 for c in v):
        data = v.encode("ascii")
        out += struct.pack("<i", len(data))
        out += data
    else:
        data = v.encode("utf-16-le")
        out += struct.pack("<i", -len(v))
        out += data
    return out


# --------------------------------------------------------------------------
# 读写
# --------------------------------------------------------------------------
class Entry(object):
    __slots__ = ("key", "value", "source_hash", "key_hash")

    def __init__(self, key, value, source_hash, key_hash=None):
        self.key = key
        self.value = value
        self.source_hash = source_hash
        self.key_hash = key_hash


class Namespace(object):
    __slots__ = ("name", "entries", "name_hash")

    def __init__(self, name, entries=None, name_hash=None):
        self.name = name
        self.entries = entries if entries is not None else []
        self.name_hash = name_hash


def load(path):
    b = open(path, "rb").read()
    return loads(b)


def loads(b):
    if b[:16] != LOCRES_MAGIC:
        raise ValueError("不是 locres（magic 不匹配）: " + b[:16].hex(" "))
    version = b[16]
    i = 17
    string_table = []
    if version >= V_COMPACT:
        (array_off,) = struct.unpack_from("<q", b, i)
        i += 8
        save_i = i
        j = array_off
        (st_count,) = struct.unpack_from("<i", b, j)
        j += 4
        for _ in range(st_count):
            s, j = read_unreal_string(b, j)
            if version >= V_OPTIMIZED:
                j += 4                      # refCount
            string_table.append(s)
        i = save_i
    if version >= V_OPTIMIZED:
        (entry_count,) = struct.unpack_from("<i", b, i)
        i += 4
    (ns_count,) = struct.unpack_from("<i", b, i)
    i += 4
    namespaces = []
    for _ in range(ns_count):
        ns_hash = None
        if version >= V_OPTIMIZED:
            (ns_hash,) = struct.unpack_from("<I", b, i)
            i += 4                          # namespaceKeyHash
        ns_name, i = read_unreal_string(b, i)
        (key_count,) = struct.unpack_from("<i", b, i)
        i += 4
        ns = Namespace(ns_name, name_hash=ns_hash)
        for _ in range(key_count):
            key_hash = None
            if version >= V_OPTIMIZED:
                (key_hash,) = struct.unpack_from("<I", b, i)
                i += 4                      # stringKeyHash
            key, i = read_unreal_string(b, i)
            (src_hash,) = struct.unpack_from("<I", b, i)
            i += 4
            if version >= V_COMPACT:
                (st_idx,) = struct.unpack_from("<i", b, i)
                i += 4
                if not (0 <= st_idx < len(string_table)):
                    raise ValueError(f"stringTable 索引越界: {st_idx}")
                value = string_table[st_idx]
            else:
                value, i = read_unreal_string(b, i)
            ns.entries.append(Entry(key, value, src_hash, key_hash))
        namespaces.append(ns)
    return {"version": version, "namespaces": namespaces, "string_table": string_table,
            "entry_count": entry_count if version >= V_OPTIMIZED else -1,
            "consumed": i, "size": len(b)}


def dumps(data, version=None):
    version = data["version"] if version is None else version
    namespaces = data["namespaces"]
    if version == V_LEGACY:
        out = b""
        out += struct.pack("<i", len(namespaces))
        for ns in namespaces:
            out = write_unreal_string(out, ns.name, force_unicode=True)
            out += struct.pack("<i", len(ns.entries))
            for e in ns.entries:
                out = write_unreal_string(out, e.key)
                out += struct.pack("<I", e.source_hash)
                out = write_unreal_string(out, e.value)
        return out

    out = bytearray()
    out += LOCRES_MAGIC
    out += bytes([version])
    out += struct.pack("<q", 0)             # 占位：localizedStringArrayOffset
    if version >= V_OPTIMIZED:
        out += struct.pack("<i", 0)         # 占位：localizedStringEntryCount
    out += struct.pack("<i", len(namespaces))

    string_table = []                       # list[[text, refcount]]
    index_of = {}
    entry_count = 0
    for ns in namespaces:
        if version == V_OPTIMIZED_CITYHASH:
            out += struct.pack("<I", cityhash64_utf16_to_uint32(ns.name))
        elif version >= V_OPTIMIZED:
            out += struct.pack("<I", str_crc32(ns.name))
        out = write_unreal_string(out, ns.name)
        out += struct.pack("<i", len(ns.entries))
        for e in ns.entries:
            if version == V_OPTIMIZED_CITYHASH:
                out += struct.pack("<I", cityhash64_utf16_to_uint32(e.key))
            elif version == V_OPTIMIZED:
                out += struct.pack("<I", str_crc32(e.key))
            out = write_unreal_string(out, e.key)
            out += struct.pack("<I", e.source_hash)
            idx = index_of.get(e.value)
            if idx is None:
                idx = len(string_table)
                index_of[e.value] = idx
                string_table.append([e.value, 1])
            else:
                string_table[idx][1] += 1
            out += struct.pack("<i", idx)
            entry_count += 1

    string_table_offset = len(out)
    out += struct.pack("<i", len(string_table))
    for text, refcount in string_table:
        out = write_unreal_string(out, text)
        if version >= V_OPTIMIZED:
            out += struct.pack("<i", refcount)

    struct.pack_into("<q", out, 17, string_table_offset)
    if version >= V_OPTIMIZED:
        struct.pack_into("<i", out, 25, entry_count)
    return bytes(out)


def total_entries(data):
    return sum(len(ns.entries) for ns in data["namespaces"])
