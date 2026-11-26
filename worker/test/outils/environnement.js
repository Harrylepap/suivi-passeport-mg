import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const DOSSIER_WORKER = resolve(import.meta.dirname, "..", "..");
export const FIXTURES = resolve(DOSSIER_WORKER, "..", "tests", "fixtures");
export const SECRETS = {
  TELEGRAM_BOT_TOKEN: "jeton-de-test",
  WEBHOOK_SECRET: "secret-webhook-de-test",
  ADMIN_SECRET: "secret-admin-de-test",
  CONTACT: "@contact_de_test",
};
const WINDOWS = process.platform === "win32";
const WRANGLER = [resolve(DOSSIER_WORKER, "node_modules", "wrangler", "bin", "wrangler.js")];

/** Lit le corps d'une requête HTTP et le décode selon son type : JSON, formulaire ou multipart. */
async function lireCorps(requete) {
  const morceaux = [];
  for await (const morceau of requete) morceaux.push(morceau);
  const brut = Buffer.concat(morceaux);
  const type = requete.headers["content-type"] || "";
  if (type.includes("application/json")) return JSON.parse(brut.toString("utf8"));
  if (type.includes("application/x-www-form-urlencoded")) {
    return Object.fromEntries(new URLSearchParams(brut.toString("utf8")));
  }
  if (type.includes("multipart/form-data")) {
    const champs = {};
    const texte = brut.toString("latin1");
    for (const m of texte.matchAll(/name="([^"]+)"(?:; filename="[^"]*")?\r\n(?:[^\r\n]+\r\n)*\r\n([\s\S]*?)\r\n--/g)) {
      champs[m[1]] = m[1] === "photo" ? "<fichier>" : Buffer.from(m[2], "latin1").toString("utf8");
    }
    return champs;
  }
  return {};
}

/** Démarre un faux serveur de l'API Telegram, qui enregistre chaque appel. */
export async function fauxTelegram() {
  const appels = [];
  let numero = 0;
  const serveur = createServer(async (requete, reponse) => {
    const methode = requete.url.split("/").pop();
    const corps = await lireCorps(requete);
    appels.push({ methode, ...corps, chat_id: corps.chat_id === undefined ? undefined : String(corps.chat_id) });
    numero += 1;
    const result = methode === "sendPhoto" ? { message_id: numero, photo: [{ file_id: `photo-${numero}` }] } : { message_id: numero };
    reponse.writeHead(200, { "content-type": "application/json" });
    reponse.end(JSON.stringify({ ok: true, result }));
  });
  await new Promise((ok) => serveur.listen(0, "127.0.0.1", ok));
  return {
    url: `http://127.0.0.1:${serveur.address().port}`,
    appels,
    /** Messages reçus par une conversation donnée. */
    pour(chat) {
      return appels.filter((a) => a.chat_id === String(chat) && /^send/.test(a.methode));
    },
    /** Attend qu'une conversation ait reçu au moins « n » messages. */
    async attendre(chat, n = 1, delai = 10000) {
      const fin = Date.now() + delai;
      while (Date.now() < fin) {
        if (this.pour(chat).length >= n) return this.pour(chat);
        await new Promise((ok) => setTimeout(ok, 50));
      }
      throw new Error(`Conversation ${chat} : ${this.pour(chat).length} message(s) reçu(s), ${n} attendu(s)`);
    },
    arreter: () => new Promise((ok) => serveur.close(ok)),
  };
}

/** Démarre un faux site de l'Ambassade, qui sert les affiches de référence. */
export async function fauxSite() {
  const serveur = createServer((requete, reponse) => {
    const nom = decodeURIComponent(requete.url.split("/").pop());
    try {
      const image = readFileSync(join(FIXTURES, nom));
      reponse.writeHead(200, { "content-type": "image/jpeg" });
      reponse.end(image);
    } catch {
      reponse.writeHead(404);
      reponse.end();
    }
  });
  await new Promise((ok) => serveur.listen(0, "127.0.0.1", ok));
  const url = `http://127.0.0.1:${serveur.address().port}`;
  return { url, image: (nom) => `${url}/uploads/${nom}`, arreter: () => new Promise((ok) => serveur.close(ok)) };
}

/** Renvoie un port TCP libre. */
async function portLibre() {
  const serveur = createServer();
  await new Promise((ok) => serveur.listen(0, "127.0.0.1", ok));
  const { port } = serveur.address();
  await new Promise((ok) => serveur.close(ok));
  return port;
}

/** Démarre le Worker en local, avec une base vide et des secrets fictifs. */
export async function demarrerWorker({ telegramUrl }) {
  const persistance = mkdtempSync(join(tmpdir(), "passeport-bot-"));
  const fichierEnv = join(persistance, "test.env");
  writeFileSync(
    fichierEnv,
    Object.entries({ ...SECRETS, TELEGRAM_API: telegramUrl, ADMIN_CHAT: "1" })
      .map(([cle, valeur]) => `${cle}=${valeur}`)
      .join("\n"),
  );
  const options = { cwd: DOSSIER_WORKER, env: { ...process.env, CI: "1", WRANGLER_SEND_METRICS: "false" } };
  execFileSync(process.execPath, [...WRANGLER, "d1", "migrations", "apply", "passeport-bot", "--local", "--persist-to", persistance], {
    ...options,
    stdio: "ignore",
  });
  const port = await portLibre();
  const processus = spawn(
    process.execPath,
    [...WRANGLER, "dev", "--local", "--ip", "127.0.0.1", "--port", String(port), "--persist-to", persistance, "--env-file", fichierEnv],
    { ...options, detached: !WINDOWS },
  );
  let journal = "";
  await new Promise((ok, echec) => {
    const minuterie = setTimeout(() => echec(new Error(`Le Worker n'a pas démarré :\n${journal}`)), 60000);
    const lire = (morceau) => {
      journal += morceau.toString();
      if (/Ready on/.test(journal)) {
        clearTimeout(minuterie);
        ok();
      }
    };
    processus.stdout.on("data", lire);
    processus.stderr.on("data", lire);
    processus.on("exit", (code) => echec(new Error(`Le Worker s'est arrêté (code ${code}) :\n${journal}`)));
  });
  return {
    url: `http://127.0.0.1:${port}`,
    persistance,
    /** Exécute une requête SQL sur la base locale : réservé aux tests d'intégration. */
    sql(requete) {
      const sortie = execFileSync(
        process.execPath,
        [...WRANGLER, "d1", "execute", "passeport-bot", "--local", "--persist-to", persistance, "--json", "--command", requete],
        { ...options, encoding: "utf8" },
      );
      return JSON.parse(sortie)[0].results;
    },
    async arreter() {
      processus.removeAllListeners("exit");
      if (WINDOWS) {
        try {
          execFileSync("taskkill", ["/pid", String(processus.pid), "/T", "/F"], { stdio: "ignore" });
        } catch {}
      } else {
        try {
          process.kill(-processus.pid, "SIGTERM");
        } catch {}
      }
      await new Promise((ok) => setTimeout(ok, 500));
      rmSync(persistance, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    },
  };
}

/** Client de test : parle au Worker comme Telegram et comme le relevé le font. */
export function client(worker) {
  let prochainUpdate = 1;
  return {
    async message(chat, texte, de = { id: chat, first_name: "Rasoa", username: `rasoa_${chat}` }) {
      return fetch(`${worker.url}/webhook`, {
        method: "POST",
        headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": SECRETS.WEBHOOK_SECRET },
        body: JSON.stringify({
          update_id: prochainUpdate++,
          message: { message_id: prochainUpdate, chat: { id: chat, type: "private" }, from: de, text: texte },
        }),
      });
    },
    async bouton(chat, donnees) {
      return fetch(`${worker.url}/webhook`, {
        method: "POST",
        headers: { "content-type": "application/json", "X-Telegram-Bot-Api-Secret-Token": SECRETS.WEBHOOK_SECRET },
        body: JSON.stringify({
          update_id: prochainUpdate++,
          callback_query: {
            id: String(prochainUpdate),
            from: { id: chat, first_name: "Rasoa" },
            data: donnees,
            message: { message_id: prochainUpdate, chat: { id: chat, type: "private" } },
          },
        }),
      });
    },
    async admin(methode, chemin, corps) {
      return fetch(`${worker.url}${chemin}`, {
        method: methode,
        headers: { Authorization: `Bearer ${SECRETS.ADMIN_SECRET}`, "content-type": "application/json" },
        body: corps === undefined ? undefined : JSON.stringify(corps),
      });
    },
  };
}
