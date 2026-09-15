---
entity_id: bug_2195_tageswert_feldverlust
type: module
created: 2026-09-14
updated: 2026-09-15
status: draft
version: "1.0"
tags: [tageswert, gewitter, hagel, aggregation, extended-metrics]
---

# Tageswert verliert Gewitter-Träger und Hagel-Kennzeichen (Issue #2195)

## Approval

- [ ] Approved

## Purpose

`WeatherMetricsService.compute_extended_metrics()` baut das erweiterte Tages-Summary aus einer
festen Feldliste neu auf und verliert dabei zwei Felder, die die Basisstufe bereits gesetzt hat:
`thunder_level_max_signals` (die Zutaten der Gewitter-Höchststufe, z. B. CAPE) und `hail_flag`
(Hagel-Kennzeichen). Das ist der vierte Fall dieser Fehlerklasse nach #1391/#1392/#1468 — die
Naht wird deshalb strukturell geschlossen (Merge statt Neubau), nicht nur für die zwei bekannten
Felder. Zusätzlich fehlt der `aggregate_stage()`-Etappen-Aggregation ein Zweig für die Regel
`union_of_max_carriers`: sie fällt auf den generischen `values[0]`-Fallback zurück, der die
Träger des ERSTEN Segments mit einem Wert nennt statt der Träger des Höchststufen-Segments. Der
Fix am Basis/Extended-Merge allein würde also einen fachlich falschen Zusatz erzeugen (Herkunft
eines niedrigeren Segments), deshalb gehören beide Änderungen in denselben Scope.

## Source

- **File:** `src/services/weather_metrics.py`
- **Identifier:** `WeatherMetricsService.compute_extended_metrics()` (`:988`), `aggregate_stage()` (`:1359`)

> Python-Core / Domain-Backend (`src/services/`, `src/app/`). Zusätzlich betroffen:
> `src/services/weather_extractor.py:164-180` (Workaround aus #2186, entfällt).

## Estimated Scope

- **LoC:** Produktivcode ca. +30/−35, Tests +~80
- **Files:** 3 Produktivdateien, 1 neue Testdatei
- **Effort:** medium

### Betroffene Dateien

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/weather_metrics.py` | MODIFY | `compute_extended_metrics()`: Merge statt Neubau (`dataclasses.replace`) |
| `src/services/weather_metrics.py` | MODIFY | `aggregate_stage()`: neuer Zweig `union_of_max_carriers` vor dem Vorfilter |
| `src/services/weather_extractor.py` | MODIFY | Workaround `:164-180` entfernen (toter Code nach dem Fix) |
| `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` | CREATE | Wächter am Wirkort + Etappen-Vereinigung |
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | Ausnahme `hail_flag` in `_S2_NUR_COMPARE_ERLAUBT` entfällt (gegenstandslos nach Change 1) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py:537-580` `compute_basis_metrics()` | Rechenkette | Setzt beide verlorenen Felder (`:547` `thunder_level_max_signals`, `:550` `hail_flag`) sowie die Aggregationsregeln `union_of_max_carriers` (`:565`) und `hail_priority` (`:568`) in `aggregation_config` |
| `src/app/thunder_scale.py:121` `union_of_max_carriers()` | Helper | Kanonische Vereinigung der Träger der Höchststufen-Segmente, unverändert; Domänenschicht, keine Abhängigkeit auf `output/` |
| `src/output/metric_format.py:1404` `hail_priority()` | Helper | Bestehende Prioritätsregel ja > unbekannt > nein — bereits als eigener Zweig in `aggregate_stage()` vorhanden, unverändert |
| `src/app/models.py:444-535` `SegmentWeatherSummary` | Dataclass | Ziel-/Quelltyp beider Rechenstufen; keine `init=False`-Felder, `__post_init__` (`:537-542`) betrifft nur den Test-Alias `wind_dir_deg_avg`, den die Basis nie setzt — `dataclasses.replace()` verhält sich daher wie der heutige Konstruktor |
| `src/services/segment_weather.py:314-337` | Aufrufer | `compute_basis_metrics()` → `compute_extended_metrics()`, Ergebnis wird `seg.aggregated` (persistiert im Snapshot) |
| `src/services/weather_extractor.py:163-180` | Aufrufer | Generischer Nachzug-Workaround aus #2186 — nach dem Fix toter Code, wird entfernt |

## Implementation Details

**1. `compute_extended_metrics()` — Merge statt Neubau (`weather_metrics.py:988`)**

Statt `SegmentWeatherSummary(... feste Feldliste ...)` wird `dataclasses.replace(basis_summary,
**extended_fields)` verwendet: Alle Felder von `basis_summary` bleiben erhalten, `extended_fields`
(dewpoint, pressure, wind_chill, cape_max_jkg, … s. bisherige Feldliste `:1012-1037`) legt sich
darüber. Bei künftigem Doppel-Setzen gewinnt Extended (Read-Modify-Write-Reihenfolge). Die
`aggregation_config` bleibt `{**basis_summary.aggregation_config, ...}` — unverändert zum
Bestand, da `replace()` das Feld ebenfalls überschreibt.

Der Hagel-Teil braucht KEINEN neuen Zweig in `aggregate_stage()` — `hail_priority` existiert dort
bereits (`:1396-1408`) und funktioniert korrekt. `hail_flag` fehlt im Ausblick heute einzig, weil
Change 1 das Feld schon vor der Etappen-Aggregation verliert (`seg.aggregated.hail_flag` ist
bereits `None`, bevor `aggregate_stage()` es überhaupt liest).

**2. `aggregate_stage()` — eigener Zweig für `union_of_max_carriers` (`weather_metrics.py:1359`)**

Nach dem Vorbild `hail_priority` (`:1396-1408`) VOR dem generischen `is not None`-Vorfilter
(`:1410-1413`): Der Vorfilter würde Segmente mit `None`-Trägern (z. B. kein Gewitter in diesem
Segment) herausnehmen und die Höchststufe nur noch über die VERBLEIBENDE Teilmenge neu
bestimmen — ein niedrigeres Segment könnte dadurch fälschlich zur Etappen-Höchststufe werden.
Der neue Zweig baut stattdessen Paare `(thunder_level_max, thunder_level_max_signals)` je
Segment aus der VOLLSTÄNDIGEN `summaries`-Liste und übergibt sie an
`app.thunder_scale.union_of_max_carriers` — Import aus der Domänenschicht, nicht aus
`output.metric_format` (keine Abhängigkeit von `aggregate_stage()` auf die Darstellungsschicht).

```
if agg_rule == "union_of_max_carriers":
    from app.thunder_scale import union_of_max_carriers
    result_fields[field_name] = union_of_max_carriers(
        [(s.thunder_level_max, s.thunder_level_max_signals) for s in summaries]
    )
    continue
```

**3. Workaround entfernen (`weather_extractor.py:164-180`)**

Der generische Nachzug über `dataclass_fields(SegmentWeatherSummary)` wird nach Change 1
überflüssig — `compute_extended_metrics()` verliert dann selbst keine Basisfelder mehr. Entfernt
wird der `nachgezogen`-Block; `return neu` bleibt als direkter Rückgabewert.

## Expected Behavior

- **Input:** Eine Stundenreihe mit Gewitter-Höchststufe (Träger z. B. `["cape"]`) und mindestens
  einer Hagelstunde, verarbeitet über `compute_basis_metrics()` → `compute_extended_metrics()`
  (Segment-Pfad) bzw. über mehrere Segmente einer Etappe (`aggregate_stage()`).
- **Output:** Der erweiterte Tageswert (`seg.aggregated`) trägt `thunder_level_max_signals` und
  `hail_flag` identisch zur Basisberechnung. Das Etappen-Aggregat nennt nur die Träger des
  Segments (oder der Segmente), das die Etappen-Höchststufe tatsächlich erreicht.
- **Side effects:** keine Persistenz-Schema-Änderung (beide Felder existieren bereits in
  `SegmentWeatherSummary` und der Serialisierung, `weather_snapshot.py:420-460`) — reine
  Rechenkorrektur. Ausgabeänderung sichtbar in Kommando-Pfad (Telegram/E-Mail-Freitext),
  Ausblick-Mail und SMS/Premium-SMS (nur Hagel-Zusatz, s. AC-8).

## Acceptance Criteria

- **AC-1:** Given ein Segment mit Gewitter-Höchststufe (Träger, z. B. CAPE) und einer Hagelstunde
  in seiner Stundenreihe, When `SegmentWeatherService` das Segment über `compute_basis_metrics()`
  → `compute_extended_metrics()` verarbeitet, Then trägt `seg.aggregated.thunder_level_max_signals`
  und `seg.aggregated.hail_flag` denselben Wert wie das direkte Ergebnis von
  `compute_basis_metrics()` (heute beides `None`).
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — rot vor Fix

- **AC-2:** Given ein Segment, dessen gespeichertes Aggregat unverändert gelesen wird (kein
  `from_time`, oder ein Segment, das zum Anfragezeitpunkt noch nicht begonnen hat — kein
  Durchlauf durch den `weather_extractor`-Neuberechnungspfad `:150-180`), mit Gewitter-
  Höchststufe samt Träger und einer Hagelstunde, When der Kommando-Pfad `_fmt_gewitter()`
  (`trip_command_processor.py:1625-1664`) die Zeile aus demselben `_aggregate_day()`-Ergebnis
  baut, Then lautet die Ausgabe `⛈ Gewitter heute (DD.MM): {label} · {herkunft}{hail_suffix}`
  mit gefülltem `herkunft` (z. B. „CAPE", `thunder_signal_label()`) und gefülltem `hail_suffix`
  (` · {hail_note}`, `format_hail_note()`) — heute bleiben beide Zusätze leer, weil
  `agg["thunder_signals"]`/`agg["hail_flag"]` bereits aus einem feldlosen `seg.aggregated`
  stammen (rot vor Fix). Ein Segment, das über den #2186-Workaround neu berechnet wird, ist für
  diese AC UNGEEIGNET, weil der Workaround beide Felder schon heute nachzieht (falsches Grün).
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — rot vor Fix

- **AC-3:** Given eine beliebige Stundenreihe, When `compute_basis_metrics()` gefolgt von
  `compute_extended_metrics()` läuft, Then ist für JEDES Feld von `SegmentWeatherSummary`
  (über `dataclasses.fields()`, außer `aggregation_config`), das die Basisstufe auf einen Wert
  ungleich `None` setzt, der Wert im erweiterten Ergebnis identisch — auch für ein künftig
  hinzugefügtes Basisfeld, ohne Änderung an `compute_extended_metrics()`. Zusätzlich gilt die
  Nichtüberschneidungs-Invariante der Analyse: kein Feld wird von Basis- UND Extended-Stufe
  gesetzt — ein Test hält das fest, damit ein künftig überschneidendes Feld eine bewusste
  Entscheidung erzwingt statt still zu divergieren. Extended-eigene Felder (nur dort berechnet)
  lösen keinen Fehlalarm aus.
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — Wächter (Nichtüberschneidung heute schon wahr, generischer Feld-für-Feld-Vergleich neu)

- **AC-4:** Given eine Etappe mit zwei Segmenten — erstes Segment niedrigere Gewitterstufe mit
  Träger A, zweites Segment die Etappen-Höchststufe mit Träger B —, When `aggregate_stage()`
  läuft, Then nennt `thunder_level_max_signals` des Etappenergebnisses NUR Träger B, unabhängig
  von der Segmentreihenfolge in der Eingabeliste (Vertauschungsprobe). Dieselbe AC deckt die
  Mutation „Zweig hinter den Vorfilter": stünde der neue Zweig hinter dem `is not None`-Filter,
  würde das Segment mit Träger A (falls sein Wert nicht `None` ist) die Höchststufen-Neuermittlung
  verfälschen.
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — rot vor Fix

- **AC-5:** Given eine Etappe mit mehreren Segmenten auf derselben Gewitter-Höchststufe mit
  verschiedenen Trägern, When `aggregate_stage()` läuft, Then ist das Ergebnis die Vereinigung
  aller Träger dieser Segmente, dedupliziert, in Erstauftritts-/Katalogreihenfolge von
  `THUNDER_SIGNAL_LABEL_DE` (nicht alphabetisch sortiert), als `list` (nicht `set` — Snapshot-JSON,
  #1405).
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — rot vor Fix

- **AC-6:** Given ein Höchststufen-Segment ohne Träger (z. B. Alt-Snapshot vor #1680) und ein
  Segment niedrigerer Stufe MIT Träger, When `aggregate_stage()` läuft, Then ist das Ergebnis
  `None` (keine Aussage) — niemals der Träger des niedrigeren Segments. Liegt die Etappen-
  Höchststufe bei `ThunderLevel.NONE` (kein Gewitter), ist das Ergebnis ebenfalls `None`
  (`union_of_max_carriers()` garantiert das selbst, `thunder_scale.py:145-150`).
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — Wächter (Verhalten von `union_of_max_carriers()` selbst unverändert; neu ist, dass `aggregate_stage()` es jetzt aufruft statt `values[0]`)

- **AC-7:** Given eine Etappe mit Gewitter-Höchststufe und Hagelstunde in mindestens einem
  Segment, When die Ausblick-Mail über `outlook.py:678-685` gerendert wird, Then zeigt die
  Gewitter-Zelle sowohl den Hagel-Zusatz (`_hail = getattr(summary, "hail_flag", None)`) als auch
  die Träger (`_signals = getattr(summary, "thunder_level_max_signals", None)`) — heute fehlt
  der Hagel-Zusatz, weil `summary` aus `aggregate_stage()` stammt.
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — rot vor Fix (Hagel-Teil)
  - RED-Befund 2026-09-14: Der Träger-Zusatz erscheint schon heute, weil `thunder_cell_html()` die
    Träger aus der Stundenreihe (`thunder_day_carriers`) holt und nicht aus dem Etappen-Aggregat.
    Dass die Träger das Aggregat überleben, ist daher an der Ausblick-Zelle nicht messbar und wird
    von AC-1/AC-3/AC-4/AC-5 bewacht.

- **AC-8:** Given dieselbe Etappe wie AC-7, When die Zeile über den Kanal SMS oder Premium-SMS
  gebaut wird (`channel in ("sms", "premium_sms")`), Then erscheint der Hagel-Zusatz aus dem
  Etappen-Aggregat (`sms_trip.py:384`, `hail_priority` über `hail_values`), aber die Gewitter-
  Träger bleiben bewusst weg — PO-Abwahl (`feat_1680_s5a` AC-12, `feat_1680_s5b` AC-9, Issue
  #2184, `trip_command_processor.py:1659`: `zeige_herkunft = channel not in ("sms",
  "premium_sms")`). Diese AC ist eine ausdrückliche Negativ-Zusicherung, kein Auslassen — sie
  verhindert, dass die RED-Phase fälschlich Träger auf SMS verlangt und damit eine bestehende
  Produktentscheidung revidiert.
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — Wächter (Hagel-Zusatz rot vor Fix, Träger-Abwesenheit bereits heute wahr und bleibt es)

- **AC-9:** Given einen Ad-hoc-Abruf mit `from_time` innerhalb eines teilweise vergangenen
  Segments (Tagesaggregat ab Anfragezeitpunkt, #2186), When `weather_extractor._punkte()` das
  Segment über `compute_basis_metrics()` → `compute_extended_metrics()` neu berechnet (OHNE den
  entfernten Nachzug-Workaround), Then trägt das neu berechnete Aggregat weiterhin
  `thunder_level_max_signals` und `hail_flag`, weil Change 1 den Verlust an der Wurzel schließt.
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — Wächter (heute bereits grün durch den Workaround; muss nach dessen Entfernen weiter grün bleiben, s. Fallstrick unten)

- **AC-10:** Given den Stand vor und nach diesem Fix, When `compute_extended_metrics()` mit
  identischer Eingabe läuft, Then sind alle Felder AUSSER `thunder_level_max_signals`/`hail_flag`
  und die Schlüssel der `aggregation_config` unverändert zum bisherigen Ergebnis (keine
  Regression an den 19 Extended-only-Feldern oder den 17 bestehenden `aggregation_config`-
  Einträgen, `tests/unit/test_weather_metrics.py:145`).
  - Test: `tests/unit/test_weather_metrics.py` (bestehend, MODIFY nur falls nötig) — Wächter, bereits heute grün

- **AC-11:** Given einen alten Wetter-Snapshot, der beide Felder nicht enthält (Serialisierung vor
  diesem Fix, `weather_snapshot.py` lässt `None` beim Speichern weg), When der Snapshot geladen
  und der Tageswert gerendert wird, Then lädt er fehlerfrei und die Gewitterzeile zeigt keinen
  Träger-/Hagel-Zusatz statt abzustürzen (fail-soft, kein `AttributeError`/`KeyError`).
  - Test: `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` — Wächter, bereits heute grün (`getattr(..., None)`-Zugriffe überall am Konsum-Ort)

## Was sich NICHT ändern darf

- **Ortsvergleich/Vorschau** (`summarize_points()`, `weather_metrics.py:1293-1351`) — baut direkt
  auf `compute_basis_metrics()` auf (Attribute ergänzt, kein Neubau), bildet die Träger bereits
  korrekt über `_compute_thunder_level_signals()` → `union_of_max_carriers`. Der `values[0]`-
  Fehler aus `aggregate_stage()` greift dort nicht. Ortsvergleich-Themen sind zurückgestellt.
- **`_aggregate_day()` im Kommando-Pfad** (`trip_command_processor.py:1517-1556`) — berechnet
  Träger bereits korrekt über `union_of_max_carriers` auf Wegpunkt-Ebene, ein eigener,
  UNABHÄNGIGER Aggregationsweg neben `aggregate_stage()`. Bleibt unverändert; die beiden Wege
  dürfen im Zuge dieses Fixes NICHT zusammengelegt werden (außerhalb des Scopes).
- **Vorhersage-Mitschnitt** (#2030, `forecast_capture`) — speichert die Träger weiterhin nicht,
  eigenes Thema (Epic #1419).
- **Alarm-Pfade, Katalog, Abweichungs-Engine, Change-Detection** — lesen keines der beiden Felder.
- **Stundentabellen** (`dp.hail_flag` auf Punktebene) — unberührt, betrifft nur die
  Tages-/Etappen-Aggregation.
- **SMS/Premium-SMS-Träger-Anzeige** — bleibt bewusst abwesend (AC-8, PO-Entscheid #2184).

## Known Limitations

- Alte, bereits gespeicherte Snapshots (`{trip_id}.json`, datierte
  `{trip_id}_{date}.json`) bleiben feldlos, bis sie neu geschrieben werden — keine
  Datenmigration, da beide Felder abgeleitet sind (AC-11 sichert den fail-soft-Fall ab).
  Damit gilt die in `feat_2186_tagesaggregat_ab_jetzt.md` festgehaltene Known Limitation
  „`hail_flag` fehlt im geprüften Bestand durchgehend" nur noch für Snapshots, die VOR diesem
  Fix geschrieben wurden — für neu geschriebene Snapshots ist sie mit diesem Fix aufgehoben.
- Der Vorhersage-Mitschnitt (#2030) bleibt von diesem Fix unberührt (s. o.).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Fehlerbehebung an einer bestehenden Rechenkette (Basis→Extended-Merge,
  Etappen-Aggregationsregel), keine neue Entscheidungsfläche (Kanäle, Provider, Datenmodell,
  Auth, Editor-Paradigma). Die Sichtbarkeit von Herkunft und Hagel im Tageswert ist durch
  #1680/#1475 bereits PO-entschieden.

## Testplan (AC-Test-Mapping)

| Test | Deckt | Status |
|---|---|---|
| `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` (CREATE) | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-11 | Gemessen 2026-09-14: rot vor Fix AC-1/2/3 (Feldvergleich)/4/5/6/7 (Hagel)/8 (Hagel); grün als Wächter AC-3 (Nichtüberschneidung)/9/11 und der Träger-Abwesenheits-Teil von AC-8. AC-8 wird über den Kommando-Pfad mit `sms`/`premium_sms` geprüft (`sms_trip.py:384` greift nur für Segmente ohne Stundenreihe) |
| `tests/unit/test_weather_metrics.py` (bestehend, ggf. MODIFY) | AC-10 | Wächter, bereits heute grün |

Kern-Schicht, keine Mocks: echte `NormalizedTimeseries`/`ForecastDataPoint`-Fixtures (Gewitter-
und Hagelstunden über die vorhandenen Fixture-Bausteine, nicht neu erfunden), `WeatherMetricsService`
direkt instanziiert (kein Provider-Netzwerkzugriff nötig für Change 1/2; Change 3 braucht den
`SegmentWeatherService`-Provider injiziert, wie in `segment_weather.py:326` vorgesehen). Testdatei
nach Verhalten benannt, nicht nach Issue-Nummer.

**Fallstrick (aus Analyse geprüft):** AC-2 und AC-9 dürfen sich NICHT gegenseitig verwechseln.
AC-2 braucht ausdrücklich ein Segment OHNE Durchlauf durch den `weather_extractor`-
Neuberechnungspfad (`:150-163`), weil der #2186-Workaround dort beide Felder schon heute
nachzieht und den Test fälschlich grün zeigen würde, bevor die Wurzel gefixt ist (falsches
Grün). AC-9 prüft umgekehrt genau diesen Pfad — dort ist Grün vor UND nach dem Fix korrekt
(vor dem Fix durch den Workaround, danach durch Change 1), weshalb AC-9 als Wächter geführt
wird, nicht als rot-vor-Fix-Nachweis.

**Mutations-Gegenprobe (jede MUSS mindestens einen Test rot machen):**

| Mutation | Gefangen von |
|---|---|
| Feldliste in `compute_extended_metrics()` zurück (Neubau statt `replace()`) | AC-1, AC-3 |
| `values[0]`-Fallback statt `union_of_max_carriers`-Zweig in `aggregate_stage()` | AC-4, AC-5, AC-6 |
| Neuer Zweig HINTER den `is not None`-Vorfilter gesetzt statt davor | AC-6 (Fall a: Höchststufe ohne Träger) — AC-4 kann es nicht fangen, dort haben beide Segmente Träger |
| Workaround in `weather_extractor.py` zurück, ohne Change 1 (Wurzel-Fix) | AC-9 (nach Entfernen des Workarounds) |

## Changelog

- 2026-09-14: Initial spec created (fix-2195-extended-metrics-feldverlust). AC-7 gegen
  Quelltext-Belege (`sms_trip.py:384`, `trip_command_processor.py:1659`) in AC-7 (Mail:
  Hagel + Träger) und AC-8 (SMS/Premium-SMS: nur Hagel, Träger bewusst abwesend, #2184)
  aufgeteilt, damit die RED-Phase keine bestehende Produktentscheidung revidiert. AC-2s
  Hagel-Behauptung von `_fmt_day_agg()` (zeigt keinen Hagel-Zusatz) auf `_fmt_gewitter()`
  (zeigt beides, exakte Stringform am Quelltext geprüft) korrigiert. Alle ACs auf fortlaufende
  Ganzzahlen AC-1…AC-11 nummeriert (kein Buchstaben-Suffix, Gate-Regex-Konformität). Status
  „rot vor Fix" vs. „Wächter" je AC ergänzt.
- 2026-09-14 (nach Freigabe, RED-Phase): Nur Beschreibungen an den Messbefund angeglichen, kein
  Then-Satz geändert — AC-7 „heute fehlt der Träger-Zusatz" war falsch (Zelle holt Träger aus der
  Stundenreihe, fehlt ist nur Hagel); Rot/Grün-Status im Testplan durch gemessene Werte ersetzt
  (AC-6 und der Hagel-Teil von AC-8 sind rot, nicht Wächter); Mutation „Zweig hinter dem
  Vorfilter" wird nur von AC-6 (a) gefangen, nicht von AC-4.
- 2026-09-15 (Validierung): Dateitabelle um `tests/tdd/test_channel_metric_matrix.py`
  (MODIFY, Ausnahme `hail_flag` in `_S2_NUR_COMPARE_ERLAUBT` entfällt) nachgezogen. Adversary-
  Befund F002: Die Zahlen in AC-10 („19 Extended-only-Felder", „17 aggregation_config-Einträge",
  Verweis `test_weather_metrics.py:145`) sind ein Rest eines früheren Spec-Stands — der
  Laufzeitstand ist 18 Extended-Felder (17 + `cape_model_id`) bzw. 28 `aggregation_config`-
  Einträge insgesamt (Basis- und Extended-Stufe zusammen). Kein Testverhalten hängt an diesen
  Zahlen (`test_weather_metrics.py:145` prüft ausschließlich die 17 Basis-Einträge, nicht die
  19/18 Extended-Zahl aus dem AC-Text). Der Then-Satz von AC-10 selbst bleibt unverändert; die
  Diskrepanz ist hier nur dokumentiert, nicht korrigiert.
