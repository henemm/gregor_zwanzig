# Context: #1585 — CAPE als Zutat unsichtbar (`selectable=False`)

## Request Summary

Issue #1585 war ursprünglich groß angelegt (ZWEI Gewitter-Metriken + Stufen-Korrektur). Scheibe B
(`thunder_probability`) ist laut Issue-Kommentar (2026-08-07) tot — keine belegte, flächige
Datenquelle. Laut Memory-Notiz (Roadmap-Korrektur 2026-08-10) ist der einzige noch offene Teil
dieses Issues **Rang 5**: die Metrik `cape` im zentralen Katalog bekommt `selectable=False`,
analog zum Präzedenzfall `confidence` (#710, ADR-0005). CAPE bleibt intern Zutat der
`thunder_level`-Fusion, verschwindet aber aus der Nutzer-Auswahl/-Sichtbarkeit.

Direkter Codeabgleich bestätigt: `cape`-Eintrag in `src/app/metric_catalog.py:351-377` hat aktuell
**kein** `selectable=False` — Rang 5 ist tatsächlich offen, nicht nur auf dem Papier erledigt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py:351-377` | Ziel der Änderung: `MetricDefinition(id="cape", ...)` bekommt `selectable=False` |
| `src/app/metric_catalog.py:67` | Feld-Deklaration `selectable: bool = True` |
| `src/app/metric_catalog.py:317-330` | Präzedenzfall `confidence` (#710) — Vorbild für Umsetzung |
| `src/app/metric_catalog.py:118-128` | Präzedenzfall `temperature_cold` (#914) |
| `src/app/metric_catalog.py:687-695` | `get_all_metrics()` — zentraler Filter (`[m for m in _METRICS if m.selectable]`) |
| `src/app/metric_catalog.py:605-613`, `:653-658` | `summary_field_for()`, `available_aggregations()` — schließen nicht-selectable aus |
| `src/app/metric_catalog.py:744,774,781` | `WEATHER_TEMPLATES` (alpen-trekking, radtour, wassersport) referenzieren `"cape"` |
| `api/routers/config.py:72-121` | `GET /api/metrics` — iteriert über `get_all_metrics()`, respektiert `selectable` |
| `api/routers/config.py:23-27` | `GET /api/templates` — liefert Template-Metrikliste **ungefiltert** (roh) |
| `src/output/renderers/email/helpers.py:117-120,175-177,283-288,304-311` | E-Mail-Renderer: generischer `if not metric_def.selectable: continue` |
| `src/output/renderers/compare_hourly_metric_ids.py:97-101` | Compare-Stundenverlauf E-Mail: leitet sich aus `get_all_metrics()` ab → respektiert `selectable` |
| `src/output/renderers/sms_trip.py:369-419` | SMS-Renderer: **prüft `selectable` nicht** — sammelt `cape_jkg` unconditional |
| `src/output/renderers/trip_report.py:288-292` | Kanal-Metrik-Auswahl für SMS läuft über `enabled`-Flag im `display_config`, nicht über Katalog-`selectable` |
| `src/output/channels/telegram.py`, `src/output/renderers/alert/render.py`, `alert/official_alerts.py` | **Keine** `selectable`-Prüfung gefunden |
| `src/output/renderers/compare_metric_catalog.py:119-121` | Ortsvergleich-Katalog (26 kuratierte Einträge) — löst `cape` über `get_metric()` auf, **nicht** über `get_all_metrics()`, prüft `selectable` nicht |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:420,434,478` | Frontend Compare/Corridor-Editor — hartkodierte Defaults für `cape_max_jkg`, unabhängig von `/api/metrics` |
| `frontend/src/lib/components/WeatherConfigDialog.svelte:93`, `shared/WeatherMetricsTab.svelte:436,524` | Trip-Editor + Ortsvergleich-Metriken-Tab: generischer Konsum von `/api/metrics`, kein Hardcoding — **keine Änderung nötig** |
| `src/output/metric_format.py:315-361` | `thunder_level_from_signals()` — CAPE-Signal für die Stufe (`:360-361`). **MUSS unverändert bleiben.** |
| `src/providers/thunder_enrichment.py:84-185` | `_fuse_thunder_levels()` — nutzt `cape_threshold_jkg`. Interne Fusion, unabhängig vom Katalog-Flag. |
| `src/services/weather_change_detection.py:51,91,613-655` | `AlertMetric.CAPE` — CAPE-Delta-Alarm (#1592), eigene Tabelle, unabhängig von `selectable` |
| `docs/adr/0005-confidence-not-selectable-metric.md` | ADR-Präzedenz: dokumentiertes Zielverhalten für `selectable=False` |
| `tests/tdd/test_issue_715_confidence_not_selectable.py` | Vorbild-Testsuite (AC-1/AC-3/AC-4/F001) |

## Existing Patterns

- **`selectable=False` heißt NICHT „nur aus Auswahl-UI/API ausblenden"** — beim `confidence`-Präzedenzfall
  verschwindet die Metrik auch aus dem **gerenderten E-Mail-Output** (Spalte + Werte), siehe
  `test_issue_715_confidence_not_selectable.py` F001 (`:183-260`). Nur der Sinn/Zweck der Metrik
  bleibt intern erhalten (z.B. `confidence` fließt weiter in `build_confidence_hint()`).
- **Bestandsdaten-Kompatibilität:** Der Loader (`src/app/loader.py:748-800`, `_parse_display_config`)
  übernimmt jede gespeicherte `metric_id` ungeprüft — kein Crash, keine Migration nötig. Filterung
  passiert ausschließlich beim Konsum (API-Antwort, Renderer), nicht beim Laden.
- **E-Mail-Renderer filtert generisch zentral** über `metric_def.selectable` (helpers.py, 4 Stellen)
  — ein neues `selectable=False` wirkt dort automatisch, ohne Code-Änderung.
- **Zwei Wege laufen NICHT über den zentralen Katalog-Flag** und respektieren `selectable` daher
  nicht automatisch: SMS (`enabled`-Flag statt `selectable`) und Ortsvergleich
  (`compare_metric_catalog.py`, eigener kuratierter 26er-Katalog + Frontend-Hardcoding in
  `corridorEditorState.ts`).

## Dependencies

- **Upstream:** `cape_jkg` als Rohgröße kommt aus `src/providers/openmeteo.py` — unverändert.
- **Downstream:** `thunder_level_from_signals()` und `_fuse_thunder_levels()` lesen `cape_jkg`
  weiterhin direkt aus den Rohdaten (`ForecastDataPoint.cape_jkg`), nicht über den Katalog-Zugriff
  — von `selectable` nicht betroffen. Ebenso der CAPE-Delta-Alarm (`AlertMetric.CAPE`,
  `weather_change_detection.py`) — eigene, unabhängige Tabelle.

## Existing Specs

- `docs/adr/0005-confidence-not-selectable-metric.md` — Präzedenz-ADR
- `docs/features/gewitter-gesamtkonzept.md` — Gesamtkonzept, Rang 5 der Roadmap (Abschnitt 11)

## Risks & Considerations

1. **E-Mail vs. SMS-Divergenz:** Ohne Zusatzmaßnahme verschwindet CAPE nach `selectable=False`
   aus der E-Mail-Tabelle der 3 Bestandstrips (`henning/14f1aafd`, `5f534011`, `74de939c`), bleibt
   aber im SMS-Kürzel `CP:` weiterhin sichtbar — inkonsistent zum PO-Ziel „CAPE wird unsichtbar,
   konsistent zu allen anderen Zutaten".
2. **Vergleichs-Preset 4 bleibt unberührt:** `compare_metric_catalog.py` prüft `selectable` nicht.
   Preset 4 (E-Mail/SMS/Telegram) würde CAPE nach der Änderung im Trip-Editor nicht mehr anbieten,
   im Ortsvergleich (Editor + Ausgabe) aber unverändert weiter anzeigen.
3. **`WEATHER_TEMPLATES`** referenzieren `"cape"` für 3 Aktivitätsprofile. `GET /api/templates`
   liefert die Liste ungefiltert — Frontend-Vorschau könnte `"cape"` weiter listen, obwohl der
   Katalog es für neue Trips still überspringt (kein Fehler, aber tote Referenz).
4. **PO-Entscheidung (2026-08-10):** CAPE soll **überall** unsichtbar werden — nicht nur im
   zentralen Katalog-Pfad. Scope für die Spec umfasst daher zusätzlich:
   - SMS: `CP:`-Kürzel für CAPE entfällt (`sms_trip.py`/`trip_report.py` — Kanal-Metrik-Auswahl
     muss `selectable` respektieren, nicht nur `enabled`)
   - Ortsvergleich: `compare_metric_catalog.py` muss `cape`/`cape_max` ausschließen; Frontend
     `corridorEditorState.ts` (Corridor-Pool-Defaults) ebenfalls bereinigen
   - Vergleichs-Preset 4 (E-Mail/SMS/Telegram) verliert CAPE als Bestandteil — Bestandsdaten dürfen
     dabei nicht crashen (gleiches Muster wie Trip-Loader: Konfig lädt still, Wert wird nur nicht
     mehr angezeigt)
   - `WEATHER_TEMPLATES`/`GET /api/templates` — CAPE-Referenz bereinigen, damit keine tote Referenz
     im Frontend-Vorschau-Pfad bleibt
   - **Unverändert bleibt:** `thunder_level_from_signals()`, `_fuse_thunder_levels()`,
     CAPE-Delta-Alarm (`AlertMetric.CAPE`, #1592) — diese lesen `cape_jkg` direkt aus Rohdaten,
     nicht über den Katalog, und sind vom `selectable`-Flag unabhängig.
