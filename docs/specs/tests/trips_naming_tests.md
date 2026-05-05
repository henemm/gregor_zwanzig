---
entity_id: trips_naming_tests
type: tests
created: 2026-05-05
updated: 2026-05-05
status: draft
version: "1.0"
tags: [tests, frontend, naming, ui, issue-126]
---

# Tests: Trips-Naming in Sidebar + Startseite (Issue #126)

## Approval

- [x] Approved

## Purpose

TDD-Tests für die Vereinheitlichung der UI-Begriffe ("Tour"/"Touren" →
"Trip"/"Trips") in Sidebar und Startseite. Validiert per echter HTTP-Request
gegen den deployed Frontend-Server, dass die alten Bezeichnungen entfernt
und die neuen vorhanden sind.

## Source

- **File:** `tests/tdd/test_trips_naming.py`
- **Identifier:** Funktionen mit Prefix `test_*`

## Bezug

- Bug-Spec: `docs/specs/bugfix/trips_naming_sidebar_homepage.md`
- GitHub Issue #126

## Test-Strategie

- **Real HTTP, no mocks** — laut CLAUDE.md gegen echten Frontend-Server.
- **Authentifiziert** — Sidebar und Startseite werden nur für eingeloggte User
  korrekt gerendert; Tests loggen via `/api/auth/login` ein und nutzen das
  Session-Cookie für die HTML-Requests.
- **Default-Target Staging**, via `GZ_TEST_BASE_URL` überschreibbar.
- **Credentials** via `GZ_TEST_USER` / `GZ_TEST_PASS` Env-Vars.

## Covered Test Functions

- `sidebar_uses_trips_label`
- `homepage_uses_trip_terminology`

### `sidebar_uses_trips_label`

- **Given:** Authentifizierte Session gegen deployed Frontend
- **When:** GET `/` und Lesen des HTML
- **Then:** Sidebar enthält "Meine Trips", nicht mehr "Meine Touren"
- **TDD-Phase:** RED vor Fix (Sidebar-Label noch "Meine Touren"), GREEN nach Implementierung in `+layout.svelte:81`.

### `homepage_uses_trip_terminology`

- **Given:** Authentifizierte Session gegen deployed Frontend
- **When:** GET `/` und Lesen des HTML
- **Then:**
  - Negativ: keiner der Strings "Erste Tour anlegen", "Neue Tour", "deine erste Tour" im HTML
  - Positiv: mindestens einer der Strings "Ersten Trip anlegen", "Neuer Trip", "Meine Trips" im HTML
- **TDD-Phase:** RED vor Fix (mind. eines der alten Strings ist drin), GREEN nach Implementierung in `+page.svelte`.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `httpx` | Library | HTTP-Client mit Cookie-Persistenz |
| `pytest` | Library | Test-Runner |
| `GZ_TEST_BASE_URL` | Env-Var | Default `https://staging.gregor20.henemm.com` |
| `GZ_TEST_USER` / `GZ_TEST_PASS` | Env-Vars | Test-User-Credentials für `/api/auth/login` |

## Expected Behavior

### Vor dem Fix (RED)
- Beide Tests schlagen fehl: HTML enthält "Meine Touren", "Erste Tour anlegen" etc.

### Nach dem Fix (GREEN)
- Beide Tests grün.

## Known Limitations

- **Auth-Voraussetzung:** Tests benötigen eingeloggten User. Wenn `GZ_TEST_PASS`
  nicht gesetzt ist, schlagen Tests mit klarer Fehlermeldung fehl (kein
  silent-skip).
- **HTML-Substring-Match:** Tests prüfen reine Zeichenketten — bei späteren
  Übersetzungs-/i18n-Refactors müssen sie angepasst werden.

## Changelog

- 2026-05-05: Initial spec für Test-Funktionen rund um Issue #126.
