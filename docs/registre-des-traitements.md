# Registre des activités de traitement

Tenu en application de l'article 30 du règlement général sur la protection des données (RGPD).

Dernière mise à jour : 26 novembre 2026.

## Responsable du traitement

| | |
|---|---|
| Nom | Administrateur bénévole du service, à titre personnel |
| Contact | Indiqué par la commande `/confidentialite` du bot |
| Service | Bot Telegram `@passeport_paris_mg_bot`, « Passeport Madagascar Paris » |
| Délégué à la protection des données | Aucun, non obligatoire pour ce service |

Le service est indépendant de l'Ambassade de Madagascar en France. Il ne traite aucune donnée pour son compte.

## Traitement n° 1 : fonctionnement du service

**Finalités**
- Répondre à la recherche d'un numéro de quittance.
- Garder en mémoire les numéros pas encore publiés et prévenir la personne quand ils paraissent.
- Envoyer aux abonnés l'annonce de chaque nouvelle liste.

**Base légale** : exécution du service demandé par la personne (article 6.1.b), qui écrit elle-même au bot et peut se désinscrire à tout moment.

**Personnes concernées** : toute personne qui écrit au bot.

**Données traitées**

| Donnée | Origine | Lieu de stockage |
|---|---|---|
| Identifiant de conversation Telegram | Telegram, à chaque message | Cloudflare Workers KV |
| Numéros de quittance suivis (5 au plus) | Saisis par la personne | Cloudflare Workers KV |

**Durée de conservation** : jusqu'à la commande `/stop`, ou 12 mois sans aucun message de la personne. Effacement automatique dans les deux cas.

## Traitement n° 2 : mesure d'usage et amélioration du service

**Finalités** : connaître la fréquentation, les numéros recherchés, le délai entre une recherche et la publication du numéro, et améliorer le service.

**Base légale** : intérêt légitime du responsable à connaître et améliorer son service (article 6.1.f). Les personnes en sont informées par la commande `/confidentialite`, présente dans le menu des commandes et dans l'aide, et peuvent s'y opposer à tout moment par `/stop`. Le traitement se limite aux données nécessaires, sans profilage ni décision automatisée.

**Personnes concernées** : toute personne qui écrit au bot.

**Données traitées**

| Donnée | Origine | Lieu de stockage |
|---|---|---|
| Identifiant de conversation Telegram | Telegram | Cloudflare D1, table `personnes` |
| Prénom, nom et pseudonyme publics | Profil Telegram | Cloudflare D1, table `personnes` |
| Langue de l'application | Telegram | Cloudflare D1, table `personnes` |
| Dates de première et de dernière visite | Calculées | Cloudflare D1, table `personnes` |
| Actions : arrivée, recherche, suivi, désinscription | Usage du bot | Cloudflare D1, table `evenements` |
| Numéros de quittance recherchés et résultat | Saisis par la personne | Cloudflare D1, table `evenements` |

Aucune donnée sensible au sens de l'article 9 n'est collectée. Le numéro de téléphone, la localisation et le texte libre des messages ne sont pas conservés.

**Durée de conservation** : comme le traitement n° 1. À la commande `/stop` ou après 12 mois d'inactivité, la fiche de la personne et tous ses événements sont supprimés.

## Destinataires

Seul le responsable du traitement accède aux données, par la console Cloudflare ou la ligne de commande. Elles ne sont ni vendues ni transmises à des tiers.

## Sous-traitants et hébergeurs

| Prestataire | Rôle | Données concernées | Localisation |
|---|---|---|---|
| Cloudflare, Inc. | Hébergement du bot, de la base et des journaux | Toutes | Mondiale, base D1 en Europe de l'Est |
| GitHub, Inc. (Microsoft) | Relevé planifié, sauvegardes, code | Sauvegardes de la base | États-Unis |
| Telegram Messenger Inc. | Messagerie | Messages échangés avec le bot | Telegram, selon ses propres conditions |

**Transferts hors de l'Union européenne** : Cloudflare et GitHub sont des sociétés américaines adhérentes au Data Privacy Framework UE-États-Unis, ce qui encadre les transferts vers les États-Unis.

## Sauvegardes

Une copie de la base et de la liste des abonnés est exportée chaque dimanche, chiffrée en AES-256 avec une phrase secrète connue du seul responsable, puis déposée dans la branche `sauvegarde` du dépôt GitHub. Seules les quatre dernières copies sont gardées, sans historique. Une personne effacée disparaît donc des sauvegardes en quatre semaines au plus.

## Journaux techniques

Les journaux d'exécution du bot (Cloudflare Workers Observability) contiennent l'identifiant de conversation et l'action réalisée. Leur durée de conservation est fixée par Cloudflare et se limite à quelques jours dans l'offre gratuite.

## Mesures de sécurité

- Accès aux données réservé au compte Cloudflare du responsable.
- Aucune donnée d'utilisateur en clair dans le dépôt GitHub, public, ni dans son historique : les sauvegardes y sont chiffrées.
- Secrets (jeton du bot, clés d'administration) stockés dans les coffres de Cloudflare et de GitHub, jamais dans le code.
- Appels au bot authentifiés par un secret partagé avec Telegram ; routes d'administration protégées par un second secret.
- Échanges chiffrés en transit (HTTPS).

## Droits des personnes

| Droit | Mise en œuvre |
|---|---|
| Information | Commande `/confidentialite` |
| Accès, rectification | Demande au contact indiqué par `/confidentialite`, réponse sous un mois |
| Effacement | Commande `/stop`, effet immédiat ; demande au contact sinon |
| Opposition | Commande `/stop` |

Toute personne peut aussi saisir la CNIL : www.cnil.fr.

## Historique des modifications

| Date | Modification |
|---|---|
| 26/11/2026 | Création du registre |
| 26/11/2026 | Mesure d'usage : base légale de l'intérêt légitime |
| 26/11/2026 | Dépôt rendu public, sauvegardes chiffrées |
