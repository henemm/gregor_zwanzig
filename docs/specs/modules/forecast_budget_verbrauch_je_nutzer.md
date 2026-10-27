---
entity_id: forecast_budget_verbrauch_je_nutzer
type: module
created: 2026-10-01
updated: 2026-10-01
status: draft
version: "1.0"
tags: [multi-user, forecast-budget, admin, observability, epic-2150, epic-2138]
workflow: feat-2475-verbrauch-je-nutzer
---

# Forecast Budget: Verbrauch je Nutzer sichtbar

## Approval

- [ ] Approved

## Purpose

Seit #2387 zählt das Open-Meteo-Gate die Abrufe je Nutzer (`data/users/<uid>/diagnostics/forecast_budget.json`), aber niemand kann diese Zahl sehen. Diese Scheibe (S4 von #2150, Issue #2475, Grundlage für #1702) macht den Verbrauch sichtbar: anonyme Kennzahlen im Scheduler-Status für das Monitoring, die Zahl je Nutzer nur für Administratoren in der Admin-Liste und der Admin-Seite.

## Source

- **File:** `internal/scheduler/forecast_budget_health.go`
- **Identifier:** `forecastBudgetSnapshot`, neu `userForecastCalls`, `forecastBudgetAnonymousStats`

Betroffene Schichten:

- **Go-API** (nur lesend): `internal/scheduler/`, `internal/handler/admin_users.go`
- **Frontend**: `frontend/src/routes/admin/+page.svelte`
- **Python-Core**: unverändert. Python bleibt die einzige Entscheidungsstelle für Fair-Share und Drosselung; Go zeigt nur Rohwerte.

## Abweichung vom Ticket-Wortlaut (PO-Abnahme erforderlich)

Das Ticket verlangt den Verbrauch „im Scheduler-Status sichtbar". Das wird bewusst nur teilweise so umgesetzt:

- **Status-Endpunkt `/api/scheduler/status`** zeigt ausschließlich **anonyme** Kennzahlen (Anzahl, fairer Anteil, größter Anteil als Zahl, Anzahl über dem Anteil). Keine Nutzerkennung, keine Zuordnung Zahl zu Person.
- **Der Bezug Nutzer zu Zahl** steht nur im Admin-API `GET /api/admin/users` und in der Admin-Seite, beide hinter Administrator-Anmeldung.

Begründung: Der Status-Endpunkt ist ein Maschinen- und Monitoring-Endpunkt (`check-gregor20.sh`, BetterStack); sein Token liegt in Skripten. Die Prämisse „ohne Anmeldung erreichbar" aus ADR-0075 Punkt 5 ist seit #2155 S2 überholt, der Kreis der Leser ist aber weiterhin größer als der der Administratoren. ADR-0075 Punkt 5 wird deshalb präzisiert, nicht abgelöst: Kennungen nie im Status-Endpunkt; Verbrauch je Nutzer nur hinter Admin-Auth. Der Schutztest `forecast_budget_user_privacy_test.go` bleibt unverändert und grün. Henning bestätigt mit der Freigabe dieser Spec, dass diese Aufteilung das Ticketziel erfüllt.

## Estimated Scope

- **LoC:** ca. +150/-5 (Go-Produktivcode ca. 70, Frontend ca. 15, Tests ca. 70; Doku zählt nicht)
- **Files:** 9
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0075 | ADR | Punkt 5 wird präzisiert (Kennungen nie im Status; Verbrauch je Nutzer nur hinter Admin-Auth) |
| ADR-0003 (Mandantentrennung) | ADR | Je Nutzer die richtige Zahl, Zwei-Nutzer-Test Pflicht |
| `docs/specs/modules/forecast_budget_je_nutzer.md` | Spec | Vorgänger #2387; Schreibformat der Nutzerdatei (unverändert) |
| `docs/specs/modules/admin_rolle_s3_admin_api.md` | Spec | Vertrag `AdminUser`-DTO: kein `omitempty`, alle Felder immer da |
| `docs/specs/modules/admin_ui_s4.md` | Spec | Admin-Seite, in die die Spalte eingefügt wird |
| `src/services/forecast_budget.py` | Modul | Schreibt die Zähler (nicht ändern); Format `{"date","calls":{"openmeteo":N},"active_users":[...]}` |
| `store.ValidUserID` | Funktion | Pflicht-Prüfung der Nutzer-ID vor jedem Dateizugriff (Path-Traversal) |
| `internal/scheduler/briefing_health.go` | Modul | Muster für Lesen von `users/*/diagnostics/…` |
| `check-gregor20.sh` (henemm-infra) | Skript | Liest den Block `forecast_budget`; nur additive Felder erlaubt |
| `internal/scheduler/forecast_budget_user_privacy_test.go` | Test | Schutztest, bleibt unverändert grün |

## Implementation Details

**1. Anonyme Kennzahlen im Status (B).** `forecastBudgetSnapshot` bekommt vier zusätzliche Felder, alle immer vorhanden (auch im Zustand `unavailable`, dort mit 0):

- `active_pots`: Anzahl aktiver Nutzertöpfe heute (Länge von `active_users` der globalen Datei, nur die Zahl).
- `fair_share`: `daily_budget / max(active_pots, 1)`, reine Anzeige.
- `max_user_calls`: höchster heutiger Nutzerwert als Zahl.
- `users_over_fair_share`: Anzahl Nutzer mit Wert über `fair_share`.

Die Feldnamen enthalten bewusst nicht den Namen `active_users`. Die Antwort enthält nie eine Kennung. Die Rechnung dient nur der Anzeige; ob gedrosselt wird, entscheidet weiterhin allein `ForecastBudgetGate.allow()` in Python. `internal/scheduler/scheduler.go` (Status-Block `forecast_budget`, ca. Zeile 1227) reicht die neuen Felder additiv durch.

**2. Lesefunktion je Nutzer (C).** Neu `userForecastCalls(dataDir, uid string) int`: prüft `store.ValidUserID(uid)`, liest `<dataDir>/users/<uid>/diagnostics/forecast_budget.json` und liefert `calls["openmeteo"]`, wenn `date` das heutige UTC-Datum ist. Datei fehlt, ist kaputt oder hat ein altes Datum: Ergebnis 0, kein Fehler, kein Schreibzugriff. Die anonymen Kennzahlen (1.) nutzen dieselbe Funktion über alle Nutzerverzeichnisse (Muster `Glob users/*/diagnostics/…`), geben aber nur Aggregate aus.

**3. Admin-API (C).** `AdminUser` in `internal/handler/admin_users.go` bekommt das Feld `open_meteo_calls_today` (int, ohne `omitempty`). `adminUserDTO` füllt es über den Scheduler-Zugriff aus (2.). Liste und Einzelantwort (`adminRespondUser`) tragen es gleichermaßen. Der Zugriff bleibt hinter `requireAdmin`.

**4. Admin-Seite.** `frontend/src/routes/admin/+page.svelte` zeigt eine neue Spalte „Verbrauch" (Open-Meteo-Abrufe heute) je Nutzerzeile; kein Zähler, keine Berechnung im Browser.

**5. Doku.** ADR-0075 Punkt 5 präzisieren; `docs/reference/api_contract.md` um die vier Status-Felder und `open_meteo_calls_today` ergänzen.

Nicht Teil: Cache-Hit/Miss je Nutzer (gibt es nur global, wird nicht erfunden), Schreibzugriffe, Änderungen an der Drosselung, neue Endpunkte.

## Expected Behavior

- **Input:** `GET /api/scheduler/status` (mit Status-Token) und `GET /api/admin/users` (Administrator-Sitzung); Nutzerzähler-Dateien unter `data/users/<uid>/diagnostics/`.
- **Output:** Status: Block `forecast_budget` mit den bisherigen Feldern plus vier anonyme Zahlen. Admin-API: je Nutzer `open_meteo_calls_today`. Admin-Seite: Spalte „Verbrauch".
- **Side effects:** keine; rein lesend.

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer A und B mit heutigen Zählerdateien (A: 120, B: 7 Abrufe) / When ein Administrator `GET /api/admin/users` aufruft / Then trägt der Eintrag von A `open_meteo_calls_today` 120 und der von B 7, ohne Vermischung der Werte.
  - Test: Go-Handlertest mit zwei Nutzerverzeichnissen und verschiedenen Zahlen, Gegenlesung je Nutzer, anschließend Werte vertauscht gegengeprüft.

- **AC-2:** Given ein Nutzer, dessen Zählerdatei ein gestriges Datum trägt / When die Admin-Liste abgerufen wird / Then steht für ihn `open_meteo_calls_today` auf 0 und das Feld ist vorhanden.
  - Test: Go-Test mit Datei vom Vortag und hohem alten Wert; erwartet 0.

- **AC-3:** Given ein Nutzer mit fehlender, leerer oder kaputter (kein gültiges JSON) Zählerdatei / When die Admin-Liste abgerufen wird / Then antwortet das API mit 200, der Nutzer erscheint mit `open_meteo_calls_today` 0 und die übrigen Nutzer behalten ihre Werte.
  - Test: Go-Test mit drei Nutzern (ohne Datei, kaputte Datei, gültige Datei); Status 200, Werte 0/0/N.

- **AC-4:** Given ein angemeldeter Nutzer ohne Administratorrolle (und ein Aufruf ohne Anmeldung) / When er `GET /api/admin/users` aufruft / Then antwortet das API mit 403 (ohne Anmeldung 401) und enthält keine Verbrauchszahl.
  - Test: Router-Test mit normalem Nutzer und Admin im Vergleich; Antwortkörper des 403 enthält kein `open_meteo_calls_today`.

- **AC-5:** Given globale Datei mit `active_users` [A, B] und Nutzerzählern A: 7300, B: 100 / When `/api/scheduler/status` ausgeliefert wird / Then enthält `forecast_budget` `active_pots` 2, `fair_share` 4500, `max_user_calls` 7300 und `users_over_fair_share` 1, aber keine Nutzerkennung und nicht den Schlüssel `active_users`.
  - Test: Go-Scheduler-Test über die serialisierte Antwort; Abwesenheitsprüfung der Kennungen im Gesamt-JSON.

- **AC-6:** Given der bestehende Schutztest `TestForecastBudgetSnapshotLeaksNoUserID` / When die Scheduler-Tests nach der Änderung laufen / Then ist er unverändert (Datei nicht angefasst) und grün.
  - Test: Lauf von `internal/scheduler/forecast_budget_user_privacy_test.go`; `git diff` der Datei ist leer.

- **AC-7:** Given keine globale Datei, kaputte globale Datei oder gestriges Datum / When `/api/scheduler/status` ausgeliefert wird / Then sind die vier neuen Felder trotzdem vorhanden (Werte 0, `fair_share` gleich `daily_budget`) und alle bisherigen Felder behalten Namen, Typ und Bedeutung.
  - Test: Go-Test über die drei Zustände; zusätzlich Vergleich der bisherigen Schlüsselmenge gegen Vorher-Stand (Kompatibilität mit `check-gregor20.sh`, nur additive Felder).

- **AC-8:** Given eine manipulierte Nutzer-ID (z. B. `../x`) / When `userForecastCalls` aufgerufen wird / Then liest es keine Datei außerhalb von `data/users/` und liefert 0.
  - Test: Go-Test mit außerhalb abgelegter Datei und Traversal-ID; Ergebnis 0.

- **AC-9:** Given die Admin-Seite mit zwei Nutzern, deren API-Antwort 120 bzw. 7 liefert / When ein Administrator die Seite öffnet / Then zeigt die Zeile des ersten Nutzers in der Spalte „Verbrauch" 120 und die des zweiten 7.
  - Test: Frontend-Test (`admin_seite_render_und_dialogfluss`-Muster) mit gemockter Netzgrenze, Zelleninhalt je Zeile; Ersatz durch falsche Zeile würde rot.

## Known Limitations

- Nur Open-Meteo-Abrufe des heutigen UTC-Tages; keine Historie, keine Kosten in Geld (das ist #1702).
- Cache-Hit/-Miss gibt es weiterhin nur global.
- Der Fair-Share-Wert im Status ist eine Anzeige-Rechnung; maßgeblich bleibt Python.
- Je Admin-Listenaufruf werden n kleine Dateien gelesen; bei der heutigen Nutzerzahl unkritisch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0075 (Präzisierung von Punkt 5, kein neues ADR)
- **Rationale:** Die Grenze „keine Kennungen im Status-Endpunkt" bleibt; neu festgehalten wird, dass der Verbrauch je Nutzer ausschließlich hinter Admin-Auth angezeigt wird. Damit wird keine dokumentierte Entscheidung rückgängig gemacht.

## Changelog

- 2026-10-01: Initial spec created (#2475, S4 von #2150)
