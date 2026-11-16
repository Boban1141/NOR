import SwiftUI
import AVFoundation

private struct Turn: Identifiable {
    let id = UUID()
    let question: String
    let response: ResearchResponse
    let language: NORLanguage
}

@MainActor
struct ContentView: View {
    @StateObject private var voice: Voice
    @StateObject private var conversation: AutomaticConversation
    @AppStorage("endpoint") private var endpoint = ""
    @AppStorage("voiceID.fr") private var frenchVoiceID = ""
    @AppStorage("voiceID.en") private var englishVoiceID = ""
    @AppStorage("language") private var languageCode = "fr"
    @AppStorage("refreshSources") private var refreshSources = false
    @AppStorage("silenceSeconds") private var silenceSeconds = 3.5
    private var language: NORLanguage { NORLanguage(rawValue: languageCode) ?? .french }
    private var voiceID: String { language == .french ? frenchVoiceID : englishVoiceID }
    private var voiceSelection: Binding<String> {
        Binding(get: { voiceID }, set: { value in
            if language == .french { frenchVoiceID = value } else { englishVoiceID = value }
        })
    }
    private func t(_ french: String, _ english: String) -> String { language.text(french, english) }
    @State private var token = Credentials.read()
    @State private var question = ""
    @State private var turns: [Turn] = []
    @State private var busy = false
    @State private var settings = false
    @State private var error: String?
    @Environment(\.scenePhase) private var scenePhase
    private let accent = Color(red: 0.66, green: 0.85, blue: 0.68)

    init() {
        let audio = Voice()
        _voice = StateObject(wrappedValue: audio)
        _conversation = StateObject(wrappedValue: AutomaticConversation(audio: audio))
    }

    private var automaticMode: Binding<Bool> {
        Binding(get: { conversation.active }, set: { enabled in
            if enabled {
                conversation.start(ConversationConfiguration(endpoint: endpoint, token: token, language: language,
                    voiceID: voiceID, refresh: refreshSources, silence: silenceSeconds)) { text, result, responseLanguage in
                    turns.append(Turn(question: text, response: result, language: responseLanguage))
                    question = ""
                }
            } else { conversation.stop() }
        })
    }

    private var voiceStatus: String {
        switch conversation.phase {
        case .idle: return t("Mode vocal désactivé", "Voice mode off")
        case .listening: return voice.preparing ? t("Préparation du microphone…", "Preparing microphone…") : t("Je t’écoute…", "I’m listening…")
        case .acknowledging: return t("NOR confirme ta demande…", "NOR is acknowledging your question…")
        case .researching: return t("Recherche en cours · microphone coupé", "Researching · microphone off")
        case .speaking: return t("NOR te répond · microphone coupé", "NOR is answering · microphone off")
        }
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        Label(t("RECHERCHE PRIVÉE", "PRIVATE RESEARCH"), systemImage: "sparkle.magnifyingglass")
                            .font(.caption.monospaced()).foregroundStyle(accent)
                        Text(t("Explorer.\nComprendre.\nVérifier.", "Explore.\nUnderstand.\nVerify.")).font(.system(size: 38, weight: .semibold, design: .serif))
                        Text(t("Des sources, des dates, et la place du doute.", "Sources, dates, and room for uncertainty.")).foregroundStyle(.secondary)
                        Label(t("Sources Tor configurées · preuves à examiner", "Configured Tor sources · evidence to examine"), systemImage: "info.circle")
                            .font(.footnote).foregroundStyle(.secondary)
                        ForEach(turns) { turn in
                            VStack(alignment: .leading, spacing: 14) {
                                Text(turn.question).font(.title3.bold())
                                Text(turn.response.answer).textSelection(.enabled)
                                if turn.response.cache?.hit == true {
                                    Text(t("Réponse récente réutilisée · sources inchangées", "Recent answer reused · sources unchanged")).font(.caption).foregroundStyle(.secondary)
                                }
                                if turn.response.mode != "grounded_synthesis" {
                                    Text(t("Résultats par extraits · synthèse IA non utilisée", "Excerpt results · AI synthesis not used"))
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                if !(turn.response.warnings ?? []).isEmpty {
                                    Text(t("Certaines fonctions ne sont pas disponibles ou les sources sont insuffisantes. Les résultats restent à vérifier.", "Some capabilities are unavailable or sources are insufficient. Results still require verification."))
                                        .font(.footnote).foregroundStyle(.orange)
                                }
                                if let claims = turn.response.claims, !claims.isEmpty {
                                    DisclosureGroup(t("Examiner les citations", "Inspect quotations")) {
                                        ForEach(Array(claims.enumerated()), id: \.offset) { _, claim in
                                            VStack(alignment: .leading, spacing: 8) {
                                                Text(claim.text).font(.subheadline.bold())
                                                ForEach(Array(claim.evidence.enumerated()), id: \.offset) { _, evidence in
                                                    Text("[\(evidence.source_id)] « \(evidence.quote) »").font(.footnote).textSelection(.enabled)
                                                }
                                            }.padding(.vertical, 8)
                                        }
                                    }
                                }
                                ForEach(turn.response.sources) { source in
                                    VStack(alignment: .leading, spacing: 8) {
                                        Text(source.title).font(.headline)
                                        if let identifier = source.source_id {
                                            Text("[\(identifier)]").font(.caption.monospaced()).foregroundStyle(accent)
                                        }
                                        Text(source.excerpt).textSelection(.enabled)
                                        Text("\(t("Collecté", "Collected")) : \(source.collected_at)").font(.caption).foregroundStyle(.secondary)
                                        Text(source.url).font(.caption.monospaced()).textSelection(.enabled)
                                        Text(t("Adresse Tor · non vérifiée indépendamment", "Tor address · not independently verified")).font(.caption).foregroundStyle(accent)
                                    }.padding().background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 16))
                                }
                                if let gaps = turn.response.research_gaps, !gaps.isEmpty {
                                    Text(t("Questions encore ouvertes", "Open research questions")).font(.headline)
                                    ForEach(Array(gaps.enumerated()), id: \.offset) { _, gap in Text(gap).font(.footnote) }
                                }
                                Button { read(turn.response.answer, in: turn.language) } label: { Label(t("Écouter", "Listen"), systemImage: "speaker.wave.2") }
                            }.padding().background(.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 20))
                        }
                        if busy || conversation.phase == .researching { ProgressView(t("Recherche et analyse des sources…", "Searching and analysing sources…")) }
                        Color.clear.frame(height: 1).id("end")
                    }.padding(22)
                }.onChange(of: turns.count) { _, _ in withAnimation { proxy.scrollTo("end") } }
            }
            .background(Color(red: 0.045, green: 0.06, blue: 0.055))
            .navigationTitle("NOR")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { conversation.stop(); turns.removeAll() } label: { Image(systemName: "square.and.pencil") }.accessibilityLabel(t("Nouvelle conversation", "New conversation")).disabled(busy)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { conversation.stop(); settings = true } label: { Image(systemName: "slider.horizontal.3") }.accessibilityLabel(t("Réglages", "Settings"))
                }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 8) {
                    Toggle(t("Conversation vocale automatique", "Automatic voice conversation"), isOn: automaticMode)
                        .font(.subheadline).disabled(busy || voice.preparing)
                    if conversation.active { Text(voiceStatus).font(.caption).foregroundStyle(accent) }
                    HStack(alignment: .bottom, spacing: 12) {
                        Button {
                            Task {
                                if voice.recording { voice.stopRecording() }
                                else { do { try await voice.startRecording(language: language) } catch { self.error = error.localizedDescription } }
                            }
                        } label: { Image(systemName: voice.recording ? "stop.circle.fill" : "mic.fill").frame(width: 44, height: 44) }
                        .accessibilityLabel(voice.recording ? t("Arrêter la dictée", "Stop dictation") : t("Dicter une question", "Dictate a question")).disabled(busy || voice.preparing || conversation.active)
                        TextField(t("Votre question…", "Your question…"), text: $question, axis: .vertical).lineLimit(1...5).padding(.vertical, 12).disabled(conversation.active)
                        Button(action: send) { Image(systemName: "arrow.up").font(.headline).frame(width: 44, height: 44).background(accent, in: Circle()).foregroundStyle(.black) }
                            .accessibilityLabel(t("Rechercher", "Search")).disabled(busy || conversation.active || question.trimmingCharacters(in: .whitespacesAndNewlines).count < 2)
                    }
                    Button(t("Arrêter la voix", "Stop voice")) { conversation.stop() }.font(.caption)
                }.padding(.horizontal, 16).padding(.vertical, 10).background(.ultraThinMaterial)
            }
            .sheet(isPresented: $settings) {
                NavigationStack {
                    Form {
                        Section("Language / Langue") {
                            Picker("Language / Langue", selection: $languageCode) {
                                ForEach(NORLanguage.allCases) { item in Text(item.name).tag(item.rawValue) }
                            }
                        }
                        Section(t("Serveur privé", "Private server")) {
                            TextField("https://nor.example", text: $endpoint).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                            SecureField(t("Jeton d’accès", "Access token"), text: $token)
                            Text(t("Votre question est transmise à ce serveur. Le jeton reste dans le trousseau de l’iPhone.", "Your question is sent to this server. The token stays in the iPhone Keychain.")).font(.footnote)
                        }
                        Section(t("Recherche", "Research")) {
                            Toggle(t("Actualiser les sources via Tor", "Refresh sources through Tor"), isOn: $refreshSources)
                            Text(t("Consulte les sources configurées avant la recherche. Cette opération peut prendre plus d’une minute. Aucun accès à tous les sites du dark web n’est garanti.", "Visits configured sources before searching. This can take over a minute. Access to every dark web site is not guaranteed.")).font(.footnote)
                        }
                        Section(t("Voix masculine", "Male voice")) {
                            Text(t("Pause avant l’envoi :", "Pause before sending:") + " " + String(format: "%.1f", silenceSeconds) + " s")
                            Slider(value: $silenceSeconds, in: 2...6, step: 0.5)
                                .accessibilityLabel(t("Durée de silence avant l’envoi", "Silence duration before sending"))
                            Picker(t("Voix", "Voice"), selection: voiceSelection) {
                                Text(t("Automatique", "Automatic")).tag("")
                                ForEach(voice.maleVoices(language: language), id: \.identifier) { item in Text("\(item.name) · \(item.language)").tag(item.identifier) }
                            }
                            Button(t("Écouter un échantillon", "Listen to a sample")) { read(t("Bonjour, je suis NOR. Explorons votre question et examinons les sources ensemble.", "Hello, I am NOR. Let us explore your question and examine the sources together.")) }
                        }
                        Section(t("Confidentialité", "Privacy")) {
                            Text(t("Dictée locale uniquement. Aucun enregistrement audio conservé. La conversation reste en mémoire et disparaît à la fermeture complète. Les sources onion ne s’ouvrent pas dans Safari.", "On-device dictation only. No audio recordings are saved. Conversations stay in memory until the app fully closes. Onion sources do not open in Safari."))
                        }
                    }.navigationTitle(t("Réglages", "Settings")).toolbar {
                        Button(t("Enregistrer", "Save")) {
                            do { try Credentials.save(token, language: language); settings = false }
                            catch { self.error = error.localizedDescription }
                        }
                    }
                }
            }
            .alert("NOR", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
            .onChange(of: languageCode) { _, _ in conversation.stop(); error = nil }
            .onChange(of: voice.transcript) { _, value in question = value }
            .onChange(of: conversation.failure) { _, message in if let message { error = message } }
            .onChange(of: scenePhase) { _, phase in
                if phase == .background || (phase == .inactive && !voice.preparing) { conversation.stop() }
            }
            .onReceive(NotificationCenter.default.publisher(for: AVAudioSession.interruptionNotification).receive(on: RunLoop.main)) { notification in
                if let value = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                   value == AVAudioSession.InterruptionType.began.rawValue { conversation.stop() }
            }
            .onReceive(NotificationCenter.default.publisher(for: AVAudioSession.routeChangeNotification).receive(on: RunLoop.main)) { notification in
                if let value = notification.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
                   value == AVAudioSession.RouteChangeReason.oldDeviceUnavailable.rawValue { conversation.stop() }
            }
            .onDisappear { conversation.stop() }
            .tint(accent)
        }
    }

    private func read(_ text: String, in responseLanguage: NORLanguage? = nil) {
        conversation.stop()
        let selected = responseLanguage ?? language
        let selectedVoice = selected == .french ? frenchVoiceID : englishVoiceID
        do { try voice.speak(text, identifier: selectedVoice, language: selected) }
        catch { self.error = error.localizedDescription }
    }

    private func send() {
        let text = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard text.count >= 2, !busy else { return }
        guard text.count <= 2000 else {
            error = t("Limitez votre question à 2 000 caractères.", "Keep your question within 2,000 characters.")
            return
        }
        let requestLanguage = language
        voice.stop()
        busy = true
        Task {
            defer { busy = false }
            do {
                let result = try await ResearchAPI.ask(text, endpoint: endpoint, token: token, language: requestLanguage, refresh: refreshSources)
                turns.append(Turn(question: text, response: result, language: requestLanguage))
                question = ""
            } catch { self.error = error.localizedDescription }
        }
    }
}
