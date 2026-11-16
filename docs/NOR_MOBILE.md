# NOR sur iPhone avec un lien privé

L'interface mobile est désormais servie par le même moteur Windows, à l'adresse votre adresse HTTPS privée NOR . Elle est ajoutable à l'écran d'accueil en tant qu'application Web. Cette version ne nécessite ni Mac, ni certificat Apple, ni publication dans l'App Store.

## Démarrer

1. Arrêter l'ancien serveur avec Ctrl+C dans sa fenêtre PowerShell.
2. Depuis le dossier NOR, lancer :

```powershell
.\Start-NOR-Mobile.ps1
```

Ce lanceur affiche un code de huit chiffres, valable dix minutes et utilisable une fois, puis démarre le serveur. Si la version mobile tourne déjà, il crée seulement un nouveau code. Il refuse de lancer une seconde instance sur l'ancien serveur.

3. Sur l’iPhone, connecter Tailscale et ouvrir l’adresse ci-dessus dans Safari.
4. Dans Safari : Partager → Sur l’écran d’accueil → Ajouter. Activer « Ouvrir comme app Web » si proposé. Ouvrir ensuite l’icône NOR et saisir le code du PC. Le bouton « Installer NOR » rappelle ces étapes.

Si Safari et l’app installée demandent des connexions distinctes, générer un nouveau code pour la seconde session : le code déjà utilisé ne peut pas resservir.

L'iPhone doit rester connecté au même tailnet autorisé, et le PC doit garder NOR, Ollama et les réseaux de collecte démarrés. La veille ou l'arrêt du PC rend le moteur indisponible.

Pour générer un nouveau code sans relancer le serveur :

```powershell
.\.venv\Scripts\python.exe backend\manage.py pair
```

Ne pas transmettre ce code ou le jeton NOR dans une conversation. Le jeton existant reste utilisable avec PowerShell, l'app native et, si nécessaire, l'option avancée de connexion dans l'interface mobile.

## Fonctions

- Conversation écrite FR/EN, saisie adaptée au téléphone et suggestions de questions modifiables avant envoi.
- Réseau automatique, Tor, I2P ou les deux ; actualisation des sources et recherche approfondie optionnelles.
- Réponse avec durée, état du cache, origine de la collecte, extraits, dates, adresses copiables et questions ouvertes. Les adresses darknet ne sont pas ouvertes dans Safari.
- Nouvelle conversation, arrêt de l'attente et déconnexion. Une réponse tardive ne peut pas réapparaître après effacement.
- Lecture avec les voix déclarées locales par le navigateur, choix de la voix et échantillon. La disponibilité et le genre des voix ne sont pas garantis par le Web Speech API : choisir la voix désirée parmi celles proposées.
- Dictée automatique uniquement si le navigateur expose une reconnaissance explicitement locale et disponible, avec annonce choisie, pause de 3,5 secondes, réponse et invitation à poser une autre question. Sans support, le bouton explique d'utiliser le micro du clavier de l'iPhone ; NOR n'active pas une reconnaissance distante à la place. La dictée du clavier est gérée par iOS et ses réglages, pas par NOR.

La lecture automatique et les permissions du microphone dépendent du navigateur et des gestes de l'utilisateur. Les fonctions vocales doivent encore être validées sur l'iPhone réel. La conversation automatique ne reste pas active en arrière-plan.

## Connexion et conservation

Le code est stocké sous forme d'empreinte dans la base locale et consommé dans une transaction pour éviter sa réutilisation simultanée. Une session opaque est conservée dans un cookie Secure, HttpOnly, SameSite=Strict, valable sept jours. Sa seule empreinte est stockée dans la base ; le changement du jeton serveur invalide les sessions. La déconnexion supprime la session du serveur.

Les opérations de session et les recherches avec cookie exigent un en-tête propre au client ; les requêtes déclarées cross-site sont refusées, et aucune ouverture CORS n'est ajoutée. Les essais de connexion sont limités à cinq par minute et adresse client. Le jeton et le code ne sont jamais placés dans une URL ou dans localStorage.

Les conversations restent en mémoire dans la page et disparaissent à son rechargement/fermeture ; les préférences non sensibles de langue/voix peuvent être retenues. Les pages sources collectées et les journaux techniques limités du moteur gardent leur fonctionnement existant. Aucun historique de conversation n'est ajouté à la base.

Le service worker ne met en cache que l'interface publique, son manifeste et ses icônes. Il ne met jamais en cache les sessions, réponses de recherche ou capacités authentifiées. Hors ligne, l'interface peut rester affichée mais ne fabrique aucune réponse. Les résultats du moteur sont rendus comme texte et jamais exécutés en HTML. Aucun CDN, police distante, service analytique ou moteur classique n'est chargé par l'interface.

## Vérifications

157 tests Python passent, dont les contrôles du code à usage unique, des sessions, de l'expiration, de la rotation du jeton, des requêtes cross-site et de la concurrence. Cinq tests JavaScript hors ligne avec doublures DOM passent (connexion, requête de recherche, texte non interprété en HTML, erreurs, réponse tardive et périmètre du service worker). Syntaxe JavaScript et scripts PowerShell vérifiés. Les modèles de recherche et transports de test restent simulés.

Le navigateur a confirmé que l'ancienne instance répond encore 404 sur `/` : le redémarrage décrit ci-dessus est nécessaire pour charger les nouvelles routes. Le contrôle visuel local a été bloqué par la politique du navigateur sur les URL `file:` ; aucun contournement n'a été effectué. Le test HTTP en processus n'a pas abouti dans l'hôte et a été arrêté. L'installation Safari, la connexion réelle après redémarrage, le rendu visuel et la voix sur iPhone restent à confirmer. Les tests directs des routes et de l'authentification ont été exécutés sans ouvrir de port.

Référence Apple pour l'installation sur l'écran d'accueil : https://support.apple.com/en-ca/guide/iphone/iphea86e5236/ios .
