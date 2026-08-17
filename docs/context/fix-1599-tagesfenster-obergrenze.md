# Context: fix-1599-tagesfenster-obergrenze

Issue: [#1599](https://github.com/henemm/gregor_zwanzig/issues/1599) · Track: Full Process

## Request Summary

Die Obergrenze des Tagesfensters (`day_window_end_hour`, z. B. 19) wird an drei Alarm-Stellen
**exklusiv** (Fenster endet 19:00) und an den Anzeige-Stellen **inklusiv** (Stunde 19 zählt mit)
ausgelegt. Ein Gewitter um 19:30 erscheint im Briefing, löst aber keinen Alarm aus.
**PO-Entscheidung 2026-08-17: Der Alarm wird inklusiv** — „bis 19" heißt, die Stunde 19 zählt
komplett mit, das Fenster endet um 20:00. Die freigegebene AC-2b aus #1584 („19:15 → kein Alarm")
wird damit ausdrücklich abgelöst.

## Kern der Ursache

Zwei Denkweisen für dieselbe Größe:

| Denkweise | Wo | Form |
|---|---|---|
| **Stundenband** (inklusiv) | Anzeige/Aggregation | `start_h <= h <= end_h` |
| **Zeitintervall** (halboffen) | Alarm-Pfade | `start <= ts < end` |

Ein inklusives Stundenband `[4..19]` entspricht dem Intervall `[04:00, 20:00)`. Überall dort, wo
aus der Stundenzahl `end_hour` eine **Zeitgrenze** gemacht wird, fehlt heute die Stunde `+1`.
Der Filter selbst (`< end_floor`) ist korrekt und darf nicht angefasst werden — er sichert seit
Bug #806 zu, dass jede Stunde genau **einem** Segment gehört.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_segments.py:265-297` | **Umrechnungsstelle 1 (Trip-Alarm):** `window_end = combine(tag, time(end_hour))` → Ziel-Segment endet 19:00. Hier liegt der eigentliche Fix; auch der Spätankunfts-Guard (`window_end <= arrival_time`) verschiebt sich um eine Stunde. |
| `src/services/compare_location_weather_source.py:35,103-152` | **Umrechnungsstelle 2 (Ortsvergleich-Alarm):** `_window_bound(window_day, end_hour, tz)`, Kommentar ab :125 dokumentiert die exklusive Auslegung ausdrücklich. |
| `src/services/compare_official_alert.py:303-309` | **Umrechnungsstelle 3 (amtliche Warnungen):** `end_local = local_now.replace(hour=end_hour, ...)` als Horizont — dritte Variante derselben Größe. |
| `src/services/segment_weather.py:254-271` | Konsument: halboffener Filter `start_floor <= ts < end_floor`. **Nicht ändern** (Bug #806/#856). |
| `src/app/day_window.py:16-50` | `DAY_WINDOW_START_HOUR/END_HOUR`, `resolve_configured_window()` — liefert Stundenzahlen, EINE Quelle für die Grenzen. Natürlicher Ort für einen gemeinsamen Intervall-Helfer. |
| `src/output/renderers/day_window.py:140-180` | Anzeige-Filter, inklusiv (`start_h <= h <= end_h`), inkl. Mitternachts-Wrap. Bleibt unverändert. |
| `src/services/comparison_engine.py:45-90` | Ortsvergleich-Anzeige/Aggregation, ebenfalls inklusiv. Bleibt unverändert. |
| `docs/reference/api_contract.md:595` | Vertrag sagt bereits „inklusive" → bestätigt die gewählte Richtung, kein Änderungsbedarf. |
| `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` | „ein Fenster, wirksam auf Anzeige und Bewertung" — der Fix stellt genau das her. |

## Tests, die heute das ALTE Verhalten festschreiben

| Test | Erwartung heute | Nach dem Fix |
|---|---|---|
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-2b (`:533-547`) | Gewitter 19:15 → **kein** Alarm | muss umgedreht werden (Alarm erwartet) |
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-5 (`:812-828`) | Ziel-Segment endet 19:00 UTC-konvertiert | Ende 20:00 |
| `tests/unit/test_alarm_zeitfenster_ziel.py` AC-3 (`:559`), Spätankunft (`:686`) | Ankunft 20:30 gilt als „nach Fensterende" | Kippkante verschiebt sich auf 20:00 |
| `tests/tdd/test_compare_alert_day_window.py::test_ac3b...stunde_19_liegt_ausserhalb` (`:509`) | Stunde 19 außerhalb | Stunde 19 innerhalb |
| `tests/tdd/test_compare_alert_day_window.py::test_ac8b...stunde_20_ausserhalb` (`:727`) | Stunde 20 außerhalb | bleibt gültig (Positivkontrolle für die neue Kante) |
| `tests/unit/test_destination_segment.py`, `tests/helpers/arrival_window_fixtures.py` | Ziel-Segment-Ende | prüfen, ggf. nachziehen |

## Dependencies

- **Upstream:** `resolve_configured_window()` (Stundenzahlen, Default 4/19, Wrap `start > end` gültig seit #1361), `tz_for_coords()`, Trip-`report_config` bzw. Compare-`preset`.
- **Downstream:** `segment_weather` (Aggregation je Segment), `weather_change_detection`/`trip_alert` (Abweichungs- und Radar-Alarme), `compare_alert_checks`, `compare_official_alert`, alle vier Kanäle über die gerenderte Ausgabe.

## Existing Specs

- `docs/specs/modules/fix_1584_alarm_zeitfenster.md` — enthält die abzulösende AC-2b („19:15 → kein Alarm"); braucht einen Nachtrag „abgelöst durch #1599".
- `docs/specs/modules/fix_1584c_compare_alarm_zeitfenster.md` — Known Limitations verweisen ausdrücklich auf diese offene Kante.
- `docs/adr/0035-ein-tagesfenster-fuer-trip-und-ortsvergleich.md` — Entscheidungsgrundlage.

## Risks & Considerations

1. **Randfall `end_hour = 23`:** `time(24)` existiert nicht. Die Grenze muss als „Fensterende + 1 h"
   **nach** der UTC-Konvertierung gebildet werden, nicht als `time(end_hour + 1)`.
2. **Sommerzeit:** `+1 h` erst auf dem UTC-Zeitstempel addieren, sonst kann eine Umstellungsnacht
   die Grenze verschieben.
3. **Mitternachts-Fenster (`start > end`, z. B. 22–2):** Trip-Ziel-Segment bildet das bewusst nicht ab
   (PO-Entscheidung 2026-08-08, Mindestfenster-Guard greift). Der Ortsvergleich behandelt es
   wrap-aware — beide Pfade müssen nach dem Fix weiterhin dieselbe Kante haben.
4. **Spätankunfts-Guard verschiebt sich:** Eine Ankunft um 19:30 fällt heute in den Mindestfenster-Zweig,
   nach dem Fix nicht mehr. Das ist gewollt, muss aber als eigener Testfall bewacht sein.
5. **Drei getrennte Umrechnungsstellen** sind der Grund, warum diese Kante überhaupt auseinanderlaufen
   konnte. Ein gemeinsamer Helfer in `app/day_window.py` (Stunden → halboffenes UTC-Intervall) verhindert
   die vierte Variante; ein Wächter-Test sollte das Auseinanderlaufen künftig fangen.
6. **Mehr Alarme am Abend:** Die Änderung erweitert das Alarmfenster um eine Stunde — gewollt
   (Abendgewitter am Tagesziel), aber im Zusammenspiel mit der Alarm-Entdopplung (#1467) zu beobachten.
7. **Vier Kanäle:** Wirkung ist die Alarm-Auslösung, nicht der Renderer — betrifft damit E-Mail,
   Telegram, SMS und Premium-SMS gleichermaßen.

## Analysis

### Type

Bug (nutzersichtbare Abweichung zwischen Anzeige und Alarm), mit einer Semantik-Festlegung als
Voraussetzung. **PO-Entscheidung 2026-08-17: Obergrenze inklusiv, Alarm zieht nach.**

### Auszählung der Klasse „Fenster-Stunde → Zeitrechnung" (vollständig)

Geprüft wurden Python (`src/`, `api/`), Go (`internal/`, `cmd/`) und Frontend; Go und Frontend
reichen die Stundenzahl nur durch (Persistenz + Klemmung), rechnen nie mit ihr.

| Stelle | Auslegung heute | Seite | Änderung |
|---|---|---|---|
| `src/services/trip_segments.py:266-297` | **exklusiv** | Alarm | ja |
| `src/services/compare_location_weather_source.py:110-152` | **exklusiv** | Alarm | ja |
| `src/services/compare_official_alert.py:303-311` | **exklusiv** | Alarm | ja |
| `src/services/comparison_engine.py:193-198` (`window_hours`) | inklusiv (`+1`) | Anzeige | nein |
| `src/services/notification_service.py:280-289` (`compute_has_gap`) | inklusiv (`range(_start, _end+1)`) | Anzeige | nein |
| `src/app/day_window.py:134-144` (`hour_in_window`) | inklusiv | Anzeige | nein |
| `src/output/renderers/day_window.py:140-180` | inklusiv | Anzeige | nein |
| `src/services/comparison_engine.py:45-90` | inklusiv | Anzeige | nein |

**Befund:** Die Anzeige-Seite liest durchgehend inklusiv; ausschließlich die drei Alarm-Stellen
fallen heraus. Die gewählte Richtung ist damit die einzige, die keine vierte Sonderregel schafft.

### Der Zielkonflikt: `end_time` trägt zwei Bedeutungen

`segment.end_time` des Ziel-Segments ist gleichzeitig (i) obere Fenstergrenze für Alarm und
Aggregation — dort **exklusiv** gelesen (`< end_floor`) — und (ii) „Tagesabschluss" für die Anzeige,
dort **inklusiv** als `.hour` gelesen. Eine Verschiebung auf 20:00 wirkt deshalb in beide Richtungen:

| Konsument | Wirkung der Verschiebung | Bewertung |
|---|---|---|
| `trip_alert.py:1007-1075` (Radar/Nowcast über `select_active_segment`, `trip_segments.py:340,379,387`) | Ziel-Segment bleibt bis 20:00 aktiv → Nowcast-Alarm um 19:30 feuert überhaupt erst | **gewollt, Kern des Fixes** |
| `trip_alert.py:1393` (Δ-Alarm Fresh-Fetch), `:1562` (amtliche Warnungen) | Segment gilt eine Stunde länger als „nicht vorbei" | **gewollt** |
| `weather_change_detection.py:304-310` (`_peak_occurred_at`) | Peak-Zeitfenster schließt Stunde 19 ein | **gewollt** |
| `email/helpers.py:146-159` + `trip_report.py:483` (`extract_hourly_rows`) | zusätzliche 20-Uhr-Zeile in der Ziel-Tabelle — die Tabelle liest die **ungefilterte** Reihe (`segment_weather.py:283-285`) | **Kollateralschaden** |
| `day_window.py:200-215` (`collect_hiking_window_points`, `is_last` inklusiv) | 20-Uhr-Punkt fließt in Mail-Kachelzeile, SMS und Telegram-Kurzübersicht (#1417) | **Kollateralschaden** |
| `trip_report.py:154-160` | Nacht-Block beginnt 20:00 statt 19:00 | **Kollateralschaden** |
| `email/plain.py:282`, `html.py:1175-1177,1224-1225` | Kopfzeile „Wetter am Ziel: 04:00–**20:00**" (Roh-Print) | **Kollateralschaden** |
| `email/plain.py:298`, `html.py:1293` | „Ankunft **20:00** → Morgen 06:00" | **Kollateralschaden** (verstärkt einen bestehenden Beschriftungsfehler: dort steht nie die echte Ankunft) |
| `weather_extractor.py:95` → `trip_command_processor.py:986` | Telegram-`/timeline` zeigt „Ankunft 20:00" | **Kollateralschaden** |

### Technical Approach

1. **Ein gemeinsamer Helfer** in `src/app/day_window.py` baut aus (Datum, `end_hour`, tz) die
   **exklusive** UTC-Obergrenze. Die `+1 h` wird **nach** der UTC-Konvertierung addiert — `time(24)`
   existiert nicht (`end_hour = 23`), und bei Addition in Lokalzeit könnte eine Umstellungsnacht die
   Grenze verschieben. Die drei Alarm-Stellen rufen nur noch diesen Helfer; damit gibt es genau eine
   Umrechnung statt drei.
2. **Anzeige-Invarianz statt globaler Umdeutung.** Eine pauschale Regel „Segment-Ende ist exklusiv"
   wäre falsch: normale Etappen enden zu krummen Zeiten (`trip_segments.py:107-230`, Quelle
   `arrival_override`/Naismith), und dort gehört die Ankunftsstunde bewusst dem **Folge**-Segment
   (Bug #806/#1146, sichtbar an der `is_last`-Sonderregel in `day_window.py:213`). Eine Umdeutung
   aller Segmente würde bei glatten Etappenzeiten eine Stunde doppelt zählen oder ganz verlieren.
   Stattdessen **eine** Hilfsfunktion „letzte zum Segment gehörende Stunde", die die Ziel-Sonderregel
   kennt (`segment_id == "Ziel"` ist der bereits etablierte Diskriminator, u. a. `plain.py:281`).
   Sichtbare Ausgabe bleibt damit **unverändert** — und Tabelle und Aggregat lesen erstmals dasselbe
   Intervall.
3. **Spätankunfts-Guard nachziehen** (`trip_segments.py:282-297`): Heute greift das Mindestfenster von
   1 h ab Ankunft ≥ 19:00. Mit der neuen Grenze griffe es erst ab 20:00 — eine Ankunft um 19:30 hätte
   nur noch 30 Minuten Überwachung statt garantiert 60. Der Guard muss deshalb auf „mindestens eine
   Stunde" statt „nur wenn das Fenster schon zu ist" umgestellt werden.
4. **ADR-0035 ergänzen:** Die Randstunden-Semantik fehlt dort — genau diese Lücke hat die Abweichung
   möglich gemacht. Ergänzung: „Die Obergrenze ist inklusiv; zeitlich `[start:00, (end+1):00)`."
   Die abgelöste AC-2b von #1584 bekommt einen Nachtrag.

### Scope Assessment

- Produktivcode: ~9 Dateien, geschätzt +80/-30 LoC
- Tests: mehrere hundert Zeilen (Vorbild `tests/unit/test_alarm_zeitfenster_ziel.py` = 852 Zeilen für
  denselben Gegenstand). **Das Test-Budget dominiert, nicht der Mechanismus.**
- Risk Level: **MEDIUM–HIGH** — kritischer Alarmpfad, viele Anzeige-Mitleser

### Umzuschreibende Bestandstests

`tests/unit/test_alarm_zeitfenster_ziel.py` (AC-2b 19:15 → dreht sich um; AC-3/AC-3b Spätankunft;
AC-5 Default-Ende), `tests/unit/test_destination_segment.py:101-135`,
`tests/tdd/test_compare_alert_day_window.py` (AC-3b Stunde 19; AC-8b Stunde 20 bleibt gültig als
Positivkontrolle), `tests/unit/test_day_window_gap_detection.py`.
Unberührt: `tests/tdd/test_compare_dispatch_fixed_window.py` und
`tests/tdd/test_daywindow_configurable.py` prüfen das **Stundenpaar** `(4, 19)`, das sich nicht ändert.

### Wächter gegen erneutes Auseinanderlaufen

- Helfer-Test mit **hart hinterlegten** Erwartungswerten (inkl. `end_hour = 23` und einem
  Umstellungstag) — kein Nachrechnen mit derselben Formel.
- Wirkungstest: Gewitter um 19:30 Ortszeit → Alarm wird **zugestellt** (nicht: `end_time` prüfen).
- Anzeige-Test: ein Datenpunkt um 20:00 darf in der Ziel-Tabelle **nicht** erscheinen.
- Untauglich: Trip-Ergebnis gegen Compare-Ergebnis vergleichen — beide rufen denselben Helfer, ein
  Fehler darin bricht beide Seiten gleich und der Vergleich bliebe grün.

### Open Questions

- [x] Randstunden-Semantik — PO-Entscheidung 2026-08-17: inklusiv
- [ ] Zuschnitt: ein Zug (LoC-Budget-Erhöhung nötig) oder zwei Scheiben?
