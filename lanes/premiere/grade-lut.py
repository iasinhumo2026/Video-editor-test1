#!/usr/bin/env python3
"""
grade-lut.py — apply a LUT to a job's Premiere GRADE layer, headless.

The house look is Autumn-Rec709 (assets/luts/rec709/), applied as Creative > Look
at Intensity 80 / Saturation 120 (2026-09-14; 70/115 until then); `apply` with no LUT named replays exactly that.

Premiere's Lumetri LUT slot cannot be driven through the scripting API (mechanism, traps
and verification discipline: lanes/premiere/premiere-grading.md; the look itself is the preset's). It lives in four serialized params plus the
component's private-data struct, all written into the .prproj itself, each guarded by a
BinaryHash whose 96-bit half is a proprietary digest — so the params are CAPTURED once from
a project where the LUT was applied by hand, and replayed verbatim thereafter.

  luts                                       # every .cube under assets/luts, which ones replay
  apply   <target.prproj>                    # the house look (Autumn-Rec709)
  apply   <target.prproj> --lut <Name>       # any other captured LUT (see `luts`)
  apply   <target.prproj> <params-file>      # an explicit params file
  capture <donor.prproj> [out] --slot look   # one-time per LUT, from a hand-applied project;
                                             # `out` defaults to <name>.lookparams next to the cube
  strip   <target.prproj> --slot look        # remove the LUT payloads ONLY — the numeric dials
                                             # (Intensity 80, Saturation 120, ...) are left as they are
  selfcheck                                  # every shipped params file, OFFLINE: element shapes, the
                                             # BinaryHash length words, the embedded cube against the
                                             # .cube beside it, the dials, the struct, sha256 drift
  selfcheck --lut <Name> | <params-file>     # just one. `apply` and `capture` run the same checks,
                                             # so a damaged file is refused before it reaches a .prproj

  --which N     which Lumetri instance on the clip (default 0)
  --slot  S     input | look (default look). `capture` and `strip` take it; `apply`
                reads the slot from the params file.

                look  = Creative > Look, which renders AFTER the dials, so correction and
                        LUT fit in ONE Lumetri and the panel shows both. The house slot.
                input = Basic Correction > Input LUT, which renders BEFORE the dials, so
                        a balance pass needs its own earlier Lumetri instance (--which 1).

Testing a LUT that has no params yet: apply it by hand in Premiere (Lumetri > Creative >
Look > Browse > assets/luts/...), set the dials, save, then `capture` that project. From
then on it is one `apply --lut <Name>` per job.

Premiere must NOT have the target project open while writing. Hands-off, that is three commands:
  ./lanes/premiere/premiere-up.sh --quit  ->  grade-lut.py apply <job>.prproj  ->  ./lanes/premiere/premiere-up.sh <job>.prproj
(the quit saves first, so the fresh Lumetri is on disk to write into). Copy the .prproj first.
"""
import re, gzip, base64, json, sys, os, glob, struct, hashlib
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_LUT = 'Autumn-Rec709'
# The locked house preset (presets/youtube/default/README.md § Grade): pid 26 = Look Intensity,
# pid 31 = Creative Saturation. `selfcheck` only WARNS when the default LUT's dials differ, because
# a deliberate re-dial is allowed; it must just never happen by accident.
HOUSE_DIALS = {'26': 80.0, '31': 120.0}
LUT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'luts'))

# Which serialized params carry a LUT, per Lumetri slot. Same shape either way: the Blob,
# a UTF-16LE path, an enum (0 for a browsed custom file), and the cube itself parsed to
# binary in Embedded LUTs. Only the path/enum pids differ. Found by diffing a Look-applied
# save against a fresh Lumetri: exactly pids 1, 24, 98 changed, enum 25 stayed 0.
SLOTS = {
    'input': dict(arb=(1, 4, 98),     enum=5,  path=4,  ext='.lutparams'),
    'look':  dict(arb=(1, 4, 24, 98), enum=25, path=24, ext='.lookparams'),   # 4 too: Premiere writes it as an explicit sentinel once a Look is on
}
SENTINEL_BYTES = b'\xfe\xfe'
SENTINEL = base64.b64encode(SENTINEL_BYTES).decode()

# ⚠️ VERSION-BOUND. This whole mechanism is calibrated to what Premiere 26.3.2 writes (2026-09-01),
# and nothing checks the running version — not here, not in check-setup.sh, not in setup. If a
# Premiere update changes this struct's layout, `apply` still succeeds and the project still
# opens, but the grade may render nothing: the failure is SILENT, exactly like a poisoned
# Lumetri or a muted track. Diagnose it the documented way — a frame grab with the layer
# toggled, never a readback — and if the frame does not move on a new Premiere build, suspect
# this constant first: re-apply the LUT by hand on that build and re-run `capture` to mint a
# fresh one. Nothing else in the pipeline is version-bound this tightly.
# The component's own PremiereFilterPrivateData as Premiere writes it for a FRESH Lumetri with a
# LUT on it (word 24 = 257). It is LUT- and slot-independent (byte-identical across the Autumn
# Look and the London Input-LUT captures) but it DOES carry instance history: a scratch Lumetri
# that had LUTs removed and re-applied a few times came back with word 10 = 1 as well. The
# pipeline always replays into a fresh instance, so capture writes this verified struct (the one
# proof.prproj cold-opened with, 2026-09-01) and only warns when the donor's differed. Revisit
# only if a Premiere upgrade changes what a fresh hand-applied LUT writes here.
PFPD_FRESH_LUT = ('<PremiereFilterPrivateData Encoding="base64" BinaryHash="696a28d1-c569-b942-6236-e3710000008c">'
                  'dG11bAMAAAD/////////////////////AAAAAP//////////AAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
                  'AAAAAAAAAAAAAAAAeOz//3js//947P//AQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAA=\n\t\t</PremiereFilterPrivateData>')

def load(p):   return gzip.open(p, 'rb').read().decode('utf-8')
def save(p, x): gzip.open(p, 'wb').write(x.encode('utf-8'))

# ── the LUT library (assets/luts) ──────────────────────────────────────────────────────
def lut_files(ext):
    """{name: path} for every file with this extension under assets/luts."""
    return {os.path.splitext(os.path.basename(p))[0]: p
            for p in sorted(glob.glob(os.path.join(LUT_ROOT, '**', '*' + ext), recursive=True))}

def resolve_params(name):
    """The captured params for a LUT name, or a clear exit telling you how to mint them."""
    looks = lut_files('.lookparams')
    if name in looks: return looks[name]
    cubes = lut_files('.cube')
    if name in cubes:
        sys.exit("%s has a cube (%s) but no captured params yet.\n"
                 "One-time mint: apply it by hand in Premiere (Lumetri > Creative > Look > Browse > that file),\n"
                 "set the dials, save, then:  uv run lanes/premiere/grade-lut.py capture <that>.prproj --slot look"
                 % (name, os.path.relpath(cubes[name])))
    sys.exit("no LUT named %s under %s (run `grade-lut.py luts`)" % (name, os.path.relpath(LUT_ROOT)))

def payload_bytes(el):
    m = re.search(r'<StartKeyframeValue[^>]*>(.*?)</StartKeyframeValue>', el, re.S)
    return base64.b64decode(re.sub(r'\s', '', m.group(1))) if m else b''

def cube_path_of(caps):
    """The .cube path Premiere browsed to when these params were captured (UTF-16LE path param)."""
    s = SLOTS[caps.get('slot', 'input')]
    raw = payload_bytes(caps.get(str(s['path']), ''))
    return raw.decode('utf-16-le', 'replace').rstrip('\0') if len(raw) > 2 else ''

def cmd_luts():
    cubes, looks, inputs = lut_files('.cube'), lut_files('.lookparams'), lut_files('.lutparams')
    print("%s  (default: %s)" % (os.path.relpath(LUT_ROOT), DEFAULT_LUT))
    for name, p in cubes.items():
        if name in looks:
            caps = json.load(open(looks[name], encoding="utf-8"))
            src = cube_path_of(caps)
            note = '' if src.startswith(LUT_ROOT) else (
                '\n%38s   captured from %s\n%38s   (a label only — it replays from the embedded cube data)'
                % ('', src, ''))
            tag = 'replayable (look slot, %d dials)%s' % (len(caps.get('num', {})), note)
        elif name in inputs:
            tag = 'input-slot capture only (retired) — hand-apply as a Look + `capture --slot look` to use it'
        else:
            tag = 'needs a one-time capture'
        print("  %-36s %s%s" % (os.path.relpath(p, LUT_ROOT), '<- DEFAULT  ' if name == DEFAULT_LUT else '', tag))
    orphans = [n for n in list(looks) + list(inputs) if n not in cubes]
    if orphans: print("  params without a cube:", ", ".join(orphans))

# ── selfcheck: everything a params file must satisfy, provable OFFLINE ─────────────────
# Why this exists (2026-09-02, your-job): a same-afternoon re-mint of Autumn's params
# captured pid 4 SELF-CLOSING. `apply` printed success, Premiere refused the project as damaged,
# and finding that one element cost a 27-minute bisect on a live job. Every fact below is one
# that was true of every params file that ever opened, and each is cheap to assert on disk.
def _hash_len_word(el):
    """The low 32 bits of a BinaryHash: measured to be payload length + 12 on every real sample."""
    m = re.search(r'BinaryHash="[0-9a-f-]*?([0-9a-f]{8})"', el)
    return int(m.group(1), 16) if m else None

def fix_pid4(caps):
    """A LUT'd Lumetri needs the Input-LUT path param (pid 4) as the EXPLICIT empty sentinel
    (`>/v4=</StartKeyframeValue>`); Premiere refuses a self-closing one as damaged. Verified by
    bisect on your-job 2026-09-02 (pid 4 was the only difference between refused and
    opened). Returns True when it had to rewrite."""
    el = str(caps.get('4', ''))
    if caps.get('slot') == 'look' and el.rstrip().endswith('/>'):
        caps['4'] = re.sub(r'\s*/>$', '>%s\n\t\t</StartKeyframeValue>' % SENTINEL, el.rstrip())
        return True
    return False

def cube_rows(path):
    """(LUT_3D_SIZE, the data floats in file order) from a .cube."""
    size, vals = None, []
    for l in open(path, encoding='utf-8', errors='replace'):
        l = l.strip()
        if l.startswith('LUT_3D_SIZE'): size = int(l.split()[1])
        elif l and l[0] in '0123456789.-': vals.extend(float(x) for x in l.split()[:3])
    return size, vals

def check_caps(caps, cube=None):
    """(fails, warns) for a loaded params dict. A fail means Premiere would refuse the project or
    render no grade; a warn is something a human should know before shipping the file."""
    fails, warns = [], []
    slot = caps.get('slot')
    if slot not in SLOTS: return ["slot %r is not one of %s" % (slot, ', '.join(SLOTS))], []
    s = SLOTS[slot]
    for p in s['arb'] + ('pfpd',):
        el = str(caps.get('component_pfpd' if p == 'pfpd' else str(p), ''))
        tag = 'PremiereFilterPrivateData' if p == 'pfpd' else 'StartKeyframeValue'
        label = 'component_pfpd' if p == 'pfpd' else 'pid %s' % p
        if not el:
            fails.append("%s missing%s" % (label, ' (captured before the 2026-09-01 fix; apply refuses it)' if p == 'pfpd' else ''))
            continue
        m = re.search(r'<%s[^>]*>(.*?)</%s>' % (tag, tag), el, re.S)
        if el.rstrip().endswith('/>') or not m:
            fails.append("%s is self-closing, not an open/close <%s> (Premiere refuses the project as damaged)" % (label, tag))
            continue
        if 'Encoding="base64"' not in el:
            fails.append("%s has no base64 Encoding attribute" % label)
        try: raw = base64.b64decode(re.sub(r'\s', '', m.group(1)), validate=True)
        except Exception:
            fails.append("%s payload is not valid base64" % label); continue
        h = _hash_len_word(el)
        if h is None:
            fails.append("%s has no BinaryHash (an unhashed payload is discarded silently)" % label)
        elif h != len(raw) + 12:
            fails.append("%s BinaryHash length word is %d but the payload is %d bytes (+12 expected): edited after capture?"
                         % (label, h, len(raw)))
        if p == 'pfpd':
            if len(raw) != 128: fails.append("component_pfpd is %d bytes, not the 128-byte tmul struct" % len(raw))
            elif el != PFPD_FRESH_LUT: warns.append("component_pfpd is not the verified fresh-instance struct (instance history?)")
    if slot == 'look' and payload_bytes(str(caps.get('4', ''))) != SENTINEL_BYTES:
        fails.append("pid 4 must decode to the empty sentinel %r in the look slot" % SENTINEL_BYTES)
    enum = str(caps.get(str(s['enum']), ''))
    if not re.fullmatch(r'-?\d+\.?', enum):
        fails.append("enum pid %d is %r, not an int" % (s['enum'], enum))
    # pid 98, the cube itself: an ITX3 block whose float32 data is the .cube's, tail-aligned
    raw = payload_bytes(str(caps.get('98', '')))
    if raw in (b'', SENTINEL_BYTES):
        fails.append("pid 98 carries no embedded cube: it would replay as NO grade, silently")
    else:
        i = raw.find(b'ITX3')
        n = struct.unpack_from('<I', raw, i + 4)[0] if 0 <= i <= len(raw) - 8 else 0
        if not (2 <= n <= 129) or len(raw) < n ** 3 * 12 or len(raw) - n ** 3 * 12 > 256:
            fails.append("pid 98 is not a plausible ITX3 cube (size word %d, %d bytes)" % (n, len(raw)))
        elif cube:
            csize, cvals = cube_rows(cube)
            emb = struct.unpack_from('<%df' % (n ** 3 * 3), raw, len(raw) - n ** 3 * 12)
            if csize != n or len(cvals) != len(emb):
                fails.append("embedded cube is %d^3 but %s is LUT_3D_SIZE %s with %d values"
                             % (n, os.path.basename(cube), csize, len(cvals) // 3))
            else:
                d = max(abs(a - b) for a, b in zip(emb, cvals))
                if d > 1e-5:
                    fails.append("embedded cube data is not %s (max delta %.3g): these params belong to a different LUT"
                                 % (os.path.basename(cube), d))
        else:
            warns.append("no .cube of the same name to compare the embedded cube against")
    src = cube_path_of(caps)
    if not src:
        fails.append("pid %d (the LUT path) does not decode as a UTF-16LE path" % s['path'])
    else:
        home = re.match(r'(/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])([^/\\]+)', src)
        if home and home.group(2) != 'Shared':
            warns.append("the baked path %s carries a home directory; the packaging leak-check rejects it" % src)
        if cube and os.path.basename(src) != os.path.basename(cube):
            warns.append("the baked path names %s, not %s" % (os.path.basename(src), os.path.basename(cube)))
    num = caps.get('num') or {}
    if not num:
        fails.append("no numeric dials: a blob-only capture replays the LUT at Intensity 100")
    else:
        bad = [p for p, v in num.items() if str(v) not in ('true', 'false')
               and not re.fullmatch(r'-?\d+(\.\d*)?([eE][-+]?\d+)?', str(v))]
        if bad: fails.append("dials with non-numeric values: %s" % ', '.join(bad))
    return fails, warns

def check_params(path, cube=None):
    try: caps = json.load(open(path, encoding="utf-8"))
    except Exception as e: return ["not JSON: %s" % e], []
    return check_caps(caps, cube)

def cmd_selfcheck(lut=None, files=()):
    cubes, looks, inputs = lut_files('.cube'), lut_files('.lookparams'), lut_files('.lutparams')
    if files:  targets = [(os.path.splitext(os.path.basename(f))[0], f) for f in files]
    elif lut:  targets = [(lut, resolve_params(lut))]
    else:      targets = sorted(looks.items()) + sorted(inputs.items())
    readme_p = os.path.join(LUT_ROOT, 'README.md')
    readme = open(readme_p, encoding='utf-8').read() if os.path.exists(readme_p) else ''
    ok = True
    for name, p in targets:
        fails, warns = check_params(p, cubes.get(name))
        # sha256 drift against the README: a re-mint is allowed, an UNNOTICED one is not. The
        # damaged 2026-09-02 file was a same-afternoon re-mint nobody had validated from a render.
        sha = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        rel = os.path.relpath(p, LUT_ROOT) if p.startswith(LUT_ROOT) else os.path.basename(p)
        rec = re.search(r'`%s`[^\n]*?([0-9a-f]{64})' % re.escape(rel), readme)
        if not rec:
            warns.append("no sha256 recorded in assets/luts/README.md § Checksums (current: %s)" % sha)
        elif rec.group(1) != sha:
            warns.append("sha256 DRIFTED from assets/luts/README.md: the file changed since it was last validated.\n"
                         "      If this re-mint was deliberate and verified from a render, record %s there;\n"
                         "      otherwise this file has never been proven to open." % sha)
        if name == DEFAULT_LUT:
            num = json.load(open(p, encoding="utf-8")).get('num', {}) if not fails else {}
            off = {k: num.get(k) for k, v in HOUSE_DIALS.items() if num and float(num.get(k, 'nan') or 'nan') != v}
            if off: warns.append("house dials are not the locked preset: %s (locked: %s)" % (off, HOUSE_DIALS))
        ok &= not fails
        shown = os.path.relpath(p)
        print("%s %s" % ('✗' if fails else '✓', p if shown.startswith('..') else shown))
        for f in fails: print("    FAIL %s" % f)
        for w in warns: print("    warn %s" % w)
    if not ok:
        sys.exit("selfcheck FAILED: do not `apply` a failing file; re-capture it from a hand-applied project")

# ── .prproj surgery ────────────────────────────────────────────────────────────────────
def lumetri_objs(xml, which=0):
    """ParameterID -> ObjectID for the `which`-th Lumetri component in the project.

    The GRADE layer carries ONE Lumetri on the house recipe (the Look renders after the
    dials, so nothing needs a second instance). `which` exists for the retired input-slot
    layout, where the LUT sat on a second instance behind a balance pass.
    """
    comps = [m for m in re.finditer(
        r'<VideoFilterComponent ObjectID="(\d+)"[^>]*>(.*?)</VideoFilterComponent>', xml, re.S)
        if 'AE.ADBE Lumetri' in m.group(2)]
    if len(comps) <= which:
        sys.exit("Lumetri #%d not found (%d present) — add it to the GRADE layer first" % (which, len(comps)))
    # ☠️ Instances are indexed across the WHOLE project file, not just the GRADE layer, and the
    # order is the file's, not the timeline's. On a real job a leftover Lumetri on a FOOTAGE clip
    # held #0 while the GRADE layer's was #1, so the default would have written the LUT into the
    # wrong clip and rendered nothing on the layer. Never assume #0 is the grade when >1 exists.
    if len(comps) > 1:
        print("⚠️  %d Lumetri instances in this project — targeting #%d. They are indexed across the whole\n"
              "    file, so a Lumetri left on a footage clip can occupy #0. Verify the target (--which N)\n"
              "    before trusting this write; strip stray Lumetri from footage clips first."
              % (len(comps), which), file=sys.stderr)
    comp = comps[which]
    out = {}
    for oid in {int(b) for _, b in re.findall(r'<Param Index="(\d+)" ObjectRef="(\d+)"/>', comp.group(2))}:
        m = re.search(r'<(\w+) ObjectID="%d"[^>]*>.*?</\1>' % oid, xml, re.S)
        if not m: continue
        p = re.search(r'<ParameterID>(-?\d+)</ParameterID>', m.group(0))
        if p: out[int(p.group(1))] = oid
    return out

def lumetri_component(xml, which=0):
    comps = [m for m in re.finditer(
        r'<VideoFilterComponent ObjectID="(\d+)"[^>]*>(.*?)</VideoFilterComponent>', xml, re.S)
        if 'AE.ADBE Lumetri' in m.group(2)]
    return comps[which]

def component_pfpd(xml, which=0):
    """The Lumetri COMPONENT's own <PremiereFilterPrivateData> element (a 128-byte 'tmul'
    struct on the component itself, not a param). Applying a LUT by hand flips it from the
    fresh struct to a 'LUT present' struct. It is NOT one of the params, so a param-only
    write leaves it fresh, and Premiere then refuses the whole project as damaged. Every
    write that ever opened had inherited an already-flipped struct from an earlier hand
    apply; every write into a truly fresh Lumetri failed. Capture it, replay it.

    Premiere de-duplicates identical blobs by BinaryHash: the FIRST Lumetri carrying a given struct holds it
    whole, every later one points at it self-closing (`<PremiereFilterPrivateData … BinaryHash="…"/>`), so
    a second fresh Lumetri in a project (a picture-in-picture clip's, 2026-10-02) has only the reference.
    Match both forms, the way _payload_el does; the replay writes the whole element over either."""
    comp = lumetri_component(xml, which).group(0)
    m = (re.search(r'<PremiereFilterPrivateData[^>]*?/>', comp, re.S) or
         re.search(r'<PremiereFilterPrivateData[^>]*>.*?</PremiereFilterPrivateData>', comp, re.S))
    return m.group(0)

def struct_words(el):
    """The 128-byte struct inside a <PremiereFilterPrivateData> element as uint32 words."""
    import struct
    m = re.search(r'<PremiereFilterPrivateData[^>]*>(.*?)</PremiereFilterPrivateData>', el, re.S)
    raw = base64.b64decode(re.sub(r'\s', '', m.group(1)))
    return struct.unpack('<%dI' % (len(raw) // 4), raw[:len(raw) // 4 * 4])

def put_component_pfpd(xml, which, el):
    c = lumetri_component(xml, which)
    nb = c.group(0).replace(component_pfpd(xml, which), el, 1)
    return xml[:c.start()] + nb + xml[c.end():]

def obj_body(xml, oid, pid=None):
    """The element with this ObjectID — VERIFIED by ParameterID.

    ObjectIDs are NOT unique in a .prproj (this project has 60 duplicated across
    different ClassIDs), so an ID-only lookup can return a completely unrelated
    element. Writing into that is exactly how a project gets silently corrupted:
    the XML stays well-formed and Premiere then refuses it as "damaged". Always
    disambiguate on the ParameterID the caller is actually after.
    """
    for m in re.finditer(r'<(\w+) ObjectID="%d"[^>]*>.*?</\1>' % oid, xml, re.S):
        if pid is None: return m
        got = re.search(r'<ParameterID>(-?\d+)</ParameterID>', m.group(0))
        if got and int(got.group(1)) == pid: return m
    return None

def _payload_el(body):
    """The <StartKeyframeValue …> element, attributes included.

    An EMPTY arb param is written self-closing (`<StartKeyframeValue …/>`), a populated
    one as an open/close pair. Match both — matching only the pair silently fails on a
    freshly-added Lumetri, which is exactly the state you apply a LUT into.
    """
    m = (re.search(r'<StartKeyframeValue[^>]*?/>', body, re.S) or
         re.search(r'<StartKeyframeValue[^>]*>.*?</StartKeyframeValue>', body, re.S))
    if not m: sys.exit("param has no StartKeyframeValue")
    return m.group(0)

def put_payload(xml, oid, payload_el, pid=None):
    """Replace ONLY the payload element inside the target's own param element.

    Never splice a whole element: the surrounding <VideoComponentParam>/<Arb…> carries
    ClassID, Version, KeyframeSetSize and StartKeyframePosition that belong to THIS
    project. Swapping the container wholesale produced a project Premiere refused to
    open ("The project appears to be damaged") even though the XML parsed fine.
    """
    m = obj_body(xml, oid, pid)
    if not m: sys.exit("param pid=%s (obj %d) not found" % (pid, oid))
    body = m.group(0)
    nb = body.replace(_payload_el(body), payload_el, 1)
    return xml[:m.start()] + nb + xml[m.end():]

def set_enum_value(xml, oid, val, pid=5):
    m = obj_body(xml, oid, pid)
    body = m.group(0)
    sk = re.search(r'<StartKeyframe>([^<]*)</StartKeyframe>', body)
    f = sk.group(1).split(','); f[1] = str(val)
    nb = body.replace(sk.group(0), '<StartKeyframe>%s</StartKeyframe>' % ','.join(f), 1)
    return xml[:m.start()] + nb + xml[m.end():]

def auto_state(xml, objs):
    """(auto_pressed, progress) for a Lumetri. Used only to insist the target is a fresh
    instance: the pipeline always applies into one, and a Lumetri someone has pressed Auto on
    carries analytics and a blob the replay would half-overwrite. (An Auto press was once
    suspected of causing the "damaged" corruptions; it was not, see component_pfpd.)"""
    pressed, progress = False, None
    for p, oid in objs.items():
        m = obj_body(xml, oid, p)
        if not m: continue
        b = m.group(0)
        if re.search(r'<Name>\s*Auto Tone Analytics Data\s*</Name>', b):
            kv = re.search(r'<StartKeyframeValue[^>]*>(.*?)</StartKeyframeValue>', b, re.S)
            raw = base64.b64decode(re.sub(r'\s', '', kv.group(1))) if kv else b''
            txt = raw.decode('utf-16-le', 'replace') + raw.decode('utf-8', 'replace')
            pressed = '"mAutoTonePressed":true' in txt
        if re.search(r'<Name>\s*SemanticAutoTone Progress\s*</Name>', b):
            sk = re.search(r'<StartKeyframe>([^<]*)</StartKeyframe>', b)
            progress = sk.group(1).split(',')[1] if sk else None
    return pressed, progress

def require_pristine(xml, objs, role):
    pressed, progress = auto_state(xml, objs)
    if pressed or (progress not in (None, '-1', '-1.')):
        sys.exit("REFUSING: the %s Lumetri is not a fresh instance (Auto pressed=%s, progress=%s). "
                 "Delete the GRADE clip, re-place it with a fresh Lumetri, save, retry."
                 % (role, pressed, progress))

def integrity(before, after):
    """Structure must be untouched apart from the payloads — cheap guard against the
    class of bug that corrupted a real project once."""
    for tag in ('ObjectID', 'ObjectRef'):
        b = sorted(re.findall(r'%s="(\d+)"' % tag, before))
        a = sorted(re.findall(r'%s="(\d+)"' % tag, after))
        if b != a: sys.exit("ABORT: %s set changed — refusing to write" % tag)
    if before.count('<VideoFilterComponent ') != after.count('<VideoFilterComponent '):
        sys.exit("ABORT: component count changed — refusing to write")

# ── commands ───────────────────────────────────────────────────────────────────────────
def cmd_capture(donor, out=None, which=0, slot='look'):
    xml = load(donor); objs = lumetri_objs(xml, which)
    require_pristine(xml, objs, 'donor')
    s = SLOTS[slot]
    caps = {'slot': slot}
    for p in s['arb'] + (s['enum'],):
        body = obj_body(xml, objs[p], p).group(0)
        caps[str(p)] = (_payload_el(body) if p != s['enum']
                        else re.search(r'<StartKeyframe>([^<]*)</StartKeyframe>', body).group(1).split(',')[1])
    # ☠️ TWO empty shapes, not one. `strip` writes the SENTINEL; a Lumetri that never had a LUT
    # serialises pid 98 SELF-CLOSING, which is a different byte pattern and used to sail straight
    # through — capture then wrote a params file with no cube in it, and `apply` replayed a grade
    # that renders nothing. payload_bytes() collapses both to b'' / the sentinel, so test the
    # DECODED payload rather than the tag's text. (A hand-apply can genuinely land here: Premiere
    # LINKS rather than embeds a cube browsed from some locations — 2026-09-02.)
    if payload_bytes(caps['98']) in (b'', SENTINEL_BYTES):
        sys.exit("donor has no embedded LUT in the %s slot — Premiere either never got one, or LINKED\n"
                 "  it instead of embedding it. Re-apply the LUT by hand on a fresh Lumetri and save,\n"
                 "  then re-run. (If it linked again, graft pid 98 from an existing capture of the SAME\n"
                 "  cube — it is a property of the cube, not of where it was browsed from.)" % slot)
    # Every numeric dial too (Look Intensity, Creative Saturation, Basic Correction, toggles).
    # The Blob mirrors some of them but Premiere does NOT read dials from it on load: a
    # blob saying Intensity 100 next to a param saying 70 renders at 70. So the dialed
    # preset is the numeric params, and they must ride along or a fresh job replays the
    # LUT at defaults (Intensity 100, Saturation 100) instead of the approved look.
    skip = set(s['arb']) | {s['enum']}
    num = {}
    for p, oid in objs.items():
        if p in skip: continue
        m = obj_body(xml, oid, p)
        sk = m and re.search(r'<StartKeyframe>([^<]*)</StartKeyframe>', m.group(0))
        if sk: num[str(p)] = sk.group(1).split(',')[1]
    caps['num'] = num
    donor_pfpd = component_pfpd(xml, which)
    if donor_pfpd != PFPD_FRESH_LUT:
        dw = [i for i, (a, b) in enumerate(zip(*(struct_words(e) for e in (donor_pfpd, PFPD_FRESH_LUT)))) if a != b]
        print("⚠️  the donor Lumetri's private-data struct differs from the fresh-instance one at word(s) %s: "
              "instance history, not the LUT. Writing the verified fresh struct instead." % (dw or '?'))
    caps['component_pfpd'] = PFPD_FRESH_LUT
    src = cube_path_of(caps)
    name = os.path.splitext(os.path.basename(src))[0]
    if not out:
        cubes = lut_files('.cube')
        if not name or name not in cubes:
            sys.exit("the donor's LUT (%r) is not a cube under %s — pass an output path, or put the cube in assets/luts first"
                     % (src, os.path.relpath(LUT_ROOT)))
        out = os.path.splitext(cubes[name])[0] + s['ext']
    if not src.startswith(LUT_ROOT):
        print("   captured from %s\n    That path is baked in permanently, but it is a LABEL — Premiere replays from the "
              "embedded cube data and never opens it (measured 2026-09-02)." % src)
    # The path is inert at render time but it SHIPS: it rides inside the hash-sealed payloads, so
    # it cannot be edited out afterwards, and the packaging leak-check rejects a params file
    # carrying someone's home directory. Browsing from a home path is the one capture mistake that
    # cannot be fixed without another hand-application, so say so loudly, here, at capture time.
    home = re.match(r'(/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])([^/\\]+)', src)
    if home and home.group(2) != 'Shared':
        print("⚠️  that path contains a HOME DIRECTORY (%s), which will ship inside every project these params\n"
              "    are applied to and cannot be edited out later (the payloads are hash-sealed). For anything a\n"
              "    client will ever receive, re-apply by hand from a username-free location — /Users/Shared/ is\n"
              "    the house one — and capture again." % home.group(2), file=sys.stderr)
    if fix_pid4(caps):
        print("   pid 4 came off the donor self-closing; written as the explicit sentinel Premiere requires.")
    json.dump(caps, open(out, 'w', encoding="utf-8"))
    print("captured %s (%s slot): %d LUT params + %d numeric dials -> %s (%.0f KB)"
          % (name or 'LUT', slot, len(caps)-3, len(num), os.path.relpath(out), len(json.dumps(caps))/1024))
    # Prove the file that was just written, before anyone applies it. A capture that fails here is
    # left on disk (it is evidence) but the exit status says it must not be used.
    fails, warns = check_params(out, lut_files('.cube').get(name))
    for w in warns: print("   warn %s" % w)
    if fails:
        sys.exit("☠️  the captured file FAILS selfcheck and must not be applied:\n  " + "\n  ".join(fails))
    print("   selfcheck ✓  sha256 %s  (record it in assets/luts/README.md § Checksums)"
          % hashlib.sha256(open(out, 'rb').read()).hexdigest())

def cmd_apply(target, params, which=0):
    xml = load(target); before = xml
    objs = lumetri_objs(xml, which)
    caps = json.load(open(params, encoding="utf-8"))
    require_pristine(xml, objs, 'target')
    s = SLOTS[caps.get('slot', 'input')]
    if fix_pid4(caps):
        print("⚠️  %s carries pid 4 self-closing; replaying it as the explicit sentinel. Re-save the file\n"
              "    (`selfcheck` fails it on disk) so the next apply does not depend on this repair." % os.path.basename(params),
              file=sys.stderr)
    # The same offline proof `selfcheck` runs, here so a damaged params file never reaches a .prproj:
    # the alternative was `apply` printing success and Premiere refusing the project (2026-09-02).
    fails, _ = check_caps(caps, lut_files('.cube').get(os.path.splitext(os.path.basename(params))[0]))
    if fails:
        sys.exit("REFUSING: %s fails selfcheck:\n  " % os.path.basename(params) + "\n  ".join(fails))
    for p in s['arb']:
        xml = put_payload(xml, objs[p], caps[str(p)], p)
    xml = set_enum_value(xml, objs[s['enum']], caps[str(s['enum'])], s['enum'])
    for p, val in caps.get('num', {}).items():
        if int(p) in objs:
            xml = set_enum_value(xml, objs[int(p)], val, int(p))
    if caps.get('component_pfpd'):
        xml = put_component_pfpd(xml, which, caps['component_pfpd'])
    else:
        sys.exit("REFUSING: params file has no component_pfpd (captured before 2026-09-01 fix); "
                 "re-run capture on a hand-applied project")
    integrity(before, xml)
    save(target, xml)
    print("applied %s (%s slot) + %d dials to %s" % (os.path.basename(params), caps.get('slot', 'input'),
                                                     len(caps.get('num', {})), target))

def cmd_strip(target, which=0, slot='look'):
    xml = load(target); before = xml
    objs = lumetri_objs(xml, which)
    s = SLOTS[slot]
    empty = '<StartKeyframeValue Encoding="base64">%s</StartKeyframeValue>' % SENTINEL
    for p in s['arb']:
        xml = put_payload(xml, objs[p], empty, p)
    xml = set_enum_value(xml, objs[s['enum']], 0, s['enum'])
    integrity(before, xml)
    save(target, xml)
    print("stripped %s-slot LUT from %s" % (slot, target))

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    def opt(flag, default=None):
        return a[a.index(flag)+1] if flag in a else default
    w = int(opt('--which', 0))
    s = opt('--slot', 'look')
    if s not in SLOTS: sys.exit("--slot must be one of: " + ", ".join(SLOTS))
    lut = opt('--lut')
    pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith('--') and not a[i-1].startswith('--')]
    cmd = a[0]
    if cmd == 'luts':
        cmd_luts()
    elif cmd == 'apply':
        params = pos[1] if len(pos) > 1 else resolve_params(lut or DEFAULT_LUT)
        cmd_apply(pos[0], params, w)
    elif cmd == 'capture':
        cmd_capture(pos[0], pos[1] if len(pos) > 1 else None, w, s)
    elif cmd == 'strip':
        cmd_strip(pos[0], w, s)
    elif cmd == 'selfcheck':
        cmd_selfcheck(lut, pos)
    else:
        sys.exit(__doc__)
