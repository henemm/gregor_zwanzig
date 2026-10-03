---
entity_id: trip_mehrreiter_konfliktschutz
type: bugfix
created: 2026-10-01
updated: 2026-10-01
status: draft
workflow: fix-1433-mehrreiter-412-datenverlust
version: "1.0"
tags: [trip, konfliktschutz, etag, if-match, teilfelder, mehrreiter, "#1433", "#2381", "#2375", "#2345"]
---

# Trip-Konfliktschutz im Mehrreiter-Fall: Teilfeld-Nutzlasten, Konflikt-Sperre, Retry

## Approval

- [ ] Approved

## Purpose

Auf der Trip-Seite `/trips/[id]` kann nach einem Konflikt (HTTP 412, „jemand anderes hat den Trip inzwischen geändert“) ein anschließendes Speichern aus einem anderen Reiter die fremde Änderung still überschreiben. Zusätzlich gibt es einen Verlustweg ganz ohne Konflikt: ein per Telegram/SMS gesetztes „nächstes Briefing überspringen“ (`report_config.skip_next`) wird beim nächsten Speichern in einem offenen Reiter still zurückgeschrieben. Beide Wege haben dieselbe Wurzel: Reiter senden eine veraltete Vollkopie fremder Felder. Diese Spec stellt die Trip-Reiter auf Teilfeld-Nutzlasten um (jeder Reiter sendet nur seine eigenen Felder), verhindert unbedingtes Schreiben nach einem 412, hält die Konfliktanzeige „Nochmal speichern“ über Reiterwechsel hinweg am Leben und schließt die verbleibenden Lücken ohne If-Match (Versand-Reiter, Pausieren/Archivieren, Unload-Flush).

## Source

- **File:** `frontend/src/lib/api.ts` (412-Behandlung, keepalive), `frontend/src/lib/etagRegistry.ts` (Konflikt-Markierung), `frontend/src/lib/stores/saveStatusStore.svelte.ts` (Konflikt-Sperre, Liste, Retry), `frontend/src/routes/trips/[id]/+page.svelte` (`/state`), sieben Trip-Schreiber unter `frontend/src/lib/components/` (siehe §2)
- **Identifier:** `pickEigenfelder` (neu, `shared/pickEigenfelder.ts`), `waehleEigenfelder` (wird Adapter, `compare/compareEditorSave.ts:319`), `markiereKonflikt`/`istKonflikt` (Registry, neu), `meldeKonflikt` (Controller, neu), `retryConflict`, `baueTripSpeicherung`, `buildAlarmeDeliveryPayload`

## Estimated Scope

- **LoC:** produktiv ca. +300/-80, zusätzlich Tests. Über dem 250-Limit ⇒ in /40 `workflow.py set-field loc_limit_override 500` setzen. Ein Workflow, eine Spec, alle ACs (nie auf eine Scheibe verengen).
- **Files:** ca. 14 produktive Frontend-Dateien, 2 Doku-Dateien, neue Tests. **Keine** Go-Datei, **keine** Python-Datei.
- **Effort:** high. Risiko MEDIUM-HIGH: zentrale Speicherlogik beider Flächen (Trip und Ortsvergleich teilen `api.ts`, Registry, `saveStatusStore`, `shared/`-Reiter).
- **Lieferbedingung (Reihenfolge, zwingend):** (1) Teilfeld-Payloads aller Trip-Schreiber, (2) Registry-/Controller-Änderung (Konflikt-Sperre, Liste, Retry), (3) keepalive-/`/state`-Änderungen. **(2) wird nie ohne (1) ausgeliefert, (3)/`/state` nie ohne (2) und die keepalive-Regel.** Grund: gültiges If-Match plus veralteter Spread ergibt 200 OK und segnet den Verlust ab (Lehre #2381). Teilfelder sind der eigentliche Schutz, Registry/Controller ergänzen ihn für gleiche Schlüssel.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/api.ts` (`send` :72, If-Match :88, 412→`discardEtag` :136, keepalive-Bypass :183-185) | Modul | Transport; 412-Behandlung und Unload-Flush werden geändert |
| `frontend/src/lib/etagRegistry.ts` (`knownEtags` :13, `adoptEtagFromPageLoad` :107, `discardEtag` :117, `enqueueTripWrite` :151) | Modul | ETag-Registry; neu: Zustand `konflikt` je Ressource |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` (`doSave` :120-143, `retryConflict` :152-164, `schedule` :184-189) | Modul | Geteilter Controller `tripSaveCtl` (Trip) und `hubSaveCtl` (Ortsvergleich) |
| `frontend/src/routes/trips/[id]/+page.svelte` (`tripSaveCtl` :43, PATCH `/state` :106, `discardEtag` :137, `handleTripUpdate` :226) | Seite | Controller-Eigentümer, Pausieren/Archivieren |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` (Montage :196-235, Flush beim Reiterwechsel :170-176, `handleActivityChange` :188) | Komponente | Nur der aktive Reiter ist gemountet |
| `frontend/src/lib/components/compare/compareEditorSave.ts` (`waehleEigenfelder` :319, `buildComparePresetPartialPayload` :295) | Modul | Vorlage aus #2375; wird Adapter auf `pickEigenfelder` |
| `internal/handler/trip.go` (`UpdateTripHandler` :268, If-Match :310, Lock :281), `internal/handler/config_merge.go` (`mergeConfigMap` :11-22), `internal/handler/etag.go` (`ifMatchAllows` :52-65), `internal/handler/weather_config.go` (If-Match :99-112, Merge :114-125) | Go (**unverändert**) | Server-Merge ist einstufig: Top-Level-Schlüssel überschreiben, Nested-Inhalt wird als Ganzes ersetzt, gelöscht wird nie |
| `internal/store/briefing_fingerprint.go:35` | Go (unverändert) | Trip-ETag = SHA-256 der Bytes der Trip-Datei |
| `src/services/trip_command_processor.py`, `trip_report_scheduler.py`, `track_resolution.py`, `src/app/loader.py save_trip` | Python (**unverändert**) | Fremdschreiber derselben Datei ohne ETag/Lock (realistische 412-Quelle und W2-Quelle) |
| `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`, `docs/specs/modules/issue_1395_s3_etag_registry.md` | Doku | Fortschreibung bzw. „Abgelöst durch“-Hinweis |
| `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` | Spec (Vorlage) | Überlässt `api.ts:136` ausdrücklich #1433 |

## Implementation Details

### 1. Befund (gegen origin/main verifiziert)

Zwei unabhängige Verlustwege, eine Wurzel:

- **W1 (Ticket):** Fremdänderung ⇒ 412 in Reiter A ⇒ `api.ts:136` verwirft den ETag ⇒ Reiter B schreibt **ohne If-Match** mit veraltetem Spread von `display_config`/`report_config` ⇒ die Fremdänderung wird überschrieben. Zusätzlich springt der gemeinsame Controller `conflict → saving → idle` (`doSave`/`schedule` rufen `setSaving()` ohne Konflikt-Guard), „Nochmal speichern“ verschwindet, `_lastFailed` verwaist, der Retry-Guard (:153) macht den Knopf wirkungslos. Reiterwechsel unmountet Reiter A (`TripTabs.svelte:196`); der Flush beim Wechsel (:170-176) greift nur bei `hasPending`, nach einem Fehler ist es `false`. Die abgelehnte Änderung von A erreichte den Server nie; verloren gehen die Fremdänderung (Server) und As Eingabe (Oberfläche).
- **W2 (ohne 412):** Der Python-Core setzt und verbraucht `report_config.skip_next` in derselben Datei (`trip_command_processor.py:2658-2660`, Verbrauch `trip_report_scheduler.py:975-987`), ohne Go-Lock und ohne ETag. `BriefingScheduleTab` speichert **immer mit `keepalive: true`** (`:41-48`, `:92`) ⇒ nie If-Match; `WeatherMetricsTab` sendet das ganze `report_config` (`:980/:1012/:1034`). Beide schreiben den Altwert zurück.
- **Weitere Lücken:** PATCH `/state` ohne If-Match (bewusst, S2 AC-15) mit anschließendem `discardEtag` (`+page.svelte:137`) ⇒ nächster Schreibvorgang unbedingt. `api.ts:183-185` sendet bei keepalive nie If-Match; der Kommentar `:178-182` („einziger Aufrufer = Unload-Flush“) ist falsch.

### 2. Feld-Eigentümer-Tabelle (Hauptrisiko des Fixes)

Server-Merge (`config_merge.go:11-22`) ist einstufig. Ein Reiter sendet daher je Objekt (`display_config`, `report_config`) **nur die Schlüssel, die er selbst bedient**; alle anderen bleiben unerwähnt und damit serverseitig unangetastet. Belege wurden per Grep im Code festgestellt, nicht geraten.

**2.1 Trip-Top-Level**

| Reiter / Schreiber | Eigene Top-Level-Felder | Beleg |
|---|---|---|
| Kopf (TripHeader) | `name` | `trip-detail/TripHeader.svelte:45` |
| Aktivität (TripTabs) | `activity` | `trip-detail/TripTabs.svelte:188` |
| Etappen | `stages` | `edit/EditStagesPanelNew.svelte:167,193,428` |
| Wertebereiche (CorridorEditor) | `corridors` | `shared/corridor-editor/CorridorEditor.svelte:272` (Mobile :228) |
| Alarme | `official_warnings` (`{enabled}`), `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`, `alert_channels` (alle vier Kanäle), `alert_channel_thresholds` (nur wenn bekannt) | `shared/alarme-tab/alarmeDeliveryPayload.ts:106-135` |
| Wetter-Metriken (Trip-PUT) | `official_alerts_enabled` | `shared/WeatherMetricsTab.svelte:980,1012,1034` |

**2.2 `display_config` (Unterschlüssel)**

| Schlüssel | Eigentümer-Reiter | Beleg |
|---|---|---|
| `metric_alert_levels` | **Alarme** (einziger Eigentümer, seit #1371) | `alarmeDeliveryPayload.ts:129-133`; Wertebereiche schreibt ihn nicht (`CorridorEditor.svelte:261-268`) |
| `metrics` | **Wetter-Metriken** | `WeatherMetricsTab.svelte:934-935` (`/weather-config`) |
| `channel_layouts` | Wetter-Metriken | `WeatherMetricsTab.svelte:920-936` |
| `preset_name` | Wetter-Metriken | `WeatherMetricsTab.svelte:937` |
| `telegram_kurzform` | Wetter-Metriken | `WeatherMetricsTab.svelte:938` |
| `outlook_metrics` | Wetter-Metriken (`null` = „nie eingestellt“ ⇒ Schlüssel **nicht** senden) | `WeatherMetricsTab.svelte:945-947` |
| `outlook_metric_formats` | Wetter-Metriken (`null` ⇒ Schlüssel nicht senden) | `WeatherMetricsTab.svelte:952-954` |
| *(keiner)* | **Wertebereiche** sendet heute die ganze `trip.display_config` (`CorridorEditor.svelte:272`), ändert aber **keinen** display-Schlüssel (Kommentar :261-268, `buildCorridorSavePayload` liefert `metric_alert_levels` nur für den Ortsvergleich-Zweig, der Trip-Zweig sendet es nicht). Neue Nutzlast: `{ corridors }` ohne `display_config`. | `CorridorEditor.svelte:261-274`, `corridorEditorState.ts:351-363` |
| `channel_layouts_per_report`, `show_night_block`, `night_interval_hours`, `thunder_forecast_days`, `sms_metrics`, `multi_day_trend_reports` (display-Ebene), `alert_preset`, `trip_id`, `updated_at` | **kein Reiter-Eigentümer** („Python-eigen / Spread-Altlast“): heute nur über den Vollspread mitgeschickt, ein Bedienelement existiert nicht | Python-Schreiber `src/app/loader.py:1757-1810` |

**2.3 `report_config` (Unterschlüssel)**

| Schlüssel | Eigentümer-Reiter | Beleg |
|---|---|---|
| `enabled`, `morning_enabled`, `evening_enabled`, `morning_time`, `evening_time` | **Versand** | `shared/versand-tab/reportConfigPayload.ts:128-139` (`schedule`-Gruppe) |
| `multi_day_trend_morning`, `multi_day_trend_evening`, `multi_day_trend_reports` | **Versand** (Entscheidung Tech Lead) | `reportConfigPayload.ts:135-138` |
| `send_email`, `send_telegram`, `send_sms`, `send_premium_sms` | **Versand** | `reportConfigPayload.ts:140-146`, `shared/VersandTab.svelte:158-167` |
| `telegram_style` | **Versand** (nur Versand besitzt den Schalter) | `reportConfigPayload.ts:25-28,121-124` |
| `show_compact_summary`, `wind_exposition_min_elevation_m` | **Wetter-Metriken** (Inhalt-Karte via `EditReportConfigSection`, `showSchedule=false`, `showChannels=false`) | `edit/EditReportConfigSection.svelte:248-251`, Montage `WeatherMetricsTab.svelte:1983-1990` |
| `show_stage_stats`, `show_metrics_summary`, `show_outlook`, `email_format`, `show_yesterday_comparison` | **Wetter-Metriken** | `EditReportConfigSection.svelte:252-270` |
| `day_window_start_hour`, `day_window_end_hour` | **Wetter-Metriken** (Tagesfenster-Karte) | `WeatherMetricsTab.svelte:1771-1779` |
| `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics` | **unklar** (UI seit #723 entfernt, werden von `EditReportConfigSection` nur mit dem Live-Wert weitergeschrieben, `:252-258`). **Festlegung:** werden **nicht** gesendet; da nicht bedienbar, gibt es nichts zu speichern, und der Server hält den Bestand. Kein Roundtrip-Test. | `edit/reportConfigWrite.ts` (`@deprecated`-Kommentare) |
| `alert_on_changes` | **unklar** (kein Trip-Reiter bedient es; nur der Listenseiten-Dialog `molecules/ReportConfigDialog.svelte:132` und `routes/trips/+page.svelte:59`) | `types.ts:251` |
| `change_threshold_temp_c`, `change_threshold_wind_kmh`, `change_threshold_precip_mm`, `trip_id` | **kein Reiter-Eigentümer** (Legacy/Python), nur über den Vollspread mitgereist | `src/app/loader.py:1866-1868` |
| `skip_next`, `paused_until`, `updated_at` | **Python-eigen, nie vom Client gesendet** | Setzen/Verbrauch: `src/services/trip_command_processor.py:2387/2467/2633/2660/2961/2977`, `src/services/trip_report_scheduler.py:975-987`, `src/services/track_resolution.py:333`; Schreibweg `src/app/loader.py:1884-1886` |

**2.4 Nicht-Reiter-Schreiber (kein Teilfeld-Thema, aber Teil dieser Spec)**

| Schreiber | Was | Behandlung |
|---|---|---|
| PATCH `/state` | `paused`, `archived` | siehe §5 |
| Python-Core | `skip_next`, `paused_until`, `updated_at`, Delta-Schwellen, `alert_rules` | Fremdschreiber; Client sendet diese Schlüssel nie |

**Regeln der Tabelle**

1. Die Allowlist je Reiter wird in `pickEigenfelder(quelle, { top, display, report })` kodiert (neue Datei `frontend/src/lib/components/shared/pickEigenfelder.ts`). Alles außerhalb der Allowlist wird nie gesendet, auch wenn der Reiter es in seiner lokalen Kopie hält (das erzwingt „Python-eigene Schlüssel nie“ und „unbekannte Schlüssel nie“ strukturell).
2. **Löschsemantik:** `[]`, `{}` und `""` werden **gesendet**, nur `undefined` wird übersprungen. Der Server-Merge löscht nie ein Feld; eine Leerauswahl (alle Metriken abgewählt, Korridore geleert, `official_alerts_enabled=false`) muss deshalb explizit als leerer Wert ankommen.
3. Pick findet **nur beim Senden** statt; lokaler Zustand und Dirty-Erkennung bleiben unberührt (Rumpf bleibt Funktion, `baueTripSpeicherung` liest ihn beim Abfeuern).
4. **Versand-Reiter:** schickt nur Versand-Schlüssel; **Wetter-Metriken** schickt nur Inhalt-/Tagesfenster-Schlüssel. Beide dürfen sich nicht mehr gegenseitig `day_window_*` bzw. Versandzeiten überschreiben (heute: Vollkopie des ganzen Blobs).
5. **Geteilte Schlüssel auf Schlüsselebene gibt es im Trip nicht** (Befund: `metric_alert_levels` gehört nur Alarme, `metrics` nur Wetter-Metriken; Nachbarn schickten sie nur als Kopie). Gleichzeitiges Ändern *desselben* Schlüssels in zwei Tabs bleibt eine Known Limitation.
6. Der Compare-Zweig der geteilten Reiter behält seine Feldlisten aus `compare_konfliktschutz_teilfelder.md` §2 unverändert (Trip/Compare-Teilungsregel).

### 3. Teilfeld-Nutzlasten umsetzen (Lieferstufe 1)

- Neue generische Funktion `pickEigenfelder` (`shared/`); `waehleEigenfelder` und `buildComparePresetPartialPayload` werden dünne Adapter darauf (Signaturen und Compare-Tests unverändert).
- Alarme: `alarmeDeliveryPayload.ts` sendet `display_config: { metric_alert_levels }` statt `{...currentDisplayConfig, metric_alert_levels}`; der zweite Parameter `currentDisplayConfig` wird überflüssig.
- Wertebereiche (Desktop und Mobile): Rumpf `{ corridors }`.
- Wetter-Metriken: `/weather-config` mit Allowlist aus §2.2; Trip-PUT mit `official_alerts_enabled` und `report_config`-Allowlist aus §2.3 (Inhalt + Tagesfenster).
- Versand (`BriefingScheduleTab`): `report_config`-Allowlist aus §2.3 (Versand-Schlüssel), `trip` lokal aus der **Server-Antwort** statt `{...trip, report_config: snapshot}`.
- Kopf (`{name}`) und Aktivität (`{activity}`) sind bereits Teilfeld, melden 412 aber noch nicht an den Controller (siehe §4).

### 4. Konflikt-Sperre statt Verwerfen, Konfliktanzeige bleibt (Lieferstufe 2)

1. `api.ts:136`: bei 412 wird der ETag **nicht** mehr verworfen. Die Registry markiert die Ressource als `konflikt` und behält den alten ETag. Jeder weitere Schreibvorgang trägt das alte If-Match und bekommt wieder 412 (nichts wird geschrieben). `trip.*` im lokalen Zustand wird bei 412 **nicht** ersetzt (sonst ginge As abgelehnte Eingabe verloren).
2. `saveStatusStore`: `schedule()` und `doSave()` verlassen den Zustand `conflict` nicht. `_lastFailed` wird eine **deduplizierte Liste** (ein Eintrag je Reiter/Schreiber), jeder Eintrag hält den Rumpf **komponentenunabhängig** (Funktion/Payload, kein Verweis auf eine Komponenteninstanz). Reiter B darf bei offenem Konflikt weiter speichern, bekommt 412 und landet in derselben Liste; die Sperre trägt der Server, keine Client-Sperre.
3. `meldeKonflikt` (neu am Controller): TripHeader (`TripHeader.svelte:45`) und `handleActivityChange` (`TripTabs.svelte:188`, heute ohne `try/catch` und an Controller vorbei) melden 412 an den Controller.
4. `retryConflict` („Nochmal speichern“): GET des Trips ⇒ `trip` **und** ETag **gemeinsam** aus der Antwort übernehmen (nie den ETag allein adoptieren bei lokal veraltetem `trip`) ⇒ alle Einträge der Liste erneut senden (jeder Eintrag enthält nur seine Eigenfelder, daher idempotent) ⇒ Konflikt-Markierung löschen. Funktioniert, obwohl der Reiter, der den Konflikt ausgelöst hat, nach einem Reiterwechsel nicht mehr angezeigt wird.
5. Der Konflikt endet nur durch `retryConflict` oder Neuladen der Seite.
6. Gilt gleichermaßen für `hubSaveCtl` im Ortsvergleich (gleiche Klasse, gleicher Store, gleiche Registry).

### 5. Lücken schließen (Lieferstufe 3)

- **Unload-Flush bei offenem Konflikt:** Heute sendet `api.ts:183-185` bei `keepalive` nie If-Match. Neu: Ist die Ressource in der Registry als `konflikt` markiert, trägt auch ein keepalive-Request das (alte) If-Match ⇒ Server antwortet 412, nichts wird geschrieben. Ohne Konflikt bleibt keepalive wie heute (If-Match fehlt, nicht serialisiert; der Unload-Flush darf weder warten noch an einem unsichtbaren 412 scheitern). Kommentar `api.ts:178-182` wird korrigiert.
- **Versand-Reiter:** kein Dauer-`keepalive` mehr. Speichern läuft wie bei den anderen Reitern über den Controller (`schedule`), `init` (keepalive) wird nur beim echten Unload-Flush durchgereicht.
- **Pausieren/Archivieren** (`routes/trips/[id]/+page.svelte:106/:137`): statt `discardEtag`: (a) offene Speichervorgänge des Controllers flushen, (b) PATCH `/state`, (c) GET des Trips; die GET-Antwort ersetzt `trip` **und** den ETag gemeinsam. Bei offenem Konflikt wird **nichts** adoptiert, der Konflikt bleibt bestehen. Der PATCH bleibt ohne If-Match (S2 AC-15, bewusste Altentscheidung).
- **`/weather-config` → Trip-PUT** ist nicht atomar: schlägt Schritt 2 mit 412 fehl, steht Schritt 1 schon. Mit der Konflikt-Sperre bleibt der Konflikt bis zum Retry sichtbar; der Retry ist mit Teilfeldern idempotent.

### 6. Code-Teilung (Trip/Ortsvergleich)

`pickEigenfelder` entsteht **einmal** in `shared/`; Trip-Reiter und Compare-Adapter nutzen sie gemeinsam. Registry, Store und `api.ts` sind ohnehin geteilt. Kein neuer Compare-only- oder Trip-only-Baustein; Adversary-Prüfpunkt „hätte das ein geteilter Baustein sein müssen?“ ⇒ ja, daher geteilt.

### 7. Mandantentrennung

Kein neuer und kein geänderter Endpoint, Go und Python unverändert. Die bestehende Trennung (`s.WithUser(middleware.UserIDFromContext(...))`) gilt unverändert; es entsteht **keine neue Zwei-Nutzer-Pflicht**. Die Zwei-Kontext-Tests unten sind zwei Sitzungen/Schreiber desselben Nutzers.

### 8. Test-Harness

`frontend/src/lib/__tests__/fakeTripServer.ts` wird erweitert: einstufiger Merge (`{merge: true}`, gespiegelt an `mergeConfigMap`) und `foreignWrite` (simuliert den Python-Fremdschreiber: Schreiben ohne If-Match, ETag ändert sich). Frontend-Tests laufen über `node --test` (kein Vitest).

## Expected Behavior

- **Input:** Nutzer bearbeitet einen Trip in mehreren Reitern bzw. Tabs/Geräten, oder ein Telegram-/SMS-Befehl ändert den Trip zwischenzeitlich.
- **Output:** Nach einem Konflikt bleibt „Nochmal speichern“ sichtbar, bis der Nutzer es ausführt oder neu lädt. Kein Speichern aus einem anderen Reiter überschreibt die Fremdänderung. Nach „Nochmal speichern“ stehen Fremdänderung und eigene Änderungen gemeinsam auf dem Server. Ein per Telegram gesetztes „nächstes Briefing überspringen“ bleibt beim Speichern in beliebigen Reitern erhalten.
- **Side effects:** Jede PUT-Nutzlast der Trip-Reiter ist kleiner (nur Eigenfelder). Nach einem 412 laufen weitere Speichervorgänge bewusst in 412, bis der Konflikt aufgelöst ist.

## Test Plan

### Automated Tests (TDD RED), `node --test`

Dateien nach Verhalten benennen; die Zusicherung wirkt dort, wo sie wirkt (Server-Stand im Fake-Server nach dem Zusammenspiel mehrerer Schreiber), nicht nur in der Nutzlast-Form.

- [ ] **W1** `trip_mehrreiter_nach_412_kein_verlust.test.ts`: GIVEN Seed, Reiter A geladen, `foreignWrite` setzt `display_config.metrics=[y]`; WHEN A `metric_alert_levels` speichert (412, Controller `conflict`) und danach B `channel_layouts` über denselben Controller speichert; THEN Server-`metrics` bleibt `[y]`, der B-PUT trug If-Match und bekam 412, Controller bleibt `conflict`. Heute rot.
- [ ] **W2** `trip_python_skip_next_ohne_412.test.ts`: GIVEN `foreignWrite` setzt `report_config.skip_next=true`; WHEN der Versand-Reiter (frischer ETag) eine Versandzeit und der Wetter-Metriken-Reiter `day_window_start_hour` speichert; THEN `skip_next` bleibt `true`. Heute rot.
- [ ] `pick_eigenfelder_kernregel.test.ts`: `[]`/`{}`/`""` gehen durch, `undefined` wird übersprungen, `skip_next`/`paused_until`/`updated_at`/`change_threshold_*` und unbekannte Schlüssel nie; `waehleEigenfelder`-Adapter liefert dasselbe wie vorher.
- [ ] `trip_reiter_nutzlast_nur_eigene_felder.test.ts`: je Schreiber der Tabelle §2 genau die Eigenfelder (Alarme ohne Rest von `display_config`, Wertebereiche ohne `display_config`, Versand ohne `day_window_*`, Wetter-Metriken ohne Versandzeiten und ohne `metric_alert_levels`).
- [ ] `trip_reiter_roundtrip_jedes_feld.test.ts`: je Reiter jedes bedienbare Feld ändern, speichern, Server-Stand per Fake-Server prüfen (gegen vergessene Eigen-Schlüssel); inklusive Löschfälle (alle Metriken abwählen, Korridore leeren, Ausblick leeren, `official_alerts_enabled=false`).
- [ ] `trip_nach_412_folgeschreiben_traegt_altes_if_match.test.ts`: nach 412 trägt jeder weitere PUT (Reiter B, Kopf, Aktivität) das alte If-Match; Registry-Zustand `konflikt`.
- [ ] `trip_retry_nach_reiterwechsel.test.ts`: A erzeugt Konflikt, Reiter A wird ausgehängt, B speichert (412, Liste hat zwei Einträge), `retryConflict` ⇒ GET, `trip` und ETag gemeinsam ersetzt, beide Eigenfelder-Sätze erneut gesendet, Server enthält Fremdänderung, A und B, Konflikt-Markierung weg.
- [ ] `trip_unload_flush_bei_konflikt.test.ts`: keepalive-Request bei `konflikt` trägt If-Match ⇒ 412, Server-Stand unverändert; ohne Konflikt wie heute (kein If-Match, nicht serialisiert).
- [ ] `trip_state_flush_patch_get.test.ts`: Pausieren mit offenem Speichervorgang ⇒ Reihenfolge Flush, PATCH, GET; `trip` und ETag gemeinsam aus der GET-Antwort; bei offenem Konflikt keine Adoption.
- [ ] `trip_versand_reiter_ohne_dauer_keepalive.test.ts`: normales Speichern geht mit If-Match über die Warteschlange; `trip` kommt aus der Server-Antwort.
- [ ] `trip_kopf_aktivitaet_melden_konflikt.test.ts`: 412 bei `{name}`/`{activity}` führt zur Konfliktanzeige am Controller.
- [ ] Parität: `hubSaveCtl` zeigt „Nochmal speichern“ über Reiterwechsel gleich wie `tripSaveCtl`.

**Bewusst umzuschreiben (kein Regress, /40 nicht als Regression werten):**

| Test | Warum |
|---|---|
| `frontend/src/lib/__tests__/tripStateDiscardsEtag.test.ts` | zementiert „`/state` verwirft den ETag“; wird zu „Flush, PATCH, GET, gemeinsame Adoption“ |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | zementiert, dass `schedule()`/`doSave()` aus `conflict` herausgehen; wird zu „Konflikt bleibt“ |
| `frontend/src/lib/stores/__tests__/saveStatusConflictRetry.test.ts` | Liste statt Einzel-`_lastFailed`; Retry holt GET und führt alle Einträge aus (anpassen, nicht löschen) |
| `frontend/src/lib/__tests__/apiKeepaliveSkipsIfMatch.test.ts` | bleibt für den echten Unload ohne Konflikt; Fall „mit Konflikt trägt If-Match“ kommt hinzu |
| `frontend/src/lib/__tests__/apiTripEtagConflict.test.ts` (:261 `test_afterDiscard_…`) | bleibt grün (ruft `discardEtag` selbst auf); ergänzt um „nach 412 kein Discard“ |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts`, `frontend/e2e/issue-776-metrics-toggle.spec.ts` | **zu prüfen** in /40: hängen am Speichern der Reiter Wetter-Metriken/Versand; erwarten ggf. Vollkopie-Nutzlasten oder Dauer-keepalive |

**Müssen unverändert grün bleiben:** `frontend/src/lib/components/shared/__tests__/*_vergleich_konflikt_nochmal_speichern.test.ts` (u. a. `alarme_…`, `versand_…`) und alle Tests zu `waehleEigenfelder`/`buildComparePresetPartialPayload`, `compareEditorSave.test.ts`; Go `go test ./internal/handler` (keine Go-Änderung).

### Staging-Prüfplan (nach Merge, in `/e2e-verify`)

Test-Trip auf Staging (nie Sammel-Versand), Wegwerf-Nutzer, nicht das Hauptkonto.

1. **Fremdschreiben per zweitem Browser-Tab:** Tab 1 und Tab 2 öffnen denselben Trip. Tab 2 ändert im Reiter Wetter-Metriken eine Metrik und speichert. Tab 1 speichert danach im Reiter Alarme (Alarm-Empfindlichkeit) ⇒ erwartet: Konfliktanzeige „Nochmal speichern“ sichtbar. Tab 1 wechselt in den Reiter Versand und speichert dort eine Zeit ⇒ erwartet: Konfliktanzeige **bleibt**; per API-GET `/api/trips/{id}` hat der Server weiter die Metrik aus Tab 2 und nicht die Alarm-/Versandänderung aus Tab 1. Dann „Nochmal speichern“ ⇒ API-GET zeigt Metrik aus Tab 2, Alarm-Empfindlichkeit und Versandzeit aus Tab 1.
2. **Fremdschreiben per Telegram-Befehl (Python):** Im Test-Trip den Befehl senden, der `skip_next` setzt („nächstes Briefing überspringen“; Eingang über den echten Kanal-Eingang). API-GET bestätigt `report_config.skip_next=true`. Offenen Reiter **ohne Neuladen** bedienen: im Versand-Reiter eine Zeit ändern, im Reiter Wetter-Metriken das Tagesfenster ändern ⇒ API-GET: `skip_next` weiterhin `true`, beide Änderungen gespeichert, **keine** Konfliktanzeige für den Versand-Reiter (frischer ETag aus der Antwort) bzw. Konfliktanzeige sichtbar, wenn der ETag veraltet war (beide Ausgänge dürfen `skip_next` nicht löschen).
3. **Pausieren bei offenem Konflikt:** Konflikt wie in 1 herstellen, dann „Pausieren“ ⇒ Konflikt bleibt sichtbar, API-GET: Fremdänderung unverändert.
4. **Seite verlassen bei offenem Konflikt:** Konflikt herstellen, dann Seite neu laden ⇒ API-GET: Fremdänderung unverändert, die Änderung des Tabs mit Konflikt ist nicht geschrieben.
5. **Ortsvergleich-Parität:** gleicher Ablauf wie 1 im Ortsvergleich-Hub (Name in Tab 2, Reiter-Wert in Tab 1) ⇒ Konfliktanzeige bleibt über Reiterwechsel; nach „Nochmal speichern“ beide Änderungen per API-GET.
6. Auf Staging ist nginx mit gzip dazwischen (ETags werden zu schwachen `W/"…"`); dieser Prüfplan ist deshalb nur dort aussagekräftig und ergänzt die lokalen Tests.

## Acceptance Criteria

- **AC-1:** Given ein anderer Tab oder Telegram hat den Trip geändert und ich speichere im Reiter Alarme (Konfliktanzeige „Nochmal speichern“ erscheint), When ich danach in einem anderen Reiter (z. B. Wetter-Metriken) speichere, Then bleibt die fremde Änderung auf dem Server unverändert erhalten und die Konfliktanzeige bleibt sichtbar. (Bug-Test W1)
- **AC-2:** Given der Konflikt ist offen und ich wechsle den Reiter, When ich in Reiter B speichere, Then bleibt „Nochmal speichern“ sichtbar, statt nach dem Speichern in Reiter B zu verschwinden.
- **AC-3:** Given Reiter A hatte den Konflikt ausgelöst und ist nach einem Reiterwechsel nicht mehr angezeigt, When ich „Nochmal speichern“ wähle, Then stehen auf dem Server danach die Fremdänderung, meine Änderung aus Reiter A und meine Änderung aus Reiter B, und die Konfliktanzeige verschwindet.
- **AC-4:** Given ein per Telegram oder SMS gesetztes „nächstes Briefing überspringen“ (`skip_next`) und ein bereits geöffneter Versand-Reiter, When ich dort eine Versandzeit oder einen Kanal speichere, Then bleibt „nächstes Briefing überspringen“ auf dem Server erhalten. (Bug-Test W2)
- **AC-5:** Given dieselbe Ausgangslage wie AC-4 und ein geöffneter Reiter Wetter-Metriken, When ich dort eine Anzeige-Einstellung oder das Tagesfenster speichere, Then bleibt „nächstes Briefing überspringen“ erhalten und das Tagesfenster wird gespeichert.
- **AC-6:** Given ich speichere im Versand-Reiter, When der Speichervorgang läuft, Then wird er wie bei den anderen Reitern in der Warteschlange mit der Versionsprüfung (If-Match) ausgeführt, statt bei jeder Geste ungeschützt zu schreiben, und der angezeigte Trip entspricht der Server-Antwort.
- **AC-7:** Given ein Konflikt ist offen und ich lade die Seite neu oder verlasse sie, When der automatische Abschluss-Speichervorgang beim Verlassen läuft, Then trägt er die Versionsprüfung, der Server lehnt mit 412 ab und die fremde Änderung bleibt erhalten; ohne offenen Konflikt wird beim Verlassen wie bisher gespeichert.
- **AC-8:** Given ich pausiere oder archiviere einen Trip, When die Aktion läuft, Then werden zuvor offene Speichervorgänge abgeschlossen, danach wird der Trip samt Versionsstempel gemeinsam neu vom Server geholt, und ein folgendes Speichern überschreibt keine fremde Änderung.
- **AC-9:** Given ein Konflikt ist offen, When ich pausiere oder archiviere, Then bleibt die Konfliktanzeige bestehen und der lokale Stand wird nicht still durch den Serverstand ersetzt.
- **AC-10:** Given ein Konflikt ist offen, When ich im Kopf den Namen oder die Aktivität ändere und der Server mit 412 antwortet, Then zeigt die Oberfläche „Nochmal speichern“ (kein stilles Scheitern) und die Fremdänderung bleibt erhalten.
- **AC-11:** Given Reiter Alarme, When ich Alarm-Kanäle, Schwellen, Ruhezeiten, Abkühlzeit, amtliche Warnungen oder die Alarm-Empfindlichkeit ändere und speichere, Then landet jedes dieser bedienbaren Felder auf dem Server und die Nutzlast enthält keinen weiteren Teil von `display_config` als `metric_alert_levels`.
- **AC-12:** Given Reiter Wertebereiche (Desktop und Mobile), When ich einen Korridor ändere, hinzufüge, entferne oder alle leere, Then landet das auf dem Server (auch die Leerung) und die Nutzlast enthält ausschließlich `corridors`.
- **AC-13:** Given Reiter Wetter-Metriken, When ich Metriken, Kanal-Layouts, Voreinstellung, Telegram-Kurzform, Ausblick, Ausblick-Formate, amtliche Warnungen, E-Mail-Inhalte oder das Tagesfenster ändere und speichere, Then landet jedes dieser bedienbaren Felder auf dem Server, auch eine Leerauswahl, und die Nutzlast enthält keinen Versand-Schlüssel und kein `metric_alert_levels`.
- **AC-14:** Given Reiter Versand, When ich Zeitplan, Zeiten, Kanäle, Telegram-Stil oder die Mehrtages-Trend-Schalter ändere und speichere, Then landet jedes dieser bedienbaren Felder auf dem Server und die Nutzlast enthält weder `day_window_*` noch E-Mail-Inhalt-Schlüssel noch Python-eigene Schlüssel.
- **AC-15:** Given Reiter Etappen sowie Kopf (Name) und Aktivität, When ich dort ändere und speichere, Then landet der Wert auf dem Server und die Nutzlast enthält nur das eigene Feld (`stages`, `name`, `activity`).
- **AC-16:** Given beliebiger Reiter, When er speichert, Then enthält die Nutzlast ausschließlich Schlüssel der Feld-Eigentümer-Tabelle seines Reiters (§2) und niemals `skip_next`, `paused_until`, `updated_at`, `change_threshold_*` oder unbekannte Schlüssel.
- **AC-17:** Given ich leere ein Feld (Metriken abwählen, Korridore leeren, Ausblick leeren, Kanal ausschalten), When ich speichere, Then kommt der leere Wert (`[]`, `{}`, `""`, `false`) auf dem Server an; ein nicht bedientes Feld (`undefined`) wird nicht gesendet.
- **AC-18:** Given ein Konflikt ist offen, When irgendein Reiter, der Kopf oder die Aktivität speichert, Then wird weiterhin die ursprüngliche Versionsprüfung mitgesendet (kein unbedingtes Schreiben nach 412) und der Server schreibt nichts.
- **AC-19:** Given „Nochmal speichern“ wird ausgeführt, When der Trip vom Server neu geholt wird, Then ersetzen Trip-Daten und Versionsstempel der Antwort den lokalen Stand gemeinsam (nie nur der Stempel allein), bevor die eigenen Änderungen erneut gesendet werden.
- **AC-20 (Parität Ortsvergleich):** Given der Ortsvergleich-Hub mit demselben Ablauf (Konflikt, Reiterwechsel, Speichern in anderem Reiter), When ich „Nochmal speichern“ wähle, Then verhält er sich gleich: Anzeige bleibt, nichts Fremdes wird überschrieben, beide Änderungen stehen danach auf dem Server.
- **AC-21 (Regressionswächter, heute erfüllt):** Given die bestehenden Ortsvergleich-Konflikt-Tests (`shared/__tests__/*_vergleich_konflikt_nochmal_speichern.test.ts`) und die Tests zu `waehleEigenfelder`/`buildComparePresetPartialPayload`, When die Tests nach dem Umbau laufen, Then sind sie grün; `waehleEigenfelder` liefert unverändert dieselben Teil-Bodies wie vor dem Umbau (Adapter auf `pickEigenfelder`).
- **AC-22 (Regressionswächter):** Given der Umbau, When `go test ./internal/handler` läuft und `git diff` geprüft wird, Then ist alles grün und es gibt keine Änderung unter `internal/` oder `src/`.
- **AC-23:** Given die dokumentierten Altentscheidungen, When die Änderung ausgeliefert ist, Then enthält `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` einen Absatz „Verhalten nach 412 / Teilfeld-Prinzip“ (Fortschreibung, kein neues ADR, kein Index-Eintrag) und `docs/specs/modules/issue_1395_s3_etag_registry.md` trägt einen „Abgelöst durch“-Hinweis zu „Discard nach 412“ und zur keepalive-Annahme („einziger Aufrufer = Unload-Flush“).
- **AC-24:** Given die in „Bewusst umzuschreiben“ genannten Tests, When sie auf die neue Zusicherung umgeschrieben sind, Then laufen sie grün und prüfen die neue Wirkung (Konflikt bleibt, Flush/PATCH/GET, Liste im Controller), nicht mehr das alte Discard-Verhalten.

## Known Limitations

- **Python `save_trip` schreibt ohne ETag und ohne Lock** (`src/app/loader.py:1922-1983`). Ein Fremdschreiber kann zwischen GET und PUT schreiben; der Schutz ist die Teilfeld-Nutzlast. Ein serverseitiges Erzwingen von If-Match (HTTP 428 bei fehlendem Header) wäre der größte Hebel, ist aber **nur Ausblick**: Python-Core, Listenseite, `PUT /api/briefings/{id}?kind=route` und weitere Pfade müssten zuerst alle mitziehen.
- **Gleicher Schlüssel, gleicher Zeitpunkt:** zwei Tabs ändern denselben Schlüssel (z. B. `metric_alert_levels`, `metrics`, `name`), der Retry sendet den lokalen Stand dieses Schlüssels. Kein Rebase.
- **`/weather-config` → Trip-PUT nicht atomar** (`tripSpeicherung.ts:61-72`); bei 412 im zweiten Schritt steht Schritt 1 bereits. Der Retry ist mit Teilfeldern idempotent.
- **PATCH `/state`** bleibt ohne If-Match (S2 AC-15); geschützt nur durch Flush/GET/Gemeinsam-Adoption und die Konflikt-Regel.
- **Reiter B darf bei offenem Konflikt speichern** und bekommt 412; die Sperre trägt der Server, keine Client-Sperre (bewusste Entscheidung).
- **Nicht bedienbare Altschlüssel** (`show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics`, `alert_on_changes`) werden von Trip-Reitern nicht mehr gesendet; ihr Eigentümer ist unklar (§2.3), der Server hält den Bestand.
- Toter Code (nicht eingehängt, nicht Teil dieser Spec): `AlertsTab.svelte`, `briefings-tab/BriefingsTab.svelte`, `trip-detail/WaypointsPanel.svelte` (letzterer enthält noch `{ stages }`-PUT).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; Fortschreibung von ADR-0036
- **Rationale:** Das Verhalten nach 412 steht in keinem ADR (nur in der S3-Spec und einem Code-Kommentar). ADR-0036 (Fingerabdruck über ETag/If-Match) wird um den Absatz „Verhalten nach 412 / Teilfeld-Prinzip“ fortgeschrieben; kein Kanal-, Provider-, Auth- oder Persistenzwechsel, daher kein neues ADR und kein Index-Eintrag. Setzt außerdem die Regel „Read-Modify-Write mit Merge, niemals Replace“ (CLAUDE.md, Daten-Schema-Reworks) clientseitig durch.

## Changelog

- 2026-10-01: Initial spec created (Issue #1433; Teilfeld-Prinzip aus #2375/#2381 auf die Trip-Seite übertragen; Konflikt-Sperre, Retry nach Reiterwechsel, Unload-Flush, `/state`)
