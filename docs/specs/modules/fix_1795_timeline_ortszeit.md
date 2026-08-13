---
entity_id: fix_1795_timeline_ortszeit
type: module
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [bug, zeitzonen, telegram, adr-0044]
workflow: fix-1795-timeline-ortszeit
---

# Fix #1795 — Timeline und Query-Familie folgen der Ortszeit der Tour

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-13

## Purpose

Die Query-Familie (`glance`, `heute_gewitter`, `timeline_heute`, `timeline_morgen`, `heute`,
`morgen`) bestimmt ihren Kalendertag über den **UTC-Tag** der eingehenden Nachricht
(`trip_command_processor.py:503-504`, `received_at.date()`) statt über den Ortstag der Tour
(ADR-0044), und die Timeline zeigt Ankunftszeiten **roh in UTC** (`:948`, `:950`) statt in der
Ortszeit des jeweiligen Wegpunkts. Diese Scheibe stellt **beides gemeinsam** um, weil Filter und
Anzeige heute konsistent UTC sind — ein halber Fix erzeugt zwei widersprüchliche Zeitbegriffe in
derselben Nachricht (ADR-0051, s. „Warum eine Scheibe und kein Schnitt"). Herausgeschnitten aus
#1727 S5a mit ausdrücklicher Begründung
(`docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md:105-113`).

## Source

- **File:** `src/services/trip_command_processor.py`
  **Identifier:** `_handle_query` (:499-564), `_trigger_on_demand` (:566-596), `_aggregate_day`
  (:808-...), `_fmt_glance` (:879-896), `_fmt_gewitter` (:898-929), `_fmt_timeline` (:931-978),
  `_timeline_buttons` (:980-1005), `_fetch_and_save_snapshot` (:274-306),
  `_on_demand_failure_body` (:240-267)
- **File:** `src/services/trip_report_scheduler.py`
  **Identifier:** `send_on_demand_report` (:922-948), `_send_trip_report_outcome` (:977-1043)
- **Zonen-Auflösung (unverändert nutzen):** `src/services/trip_day.py::trip_local_now` (:74-88),
  `display_tz` (:45-52); `src/utils/timezone.py::local_fmt` (:119-121)

## Estimated Scope

- **LoC:** Produktivcode ≈ **+100/−35** (`trip_command_processor.py` +73/−29,
  `trip_report_scheduler.py` +27/−6); Testcode ≈ **760** (neue Suite ~650, Bestandsreparaturen
  ~110); **Gesamt ≈ 900 gezählte Zeilen**.
  **LoC-Override 1000** (statt Limit 250) — begründet: die Sommerzeit-Pflicht aus ADR-0044
  verlangt beide Wechseltage geprüft auf Stundenebene, dazu drei Bestandsfixturen, die durch die
  Tag-Umstellung rot werden (s. AC-9), und zwei Vertragslisten-Aufrufer des Rückgabetyps. #1727
  S5a — die direkte Vorgängerscheibe mit vergleichbarem Muster — lag bei 848 gezählten Zeilen und
  brauchte trotzdem zwei nachträgliche Wächter-Anpassungen durch Adversary-Nachforderungen; der
  Puffer auf 1000 ist keine Bequemlichkeit, sondern eine gemessene Reserve.
- **Files:** 10 (2 Produktivdateien MODIFY, 1 neue Testdatei CREATE, `tests/tdd/conftest.py`
  MODIFY, 3 Bestandstestdateien MODIFY zum Einfrieren von Fixturen, 2 Testdateien MODIFY wegen
  Rückgabetyp-Änderung, 1 ADR MODIFY — zählt nicht auf LoC)
- **Effort:** high — kritischer Pfad (jeder Telegram-/Mail-Befehl der Query-Familie), breite
  Anzeigeänderung, Persistenz-Anteil (Anker-Schlüssel), zwei Bestands-Wächter mit harten
  strukturellen Auflagen (s. u.)

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `_handle_query` (eine Auflösung, zwei Zonen), `_trigger_on_demand`, `_aggregate_day` (4 Aufrufstellen), `_fmt_glance`, `_fmt_gewitter`, `_fmt_timeline`, `_timeline_buttons` |
| `src/services/trip_report_scheduler.py` | MODIFY | `OnDemandErgebnis`-NamedTuple, `send_on_demand_report`, optionaler `target_date`-Parameter an `_send_trip_report_outcome` |
| `tests/tdd/test_timeline_folgt_der_ortszeit.py` | CREATE | Neue Suite, Verhaltensname statt Issue-Nummer |
| `tests/tdd/conftest.py` | MODIFY | `_anker()`-Helfer heben (Vorbedingungs-Anker, aus `test_befehlspfade_folgen_ortszone.py`) |
| `tests/tdd/test_befehlspfade_folgen_ortszone.py` | MODIFY | Altnutzer des gehobenen `_anker()` nachziehen (Import statt lokaler Kopie) |
| `tests/tdd/test_thunder_origin_four_places.py` | MODIFY | Fixtur `kommando` einfrieren (`:206-236`) |
| `tests/tdd/test_thunder_origin_trip.py` | MODIFY | Fixtur einfrieren (`:192-219`) |
| `tests/tdd/test_issue_1007_heute_voll_briefing.py` | MODIFY | `date.today()` an sieben Stellen einfrieren (`:248`, `:280`, `:294`, `:322`, `:343`, `:365-366`, `:397`, `:446`) |
| `tests/tdd/test_briefing_slot_idempotenz.py` | MODIFY | Vertragsliste (`:1087`) auf `.outcome`/`OnDemandErgebnis` nachziehen |
| `tests/tdd/test_issue_1087_trip_official_alerts.py` | MODIFY | Aufrufstelle auf `.outcome` nachziehen |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | Restliste nachziehen (zählt nicht auf LoC) |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `services.trip_day.trip_local_now(trip, now_utc)` | module function | EINE Zonen-Auflösung für Ortstag UND Ortsstunde beider Query-Tage (heute/morgen) |
| `services.trip_day.display_tz(trip, day_date)` | module function | Anzeige-Zone je Tag — heute/morgen können unterschiedliche Zonen tragen (AC-4) |
| `utils.timezone.local_fmt(dt, tz)` | module function | Ersetzt die rohe `f"{p.arrival_time:%H:%M}"`-Formatierung in `_fmt_timeline` (`:948`, `:950`) |
| ADR-0044 (Akzeptiert) | decision | Verlangt Ortstag statt UTC-Tag; `_handle_query` steht dort namentlich unter „Noch nicht umgesetzt" |
| ADR-0051 Regel 3 (Vorgeschlagen) | decision | Verbietet Systemuhr-Default — `tz`/`now_utc` werden an allen berührten Funktionen als Pflichtparameter hereingereicht |
| `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md` | spec | Vorgänger-Scheibe, grenzt `_handle_query` ausdrücklich aus (`:105-113`), liefert das Pflichtparameter-Muster |
| `tests/tdd/test_befehlspfade_folgen_ortszone.py::test_befehlspfade_folgen_dem_parameter_nicht_der_systemuhr` (`:517-670`) | test | Vorlage gegen „Parameter behalten, im Rumpf ignorieren" (S5a Adversary-Befund F001), Grundlage für AC-6 |
| `tests/test_success_status_guard.py:1622-1632`, `:1839`, `:1930` | guard | Bindet `_handle_query` an vier `success=True`-Literale in fester Reihenfolge — Auflage: Funktion nicht zerlegen |
| `tests/test_output_timezone_guard.py` | guard | 9 AST-Muster; keine `KNOWN_VIOLATIONS`-Einträge mehr für `trip_command_processor.py` — nichts Neues einführen |
| `trip_alert._get_cached_weather` (`:616-637`) | consumer | Liest den von `_fetch_and_save_snapshot` geschriebenen Anker; verwirft ihn bei `target_date != trip_local_today()` mit `reason="wrong_day"` |

## Implementation Details

**Zone einmal auflösen, als Pflichtparameter durchreichen (Variante a)** — nach dem Muster von
`_format_drilldown` (`:781-785`), dessen Docstring den Pflichtparameter ausdrücklich begründet
(„ein Default würde die Ortszeit wieder still gegen die Prozess-Zeitzone tauschen", `:787-788`):

```python
local_now = trip_local_now(trip, received_at)      # EINE Auflösung (trip_day.py:74-88)
today     = local_now.date()
tomorrow  = today + timedelta(days=1)
tz_heute  = display_tz(trip, today)
tz_morgen = display_tz(trip, tomorrow)
```

Die zwei `display_tz`-Aufrufe sind **keine** verbotene Zweitauflösung — genau das tut
`_day_window` (`:770-779`) heute schon (der Anker bestimmt den Tag, `display_tz` die Anzeige
*dieses* Tages). Verboten ist die Kopie der Auflösungslogik im Rumpf eines Formatierers.

Alle fünf Formatierer (`_aggregate_day`, `_fmt_glance`, `_fmt_gewitter`, `_fmt_timeline`,
`_timeline_buttons`) bekommen `tz` als Pflichtparameter; `_fmt_timeline` nutzt
`local_fmt(p.arrival_time, tz)` statt der rohen `f"{p.arrival_time:%H:%M}"` an den zwei Stellen
`:948`/`:950`.

**Warum nicht Instanzzustand (`self._tz`):** Damit ließe sich einem Formatierer im Test keine
*falsche* Zone unterschieben — „liest das Feld" und „löst selbst auf" sind von außen nicht
unterscheidbar. Mit explizitem Parameter greift die fertige S5a-Vorlage
`test_befehlspfade_folgen_dem_parameter_nicht_der_systemuhr` unverändert (Grundlage AC-6).

**`send_on_demand_report`:** neuer Rückgabetyp `OnDemandErgebnis(outcome: str, zieltag: date)`
(NamedTuple) statt des bisherigen `-> bool`-annotierten Outcome-Strings (die Annotation war seit
#1007 ohnehin falsch, s. Analyse-Dokument „Risks"). `_send_trip_report_outcome` bekommt einen
optionalen Parameter `target_date: date | None = None` (**eine** Stelle, `:1039-1042`) — bei
gesetztem Wert wird er statt der internen `datetime.now(timezone.utc)`-Auflösung verwendet, sonst
bleibt das bisherige Verhalten für die sechs bestehenden Aufrufer unverändert. Ein NamedTuple ist
nicht `True` und fällt im Normalisierer `test_briefing_slot_idempotenz.py:1098-1103` in den
else-Zweig ⇒ **laut rot, nicht still falsch**, sollte eine Aufrufstelle die Migration verpassen.

`_trigger_on_demand` verliert seinen `target_date`-Parameter (Nebengewinn) — der Fehlertext liest
den Zieltag künftig aus `OnDemandErgebnis.zieltag`, nicht aus einer zweiten, im Aufrufer geraten
Variable (Grundlage AC-7).

`_fetch_and_save_snapshot` bekommt `today`/`tomorrow` aus derselben Auflösung wie oben (kein
eigener Zonenzugriff) und schreibt `WeatherSnapshotService.save(trip.id, …, today)` künftig mit
dem Ortstag als `target_date`-Schlüssel (Grundlage AC-8).

## 🔴 Auflagen

- **`_handle_query` darf NICHT zerlegt werden.** Bei sieben `tz`-Argumenten ist eine Aufspaltung
  in kleinere Funktionen verführerisch — sie bricht den B18-Wächter an drei Stellen gleichzeitig
  (`tests/test_success_status_guard.py:1622-1632`, `:1839`, `:1930`), weil der Detektor an
  Ordinalen literaler `success=True`-Rückgaben hängt, nicht an Zeilennummern.
- **VIER, nicht drei, `_aggregate_day`-Aufrufstellen:** `:885`, `:886`, `:904`, `:985`. Eine
  übersehene filtert weiter nach UTC und fällt nur im Mismatch-Fenster auf.
- **Kein rohes `.astimezone()`, kein `date.today()`, kein `datetime.now()` ohne `tz`, kein
  Zonenliteral.** `tests/test_output_timezone_guard.py` läuft in CI und darf keine neuen Funde
  auf `trip_command_processor.py` bekommen.

## Nutzersichtbare Verhaltensänderungen (alle GEWOLLT)

1. **Die `🕐`-Spalte verschiebt sich für JEDEN Nutzer an JEDEM Tag** um den UTC-Offset (Korsika
   +2 h) — nicht nur im Mismatch-Fenster. Kein Golden-Test greift heute darauf zu; ohne
   ausdrückliche Nennung liest der nächste Leser das als Regression.
2. Die vier Query-Kommandos nennen im Mismatch-Fenster einen anderen Tag als heute. Damit
   **endet** die Divergenz zu `/status`, die
   `fix_1727_s5a_befehlspfade_ortstag.md:260-266` als Known Limitation führt.
3. `_fetch_and_save_snapshot` schreibt den Anker künftig mit dem Ortstag ⇒ der Alarm-Leser
   (`trip_alert._get_cached_weather`) verwirft ihn nicht mehr. Das **schaltet Alarme frei, die
   vorher im Mismatch-Fenster nicht liefen** — belegt durch AC-8, nicht nur behauptet.

## Nicht in dieser Scheibe

- **#1818 (einspurige Anker-Abdeckung).** `_send_trip_report_outcome` berechnet genau **einen**
  `target_date` (`trip_report_scheduler.py:1040-1043`) und schreibt daraus ein Tages-Set in die
  undatierte Ankerdatei (`:1300`). `_fetch_and_save_snapshot` ist der einzige Schreiber, der
  beide Tage holt (`trip_command_processor.py:297-299`) — er läuft aber nur, wenn kein Snapshot
  ladbar ist (`:518`). Sobald der Scheduler einmal geschrieben hat, wird der Zwei-Tage-Abruf nie
  wieder ausgelöst; der Anker trägt dann je nach letztem Lauf entweder heute ODER morgen — nie
  beides. Ein AC der Form „`timeline_morgen` zeigt nach dem Fix die morgige Etappe" wäre mit
  einem gewöhnlichen Scheduler-Anker damit **strukturell nie grün** — unabhängig von einer
  korrekten Implementierung dieser Scheibe. Deshalb beziehen sich die ACs hier auf Filter- und
  Formatierlogik, und der Testaufbau bestückt den Anker/die Timeline explizit mit beiden Tagen
  statt sich auf den Scheduler-Anker zu verlassen. #1818 ist als eigenes Issue gebucht.
- **S5b/S5c-Dateien:** `preview_service.py`, `comparison_engine.py`, `gpx_processing.py`,
  `openmeteo.py`, `api/routers/debug.py`, `tools/weather_validation.py`.
- **Koordinaten-Cache für `tz_for_coords`.** Bewusste Nicht-Entscheidung aus S5a: `.timezone_at()`
  je Tour und Aufruf ist linear und billig; keine Optimierung ohne gemessenen Engpass.
- **Die Go-Seite.**

## Expected Behavior

- **Input:** ein eingehender Telegram- oder Mail-Befehl der Query-Familie (`received_at`, ein
  UTC-Zeitpunkt), ein Trip mit Wegpunkten.
- **Output:** Kalendertag (Filter, Kopfzeile) und Uhrzeit-Anzeige (`🕐`-Zeilen) entsprechen der
  Ortszeit der jeweils betroffenen Etappe — nicht dem UTC-Tag/der UTC-Uhrzeit der Nachricht.
- **Side effects:** der bei fehlendem Snapshot geschriebene Wetter-Anker
  (`WeatherSnapshotService.save`) trägt künftig den Ortstag als `target_date`-Schlüssel statt des
  UTC-Tages; der Alarm-Leser liest denselben Schlüssel (s. AC-8).

## Acceptance Criteria

- **AC-1:** Given eine Tour auf Korsika (Europe/Paris, im August UTC+2) hat eine Etappe mit einem
  Wegpunkt, dessen `arrival_time` auf `06:00 UTC` steht (= 08:00 Ortszeit) / When `timeline_heute`
  zu `MITTAGS_UTC` (14:00 UTC, bewusst AUSSERHALB des Mismatch-Fensters) abgefragt wird / Then
  zeigt die Timeline-Zeile `🕐 08:00`, nicht `🕐 06:00`.
  - Test: Abfragezeitpunkt bewusst außerhalb des Mismatch-Fensters wählen, damit allein die
    Uhrzeitumrechnung geprüft wird, nicht ein Tageswechsel; Assertion, dass `🕐 08:00` in
    `confirmation_body` steht und `🕐 06:00` nicht.

- **AC-2:** Given eine Tour auf Korsika mit einer Etappe für den Ortstag D+1 / When eine
  Nachricht zu `NACHTS_UTC` (22:30 UTC = 00:30 Ortszeit des Folgetags, Mismatch-Fenster) für
  `glance`, `heute_gewitter`, `timeline_heute` und `timeline_morgen` gesendet wird / Then beziehen
  sich „heute"/„morgen" bei allen VIER Kommandos auf den Ortstag (D+1/D+2), erkennbar an der
  Datumsbeschriftung in der jeweiligen Kopfzeile — vor dem Fix trugen alle vier noch den UTC-Tag
  (D/D+1).
  - Test: parametrisierter Test über die vier `query_key`-Werte, Assertion auf das erwartete
    Ortstag-Datum in der Kopfzeile jedes `confirmation_body`.

- **AC-3:** Given ein vorhandener Wetter-Snapshot trägt eine Etappe für den Ortstag D+1, die
  Nachricht kommt zu `NACHTS_UTC` (Mismatch-Fenster, Ortstag = D+1) / When `timeline_heute`
  abgefragt wird / Then nennt die Kopfzeile den Ortstag D+1 UND darunter steht mindestens eine
  `🕐`-Zeile mit einer ortszeitrichtig umgerechneten Uhrzeit — wer nur den Filter auf den Ortstag
  umstellt, aber die Uhrzeit weiter roh in UTC formatiert, bekommt „Keine Etappe geplant" (der
  Filter sucht einen Tag, den die unveränderten Rohdaten für eine andere Zone tragen); das muss
  dieser Test laut fehlschlagen lassen.
  - Test: eine einzige Assertion-Gruppe prüft BEIDE Bestandteile gemeinsam (Kopfzeilen-Datum UND
    Vorhandensein/Wert einer `🕐`-Zeile) — ein Test, der nur eines von beidem prüft, lässt einen
    Halb-Fix durch.

- **AC-4:** Given eine Tour hat die heutige Etappe in Neuseeland (Pacific/Auckland, im August
  UTC+12) und die morgige auf Korsika (Europe/Paris, UTC+2) — Fixtur `trip_two_zones`
  (`tests/tdd/conftest.py:55-76`) / When `glance` abgefragt wird / Then beschriftet und filtert
  `_fmt_glance` den heutigen Abschnitt in der neuseeländischen Zone und den morgigen Abschnitt in
  der korsischen Zone — je Tag die Zone SEINER EIGENEN Etappe, nicht eine gemeinsame Zone für
  beide Tage.
  - Test: `trip_two_zones`-Fixtur verwenden, Assertion auf die je Abschnitt erwartete
    Ortsuhrzeit/das erwartete Datum; eine gemeinsame Zone für beide Tage ist die bequeme falsche
    Abkürzung, die dieser Test fangen muss.

- **AC-5:** Given eine Tour in Europe/Paris hat Wegpunkte mit `arrival_time`-Werten rund um beide
  Sommerzeit-Wechseltage 2026 — 29.03. (Lücke, Ortstag hat 23 Stunden) und 25.10. (Doppelstunde,
  Ortstag hat 25 Stunden) / When `timeline_heute`/`timeline_morgen` an beiden Tagen abgefragt wird
  / Then zeigt jede `🕐`-Zeile die korrekte Ortsstunde des jeweiligen Wegpunkts — geprüft auf die
  Häufigkeit JEDER EINZELNEN Stunde (ADR-0044), nicht nur auf das Datum.
  - Test: zwei separate Testfälle (29.03. und 25.10.), je mit mehreren Wegpunkten über den
    Umstellungszeitpunkt verteilt; Assertion auf die exakte `%H:%M`-Zeichenkette jeder Zeile, nicht
    nur auf die Zeilenzahl.

- **AC-6:** Given `freeze_time(X)` ist aktiv UND gleichzeitig wird `received_at = Y` übergeben, X
  und Y liegen auf verschiedenen Ortstagen der Tour / When eine der vier Query-Kommandos
  verarbeitet wird / Then folgt das Ergebnis (Kopfzeilen-Datum, gefilterte Etappe) `Y`, nicht der
  eingefrorenen Systemuhr `X` — Vorlage `tests/tdd/test_befehlspfade_folgen_ortszone.py:517-670`
  (Adversary-Befund F001 aus S5a: „Parameter behalten, im Rumpf ignorieren").
  - Test: zwei literal getrennte Erwartungen (eine für X, eine für Y), Assertion, dass das
    Ergebnis der Y-Erwartung entspricht und NICHT der X-Erwartung; `freeze_time`-Wirksamkeitsanker
    wie in der Vorlage.

- **AC-7:** Given `send_on_demand_report` liefert für einen Aufruf, bei dem am regulären Zieltag
  keine Etappe existiert, ein `OnDemandErgebnis` mit einem `zieltag`, der vom lokal im Aufrufer
  berechneten `today`/`tomorrow` bewusst abweicht (z. B. weil der interne
  `_send_trip_report_outcome`-Aufruf knapp nach Ortsmitternacht ausgeführt wird) / When der
  Fehlertext für `/heute`/`/morgen` gerendert wird / Then nennt er den TATSÄCHLICH benutzten
  Zieltag (`OnDemandErgebnis.zieltag`), nicht ein vom Aufrufer selbst geratenes Datum.
  - Test: `_send_trip_report_outcome` mit einem `target_date` aufrufen, der bewusst vom im
    Aufrufer lokal berechneten `today`/`tomorrow` abweicht; Assertion, dass der Fehlertext den
    `OnDemandErgebnis.zieltag`-Wert trägt.

- **AC-8:** Given eine Tour im Mismatch-Fenster hat noch keinen ladbaren Wetter-Snapshot
  (`timeline.available is False`) / When `_handle_query` daraufhin `_fetch_and_save_snapshot`
  auslöst / Then trägt die geschriebene Ankerdatei `target_date` = Ortstag (nicht UTC-Tag), und
  ein anschließender Aufruf von `trip_alert._get_cached_weather` verwirft sie NICHT MEHR mit
  `reason="wrong_day"` — die Gegenrichtung (UTC-Tag als Schlüssel ⇒ Verwurf) ist im
  Analyse-Dokument empirisch belegt (Wegwerf-Probe, Wellington-Trip, `now_utc=2026-08-13T13:00Z`).
  - Test: Mismatch-Fenster-Fixtur ohne Snapshot, `_handle_query` auslösen, danach
    `trip_alert._get_cached_weather` auf denselben Trip aufrufen; Assertion, dass sie ein Ergebnis
    liefert (nicht `None`) und kein `wrong_day`-Log erscheint.

- **AC-9:** Given die drei Bestandsdateien `test_thunder_origin_four_places.py`,
  `test_thunder_origin_trip.py` und `test_issue_1007_heute_voll_briefing.py` nutzen bisher
  `datetime.now(tz=timezone.utc)` bzw. `date.today()` in ihren Fixturen / When der komplette
  Testlauf dieser drei Dateien zu einem beliebigen Ausführungszeitpunkt läuft — auch mitten im
  Mismatch-Fenster für Europe/Vienna — / Then sind alle Tests weiterhin grün, weil die Fixturen
  auf einen festen, zonensicheren Zeitpunkt eingefroren sind statt an die Systemuhr gekoppelt zu
  bleiben.
  - Test: die drei Dateien unter `freeze_time` auf einen Zeitpunkt **im** Mismatch-Fenster
    (z. B. 22:30 UTC, Europe/Vienna im Sommer) laufen lassen. Vorbedingungs-Anker: zuerst
    messen, dass Ortstag und UTC-Tag zu diesem Zeitpunkt wirklich auseinanderfallen — sonst
    prüft der Lauf nichts. Gegenprobe zur Falsifizierbarkeit: derselbe Lauf auf dem Stand
    **vor** dem Einfrieren muss rot sein.

- **AC-10:** Given die Umstellung auf `tz`-Pflichtparameter und `trip_local_now` ist an allen
  Formatierern abgeschlossen / When `tests/test_output_timezone_guard.py` und
  `tests/test_success_status_guard.py` laufen / Then bleibt `test_output_timezone_guard.py` ohne
  neuen `KNOWN_VIOLATIONS`-Eintrag für `trip_command_processor.py` grün, und
  `test_success_status_guard.py` bleibt ohne Nachzug grün, weil `_handle_query` seine vier
  `success=True`-Rückgaben (`:525`, `:534`, `:542`, `:551`) in Zahl und Reihenfolge unverändert
  behält.
  - Test: `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` und die drei
    referenzierten Assertions in `tests/test_success_status_guard.py` laufen lassen; beide grün
    ohne Änderung an den Wächterdateien selbst.

- **AC-11:** Given die Restliste „Noch nicht umgesetzt" in
  `docs/adr/0044-kalendertage-folgen-der-ortszeit.md:142-147` nennt **fünf** Stellen, die
  längst geliefert sind — `_show_status`, `_show_now`, `command_date` und
  `inbound_telegram_reader.py` (alle vier aus #1727 S5a, `fd87fca6`) sowie `_handle_query`
  (diese Scheibe); die Datei wurde zuletzt mit `fa53c4a3`/#1726 angefasst, S5a hat sie
  **nicht** nachgezogen / When diese Scheibe live geht / Then stehen alle fünf im Abschnitt
  „Umgesetzt", mit ihrer jeweiligen Issue-Nummer, und die Restliste enthält nur noch
  tatsächlich Offenes (`preview_service.py`, `api/routers/debug.py`,
  `tools/weather_validation.py` → S5b/S5c).
  - Test: `# doc-compliance-test` — Assertion, dass keiner der fünf Namen mehr unterhalb der
    Überschrift „Noch nicht umgesetzt" steht und `_handle_query` unter „Umgesetzt" auftaucht
    (die laut CLAUDE.md einzige erlaubte Ausnahme für einen Dateiinhalts-Check).
  - 🔴 Begründung, warum das ein AC ist und keine Fleißaufgabe: das ADR warnt an dieser Stelle
    selbst — „eine unvollständige Restliste liest sich wie eine vollständige". Genau dieser
    Fehler ist bereits eingetreten und blieb eine Scheibe lang unbemerkt.

## Nachweisführung

Vollständig offline belegbar (Kern-Schicht): `freeze_time` (freezegun) plus In-Memory-`Trip`/
`Stage`/`Waypoint`-Fixturen, analog zu `tests/unit/test_trip_local_today.py`. Keine Staging-Mail
nötig — der Versand selbst ist unberührt, alle betroffenen Stellen sind Filter-, Formatier- und
ein Persistenz-Schlüssel-Pfad.

## Testbenennung

Neue Suite `tests/tdd/test_timeline_folgt_der_ortszeit.py` — nach Verhalten benannt, kein
`test_issue_1795*`-Name (durchgesetzt von `test_naming_gate.py`).

## Known Limitations

- **Mehrzonen-Restfehler** (ADR-0044, bewusst offen, PO-Entscheidung): Wechselt der Wanderer an
  genau dem betreffenden Tag die Zeitzone, bleibt die Differenz zweier benachbarter Etappen als
  Restfehler — eine Tour dieser Spannweite hat ohnehin keinen eindeutigen „Kalendertag".
- **Das Mismatch-Fenster ist jahreszeitabhängig:** für Europe/Vienna im Sommer (CEST, UTC+2) 2
  Stunden breit, im Winter (CET, UTC+1) nur 1 Stunde. Die Breite ist stets |UTC-Offset| Stunden.
- **`WeatherSnapshotService.save()` schreibt nicht atomar** (`filepath.write_text(...)`, kein
  Temp-File mit Rename), und `load()` (`:196-226`) gibt bei JEDER Lesestörung `None` zurück
  (`JSONDecodeError`, `ValueError`, `KeyError`, `OSError`), nicht nur bei fehlender Datei. Eine an
  sich gute, korrekt datierte Ankerdatei, die gerade unlesbar ist, führt damit ebenfalls auf
  `not timeline.available` und wird überschrieben. Schmaler, **vorbestehender** Fall, nicht durch
  diese Scheibe verursacht.
- **Einspurige Anker-Abdeckung** (#1818, eigenes Issue, s. „Nicht in dieser Scheibe") — ein
  vorbestehender, unabhängiger Defekt, den diese Scheibe nicht behebt.

## Warum eine Scheibe und kein Schnitt

- **„Tag zuerst"** = der #1697-Bruch selbst: der Filter vergleicht einen Ortstag gegen
  unveränderte UTC-Zeitstempel ⇒ „Keine Etappe geplant". Ausgeschlossen.
- **„Uhrzeit zuerst"** = zwei Zeitbegriffe in einer Nachricht: Kopfzeile nennt den UTC-Tag, die
  `🕐`-Zeilen darunter zeigen bereits Ortszeit — genau wovor ADR-0051 warnt. Ausgeschlossen.
- **„Rückgabe-Zieltag abtrennen"** wäre technisch sauber (≈ +35/−10 Produktiv), kauft aber genau
  die Divergenz zurück, die S5a bereits ausdrücklich auf #1795 verwiesen hat, plus eine zweite
  Spec-, RED-, Adversary- und Staging-Runde. Der LoC-Override auf 1000 ist billiger als eine
  zweite volle Runde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (Akzeptiert), ADR-0051 Regel 3 (Vorgeschlagen)
- **Rationale:** Setzt die bereits akzeptierte ADR-0044-Entscheidung an der zuletzt namentlich
  gelisteten Stelle (`_handle_query` und die Query-Familie) um — keine offene Produktfrage, ein
  Bug gegen eine getroffene Entscheidung, kein neues ADR nötig. Folgt zusätzlich Regel 3 aus
  ADR-0051 (`tz`/`now_utc` als Pflichtparameter, kein Systemuhr-Default), obwohl jenes ADR noch
  „Vorgeschlagen" ist — Regel 3 ist an anderer Stelle (#1724, #1726, #1727 S5a) bereits umgesetzt
  und dort als bindendes Muster etabliert, an dem sich diese Scheibe ausdrücklich orientiert.

## Changelog

- 2026-08-13: Spec erstellt nach `docs/context/fix-1795-timeline-ortszeit.md` (Basis-HEAD
  `dbad9614`).
- 2026-08-13 (nach Umsetzung, Umfangsprüfung): Dateitabelle an die tatsächliche Lieferung
  angeglichen — die ACs sind unberührt, nur die beschreibende Liste war falsch geworden.
  Drei Abweichungen:
  1. **`_fetch_and_save_snapshot` wurde NICHT geändert.** AC-8 ist trotzdem erfüllt, und zwar
     strukturell: die Funktion bekommt `today` unverändert vom Aufrufer, und der trägt seit
     dieser Scheibe den Ortstag (`trip_command_processor.py:532`). Weniger Diff als
     angekündigt, gleiche Wirkung.
  2. **`tests/tdd/conftest.py`** hat nicht die DST-Fixtur aufgenommen, sondern den
     `_anker()`-Helfer (Vorbedingungs-Anker). Die DST-Fälle liegen lokal in der neuen Suite;
     AC-5 ist inhaltlich abgedeckt (29.03. und 25.10.2026).
  3. **`tests/tdd/test_befehlspfade_folgen_ortszone.py`** war in der Tabelle nicht vorgesehen,
     wurde aber angefasst — als Altnutzer des gehobenen `_anker()`. Eine dritte Kopie wäre der
     Fehler gewesen, den ADR-0044 für die Zonen-Auflösung selbst verbietet.
- 2026-08-13: **Testumfang über der Schätzung.** Die neue Suite ist 928 statt geschätzter ~650
  Zeilen. Ursache sind die Adversary-Runden (F001, F002, F004, F005) — genau der Posten, für den
  der Override von 1000 Reserve tragen sollte; die Reserve war zu klein. Produktivcode liegt mit
  +111/−42 im geschätzten Korridor.
