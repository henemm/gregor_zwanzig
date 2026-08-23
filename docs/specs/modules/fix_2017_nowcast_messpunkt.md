---
entity_id: fix_2017_nowcast_messpunkt
type: bugfix
created: 2026-08-20
updated: 2026-08-20
status: approved
version: "1.0"
tags: [alerts, radar, nowcast, trip, geometry]
---

# Nowcast-Messpunkt: interpolierte Position statt Segment-Startpunkt (Issue #2017)

## Approval

- [x] Approved — PO-Freigabe 2026-08-20 (Henning), 12 ACs

## Purpose

Der Radar-/Nowcast-Alarm (`trip_alert.py`) und der Starkregen-Kurzfristhinweis
(`trip_report_scheduler.py`) fragen das Wetter am **Startpunkt des aktiven Segments** ab — dem
Wegpunkt, den der Wanderer bereits verlassen hat. Gemessen: Median 2,68 km Versatz während der
Gehphasen (Issue-Kommentar), bestätigt durch eigene Messung (Median 1,99 km bei H=55, 3,22 km bei
H=180, siehe Known Limitations). Diese Spec führt einen geteilten Baustein ein, der die Position
**zur Mitte des jeweiligen Vorwarnfensters** aus der Gehzeit-Planung interpoliert (lat, lon **und
Höhe**), und verdrahtet ihn an beiden Fundstellen — ohne zusätzliches API-Budget. Sie ist Stufe 3
einer dokumentierten Verfeinerungskette (#656 → #822 → #2017, siehe Framing unten) und schreibt
die zugehörige Known Limitation in `radar_nowcast.md:110` fort statt sie neu zu erfinden.

## Framing: Stufe 3 einer Verfeinerungskette

| Stufe | Issue | Abfragepunkt |
|---|---|---|
| 1 | #656 | `waypoints[0]` — erster Wegpunkt des Tages |
| 2 | #822 | `active.start_point` — Start des aktiven Segments |
| **3** | **#2017** | **Position zum Onset-Zeitpunkt, angenähert über Interpolation zur Fenstermitte** |

`docs/specs/modules/radar_nowcast.md:110` benennt die Näherung seit #656 ausdrücklich als
bekannte Grenze: „'Aktuelle Position' = repräsentativer Punkt der heutigen Etappe, kein
Live-GPS." Der Kommentar `trip_alert.py:1257` ist eine bewusste Budget-Entscheidung aus #1329,
keine Schlamperei — diese Spec verschärft die Näherung, sie hebt sie nicht auf.

## Der Zirkelschluss — warum "Position zum Onset-Zeitpunkt" nicht exakt erreichbar ist

Der Onset-Zeitpunkt entsteht **aus** dem Nowcast-Ergebnis (`radar_service.py:543-599`,
`_onset_dt = now_utc + timedelta(minutes=result.onset_minutes)`, `trip_alert.py:1282`) — er ist
erst bekannt, *nachdem* die Abfrage mit einer festen Koordinate bereits gelaufen ist. Die exakte
Onset-Position kann mit einem Abruf nicht abgefragt werden, ohne den Onset schon zu kennen. Diese
Spec löst den Zirkel **onset-frei** auf: Position zu einem *festen* Zeitpunkt in der Mitte des
Vorwarnfensters (`now + Fenster//2`), unabhängig vom (noch unbekannten) Onset — ein Abruf,
deterministisch. Zwei Alternativen wurden geprüft und verworfen, siehe Known Limitations 3 und 4.

## Source

- **File:** `src/services/trip_segments.py`, `src/services/trip_alert.py`,
  `src/services/trip_report_scheduler.py`
- **Identifier:** `position_at_time()` (neu), `TripAlertService.check_radar_alerts()`,
  `TripReportSchedulerService._starkregen_hint_data()` (Methode, die
  `trip_report_scheduler.py:1809-1815` enthält)
- **Schicht:** Python-Core (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** Scheibe A ~180–220 (Baustein + eigene Tests), Scheibe B ~60–100 saldiert
  (Wiring an zwei Stellen minus Guard-Rückbau minus gelöschte Testdatei).
  Kein `loc_limit_override` nötig — beide Scheiben bleiben unter 250 LoC.
- **Files:** Scheibe A: 2 (1 modifiziert, 1 neu). Scheibe B: 6 (4 modifiziert, 1 gelöscht, 1
  Doku).
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.trip_segments.resolve_current_segment` | function | Liefert `(active, segment_date)` — Segmentwahl bleibt bei den Aufrufern, unverändert |
| `services.trip_segments.convert_trip_to_segments` | function | Wird vom neuen Baustein selbst genutzt, um Folgesegmente/-tage nachzuladen |
| `services.trip_segments.TripSegment` | model | Trägt `start_time`/`end_time`, `start_point`, `end_point` — Grundlage der Interpolation |
| `app.models.GPXPoint` | model | Rückgabetyp — `lat`, `lon`, `elevation_m` |
| `services.radar_service.RADAR_ONSET_THRESHOLD_MIN` | constant | Aus #2009 — Offset-Quelle für `trip_alert.py` (`//2`); **Voraussetzung: #2009 auf `main`** |
| `services.radar_service.NOWCAST_HORIZON_MIN` | constant | Offset-Quelle für `trip_report_scheduler.py` (`//2`), bereits auf `main` (#1439) |
| `services.radar_service.RadarNowcastService.get_nowcast` | function | Erhält ab Scheibe B die interpolierte Koordinate statt `active.start_point`; trägt seit #1991 `elevation_m` — **Voraussetzung: #1991 auf `main`** |

## Implementation Details

### Scheibe A — geteilter Baustein (sofort startbar, unabhängig von #1991/#2009)

Neue Funktion in `src/services/trip_segments.py` (dieselbe Datei wie
`resolve_current_segment()`/`convert_trip_to_segments()` — Docstring dort nennt sie bereits
„SSoT for segment conversion, shared between briefing and radar alert"):

```python
def position_at_time(
    trip: "Trip", active: TripSegment, segment_date: date, at: datetime,
) -> GPXPoint:
    """Interpolierte Position innerhalb/nach dem aktiven Segment zum Zeitpunkt `at`.

    Onset-frei (#2017): `at` ist ein FESTER Zeitpunkt (Fenstermitte), kein aus
    dem Nowcast-Ergebnis abgeleiteter — sonst Zirkelschluss (siehe Spec).
    """
```

Ablauf:

1. **Ortsfestes Ziel-Segment** (`isinstance(active.segment_id, int)` ist `False`, bzw.
   `active.distance_km == 0.0` — etablierter Filter, siehe `trip_segments.py`
   Existing-Patterns): sofort `active.start_point` zurückgeben. Keine Interpolation — der
   Wanderer bewegt sich dort nicht.
2. **Vorschau-Zweig** (`at` bzw. `now_utc` liegt noch vor `active.start_time` — der Fall, in dem
   `resolve_current_segment()` das erste Segment des Tages als Vorschau liefert,
   `trip_segments.py:412`): Fortschritt = 0, `active.start_point` zurückgeben. Der Wanderer ist
   noch nicht losgelaufen, das ist die richtige Antwort, kein Sonderfall im negativen Sinn.
3. **`at` liegt innerhalb `[active.start_time, active.end_time]`:** Fortschrittsanteil
   `p = (at - active.start_time) / (active.end_time - active.start_time)`, geklemmt auf `[0,1]`.
   Lineare Interpolation von `lat`, `lon` **und `elevation_m`** zwischen `active.start_point` und
   `active.end_point` nach `p`. Dieselbe Näherung wie die bestehende Zeit-Interpolation
   `_interpolate_missing_times()` (`trip_segments.py:59-105`) — dort nur für Zeiten, hier
   erstmals für Geometrie.
4. **`at` liegt nach `active.end_time`:** Vorwärtssuche. `convert_trip_to_segments(trip,
   segment_date)` liefert die volle Tagesliste; das Nachfolgesegment von `active` (per
   `segment_id`-Reihenfolge bzw. Listenindex) wird geprüft; liegt `at` auch darüber hinaus,
   iterativ weiter. Reicht der Tag nicht aus (letztes Segment des Tages endet vor `at`), wird
   `convert_trip_to_segments(trip, segment_date + timedelta(days=1))` nachgeladen und die Suche
   dort fortgesetzt.
5. **Fail-soft** (kein Folgetag vorhanden — Tour zu Ende, Ruhetag ohne Stage, < 2 Wegpunkte,
   oder eine durch den bestehenden Zeitlücken-Guard übersprungene Segmentkette,
   `trip_segments.py:200-218`): auf den letzten bekannten `end_point` klemmen, ein
   `logger.debug`/`logger.warning`-Eintrag mit erkennbarem Grund, **keine Exception nach
   außen**. Der Aufrufer bekommt in jedem Fall einen `GPXPoint` zurück.

`tests/tdd/test_position_at_time.py` (neu) deckt: Interpolation innerhalb eines Segments ·
Höhen-Interpolation · Segmentgrenzen-Überschreitung (Folgesegment) · Tagesgrenzen-Überschreitung
(Folgetag nachgeladen) · Ziel-Segment bleibt stationär · Vorschau-Zweig liefert Fortschritt 0 ·
Fail-soft-Klemme bei fehlendem Folgetag/Ruhetag/Zeitlücke.

### Scheibe B — Wiring (blockiert bis #1991 UND #2009 auf `main`)

**`trip_alert.py:1257-1265`:**

```python
_at = now_utc + timedelta(minutes=RADAR_ONSET_THRESHOLD_MIN // 2)
_pos = position_at_time(trip, active, segment_date, _at)
lat, lon = _pos.lat, _pos.lon
...
result = radar_svc.get_nowcast(lat, lon, elevation_m=_pos.elevation_m, priority="polling")
```

**`trip_report_scheduler.py:1809-1815`:** analog, mit `NOWCAST_HORIZON_MIN // 2` als Offset.
Die **eigene lokale Segmentwahl** dieser Methode (`:1780-1789`, bewusst ohne Vortags-Rückgriff,
#1667 S3) bleibt unangetastet — `position_at_time()` erhält deren `(active, segment_date)` als
Parameter, ohne sie zu beeinflussen. **Geteilt wird ausschließlich die Positionsberechnung.**

**Segment-Ende-Guard-Rückbau (#2009 AC-6):** Der in #2009 eingeführte Guard in `trip_alert.py`
(unterdrückt Alarme, deren Onset nach `active.end_time` liegt) wird **ersatzlos entfernt**,
zusammen mit `tests/tdd/test_radar_alert_segment_end_guard.py`. Der Guard war eine
Ausgleichsmaßnahme für den falschen Messpunkt (dokumentiert als Known Limitation mit
Verfallsdatum in `fix_2009_nowcast_vorlauf.md`, Commit `87644e6a`) — nach dieser Korrektur läge
der Onset systematisch dort, wo der Wanderer zu diesem Zeitpunkt sein wird, und der Guard würde
**richtige** Alarme verwerfen. Das ist der dokumentierte, vorgesehene Rückbau, kein stiller
Spec-Widerruf.

**Bugfestschreibende Tests:** `tests/tdd/test_issue_822_radar_nowcast_segment.py` — **AC-2**
(`test_ac2_segment_selection_by_time`, Zeile 249) und **AC-3**
(`test_ac3_nowcast_called_at_segment_coordinates`, Zeile 388) prüfen heute exakte Gleichheit
(Toleranz `< 0.01°`) mit `active.start_point`. Beide werden auf den interpolierten Punkt
umgeschrieben — begründet über die Verfeinerungskette #656 → #822 → #2017: AC-3 aus #822 wollte
„nicht mehr `waypoints[0]`, sondern der Segment-Startpunkt" beweisen; das bleibt durch #2017
unberührt für den *Vorschau*-Fall (dort ist Fortschritt 0 weiterhin `start_point`), ändert sich
aber für den *aktiven* Fall, wo #2017 einen genaueren Punkt liefert. Beide Tests werden bewusst
und einzeln angepasst, nicht pauschal überschrieben.

**Known-Limitation-Nachzug:** `docs/specs/modules/radar_nowcast.md:110` — „'Aktuelle Position' =
repräsentativer Punkt der heutigen Etappe, kein Live-GPS" wird um die Präzisierung ergänzt: der
repräsentative Punkt ist seit #2017 die zur Fenstermitte interpolierte Position, nicht mehr der
Segment-Startpunkt.

## Expected Behavior

- **Input:** `TripSegment` mit `start_point`/`end_point`/`start_time`/`end_time` aus
  `resolve_current_segment()` bzw. der lokalen Segmentwahl in `trip_report_scheduler.py`; fester
  Zieloffset (`RADAR_ONSET_THRESHOLD_MIN // 2` bzw. `NOWCAST_HORIZON_MIN // 2`).
- **Output:** `GPXPoint` mit interpolierten `lat`/`lon`/`elevation_m`; bei ortsfestem Ziel-Segment
  oder Vorschau-Zweig identisch zum bisherigen `start_point`. `get_nowcast()` wird an beiden
  Fundstellen mit dieser Position statt dem Segment-Startpunkt aufgerufen, inklusive Höhe.
- **Side effects:** Keine zusätzlichen `get_nowcast()`-Aufrufe (weiterhin genau ein Abruf je
  Lauf und Fundstelle). Kein neues Persistenzfeld, keine Migration — `position_at_time()` ist
  eine reine Berechnung, nichts wird gespeichert.

## Acceptance Criteria

- **AC-1:** Given ein aktives Geh-Segment und ein Zeitpunkt `at` innerhalb `[start_time,
  end_time]` / When `position_at_time(trip, active, segment_date, at)` aufgerufen wird / Then
  liegt die zurückgegebene Position linear zwischen `start_point` und `end_point`, entsprechend
  dem Zeitanteil `(at - start_time) / (end_time - start_time)`.
  - Test: echter Aufruf mit konstruiertem Segment und `at` = Fenstermitte, Assert auf
    `lat`/`lon` gegen den analytisch erwarteten interpolierten Wert (kein Mock).

- **AC-2:** Given dasselbe Segment mit unterschiedlicher `elevation_m` an Start- und Endpunkt /
  When `position_at_time()` für einen Zeitpunkt in der Segmentmitte aufgerufen wird / Then ist
  auch `elevation_m` linear interpoliert, nicht die Höhe des Startpunkts.
  - Test: echter Aufruf, Assert auf `elevation_m` gegen den erwarteten Zwischenwert.

- **AC-3:** Given ein Zeitpunkt `at`, der auf ein ortsfestes Ziel-Segment fällt (`segment_id`
  kein `int` bzw. `distance_km == 0.0`) / When `position_at_time()` aufgerufen wird / Then wird
  unverändert `start_point` zurückgegeben, ohne Interpolation.
  - Test: echter Aufruf mit konstruiertem Ziel-Segment, Assert auf Identität mit
    `active.start_point` (nicht nur numerische Nähe).

- **AC-4:** Given `now_utc` liegt noch vor dem ersten Segment des Tages (Vorschau-Zweig aus
  `resolve_current_segment()`, Wanderer noch auf der Unterkunft) / When `position_at_time()`
  aufgerufen wird / Then ist der Fortschrittsanteil 0 und die Rückgabe ist `active.start_point`
  — kein Scheinfehler durch negativen oder verfrühten Zeitanteil.
  - Test: echter Aufruf mit `at`/`now_utc` vor `active.start_time`, Assert auf
    `start_point`-Identität.

- **AC-5:** Given ein Zieloffset, dessen `at` über das Ende des aktiven Segments, aber nicht
  über das Ende des Tages hinausläuft / When `position_at_time()` aufgerufen wird / Then wird
  auf das zeitlich passende Folgesegment desselben Tages weitergesucht und die Position dort
  interpoliert, statt am Ende des aktiven Segments zu klemmen.
  - Test: echter Aufruf über zwei aufeinanderfolgende Segmente, `at` im zweiten Segment, Assert
    auf einen Punkt, der nur aus dem zweiten Segment erreichbar ist.

- **AC-6:** Given ein Zieloffset, dessen `at` über das Ende des letzten Segments des Tages
  hinausläuft / When `position_at_time()` aufgerufen wird / Then wird
  `convert_trip_to_segments(trip, segment_date + 1 Tag)` nachgeladen und die Position im
  entsprechenden Segment des Folgetags interpoliert.
  - Test: echter Aufruf mit `at` jenseits des letzten Tagessegments, Trip mit gültiger
    Folgetags-Etappe, Assert auf einen Punkt aus dem Folgetag.

- **AC-7:** Given `at` liegt jenseits des letzten verfügbaren Segments UND es existiert kein
  Folgetag (Tour zu Ende, Ruhetag ohne Stage, oder eine durch den bestehenden Zeitlücken-Guard
  entstandene Lücke) / When `position_at_time()` aufgerufen wird / Then wird auf den letzten
  bekannten `end_point` geklemmt, ein Log-Eintrag mit erkennbarem Grund geschrieben, und es wird
  **keine** Exception nach außen geworfen.
  - Test: echter Aufruf mit Trip ohne Folgetags-Stage, Assert auf Rückgabewert
    (`end_point`-Identität) und dass der Aufruf nicht wirft.

- **AC-8:** Given `TripAlertService.check_radar_alerts()` mit einem aktiven Geh-Segment / When
  der Radar-Alarm-Pfad läuft / Then wird `get_nowcast()` mit der über `position_at_time(...,
  at=now + RADAR_ONSET_THRESHOLD_MIN // 2)` berechneten Position (inkl. Höhe) aufgerufen, nicht
  mit `active.start_point`.
  - Test: echter `check_radar_alerts()`-Lauf mit einem Segment, dessen `start_point` und
    interpolierter Punkt sich nachweisbar unterscheiden; Assert auf die tatsächlich an
    `get_nowcast()` übergebenen Koordinaten (DI-Seam / Capture, kein Mock der
    Entscheidungslogik).

- **AC-9:** Given der Starkregen-Kurzfristhinweis-Pfad in `trip_report_scheduler.py` mit seiner
  eigenen (unveränderten) Segmentwahl / When er läuft / Then wird `get_nowcast()` mit der über
  `position_at_time(..., at=now + NOWCAST_HORIZON_MIN // 2)` berechneten Position aufgerufen,
  und die Segmentwahl selbst liefert weiterhin dasselbe Segment wie vor dieser Änderung
  (Regressionsschutz für #1667 S3: kein Vortags-Rückgriff).
  - Test: echter Aufruf mit einem Trip, bei dem Alarm- und Briefing-Pfad unterschiedliche
    Segmente wählen würden (z. B. Segment endet genau `now_utc`); Assert, dass beide Pfade ihre
    jeweils eigene, unveränderte Segmentwahl behalten UND beide `position_at_time()` mit ihrem
    eigenen Offset aufrufen.

- **AC-10:** Given der Segment-Ende-Guard aus #2009 (AC-6 jener Spec) ist entfernt / When ein
  Onset-Zeitpunkt errechnet wird, der (nach altem Maßstab) nach `active.end_time` läge / Then
  wird der Alarm **nicht** mehr durch diesen Guard unterdrückt — `check_radar_alerts()` sendet
  ihn regulär, sofern kein anderer Gate ihn stoppt.
  - Test: `tests/tdd/test_radar_alert_segment_end_guard.py` ist gelöscht; ein neuer oder
    bestehender Test in `test_issue_822_radar_nowcast_segment.py` bzw.
    `test_feature_656_radar_nowcast.py` belegt, dass ein später Onset nicht mehr pauschal
    unterdrückt wird (Positivnachweis der Entfernung, nicht nur Abwesenheit des alten Tests).

- **AC-11 (Kontrollfall/Regressionsschutz):** Given ein Segment, dessen Dauer kürzer ist als der
  verwendete Zieloffset (`RADAR_ONSET_THRESHOLD_MIN // 2` bzw. `NOWCAST_HORIZON_MIN // 2`), und
  bei dem die Vorwärtssuche kein weiteres Segment und keinen Folgetag findet / When
  `position_at_time()` läuft / Then bleibt das Verhalten aus AC-7 (Klemmen auf `end_point`,
  kein Crash) — UND ein Kontrollfall mit `at` exakt auf `start_time` liefert weiterhin exakt
  `start_point` (Fortschritt 0 an der unteren Grenze, keine Verschiebung durch Klemmung).
  - Test: zwei Aufrufe im selben Testlauf — Grenzfall unten (`at == start_time` →
    `start_point`) und der bereits in AC-7 geprüfte Grenzfall oben, um **beide Enden des
    Grenzverhaltens von `position_at_time()`** nachzuweisen: unten greift der Vorschau-Zweig,
    oben die Fail-soft-Klemmung. Nicht gemeint ist der Klemm-Ausdruck
    `max(0.0, min(1.0, p))` in `_interpolate_point()` — der wird von diesen beiden Aufrufen
    gar nicht erreicht (beide Aufrufstellen schließen `p` außerhalb `[0,1]` schon durch die
    Verzweigung davor aus; er bleibt als defensive Absicherung für die in Scheibe B
    hinzukommenden Aufrufer stehen). Die Zusicherung ist dadurch nicht schwächer, sondern
    genauer benannt.

- **AC-12 (Budget-Invariante):** Given ein Lauf von `check_radar_alerts()` für einen Trip mit
  aktivem Geh-Segment / When der Radar-Alarm-Pfad vollständig durchläuft / Then erfolgt **genau
  ein** `get_nowcast()`-Aufruf für diesen Trip — die Verlegung des Abrufpunkts erhöht die Zahl
  der Abrufe nicht. Dasselbe gilt analog für den Starkregen-Hinweis-Pfad in
  `trip_report_scheduler.py`. Der Kommentar `trip_alert.py:1257` („Genau EIN get_nowcast-Call
  pro Trip an Segment-Startpunkt") hielt diese Zusicherung bislang nur als Prosa fest; da genau
  diese Zeile durch Scheibe B angefasst wird, verliert der Kommentar seinen Anker — die
  Invariante gehört ab jetzt in einen Test, nicht in einen Kommentar.

  > **⚠️ Für den Alarm-Pfad ABGELÖST durch #2051 S2a** (`feat_2051_s2a_raeumliche_ausdehnung.md`,
  > Abschnitt „Abgelöste Zusicherung"). `check_radar_alerts()` fragt seit S2a **mehrere** Punkte
  > entlang der Reststrecke ab — die räumliche Ausdehnung des Regenereignisses lässt sich aus
  > einem Punkt nicht bilden. An die Stelle von „genau ein Abruf" tritt eine **Obergrenze**
  > (`trip_segments.RADAR_ZONE_MAX_POINTS`); der **erste** Punkt bleibt unverändert der hier
  > spezifizierte #2017-Messpunkt und trägt allein die Auslöseregel, die übrigen liefern nur die
  > Zonen. Bei einer Reststrecke unterhalb des Punktabstands bleibt es faktisch bei einem Abruf.
  >
  > **Unverändert gültig** bleibt AC-12 für den **Starkregen-Hinweis-Pfad**
  > (`trip_report_scheduler.py`, Wächter `test_ac12_starkregen_hinweis_ruft_get_nowcast_genau_einmal`)
  > und für den `/jetzt`-Pfad. Die Ablösung ist eng auf den Alarm-Pfad begrenzt.
  >
  > Den Alarm-Pfad bewacht seither `tests/unit/test_alert_log_capture_correlation.py`
  > (`test_ac4_e2e_zweig_c_...`): Budget-Deckel eingehalten **und** der auslösende Datensatz ist
  > der #2017-Messpunkt, nicht ein Zonen-Folgepunkt.
  - Test: Aufruf-Zähler am `get_nowcast`-Seam (DI-Seam, kein Mock der Entscheidungslogik) über
    einen vollständigen `check_radar_alerts()`-Lauf, Assert `== 1`. Analoger Zähler-Assert für
    den Starkregen-Hinweis-Lauf in `trip_report_scheduler.py`.

## AC-Test-Mapping (Test-Plan)

| AC | Testdatei | Testfunktion (geplant) |
|----|-----------|--------------|
| AC-1 | `tests/tdd/test_position_at_time.py` | `test_ac1_interpolates_within_active_segment` |
| AC-2 | `tests/tdd/test_position_at_time.py` | `test_ac2_elevation_interpolates_too` |
| AC-3 | `tests/tdd/test_position_at_time.py` | `test_ac3_destination_segment_stays_stationary` |
| AC-4 | `tests/tdd/test_position_at_time.py` | `test_ac4_preview_branch_returns_progress_zero` |
| AC-5 | `tests/tdd/test_position_at_time.py` | `test_ac5_crosses_segment_boundary` |
| AC-6 | `tests/tdd/test_position_at_time.py` | `test_ac6_crosses_day_boundary` |
| AC-7 | `tests/tdd/test_position_at_time.py` | `test_ac7_fail_soft_clamps_without_exception` |
| AC-8 | `tests/tdd/test_issue_822_radar_nowcast_segment.py` (MODIFY) | `test_ac2_segment_selection_by_time`, `test_ac3_nowcast_called_at_segment_coordinates` |
| AC-9 | `tests/tdd/test_trip_report_scheduler_starkregen_hint.py` (bestehend, ergänzt) | neue Testfunktion zur Positions-Berechnung |
| AC-10 | `tests/tdd/test_radar_alert_segment_end_guard.py` (DELETE) + Positivnachweis in `test_feature_656_radar_nowcast.py` | siehe oben |
| AC-11 | `tests/tdd/test_position_at_time.py` | `test_ac11_boundary_clamp_regression` |
| AC-12 | `tests/tdd/test_issue_822_radar_nowcast_segment.py` (MODIFY, DI-Seam-Zähler) + `tests/tdd/test_trip_report_scheduler_starkregen_hint.py` (ergänzt) | `test_ac12_single_get_nowcast_call_per_run` (je Pfad) |

### Aufgabenpunkte des Issues → AC-Abdeckung

| Aufgabenpunkt | AC |
|---|---|
| Interpolation im aktiven Segment (statt Startpunkt) | AC-1 |
| Höhe muss mitwandern (#1991-Abhängigkeit) | AC-2 |
| Ziel-Segment bleibt ortsfest | AC-3 |
| Vorschau-Zweig liefert Fortschritt 0 | AC-4 |
| Segmentgrenzen-Überschreitung | AC-5 |
| Tagesgrenzen-Überschreitung | AC-6 |
| Fail-soft, keine Exception | AC-7 |
| Fundstelle 1 (`trip_alert.py`) nutzt den Baustein | AC-8 |
| Fundstelle 2 (`trip_report_scheduler.py`) nutzt den Baustein, eigene Segmentwahl bleibt | AC-9 |
| Segment-Ende-Guard-Rückbau (#2009 AC-6) | AC-10 |
| Regressionsschutz Klemmung/Kontrollfall | AC-11 |
| API-Budget-Neutralität (ein Abruf pro Trip/Lauf) | AC-12 |

## Explizit AUSGESCHLOSSEN

- **Variante 2 (zwei Abrufe, iterativ an der Onset-Position).** Fachlich schlechter, nicht nur
  teurer: anderer Ort ⇒ anderer Onset ⇒ andere Position — das Ergebnis kann in sich
  widersprüchlich werden, die Wahl zwischen den beiden Abrufen ist derselbe Zirkelschluss, den
  diese Spec gerade auflöst. Gemessener Zugewinn gegenüber V1 nur 70 m im Median (H=55) — und
  die Messung ist zu V2 wohlwollend, weil sie das Minimum beider Abrufe wertet, was im Betrieb
  nicht bekannt ist. Doppeltes API-Budget für einen Zugewinn, der den Mechanismus verkompliziert.
- **Variante 3 (Trajektorie — Position je Vorhersage-Zeitschritt).** Strukturell unmöglich mit
  einem Abruf: `RadarFrame` (`src/providers/brightsky.py:32-37`) trägt kein `lat`/`lon`, alle
  Frames stammen aus einer fixen Koordinate (`_fetch_frames_with_fallback(lat, lon)`,
  `radar_service.py:170-241`). Bräuchte zwingend n Abrufe — unverhältnismäßig für ein
  55–180-Minuten-Fenster mit linearer Näherung.
- **GPS/Live-Check-in als Alternative.** Kein technischer, sondern ein Produktentscheid (PO
  2026-08-20): Der Wanderer ist auf der Tour offline oder nur über Satellit erreichbar — das ist
  der Daseinszweck des Produkts. Online-Warnsysteme mit Live-Position existieren zahlreich und
  helfen im Gebirge nicht.
- **`/jetzt`-Sofortabfrage (`trip_command_processor.py:1375`, `stage.waypoints[0]`).** Andere
  Fehlerklasse (kein Onset-Zirkel, sondern falscher Bezugspunkt für eine Sofortabfrage) —
  eigener Befund, nicht Teil dieses Tickets. Prüfung auf eigenes Issue empfohlen.
- **Ortsangabe im Starkregen-Hinweistext** (`starkregen_hint.py:18-27` nennt heute keinen Ort).
  Die wirksamere Folgearbeit für den 180-Minuten-Pfad, aber Mail-Inhalt und damit ein anderer
  Zuschnitt (Renderer-Gate) — eigenes Issue.

## Known Limitations

1. 🔴 **Planposition, nicht Ist-Position.** Das System kennt die tatsächliche Position des
   Wanderers nicht und wird sie nie kennen — er ist offline oder auf Satellit. Das ist der
   Daseinszweck des Produkts, kein Mangel (PO-Entscheid 2026-08-20). Formal: Sei `p_plan` der
   geplante Fortschrittsanteil im Segment zum Zeitpunkt der Abfrage, `p_real` der tatsächliche.
   Fehler des bisherigen Startpunkts = `p_real`; Fehler der Interpolation = `|p_plan − p_real|`.
   Die Interpolation ist mindestens so gut wie der Startpunkt, solange `p_real >= p_plan/2`. Erst
   bei über 50 % Rückstand gegenüber dem Plan kann der Startpunkt zufällig näher an der Wahrheit
   liegen — dann aber „näher an falsch", nie richtig. Diese Korrektur beseitigt den
   **systematischen** Bias (der Startpunkt liegt immer zurück, nie voraus), nicht die
   **stochastische** Abweichung vom Plan.

2. **Restfehler beim 180-Minuten-Pfad (Starkregen-Kurzfristhinweis) bleibt spürbar.** Eigene
   Messung (Trip `5f534011`, 51 Geh-Segmente, 3.595 Geh-Minuten, gleichverteilter Onset):
   V1 bei H=180 senkt den Median von 3,22 km (V0) auf **0,73 km** (−77 %), aber p90 bleibt bei
   **2,45 km**, **17,6 %** der Fälle liegen über 2 km (worst case: p90 3,14 km, 39,6 %). Der
   Starkregen-Hinweis bleibt damit ungenauer als der Alarmpfad (dort bei H=55: Median 0,37 km,
   0,0 % über 2 km). Die wirksamere Folgearbeit ist eine Ortsangabe im Hinweistext selbst — der
   Text nennt heute überhaupt keinen Ort (`starkregen_hint.py:18-27`), weshalb der Leser die
   Aussage unabhängig von der Positionsgenauigkeit auf sich bezieht. Eigenes Issue, weil
   Mail-Inhalt und damit anderer Zuschnitt (Renderer-Gate).

3. **Warum kein zweiter Abruf (V2):** siehe „Explizit AUSGESCHLOSSEN".

4. **Warum keine Trajektorie (V3):** siehe „Explizit AUSGESCHLOSSEN".

5. **Kein Ortsname für den Zwischenpunkt.** `GPXPoint` trägt keinen Namen; der interpolierte
   Punkt liegt namenlos zwischen zwei Wegpunkten. Der Alarmtext nutzt bereits „Etappe N" /
   „km von–bis" (`output/renderers/alert/segments.py:91-111`, `format_alert_location()`), nicht
   den Wegpunktnamen — daraus entsteht kein neuer Zwang. `km_from`/`km_to` in
   `RadarAlertRequest` bleiben unverändert die km-Spanne des **Segments**, nicht des
   Interpolationspunkts (die Aussage „irgendwo in diesem Kilometerbereich" bleibt korrekt,
   unabhängig davon, wo innerhalb der Spanne abgefragt wurde).

7. 🔴 **Der einzige reale Zusatzverbrauch: Trip↔Ortsvergleich teilen keinen Cache-Eintrag
   mehr.** Der Ortsvergleich misst an festen Preset-Koordinaten (er kennt keine Etappen,
   `compare_radar_alert.py:13-16`), der Trip-Pfad seit #2017 an der interpolierten Position.
   Lag ein Preset-Ort bisher exakt auf einem Trip-Wegpunkt, teilten sich beide Pfade innerhalb
   der Cache-TTL einen Abruf; das entfällt — zwei Cache-Schlüssel, zwei Abrufe. **Das ist die
   einzige Stelle, an der diese Änderung real zusätzliches API-Kontingent kostet.**

   Einordnung, ohne zu beschönigen und ohne zu dramatisieren: Der gemeinsame Treffer setzte
   Koordinatengleichheit auf vier Nachkommastellen voraus (~11 m) und war damit Zufall, kein
   Regelfall. Der Alarm-Takt beträgt 900 s, die Cache-TTL 300 s — der Trip-Poll profitierte
   ohnehin nie von seinem eigenen Vorlauf-Cache; betroffen ist allein das Zusammentreffen
   zweier *verschiedener* Funktionen im selben 300-s-Fenster. Der Verbrauchsstrom, der das
   Budget trägt (96 Läufe/Tag je Job), ändert seine Abrufzahl nicht.

   **Sichtbar gehalten statt weggeschrieben:** `tests/unit/test_radar_nowcast_cache_sharing.py`
   führt beide Aussagen getrennt — der Mechanismus-Wächter
   (`test_end_to_end_trip_and_compare_radar_paths_share_one_fetch`) prüft weiterhin scharf,
   dass zwei Aufrufer an *derselben* Stelle einen Abruf teilen (ADR-0033 unverändert in
   Kraft), und
   `test_end_to_end_trip_und_vergleich_am_selben_wegpunkt_erzeugen_zwei_fetches` hält den
   Preis fest. Die Erwartung des Mechanismus-Wächters auf „2 Abrufe" umzustellen wäre der
   falsche Weg gewesen: „2" ist auch das Ergebnis eines vollständig defekten Caches, die
   Zusicherung wäre dann durch ihre eigene Verletzung erfüllt.

6. **Kein Tages-Überlauf in der Messgrundlage getroffen.** Bei der Wirksamkeitsmessung (Trip
   `5f534011`) trat in keiner Kombination aus Variante/Horizont ein Tagesüberlauf auf (0
   übersprungene Onset-Punkte). AC-6 (Tagesgrenzen-Überschreitung) ist damit durch Konstruktion
   getestet, nicht durch reale Beobachtung auf dieser Tour bestätigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche im Sinne von `docs/adr/README.md` (Kanäle, Provider,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie) ist berührt. Die
  Änderung ist eine Präzisierung einer bereits in der Ursprungs-Spec (`radar_nowcast.md:110`)
  dokumentierten Known Limitation, keine neue Grundsatzentscheidung.

## Changelog

- 2026-08-20: Initial spec created (Issue #2017)
- 2026-08-21: Scheibe B geliefert (Verdrahtung beider Pfade, Segment-Ende-Guard-Rückbau).
  Known Limitation 7 ergänzt: Trip und Ortsvergleich teilen keinen Cache-Eintrag mehr,
  wenn ein Preset-Ort auf einem Trip-Wegpunkt liegt — der einzige reale Zusatzverbrauch
  dieser Änderung, mit getrenntem Mechanismus-Wächter belegt statt durch eine
  aufgeweichte Erwartung verdeckt.
- 2026-08-20: AC-11 präzisiert (Adversary-Finding F003, Scheibe A) — geprüft werden beide
  Enden des **Grenzverhaltens von `position_at_time()`** (Vorschau-Zweig unten, Fail-soft-
  Klemmung oben), nicht der von dort unerreichbare Klemm-Ausdruck in `_interpolate_point()`.
  Zusicherung unverändert stark, nur genauer benannt. Zusätzlich abgedeckt seit demselben
  Fix-Loop: Übernachtungslücke zwischen zwei Etappentagen (F002) und die Vorausschau-Grenze
  von einem Folgetag (F004) — beide gehören zur AC-7-Familie „Fail-soft-Klemmung" und ändern
  keine Zusicherung, sondern schließen Testlücken.
