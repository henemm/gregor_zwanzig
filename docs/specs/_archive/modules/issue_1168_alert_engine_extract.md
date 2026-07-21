---
entity_id: issue_1168_alert_engine_extract
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [alerts, refactor, epic-1095, shared-service]
---

<!-- Issue #1168 — Scheibe 1 von Epic #1095: Deviation-Alert-Engine location-generisch extrahieren -->

# Issue 1168 — Deviation-Alert-Engine location-generisch extrahieren (Scheibe 1/3, Epic #1095)

## Approval

- [x] Approved — PO „Freigabe" 2026-07-09

## Purpose

Den Deviation-Alert-Auswertungskern aus `TripAlertService` (`src/services/trip_alert.py`)
in einen **location-generischen Shared-Service** herauslösen, damit später auch der
Orts-Vergleich (Scheibe 2, #1169) ihn als zweiten Consumer anschließen kann — ohne die
Alarm-Logik zu duplizieren. **Reiner Umbau ohne Verhaltensänderung**: `TripAlertService`
wird zum dünnen Adapter, der die neue Engine aufruft; Trip-Alarme verhalten sich danach
bit-identisch zu vorher. Grundlage ist die Architektur-Gegenüberstellung in
`docs/context/feat-1095-compare-alerts.md` (Abschnitt „Architektur-Gegenüberstellung Trip
↔ Compare"): der Auswertungskern liest bereits keine Trip-/Stage-/Waypoint-Felder, sondern
arbeitet rein auf Wetterdaten-pro-Punkt + Config.

## Source

- **File:** `src/services/deviation_alert_engine.py` (NEU, ~180–220 LoC) — `DeviationAlertEngine`,
  enthält die extrahierten pure/staticmethod-Bausteine: Change-Detection, Filter significant,
  Filter-gegen-State, Severity, Quiet-Hours (inkl. Mitternachts-Wrap), Cooldown, Detektor-Wahl,
  Kanalwahl. Operiert auf `List[PointWeatherData]` + `AlertEvaluationConfig`, kennt kein `Trip`.
- **File:** `src/services/point_weather.py` (NEU, ~60–90 LoC) — generisches DTO
  `PointWeatherData` (id, name, lat/lon, timeseries, aggregated, fetched_at, provider,
  official_alerts — Analogon zu `SegmentWeatherData` ohne `TripSegment`-Kopplung) und
  `Protocol LocationWeatherSource` als schmale Beschaffungs-Schnittstelle über
  `providers.base.get_provider("openmeteo")`. Enthält `TripSegmentWeatherAdapter`, der
  bestehende `List[SegmentWeatherData]`-Ergebnisse (aus `SegmentWeatherService`) verlustfrei
  in `PointWeatherData` umwandelt — die Wetter-Beschaffung selbst (`SegmentWeatherService`,
  `ForecastService`) wird NICHT verändert, nur eine Adapter-Schicht darüber ergänzt.
- **File:** `src/services/trip_alert.py` (UMBAU zu Thin-Adapter, ca. -220/+60 LoC) —
  `TripAlertService` baut aus `Trip` + `List[SegmentWeatherData]` die generischen Eingaben
  (`PointWeatherData`-Liste via `TripSegmentWeatherAdapter`, `AlertEvaluationConfig` aus
  Trip-Feldern), ruft `DeviationAlertEngine.evaluate(...)`, und delegiert Rendering
  (ADR-0011) und Versand (ADR-0017, `NotificationService`) unverändert weiter.
- **File:** `src/services/alert_state.py` (MODIFY, ~10 LoC) — Parameter `trip_id` wird zu
  `entity_id` verallgemeinert (rein interne Umbenennung; alle Aufrufer nutzen den Parameter
  bereits positional, siehe Aufrufstellen in `trip_alert.py`/`trip_report_scheduler.py`).
  Dateipfad-Schema `data/users/<user_id>/alert_state/<entity_id>.json` bleibt unverändert —
  bestehende `<trip_id>.json`-Dateien sind weiterhin gültig, da Trip weiterhin `trip.id`
  als `entity_id` übergibt.
- **File:** `docs/adr/0021-shared-deviation-alert-engine.md` (NEU) — Architektur-Entscheidung
  „ein gemeinsames Deviation-Alert-Gehirn für Trip + Compare" (siehe AC-5).
- **File:** `tests/tdd/test_issue_1168_alert_engine_extract.py` (NEU) — Verhaltens-Tests, siehe
  Test Plan.

## Estimated Scope

- **LoC:** ~350–450 (Extraktion + Adapter-Schicht + neues DTO + ADR-Dokument)
- **Files:** 6 (2 neue Services, 1 Umbau, 1 kleine Modify, 1 ADR, 1 Testdatei)
- **Effort:** high

> **LoC-Limit-Hinweis:** Die Schätzung überschreitet voraussichtlich das Workflow-Limit von
> 250 LoC (`docs/context/rework-1168-alert-engine-extract.md`, Risiko 4). Vor der
> Implementierung ist `workflow.py set-field loc_limit_override <N>` **nach expliziter
> PO-Freigabe** zu setzen (Memory-Regel: kein Override ohne Permission) — nicht eigenmächtig.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.base.get_provider("openmeteo")` | intern | Gemeinsame Provider-Ebene, auf der sowohl Trip- als auch künftige Compare-Wetter-Beschaffung aufsetzen |
| `services.weather_change_detection.WeatherChangeDetectionService` | intern | Detektor-Logik, wird von der Engine unverändert per Detektor-Wahl aufgerufen |
| `services.alert_state.AlertStateService` | intern | Melde-Gedächtnis/Dedup, Parameter auf `entity_id` verallgemeinert |
| `services.alert_daily_limit` | intern | Tageslimit-Zähler, bleibt Trip-seitig im Adapter (nicht Teil dieser Scheibe) |
| `services.notification_service.NotificationService` | intern | Versand (ADR-0017), wird von `TripAlertService` weiterhin unverändert aufgerufen |
| `output.renderers.alert.*` | intern | Renderer (ADR-0011), unverändert |
| `services.segment_weather.SegmentWeatherService` | intern | Bestehende Trip-Wetter-Beschaffung, wird per Adapter in `PointWeatherData` gewandelt, nicht verändert |
| `app.trip.Trip` | intern | Quelle der `AlertEvaluationConfig`-Werte im Trip-Adapter (Regeln, Cooldown, Ruhezeiten, Kanäle) |
| `api.routers.scheduler` (`/api/scheduler/alert-checks`) | intern | Bestehender Aufrufpfad, unverändert — ruft weiterhin `TripAlertService.check_all_trips()` |
| Epic #1095 / Scheibe 2 (#1169) | Folge-Issue | Künftiger zweiter Consumer der Engine (Compare) — NICHT Teil dieser Scheibe |

## Implementation Details

### Architekturschnitt

```
TripAlertService (dünner Adapter)
  ├─ baut AlertEvaluationConfig aus Trip-Feldern
  │  (alert_rules/metric_alert_levels, cooldown, quiet_from/to, channels, report_config)
  ├─ wandelt List[SegmentWeatherData] → List[PointWeatherData]
  │  via TripSegmentWeatherAdapter (verlustfrei, keine Wertänderung)
  ├─ ruft DeviationAlertEngine.evaluate(points, config, alert_state) -> EvaluationResult
  └─ delegiert Rendering (ADR-0011) + Versand (ADR-0017) mit dem EvaluationResult
```

`DeviationAlertEngine.evaluate()` kapselt die Reihenfolge, die heute in
`TripAlertService.check_and_send_alerts()` linear abläuft: Detektor-Wahl → Change-Detection
→ Filter significant → Filter-gegen-State → Quiet-Hours-Check → Cooldown-Check →
Severity-Bestimmung → Kanalwahl. Die Reihenfolge und alle Bedingungen werden 1:1 aus den
bestehenden Methoden übernommen (keine Logikänderung), nur der Empfänger-Typ wird von
`Trip`/`List[SegmentWeatherData]` auf `AlertEvaluationConfig`/`List[PointWeatherData]`
umgestellt.

`AlertEvaluationConfig` ist ein reines Daten-Objekt (kein Trip-Bezug), das die heute über
`trip.*`-Attribute gelesenen Werte bündelt: `cooldown_minutes`, `quiet_from`, `quiet_to`,
`alert_rules`/`metric_alert_levels`, `display_config`-Auszug für Detektor-Wahl,
`report_config`-Auszug für Kanalwahl. Der Trip-Adapter baut dieses Objekt aus dem Trip; ein
künftiger Compare-Adapter (Scheibe 2/3) würde es aus `ComparePreset` bauen — beides ist
NICHT Teil dieser Spec.

### Nicht angetastet

- Rendering (`src/output/renderers/alert/*`, ADR-0011)
- Versand (`src/services/notification_service.py`, ADR-0017)
- Wetter-Beschaffung selbst (`SegmentWeatherService`, `ForecastService`, Provider-Adapter)
- Scheduler-Aufrufpfad (`api/routers/scheduler.py:50-57`, `internal/scheduler/scheduler.go`)
- Tageslimit (`alert_daily_limit`), Alert-Log (`_append_alert_log`), Radar-Onset-Pfad — bleiben
  im Trip-Adapter, da sie in der Architektur-Analyse nicht als geteilte Bausteine identifiziert
  wurden

## Expected Behavior

- **Input:** Für Trip-Pfad unverändert — `Trip` + `cached_weather`/`fresh_weather`
  (`List[SegmentWeatherData]`) über `TripAlertService.check_and_send_alerts()`. Intern neu:
  generische Eingaben `List[PointWeatherData]` + `AlertEvaluationConfig` + bestehendes
  Alert-State-Dict an `DeviationAlertEngine.evaluate()`.
- **Output:** Identische Alarm-Entscheidung wie vor dem Umbau (ausgelöst/unterdrückt,
  Metrik, Severity, Kanäle, Alert-Text) — Rendering und Versand unverändert.
- **Side effects:** Gleiche Seiteneffekte wie vorher (State-Datei-Schreibzugriff unter
  `data/users/<user_id>/alert_state/<entity_id>.json`, Versand über bestehende Kanäle,
  Alert-Log-Eintrag). Keine neuen Seiteneffekte durch diese Scheibe.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktiven Alarmregeln und ein Wetter-Zustand, der vor dem
  Umbau nachweislich einen Alarm auslöst (Metrik überschreitet die konfigurierte
  Delta-Schwelle), sowie ein zweiter Trip/Zustand, der bewusst KEINEN Alarm auslöst / When
  beide Fälle nach dem Umbau über `TripAlertService.check_and_send_alerts()` mit denselben
  Cached-/Fresh-Wetterdaten laufen / Then löst der erste Fall denselben Alarm mit
  identischer Metrik, Severity, Kanalauswahl und Alert-Text aus wie vor dem Umbau, und der
  zweite Fall bleibt weiterhin stumm — Nachweis über echten Trip-Alarm-Durchlauf, keine Mocks.
  - Test: Vorher/Nachher-Vergleich desselben Szenarios (Fixture-Trip + fixierte
    Wetter-Zeitreihe) gegen einen echten lokalen Kanal-Sink (Telegram-HTTP-Socket bzw.
    IMAP-Postfach), kein `unittest.mock`.

- **AC-2:** Given ein Trip mit konfiguriertem Cooldown (`alert_cooldown_minutes`) und
  Ruhezeiten (`alert_quiet_from`/`alert_quiet_to`) inklusive eines Mitternachts-Wraps
  (z. B. 22:00–06:00) / When zwei aufeinanderfolgende signifikante Wetteränderungen
  innerhalb des Cooldown-Fensters bzw. während der Ruhezeit eintreten / Then unterdrückt
  die extrahierte Engine den zweiten Alarm exakt wie vor dem Umbau, und ein
  State-Dedup-Eintrag verhindert einen erneuten Versand derselben Abweichung beim
  nächsten Lauf.
  - Test: Echter zweiter Auswertungslauf mit fortgeschrittener Systemzeit
    (Cooldown-Fenster) bzw. Uhrzeit innerhalb des Wrap-Bereichs, echter Alert-State auf
    Disk, kein Mock der Zeit-/State-Logik.

- **AC-3:** Given ein generischer Satz Punkt-Wetterdaten (Name/Koordinate + Zeitreihe, ohne
  Trip-, Stage- oder Waypoint-Bezug), eine `AlertEvaluationConfig` (Regeln, Cooldown,
  Ruhezeiten, Kanäle) und ein leerer Melde-Snapshot / When diese Eingaben direkt an
  `DeviationAlertEngine.evaluate()` übergeben werden, ohne dass ein `Trip`-Objekt existiert
  / Then liefert die Engine dieselbe korrekte Alarm-Entscheidung (ausgelöst/nicht ausgelöst,
  Severity, betroffene Kanäle), die ein gleichwertiger Trip-Aufruf mit denselben
  zugrundeliegenden Werten liefern würde.
  - Test: Direkter Aufruf der Engine mit handgebauten `PointWeatherData`/`AlertEvaluationConfig`
    (kein Trip-Fixture), Assertion auf Rückgabewert; kein Mock innerhalb der Engine-Logik.

- **AC-4:** Given eine bestehende Datei
  `data/users/<user_id>/alert_state/<trip_id>.json` aus der Zeit vor dem Umbau / When der
  umgebaute Code (`AlertStateService` mit `entity_id`-Parameter) denselben Trip nach der
  Umstellung prüft / Then wird die Datei unverändert eingelesen, ihr Inhalt korrekt als
  bereits gemeldete Abweichungen interpretiert, und es ist keine Migrations-Skript-Ausführung
  nötig.
  - Test: Alte Testdatei (aus Vor-Umbau-Fixture) im echten Verzeichnis ablegen, echten
    Alert-Lauf gegen dieselbe Abweichung ausführen, prüfen dass sie als bereits gemeldet
    erkannt und NICHT erneut versendet wird.

- **AC-5:** Given die Architektur-Entscheidung, Trip- und künftige Compare-Alarme auf einer
  gemeinsamen Auswertungs-Engine zu vereinen statt sie zu duplizieren / When die Umsetzung
  dieser Scheibe abgeschlossen ist / Then dokumentiert eine neue ADR-Datei unter `docs/adr/`
  diese Entscheidung inklusive der verworfenen Alternative (separate Compare-Engine
  duplizieren) und wird vom `adr_guard`-Hook beim Commit als vorhanden akzeptiert.
  - Test: `adr_guard`-Hook lässt den Commit ohne `[no-adr]`-Marker durch, weil eine
    passende ADR-Datei im selben Commit enthalten ist.

## Known Limitations

- Keine Compare-Anbindung — der Orts-Vergleich bleibt in dieser Scheibe unverändert ohne
  Alarm-Auswertung; das ist Scheibe 2 (#1169), inklusive des dort nötigen
  pro-Ort-Snapshot-Ankers.
- Keine Config-UI — keine Frontend-Änderungen; das ist Scheibe 3 (#1170).
- Kein neues Alarm-Verhalten und keine absoluten Schwellwerte — diese Scheibe ändert
  ausschließlich die interne Struktur, nicht was oder wann ein Alarm ausgelöst wird.
- Die neue location-generische Wetter-Beschaffungs-Schnittstelle (`LocationWeatherSource`
  Protocol) wird in dieser Scheibe nur für Trip implementiert
  (`TripSegmentWeatherAdapter`); eine Compare-seitige Implementierung auf Basis von
  `ForecastService`/`Location` ist NICHT Teil dieser Scheibe.
- Tageslimit (`alert_daily_limit`), Alert-Log-Kachel und Radar-Onset-Sofort-Trigger bleiben
  vorerst Trip-spezifisch im Adapter — eine Verallgemeinerung dieser Bausteine ist nicht
  Bestandteil dieser Scheibe und müsste bei Bedarf separat betrachtet werden.

## Risiken

1. **Regressionsrisiko am Live-Alarm-Pfad:** Der 15-Minuten-Scheduler-Job
   (`/api/scheduler/alert-checks` → `check_all_trips()`) ist produktiv aktiv. Bit-identisches
   Trip-Verhalten ist deshalb Hard-Gate (AC-1/AC-2), nicht optional — Verifikation über
   echten Alarm-Durchlauf, keine Mocks.
2. **LoC-Limit 250 wird voraussichtlich überschritten** (Schätzung ~350–450 LoC). Vor
   Implementierungsbeginn ist eine explizite PO-Freigabe für
   `workflow.py set-field loc_limit_override <N>` einzuholen — kein eigenmächtiger Override.
3. **Keine Mocks erlaubt** (CLAUDE.md) — Alert-Tests müssen gegen echte
   Wetter-/Versand-/State-Pfade laufen, was den Testaufwand für diese Scheibe erhöht.
4. **ADR-Pflicht** (`adr_guard`-Hook) — ohne ADR im selben Commit blockt der Commit-Gate.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0021 (neu, `docs/adr/0021-shared-deviation-alert-engine.md`)
- **Rationale:** Der Deviation-Alert-Auswertungskern ist bereits location-generisch
  (arbeitet auf Wetterdaten-pro-Punkt + Config, keine Trip-/Stage-/Waypoint-Kopplung).
  Rendering (ADR-0011) und Versand (ADR-0017) sind bereits geteilt. Statt für den
  Orts-Vergleich eine zweite, duplizierte Auswertungs-Engine zu bauen (verworfene
  Alternative), wird der bestehende Kern in einen eigenständigen Shared-Service extrahiert;
  Trip bleibt erster, unverändert funktionierender Consumer, der Orts-Vergleich wird in
  Scheibe 2 (#1169) als zweiter Consumer angeschlossen.

## Test Plan

Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md) — echte Trip-/State-/Kanal-Pfade,
Vorbild: `tests/tdd/test_issue_816_alert_deviation.py` (echter lokaler Telegram-HTTP-Sink,
echter Dateisystem-State unter `data/users/<user_id>/`).

Neue Testdatei: `tests/tdd/test_issue_1168_alert_engine_extract.py`

- `test_ac1_trip_alarm_fires_identically_after_extraction` — echter Trip-Alarm-Durchlauf
  (Fixture-Trip mit Alarmregel + Wetter-Zeitreihe, die die Schwelle reißt) gegen echten
  Telegram-Sink; Assertion auf identische Metrik/Severity/Kanal/Text wie im
  Vor-Umbau-Referenzlauf (fixiertes Erwartungs-Snapshot aus dem bestehenden
  `test_issue_816_alert_deviation.py`-Szenario).
- `test_ac1_trip_alarm_stays_silent_identically_after_extraction` — analoger Durchlauf mit
  einem Szenario, das bewusst keinen Alarm auslöst (z. B. Abweichung unterhalb der
  Delta-Schwelle); Assertion: kein Sink-Aufruf.
- `test_ac2_cooldown_suppresses_second_alert` — zwei echte Auswertungsläufe mit
  fortgeschrittener Systemzeit innerhalb des Cooldown-Fensters; zweiter Lauf löst keinen
  Versand aus.
- `test_ac2_quiet_hours_midnight_wrap_suppresses_alert` — echter Lauf mit Uhrzeit im
  Mitternachts-Wrap-Bereich (z. B. 23:30 bei Ruhezeit 22:00–06:00); kein Versand.
- `test_ac3_engine_evaluates_generic_point_data_without_trip` — direkter Aufruf von
  `DeviationAlertEngine.evaluate()` mit handgebauten `PointWeatherData`/
  `AlertEvaluationConfig`-Objekten ohne jegliches `Trip`-Fixture; Assertion auf korrekte
  Entscheidung.
- `test_ac4_legacy_alert_state_file_still_readable` — vorab abgelegte Alt-State-Datei im
  `<trip_id>.json`-Format, echter Alarm-Lauf gegen dieselbe Abweichung, Assertion: als
  bereits gemeldet erkannt, kein erneuter Versand.
- `test_ac5_adr_file_present_and_accepted_by_guard` — doc-compliance-test (Ausnahme laut
  CLAUDE.md): prüft, dass `docs/adr/0021-shared-deviation-alert-engine.md` existiert und
  vom `adr_guard`-Schema akzeptiert wird.

## Changelog

- 2026-07-09: Initial spec erstellt — Issue #1168, Scheibe 1 von Epic #1095
