"""Relevé des listes de passeports à retirer et diffusion aux abonnés."""
import collections
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ENDPOINT = os.environ.get(
    "SITE_ANNONCES_URL",
    "https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce/liste_quittance",
)
PAGE = "https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce"
BASE = Path(os.environ.get("ANNONCES_JSON", Path(__file__).parent / "annonces.json"))
TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 60

RE_QUITTANCE = re.compile(r"(?<!\d)(20\d{2})\s*[-‐-―.]?\s*(\d{4,6})(?!\d)")

OCR_LECTURES = ((1800, 6), (1800, 11), (2400, 6), (2400, 11), (3200, 6), (3200, 11))
OCR_VOTES_MIN = 2
OCR_SEUIL = 160
NUMEROS_ATTENDUS = (10, 30)

PRUDENCE = "<i>Lecture automatique : vérifiez toujours votre numéro sur l'image avant de vous déplacer.</i>"
COMMANDES = [
    ("start", "Présentation du service"),
    ("derniere", "Revoir la dernière liste publiée"),
    ("suivis", "Voir mes numéros suivis"),
    ("aide", "Comment utiliser le bot"),
    ("confidentialite", "Vos données et vos droits"),
    ("stop", "Ne plus recevoir de messages"),
]


class ErreurHttp(Exception):
    """Réponse HTTP en erreur, avec son code."""

    def __init__(self, code, detail):
        super().__init__(f"HTTP {code} : {detail[:200]}")
        self.code = code


def http(url, data=None, headers=None, timeout=TIMEOUT, method=None):
    """Exécute une requête HTTP et renvoie le corps de la réponse."""
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise ErreurHttp(exc.code, exc.read().decode("utf-8", errors="replace")) from None


def ecrire_base(base):
    """Enregistre la base dans annonces.json, par remplacement atomique."""
    tmp = BASE.with_suffix(".tmp")
    tmp.write_text(json.dumps(base, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(BASE)


def nom_court(fiche):
    """Renvoie le titre nettoyé d'une affiche, par exemple « BEG 2026-066 »."""
    titre = re.sub(r"^Num\S*\s*:\s*", "", fiche["titre"]).strip()
    titre = re.sub(r"\s*([-/])\s*", r"\1", titre)
    titre = re.sub(r"\s+", " ", titre)
    titre = re.sub(r"^beg\b", "BEG", titre, flags=re.I)
    return html.escape(titre)


def fetch_annonces():
    """Renvoie les annonces en ligne, de la plus récente à la plus ancienne, en un seul appel."""
    body = urllib.parse.urlencode({"draw": 1, "start": 0, "length": 1000}).encode()
    raw = http(ENDPOINT, data=body).decode("utf-8", errors="replace")
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


def _suites(sombre, k, axe):
    """Repère les pixels appartenant à une suite d'au moins k pixels sombres le long d'un axe."""
    import numpy as np

    m = np.moveaxis(sombre, axe, 0).astype(np.int32)
    n = m.shape[0]
    cumul = np.concatenate([np.zeros((1,) + m.shape[1:], np.int32), np.cumsum(m, 0)])
    pleine = (cumul[k:] - cumul[:-k]) == k
    delta = np.zeros((n + 1,) + m.shape[1:], np.int32)
    delta[: n - k + 1] += pleine
    delta[k:] -= pleine
    return np.moveaxis(np.cumsum(delta, 0)[:n] > 0, 0, axe)


def preparer(image, largeur):
    """Agrandit l'affiche, la passe en noir et blanc et efface le cadre et les traits du tableau."""
    import numpy as np
    from PIL import Image

    rgb = image.convert("RGB")
    rgb = rgb.resize((largeur, round(rgb.height * largeur / rgb.width)), Image.LANCZOS)
    sombre = np.asarray(rgb).max(axis=2) < OCR_SEUIL
    k = largeur // 30
    sombre &= ~(_suites(sombre, k, 1) | _suites(sombre, k, 0))
    return Image.fromarray(np.where(sombre, 0, 255).astype(np.uint8))


def lire_numeros(contenu):
    """Lit les numéros de quittance d'une affiche et garde ceux que plusieurs lectures confirment."""
    from PIL import Image

    image = Image.open(io.BytesIO(contenu))
    votes = collections.Counter()
    preparees = {}
    with tempfile.TemporaryDirectory() as tmp:
        for largeur, psm in OCR_LECTURES:
            if largeur not in preparees:
                preparees[largeur] = os.path.join(tmp, f"{largeur}.png")
                preparer(image, largeur).save(preparees[largeur])
            texte = subprocess.run(
                ["tesseract", preparees[largeur], "stdout", "--psm", str(psm)],
                capture_output=True, check=True, timeout=180,
            ).stdout.decode("utf-8", errors="replace")
            votes.update({f"{a}-{n}" for a, n in RE_QUITTANCE.findall(texte)})
    return sorted(n for n, v in votes.items() if v >= OCR_VOTES_MIN)


def indexer(annonce):
    """Télécharge une affiche, en lit les numéros et renvoie la fiche avec le contenu de l'image."""
    fiche = {"titre": annonce["titre"], "image": annonce["image"], "numeros": None}
    if annonce.get("file_id"):
        fiche["file_id"] = annonce["file_id"]
    contenu = None
    try:
        contenu = http(annonce["image"])
        fiche["numeros"] = lire_numeros(contenu)
    except Exception as exc:
        print(f"Lecture impossible pour {annonce['titre']} ({exc})", file=sys.stderr)
    return fiche, contenu


def worker(methode, chemin, contenu=None):
    """Appelle une route d'administration du Worker et renvoie sa réponse JSON."""
    data = None if contenu is None else json.dumps(contenu, ensure_ascii=False).encode("utf-8")
    rep = http(
        os.environ["WORKER_URL"].rstrip("/") + chemin,
        data=data,
        headers={"Authorization": "Bearer " + os.environ["ADMIN_SECRET"], "Content-Type": "application/json"},
        method=methode,
    )
    return json.loads(rep)


def publier_base(base):
    """Envoie la base au Worker, qui s'en sert pour répondre aux recherches."""
    rep = worker("PUT", "/admin/annonces", base)
    print(f"Base publiée : {rep['annonces']} annonces")


def alerter_admin(texte):
    """Envoie un message à l'administrateur, sans interrompre le relevé."""
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat:
        return
    try:
        telegram("sendMessage", {"chat_id": chat, "text": texte, "disable_web_page_preview": "true"})
    except Exception as exc:
        print(f"Alerte non envoyée ({exc})", file=sys.stderr)


def controler_lecture(fiche):
    """Prévient l'administrateur si le nombre de numéros lus sur une affiche paraît anormal."""
    nb = len(fiche["numeros"] or [])
    bas, haut = NUMEROS_ATTENDUS
    if fiche["numeros"] is None:
        motif = "la lecture a échoué"
    elif nb == 0:
        motif = "aucun numéro lu"
    elif nb < bas or nb > haut:
        motif = f"{nb} numéros lus, nombre inhabituel"
    else:
        return
    alerter_admin(
        f"Lecture à vérifier : {html.unescape(nom_court(fiche))}, {motif}.\n{fiche['image']}"
    )


def purger():
    """Demande au Worker d'effacer les personnes inactives depuis la durée de conservation."""
    try:
        rep = worker("POST", "/admin/purge", {})
        if rep["purges"]:
            print(f"Personnes inactives effacées : {rep['purges']}")
    except Exception as exc:
        print(f"Purge impossible ({exc})", file=sys.stderr)


def journaliser(evenements):
    """Transmet des événements au Worker pour les statistiques, sans interrompre le relevé."""
    try:
        worker("POST", "/admin/evenements", {"evenements": evenements})
    except Exception as exc:
        print(f"Statistiques non transmises ({exc})", file=sys.stderr)


def telegram(method, fields, file=None, files=None):
    """Appelle l'API Telegram, avec des fichiers joints si « file » ou « files » est fourni."""
    url = f"{TELEGRAM_API}/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"
    joints = files or ([file] if file else [])
    headers = None
    if not joints:
        data = urllib.parse.urlencode(fields).encode()
    else:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            )
        for field, filename, content in joints:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    return json.loads(http(url, data=data, headers=headers))


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
    """Exécute un envoi vers un abonné et le désabonne s'il a bloqué le bot."""
    try:
        envoi()
    except ErreurHttp as exc:
        if exc.code == 403:
            worker("DELETE", f"/admin/abonnes/{chat}")
            print("Un abonné retiré (bot bloqué)")
        else:
            print(f"Envoi impossible ({exc})", file=sys.stderr)
    except Exception as exc:
        print(f"Envoi impossible ({exc})", file=sys.stderr)
    time.sleep(0.05)


def instant_publication(fiche):
    """Renvoie l'instant de mise en ligne d'une affiche, lu dans le nom de son fichier, ou None."""
    m = re.search(r"form_affiche_(\d{14})", fiche["image"])
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def jour_publication(fiche):
    """Renvoie le jour de mise en ligne d'une affiche, ou None."""
    instant = instant_publication(fiche)
    return instant.date() if instant else None


def ligne_liste(fiche):
    """Renvoie la ligne d'une affiche dans un message : son titre et son nombre de numéros."""
    if fiche["numeros"]:
        return f"• {nom_court(fiche)} · {len(fiche['numeros'])} numéros"
    return f"• {nom_court(fiche)}"


def grouper_par_jour(elements):
    """Regroupe des couples (fiche, contenu) par jour de mise en ligne, dans l'ordre d'arrivée."""
    groupes = []
    for fiche, contenu in elements:
        jour = jour_publication(fiche)
        if jour and groupes and groupes[-1][0] == jour:
            groupes[-1][1].append((fiche, contenu))
        else:
            groupes.append((jour, [(fiche, contenu)]))
    return groupes


def publication_precedente(annonces, jour):
    """Renvoie les affiches du dernier jour de publication antérieur à « jour »."""
    if not jour:
        return []
    jours = {jour_publication(f) for f in annonces} - {None}
    avant = [j for j in jours if j < jour]
    if not avant:
        return []
    dernier = max(avant)
    return [f for f in annonces if jour_publication(f) == dernier]


def legende_publication(jour, fiches, precedentes):
    """Compose le message d'une publication : listes du jour et rappel de la publication précédente."""
    nb = len(fiches)
    toutes_listes = all(f["numeros"] for f in fiches)
    if jour:
        date = f"le {jour:%d/%m/%Y}"
        if nb == 1:
            titre = f"Nouvelle {'liste publiée' if toutes_listes else 'publication'} {date}"
        else:
            titre = f"{nb} nouvelles {'listes publiées' if toutes_listes else 'publications'} {date}"
    else:
        titre = "Nouvelle publication de l'Ambassade"
    lignes = [f"<b>{titre}</b>", *[ligne_liste(f) for f in fiches]]
    if precedentes:
        lignes += ["", f"Publication précédente : le {jour_publication(precedentes[0]):%d/%m/%Y}"]
        lignes += [ligne_liste(f) for f in precedentes]
    lignes += ["", "Envoyez votre numéro de quittance pour savoir s'il en fait partie."]
    return "\n".join(lignes)


def diffuser(jour, elements, abonnes, precedentes):
    """Annonce les affiches d'un même jour à tous les abonnés, puis prévient ceux qui suivaient un numéro."""
    texte = legende_publication(jour, [f for f, _ in elements], precedentes)
    champs = {
        "text": texte,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "Voir les listes officielles", "url": PAGE}]]}),
    }
    for abonne in abonnes:
        vers_abonne(abonne["chat"], lambda: telegram("sendMessage", {"chat_id": abonne["chat"], **champs}))
    for fiche, contenu in elements:
        alerter_suivis(fiche, contenu, abonnes)
    journaliser([{"type": "diffusion", "liste": nom_court(f), "valeur": len(abonnes)} for f, _ in elements])
    print(f"Diffusion de {len(elements)} affiches à {len(abonnes)} abonnés")


def alerter_suivis(fiche, contenu, abonnes):
    """Prévient les abonnés dont un numéro suivi figure dans l'affiche."""
    numeros = set(fiche["numeros"] or [])
    evenements = []
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
            f"{PRUDENCE}"
        )
        vers_abonne(abonne["chat"], lambda: envoyer_affiche(abonne["chat"], fiche, legende, contenu))
    if evenements:
        journaliser(evenements)


def relever(dry=False):
    """Détecte les nouvelles affiches, les indexe, publie la base et les diffuse."""
    base = json.loads(BASE.read_text(encoding="utf-8")) if BASE.exists() else {"annonces": []}
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
    alerter_admin(bilan_releve(base, [f for f, _ in elements], verifier_service()))


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


def configurer_bot():
    """Branche Telegram sur le Worker et définit le menu et la présentation du bot."""
    rep = telegram("setWebhook", {
        "url": os.environ["WORKER_URL"].rstrip("/") + "/webhook",
        "secret_token": os.environ["WEBHOOK_SECRET"],
        "allowed_updates": '["message","callback_query"]',
    })
    print("Webhook :", rep.get("description"))
    commandes = [{"command": c, "description": d} for c, d in COMMANDES]
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
        return publier_base(json.loads(BASE.read_text(encoding="utf-8")))
    relever(dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
