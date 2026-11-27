const PAGE = "https://ambamad-paris.diplomatie.gov.mg/app/passeport/index.php/annonce";
const SUIVIS_MAX = 5;
const CONSERVATION_MOIS = 12;
const RAPPEL_JOURS = 14;
const LIMITE_RECHERCHES_HEURE = 30;
const RE_QUITTANCE = /(?<!\d)(20\d{2})\s*[-‐-―.]?\s*(\d{4,6})(?!\d)/g;
const RE_COURT = /(?<!\d)(\d{4,6})(?!\d)/g;

const PRUDENCE = "<i>Lecture automatique : vérifiez toujours votre numéro sur l'image avant de vous déplacer.</i>";
const ACCUEIL = [
  "<b>Suivi des passeports à retirer</b>",
  "Ambassade de Madagascar en France",
  "",
  "Bonjour, je vous aide à savoir si votre passeport est prêt.",
  "",
  "<b>Comment ça marche</b>",
  "1. Envoyez votre numéro de quittance, par exemple <code>2026-61191</code>.",
  "2. Je vous dis tout de suite s'il figure dans une liste publiée.",
  "3. S'il n'est pas encore publié, je le garde en mémoire et je vous préviens dès qu'il sort.",
  "",
  "Vous recevez aussi chaque nouvelle liste dès sa publication.",
  "",
  PRUDENCE,
  "<i>Service bénévole et gratuit, indépendant de l'Ambassade.</i>",
].join("\n");
const AIDE = [
  "<b>Aide</b>",
  "",
  "Envoyez simplement votre numéro de quittance, par exemple <code>2026-61191</code>.",
  "",
  "/derniere : revoir la dernière liste publiée",
  "/suivis : voir vos numéros suivis",
  "/confidentialite : vos données et vos droits",
  "/stop : ne plus recevoir de messages",
  "",
  PRUDENCE,
].join("\n");
/** Compose la politique de confidentialité, avec le contact défini dans la configuration. */
export const confidentialite = (contact) => [
  "<b>Confidentialité</b>",
  "",
  "Ce service est bénévole et indépendant de l'Ambassade.",
  "",
  "<b>Ce qui est enregistré</b>",
  "Pour faire fonctionner le bot et l'améliorer, sont conservés :",
  "• votre identifiant de conversation Telegram, votre nom public et votre pseudonyme s'il existe ;",
  "• les numéros de quittance que vous recherchez, la date de chaque recherche et son résultat ;",
  "• les numéros que vous suivez, jusqu'à leur publication, puis deux semaines encore pour vous rappeler d'aller retirer votre passeport.",
  "",
  "<b>À quoi cela sert</b>",
  "Répondre à vos recherches, vous prévenir quand votre numéro paraît, mesurer la fréquentation et améliorer le service. Ces données ne sont ni vendues ni transmises à des tiers.",
  "",
  "<b>Combien de temps</b>",
  `Tant que vous utilisez le bot. Après ${CONSERVATION_MOIS} mois sans aucun message de votre part, ou dès la commande /stop, votre inscription, vos numéros suivis et les données qui vous identifient sont effacés. Les sauvegardes de sécurité sont conservées quatre semaines au plus.`,
  "",
  "<b>Vos droits</b>",
  `Vous pouvez à tout moment consulter, corriger ou effacer vos données (/stop), conformément au RGPD. Pour toute demande, écrivez à ${contact || "l'administrateur du service"} sur Telegram.`,
  "",
  "Ces données sont traitées sur la base de l'intérêt légitime du service. Vous pouvez vous y opposer à tout moment avec /stop.",
].join("\n");
const B_OFFICIEL = { text: "Listes officielles", url: PAGE };
const MENU = [
  [
    { text: "Dernière liste", callback_data: "derniere" },
    { text: "Mes numéros suivis", callback_data: "suivis" },
  ],
  [B_OFFICIEL],
];

export default {
  /** Aiguille les requêtes : webhook Telegram, routes d'administration, page d'état. */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/webhook") {
      if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
        return new Response("refuse", { status: 403 });
      }
      const update = await request.json();
      ctx.waitUntil(
        traiterUpdate(update, env).catch((e) =>
          console.error(JSON.stringify({ evenement: "erreur", message: e.message })),
        ),
      );
      return new Response("ok");
    }

    if (url.pathname.startsWith("/admin/")) {
      if (request.headers.get("Authorization") !== `Bearer ${env.ADMIN_SECRET}`) {
        return new Response("refuse", { status: 403 });
      }
      return admin(request, url, env);
    }

    return new Response("Bot en ligne");
  },

  /** Tâche planifiée : lance le relevé GitHub à 10 h et 19 h, et envoie les rappels de retrait à 10 h. */
  async scheduled(evenement, env, ctx) {
    const date = new Date(evenement.scheduledTime);
    ctx.waitUntil(
      declencherReleve(env, date).catch((e) =>
        console.error(JSON.stringify({ evenement: "erreur_declenchement", message: e.message })),
      ),
    );
    if (heureParis(date) === 10) {
      ctx.waitUntil(
        envoyerRappels(env, date).catch((e) =>
          console.error(JSON.stringify({ evenement: "erreur_rappels", message: e.message })),
        ),
      );
    }
  },
};

/** Renvoie l'heure de Paris, de 0 à 23, à une date donnée. */
function heureParis(date) {
  return Number(
    new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "numeric", hourCycle: "h23" })
      .formatToParts(date)
      .find((partie) => partie.type === "hour").value,
  );
}

/** Indique si une date tombe à 10 h ou à 19 h, heure de Paris, été comme hiver. */
export function estHeureDeReleve(date) {
  const heure = heureParis(date);
  return heure === 10 || heure === 19;
}

/** Compose le rappel envoyé quelques jours après la publication d'un numéro suivi. */
export function texteRappel(numero, liste) {
  return [
    "📌 <b>Rappel : votre passeport vous attend</b>",
    `Le numéro <code>${echapper(numero)}</code> figure dans la liste ${liste}, publiée il y a deux semaines.`,
    "",
    "Retrait sans rendez-vous à l'Ambassade, du lundi au vendredi de 14 h 30 à 16 h 30, avec votre ancien passeport. Ces horaires peuvent changer : vérifiez-les sur l'affiche.",
    "",
    "Si vous l'avez déjà retiré, ignorez ce message.",
  ].join("\n");
}

/** Envoie les rappels arrivés à échéance, puis les efface. Renvoie le nombre de rappels envoyés. */
async function envoyerRappels(env, maintenant) {
  const echeance = maintenant.getTime() - RAPPEL_JOURS * 86400000;
  let envoyes = 0;
  let cursor;
  do {
    const page = await env.KV.list({ prefix: "rappel:", cursor });
    for (const cle of page.keys) {
      const { numero, liste, du } = cle.metadata || {};
      if (!du || Date.parse(du) > echeance) continue;
      const chat = cle.name.split(":")[1];
      await envoyerTexte(env, chat, texteRappel(numero, liste)).catch(() => {});
      await env.KV.delete(cle.name);
      await journaliser(env, chat, "rappel_retrait", { numero, liste });
      envoyes += 1;
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return envoyes;
}

/** Efface les rappels en attente d'une personne. */
async function effacerRappels(env, chat) {
  const page = await env.KV.list({ prefix: `rappel:${chat}:` });
  for (const cle of page.keys) await env.KV.delete(cle.name);
}

/** Lance le workflow du relevé sur GitHub ; prévient l'administrateur si GitHub refuse. */
export async function declencherReleve(env, date) {
  if (!estHeureDeReleve(date)) return false;
  const api = (env.GITHUB_API || "https://api.github.com").replace(/\/$/, "");
  const depot = env.GITHUB_DEPOT || "Harrylepap/suivi-passeport-mg";
  const reponse = await fetch(`${api}/repos/${depot}/actions/workflows/check.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "passeport-bot",
      "content-type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (reponse.status === 204) {
    console.log(JSON.stringify({ evenement: "releve_declenche" }));
    return true;
  }
  if (env.ADMIN_CHAT) {
    await envoyerTexte(
      env,
      env.ADMIN_CHAT,
      `Le lancement du relevé a échoué (GitHub ${reponse.status}). Lancez-le à la main depuis l'onglet Actions, et vérifiez le jeton GITHUB_DISPATCH_TOKEN.`,
    ).catch(() => {});
  }
  throw new Error(`GitHub ${reponse.status} : ${await reponse.text()}`);
}

/** Routes réservées au relevé : publication de la base, liste et suppression d'abonnés. */
async function admin(request, url, env) {
  if (request.method === "PUT" && url.pathname === "/admin/annonces") {
    const base = await request.json();
    if (!Array.isArray(base.annonces)) return new Response("format", { status: 400 });
    await env.KV.put("annonces", JSON.stringify(base));
    return Response.json({ annonces: base.annonces.length });
  }
  if (request.method === "GET" && url.pathname === "/admin/abonnes") {
    const abonnes = [];
    let cursor;
    do {
      const page = await env.KV.list({ prefix: "abonne:", cursor });
      for (const cle of page.keys) {
        abonnes.push({ chat: cle.name.slice(7), suivis: cle.metadata?.suivis || [] });
      }
      cursor = page.list_complete ? undefined : page.cursor;
    } while (cursor);
    return Response.json({ abonnes });
  }
  if (request.method === "POST" && url.pathname === "/admin/evenements") {
    const { evenements = [] } = await request.json();
    for (const e of evenements) await journaliser(env, e.chat, e.type, e);
    return Response.json({ evenements: evenements.length });
  }
  if (request.method === "POST" && url.pathname === "/admin/purge") {
    return Response.json({ purges: await purger(env) });
  }
  if (request.method === "POST" && url.pathname === "/admin/rappels") {
    const { rappels = [] } = await request.json();
    for (const { chat, numero, liste, du } of rappels) {
      await env.KV.put(`rappel:${chat}:${numero}`, "1", {
        metadata: { numero, liste, du: du || new Date().toISOString() },
      });
    }
    return Response.json({ rappels: rappels.length });
  }
  if (request.method === "POST" && url.pathname === "/admin/rappels/envoyer") {
    return Response.json({ envoyes: await envoyerRappels(env, new Date()) });
  }
  const m = url.pathname.match(/^\/admin\/abonnes\/(-?\d+)$/);
  if (request.method === "DELETE" && m) {
    await env.KV.delete(`abonne:${m[1]}`);
    return Response.json({ supprime: m[1] });
  }
  return new Response("inconnu", { status: 404 });
}

/** Efface les personnes inactives depuis la durée de conservation et les en avertit. */
async function purger(env) {
  const { results } = await env.DB.prepare(
    `SELECT chat FROM personnes WHERE derniere_vue < datetime('now', '-${CONSERVATION_MOIS} months')`,
  )
    .bind()
    .all();
  for (const { chat } of results) {
    await env.DB.batch([
      env.DB.prepare("DELETE FROM evenements WHERE utilisateur = ?").bind(chat),
      env.DB.prepare("DELETE FROM personnes WHERE chat = ?").bind(chat),
    ]);
    await env.KV.delete(`abonne:${chat}`);
    await effacerRappels(env, chat);
    await envoyerTexte(
      env,
      chat,
      `Sans nouvelle de votre part depuis ${CONSERVATION_MOIS} mois, vos données ont été effacées et vous ne recevrez plus les listes.\nEnvoyez /start pour revenir.`,
    ).catch(() => {});
  }
  return results.length;
}

/** Appelle l'API Telegram et lève une erreur portant le code renvoyé en cas d'échec. */
async function tg(env, method, payload) {
  const estFormulaire = payload instanceof FormData;
  const api = (env.TELEGRAM_API || "https://api.telegram.org").replace(/\/$/, "");
  const rep = await fetch(`${api}/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: estFormulaire ? undefined : { "content-type": "application/json" },
    body: estFormulaire ? payload : JSON.stringify(payload),
  });
  const json = await rep.json();
  if (!json.ok) {
    const err = new Error(`Telegram ${json.error_code} : ${json.description}`);
    err.code = json.error_code;
    throw err;
  }
  return json.result;
}

/** Envoie un message texte, avec des boutons facultatifs. */
function envoyerTexte(env, chat, texte, boutons) {
  const payload = { chat_id: chat, text: texte, parse_mode: "HTML", disable_web_page_preview: true };
  if (boutons) payload.reply_markup = { inline_keyboard: boutons };
  return tg(env, "sendMessage", payload);
}

/** Envoie l'image d'une affiche ; elle n'est téléversée qu'une fois, puis servie par son file_id. */
async function envoyerAffiche(env, chat, fiche, legende) {
  const nom = fiche.image.split("/").pop();
  const fileId = fiche.file_id || (await env.KV.get(`file:${nom}`));
  if (fileId) {
    return tg(env, "sendPhoto", { chat_id: chat, photo: fileId, caption: legende, parse_mode: "HTML" });
  }
  let image;
  try {
    const rep = await fetch(fiche.image, { headers: { "User-Agent": "Mozilla/5.0" } });
    if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
    image = await rep.blob();
  } catch (e) {
    console.error("image", e.message);
    return envoyerTexte(env, chat, legende, [[{ text: "Voir l'affiche", url: fiche.image }]]);
  }
  const form = new FormData();
  form.append("chat_id", String(chat));
  form.append("caption", legende);
  form.append("parse_mode", "HTML");
  form.append("photo", image, nom);
  const envoye = await tg(env, "sendPhoto", form);
  await env.KV.put(`file:${nom}`, envoye.photo[envoye.photo.length - 1].file_id);
  return envoye;
}

/** Met à jour la fiche d'une personne (identité Telegram), consultable par l'administrateur. */
async function enregistrerPersonne(env, chat, de) {
  if (!env.DB || chat === undefined || chat === null) return;
  try {
    await env.DB.prepare(
      `INSERT INTO personnes (chat, pseudo, prenom, nom, langue, premiere_vue, derniere_vue)
       VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
       ON CONFLICT(chat) DO UPDATE SET
         pseudo = excluded.pseudo, prenom = excluded.prenom, nom = excluded.nom,
         langue = excluded.langue, derniere_vue = datetime('now')`,
    )
      .bind(String(chat), de?.username ?? null, de?.first_name ?? null, de?.last_name ?? null, de?.language_code ?? null)
      .run();
  } catch (e) {
    console.error(JSON.stringify({ evenement: "erreur_personne", message: e.message }));
  }
}

/** Écrit un événement dans les journaux et dans la base de statistiques, sans bloquer la réponse. */
async function journaliser(env, chat, type, details = {}) {
  try {
    const utilisateur = chat === undefined || chat === null ? null : String(chat);
    const ligne = {
      evenement: type,
      utilisateur,
      numero: details.numero ?? null,
      trouve: details.trouve === undefined ? null : Number(details.trouve),
      liste: details.liste ?? null,
      valeur: details.valeur ?? null,
    };
    console.log(JSON.stringify(ligne));
    if (!env.DB) return;
    await env.DB.prepare(
      "INSERT INTO evenements (utilisateur, type, numero, trouve, liste, valeur) VALUES (?, ?, ?, ?, ?, ?)",
    )
      .bind(utilisateur, type, ligne.numero, ligne.trouve, ligne.liste, ligne.valeur)
      .run();
  } catch (e) {
    console.error(JSON.stringify({ evenement: "erreur_journal", message: e.message }));
  }
}

/** Extrait d'un message les numéros complets (2026-61191) ou, à défaut, les numéros sans année. */
export function extraireNumeros(texte) {
  const complets = [...new Set([...texte.matchAll(RE_QUITTANCE)].map((m) => `${m[1]}-${m[2]}`))];
  const courts = complets.length ? [] : [...new Set([...texte.matchAll(RE_COURT)].map((m) => m[1]))];
  return { complets, courts };
}

/** Compte les recherches d'une personne au cours de la dernière heure. */
async function recherchesRecentes(env, chat) {
  if (!env.DB) return 0;
  const ligne = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM evenements WHERE utilisateur = ? AND type = 'recherche' AND date >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 hour')",
  )
    .bind(String(chat))
    .first();
  return ligne?.n || 0;
}

/** Échappe un texte pour l'insérer dans un message HTML. */
export const echapper = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Renvoie le titre nettoyé d'une affiche, par exemple « BEG 2026-066 ». */
export function nomCourt(fiche) {
  const titre = fiche.titre
    .replace(/^Num\S*\s*:\s*/, "")
    .trim()
    .replace(/\s*([-/])\s*/g, "$1")
    .replace(/\s+/g, " ")
    .replace(/^beg\b/i, "BEG");
  return echapper(titre);
}

/** Lit la base et renvoie les affiches qui contiennent des numéros. */
async function lireListes(env) {
  const base = (await env.KV.get("annonces", "json")) || { annonces: [] };
  return base.annonces.filter((f) => f.numeros && f.numeros.length);
}

/** Renvoie les numéros suivis d'un abonné et indique s'il est nouveau. */
async function lireProfil(env, chat) {
  const { value, metadata } = await env.KV.getWithMetadata(`abonne:${chat}`);
  return { nouveau: value === null, suivis: metadata?.suivis || [] };
}

/** Enregistre un abonné et ses numéros suivis. */
function ecrireProfil(env, chat, suivis) {
  return env.KV.put(`abonne:${chat}`, "1", { metadata: { suivis } });
}

/** Extrait le texte d'un message ou d'un clic sur un bouton, puis y répond. */
async function traiterUpdate(update, env) {
  let message;
  let texte;
  if (update.callback_query) {
    message = update.callback_query.message;
    texte = update.callback_query.data || "";
    await tg(env, "answerCallbackQuery", { callback_query_id: update.callback_query.id }).catch(() => {});
  } else {
    message = update.message;
    texte = message?.text || "";
  }
  if (!message || message.chat?.type !== "private") return;
  const chat = message.chat.id;
  const de = update.callback_query ? update.callback_query.from : message.from;
  try {
    await enregistrerPersonne(env, chat, de);
    await repondre(env, chat, texte.trim());
  } catch (e) {
    if (e.code === 403) await env.KV.delete(`abonne:${chat}`);
    else throw e;
  }
}

/** Traite une commande ou une recherche de numéro et envoie la réponse. */
async function repondre(env, chat, texte) {
  const commande = texte ? texte.split(/\s+/)[0].split("@")[0].toLowerCase().replace(/^\//, "") : "";

  if (commande === "stop") {
    await env.KV.delete(`abonne:${chat}`);
    await effacerRappels(env, chat);
    if (env.DB) {
      await env.DB.batch([
        env.DB.prepare("DELETE FROM evenements WHERE utilisateur = ?").bind(String(chat)),
        env.DB.prepare("DELETE FROM personnes WHERE chat = ?").bind(String(chat)),
      ]);
    }
    return envoyerTexte(
      env,
      chat,
      "<b>Désinscription enregistrée</b>\n\n" +
        "Vous ne recevrez plus de messages, et vos numéros suivis comme vos données sont effacés.\n" +
        "Envoyez /start pour revenir.",
    );
  }

  if (commande === "confidentialite" || commande === "confidentialité") {
    return envoyerTexte(env, chat, confidentialite(env.CONTACT));
  }

  const profil = await lireProfil(env, chat);
  if (profil.nouveau) await ecrireProfil(env, chat, []);

  if (commande === "start") {
    await journaliser(env, chat, "demarrage");
    return envoyerTexte(env, chat, ACCUEIL, MENU);
  }
  if (commande === "aide" || commande === "help") {
    await journaliser(env, chat, "aide");
    return envoyerTexte(env, chat, AIDE, MENU);
  }

  if (commande.startsWith("oublier:")) {
    const numero = commande.slice(8);
    if (profil.suivis.includes(numero)) {
      await ecrireProfil(env, chat, profil.suivis.filter((n) => n !== numero));
      await journaliser(env, chat, "suivi_retire", { numero });
    }
    return envoyerTexte(env, chat, `Je ne suis plus le numéro <code>${echapper(numero)}</code>.`);
  }

  const listes = await lireListes(env);
  const publies = new Set(listes.flatMap((f) => f.numeros));

  if (commande === "derniere") {
    if (!listes.length) return envoyerTexte(env, chat, "Aucune liste en mémoire pour le moment.");
    const fiche = listes[listes.length - 1];
    await journaliser(env, chat, "derniere", { liste: nomCourt(fiche) });
    return envoyerAffiche(
      env,
      chat,
      fiche,
      `<b>Dernière liste publiée</b>\n${nomCourt(fiche)} · ${fiche.numeros.length} numéros\n\n${PRUDENCE}`,
    );
  }

  if (commande === "suivis") {
    await journaliser(env, chat, "suivis");
    const suivis = profil.suivis.filter((n) => !publies.has(n));
    if (suivis.length !== profil.suivis.length) await ecrireProfil(env, chat, suivis);
    if (!suivis.length) {
      return envoyerTexte(
        env,
        chat,
        "<b>Vos numéros suivis</b>\n\nAucun pour le moment.\n" +
          "Envoyez un numéro de quittance pas encore publié et je le suivrai pour vous.",
      );
    }
    return envoyerTexte(
      env,
      chat,
      "<b>Vos numéros suivis</b>\n\n" +
        suivis.map((n) => `• <code>${n}</code>`).join("\n") +
        "\n\nJe vous préviens dès que l'un d'eux est publié.",
      suivis.map((n) => [{ text: `Ne plus suivre ${n}`, callback_data: `oublier:${n}` }]),
    );
  }

  const { complets, courts } = extraireNumeros(texte);
  if ((complets.length || courts.length) && (await recherchesRecentes(env, chat)) >= LIMITE_RECHERCHES_HEURE) {
    await journaliser(env, chat, "limite");
    return envoyerTexte(
      env,
      chat,
      "Vous avez fait beaucoup de recherches en peu de temps. Réessayez dans une heure.",
    );
  }
  if (!complets.length && !courts.length) {
    await journaliser(env, chat, "message_autre");
    return envoyerTexte(env, chat, profil.nouveau ? ACCUEIL : AIDE, MENU);
  }

  let suivis = profil.suivis;
  for (const demande of [...complets, ...courts].slice(0, SUIVIS_MAX)) {
    const estCourt = courts.includes(demande);
    const trouvees = [];
    for (const fiche of listes) {
      for (const num of fiche.numeros) {
        if (num === demande || (estCourt && num.endsWith(`-${demande}`))) trouvees.push({ num, fiche });
      }
    }

    if (trouvees.length) {
      const { num, fiche } = trouvees[trouvees.length - 1];
      let legende = `✅ <b>${num} est publié</b>\nListe ${nomCourt(fiche)}\n\n`;
      if (trouvees.length > 1) {
        legende += `Ce numéro apparaît dans ${trouvees.length} listes, voici la plus récente.\n\n`;
      }
      legende += PRUDENCE;
      await journaliser(env, chat, "recherche", { numero: num, trouve: true, liste: nomCourt(fiche) });
      if (suivis.includes(num)) {
        suivis = suivis.filter((n) => n !== num);
        await ecrireProfil(env, chat, suivis);
      }
      await envoyerAffiche(env, chat, fiche, legende);
      continue;
    }

    await journaliser(env, chat, "recherche", { numero: demande, trouve: false });
    let reponse = `❌ <b>${demande} n'est pas encore publié</b>\n${listes.length} listes vérifiées`;
    if (listes.length) reponse += `, la plus récente : ${nomCourt(listes[listes.length - 1])}`;
    reponse += ".\n\n";
    if (estCourt) {
      reponse += "Pour que je le suive, envoyez le numéro complet avec l'année, par exemple <code>2026-61191</code>.";
    } else if (suivis.includes(demande)) {
      reponse += "🔔 Je le suis déjà et je vous préviens dès qu'il est publié.";
    } else if (suivis.length >= SUIVIS_MAX) {
      reponse += `Vous suivez déjà ${SUIVIS_MAX} numéros. Retirez-en un avec /suivis pour suivre celui-ci.`;
    } else {
      suivis = [...suivis, demande];
      await ecrireProfil(env, chat, suivis);
      await journaliser(env, chat, "suivi_ajoute", { numero: demande });
      reponse += "🔔 Je le garde en mémoire et je vous préviens dès qu'il est publié.";
    }
    reponse +=
      "\n\n<i>La lecture automatique peut manquer un numéro. En cas de doute, consultez les listes officielles.</i>";
    await envoyerTexte(env, chat, reponse, [[B_OFFICIEL]]);
  }
}
