# Langue, réseau et couverture de la question

Le test réel de l'utilisateur sur la confidentialité et les tunnels I2P a révélé une synthèse anglaise malgré une demande française, des résultats Tor et l'absence de signalement du sujet « tunnels ». Les corrections suivantes répondent à ce cas.

## Sélection des sources

L'API accepte maintenant `network: "auto" | "i2p" | "tor" | "all"`. Par défaut, la mention d'I2P seule sélectionne I2P ; la mention de Tor ou onion seule sélectionne Tor. Si la question mentionne les deux, ou aucun, les deux catalogues restent disponibles. `all` désactive cette inférence. Ce mécanisme est lexical, pas une interprétation générale de l'intention.

La sélection s'applique aux candidats lexicaux et sémantiques avant leurs plafonds, à chaque tour de recherche et aux sources d'une actualisation. Une recherche I2P vide ne se rabat pas sur Tor. La réponse indique `network_scope`. Le cache est séparé par périmètre et sa version a changé pour ne pas réutiliser les anciennes réponses.

PowerShell permet le choix explicite avec `-Network i2p`, `-Network tor`, `-Network all` ou `-Network auto`. L'app iPhone utilise le mode automatique tant qu'elle ne transmet pas de choix explicite.

## Sujets conservés

La détection d'un concept connu ne supprime plus les autres mots utiles de la question. Les tunnels ont une expansion bilingue dédiée. Deux bilans sont séparés :

- `coverage.missing_query_topics` : thèmes non retrouvés dans les extraits sélectionnés.
- `coverage.unanswered_query_topics` : thèmes non traités dans les affirmations de la synthèse.

Les points manquants alimentent les questions ouvertes, y compris lorsque le modèle ne les signale pas. Le contrôle repose sur des expressions et synonymes : une mention ne prouve pas que le sujet est expliqué correctement ou en profondeur. Il ne constitue pas une validation logique du raisonnement.

## Langue des textes générés

Le prompt précise la langue. Une heuristique FR/EN détecte ensuite les textes manifestement dans l'autre langue. Une unique demande de traduction structurée peut corriger les affirmations et questions ouvertes. Le nombre et l'ordre des textes doivent rester identiques. Les preuves, identifiants et citations restent attachés côté serveur et ne sont jamais traduits.

Si la correction échoue ou reste manifestement dans la mauvaise langue, NOR retire la synthèse et affiche son message de repli localisé avec les extraits. Le contrôle thématique et celui des citations restent actifs après la traduction. La traduction peut néanmoins déformer un sens sans être détectée ; le mécanisme ne certifie pas la fidélité sémantique. L'heuristique peut manquer des phrases courtes, ambiguës ou dans une troisième langue.

`response_language_repaired` signale une correction ; `response_language_unavailable` signale son échec. Les citations et titres conservent volontairement la langue des sources. La correction peut ajouter un appel au modèle et augmenter la durée ; aucun gain de latence n'est promis.

## Vérification sur le PC

Arrêter puis redémarrer le serveur depuis NOR :

```powershell
.\.venv\Scripts\python.exe backend\manage.py serve
```

Dans une deuxième fenêtre :

```powershell
.\Ask-NOR.ps1 -Question "Que disent les sources I2P sur la confidentialité et les tunnels réseau ?" -Network i2p -NoCache -Details
```

Il n'est pas nécessaire de recollecter ou recalculer les embeddings pour tester ces corrections sur les pages déjà présentes. Si elles ne documentent pas les tunnels, NOR doit signaler cette lacune. Une collecte ultérieure peut enrichir l'index mais ne garantit pas de résoudre le manque.

Validation : 145 tests Python passent. Les nouveaux tests couvrent l'inférence du réseau, les filtres lexicaux et sémantiques, les thèmes conservés, les lacunes, la correction de langue, ses échecs et l'absence de repli vers Tor. Analyse syntaxique PowerShell réussie. Le benchmark lexical synthétique de onze questions conserve hit@3 et MRR à 1.0. Les tests utilisent des modèles simulés ; le modèle réel doit encore être essayé avec ces modifications.
