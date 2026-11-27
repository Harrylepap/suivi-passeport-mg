"""Lecture des numéros de quittance sur les affiches : prétraitement, OCR et vote."""
import collections
import io
import os
import subprocess
import sys
import tempfile

from releve import config
from releve.reseau import http


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
    sombre = np.asarray(rgb).max(axis=2) < config.OCR_SEUIL
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
        for largeur, psm in config.OCR_LECTURES:
            if largeur not in preparees:
                preparees[largeur] = os.path.join(tmp, f"{largeur}.png")
                preparer(image, largeur).save(preparees[largeur])
            texte = subprocess.run(
                ["tesseract", preparees[largeur], "stdout", "--psm", str(psm)],
                capture_output=True, check=True, timeout=180,
            ).stdout.decode("utf-8", errors="replace")
            votes.update({f"{a}-{n}" for a, n in config.RE_QUITTANCE.findall(texte)})
    return sorted(n for n, v in votes.items() if v >= config.OCR_VOTES_MIN)


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
