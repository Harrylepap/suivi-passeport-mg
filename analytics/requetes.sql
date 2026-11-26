-- Recherches par jour, trouvées et non trouvées
SELECT date(date) AS jour,
       COUNT(*) AS recherches,
       SUM(trouve) AS trouvees,
       COUNT(*) - SUM(trouve) AS non_trouvees
FROM evenements
WHERE type = 'recherche'
GROUP BY jour
ORDER BY jour DESC;

-- Utilisateurs actifs par jour
SELECT date(date) AS jour, COUNT(DISTINCT utilisateur) AS utilisateurs
FROM evenements
WHERE utilisateur IS NOT NULL
GROUP BY jour
ORDER BY jour DESC;

-- Ce que chaque utilisateur a cherché
SELECT utilisateur, numero, trouve, liste, date
FROM evenements
WHERE type = 'recherche'
ORDER BY utilisateur, date;

-- Fiche par personne : identité et numéros cherchés, avec date de publication
SELECT p.chat,
       p.prenom,
       p.nom,
       p.pseudo,
       e.numero,
       MIN(e.date) AS premiere_recherche,
       MAX(CASE WHEN e.trouve = 1 THEN e.date END) AS publie
FROM personnes p
LEFT JOIN evenements e ON e.utilisateur = p.chat AND e.type = 'recherche'
GROUP BY p.chat, e.numero
ORDER BY p.derniere_vue DESC, premiere_recherche;

-- Numéros les plus recherchés
SELECT numero, COUNT(*) AS recherches, COUNT(DISTINCT utilisateur) AS utilisateurs, MAX(trouve) AS publie
FROM evenements
WHERE type = 'recherche'
GROUP BY numero
ORDER BY recherches DESC
LIMIT 50;

-- Délai entre la première recherche d'un numéro et l'alerte de publication
SELECT a.numero,
       MIN(r.date) AS premiere_recherche,
       a.date AS alerte,
       ROUND(julianday(a.date) - julianday(MIN(r.date)), 1) AS jours_d_attente
FROM evenements a
JOIN evenements r ON r.numero = a.numero AND r.type = 'recherche'
WHERE a.type = 'alerte_suivi'
GROUP BY a.id
ORDER BY a.date DESC;

-- Arrivées et désinscriptions par semaine
SELECT strftime('%Y-%W', date) AS semaine,
       SUM(type = 'demarrage') AS arrivees,
       SUM(type = 'desinscription') AS desinscriptions
FROM evenements
GROUP BY semaine
ORDER BY semaine DESC;

-- Répartition des actions
SELECT type, COUNT(*) AS nombre
FROM evenements
GROUP BY type
ORDER BY nombre DESC;

-- Heures d'utilisation, heure de Paris en hiver
SELECT strftime('%H', date, '+1 hour') AS heure, COUNT(*) AS actions
FROM evenements
WHERE utilisateur IS NOT NULL
GROUP BY heure
ORDER BY heure;

-- Portée de chaque diffusion
SELECT date, liste, valeur AS abonnes
FROM evenements
WHERE type = 'diffusion'
ORDER BY date DESC;
