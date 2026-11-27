"""Lecture du site de l'Ambassade et de la base locale des affiches."""
import html
import json
import re
import urllib.parse

from releve import config
from releve.reseau import http, worker


def fetch_annonces():
    """Renvoie les annonces en ligne, de la plus récente à la plus ancienne, en un seul appel."""
    body = urllib.parse.urlencode({"draw": 1, "start": 0, "length": 1000}).encode()
    raw = http(config.ENDPOINT, data=body).decode("utf-8", errors="replace")
    start = raw.find('{"draw"')
    if start < 0:
        raise RuntimeError("JSON introuvable dans la réponse : " + raw[:200])
    data = json.loads(raw[start:])
    annonces = []
    for row in data["data"]:
        cell = row[0]
        img = re.search(r"src='([^']+)'", cell)
        if not img:
            continue
        titre = re.search(r"<h5>(.*?)</h5>", cell, re.S)
        annonces.append({
            "titre": html.unescape(titre.group(1)).strip() if titre else "Annonce",
            "image": img.group(1),
        })
    if not annonces:
        raise RuntimeError("Aucune annonce lue, le format de la page a peut-être changé")
    return annonces


def lire_base():
    """Charge annonces.json, ou une base vide au premier lancement."""
    if config.BASE.exists():
        return json.loads(config.BASE.read_text(encoding="utf-8"))
    return {"annonces": []}


def ecrire_base(base):
    """Enregistre la base dans annonces.json, par remplacement atomique."""
    tmp = config.BASE.with_suffix(".tmp")
    tmp.write_text(json.dumps(base, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(config.BASE)


def publier_base(base):
    """Envoie la base au Worker, qui s'en sert pour répondre aux recherches."""
    rep = worker("PUT", "/admin/annonces", base)
    print(f"Base publiée : {rep['annonces']} annonces")
