"""Lance les quatre niveaux de tests et en fait des captures de terminal SVG dans assets/.

Exige Tesseract et les dépendances de test. Sur un poste sans Tesseract, lancer dans un conteneur Linux.
Usage : python outils/captures.py
"""
import html
import os
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ASSETS = RACINE / "assets"
MONO = "'JetBrains Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace"
FOND, TEXTE, OK, GRIS, ROUGE, VERT, TITRE = "#0D1117", "#E6EDF3", "#3FB950", "#8B949E", "#FC3D32", "#007E3A", "#79C0FF"


def executer(commande, dossier=RACINE):
    """Lance une commande de test et renvoie sa sortie ; s'arrête si elle échoue."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(RACINE)}
    resultat = subprocess.run(commande, cwd=dossier, env=env, capture_output=True, text=True, encoding="utf-8")
    sortie = resultat.stdout + resultat.stderr
    if resultat.returncode != 0:
        sys.exit(f"Échec de {' '.join(commande)} :\n{sortie}")
    return sortie


def terminal(nom, titre, blocs):
    """Dessine une fenêtre de terminal ; blocs = (commande, [(texte, couleur, retrait)])."""
    pas, largeur = 22, 980
    hauteur = 52 + pas * sum(len(lignes) + 2 for _, lignes in blocs) + 16
    corps = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}" role="img" aria-label="{html.escape(titre)}">',
        f'<rect width="{largeur}" height="{hauteur}" rx="12" fill="{FOND}"/>',
        f'<rect x="0" y="0" width="{largeur / 2}" height="4" fill="{ROUGE}"/><rect x="{largeur / 2}" y="0" width="{largeur / 2}" height="4" fill="{VERT}"/>',
        '<circle cx="24" cy="26" r="6" fill="#FF5F57"/><circle cx="44" cy="26" r="6" fill="#FEBC2E"/><circle cx="64" cy="26" r="6" fill="#28C840"/>',
        f'<text x="{largeur / 2}" y="31" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{GRIS}">{html.escape(titre)}</text>',
    ]
    y = 52
    for commande, lignes in blocs:
        y += pas
        corps.append(f'<text x="24" y="{y}" font-family="{MONO}" font-size="14" fill="{GRIS}">$ <tspan fill="{TEXTE}">{html.escape(commande)}</tspan></text>')
        for texte, couleur, retrait in lignes:
            y += pas
            corps.append(f'<text x="{24 + 18 * retrait}" y="{y}" font-family="{MONO}" font-size="14" fill="{couleur}" xml:space="preserve">{html.escape(texte)}</text>')
        y += pas
    corps.append("</svg>")
    (ASSETS / f"{nom}.svg").write_text("\n".join(corps) + "\n", encoding="utf-8")


def lignes_python(sortie):
    """Met en forme la sortie verbeuse de unittest, regroupée par classe de test."""
    lignes, classe = [], None
    for brut in sortie.splitlines():
        m = re.match(r"(test_\w+) \(tests\.\w+\.\w+\.(\w+)\.\w+\) \.\.\. (\w+)", brut)
        if m:
            test, nom_classe, etat = m.groups()
            if nom_classe != classe:
                lignes.append((nom_classe, TITRE, 0))
                classe = nom_classe
            lignes.append((f"{'✔' if etat == 'ok' else '✘'} {test}", OK if etat == "ok" else ROUGE, 1))
        elif brut.startswith("Ran "):
            lignes.append((re.sub(r" in [\d.]+s", "", brut) + " · OK", OK, 0))
    return lignes


def lignes_node(sortie):
    """Met en forme la sortie du lanceur de tests de Node, regroupée par suite."""
    lignes = []
    for brut in sortie.splitlines():
        if brut.startswith("▶ "):
            lignes.append((brut[2:], TITRE, 0))
        elif brut.startswith("  ✔ "):
            lignes.append((re.sub(r" \([\d.]+ms\)$", "", brut.strip()), OK, 1))
    reussis = re.search(r"ℹ pass (\d+)", sortie).group(1)
    echecs = re.search(r"ℹ fail (\d+)", sortie).group(1)
    lignes.append((f"{reussis} réussis · {echecs} échec", OK, 0))
    return lignes


def lignes_behave(sortie):
    """Met en forme la sortie de behave : fonctionnalités, scénarios et bilan."""
    lignes, fonctionnalite = [], None
    for brut in sortie.splitlines():
        m = re.match(r"Fonctionnalité: (.+?)\s+#", brut)
        if m and m.group(1) != fonctionnalite:
            fonctionnalite = m.group(1)
            lignes.append((fonctionnalite, TITRE, 0))
        m = re.match(r"\s+Scénario: (.+?)\s+#", brut)
        if m:
            lignes.append((f"✔ {m.group(1)}", OK, 1))
    for brut in sortie.splitlines():
        if re.match(r"\d+ (features|scenarios|steps) passed", brut):
            lignes.append((brut.replace(", 0 skipped", ""), OK if "steps" in brut else GRIS, 0))
    return lignes


def main():
    py_unitaires = executer([sys.executable, "-m", "unittest", "discover", "-s", "tests/unitaires", "-t", ".", "-v"])
    py_integration = executer([sys.executable, "-m", "unittest", "discover", "-s", "tests/integration", "-p", "test_*_it.py", "-t", ".", "-v"])
    npm = "npm.cmd" if os.name == "nt" else "npm"
    worker = {n: executer([npm, "run", "-s", f"test:{n}"], RACINE / "worker") for n in ("unitaire", "integration", "api")}
    behave = executer([sys.executable, "-m", "behave", "--no-color"])

    terminal("tests-unitaires", "Unitaires · règles de gestion, sans réseau ni base", [
        ("python -m unittest discover -s tests/unitaires", lignes_python(py_unitaires)),
        ("npm run test:unitaire", lignes_node(worker["unitaire"])),
    ])
    terminal("tests-integration", "Intégration · Tesseract, site simulé, base D1 locale", [
        ("python -m unittest discover -s tests/integration", lignes_python(py_integration)),
        ("npm run test:integration", lignes_node(worker["integration"])),
    ])
    terminal("tests-api", "API · Worker démarré, appelé comme Telegram et le relevé", [
        ("npm run test:api", lignes_node(worker["api"])),
    ])
    terminal("tests-bout-en-bout", "Bout en bout · scénarios Gherkin, relevé et Worker réels", [
        ("python -m behave", lignes_behave(behave)),
    ])
    print("Captures écrites dans assets/")


if __name__ == "__main__":
    main()
