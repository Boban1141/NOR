import Foundation

struct Source: Decodable, Identifiable {
    var id: String { chunk_id ?? url }
    let url: String
    let title: String
    let excerpt: String
    let collected_at: String
    let source_id: String?
    let chunk_id: String?
}

struct ResearchResponse: Decodable {
    let answer: String
    let sources: [Source]
    let mode: String?
    let warnings: [String]?
    let claims: [ResearchClaim]?
    let research_gaps: [String]?
    let cache: ResearchCache?
}

struct ResearchCache: Decodable {
    let hit: Bool
    let age_seconds: Double?
}

struct ResearchClaim: Decodable {
    let text: String
    let evidence: [ResearchEvidence]
}

struct ResearchEvidence: Decodable {
    let source_id: String
    let quote: String
}

private struct ResearchRequest: Encodable {
    let question: String
    let language: String
    let refresh: Bool
}

enum NORFailure: LocalizedError {
    case message(String)
    var errorDescription: String? {
        switch self { case .message(let value): return value }
    }
}

enum ResearchAPI {
    static func validate(endpoint: String, token: String, language: NORLanguage) throws -> URL {
        guard let base = URL(string: endpoint), base.scheme == "https", base.host != nil,
              base.user == nil, base.password == nil, base.query == nil, base.fragment == nil else {
            throw NORFailure.message(language.text("Ajoutez l’adresse HTTPS de votre serveur dans les réglages.", "Add your server HTTPS address in Settings."))
        }
        guard token.count >= 32 else { throw NORFailure.message(language.text("Ajoutez votre jeton d’accès dans les réglages.", "Add your access token in Settings.")) }
        return base
    }

    static func ask(_ question: String, endpoint: String, token: String, language: NORLanguage, refresh: Bool = false) async throws -> ResearchResponse {
        let base = try validate(endpoint: endpoint, token: token, language: language)
        var request = URLRequest(url: base.appendingPathComponent("research"))
        request.httpMethod = "POST"
        request.timeoutInterval = 180
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(ResearchRequest(question: question, language: language.rawValue, refresh: refresh))
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw NORFailure.message(language.text("Recherche indisponible. Vérifiez le serveur et votre accès.", "Search unavailable. Check your server and access token."))
        }
        return try JSONDecoder().decode(ResearchResponse.self, from: data)
    }
}
