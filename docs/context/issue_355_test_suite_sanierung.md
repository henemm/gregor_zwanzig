# Context: Test-Suite-Sanierung (#355)

## Request Summary

Die Backend-Suite (`uv run pytest`) ist mit **66 Failures über 21 Dateien** rot — durchweg
**Test-seitige Verwahrlosung, keine Produktions-Regression** (Prod läuft stabil). Ziel: Tests
gruppenweise an die Realität anpassen bzw. veraltete Tests entfernen, bis `uv run pytest` wieder
grün ist. Pro Test gilt: **erst feststellen ob Produktion korrekt (Test anpassen) oder echte
Regression (Produktion fixen)** — keine blinde Assertion-Anpassung, KEINE Mocks.

## Failure-Gruppen (nach Wurzelursache)

### Gruppe 1 — Workflow-Tooling stale (~37 Tests) — KLAR STALE
Testen abgeschaffte/umbenannte Tooling-Interna. Vorbild-Refresh: [[bug_333_test_issue_258_obsolete]].

| Datei | Anz | Ursache |
|-------|-----|---------|
| `test_epic_191_logbuch_audit.py` | 13 | Subprozesse ohne `GZ_ACTIVE_WORKFLOW` → `FATAL` (Symlink-Fallback deaktiviert, Commit 59bd925) |
| `test_e2e_check_verification.py` | 13 | ruft `e2e_commit_gate.find_project_root` — Funktion umbenannt zu `get_project_root` |
| `test_epic_191_state_migration.py` | 5 | alte State-Shape / Symlink-Auflösung |
| `test_epic_191_zeilenlimit.py` | 3 | `GZ_ACTIVE_WORKFLOW`-Auflösung im Subprozess |
| `test_epic_191_ac_format_pflicht.py` | 2 | workflow_gate-Live-Aufruf ohne Session-Env |
| `test_epic_191_adversary_verschaerfung.py` | 1 | override-ambiguous State-Schreibung |

### Gruppe 2 — Entfernte/verschobene Code-Struktur (7 Tests) — KLAR STALE
| Datei | Anz | Ursache |
|-------|-----|---------|
| `test_bug_281_290_stagestrip.py` | 4 | sucht `frontend/src/routes/_cockpit/StagePill.svelte` — existiert dort nicht mehr (Komponente verschoben/integriert; in Phase 2 neuen Pfad finden) |
| `test_epic_129a_1/2_module_structure.py` | 2 | `No module named 'web.pages.compare'` — NiceGUI-`web/pages`-Struktur im SvelteKit-Umbau entfernt |
| `test_issue_236_remaining_templates.py` | 1 | `G_BOX_WARNING_BG fehlt in compare_subscription.py` — Token verschoben/umbenannt (verifizieren) |

### Gruppe 3 — Veraltete Content/Design-Erwartungen (6 Tests) — KLAR STALE
| Datei | Anz | Ursache |
|-------|-----|---------|
| `test_weather_templates.py` | 3 | `assert len==14`/`==7`, Prod liefert korrekt 15 (Template erweitert) |
| `test_design_optimierungen.py` | 1 | erwartet `pure white`, Design nutzt gewollt `G_PAPER` rgb(246,244,238) Off-White |
| `test_trips_naming.py` | 2 | veraltete Terminologie-/Label-String-Erwartungen |

### Gruppe 4 — Golden-File-Drift (5 Tests) — PRÜFEN: Renderer-Änderung gewollt?
`test_email_plain_golden.py` (5): „Plain-Body-Drift" in arlberg/corsica/gr20/gr221-Fixtures.
Golden-Erwartung vs. aktueller Plain-Renderer. **Vor Neu-Generierung** prüfen, ob die
Renderer-Änderungen (vermutl. aus EPIC 9 Email-Design) gewollt waren — dann Golden neu sichern.

### Gruppe 5 — Test-Fixture-/Umgebungs-Drift (3 Tests) — PRÜFEN
| Datei | Anz | Ursache |
|-------|-----|---------|
| `test_wind_exposition_pipeline.py` | 2 | `_FakeWaypoint` fehlt `arrival_calculated` (Prod nutzt es: `trip_report_scheduler.py:548`, Issue #296) → Fake nachziehen; + „GratWind"-SMS-Label |
| `test_html_email.py` | 1 | `test_..._with_real_data`: „no HTML tables" — vermutl. Offline-Umgebung [[project_openmeteo_limit_diagnosis]] (#346 conftest autouse) liefert andere Daten; ggf. `@pytest.mark.live`/`@email` |

### Gruppe 6 — HÖCHSTE SORGFALT: mögliche echte Logik (5 Tests)
`test_friendly_format_email_and_alerts.py` (2), `test_friendly_format_and_alerts_config.py` (2),
`test_trip_alert.py::test_alerts_enabled_does_not_block` (1). Betrifft die
**display_config → Alert-Metric-Map**-Logik (`wind_max_kmh not in map`, `assert 1==0`,
`alerts_enabled_does_not_block`). **Könnte echte Regression ODER gewollte Semantik-Änderung
sein** — Einzelanalyse gegen aktuellen Produktionscode zwingend, nicht wegtesten.

### Gruppe 7 — Selbstreferentiell (1 Test)
`test_issue_201_mocks_removed.py::test_ac5_scoped_run_one_pass_one_skip`: Meta-Test, der pytest
auf andere Tests laufen lässt — wird grün, sobald die Ziel-Tests grün sind. Zuletzt re-prüfen.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `tests/conftest.py` | #346 autouse Offline-Fixture (`addopts = not email and not live`) — relevant für Gruppe 5 |
| `.claude/hooks/workflow.py`, `workflow_state_multi.py` | Tooling, das Gruppe 1 testet (korrekt; Tests stale) |
| `.claude/hooks/e2e_commit_gate.py` | `get_project_root` (Gruppe 1: Test ruft alten Namen) |
| `src/services/trip_report_scheduler.py:548` | nutzt `arrival_calculated` (Gruppe 5 Fake-Drift) |
| `src/output/renderers/email/*` | Plain-Renderer (Gruppe 4 Golden) |
| Alert-Map-Quelle (Phase 2: lokalisieren, vmtl. `src/services/*alert*`) | Gruppe 6 — echte-Logik-Verdacht |

## Existing Patterns

- **Refresh-Vorbild [[bug_333_test_issue_258_obsolete]]:** Session-Env-Vars per `monkeypatch.delenv`
  isolieren, Subprozess-Env mit `GZ_ACTIVE_WORKFLOW` versorgen, Production-Code byte-gleich lassen.
  Direkt auf Gruppe 1 (epic_191) übertragbar.
- **Source-Inspection-Tests** (vgl. #343 HorizonChip.test): bei verschobenen Dateien (Gruppe 2)
  nur den Pfad korrigieren, Assertion-Logik behalten.
- **Golden-Tests:** zentral neu generieren statt Hand-Edit, wenn Renderer-Änderung bestätigt gewollt.

## Dependencies

- **Upstream (Tests hängen daran):** Workflow-Tooling (#191/#325/#333-Umbau), SvelteKit-Migration
  (NiceGUI `web/` entfernt), EPIC 9 Email-Design, #346 Offline-Fixture, #296 Naismith.
- **Downstream (was die grüne Suite freischaltet):** Backend-Commits via `pre_commit_gate` (#352 nur
  noch scope-aware — Backend-Commits brauchen weiter grüne Suite, siehe
  [[project_precommit_gate_full_suite_block]]).

## Existing Specs

- Kein dedizierter Spec; Bezug: Workflow-Tooling-Specs (`epic_191_*`), #346 Fixture-Provider-Spec.

## Analyse-Ergebnisse (Phase 2, 2026-05-24)

Drei parallele Analyse-Agents haben die unklaren Gruppen verifiziert:

- **Gruppe 6 = STALE (KORRIGIERT 2026-05-24 — KEINE Regression):** Erste Einschätzung war
  „Regression", war aber FALSCH (Adversary kannte #131 nicht). `weather_change_detection.py`
  `from_display_config()` filtert **absichtlich** nach `mc.enabled`, nicht `alert_enabled` —
  **bewusste Design-Entscheidung in #131** (Commit 10e554c, 2026-05-14: „from_display_config()
  filtert auf mc.enabled (sichtbare Metriken)"). Die Wetter-Änderungs-Mail prüft alle angezeigten
  Metriken; `alert_enabled` gehört zum separaten Alarm-System (alert_rules/#222). Der voreilige
  Bug #356 wurde nach Verifikation als „kein Bug" zurückgezogen (Fix zurückgerollt). **Die 4 Tests
  (test_friendly_format_*) sind die VERALTETEN** (Feb–Mai, alte alert_enabled-Semantik, bei #131
  nicht nachgezogen) → in #355 an die `enabled`-Semantik anpassen ODER entfernen (der #131-Test
  `test_ac2_from_display_config_uses_enabled_not_alert_enabled` deckt das korrekte Verhalten ab).
  **Zusätzlich:** Docstring von `from_display_config` („Only metrics with alert_enabled=True") ist
  ebenfalls veraltet → auf `enabled`-Semantik korrigieren. **Lehre:** Adversary bei Semantik-Fragen
  NICHT auf wenige Dateien eingrenzen — er übersah den maßgeblichen #131-Test in tests/unit/.
- **Gruppe 4 (Golden, 5) = STALE:** Renderer-Profilzeile `◯ WETTER-BRIEFING` (Commits cc54224 #241,
  aac563b #255) gewollt; Golden neu generieren. `plain.py:123`.
- **Gruppe 5:** B1 `test_cumulative_distance_set` = STALE (Fake `_FakeWaypoint` um
  `arrival_calculated` erweitern, `test_wind_exposition_pipeline.py:92`). B3 `test_html_email`
  = STALE (Assertion `"<table>"` → `"<table "`, Renderer schreibt `<table class="matrix-table">`).
  B2 `test_sms_grat_wind_label` = **FEATURE-GAP** (WIND_EXPOSITION im SMS-Token-Pfad nie gebaut,
  β3-Deferral) → eigenes Feature-Issue, in #355 als `xfail` markieren.
- **Gruppe 2:** `test_bug_281_290_stagestrip` (4) + `test_epic_129a_*` (2) = OBSOLET-LÖSCHEN
  (StagePill/`routes/_cockpit/` + NiceGUI `web/pages/` entfernt). `test_issue_236::ac6` (1) =
  **UNKLAR**: `G_BOX_WARNING_BG` existiert in `design_tokens.py`, wird in `compare_subscription.py`
  nicht genutzt → Feature-Debt oder verwaister Token, klären (evtl. eigenes Issue).
- **Gruppen 1, 3, 7:** wie in Phase 1 — klar stale, mechanische Anpassung.

**Strukturierung (vom PO bestätigt):** (1) Alarm-Regression als eigener Bug zuerst + Deploy.
(2) #355 Test-Sanierung danach in Häppchen: A=Gruppe 1 (~37), B=Gruppen 2+3+4+5(B1/B3)+7 (~21),
Feature-Gaps (B2 WIND_EXPOSITION-SMS, ggf. #236-AC6) als eigene Issues + `xfail`/skip.

## Risks & Considerations

1. **Echte Regression im Test-Drift verstecken (Gruppe 6):** wenn Alert-Map-Tests blind angepasst
   werden, könnte ein echter Bug zementiert werden. → Gruppe 6 zuerst und einzeln gegen Prod-Code.
2. **Golden blind neu generieren (Gruppe 4):** würde eine unbeabsichtigte Renderer-Regression
   einfrieren. → Diff der Golden inspizieren, gegen EPIC-9-Intention prüfen.
3. **Umfang/LoC:** 66 Tests über 21 Dateien — über jedem Single-Workflow-Limit. Voraussichtlich
   `loc_limit_override` nötig; ggf. in thematische Teil-Lieferungen (Gruppe 1 / 2+3 / 4+5 / 6)
   splitten statt ein Riesen-Commit.
4. **KEINE Mocks** (Projektregel) — Gruppe-5/6-Fakes durch echte Fixtures ersetzen, nicht durch Mocks.
5. **Parallel-Sessions:** Working-Tree enthält Fremd-Arbeit (waypointEditor.test.ts u.a.) — beim
   Committen chirurgisch stagen ([[feedback_shared_index_commit]]).
