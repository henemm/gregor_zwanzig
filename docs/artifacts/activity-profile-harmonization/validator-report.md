---
type: external-validator-report
spec: docs/specs/modules/activity_profile.md
date: 2026-05-01T20:05:00+02:00
server: https://gregor20.henemm.com
validator: external (independent QA)
---

# External Validator Report

**Spec:** `docs/specs/modules/activity_profile.md`
**Datum:** 2026-05-01
**Server:** https://gregor20.henemm.com

## Vorbemerkung zum Spec-Stand

Die Spec definiert ein **Two-PR-Migration-Verfahren**:
- **PR 1:** Canonical-Enum + Aliase, kein Test-Touch
- **PR 2:** Alias-Entfernung + mechanisches Rename aller Importer

Die Akzeptanzkriterien §A3 und §A6 sind explizit „nach PR 2" formuliert.
Die im Repo beobachtbare Situation entspricht dem **Zustand nach PR 1, vor PR 2**:
`src/app/user.py` enthält die Alias-Zeile mit Kommentar
`# backward-compat alias (PR 1) — entfernt in PR 2`. Konsequenz: Akzeptanzkriterien
für den Endzustand können nicht alle erfüllt sein.

## Checklist

| #   | Expected Behavior | Beweis | Verdict |
|-----|-------------------|--------|---------|
| §A1a | `grep -rn "class ActivityProfile" src/` → genau 1 Treffer | 1 Treffer in `src/app/profile.py:12` | **PASS** |
| §A1b | `grep -rn "class LocationActivityProfile" src/` → 0 Treffer | 0 Treffer | **PASS** |
| §A2  | Alle 4 Enum-Werte (`wintersport`, `wandern`, `summer_trekking`, `allgemein`) vorhanden, `ActivityProfile("custom")` raised `ValueError` | Python REPL bestätigt alle 4 Werte; `ActivityProfile('custom')` → `ValueError` | **PASS** |
| §A3  | `grep -rn "LocationActivityProfile" src tests` → 0 Treffer (nach PR 2) | **107** Non-pyc-Treffer in 9 Dateien (s.u.) | **FAIL gegen Endzustand** / **N/A für PR 1** |
| §A4a | `pytest` grün nach PR 1 ohne Test-Änderungen | Spec-relevante Tests (`test_generic_locations`, `test_sport_aware_scoring`, `test_weather_templates`, `test_config_persistence`, `test_loader`, `test_trip`) → 100/100 grün | **PASS** |
| §A4b | `pytest` grün nach PR 2 mit umgestellten Imports | PR 2 nicht implementiert | **N/A** |
| §A5  | `verify_activity_profile_migration.py` Exit 0 vor PR 1 und nach PR 2 | `OK: 451 Dateien gescannt, 10 Profile-Werte alle gueltig` — Exit 0 | **PASS** |
| §A6a | Go-API akzeptiert `activity_profile: "summer_trekking"` (PR 2 abhängig) | `POST /api/subscriptions` ohne Auth → HTTP 401, nicht prüfbar | **UNKLAR** |
| §A6b | Go-API lehnt `activity_profile: "custom"` mit 400 ab | nicht prüfbar (Auth-Wall) | **UNKLAR** |
| §A7a | GPX-Upload mit `ActivityProfile.SUMMER_TREKKING` funktioniert | UI hinter Login (302→/login), keine Credentials in Validator-Session | **UNKLAR** |
| §A7b | Compare-Scoring dispatcht für `wintersport`, `wandern`, `allgemein` | UI hinter Login, nicht prüfbar | **UNKLAR** |
| §A8  | Checkliste für zukünftige Sportarten | Future-Checklist, kein Validierungs-Item für Initial-Spec | **N/A** |

## Findings

### F1 — PR 2 nicht durchgeführt (gegen Spec-Endzustand)

- **Severity:** HIGH (gegen Spec-Endzustand) / NONE (für validen PR-1-Zwischenzustand)
- **Expected:** Spec §A3: `grep -rn "LocationActivityProfile" src tests` → 0 Treffer
- **Actual:** 107 Non-pyc-Treffer in 9 Dateien:
  - `src/app/loader.py` (Importer)
  - `src/app/metric_catalog.py` (Importer)
  - `src/app/user.py` (enthält Alias-Zeile + 2 Verwendungen)
  - `src/web/pages/compare.py` (Importer + 4 Verwendungen)
  - `tests/integration/test_config_persistence.py`
  - `tests/tdd/test_activity_profile_harmonization.py`
  - `tests/tdd/test_generic_locations.py`
  - `tests/tdd/test_sport_aware_scoring.py`
  - `tests/tdd/test_weather_templates.py`
- **Evidence:**
  ```
  $ grep -rn "LocationActivityProfile" src tests | grep -v __pycache__ | wc -l
  107
  $ grep -n "backward-compat alias" src/app/user.py
  21:LocationActivityProfile = ActivityProfile  # backward-compat alias (PR 1) — entfernt in PR 2
  ```
- **Bewertung:** Konsistent mit „PR 1 abgeschlossen, PR 2 ausstehend". Der Alias-Kommentar
  in `user.py:21` benennt PR 2 explizit als kommend. Das ist **kein Defekt**, sondern ein
  Spec-konformer Zwischenstand — sofern die Implementierer-Session PR 1 als
  abgeschlossen meldet und PR 2 als separaten PR plant.

### F2 — UI- und API-Akzeptanzkriterien nicht direkt validierbar

- **Severity:** MEDIUM (Validierungslücke)
- **Expected:** §A6 (Go-Whitelist), §A7 (GPX-Upload, Compare-Scoring) — funktional in der
  Live-App
- **Actual:**
  - `POST /api/subscriptions` → HTTP 401 (unauthorized) — keine Validator-Credentials
  - `GET /` → 302 → `/login` — UI ohne Login nicht erreichbar
- **Evidence:**
  ```
  $ curl -X POST https://gregor20.henemm.com/api/subscriptions \
      -H "Content-Type: application/json" \
      -d '{"activity_profile":"summer_trekking"}'
  {"error":"unauthorized"}  HTTP 401

  $ curl -L https://gregor20.henemm.com/
  HTTP=200  Final=https://gregor20.henemm.com/login
  ```
- **Bewertung:** §A6 und §A7 können unter External-Validator-Isolation
  (kein src/-Read, keine Implementierer-Credentials, nur Spec + laufende App) nicht
  bewiesen werden. Verifikation muss in einer Session mit Login-Zugang erfolgen.

### F3 — Verifikations-Skript funktioniert wie spezifiziert

- **Severity:** —
- **Expected:** Spec §6.3 / §A5: Skript scannt `data/users/`, gibt Exit 0 für valide Werte
- **Actual:** `OK: 451 Dateien gescannt, 10 Profile-Werte alle gueltig`, Exit 0
- **Evidence:**
  ```
  $ uv run python3 scripts/verify_activity_profile_migration.py; echo "EXIT=$?"
  OK: 451 Dateien gescannt, 10 Profile-Werte alle gueltig
  EXIT=0
  ```
- **Bewertung:** Pre-Migration-Bestand ist Exit-0-clean. Schema-Backup-Hook-Voraussetzung
  (s. Spec §7.1) ist damit erfüllt.

### F4 — Pytest-Failures außerhalb des Spec-Scopes

- **Severity:** LOW (Spec-irrelevant)
- **Beobachtung:** `uv run pytest --ignore=tests/e2e` schlägt in folgenden Dateien fehl:
  - `tests/integration/test_wind_exposition_pipeline.py::test_sms_grat_wind_label`
  - `tests/tdd/test_account_page.py` (2 Test-Cases)
  - `tests/tdd/test_geosphere_parsing.py::test_snowgrid_multiple_locations`
  - `tests/tdd/test_snowgrid.py::test_all_resorts_have_data` (Geosphere 429 Rate-Limit)
  - `tests/e2e/test_e2e_friendly_format_config.py::test_alert_enabled` (`KeyError: 'display_config'`)
- **Bewertung:** Keine dieser Failures betrifft das `ActivityProfile`-Modul oder seine
  Importer. Die in §5 der Spec aufgelisteten Test-Dateien sind alle grün.

## Verdict: **AMBIGUOUS**

### Begründung

Validierbare PR-1-Kriterien sind durchweg erfüllt (§A1, §A2, §A4 für PR 1, §A5).
Der Code-Zustand entspricht **eindeutig dem Zwischenstand „PR 1 abgeschlossen,
PR 2 ausstehend"** — der Alias in `src/app/user.py:21` ist mit Kommentar als
PR-2-Restposten markiert.

Gegen den **Spec-Endzustand** (nach PR 2) ist §A3 nicht erfüllt: 107 Treffer
für `LocationActivityProfile` in 9 Dateien.

§A6 (Go-API-Whitelist) und §A7 (GPX-Upload + Compare-Scoring) sind unter
Validator-Isolation nicht prüfbar (keine Auth, UI hinter Login). Das ist eine
**Validierungslücke**, kein nachgewiesener Defekt.

**Konsequenz:**
- Wenn die Implementierer-Session **PR 1 als Abschluss** meldet → die PR-1-Kriterien
  sind verified. PR 2 muss als separater Folge-PR offen bleiben und eigene
  Validierung erhalten (mit dann erfüllbarem §A3 und prüfbarem §A6).
- Wenn die Implementierer-Session **beide PRs als Abschluss** meldet → das ist
  **BROKEN gegen §A3**.

Ohne Implementierer-Kontext (laut Validator-Regeln nicht einsehbar) ist die
Eindeutigkeit nicht herstellbar — daher **AMBIGUOUS**.

### Empfehlung an die Implementierer-Session

1. Klärung, ob diese Validierung **PR 1 allein** oder **PR 1 + PR 2 gemeinsam** abdecken soll.
2. Falls **nur PR 1**: Report ist VERIFIED für die anwendbaren Kriterien (§A1, §A2, §A4a, §A5).
3. Falls **beide PRs**: §A3-FAIL fixen — Alias-Zeile in `user.py:21` entfernen, alle
   `LocationActivityProfile`-Imports auf `from app.profile import ActivityProfile`
   umstellen (s. Spec §6.1 PR 2, Schritt 2 — die Liste der zu ändernden Dateien stimmt
   mit den 9 hier gefundenen Treffer-Dateien exakt überein).
4. **Zusatz:** §A6 und §A7 müssen in einer separaten authentifizierten Test-Session
   abgedeckt werden — der External Validator hat dafür systembedingt keinen Zugang.
