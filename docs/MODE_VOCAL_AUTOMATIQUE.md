# Conversation vocale automatique — NOR v0.4

## Cycle ajouté au code

Activer « Conversation vocale automatique » ouvre la dictée locale dans la langue choisie. Une fois le texte reconnu et une pause suffisante détectée, NOR ferme le microphone et dit :

> D’accord, laisse-moi un instant pour examiner les sources.

La recherche ne démarre qu'après la fin de cette annonce. NOR lit ensuite la réponse, puis termine par :

> As-tu une autre question ?

Il attend la fin complète de cette lecture et un bref délai de stabilisation audio avant de rouvrir le microphone. Le microphone reste fermé pendant l'annonce, la recherche et la réponse : la voix de NOR ne doit pas devenir une nouvelle question.

Équivalents anglais :

> Alright, give me a moment to review the sources.

> Do you have another question?

Les références `[S1]` restent visibles dans le texte et les citations à l'écran, mais ne sont pas lues comme des mots.

## Pause et limites

- Pause par défaut : 3,5 secondes, réglable entre 2 et 6 secondes dans les réglages de la voix.
- Les changements de transcription et les signaux audio au-dessus d'un seuil repoussent la fin de question. Cette méthode est une heuristique ; elle n'offre pas la précision d'un détecteur de parole entraîné et calibré sur les appareils réels.
- Une pièce bruyante peut retarder l'envoi ; une voix très faible peut nécessiter une pause plus longue. Les autorisations et le modèle de dictée local doivent être disponibles sur l'iPhone.
- Sans question exploitable pendant 25 secondes, le mode se met en pause. Il ne recherche pas à partir du silence.
- Après 60 secondes d'écoute continue, ou si le moteur de dictée s'arrête trop tôt, le texte est conservé pour être complété ou envoyé manuellement. Une question incomplète n'est pas envoyée automatiquement.
- Une question de plus de 2 000 caractères est conservée et doit être raccourcie.

## Arrêt et confidentialité

Le bouton « Arrêter la voix » ou la désactivation du mode arrête l'écoute et la lecture et annule l'attente de recherche côté app. Une réponse réseau tardive d'une session arrêtée ne relance ni la voix ni le microphone. Le serveur peut cependant terminer un calcul déjà engagé.

Le passage en arrière-plan, une interruption audio, la déconnexion d'un périphérique audio, l'ouverture des réglages ou un changement de langue désactivent le mode. Il faut le réactiver explicitement. Les demandes initiales de permissions peuvent temporairement rendre l'app inactive ; elles sont distinguées du passage en arrière-plan.

Le mode n'est pas réactivé automatiquement au lancement suivant. L'interface indique quand NOR écoute, cherche ou parle. Aucun enregistrement audio n'est conservé par le code de NOR et la reconnaissance exige le mode local. Le texte de la question est envoyé au serveur configuré, comme pour une recherche écrite.

En cas de refus des permissions, d'absence de voix masculine, d'indisponibilité de la dictée locale ou d'erreur serveur, le mode s'arrête et affiche une explication. Il ne boucle pas silencieusement sur une erreur.

## Validation restant à faire

Le code et neuf nouveaux tests XCTest sont écrits. Avec les deux tests précédents, la suite iOS comporte onze tests. Aucun n'a été compilé ou exécuté sous Windows. Le moteur du serveur n'est pas modifié par cette fonctionnalité ; ses 43 tests avaient passé lors de la version précédente.

Le workflow macOS doit d'abord compiler et exécuter ces tests. Un test sur iPhone réel doit ensuite vérifier :

1. Les permissions initiales et leur refus.
2. Une pause courte au milieu d'une question, puis la fin réelle de la question.
3. L'ordre exact annonce → recherche → réponse → question de suivi → nouvelle écoute.
4. L'absence de reconnaissance de la voix de NOR et les différences entre haut-parleur et écouteurs.
5. Les arrêts pendant chaque phase, une réponse réseau tardive et les interruptions audio.
6. La dictée locale, la voix masculine et le cycle complet en français et en anglais.

La qualité de la détection des pauses, le rendu sonore et le comportement matériel ne sont pas encore validés.
