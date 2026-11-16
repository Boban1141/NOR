import Foundation
import Combine

@MainActor
protocol ConversationAudio: AnyObject {
    func listen(language: NORLanguage, silence: TimeInterval,
                onQuestion: @escaping (String) -> Void,
                onFailure: @escaping (String) -> Void) async throws
    func speakAndWait(_ text: String, identifier: String, language: NORLanguage) async throws
    func stop()
}

struct ConversationConfiguration {
    let endpoint: String
    let token: String
    let language: NORLanguage
    let voiceID: String
    let refresh: Bool
    let silence: TimeInterval
}

@MainActor
final class AutomaticConversation: ObservableObject {
    enum Phase: Equatable { case idle, listening, acknowledging, researching, speaking }
    @Published private(set) var active = false
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var failure: String?
    private let audio: ConversationAudio
    private let researcher: (String, ConversationConfiguration) async throws -> ResearchResponse
    private var run = UUID()
    private var workflow: Task<Void, Never>?

    init(audio: ConversationAudio,
         researcher: @escaping (String, ConversationConfiguration) async throws -> ResearchResponse = { question, configuration in
             try await ResearchAPI.ask(question, endpoint: configuration.endpoint, token: configuration.token,
                                       language: configuration.language, refresh: configuration.refresh)
         }) {
        self.audio = audio
        self.researcher = researcher
    }

    static func acknowledgement(_ language: NORLanguage) -> String {
        language.text("D’accord, laisse-moi un instant pour examiner les sources.",
                      "Alright, give me a moment to review the sources.")
    }

    static func followup(_ language: NORLanguage) -> String {
        language.text("As-tu une autre question ?", "Do you have another question?")
    }

    func start(_ configuration: ConversationConfiguration,
               onAnswer: @escaping (String, ResearchResponse, NORLanguage) -> Void) {
        stop()
        failure = nil
        active = true
        let current = run
        workflow = Task { [weak self] in
            guard let self else { return }
            do {
                _ = try ResearchAPI.validate(endpoint: configuration.endpoint, token: configuration.token, language: configuration.language)
                try await self.listen(configuration, run: current, onAnswer: onAnswer)
            } catch { self.fail(error.localizedDescription, run: current) }
        }
    }

    private func listen(_ configuration: ConversationConfiguration, run current: UUID,
                        onAnswer: @escaping (String, ResearchResponse, NORLanguage) -> Void) async throws {
        guard isCurrent(current) else { return }
        phase = .listening
        try await audio.listen(language: configuration.language, silence: configuration.silence,
            onQuestion: { [weak self] question in
                self?.answer(question, configuration: configuration, run: current, onAnswer: onAnswer)
            }, onFailure: { [weak self] message in self?.fail(message, run: current) })
    }

    private func answer(_ question: String, configuration: ConversationConfiguration, run current: UUID,
                        onAnswer: @escaping (String, ResearchResponse, NORLanguage) -> Void) {
        guard isCurrent(current), phase == .listening else { return }
        guard (2...2000).contains(question.count) else {
            fail(configuration.language.text("Votre question doit contenir entre 2 et 2 000 caractères. Votre texte est conservé.", "Your question must contain between 2 and 2,000 characters. Your text is preserved."), run: current)
            return
        }
        audio.stop()
        phase = .acknowledging
        workflow = Task { [weak self] in
            guard let self else { return }
            do {
                try await self.audio.speakAndWait(Self.acknowledgement(configuration.language), identifier: configuration.voiceID, language: configuration.language)
                guard self.isCurrent(current) else { return }
                self.phase = .researching
                let result = try await self.researcher(question, configuration)
                guard self.isCurrent(current) else { return }
                onAnswer(question, result, configuration.language)
                self.phase = .speaking
                let spoken = result.answer.replacingOccurrences(of: #"\[S[1-8]\]"#, with: "", options: .regularExpression)
                try await self.audio.speakAndWait(spoken + "\n\n" + Self.followup(configuration.language), identifier: configuration.voiceID, language: configuration.language)
                guard self.isCurrent(current) else { return }
                // Let output audio settle before opening the microphone again.
                try await Task.sleep(nanoseconds: 400_000_000)
                try await self.listen(configuration, run: current, onAnswer: onAnswer)
            } catch { self.fail(error.localizedDescription, run: current) }
        }
    }

    // Audio callbacks can arrive from the silence task just cancelled when it
    // closed the microphone. Session identity, not that caller's task state,
    // decides whether this question still belongs to the conversation.
    private func isCurrent(_ current: UUID) -> Bool { active && current == run }

    private func fail(_ message: String, run current: UUID) {
        guard current == run, active else { return }
        stop()
        failure = message
    }

    func stop() {
        run = UUID()
        active = false
        phase = .idle
        workflow?.cancel()
        workflow = nil
        audio.stop()
    }
}
