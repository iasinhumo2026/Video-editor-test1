// glide.swift — scripted cursor choreography for a screen-recording take (macOS).
//
//   swiftc -O workflows/glide.swift -o <bin>        (screen-studio-take.mjs compiles and caches it)
//   <bin> park:1300,760 wait:0.8 mark:in move:606,352,1.3 wait:0.45 dclick scroll:20,1.5 mark:out
//
// Steps, in order (coordinates are GLOBAL points, origin top-left of the main display):
//   park:X,Y            put the cursor there instantly (a mouseMoved event, so the recorder logs it)
//   move:X,Y,SECONDS    glide there on an eased cubic bezier with a slight arc, posted at 120 Hz
//   wait:SECONDS        hold, with a resting hand's drift of up to 2 pt so the recorder keeps a live cursor
//   click | dclick      a real left click / double click (clickState 1 then 2) where the cursor is
//   rclick              a right click (a context menu opens at the cursor)
//   drag:X,Y,SECONDS    press where the cursor is, drag along the eased arc to X,Y, release (a file into an app)
//   type:TEXT           type TEXT (everything after the first colon, commas included) at a typing cadence
//   rate:BASE,JITTER    per-character typing delay for later type steps, in ms (default 30,40: about 40-80 ms a key)
//   key:COMBO           one key press, e.g. key:return, key:escape, key:cmd+shift+period, key:ctrl+c, key:cmd+shift+h
//                       (named keys, or any single US-layout character)
//   scroll:LINES,SECONDS  LINES wheel notches (positive = down) under the cursor, spread on the ease curve; the
//                       app smooth-scrolls each notch. Posted at the SESSION tap with no source: at the HID tap no
//                       scroll reached Chrome at all, pixel or line, fronted or not (2026-10-02)
//   pscroll:POINTS,SECONDS  a SMOOTH scroll: continuous pixel deltas at 120 Hz on the ease curve, the way a trackpad
//                       sends them (positive = down), so the page glides instead of stepping notch by notch
//                       (a slow scroll at the end of a static page take, 2026-10-07)
//   mark:NAME           print the wall-clock time and cursor position of this point (a zoom or trim edge)
//
// Every event line carries `unix=<ms>` (wall clock), so a caller can map it onto the recorder's own clock.
// The events are CGEvents posted at the HID tap: the recorder logs them exactly like a hand on the mouse,
// so its cursor smoothing and click-driven zooms apply. Posting needs Accessibility for the calling app.
import Foundation
import ApplicationServices

guard CGPreflightPostEventAccess() else {
    FileHandle.standardError.write("glide: this process may not post events (System Settings > Privacy & Security > Accessibility)\n".data(using: .utf8)!)
    exit(3)
}

let src = CGEventSource(stateID: .hidSystemState)
var pos = CGEvent(source: nil)!.location

func unixMs() -> Int { Int(Date().timeIntervalSince1970 * 1000) }
func say(_ s: String) { print("\(s) unix=\(unixMs())"); fflush(stdout) }

func post(_ type: CGEventType, _ p: CGPoint, clickState: Int64 = 0) {
    let e = CGEvent(mouseEventSource: src, mouseType: type, mouseCursorPosition: p, mouseButton: .left)!
    if clickState > 0 { e.setIntegerValueField(.mouseEventClickState, value: clickState) }
    e.post(tap: .cghidEventTap)
}

func ease(_ t: Double) -> Double { t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2 }

// run `body(i, t)` for i in 1...steps at 120 Hz, t = eased progress, sleeping to the schedule
func animate(_ seconds: Double, _ body: (Double) -> Void) {
    let steps = max(1, Int(seconds * 120))
    let start = Date()
    for i in 1...steps {
        body(ease(Double(i) / Double(steps)))
        let gap = start.addingTimeInterval(seconds * Double(i) / Double(steps)).timeIntervalSinceNow
        if gap > 0 { usleep(useconds_t(gap * 1_000_000)) }
    }
}

func move(to p3: CGPoint, seconds: Double, dragging: Bool = false) {
    let p0 = pos
    let dx = p3.x - p0.x, dy = p3.y - p0.y
    let dist = (dx * dx + dy * dy).squareRoot()
    let nx = dist > 0 ? -dy / dist : 0, ny = dist > 0 ? dx / dist : 0
    let bow = dist * 0.08  // the arc: both control points pushed sideways by 8 % of the distance
    let p1 = CGPoint(x: p0.x + dx / 3 + nx * bow, y: p0.y + dy / 3 + ny * bow)
    let p2 = CGPoint(x: p0.x + 2 * dx / 3 + nx * bow, y: p0.y + 2 * dy / 3 + ny * bow)
    animate(seconds) { t in
        let u = 1 - t
        post(dragging ? .leftMouseDragged : .mouseMoved, CGPoint(x: u*u*u*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t*t*t*p3.x,
                                  y: u*u*u*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t*t*t*p3.y))
    }
    pos = p3
}

// press where the cursor is, drag on the same eased arc to X,Y, release there (Finder file -> app drop)
func drag(to p: CGPoint, seconds: Double) {
    say("drag from \(Int(pos.x)),\(Int(pos.y))")
    post(.leftMouseDown, pos, clickState: 1); usleep(120_000)
    let start = pos
    post(.leftMouseDragged, CGPoint(x: start.x + 6, y: start.y + 4)); usleep(80_000)  // past the drag threshold
    move(to: p, seconds: seconds, dragging: true)
    usleep(120_000); post(.leftMouseUp, pos, clickState: 1)
}

func rclick() {
    say("rclick at \(Int(pos.x)),\(Int(pos.y))")
    for t in [CGEventType.rightMouseDown, .rightMouseUp] {
        CGEvent(mouseEventSource: src, mouseType: t, mouseCursorPosition: pos, mouseButton: .right)!.post(tap: .cghidEventTap)
        usleep(45_000)
    }
}

// virtual key codes (US layout) for key:COMBO; letters and digits beyond these go through type:
let keyCodes: [String: CGKeyCode] = ["return": 36, "enter": 36, "escape": 53, "esc": 53, "space": 49, "tab": 48,
    "delete": 51, "backspace": 51, "period": 47, "comma": 43, "slash": 44, "left": 123, "right": 124, "down": 125,
    "up": 126, "equal": 24, "minus": 27, "a": 0, "c": 8, "v": 9, "n": 45, "w": 13, "k": 40, "l": 37, "o": 31, "g": 5, "d": 2]
let modFlags: [String: CGEventFlags] = ["cmd": .maskCommand, "shift": .maskShift, "ctrl": .maskControl, "alt": .maskAlternate, "opt": .maskAlternate]

func key(_ combo: String) {
    let parts = combo.lowercased().split(separator: "+").map(String.init)
    guard let name = parts.last, let code = keyCodes[name] ?? (name.count == 1 ? plainKeys[name.first!] : nil) else {
        FileHandle.standardError.write("glide: unknown key \(combo)\n".data(using: .utf8)!); exit(2)
    }
    var flags = CGEventFlags()
    for m in parts.dropLast() {
        guard let f = modFlags[m] else { FileHandle.standardError.write("glide: unknown modifier \(m)\n".data(using: .utf8)!); exit(2) }
        flags.insert(f)
    }
    for down in [true, false] {
        let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down)!
        e.flags = flags
        e.post(tap: .cghidEventTap)
        usleep(30_000)
    }
}

// US-layout key codes, shifted where the character needs it. Real key codes, never a unicode string on key 0:
// Terminal dropped every unicode-string character of a take while still taking Return (2026-10-02).
let plainKeys: [Character: CGKeyCode] = ["a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50, " ": 49]
let shiftedKeys: [Character: Character] = ["!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8",
    "(": "9", ")": "0", "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\", ":": ";", "\"": "'", "<": ",", ">": ".", "?": "/", "~": "`"]

func keyFor(_ ch: Character) -> (CGKeyCode, Bool)? {
    if let k = plainKeys[ch] { return (k, false) }
    if let base = shiftedKeys[ch], let k = plainKeys[base] { return (k, true) }
    if ch.isUppercase, let lower = ch.lowercased().first, let k = plainKeys[lower] { return (k, true) }
    return nil
}

var typeBase = 30_000, typeJitter = 40_000   // per-character delay (us); "rate:BASE,JITTER" in ms changes it
func type(_ text: String) {
    var lcg: UInt32 = 7  // a fixed pseudo-random cadence: every take of the same text types identically
    for ch in text {
        guard let (code, shift) = keyFor(ch) else { continue }  // checked before the take starts
        for down in [true, false] {
            let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down)!
            e.flags = shift ? .maskShift : []
            e.post(tap: .cghidEventTap)
            usleep(12_000)
        }
        lcg = lcg &* 1103515245 &+ 12345
        usleep(useconds_t(typeBase + Int(lcg >> 16) % max(1, typeJitter)))  // about 40-80 ms a character by default
    }
}

// A hold keeps the cursor MOVING, a little: Screen Studio 4.0 draws the cursor sliding back to its pre-clip position
// once the clip's last real move has passed (2026-10-02: h07-b never reached its button, h10-b left Final Cut for the
// corner), and a sub-point nudge does not count as a move. So a hold is a resting hand's drift: whole-point steps of
// at most 2 pt round the resting point, every 0.1 s, ending exactly on it.
func hold(_ seconds: Double) {
    let start = Date(), end = start.addingTimeInterval(seconds)
    var last = CGPoint(x: -1, y: -1)
    while Date() < end {
        let t = Date().timeIntervalSince(start)
        let p = CGPoint(x: pos.x + (2 * sin(2 * Double.pi * t / 2.3)).rounded(), y: pos.y + (1.5 * sin(2 * Double.pi * t / 3.1)).rounded())
        if p != last { post(.mouseMoved, p); last = p }
        let left = end.timeIntervalSinceNow
        if left > 0 { usleep(useconds_t(min(0.1, left) * 1_000_000)) }
    }
    post(.mouseMoved, pos)
}

func click(times: Int) {
    say("click x\(times) at \(Int(pos.x)),\(Int(pos.y))")
    for n in 1...times {
        post(.leftMouseDown, pos, clickState: Int64(n)); usleep(45_000)
        post(.leftMouseUp, pos, clickState: Int64(n))
        if n < times { usleep(90_000) }
    }
}

func scroll(_ lines: Int, seconds: Double) {
    let n = abs(lines), notch: Int32 = lines > 0 ? -1 : 1  // a negative wheel delta scrolls the content down
    var sent = 0
    animate(seconds) { t in
        while sent < Int((Double(n) * t).rounded()) {
            // no source, the SESSION tap, explicitly non-continuous: the HID-tap form never reached Chrome (2026-10-02)
            if let e = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: notch, wheel2: 0, wheel3: 0) {
                e.setIntegerValueField(.scrollWheelEventIsContinuous, value: 0)
                e.location = pos
                e.post(tap: .cgSessionEventTap)
            }
            sent += 1
        }
    }
}

func pscroll(_ points: Double, seconds: Double) {
    var sent = 0.0
    animate(seconds) { t in
        let d = Int32((points * t - sent).rounded())
        if d != 0, let e = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 1, wheel1: -d, wheel2: 0, wheel3: 0) {
            e.setIntegerValueField(.scrollWheelEventIsContinuous, value: 1)
            e.location = pos
            e.post(tap: .cgSessionEventTap)
            sent += Double(d)
        }
    }
}

// every step is checked before the first event is posted: a typo never stops a take halfway
let known = Set(["park", "move", "wait", "click", "dclick", "rclick", "scroll", "pscroll", "type", "key", "mark", "rate", "drag"])
for step in CommandLine.arguments.dropFirst() {
    let parts = step.split(separator: ":", maxSplits: 1).map(String.init)
    let need = ["park": 2, "move": 3, "wait": 1, "scroll": 2, "pscroll": 2, "rate": 2, "drag": 3][parts[0]] ?? 0
    var bad = !known.contains(parts[0])
    if need > 0 { bad = bad || (parts.count < 2 ? [] : parts[1].split(separator: ",").compactMap { Double($0) }).count < need }
    if parts[0] == "type", parts.count > 1, let bad1 = parts[1].first(where: { keyFor($0) == nil }) {
        FileHandle.standardError.write("glide: cannot type \"\(bad1)\" (US-layout keys only) in \(step)\n".data(using: .utf8)!); exit(2)
    }
    if parts[0] == "key", parts.count > 1 {
        let ks = parts[1].lowercased().split(separator: "+").map(String.init)
        let last = ks.last ?? ""
        bad = bad || (keyCodes[last] == nil && !(last.count == 1 && plainKeys[last.first!] != nil)) || ks.dropLast().contains { modFlags[$0] == nil }
    }
    if bad { FileHandle.standardError.write("glide: bad step \(step)\n".data(using: .utf8)!); exit(2) }
}

say("start")
for step in CommandLine.arguments.dropFirst() {
    let parts = step.split(separator: ":", maxSplits: 1).map(String.init)
    let args = parts.count > 1 ? parts[1] : ""
    let n = args.split(separator: ",").compactMap { Double($0) }
    func need(_ k: Int) { if n.count < k { FileHandle.standardError.write("glide: bad step \(step)\n".data(using: .utf8)!); exit(2) } }
    switch parts[0] {
    case "park": need(2); pos = CGPoint(x: n[0], y: n[1]); post(.mouseMoved, pos)
    case "move": need(3); move(to: CGPoint(x: n[0], y: n[1]), seconds: n[2])
    case "wait": need(1); hold(n[0])
    case "click": click(times: 1)
    case "dclick": click(times: 2)
    case "scroll": need(2); scroll(Int(n[0]), seconds: n[1])
    case "pscroll": need(2); pscroll(n[0], seconds: n[1])
    case "rclick": rclick()
    case "drag": need(3); drag(to: CGPoint(x: n[0], y: n[1]), seconds: n[2])
    case "type": type(args)
    case "rate": need(2); typeBase = Int(n[0] * 1000); typeJitter = Int(n[1] * 1000)
    case "key": key(args)
    case "mark": say("mark \(args) at \(Int(pos.x)),\(Int(pos.y))")
    default: FileHandle.standardError.write("glide: unknown step \(step)\n".data(using: .utf8)!); exit(2)
    }
}
say("end")
