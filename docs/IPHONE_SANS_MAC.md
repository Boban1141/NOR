# NOR sur iPhone, depuis Windows

## Compilation à distance préparée

Le projet contient `.github/workflows/ios-check.yml`. Une fois le **contenu du dossier NOR** placé à la racine d'un dépôt GitHub, ce workflow peut être lancé manuellement dans Actions → NOR - iPhone compilation and tests → Run workflow.

Il utilise un runner macOS hébergé par GitHub pour :

1. Générer le projet Xcode avec XcodeGen.
2. Sélectionner un simulateur iPhone réellement disponible.
3. Compiler l'app et exécuter les tests iOS.
4. Vérifier aussi la compilation pour un iPhone physique, sans signature.
5. Conserver le rapport de test durant sept jours.

Il n'a pas encore été exécuté : aucun dépôt distant NOR n'a été créé ou associé. Ce workflow ne produit pas encore de fichier installable, ne publie rien et n'exige aucun secret Apple. Le coût éventuel dépend du compte GitHub et de ses minutes disponibles ; aucune exécution payante n'a été déclenchée.

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
