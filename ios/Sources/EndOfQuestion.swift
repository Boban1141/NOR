import Foundation

/// Monotonic times supplied by the audio service; no network or timers here.
struct EndOfQuestion {
    enum Decision: Equatable { case wait, submit, idleTimeout, tooLong }
    let startedAt: TimeInterval
    let silence: TimeInterval
    private(set) var lastActivity: TimeInterval
    private(set) var text = ""

    init(now: TimeInterval, silence: TimeInterval) {
        startedAt = now
        lastActivity = now
        self.silence = min(6, max(2, silence))
    }

    mutating func recognized(_ value: String, now: TimeInterval) {
        let value = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if value != text { text = value; lastActivity = now }
    }

    mutating func audibleSpeech(now: TimeInterval) { lastActivity = now }

    func decision(now: TimeInterval) -> Decision {
        if now - startedAt >= 60 { return .tooLong }
        if text.count < 2 { return now - startedAt >= 25 ? .idleTimeout : .wait }
        return now - lastActivity >= silence ? .submit : .wait
    }
}
