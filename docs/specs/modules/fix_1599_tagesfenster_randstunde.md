---
entity_id: fix_1599_tagesfenster_randstunde
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: approved
workflow: fix-1599-tagesfenster-obergrenze
version: "1.0"
tags: [issue-1599, alerts, day-window, trip-segments, compare, adr-0035]
---

# Tagesfenster-Obergrenze wird inklusiv: Alarm zieht die Randstunde nach

## Approval

- [x] Approved — PO-Freigabe 2026-08-17 (ACs auf Deutsch vorgelegt und bestätigt)

## Purpose

Die Obergrenze des Tagesfensters (`day_window_end_hour`, Default 19) wird an
drei Alarm-Stellen **exklusiv** ausgelegt (Fenster endet um 19:00), an allen
Anzeige-Stellen dagegen **inklusiv** (Stunde 19 zählt komplett mit, Fenster
endet faktisch um 20:00). Ein Gewitter um 19:30 Ortszeit erscheint deshalb im
Briefing, löst aber keinen Alarm aus — Anzeige und Bewertung widersprechen
sich am selben Datenpunkt. **PO-Entscheidung 2026-08-17: Der Alarm wird
inklusiv** — „bis 19" heißt, die Stunde 19 zählt vollständig mit, das
Alarmfenster endet zeitlich bei 20:00. Die freigegebene AC-2b aus #1584
(„19:15 Ortszeit → kein Alarm") wird damit ausdrücklich abgelöst durch eine
neue Grenze bei 20:15. Die **konfigurierten Stundenwerte selbst ändern sich
nicht** — `resolve_configured_window()` liefert weiterhin `(4, 19)`;
geändert wird ausschließlich die Umrechnung „Stundenzahl → Zeitgrenze" an
den drei Alarm-Stellen, über einen neuen, gemeinsamen Helfer, damit diese
Kante künftig nicht ein viertes Mal auseinanderlaufen kann.

## Source

- **File:** `src/app/day_window.py`
- **Identifier:** neuer Helfer `window_end_utc_exclusive(local_date, end_hour, tz)`
  — baut aus (Kalendertag, `end_hour`, Ortszeit-Zone) die **exklusive**
  UTC-Obergrenze `[start:00, (end_hour+1):00)`. Ergänzt die bestehende
  `resolve_configured_window()`, die weiterhin nur die Stundenzahlen liefert.

> **Schicht-Hinweis:** Alle Code-Änderungen liegen im Python-Core unter
> `src/app/`, `src/services/`, `src/output/renderers/` und `tests/unit/`, `tests/tdd/`
> (FastAPI-Domain-Backend). Keine Go-, keine Frontend-Änderung — Go und
> Frontend reichen die Stundenzahl nur durch (Persistenz + Klemmung), rechnen
> nie mit ihr (vollständige Auszählung in der Analyse, siehe Kontext-Doc).

## Estimated Scope

- **LoC:** Produktivcode ~80/-30 über ~9 Dateien; Testcode dominiert das
  Budget (Vorbild `tests/unit/test_alarm_zeitfenster_ziel.py` = 852 Zeilen
  für denselben Gegenstand bei #1584) — mehrere hundert Zeilen.
- **Files:** 9 Produktionsdateien (siehe Dependencies), zzgl. mehrerer
  Testdateien (neu + umgeschrieben, siehe „Umzuschreibende Bestandstests")
  und 2 Doku-Dateien (ADR-0035, Spec-Nachtrag #1584 — zählen laut
  Regel-Budget nicht zum LoC-Limit).
- **Effort:** medium-high (kritischer Alarmpfad, drei getrennte
  Umrechnungsstellen, viele Anzeige-Mitleser).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/day_window.py::resolve_configured_window()` | module | Einzige Quelle für die Stundenzahlen (Default 4/19). Bleibt unverändert — der neue Helfer baut nur die Zeitgrenze aus deren Rückgabewert. |
| `src/services/trip_segments.py` | module | **Umrechnungsstelle 1 (Trip-Alarm):** Ziel-Segment-Ende (`end_time = combine(tag, time(end_hour))`, Zeile ~265-297) und der Spätankunfts-Guard rufen künftig `window_end_utc_exclusive()` statt selbst zu rechnen. |
| `src/services/compare_location_weather_source.py` | module | **Umrechnungsstelle 2 (Ortsvergleich-Δ-Alarm):** `_window_bound(window_day, end_hour, tz)` (Zeile ~35, 103-152) ruft künftig denselben Helfer. |
| `src/services/compare_official_alert.py` | module | **Umrechnungsstelle 3 (amtliche Warnungen):** `end_local = local_now.replace(hour=end_hour, ...)` (Zeile ~303-311) als Sichtbarkeits-Horizont ruft künftig denselben Helfer. |
| `src/services/segment_weather.py` | module | Konsument, liest unverändert den halboffenen Filter `start_floor <= ts < end_floor` (Zeile ~254-271) — **nicht ändern** (Bug #806/#856). |
| `src/output/renderers/day_window.py` | module | Anzeige-Filter (inklusiv, Zeile ~140-180) bleibt unverändert; bekommt aber die neue Hilfsfunktion „letzte zum Segment gehörende Stunde" für die Ziel-Sonderregel (`is_last`, Zeile ~200-215, `collect_hiking_window_points`). |
| `src/output/renderers/email/helpers.py`, `src/output/renderers/trip_report.py`, `src/output/renderers/email/plain.py`, `src/output/renderers/email/html.py` | module | `extract_hourly_rows()` liest die ungefilterte Reihe für die Ziel-Tabelle (`email/helpers.py:146-159`, `trip_report.py:483`); Kopfzeile „Wetter am Ziel" (`plain.py:282`, `html.py:1175-1225`), Nacht-Block-Beginn (`trip_report.py:154-160`) und „Ankunft"-Zeile (`plain.py:298`, `html.py:1293`) müssen die Anzeige-Invarianz einhalten. |
| `src/services/weather_extractor.py`, `src/services/trip_command_processor.py` | module | Telegram-`/timeline` (`weather_extractor.py:95` → `trip_command_processor.py:986`) zeigt dieselbe „Ankunft"-Zeile — muss ebenfalls unverändert bleiben. |
| `src/utils/timezone.py::tz_for_coords()` | module | Bereits an allen drei Umrechnungsstellen verwendet für die Ortszeit-Auflösung; unverändert. |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | doc | Bekommt die fehlende Randstunden-Semantik als Entscheidungspunkt ergänzt — deren Fehlen ist die Wurzel der Abweichung. |
| `docs/specs/modules/fix_1584_alarm_zeitfenster.md` | doc | Bekommt einen Nachtrag: AC-2b abgelöst durch #1599. |

## Implementation Details

1. **Ein gemeinsamer Helfer** `window_end_utc_exclusive(local_date, end_hour,
   tz)` in `src/app/day_window.py` konstruiert die Fensterobergrenze in
   Ortszeit (`local_date` + `time(end_hour)`), addiert **eine Stunde erst
   nach der UTC-Konvertierung** und gibt die exklusive UTC-Obergrenze
   zurück. Reihenfolge ist bindend: zuerst `.astimezone(timezone.utc)`, dann
   `+ timedelta(hours=1)` — nicht `time(end_hour + 1)` (existiert nicht bei
   `end_hour = 23`) und nicht Addition vor der UTC-Konvertierung (eine
   Umstellungsnacht könnte sonst die Grenze verschieben). Alle drei
   Alarm-Stellen rufen ausschließlich diesen Helfer; damit gibt es genau
   eine Umrechnung statt drei separaten.
2. **Drei Alarm-Stellen umgestellt:**
   - `trip_segments.py`: Ziel-Segment-Ende nutzt `window_end_utc_exclusive()`
     statt der bisherigen exklusiven Inline-Rechnung.
   - `compare_location_weather_source.py`: `_window_bound()` nutzt denselben
     Helfer für die obere Grenze.
   - `compare_official_alert.py`: der Sichtbarkeits-Horizont für amtliche
     Warnungen nutzt denselben Helfer statt `local_now.replace(hour=end_hour)`.
3. **Anzeige-Invarianz statt globaler Umdeutung.** Eine pauschale Regel
   „Segment-Ende ist jetzt exklusiv+1h" wäre falsch: normale Etappen enden zu
   krummen Zeiten (Naismith/`arrival_override`), und dort gehört die
   Ankunftsstunde bewusst dem **Folge**-Segment (Bug #806/#1146, sichtbar an
   der `is_last`-Sonderregel). Eine Umdeutung aller Segmente würde bei
   glatten Etappenzeiten eine Stunde doppelt zählen oder verlieren.
   Stattdessen eine **neue Hilfsfunktion** „letzte zum Segment gehörende
   Stunde" in `day_window.py`, die ausschließlich für das Ziel-Segment
   (Diskriminator `segment_id == "Ziel"`, etabliert u. a. in `plain.py:281`)
   die neue, um eine Stunde spätere Alarmgrenze **nicht** in die Anzeige
   durchreicht. Alle Anzeige-Konsumenten (Stundentabelle, Kopfzeile,
   Nacht-Block, Ankunft-Zeile in E-Mail/Telegram, Kachelzeile/SMS/Telegram-
   Kurzübersicht) rufen diese Hilfsfunktion statt `segment.end_time.hour`
   direkt zu lesen. Sichtbare Ausgabe bleibt damit **unverändert** — nur die
   Alarm-Auslösung gewinnt die Randstunde.
4. **Spätankunfts-Guard nachziehen** (`trip_segments.py`): Heute greift das
   Mindestfenster von 1 h, sobald die Ankunft `>=` der alten (exklusiven)
   Fenstergrenze liegt. Mit der neuen, eine Stunde späteren Grenze müsste der
   Guard sonst erst eine Stunde später greifen — eine Ankunft um 19:30 hätte
   dann nur noch 30 Minuten Überwachung statt garantiert 60. Der Guard wird
   deshalb von „nur wenn das Fenster schon zu ist" auf „mindestens eine
   Stunde ab Ankunft, unabhängig von der Fenstergrenze" umgestellt.
5. **ADR-0035 und Spec-Nachtrag #1584** wie in „Doku-Folgepflichten"
   beschrieben.

**Wo die Zusicherung tatsächlich WIRKT (Mutations-Gegenprobe-relevant):**
Die Änderung sitzt an vier Stellen — dem gemeinsamen Helfer, den drei
Aufrufern und der neuen Anzeige-Hilfsfunktion. Ein Test, der nur den Helfer
isoliert aufruft und seinen Rückgabewert prüft, beweist NICHT, dass ein
Alarm tatsächlich zugestellt wird oder dass die Anzeige unverändert bleibt —
dafür müssen die ACs über den echten Sendepfad bzw. den echten
Renderer-Output laufen (analog zur Lehre aus #1584).

## Expected Behavior

- **Input:** Trip mit `report_config.day_window_end_hour` (Default 19,
  konfigurierbar), Ortsvergleich-Preset mit äquivalentem Feld, jeweils eine
  Ziel-Koordinate mit auflösbarer Zeitzone.
- **Output:** Die drei Alarm-Pfade (Trip-Δ-Alarm/Radar, Compare-Δ-Alarm,
  Compare-amtliche-Warnungen) werten Ereignisse bis einschließlich der
  konfigurierten Endstunde aus (bei Default 19 also bis 20:00 Ortszeit
  exklusiv). Alle Anzeige-Pfade (Stundentabelle, Kopfzeile, Nacht-Block,
  Ankunft-Zeilen, Kachelzeile/SMS/Telegram-Kurzübersicht) zeigen exakt
  denselben Inhalt wie vor dieser Änderung.
- **Side effects:** Der Spätankunfts-Guard im Ziel-Segment garantiert
  weiterhin mindestens eine Stunde Überwachung ab Ankunft, unabhängig davon,
  wie nah die Ankunft an der (jetzt späteren) Fenstergrenze liegt. Mehr
  Alarme am Abend zwischen der alten und der neuen Grenze sind eine
  gewollte, nutzersichtbare Nebenwirkung (Kern des Fixes), keine
  Kollateralwirkung.

## Acceptance Criteria

**Zentrale Regel:** Für die Alarm-ACs (AC-1 bis AC-6) zählt ausschließlich
die **zugestellte Wirkung** — ein Alarm wird über den echten Sendepfad
(`TripAlertService`/Deviation-Pfad für Trip, den entsprechenden
Compare-Alert-Pfad für Ortsvergleich) tatsächlich versendet oder nicht. Ein
Test, der nur einen internen Zwischenwert wie `end_time` oder
`aggregated.thunder_level_max` prüft, ist NICHT ausreichend — das ist exakt
die Verwechslung, die den ursprünglichen Bug #1584 unentdeckt ließ. Für die
Anzeige-ACs (AC-10 bis AC-15) zählt der tatsächlich gerenderte Ausgabetext
(E-Mail-HTML/Plain, Telegram-Antwort, SMS), nicht ein interner
Zwischenwert. AC-7 bis AC-9 sind bewusst **strukturelle** Wächter-ACs (analog
zu AC-5 in #1584) mit hart hinterlegten Erwartungswerten am gemeinsamen
Helfer, ohne eigene Sendepfad-Wirkung. Jedes Grenzwert-Paar (z. B. AC-1/AC-2)
ist **diskriminierend**: der „außerhalb"-Fall liegt knapp jenseits der neuen
Grenze, nicht irgendwo weit draußen — sonst bliebe der Test in beiden Welten
gleichermaßen grün.

**Rot-Erwartung in der TDD-RED-Phase (verbindlich).** Nicht jeder AC kann vor der
Implementierung rot sein — ein AC, der Bestandsverhalten festschreibt, ist von Anfang an grün.
Damit später nachweisbar bleibt, welcher Test tatsächlich etwas bewacht, gilt die Zuordnung:

| Muss in RED **rot** sein (beweist den Fix) | Ist in RED bereits **grün** (Wächter, muss grün bleiben) |
|---|---|
| AC-1 (Gewitter 19:30 → Alarm), AC-3 (Compare Stunde 19), AC-5 (amtliche Warnung 19:45) | AC-2, AC-4, AC-6 (jeweils die „außerhalb"-Hälfte des Grenzwert-Paars) |
| AC-7, AC-8, AC-9 (Helfer existiert noch nicht) | AC-10 bis AC-15 (Anzeige-Invarianz — sie schützen gegen den Kollateralschaden, den erst die Implementierung auslösen könnte) |
| AC-20 (Wächter setzt den Helfer voraus) | AC-16, AC-17 (Spätankunft: heute grün, würde durch einen unvollständigen Fix **rot** — echter Regressionswächter), AC-18, AC-19 |

Ein in RED grüner Wächter-AC ist **kein** Freibrief: Seine Schutzwirkung wird ausschließlich über
die Mutations-Gegenprobe belegt. Wird die zugehörige Mutation von keinem Test gefangen, ist der
Wächter wertlos und der Befund gehört gemeldet — nicht der Test geschönt.

### Gruppe A — Trip-Alarm (Umrechnungsstelle 1)

- **AC-1:** Given ein Trip mit Tagesfenster 4-19 Uhr (Default) und ein
  simuliertes Gewitter am Tagesziel um 19:30 Ortszeit / When der Alarm-Check
  läuft / Then wird der Alarm tatsächlich zugestellt — das ist der
  eigentliche Fehler aus #1599: heute bleibt der Alarm bei 19:30 aus.
  - Test: Fixture-Zeitreihe mit `thunder_level=HIGH` um 19:30 Ortszeit am
    Tagesziel. Echter Lauf über `TripAlertService`/Deviation-Pfad; Assert
    tatsächlicher Versand (z. B. `mail_sink` gefüllt), nicht nur ein
    Aggregatwert.

- **AC-2:** Given derselbe Trip wie AC-1 und ein simuliertes Gewitter um
  20:15 Ortszeit / When der Alarm-Check läuft / Then bleibt der Alarm aus —
  Positivkontrolle dafür, dass es weiterhin eine Obergrenze gibt. Ohne sie
  könnte das Alarmfenster unbemerkt bis Mitternacht offenstehen. Löst die
  freigegebene AC-2b aus #1584 (Grenze 19:15) ab: derselbe fachliche Zweck
  „kein nächtlicher Alarm auf der Hüttenwanderung", eine Stunde später
  geprüft.
  - Test: identischer Aufbau wie AC-1, Gewitterzeitpunkt auf 20:15 Ortszeit
    verschoben; Assert kein Versand über denselben echten Sendepfad.

### Gruppe B — Ortsvergleich-Δ-Alarm (Umrechnungsstelle 2)

- **AC-3:** Given ein aktivierter Ortsvergleich mit Tagesfenster 4-19 Uhr und
  eine Wetteränderung am verglichenen Ort um 19:40 Ortszeit (innerhalb
  Stunde 19) / When der Compare-Alert-Check läuft / Then wird der Alarm
  tatsächlich zugestellt.
  - Test: Δ-Anker + Fresh-Fetch mit abweichendem Wert um 19:40 Ortszeit;
    echter Lauf über den Compare-Alert-Sendepfad; Assert Versand erfolgt.

- **AC-4:** Given derselbe Ortsvergleich wie AC-3 und dieselbe Wetteränderung
  um 20:10 Ortszeit (innerhalb Stunde 20) / When der Compare-Alert-Check
  läuft / Then bleibt der Alarm aus.
  - Test: identischer Aufbau, Änderungszeitpunkt auf 20:10 Ortszeit
    verschoben; Assert kein Versand über denselben echten Sendepfad.

### Gruppe C — Amtliche Warnungen im Ortsvergleich (Umrechnungsstelle 3)

- **AC-5:** Given ein aktivierter Ortsvergleich mit Tagesfenster 4-19 Uhr und
  eine amtliche Wetterwarnung, deren Gültigkeit um 19:45 Ortszeit beginnt /
  When der amtliche-Warnungs-Check läuft / Then wird die Warnung als
  innerhalb des Sichtbarkeits-Horizonts berücksichtigt und zugestellt — der
  Horizont reicht bis 20:00 Ortszeit, nicht bis 19:00.
  - Test: amtliche Warnungs-Fixture mit Gültigkeitsbeginn 19:45 Ortszeit;
    echter Lauf über `compare_official_alert`-Sendepfad; Assert Versand
    erfolgt.

- **AC-6:** Given denselben Ortsvergleich wie AC-5 und eine amtliche
  Wetterwarnung, deren Gültigkeit erst um 20:15 Ortszeit beginnt / When der
  amtliche-Warnungs-Check läuft / Then bleibt die Warnung außerhalb des
  Sichtbarkeits-Horizonts und wird nicht zugestellt.
  - Test: identischer Aufbau, Gültigkeitsbeginn auf 20:15 Ortszeit
    verschoben; Assert kein Versand über denselben echten Sendepfad.

### Gruppe D — Gemeinsamer Helfer (strukturell, hart hinterlegte Werte)

- **AC-7:** Given der gemeinsame Helfer wird mit `end_hour = 19` für ein
  beliebiges Kalenderdatum und eine feste Zeitzone aufgerufen / When das
  Ergebnis mit einem fest im Test hinterlegten Erwartungswert verglichen
  wird / Then lautet die exklusive UTC-Obergrenze auf denselben Kalendertag
  um 20:00 Ortszeit, umgerechnet nach UTC.
  - Test: `window_end_utc_exclusive(date(...), 19, tz)` gegen hart im Test
    notierten UTC-Zeitstempel (nicht mit derselben Formel nachgerechnet).

- **AC-8:** Given der gemeinsame Helfer wird mit `end_hour = 23`
  aufgerufen (Randfall `time(24)` existiert nicht) / When das Ergebnis
  geprüft wird / Then lautet die exklusive UTC-Obergrenze auf 00:00 Ortszeit
  des **Folgetags**, korrekt nach UTC umgerechnet.
  - Test: `window_end_utc_exclusive(date(...), 23, tz)` gegen hart
    hinterlegten Erwartungswert des Folgetags.

- **AC-9:** Given der gemeinsame Helfer wird für ein Kalenderdatum
  aufgerufen, das ein Sommerzeit-Umstellungsdatum ist (z. B. letzter
  Sonntag im Oktober) / When das Ergebnis geprüft wird / Then stimmt die
  UTC-Obergrenze mit dem tatsächlich gültigen UTC-Versatz dieses Tages
  überein — die `+1 h`-Verschiebung wird nachweislich nach der
  UTC-Konvertierung angewendet, nicht vorher.
  - Test: `window_end_utc_exclusive()` an einem realen Umstellungsdatum
    gegen hart hinterlegten UTC-Zeitstempel (unter Verwendung der
    tatsächlichen `zoneinfo`-Daten, nicht eines Mocks der Umstellung).

### Gruppe E — Anzeige-Invarianz (jeweils eigenständig geprüft)

- **AC-10:** Given ein Trip-Briefing mit Ziel-Segment und Tagesfenster
  4-19 Uhr / When die E-Mail gerendert wird / Then enthält die
  Ziel-Stundentabelle **keine** 20-Uhr-Zeile — obwohl der Alarmpfad ab jetzt
  bis 20:00 auswertet, bleibt die sichtbare Tabelle bei Stunde 19 stehen.
  - Test: gerenderte HTML-/Plain-Mail parsen, Zeilen der Ziel-Stundentabelle
    auszählen; Assert keine Zeile mit Stunde 20.

- **AC-11:** Given dasselbe Trip-Briefing wie AC-10 / When die Kopfzeile
  „Wetter am Ziel" gerendert wird / Then zeigt sie dasselbe Ende wie vor
  dieser Änderung (19:00), nicht die neue Alarm-Obergrenze 20:00.
  - Test: Kopfzeilentext aus HTML und Plain-Text extrahieren; Assert
    identisch zu einer vor der Änderung aufgezeichneten Referenz.

- **AC-12:** Given dasselbe Trip-Briefing wie AC-10 / When der Nacht-Block
  gerendert wird / Then beginnt er zur selben Uhrzeit wie vor dieser
  Änderung, nicht eine Stunde später.
  - Test: Beginn-Zeitstempel des Nacht-Blocks aus dem gerenderten Report
    extrahieren; Assert unverändert gegenüber Referenz.

- **AC-13:** Given dasselbe Trip-Briefing wie AC-10 / When die
  „Ankunft"-Zeile in E-Mail (HTML und Plain) gerendert wird / Then zeigt sie
  denselben Wert wie vor dieser Änderung.
  - Test: „Ankunft"-Zeile aus HTML und Plain-Text extrahieren; Assert
    unverändert gegenüber Referenz.

- **AC-14:** Given einen Telegram-`/timeline`-Aufruf für denselben Trip /
  When die Antwort gerendert wird / Then zeigt die „Ankunft"-Zeile denselben
  Wert wie vor dieser Änderung.
  - Test: `trip_command_processor`-Antwort auf `/timeline` prüfen; Assert
    Ankunft-Zeile unverändert.

- **AC-15:** Given denselben Trip / When Mail-Kachelzeile, SMS-Text und
  Telegram-Kurzübersicht (`glance`) gerendert werden / Then beziehen alle
  drei keinen 20-Uhr-Datenpunkt des Ziel-Segments ein.
  - Test: gerenderte Kachelzeile, `GET /api/preview/{id}/sms`-Text und
    Telegram-`glance`-Antwort auf enthaltene Datenpunkte prüfen; Assert kein
    20-Uhr-Wert des Ziel-Segments.

### Gruppe F — Spätankunft

- **AC-16:** Given ein Trip, dessen Ankunft am Tagesziel um 19:30 Ortszeit
  liegt (Tagesfenster 4-19 Uhr) / When das Ziel-Segment konstruiert wird /
  Then umfasst das Überwachungsfenster **mindestens eine Stunde** ab
  Ankunft — ohne den nachgezogenen Guard würde es auf 30 Minuten schrumpfen,
  weil die neue Fenstergrenze bei 20:00 liegt.
  - Test: Ziel-Segment-Dauer für Ankunft 19:30 Ortszeit berechnen; Assert
    `end_time - arrival_time >= timedelta(hours=1)`.

- **AC-17:** Given ein Trip, dessen Ankunft am Tagesziel um 20:30 Ortszeit
  liegt (nach der neuen Fenstergrenze 20:00) / When das Ziel-Segment
  konstruiert wird / Then umfasst das Überwachungsfenster weiterhin genau
  das bestehende Mindestfenster von einer Stunde — unverändertes
  Regressionsverhalten gegenüber #1584.
  - Test: Ziel-Segment-Dauer für Ankunft 20:30 Ortszeit berechnen; Assert
    `end_time - arrival_time == timedelta(hours=1)`.

### Gruppe G — Normale Etappen und Mitternachtsfenster

- **AC-18:** Given eine reguläre (nicht-Ziel-) Etappe, die zu einer glatten
  Uhrzeit endet (z. B. 15:00 Ortszeit) / When die Ziel-Stundentabelle
  gerendert wird / Then wird die Stunde 15 weder doppelt gezählt (auch im
  Folgesegment) noch verloren — die Anzeige-Hilfsfunktion wirkt
  ausschließlich auf das Ziel-Segment, nicht auf reguläre Etappen (Bug
  #806/#1146, `is_last`-Sonderregel).
  - Test: Etappe mit glattem Endzeitpunkt 15:00 fixieren; Assert Stunde 15
    in der gerenderten Stundentabelle genau einmal erscheint.

- **AC-19:** Given ein Trip mit Mitternachts-Tagesfenster
  (`day_window_start_hour=22`, `day_window_end_hour=2`) / When das
  Ziel-Segment konstruiert und der Alarm-Check ausgeführt wird / Then
  verhält sich das System exakt wie vor dieser Änderung (Mindestfenster-Guard
  von #1584 greift unverändert, PO-Entscheidung 2026-08-08) — diese Scheibe
  ändert am Mitternachtsfall nichts.
  - Test: bestehender Test `test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`
    (aus #1584) bleibt unverändert grün; Assert identisches
    Segment-Verhalten vor und nach dieser Änderung.

### Gruppe H — Wächter gegen die vierte Kopie

- **AC-20:** Given der gemeinsame Helfer `window_end_utc_exclusive()` wird
  testweise so verändert, dass er ein anderes Ergebnis liefert (per
  Monkeypatch, nicht per Quelltext-Edit) / When alle drei Alarm-Pfade (Trip,
  Compare-Δ, Compare-amtliche-Warnungen) mit identischen Randzeitpunkten
  geprüft werden / Then verschiebt sich die Alarmgrenze an **allen drei**
  Stellen gleichermaßen — es gibt keine vierte, unabhängige Umrechnung mehr,
  die von der Änderung unberührt bliebe.
  - Test: `window_end_utc_exclusive` per `monkeypatch` auf eine abweichende
    Rückgabe setzen; alle drei Alarm-Pfade mit demselben Grenzzeitpunkt
    laufen lassen; Assert alle drei reagieren konsistent auf die
    veränderte Grenze (nicht: Trip-Ergebnis gegen Compare-Ergebnis
    vergleichen — siehe Mutations-Gegenprobe).

## Nachträge aus der RED-Phase (2026-08-17)

1. **Zusätzlich umzuschreibender Bestandstest, in der Tabelle unten nicht genannt:**
   `tests/unit/test_alarm_zeitfenster_ziel.py::test_ac6_konfiguriertes_fenster_6_16_...` prüfte ein
   Gewitter um 16:30 bei konfiguriertem Fenster 6–16. Mit inklusiver Obergrenze liegt die Stunde 16
   künftig **innerhalb** (Fenster endet 17:00), der Prüfzeitpunkt verlöre seine Trennschärfe. Er wandert
   auf 17:30 — weiterhin diskriminierend gegenüber einem fälschlich hartcodierten Default `(4, 19)`,
   dessen Grenze bei 20:00 läge. Die Regel gilt allgemein: **jedes** konfigurierte Fenster verschiebt
   seine Kante um eine Stunde, nicht nur das Default-Fenster.
2. **Messort von AC-18 präzisiert.** AC-18 wird an der geteilten Punktequelle
   `collect_hiking_window_points()` geprüft, nicht am gerenderten Text. Grund: Die E-Mail-Stundentabelle
   (`extract_hourly_rows`) filtert je Segment `start_h <= h <= end_h` **ohne** die Disjunktheits-Regel,
   die `collect_hiking_window_points()` für nicht-letzte Segmente hat (`< e_h`). Stoßen zwei Etappen an
   einer glatten Stunde aneinander, erscheint diese Stunde dort **schon heute** in beiden Tabellen.
   Ein AC-18 am gerenderten Text wäre folglich bereits vor dieser Änderung rot und würde einen
   **bestehenden, von #1599 unabhängigen** Befund messen statt die hier zugesicherte Invariante.
   → Als Nebenbefund gemeldet, nicht in dieser Scheibe behoben.
3. **Testumfang:** Die RED-Phase brauchte 591 hinzugefügte / 55 entfernte Testzeilen (netto +536).
   Zusammen mit dem erwarteten Produktivcode liegt der Bedarf bei rund 650 Zeilen.

## Mutations-Gegenprobe

Pflicht für den Adversary: jede der folgenden Verfälschungen muss mindestens
einen der genannten ACs rot machen. Eine Verfälschung, die von KEINEM AC
gefangen wird, ist ein Finding.

- **`+1 h` im gemeinsamen Helfer entfernt** (Rückfall auf die alte,
  exklusive Grenze bei `end_hour:00`) → AC-1, AC-3, AC-5 müssen rot werden
  (19:30/19:40/19:45 lägen dann außerhalb der alten Grenze 19:00); AC-7
  muss rot werden (hart hinterlegter Erwartungswert 20:00 stimmt nicht mehr).
- **`+1 h` zu `-1 h` oder `+2 h` verfälscht** → AC-7, AC-8, AC-9 müssen rot
  werden (falsche hart hinterlegte Erwartungswerte); zusätzlich AC-2
  (bei `+2 h` läge 20:15 plötzlich wieder innerhalb) bzw. AC-1 (bei `-1 h`
  läge 19:30 wieder außerhalb).
- **Anzeige-Kompensation (Hilfsfunktion „letzte zum Segment gehörende
  Stunde") komplett entfernt**, Anzeige liest direkt `segment.end_time.hour`
  → mindestens ein Anzeige-AC muss rot werden, NICHT nur ein Alarm-AC: AC-10
  (Ziel-Tabelle bekommt eine 20-Uhr-Zeile) und/oder AC-11/AC-12/AC-13/AC-14/
  AC-15 müssen rot werden. Bliebe nur ein Alarm-AC betroffen, wäre das ein
  Finding — Alarm und Anzeige sind bewusst getrennte Zusicherungen.
- **Anzeige-Kompensation pauschal auf alle Segmente angewandt** (nicht nur
  auf `segment_id == "Ziel"`) → AC-18 muss rot werden; AC-10-AC-15 bleiben
  davon unberührt grün, weil sie ausschließlich das Ziel-Segment betreffen —
  genau das macht AC-18 zum notwendigen, eigenständigen Wächter.
  **Korrektur 2026-08-17 (Befund F001, Adversary-Runde 1):** Die frühere
  Begründung „die glatte 15-Uhr-Etappe verliert oder verdoppelt eine Stunde"
  ist widerlegt und mit einer reinen Grenzstunden-Prüfung auch nicht
  erfüllbar. Die Grenzstunde ist gegen diese Mutation prinzipiell blind: sie
  ist immer die Startstunde des Folgesegments und bleibt über
  `s_h <= h < e_h` eingeschlossen, solange dieses länger als eine Stunde ist —
  bei kürzeren Folgesegmenten greift der Guard in `display_end_time()`
  (`zurueckgenommen > segment.start_time`) und nimmt gar nichts zurück.
  Zerstört wird die **Lückenfreiheit des Gehzeitfensters**: jedem
  nicht-letzten Segment fehlt danach die Stunde VOR seinem Ende. AC-18 misst
  deshalb die vollständige Stundenkette, nicht die Grenzstunde.
- **Spätankunfts-Guard auf das alte Verhalten zurückgedreht** (Guard greift
  erst ab der neuen Grenze 20:00 statt „mindestens 1 h ab Ankunft") → AC-16
  muss rot werden (Ankunft 19:30 hätte dann nur 30 Minuten statt
  mindestens 1 h); AC-17 bleibt unberührt grün (20:30 liegt so oder so
  jenseits jeder Fenstergrenze) — AC-16 ist der einzige AC, der diese
  Mutation sieht.
- **Nur zwei der drei Alarm-Stellen umgestellt** (z. B. Trip und
  Compare-Δ, aber `compare_official_alert.py` bleibt bei der alten
  Inline-Rechnung) → AC-5/AC-6 müssen rot werden, AC-1-AC-4 bleiben grün.
  Umgekehrt für jede andere Kombination von zwei umgestellten Stellen: der
  jeweils NICHT umgestellte Pfad ist an seinem eigenen AC-Paar erkennbar.
  AC-20 ist der generische Wächter, der jede Auslassung unabhängig vom
  konkreten Pfad sichtbar macht, weil er alle drei Pfade gegen dieselbe
  Manipulation des Helfers prüft.
- **Ein Test vergleicht stattdessen Trip-Ergebnis gegen Compare-Ergebnis**
  (statt gegen hart hinterlegte Erwartungswerte) → **taugt NICHT als
  Wächter**. Beide rufen denselben Helfer; ein Fehler darin bricht beide
  Seiten gleich, der Vergleich bliebe grün. Deshalb sind alle Erwartungswerte
  in AC-7 bis AC-9 und in den Alarm-ACs hart im jeweiligen Test hinterlegt,
  nicht mit derselben Formel nachgerechnet.

## Umzuschreibende Bestandstests

| Test | Heutige Erwartung | Status |
|---|---|---|
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-2b (:533-547) | Gewitter 19:15 → kein Alarm | **umgedreht** — 19:15 liegt jetzt innerhalb (< 20:00), Alarm wird erwartet; die neue Außerhalb-Grenze liegt bei 20:15 (AC-2 dieser Spec) |
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-5 (:812-828) | Ziel-Segment endet 19:00 UTC-konvertiert | **verschoben** — Ende jetzt 20:00 |
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-3 (:559) und Spätankunft (:686) | Ankunft 20:30 gilt als „nach Fensterende" | **verschoben** — Kippkante wandert auf 20:00 (AC-16/AC-17 dieser Spec) |
| `tests/tdd/test_compare_alert_day_window.py::test_ac3b...stunde_19_liegt_ausserhalb` (:509) | Stunde 19 außerhalb | **umgedreht** — Stunde 19 liegt jetzt innerhalb |
| `tests/tdd/test_compare_alert_day_window.py::test_ac8b...stunde_20_ausserhalb` (:727) | Stunde 20 außerhalb | **unberührt** — bleibt gültig als Default-Fall (Preset ohne gesetzte Fenster-Felder). AC-4 dieser Spec verlangt „derselbe Ortsvergleich wie AC-3", also ein **ausdrücklich** gesetztes Fenster; dafür gibt es seit der GREEN-Phase den eigenen Test `test_1599_ac4_aenderung_in_stunde_20_liegt_ausserhalb_des_fensters` |
| `tests/unit/test_destination_segment.py:101-135` | Ziel-Segment-Ende bei alter Grenze | **verschoben** — Erwartungswert auf neue Grenze nachgezogen |
| `tests/helpers/arrival_window_fixtures.py` | feste Ziel-Segment-Endzeiten | **verschoben** — soweit Fixtures die alte Grenze fest kodieren, auf neue Grenze nachgezogen |
| `tests/unit/test_day_window_gap_detection.py` | Lücken-Erkennung nahe der alten Grenze | **verschoben** — Grenzfälle nahe 19:00/20:00 geprüft und ggf. nachgezogen |
| `tests/tdd/test_compare_official_alert_daily_limit_order.py::test_ac17_day_window_end_bleibt_zeichengleich_unveraendert` | SHA-256 von `_day_window_end()` festgeschrieben (#1584 S4a: „Nicht-Ziel") | **Hash neu gepinnt** — `_day_window_end()` ist in #1599 erklärtes Ziel (Umrechnungsstelle 3); Erwartungswert auf den #1599-Stand gesetzt, Tripwire bleibt unverändert scharf (GREEN-Phase 2026-08-17) |
| `tests/tdd/test_radar_alert_follows_ortstag.py::test_ein_etappen_trip_bleibt_nach_mitternacht_im_zielfenster_ueberwacht` | Ziel-Segment-Fenster `02:00-19:00` UTC, Außen-Zeitpunkt 20:00 UTC | **verschoben** — Fenster endet jetzt 20:00 UTC, Außen-Zeitpunkt wandert auf 21:00 UTC (GREEN-Phase 2026-08-17) |
| `tests/tdd/test_compare_dispatch_fixed_window.py` | Stundenpaar `(4, 19)` | **unberührt** — prüft die konfigurierten Stundenzahlen, die sich nicht ändern |
| `tests/tdd/test_daywindow_configurable.py` | Stundenpaar `(4, 19)` | **unberührt** — prüft die konfigurierten Stundenzahlen, die sich nicht ändern |

## Doku-Folgepflichten

- **`docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md`**: Der
  bestehende Absatz „Konsument Ziel-Segment (#1584)" wird um die
  Randstunden-Semantik ergänzt: „Die Obergrenze ist inklusiv; zeitlich
  entspricht das dem halboffenen Intervall `[start:00, (end+1):00)`." Genau
  diese fehlende Festlegung hat die Abweichung zwischen Alarm und Anzeige
  erst ermöglicht — die Ergänzung schließt die Lücke, kein neues ADR nötig
  (siehe „Architektur-Entscheidung" unten).
- **`docs/specs/modules/fix_1584_alarm_zeitfenster.md`**: Bekommt einen
  Changelog-Nachtrag: „AC-2b (19:15 Ortszeit → kein Alarm) abgelöst durch
  #1599 (2026-08-17) — PO-Entscheidung: Obergrenze inklusiv, Alarmfenster
  reicht bis 20:00 statt 19:00. Der fachliche Zweck (kein nächtlicher
  Alarm) bleibt gewahrt, die Prüfgrenze wandert von 19:15 auf 20:15."
- **`docs/reference/api_contract.md:629`**: Beschreibt `day_window_end_hour`
  bereits als „inklusive". Kein Änderungsbedarf — wird als Bestätigung im
  Changelog dieser Spec festgehalten, statt stillschweigend übergangen zu
  werden.
- **`docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md`**: Die dort
  offen benannte Known Limitation zu dieser Randstunden-Kante ist mit
  dieser Spec erledigt und wird entsprechend in ihrem eigenen Changelog
  vermerkt (Verweis auf #1599).

## Known Limitations

- **Nutzersichtbare Nebenwirkung (gewollt):** Das Alarmfenster erweitert
  sich um eine Stunde am Abend. Im Zusammenspiel mit der
  Alarm-Entdopplung (#1467) ist das nach Deploy zu beobachten, aber nicht
  Gegenstand dieser Scheibe.
- **Nicht einzeln verifiziert:** weitere `aggregated`-Konsumenten
  (`risk_engine.py`, `corridor_threshold.py`, `day_comparison.py`,
  `point_weather.py`) könnten für das um eine Stunde größere Ziel-Segment-
  Fenster andere Schwellen auslösen als bisher — Restrisiko, nicht
  Gegenstand dieser Scheibe (übernommen aus #1584, unverändert gültig).
- **Mitternachts-Tagesfenster am Zielsegment weiterhin nicht abgebildet**
  (PO-Entscheidung 2026-08-08, aus #1584): diese Scheibe ändert daran
  nichts, siehe AC-19.
- **Ruhezeiten vs. Tagesfenster:** wie in #1584 festgelegt, gelten beide
  Mechanismen weiterhin als Schnittmenge, keine Ablösung. Diese Scheibe
  ändert an den Ruhezeiten selbst nichts.
- **Nicht Gegenstand:** `deviation_alert_engine.py` rechnet Ruhezeiten
  weiterhin hart in `Europe/Vienna`, nicht in der Ortszeit des Ziels
  (bestehender Sonderfall aus #1584, unverändert).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0035 (bestehend, wird ergänzt — kein neues ADR)
- **Rationale:** ADR-0035 hat bereits entschieden, dass es EIN Tagesfenster
  gibt, das auf Anzeige UND Bewertung wirkt, und benennt als Folgepflicht
  ausdrücklich: „Neue Ausgaben beziehen ihr Zeitfenster aus derselben
  Quelle — kein weiterer Auflöser." Diese Scheibe wendet exakt diese
  Folgepflicht konsequent zu Ende: sie beseitigt die letzte verbliebene
  Divergenz zwischen der (bereits inklusiven) Anzeige-Lesart und der
  (bislang exklusiven) Alarm-Lesart derselben Stundenzahl. Es entsteht kein
  neuer Zeitbegriff, keine neue Quelle, keine neue Bedienfläche — nur eine
  präzisere, gemeinsame Umrechnung einer bereits etablierten Größe. Ein
  neues ADR wäre Overhead; die fehlende Randstunden-Festlegung wird als
  Ergänzung in ADR-0035 nachgetragen (siehe „Doku-Folgepflichten").

## Changelog

- 2026-08-17: Initial spec created. Löst AC-2b aus
  `docs/specs/modules/fix_1584_alarm_zeitfenster.md` ab (dort per Nachtrag
  vermerkt). Bestätigt `docs/reference/api_contract.md:629` als bereits
  korrekt („inklusive") — kein Änderungsbedarf am Vertrag.
- 2026-08-17: Mutations-Gegenprobe, vierter Spiegelstrich korrigiert (Befund
  F001 aus Adversary-Runde 1): Die Grenzstunde einer glatten Etappe kann die
  pauschale Anzeige-Kompensation strukturell nicht sehen. AC-18 misst deshalb
  die Lückenfreiheit der gesamten Gehzeit-Stundenkette statt nur die
  Grenzstunde.
- 2026-08-17: Dateipfade in „Dependencies" und im Schicht-Hinweis korrigiert
  (Befund der Spec-Compliance-Prüfung): die vier Anzeige-Mitleser wohnen unter
  `src/output/renderers/` (`email/helpers.py`, `email/plain.py`,
  `email/html.py`, `trip_report.py`), nicht unter `src/services/`. Der Code war
  von Anfang an richtig, nur der Spec-Text zeigte ins Leere.
- 2026-08-17: AC-4 bekommt einen eigenen Test
  (`test_1599_ac4_aenderung_in_stunde_20_liegt_ausserhalb_des_fensters`).
  Bisher deckte der Bestandstest `test_ac8b...stunde_20_ausserhalb` diese
  Hälfte ab, der jedoch am **Default**-Fenster hängt — AC-4 verlangt wörtlich
  „derselbe Ortsvergleich wie AC-3", also dasselbe **ausdrücklich gesetzte**
  Fenster `(4, 19)`. Beide Hälften der Kante messen jetzt an derselben
  Konfiguration; `test_ac8b` bleibt als Default-Fall bestehen.
