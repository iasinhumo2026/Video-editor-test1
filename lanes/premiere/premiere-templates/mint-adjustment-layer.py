#!/usr/bin/env python3
"""
mint-adjustment-layer.py — emit an adjustment-layer template project at ANY frame size.

WHY THIS EXISTS
    Scripting cannot CONSTRUCT an adjustment layer (no QE constructor, the MCP's
    add_adjustment_layer is a no-op stub, hand-built FCP XML imports offline), so the
    layer is minted by importing a donor .prproj that already contains one:

        app.project.importSequences("<template>.prproj", ["<sequence-uuid>"])

    The donor's layer carries a FIXED frame size. The original donor is 3840x2160, which
    covers any 16:9 timeline but does NOT reliably cover a VERTICAL one: with Premiere's
    media preference on "Set to frame size", a 16:9 layer scaled to fit 1080x1920 leaves
    the top and bottom of the frame ungraded, silently.

    So: mint the layer at the sequence's own size. This script rewrites the donor.

WHAT IT REWRITES
    A .prproj is gzipped XML. The layer's size lives in exactly one place: the FrameRect
    of the VideoStream reached by
        MasterClip[IsAdjustmentLayer] -> VideoClip -> VideoMediaSource -> Media -> VideoStream
    Everything else in the file is renamed/re-UUID'd so a 1080x1920 layer cannot collide
    with (or be deduped against) a 3840x2160 one already sitting in the target project.

    UUIDs are derived with uuid5 from the size, so minting the same size twice produces a
    byte-identical file and re-importing is idempotent.

    The layer's stream FrameRate is left alone on purpose: the media is synthetic, still
    and continuous-time (IsStill/IsContinuousTime/Infinite), so it has no frames to
    conform and no timebase to mismatch. Size is the only property that matters.

USAGE
    uv run lanes/premiere/premiere-templates/mint-adjustment-layer.py 1080x1920
    uv run lanes/premiere/premiere-templates/mint-adjustment-layer.py 1080x1920 -o /tmp/al.prproj

    Prints the sequence UUID to hand to importSequences. After importing: keep the
    "Adjustment Layer <W>x<H>" item, delete the junk "adj-template-<W>x<H>" sequence.
"""

import argparse
import gzip
import re
import sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DONOR = HERE / "adjustment-layer.prproj"

# Namespace for the derived UUIDs. Arbitrary but fixed: changing it re-mints every
# template under new ids, which would orphan layers already placed in saved projects.
NS = uuid.UUID("6f9b1a44-3f6e-5c2a-9f1d-2c0f5b7a8e10")

# Identifiers that are Premiere's own type/format constants, never this project's
# objects. A remap must never touch them.
FIXED_ATTRS = ("ClassID", "ImplementationID", "MediaType", "PreviewFormatIdentifier")

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def read_donor(path):
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw).decode("utf-8")
    return raw.decode("utf-8")


def own_object_uuids(xml):
    """Every UUID that names an object THIS file owns, minus Premiere's constants."""
    owned = set()
    for pat in (
        r'ObjectUID="(%s)"' % UUID_RE.pattern,
        r'ObjectURef="(%s)"' % UUID_RE.pattern,
        r"<ClipID>(%s)</ClipID>" % UUID_RE.pattern,
        r"<Sequence ObjectURef=\"(%s)\"" % UUID_RE.pattern,
    ):
        owned.update(m.group(1) for m in re.finditer(pat, xml))

    fixed = set()
    for attr in FIXED_ATTRS:
        fixed.update(
            m.group(1) for m in re.finditer(r'%s="(%s)"' % (attr, UUID_RE.pattern), xml)
        )
        fixed.update(
            m.group(1)
            for m in re.finditer(r"<%s>(%s)</%s>" % (attr, UUID_RE.pattern, attr), xml)
        )
    return owned - fixed


def adjustment_layer_stream_id(xml):
    """Walk MasterClip[IsAdjustmentLayer] down to the VideoStream that carries its size."""
    mc = re.search(
        r'<MasterClip ObjectUID="[^"]+"[^>]*>(?:(?!</MasterClip>).)*?'
        r"<IsAdjustmentLayer>true</IsAdjustmentLayer>(?:(?!</MasterClip>).)*?</MasterClip>",
        xml,
        re.S,
    )
    if not mc:
        sys.exit("no MasterClip with <IsAdjustmentLayer>true</IsAdjustmentLayer> in the donor")

    clip_ref = re.search(r'<Clip Index="0" ObjectRef="(\d+)"/>', mc.group(0))
    if not clip_ref:
        sys.exit("adjustment-layer MasterClip has no Clip ObjectRef")

    clip = re.search(
        r'<VideoClip ObjectID="%s"[^>]*>(.*?)</VideoClip>' % clip_ref.group(1), xml, re.S
    )
    if not clip:
        sys.exit("VideoClip #%s not found" % clip_ref.group(1))

    src_ref = re.search(r'<Source ObjectRef="(\d+)"/>', clip.group(1))
    if not src_ref:
        sys.exit("adjustment-layer VideoClip has no Source ObjectRef")

    src = re.search(
        r'<VideoMediaSource ObjectID="%s"[^>]*>(.*?)</VideoMediaSource>' % src_ref.group(1),
        xml,
        re.S,
    )
    if not src:
        sys.exit("VideoMediaSource #%s not found" % src_ref.group(1))

    media_uid = re.search(r'<Media ObjectURef="([^"]+)"/>', src.group(1))
    if not media_uid:
        sys.exit("adjustment-layer media source has no Media ObjectURef")

    media = re.search(
        r'<Media ObjectUID="%s"[^>]*>(.*?)</Media>' % media_uid.group(1), xml, re.S
    )
    if not media:
        sys.exit("Media %s not found" % media_uid.group(1))

    stream_ref = re.search(r'<VideoStream ObjectRef="(\d+)"/>', media.group(1))
    if not stream_ref:
        sys.exit("adjustment-layer Media has no VideoStream ObjectRef")
    return stream_ref.group(1)


def resize_stream(xml, stream_id, width, height):
    block = re.search(
        r'(<VideoStream ObjectID="%s"[^>]*>)(.*?)(</VideoStream>)' % stream_id, xml, re.S
    )
    if not block:
        sys.exit("VideoStream #%s not found" % stream_id)

    body, n = re.subn(
        r"<FrameRect>[^<]*</FrameRect>",
        "<FrameRect>0,0,%d,%d</FrameRect>" % (width, height),
        block.group(2),
    )
    if n != 1:
        sys.exit("expected exactly 1 FrameRect on VideoStream #%s, found %d" % (stream_id, n))
    return xml[: block.start()] + block.group(1) + body + block.group(3) + xml[block.end() :]


def mint(width, height, donor=DONOR):
    xml = read_donor(donor)

    stream_id = adjustment_layer_stream_id(xml)
    xml = resize_stream(xml, stream_id, width, height)

    size = "%dx%d" % (width, height)
    seq_uuid_before = re.search(r'<Sequence ObjectUID="([^"]+)"', xml)
    if not seq_uuid_before:
        sys.exit("no <Sequence ObjectUID> in the donor")
    seq_uuid_before = seq_uuid_before.group(1)

    remap = {
        u: str(uuid.uuid5(NS, "%s/%s" % (size, u))) for u in own_object_uuids(xml)
    }
    for old, new in remap.items():
        xml = xml.replace(old, new)

    # Names, so both the item and the junk sequence are unmistakable in a bin that may
    # already hold a differently sized layer.
    xml = xml.replace("<Name>Adjustment Layer</Name>", "<Name>Adjustment Layer %s</Name>" % size)
    xml = xml.replace("<ClipName>Adjustment Layer</ClipName>", "<ClipName>Adjustment Layer %s</ClipName>" % size)
    xml = xml.replace("<Name>adj-template</Name>", "<Name>adj-template-%s</Name>" % size)

    return xml, remap.get(seq_uuid_before, seq_uuid_before)


def main():
    ap = argparse.ArgumentParser(description="Mint a Premiere adjustment-layer template at a given frame size.")
    ap.add_argument("size", help="WxH, e.g. 1080x1920")
    ap.add_argument("-o", "--out", help="output .prproj (default: alongside the donor, adjustment-layer-WxH.prproj)")
    ap.add_argument("--donor", default=str(DONOR), help="source template (default: the repo's 3840x2160 one)")
    args = ap.parse_args()

    m = re.fullmatch(r"(\d+)x(\d+)", args.size.strip().lower())
    if not m:
        sys.exit("size must look like 1080x1920")
    width, height = int(m.group(1)), int(m.group(2))

    xml, seq_uuid = mint(width, height, Path(args.donor))
    out = Path(args.out) if args.out else HERE / ("adjustment-layer-%dx%d.prproj" % (width, height))
    # mtime 0 so the same size always produces a byte-identical file.
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(out, "wb"), compresslevel=9, mtime=0) as fh:
        fh.write(xml.encode("utf-8"))

    print(out)
    print(seq_uuid)


if __name__ == "__main__":
    main()
