#!/usr/bin/env python3
"""pii-scan.py — sweep the CUT for a literal string that must never reach the screen (a phone number, an API key, an account id).

    uv run workflows/pii-scan.py projects/<job> --needle 555-0100-1234        # sweep the kept spans, write the hit map + a sheet
    uv run workflows/pii-scan.py projects/<job>                               # needles / phrases from projects/<job>/pii.json
    uv run workflows/pii-scan.py projects/<job> --needle ... --all            # sweep the WHOLE raw, not just what ships
    uv run workflows/pii-scan.py projects/<job> --phrase "running a rehearsal" --any-number 7   # words, and any phone-shaped number
    uv run workflows/pii-scan.py projects/<job> --raw assets/captures/g4.mp4 --all        # ANY video: a capture take, a draft
                                                                        # (-> review/pii-scan-g4.json, never the raw's map)
    uv run workflows/pii-scan.py --still grab.png --pii projects/<job>/pii.json            # stills, no video: the pre-take gate

    --needle S        a literal matched through its DIGITS (repeatable); one with no digits at all is swept as a --phrase
    --phrase S        words that must not show (repeatable): case-insensitive, whitespace and punctuation normalised,
                      matched from the START of a word with its end free, so a stem catches every ending ('cancell' hits
                      cancelled and cancelling) while 'sign in' still misses 'design in'. Read against each OCR block AND
                      a frame's blocks joined in reading order and down each column (a line that wraps into the next
                      block still matches, beside a sidebar too); the hit boxes are the blocks carrying its tokens
    --any-number N    flag any block holding a phone-shaped run of >= N digits (groups joined by spaces, dashes, dots or
                      parens or underscores, spaced or not; inside a file name when a separator fences the digits:
                      555-0100-1234.txt, lead_555-0100-1234.txt, call-2026-09-23-555-0100-1234.mp3), clocks, dates,
                      UUIDs and camera date-times excluded; digits glued to letters on BOTH sides (x5550100x) are not
                      counted: the sweep for a number nobody can name in advance
    --pii <file>      the target file (default <job>/pii.json): a JSON list of needles, or {"needles": [...],
                      "phrases": [...], "any_number": N}; any file not ending .json is phrases, one per line (# comments)
    --still PNG ...   OCR these stills instead of a video (job optional, put it FIRST); prints every hit, writes nothing
    --raw <file>      the video to sweep (default: EVERY video under raw/ the EDL plays, each into its own map). Any
                      video works — a screen-record take or an exported draft — with --all, because the EDL's kept
                      spans describe the raw and nothing else
    --all             scan the whole video; default scans ONLY the EDL's kept spans (transcript/cuts.json)
    --coarse N        coarse sample rate in frames per second (default 2)
    --seed-run N      digits of a needle a COARSE frame must show to open a window (default 7, capped at the needle's length)
    --min-run N       digits a frame INSIDE an open window must show to count (default 4)
    --ocr-width N     OCR at this width, boxes scaled back to source pixels (default 1920; 0 = native)
    --block N         frames a window grows by per step (default: the coarse step)
    --batch N         frames per OCR batch (default 64)
    --out <path>      hit map (default <job>/review/pii-scan.json for the job's own raw, the file place-blur.py reads;
                      review/pii-scan-<stem>.json for any video outside raw/, so sweeping a take or a draft never
                      replaces the raw's confirmed map, and for EACH raw of a job that plays several). The sheet sits
                      beside it, named for it: pii-hits[-<stem>]/. One map, so a sweep of several raws refuses it
    --no-sheet        skip the contact sheet

Exit 0 = clean sweep. Exit 1 = something was found (the boxes still have to be blurred and the sweep re-run clean).
Exit 2 = --still could not vouch for a still (missing, undecodable, or Vision read NO text on it: a blank grab is not a
clean one), there was nothing to look for, or the video is missing. Exit 3 = the OCR could not sweep: the shim did not
run, it could not read a frame of the sweep, ffmpeg could not hand one over, or ffprobe could not read the video (an
unread frame is never a clean one, so there is no verdict). A job that plays several raws is swept raw by raw: exit 1
when any of them shows a hit.

"Clean" means Vision READ nothing, never that nothing is there. A phone held up to the camera read 0 digits in 14 OCR
variants on 2026-09-21, and frame stacking recovered part of the number the next day: defocused or small text on a
camera-held screen is checked by eye, whatever this sweep says.

Why this exists (2026-09-19): a 52-minute 4K screen recording had two phone numbers on screen, and the ad-hoc sweep that
found them was rewritten twice for speed and twice for false hits — a full-resolution OCR of every frame of the RAW, a
window growth that re-read frames it had already read, and a digit-shape matcher that flagged a call UUID, a token count
and a clock. Four things that cost that time are the four things this tool does:

  1. It scans the CUT, not the raw. kept_spans() is hero-frame.py's, verbatim: a 52-minute source is 13 minutes of ship.
  2. It OCRs DOWNSCALED frames. Vision reads a 1920-wide frame in ~0.1 s and a 4K one in ~1.0 s, with the same hits;
     the boxes are scaled back to source pixels so a blur placer still gets real coordinates.
  3. It reads every frame at most ONCE (`self.boxes` is the memo, `scanned` is the covered set), so growing a window
     outward costs the new frames only.
  4. Needles are LITERAL. A seed needs --seed-run digits of the needle in a row (7 is ~1-in-10-million per text block);
     only INSIDE an open window does the looser --min-run apply, because a partial read there ("555-1", "3324" as the
     number is typed or scrolls off) is a real leak. Even there a short run is not enough on its own: the fragment
     has to be nothing but a piece of the needle, or a clock walks straight back in — one did, on the first version
     of this tool: "Fri Sep 18 4:37 PM" reads as 18437, and a ten-digit number easily contains 1843 somewhere.

Words and unknown numbers (2026-09-21): every first-round capture of a live-app job showed text that must not ship — a
churn figure, and the session's own staging prompts typed into the app — and none of it had a digit run to match, so
two job-local word sweeps were written beside this tool. --phrase and --any-number are those sweeps, and --still is the
pre-take gate screen-record.sh --preflight runs on a window grab so a tainted take never rolls.

Every example in this file is a made-up 555 number, deliberately: a tool whose whole job is keeping a real string off
the screen does not carry one in its own source, and this file ships in the client package.

THE OUTPUT IS A CONTRACT with whatever blurs the boxes, so it is written in the shape a blur placer already eats:

    review/pii-scan.json       {"<source frame>": [[x0, y0, x1, y1, "the text that box carried"], …], …}

  · the key is the SOURCE frame index as a decimal string (frame 0 is the raw's first frame, no padding), and the
    frame number is what maps a hit onto a timeline — a placer reads its own clip in/out points and converts.
  · the box is four integers in SOURCE pixels — left, top, right, bottom, origin TOP-LEFT — whatever --ocr-width
    the sweep actually ran at; the fragment is the OCR text, kept so a hit can be judged without re-reading a frame.
  · EVERY frame the sweep read is a key, so a frame with an empty list means "read, nothing on it" — a placer drops
    those (`if v`) and interpolates short dropouts itself. A frame that was never read is simply absent: absence is
    not evidence, which is why the meta file records what the sweep covered.

    review/pii-scan.meta.json  the sweep itself: raw, needles, kept_only, fps, source size, ocr_width, seed/min run,
                               frames_read, hit_frames, and each window's frames, seconds and fragments.

Plus review/pii-hits/, a still per window with the boxes drawn on it. The hits are confirmed BY EYE off that sheet
before anything is blurred: same RANK-don't-choose discipline as hero-frame.py. macOS Vision does the OCR through an
inline Swift shim (the pattern workflows/window-grab.sh uses); it is compiled once per run, because
`swift file.swift` re-compiles on every call.
"""
import argparse, json, platform, re, shutil, subprocess, sys, tempfile, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.m4v', '.mxf', '.avi', '.MP4', '.MOV'}

SWIFT_OCR = r'''
import Foundation
import Vision
import CoreGraphics
import ImageIO

// One image path per line on stdin. One TSV row per text block, and one "-" row per file so a
// frame with no text is still recorded as scanned:  path \t x0 \t y0 \t x1 \t y1 \t text
while let line = readLine(strippingNewline: true) {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    // CGImageSource, not NSImage: NSImage re-renders at screen scale and moves the boxes.
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        FileHandle.standardError.write("cannot decode \(path)\n".data(using: .utf8)!)
        print("\(path)\t-\t-\t-\t-\t"); continue
    }
    let w = Double(img.width), h = Double(img.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false        // a phone number is not a word
    do {
        try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    } catch {                                  // never swallow: a silent throw reads as "no hits"
        FileHandle.standardError.write("ocr failed \(path): \(error)\n".data(using: .utf8)!)
        print("\(path)\t-\t-\t-\t-\t"); continue
    }
    for obs in (req.results ?? []) {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox                // normalised, origin bottom-left
        let text = top.string.replacingOccurrences(of: "\t", with: " ").replacingOccurrences(of: "\n", with: " ")
        print("\(path)\t\(Int(b.minX * w))\t\(Int((1 - b.maxY) * h))\t\(Int(b.maxX * w))\t\(Int((1 - b.minY) * h))\t\(text)")
    }
    print("\(path)\t-\t-\t-\t-\t")
}
'''


def digits(s):
    return re.sub(r'\D', '', s)


def common_run(a, b):
    """Longest run of digits the two share. Both arguments are digit-only strings."""
    best = 0
    for i in range(len(a)):
        for j in range(i + best + 1, len(a) + 1):
            if a[i:j] not in b:
                break
            best = j - i
    return best


def tokens(s):
    """A phrase or an OCR block as lower-case word/number tokens: whitespace and punctuation only separate, so
    "Draft-copy." and "draft copy" are the same two tokens. An apostrophe is DROPPED, not split on, so we're, we’re
    and the 'were' Vision sometimes reads for them are one token."""
    return re.findall(r'[^\W_]+', re.sub(r"['’‘`´]", '', unicodedata.normalize('NFKC', s).lower()))


def reading_order(boxes):
    """Box indices top-to-bottom, left-to-right. A block joins the current line while its vertical centre sits
    above the bottom of the line's first block, so blocks a pixel apart on one line are not read out of order."""
    order = sorted(range(len(boxes)), key=lambda i: boxes[i][1] + boxes[i][3])
    lines = []
    for i in order:
        if lines and (boxes[i][1] + boxes[i][3]) / 2 <= boxes[lines[-1][0]][3]:
            lines[-1].append(i)
        else:
            lines.append([i])
    return [i for line in lines for i in sorted(line, key=lambda i: boxes[i][0])]


def columns(boxes):
    """Box-index chains that read DOWN one column: each block followed by the nearest block directly below it (their
    x ranges overlap, and the gap between them is at most a line height). The reading-order join runs the full width
    of the frame, so beside a sidebar a wrapped line reads 'files managed | quarterly | tick 14.txt | by "Google
    Drive"' and the phrase is lost (live, 2026-09-23); a chain keeps the column's lines together. Only chains of two
    or more blocks come back: a lone block is already read, whole, in the reading-order join."""
    below = {}
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if j == i or (b[1] + b[3]) / 2 <= a[3] or min(a[2], b[2]) <= max(a[0], b[0]):
                continue                                  # not below it, or not in its column
            if b[1] - a[3] > max(a[3] - a[1], b[3] - b[1]):
                continue                                  # a paragraph break away, or further
            if i not in below or b[1] < boxes[below[i]][1]:
                below[i] = j
    fed = set(below.values())
    chains = []
    for i in reading_order(boxes):
        if i in fed or i not in below:
            continue
        chain = [i]
        while chain[-1] in below:                         # strictly downward, so a chain always ends
            chain.append(below[chain[-1]])
        chains.append(chain)
    return chains


def phrase_hits(boxes, phrases):
    """{box index: {phrase, …}} for every block that carries a phrase's tokens. The frame's blocks are joined in
    reading order, and each column's blocks are joined top to bottom (columns()), so a phrase inside one block, a
    phrase that wraps into the next block, and one that wraps beside a sidebar are the same search; phrases are token
    lists (tokens() of the phrase).

    A phrase is TEXT FROM THE START OF A WORD, the way the job-local grep sweeps it replaced read a stem: its end may
    stop inside a word, so 'cancell' catches cancelled and cancelling and 'member' catches members, while its start
    and every word before its last are whole, so 'sign in' never fires on 'design in' and 'filming a demo' never on
    'filming about demos'. Whole tokens only missed all 77 churn-line frames of a rejected 2026-09-21 take ('cancell')."""
    if not phrases:
        return {}
    found = {}
    for order in [reading_order(boxes)] + columns(boxes):
        spans, words, at = [], [], 0          # spans: (first char, end char, box) of each token in the joined text
        for i in order:
            for t in tokens(boxes[i][4]):
                spans.append((at, at + len(t), i)); words.append(t); at += len(t) + 1
        text = ' '.join(words)
        for want in phrases:
            needle = ' '.join(want)
            k = text.find(needle)
            while k >= 0:
                if k == 0 or text[k - 1] == ' ':
                    for a, b, i in spans:
                        if a < k + len(needle) and b > k:
                            found.setdefault(i, set()).add(needle)
                k = text.find(needle, k + 1)
    return found


CLOCK = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?m\b\.?)?', re.I)
BREAK = re.compile(r'[^\w\s+().\-–—]')                  # never inside a phone number: , : / $ # % · | …
NUMERIC = re.compile(r'\+?[\d().\-–—]*\d[\d().\-–—]*')     # digits joined by - . ( ) and a leading +
DATE = re.compile(r'\d{4}[-.–]\d{1,2}[-.–]\d{1,2}|\d{1,2}[-.]\d{1,2}[-.](?:\d{2}|\d{4})|(?:19|20)\d\d[-–—](?:19|20)\d\d')
CALENDAR = re.compile(r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|'
                      r'sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|mon(?:day)?|tue(?:s(?:day)?)?|'
                      r'wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\.?', re.I)
DAY_YEAR = re.compile(r'\d{1,2}(?: (?:19|20)\d\d)?')
LEAD = re.compile(r'\+?[\d().\-–—]*\d')                    # the numeric head of a token with letters glued on
TAIL = re.compile(r'\d[\d().\-–—]*$')                      # ... and its numeric tail
INNER = re.compile(r'[\d().\-–—]*\d[\d().\-–—]*')          # ... and every numeric run inside it
STAMP = re.compile(r'(?<!\d)(?:19|20)\d\d(-?)(?:0[1-9]|1[0-2])\1(?:0[1-9]|[12]\d|3[01])'
                   r'(?:[_\-T.]?[0-2]\d[0-5]\d(?:[0-5]\d(?:\d{3})?)?)?(?!\d)')
# a camera or screenshot file's date-time: IMG_20260919_101700, PXL_20260919_101700123, Screenshot_2026-09-19_101700
UUID = re.compile(r'(?<![0-9])[0-9a-z]{8}(?:-[0-9a-z]{4}){3}-[0-9a-z]{12}(?![0-9])', re.I)
# the 8-4-4-4-12 shape, any letters: Vision reads a UUID's 0 as O ('cOffee1a-2470-…'). Letters may touch it on either
# side: RapidOCR (Windows) drops the spaces of a plain font, 'Call ID c0ffee1a-…' read as 'Call1Dc0ffee1a-…', and a
# letter-fenced shape made the UUID's '2470-4193-9235' a 12-digit phone number (2026-10-13); only a digit glued on
# can make the shape part of a longer number
SEP = re.compile(r'[().\-–—_]+')                             # a spaced separator: 555 - 184 - 3324, or 555_184_3324


def inner(mid):
    """The numeric runs inside a token's letters, each only when a separator or the token's edge (never a letter)
    sits on BOTH sides of its digits: 'lead-555-184-3324.txt' -> ['lead-', '555-184-3324', '.txt'] (a prefixed
    file name passed as clean, 2026-09-23). A run glued to a letter stays word: the UUID's '9235-1184ab'. A camera
    date-time is blanked out first, never the run beside it: 'call-2026-09-23-555-184-3324.mp3' keeps its number."""
    out, k = [], 0
    bare = STAMP.sub(lambda m: '_' * len(m.group()), mid)
    for m in INNER.finditer(bare):
        a = m.start() + re.search(r'\d', m.group()).start()
        b = m.start() + len(m.group().rstrip('().-–—'))
        if (a and bare[a - 1].isalpha()) or (b < len(bare) and bare[b].isalpha()):
            continue
        out += [mid[k:a], mid[a:b]]
        k = b
    return [p for p in out + [mid[k:]] if p]


def glued(tok):
    """A whitespace token split where letters meet digits: '555-184-3324.txt' -> ['555-184-3324', '.txt'],
    'Phone555-184-3324' -> ['Phone', '555-184-3324']. Skipping the whole token hid a number named as a file from the
    live preflight (2026-09-23). Digits INSIDE letters stay a word unless separators fence them (inner()); a UUID is
    one word, never split, since its all-digit groups ('38417502-8841-', '-2470-4193-') are an ID, not a number (a
    call ID failed the preflight, 2026-09-23); only what is glued on outside it is split."""
    u = UUID.search(tok)
    if u:
        return [p for p in glued(tok[:u.start()]) + [u.group()] + glued(tok[u.end():]) if p]
    if not tok:
        return []
    if NUMERIC.fullmatch(tok):
        return [tok]
    head = LEAD.match(tok)
    head = head.group() if head else ''
    tail = TAIL.search(tok, len(head))
    tail = tail.group() if tail else ''
    mid = tok[len(head):len(tok) - len(tail)]
    return [p for p in [head] + inner(mid) + [tail] if p]


def phone_runs(text):
    """The digits of every phone-shaped run in one OCR block: numeric tokens (digits joined by - . ( ) and a leading
    +) in a row, whitespace or a spaced separator between them ('(555) 184 - 3324' is one run). A clock is cut out
    first and anything else — a colon, a comma, a slash, a $, a letter glued on — ends the run, so 4:37 PM,
    $2,470.00, 09/19/2026, a UUID or a v2.4.70 never add up to a number; the digits on either side of a glued letter
    still count (glued()). Dates are dropped by shape: an ISO date, a year range (spaced or not), and a day (and
    year) after a month or weekday name (Sep 18 2026) — never a longer run after one, because "Call Jan 555-0199" is
    a name, not a date."""
    def num(t):
        return NUMERIC.fullmatch(t) and not DATE.fullmatch(t)

    runs = []
    for piece in BREAK.split(CLOCK.sub('|', text)):
        toks = [p for tok in piece.split() for p in glued(tok)]
        i = 0
        while i < len(toks):
            if not num(toks[i]):
                i += 1
                continue
            j = i
            while j < len(toks) and (num(toks[j]) or (SEP.fullmatch(toks[j]) and j + 1 < len(toks)
                                                          and num(toks[j + 1]))):
                j += 1
            run = toks[i:j]
            if not (i and CALENDAR.fullmatch(toks[i - 1]) and DAY_YEAR.fullmatch(' '.join(run))) \
                    and not DATE.fullmatch(''.join(run).replace('_', '-')):
                runs.append(''.join(digits(t) for t in run))
            i = j
    return runs


def compile_shim(work):
    """The OCR shim as a command. macOS: the Vision shim, compiled ONCE per run (`swift <file>` re-compiles every call,
    25 s per batch on a 52-min job). Anywhere else: workflows/ocr_shim.py, RapidOCR speaking the same TSV protocol
    (proven on Windows 2026-09-27; this tool used to exit 3 off macOS)."""
    if platform.system() != 'Darwin':
        return ['uv', 'run', '-q', str(Path(__file__).resolve().parent / 'ocr_shim.py')]
    src, binary = work / 'piiocr.swift', work / 'piiocr'
    src.write_text(SWIFT_OCR, encoding='utf-8')
    subprocess.run(['swiftc', '-O', str(src), '-o', str(binary)], check=True)
    return [str(binary)]


def ocr_rows(binary, files):
    """[(path, box)] per text block Vision read, plus one (path, None) per file so an image with no text is still
    recorded as read; a box is [x0, y0, x1, y1, text] in the image's own pixels. Returns the shim's stderr too: a
    file it could not decode is named there."""
    out = subprocess.run(binary, input='\n'.join(str(p) for p in files), capture_output=True, text=True,
                         encoding='utf-8')
    if out.returncode and not out.stdout.strip():
        # the RapidOCR shim off macOS installs through uv on first use: a failed run read NOTHING, and nothing read
        # must never pass as clean (exit 3, "this machine cannot sweep")
        print(f'✗ the OCR shim failed (exit {out.returncode}): {(out.stderr or "").strip()[-300:]}', file=sys.stderr)
        raise SystemExit(3)
    rows = []
    for line in out.stdout.splitlines():
        cols = line.split('\t')
        if len(cols) < 6:                     # a torn row is skipped, never parsed positionally
            print(f'⚠ unparsable OCR row: {line[:80]!r}')
            continue
        rows.append((cols[0], None if cols[1] == '-' else [int(v) for v in cols[1:5]] + ['\t'.join(cols[5:])]))
    return rows, out.stderr


def played_raws(job):
    """The videos under raw/ the EDL plays (a cuts.json segment names it as its `clip`), or every video under raw/
    when there is no EDL or it names none of them."""
    vids = sorted(p for p in (job / 'raw').glob('*') if p.suffix in VIDEO_EXT)
    cuts = job / 'transcript' / 'cuts.json'
    named = {Path(s['clip']).name for s in json.loads(cuts.read_text(encoding='utf-8'))['segments']
             if s.get('clip')} if cuts.exists() else set()
    return [p for p in vids if p.name in named] or vids


def find_raws(job, raw_arg):
    """The videos to sweep: --raw, or EVERY raw the job plays (played_raws()). The first raw alone was the default, and
    on a camera + screen-recording job it swept the camera, said ✓ clean and never read the recording that showed the
    phone number (2026-10-13)."""
    if raw_arg:
        p = Path(raw_arg)
        return [p if p.is_absolute() else (job / p)]
    vids = played_raws(job)
    if not vids:
        print(f'✗ no video under {job / "raw"}; pass --raw')
        raise SystemExit(2)                    # sys.exit(<message>) is exit 1, the "found something" code
    return vids


def hit_map_path(job, raw):
    """The hit map a sweep writes without --out. The job's own raw (anything under raw/) keeps review/pii-scan.json,
    the file place-blur.py reads; any other video — a capture take, an exported draft — gets review/pii-scan-<stem>.json.
    One shared default meant every take sweep replaced the raw's confirmed map and emptied its sheet (2026-09-23).
    A job that plays SEVERAL raws gives each its own review/pii-scan-<stem>.json, so no raw's sweep replaces
    another's (place-blur.py --hits <map> blurs each).
    `raw` is the path as GIVEN: a multi-section sub-job's raw/ holds a SYMLINK to the parent's raw (rough-cut
    § Multi-section), whose target sits outside sections/<name>/raw/ and is still that section's raw. Only its folder
    is resolved (so /tmp and /private/tmp agree), never the file itself."""
    home = (job / 'raw').resolve()
    if ((raw.parent.resolve() / raw.name).is_relative_to(home) or raw.resolve().is_relative_to(home)) \
            and len(played_raws(job)) < 2:
        return job / 'review' / 'pii-scan.json'
    return job / 'review' / f'pii-scan-{raw.stem}.json'


def sheet_dir(out):
    """The contact sheet's folder, beside its hit map and named for it: pii-scan.json -> pii-hits/, pii-scan-g4.json ->
    pii-hits-g4/, any other name -> pii-hits-<name>/. sheet() empties its folder first, so two maps never share one."""
    if out.stem == 'pii-scan':
        return out.parent / 'pii-hits'
    return out.parent / ('pii-hits-' + (out.stem[len('pii-scan-'):] if out.stem.startswith('pii-scan-') else out.stem))


def replaced_sweep(out, raw):
    """The video an existing hit map at `out` was swept from, when it is NOT this one: that map is about to be replaced."""
    try:
        was = json.loads(out.with_suffix('.meta.json').read_text(encoding='utf-8')).get('raw')
    except (OSError, ValueError, AttributeError):
        return None
    return was if was and was != str(raw) else None


def kept_spans(job, raw, use_all):
    cuts = job / 'transcript' / 'cuts.json'
    if use_all or not cuts.exists():
        if not use_all:
            print(f'⚠ no {cuts.name}: sweeping the WHOLE raw (slower, and it flags frames that never ship)')
        return None
    segs = json.load(open(cuts, encoding='utf-8'))['segments']
    spans = [(float(s['start']), float(s['end'])) for s in segs
             if not s.get('clip') or Path(s['clip']).name == raw.name]
    if not spans:
        print(f'⚠ no cuts.json segment names {raw.name}: sweeping the WHOLE raw')
        return None
    return sorted(spans)


def probe(raw):
    """(width, height, fps, duration, offset) of the first video stream. JSON, never csv: ffprobe 9 prints a timecoded
    file's video row twice in csv (once inside its tmcd "Track Reference" stream group; the whole output once read
    '10.000000\\n\\n1920' as the duration), and a Matroska or WebM stream has no duration of its own (csv 'N/A', which
    crashed the sweep with exit 1, the "found something" code). There the muxer's DURATION tag is read, which is the
    stream's END time (ffmpeg's and OBS's muxers write it), and only without one the container's duration, which runs
    to the audio's end and so can name a frame past the last (the sweep dies on that frame: last_frame()). `offset`
    is how far the video starts after the file does, which seek() needs. Width and height are AS DECODED: ffmpeg
    auto-rotates before the OCR scale, so an iPhone take coded 1920x1080 with a -90 matrix hands over 1080x1920 frames,
    and the coded size put every hit box 1.78x off and place-blur's crop off the frame (2026-10-13). Older ffprobe
    reports the turn as a `rotate` tag."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate,duration,start_time:stream_tags=DURATION,rotate'
                          ':stream_side_data=rotation:format=duration,start_time', '-of', 'json', str(raw)],
                         capture_output=True, text=True).stdout
    d = json.loads(out)
    s, f = d['streams'][0], d.get('format', {})
    num, _, den = s['r_frame_rate'].partition('/')
    fps = float(num) / float(den or 1)
    w, h = int(s['width']), int(s['height'])
    rot = next((sd['rotation'] for sd in s.get('side_data_list', []) if 'rotation' in sd),
               (s.get('tags') or {}).get('rotate', 0))
    if round(float(rot)) % 180:
        w, h = h, w
    start = float(s.get('start_time') or 0)
    offset = start - float(f.get('start_time') or 0)
    tag = (s.get('tags') or {}).get('DURATION')
    if s.get('duration'):
        dur = float(s['duration'])
    elif tag:
        hh, mm, ss = tag.split(':')
        dur = int(hh) * 3600 + int(mm) * 60 + float(ss) - start
    else:
        dur = float(f['duration']) - offset
    return w, h, fps, dur, offset


def last_frame(dur, fps):
    """The last frame's INDEX. A clip of N frames is 0..N-1: int(dur * fps) named frame N, which ffmpeg cannot hand
    over, and the sweep died on it whenever N was a multiple of the coarse step (every 5 s screen-record take)."""
    return max(0, round(dur * fps) - 1)


def seek(frame, fps, offset=0.0):
    """The -ss that makes ffmpeg's FIRST output frame this one. An input seek keeps the frames at or after the
    seek point, so it lands half a frame BEFORE the frame: the old (frame + 0.5) handed back frame + 1, and every key
    in the hit map named the frame before the one its boxes were read on. -ss counts from the FILE's start, so a video
    stream that starts `offset` s after it (probe()) is reached that much later: at 0.05 s a key held the frame two
    before it, past place-blur.py's one-frame union (2026-10-13)."""
    return f'{max(0.0, (frame - 0.5) / fps + offset):.6f}'


def targets(doc, needles, phrases, any_number):
    """Every --needle / --phrase / --any-number, plus the target file if there is one: a JSON list of needles, a JSON
    {"needles": [...], "phrases": [...], "any_number": N}, or any other file as phrases, one per line (# comments).
    Returns (needles, phrases, any_number)."""
    found, said = list(needles or []), list(phrases or [])
    if doc is not None and doc.exists():
        if doc.suffix.lower() == '.json':
            loaded = json.loads(doc.read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                found += list(loaded.get('needles') or [])
                said += list(loaded.get('phrases') or [])
                any_number = any_number or loaded.get('any_number')
            else:
                found += list(loaded)
        else:
            said += [s.strip() for s in doc.read_text(encoding='utf-8').splitlines()
                     if s.strip() and not s.lstrip().startswith('#')]
    # The needle matcher reads DIGITS. A needle with none of them used to be dropped with a warning, which handed back
    # a ✓ for a string nobody looked for; it is words, so it is swept as the words it is.
    for n in found:
        if not digits(n):
            print(f'⚠ needle {n!r} has no digits: swept as a --phrase (from the start of a word, case and punctuation '
                  f'ignored)')
            said.append(n)
    for n in found:
        if digits(n) and re.search(r'[A-Za-z]', n):
            print(f'⚠ needle {n!r} is matched through its DIGITS only ({digits(n)}): its letters are not compared '
                  f'(add it as a --phrase too to match the whole string)')
        if 0 < len(digits(n)) < 6:
            print(f'⚠ needle {n!r} carries only {len(digits(n))} digits: the seed run caps at the needle\'s own length, '
                  f'so every {len(digits(n))}-digit run on screen opens a window. Expect a noisy sheet.')
    for p in said:
        if not tokens(p):
            print(f'⚠ phrase {p!r} has no letters or digits: there is nothing in it to sweep for')
        elif re.search(r'[\\\[\]|*?^${}]', p):     # a grep term ported as-is: '$[0-9]' silently became the words "0 9"
            print(f'⚠ phrase {p!r} looks like a pattern, but a phrase is literal words with its punctuation ignored: '
                  f'it is swept as "{" ".join(tokens(p))}"')
    return [n for n in found if digits(n)], [p for p in said if tokens(p)], (int(any_number) if any_number else None)


class Sweep:
    """raw is None for --still: only the compiled shim and the matcher are used."""

    def __init__(self, raw, fps, src_w, ocr_w, needles, seed_run, min_run, batch, work, phrases=(), any_number=None,
                 offset=0.0, last=None):
        self.raw, self.fps, self.src_w, self.ocr_w, self.offset, self.last = raw, fps, src_w, ocr_w, offset, last
        self.needles = [digits(n) for n in needles]
        self.phrases, self.any_number = [tokens(p) for p in phrases], any_number
        self.seed_run, self.min_run, self.batch, self.work = seed_run, min_run, batch, work
        self.boxes, self.scanned, self.ocr_calls = {}, set(), 0
        self.bin = compile_shim(work)

    def match(self, frag, run):
        """A fragment shows the needle when the whole number is in it, when it shares a long run with it, or when
        the fragment is nothing BUT a view of it. That last clause is what keeps a clock out: a time that reads as
        18437 may share the run 1843 with the needle, but 18437 is not a piece of it — it only overlaps one."""
        f = digits(frag)
        if not f:
            return False
        for n in self.needles:
            if n in f:
                return True
            best = common_run(f, n)
            if best >= min(self.seed_run, len(n)):        # long enough to be the number itself, OCR garble and all
                return True
            if best < min(run, len(n)):
                continue
            short = f[1:] if f[:1] == '1' and f[1:] and f[1:] in n else f   # a leading country code is not a stranger
            if short in n:
                return True
        return False

    def explain(self, boxes, run):
        """[(box, [why, …])] for every block of one frame that must not ship: a digit needle, a phrase (read across
        the frame's blocks, so it needs the whole frame), or a phone-shaped number of --any-number digits."""
        said, out = phrase_hits(boxes, self.phrases), []
        for i, b in enumerate(boxes):
            why = [f'phrase "{p}"' for p in sorted(said.get(i, ()))]
            if self.match(b[4], run):
                why.append('needle')
            if self.any_number:
                why += [f'a {len(r)}-digit number' for r in phone_runs(b[4]) if len(r) >= self.any_number]
            if why:
                out.append((b, why))
        return out

    def hit(self, frame, run):
        return [b for b, _ in self.explain(self.boxes.get(frame, []), run)]

    def extract(self, frames):
        """Frames -> jpgs named for their SOURCE frame number, contiguous runs in one ffmpeg call."""
        shot = self.work / 'frames'
        if shot.exists():
            shutil.rmtree(shot)
        shot.mkdir(parents=True)
        runs, start = [], None
        for i, f in enumerate(frames):
            if start is None:
                start = f
            if i + 1 == len(frames) or frames[i + 1] != f + 1:
                runs.append((start, f)); start = None
        for a, b in runs:
            vf = f'scale={self.ocr_w}:-2' if self.ocr_w else None
            # passthrough sync: the default constant-rate sync duplicated a run's first frame on any file with audio,
            # so key k held frame k-1 and the run's last frame was never read (2026-10-13). Its frames keep their own
            # timestamps, half a frame off the seek, and on a millisecond clock (Matroska, WebM) two of them rounded
            # onto one tick of the default 1/fps encoder clock and the jpeg encoder refused the run: a microsecond
            # clock never rounds two frames together
            cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', seek(a, self.fps, self.offset), '-i', str(self.raw),
                   '-frames:v', str(b - a + 1), *passthrough(), '-enc_time_base', '1:1000000']
            if vf:
                cmd += ['-vf', vf]
            cmd += ['-q:v', '3', '-start_number', str(a), str(shot / 'f%08d.jpg')]   # zero-padded: the name IS the frame
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode == 0:
                continue
            # A run at the very end that ffmpeg hands nothing for lies past the video's last frame: a stream copy cut
            # with -ss leaves an edit list whose duration runs a frame or two past the last picture (an iPhone take cut
            # on Windows, 2026-10-13: 20.018 s, last frame at 19.973), and that frame's seek wrote nothing and crashed
            # the sweep with a traceback and exit 1, the "found something" code. Nothing is on screen there. Anything
            # else ffmpeg cannot hand over is no verdict.
            if self.last is not None and b >= self.last - 2 \
                    and not any((shot / f'f{n:08d}.jpg').exists() for n in range(a, b + 1)):
                print(f'  · frame {a}{f"-{b}" if b > a else ""} is past the last frame of {self.raw.name}: nothing on '
                      'screen to read there', file=sys.stderr)
                continue
            print(f'✗ ffmpeg could not hand over frames {a}-{b} of {self.raw.name} (exit {r.returncode}): no verdict\n  '
                  + (r.stderr or '').strip()[-400:], file=sys.stderr)
            raise SystemExit(3)
        return shot

    def ocr(self, frames):
        """OCR every frame not already read. The memo is the whole point: window growth re-reads nothing."""
        todo = sorted(f for f in frames if f not in self.scanned)
        if not todo:
            return
        for i in range(0, len(todo), self.batch):
            chunk = todo[i:i + self.batch]
            shot = self.extract(chunk)
            files = sorted(shot.glob('f*.jpg'))
            if not files:
                self.scanned.update(chunk)
                continue
            rows, err = ocr_rows(self.bin, files)
            # A frame the OCR names as NOT read still gets its "-" row (the shims' protocol), and a "-" row is "read,
            # nothing on it": a sweep that read past it would call a frame it never saw clean. It did on the Windows
            # re-test (2026-09-27): a shim process whose OCR failed on every image put 34 frames that showed the needle
            # into the hit map as [] (86 hit frames reported, 120 on screen). Every frame read, or no verdict at all.
            unread = [l for l in err.splitlines() if l.startswith(('ocr failed ', 'cannot decode '))]
            # every file ends on its own "-" row; one with none was never reached (a shim that died part way through
            # the batch prints nothing for the rest), so it is unread too, never a clean frame (review, 2026-09-27)
            done = {path for path, box in rows if box is None}
            unread += [f'no row for {f} (the OCR stopped before it)' for f in files if str(f) not in done]
            if unread:
                print(f'✗ the OCR could not read {len(unread)} frame(s), and a frame it never read is not a clean one: '
                      f'no verdict, re-run the sweep\n  ' + '\n  '.join(unread[:5]), file=sys.stderr)
                raise SystemExit(3)
            self.ocr_calls += len(files)
            scale = self.src_w / self.ocr_w if self.ocr_w else 1.0
            for path, box in rows:
                frame = int(Path(path).stem[1:])
                self.scanned.add(frame)
                if box is None:
                    self.boxes.setdefault(frame, [])
                    continue
                self.boxes.setdefault(frame, []).append([int(round(v * scale)) for v in box[:4]] + [box[4]])
            self.scanned.update(chunk)                # a frame ffmpeg could not hand over is still read-once


def windows(seeds, gap):
    out = []
    for f in sorted(seeds):
        if out and f - out[-1][1] <= gap:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


def merge(wins):
    out = []
    for lo, hi in sorted(wins):
        if out and lo <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return out


def allowed(spans, fps, last):
    if spans is None:
        return lambda f: 0 <= f <= last
    bounds = [(int(a * fps), min(last, int(b * fps))) for a, b in spans]
    return lambda f: any(a <= f <= b for a, b in bounds)


def grow(sweep, win, ok, block):
    """Per-frame inside the window, then outward a block at a time until a block reads clean."""
    lo, hi = win
    sweep.ocr([f for f in range(lo, hi + 1) if ok(f)])
    while True:
        blk = [f for f in range(lo - block, lo) if ok(f)]
        if not blk:
            break
        sweep.ocr(blk)
        found = [f for f in blk if sweep.hit(f, sweep.min_run)]
        if not found:
            break
        lo = min(found)
    while True:
        blk = [f for f in range(hi + 1, hi + 1 + block) if ok(f)]
        if not blk:
            break
        sweep.ocr(blk)
        found = [f for f in blk if sweep.hit(f, sweep.min_run)]
        if not found:
            break
        hi = max(found)
    return [lo, hi]


def sheet(raw, sweep, boxes_at, hits, wins, out_dir):
    """A still per window with the matched boxes drawn on it, then one contact sheet."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    stills = []
    for lo, hi in wins:
        inside = [f for f in hits if lo <= f <= hi]
        if not inside:
            continue
        mid = inside[len(inside) // 2]
        draw = ','.join(f'drawbox=x={b[0]}:y={b[1]}:w={b[2] - b[0]}:h={b[3] - b[1]}:color=red@1:t=6'
                        for b in boxes_at(mid))
        still = out_dir / f'f{mid:08d}.jpg'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', seek(mid, sweep.fps, sweep.offset),
                        '-i', str(raw), '-frames:v', '1', *passthrough(), '-vf', f'{draw},scale=960:-2', '-q:v', '3',
                        str(still)], check=True)
        stills.append(still)
    if not stills:
        return out_dir
    cols = min(3, len(stills))
    rows = -(-len(stills) // cols)
    # Every still named as its own input, in window order, never `-pattern_type glob`: that is libc glob(), which the
    # Windows ffmpeg builds do not have ("globbing is not supported by this libavformat build"), so the first sweep
    # that FOUND something on Windows died here, after the hit map was written and before the verdict (2026-09-27)
    ins = [arg for s in stills for arg in ('-i', str(s))]
    chain = ''.join(f'[{i}:v]' for i in range(len(stills))) + f'concat=n={len(stills)}:v=1:a=0,'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *ins, '-frames:v', '1', '-filter_complex',
                    f'{chain}tile={cols}x{rows}:padding=6:color=black', '-q:v', '4', str(out_dir / 'sheet.jpg')],
                   check=True)
    return out_dir / 'sheet.jpg'


NOT_PROOF = ('  "clean" means the OCR READ nothing, not that nothing is there: defocused or small text can still be '
             'recovered by frame stacking (2026-09-22), so a hit-free sweep of a camera-held screen is not proof')


def stills(sweep, paths):
    """--still: OCR each image at its own size, print every flagged block and why, exit 1 on any. A still Vision read
    NO text on is exit 2, never 0: a blank or undecodable grab (no Screen Recording permission, a minimized window)
    vouches for nothing, and a pre-take gate that passed one would roll the take on a guess."""
    files = [Path(p).resolve() for p in paths]
    gone = [str(p) for p in files if not p.is_file()]
    if gone:
        print(f'✗ no such still: {", ".join(gone)}')
        return 2
    read = {str(p): [] for p in files}
    rows, err = ocr_rows(sweep.bin, files)
    for line in err.splitlines():
        print(f'⚠ {line}')
    for path, box in rows:
        if box is not None:
            read.setdefault(path, []).append(box)
    hits, blank = 0, []
    for path, boxes in read.items():
        flagged = sweep.explain(boxes, sweep.seed_run)
        print(f'{Path(path).name}: {len(boxes)} text block(s) read, {len(flagged)} flagged')
        for b, why in flagged:
            print(f'  ✗ [{b[0]},{b[1]},{b[2]},{b[3]}] {b[4]!r}  <- {", ".join(why)}')
        hits += len(flagged)
        if not boxes:
            blank.append(Path(path).name)
    if hits:
        print(f'✗ {hits} block(s) on screen that must not ship')
        return 1
    if blank:
        print(f'✗ Vision read NO text on {", ".join(blank)}: a blank grab is not a clean one (minimized window? '
              f'no Screen Recording permission?)')
        return 2
    print('✓ clean: nothing flagged on the still(s)')
    print(NOT_PROOF)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job', nargs='?'); ap.add_argument('--needle', action='append'); ap.add_argument('--raw')
    ap.add_argument('--phrase', action='append'); ap.add_argument('--any-number', type=int)
    ap.add_argument('--pii'); ap.add_argument('--still', nargs='+')
    ap.add_argument('--all', action='store_true'); ap.add_argument('--coarse', type=float, default=2.0)
    ap.add_argument('--seed-run', type=int, default=7); ap.add_argument('--min-run', type=int, default=4)
    ap.add_argument('--ocr-width', type=int, default=1920); ap.add_argument('--block', type=int)
    ap.add_argument('--batch', type=int, default=64); ap.add_argument('--out')
    ap.add_argument('--no-sheet', action='store_true')
    a = ap.parse_args()
    if not a.job and not a.still:
        ap.error('the job folder is required (only --still runs without one)')
    if a.any_number is not None and a.any_number < 1:
        ap.error('--any-number takes a digit count, 1 or more')
    job = Path(a.job).resolve() if a.job else None
    doc = Path(a.pii) if a.pii else (job / 'pii.json' if job else None)
    if a.pii and not doc.is_file():
        print(f'✗ no target file at {doc}')
        return 2
    needles, phrases, any_number = targets(doc, a.needle, a.phrase, a.any_number)
    if not (needles or phrases or any_number):
        print('✗ nothing to look for: pass --needle "<the literal string>" / --phrase "<words>" / --any-number N '
              '(repeatable), or --pii <file> / projects/<job>/pii.json')
        return 2
    if a.still:
        with tempfile.TemporaryDirectory(prefix='pii-scan-') as tmp:
            return stills(Sweep(None, 0, 0, 0, needles, a.seed_run, a.min_run, a.batch, Path(tmp), phrases, any_number),
                          a.still)
    givens = find_raws(job, a.raw)             # unresolved: a section's symlinked raw is still under its raw/
    if a.out and len(givens) > 1:
        print(f'✗ --out names ONE hit map, and this job plays {len(givens)} raws '
              f'({", ".join(g.name for g in givens)}): pass --raw with it')
        return 2
    probed = []
    for given in givens:                       # every raw is checked before any is swept: no half-swept verdict
        raw = given.resolve()
        if not raw.is_file():                  # probe() would crash with exit 1, the "found something" code
            print(f'✗ no such video: {given} (a relative --raw is read from the job folder)')
            return 2
        try:
            probed.append((given, raw, probe(raw)))
        except (ValueError, KeyError, IndexError, ZeroDivisionError) as e:   # unreadable: no verdict, never "found"
            print(f'✗ ffprobe could not read {raw.name} ({e!r}): nothing was swept, no verdict', file=sys.stderr)
            return 3
    if needles:
        print(f'needles: {", ".join(needles)}   seed {a.seed_run} digits · inside a window {a.min_run}')
    if phrases:
        print(f'phrases: {"; ".join(phrases)}')
    if any_number:
        print(f'any number: a phone-shaped run of {any_number}+ digits')
    if len(probed) > 1:
        print(f'this job plays {len(probed)} raws: each is swept into its own map')
    found = []
    for given, raw, (src_w, src_h, fps, dur, offset) in probed:
        out = Path(a.out) if a.out else hit_map_path(job, given)
        hits = sweep_raw(job, raw, src_w, src_h, fps, dur, offset, out, a, needles, phrases, any_number)
        if hits:
            found.append((raw, hits, out))
    if len(probed) > 1:
        for raw, hits, out in found:
            print(f'✗ {raw.name}: {hits} hit frame(s) -> {out}   (Premiere: place-blur.py --hits that map)')
    if found:
        print('✗ the cut shows something it must not: blur the boxes, then re-run until this sweep is clean')
        return 1
    print('✓ clean: no needle on screen in the scanned range')
    print(NOT_PROOF)
    return 0


def sweep_raw(job, raw, src_w, src_h, fps, dur, offset, out, a, needles, phrases, any_number):
    """Sweep one video into the hit map at `out` (and its meta and sheet). Returns its hit frame count."""
    spans = kept_spans(job, raw, a.all)
    last = last_frame(dur, fps)
    ok = allowed(spans, fps, last)
    step = max(1, round(fps / a.coarse))
    block = a.block or step
    was = replaced_sweep(out, raw)
    if was:
        print(f'⚠ {out} holds the sweep of {was}: this sweep of {raw.name} REPLACES it (pass --out to keep both)')
    coarse = [f for f in range(0, last + 1, step) if ok(f)]
    covered = sum(b - a_ for a_, b in spans) if spans else dur
    print(f'{raw.name}  {src_w}x{src_h} @ {fps:.3f} fps  ·  {covered:.0f}s of {dur:.0f}s '
          f'({"kept spans" if spans else "whole raw"})  ·  coarse {len(coarse)} frames at {a.coarse} fps')

    with tempfile.TemporaryDirectory(prefix='pii-scan-') as tmp:      # unique per run: two sweeps cannot share a shim
        work = Path(tmp)
        sweep = Sweep(raw, fps, src_w, a.ocr_width, needles, a.seed_run, a.min_run, a.batch, work, phrases, any_number,
                      offset, last)
        sweep.ocr(coarse)
        seeds = [f for f in coarse if sweep.hit(f, a.seed_run)]
        print(f'coarse pass: {len(seeds)} seed frame(s)')
        grown = [grow(sweep, w, ok, block) for w in windows(seeds, 2 * step)]
        wins = merge(grown)
        # The loose --min-run only ever applies INSIDE an open window; a lone 4-digit read out in the
        # middle of nowhere is a clock, which is what the ad-hoc matcher kept flagging.
        inside = {f for lo, hi in wins for f in range(lo, hi + 1)}
        boxes_at = lambda f: sweep.hit(f, a.min_run if f in inside else a.seed_run)
        hits = sorted(f for f in sweep.scanned if boxes_at(f))
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump({str(f): boxes_at(f) for f in sorted(sweep.scanned)}, fh)
        meta = dict(raw=str(raw), needles=needles, kept_only=bool(spans), fps=fps, source=[src_w, src_h],
                    ocr_width=a.ocr_width or src_w, seed_run=a.seed_run, min_run=a.min_run, coarse_fps=a.coarse,
                    frames_read=len(sweep.scanned), hit_frames=len(hits),
                    windows=[dict(frames=[lo, hi], seconds=[round(lo / fps, 3), round(hi / fps, 3)],
                                  fragments=sorted({b[4] for f in range(lo, hi + 1) for b in boxes_at(f)}))
                             for lo, hi in wins], phrases=phrases, any_number=any_number)
        # with_suffix, not a string replace: `--out sweep` (no .json) would otherwise write the meta OVER the hit map
        out.with_suffix('.meta.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
        for w in meta['windows']:
            print(f"  {w['seconds'][0]:>9.3f} – {w['seconds'][1]:<9.3f}s  frames {w['frames'][0]}–{w['frames'][1]:<7}"
                  f"  {'; '.join(w['fragments'])[:70]}")
        if hits and not a.no_sheet:
            print(f'sheet -> {sheet(raw, sweep, boxes_at, hits, wins, sheet_dir(out))}   (confirm BY EYE before blurring)')
        print(f'{sweep.ocr_calls} frames read · {len(hits)} hit frame(s) in {len(wins)} window(s) -> {out}')
    return len(hits)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit as e:
        raise SystemExit(3 if isinstance(e.code, str) and e.code.startswith('[pii-scan] macOS only') else e.code)
