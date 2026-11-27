"""Échanges réseau : HTTP, API Telegram, routes d'administration du Worker."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from releve import config


class ErreurHttp(Exception):
    """Réponse HTTP en erreur, avec son code."""

    def __init__(self, code, detail):
        super().__init__(f"HTTP {code} : {detail[:200]}")
        self.code = code


def http(url, data=None, headers=None, timeout=config.TIMEOUT, method=None):
    """Exécute une requête HTTP et renvoie le corps de la réponse."""
    req = urllib.request.Request(url, data=data, headers={**config.UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise ErreurHttp(exc.code, exc.read().decode("utf-8", errors="replace")) from None


def telegram(method, fields, file=None, files=None):
    """Appelle l'API Telegram, avec des fichiers joints si « file » ou « files » est fourni."""
    url = f"{config.TELEGRAM_API}/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"
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


def alerter_admin(texte, silencieux=False):
    """Envoie un message à l'administrateur, sans sonnerie si « silencieux », sans interrompre le relevé."""
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat:
        return
    champs = {"chat_id": chat, "text": texte, "disable_web_page_preview": "true"}
    if silencieux:
        champs["disable_notification"] = "true"
    try:
        telegram("sendMessage", champs)
    except Exception as exc:
        print(f"Alerte non envoyée ({exc})", file=sys.stderr)


def journaliser(evenements):
    """Transmet des événements au Worker pour les statistiques, sans interrompre le relevé."""
    try:
        worker("POST", "/admin/evenements", {"evenements": evenements})
    except Exception as exc:
        print(f"Statistiques non transmises ({exc})", file=sys.stderr)
