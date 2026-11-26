# Contribuer

Les contributions sont les bienvenues.

## Branches

- `develop` reçoit toutes les contributions.
- `main` correspond à la version en service. Seul le mainteneur y fusionne `develop`, après vérification.

Toute demande de fusion se propose donc sur `develop`. Une demande ouverte directement vers `main` est refusée automatiquement.

## Démarche

1. Créez une copie du dépôt (fork) et une branche à partir de `develop`.
2. Faites vos modifications et lancez les tests :

   ```
   pip install -r requirements-dev.txt
   python -m unittest discover -s tests/unitaires -t . -v
   python -m unittest discover -s tests/integration -p "test_*_it.py" -t . -v
   cd worker && npm ci && npm test
   cd .. && PYTHONPATH=. python -m behave
   ```

   La stratégie de test est décrite dans [docs/strategie-de-test.md](docs/strategie-de-test.md). Un comportement nouveau arrive avec ses tests, au bon niveau, et un bug corrigé avec le test qui l'aurait attrapé.

3. Ouvrez une demande de fusion vers `develop`, en expliquant le problème résolu.

Les tests s'exécutent automatiquement sur chaque demande. Ils n'ont pas accès aux secrets du service et ne déploient rien.

## Données personnelles

N'ajoutez jamais au dépôt de données d'utilisateurs, de jetons ni de secrets, même dans un test. Les tests emploient des identifiants fictifs.
