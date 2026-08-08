---
entity_id: fix_1584c_compare_alarm_zeitfenster
type: bugfix
created: 2026-08-08
updated: 2026-08-08
status: draft
workflow: fix-1584c-compare-zeitfenster
version: "1.0"
tags: [issue-1584, compare, alerts, day-window, adr-0035, adr-0009]
---

# Ortsvergleich-Abweichungsalarm vergleicht zwei verschiedene Tageszeiten statt desselben Tagesfensters

## Approval

- [ ] Approved

## Purpose

`CompareLocationWeatherSource.fetch()` baut bei **jedem** Aufruf ein neues
Ein-Stunden-Segment bei `datetime.now()`. Derselbe Code erzeugt sowohl den
Δ-Anker-Snapshot beim Compare-Report-Versand als auch den Frisch-Abruf beim
15-Minuten-Alarm-Check. Beide Aufrufe liegen fast immer zu unterschiedlichen
Tagesstunden — der Abweichungs-Alarm vergleicht damit strukturell nicht
"hat sich die Vorhersage geändert", sondern "ist es eine andere Uhrzeit".
Ausgeführter Beleg (Fixture mit `t2m_c = Stunde`, unveränderte Vorhersage):
Anker 07:00 → `aggregated.temp_max_c = 7.0`, Frisch 15:00 → `= 15.0`, Δ 8,0
gegen Schwelle 7,0 (`weather_change_detection.py:339`) — reiner Tagesgang
genügt zum fälschlichen Auslösen. Umgekehrt bleibt der Alarm blind für echte
Änderungen außerhalb der gerade laufenden Stunde. Diese Scheibe stellt das
synthetische Segment auf das bereits etablierte, geteilte Tagesfenster
(ADR-0035) um, ortszeit-aufgelöst je Ort — Anker und Frisch-Abruf decken
dadurch **durch Konstruktion** dasselbe Fenster desselben Kalendertags ab.
Zusätzlich verhindert eine Anker-Höchstalter-Regel (26 h), dass ein durch
ausbleibenden Versand veralteter Anker (ADR-0009: kein Vergleichsanker ohne
Briefing) weiterhin als Bezugspunkt für Änderungsalarme dient.

## Source

- **File:** `src/services/compare_location_weather_source.py`
- **Identifier:** `CompareLocationWeatherSource.fetch()` (Zeile 32-57, konkret
  die `now`/`now+timedelta(hours=1)`-Segmentkonstruktion Zeile 38-46)

> **Schicht-Hinweis:** Alle Code-Änderungen liegen im Python-Core unter
> `src/services/` und `tests/unit/` (FastAPI-Domain-Backend). Keine Go-,
> keine Frontend-Änderung. `weather_change_detection.py`,
> `segment_weather.py` und `DeviationAlertEngine` (Trip- **und**
> Compare-gemeinsam) werden NICHT angefasst — sie lesen unverändert
> `aggregated`/`fetched_at` und ziehen den Fix automatisch nach.

## Estimated Scope

- **LoC:** ~60-95 Produktivcode (innerhalb des 250-LoC-Budgets), ~80-150 Tests
- **Files:** 3 Produktionscode + 1 neue Testdatei (Namensregel: nach
  Verhalten, nicht Issue-Nummer)
- **Effort:** medium

### Affected Files

| Datei | Änderungstyp | Beschreibung | ~LoC |
|---|---|---|---|
| `src/services/compare_location_weather_source.py` | MODIFY | `fetch()` bekommt Fensterstunden-Parameter; Segment = Tagesfenster des lokalen Kalendertags am Ort statt `now…now+1h` | 35-50 |
| `src/services/compare_alert.py` | MODIFY | `_evaluate_one_location()`/Aufrufkette reicht `resolve_compare_time_window(preset)` an `fetch()` durch; Anker-Höchstalter-Guard (26 h) vor `engine.evaluate()` mit WARNING-Protokollzeile | 15-20 |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `_write_compare_alert_snapshots()` (Zeile 475-491) bekommt dasselbe Fenster durchgereicht (Aufrufstelle Zeile 422-425 hat `preset` bereits im Scope) | 10-15 |
| `src/services/report_config_resolver.py` | UNVERÄNDERT | `resolve_compare_time_window(preset)` (Zeile 193-206) wird nur wiederverwendet — kein neuer Auflöser | 0 |
| `tests/unit/test_compare_alert_day_window.py` | CREATE | Grenzfälle Uhrzeit/Fenster/Anker-Alter am echten Alarm-Sendepfad | 80-150 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/report_config_resolver.py::resolve_compare_time_window(preset)` | function | Einzige Quelle für die effektiven Fenster-Grenzen des Presets (Default 4/19), bereits geteilt zwischen Versand und Vorschau — wird hier um den Alarm-Δ-Pfad als dritten Aufrufer ergänzt |
| `src/utils/timezone.py::tz_for_coords(lat, lon)` | function | Ortszeit-Zone je Compare-Ort — bereits Vorbild in `compare_official_alert.py:257` und `trip_segments.py:263` |
| `src/services/point_weather.py::PointWeatherData.fetched_at` | field | Trägt bereits den Zeitpunkt, zu dem der Anker geschrieben wurde — Basis der 26h-Höchstalter-Prüfung, kein neues Feld nötig |
| `src/services/compare_weather_snapshot.py::CompareWeatherSnapshotService` | module | Lädt/speichert den Δ-Anker unverändert (liest `fetched_at` bereits mit) |
| `src/services/deviation_alert_engine.py::DeviationAlertEngine` | module | Gemeinsamer Auswertungskern Trip+Compare (ADR-0021) — bleibt UNVERÄNDERT; die Anker-Höchstalter-Regel ist Compare-eigene Vorprüfung, kein Eingriff in den geteilten Kern |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | doc | Wird um diesen neuen Konsumenten ergänzt (s. Architektur-Entscheidung) |

## Implementation Details

**`CompareLocationWeatherSource.fetch(point_id, lat, lon, start_hour, end_hour)`:**
Statt `now = datetime.now(timezone.utc).replace(...)` und
`end_time=now + timedelta(hours=1)` wird die Ortszeit-Zone
`tz = tz_for_coords(lat, lon)` bestimmt, der lokale Kalendertag
`local_today = datetime.now(timezone.utc).astimezone(tz).date()` gebildet und
`window_start`/`window_end` als `datetime.combine(local_today, time(start_hour|end_hour)).replace(tzinfo=tz).astimezone(timezone.utc)` — exakt das Muster,
das `trip_segments.py:263-273` bereits für das Ziel-Segment nutzt. Das
Segment deckt damit **immer** das Fenster des laufenden lokalen Kalendertags
ab, unabhängig davon, zu welcher Uhrzeit `fetch()` läuft — es gibt bewusst
**keine** Sonderfall-Verzweigung "nach Fensterende auf morgen umschalten"
(PO-Entscheidung 2, Randfall 22:00). `duration_hours` ergibt sich aus der
tatsächlichen Differenz statt fest `1.0`.

**Aufrufketten:** `compare_alert.py::CompareAlertService.check_all_compare_presets()`
hat `preset` bereits im Scope (Hauptschleife, Zeile 115) und reicht
`resolve_compare_time_window(preset)` durch `_detect_triggered_locations()` →
`_evaluate_one_location()` an `self._weather_source.fetch(location_id, loc.lat, loc.lon, start_hour, end_hour)`.
`scheduler_dispatch_service.py::send_one_compare_preset()` hat `preset` an
der Aufrufstelle von `_write_compare_alert_snapshots()` (Zeile 422-425)
ebenfalls bereits im Scope — die Funktionssignatur bekommt einen zusätzlichen
`preset`-Parameter, aus dem sie dasselbe Fenster auflöst, statt es selbst zu
kennen.

**Anker-Höchstalter-Guard (26 h):** In `_evaluate_one_location()` wird vor dem
Aufruf von `engine.evaluate()` geprüft, ob `cached` nicht leer ist und
`datetime.now(timezone.utc) - cached[0].fetched_at > timedelta(hours=26)`.
Trifft das zu, wird `logger.warning(...)` mit Preset- und Ortskennung
protokolliert und die Methode liefert `None` (kein Trigger) zurück — die
Engine wird für diesen Ort gar nicht erst aufgerufen. Der Anker selbst wird
dabei **nicht** neu geschrieben (das würde die Δ-Wache auf 15 Minuten
verkürzen, s. Known Limitations); der nächste reguläre Report-Versand stellt
sie über `_write_compare_alert_snapshots()` automatisch wieder her. Die
Prüfung sitzt bewusst in `compare_alert.py` und nicht in der geteilten
`DeviationAlertEngine` — sie ist eine Compare-eigene Politik (Anker-Frische
hängt am Versandrhythmus des jeweiligen Presets), keine Trip-Anforderung
dieser Scheibe, und ändert daher keinen Baustein, den der Trip-Pfad mitnutzt.

## Expected Behavior

- **Input:** Compare-Preset mit optionalem `day_window_start_hour`/`_end_hour`
  (Default 4/19 über `resolve_compare_time_window()`), Ort mit `lat`/`lon`,
  bestehender oder fehlender Δ-Anker-Snapshot mit `fetched_at`.
- **Output:** Anker und Frisch-Abruf decken **immer** dasselbe Tagesfenster
  desselben lokalen Kalendertags ab — ein unveränderter Forecast erzeugt kein
  Δ, eine echte Änderung innerhalb des Fensters wird unabhängig von der
  Prüfstunde erkannt. Ist der Anker älter als 26 h, bleibt ein Alarm trotz
  echter Änderung aus, mit WARNING-Protokollzeile.
- **Side effects:** Anzahl der Provider-Abrufe unverändert (s. Known
  Limitations — API-Kontingent). `alert_state`-Schlüssel bleibt
  `metric:ortskennung`, keine Migration.

## Acceptance Criteria

**Zentrale Regel:** Jedes AC hängt an der **zugestellten Wirkung** am
Alarm-Sendepfad (`CompareAlertService.check_all_compare_presets()` →
`NotificationService.send_multi_location_deviation_alert()`, Nachweis über
`mail_sink`/`sent`-Zustand oder äquivalenten Sende-Nachweis) — nicht an
Zwischenwerten wie `aggregated`, `segment.end_time` oder `duration_hours`.
Jedes AC muss **diskriminierend** sein: ein Test, der in alter UND neuer
Implementierung gleichermaßen grün bliebe, ist wertlos (s. Mutations-Block).

- **AC-1 (Normalfall — unveränderte Vorhersage, verschiedene Tagesstunden):**
  Given ein Compare-Preset mit Ort in Mitteleuropa, Tagesfenster 4-19 Uhr
  (Default), Δ-Anker geschrieben um 07:00 Ortszeit, unveränderte
  Vorhersage-Zeitreihe für den gesamten Tag / When der Alarm-Check um 15:00
  Ortszeit desselben Tages läuft / Then bleibt der Alarm aus.
  - Scheitert ohne Fix: Alt-Code baut je Aufruf ein 1h-Fenster bei `now` —
    Anker (07:00-Wert) und Frisch (15:00-Wert) unterscheiden sich im
    Tagesgang und lösen fälschlich einen Alarm aus, obwohl sich nichts
    geändert hat.
  - Test: Fixture-Zeitreihe mit `t2m_c = Stunde` (kein echter Wechsel).
    Echter Lauf über `CompareAlertService`; Assert kein Versand
    (`mail_sink` leer).

- **AC-2 (echte Änderung außerhalb der Prüfstunde):** Given denselben
  Ortsvergleich wie AC-1, und eine echte Vorhersage-Änderung, die eine Schwelle nur um
  14:00 Ortszeit überschreitet (nicht um die aktuelle Prüfstunde) / When der
  Alarm-Check um 15:00 Ortszeit läuft / Then wird der Alarm tatsächlich
  zugestellt.
  - Scheitert ohne Fix: Das alte 1h-Fenster deckt nur 15:00-16:00 ab, der
    geänderte 14:00-Wert liegt außerhalb — der Alarm bleibt fälschlich aus
    (Blindheit-Hälfte des Fehlerbilds).
  - Test: Fixture mit Schwellenüberschreitung exakt in Stunde 14, Prüfzeit
    15:00 Ortszeit. Echter Lauf über `CompareAlertService`; Assert Versand
    erfolgt.

- **AC-3a (Grenzwert innerhalb der Fenster-Obergrenze):** Given Tagesfenster
  4-19 Uhr, eine echte Änderung genau in Stunde 18 (18:00 Ortszeit, letzte
  volle Stunde noch innerhalb `[4,19)`) / When der Alarm-Check läuft / Then
  wird der Alarm zugestellt.
  - Scheitert bei zu engem Fenster (z. B. Rundungsfehler an der
    Obergrenze): Stunde 18 fiele fälschlich heraus, kein Versand.
  - Test: Fixture mit Änderung in Stunde 18. Echter Lauf; Assert Versand.

- **AC-3b (Grenzwert außerhalb der Fenster-Obergrenze):** Given denselben
  Aufbau wie AC-3a, aber die Änderung liegt genau in Stunde 19 (19:00
  Ortszeit, außerhalb `[4,19)` — exklusive Randstunde, analog
  `segment_weather.py` Bug #806) / When der Alarm-Check läuft / Then bleibt
  der Alarm aus.
  - Scheitert bei zu weitem Fenster (z. B. Obergrenze versehentlich
    inklusive oder unbegrenzt): Stunde 19 würde fälschlich mitgezählt, ein
    Alarm ginge unerwünscht raus.
  - Test: Fixture mit Änderung in Stunde 19, sonst identisch zu AC-3a; Assert
    kein Versand.

- **AC-4 (Ortszeit-Auflösung außerhalb Mitteleuropas):** Given ein
  Compare-Ort mit klarem UTC-Versatz zu `Europe/Vienna` (z. B. Nordamerika),
  Tagesfenster 4-19 Uhr Ortszeit am Ort (Default), eine echte Änderung um
  17:00 **Ortszeit am Ort** / When der Alarm-Check zu einer simulierten Zeit
  von 17:05 Ortszeit am Ort läuft / Then wird der Alarm zugestellt.
  - Scheitert bei fest verdrahteter `Europe/Vienna`- oder UTC-Auflösung:
    dasselbe UTC-Ereignis läge außerhalb des dort falsch berechneten
    Fensters, der Alarm bliebe aus. Mitteleuropäische Ziele (AC-1 bis AC-3b)
    sehen diese Mutation nicht — nur AC-4 basiert auf einem echten
    UTC-Versatz.
  - Test: Fixture mit Ziel-Koordinate außerhalb Mitteleuropas, Zeitangaben
    in Ortszeit am Ort. Echter Lauf; Assert Versand.

- **AC-5 (Randfall 22:00 — immer das Fenster des laufenden lokalen Tages,
  kein Umschalten auf den Folgetag):** Given Tagesfenster 4-19 Uhr, Δ-Anker
  geschrieben um 07:00 Ortszeit an Tag D, Vorhersage für Tag D unverändert,
  Vorhersage für Tag D+1 (4-19 Uhr) bewusst **anders** in der Fixture / When
  der Alarm-Check um 22:00 Ortszeit noch an Tag D läuft / Then bleibt der
  Alarm aus.
  - Scheitert bei einer Implementierung, die nach Fensterende auf den
    Folgetag umschaltet: Frisch-Abruf würde Tag D+1 (4-19) berechnen, Anker
    bleibt Tag D (4-19) — die bewusst unterschiedliche D+1-Fixture erzeugt
    dann ein Δ und einen fälschlichen Alarm.
  - Test: Fixture mit unterschiedlichen Zeitreihen für Tag D und Tag D+1,
    Prüfzeit 22:00 Ortszeit an Tag D. Echter Lauf; Assert kein Versand.

- **AC-6a (Anker-Alter knapp unterhalb der 26h-Grenze):** Given ein Δ-Anker
  mit `fetched_at` = jetzt − 25 h 50 min, eine echte Änderung innerhalb des
  Fensters, die eine Schwelle überschreitet / When der Alarm-Check läuft /
  Then wird der Alarm zugestellt.
  - Scheitert bei zu aggressiver Alters-Schwelle (z. B. 24 h statt 26 h):
    dieser noch gültige Anker würde bereits fälschlich unterdrückt.
  - Test: Anker-Fixture mit `fetched_at` 25 h 50 min in der Vergangenheit,
    echte Schwellen-Änderung. Echter Lauf; Assert Versand.

- **AC-6b (Anker-Alter knapp oberhalb der 26h-Grenze — kein Alarm, WARNING
  protokolliert):** Given denselben Aufbau wie AC-6a, aber `fetched_at` =
  jetzt − 26 h 10 min / When der Alarm-Check läuft / Then bleibt der Alarm
  aus, UND es erscheint eine WARNING-Protokollzeile mit der
  Ortsvergleichs-Kennung.
  - Scheitert ohne die Alters-Regel: derselbe (per Konstruktion echte)
    Schwellen-Diff würde einen Alarm gegen einen 26+ Stunden alten,
    ADR-0009-widrigen Anker auslösen.
  - Test: Anker-Fixture mit `fetched_at` 26 h 10 min in der Vergangenheit.
    Echter Lauf; Assert kein Versand UND WARNING-Log-Eintrag mit
    Preset-/Ortskennung.

- **AC-7 (nach neuem Anker wird eine echte Änderung wieder gemeldet):**
  Given den unterdrückten Zustand aus AC-6b (26 h 10 min alter Anker), dann
  wird ein NEUER Δ-Anker geschrieben (`fetched_at` = jetzt, z. B. durch
  regulären Report-Versand) / When derselbe echte Änderungswert erneut
  gegen den neuen Anker geprüft wird / Then wird der Alarm jetzt zugestellt.
  - Scheitert, wenn die Alters-Sperre versehentlich `alert_state` oder
    Cooldown so markiert, als sei die Änderung bereits gemeldet worden: der
    Alarm bliebe auch nach dem neuen, frischen Anker fälschlich aus — die
    Alters-Sperre würde zur Dauerstille statt zur temporären Unterdrückung.
  - Test: Ablauf AC-6b, danach neuer Anker-Snapshot mit aktuellem
    `fetched_at` und demselben (unveränderten) Änderungswert. Echter Lauf;
    Assert Versand erfolgt.

- **AC-8a (Default 4/19 bei fehlenden Tagesfenster-Feldern, innerhalb):**
  Given ein Compare-Preset OHNE gesetzte `day_window_start_hour`/`_end_hour`
  (Produktiv-Regelfall: 4 von 5 Vergleichen), eine echte Änderung in Stunde
  18 / When der Alarm-Check läuft / Then wird der Alarm zugestellt.
  - Scheitert, wenn ein fehlendes Preset-Feld statt auf Default 4/19 auf
    ein anderes Verhalten zurückfällt (z. B. Absturz oder implizit
    "ganzer Tag" wie vor ADR-0035): der Test würde entweder fehlschlagen
    oder AC-8b nicht mehr diskriminierend sein.
  - Test: Preset-Fixture ohne Tagesfenster-Felder, Änderung in Stunde 18.
    Echter Lauf; Assert Versand.

- **AC-8b (Default 4/19 bei fehlenden Tagesfenster-Feldern, außerhalb —
  Regressions-Wächter gegen "Bewertung = ganzer Tag"):** Given denselben
  Aufbau wie AC-8a, aber die Änderung liegt in Stunde 20 (außerhalb des
  Default-Fensters 4-19) / When der Alarm-Check läuft / Then bleibt der
  Alarm aus.
  - Scheitert, wenn ein fehlendes Tagesfenster-Feld (statt auf den Default
    zu fallen) auf die von ADR-0035 abgelöste #1268-Regel "Bewertung = ganzer
    Tag" zurückfällt: Stunde 20 läge dann fälschlich innerhalb, der Alarm
    ginge unerwünscht raus.
  - Test: identisch zu AC-8a, Änderung in Stunde 20 statt 18. Echter Lauf;
    Assert kein Versand.

**Mutations-Gegenprobe (Hinweis für den Adversary):**
- Tagesfenster-Segmentkonstruktion durch die alte `now…now+1h`-Logik ersetzt
  (Revert) → AC-1 muss rot werden (Tagesgang löst wieder fälschlich aus) UND
  AC-2 muss rot werden (Blindheit außerhalb der laufenden Stunde kehrt zurück).
- Obergrenze des Fensters entfernt/verschoben (inklusive statt exklusiv, oder
  unbegrenzt) → AC-3b muss rot werden.
- `tz_for_coords()` durch `Europe/Vienna` oder UTC ersetzt → AC-4 muss rot
  werden; AC-1/AC-2/AC-3a/AC-3b/AC-8a/AC-8b bleiben unberührt (Ziel in
  Mitteleuropa, kein sichtbarer UTC-Versatz zu Vienna).
- Randfall-Sonderfall "nach Fensterende auf Folgetag umschalten" eingebaut →
  AC-5 muss rot werden.
- 26h-Höchstalter-Guard entfernt → AC-6b muss rot werden (Alarm ginge trotz
  veraltetem Anker raus); AC-6a bleibt unberührt (immer noch innerhalb jeder
  denkbaren Schwelle).
- 26h-Höchstalter-Guard schreibt fälschlich `alert_state`/Cooldown beim
  Unterdrücken → AC-7 muss rot werden (Dauerstille auch nach neuem Anker).
- `resolve_compare_time_window()` durch ein hartcodiertes `(0, 24)` ersetzt
  (Konfigurierbarkeit/Default ausgehebelt, "ganzer Tag" wie vor ADR-0035) →
  AC-8b muss rot werden; AC-8a bleibt unberührt.

## Known Limitations

- **Bestandsanker-Übergang:** Alte Anker im 1-Stunden-Zuschnitt können beim
  ersten Alarm-Check nach dem Deploy einmalig einen Fehlalarm auslösen, bis
  der nächste reguläre Report-Versand einen Anker im neuen Tagesfenster-
  Zuschnitt schreibt. Produktiv betrifft das **einen** aktiven Vergleich
  (Le Var — einziger mit aktivierten Alarmen).
- **Schwellen nicht neu kalibriert:** Die bestehenden Δ-Schwellen sind für
  Momentanwerte (1h-Fenster) kalibriert. Ein Maximum über ein ~15h-Fenster
  hat andere statistische Eigenschaften — ob die Schwellen dadurch zu träge
  oder zu empfindlich werden, ist **nicht gemessen** und nicht Gegenstand
  dieser Scheibe.
- **26h-Regel und seltenere Versandrhythmen:** Vergleiche, die seltener als
  täglich versendet werden, haben zwischen zwei Versänden immer einen Anker
  älter als 26 h — der Änderungsalarm bleibt für sie faktisch dauerhaft
  unterdrückt (Radar-/NowCast- und amtlicher Pfad sind davon nicht
  betroffen, s. Nicht in dieser Scheibe). Akzeptierter Trade-off gemäß
  ADR-0009: ohne aktuellen Briefing-Stand gibt es keinen validen
  Vergleichsanker.
- **Mitternachts-Tagesfenster (`start_hour > end_hour`) werden NICHT
  abgebildet**, analog zur bewussten Grenze am Ziel-Segment in
  `trip_segments.py:252-257` (Spec `fix_1584_alarm_zeitfenster.md`,
  ADR-0035). Details/Begründung dort — hier gilt dieselbe Grenze für das
  Compare-Alarm-Segment.
- **API-Kontingent unverändert (abgeleitet, nicht gemessen):** Open-Meteo
  wird tageweise abgefragt (`openmeteo.py:707-709`) und liefert ohnehin 24 h
  (`segment_weather.py:239`), gefiltert wird lokal. Ein breiteres Fenster
  innerhalb desselben Kalendertags ändert die Zahl der Provider-Abrufe
  nicht — diese Aussage ist aus dem Query-Muster abgeleitet, nicht an einer
  echten API-Antwort gemessen.
- **Obergrenze exklusiv — bewusst dem Alarmpfad folgend, nicht der Anzeige
  (gemessene Abweichung):** Diese Scheibe behandelt `day_window_end_hour = 19`
  als **Fensterende um 19:00**, Stunde 19 also außerhalb (AC-3b). Das folgt
  dem Trip-Alarmpfad (`trip_segments.py:269-273` setzt `window_end` auf
  `time(end_hour)`; `segment_weather.py:262-270` filtert `< end_floor`,
  Bug #806) und der ausdrücklich freigegebenen AC-2b von
  `fix_1584_alarm_zeitfenster.md` („Gewitter 19:15 → kein Alarm").
  **Die Anzeige rechnet anders:** `output/renderers/day_window.py:162` prüft
  `start_hour <= h <= end_hour`, Stunde 19 gilt dort als **innerhalb**, und
  `docs/reference/api_contract.md:595` beschreibt die Obergrenze ebenfalls als
  „inklusive". Für einen Wanderer heißt das: ein Ereignis um 19:30 Ortszeit
  erscheint in der Tagesfenster-Anzeige, bewaffnet aber keinen Alarm. Die
  Abweichung besteht seit #1584 und wird hier **nicht** stillschweigend auf
  eine Seite gezogen — sie ist dem PO gemeldet und gehört als eigene
  Entscheidung geklärt (ADR-0035 fordert ein Fenster für Anzeige **und**
  Bewertung).
- **Teilungs-Regel eingehalten:** Es entsteht kein Compare-eigener
  Zeitfenster-Baustein. `resolve_compare_time_window()` (bereits geteilt
  zwischen Versand und Vorschau) und `tz_for_coords()` (bereits Vorbild in
  `compare_official_alert.py` und `trip_segments.py`) werden ausschließlich
  wiederverwendet.

**Nicht in dieser Scheibe** (mit Begründung):

1. **Radar/NowCast-Pfad** (`compare_radar_alert.py`) — hat den Defekt
   strukturell nicht: Regen-Onset ≤ 20 min ist inhärent "jetzt", kein
   Tagesfenster-Bezug.
2. **Amtlicher Pfad** (`compare_official_alert.py`) — nutzt das Tagesfenster
   bereits korrekt als Vorausblick-Horizont mit Klemmung auf `now`; ist das
   Vorbild dieser Scheibe, nicht ihr Gegenstand.
3. **Harte `Europe/Vienna`-Kodierung der Ruhezeiten**
   (`deviation_alert_engine.py:31,105`) — bestehender, unveränderter
   Sonderfall, eigene Scheibe.
4. **#1467-Zusammenlegung** von `check_and_send_alerts()` und
   `check_all_compare_presets()` — diese Scheibe arbeitet unterhalb davon
   (Wetterbeschaffung, nicht Ablaufsteuerung) und fasst
   `deviation_alert_engine.py` nicht an.
5. **#1594** (Alarme brechen am Ende der Ruhezeit gesammelt los, kurz vor
   dem Briefing) — eigenes, unabhängiges Fehlerbild.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0035 (bestehend, wird ergänzt — kein neues ADR)
- **Rationale:** ADR-0035 hat bereits entschieden, dass es EIN Tagesfenster
  gibt (`resolve_configured_window()`/`resolve_compare_time_window()`), das
  auf Anzeige UND Bewertung wirkt, und benennt als Folgepflicht ausdrücklich
  "Neue Ausgaben ... beziehen ihr Zeitfenster aus derselben Quelle — kein
  weiterer Auflöser". Diese Scheibe wendet genau diese Folgepflicht auf
  einen bislang unabgedeckten Konsumenten an: den Compare-Abweichungs-Alarm
  (Anker- und Frisch-Segmentkonstruktion in
  `CompareLocationWeatherSource.fetch()`). Es entsteht kein neuer
  Zeitbegriff und kein neuer Auflöser — nur ein weiterer Aufrufer derselben,
  bereits etablierten Auflösung, analog zum Ziel-Segment-Konsumenten aus
  #1584 (Trip-Scheibe). `docs/adr/0035-...md` bekommt einen kurzen
  Ergänzungs-Absatz für diesen Konsumenten. Die 26h-Anker-Höchstalter-Regel
  stützt zusätzlich ADR-0009 (Alerts als Abweichungs-Wächter gegen den
  Briefing-Stand — ohne aktuellen Briefing-Stand gibt es keinen validen
  Vergleichsanker) und löst es nicht ab; auch dafür ist kein neues ADR
  nötig.

## Changelog

- 2026-08-08: Initial spec created
