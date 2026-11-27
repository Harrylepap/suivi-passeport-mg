import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { confidentialite, echapper, extraireNumeros, nomCourt, texteRappel } from "../../src/index.js";

describe("ExtractionDesNumerosTest", () => {
  test("un numéro complet est reconnu, quel que soit le séparateur", () => {
    assert.deepEqual(extraireNumeros("mon numéro est 2026 61191").complets, ["2026-61191"]);
    assert.deepEqual(extraireNumeros("2026–61191 et 2025-5052").complets, ["2026-61191", "2025-5052"]);
  });

  test("sans année, le numéro est gardé comme numéro court", () => {
    assert.deepEqual(extraireNumeros("61191"), { complets: [], courts: ["61191"] });
  });

  test("un numéro complet l'emporte sur les numéros courts", () => {
    assert.deepEqual(extraireNumeros("2026-61191 dossier 4242").courts, []);
  });

  test("les doublons sont retirés", () => {
    assert.deepEqual(extraireNumeros("2026-61191 2026-61191").complets, ["2026-61191"]);
  });

  test("un texte sans numéro ne donne rien", () => {
    assert.deepEqual(extraireNumeros("bonjour"), { complets: [], courts: [] });
  });
});

describe("PresentationTest", () => {
  test("les titres d'affiches sont nettoyés", () => {
    assert.equal(nomCourt({ titre: "Numéro: beg 2026 - 023" }), "BEG 2026-023");
    assert.equal(nomCourt({ titre: "Numéro: BEG 2026- 034/ 054" }), "BEG 2026-034/054");
  });

  test("le HTML est échappé", () => {
    assert.equal(echapper("<b>A & B</b>"), "&lt;b&gt;A &amp; B&lt;/b&gt;");
  });

  test("la politique de confidentialité affiche le contact configuré", () => {
    assert.match(confidentialite("@contact"), /écrivez à @contact/);
    assert.match(confidentialite(undefined), /écrivez à l'administrateur du service/);
  });
});

describe("RappelDeRetraitTest", () => {
  test("le rappel cite le numéro, la liste et les horaires de retrait", () => {
    const texte = texteRappel("2026-61191", "BEG 2026-066");
    assert.match(texte, /<code>2026-61191<\/code>/);
    assert.match(texte, /BEG 2026-066/);
    assert.match(texte, /14 h 30 à 16 h 30/);
    assert.match(texte, /vérifiez-les sur l'affiche/);
  });
});
