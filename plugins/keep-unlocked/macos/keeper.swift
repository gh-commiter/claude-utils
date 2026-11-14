// keep-unlocked-keeper [-w pid]: keeps the Mac awake and unlocked until killed, or until pid exits.
// What caffeinate -dims does (assertions, released by the kernel when this process ends), plus every 60 s what
// caffeinate -u does and a mouse move to where the pointer already is: the screen saver and its lock follow the
// HID idle timer, which only a real input event resets. Posting events needs the Events permission; this binary
// is signed with a Developer ID, so the permission belongs to it alone (not to osascript, which any script runs).
import CoreGraphics
import Dispatch
import Foundation
import IOKit.pwr_mgt

let why = "keep-unlocked (Claude Code)" as CFString
var ids = [IOPMAssertionID]()
for type in [kIOPMAssertionTypePreventUserIdleDisplaySleep, kIOPMAssertionTypePreventUserIdleSystemSleep,
             kIOPMAssertionTypePreventSystemSleep, "PreventDiskIdle"] {
    var id = IOPMAssertionID(0)
    IOPMAssertionCreateWithName(type as CFString, IOPMAssertionLevel(kIOPMAssertionLevelOn), why, &id)
    ids.append(id)
}

var activity = IOPMAssertionID(0)
func nudge() {
    IOPMAssertionDeclareUserActivity(why, kIOPMUserActiveLocal, &activity)
    let here = CGEvent(source: nil)?.location ?? .zero
    CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: here, mouseButton: .left)?
        .post(tap: .cghidEventTap)
}
let timer = DispatchSource.makeTimerSource()
timer.schedule(deadline: .now(), repeating: 60)
timer.setEventHandler(handler: nudge)
timer.resume()

let args = CommandLine.arguments
var watch: DispatchSourceProcess?
if args.count == 3, args[1] == "-w", let pid = pid_t(args[2]) {
    if kill(pid, 0) != 0 && errno == ESRCH { exit(0) }
    watch = DispatchSource.makeProcessSource(identifier: pid, eventMask: .exit)
    watch!.setEventHandler { exit(0) }
    watch!.resume()
}
dispatchMain()
