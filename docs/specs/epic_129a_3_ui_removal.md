---
entity_id: epic_129a_3_ui_removal
type: refactor
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [refactor, tech-debt, epic-129, nicegui-removal, deletion-only]
---

<!-- GitHub Issue #129 (Phase A.3 von A.1/A.2/A.3/B) — NiceGUI ersatzlos löschen + systemd disable -->

# Epic #129 Phase A.3 — NiceGUI-UI ersatzlos löschen + Service abklemmen

## Approval

- [ ] Approved

## Purpose

Dritte und größte Phase der NiceGUI-Removal. Nach Phase A.1 (Compare-Helper) und A.2 (GPX-Helper + Coordinates) sind alle UI-freien Helper sauber nach `src/services/` umgezogen. Jetzt werden:

1. **11 NiceGUI-Code-Dateien** unter `src/web/` ersatzlos gelöscht
2. **7 Test-Dateien** entfernt (UI-Tests + APScheduler-Tests, alle obsolet)
3. **Production-Service `gregor_zwanzig.service` deaktiviert** (sonst Crash beim Restart, weil `python -m src.web.main` ins Leere zeigt)
4. **`pyproject.toml` aufgeräumt** — `nicegui`, `apscheduler` als Dependencies raus, 3 Ruff-Exceptions weg
5. **`.claude/validate.py` + `.claude/commands/e2e-verify.md`** angepasst — beide haben noch String-Eval-Imports auf `web.main`, die nach dem Lösch-Schritt crashen

Service-Disable und Code-Löschung **in einem atomic Workflow**, weil sonst Production zwischendurch crashed (deploy-Skript macht systemctl restart auf einen nicht mehr existierenden Entry-Point).

## Source

### Zu löschen (Production-Code, 11 Dateien)

| Datei | LoC | Begründung |
|-------|-----|------------|
| `src/web/__init__.py` | 9 | Modul-Marker — leer |
| `src/web/main.py` | 139 | NiceGUI Entry-Point, von außen unerreichbar (Nginx routet nicht auf 8080) |
| `src/web/scheduler.py` | 387 | Python-APScheduler — Go-Scheduler in `internal/scheduler/scheduler.go` ist authoritativ |
| `src/web/pages/__init__.py` | 1 | Leerer Modul-Marker |
| `src/web/pages/dashboard.py` | 75 | NiceGUI-Page |
| `src/web/pages/settings.py` | 350 | NiceGUI-Page |
| `src/web/pages/trips.py` | ~774 | NiceGUI-Page nach A.1+A.2-Helper-Extraktion |
| `src/web/pages/compare.py` | ~866 | NiceGUI-Page nach A.1-Helper-Extraktion |
| `src/web/pages/gpx_upload.py` | ~265 | NiceGUI-Page nach A.2-Helper-Extraktion |
| `src/web/pages/weather_config.py` | 514 | NiceGUI-Page |
| `src/web/pages/report_config.py` | 256 | NiceGUI-Page |

**Gesamt:** ca. 3.636 LoC weg.

### Zu löschen (Tests, 7 Dateien)

| Datei | Tests | Begründung |
|-------|-------|------------|
| `tests/tdd/test_weather_config_api_ui.py` | 23 | Testet alte NiceGUI-UI über String-Eval-Import von `web.main` + Playwright Port 18092 |
| `tests/tdd/test_safari_cache_fix.py` | wenige | Validation für alte UI |
| `tests/e2e/test_weather_config.py` | 1+ | Schon `@pytest.mark.skip` (decommissioned in M4b) |
| `tests/integration/test_trip_report_scheduler.py` | 14 | Testet Python-`web.scheduler` (APScheduler), nicht den Go-Scheduler |
| `tests/tdd/test_betterstack_heartbeat.py` | mehrere | Testet `HEARTBEAT_MORNING/EVENING` aus `web.scheduler` |
| `tests/unit/test_settings_protection.py` | 4 | Testet `web.pages.settings.save_env_settings` (UI-Helper, wird gelöscht) |
| `tests/unit/test_weather_config_strategy.py` | 7 | Testet `_DialogStrategy`, `_make_trip_save_fn` aus `web.pages.weather_config` |

### Zu modifizieren (3 Dateien)

| Datei | Änderung |
|-------|----------|
| `pyproject.toml` | Entfernen: `nicegui>=2.0.0`, `apscheduler>=…`. Ruff-Exceptions raus für `src/web/scheduler.py`, `src/web/pages/compare.py`, `src/web/pages/gpx_upload.py` |
| `.claude/validate.py` (Zeile 82) | String-Eval `from web.main import *` → `from api.main import app` (Go-API funktioniert, NiceGUI nicht mehr) |
| `.claude/commands/e2e-verify.md` | Referenzen auf `python3 -m src.web.main` raus oder auf Go-Stack umstellen |

### Production-Aktionen (systemd, manuell + via Deploy-Script)

1. **VOR Push:** Auf Production manuell `sudo systemctl stop gregor_zwanzig.service && sudo systemctl disable gregor_zwanzig.service` (sonst crasht der Service beim Auto-Restart durch deploy-script)
2. **Nach Deploy:** Verifikation `systemctl is-active gregor_zwanzig.service` → `inactive`
3. **`gregor_zwanzig.service`-File** in `henemm-infra` als gelöscht markieren (PR im Infra-Repo) — kann auch Phase B sein, aber gehört thematisch dazu

### Geschützt — wird NICHT angefasst

| Datei | Begründung |
|-------|------------|
| `src/services/comparison_*.py`, `src/services/gpx_processing.py`, `src/services/coordinates.py` | Helper aus A.1+A.2, weiterhin produktiv |
| `api/routers/*.py` | Production-API |
| `internal/scheduler/scheduler.go` | Go-Scheduler (authoritativ) |
| `tests/refactor/test_epic_129a_*.py` + `tests/refactor/test_issue_201_*.py` | Refactor-Tests aus den vorigen Phasen |
| `tests/tdd/test_account_page.py`, `test_change_password.py`, `test_register_page.py`, `test_account_page_extend.py` | HTTP-Tests gegen SvelteKit-Stack |
| `tests/unit/test_gpx_upload_page.py`, `tests/unit/test_etappen_config.py`, `tests/unit/test_trips_time_window_bugfix.py`, `tests/tdd/test_compare_provider_routing.py`, `tests/tdd/test_sport_aware_scoring.py` | Testen die nach `services/` migrierten Helper |
| `tests/integration/test_report_config.py` | Testet `app.models.TripReportConfig` (DTO, nicht NiceGUI) — bleibt |
| `CLAUDE.md`, `docs/specs/_template.md` | Doku-Aufräumung → Phase B |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `gregor_zwanzig.service` (systemd) | Production-Service | Wird in dieser Phase deaktiviert |
| `henemm-infra` Repo | Sister-Projekt | Service-File-Löschung als separate PR — out of scope, MQ an `infra` |
| Bisherige Phasen A.1, A.2 | refactor workflows | Vorbedingung — alle Helper sind raus |

## Implementation Details

### Reihenfolge (kritisch wegen Production!)

1. **Pre-Push: NiceGUI-Service auf Prod stoppen** — manuell SSH:
   ```bash
   sudo systemctl stop gregor_zwanzig.service
   sudo systemctl disable gregor_zwanzig.service
   ```
   Verifikation: `systemctl is-active gregor_zwanzig.service` → `inactive`
2. **`.claude/validate.py` + `.claude/commands/e2e-verify.md`** anpassen (sonst crashen Hook-Skripte beim ersten Edit nach Lösch)
3. **`pyproject.toml`** aufräumen (`nicegui`, `apscheduler`, Ruff-Exceptions)
4. **`uv lock`** ausführen → `uv.lock` aktualisiert
5. **7 Test-Dateien löschen**
6. **11 Production-Dateien in `src/web/` löschen** (komplettes Verzeichnis)
7. **Verifikation:**
   - `uv run pytest tests/refactor/ tests/unit/ tests/tdd/ -q --tb=short` → keine ImportError, keine neuen Failures gegenüber Baseline
   - `find src/web -type f` → leer
   - `grep -rn "from web\.\|import web\." src/ api/ tests/ .claude/` → 0 Treffer
8. **Push** → Auto-Deploy auf Staging (NiceGUI-Service ist auf Staging eh nicht da → kein Risiko)
9. **Prod-Deploy** mit `deploy-gregor-prod.sh` — wird kein NiceGUI-Restart mehr versuchen, weil Service disabled

### Was NICHT in dieser Phase

- **`gregor_zwanzig.service`-File aus `henemm-infra` löschen** — separater PR im Sister-Repo, MQ an `infra`
- **CLAUDE.md NiceGUI-Sektionen entfernen** → Phase B
- **`docs/specs/_template.md` um Schicht-Hinweis erweitern** → Phase B
- **`docs/specs/web_ui.md` als Legacy markieren oder löschen** → Phase B

## Expected Behavior

- **Pre-Refactor:** `pytest tests/` läuft mit pre-existing Failures (vor allem APScheduler-Tests, NiceGUI-E2E). NiceGUI-Service auf Prod aktiv aber von außen unerreichbar.
- **Post-Refactor:** `pytest tests/` läuft mit weniger Tests (gelöschte Tests weg) und gleichen oder weniger Failures. NiceGUI-Service auf Prod inaktiv. `src/web/` leer/weg. `nicegui` und `apscheduler` nicht mehr in `pyproject.toml`.
- **Side effects:** ~3.700 LoC Production-Code weg, ~50 Test-Funktionen weg, 2 Dependencies gespart (~80 MB RAM).

## Acceptance Criteria

- **AC-1:** Given das Repo nach dem Refactor / When `find src/web -type f` läuft / Then **0 Treffer**. Verzeichnis ist komplett weg.
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Repo nach dem Refactor / When `grep -rn "from web\.\|import web\." src/ api/ tests/ .claude/ --include="*.py"` läuft / Then **0 Treffer**. Niemand importiert mehr aus `web.*`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given die 7 zu löschenden Test-Dateien / When `ls`-Check läuft / Then **0 existieren**. Genau diese: `tests/tdd/test_weather_config_api_ui.py`, `test_safari_cache_fix.py`, `test_betterstack_heartbeat.py`, `tests/e2e/test_weather_config.py`, `tests/integration/test_trip_report_scheduler.py`, `tests/unit/test_settings_protection.py`, `test_weather_config_strategy.py`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given `pyproject.toml` nach dem Refactor / When grep nach `nicegui` und `apscheduler` läuft / Then **0 Treffer**. Beide Dependencies entfernt + Ruff-Exceptions für `src/web/*` ebenfalls weg.
  - Test: (populated after /tdd-red)

- **AC-5:** Given `.claude/validate.py` und `.claude/commands/e2e-verify.md` / When grep nach `from web.main`, `python.*-m src.web.main`, `from web.scheduler` läuft / Then **0 Treffer**.
  - Test: (populated after /tdd-red)

- **AC-6:** Given Production nach Deploy / When `systemctl is-active gregor_zwanzig.service` läuft / Then Output `inactive`. Service ist disabled und gestoppt.
  - Verifikation: live SSH-Check nach Deploy
  - Test: (populated after /tdd-red — Live-Smoke-Skript-Test)

- **AC-7:** Given das Repo nach dem Refactor / When `uv run pytest tests/ -q --tb=no --co` (collect-only) läuft / Then sammelt es **mindestens 50 Tests weniger** als vor dem Refactor (weil 7 Test-Dateien weg sind, einige davon mit vielen Tests). 0 Collection-Errors durch fehlende Imports.
  - Test: (populated after /tdd-red — vorher/nachher-Vergleich)

## Out of Scope (für Phase A.3)

- **`gregor_zwanzig.service`-File aus `henemm-infra/` löschen** — Sister-Repo, separate PR, MQ an `infra`
- **CLAUDE.md aufräumen** → Phase B
- **`docs/specs/_template.md` um Schicht-Hinweis erweitern** → Phase B
- **`docs/specs/web_ui.md` als Legacy markieren** → Phase B
- **Code-Reviews der NiceGUI-Files vor Löschung** — wir vertrauen den vorherigen Phase-Verifikationen (Helper sind raus)

## Verification

- **Unit (scoped):** `uv run pytest tests/refactor/ tests/unit/test_gpx_*.py tests/unit/test_etappen_config.py tests/unit/test_trips_time_window_bugfix.py tests/tdd/test_compare_provider_routing.py tests/tdd/test_sport_aware_scoring.py -v` muss alle grün sein (verbleibende Refactor-Tests + Helper-Tests)
- **Smoke:** `uv run pytest tests/ -q --tb=no` — Vergleich Baseline vor #129 A.3 (Test-Anzahl + Failures)
- **Linter/Imports:** `uv run python -c "import api.main; print('Go-API import ok')"` darf keinen Fehler werfen
- **Live nach Prod-Deploy:**
  - `sudo systemctl is-active gregor_zwanzig.service` → `inactive`
  - `sudo journalctl -u gregor_zwanzig.service --since "5 min ago"` — kein Service-Restart-Loop
  - `curl -s https://gregor20.henemm.com/api/health` → 200
  - `curl -s https://gregor20.henemm.com/api/scheduler/status` → läuft mit 5 Jobs (Go-Scheduler)
  - `curl -s https://gregor20.henemm.com/` → 302 (Login-Redirect, normal)

## LoC-Estimate

- **Production-Code Löschungen:** ~3.700 LoC
- **Test-Code Löschungen:** ~600 LoC (geschätzt 50-60 Tests in 7 Dateien)
- **Hook/Doku-Anpassungen:** ~10 LoC (validate.py + e2e-verify.md + pyproject.toml)
- **Neue Refactor-Tests:** ~150 LoC (1 Datei mit 7 ACs)
- **Erwartetes LoC-Delta laut Workflow-Tool:** netto stark negativ (-4.000 LoC), aber Tool zählt evtl. nur additive. **Override auf 5000 für Sicherheit.**

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Production-Crash durch Service-Restart auf nicht-existierende Files | hoch wenn Service nicht vorher disabled | **Pflicht-Schritt 1:** systemctl disable VOR Push (siehe Implementation Details) |
| `.claude/validate.py` Hook crasht beim ersten Edit | mittel | **Pflicht-Schritt 2:** validate.py + e2e-verify.md anpassen VOR Lösch-Schritt |
| Vergessener Import irgendwo (z. B. obscure script) | mittel | AC-2 (grep-test) deckt das ab |
| `nicegui`-Dep raus → andere Files brechen | niedrig | Phase-2-Analyse hat 0 nicegui-Imports außerhalb von `src/web/` gefunden |
| 7 Test-Dateien Löschungen brechen pytest-Collection in anderen Files | niedrig | AC-7 prüft Collection-Sauberkeit |
| Sister-Repo `henemm-infra` hat noch Referenz auf gelöschten Service | niedrig | MQ an `infra` nach Phase A.3 fertig |
