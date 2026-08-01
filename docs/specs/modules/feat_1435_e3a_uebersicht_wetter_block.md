---
entity_id: feat_1435_e3a_uebersicht_wetter_block
type: feature
created: 2026-08-01
updated: 2026-08-01
status: approved
version: "1.0"
tags: [metric-catalog, trip-detail, overview, trip-compare-sharing, dead-code-removal]
workflow: fix-1435-e3-namensfehler
---

# Feature #1435 Etappe E3a — Der Übersichts-Reiter einer Tour bekommt einen Wetter-Metriken-Block

## Approval

- [x] Approved — PO „Go", 2026-08-01. Einschließlich LoC-Ausnahme auf 1500
  (rund 1000 der ~1250 Zeilen sind reine Löschung) und der beiden vom
  Orchestrierer ergänzten Kriterien AC-11 (unbekannte Kennung verschwindet
  nicht still) und AC-12 (Sichtbarkeit am Handy per Bildschirmfoto).

## Purpose

Der Übersichts-Reiter einer Tour (`HubOverview.svelte`) zeigt heute vier
Blöcke — Etappen/Profil, Briefings, Alerts, Vorschau — aber **nicht**, welche
Wettergrößen die Tour überhaupt versendet, obwohl das die inhaltlich
wichtigste Einstellung einer Tour ist. Die Recherche zu #1435 E3 hat
außerdem gezeigt, dass die im Ticket genannte „Reparatur" (angeblich
englische Kennungen statt Namen) an totem Code ansetzen würde: die dafür
verantwortlich gemachten Bauteile (`WeatherMetricsPreviewCard.svelte`,
`MetricsPreview.svelte`, `TripOverview.svelte`) werden seit Issue #487
nirgends mehr gerendert. Diese Etappe schließt die echte Lücke — ein neuer
fünfter Block, der die eingestellten Größen in Klartext aus dem zentralen
Wetter-Namensregister zeigt — und entfernt im selben Zug den toten Code
samt seiner vier eigenen, nie erreichten Namens-/Default-Vokabulare.

## Source

> **Schicht-Hinweis:** reine Frontend-Änderung (SvelteKit). Das zentrale
> Wetter-Namensregister (`GET /api/metrics`) ist bereits produktiv und wird
> ausschließlich lesend konsumiert. Keine Go-, keine Python-Beteiligung —
> `resolve_trip_active_metrics()` (`src/output/renderers/trip_metric_ids.py`)
> bleibt unverändert und dient nur als Referenz-Semantik (s. Implementation
> Details Punkt 1).

- **File:** `frontend/src/lib/components/trip-detail/HubOverview.svelte`
- **Identifier:** neuer fünfter `<Card>`-Block in der rechten Spalte
  (Zeilen ~68-90), neue Prop `metricsCatalog`, neuer `$derived`
- **File:** `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts` *(neu)*
- **Identifier:** `resolveTripMetricsOverviewState()`
- **File:** `frontend/src/routes/trips/[id]/+page.server.ts`
- **Identifier:** `load()` (Zeilen 6-26) — zweiter, paralleler, fail-soft
  Fetch von `GET /api/metrics`
- **File:** `frontend/src/routes/trips/[id]/+page.svelte`, `frontend/src/lib/components/trip-detail/TripTabs.svelte`
- **Identifier:** Prop-Durchreichung `metricsCatalog` von `data` bis zu `HubOverview`

## Estimated Scope

- **LoC:** ~100 Produktivcode neu (~40 Block-Markup + Prop + `$derived` in
  `HubOverview.svelte`, ~45 geteilter Baustein `tripActiveMetricNames.ts`
  inkl. Dokumentationskommentar, ~12 Loader-Erweiterung in
  `+page.server.ts`, Rest Prop-Durchreichung in `+page.svelte`/`TripTabs.svelte`)
  + ~150 Zeilen neue Tests (node:test, Fixture- und AST-basiert) −
  **~1000 Zeilen Löschung** (tote Bauteile, toter E2E-Test, tote
  Testblöcke) → **Netto deutlich negativ**, das LoC-Gate zählt aber
  hinzugefügt **und** gelöscht (CLAUDE.md), macht also brutto ~**1250**
  gegen das 250-Zeilen-Budget. **Braucht eine PO-Ausnahme** — rund 80 % des
  Zeilenumfangs ist reine Löschung von nachweislich totem Code, kein neues
  Verhalten.
- **Files:**
  - 4 Produktivdateien geändert: `HubOverview.svelte`, `TripTabs.svelte`,
    `+page.server.ts`, `+page.svelte`
  - 2 Produktivdateien geändert (Aufräumen): `trip-detail/index.ts` (2
    Export-Zeilen entfernt), `frontend/src/lib/utils/rightColumn.ts` (4
    Symbole entfernt, `getReportSchedule`/`ReportSchedule` bleiben)
  - 1 Produktivdatei neu: `shared/trip-metrics/tripActiveMetricNames.ts`
  - 4 Produktivdateien gelöscht: `MetricsPreview.svelte`,
    `WeatherMetricsPreviewCard.svelte`, `WeatherMetricsPreviewCard.tokens.test.ts`,
    `TripOverview.svelte`
  - 1 E2E-Testdatei gelöscht: `frontend/e2e/trip-detail-overview-right.spec.ts`
  - 1 Testdatei geändert (Testblöcke der vier entfernten Funktionen raus,
    `getReportSchedule`-Tests bleiben): `frontend/src/lib/utils/rightColumn.test.ts`
  - 5 Testdateien neu (s. Test Plan)
- **Effort:** medium (überwiegend Löschen + eine kleine, klar begrenzte
  neue Fläche).

### Affected Files

| File | Change Type | Description |
|---|---|---|
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | neuer fünfter Block „Wetter-Metriken" + Prop `metricsCatalog` |
| `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts` | CREATE | geteilte Drei-Zustands-Namensauflösung |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | reicht `metricsCatalog` an `HubOverview` durch |
| `frontend/src/routes/trips/[id]/+page.server.ts` | MODIFY | lädt `/api/metrics` parallel, fail-soft |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | reicht `data.metricsCatalog` an `TripTabs` durch |
| `frontend/src/lib/components/trip-detail/index.ts` | MODIFY | Export-Zeilen 4 (`TripOverview`) und 9 (`WeatherMetricsPreviewCard`) entfernt |
| `frontend/src/lib/utils/rightColumn.ts` | MODIFY | `METRIC_LABELS`, `prettyLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics` entfernt |
| `frontend/src/lib/utils/rightColumn.test.ts` | MODIFY | zugehörige Testblöcke entfernt |
| `frontend/src/lib/components/trip-detail/MetricsPreview.svelte` | DELETE | tot seit #487 (nicht einmal exportiert) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | DELETE | tot seit #487 (nur re-exportiert, nie importiert) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.tokens.test.ts` | DELETE | testet ausschließlich die gelöschte Komponente |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | DELETE | tot seit #487, ersetzt durch `HubOverview.svelte` |
| `frontend/e2e/trip-detail-overview-right.spec.ts` | DELETE | prüft `right-card-*`-Testids, die nur in der gelöschten Karte existieren |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/metrics` (`api/routers/config.py:58`) | READ | zentrales Wetter-Namensregister, liefert `Record<category, MetricEntry[]>` — bereits produktiv, einziger Namenslieferant |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts::selectTableColumns` | READ | liefert bereits eine geprüfte Funktion „aktivierte Metrik-IDs → `MetricEntry[]` in `CATEGORY_ORDER`-Reihenfolge" — der neue Baustein ruft sie auf, statt eine zweite Sortierlogik zu schreiben |
| `frontend/src/lib/types.ts::WeatherConfigMetric`/`WeatherConfig`/`MetricEntry` | READ | Datenformen der Trip-Metrik-Auswahl bzw. des Katalogs, unverändert |
| `src/output/renderers/trip_metric_ids.py::resolve_trip_active_metrics()` | REFERENZ | kanonische Backend-Semantik der drei Zustände (Auswahl/Altbestand/Leerauswahl) — der neue Frontend-Baustein spiegelt NUR die Fallback-**Bedingung** (`len(dc.metrics) == 0`), nicht die Namens-/ID-Liste (s. Known Limitations) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:386-415` | REFERENZ | Muster für einen eigenständigen Katalog-Ladepfad mit Lade-/Fehlerzustand — hier NICHT übernommen, s. Implementation Details Punkt 3 (Server-Load statt Client-Fetch) |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_shared_labels.test.ts` | REFERENZ | Stilvorbild für den Ratsche-Test gegen ein neues Namens-/Default-Vokabular |
| `frontend/src/routes/trips/[id]/__tests__/pageServerEtagPassthrough.test.ts` | REFERENZ | Stilvorbild für den Loader-Test (`+page.server.ts` ist unter `node --test` nicht ausführbar, da es `$env/dynamic/private` importiert — doc-compliance-Test statt funktionalem Aufruf, s. Test Plan) |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1081ff` (Übersichts-Reiter des Ortsvergleichs) | UNVERÄNDERT | listet die gewählten Größen ebenfalls nicht — kein Gegenstück, das diese Etappe verletzen könnte (s. Known Limitations) |

## Implementation Details

### 1. Geteilter Baustein: Drei-Zustands-Namensauflösung

Neue Datei `frontend/src/lib/components/shared/trip-metrics/tripActiveMetricNames.ts`.
Nach der Teilungs-Invariante (CLAUDE.md, PO-Vorgabe „möglichst viel Code
zwischen Trip und Ortsvergleich teilen") gehört die **Namensauflösung**
(nicht das Block-Bauteil selbst) unter `shared/`, auch wenn heute nur der
Trip-Kontext sie aufruft — dieselbe Bauart wie `activeAlertMetricsFromCatalog.ts`
(E1a-2), das ebenfalls unter `shared/alarme-tab/` liegt.

```ts
export type TripMetricsOverviewState =
	| { kind: 'selected'; names: string[] }
	| { kind: 'altbestand' }
	| { kind: 'empty' };

export function resolveTripMetricsOverviewState(
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
): TripMetricsOverviewState {
	if (!metrics || metrics.length === 0) {
		return { kind: 'altbestand' };
	}
	const enabledMap: Record<string, boolean> = {};
	for (const m of metrics) enabledMap[m.metric_id] = m.enabled === true;
	const anyActive = Object.values(enabledMap).some((v) => v);
	if (!anyActive) {
		return { kind: 'empty' };
	}
	return { kind: 'selected', names: selectTableColumns(catalog, enabledMap).map((e) => e.label) };
}
```

Die Bedingung `!metrics || metrics.length === 0` spiegelt exakt
`trip_report.py:119`s `_trip_metrics_altbestand = len(dc.metrics) == 0` —
**nicht** die siebenteilige `DEFAULT_TRIP_METRIC_IDS`-Liste. Der Zustand
`altbestand` trägt bewusst **keine** Namen (s. Punkt 2) — die Funktion muss
den Standardsatz also nirgends kennen oder aufzählen. Reihenfolge kommt aus
`selectTableColumns()` (bereits vorhandene, getestete Funktion aus
`trip-detail/metricsEditor.ts`, nutzt `CATEGORY_ORDER`) — kein neuer
Sortier-Mechanismus.

Anders als beim Ortsvergleich trägt `WeatherConfigMetric` nur `metric_id` +
`enabled`, keine Auswertung (`aggregation`). Die E1b-Mehrdeutigkeitsregel
(„Temperatur (Minimum)" vs. „Temperatur (Maximum)") ist hier gegenstandslos:
das Trip-Register liefert für Temperatur genau eine `id="temperature"`
(`src/app/metric_catalog.py:87`), keine aggregationsabhängige Aufspaltung
wie im Compare-Katalog.

### 2. Block-Markup in `HubOverview.svelte` — drei Anzeige-Zustände plus Fehlerfall

Der neue Block wird als **erste** Karte der rechten Spalte eingefügt (vor
„Briefings laufen") — Begründung: es ist laut PO die inhaltlich wichtigste
Einstellung einer Tour, die anderen drei Karten sind organisatorisch
(Zeitplan, Alerts-Historie, Vorschau).

```svelte
<Card padding={18}>
	<Eyebrow style="margin-bottom: 10px;">Wetter-Metriken</Eyebrow>
	{#if !metricsCatalog}
		<p data-testid="hub-metrics-catalog-error" style="...">Wetter-Metriken konnten nicht geladen werden.</p>
	{:else if metricsState.kind === 'altbestand'}
		<p data-testid="hub-metrics-altbestand">Noch nicht eingestellt — es gilt der Standardsatz.</p>
	{:else if metricsState.kind === 'empty'}
		<p data-testid="hub-metrics-empty">Keine Wettergrößen ausgewählt — das Briefing enthält keine Wettertabelle.</p>
	{:else}
		<p data-testid="hub-metrics-selected">{metricsState.names.join(', ')}</p>
	{/if}
	<Btn variant="ghost" size="sm" onclick={makeJumpHandler('weather')}>Wetter-Metriken bearbeiten →</Btn>
</Card>
```

Vier sich gegenseitig ausschließende Zweige, eigene Testids je Zweig (analog
E1b, das ebenfalls unterscheidbare Testids für inhaltlich verschiedene
Sätze verlangt). Der Sprung-Link nutzt denselben Mechanismus wie die
bestehenden vier Karten — `makeJumpHandler('weather')` → `onJump('weather')`
→ `handleValueChange('weather')` in `TripTabs.svelte` (Zeile 134ff.),
identisch zum bereits verdrahteten `TABS`-Eintrag `{ value: 'weather',
label: 'Wetter-Metriken' }` (`TripTabs.svelte:80`).

### 3. Katalog-Ladeweg: Server-Load statt Client-Fetch (Fehlerklasse #1320)

`+page.server.ts` lädt `GET /api/metrics` **parallel** zum bestehenden
Trip-Fetch, fail-soft (`.catch(() => null)`), und gibt das Ergebnis als
`metricsCatalog` neben `trip`/`etag` zurück:

```ts
const [tripRes, metricsCatalog] = await Promise.all([
	fetch(`${API()}/api/trips/${params.id}`, { headers }),
	fetch(`${API()}/api/metrics`, { headers }).then((r) => (r.ok ? r.json() : null)).catch(() => null)
]);
```

Der Trip-Fetch behält seine bestehende Fehlerbehandlung (404/5xx) unverändert
bei — ein fehlgeschlagener Katalog-Fetch darf die Seite **nicht** zum
Kippen bringen, nur der neue Block verliert seine Datengrundlage
(vierter Zweig oben). Begründung für Server-Load statt eines eigenen
Client-seitigen Ladepfads (wie `WeatherMetricsTab.svelte:386-415`, mit
eigenem `loadError`-Zustand): dadurch existiert **kein** Ladefenster, in
dem der Block „Noch nicht eingestellt" zeigt, obwohl tatsächlich eine
Auswahl existiert — exakt die Fehlerklasse, die in E1a-2 (Befund F001,
#1320) real aufgetreten ist. `metricsCatalog` wandert unverändert von
`+page.svelte` (`data.metricsCatalog`) über `TripTabs.svelte` als Prop an
`HubOverview.svelte`.

### 4. Löschungen

Alle vier Dateien sind seit Issue #487 nirgends mehr eingebunden (Befund
im Kontextdokument, gegen den aktuellen Code verifiziert — s. Estimated
Scope/Affected Files):

- `frontend/src/lib/components/trip-detail/MetricsPreview.svelte` — nicht
  einmal exportiert
- `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` —
  nur re-exportiert (`index.ts:9`), nie importiert
- `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.tokens.test.ts` —
  testet ausschließlich die gelöschte Komponente
- `frontend/src/lib/components/trip-detail/TripOverview.svelte` — ersetzt
  durch `HubOverview.svelte`, dokumentiert das selbst im Kopfkommentar
- `frontend/e2e/trip-detail-overview-right.spec.ts` — prüft `right-card-*`-
  Testids, die nur in der gelöschten Karte existieren

`frontend/src/lib/components/trip-detail/index.ts` verliert die
Export-Zeilen 4 (`TripOverview`) und 9 (`WeatherMetricsPreviewCard`).

`frontend/src/lib/utils/rightColumn.ts` verliert `METRIC_LABELS`,
`prettyLabel`, `getDefaultMetricsForProfile`, `getActiveMetrics` — ihr
einziger Aufrufer war die jetzt gelöschte Karte bzw. `TripOverview.svelte`.
`getReportSchedule`/`ReportSchedule` bleiben **unverändert**: sie werden
produktiv von `TripHeader.svelte`, `BriefingPreviewCard.svelte` und
`TripEditView.svelte` genutzt. `frontend/src/lib/utils/rightColumn.test.ts`
verliert die Testblöcke der vier entfernten Funktionen; die
`getReportSchedule`/`getActivePreset`/`getPresetLabel`-Tests bleiben grün.

### 5. Ratsche gegen Rückfall

Analog `shared/__tests__/alarme_tab_shared_labels.test.ts` verbietet ein
Syntaxbaum-Test, dass in `tripActiveMetricNames.ts` (oder anderswo im
neuen Block) eine lokale Metrik-ID→Name-Tabelle oder eine hartkodierte
Standard-Metrik-Liste entsteht — die einzige erlaubte Quelle für Namen ist
der übergebene `catalog`-Parameter.

## Expected Behavior

- **Input A:** Eine Tour hat `display_config.metrics = [{metric_id:
  'temperature', enabled: true}, {metric_id: 'wind', enabled: true},
  {metric_id: 'gust', enabled: false}]`. Der Nutzer öffnet den Reiter
  „Übersicht".
- **Output A:** Der neue Block zeigt „Temperatur, Wind" (Register-
  Reihenfolge, nicht Einfüge-Reihenfolge; „Böen" fehlt, weil `enabled:
  false`) plus den Sprung-Link in den Reiter „Wetter-Metriken".
- **Input B:** Eine alte Tour hat `display_config.metrics` nicht gesetzt
  (bzw. `[]`).
- **Output B:** Der Block zeigt „Noch nicht eingestellt — es gilt der
  Standardsatz." — **keine** Aufzählung der sieben Standard-Größen.
- **Input C:** Eine Tour hat `display_config.metrics` mit Einträgen, aber
  alle `enabled: false` (Nutzer hat bewusst alles abgewählt).
- **Output C:** Der Block zeigt „Keine Wettergrößen ausgewählt — das
  Briefing enthält keine Wettertabelle." — unterscheidbar von Output B.
- **Input D:** Der Katalog-Fetch in `+page.server.ts` schlägt fehl (Netz,
  5xx).
- **Output D:** Die Seite lädt trotzdem vollständig (Trip, alle anderen
  Blöcke); der neue Block zeigt „Wetter-Metriken konnten nicht geladen
  werden." statt eines der drei Zustände.
- **Side effects:** Keine. Rein lesende Ableitung, ein zusätzlicher
  paralleler `GET`-Request pro Seitenaufruf, keine Persistenz-Änderung,
  kein Backend-, Go- oder Mail-Renderer-Eingriff (Renderer-Mail-Gate #811
  nicht betroffen).

## Acceptance Criteria

- **AC-1:** Given eine Tour hat im Wetter-Metriken-Tab mehrere Größen
  aktiviert / When der Nutzer den Reiter „Übersicht" öffnet / Then zeigt
  der neue Block die deutschen Namen genau der aktivierten Größen, in der
  Reihenfolge des zentralen Registers — nicht in der Reihenfolge, in der
  sie in `display_config.metrics` gespeichert sind.
  - Test: `resolveTripMetricsOverviewState()` gegen ein realistisches
    `MetricCatalog`-Fixture mit `metrics`-Eingabe in umgekehrter
    Register-Reihenfolge → Ergebnis `{kind:'selected', names:[...]}` in
    Register-Reihenfolge.

- **AC-2:** Given eine Tour hat `display_config.metrics` nicht gesetzt oder
  als leeres Array / When der Reiter „Übersicht" geöffnet wird / Then zeigt
  der Block den Satz „Noch nicht eingestellt — es gilt der Standardsatz."
  — ohne die sieben Standard-Größen namentlich aufzuzählen.
  - Test: `resolveTripMetricsOverviewState(undefined, catalog)` UND
    `resolveTripMetricsOverviewState([], catalog)` liefern beide
    `{kind:'altbestand'}`; struktureller Nachweis, dass der zugehörige
    Template-Zweig (Testid `hub-metrics-altbestand`) keine `names`-Liste
    rendert.

- **AC-3:** Given eine Tour hat `display_config.metrics` mit Einträgen, bei
  denen alle `enabled: false` sind (bewusste Leerauswahl) / When der
  Reiter „Übersicht" geöffnet wird / Then zeigt der Block den Satz „Keine
  Wettergrößen ausgewählt — das Briefing enthält keine Wettertabelle." —
  unterscheidbar vom Altbestand-Text aus AC-2 durch eigenen Wortlaut und
  eigenes Testid.
  - Test: Fixture mit `metrics: [{metric_id:'temperature',enabled:false},
    {metric_id:'wind',enabled:false}]` → `{kind:'empty'}`; struktureller
    Nachweis, dass in diesem Fall ausschließlich der Testid
    `hub-metrics-empty` rendert, nicht `hub-metrics-altbestand`.

- **AC-4:** Given der Katalog-Fetch (`GET /api/metrics`) in `+page.server.ts`
  schlägt fehl (Netzwerkfehler oder Nicht-200) / When die Trip-Detailseite
  geladen wird / Then liefert `load()` trotzdem Trip und ETag unverändert
  aus (keine 500-Seite), `metricsCatalog` ist `null`, und der neue Block
  zeigt den Fallback-Hinweis statt einem der drei Zustände.
  - Test (doc-compliance, Vorbild `pageServerEtagPassthrough.test.ts` —
    `+page.server.ts` importiert `$env/dynamic/private` und ist unter
    `node --test` nicht ausführbar): Quelltext-Nachweis, dass der
    Katalog-Fetch ein `.catch(() => null)` trägt und der Trip-Fehlerzweig
    (`throw error(...)`) davon unberührt bleibt; ergänzend ein
    struktureller Nachweis in `HubOverview.svelte`, dass `!metricsCatalog`
    als eigener, erster Zweig vor den drei Zustands-Zweigen geprüft wird.

- **AC-5:** Given eine Tour mit aktiven Wetter-Metriken / When die
  Übersichtsseite zum ersten Mal rendert (SSR + Hydration) / Then zeigt der
  Block zu keinem Zeitpunkt fälschlich „Noch nicht eingestellt", obwohl
  tatsächlich eine Auswahl existiert — kein Ladefenster wie in
  Fehlerklasse #1320 (E1a-2, Befund F001).
  - Test: struktureller Nachweis, dass `HubOverview.svelte` `metricsCatalog`
    ausschließlich als Prop liest (kein eigener `api.get('/api/metrics')`-
    Aufruf, kein `$effect`, das den Katalog nachlädt) — der Katalog ist
    beim ersten Rendern bereits vollständig geladen, weil `+page.server.ts`
    ihn vor dem Return awaitet (Teil desselben doc-compliance-Tests wie
    AC-4).

- **AC-6:** Given der Programmcode nach Auslieferung dieser Etappe / When
  man nach den vier im Ticket ursprünglich als „fehlerhaft" benannten
  Bauteilen (`MetricsPreview.svelte`, `WeatherMetricsPreviewCard.svelte`,
  `WeatherMetricsPreviewCard.tokens.test.ts`, `TripOverview.svelte`) und
  dem toten E2E-Test sucht / Then existieren diese Dateien nicht mehr, und
  `trip-detail/index.ts` enthält keinen Export mehr, der auf sie verweist.
  - Test: struktureller Nachweis (Datei-Existenz-Prüfung über die fünf
    Pfade) + Scan von `trip-detail/index.ts` auf verbleibende Import-/
    Export-Referenzen dieser Namen.

- **AC-7:** Given `frontend/src/lib/utils/rightColumn.ts` nach dieser
  Etappe / When man nach `METRIC_LABELS`, `prettyLabel`,
  `getDefaultMetricsForProfile` oder `getActiveMetrics` sucht / Then
  existieren diese vier Symbole nicht mehr, während `getReportSchedule`
  und der Typ `ReportSchedule` unverändert exportiert werden und ihre
  bestehenden Tests weiterhin grün sind.
  - Test: struktureller Nachweis, dass `rightColumn.ts` keinen dieser vier
    Bezeichner mehr exportiert bzw. deklariert; ergänzend Regressionslauf
    der verbliebenen `getReportSchedule`/`getActivePreset`/`getPresetLabel`-
    Tests in `rightColumn.test.ts`.

- **AC-8:** Given der neue geteilte Baustein `tripActiveMetricNames.ts` /
  When man nach einer lokal deklarierten Metrik-ID→Name-Tabelle oder einer
  hartkodierten Standard-Metrik-Liste in dieser Datei sucht / Then existiert
  keine — jeder Name kommt ausschließlich aus dem übergebenen
  `catalog`-Parameter, keine neue, redaktionell gepflegte Zweitquelle
  entsteht (Ratsche gegen Nachwachsen, #1435).
  - Test: Syntaxbaum-Nachweis (Vorbild `alarme_tab_shared_labels.test.ts`)
    — keine lokale `Record<string,string>`-artige Konstante mit
    Metrik-ID-Schlüsseln, kein Import/Re-Export von `DEFAULT_TRIP_METRIC_IDS`.

- **AC-9:** Given der Übersichts-Reiter des Ortsvergleichs (`CompareTabs.svelte`,
  `activeTab === 'uebersicht'`) / When diese Etappe ausgeliefert ist / Then
  zeigt er weiterhin **keinen** Wetter-Metriken-Block — kein Compare-
  Pendant entsteht in dieser Etappe — während die neue Namensauflösungs-
  Funktion trotzdem unter `frontend/src/lib/components/shared/` liegt,
  nicht unter `trip-detail/` (Teilungs-Invariante, CLAUDE.md).
  - Test: struktureller Nachweis, dass `tripActiveMetricNames.ts` unter dem
    `shared/`-Pfad liegt, UND dass `CompareTabs.svelte`s
    `uebersicht`-Zweig keinen neuen Import dieser Datei enthält (kein
    stillschweigendes Compare-Pendant, Anti-Pattern-Referenz #1170).

- **AC-10:** Given ein Nutzer sieht den neuen Block in irgendeinem seiner
  vier möglichen Anzeige-Zustände (Auswahl, Altbestand, Leerauswahl,
  Katalog-Fehler) / When er auf den Sprung-Link klickt / Then wechselt die
  Ansicht in den Reiter „Wetter-Metriken" — über denselben Mechanismus wie
  die vier bestehenden Blöcke (`onJump` → `handleValueChange('weather')`),
  kein eigener Navigationsweg.
  - Test: struktureller Nachweis, dass der Sprung-Button im neuen Block
    `makeJumpHandler('weather')` aufruft — dieselbe Funktion, die die
    bestehenden vier Karten bereits für ihre jeweiligen Ziel-Tabs nutzen.

- **AC-11:** Given eine Tour hat eine Größe gespeichert, die das zentrale
  Register nicht (mehr) kennt — etwa nach einer Umbenennung / When der
  Reiter „Übersicht" geöffnet wird / Then verschwindet diese Größe **nicht
  still**: der Block zeigt die bekannten Namen und weist die unbekannten
  gesondert aus („… · 1 Größe unbekannt"), ohne die rohe englische Kennung
  als Namen auszugeben.
  - Begründung: „still verschwindende Größe" ist die Fehlerklasse, gegen die
    #1435 insgesamt antritt (Ticket-Text, Befund 3: „jede Übersetzung ist
    eine Stelle, an der eine Größe still verschwinden kann"). Ein Block, der
    unbekannte Kennungen wortlos wegfiltert, wäre eine neue solche Stelle.
    Die rohe Kennung anzuzeigen wäre dagegen der Rückfall in genau den
    Zustand, den das Ticket ursprünglich beklagte.
  - Test: Fixture mit `metrics: [{metric_id:'temperature',enabled:true},
    {metric_id:'soil_temp',enabled:true}]` gegen einen Katalog ohne
    `soil_temp` → Ergebnis führt `names:['Temperatur']` **und** einen
    Zähler/Feld für die unbekannten Kennungen; Gegenprobe, dass die rohe
    Kennung `soil_temp` in keiner Namensliste auftaucht.

- **AC-12:** Given ein Nutzer öffnet den Reiter „Übersicht" auf einem
  Mobilgerät (390×844) / When der neue Block in einem seiner Zustände
  angezeigt wird / Then ist er dort tatsächlich sichtbar und lesbar — die
  Namensliste bricht um, statt die Kachel zu sprengen oder abgeschnitten zu
  werden.
  - Begründung: #1446 — die Empfindlichkeits-Tabelle ist am Handy
    unsichtbar (`display:none` auf `<table>` blendet auch den Rumpf aus) und
    das entging **allen** Prüfungen, weil eine DOM-Abfrage sie als
    „sichtbar" meldete. Nur der Screenshot zeigte es.
  - Test: Nachweis in der Staging-Verifikation per Screenshot bei 390×844 —
    ausdrücklich **nicht** über eine Sichtbarkeits-Abfrage im DOM. Zusätzlich
    struktureller Nachweis, dass der Block keine viewport-abhängige
    `display`-Regel auf einem Container erhält, der seine Kinder mit
    ausblendet.

## Known Limitations

- **E3b (SMS-Kürzel `SD`/`SL`) folgt separat.** Die PO-Festlegung vom
  2026-06-30 (Schutz der Briefing-SMS-Token-Grammatik) ist für E3b
  ausdrücklich aufgehoben, bleibt aber für E3a unberührt — diese Etappe
  fasst `sms_trip.py`, `trip_report.py`, `tokens/builder.py`, `tokens/render.py`
  und `adapters/trip_result.py` nicht an.
- **Der Übersichts-Reiter des Ortsvergleichs bekommt in dieser Etappe
  keinen entsprechenden Block.** `CompareTabs.svelte:1081ff` listet die
  gewählten Größen schon heute nicht — es gibt also kein Gegenstück, das
  diese Etappe verletzen könnte. Die Namensauflösungs-Funktion liegt
  trotzdem unter `shared/`, damit ein späteres Compare-Pendant sie ohne
  Verschiebung wiederverwenden kann (s. AC-9).
- **Die Drei-Zustands-Bedingung ist eine schmale, bewusste Frontend-
  Kopplung an die Backend-Semantik.** `resolveTripMetricsOverviewState()`
  spiegelt exakt `trip_report.py:119`s `len(dc.metrics) == 0`-Bedingung —
  **nicht** die `DEFAULT_TRIP_METRIC_IDS`-Liste selbst (die bleibt reine
  Backend-Kenntnis, der Block zählt sie nie auf). Ändert sich künftig die
  Fallback-**Bedingung** in `resolve_trip_active_metrics()` (z. B. ein
  vierter Zustand), muss diese eine Zeile im Frontend von Hand nachgezogen
  werden. Das ist ein realer, aber schmaler Restwert-Kopplungspunkt — kein
  neues Namensvokabular im Sinne von #1435.
- **Kein Retry-Mechanismus für den fehlgeschlagenen Katalog-Fetch.** Zustand
  D (Katalog-Fehler) bietet keinen eigenen Wiederholen-Button — der Nutzer
  kann die Seite neu laden oder direkt in den Reiter „Wetter-Metriken"
  wechseln, der einen eigenen, unabhängigen Ladepfad mit Retry hat
  (`WeatherMetricsTab.svelte`). Ein eigener Retry-Mechanismus für den
  Übersichts-Block ist bewusst nicht Teil dieser Etappe (geringer Nutzen
  für einen reinen Anzeige-Block).
- **Harte Auflage #1435 eingehalten:** kein Python-, kein Go-Code wird
  angefasst. E3a ist reine Frontend-Arbeit (neuer Block + Aufräumen toten
  Codes).
- **Renderer-Mail-Gate (#811) nicht betroffen:** keine Datei dieser Etappe
  liegt unter `src/output/renderers/email/*.py` o. ä.
- **AC-8-Wächter fängt versehentliches Nachwachsen, nicht absichtliche
  Umgehung (Fix-Loop 2, F004).** Die strukturelle Ratsche in
  `tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts` erkennt
  eine neue lokale Metrik-ID→Name-Tabelle in mehreren Formen — direkte
  `Record<string,string>`-Konstante, String-Array mit bekannten Kennungen,
  `Map`/`Object.fromEntries`/Tupel-Array, Objekt-Literal ohne Typannotation
  — sowohl im Baustein selbst als auch in jeder Nachbardatei, die er per
  relativem `./…`-Import aus demselben Verzeichnis einbindet (eine Ebene
  tief, keine Rekursion). Die Kennungs-Menge dafür leitet der Wächter aus
  dem Register selbst ab (`src/app/metric_catalog.py`, `id="…"`-Werte),
  statt sie handzupflegen — eine handgepflegte Liste im Wächter gegen
  handgepflegte Listen im Produktcode wäre derselbe Widerspruch, den #1435
  abstellen soll. Bewusst **nicht** erkannt werden zwei Muster, die eine
  **absichtliche** Umgehung voraussetzen und keinen Unfall: (1) ein
  Objekt-Literal mit **berechneten Schlüsseln**
  (`{ [ID_TEMP]: 'Temperatur', ... }` — die Kennung steht dann nicht mehr
  als String-Literal im Syntaxbaum) und (2) ein **Tabellenaufbau in einer
  Schleife** aus zwei parallelen Arrays (Kennungen und Namen getrennt
  deklariert, erst zur Laufzeit zusammengeführt). Ein Wächter, der beliebig
  konstruierte Umwege gegen einen entschlossenen Umgeher fangen soll, wird
  beliebig teuer (Regel-Budget, CLAUDE.md) — sein Zweck ist, dass ein
  normales Aufräum-Refactoring (z.B. "Namen in eine eigene Datei
  auslagern") nicht versehentlich wieder eine Zweitquelle erzeugt, nicht
  eine für den Zweck errichtete Mauer gegen Vorsatz.

## Bewusst nicht Teil dieser Etappe

- **SMS-Kürzel-Vereinheitlichung (E3b)** — eigene, spätere Etappe mit
  eigener PO-Freigabe der ADR-Konsequenz.
- **Wetter-Metriken-Block im Ortsvergleichs-Übersichts-Reiter** — es gibt
  dort heute keinen entsprechenden Block und damit keine Regressionsgefahr;
  ein Compare-Pendant wäre eine eigene, noch nicht angeforderte Etappe.
- **Retry-Mechanismus für den Katalog-Fehlerfall im Übersichts-Block.**

## Test Plan

Kern-Schicht (deterministisch, ohne Netz), `node --import
./test-lib-loader.mjs --experimental-strip-types --test <datei>`.

| Testdatei (neu) | Belegt | Stil |
|---|---|---|
| `frontend/src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNames.test.ts` | AC-1, AC-2, AC-3 | Fixture-basiert, reine Funktion `resolveTripMetricsOverviewState()` gegen ein realistisches `MetricCatalog`-Fixture (Struktur wie die echte `/api/metrics`-Antwort) |
| `frontend/src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNames_noHardcodedVocabulary_structure.test.ts` | AC-8 | Svelte-/TS-Syntaxbaum-Prüfung, Vorbild `alarme_tab_shared_labels.test.ts` |
| `frontend/src/lib/components/trip-detail/__tests__/hubOverviewMetricsBlock_structure.test.ts` | AC-4 (Frontend-Teil), AC-5 (Frontend-Teil), AC-9, AC-10 | Svelte-Compiler-AST (`svelte/compiler` `parse`), inspiziert die vier sich ausschließenden Zweige, Testids, Prop-Nutzung statt Client-Fetch, Sprung-Link-Aufruf |
| `frontend/src/lib/components/trip-detail/__tests__/deadTripOverviewComponentsRemoved.test.ts` | AC-6, AC-7 | Datei-Existenz-Prüfung (fünf gelöschte Pfade) + Export-/Import-Scan (`index.ts`, `rightColumn.ts`) |
| `frontend/src/routes/trips/[id]/__tests__/pageServerMetricsCatalogFailSoft.test.ts` | AC-4 (Loader-Teil), AC-5 (Loader-Teil) | doc-compliance (Quelltext-Regex), Vorbild `pageServerEtagPassthrough.test.ts` — `+page.server.ts` importiert `$env/dynamic/private` und ist unter `node --test` nicht direkt ausführbar |
| `frontend/src/lib/components/shared/trip-metrics/__tests__/tripActiveMetricNamesUnknownId.test.ts` | AC-11 | Fixture-basiert: gespeicherte Kennung fehlt im Katalog → bekannte Namen bleiben, unbekannte werden gesondert ausgewiesen; Gegenprobe, dass die rohe Kennung in keiner Namensliste steht |
| `frontend/src/lib/components/trip-detail/__tests__/hubOverviewMetricsBlock_structure.test.ts` (erweitert) | AC-12 (struktureller Teil) | Nachweis, dass der Block keine viewport-abhängige `display`-Regel auf einem Container trägt, der seine Kinder mit ausblendet (Fehlerklasse #1446) |

**AC-12, sichtbarer Teil — nicht durch einen Kern-Test abnehmbar.** Der Nachweis
erfolgt in der Staging-Verifikation (Phase 7) als **Screenshot bei 390×844** in
allen vier Zuständen. Ausdrücklich **keine** DOM-Sichtbarkeitsabfrage: bei #1446
meldete genau diese Abfrage „sichtbar", während der Nutzer nichts sah. Ohne
Screenshot-Beleg gilt AC-12 als nicht erfüllt.

Bestehende Tests, die unverändert grün bleiben müssen: `rightColumn.test.ts`
(gekürzt um die vier entfernten Funktionsblöcke, `getReportSchedule`/
`getActivePreset`/`getPresetLabel`-Tests bleiben unangetastet),
`TripHeader.mobile-metrics.test.ts`, `TripHeader.spacing.test.ts` (beide
lesen `getReportSchedule`, nicht die entfernten Symbole). Alle neuen
Testdateien lösen ihren Prüfling relativ zu `import.meta.url` auf
(Pfadregel #1409), kein fester Hauptrepo-Pfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt das in E1a-1/E1a-2/E1b bereits etablierte Prinzip
  „eine zentrale Registerquelle statt redaktionell gepflegter Vokabulare"
  auf einen weiteren Frontend-Konsumenten fort und entfernt zusätzlich vier
  bereits tote Vokabulare — keine neue Grundsatzentscheidung im Sinne der
  CLAUDE.md-ADR-Trigger (Kanäle, Provider, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie unberührt).

## Changelog

- 2026-08-01: Initial spec created (Feature #1435 Etappe E3a, Teilung von
  E3 laut PO-Entscheidung 2026-08-01, s. `docs/context/fix-1435-e3-namensfehler.md`).
  Belegstellen gegen den aktuellen Code verifiziert (`HubOverview.svelte`,
  `TripTabs.svelte`, `+page.server.ts`, `trip-detail/index.ts`,
  `rightColumn.ts`, `trip_metric_ids.py`, `metricsEditor.ts::selectTableColumns`,
  `metric_catalog.py`, `alarme_tab_shared_labels.test.ts`,
  `pageServerEtagPassthrough.test.ts`), nicht aus dem Kontextdokument
  übernommen.
