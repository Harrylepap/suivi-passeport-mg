"""Tests unitaires : règles de gestion du relevé, sans réseau ni fichier."""
import unittest

import check


def fiche(numero, horodatage, nb=25):
    return {
        "titre": f"Numéro: BEG 2026- {numero}",
        "image": f"https://x/uploads/form_affiche_{horodatage}abcde.jpg",
        "numeros": [f"2026-{i}" for i in range(nb)],
    }


class NomCourtTest(unittest.TestCase):
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
            with self.subTest(titre=titre):
                self.assertEqual(check.nom_court({"titre": titre}), attendu)


class NumerosDeQuittanceTest(unittest.TestCase):
    """Reconnaissance des numéros dans le texte lu sur une affiche."""

    def extraire(self, texte):
        return [f"{a}-{n}" for a, n in check.RE_QUITTANCE.findall(texte)]

    def test_formats_acceptes(self):
        self.assertEqual(self.extraire("1 2026-61191 16 2026–61330"), ["2026-61191", "2026-61330"])
        self.assertEqual(self.extraire("2025 - 5052"), ["2025-5052"])

    def test_numero_d_annonce_ignore(self):
        self.assertEqual(self.extraire("BEG N° 2026– 066"), [])

    def test_telephone_ignore(self):
        self.assertEqual(self.extraire("Contact : +33 6 83 78 94 97"), [])


class ControleDeLectureTest(unittest.TestCase):
    """Alerte de l'administrateur quand une lecture paraît anormale."""

    def test_seuils(self):
        envoyees = []
        original = check.alerter_admin
        check.alerter_admin = envoyees.append
        try:
            for nb in (None, 0, 5, 20, 40):
                numeros = None if nb is None else [f"2026-{i}" for i in range(nb)]
                check.controler_lecture({"titre": "Numéro: BEG 2026- 067", "image": "https://x/a.jpg", "numeros": numeros})
        finally:
            check.alerter_admin = original
        self.assertEqual(len(envoyees), 4)
        self.assertIn("la lecture a échoué", envoyees[0])
        self.assertIn("aucun numéro lu", envoyees[1])


class DatesDePublicationTest(unittest.TestCase):
    """Dates lues dans le nom des fichiers et regroupement par jour."""

    def test_jour_lu_dans_le_nom_du_fichier(self):
        self.assertEqual(str(check.jour_publication(fiche("066", "20261124181658"))), "2026-11-24")
        self.assertIsNone(check.jour_publication({"titre": "x", "image": "https://x/autre.jpg"}))

    def test_regroupement_par_jour(self):
        groupes = check.grouper_par_jour(
            [(fiche("064", "20261124181501"), None), (fiche("065", "20261124181601"), None), (fiche("067", "20261126101000"), None)]
        )
        self.assertEqual([len(g) for _, g in groupes], [2, 1])

    def test_precedente_est_tout_le_jour_anterieur(self):
        a062, a063 = fiche("062", "20261119165000"), fiche("063", "20261119170142")
        a064, a066 = fiche("064", "20261124181501"), fiche("066", "20261124181658")
        jour = check.jour_publication(a066)
        self.assertEqual(check.publication_precedente([a062, a063, a064, a066], jour), [a062, a063])
        self.assertEqual(check.publication_precedente([a064, a066], jour), [])


class MessageDePublicationTest(unittest.TestCase):
    """Texte de l'annonce envoyée aux abonnés."""

    def test_plusieurs_listes_le_meme_jour(self):
        nouvelles = [fiche("064", "20261124181501", 24), fiche("066", "20261124181658")]
        precedentes = [fiche("062", "20261119165000"), fiche("063", "20261119170142")]
        texte = check.legende_publication(check.jour_publication(nouvelles[0]), nouvelles, precedentes)
        self.assertIn("<b>2 nouvelles listes publiées le 24/11/2026</b>", texte)
        self.assertIn("• BEG 2026-064 · 24 numéros", texte)
        self.assertIn("Publication précédente : le 19/11/2026\n• BEG 2026-062 · 25 numéros\n• BEG 2026-063", texte)

    def test_une_seule_liste_sans_precedente(self):
        texte = check.legende_publication(check.jour_publication(fiche("066", "20261124181658")), [fiche("066", "20261124181658")], [])
        self.assertIn("<b>Nouvelle liste publiée le 24/11/2026</b>", texte)
        self.assertNotIn("Publication précédente", texte)


class BilanDuReleveTest(unittest.TestCase):
    """Message envoyé à l'administrateur à la fin de chaque relevé."""

    def test_sans_nouvelle_affiche(self):
        base = {"annonces": [fiche("065", "20261124181601"), fiche("066", "20261124181658")]}
        texte = check.bilan_releve(base, [])
        self.assertIn("aucune nouvelle affiche", texte)
        self.assertIn("Dernière publication : BEG 2026-066 du 24/11/2026", texte)

    def test_avec_nouvelles_affiches(self):
        nouvelle = fiche("067", "20261126101000", 22)
        texte = check.bilan_releve({"annonces": [nouvelle]}, [nouvelle])
        self.assertIn("1 nouvelle(s) affiche(s)", texte)
        self.assertIn("• BEG 2026-067 · 22 numéros", texte)


if __name__ == "__main__":
    unittest.main()
