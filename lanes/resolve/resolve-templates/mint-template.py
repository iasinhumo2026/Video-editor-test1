#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# ///
"""mint-template.py: mint a Resolve project template (.drp) at any frame rate, offline.

Resolve's scripting API cannot write timelinePlaybackFrameRate (SetSetting returns
False for every value), which is why .drp templates exist at all. This script removes
the last human step: instead of clicking the rate into Project Settings once per
frame rate, patch an existing template's settings blob directly.

Where the settings live (mapped 2026-08-04 against Resolve Studio 21.0.3 exports):
  project.xml > CommonConfig > SM_Config > FieldsBlob   (hex text)
    = keyed-dict [u32 hdr=1][u32 count] of {SetupBA: BYTES, LastModTimeForCache: i64}
      (big-endian, UTF-16BE keys, same layout the upstream davinci-resolve-mcp
       keyed-dict.js round-trips for media blobs)
  SetupBA = [u32 1][u32 payloadLen][u8 0x81][zstd frame]
  decompressed payload = protobuf message with (fields verified by A/B export diffs):
    f15  varint  timeline frame rate enum = floor(fps) * 2; EXACTLY 24 fps = field absent
                 (verified 18 rates: 16->32 ... 23.976->46, 29.97->58, 30->60, 120->240)
    f248 float32 PLAYBACK frame rate (the API-unwritable setting); absent at 24
  Everything else (resolution, color science, defaults) rides along untouched.

usage: uv run lanes/resolve/resolve-templates/mint-template.py <source.drp> <fps> <out.drp>
  paths are taken as given: from the repo root, pass them repo-relative, e.g.
  uv run lanes/resolve/resolve-templates/mint-template.py \
    lanes/resolve/resolve-templates/1080p30.drp 23.976 \
    lanes/resolve/resolve-templates/1080p23976.drp

Needs Python 3.14+ (stdlib compression.zstd) or `pip install zstandard`.

ALWAYS verify a minted template before trusting it: pm.ImportProject + read back
BOTH timelineFrameRate and timelinePlaybackFrameRate, then delete the scratch project.
"""
import re
import struct
import sys
import zipfile

try:
    from compression import zstd
except ImportError:  # < 3.14
    import zstandard as _z

    class zstd:  # noqa: N801 (minimal shim, same two calls)
        compress = staticmethod(lambda b, level=9: _z.ZstdCompressor(level=level).compress(b))
        decompress = staticmethod(lambda b: _z.ZstdDecompressor().decompress(b))


def parse_fields(b):
    """Top-level protobuf fields as (start, end, fnum, wiretype)."""
    out, off = [], 0
    while off < len(b):
        start = off
        tag, shift = 0, 0
        while True:
            c = b[off]; off += 1
            tag |= (c & 0x7F) << shift; shift += 7
            if not c & 0x80:
                break
        fnum, wt = tag >> 3, tag & 7
        if wt == 0:
            while b[off] & 0x80:
                off += 1
            off += 1
        elif wt == 1:
            off += 8
        elif wt == 5:
            off += 4
        elif wt == 2:
            n, shift = 0, 0
            while True:
                c = b[off]; off += 1
                n |= (c & 0x7F) << shift; shift += 7
                if not c & 0x80:
                    break
            off += n
        else:
            raise ValueError(f"unsupported wire type {wt} at {start}")
        out.append((start, off, fnum, wt))
    return out


def encode_varint(v):
    out = bytearray()
    while True:
        out.append((v & 0x7F) | (0x80 if v > 0x7F else 0))
        v >>= 7
        if not v:
            return bytes(out)


def retarget(pb, fps):
    """Strip f15/f248 and re-insert them for `fps` (omit both at exactly 24)."""
    fields = parse_fields(pb)
    keep = bytearray()
    insert_at = None
    for start, end, fnum, _wt in fields:
        if fnum in (15, 248):
            if insert_at is None:
                insert_at = len(keep)
            continue
        keep.extend(pb[start:end])
    if insert_at is None:
        insert_at = len(keep)
    patch = b""
    if abs(fps - 24.0) > 1e-9:
        patch += encode_varint(15 << 3 | 0) + encode_varint(int(fps) * 2)          # f15
        patch += encode_varint(248 << 3 | 5) + struct.pack("<f", fps)              # f248
    return bytes(keep[:insert_at]) + patch + bytes(keep[insert_at:])


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__.strip().split("\n")[0] + "\nusage: mint-template.py <source.drp> <fps> <out.drp>")
    src, fps, dst = sys.argv[1], float(sys.argv[2]), sys.argv[3]

    z = zipfile.ZipFile(src)
    xml = z.read("project.xml").decode("utf-8")
    m = re.search(r"(<CommonConfig>.*?<FieldsBlob>)([0-9a-fA-F]+)(</FieldsBlob>)", xml, re.S)
    if not m:
        sys.exit("no CommonConfig FieldsBlob found: not a .drp project export?")
    cfg = bytes.fromhex(m.group(2))

    klen = struct.unpack(">I", cfg[8:12])[0]
    lenpos = 12 + klen + 5                                    # key + vtype(4) + subtype(1)
    balen = struct.unpack(">I", cfg[lenpos:lenpos + 4])[0]
    ba_start = lenpos + 4
    ba, suffix = cfg[ba_start:ba_start + balen], cfg[ba_start + balen:]
    if ba[8] != 0x81 or ba[9:13] != b"\x28\xb5\x2f\xfd":
        sys.exit("unexpected SetupBA wrapper (no zstd frame): format changed?")

    pb = zstd.decompress(ba[9:])
    pb2 = retarget(pb, fps)
    comp = zstd.compress(pb2, 9)
    assert zstd.decompress(comp) == pb2
    new_ba = ba[:4] + struct.pack(">I", 1 + len(comp)) + b"\x81" + comp
    new_cfg = cfg[:lenpos] + struct.pack(">I", len(new_ba)) + new_ba + suffix

    xml2 = xml[: m.start(2)] + new_cfg.hex() + xml[m.end(2):]
    name = re.search(r"<ProjectName>([^<]*)</ProjectName>", xml2)
    if name:
        stem = re.sub(r"\.drp$", "", re.split(r"[\\/]", dst)[-1])   # either separator: a Windows path named the whole path
        xml2 = xml2.replace(name.group(0), f"<ProjectName>_tpl_{stem}</ProjectName>")

    out = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    for n in z.namelist():
        out.writestr(n, xml2 if n == "project.xml" else z.read(n))
    out.close()

    # readback from the written file
    chk = zipfile.ZipFile(dst).read("project.xml").decode("utf-8")
    cfg2 = bytes.fromhex(re.search(r"<CommonConfig>.*?<FieldsBlob>([0-9a-fA-F]+)</FieldsBlob>", chk, re.S).group(1))
    ba2 = cfg2[ba_start:ba_start + struct.unpack(">I", cfg2[lenpos:lenpos + 4])[0]]
    pb3 = zstd.decompress(ba2[9:9 + struct.unpack(">I", ba2[4:8])[0] - 1])
    got = {f: pb3[s:e] for s, e, f, _ in parse_fields(pb3) if f in (15, 248)}

    def _varint(b):  # decode the varint after the field's tag varint
        i = 0
        while b[i] & 0x80:
            i += 1
        v, shift = 0, 0
        for c in b[i + 1:]:
            v |= (c & 0x7F) << shift; shift += 7
        return v

    f15_s = "absent (24)" if 15 not in got else str(_varint(got[15]))
    f248_s = "absent (24)" if 248 not in got else f"{struct.unpack('<f', got[248][-4:])[0]:.6g}"
    print(f"wrote {dst}")
    print(f"  f15 (timeline rate enum): {f15_s}")
    print(f"  f248 (playback rate):     {f248_s}")
    print("verify in Resolve before trusting: ImportProject + read back timelineFrameRate AND timelinePlaybackFrameRate")


if __name__ == "__main__":
    main()
