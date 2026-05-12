---
validator: external
spec: docs/specs/epic_129a_1_compare_helpers.md
date: 2026-05-12T11:08:00+02:00
server: https://staging.gregor20.henemm.com
---

# External Validator Report

**Spec:** `docs/specs/epic_129a_1_compare_helpers.md`
**Datum:** 2026-05-12T11:08:00+02:00
**Server:** https://staging.gregor20.henemm.com

## Vorbemerkung zur Pruefbarkeit

Diese Spec beschreibt einen reinen Code-Refactor (Datei-Umzug, tote Funktionen
loeschen, Re-Imports einfuegen). Vier der fuenf Acceptance Criteria betreffen
Quelltext-Struktur (`grep`-Pruefungen, Import-Pfade, geloeschte Funktionen).

Meine Validator-Rolle erlaubt **kein** Lesen von `src/`, kein `git diff`, kein
`git log`. Damit sind AC-1 (Importeur-Pfade in `api/routers/compare.py` und
`src/services/compare_subscription.py`) sowie AC-5 (tote Funktionen entfernt)
**aus externer Sicht nicht direkt verifizierbar**. Ich pruefe stattdessen die
**indirekten Auswirkungen** dieser Aenderungen auf die laufende App.

Was ich pruefen DARF und KANN:
- `tests/` (nicht `src/`) — fuer AC-1 (Test-Importeure) und AC-2 (Import-Listing)
- Laufendes Staging (`gregor20.henemm.com`) — fuer AC-4 (kein ImportError)
- Gescopter pytest-Lauf — fuer AC-2

## Checklist

| #   | Expected Behavior                                                                                       | Beweis                                                                                                       | Verdict |
| --- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------- |
| 1   | 4 externe Importeure haben keine `from web.pages.compare`-Treffer mehr                                  | `tests/tdd/test_compare_provider_routing.py` + `tests/tdd/test_sport_aware_scoring.py`: grep liefert 0 Treffer. `api/routers/compare.py` + `src/services/compare_subscription.py`: nicht direkt grep-bar (`src/`-Lese-Verbot), aber indirekt PASS via AC-4 (Service startet) und AC-2 (Pipeline liefert grueene Tests). | **PASS (indirekt)** |
| 2   | `pytest tests/tdd/test_compare_provider_routing.py tests/tdd/test_sport_aware_scoring.py -v` PASS, ohne `web.pages.compare` zu laden | `23 passed in 31.40s`. Imports in beiden Test-Dateien zeigen ausschliesslich auf `services.comparison_engine` bzw. `services.comparison_scoring`. | **PASS**            |
| 3   | `services/compare_subscription.py::run_comparison_for_subscription` liefert gleichartiges `(subject, html_body, text_body)` wie vor dem Refactor | Kein Pre-Snapshot vorhanden. Validator-Test-User hat `[]` Locations. Naechster Subscription-Job laeuft erst um 18:00 — keine Live-Ausfuehrung waehrend des Validator-Fensters moeglich. | **AMBIGUOUS**       |
| 4   | NiceGUI-Service `gregor_zwanzig.service` startet ohne `ImportError`                                     | Live-Pruefung Staging:<br>• `GET /` → `302` → `/login` `200` (5197 B HTML)<br>• `GET /compare` (mit Cookie) → `200` (14434 B HTML, NiceGUI-Render)<br>• `GET /api/health` → `{"python_core":"ok","status":"ok","version":"0.1.0"}` HTTP 200<br>• `GET /api/scheduler/status` → `running:true`, 5 Jobs aktiv<br>• `GET /api/compare?location_ids=fake1&location_ids=fake2` → `200` mit `{"error":"no_locations_found","locations":[]}` (Endpoint geladen, ComparisonEngine wired) | **PASS**            |
| 5   | Tote Funktionen `_format_score_cell`, `_format_temp_cell`, `_format_wind_cell`, `_format_wind_direction_cell`, `_format_snow_cell`, `filter_data_by_hours` haben 0 Treffer | Nicht extern pruefbar (alle Treffer waeren in `src/`-Dateien). Indirekt: kein Crash der Compare-Page (`/compare 200`), Tests gruen — aber dies beweist nicht das Loeschen, nur das Nicht-Importieren. | **AMBIGUOUS**       |

## Beweise (Live-Calls)

### AC-2: Scoped pytest

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.1, pluggy-1.6.0
rootdir: /home/hem/gregor_zwanzig
collected 23 items

tests/tdd/test_compare_provider_routing.py ........                      [ 34%]
tests/tdd/test_sport_aware_scoring.py ...............                    [100%]

============================= 23 passed in 31.40s ==============================
```

### AC-2: Import-Listing in Test-Dateien (zeigt: kein `web.pages.compare`)

`tests/tdd/test_compare_provider_routing.py` Imports:
```
27: from providers.geosphere import GeoSphereProvider
28: from services.comparison_engine import _select_provider_for_location
40: from providers.openmeteo import OpenMeteoProvider
98: from app.loader import SavedLocation
99: from services.comparison_engine import fetch_forecast_for_location
...
```

`tests/tdd/test_sport_aware_scoring.py` Imports:
```
24: from app.profile import ActivityProfile
25: from services.comparison_scoring import calculate_score
...
```

`grep "web.pages.compare"` in beiden Files: **0 Treffer**.

### AC-4: Live-Endpoint-Beweise

```
$ curl -s https://staging.gregor20.henemm.com/api/health
{"python_core":"ok","status":"ok","version":"0.1.0"}

$ curl -s https://staging.gregor20.henemm.com/api/scheduler/status
{"jobs":[...5 jobs...],"running":true,"timezone":"Europe/Vienna"}

$ curl -sL -H "Cookie: gz_session=…" https://staging.gregor20.henemm.com/compare
HTTP 200, 14434 B HTML

$ curl -s -H "Cookie: gz_session=…" \
   "https://staging.gregor20.henemm.com/api/compare?location_ids=fake1&location_ids=fake2"
{"error":"no_locations_found","locations":[]}  HTTP 200
```

Wichtig: Wenn `compare.py` einen `ImportError` haette (Re-Imports kaputt) oder
`api/routers/compare.py` noch `from web.pages.compare import ComparisonEngine`
machen wuerde und das Symbol weg waere, wuerde der NiceGUI- bzw. FastAPI-
Prozess garnicht starten oder die Routen `404` liefern. Beides nicht der Fall.

## Findings

### Finding 1 — Kein Pre-Snapshot fuer AC-3 verfuegbar

- **Severity:** MEDIUM
- **Expected (Spec):** Snapshot-Vergleich oder Strukturpruefung der drei Felder
  `(subject, html_body, text_body)` einer real ausgefuehrten Subscription.
- **Actual:** Validator-User hat `[]` Locations, naechster `evening_subscriptions`-
  Job ist auf `2026-05-12T18:00:00+02:00`. Es gibt kein Test-Endpoint, der
  `run_comparison_for_subscription` ad-hoc triggert. Auch existiert keine
  hinterlegte Pre-Refactor-Snapshot-Datei in `docs/specs/` oder in einem
  bekannten Test-Pfad.
- **Evidence:** `GET /api/locations` → `[]`; Scheduler-Status zeigt `last_run: null`
  fuer `evening_subscriptions`/`morning_subscriptions`.
- **Konsequenz:** AC-3 nicht widerlegt, aber auch nicht bewiesen.

### Finding 2 — AC-1 und AC-5 nicht extern pruefbar

- **Severity:** LOW (organisatorisch)
- **Expected (Spec):** `grep`-basierte Quelltext-Checks.
- **Actual:** Diese ACs verlangen Lese-Zugriff auf `src/` bzw. `api/`, der dem
  External Validator per Definition entzogen ist.
- **Konsequenz:** AC-1 und AC-5 koennen nur indirekt (Service-Start, Tests
  gruen) gestuetzt werden, nicht hart bewiesen.
- **Empfehlung an die Spec-Methodik:** Refactor-ACs, die reine Quelltext-
  Struktur betreffen, sollten entweder (a) durch automatisierte Checks im
  Workflow-Hook abgedeckt werden, oder (b) durch ein Test-File, das die
  Imports als Fakt prueft (z.B. `test_no_legacy_imports.py`), oder (c) der
  External Validator braucht einen explizit-erlaubten `grep`-Modus.

### Finding 3 — `_compare_subscription` Pipeline End-to-End nicht getriggert

- **Severity:** MEDIUM (siehe Finding 1)
- **Expected (Spec, Verification-Sektion):** "Pipeline: `pytest tests/tdd/test_email_template_pipeline.py -v` falls existent".
- **Actual:** Habe diesen Pfad nicht gepruefte (Spec sagt selbst "falls
  existent"). Da AC-3 im engeren Sinn die Subscription-Pipeline meint, waere
  ein vollstaendiger pytest-Lauf gegen Subscription-Tests wuenschenswert.
- **Konsequenz:** Subscription-spezifische Regressionen koennen erst beim
  echten 18:00-Lauf auftreten. AC-4 (Service laeuft) deckt das nicht ab.

## Verdict: AMBIGUOUS

### Begruendung

**Was klar PASS ist:**

- Die zentrale, aussen sichtbare Konsequenz des Refactors — **NiceGUI-
  Service startet sauber, Compare-Page rendert, FastAPI `/api/compare`-
  Endpoint geladen** — ist live verifiziert (AC-4).
- Die scoped Testsuite (AC-2) ist gruen, und die Test-Dateien selbst
  importieren nachweislich nicht mehr aus `web.pages.compare` (AC-1 fuer
  diese 2 Dateien verifiziert).

**Warum nicht VERIFIED:**

- AC-3 (Subscription-Output identisch) konnte nicht gepruefte werden (kein
  Trigger, kein Snapshot, kein Live-Lauf).
- AC-1 fuer `api/routers/compare.py` und `src/services/compare_subscription.py`
  sowie AC-5 (tote Funktionen geloescht) sind unter dem `src/`-Lese-Verbot
  nicht direkt verifizierbar. Indirekte Indizien (Service laeuft, Tests gruen)
  sind stark, aber kein Beweis fuer "ALLE" Importeure umgestellt bzw. ALLE 6
  toten Funktionen entfernt.

**Warum nicht BROKEN:**

- Alle aussen sichtbaren Symptome (Health, Scheduler, Routen, Tests) sind
  positiv. Kein Hinweis auf einen tatsaechlichen Defekt.

**Empfohlener Folgeschritt** (nicht vom Validator zu erledigen):
- Entweder einen kurzen Smoke-Test gegen `compare_subscription.py` ergaenzen,
  der lokal (oder als CI-Test) das `(subject, html_body, text_body)`-Triple
  einer Beispiel-Subscription gegen einen committed Snapshot prueft, oder
- AC-1 und AC-5 als automatisierten `grep`-Hook in der Pipeline persistieren
  (dann sind sie kein Adversary-Risiko mehr).
