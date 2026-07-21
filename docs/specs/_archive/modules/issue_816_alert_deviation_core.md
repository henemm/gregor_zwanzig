---
entity_id: issue_816_alert_deviation_core
type: module
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [alert, deviation, briefing-snapshot, alert-state, change-detection, epic-813, slice-1]
---

# Alert-Rework Slice 1: Forecast-Abweichungs-Kern

## Approval

- [x] Approved

## Purpose

Ersetzt das absolute-Schwellwert-Modell im Forecast-Alert-Pfad (`check_and_send_alerts`)
durch einen Abweichungs-Melder: Der Alert meldet **Δ gegenüber dem letzten versandten
Briefing** (Snapshot-Referenz stabil, read-only). Ein Melde-Gedächtnis (`alert_state`)
verhindert Wiederholungs-Spam; Eskalation löst erneut aus. Die Benachrichtigung ist
mobil-first, knapp und zeigt Vorher→Jetzt mit Segment-Zeit und km.

## Source

- **File:** `src/services/trip_alert.py` — Kern (Snapshot-Overwrite raus, alert_state-Integration, knapper Render-Pfad)
- **File:** `src/services/alert_state.py` — NEU (Persistenz-Service `alert_state`)
- **File:** `src/services/weather_change_detection.py` — absolute Regeln im Alert-Pfad ausklammern
- **File:** `src/services/trip_report_scheduler.py` — alert_state-Reset beim Briefing-Versand
- **File:** `src/output/renderers/email/helpers.py` — `build_segment_label` um km erweitern
- **File:** `src/output/renderers/email/__init__.py` / knapper Alert-Renderer (ggf. neues Modul)

> **Schicht: Python-Backend.** Alle betroffenen Dateien liegen in `src/`.
> Go-API (`api/`, `internal/`) und Frontend (`frontend/`) bleiben unberührt.

## Estimated Scope

- **LoC:** ~280–350 (netto; generierte/Lock-Dateien zählen nicht)
- **Files:** 6 (5 bestehend + 1 neu)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_snapshot.py` — `WeatherSnapshotService.load` | upstream | Liest Briefing-Snapshot als Referenz (read-only) |
| `src/services/weather_change_detection.py` — `WeatherChangeDetectionService` | upstream | Δ-Erkennung (symmetrisch, ohne `_detect_absolute_changes`) |
| `src/app/metric_catalog.py` — `get_change_detection_map()` | upstream | Δ-Schwellen-Defaults für Slice 1 (Temp 5.0, Wind/Böen 20.0, Regen 10.0, Schneefallgrenze 20.0, Gewitter 1.0) |
| `src/output/renderers/email/helpers.py` — `format_change_line`, `build_segment_label` | upstream | SSoT für Vorher→Jetzt-Zeile; `build_segment_label` wird um km erweitert |
| `src/outputs/email.py` — `EmailOutput` | upstream | Knappen Alert-Versand |
| `src/outputs/telegram.py` — `TelegramOutput` | upstream | Knappen Alert-Versand (Telegram-Kanal) |
| `src/app/models.py` — `WeatherChange`, `TripSegment` | upstream | Change-DTO; `start_point.distance_from_start_km` für km-Angabe (#801) |
| `src/services/trip_report_scheduler.py` — Briefing-Versand Z. 628–633 | downstream | Reset-Hook für `alert_state` beim Briefing |
| `src/services/trip_alert.py` — `check_all_trips`, Scheduler-Cron 30 Min | downstream | Aufruf-Kontext |

## Implementation Details

### A — Briefing-Snapshot: read-only Referenz

**Entfernen:** Snapshot-Overwrite-Block in `trip_alert.py` Z. 160–168 (Kommentar
„Update snapshot so next alert compares against THIS weather" und der zugehörige
`WeatherSnapshotService.save`-Aufruf im `check_and_send_alerts`-Erfolgs-Zweig).

**Ergebnis:** `WeatherSnapshotService.save` wird nur noch vom Briefing-Scheduler
aufgerufen (Z. 628–633 in `trip_report_scheduler.py`). Die Referenz bleibt stabil
bis das nächste Briefing (Morgen ODER Abend) rausgeht.

### B — Melde-Gedächtnis `alert_state`

**Neuer Service:** `src/services/alert_state.py` — `AlertStateService`

```
Persistenzpfad (mandantengetrennt):
  data/users/<user_id>/alert_state/<trip_id>.json

Schema (pro Datei):
{
  "<metric>:<segment_id>": {
    "last_reported_value": <float>,
    "reported_at": "<ISO-8601>"
  },
  ...
}
```

**Re-Alert-Logik** (vor `_send_alert`):
1. Für jede erkannte Δ-Abweichung (`WeatherChange`) nachschlagen ob Schlüssel
   `<metric>:<segment_id>` im `alert_state` vorhanden.
2. **Neu (kein Eintrag):** Alert durchlassen, Eintrag anlegen mit `last_reported_value`
   = `new_value` des aktuellen Laufs.
3. **Bekannt, keine Eskalation:**
   `|current_new_value − last_reported_value| < threshold` → unterdrücken (kein Alert,
   kein Update des Eintrags).
4. **Eskalation:** `|current_new_value − last_reported_value| >= threshold` → Alert
   durchlassen, Eintrag auf `last_reported_value = current_new_value` aktualisieren.

**Reset:** Beim Briefing-Versand `alert_state` für den betreffenden Trip löschen
(komplette Datei entfernen oder leeres dict schreiben). Andockt in
`trip_report_scheduler.py` direkt nach dem `WeatherSnapshotService.save`-Block
(Z. 628–633).

**Mandantentrennung:** `AlertStateService(user_id=…)` — Pfad immer unter
`data/users/{user_id}/alert_state/`. Pflicht-Test mit zwei verschiedenen `user_id`s.

### C — Symmetrische Δ-Erkennung (ohne absolute Regeln im Alert-Pfad)

In `WeatherChangeDetectionService.detect_changes` (Z. 302–303) wird
`_detect_absolute_changes` aufgerufen. Für den Alert-Pfad muss dieser Aufruf
ausgeschlossen sein.

**Umsetzung:** Flag-Parameter `include_absolute: bool = True` an `detect_changes` oder
separate `detect_delta_only`-Methode. Im Alert-Pfad (`_detect_all_changes` in
`trip_alert.py`) nur Δ-Erkennung aufrufen (`include_absolute=False` oder Pendant).

Δ-Schwellen-Quelle Slice 1 = `MetricCatalog.get_change_detection_map()` (Defaults).
Die `_select_change_detector`-Logik (alert_rules → display_config → report_config →
Defaults) bleibt erhalten, aber der selektierte Detektor ruft `detect_changes` ohne
absolute Regeln auf.

Richtung: `abs(delta) >= threshold` — beide Richtungen (Verschlechterung UND Verbesserung).

### D — Knapper Alert-Render-Pfad

**Anforderung:** Alert-Mail ≠ volle Briefing-Mail. Die Mail enthält **ausschließlich**
die Kopfzeile, die Vorher→Jetzt-Zeilen und eine Orientierungs-Fußzeile — sonst NICHTS.

**Vollständige RAUS-Liste (alle Briefing-Bestandteile entfallen, PO-bestätigt 2026-06-14):**
Stundentabellen · Etappen-Ausblick/„Nächste Etappen" (`multi_day_trend`) · Gewitter-Vorschau
(+1/+2) · „Nacht am Ziel" · Metrik-Pills/Tages-Übersicht · Stabilitäts-/Confidence-Hinweis ·
Vortags-Vergleich (`day_comparison`) · Etappen-Statistik (`stage_stats`).

**DRIN — exakt drei Bestandteile:**
1. **Kopfzeile** (neutral): `Wetter ändert sich seit dem Briefing`.
2. **Pro betroffener Metrik eine Zeile**, sortiert nach **Stärke der Abweichung**
   (größtes `|delta|/threshold` zuerst): `Metrik  Vorher → Jetzt Einheit  (Etappe N, km X–Y, HH–HH Uhr)`.
3. **Fußzeile** (Orientierung): `Stand: <heute HH:MM> · verglichen mit dem letzten Briefing`.

**Aufbau Alert-Nachricht (E-Mail + Telegram):**

```
Betreff: [<Reisename>] Wetter ändert sich seit dem Briefing

Wetter ändert sich seit dem Briefing

Regen      2 → 18 mm     (Etappe 3, km 12–18, 14–16 Uhr)
Böen      25 → 48 km/h   (Etappe 3, km 12–18, 14–16 Uhr)
Temp      22 → 16 °C     (Etappe 3, km 18–24, 16–18 Uhr)

Stand: heute 13:30 · verglichen mit dem letzten Briefing
```

**Betreff neutral** (symmetrisch — kann Verschlechterung ODER Entwarnung sein):
`[<Reisename>] Wetter ändert sich seit dem Briefing`. Kein „⚠️ Warnung".

**km-Erweiterung `build_segment_label`** in `helpers.py`:
- Aktuell: `"Segment N (HH:MM–HH:MM)"` — keine km.
- Neu: `"Etappe N, km X–Y, HH:MM–HH:MM"` wenn `start_point.distance_from_start_km`
  und `end_point.distance_from_start_km` vorhanden (aus Segment-Daten, #801).
- Fallback wenn km = None/0.0: bisheriges Format ohne km-Angabe.
- Bestehende Briefing-Nutzung von `build_segment_label` (plain.py Z. 190–195) erbt
  die km-Angabe automatisch — kein Bruch.

**Render-Pfad:** Neuer knapper Renderer oder neuer `report_type="deviation_alert"` im
bestehenden `render_email`/`render_plain`. Entscheidung in Implementierung: am
sparsamsten ist ein separates Hilfsmodul `src/output/renderers/email/alert_compact.py`
mit `render_deviation_alert(changes, segments, trip_name, tz) -> (html, plain)`.

**Mail-Header:** `X-GZ-Mail-Type: deviation-alert` (abgrenzt von `trip-briefing` und
`compare` — wichtig für `briefing_mail_validator.py`, der bei fremden Typen sauber
No-Op macht).

**Telegram:** Plain-Text analog (kein HTML), gleiche Zeilen-Struktur.

## Expected Behavior

- **Input:** `check_and_send_alerts(trip, cached_weather)` — `cached_weather` ist der
  Briefing-Snapshot (geladen via `WeatherSnapshotService.load`), `fresh_weather` wird
  frisch vom Provider geholt.
- **Output:**
  - Knappe Alert-Mail + Telegram an konfigurierte Kanäle wenn Δ ≥ Threshold UND
    (`alert_state` hat keinen Eintrag ODER Eskalation erkannt).
  - Kein Alert wenn: throttled, QuietHours, kein Kanal, keine Δ, `alert_state` sagt
    "schon gemeldet, keine Eskalation".
- **Side effects:**
  - `data/users/<user_id>/alert_state/<trip_id>.json` — gelesen + ggf. aktualisiert.
  - `data/users/<user_id>/alert_throttle.json` — unverändert (bleibt bestehen).
  - `data/users/<user_id>/alert_log.json` — Eintrag bei Versand (unverändert).
  - **KEIN** Snapshot-Write mehr (Baustein A).
  - `alert_state` wird beim Briefing-Versand resettet (kein direkter Side-Effect in
    `check_and_send_alerts`, sondern im Scheduler).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gespeichertem Briefing-Snapshot und einem laufenden
  `check_and_send_alerts`-Zyklus / When der Alert erfolgreich verschickt wird / Then
  bleibt der Snapshot unverändert (kein `WeatherSnapshotService.save` im Alert-Pfad).
  - Test: Zwei aufeinanderfolgende Alert-Läufe mit kontrolliertem Snapshot — nach beiden
    Läufen hat `WeatherSnapshotService.load(trip_id)` denselben Inhalt wie vor dem
    ersten Lauf; Snapshot-mtime bleibt unverändert. Kein Mock — echter Dateisystem-State.

- **AC-2:** Given ein Trip dessen Δ für eine Metrik/Segment-Kombination bereits in
  `alert_state` eingetragen ist und keine weitere volle Δ-Stufe erreicht wurde / When
  `check_and_send_alerts` erneut läuft / Then wird kein Alert verschickt (Wiederholungs-Spam unterdrückt).
  - Test: Alert-Lauf mit Δ = Threshold → Alert sent, `alert_state` angelegt. Sofortiger
    zweiter Lauf mit gleichem frischen Wert → kein Alert, kein E-Mail/Telegram-Versand
    nachweisbar. Echter Versand via IMAP prüfen oder Channel-Stub mit Assertion.

- **AC-3:** Given ein Trip mit vorhandenem `alert_state`-Eintrag für Metrik/Segment /
  When der frische Wert um mindestens eine weitere volle Δ-Stufe (= Threshold) vom
  zuletzt gemeldeten Wert abweicht / Then wird erneut ein Alert verschickt und
  `alert_state` auf den neuen `last_reported_value` aktualisiert.
  - Test: `alert_state` mit `last_reported_value = 10` für Regen, Threshold = 10.
    Frischer Wert = 20 → Δ = 10 ≥ Threshold → Alert sent, `alert_state.last_reported_value`
    = 20. Echter Datei-Zustand nach Lauf prüfen (kein Dateiinhalt-Check: Load + Wert vergleichen).

- **AC-4:** Given zwei Nutzer (user_a, user_b) mit je einem Trip und eigenen
  Alert-States / When für user_a ein Alert ausgelöst und `alert_state` geschrieben wird /
  Then ist `data/users/user_b/alert_state/` unberührt und user_b-Trips erhalten
  keinen Alert.
  - Test: Zwei `TripAlertService(user_id="user_a"/"user_b")`-Instanzen, unabhängige
    Trips — nach Lauf unter user_a existiert `alert_state` nur unter user_a.
    Mandantentrennung bewiesen mit echtem Dateisystem.

- **AC-5:** Given ein Briefing wurde erfolgreich versandt (`_send_briefing_report`
  in `trip_report_scheduler.py`) / When der `WeatherSnapshotService.save`-Block (Z. 628–633)
  ausgeführt wird / Then wird `alert_state` für den betreffenden Trip zurückgesetzt
  (Datei entfernt oder leeres dict).
  - Test: `alert_state`-Datei mit Eintrag anlegen, danach `_send_briefing_report` auf
    Test-Trip mit kontrolliertem SMTP-Stub ausführen — nach Rückkehr ist
    `AlertStateService.load(trip_id)` leer oder Datei nicht vorhanden.

- **AC-6:** Given ein Trip mit mehreren Wetter-Δ ≥ Threshold (Segmente mit bekannter
  km-Angabe aus `distance_from_start_km`) / When eine Alert-Mail verschickt wird / Then
  enthält die Plain-Text-Mail GENAU: die Kopfzeile „Wetter ändert sich seit dem Briefing",
  pro Metrik eine Vorher→Jetzt-Zeile mit „(Etappe N, km X–Y, HH–HH Uhr)" — sortiert nach
  Stärke der Abweichung (größtes `|delta|/threshold` zuerst) — und eine Fußzeile „Stand: …
  · verglichen mit dem letzten Briefing"; und sie enthält KEINE Stundentabelle, KEINEN
  Ausblick, KEINE Gewitter-Vorschau, KEINE Nacht-Sektion, KEINEN Vortags-Vergleich,
  KEINE Etappen-Statistik.
  - Test: Echter `build_mime_message`-Aufruf (report_type=deviation_alert) mit zwei
    Changes unterschiedlicher Stärke und gesetztem `distance_from_start_km` — MIME
    serialisieren, Plain-Part prüfen: km-String vorhanden, die stärkere Abweichung steht
    vor der schwächeren, Fußzeile vorhanden, KEIN `HH:00`-Stundentabellen-Muster und keiner
    der ausgeschlossenen Briefing-Blöcke. Kein Mock.
  - Test (km-Fallback): Change mit `distance_from_start_km == 0.0` → Zeile fällt auf
    „(Etappe N, HH–HH Uhr)" ohne km zurück, Etappe + Zeit bleiben.

- **AC-7:** Given ein Alert wird per Forecast-Pfad verschickt / When die Mail beim
  Empfänger ankommt / Then trägt sie den Header `X-GZ-Mail-Type: deviation-alert`
  und `briefing_mail_validator.py` beendet sich mit Exit 0 (No-Op für falschen Typ).
  - Test: `build_mime_message` mit `report_type="deviation_alert"` erzeugt Header;
    `briefing_mail_validator.validate_message` auf dieser Mail → Exit 0 (No-Op-Dispatch).

- **AC-8:** Given absolute Regeln (`_absolute_rules`) im `WeatherChangeDetectionService`
  sind konfiguriert / When `check_and_send_alerts` Δ-Erkennung im Alert-Pfad aufruft /
  Then werden keine `_detect_absolute_changes`-Ergebnisse in die Change-Liste aufgenommen
  (nur symmetrische Δ-Vergleiche).
  - Test: `WeatherChangeDetectionService` mit einer `_absolute_rules`-Instanz und einem
    frischen Wert der die absolute Regel verletzt — direkter Aufruf der Alert-Pfad-Methode
    (`detect_changes(include_absolute=False)` o.Ä.) → Ergebnis enthält keine Changes
    mit `direction=None` (absolute-Rule-Marker). Kein Mock, echter Service-Aufruf.

## Known Limitations

- Slice 1 nutzt ausschließlich `MetricCatalog`-Δ-Defaults als Schwellen. Per-Metrik-
  justierbare Tab-Δ-Schwellen (Slice 2 / Tab-UI) sind NICHT Teil dieser Spec.
- Radar/Nowcast-Pfad (`check_radar_alerts`) bleibt vollständig unberührt (Slice 3).
- `alert_state`-Reset setzt den kompletten Trip-State zurück; keine Granularität auf
  Metrik-Ebene beim Reset — vereinfacht die Implementierung auf Kosten von marginalen
  False-Positives im ersten Lauf nach einem Briefing.
- Mail-E2E-Gate: `briefing_mail_validator.py` ist für `deviation-alert` nicht zuständig
  (No-Op). Ein dedizierter `deviation_alert_validator.py` ist Slice 4 / Folge-Issue.
- SMS-Kanal nicht im Scope (nur E-Mail und Telegram).

## Changelog

- 2026-06-14: v1.0 Initial spec created (Issue #816, Epic #813 Slice 1)
