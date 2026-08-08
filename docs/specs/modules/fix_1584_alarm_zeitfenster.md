---
entity_id: fix_1584_alarm_zeitfenster
type: bugfix
created: 2026-08-07
updated: 2026-08-07
status: draft
workflow: fix-1584-alarm-zeitfenster
version: "1.0"
tags: [issue-1584, alerts, day-window, trip-segments, adr-0035]
---

# Ziel-Segment endet am Tagesfenster statt hart 2 Stunden nach Ankunft

## Approval

- [x] Approved

## Purpose

Das Ziel-Segment einer Etappe (`segment_id="Ziel"`) endet heute hart bei
`arrival_time + timedelta(hours=2)`. Beide Alarmpfade
(`weather_change_detection.py`, Radar-/NowCast-Check in `trip_alert.py`) und
die Aggregation (`segment_weather.py`) lesen ausschließlich `segment.end_time`
— die Gefahren-Überwachung für das Tagesziel ist damit strukturell zwei
Stunden nach Ankunft abgeschaltet. Am 2026-08-07 zog ein Hagelgewitter (Böen
44 km/h, 21,5 mm) über das Tagesziel des Trips „KHW 403", ohne dass ein
einziger Alarm ausging. Diese Änderung stellt das Ziel-Segment-Ende auf die
ortszeit-aufgelöste `day_window_end_hour` um, damit Alarm und Aggregation für
das Ziel denselben, bereits etablierten Zeitbegriff (ADR-0035) nutzen wie
Anzeige und Bewertung.

## Source

- **File:** `src/services/trip_segments.py`
- **Identifier:** `convert_trip_to_segments(trip, target_date)` — Konstruktion
  des `destination_segment` (Zeile 243-263, konkret `end_time=` in Zeile 258)

> **Schicht-Hinweis:** Alle Code-Änderungen liegen im Python-Core unter
> `src/services/` und `tests/unit/` (FastAPI-Domain-Backend). Keine Go-,
> keine Frontend-Änderung. Kein Eingriff in `weather_change_detection.py`
> oder `trip_alert.py` selbst — beide lesen unverändert `segment.end_time`
> und ziehen den Fix automatisch nach, ohne angefasst zu werden.

## Estimated Scope

- **LoC:** ~60-90 (Code ~15-25 in `trip_segments.py`, Test-Umschreibung
  ~15-20, neuer E2E-Test ~30-45)
- **Files:** 3 Produktionscode/Test (`trip_segments.py`,
  `tests/unit/test_destination_segment.py`, ein neuer Test am
  Alarm-Sendepfad) + `docs/adr/0035-...md` (Ergänzung, zählt laut
  Regel-Budget nicht zum LoC-Limit)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/day_window.py::resolve_configured_window()` | module | Einzige Quelle für die effektiven Fenster-Grenzen (Default 4/19, Rückwärtskompatibilität bei `None`) — wird für das Ziel-Segment wiederverwendet, kein neuer Auflöser |
| `src/app/models.py::TripReportConfig.day_window_start_hour`/`_end_hour` (Zeile 885-886) | model | Konfigurierbares Tagesfenster liegt NICHT direkt auf `Trip`, sondern auf `TripReportConfig` — erreichbar über das optionale Feld `trip.report_config` |
| `src/utils/timezone.py::tz_for_coords()` | module | Bereits im selben File für die regulären Segmente verwendet (Zeile 181); liefert die Ortszeit-Zone für die letzte Wegpunkt-Koordinate |
| `src/services/segment_weather.py::_aggregate_for_segment()` | module | Liest unverändert `segment.start_time`/`segment.end_time` — Konsument, nicht geändert |
| `src/services/weather_change_detection.py` | module | Liest unverändert `aggregated` (aus dem größeren Fenster) für die Alarmregel `thunder_level` — Konsument, nicht geändert |
| `src/services/trip_alert.py` | module | Radar-/NowCast-Pfad (Zeile 730-745) und Deviations-Fetch (Zeile 964-969) werten `segment.end_time` aus — Konsument, nicht geändert |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | doc | Bestehendes ADR — wird um diesen neuen Konsumenten ergänzt (s. Architektur-Entscheidung) |

## Implementation Details

**`trip_segments.py::convert_trip_to_segments()`, Konstruktion des
`destination_segment` (aktuell Zeile 243-263):**

Statt `end_time=arrival_time + timedelta(hours=2)` wird das Fensterende über
`resolve_configured_window(...)` bestimmt. Die konfigurierten Grenzen liegen
NICHT direkt auf `Trip`, sondern auf `TripReportConfig`
(`src/app/models.py:885-886`), erreichbar über das optionale Feld
`trip.report_config` (kann `None` sein). Analog zum bereits etablierten,
defensiven Muster in `notification_service.py:281-282`
(`getattr(_rc, "day_window_start_hour", None) if _rc else None`) wird
`_rc = trip.report_config` gebildet und
`resolve_configured_window(getattr(_rc, "day_window_start_hour", None) if
_rc else None, getattr(_rc, "day_window_end_hour", None) if _rc else None)`
aufgerufen — ein Trip ganz ohne `report_config` fällt damit über denselben
Defensive-Pfad still auf den Default 4/19 zurück, genau wie ein Trip mit
`report_config`, aber unbesetzten Tagesfenster-Feldern. Das Ergebnis wird auf
die Ortszeit der letzten Wegpunkt-Koordinate (`last_wp.lat`, `last_wp.lon`)
aufgelöst — exakt das Muster, das für die regulären Segmente bereits im
selben File steht (Zeile 181-191: `tz_for_coords()` →
`datetime.combine(...)` mit der aufgelösten Zeit → `.replace(tzinfo=seg_tz)`
→ `.astimezone(timezone.utc)`).

Ablauf:
1. `_rc = trip.report_config`; `_, end_hour = resolve_configured_window(getattr(_rc, "day_window_start_hour", None) if _rc else None, getattr(_rc, "day_window_end_hour", None) if _rc else None)`
2. Ortszeit-Zone der Ziel-Koordinate: `dest_tz = tz_for_coords(last_wp.lat, last_wp.lon)`
3. Fensterende in Ortszeit am Kalendertag der Ankunft konstruieren, nach UTC
   konvertieren (`.astimezone(timezone.utc)`), analog zum bestehenden Muster.
4. **Randfall „Ankunft liegt bereits nach `day_window_end_hour`"**: wenn das
   so berechnete Fensterende `<= arrival_time` ist, greift derselbe Klemm-
   Gedanke wie beim bestehenden Mitternachts-Guard (Zeile 193-204) — statt
   einer negativen oder kollabierten Dauer wird ein minimales Fenster
   verwendet (`end_time = arrival_time + timedelta(hours=1)`, analog zur
   bisherigen Fehlerbehandlung: lieber ein kurzes, aber gültiges Fenster als
   ein Segment, das komplett verschwindet oder rückwärts läuft).
5. `duration_hours` wird aus der tatsächlichen Differenz berechnet statt
   fest `2.0` zu sein.

**Wo die Zusicherung tatsächlich WIRKT (Mutations-Gegenprobe-relevant):** Die
Änderung sitzt ausschließlich an der Segment-Konstruktion. Weder
`weather_change_detection.py` noch `trip_alert.py` noch
`segment_weather.py` werden angefasst — sie lesen weiterhin
`segment.end_time` und `segment.start_time` unverändert. Ein Test, der nur
`convert_trip_to_segments()` isoliert aufruft und `dest.end_time` prüft,
beweist NICHT, dass ein Alarm tatsächlich zugestellt wird — dafür muss der
Test über den echten Alarm-Sendepfad laufen (`TripAlertService` bzw. den
Deviation-Check, analog zu `test_forecast_cache_sharing.py:460+`), sonst
wiederholt sich exakt der Fehler aus diesem Issue: ein Zwischenwert wird
geprüft statt der zugestellten Wirkung.

## Expected Behavior

- **Input:** `trip` (mit optional gesetztem `trip.report_config` und darauf
  optional gesetzten `day_window_start_hour`/`day_window_end_hour`),
  `target_date`.
- **Output:** `destination_segment.end_time` reicht bis zur Ortszeit-
  aufgelösten `day_window_end_hour` (Default 19 Uhr) statt bis
  `arrival_time + 2h`; `duration_hours` entsprechend variabel (5-15h statt
  fix 2h, abhängig von der Ankunftszeit).
- **Side effects:** Aggregation (`segment_weather.py`) und beide Alarmpfade
  sehen automatisch das größere Fenster, ohne selbst geändert zu werden.
  Zielsegment-Zeile und Highlights im Trip-Briefing zeigen künftig
  Aggregate über das größere Fenster (s. Known Limitations —
  nutzersichtbare Nebenwirkung, gewollt).

## Acceptance Criteria

**Zentrale Regel für alle folgenden ACs:** Abnahme hängt an der
**zugestellten Wirkung** — ein Alarm wird tatsächlich versendet (z.B.
`mail_sink`/`sent`-Zustand über den echten `TripAlertService`- bzw.
Deviation-Sendepfad) oder nicht. Ein Test, der nur einen internen
Zwischenwert wie `aggregated.thunder_level_max` oder `segment.end_time`
isoliert prüft, ist NICHT ausreichend — genau diese Verwechslung hat in
diesem Issue bereits zu einer falschen Behauptung geführt. Ebenso reicht ein
Test, der nur das Briefing auf Gewittersymbole prüft, nicht — das ist bereits
heute korrekt und wäre auch ohne diesen Fix grün. **Einzige benannte
Ausnahme: AC-5** — dort geht es ausschließlich um eine
Rückwärtskompatibilitäts-Zusicherung für einen Default-Wert ohne eigene
Wirkungsdimension (kein Verhalten, das an einem Sendepfad unterscheidbar
wäre); AC-5 bleibt deshalb bewusst eine Strukturprüfung. Ein Test muss außerdem
**diskriminierend** sein: er darf nicht in beiden Welten (mit und ohne Fix)
gleichermaßen grün bleiben — ein Zeitpunkt weit außerhalb jedes plausiblen
Fensters beweist nichts, nur ein Zeitpunkt nah an der tatsächlichen Grenze tut
das (s. AC-2a/AC-2b, AC-6).

- **AC-1:** Given ein Trip mit Tagesfenster 4-19 Uhr (Default), dessen letztes
  reguläres Segment um 13:18 Ortszeit am Tagesziel endet, und ein simuliertes
  Gewitter (`thunder_level=HIGH`) um 17:00 Ortszeit am selben Ort / When der
  Alarm-Check zu einer simulierten Zeit von 17:05 Ortszeit läuft / Then wird
  tatsächlich ein Alarm ausgeliefert (Versand über den echten Sendepfad
  nachweisbar, nicht nur ein interner Aggregatwert).
  - Test: Fixture-Zeitreihe mit `thunder_level=HIGH` um 17:00 Ortszeit,
    Ankunft 13:18, Tagesfenster unverändert (4/19). Echter Lauf über
    `TripAlertService`/Deviation-Pfad; Assert über tatsächlich erfolgten
    Versand (z.B. `mail_sink` gefüllt oder äquivalenter Sende-Nachweis) —
    kein Assert allein auf `aggregated.thunder_level_max`.

- **AC-2a (Grenzwert innerhalb, diskriminierende Hälfte):** Given derselbe
  Trip wie AC-1 (Tagesfenster 4-19 Uhr, Ankunft 13:18), und ein simuliertes
  Gewitter (`thunder_level=HIGH`) um 18:45 Ortszeit — knapp innerhalb der
  neuen Fenster-Obergrenze 19:00, aber deutlich außerhalb des alten,
  fehlerhaften 2-Stunden-Fensters (das bei Ankunft 13:18 bereits um 15:18
  endet) / When der Alarm-Check zu einer simulierten Zeit von 18:50 Ortszeit
  läuft / Then wird der Alarm tatsächlich zugestellt. Das ist die
  diskriminierende Hälfte: bliebe der alte 2-Stunden-Fehler bestehen, wäre
  dieser Test rot.
  - Test: Fixture-Zeitreihe mit `thunder_level=HIGH` um 18:45 Ortszeit,
    Ankunft 13:18, Tagesfenster 4/19. Echter Lauf über
    `TripAlertService`/Deviation-Pfad zu simulierter Zeit 18:50 Ortszeit;
    Assert Versand erfolgt über denselben echten Sendepfad wie AC-1.

- **AC-2b (Grenzwert außerhalb, fachlicher Zweck: kein nächtlicher Alarm):**
  Given derselbe Trip wie AC-1/AC-2a, und ein simuliertes Gewitter
  (`thunder_level=HIGH`) um 19:15 Ortszeit — knapp außerhalb der
  Fenster-Obergrenze 19:00 / When der Alarm-Check zu einer simulierten Zeit
  von 19:20 Ortszeit läuft / Then bleibt der Alarm aus. Bewacht die
  ausdrückliche PO-Vorgabe, dass nachts/spätabends kein teurer Alarm
  ausgelöst wird („auf einer Hüttenwanderung braucht das niemand") — und
  dass das neue Fenster nicht versehentlich zu weit geöffnet wird (z.B. bis
  Mitternacht oder unbegrenzt).
  - Test: identischer Aufbau wie AC-2a, Gewitterzeitpunkt auf 19:15
    Ortszeit verschoben, Alarm-Check zu simulierter Zeit 19:20 Ortszeit;
    Assert kein Versand über denselben echten Sendepfad.

- **AC-3:** Given ein Trip, dessen letztes reguläres Segment erst um 20:30
  Ortszeit am Tagesziel ankommt (Fenster 4-19 Uhr, also NACH
  `day_window_end_hour`), und ein simuliertes Gewitter (`thunder_level=HIGH`)
  um 20:45 Ortszeit — innerhalb des minimalen Randfall-Fensters / When der
  Alarm-Check zu einer simulierten Zeit von 20:50 Ortszeit läuft / Then wird
  der Alarm tatsächlich ausgeliefert — der Trip fällt durch die
  Spätankunft NICHT stillschweigend aus der Überwachung (kein Absturz, kein
  „alle Segmente vorbei"-Abbruch im Radar-Pfad).
  - Test: Fixture mit Ankunft 20:30 Ortszeit, `thunder_level=HIGH` um 20:45
    Ortszeit. Echter Lauf über `TripAlertService`/Radar-Pfad zu simulierter
    Zeit 20:50 Ortszeit; Assert Versand erfolgt über denselben echten
    Sendepfad wie in AC-1. Beweist gleichzeitig, dass das Segment gültig
    bleibt (sonst würde der bestehende Radar-Pfad-Abbruch aus
    `trip_alert.py:737-745` greifen und den Trip stumm überspringen).

- **AC-4:** Given ein Trip mit Tagesziel deutlich außerhalb Mitteleuropas
  (Koordinate mit klarem UTC-Versatz zu `Europe/Vienna`, Tagesfenster 4-19
  Uhr Ortszeit am Ziel, Default), und ein simuliertes Gewitter
  (`thunder_level=HIGH`) um 17:00 **Ortszeit am Ziel** / When der Alarm-Check
  zu einer simulierten Zeit von 17:05 Ortszeit am Ziel läuft / Then wird der
  Alarm tatsächlich ausgeliefert — die Fenstergrenze wurde nach der Ortszeit
  am Zielort aufgelöst, nicht nach `Europe/Vienna` (bei fest verdrahteter
  Wiener Zeitzone läge dasselbe UTC-Ereignis außerhalb des dort berechneten
  Fensters und der Alarm bliebe aus).
  - Test: analog AC-1, aber Ziel-Koordinate in einer deutlich versetzten
    Zeitzone; Gewitter-Zeitpunkt und Alarm-Check-Zeitpunkt beide in
    Ortszeit am Ziel angegeben (nicht in Vienna-Zeit umgerechnet). Echter
    Lauf über `TripAlertService`/Deviation-Pfad; Assert Versand erfolgt.
    Ein Testfehlschlag bei fest verdrahteter Vienna-Zeit ist der beweisende
    Fall.

- **AC-5 (strukturell, Rückwärtskompatibilität ohne eigene
  Wirkungsdimension):** Given ein Trip ohne gesetzte
  `day_window_start_hour`/`day_window_end_hour` (Alt-Trip, `None`) / When
  das Ziel-Segment konstruiert wird / Then wird der Default 4/19 Uhr
  verwendet — exakt wie `resolve_configured_window()` es für alle anderen
  Konsumenten bereits tut.
  - Test: Trip-Fixture ohne Tagesfenster-Felder; Assert `dest.end_time`
    entspricht 19:00 Ortszeit (in UTC umgerechnet) am Ankunftstag.

- **AC-6 (konfiguriertes Fenster, diskriminierend gegen fest verdrahteten
  Default — Wächter, kein RED-Test):** Given ein Trip mit **abweichend
  konfiguriertem** Tagesfenster (`report_config.day_window_start_hour = 6`,
  `report_config.day_window_end_hour = 16`, statt Default 4/19), Ankunft
  wie in AC-1 (13:18 Ortszeit), und ein simuliertes Gewitter
  (`thunder_level=HIGH`) um 16:30 Ortszeit — zwischen der konfigurierten
  Obergrenze (16:00) und der Default-Obergrenze (19:00) / When der
  Alarm-Check zu einer simulierten Zeit von 16:35 Ortszeit läuft / Then
  bleibt der Alarm aus, weil 16:30 außerhalb des tatsächlich konfigurierten
  Fensters liegt. Diskriminierend gegen ein hartcodiertes `(4, 19)`: dort
  läge 16:30 innerhalb, der Alarm ginge fälschlich raus und der Test würde
  rot. **Erwarteter RED-Status vor dem Fix: vermutlich bereits grün** — das
  alte 2-Stunden-Fenster endet bei Ankunft 13:18 bereits um 15:18, 16:30
  liegt auch dort außerhalb. AC-6 ist ein Wächter gegen das Aushebeln der
  Einstellbarkeit des Tagesfensters, kein Nachweis des ursprünglichen Bugs
  — er darf nicht künstlich rot gebogen werden, analog zu AC-2b und AC-3.
  - Test: Fixture-Zeitreihe mit `thunder_level=HIGH` um 16:30 Ortszeit,
    Ankunft 13:18, `report_config.day_window_start_hour=6`,
    `day_window_end_hour=16`. Echter Lauf über
    `TripAlertService`/Deviation-Pfad zu simulierter Zeit 16:35 Ortszeit;
    Assert kein Versand über denselben echten Sendepfad.

**Mutations-Gegenprobe (Hinweis für den Adversary):**
- `resolve_configured_window(...)` durch die alten `timedelta(hours=2)`
  ersetzt (Revert auf das alte Fehlverhalten) → AC-1 und AC-2a müssen rot
  werden (18:45/17:00 lägen dann außerhalb des alten Fensters bis 15:18).
- `resolve_configured_window(...)` durch ein hartcodiertes `(4, 19)` ersetzt
  (Konfigurierbarkeit ausgehebelt, Default-Fall bleibt zufällig korrekt) →
  AC-1 bis AC-2b bleiben davon unberührt grün, weil sie alle mit dem
  Default-Fenster arbeiten. **Nur AC-6 fängt diese Mutation**: das
  abweichend konfigurierte Fenster (6-16 Uhr) würde bei hartcodiertem
  `(4, 19)` fälschlich bis 19 Uhr reichen, der Alarm um 16:30 ginge raus,
  AC-6 wird rot.
- Obergrenze des Fensters entfernt (Segment läuft bis Mitternacht oder
  unbegrenzt statt bis `day_window_end_hour`) → die 19:15-Hälfte (AC-2b)
  muss rot werden, weil dann auch ein Gewitter kurz nach 19:00 noch einen
  Alarm auslöst.
- Ortszeit-Auflösung (`tz_for_coords`) entfernt, stattdessen `Europe/Vienna`
  fest verwendet → AC-4 muss rot werden (AC-1/AC-2a/AC-2b/AC-3/AC-6 nutzen
  Ziel-Orte in Mitteleuropa und würden diese Mutation nicht sehen — AC-4 ist
  der einzige AC, der auf einem UTC-Versatz zu Vienna basiert).
- Randfall-Guard aus Schritt 4 entfernt → AC-3 muss rot werden (das
  Segment kollabiert oder wird negativ, das Gewitter um 20:45 Ortszeit
  fällt außerhalb des dann falsch berechneten Fensters).

## Known Limitations

- **Nutzersichtbare Nebenwirkung:** Zielsegment-Zeile und Highlights im
  Trip-Briefing zeigen künftig Aggregate über ein 5-15-Stunden-Fenster statt
  über fix 2 Stunden. Gewollt — beseitigt den Widerspruch zwischen
  Zielsegment-Wert und Metriken-Überblick derselben Mail (0,0 mm vs.
  8,9 mm im Belegfall), aber sichtbar anders als bisher.
- **Nicht einzeln verifiziert:** weitere `aggregated`-Konsumenten
  (`risk_engine.py`, `corridor_threshold.py`, `day_comparison.py`,
  `point_weather.py`) könnten für das größere Zielsegment-Fenster andere
  Schwellen auslösen als bisher. Restrisiko, durch die bestehende Suite nur
  teilweise abgedeckt — nicht Gegenstand dieser Scheibe.
- **Nicht belegt:** ob das SMS-Zeichenbudget bei größeren
  Niederschlags-/Windwerten (aus dem größeren Fenster) an seine Grenze
  kommt. Nicht geprüft, kein bekannter Vorfall.
- **Kollision mit #1329 geprüft, besteht nicht:**
  `tests/unit/test_forecast_cache_sharing.py:385-457` schützt, dass Aggregat
  und Cache-Identität aus dem eigenen Segment-Fenster des jeweiligen
  Aufrufers entstehen (Trip vs. Ortsvergleich) — die Absicht gilt pro
  Aufrufer, nicht pro Segmentgröße. Ein größeres, aber weiterhin eindeutig
  zugeordnetes Fenster verletzt diesen Schutz nicht; keine Anpassung an
  diesem Test nötig.
- **PO-Entscheidung „Ruhezeiten vs. Tagesfenster" (freigegeben):**
  Nach dieser Änderung begrenzen zwei unabhängige Mechanismen die
  Alarmzeit für das Ziel: das Tagesfenster (Daten-Geltungsbereich, hier
  umgesetzt) und die bestehenden Ruhezeiten (Zustellungs-Gate, unverändert).
  **Beide gelten als Schnittmenge** (bei Default-Werten ≈6-19 Uhr), keine
  Ablösung — Ruhezeiten sind eine explizit gesetzte Nutzereinstellung, das
  Tagesfenster meist ein unangetasteter Default. Eine Ablösung würde
  jemandem mit bewusst gesetzten Ruhezeiten (z.B. 22-05 Uhr) plötzlich
  Alarme zwischen 19 und 22 Uhr zustellen. Diese Scheibe ändert an den
  Ruhezeiten selbst nichts — die Schnittmenge ergibt sich automatisch aus
  den bereits bestehenden, unveränderten Ruhezeiten-Prüfungen
  (`_is_quiet_hours()` in `trip_alert.py`, `deviation_alert_engine.py`).
- **Mitternachts-Tagesfenster werden am Zielsegment NICHT abgebildet
  (PO-Entscheidung 2026-08-08, aus Adversary-Befund F005):** Ein Fenster mit
  `day_window_start_hour > day_window_end_hour` (z. B. 22-2 Uhr) ist seit
  #1361/#1372 S1b gültig, hat aber ein **Loch** (im Beispiel 2:00-22:00). Das
  Zielsegment ist ein einzelnes zusammenhängendes Intervall und kann ein Loch
  nicht darstellen. Für solche Trips greift deshalb der Randfall-Guard
  (Mindestfenster 1 h) — bewusst, nicht versehentlich. Der naheliegende
  Ausweg „Fensterende = nächstes Auftreten von `end_hour` ab der Ankunft"
  wurde erprobt und **verworfen**: er schüttet das Loch still zu und liefert
  je nach Ankunftszeit 1 h bis fast 24 h Alarmfenster (bei Tagesankünften
  zwischen 02:01 und 21:59 Ortszeit sogar 16-24 h), was AC-2b und AC-3b
  direkt aushebelt. Eine saubere Lösung müsste das Zielsegment **aufspalten**
  — eigene Scheibe. Bewacht durch
  `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`.
- **Nicht Gegenstand:** `deviation_alert_engine.py:78-106` rechnet
  Ruhezeiten hart in `Europe/Vienna`, nicht in der Ortszeit des Ziels.
  Bestehender Sonderfall, eigene Scheibe (relevant für Trips außerhalb
  Mitteleuropas).
- **Kein Renderer-Fix:** Die frühere Annahme „das Briefing verschweigt die
  Gefahr" ist durch eine Staging-Gegenprobe widerlegt (Issue-Kommentar 3)
  — die zugestellte Mail enthielt Gewittersymbole, Böen und 21,5 mm Regen
  im Nacht-Block (`fetch_night_weather()`, unabhängig vom Segment-Zuschnitt).
  Diese Scheibe fasst keinen Renderer-Code an.

**Folge-Scheiben (nicht Teil dieser Spec):**
1. Ruhezeiten-Prüfung im Radar-Pfad vor den Segment-Check ziehen
   (`trip_alert.py:737-750`), damit die Architektur denselben Fehler nicht
   erneut ermöglicht.
2. Tagesfenster beim Trip-Anlegen editierbar machen
   (`WeatherMetricsTab.svelte:1244`) — durch die Alarmrelevanz aufgewertet.
3. Prüfen, ob der Compare-Pfad dieselbe Zeitfenster-Bindung hat.

**Folge-Scheibe aus F005:** Zielsegment für Mitternachts-Tagesfenster
aufspalten (zwei Intervalle statt eines), damit `start_hour > end_hour` auch
am Ziel wirkt statt auf das Mindestfenster zu fallen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0035 (bestehend, wird ergänzt — kein neues ADR)
- **Rationale:** ADR-0035 hat bereits entschieden, dass es EIN Tagesfenster
  gibt (`resolve_configured_window()`), das auf Anzeige UND Bewertung wirkt,
  und benennt als Folgepflicht ausdrücklich: „Neue Ausgaben (Kanäle,
  Tabellen) beziehen ihr Zeitfenster aus derselben Quelle — kein weiterer
  Auflöser." Diese Scheibe wendet genau diese Folgepflicht auf einen
  bislang unabgedeckten Konsumenten an (die Konstruktion des Ziel-Segments,
  die wiederum Alarm UND Aggregation speist) — sie widerspricht ADR-0035
  nicht und löst es nicht ab, sondern schließt eine Lücke in seiner
  Anwendung. Ein neues ADR wäre hier Overhead: es entsteht kein neuer
  Zeitbegriff, keine neue Quelle, keine neue Bedienfläche — nur ein
  zusätzlicher Aufrufer derselben, bereits etablierten Auflösung. Als Teil
  dieser Scheibe bekommt `docs/adr/0035-...md` einen kurzen Ergänzungs-
  Absatz, der den Ziel-Segment-Alarmpfad als weiteren Konsumenten nennt.

## Changelog

- 2026-08-07: Initial spec created
- 2026-08-07: AC-3/AC-4 auf den Alarm-Sendepfad gehoben (spec-validator
  INVALID-Befund) — beide prüften zuvor nur Segment-Strukturwerte
  (`dest.end_time`), die auch bei kaputter Alarmzustellung grün geblieben
  wären. AC-5 bleibt bewusst strukturell und ist jetzt explizit als
  Ausnahme von der zentralen Wirkungs-Regel gekennzeichnet.
- 2026-08-07: AC-2 als nicht-diskriminierend erkannt (spec-validator
  INVALID-Befund, Runde 3) — 22:00 Ortszeit lag sowohl im alten als auch im
  neuen Fenster außerhalb, der Test wäre in beiden Welten grün geblieben.
  Ersetzt durch Grenzwert-Paar AC-2a (18:45 Ortszeit, innerhalb, beweist den
  Fix) / AC-2b (19:15 Ortszeit, außerhalb, bewacht die PO-Vorgabe „kein
  nächtlicher Alarm" an der tatsächlichen Fenstergrenze). Mutations-Block
  entsprechend ergänzt.
- 2026-08-07: Zwei PO-freigegebene Nachträge — (1) Sachfehler korrigiert:
  das Tagesfenster liegt auf `TripReportConfig` (`models.py:885-886`),
  erreichbar über `trip.report_config` (optional), NICHT direkt auf `Trip`
  — korrigiert in „Dependencies", „Implementation Details" und „Expected
  Behavior". (2) AC-6 ergänzt: die RED-Phase maß, dass ein hartcodiertes
  `(4, 19)` von keinem der bisherigen sechs — jetzt fünf plus AC-6 — ACs
  gefangen wird, weil alle mit dem Default-Fenster arbeiten. AC-6 nutzt ein
  abweichend konfiguriertes Fenster (6-16 Uhr) mit einem Gewitter um 16:30
  Ortszeit, um genau diese Lücke diskriminierend zu schließen; ausdrücklich
  als Wächter ohne eigenen RED-Nachweis gekennzeichnet, analog zu AC-2b/
  AC-3. Mutations-Block entsprechend aufgeteilt (`timedelta(hours=2)` →
  AC-1/AC-2a, hartcodiertes `(4, 19)` → AC-6).
