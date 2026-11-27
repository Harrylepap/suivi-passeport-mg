"""Tests d'intégration : le relevé avec ses dépendances réelles, Tesseract et le site simulé."""
import json
import shutil
import unittest

from releve import config, lecture, publication, site
from tests.outils.simulateurs import AFFICHES, FIXTURES, SiteSimule


@unittest.skipUnless(shutil.which("tesseract"), "tesseract absent")
class LectureDesAffichesIT(unittest.TestCase):
    """Lecture complète d'affiches de référence, contrôlées à l'œil."""

    def test_affiches_de_reference(self):
        attendus = json.loads((FIXTURES / "attendus.json").read_text(encoding="utf-8"))
        for nom, cas in attendus.items():
            with self.subTest(affiche=nom, cas=cas["cas"]):
                lus = lecture.lire_numeros((FIXTURES / nom).read_bytes())
                self.assertEqual(lus, cas["numeros"])


class ReleveDuSiteIT(unittest.TestCase):
    """Dialogue du relevé avec le site, simulé avec ses défauts réels."""

    @classmethod
    def setUpClass(cls):
        cls.site = SiteSimule()
        cls.ancienne_adresse = config.ENDPOINT
        config.ENDPOINT = cls.site.adresse_annonces

    @classmethod
    def tearDownClass(cls):
        config.ENDPOINT = cls.ancienne_adresse
        cls.site.arreter()

    def test_liste_lue_malgre_les_notices_php(self):
        self.site.titres = ["BEG 2025-038", "BEG 2026-066"]
        annonces = site.fetch_annonces()
        self.assertEqual([publication.nom_court(a) for a in annonces], ["BEG 2026-066", "BEG 2025-038"])
        self.assertTrue(annonces[0]["image"].endswith(AFFICHES["BEG 2026-066"]))

    def test_site_vide_signale(self):
        self.site.titres = []
        with self.assertRaises(RuntimeError):
            site.fetch_annonces()


if __name__ == "__main__":
    unittest.main()
