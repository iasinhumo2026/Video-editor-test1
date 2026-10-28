#!/usr/bin/env python3
"""
apply-autostart-patch.py — make the MCP Bridge CEP panel start itself.

WHY
    Stock, the panel needs a human to open Window > Extensions > MCP Bridge (CEP) and click
    "Start Bridge" before ANY scripted Premiere work can happen — every session. Two small
    edits remove that: <StartOn> in the manifest opens the panel when Premiere activates, and
    a shim in bridge-cep.js starts the bridge once the panel loads.

    The edits live in cep-bridge-autostart.patch beside this file, but a `.patch` needs the
    `patch` binary (not present on every Windows box) and fails on any upstream line drift.
    This applies the same two changes by content instead: idempotent, no dependencies beyond
    python3, and safe to run on an already-patched panel.

    Run it after ANY of: a fresh `git clone` of the engine, an engine version bump, or a
    re-copy of cep-plugin/ into the CEP extensions directory. `setup-premiere.sh` calls it on
    a client's first run, which is why a client never has to click Start Bridge.

USAGE
    uv run lanes/premiere/premiere-templates/apply-autostart-patch.py <dir> [<dir>...]
        <dir> = a cep-plugin directory (vendor/premiere-mcp/cep-plugin) or an installed panel
                (~/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP)

    Exit 0 = patched or already patched. Exit 1 = a target it could not patch.
"""

import re
import sys
from pathlib import Path

MARK = "REPO-PATCH: autostart"

SHIM = '''

/* --- REPO-PATCH: autostart (video-editor) -------------------------------
   Starts the bridge on panel load so no human has to click "Start Bridge".
   Config (temp dir) is already loaded from disk by init() at construction.
   Idempotent: re-applying this file is safe, and the guard prevents a
   double-start if the panel is reloaded. Remove this block to restore the
   stock click-to-start behaviour. --------------------------------------- */
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        try {
            if (window.bridge && !window.bridge.isConnected) {
                window.bridge.log('Autostart (repo patch): starting bridge...', 'info');
                window.startBridge();
            }
        } catch (e) {
            if (window.bridge) window.bridge.log('Autostart failed: ' + e, 'error');
        }
    }, 1500);
});
'''

START_ON = """          <StartOn>
            <Event>com.adobe.csxs.events.ApplicationActivate</Event>
          </StartOn>
"""


def patch_js(path):
    src = path.read_text(encoding="utf-8")
    if MARK in src:
        return "already patched"
    # The shim only needs window.bridge and window.startBridge to exist by the time its
    # timeout fires, so appending at end of file is enough and is drift-proof.
    if "startBridge" not in src:
        return None
    # exactly one blank line before the block, so the result is byte-identical to the .patch
    path.write_text(src.rstrip("\n") + "\n\n" + SHIM.strip("\n") + "\n", encoding="utf-8")
    return "patched"


def patch_manifest(path):
    src = path.read_text(encoding="utf-8")
    if "StartOn" in src:
        return "already patched"
    # Anchor on <AutoVisible>, the one element the Lifecycle block is guaranteed to carry.
    m = re.search(r"[ \t]*<AutoVisible>[^<]*</AutoVisible>[ \t]*\r?\n", src)
    if not m:
        return None
    path.write_text(src[: m.end()] + START_ON + src[m.end() :], encoding="utf-8")
    return "patched"


def main():
    targets = [Path(a) for a in sys.argv[1:]]
    if not targets:
        sys.exit(__doc__.strip().splitlines()[-1])

    failed = 0
    for d in targets:
        js, mf = d / "bridge-cep.js", d / "CSXS" / "manifest.xml"
        if not js.is_file() or not mf.is_file():
            print("  ! not a CEP panel dir (need bridge-cep.js + CSXS/manifest.xml): %s" % d)
            failed += 1
            continue
        for label, path, fn in (("bridge-cep.js", js, patch_js), ("manifest.xml", mf, patch_manifest)):
            r = fn(path)
            if r is None:
                print("  ! could not patch %s in %s — the upstream file changed shape; "
                      "apply cep-bridge-autostart.patch by hand" % (label, d))
                failed += 1
            else:
                print("  autostart %-13s %s  (%s)" % (label, r, d))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
