#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""update.py: take a new version of the editor without losing your changes.

    uv run update.py                    update this project to the newest version in Downloads
    uv run update.py <zip or folder>    update it to that download
    uv run update.py --continue         finish an update (or an undo) that stopped on conflicts
    uv run update.py --abort            cancel it: every file goes back as it was
    uv run update.py --undo             take the last update back out, keeping everything done since
    uv run update.py --keep-mine <file> / --take-new <file>   settle a conflict on a file with no markers
    uv run update.py --init             baseline a fresh install (./setup.sh runs it)
    uv run update.py --find-installs    list the set-up installs on this machine (./setup.sh asks before a second)

This folder is a git repository with two lines of history. The `upstream` branch holds every
version of the editor exactly as it shipped; the project's branch holds the project, the user's
changes included. An update commits what the user changed, lays the new version on `upstream` and
merges it in: a file only the new version changed is updated, a file only the user changed keeps
their version, and a spot both changed stops as a conflict for Claude to resolve. projects/,
vendor/, .env, .mcp.json, large media and everything else .gitignore lists is never tracked and
never touched.

The newest download is found by the VERSION inside it, never by its file name (a second download is
saved as "video-editor-client (1).zip"), and the update always runs on the newest updater on hand,
the download's own, so a fix to the updater lands with the version that ships it. A folder installed
before updates existed is baselined on its first update against every version ever shipped
(.shipped-blobs.json, .shipped-history.pack): a file matching one was never changed, a changed one is
merged against the shipped version closest to it. Run inside a download that was never set up, it
finds the project the user works in and updates that.

Exit codes: 0 done · 1 error (the message says why; a failed update is put back) · 3 stopped on
conflicts: resolve them, then --continue (or --abort).
"""
import argparse
import difflib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows consoles default to a codepage that can't print ✓
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BLOBS = '.shipped-blobs.json'          # the git blob id of every file of every version ever shipped
HISTORY = '.shipped-history.pack'      # the text of every shipped file, every version, as a git pack
UPSTREAM = 'refs/heads/upstream'
CONFLICTS = 've-update-conflicts'      # in .git: the files an update stopped on, for --continue
STATE = 've-update-state.json'         # in .git: what an update in progress changed, for --abort
ADOPTED = 've-adopted'                 # in .git: baselined without a record of the install; cleared on success
TMP_PREFIX = 've-update-tmp-'
LARGE = 50 * 1024 * 1024               # an untracked file this big is media: left out of git, never touched
MEDIA = ('.mp4', '.m4v', '.mov', '.mxf', '.braw', '.r3d', '.mkv', '.webm', '.avi', '.wav', '.mp3', '.m4a', '.aif',
         '.aiff', '.flac', '.png', '.jpg', '.jpeg', '.heic', '.gif', '.tif', '.tiff', '.psd', '.prproj', '.drp')
#                                        an untracked, not-shipped file of these kinds is media at any size
MARKER = 'finalize.sh'   # the step-8 owner, in every version: a Content OS folder has the same root files but never this
PACKAGE_FILES = ('VERSION', 'CLAUDE.md', 'check-setup.sh', MARKER, 'update.py')
# What an undo never takes away: the tools that finish it, and the user's own rules.
KEEP_ON_UNDO = ('update.py', BLOBS, HISTORY, '.claude/hooks/setup-check.sh', 'my-rules.md')
REGISTRY = Path.home() / '.video-editor' / 'installs'   # every project on this machine that takes updates
# The user's own git settings never reach this bookkeeping: no hooks, no signing prompts, no refusal
# over folder ownership (a drive or an account the folder came from), no replayed old resolutions, and
# never CRLF (Git for Windows turns autocrlf on system-wide, and a CRLF checkout breaks every .sh).
GIT = ['git', '-c', 'core.autocrlf=false', '-c', 'core.quotepath=false', '-c', 'core.hooksPath=' + os.devnull,
       '-c', 'commit.gpgSign=false', '-c', 'tag.gpgSign=false', '-c', 'safe.directory=*',
       '-c', 'core.fsmonitor=false', '-c', 'rerere.enabled=false']


class Fail(Exception):
    pass


def git_rc(cwd, *args, env=None, stdin=None):
    e = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')}
    e.update(env or {})
    r = subprocess.run(GIT + list(args), cwd=str(cwd), env=e, input=stdin, capture_output=True)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def git(cwd, *args, env=None, stdin=None):
    rc, out, err = git_rc(cwd, *args, env=env, stdin=stdin)
    if rc:
        words = [a for i, a in enumerate(args) if a != '-c' and (i == 0 or args[i - 1] != '-c')
                 and not a.startswith('--git-dir') and not a.startswith('--work-tree')]
        raise Fail('git %s failed:\n%s' % (' '.join(words[:2]), (err or out).strip()))
    return out


def zlist(out):
    return [p for p in out.split('\0') if p]


def plural(n, word):
    return '%d %s%s' % (n, word, '' if n == 1 else 's')


def rev(root, ref):
    rc, out, _ = git_rc(root, 'rev-parse', '-q', '--verify', ref + '^{commit}')
    return out.strip() if rc == 0 else None


def tree(root, ref):
    return git(root, 'rev-parse', ref + '^{tree}').strip()


def paths_in(root, ref):
    return set(zlist(git(root, 'ls-tree', '-r', '--name-only', '-z', ref))) if ref else set()


def merge_base(root, a, b):
    rc, out, _ = git_rc(root, 'merge-base', a, b)
    return out.strip() if rc == 0 else None


def in_progress(root):
    """'merge' or 'revert' while an update or an undo is stopped on conflicts, else None."""
    if not (root / '.git').exists():
        return None
    if git_rc(root, 'rev-parse', '-q', '--verify', 'MERGE_HEAD')[0] == 0:
        return 'merge'
    if git_rc(root, 'rev-parse', '-q', '--verify', 'REVERT_HEAD')[0] == 0 or load_state(root).get('stopped') == 'undo':
        return 'revert'
    return None


def unmerged(root):
    return zlist(git(root, 'diff', '--name-only', '--diff-filter=U', '-z'))


def read_version(d):
    try:
        return (Path(d) / 'VERSION').read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


def vkey(v):
    try:
        return tuple(int(x) for x in v.split('.'))
    except (AttributeError, ValueError):
        return None


def newer(a, b):
    return bool(vkey(a)) and (not vkey(b) or vkey(a) > vkey(b))


def version_at(root, commit):
    rc, out, _ = git_rc(root, 'show', commit + ':VERSION') if commit else (1, '', '')
    return out.strip() if rc == 0 else None


def current_version(root):
    """The version the project is on: the one it last merged, else its VERSION file."""
    if (root / '.git').exists() and rev(root, UPSTREAM) and rev(root, 'HEAD'):
        v = version_at(root, merge_base(root, 'HEAD', UPSTREAM))
        if v:
            return v
    return read_version(root)


def is_install(root):
    """A client install, never the maintainer repo the package is built from."""
    return ((root / 'CLAUDE.md').is_file() and (root / 'check-setup.sh').is_file() and (root / MARKER).is_file()
            and not (root / 'packaging' / 'package-for-client.sh').exists())


def set_up(root):
    """A folder someone works in: it finished setup, or it already takes updates."""
    return (root / '.setup-complete').exists() or ((root / '.git').exists() and rev(root, UPSTREAM) is not None)


def has_jobs(root):
    return any(p.is_dir() and p.name != '_sample' for p in (root / 'projects').glob('*'))


def is_download(root):
    """A package nobody set up or worked in: a download the user opened, not their project."""
    return is_install(root) and not set_up(root) and not has_jobs(root)


def registered():
    try:
        lines = REGISTRY.read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        p = Path(line.strip())
        if line.strip() and p.is_dir() and is_install(p) and set_up(p) and all(p.resolve() != q.resolve() for q in out):
            out.append(p)
    return out


def register(root):
    try:
        known = [str(p.resolve()) for p in registered()]
        if str(root.resolve()) not in known:
            REGISTRY.parent.mkdir(parents=True, exist_ok=True)
            REGISTRY.write_text('\n'.join(known + [str(root.resolve())]) + '\n', encoding='utf-8')
    except OSError:
        pass


def projects_on_this_machine(exclude, skip_private=False):
    """Set-up installs: the registry, plus a shallow look where people keep them (an install from
    before the registry existed is only found this way). skip_private leaves out ~/Desktop and ~/Documents,
    whose first read on a Mac raises a folder-access prompt (setup.sh's check must never stop on one), and on a
    Mac ~/Downloads too, guarded the same way; an install there is still found by the registry, or by the folder
    beside this one."""
    found = [p for p in registered() if p.resolve() != exclude.resolve()]
    home = Path.home()
    private = (home / 'Desktop', home / 'Documents') + ((home / 'Downloads',) if sys.platform == 'darwin' else ())
    places = tuple(p for p in (home / 'Downloads', home) if p not in private) + (exclude.parent,) if skip_private else \
        (home / 'Downloads', home / 'Desktop', home / 'Documents', home, exclude.parent)
    for place in places:
        try:
            level1 = [p for p in place.iterdir() if p.is_dir() and not p.name.startswith('.')
                      and not (skip_private and p in private)]
        except OSError:
            continue
        for p in level1 + [c for q in level1 if q.name.lower().startswith(('video', 'editor', 'claude', 'project'))
                           for c in _subdirs(q)]:
            if (p / '.setup-complete').is_file() and is_install(p) and p.resolve() != exclude.resolve() \
                    and all(p.resolve() != q.resolve() for q in found):
                found.append(p)
    return found


def _subdirs(p):
    try:
        return [c for c in p.iterdir() if c.is_dir() and not c.name.startswith('.')]
    except OSError:
        return []


def load_known(*dirs):
    """(path -> every blob id it ever shipped as, VERSION -> {path: blob id}, old blob -> scrubbed twin)."""
    known, versions, standins = {}, {}, {}
    for d in dirs:
        try:
            data = json.loads((Path(d) / BLOBS).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        blobs = data.get('blobs', {})
        for p, shas in blobs.items():
            known.setdefault(p, set()).update(shas)
        paths = sorted(blobs)      # each version is a list aligned to the sorted paths: an index or -1
        for v, idx in data.get('versions', {}).items():
            versions.setdefault(v, {p: blobs[p][i] for p, i in zip(paths, idx) if i >= 0})
        standins.update(data.get('standins', {}))
    return known, versions, standins


def import_history(root, *dirs):
    """Bring the text of every shipped version of every file into this repository (best effort)."""
    for d in dirs:
        pack = Path(d) / HISTORY
        if pack.is_file():
            git_rc(root, 'index-pack', '--stdin', stdin=pack.read_bytes())


def existing(root, shas):
    shas = sorted(set(s for s in shas if s))
    if not shas:
        return set()
    out = git(root, 'cat-file', '--batch-check', stdin=('\n'.join(shas) + '\n').encode())
    return {line.split()[0] for line in out.splitlines() if line and not line.endswith('missing')}


def ensure_repo(root):
    if not (root / '.git').exists():
        git(root, 'init', '-q')
        git(root, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    git(root, 'config', 'core.autocrlf', 'false')
    git(root, 'config', 'merge.conflictStyle', 'diff3')   # conflicts show the version before, too
    if os.name == 'nt':
        git(root, 'config', 'core.longpaths', 'true')
    for key, value in (('user.name', 'Video Editor'), ('user.email', 'video-editor@localhost')):
        if git_rc(root, 'config', key)[0]:
            git(root, 'config', key, value)


def empty_excludes(root):
    """An empty excludes file: the project's own .gitignore decides, never a personal global one."""
    p = root / '.git' / 've-no-excludes'
    if not p.exists():
        p.write_text('', encoding="utf-8")
    return p.as_posix()


def rules_for(root, src_dir, *also):
    """The new version's ignore rules (on top of the project's own), plus any copy of the package that
    sits INSIDE the project (the download unzipped there), which is kept out for good."""
    text = ''
    gi = src_dir / '.gitignore'
    if gi.is_file():
        text = gi.read_text(encoding='utf-8', errors='replace')
    ex = root / '.git' / 'info' / 'exclude'
    for d in (src_dir,) + also:
        try:
            inside = '/' + glob_escape(Path(d).resolve().relative_to(root.resolve()).parts[0]) + '/'
        except (ValueError, IndexError):
            continue
        text += '\n' + inside + '\n'
        ex.parent.mkdir(exist_ok=True)
        if inside not in (ex.read_text(encoding='utf-8') if ex.exists() else '').splitlines():
            with open(ex, 'a', encoding='utf-8') as fh:
                fh.write(inside + '\n')
    p = root / '.git' / 've-rules'
    p.write_text(text, encoding='utf-8')
    return p.as_posix()


def glob_escape(p):
    return re.sub(r'([\\*?\[\]])', r'\\\1', p).rstrip(' ') + ('\\ ' * (len(p) - len(p.rstrip(' '))))


def clear_lock(root):
    """git's index lock left by an interrupted run (a live git process holds one for seconds)."""
    lock = root / '.git' / 'index.lock'
    if lock.exists():
        if time.time() - lock.stat().st_mtime < 120:
            raise Fail('another git operation is running in this folder right now: wait two minutes, then run '
                       'the same command again')
        lock.unlink()
        print('· Cleared a lock an interrupted update left behind.')


def clear_leftovers(root):
    clear_lock(root)
    old = time.time() - 3600
    for p in (root / '.git').glob('ve-*.index'):
        if p.stat().st_mtime < old:
            p.unlink()
    for p in Path(tempfile.gettempdir()).glob(TMP_PREFIX + '*'):
        try:
            if p.stat().st_mtime < old:
                rmtree(p)
        except OSError:
            pass


def tree_of(root, work_tree, excludes, name, seed=None):
    """Stage every non-ignored file under work_tree into a scratch index: (tree id, entries). seed: a
    commit whose files stay tracked even where an ignore rule now covers them (git never untracks)."""
    idx = root / '.git' / ('ve-%s.index' % name)
    if idx.exists():
        idx.unlink()
    env = {'GIT_INDEX_FILE': str(idx)}
    gd = '--git-dir=' + (root / '.git').as_posix()
    wt = '--work-tree=' + Path(work_tree).as_posix()
    try:
        if seed:
            git(work_tree, gd, wt, 'read-tree', seed, env=env)
        git(work_tree, '-c', 'core.excludesFile=' + excludes, gd, wt, 'add', '-A', env=env)
        t = git(work_tree, gd, wt, 'write-tree', env=env).strip()
        entries = []
        for rec in zlist(git(work_tree, gd, wt, 'ls-files', '-s', '-z', env=env)):
            meta, path = rec.split('\t', 1)
            mode, sha, _stage = meta.split()
            entries.append((mode, sha, path))
        return t, entries
    finally:
        if idx.exists():
            idx.unlink()


def tree_from(root, entries, name):
    idx = root / '.git' / ('ve-%s.index' % name)
    if idx.exists():
        idx.unlink()
    env = {'GIT_INDEX_FILE': str(idx)}
    try:
        data = ''.join('%s %s\t%s\0' % e for e in entries).encode('utf-8')
        git(root, 'update-index', '-z', '--index-info', env=env, stdin=data)
        return git(root, 'write-tree', env=env).strip()
    finally:
        if idx.exists():
            idx.unlink()


def commit(root, t, parents, msg):
    args = ['commit-tree', t]
    for p in parents:
        args += ['-p', p]
    return git(root, *args, '-m', msg).strip()


def closest(root, sha, candidates, prefer=None):
    """The candidate blob fewest changed lines away from `sha`: the version the user started from (on a
    tie, the one the folder's VERSION names, else the older-sorting one)."""
    best = None
    for c in sorted(candidates, key=lambda c: (c != prefer, c)):
        rc, out, _ = git_rc(root, 'diff', '--numstat', c, sha)
        if rc == 0:
            n = sum(int(x) for line in out.splitlines() for x in line.split('\t')[:2] if x.isdigit())
            if best is None or n < best[0]:
                best = (n, c)
    return best[1] if best else candidates[0]


def baseline(root, fingerprints, excludes=None, package=None, new_version=None):
    """Record the package this folder was installed from as `upstream`, and the folder as it is now
    (the user's changes included) on top of it. package: the new version's {path: (mode, blob)}.
    Returns how many files matched no shipped version (the user's own work)."""
    known, versions, standins = fingerprints
    package = package or {}
    ensure_repo(root)
    if git_rc(root, 'symbolic-ref', '-q', 'HEAD')[0]:
        raise Fail('this folder\'s git repository is not on a branch (detached HEAD): check one out first')
    head = rev(root, 'HEAD')
    t, entries = tree_of(root, root, excludes or empty_excludes(root), 'current', seed=head)
    # Shipped files an older .gitignore hid (a pre-rendered background, the _sample skeleton) are part
    # of the folder as it stands: record them, so an undo can never delete them.
    present = {p for _m, _s, p in entries}
    hidden = sorted(p for p in (set(known) | set(package)) - present - {BLOBS, HISTORY} if (root / p).is_file())
    if hidden:
        shas = git(root, 'hash-object', '-w', '--stdin-paths', stdin=('\n'.join(hidden) + '\n').encode()).split()
        entries += [('100755' if os.access(root / p, os.X_OK) and os.name != 'nt' else '100644', s, p)
                    for p, s in zip(hidden, shas)]
        t = tree_from(root, entries, 'current2')
        present |= set(hidden)
    have = existing(root, [x for _m, _s, p in entries for b in known.get(p, ()) for x in (b, standins.get(b))])
    shipped = versions.get(read_version(root)) or {}
    older = {}          # path -> forms some version other than the incoming one shipped
    for v, m in versions.items():
        if v != new_version:
            for p, b in m.items():
                older.setdefault(p, set()).add(b)
    # Unchanged = byte-identical to a version that shipped. Anything else is the user's work, merged
    # against the shipped form closest to it: only when the text of every form is on hand (or it only
    # ever shipped in one form), and never a form only the incoming version ships, which the user
    # cannot have started from.
    base, mine = [], 0
    for mode, sha, path in entries:
        if path in (BLOBS, HISTORY) or sha in known.get(path, ()):
            base.append((mode, sha, path))
            continue
        mine += 1
        forms = {b for b in known.get(path, set())
                 if not (package.get(path, (None, None))[1] == b and b not in older.get(path, ()))}
        text = {b: (b if b in have else standins.get(b)) for b in forms}
        cands = sorted(set(x for x in text.values() if x in have))
        if cands and (len(cands) == len(forms) or len(cands) > 1):
            prefer = text.get(shipped.get(path))
            base.append((mode, closest(root, sha, cands, prefer) if len(cands) > 1 else cands[0], path))
    # A shipped file the user deleted stays deleted (only when every unchanged file says which
    # version this is, so a file the folder never had is not taken for one it removed).
    clean = bool(shipped) and all(shipped.get(p) == s for _m, s, p in base if p not in (BLOBS, HISTORY)
                                  and s in known.get(p, ()))
    if clean:
        gone = {p: b for p, b in shipped.items() if p not in present and not (root / p).exists()}
        have_gone = existing(root, gone.values())
        for p, b in gone.items():
            if b in have_gone:
                mode = package.get(p, (None,))[0]
                if not mode:     # Windows: 100644, as git records every file it adds there (core.fileMode is off)
                    mode = ('100755' if git(root, 'cat-file', '-p', b)[:2] == '#!' and os.name != 'nt'
                            else '100644')
                base.append((mode, b, p))
    btree = tree_from(root, base, 'base')
    b = commit(root, btree, [], 'Package %s, as installed' % (read_version(root) or '(unknown version)'))
    git(root, 'update-ref', UPSTREAM, b)
    if head is None and t == btree:
        top = b
    else:
        top = commit(root, t, ([head] if head else []) + [b], 'Your project when updates were set up')
    git(root, 'update-ref', 'HEAD', top)
    git(root, 'reset', '-q')      # the index matches that commit; no file on disk is touched
    return mine


def extract(zpath, dest):
    dest = dest.resolve()
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if dest not in target.parents and target != dest:
                raise Fail('%s: unsafe path inside the zip: %s' % (zpath, info.filename))
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as s, open(target, 'wb') as d:
                shutil.copyfileobj(s, d)
            mode = (info.external_attr >> 16) & 0o777   # zipfile drops the exec bit; put it back
            if mode and os.name != 'nt':
                os.chmod(target, mode)


def package_version(p):
    """(VERSION, package folder) of a download (a zip, or the folder it unzipped to, the package at
    most one folder down), else None. A folder somebody set up is an install, never a download."""
    try:
        if p.is_dir():
            for c in [p] + sorted(x for x in p.iterdir() if x.is_dir()):
                if all((c / f).is_file() for f in PACKAGE_FILES[:4]) and not set_up(c):
                    return read_version(c), c
            return None
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            for n in sorted(names):
                parts = n.split('/')
                if parts[-1] == 'VERSION' and len(parts) <= 2:
                    top = n[:-len('VERSION')]
                    if all(top + f in names for f in PACKAGE_FILES[1:4]):
                        return z.read(n).decode('utf-8', 'replace').strip(), p
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError, zlib.error, EOFError):
        pass
    return None


def downloads(root, places):
    """Every video-editor download in `places`, newest version first; plus the damaged ones and the
    places that could not be read (a macOS privacy block reads like an empty folder)."""
    seen, found, damaged, unreadable = set(), [], [], []
    for d in places:
        try:
            items = sorted(d.iterdir())
        except PermissionError:
            unreadable.append(d)
            continue
        except OSError:
            continue
        for p in items:
            if not p.name.lower().startswith('video-editor') or not (p.is_dir() or p.suffix.lower() == '.zip'):
                continue
            key = str(p.resolve())
            if key in seen or p.resolve() == root.resolve():
                continue
            seen.add(key)
            got = package_version(p)
            if got and vkey(got[0]):
                found.append((vkey(got[0]), got[0], p))
            elif p.suffix.lower() == '.zip':
                damaged.append(p)
    return sorted(found, key=lambda f: f[0], reverse=True), damaged, unreadable


def own_package():
    """The package this updater runs from, when it is a download (not an install)."""
    here = Path(__file__).resolve().parent
    got = package_version(here) if (here / 'update.py').is_file() else None
    return (vkey(got[0]), got[0], got[1]) if got and vkey(got[0]) and got[1].resolve() == here else None


def downloads_folder():
    """~/Downloads, or where Windows has moved it (Known Folder redirection to another drive)."""
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as k:
                return Path(os.path.expandvars(winreg.QueryValueEx(k, '{374DE290-123F-4565-9164-39C4925E467B}')[0]))
        except OSError:
            pass
    return Path.home() / 'Downloads'


def newest_download(root, cur):
    home = Path.home()
    base = [downloads_folder(), home / 'Downloads', root.parent, root]
    found, damaged, unreadable = downloads(root, base)
    own = own_package()
    if own and own[2].resolve() != root.resolve():
        found = sorted(found + [own], key=lambda f: f[0], reverse=True)
    best = next((f for f in found if newer(f[1], cur)), None)
    if not found:    # the Desktop only when no download at all turned up: on a Mac, reading it can prompt
        more, d2, u2 = downloads(root, [home / 'Desktop'])
        found, damaged, unreadable = sorted(found + more, key=lambda f: f[0], reverse=True), damaged + d2, unreadable + u2
        best = next((f for f in found if newer(f[1], cur)), None)
    return best, found, damaged, unreadable


def pick_source(source, root, cur, force):
    if source:
        p = Path(source).expanduser().resolve()
        got = package_version(p) if p.exists() else None
        if not got:
            if p.is_file() and p.suffix.lower() == '.zip':
                raise Fail('%s is damaged, still downloading, or not a video-editor download: wait for it to finish, '
                           'or download it again' % p)
            raise Fail('%s: not a video-editor download (the .zip, or the folder it unzipped to)' % source)
        if force or newer(got[0], cur):
            return p
        best = newest_download(root, cur)[0]   # a second download is saved as "... (1).zip"
        if best:
            print('· %s is %s, not newer than this project (%s): using %s (%s), the newest download.'
                  % (p.name, got[0], cur, best[2], best[1]))
            return best[2]
        return p
    best, found, damaged, unreadable = newest_download(root, cur)
    if best:
        print('· Newest download: %s (%s)' % (best[2], best[1]))
        return best[2]
    why = []
    for p in damaged:
        try:
            size = p.stat().st_size // (1024 * 1024)
        except OSError:
            size = 0
        why.append('%s is damaged or still downloading (%d MB): wait for it to finish, or download it again' % (p, size))
    for d in unreadable:
        why.append('%s could not be read: on a Mac, allow Claude (or its terminal) in System Settings → Privacy & '
                   'Security → Files and Folders' % d)
    seen = ', '.join('%s (%s)' % (f[2], f[1]) for f in found[:4]) or 'none'
    raise Fail('no newer version found: this project is on %s; downloads seen: %s.%s %s give its path: '
               'uv run update.py "<the zip>"'
               % (cur or 'an unknown version', seen, ''.join(' ' + w + '.' for w in why),
                  'Or' if unreadable or damaged else 'Download the new zip from the download page, or'))


def open_source(p, root):
    tmp = None
    if p.is_dir():
        got = package_version(p)
    else:
        tmp = Path(tempfile.mkdtemp(prefix=TMP_PREFIX))
        try:
            extract(p, tmp)
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError, RuntimeError) as e:
            rmtree(tmp)
            raise Fail('%s is damaged or incomplete (%s): download it again' % (p.name, e))
        got = package_version(tmp)
    top = got[1] if got else None
    missing = [f for f in PACKAGE_FILES if not top or not (top / f).is_file()]
    if missing:
        rmtree(tmp)
        raise Fail('%s is not a complete video-editor package (missing %s)' % (p, ', '.join(missing)))
    if top.resolve() == root.resolve():
        rmtree(tmp)
        raise Fail('that is this project itself: point at the NEW download')
    return top, tmp


def rmtree(p):
    def writable(fn, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    if p and Path(p).exists():
        try:
            shutil.rmtree(str(p), onerror=writable)
        except OSError:
            pass      # temp space: whatever a virus scanner still holds is cleared by a later run


def release_notes(src_dir, since=None, limit=40):
    """Every RELEASE.md section newer than `since` (only the newest when `since` is unknown), minus
    the how-to-update bullets, which mean nothing to someone who just updated."""
    try:
        lines = (src_dir / 'RELEASE.md').read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    sections = []
    for line in lines:
        if line.startswith('## '):
            sections.append((line[3:].strip(), [line]))
        elif sections and line.strip() and 'update.py' not in line and not line.startswith('- To update'):
            sections[-1][1].append(line)
    keep = [s for s in sections if newer(s[0], since)] if vkey(since) else sections[:1]
    out = []
    for _v, body in keep:        # past the cap, each older section still shows its heading and lead line
        out += body if len(out) + len(body) <= limit else body[:2]
    return out


def names(paths, n=12):
    paths = list(paths)
    return ', '.join(paths[:n]) + (' … +%d more' % (len(paths) - n) if len(paths) > n else '')


def is_binary(p):
    try:
        with open(p, 'rb') as fh:
            return b'\0' in fh.read(8000)
    except OSError:
        return False


def has_markers(p):
    try:
        data = p.read_bytes()
    except OSError:
        return False
    if b'\0' in data[:8000]:
        return False           # binary: git leaves one side in place, no markers
    return any(line.startswith((b'<<<<<<< ', b'||||||| ', b'>>>>>>> ')) for line in data.splitlines())


def save_state(root, **kw):
    (root / '.git' / STATE).write_text(json.dumps(kw), encoding='utf-8')


def update_state(root, **kw):
    st = load_state(root)
    st.update(kw)
    save_state(root, **st)


def load_state(root):
    try:
        return json.loads((root / '.git' / STATE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def clear_state(root):
    for f in (STATE, CONFLICTS):
        p = root / '.git' / f
        if p.exists():
            p.unlink()


def leave_out_large(root, rules, shipped=()):
    """Media dropped outside projects/ stays exactly where it is, but out of git for good: any untracked file over
    LARGE, and any untracked file of a MEDIA kind whatever its size (a 1 MB clip or a still would otherwise ride in
    every commit). A file the editor itself ships, like a pre-rendered background, is never media."""
    shipped = set(shipped)
    if rev(root, UPSTREAM):
        shipped |= paths_in(root, UPSTREAM)
    big = [p for p in zlist(git(root, '-c', 'core.excludesFile=' + rules, 'ls-files', '-o', '--exclude-standard', '-z'))
           if p not in shipped and (root / p).is_file()
           and (Path(p).suffix.lower() in MEDIA or (root / p).stat().st_size > LARGE)]
    if big:
        ex = root / '.git' / 'info' / 'exclude'
        ex.parent.mkdir(exist_ok=True)
        with open(ex, 'a', encoding='utf-8') as fh:
            fh.write(''.join('/' + glob_escape(p) + '\n' for p in big))
        print('· Left out of updates (media, untouched where it is): %s' % names(big))


def unwritable(root, paths):
    """Files the update must rewrite that another app holds open (Windows) or that are read-only."""
    bad = []
    for p in paths:
        f = root / p
        if f.is_file():
            try:
                with open(f, 'ab'):
                    pass
            except OSError:
                bad.append(p)
    return bad


def protect_untracked(root, mb):
    """A file the new version adds where the user already keeps an untracked copy (one the old ignore
    rules hid, say a re-rendered background) is moved aside as '<name> (yours)', never overwritten.
    Returns [(original, moved to)], and the added paths that already existed (never deleted by a
    put-back)."""
    tracked = set(zlist(git(root, 'ls-files', '-z')))
    moved, there = [], []
    for p in zlist(git(root, 'diff', '--name-only', '-z', '--diff-filter=A', mb, UPSTREAM)):
        f = root / p
        if p in tracked or not f.is_file():
            continue
        there.append(p)
        if git(root, 'hash-object', '--', str(f)).strip() != git(root, 'rev-parse', '%s:%s' % (UPSTREAM, p)).strip():
            dest, n = f.with_name(f.stem + ' (yours)' + f.suffix), 2
            while dest.exists():
                dest, n = f.with_name('%s (yours %d)%s' % (f.stem, n, f.suffix)), n + 1
            f.rename(dest)
            moved.append((p, dest.relative_to(root).as_posix()))
    return moved, there


def restore_moved(root, moved):
    for orig, dest in moved:
        f, d = root / orig, root / dest
        if d.exists():
            if f.exists():
                f.unlink()
            d.rename(f)


def put_back(root, before, up, mb, moved, there):
    """Undo a merge git could not finish (a file it could not write): the project as it was."""
    if in_progress(root):
        git_rc(root, 'merge', '--abort')
    git_rc(root, 'reset', '-q', '--hard', before)
    tracked = set(zlist(git(root, 'ls-files', '-z')))
    for p in zlist(git(root, 'diff', '--name-only', '-z', '--diff-filter=A', mb, UPSTREAM)):
        if p not in tracked and p not in there and (root / p).is_file():
            (root / p).unlink()
    restore_moved(root, moved)
    git(root, 'update-ref', UPSTREAM, up)
    clear_state(root)


def elsewhere(root):
    """The session is not in the project (a download redirected here): commands need the folder."""
    return Path.cwd().resolve() != root.resolve()


def cmd(root, args):
    return ('uv run update.py --project "%s" %s' % (root, args)).strip() if elsewhere(root) else ('uv run update.py ' + args).strip()


UV_FLOOR = '0.9.17'   # relative exclude-newer ("14 days"), every tool's cooldown: setup.sh and check-setup.sh hold the same


def uv_behind():
    """The line to print when the uv on PATH is older than UV_FLOOR, else ''. An update is the one step sure to run
    before the next edit, and this file needs no package, so an old uv still runs it."""
    try:
        out = subprocess.run(['uv', '--version'], capture_output=True, text=True).stdout
    except OSError:
        return ''
    m = re.match(r'uv (\d+(?:\.\d+)*)', out.strip())
    if not m:
        return ''
    have, want = [int(x) for x in m.group(1).split('.')], [int(x) for x in UV_FLOOR.split('.')]
    if have + [0] * (3 - len(have)) >= want:
        return ''
    return ('⚠ uv %s is older than %s, which every tool in this version needs (its 14-day package cooldown): every '
            'tool would stop on its first run. Run ./check-setup.sh now: it names the command that upgrades uv the '
            'way it was installed (brew upgrade uv · winget upgrade --id astral-sh.uv -e · uv self update).'
            % (m.group(1), UV_FLOOR))


def setup_due(root):
    """True when ./setup.sh has not run on this VERSION: its self-test (and, on Windows, Smart App Control's pre-check,
    workflows/sac-warm.py) is keyed to VERSION, and after an update nothing else runs them: check-setup.sh only notes
    the pre-check, and the SessionStart hook stays silent on a marker from before the record (the Windows re-test,
    2026-10-13: an update from 2026.10.13 ran neither)."""
    try:
        ver = (root / 'VERSION').read_text(encoding='utf-8').strip()
        marker = (root / '.setup-complete').read_text(encoding='utf-8').splitlines()
    except OSError:
        return False
    return (root / 'workflows' / 'selftest.py').is_file() and ('selftest=' + ver) not in marker


def next_steps(root, undo=False):
    what = 'the restored version\'s instructions' if undo else 'the new version\'s instructions'
    check = './check-setup.sh can be run (only a ✗ line needs ./setup.sh)'
    if not undo and setup_due(root):
        check = ('./setup.sh runs once, with the Bash timeout at 600000 ms (it skips everything already done, re-runs '
                 'its 30-second self-test for this version and, on Windows, pre-checks the new tools\' files with '
                 'Smart App Control)')
    if elsewhere(root):
        return ('Next: tell the user their project is %s: open that folder in Claude Code (File → Open Folder) and '
                'work there; this folder was only the download and can be deleted. In that folder, %s load, and '
                '%s.' % (root, what, check))
    if not undo and setup_due(root):
        return ('Next: run ./setup.sh yourself, with the Bash timeout at 600000 ms: it skips everything already done, '
                're-runs its 30-second self-test for this version and, on Windows, pre-checks the new tools\' files '
                'with Smart App Control once. Then tell the user to start a fresh Claude Code session (type /clear, '
                'or quit and reopen it) so %s load.' % what)
    return ('Next: run ./check-setup.sh (only a ✗ line needs ./setup.sh). Then tell the user to start a fresh Claude '
            'Code session (type /clear, or quit and reopen it) so %s load.' % what)


CONFLICT_KINDS = {
    'merge': {'UU': 'both changed it', 'AA': 'both added it, with no record of the version the user started from',
              'UD': 'the new version removed it; the user\'s changed copy is kept in place',
              'DU': 'the user deleted it and the new version changed it: delete it again unless the change is needed',
              'AU': 'both changed it', 'UA': 'both changed it'},
    'revert': {'UU': 'changed again since the update', 'AA': 'changed again since the update',
               'UD': 'the undo removes it, and it was changed since the update',
               'DU': 'deleted since the update, and the undo brings back its old text',
               'AU': 'changed again since the update', 'UA': 'changed again since the update'},
}


def say_conflicts(root, files, kind='merge'):
    (root / '.git' / CONFLICTS).write_text('\n'.join(files) + '\n', encoding='utf-8')
    kinds = dict(CONFLICT_KINDS[kind])
    if kind == 'merge' and not load_state(root).get('adopted'):
        kinds['AA'] = 'both added it'
    status = {}
    for rec in zlist(git(root, 'status', '--porcelain', '-z')):
        status[rec[3:]] = rec[:2]
    where = ('%s/' % root) if elsewhere(root) else ''
    if kind == 'revert':
        print('✋ The undo stopped on %s changed since the update:' % plural(len(files), 'file'))
    else:
        print('✋ Stopped on %s that both the user and the new version changed:' % plural(len(files), 'file'))
    for f in files:
        label = kinds.get(status.get(f, 'UU'), 'both changed it')
        if is_binary(root / f):
            label += '; binary, no markers: pick a side with --keep-mine or --take-new'
        print('    %s%s  (%s)' % (where, f, label))
    if kind == 'revert':
        print('''
For Claude: resolve every conflict block in those files, then run `%s`.
    <<<<<<< HEAD                  the project now: the update plus the user's later work
    ||||||| ...                   the text the update brought
    =======
    >>>>>>> parent of ...         the file as it was before the update
  Take the before-the-update side, except for the user's own later edits, which stay. A file with no
  markers: `%s <file>` keeps it as it is now, `%s <file>` takes the before-the-update
  version. `%s` cancels the undo.''' % (cmd(root, '--continue'), cmd(root, '--keep-mine'), cmd(root, '--take-new'),
                                         cmd(root, '--abort')))
        return
    print('''
For Claude: resolve every conflict block in those files, then run `%s`.
    <<<<<<< HEAD                  this project's version (the user's changes)
    ||||||| ...                   the version the user had before (when there is a record of it)
    =======
    >>>>>>> refs/heads/upstream   the new version
  Keep the new version's content AND the user's deliberate changes; where they truly clash, keep the
  user's change and tell them. With no record of the starting version, a HEAD block can be the user's
  change OR an older line the new version rewrote: take the new side unless the HEAD side is clearly
  theirs (their brand, preset, wording or rule), and ask about any block you cannot call. A rule or an
  identity line the user wrote into CLAUDE.md goes to my-rules.md (no update ever changes it), and
  CLAUDE.md takes the new version. A file with no markers (a binary): `%s <file>` keeps the
  user's, `%s <file>` takes the new one. RELEASE.md says what changed. `%s` puts every
  file back as it was before the update.''' % (cmd(root, '--continue'), cmd(root, '--keep-mine'),
                                               cmd(root, '--take-new'), cmd(root, '--abort')))


def blobs_at(root, ref):
    out = {}
    for rec in zlist(git(root, 'ls-tree', '-r', '-z', ref)):
        meta, path = rec.split('\t', 1)
        out[path] = meta.split()[2]
    return out


def move_to_my_rules(root, mb, before, new_ver, files):
    """Lines the user ADDED to CLAUDE.md (where "apply my brand kit" wrote their identity before my-rules.md
    existed) move into my-rules.md, which no update changes, so CLAUDE.md takes each new version cleanly.
    Only pure additions move: an edited or deleted shipped line stays an ordinary merge."""
    f, mine_f = 'CLAUDE.md', 'my-rules.md'
    if not mb or mine_f in files or not (root / mine_f).is_file():
        return 0
    try:
        base = git(root, 'show', '%s:%s' % (mb, f)).splitlines()
        ours = git(root, 'show', '%s:%s' % (before, f)).splitlines()
        new = git(root, 'show', '%s:%s' % (UPSTREAM, f))
    except Fail:
        return 0
    if '@' + mine_f not in new:
        return 0
    chunks, kept = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base, ours, autojunk=False).get_opcodes():
        if op == 'equal':
            kept += ours[j1:j2]
            continue
        if op != 'insert':
            return 0
        lines = ours[j1:j2]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            head = next((h[3:].strip() for h in reversed(ours[:j1]) if h.startswith('## ')), '')
            chunks.append((head, lines))
    if not chunks or kept != base:
        return 0
    text = (root / mine_f).read_text(encoding='utf-8').rstrip('\n')
    text += '\n\n## Moved here from CLAUDE.md by the update to %s\n' % new_ver
    for head, lines in chunks:
        text += '\n' + ('(from its "%s" section)\n' % head if head else '') + '\n'.join(lines) + '\n'
    (root / mine_f).write_bytes(text.encode('utf-8'))    # bytes: text mode writes CRLF on Windows
    git(root, 'checkout', UPSTREAM, '--', f)
    git(root, 'add', '--', mine_f)
    return sum(len(lines) for _h, lines in chunks)


def report(root, mb, before, old_ver, new_ver, src_dir, moved, stopped):
    was, now = blobs_at(root, before), blobs_at(root, UPSTREAM)
    mine = [p for p in zlist(git(root, 'diff', '--name-only', '-z', mb, before)) if was.get(p) != now.get(p)]
    changed = zlist(git(root, 'diff', '--name-only', '-z', mb, UPSTREAM))
    print('%s %s → %s: %s changed in the new version.'
          % ('… Updating' if stopped else '✓ Updated', old_ver or '(unknown version)', new_ver,
             plural(len(changed), 'file')))
    if mine:
        print('  Your own changes, carried over (%s): %s' % (plural(len(mine), 'file'), names(mine)))
    if moved:
        print('  The new version ships these paths, so your own copies were moved aside, not overwritten: '
              + names(d for _o, d in moved))
    notes = release_notes(src_dir, old_ver)
    if notes:
        print('\nWhat is new (RELEASE.md):\n  ' + '\n  '.join(notes))
    print()
    return notes


def finish(root, again=False):
    """After a merged update: what the user needs to know, then the bookkeeping."""
    st = load_state(root)
    if again and st.get('notes'):
        print('What is new (RELEASE.md):\n  ' + '\n  '.join(st['notes']))
    mb = merge_base(root, st.get('head_before') or 'HEAD^1', UPSTREAM)
    if mb:
        old, new = paths_in(root, mb), paths_in(root, UPSTREAM)
        retired = [p for p in sorted(paths_in(root, 'HEAD')) if p in old and p not in new]
        if retired:
            print('The new version retired these, but the user had changed them, so their copies stay: %s. '
                  'Move anything still needed to where RELEASE.md says it went, then delete the rest.' % names(retired))
        changed = zlist(git(root, 'diff', '--name-only', '-z', mb, UPSTREAM))
        try:
            filled = '<<YOUR_NAME>>' not in (root / 'brand-kit.md').read_text(encoding='utf-8')
        except OSError:
            filled = False
        if filled and 'brand-kit.md' in changed:
            print('brand-kit.md changed in this version and the user\'s is filled in: fill any new <<...>> field '
                  'from a value they already gave for the same role (ask only for genuinely new ones), then say '
                  '"apply my brand kit" so every preset carries the brand.')
    clear_state(root)
    if (root / '.git' / ADOPTED).exists():
        (root / '.git' / ADOPTED).unlink()
    git_rc(root, 'update-ref', '-d', 'refs/ve/snapshot')
    register(root)
    behind = uv_behind()
    if behind:
        print(behind)
    print(next_steps(root))
    return 0


def redirect_target(root, what):
    """Run inside a download nobody set up: the one project on this machine it should act on."""
    homes = projects_on_this_machine(root)
    if len(homes) == 1:
        print('This folder is a download that was never set up, not the project the user works in: %s %s.'
              % (what, homes[0]))
        return homes[0]
    listing = '; '.join(map(str, homes))
    raise Fail('%s is a download that was never set up, not the project the user works in. %s'
               % (root, ('Projects on this machine: %s. Ask which one, then run: uv run update.py --project '
                         '"<that folder>"' % listing) if homes else
                  'No set-up project was found on this machine: ask the user where their editor folder is, then run: '
                  'uv run update.py --project "<that folder>"'))


def overwritten_leftovers(root):
    """Files only OLDER versions shipped, still on disk beside a newer VERSION: what a new version unzipped over an
    install from before updates leaves behind (prune.sh after 2026.09.25.4, say)."""
    _known, versions, _st = load_known(root)
    cur = read_version(root)
    now = versions.get(cur)
    if not now or not vkey(cur):
        return []
    older = set()
    for v, m in versions.items():
        if vkey(v) and vkey(v) < vkey(cur):
            older |= set(m)
    return sorted(p for p in older - set(now) if p not in (BLOBS, HISTORY) and (root / p).is_file())


def update(root, source, force):
    if in_progress(root):
        raise Fail('an update is already in progress in %s: finish it with `%s`, or cancel it with `%s`'
                   % (root, cmd(root, '--continue'), cmd(root, '--abort')))
    if not is_install(root):
        raise Fail('%s is not a video-editor project folder: run this from the project folder' % root)
    if is_download(root):
        return update(redirect_target(root, 'updating'), source or str(root), force)
    try:
        p = pick_source(source, root, current_version(root), force)
    except Fail:
        left = [] if (root / '.git').exists() and rev(root, UPSTREAM) else overwritten_leftovers(root)
        if left:
            raise Fail('the new version (%s) was unzipped OVER this folder: %s from older versions %s still here (%s), '
                       'so edits made to the editor\'s own files were overwritten and cannot be recovered here. '
                       'Restore this folder from Time Machine (Mac) or File History (Windows) if there is a backup, '
                       'then unzip the newest download into a NEW, separate folder and run that folder\'s update.py '
                       'on this one. Nothing was changed.'
                       % (read_version(root), plural(len(left), 'file'), 'is' if len(left) == 1 else 'are',
                          names(left, 4)))
        raise
    src_dir, tmp = open_source(p, root)
    try:
        me, theirs = Path(__file__).resolve(), src_dir / 'update.py'
        mine_v = read_version(me.parent) if (me.parent / 'update.py').is_file() else None
        if (os.environ.get('VE_UPDATE_HANDOFF') != '1' and theirs.read_bytes() != me.read_bytes()
                and not newer(mine_v, read_version(src_dir))):
            # The newest updater on hand runs the update, so its fixes apply to this one.
            sys.stdout.flush()
            sys.stderr.flush()
            args = [sys.executable, str(theirs), str(src_dir), '--project', str(root)] + (['--force'] if force else [])
            return subprocess.run(args, env=dict(os.environ, VE_UPDATE_HANDOFF='1')).returncode
        return apply_update(root, src_dir, force)
    finally:
        rmtree(tmp)


def restore_overwritten(root, up, uentries):
    """The new version copied OVER the project (Windows' Extract All offers Replace first): a file now
    identical to the incoming one is put back to the user's own last text, from the last update's commit
    or from the snapshot the SessionStart hook takes of unsaved-to-git edits, so the merge carries both.
    Returns True when the folder looks overwritten."""
    head, old = blobs_at(root, 'HEAD'), blobs_at(root, up)
    incoming = {p: s for _m, s, p in uentries}
    try:
        on_disk = (root / 'VERSION').read_bytes()
    except OSError:
        on_disk = b''
    if 'VERSION' not in incoming or head.get('VERSION') == incoming['VERSION'] \
            or blob_of(on_disk) != incoming['VERSION']:
        return False                  # not unzipped over: the working tree is the user's, as it stands
    snap = rev(root, 'refs/ve/snapshot')
    kept = blobs_at(root, snap) if snap else {}
    from_head, from_snap = [], []
    candidates = set(zlist(git(root, 'diff', '--name-only', '-z', 'HEAD'))) | {q for q, b in kept.items() if head.get(q) != b}
    for p in sorted(candidates):
        f = root / p
        if p not in incoming or not f.is_file() or git(root, 'hash-object', '--', str(f)).strip() != incoming[p]:
            continue
        if kept.get(p) not in (None, old.get(p), incoming[p], head.get(p)):
            from_snap.append(p)
        elif p in head and head[p] not in (old.get(p), incoming[p]):
            from_head.append(p)
    if from_head:
        git(root, 'checkout', 'HEAD', '--', *from_head)
    if from_snap:
        git(root, 'checkout', snap, '--', *from_snap)
    if from_head or from_snap:
        print('· The new version had been copied over %s; the user\'s versions are restored and merged with it.'
              % names(from_head + from_snap))
    return True


def blob_of(data):
    import hashlib
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def recover_interrupted(root):
    """An apply killed between its bookkeeping and its merge (a closed terminal, a crash) left the state file, an
    upstream already moved to the new package and, maybe, some of the package's files written over the project's.
    Put the project back as it was before that run, so the new run starts from the user's own files."""
    st = load_state(root)
    if not st.get('head_before') or st.get('kind') == 'undo' or st.get('stopped') == 'undo' or in_progress(root):
        return False
    if rev(root, 'HEAD') != st['head_before']:
        clear_state(root)              # the merge was committed: only the bookkeeping after it was lost
        return False
    pkg, hb = blobs_at(root, UPSTREAM), blobs_at(root, st['head_before'])
    touched = set(zlist(git(root, 'diff', '--name-only', '-z', 'HEAD'))) \
        | set(zlist(git(root, 'ls-files', '-o', '--exclude-standard', '-z')))
    back, gone = [], []
    for p in sorted(touched):
        f = root / p
        if p not in pkg or not f.is_file() or git(root, 'hash-object', '--', str(f)).strip() != pkg[p] \
                or hb.get(p) == pkg[p]:
            continue
        if p in hb:
            back.append(p)
        else:
            f.unlink()
            gone.append(p)
    if back:
        git(root, 'checkout', st['head_before'], '--', *back)
    restore_moved(root, st.get('moved') or [])
    if st.get('upstream_before'):
        git(root, 'update-ref', UPSTREAM, st['upstream_before'])
    clear_state(root)
    print('· The last update was interrupted; it was put back first.')
    return True


def apply_update(root, src_dir, force):
    print('Project: %s' % root)
    new_ver = read_version(src_dir)
    ensure_repo(root)
    clear_leftovers(root)
    recover_interrupted(root)
    level1 = _subdirs(root)
    nested = [d for d in level1 + [c for q in level1 for c in _subdirs(q)]
              if all((d / f).is_file() for f in PACKAGE_FILES)]     # a copy of the package unzipped inside
    rules = rules_for(root, src_dir, Path(__file__).resolve().parent, *nested)
    utree, uentries = tree_of(root, src_dir, empty_excludes(root), 'package')   # its own rules only
    upaths = {p for _m, _s, p in uentries}
    if not {'VERSION', 'update.py'} <= upaths:
        raise Fail('the new package\'s own .gitignore hides its files; nothing was changed')
    try:
        lane = next((l[5:].strip() for l in (root / '.setup-complete').read_text(encoding='utf-8').splitlines()
                     if l.startswith('lane=')), '')
    except OSError:
        lane = ''
    if (lane in ('premiere', 'resolve', 'capcut', 'finalcut') and not force
            and any(p.startswith('lanes/') for p in upaths) and not any(p.startswith('lanes/%s/' % lane) for p in upaths)):
        raise Fail('this download is a package without your editing app (%s): download the full package from the '
                   'download page. Nothing was changed.' % lane)
    if not rev(root, UPSTREAM):
        # Installed before updates existed: baseline it now, under the NEW version's ignore rules (on
        # top of its own), against every version either copy knows.
        import_history(root, root, src_dir)
        fp = load_known(root, src_dir)
        leave_out_large(root, rules, set(fp[0]) | upaths)
        mine = baseline(root, fp, rules, {p: (m, s) for m, s, p in uentries}, new_ver)
        (root / '.git' / ADOPTED).write_text(new_ver or '', encoding='utf-8')
        print('✓ Set this project up for updates: a git repository now tracks it%s.'
              % ((' (%s the user changed %s merged with them, never overwritten)'
                  % (plural(mine, 'file'), 'is' if mine == 1 else 'are')) if mine else ''))
    adopted = (root / '.git' / ADOPTED).exists()
    mb = merge_base(root, 'HEAD', UPSTREAM)
    old_ver = version_at(root, mb) or read_version(root)
    if vkey(new_ver) and vkey(old_ver) and vkey(new_ver) < vkey(old_ver) and not force:
        raise Fail('that download is %s, older than this project (%s); nothing was changed. Run `uv run update.py` '
                   'with no path to find the newest download.' % (new_ver, old_ver))
    up = rev(root, UPSTREAM)
    merged = git_rc(root, 'merge-base', '--is-ancestor', UPSTREAM, 'HEAD')[0] == 0
    if utree == tree(root, UPSTREAM) and merged:
        register(root)
        print('✓ Already up to date with %s; nothing to do.' % new_ver)
        return 0
    old_paths = paths_in(root, mb)
    if old_paths and len(old_paths - upaths) > len(old_paths) / 2 and not force:
        raise Fail('that download would remove %d of the %d files this project has from the editor: it does not '
                   'look like a newer version of it. Nothing was changed.' % (len(old_paths - upaths), len(old_paths)))
    if restore_overwritten(root, up, uentries):
        print('· The new version had been unzipped over this folder. Edits made to its files in THIS session, before '
              'that, could not be recovered; tell the user, and next time to leave the download where it is.')

    # 1. Whatever the user changed since the last update becomes a commit of its own.
    leave_out_large(root, rules, upaths)
    git(root, '-c', 'core.excludesFile=' + rules, 'add', '-A')
    if git_rc(root, 'diff', '--cached', '--quiet')[0]:
        git(root, 'commit', '-q', '-m', 'Your changes before updating to %s' % new_ver)
    before = rev(root, 'HEAD')

    # 2. The new version, exactly as shipped, on top of upstream.
    if utree != tree(root, UPSTREAM):
        u, n = commit(root, utree, [up], 'Package %s' % new_ver), 2
        while git_rc(root, 'merge-base', '--is-ancestor', u, 'HEAD')[0] == 0:   # an undo took it back out
            u, n = commit(root, utree, [up], 'Package %s (again, %d)' % (new_ver, n)), n + 1
        git(root, 'update-ref', UPSTREAM, u)
    mb = merge_base(root, before, UPSTREAM)
    locked = unwritable(root, zlist(git(root, 'diff', '--name-only', '-z', mb, UPSTREAM)))
    if locked:
        git(root, 'update-ref', UPSTREAM, up)
        raise Fail('%s %s open in another app, or read-only: close it (on Windows, Premiere or Resolve can hold '
                   'a LUT or a template) and run the update again. Nothing was changed.'
                   % (names(locked), 'is' if len(locked) == 1 else 'are'))
    moved, there = protect_untracked(root, mb)
    save_state(root, version=new_ver, head_before=before, upstream_before=up, moved=moved, adopted=adopted)
    register(root)

    # 3. Merge it in. A just-baselined project's conflicts mostly lack a base, and diff3 would show each
    # as one whole-file block; the plain style splits them line by line.
    git(root, 'update-ref', 'refs/tags/before-update-%s' % new_ver, before)
    rc, out, err = git_rc(root, '-c', 'core.excludesFile=' + rules,
                          '-c', 'merge.conflictStyle=' + ('merge' if adopted else 'diff3'),
                          'merge', '--no-ff', '--no-commit', '-m', 'Update to %s' % new_ver, UPSTREAM)
    files = unmerged(root) if in_progress(root) == 'merge' else []
    if rc and not files and in_progress(root) != 'merge':
        put_back(root, before, up, mb, moved, there)
        raise Fail('the update could not finish and was put back, so nothing changed:\n%s\nIf a file is open in '
                   'another app (on Windows, also check Controlled Folder Access for git.exe), close it and run '
                   'the update again.' % (err or out).strip())
    if force and newer(old_ver, new_ver) and in_progress(root) == 'merge':   # going back: the updater stays new
        tools = [f for f in ('update.py', '.claude/hooks/setup-check.sh') if f in paths_in(root, before)]
        git(root, 'checkout', before, '--', *tools)
        git(root, 'add', '--', *tools)
        files = [f for f in files if f not in tools]
    # A file the new version retired but the user changed keeps the user's copy: nothing to decide.
    status = dict((rec[3:], rec[:2]) for rec in zlist(git(root, 'status', '--porcelain', '-z')))
    kept = [f for f in files if status.get(f) == 'UD']
    if kept:
        git(root, 'add', '--', *kept)
        files = [f for f in files if f not in kept]
    lines = 0 if newer(old_ver, new_ver) else move_to_my_rules(root, mb, before, new_ver, files)
    files = [f for f in files if not (lines and f == 'CLAUDE.md')]
    notes = report(root, mb, before, old_ver, new_ver, src_dir, moved, bool(files))
    if lines:
        print('· The %s the user had added to CLAUDE.md (their brand identity or rules) moved to the end of '
              'my-rules.md, which no update changes, so CLAUDE.md took the new version cleanly.\n'
              % plural(lines, 'line'))
    update_state(root, notes=notes)
    if files:
        say_conflicts(root, files)
        return 3
    if in_progress(root) == 'merge':
        git(root, 'commit', '-q', '--no-edit')
    if force and newer(old_ver, new_ver):
        tools = [f for f in ('update.py', '.claude/hooks/setup-check.sh') if f in paths_in(root, before)]
        git(root, 'checkout', before, '--', *tools)
        if git_rc(root, 'diff', '--quiet', 'HEAD', '--', *tools)[0]:
            git(root, 'commit', '-q', '-m', 'Keep the newer updater after going back to %s' % new_ver, '--', *tools)
    return finish(root)


def relpath(root, f):
    """A file named any way (absolute, ./x, the path the conflict list printed) as a project path."""
    p = Path(f).expanduser()
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(root.resolve())
        except ValueError:
            try:
                p = p.relative_to(root)
            except ValueError:
                return None
    t = p.as_posix()
    return t[2:] if t.startswith('./') else t


def settle(root, files, side):
    """--keep-mine / --take-new: one side of a conflicted file, whole (for a binary, or by choice)."""
    kind = in_progress(root)
    if not kind and is_download(root):
        return settle(redirect_target(root, 'settling a conflict in'), files, side)
    if not kind:
        raise Fail('no update or undo is stopped on conflicts here')
    other = 'MERGE_HEAD' if kind == 'merge' else 'REVERT_HEAD'
    stopped = set(unmerged(root))
    try:
        stopped |= set((root / '.git' / CONFLICTS).read_text(encoding='utf-8').splitlines())
    except OSError:
        pass
    wanted = [relpath(root, f) for f in files]
    bad = [f for f, w in zip(files, wanted) if not w or w not in stopped]
    if bad:
        raise Fail('%s %s not one of the files the %s stopped on (%s); nothing changed'
                   % (', '.join(bad), 'is' if len(bad) == 1 else 'are', 'update' if kind == 'merge' else 'undo',
                      names(sorted(p for p in stopped if p))))
    for f in wanted:
        ref = 'HEAD' if side == 'mine' else other
        if kind == 'revert' and side == 'new':
            st = load_state(root)
            ref = (st.get('undone') or 'HEAD') + '^1'
        if git_rc(root, 'cat-file', '-e', '%s:%s' % (ref, f))[0] == 0:
            git(root, 'checkout', ref, '--', f)
        else:
            git_rc(root, 'rm', '-q', '--cached', '--', f)
            if (root / f).exists():
                (root / f).unlink()
        git(root, 'add', '-A', '--', f)
        print('✓ %s: %s' % (f, 'kept as it is in the project' if side == 'mine' else
                            ('took the new version' if kind == 'merge' else 'took the before-the-update version')))
    return 0


def cont(root):
    kind = in_progress(root)
    if not kind and is_download(root):
        return cont(redirect_target(root, 'continuing in'))
    if not kind:
        print('No update is in progress.')
        return 0
    clear_lock(root)
    listed = []
    try:
        listed = (root / '.git' / CONFLICTS).read_text(encoding='utf-8').splitlines()
    except OSError:
        pass
    conflicted = sorted(set(p for p in listed + unmerged(root) if p))
    left = [p for p in conflicted if has_markers(root / p)]
    status = dict((rec[3:], rec[:2]) for rec in zlist(git(root, 'status', '--porcelain', '-z')))
    # a file deleted on one side (or a binary) has no markers: it needs a decision, unless Claude deleted it
    undecided = [p for p in unmerged(root) if (is_binary(root / p) or status.get(p) in ('DU', 'UD', 'AU', 'UA'))
                 and (root / p).exists()]
    where = ('%s/' % root) if elsewhere(root) else ''
    if left or undecided:
        if left:
            print('Still has conflict markers, resolve these first: ' + names([where + p for p in left], 50))
        if undecided:
            print('No markers to resolve (a binary, or deleted on one side): pick a side first with `%s <file>` '
                  'or `%s <file>`, or delete the file to drop it: %s'
                  % (cmd(root, '--keep-mine'), cmd(root, '--take-new'), names([where + p for p in undecided], 50)))
        print('Markers: <<<<<<< HEAD = the project now · ======= · >>>>>>> = the %s side. Then `%s` again.'
              % ('new version' if kind == 'merge' else 'before-the-update', cmd(root, '--continue')))
        return 3
    # Only the conflicts (and what the merge itself staged) go into the update's commit; anything else
    # the user did meanwhile is a commit of its own, so an undo never takes it away.
    in_index = set(zlist(git(root, 'ls-files', '-z')))
    conflicted = [p for p in conflicted if (root / p).exists() or p in in_index]
    if conflicted:
        git(root, 'add', '-A', '--', *conflicted)
    if kind == 'revert':
        return commit_undo(root)
    git(root, 'commit', '-q', '--no-edit')
    rules = empty_excludes(root)
    leave_out_large(root, rules)
    git(root, '-c', 'core.excludesFile=' + rules, 'add', '-A')
    if git_rc(root, 'diff', '--cached', '--quiet')[0]:
        git(root, 'commit', '-q', '-m', 'Your changes while updating')
    print('✓ Update finished.')
    return finish(root, again=True)


def abort(root):
    kind = in_progress(root)
    if not kind and is_download(root):
        return abort(redirect_target(root, 'cancelling in'))
    if not kind:
        print('No update is in progress; nothing to cancel.')
        return 0
    clear_lock(root)
    git_rc(root, 'update-index', '-q', '--refresh')     # a folder copied mid-update has new file stamps
    st = load_state(root)
    if kind == 'merge':
        git(root, 'merge', '--abort')
        if st.get('upstream_before'):
            git(root, 'update-ref', UPSTREAM, st['upstream_before'])
        restore_moved(root, [tuple(m) for m in st.get('moved', [])])
    else:
        if git_rc(root, 'rev-parse', '-q', '--verify', 'REVERT_HEAD')[0] == 0:
            git_rc(root, 'revert', '--abort')
        git(root, 'reset', '-q', '--hard', 'HEAD')       # everything was committed before the undo began
    clear_state(root)
    print('✓ Cancelled: every file is back as it was before the %s. Run it again whenever you like.'
          % ('update' if kind == 'merge' else 'undo'))
    return 0


def last_update(root):
    """The newest 'Update to X' merge on the project's own line that has not been undone."""
    undone = set()
    for line in git(root, 'log', '--first-parent', '--format=%H %s', '-n', '500').splitlines():
        sha, _, subject = line.partition(' ')
        if subject.startswith('Revert "Update to '):
            undone.add(subject[len('Revert "'):].rstrip('"'))
        elif subject.startswith('Update to ') and subject not in undone:
            return sha, subject[len('Update to '):]
    return None, None


def undo(root):
    if in_progress(root):
        raise Fail('an update is stopped on conflicts: finish it with `%s`, or cancel it with `%s`'
                   % (cmd(root, '--continue'), cmd(root, '--abort')))
    if is_download(root):
        return undo(redirect_target(root, 'undoing the last update in'))
    if not (root / '.git').exists() or not rev(root, UPSTREAM):
        raise Fail('this project has no update to undo')
    clear_lock(root)
    m, version = last_update(root)
    if not m:
        raise Fail('this project has no update to undo')
    rules = empty_excludes(root)
    leave_out_large(root, rules)
    git(root, '-c', 'core.excludesFile=' + rules, 'add', '-A')
    if git_rc(root, 'diff', '--cached', '--quiet')[0]:
        git(root, 'commit', '-q', '-m', 'Your changes after updating to %s' % version)
    package = rev(root, m + '^2')
    prev = rev(root, package + '^1') if package else None
    brought = set(zlist(git(root, 'diff', '--name-only', '-z', merge_base(root, m + '^1', package), package))) \
        if package else set()
    save_state(root, kind='undo', version=version, undone=m, upstream_to=prev)
    git_rc(root, 'revert', '-m', '1', '--no-commit', m)
    # Only what the update brought goes back. Everything else the revert touched (work the user did while
    # that update was stopped), the user's own rules and the updater itself stay as they are now.
    touched = set(zlist(git(root, 'diff', '--name-only', '-z', 'HEAD'))) | set(unmerged(root))
    head_paths = paths_in(root, 'HEAD')
    keep = sorted(p for p in touched if (p in KEEP_ON_UNDO or p not in brought) and p in head_paths)
    if keep:
        git(root, 'checkout', 'HEAD', '--', *keep)
        git(root, 'add', '-A', '--', *keep)
    # The user's later state wins on files one side deleted: a file the update added and the user changed
    # since stays (UD), and one the user deleted since stays deleted (DU).
    status = dict((rec[3:], rec[:2]) for rec in zlist(git(root, 'status', '--porcelain', '-z')))
    stays = [p for p, s in status.items() if s == 'UD' and (root / p).exists()]
    if stays:
        git(root, 'add', '--', *stays)
    gone = [p for p, s in status.items() if s == 'DU']
    for p in gone:
        git_rc(root, 'rm', '-q', '-f', '--', p)
    if stays or gone:
        print('· Kept as they are now: %s' % names(stays + gone))
    files = unmerged(root)
    if files:
        update_state(root, stopped='undo')
        say_conflicts(root, files, 'revert')
        return 3
    return commit_undo(root)


def commit_undo(root):
    """Seal an undo. Its commit also names, as a second parent, a record of the package as the project
    now has it (the version before the update, plus what the undo kept of the update: the updater, and
    files the user went on to change), so taking the update again later merges those files instead of
    stopping on them as 'both added'."""
    st = load_state(root)
    package, prev = rev(root, st['undone'] + '^2'), st.get('upstream_to')
    now = git(root, 'write-tree').strip()
    kept = []
    if package and prev:
        was, then, final = blobs_at(root, prev), blobs_at(root, package), set(zlist(git(root, 'ls-tree', '-r',
                                                                                         '--name-only', '-z', now)))
        kept = [p for p in then if p not in was and p in final]
    record = prev
    if kept:
        entries = []
        for rec in zlist(git(root, 'ls-tree', '-r', '-z', prev)):
            meta, path = rec.split('\t', 1)
            mode, _t, sha = meta.split()
            entries.append((mode, sha, path))
        for rec in zlist(git(root, 'ls-tree', '-r', '-z', package, '--', *kept)):
            meta, path = rec.split('\t', 1)
            mode, _t, sha = meta.split()
            entries.append((mode, sha, path))
        record = commit(root, tree_from(root, entries, 'undo'), [prev],
                        'Package as the project has it after undoing %s' % st.get('version', ''))
    c = commit(root, now, [rev(root, 'HEAD')] + ([record] if record else []), 'Revert "Update to %s"' % st.get('version', ''))
    git(root, 'update-ref', 'HEAD', c)
    git_rc(root, 'revert', '--quit')
    for f in ('MERGE_MSG', 'REVERT_HEAD'):
        if (root / '.git' / f).exists():
            (root / '.git' / f).unlink()
    git(root, 'reset', '-q')
    update_state(root, upstream_to=record)
    return finish_undo(root)


def finish_undo(root):
    st = load_state(root)
    if st.get('upstream_to'):
        git(root, 'update-ref', UPSTREAM, st['upstream_to'])
    clear_state(root)
    try:
        rules = (root / 'my-rules.md').read_text(encoding='utf-8')
        claude = (root / 'CLAUDE.md').read_text(encoding='utf-8')
    except OSError:
        rules, claude = '', '@my-rules.md'
    if '@my-rules.md' not in claude:
        # the lines to copy: the user's own rules, never a heading, a "(from its ... section)" note, a line of the
        # shipped template, or one the restored CLAUDE.md already has (an update moved it out, the undo put it back)
        tmpl = set()
        for sha in existing(root, load_known(root)[0].get('my-rules.md', ())):
            tmpl |= set(git(root, 'cat-file', '-p', sha).splitlines())
        pkg = rev(root, st['undone'] + '^2') if st.get('undone') else None
        if pkg and git_rc(root, 'cat-file', '-e', pkg + ':my-rules.md')[0] == 0:
            tmpl |= set(git(root, 'show', pkg + ':my-rules.md').splitlines())
        have = {l.strip() for l in claude.splitlines()}
        left = [l.strip() for l in rules.splitlines()
                if l.strip() and not l.lstrip().startswith('#') and l not in tmpl
                and not re.fullmatch(r'\(from its ".*" section\)', l.strip()) and l.strip() not in have]
        if left:
            print('The restored version does not read my-rules.md: copy these %s from it into CLAUDE.md\'s Rules '
                  'section so they keep applying until the next update: %s'
                  % (plural(len(left), 'line'), '; '.join(left[:4]) + (' (and %d more)' % (len(left) - 4) if len(left) > 4 else '')))
    print('✓ Took %s back out: every file it brought is back as it was, and everything done since is kept '
          '(and so are my-rules.md and this updater). Run the update again whenever it is wanted.'
          % st.get('version', 'the last update'))
    print(next_steps(root, undo=True))
    return 0


def init(root):
    if not is_install(root):
        raise Fail('%s is not a client install; --init only runs in one' % root)
    if (root / '.git').exists() and rev(root, UPSTREAM):
        register(root)
        print('✓ updates: already set up')
        return 0
    ensure_repo(root)
    import_history(root, root)
    fp = load_known(root)
    leave_out_large(root, empty_excludes(root), set(fp[0]))
    own = fp[1].get(read_version(root)) or {}
    mine = baseline(root, fp, package={p: (None, b) for p, b in own.items()}, new_version=None)
    register(root)
    print('✓ updates: set up (a git baseline of this version), so a new version merges in without touching '
          'the user\'s changes' + (' (%s already differ%s from it: kept as theirs)'
                                   % (plural(mine, 'file'), 's' if mine == 1 else '') if mine else ''))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', nargs='?', help='the new version: its .zip or unzipped folder (default: the newest '
                                              'download)')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--continue', dest='cont', action='store_true', help='finish after resolving conflicts')
    g.add_argument('--abort', action='store_true', help='cancel an update or an undo that stopped on conflicts')
    g.add_argument('--undo', action='store_true', help='take the last update back out, keeping later changes')
    g.add_argument('--keep-mine', nargs='+', metavar='FILE', help='settle these conflicted files as they are now')
    g.add_argument('--take-new', nargs='+', metavar='FILE', help='settle these conflicted files with the other side')
    g.add_argument('--init', action='store_true', help='baseline this install (setup.sh runs it)')
    g.add_argument('--find-installs', action='store_true', help='print the set-up installs on this machine, one per line')
    ap.add_argument('--force', action='store_true', help='only when the user asked to go back to an older version')
    ap.add_argument('--project', default='.', help='the project folder (default: the current folder)')
    a = ap.parse_args(argv)
    root = Path(a.project).expanduser().resolve()
    if shutil.which('git') is None or subprocess.run(['git', '--version'], capture_output=True).returncode:
        print('✗ git is not installed, and updates run on it. macOS: xcode-select --install · '
              'Windows: winget install Git.Git · Linux: sudo apt install git', file=sys.stderr)
        return 1
    if a.find_installs:
        for p in projects_on_this_machine(root, skip_private=True):
            print(p)
        return 0
    try:
        if is_install(root) and set_up(root):
            register(root)       # a moved or copied project re-registers the first time it is used
        if a.cont:
            return cont(root)
        if a.abort:
            return abort(root)
        if a.undo:
            return undo(root)
        if a.keep_mine:
            return settle(root, a.keep_mine, 'mine')
        if a.take_new:
            return settle(root, a.take_new, 'new')
        if a.init:
            return init(root)
        return update(root, a.source, a.force)
    except Fail as e:
        sys.stdout.flush()
        print('✗ ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
