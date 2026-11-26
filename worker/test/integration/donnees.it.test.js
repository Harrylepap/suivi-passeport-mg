import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { client, demarrerWorker, fauxTelegram } from "../outils/environnement.js";

let telegram;
let worker;
let bot;

before(async () => {
  telegram = await fauxTelegram();
  worker = await demarrerWorker({ telegramUrl: telegram.url });
  bot = client(worker);
  await bot.admin("PUT", "/admin/annonces", { annonces: [] });
});

after(async () => {
  await worker?.arreter();
  await telegram?.arreter();
});

describe("SchemaIT", () => {
  test("les migrations créent les tables attendues", () => {
    const tables = worker.sql("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").map((t) => t.name);
    assert.ok(tables.includes("personnes"));
    assert.ok(tables.includes("evenements"));
  });
});

describe("JournalisationIT", () => {
  test("l'identité de la personne est enregistrée dans D1", async () => {
    await bot.message(8001, "/start", { id: 8001, first_name: "Rakoto", username: "rakoto" });
    await telegram.attendre(8001);
    const [personne] = worker.sql("SELECT pseudo, prenom FROM personnes WHERE chat = '8001'");
    assert.deepEqual(personne, { pseudo: "rakoto", prenom: "Rakoto" });
  });

  test("une recherche est rattachée à la conversation, avec son résultat", async () => {
    await bot.message(8002, "2026-77777");
    await telegram.attendre(8002);
    const evenements = worker.sql("SELECT type, numero, trouve FROM evenements WHERE utilisateur = '8002' ORDER BY id");
    assert.deepEqual(evenements, [
      { type: "recherche", numero: "2026-77777", trouve: 0 },
      { type: "suivi_ajoute", numero: "2026-77777", trouve: null },
    ]);
  });
});

describe("EffacementIT", () => {
  test("/stop supprime la fiche et tout l'historique de la personne", async () => {
    await bot.message(8003, "2026-77778");
    await telegram.attendre(8003);
    await bot.message(8003, "/stop");
    await telegram.attendre(8003, 2);
    assert.deepEqual(worker.sql("SELECT chat FROM personnes WHERE chat = '8003'"), []);
    assert.deepEqual(worker.sql("SELECT id FROM evenements WHERE utilisateur = '8003'"), []);
  });

  test("la purge efface les personnes inactives depuis douze mois et les prévient", async () => {
    await bot.message(8004, "2026-77779");
    await telegram.attendre(8004);
    worker.sql("UPDATE personnes SET derniere_vue = datetime('now', '-13 months') WHERE chat = '8004'");
    const { purges } = await (await bot.admin("POST", "/admin/purge", {})).json();
    assert.equal(purges, 1);
    const [, adieu] = await telegram.attendre(8004, 2);
    assert.match(adieu.text, /12 mois/);
    assert.deepEqual(worker.sql("SELECT chat FROM personnes WHERE chat = '8004'"), []);
    const { abonnes } = await (await bot.admin("GET", "/admin/abonnes")).json();
    assert.ok(!abonnes.some((a) => a.chat === "8004"));
  });

  test("une personne active n'est pas purgée", async () => {
    await bot.message(8005, "/start");
    await telegram.attendre(8005);
    await bot.admin("POST", "/admin/purge", {});
    assert.equal(worker.sql("SELECT chat FROM personnes WHERE chat = '8005'").length, 1);
  });
});
