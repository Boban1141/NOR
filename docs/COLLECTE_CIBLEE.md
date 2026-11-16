# Collecte liée à la question

L'option d'actualisation utilise désormais les thèmes de la question pour sélectionner les points de départ et classer les liens. Sans actualisation, NOR continue à répondre depuis son index local, sans collecte réseau.

## Catalogue et provenance

Le catalogue contient six points de départ et quatre groupes d'opérateurs déclarés : Tor Project (communauté, support, blog), ProPublica, Amnesty International et The Guardian. Les nouveaux domaines Tor sont publiés sur https://onion.torproject.org/ et celui du Guardian sur https://theguardian.engineering/blog/info-2022-oct-06-how-we-built-the-guardians-tor-onion-service . Références consultées le 16 novembre 2026. La présence dans ces publications ne prouve pas leur disponibilité actuelle via Tor.

Ces services sont des miroirs publics. Aucun n'est présenté comme une réserve d'informations exclusives ou de vérités cachées. Les trois domaines Tor ont le même opérateur déclaré. Les noms d'opérateurs sont des métadonnées du catalogue, pas une identité certifiée. Pour un catalogue personnalisé, définir `NOR_SOURCE_REGISTRY` vers son registre de métadonnées ; seuls les URL de `NOR_SOURCES` autorisent la collecte.

## Parcours de recherche

1. Classer les sources configurées selon leurs thèmes déclarés et la question. Choisir d'abord des opérateurs différents, au maximum six points de départ.
2. Explorer leurs liens selon le texte d'ancrage et le chemin de l'URL. Réutiliser les liens déjà observés dans `discovered_links`, toujours dans les hôtes sélectionnés.
3. Donner une chance aux différents hôtes avant de visiter davantage de pages du même hôte. Limiter une actualisation à dix tentatives, deux niveaux de liens et un budget nominal de 45 secondes. Les délais réseau peuvent faire dépasser ce budget ; il ne garantit pas dix pages collectées.
4. Indexer lexicalement les textes reçus avant de répondre. Les nouveaux passages doivent encore être passés à `embed` pour enrichir l'index sémantique ; la réponse le signale. Les embeddings existants continuent de fonctionner sur les passages déjà indexés.
5. Privilégier les opérateurs différents dans les résultats, avec au maximum deux passages par opérateur et par hôte. Afficher `coverage.distinct_operator_groups` et avertir avec `single_operator_evidence` si un seul groupe est représenté. L'indépendance reste non établie.

Aucune requête de recherche n'est envoyée à Google. Aucun moteur onion externe n'est interrogé et aucune URL de recherche distante n'est construite à partir de la question. Les mots de la question servent seulement au classement local des liens observés. Les pages ne peuvent pas ajouter d'hôtes autorisés, exécuter du code, suivre des redirections ou provoquer un repli réseau direct.

La collecte dépend des liens réellement proposés par les sites. Un sujet absent du catalogue peut rester sans réponse. Les articles contradictoires ne sont pas encore identifiés par un module spécialisé de comparaison ; les synthèses et leur portée doivent être évaluées sur des cas réels.

## Activer sur le PC existant

Arrêter le serveur avec Ctrl+C, puis, depuis le dossier NOR :

```powershell
.\.venv\Scripts\python.exe backend\manage.py collect
.\.venv\Scripts\python.exe backend\manage.py embed
.\.venv\Scripts\python.exe backend\manage.py serve
```

Dans une autre fenêtre, depuis NOR :

```powershell
.\Ask-NOR.ps1 -Question "Que disent les sources sur la vie privée et la censure ?" -Refresh -Details
```

`collection` précise si la collecte est guidée par la question et combien d'hôtes ont réellement répondu. `duration_ms` inclut maintenant la collecte éventuelle ; `timings.collection_ms` l'isole. Un résultat `live_search_used: true` signifie qu'au moins une page a été collectée, pas qu'elle apporte une preuve nouvelle ou indépendante.

Après d'autres actualisations, relancer `embed` pour vectoriser les nouveaux passages. Aucun changement de dépendances, publication, déploiement ni CI n'est nécessaire.

## Vérifications

Les tests couvrent le classement par sujet, la diversité des opérateurs, la priorité des ancres, la réutilisation des liens, le refus des hôtes retirés du catalogue, les limites de profondeur et de résultats, ainsi que le raccordement API. Les transports sont simulés. L'évaluation lexicale synthétique de onze questions conserve le document attendu au premier rang ; elle ne mesure ni Tor réel, ni la qualité d'Ollama. La collecte réelle des nouvelles adresses reste à exécuter sur le PC de l'utilisateur.
