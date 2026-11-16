# Diagnostiquer les sources indisponibles

Les anciens résumés ne conservaient pas les causes d'échec. Les 13 échecs précédents ne peuvent donc pas être attribués rétrospectivement à une panne réseau, un code HTTP ou une redirection.

Depuis le dossier NOR :

```powershell
.\.venv\Scripts\python.exe backend\manage.py diagnose-sources
```

Ce contrôle tente uniquement les adresses de départ, sans suivre leurs liens ni les redirections. Le budget nominal est de 180 secondes au total ; les timeouts par requête restent inchangés. Les pages HTML reçues sont conservées et indexées lexicalement. Aucun modèle IA n'est appelé et les embeddings ne sont pas recalculés.

La sortie et `.runtime/source-diagnostics.json` contiennent le nom déclaré de chaque source testée, les compteurs, codes HTTP et catégories d'erreur. Aucun texte de page, URL complète, cible de redirection, question ou jeton n'est placé dans ce rapport. Un SHA-256 de l'hôte sert d'identifiant ; ce condensat ne garantit pas l'anonymisation des domaines publics connus. Le rapport local est remplacé à chaque diagnostic et reste ignoré par Git.

| Code | Interprétation |
| --- | --- |
| `http_error` | Réponse HTTP différente de 200 ; consulter `http_statuses` pour distinguer 403, 404, 429, 503, etc. |
| `redirect_same_host` | Redirection vers le même hôte onion, bloquée. Vérifier le chemin canonique auprès de l'opérateur. |
| `redirect_other_host` | Redirection vers un autre hôte onion, bloquée. Le catalogue autorisé ne change pas. |
| `redirect_invalid_target` | Cible incompatible avec les règles des sources, notamment une URL hors onion. |
| `redirect_blocked` | Redirection sans cible exploitable. |
| `proxy_error` | Échec signalé par le transport proxy ; ne prouve pas que Tor entier est hors service. |
| `network_timeout` | Délai réseau dépassé. Un timeout encapsulé peut être classé `connection_error`. |
| `tls_error` | Erreur TLS. La vérification des certificats reste active. |
| `connection_error` | Connexion interrompue ou impossible, sans cause plus précise disponible. |
| `unsupported_content_type` | Réponse non HTML refusée. |
| `page_size_limit`, `page_time_limit` | Plafond de taille ou budget de lecture dépassé. |
| `request_error`, `page_rejected` | Autre rejet du transport ou de la validation ; aucune exception brute n'est reproduite. |

`unattempted_hosts` distingue les domaines non testés de ceux en échec. Pour le diagnostic, un code de sortie 1 indique un résultat partiel, un échec ou aucune source collectée. Une sortie 0 indique que toutes les sources configurées ont été tentées sans échec ; elle ne certifie ni la qualité ni la vérité du contenu.

`collect` conserve aussi un bilan dans `.runtime/collection-report.json`. Les tentatives sont maintenant réparties entre hôtes, même sans question. `stop_reason` distingue `page_limit`, `time_budget` et `completed` ; `budget_exhausted` reste présent pour compatibilité.

Les redirections, le repli réseau direct et l'exécution de JavaScript restent interdits. Aucun nouvel essai automatique ni délai supplémentaire par page n'est ajouté. Une correction des adresses ou du transport sera fondée sur les codes réellement obtenus et sur la provenance officielle des adresses.

Validation : 100 tests Python passent, dont 14 nouveaux cas sur les erreurs, les redirections, les rapports, la répartition des tentatives et l'absence de jeton dans la sortie. Les transports sont simulés ; la disponibilité réelle des sources reste à vérifier sur le PC de l'utilisateur.
