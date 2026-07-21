---
entity_id: issue_355_test_suite_sanierung
type: module
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [tests, maintenance, test-drift, backend]
issue: 355
---

# Issue #355 — Test-Suite-Sanierung (~66 veraltete Tests)

## Approval

- [ ] Approved

## Purpose

`uv run pytest` ist mit ~66 Failures über 21 Dateien rot — **durchweg Test-seitige Verwahrlosung,
keine Produktions-Regression** (Prod läuft stabil; in der #356-Klärung explizit verifiziert). Ziel:
Die Suite wieder grün, indem veraltete Tests an die heutige Code-Realität angepasst oder (bei
entferntem Code) gelöscht werden. **Leitprinzip: Produktionsverhalten wird NICHT geändert** —
Tests folgen dem Code, nicht umgekehrt. Eine grüne Suite schaltet Backend-Commits wieder frei
(siehe [[project_precommit_gate_full_suite_block]]).

## Scope

### In Scope (Test-Anpassung/-Löschung, keine Verhaltensänderung)

Sanierung in thematischen Teil-Lieferungen:

**Lieferung A — Workflow-Tooling-Tests (~37):** `test_epic_191_logbuch_audit` (13),
`test_e2e_check_verification` (13), `test_epic_191_state_migration` (5), `test_epic_191_zeilenlimit`
(3), `test_epic_191_ac_format_pflicht` (2), `test_epic_191_adversary_verschaerfung` (1). Muster wie
[[bug_333_test_issue_258_obsolete]]: Session-Env (`GZ_ACTIVE_WORKFLOW`) in Subprozessen
korrekt setzen/isolieren; `find_project_root`→`get_project_root` (umbenannt). Production-Tooling
unverändert.

**Lieferung B — verschobener/entfernter Code + veraltete Erwartungen (~21):**
- `test_bug_281_290_stagestrip` (4) + `test_epic_129a_1/2_module_structure` (2): Ziel-Code entfernt
  (StagePill/`routes/_cockpit/`, NiceGUI `web/pages/`) → **löschen** (Feature lebt in SvelteKit).
- `test_weather_templates` (3): Counts 14→15 / 7→aktuell anpassen.
- `test_trips_naming` (2): Terminologie-Strings an aktuelle UI anpassen.
- `test_design_optimierungen` (1): erwartet `pure white`; Soll ist `G_PAPER` rgb(246,244,238) →
  Erwartung an Design-Token anpassen.
- `test_email_plain_golden` (5): Golden-Dateien neu generieren (Renderer-Profilzeile aus #241/#255
  gewollt, `plain.py:123`).
- `test_wind_exposition_pipeline::test_cumulative_distance_set` (1): Test-Fake `_FakeWaypoint` um
  Feld `arrival_calculated` erweitern.
- `test_html_email::..._with_real_data` (1): Assertion `"<table>"` → `"<table "` (Renderer schreibt
  `<table class="matrix-table">`).
- `test_issue_201_mocks_removed::test_ac5_scoped_run...` (1): selbstreferentiell — wird grün, sobald
  die Ziel-Tests grün sind; zuletzt re-prüfen.

**Lieferung C — Alert-Map-Tests an #131-Semantik (4) + Docstring-Korrektur:**
- `test_friendly_format_email_and_alerts::test_only_alert_enabled_metrics_in_map` +
  `::test_per_metric_alert_config_used_in_detection`,
  `test_friendly_format_and_alerts_config::test_change_detection_uses_alert_config` +
  `::test_no_alerts_means_empty_thresholds`: erwarten die ALTE `alert_enabled`-Semantik. Die heutige
  (bewusste, #131) Semantik ist `enabled`. → Tests an `enabled`-Semantik anpassen ODER entfernen,
  da der maßgebliche #131-Test `test_ac2_from_display_config_uses_enabled_not_alert_enabled` das
  korrekte Verhalten bereits abdeckt.
- **Einzige Produktionscode-Änderung:** veralteten Docstring von
  `WeatherChangeDetectionService.from_display_config` („Only metrics with alert_enabled=True…") auf
  die `enabled`-Semantik korrigieren. Reine Doku, kein Verhalten.

### Out of Scope (eigene Issues, in #355 nur als `xfail`/skip mit Verweis)

- **WIND_EXPOSITION im SMS-Token-Pfad** (`test_sms_grat_wind_label`) — Feature-Gap (β3-Deferral),
  nie implementiert → eigenes Feature-Issue, Test `@pytest.mark.xfail(reason=…, strict=False)`.
- **`G_BOX_WARNING_BG` ungenutzt** (`test_issue_236::test_ac6_warning_banner_tokens`) — Feature-Debt
  oder verwaister Token → klären; bis dahin `xfail` oder Token-Nutzung in `compare_subscription.py`
  als eigenes Issue.
- Keine Änderung an Produktions-**verhalten** (nur der eine veraltete Docstring).
- Keine neuen Tests, kein Coverage-Ausbau.

## Source

- **Files (Tests):** die 21 in „In Scope" genannten Test-Dateien unter `tests/`.
- **File (Doku-Fix):** `src/services/weather_change_detection.py` (nur Docstring von
  `from_display_config`).
- **Golden-Daten:** `tests/golden/email/` Referenzdateien (neu generieren).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/conftest.py` | Test-Infra | #346 autouse Offline-Fixture (`addopts = not email and not live`) |
| `.claude/hooks/workflow.py`, `workflow_state_multi.py` | Tooling | korrektes Soll-Verhalten (Lieferung A) |
| `.claude/hooks/e2e_commit_gate.py::get_project_root` | Tooling | umbenannte Funktion (Lieferung A) |
| `src/app/trip.py::Waypoint.arrival_calculated` | Modell | Feld, das der Test-Fake nachziehen muss |
| `src/output/renderers/email/plain.py`, `compare_html.py` | Renderer | Golden/Assertion-Abgleich |
| #131-Test `test_ac2_from_display_config_uses_enabled_not_alert_enabled` | Test | maßgebliche `enabled`-Semantik |

## Expected Behavior

- **Input:** `uv run pytest` (Default-Marker `not email and not live`).
- **Output:** 0 Failures (alle ~66 vormals roten Tests grün; `xfail`-markierte Feature-Gap-Tests
  zählen nicht als Failure).
- **Side effects:** Keine Verhaltensänderung in `src/`, außer einer Docstring-Korrektur. Gelöschte
  Tests betreffen nur entfernten Code. Neu generierte Golden-Dateien spiegeln den aktuellen,
  gewollten Renderer-Stand.

## Acceptance Criteria

- **AC-1:** Given die Workflow-Tooling-Tests aus Lieferung A / When `uv run pytest tests/tdd/test_epic_191_*.py tests/tdd/test_e2e_check_verification.py -p no:cacheprovider` läuft / Then sind alle grün, ohne dass Produktionscode in `.claude/hooks/` geändert wurde (nur Test-/Fixture-Anpassung, z.B. Session-Env setzen, `get_project_root`).

- **AC-2:** Given die Tests gegen entfernten Code (StagePill, NiceGUI `web/pages/`) / When die Suite läuft / Then sind diese Tests entfernt (nicht mehr gesammelt), und kein verbleibender Test referenziert einen nicht-existenten Pfad/Modul.

- **AC-3:** Given die veralteten Erwartungs-Tests (weather_templates Counts, trips_naming, design_optimierungen pure-white, golden plain emails, html_email table-Assertion, _FakeWaypoint) / When die Suite läuft / Then sind alle grün durch Anpassung der Test-Erwartung an die aktuelle, gewollte Code-/Design-Realität — Produktionsverhalten unverändert.

- **AC-4:** Given die 4 Alert-Map-Tests, die die alte `alert_enabled`-Semantik erwarten / When sie an die heutige (#131) `enabled`-Semantik angepasst oder entfernt werden / Then ist `from_display_config()` unverändert (Code byte-gleich, nur Docstring korrigiert), die Tests grün, und der #131-Test `test_ac2_from_display_config_uses_enabled_not_alert_enabled` bleibt grün.

- **AC-5:** Given die zwei Feature-Gaps (WIND_EXPOSITION-SMS, `G_BOX_WARNING_BG`) / When die Suite läuft / Then sind ihre Tests `@pytest.mark.xfail` mit Begründung + Verweis auf das jeweilige Folge-Issue (keine stille Löschung eines noch gewollten Features).

- **AC-6:** Given die gesamte Sanierung abgeschlossen / When `uv run pytest -p no:cacheprovider` läuft / Then **0 failed** (xfail/xpass erlaubt), und es wurde KEINE Produktions-Verhaltensänderung eingecheckt (Diff in `src/` beschränkt auf den einen Docstring).

## Risks

1. **Versehentlich gewolltes Verhalten „weggetestet" oder echter Fehler zementiert.** Mitigation:
   pro Test geprüft ob Code korrekt (Phase 2 + #356-Klärung erbrachten: alle stale, kein Bug).
   Bei Lieferung C besonders: #131 ist maßgeblich, `alert_enabled`-Erwartung ist veraltet.
2. **Golden blind neu generieren friert eine unbeabsichtigte Renderer-Regression ein.** Mitigation:
   Diff der neuen Golden gegen alt inspizieren, gegen #241/#255-Intention (Profilzeile) abgleichen.
3. **Feature stillschweigend löschen statt tracken.** Mitigation: WIND_EXPOSITION-SMS + #236-AC6 als
   `xfail` mit Folge-Issue, nicht löschen.
4. **Umfang/LoC** (~66 Tests, 21 Dateien) über jedem Single-Workflow-Limit. Mitigation:
   `loc_limit_override` + Umsetzung/Commits je Teil-Lieferung (A/B/C) statt ein Riesen-Commit.
5. **Parallel-Sessions:** Working-Tree enthält Fremd-Arbeit → chirurgisch stagen
   ([[feedback_shared_index_commit]]).

## Tests

Keine NEUEN Produkt-Tests. Erfolgskriterium = bestehende Suite grün:
`uv run pytest -p no:cacheprovider` → 0 failed. Pro Lieferung gezielt die jeweilige Gruppe grün
fahren, am Ende die Gesamtsuite. KEINE Mocks (Projektregel) — Fakes durch echte Fixtures/Felder
ersetzen, nicht durch Mocks.

## Changelog

- 2026-05-24: Initial spec. Reine Test-Sanierung von ~66 veralteten Tests (kein Prod-Bug; #356 als
  Fehldiagnose zurückgezogen — die vermeintliche Alert-Regression ist die bewusste #131-Semantik).
  Drei Teil-Lieferungen A/B/C, zwei Feature-Gaps als `xfail` + Folge-Issues. Einzige Prod-Änderung:
  veralteter Docstring in `weather_change_detection.from_display_config`.
