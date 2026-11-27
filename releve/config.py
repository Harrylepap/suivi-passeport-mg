"""Réglages du relevé, surchargeables par variables d'environnement."""
import os
import re
from pathlib import Path

ENDPOINT = os.environ.get(
    "SITE_ANNONCES_URL",
    "https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce/liste_quittance",
)
PAGE = "https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce"
BASE = Path(os.environ.get("ANNONCES_JSON", Path(__file__).resolve().parents[1] / "annonces.json"))
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
