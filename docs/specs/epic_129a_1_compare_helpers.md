---
entity_id: epic_129a_1_compare_helpers
type: refactor
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [refactor, tech-debt, epic-129, services-extraction]
---

<!-- GitHub Issue #129 (Phase A.1 von A.1/A.2/A.3/B) — Helper-Extraktion aus src/web/pages/compare.py -->

# Epic #129 Phase A.1 — Compare-Helper aus NiceGUI-UI extrahieren

## Approval

- [ ] Approved

## Purpose

Erste von vier Etappen zur ersatzlosen Entfernung der NiceGUI-UI (Issue #129). In dieser Phase A.1 werden die UI-freien Helper aus `src/web/pages/compare.py` (1994 LoC) nach `src/services/` umgezogen. `compare.py` selbst wird **nicht** gelöscht (kommt in Phase A.3) und nutzt die extrahierten Helper übergangsweise via Re-Imports.

Externe Konsumenten (`api/routers/compare.py`, `src/services/compare_subscription.py`, betroffene Tests) zeigen nach diesem Umzug nicht mehr auf `web.pages.compare` für ihre Helper, sondern direkt auf `services.*`. Damit ist die NiceGUI-Schicht in Phase A.3 löschbar, ohne dass Production-Code (Go-API + Subscription-Pipeline) zerbricht.

## Source

### Neue Dateien (alle in `src/services/`)

| Datei | Inhalt |
|-------|--------|
| `src/services/comparison_scoring.py` | `calculate_score`, `_score_wintersport`, `_score_wandern`, `_score_allgemein` |
| `src/services/comparison_engine.py` | `ComparisonEngine`, `fetch_forecast_for_location`, `_select_provider_for_location`, `dict_to_comparison_result` |
| `src/services/comparison_renderers.py` | `render_comparison_html`, `render_comparison_text`, `_degrees_to_compass` |

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `src/web/pages/compare.py` | Helper-Definitionen entfernt → ersetzt durch `from services.comparison_* import …`. UI-Code (`render_compare`, `render_winner_card`, `run_comparison_for_subscription` mit `ui.notify`) bleibt. **Tote Funktionen ersatzlos gelöscht:** `_format_score_cell`, `_format_temp_cell`, `_format_wind_cell`, `_format_wind_direction_cell`, `_format_snow_cell`, `filter_data_by_hours` (alle nicht aufgerufen, von Phase-2-Analyse bestätigt). |
| `api/routers/compare.py` (Z. 22) | `from web.pages.compare import ComparisonEngine` → `from services.comparison_engine import ComparisonEngine` |
| `src/services/compare_subscription.py` (Z. 40-44) | `from web.pages.compare import ComparisonEngine, render_comparison_html, render_comparison_text` → entsprechende neue Pfade |
| `tests/tdd/test_compare_provider_routing.py` | Imports umstellen auf `services.comparison_engine` |
| `tests/tdd/test_sport_aware_scoring.py` | Imports umstellen auf `services.comparison_scoring` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/web/pages/compare.py` | Python file (legacy) | Wird nach Phase A.3 gelöscht — bis dahin importiert sie aus den neuen Service-Modulen |
| `api/routers/compare.py` | FastAPI router | Production-API — darf weder syntaktisch noch semantisch brechen |
| `src/services/compare_subscription.py` | Service | Subscription-Pipeline (E-Mail-Versand) — wird vom Scheduler aufgerufen |
| `app.config.Location`, `app.user.CompareSubscription`, `app.models.ForecastDataPoint` | DTOs | Werden von den Helpern benutzt — bleiben unverändert |

## Implementation Details

### Reihenfolge der Extraktion (wegen Funktions-Abhängigkeiten)

1. **`comparison_scoring.py`** zuerst — `calculate_score` hat keine externen Helper-Deps.
2. **`comparison_renderers.py`** — `render_*` Funktionen hängen nur an `_degrees_to_compass` (in derselben Datei).
3. **`comparison_engine.py`** — nutzt `calculate_score` (aus 1.) und `fetch_forecast_for_location` (eigene Datei).
4. **`compare.py` Re-Imports** ergänzen — danach laufen die UI-Funktionen weiter.
5. **Externe Imports** umstellen.
6. **Tote Code-Funktionen** entfernen.

### Übergangs-Pattern in `compare.py`

```python
# Bis Phase A.3 (NiceGUI-Löschung): Re-Imports halten UI lauffähig
from services.comparison_scoring import calculate_score
from services.comparison_engine import (
    ComparisonEngine,
    dict_to_comparison_result,
    fetch_forecast_for_location,
)
from services.comparison_renderers import (
    render_comparison_html,
    render_comparison_text,
)
```

### Was NICHT in dieser Phase passiert

- **`run_comparison_for_subscription` in `compare.py`** bleibt mit `ui.notify`-Calls erhalten (UI-Variante). Die Service-Variante in `services/compare_subscription.py` wird ohnehin schon genutzt — siehe Memory-Regel „Code-Duplikate konsolidieren".
- **UI-Funktionen** (`render_compare`, `render_header`, `render_winner_card`, `render_results_table`, `render_hourly_table`, `format_time_range`) bleiben in `compare.py`. Werden in Phase A.3 mit der ganzen Datei gelöscht.

## Expected Behavior

- **Pre-Refactor:** `pytest tests/` grün. `api/routers/compare.py` lädt sauber. Subscription-Cron-Lauf liefert die gleiche E-Mail wie heute.
- **Post-Refactor:** identisch — keine funktionale Änderung. Nur Datei-Layout.
- **Side effects:** `src/services/` bekommt 3 neue Module. `src/web/pages/compare.py` schrumpft um ~700 LoC (Helper raus + tote Funktionen weg).

## Acceptance Criteria

- **AC-1:** Given die 4 betroffenen externen Importeure (`api/routers/compare.py`, `src/services/compare_subscription.py`, `tests/tdd/test_compare_provider_routing.py`, `tests/tdd/test_sport_aware_scoring.py`) / When grep nach `from web.pages.compare` oder `from src.web.pages.compare` läuft / Then **kein Treffer mehr** in diesen 4 Dateien.
  - Test: (populated after /tdd-red)

- **AC-2:** Given die 3 neuen Service-Module / When `pytest tests/tdd/test_compare_provider_routing.py tests/tdd/test_sport_aware_scoring.py -v` läuft / Then alle Tests **PASS**, ohne dass `src/web/pages/compare.py` für die getesteten Funktionen geladen werden muss (verifizierbar durch Import-Listing in den Tests).
  - Test: (populated after /tdd-red)

- **AC-3:** Given der bestehende Subscription-Workflow / When `services/compare_subscription.py::run_comparison_for_subscription` aufgerufen wird (in einem Integration-/Smoke-Test gegen eine Beispiel-Subscription) / Then erzeugt sie ein gleichartiges `(subject, html_body, text_body)`-Triple wie vor dem Refactor (verifiziert durch Snapshot-Vergleich oder Strukturprüfung der Felder).
  - Test: (populated after /tdd-red)

- **AC-4:** Given der NiceGUI-Service `gregor_zwanzig.service` läuft mit dem gepatchten `compare.py` / When der Service neu startet (`systemctl restart`) / Then **kein ImportError** in den Logs (das beweist, dass die Re-Imports in `compare.py` korrekt sind und die UI-Funktionen weiterhin lauffähig sind, auch wenn extern nicht erreichbar).
  - Test: (populated after /tdd-red)

- **AC-5:** Given die toten Funktionen `_format_score_cell`, `_format_temp_cell`, `_format_wind_cell`, `_format_wind_direction_cell`, `_format_snow_cell`, `filter_data_by_hours` / When grep nach diesen Bezeichnern im gesamten Repo (`*.py`, exklusive `.git`, `.claude/worktrees/`) läuft / Then **0 Treffer** (vollständig entfernt).
  - Test: (populated after /tdd-red)

## Out of Scope (für Phase A.1)

- **`src/web/pages/compare.py` ersatzlos löschen** → Phase A.3
- **GPX-Helper aus `pages/trips.py` und `pages/gpx_upload.py`** → Phase A.2 (separater Workflow `epic-129a-2-gpx-helpers`)
- **`src/web/utils.py` (`parse_dms_coordinates`)** → Phase A.2
- **systemd-Service deaktivieren** → Phase B (`epic-129b-infra-doku-cleanup`)
- **`CLAUDE.md`-Aufräumung** → Phase B
- **Spec-Template um Schicht-Hinweis erweitern** → Phase B

## Verification

- **Unit:** `pytest tests/tdd/test_compare_provider_routing.py tests/tdd/test_sport_aware_scoring.py -v` (scoped, kein vollständiger pytest tests/-Lauf)
- **Pipeline:** `pytest tests/tdd/test_email_template_pipeline.py -v` falls existent (sicherstellen dass `compare_subscription.py` weiter funktioniert)
- **Vollständiger Lauf vor Push:** `pytest tests/ -q --tb=short` muss grün bleiben (nur das Endergebnis prüfen, nicht den vollen Output für Adversary)
- **Smoke-Test Staging nach Deploy:**
  ```bash
  curl -s https://staging.gregor20.henemm.com/api/health
  curl -s https://staging.gregor20.henemm.com/api/scheduler/status | python3 -m json.tool
  ```

## LoC-Estimate

- **Verschoben:** ~700 LoC (compare.py → services/)
- **Gelöscht (tote Funktionen):** ~150 LoC
- **Re-Imports in compare.py:** ~10 LoC
- **Externe Import-Updates:** 4 Stellen, jeweils 1-3 Zeilen
- **Erwartetes LoC-Delta laut Workflow-Tool:** ca. +800 (neue Service-Files zählen als adds, alte Helpers in compare.py zählen als deletes — Tool zählt netto). **Override auf 1500 nötig.**

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Vergessener Helper-Import in `compare.py` führt zu `NameError` beim NiceGUI-Service-Start | mittel | AC-4 (Service-Restart-Smoke), `pytest tests/` |
| `services/compare_subscription.py` bricht nach Import-Update | niedrig | AC-3 + bestehende Tests in `tests/tdd/test_*subscription*.py` |
| Tote Funktionen werden doch irgendwo importiert (z.B. via Reflection) | sehr niedrig | AC-5 (grep), pytest deckt es auf |
| Re-Imports in `compare.py` schaffen zirkuläre Imports | niedrig | Phase-2-Analyse hat keine Zirkularität gefunden, aber Test im Service-Restart |
