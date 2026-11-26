import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import worker from "../src/index.js";

const CHAT = 4242;
const BASE = {
  annonces: [
    { titre: "Numéro: BEG 2026- 065", image: "https://exemple.test/a.jpg", numeros: ["2026-60917"], file_id: "F65" },
    { titre: "Numéro: beg 2026 - 066", image: "https://exemple.test/b.jpg", numeros: ["2026-61191"], file_id: "F66" },
  ],
};

let env;
let appels;
let evenements;
let personnes;

/** Simule le stockage KV de Cloudflare. */
function fauxKV() {
  const donnees = new Map();
  return {
    donnees,
    async get(cle, type) {
      const e = donnees.get(cle);
      if (!e) return null;
      return type === "json" ? JSON.parse(e.value) : e.value;
    },
    async getWithMetadata(cle) {
      const e = donnees.get(cle);
      return { value: e ? e.value : null, metadata: e ? e.metadata : null };
    },
    async put(cle, value, options = {}) {
      donnees.set(cle, { value, metadata: options.metadata ?? null });
    },
    async delete(cle) {
      donnees.delete(cle);
    },
    async list({ prefix }) {
      const keys = [...donnees.entries()]
        .filter(([nom]) => nom.startsWith(prefix))
        .map(([name, e]) => ({ name, metadata: e.metadata }));
      return { keys, list_complete: true };
    },
  };
}

/** Applique une requête à nos tableaux en mémoire, pour simuler la base D1. */
function executer(sql, valeurs) {
  if (sql.startsWith("INSERT INTO evenements")) {
    evenements.push({ utilisateur: valeurs[0], type: valeurs[1], numero: valeurs[2], trouve: valeurs[3] });
  } else if (sql.startsWith("INSERT INTO personnes")) {
    const [chat, pseudo, prenom, nom] = valeurs;
    personnes.set(chat, { chat, pseudo, prenom, nom });
  } else if (sql.startsWith("DELETE FROM evenements")) {
    evenements = evenements.filter((e) => e.utilisateur !== valeurs[0]);
  } else if (sql.startsWith("DELETE FROM personnes")) {
    personnes.delete(valeurs[0]);
  }
}

/** Simule la base D1, en retenant écritures et comptages. */
function fauxDB() {
  return {
    prepare(sql) {
      return {
        bind(...valeurs) {
          return {
            sql,
            valeurs,
            async run() {
              executer(sql, valeurs);
            },
            async all() {
              if (sql.startsWith("SELECT chat FROM personnes")) {
                return { results: [...personnes.values()].filter((p) => p.inactif).map((p) => ({ chat: p.chat })) };
              }
              return { results: [] };
            },
          };
        },
        async first() {
          return { n: 0, trouvees: 0, numeros: 0 };
        },
      };
    },
    async batch(requetes) {
      for (const r of requetes) executer(r.sql, r.valeurs);
    },
  };
}

/** Envoie un message au webhook et attend la fin du traitement. */
async function message(texte, { chat = CHAT, secret = env.WEBHOOK_SECRET, de } = {}) {
  const taches = [];
  const from = de ?? { id: chat, first_name: "Jean", username: "jean_test" };
  const requete = new Request("https://bot.test/webhook", {
    method: "POST",
    headers: { "X-Telegram-Bot-Api-Secret-Token": secret, "content-type": "application/json" },
    body: JSON.stringify({
      update_id: 1,
      message: { message_id: 1, chat: { id: chat, type: "private" }, from, text: texte },
    }),
  });
  const reponse = await worker.fetch(requete, env, { waitUntil: (p) => taches.push(p) });
  await Promise.all(taches);
  return reponse;
}

beforeEach(async () => {
  appels = [];
  evenements = [];
  personnes = new Map();
  env = {
    KV: fauxKV(),
    DB: fauxDB(),
    TELEGRAM_BOT_TOKEN: "jeton",
    WEBHOOK_SECRET: "secret-webhook",
    ADMIN_SECRET: "secret-admin",
    CONTACT: "@contact_test",
  };
  await env.KV.put("annonces", JSON.stringify(BASE));
  globalThis.fetch = async (url, init) => {
    const methode = String(url).split("/").pop();
    appels.push({ methode, corps: JSON.parse(init.body) });
    return Response.json({ ok: true, result: {} });
  };
});

test("le webhook refuse un appel sans le secret de Telegram", async () => {
  const reponse = await message("/start", { secret: "faux" });
  assert.equal(reponse.status, 403);
  assert.equal(appels.length, 0);
});

test("/start envoie l'accueil et abonne la personne", async () => {
  await message("/start");
  assert.equal(appels[0].methode, "sendMessage");
  assert.match(appels[0].corps.text, /Suivi des passeports à retirer/);
  assert.ok(env.KV.donnees.has(`abonne:${CHAT}`));
  assert.equal(evenements[0].type, "demarrage");
});

test("l'accueil ne prétend pas que les données sont anonymes", async () => {
  await message("/start");
  assert.doesNotMatch(appels[0].corps.text, /anonyme/i);
});

test("/confidentialite décrit les données réellement enregistrées", async () => {
  await message("/confidentialite");
  assert.match(appels[0].corps.text, /Confidentialité/);
  assert.match(appels[0].corps.text, /numéros de quittance que vous recherchez/);
  assert.match(appels[0].corps.text, /\/stop/);
});

test("l'identité de la personne est enregistrée", async () => {
  await message("/start", { de: { id: CHAT, first_name: "Rakoto", username: "rakoto" } });
  assert.deepEqual(personnes.get(String(CHAT)), {
    chat: String(CHAT),
    pseudo: "rakoto",
    prenom: "Rakoto",
    nom: null,
  });
});

test("l'événement est rattaché à l'identifiant réel de la conversation", async () => {
  await message("/start");
  assert.equal(evenements[0].utilisateur, String(CHAT));
});

test("un numéro publié renvoie l'affiche de sa liste", async () => {
  await message("mon numéro est 2026 61191");
  assert.equal(appels[0].methode, "sendPhoto");
  assert.equal(appels[0].corps.photo, "F66");
  assert.match(appels[0].corps.caption, /2026-61191 est publié/);
  assert.match(appels[0].corps.caption, /BEG 2026-066/);
  assert.deepEqual(evenements.map((e) => [e.type, e.numero, e.trouve]), [["recherche", "2026-61191", 1]]);
});

test("un numéro non publié est mis en suivi", async () => {
  await message("2026-99999");
  assert.match(appels[0].corps.text, /n'est pas encore publié/);
  assert.deepEqual(env.KV.donnees.get(`abonne:${CHAT}`).metadata.suivis, ["2026-99999"]);
  assert.deepEqual(evenements.map((e) => e.type), ["recherche", "suivi_ajoute"]);
});

test("un numéro court est trouvé mais jamais mis en suivi", async () => {
  await message("61191");
  assert.equal(appels[0].methode, "sendPhoto");
  await message("99999");
  assert.match(appels[1].corps.text, /numéro complet avec l'année/);
  assert.deepEqual(env.KV.donnees.get(`abonne:${CHAT}`).metadata.suivis, []);
});

test("le suivi est limité à cinq numéros", async () => {
  for (let i = 1; i <= 6; i++) await message(`2026-9000${i}`);
  assert.equal(env.KV.donnees.get(`abonne:${CHAT}`).metadata.suivis.length, 5);
  assert.match(appels.at(-1).corps.text, /Vous suivez déjà 5 numéros/);
});

test("/stop désabonne et efface les données de la personne", async () => {
  await message("2026-99999");
  await message("/stop");
  assert.ok(!env.KV.donnees.has(`abonne:${CHAT}`));
  assert.equal(evenements.length, 0);
  assert.ok(!personnes.has(String(CHAT)));
});

test("le bot n'expose aucune commande de statistiques", async () => {
  for (const commande of ["/stats", "/personnes"]) {
    await message(commande, { chat: 1 });
    assert.doesNotMatch(appels.at(-1).corps.text, /Statistiques|Personnes/);
  }
});

test("la purge efface les personnes inactives et les prévient", async () => {
  await message("2026-99999");
  personnes.get(String(CHAT)).inactif = true;
  const reponse = await worker.fetch(
    new Request("https://bot.test/admin/purge", { method: "POST", headers: { Authorization: "Bearer secret-admin" } }),
    env,
    {},
  );
  assert.deepEqual(await reponse.json(), { purges: 1 });
  assert.ok(!personnes.has(String(CHAT)));
  assert.equal(evenements.length, 0);
  assert.ok(!env.KV.donnees.has(`abonne:${CHAT}`));
  assert.match(appels.at(-1).corps.text, /12 mois/);
});

test("la politique de confidentialité donne un contact", async () => {
  await message("/confidentialite");
  assert.match(appels[0].corps.text, /@contact_test/);
});

test("les routes d'administration exigent le secret", async () => {
  const sans = await worker.fetch(new Request("https://bot.test/admin/abonnes"), env, {});
  assert.equal(sans.status, 403);
  await message("/start");
  const avec = await worker.fetch(
    new Request("https://bot.test/admin/abonnes", { headers: { Authorization: "Bearer secret-admin" } }),
    env,
    {},
  );
  assert.deepEqual(await avec.json(), { abonnes: [{ chat: String(CHAT), suivis: [] }] });
});
