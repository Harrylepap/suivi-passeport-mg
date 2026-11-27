"""Contrôles et bilan adressés à l'administrateur."""
import html
import os
import sys
import time

from releve import config
from releve.publication import jour_publication, ligne_liste, nom_court
from releve.reseau import alerter_admin, http, telegram, worker


def controler_lecture(fiche):
    """Prévient l'administrateur si le nombre de numéros lus sur une affiche paraît anormal."""
    nb = len(fiche["numeros"] or [])
    bas, haut = config.NUMEROS_ATTENDUS
    if fiche["numeros"] is None:
        motif = "la lecture a échoué"
    elif nb == 0:
        motif = "aucun numéro lu"
    elif nb < bas or nb > haut:
        motif = f"{nb} numéros lus, nombre inhabituel"
    else:
        return
    alerter_admin(f"Lecture à vérifier : {html.unescape(nom_court(fiche))}, {motif}.\n{fiche['image']}")


def purger():
    """Demande au Worker d'effacer les personnes inactives depuis la durée de conservation."""
    try:
        rep = worker("POST", "/admin/purge", {})
        if rep["purges"]:
            print(f"Personnes inactives effacées : {rep['purges']}")
    except Exception as exc:
        print(f"Purge impossible ({exc})", file=sys.stderr)


def anomalies_webhook(info, worker_url, maintenant=None):
    """Analyse l'état du webhook renvoyé par Telegram et liste ce qui ne va pas."""
    maintenant = maintenant or time.time()
    anomalies = []
    attendu = worker_url.rstrip("/") + "/webhook"
    if info.get("url") != attendu:
        anomalies.append(f"webhook mal branché ({info.get('url') or 'aucune adresse'})")
    if info.get("pending_update_count", 0) > 20:
        anomalies.append(f"{info['pending_update_count']} messages en attente de traitement")
    if info.get("last_error_date", 0) > maintenant - 12 * 3600:
        anomalies.append(f"erreur récente de Telegram : {info.get('last_error_message', 'inconnue')}")
    return anomalies


def verifier_service():
    """Vérifie que le Worker répond et que Telegram lui transmet bien les messages."""
    anomalies = []
    try:
        if http(os.environ["WORKER_URL"].rstrip("/") + "/", timeout=15).decode() != "Bot en ligne":
            anomalies.append("le Worker répond de façon inattendue")
    except Exception as exc:
        anomalies.append(f"le Worker ne répond pas ({exc})")
    try:
        info = telegram("getWebhookInfo", {}).get("result") or {}
        anomalies += anomalies_webhook(info, os.environ["WORKER_URL"])
    except Exception as exc:
        anomalies.append(f"état du webhook illisible ({exc})")
    return anomalies


def bilan_releve(base, nouvelles, anomalies=()):
    """Résume un relevé pour l'administrateur : affiches, puis état du bot."""
    if nouvelles:
        lignes = "\n".join(html.unescape(ligne_liste(f)) for f in nouvelles)
        texte = f"Relevé terminé : {len(nouvelles)} nouvelle(s) affiche(s).\n{lignes}"
    else:
        texte = "Relevé terminé : aucune nouvelle affiche."
        listes = [f for f in base["annonces"] if f["numeros"]]
        if listes:
            jour = jour_publication(listes[-1])
            quand = f" du {jour:%d/%m/%Y}" if jour else ""
            texte += f"\nDernière publication : {html.unescape(nom_court(listes[-1]))}{quand}."
    if anomalies:
        return texte + "\n\n⚠️ Bot en difficulté :\n" + "\n".join(f"• {a}" for a in anomalies)
    return texte + "\n\nBot opérationnel."
