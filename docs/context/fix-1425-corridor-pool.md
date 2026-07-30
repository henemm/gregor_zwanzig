# Context: fix-1425-corridor-pool

## Request Summary
#1425 Schritt 2, Teil 1 (Pool erweitern): der Trip-Korridor-Editor (Reiter „Wertebereiche", `context="route"`) bietet aktuell nur 6 fest verdrahtete Metriken (`ROUTE_METRIC_DEFS`) als Wertebereich an. Der Ortsvergleich hat dasselbe Problem in #1373 bereits gelöst, indem er seinen Pool aus dem zentralen Katalog aufbaut (`GET /api/compare/metrics`). Ziel dieses Workflows: den Trip-Pool analog umstellen — OHNE die Gewitter-Skalen-Vereinheitlichung (thunder_level Prozent vs. Katalog-Ordinalskala + Datenmigration), die ist ein separater Folge-Workflow.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:28-35` | `ROUTE_METRIC_DEFS` — feste 6er-Liste, wird durch Katalog-Zugriff ersetzt/erweitert |
| `corridorEditorState.ts:90-97` | `ROUTE_CORRIDOR_CATALOG_IDS` — 6-Zeilen-Brücke Katalog-ID → Route-Metric (enthält bereits `freezing_level`+`snowfall_limit`→`snow_line`, Issue #1387 behoben) |
| `corridorEditorState.ts:109-138` | `buildRoutePool()` — iteriert über `ROUTE_METRIC_DEFS`, muss auf Katalog-Quelle umgestellt werden (analog `buildComparePool`) |
| `corridorEditorState.ts:397-420` | `buildComparePool()` — Vorbild: nimmt `defs: CompareMetricDef[]` als Parameter statt Modulkonstante, sammelt unbekannte Metrik-IDs in `unknownCorridors` statt sie stillschweigend zu verwerfen (F003-Fix) |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts:42-97` | `buildCompareMetricDefs()` + `fetchCompareMetricCatalogOnce()` — Vorbild für den Fetch/Cache-Mechanismus, den `route` ebenfalls braucht |
| `CorridorEditor.svelte:24,29,79,81,92-96,107,193` / `CorridorEditorMobile.svelte:37,42,82,84,165` | Aufrufer von `buildRoutePool`; Kommentar `:92-96` markiert `context==='route'` bisher bewusst als synchron (kein Fetch) — muss beim Umbau async werden |
| `src/output/renderers/compare_metric_catalog.py` (`get_compare_metric_catalog()` `:234-269`, `_COMPARE_DEFAULTS` `:259-293`) | Enthält bereits `rangeMin/rangeMax/step/kind/ordinalLabels` je Metrik — die Skalen-Kuration, die `/api/metrics` NICHT liefert |
| `src/app/metric_catalog.py` | Echte SSoT (26 Einträge, 24 `selectable=True`) — aber ohne Range/Step-Daten |
| `api/routers/compare.py:11-22` (`GET /api/compare/metrics`) vs. `api/routers/config.py:58-89` (`GET /api/metrics`) | Zwei Endpunkte; `/api/compare/metrics` trägt die Slider-Skalen, `/api/metrics` nicht |
| `internal/model/trip.go:72` (`Corridor.Metric string`), `:188-195` (`AlertableMetrics`) | Kein Enum, keine serverseitige Validierung — neue Metrik-ID wird klaglos gespeichert |
| `src/output/renderers/email/html.py:555-569` (`TRIP_CORRIDOR_METRIC_TO_COL_KEY`) | Übergangs-Mapping aus Schritt 1, Kommentar verweist bereits auf „entfällt mit Pool-Umzug in Schritt 2" — NICHT Teil dieses Workflows (das ist Teil der Gewitter-Migration/Cleanup-Schritte 2+3 im Issue) |

## Existing Patterns
- **Compare hat das identische Problem bereits gelöst (#1373):** Katalog bleibt backend-seitig kuratiert (`compare_metric_catalog.py`), Frontend fetcht ihn einmalig (Promise-Cache) und übergibt `defs` explizit an `buildComparePool`/`addRow` statt eine Modulkonstante zu nutzen. Unbekannte Metrik-IDs werden nicht verworfen, sondern separat durchgereicht (Datenerhalt-Invariante, CLAUDE.md).
- `RouteMetricDef`/`CompareMetricDef` sind strukturell fast identisch (`metric, label, unit, scale, step, defaultMin, defaultMax`) — Compare hat zusätzlich `kind`, `ordinalLabels`, `alarmCapable`, `aggregationLabel`. Eine Vereinheitlichung der Typen ist denkbar, aber nicht zwingend Teil dieses Workflows.

## Dependencies
- **Upstream:** Trip-Pool bräuchte dieselbe Skalen-Kuration wie `compare_metric_catalog.py` liefert — entweder eigene Route-Kuration im Backend, oder Wiederverwendung derselben Quelle (Design-Entscheidung, s. Risiken).
- **Downstream:** `CorridorEditor.svelte` + `CorridorEditorMobile.svelte` (beide Aufrufer), `tests/tdd/test_alert_metric_mapping_parity.py` (parst `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS` per Regex aus der TS-Datei — bricht bei Umbenennung/Entfernung), `frontend/.../__tests__/weatherMetricsTabCorridorCoupling.test.ts:197-242` (testet snow_line-Brücke gegen `buildRoutePool`).

## Existing Specs
- `docs/specs/modules/feat_1373_s2_ein_katalog.md` — Compare S2, Zeile ~299-301 vermerkt explizit: „#1384 (Trip-Wertebereiche-Pool) ist NICHT Teil dieser Spec" — dieser Workflow holt das nach.
- `docs/specs/modules/issue_1231_korridor_editor.md` — Ursprungs-Spec des geteilten Korridor-Editors (context="route"/"vergleich").

## Risks & Considerations
- **Geteilte Komponente (CLAUDE.md Trip/Compare-Teilungs-Invariante):** Jede Änderung an `corridorEditorState.ts` kann den Compare-Pfad mitbetreffen — `buildComparePool`/Compare-Tests müssen byte-/verhaltensgleich bleiben.
- **Kein serverseitiges Enum** für `Corridor.Metric` (Go) — die Erweiterung ist rein clientseitig; kein Backend-Gate verhindert ungültige Metrik-IDs, aber es gibt auch keins zu migrieren.
- **`test_alert_metric_mapping_parity.py`** parst die TS-Konstanten per Regex — muss beim Umbau mitgezogen oder bewusst abgelöst werden (sonst Grün täuscht vor).
- **Design-Entscheidung offen:** Nimmt Trip denselben Endpoint (`/api/compare/metrics`) wie Compare, oder einen neuen Route-spezifischen? `/api/compare/metrics` heißt „compare" im Pfad, liefert aber inzwischen einen allgemeinen kuratierten Katalog — Umbenennung vs. Wiederverwendung ist eine Frage für die Spec-Phase.
- **Gewitter-Skala bewusst ausgeklammert:** Der Katalog kennt `thunder_level` als 3-stufige Ordinalskala (`kind:'ordinal'`), der aktuelle Trip-Wert ist Prozent 0-100. Wird der Pool naiv umgestellt, würde `thunder_level` plötzlich als Ordinal-Kind erscheinen, obwohl Bestandsdaten (Prozent) das nicht hergeben — **`thunder_level` muss in diesem Workflow von der Katalog-Übernahme ausgenommen bleiben** (weiterhin `ROUTE_METRIC_DEFS`-Eintrag, unverändert Prozent-Skala), bis der Folge-Workflow die Migration erledigt.
- **`unknownCorridors`-Analogie:** Bestehende Trip-Korridore mit einer der bisher fehlenden 18 Katalog-Metriken existieren nicht (Pool war ja bisher auf 6 begrenzt) — kein akutes Datenerhalt-Risiko beim Rollout, aber das Pattern (nicht still verwerfen) sollte trotzdem übernommen werden für zukünftige Katalog-Änderungen.

## Analysis

### Type
Feature (Erweiterung einer bestehenden Auswahlfläche, kein gemeldetes Fehlverhalten in diesem Teil).

### Technischer Ansatz (Plan/Sonnet-Bewertung, verifiziert + 1 Korrektur)
- **Endpoint:** `/api/compare/metrics` unverändert weiterverwenden (Backend-Quelle `compare_metric_catalog.py`, 26 Einträge mit `rangeMin/rangeMax/step/kind/metric_id/aggregation`). Kein neuer Route-Endpoint, keine Umbenennung.
- **Duplikat-Ausschluss (Kernrisiko, verifiziert):** Der Compare-Katalog führt bereits gebrückte Größen unter EIGENEN Keys mit `metric_id` aus derselben Gruppe wie `ROUTE_CORRIDOR_CATALOG_IDS` (z.B. `temp_max_c`/`temp_min_c` → `metric_id="temperature"`, `gust_max_kmh` → `"gust"`, `precip_sum_mm` → `"precipitation"`, `thunder_level_max` → `"thunder"`, `freezing_level_m` → `"freezing_level"`, `snowfall_limit_m` → `"snowfall_limit"` — nachgezählt in `compare_metric_catalog.py:64-145`). Ohne Filter entstünden Doppel-Einträge (z.B. zwei "Temperatur"-Zeilen: die alte alarm-verdrahtete `temperature_max` und eine neue, nicht verdrahtete `temp_max_c`). Filter: alle Einträge ausschließen, deren `metric_id` in der bestehenden `ROUTE_CORRIDOR_CATALOG_IDS`-Schlüsselmenge (`gust, precipitation, temperature, thunder, snowfall_limit, freezing_level`) auftaucht. Rechnung: 26 − 2 (`_COMPARE_RANGE_UNSUPPORTED`: precip_type_dominant, wind_direction_deg) − 7 (Duplikate) = 17 neue Metriken. Das schließt `thunder_level_max` automatisch aus — kein separater Sonderfall für die Gewitter-Ausklammerung nötig.
- **Korrektur ggü. Plan-Entwurf:** `metric_id` existiert nur auf der Roh-Antwort `CompareMetricCatalogEntry` (`types.ts:467`), NICHT auf dem daraus mit `buildCompareMetricDefs()` erzeugten `CompareMetricDef` (das Feld wird beim Mapping fallengelassen, `compareMetricCatalogLoader.ts:42-69`). Der Duplikat-Filter muss deshalb auf den **rohen** Katalog-Einträgen laufen (vor oder während der Umwandlung in Route-Zeilen), nicht auf bereits gebauten `CompareMetricDef[]`. Sauberster Schnitt: ein eigener, kleiner Mapper `buildRouteMetricDefsFromCatalog(entries: CompareMetricCatalogEntry[]): RouteMetricDef[]` neben `buildCompareMetricDefs`, der filtert und auf `RouteMetricDef`-Form (kein `kind`/`ordinalLabels` nötig, da Ordinal/Enum-Fälle durch den Filter bzw. `_COMPARE_RANGE_UNSUPPORTED` bereits draußen sind) abbildet — ändert `CompareMetricDef` NICHT, also keine Rückwirkung auf den Compare-Pfad.
- **`buildRoutePool`-Umbau:** neuer optionaler Parameter `extraDefs: RouteMetricDef[] = []`, angehängt an die weiterhin byte-identische `ROUTE_METRIC_DEFS`-Konstante (Testschutz, s.u.). Gating gegen den Wetter-Metriken-Tab (`activeCatalogMetrics`) für die neuen Defs direkt über deren mitgeführte `metric_id`, für die alten 6 unverändert über `ROUTE_CORRIDOR_CATALOG_IDS`.
- **Fetch/Cache:** denselben Promise-Cache wiederverwenden (`fetchCompareMetricCatalogOnce()`), Route bekommt keinen zweiten Netzwerk-Request. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` müssen dafür für `context==='route'` denselben `$effect`-Ladepfad wie `context==='vergleich'` bekommen (bisher bewusst synchron, Kommentar `CorridorEditor.svelte:92-96`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `corridorEditorState.ts` | MODIFY | `buildRoutePool` bekommt `extraDefs`-Parameter; `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS` bleiben unverändert |
| `compareMetricCatalogLoader.ts` (oder neue Datei) | MODIFY/CREATE | Neuer Mapper `buildRouteMetricDefsFromCatalog()` mit Duplikat-Filter über `metric_id` |
| `CorridorEditor.svelte` | MODIFY | Async-Ladepfad für `context==='route'` analog `vergleich` |
| `CorridorEditorMobile.svelte` | MODIFY | dito |
| `corridorEditorState.test.ts` / Frontend-Unit-Tests | MODIFY/CREATE | Neue Fälle: Duplikat-Ausschluss, `thunder` fehlt weiterhin, Ladezustand |
| `weatherMetricsTabCorridorCoupling.test.ts` | MODIFY | Bestehende 6er-Fälle unverändert grün halten, ggf. neue Fälle ergänzen |
| `tests/tdd/test_alert_metric_mapping_parity.py` | KEINE Änderung erwartet | Regex-Parser bleibt unberührt, solange die beiden Konstanten unverändert bestehen bleiben |

### Scope Assessment
- Files: ~6-7
- Estimated LoC: +150/-0 bis +250/-0 (überwiegend Tests)
- Risk Level: MEDIUM (geteilte Komponente, aber rein additiv/lesend — kein Schreibpfad, keine Backend-Änderung, keine Datenmigration in diesem Workflow)

### Dependencies
- Upstream: `GET /api/compare/metrics` (unverändert), `compareMetricCatalogLoader.ts::fetchCompareMetricCatalogOnce()` (Wiederverwendung des Caches)
- Downstream: `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `test_alert_metric_mapping_parity.py` (Regressionsschutz, keine Änderung nötig), `weatherMetricsTabCorridorCoupling.test.ts`

### Open Questions
- [x] Duplikat-Ausschlussmechanismus — geklärt (Filter über `metric_id` auf Roh-Katalog-Ebene)
- [x] Gewitter-Ausschluss — ergibt sich automatisch aus dem Duplikat-Filter, kein Sonderfall nötig
- [x] Reihenfolge der ~17 neuen Metriken im Pool — PO-Entscheidung: Katalog-Reihenfolge (konsistent mit dem Ortsvergleich, kein eigener Sortiermechanismus)
- [x] "Notify"-Frage war gegenstandslos: Der "Warnen"-Button existiert im Korridor-Editor nicht mehr (`CorridorEditor.svelte:347-350`, entfernt in #1371) — nur noch "Markieren" (`mark`). Neue Metriken zeigen automatisch dasselbe (einzige) Bedienelement wie die alten 6, keine Fallunterscheidung nötig.
