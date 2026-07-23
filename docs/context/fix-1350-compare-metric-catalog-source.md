# Analyse: fix-1350-compare-metric-catalog-source (Scheibe 2 von #1335-Angleichung)

Issue #1350. Ziel laut ursprünglichem Plan: Compare-Editor zieht wählbare Metriken aus
`/api/metrics` statt handgepflegter Frontend-Liste `compareMetricDefs.ts`. **Analyse zeigt:
der naive Swap ist NICHT machbar** — drei harte Blocker, mehrstufiges Rework mit Datenverlust-Risiko.

## Ist-Kette (verifiziert)
- Quelle: `frontend/.../compare/compareMetricDefs.ts:30-74` (`ALL_METRICS`, 25 handgepflegte `MetricDef`).
- Editor-Modell: `corridorEditorState.ts:273-289` (`COMPARE_METRIC_DEFS = ALL_METRICS.map(...)`, reichert um `scale`/`defaultMin/Max`/`alarmCapable`/`kind` an).
- Selektions-UI: `WeatherMetricsTab.svelte:713-722` (`context='vergleich'`, kein Katalog-Fetch).
- Backend-Autoritativ (nicht exponiert): `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID` — dieselben 25 Keys wie `ALL_METRICS`. **Das ist die echte Doppelpflege: FE-Liste ↔ diese Backend-Map müssen synchron bleiben** (die 10 fehlenden Metriken aus #1324 waren genau dieser Drift).

## Drei harte Blocker gegen naiven `/api/metrics`-Swap
1. **Namensraum-Bruch / Datenverlust-Risiko:** `/api/metrics` liefert Katalog-IDs (`temperature`), Compare persistiert/rendert eigene Keys (`temp_max_c`). Swap bricht gespeicherte `active_metrics`/`corridors` + die Render-Pipeline (BUG-DATALOSS-Klasse).
2. **Fehlende Präsentationsfelder:** `/api/metrics` (`config.py:58-83`) liefert KEINE `rangeMin/rangeMax/step/higherIsBetter/kind` — daran hängen Schwellen-Slider (Wertebereiche-Tab) + Winner-Box-Richtung (`CompareMatrix.svelte:76-134`). Selbst der **Trip** zieht seine Slider-Ranges nicht aus `/api/metrics`, sondern aus hartkodiertem `ROUTE_METRIC_DEFS`.
3. **min/max-Split + nicht ableitbare Keys:** 24 Katalog-Metriken → 25 Compare-Einträge (Temp min+max). 5 Keys (`sunny_hours_h`, `snowfall_limit_m`, `cloud_*_avg_pct`) haben im Katalog keine passenden `summary_fields`.

## Konsumenten (Regressionsflächen)
`ALL_METRICS`: `corridorEditorState.ts`, `compareWizardState`. `COMPARE_METRIC_DEFS`: `WeatherMetricsTab`, `CorridorEditor(Mobile)`, `weatherMetricsCompareSave.ts` (Default=alle Keys!), `buildComparePool`. Weitere `compareMetricDefs.ts`-Exporte (Ideal-Ranges/Profile): `CompareNewEditor`, `compareHubWizardBridge`, `compareEditorSave`. 4. Kopie: `CompareMatrix.svelte:29-51` (eigene `higherIsBetter`-Liste, laut Test mutmaßlich toter Code).

## Abgrenzung
Nur Übersichts-/Auswahl-Liste (`compareMetricDefs.ts`). Stundenliste (`compareHourlyMetricDefs.ts`) ist separates Vokabular, bewusst getrennt (Scheibe 1 #1335).

## Ansatz-Optionen
- **(A) Drift-Wächter (klein, risikoarm):** FE-Liste + Backend-`FRONTEND_TO_RENDERER_METRIC_ID` bleiben, aber ein Test/Gate erzwingt **Key-Parität** → keine stille Divergenz mehr (löst den #1324-Schmerz). Formal bleibt Doppelpflege, aber Fehler werden gefangen. Kein Datenverlust-Risiko.
- **(B) Voller SSoT-Umbau (3 Sub-Scheiben, riskant):** Dedizierter Backend-Compare-Katalog-Endpoint (aus `compare_metric_ids.py` angereichert um Labels/Ranges/`higherIsBetter`/`kind`), FE ersetzt `ALL_METRICS` durch Fetch. Berührt frozen DTO/api_contract, Persistenz-Roundtrip (Datenverlust-Klasse), 4 FE-Konsumenten. >250 LoC, mehrstufig.

## Empfehlung (Tech Lead)
**(A) zuerst.** Der gemeldete Kern-Schmerz ist stille Divergenz (Metrik im Backend, fehlt im Compare — #1324). Ein Paritäts-Wächter beseitigt das mit minimalem Risiko und ohne Datenverlust-Gefahr. Der volle Endpoint-Umbau (B) bringt echte SSoT, aber überproportional Aufwand+Risiko für den Grenznutzen — und selbst der Trip hält seine Ranges hartkodiert. B bewusst als eigene, sorgfältig geschnittene Epic-#1230-Arbeit, nicht unter Zeitdruck.

## Offene Design-Frage (PO)
Scope #1350: (A) Paritäts-Wächter jetzt, oder (B) voller SSoT-Endpoint-Umbau in 3 Sub-Scheiben?
