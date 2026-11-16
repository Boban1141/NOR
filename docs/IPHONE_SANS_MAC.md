# NOR sur iPhone, depuis Windows

## Compilation manuelle sur macOS

La CI GitHub Actions a été supprimée à la demande de l’utilisateur. Aucune compilation ne se déclenche désormais lors des commits ou des PR.

Pour compiler sans posséder de Mac, il faudra disposer d’une machine macOS distante avec Xcode et XcodeGen. Aucun service distant n’est encore configuré.

Depuis le dossier `ios` sur cette machine :

```sh
xcodegen generate
xcodebuild build -project NOR.xcodeproj -scheme NOR -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO
```

Pour exécuter les tests, choisir l’identifiant d’un simulateur iPhone disponible avec `xcrun simctl list devices available`, puis lancer :

```sh
xcodebuild test -project NOR.xcodeproj -scheme NOR -destination 'platform=iOS Simulator,id=IDENTIFIANT_DU_SIMULATEUR' CODE_SIGNING_ALLOWED=NO
```

Ces commandes ne produisent pas encore d’application signée installable sur l’iPhone. La compilation et les tests iOS restent non validés.

## Installation privée : étape distincte

Un build non signé ne peut pas être installé sur l'iPhone. Le parcours privé envisagé est une distribution Ad Hoc, qui nécessite :

- Une adhésion Apple Developer Program appropriée.
- Un App ID correspondant à l'identifiant unique de NOR.
- L'UDID de votre iPhone enregistré dans votre compte Apple Developer.
- Un certificat de distribution avec sa clé privée et un profil Ad Hoc couvrant cet appareil.
- Une étape de compilation/signature macOS puis un canal d'installation privé compatible iOS.

La signature et le canal d'installation ne sont **pas encore configurés**. Télécharger un ZIP ou un IPA dans Fichiers sur l'iPhone ne suffit pas à installer l'app.

La génération d'un certificat et d'une clé privée peut être organisée avec des outils de certificat depuis Windows, mais le paquet iOS doit toujours être compilé/signé sur macOS. Les identifiants Apple ne doivent jamais être inscrits dans le code ni communiqués dans la conversation. Les futurs secrets de signature seront déposés directement dans un coffre de secrets de l'environnement de compilation.

Les certificats et profils ont une validité limitée ; prévoir le renouvellement. Ce parcours ne suppose ni publication sur Google Play ni publication sur l'App Store.

## Documents officiels consultés

- Runners macOS GitHub : https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- Signature sur runners macOS : https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications
- Appareils enregistrés Apple : https://developer.apple.com/help/account/devices/devices-overview/
- Profil Ad Hoc : https://developer.apple.com/help/account/provisioning-profiles/create-an-ad-hoc-provisioning-profile/

## Ce qui peut continuer sans signature

Le moteur de recherche, la collecte Tor, les évaluations et l'application bilingue peuvent être développés avant que ces accès soient disponibles. La compilation distante et l'installation resteront signalées comme non validées jusqu'à leur exécution réelle.
