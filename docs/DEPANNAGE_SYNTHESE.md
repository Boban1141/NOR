# Diagnostic de la synthèse

Le premier essai réel communiqué par l'utilisateur a confirmé le modèle de conversation, les embeddings et une collecte Tor, mais aucune synthèse : `synthesis_unavailable`. Ce résultat ne permettait pas de distinguer un délai dépassé, une réponse JSON invalide ou une autre panne.

Le rapport contient désormais `diagnostics`, avec un code sans contenu privé :

| Code | Signification |
|---|---|
| `model_timeout` | Le délai du modèle a été dépassé. |
| `model_connection_error` | La connexion au service a échoué. |
| `model_http_error` | Le service a renvoyé une réponse HTTP non réussie. |
| `invalid_structured_response` | Le résultat ne respecte pas le schéma attendu. |
| `model_output_truncated` | Le modèle a signalé une fin liée à sa limite de sortie. |
| `model_error` | Erreur sans catégorie publique reconnue. |

Les citations restent contrôlées à l'identique ; aucun contrôle de preuve n'a été retiré pour obtenir artificiellement un succès. Le prompt demande au maximum trois affirmations concises.

Pour l'essai avec Qwen 2.5 1.5B sur CPU, la configuration locale peut utiliser un délai de 90 secondes, un contexte de 8 192 et une sortie de 1 024 tokens. Ce sont des paramètres de diagnostic, pas une garantie de correction. Des délais élevés peuvent dépasser l'attente globale de l'app iPhone ; le traitement asynchrone reste à prévoir pour les recherches longues.

Relancer depuis le dossier NOR :

```powershell
.\.venv\Scripts\python.exe backend\manage.py verify
```

L'accès Tor n'est considéré réussi qu'après collecte, et la synthèse seulement si au moins une affirmation avec citation exacte est acceptée. Les deux sources précédemment inaccessibles peuvent rester indisponibles indépendamment de la synthèse.
