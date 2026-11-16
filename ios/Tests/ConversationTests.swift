import XCTest
@testable import NOR

final class EndOfQuestionTests: XCTestCase {
    func testShortPauseDoesNotSendAQuestion() {
        var boundary = EndOfQuestion(now: 0, silence: 3.5)
        boundary.recognized("Pourquoi", now: 1)
        XCTAssertEqual(boundary.decision(now: 3), .wait)
        boundary.recognized("Pourquoi cette différence", now: 3.1)
        XCTAssertEqual(boundary.decision(now: 5), .wait)
        XCTAssertEqual(boundary.decision(now: 6.7), .submit)
    }

    func testAudibleSpeechPreventsPrematureSubmission() {
        var boundary = EndOfQuestion(now: 0, silence: 3)
        boundary.recognized("Une question", now: 1)
        boundary.audibleSpeech(now: 3.5)
        XCTAssertEqual(boundary.decision(now: 5), .wait)
        XCTAssertEqual(boundary.decision(now: 6.6), .submit)
    }

    func testRepeatedPartialResultDoesNotResetThePause() {
        var boundary = EndOfQuestion(now: 0, silence: 3)
        boundary.recognized("My question", now: 1)
        boundary.recognized("My question", now: 3)
        XCTAssertEqual(boundary.decision(now: 4.1), .submit)
    }

    func testSilenceWithoutAQuestionDoesNotSendAnything() {
        let boundary = EndOfQuestion(now: 0, silence: 3)
        XCTAssertEqual(boundary.decision(now: 20), .wait)
        XCTAssertEqual(boundary.decision(now: 26), .idleTimeout)
    }

    func testLongContinuousSpeechPausesInsteadOfSendingIncompleteText() {
        var boundary = EndOfQuestion(now: 0, silence: 3)
        boundary.recognized("A long unfinished question", now: 58)
        boundary.audibleSpeech(now: 59)
        XCTAssertEqual(boundary.decision(now: 60), .tooLong)
    }
}

@MainActor
private final class FakeConversationAudio: ConversationAudio {
    var onQuestion: ((String) -> Void)?
    var onFailure: ((String) -> Void)?
    var phrases: [String] = []
    var listenCount = 0
    var speech: CheckedContinuation<Void, Error>?

    func listen(language: NORLanguage, silence: TimeInterval,
                onQuestion: @escaping (String) -> Void, onFailure: @escaping (String) -> Void) async throws {
        listenCount += 1
        self.onQuestion = onQuestion
        self.onFailure = onFailure
    }

    func speakAndWait(_ text: String, identifier: String, language: NORLanguage) async throws {
        phrases.append(text)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            speech = continuation
        }
    }

    func finishSpeech() {
        let continuation = speech
        speech = nil
        continuation?.resume()
    }

    func stop() {
        onQuestion = nil
        onFailure = nil
        let continuation = speech
        speech = nil
        continuation?.resume(throwing: CancellationError())
    }
}

@MainActor
final class AutomaticConversationTests: XCTestCase {
    private func configuration(_ language: NORLanguage = .french) -> ConversationConfiguration {
        ConversationConfiguration(endpoint: "https://nor.example", token: String(repeating: "x", count: 40),
            language: language, voiceID: "", refresh: false, silence: 3.5)
    }

    private func response() throws -> ResearchResponse {
        try JSONDecoder().decode(ResearchResponse.self, from: Data(#"{"answer":"Une réponse sourcée [S1].","sources":[]}"#.utf8))
    }

    private func waitUntil(_ condition: () -> Bool) async throws {
        let deadline = ContinuousClock.now + .seconds(3)
        while !condition(), ContinuousClock.now < deadline {
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        XCTAssertTrue(condition(), "Expected voice state was not reached")
    }

    func testAcknowledgementPrecedesResearchAndListeningResumesAfterFollowup() async throws {
        let audio = FakeConversationAudio()
        let result = try response()
        var requests = 0
        var received = 0
        let conversation = AutomaticConversation(audio: audio) { _, _ in requests += 1; return result }
        conversation.start(configuration()) { _, _, _ in received += 1 }
        try await waitUntil { audio.listenCount == 1 }
        audio.onQuestion?("Quelle est l’origine des humains ?")
        try await waitUntil { audio.phrases.count == 1 }
        XCTAssertEqual(audio.phrases[0], "D’accord, laisse-moi un instant pour examiner les sources.")
        XCTAssertEqual(requests, 0)
        XCTAssertEqual(conversation.phase, .acknowledging)
        audio.finishSpeech()
        try await waitUntil { audio.phrases.count == 2 }
        XCTAssertEqual(requests, 1)
        XCTAssertEqual(received, 1)
        XCTAssertTrue(audio.phrases[1].hasSuffix("As-tu une autre question ?"))
        XCTAssertFalse(audio.phrases[1].contains("[S1]"))
        XCTAssertEqual(audio.listenCount, 1, "Microphone must not reopen while NOR speaks")
        audio.finishSpeech()
        try await waitUntil { audio.listenCount == 2 }
        XCTAssertEqual(conversation.phase, .listening)
        conversation.stop()
    }

    func testStopDuringAcknowledgementPreventsRequestAndLateCallbacks() async throws {
        let audio = FakeConversationAudio()
        let result = try response()
        var requests = 0
        let conversation = AutomaticConversation(audio: audio) { _, _ in requests += 1; return result }
        conversation.start(configuration()) { _, _, _ in XCTFail("Must not deliver a stopped answer") }
        try await waitUntil { audio.listenCount == 1 }
        let oldCallback = audio.onQuestion
        oldCallback?("My question")
        try await waitUntil { audio.phrases.count == 1 }
        conversation.stop()
        oldCallback?("Another late question")
        for _ in 0..<10 { await Task.yield() }
        XCTAssertEqual(requests, 0)
        XCTAssertEqual(conversation.phase, .idle)
        XCTAssertFalse(conversation.active)
        XCTAssertNil(audio.speech)
    }

    func testStopDuringResearchSuppressesLateAnswer() async throws {
        let audio = FakeConversationAudio()
        let result = try response()
        var pending: CheckedContinuation<ResearchResponse, Error>?
        let conversation = AutomaticConversation(audio: audio) { _, _ in
            try await withCheckedThrowingContinuation { pending = $0 }
        }
        conversation.start(configuration()) { _, _, _ in XCTFail("A stopped request must not speak or deliver") }
        try await waitUntil { audio.listenCount == 1 }
        audio.onQuestion?("My question")
        try await waitUntil { audio.phrases.count == 1 }
        audio.finishSpeech()
        try await waitUntil { pending != nil }
        conversation.stop()
        pending?.resume(returning: result)
        pending = nil
        for _ in 0..<10 { await Task.yield() }
        XCTAssertEqual(audio.phrases.count, 1)
        XCTAssertEqual(audio.listenCount, 1)
        XCTAssertFalse(conversation.active)
    }

    func testResearchFailureDoesNotResumeMicrophone() async throws {
        let audio = FakeConversationAudio()
        let conversation = AutomaticConversation(audio: audio) { _, _ in throw NORFailure.message("Server offline") }
        conversation.start(configuration(.english)) { _, _, _ in XCTFail("No answer expected") }
        try await waitUntil { audio.listenCount == 1 }
        audio.onQuestion?("My question")
        try await waitUntil { audio.phrases.count == 1 }
        XCTAssertEqual(audio.phrases[0], "Alright, give me a moment to review the sources.")
        audio.finishSpeech()
        try await waitUntil { conversation.failure != nil }
        XCTAssertEqual(conversation.failure, "Server offline")
        XCTAssertEqual(audio.listenCount, 1)
        XCTAssertFalse(conversation.active)
    }
}
