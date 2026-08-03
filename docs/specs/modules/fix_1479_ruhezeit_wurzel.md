---
entity_id: fix_1479_ruhezeit_wurzel
type: bugfix
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.0"
tags: [alerts, trip, compare, epic-1458, issue-1479]
---

# Ruhezeit-Härtung an der Wurzel: ein kaputter Wert darf keinen Alarm-Lauf mehr mitreißen (Issue #1479)

## Approval

- [x] Approved — PO „go" am 2026-08-03

## Purpose

Ein unbrauchbarer Ruhezeit-Wert in EINEM Ortsvergleich oder Trip (z. B.
`alert_quiet_from = "25:00"` oder ein Nicht-String wie `2200`) lässt
`DeviationAlertEngine.is_quiet_hours()` eine Ausnahme werfen. An drei von sechs
Aufrufstellen ist diese Ausnahme ungefangen und beendet den **kompletten**
Alarm-Lauf des Nutzers — alle weiteren Trips/Ortsvergleiche werden still
übersprungen. An zwei weiteren Stellen verliert zumindest der betroffene Trip
selbst seinen Alarm. Ausbleibender Alarm ist laut Leitsatz aus #1467 der
gefährlichste Fehlerfall. Diese Scheibe härtet die geteilte Funktion selbst
(Wurzel-Fix, PO-Entscheidung 2026-08-03) statt eine vierte Kopie des in
#1467 S2 AG2 bereits gebauten Behelfs-Schutzes anzulegen — und baut diesen
Behelf zurück, weil er nach der Härtung überflüssig wird.

## Source

- **File:** `src/services/deviation_alert_engine.py`
- **Identifier:** `class DeviationAlertEngine`, `staticmethod is_quiet_hours()`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Kein
Go-Code, kein Frontend-Code — Go hält `AlertQuietFrom`/`AlertQuietTo` als
`*string` (`internal/model/compare_preset.go:78-79`, `internal/model/trip.go:116`)
und wertet sie nie selbst aus.

## Estimated Scope

- **LoC:** Produktivcode etwa +20 / −25 (Rückbau überwiegt den Zusatz), Tests
  etwa +220
- **Files:** 5 MODIFY + 1 CREATE
- **Effort:** low-medium (eine geteilte Funktion + fünf Aufrufer, die nur eine
  Kennung durchreichen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DeviationAlertEngine` | module | Geteilter Auswertungskern (ADR-0021) — hier wird gehärtet |
| `rework_1467_s2_aenderungsalarm` | module | AG2 baute den Behelfs-Schutz in `compare_alert.py`, der hier zurückgebaut wird |
| `issue_181_alert_cooldown_quiet_hours` | module | Ursprungs-Spec Ruhezeiten, Known Limitation „halbes Fenster ⇒ `False`" gilt unverändert |
| `compare_official_alert.py` | module | Aufrufstelle 2 — heute ungeschützter Ganz-Lauf-Absturz |
| `compare_radar_alert.py` | module | Aufrufstelle 3 — heute ungeschützter Ganz-Lauf-Absturz |
| `trip_alert.py` (`_is_quiet_hours`-Adapter) | module | Bündelt Aufrufstellen 4/5/6 (Radar-Onset, `check_and_send_alerts`, `_send_official_alert_only`) |

## Ist-Stand — sechs Aufrufstellen, gemessen 2026-08-03 (HEAD `476094b9`)

| # | Aufrufstelle | Fehlerbehandlung heute | Wirkung bei unbrauchbarem Wert |
|---|---|---|---|
| 1 | `compare_alert.py:162` (Δ-Wetter Ortsvergleich) | eigener `try/except Exception` (#1467 S2 AG2) + Neutralisierung von `config.quiet_from/to` | ✅ abgefangen, Lauf läuft weiter — **entfällt in dieser Scheibe** |
| 2 | `compare_official_alert.py:107` (amtlich Ortsvergleich) | keine — Aufruf im Generator von `sum(...)` (`:72`) | ❌ **ganzer Lauf des Nutzers bricht ab** |
| 3 | `compare_radar_alert.py:104` (Nowcast Ortsvergleich) | keine — `for`-Schleife ohne `try` | ❌ **ganzer Nowcast-Lauf bricht ab** |
| 4 | `trip_alert.py:733` (Radar-Onset Trips) | keine — erstes `try` erst bei `:755` (Nowcast-Abruf) | ❌ **ganzer Radar-Onset-Lauf bricht ab**, alle weiteren Trips |
| 5 | `trip_alert.py:205` (`check_and_send_alerts`) | im äußeren `try/except Exception` `:427-438` | ⚠️ Lauf läuft weiter, **dieser Trip verliert seinen Alarm** |
| 6 | `trip_alert.py:1118` (`_send_official_alert_only`) | wie 5 | ⚠️ wie 5 |

Aufrufstellen 4, 5 und 6 laufen alle über denselben Adapter
`TripAlertService._is_quiet_hours(trip, now)` (`trip_alert.py:494-512`), der
seinerseits `DeviationAlertEngine.is_quiet_hours()` aufruft — die Härtung der
Engine wirkt also für alle drei automatisch mit; der Adapter reicht nur die
Trip-Kennung als `context_label` durch.

## Implementation Details

### Wurzel-Härtung (`deviation_alert_engine.py`)

`is_quiet_hours()` bekommt einen neuen optionalen Parameter
`context_label: str = ""`. Die beiden `fromisoformat`-Zeilen (`:95-96`) werden
mit `try/except Exception` umschlossen — bewusst NUR diese zwei Zeilen, nicht
die ganze Funktion: die Zeitzonen-Umrechnung (`astimezone(VIENNA)`) darf
weiter laut scheitern, das ist ein anderer Fehlerfall.

Bei einer Ausnahme:
- Rückgabe `False` (= „keine Ruhezeit gesetzt" — Richtung: lieber eine
  Meldung zu viel als eine verschluckte, deckungsgleich mit der bestehenden
  Known Limitation aus #181 für das halb ausgefüllte Fenster)
- `logger.warning(...)` MUSS enthalten: `type(e).__name__`, `quiet_from!r`,
  `quiet_to!r` und `context_label` (falls gesetzt)

**Absichtlich breit auf `Exception`**, Begründung 1:1 aus #1467 S2 AG2
F001/F003 übernommen: der Wert stammt aus einer Nutzerdatei, nicht aus
Programmlogik. Schaden bei zu enger Klausel (Alarm bleibt für ALLE aus) wiegt
schwerer als Schaden bei zu breiter Klausel (ein echter Programmfehler landet
als Warnung im Protokoll statt abzustürzen — die Meldung geht trotzdem raus).
Deshalb ist der Ausnahmetyp in der Protokollzeile Pflicht, damit ein echter
Programmfehler dort auffindbar bleibt.

Der zweite, interne Aufruf in `evaluate()` (`:243`) profitiert automatisch —
er ruft dieselbe (jetzt gehärtete) Methode auf.

### Aufrufstellen 2–4: Kennung durchreichen, kein eigener Schutz

- `compare_official_alert.py:107` reicht `context_label=preset_id` durch.
- `compare_radar_alert.py:104` reicht `context_label=preset_id` durch.
- `trip_alert.py::_is_quiet_hours` (`:494-512`, Adapter für 4/5/6) reicht
  `context_label=trip.id` durch — deckt damit alle drei Trip-Aufrufstellen in
  einer Änderung ab.

Keine dieser Stellen bekommt ein eigenes `try/except` — genau das ist der
Punkt des Wurzel-Fixes (ADR-0021: eine geteilte Alert-Engine für Trip und
Ortsvergleich, der Schutz gehört in den geteilten Baustein, nicht in vier
Kopien).

### Rückbau: `compare_alert.py:161-181`

Der Behelfs-Schutz aus #1467 S2 AG2 (`try/except Exception` um den
`is_quiet_hours()`-Aufruf, Protokollzeile, Neutralisierung von
`config.quiet_from`/`config.quiet_to` vor der Weitergabe an
`_evaluate_one_location()` → `DeviationAlertEngine.evaluate()`) entfällt
vollständig. Der einfache, direkte Aufruf `DeviationAlertEngine.is_quiet_hours(
now, config.quiet_from, config.quiet_to, context_label=preset_id)` bleibt
stehen — jetzt schützt sich die Engine selbst, auch beim zweiten,
Preset-internen Aufruf über `evaluate()`. Die Neutralisierung von
`config.quiet_from`/`config.quiet_to` wird überflüssig, weil `evaluate()` bei
demselben kaputten Wert nicht mehr wirft, sondern intern denselben
`False`-Pfad nimmt.

**Nachweis, dass der Rückbau nichts verliert:** der bestehende Test
`tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py::test_f001_broken_quiet_value_does_not_abort_other_presets_same_user`
bleibt **unverändert** (keine Zeile angefasst) und MUSS weiterhin grün sein.

## Expected Behavior

- **Input:** `alert_quiet_from`/`alert_quiet_to` aus einer Nutzerdatei —
  gültiger String (`"22:00"`), leerer String, `None`/fehlend, kaputter String
  (`"25:00"`, `"abc"`) oder Nicht-String (`int`, `float`, `list`, `bool`,
  `dict`).
- **Output:** Bei gültigem, vollständigem Wert unverändert die bisherige
  Mitternachts-Wrap-Logik. Bei jedem unbrauchbaren Wert (leer, fehlend,
  kaputter String, Nicht-String) `False` — „keine Ruhezeit aktiv", der Lauf
  geht für diesen Ort/Trip normal weiter.
- **Side effects:** Bei einer gefangenen Ausnahme genau eine
  `logger.warning`-Zeile mit Ausnahmetyp, beiden Rohwerten und der Kennung des
  betroffenen Presets/Trips. Kein Programmabbruch, keine verlorenen weiteren
  Presets/Trips desselben Nutzers.

## Acceptance Criteria

- **AC-1:** Given zwei amtliche Ortsvergleich-Presets desselben Nutzers, eines
  mit kaputtem `alert_quiet_from` (`"25:00"`) und eines gesund mit einer
  auslösenden amtlichen Warnung, When `CompareOfficialAlertService.check_all_compare_presets()`
  läuft, Then bricht der Lauf nicht ab und das gesunde Preset stellt seinen
  Alarm trotzdem zu.
  - Test: zwei echte Preset-Dateien über `tests/helpers/compare_briefings.py`,
    Zustellung am echten Mail- bzw. Telegram-Sink für das gesunde Preset
    prüfen, kein Abbruch der Schleife.

- **AC-2:** Given zwei Nowcast-Ortsvergleich-Presets desselben Nutzers, eines
  mit kaputtem `alert_quiet_to` (Nicht-String, z. B. `2200`) und eines gesund
  mit erfülltem Onset, When `CompareRadarAlertService.check_all_compare_presets()`
  läuft, Then bricht der Lauf nicht ab und das gesunde Preset stellt seinen
  Alarm trotzdem zu.
  - Test: zwei Preset-Fixtures, echte Onset-Bedingung für das gesunde Preset,
    Zustellung am Sink prüfen.

- **AC-3:** Given zwei Trips desselben Nutzers, einer mit kaputtem
  `alert_quiet_from` (`"abc"`) und einer gesund mit erfülltem Radar-Onset,
  When der Radar-Onset-Check über alle Trips läuft, Then bricht der Lauf
  nicht ab und der gesunde Trip stellt seinen Alarm trotzdem zu.
  - Test: zwei Trip-Fixtures, Onset-Bedingung für den gesunden Trip erfüllt,
    Zustellung am Sink prüfen.

- **AC-4:** Given einen Trip mit kaputtem Ruhezeit-Wert (kaputter String oder
  Nicht-String) und einer auslösenden Wetteränderung, When
  `TripAlertService.check_and_send_alerts()` für diesen Trip läuft, Then wird
  der Alarm für GENAU DIESEN Trip trotzdem zugestellt, statt heute still
  verloren zu gehen.
  - Test: Trip-Fixture mit kaputtem Wert, Δ über Schwelle, Zustellung am Sink
    prüfen (vorher: 0 Zustellungen, nachher: 1).

- **AC-5:** Given einen Trip mit kaputtem Ruhezeit-Wert und einer neuen
  amtlichen Warnung, When `TripAlertService._send_official_alert_only()` für
  diesen Trip läuft, Then wird die amtliche Warnung trotzdem zugestellt,
  statt heute still verloren zu gehen.
  - Test: Trip-Fixture mit kaputtem Wert, amtliche Warnung vorhanden,
    Zustellung am Sink prüfen.

- **AC-6:** Given `is_quiet_hours()` mit `quiet_from`/`quiet_to` aus den fünf
  Nicht-String-Typen (`int`, `float`, `list`, `bool`, `dict`) sowie den
  kaputten Strings `"25:00"` und `"abc"`, When die Funktion direkt
  aufgerufen wird, Then liefert sie in JEDEM dieser sieben Fälle `False`,
  ohne eine Ausnahme nach außen zu werfen.
  - Test: parametrisierter Aufruf über alle sieben Werte, `assert result is
    False` und keine Exception propagiert.

- **AC-7:** Given `quiet_from=""` (leerer String, kein `ValueError`-Auslöser)
  oder `quiet_from=None`/fehlend, When `is_quiet_hours()` aufgerufen wird,
  Then liefert sie unverändert `False` über den bestehenden
  `if not quiet_from or not quiet_to`-Pfad (`:91-92`), OHNE dass der neue
  `try/except` je greift.
  - Test: leerer String und `None` direkt geprüft, plus ein
    Log-Spion/-Capture, der beweist, dass die neue Warnzeile NICHT
    geschrieben wurde (Unterscheidung „regulärer Leerfall" vs. „gefangene
    Ausnahme").

- **AC-8:** Given ein unbrauchbarer Ruhezeit-Wert und ein gesetzter
  `context_label`, When `is_quiet_hours()` die Ausnahme fängt, Then enthält
  die geschriebene `logger.warning`-Zeile den Ausnahmetyp
  (`type(e).__name__`), beide Rohwerte (`quiet_from!r`, `quiet_to!r`) und den
  `context_label`-Wert.
  - Test: `caplog`/Log-Capture nach dem Aufruf, alle vier Bestandteile als
    Teilstring in der geschriebenen Zeile nachweisen.

- **AC-9:** Given eine gültige, vollständige Ruhezeit (inkl.
  Mitternachts-Wrap wie `22:00–07:00`) und ein halb ausgefülltes Fenster (nur
  `quiet_from` gesetzt), When `is_quiet_hours()` mit den bestehenden
  Regressionsfällen aus #181 aufgerufen wird, Then bleibt das Verhalten
  gegenüber dem Stand vor dieser Scheibe unverändert (Unterdrückung im
  gültigen Fenster, keine Unterdrückung beim halben Fenster).
  - Test: bestehende Fälle aus `test_alert_quiet_hours_localtime.py` und
    `issue_181_alert_cooldown_quiet_hours`-Suite laufen unverändert grün,
    plus ein neuer direkter Aufruf für den Mitternachts-Wrap.

- **AC-10:** Given den Rückbau des Behelfs-Schutzes in `compare_alert.py`,
  When der bestehende Test
  `test_compare_alert_quiet_hours_precedes_fetch.py::test_f001_broken_quiet_value_does_not_abort_other_presets_same_user`
  nach dem Rückbau läuft, Then bleibt er unverändert (keine Zeile in der
  Testdatei angefasst) grün.
  - Test: `uv run pytest tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py::test_f001_broken_quiet_value_does_not_abort_other_presets_same_user`
    — Exit 0, Diff der Testdatei = 0 Zeilen.

- **AC-11:** Given den Code-Stand nach dieser Scheibe, When man
  `compare_official_alert.py`, `compare_radar_alert.py` und
  `trip_alert.py::_is_quiet_hours` auf ein eigenes `try`/`except` um den
  `is_quiet_hours()`-Aufruf durchsucht, Then findet sich dort KEIN eigenes
  `try`/`except` — der Schutz lebt ausschließlich in
  `DeviationAlertEngine.is_quiet_hours()`.
  - Test: gezielter `grep` im Test auf die drei Aufrufstellen, Assertion,
    dass kein `try`/`except Exception` in unmittelbarer Nähe (± 5 Zeilen) des
    `is_quiet_hours(`-Aufrufs steht — beweist, dass ein Rückfall in die
    Kopier-Lösung (vom PO ausdrücklich verworfen) den Test bricht.

## Nicht in dieser Scheibe

- Eingabeprüfung/Validierung beim Speichern (Go-Handler bzw. Frontend) — Go
  hält den Wert als `*string` und wertet ihn zur Laufzeit nie aus. Dass ein
  unbrauchbarer Wert überhaupt in die Datei geschrieben werden kann, bleibt
  ein eigener, hier nicht behobener Befund.
- Reihenfolge „Ruhezeit vor dem Wetterabruf" für den Nowcast-Pfad
  (`compare_radar_alert.py`) — gehört zu #1467 S3.
- Keine Frontend-Änderung.
- Kein neuer Go-Endpunkt, kein neuer Cron-Job — `api/routers/scheduler.py`
  bleibt unangetastet; nach dem Wurzel-Fix hat ein zusätzlicher Schutz dort
  ohnehin keine Wirkung mehr für diesen Fehlerfall.

## Known Limitations

- Ein Nutzer mit kaputtem Wert bekommt künftig Alarme während seiner
  gemeinten Ruhezeit statt gar keiner Alarme — bewusster Nebeneffekt, vom PO
  in #1467 S2 AG2 bereits bestätigt (sichere Richtung: lieber eine Meldung zu
  viel). Die Protokollzeile macht den kaputten Wert im Betrieb auffindbar.
- Keine Eingabeprüfung beim Speichern (s. „Nicht in dieser Scheibe") — der
  kaputte Wert kann jederzeit erneut entstehen, bis dieser Folgebefund separat
  behoben wird.

## Testplan

Kern-Schicht, deterministisch, kein Netz — Vorbild
`tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` (echte
Preset-Dateien über `tests/helpers/compare_briefings.py`, echte
`LocationWeatherSource`-Implementierungen als Test-Seams, kein
`Mock()`/`patch()`/`MagicMock`).

Neue Testdatei: `tests/tdd/test_alert_quiet_hours_robustness.py` (Namensregel:
Verhalten, nicht Issue-Nummer — `test_naming_gate.py` würde eine
`test_issue_1479_*.py` hart blocken). Prüfling relativ zur Testdatei auflösen
(`Path(__file__).resolve().parents[2]`), niemals über den festen
Hauptrepo-Pfad (#1409).

Deckt: AC-1 bis AC-11, davon
- 3 Zwei-Einheiten-Tests (AC-1/2/3, je zwei echte Fixtures desselben Nutzers)
- 2 Trip-Einzel-Tests (AC-4/5)
- 1 parametrisierter Typen-Test über sieben Werte (AC-6)
- 1 Regressions-Test Leerfall/`None` (AC-7)
- 1 Log-Inhalts-Test (AC-8)
- 1 Regressions-Test gültige Ruhezeit + halbes Fenster (AC-9)
- 1 unveränderter Bestandstest-Lauf (AC-10)
- 1 struktureller Grep-Test gegen Rückfall in Kopier-Lösung (AC-11)

Nach der Implementierung: gezielter Lauf der neuen Testdatei plus der
namentlich benannten Bestandstests aus AC-9/AC-10 — **kein** voller
`uv run pytest`-Lauf ohne benannte Dateien (Gate `broad_test_run_gate.py`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — setzt ADR-0021 (eine geteilte Alert-Engine für
  Trip und Ortsvergleich) konsequent um: der Fehlerschutz gehört in den
  geteilten Baustein, nicht in vier Kopien.
- **Rationale:** Der PO hat am 2026-08-03 ausdrücklich die Kopier-Lösung
  (vierter Behelfs-Schutz in `compare_official_alert.py`) verworfen zugunsten
  des Wurzel-Fixes. AC-11 macht diese Entscheidung strukturell prüfbar.

## Changelog

- 2026-08-03: Initiale Spec erstellt aus `docs/context/fix-1479-ruhezeit-wurzel.md`.
