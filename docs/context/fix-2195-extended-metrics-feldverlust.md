# Context: fix-2195-extended-metrics-feldverlust

## Request Summary
`WeatherMetricsService.compute_extended_metrics()` baut ein neues `SegmentWeatherSummary` aus einer
festen Feldliste und verliert dabei `thunder_level_max_signals` und `hail_flag` (Issue #2195, vierter
Fall nach #1391/#1392/#1468). Die Naht soll strukturell geschlossen werden (Merge statt Replace) und
ein Wächter soll jedes künftig verlorene Feld melden.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_metrics.py:988-1070` | `compute_extended_metrics()` — der feldweise Neubau (Fehlerstelle) |
| `src/services/weather_metrics.py:537-580` | `compute_basis_metrics()` — setzt beide Felder (`:547`, `:550`) inkl. Aggregationsregeln `union_of_max_carriers` (`:565`) / `hail_priority` (`:568`) |
| `src/services/weather_metrics.py:1359-1462` | `aggregate_stage()` — Etappen-Aggregation; **kein Zweig für `union_of_max_carriers`** → Fallback `values[0]` (`:1456-1457`) |
| `src/app/thunder_scale.py:121` | `union_of_max_carriers()` — kanonische Vereinigung, Docstring sieht „später Segmente" ausdrücklich vor |
| `src/app/models.py:444-535` | Dataclass `SegmentWeatherSummary` |
| `src/services/segment_weather.py:314-337` | Aufrufer 1: Ergebnis wird `seg.aggregated` (persistiert im Snapshot) |
| `src/services/weather_extractor.py:163-180` | Aufrufer 2: generischer lokaler Workaround aus #2186 (`replace` mit None-Nachzug) |
| `src/services/weather_snapshot.py:420-460` | Serialisierung lässt None weg; Deserialisierung filtert über `fields()` |
| `src/services/stage_weather.py:113`, `src/services/trip_report_scheduler.py:2528`, `src/output/renderers/compact_summary.py:268` | Aufrufer von `aggregate_stage()` |
| `src/output/renderers/email/outlook.py:678-685` | Konsument: Hagel-Zusatz + Gewitter-Träger im Ausblick (über `aggregate_stage`) |
| `src/services/trip_command_processor.py:1536-1556,1647,1720` | Konsument: Tageszeile/Timeline im Kommando-Pfad (Telegram/SMS) aus `seg.aggregated` |
| `src/output/renderers/sms_trip.py:384` | Konsument: Hagel aus Etappen-Aggregat |

## Existing Patterns
- **Generischer Nachzug** in `weather_extractor.py:173-180`: alle `init`-Felder, die in `neu` None und in `basis` gesetzt sind, per `dataclasses.replace` übernehmen. Exakt der gewünschte Merge — nach dem Fix toter Code.
- **Durchreichungs-Test** `tests/tdd/test_bug_226_dni_wmo_passthrough.py` (#226): prüft Basis→Extended direkt, aber nur zwei feste Felder. Vorlage für den Wächter, muss aber generisch über `dataclasses.fields()` laufen.
- **Aggregationsregel mit eigenem Zweig**: `hail_priority` (`:1396-1408`) und `agreement` (`:1435-1442`) — Vorbild für einen `union_of_max_carriers`-Zweig.

## Dependencies
- Upstream: `NormalizedTimeseries`, `compute_basis_metrics()`, `effective_cape_model_id`, `app.thunder_scale`
- Downstream: `seg.aggregated` → Snapshot, Kommando-Pfad, `aggregate_stage()` → Ausblick-Mail, SMS, Scheduler

## Existing Specs
- `docs/specs/modules/weather_metrics.md`, `weather_metrics_extended.md`, `multi_day_trend.md`
- `docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md` (Herkunft im Trip) + weitere `feat_1680_s*`
- `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md`, `feat_1475_hagel_luecken_nachbesserung.md`
- `docs/specs/modules/feat_2186_tagesaggregat_ab_jetzt.md` (Workaround)

## Analyse

### Feld-Diff (vollständig)
- Basis setzt und Extended kopiert: 15 Felder (Temperaturen, Wind, Niederschlag, Wolken, Feuchte, `thunder_level_max`, Sicht, beide Onsets, `dominant_wmo_code`, `dni_avg_wm2`, `sunny_hours`).
- Nur Extended berechnet: 19 Felder (Taupunkt … Bewölkungsstufen, `cape_model_id`).
- **Verloren: `thunder_level_max_signals`, `hail_flag`.**
- **Keine Überschneidung** — kein Feld wird von beiden Stufen gesetzt, ein Merge kann nichts überschreiben. Kein Hinweis auf absichtliches Weglassen (Kommentar `:1000-1005` nennt es selbst „Naht").

### 🔴 Kernbefund der Analyse: der Fix allein würde einen FALSCHEN Zusatz erzeugen
`aggregate_stage()` kennt `union_of_max_carriers` nicht und nimmt `values[0]` — die Träger des **ersten**
Segments mit einem Wert, egal ob dieses Segment die Höchststufe der Etappe trägt. Heute bleibt das
unsichtbar, weil das Feld schon vorher verloren ging (Ergebnis None → kein Zusatz). Schließt man nur die
Naht, bekommt der Ausblick eine Herkunft, die zu einem niedrigeren Segment gehören kann.
**Fehlender Zusatz würde zu falschem Zusatz.** Deshalb gehört der `union_of_max_carriers`-Zweig in
`aggregate_stage()` zwingend in denselben Scope.

### Nutzersichtbare Wirkung heute
- Kommando-Pfad (Tageszeile/Timeline): kein „· CAPE"-/Träger-Zusatz, kein Hagel-Hinweis aus dem Tageswert (außer bei Neuberechnung ab Anfragezeitpunkt, #2186).
- Ausblick-Mail und SMS: Hagel-Zusatz aus Etappen-Aggregat fehlt, Gewitter-Träger fehlen.
- Nicht betroffen: Ortsvergleich und Vorschau (`summarize_points`), Stundentabellen (`dp.hail_flag`).
- Kein Alarm-Nebeneffekt: Katalog, Abweichungs-Engine, Change-Detection lesen keines der Felder.

### Risiken & Considerations
- **Ausgabe ändert sich sichtbar** (Herkunfts- und Hagel-Zusatz erscheinen wieder) → Mail-Renderer-Gate / Briefing-Validator können anschlagen; Staging-Mail muss plausibel sein.
- **Alte Snapshots** (`{trip_id}.json`, datierte `{trip_id}_{date}.json`) bleiben feldlos, bis sie neu geschrieben werden — Laden bleibt kompatibel, vergangene datierte Snapshots werden nie nachgerüstet (keine Datenmigration nötig, Felder sind abgeleitet).
- **Kein Test fängt den Verlust heute an der Quelle**: `test_tageswert_fenster…:430/478` laufen über den Workaround, `test_thunder_origin_*` umgehen Extended. Der Wächter muss am Wirkort (`compute_extended_metrics` bzw. `SegmentWeatherService`) prüfen, nicht am Workaround.
- Workaround in `weather_extractor.py` wird toter Code — entfernen, damit Tests nicht zufällig über ihn grün bleiben.
- `tests/unit/test_weather_metrics.py:145` prüft `len(aggregation_config) == 17` der Basis — unberührt.

## Analysis

### Type
Bug

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/weather_metrics.py` | MODIFY | `compute_extended_metrics()`: Merge statt Neubau — `dataclasses.replace(basis_summary, **extended_fields)`, Extended gewinnt bei künftigem Doppel-Setzen; `aggregation_config` weiter per `{**basis, ...}` |
| `src/services/weather_metrics.py` | MODIFY | `aggregate_stage()`: eigener Zweig `union_of_max_carriers` **vor** dem `is not None`-Vorfilter (wie `hail_priority`), Paare `(thunder_level_max, thunder_level_max_signals)` je Segment; Import aus `app.thunder_scale` (kanonischer Ort, keine Abhängigkeit auf die Darstellungsschicht) |
| `src/services/weather_extractor.py` | MODIFY | Workaround `:164-180` entfernen (nach dem Fix toter Code) |
| `tests/tdd/test_extended_metrics_uebernimmt_alle_basisfelder.py` | CREATE | Generischer Wächter über `dataclasses.fields()` am Wirkort + Etappen-Vereinigung der Träger |

### Scope Assessment
- Files: 3 Produktion + 1 Test
- Estimated LoC: +~30/−~35 Produktion, +~80 Test
- Risk Level: MEDIUM (sichtbare Ausgabeänderung in Ausblick-Mail, SMS, Kommando-Pfad)

### Technical Approach
1. `compute_extended_metrics()` baut auf dem Basis-Objekt auf (Read-Modify-Write): alle Basisfelder bleiben, Extended-Felder werden darübergelegt. Damit ist die Naht strukturell zu, nicht nur für die zwei heute bekannten Felder.
2. `aggregate_stage()` vereinigt die Träger nur der Segmente, die die Etappen-Höchststufe erreichen (`union_of_max_carriers`), statt die des ersten Segments zu nehmen. Rückgabe bleibt `list` (Snapshot-JSON, #1405).
3. Workaround im Extractor fällt weg; die bestehenden Tests `test_tageswert_fenster…:430/478` müssen danach weiter grün sein — jetzt, weil die Wurzel stimmt.
4. Wächter: echte Zeitreihe mit Gewitter- und Hagelstunde durch `compute_basis_metrics()` → `compute_extended_metrics()`; für jedes Feld, das in der Basis gesetzt ist, muss das Ergebnis denselben Wert haben. Extended-only-Felder lösen keinen Fehlalarm aus. Etappen-Test: zwei Segmente, erstes mit niedrigerer Stufe und anderem Träger → nur die Träger des Höchststufen-Segments.
5. Mutations-Gegenprobe: Feldliste zurück, `values[0]` zurück, Zweig hinter den Vorfilter, Workaround zurück ohne Wurzel-Fix — jede muss mindestens einen Test rot machen.

### Gegenproben (vor der Spec geprüft)
- **`replace()` ist sicher:** `SegmentWeatherSummary` hat keine `init=False`-Felder; `__post_init__` (`models.py:537-542`) setzt nur `wind_direction_avg_deg` aus dem Test-Alias `wind_dir_deg_avg`, und das nur, wenn der Alias gesetzt und das Zielfeld leer ist — die Basis setzt den Alias nie. `replace()` verhält sich damit wie der heutige Konstruktor.
- **Ortsvergleich wirklich nicht betroffen:** `summarize_points()` (`weather_metrics.py:1293-1351`) baut direkt auf `compute_basis_metrics()` auf (Attribute ergänzt, kein Neubau) und aggregiert eine einzige Stundenliste — die Träger werden dort über `_compute_thunder_level_signals()` → `union_of_max_carriers` korrekt gebildet, der `values[0]`-Fehler aus `aggregate_stage()` greift dort nicht.
- **Nutzersicht-Test möglich ohne Mock:** `SegmentWeatherService` bekommt den Provider injiziert (`segment_weather.py:326`), `seg.aggregated` ist das Ergebnis von `compute_extended_metrics()` (`:337`) — der Bug lässt sich am gespeicherten Tageswert und an der Tageszeile des Kommando-Pfads rot zeigen.
- **Nicht im Scope:** Der Vorhersage-Mitschnitt (#2030, `forecast_capture._werte`) speichert die Träger weiterhin nicht — das ist die im Epic #1419 genannte offene Messung, eigenes Thema.

### Dependencies
- `app.thunder_scale.union_of_max_carriers` (bestehend, unverändert)
- Kein Alarm-Pfad betroffen; keine Datenmigration (abgeleitete Felder, Alt-Snapshots laden kompatibel)

### Open Questions
- keine fachlichen — das Soll (Herkunft und Hagel sollen im Tageswert erhalten bleiben) ist durch #1680/#1475 bereits PO-entschieden
