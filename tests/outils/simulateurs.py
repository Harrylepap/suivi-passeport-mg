"""Partenaires simulés pour les tests : site de l'Ambassade, API Telegram, Worker local."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = RACINE / "tests" / "fixtures"
WINDOWS = sys.platform == "win32"
SECRETS = {
    "TELEGRAM_BOT_TOKEN": "jeton-de-test",
    "WEBHOOK_SECRET": "secret-webhook-de-test",
    "ADMIN_SECRET": "secret-admin-de-test",
    "CONTACT": "@contact_de_test",
}

# Affiches de référence, avec le titre que le site leur donne.
AFFICHES = {
    "BEG 2025-016": "form_affiche_20250516112903kLNXj.jpg",
    "BEG 2025-038": "form_affiche_20250922155521PWpga.jpeg",
    "BEG 2026-066": "form_affiche_20261124181658mTuCM.jpg",
}


def _demarrer(gestionnaire):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), gestionnaire)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur, f"http://127.0.0.1:{serveur.server_address[1]}"


def _corps(requete):
    longueur = int(requete.headers.get("Content-Length") or 0)
    brut = requete.rfile.read(longueur)
    type_ = requete.headers.get("Content-Type", "")
    if "application/json" in type_:
        return json.loads(brut)
    if "application/x-www-form-urlencoded" in type_:
        return dict(urllib.parse.parse_qsl(brut.decode("utf-8")))
    if "multipart/form-data" in type_:
        texte = brut.decode("latin-1")
        champs = {}
        motif = r'name="([^"]+)"(?:; filename="[^"]*")?\r\n(?:[^\r\n]+\r\n)*\r\n([\s\S]*?)\r\n--'
        for nom, valeur in re.findall(motif, texte):
            champs[nom] = "<fichier>" if nom == "photo" else valeur.encode("latin-1").decode("utf-8")
        return champs
    return {}


class SiteSimule:
    """Site de l'Ambassade : la liste des annonces en JSON, précédée de notices PHP, et les images."""

    def __init__(self):
        self.titres = []
        site = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                _corps(self)
                lignes = []
                for titre in reversed(site.titres):
                    image = f"{site.url}/uploads/{AFFICHES[titre]}"
                    lignes.append([f"<h5>Numéro: {titre}</h5>\r\n\t<div><img style='width:100%' src='{image}'/></div>"])
                corps = "<div><h4>A PHP Error was encountered</h4></div>" + json.dumps(
                    {"draw": "1", "recordsTotal": len(lignes), "recordsFiltered": len(lignes), "data": lignes}
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=UTF-8")
                self.end_headers()
                self.wfile.write(corps.encode("utf-8"))

            def do_GET(self):
                fichier = FIXTURES / urllib.parse.unquote(self.path.rsplit("/", 1)[-1])
                if not fichier.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(fichier.read_bytes())

        self.serveur, self.url = _demarrer(Gestionnaire)

    @property
    def adresse_annonces(self):
        return f"{self.url}/index.php/annonce/liste_quittance"

    def arreter(self):
        self.serveur.shutdown()


class TelegramSimule:
    """API Telegram : enregistre chaque appel et répond comme le vrai service."""

    def __init__(self):
        self.appels = []
        self.verrou = threading.Lock()
        telegram = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                methode = self.path.rsplit("/", 1)[-1]
                corps = _corps(self)
                with telegram.verrou:
                    numero = len(telegram.appels) + 1
                    appel = {"methode": methode, **corps}
                    if "chat_id" in corps:
                        appel["chat_id"] = str(corps["chat_id"])
                    telegram.appels.append(appel)
                resultat = {"message_id": numero}
                if methode == "sendPhoto":
                    resultat["photo"] = [{"file_id": f"photo-{numero}"}]
                if methode == "getUpdates":
                    resultat = []
                reponse = json.dumps({"ok": True, "result": resultat}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(reponse)

        self.serveur, self.url = _demarrer(Gestionnaire)

    def messages(self, chat):
        with self.verrou:
            return [a for a in self.appels if a.get("chat_id") == str(chat) and a["methode"].startswith("send")]

    def attendre(self, chat, nombre=1, delai=15):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            recus = self.messages(chat)
            if len(recus) >= nombre:
                return recus
            time.sleep(0.05)
        raise AssertionError(f"Conversation {chat} : {len(self.messages(chat))} message(s) reçu(s), {nombre} attendu(s)")

    def arreter(self):
        self.serveur.shutdown()


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WorkerLocal:
    """Worker Cloudflare démarré en local, avec une base vide et des secrets fictifs."""

    def __init__(self, telegram_url):
        self.persistance = tempfile.mkdtemp(prefix="passeport-bot-")
        fichier_env = Path(self.persistance) / "test.env"
        variables = {**SECRETS, "TELEGRAM_API": telegram_url}
        fichier_env.write_text("\n".join(f"{c}={v}" for c, v in variables.items()), encoding="utf-8")
        dossier = RACINE / "worker"
        env = {**os.environ, "CI": "1", "WRANGLER_SEND_METRICS": "false"}
        wrangler = [shutil.which("node") or "node", str(dossier / "node_modules" / "wrangler" / "bin" / "wrangler.js")]
        subprocess.run(
            [*wrangler, "d1", "migrations", "apply", "passeport-bot", "--local", "--persist-to", self.persistance],
            cwd=dossier, env=env, check=True, capture_output=True,
        )
        port = _port_libre()
        self.url = f"http://127.0.0.1:{port}"
        self.processus = subprocess.Popen(
            [*wrangler, "dev", "--local", "--ip", "127.0.0.1", "--port", str(port),
             "--persist-to", self.persistance, "--env-file", str(fichier_env)],
            cwd=dossier, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=not WINDOWS,
        )
        journal = []
        fin = time.monotonic() + 90
        for ligne in iter(self.processus.stdout.readline, b""):
            journal.append(ligne.decode("utf-8", "replace"))
            if "Ready on" in journal[-1]:
                break
            if time.monotonic() > fin:
                break
        else:
            raise RuntimeError("Le Worker s'est arrêté :\n" + "".join(journal))
        if not any("Ready on" in l for l in journal):
            raise RuntimeError("Le Worker n'a pas démarré :\n" + "".join(journal))
        threading.Thread(target=lambda: [None for _ in iter(self.processus.stdout.readline, b"")], daemon=True).start()

    def arreter(self):
        if WINDOWS:
            subprocess.run(["taskkill", "/pid", str(self.processus.pid), "/T", "/F"], capture_output=True)
        else:
            try:
                os.killpg(self.processus.pid, 15)
            except ProcessLookupError:
                pass
        time.sleep(0.5)
        shutil.rmtree(self.persistance, ignore_errors=True)
