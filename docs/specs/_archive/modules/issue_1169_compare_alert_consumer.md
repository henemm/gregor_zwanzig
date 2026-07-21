---
entity_id: compare_alert_consumer
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [alerts, compare, epic-1095]
---

<!-- Issue #1169 — Scheibe 2 von 3, Epic #1095: Orts-Vergleich als zweiter Consumer der DeviationAlertEngine -->

# Issue 1169 — Ortsvergleich als zweiter Consumer der Deviation-Alert-Engine (Scheibe 2/3, Epic #1095)

## Approval

- [x] Approved (PO, 2026-07-09 — ACs auf Deutsch freigegeben)

## Purpose

Den Orts-Vergleich (`ComparePreset`) an die in Scheibe 1 (#1168, live) herausgelöste
location-generische `DeviationAlertEngine` anschließen — als **zweiten Consumer**, ohne
die Alarm-Auswertungslogik zu duplizieren (ADR-0021). Ein neuer 15-Minuten-Scheduler-Job
wertet pro Vergleichs-Ort frisches Wetter gegen einen persistierten pro-Ort-Snapshot-Anker
aus (ADR-0009: Abweichung vom zuletzt **gemeldeten** Stand, nicht absolute Schwelle) und
versendet Deviation-Alert-Mails an die Preset-Empfänger. Die Alarmkonfiguration ist in
dieser Scheibe fest hartkodiert (Default-Sensitivität "standard", 120 Min Cooldown, nur
E-Mail); eine editierbare UI folgt in Scheibe 3 (#1170).

## Source

- **File:** `src/services/compare_location_weather_source.py` (NEU, ~60–90 LoC) —
  `LocationWeatherSource`-Implementierung (Protocol aus `src/services/point_weather.py:67-76`)
  für Compare-Orte: baut je Ort ein synthetisches Ein-Punkt-`TripSegment`
  (`src/app/models.py:322-335`, `start_point == end_point`, minimales Zeitfenster) und
  nutzt `SegmentWeatherService.fetch_segment_weather()`
  (`src/services/segment_weather.py:71-101`) + `TripSegmentWeatherAdapter.to_points()`
  (`src/services/point_weather.py:83-98`), damit cached (Anker) und fresh **identisch
  geformt** sind (`PointWeatherData`). `enrich_ensemble=False` beim Fresh-Fetch (Quota,
  Bug #288-Analogon). Provider-Wahl über
  `comparison_engine._select_provider_for_location()` (`src/services/comparison_engine.py:285`).
- **File:** `src/services/compare_weather_snapshot.py` (NEU, ~50–80 LoC) — Δ-Anker-Store
  analog `WeatherSnapshotService`: serialisiert `PointWeatherData`, keyed
  `"{preset_id}__{location_id}"`, unter `data/users/<user_id>/compare_weather_snapshots/`.
  Wird von `send_one_compare_preset()` nach erfolgreichem Report-Versand geschrieben (über
  denselben `LocationWeatherSource`-Impl); der Alert-Check **liest nur**. Bootstrap: kein
  Snapshot vorhanden → leere `cached=[]`-Liste, kein Sonderfall-Code nötig, da
  `DeviationAlertEngine.evaluate()` bei leerem `cached` `no_significant_changes` liefert
  (`src/services/deviation_alert_engine.py:230-233`).
- **File:** `src/services/compare_alert.py` (NEU, ~120–160 LoC) — `CompareAlertService`
  analog `TripAlertService` (`src/services/trip_alert.py:39-85,261-345`): pro Nutzer
  instanziiert (`user_id`-Parameter, keine "default"-Fallbacks), lädt
  `compare_presets.json`, baut je Preset/Ort `AlertEvaluationConfig` aus **hartkodierten
  Defaults** (siehe Implementation Details B2), ruft
  `DeviationAlertEngine.evaluate(cached, fresh, config, alert_state)`, prüft Cooldown
  (neuer Store, keyed `preset_id`, RMW analog `alert_throttle.json`), versendet über
  `NotificationService.send_location_deviation_alert()` und schreibt danach
  `AlertStateService`-Dedup (`entity_id = f"{preset_id}:{location_id}"`,
  `src/services/alert_state.py:34-71`). Öffentliche Einstiegsmethode
  `check_all_compare_presets() -> int` (Muster `TripAlertService.check_all_trips()`).
- **File:** `src/services/notification_service.py` (MODIFY, ~30–40 LoC) — neue trip-freie
  Methode `send_location_deviation_alert(entity_name, points, changes, effective_channels,
  mail_sink=None) -> NotificationResult`, wiederverwendet `_dispatch_alert_message()`
  (`:428-…`, `mail_type="deviation-alert"`) unverändert — analog zu `send_deviation_alert()`
  (`:311-344`), aber ohne `Trip`-Abhängigkeit.
- **File:** `src/output/renderers/alert/project.py` (MODIFY, ~30–40 LoC) — neue
  `to_point_alert_message(changes, points, entity_name, *, tz, stand_at) -> AlertMessage`
  neben dem bestehenden `to_alert_message()` (`:49-65`): baut `AlertEvent` ohne
  `_segment_km()`-Lookup (Punkt hat keine km-Spanne, `km_from=km_to=0.0` als neutraler
  Platzhalter) und setzt zusätzlich `location_label` (Ortsname).
- **File:** `src/output/renderers/alert/model.py` + `src/output/renderers/alert/render.py`
  (MODIFY, ~20–30 LoC) — additives, optionales Feld `location_label: str | None = None`
  auf `AlertMessage` (`model.py:37-44`). In `render.py` wird an den Stellen, die heute
  `_km_str(msg)`/`_km_str_events(...)` für die Anzeige nutzen (`:97-99,188,258-261,331,367,
  405-406`), bei gesetztem `location_label` der Ortsname statt der km-Spanne angezeigt.
  Trip-Pfad setzt `location_label` nie → Ausgabe dort bit-identisch (Snapshot-Test-Pflicht).
- **File:** `src/services/scheduler_dispatch_service.py` (MODIFY, ~20–30 LoC) — in
  `send_one_compare_preset()` (`:198-300`) nach dem `EmailOutput(...).send(...)`-Aufruf
  (`:290-296`) je Ort im Preset einen Snapshot-Write über
  `compare_weather_snapshot.py` + denselben `compare_location_weather_source.py`-Impl.
- **File:** `api/routers/scheduler.py` (MODIFY, ~10 LoC) — neuer Endpoint
  `POST /api/scheduler/compare-alert-checks` (Muster `trigger_alert_checks`, `:50-57`):
  `CompareAlertService(user_id=user_id).check_all_compare_presets()`.
- **File:** `internal/scheduler/scheduler.go` (MODIFY, ~15 LoC) — neuer `jobDef`-Eintrag
  `*/15 * * * *` → `compare_alert_checks` (Muster `alertChecks`, `:93,153-157`) +
  Job-Count-Log `"6 jobs"` → `"7 jobs"` (`:112`).
- **File:** `tests/tdd/test_issue_1169_compare_alert_consumer.py` (NEU) — Verhaltens-Tests,
  siehe Test Plan.

> **Schicht-Hinweis:** 8 von 9 Dateien sind Python-Core (`src/services/`,
> `src/output/renderers/`, `api/routers/`); nur der Cron-Job-Eintrag ist Go
> (`internal/scheduler/`). Kein Frontend-Code in dieser Scheibe.

## Estimated Scope

- **LoC:** ~330–400 Produktivcode + ~150–250 Tests (LoC-Override 700 — **PO-freigegeben**,
  vor Implementierungsbeginn per `workflow.py set-field loc_limit_override 700` zu setzen)
- **Files:** 9 (4 CREATE Python, 4 MODIFY Python, 1 MODIFY Go) + 1 neue Testdatei
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.deviation_alert_engine.DeviationAlertEngine` | intern (Scheibe 1, #1168) | Geteilter, trip-freier Auswertungskern — Kernabhängigkeit dieser Scheibe |
| `services.point_weather.PointWeatherData` / `AlertEvaluationConfig` / `LocationWeatherSource` | intern (Scheibe 1) | Generische DTOs + Beschaffungs-Protocol, die Compare implementiert |
| `services.alert_state.AlertStateService` | intern | Dedup-Store, `entity_id = f"{preset_id}:{location_id}"` — bereits generisch |
| `services.segment_weather.SegmentWeatherService` | intern | Wetter-Beschaffung, unverändert wiederverwendet über synthetisches Ein-Punkt-Segment |
| `services.comparison_engine._select_provider_for_location` | intern | Provider-Wahl (GeoSphere/OpenMeteo je Region), wiederverwendet statt dupliziert |
| `services.notification_service.NotificationService._dispatch_alert_message` | intern | Geteilter Versand-Kern (ADR-0017/ADR-0021), unverändert |
| `output.renderers.alert.project.to_alert_message` | intern | Vorbild für die neue `to_point_alert_message()` |
| `services.scheduler_dispatch_service.send_one_compare_preset` | intern | Bestehender Compare-Report-Versandpfad — hier dockt der Snapshot-Write an |
| `app.loader.list_all_user_ids` / `load_all_locations` | intern | Nutzer-Enumeration + Ortsauflösung, mandantengetrennt |
| `api.routers.scheduler` | intern | Neuer HTTP-Endpoint, Muster `trigger_alert_checks` |
| `internal/scheduler/scheduler.go` | intern (Go) | Neuer Cron-Job, Muster `alertChecks` |
| ADR-0009 (Abweichungs-Wächter) | Architektur | Alarm-Semantik: Abweichung vom letzten gemeldeten Report, keine Absolutwerte |
| ADR-0021 (Shared Deviation Engine) | Architektur | Konsolidierungs-Entscheidung, deren zweiter Consumer diese Scheibe umsetzt |
| Scheibe 3 (#1170) | Folge-Issue | Editierbare Alarmkonfiguration im Frontend — NICHT Teil dieser Scheibe |

## Implementation Details

### Architekturschnitt

```
send_one_compare_preset()                    CompareAlertService.check_all_compare_presets()
  ├─ Report-Versand (EmailOutput, unverändert)  ├─ für jeden User (list_all_user_ids)
  └─ NEU: Snapshot-Write je Ort                    └─ für jedes Preset × jeden Ort:
       via compare_location_weather_source.py           ├─ cached = compare_weather_snapshot.load(...)
       → compare_weather_snapshot.save(...)              ├─ fresh  = compare_location_weather_source.fetch(...)
                                                           ├─ config = AlertEvaluationConfig(DEFAULTS)
                                                           ├─ Cooldown-Check (neuer Store, keyed preset_id)
                                                           ├─ DeviationAlertEngine.evaluate(cached, fresh, config, alert_state)
                                                           ├─ bei triggered=True:
                                                           │    NotificationService.send_location_deviation_alert(...)
                                                           │    → to_point_alert_message() → _dispatch_alert_message()
                                                           └─ alert_state.save(...) (RMW, wie Trip-Pfad)
```

### A1 — Wetter-Beschaffung (Form-Identität cached/fresh)

Compare fetcht heute Wetter via `ComparisonEngine`/`ForecastService` (Dict-/`raw_data`-Form),
die Engine braucht aber `PointWeatherData` mit `aggregated: SegmentWeatherSummary` +
`timeseries: NormalizedTimeseries` — diese Typen entstehen nur im Segment-Pfad. Statt eine
zweite Aggregations-Pipeline zu bauen, baut `compare_location_weather_source.py` je Ort ein
synthetisches `TripSegment` (`start_point == end_point == Ort`) und ruft
`SegmentWeatherService.fetch_segment_weather(segment, enrich_ensemble=False)` +
`TripSegmentWeatherAdapter.to_points([...])`. Dadurch sind der beim Report-Versand
geschriebene Anker-Snapshot und das beim 15-Min-Check gefetchte fresh-Wetter **durch
denselben Code-Pfad** erzeugt — ein Form- oder Provider-Mismatch ist strukturell
ausgeschlossen (kein Sonderfall-Handling nötig).

### B1 — Snapshot-Trigger (ADR-0009-konform)

Der Δ-Anker wird **beim Report-Versand** geschrieben (`send_one_compare_preset()`, nach dem
Mail-Versand), der 15-Minuten-Alert-Check **liest nur**. Damit akkumuliert die gemeldete
Abweichung korrekt seit dem letzten tatsächlich versendeten Compare-Report — exakt das
ADR-0009-Modell ("Abweichung vom zuletzt gemeldeten Stand"), nur auf Compare übertragen.
Der 15-Min-Check selbst verursacht **keinen** Doppel-Fetch/Doppel-Snapshot-Write. Fehlt der
Snapshot (Bootstrap, erster Lauf nach Preset-Anlage), liefert die Engine
`no_significant_changes` — kein Crash, kein Alarm.

### B2 — Default-Alarmkonfiguration (hartkodiert, Scheibe 3 ergänzt Felder additiv)

`AlertEvaluationConfig` wird pro Preset/Ort mit folgenden Defaults gebaut, OHNE ein neues
`ComparePreset`-Schema-Feld einzuführen:

- `metric_alert_levels`: alle 12 Tabellenmetriken auf `"standard"` — äquivalent zu
  `expand_preset("standard")`/`expand_per_metric_levels(..., display_config=None)`
  (dieselbe Default-Sensitivität wie neue Trips ohne individuelle Anpassung)
- `cooldown_minutes`: 120
- `quiet_from`/`quiet_to`: `None` (keine Ruhezeiten)
- `channels`: `{"email"}` (Compare-Versand ist heute E-Mail-only, kein
  Telegram/SMS-Mapping für Presets)

`CompareAlertService` liest optionale, vorwärtskompatible Override-Felder aus dem Preset-Dict
via `preset.get(feld, DEFAULT)` — Scheibe 3 kann diese Felder ergänzen, ohne die
Auswertungslogik dieser Scheibe zu ändern.

### C — Versand ohne Trip-Bindung

`NotificationService.send_deviation_alert()` verlangt zwingend ein `Trip`-Objekt. Neue
Methode `send_location_deviation_alert(entity_name: str, points: List[PointWeatherData],
changes: List[WeatherChange], effective_channels: set[str], mail_sink=None) ->
NotificationResult` baut analog eine `AlertMessage` über `to_point_alert_message()` und
delegiert an den unveränderten `_dispatch_alert_message()`-Kern (ADR-0021: Rendering/Versand
bleiben geteilt, nur Report bleibt getrennt).

### "km 0–0"-Fix (additiver Renderer-Fund, Tech-Lead-Entscheidung: wird mitgefixt)

Der geteilte Alert-Renderer bettet fest eine Strecken-km-Spanne ein
(`render.py:97-99,188,258-261,331,367,405-406`, via `km_span()`). Ein Vergleichs-Ort ist ein
Punkt ohne km-Kontext — `to_point_alert_message()` liefert deshalb `km_from=km_to=0.0` als
neutralen Platzhalter, was ohne Fix als sinnloses "km 0–0" in jeder Compare-Alert-Mail
erschiene. Fix: additives, optionales Feld `AlertMessage.location_label: str | None = None`;
ist es gesetzt, zeigen die betroffenen Renderer-Stellen den Ortsnamen statt der km-Spanne.
Der Trip-Pfad setzt `location_label` nie (`to_alert_message()` bleibt unverändert) — bestehende
Trip-Alert-Ausgabe bleibt daher bit-identisch (Snapshot-Test-Pflicht, AC-7).

### Scheduler-Verdrahtung

Neuer Python-Endpoint `POST /api/scheduler/compare-alert-checks` (Muster
`trigger_alert_checks`, `api/routers/scheduler.py:50-57`) ruft
`CompareAlertService(user_id=user_id).check_all_compare_presets()`. Neuer Go-`jobDef`
`*/15 * * * *` (Muster `alertChecks`, `internal/scheduler/scheduler.go:93,153-157`) fächert
über `runForAllUsers()` (`:124-145`, via `ListUserIDs`) auf jeden Nutzer auf — dieselbe
Per-User-Isolation wie beim bestehenden Trip-Alert-Job. Job-Count-Log `"6 jobs"` → `"7 jobs"`
(`:112`).

### Reihenfolge (atomar testbar, aus Analyse übernommen)

1. `compare_location_weather_source.py` (+ Form-Paritäts-Test) →
2. `compare_weather_snapshot.py` (+ Roundtrip-/Bootstrap-Test) →
3. Renderer/Versand (`to_point_alert_message` + `send_location_deviation_alert` +
   `location_label`, Trip-Snapshot-Test bleibt grün) →
4. `compare_alert.py` (Integration, Zwei-Nutzer/Zwei-Preset-Test) →
5. Snapshot-Write-Hook in `send_one_compare_preset` + Python-Endpoint →
6. Go-Cron-Job + Job-Count-Fix + Staging-E2E.

## Expected Behavior

- **Input:** `compare_presets.json` je Nutzer (bestehende Presets, unverändertes Schema),
  persistierte pro-Ort-Snapshots (`compare_weather_snapshots/`), frisches Wetter über
  `LocationWeatherSource`, HTTP-Trigger `POST /api/scheduler/compare-alert-checks?user_id=...`
  (vom Go-Cron alle 15 Min pro Nutzer aufgerufen).
- **Output:** Bei signifikanter Abweichung vom Anker (und außerhalb Cooldown/Dedup) eine
  Deviation-Alert-E-Mail an die Preset-Empfänger (`preset.empfaenger`, Fallback
  `settings.mail_to`) mit Ortsname statt "km 0–0". Ohne Abweichung/innerhalb Cooldown/ohne
  Snapshot: kein Versand, kein Fehler.
- **Side effects:** neue Dateien unter `data/users/<user_id>/compare_weather_snapshots/`,
  `data/users/<user_id>/alert_state/<preset_id>:<location_id>.json`, neuer
  Cooldown-Store (analog `alert_throttle.json`, keyed `preset_id`) — alle per RMW
  geschrieben, mandantengetrennt. Kein neues Feld in `compare_presets.json` selbst.

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit persistiertem pro-Ort-Anker-Snapshot und frisches
  Wetter, das die Standard-Δ-Schwelle für eine Metrik reißt, sowie ein zweiter Ort/Zustand im
  selben Preset ohne relevante Abweichung / When der neue 15-Minuten-Alert-Check für diesen
  Nutzer läuft (`CompareAlertService.check_all_compare_presets()` bzw. über den HTTP-Endpoint)
  / Then wird für den ersten Ort eine Deviation-Alert-E-Mail an die konfigurierten
  Preset-Empfänger versendet und über IMAP im Stalwart-Test-Postfach nachweisbar zugestellt,
  während der zweite Ort stumm bleibt.
  - Test: echter End-to-End-Lauf mit echtem Fixture-Preset + echtem Anker-Snapshot + echt
    zugestellter Mail (kein Mock), IMAP-Verifikation gegen `gregor-test@henemm.com`.

- **AC-2:** Given ein frisches Wetter mit hohem ABSOLUTWERT einer Metrik (z. B. starker
  Regen), das aber WERTGLEICH zum persistierten Anker ist / When der Alert-Check läuft / Then
  löst dies KEINEN Alarm aus (ADR-0009: kein absoluter Schwellenvergleich); erst eine
  tatsächliche Änderung des Werts GEGENÜBER dem Anker löst einen Alarm aus.
  - Test: zwei Läufe desselben Preset/Orts — erster mit identischem Fresh-Wetter zum Anker
    (kein Versand), zweiter mit verändertem Fresh-Wetter (Versand) — echter Dateisystem-Anker,
    kein Mock der Auswertungslogik.

- **AC-3:** Given zwei verschiedene Nutzer mit je einem eigenen Compare-Preset, eigenen
  Empfängern und eigenen Anker-Snapshots / When der Alert-Check für beide Nutzer läuft / Then
  geht ein ausgelöster Alarm für Nutzer A ausschließlich an A's konfigurierte Empfänger, und
  Snapshot-/Alert-State-/Cooldown-Dateien liegen ausschließlich unter
  `data/users/A/...` bzw. `data/users/B/...` — B's Daten und Postfach bleiben unberührt. Nie
  ein Fallback auf `"default"`.
  - Test: zwei echte Nutzer-Verzeichnisse mit je eigenem Preset, zwei getrennte
    IMAP-Postfächer/Empfänger-Adressen, Assertion auf Dateipfad-Isolation UND
    Zustell-Isolation.

- **AC-4:** Given ein Compare-Preset, dessen Report gerade über
  `send_one_compare_preset()` versendet wurde / When direkt danach — ohne Wetteränderung —
  der Alert-Check für dasselbe Preset läuft / Then existiert je Ort im Preset ein frischer
  pro-Ort-Snapshot in identischer Form/Provider wie das später gefetchte Fresh-Wetter, und der
  Alert-Check schlägt NICHT an (kein künstlicher Alarm durch Form-Mismatch).
  - Test: echter Report-Versand-Aufruf, danach echte Snapshot-Datei-Prüfung
    (`PointWeatherData`-Form) + echter Alert-Check-Lauf mit Assertion "kein Versand".

- **AC-5:** Given ein neu angelegtes Compare-Preset ohne jemals versendeten Report (kein
  Anker-Snapshot vorhanden) / When der Alert-Check zum ersten Mal für dieses Preset läuft /
  Then wird kein Alarm ausgelöst und der Lauf terminiert ohne Fehler/Exception.
  - Test: frisches Preset-Fixture ohne Snapshot-Verzeichnis, echter Alert-Check-Lauf,
    Assertion auf `count == 0`/kein Versand UND kein unbehandelter Fehler im Log.

- **AC-6:** Given ein ausgelöster Deviation-Alarm für ein Preset (Default-Cooldown 120 Min,
  Kanal nur E-Mail) / When derselbe Alert-Check ein zweites Mal innerhalb des
  Cooldown-Fensters bzw. bei unveränderter Abweichung nach einem erneuten Lauf ausgeführt wird
  / Then wird der zweite Versand durch Cooldown UND durch Alert-State-Dedup unabhängig
  voneinander unterdrückt, und es wird zu keinem Zeitpunkt ein Telegram- oder SMS-Kanal
  bedient.
  - Test: zwei echte, zeitlich versetzte Läufe (fortgeschrittene Systemzeit innerhalb des
    Cooldown-Fensters) gegen echten Cooldown-Store + echten `alert_state`; Assertion: genau
    ein Versand über den ersten Lauf, kein zweiter; `effective_channels == {"email"}`.

- **AC-7:** Given eine Compare-Deviation-Alert-Nachricht für einen benannten Vergleichs-Ort
  / When sie über `to_point_alert_message()`/die Alert-Renderer gerendert wird / Then zeigt
  Betreff, E-Mail- und Telegram-Text den Ortsnamen statt "km 0–0"; ein paralleler,
  unveränderter Trip-Alert-Durchlauf über `to_alert_message()` liefert weiterhin exakt dieselbe
  Ausgabe wie vor dieser Scheibe (Regressions-Schutz für den geteilten Renderer).
  - Test: gerenderte Compare-Alert-Ausgabe enthält den Ortsnamen und NICHT den String
    "km 0–0"; zusätzlich ein Vorher/Nachher-Snapshot-Vergleich eines bestehenden
    Trip-Alert-Fixtures (identischer Text vor/nach dieser Scheibe).

- **AC-8:** Given der neue Python-Endpoint und Go-Cron-Job / When
  `POST /api/scheduler/compare-alert-checks?user_id=<uid>` aufgerufen wird bzw. der
  15-Minuten-Cron-Job feuert / Then wertet der Aufruf die Compare-Presets genau dieses
  Nutzers aus (kein anderer Nutzer wird berührt), und der Go-Scheduler meldet beim Start
  7 statt 6 registrierte Jobs.
  - Test: echter HTTP-POST gegen den laufenden Python-Core-Service mit `user_id`-Parameter,
    Assertion auf `{"status": "ok", "count": N}`; separater Log-/Startup-Check des Go-Binaries
    auf "7 jobs".

## Known Limitations

- Keine editierbare Alarmkonfiguration im Frontend — Default-Sensitivität, Cooldown und
  Kanal sind in dieser Scheibe hartkodiert. Das ist Scheibe 3 (#1170).
- Kein neues `ComparePreset`-Schema-Feld — Overrides werden vorwärtskompatibel via
  `preset.get(feld, DEFAULT)` gelesen, aber es existiert noch kein UI-Weg, sie zu setzen.
- Alarmierung nur über den E-Mail-Kanal — Compare-Reports sind heute E-Mail-only, es gibt
  kein Preset-seitiges Telegram-/SMS-Mapping.
- Keine Quiet-Hours für Compare-Alerts in dieser Scheibe (Default `None`/`None`).
- Der Δ-Anker existiert nur für Presets, die mindestens einmal per Report versendet wurden
  (Bootstrap-Fall bleibt bewusst stumm, kein Ersatz-Fetch beim ersten Alert-Check).

## Risiken

1. **LoC-Limit deutlich überschritten** (Schätzung ~330–400 Prod + ~150–250 Tests-LoC) —
   PO-Freigabe für `workflow.py set-field loc_limit_override 700` liegt bereits vor
   Implementierungsbeginn vor.
2. **Regressionsrisiko am geteilten Alert-Renderer:** `render.py`/`model.py` werden auch vom
   produktiven Trip-Alert-Pfad genutzt — additives, optionales `location_label`-Feld hält das
   Risiko strukturell klein, ein Snapshot-Test auf unveränderte Trip-Ausgabe ist trotzdem
   Hard-Gate (AC-7).
3. **Keine Mocks erlaubt** (CLAUDE.md) — E-Mail-Zustellung und Zwei-Nutzer-Isolation müssen
   gegen echte IMAP-/Dateisystem-Zustände getestet werden, was den Testaufwand erhöht.
4. **Mail-Validator-Gate:** Änderungen an `src/output/renderers/alert/*.py` triggern das
   Renderer-Commit-Gate (`renderer_mail_gate.py`) — vor Commit müssen sowohl ein
   Verhaltens-Test grün als auch (bei betroffenen Trip-Briefing-Pfaden)
   `briefing_mail_validator.py` erfolgreich laufen.
5. **Wetter-Form-Mismatch strukturell ausgeschlossen** durch A1 (gemeinsamer
   `LocationWeatherSource`-Impl für Anker-Write und Fresh-Fetch), muss aber dennoch per
   AC-4-Test bewiesen werden, nicht nur durch Code-Review angenommen werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0009 (Referenz, bereits akzeptiert) + ADR-0021 (Referenz, bereits
  akzeptiert) — **keine neue ADR nötig**.
- **Rationale:** Diese Scheibe setzt ausschließlich bereits getroffene Architektur-
  Entscheidungen um: ADR-0009 definiert die Abweichungs-Wächter-Semantik (Anker = letzter
  gemeldeter Stand), die hier 1:1 auf Compare übertragen wird; ADR-0021 hat die
  Konsolidierungs-Entscheidung (ein gemeinsames Alarm-Gehirn für Trip + Compare) bereits
  getroffen und den Orts-Vergleich explizit als künftigen zweiten Consumer benannt. Diese
  Scheibe ist der Vollzug dieser Entscheidung, keine neue.

## Test Plan

Alle Tests folgen der Projektregel „keine Mocks" (CLAUDE.md) — echte Preset-/Snapshot-/
State-/Kanal-Pfade. Vorbild: `tests/tdd/test_issue_1168_alert_engine_extract.py` (echte
Engine-Aufrufe) sowie `tests/tdd/test_issue_816_alert_deviation.py` (echter lokaler
Kanal-Sink / echte IMAP-Zustellung).

Neue Testdatei: `tests/tdd/test_issue_1169_compare_alert_consumer.py`

- `test_ac1_compare_deviation_alert_delivered_end_to_end` — echtes Fixture-Preset mit
  Anker-Snapshot + Fresh-Wetter über der Δ-Schwelle für Ort A, unverändertes Wetter für Ort
  B; echter `CompareAlertService`-Lauf; IMAP-Abruf gegen `gregor-test@henemm.com` bestätigt
  Zustellung für A, kein Treffer für B.
- `test_ac2_identical_absolute_value_does_not_alarm` — Fresh-Wetter mit hohem Absolutwert
  aber unverändert zum Anker → kein Versand; zweiter Lauf mit tatsächlich verändertem Wert
  → Versand.
- `test_ac3_two_users_isolated_recipients_and_files` — zwei echte
  `data/users/<uid>/`-Verzeichnisse mit je eigenem Preset/Empfänger/Anker; Assertion auf
  Datei-Pfad-Isolation und getrennte IMAP-Zustellung; kein `"default"`-Fallback im Code-Pfad.
- `test_ac4_snapshot_written_on_report_send_matches_fresh_form` — echter
  `send_one_compare_preset()`-Aufruf, danach Snapshot-Datei-Assertion (Form/Provider) +
  direkt anschließender Alert-Check ohne Wetteränderung → kein Versand.
- `test_ac5_bootstrap_no_snapshot_no_alarm_no_crash` — frisches Preset ohne
  Snapshot-Verzeichnis, echter Alert-Check-Lauf, `count == 0`, keine Exception im Log.
- `test_ac6_cooldown_and_state_dedup_suppress_repeat_email_only_channel` — zwei zeitlich
  versetzte echte Läufe innerhalb des 120-Min-Cooldown-Fensters; genau ein Versand;
  `effective_channels == {"email"}` durchgängig geprüft.
- `test_ac7_point_alert_shows_location_name_not_km_zero` — gerenderte Compare-Alert-Ausgabe
  (Betreff/E-Mail/Telegram) enthält den Ortsnamen, NICHT "km 0–0"; zusätzlich
  `test_ac7_trip_alert_rendering_unchanged` als Snapshot-Vergleich eines bestehenden
  Trip-Fixtures vor/nach dieser Scheibe.
- `test_ac8_scheduler_endpoint_scoped_to_user_and_job_registered` — echter HTTP-POST gegen
  `POST /api/scheduler/compare-alert-checks?user_id=<uid>` mit Assertion auf
  Nutzer-Scoping; separater Go-Startup-Log-Check auf "7 jobs".

## Changelog

- 2026-07-09: Initial spec erstellt — Issue #1169, Scheibe 2 von Epic #1095
