#!/usr/bin/env bash
# SessionStart hook: on a fresh install, inject a reminder telling Claude to run the
# onboarding/setup flow (CLAUDE.md "FIRST RUN" gate) before doing anything else. Emits NOTHING once
# setup is done and the toolchain is the one its self-test passed on. Always exits 0 so it can never break a session.
#
# Pure bash + printf on purpose (NO jq / python dependency), because on a brand-new machine those may
# not be installed yet, and this is the very hook that's supposed to get them installed. Runs on macOS,
# Linux, and Windows (Claude Code on Windows runs hooks through Git Bash, which ships with Git for
# Windows). If Git Bash itself is missing the hook can't fire — that front door lives in CLAUDE.md.
#
# cwd is the project root. "Setup done" = the .setup-complete marker exists (written by ./setup.sh
# once every core tool verifies) AND its lane= line is not "pending" (the which-app question, asked
# only when several editing apps are installed, has been answered with ./setup.sh --lane <pick>).
# Personalization (brand-kit.md) is OPTIONAL and never gates this; the editor works out of the box
# with the neutral bundled look.

if [ -f check-setup.sh ]; then
  # NOTE: newlines below are the literal two-character sequence \n (valid JSON string escapes); printf %s
  # passes them through verbatim, and there are no " or \ or apostrophe chars in the messages to break the JSON.
  msg=''
  # A set-up project registers itself (update.py keeps the same list), so a new version the user
  # downloads and opens by mistake can find it. Windows paths are stored the way Python writes them.
  reg="$HOME/.video-editor/installs"
  if [ -f .setup-complete ]; then
    here="$(pwd -P)"
    command -v cygpath >/dev/null 2>&1 && here="$(cygpath -w "$here")"
    { [ -f "$reg" ] && grep -qxF "$here" "$reg"; } || { mkdir -p "$HOME/.video-editor" && printf '%s\n' "$here" >> "$reg"; } 2>/dev/null
  fi
  if [ -f .git/MERGE_HEAD ]; then
    msg='⚠️ AN UPDATE STOPPED ON CONFLICTS and is not finished. Before anything else run: uv run update.py --continue. It lists the files that still hold conflict markers (CLAUDE.md can be one of them, so read it from disk); resolve them per CLAUDE.md § Updating, then run --continue again. uv run update.py --abort cancels the update instead.'
  elif [ -f .git/REVERT_HEAD ] || grep -qs '"stopped": "undo"' .git/ve-update-state.json; then
    msg='⚠️ AN UNDO OF THE LAST UPDATE STOPPED ON CONFLICTS and is not finished. Before anything else run: uv run update.py --continue. It lists the files still holding conflict markers; in each, take the before-the-update side, except for later edits the user made, then run --continue again. uv run update.py --abort cancels the undo instead.'
  elif [ -f .git/ve-update-state.json ]; then
    # the state file with no MERGE_HEAD / REVERT_HEAD: an update was killed half way (update.py puts it back first)
    msg='⚠️ AN UPDATE WAS INTERRUPTED and is not finished. Before anything else run: uv run update.py again. It puts the interrupted run back first, then updates.'
  elif [ ! -f .setup-complete ]; then
    # Another folder on this machine already takes updates: this one is most likely a NEW VERSION the
    # user downloaded and opened, not a second install. Only folders that still exist count.
    others=''
    if [ -f "$reg" ]; then
      while IFS= read -r line || [ -n "$line" ]; do
        line="$(printf '%s' "$line" | tr -d '\r\t')"
        [ -n "$line" ] || continue
        p="$line"; command -v cygpath >/dev/null 2>&1 && p="$(cygpath -u "$line" 2>/dev/null || printf '%s' "$line")"
        [ -f "$p/.setup-complete" ] || continue
        others="${others:+$others; }$line"
      done < "$reg"
      others="$(printf '%s' "$others" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    fi
    if [ -n "$others" ]; then
      msg='⚠️ NEW DOWNLOAD: this folder was never set up, and this machine already has the editor installed ('"$others"'). If the user wants to UPDATE, do not run setup here: run uv run update.py in this folder (it updates their project from this download), then tell them to reopen their project folder. Only if they want a second, separate install, follow FIRST RUN in CLAUDE.md.'
    else
      msg='⚠️ FRESH INSTALL: setup has not finished yet (no .setup-complete marker).\n\nFollow the FIRST RUN onboarding gate in CLAUDE.md before editing anything:\n  1. Run ./setup.sh yourself (no need to ask), with the Bash timeout at its maximum (600000 ms) or in the background: a first run on a fresh machine can take 10-20 minutes, and a run that is cut off is simply re-run. It detects the OS, installs every missing tool, bootstraps the render engine, verifies with ./check-setup.sh, then auto-detects an installed editing app (Premiere / Resolve / CapCut / Final Cut) and wires its lane. It is idempotent.\n  2. Handle its exit codes per the FIRST RUN gate in CLAUDE.md, step 1 — that block is the spec and it stays current; this reminder is only the nudge to go read it.\n  3. Brand kit is OPTIONAL: offer it once after tools pass; never block editing on it.\n\nIf the user asks to edit a video right now, run setup first (an edit cannot run without ffmpeg). If the user says they are UPDATING an editor they already use, do not run setup here: run uv run update.py in this folder, which finds their project and updates it from this download.'
    fi
  elif grep -qs '^failed=' .setup-complete; then
    lane="$(sed -n 's/^failed=//p' .setup-complete | head -n 1 | tr -cd 'a-z-')"
    msg='⚠️ SETUP ALMOST DONE: the '"$lane"' lane failed to install last time. Re-run ./setup.sh --lane '"$lane"' yourself and fix the installer error it prints (CLAUDE.md FIRST RUN step 1, exit 1).'
  elif grep -qs '^wait=' .setup-complete; then
    lane="$(sed -n 's/^wait=//p' .setup-complete | head -n 1 | tr -cd 'a-z-')"
    msg='⚠️ SETUP ALMOST DONE: the '"$lane"' lane is waiting on one click from the user (Final Cut: Continue in the SpliceKit window, with Final Cut quit). Ask whether that is done, then run ./setup.sh --lane '"$lane"' yourself (CLAUDE.md FIRST RUN step 2).'
  elif grep -qs '^lane=pending' .setup-complete; then
    msg='⚠️ SETUP ALMOST DONE: the tools are installed, but the editing-app pick is still open (.setup-complete says lane=pending). Several editing apps are installed on this machine. Ask the user in ONE line which one they edit in (run ./setup.sh to list the detected apps if unsure), then run ./setup.sh --lane <their pick> (premiere | resolve | capcut | finalcut | chat-only) (finalcut is macOS only; capcut runs on macOS and Windows). premiere/resolve/finalcut end with a Claude Code restart. See CLAUDE.md FIRST RUN step 2.'
  else
    # the marker holds the render-engine version it was set up for; a version bump needs the bootstrap again
    pin="$(grep -o 'HF_PIN="[0-9.]*"' setup.sh 2>/dev/null | head -n 1 | tr -cd '0-9.')"
    have_pin="$(cat .setup-hyperframes-ok 2>/dev/null | tr -cd '0-9.')"
    [ -f .setup-hyperframes-ok ] && [ -z "$have_pin" ] && have_pin=0.8.16   # every setup before 2026.09.25.3
    if [ ! -f .setup-hyperframes-ok ] || { [ -n "$pin" ] && [ "$have_pin" != "$pin" ]; }; then
      msg='⚠️ SETUP NOT QUITE DONE: the render engine is not set up for this version (no matching .setup-hyperframes-ok), so graphics cannot render yet. Re-run ./setup.sh yourself, with the Bash timeout at 600000 ms (it skips everything already done); if it fails, it is usually the network.'
    fi
    # The toolchain setup's self-test passed on (its ffmpeg=, uv=, node= lines) against this session's: a `brew upgrade`
    # since (Homebrew's ffmpeg 9 deleted -vsync under a working install, 2026-10-13) is re-tested before an edit runs on it.
    if [ -z "$msg" ] && grep -qs '^selftest=' .setup-complete; then
      changed=''
      for t in ffmpeg uv node; do
        case "$t" in
          ffmpeg) now="$(ffmpeg -version 2>/dev/null | head -n 1 | awk '{print $3}')" ;;
          uv)     now="$(uv --version 2>/dev/null | awk '{print $2}')" ;;
          node)   now="$(node -p 'process.versions.node' 2>/dev/null)" ;;
        esac
        was="$(sed -n "s/^$t=//p" .setup-complete | head -n 1 | tr -d '\r')"
        now="$(printf '%s' "$now" | tr -cd 'A-Za-z0-9._+-')"; was="$(printf '%s' "$was" | tr -cd 'A-Za-z0-9._+-')"
        [ -n "$now" ] && [ -n "$was" ] && [ "$now" != "$was" ] && changed="${changed:+$changed, }$t $was → $now"
      done
      if [ -n "$changed" ]; then
        msg='⚠️ THE TOOLCHAIN CHANGED SINCE SETUP ('"$changed"'). Before editing, run ./setup.sh yourself with the Bash timeout at 600000 ms: it skips everything already done, checks the new versions against what the editor needs, re-runs its 30-second self-test and records them. If it stops, fix what it names first.'
      fi
    fi
    # The Final Cut lane: lanes/finalcut/doctor.py says which copy is the lane's (lab-notes § 21). Exit 4: Final Cut
    # updated past its patched copy (the copy is a copy), the one SpliceKit click again; exit 3: a stale patched copy,
    # or a Final Cut that is not the lane's copy, is in the way. uv exists on any machine set up with lane=finalcut.
    if [ -z "$msg" ] && [ "$(uname -s)" = Darwin ] && grep -qs '^lane=finalcut' .setup-complete \
       && [ -f lanes/finalcut/doctor.py ] && command -v uv >/dev/null 2>&1; then
      rc=0; uv run --quiet lanes/finalcut/doctor.py >/dev/null 2>&1 || rc=$?
      if [ "$rc" = 4 ]; then
        msg='⚠️ FINAL CUT WAS UPDATED, the patched copy is an older version (or it is gone): run ./setup.sh --lane finalcut yourself and relay the one SpliceKit click it asks for.'
      elif [ "$rc" = 3 ]; then
        msg='⚠️ THE FINAL CUT LANE NEEDS A REPAIR: a stale patched copy of Final Cut, or a Final Cut that is not the lane copy, is in the way, or on an Intel Mac the copy still has Smooth Scroll on (uv run lanes/finalcut/doctor.py says which). Before any Final Cut work, run uv run lanes/finalcut/doctor.py --repair yourself: it quits the wrong Final Cut, moves stale copies to the Trash and launches the lane copy by its path. Never ask the user to quit and reopen Final Cut.'
      fi
    fi
  fi
  if [ -n "$msg" ]; then
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
  fi
  # Unsaved-to-git edits are snapshotted each session (no file is touched), so a new version later
  # unzipped OVER this folder cannot silently erase them: update.py restores from the snapshot. Never
  # over a folder that already holds a newer VERSION than its last update (that IS the overwrite), and
  # none kept once nothing is unsaved.
  if [ -f .git/refs/heads/upstream ] || grep -qs 'refs/heads/upstream' .git/packed-refs; then
    if [ "$(git -c safe.directory='*' show HEAD:VERSION 2>/dev/null)" = "$(cat VERSION 2>/dev/null)" ]; then
      snap="$(git -c core.hooksPath=/dev/null -c safe.directory='*' -c core.autocrlf=false stash create 2>/dev/null)"
      if [ -n "$snap" ]; then git -c safe.directory='*' update-ref refs/ve/snapshot "$snap" 2>/dev/null
      else git -c safe.directory='*' update-ref -d refs/ve/snapshot 2>/dev/null; fi
    fi
  fi
fi

exit 0
