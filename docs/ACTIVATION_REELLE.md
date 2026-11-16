# Activation réelle de NOR — état et parcours

## Dépôt de travail

Le projet est maintenant dans le dépôt privé `Boban1141/NOR`, branche `nor/activation`, PR en brouillon nº 1. Les changements liés sont regroupés dans cette même PR. Aucune fusion et aucun déploiement public n'ont été effectués.

## Blocage constaté

GitHub Actions a refusé de lancer la première vérification : l'interface signale des paiements récents en échec ou un plafond de dépenses à augmenter. Aucun job de ce lancement n'a démarré. Cela doit être réglé par le propriétaire du compte dans Billing & plans ; aucun moyen de paiement ou plafond n'a été modifié.

L'environnement local ne dispose ni de Tor ni d'Ollama. Docker Desktop est installé, mais son moteur n'est pas démarré. Les requêtes HTTPS de téléchargement tentées depuis le terminal ont échoué sur la résolution DNS. Aucun modèle ni binaire n'a donc été installé ou téléchargé ici.

## Premières sources configurées

`backend/sources.json` contient trois adresses publiées par leurs opérateurs : Tor Project Community, ProPublica et Amnesty International. Leur provenance est documentée dans `source_registry.json`.

**Ce sont des miroirs publics destinés au diagnostic de connexion.** Ils ne constituent pas le corpus spécialisé demandé et ne promettent pas des informations exclusives au dark web. La provenance d'une adresse ne démontre pas qu'elle répond actuellement : `reachability_verified` reste faux jusqu'à une collecte réelle.

Le collecteur accepte désormais les sous-domaines onion tels que le `www` publié par Amnesty. Les redirections et les accès hors domaines configurés restent refusés.

## Test réel préparé

Le workflow `NOR - live Tor and model connectivity` installe Tor et Ollama sur un runner Linux éphémère, puis télécharge :

- `qwen2.5:1.5b`, petit modèle de conversation de diagnostic ;
- `bge-m3:567m`, modèle d'embeddings multilingue.

Ce choix sert à limiter les ressources du test. Ce n'est pas une sélection finale pour une intelligence de haute qualité. Les tags et tailles sont documentés par l'éditeur du catalogue :

- https://ollama.com/library/qwen2.5:1.5b
- https://ollama.com/library/bge-m3

Le script `backend/live_smoke.py` vérifie réellement :

1. Une réponse structurée du modèle de conversation.
2. Des embeddings pour des phrases française et anglaise.
3. Une collecte Tor d'au moins une des trois sources de diagnostic.
4. L'indexation et une recherche avec synthèse à citations contrôlées.

Il génère `live-smoke.json` sans conserver les contenus des pages dans l'artefact et échoue si une des quatre étapes essentielles ne fonctionne pas. Les pages et vecteurs du test sont stockés dans un répertoire temporaire, puis supprimés. Un test réussi ne fournit ni un serveur permanent, ni une mesure de qualité sur des recherches difficiles.

## Après résolution du blocage GitHub

Relancer les vérifications de la PR. Les workflows de serveur, compilation iOS et connexion réelle doivent tous être examinés ; leurs erreurs éventuelles restent à corriger dans cette PR. Le workflow réel peut télécharger plusieurs gigaoctets sur le runner et consommer des minutes Actions.

La suite reste : sélectionner un modèle adapté au serveur définitif, constituer un corpus spécialisé pertinent, valider les réponses sur des cas réels, héberger le moteur avec HTTPS privé et configurer la signature Apple pour l'iPhone.

## Paramètres du modèle

Les timeouts et limites peuvent être adaptés côté serveur :

```text
NOR_MODEL_TIMEOUT=20
NOR_MODEL_CONTEXT=16384
NOR_MODEL_OUTPUT_LIMIT=2200
```

Les valeurs sont bornées : timeout entre 5 et 120 secondes, contexte entre 2 048 et 32 768, sortie entre 256 et 4 096 tokens. Un modèle lent avec des timeouts élevés peut dépasser l'attente de 180 secondes de l'app ; un traitement asynchrone sera nécessaire pour ces configurations. Aucun réglage ne doit être présenté comme une garantie de rapidité.
