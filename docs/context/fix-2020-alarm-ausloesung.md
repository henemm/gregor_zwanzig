# Context: #2020 — Auslösung des Regen-Alarms (Scheibe 1)

Issue: [#2020](https://github.com/henemm/gregor_zwanzig/issues/2020) · `priority:critical`
Umgeschnitten auf PO-Entscheid 2026-08-21. Vorgänger-Analyse (Formulierung → **Scheibe 2**):
`docs/context/fix-2020-alarm-zeitangaben.md`, Spec dazu
`docs/specs/modules/fix_2020_alarm_zeitangaben.md` (freigegeben, **zurückgestellt**).

## Die Leitfrage des PO

> Hilft diese Information dem Nutzer? Warum hat er sie nicht bekommen, als sie ihm
> genutzt hätte? Und warum gab es keinen Nowcast — hat es überhaupt geregnet?

## Nachtrag: Was wirklich gefallen ist

Abgerufen 2026-08-21 über die Open-Meteo-Rückschau für den Ziel-Wegpunkt G4
(46.73042 / 12.321643, Innichen), Tag 2026-08-20, Ortszeit:

| Zeit | Regen | | Zeit | Regen |
|---|---|---|---|---|
| 11:00 | 0,1 mm | | 16:00 | 3,2 mm |
| 12:00 | 0,1 mm | | 17:00 | 0,7 mm |
| **13:00** | **9,7 mm** | | 18:00 | 0,4 mm |
| 14:00 | 0,0 mm | | 21:00 | 1,8 mm |
| **15:00** | **11,5 mm** | | 22:00 | 3,9 mm |
| | | | **Tag** | **33,1 mm** |

**Es hat geregnet — kräftig, und mehr als vorhergesagt** (33,1 mm tatsächlich gegen
29,4 mm prognostiziert). Der Alarm war inhaltlich vollständig berechtigt. Die
Vorhersage war nicht das Problem.

**Aber die Zeitachse entwertet ihn:** Der Wanderer erreichte das Ziel laut Plan um
11:33. Der erste schwere Guss fiel um **13:00 (9,7 mm)**, die stärkste Stunde war
**15:00 (11,5 mm)**. Die erste Alarm-Mail ging um **15:30** raus — nach dem ersten Guss,
mitten im Höhepunkt. Die zweite um 18:15, bitgleich, als es praktisch vorbei war.

**Antwort auf die Leitfrage: Nein, die Information hat nicht genützt** — auch korrekt
formuliert nicht. Um zu helfen, hätte die Warnung vor etwa 10:00 kommen müssen, solange
er noch ging und entscheiden konnte.

Was er am Vormittag stattdessen bekam (aus `alert_log.json`): drei Gewitter-Alarme
(07:31, 09:01, 11:01 UTC), der um 11:01 meldete eine **sinkende** Gewitterneigung
(`thunder` 3,0 → 1,0). Zwei Stunden später fielen 9,7 mm in einer Stunde.

## Korrektur einer früheren eigenen Aussage

In der Erstanalyse stand, die Meldung sei „so früh wie technisch möglich" gekommen.
**Das war zu weit gegriffen.** Belegt ist nur, dass der 15-Minuten-Prüfzyklus keine
Lücke hat (`scheduler.go:192`, kein Ergebnis-Cache, `trip_alert.py:1537-1564`). Die
**Auslöseschwelle** war dabei nicht betrachtet — und genau dort liegt die Ursache.

## Befunde zur Auslösung

**A1 — Die Δ-Schwelle ist absolut und verschluckt relative Sprünge.**
Regel des Trips: `{kind: delta, metric: precipitation_sum, threshold: 10, unit: mm}`.
Geprüft wird `abs(delta) > threshold` gegen die **den ganzen Tag stehende** Morgenbasis
von 7,4 mm (`weather_change_detection.py:631-667`; Basis fix laut
`trip_alert.py:412-413`, #1916). Es feuert also erst oberhalb von **17,4 mm**. Ein
Anstieg von 7,4 auf 16 mm — mehr als eine Verdopplung — bleibt **stumm**.
Bittere Pointe: die Mail titelt selbst mit **„+297 %"**; das Produkt denkt längst in
Prozent, ausgelöst wird über eine absolute Millimeterzahl.
**Nicht beweisbar, aber auch nicht ausgeschlossen:** Zwischenstände der Vorhersage
werden nirgends aufgezeichnet (`alert_log.json` protokolliert nur ausgelöste Alarme;
`diagnostics/alert_anchor_rejected.jsonl` hat für 2026-08-20 keine Einträge). Der
Mechanismus passt exakt zum Symptom.

**A2 — Absolute Regeln werden auf dem Alarmpfad NIE ausgewertet. 🔴**
`_detect_absolute_changes()` existiert, wird aber vom Alarmpfad ausgeschaltet:
`trip_alert.py:1059` und `deviation_alert_engine.py:213` rufen beide
`detect_changes(..., include_absolute=False)` (#816). Der Alarm kann damit **nur** sagen
„es hat sich seit heute früh um mehr als X geändert" — **niemals** „es ist jetzt
gefährlich viel". Selbst eine konfigurierte Regel „warne bei über 20 mm" könnte auf
diesem Pfad nicht feuern. Das ist der vermutlich tiefste Grund dafür, dass an einem Tag
mit 33 mm keine brauchbare Warnung kam.
*Vor der Spec zu verifizieren:* ob es einen anderen Pfad gibt, der absolute Regeln für
Alarme auswertet — der Befund stützt sich bisher auf die Aufrufstellen, nicht auf einen
Negativ-Nachweis über alle Aufrufer.

**A3 — Die Nowcast-Unterdrückung prüft nicht, wie weit die Wirklichkeit die
Ankündigung überholt.**
`trip_alert.py:1330`: `if _briefing_announced and not result.is_convective: continue`,
wobei `_briefing_announced = (_briefing_precip is not None and _briefing_precip >= 0.5)`
(`trip_alert.py:1326`). Angekündigt waren **7,4 mm**, gefallen sind **33 mm** — eine
Vervierfachung wurde als „schon bekannt" abgetan. Nur konvektive Lagen (Gewitter/Hagel)
durchbrechen die Sperre (#883 Slice 4). Zusätzlich: die Unterdrückung schreibt nur
`logger.debug`, **keinen** `alert_log`-Eintrag — sie ist im Protokoll unsichtbar.

## Was zu messen ist, BEVOR eine Schwelle festgelegt wird

Eine relative Schwelle ohne Untergrenze ist gefährlich: 0,1 → 0,4 mm sind +300 % und
völlig belanglos. Zwei Messungen gehören daher in die Analyse-Phase:

1. **Hebelwirkung, nicht Verschärfung.** Für jede Kandidaten-Regel auszählen, wie oft
   sie über echte Vorhersagereihen **allein** ausgelöst hätte — also zusätzlich zu dem,
   was die heutige 10-mm-Regel ohnehin fängt. Eine Regel, die nur mitfeuert, bringt
   nichts.
2. **Flutrisiko.** Dieselbe Auszählung als Alarmzahl pro Tag und Trip. Vor Tourstart
   ist ein flutender Alarm schlimmer als ein stummer.

Datenquelle: echte Open-Meteo-Reihen für die KHW-Wegpunkte über mehrere Tage,
deterministisch als Fixture abgelegt — Zwischenstände aus der Vergangenheit sind nicht
rekonstruierbar (siehe A1).

**Falle aus dem Projektgedächtnis:** Relatives und absolutes Band überholen sich an der
Naht. Der Wächter über eine kombinierte Regel muss **Monotonie** prüfen — ein größerer
Sprung darf nie zu einer schwächeren Meldung führen als ein kleinerer.

## Zuschnitt

**Scheibe 1 (dieses Ticket):** Auslösung — A1/A2 (Schwellenmechanik) und A3
(Nowcast-Unterdrückung + ihre Sichtbarkeit im Protokoll).
**Scheibe 2 (zurückgestellt):** Formulierung der Zeitangaben — Spec liegt fertig und
validiert unter `docs/specs/modules/fix_2020_alarm_zeitangaben.md`.

**Weiterhin Nicht-Ziel:** die doppelte Zustellung um 15:30 und 18:15 (stehende
Vergleichsbasis) → **#2018** / **#1987**, die dortige Session hat die Belege.

## Nachbarschaft

`trip_alert.py` — **#2017 Scheibe B** (Session `intake-2017-b`) schreibt bei ~1259 und
ist laut Index in Phase TDD RED; A3 sitzt bei 1330. Vor der Umsetzung abstimmen.
