# Kontext/Analyse — Issue #1411 (Epic #1372, S4b Scheibe 1: Compare-Grundauswahl)

**Workflow:** `feat-1411-s4b-grundauswahl` · **Modus:** ÄNDERUNG (bestehende Compare-Grundauswahl umbauen)
**Blockiert durch:** #1357 (S4a, geschlossen, `07fe4641` live)
**Abgegrenzt von:** #1406 (S4b Scheibe 2 — die drei Kombi-Elemente Stundenverlauf/Ausblick/Alarme + Ausblick-Speicherfeld; **out of scope hier**, siehe #1406-Kommentar 2026-07-28 19:15)

## Ziel in einem Satz

Im Ortsvergleich werden aus zwei Auswahl-Zeilen „Temperatur" (Maximum) und „Temperatur" (Minimum) **eine** Zeile „Temperatur" mit zwei unabhängig ankreuzbaren Auswertungs-Kästchen (Maximum/Minimum) — ohne dass sich am Speicherformat, an der Reihenfolge-Liste oder an der Mail etwas ändert.

## Ist-Zustand

### Compare-Grundauswahl heute

`frontend/src/lib/components/shared/WeatherMetricsTab.svelte:900-921` (Card „Wetter-Metriken", `context='vergleich'`):

```svelte
{#each compareCatalog as entry (entry.metric)}
  <label class="vergleich-metric-row" data-testid="weather-metrics-vergleich-row-{entry.metric}">
    <input type="checkbox" checked={materializedActiveMetricKeys.includes(entry.metric)}
           onchange={() => toggleCompareMetric(entry.metric)} />
    <span>{entry.label}</span>
    {#if entry.aggregation_label}
      <span class="vergleich-aggregation" ...>{entry.aggregation_label}</span>
    {/if}
  </label>
{/each}
```

`compareCatalog` kommt aus `GET /api/compare/metrics` → `src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()`. Es sind **26 flache Einträge**, je einer pro `(metric_id, aggregation)`-Paar (`COMPARE_METRIC_CATALOG`, `compare_metric_catalog.py:64-145`). Seit #1401 A1 trägt jeder Eintrag `label` (aus dem zentralen Register, OHNE Auswertung im Namen) und `aggregation_label` als **eigenes** Feld daneben — das Kombinieren zu „Temperatur max" passiert seit A1 nicht mehr im Text, aber die 26 Einträge bleiben 26 **Checkbox-Zeilen**. Nur zwei `metric_id`s haben mehr als eine Auswertung im Katalog: `temperature` (max, min) und `wind_chill` (max, min) — alle übrigen 22 `metric_id`s haben genau eine. D. h. heute erscheinen „Temperatur" und „gefühlte Temperatur" als je zwei Zeilen, alle anderen 22 Größen als je eine Zeile mit einem (wirkungslosen, weil alternativlosen) Auswertungs-Badge.

Toggle-Pfad: `toggleCompareMetric()` (`WeatherMetricsTab.svelte:783-786`) → `toggleCompareMetricKeyFromState()` (`compareMetricOrder.ts:63-68`) → mutiert `wiz.activeMetricKeys` (Array von Auswahl-Schlüsseln, hier: Katalog-`key`s wie `temp_max_c`/`temp_min_c`), reihenfolge-erhaltend (`compareMetricOrder.ts:82-85`).

### Trip-Seite nach #1357 (der geteilte Baustein)

Zwei **getrennte** Karten, beide `context='route'`:

- **02 — Grundauswahl** (`WeatherMetricsTab.svelte:1059-1068`) → `WeatherV2Grundauswahl.svelte`: nach `CATEGORY_ORDER`/`CATEGORY_LABELS` gruppierte Toggle-Knöpfe, EIN Knopf je `metric_id` aus dem **zentralen** Katalog (`/api/metrics`, `Record<string, MetricEntry[]>`), reiner An/Aus-Zustand (`onToggle(id, wasOn)`). **Kennt keine Auswertung.**
- **05 — Auswertungen** (`WeatherMetricsTab.svelte:1269-1304`) → `AggregationMetricRow.svelte` + `aggregationSelection.ts`: EIN Segmented-Control je aktiver `metric_id` **mit mehr als einer berechenbaren Auswertung** (`showsAggregationChoice()`, `aggregationSelection.ts:47-49`), **EINZELWAHL** unter sich ausschließenden Möglichkeiten (Spanne/nur Min/nur Max/nur Mittel — PO 2026-07-28: „Es gibt kein zusätzlich: entweder oder"). Ergebnis wird in `aggregationsMap[metric_id] = string[]` (z. B. `['min','max']` für Spanne) gespeichert, das ist EIN Feld auf EINEM `MetricConfig`-Eintrag.

**Wichtig:** Der „geteilte Baustein aus #1357" ist NICHT `AggregationMetricRow`/`aggregationSelection.ts` allein einsetzbar für den Vergleich — dessen Datenmodell passt strukturell nicht (s. u.).

## Der technische Kern: Mengen-Wahl vs. Einzelwahl

Zwei Datenmodelle stehen sich gegenüber, und sie sind **nicht kompatibel**:

| | Trip (`aggregationSelection.ts`) | Vergleich (`compareCatalog`) |
|---|---|---|
| Ein Eintrag pro | `metric_id` (EIN `MetricConfig` mit Feld `aggregations: string[]`) | `(metric_id, aggregation)`-Paar (EIN Katalog-`key`, EIN Auswahl-Schlüssel) |
| Auswahl-Semantik | **Einzelwahl** unter 4 sich ausschließenden Möglichkeiten (`aggregationChoices()` inkl. synthetischer „Spanne" = min+max **in einer Kachel**) | **Mengen-Wahl**: jeder `key` unabhängig an/aus (`toggleCompareMetricKeyFromState`), **beliebig viele gleichzeitig** |
| Anzeige bei Max+Min aktiv | EINE Kachel „gef. 16.8–23.5 °C" (Spanne) | ZWEI Tabellenspalten „Temperatur Max" / „Temperatur Min" |

Der Vergleich braucht **keine** „Spanne"-Kachel-Logik (das ist ein Trip-Konzept) — er braucht pro `metric_id` mit >1 Auswertung eine Zeile mit **unabhängig** ankreuzbaren Kästchen, weil jedes Kästchen einen **eigenen** Katalog-`key` (und damit eine eigene Mail-Spalte) an/abschaltet. Das ist strukturell näher an einer Checkbox-Gruppe als an `AggregationMetricRow`s exklusivem Segmented-Control.

**Fehlender Parameter, konkret:**
1. **Gruppierungs-Funktion** fehlt: `aggregationSelection.ts` erwartet einen `MetricEntry` mit `.aggregations` (zentrales Katalog-Format). `compareCatalog` ist aber eine flache `CompareMetricCatalogEntry[]`-Liste ohne diese Struktur — es gibt noch keine Funktion, die die 26 Einträge nach `metric_id` gruppiert (→ 24 Gruppen, davon 22 mit 1 und 2 mit 2 Optionen).
2. **Mehrfachwahl-Darstellung** fehlt: `AggregationMetricRow.svelte` rendert einen exklusiven Segmented-Control (`aria-pressed={selectedChoiceId === c.id}`, genau EIN aktiver Button). Für den Vergleich müsste JEDE Option unabhängig toggle-bar sein (mehrere gleichzeitig „active"). Das ist eine Erweiterung des bestehenden Bausteins (neuer Modus-Parameter), keine Neuerfindung — passt zur Teilungs-Invariante, wenn als Parameter am bestehenden Baustein gelöst statt als Zweitkomponente.
3. **Keine „Spanne"-Merge nötig** im Vergleich — die Mengen-Wahl-Variante muss die rohen Optionen zeigen (Maximum/Minimum je eigenes Kästchen), nicht `aggregationChoices()`s synthetische Range-Option.

## Reihenfolge-Verhalten — am Code belegt, nicht geraten

**Befund: Die Umstellung der Grundauswahl berührt `wiz.activeMetricKeys` (das Reihenfolge-/Mail-Feld) nicht.**

- Der Klick auf „Maximum" bzw. „Minimum" ruft weiterhin `toggleCompareMetric(key)` mit dem jeweiligen **einzelnen Katalog-`key`** (`temp_max_c` bzw. `temp_min_c`) auf — exakt derselbe Mechanismus wie heute, nur ausgelöst von einem Kästchen INNERHALB einer gruppierten Zeile statt von zwei separaten Zeilen.
- `WeatherV2Reihenfolge.svelte` (`WeatherMetricsTab.svelte:946-956`) wird **nicht angefasst**. Sie liest weiterhin `materializedActiveMetricKeys` (Liste einzelner `key`s) und zeigt **weiterhin zwei getrennte, sortierbare Zeilen** „Temperatur / Maximum" und „Temperatur / Minimum" — mit unabhängiger Position und unabhängigem „Aus"-Knopf.
- Persistenz (`display_config.active_metrics`) bleibt im **Neuformat** `[{"metric_id": "temperature", "aggregation": "max"}, ...]` (seit #1373, `compareMetricSelection.ts:127-138`) — unverändert.
- Renderer (HTML/Klartext/Telegram/SMS) lesen `active_metrics` über `resolve_enabled_metrics()` (`compare_metric_ids.py:125-172`) — diese Funktion kennt nur einzelne `key`s, keine Gruppierung. Sie wird nicht berührt.

**Konsequenz:** Es gibt bei dieser Scheibe kein Datenverlust- oder Mail-Änderungs-Risiko durch die Umstellung selbst — die Grundauswahl-Karte wird nur **anders dargestellt** (eine Zeile statt zwei), das darunterliegende Array und die Reihenfolge-Karte bleiben unverändert. Die Mail zeigt Temperatur-Max und -Min weiterhin als zwei Spalten, wenn beide angehakt sind — **das war schon vor dieser Änderung so** und ändert sich nicht.

## Full- oder Frontend-only

**Frontend-only.** Belege:
- Go-Seite: `/api/compare/metrics` ist ein reiner Proxy (`internal/router/router.go:155` → `handler.ProxyHandler(...)`), keine Go-Modelländerung nötig. `active_metrics` ist bereits `map[string]interface{}` (opaque, `internal/model/trip.go` / ComparePreset), keine Schema-Änderung.
- Python: `get_compare_metric_catalog()` (`compare_metric_catalog.py:234-269`) liefert bereits alle nötigen Felder (`metric_id`, `aggregation`, `aggregation_label`, `label`, `key`). Für eine reine Frontend-Gruppierung nach `metric_id` ist **kein neues Feld** nötig (kein `category` auf `CompareMetricCatalogEntry` erforderlich — Gruppierung läuft über das bereits vorhandene `metric_id`). `resolve_enabled_metrics()` bleibt unverändert (s. o.).
- Betroffen sind ausschließlich: `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Markup-Block `context='vergleich'`), eine neue/erweiterte Pure-Function-Datei (Gruppierung), eine Erweiterung von `AggregationMetricRow.svelte`/`aggregationSelection.ts` (oder ein neuer Mengen-Wahl-Zweig darin) und die betroffenen Tests.

## Scoping

**Geschätzte Dateien:**

| Datei | Änderung | ~LoC |
|---|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts` (oder neue Datei `compareAggregationGrouping.ts`) | neue Pure-Function: `compareCatalog` (flach) → nach `metric_id` gruppierte Struktur `{metric_id, label, options: [{key, aggregation, aggregation_label}]}[]` | 40–60 |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | Mengen-Wahl-Modus ergänzen (mehrere Buttons gleichzeitig aktiv statt exklusiv) — ODER neue, sehr kleine Geschwister-Komponente mit dokumentierter Begründung (Einzelwahl vs. Mengenwahl ist ein echter Verhaltensunterschied, kein Duplikat) | 20–40 |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:900-921` | Checkbox-Liste durch gruppierte Zeilen ersetzen | Δ ~30–50 (Ersatz von ~18 Zeilen) |
| Unit-Tests (Gruppierungsfunktion, Muster `aggregation_selection.test.ts`) | neu | 60–100 |
| `frontend/e2e/fix-1350-compare-metric-select.staging.spec.ts`, `compare-active-metrics-format.staging.spec.ts`, `compare-editor-slice4.spec.ts` | Anpassen — s. Risiken | 30–60 |

**Summe grob 180–310 LoC** (ohne Doku/Spec). Das Limit von 250 LoC/Workflow ist **eng**, ohne die drei bestehenden E2E-Spec-Dateien (die zwingend mit angefasst werden müssen, weil sie strukturell von „eine Zeile pro Katalog-`key`" ausgehen) wahrscheinlich **überschritten**. Empfehlung: PO entscheidet über Override (`loc_limit_override`), sobald die tatsächliche Implementierung den genauen Wert zeigt — nicht vorab pauschal erhöhen.

## Nachweisbarkeit

- **DOM/Playwright (nicht-staging, `compare-editor-slice4.spec.ts`-Muster):** „Temperatur" erscheint genau einmal in der Grundauswahl-Liste, mit zwei unabhängig klickbaren Kästchen; Klick auf „Minimum" allein aktiviert `temp_min_c`, ohne `temp_max_c` zu berühren; beide gleichzeitig aktivierbar.
- **Reihenfolge/Mail-Regression (Staging, HTML UND Klartext-Teil derselben Mail — bekannter blinder Fleck des Pflicht-Validators, der nur HTML liest):** bei Max+Min aktiv weiterhin zwei Spalten in der Vergleichs-Mail, Zahl-für-Zahl gegen eine Mail vor der Änderung. Da die Persistenz/der Renderer nicht angefasst werden, ist das primär eine **Regressionsprobe**, kein Nachweis neuen Verhaltens.
- **Datenerhalt:** ein Bestandsvergleich mit nur `temp_max_c` aktiv lädt nach der Änderung weiterhin nur mit angehaktem „Maximum"-Kästchen (kein `min` fälschlich mit-aktiviert).

## Offene Entscheidungen für den Product Owner

1. **Reihenfolge-Verhalten bestätigen:** Die Reihenfolge-Liste (WeatherV2Reihenfolge) bleibt bei ZWEI separaten Zeilen „Temperatur / Maximum" und „Temperatur / Minimum" (unverändert), nur die Auswahl-Karte darüber zeigt eine zusammengefasste Zeile. **Empfehlung:** so lassen — deckt sich mit „Mail zeigt weiterhin zwei Spalten" und ist die risikoärmste Option (keine Änderung an Persistenz/Reihenfolge/Renderer). Alternative (Reihenfolge-Liste ebenfalls zusammenfassen) wäre #1406-Scope (drei Kombi-Elemente) und stünde im Widerspruch zur „zwei Spalten gleichzeitig"-Vorgabe.
2. **Baustein-Erweiterung vs. neue Komponente:** `AggregationMetricRow.svelte` um einen Mengen-Wahl-Modus erweitern (ein Parameter, EIN Baustein für Einzel- und Mengenwahl) statt einer zweiten, fast identischen Komponente. **Empfehlung:** Erweiterung — entspricht der Teilungs-Invariante direkter, und der Unterschied (exklusiv vs. unabhängig) ist als Prop klein abbildbar.
3. **LoC-Limit:** Realistische Schätzung 180–310 LoC, eng am/über dem 250er-Limit — vor allem wegen der drei bestehenden E2E-Spec-Dateien, die zwingend mitgezogen werden müssen (s. Risiken). **Empfehlung:** Erst mit echtem Diff neu schätzen, bei Bedarf Override anfragen — nicht vorab pauschal erhöhen.

## Risiken/Fallen am Code gefunden

- **Drei bestehende E2E-Spec-Dateien gehen von „eine Zeile pro Katalog-`key`" aus** (`weather-metrics-vergleich-row-{key}`, z. B. `weather-metrics-vergleich-row-temp_max_c`) und iterieren/zählen über `[data-testid^="weather-metrics-vergleich-row-"]` in der Annahme von bis zu 26 Zeilen (`fix-1350-compare-metric-select.staging.spec.ts:62-67`, `compare-active-metrics-format.staging.spec.ts:155-164`, `compare-editor-slice4.spec.ts:90`). Nach der Umstellung gibt es nur noch 24 gruppierte Zeilen, zwei davon mit mehreren Kästchen. Diese Tests brechen strukturell und müssen umgeschrieben werden (Test-ID-Schema ändert sich: eine Zeile pro `metric_id` statt pro `key`, plus ein Kästchen-Test-ID je Option) — nicht nur Werte anpassen.
- **`weatherMetricsTabVergleichLabels.test.ts` bleibt vermutlich unberührt**, weil er `toCompareSelectionEntries()` (Datenebene, unverändert) prüft, nicht die Svelte-Darstellung — trotzdem beim Umbau gegenlesen, ob eine neue Gruppierungsfunktion denselben Datenfluss nutzt oder eine Parallel-Quelle entsteht.
- **`weatherMetricsTabSections.ts:35`** hält `'auswertungen'` bewusst `ROUTE_ONLY` mit Kommentar „Er zieht mit #1411 nach". Dieser Kommentar (und die AC-9-Referenz auf `docs/specs/modules/trip_aggregation_selection.md`) muss in der Spec dieses Tickets aufgelöst werden — die Lösung hier fügt **keinen neuen Abschnitt `'auswertungen'`** für den Vergleich hinzu, sondern baut die Mengen-Wahl **in den bestehenden `'grundauswahl'`-Abschnitt** ein. Sollte das nicht der PO-Erwartung entsprechen, ist das eine offene Frage, keine Selbstverständlichkeit.
- **22 von 24 Gruppen haben nur eine Option** — für sie darf laut Invariante 1 („kein Element ohne Wirkung") keine unnötige Auswahl-Bedienung entstehen; sie sollten wie heute als einfache Checkbox-Zeile mit (nicht interaktivem) Auswertungs-Label erscheinen, nicht als „Gruppe mit einem Kästchen".
