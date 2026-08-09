---
entity_id: fix_1651_vorschau_zeitfenster
type: bugfix
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "2.0"
tags: [gewitter, vorschau, zeitfenster, issue-1651]
---

<!-- Version 2.0 ersetzt die Fassung vom selben Tag vollstaendig. PO-Entscheidung
2026-08-09 (siehe Kommentar 2 an Issue #1651): nicht das Fenster BESCHRIFTEN,
sondern das Nachtgewitter tatsaechlich NENNEN — mit exakter Uhrzeit. Die alte
Fassung (Suffix " (Fenster 04-19 Uhr)") ist damit ueberholt und wird NICHT
uebernommen. -->

# #1651 — Gewitter außerhalb des Tagesfensters wird in der Mail genannt, mit Uhrzeit

> **Scheiben-Schnitt, PO-Entscheidung 2026-08-09 (nach dem TDD-RED).** Diese Spec
> deckt nur noch die **morgendliche „⚡ Gewitter-Vorschau"** ab. Der abendliche
> **Mehrtages-Ausblick** ist herausgelöst nach **#1653**, weil seine Gewitter-Zelle
> erst drei eigene, gemessene Fehler loswerden muss (Wort und Uhrzeit aus
> verschiedenen Zeiträumen; Tag oder Nacht verschwindet; rohe Programmnamen),
> bevor eine Nacht-Angabe sinnvoll darauf passt. Die rohen Programmnamen
> (`⚡MED`/`⚡HIGH` statt „mittel"/„hoch") laufen als eigene kleine Lieferung
> unter **#1654**. **AC-2 und AC-10 sind damit hierher nicht mehr anwendbar** —
> sie stehen unten als verschoben markiert und werden in #1653 neu gefasst.
>
> **Korrektur zu einer Annahme dieser Spec:** Der Satz „Telegram (rich) erfüllt die
> Vorgabe bereits" gilt **nicht allgemein**. Gemessen: Telegram zeigt den stärksten
> Wert über 24 Stunden mit dessen Uhrzeit und verschweigt dabei den jeweils
> schwächeren — bei Tag „mittel" 14:00 + Nacht „hoch" 00:00 erscheint `⚡hoch@0`,
> das Tagesgewitter fehlt. Behandelt in #1653.

## Approval

- [ ] Approved

## Purpose

Ein Gewitter **außerhalb** des konfigurierten Tagesfensters (Default 04–19 Uhr
Ortszeit) soll in der Trip-Mail **genannt werden, mit exakter Uhrzeit** — statt
wie heute verschwiegen zu werden. Betroffen ist in dieser Scheibe **eine** Stelle:
die morgendliche „⚡ Gewitter-Vorschau" (Fließtext-Satz), sichtbar in HTML **und**
Klartext. SMS zeigt die Angabe weiterhin nicht (Platzgrund, PO-Vorgabe).
Die abendliche „Mehrtages-Ausblick"-Tabelle und Telegram sind nach **#1653**
herausgelöst.

PO-Wortlaut (Kommentar 2 an Issue #1651, 2026-08-09):

> „Bei der SMS wird's einfach nicht angezeigt. Bei E-Mail und Telegram darf
> das Gewitter außerhalb des ‚Tagesfensters' natürlich schon erwähnt werden:
> In der Zusammenfassung z.B. mit Gewitter mit exakter Uhrzeit."

Die zentrale Zusicherung dieser Scheibe: der ursprüngliche #1498-Fehler darf
nicht in umgekehrter Form zurückkommen. Der Fehler war nicht „die Vorschau
erwähnt die Nacht", sondern: zwei verschiedene Datenquellen sagten für
**dieselbe Stunde** derselben Mail Widersprüchliches. Diese Scheibe stellt
sicher, dass die neue Nacht-Angabe für die Stunden, die auch die
„Nacht am Ziel"-Tabelle derselben Mail zeigt, aus **derselben** Quelle stammt.

## Source

- **File:** `src/app/day_window.py` — neue Funktion für die Nacht-Angabe
  (Fenster-Zugehörigkeit und Zusammenführung zweier Stundenquellen)
- **File:** `src/services/trip_report_scheduler.py` —
  `_thunder_entry_from_trend_row()`, `_build_thunder_forecast()`,
  `_build_thunder_forecast_from_trend_or_fetch()`, `_build_stage_trend()`,
  Hauptablauf (`generate_and_send`, Zeile ~875–902)
- **File:** `src/services/preview_service.py` — Reihenfolge der
  Nachtwetter-Beschaffung
(`src/output/renderers/email/outlook.py` war in Version 2.0 vorgesehen und ist
mit dem Scheiben-Schnitt nach #1653 herausgelöst.)

Schicht: **Python-Core** (`src/app/`, `src/services/`,
`src/output/renderers/`). Kein Go-, kein Frontend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.day_window.resolve_configured_window()` / `hour_in_window()` | vorhanden | Fenster-Grenzen und Zugehörigkeits-Prüfung — dieselbe Quelle, auf der auch die bestehende Tagesfenster-Klemmung (#1498 Fall 2) beruht |
| `services.segment_weather.fetch_night_weather()` | vorhanden | Liefert die Nacht-Zeitreihe (Ankunft heute → 06:00 Folgetag) — dieselbe Funktion, die auch die „Nacht am Ziel"-Tabelle speist; keine zweite Quelle |
| `TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch()` | vorhanden | Einziger Weg, über den sowohl Versand als auch Vorschau-Endpunkt den Vorschau-Eintrag beziehen — trägt die Parität aus AC-9 strukturell |
| `services.preview_service.py` | vorhanden | Bezieht Vorschau-Eintrag und Ausblick-Tabelle über dieselben Scheduler-Methoden wie der Versandpfad |
| `output/renderers/email/html.py:1323`, `plain.py:328` | vorhanden | Lesen ausschließlich `fc['text']` — keine Änderung nötig, die neue Nacht-Angabe erreicht beide automatisch, weil sie in `text` eingebaut wird |
| `output/renderers/sms_trip.py:473–483` | vorhanden | Liest nur `entry["level"]`/`entry["hour"]`, nicht `entry["text"]` — SMS bleibt strukturell unberührt |
| `output/renderers/narrow.py:571–586` (`_outlook_lines`, Telegram rich) | vorhanden | Liest `thunder_token` aus der **ungefilterten** `hourly_thunder`-Reihe der Etappe — zeigt Nachtgewitter bereits heute; wird von dieser Scheibe nicht angefasst |

## Scope

### Affected Files

| File | Change Type | Description |
|---|---|---|
| `src/app/day_window.py` | MODIFY | Neue Funktion, die aus zwei Stundenreihen (eigene Etappen-Zeitreihe + optional Nacht-Zeitreihe) die außerhalb des Fensters liegenden Stunden bestimmt und daraus Level+früheste Stunde ableitet (Implementation Details) |
| `src/services/trip_report_scheduler.py` | MODIFY | Neuer optionaler `night_weather`-Parameter an `_build_thunder_forecast_from_trend_or_fetch()`, `_thunder_entry_from_trend_row()`, `_build_thunder_forecast()`; Suffix-Anhängen an `text`; `_build_stage_trend()` bekommt denselben optionalen Parameter und setzt `row["night_thunder"]`; Hauptablauf reicht das bereits vorhandene `night_weather` an beide Aufrufe durch |
| `src/services/preview_service.py` | MODIFY | Nachtwetter-Beschaffung (aktuell nach dem Trend-/Vorschau-Aufbau) nach vorne verschoben, analog zum Versandpfad, damit sie beim Bau von Trend und Vorschau bereits vorliegt |
| ~~`src/output/renderers/email/outlook.py`~~ | — | **verschoben nach #1653** |
| `tests/unit/test_thunder_forecast_day_window.py` | MODIFY | Bestehende Tests zur Fenster-Klemmung um die neue Nacht-Angabe ergänzen |
| `tests/tdd/test_thunder_forecast_low_level.py` | MODIFY | dito für die LOW-Stufe |
| `tests/tdd/test_briefing_parity_night_thunder.py` | MODIFY | Bereits vorhandene Fixtures (`_thunder_forecast()`, `_night_weather()`, `_night_dp()`) sind direkt wiederverwendbar — neue Tests für die Kombination Vorschau + Nacht-Tabelle in derselben Mail |
| `tests/tdd/test_bug_874_th_plus_sms.py` | MODIFY | Regressionsnachweis: SMS-Token unverändert trotz Nacht-Angabe im `text`-Feld |
| `tests/unit/test_trip_report_formatter_v2.py` | MODIFY | Erwarteter Vorschau-Text ggf. anpassen, falls dort ein Nachtgewitter-Fixture verwendet wird |
| `tests/golden/email/corsica-vigilance-html.txt`, `corsica-vigilance-plain.txt`, `gr20-spring-morning-html.txt`, `gr20-spring-morning-plain.txt` | MODIFY | Golden-Snapshots neu ziehen, sofern der Fixture-Trip ein Nachtgewitter zeigt |
| neue Testdatei (Name nach Verhalten, z.B. `tests/unit/test_thunder_night_addendum.py`) | CREATE | Gezielte Tests für die neue Helper-Funktion in `app/day_window.py` (Merge-Logik, Mehrere-Nachtstunden-Regel, +2 ohne Nacht-Tabelle) |

### Estimated Changes

Siehe Abschnitt „Umfang" — die ehrliche Schätzung liegt über dem
250-Zeilen-Workflow-Limit.

## Implementation Details

### 1. Wo die zwei Quellen für dieselbe Stunde herkommen (gemessen)

`night_weather` (Nacht-Tabelle) deckt Ankunft **heute** bis **06:00 des
Folgetags** ab (`segment_weather.py::fetch_night_weather`, Zeile 410–460).
Der Vorschau-Eintrag für „+1" (morgen) stammt aus einem **anderen** Abruf —
entweder der bereits gebauten `multi_day_trend`-Zeile (Trend-Weg,
`_thunder_entry_from_trend_row`) oder einem eigenen Fallback-Fetch
(`_build_thunder_forecast`). Für die Stunden **00:00–06:00 des Folgetags**
behaupten damit zwei verschiedene Quellen etwas über dieselbe Stunde — genau
die Konstellation, die den ursprünglichen #1498-Fehler erzeugt hat.

**Auflösung (Regel dieser Scheibe):** Für Stunden, die `night_weather`
abdeckt (00:00–06:00 des Folgetags), ist `night_weather` die maßgebliche
Quelle — sie ist dieselbe Quelle, welche die „Nacht am Ziel"-Tabelle direkt
neben der Vorschau zeigt. Für alle anderen außerhalb des Fensters liegenden
Stunden (z.B. 20:00–23:00 desselben Folgetags, und der gesamte Folge-Tag
„+2", den `night_weather` nicht erreicht) gilt die **eigene**, bereits
vorliegende Zeitreihe der jeweiligen Etappe — dieselbe Reihe, aus der auch
die Telegram-„Ausblick"-Bubble ihr `thunder_token` bezieht
(`narrow.py::_outlook_lines`, liest bereits ungefiltert). Kein neuer
Netzabruf nötig: beide Reihen liegen an allen drei Bauwegen bereits vor.

### 2. Neue Helper-Funktion (`app/day_window.py`)

```python
def night_addendum(
    own_hourly: list[tuple[int, "ThunderLevel"]],
    night_hourly: list[tuple[int, "ThunderLevel"]] | None,
    win_start: int,
    win_end: int,
) -> tuple["ThunderLevel", int] | None:
    """Level + fruehste Stunde des schlimmsten Gewitters AUSSERHALB des
    Fensters. `night_hourly` (falls gegeben) ueberschreibt `own_hourly` fuer
    Stunden, die es abdeckt (Autoritaet der Nacht-Tabellen-Quelle)."""
```

`own_hourly`/`night_hourly` sind `(Ortszeit-Stunde, ThunderLevel)`-Paare aus
den jeweils bereits vorhandenen, ungefilterten Zeitreihen. Die Funktion:
merged beide (Nacht-Quelle gewinnt bei überlappender Stunde), filtert auf
`not hour_in_window(hour, win_start, win_end)`, ermittelt das Maximum-Level
über `thunder_ordinal()` und davon die früheste Stunde — spiegelbildlich zur
bestehenden Innerhalb-Fenster-Logik in `_thunder_entry_from_trend_row`. Kein
Level (nur `NONE` außerhalb) → `None` (kein Zusatz).

### 3. Integration Vorschau-Satz (Morgen-Default, Fetch-Weg + Trend-Weg)

`_build_thunder_forecast_from_trend_or_fetch()` bekommt einen neuen
optionalen Parameter `night_weather: Optional[NormalizedTimeseries] = None`
und reicht ihn an `_thunder_entry_from_trend_row()` bzw.
`_build_thunder_forecast()` durch (nur für den „+1"-Eintrag relevant, „+2"
bekommt `night_hourly=None`). Beide Methoden rufen `night_addendum()` auf
und hängen bei einem Treffer
`f", nachts {STUFE} ab {hour:02d}:00"` an den bestehenden `text` an — der
bisherige Text (inkl. Fenster-Klemmung) bleibt unverändert, das ist ein
reiner Anhang.

**Die Stufe wird genannt (PO-Entscheidung 2026-08-09).** Wortschatz:

| Level | Nacht-Zusatz |
|---|---|
| LOW | `, nachts leichtes Gewitter ab HH:MM` |
| MED | `, nachts mittleres Gewitter ab HH:MM` |
| HIGH | `, nachts starkes Gewitter ab HH:MM` |

Bewusste Abweichung vom Tagestext: dort trägt MED **kein** Adjektiv
(„Gewitter möglich ab HH:MM"). Der Nacht-Zusatz nennt alle drei Stufen, weil
er als angehängter Halbsatz für sich lesbar sein muss — ein „nachts Gewitter"
ohne Adjektiv wäre von „Stufe unbekannt" nicht unterscheidbar.

Beispiele:
- gemessenes #1651-Szenario (kein Gewitter im Fenster, HIGH um 00:00):
  `"Kein Gewitter erwartet, nachts starkes Gewitter ab 00:00"`
- Tag und Nacht gemeinsam (angehängt, nicht ersetzt):
  `"Starkes Gewitter erwartet ab 14:00, nachts mittleres Gewitter ab 22:00"`

Hauptablauf (`generate_and_send`): `night_weather` ist an Zeile ~876–878
bereits vorhanden — wird unverändert an `_build_thunder_forecast_from_trend_or_fetch()`
(Zeile ~900) sowie an `_build_stage_trend()` (Zeile ~889, s.u.) durchgereicht.

### 4. Integration Ausblick-Tabelle (Abend-Default) — VERSCHOBEN NACH #1653

Der folgende Abschnitt ist mit dem Scheiben-Schnitt vom 2026-08-09 nicht mehr
Teil dieser Spec. Er bleibt als Vorarbeit stehen, ist aber in #1653 neu zu
fassen — die dort gemessenen Altfehler der Zelle ändern den Entwurf.

`_build_stage_trend()` bekommt denselben optionalen `night_weather`-Parameter.
Nach dem Bau jeder Zeile über `build_outlook_row()` (die bereits ungefilterte
`hourly_thunder`-Samples liefert) wird geprüft, ob `row["date"] ==
target_date + 1 Tag` — nur dann wird `night_weather` als zweite Quelle an
`night_addendum()` übergeben, sonst nur die eigene Reihe. Bei einem Treffer
bekommt die Zeile ein neues additives Feld `row["night_thunder"] = (level,
hour)`.

`render_outlook_table()` (HTML) und `render_outlook_plain()` (Klartext)
lesen `stage.get("night_thunder")` und hängen an die bestehende „Gew"-Zelle
an: ist die Zelle bislang „–"/„⚡–" (kein Tages-Gewitter), wird sie durch
`"nachts {STUFE} HH:MM"` (HTML) bzw. `"⚡ nachts {STUFE} HH:MM"` (Klartext,
Symbol-Konvention aus `_THUNDER_MAP` übernommen) **ersetzt** statt ergänzt —
ein Bindestrich gefolgt von einer Uhrzeit wäre irreführend. Zeigt die Zelle
bereits ein Tages-Gewitter, wird `" nachts {STUFE} HH:MM"` angehängt.

`{STUFE}` in der Tabelle nutzt den **kurzen** Wortschatz, den die Spalte
bereits führt (`THUNDER_LABEL_DE`: `leicht`/`mittel`/`hoch`) — nicht die
langen Adjektive des Fließtexts. Beispiel: `⚡ nachts hoch 00:00`.

### 5. Reihenfolge UND Bedingung in `preview_service.py`

**5a — Reihenfolge.** Der Vorschau-Pfad beschafft `night_weather` aktuell
**nach** dem Bau von Trend und Vorschau-Eintrag (Zeile 218–220 vs. 198–202;
nachgemessen 2026-08-09). Damit die neue Nacht-Angabe auch im
Vorschau-Endpunkt erscheint (AC-9, Parität), wird die Beschaffung vor die
Aufrufe von `_build_stage_trend()`/
`_build_thunder_forecast_from_trend_or_fetch()` verschoben — reine
Umstellung, kein neuer Netzabruf.

**5b — 🔴 Die Bedingungen der beiden Pfade sind NICHT gleich (nachgemessen).**
Reihenfolge allein genügt nicht:

| Pfad | Bedingung für den Nachtwetter-Abruf |
|---|---|
| Versand, `trip_report_scheduler.py:875-877` | `if segment_weather:` — praktisch immer |
| Vorschau, `preview_service.py:219` | zusätzlich `night_weather_needed(trip.display_config)` |

`night_weather_needed()` (`segment_weather.py`) liefert heute nur dann `True`,
wenn die **Nacht-Stundentabelle** (`show_night_block`) oder die
**Nacht-Tiefsttemperatur** (`temperature_night`) aktiv ist. Für einen Trip
**ohne** Nacht-Tabelle hätte der Versand also die Nacht-Zeitreihe, die
Vorschau nicht — beide bildeten die Nacht-Angabe aus **verschiedenen**
Quellen, und AC-9 bräche genau dort.

Besonders tückisch: Testfixtures mit aktiver Nacht-Tabelle bleiben dabei
grün; der Fehler zeigt sich nur im echten Pfad. Das ist die Fehlerklasse
„Prüfort ≠ Wirkort".

**Auflösung:** `night_weather_needed()` wird um die Bedingung erweitert, dass
auch eine aktive **Gewitter-Metrik** Nachtdaten nötig macht — denn ab dieser
Scheibe speisen sie zusätzlich die Nacht-Angabe. Die Funktion bleibt damit
die **eine geteilte Entscheidung** für beide Pfade (so ist sie ausdrücklich
gedacht, siehe ihr Docstring), statt dass der Vorschau-Pfad eine eigene
Sonderregel bekommt.

**Folge fürs Kontingent, bewusst in Kauf genommen:** Trips mit
Gewitter-Metrik, aber ohne Nacht-Tabelle, holen im Vorschau-Pfad künftig
zusätzlich die Nacht-Zeitreihe. Der Versand tat das ohnehin schon; es
entsteht kein neuer Abruf im Versand, nur eine Angleichung der Vorschau.

### Offene Punkte — hiermit entschieden

1. **Spaltenbreite:** Die „Gew"-Spalte ist eine Tabellenzelle ohne feste
   Zeichenbreite (HTML: `<td>` mit `padding`, kein `white-space:nowrap`;
   Klartext-Ausblick fügt ohnehin keine feste Spaltenbreite durch, s.
   `render_outlook_plain`). „nachts 02:00" passt ohne Layoutbruch.
2. **Mehrere Nachtstunden:** früheste Stunde des **erreichten
   Höchst-Levels** über alle außerhalb liegenden Stunden hinweg (00:00–03:59
   UND 20:00–23:59 zusammen als ein Pool) — spiegelbildlich zur
   bestehenden Innerhalb-Fenster-Regel. Beispiel: MED um 02:00 UND HIGH um
   22:00 → „nachts starkes Gewitter ab 22:00" (HIGH gewinnt, dessen früheste
   Stunde).
3. **Level-Angabe: MIT Stufen-Wort** — PO-Entscheidung 2026-08-09, nachdem
   auffiel, dass ohne Stufe zusammen mit Regel 2 beide Informationen
   verlorengehen (bei MED um 02:00 und HIGH um 22:00 bliebe nur „nachts
   Gewitter ab 22:00" — weder die Schwere noch das frühere Ereignis wären
   erkennbar). Wörtlich: `", nachts starkes Gewitter ab HH:MM"` (Fließtext,
   Adjektive `leichtes`/`mittleres`/`starkes`) bzw. `"nachts hoch HH:MM"`
   (Ausblick-Tabelle, Kurzwortschatz `leicht`/`mittel`/`hoch`).
4. **„+2" ohne Nacht-Tabellen-Gegenquelle:** die Angabe erscheint dort
   trotzdem (PO will die Information generell zeigen, nicht nur dort, wo ein
   Widerspruchsrisiko besteht) — Quelle ist ausschließlich die eigene,
   bereits vorliegende Zeitreihe der „+2"-Etappe.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (Kernszenario Morgen, GIVEN Default-Fenster, kein Gewitter im
  Fenster, HIGH um 00:00 in `night_weather` WHEN der Vorschau-Eintrag gebaut
  wird THEN lautet `entry["text"]` „Kein Gewitter erwartet, nachts starkes
  Gewitter ab 00:00").
- [x] ~~Test 2 (Kernszenario Abend)~~ — **verschoben nach #1653**.
  ~~(GIVEN derselbe Fall WHEN die
  Ausblick-Tabelle für denselben Tag gebaut wird THEN zeigt die
  „Gew"-Zelle „nachts hoch 00:00" statt „–"/„⚡–".)~~
- [ ] Test 3 (Konsistenz mit Nacht-Tabelle, GIVEN dieselbe zugestellte Mail
  WHEN sowohl die Nacht-Tabellen-Zeile 00:00 als auch die neue Nacht-Angabe
  gelesen werden THEN nennen beide dieselbe Stunde und dasselbe Level).
- [ ] Test 4 (Tag + Nacht kombiniert, GIVEN HIGH ab 14:00 im Fenster UND MED
  um 22:00 außerhalb WHEN der Eintrag gebaut wird THEN lautet der Text
  „Starkes Gewitter erwartet ab 14:00, nachts mittleres Gewitter ab 22:00").
- [ ] Test 5 (Keine Änderung ohne Nachtgewitter, GIVEN ruhige Nacht UND
  ruhiger Tag WHEN der Eintrag gebaut wird THEN bleibt der Text „Kein
  Gewitter erwartet" ohne Zusatz).
- [ ] Test 6 (+2 ohne Gegenquelle, GIVEN Gewitter außerhalb des Fensters am
  übernächsten Tag WHEN der Eintrag für „+2" gebaut wird THEN erscheint die
  Nacht-Angabe trotzdem, aus der eigenen Zeitreihe).
- [ ] Test 7 (Mehrere Nachtstunden, GIVEN MED um 02:00 UND HIGH um 22:00
  WHEN der Eintrag gebaut wird THEN wird ausschließlich „nachts starkes Gewitter ab 22:00" genannt).
- [ ] Test 8 (SMS unverändert, GIVEN ein Eintrag mit gesetzter Nacht-Angabe
  im `text`-Feld WHEN der SMS-Renderer das TH+-Token baut THEN bleibt das
  Token unverändert — liest weiterhin nur `level`/`hour`).
- [ ] Test 9 (Parität Vorschau-Endpunkt ↔ zugestellte Mail, GIVEN derselbe
  Trip und Zieltag WHEN der Eintrag einmal über `preview_service.py` und
  einmal über den Versandpfad gebaut wird THEN ist `entry["text"]"
  zeichengleich).

## Acceptance Criteria

- **AC-1 (Kernszenario Morgen — das gemessene #1651-Szenario):** Given ein
  Trip mit Default-Tagesfenster (04–19 Uhr), am Folgetag kein Gewitter
  innerhalb dieses Fensters, aber ein Gewitter der Stufe „hoch" um 00:00 Uhr
  (dieselbe Stunde, die auch die Nacht-Tabelle derselben Mail zeigt) / When
  die morgendliche Trip-Mail erzeugt wird / Then steht in der Gewitter-
  Vorschau-Zeile für diesen Tag der Satz „Kein Gewitter erwartet, nachts
  starkes Gewitter ab 00:00" statt der bisherigen reinen Entwarnung ohne
  Nacht-Hinweis.

- **AC-2 — VERSCHOBEN NACH #1653, in dieser Scheibe nicht anwendbar.**
  ~~Given derselbe Trip und Tag wie AC-1 / When
  die abendliche Trip-Mail mit aktivem Mehrtages-Ausblick erzeugt wird /
  Then zeigt die Spalte „Gew" für diesen Tag „nachts hoch 00:00" (HTML) bzw.
  „⚡ nachts hoch 00:00" (Klartext) statt der bisherigen Entwarnung „–"/„⚡–" —
  in beiden Mail-Teilen (HTML und Klartext) derselben Mail.~~

- **AC-3 (Konsistenz mit der Nacht-Tabelle — zentrale #1498-Zusicherung):**
  Given ein Trip, dessen „Nacht am Ziel"-Tabelle für 00:00 des Folgetags ein
  Gewitter der Stufe „hoch" zeigt / When dieselbe Mail sowohl die
  Nacht-Tabelle als auch die neue Vorschau- bzw. Ausblick-Nacht-Angabe
  enthält / Then nennen beide Stellen exakt dieselbe Stunde und dasselbe
  Level — es entsteht keine widersprüchliche Aussage über dieselbe Stunde
  in derselben Mail.

- **AC-4 (Tages- und Nachtgewitter gemeinsam):** Given ein Trip mit
  Gewitter der Stufe „hoch" ab 14:00 Uhr innerhalb des Fensters UND
  zusätzlich Gewitter der Stufe „mittel" um 22:00 Uhr außerhalb des
  Fensters am selben Tag / When die Trip-Mail erzeugt wird / Then nennt der
  Satz beide Ereignisse: „Starkes Gewitter erwartet ab 14:00, nachts
  mittleres Gewitter ab 22:00" — die Tages-Aussage bleibt unverändert, die
  Nacht-Angabe wird angehängt und nennt ihre eigene Stufe.

- **AC-5 (Keine Änderung ohne Nachtgewitter — Regressionsschutz):** Given
  ein Trip ohne jedes Gewitter (weder im Fenster noch außerhalb) am
  Folgetag / When die Trip-Mail erzeugt wird / Then bleibt der Text „Kein
  Gewitter erwartet" unverändert, ohne angehängte Nacht-Angabe.

- **AC-6 (Übernächster Tag ohne Nacht-Tabellen-Gegenquelle):** Given ein
  Trip mit Gewitter außerhalb des Fensters am übernächsten Tag („+2", für
  den es keine „Nacht am Ziel"-Tabelle in derselben Mail gibt) / When die
  Trip-Mail erzeugt wird / Then erscheint die Nacht-Angabe für „+2"
  trotzdem, aus der für diesen Tag ohnehin bereits beschafften Zeitreihe —
  kein neuer Netzabruf.

- **AC-7 (Mehrere Nachtstunden — früheste Stunde des Höchst-Levels):**
  Given Gewitter der Stufe „mittel" um 02:00 Uhr UND der Stufe „hoch" um
  22:00 Uhr, beide außerhalb des Fensters am selben Tag / When der Satz
  gebaut wird / Then wird ausschließlich das höhere Level mit seiner
  frühesten Stunde genannt: „nachts starkes Gewitter ab 22:00" — nicht
  02:00, und die genannte Stufe ist die höhere („starkes"), nicht die des
  früheren Ereignisses.

- **AC-8 (SMS und Telegram-Kurzform bleiben unverändert —
  Regressionsschutz):** Given ein Trip-Report mit einer neu angehängten
  Nacht-Angabe im Vorschau-Text / When der Report für SMS oder die
  Telegram-Kurzform gerendert wird / Then bleibt das TH+-Token unverändert
  gegenüber dem Stand vor dieser Scheibe — es liest weiterhin
  ausschließlich `level`/`hour`, nie den Fließtext.

- **AC-9 (Parität Vorschau-Endpunkt ↔ zugestellte Mail):** Given derselbe
  Trip und derselbe Zieltag / When der Vorschau-Satz einmal über den
  Vorschau-Endpunkt (`preview_service.py`) und einmal über die tatsächlich
  zugestellte Trip-Mail erzeugt wird / Then ist der Satz an beiden Stellen
  zeichengleich, weil beide Wege dieselbe Scheduler-Methode durchlaufen und
  `night_weather` an beiden Stellen in derselben Reihenfolge vorliegt.

- **AC-11 (Parität auch ohne Nacht-Tabelle — die Falle aus 5b):** Given ein
  Trip, dessen Gewitter-Metrik aktiv ist, der aber **keine** Nacht-Tabelle
  anzeigt (`show_night_block` aus, Nacht-Tiefsttemperatur nicht gewählt),
  und der am Folgetag ein Gewitter außerhalb des Tagesfensters hat / When
  derselbe Tag einmal über den Vorschau-Endpunkt und einmal über die
  zugestellte Mail erzeugt wird / Then nennen beide dieselbe Nachtstunde —
  der Vorschau-Pfad greift auf dieselbe Nacht-Zeitreihe zu wie der Versand,
  statt still auf eine andere Quelle auszuweichen.

- **AC-10 — VERSCHOBEN NACH #1653, in dieser Scheibe nicht anwendbar.**
  Die Annahme dahinter ist zudem widerlegt: Telegram zeigt den 24-Stunden-
  Höchstwert und verschweigt den jeweils schwächeren von Tag und Nacht.
  ~~Given ein Trip mit
  Nachtgewitter außerhalb des Fensters / When die Telegram-„Ausblick"-Bubble
  gerendert wird / Then bleibt ihre Darstellung (z.B. „⚡H@2") gegenüber
  dem Stand vor dieser Scheibe unverändert — sie zeigt Nachtgewitter bereits
  heute über ihre eigene, ungefilterte Quelle.~~

## Umfang

**Neu bemessen nach dem TDD-RED und dem Scheiben-Schnitt vom 2026-08-09.**

Die Schätzung der Version 2.0 (~335–405 Zeilen) war um etwa das Dreifache zu
niedrig: der Entwickler brauchte für die elf Kriterien **994 Zeilen Testcode**,
weil die beiden Paritäts-Prüfungen (AC-9, AC-11) den echten Versand- **und** den
echten Vorschau-Pfad fahren statt einen nachgebauten. Zusammen mit dem
Produktivcode lag der Workflow bei rund **1180 Zeilen** — weit über den vom PO
freigegebenen 500.

**Folge (PO-Entscheidung):** Der Abend-Teil ist nach #1653 herausgelöst, die
rohen Programmnamen nach #1654. In dieser Scheibe verbleiben:

| Teil | geschätzt |
|---|---|
| Produktivcode (`day_window.py`, `trip_report_scheduler.py`, `preview_service.py`) | ~150 |
| Tests: `test_thunder_night_addendum.py` + `test_thunder_night_addendum_parity.py` | ~713 |
| entfällt: `test_outlook_night_thunder_cell.py` (281 Z.) | → #1653 |

Damit bleibt der Workflow weiterhin über 250, aber innerhalb der bereits
gesetzten Grenze von 500 nur bei den Produktivzeilen — der Testanteil überschreitet
sie. **Das ist bewusst so und vom PO getragen:** die Paritäts-Prüfungen sind der
eigentliche Schutz gegen einen Rückfall in #1498 und werden nicht gekürzt.
Reicht das Limit beim Commit nicht, wird es angehoben, nicht der Test gekürzt.

## Nicht in dieser Scheibe

- **Die „Metriken-Überblick"-Pille** (`helpers.py:1686-1730`, „Gewitter ab
  HH:MM · stärkste HH:MM") — dieselbe Fensterlosigkeit, aber ein eigener
  Sachverhalt, wird getrennt verbucht.
- **Hagel-Zusatz für die Nacht-Angabe** — der bestehende Hagel-Hinweis
  (`format_hail_note`) bleibt ausschließlich an das Tagesfenster-Ergebnis
  gekoppelt; die neue Nacht-Angabe trägt keinen eigenen Hagel-Zusatz (Scope-
  Begrenzung, kein fachlicher Verlust — Hagel ist ein Zusatzhinweis, kein
  Kernwert).
- **Die Tagesfenster-Klemmung selbst** — der Fix aus #1530 (Tages-Text
  behauptet keine Nachtstunden mehr) bleibt unverändert bestehen; diese
  Scheibe ergänzt nur additiv.
- **Die dokumentierte Restgrenze 04–06 Uhr aus #1530** — bleibt unverändert
  bestehen, wird durch die `night_weather`-Autorität für 00:00–06:00 in
  dieser Scheibe implizit mit erledigt (dieselbe Quelle wie die
  Nacht-Tabelle), aber nicht gesondert nachgewiesen.

## Risiko

Die Änderung ist additiv (neues Suffix, neues Zeilen-Feld) und rührt weder
an der Level-Berechnung innerhalb des Fensters noch an Alarm-/Versandlogik —
kein neuer Alarm entsteht, keiner entfällt. Das Hauptrisiko liegt in der
Reihenfolge-Änderung in `preview_service.py` (Nachtwetter-Beschaffung nach
vorne verschoben) — ein Fehler dort würde sich als fehlende oder doppelte
Nacht-Beschaffung zeigen, nicht als falscher Text; Test 9 (Parität) deckt
das ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung einer bestehenden Formatierungs-/Aggregations-
  stelle um eine zusätzliche, additive Quellen-Zusammenführung. Berührt
  keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie) im Sinne von `docs/adr/README.md`.

## Changelog

- 2026-08-09: Version 2.0 — vollständige Neufassung nach PO-Entscheidung
  (Kommentar 2 an Issue #1651): Nachtgewitter wird GENANNT statt das
  Zeitfenster nur beschriftet. Ersetzt Version 1.0 (Suffix-Ansatz)
  vollständig.
- 2026-08-09: Initial spec created (Version 1.0, überholt). Bezug: Issue
  #1651, Vorgänger #1530/#1498.
