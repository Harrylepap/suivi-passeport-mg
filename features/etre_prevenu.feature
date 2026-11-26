# language: fr
Fonctionnalité: Être prévenu de la publication de son numéro
  Pour ne pas avoir à revenir chaque jour
  En tant que personne dont le numéro n'est pas encore publié
  Je veux que le bot me prévienne le jour où il paraît

  Contexte:
    Étant donné que l'Ambassade a publié les listes "BEG 2025-016"
    Et que le relevé est passé

  Scénario: Mon numéro suivi paraît dans une nouvelle liste
    Étant donné que j'ai envoyé "2026-61191" au bot
    Quand l'Ambassade publie la liste "BEG 2026-066"
    Et que le relevé passe
    Alors je reçois l'annonce "Nouvelle liste publiée le 24/11/2026"
    Et l'annonce rappelle la publication précédente du "16/05/2025"
    Et je reçois l'alerte "2026-61191 est publié"

  Scénario: Je ne reçois plus rien après m'être désinscrit
    Étant donné que j'ai envoyé "2026-61191" au bot
    Et que j'ai envoyé "/stop" au bot
    Quand l'Ambassade publie la liste "BEG 2026-066"
    Et que le relevé passe
    Alors je ne reçois ni annonce ni alerte
