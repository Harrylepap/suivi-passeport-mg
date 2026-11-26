# language: fr
Fonctionnalité: Savoir si son passeport est prêt
  Pour ne plus relire chaque affiche à l'œil
  En tant que personne qui attend son passeport
  Je veux envoyer mon numéro de quittance au bot et savoir s'il a été publié

  Contexte:
    Étant donné que l'Ambassade a publié les listes "BEG 2025-038, BEG 2026-066"
    Et que le relevé est passé

  Scénario: Mon numéro figure dans une liste publiée
    Quand j'envoie "2026-61191" au bot
    Alors le bot me répond que "2026-61191" est publié dans la liste "BEG 2026-066"
    Et la réponse contient l'affiche

  Scénario: Mon numéro n'est pas encore publié
    Quand j'envoie "2026-99999" au bot
    Alors le bot me répond que "2026-99999" n'est pas encore publié
    Et il me propose de me prévenir

  Scénario: J'envoie mon numéro sans l'année
    Quand j'envoie "53580" au bot
    Alors le bot me répond que "2025-53580" est publié dans la liste "BEG 2025-038"
