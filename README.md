# NOR — application iPhone bilingue et moteur de recherche, v0.4

NOR explore des sources difficiles d'accès et expose les preuves et leurs limites.
Ce livrable est un **prototype de développement**, pas une application iOS signée ni un moteur de recherche exhaustif.

Le projet de travail est maintenant dans le [dépôt privé NOR](https://github.com/Boban1141/NOR), [PR nº 1](https://github.com/Boban1141/NOR/pull/1). La CI GitHub Actions a été retirée à la demande de l’utilisateur. Les vérifications sont désormais manuelles ; voir [l’état d’activation](docs/ACTIVATION_REELLE.md).

## Ce qui est implémenté

- Interface SwiftUI pour iPhone iOS 17+, avec choix français/anglais mémorisé, questions écrites et résultats avec extraits, dates et adresses.
- Dictée française ou anglaise locale uniquement, sous réserve du support de l'appareil. Autorisations demandées à l'usage.
- [Conversation vocale automatique](docs/MODE_VOCAL_AUTOMATIQUE.md) : attente d'une pause, annonce choisie, recherche, réponse et invitation à poser une autre question. Fonction ajoutée au code, à valider sur iPhone.
- Choix parmi les voix masculines installées pour chaque langue, préférences séparées, écoute d'un échantillon et arrêt de la lecture.
- Messages du serveur dans la langue choisie ; extraits conservés dans leur langue originale. Les synthèses et la recherche sémantique multilingue nécessitent les modèles configurés.
- Jeton d'accès conservé dans le trousseau iOS, connexion serveur HTTPS uniquement.
- API privée avec authentification, passages FTS5/BM25, variantes bilingues, fusion des classements, suppression des copies identiques et diversité des hôtes.
- Connecteur Ollama pour recherche sémantique, planification adaptative ou approfondie en deux tours et synthèse structurée avec citations exactes contrôlées.
- Collecteur HTML onion v3 via Tor SOCKS5h uniquement ; au plus deux redirections validées sur le même hôte, aucun repli réseau direct, JavaScript ou exécution de fichiers.
- Suivi borné des liens dans les domaines configurés, conservation des versions modifiées et actualisation depuis l'app.
- Aucun faux résultat de démonstration. Un catalogue vide donne explicitement zéro résultat.

Voir les [améliorations de rapidité et de pertinence](docs/RAPIDITE_ET_PERTINENCE.md) : profil adaptatif par défaut, extraits ciblés, cache de trois minutes, mesures et commandes de vérification.

Voir la [collecte liée à la question](docs/COLLECTE_CIBLEE.md) : six points de départ, diversité des opérateurs, liens classés selon la question et actualisation bornée.

Pour les sources indisponibles : [diagnostic détaillé de collecte](docs/DIAGNOSTIC_COLLECTE.md), commande `manage.py diagnose-sources`.

Le [connecteur I2P](docs/I2P.md) est ajouté : catalogue séparé, proxy HTTP local au port 4444 et diagnostic `--network i2p`. Les deux catalogues totalisent désormais huit points de départ.

Voir les [contrôles de langue, réseau et couverture](docs/QUALITE_REPONSES.md), avec sélection automatique I2P/Tor et option `-Network`.

Le [parcours de connexion privée iPhone](docs/IPHONE_CONNEXION.md) est préparé : script Windows Tailscale Serve, test de connexion dans les réglages et script manuel de compilation/export sur macOS. L’application native reste à compiler, signer et installer.

## Limites actuelles

Le connecteur IA est implémenté, mais aucun modèle réel n'est connecté dans cet environnement. Sans modèle, NOR restitue des extraits et des avertissements. Avec les modèles configurés, il peut planifier, rechercher par sens et synthétiser. Le collecteur suit des liens uniquement dans les domaines onion configurés. Les dates indiquent la collecte, pas la publication. Les sources ne sont jamais déclarées vérifiées automatiquement ; une citation exacte ne démontre pas qu'une affirmation est vraie.

Cette première version ne peut donc pas encore satisfaire l'objectif de recherche approfondie sur le dark web. Six points de départ publiés par leurs opérateurs sont configurés : documentation et blog Tor, ProPublica, Amnesty et Guardian. Ce sont des miroirs publics, pas encore un vaste corpus spécialisé. Aucun contenu réel n'a été collecté dans cet environnement. Aucun fournisseur IA ou vocal payant n'a été activé.

Voir [le guide complet du moteur v0.3](docs/MOTEUR_RECHERCHE.md) pour activer les modèles, indexer les sources, comprendre les limites et reproduire les évaluations.

## Démarrer le serveur localement

Pour le parcours complet sans CI (configuration privée, diagnostic, collecte, embeddings et lancement), suivre [le démarrage manuel](docs/DEMARRAGE_MANUEL.md). Le lanceur `Start-NOR.ps1` utilise `backend/manage.py` et conserve la configuration et le jeton hors du dépôt.

Depuis `backend`, avec Python 3.12 :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:NOR_ACCESS_TOKEN = python nor.py token
python -m uvicorn nor:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Le jeton généré doit être conservé dans votre gestionnaire de secrets et saisi dans les réglages de l'app. Ne pas l'ajouter au code. Les variables de `.env.example` doivent être exportées explicitement.

Le serveur reste local par défaut. Pour un iPhone physique, prévoir un accès HTTPS privé à ce serveur (VPN ou infrastructure dédiée) ; `127.0.0.1` sur le téléphone désigne le téléphone. Ne pas ouvrir directement ce prototype sur Internet.

## Ajouter des sources réelles

1. Installer et démarrer Tor sur le serveur, avec un port SOCKS local (9050 par défaut).
2. Vérifier les trois sources de diagnostic configurées, puis compléter `backend/sources.json` avec des sources pertinentes. Leur provenance est documentée dans `source_registry.json`. Aucun exemple fictif n'est préchargé.
3. Exécuter `python nor.py crawl` puis `python nor.py index`. Après configuration d'un modèle d'embeddings, exécuter `python nor.py embed` pour activer la recherche sémantique.

La collecte ne journalise pas les adresses ni les contenus. Les pages collectées sont enregistrées en clair dans `nor.sqlite3` : utiliser un disque chiffré, limiter les accès et définir une politique de rétention avant toute donnée sensible. Aucune garantie d'anonymat n'est fournie par le seul usage de Tor.

## Générer et installer l'app sur iPhone

**Sans Mac personnel** : une machine macOS distante reste nécessaire pour compiler et signer l’app native. Voir [le parcours depuis Windows](docs/IPHONE_SANS_MAC.md). Aucun workflow GitHub Actions n’est conservé.

Un Mac avec Xcode est nécessaire pour la compilation native dans ce parcours. Le code a été écrit sous Windows et **n'a pas été compilé ni testé sur simulateur/iPhone**.

1. Sur le Mac, installer Xcode et XcodeGen (`brew install xcodegen`).
2. Dans `ios`, exécuter `xcodegen generate`, puis ouvrir `NOR.xcodeproj`.
3. Dans Signing & Capabilities, choisir votre équipe Apple et un identifiant de bundle unique.
4. Connecter votre iPhone, activer le mode développeur si demandé, sélectionner l'appareil et lancer Run.
5. Dans NOR, régler l'adresse HTTPS du serveur et enregistrer le jeton.

Ce parcours n'exige pas de publication dans les stores. La durée et les possibilités d'installation dépendent du provisionnement Apple ; un compte personnel ne constitue pas une distribution permanente.

Sources Apple :
- https://developer.apple.com/help/account/basics/about-your-developer-account
- https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device
- https://developer.apple.com/documentation/Speech/SFSpeechRecognizer/supportsOnDeviceRecognition

## Validation

```powershell
cd backend
python -m pytest -q
```

145 tests Python passent sous Windows : authentification, langues, passages, indexation incrémentale, classement, sémantique avec vecteurs de test, contrôle des citations, pannes de modèle, restrictions et budgets du collecteur, sources de diagnostic et rapport d'échec d'activation. Les tests utilisent des modèles et transports simulés. Le test HTTP intégré reste à exécuter sur le serveur cible ; cet environnement bloque la création de sockets asyncio Windows. Ces tests ne valident pas une connexion Tor réelle ni la qualité d'un modèle réel.

Le petit [benchmark synthétique](docs/evaluation_v0.3.json), distinct du corpus de production, contient 8 documents et 11 questions. Le document attendu est retrouvé au premier rang pour les 11 questions. Cela ne démontre pas une performance exceptionnelle sur le dark web réel.

Treize tests XCTest sont préparés : erreurs localisées, pauses et fin de question, cycle vocal, arrêt et réponse tardive après annulation. Ils n'ont pas été exécutés sous Windows ; leur exécution reste à effectuer manuellement sur macOS.

À valider sur iPhone : refus des permissions, démarrage/arrêt dictée, interruption par appel ou mise en arrière-plan, absence de voix masculine, lecture longue, erreur d'accès, serveur hors ligne et tailles de texte accessibles.

## Suite du travail

1. Compiler et tester l'app sur un appareil réel ; préparer une icône et la signature.
2. Constituer un catalogue réel de sources pertinentes et évaluer la collecte Tor dans un environnement isolé.
3. Configurer un modèle d'embeddings multilingue et évaluer le classement hybride sur des cas réels.
4. Connecter un modèle de synthèse réel et évaluer son raisonnement ; les contrôles de références sont déjà implémentés.
5. Ajouter recherches asynchrones, suivi des sources, limites de débit, plafonds de coût et rétention.
6. Comparer des voix masculines de meilleure qualité si les voix iOS ne suffisent pas.

Le nom NOR reste provisoire sur le plan des marques : la recherche publique antérieure n'est pas une validation juridique.
