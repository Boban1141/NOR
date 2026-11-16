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

## Script macOS préparé

Le fichier `ios/Build-NOR.command` permet de lancer manuellement les étapes sur une machine macOS avec Xcode et XcodeGen, sans CI :

```sh
cd ios
bash Build-NOR.command check
xcrun simctl list devices available
bash Build-NOR.command test IDENTIFIANT_SIMULATEUR
```

`check` produit un build non signé, impropre à l’installation sur iPhone. Après résolution de toute erreur de compilation et validation des tests, un compte Apple Developer autorisé, l’appareil enregistré et les ressources de signature doivent être disponibles sur le Mac. Pour préparer l’export privé :

```sh
bash Build-NOR.command archive IDENTIFIANT_EQUIPE IDENTIFIANT_BUNDLE
```

Utiliser l’identifiant d’équipe Apple de dix caractères et un identifiant de bundle unique enregistré dans son compte. Le Mac doit déjà être connecté au compte Apple autorisé dans Xcode. Le script crée l’archive puis un export `release-testing` (distribution aux appareils enregistrés), sans destination de téléversement. Les fichiers produits vont dans `.runtime/ios-build/`, hors du dépôt. Aucun certificat, mot de passe Apple, jeton NOR ou clé privée n’est inclus dans les sources.

Le parcours peut nécessiter une adhésion Apple Developer payante ; il ne la crée pas et ne déclenche aucun achat. Le compte personnel gratuit pour test sur appareil repose sur Xcode et ses profils temporaires, et ne remplace pas une distribution Ad Hoc depuis un Mac distant. Un Mac emprunté avec l’iPhone connecté est une autre possibilité de test personnel ; les profils Personal Team expirent normalement après sept jours selon Apple.

L’export IPA doit ensuite être installé par un canal privé compatible avec son provisionnement et l’appareil enregistré. Le script ne fournit pas ce canal et télécharger simplement un IPA sur l’iPhone ne suffit pas. Aucun hébergement public, publication App Store ou signature n’a été effectué. Le script n’a pas été exécuté sur macOS : les erreurs de compilation, de profil ou d’export restent à résoudre dans cet environnement.

Préparer l’accès au serveur selon [la connexion privée iPhone](IPHONE_CONNEXION.md). Référence Apple : https://developer.apple.com/help/account/basics/about-your-developer-account .
