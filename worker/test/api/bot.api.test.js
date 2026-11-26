import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { client, demarrerWorker, fauxSite, fauxTelegram } from "../outils/environnement.js";

let telegram;
let site;
let worker;
let bot;
let prochainChat = 7000;
const nouveauChat = () => ++prochainChat;

/** Publie une base, par la même route que le relevé. */
async function publier(...fiches) {
  const reponse = await bot.admin("PUT", "/admin/annonces", { annonces: fiches });
  assert.equal(reponse.status, 200);
}

before(async () => {
  telegram = await fauxTelegram();
  site = await fauxSite();
  worker = await demarrerWorker({ telegramUrl: telegram.url });
  bot = client(worker);
  await publier(
    { titre: "Numéro: BEG 2025-038", image: site.image("form_affiche_20250922155521PWpga.jpeg"), numeros: ["2025-53580", "2024-49197"] },
    { titre: "Numéro: BEG 2026- 066", image: site.image("form_affiche_20261124181658mTuCM.jpg"), numeros: ["2026-61191", "2026-61330"] },
  );
});

after(async () => {
  await worker?.arreter();
  await telegram?.arreter();
  await site?.arreter();
});

describe("WebhookApiScenario", () => {
  test("un appel sans le secret de Telegram est refusé et reste sans effet", async () => {
    const chat = nouveauChat();
    const reponse = await fetch(`${worker.url}/webhook`, {
      method: "POST",
      headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": "faux" },
      body: JSON.stringify({ update_id: 1, message: { message_id: 1, chat: { id: chat, type: "private" }, text: "/start" } }),
    });
    assert.equal(reponse.status, 403);
    await new Promise((ok) => setTimeout(ok, 300));
    assert.equal(telegram.pour(chat).length, 0);
  });

  test("le webhook répond immédiatement, le message part ensuite", async () => {
    const chat = nouveauChat();
    const reponse = await bot.message(chat, "/start");
    assert.equal(reponse.status, 200);
    const [accueil] = await telegram.attendre(chat);
    assert.match(accueil.text, /Suivi des passeports à retirer/);
  });
});

describe("AccueilApiScenario", () => {
  test("l'accueil présente le service sans prétendre que les données sont anonymes", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "/start");
    const [accueil] = await telegram.attendre(chat);
    assert.match(accueil.text, /Envoyez votre numéro de quittance/);
    assert.doesNotMatch(accueil.text, /anonyme/i);
  });

  test("un message sans numéro reçoit l'aide", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "/start");
    await bot.message(chat, "bonjour");
    const [, aide] = await telegram.attendre(chat, 2);
    assert.match(aide.text, /Aide/);
  });
});

describe("RechercheApiScenario", () => {
  test("un numéro publié reçoit l'affiche de sa liste", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "mon numéro est 2026 61191");
    const [reponse] = await telegram.attendre(chat);
    assert.equal(reponse.methode, "sendPhoto");
    assert.match(reponse.caption, /2026-61191 est publié/);
    assert.match(reponse.caption, /BEG 2026-066/);
  });

  test("une affiche n'est téléversée qu'une fois, puis réutilisée", async () => {
    const premier = nouveauChat();
    const second = nouveauChat();
    await bot.message(premier, "2025-53580");
    const [envoi] = await telegram.attendre(premier);
    await bot.message(second, "2025-53580");
    const [reprise] = await telegram.attendre(second);
    assert.equal(envoi.photo, "<fichier>");
    assert.match(reprise.photo, /^photo-\d+$/);
  });

  test("un numéro non publié est mis en suivi", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "2026-99999");
    const [reponse] = await telegram.attendre(chat);
    assert.match(reponse.text, /2026-99999 n'est pas encore publié/);
    assert.match(reponse.text, /je vous préviens dès qu'il est publié/);
    await bot.message(chat, "/suivis");
    const [, suivis] = await telegram.attendre(chat, 2);
    assert.match(suivis.text, /2026-99999/);
  });

  test("un numéro sans l'année est retrouvé", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "61191");
    const [reponse] = await telegram.attendre(chat);
    assert.match(reponse.caption, /2026-61191 est publié/);
  });

  test("un numéro sans l'année n'est jamais mis en suivi", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "99999");
    const [reponse] = await telegram.attendre(chat);
    assert.match(reponse.text, /numéro complet avec l'année/);
  });
});

describe("SuiviApiScenario", () => {
  test("le suivi est limité à cinq numéros", async () => {
    const chat = nouveauChat();
    for (let i = 1; i <= 6; i++) await bot.message(chat, `2026-9100${i}`);
    const messages = await telegram.attendre(chat, 6);
    assert.match(messages.at(-1).text, /Vous suivez déjà 5 numéros/);
  });

  test("un suivi se retire par son bouton", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "2026-92001");
    await telegram.attendre(chat);
    await bot.bouton(chat, "oublier:2026-92001");
    const [, retrait] = await telegram.attendre(chat, 2);
    assert.match(retrait.text, /Je ne suis plus le numéro/);
    await bot.message(chat, "/suivis");
    const [, , suivis] = await telegram.attendre(chat, 3);
    assert.match(suivis.text, /Aucun pour le moment/);
  });
});

describe("ConfidentialiteApiScenario", () => {
  test("la politique décrit les données, les droits et le contact configuré", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "/confidentialite");
    const [politique] = await telegram.attendre(chat);
    assert.match(politique.text, /numéros de quittance que vous recherchez/);
    assert.match(politique.text, /@contact_de_test/);
    assert.match(politique.text, /\/stop/);
  });
});

describe("DesinscriptionApiScenario", () => {
  test("/stop désabonne la personne", async () => {
    const chat = nouveauChat();
    await bot.message(chat, "2026-93001");
    await telegram.attendre(chat);
    await bot.message(chat, "/stop");
    const [, confirmation] = await telegram.attendre(chat, 2);
    assert.match(confirmation.text, /Désinscription enregistrée/);
    const { abonnes } = await (await bot.admin("GET", "/admin/abonnes")).json();
    assert.ok(!abonnes.some((a) => a.chat === String(chat)));
  });
});

describe("AdministrationApiScenario", () => {
  test("les routes d'administration exigent le secret", async () => {
    const sans = await fetch(`${worker.url}/admin/abonnes`);
    assert.equal(sans.status, 403);
    const avec = await bot.admin("GET", "/admin/abonnes");
    assert.equal(avec.status, 200);
  });

  test("le bot n'expose aucune commande de statistiques, même à l'administrateur", async () => {
    for (const commande of ["/stats", "/personnes"]) {
      await bot.message(1, commande);
    }
    const messages = await telegram.attendre(1, 2);
    for (const m of messages) assert.doesNotMatch(m.text, /Statistiques|Personnes/);
  });
});
