---
entity_id: issue_822_radar_nowcast_segment
type: module
created: 2026-06-15
updated: 2026-06-15
status: draft
version: "1.0"
tags: [alert, radar, nowcast, segment, trip-alert, tz, mandantentrennung]
---

# Issue #822 — Radar-/Regen-Nowcast-Alert segmentbewusst machen

## Approval

- [x] Approved (PO, 2026-06-15)

## Purpose

Ersetzt den Einzelpunkt-Check (`stage.waypoints[0]`) in `TripAlertService.check_radar_alerts` durch eine segmentbewusste Auswahl: Die Methode leitet nach derselben Logik wie das Briefing das **aktuelle oder nächste Segment** ab und prüft den Nowcast dort. Die Alert-Mail nennt anschließend Etappe, km-Bereich und Onset-Zeit in der Tour-Zeitzone — statt einer anonymen Standort-Warnung ohne Ortsbezug.

## Source

- **File:** `src/services/trip_alert.py` — `check_radar_alerts` segmentbewusst umbauen
- **File:** `src/services/trip_segments.py` — NEU: gemeinsamer Segment-Helfer (Extraktion aus `TripReportSchedulerService._convert_trip_to_segments`)
- **File:** `src/services/trip_report_scheduler.py` — Scheduler ruft neuen Helfer auf (Refactor, Verhalten unverändert)
- **File:** `src/services/radar_service.py` — `format_now_text` bekommt optionalen `tz`-Parameter für Tour-TZ
- **File:** `tests/tdd/test_issue_822_radar_nowcast_segment.py` — mock-freie TDD-Tests

> **Schicht: Python-Backend.** Alle produktiven Dateien liegen in `src/`.
> Go-API (`internal/`, `api/`) und Frontend (`frontend/`) bleiben unberührt.

## Estimated Scope

- **LoC:** ~130–180 (Helfer ~60, trip_alert.py ~50, radar_service.py ~15, Tests ~70)
- **Files:** 4 produktiv (davon 1 neu) + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_report_scheduler.py` — `TripReportSchedulerService._convert_trip_to_segments(trip, target_date)` | upstream (Extraktion) | SSoT-Segmentlogik des Briefings — wird in neuen Helfer extrahiert |
| `src/app/models.py` — `TripSegment`, `Trip`, `Stage` | upstream | Datenstrukturen für Segment-Ableitung |
| `src/services/radar_service.py` — `RadarNowcastService.get_nowcast(lat, lon)`, `format_now_text(result, *, tz=None)` | upstream | Nowcast-Abruf + Onset-Text mit Tour-TZ |
| `src/services/radar_service.py` — `radar_alert_due(result, threshold_min=20)` | upstream | Auslöse-Entscheidung — unverändert |
| `src/output/renderers/email/helpers.py` — `build_segment_label(change_like, segments, *, tz)` | upstream | Erzeugt „Etappe N, km X–Y, HH:MM–HH:MM" (oder Fallback) |
| `src/utils/timezone.py` — `tz_for_coords(lat, lon) -> ZoneInfo` | upstream | Tour-Zeitzone aus den Koordinaten des ersten Segment-Startpunkts |
| `src/services/trip_alert.py` — `get_time_until_next_alert(trip.id)`, Throttle/Recording-Semantik (#773) | internal | Cooldown-Wert auslesen; Recording-Semantik bleibt unverändert |
| `src/outputs/email.py` — `EmailOutput` | downstream | E-Mail-Versand |
| `src/outputs/telegram.py` — `TelegramOutput` | downstream | Telegram-Versand |

## Implementation Details

### A — Segment-Helfer extrahieren (`src/services/trip_segments.py`)

`TripReportSchedulerService._convert_trip_to_segments(trip, target_date) -> List[TripSegment]`
ist eine private Methode, die die SSoT-Segmentlogik für das Briefing enthält. Sie erzeugt
aus Stage-Waypoint-Paaren eine Liste von `TripSegment`-Objekten mit:
- `segment_id` (str: „1"…„N" / „Ziel")
- `start_point` / `end_point` mit `lat`, `lon`, `distance_from_start_km`
- `start_time` / `end_time` (UTC)

**Vorgehen:**
1. Neues Modul `src/services/trip_segments.py` anlegen.
2. Logik 1:1 als Modul-Funktion `convert_trip_to_segments(trip, target_date) -> List[TripSegment]` extrahieren.
3. `TripReportSchedulerService._convert_trip_to_segments` wird zu einem dünnen Delegator:
   ```python
   def _convert_trip_to_segments(self, trip, target_date):
       from services.trip_segments import convert_trip_to_segments
       return convert_trip_to_segments(trip, target_date)
   ```
4. Briefing-Verhalten bleibt **bit-identisch** — Roundtrip-Pflicht: gleicher Trip + Datum
   → identische Segmentliste (segment_id, km, Zeiten, Koordinaten) vor und nach Refactor.

**Wichtig:** Stages ohne Waypoints liefern leere Segmentliste → kein Alert. Dieses
Verhalten ist konsistent mit dem Briefing und wird als Known Limitation dokumentiert.

### B — Aktuelle/nächste Segment-Auswahl in `check_radar_alerts`

Statt `stage.waypoints[0]` wird das aktuelle/nächste Segment mit folgender Logik gewählt:

```
now_utc = datetime.now(UTC)
segments = convert_trip_to_segments(trip, today)

if not segments:
    return  # keine Segmente → kein Alert

active = None
for seg in segments:
    if seg.start_time <= now_utc <= seg.end_time:
        active = seg
        break

if active is None:
    if now_utc < segments[0].start_time:
        active = segments[0]   # vor allen Segmenten → erstes
    else:
        return  # nach allen Segmenten → kein Alert (siehe Entscheidung unten)
```

**Offene Detail-Entscheidung — Randfall „Etappe schon vorbei":**

Wenn `now_utc > segments[-1].end_time` (alle Segmente des Tages zeitlich vorbei):

- Option X: letztes Segment nehmen (Ziel) und prüfen.
- Option Y: keinen Alert senden.

**Default-Empfehlung und gewählte Umsetzung: Option Y — kein Alert.**
Begründung: Ein Regen-Nowcast für ein Segment, das bereits passiert wurde, hat keinen
Nutzwert für den Wanderer. Das Ziel ist eine handlungsrelevante Warnung; ein Alert nach
Etappen-Ende würde Nutzer irritieren. Wenn morgen wieder Segmente bestehen, greift der
nächste Lauf des 15-Minuten-Jobs. Diese Entscheidung ist als Known Limitation dokumentiert.

### C — Nowcast an Segment-Koordinaten + Ort-Label + Tour-TZ

Nach Segment-Auswahl:

```python
lat = active.start_point.lat
lon = active.start_point.lon
tz = tz_for_coords(lat, lon)   # Tour-Zeitzone

result = radar_service.get_nowcast(lat, lon)   # EIN Call pro Trip

if not radar_alert_due(result):
    return

# Ort-Label bauen
change_like = SimpleNamespace(segment_id=active.segment_id)
label = build_segment_label(change_like, segments, tz=tz)

# Onset-Zeit in Tour-TZ
onset_text = format_now_text(result, tz=tz)
```

Genau **ein `get_nowcast`-Call** pro Trip-Lauf (wie bisher).

### D — Mail-Body-Aufbau in `check_radar_alerts` (Aufrufer)

Ort-Label und Cooldown werden im Aufrufer zusammengesetzt, da dort Segment, tz und
Cooldown bekannt sind. `format_now_text` gibt den Onset-Satz (mit tz-korrekter Zeit) zurück.

**Betreff:**
- Konvektiv (`result.is_convective == True`): `[<Trip-Name>] ⚠️ Gewitter – <label>`
- Nicht konvektiv: `[<Trip-Name>] Regen zieht auf – <label>`

Wobei `<label>` die Kurzform des Segment-Labels ist (z.B. „Etappe 3").

**Body:**

```
<onset_text>  (z.B. „Leichter Regen ab ca. 13:05 (in ~5 Min)")
auf <segment_label>.  (z.B. „auf Etappe 3, km 8–12.")

Quelle: <result.source>.
Du erhältst diese Warnung höchstens einmal in <cooldown_display>.
```

`<cooldown_display>` = effektiver Cooldown aus `get_time_until_next_alert`-Logik:
`trip.alert_cooldown_minutes if trip.alert_cooldown_minutes is not None else throttle_hours*60`.
Formatierung: ganzzahlige Stunden → „N Stunde(n)"; Minuten < 60 → „N Minuten".

**`format_now_text` in `radar_service.py`:** Erhält optionalen `tz: ZoneInfo | None = None`-Parameter.
Wenn gesetzt, wird die Onset-Zeit (jetzt + onset_minutes) in dieser TZ formatiert statt
`server_timezone.astimezone()`. Rückwärtskompatibler Default: `tz=None` → bisheriges Verhalten.

### E — Throttle/Recording-Semantik unverändert (#773)

`alert_log`-Eintrag und `radar_alert_throttle.json` werden **unverändert** gesetzt — auch
bei Best-Effort-Versandfehlern (wie nach #773 F001 festgelegt). Mandantentrennung
(`load_all_trips(user_id=self._user_id)`) bleibt.

## Expected Behavior

- **Input:** `check_radar_alerts()` auf einem `TripAlertService(user_id=X)` — iteriert über alle Trips des Users.
- **Output:**
  - Kein Alert wenn: kein Segment aktiv/nächstes (Etappe vorbei), leere Segmentliste,
    Throttle aktiv, `radar_alert_due` = False.
  - Alert-Mail + Telegram (konfigurierte Kanäle) mit Segment-Label, Onset-Zeit in Tour-TZ
    und dynamischem Cooldown-Text wenn: aktives/nächstes Segment vorhanden UND `radar_alert_due` = True
    UND nicht throttled.
- **Side effects:**
  - `data/users/<user_id>/radar_alert_throttle.json` — unverändert gesetzt nach Alert.
  - `data/users/<user_id>/alert_log.json` — Eintrag nach Alert.
  - Genau ein `get_nowcast`-Call pro Trip-Lauf.

## Acceptance Criteria

**AC-1:** Given die `_convert_trip_to_segments`-Logik wird in `src/services/trip_segments.py` als `convert_trip_to_segments` extrahiert und `TripReportSchedulerService._convert_trip_to_segments` delegiert an den Helfer / When `convert_trip_to_segments(trip, target_date)` mit demselben Trip und Datum aufgerufen wird wie zuvor `_convert_trip_to_segments` / Then ist die zurückgegebene Segmentliste bit-identisch: gleiche Anzahl Segmente, gleiche `segment_id`-Werte, gleiche `distance_from_start_km` für Start- und Endpunkt, gleiche `start_time`/`end_time` (UTC), gleiche lat/lon. Kein Mock — echter Trip-Roundtrip mit Datei-State.

**AC-2:** Given ein Trip mit drei Segmenten (Segmente A: 08:00–12:00, B: 12:00–16:00, C: 16:00–20:00 UTC) / When `check_radar_alerts` zu unterschiedlichen Zeitpunkten aufgerufen wird / Then gilt: (a) bei `now = 13:30 UTC` wird Segment B gewählt (Zeit innerhalb [start_time, end_time]); (b) bei `now = 07:00 UTC` (vor allen) wird Segment A gewählt; (c) bei `now = 21:00 UTC` (nach allen) wird kein Alert gesendet. Test beweist Segment-Wahl durch Inspektion des `get_nowcast`-Aufrufs (Koordinaten entsprechen dem erwarteten Segment) oder durch Nachweis kein Versand bei Fall (c). Kein Mock auf `convert_trip_to_segments` oder `build_segment_label`.

**AC-3:** Given ein Trip mit echtem aktivem Segment (heutige Etappe, Start/End-Waypoints mit lat/lon) / When `check_radar_alerts` einen Alert als fällig erkennt (`radar_alert_due = True`) / Then wird `get_nowcast` genau einmal aufgerufen mit den Koordinaten des `start_point` des gewählten Segments — NICHT mit `stage.waypoints[0]`-Koordinaten, sofern diese abweichen. Nachweis: DI-Seam `frame_source` (dokumentierter Test-Seam aus #773) liefert deterministische Regen-Frames; assert exakt ein `get_nowcast`-Call; Koordinaten entsprechen `active.start_point.lat/lon`.

**AC-4:** Given ein Alert wird ausgelöst und `radar_alert_due = True` für das aktuelle Segment / When die Mail verschickt wird / Then enthält der Mail-Body das Segment-Label „Etappe N, km X–Y" (aus `build_segment_label`) mit echten km-Werten aus `distance_from_start_km`, sowie den Cooldown-Text „Du erhältst diese Warnung höchstens einmal in N Stunde(n)" mit dem tatsächlichen effektiven Cooldown-Wert (nicht einem Platzhalter). Test: `build_mime_message`-Aufruf mit kontrolliertem Segment (bekannter km-Bereich) + deterministische Regen-Frames via DI-Seam → MIME-Body auslesen, Segment-Label und Cooldown-String per Substring prüfen. Kein Mock auf Mail-/Label-Logik.

**AC-5:** Given `format_now_text` erhält einen `tz`-Parameter (Tour-Zeitzone aus `tz_for_coords`) / When der Onset-Text generiert wird / Then ist die Onset-Uhrzeit in der Tour-TZ formatiert, nicht in der Server-Zeitzone. Test: Trip mit Koordinaten in einer TZ die sich um ≥2 Stunden von UTC unterscheidet (z.B. CEST UTC+2); `onset_minutes = 10`; assert angezeigte Uhrzeit entspricht `now + 10 min` in der Tour-TZ, nicht in UTC oder Server-TZ. Kein Mock auf `tz_for_coords`.

**AC-6:** Given der effektive Cooldown eines Trips beträgt `trip.alert_cooldown_minutes = 90` (überschreibt den Default) / When ein Alert gesendet wird / Then nennt der Mail-Body „höchstens einmal in 90 Minuten" (nicht „2 Stunden"). Test: Trip mit explizit gesetztem `alert_cooldown_minutes = 90` → MIME-Body enthält „90 Minuten"; Trip ohne `alert_cooldown_minutes` (None, Default 120 min = 2 h) → Body enthält „2 Stunden". Kein Mock auf Cooldown-Logik.

**AC-7:** Given ein Alert wird ausgelöst / When `check_radar_alerts` den Alert verarbeitet / Then wird `alert_log`-Eintrag und `radar_alert_throttle.json` gesetzt (wie nach #773); ein zweiter Aufruf innerhalb des Throttle-Fensters sendet keinen weiteren Alert. Test: erster Lauf → Alert nachweisbar (via DI-Seam oder IMAP), Throttle-Datei existent; zweiter Lauf innerhalb Fenster → kein zweiter Alert, kein neuer IMAP-Eintrag. Kein Mock auf Throttle-Logik.

**AC-8:** Given zwei Nutzer (`tdd-822-ac1`, `tdd-822-ac2`) mit je eigenem Trip und Throttle-State / When `check_radar_alerts` für einen Nutzer läuft / Then ist `data/users/tdd-822-ac2/` nach dem Lauf von `tdd-822-ac1` unberührt — weder Throttle-Datei noch alert_log wurden geändert. Test: zwei `TripAlertService(user_id=...)`-Instanzen, je ein Trip; nach Lauf unter `tdd-822-ac1` sind die Datei-Pfade unter `tdd-822-ac2` unverändert (Timestamp-Vergleich vor/nach). Kein Mock.

## Known Limitations

- **Stages ohne Waypoints:** Trips/Etappen ohne gültige Waypoint-Paare erzeugen eine leere Segmentliste → kein Alert. Das ist konsistent mit dem Briefing-Verhalten. Kein Fix in diesem Slice.
- **Randfall „Etappe vorbei":** Wenn alle Segmente des aktuellen Tags zeitlich abgelaufen sind (`now_utc > segments[-1].end_time`), sendet dieser Slice **keinen Alert** (Variante A, kein Alert). Begründung: vergangene Segmente sind handlungsirrelevant. Der nächste 15-Minuten-Job-Lauf greift wieder, sobald ein neuer Tag beginnt.
- **Ein Koordinaten-Punkt:** Der Nowcast wird am `start_point` des gewählten Segments abgefragt, nicht entlang der gesamten Strecke. Für lange Segmente (> 10 km) kann die Regen-Lage am Endpunkt abweichen. Multi-Punkt-Scan ist kein Scope dieses Slices.
- **Kein Multi-Segment-Scan:** Nur das aktuelle/nächste Segment wird geprüft (Variante A). Gleichzeitige Alerts für mehrere Segmente sind nicht vorgesehen.
- **RADOLAN/INCA-Abdeckung:** Wenn das gewählte Segment außerhalb der RADOLAN/INCA-Bounding-Box liegt, fällt der Nowcast auf AROME/ICON/Open-Meteo zurück — unverändert, kein Fix in diesem Slice.
- **Kein dedizierter Radar-Mail-Validator:** Es existiert kein `radar_alert_validator.py` (analog `briefing_mail_validator.py`). Verifikation erfolgt über DI-Seam + MIME-Prüfung in den TDD-Tests.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_ac1_segment_helper_roundtrip_bit_identical` |
| AC-2 | `test_ac2_segment_selection_by_time` |
| AC-3 | `test_ac3_nowcast_called_at_segment_coordinates` |
| AC-4 | `test_ac4_mail_body_contains_segment_label_and_cooldown` |
| AC-5 | `test_ac5_onset_time_in_tour_timezone` |
| AC-6 | `test_ac6_cooldown_display_reflects_trip_setting` |
| AC-7 | `test_ac7_throttle_recording_unchanged` |
| AC-8 | `test_ac8_mandantentrennung_isolated` |

Testdatei: `tests/tdd/test_issue_822_radar_nowcast_segment.py` (mock-frei).

## Changelog

- 2026-06-15: v1.0 Initial spec created (Issue #822). Radar-/Regen-Nowcast-Alert segmentbewusst machen: gemeinsamer Segment-Helfer, aktives/nächstes Segment nach Tageszeit, Ort-Label via build_segment_label, Tour-TZ via tz_for_coords, dynamischer Cooldown-Text.
