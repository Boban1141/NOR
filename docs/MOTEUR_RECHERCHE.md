# NOR v0.3 — moteur de recherche et intelligence

## Fonctionnement implémenté

1. **Collecte Tor** : les URL de départ sont configurées par l'opérateur. Le collecteur suit des liens uniquement dans ces domaines onion, avec plafonds de profondeur, de pages et de volume. Il ne découvre pas tous les sites du dark web. Aucun repli direct, redirection, exécution de JavaScript, téléchargement de binaire ou accès à un réseau privé n'est permis par ce collecteur.
2. **Versions** : les contenus textuels modifiés sont conservés durant 30 jours dans `page_versions`. L'index courant est mis à jour ; une ancienne version n'est pas présentée comme nouvelle.
3. **Passages** : les pages sont découpées en passages de 1 500 caractères environ, avec chevauchement. Les offsets portent sur le texte normalisé (espaces regroupés), et non sur les octets du HTML original.
4. **Recherche lexicale** : SQLite FTS5/BM25, retrait de mots courants FR/EN et expansion bilingue contrôlée pour quelques concepts. Cette expansion locale n'est pas un traducteur général.
5. **Recherche sémantique optionnelle** : un modèle d'embeddings multilingue installé sur le serveur encode les passages et les requêtes. Recherche par similarité cosinus, puis fusion des classements lexicaux/sémantiques par Reciprocal Rank Fusion. Les vecteurs sont mis en cache par passage et nom de modèle.
6. **Recherche en deux tours au maximum** : lorsqu'un modèle de conversation est configuré, il prépare des requêtes, puis peut proposer deux recherches complémentaires après avoir examiné les premiers extraits. Le nombre total de requêtes est plafonné à huit ; chaque recherche fusionne au plus six classements.
7. **Diversité** : suppression des passages identiques et maximum de deux passages par hôte dans les huit résultats finaux. Deux hôtes ne prouvent pas deux auteurs indépendants ; les copies légèrement modifiées peuvent encore échapper au dédoublonnage.
8. **Synthèse optionnelle** : le modèle renvoie des affirmations structurées, des citations exactes et des identifiants de source. Le serveur refuse une affirmation si une référence n'existe pas ou si sa citation n'est pas présente dans l'extrait associé.
9. **Transparence** : le résultat indique les fonctions effectivement utilisées, les avertissements, les limites de couverture et les questions ouvertes. Aucun résultat n'est automatiquement déclaré vrai.

## Ce que vérifie réellement le contrôle des citations

Le contrôle démontre qu'une citation reproduit un extrait disponible. **Il ne démontre ni que l'affirmation est logiquement soutenue par cette citation, ni que la source dit vrai.** La qualité du raisonnement et les contradictions doivent encore être évaluées avec un vrai modèle et des cas annotés par des humains.

Les pages ne sont jamais interprétées comme des instructions système. Le modèle ne reçoit ni jeton d'accès, ni accès au navigateur, ni outil d'exécution. Cette séparation limite les conséquences d'une instruction malveillante dans une page ; elle ne constitue pas une garantie universelle contre les manipulations du modèle.

## Activer le moteur

Depuis `backend`, après installation des dépendances et démarrage du service Tor :

```powershell
# Configurer d'abord sources.json avec de véritables URL obtenues auprès de leurs opérateurs.
python nor.py crawl
python nor.py index
```

`crawl` tente au plus 20 pages et une profondeur de deux liens, avec un budget nominal de 90 secondes. Les timeouts réseau limitent les attentes d'inactivité ; le budget total est vérifié entre les lectures et les pages, et ne constitue pas une échéance stricte d'annulation des sockets.

## Brancher une vraie IA

Installer Ollama sur le serveur de calcul, puis y installer un modèle de conversation compatible avec les sorties JSON structurées et un modèle d'embeddings multilingue. Le choix dépendra de la RAM/VRAM disponible et d'une évaluation comparative. Aucun modèle n'est téléchargé automatiquement et aucun service payant n'est activé par ce projet.

```powershell
$env:NOR_OLLAMA_URL = 'http://127.0.0.1:11434'
$env:NOR_CHAT_MODEL = '<nom-du-modele-installe>'
$env:NOR_EMBED_MODEL = '<nom-du-modele-multilingue-installe>'
python nor.py embed
```

Utiliser des versions de modèles fixes. Si le modèle d'embeddings est remplacé sous le même nom, reconstruire les vecteurs :

```powershell
python nor.py embed --rebuild
```

Un endpoint Ollama externe doit utiliser HTTPS et un réseau de confiance ; l'adaptateur ne configure pas encore d'authentification fournisseur. Un endpoint HTTP n'est autorisé que sur la boucle locale. Un serveur Ollama peut lui-même utiliser un modèle distant : il faut vérifier sa configuration avant d'y transmettre des sources sensibles.

En cas de modèle absent, de réponse invalide, de citation inventée ou de panne, NOR restitue des extraits et des avertissements. Il ne simule pas une intelligence connectée. Les appels au modèle utilisent des timeouts et des plafonds de réponse ; un modèle trop lent peut donc déclencher ce repli.

## Utiliser l'application

Les réglages permettent d'activer « Actualiser les sources via Tor ». Cette option demande au serveur de revisiter au plus huit pages des domaines configurés avant la recherche. L'actualisation n'est pas une exploration illimitée pilotée par la question. L'app affiche les repères `[S1]`, `[S2]`, les citations inspectables et les questions encore ouvertes.

L'API conserve `POST /research`, avec le contrat :

```json
{"question":"Votre question", "language":"fr", "refresh":false}
```

Le jeton Bearer reste obligatoire. `GET /capabilities` indique le nombre de passages et de vecteurs indexés, ainsi que les modèles configurés. Il ne prétend pas vérifier leur disponibilité. Les deux recherches simultanées permises sont une limite par processus ; ce prototype doit être lancé avec un seul worker. Les autres appels reçoivent HTTP 429 et doivent être réessayés plus tard.

## Évaluation effectuée

- Tests automatiques : récupération bilingue, indexation incrémentale, passages, copies, diversité des hôtes, recherche sémantique avec vecteurs de test, panne de modèle, schémas JSON, citations inventées, restrictions Tor et limites du collecteur.
- Corpus de référence **synthétique**, distinct des données de production : 8 documents et 11 questions. Résultat mesuré : document attendu au premier rang pour les 11 questions.
- Voir `evaluation_v0.3.json` pour les résultats et les durées locales. Ce petit corpus valide des comportements de base ; il ne mesure pas une performance exceptionnelle sur des sources réelles.
- Aucun modèle réel, aucune connexion Tor réelle et aucun test iPhone n'ont été exécutés dans cet environnement.

Relancer :

```powershell
python -m pytest -q
python evaluate.py --output ../docs/evaluation_v0.3.json
```

## Limites et étape de validation suivante

Le moteur sémantique actuel effectue une recherche exacte plafonnée aux 20 000 premiers vecteurs du modèle, classés par identifiant ; l'API le signale si le plafond est atteint. Ce moteur n'est pas adapté à des millions de passages. Avant changement d'échelle, prévoir un index vectoriel adapté, des travaux asynchrones, un classement spécialisé, des contrôles de charge et un jeu d'évaluation réel.

Il reste à constituer un catalogue pertinent de sources, connecter le modèle choisi, mesurer les erreurs et les coûts réels, examiner les attaques par injection et valider la compilation iOS. La simple présence du connecteur IA ne garantit pas la qualité des recherches.

## Conservation et exploitation

Les pages, anciennes versions et vecteurs sont stockés en clair dans SQLite ; prévoir chiffrement du disque, accès restreint et politique de conservation. Les traces de recherche ne contiennent pas les questions ni les extraits, mais seulement un identifiant, une date, le mode, la durée et des codes d'avertissement. Elles sont purgées après 30 jours lors d'une recherche suivante. Les anciennes versions sont purgées lors d'une collecte suivante ; il n'y a pas encore de purge planifiée. Les pages courantes et leurs vecteurs ne sont pas purgés automatiquement.

L'indexation transmet le texte des sources au serveur de modèle configuré. Ce prototype vise un usage privé à utilisateur unique ; il n'implémente pas encore l'isolation entre comptes, la gestion des droits d'une équipe ni les contrôles nécessaires à une ouverture publique.

## Références techniques

- SQLite FTS5 : https://www.sqlite.org/fts5.html
- Ollama, contrat API : https://github.com/ollama/ollama/blob/main/docs/api.md
- Ollama, sorties structurées : https://registry.ollama.com/blog/structured-outputs
