CREATE TABLE personnes (
  chat TEXT PRIMARY KEY,
  pseudo TEXT,
  prenom TEXT,
  nom TEXT,
  langue TEXT,
  premiere_vue TEXT,
  derniere_vue TEXT
);

CREATE INDEX personnes_derniere_vue ON personnes (derniere_vue);
