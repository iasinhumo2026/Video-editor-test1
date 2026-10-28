#!/usr/bin/env python3
"""session-notes.py: the creator's own words from every Claude Code session on a job, for bake-preset.

    uv run .claude/skills/bake-preset/scripts/session-notes.py <job>
    uv run .claude/skills/bake-preset/scripts/session-notes.py <job> --sessions <folder>   # another session folder

Claude Code keeps each session as a .jsonl in <config>/projects/<this folder's full path, every character that is
not a letter or a digit turned into "-">, <config> being $CLAUDE_CONFIG_DIR or ~/.claude. A session counts when its
file names the job anywhere. From each, oldest first, this prints only what the creator TYPED, with its time: never
Claude's replies, tool output, injected skill text, task notifications, slash commands, subagent traffic or a
compaction summary. It is the record of every note and every "why" behind the edit, and after a compaction the only
one left of the early rounds. Codex keeps its sessions elsewhere, in another format: not read here.

Always exits 0, with one line saying so when no session matched (the sources are then RUN.md, review/ and the
conversation at hand); 2 = bad arguments.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows consoles default to a codepage that can't print every note
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[4]          # .claude/skills/bake-preset/scripts/ -> the editor folder
NOT_TYPED = ('<command-', '<local-command-', '<task-notification', '<bash-', '[Request interrupted')
REMINDER = re.compile(r'<system-reminder>.*?</system-reminder>', re.S)


def sessions_dir(root=ROOT):
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
    return config / 'projects' / re.sub(r'[^A-Za-z0-9]', '-', str(root))


def typed(entry):
    """The creator's typed text in one transcript entry, '' when the entry is anything else."""
    if (entry.get('type') != 'user' or entry.get('isMeta') or entry.get('isSidechain')
            or entry.get('isCompactSummary')):
        return ''
    origin = entry.get('origin')
    if isinstance(origin, dict) and origin.get('kind') != 'human':      # a task notification, another session
        return ''
    content = (entry.get('message') or {}).get('content')
    image = ''
    if isinstance(content, list):                                          # a tool result carries no text part
        parts = [c for c in content if isinstance(c, dict)]
        image = ' [+image]' if any(c.get('type') == 'image' for c in parts) else ''
        content = '\n'.join(c.get('text', '') for c in parts if c.get('type') == 'text')
    if not isinstance(content, str):
        return ''
    text = REMINDER.sub('', content).strip()
    return '' if not text or text.startswith(NOT_TYPED) else text + image


def notes(folder, job):
    """[(first time, session id, [(time, text), ...])] for every session in `folder` naming the job, oldest first."""
    named = re.compile(r'(?<![A-Za-z0-9_-])' + re.escape(job) + r'(?![A-Za-z0-9_-])')
    found = []
    for f in sorted(Path(folder).glob('*.jsonl')) if Path(folder).is_dir() else []:
        raw = f.read_text(encoding='utf-8', errors='replace')
        if not named.search(raw):
            continue
        turns = []
        for line in raw.splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            text = typed(entry) if isinstance(entry, dict) else ''
            if text:
                turns.append((str(entry.get('timestamp', ''))[:16].replace('T', ' '), text))
        if turns:
            found.append((turns[0][0], f.stem, turns))
    return sorted(found)


def main(argv=None):
    ap = argparse.ArgumentParser(description="The creator's own words from every Claude Code session on a job.")
    ap.add_argument('job', help='the job folder name under projects/')
    ap.add_argument('--sessions', type=Path, help="the session folder (default: this editor folder's, "
                                                  "under $CLAUDE_CONFIG_DIR or ~/.claude/projects/)")
    a = ap.parse_args(argv)
    folder = a.sessions or sessions_dir()
    found = notes(folder, a.job)
    if not found:
        print(f'No Claude Code session in {folder} names {a.job}: '
              'the sources are RUN.md, review/ and the conversation at hand.')
    for first, sid, turns in found:
        print(f'## session {sid[:8]} · {first} → {turns[-1][0]} · {len(turns)} message(s)\n')
        for when, text in turns:
            print(f'[{when}] {text}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
