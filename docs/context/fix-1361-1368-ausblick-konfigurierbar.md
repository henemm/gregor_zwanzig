# Context: fix-1361-1368-ausblick-konfigurierbar

Issues: #1361 Befund 2 + #1368 (S3 Scheibe A von Epic #1372, Dach #1374)
Erhoben: 2026-07-27, Basis-Stand `bcc656ef`
Vorgänger: Scheibe B `9aabba19` (#1366), Scheibe C `bcc656ef` (#1378)

## Request Summary

Der 3-Tages-Ausblick der Vergleichs-Mail hat keine Bedienfläche (feste Spalten),
keine eigene Überschrift, und er wiederholt den Tag, den die Stundentabelle
bereits im Detail zeigt.

## PO-Vorgaben

- **V1 (2026-07-27, wörtlich):** „Der Ausblick soll nie den Tag angeben, der im
  Detail im Briefing angezeigt wird, sondern immer am darauf folgenden Tag
  beginnen." Als Abnahmeregel: der Detailtag darf im Ausblick **nicht** vorkommen.
- **V2 (#1368-Kommentar, 2026-07-26):** #1368 und #1361 Befund 2 zusammen
  bearbeiten — „sonst wird der Block zweimal angefasst."
- **V3 (CLAUDE.md):** Trip/Compare-Teilungs-Invariante. Der Ausblick ist heute
  **vollständig** geteilt; eine Compare-eigene Kopie wäre ein Verstoß.
- **V4 (2026-07-27, auf Vorlage der Trade-offs):** Der Nutzer wählt aus **allen
  24** Größen mit Tagesauswertung, nicht nur aus den sieben, die der Ausblick
  heute berechnet. Der geteilte Baustein wird dafür umgebaut; der Trip-Ausblick
  zieht mit.

## Machbarkeit belegt: die Daten liegen schon vor

`SegmentWeatherSummary` (`src/app/models.py`) trägt **32 Felder** — darunter
jede der 24 Katalog-Tagesauswertungen: `temp_min_c/temp_max_c/temp_avg_c`,
`wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `pop_max_pct`,
`thunder_level_max`, `cape_max_jkg`, `cloud_avg_pct`,
`cloud_low_avg_pct/cloud_mid_avg_pct/cloud_high_avg_pct`, `humidity_avg_pct`,
`dewpoint_avg_c`, `pressure_avg_hpa`, `wind_chill_min_c/wind_chill_max_c`,
`visibility_min_m`, `snow_depth_cm`, `snow_new_sum_cm`, `freezing_level_m`,
`snowfall_limit_m`, `uv_index_max`, `dni_avg_wm2`, `sunny_hours`,
`wind_direction_avg_deg`, `precip_type_dominant`.

`metric_catalog.MetricDefinition.summary_fields` mappt Aggregation → genau
dieses Feld. **Kein zusätzlicher Datenabruf nötig** — der Ausblick verwirft die
Werte heute nur auf dem Weg in die Tabelle. Das reduziert den Umbau auf
Darstellung + Auswahl.

## Vorgeschlagener Umbauweg (Strangler, Trip-Parität)

1. `build_outlook_row(summary, points, weekday, tz, metrics=None)` — `metrics`
   ist eine Liste `{metric_id, aggregation}`. Die Zellen werden datengetrieben
   über `summary_fields[aggregation]` aus `summary` gelesen.
2. **`metrics=None` reproduziert exakt die heutigen sieben Spalten** (+ ACC im
   Trip-Fall). Der Trip ruft weiterhin ohne `metrics` auf → **Trip-Mail bleibt
   byte-identisch**. `tests/tdd/test_shared_outlook_renderer.py` hat dafür
   bereits Byte-Identitäts-Tests, die als Wächter dienen.
3. Spaltenköpfe kommen aus `col_label` des Katalogs statt aus der festen
   Kopfzeile — Nebennutzen: die heute kryptischen Kürzel `N`/`D`/`R`/`PR`
   werden durch Katalog-Labels ersetzt.
4. Auswahl liegt als `display_config.outlook_metrics` im **Neuformat**
   `[{metric_id, aggregation}]` (wie `active_metrics` seit #1373) — damit kein
   viertes Vokabular entsteht und **kein Go-Eingriff** nötig ist
   (`mergeConfigMap` deckt `display_config` generisch ab).
5. Reihenfolge folgt der Auswahlreihenfolge (Muster `_visible_hour_metrics`);
   kein eigenes Bedienelement über den geteilten `WeatherV2Reihenfolge` hinaus.

## Belege an der echten Mail (Staging, 27.07. 09:00:37 UTC)

| Beobachtung | Belegt |
|---|---|
| Kopfzeile `Datum: Monday, 27.07.2026`, Ausblick zeigt `Mo · Di · Mi` | Der Detailtag wird wiederholt (V1 verletzt) |
| HTML-Spaltenköpfe `Tag \| N \| D \| R \| PR \| Wind \| Böen \| Gew`, **dreimal identisch** | #1361 Befund 2 |
| Wörter „Ausblick" und „3-Tages" kommen im HTML **0×** vor | #1368.1 ist nicht „falsche Überschrift", sondern **keine** |
| Klartext-Überschrift lautet `Nächste Etappen` | Trip-Wortwahl; im Ortsvergleich gibt es keine Etappen |
| Klartext-Zeile `Mo` + 26 Leerzeichen + Werte | Compare setzt `row["name"]` nicht — leeres Namensfeld des Trip-Formats |

## Ist-Zustand

### Der Ausblick ist vollständig geteilt

| Baustein | Datei | Trip | Compare |
|---|---|---|---|
| Zeilenbau | `email/outlook.py:236-321` `build_outlook_row` | `trip_report_scheduler.py:1441` | `compare_html.py:812` |
| HTML-Tabelle | `email/outlook.py:40-195` `render_outlook_table` | `email/html.py:1113` (`show_acc=True`, 9 Spalten) | `compare_html.py:829` (`show_acc=False`, 8 Spalten) |
| Klartext-Zeile | `email/outlook.py:202-229` `render_outlook_plain` | `email/plain.py:276` | `comparison.py:272` |

`build_outlook_row` liefert ein festes Dict: `weekday, temp_lo, temp_hi,
precip_mm, wind_dir, wind_kmh, thunder, hourly_precip, hourly_wind,
hourly_gust, hourly_thunder` + optional `confidence_pct,
rain_probability_pct, sms_threshold_*`. Trip reichert danach `date`, `name`,
`note` an (`trip_report_scheduler.py:1449-1451`) — **Compare tut das nicht**,
daher das leere Namensfeld.

Der Ausblick kennt damit **7 Größen** (Temp min/max, Regen, Regen-W., Wind,
Böen, Gewitter; + ACC nur Trip). Der Katalog bietet **24** Größen mit
Tagesauswertungen an (`metric_catalog.py`, `summary_fields`).

### Tages-Slice

`comparison_engine.py:149-154`:
```python
_outlook_days = sorted({d for _dp, d in _by_local_day if d >= target_date})[:3]
```
`>= target_date` schließt den Detailtag ein — Ursache für V1-Verletzung. Der
Fix ist im Kern `>`, plus ein vierter Tag muss verfügbar sein
(`COMPARE_FORECAST_HOURS = 96` deckt das ab, ist zu prüfen).

### Überschriften

- HTML: `compare_html._location_heading()` (`:717-745`) rendert `ORT <Name>`
  + Zeitzonen-Kürzel. Seit #1378 für **beide** Blöcke aufgerufen — Stundentabelle
  (`:756`) und Ausblick (`:828`), gleicher Text. Ein früherer Sammel-Kopf
  „AUSBLICK · 3-Tage-Ausblick · alle Orte" wurde mit #1323 entfernt (siehe
  `tests/tdd/test_compare_outlook_placement.py:122-141`).
- Klartext: `outlook.py:211` schreibt fest `Nächste Etappen`.
- `comparison.py:275-279` schreibt `STUNDENVERLAUF` nur bei
  `hour_rows_written` (seit #1366 `9ae845d8`) — der Fund aus Scheibe B ist
  dadurch teilweise entschärft; bleiben ALLE Orte ohne Stundenzeilen, steht der
  Ausblick ohne jede Sektionsüberschrift. `tests/unit/test_compare_empty_metric_selection.py:305`
  verweist im Kommentar ausdrücklich auf #1368.

### Vorbild: die Stundenverlauf-Auswahl (vollständiger Weg)

| Schicht | Fundstelle |
|---|---|
| Bedienfläche | `shared/CompareHourlyLayoutControls.svelte:103-155`, eingebunden in geteiltem `shared/WeatherMetricsTab.svelte:942` (`context="route"\|"vergleich"`) |
| Reihenfolge | geteilter `WeatherV2Reihenfolge.svelte` via `SortableList`/`DragHandle` (ADR-0024) |
| Formular-State | `compareWizardState.svelte.ts:40` `hourlyMetricKeys: string[]\|null` |
| Schreiben | `compareEditorSave.ts:124` → `display_config.hourly_metrics` |
| Go-Persistenz | **kein Eingriff nötig**: `display_config` ist ein generischer Blob, `handler/config_merge.go::mergeConfigMap` merged jeden Key (`compare_preset.go:300`) |
| Auflösung | `report_config_resolver.py:248` → `compare_hourly_metric_ids.py:34-68` (`None`=kein Filter, `[]`=leer bleibt leer, unbekannte IDs mit `logger.warning` verworfen) |
| Renderer | `compare_html._visible_hour_metrics:613-626`; Klartext importiert **dieselbe** Funktion (`comparison.py:29`) — ein Auflöser |

### Zwei Speicherformate im Bestand

- `display_config.hourly_metrics`: **Altformat**, String-Keys, eigenes
  Vokabular (9 Einträge, statischer Frontend-Katalog
  `compareHourlyMetricDefs.ts:29-44` gegen `FRONTEND_TO_HOURLY_METRIC_ID`).
- `display_config.active_metrics`: **Neuformat** seit #1373 —
  `{"metric_id": "wind_chill", "aggregation": "max"}`. Auflösung über
  `compare_metric_catalog.key_for()`; Alt- und Neuformat gemischt erlaubt
  (`compare_metric_ids.py:101-122`). Katalog-Endpunkt
  `GET /api/compare/metrics`.

Das Neuformat ist die Richtung des Epics („eine Größe, mehrere Auswertungen").

### `outlook_enabled` — latenter Bug

Existiert top-level und wird gelesen (`report_config_resolver.py:266`, Default
`True`), aber:
- **kein Feld im Go-Struct** `internal/model/compare_preset.go` → ein Client,
  der es über die Go-API schreibt, verliert es still (`json.Decode` in ein
  frisches Struct, `handler/compare_preset.go:281`).
- **keine Bedienfläche** — `grep outlook_enabled frontend/` = 0 Treffer. Das
  strukturell parallele `hourly_enabled` ist voll verdrahtet.

Wer eine Ausblick-Bedienfläche baut, muss also **top-level** Felder durch Go
ziehen (Struct-Feld + nil-Preserve-Block wie `compare_preset.go:321-327`) —
oder die Auswahl in `display_config` legen, wo kein Go-Eingriff nötig ist.

## Risks & Considerations

1. **Der geteilte Baustein kennt nur 7 der 24 Größen.** Eine Auswahl über den
   vollen Katalog erfordert den Umbau von `build_outlook_row` (Lesen direkt aus
   `SegmentWeatherSummary` statt festem Dict) — und trifft damit den Trip.
   Eine Auswahl **innerhalb der vorhandenen 7** braucht das nicht.
2. **`_location_heading` wurde in #1378 gerade zusammengeführt.** Für #1368.1
   muss der Ausblick eine eigene Überschrift bekommen; die Zeitzonen-Anschrift
   aus #1378 darf dabei nicht verloren gehen (sie hängt heute am Ortsnamen).
3. **„Nächste Etappen" steht im geteilten Baustein.** Der Text muss
   parametrisierbar werden, ohne den Trip-Wortlaut zu ändern.
4. **Mitternachts-Fenster:** Bei `start_hour > end_hour` umfasst
   `hourly_data` zwei Kalendertage (`comparison_engine.py:77-82`). Es gibt kein
   Feld „der im Detail gezeigte Tag"; der einzige Tagesbezug der Mail ist
   `target_date` im Kopf. V1 braucht dafür eine ausdrückliche Regel.
5. **Klartext bleibt Prüf-blind** — `email_spec_validator.py` liest nur HTML.
   Nachweis in beiden Mail-Teilen führen (Scheibe-B-Erfahrung).
6. **Renderer-Commit-Gate #811** greift (`email/outlook.py`, `compare_html.py`
   liegen unter `email/`): echte Compare-Test-Mail + `email_spec_validator`
   vor dem Commit.
7. **Viele Tests hängen am Ausblick** — u.a.
   `test_shared_outlook_renderer.py`, `test_compare_outlook.py`,
   `test_compare_outlook_placement.py`, `test_fix_911_visual_table.py`,
   `test_issue_721_email_outlook.py`, `test_compare_empty_metric_selection.py`.
   Trip-seitige Layout-Tests sind Byte-/Struktur-Checks und reagieren
   empfindlich auf Änderungen am geteilten Baustein.
8. **`test_shared_outlook_renderer.py::test_build_outlook_row_pure_function`
   ist vorbestehend rot** (Doppelimport `from src.output...` vs `output...`,
   ohne Zeitbezug, siehe #1196) — nicht mit einer eigenen Regression verwechseln.

## Existing Specs / Referenzen

- Epic #1372 Zielbild: „eine Größe, mehrere Auswertungen, Zuordnung je Ausgabe
  (Vergleichstabelle · Stundenverlauf · 3-Tages-Ausblick), Reihenfolge je Ausgabe"
- `docs/specs/modules/issue_1378_compare_zeitbasis.md` (Vorgänger-Scheibe)
- ADR-0024 (Drag-&-Drop-Reihenfolge), ADR-0035 (Tagesfenster)
- `docs/reference/mail_validators.md`
