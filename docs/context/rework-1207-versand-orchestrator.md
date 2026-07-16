# Context: rework-1207-versand-orchestrator

**Issue:** #1207 — „Ein Versand-Orchestrator für Trip + Compare: Python-Pfad konsolidieren (Rest aus Epic #1204)"
**Track:** Full Process · Modell Opus
**Erstellt:** 2026-07-16

## Request Summary

Der Cron-**Auslöser** ist bereits vereinheitlicht (#1250-S7c: ein Go-Cron-Eintrag `briefing_dispatch`). Unterhalb davon ist die Python-**Orchestrierung** aber weiter dreigeteilt. Ziel: **EIN** Versand-Orchestrator, in dem Trip (`kind:"route"`) und Vergleich (`kind:"vergleich"`) **Nachrichtentypen auf einem Weg** sind — statt zweier paralleler Versandwege. Rendering-Grenze (ADR-0011) und Versand (ADR-0017) sind bereits geteilt; der Orchestrator darüber ist der letzte parallele Backend-Stack.

## Architektur-Überblick (Ist)

Go = HTTP/Cron-Layer, Python = Dispatch-/Render-Engine (FastAPI-Core, `localhost:8000`). Go-Cron ruft Python-Endpoints synchron per HTTP auf.

```
Go-Cron  briefing_dispatch (0 * * * *)   internal/scheduler/scheduler.go:106
  └─ briefingDispatch()                    scheduler.go:188
       ├─ tripReports()          → POST /api/scheduler/trip-reports?user_id=<id>        scheduler.go:193/195
       └─ comparePresetsDaily()  → POST /api/scheduler/compare-presets-daily?user_id=<id>  scheduler.go:282/285
             └─ pingHeartbeat NUR bei compare.status==ok                                  scheduler.go:290-292
```

Beide Fan-outs iterieren über alle registrierten User (`runForAllUsers`, `scheduler.go:148`, continue-on-error) und hängen `?user_id=<id>` an (`scheduler.go:327`).

## Die drei Python-Dateien

| Datei | LoC | Rolle | Form |
|---|---|---|---|
| `src/services/trip_report_scheduler.py` | 1.626 | Trip-Briefing-Engine: lädt Trips, Wetter-Anreicherung (Ensemble/Gewitter/Stabilität/Tageslicht/amtliche Warnungen), baut DTO, delegiert Render+Versand an `NotificationService` (multi-channel) | Klasse `TripReportSchedulerService` (`:128`) |
| `src/services/scheduler_dispatch_service.py` | 391 | Compare-Preset-Dispatch: lädt Presets, Slot-Fälligkeit, `ComparisonEngine`, rendert Compare-Mail, versendet **direkt via `EmailOutput`** (nur E-Mail), persistiert Status | Modul-Funktionen |
| `src/services/compare_slot_scheduler.py` | 100 | **Reine** Slot-/Fälligkeits-Rechenlogik, kein IO, kein Versand. Einziger Importer: `scheduler_dispatch_service.py:22` | `resolve_preset_slots` (`:36`), `presets_due_for_hour` (`:58`) |

### Entry-Points
- **Trip Cron:** `TripReportSchedulerService.send_reports_for_hour(hour)` (`:184`) via `api/routers/scheduler.py:28`
- **Compare Cron:** `run_compare_presets_daily(user_id, hour)` (`:27`) via `api/routers/scheduler.py:129`
- **Trip Einzel/Test:** `send_test_report` (`:509`), `send_on_demand_report` (`:533`, Inbound-Kommando)
- **Compare Einzel:** `send_compare_preset` (`:341`) via `api/routers/scheduler.py:204`

## Aufruf-Ketten (Ist)

**Trip:** `send_reports_for_hour` `:184` → `_get_active_trips` `:384` → `_send_trip_report_outcome` `:581` (Segmente, Wetter, `resolve_report_render_options` `:636`, DTO) → `NotificationService.send_trip_report` (`notification_service.py:211`) → `TripReportFormatter.format_email` → Kanäle E-Mail/SMS/Telegram → `EmailOutput.send` (`email.py:369`, `mail_type="trip-briefing"`).

**Compare:** `run_compare_presets_daily` `:27` → `presets_due_for_hour` (`compare_slot_scheduler.py:58`) → `send_one_compare_preset` `:245` (Empfänger `:273`, Orte, `ComparisonEngine.run`, `resolve_compare_render_options` `:307`) → `render_compare_email` `:310` → `EmailOutput(settings).send(to=empfaenger, mail_type="compare")` `:322` → SMTP `email.py:539`. Danach `_write_compare_alert_snapshots` + `save_compare_preset_status`.

## Geteilt vs. divergent

### Dupliziert (Konsolidierungs-Kandidaten — das eigentliche Ziel)
- Per-User `Settings().with_user_profile(user_id)` (Trip `:148` / Compare `:95`, `:366`)
- Stündlicher Fälligkeits-Loop mit Morgen/Abend-Slots (Trip `send_reports_for_hour` `:209`; Compare `presets_due_for_hour`)
- Pause-/Enabled-/Runtime-Guards (Trip `_get_active_trips` `:410`; Compare `presets_due_for_hour` `:75`)
- `EmailOutput(...).send(..., mail_type=...)`-Aufruf mit Marker-Header (#1124)
- Render-Optionen über dasselbe Modul `report_config_resolver.py`
- Status-/Snapshot-Persistenz nach Versand

### Echte Divergenz (darf NICHT naiv zusammengelegt werden)
| Aspekt | Trip | Compare |
|---|---|---|
| **Renderer** | `TripReportFormatter.format_email` | `render_compare_email` — **ADR-0023 E9: Templates bleiben getrennt** |
| **Versand-Delegation** | `NotificationService` (E-Mail **+ SMS + Telegram**) | `EmailOutput` direkt, **nur E-Mail** |
| **Empfänger** | Profil-`mail_to` (keine per-Trip-Liste) | per-Preset `empfaenger`-Liste, `mail_to`-Fallback |
| **Config-Quelle** | typisierte Dataclasses (`trip.report_config`/`display_config`) | rohes Preset-`dict` von Platte |
| **Resolver-Signatur** | `resolve_report_render_options(report_config, display_config, report_type)` `:102` | `resolve_compare_render_options(preset: dict)` `:166` |
| **Catch-up** | volle `pending_briefings.json`-Nachliefer-Maschinerie (`:319-370`) | **keine** |
| **Zieldatum** | morning=heute / evening=morgen | morning=today / evening=today+1 |

## Fundamente (bereits geliefert)

- **`report_config_resolver.py`** — zentrale Config-Zuleitung (#1203 geschlossen). Zwei reine Funktionen mit **unterschiedlichen Signaturen** (typisiert vs. dict). Trip nutzt sie (`:636`), Compare nutzt sie (`dispatch:267,307`), `compare_slot_scheduler.py` nutzt sie nicht.
- **`kind`-Schema (ADR-0023 / #1230)** — Werte **`"route"` / `"vergleich"`** (nicht "compare"). Go kanonisch (`briefing_subscription.go:20-25`, Feld auf `trip.go:159`, `compare_preset.go:102`). Python unterscheidet über rohen JSON-Wert `data.get("kind")` (`loader.py:304,397`). Beide kinds liegen als getrennte Dateien in `data/users/<id>/briefings/<id>.json` — **kein** Union-Modell auf Platte.
- **`/api/briefings*`** — Go-API, `kind` immer Pflicht/explizit, 400 `kind_required` sonst (`briefing_subscription.go`).

## ADRs (verbindliche Grenzen)

- **ADR-0011** (`docs/adr/0011-...`): Render-Logik **ausschließlich Python-Backend**, reine Funktionen, ein Renderer.
- **ADR-0017** (`docs/adr/0017-output-paket-konsolidierung.md`): EIN Ausgabe-Paket `src/output/` — `renderers/` **erzeugen**, `channels/` **versenden**. Nur `NotificationService` orchestriert Renderer+Transporte.
- **ADR-0023** (`docs/adr/0023-briefing-subscription-shared-model.md`): geteiltes `kind`-diskriminiertes Modell + `briefings/`-Persistenz; **Renderer-Templates bleiben getrennt (E9)**; verlustfreie Migration.

## Observability-Constraint (AC-4, kritisch)

Der Go-Scheduler macht **zwei getrennte HTTP-Calls** und schreibt **zwei getrennte `last_run`-Keys** via `recordRun()` (`scheduler.go:296`):
- `trip_reports_hourly` (`:194`)
- `compare_presets_daily` (`:284`)

`/api/scheduler/status` expandiert `briefing_dispatch` zu **einer Zeile pro Sub-Job** (`scheduler.go:436-459`) → nach außen weiterhin zwei Job-Zeilen. `scheduler_unify_test.go` prüft: 8 Cron-Entries, aber 9 Job-Zeilen, beide Sub-Jobs mit `last_run.status`. Heartbeat hängt an `compare_presets_daily.status==ok`.

**Folge:** Wird die Python-Seite zu EINEM Orchestrator konsolidiert, müssen die **zwei Go-Endpoints + zwei `last_run`-Keys erhalten bleiben** (sonst Observability-Regression + roter Go-Test). Die Konsolidierung ist ein Python-internes Refactoring, das die Go↔Python-Schnittstelle (zwei Endpoints) unangetastet lassen kann/sollte.

## Risiken & Überlegungen (Input für /20-analyse)

1. **„EIN Orchestrator" ≠ „alles zusammenlegen".** Renderer bleiben getrennt (E9), Kanal-Policy divergiert (Compare nur E-Mail), Empfänger-Policy divergiert, Catch-up nur Trip. Der richtige Schnitt ist vermutlich: gemeinsames **Orchestrierungs-Skelett** (per-User Settings, Fälligkeits-Loop, Config-Routing, `send(mail_type=...)`, Status-Persistenz) mit `kind`-Verzweigung für Renderer/Kanäle/Empfänger — passend zur CLAUDE.md-Invariante „Trip/Compare möglichst viel teilen".
2. **Verhaltensneutralität (AC-3) ist hart.** Beide Mails müssen inhaltlich identisch bleiben, bewiesen via `briefing_mail_validator.py` **und** `email_spec_validator.py` (Exit 0) gegen echte Staging-Mail. Jede Änderung am Rendering-Ergebnis ist ein Verstoß.
3. **Renderer-Mail-Gate #811** triggert bei Edits an `channels/email.py` / `renderers/email/*`. Wenn der Umbau nur die *Orchestrierung* betrifft und die Inhalts-/Channel-Dateien nicht anfasst, lässt sich das Gate vermeiden — sonst greift es (test_issue_811 + briefing_mail_validator vor Commit).
4. **Multi-User-Isolation.** Compare-Empfänger sind aktuell beliebige per-Preset-Adressen (keine Registry-Prüfung); Trip strikt Profil-`mail_to`. Diese Policy-Differenz darf durch die Konsolidierung **nicht** verwischt werden (kein Cross-User-Leck, kein versehentliches Aufweichen der Trip-Beschränkung).
5. **Config-Routing.** AC-2: ausschließlich über `report_config_resolver.py`, kein Direktzugriff (Struktur-Verbot #1209 gilt weiter). Die zwei unterschiedlichen Signaturen (typisiert vs. dict) müssen im Orchestrator sauber per `kind` geroutet werden.
6. **LoC-Limit.** 250/Workflow wird bei ~2.100 LoC Konsolidierungsfläche gesprengt — Override in der Implementierungsphase gezielt erfragen.
7. **Nicht in Scope:** Frontend/Editor (#1206/#1273), Mail-Inhalt/Templates (E9: zwei Templates bleiben). `compare_slot_scheduler.py` ist reine Timing-Logik — soll als eigener „Versandweg" verschwinden (in den Orchestrator absorbiert), die *Timing-Berechnung* selbst bleibt aber nötig.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py` | Trip-Engine — größter Konsolidierungs-Block |
| `src/services/scheduler_dispatch_service.py` | Compare-Dispatch — zweiter Versandweg |
| `src/services/compare_slot_scheduler.py` | Compare-Slot-Timing — als eigener Weg auflösen |
| `src/services/report_config_resolver.py` | Zentrale Config-Auflösung (AC-2) |
| `src/services/notification_service.py` | Trip-Versand-Abstraktion (multi-channel) |
| `src/output/renderers/comparison.py` / `email/compare_html.py` | Compare-Renderer (bleibt) |
| `src/output/renderers/trip_report.py` | Trip-Renderer (bleibt) |
| `src/output/channels/email.py` | Mailversand (Gate #811!) |
| `api/routers/scheduler.py` | Python-Trigger-Endpoints |
| `internal/scheduler/scheduler.go` | Go-Cron, zwei HTTP-Calls, zwei last_run-Keys (AC-4) |
| `internal/scheduler/scheduler_unify_test.go` | Go-Test, der 9 Job-Zeilen erzwingt |

## Existing Specs / ADRs
- `docs/adr/0011-alert-render-single-backend-renderer.md`
- `docs/adr/0017-output-paket-konsolidierung.md`
- `docs/adr/0023-briefing-subscription-shared-model.md`

---

## Analysis

### Type
Feature / **Rework** (Refactoring, verhaltensneutral). Kein Bug.

### Technischer Ansatz (empfohlen): dünner geteilter Seam, keine tiefe Verschmelzung

Neue Datei `src/services/dispatch_orchestrator.py` mit **einem** geteilten Skelett `run_briefing_dispatch(kind, user_id, hour)` + zwei `kind`-Strategien (Strategy/Template-Method). Die Strategien **delegieren an den bestehenden Code**, verschieben ihn NICHT.

**Geteiltes Skelett** (das eigentliche „EIN Orchestrator"):
1. `Settings().with_user_profile(user_id)` (heute doppelt: Trip `:148`, Compare `:95/:366`)
2. `strategy = _STRATEGY[kind]`
3. `pre_pass` (kind-Hook: Trip Catch-up / Compare Auto-Pause)
4. `due = strategy.collect_due(...)`
5. Loop mit Fehler-Isolation + `strategy.inter_mail_delay` + Tally
6. Rückgabe im kind-eigenen Format

**Strategy-Interface** (kapselt die echten Divergenzen):
| Feld/Methode | Trip (`route`) | Compare (`vergleich`) |
|---|---|---|
| `inter_mail_delay` | **2.0s** (`:241`) | **0** (kein Delay heute) |
| `smtp_guard` | True, `(0,0)`-Early-Return (`:203`) | False (per-Preset) |
| `pre_pass` | `_process_pending_markers` (`:245`) | Auto-Pause-Loop (`:62-86`) |
| `collect_due` | morning/evening-Sammlung (`:208`) | `presets_due_for_hour` |
| `dispatch_one` | `_send_trip_report_outcome` (`:581`) → `NotificationService` | `send_one_compare_preset` (`:245`) → `EmailOutput` direkt |

**Entry-Points bleiben** (`send_reports_for_hour`, `run_compare_presets_daily`), werden Thin-Wrapper. → Zwei Go-Endpoints + zwei `last_run`-Keys unangetastet (**AC-4 erfüllt, Go nicht angefasst**).

**Compare NICHT durch `NotificationService` routen:** würde einen `kind`-Branch in den Multi-Channel-Send-Code zwingen → Gate #811-Risiko + AC-3-Bruch. Der korrekte geteilte Sink ist die **Channel-Schicht `EmailOutput.send(mail_type=…)`** — die existiert bereits geteilt.

### Affected Files
| File | Change | Description |
|---|---|---|
| `src/services/dispatch_orchestrator.py` | **CREATE** | Skelett + 2 Strategy-Adapter (~150-250 LoC) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `run_compare_presets_daily` → Wrapper (~-80/+20) |
| `src/services/trip_report_scheduler.py` | MODIFY | `send_reports_for_hour` → Wrapper + Strategy-Hooks (~±30) |
| `api/routers/scheduler.py` | MODIFY | 2 Endpoints umverdrahten (~10) |
| `tests/tdd/test_dispatch_orchestrator.py` | CREATE | Neue Verhaltens-Tests (Skelett teilt Loop/Settings/Delay) |

### Scope Assessment
- Dateien: 1 neu, ~3 geändert (+ Test)
- Geschätzte LoC: ~+250-350 netto, überwiegend dünne Verdrahtung → **LoC-Override (250) nötig** in Implementierung
- Risiko: **MEDIUM** (mit benannten HIGH-Punkten unten)
- **Ein Workflow, kein Epic.** (Scheibe 1 = das ganze Issue; optional Scheibe 2: Compare-Fälligkeit in `collect_due` falten, `compare_slot_scheduler.py` bleibt Timing-Lib.)

### Sicherheitsnetz (Kern-Tests, müssen grün bleiben)
- `test_compare_preset_slot_dispatch.py` — Slot-Timing-Vertrag (Morgen@7/Abend@18, `resolve_preset_slots`)
- `test_issue_1012_no_data_guard.py` — Trip `send_reports_for_hour` Verhalten (All-Failed≠sent, No-Data-Marker)
- `test_compare_preset_loader.py:210` — AC-5 Fälligkeits-Parität (`due_old==due_new`)
- ~30 Content-Tests importieren `TripReportSchedulerService`; viele Compare-Tests importieren `run_compare_presets_daily`/`send_one_compare_preset`
- **Fragil gegen Umbenennung:** `logger="trip_report_scheduler"` (test_bug_353), `inspect.getsource` (test_issue_872), Pfad-Asserts (test_report_config_scheduler_structure) → **Delegation, nicht Relocation** ist zwingend

### Verhaltensneutralitäts-Nachweis (AC-3)
- Trip: `briefing_mail_validator.py` (Marker `X-GZ-Mail-Type: trip-briefing` + `X-GZ-Format: full|compact`), Exit 0
- Compare: `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`, ≥3 Orte), Exit 0
- Sendeweg Staging: Test-Trip mit einzigem Empfänger `gregor-test@henemm.com`, Trigger via interner Python-Port `localhost:8000` (`POST /api/scheduler/trip-reports?hour=&user_id=` bzw. `/compare-presets-daily`), IMAP gegen Stalwart

### HIGH-Risiko-Punkte (Verhaltensneutralität am fragilsten)
1. **Inter-Mail-Delay:** Trip 2s vs. Compare 0 — muss pro `kind` parametrisiert bleiben (Catch-up-Sends haben *keinen* Delay — nicht versehentlich vereinheitlichen)
2. **SMTP-Guard-Asymmetrie:** Trip `(0,0)`-Early-Return vs. Compare per-Preset — kind-lokal halten
3. **Return-/Failure-Taxonomie:** Trip `(sent,failed)` mit `no_weather→failed` vs. Compare `count` — Router leiten unterschiedliche Response-Bodies ab (`status="partial"` vs. `"ok"`) → 1:1 reproduzieren
4. **Gate #811:** bleibt dormant, solange `channels/email.py`/`renderers/email/*` nicht angefasst werden
5. **Multi-User-Isolation:** Compare-Empfänger = beliebige per-Preset-Adressen (keine Registry-Prüfung); Trip strikt `mail_to` — Empfänger-Auflösung kind-lokal lassen, Policy-Differenz erhalten

### Tech-Lead-Entscheidungen (alle: Verhalten erhalten, da AC-3 verhaltensneutral verlangt)
Diese fünf Punkte sind bewusst als **Non-Goals** festgelegt (nicht ableitbar aus Code, aber durch AC-3/Issue-Scope determiniert):
1. **Tiefe:** dünner Seam (Strategy-Skelett), keine tiefe DTO-/Send-Verschmelzung
2. **Compare-Kanäle:** bleibt **E-Mail-only** (SMS/Telegram wäre eigenes Feature, Issue-Scope schließt Template/Inhalt aus)
3. **Compare-Empfänger-Policy:** **verbatim erhalten** (per-Preset-Liste) — Angleichung an Trip wäre Verhaltensänderung
4. **Inter-Mail-Delay:** Compare bleibt **0** (kein 2s-Delay dazugewinnen)
5. **Status-Semantik:** beide Tally-Formen **1:1 erhalten** (kein einheitliches `DispatchResult`)

### Latenter Nebenbefund (nicht in Scope, mögliches Folge-Issue)
Compare-Presets versenden an beliebige Adressen ohne Prüfung gegen die Nutzer-Registry — potenzielle Multi-User-Isolations-Frage. Für #1207 **verbatim erhalten** (verhaltensneutral). Ob das ein echtes Leck ist → separater Triage-Punkt (Kandidat #1199 oder eigenes Issue bei nutzersichtbarem Risiko), NICHT in diesem Refactor.

### Open Questions
- Keine blockierenden. Alle Design-Gabelungen sind durch AC-3 (verhaltensneutral) + expliziten Issue-Scope determiniert; die PO-Freigabe erfolgt am natürlichen Checkpoint der AC-Freigabe (`/30-write-spec`).
