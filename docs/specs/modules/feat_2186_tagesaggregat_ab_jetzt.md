---
entity_id: feat_2186_tagesaggregat_ab_jetzt
type: module
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [ad-hoc-abruf, timeline, tagesaggregat, telegram, email]
---

# Tagesaggregat ab Anfragezeitpunkt (Ad-hoc-Abruf)

## Approval

- [ ] Approved

## Purpose

Beim Ad-hoc-Abruf (`glance`, `heute_gewitter`, `timeline_heute`) rechnet das Tages-Aggregat
für „heute" bislang den bereits vergangenen Vormittag mit — ein Abruf um 14:00 zeigt noch den
Regen von 08:00. Diese Spec fenstert die Tages-Aggregatbildung auf `[jetzt … Segmentende]` und
lässt „morgen" dabei strukturell unberührt.

## Offene Produktentscheidungen

**(1) Was umfasst „heute"?**
Empfehlung: `[max(jetzt, Aufbruch) … Tagesfensterende]` — dasselbe Fenster wie heute, nur vorne
beschnitten (Schnittmenge aus Etappenfenster und `[jetzt … Ortsmitternacht]`).

Verworfene Alternativen:
- *Bis Ortsmitternacht:* zöge die Nachtstunden ins Tagesaggregat herein — widerspricht dem 3×
  bestätigten PO-Entscheid „strikt nur Tagesfenster" (#1841/#1848) und der Abwehr aus #1653.
- *Feste 04–19 Uhr nach ADR-0035:* zöge Stunden **vor** dem tatsächlichen Aufbruch neu herein —
  eine eigene Produktänderung, die hier nicht verlangt ist.
- *Feste 12 Stunden Dauer:* `glance` zeigt „heute" und „morgen" nebeneinander — ab dem
  Nachmittag enthielten beide Zeilen dieselben Stunden.

**(2) Abruf nach Tagesfensterende, wenn nichts mehr übrig ist.**
Empfehlung: **Fehlanzeige** statt eines Werts aus vergangenen Stunden — ein Wert würde
Gültigkeit für ein Fenster behaupten, das nicht mehr existiert (Linie aus #2167: nie Gültigkeit
für Ungemessenes behaupten; ADR-0007: nur Daten, keine Handlungsempfehlung).

## Source

- **File:** `src/services/weather_extractor.py`
- **Identifier:** `timeline()`, `_punkte()` (`:102-116`)

> Python-Core / Domain-Backend (`src/services/`). Zusätzlich betroffen:
> `src/services/trip_command_processor.py:802`/`:806` (Aufrufer, `from_time=received_at`).

## Estimated Scope

- **LoC:** Produktivcode ca. +40/-5, Tests +150–200
- **Files:** 2 Produktivdateien, 2 neue Testdateien, 1 erweiterte Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/day_window.py:89` `segment_window_points()` | Helper | Exakter Stundenschnitt `[start_floor, end_floor)` — Pflicht, keine eigene Nachrechnung (Bug #806/#856) |
| `src/services/segment_weather.py:310/:314` | Rechenkette | `compute_basis_metrics()` → `compute_extended_metrics()` — beide Stufen, in dieser Reihenfolge |
| `src/services/weather_metrics.py:462/:1156` | Helper | `compute_basis_metrics()`, `compute_extended_metrics()` (bildet u.a. `pop_max_pct`) |
| `src/services/trip_command_processor.py:761` `_handle_query()` | Aufrufer | Hält `received_at`, ruft `timeline()` genau einmal, reicht Ergebnis an alle 5 Ausgabestellen |
| `src/services/trip_command_processor.py:104/:111` `_BARE_KEYWORD_MAP` | Aufrufer | Macht `glance`/`gewitter` auch per E-Mail-Freitext erreichbar |

## Implementation Details

```
timeline(trip_id, target_date, from_time: datetime | None = None)
  └─ _punkte(segments, from_time)
       für jedes Segment:
         wenn from_time is None oder seg.timeseries is None:
             → seg.aggregated UNVERÄNDERT übernehmen (kein Fehler)
         schnitt_start = max(seg.start_time, from_time)
         wenn schnitt_start <= seg.start_time:
             → seg.aggregated UNVERÄNDERT übernehmen (noch nicht begonnen / from_time davor)
         wenn schnitt_start >= seg.end_time:
             → Segment entfällt (vollständig vergangen)
         sonst (Segment wird beschnitten):
             punkte = segment_window_points(schnitt_start, seg.segment.end_time,
                                            seg.timeseries.data)
             wenn punkte leer:
                 → seg.aggregated UNVERÄNDERT übernehmen (siehe AC-8)
             fenster_ts = NormalizedTimeseries(meta=seg.timeseries.meta, data=punkte)
             basis = compute_basis_metrics(
                         fenster_ts,
                         tz=<Ortszone dieses Segments>,
                         day_window_start_hour=seg.segment.day_window_start_hour,
                         day_window_end_hour=seg.segment.day_window_end_hour)
             neu   = compute_extended_metrics(fenster_ts, basis)
             → neu als Aggregat für dieses Segment übernehmen
```

**Signaturtreue (am Quelltext geprüft, nicht abgeleitet):**

- `segment_window_points(start_time, end_time, points)` (`src/app/day_window.py:89`) nimmt eine
  **Punktliste**, keine `NormalizedTimeseries`; Endgrenze exklusiv nach Stundenabrundung.
- `compute_basis_metrics(timeseries, *, tz, day_window_start_hour=None, day_window_end_hour=None)`
  (`src/services/weather_metrics.py:462`) — `tz` ist **keyword-only und Pflicht**. Die Fensterstunden
  wirken NUR auf `thunder_onset_utc`/`precip_heavy_onset_utc`, nicht auf die übrigen Felder.
- `compute_extended_metrics(timeseries, basis_summary)` (`src/services/weather_metrics.py:930`) —
  nimmt **keine** Fensterstunden und wirft `ValueError` bei leerer Reihe
  (`weather_metrics.py:958`); daher der Leer-Zweig oben.
- Die Fensterstunden hängen am **Segment** (`seg.segment.day_window_start_hour`, so auch in
  `weather_snapshot.py:512-517` serialisiert) — beim Implementieren gegenprüfen, ob der Wert
  zusätzlich auf `SegmentWeatherSummary` gespiegelt ist, und die tatsächlich gefüllte Quelle
  verwenden.

**Korrekturen aus der RED-Phase (2026-09-08, am Quelltext geprüft — die Skizze oben ist an
diesen drei Punkten ungenau):**

1. `compute_basis_metrics`/`compute_extended_metrics` sind **Methoden** von
   `WeatherMetricsService` (`weather_metrics.py:241`), keine freien Funktionen. Es braucht eine
   Instanz.
2. Das Vorbild `segment_weather.py:307-314` löst die Fensterstunden **erst** über
   `resolve_configured_window(segment.day_window_start_hour, segment.day_window_end_hour)` auf
   und übergibt `tz=location_tz(segment.start_point)`. Diesen Weg übernehmen, nicht die rohen
   Segmentwerte durchreichen.
3. `from_time` muss **hinter** `target_date` stehen. `tests/unit/test_ziel_segment_anzeige_invarianz.py:287`
   ruft `timeline("anzeige-1599", TAG)` mit dem Datum als zweitem **Positions**argument — ein
   `from_time` an zweiter Stelle bräche diesen Test.

Weiter am Bestand bestätigt: Der Snapshot-Roundtrip (`save`/`load`) erhält alle Rohfelder der
Stundenreihe (`cape_jkg`, `uv_index`, `cloud_low_pct`, `snowfall_limit_m`, `precip_type` …)
**und** `segment.day_window_start_hour`/`_end_hour` — die Neuberechnung hat also alles, was sie
braucht. Alle bestehenden `timeline()`-Aufrufer (2 in `src/`, 3 in `tests/`) übergeben kein
`from_time`; der Default `None` bricht keinen davon.

`trip_command_processor.py` übergibt `from_time=received_at` an den bestehenden
`timeline()`-Aufruf (`:802`/`:806`). Die vier Formatierer (`_fmt_glance`, `_fmt_gewitter`,
`_timeline_buttons`, `_fmt_timeline`) und `_aggregate_day` bleiben signaturunverändert — sie
lesen alle aus demselben `TimelineResult`, das `_punkte()` bereits gefenstert liefert.

## Expected Behavior

- **Input:** Ad-hoc-Abruf (`glance`, `heute_gewitter`, `timeline_heute`) zu einem Zeitpunkt
  `received_at`, der innerhalb oder nach Tourbeginn liegt.
- **Output:** Tages-Aggregat „heute" spiegelt nur `[max(received_at, Segmentstart) …
  Segmentende]`; vollständig vergangene Segmente entfallen aus den Wegpunkten. „morgen" bleibt
  identisch zu einem früheren Abruf am selben Tag.
- **Side effects:** keine — reine Lesepfad-Änderung, keine Persistenz-Schreibung.

## Acceptance Criteria

- **AC-1:** Given ein Abruf von `glance` am Nachmittag, When der Vormittag bereits Niederschlag
  aufwies, Then enthält der Tageswert für „heute" den Niederschlag des Vormittags nicht mehr.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-2:** Given zwei Abrufe am selben Tag zu unterschiedlichen Uhrzeiten, When beide die
  Zeile „morgen" lesen, Then sind die Werte für „morgen" bei beiden Abrufen wertgleich — „ab
  jetzt" verändert den Folgetag nicht.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-3:** Given ein Segment, dessen Beginn nach dem Anfragezeitpunkt liegt, When die
  Tages-Aggregation läuft, Then behält dieses Segment sein gespeichertes Aggregat unverändert
  (keine Neuberechnung, Werte identisch zum ungefensterten Abruf).
  - Test: `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py`

- **AC-4:** Given ein Segment, das zum Anfragezeitpunkt teilweise vergangen ist, When die
  Tages-Aggregation läuft, Then wird sein Aggregat über das mit `segment_window_points()`
  beschnittene Fenster `[Anfragezeitpunkt, Segmentende)` neu berechnet.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-5:** Given ein Segment, das zum Anfragezeitpunkt vollständig vergangen ist, When die
  Wegpunkte für „heute" gebildet werden, Then erscheint dieses Segment nicht mehr in den
  Wegpunkten.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-6:** Given ein beschnittenes Segment mit vorhandener Stundenreihe, When sein Aggregat
  neu berechnet wird, Then trägt das neue Aggregat die Felder **beider** Rechenstufen —
  mindestens `pop_max_pct`, `cape_max_jkg`, `uv_index_max`, `cloud_low_avg_pct`,
  `precip_type_dominant` und `snowfall_limit_m` sind belegt (nicht `None`), sofern die
  Stundenreihe die zugehörigen Rohwerte trägt.
  - Test: `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py`
  - Wichtigste AC dieser Spec: sie bewacht 18 Felder, die bei einer unvollständigen
    Rechenkette still `None` würden — sichtbar als „keine Daten", ohne dass etwas fehlschlägt.

- **AC-7:** Given ein beschnittenes Segment mit eigenem `day_window_start_hour`/
  `day_window_end_hour`, When sein Aggregat neu berechnet wird, Then werden diese Werte an die
  Neuberechnung durchgereicht, sodass `thunder_onset_utc`/`precip_heavy_onset_utc` nicht auf den
  04–19-Uhr-Default zurückfallen.
  - Test: `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py`

- **AC-8:** Given ein Segment ohne Stundenreihe (`seg.timeseries is None`), When die
  Tages-Aggregation für dieses Segment läuft, Then bleibt sein gespeichertes Aggregat
  unverändert und es entsteht kein Fehler (kein `ValueError`, kein Absturz).
  - Test: `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py`

- **AC-9:** Given ein Aufruf von `timeline()` ohne `from_time`, When die bestehenden vier
  Aufrufer diesen Aufruf unverändert nutzen, Then verhält sich `timeline()` exakt wie vor
  dieser Änderung (Rückwärtskompatibilität).
  - Test: `tests/tdd/test_weather_extractor.py`

- **AC-10:** Given einen Ad-hoc-Abruf, When er über `_fmt_glance`, `_fmt_gewitter`,
  `_timeline_buttons`, `_fmt_timeline` oder `_aggregate_day` ausgegeben wird, Then wirkt die
  Fensterung auf **alle fünf** Ausgabestellen gleichermaßen (kein Ausgabepfad zeigt noch den
  ungefensterten Vormittag).
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-11:** Given denselben `glance`- bzw. `gewitter`-Abruf einmal per Telegram-Freitext und
  einmal per E-Mail-Freitext über `_BARE_KEYWORD_MAP`, When beide zum selben Zeitpunkt
  abgesetzt werden, Then ist die Fensterung in beiden Kanälen identisch wirksam.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

- **AC-12:** Given eine Tour in einer weit von UTC entfernten Ortszeitzone (Neuseeland, wie in
  `fix_1795` AC-4), When ein Ad-hoc-Abruf zu einem Ortszeitpunkt erfolgt, Then bleibt die
  Zuordnung „heute"/„morgen" korrekt und die Fensterung schneidet nicht in den falschen
  Ortstag.
  - Test: `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py`

## Was sich NICHT ändern darf

- **Mail-Renderer** (`src/output/renderers/day_window.py`, `narrow.py`, `compact_summary.py`,
  `outlook.py`) — eigene, feste 04–19-Uhr-Fensterlogik, bleibt unberührt.
- **SMS-Token-Bau** (`src/output/tokens/builder.py`) — liest Etappen-Aggregate direkt, nicht
  `_aggregate_day`.
- **Alarm-Pfade und tagesdatierte Anker-Snapshots** — nicht Teil dieses Ad-hoc-Abrufpfads.
- **Das Verhalten für „morgen"** — in jeder Hinsicht wertgleich zu heute, siehe AC-2.

## Known Limitations

- Ein Abruf nach Tagesfensterende (kein verbleibendes Segment für „heute") liefert eine
  Fehlanzeige statt eines veralteten Werts — siehe Produktentscheidung (2).
- `hail_flag` fehlt im geprüften Bestand durchgehend (Serialisierung lässt `None` weg); ein
  Test, der Hagel über echte Snapshots beweisen will, misst nichts und wird hier nicht
  verlangt.
- Ortsvergleich-Snapshots (`compare_weather_snapshots/`) sind nicht Teil dieser Spec —
  Ortsvergleich-Themen sind zurückgestellt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verhaltenspräzisierung eines bestehenden Ad-hoc-Abrufpfads
  (Kalendertag → Restfenster ab Anfragezeitpunkt), keine neue Entscheidungsfläche (Kanäle,
  Provider, Datenmodell, Auth, Editor-Paradigma). Der 3× bestätigte PO-Entscheid „strikt nur
  Tagesfenster" (#1841/#1848) wird bestätigt, nicht abgelöst.

## Testplan (AC-Test-Mapping)

| Test | Deckt |
|---|---|
| `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py` (CREATE) | AC-1, AC-2, AC-4, AC-5, AC-10, AC-11, AC-12 |
| `tests/tdd/test_tageswert_fenster_erhaelt_alle_metriken.py` (CREATE) | AC-3, AC-6, AC-7, AC-8 |
| `tests/tdd/test_weather_extractor.py` (MODIFY) | AC-9 |

Pfadkorrektur (2026-09-08, RED-Phase): Die Spec nannte für AC-9
`tests/unit/test_weather_extractor.py`. Diese Datei existiert nicht — die
Extractor-Suite liegt unter `tests/tdd/`. Am Bestand geprüft, nicht abgeleitet.

Testdateien sind nach Verhalten benannt, nicht nach Issue-Nummer. Vor Commit `grep -rln`
über `tests/` nach `.timeline(`, um bestehende Aufrufer auf Signaturverträglichkeit zu prüfen
(laut Analyse 4 Dateien, alle ohne `from_time` → Default `None` bricht sie nicht).

## Changelog

- 2026-09-08: Initial spec created (feat-2186-tagesaggregat-ab-jetzt)
