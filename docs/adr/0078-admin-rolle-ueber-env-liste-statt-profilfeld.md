# ADR-0078: Die Admin-Rolle wird über die Umgebungsvariable `GZ_ADMIN_USER_IDS` bestimmt, nicht über ein Profilfeld

- **Status:** Akzeptiert
- **Datum:** 2026-09-28
- **Bezug:** GitHub-Issue #2155 (Scheibe S1, Epic #2138), Spec `docs/specs/modules/admin_rolle_s1.md`

## Kontext

Gregor Zwanzig ist mandantenfähig, kennt aber keine Rollen. Betriebs-Endpunkte
(`POST /api/scheduler/trip-reports|alert-checks|inbound-commands`) sind für jeden
angemeldeten Nutzer erreichbar; Tier-Freigaben laufen von Hand in der `user.json`. Für die
Absicherung dieser Endpunkte und die spätere Admin-Oberfläche (Scheiben S2 bis S4) braucht es
einen Admin-Begriff. Offen war, **wo** er gespeichert wird: als Profilfeld `role` am
Nutzerobjekt oder außerhalb der Nutzerdaten.

## Entscheidung

1. **Admin ist, wessen Nutzerkennung in `GZ_ADMIN_USER_IDS` steht.** Komma-getrennte Liste;
   Leerzeichen und leere Einträge fallen weg (Muster `splitOrigins`,
   `internal/config/webauthn.go`). Vergleich exakt, keine Teilstring-Treffer.
2. **Fail-closed.** Leere oder fehlende Variable ⇒ niemand ist Admin.
3. **Kein Profilfeld `role` im Speicher.** `model.User` bekommt kein solches Feld.
   `GET /api/auth/profile` liefert ein **abgeleitetes** `role: "admin"|"user"`, berechnet aus
   der ENV-Liste; `PUT /api/auth/profile` ignoriert ein mitgesendetes `role`.
4. **Durchsetzung über die Middleware `RequireAdmin`** (`internal/middleware`), pro Route
   angewandt (der Router kennt keine Gruppen). Nicht-Admin ⇒ HTTP 403 `{"error":"forbidden"}`;
   „nicht angemeldet" bleibt 401 durch die globale Kette.
5. **Adminvergabe ist Betreiber-Aufgabe** (`.env` + Neustart). Spätere Scheiben (S3
   Admin-API) ändern die Liste nicht.

## Verworfene Alternativen

- **Profilfeld `role` in `user.json`.** Verworfen aus drei Gründen: (a) Das Feld läge im per
  `PUT /api/auth/profile` erreichbaren Nutzerobjekt — jeder Nutzer könnte sich selbst zum Admin
  machen, sobald ein Update-Pfad das Feld durchreicht (Rechteausweitung); (b) die Roh-Merge-
  Falle: Update-Pfade, die das Nutzerobjekt als Ganzes ersetzen oder unbekannte Felder
  mitschreiben, könnten das Feld ungewollt setzen oder verlieren; (c) es wäre eine
  Daten-Schema-Änderung mit Migrationspflicht für Bestandsdaten (BUG-DATALOSS-GR221).

## Konsequenzen

- Keine Datenmigration, keine Änderung an `model.User`, kein neuer Schreibpfad.
- Eine falsch oder gar nicht gesetzte Liste sperrt die geschützten Routen für alle — sicher
  (fail-closed), aber die Kennung muss vor dem Rollout in Prod- und Staging-`.env` eingetragen
  werden. Änderungen an der Liste wirken erst nach einem Neustart der Go-API.
- Die Rolle ist pro Anfrage aus Konfiguration ableitbar; sie kann von keinem Nutzer und von
  keiner API verändert werden.
- Der Cron-Betrieb ist unberührt: Der Go-Scheduler ruft den Python-Core direkt, nicht über den
  Router.
