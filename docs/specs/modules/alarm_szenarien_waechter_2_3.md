---
entity_id: alarm_szenarien_waechter_2_3
type: feature
created: 2026-08-22
updated: 2026-08-22
status: approved
workflow: feat-2050-s2a-waechter-szenarien-2-3
version: "1.0"
tags: [alarm, testing, harness]
---

# Alarm-Szenarien 2 und 3 als Wächter auf der Prüfstrecke (Scheibe S2a, Issue #2050)

## Approval

- [x] Approved — PO ("Approved"), 2026-08-22

## Purpose

Zwei der zwölf Alarm-Szenarien aus Issue #2050 haben heute Testabdeckung, aber auf einer Ebene,
die die eigentliche Zusicherung nicht erreicht (Szenario 2: keiner der 17 Tests fährt eine
Zeitreihe mit Gedächtnis; Szenario 3: keiner der 10 Tests läuft über die echte
Auslöseentscheidung). Diese Scheibe stellt genau diese Lücke als zwei dauerhafte Wächter auf die
in S1 gebaute `AlarmPruefstrecke` — ohne Produktivcode zu ändern und ohne die bestehenden
17+10 Tests anzufassen.

## Source

- **File (neu):** `tests/tdd/test_alarm_szenario_briefing_ueberholung_zeitreihe.py` (Wächter 1,
  Szenario 2), `tests/tdd/test_alarm_szenario_gewitter_vorverlegung.py` (Wächter 2,
  Szenario 3)
- **Identifier:** keine neuen Produktiv-Symbole — beide Dateien nutzen ausschließlich
  `AlarmPruefstrecke`/`AlarmPruefstreckeLauf` (`tests/helpers/alarm_pruefstrecke.py`) und
  bestehende produktive Schreibwege (`WeatherSnapshotService.save_dated`, `alert_log`).

> **Korrektur beim Bau (2026-08-22):** Der Briefing-Anker wird über `save_dated()` gesetzt, nicht
> über `save_alarm_anchor()`. Der Radar-Zweig liest den Briefing-Wert über
> `WeatherSnapshotService(...).load_dated(trip.id, segment_date)` (`trip_alert.py:1362`);
> `save_alarm_anchor()` schreibt eine andere Datei (`{trip_id}_alarm_anchor_{channel}.json`), die
> nur `load_alarm_anchor` liest. Über den falschen Weg wäre AC-1 **still grün** geworden — ohne
> Briefing greift `_briefing_announced` nicht, der Alarm feuert dann ohne jede Überholung und der
> Wächter hätte nichts bewacht.

> Schicht: Python-Core-Testinfrastruktur (`tests/tdd/`) — kein Produktivcode in `src/`/`api/`
> wird geändert, kein Go-/Frontend-Anteil.

## Estimated Scope

- **LoC:** ~250-320 (zwei Testdateien, je ~110-180 Zeilen: Wächter 1 braucht Trip- und
  Snapshot-Aufbau plus vier `lauf()`-Aufrufe mit Log-Auswertung, Wächter 2 braucht
  Wetter-Fixtures mit `thunder_onset_utc` plus zwei `lauf()`-Aufrufe). Kann das
  250-LoC-Standardlimit reißen — ggf. `loc_limit_override` wie in S1 (dort 500) nötig.
- **Files:** 2 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke.lauf` | function | Der Harness selbst — beide Wächter rufen ausschließlich `.lauf(...)`, kein eigener Aufbau der Auslöseentscheidung |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstreckeLauf` | dataclass | Ergebnisobjekt (`triggered_count`, `mail`, `telegram`, `sms`, `premium_sms`) |
| `src/services/trip_alert.py::TripAlertService.check_radar_alerts` (`:1140-1623`) | method | Einstiegspunkt für Wächter 1 (`zweig="radar"`) — Überholungsprüfung `:1370-1402`, Cooldown-Gate `:1239-1273`, Buchung nach Zustellung `:1607-1612` |
| `src/services/trip_alert.py::TripAlertService.check_and_send_alerts` (`:216-456`) | method | Einstiegspunkt für Wächter 2 (`zweig="deviation"`) |
| `src/services/deviation_alert_engine.py::DeviationAlertEngine._select_detector` (`:175-204`) | method | Die Konfigurations-Weiche, die Wächter 2 gezielt prüft — wertet `thunder_onset` nur bei aktivem `metric_alert_levels`-Eintrag aus |
| `src/services/alert_gate.py::check_nowcast_gate` (`:140-184`) | function | Liefert bei aktiver Sperrzeit `GateResult(False, REASON_COOLDOWN)` — die Sperre, die Lauf 2 in Wächter 1 zum Schweigen bringt |
| `src/services/alert_log.py::append_suppressed_entry`/`read_undelivered` | function | Schreib-/Leseweg des Unterdrückungsprotokolls, über das Lauf 2 seinen Unterdrückungsgrund nachweist |
| `tests/helpers/nowcast_gate_fixtures.py::make_trip`/`frozen_active_window` | function | **Nur lesen/importieren**, nicht ändern (belegt durch Session #2036). Liefert Trip-Fixture und gestellte Uhr im garantiert aktiven Fenster |
| `tests/tdd/test_nowcast_briefing_overtake.py` (nicht geändert) | reference | Fixture-Muster für Snapshot-Aufbau (`_write_snapshot`) und Frame-Quellen für Radar-Überholung — als Vorbild lesen, nicht importieren (eigener `uid` je Wächter) |
| `tests/tdd/test_onset_shift_alert.py` (nicht geändert) | reference | Fixture-Muster für `thunder_onset_utc`-Wetterdaten und Textprüfung (Richtungswort, beide Uhrzeiten) — als Vorbild lesen, nicht importieren |

## Implementation Details

**Wächter 1 (`zweig="radar"`), eine `AlarmPruefstrecke` auf einer `user_id`, vier Läufe:**

1. Lauf 1: Briefing-Snapshot kündigt 1 mm an, Radar-Frames liefern 11 mm (Überholungsfaktor
   erfüllt, `trip_alert.py:1380-1384`) → Alarm.
2. Lauf 2: kurz danach, unveränderte Eingangsdaten (gleicher Snapshot, gleiche 11 mm) → schweigt.
   Da die Überholungsbedingung selbst unverändert erfüllt wäre, kann die Stille nur von der durch
   Lauf 1 gebuchten Sperre kommen (`record_nowcast_sent` → `ThrottleStore`, `trip_alert.py:1607`).
   Nachgewiesen über `alert_log.read_undelivered()`: der Eintrag trägt
   `reason == alert_log.REASON_NOWCAST` und `gate_reason == alert_log.REASON_COOLDOWN`
   ("cooldown") — unterscheidbar vom Unterdrückungsgrund einer unveränderten Lage, der als
   `"briefing_announced:<mm>mm"` protokolliert würde (`trip_alert.py:1390-1395`, Vorbild
   `test_ac6_remaining_suppression_creates_alert_log_entry`,
   `test_nowcast_briefing_overtake.py:799`).
3. Lauf 3: deutlich verschärfte Lage (höherer Regenwert), Uhr liegt weiterhin innerhalb des
   Sperrfensters aus Lauf 1 → kommt durch (Anforderung A-3).
4. Gegenprobe (vierter Lauf, **eigene** `user_id`, kein Bezug zu 1-3): kurze Spitze mit gleicher
   Spitzenrate wie eine auslösende Lage, aber zu geringer Gesamtmenge → `triggered_count == 0`.

Uhrzeiten aller Läufe liegen im garantiert aktiven Fenster (Vorbild `frozen_active_window()`,
Default 12:00 UTC) — kein Test hängt von der Wanduhr ab.

**Wächter 2 (`zweig="deviation"`), eine `AlarmPruefstrecke` auf eigener `user_id`, zwei Läufe:**

1. Trip mit `trip.display_config.metric_alert_levels["thunder_onset"]` auf einen Level ≠ "off"
   gesetzt. `cached_weather` trägt `thunder_onset_utc` = 17:00, `fresh_weather` = 15:00. Ein Lauf
   über `check_and_send_alerts(...)` → genau ein Alarm; der gerenderte Text (mind. ein Kanal)
   nennt beide Uhrzeiten (17 und 15 Uhr) und ein Richtungswort für die Vorverlegung (#1468-Bestand,
   geprüft am `→`-Symbol bzw. dem etablierten Richtungswort — **keine** Prüfung auf Formulierungen
   aus #2020 S2, s. Nicht-Ziele).
2. Negativprobe: derselbe Aufbau, aber `metric_alert_levels["thunder_onset"]` auf "off" (oder
   entfernt) → `triggered_count == 0`. Das nagelt `DeviationAlertEngine._select_detector`
   (`deviation_alert_engine.py:175-204`) fest, die heute kein Test erreicht (belegter Null-Treffer
   beim Grep über alle 41 Aufrufer von `check_and_send_alerts`, gefiltert auf `thunder_onset`).

## Expected Behavior

- **Input:** je Wächter ein `Trip`-Fixture (Vorbild `make_trip()`), zweigspezifische
  Eingangsdaten (Radar-Frames bzw. `cached_weather`/`fresh_weather`), gestellte Uhrzeiten im
  aktiven Fenster.
- **Output:** `AlarmPruefstreckeLauf` je Lauf (`triggered_count`, vier Kanal-Inhalte); bei
  Wächter 1 zusätzlich ein über `alert_log.read_undelivered()` gelesener Protokolleintrag mit
  benanntem Unterdrückungsgrund für Lauf 2.
- **Side effects:** reale Schreibvorgänge in die Zustandsspeicher unter dem pro-Test isolierten
  `get_data_dir(user_id)` (Cooldown, Alarm-Protokoll, Wetter-Snapshot) — kein echter
  Mail-/SMS-/Telegram-Versand.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Briefing 1 mm Regen ankündigte, während der Radar-Nowcast
  11 mm für dasselbe Fenster zeigt, When der erste Prüflauf über den Radar-Zweig fährt, Then
  löst der Lauf genau einen Alarm aus und alle vier Kanäle tragen den gerenderten Inhalt.
  - Test: `AlarmPruefstrecke.lauf(zweig="radar", ...)` mit Briefing-Snapshot 1 mm und
    Radar-Frames für 11 mm; `triggered_count == 1`, alle vier Kanal-Listen nicht leer.
  - Vorgeschalteter Sonden-Lauf (Fix-Loop 2026-08-22, Adversary-Finding F002): ein Lauf mit
    ~0,5 mm überholt die Ankündigung NICHT, muss schweigen und protokolliert dabei den vom
    Prüfling GELESENEN Briefing-Wert (`gate_reason` `briefing_announced:1.0mm`,
    `trip_alert.py:1393`, gelesen über `alert_log.read_undelivered()`). Damit ist die
    Ankündigung positiv nachgewiesen statt vorausgesetzt: bricht der Lesepfad
    (`load_dated`, `trip_alert.py:1363`), greift die Unterdrückung nicht mehr, der Sonden-Lauf
    löst aus und AC-1 wird rot — vorher blieb er in genau diesem Fall grün, weil ein Alarm
    ohne jede Überholung von einem Alarm wegen Überholung nicht unterscheidbar war.

- **AC-2:** Given der erste Prüflauf hat ausgelöst und dabei eine Sperrzeit gebucht, When ein
  zweiter Prüflauf mit unveränderter Lage (gleiches Briefing, gleicher Radar-Wert) kurz danach
  auf demselben Trip fährt, Then schweigt der zweite Lauf nachweislich WEGEN der gebuchten Sperre
  — nicht weil sich an der Wetterlage nichts geändert hätte: das Alarmprotokoll trägt für diesen
  Lauf einen Unterdrückungs-Eintrag mit dem Sperrzeit-Grund, unterscheidbar von dem Grund, den
  eine echte "Lage unverändert"-Unterdrückung protokollieren würde.
  - Test: Lauf 2 identisch zu Lauf 1 fahren, `triggered_count == 0`; über
    `alert_log.read_undelivered()` einen `REASON_NOWCAST`-Eintrag mit
    `gate_reason == alert_log.REASON_COOLDOWN` ("cooldown") nachweisen — NICHT mit einem
    `"briefing_announced:"`-Präfix, der die andere Unterdrückungsursache anzeigen würde.

- **AC-3:** ⚠️ **Gemessen rot am 2026-08-22 — ausgelagert nach Issue #2065, nicht Teil dieser
  Lieferung.** Der Wächter wurde gebaut, ausgeführt und schlägt fehl; die Zusicherung ist heute
  im Produktivcode nicht erfüllt (Details unter „Known Limitations"). Wortlaut zur
  Nachvollziehbarkeit:
  Given die Sperrzeit aus dem ersten Prüflauf ist zum Zeitpunkt des dritten Prüflaufs
  noch aktiv, When der dritte Prüflauf mit deutlich verschärfter Lage (höhere Regenmenge als in
  Lauf 1 und 2) fährt, Then löst dieser Lauf trotz der noch laufenden Sperre einen Alarm aus.
  - Test: dritter Lauf innerhalb desselben Sperrfensters mit verschärften Eingangsdaten fahren,
    `triggered_count >= 1` nachweisen. Bricht dieser Test strukturell (Sperrzeit-Gate liegt in
    `check_radar_alerts()` VOR der Überholungsprüfung und kennt keine Eskalations-Ausnahme,
    `trip_alert.py:1239-1273` vs. `:1380-1384`), ist das ein Befund für eine eigene Scheibe, nicht
    Anlass für Produktivcode in dieser Scheibe (s. Nicht-Ziele).

- **AC-4:** Given eine kurze Regenspitze mit derselben Spitzenrate wie eine auslösende Lage, aber
  einer Gesamtmenge unterhalb der Überholungs-Untergrenze, auf einem eigenen, von den ersten drei
  Läufen unabhängigen Trip, When ein einzelner Prüflauf über den Radar-Zweig fährt, Then bleibt
  der Lauf ohne Alarm.
  - Test: eigene `user_id`, ein `AlarmPruefstrecke.lauf(zweig="radar", ...)` mit Spitzenrate
    gleich einem Auslöse-Fall, aber zu geringer Gesamtmenge; `triggered_count == 0`.

- **AC-5:** Given ein Trip, bei dem der Alarmtyp "Gewitterbeginn" aktiv geschaltet ist und dessen
  zwischengespeicherte Wetterlage einen Gewitterbeginn um 17 Uhr zeigte, während die aktuelle
  Wetterlage denselben Gewitterbeginn auf 15 Uhr vorverlegt, When ein Prüflauf über den
  Änderungs-Zweig (die echte Auslöseentscheidung, nicht die Erkennungslogik allein) fährt, Then
  löst der Lauf genau einen Alarm aus.
  - Test: `AlarmPruefstrecke.lauf(zweig="deviation", cached_weather=..., fresh_weather=...)` mit
    `thunder_onset_utc` 17:00 → 15:00 und aktivem `metric_alert_levels["thunder_onset"]`;
    `triggered_count == 1`.

- **AC-6:** Given derselbe Vorverlegungs-Alarm aus AC-5, When der ausgelieferte Alarmtext gelesen
  wird, Then nennt der Text beide Uhrzeiten (17 Uhr und 15 Uhr) und macht durch ein Richtungswort
  bzw. das etablierte Pfeil-Symbol erkennbar, dass sich der Beginn nach VORNE verschoben hat.
  - Test: Text mindestens eines Kanals (z. B. `mail` oder `telegram`) aus AC-5s Lauf auf beide
    Uhrzeiten und Richtungsangabe prüfen — keine Prüfung auf Formulierungen, die #2020 Scheibe 2
    gerade ändert (s. Nicht-Ziele).

- **AC-7:** Given derselbe Trip und dieselbe Wetteränderung wie in AC-5, aber mit
  `metric_alert_levels["thunder_onset"]` abgeschaltet (Level "off" bzw. Eintrag entfernt), When
  derselbe Prüflauf über den Änderungs-Zweig fährt, Then löst der Lauf KEINEN Alarm aus — die
  Konfigurations-Weiche verhindert die Auswertung des Alarmtyps, obwohl die Wetterdaten
  unverändert einen Gewitterbeginn-Sprung zeigen.
  - Test: identischer Lauf zu AC-5 mit deaktiviertem `thunder_onset`-Level;
    `triggered_count == 0`.

- **AC-8:** Given ein Trip, dessen Briefing nur 0,5 mm ankündigte, und eine Radarlage von
  ~1,5 mm im Vergleichsfenster — die den Überholungs-FAKTOR damit deutlich überschreitet
  (2 × 0,5 mm = 1,0 mm), aber unter der absoluten Relevanz-Untergrenze von 2,0 mm bleibt, When
  ein einzelner Prüflauf über den Radar-Zweig fährt, Then bleibt der Lauf ohne Alarm, und das
  Alarmprotokoll weist die Briefing-Ankündigung als Grund aus.
  - Test: eigene `user_id`, Briefing-Snapshot 0,5 mm, Radar-Frames 9 mm/h über 10 Minuten;
    `triggered_count == 0`, kein Kanalinhalt, `briefing_announced:0.5mm` im
    Unterdrückungs-Protokoll. Die Faktor-Bedingung wird vor dem Lauf am echten
    `get_nowcast()`-Ergebnis gegen `trip_alert._BRIEFING_OVERTAKE_FACTOR` (Modul-Referenz)
    als ERFÜLLT nachgewiesen — sonst prüfte der Fall wieder nur den Faktor.
  - Warum zusätzlich zu AC-4 (Fix-Loop 2026-08-22, Adversary-Finding F001): die
    Überholungsprüfung ist eine UND-Verknüpfung aus Faktor-Schwelle und absoluter Untergrenze
    (`trip_alert.py:1381-1385`). AC-4s ~1,83 mm scheitern bereits am Faktor (2 × 1,0 mm), die
    absolute Untergrenze wird dort nie zur wirksamen Bedingung — ihr Wegfall
    (`_OVERTAKE_MIN_ABSOLUTE_MM = 0.0`) blieb von allen sechs Wächtern unbemerkt.

## Known Limitations

- **AC-3 ist gemessen rot und nach Issue #2065 ausgelagert (2026-08-22).** Der Wächter wurde
  gebaut und ausgeführt; er scheitert mit dem protokollierten Unterdrückungsgrund `cooldown`
  (`alert_log.REASON_COOLDOWN`), nicht mit `briefing_announced:`. Damit ist am Wirkort belegt,
  was die Analyse vermutet hatte: `check_nowcast_gate` prüft die Sperrzeit unbedingt VOR jeder
  Eskalations-/Überholungsbewertung (`trip_alert.py:1239-1273` vs. `:1381`) und nimmt keinen
  Parameter entgegen, über den es von einer Verschärfung erfahren könnte
  (`alert_gate.py:140-184`). **Anforderung A-3 aus #2050 ist damit verletzt** — ein
  Produktivfehler, kein Testproblem. Der Testcode liegt unverändert in #2065; diese Scheibe
  liefert ihn nicht mit, weil sie keinen Produktivcode ändert und ein roter Kerntest nicht
  mergefähig ist. Die Nummerierung der übrigen ACs bleibt unverändert, damit die Lücke sichtbar
  bleibt statt zu verschwinden.
- Abgrenzung dazu: #2020 Scheibe 1 hat die **Briefing-Ankündigungs-Sperre** bei
  Mengen-Überholung gebrochen, **nicht** den Cooldown nach einem eigenen Alarm. Wer #2020 S1 als
  „A-3 ist erledigt" liest, liegt falsch.
- `alert_state.reset()` verwirft `event_identity:`-Schlüssel still (`alert_state.py:38-45`,
  bereits in der S1-Spec vermerkt) — betrifft diese Scheibe nicht direkt, da keiner der beiden
  Wächter über eine Briefing-Grenze hinweg vorbelegten Zustand voraussetzt.

## Nicht Ziel

- Szenario 1 (B-1, "Regen läuft schon") — braucht Produktivcode und kollidiert mit #2020
  Scheibe 2, wird als eigene Scheibe **S2b** nachgezogen.
- Jede Änderung an Produktivcode (`src/`, `api/`).
- Änderungen an `tests/tdd/test_nowcast_briefing_overtake.py`,
  `tests/tdd/test_onset_shift_alert.py`, `tests/helpers/nowcast_gate_fixtures.py` (letztere durch
  Session #2036 belegt — lesen/importieren erlaubt, ändern nicht).
- Textprüfende Zusicherungen auf Formulierungen, die #2020 Scheibe 2 gerade ändert: Langform
  `Bis jetzt:`/`Ab jetzt:`, Kurzform-Token `Rest{mm}@{HH}`, Bedeutungswörter bei Zeitangaben.
- Ein Szenario für Etappen < 1 h (Nebenbefund aus #2020 S2, `trip_segments.py:294-311` vs.
  `:220-243`, Bug #856) — für eine spätere Scheibe vermerkt, nicht hier behandelt.
- Die verbleibenden zehn der zwölf Alarm-Szenarien aus #2050 (spätere Scheiben).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur ohne Produktivcode-Änderung, keine neue Route, kein
  neues Datenmodell, keine Rücknahme einer bestehenden Architekturentscheidung. Kein
  ADR-würdiger Grundsatzentscheid.

## Changelog

- 2026-08-22: Initial spec created (Scheibe S2a aus #2050, verdichtet aus
  `docs/context/feat-2050-s2a-waechter-szenarien-2-3.md`).
- 2026-08-22: Nach dem Bau — AC-3 gemessen rot, nach #2065 ausgelagert (Anforderung A-3 im
  Produktivcode verletzt). Dateinamen an die Umsetzung angeglichen. Briefing-Anker über
  `save_dated()` statt `save_alarm_anchor()` korrigiert; der ursprüngliche Weg hätte AC-1 still
  grün werden lassen. Lieferumfang damit 6 Wächter.
- 2026-08-22 (Fix-Loop nach Adversary-Verdict BROKEN): AC-8 ergänzt (absolute Untergrenze der
  Überholung unabhängig vom Faktor bewacht, F001) und AC-1 um den Sonden-Lauf erweitert
  (Briefing-Ankündigung positiv nachgewiesen statt vorausgesetzt, F002). Beide Mutationen sind
  jetzt gemessen rot — Nachweis in
  `docs/artifacts/feat-2050-s2a-waechter-szenarien-2-3/mutations-nachweis-fixloop.txt`.
  Lieferumfang damit 7 Wächter, weiterhin ohne jede Produktivcode-Änderung.
