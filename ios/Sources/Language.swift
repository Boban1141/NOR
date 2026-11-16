import Foundation

enum NORLanguage: String, CaseIterable, Identifiable {
    case french = "fr"
    case english = "en"
    var id: String { rawValue }
    var name: String { self == .french ? "Français" : "English" }
    var speechLocale: String { self == .french ? "fr-FR" : "en-US" }
    func text(_ french: String, _ english: String) -> String {
        self == .french ? french : english
    }
}
