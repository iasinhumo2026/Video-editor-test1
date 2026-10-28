#!/usr/bin/env bash
# finalize.sh <job> — the EXPORT step. Make a finished job's outputs/ unambiguous.
#
# When a job is DONE, this promotes the real final render to ONE clear deliverable
# and retires the dead drafts — so there's never confusion about which file ships.
# It also drops a copy in ~/Downloads (the "export") so the finished file is ready to grab/upload.
# It does NOT nuke the job: everything you'd need to come back and re-edit is kept.
#
# The convention it enforces in projects/<job>/outputs/:
#   <job>.final.mp4         <- THE deliverable. Ship this. (promoted from the latest render)
#   <job>.mp4              <- clean base cut (re-edit / re-caption input) — KEPT
#   <job>.transcript.json  <- KEPT
# And it leaves the hf-graphics/ SOURCE (build.py, compositions/, parts.json, PROJECT.md)
# fully intact, so the whole graphics build can be reopened and tweaked later.
#
# It does NOT reclaim disk space: a cold job leaves the working drive whole, by hand
# (to cold storage, or to the Trash).
#
# Default is a DRY RUN — it only reports the plan. Add --apply to actually do it.
#   ./finalize.sh <job>                          # show the plan
#   ./finalize.sh <job> --apply                  # promote the final + delete drafts
#   ./finalize.sh <job> --apply --keep-drafts    # promote + export copy; nothing in outputs/ deleted
#   ./finalize.sh <job> --variant ad --apply     # a second deliverable living in outputs/ad/
#
# --keep-drafts: for runs that may not hard-delete. Every would-be DELETE (old drafts, superseded
#   renders) is reported as KEEP and left on disk, and an older <job>.final.mp4 that a newer pick
#   replaces is first moved aside to <job>.draft-prev.mp4 (-2, -3.. if taken): a draft name, so it is
#   never promoted and a later plain --apply retires it like any draft. The creator removes them.
# outputs/<job>.mp4 newer than every render and the final = probably an app export on the base-cut
#   name: finalize warns, and --apply refuses (nothing moved, deleted or exported) until it's renamed.
# --variant NAME: works ONLY inside outputs/NAME/ (never outputs/*.mp4): the deliverable is
#   outputs/NAME/<job>.NAME.final.mp4, the family is <job>.NAME* / <job>-NAME*, the export copy is
#   <job>.NAME.final.mp4. A variant folder has no base cut, so <job>.NAME.mp4 is an ordinary render.
#   A plain run never looks inside outputs/NAME/.
# A render that runs more than 20 % shorter or longer than the deliverable is ANOTHER deliverable (a reel, an intro
#   clip), never its next version: finalize warns and --apply refuses to promote it over the final, and it is never
#   deleted as a superseded render. Move it into outputs/NAME/ and finalize it with --variant NAME. (2026-09-28: an
#   82 s IG intro cut from a 14 min master sat newer in outputs/, and a plain --apply would have shipped it as the
#   master, over its Downloads copy.) "final" and "draft" are read in the name AFTER the job's own, so a job named
#   for its subject ("<x>-final-cut-pro") does not make every render in it final-named.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USAGE="usage: ./finalize.sh <job> [--apply] [--keep-drafts] [--variant NAME]"
JOB=""
APPLY=0
KEEP_DRAFTS=0
VARIANT=""
VARIANT_SET=0
# Unknown flags are refused, never ignored: a mistyped --keep-drafts next to --apply would
# otherwise delete exactly what it was meant to keep.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --keep-drafts) KEEP_DRAFTS=1 ;;
    --variant) [[ $# -ge 2 ]] || { echo "$USAGE"; exit 1; }; VARIANT="$2"; VARIANT_SET=1; shift ;;
    --variant=*) VARIANT="${1#--variant=}"; VARIANT_SET=1 ;;
    -*) echo "unknown option: $1"; echo "$USAGE"; exit 1 ;;
    *) [[ -z "$JOB" ]] || { echo "unexpected argument: $1"; echo "$USAGE"; exit 1; }; JOB="$1" ;;
  esac
  shift
done

[[ -n "$JOB" ]] || { echo "$USAGE"; exit 1; }
# An empty name is refused too: dropping it would run the ORGANIC flow on outputs/*.mp4.
if [[ $VARIANT_SET -eq 1 ]]; then
  [[ -n "$VARIANT" && "$VARIANT" != -* && "$VARIANT" != .* && "$VARIANT" != */* ]] \
    || { echo "bad --variant name '$VARIANT' (a folder name under outputs/)"; exit 1; }
fi

if [[ -n "$VARIANT" ]]; then
  REL="outputs/$VARIANT"
  BASE=""                                   # no clean base cut inside a variant folder
  DELIVERABLE="$JOB.$VARIANT.final.mp4"
  in_family() { case "$(basename "$1")" in "$JOB.$VARIANT"*|"$JOB-$VARIANT"*) return 0 ;; esac; return 1; }
else
  REL="outputs"
  BASE="$JOB.mp4"
  DELIVERABLE="$JOB.final.mp4"
  in_family() { [[ "$(basename "$1")" == "$JOB"* ]]; }
fi

OUT="$REPO/projects/$JOB/$REL"
[[ -d "$OUT" ]] || { echo "No $REL/ for job '$JOB' at $OUT"; exit 1; }

size() { du -h "$1" 2>/dev/null | cut -f1; }

echo "=== finalize: $JOB${VARIANT:+ (variant: $VARIANT)} ==="

DELIV_PATH="$OUT/$DELIVERABLE"
tail_name() { local b; b="$(basename "$1")"; printf '%s' "${b#"$JOB"}"; }   # the name after the job's own
is_final_named() { [[ "$(tail_name "$1")" == *final* ]]; }   # contains "final" (past the job name)
is_draft_named() { [[ "$(tail_name "$1")" == *draft* ]]; }   # contains "draft" (past the job name)
# a render's duration in seconds, "" when ffprobe cannot read it (never fails: set -e runs this script)
dur() { local d; d="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null | tr -d '\r' | head -n 1 || true)"
        if [[ "$d" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then printf '%s' "$d"; fi; return 0; }
# true when $1 runs more than 20 % shorter or longer than $2 (both readable): another deliverable, not a new version
other_length() { local a b; a="$(dur "$1")"; b="$(dur "$2")"; [[ -n "$a" && -n "$b" ]] &&
                 awk -v a="$a" -v b="$b" 'BEGIN { exit !(a > 0 && b > 0 && (a < b ? a / b : b / a) < 0.8) }'; }
# echo the newest path (by mtime) among the args, "" if none. Portable `-nt` test (bash builtin).
newest_of() { local best="" g; for g in "$@"; do if [[ -z "$best" || "$g" -nt "$best" ]]; then best="$g"; fi; done; printf '%s' "$best"; }

# All render candidates = *.mp4 in outputs/ except the clean base cut and the canonical
# deliverable itself (<job>.final.mp4 is the "incumbent", reconciled below).
# (while-read, not `mapfile` — mapfile is bash 4+, absent in macOS's default /bin/bash 3.2.)
cands=()
while IFS= read -r f; do cands+=("$f"); done < <(find "$OUT" -maxdepth 1 -type f -name '*.mp4' \
  ! -name "$BASE" ! -name "$DELIVERABLE" | sort)

# The base-name collision: an app export written to outputs/<job>.mp4 is excluded above as the
# base cut, so nothing would ever promote it. When the base is strictly newer than every render
# AND the deliverable, say so before the plan. Never auto-promoted, and --apply stops HERE, before
# any mv/rm/cp: promoting an older render (or exporting the incumbent) would ship a stale file.
base_newest=0
if [[ -n "$BASE" && -f "$OUT/$BASE" ]]; then
  base_newest=1
  for f in ${cands[@]+"${cands[@]}"} "$DELIV_PATH"; do
    if [[ -e "$f" && ! "$OUT/$BASE" -nt "$f" ]]; then base_newest=0; fi
  done
fi
if [[ $base_newest -eq 1 ]]; then
  echo "  ⚠ outputs/$BASE is the newest render: if it is an app export (not the clean base cut), rename it $JOB-final.mp4 and re-run"
  if [[ $APPLY -eq 1 ]]; then
    echo "    Refusing --apply: nothing promoted, deleted or exported. If it IS the clean base cut, every render"
    echo "    predates it (re-render), or, if it ships as is, cp it to $DELIVERABLE."
    exit 1
  fi
  echo "    (--apply refuses while it is)"
  echo
fi

# Candidates eligible to BECOME the deliverable = everything that isn't an explicit *draft*.
# A *graphics* render is NOT special: it's a mid-pipeline (pre-caption) stage that a newer
# captioned/music/-vN render supersedes. The old logic ranked *graphics* above newest-mtime,
# which is exactly what promoted a graphics-only draft over the real captioned+music final
# (and then deleted the music cut). (${arr[@]+"${arr[@]}"} = empty-array-safe expansion.)
pickable=()
for f in ${cands[@]+"${cands[@]}"}; do is_draft_named "$f" || pickable+=("$f"); done

# Pick the best candidate, in order:
#   1. an explicit *final*-named render (newest such), e.g. <job>-final.mp4
#   2. else the NEWEST render in the job-name family (basename starts with <job>) — so a
#      newer -music / -captioned / -vN beats an older -graphics draft, and a stray
#      non-family fragment (e.g. hook-v5.mp4) can never be promoted
#   3. else the newest render overall
pick=""
if [[ ${#pickable[@]} -gt 0 ]]; then
  finalnamed=()
  for f in "${pickable[@]}"; do is_final_named "$f" && finalnamed+=("$f"); done
  if [[ ${#finalnamed[@]} -gt 0 ]]; then
    pick="$(newest_of "${finalnamed[@]}")"
  else
    family=()
    for f in "${pickable[@]}"; do in_family "$f" && family+=("$f"); done
    if [[ ${#family[@]} -gt 0 ]]; then pick="$(newest_of "${family[@]}")"
    else pick="$(newest_of "${pickable[@]}")"; fi
  fi
fi

# THE LENGTH GUARD: a pick that runs much shorter or longer than the incumbent is another deliverable. Warned before
# the plan, and --apply stops HERE, before any mv/rm/cp (the base-name collision's pattern above).
if [[ -n "$pick" && -f "$DELIV_PATH" && "$pick" -nt "$DELIV_PATH" ]] && other_length "$pick" "$DELIV_PATH"; then
  echo "  ⚠ $(basename "$pick") runs $(dur "$pick" | cut -d. -f1) s, $DELIVERABLE $(dur "$DELIV_PATH" | cut -d. -f1) s: a render that much"
  echo "    shorter or longer is ANOTHER deliverable (a reel, an intro clip), not the next version of this one. Move it to"
  echo "    outputs/<name>/ and finalize it with --variant <name>; if it really is the new deliverable, move $DELIVERABLE aside first."
  if [[ $APPLY -eq 1 ]]; then
    echo "    Refusing --apply: nothing promoted, deleted or exported."
    exit 1
  fi
  echo "    (--apply refuses while it is)"
  echo
fi

# Reconcile with the incumbent <job>.final.mp4. THE GUARD: never overwrite an existing final
# with an OLDER pick. Only promote when there's no final yet, or the pick is strictly NEWER
# than the current final. (This is what stops a graphics draft clobbering a real deliverable.)
promote=""
kept_drafts=0                             # renders --keep-drafts leaves on disk (reported in the summary)
if [[ -f "$DELIV_PATH" ]]; then
  if [[ -n "$pick" && "$pick" -nt "$DELIV_PATH" ]]; then
    promote="$pick"
    if [[ $KEEP_DRAFTS -eq 1 ]]; then
      # the incumbent is a render too: move it aside under a free draft name instead of overwriting it
      prev="${DELIVERABLE%.final.mp4}.draft-prev"; aside="$prev.mp4"; n=2
      while [[ -e "$OUT/$aside" ]]; do aside="$prev-$n.mp4"; n=$((n + 1)); done
      echo "  KEEP    $DELIVERABLE  ->  $aside   (--keep-drafts; previous deliverable, $(size "$DELIV_PATH"))"
      kept_drafts=$((kept_drafts + 1))
      [[ $APPLY -eq 1 ]] && mv "$DELIV_PATH" "$OUT/$aside"
    fi
    echo "  PROMOTE $(basename "$pick")  ->  $DELIVERABLE   (newer than current final, $(size "$pick"))"
    [[ $APPLY -eq 1 ]] && mv -f "$pick" "$DELIV_PATH"
  else
    echo "  KEEP    $DELIVERABLE   (already the deliverable, $(size "$DELIV_PATH"))"
  fi
elif [[ -n "$pick" ]]; then
  promote="$pick"
  echo "  PROMOTE $(basename "$pick")  ->  $DELIVERABLE   ($(size "$pick"))"
  [[ $APPLY -eq 1 ]] && mv -f "$pick" "$DELIV_PATH"
fi

# Reference file whose mtime defines "the deliverable" (for the never-delete-newer guard).
# After an --apply promote the pick was moved onto DELIV_PATH (newest); in a dry run, or when
# no final exists, the pick itself. A pending promote is the reference in a dry run even when an
# older final exists: that final is what --apply replaces, and judging against it made the dry run
# say KEEP ("newer than the deliverable") for a draft the --apply then deleted (2026-10-13).
ref=""
if [[ -n "$promote" && -e "$promote" ]]; then ref="$promote"
elif [[ -e "$DELIV_PATH" ]]; then ref="$DELIV_PATH"; fi

# Retire the rest. Guards, in order:
#   - skip the promoted pick (it's been moved onto the deliverable)
#   - never delete another *final*-named render (anomalous — let a human decide)
#   - never delete a render NEWER than the deliverable we're shipping (it may be the real final)
#   - everything else (older drafts / superseded renders) is deleted — or, with --keep-drafts,
#     reported as KEEP and left where it is
for f in ${cands[@]+"${cands[@]}"}; do
  [[ -n "$promote" && "$f" == "$promote" ]] && continue
  [[ -e "$f" ]] || continue
  b=$(basename "$f")
  if is_final_named "$f"; then
    echo "  KEEP    $b   (also looks final — NOT deleting; remove by hand if dead)"
    continue
  fi
  if [[ -n "$ref" ]] && other_length "$f" "$ref"; then
    echo "  KEEP    $b   (runs $(dur "$f" | cut -d. -f1) s against the deliverable's $(dur "$ref" | cut -d. -f1) s: another deliverable, NOT deleting; move it to outputs/<name>/)"
    continue
  fi
  if [[ -n "$ref" && "$f" -nt "$ref" ]]; then
    echo "  KEEP    $b   (newer than the deliverable — NOT deleting; promote it by hand if it's the real final)"
    continue
  fi
  if is_draft_named "$f"; then why="draft, $(size "$f")"; else why="superseded render, $(size "$f")"; fi
  if [[ $KEEP_DRAFTS -eq 1 ]]; then
    echo "  KEEP    $b   (--keep-drafts; $why)"
    kept_drafts=$((kept_drafts + 1))
    continue
  fi
  echo "  DELETE  $b   ($why)"
  [[ $APPLY -eq 1 ]] && rm -f "$f"
done

# Report what's kept for re-editing.
[[ -n "$BASE" && -f "$OUT/$BASE" ]]  && echo "  KEEP    $BASE   (clean base cut for re-edit, $(size "$OUT/$BASE"))"
[[ -f "$OUT/$JOB.transcript.json" ]]  && echo "  KEEP    $JOB.transcript.json"
[[ -d "$REPO/projects/$JOB/hf-graphics" ]] && echo "  KEEP    hf-graphics/ source (build.py + compositions — reopen to re-edit)"

if [[ -z "$pick" && ! -f "$OUT/$DELIVERABLE" ]]; then
  echo
  if [[ -n "$BASE" ]]; then
    echo "  ⚠ No render found to promote. If $BASE itself is the deliverable (e.g. a no-graphics raw cut),"
    echo "    copy it: cp \"$OUT/$BASE\" \"$OUT/$DELIVERABLE\""
  else
    echo "  ⚠ No render found to promote in $REL/."
  fi
fi

# Export copy → Downloads, so the finished file is ready to grab/upload ("exporting").
# Override with VE_EXPORT_DIR. On WSL2 ~/Downloads is the Linux home (invisible in Windows
# Explorer), so default to the Windows user's Downloads when we can resolve it.
DL="${VE_EXPORT_DIR:-$HOME/Downloads}"
if [[ -z "${VE_EXPORT_DIR:-}" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  WINHOME="$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')" 2>/dev/null || true)"
  [[ -n "$WINHOME" && -d "$WINHOME/Downloads" ]] && DL="$WINHOME/Downloads"
fi
EXPORTED=0
if [[ -f "$DELIV_PATH" || -n "$promote" ]]; then
  if [[ $APPLY -eq 1 ]]; then
    if [[ -d "$DL" ]]; then
      cp -f "$DELIV_PATH" "$DL/$DELIVERABLE" && EXPORTED=1 \
        && echo "  EXPORT  $DELIVERABLE  ->  $DL/$DELIVERABLE   ($(size "$DELIV_PATH"))"
    else
      echo "  ⚠ $DL not found — skipped Downloads export copy"
    fi
  else
    echo "  EXPORT  $DELIVERABLE  ->  $DL/$DELIVERABLE   (Downloads copy)"
  fi
fi

echo
if [[ $APPLY -eq 1 ]]; then
  echo "Done. Deliverable: projects/$JOB/$REL/$DELIVERABLE"
  if [[ $EXPORTED -eq 1 ]]; then echo "      Exported copy: $DL/$DELIVERABLE"; fi
  if [[ $kept_drafts -gt 0 ]]; then echo "      Kept $kept_drafts old render(s) in $REL/ (--keep-drafts): remove them by hand once they're dead"; fi
  # the edit is finished: what it taught goes into the preset now or never (2026-10-13), so the offer rides here
  if [[ -f "$DELIV_PATH" ]]; then
    echo "Next: offer to bake this edit's creative calls into its preset (skill bake-preset), so the next video like it comes out right first try"
  fi
else
  echo "DRY RUN — nothing changed. Re-run with --apply to do it."
fi
exit 0
