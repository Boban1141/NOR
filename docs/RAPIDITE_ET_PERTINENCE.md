# Recherche plus rapide et plus pertinente

Le profil `balanced`, utilisé par défaut, commence par chercher dans l'index. Si les extraits couvrent les thèmes détectés, il passe directement à la synthèse. Sinon, il demande au modèle des requêtes supplémentaires. `deep` conserve la planification et un éventuel deuxième tour. Cette détection de couverture est une heuristique, pas une preuve de réponse complète.

Les résultats privilégient les passages qui couvrent les thèmes de la question et les pages distinctes. Les fenêtres transmises au modèle sont limitées à 700 caractères par passage. Leurs citations, offsets et empreintes correspondent au texte réellement fourni. Le nombre de passages par hôte reste plafonné ; plusieurs pages du même opérateur ne constituent pas des sources indépendantes.

Pour les thèmes vie privée et censure, un filtre supplémentaire rejette les affirmations hors sujet ou qui mentionnent un thème absent de leur citation. Ce filtre bilingue reste limité à ces concepts et ne remplace pas une validation du raisonnement. Les thèmes absents sont signalés dans `coverage.missing_query_topics` et les questions ouvertes.

Le collecteur privilégie les liens thématiques avant les simples changements de langue et extrait le contenu de `main` ou `article` lorsqu'il existe. Ces changements de collecte s'appliquent à la prochaine collecte, suivie d'une nouvelle indexation des embeddings.

## Réponses récentes

Un cache en mémoire conserve au maximum 64 réponses pendant trois minutes. Une modification du corpus, de la révision des embeddings, de la langue, du profil ou de la configuration du modèle empêche leur réutilisation. Le cache disparaît au redémarrage ; questions et réponses du cache ne sont pas écrites sur disque. Un remplacement de modèle sous le même nom exige un redémarrage, et une reconstruction des embeddings si nécessaire.

Une actualisation Tor explicite contourne ce cache. Un résultat réutilisé l'indique dans `cache.hit`, avec son âge. Les sources ne sont pas revisitées lors de cette réutilisation.

## Utilisation sous Windows

Redémarrer le serveur après la modification du code, dans sa fenêtre PowerShell : `Ctrl+C`, puis :

```powershell
.\.venv\Scripts\python.exe backend\manage.py serve
```

Dans une deuxième fenêtre, depuis le dossier NOR :

```powershell
# Mesurer une nouvelle réponse sans réutilisation.
.\Ask-NOR.ps1 -Question "Que disent les sources sur la vie privée et la censure ?" -Details -NoCache
# Remplir le cache, puis répéter pour observer cache.hit=true.
.\Ask-NOR.ps1 -Question "Que disent les sources sur la vie privée et la censure ?" -Details
.\Ask-NOR.ps1 -Question "Que disent les sources sur la vie privée et la censure ?" -Details
# Recherche avec planification approfondie.
.\Ask-NOR.ps1 -Question "Votre question" -Deep -NoCache -Details
```

L'API accepte `profile: "balanced" | "deep"` et `use_cache: true | false`. `duration_ms` et `timings` permettent d'observer les durées. La première réponse reste dépendante de la vitesse du modèle et de la collecte éventuellement demandée.

## Validation et limites

73 tests Python passent, dont 11 nouveaux tests de classement, de fenêtres exactes, de filtrage thématique, de couverture et de cache. Avec un modèle simulé et une question entièrement couverte, le profil balanced effectue un seul appel de conversation pour synthétiser ; une répétition depuis le cache n'en effectue aucun. Cela ne mesure pas la latence d'Ollama en conditions réelles.

La connexion réseau de l'environnement de développement étant bloquée, ces modifications restent à mesurer avec Ollama et Tor sur le PC de l'utilisateur. Aucun gain en secondes ni qualité exceptionnelle générale n'est revendiqué. Le corpus actuel reste petit et la recherche porte sur les sources configurées.
