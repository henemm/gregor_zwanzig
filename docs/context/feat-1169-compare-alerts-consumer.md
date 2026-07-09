# Context: feat-1169-compare-alerts-consumer

Scheibe 2/3 von Epic #1095. Baut auf Scheibe 1 (#1168, live: location-generische
`DeviationAlertEngine`) auf. Epic-Gesamtkontext: `docs/context/feat-1095-compare-alerts.md`.
ADR-0009 (Abweichungs-Anker), ADR-0021 (shared deviation engine).

## Request Summary
Den Orts-Vergleich (ComparePreset) als **zweiten Consumer** der in Scheibe 1
herausgelösten `DeviationAlertEngine` anschließen: pro Vergleichs-Ort einen
persistierten Wetter-Snapshot (Δ-Anker analog Trip-Briefing-Snapshot) einführen,
alle 15 Min frisches Wetter dagegen auswerten und **Deviation-Alerts an die
Preset-Empfänger** versenden. **Default-Alarmkonfiguration** (editierbare UI erst
Scheibe 3, #1170).

## Kern-Architektur: Trip als Blaupause (erster Consumer)

Trip-Verdrahtung in `src/services/trip_alert.py::check_and_send_alerts` (`:86-242`),
Batch `check_all_trips` (`:261-345`). Sechs Bausteine, die Compare analog braucht:

| # | Baustein | Trip (bestehend) | Compare (Scheibe 2) |
|---|----------|------------------|---------------------|
| 1 | **Δ-Anker (cached weather)** | `WeatherSnapshotService` (`weather_snapshot.py`), keyed `trip.id`, `SegmentWeatherData`-Form, **geschrieben beim Briefing-Versand** (`data/users/<uid>/weather_snapshots/`) | **NEU: pro-Ort-Snapshot-Store**, keyed `preset_id + location`, `PointWeatherData`-Form, geschrieben **beim Compare-Report-Versand** |
| 2 | **fresh weather** | `_fetch_fresh_weather` → `SegmentWeatherService` → `TripSegmentWeatherAdapter.to_points` (`trip_alert.py:161,178-179`, `point_weather.py:79-98`) | **NEU: `LocationWeatherSource`-Impl** (Protocol steht: `point_weather.py:67-76`) → `PointWeatherData` je Ort |
| 3 | **AlertEvaluationConfig** | aus `trip.*` (`trip_alert.py:180-190`) | aus ComparePreset-Dict — **Defaults** (Preset hat noch keine Alert-Felder) |
| 4 | **alert_state (Dedup)** | `AlertStateService(user_id).load/save(trip.id)`, RMW im Caller (`trip_alert.py:175-177,222-231`) | dieselbe `AlertStateService`, `entity_id = f"{preset_id}:{location}"` (Namespace lt. `alert_state.py:4-9` bereits vorgesehen) |
| 5 | **Versand** | `NotificationService.send_deviation_alert(trip, weather, changes, channels)` — **trip-gebunden** (`notification_service.py:311-344`) | **NEU: preset-generische Sende-Methode** über `_dispatch_alert_message` (`:428`) / `to_alert_message` (braucht nur Name-String, `alert/project.py:49`) |
| 6 | **Cooldown** | eigene Datei `alert_throttle.json`, `DeviationAlertEngine.is_cooldown_active` (`trip_alert.py:79,397-420`) | analoger Cooldown-Store keyed `preset_id` (Default-Cooldown) |

## Related Files

### Scheibe-1-Fundament (wiederverwenden, NICHT ändern)
| Datei | Relevanz |
|------|----------|
| `src/services/deviation_alert_engine.py:204-245` | `evaluate(cached, fresh, config, alert_state) -> EvaluationResult` — Trip-frei, der geteilte Kern |
| `src/services/point_weather.py:30-98` | `PointWeatherData`, `AlertEvaluationConfig`, `LocationWeatherSource`-Protocol, `TripSegmentWeatherAdapter` |
| `src/services/alert_state.py:34-71` | `AlertStateService` — Dedup-Store, `entity_id`-basiert (Blind-Replace pro Datei, RMW im Caller) |

### Compare-Zielsystem (Anschluss)
| Datei | Relevanz |
|------|----------|
| `src/services/scheduler_dispatch_service.py:20-79` | `run_compare_presets_daily(user_id)` — lädt `compare_presets.json` (direktes Array), iteriert Presets pro Nutzer |
| `src/services/scheduler_dispatch_service.py:198-300` | `send_one_compare_preset(...)` — Report-Versand (E-Mail); **hier Snapshot-Write andocken** |
| `src/services/scheduler_dispatch_service.py:162-197` | `save_compare_preset_status` — RMW-Blaupause auf `compare_presets.json` |
| `src/services/comparison_engine.py:303-476` | `fetch_forecast_for_location(loc, hours)` via `ForecastService` — liefert **Dict/`raw_data`**, NICHT `PointWeatherData`-kompatibel |
| `src/app/config.py:54-69` | `Location` (Felder `latitude`/`longitude`/`name`/`elevation_m`) |
| `src/app/user.py:47-69` | `SavedLocation` (`id`/`name`/`lat`/`lon`/`elevation_m`/`display_config`) — von `load_all_locations` geliefert |

### Scheduler-Registrierung
| Datei | Relevanz |
|------|----------|
| `internal/scheduler/scheduler.go:91-104` | Job-Tabelle; Trip `*/15` (`:93`), Compare-Daily `0 6` (`:97`); `runForAllUsers` (`:124-145`) via `ListUserIDs` |
| `internal/scheduler/scheduler.go:112` | **Hardcoded `"6 jobs"`-Log** — bei neuem Job mitziehen |
| `api/routers/scheduler.py:50-57` | `POST /alert-checks` → `TripAlertService(user_id).check_all_trips()` (Muster) |
| `api/routers/scheduler.py:102-108` | `POST /compare-presets-daily` → `run_compare_presets_daily(user_id)` |
| `src/app/loader.py:794-816` | `list_all_user_ids()` — zentrale Nutzer-Enumeration |

### Renderer (geteilt, fast location-generisch)
| Datei | Relevanz |
|------|----------|
| `src/output/renderers/alert/project.py:49` | `to_alert_message(changes, segments, name, *, tz, stand_at)` — braucht nur **Name-String**, kein `Trip` |
| `src/output/renderers/alert/render.py:1-4` | `render_subject/email/telegram/sms` — metrik-generisch |

## Existing Patterns
- **Δ-Anker (ADR-0009):** Alarm = „Wetter weicht ab vom zuletzt GEMELDETEN Stand", nicht Absolut-Schwelle. Snapshot wird **beim Report-Versand** geschrieben, vom Alert-Check nur gelesen — der Alert-Check schreibt den Wetter-Snapshot NICHT neu (nur `alert_state`-Dedup + Cooldown). So akkumuliert die Abweichung seit dem letzten Report.
- **Per-User-Service-Instanz:** kein User-Loop im Service; Go-Cron `runForAllUsers` fächert über `ListUserIDs` auf, Router reicht `user_id` durch. Isolation über `user_id`-scoped Pfade.
- **RMW im Caller** für State-Dateien; `save_compare_preset_status` ist die Compare-RMW-Blaupause.
- **Konsolidieren statt duplizieren** (ADR-0021): Engine/Renderer/Dispatcher teilen, nur Report bleibt getrennt.

## Dependencies
- **Upstream:** `DeviationAlertEngine`, `PointWeatherData`/`AlertEvaluationConfig`/`LocationWeatherSource` (Scheibe 1), `SegmentWeatherService`/`ForecastService` (Wetter), `NotificationService._dispatch_alert_message`, `AlertStateService`, `list_all_user_ids`.
- **Downstream:** neuer Go-Cron-Job + Python-Endpoint; Preset-Empfänger (`empfaenger`, Fallback `settings.mail_to`).

## Risks & Considerations
1. **Wetter-Form-Lücke:** Compare fetcht heute via `ForecastService` (Dict/`raw_data`), aber die Engine braucht `PointWeatherData` mit `aggregated: SegmentWeatherSummary` + `timeseries: NormalizedTimeseries`. Diese Typen entstehen nur im **Segment-Pfad** (`SegmentWeatherService`). → `LocationWeatherSource`-Impl baut je Ort ein synthetisches Ein-Punkt-Segment und nutzt `SegmentWeatherService` + `TripSegmentWeatherAdapter`. **Cached und fresh müssen identische Form/Provider haben**, sonst falsche Deltas.
2. **Snapshot-Write-Trigger (Design-Frage für Analyse):** ADR-0009-korrekt ist Anker = Wetter beim letzten Compare-Report. → Snapshot beim `send_one_compare_preset` schreiben, Alert-Check nur lesen. Bootstrap: erster Alert-Check ohne Anker → kein Alarm.
3. **NotificationService trip-gebunden:** `send_deviation_alert` verlangt `Trip` + `SegmentWeatherData`. Preset-generische Methode nötig (über `_dispatch_alert_message`/`to_alert_message`, das nur Name-String braucht) — NICHT duplizieren.
4. **user_id-Isolation (PFLICHT):** mandantenfähig, **Test mit zwei verschiedenen Nutzern**; nie `"default"`-Fallback.
5. **Datenschema-Merge:** neuer Snapshot-/State-Store per RMW, kein Blind-Replace der Preset-Datei.
6. **Default-Config-Klärung:** Welche Default-Alarmschwellen/Kanäle gelten ohne UI? Kanäle mindestens E-Mail (Compare-Versand ist heute E-Mail-only); `metric_alert_levels`/Cooldown/Quiet aus sinnvollen Defaults.
7. **LoC:** Feature über Go+Python — voraussichtlich >250 LoC, Override-Freigabe beim PO einholen.
8. **Mail-Validator-Gate:** Deviation-Alert-Mail nutzt `alert/*`-Renderer (Radar-Mailgate); Verifikation gegen echt zugestellte Staging-Mail.
9. **Scheibe-3-Kompatibilität:** Snapshot-/Config-Schema so wählen, dass die editierbare UI (#1170) nur Felder ergänzt, nicht umbaut.

## Analysis

### Type
Feature (Full Process). Scheibe 2/3 des Epics #1095, Konsolidierungs-Ansatz (ADR-0021).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/services/compare_location_weather_source.py` | **CREATE** | `LocationWeatherSource`-Impl: synthetisches Ein-Punkt-`TripSegment` → `SegmentWeatherService` → `TripSegmentWeatherAdapter.to_points` (Form-Identität mit Trip-fresh garantiert) |
| `src/services/compare_weather_snapshot.py` | **CREATE** | Δ-Anker-Store, `PointWeatherData` serialisiert, keyed `preset_id__location_id`, `data/users/<uid>/compare_weather_snapshots/` |
| `src/services/compare_alert.py` | **CREATE** | `CompareAlertService` analog `TripAlertService`: Presets laden, Default-`AlertEvaluationConfig`, Engine-Aufruf, Cooldown/Quiet/Dedup, Versand. Enthält Cooldown-Store (analog `alert_throttle.json`, keyed `preset_id`, RMW) |
| `src/services/notification_service.py` | MODIFY | Neue trip-freie Methode `send_location_deviation_alert(entity_name, points, changes, channels)` → wiederverwendet `_dispatch_alert_message` |
| `src/output/renderers/alert/project.py` | MODIFY | Neue `to_point_alert_message()` (Name statt km-Spanne) neben `to_alert_message()` |
| `src/output/renderers/alert/model.py` + `render.py` | MODIFY | Additives optionales `location_label` — zeigt Ortsname statt „km 0–0" bei Punkt-Alarmen (Trip-Pfad unverändert: Feld nie gesetzt) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | In `send_one_compare_preset` nach Mail-Versand Snapshot-Write je Ort über denselben `LocationWeatherSource` |
| `api/routers/scheduler.py` | MODIFY | Neuer Endpoint `POST /api/scheduler/compare-alert-checks` (Muster `trigger_alert_checks`) |
| `internal/scheduler/scheduler.go` | MODIFY | Neuer `jobDef` `*/15` `compare_alert_checks` + Handler `compareAlertChecks()` + Job-Count-Log 6→7 (`:112`) |

**Keine Änderung:** `internal/model/compare_preset.go`, `internal/handler/compare_preset.go`, Frontend — Default-Config ist hartkodiert; Scheibe 3 ergänzt Felder (Pointer-Pattern) + UI, ohne Auswertungslogik umzubauen.

### Scope Assessment
- Dateien: 4 CREATE (Python), 5 MODIFY (4 Python + 1 Go)
- Geschätzte LoC: **~330–400 Produktivcode + ~150–250 Tests** → deutlich über dem 250-LoC-Workflow-Limit → **PO-Override nötig** (bzw. Aufteilung in 2 PRs möglich).
- Risk Level: **MEDIUM–HIGH** (Renderer-Erweiterung berührt geteilten Trip-Alarm-Renderer → Regressionsrisiko; Wetter-Form-Mismatch durch A1 strukturell ausgeschlossen)

### Technical Approach (Entscheidungen)
- **A — Wetter-Beschaffung: Variante A1** (synthetisches Ein-Punkt-`TripSegment` über `SegmentWeatherService`). Garantiert byte-identische Form für cached & fresh (beide durch denselben Impl), kein Duplikat von `WeatherMetricsService`-Aggregation. `_select_provider_for_location()` wiederverwenden. `enrich_ensemble=False` beim Fresh-Fetch (Quota, #288-Analogon).
- **B1 — Snapshot-Trigger:** Write in `send_one_compare_preset` (Report-Versand), Alert-Check liest nur → ADR-0009-korrekt („Abweichung seit letztem Report"). Zweit-Fetch beim Report-Versand (täglich/wöchentlich) akzeptabel; 15-Min-Check hat KEINEN Doppel-Fetch. Bootstrap: leerer `cached=[]` → Engine liefert `no_significant_changes`, kein Sonderfall-Code.
- **B2 — Default-Alarmkonfiguration:** alle 12 Tabellenmetriken auf `"standard"` (= `expand_preset("standard")`, wie Trip-Default), Cooldown **120 Min**, keine Quiet-Hours, Kanal **nur E-Mail** (Compare-Versand ist E-Mail-only; kein Preset-Telegram-Mapping). Kein neues Preset-Schema-Feld in dieser Scheibe. Service liest optionale Felder bereits vorwärtskompatibel via `preset.get(feld, DEFAULT)`.
- **C — Versand:** neue `send_location_deviation_alert()` + `to_point_alert_message()`; `_dispatch_alert_message` unverändert wiederverwendet (Konsolidierung, ADR-0021).

### Neuer Befund (nicht im Ausgangs-Issue): „km 0–0"
Der geteilte Alert-Renderer bettet fest eine Strecken-km-Spanne ein (`render.py:97-99,179,266,405`). Ein Vergleichs-Ort ist ein Punkt (km 0–0) → jede Compare-Alert-Mail zeigte sinnloses „km 0–0". → Renderer additiv um `location_label` erweitern (Ortsname statt km-Spanne). **Tech-Lead-Entscheidung: wird mitgefixt** (Lesbarkeits-Leitprinzip), Trip-Pfad bleibt per Snapshot-Test unverändert.

### Reihenfolge (atomar testbar)
1. `compare_location_weather_source.py` (+Unit-Test Form-Parität) →
2. `compare_weather_snapshot.py` (+Roundtrip/Bootstrap-Test) →
3. Renderer/Versand (`to_point_alert_message` + `send_location_deviation_alert` + `location_label`, Trip-Snapshot-Test grün) →
4. `compare_alert.py` (Integration, Zwei-Nutzer/Zwei-Preset-Test) →
5. Snapshot-Write-Hook + Python-Endpoint →
6. Go-Cron-Job + Job-Count-Fix + Staging-E2E.

### Open Questions (PO)
- [ ] LoC-Override für größeres Paket (bzw. Aufteilung in 2 PRs)?
- [ ] Default-Empfindlichkeit „standard" (wie Trips) bestätigt? — Tech-Lead-Default, editierbar ab Scheibe 3.

### Next Step
`/30-write-spec` — Spec mit AC-N-Format; PO gibt ACs frei ('go').
