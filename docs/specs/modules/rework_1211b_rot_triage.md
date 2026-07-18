---
entity_id: rework_1211b_rot_triage
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [testing, pytest, rot-triage, testsuite]
---

<!-- Issue #1211 — Sammelprojekt #1196 (Test-Aufräum-Programm), Scheibe 2b von 3
     (Scheibe 2a: Staging-Marker, Commit 41eb5727, LIVE; Scheibe 2c: Live-Modul-
     Feinschnitt, noch offen). Workflow: rework-1211b-rot-triage. -->

# Testsuite Scheibe 2b — Rot-Triage: 390 rote Tests auf 0 bringen (Issue #1211b)

## Approval

- [ ] Approved

## Purpose

Alle 390 im deterministischen Standard-Lauf roten Tests (98 Dateien, gemessen
2026-07-18 mit der 4-Etappen-Methode plus in-process Netz-Sperre) werden
gemäß der im Kontext-Doc bereits vorliegenden Triage in VIER Batches
behandelt: veraltete Tests löschen, echte Testfehler minimal fixen,
Live-abhängige Tests markieren (Muster Scheibe 2a) und echte Produkt-/
Tooling-Befunde als Bug-Issues dokumentieren + xfail versehen. Ziel: der
Kern-Testlauf ist danach durchgängig grün und bleibt es — kein „vorbestehend
rot" mehr im Sinne der CLAUDE.md-Test-Politik.

## Source

> Reine Test-Infrastruktur, kein einzelner Produktionscode-Ort. Betroffen
> sind ~95 Testdateien unter `tests/unit/`, `tests/integration/`,
> `tests/tdd/`, `tests/visual/`, `tests/red/` (vollständige Listen: siehe
> Batch-Tabellen unten) sowie `tests/tdd/test_pytest_collection_and_timeout_safety.py`
> (Wächter, Batch 3) und `docs/context/rework-1211b-rot-triage.md`
> (Triage-Wahrheit, wird als Status-Nachweis fortgeschrieben).

- **File:** siehe Batch-1..4-Tabellen (Datei-genaue Liste, Quelle:
  `docs/artifacts/rework-1211b-rot-triage/rotliste.json`, 98 Dateien, 387
  einzeln benannte rote Tests + 3 Errors laut Kontext-Doc-Messung).
- **Identifier:** pro Datei genau eine Aktion — (a) `DELETE` komplette Datei,
  (b) `MODIFY` Testfehler-Fix (Pfad/Assertion/Locator), (c) `MODIFY`
  `pytestmark = pytest.mark.email|live|staging`, oder (d) `MODIFY`
  `@pytest.mark.xfail(reason='#NNNN')` auf den betroffenen Testfunktionen.

## Estimated Scope

- **LoC:** Additions ~150–250 (Marker-Zeilen, xfail-Decorators,
  Pfad-/Assertion-/Locator-Fixes, Doku-Fixes) — Deletions dominieren das
  Diff: ~39 komplett gelöschte Testdateien + 4 Teil-Löschungen (geschätzt
  mehrere tausend Zeilen). Löschungen zählen nicht gegen das
  250-LoC-Additions-Limit (CLAUDE.md LoC-Regel).
- **Files:** ~95 Testdateien (98 rote Dateien − 1 Nicht-Scope − 2
  Nachtriage-Gap; 4 davon doppelt gezählt wegen Teil-Aufteilung über zwei
  Batches) + 1 Wächter-Datei (Batch 3) + `docs/context/rework-1211b-rot-triage.md`
  (Status-Update) + 5–6 neue GitHub-Issues (kein Datei-Diff im Repo, davon 1
  im externen Plugin-Repo `henemm/agent-os-openspec`)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-1211b-rot-triage.md` | intern | Single-Source-Triage-Wahrheit für alle 4 Batches |
| `docs/artifacts/rework-1211b-rot-triage/rotliste.json` | intern | Datei-genaue Rohdaten (98 Dateien, Test-IDs, Rot-Zahlen) — Grundlage aller Batch-Tabellen |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` (Scheibe 1+2a) | intern | Kollektions-Wächter, wird in Batch 3 um die 13 K3-Marker-Dateien erweitert |
| Scheibe 2a — `docs/specs/modules/rework_1211a_staging_marker.md`, Commit `41eb5727` | intern | Marker-Muster (Modul- vs. Teil-Marker) für Batch 3 |
| CLAUDE.md „Test-Politik: Zwei Schichten" (PO-go 2026-07-09) | Policy | Kern muss 0 failed/0 errors sein — Grundregel dieser Scheibe |
| CLAUDE.md „Nebenbefund-Triage" (PO-go 2026-07-09) | Policy | `[triage:a/b/c/po]`-Marker-Konvention für Batch-4-Bündel |
| Sammelprojekt #1196 / Issue #1211 | GitHub Issue | Übergeordnetes Test-Aufräum-Programm bzw. dessen Scheibe 2 |
| Plugin-Repo `henemm/agent-os-openspec` | extern | Ziel-Repo für Bundle-4-Issue (Plugin-Update-Regression) |
| Epic #1127 (Cross-Provider-Fallback), Folge-Issues #1143ff | GitHub Issue | Ziel für feature_734/761-xfail — keine Neuanlage |
| #1301-Session | GitHub Issue / parallele Session | `test_compare_dispatch_channel_fanout.py` bleibt unberührt (Nicht-Scope) |

## Implementation Details

```
1. Batch 1 (Löschungen): 39 Dateien komplett + 4 Dateien Teil-Löschung
   entfernen (siehe Batch-1-Tabellen). Jede Löschung referenziert die
   Beleg-Commits/Begründung aus dem Kontext-Doc im Commit-Text (AC-2).

2. Batch 2 (Testfehler-Fixes): 17 Dateien minimal fixen — GPX-Pfad-
   Konstanten, get_data_root-Assertion, #1133-Fixture-Kollision,
   Env-Var-Rename, timeout-Override, SMTP-Timeout, Format-Detail,
   2x Locator. Keine Assertion abschwächen (AC-5).

3. Batch 3 (Marker): 13 Dateien nach K3-Tabelle mit
   pytest.mark.email/live/staging versehen (Modul- oder Teil-Ebene,
   Muster Scheibe 2a). Wächter test_pytest_collection_and_timeout_safety.py
   um diese 13 Dateien erweitern (AC-4).

4. Batch 4 (Echte Befunde): 5 Bug-Issue-Bündel + 4 Einzel-Referenzen
   anlegen (gh issue create, [triage:]-Marker), betroffene Tests
   xfail(reason='#NNNN'). Doku-Drift (316/1165/765) direkt fixen,
   kein Issue.

5. Nachtriage GEKLÄRT (s. Source-Abschnitt): test_weather_metrics.py +
   test_trip_alert_stage_name.py → beide Batch 2 (Testfehler, minimal fixen).

6. Standard-Lauf (4-Etappen-Methode, Netz-Sperre) erneut ausführen,
   AC-1 verifizieren: 0 failed, 0 errors.
```

### Batch 1 — Löschungen (Veraltet)

**Gruppe K1 — 12 Dateien komplett löschen** (Testobjekte nachweislich bei
Plugin-Migration entfernt, Commits `33da201c`/`465380c1`/`f1e3acc1`):

| Datei | Rot | Änderungstyp |
|---|---|---|
| `tests/tdd/test_session_singleton_guard.py` | 24 | DELETE |
| `tests/tdd/test_issue_258_hook_arch.py` | 17 | DELETE |
| `tests/tdd/test_issue_828_express_path.py` | 16 | DELETE |
| `tests/tdd/test_edit_verify_hook.py` | 13 | DELETE |
| `tests/tdd/test_bug_565_compact_to_clear.py` | 12 | DELETE |
| `tests/tdd/test_issue_508_workflow_gate_none_verdict.py` | 11 | DELETE |
| `tests/tdd/test_bug_563_deploy_gate.py` | 7 | DELETE |
| `tests/tdd/test_issue_826_complete_verdict_gate.py` | 7 | DELETE |
| `tests/tdd/test_bug_548_workflow_output_readability.py` | 6 | DELETE |
| `tests/tdd/test_issue_895_singleton_guard_lifecycle.py` | 5 | DELETE |
| `tests/tdd/test_epic_191_state_migration.py` | 4 | DELETE |
| `tests/tdd/test_issue_960_complete_gate.py` | 4 | DELETE |

= 126 rote Tests, 12 Dateien komplett gelöscht.

**Gruppe K1-Ausnahme — Teil-Löschung** (Rest bleibt, siehe auch Batch 3/4):

| Datei | Rot betroffen | Aktion |
|---|---|---|
| `tests/tdd/test_issue_465_workflow_optimierung.py` | 7 (von 9 Tests) | DELETE nur die 7 roten Tests; 2 grüne `email_spec_validator`-Tests bleiben unangetastet |
| `tests/tdd/test_issue_384_hook_fail_open.py` | 1 von 11 (Count-Test) | DELETE nur den veralteten Count-Test; 10 verbleibende rote Tests → Batch 4 Bundle 2 (echter Befund) |
| `tests/tdd/test_fix_853_842_837_tooling_gates.py` | Teil (AC-1/AC-4-Tests) von 6 | DELETE nur AC-1/AC-4-Tests; `test_ac2` → Batch 3 (live-Marker); übrige AC-2-Tests bereits grün bei genauer Messung |

**Gruppe K4 — 9 Dateien komplett löschen** (Renderer seit #911/#912/#956/#995/#1003/#731/#1022 weiterentwickelt, alte Farben/Struktur):

| Datei | Rot | Änderungstyp |
|---|---|---|
| `tests/tdd/test_issue_623_trend_channels.py` | 7 | DELETE |
| `tests/tdd/test_issue_561_trend_v4.py` | 4 | DELETE |
| `tests/tdd/test_issue_669_outlook_thunder_badge.py` | 4 | DELETE |
| `tests/tdd/test_issue_722_email_compact.py` | 2 | DELETE |
| `tests/tdd/test_issue_884_mail_fidelity.py` | 2 | DELETE |
| `tests/tdd/test_issue_236_remaining_templates.py` | 2 | DELETE |
| `tests/tdd/test_issue_906_907_mail_render.py` | 1 | DELETE |
| `tests/tdd/test_issue_613_email_redesign.py` | 1 | DELETE |
| `tests/tdd/test_issue_997_validator_trend_row.py` | 1 | DELETE |

= 24 rote Tests, 9 Dateien komplett gelöscht.

**Gruppe K5 — 9 Dateien komplett löschen** (Telegram-Architektur-Entscheidungen
#1019 Registrierungs-Gate, #1250-S7a trips/→briefings/-Cutover, #697
On-Demand-Fetch, #731 CONFIG-Entfernung, #1133-Fixture):

| Datei | Rot | Änderungstyp |
|---|---|---|
| `tests/tdd/test_issue_697_telegram_on_demand_fetch.py` | 6 | DELETE |
| `tests/tdd/test_e2e_telegram_pipeline.py` | 3 | DELETE |
| `tests/tdd/test_issue_637_telegram_webhook.py` | 3 | DELETE |
| `tests/tdd/test_issue_655_telegram_callback_query.py` | 3 | DELETE |
| `tests/tdd/test_issue_744_telegram_bare_keywords.py` | 3 | DELETE |
| `tests/tdd/test_issue_653_telegram_tier2_timeline.py` | 1 | DELETE |
| `tests/tdd/test_issue_670_inbound_keywords.py` | 1 | DELETE |
| `tests/tdd/test_issue_1077_telegram_test_chat_isolation.py` | 1 | DELETE |
| `tests/tdd/test_issue_572_multi_user_routing.py` | 1 | DELETE |

= 22 rote Tests, 9 Dateien komplett gelöscht.

**Gruppe K6 — 9 Dateien komplett löschen:**

| Datei | Rot | Begründung |
|---|---|---|
| `tests/tdd/test_epic_404_phase2_ist_screenshots.py` | 16 | Löschkandidat aus 2a-Validierung |
| `tests/tdd/test_bug_405_sms_preview_screenshot.py` | 6 | Audit-Ordner weg |
| `tests/tdd/test_issue_892_prompt_field.py` | 3 | phase_listener weg |
| `tests/tdd/test_issue_403_triptabs_segmented.py` | 2 | atoms.test.ts weg |
| `tests/tdd/test_bug_567_stale_deploy_refs.py` | 1 | veraltet |
| `tests/tdd/test_bug_600_tdd_verhaltenstest.py` | 1 | veraltet |
| `tests/tdd/test_epic_191_adversary_verschaerfung.py` | 1 | veraltet |
| `tests/tdd/test_epic_191_zeilenlimit.py` | 1 | veraltet |
| `tests/tdd/test_worktree_state_routing.py` | 1 | veraltet |

= 32 rote Tests, 9 Dateien komplett gelöscht.

**Gruppe GEMISCHT-Teil (Löschanteil, Rest → Batch 4 Bundle 5):**

| Datei | Rot betroffen | Aktion |
|---|---|---|
| `tests/tdd/test_imap_stalwart_migration.py` | Teil (von 5) | DELETE nur den Teil, der auf gelöschtes `test_html_email.py` referenziert; Gmail-Default-Teil → Batch 4 Bundle 5 |

**Batch 1 Summe:** 39 Dateien komplett + 4 Dateien Teil-Löschung = 43 Dateien
berührt.

### Batch 2 — Testfehler-Fixes

| Datei | Rot | Fix |
|---|---|---|
| `tests/unit/test_gpx_parser.py` | 13 | Pfad-Konstanten auf `data/users/default/gpx/` umstellen |
| `tests/unit/test_elevation_analysis.py` | 8 | dito |
| `tests/unit/test_hybrid_segmentation.py` | 8 | dito |
| `tests/unit/test_segment_builder.py` | 6 | dito |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | 5 | dito (Muster `REAL_GPX_DIR` bereits vorhanden) |
| `tests/unit/test_gpx_upload_page.py` | 5 | dito |
| `tests/unit/test_etappen_config.py` | 4 | dito |
| `tests/tdd/test_gpx_proxy.py` | 4 | dito |
| `tests/integration/test_weather_snapshot.py` | 2 | Assertion auf `get_data_root()`-relativ umstellen (#1133-Isolation) |
| `tests/tdd/test_alert_log.py` | 4 | #1133-Fixture-Kollision beheben |
| `tests/tdd/test_briefing_log.py` | 4 | dito |
| `tests/tdd/test_issue_829_token_usage.py` | 3 | Env-Var-Rename `GZ_`→`OPENSPEC_` |
| `tests/tdd/test_622_fidelity_pre_actions.py` | 2 | fehlenden timeout-Override ergänzen |
| `tests/tdd/test_914_slice4_alert_sms_dispatch.py` | 1 | `smtp.invalid` ohne Timeout → Timeout ergänzen |
| `tests/tdd/test_utc_localtime.py` | 1 | Formatdetail — nach Prüfung fixen (nicht Erwartung abschwächen) |
| `tests/tdd/test_issue_911_mail_details.py` | 1 | Locator fixen (AC gültig und erfüllt) |
| `tests/visual/test_issue_956_email_pixel_diff.py` | 1 | Locator fixen |

= 17 Dateien, 72 rote Tests → grün, keine Assertion abgeschwächt (AC-5).

### Batch 3 — Marker (Live-Abhängig, exakt nach K3-Tabelle + 934/1035)

| Datei | Ziel | Marker | Ebene | Rot |
|---|---|---|---|---|
| `tests/tdd/test_account_page.py` | Prod-Domain (Go-API) | `live` | Modul | 8 |
| `tests/tdd/test_issue_1069_tier_channel_gating.py` | Staging (Playwright) | `staging` | Teil: nur TestAC4/5/6 | 3 |
| `tests/tdd/test_feature_770_inca_nowcast_fix.py` | GeoSphere INCA | `live` | Modul | 2 |
| `tests/tdd/test_issue_1037_massif_closure.py` | Präfektur-API (FR) | `live` | Teil: nur `_live_massifs`/fetch-Tests | 2 |
| `tests/tdd/test_issue_1142_geosphere_direct_fallback.py` | GeoSphere | `live` | Teil: AC-1/AC-2 | 2 |
| `tests/tdd/test_issue_645_telegram_outputerror_arity.py` | Telegram-API | `live` | Teil: 2 von 3 (3. dialt 127.0.0.1) | 2 |
| `tests/tdd/test_issue_731_unified_commands.py` | Live-Nowcast-Kette | `live` | Teil: nur TestAC3HeuteMorgen | 2 |
| `tests/tdd/test_scheduler_triggers.py` | IMAP-Polling | `email` | Teil: 2 `inbound_commands`-Tests | 2 |
| `tests/tdd/test_channel_test_button.py` | echter SMTP-Versand | `email` | Teil: 1 von 6 | 1 |
| `tests/tdd/test_issue_608_sms_seven_io.py` | seven.io | `live` | Teil: 1 Test | 1 |
| `tests/tdd/test_fix_853_842_837_tooling_gates.py` | prod_selftest → Prod-Health | `live` | Teil: nur `test_ac2` | 1 |
| `tests/tdd/test_issue_934_wizard_schedule.py` | lokaler Stack 3001/8091 + Login | `staging` | Modul | 6 |
| `tests/tdd/test_issue_1035_vigilance_source.py` | reale Vigilance-Lage | `live` | Teil/Modul (wetterlagenabhängig) | 1 |

= 13 Dateien, 33 rote Tests. Wächter `test_pytest_collection_and_timeout_safety.py`
wird um exakt diese 13 Dateien erweitert (Muster Scheibe 2a).

### Batch 4 — Echte Befunde (Bug-Issues + xfail)

**Bundle 1 — Mail/Render-Produktbugs `[triage:a]`:**

| Datei | Rot | Befund |
|---|---|---|
| `tests/tdd/test_email_profile_pipeline.py` | 11 | Profil-Signatur nie in HTML verdrahtet (`src/output/renderers/email/html.py:782`) |
| `tests/tdd/test_issue_255_profil_signaturen.py` | 2 | dito |
| `tests/tdd/test_issue_257_trip_briefing_polish.py` | 2 | dito (AC-8) |
| `tests/tdd/test_horizon_filter.py` | 1 | thunder-Spalte-Fehler |
| `tests/tdd/test_stage_weather_endpoint.py` | 1 | null-Serialisierung |
| `tests/tdd/test_bug_497_preview_content.py` | 1 | SMS-Präfix-Bug |
| `tests/tdd/test_report_config_render_contract.py` | 1 | Render-Contract-Bug |
| `tests/tdd/test_issue_277_css_variable_fallbacks.py` | 1 | CSS-Variable-Fallback-Bug (Ergänzung, s.u.) |

= 20 rote Tests, 1 Bug-Issue.

**Bundle 2 — Gate-/Tooling-Bugs `[triage:c]`:**

| Datei | Rot betroffen | Befund |
|---|---|---|
| `tests/tdd/test_issue_384_hook_fail_open.py` | 10 von 11 | 5 existierende, aktiv verdrahtete Hooks ohne Fail-open-Wrapping = Lockout-Falle |
| `tests/tdd/test_issue_603_design_fidelity_gate.py` | 5 | `pre_issue_close_design_gate.py` Exit 2 trotz gültigem Pass-Artefakt |
| `tests/tdd/test_issue_668_head_sha_dedup.py` | 2 | staging_gate-Dedup-Regression (Ex-#1132) |
| `tests/tdd/test_e2e_path_helper.py` | 1 | Gate-Helper-Bug |
| `tests/tdd/test_issue_816_alert_deviation.py` | 1 | deviation-alert-Validator-Bug |

= 19 rote Tests, 1 Bug-Issue.

**Bundle 3 — Isolation-Leck Dual-Modul `[triage:b]`:**

| Datei | Rot | Befund |
|---|---|---|
| `tests/tdd/test_952_onset_alert_fidelity.py` | 1 | `app.loader` vs. `src.app.loader` Dual-Modul-Leck (`api/routers/validator.py:23` unisoliert, 4 weitere `api/routers`-Dateien mischen Importe — nur Code-Fund, kein weiterer roter Test) |

= 1 roter Test, 1 Bug-Issue.

**Bundle 4 — Plugin-Update-Regression, Issue im externen Repo `henemm/agent-os-openspec`:**

| Datei | Rot | Befund |
|---|---|---|
| `tests/tdd/test_issue_753_746_hygiene.py` | 2 | Plugin-Update `d821e7c9` überschrieb Repo-Agent-Docs |
| `tests/tdd/test_external_validator_auth.py` | 1 | dito |

= 3 rote Tests, 1 Issue **im Plugin-Repo**, nicht in `gregor_zwanzig`.

**Bundle 5 — Ergänzung (im Kontext-Doc als „Echter Befund" gelistet, im
Bündel-Vorschlag des Auftrags keinem der 4 Bündel zugeordnet — hier
transparent nachgetragen, damit AC-2 vollständig erfüllbar ist):**

| Datei | Rot betroffen | Befund |
|---|---|---|
| `tests/tdd/test_imap_stalwart_migration.py` | Teil (Rest von 5) | Gmail-Default in `.claude/tools/output_validator.py:106` vergessen (`imap.gmail.com`, alte Env-Var-Namen) |

`test_issue_277_css_variable_fallbacks.py` ist bereits in Bundle 1
mit-erfasst (thematisch Rendering). Der Gmail-Rest von
`test_imap_stalwart_migration.py` bekommt ein eigenes Issue oder wird
Bundle 2 zugeschlagen (Tooling/Validator) — Entscheidung bei Umsetzung.

**Einzel-Referenzen (kein neues Bündel):**

| Datei | Rot | Ziel |
|---|---|---|
| `tests/tdd/test_feature_734_arome_france_nowcast.py` | 3 | xfail auf existierendes Epic-#1127-Folgeissue (#1143ff, KEINE Neuanlage) |
| `tests/tdd/test_feature_761_icon_d2_nowcast.py` | 2 | dito |
| `tests/tdd/test_feature_574_segment_km_header.py` | 3 | km-Header nie implementiert → xfail auf NEUES Issue `[triage:po]` |
| `tests/tdd/test_issue_883_acute_danger_override.py` | 1 | nie implementiert → xfail auf NEUES Issue `[triage:po]` (ggf. gebündelt mit feature_574, PO entscheidet) |
| `tests/red/test_issue_435_format_modes.py` | 1 | xfail(reason auf dokumentierten Spec-Restpunkt) — KEIN Issue, tests/red-Konzept bleibt bestehen |

**Direkt-Fixes (kein Issue, kein xfail — reine Doku-Drift/Hygiene, direkt
korrigieren):**

| Datei | Rot | Fix |
|---|---|---|
| `tests/tdd/test_issue_316_docs_cleanup.py` | 3 | Doku-Drift direkt fixen |
| `tests/tdd/test_issue_1165_adr_index_cleanup.py` | 1 | ADR-Duplikat direkt fixen |
| `tests/tdd/test_765_backend_hygiene_compliance.py` | 3 | Hygiene direkt fixen |

### Nicht-Scope

| Datei | Rot | Grund |
|---|---|---|
| `tests/tdd/test_compare_dispatch_channel_fanout.py` | 1 | #1301-Session — nur dokumentiert, unberührt; vor Abschluss mit #1301-Session klären oder als letzter xfail markieren (AC-1) |

### Nachtriage (geklärt 2026-07-18, Orchestrierer-Prüfung mit Code-/Git-Beleg — beide → Batch 2)

| Datei | Rot | Kategorie + Fix |
|---|---|---|
| `tests/unit/test_weather_metrics.py` | 1 | **Testfehler → minimal fixen**: `test_extended_aggregation_config_merged` asserted `len == 22` (Z.610), aber #1278/#1296 haben legitim eine 23. Metrik ergänzt — Zählwert + Kommentar aktualisieren, keine Erwartungs-Aufweichung |
| `tests/integration/test_trip_alert_stage_name.py` | 1 | **Testfehler → minimal fixen**: `_SVELTE_FILES` (Z.204) listet `trip-wizard/TripWizardShell.svelte`, die in `d7703708` (#1215 Toter-Code-Abbau) bewusst gelöscht wurde — stalen Listeneintrag entfernen, übrige Dateien werden weiter geprüft |

## Expected Behavior

- **Input:** `uv run pytest` Standardlauf (netzfrei, 4-Etappen-Methode mit
  in-process Netz-Sperre, wie in der Messung vom 2026-07-18)
- **Output:** 0 failed, 0 errors (xfail/xpass zählen nicht als failed); jeder
  der 390 vormals roten Tests ist entweder gelöscht (Batch 1), grün
  (Batch 2), aus der Standard-Selektion marker-verschoben (Batch 3) oder
  trägt `xfail(reason='#NNNN')` mit echter Issue-Nummer (Batch 4)
- **Side effects:** ~39 Testdateien verschwinden komplett aus dem Repo, 4
  weitere werden gekürzt; 5–6 neue GitHub-Issues (davon 1 im externen
  Plugin-Repo `henemm/agent-os-openspec`); Wächter
  `test_pytest_collection_and_timeout_safety.py` erweitert; Kontext-Doc als
  Status-Nachweis fortgeschrieben

## Acceptance Criteria

- **AC-1:** Given der vollständige Standard-Lauf (4-Etappen-Messmethode mit Netz-Sperre wie im Kontext-Doc), When alle vier Batches umgesetzt sind, Then ist das Ergebnis 0 failed und 0 errors (xfail/xpass zählen nicht als failed; der einzige unberührte Rest ist test_compare_dispatch_channel_fanout, der vor Abschluss mit der #1301-Session geklärt oder als letzter xfail markiert wird).
  - Test: erneuter 4-Etappen-Lauf mit in-process Netz-Sperre (identische Methode wie die Ausgangsmessung), JUnit-XML je Etappe, 0 failed + 0 errors über alle 4 Etappen summiert.

- **AC-2:** Given die Triage-Tabelle in docs/context/rework-1211b-rot-triage.md, When die Scheibe schließt, Then ist JEDER der 390 roten Tests genau einer Kategorie zugeordnet und jede Löschung/xfail/Marker-Setzung ist dort (bzw. im Commit) auf die Kategorie rückführbar — kein Test verschwindet unbegründet.
  - Test: Abgleich der finalen Batch-Tabellen dieser Spec (98 Dateien, inkl. der 2 Nachtriage-Gap-Dateien nach Klärung) gegen `rotliste.json` — jede Datei/jeder Test hat eine dokumentierte Aktion mit Begründung.

- **AC-3:** Given ein als „Echter Befund" kategorisierter Test, When die Scheibe schließt, Then existiert das zugehörige Bug-Issue (mit [triage:]-Marker) und der Test trägt `xfail(reason='#NNNN')` mit der echten Issue-Nummer — kein xfail ohne Issue-Referenz (Ausnahme: feature_734/761 referenzieren existierende #1127-Folge-Issues; tests/red-Fall referenziert den dokumentierten Spec-Restpunkt).
  - Test: `gh issue view` je erzeugtem Issue (5 im gregor_zwanzig-Repo + 1 im Plugin-Repo `henemm/agent-os-openspec`, dort repo-qualifiziert zitiert), plus Grep über alle Batch-4-Testdateien auf `xfail(reason=` mit gültiger Issue-Referenz.

- **AC-4:** Given die Batch-3-Marker, When `pytest --collect-only` mit Standard-Selektion bzw. `-m email/live/staging` läuft, Then sind die neu markierten Tests aus der Standard-Selektion verschwunden, unter ihrem Marker aber weiterhin sammelbar (Partition wie 2a-Wächter), und der erweiterte Wächter beweist das.
  - Test: `test_pytest_collection_and_timeout_safety.py` neue Testfunktionen — echte `pytest --collect-only`-Subprozesse für die 13 Batch-3-Dateien, analog Scheibe 2a (kein Mock, kein Dateiinhalt-Grep).

- **AC-5:** Given die Batch-2-Fixes, When die betroffenen Dateien einzeln ausgeführt werden (netzfrei), Then sind alle vormals roten Tests dieser Dateien grün — ohne dass eine Assertion abgeschwächt wurde (Pfad-/Fixture-/Locator-Korrekturen, keine Erwartungs-Aufweichung).
  - Test: `uv run pytest <datei>` je der 17 Batch-2-Dateien, Diff-Review zeigt ausschließlich Pfad-/Assertion-Ziel-/Locator-Korrekturen, keine geänderten Erwartungswerte ohne fachliche Begründung.

- **AC-6:** Given die Löschungen aus Batch 1, When ein Test-Objekt noch existiert und aktuelles Verhalten prüfbar wäre, Then wurde die Datei NICHT gelöscht, sondern nur die veralteten Teile (belegt durch die GEMISCHT-Urteile im Kontext-Doc: 465er behält 2 grüne Tests, 384er behält die 10 Fail-open-Tests als xfail, fix_853 behält AC-2).
  - Test: Diff-Review der 4 GEMISCHT-Dateien (test_issue_465, test_issue_384, test_fix_853_842_837, test_imap_stalwart_migration) zeigt Teil-Löschung statt Datei-Löschung; die verbleibenden Tests laufen weiterhin (grün oder xfail, nicht ersatzlos entfernt).

## Known Limitations

- Echte Befunde werden NICHT in dieser Scheibe gefixt (nur Issue+xfail) —
  Produkt-/Gate-Fixes sind eigene Workflows.
- Reihenfolge-Verschmutzung Voll-Lauf (#1180) bleibt offen; AC-1-Messung
  nutzt die Etappen-Methode.
- LoC: Batch 2+3+4 Additions geschätzt 150–250; Löschungen dominieren das
  Diff. Falls Limit reißt → `loc_limit_override` NUR mit PO-Erlaubnis.
- Scheibe 2c (live-Modul-Feinschnitt) bleibt eigenes Vorhaben.
- Die zwei ursprünglich untriagierten Tests (test_weather_metrics, test_trip_alert_stage_name) sind nachtriagiert und Batch 2 zugeordnet (s. Source).
- Kontext-Doc nennt 390 rot (387 failed + 3 errors); `rotliste.json` führt
  387 Tests über 98 Dateien datei-genau auf — die 3 zusätzlichen „Errors"
  sind darin nicht als Einzeltest sichtbar (vermutlich Collection-Errors ohne
  Testnamen) und müssen bei Umsetzungsbeginn identifiziert und derselben
  Vier-Kategorien-Logik zugeordnet werden.
- GEMISCHT-Dateien mit unklarer exakter Testzahl-Aufteilung
  (`test_fix_853_842_837_tooling_gates.py`, `test_imap_stalwart_migration.py`):
  Batch-Zuordnung ist auf Datei-Ebene dokumentiert, die exakte
  Test-zu-Batch-Zuordnung MUSS bei Umsetzung anhand der Testnamen im Code
  verifiziert werden.
- Bundle 4 (Plugin-Update-Regression) erzeugt ein Issue im externen Repo
  `henemm/agent-os-openspec`, nicht in `gregor_zwanzig` — der xfail-reason
  zitiert dort repo-qualifiziert (z.B. `xfail(reason='agent-os-openspec#NN')`),
  da kein lokales `gregor_zwanzig`-Issue diesen Bug behebt (Cross-Repo-
  Konvention, siehe CLAUDE.md-Referenz „Gate-/Hook-Bugs gehören ins
  Plugin-Repo").
- Bundle 5 (`test_issue_277_css_variable_fallbacks.py`,
  `test_imap_stalwart_migration.py`-Gmail-Rest) ist eine Ergänzung dieser
  Spec zum Bündel-Vorschlag aus dem Auftrag — beide sind im Kontext-Doc als
  „Echter Befund" gelistet, aber im ursprünglichen 4-Bündel-Vorschlag
  keinem Bündel explizit zugeordnet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Test-Infrastruktur-Konvention, keine
  produktseitige Architektur — analog Scheibe 2a)
- **Rationale:**
  1. Die 4-Etappen-Messmethode mit in-process Netz-Sperre (socket.connect
     gepatcht, localhost erlaubt) wird als wiederholbarer Abnahme-Mechanismus
     für AC-1 festgelegt. Verworfene Alternative: ein einzelner Voll-Lauf
     ohne Netz-Sperre — verworfen wegen des Risikos von echtem
     Mail-/API-Traffic (Rate-Limits, versehentlicher Live-Versand) und
     Hängern bei nicht abgesicherten Live-Dialern, die den gesamten Lauf
     blockieren würden.
  2. `tests/red/` bleibt strukturell unangetastet (Konzept „bewusst
     dauerhaft rot" bleibt bestehen als dokumentiertes Known-Red-Backlog);
     nur der eine rote Test darin bekommt `xfail` auf den dokumentierten
     Spec-Restpunkt. Eine `addopts`-Änderung (z.B. `--ignore=tests/red/`
     ergänzen, um die Doku-Realitäts-Lücke zu schließen, dass die Doku
     einen Ausschluss behauptet, den `addopts` faktisch nicht enthält) wurde
     erwogen und verworfen — das läge außerhalb des Scopes dieser Scheibe
     und wäre ein eigener Regel-Budget-Eingriff (CLAUDE.md).

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1211, Sammelprojekt #1196,
  Scheibe 2b (Rot-Triage), folgt auf Scheibe 2a (Commit `41eb5727`)
