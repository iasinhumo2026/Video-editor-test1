# Locked-screen Premiere control (scratch tools from the 2026-09-02 your-job run)

The working tool is **`lanes/premiere/premiere-dismiss.sh`** (detect a hidden modal via `sample`, post
Return to the pid until it is gone); it compiles `keypid.swift` from here on first use. Only `keypid.swift` proved useful: it posts a
bare key (36 = Return) to a pid via `CGEvent.postToPid`, which dismissed Premiere's native
"project appears to be damaged" alert while the Mac was password-locked. Four sibling tools
(AX menu press, AX window dump, Cmd+Q via postToPid, window-relative click via postToPid) did
NOT work under the lock and were deleted 2026-09-04 — do not re-try those approaches. Detect a hidden modal with `sample <pid> 1 -mayDie | grep -c RunModal`.
Build: `swiftc -O -o keypid keypid.swift`; use: `./keypid <pid> 36 pid`.
