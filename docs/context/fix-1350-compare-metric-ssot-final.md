# Context: fix-1350-compare-metric-ssot-final (Teil 3 von #1350)

## Request Summary
Schwellen-Editor/Pool des Ortsvergleichs (`COMPARE_METRIC_DEFS`) und — laut Issue — die Winner-Box
beziehen ihre Metrik-Definitionen aus dem Backend-Katalog `GET /api/compare/metrics` (Teil 1/2);
`compareMetricDefs.ts` fällt → echte Single Source of Truth. Persistenz-Keys unverändert (kein Datenverlust).

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/.../shared/corridor-editor/corridorEditorState.ts` | **Kern.** `CompareMetricDef` (Z.219-233), `COMPARE_METRIC_DEFS = ALL_METRICS.map()` (Z.273-289), `_COMPARE_DEFAULTS` (Z.256-271, 14 Keys), `_COMPARE_ALARM_KEYS` (Z.235-238, 10 Keys), `buildComparePool` (306-328), `addCompareRow` (341-360), `buildComparePrefillRows` (375-400), `buildCompareCorridorSavePayload` (422-483) |
| `frontend/.../compare/compareMetricDefs.ts` | **Soll fallen.** Katalog `ALL_METRICS` + Profil-Feature `IDEAL_DEFAULTS`/`IdealRange`/`ProfileKey`/`PROFILE_METRICS_WITH_SCALES` + toter Code `deriveIdealText`/`validateIdealRanges` |
| `src/output/renderers/compare_metric_catalog.py` | Backend-Katalog (Teil 1). Ggf. um `alarmCapable`(+`defaultMin/Max`) anzureichern. Charakterisierungs-Fixture `tests/tdd/test_compare_metric_catalog_endpoint.py` |
| `frontend/.../shared/corridor-editor/CorridorEditor.svelte` / `CorridorEditorMobile.svelte` | Konsumenten `buildComparePool`/`addCompareRow`/`COMPARE_METRIC_DEFS.filter`; rendern `scale/step/kind/ordinalLabels/alarmCapable/label/unit` |
| `frontend/.../weather-metrics-tab/weatherMetricsCompareSave.ts:12,25` | Default „alle Keys" = `COMPARE_METRIC_DEFS.map(d=>d.metric)` (Legacy `active_metrics=null`) |
| `frontend/.../shared/weather-metrics-tab/compareMetricSelection.ts` | **Vorbild-Mapper aus Teil 2** (`toCompareSelectionEntries`) |
| `frontend/src/lib/types.ts:428-444` | `CompareMetricCatalogEntry` (Endpoint-Typ) |
| `frontend/.../compare/CompareMatrix.svelte` | Winner-Box — **tote Komponente** (s.u.) |
| `frontend/.../compare/compareWizardState.svelte.ts`, `compareHubWizardBridge.ts`, `compareEditorSave.ts`, `compare-new/CompareNewEditor.svelte` | Konsumenten von `IdealRange`/`ProfileKey`/`PROFILE_METRICS_WITH_SCALES` (Profil-Feature) |

## Feld-Abgleich Endpoint ↔ `COMPARE_METRIC_DEFS` (Schwellen-Editor)
Endpoint liefert: `key/label/unit/decimals/higherIsBetter/kind/rangeMin/rangeMax/step` (+`ordinalLabels`/`enumValues`).
- **Direkt/ableitbar** (dünner Mapper analog `toCompareSelectionEntries`): `metric(=key)`, `label`, `unit`, `step`, `kind` (enum→range plattdrücken wie heute), `ordinalLabels`, `scale = [rangeMin??0, rangeMax??100]` (Thunder: `[0, ordinalLabels.length-1]`).
- **KEINE Endpoint-Quelle (echte Zusatzdaten):**
  - `defaultMin/defaultMax` — UX-Startwerte für neue Schwellen-Zeile (14 Keys), nur in `addCompareRow`/`buildComparePrefillRows` gelesen, NICHT im Row-Rendering.
  - `alarmCapable` — welche Metriken „Warnen" dürfen (10 Keys); Backend kennt die Liste bereits (`compare_alert._SUMMARY_KEY_TO_CATALOG_ID`).

## Winner-Box (CompareMatrix.svelte) — tote Komponente
`compare_matrix_dead_code.test.ts` (AC-20, `issue_1256_compare_ui_rewire.md`) sichert: CompareMatrix (+HourlyMatrix) haben KEINEN produktiven Import. Die lokale `PROFILE_METRICS`-Liste (mit `higherIsBetter`) wird nur INNERHALB dieser toten Komponente fürs Ranking gelesen (Z.57/131/134/160) — hängt NICHT an `compareMetricDefs.ts`. `higherIsBetter`-Werte decken sich bereits mit dem Backend-Katalog. **Folge:** Für den `compareMetricDefs.ts`-Abriss ist die Winner-Box irrelevant; „Winner-Box auf dieselbe Quelle" ist bei totem Code gegenstandslos → Option: tote Komponente + Guard-Test ersatzlos löschen (Aufräumen) statt an neue Quelle verdrahten.

## `compareMetricDefs.ts`-Zerlegung
- **(a) Katalog** (→ Endpoint): `MetricDef`(Typ, nur intern), `ALL_METRICS` (einziger Prod-Konsument = `COMPARE_METRIC_DEFS`).
- **(b) Profil-Feature** (Umzug nötig, natürliche Heimat `corridorEditorState.ts` bzw. neue `compareProfileDefaults.ts`): `ProfileKey`(5 Konsumenten), `IdealRange`(4), `IDEAL_DEFAULTS`(1: corridorEditorState), `PROFILE_METRICS_WITH_SCALES`(2). **Restkopplung:** `PROFILE_METRICS_WITH_SCALES` referenziert Katalog-Defs, Konsumenten nutzen aber nur `m.key`/`m.label` → auf Keys + Label-Lookup umstellbar.
- **(c) tot** (nur Tests): `deriveIdealText`, `validateIdealRanges` → mit Tests streichen.

## Zentrale Designentscheidungen (für /20-analyse, teils PO)
- **D1 (Kern, evtl. PO):** Wo leben `defaultMin/defaultMax` + `alarmCapable`?
  - (A) Endpoint/Katalog anreichern → volle SSoT, aber Backend-Touch (+ Teil-1-Fixture aktualisieren).
  - (B) dünne FE-Default/Alarm-Tabelle (ohne `ALL_METRICS`) → `compareMetricDefs.ts` fällt trotzdem, aber Defaults/Alarm bleiben FE-seitig (partielle SSoT).
  - (Hybrid) `alarmCapable` → Backend (semantisch Alarm-Engine-Wissen), `defaultMin/defaultMax` → dünne FE-UX-Tabelle (Präzedenz: Trip hält Startwerte FE-seitig). Tech-Lead-Neigung: Hybrid.
- **D2:** Tote Winner-Box (`CompareMatrix.svelte` + `HourlyMatrix.svelte`?) im Rahmen „toten Code aufräumen" löschen (inkl. `compare_matrix_dead_code.test.ts` + Referenzen in `issue_462.test.ts`/`issue_390`), oder unangetastet lassen? Neigung: löschen (Issue nennt Aufräumen).
- **D3:** Profil-Feature-Umzug (b) — Zielort `corridorEditorState.ts` vs. neue `compareProfileDefaults.ts`.

## Risks & Considerations
- **Datenverlust-Klasse:** `buildCompareCorridorSavePayload` schreibt `corridors`/`ideal_ranges`/`metric_alert_levels`; `min/max` der Rows kommen aus `corridors[]`/`defaultMin/Max`. Charakterisierungs-Tests: Schwellen-Defaults, Pool, Save-Payload müssen bitgleich bleiben.
- **Reaktivität/Async:** Schwellen-Editor bekommt (wie Teil 2) einen Fetch statt statischer Liste → Lade-/Fehlerzustand, Staging-PUT-Count.
- **`kind`-Flattening:** Endpoint hat `enum` (precip_type_dominant); FE muss wie heute auf `range` reduzieren, sonst UI-Bruch.
- **Scope/LoC:** groß, wahrscheinlich >250 LoC → ggf. weiter in Sub-Scheiben schneiden (PO-Regressionsangst). Backend-Touch bei D1(A/Hybrid) → eigener Charakterisierungs-Lauf.
