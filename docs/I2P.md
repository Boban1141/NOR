# Connecteur I2P

NOR collecte maintenant des pages `.onion` par Tor et des pages `.i2p` par le proxy HTTP local I2P. Aucun moteur de recherche classique n'est interrogé et aucun repli vers le Web classique n'est permis.

## Configuration

Le catalogue Tor reste `backend/sources.json`. Le catalogue I2P séparé est `backend/sources_i2p.json`, avec deux points de départ : `http://i2p-projekt.i2p/` et `http://i2pforum.i2p/`. Ils sont référencés dans la documentation officielle https://i2p.net/en/docs/guides/gettingstarted/ (consultée le 16 novembre 2026). Leur disponibilité et leur contenu ne sont pas vérifiés automatiquement. Le groupe d'opérateur commun est une déclaration prudente du registre, pas une certification d'identité ou d'indépendance.

Le transport utilise `http://127.0.0.1:4444` par défaut, conformément au guide officiel https://i2p.net/en/docs/guides/browser-config/ . La clé facultative `i2p_proxy` de `nor.local.json` permet un autre port local ; sa valeur doit être un proxy HTTP sur une adresse de boucle locale, sans identifiants. Les anciennes configurations reçoivent la valeur par défaut en mémoire sans réécriture ni changement de jeton. Aucun nouveau paquet Python n'est nécessaire.

Variables pour un lancement direct : `NOR_I2P_PROXY` et `NOR_I2P_SOURCES`. Le lanceur `manage.py` applique sa configuration locale et les catalogues du projet. Les adresses conventionnelles `.i2p` et Base32 de 52 caractères sont acceptées. Les formats I2P avancés ne sont pas tous pris en charge.

## Vérifier puis collecter

Depuis le dossier NOR, avec I2P démarré :

```powershell
.\.venv\Scripts\python.exe backend\manage.py diagnose-sources --network i2p
```

Le diagnostic tente uniquement les deux adresses I2P, sans collecter leurs liens. Une connexion TCP au port 4444 ne suffit pas à valider un site distant : il faut que ce contrôle reçoive une page. Le rapport local indique les erreurs par source et le réseau utilisé. La commande conserve les pages reçues et leur index lexical, sans appeler le modèle.

Après le diagnostic, pour explorer les liens puis créer les embeddings, arrêter le serveur avec Ctrl+C et exécuter :

```powershell
.\.venv\Scripts\python.exe backend\manage.py collect --network i2p
.\.venv\Scripts\python.exe backend\manage.py embed
.\.venv\Scripts\python.exe backend\manage.py serve
```

Dans une autre fenêtre :

```powershell
.\Ask-NOR.ps1 -Question "Que disent les sources I2P sur la confidentialité ?" -NoCache -Details
```

`--network tor` limite collecte/diagnostic à Tor ; `--network all` est la valeur par défaut. Cela sélectionne le réseau de collecte. Les réponses utilisent désormais un périmètre automatique selon la question ou le choix explicite `-Network i2p|tor|all` : voir [qualité des réponses](QUALITE_REPONSES.md). L’index reste commun mais ses candidats sont filtrés avant classement. Chaque source API possède un champ `network`. L'actualisation depuis l'app utilise les deux catalogues et conserve les budgets globaux existants. Le test `verify` reste explicitement un test Tor/Ollama, pas une validation I2P.

## Limites de transport et de recherche

Le proxy I2P peut normalement servir de passerelle vers le Web classique. NOR interdit cette utilisation en validant chaque URL avant connexion : seuls `.onion` et `.i2p` sont admis. L'environnement proxy du système est ignoré. Les cibles de contrôle `proxy.i2p` et les paramètres d'address helper sont refusés. Les redirections vers un autre hôte ou réseau sont bloquées, tout comme la diminution HTTPS vers HTTP. Les sauts autorisés restent limités à deux sur le même hôte et partagent un budget de page. Les anciennes pages du Web classique éventuellement présentes dans la base sont exclues de l'index de réponse sans suppression des données brutes.

Les alias I2P lisibles dépendent du carnet d'adresses de l'installation. Un site peut donc être indisponible, inconnu ou lent. Le contenu n'est pas authentifié simplement parce que son adresse est `.i2p` ; les réponses restent accompagnées d'extraits et non vérifiées indépendamment. Ce connecteur n'explore pas tout I2P.

Validation : 133 tests Python passent, dont 24 nouveaux cas I2P (routage, catalogue séparé, refus du Web classique, redirections externes, proxy local, anciens paramètres et recherche). Transports simulés ; l'environnement de développement ne permet pas les connexions réseau réelles. Les essais sur le PC de l'utilisateur restent nécessaires. Les libellés SwiftUI mentionnent désormais Tor et I2P ; compilation iOS toujours à réaliser sur macOS.
