"""Tests d'intégration : le relevé avec ses dépendances réelles, Tesseract et le site simulé."""
import json
import shutil
import unittest

import check
from tests.outils.simulateurs import AFFICHES, FIXTURES, SiteSimule


@unittest.skipUnless(shutil.which("tesseract"), "tesseract absent")
class LectureDesAffichesIT(unittest.TestCase):
    """Lecture complète d'affiches de référence, contrôlées à l'œil."""

    def test_affiches_de_reference(self):
        attendus = json.loads((FIXTURES / "attendus.json").read_text(encoding="utf-8"))
        for nom, cas in attendus.items():
            with self.subTest(affiche=nom, cas=cas["cas"]):
                lus = check.lire_numeros((FIXTURES / nom).read_bytes())
                self.assertEqual(lus, cas["numeros"])


class ReleveDuSiteIT(unittest.TestCase):
    """Dialogue du relevé avec le site, simulé avec ses défauts réels."""

    @classmethod
    def setUpClass(cls):
        cls.site = SiteSimule()
        cls.ancienne_adresse = check.ENDPOINT
        check.ENDPOINT = cls.site.adresse_annonces

    @classmethod
    def tearDownClass(cls):
        check.ENDPOINT = cls.ancienne_adresse
        cls.site.arreter()

    def test_liste_lue_malgre_les_notices_php(self):
        self.site.titres = ["BEG 2025-038", "BEG 2026-066"]
        annonces = check.fetch_annonces()
        self.assertEqual([check.nom_court(a) for a in annonces], ["BEG 2026-066", "BEG 2025-038"])
        self.assertTrue(annonces[0]["image"].endswith(AFFICHES["BEG 2026-066"]))

    def test_site_vide_signale(self):
        self.site.titres = []
        with self.assertRaises(RuntimeError):
            check.fetch_annonces()


if __name__ == "__main__":
    unittest.main()
