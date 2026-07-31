# Context + Analyse: #1401 Scheibe B — Stundenverlauf + Alarme lesen aus dem Namensregister

## Request Summary

#1401 Scheibe B: Die Auswahlflächen **Stundenverlauf** (`compareHourlyMetricDefs.ts`, 10 eigene Namen) und **Alarme** (`AlertMetricLevelTable.svelte`, 14 eigene Namen + divergente Zweitkopie `alertMetricLabels.ts`) vergeben ihre Anzeigenamen weiterhin selbst statt sie aus dem zentralen Wetter-Namensregister (`src/app/metric_catalog.py`, seit Scheibe A1 live über `GET /api/metrics` bzw. `GET /api/compare/metrics`) abzuleiten. Ziel: beide Flächen lesen den Namen aus dem Register; die verbliebene Divergenz zwischen `AlertMetricLevelTable.svelte::METRIC_LABELS` und `alertMetricLabels.ts::ALERT_METRIC_LABELS` verschwindet.

Nicht Teil dieser Scheibe: Scheibe C (Begründung statt Leerstelle bei fehlenden Größen, Invariante 2) und S4/#1357 (Auswertung als eigenes wählbares Element — betrifft hier nur die Frage, ob `temperature_min`/`temperature_max` künftig als "Temperatur" + Auswertung erscheinen; das wird bewusst NICHT vorgezogen, siehe Analyse unten).

## Related Files

| Datei | Rolle |
|---|---|
| `src/app/metric_catalog.py` | Zentrales Namensregister (26 Größen, `label_de`), seit A1 SSoT. Liefert `GET /api/metrics` (Trip, alle Kontexte außer Vergleich lädt es aktuell nicht) |
| `src/output/renderers/compare_metric_catalog.py` | Vergleichs-Katalog (`GET /api/compare/metrics`, 26 Einträge, Name + `aggregation_label` getrennt) |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | **Ziel 1**: `ALL_HOURLY_METRICS` — 10 eigene `{key,label}`-Paare für die Stundenverlauf-Checkboxen im Vergleich. Bewusst "eigenständiges Vokabular" laut Kopfkommentar (Issue #1106) |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` | **Ziel 2**: `METRIC_LABELS` — 14 lokal getippte Namen, rendert die Alarme-Tabelle. Wird von `AlertsTab.svelte` (Trip, Legacy) UND von `shared/AlarmeTab.svelte` (geteilter Organismus, context=`route`\|`vergleich`, **ist entgegen dem "UNGEWIRED"-Kommentar im Dateikopf inzwischen live eingebunden** — s.u.) sowie von `CorridorEditor(Mobile).svelte` eingebunden |
| `frontend/src/lib/utils/alertMetricLabels.ts` | **Ziel 3**: `ALERT_METRIC_LABELS` — 14 Namen + Einheit + Vergleichsoperator. Breiter verwendet als nur die Tabelle: `TripEditView.svelte`, `TripOverview.svelte`, `AlertsPreviewCard.svelte`, `alert-rules-editor/AlertRuleRow.svelte`, `alerts-tab/alertMetricTable.ts` (Presets/Defaults) |
| `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts` | Bereits existierendes Vorbild für einen ID-Crosswalk (`COMPARE_TO_ALERT_METRIC`, 6 Einträge: Compare-Key → `AlertMetric`) |
| `src/output/renderers/compare_hourly_metric_ids.py::FRONTEND_TO_HOURLY_METRIC_ID` | Bestehende Backend-Ressource, mappt FE-Hourly-Keys → Renderer-Feld-IDs (NICHT identisch mit Katalog-`id`, daher nicht direkt wiederverwendbar für Labels) |

## Aktuelle Einbindung (verifiziert, Stand heute — Dateikopf-Kommentare teils veraltet)

`shared/AlarmeTab.svelte` (trägt `AlertMetricLevelTable`) wird tatsächlich eingebunden von: `compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte`, `trip-detail/TripTabs.svelte`, `trip-detail/AlarmeScheduleTab.svelte`, `shared/VersandTab.svelte`, `shared/WeatherMetricsTab.svelte`. Der Kopfkommentar "UNGEWIRED in dieser Scheibe (S2)" ist also überholt — die Fläche ist **produktiv, in beiden Kontexten**. `CompareAlarmSection.svelte` (die im Compare-Mapping-Kommentar erwähnte Vorgänger-Datei) existiert nicht mehr im Repo — bereits abgelöst.

## Existing Patterns

1. **A1-Muster (bereits etabliert):** `WeatherMetricsTab.svelte` (context=`route`) lädt `GET /api/metrics` → `MetricEntry[]` mit `id`/`label`/`unit` und baut daraus die Auswahlliste. Der Vergleichs-Zweig lädt stattdessen `GET /api/compare/metrics`. **Beide Register enthalten dieselben Namen je Wettergröße** (das war der Zweck von A1) — welches der beiden Register eine Fläche konsumiert, ist also für den Anzeigetext folgenlos.
2. **`/api/metrics` wird im Vergleichs-Kontext aktuell NICHT geladen** (Kommentar `WeatherMetricsTab.svelte:799`). Für Ziel 1 (Stundenverlauf, geteilt zwischen Trip und Vergleich) müsste entweder (a) `/api/metrics` zusätzlich im Vergleichs-Kontext geladen werden, oder (b) ein kleiner ID-Crosswalk analog `COMPARE_TO_ALERT_METRIC` gebaut werden. Variante (a) ist die "Rückbau statt Neubau"-Lösung ([[reference_trip_hourly_table_uses_central_catalog]]) — der Trip-Renderer (`dp_to_row`) nutzt für die Stundenzeile exakt dieselben 10 Basis-Größen aus demselben Katalog wie der Vergleich anzeigen soll.
3. **ID-Crosswalk-Pattern bereits etabliert**: `compareMetricMapping.ts::COMPARE_TO_ALERT_METRIC` zeigt das Muster für "kleine, stabile Zuordnungstabelle zwischen zwei Namensräumen, keine Textduplikation" — für Ziel 1 und Ziel 2/3 brauchen wir dasselbe Muster (Hourly-Key → Katalog-`id`, bzw. `AlertMetric` → Katalog-`id`).

## Dependencies

- **Upstream:** `src/app/metric_catalog.py` (Katalog-Wahrheit), `GET /api/metrics` (Go-Proxy `internal/router/router.go`).
- **Downstream:** Persistenz bleibt unverändert (Keys `temp_c`, `wind_gust` etc. sind Speicher-Keys, nicht Anzeigenamen — kein Datenverlust-Risiko).

## Existing Specs

- `docs/specs/modules/fix_1401_a2_mailtabellen.md` — A2a/A2b (Mail-Tabellen), als Vorbild für Beleg-/Test-Stil dieser Scheibe.
- `docs/specs/modules/issue_1106_hourly_metrics_config.md` — ursprüngliche Spec für `compareHourlyMetricDefs.ts` (bewusste Trennung vom Compare-Katalog — diese Prämisse wird mit Scheibe B aufgehoben).
- `docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md` — Ursprungsspec `alertMetricLabels.ts`.
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — `AlarmeTab.svelte`-Spec.

## Risiken & offene Design-Entscheidungen (für `/30-write-spec`)

1. **`temperature_min`/`temperature_max` haben im Katalog nur EINEN Eintrag (`id="temperature"`, "Temperatur")**, die Alarm-Metriken sind aber weiterhin schwellenwert-seitig getrennt (zwei Richtungen). Vorschlag: Anzeige wird "Temperatur" + Auswertung als Zusatz (z.B. "Temperatur (min)"/"Temperatur (max)"), NICHT der volle S4-Umbau (wählbare Auswertung) — nur die Beschriftung zieht nach. Analog: `wind_change`/`temperature_change`/`precipitation_change` haben **keine** Katalog-Entsprechung (Deltas, keine Absolutgröße) → bleiben unverändert, mit explizitem Ausnahme-Set (Muster: A2b `test_ac4_exemption_set_is_declared_and_complete`).
2. **Vergleichs-Kontext lädt `/api/metrics` aktuell nicht** — Ziel 1 braucht diesen zusätzlichen Ladevorgang oder eine gleichwertige Quelle. Zu klären in der Spec: zusätzlicher Fetch vs. Erweiterung von `/api/compare/metrics` um die 10 Hourly-Basisgrößen.
3. **`alertMetricLabels.ts` hat einen größeren Konsumentenkreis** als nur die Tabelle (Rule-Editor, Preview-Karten, Trip-Übersicht) — Änderungen dort wirken auf mehr Flächen als im Issue-Titel genannt. Das ist im Sinne des Issues (EIN Namensregister), aber die Spec muss diese Flächen explizit als "wird automatisch mitgezogen" benennen, damit der Adversary sie prüft.
4. **Renderer-Mail-Gate (#811) ist hier NICHT betroffen** — reine Frontend-Änderung, keine Mail-Renderer-Datei im Scope.
5. **Geteilte-Bausteine-Invariante**: `AlarmeTab.svelte` ist bereits geteilt (context-Prop) — Scheibe B ändert nur die Label-Quelle innerhalb des bestehenden geteilten Bausteins, baut nichts Neues auf, das dagegen verstoßen könnte.

## Nachtrag 2026-07-31: Design-Entscheidungen umgesetzt

Alle fünf oben offenen Fragen sind mit der Spec entschieden und implementiert
(Adversary VERIFIED, 54/54 Tests grün): Punkt 1 (`temperature_min`/`_max` →
"Temperatur (Minimum)"/"Temperatur (Maximum)", kein S4-Vorgriff), Punkt 2
(zusätzlicher `/api/metrics`-Fetch im Vergleichs-Kontext, fail-soft außerhalb
des Katalog-Gates), Punkt 3 (Blast-Radius-Konsumenten von
`alertMetricLabels.ts` explizit benannt und per Adversary geprüft). Details:
`docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md`.
