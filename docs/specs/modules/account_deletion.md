---
entity_id: account_deletion
type: module
created: 2026-04-16
updated: 2026-09-09
status: draft
version: "1.0"
tags: [go, auth, account-deletion, f15]
---

# F15 Phase 3 — Account Deletion

## Approval

- [ ] Approved

## Purpose

Eingeloggte User koennen ihren Account loeschen. Alle User-Daten werden kaskadierend entfernt (locations, trips, subscriptions, gpx, snapshots, user.json). **Seit #2129/ADR-0060:** Da `data/users/{id}/sessions.json` Teil des geloeschten Verzeichnisses ist, werden damit alle Anmeldungen des Nutzers auf allen Geraeten ungueltig, nicht nur die des loeschenden Geraets — davor blacklistete der Logout-Pfad nur die eine aktuelle Session.

**Seit #2270:** Es gibt eine lesende Gegenrichtung — `GET /api/auth/export` liefert dem Nutzer denselben Datenbaum als ZIP zum Herunterladen, abzueglich einer begruendeten Ausnahmeliste (Geheimnisse, Betriebsdaten). Details: `docs/specs/modules/user_data_export.md`.

## Scope

### In Scope

- `DELETE /api/auth/account` — Account + alle Daten loeschen
- `internal/store/user.go` — `DeleteUser(id)` Methode
- `internal/handler/auth.go` — `DeleteAccountHandler`
- `cmd/server/main.go` — Route

### Out of Scope

- Bestaetigungs-UI im Frontend (kommt mit Account-Seite)
- Soft-Delete / Backup vor Loeschung
- Admin-seitige User-Loeschung

## Implementation Details

### Step 1: DeleteUser Store-Methode (`internal/store/user.go`, +10 LoC)

```go
func (s *Store) DeleteUser(id string) error {
    dir := s.UserDir(id)
    return os.RemoveAll(dir)
}
```

Loescht das gesamte Verzeichnis `data/users/{id}/` rekursiv — inklusive locations, trips, gpx, snapshots, user.json, password_reset.json, etc.

### Step 2: DeleteAccountHandler (`internal/handler/auth.go`, +25 LoC)

```go
func DeleteAccountHandler(s *store.Store) http.HandlerFunc
```

1. `userId := middleware.UserIDFromContext(r.Context())`
2. `s.LoadUser(userId)` → 404 falls nicht gefunden
3. `s.DeleteUser(userId)` → 500 bei Fehler
4. Cookie des anfragenden Geraets loeschen — die Sitzungsliste selbst ist mit dem Verzeichnis aus Schritt 3 bereits weg (seit #2129/ADR-0060; zuvor: Session blacklisten wie Logout, nur das eine Geraet)
5. HTTP 200 `{"status":"deleted"}`

### Step 3: Route (`cmd/server/main.go`, +1 LoC)

```go
r.Delete("/api/auth/account", handler.DeleteAccountHandler(s))
```

NICHT exempt von AuthMiddleware — nur eingeloggte User koennen ihren Account loeschen.

## Expected Behavior

- **Eingeloggt + DELETE /api/auth/account:** Account + alle Daten geloescht, alle Sessions auf allen Geraeten invalidiert (seit #2129/ADR-0060), Cookie des anfragenden Geraets geloescht
- **Nicht eingeloggt:** 401 Unauthorized (durch Middleware)
- **Nach Loeschung:** Login mit alten Credentials schlaegt fehl (User existiert nicht mehr)

## Known Limitations

- Kein Soft-Delete — Daten sind unwiderruflich weg
- Keine Bestaetigungsabfrage auf API-Ebene (Frontend muss Confirmation-Dialog zeigen)
- Seed-User kann sich selbst loeschen (wird beim naechsten Restart neu erstellt falls AUTH_PASS gesetzt)

## Changelog

- 2026-04-16: Initial spec (F15 Phase 3 — Account Deletion, GitHub Issue #53)
- 2026-09-06: Session-Invalidierung durch #2129 (ADR-0060) auf alle Geraete ausgeweitet — Details dort, nicht hier nachpflegen.
- 2026-09-09: Querverweis auf #2270 (Datenexport, lesende Gegenrichtung) ergaenzt — Details dort, nicht hier nachpflegen.
