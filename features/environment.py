"""Environnement des scénarios de bout en bout : partenaires simulés et Worker local."""
import itertools
import os
import shutil
import tempfile
from pathlib import Path

from tests.outils.simulateurs import SiteSimule, TelegramSimule, WorkerLocal

_conversations = itertools.count(900001)


def before_all(context):
    if not shutil.which("tesseract"):
        raise RuntimeError("Les scénarios de bout en bout exigent Tesseract")
    context.site = SiteSimule()
    context.telegram = TelegramSimule()
    context.worker = WorkerLocal(context.telegram.url)


def after_all(context):
    for partenaire in ("worker", "telegram", "site"):
        if hasattr(context, partenaire):
            getattr(context, partenaire).arreter()


def before_scenario(context, scenario):
    context.dossier = Path(tempfile.mkdtemp(prefix="releve-"))
    context.base = context.dossier / "annonces.json"
    context.chat = next(_conversations)
    context.vus = 0
    context.site.titres = []


def after_scenario(context, scenario):
    shutil.rmtree(context.dossier, ignore_errors=True)
