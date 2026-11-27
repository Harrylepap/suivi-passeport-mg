"""Envoi des annonces aux abonnés, des alertes de suivi, et enregistrement des rappels."""
import json
import sys
import time

from releve import config
from releve.publication import legende_publication, nom_court
from releve.reseau import ErreurHttp, journaliser, telegram, worker


def envoyer_affiche(chat, fiche, legende, contenu):
    """Envoie l'image d'une affiche, en réutilisant son file_id Telegram s'il est connu."""
    fields = {"chat_id": chat, "caption": legende, "parse_mode": "HTML"}
    if fiche.get("file_id"):
        telegram("sendPhoto", {**fields, "photo": fiche["file_id"]})
    elif contenu:
        nom = fiche["image"].rsplit("/", 1)[-1]
        rep = telegram("sendPhoto", fields, file=("photo", nom, contenu))
        fiche["file_id"] = rep["result"]["photo"][-1]["file_id"]
    else:
        telegram("sendMessage", {
            "chat_id": chat, "text": legende, "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Voir l'affiche", "url": fiche["image"]}]]}),
        })


def vers_abonne(chat, envoi):
    """Exécute un envoi vers un abonné ; le désabonne s'il a bloqué le bot. Renvoie True si l'envoi a réussi."""
    reussi = False
    try:
        envoi()
        reussi = True
    except ErreurHttp as exc:
        if exc.code == 403:
            worker("DELETE", f"/admin/abonnes/{chat}")
            print("Un abonné retiré (bot bloqué)")
        else:
            print(f"Envoi impossible ({exc})", file=sys.stderr)
    except Exception as exc:
        print(f"Envoi impossible ({exc})", file=sys.stderr)
    time.sleep(0.05)
    return reussi


def diffuser(jour, elements, abonnes, precedentes):
    """Annonce les affiches d'un même jour à tous les abonnés, puis prévient ceux qui suivaient un numéro."""
    texte = legende_publication(jour, [f for f, _ in elements], precedentes)
    champs = {
        "text": texte,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Voir les listes officielles", "url": config.PAGE}]]}),
    }
    for abonne in abonnes:
        vers_abonne(abonne["chat"], lambda: telegram("sendMessage", {"chat_id": abonne["chat"], **champs}))
    for fiche, contenu in elements:
        alerter_suivis(fiche, contenu, abonnes)
    journaliser([{"type": "diffusion", "liste": nom_court(f), "valeur": len(abonnes)} for f, _ in elements])
    print(f"Diffusion de {len(elements)} affiches à {len(abonnes)} abonnés")


def programmer_rappels(rappels):
    """Demande au Worker de rappeler, quelques jours plus tard, d'aller retirer les passeports annoncés."""
    if not rappels:
        return
    try:
        worker("POST", "/admin/rappels", {"rappels": rappels})
    except Exception as exc:
        print(f"Rappels non programmés ({exc})", file=sys.stderr)


def alerter_suivis(fiche, contenu, abonnes):
    """Prévient les abonnés dont un numéro suivi figure dans l'affiche, et programme leur rappel."""
    numeros = set(fiche["numeros"] or [])
    evenements, rappels = [], []
    for abonne in abonnes:
        sortis = [n for n in abonne["suivis"] if n in numeros]
        if not sortis:
            continue
        evenements += [
            {"type": "alerte_suivi", "chat": abonne["chat"], "numero": n, "liste": nom_court(fiche)} for n in sortis
        ]
        accord = "est publié" if len(sortis) == 1 else "sont publiés"
        legende = (
            f"✅ <b>Bonne nouvelle : {', '.join(sortis)} {accord}</b>\n"
            f"Liste {nom_court(fiche)}\n\n"
            f"{config.PRUDENCE}"
        )
        if vers_abonne(abonne["chat"], lambda: envoyer_affiche(abonne["chat"], fiche, legende, contenu)):
            rappels += [{"chat": abonne["chat"], "numero": n, "liste": nom_court(fiche)} for n in sortis]
    if evenements:
        journaliser(evenements)
    programmer_rappels(rappels)
