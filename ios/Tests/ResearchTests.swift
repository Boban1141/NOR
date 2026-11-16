import XCTest
@testable import NOR

final class ResearchTests: XCTestCase {
    func testInvalidServerUsesSelectedLanguage() async {
        for language in NORLanguage.allCases {
            do {
                _ = try await ResearchAPI.ask("origins", endpoint: "http://localhost", token: String(repeating: "x", count: 40), language: language)
                XCTFail("HTTP must be rejected before making a request")
            } catch {
                XCTAssertEqual(error.localizedDescription, language.text(
                    "Ajoutez l’adresse HTTPS de votre serveur dans les réglages.",
                    "Add your server HTTPS address in Settings."))
            }
        }
    }

    func testMissingTokenUsesSelectedLanguage() async {
        do {
            _ = try await ResearchAPI.ask("origins", endpoint: "https://nor.example", token: "", language: .english)
            XCTFail("Missing credentials must be rejected before making a request")
        } catch {
            XCTAssertEqual(error.localizedDescription, "Add your access token in Settings.")
        }
    }
}
