---
entity_id: fix_1517_validator_register_order
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [auth, go-api, bugfix]
---

# RegisterHandler — Existenzprüfung vor E-Mail-Pflichtprüfung

## Approval

- [ ] Approved

## Purpose

`RegisterHandler` prüft aktuell das seit #1226 pflichtige `email`-Feld VOR der
Existenzprüfung des Usernamens (`s.UserExists`). Ein idempotenter Register-Aufruf
ohne `email` gegen einen bereits existierenden Nutzer liefert dadurch fälschlich
`400 "validation failed"` statt `409 "user already exists"`. Das bricht
`scripts/setup-validator-user.sh` (sendet nie ein `email`-Feld) und war Ursache
dafür, dass der Staging-Validator-Nutzer ohne `password_hash` blieb (#1517).

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `RegisterHandler`

## Estimated Scope

- **LoC:** ~10 (Produktivcode, reine Umstellung) + ~25 (Test)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.Store.UserExists` | Go-Methode | Existenzprüfung des Usernamens — unverändert, wird nur früher im Ablauf aufgerufen |

## Implementation Details

In `RegisterHandler` (`internal/handler/auth.go`) den Block

```go
if s.UserExists(req.Username) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(409)
    w.Write([]byte(`{"error":"user already exists"}`))
    return
}
```

(aktuell nach der E-Mail-Prüfung, Zeile 77-82) VOR den Block

```go
if req.Email == "" {
    ...
}
if !strings.Contains(req.Email, "@") {
    ...
}
```

(aktuell Zeile 64-75) ziehen.

Die Reihenfolge der reinen Format-Validierungen (Username-Länge Zeile 40-45,
Username-Regex Zeile 46-51, Passwort-Länge Zeile 52-57) bleibt **unverändert vor**
`s.UserExists` — nur die E-Mail-Pflichtprüfung wandert hinter die Existenzprüfung.
Kein Eingriff an `dispatchVerificationMail`, `s.SaveUser`, `s.ProvisionUserDirs`.

Resultierende Reihenfolge in `RegisterHandler`:
1. JSON-Decode
2. Username-Länge (400)
3. Username-Regex (400)
4. Passwort-Länge (400)
5. **`s.UserExists` (409)** ← vorgezogen
6. E-Mail leer (400)
7. E-Mail-Format (400 `invalid_email`)
8. bcrypt, SaveUser, ProvisionUserDirs, dispatchVerificationMail, 201

## Expected Behavior

- **Input:** `POST /api/auth/register` mit `username`, `password`, optional `email`
- **Output:** Bei existierendem Username **409** unabhängig davon, ob `email`
  gesetzt ist. Bei neuem Username ohne `email` weiterhin **400
  "validation failed"**. Bei neuem Username mit ungültigem Username/Passwort
  weiterhin **400** (Reihenfolge davor unverändert).
- **Side effects:** Keine neuen. Kein Konto wird bei 409 oder 400 angelegt (wie
  zuvor).

## Acceptance Criteria

- **AC-1:** Given ein Username existiert bereits im Store / When `POST
  /api/auth/register` mit diesem Username und **ohne** `email`-Feld aufgerufen
  wird / Then antwortet der Handler mit **409 "user already exists"** (nicht 400).
  - Test: Neuer Test in `internal/handler/auth_test.go` — Store mit existierendem
    User vorbereiten (analog `TestRegisterHandlerDuplicateUser`), Request-Body
    ohne `email`-Feld senden, `w.Code == 409` und Fehlertext `"user already
    exists"` prüfen. Dies ist der Kern-Regressionstest für den Bug aus #1517
    (rot vor dem Fix, grün danach).

- **AC-2:** Given ein Username existiert bereits im Store / When `POST
  /api/auth/register` mit diesem Username und **gesetztem** `email`-Feld
  aufgerufen wird / Then antwortet der Handler weiterhin mit **409 "user
  already exists"**.
  - Test: Bestehender Test `TestRegisterHandlerDuplicateUser`
    (`internal/handler/auth_test.go:82`) bleibt unverändert grün — belegt, dass
    der Fix das bestehende Duplikat-Verhalten mit E-Mail nicht verändert.

- **AC-3:** Given ein Username existiert **nicht** im Store / When `POST
  /api/auth/register` mit diesem (neuen) Username und **ohne** `email`-Feld
  aufgerufen wird / Then antwortet der Handler weiterhin mit **400 "validation
  failed"**.
  - Test: Bestehender Test `TestRegisterHandler_MissingEmail_AC1`
    (`internal/handler/auth_test.go:136`) bleibt unverändert grün — belegt, dass
    die E-Mail-Pflichtprüfung für neue User (#1226) durch das Vorziehen von
    `s.UserExists` nicht ausgehebelt wird.

- **AC-4:** Given ein Username existiert **nicht** im Store / When `POST
  /api/auth/register` mit zu kurzem Username (< 3 Zeichen) oder zu kurzem
  Passwort (< 8 Zeichen) aufgerufen wird / Then antwortet der Handler weiterhin
  mit **400** (nicht 409, nicht 500).
  - Test: Bestehende Tests `TestRegisterHandlerShortUsername`
    (`internal/handler/auth_test.go:103`) und `TestRegisterHandlerShortPassword`
    (`internal/handler/auth_test.go:117`) bleiben unverändert grün — belegt,
    dass die Reihenfolge der Format-Validierungen VOR `s.UserExists` nicht
    angetastet wurde.

## Known Limitations

- **User-Enumeration:** Die Existenzprüfung liegt jetzt vor der E-Mail-Pflicht-
  prüfung — ein Angreifer kann durch Weglassen von `email` herausfinden, ob ein
  Username existiert (409 statt 400), ohne eine gültige E-Mail angeben zu
  müssen. Das ist kein neues Informationsleck gegenüber dem Status quo: bei
  vollständigen, formal gültigen Requests war der 409 bei Duplikat schon vorher
  sichtbar. Username-Länge/-Regex und Passwort-Länge bleiben unverändert VOR der
  Existenzprüfung, dort ändert sich am Enumeration-Verhalten nichts.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine lokale Reihenfolgeänderung innerhalb eines bestehenden
  Handlers, kein neues Datenmodell, kein neuer Kanal, keine neue Abhängigkeit —
  berührt keine der in `docs/adr/README.md` gelisteten Entscheidungsflächen.

## Changelog

- 2026-08-09: Initial spec created
