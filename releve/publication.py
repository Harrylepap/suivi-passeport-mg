"""Règles de présentation des publications : titres, dates, regroupement et texte des annonces."""
import html
import re
from datetime import datetime


def nom_court(fiche):
    """Renvoie le titre nettoyé d'une affiche, par exemple « BEG 2026-066 »."""
    titre = re.sub(r"^Num\S*\s*:\s*", "", fiche["titre"]).strip()
    titre = re.sub(r"\s*([-/])\s*", r"\1", titre)
    titre = re.sub(r"\s+", " ", titre)
    titre = re.sub(r"^beg\b", "BEG", titre, flags=re.I)
    return html.escape(titre)


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
