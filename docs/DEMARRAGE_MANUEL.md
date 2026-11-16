# Démarrer NOR manuellement, sans CI

Les commandes suivantes se lancent depuis le dossier NOR sur la machine qui hébergera le moteur. Elles ne publient rien sur Internet et ne configurent pas l'installation iPhone.

## 1. Préparer Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Cette installation nécessite un accès réseau aux distributions Python. Aucun contournement de la politique d'exécution PowerShell n'est nécessaire : les commandes utilisent directement l'exécutable Python de l'environnement.

## 2. Préparer les services

Installer Ollama depuis https://ollama.com/download et Tor depuis https://www.torproject.org/download/tor/ en suivant leurs instructions. Démarrer Ollama, puis Tor avec un port SOCKS local `127.0.0.1:9050`. NOR ne doit pas être utilisé comme relais Tor.

Installer dans Ollama un modèle de conversation compatible JSON structuré et un modèle d'embeddings multilingue. Pour un **diagnostic léger uniquement**, les modèles déjà documentés dans le projet peuvent être téléchargés explicitement :

```powershell
ollama pull qwen2.5:1.5b
ollama pull bge-m3:567m
```

Ces téléchargements utilisent plusieurs gigaoctets de disque et ne constituent pas le choix final d'un modèle de haute qualité. Ils ne sont pas déclenchés par le lanceur NOR.

## 3. Initialiser la configuration privée

```powershell
.\.venv\Scripts\python.exe backend\manage.py init --chat-model qwen2.5:1.5b --embedding-model bge-m3:567m
```

Cette commande crée `nor.local.json` et un jeton aléatoire dans `.runtime/access-token`. Elle refuse d'écraser une configuration existante et conserve un jeton déjà présent. Pour choisir d'autres modèles ou une autre adresse de serveur, modifier `nor.local.json`, qui contient uniquement des paramètres de données et n'est jamais exécuté comme du code.

Ces fichiers sont exclus de Git. Le jeton n'est pas imprimé dans les rapports. Sur Windows, les permissions POSIX ne suffisent pas à garantir une ACL privée : protéger le dossier `.runtime` avec les permissions du compte qui exécute NOR. Ne jamais ajouter son contenu au dépôt ou le partager dans la conversation.

## 4. Vérifier les prérequis

```powershell
.\.venv\Scripts\python.exe backend\manage.py doctor
```

Le diagnostic vérifie les dépendances, la présence du jeton, la réponse d'Ollama, la présence des deux modèles choisis et une réponse au protocole SOCKS5. Il affiche les éléments manquants, sans le jeton.

**Un proxy SOCKS qui répond ne prouve pas que le réseau Tor fonctionne.** Le champ `tor_network_verified` reste faux dans ce diagnostic. Un code de sortie 2 signifie que des prérequis manquent.

## 5. Tester réellement, puis créer le corpus

```powershell
.\.venv\Scripts\python.exe backend\manage.py verify
.\.venv\Scripts\python.exe backend\manage.py collect
.\.venv\Scripts\python.exe backend\manage.py embed
```

`verify` utilise un corpus temporaire, vérifie Tor et les modèles et écrit `.runtime/live-smoke.json`. Il ne déclare pas le moteur prêt si la synthèse ou une connexion manque.

`collect` conserve les pages et leurs passages dans `.runtime/nor.sqlite3`. `embed` calcule les vecteurs avec le modèle configuré. Les six points de départ sont des miroirs publics et des ressources documentaires ; compléter le catalogue pour les besoins spécialisés. Voir [la collecte ciblée](COLLECTE_CIBLEE.md), activée avec `-Refresh` pour une question.

## 6. Démarrer le serveur

```powershell
.\.venv\Scripts\python.exe backend\manage.py serve
```

Ou lancer `Start-NOR.ps1` depuis PowerShell. `Start-NOR.ps1 -CheckOnly` exécute seulement le diagnostic.

Le serveur démarre au premier plan et écoute uniquement `127.0.0.1:8000`, avec un seul worker et sans journal des requêtes. Fermer le serveur avec Ctrl+C. Le lanceur ne crée pas de service permanent et n'ouvre pas le pare-feu. Il peut démarrer en mode extraits si un modèle est arrêté : vérifier le diagnostic et les avertissements avant de juger ses capacités.

## Poser une question depuis PowerShell

Une fois le serveur lancé, ouvrir une seconde fenêtre PowerShell dans NOR :

```powershell
.\Ask-NOR.ps1 -Question "Que disent les sources sur la vie privée et la censure ?"
```

Ajouter `-Details` pour afficher aussi les sources et diagnostics. Le script lit le jeton localement, sans l'afficher, et décode directement les octets UTF-8 pour éviter les accents déformés dans Windows PowerShell 5.1. Si l'exécution des scripts est bloquée par une politique locale, utiliser les commandes manuelles documentées sans modifier cette politique automatiquement.

## Connexion iPhone : étape encore distincte

Le serveur local en HTTP n'est pas directement compatible avec les réglages HTTPS de l'app iPhone. Un accès HTTPS privé à cette machine doit être mis en place séparément, puis configuré dans NOR avec le jeton. Aucun tunnel, certificat, domaine public, hébergement ni signature Apple n'est créé par ce parcours.

## Validation effectuée ici

Les tests du lanceur vérifient la conservation du jeton, son absence des sorties, les erreurs de configuration, la différence entre service présent et modèles installés, et l'écoute limitée à la boucle locale. Les connexions réelles restent bloquées ici par l'absence de services et les limitations réseau décrites dans `ACTIVATION_REELLE.md`.

## Comprendre les échecs de collecte

Exécuter `.\.venv\Scripts\python.exe backend\manage.py diagnose-sources` pour tester uniquement les points de départ et enregistrer les causes par source. Voir [diagnostic de collecte](DIAGNOSTIC_COLLECTE.md). Le bilan distingue les domaines non tentés des domaines en échec.

## Ajouter I2P au moteur

Le proxy I2P doit être démarré séparément. Voir [le connecteur I2P](I2P.md) pour `diagnose-sources --network i2p`, la collecte et les limites. Le diagnostic `doctor` historique décrit Tor/Ollama ; le test du port 4444 seul ne valide pas un site I2P.
