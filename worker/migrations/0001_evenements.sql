CREATE TABLE evenements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  utilisateur TEXT,
  type TEXT NOT NULL,
  numero TEXT,
  trouve INTEGER,
  liste TEXT,
  valeur INTEGER
);

CREATE INDEX evenements_date ON evenements (date);
CREATE INDEX evenements_type ON evenements (type, date);
CREATE INDEX evenements_utilisateur ON evenements (utilisateur);
