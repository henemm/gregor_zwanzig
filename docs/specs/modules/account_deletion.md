---
entity_id: account_deletion
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [go, auth, account-deletion, f15]
---

# F15 Phase 3 — Account Deletion

## Approval

- [ ] Approved

## Purpose

Eingeloggte User koennen ihren Account loeschen. Alle User-Daten werden kaskadierend entfernt (locations, trips, subscriptions, gpx, snapshots, user.json). Session wird blacklisted und Cookie geloescht.

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
4. Session blacklisten + Cookie loeschen (wie Logout)
5. HTTP 200 `{"status":"deleted"}`

### Step 3: Route (`cmd/server/main.go`, +1 LoC)

```go
r.Delete("/api/auth/account", handler.DeleteAccountHandler(s))
```

NICHT exempt von AuthMiddleware — nur eingeloggte User koennen ihren Account loeschen.

## Expected Behavior

- **Eingeloggt + DELETE /api/auth/account:** Account + alle Daten geloescht, Session invalidiert, Cookie geloescht
- **Nicht eingeloggt:** 401 Unauthorized (durch Middleware)
- **Nach Loeschung:** Login mit alten Credentials schlaegt fehl (User existiert nicht mehr)

## Known Limitations

- Kein Soft-Delete — Daten sind unwiderruflich weg
- Keine Bestaetigungsabfrage auf API-Ebene (Frontend muss Confirmation-Dialog zeigen)
- Seed-User kann sich selbst loeschen (wird beim naechsten Restart neu erstellt falls AUTH_PASS gesetzt)

## Changelog

- 2026-04-16: Initial spec (F15 Phase 3 — Account Deletion, GitHub Issue #53)
