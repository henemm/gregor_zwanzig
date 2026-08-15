---
entity_id: feat_1728_s2_editor
type: module
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [metrics, sms, editor, frontend, aggregation]
---

<!-- Issue #1728 Scheibe 2 (Frontend/Editor) — Wegfall des Bedienabschnitts
     "05 — Auswertungen" im Trip-Editor, Kürzel-Zeilen für die vier neuen
     Tagesrichtungs-Größen (#1728 Scheibe 1) + wind_chill_night (Altlücke,
     #1484/#1660 A). -->

# Editor-Nachzug: Auswertungen-Block entfällt, fünf neue Kürzel-Zeilen (Frontend)

## Approval

- [x] Approved (PO „freigabe" 2026-08-15)

## Purpose

Der Editor-Abschnitt „05 — Auswertungen" (Trip-Kontext, `WeatherMetricsTab.svelte`)
steuert `MetricConfig.aggregations` — einen Mechanismus, der seit Scheibe 1
(`feat_1728_s1_temp_aufloesung`) an keinem Trip-Wirkort mehr gelesen wird
(SMS-Gate hängt an den vier neuen Katalog-IDs, die drei E-Mail-Pillen zeigen
unbedingt die Spanne). Der Block bliebe als totes, aber weiterhin bedienbares
UI-Element stehen und suggerierte eine Wirkung, die nicht mehr existiert.
Zusätzlich fehlen den vier neuen Tagesrichtungs-Größen sowie
`wind_chill_night` (vorbestehende, unabhängige Lücke seit #1484/#1660 A)
eigene Kürzel-Zeilen im Abschnitt „04 — Schwellwerte", obwohl Backend und
Katalog sie bereits vollständig unterstützen. Diese Scheibe entfernt den
toten Block, fügt die fünf fehlenden Kürzel-Zeilen nach Bestandsmuster
hinzu und migriert bzw. ersetzt die dadurch betroffenen Tests.

## Source

Schicht: **Frontend / User-UI** (`frontend/src/lib/components/shared/`,
SvelteKit, geteilte Editor-Komponente `context="route"|"vergleich"`). Kein
Backend-Change (DEC-1) — weder Python-Core noch Go-API sind betroffen.

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` —
  **Identifier:** Abschnitt „04 — Schwellwerte" (`:1584-1718`, Ergänzung),
  Abschnitt „05 — Auswertungen" (`:1720-1757`, Entfernung), State-Variablen
  `aggregationMetricIds`/`showsAggregationChoice` (`:344-348`, Entfernung)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` —
  **Identifier:** `ROUTE_ONLY_SECTIONS` (`:42`, `'auswertungen'` entfernen)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/aggregation_selection.test.ts` —
  **Identifier:** komplette Datei (225 Zeilen), UI-unabhängige Teile migriert, Rest gelöscht
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts` —
  **Identifier:** Testfall `:38-40` (Positiv→Negativ)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/multiSymbolMetricRowWiring.test.ts` —
  **Identifier:** Erweiterung um 5 Fälle (Bestandsmuster)
- **File (neu):** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/buildWeatherConfigMetricsAggregations.test.ts` —
  Migrationsziel der UI-unabhängigen `buildWeatherConfigMetrics`-Fälle
- **File (neu):** `frontend/e2e/weather-metrics-editor-day-range-kuerzel.spec.ts` —
  Playwright-Klickpfad

## Estimated Scope

- **LoC produktiv:** ~120–150 (Budget 250) — 5× `MultiSymbolMetricRow`-Block
  (~45 Zeilen Ergänzung), 05-Block-Löschung (~-38 Zeilen inkl. Kommentar),
  State-Variablen-Löschung (~-8 Zeilen), `ROUTE_ONLY_SECTIONS`-Zeile (~-1 Zeile)
- **Files produktiv:** 2 (`WeatherMetricsTab.svelte` tragend,
  `weatherMetricsTabSections.ts` 1 Zeile)
- **Test-LoC:** realistisch ~250–300 (unter Budget 500, kein Override nötig) —
  neue Migrationsdatei ~60–80 Zeilen (Teilmenge aus 225 Zeilen Altbestand),
  `weatherMetricsTabSections.test.ts` ±10 Zeilen (Ersetzung, kein Zuwachs),
  `multiSymbolMetricRowWiring.test.ts` +~60 Zeilen (5 neue Fälle nach
  Bestandsmuster, ~12 Zeilen je Fall), neuer Playwright-Spec ~80–120 Zeilen
  (Vorbild `issue-494-trip-edit-design.spec.ts:208-216` + eigener Vergleich-
  Regressionscheck)
- **Test-Files:** 4 (1 gelöscht: `aggregation_selection.test.ts`; 1 neu:
  Migrationsdatei; 1 angepasst: `weatherMetricsTabSections.test.ts`; 1
  erweitert: `multiSymbolMetricRowWiring.test.ts`; 1 neu: Playwright-Spec)
- **Effort:** low-medium — reines Copy-Paste-Muster plus mechanische Test-
  Erweiterung, keine neue Design-Entscheidung
- **Risiko:** LOW-MEDIUM — größtes Risiko ist versehentliches Berühren des
  `AggregationMetricRow mode='multiple'`-Zweigs (Compare/Ausblick), s. DEC-2

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1728_s1_temp_aufloesung` | Spec | Backend-Voraussetzung: liefert die vier neuen Katalog-IDs + generisch erweiterte `GET /api/metrics`/`GET /api/sms-symbols` — bereits live (`5056726a`), kein weiterer Backend-Change nötig (DEC-1) |
| `trip_aggregation_selection` (#1357) | Spec | Quelle des jetzt abzuschaffenden Abschnitts „05 — Auswertungen"; wird durch diese Scheibe abgelöst, nicht gelöscht als Spec (bleibt als Historie stehen) |
| `compare_metric_order` § „Abgeloeste Festlegung" | Spec | Löst die frühere `ROUTE_ONLY_SECTIONS`-Festlegung ab (2026-07-18) — Referenz für den Umgang mit dieser Konstante |

## Implementation Details

### DEC-1 — Kein Backend-Change

`GET /api/metrics` (Grundauswahl) und `GET /api/sms-symbols` (Kürzel) sind
seit Scheibe 1 vollständig generisch und liefern die vier neuen Größen
bereits automatisch:

- `WeatherMetricsTab.svelte:495-503` lädt `GET /api/metrics` roh in
  `catalog`; `WeatherV2Grundauswahl.svelte:31-55` iteriert `CATEGORY_ORDER`
  ohne ID-Filter — alle vier neuen Größen (`category="temperature"`) stehen
  bereits als Toggle-Buttons in „02 — Grundauswahl".
- `metricSymbols` kommt generisch aus `GET /api/sms-symbols`
  (`WeatherMetricsTab.svelte:183-186`); `api/routers/config.py:55-57` baut
  `all_metric_ids` bereits aus `SMS_SYMBOL_BY_METRIC` +
  `SMS_MULTI_SYMBOLS_BY_METRIC` inklusive der vier neuen IDs
  (`metric_catalog.py:710-716`, Scheibe 1 live).

Diese Scheibe ändert **kein** Backend-File.

### DEC-2 — `AggregationMetricRow.svelte` bleibt vollständig bestehen

Die Komponente wird **nicht** gelöscht oder in ihrem `mode='multiple'`-Zweig
angefasst — nur ihr Trip-Aufrufer im 05-Block entfällt. Downstream-Nutzer,
die unverändert bleiben müssen:

- `WeatherMetricsTab.svelte:1308-1315` — Compare-Grundauswahl „02"
  (`context='vergleich'`-Zweig)
- `CompareOutlookLayoutControls.svelte:161-164` — 3-Tages-Ausblick

Beide nutzen `mode='multiple'` (`AggregationMetricRow.svelte:78-93`); nur
der `mode='single'`-Zweig (`:49-51,66-77`) gehörte zum jetzt entfallenden
05-Block. Der sichere, kleinstmögliche Diff entfernt den **Aufrufer**
(05-Block in `WeatherMetricsTab.svelte`), nicht die Komponente selbst.

### DEC-3 — `aggregationsMap` bleibt im State

Die State-Variable `aggregationsMap` (`WeatherMetricsTab.svelte:235`,
`$state`) bleibt bestehen — sie hängt weiterhin im Speicherweg
(`buildWeatherConfigMetrics(…, aggregationsMap)`, `metricsEditor.ts:338-379`,
Feld `aggregations` `:369`) sowie in Dirty-Vergleich/Laden/Reset
(`:370,376,380,444,461,837,854`). Nur die UI-Schreibstelle — der
`onSelect`-Callback im 05-Block (`:1743-1750`) — entfällt mit dem Block.
Vollständige Entfernung von `aggregationsMap` aus Modell/Loader/API ist
Scheibe 3 (`feat_1728_s1_temp_aufloesung`, Abgrenzung 2).

### DEC-4 — Test-Migration statt Löschung

`aggregation_selection.test.ts` (225 Zeilen) fällt nicht restlos weg. Prüfung
gegen die alten ACs von #1357 (`trip_aggregation_selection.md` AC-5/6/8/9):

| AC (#1357) | Überlebt den Wegfall? | Begründung |
|---|---|---|
| AC-5 (keine Auswahl bei nur 1 Auswertung) | Nein | prüft ausschließlich den entfallenden UI-Block |
| AC-6 (Roundtrip) | **Teilweise** | der reine `buildWeatherConfigMetrics(...)`-Payload-Bau mit `aggregationsMap`-Parameter bleibt gültig (DEC-3: die Funktion lebt bis Scheibe 3 weiter) — der Quelltext-Grep auf den UI-Block ist hinfällig |
| AC-8 (leere `aggregations` versteckt Mail-Pille) | **Teilweise** | nur der Payload-Teil (`buildWeatherConfigMetrics` schreibt leere Liste) bleibt gültig; die UI-Herleitung ist hinfällig |
| AC-9 (Vergleich bekommt Auswertungswahl nicht) | Nein, redundant | kanonische Prüfstelle ist `weatherMetricsTabSections.test.ts` (bleibt bestehen) |

**Migrationsziel:** neue Datei
`weather-metrics-tab/__tests__/buildWeatherConfigMetricsAggregations.test.ts`
— übernimmt ausschließlich die UI-unabhängigen `buildWeatherConfigMetrics`-
Aufrufe (Payload-Bau mit `aggregationsMap`-Parameter, Teile von AC-6/AC-8).
Kein Rendering, kein Quelltext-Grep auf UI-Elemente. Restliche Fälle in
`aggregation_selection.test.ts` werden mit der Datei gelöscht. Namensregel
eingehalten: nach Verhalten benannt, nicht nach Issue-Nummer.

### DEC-5 — `wind_chill_night` wird mitgenommen

Vorbestehende, von #1728 unabhängige Lücke: `wind_chill_night` hat heute
**keine** Kürzel-Zeile im Editor, obwohl sein Kürzel `FN` seit #1660 A im
Katalog existiert (`metric_catalog.py:224`, `compact_label="TFN"`, zur
Laufzeit `"FN"` durch Register-Ableitung). PO-bestätigt: bei dieser
Gelegenheit mitgenommen, weil dieselbe Stelle und dasselbe Muster betroffen
sind — kein eigenes Ticket dafür.

### DEC-6 — Fünf neue Kürzel-Zeilen (Copy-Paste-Muster)

Exaktes Muster der drei Bestandszeilen `temperature`/`temperature_night`/
`wind_chill` (`WeatherMetricsTab.svelte:1692-1713`, Abschnitt
„04 — Schwellwerte", `{#if sections.includes('sms_schwellen')}` `:1584` …
`:1718`), fünf neue `{#if}`-Blöcke direkt danach eingefügt:

| metricId | Default-Label (Fallback) | Kürzel |
|---|---|---|
| `temperature_day_low` | „Tages-Tiefsttemperatur (Gehzeit)" | `K` |
| `temperature_day_high` | „Tages-Höchsttemperatur (Gehzeit)" | `D` |
| `wind_chill_day_low` | „Gefühlte Tages-Tiefsttemperatur (Gehzeit)" | `FK` |
| `wind_chill_day_high` | „Gefühlte Tages-Höchsttemperatur (Gehzeit)" | `FD` |
| `wind_chill_night` | „Gefühlte Nacht-Tiefsttemperatur" (`metric_catalog.py:221`) | `FN` |

Jeder Block: `{#if !buckets.off.includes('<id>')}` … `<MultiSymbolMetricRow
metricId="<id>" label={metricById['<id>']?.label ?? '<Fallback>'}
symbols={metricSymbols['<id>'] ?? []} />` … `{/if}`. `wind_chill` selbst
behält seine bestehende Zeile unverändert (`WC` weiterhin daran gebunden,
DEC-3 aus Scheibe 1) — keine Anpassung an der bestehenden Zeile.

### DEC-7 — 05-Block-Entfernung

Vollständig entfernt:

- Kommentar+Block: `WeatherMetricsTab.svelte:1720-1757` (38 Zeilen)
- `{#if sections.includes('auswertungen') && aggregationMetricIds.length}`-
  Fragment: `:1727-1757` (31 Zeilen)
- State-Variablen, exklusiv am Block: `aggregationMetricIds` (`$derived`,
  `:344-348`, Lesestellen nur `:1727,:1737`), `showsAggregationChoice`
  (Import `:58`, Aufruf `:346`, einzige Verwendung)

`aggregationsMap` bleibt bestehen (DEC-3) — nur der `onSelect`-Callback
(`:1743-1750`) fällt mit dem Block.

### DEC-8 — `ROUTE_ONLY_SECTIONS` bereinigen

`'auswertungen'` aus `weatherMetricsTabSections.ts:42` entfernen — doppelte
Absicherung gegen erneutes Rendern (Verteidigung in der Tiefe, zusätzlich
zum Entfernen des `{#if}`-Blocks selbst, wie im Bestand üblich). Der
`vergleich`-Zweig (`{#if context === 'vergleich'}` ab `WeatherMetricsTab.svelte:1253`)
nimmt strukturell ohnehin einen anderen Render-Pfad — der 05-Block-Code lag
nur im `route`-Zweig, „05" war bereits doppelt auf `route` beschränkt.

### DEC-9 — `weatherMetricsTabSections.test.ts` auf Negativ drehen

`:38-40` prüft aktuell **positiv**, dass `weatherMetricsTabSections('route')`
`'auswertungen'` enthält — das widerspricht der neuen Zusage direkt. Der Fall
wird **ersetzt** (nicht ergänzt) durch das Gegenteil: `'auswertungen'` ist in
KEINEM Kontext (`route` noch `vergleich`) mehr enthalten. Format-Vorbild
bleibt die Datei selbst (37 Zeilen, ein Testfall pro Zusicherung, direkter
Funktionsaufruf ohne Rendering).

### DEC-10 — `multiSymbolMetricRowWiring.test.ts` erweitern

Reiner Quelltext-Regex-Test (kein Svelte-Rendering-Harness verfügbar,
137 Zeilen Bestand) — Vorbild für die Verdrahtungsprüfung der fünf neuen
Zeilen: Import vorhanden, Gate-Block-Muster
`{#if !buckets.off.includes('<id>')}...{/if}` vorhanden, Prop-Bindung
(`metricId`, `symbols={metricSymbols['<id>'] ?? []}`) nicht hartcodiert. Fünf
neue Fälle nach exakt diesem Muster, ein Fall je neue metricId.

### DEC-11 — Playwright-Klickpfad nach Bestandsmuster

Kein bestehender Test deckt die 05-Block-Testids ab
(`metric-aggregations`, `aggregation-metric-row-*`, `aggregation-option-*`
kommen in `frontend/e2e/**` nirgends vor). Format-Vorbild:
`frontend/e2e/issue-494-trip-edit-design.spec.ts:208-216` (Testname
„… existieren NICHT mehr im DOM", `toHaveCount(0)` je entferntem Testid) und
`versand-tab.spec.ts:142-163` (Element nach Umzug verschwunden).

Neuer Spec `frontend/e2e/weather-metrics-editor-day-range-kuerzel.spec.ts`
deckt drei Punkte ab:

1. Trip-Editor öffnen, „05 — Auswertungen" existiert **nicht mehr**
   (negativer Nachweis, Selektor nicht gefunden).
2. Die fünf neuen Kürzel-Zeilen in „04 — Schwellwerte" sichtbar prüfen
   (positiver Nachweis über stabile Testids `sms-multi-symbol-row-{metricId}`
   und `sms-symbol-badge-{metricId}-{symbol}`, `MultiSymbolMetricRow.svelte:17,21`
   — bereits vorhandenes, stabiles Testid-Schema, kein neues Schema nötig).
3. Vergleich-Editor bleibt unverändert (Regressionsschutz) —
   `AggregationMetricRow mode='multiple'` funktioniert dort weiterhin
   sichtbar (mindestens ein Sichtprüfungspunkt in der Compare-Grundauswahl
   oder im 3-Tages-Ausblick).

**Aufnahme in die CI-Positivliste (`.github/ci_e2e_specs.txt`) ist NICHT Teil
dieser Scheibe** — Filter B verlangt 3× grün im Zielverbund, das kann ein
neuer Spec nicht selbst herstellen. Bis zur Aufnahme läuft der Spec lokal/
manuell, nicht automatisch in CI. „E2E bestanden" gilt erst nach erfüllten
Aufnahmekriterien.

## Expected Behavior

- **Input:** Trip-Editor, Abschnitt „04 — Schwellwerte" — fünf zusätzliche
  Kürzel-Zeilen für Größen, die in „02 — Grundauswahl" bereits wählbar sind
  (seit Scheibe 1). Abschnitt „05 — Auswertungen" existiert nicht mehr.
- **Output:** Trip-Kontext zeigt keine Auswertungswahl-UI mehr (Spanne/
  Tiefst/Höchst/Mittel-Buttons entfallen ersatzlos); die vier neuen
  Tagesrichtungs-Größen sowie `wind_chill_night` zeigen ihr Kürzel-Badge
  in „04 — Schwellwerte", sobald sie nicht abgewählt sind. Vergleich-Kontext
  unverändert.
- **Side effects:** keine — reine Editor-Darstellung, kein neuer
  API-Aufruf, kein geänderter Speicherpfad (`aggregationsMap` bleibt im
  Payload, DEC-3).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Editor mit `temperature_day_low` nicht abgewählt / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint die Zeile mit Testid `sms-multi-symbol-row-temperature_day_low` und Kürzel-Badge `sms-symbol-badge-temperature_day_low-K`.
  - Test: `multiSymbolMetricRowWiring.test.ts`, neuer Fall für `temperature_day_low` (Quelltext-Verdrahtungsprüfung); Klickpfad-Nachweis zusätzlich in `weather-metrics-editor-day-range-kuerzel.spec.ts`.

- **AC-2:** Given ein Trip-Editor mit `temperature_day_high` nicht abgewählt / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint die Zeile mit Testid `sms-multi-symbol-row-temperature_day_high` und Kürzel-Badge `sms-symbol-badge-temperature_day_high-D`.
  - Test: `multiSymbolMetricRowWiring.test.ts`, neuer Fall für `temperature_day_high`; Klickpfad-Nachweis in `weather-metrics-editor-day-range-kuerzel.spec.ts`.

- **AC-3:** Given ein Trip-Editor mit `wind_chill_day_low` nicht abgewählt / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint die Zeile mit Testid `sms-multi-symbol-row-wind_chill_day_low` und Kürzel-Badge `sms-symbol-badge-wind_chill_day_low-FK`.
  - Test: `multiSymbolMetricRowWiring.test.ts`, neuer Fall für `wind_chill_day_low`; Klickpfad-Nachweis in `weather-metrics-editor-day-range-kuerzel.spec.ts`.

- **AC-4:** Given ein Trip-Editor mit `wind_chill_day_high` nicht abgewählt / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint die Zeile mit Testid `sms-multi-symbol-row-wind_chill_day_high` und Kürzel-Badge `sms-symbol-badge-wind_chill_day_high-FD`.
  - Test: `multiSymbolMetricRowWiring.test.ts`, neuer Fall für `wind_chill_day_high`; Klickpfad-Nachweis in `weather-metrics-editor-day-range-kuerzel.spec.ts`.

- **AC-5:** Given ein Trip-Editor mit `wind_chill_night` nicht abgewählt / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint die Zeile mit Testid `sms-multi-symbol-row-wind_chill_night` und Kürzel-Badge `sms-symbol-badge-wind_chill_night-FN` — die vorbestehende Lücke (DEC-5) ist geschlossen.
  - Test: `multiSymbolMetricRowWiring.test.ts`, neuer Fall für `wind_chill_night`; Klickpfad-Nachweis in `weather-metrics-editor-day-range-kuerzel.spec.ts`.

- **AC-6:** Given eine der fünf neuen Größen wurde in „02 — Grundauswahl" abgewählt (`buckets.off` enthält die metricId) / When Abschnitt „04 — Schwellwerte" gerendert wird / Then erscheint für diese metricId keine Zeile (Gate-Bedingung `!buckets.off.includes(...)` greift, kein reiner Existenz-Test ohne Abwahl-Gegenprobe).
  - Test: `multiSymbolMetricRowWiring.test.ts`, Abwahl-Fall je neuer Zeile (Bestandsmuster, Quelltext-Gate-Regex).

- **AC-7:** Given ein Trip-Editor (`context='route'`) / When der Abschnitt „05 — Auswertungen" gesucht wird / Then existiert weder der Quelltext-Block (`{#if sections.includes('auswertungen') ...}` ist aus `WeatherMetricsTab.svelte` entfernt) noch ein sichtbares DOM-Element im Browser.
  - Test: statische Prüfung im Repo (kein `sections.includes('auswertungen')`-Vorkommen mehr in `WeatherMetricsTab.svelte`) plus Playwright-Negativnachweis (`toHaveCount(0)`) in `weather-metrics-editor-day-range-kuerzel.spec.ts`, Vorbild `issue-494-trip-edit-design.spec.ts:208-216`.

- **AC-8:** Given `weatherMetricsTabSections('route')` / When die zurückgegebene Sektionsliste geprüft wird / Then ist `'auswertungen'` in KEINEM Kontext (weder `route` noch `vergleich`) mehr enthalten.
  - Test: `weatherMetricsTabSections.test.ts`, ersetzter Fall (vormals `:38-40` positiv, jetzt negativ).

- **AC-9:** Given der Ortsvergleich-Editor (`context='vergleich'`) / When die Compare-Grundauswahl „02" gerendert wird / Then funktioniert `AggregationMetricRow mode='multiple'` unverändert — der `vergleich`-Zweig war nie vom 05-Block betroffen und bleibt es (Regressionsschutz gegen versehentliches Mitentfernen).
  - Test: bestehende Compare-Tests, die `AggregationMetricRow mode='multiple'` prüfen, bleiben unverändert grün; Playwright-Sichtprüfungspunkt in `weather-metrics-editor-day-range-kuerzel.spec.ts` (Punkt 3, Vergleich-Editor öffnen, Grundauswahl-Mehrfachwahl sichtbar).

- **AC-10:** Given der 3-Tages-Ausblick (`CompareOutlookLayoutControls.svelte`) / When die Layout-Steuerung gerendert wird / Then funktioniert `AggregationMetricRow mode='multiple'` dort unverändert (`:161-164`) — kein Regressionsschaden durch die 05-Block-Entfernung im Trip-Kontext.
  - Test: bestehende Ausblick-Tests für `CompareOutlookLayoutControls` bleiben unverändert grün (keine Anpassung an diesem Test nötig — reiner Nichtberühr-Nachweis).

- **AC-11:** Given die UI-unabhängigen `buildWeatherConfigMetrics`-Fälle aus dem alten `aggregation_selection.test.ts` (Teile von AC-6/AC-8, #1357) / When sie in `buildWeatherConfigMetricsAggregations.test.ts` migriert laufen / Then bleiben sie grün — die geprüfte Funktion (`buildWeatherConfigMetrics` mit `aggregationsMap`-Parameter) lebt unverändert weiter, bis Scheibe 3 sie entfernt.
  - Test: `buildWeatherConfigMetricsAggregations.test.ts` (neu), migrierte Fälle ohne inhaltliche Änderung an der geprüften Funktion.

- **AC-12:** Given der komplette Klickpfad (Trip-Editor öffnen, „05" fehlt, fünf neue Zeilen sichtbar, Vergleich-Editor unverändert) / When der neue Playwright-Spec `weather-metrics-editor-day-range-kuerzel.spec.ts` lokal ausgeführt wird / Then läuft er vollständig grün gegen Staging — **ohne** dass daraus automatisch „E2E bestanden" im CI-Sinn folgt, solange der Spec nicht in `.github/ci_e2e_specs.txt` aufgenommen ist (Filter B: 3× grün im Zielverbund).
  - Test: manueller/lokaler Playwright-Lauf des neuen Specs gegen Staging; Aufnahmekriterien für die CI-Positivliste sind explizit NICHT Bestandteil dieser Scheibe (s. Known Limitations).

## Known Limitations

- **Neuer Playwright-Spec nicht sofort in der CI-Positivliste.** Die
  Wächst-nur-Ratsche (`.github/ci_e2e_specs.txt`) verlangt 3× grün im
  Zielverbund (Filter B) vor Aufnahme — das kann diese Scheibe nicht selbst
  herstellen. Bis zur Aufnahme läuft der Spec nicht automatisch in CI.
- **Testid-Kollision `aggregation-choices-temperature` im Vergleich bleibt
  unangetastet.** Zwei `mode='multiple'`-Aufrufer ohne `testidPrefix`
  erzeugen dasselbe Testid (`compare-outlook-metric-selection.staging.spec.ts:190`
  schließt den Fall bewusst aus). Vorbestehender Bestandsbefund, gehört ins
  Sammel-Issue #1199 (Nebenbefund-Triage), nicht in diese Scheibe.
- **`AggregationMetricRow` `mode='single'`-Zweig wird nach dieser Scheibe
  im Trip-Kontext nie mehr aufgerufen**, bleibt aber im Code stehen (DEC-2:
  Komponente nicht angefasst). Kein toter Zweig im engeren Sinn, da
  `mode='multiple'` weiterhin aktiv genutzt wird — nur der `single`-Pfad
  hat keinen Aufrufer mehr. Vollständige Bereinigung ist ggf. Teil von
  Scheibe 3.
- **`aggregationsMap` bleibt im State und im Speicherweg** (DEC-3) —
  Bestandstrips mit gespeicherter, jetzt unbedienbarer Auswertungswahl
  behalten diese beim Laden/Speichern unverändert bei (Merge, kein
  Replace). Kein sichtbarer Effekt mehr, da kein Wirkort mehr existiert
  (seit Scheibe 1).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe entfernt ein UI-Element, dessen zugrunde
  liegende Architekturentscheidung (Kürzel-Zeilen-Muster, Nachtgrößen-
  Abspaltung) bereits in #1484/#1660 A getroffen und in Scheibe 1
  (`feat_1728_s1_temp_aufloesung`) operationalisiert wurde. Sie schafft
  keine neue Entscheidungsfläche — reine Nachvollziehung im Frontend nach
  etabliertem Muster.

## Changelog

- 2026-08-15: Initial spec created (Issue #1728 Scheibe 2)
