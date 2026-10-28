"""pes.py: the ONE Python runner for the Premiere bridge.

    from pes import es, paged, es_lit
    from job_guard import require_job_project

    require_job_project(es, job)                       # es = the bridge runner, as the guard expects
    seq = json.loads(es('(function(){ ... })()'))
    clips = paged(lambda n0, n1: '(function(){ ... slice %d..%d ... })()' % (n0, n1))
    es('(function(){ var PATH = %s; ... })()' % es_lit(path))   # every name or path written into a script

Every call goes through `premiere-bridge.mjs es`, which owns the bridge's output contract (the
command's own comment carries it): one line of stdout, a runtime failure as `ERROR: <message> @
line <n>` with a non-zero exit, a result at or over the CEP return cap named as the cap, and a
timeout the caller passes instead of the panel's 45 s default.

Why (2026-09-19): six lane scripts each grew their OWN `def es`, every one a different guess at an
undocumented contract — a plain `json.loads` that died on any leading line, two backwards line scans
with a blind retry, a `rfind("\\n{")` with no error check at all, and a seventh copy inside a job
folder. The same session lost three round-trips to a 64 KB readback that came back as truncated JSON
rather than an error, and read a good 4.93 GB export as a failure because nobody could pass a
timeout. One runner, one contract, one place to fix the next surprise.
"""
import glob, json, os, re, subprocess, sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
WAV_EPR = 'Wave48mono24.epr'


def es_lit(v):
    """`v` written into a script: json.dumps, with every '.', '(' and '_' inside a string as a \\u escape, which
    ExtendScript reads back as the same character. The MCP Bridge panel refuses, as a bare "Script validation
    failed", any script whose TEXT holds process. / eval( / require( / new Function( / __dirname / __filename /
    child_process, string literals included, so a media file named "Editing Process.MP4" failed every script that
    named it (audit, 2026-10-13). Numbers are untouched. premiere-bridge.mjs's esLit (bridge-lib.mjs) is the same."""
    return re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: re.sub(r'[._(]', lambda c: '\\u%04x' % ord(c.group()), m.group()),
                  json.dumps(v))


def wav_preset():
    """The installed Premiere's own WAV bounce preset (48 kHz mono 24-bit), found, never typed.

    A hard-coded '/Applications/Adobe Premiere Pro 2026/...' path died on every other year's install
    and on Windows. Order: PREMIERE_WAV_PRESET (a named path that is missing exits, never falls through);
    macOS: the RUNNING Premiere's bundle (the one the bridge drives; premiere-pid.sh's match, Beta
    excluded), else the newest non-Beta install under /Applications; Windows: the newest non-Beta
    install under C:/Program Files/Adobe.

    On Windows the path comes back in BACKSLASHES only: exportAsMediaDirect answers "Unknown Error" to a preset path
    with a forward slash anywhere in it, and glob joined its matches onto the forward-slashed ProgramFiles prefix, so
    every bounce (cut-proof, audio-polish --bounce, place-music --bounce) failed on the Windows re-test (Premiere
    26.5.1, 2026-09-27). The output path has the same rule ("Unable to initialize export!"): pass it as str(Path).
    The QE frame grab has it too (premiere-bridge.mjs frame)."""
    native = os.path.normpath if os.name == 'nt' else (lambda p: p)
    env = os.environ.get('PREMIERE_WAV_PRESET')
    if env:
        if os.path.isfile(env):
            return native(env)
        sys.exit(f'PREMIERE_WAV_PRESET={env} does not exist')
    if sys.platform == 'darwin':
        try:
            ps = subprocess.run(['ps', '-axo', 'comm='], capture_output=True, text=True).stdout
        except FileNotFoundError:
            ps = ''
        for line in ps.splitlines():
            line = line.strip()
            if re.search(r'/Contents/MacOS/Adobe Premiere Pro[^/]*$', line) and 'Beta' not in line:
                p = line.split('/Contents/MacOS/')[0] + '/Contents/Settings/EncoderPresets/' + WAV_EPR
                if os.path.isfile(p):
                    return p
        pat = '/Applications/Adobe Premiere Pro*/Adobe Premiere Pro*.app/Contents/Settings/EncoderPresets/' + WAV_EPR
    elif os.name == 'nt':
        pf = os.environ.get('ProgramFiles', 'C:/Program Files').replace('\\', '/')
        pat = pf + '/Adobe/Adobe Premiere Pro*/Settings/EncoderPresets/' + WAV_EPR
    else:
        pat = None
    hits = sorted(p for p in glob.glob(pat) if 'Beta' not in p) if pat else []
    if hits:
        return native(hits[-1])
    sys.exit(f'no Premiere {WAV_EPR} found: set PREMIERE_WAV_PRESET to its full path')


_seen_size = {}


def lsof_open(path):
    """Does any process still hold the file open? With no lsof (Windows) the file counts as open until its size
    holds across two polls: a bare False let a bounce wait break on the first poll past 1 KB (2026-09-27)."""
    try:
        r = subprocess.run(['lsof', '--', str(path)], capture_output=True, text=True)
    except FileNotFoundError:
        size = os.path.getsize(path)
        prev = _seen_size.get(str(path))
        _seen_size[str(path)] = size
        return prev != size
    return r.returncode == 0 and bool(r.stdout.strip())


def _why(err, out):
    """The one line worth printing out of a failed call: node prints a whole stack under its message
    and the bridge logs [INFO] lines beside it, so neither the first nor the last line is the cause."""
    lines = [l.rstrip() for l in (err or '').splitlines() if l.strip()]
    for l in lines:
        if l.startswith(('Error:', 'ERROR:', 'bridge error', 'result hit', 'es:')):
            return l
    for l in lines:
        if '] [ERROR] [' in l:
            return l.split('] ', 2)[-1]
    return out or (lines[-1] if lines else 'no output')


def es(script, timeout=None, job=None):
    """One ExtendScript through the bridge -> its single line of output, verbatim.

    `timeout` is milliseconds and reaches the CEP panel's own watchdog, so a long write (an export,
    a several-hundred-clip pass) returns its real result instead of "timed out after 45000ms".
    A bridge failure, an `ERROR:` from the script, or a result over the return cap exits the run:
    a lane script that keeps going on a half-answer writes the damage.

    `job` runs the bridge's active-project guard on THIS call. A lane script normally leaves it
    unset and guards ONCE at startup with job_guard.require_job_project (the same check, one
    round-trip instead of one per call) — so es passes `--no-guard`, which the bridge requires
    rather than letting the guard be skipped by forgetting it."""
    cmd = ['node', str(BRIDGE), 'es', '--job', str(job)] if job else ['node', str(BRIDGE), 'es', '--no-guard']
    if timeout:
        cmd += ['--timeout', str(int(timeout))]
    r = subprocess.run(cmd + [script], capture_output=True, text=True)
    out = (r.stdout or '').strip()
    if r.returncode:
        sys.exit(f'bridge: {_why(r.stderr, out)}')
    return out


def paged(make_script, size=40, cap=20000, timeout=None, job=None):
    """A readback that would blow the bridge's 65535-char return cap, one page at a time.

    `make_script(n0, n1)` returns an ES expression whose result is a JSON ARRAY of at most n1-n0
    rows; the loop stops on the first short page. A whole-timeline readback with a media path per
    clip hits the cap around 200 clips, which surfaces to a single-shot caller as JSON that dies
    mid-string — so anything unbounded (every clip on a track, every track above V2) is paged."""
    out = []
    for n0 in range(0, cap, size):
        part = json.loads(es(make_script(n0, n0 + size), timeout, job))
        out += part
        if len(part) < size:
            return out
    sys.exit(f'paged: stopped at the {cap}-row cap — raise `cap` if the timeline really is that long')
