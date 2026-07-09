# Architektur – Gregor Zwanzig

**Updated:** 2026-07-03 (Issue #1001 — Telegram-Ausgabe neu gebaut: `render_telegram_bubbles()` ersetzt `render_narrow()` für den Telegram-Kanal, Multi-Bubble-Versand statt Prosa-Nachricht, echte Monospace-Segment-Tabellen, Inline-Keyboard-Aktionen-Bubble); 2026-06-30 (Issue #919 — Radar-Alert auf kanonischen Renderer migriert: `OnsetEvent`-Datenklasse + `cooldown_display` in `model.py`, Onset-Zweige in alle vier `render_*`-Funktionen, `check_radar_alerts` baut jetzt `AlertMessage(OnsetEvent(...))`, `src/outputs/radar_alert.py` gelöscht); 2026-06-26 (Issue #887 — SMS/Telegram Report-Konsistenz: SMS `pop_hourly` aus `agg.pop_max_pct`, Telegram Detail-Zeile mit config-gesteuerten Metriken; Issue #884 — HTML-Mail Fidelity: 8-Sektion-Layout mit zweispaltigem Header + Stats-Grid, Ziel-Sektion, Ausblick mit Risk-Dot, Kommandos-Sektion, zweigeteilt Footer); 2026-06-15 (Issue #822 — Radar-/Regen-Nowcast-Alert segmentbewusst: gemeinsamer Segment-Helfer, aktives/nächstes Segment nach Tageszeit, Ort-Label via build_segment_label, Tour-TZ via tz_for_coords, dynamischer Cooldown-Text); 2026-06-14 (Issue #816 — Alert-Abweichungs-Kern: read-only Snapshot, alert_state Melde-Gedächtnis, knapper Render-Pfad); 2026-06-12 (Issue #758 — Einheitlicher Speicher-Status-Indikator + Trip-Editor Auto-Save; #733 Briefing-Mail-Validator Marker-Header); 2026-06-11 (Issue #749 — Day Comparison Renderer: render_day_comparison_html/plain für Vortag-Vergleich-Sektion); 2026-06-09 (Issue #675 — Etappen-Startzeiten Editor-Widget; Issue #671 — Bot-Menü automatisch beim Service-Start + Live-Selftest); 2026-06-08 (Issue #655 — Telegram callback_query + editMessageText Zoom-Navigation); 2026-06-07 (Issue #637 — Telegram Webhook Migration); 2026-06-03 (Issue #572 — Inbound-Handler Multi-User Routing); 2026-05-31 (Issue #483 — Demo-Modus im Vorschau-Tab; Issue #495 — MapCanvas Leaflet-Karte; Issue #475 — OutputLayoutEditor zu Organisms)

## Überblick
Gregor Zwanzig ist ein verteiltes System mit separatem Frontend (SvelteKit) und einem Dual-Stack-Backend (Go + Python):

- **Go-API:** REST-API (Port 8090), Auth/Sessions, Mandantentrennung, Persistenz/Store, Proxy zum Python-Core
- **Python-Core:** Wetter-Domäne (Provider, Risk Engine, Aggregation), alle Kanal-Renderer und -Transporte, Scheduler, Alerts, Inbound-Handler (FastAPI, Port 8000)
- **Frontend:** SvelteKit Web-UI für Trip-Management, Konfiguration und Orts-Vergleiche
- **Channels:** E-Mail (SMTP), Telegram, SMS (seven.io)
- **Subscriptions:** Trip-Reports (automatisch pro Etappe), Orts-Vergleiche (personalisierte Standort-Rankings)

Siehe `docs/adr/0015-dual-stack-zielarchitektur.md` für die verbindliche Zuständigkeitsgrenze.

---

## Backend Architecture (Dual-Stack)

Das Backend besteht aus zwei klar getrennten Schichten (siehe `docs/adr/0015-dual-stack-zielarchitektur.md`):

- **Go-API (`gregor-api`, Port 8090):** REST-API, Auth/Sessions, Mandantentrennung,
  Persistenz/Store (`internal/store/`) und Proxy zum Python-Core.
- **Python-Core (`api/` + `src/`, interner Port 8000):** Wetter-Domäne
  (Provider, Normalisierung, Risk Engine, Aggregation), alle Kanal-Renderer und -Transporte,
  Scheduler, Alert-System, Inbound-Handler.

Die Vertragsgrenze zwischen Go und Python ist HTTP mit den DTOs aus
`docs/reference/api_contract.md`.

### Python-Core: Wetter-Pipeline und Rendering

Die folgenden Komponenten leben im Python-Core:

1. **Business-Logik**
   - **Provider-Adapter**: holen Rohdaten von Wetter-APIs (z. B. MET Norway, DWD)
   - **Normalizer**: wandelt Daten in ein gemeinsames DTO ([api_contract.md](./api_contract.md))
   - **Risk Engine**: bewertet Forecasts anhand Schwellen (Regen, Gewitter, Wind, Hitze)
   - **Report Formatter**: erzeugt kurze Texte + Debug-Anhang
   - **DebugBuffer**: gemeinsame Quelle für Console + E-Mail-Debug

2. **Render-Pipeline**
   - **Channel Renderers** (`src/output/renderers/`) – β3: Pure-Function Renderer für E-Mail + SMS
   - `render_email()` – HTML + Plain-Text Körper (aus Token-Zeilen)
   - `render_sms()` – Kompaktes Format ≤160 Zeichen (v2.0 Wire-Format)
   - `render_telegram_bubbles()` – Telegram-Format (`src/output/renderers/narrow.py`,
     seit Issue #1001, ersetzt `render_narrow()` für `channel == "telegram"` vollständig):
     rendert eine Liste von `TelegramBubble`-Objekten statt eines Prosa-Textblocks —
     Kopf-, Kurzübersicht-, je Segment-, Ziel-, optional Ausblick- und Aktionen-Bubble
     (mit Inline-Keyboard). Segment-/Ziel-/Ausblick-Bubbles enthalten echte
     spaltenausgerichtete Monospace-Tabellen (`_narrow_table()`, `<pre>` +
     `parse_mode="HTML"`) statt der früheren `_tg_segment_line()`-Prosa-Zeile. Versand
     erfolgt als mehrere einzelne `sendMessage`-Aufrufe (`trip_report_scheduler.py`).
     Siehe `docs/adr/0014-telegram-multi-bubble-format.md`.
   - **Day Comparison Renderers** (Issue #749) – neue Pure Functions für Vortag-Vergleich-Sektion:
     - `render_day_comparison_html(comparison)` – HTML mit farblicher Richtungscodierung (BETTER/WORSE/EQUAL)
     - `render_day_comparison_plain(comparison)` – Plain-Text Variante mit Pfeilen
   - Schnittstelle: TokenLine (aus Report Formatter) → Channel-spezifischer Output

3. **Channels**
   - **SMTP-Mailer** (`src/output/channels/email.py`) – E-Mail-Versand
   - **Telegram-Bot** (`src/output/channels/telegram.py`) – Telegram-Versand
   - **SMS** (`src/output/channels/sms.py`) – SMS-Versand via seven.io

### Datenfluss (Produktiv)

Der Produktivpfad läuft über den Python-Core-Scheduler und wird von der Go-API getriggert
oder über Cron-Jobs gesteuert:

```
Scheduler / API-Trigger
  ↓
Trip + DisplayConfig (aus Go-Store)
  ↓
Provider-Adapter
  ↓
Normalisierung
  ↓
Risk Engine
  ↓
Formatter → TokenLine
  ↓
Channel Renderers
  ├─→ render_email() → (HTML, Plain)
  ├─→ render_telegram_bubbles() → TelegramBubble-Liste
  ├─→ render_sms() → Wire-Format ≤160 Zeichen
  └─→ DebugBuffer
  ↓
Channel (E-Mail / Telegram / SMS / Console)
```

### Datenfluss (Legacy-CLI)

Für lokale Entwicklung und Debugging existiert weiterhin die CLI in `src/app/cli.py`
(`--report`, `--channel`, `--dry-run`, `--config`, `--debug`). Dieser Pfad ist nicht
mehr der Produktivpfad.

## Debug-Prinzip
- Alle Schritte schreiben standardisierte Debug-Zeilen in den DebugBuffer
- Console = vollständige Ausgabe
- E-Mail = 1:1 identisches Subset
- Kern-Debug-Zeilen (immer enthalten): `cfg.path`, `report`, `channel`, `debug`, `dry_run`

## Inbound-Handler (Multi-User Routing)

**Komponenten:** `src/services/inbound_email_reader.py`, `src/services/inbound_telegram_reader.py`

**Zweck:** Eingehende Befehle (E-Mail-Replies, Telegram-Nachrichten) dem richtigen User zuordnen und verarbeiten.

**Workflow:**

1. **Email-Handler** (`InboundEmailReader.poll_and_process()`)
   - Liest IMAP-Inbox (shared mailbox)
   - Pro Nachricht: `lookup_user_by_email(from_addr)` → sucht User-Profil mit passender `mail_to`
   - Fallback: `user_id = "default"` wenn kein User gefunden
   - Ladet Trips des Nutzers via `load_all_trips(user_id)`
   - Verarbeitet Befehl (z. B. "status", "help")
   - Antwortet an die aufgelöste User-Adresse

2. **Telegram-Handler** (`InboundTelegramReader._process_update()`)
   - **Empfängt Telegram-Updates per Webhook** (Push-basiert seit Issue #637; Polling entfernt)
   - Go-Endpoint `/api/webhooks/telegram/{secret}` mit Secret-Header-Validierung → Python-Weiterleitung
   - Extrahiert Chat-ID
   - `lookup_user_by_telegram_chat_id(chat_id)` → findet User-Profil
   - Fallback: `user_id = "default"` wenn kein User gefunden
   - Ladet Trips des Nutzers und verarbeitet Befehl
   - Idempotenz via `update_id`-Watermark → keine Doppel-Zustellung
   - **Hybrid-Navigation via callback_query** (seit Issue #655):
     - Button-Klicks (Tier-1 Glance, Tier-2 Timeline, Tier-3 Drilldown, Zurück) kommen als `callback_query`
     - `_process_callback_query()` mappt `callback_data` → Processor-Body (z.B. `tl_today` → `### query: timeline_heute`)
     - `TelegramOutput.edit_message_text()` ersetzt Nachricht in-place (statt neue zu senden) → Zoom-Navigation
     - `TelegramOutput.answer_callback_query()` wird immer aufgerufen → Telegram-Lade-Spinner stoppt (auch bei unbekannten Buttons)

**Lookup-Funktionen** (`src/app/loader.py`):
- `list_all_user_ids(data_dir)` – alle User-IDs unter `data/users/` (ausschließt test_ / _ Präfixe)
- `lookup_user_by_email(email)` – sucht User mit `mail_to == email` (case-insensitive)
- `lookup_user_by_telegram_chat_id(chat_id)` – sucht User mit `telegram_chat_id == chat_id`

**Konfiguration:** Nutzer-Profile liegen in `data/users/<user_id>/user.json` mit Feldern `mail_to` und `telegram_chat_id`.

### Telegram Bot-Menü (Automatisches Setup)

**Neu seit Issue #671 (2026-06-09):** Das Telegram-Bot-Menü wird **automatisch beim FastAPI-Service-Start**
aus `BOT_COMMANDS` gesetzt und verifiziert:

- **Startup-Hook** (`api/main.py`, Lifespan): ruft `TelegramOutput.set_my_commands()` auf
- **Quelle:** `BOT_COMMANDS` in `src/output/channels/telegram.py` (8 Befehle: glance, heute, morgen, now, heute_gewitter, timeline_heute, timeline_morgen, hilfe)
- **Idempotent:** jeder Deploy/Restart stellt das Menü sicher
- **Fail-soft:** fehlender Bot-Token blockt den Service-Start nicht
- **Live-Verifikation (Post-Deploy):** Der Selftest prüft via `getMyCommands` gegen den Prod-Bot,
  ob das Live-Menü dem erwarteten Stand entspricht (Issue #671, AC-4)

Manuelle Verwaltung ist nur noch im Notfall nötig — siehe `docs/runbooks/telegram-webhook.md` → „Bot-Menü".

### Alert-System (Deviation-Kern, Issue #816)

**Komponenten:** `src/services/alert_state.py`, `src/services/trip_alert.py`, `src/services/deviation_alert_engine.py`, `src/services/point_weather.py`, `src/services/weather_change_detection.py`, `src/output/renderers/alert/` (kanonischer Renderer seit #917); zweiter Consumer seit #1169: `src/services/compare_alert.py`, `src/services/compare_location_weather_source.py`, `src/services/compare_weather_snapshot.py`

**Zweck:** Meldet **Abweichungen gegenüber dem letzten Briefing-Snapshot** statt absoluter Schwellwerte.

**Location-generischer Auswertungskern (Issue #1168, Epic #1095 Scheibe 1):** Die eigentliche
Auswertungslogik (Change-Detection-Aufruf, Filter significant, Filter gegen Melde-Gedächtnis,
Severity-Bestimmung, Quiet-Hours, Cooldown, Kanalwahl, Detektor-Wahl) lebt seit Issue #1168 in
`DeviationAlertEngine.evaluate()` (`src/services/deviation_alert_engine.py`) und operiert auf
generischen DTOs (`PointWeatherData`, `AlertEvaluationConfig`, `src/services/point_weather.py`)
statt auf `Trip`-Strukturen. `TripAlertService` ist nur noch ein dünner Adapter (baut
`AlertEvaluationConfig` aus Trip-Feldern via `TripSegmentWeatherAdapter`, ruft die Engine auf,
delegiert Rendering/Versand unverändert weiter). Trip ist der erste Consumer. Details/Alternativen:
`docs/adr/0021-shared-deviation-alert-engine.md`.

**Zweiter Consumer — Orts-Vergleich (Issue #1169, Epic #1095 Scheibe 2, live seit 2026-07-09):**
`CompareAlertService` (`src/services/compare_alert.py`) ruft dieselbe `DeviationAlertEngine`
für `ComparePreset`-Orte auf, ohne die Auswertungslogik zu duplizieren. Wetter-Beschaffung
über `compare_location_weather_source.py` (synthetisches Ein-Punkt-`TripSegment` +
`SegmentWeatherService`, damit Anker-Snapshot und Fresh-Wetter formidentisch sind). Der
Δ-Anker (ADR-0009: Abweichung vom zuletzt **gemeldeten** Stand) wird pro Ort in
`compare_weather_snapshot.py` persistiert (`data/users/<user_id>/compare_weather_snapshots/`)
und beim Report-Versand (`send_one_compare_preset()`) aktualisiert; der 15-Minuten-Check liest
nur. Versand ohne Trip-Bindung über `NotificationService.send_location_deviation_alert()`; der
geteilte Alert-Renderer zeigt bei gesetztem `AlertMessage.location_label` den Ortsnamen statt
der (bei einem Punkt sinnlosen) km-Spanne. Alarmkonfiguration ist in Scheibe 2 hartkodiert
(Default-Sensitivität „standard", 120 Min Cooldown, nur E-Mail) — editierbare UI folgt in
Scheibe 3 (#1170). Scheduler: `POST /api/scheduler/compare-alert-checks`, Go-Cron-Job
`compare_alert_checks` (`*/15 * * * *`, 7. registrierter Job). Details:
`docs/specs/modules/issue_1169_compare_alert_consumer.md`.

**Architektur:**

1. **Read-Only Briefing-Snapshot**
   - `WeatherSnapshotService.save()` wird NUR vom Briefing-Scheduler aufgerufen (nicht vom Alert-Pfad)
   - Snapshot bleibt stabil zwischen Briefings → erlaubt konsistente Δ-Vergleiche über mehrere Alert-Läufe

2. **Melde-Gedächtnis (`alert_state`)**
   - Persistenz: `data/users/<user_id>/alert_state/<trip_id>.json`
   - Schema: `{ "<metric>:<segment_id>": { "last_reported_value": float, "reported_at": ISO-8601 } }`
   - **Re-Alert-Logik:**
     - Neu (kein Eintrag): Alert sent, Eintrag angelegt
     - Stagnation (`|current - last| < threshold`): unterdrückt
     - Eskalation (`|current - last| >= threshold`): erneut Alert, Wert aktualisiert
   - **Reset:** beim Briefing-Versand komplette Datei löschen

3. **Symmetrische Δ-Erkennung**
   - `WeatherChangeDetectionService.detect_changes(cached, fresh, include_absolute=False)` — nur Δ, keine absoluten Regeln im Alert-Pfad
   - Schwellen Slice 1 (MetricCatalog-Defaults): Temp ±5°C, Wind/Böen ±20 km/h, Regen ±10 mm, Nullgradgrenze ±200 m, Gewitter ±1 (Issue #959/ADR-0019: einzige Winter-Alert-Metrik ist `freezing_level`)
   - `AlertEvent.threshold` ist immer die Δ-Auslöseschwelle, nie ein Absolut-Referenzwert — „über/unter Schwelle" heißt `abs(value_to − value_from) ≥ threshold` (ADR-0013)

4. **Kanonischer Alert-Render-Pfad (Issue #917)**
   - Renderer: `src/output/renderers/alert/` (model.py, project.py, render.py) — ersetzt das gelöschte `alert_compact.py`
   - 4 Render-Pfade: `render_subject()`, `render_email()`, `render_telegram()`, `render_sms()`
   - Projektion: `to_alert_message()` erzeugt `AlertMessage` aus `WeatherChange`-Events
   - Dynamischer Betreff: `Trip · km · Richtung · Metrik`; faktisch-generische H1
   - Severity-Sortierung pro Metrik; ASCII-SMS ≤140 Zeichen mit Überlauf-Marker
   - Enthält NICHT: Stundentabellen, Ausblick, Gewitter-Vorschau, Pills, Vortag-Vergleich, Statistik
   - km-Erweiterung: `build_segment_label()` zeigt `"Etappe N, km X–Y, HH–HH"` wenn km vorhanden (Issue #801)
   - Mail-Header: `X-GZ-Mail-Type: deviation-alert` (unterscheidet von `trip-briefing` und `compare`)
   - **Nicht zu verwechseln mit** `src/output/renderers/alert/official_alerts.py` (Issue #1087) —
     eigenständiges Modul im selben Verzeichnis für **amtliche** Behörden-Warnungen (Epic #1033/#1073,
     Compare UND Trip-Briefing), keine Δ-Abweichungslogik

5. **Radar-/Regen-Nowcast-Alert segmentbewusst (Issue #822) — kanonischer Renderer seit Issue #919**
   - Gemeinsamer Segment-Helfer: `src/services/trip_segments.py:convert_trip_to_segments(trip, target_date) -> List[TripSegment]`
     - Extrahiert SSoT-Segmentlogik aus dem Briefing-Scheduler
     - Erzeugt konsistente Segmente mit `segment_id`, `start_point`/`end_point`, `start_time`/`end_time`
   - **Segment-Auswahl in `check_radar_alerts`:**
     - Statt Blindcheck am `stage.waypoints[0]`: wähle das aktuelle oder nächste Segment nach `now_utc`
     - Logik: Aktives Segment = `seg.start_time <= now_utc <= seg.end_time`; wenn nicht: erstes Segment vor `now_utc`; wenn alle vorbei: kein Alert
   - **Nowcast + Ort-Label:**
     - Ein `get_nowcast()`-Call am `segment.start_point` (nicht am alten Stage-Waypoint)
     - `tz_for_coords(lat, lon)` bestimmt Tour-Zeitzone; `format_now_text(result, tz=tz)` gibt Onset-Zeit in Tour-TZ aus
     - `build_segment_label()` erzeugt „Etappe N, km X–Y" mit echten Strecken-Kilometern
   - **Kanonischer Render-Pfad (Issue #919):** `check_radar_alerts` konstruiert `AlertMessage(OnsetEvent(...))` und leitet durch dieselben vier Renderer wie der Abweichungs-Alert:
     - `render_subject(msg)` — Betreff: `[<trip>] km <a>–<b> · Regen/Gewitter in <m> Min`
     - `render_email(msg)` — HTML + Plain mit Onset-Uhrzeit, Intensity-Label, Quellenangabe, Cooldown-Block
     - `render_telegram(msg)` — Fettzeile + Detail mit Onset-Uhrzeit und Quelle
     - `render_sms(msg)` — Token `R!<min>` (Regen) oder `TH!<min>` (Gewitter), ≤140 Zeichen GSM-7
     - `OnsetEvent`-Datenklasse: `onset_minutes`, `onset_time`, `km_from`/`km_to`, `is_convective`, `intensity_label`, `source_label`
     - `AlertMessage.cooldown_display` trägt den dynamischen Cooldown-Text (z.B. „2 Stunden")
     - `src/outputs/radar_alert.py` ist gelöscht — kein separater Inline-Body-Bau mehr
   - **Throttle-Semantik unverändert** (Issue #773): `radar_alert_throttle.json` + `alert_log` auch bei Best-Effort-Versandfehlern

6. **Konvektiver Sicherheits-Override (Issue #883, Epic #813 Slice 4)**
   - Der Radar-Wächter unterdrückt einen Alert normalerweise, wenn das Briefing den Regen für die Onset-Stunde bereits angekündigt hatte (`_briefing_precip >= 0.5` → kein Alert).
   - **Ausnahme:** Ist der Nowcast konvektiv (`NowcastResult.is_convective=True`, d.h. Gewitter/Hagel), durchbricht dieser Override die Briefing-Unterdrückung — ein aufziehendes Gewitter ist ein anderer Entscheidungsmoment als eine Briefing-Zeile vom Morgen.
   - Normaler Regen, Quiet Hours, Cooldown/Throttle und der Doppel-Alert-Guard bleiben weiterhin wirksam.
   - **Mail-Wording fallabhängig:** `"jetzt akut"` (Override, Regen war angekündigt) vs. `"im Briefing nicht angekündigt"` (normaler Nicht-Ankündigungsfall).
   - **Scope:** Eingriff ausschließlich in `check_radar_alerts()` (~2 Zeilen); `check_and_send_alerts` (Δ-Pfad) bleibt strikt unverändert.

**Datenfluss:**
```
check_and_send_alerts(trip, cached_weather)
  ↓ load alert_state (leer oder mit Einträgen)
  ↓ detect_changes(cached, fresh, include_absolute=False)
  ↓ pro Change: Re-Alert-Logik (Neu/Stagnation/Eskalation)
  ↓ render_deviation_alert() → (html, plain)
  ↓ Versand + alert_state updaten

check_radar_alerts(user_id)  [Issue #822 + #919]
  ↓ pro Trip: convert_trip_to_segments(trip, today)
  ↓ Segment-Auswahl nach now_utc (aktiv/nächstes)
  ↓ get_nowcast(segment.start_point.lat, segment.start_point.lon)
  ↓ build_segment_label() + format_now_text(tz=tour_tz)
  ↓ AlertMessage(OnsetEvent(...))  [seit #919]
  ↓ render_subject / render_email / render_telegram / render_sms
  ↓ Versand + throttle/log setzen

_send_briefing_report() [trip_report_scheduler.py]
  ↓ WeatherSnapshotService.save(snapshot)
  ↓ AlertStateService.reset(trip_id)

check_all_compare_presets(user_id)  [CompareAlertService, Issue #1169]
  ↓ pro Preset × Ort: compare_weather_snapshot.load(preset_id, location_id)  (Anker, ggf. leer)
  ↓ compare_location_weather_source.fetch(location) → fresh PointWeatherData
  ↓ DeviationAlertEngine.evaluate(cached, fresh, AlertEvaluationConfig(defaults), alert_state)
  ↓ Cooldown-Check (preset_id-Store, 120 Min) + AlertStateService-Dedup ("preset_id:location_id")
  ↓ to_point_alert_message() → NotificationService.send_location_deviation_alert()

send_one_compare_preset() [scheduler_dispatch_service.py, nach Report-Versand]
  ↓ compare_weather_snapshot.save(preset_id, location_id, fresh)  je Ort im Preset (Δ-Anker-Update)
```

**Mandantentrennung:** `AlertStateService(user_id=...)`, `TripAlertService(user_id=...)` laden/speichern strikt unter `data/users/{user_id}/alert_state/` resp. `data/users/{user_id}/radar_alert_throttle.json`.

Siehe: `docs/features/issue-816-alert-deviation-core.md`, `docs/specs/modules/issue_816_alert_deviation_core.md`, `docs/specs/modules/issue_822_radar_nowcast_segment.md`, `docs/specs/modules/issue_883_acute_danger_override.md`

---

## Frontend Architecture (SvelteKit)

**Stack:** SvelteKit 5 (Svelte 5 Runes), Tailwind CSS, Playwright E2E

**Location:** `frontend/` (SvelteKit project root)

### Directory Structure

```
frontend/
├── src/
│   ├── app.css                    # Global design tokens (@layer base) + atom styles (@layer components)
│   ├── app.html                   # HTML shell (Fonts: Inter Tight, JetBrains Mono)
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ui/               # Atom Library (shadcn + Gregor atoms)
│   │   │   │   ├── button/, card/, dialog/, badge/  # shadcn imports
│   │   │   │   ├── btn/, g-card/, pill/, eyebrow/, dot/, topo/, elev-sparkline/  # Gregor atoms (Epic #133)
│   │   │   │   └── sidebar/      # Main navigation (Issue #145)
│   │   │   ├── atoms/             # Atom-Schicht (Atomic Design Level 1, Epic #371)
│   │   │   │   └── *.svelte       # Token-basierte UI-Primitive (Button, Label, Badge, etc.)
│   │   │   ├── molecules/         # Molecule-Schicht (Atomic Design Level 2, Epic #372)
│   │   │   │   └── *.svelte       # Combinations of atoms (FieldGroup, StatCard, etc.)
│   │   │   ├── organisms/         # Organism-Schicht (Atomic Design Level 3, Epic #471)
│   │   │   │   ├── index.ts       # Barrel re-export (TripHeader, TripWizardShell, AlertRulesEditor)
│   │   │   │   └── organisms.test.ts  # Source-inspection tests (no ui/ imports)
│   │   │   ├── trip-wizard/       # Trip creation/editing wizard
│   │   │   │   ├── TripWizardShell.svelte
│   │   │   │   ├── Stepper.svelte
│   │   │   │   ├── steps/*.svelte
│   │   │   │   └── templates/
│   │   │   ├── trip-detail/       # Trip display & editing
│   │   │   │   ├── TripHeader.svelte
│   │   │   │   ├── TripTabs.svelte
│   │   │   │   ├── waypoints/
│   │   │   │   │   ├── MapCanvas.svelte    # Leaflet-Karte mit OpenTopoMap-Tiles (Issue #495)
│   │   │   │   │   └── ...
│   │   │   │   └── index.ts       # Barrel (TripHeader re-exported in organisms/)
│   │   │   ├── alert-rules-editor/  # Alert configuration
│   │   │   │   ├── AlertRulesEditor.svelte
│   │   │   │   └── components/
│   │   │   ├── compare/           # Compare-Wizard (Epic #438)
│   │   │   │   ├── CompareWizard.svelte
│   │   │   │   ├── CompareMatrix.svelte
│   │   │   │   ├── compareWizardState.svelte.ts
│   │   │   │   ├── compareMetricDefs.ts
│   │   │   │   ├── steps/
│   │   │   │   └── __tests__/
│   │   │   ├── shared/            # Cross-feature components (OutputLayoutEditor, etc.)
│   │   │   ├── preview/           # Email/SMS preview renderers
│   │   │   ├── email-preview/     # Email rendering
│   │   │   ├── mobile/            # Mobile-only components
│   │   │   ├── edit/              # Form & edit views
│   │   │   ├── briefings-tab/     # Briefings configuration
│   │   │   ├── alerts-tab/        # Alerts configuration
│   │   │   └── utils/             # Helpers (cn(), type utilities)
│   │   ├── types.ts               # Shared TypeScript types
│   │   └── stores/                # Svelte Stores (auth, theme, etc.)
│   └── routes/
│       ├── +layout.svelte         # Root layout (includes Sidebar)
│       ├── +page.svelte           # Home (Trip Cockpit Dashboard, Epic #134)
│       ├── trips/                 # Trip management (CRUD wizard)
│       ├── compare/               # Compare wizard + subscription list
│       │   ├── +page.svelte       # Create new comparison
│       │   ├── [id]/
│       │   │   └── edit/
│       │   │       ├── +page.svelte
│       │   │       └── +page.server.ts
│       │   └── +page.server.ts
│       ├── account/               # User account settings
│       └── _design/               # Component showcase (dev-only)
├── e2e/                           # Playwright E2E tests
│   ├── helpers.ts                 # Auth helpers, shared utilities
│   ├── design-system-lauf-a.spec.ts
│   ├── design-system-lauf-b.spec.ts
│   └── *.spec.ts                  # Feature tests
└── package.json                   # Dependencies (SvelteKit, Tailwind, shadcn, bits-ui, etc.)
```

### Atomic Design Layers (Epic #368, #371, #372, #471)

Frontend components follow Atomic Design principles with 3 explicit layers:

| Layer | Location | Purpose | Examples | Epic |
|-------|----------|---------|----------|------|
| **Atoms** | `components/atoms/` | Base UI primitives | Button, Label, Badge, Icon | #371 |
| **Molecules** | `components/molecules/` | Combinations of atoms | FieldGroup, StatCard, Tabs | #372 |
| **Organisms** | `components/organisms/` | Complex page sections | TripHeader, TripWizardShell, AlertRulesEditor | #471 |

**Import Rules:**
- **Atoms** may import from `ui/` (shadcn + gregor primitives)
- **Molecules** may import from `atoms/` and `ui/`
- **Organisms** may import from `atoms/`, `molecules/`, and other `organisms/` — **never** directly from `ui/`
- **Routes** should prefer importing from `organisms/` and `molecules/`, using `atoms/` only for rare custom layouts

**Organism Barrel** (`components/organisms/index.ts`):
Re-exports 4 core organisms without moving their physical source files:
```typescript
export { default as TripHeader } from '../trip-detail/TripHeader.svelte';
export { default as TripWizardShell } from '../trip-wizard/TripWizardShell.svelte';
export { default as AlertRulesEditor } from '../alert-rules-editor/AlertRulesEditor.svelte';
export { default as OutputLayoutEditor } from '../shared/OutputLayoutEditor.svelte';
```

Consumers import via: `import { TripHeader, OutputLayoutEditor } from '$lib/components/organisms'`

See `docs/design-system/COMPONENTS.md` for the canonical component catalog.

### Component Library (Epic #133)

#### Design-System Lauf A (Issues #141, #142, #145)

- **Design Tokens:** `--g-*` namespace in `app.css @layer base`
  - Primary colors: `--g-accent`, `--g-paper`, `--g-ink`
  - Surfaces: `--g-surface-0`, `--g-surface-1`, `--g-surface-2`
  - Semantic: `--g-success`, `--g-warning`, `--g-danger`, `--g-info`
  - Weather: `--g-wx-rain`, `--g-wx-sun`, `--g-wx-wind`, `--g-wx-snow`, `--g-wx-thunder`, `--g-wx-fog`
  - Typography: `--g-font-ui` (Inter Tight), `--g-font-data` (JetBrains Mono)
  - Layout: `--g-radius-*`, `--g-elev-*` (shadows)

- **Sidebar Component:** `$lib/components/ui/sidebar/Sidebar.svelte`
  - Main navigation container
  - Responsive design, icon-based nav items
  - Extracted from `+layout.svelte` (Issue #145)

### Trip-Editor & Compare-Editor Save-Strategien (Issue #758)

**Trip-Editor (Auto-Save):**
- **TripHeader.svelte** rendert einen einheitlichen `SaveIndicator` (zentral sichtbar über allen Tabs)
- Alle Trip-Änderungen (Name, Etappen, Briefing, Metriken) triggern **Auto-Save** mit Debounce (~700 ms)
- Zustände: `idle` (sauber) → `saving` (API-Call läuft) → `idle` (erfolgreich) oder `error` (Fehler)
- Explizite Speichern-Buttons wurden aus Trip-Editor-Tabs entfernt
- Flush vor Navigation: `beforeNavigate` leert Debounce-Queue, bevor der Nutzer einen anderen Tab/Trip aufruft (Datenverlust-Schutz)
- **Store:** `saveStatusStore.svelte.ts` — zentraler State für beide Editoren, pro Editor-Instanz ein eigenes Objekt

**Compare-Editor (Expliziter Save):**
- Behält expliziten Speichern-Button
- Nutzer-Änderungen zeigen `dirty`-Zustand, erst Speichern-Klick triggert Save
- Gleiches `SaveIndicator`-Komponente wie Trip-Editor, aber andere Zustands-Quelle (`compareWizardState`)
- Unabhängig vom Trip-Editor-Indikator (kein globales Sharing)

**Implementierungs-Details:**
- `SaveIndicator.svelte` ist Atom-Komponente (rendert nur UI-State)
- `saveStatusStore.svelte.ts` exportiert Setter-Funktionen (`setSaving()`, `setSaved()`, `setError()`, `setDirty()`)
- Auto-Save nutzt Try-Catch mit explizitem Error-Reporting statt `console.error`
- Alle PUT-Endpunkte nutzen Read-Modify-Write-Semantik (Backend, `api.ts`), kein partielles Überschreiben

Siehe `docs/specs/modules/issue_758_save_indicator.md` für technische Details.

#### Design-System Lauf B (Issues #143, #144, #146)

**Atom Components** — lightweight, token-based UI primitives:

| Component | Slot | Props | Purpose |
|-----------|------|-------|---------|
| `<Btn>` | `btn` | `variant`, `size` | Interactive button |
| `<GCard>` | `g-card` | - | Surface container with elevation |
| `<Pill>` | `pill` | `tone` | Compact label (semantic colors) |
| `<Eyebrow>` | `eyebrow` | - | All-caps metadata text |
| `<Dot>` | `dot` | `tone`, `size` | Circular indicator (weather/status) |
| `<TopoBg>` | `topo-bg` | `opacity` | Topographic background pattern |
| `<ElevSparkline>` | `elev-sparkline` | `data`, `width`, `height`, `active` | SVG elevation sparkline |

**Styling Approach:**
- `data-slot="<name>"` + `data-variant`/`data-tone`/`data-size` attributes
- Global CSS selectors in `app.css @layer components`
- Token references only (no arbitrary Tailwind values)
- Safer for Tailwind 4 scanning

**Reference:** `docs/reference/frontend_components.md`, `docs/reference/sveltekit_best_practices.md`

### Data Flow

```
User Action (Route/Form)
  ↓
SvelteKit Handler (+layout.server.ts, +page.server.ts)
  ↓
REST API Call (gregor-api)
  ↓
Go Backend (Business Logic)
  ↓
JSON Response
  ↓
SvelteKit Page Component (load() data → Svelte $state)
  ↓
Component Render (Atoms + Slots + Effects)
  ↓
HTML + Client-Side Interactivity
```

### Authentication & Authorization

**Auth Methods:**
- **Username/Password:** `/api/auth/register` + `/api/auth/login` (traditional, bcrypt-hashed)
- **Passkey/WebAuthn (Issues #450, #467):** 
  - V1 Identifier-First: `/api/auth/passkey/register/begin|finish` (Face ID, Touch ID, Windows Hello, YubiKey), `/api/auth/passkey/login/begin|finish`, `/api/auth/passkey/credentials/{id}` (delete)
  - V3 Discoverable (login without username): `/api/auth/passkey/discoverable/begin|finish` (Conditional UI with native autofill picker)
- **Google OAuth (Issue #425, feature-gated via `GZ_GOOGLE_CLIENT_ID`):** OAuth 2.0 Authorization Code flow
  - Init: GET `/api/auth/google/init` → redirect to Google consent
  - Callback: GET `/api/auth/google/callback?code=...&state=...` → create/lookup user, issue session
  - User-ID format for OAuth users: `g-{8hex}` to prevent session parsing errors
- **Magic Link (Issue #449):** `/api/auth/magic-link` + `/api/auth/magic-link/verify` (6-digit OTP per E-Mail)

**Session Format:** Server-side-signed cookie `gz_session = <userId>.<timestamp>.<hmacSig>` (24h TTL, HttpOnly, SameSite=Lax, Secure on HTTPS) — identisch über alle Auth-Methoden hinweg.

**User Model Extensions (Issues #425, #450):**
- `PasswordHash` field optional (`omitempty` JSON tag) — leerer Hash für reine OAuth/Passkey-User
- `PasskeyCredentials[]` array für FIDO2 credentials (Credential-ID, Public-Key, Attestation-Type, Transport, AAGUID, SignCount, Label, timestamps)
- `OAuthProvider` + `OAuthSub` für externe Identitäten
- Profile endpoint (`GET /api/auth/profile`) returns `has_passkey: bool` + `passkeys[]` array (public metadata only, no secret key material)

**Server-side Validation:**
- `hooks.server.ts` verifies session cookie signature
- Protected Routes: All routes except `/login`, `/register`, `/magic-link`, `/api/auth/google/*` require valid session
- Client-side: Svelte Stores track auth state; components react to changes
- Development: `/_design` showcase is auth-protected (development convenience)

### Testing Strategy

**E2E Tests (Playwright):**
- All UI features must have E2E tests
- Use `[data-testid="..."]` for stable selectors
- Validate component structure via `[data-slot="..."]`
- Test token application (computed styles, not hardcoded colors)

**Example:** `frontend/e2e/design-system-lauf-b.spec.ts` (10 tests)

### Frontend Dependencies

**Key libraries:**
- **SvelteKit 5:** React framework + SSR
- **Svelte 5:** Runes-based reactivity
- **Tailwind CSS:** Utility-first styling
- **Leaflet (~1.9.4):** Interactive maps for waypoint editing (Issue #495)
  - Tile layer: OpenTopoMap (topographic tiles with contour lines)
  - Waypoint markers and polyline routing
  - Zoom control and bounds fitting
- **@types/leaflet:** TypeScript types for Leaflet
- **shadcn/svelte:** Pre-built accessible components (buttons, dialogs, etc.)
- **bits-ui:** Headless component library
- **@lucide/svelte:** Icon library
- **svelte-dnd-action:** Drag-and-drop utilities

### Build & Deployment

- **Build:** `npm run build` → static SvelteKit app (Node adapter)
- **Development:** `npm run dev` → local server (port 5173)
- **Production:** Systemd service `gregor-frontend.service` (port 5173)
- **Nginx Reverse-Proxy:** Routes `/` to SvelteKit frontend

### Multi-Step Wizards

The frontend includes two configurable wizard systems:

#### Trip Wizard (Epic #136)
- **Purpose:** Create/edit trips with stages and waypoints
- **Steps:** 4 (Name/Profile, Stages, Waypoints, Review)
- **State Management:** `tripWizardState.svelte.ts`
- **Component:** `frontend/src/lib/components/trip-wizard/`
- **Persistence:** `/api/trips` POST/PUT

#### Compare Wizard (Epic #438)
- **Purpose:** Create/edit location comparison subscriptions
- **Steps:** 5 (Name/Profile, Locations, Ideal Values, Layout, Schedule)
- **State Management:** `compareWizardState.svelte.ts`
- **Component:** `frontend/src/lib/components/compare/`
- **Persistence:** `/api/subscriptions` POST/PUT
- **Current Status:**
  - ✓ Step 1: Name + Activity Profile (Issue #440, auto-preselect via #547)
  - ✓ Step 2: Location selection (Issue #440)
  - ✓ Step 3: Ideal value ranges per metric (Issue #441, uses `compareMetricDefs.ts`)
  - ✓ Step 4: Output formatting layout (Issue #442)
  - ✓ Step 5: Schedule + delivery config (Issue #443)

**Key Data Structures:**
- `ActivityProfile` — Enum type for activity categories (WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN)
- `MetricDef` — Descriptor for a weather metric (label, unit, range, input kind)
- `IdealRange` — Min/max thresholds for a metric (numeric or enum)
- `PROFILE_METRICS_WITH_SCALES` — Metric definitions indexed by profile
- `IDEAL_DEFAULTS` — Default ranges per profile (populated on first render)

---

## Integration Points

### Backend ↔ Frontend

**REST API Contracts:**

*Authentication:*
- `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` — Password-based auth
- `/api/auth/passkey/register/begin|finish` — WebAuthn passkey registration (Issue #450)
- `/api/auth/passkey/login/begin|finish` — WebAuthn passkey login (Identifier-First)
- `/api/auth/passkey/discoverable/begin|finish` — WebAuthn passkey login (Conditional UI, login without username) (Issue #467)
- `/api/auth/passkey/credentials/{id}` — Passkey management (delete)
- `/api/auth/google/init|callback` — Google OAuth (Issue #425, feature-gated)
- `/api/auth/magic-link`, `/api/auth/magic-link/verify` — Magic Link OTP (Issue #449)
- `/api/auth/profile` — User profile + passkey list

*Data:*
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/trips` | GET/POST | Trip CRUD |
| `/api/trips/{id}` | GET/PUT/DELETE | Individual trip |
| `/api/trips/{id}/stages` | GET/POST | Stage management |
| `/api/trips/{id}/briefing-history` | GET | Briefing delivery log for archived trip (Issue #559) |
| `/api/locations` | GET/POST | Location library (for compare) |
| `/api/subscriptions` | GET/POST | Create/list subscriptions (compare) |
| `/api/subscriptions/{id}` | GET/PUT/DELETE | Individual subscription |
| `/api/subscriptions/{id}/preview` | POST | Preview comparison output |
| `/api/preview/{id}/email\|sms\|telegram` | GET | Trip report preview rendering (demo mode optional) |
| `/api/account` | GET/PUT | User account |
| `/api/scheduler/status` | GET | Job status monitoring |

**Subscription Types:**
- `"trip"` — Auto-generated reports per stage
- `"compare"` — Location comparison (configurable via wizard)

**Compare Subscription Payload:**
```json
{
  "id": "compare-001",
  "name": "Ski 2026",
  "enabled": true,
  "config": {
    "activity_profile": "WINTERSPORT",
    "location_ids": ["hut-a", "hut-b", "hut-c"]
  },
  "display_config": {
    "ideal_ranges": {
      "temp_max_c": { "min": -5, "max": 5 },
      "snow_depth_cm": { "min": 30, "max": 200 },
      "wind_max_kmh": { "min": 0, "max": 40 }
    },
    "output_layout": { /* TBD #442 */ },
    "schedule": { /* TBD #443 */ }
  }
}
```

**Format:** JSON, standard HTTP methods (GET, POST, PUT, DELETE)

**Auth:** Session cookies (format: `<userId>.<timestamp>.<hmacSig>`, set by Login or Passkey endpoints, 24h TTL)

### Frontend → Channels

Frontend **does not** directly call E-Mail/SMS channels. Instead:
- User configures subscriptions in `/account`
- Backend scheduler handles actual sends (cron-based)
- Frontend displays subscription status + last-send timestamps

---

## Monitoring & Observability

- **Frontend Errors:** Client-side error logging (future: Sentry)
- **Backend Metrics:** BetterStack heartbeats for jobs (morning/evening reports, trip alerts, compare subscriptions)
- **Health Checks:** `/api/health` (backend), `/` (frontend)
- **Scheduler Status:** `/api/scheduler/status` shows last-run timestamps and errors per job

**Compare-Specific:**
- Frontend validates wizard steps before saving
- Backend accepts any `display_config` (opaque, no schema enforcement)
- No server-side validation of `ideal_ranges` values yet (future enhancement)

See `~/.claude/CLAUDE.md` → Monitoring for details.

---

## Feature Documentation

- **Epic #438 (Compare Wizard):** `docs/features/epic-438-compare-wizard.md`
- **Epic #134 (Trip Cockpit Dashboard):** `docs/features/epic-134-cockpit-dashboard.md`
- **Epic #1033 (Amtliche Alerts im Orts-Vergleich):** `docs/features/epic-1033-compare-official-alerts.md` — additives `src/services/official_alerts/`-Modul (Slices 1, 2, 5 implementiert), Registry-Pattern analog Provider-Adapter, Fail-soft-Garantie, pro Orts-Vergleich ein-/ausschaltbar (Slice 5)
- **Epic #1073 (Amtliche Alerts AT/IT + querschnittliche Nutzung):** `docs/features/epic-1073-alerts-at-it.md` — Slice 1 (#1085, implementiert): `GeoSphereWarnSource` (AT), erste Nicht-FR-Quelle im Registry, auth-frei, koordinatenbasiert, `warnstufeid`→`level`-Mapping; Slice 3 (#1087, implementiert): amtliche Warnungen jetzt auch in Trip-Briefings, gemeinsame Renderer-Komponente `src/output/renderers/alert/official_alerts.py` (Compare + Trip, keine Kopie), Trip-Toggle `official_alerts_enabled`
- **Epic #1127 (Cross-Provider-Fallback bei Open-Meteo-Total-Ausfall):** `docs/features/epic-1127-cross-provider-fallback.md` — zweite Redundanz-Stufe nach dem Intra-Open-Meteo-Modell-Fallback (#1115, ADR-0018): greift nur, wenn Open-Meteo als Verteiler komplett ausfällt. Slice 0 (#1141, implementiert): Routing-Unterbau `src/providers/region_routing.py` (Land/Alpen-Rechtecke AT/DE/FR) + Stub-Direktprovider `src/providers/regional_stubs.py`, Einhängepunkt `src/providers/openmeteo.py:864`, neuer `fallback_reason="cross_provider_total_outage"`; Slice AT (#1142, implementiert): `GeoSphereDirectProvider` ersetzt `at_direct`-Stub; FR/DE (#1143/#1144) offen
- **Design System:** `docs/design-system/` (CHARTER, COMPONENTS, TOKENS, SCREENS)
- **API Contract:** `docs/reference/api_contract.md`

---

## Related Issues

- **#559:** Archive page completion — Briefing-Verlauf modal, Template copy, Event summary ✓
- **#440:** Compare Wizard shell + Steps 1–2 ✓
- **#441:** Compare Wizard Step 3 (Ideal Ranges) ✓
- **#442:** Compare Wizard Step 4 (Layout) — planned
- **#443:** Compare Wizard Step 5 (Schedule) — planned
- **#134:** Trip Cockpit Dashboard ✓
- **#136:** Trip Wizard completion ✓
- **#133:** Design System (Atoms + Tokens) ✓