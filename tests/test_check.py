import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check

FIXTURES = Path(__file__).parent / "fixtures"


class NomCourt(unittest.TestCase):
    """Nettoyage des titres d'affiches."""

    def test_titres(self):
        cas = {
            "Numéro: BEG 2026- 066": "BEG 2026-066",
            "Numéro: beg 2026 - 023": "BEG 2026-023",
            "Numéro: BEG-2024-060": "BEG-2024-060",
            "Numéro: BEG 2026- 034/ 054": "BEG 2026-034/054",
            "Numéro: AVIS <AUX> USAGERS": "AVIS &lt;AUX&gt; USAGERS",
        }
        for titre, attendu in cas.items():
            self.assertEqual(check.nom_court({"titre": titre}), attendu)


class NumerosDeQuittance(unittest.TestCase):
    """Reconnaissance des numéros dans un texte."""

    def extraire(self, texte):
        return [f"{a}-{n}" for a, n in check.RE_QUITTANCE.findall(texte)]

    def test_formats_acceptes(self):
        self.assertEqual(self.extraire("1 2026-61191 16 2026–61330"), ["2026-61191", "2026-61330"])
        self.assertEqual(self.extraire("2025 - 5052"), ["2025-5052"])

    def test_numero_d_annonce_ignore(self):
        self.assertEqual(self.extraire("BEG N° 2026– 066"), [])

    def test_telephone_ignore(self):
        self.assertEqual(self.extraire("Contact : +33 6 83 78 94 97"), [])


class DatesDePublication(unittest.TestCase):
    """Dates lues dans le nom des fichiers et choix de la publication précédente."""

    def fiche(self, horodatage):
        return {"titre": "Numéro: BEG", "image": f"https://x/uploads/form_affiche_{horodatage}abcde.jpg"}

    def fiche_nommee(self, numero, horodatage, nb=25):
        return {
            "titre": f"Numéro: BEG 2026- {numero}",
            "image": f"https://x/uploads/form_affiche_{horodatage}abcde.jpg",
            "numeros": [f"2026-{i}" for i in range(nb)],
        }

    def test_jour_lu_dans_le_nom_du_fichier(self):
        self.assertEqual(str(check.jour_publication(self.fiche("20261124181658"))), "2026-11-24")
        self.assertIsNone(check.jour_publication({"titre": "x", "image": "https://x/autre.jpg"}))

    def test_regroupement_par_jour(self):
        a = self.fiche_nommee("064", "20261124181501")
        b = self.fiche_nommee("065", "20261124181601")
        c = self.fiche_nommee("067", "20261126101000")
        groupes = check.grouper_par_jour([(a, None), (b, None), (c, None)])
        self.assertEqual([len(g) for _, g in groupes], [2, 1])

    def test_precedente_est_tout_le_jour_anterieur(self):
        a062 = self.fiche_nommee("062", "20261119165000")
        a063 = self.fiche_nommee("063", "20261119170142")
        a064 = self.fiche_nommee("064", "20261124181501")
        a066 = self.fiche_nommee("066", "20261124181658")
        jour = check.jour_publication(a066)
        self.assertEqual(check.publication_precedente([a062, a063, a064, a066], jour), [a062, a063])
        self.assertEqual(check.publication_precedente([a064, a066], jour), [])

    def test_message_groupe(self):
        nouvelles = [self.fiche_nommee("064", "20261124181501", 24), self.fiche_nommee("066", "20261124181658")]
        precedentes = [self.fiche_nommee("062", "20261119165000"), self.fiche_nommee("063", "20261119170142")]
        texte = check.legende_publication(check.jour_publication(nouvelles[0]), nouvelles, precedentes)
        self.assertIn("<b>2 nouvelles listes publiées le 24/11/2026</b>", texte)
        self.assertIn("• BEG 2026-064 · 24 numéros", texte)
        self.assertIn("Publication précédente : le 19/11/2026\n• BEG 2026-062 · 25 numéros\n• BEG 2026-063", texte)


@unittest.skipUnless(shutil.which("tesseract"), "tesseract absent")
class LectureDesAffiches(unittest.TestCase):
    """Lecture complète d'affiches de référence, contrôlées à l'œil."""

    def test_affiches_de_reference(self):
        attendus = json.loads((FIXTURES / "attendus.json").read_text(encoding="utf-8"))
        for nom, cas in attendus.items():
            with self.subTest(affiche=nom, cas=cas["cas"]):
                lus = check.lire_numeros((FIXTURES / nom).read_bytes())
                self.assertEqual(lus, cas["numeros"])


if __name__ == "__main__":
    unittest.main()
