# AGENTS.md

**Read [`CLAUDE.md`](CLAUDE.md) first, all of it.** It is this project's whole rulebook (setup, the
eight-step pipeline, the presets, the locks), written for Claude Code and binding on any agent working
here, Codex included; [`my-rules.md`](my-rules.md) holds the user's own rules and wins over it for their
videos. The skills it names live in `.claude/skills/<name>/SKILL.md`: read the one for the step before
acting.

## A change at review runs inline, never in a subagent

A step-7 change the user calls ("change this caption", "move that graphic", one graphic or one
caption) is made right here in the chat: edit the one comp or caption, re-render that one part,
re-place it, show it. Never spawn a subagent, helper or worker for it, and never re-run `edit-review`:
a subagent starts with no context and re-reads the whole job, so a one-line fix takes minutes and
burns usage. Subagents belong only where a skill spawns them (the rough cut's fresh-eyes pass and
`edit-review`'s one review round), on the chat's own model unless the user explicitly asks for
another (CLAUDE.md § Rules).

## Final Cut Pro (the `finalcut` lane): never quit-and-reopen

Final Cut runs one instance at a time, and the lane's patched copy (made by SpliceKit) shares the App
Store app's identity. So while the App Store Final Cut is open, every launch of the copy just brings the
App Store app forward, which has no bridge: the connection times out forever, and "quit and reopen Final
Cut" (from the Dock, by name, by bundle id or with computer use) brings the App Store app straight back.

- Start Final Cut ONLY with `uv run lanes/finalcut/doctor.py --repair`. It quits a Final Cut that is not
  the lane's copy, moves stale copies to the Trash, launches the one copy by its path and proves the
  bridge (`uv run lanes/finalcut/sk.py system.version`).
- **After two failed bridge connects** (`sk.py` exit 2, a SpliceKit tool timing out, "no windows
  available"), run that repair yourself. Never ask the user to quit and reopen Final Cut, SpliceKit or
  this agent, and never fall back to asking them to export XML by hand.
- The only thing the repair ever hands the user is SpliceKit's one click (exit 4): it has already quit
  Final Cut and opened SpliceKit, and it prints the exact message to relay. Then run the repair again.
- Drive Final Cut through the bridge (`lanes/finalcut/*.py`, the `splicekit` MCP), not computer use.
