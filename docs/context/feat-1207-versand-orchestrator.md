# Context: feat-1207-versand-orchestrator

**Issue:** #1207 — Ein Versand-Orchestrator für Trip + Compare: Python-Pfad konsolidieren
**Track:** Full Process (Scope High · Blast Radius High · Unsicherheit Medium = 5)
**Erstellt:** 2026-07-16

## Request Summary

Der Python-Briefing-Versand läuft in zwei vollständig getrennten Implementierungen für Trip und Orts-Vergleich. #1250-S7c hat nur den *Auslöser* im Go-Scheduler vereinheitlicht (`briefing_dispatch`); darunter ist die Orchestrierung weiter parallel. Ziel: ein Versand-Orchestrator, in dem `route` und `vergleich` **Nachrichtentypen** sind, keine getrennten Pfade.

## Korrektur am Issue-Text (wichtig)

Der Issue-Text (und meine eigene Neufassung von heute) spricht von **drei** parallelen Orchestrierern. Das ist falsch:

| Datei | LoC | Was es wirklich ist |
|---|---|---|
| `src/services/trip_report_scheduler.py` | 1.626 | Trip-Versand — aber ~660 LoC davon sind **Wetter-Pipeline** (Ensemble, Trend, Gewitter, Nacht), die Compare gar nicht braucht (dort steckt Wetter in der `ComparisonEngine`) |
| `src/services/scheduler_dispatch_service.py` | 391 | Compare-Versand |
| `src/services/compare_slot_scheduler.py` | 100 | **Kein Orchestrierer** — die bereits *extrahierte* Fälligkeitslogik (`presets_due_for_hour`). Trip hat dasselbe noch inline. |

Es sind **zwei** Versand-Implementierungen, nicht drei. `compare_slot_scheduler.py` ist kein Problem, sondern ein Teil der Lösung — es ist die Referenz, wie Fälligkeitslogik aussieht, wenn man sie herauszieht. Die 2.100-LoC-Zahl im Issue überzeichnet den Doppelbau erheblich.

## Der stärkste Befund: Compare-Briefing ist der einzige Versand am `NotificationService` vorbei

ADR-0017 nennt den `NotificationService` den **einzigen Versand-Orchestrierer**. Faktisch:

| Pfad | Weg |
|---|---|
| Trip-Briefing | `NotificationService.send_trip_report()` → 3 Kanäle (Email/SMS/Telegram) — `notification_service.py:250-292` |
| Compare-**Alert** | `NotificationService.send_multi_location_deviation_alert()` — `notification_service.py:419`, `:596`, `:671` |
| Compare-**Briefing** | `EmailOutput(settings).send(...)` **direkt** — `scheduler_dispatch_service.py:322`, nur E-Mail |

Der Compare-Briefing-Versand ist die **einzige** Stelle, die den Service umgeht. Der Compare-*Alert*-Pfad geht bereits durch ihn — der Beweis, dass der Weg für Compare-Daten trägt. Das ist der natürliche Schnitt für dieses Issue und zugleich ein bestehender ADR-0017-Verstoß.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py:184` | `send_reports_for_hour` — Trip-Cron-Einstieg; Fälligkeit inline `:209-214`, Guards `_get_active_trips:410` |
| `src/services/scheduler_dispatch_service.py:27` | `run_compare_presets_daily` — Compare-Cron-Einstieg |
| `src/services/scheduler_dispatch_service.py:245` | `send_one_compare_preset` — die eigentliche Compare-Versandlogik (Engine→Render→Mail→Snapshot→Status) |
| `src/services/compare_slot_scheduler.py:58` | `presets_due_for_hour` — extrahierte Fälligkeit, Vorbild für Trip |
| `src/services/notification_service.py:211` | Rendering-/Versand-Grenze für Trip (DTO `TripReportRequest`) |
| `src/services/notification_service.py:419` | Compare-Alert geht bereits über den Service |
| `src/services/report_config_resolver.py:102` / `:166` | `resolve_report_render_options` vs. `resolve_compare_render_options` — **eine Datei, zwei DTOs, kein geteilter Code** |
| `src/app/loader.py:1278` / `:304` | Die `kind`-Naht: beide Loader lesen `briefings/*.json` und filtern invers |
| `src/output/channels/email.py:369` | `EmailOutput.send()` — ab hier IST alles geteilt (Guards #1235/#1219, MIME, Retry) |
| `api/routers/scheduler.py:28` / `:129` | Die zwei HTTP-Endpoints, die der Go-Cron trifft |
| `internal/scheduler/scheduler.go:185` | `briefingDispatch()` aus S7c — ruft beide Fan-outs sequenziell |

## Der gemeinsame Kern — wo Trip und Compare dasselbe anders tun

| Schritt | Trip | Compare | Bewertung |
|---|---|---|---|
| Abos laden | `load_all_trips` :397 | `load_compare_presets` :56 | invers filternde Loader auf **demselben** `briefings/`-Verzeichnis |
| Fälligkeit | inline :209-214 | `presets_due_for_hour` :93 | **gleiche Semantik, zwei Implementierungen** |
| Zieldatum | `_get_target_date` :434 | `compare_slot_scheduler.py:97/99` | identische Regel (morning=today, evening=today+1) |
| Wetter | `_fetch_weather` :968 (+Ensemble/Trend/Gewitter) | `ComparisonEngine.run()` :292 | **legitim verschieden** — Etappen vs. Orte |
| Render-Optionen | `resolve_report_render_options` :636 | `resolve_compare_render_options` :307 | zwei DTOs |
| Rendern | via `NotificationService` :216 | `render_compare_email` **direkt** :310 | Compare umgeht die Kapselung |
| Versenden | `NotificationService` → 3 Kanäle | `EmailOutput` direkt → **nur E-Mail** | **der Kernbruch** |
| Snapshot | `WeatherSnapshotService` :854 | `_write_compare_alert_snapshots` :334 | zwei Wege |
| Alert-State-Reset | `_reset_alert_state_after_briefing` :931 | **fehlt** | Asymmetrie — bewusst? |
| Status schreiben | `briefing_log.json` **Append** :939 | `briefings/<id>.json` **RMW** :125 | ~~zwei last_run-Repräsentationen für dieselbe Sache~~ **WIDERLEGT in Phase 2 — zwei verschiedene Informationen, s.u.** |
| Rate-Limit | 2s zwischen Mails :241 | **fehlt** | Compare kann Resend-Limits reißen |
| Fehler-Semantik | `(sent, failed)` + Outcome-Strings :600 | nur `success_count`, `except` schluckt :116 | Compare-Fehler sind unsichtbar |

## Existing Patterns

- **Vorbild der Konvergenz:** #1168 Engine-Extraktion — Fundament-Scheibe ohne Verhaltensänderung, dann Consumer umstellen. Ebenso S0–S7c aus #1250 (konvergente Annäherung statt Big-Bang, je Scheibe eigener Workflow).
- **Der Merge-Pfad ist die Datenverlust-Falle:** #1250-S6 (`mergeBriefingPatch`, GR221 7. Wiederholung). Prinzip: **neuen Merge nie selbst bauen — Bestandslogik teilen/delegieren.**
- **`kind` explizit, nie Store-Probing:** Trip-ID == Preset-ID ist real (Migrations-F001).
- **Derived-on-load: reset-before-derive** (#1250-S4-Landmine).

## Existing Specs

- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec; **KL-1 (:591-594) ist wörtlich der Auftrag dieses Issues**: „Tiefe Renderer-Zusammenführung (`comparison.py` vs. `trip_report.py`/`NotificationService`) ist NICHT Teil von #1250 — Folge-Issue, mit #1207 zu verschmelzen"
- `docs/adr/0017-output-paket-konsolidierung.md` — „renderers erzeugen, channels versenden"; NotificationService = einziger Versand-Orchestrierer
- `docs/adr/0011-alert-render-single-backend-renderer.md` — Alert-Renderer (nicht Trip-vs-Compare, wie oft zitiert)
- `docs/reference/mail_validators.md` — die zwei Mail-Gates (Trip vs. Compare), Pflicht vor „E2E bestanden"

## E9 — was bewusst getrennt bleibt

Epic #1230 (E9) und KL-1: **die Templates bleiben zwei.** Etappen-Zeilen (route) vs. transponierte Orte-Spalten (vergleich). Zusammenführen ist ausdrücklich **kein** Ziel. Gemeinsame Primitiva sind Zielbild, teils noch nicht Code:

| Primitiv | Ist-Stand |
|---|---|
| Footer, Profil-Signatur, Design-Tokens, Warn-Streifen | **geteilt** (`email/helpers.py:410`, `profile_signature.py:95`, `design_tokens.py`) |
| Kanal-Kappung (Email ∞ / Telegram 8 / SMS 140) | existiert **Trip-only** (`channel_layout.py:20`), Compare importiert es nicht |
| Tabellen-Renderer | **zwei Implementierungen** (`html.py:488` vs. `compare_html.py:489/357`) |
| Korridor-Markierung | **Compare-only** (`compare_html.py:207-236`), Trip-Renderer kennen `Corridor` nicht |

## Dependencies

- **Upstream:** `report_config_resolver.py` (#1203, erfüllt) · `loader.py`/`briefings/` (#1250-S7a/S7b, live) · `Settings().with_user_profile()`
- **Downstream:** Go-Scheduler via HTTP (`briefing_dispatch`) · `/api/scheduler/status` (`last_run` je Sub-Job, AC-24 aus S7c) · Inbound-Kommandos (`send_on_demand_report`) · UI-Einzelversand (`/send`-Endpoints)

## Risks & Considerations

1. **Kanal-Asymmetrie ist eine PO-Frage, kein Implementierungsdetail.** Compare kann heute nur E-Mail. Hängt man es an den `NotificationService`, bekommt es SMS/Telegram strukturell „gratis". Epic #1230 sieht `channels: ("email"|"telegram"|"sms")[]` für **beide** kinds vor — aber das wäre eine **Verhaltensänderung**, keine Konsolidierung. Muss die Spec explizit entscheiden: Kanäle freischalten (Feature) oder Compare bewusst auf E-Mail gepinnt lassen (verhaltensneutral)? **Empfehlung: pinnen** — verhaltensneutral halten, Freischaltung als eigenes Issue.
2. **Live-Versandpfad.** Hier gehen echte Briefings an echte Empfänger. Beide Mail-Validatoren sind Pflicht-Gate, `renderer_mail_gate.py` blockt Commits auf Mail-Inhalts-Dateien vor grünem Validator-Lauf.
3. **Status-Persistenz-Vereinheitlichung ist der Datenverlust-Kandidat.** `briefing_log.json` (Append) vs. `briefings/<id>.json` (RMW) zusammenzuführen heißt Schema-Rework → Read-Modify-Write mit Merge, nie Replace (GR221-Klasse, 7 Wiederholungen). **Kandidat, es NICHT anzufassen** und in einer Folge-Scheibe zu lassen.
4. **Scope-Explosion.** Der ehrliche Kern ist klein (Compare an den NotificationService hängen, Fälligkeit teilen). Das Issue lädt zusätzlich zum Renderer-Tiefen-Merge (KL-1) ein — der aber per E9 gar nicht gemeint ist. Scheiben-Schnitt ist die wichtigste Spec-Entscheidung.
5. **Sechs parallele Sessions laufen** (#1268, #1275, #1277, #1266, #1124, MeteoAlarm) — überwiegend Frontend. Dieses Issue ist Backend/Python, Kollisionsrisiko gering, aber Rebase-Disziplin nötig (Parallel-Session-Churn war bei S7b massiv).
6. **Fehler-Semantik:** Compare schluckt Fehler per `except` und meldet nur `success_count`. Vereinheitlichung würde Fehler sichtbar machen — potenziell „neue" Fehler in `/api/scheduler/status`, die vorher stumm waren. Gut, aber als Verhaltensänderung zu benennen.

## Phase-2-Analyse: drei Korrekturen an diesem Dokument

### K1 — Status-Persistenz sind ZWEI VERSCHIEDENE INFORMATIONEN, nicht zwei Repräsentationen (widerlegt Risiko 3 + die Zeile in der Kern-Tabelle)

| | Trip `briefing_log.json` | Compare `letzter_versand` |
|---|---|---|
| Frage | „*ist der heutige Slot erledigt?*" — Slot-Zustand **pro report_type** | „*wann war das letzte Mal?*" — Letztstand |
| Form | Append-Historie `{trip_id, kind: morning\|evening, sent_at, channels}` | ein ISO-Timestamp |
| Anzeige | **Häkchen** an geplanter Zeile, serverseitig auf heute gefiltert (`cockpit.go:29-33`, `cockpitHelpers.ts:139-144`) — Timestamp wird dem Nutzer **nie gezeigt**; Eintrag von gestern ist wertlos | **Relativtext** „heute/gestern/Wochentag" (`subscriptionHelpers.ts:199-211`) — Eintrag von letzter Woche ist weiterhin die Wahrheit |

Die Trip-Form ist eine **strikte Obermenge**: letzter Eintrag = `letzter_versand`.

**Umzug Trip→Compare-Form (Einzelfeld) wäre verlustbehaftet, hart:**
- `BriefingCountByTrip()` (`internal/store/log.go:78-88`) zählt über die **volle Historie** → `GET /api/archive/stats` („NOT time-filtered — full history", `archive_stats.go:12-14`). Aus einem Timestamp arithmetisch **nicht ableitbar**.
- **Sichtbarer Nutzer-Bug:** Ein Einzelfeld kann „morgen ✓, abend ✗" nicht darstellen — der Abend-Versand überschriebe den Morgen-Status. `cockpitHelpers.ts:152/160` matcht bewusst auf `(trip_id, kind, heute)`.
- **Präzedenz:** Für die Schwesterdatei `alert_log.json` wurde eine 48h-Retention eingeführt **und wieder entfernt**, weil `AlertCountByTrip()` die volle Historie braucht (`internal/store/log.go:91-93`). Wer die Trip-Historie auf ein Einzelfeld reduziert, wiederholt eine bereits revertierte Entscheidung.

**Umzug Compare→Trip-Form (Log) ist informationsverlustfrei** und **additiv** — kein Schema-Rework, kein GR221-Risiko: Backfill = ein synthetischer Eintrag aus `letzter_versand`. Es ist damit aber auch kein „Vereinheitlichen", sondern das **Feature** „der Ortsvergleich bekommt eine Versand-Historie".

### K2 — `last_run` im Scheduler-Status ist ein DRITTER, orthogonaler Begriff

`/api/scheduler/status` speist sich aus einer **In-Memory-Map im Go-Scheduler** (`scheduler.go:58` `lastRuns`, `:296-313` `recordRun`) — **stirbt bei jedem Prozess-Restart**, Granularität = Cron-Job (nicht Trip/Preset), Semantik = „Tick lief, HTTP gab ok/error" (auch bei 0 Versänden `ok`). **Keine** der beiden Datei-Repräsentationen speist ihn. AC-24 aus S7c ist davon unberührt.

### K3 — Der 2s-Delay kommt NICHT gratis (widerlegt eine Zusage an den PO)

`INTER_MAIL_DELAY_SECONDS = 2` (`trip_report_scheduler.py:46`) sitzt in der **Batch-Schleife des Trip-Schedulers** (`:177`, `:241`), **nicht** im `NotificationService` (dort 0 `sleep`-Treffer — der Service sendet je Aufruf genau eine Mail und kennt keine Batch-Schleife). Ein Wechsel des Compare-Versands auf den Service transportiert ihn **nicht** mit. Der Delay muss explizit in die Compare-Batch-Schleife (`scheduler_dispatch_service.py:95-119`).

## Naht A — der Schnitt ist anders als gedacht, aber besser

**`TripReportRequest` ist keine Option für Compare:** harter Guard `if not request.segment_weather: return` (`notification_service.py:212-213`) — Compare hat nie `segment_weather`; `TripReportFormatter` ist fest im Konstruktor (`:203`); `mail_type` ist in `_send_email` hart auf `"trip-briefing"` verdrahtet (`:1051`/`:1059`), kein DTO-Feld; `compare_hourly_enabled` hat keine Durchreiche; kein `to=`-Override.

**Aber der Service hat bereits ein etabliertes Compare-Muster** — vier bestehende Methoden (`:419`, `:580`, `:637`, `:671`): flache Keyword-Parameter (kein DTO) · Renderer-Auswahl im Methodenrumpf (lokaler Import) · `mail_type` als **Parameter** durchgereicht (`_dispatch_alert_message:782` → `:845`) · Kanäle als `effective_channels: set[str]` (`:665-669`).

→ Der Schnitt ist eine **neue Methode `send_compare_briefing(...)` im Stil der bestehenden Compare-Methoden**, nicht Compare durch `TripReportRequest` quetschen. Das fasst `send_trip_report`/`TripReportRequest` **nicht an** (Trip-Pfad bleibt unberührt) und pinnt Kanäle sauber über `effective_channels={"email"}`.

## Naht B — gefährlicher als gedacht: „Trip zieht auf `presets_due_for_hour`" ist KEINE Option

1. **`presets_due_for_hour` würde einen Trip nicht crashen, aber alle fünf Trip-Guards still überspringen** — `paused_at`, `rc.enabled`, `paused_until`, `skip_next`, `get_stage_for_date` haben **kein** Compare-Pendant. Ergebnis: **pausierte Trips würden senden.** Stiller Fehler, kein Crash.
2. **Default-Divergenz:** Compare-Morgen `06:00` (Migrations-Fallback `compare_slot_scheduler.py:47-50`), Trip-Morgen `07:00` (`:376`). Compare `evening_enabled` default **False** — Trip prüft den Abend-Slot unbedingt → Trips verlören den Abend-Report.
3. **`skip_next` schreibt im Fälligkeits-Check** (`_get_active_trips:439-445` ruft `save_trip`) — `_get_active_trips` ist **nicht seiteneffektfrei**, während `compare_slot_scheduler.py:5` ausdrücklich „Reine Funktionen (kein IO)" fordert. Compare hat denselben Konflikt bereits gelöst: Auto-Pause läuft als **eigener Durchlauf** außerhalb der reinen Funktion (`scheduler_dispatch_service.py:60-87`).
4. **Trips flache Slot-Felder sind ausdrücklich NICHT autoritativ** (`trip.py:218-220`: „`report_config` bleibt die einzige Wahrheit fuer den Versand") — `resolve_preset_slots` liest genau diese Felder.
5. **`end_date`:** Compare liest ein Feld, Trip hat eine `@property` über die Etappen (`trip.py:242-247`), die laut Kommentar `:219-220` **kein Feld werden darf**. Bei `asdict` fehlt der Key → Guard greift nie.

→ Naht B ist kein „Trip zieht auf das Compare-Muster", sondern bestenfalls „**gemeinsamer Fälligkeits-Vertrag**, der die Trip-Guards als Erweiterung trägt" — deutlich größer und riskanter als der Issue-Text suggeriert. Kandidat zum Descopen.

## Nebenbefunde (→ #1199, nicht Scope)

- `top_ort_letzter_versand`: geschrieben (`scheduler_dispatch_service.py:168`), durchgereicht (`loader.py:232`, `compare_preset.go:189`), **0 Leser** — toter Feldpfad.
- `BriefingHistoryDialog.svelte` wird nirgends importiert; `/api/archive/stats` hat 0 Frontend-Konsumenten. Endpoints leben, Konsumenten tot.
- `_append_briefing_log` schreibt **nicht atomar, ohne Lock** (`:946-951` read→mutate→write). Crash zwischen Truncate und Write vernichtet die Historie — und Go liest korrupt **fail-soft als leer** (`log.go:32-34`), der Verlust wäre **unsichtbar**.
- Namenskollision: `BriefingLogEntry.Kind` = `morning`/`evening` (report_type), **nicht** das #1250-`kind`.

## Offene Fragen für Phase 2 (Analyse)

- Schnitt: Scheibe A = Compare an `NotificationService` (verhaltensneutral, E-Mail gepinnt); Scheibe B = Fälligkeitslogik teilen (Trip zieht auf `presets_due_for_hour`-Muster); Scheibe C = Status-Persistenz; Renderer-Tiefen-Merge = **descopen**, da E9 die Templates trennt?
- Ist `_reset_alert_state_after_briefing` bei Compare eine Lücke (Bug) oder Absicht?
- Verträgt `presets_due_for_hour` die Trip-Guards (`paused_until`, `skip_next`, `rc.enabled`) oder braucht es einen erweiterten gemeinsamen Vertrag?
