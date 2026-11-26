# Stratégie de test

Ce projet applique la stratégie décrite dans l'[engineering playbook](https://github.com/Harrylepap/engineering-playbook/blob/main/03-tester.md) : chaque niveau de test répond à une seule question.

## Une question par niveau

| Niveau | La question | Ce qu'il touche | Où | Convention |
|---|---|---|---|---|
| Unitaire | Cette règle de gestion est-elle juste ? | Une fonction, sans réseau ni base | `tests/unitaires/`, `worker/test/unitaire/` | `*Test` |
| Intégration | Ce composant parle-t-il correctement à ses dépendances ? | Le relevé avec Tesseract et le site simulé ; le Worker avec une vraie base D1 locale | `tests/integration/`, `worker/test/integration/` | `*IT` |
| API | Le contrat exposé tient-il, vu de l'extérieur ? | Le Worker démarré, appelé comme Telegram et le relevé l'appellent | `worker/test/api/` | `*ApiScenario` |
| Bout en bout | Le parcours utilisateur complet fonctionne-t-il ? | Le relevé, la lecture des affiches, le Worker ; le site et Telegram simulés | `features/` | Gherkin |

## Les règles appliquées

**Boîte noire au-dessus de l'unitaire.** Les scénarios d'API et de bout en bout n'importent aucune fonction interne et ne lisent jamais la base. Ils envoient des messages au webhook, appellent les routes d'administration, et observent ce que Telegram reçoit. Seuls les tests d'intégration du Worker interrogent la base D1, puisque leur question porte précisément sur elle.

**Pas de données préchargées.** Chaque test démarre sur une base vide et crée ce dont il a besoin par les chemins d'un vrai client : un message au bot, ou la publication de la base par la route qu'emprunte le relevé. Chaque scénario utilise sa propre conversation, pour que les tests ne dépendent pas les uns des autres.

**Le même test, partout.** Les adresses du site, de Telegram et du Worker, ainsi que l'emplacement de la base, se règlent par variables d'environnement (`SITE_ANNONCES_URL`, `TELEGRAM_API_URL`, `WORKER_URL`, `ANNONCES_JSON`, `TELEGRAM_API`). Le code ne connaît pas l'environnement dans lequel il tourne.

**Aucun secret réel.** Le Worker de test démarre avec un fichier d'environnement fictif, qui remplace `.dev.vars`. Aucun appel ne part vers Telegram ni vers le site de l'Ambassade.

## Les partenaires simulés

| Partenaire | Simulation |
|---|---|
| Site de l'Ambassade | Sert la liste des annonces en JSON, précédée des notices PHP du vrai site, et les trois affiches de référence |
| API Telegram | Enregistre chaque appel et répond comme le vrai service, identifiant de fichier compris |
| Cloudflare KV et D1 | Réels, en local, par `wrangler dev` |
| Tesseract | Réel |

## Les affiches de référence

Trois affiches, choisies pour leurs difficultés, ont été lues à l'œil et servent d'étalon : une capture basse résolution à cadre orange, un tableau à traits épais mêlant deux années, un export net sur deux colonnes. Leur lecture complète doit rendre exactement les numéros attendus.

## Lancer les tests

```
python -m unittest discover -s tests/unitaires -t . -v
python -m unittest discover -s tests/integration -p "test_*_it.py" -t . -v
cd worker && npm ci && npm run test:unitaire && npm run test:integration && npm run test:api
cd .. && PYTHONPATH=. python -m behave
```

L'intégration du relevé et le bout en bout exigent Tesseract. Le bout en bout démarre lui-même le Worker en local.

## La couverture, sans s'y soumettre

La couverture des tests unitaires s'affiche dans le résumé de chaque exécution de la CI. Elle sert à repérer les angles morts, sans seuil imposé.

## Dans la CI

```
Unitaires ──┬── Intégration ──┐
            └── API ──────────┴── Bout en bout ── Release ── Déploiement
```

Les niveaux rapides passent d'abord. Une release n'est créée, et le Worker déployé, que si les quatre niveaux réussissent sur `main`.
