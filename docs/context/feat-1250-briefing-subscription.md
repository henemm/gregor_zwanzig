# Context: feat-1250-briefing-subscription

## Request Summary

Issue #1250 (Phase 3 von Epic #1230): Trip- und Compare-Subscription auf EIN
Schema `BriefingSubscription{kind:"route"|"vergleich"}` migrieren — Renderer
wählt Template per kind, API-Endpoints konsolidieren, Lifecycle vereinheitlicht
(endDate nullable; vergleich: Auto-PAUSE bei Erreichen, C3). Migration
verlustfrei mit Dry-Run + Report (C4). Voraussetzungen erfüllt: Phase 1
(#1231, corridors beidseitig), Phase 2 (#1229, Hub) und Phase 4 (#1232,
geteilte Organismen + flache Briefing-Slot-Felder) sind live.

## Ist-Vermessung (2026-07-13, Belege = Datei:Zeile)

### 1. Drei parallele Stacks, nicht zwei (KERNBEFUND)

Neben **Trip** und **ComparePreset** lebt ein dritter, aktiver Legacy-Pfad
**CompareSubscription**: `compare_subscriptions.json` (Wrapper `{subscriptions:[…]}`),
Go `internal/store/subscription.go:15-17,105-121` + Handler `handler/subscription.go`
(305 LoC) + eigener CRUD `/api/subscriptions*` (router.go:145-152), Python
`src/app/user.py:117` + `loader.py:1375-1467`, FE-Type `Subscription`
(types.ts:298-320). Offenes Issue dazu: **#1131** (Alt-Pfad compare_subscription.py
entfernen, CLI-only). Scope-Entscheidung nötig: Legacy-Stack VOR der
Konsolidierung stilllegen (empfohlen, sonst migriert man gegen ein bewegliches Ziel).

### 2. Datenmodelle

Go: `internal/model/trip.go:101-131` vs `compare_preset.go:14-92`.
- **Äquivalent:** Name · Corridors (beide `[]Corridor`, kein omitempty) ·
  DisplayConfig-map (inkl. `channel_layouts`, geteilt) · AlertCooldown/Quiet ·
  OfficialAlerts-Flags.
- **Divergent gleicher Semantik:** Kanäle/Empfänger (Trip: `ReportConfig`-map;
  Preset: `SendTelegram/SendSms` + `Empfaenger[]`) · Briefing-Slots (Trip: in
  `ReportConfig`-map `morning_enabled/time`…; Preset: native Felder :84-87) ·
  Profil (`Activity` ActivityType vs `Profil` ActivityProfile — verschiedene
  Namensräume!) · Pause (Trip `PausedAt *time` :121; Preset `schedule=="manual"`
  + `PreviousSchedule`) · endDate (Trip: berechnet `max(stage.date)`,
  trip.py:212-214, FE `computeTripEnd`; Preset: persistiert `EndDate *string` :88).
- **kind-spezifisch:** Trip `Stages`, `AlertRules`, `Aggregation`,
  `AvalancheRegions`, `Shortcode`; Preset `LocationIDs`, `HourlyEnabled`,
  `RadarAlertEnabled`.
- **Deprecated am Preset:** `Schedule` (nur noch Pause-Flag), `PreviousSchedule`,
  `Weekday`, `HourFrom/HourTo`, `ForecastHours` (compare_preset.go:24-33).
- Python: `Trip`-dataclass (trip.py:168-266); **ComparePreset existiert NICHT als
  Klasse** — ≥4 Stellen lesen rohe Dicts mit dupliziertem Datei-Load
  (compare_alert.py:292, compare_radar_alert.py:180, compare_official_alert.py:185,
  scheduler_dispatch_service.py:38).
- FE: `Trip` (types.ts:275-296), `ComparePreset` (:485-524, trägt alt+neu parallel),
  `Corridor` geteilt (:110-116).
- **Kein kind-/type-Diskriminator existiert irgendwo** (Grep bestätigt).

### 3. Persistenz (asymmetrisch)

- Trip: 1 Datei pro Entität `data/users/<uid>/trips/<id>.json`
  (store/trip.go:14-16; loader.py:250/1300).
- ComparePreset: EIN Sammel-Array `compare_presets.json` (store/compare_preset.go:11-13);
  Python schreibt Status per id-Scan ins Array (scheduler_dispatch_service.py:179-199).
- Legacy CompareSubscription: `compare_subscriptions.json` mit Wrapper.
- Slot-Migration existiert DOPPELT und muss konsistent bleiben:
  Go store/compare_preset.go:56 + Python compare_slot_scheduler.py:36.

### 4. API-Oberfläche (router.go)

- Trip: CRUD + `PATCH state` + waypoints/weather/briefing-history +
  Python-Proxies send/alert-preview/preview (:136-175).
- ComparePreset: CRUD + `PATCH state` (nur archived) + `POST send`-Proxy (:182-188).
- Legacy `/api/subscriptions*`: 8 Routen (:145-152).
- Handler-LoC: trip.go 442 · compare_preset.go 528 · subscription.go 305.

### 5. Scheduler (zwei Vollpfade)

- Trip: Cron stündlich → `/api/scheduler/trip-reports` →
  `trip_report_scheduler.py` (1453 LoC; Pending-Marker, `report_config`-Hours,
  paused-Guard :405-410).
- Compare: Cron stündlich → `/api/scheduler/compare-presets-daily` →
  `scheduler_dispatch_service.py` (360 LoC) + `compare_slot_scheduler.py` (100 LoC,
  `presets_due_for_hour`); dazu 3 eigene 15-Min-Alert-Jobs (scheduler.go:104-106).
- Geteilt: nur der Cron-Takt + `runForAllUsers` (scheduler.go:131).

### 6. Renderer

Kein kind-Dispatch: Compare rendert über `comparison.py:145` →
`email/compare_html.py`; Trip über NotificationService →
`trip_report.py` (720 LoC)/`email/html.py`/`sms_trip.py`. Nach #1231 geteilt ist
nur das `Corridor`-Modell + `corridor_match.py` (36 LoC) — der Trip-Renderer
konsumiert `corridor_inside` NICHT (Trip-Alarme laufen weiter über alert_rules).

### 7. Lifecycle

**Auto-PAUSE bei EndDate existiert NICHT** — heute nur Versand-Skip ab Folgetag
(compare_slot_scheduler.py:81-84), Status bleibt unverändert. FE-Status:
`deriveStatusFromPreset` (subscriptionHelpers.ts:100, aus name/location_ids/
schedule) vs. Trip direkt aus paused_at/archived_at.

### 8. Geteilte FE-Organismen (Phase-4-Stand)

`shared/VersandTab.svelte` (EIN Organism, `context:'route'|'vergleich'` :32 —
aber ZWEI Datenformen: route = `Trip`+`reportConfig`+Self-Save via PUT /api/trips;
vergleich = `CompareWizardState`, Save zentral im Editor) ·
`shared/layout-tab/LayoutTab.svelte` (beide, via `display_config.channel_layouts`) ·
`shared/corridor-editor/` (beide, `Corridor[]`; Compare mit Dual-Write
corridors ↔ ideal_ranges/active_metrics/metric_alert_levels,
compareWizardState.svelte.ts:29, CompareEditor.svelte:119).

### 9. Größenordnung

Go-Kern ~2110 LoC (Stores 371, Handler 1275, Models 392, scheduler.go 464 geteilt);
Python ~4579 LoC (trip_report_scheduler 1453, loader 1574, dispatch 360,
comparison 194, trip_report 720, slot_scheduler 100, compare_subscription 142)
+ Compare-Alarm-Trias mit je eigenem Preset-Loader.

## Top-Risiken verlustfreie Migration (aus der Vermessung)

1. Dritter Legacy-Stack `CompareSubscription` aktiv → erst Scope klären/stilllegen (#1131).
2. Asymmetrisches Dateilayout (1-Datei-pro-Trip vs Sammel-Array) → mindestens ein
   Stack braucht Datei-Migration; Presets haben keine stabile Datei-Identität.
3. Python-Preset-Zugriffe sind rohe Dicts an ≥4 Stellen ohne zentralen Kontrakt.
4. Deprecated-Felder tragen lebende Semantik (schedule/previous_schedule = Pause!);
   doppelte Slot-Migration Go+Python muss synchron bleiben.
5. Lifecycle-Divergenz (paused_at vs schedule=="manual"; berechnetes vs
   persistiertes endDate) + Auto-Pause ist Neubau, berührt Scheduler-Guards,
   deriveStatusFromPreset und Pause-Toggle gleichzeitig.
6. „Renderer per kind" erfordert Zusammenführung zweier Render-Entrypoints —
   größter ungedeckter Aufwand; FE-Dual-Write (mark→ideal_ranges) darf beim
   Wegfall von Legacy-Keys keine Markierungen verlieren.

## Existing Specs / Referenzen

- Epic #1230 (Body = Zielmodell, C1-C6, E8/E9) · `docs/specs/modules/issue_1229_monitor_hub.md`
  (KL-2: briefings[]-Frage gehört hierher) · `docs/specs/modules/issue_1231_korridor_editor.md`
  (Corridor-Modell, Dual-Write) · `versand_tab_vergleich.md`/`versand_tab_route.md` (Organism)
- `docs/reference/api_contract.md` (SSoT DTOs — MUSS mitgezogen werden)
- Verwandte offene Issues: #1131 (Legacy compare_subscription entfernen),
  #1203 (Config-Resolver), #1159 (Merge-Helfer für Config-PUTs), #1207
  (Konvergenz Scheibe 4 Versand-Orchestrator — geht vermutlich in Phase 3 auf),
  #1244 (corridors:null bricht Python-Loader — gleiche Baustelle!), #1221
  (Compare-Editor handleSave verliert Felder).

## Analysis (Strategie-Bewertung 2026-07-13, Plan-Agent)

### Type
Feature/Rework (Architektur-Konsolidierung, Epic-Phase 3)

### Kernentscheidungen (Empfehlung)

1. **Konvergente Annäherung, KEIN Big-Bang:** Trip und Preset werden Feld für
   Feld auf identische Semantik gezogen; `kind` additiv; gemeinsame Store-Schicht
   erst bei Deckungsgleichheit. Richtungs-Tabelle: Pause → `paused_at`
   (Trip-Modell, Preset dual-write mit schedule=='manual' bis FE um);
   Briefing-Slots + Kanäle → flache Felder (Preset-Modell, Trip dual-read aus
   report_config); Profil → `activity_profile`-Namensraum (einzige echte
   Wertkonvertierung: Trip.Activity-Mapping); endDate → persistiert+nullable auf
   beiden (route: Server materialisiert aus max(stage.date)); Deprecated-Felder
   als dokumentierter Pass-Through bis zur Migrations-Scheibe.
2. **Legacy-Drittstack zuerst stilllegen (Scheibe 0 = #1131):** nachweislich
   (fast) tot — Scheduler-Proxies 404 seit #515 (test_issue_515:52-64),
   `save_subscription_status` ohne Produktions-Caller, FE-Nutzung nur
   Account-Zähler-Bug (+page.server.ts:27, zählt falschen Store) + gefährlicher
   Totcode `wiz.save()`/`toggleEnabled()` (compareWizardState.svelte.ts:85/161 —
   würde Preset-IDs in den Legacy-Store schreiben). Bestandsdateien
   `compare_subscriptions.json` bleiben liegen (keine Datenlöschung).
3. **Ziel-Persistenz:** `data/users/<uid>/briefings/<id>.json` (1 Datei/Entität,
   Trip-Muster) — beseitigt das Lost-Update-Fenster des konkurrierenden RMW auf
   compare_presets.json (Go-Handler vs scheduler_dispatch:179-210). Migration =
   Deploy-Schritt: Dry-Run mit Feld-Diff-Report → Backup → idempotent (Ziel
   existiert+kind → skip), Read-new-fallback-old während der Scheiben; doppelte
   Slot-Migration (Go+Py) vorher auf das Migrationsskript reduzieren; Felder
   explizit materialisieren (Go-Self-Heal persistiert nicht, #1231-Befund).
4. **Renderer-Dispatch NICHT in #1250:** E9 hält Templates ohnehin getrennt;
   nach Scheibe 7 existiert kind-Dispatch am Scheduler-Einstieg. Die tiefe
   Zusammenführung der zwei Render-Entrypoints (comparison.py vs
   NotificationService/trip_report.py) → Folge-Issue, mit #1207 verschmelzen.
   Epic-AC „kein paralleler Stack" ist erfüllt mit: ein Schema + ein Store +
   eine API + ein Scheduler-Einstieg.
5. **Vorziehen (eigene Mini-Workflows, VOR Scheibe 4/5):** #1244 (corridors:null
   bricht Python-Loader — Migration liest jeden Trip durch den Loader) und
   #1221 (handleSave-Datenverlust verfälscht Vorher/Nachher-Verifikation).
   #1203/#1159 NICHT mitbauen (aber Scheibe 1 = natürlicher Unterbau von #1203;
   Scheibe 6 darf Blind-Replace nicht als 7. Wiederholung einführen).

### Scheiben-Plan (je unabhängig auslieferbar)

| # | Inhalt | ~LoC add | Risiko |
|---|---|---|---|
| 0 | Legacy CompareSubscription stilllegen (#1131): 9 Routen, handler/store/loader/CLI/FE-Totcode; Account-Zähler auf /api/compare/presets | ~40 (netto stark negativ) | niedrig |
| 1 | Python-Preset-Kontrakt: ComparePreset-Dataclass + EIN Loader statt 4 rohe Dict-Loads | ~200 | niedrig |
| 2 | Pause-Konvergenz: paused_at additiv am Preset (Go+Py+FE), Dual-Write, deriveStatusFromPreset liest paused_at zuerst | ~200 | mittel |
| 3 | Auto-Pause bei endDate (NEUBAU, C3/E8): Slot-Scheduler setzt paused_at + Hub-Hinweis | ~150 | mittel |
| 4 | Trip-Konvergenz: flache Slot-/Kanal-Felder additiv (Dual-Read), end_date-Materialisierung | ~250 (Override-Kandidat) | hoch |
| 5 | kind + gemeinsames Modell/Store + Datei-Migration → briefings/<id>.json (Dry-Run/Backup/idempotent) | ~250 + Skript | hoch |
| 6 | API-Konsolidierung: /api/briefings* + dünne Kompat-Delegates für /api/trips* und /api/compare/presets* (C6: Testids/FE stabil) | ~250 | mittel |
| 7 | Scheduler-Vereinheitlichung: EIN Einstieg liest briefings/, dispatcht per kind auf bestehende Pfade | ~200 | mittel |

Abhängigkeiten: 0 zuerst; 1→2→3; 4 parallel zu 2/3 möglich; 5 braucht 1-4;
6/7 brauchen 5. Erste Scheibe JETZT: **Scheibe 0**.

### Scope Assessment
Programm über mehrere Workflows (Muster #1231: eine Spec, Scheiben-Workflows).
Gesamt grob ~1,5k LoC add über 8 Scheiben + Migrationstooling; jede Scheibe
im Limit bzw. mit angekündigtem Override.

## Pflicht-Regeln für diese Arbeit

- Daten-Schema-Rework: Read-Modify-Write mit Merge, NIE Replace (BUG-DATALOSS-GR221);
  Schema-Dateien lösen Pre-Snapshot-Backup aus; Migration = per-Host-Deploy-Schritt
  (data/users gitignored), idempotent + Backup + Dry-Run + Report (C4).
- Go-Self-Heal persistiert nicht (Befund #1231-Migration) — Migration muss
  Felder explizit materialisieren.
- LoC-Limit 250/Workflow → Phase 3 MUSS in mehrere unabhängig auslieferbare
  Scheiben (vermutlich je eigener Workflow, wie #1231 mit 7 Slices).
