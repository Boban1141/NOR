import AVFoundation
import Speech
import SwiftUI

@MainActor
final class Voice: NSObject, ObservableObject, ConversationAudio, AVSpeechSynthesizerDelegate {
    @Published var recording = false
    @Published var preparing = false
    @Published var transcript = ""
    private let engine = AVAudioEngine()
    private let synthesizer = AVSpeechSynthesizer()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var recognition: SFSpeechRecognitionTask?
    private var tapped = false
    private var generation: UUID?
    private var boundary: EndOfQuestion?
    private var silenceTask: Task<Void, Never>?
    private var onQuestion: ((String) -> Void)?
    private var onFailure: ((String) -> Void)?
    private var spokenUtterance: AVSpeechUtterance?
    private var speechCompletion: CheckedContinuation<Void, Error>?

    override init() {
        super.init()
        synthesizer.delegate = self
        NotificationCenter.default.addObserver(self, selector: #selector(interrupted(_:)),
            name: AVAudioSession.interruptionNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(routeChanged(_:)),
            name: AVAudioSession.routeChangeNotification, object: nil)
    }

    deinit { NotificationCenter.default.removeObserver(self) }

    func maleVoices(language: NORLanguage) -> [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices().filter { $0.gender == .male && $0.language.hasPrefix(language.rawValue) }
    }

    private func utterance(_ text: String, identifier: String, language: NORLanguage) throws -> AVSpeechUtterance {
        guard let voice = maleVoices(language: language).first(where: { $0.identifier == identifier }) ?? maleVoices(language: language).first else {
            throw NORFailure.message(language.text("Aucune voix masculine disponible pour cette langue. Ajoutez une voix dans Réglages iOS → Accessibilité → Contenu énoncé → Voix.", "No male voice is installed for this language. Add one in iOS Settings → Accessibility → Spoken Content → Voices."))
        }
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .spokenAudio)
        try session.setActive(true)
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = voice
        utterance.rate = 0.46
        return utterance
    }

    func speak(_ text: String, identifier: String, language: NORLanguage) throws {
        stop()
        let item = try utterance(text, identifier: identifier, language: language)
        spokenUtterance = item
        synthesizer.speak(item)
    }

    func speakAndWait(_ text: String, identifier: String, language: NORLanguage) async throws {
        try Task.checkCancellation()
        stop()
        let item = try utterance(text, identifier: identifier, language: language)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            spokenUtterance = item
            speechCompletion = continuation
            synthesizer.speak(item)
        }
        try Task.checkCancellation()
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor [weak self] in self?.completeSpeech(utterance, cancelled: false) }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor [weak self] in self?.completeSpeech(utterance, cancelled: true) }
    }

    private func completeSpeech(_ item: AVSpeechUtterance, cancelled: Bool) {
        guard spokenUtterance === item else { return }
        let continuation = speechCompletion
        speechCompletion = nil
        spokenUtterance = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        if cancelled { continuation?.resume(throwing: CancellationError()) }
        else { continuation?.resume() }
    }

    func startRecording(language: NORLanguage) async throws {
        try await beginRecording(language: language, silence: nil, onQuestion: nil, onFailure: nil)
    }

    func listen(language: NORLanguage, silence: TimeInterval,
                onQuestion: @escaping (String) -> Void, onFailure: @escaping (String) -> Void) async throws {
        try await beginRecording(language: language, silence: silence, onQuestion: onQuestion, onFailure: onFailure)
    }

    private func beginRecording(language: NORLanguage, silence: TimeInterval?,
                                onQuestion: ((String) -> Void)?, onFailure: ((String) -> Void)?) async throws {
        guard !preparing else { throw CancellationError() }
        stop()
        let current = UUID()
        generation = current
        preparing = true
        defer { preparing = false }
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
        }
        guard generation == current, !Task.isCancelled else { throw CancellationError() }
        guard speech == .authorized else { throw NORFailure.message(language.text("Autorisez la reconnaissance vocale dans les réglages iOS.", "Allow speech recognition in iOS Settings.")) }
        let microphone = await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { continuation.resume(returning: $0) }
        }
        guard generation == current, !Task.isCancelled else { throw CancellationError() }
        guard microphone else { throw NORFailure.message(language.text("Autorisez le microphone dans les réglages iOS.", "Allow microphone access in iOS Settings.")) }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: language.speechLocale)),
              recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else {
            throw NORFailure.message(language.text("La dictée locale de cette langue n’est pas disponible sur cet iPhone. Vous pouvez écrire votre question.", "On-device dictation for this language is unavailable on this iPhone. You can type your question."))
        }
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement, options: .duckOthers)
        try session.setActive(true)
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = true
        self.request = request
        self.onQuestion = onQuestion
        self.onFailure = onFailure
        if let silence { boundary = EndOfQuestion(now: ProcessInfo.processInfo.systemUptime, silence: silence) }
        transcript = ""
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else {
            stopRecording()
            throw NORFailure.message(language.text("Microphone indisponible.", "Microphone unavailable."))
        }
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            request.append(buffer)
            // Signal level supplements transcription updates: a slow recognizer
            // must not end a question while the person is still audibly speaking.
            guard let samples = buffer.floatChannelData?[0], buffer.frameLength > 0 else { return }
            var energy: Float = 0
            for index in 0..<Int(buffer.frameLength) { energy += samples[index] * samples[index] }
            if sqrt(energy / Float(buffer.frameLength)) > 0.012 {
                let now = ProcessInfo.processInfo.systemUptime
                Task { @MainActor [weak self] in
                    guard let self, self.generation == current else { return }
                    self.boundary?.audibleSpeech(now: now)
                }
            }
        }
        tapped = true
        recognition = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor [weak self] in
                guard let self, self.generation == current else { return }
                if let result {
                    self.transcript = result.bestTranscription.formattedString
                    self.boundary?.recognized(self.transcript, now: ProcessInfo.processInfo.systemUptime)
                }
                if error != nil {
                    let callback = self.onFailure
                    self.stopRecording()
                    callback?(language.text("La dictée a été interrompue. Votre texte est conservé ; réactivez le mode vocal ou envoyez-le manuellement.", "Dictation was interrupted. Your text is preserved; enable voice mode again or send it manually."))
                } else if result?.isFinal == true {
                    if let boundary = self.boundary {
                        if boundary.decision(now: ProcessInfo.processInfo.systemUptime) == .submit {
                            let callback = self.onQuestion
                            let text = self.transcript
                            self.stopRecording()
                            callback?(text)
                        } else {
                            // A recognizer that ended early cannot capture a
                            // continuation. Preserve the draft rather than send
                            // an incomplete question as though it were finished.
                            let callback = self.onFailure
                            self.stopRecording()
                            callback?(language.text("La dictée s’est arrêtée avant la pause prévue. Votre texte est conservé ; complétez-le ou envoyez-le manuellement.", "Dictation ended before the expected pause. Your text is preserved; complete it or send it manually."))
                        }
                    } else { self.stopRecording() }
                }
            }
        }
        do { engine.prepare(); try engine.start(); recording = true }
        catch { stopRecording(); throw error }
        if silence != nil {
            silenceTask = Task { [weak self] in
                while !Task.isCancelled {
                    do { try await Task.sleep(nanoseconds: 250_000_000) } catch { return }
                    guard let self, self.generation == current, let boundary = self.boundary else { return }
                    switch boundary.decision(now: ProcessInfo.processInfo.systemUptime) {
                    case .wait: continue
                    case .submit:
                        let callback = self.onQuestion
                        let text = self.transcript.trimmingCharacters(in: .whitespacesAndNewlines)
                        self.stopRecording()
                        callback?(text)
                        return
                    case .idleTimeout, .tooLong:
                        let callback = self.onFailure
                        self.stopRecording()
                        callback?(language.text("Écoute mise en pause. Votre texte est conservé ; réactivez le mode vocal ou envoyez-le manuellement.", "Listening paused. Your text is preserved; enable voice mode again or send it manually."))
                        return
                    }
                }
            }
        }
    }

    func stopRecording() {
        generation = nil
        silenceTask?.cancel()
        silenceTask = nil
        boundary = nil
        onQuestion = nil
        onFailure = nil
        engine.stop()
        if tapped { engine.inputNode.removeTap(onBus: 0); tapped = false }
        request?.endAudio()
        recognition?.cancel()
        recognition = nil
        request = nil
        recording = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    func stop() {
        stopRecording()
        let continuation = speechCompletion
        speechCompletion = nil
        spokenUtterance = nil
        synthesizer.stopSpeaking(at: .immediate)
        continuation?.resume(throwing: CancellationError())
    }

    @objc nonisolated private func interrupted(_ notification: Notification) {
        guard let value = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              value == AVAudioSession.InterruptionType.began.rawValue else { return }
        Task { @MainActor [weak self] in
            let callback = self?.onFailure
            self?.stop()
            callback?("Audio interrupted. / Audio interrompu.")
        }
    }

    @objc nonisolated private func routeChanged(_ notification: Notification) {
        guard let value = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
              value == AVAudioSession.RouteChangeReason.oldDeviceUnavailable.rawValue else { return }
        Task { @MainActor [weak self] in
            let callback = self?.onFailure
            self?.stop()
            callback?("Audio device disconnected. / Périphérique audio déconnecté.")
        }
    }
}
