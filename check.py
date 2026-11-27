"""Point d'entrée du relevé des listes de passeports à retirer."""
import json
import sys

from releve import config
from releve.bilan import bilan_releve, controler_lecture, purger, verifier_service
from releve.diffusion import alerter_suivis, diffuser
from releve.lecture import indexer
from releve.publication import grouper_par_jour, publication_precedente
from releve.reseau import alerter_admin, telegram, worker
from releve.site import ecrire_base, fetch_annonces, lire_base, publier_base


def relever(dry=False):
    """Détecte les nouvelles affiches, les indexe, publie la base, les diffuse et envoie le bilan."""
    base = lire_base()
    premiere_fois = not base["annonces"]
    connues = {a["image"] for a in base["annonces"]}
    nouvelles = [a for a in reversed(fetch_annonces()) if a["image"] not in connues]

    if dry:
        for a in nouvelles:
            print(f"Nouvelle annonce : {a['titre']} -> {a['image']}")
        if not nouvelles:
            print("Rien de nouveau")
        return

    en_attente = [f for f in base["annonces"] if f["numeros"] is None]
    abonnes = worker("GET", "/admin/abonnes")["abonnes"] if (nouvelles or en_attente) else []

    for fiche in en_attente:
        relue, contenu = indexer(fiche)
        if relue["numeros"] is not None:
            fiche.update(relue)
            ecrire_base(base)
            publier_base(base)
            alerter_suivis(fiche, contenu, abonnes)

    elements = []
    for a in nouvelles:
        fiche, contenu = indexer(a)
        nb = "?" if fiche["numeros"] is None else len(fiche["numeros"])
        print(f"Nouvelle annonce : {a['titre']} ({nb} numéros)")
        base["annonces"].append(fiche)
        ecrire_base(base)
        elements.append((fiche, contenu))
    if elements:
        publier_base(base)

    if not premiere_fois:
        for jour, groupe in grouper_par_jour(elements):
            for fiche, _ in groupe:
                controler_lecture(fiche)
            diffuser(jour, groupe, abonnes, publication_precedente(base["annonces"], jour))
            ecrire_base(base)

    if not nouvelles:
        print("Rien de nouveau")
    publier_base(base)
    purger()
    anomalies = verifier_service()
    alerter_admin(bilan_releve(base, [f for f, _ in elements], anomalies), silencieux=not anomalies)


def configurer_bot():
    """Branche Telegram sur le Worker et définit le menu et la présentation du bot."""
    import os

    rep = telegram("setWebhook", {
        "url": os.environ["WORKER_URL"].rstrip("/") + "/webhook",
        "secret_token": os.environ["WEBHOOK_SECRET"],
        "allowed_updates": '["message","callback_query"]',
    })
    print("Webhook :", rep.get("description"))
    commandes = [{"command": c, "description": d} for c, d in config.COMMANDES]
    telegram("setMyCommands", {"commands": json.dumps(commandes, ensure_ascii=False)})
    telegram("setMyShortDescription", {
        "short_description": "Suivi des passeports à retirer à l'Ambassade de Madagascar en France. Service bénévole, non officiel.",
    })
    telegram("setMyDescription", {
        "description": (
            "Envoyez votre numéro de quittance pour savoir si votre passeport figure dans une liste "
            "publiée par l'Ambassade de Madagascar en France, et recevez chaque nouvelle liste.\n\n"
            "Service bénévole et gratuit, indépendant de l'Ambassade."
        ),
    })
    print("Bot configuré")


def main():
    """Point d'entrée : --setup, --publier, --dry-run, ou relevé complet sans option."""
    if "--setup" in sys.argv:
        return configurer_bot()
    if "--publier" in sys.argv:
        return publier_base(lire_base())
    relever(dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
