# Connexion privée iPhone vers NOR sur Windows

NOR reste une application native SwiftUI. Le serveur Windows, Ollama, Tor et I2P doivent rester démarrés ; l'iPhone envoie ses questions au PC par HTTPS. Tailscale transporte cette connexion privée, il ne fournit pas les sources de recherche.

## 1. Installer et connecter Tailscale

Sur Windows, télécharger Tailscale depuis https://tailscale.com/download/windows ou utiliser :

```powershell
winget install --id Tailscale.Tailscale --exact --source winget
```

Ouvrir Tailscale et se connecter à son compte. Installer aussi l'app Tailscale sur l'iPhone, se connecter au même réseau privé et activer sa connexion VPN. Ne pas partager de mots de passe ou clés d'authentification dans la conversation.

Tailscale Serve est accessible aux appareils autorisés par les règles du tailnet, et pas automatiquement à tous les internautes. Un tailnet partagé peut autoriser d'autres membres : vérifier les appareils et règles du compte. Aucun Funnel public n'est utilisé par ce parcours. Le nom DNS du PC utilisé pour le certificat HTTPS peut apparaître dans les journaux publics de certificats : choisir un nom de machine non sensible avant d'activer HTTPS.

## 2. Garder NOR ouvert

Dans une première fenêtre PowerShell, depuis NOR :

```powershell
.\.venv\Scripts\python.exe backend\manage.py serve
```

Laisser cette fenêtre ouverte. Le serveur reste sur `127.0.0.1:8000`. Le PC doit être allumé et ne pas être en veille.

## 3. Préparer puis activer HTTPS privé

Dans une deuxième fenêtre, depuis NOR :

```powershell
.\Connect-NOR-iPhone.ps1
```

Sans paramètre, ce script vérifie les prérequis et ne change pas Tailscale. Il ne lit ni n'affiche le jeton NOR. S'il indique que les vérifications passent, ouvrir PowerShell en administrateur et exécuter depuis NOR :

```powershell
.\Connect-NOR-iPhone.ps1 -Enable
```

Tailscale peut demander d'activer HTTPS dans son interface de compte. Suivre le lien officiel affiché par son CLI, puis relancer le script. Le script utilise `tailscale serve --bg --https=443 http://127.0.0.1:8000`, vérifie son résultat et affiche l'adresse privée `https://...ts.net`. Les comptes et autorisations ne sont pas créés automatiquement.

Le script refuse une configuration Serve/Funnel préexistante autre que son propre proxy NOR et ne la réinitialise pas. Cela évite d'interrompre ou remplacer un autre service. La commande `tailscale serve status` permet de l'inspecter. `--bg` rend le proxy persistant ; le serveur NOR doit néanmoins être démarré séparément après un redémarrage Windows.

Pour arrêter ce seul proxy, après vérification qu'il appartient toujours à NOR :

```powershell
tailscale serve --bg --https=443 http://127.0.0.1:8000 off
```

## 4. Vérifier le trajet depuis l'iPhone

Avec Tailscale activé sur l'iPhone, ouvrir dans Safari l'adresse affichée, suivie de `/health`. Une réponse JSON avec `status: ok` vérifie le trajet HTTPS ; ce n'est pas une version Web de NOR. Aucun jeton n'est demandé pour ce contrôle non sensible.

Une fois l'app native compilée, signée et installée, ouvrir ses réglages :

1. Saisir l'adresse HTTPS de base, sans `/health` ni `/research`.
2. Saisir le jeton privé de ce serveur. Ne jamais le coller dans une conversation, une URL ou le dépôt.
3. Appuyer sur « Tester la connexion ». Le test appelle `/capabilities` avec authentification et affiche le nombre de passages indexés. Il ne lance aucune recherche ni vérification Tor/I2P/modèle.
4. Enregistrer les réglages, puis poser une question écrite avant d'activer la voix.

L'app conserve le jeton dans le trousseau quand les réglages sont enregistrés. Son transport éphémère ne conserve pas de cache HTTP ou de cookies et refuse les redirections. Une erreur d'accès utilise un message français ou anglais. La validité TLS reste contrôlée normalement.

## Signature et état réel

La connexion serveur et l'installation native sont deux étapes distinctes. Voir [le parcours de compilation](IPHONE_SANS_MAC.md). Aucun IPA signé n'a encore été produit. Les modifications SwiftUI et les 13 tests XCTest préparés restent à compiler et exécuter sur macOS. Les 145 tests Python du moteur sont validés et les huit contrôles de configuration du proxy passent dans le PowerShell de travail ; cela ne valide pas une connexion Tailscale réelle. La syntaxe des trois scripts PowerShell a été analysée sans erreur. L’hôte a bloqué leur exécution avec Windows PowerShell 5.1 et le lancement du Bash Windows : leur validation dans ces interpréteurs reste à faire sans modifier les politiques de sécurité. Tailscale n'est pas installé dans l'environnement de travail et aucun compte n'a été connecté ici.

Références officielles : https://tailscale.com/docs/install/windows ; https://tailscale.com/docs/features/tailscale-serve ; https://tailscale.com/docs/reference/tailscale-cli/serve ; https://tailscale.com/docs/how-to/set-up-https-certificates .
