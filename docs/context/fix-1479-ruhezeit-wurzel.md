# Context: fix-1479-ruhezeit-wurzel

**Issue:** #1479 — „Kaputter Ruhezeit-Wert legt den amtlichen Alarm-Lauf fuer alle
Ortsvergleiche lahm" (Label `bug`, `priority:high`, `area:alerts`)
**Track:** Standard (Intake-Score 3 — Scope Medium / Blast Radius High / Unsicherheit Low)
**PO-Entscheidung 2026-08-03:** Wurzel-Fix in der geteilten Ruhezeit-Pruefung, nicht
noch eine Kopie des Schutzes im amtlichen Pfad.

## Request Summary

Ein unbrauchbarer Ruhezeit-Wert in **einem** Ortsvergleich (z. B. `alert_quiet_from
= "25:00"`, oder gar kein String) laesst `DeviationAlertEngine.is_quiet_hours()` eine
Ausnahme werfen. In den meisten Aufrufpfaden ist diese Ausnahme ungefangen und beendet
den kompletten Alarm-Lauf des Nutzers — **ausbleibende Alarme**, der laut Leitsatz von
#1467 gefaehrlichste Fehlerfall. Der Fix haertet die geteilte Funktion selbst: ein
unbrauchbarer Wert gilt als „keine Ruhezeit gesetzt" und wird laut protokolliert.

## Gemessener Ist-Stand: alle sechs Aufrufstellen

`grep -rn "is_quiet_hours" src/ api/` — Stand 2026-08-03, HEAD `476094b9`.

| # | Aufrufstelle | Fehlerbehandlung am Aufrufort | Wirkung bei unbrauchbarem Wert |
|---|---|---|---|
| 1 | `src/services/compare_alert.py:162` (Δ-Wetter Ortsvergleich) | eigenes `try/except Exception` (#1467 S2 AG2, F001+F003) + Neutralisierung von `config.quiet_from/to` | ✅ abgefangen, protokolliert, Lauf laeuft weiter |
| 2 | `src/services/compare_official_alert.py:107` (amtlich Ortsvergleich) | **keine** — Aufruf steckt im Generator-Ausdruck von `sum(...)` (`:72`) | ❌ **ganzer Lauf des Nutzers bricht ab**, alle weiteren Ortsvergleiche still uebersprungen ⇒ **das ist #1479** |
| 3 | `src/services/compare_radar_alert.py:104` (Nowcast Ortsvergleich) | **keine** — `for`-Schleife `:77-79` ohne `try` | ❌ **ganzer Nowcast-Lauf bricht ab** |
| 4 | `src/services/trip_alert.py:733` (Radar-Onset Trips) | **keine** — Schleife ab `:709`, das erste `try` steht erst bei `:755` (Nowcast-Abruf) | ❌ **ganzer Radar-Onset-Lauf bricht ab**, alle weiteren Trips |
| 5 | `src/services/trip_alert.py:205` (via `check_and_send_alerts`) | im `try/except Exception` `:427-438` | ⚠️ Lauf laeuft weiter, **dieser Trip verliert seinen Alarm** (nur `logger.error`) |
| 6 | `src/services/trip_alert.py:1118` (`_send_official_alert_only`) | im selben `try` `:427-438` | ⚠️ wie 5 |

**Kernbefund:** Die Luecke ist breiter als das Issue annimmt. **Drei** Stellen reissen
den ganzen Lauf mit (2, 3, 4), **zwei** verlieren still den Alarm eines Trips (5, 6).
Das Issue schreibt unter „Abgrenzung", der Nowcast-Pfad sei „von dieser konkreten Form
nicht betroffen" — das stimmt fuer die *Reihenfolge*-Frage aus #1467 AG2 (er prueft die
Ruhezeit erst nach der Erkennung), **nicht** fuer den Absturz: `compare_radar_alert.py:104`
steht genauso ungeschuetzt da.

## Ursache

`src/services/deviation_alert_engine.py:75-100`:

```python
if not quiet_from or not quiet_to:
    return False
...
from_time = time_type.fromisoformat(quiet_from)   # <- wirft
to_time = time_type.fromisoformat(quiet_to)
```

- unbrauchbarer **String** (`"25:00"`, `"abc"`) ⇒ `ValueError`
- **Nicht-String** (`int` 2200, `float`, `list`, `bool`, `dict`) ⇒ `TypeError`

Der Wert stammt aus einer Nutzerdatei (`data/users/<u>/briefings/<id>.json` bzw.
`trips/<id>.json`) und wird **zur Laufzeit nirgends erzwungen**: Go haelt ihn als
`*string` (`internal/model/compare_preset.go:78-79`, `internal/model/trip.go:116`) und
wertet ihn selbst nie aus (`grep AlertQuietFrom` → nur Speichern/Round-Trip, keine
Auswertung); Python-seitig `src/app/models.py`. Es gibt also keine Schranke davor.

## Vorlage fuer den Fix

`src/services/compare_alert.py:132-181` (#1467 S2 AG2, Fix-Loop F001 + F003) — vom
Adversary ueber 4 Runden abgenommen. Die dort festgehaltene Begruendung gilt
unveraendert und wird bei der Wurzel-Haertung uebernommen:

- **breit auf `Exception` fangen** — der Wert kommt aus einer Nutzerdatei, nicht aus
  Programmlogik; der Schaden bei zu enger Klausel (Alarm bleibt fuer ALLE aus) wiegt
  schwerer als bei zu breiter
- **Ausnahmetyp mitprotokollieren** (`type(e).__name__`), damit ein echter
  Programmfehler dort auffindbar bleibt und nicht als „kaputter Nutzerwert" durchgeht
- **Richtung: lieber eine Meldung zu viel als eine verschluckte** — deckungsgleich mit
  der bestehenden „Known Limitation" aus #181: halb ausgefuelltes Fenster (`from` ohne
  `to`) ⇒ `False`, also keine Unterdrueckung

**Vereinfachung, die der Wurzel-Fix ermoeglicht:** Ist `is_quiet_hours()` selbst
tolerant, wird der Behelfs-Schutz in `compare_alert.py:161-181` ueberfluessig — inkl.
der Neutralisierung von `config.quiet_from/to`, die es nur gibt, weil
`DeviationAlertEngine.evaluate()` (`:243`) denselben Aufruf ein zweites Mal macht und
dort erneut werfen wuerde. Netto faellt Code weg statt hinzuzukommen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/deviation_alert_engine.py:75-100` | **Prueflings-Kern** — hier wird gehaertet |
| `src/services/deviation_alert_engine.py:243` | zweiter Aufruf innerhalb `evaluate()` |
| `src/services/compare_official_alert.py:72, :105-113` | Ausloeser des Issues |
| `src/services/compare_radar_alert.py:77-79, :104` | zweiter ungeschuetzter Ganz-Lauf-Absturz |
| `src/services/trip_alert.py:205, :494-511, :733, :1118` | Trip-Adapter + drei Aufrufstellen |
| `src/services/compare_alert.py:132-181` | Vorlage **und** Rueckbau-Kandidat |
| `api/routers/scheduler.py:100-108` | Einstieg `POST /compare-official-alert-checks`, reicht ohne eigenes `try` durch |

## Bestehende Tests (Regressionsflaeche)

`grep -rln "is_quiet_hours\|quiet_from\|alert_quiet" tests/` → 9 Dateien:
`test_issue_1168_alert_engine_extract.py`, `test_alert_quiet_hours_localtime.py`,
`test_alert_cooldown_quiet.py`, `test_compare_alert_quiet_hours_precedes_fetch.py`,
`test_compare_official_alert.py`, `test_compare_radar_alert.py`,
`test_compare_preset_loader.py`, `test_issue_883_acute_danger_override.py`,
`test_throttle_store.py`.

**Kein einziger** schreibt die heutige Ausnahme-Semantik fest (`grep ValueError|TypeError`
findet nur einen Docstring-Treffer zu `Trip.__post_init__`). Die Haertung bricht also
keine bestehende Zusicherung.

**Nachweis-Vorbild (vom Issue gefordert):**
`tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py::test_f001_broken_quiet_value_does_not_abort_other_presets_same_user`
— zwei Ortsvergleiche desselben Nutzers, einer kaputt, einer gesund und ausloesend;
der gesunde MUSS zustellen. Mock-freie Seams: echte Preset-Dateien via
`tests/helpers/compare_briefings.py`, echte `LocationWeatherSource`-Implementierungen.

## Existing Specs

- `docs/specs/modules/issue_181_alert_cooldown_quiet_hours.md` — Ursprungs-Spec
  Ruhezeiten inkl. Mitternachts-Wrap; **Known Limitation**: Halbkonfiguration ⇒ `False`
- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — AG2, dort AC-4/5/6 + F001/F003
- `docs/specs/modules/feat_864_859_alert_presets.md` — Empfindlichkeitsstufen (Umfeld)
- ADR-0021 — eine geteilte Alert-Engine fuer Trip und Ortsvergleich (stuetzt den
  Wurzel-Fix: der Schutz gehoert in den geteilten Baustein, nicht in vier Kopien)

## Dependencies

- **Upstream:** `datetime.time.fromisoformat`, `zoneinfo` (`Europe/Vienna`, #1312 D1)
- **Downstream:** die sechs Aufrufstellen oben; `api/routers/scheduler.py`
  (`/alert-checks`, `/compare-alert-checks`, `/compare-radar-alert-checks`,
  `/compare-official-alert-checks`); Go-Scheduler ruft diese Endpunkte, wertet die
  Ruhezeit aber **nicht selbst** aus ⇒ **keine Go-Aenderung noetig**

## Risks & Considerations

1. **Bewusster Nebeneffekt:** Ein Nutzer mit kaputtem Wert bekommt kuenftig Alarme
   waehrend seiner gemeinten Ruhezeit statt gar keiner Alarme. Das ist die vom PO in
   #1467 AG2 bestaetigte Richtung — und die Protokollzeile macht es auffindbar.
2. **Zu breites Fangen verdeckt Programmfehler.** Gegenmittel wie in AG2: Ausnahmetyp
   in die Protokollzeile. Ausserdem greift der Fang nur um die zwei
   `fromisoformat`-Zeilen, nicht um die ganze Funktion.
3. **Wo protokollieren?** `is_quiet_hours()` ist `@staticmethod` und kennt weder
   Preset- noch Trip-Kennung. Ohne Kennung ist die Warnung im Betrieb schwer zuzuordnen
   (Aufloesung in der Analyse-Phase: optionaler Kennungs-Parameter vs. Aufrufer
   protokolliert selbst).
4. **Rueckbau in `compare_alert.py`** beruehrt frisch abgenommenen Code aus #1467 AG2.
   Muss durch dieselben Tests gedeckt bleiben, die AG2 gruen halten — der
   F001/F003-Test dort MUSS ohne Aenderung weiterlaufen.
5. **Keine Eingabepruefung beim Speichern** — dass ein unbrauchbarer Wert ueberhaupt in
   der Datei landen kann, bleibt bestehen. Das ist ein eigener Befund (Frontend/Go),
   **nicht** Teil dieser Scheibe.
6. **LoC-Limit 250** — Rueckbau wirkt gegen den Zaehler; Testdateien tragen den
   Hauptanteil.

## Analysis

### Type

**Bug** — ausbleibende Alarme durch ungefangene Ausnahme. Kein neues Verhalten.

### Technical Approach (Empfehlung)

**Die geteilte Funktion faengt selbst.** `DeviationAlertEngine.is_quiet_hours()`
umschliesst die beiden `fromisoformat`-Zeilen mit `try/except Exception`, protokolliert
`logger.warning` inkl. **Ausnahmetyp** und beiden Rohwerten und gibt `False` zurueck
(= „keine Ruhezeit gesetzt"). Bewusst nur diese zwei Zeilen im `try`, nicht die ganze
Funktion — die Zeitzonen-Umrechnung darf weiter laut scheitern.

**Zuordenbarkeit der Protokollzeile** (offene Frage 3 aus dem Kontext, entschieden):
optionaler letzter Parameter `context_label: str = ""`, den jede der sechs
Aufrufstellen mit ihrer Kennung fuellt (Preset-Kennung bzw. Trip-Kennung). Verworfene
Alternativen: Kennung ins `AlertEvaluationConfig` legen (mehr Oberflaeche, nutzt nur
dem einen Pfad) · ohne Kennung protokollieren (im Betrieb nicht zuzuordnen) · jeder
Aufrufer faengt selbst (= die vom PO verworfene Kopier-Loesung).

**Rueckbau:** `compare_alert.py:161-181` faellt weg — `try/except`, Protokollzeile und
die Neutralisierung von `config.quiet_from/to`. Letztere existiert nur, weil
`evaluate()` (`:243`) denselben Aufruf wiederholt und dort erneut werfen wuerde; nach
der Haertung wirft dort nichts mehr. Der F001/F003-Test aus AG2 bleibt unveraendert und
MUSS weiter gruen sein — er ist der Beweis, dass der Rueckbau nichts verliert.

### Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `src/services/deviation_alert_engine.py` | MODIFY | `try/except` + `logger.warning` + `context_label`-Parameter |
| `src/services/compare_alert.py` | MODIFY | Behelfs-Schutz zurueckbauen, Kennung durchreichen |
| `src/services/compare_official_alert.py` | MODIFY | Kennung durchreichen |
| `src/services/compare_radar_alert.py` | MODIFY | Kennung durchreichen |
| `src/services/trip_alert.py` | MODIFY | Kennung durchreichen (Adapter `_is_quiet_hours`) |
| `tests/tdd/test_alert_quiet_hours_robustness.py` | CREATE | Nachweis je Pfad (Namensregel: Verhalten, nicht Issue-Nummer) |

### Scope Assessment

- Dateien: 5 MODIFY + 1 CREATE
- LoC: Produktivcode etwa **+20 / −25** (Rueckbau ueberwiegt), Tests etwa **+220**
- Risiko: **MITTEL** — kritischer Pfad, aber die Aenderung erweitert ausschliesslich die
  Toleranz; kein bestehender Test schreibt die Ausnahme-Semantik fest
- **Kein Go, kein Frontend** — reine Python-Aenderung

### Risiko: was koennte brechen?

1. Zu breites `except` verschluckt einen echten Programmfehler ⇒ Gegenmittel:
   Ausnahmetyp im Protokoll, enger `try`-Block.
2. Rueckbau in `compare_alert.py` entfernt versehentlich mehr als den Behelf ⇒
   Gegenmittel: AG2-Test unveraendert laufen lassen.
3. Signatur-Erweiterung bricht einen Aufrufer ⇒ Gegenmittel: Parameter ist optional mit
   Vorgabewert; `grep` deckt alle sechs Stellen ab.

### Open Questions

Keine offenen Fragen an den PO. Die einzige Entscheidung (Wurzel-Fix statt Kopie) ist
am 2026-08-03 getroffen; die Protokoll-Zuordnung ist eine technische Detailfrage und
oben entschieden.

## Nicht in dieser Scheibe

- Eingabepruefung/Validierung beim Speichern (Go-Handler / Frontend)
- Reihenfolge-Frage „Ruhezeit vor dem Wetterabruf" fuer den Nowcast-Pfad — die gehoert
  zu #1467 S3
- `api/routers/scheduler.py` zusaetzlich absichern: nach dem Wurzel-Fix ohne Wirkung
  fuer diesen Fehlerfall; in der Analyse zu entscheiden, ob trotzdem sinnvoll
