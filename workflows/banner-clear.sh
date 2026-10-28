#!/bin/bash
# banner-clear.sh [timeout s=10]: wait until no macOS notification banner is on screen (exit 0), or give up (exit 1).
# Notification Center keeps one full-screen layer-21 window; a banner is opaque pixels in it, so its own buffer
# (screencapture -l, which reads a covered window) is transparent when no banner shows.
T="${1:-10}"; F="$(mktemp -t banner).png"
WID=$(osascript -l JavaScript -e 'ObjC.import("CoreGraphics");(ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll,0))).find(x=>x.kCGWindowOwnerName==="Notification Center")||{}).kCGWindowNumber||""')
[ -n "$WID" ] || exit 0
end=$(( $(date +%s) + T ))
while :; do
  screencapture -x -o -l"$WID" "$F" 2>/dev/null
  if python3 -c "
from PIL import Image; im=Image.open('$F').convert('RGBA'); a=im.getchannel('A'); import sys
sys.exit(0 if a.getextrema()[1] < 8 else 1)"; then rm -f "$F"; exit 0; fi
  [ "$(date +%s)" -ge "$end" ] && { rm -f "$F"; exit 1; }
  sleep 0.5
done
