---
entity_id: dispatch_orchestrator
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [dispatch, scheduler, trip, compare, refactor]
---

<!-- Issue #1207 — letzter Backend-Rest der Briefing-Subscription-Konsolidierung (Epic #1204/ADR-0023) -->

# Dispatch Orchestrator — EIN Versand-Orchestrator für Trip + Compare

## Approval

- [ ] Approved

## Purpose

Vereint die Python-seitige Versand-Orchestrierung von Trip-Briefings (`kind:"route"`)
und Vergleichs-Briefings (`kind:"vergleich"`) unter einem gemeinsamen Skelett
(per-User Settings, Fälligkeits-Loop, Config-Routing, Status-Persistenz), sodass
beide `kind`-Werte Nachrichtentypen auf EINEM Versandweg sind statt zweier
paralleler Stacks. Der Go-Cron-Auslöser ist bereits vereinheitlicht (#1250-S7c);
dies löst den letzten parallelen Backend-Rest darunter auf. Renderer-Templates,
Kanal-Policy und Empfänger-Policy bleiben pro `kind` divergent — der Umbau ist
ausdrücklich verhaltensneutral (AC-3).

## Source

- **File:** `src/services/dispatch_orchestrator.py` (NEU)
- **Identifier:** `run_briefing_dispatch(kind, user_id, hour)` + Strategy-Adapter
  `TripDispatchStrategy` / `CompareDispatchStrategy`

## Estimated Scope

- **LoC:** ~+250 bis +350 netto (überwiegend dünne Verdrahtung, keine Logik-Neuschöpfung) — LoC-Override (Limit 250) erforderlich
- **Files:** 1 neu (`dispatch_orchestrator.py`), 3 geändert (`scheduler_dispatch_service.py`, `trip_report_scheduler.py`, `api/routers/scheduler.py`), 1 neue Testdatei
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `report_config_resolver.resolve_report_render_options` | function | Typisierte Config-Auflösung für Trip (`kind="route"`) — einzig erlaubter Zugriffspfad (AC-2) |
| `report_config_resolver.resolve_compare_render_options` | function | Dict-basierte Config-Auflösung für Vergleich (`kind="vergleich"`) — einzig erlaubter Zugriffspfad (AC-2) |
| `trip_report_scheduler.TripReportSchedulerService` | class | Bestehende Trip-Engine; wird per Strategy delegiert, NICHT verschoben (Delegation statt Relocation) |
| `scheduler_dispatch_service` (Compare-Dispatch-Funktionen) | module | Bestehende Compare-Engine; wird per Strategy delegiert, NICHT verschoben |
| `compare_slot_scheduler.presets_due_for_hour` / `resolve_preset_slots` | function | Reine Fälligkeits-/Timing-Logik, bleibt als eigenständige Bibliothek erhalten (kein Versandweg mehr, aber weiter genutzt) |
| `notification_service.NotificationService` | class | Trip-Versand-Abstraktion (E-Mail + SMS + Telegram) — bleibt Trip-exklusiv |
| `output.channels.email.EmailOutput` | class | Direkter Compare-Versand (E-Mail-only) — bleibt Compare-Pfad, geteilter Sink über `mail_type` |
| `api/routers/scheduler.py` (`/api/scheduler/trip-reports`, `/api/scheduler/compare-presets-daily`) | router | Zwei bestehende Endpoints bleiben nach außen unverändert (Thin-Wrapper auf den Orchestrator) |
| `internal/scheduler/scheduler.go` | Go-Cron | Ruft weiterhin zwei HTTP-Endpoints auf und schreibt zwei `last_run`-Keys — bleibt unangetastet (AC-4) |

## Implementation Details

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/dispatch_orchestrator.py` | CREATE | Geteiltes Skelett + zwei Strategy-Adapter (~150-250 LoC) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `run_compare_presets_daily` wird Thin-Wrapper um den Orchestrator (~-80/+20 LoC) |
| `src/services/trip_report_scheduler.py` | MODIFY | `send_reports_for_hour` wird Thin-Wrapper + Strategy-Hooks (~±30 LoC) |
| `api/routers/scheduler.py` | MODIFY | Beide Endpoints auf den Orchestrator umverdrahtet (~10 LoC) |
| `tests/tdd/test_dispatch_orchestrator.py` | CREATE | Neue Verhaltens-Tests: geteiltes Skelett teilt Settings/Loop/Delay pro `kind` korrekt |

### Empfohlener technischer Ansatz: dünner geteilter Seam (Strategy-Skelett)

`run_briefing_dispatch(kind, user_id, hour)` kapselt genau das, was heute
dupliziert ist, und delegiert den Rest an eine kind-spezifische Strategie:

1. `Settings().with_user_profile(user_id)` — heute doppelt (Trip, Compare)
2. `strategy = _STRATEGY[kind]` (`route` → Trip-Adapter, `vergleich` → Compare-Adapter)
3. `strategy.pre_pass(...)` — kind-Hook (Trip: Catch-up-Marker-Verarbeitung; Compare: Auto-Pause-Loop)
4. `due = strategy.collect_due(...)` — Fälligkeitssammlung pro `kind`
5. Schleife mit Fehler-Isolation, `strategy.inter_mail_delay` zwischen Sends, Tally im kind-eigenen Format
6. Rückgabe im kind-eigenen Format (Trip: `(sent, failed)`; Compare: `count`/Status-Dict — **nicht** vereinheitlichen)

Divergenzen bleiben strikt in der Strategie gekapselt:

| Feld/Methode | Trip (`route`) | Compare (`vergleich`) |
|---|---|---|
| `inter_mail_delay` | 2.0s | 0 |
| `smtp_guard` | True, `(0,0)`-Early-Return | False (per-Preset) |
| `pre_pass` | Catch-up-Marker-Verarbeitung | Auto-Pause-Loop |
| `collect_due` | Morgen/Abend-Sammlung | `presets_due_for_hour` |
| `dispatch_one` | delegiert an `NotificationService` (E-Mail+SMS+Telegram) | delegiert an `EmailOutput` direkt (E-Mail-only) |
| `render_config_source` | `resolve_report_render_options(report_config, display_config, report_type)` | `resolve_compare_render_options(preset: dict)` |

Bestehende Entry-Points (`send_reports_for_hour`, `run_compare_presets_daily`)
bleiben namentlich und signaturgleich erhalten und werden zu Thin-Wrappern —
dadurch bleiben die zwei Go-Endpoints und die zwei `last_run`-Keys unangetastet
(AC-4 ohne Go-seitige Änderung erfüllt). Compare wird bewusst NICHT über
`NotificationService` geroutet (würde `kind`-Branches im Multi-Channel-Send
erzwingen → Gate-#811-Risiko + AC-3-Bruch); der geteilte Sink bleibt die
Channel-Schicht `EmailOutput.send(mail_type=...)`.

## Expected Behavior

- **Input:** Stündlicher Trigger vom Go-Cron `briefing_dispatch` — zwei separate
  HTTP-Aufrufe (`/api/scheduler/trip-reports`, `/api/scheduler/compare-presets-daily`)
  mit `user_id` und `hour`; `kind` ergibt sich implizit aus dem aufgerufenen Endpoint.
- **Output:** Trip liefert weiterhin `(sent, failed)` wie vor dem Umbau; Compare
  liefert weiterhin `count`/Status-Dict wie vor dem Umbau — beide Formen bleiben
  1:1 erhalten, kein einheitliches `DispatchResult`.
- **Side effects:** Status-/Snapshot-Persistenz pro `kind` unverändert; E-Mail-Versand
  für beide `kind`, zusätzlich SMS/Telegram nur für Trip; `/api/scheduler/status`
  zeigt weiterhin zwei getrennte Job-Zeilen.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat sowohl ein fälliges Trip- als auch ein fälliges
  Vergleichs-Briefing / When der stündliche `briefing_dispatch`-Job feuert / Then
  laufen beide Versände durch einen gemeinsamen Orchestrator, der anhand `kind`
  (`route`/`vergleich`) das passende Renderer-Template wählt, und der Vergleich
  hat keinen eigenständigen Versand-/Orchestrierungsweg mehr (die Fälligkeits-/
  Timing-Berechnung in `compare_slot_scheduler.py` bleibt als reine Bibliothek
  erhalten — sie ist kein eigener „Versandweg").
  - Test: `tests/tdd/test_dispatch_orchestrator.py` ruft `send_reports_for_hour`
    und `run_compare_presets_daily` für denselben `user_id`/`hour` auf und prüft
    per Import-/Aufruf-Introspektion, dass beide intern denselben
    `run_briefing_dispatch`-Einstieg durchlaufen (gemeinsames Settings-Laden,
    gemeinsame Delay-/Tally-Schleife) statt zweier unabhängiger Codepfade.

- **AC-2:** Given der Orchestrator ist konsolidiert / When ein Briefing über den
  gemeinsamen Orchestrator versandt wird / Then wird die Render-Config ausschließlich über
  `report_config_resolver.py` aufgelöst (kein Direktzugriff; Struktur-Verbot
  #1209 gilt weiter) — für `kind="route"` über `resolve_report_render_options`,
  für `kind="vergleich"` über `resolve_compare_render_options(dict)`.
  - Test: `tests/tdd/test_report_config_scheduler_structure.py` (bestehend, muss
    grün bleiben) plus neuer Test, der per `inspect`/AST prüft, dass weder
    `trip_report_scheduler.py` noch `scheduler_dispatch_service.py` noch
    `dispatch_orchestrator.py` Render-Config-Felder direkt aus Trip-/Preset-
    Objekten lesen, sondern nur über die zwei Resolver-Funktionsnamen.

- **AC-3:** Given die Konsolidierung ist verhaltensneutral gemeint / When
  Trip-Briefing und Vergleichs-Mail auf Staging real an `gregor-test@henemm.com`
  zugestellt werden / Then bestehen `briefing_mail_validator.py` (Marker
  `X-GZ-Mail-Type: trip-briefing`) bzw. `email_spec_validator.py` (Marker
  `X-GZ-Mail-Type: compare`) mit Exit 0, und die Mails sind inhaltlich identisch
  zum Stand vor dem Umbau.
  - Test: Staging-Trigger via internem Python-Port `localhost:8000`
    (`POST /api/scheduler/trip-reports?hour=&user_id=` bzw.
    `/compare-presets-daily`) mit Test-Trip/Test-Preset, deren einziger
    Empfänger `gregor-test@henemm.com` ist; IMAP-Abruf gegen Stalwart; beide
    Validatoren müssen Exit 0 liefern (PFLICHT vor „E2E bestanden").

- **AC-4:** Given `/api/scheduler/status` ist das Beobachtungsfenster / When der
  konsolidierte Orchestrator gelaufen ist / Then zeigt der Endpoint weiterhin
  zwei getrennte Job-Zeilen `trip_reports_hourly` und `compare_presets_daily`
  mit je `last_run`/`next_run` inkl. Fehlerstatus (die S7c-Sub-Job-Auflösung
  bleibt sichtbar; die Go↔Python-Schnittstelle mit zwei Endpoints und zwei
  `last_run`-Keys bleibt unangetastet).
  - Test: Nach einem Testlauf beider Endpoints `GET /api/scheduler/status`
    abfragen und prüfen, dass beide Job-Zeilen mit je eigenem `last_run.status`
    vorhanden sind (bestehender Go-Test `scheduler_unify_test.go` bleibt grün:
    8 Cron-Entries, 9 Job-Zeilen).

- **AC-5:** Given die deterministischen Bestands-Kern-Tests sind das
  Sicherheitsnetz gegen versehentliche Verhaltensänderung / When der
  Orchestrator eingeführt wird / Then bleiben
  `tests/tdd/test_compare_preset_slot_dispatch.py` (Slot-Timing),
  `tests/tdd/test_issue_1012_no_data_guard.py` (Trip `send_reports_for_hour`),
  `tests/tdd/test_compare_preset_loader.py` (Fälligkeits-Parität
  `due_old==due_new`) sowie die namens-/quelltext-gebundenen Tests
  (`test_bug_353`, `test_issue_872`, `test_report_config_scheduler_structure`)
  vollständig grün — Delegation statt Relocation, Entry-Point-Funktionen und
  Modulnamen bleiben erhalten.
  - Test: `uv run pytest tests/tdd/test_compare_preset_slot_dispatch.py
    tests/tdd/test_issue_1012_no_data_guard.py
    tests/tdd/test_compare_preset_loader.py tests/tdd/test_bug_353_trend_horizon.py
    tests/tdd/test_issue_872_threshold_ux.py tests/tdd/test_report_config_scheduler_structure.py`
    — alle grün ohne Anpassung an Assertion-Inhalte (nur Import-Pfade dürfen
    unverändert bleiben, keine Umbenennung von `TripReportSchedulerService`,
    `send_reports_for_hour`, `run_compare_presets_daily`, `send_one_compare_preset`).

## Known Limitations

Fünf bewusste Non-Goals (Tech-Lead-Entscheidung, durch AC-3 verhaltensneutral
determiniert, nicht aus dem Code ableitbar):

- **Tiefe:** dünner Seam (Strategy-Skelett), keine tiefe DTO-/Send-Verschmelzung
- **Compare-Kanäle:** bleibt E-Mail-only (SMS/Telegram wäre eigenes Feature, Issue-Scope schließt Template/Inhalt aus)
- **Compare-Empfänger-Policy:** bleibt verbatim erhalten (per-Preset-Liste) — Angleichung an Trip wäre eine Verhaltensänderung
- **Inter-Mail-Delay:** ~~Compare bleibt 0 (kein 2s-Delay dazugewinnen)~~ —
  **REVIDIERT per PO-Entscheidung 2026-07-16.** Das Non-Goal galt für den
  verhaltensneutralen Refactor `3ca3be14` und war dort richtig: der Refactor
  durfte kein Verhalten dazugewinnen. Inzwischen versendet Compare seit #1270
  drei Kanäle (E-Mail + Telegram + SMS) pro Preset; ohne Pause zwischen den
  Presets besteht Rate-Limit-Risiko bei Resend/Telegram. Trip hat diesen
  Schutz seit #766. Compare bekommt daher ebenfalls `inter_mail_delay = 2.0`.
- **Status-Semantik:** beide Tally-Formen bleiben 1:1 erhalten (kein einheitliches `DispatchResult`)

Latenter Nebenbefund (nicht in Scope, mögliches Folge-Issue): Compare-Presets
versenden an beliebige Adressen ohne Prüfung gegen die Nutzer-Registry —
potenzielle Multi-User-Isolations-Frage. Für #1207 verbatim erhalten
(verhaltensneutral). Ob das ein echtes Leck ist, ist ein separater
Triage-Punkt (Kandidat #1199 oder eigenes Issue bei nutzersichtbarem Risiko),
NICHT Teil dieses Refactors.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0023 (ergänzend ADR-0017 Output-Paket-Grenze)
- **Rationale:** Dieses Issue ist der letzte Backend-Rest der Briefing-
  Subscription-Konsolidierung (Epic #1204). ADR-0023 legt das geteilte
  `kind`-diskriminierte Modell fest und schreibt explizit fest, dass
  Renderer-Templates getrennt bleiben (E9) — der Orchestrator konsolidiert
  ausschließlich die Python-interne Versand-Orchestrierung darüber, verletzt
  aber nicht die Renderer-Trennung. ADR-0017 begrenzt Rendern (`renderers/`)
  und Versenden (`channels/`) als eigenes Ausgabe-Paket; die Konsolidierung
  bleibt strikt innerhalb dieser Grenze (kein Übergriff auf `channels/email.py`
  oder `renderers/`, sonst würde Gate #811 greifen).

## Test Coverage

Neue Tests in `tests/tdd/test_dispatch_orchestrator.py`:

- `test_shared_skeleton_single_entrypoint` — Trip- und Compare-Aufruf laufen
  über denselben `run_briefing_dispatch`-Einstieg (AC-1)
- `test_config_resolver_exclusive_access` — kein Direktzugriff auf Render-Config
  außerhalb der zwei Resolver-Funktionen (AC-2)
- `test_strategy_inter_mail_delay_preserved` — Trip 2.0s / Compare 0 bleiben
  pro `kind` unverändert (HIGH-Risiko-Punkt 1)
- `test_strategy_smtp_guard_preserved` — Trip `(0,0)`-Early-Return / Compare
  per-Preset-Guard bleiben kind-lokal (HIGH-Risiko-Punkt 2)
- `test_return_taxonomy_preserved` — Trip `(sent, failed)` vs. Compare
  `count`/Status-Dict bleiben unverändert, keine Vereinheitlichung (HIGH-Risiko-Punkt 3)
- `test_entry_points_unchanged_signature` — `send_reports_for_hour` und
  `run_compare_presets_daily` bleiben namens- und signaturgleich (Delegation,
  keine Relocation)

Bestehende Kern-Tests, die ohne Anpassung grün bleiben müssen (Sicherheitsnetz, AC-5):

- `tests/tdd/test_compare_preset_slot_dispatch.py`
- `tests/tdd/test_issue_1012_no_data_guard.py`
- `tests/tdd/test_compare_preset_loader.py`
- `tests/tdd/test_bug_353.py` (Logger-Name `trip_report_scheduler`)
- `tests/tdd/test_issue_872.py` (`inspect.getsource`-Assertion)
- `tests/tdd/test_report_config_scheduler_structure.py` (Struktur-Verbot #1209)

## Changelog

- 2026-07-16: Initial spec created — Issue #1207
- 2026-07-16: Non-Goal „Inter-Mail-Delay: Compare bleibt 0" revidiert
  (PO-Entscheidung). Compare erhält `inter_mail_delay = 2.0` wie Trip (#766),
  weil Compare seit #1270 drei Kanäle pro Preset versendet und ohne Pause
  Rate-Limits bei Resend/Telegram riskiert. Das ursprüngliche Non-Goal bleibt
  in „Known Limitations" durchgestrichen erhalten (Historie des
  verhaltensneutralen Refactors `3ca3be14`).
