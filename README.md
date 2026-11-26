# Suivi des passeports à retirer

L'Ambassade de Madagascar en France annonce les passeports prêts en publiant des listes de numéros de quittance. Ces listes paraissent sous forme d'images, sans recherche possible et sans alerte : pour savoir si son passeport est arrivé, il faut revenir sur le site et relire chaque affiche.

Ce projet relève ces affiches, en extrait les numéros et les rend consultables depuis Telegram.

Le service est bénévole, gratuit et sans lien avec l'Ambassade.

## Ce que l'on peut faire depuis Telegram

Le service prend la forme d'un bot Telegram. En lui écrivant, une personne peut :

- **savoir si son passeport est prêt** : elle envoie son numéro de quittance, par exemple `2026-61191`, et reçoit aussitôt la réponse, accompagnée de l'affiche où figure le numéro ;
- **être prévenue plus tard** : si le numéro n'a pas encore été publié, le bot le garde en mémoire et envoie un message le jour où il apparaît dans une liste ;
- **recevoir chaque nouvelle liste** dès que l'Ambassade la publie ;
- **revoir la dernière liste**, consulter ou retirer ses numéros suivis, et se désinscrire à tout moment.

Les commandes disponibles :

| Commande    | Effet                                          |
|-------------|------------------------------------------------|
| `/start`    | Présente le service                            |
| `/derniere` | Renvoie la dernière liste publiée              |
| `/suivis`   | Affiche les numéros suivis, avec leur retrait  |
| `/aide`     | Rappelle le mode d'emploi                      |
| `/stop`     | Désinscrit et efface les numéros suivis        |

## Une lecture automatique, donc faillible

Les numéros sont lus sur les images par reconnaissance de caractères. Le résultat est fiable sur les affiches récentes, moins sur les plus anciennes, de qualité inégale. Un numéro peut être manqué ou mal lu.

C'est pourquoi chaque réponse est accompagnée de l'image d'origine et rappelle de la vérifier avant de se déplacer. En cas de doute, les [listes officielles](https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce) font foi.

## Fonctionnement

Le projet se compose de deux parties indépendantes.

**Le relevé** (`check.py`) s'exécute deux fois par jour, à 11 h et à 19 h, heure de Paris, sur GitHub Actions. Il interroge une seule fois le site de l'Ambassade. Si une affiche nouvelle est parue, il la télécharge, en lit les numéros, met la base à jour, envoie l'affiche à tous les abonnés et prévient ceux qui suivaient l'un des numéros.

**Les réponses** (`worker/src/index.js`) sont assurées en continu par un Worker Cloudflare, que Telegram appelle à chaque message. Le Worker ne contacte jamais le site de l'Ambassade pour répondre : il consulte la base déjà constituée.

Le site est donc sollicité avec retenue : deux appels par jour, et un seul téléchargement par affiche, à sa première parution. Les images sont ensuite servies par Telegram.

### La lecture des affiches

Avant la reconnaissance de caractères, chaque image est agrandie, convertie en noir et blanc, puis débarrassée de son cadre et des traits du tableau, qui perturbent la lecture. Elle est lue six fois, à trois tailles et selon deux modes de mise en page de Tesseract. Un numéro n'est retenu que si deux lectures au moins s'accordent.

## Données et vie privée

- `annonces.json` contient, pour chaque affiche, son titre, son adresse, les numéros lus et l'identifiant de l'image chez Telegram. Ces informations sont publiques : elles proviennent du site de l'Ambassade.
- Les données des utilisateurs ne figurent pas dans ce dépôt. Elles sont conservées chez Cloudflare : l'inscription et les numéros suivis dans le stockage clé-valeur, l'identité et l'historique dans la base D1.
- Pour chaque personne sont enregistrés son identifiant de conversation Telegram, son nom public et son pseudonyme, ainsi que les numéros recherchés, la date de chaque recherche et son résultat. Cela sert à répondre, à prévenir de la publication d'un numéro, et à l'analyse d'usage.
- Les utilisateurs en sont informés par la commande `/confidentialite`, présente dans le menu des commandes et dans l'aide,, qui exposent le traitement et les droits (accès, rectification, effacement) prévus par le RGPD. L'usage du bot vaut acceptation.
- La commande `/stop` efface l'inscription, les numéros suivis, la fiche de la personne et tous ses événements : c'est le droit à l'effacement.
- Aucun numéro de téléphone ni aucun texte libre de message n'est conservé, seulement les numéros de quittance recherchés.

Ces données ne sont jamais versées en clair dans ce dépôt public : la base D1 n'est accessible qu'avec le compte Cloudflare de l'administrateur, et les sauvegardes sont chiffrées.

Les personnes sans aucun message depuis 12 mois sont effacées automatiquement lors du relevé, et prévenues par un dernier message.

### Sauvegardes

Chaque dimanche, un workflow exporte la base D1 et la liste des abonnés, les chiffre en AES-256 avec une phrase secrète (secret `SAUVEGARDE_PHRASE`), puis les dépose dans la branche `sauvegarde`, un fichier par date. Seules les quatre dernières semaines sont gardées, et la branche est réécrite à chaque fois, sans historique : une personne effacée disparaît des sauvegardes en quatre semaines au plus. Sans la phrase secrète, les fichiers sont illisibles.

Pour restaurer, dans une base vide :

```
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -in AAAA-MM-JJ.tar.gz.enc | tar -xzf -
cd worker
npx wrangler d1 execute passeport-bot --remote --file ../base.sql
```

## Statistiques et journaux

Le bot n'expose aucune commande de statistiques : les données ne se consultent qu'en base, avec les droits du compte Cloudflare.

Les tables `personnes` et `evenements` s'interrogent en SQL. Le fichier [analytics/requetes.sql](analytics/requetes.sql) rassemble des requêtes prêtes à l'emploi : recherches par jour, fiche par personne, numéros les plus demandés, délai entre une recherche et la publication.

```
cd worker
npx wrangler d1 execute passeport-bot --remote --command "SELECT type, COUNT(*) FROM evenements GROUP BY type"
npx wrangler d1 execute passeport-bot --remote --json --file ../analytics/requetes.sql > resultats.json
```

| Type d'événement  | Signification                                        |
|-------------------|------------------------------------------------------|
| `demarrage`       | Commande `/start`                                    |
| `recherche`       | Numéro envoyé, avec `trouve` à 1 ou 0                |
| `suivi_ajoute`    | Numéro non publié mis en suivi                       |
| `suivi_retire`    | Suivi retiré par l'utilisateur                       |
| `alerte_suivi`    | Abonné prévenu de la publication d'un numéro suivi   |
| `diffusion`       | Nouvelle liste envoyée, `valeur` = nombre d'abonnés  |
| `desinscription`  | Commande `/stop`                                     |
| `derniere`, `suivis`, `aide`, `message_autre` | Autres actions                   |

Les journaux d'exécution du Worker, au format JSON, se consultent dans le tableau de bord Cloudflare, onglet Observabilité du Worker, ou en direct avec `npx wrangler tail`.

## Tests et déploiement

Chaque envoi sur `main` et chaque demande de fusion lancent deux séries de tests sur GitHub Actions :

- le relevé : nettoyage des titres, reconnaissance des numéros, et lecture complète de trois affiches de référence dont le contenu a été contrôlé à l'œil ;
- le Worker : accueil, recherche, suivi, désinscription, confidentialité et contrôle des accès.

Si les tests réussissent sur `main`, une release numérotée est créée sur GitHub, avec ses notes de version, puis cette version est déployée : les migrations de la base sont appliquées et le Worker est mis en ligne, étiqueté du numéro de la release. Un échec du déploiement ou du relevé quotidien déclenche un message Telegram à l'administrateur.

Pour lancer les tests en local :

```
python -m unittest discover -s tests -v
cd worker && npm ci && npm test
```

## Structure du dépôt

```
check.py                      relevé, lecture des affiches, diffusion
annonces.json                 base des affiches et des numéros lus
requirements.txt              dépendances Python, versions figées
tests/                        tests du relevé et affiches de référence
worker/src/index.js           réponses aux messages (Worker Cloudflare)
worker/migrations/            schéma de la base de statistiques
worker/test/                  tests du Worker
worker/wrangler.toml          configuration du Worker
analytics/requetes.sql        requêtes d'analyse
.github/workflows/check.yml   planification du relevé
.github/workflows/ci.yml      tests, release et déploiement
.github/workflows/sauvegarde.yml   sauvegarde hebdomadaire chiffrée
.github/workflows/branche-cible.yml   contrôle de la branche des contributions
CONTRIBUTING.md               règles de contribution
```

## Installer sa propre instance

Prérequis : un bot Telegram créé auprès de BotFather, un compte Cloudflare, un compte GitHub, Node.js, Python 3.11 ou plus récent, Tesseract.

1. **Créer le stockage et déployer le Worker**

   ```
   cd worker
   npx wrangler login
   npm ci
   npx wrangler kv namespace create passeport-bot
   npx wrangler d1 create passeport-bot
   ```

   Reporter les deux identifiants obtenus dans `wrangler.toml`, puis :

   ```
   npx wrangler d1 migrations apply passeport-bot --remote
   npx wrangler deploy
   ```

2. **Définir les secrets du Worker**

   ```
   npx wrangler secret put TELEGRAM_BOT_TOKEN
   npx wrangler secret put WEBHOOK_SECRET
   npx wrangler secret put ADMIN_SECRET
   ```

   `WEBHOOK_SECRET` et `ADMIN_SECRET` sont deux chaînes aléatoires à choisir. La première authentifie les appels de Telegram, la seconde ceux du relevé.

3. **Publier la base et brancher Telegram sur le Worker**

   Avec `TELEGRAM_BOT_TOKEN`, `WORKER_URL`, `ADMIN_SECRET` et `WEBHOOK_SECRET` dans l'environnement :

   ```
   pip install -r requirements.txt
   python check.py --publier
   python check.py --setup
   ```

4. **Planifier le relevé**

   Ajouter aux secrets du dépôt GitHub :

   | Secret                  | Rôle                                                              |
   |-------------------------|-------------------------------------------------------------------|
   | `TELEGRAM_BOT_TOKEN`    | Jeton du bot                                                      |
   | `WORKER_URL`            | Adresse du Worker                                                 |
   | `ADMIN_SECRET`          | Secret partagé avec le Worker                                     |
   | `TELEGRAM_CHAT_ID`      | Conversation de l'administrateur, pour les alertes d'échec        |
   | `CLOUDFLARE_API_TOKEN`  | Jeton Cloudflare avec les droits Workers, KV et D1 en écriture    |
   | `SAUVEGARDE_PHRASE`     | Phrase secrète de chiffrement des sauvegardes                     |

   Et une variable du dépôt, `CONTACT` : le pseudo Telegram affiché par `/confidentialite` pour les demandes RGPD.

   Le relevé s'exécute ensuite seul, et peut être lancé à la main depuis l'onglet Actions.

Options de `check.py` :

| Option       | Effet                                                            |
|--------------|------------------------------------------------------------------|
| (aucune)     | Relevé complet : détection, lecture, publication, diffusion      |
| `--dry-run`  | Affiche les nouvelles affiches sans rien envoyer ni enregistrer  |
| `--publier`  | Envoie la base au Worker                                         |
| `--setup`    | Configure le webhook, le menu et la présentation du bot          |

## Contribuer

Les demandes de fusion se proposent sur la branche `develop`, voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Le code est distribué sous licence MIT, voir [LICENSE](LICENSE).

Les listes et les images restent la propriété de l'Ambassade de Madagascar en France, qui les publie.

Le projet s'appuie sur des composants tiers, chacun sous sa propre licence :

| Composant  | Usage                             | Licence              |
|------------|-----------------------------------|----------------------|
| Tesseract  | Reconnaissance de caractères      | Apache 2.0           |
| Pillow     | Traitement des images             | MIT-CMU              |
| NumPy      | Calcul sur les pixels             | BSD 3 clauses        |
| Wrangler   | Déploiement du Worker             | MIT ou Apache 2.0    |
