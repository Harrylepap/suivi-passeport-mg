"""Génère la bannière et les diagrammes de séquence animés du README dans assets/.

Usage : python outils/visuels.py
"""
import html
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[1] / "assets"

ROUGE, VERT, ENCRE, GRIS, FOND = "#FC3D32", "#007E3A", "#14181F", "#6B7280", "#FFFFFF"
POLICE = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace"


def banniere():
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="260" viewBox="0 0 1200 260" role="img" aria-label="Passeport Madagascar Paris">
  <rect width="1200" height="260" fill="{FOND}"/>
  <rect x="0.5" y="0.5" width="1199" height="259" fill="none" stroke="#E5E7EB"/>
  <rect x="1080" y="0" width="120" height="130" fill="{ROUGE}"/>
  <rect x="1080" y="130" width="120" height="130" fill="{VERT}"/>
  <g transform="translate(70 62)">
    <rect width="104" height="136" rx="10" fill="{VERT}"/>
    <rect x="8" y="8" width="88" height="120" rx="6" fill="none" stroke="#FFFFFF" stroke-opacity="0.35"/>
    <circle cx="52" cy="58" r="24" fill="none" stroke="#FFFFFF" stroke-width="3"/>
    <ellipse cx="52" cy="58" rx="10" ry="24" fill="none" stroke="#FFFFFF" stroke-width="2"/>
    <line x1="28" y1="58" x2="76" y2="58" stroke="#FFFFFF" stroke-width="2"/>
    <rect x="30" y="98" width="44" height="6" rx="3" fill="#FFFFFF"/>
    <rect x="38" y="110" width="28" height="4" rx="2" fill="#FFFFFF" fill-opacity="0.6"/>
  </g>
  <text x="214" y="124" font-family="{POLICE}" font-size="46" font-weight="700" fill="{ENCRE}">Passeport Madagascar Paris</text>
  <text x="214" y="166" font-family="{POLICE}" font-size="22" fill="{GRIS}">Suivi des passeports à retirer, en un message Telegram</text>
</svg>
"""
    (SORTIE / "banniere.svg").write_text(svg, encoding="utf-8")


def sequence(nom, titre, acteurs, messages):
    """acteurs : libellés ; messages : (de, vers, texte, style) avec style dans requete|reponse|interne."""
    marge, pas = 150, 200
    largeur = marge * 2 + pas * (len(acteurs) - 1)
    haut_entete, pas_msg = 118, 58
    hauteur = haut_entete + pas_msg * len(messages) + 50
    xs = [marge + i * pas for i in range(len(acteurs))]
    n = len(messages)
    duree = n * 1.0 + 4.0
    css = [
        f".msg{{opacity:0;animation-duration:{duree:.1f}s;animation-iteration-count:infinite;animation-timing-function:ease-out}}",
    ]
    for i in range(n):
        debut = (0.6 + i * 1.0) / duree * 100
        plein = debut + 0.25 / duree * 100
        fin = (duree - 0.8) / duree * 100
        css.append(
            f"@keyframes a{i}{{0%,{debut:.2f}%{{opacity:0;transform:translateY(6px)}}"
            f"{plein:.2f}%,{fin:.2f}%{{opacity:1;transform:translateY(0)}}100%{{opacity:0;transform:translateY(0)}}}}"
            f".m{i}{{animation-name:a{i}}}"
        )
    corps = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}" role="img" aria-label="{html.escape(titre)}">',
        f"<style>{''.join(css)}</style>",
        "<defs>",
        f'<marker id="pr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{ROUGE}"/></marker>',
        f'<marker id="pv" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{VERT}"/></marker>',
        f'<marker id="pg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{GRIS}"/></marker>',
        "</defs>",
        f'<rect width="{largeur}" height="{hauteur}" rx="12" fill="{FOND}" stroke="#E5E7EB"/>',
        f'<rect x="0" y="0" width="6" height="{hauteur}" fill="{ROUGE}"/>',
        f'<rect x="0" y="{hauteur / 2}" width="6" height="{hauteur / 2}" fill="{VERT}"/>',
        f'<text x="{marge - 60}" y="40" font-family="{POLICE}" font-size="20" font-weight="700" fill="{ENCRE}">{html.escape(titre)}</text>',
    ]
    for x, acteur in zip(xs, acteurs):
        corps += [
            f'<line x1="{x}" y1="{haut_entete - 26}" x2="{x}" y2="{hauteur - 26}" stroke="#D1D5DB" stroke-dasharray="4 5"/>',
            f'<rect x="{x - 80}" y="58" width="160" height="36" rx="8" fill="{ENCRE}"/>',
            f'<text x="{x}" y="81" text-anchor="middle" font-family="{POLICE}" font-size="14" font-weight="600" fill="#FFFFFF">{html.escape(acteur)}</text>',
        ]
    couleurs = {"requete": (ROUGE, "pr", ""), "reponse": (VERT, "pv", ' stroke-dasharray="7 5"'), "interne": (GRIS, "pg", "")}
    for i, (de, vers, texte, style) in enumerate(messages):
        y = haut_entete + 14 + i * pas_msg
        couleur, marqueur, tirets = couleurs[style]
        x1, x2 = xs[de], xs[vers]
        corps.append(f'<g class="msg m{i}">')
        corps.append(f'<circle cx="{marge - 62}" cy="{y + 18}" r="11" fill="{couleur}"/>')
        corps.append(f'<text x="{marge - 62}" y="{y + 22}" text-anchor="middle" font-family="{POLICE}" font-size="12" font-weight="700" fill="#FFFFFF">{i + 1}</text>')
        if de == vers:
            corps.append(f'<path d="M{x1} {y + 8} h46 v22 h-44" fill="none" stroke="{couleur}" stroke-width="2.2" marker-end="url(#{marqueur})"/>')
            corps.append(f'<text x="{x1 + 54}" y="{y + 24}" font-family="{POLICE}" font-size="13.5" fill="{ENCRE}">{html.escape(texte)}</text>')
        else:
            sens = 1 if x2 > x1 else -1
            corps.append(f'<line x1="{x1 + 3 * sens}" y1="{y + 22}" x2="{x2 - 4 * sens}" y2="{y + 22}" stroke="{couleur}" stroke-width="2.2"{tirets} marker-end="url(#{marqueur})"/>')
            corps.append(f'<text x="{(x1 + x2) / 2}" y="{y + 13}" text-anchor="middle" font-family="{POLICE}" font-size="13.5" fill="{ENCRE}">{html.escape(texte)}</text>')
        corps.append("</g>")
    corps.append("</svg>")
    (SORTIE / f"{nom}.svg").write_text("\n".join(corps), encoding="utf-8")


banniere()
sequence(
    "sequence-recherche",
    "Recherche d'un numéro de quittance",
    ["Utilisateur", "Telegram", "Worker", "KV", "D1"],
    [
        (0, 1, "2026-61191", "requete"),
        (1, 2, "webhook signé par secret", "requete"),
        (2, 1, "200 OK immédiat", "reponse"),
        (2, 3, "abonné et base des numéros", "requete"),
        (3, 2, "publié dans BEG 2026-066", "reponse"),
        (2, 4, "journaliser la recherche", "interne"),
        (2, 1, "sendPhoto, file_id en cache", "requete"),
        (1, 0, "2026-61191 est publié + affiche", "reponse"),
    ],
)
sequence(
    "sequence-releve",
    "Relevé de 11 h et 19 h",
    ["GitHub Actions", "Site Ambassade", "Tesseract", "Worker", "Telegram"],
    [
        (0, 1, "1 requête : liste des annonces", "requete"),
        (1, 0, "affiches en ligne (JSON)", "reponse"),
        (0, 0, "comparer à annonces.json", "interne"),
        (0, 1, "télécharger la nouvelle affiche", "requete"),
        (0, 2, "6 lectures prétraitées", "requete"),
        (2, 0, "vote : 25 numéros", "reponse"),
        (0, 3, "publier la base", "requete"),
        (0, 4, "annonce aux abonnés", "requete"),
        (0, 4, "alerte aux numéros suivis", "requete"),
    ],
)
print("Visuels écrits dans assets/")
