"""Étapes des scénarios : on agit comme l'utilisateur, le site et le relevé, on observe Telegram."""
import json
import os
import subprocess
import sys
import urllib.request

from behave import given, then, when

from tests.outils.simulateurs import RACINE, SECRETS


def envoyer(context, texte):
    """Envoie un message au Worker, comme le fait Telegram."""
    mise_a_jour = {
        "update_id": context.chat,
        "message": {
            "message_id": 1,
            "chat": {"id": context.chat, "type": "private"},
            "from": {"id": context.chat, "first_name": "Rasoa"},
            "text": texte,
        },
    }
    requete = urllib.request.Request(
        f"{context.worker.url}/webhook",
        data=json.dumps(mise_a_jour).encode(),
        headers={"Content-Type": "application/json", "X-Telegram-Bot-Api-Secret-Token": SECRETS["WEBHOOK_SECRET"]},
    )
    urllib.request.urlopen(requete, timeout=30).read()


def nouveaux_messages(context, nombre=1):
    """Attend et renvoie les messages reçus depuis la dernière observation."""
    recus = context.telegram.attendre(context.chat, context.vus + nombre)
    nouveaux = recus[context.vus:]
    context.vus = len(recus)
    return nouveaux


def texte(message):
    return message.get("text") or message.get("caption") or ""


def lancer_releve(context):
    """Lance le vrai relevé, configuré vers le site, Telegram et le Worker simulés."""
    env = {
        **os.environ,
        "SITE_ANNONCES_URL": context.site.adresse_annonces,
        "TELEGRAM_API_URL": context.telegram.url,
        "WORKER_URL": context.worker.url,
        "ANNONCES_JSON": str(context.base),
        "TELEGRAM_BOT_TOKEN": SECRETS["TELEGRAM_BOT_TOKEN"],
        "ADMIN_SECRET": SECRETS["ADMIN_SECRET"],
        "PYTHONIOENCODING": "utf-8",
    }
    env.pop("TELEGRAM_CHAT_ID", None)
    resultat = subprocess.run([sys.executable, str(RACINE / "check.py")], env=env, capture_output=True, text=True, timeout=600)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr


@given('l\'Ambassade a publié les listes "{listes}"')
def ambassade_a_publie(context, listes):
    context.site.titres = [t.strip() for t in listes.split(",")]


@when('l\'Ambassade publie la liste "{liste}"')
def ambassade_publie(context, liste):
    context.site.titres.append(liste)


@given("le relevé est passé")
@when("le relevé passe")
def releve(context):
    lancer_releve(context)


@given('j\'ai envoyé "{message}" au bot')
def deja_envoye(context, message):
    envoyer(context, message)
    nouveaux_messages(context)


@when('j\'envoie "{message}" au bot')
def j_envoie(context, message):
    envoyer(context, message)


@then('le bot me répond que "{numero}" est publié dans la liste "{liste}"')
def reponse_publie(context, numero, liste):
    (reponse,) = nouveaux_messages(context)
    assert f"{numero} est publié" in texte(reponse), texte(reponse)
    assert liste in texte(reponse), texte(reponse)
    context.derniere = reponse


@then("la réponse contient l'affiche")
def contient_affiche(context):
    assert context.derniere["methode"] == "sendPhoto", context.derniere


@then('le bot me répond que "{numero}" n\'est pas encore publié')
def reponse_non_publie(context, numero):
    (reponse,) = nouveaux_messages(context)
    assert f"{numero} n'est pas encore publié" in texte(reponse), texte(reponse)
    context.derniere = reponse


@then("il me propose de me prévenir")
def propose_prevenir(context):
    assert "je vous préviens dès qu'il est publié" in texte(context.derniere), texte(context.derniere)


@then('je reçois l\'annonce "{titre}"')
def recoit_annonce(context, titre):
    context.recus = nouveaux_messages(context, 2)
    annonces = [m for m in context.recus if titre in texte(m)]
    assert annonces, [texte(m) for m in context.recus]
    context.annonce = annonces[0]


@then('l\'annonce rappelle la publication précédente du "{date}"')
def rappel_precedente(context, date):
    assert f"Publication précédente : le {date}" in texte(context.annonce), texte(context.annonce)


@then('je reçois l\'alerte "{alerte}"')
def recoit_alerte(context, alerte):
    alertes = [m for m in context.recus if alerte in texte(m)]
    assert alertes, [texte(m) for m in context.recus]
    assert alertes[0]["methode"] == "sendPhoto", alertes[0]


@then("je ne reçois ni annonce ni alerte")
def ne_recoit_rien(context):
    recus = context.telegram.messages(context.chat)[context.vus:]
    assert recus == [], [texte(m) for m in recus]
