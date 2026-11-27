import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";
import { declencherReleve, estHeureDeReleve } from "../../src/index.js";

const env = {
  GITHUB_DISPATCH_TOKEN: "jeton-github",
  GITHUB_API: "https://github.test",
  GITHUB_DEPOT: "proprietaire/depot",
  TELEGRAM_BOT_TOKEN: "jeton-telegram",
  TELEGRAM_API: "https://telegram.test",
  ADMIN_CHAT: "1",
};

describe("CreneauDuReleveTest", () => {
  test("11 h et 19 h à Paris en hiver, soit 10 h et 18 h UTC", () => {
    assert.ok(estHeureDeReleve(new Date("2026-11-27T10:00:00Z")));
    assert.ok(estHeureDeReleve(new Date("2026-11-27T18:00:00Z")));
    assert.ok(!estHeureDeReleve(new Date("2026-11-27T09:00:00Z")));
    assert.ok(!estHeureDeReleve(new Date("2026-11-27T17:00:00Z")));
  });

  test("11 h et 19 h à Paris en été, soit 9 h et 17 h UTC", () => {
    assert.ok(estHeureDeReleve(new Date("2026-07-01T09:00:00Z")));
    assert.ok(estHeureDeReleve(new Date("2026-07-01T17:00:00Z")));
    assert.ok(!estHeureDeReleve(new Date("2026-07-01T10:00:00Z")));
    assert.ok(!estHeureDeReleve(new Date("2026-07-01T18:00:00Z")));
  });
});

describe("DeclenchementDuReleveTest", () => {
  let appels;
  let statutGithub;
  const fetchOriginal = globalThis.fetch;

  beforeEach(() => {
    appels = [];
    statutGithub = 204;
    globalThis.fetch = async (url, init) => {
      appels.push({ url: String(url), init });
      if (String(url).startsWith("https://github.test")) return new Response(null, { status: statutGithub });
      return Response.json({ ok: true, result: {} });
    };
  });

  afterEach(() => {
    globalThis.fetch = fetchOriginal;
  });

  test("à l'heure du relevé, le workflow est lancé sur main", async () => {
    assert.equal(await declencherReleve(env, new Date("2026-11-27T10:00:00Z")), true);
    assert.equal(appels.length, 1);
    assert.equal(appels[0].url, "https://github.test/repos/proprietaire/depot/actions/workflows/check.yml/dispatches");
    assert.equal(appels[0].init.headers.Authorization, "Bearer jeton-github");
    assert.deepEqual(JSON.parse(appels[0].init.body), { ref: "main" });
  });

  test("hors des heures du relevé, rien n'est lancé", async () => {
    assert.equal(await declencherReleve(env, new Date("2026-11-27T09:00:00Z")), false);
    assert.equal(appels.length, 0);
  });

  test("un refus de GitHub prévient l'administrateur", async () => {
    statutGithub = 401;
    await assert.rejects(declencherReleve(env, new Date("2026-11-27T18:00:00Z")), /GitHub 401/);
    const alerte = appels.find((a) => a.url.startsWith("https://telegram.test"));
    assert.match(JSON.parse(alerte.init.body).text, /Le lancement du relevé a échoué \(GitHub 401\)/);
  });
});
