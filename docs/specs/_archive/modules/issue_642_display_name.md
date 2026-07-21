---
entity_id: issue_642_display_name
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [auth, profile, user, frontend, go-api]
---

# User-Anzeigename (Issue #642)

## Approval

- [x] Approved

## Purpose

Ein Nutzer kann seinen **angezeigten Namen** frei ändern. Der technische Login-Name (`User.ID`) bleibt unverändert als unveränderlicher Auth- und Speicher-Schlüssel — der Anzeigename ist davon entkoppelt und wird überall dort gezeigt, wo heute der Login-Name erscheint.

## Source

- **File:** `internal/model/user.go` — `User`-Struct (neues Feld `DisplayName`)
- **File:** `internal/handler/auth.go` — `profileResponse`, `GetProfileHandler`, `UpdateProfileHandler`
- **File:** `frontend/src/routes/account/+page.svelte` — Anzeigename-Eingabe + Speichern
- **File:** `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` — Anzeige `display_name || id`

## Estimated Scope

- **LoC:** ~120
- **Files:** 5-6 (Go: model + handler; Frontend: account page, account +page.server.ts, Sidebar, layout)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Session-Auth (`hooks.server.ts`, `verifySession`) | upstream | liefert echte `user_id` |
| Store (`internal/store/user.go`) | upstream | `LoadUser`/`SaveUser` (Merge, kein Replace) |

## Implementation Details

```
Backend (Go):
- User-Struct: neues optionales Feld `DisplayName string json:"display_name,omitempty"`
- GET /api/auth/profile: profileResponse erhält `display_name`
- PUT /api/auth/profile: Update-Struct erhält `DisplayName *string json:"display_name"`
  - Read-Modify-Write: bestehenden User laden, NUR display_name (und bisherige Felder) ändern, Rest erhalten
  - Validierung: trim; max 50 Zeichen; keine Steuerzeichen/Zeilenumbrüche
  - Leer/nur-Whitespace nach Trim → display_name wird gelöscht (Fallback auf id)
  - user_id KOMMER aus Auth-Kontext (Session), niemals "default"

Frontend:
- Account-Profil-Card: Eingabefeld "Anzeigename" (vorbelegt mit display_name, Platzhalter = id)
  - Login-Name (id) bleibt als read-only "Benutzername" sichtbar
  - save() sendet display_name zusätzlich an PUT /api/auth/profile
- Sidebar + überall wo der Name steht: zeige `display_name || id`
- +page.server.ts / layout: display_name aus Profil durchreichen
```

## Expected Behavior

- **Input:** Nutzer tippt im Account einen Anzeigenamen ein und speichert.
- **Output:** Anzeigename wird persistiert; nach Reload zeigen Account-Card UND Seitenleiste den neuen Namen.
- **Side effects:** Login-Name (`User.ID`), Speicherpfad und Session bleiben unverändert. Leerer Anzeigename → Fallback auf Login-Name.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer ohne gesetzten Anzeigenamen / When er die Account-Seite öffnet / Then sieht er ein editierbares Feld "Anzeigename" (leer/Platzhalter) und daneben weiterhin seinen Login-Namen read-only.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Feld vorhanden + editierbar, Login-Name unverändert sichtbar.
- **AC-2:** Given ein eingeloggter Nutzer / When er einen Anzeigenamen eingibt und speichert / Then antwortet `PUT /api/auth/profile` mit 200 und ein anschließendes `GET /api/auth/profile` liefert den neuen `display_name`.
  - Test: echter HTTP-Roundtrip (PUT dann GET) gegen laufenden Server, Antwort enthält den gesetzten Wert.
- **AC-3:** Given ein Nutzer hat einen Anzeigenamen gesetzt / When er die App neu lädt / Then zeigt die Seitenleiste (Fußzeile/Avatar-Initial) den Anzeigenamen statt des Login-Namens.
  - Test: Playwright-E2E — Sidebar-Text == Anzeigename nach Reload.
- **AC-4:** Given ein Nutzer mit gesetztem Anzeigenamen / When er das Feld leert und speichert / Then wird der Anzeigename entfernt und überall fällt die Anzeige auf den Login-Namen zurück.
  - Test: HTTP-Roundtrip — nach PUT mit leerem display_name liefert GET keinen/leeren display_name; UI zeigt id.
- **AC-5:** Given zwei verschiedene Nutzer A und B / When A seinen Anzeigenamen ändert / Then bleibt Bs Anzeigename und Profil unverändert (Mandantentrennung, kein "default"-Fallback).
  - Test: HTTP-Roundtrip mit zwei echten Sessions — A ändert, B unverändert; A behält nur seine Änderung.
- **AC-6:** Given ein Nutzer / When er einen überlangen (>50 Zeichen) oder Steuerzeichen enthaltenden Anzeigenamen sendet / Then wird er abgewiesen oder sauber getrimmt/normalisiert (kein 500, keine Persistenz von Zeilenumbrüchen).
  - Test: echter HTTP-Call mit Grenzwert-Eingabe; Antwort definiert (4xx oder normalisiert), GET zeigt kein kaputtes Feld.
- **AC-7:** Given ein Bestands-Nutzer ohne `display_name`-Feld in `user.json` / When sein Profil geladen und ein anderes Feld (z.B. mail_to) geändert wird / Then bleiben alle bestehenden Felder erhalten (Read-Modify-Write-Merge, kein Datenverlust).
  - Test: Profil mit vorhandenen Feldern laden, mail_to per PUT ändern, GET zeigt alle alten Felder unverändert + neues mail_to.
