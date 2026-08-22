---
entity_id: fix_2075_ende_am_radar_horizont
type: module
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [alarm, nowcast, radar, dauer, ende, bugfix]
---

# Blockende zu nah am Radar-Horizont wird zur Untergrenze verfälscht — #2075

## Approval

- [x] Approved (PO, 2026-08-22)

## Purpose

`_derive_wet_block_end` (Issue #2051 S1) leitet das Ende eines nassen Blocks
aus der bereits abgerufenen Frame-Zeitreihe ab und rechnet dabei — anders als
seine beiden Geschwister `_accumulate_precip_mm` und `_laufendes_frame` — den
nächsten Frame-Nachbarn nicht in die Deckungsgrenze ein. Endet der Regen
innerhalb der letzten `_MAX_FRAME_COVERAGE` (15 Min) vor dem Horizont, meldet
der Dienst deshalb `Regen mindestens bis <Horizont>` statt des echten, vom
Radar belegten Endes: bis zu 14 Minuten Regen zu viel, und eine belegte
Aussage erscheint als bloße Untergrenze statt als das, was sie ist. Gemessen
auf Staging bei der Verifikation von #2051 Scheibe 1. Dies ist ein
Umsetzungsfehler gegen die eigene Spec `feat_2051_s1_dauer_und_ende.md`
(Implementation Details schreiben die Nachbar-Deckung ausdrücklich vor), keine
offene Entwurfsfrage.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `_derive_wet_block_end` (Z. 278-341)

> **Schicht-Hinweis:** Python-Core (`src/services/`). Kein Go-API-, kein
> Frontend-Anteil.

Begleitend, nur als Textkonsumenten betroffen (keine Änderung an ihnen
nötig): `src/output/renderers/alert/render.py` — Langform `_onset_end_suffix`
(ab Z. 546) und Kurzform `_sms_onset_ende` (ab Z. 796) entscheiden beide
allein an `event_ongoing_beyond_horizon`, das `_derive_wet_block_end`
zurückgibt.

## Estimated Scope

- **LoC:** ~3 Produktivcode, ~85 Test.
- **Files:** 2 (1 MODIFY, 1 CREATE).
- **Effort:** low.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_accumulate_precip_mm` | function (`radar_service.py:200-242`) | Funktionierendes Geschwister — rechnet den Nachbarn bereits korrekt in die Deckung ein (`min(next_ts_full, ts + _MAX_FRAME_COVERAGE, end)`, Z. 272). Vorbild für den Fix, nicht selbst betroffen. |
| `_laufendes_frame` | function (`radar_service.py:352-382`) | Drittes Geschwister (#2050 S2b) — rechnet den Nachbarn ebenfalls korrekt ein. Ebenfalls nur Vorbild, nicht betroffen. |
| `_MAX_FRAME_COVERAGE` / `_DRY_THRESHOLD_MM_H` | constants (`radar_service.py:95,122`) | Bleiben unverändert — keine neue Toleranzzahl. |
| Onset-Zweig / `already_running`-Zweig | call sites (`radar_service.py:1014`, `1031`) | Beide Aufrufer von `_derive_wet_block_end` — der Fix wirkt in beiden. Der `already_running`-Zweig (#2050 S2b) maximiert das Ergebnis zusätzlich gegen die Deckungsgrenze des laufenden Frames (`max(_end_ts, _laufend[3])`), das bleibt unverändert. |
| `event_end_minutes` / `event_ongoing_beyond_horizon` | fields (`NowcastResult`, #2051 S1) | Downstream-Felder, unverändert im Namen und Datentyp — nur ihr Wert in der betroffenen Zone ändert sich. |

## Implementation Details

`_derive_wet_block_end` bildet je nassem Frame eine `coverage_end` aus dessen
eigener Deckung (`ts + _MAX_FRAME_COVERAGE`), gedeckelt auf den Horizont —
ermittelt aber unmittelbar danach `next_ts` (Zeitstempel des nächsten
Frame-Nachbarn, `bisect_right` über `all_ts_sorted`), ohne ihn einzurechnen.
Der Fix besteht aus **zwei** Teilen — der im Ticket vorgeschlagene Einzeiler
(Teil 1 allein) hält der Gegenprobe am Randfall `T = 13:33` **nicht** stand
(siehe AC-2):

```python
coverage_end = min(ts + _MAX_FRAME_COVERAGE, horizon)
next_idx = bisect.bisect_right(all_ts_sorted, ts)
next_ts = all_ts_sorted[next_idx] if next_idx < len(all_ts_sorted) else None

# Teil 1: den Nachbarn in die Deckungsgrenze einrechnen -- dieselbe
# Nachbar-Deckungslogik wie in `_accumulate_precip_mm` und `_laufendes_frame`.
if next_ts is not None:
    coverage_end = min(coverage_end, next_ts)

# Teil 2: der Horizont-Zweig darf nur noch greifen, wenn wirklich KEIN Frame
# mehr innerhalb des Fensters folgt -- sonst kippt ein Trockenframe exakt AUF
# dem Horizont den Zweig faelschlich in "ongoing", bevor er ausgewertet wird.
if coverage_end >= horizon and (next_ts is None or next_ts > horizon):
    return horizon, True
if next_ts is None:
    return coverage_end, True
if next_ts > coverage_end:
    return coverage_end, False
```

Teil 1 allein schließt die fehlerhafte Zone `T = 13:21 … 13:31` (Nachbar
jenseits des reinen `coverage_end`-Deckels, aber innerhalb des Horizonts).
Teil 2 ist zusätzlich nötig für `T = 13:33`: dort liegt der nächste
(trockene) Frame exakt auf dem Horizont, `coverage_end` bleibt nach Teil 1
`== horizon`, und ohne Teil 2 griffe der Horizont-Zweig weiterhin, bevor der
trockene Frame bei 13:35 überhaupt ausgewertet wird. Beide Teile zusammen
sind die vollständige Angleichung an die beiden funktionierenden Geschwister
— kein neuer Mechanismus, keine neue Zahl.

## Expected Behavior

- **Input:** dieselbe Frame-Zeitreihe wie heute (`frames`, `all_ts_sorted`,
  `onset_ts`, `horizon`) — kein zusätzlicher Quellenabruf, keine geänderte
  Signatur.
- **Output:** `_derive_wet_block_end` nennt in der Zone `horizon - 14min …
  horizon - 2min` (gemessen: `T = 13:21 … 13:31` bei `horizon = 13:35`) das
  echte, vom Radar belegte Ende (`last_wet_ts, False`) statt fälschlich
  `(horizon, True)`. Alle Bestandsfälle außerhalb dieser Zone bleiben
  unverändert.
- **Side effects:** keine — reine Korrektur der Grenzfindung innerhalb einer
  bestehenden, additiv eingeführten Funktion. Kein Datenmodell-Bruch, keine
  Persistenz betroffen, keine Änderung an der Auslöseregel.

## Acceptance Criteria

- **AC-1:** Given eine Frame-Zeitreihe im 2-Minuten-Raster (Beginn 10:55,
  `now = 10:35`, `horizon = 13:35`), deren letzter nasser Frame `T` einen Wert
  aus `{13:21, 13:23, 13:25, 13:27, 13:29, 13:31}` trägt und danach nur noch
  trockene bzw. keine weiteren Frames folgen / When `_derive_wet_block_end`
  für jeden dieser sechs Werte einzeln ausgewertet wird / Then ist das
  zurückgegebene Ende in JEDEM der sechs Fälle exakt `T`, und
  `ongoing_beyond_horizon` ist `False` — nicht `(horizon, True)`. Diese Zone
  wird bewusst als Fläche geprüft, nicht als Einzelpunkt: #2051 S1 hatte je
  ein Kriterium an den beiden Rändern (deutlich vor dem Horizont bzw. bis zum
  Horizont durchgehend nass) und ließ die Fläche dazwischen ungeprüft — genau
  dort lag der Fehler.
  - Test: parametrisierter Unit-Test gegen `_derive_wet_block_end` mit den
    sechs `T`-Werten, je Wert `(end_ts, ongoing)` gegen `(T, False)` geprüft.

- **AC-2:** Given denselben Rahmen wie AC-1, aber mit `T = 13:33` und einem
  tatsächlich vorhandenen, trockenen Frame exakt auf dem Horizont (13:35) /
  When `_derive_wet_block_end` ausgewertet wird / Then ist das Ende `13:33`
  und `ongoing_beyond_horizon = False` — nicht `(horizon, True)`. Dieser Fall
  wird von Teil 1 der Lösung allein NICHT repariert (`coverage_end` bleibt
  nach der Nachbar-Einrechnung `== horizon`); erst Teil 2 (Horizont-Zweig nur
  bei fehlendem Folge-Frame) schließt ihn.
  - Test: Unit-Test mit explizitem Trockenframe auf dem Horizont-Zeitstempel,
    `(end_ts, ongoing)` gegen `(13:33, False)` geprüft.

- **AC-3:** Given eine Frame-Zeitreihe, die durchgehend nass bis zum Horizont
  reicht (kein Trockenframe im gesamten Fenster, letzter bekannter Frame
  liegt auf oder nach `horizon - _MAX_FRAME_COVERAGE`) / When
  `_derive_wet_block_end` ausgewertet wird / Then bleibt das Ergebnis
  `(horizon, True)` — unverändert gegenüber dem heutigen Verhalten. Der Fix
  darf diesen Fall nicht berühren.
  - Test: Regressionstest (Bestandsfixture aus
    `test_nowcast_blockende_horizont_waechter.py`), `(end_ts, ongoing)` gegen
    `(horizon, True)` geprüft.

- **AC-4:** Given eine Frame-Zeitreihe, die vor dem Horizont abbricht (kein
  weiterer Frame-Eintrag in `all_ts_sorted` nach dem letzten bekannten Frame),
  während dieser letzte bekannte Frame noch nass ist / When
  `_derive_wet_block_end` ausgewertet wird / Then bleibt das Ergebnis
  `(coverage_end, True)` an der Deckungsgrenze des letzten Frames —
  unverändert gegenüber dem heutigen Verhalten.
  - Test: Regressionstest (Bestandsfixture, abgeschnittene Zeitreihe),
    `(end_ts, ongoing)` gegen `(letzter_frame + 15min, True)` geprüft.

- **AC-5:** Given eine Frame-Zeitreihe, deren letzter nasser Frame um 13:30
  liegt und deren nächster (trockener) Frame erst bei 13:40 folgt — also
  JENSEITS des Horizonts (13:35) / When `_derive_wet_block_end` ausgewertet
  wird / Then bleibt das Ergebnis `(horizon, True)` — der Fix darf hier weder
  auf 13:40 kippen (das wäre eine Aussage über unbeobachtete Zeit, die das
  Radar zwischen 13:35 und 13:40 nicht belegt) noch auf einen früheren Wert
  als den Horizont.
  - Test: Unit-Test mit Nachbar-Frame jenseits des Horizonts,
    `(end_ts, ongoing)` gegen `(horizon, True)` geprüft.

- **AC-6:** Given einen nassen Block mit einer Datenlücke innerhalb der
  `_MAX_FRAME_COVERAGE`-Deckung (Lücke ≤ 15 Min) sowie mit einer Datenlücke
  größer als die Deckung (> 15 Min), jeweils gefolgt von einem erneut nassen
  bzw. keinem weiteren Frame / When `_derive_wet_block_end` beide Fälle
  auswertet / Then läuft der Block bei der kleinen Lücke unverändert weiter
  (Ende beim späteren nassen Frame), bei der großen Lücke endet er an der
  Deckungsgrenze des Frames vor der Lücke (`ongoing_beyond_horizon = False`)
  — beide Fälle unverändert gegenüber dem heutigen Verhalten.
  - Test: Regressionslauf der Bestandsfixtures aus
    `test_nowcast_blockende_datenluecke.py`, keine inhaltliche Anpassung.

- **AC-7:** Given zwei getrennte nasse Blöcke in derselben Frame-Zeitreihe
  (Trockenframe zwischen ihnen) / When `_derive_wet_block_end` das Ende des
  ersten Blocks ableitet / Then endet der Block beim ersten Trockenframe —
  der zweite, spätere Block wird NICHT eingerechnet, die beiden verschmelzen
  weiterhin nicht zu einer überlangen Dauer.
  - Test: Regressionslauf der Bestandsfixture aus
    `test_nowcast_blockende_ableitung.py`, keine inhaltliche Anpassung.

- **AC-8:** Given den Aufbau aus AC-1 (`T` in der Zone `13:21 … 13:31`) / When
  die Langform (`_onset_end_suffix`) und die Kurzform (`_sms_onset_ende`)
  gerendert werden / Then enthält die Langform `letzter Regen gegen HH:MM`
  und die Kurzform `@HH:MM` (ohne führendes ` >`) — NICHT die
  Untergrenzen-Formen `Regen mindestens bis HH:MM` bzw. ` >@HH:MM`. Der
  Fehler wirkt bis in den gerenderten Text durch, nicht nur in den
  Rückgabewerten der Ableitungsfunktion.
  - Test: Unit-Test gegen `_onset_end_suffix` und `_sms_onset_ende` mit einem
    `OnsetEvent`, dessen `event_end_time`/`event_ongoing_beyond_horizon` aus
    einem AC-1-Fall stammen; Substring-Prüfung auf die Normalform, Negativ-
    Prüfung auf die Untergrenzen-Form.

- **AC-9:** Given die drei Lagen (A/B/C) aus
  `tests/tdd/test_alarm_szenario_laufendes_ereignis.py` (#2050 S2b; Lage A und
  B laufen über den Onset-Zweig, nur Lage C über `already_running` — letzter
  Frame jeweils 37 Minuten vor dem Horizont, außerhalb der fehlerhaften Zone) / When die volle Bestandstestdatei nach
  dem Fix läuft / Then bleiben alle drei Lagen unverändert grün — nachgerechnet
  betroffen ist keine von ihnen, weil im offenen Intervall
  `(Horizont − 15 min, Horizont]` in keiner der drei Lagen ein Frame liegt.
  Dieses AC sichert die Nicht-Betroffenheit ab, statt sie nur zu behaupten.
  - Test: Regressionslauf von
    `test_alarm_szenario_laufendes_ereignis.py` in voller Länge, 0 neue rote
    Fälle.

## Known Limitations

- **Keine Umkehr der Sicherheitsrichtung.** Der Fehler übertreibt die
  Regendauer, verharmlost sie nie (bis zu 14 Minuten zu viel gemeldet). Der
  Fix dreht diese Richtung nicht um: er kann das gemeldete Ende nur nach
  vorn (näher an die letzte tatsächliche Beobachtung) korrigieren, niemals
  ein Ende behaupten, das das Radar nicht belegt. Unbeobachtete Zeit
  (jenseits des Horizonts, in einer Datenlücke) bleibt unbeobachtet und wird
  weiterhin nicht als Ende ausgegeben.
- **R4 bleibt strukturell** (wie bereits in `feat_2051_s1_dauer_und_ende.md`
  festgehalten): jenseits von 180 Minuten (`_NOWCAST_HORIZON_MIN`) bleibt das
  tatsächliche Ende grundsätzlich unbekannt. Diese Arbeit ändert daran
  nichts — sie korrigiert ausschließlich die Grenzfindung innerhalb des
  bereits beobachteten Fensters.
- **Abhängig vom Quellenraster** wie schon in #2051 S1: bei gröberem Raster
  (bis 15 Min Kadenz) kann das abgeleitete Ende weiterhin um bis zu
  `_MAX_FRAME_COVERAGE` von der Wirklichkeit abweichen — diese Toleranz wird
  durch den Fix nicht verändert, nur korrekt angewendet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Korrektur einer bestehenden, additiv
  eingeführten Funktion (#2051 S1) an die bereits etablierte
  Nachbar-Deckungslogik ihrer beiden Geschwister an. Kein neuer Mechanismus,
  keine neue Konstante, kein neues Feld, kein neuer Text — berührt keine der
  vier Entscheidungsflächen (Kanäle, Provider, Datenmodell/Persistenz, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie), die ein neues ADR verlangen
  würden.

## Changelog

- 2026-08-22: Initial spec created (#2075, Nachbesserung zu #2051 S1).
