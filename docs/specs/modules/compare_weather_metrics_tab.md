---
entity_id: compare_weather_metrics_tab
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [compare, trip, shared, metrics, tab, corridor]
---

<!-- Issue #1311 — Scheibe C1 von Epic #1301 -->

# Geteilter Wetter-Metriken-Tab (C1 — Compare bekommt Metrik-Auswahl)

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich hat heute keine eigene Fläche, um Wetter-Metriken für die
Vergleichs-Mail an- oder abzuwählen — `display_config.active_metrics` wird
bislang nur indirekt über das Alarm-Häkchen (`notify`) der Wertebereiche
abgeleitet (eine Attrappen-nahe Kopplung: „Alarm an" und „in der Mail zeigen"
sind zwei verschiedene Nutzer-Absichten, die zufällig dasselbe Feld
beschreiben). C1 führt einen neuen Tab **„Wetter-Metriken"** ein, der die
bestehende, 1027-zeilige Trip-Komponente `WeatherMetricsTab.svelte` nach
`shared/` überführt (Vorbild `AlarmeTab.svelte`: `context="route"|"vergleich"`)
und im Vergleichs-Kontext ausschließlich das an/aus-Steuerelement zeigt, das
tatsächlich Mail-Wirkung hat. Als Nebeneffekt löst C1 Issue #1293 an der
Wurzel: Der Trip-Wertebereiche-Pool bezieht seine sechs korridorfähigen
Metriken künftig aus der Auswahl dieses Tabs statt aus einer fest
verdrahteten 6er-Liste.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  (1027 Zeilen, Stand vor C1) → verschoben + erweitert nach
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `WeatherMetricsTab.svelte` (`Props`, `buildWeatherPayload()`,
  `handleSave()`, `scheduleAutoSave()`), `compareTabsResolve.ts` (`COMPARE_TABS`),
  `corridorEditorState.ts` (`buildRoutePool`, `buildCompareCorridorSavePayload`),
  `alertMetricTable.ts` (`CATALOG_TO_ALERT_METRICS`)

## Estimated Scope

- **LoC:** Zwei getrennt zu betrachtende Zahlen (PO-Vorgabe: ehrlich beziffern):
  - **Reine Verschiebung** von `trip-detail/WeatherMetricsTab.svelte` nach
    `shared/WeatherMetricsTab.svelte`: ~1027 Zeilen, inhaltlich für
    `context="route"` unverändert (Regressionsschutz, AC-6). Zählt nach
    Projektkonvention nicht als Diff-LoC, **sofern** git die Verschiebung als
    Rename erkennt (`git mv`, keine Parallel-Reformatierung im selben Commit).
  - **Echte Verhaltensänderung** (zählt gegen das 250-LoC-Budget):
    ~350-450 Zeilen — Props-/Sections-Erweiterung um `context` in der
    verschobenen Komponente (~80-120 Z., Vorbild `AlarmeTab.svelte:42-92` +
    neue `weatherMetricsTabSections.ts`, Vorbild `alarmeTabSections.ts`,
    ~30 Z.), Tab-Registrierung (`compareTabsResolve.ts` +1 Eintrag,
    `CompareTabs.svelte` neues Tab-Panel + Hydrate/Flush-Wiring analog
    Idealwerte-Tab, ~60-90 Z.), Entkopplung `notify`↔`active_metrics`
    (`corridorEditorState.ts`, ~15-25 Z. Diff), `buildRoutePool`-Erweiterung
    um Metrik-Filter + neue Mapping-Konstante (~40-60 Z.), zwei Call-Site-
    Anpassungen (`CorridorEditor.svelte`/`CorridorEditorMobile.svelte`,
    ~4 Z.), Test-Anpassungen/-Ergänzungen (~120-160 Z. über 3-4 Testdateien).
  - **Konsequenz:** Selbst nur mit der „echten" Zahl wird das 250-LoC-Budget
    voraussichtlich gerissen. Der Developer-Agent muss **vor** Implementierung
    einen `loc_limit_override` beim PO einholen (kein Selbst-Override, s.
    CLAUDE.md) — grober Zielwert 500.
- **Files:** ~11 (7-8 Quelldateien, 3-4 Testdateien), zzgl. `api_contract.md`
  (dokumentativ, nicht LoC-relevant)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:57-67` | intern | Bestehende Props (`trip`, `createMode?`, `onChannelsChange?`, `onTripUpdate?`, `saveController?`) — wird um `context: 'route'\|'vergleich' = 'route'` + vergleich-Felder (`preset`/`wiz`, analog `AlarmeTab.svelte:42-51`) ergänzt |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:428-501` | intern | `buildWeatherPayload()`/`handleSave()`/`scheduleAutoSave()` — Zwei-PUT-Trip-Save (`weather-config` + Trip-PUT) bleibt `context="route"`-exklusiv; `context="vergleich"` bekommt einen eigenen, deutlich schlankeren Save-Zweig (nur `active_metrics`) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:42-51,87-92` | intern | Teilungs-Vorbild: `context`-Prop-Dispatch, Props-Split route/vergleich, Abschnittsreihenfolge aus einer reinen Funktion statt Markup-Duplikat |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:1-35` | intern | Vorbild für neue `weatherMetricsTabSections.ts` — reine Funktion `weatherMetricsTabSections(context)`, die entscheidet, welche Abschnitte (Grundauswahl/Reihenfolge/friendly/Horizonte/SMS-Schwellen/Report-Config) je Kontext sichtbar sind |
| `frontend/src/lib/components/compare/compareTabsResolve.ts:7-17` | intern | `COMPARE_TABS`-Array — neuer Eintrag `{ value: 'wetter-metriken', label: 'Wetter-Metriken' }` zwischen `orte` und `idealwerte` |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1037,1109` | intern | Tab-Panel-Reihenfolge im Markup (`compare-detail-panel-orte` gefolgt von `compare-detail-panel-idealwerte`) — neues Panel `compare-detail-panel-wetter-metriken` dazwischen; Hydrate-on-first-open-Muster analog `idealwerteHydrated` (`:298-350`) |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts:27-36,59-64,95-133` | intern | `HubWizardFields`/`HubEdit`/`buildHubPutPayload` besitzen `activeMetricKeys` bereits als eigenständiges Feld — der neue Tab wird ein **zweiter** Leser/Schreiber von `wizardState.activeMetricKeys` (kein neues Feld nötig), analog `flushPendingVersandSave`-Muster für einen eigenen Flush-Helper `flushPendingWeatherMetricsSave` |
| `frontend/src/lib/components/compare/compareEditorSave.ts:96-102` | intern | `buildComparePresetSavePayload`: `edits.activeMetricKeys !== undefined` → `displayConfig.active_metrics` (RMW, `undefined` = unangetastet) — bereits vorhanden, KEINE Änderung nötig |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:387-434` | intern | `buildCompareCorridorSavePayload`: Zeilen 428-433 (`if (r.alarmCapable === false) continue; if (r.notify) activeSet.add(...) else activeSet.delete(...)`) leiten `active_metrics` heute aus `notify` ab — diese Ableitung entfällt; `metricAlertLevels`-Zeile (433, zweiter Teil) bleibt (Alarm-Funktion von `notify` unverändert) |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:29-36,66-85` | intern | `ROUTE_METRIC_DEFS` (6 Metriken) + `buildRoutePool(corridors)` — Signatur wird um einen optionalen zweiten Parameter (aktive Catalog-Metrik-IDs aus dem Wetter-Tab) erweitert; ohne Parameter bleibt Alt-Verhalten (alle 6) erhalten (Aufrufer-Migration s.u.) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:70` und `CorridorEditorMobile.svelte:72` | intern | Beide einzigen `buildRoutePool(...)`-Aufrufer — Umstellung auf `buildRoutePool(trip?.corridors ?? [], trip?.display_config?.metrics)` |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:280-326` | intern | `CATALOG_TO_ALERT_METRICS`/`activeAlertableMetrics()` — bestehendes Vorbild für „Catalog-Metrik-ID → Zielmetrik"-Mapping; **nicht direkt wiederverwendbar** für den Korridor-Pool, s. Known Limitations (Namensraum-Lücke `snow_line`) |
| `frontend/src/lib/types.ts:72-87,174-181` | intern | `AlertMetric`-Union (enthält `snow_line`) und `WeatherConfigMetric` (`metric_id`, `enabled`) — Eingabetyp für den neuen Pool-Filter |
| `src/app/metric_catalog.py:220-228,451` | intern | `get_all_metrics()` filtert `selectable=true` (Confidence #710 bleibt draußen) — EIN Katalog für beide Seiten, keine Änderung nötig |
| `docs/reference/api_contract.md:1320-1345,1379-1380` | Doku | `display_config.active_metrics`-Semantik (`Feld fehlt = Legacy-Fallback, alle alarmfähigen`) — Beschreibung um „wird jetzt vom Wetter-Metriken-Tab geschrieben, nicht mehr vom `notify`-Häkchen" zu ergänzen |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts:33-69` | Test | `buildRoutePool`-Bestandstests (6er-Pool, keine Filterung) — werden auf „mit/ohne Filter-Parameter" erweitert |

## Implementation Details

### 1. Context-Dispatch in der verschobenen Komponente

```svelte
<!-- frontend/src/lib/components/shared/WeatherMetricsTab.svelte -->
<script lang="ts">
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import { weatherMetricsTabSections, type WeatherMetricsContext } from './weather-metrics-tab/weatherMetricsTabSections.ts';

	interface Props {
		context?: WeatherMetricsContext; // 'route' | 'vergleich', Default 'route'
		// route (unveraendert)
		trip?: Trip;
		createMode?: boolean;
		onChannelsChange?: (c: ChannelConfig) => void;
		onTripUpdate?: (t: Trip) => void;
		saveController?: SaveStatus;
		// vergleich (neu)
		wiz?: CompareWizardState;
	}
	let { context = 'route', trip, createMode = false, onChannelsChange, onTripUpdate, saveController, wiz }: Props = $props();

	const sections = $derived(weatherMetricsTabSections(context));
	// sections.includes('grundauswahl') -> immer wahr (beide Kontexte)
	// sections.includes('reihenfolge'|'sms_schwellen'|'report_config') -> nur route
</script>
```

> **⚠️ Teilweise abgelöst am 2026-07-24 durch
> [`compare_metric_order.md`](compare_metric_order.md) (Issue #1359,
> Scheibe 1).** Der Abschnitt `'reihenfolge'` ist **nicht mehr**
> route-exklusiv — er ist seither in **beiden** Kontexten sichtbar, damit
> die Metrik-Reihenfolge im Ortsvergleich einstellbar ist. Der folgende
> Code-Ausschnitt und der Satz „nur die Grundauswahl" beschreiben den Stand
> **vor** dieser Änderung und sind nur noch historisch zu lesen. Alles
> Übrige in diesem Dokument (Katalogquelle, Persistenz, AC-4-Zusage „kein
> Schreiben ohne Nutzer-Geste") gilt unverändert weiter.

```typescript
// frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts
// Vorbild: shared/alarme-tab/alarmeTabSections.ts — reine Funktion, keine
// Duplikat-Reihenfolge im Markup.
// HISTORISCH (Stand vor #1359) — aktueller Stand: siehe compare_metric_order.md
export type WeatherMetricsContext = 'route' | 'vergleich';

const ROUTE_ONLY_SECTIONS = ['reihenfolge', 'sms_schwellen', 'report_config'] as const;

export function weatherMetricsTabSections(context: WeatherMetricsContext): string[] {
	const sections: string[] = ['grundauswahl'];
	if (context === 'route') sections.push(...ROUTE_ONLY_SECTIONS);
	return sections;
}
```

Im `context="vergleich"`-Zweig wurde **bis #1359 nur** die Grundauswahl
(Metrik an/aus) gerendert; seither zusätzlich der Reihenfolge-Abschnitt. **Katalogquelle im Vergleich-Kontext ist `COMPARE_METRIC_DEFS`**
(derselbe 15er-Pool wie im Idealwerte-Tab; 15 seit `pop_max_pct`/#1285) — NICHT der Trip-Katalog aus
`GET /api/metrics`: `display_config.active_metrics` lebt im
Compare-Namensraum (`temp_max_c`, `wind_max_kmh`, … — vgl.
`compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`), der mit den
Trip-Katalog-IDs (`temperature`, `gust`, …) nicht 1:1 mappbar ist; nur der
Compare-Namensraum erzeugt tatsächliche Mail-Wirkung (AC-2/AC-8). Eine
`CATEGORY_LABELS`/`CATEGORY_ORDER`-Gruppierung existiert in diesem
Namensraum nicht — die Grundauswahl rendert ungruppiert. (Präzisiert
2026-07-18 nach GREEN-Befund; ursprüngliche Formulierung nannte den
Trip-Katalog.) Keine
Buckets (primary/secondary/off-Feinsteuerung), kein `friendlyMap`, kein
`horizonsMap`, keine SMS-Schwellen (`ThresholdMetricRow`), kein
`EditReportConfigSection`. Diese Elemente hätten im Vergleich keine
Mail-Wirkung (`resolve_compare_render_options` liest nur an/aus) und wären
exakt die Attrappen-Klasse, die das Epic beseitigt.

### 2. Vergleich-Save-Zweig (schlank, kein Zwei-PUT-Muster)

```typescript
// frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
// Analog compareHubWizardBridge.ts::flushPendingVersandSave — Diff gegen
// einen "before"-Snapshot, kein Schreiben ohne echte Aenderung.
export function flushPendingWeatherMetricsSave(
	preset: ComparePreset,
	current: string[],  // wiz.activeMetricKeys nach Nutzer-Toggle
	before: string[] | null
): { url: string; body: ComparePreset } | null {
	const baseline = before ?? current;
	if (JSON.stringify([...current].sort()) === JSON.stringify([...baseline].sort())) return null;
	return buildHubPutPayload(preset, { activeMetricKeys: current });
}
```

Aufruf-Ort: analog dem bestehenden Hydrate-on-first-open + Flush-on-tab-switch/
window-pointerup-Muster in `CompareTabs.svelte` für den Idealwerte-Tab
(`:298-350`, `:411`) bzw. dem schlankeren Versand-Muster (`flushPendingVersandSave`)
— Checkbox-Toggles ohne Drag-Geste rechtfertigen die einfachere Variante.

### 3. Entkopplung `notify` ↔ `active_metrics`

```typescript
// corridorEditorState.ts::buildCompareCorridorSavePayload — Zeilen 428-433 VORHER:
//   if (r.alarmCapable === false) continue;
//   if (r.notify) activeSet.add(r.metric); else activeSet.delete(r.metric);
//   metricAlertLevels[r.metric] = deriveMetricAlertLevel(...);
// NACHHER: activeSet bleibt ungeruehrt von notify (reiner Pass-Through von
// original.activeMetricKeys, s. Zeile 403); nur metricAlertLevels wird weiter
// aus notify abgeleitet — notify behaelt seine Alarm-Funktion (AC-3).
for (const r of rows) {
	if (!r.mark) { delete idealRanges[r.metric]; }
	else if (r.kind === 'ordinal') { /* unveraendert */ }
	else { /* unveraendert */ }
	if (r.alarmCapable === false) continue;
	metricAlertLevels[r.metric] = deriveMetricAlertLevel(r.notify, r.metric, original.metricAlertLevels ?? {});
	// activeSet.add/delete ENTFERNT — active_metrics gehoert ab C1 exklusiv
	// dem Wetter-Metriken-Tab.
}
```

Der Rückgabetyp behält `activeMetricKeys` (Pass-Through von
`original.activeMetricKeys` minus `removedMetrics`-Bereinigung, Zeilen
408-413 bleiben unverändert) — `CorridorSnapshot.activeMetricKeys` zeigt damit
weiterhin einen konsistenten Wert, ändert ihn aber nicht mehr aus
Wertebereiche-Interaktionen heraus.

### 4. #1293-Wurzelfix: `buildRoutePool` folgt der Tab-Auswahl

```typescript
// corridorEditorState.ts — buildRoutePool erweitert um optionalen Filter.
// Namensraum-Bruecke: WeatherConfigMetric.metric_id (Python-Katalog-IDs, z.B.
// "gust","precipitation","temperature","thunder","snowfall_limit") ->
// ROUTE_METRIC_DEFS.metric (AlertMetric-Werte, z.B. "wind_gust").
// NICHT identisch mit alertMetricTable.ts::CATALOG_TO_ALERT_METRICS, weil
// dessen Ausgabe durch ALERTABLE_METRICS gefiltert wird (13 Delta-Alarm-
// Metriken) UND "snow_line" dort seit Issue #959 (Konsolidierung in
// freezing_level) nicht mehr enthalten ist — waehrend ROUTE_METRIC_DEFS
// "snow_line" als eigenstaendigen Korridor fuehrt (Schneefallgrenze-
// Wertebereich, KEIN Alarm-Kontext). Eine eigene, kleine Mapping-Konstante
// vermeidet, dass der Korridor "Schneefallgrenze" nach dem #1293-Fix nie
// mehr im Pool erscheinen kann (s. Known Limitations).
const ROUTE_CORRIDOR_CATALOG_IDS: Record<string, string[]> = {
	gust: ['wind_gust'],
	precipitation: ['precipitation_sum'],
	temperature: ['temperature_min', 'temperature_max'],
	thunder: ['thunder_level'],
	snowfall_limit: ['snow_line'],
};

export function buildRoutePool(
	corridors: Corridor[],
	activeCatalogMetrics?: WeatherConfigMetric[]
): { rows: CorridorRowState[]; poolLeft: RouteMetricDef[] } {
	const allowed = activeCatalogMetrics
		? new Set(
				activeCatalogMetrics
					.filter((m) => m.enabled)
					.flatMap((m) => ROUTE_CORRIDOR_CATALOG_IDS[m.metric_id] ?? [])
			)
		: null; // kein Filter-Parameter -> Alt-Verhalten (alle 6), s. u.
	// ... bestehende Schleife, poolLeft-Eintraege ausserhalb `allowed` werden
	// uebersprungen (weder rows noch poolLeft) statt wie bisher immer
	// angeboten; bereits als Corridor GESPEICHERTE Zeilen (rows) bleiben
	// sichtbar (Datenerhalt), auch wenn die Metrik inzwischen im Wetter-Tab
	// abgewaehlt wurde — s. AC-9.
}
```

`allowed === null` (kein zweiter Parameter) erhält das Alt-Verhalten für
etwaige weitere, hier nicht erfasste Aufrufer — die beiden bekannten
Aufrufer (`CorridorEditor.svelte:70`, `CorridorEditorMobile.svelte:72`)
werden auf `buildRoutePool(trip?.corridors ?? [], trip?.display_config?.metrics)`
umgestellt.

## Expected Behavior

- **Input:** Nutzer öffnet im Ortsvergleich-Editor den neuen Tab
  „Wetter-Metriken" und schaltet einzelne Metriken an/aus; im Trip-Editor
  öffnet der Nutzer denselben Tab (unverändertes Verhalten) und wählt
  Metriken für Buckets/Reihenfolge/Horizonte.
- **Output:** Compare — `display_config.active_metrics` wird über den
  bestehenden RMW-Pfad (`compareEditorSave.ts:96-102`) gespeichert; die
  nächste Vergleichs-Mail (Versand oder Vorschau) enthält genau die
  angewählten Metriken. Trip — Wertebereiche-Tab zeigt als Pool nur die
  korridorfähigen Metriken, die im Wetter-Metriken-Tab aktiv sind.
- **Side effects:** Das Alarm-Häkchen (`notify`) in den Wertebereichen
  (Trip UND Compare) verliert seinen bisherigen Nebeneffekt auf die
  Mail-Metrikauswahl im Compare-Fall, behält aber unverändert seine
  Alarm-Auslöse-Funktion (`metric_alert_levels`). Bestandspresets ohne
  jemals gespeicherte `active_metrics` zeigen weiterhin die Legacy-Semantik
  (alle alarmfähigen Metriken).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleichs-Preset im Editor / When der Nutzer den
  Tab „Wetter-Metriken" öffnet / Then zeigt der Tab die wählbaren
  Wetter-Metriken (ohne die Vorhersage-Verlässlichkeit „Confidence") mit
  einem An/Aus-Schalter je Metrik, ohne Buckets, Horizonte, Kurzform- oder
  SMS-Schwellen-Einstellungen.
  - Test: Tab öffnen, prüfen dass jede sichtbare Metrikzeile nur einen
    An/Aus-Schalter zeigt, „Confidence"/„Sicherheit" nirgends auftaucht und
    keine Buckets-/Reihenfolge-/Horizont-/SMS-Schwellen-Bedienelemente
    vorhanden sind.

- **AC-2:** Given eine im Wetter-Metriken-Tab abgewählte Metrik, die zuvor in
  der Mail erschien / When die Vergleichs-Mail (Versand oder Vorschau) erneut
  gerendert wird / Then fehlt diese Metrik in der Mail; eine dort neu
  angewählte, zuvor fehlende Metrik erscheint.
  - Test: Metrik im Tab abwählen, speichern, Vorschau/Versand auslösen und
    das gerenderte Ergebnis auf Abwesenheit prüfen; umgekehrt für eine
    zuvor abwesende, neu angewählte Metrik auf Anwesenheit prüfen (echte
    Mail-Wirkung, nicht nur das persistierte Feld).

- **AC-3:** Given eine Metrik mit aktiviertem Alarm-Häkchen („Warnen") in den
  Wertebereichen / When der Nutzer diese Metrik im Wetter-Metriken-Tab
  abwählt (aus der Mail nimmt) / Then bleibt das Alarm-Häkchen unverändert
  aktiv und der Δ-Wächter löst für diese Metrik weiterhin Alarme aus; die
  Metrikauswahl der Mail wird durch das Alarm-Häkchen selbst nicht mehr
  verändert.
  - Test: Alarm-Häkchen setzen, Metrik anschließend im neuen Tab abwählen,
    prüfen dass ein simulierter Schwellenwert-Überschritt weiterhin einen
    Alarm auslöst UND die Mail die Metrik nicht mehr zeigt.

- **AC-4:** Given ein Bestands-Preset ohne jemals gespeicherte
  Metrik-Auswahl / When die Vergleichs-Mail gerendert wird, ohne dass der
  Wetter-Metriken-Tab geöffnet wurde / Then zeigt die Mail unverändert alle
  alarmfähigen Metriken (Legacy-Verhalten); das bloße Öffnen des Tabs ohne
  eine Nutzer-Interaktion speichert nichts.
  - Test: Preset ohne `active_metrics`-Feld rendern und mit dem
    Vorher-Zustand vergleichen; Tab öffnen und ohne Klick verlassen, dann
    per Vergleich des Presets vor/nach Öffnen prüfen, dass kein PUT
    ausgelöst wurde.

- **AC-5:** Given eine Trip-Route mit einer bestimmten Auswahl im
  Wetter-Metriken-Tab / When der Nutzer den Wertebereiche-Tab öffnet / Then
  bietet dieser als hinzufügbaren Pool genau die korridorfähigen Metriken
  an, die im Wetter-Metriken-Tab aktiv sind — nicht mehr grundsätzlich alle
  sechs.
  - Test: Im Wetter-Metriken-Tab eine korridorfähige Metrik abwählen,
    Wertebereiche-Tab öffnen und prüfen, dass diese Metrik nicht mehr im
    „+ Metrik hinzufügen"-Pool erscheint; eine weiterhin aktive Metrik bleibt
    im Pool.

- **AC-6:** Given ein bestehender Trip mit Wetter-Metriken-Konfiguration /
  When der Wetter-Tab wie vor C1 bedient wird (Buckets, Reihenfolge,
  Horizonte, Kurzform, SMS-Schwellen, Report-Config-Checkboxen) / Then
  verhält sich der Tab in jeder Hinsicht identisch zum Stand vor C1
  (Regressionsschutz).
  - Test: Bestehende Trip-Testsuite für den Wetter-Tab unverändert grün;
    zusätzlich ein End-to-End-Durchlauf (Metrik in Bucket verschieben,
    speichern, Trip-Briefing prüfen) liefert dasselbe Ergebnis wie vor C1.

- **AC-7:** Given ein Ortsvergleichs-Preset mit einem dem Frontend
  unbekannten, aber persistierten Feld in `display_config` oder `corridors` /
  When eine beliebige Speicherung über den Wetter-Metriken-Tab, den
  Wertebereiche-Tab oder einen anderen Tab erfolgt / Then bleibt dieses
  unbekannte Feld im gespeicherten Preset unverändert erhalten.
  - Test: Preset mit einem künstlichen unbekannten Feld laden, eine Metrik im
    neuen Tab umschalten, speichern und das unbekannte Feld im
    Persistenz-Ergebnis auf Unverändertheit prüfen.

- **AC-8:** Given der Wetter-Metriken-Tab im Vergleichs-Kontext / When der
  Nutzer die verfügbaren Bedienelemente betrachtet / Then sind ausschließlich
  Elemente vorhanden, die eine nachweisbare Wirkung auf die Vergleichs-Mail
  oder deren Metrikauswahl haben — keine Attrappen ohne Konsequenz.
  - Test: Jedes im Vergleichs-Kontext sichtbare Bedienelement einer
    beobachtbaren Mail- oder Persistenz-Wirkung zuordnen; Elemente ohne
    zuordenbare Wirkung gelten als Verstoß.

- **AC-9:** Given ein Wertebereich (Korridor) mit gespeicherten Min/Max-Werten
  für eine Metrik, die anschließend im Wetter-Metriken-Tab abgewählt wird /
  When der Wertebereiche-Tab danach erneut geöffnet und gespeichert wird /
  Then bleibt der zuvor gespeicherte Korridor (Min/Max/Alarm-Stufe) erhalten,
  auch wenn die Metrik aktuell nicht mehr im „+ Metrik hinzufügen"-Pool
  auswählbar ist (kein stiller Datenverlust bei De-Selektion).
  - Test: Korridor mit Werten anlegen, zugehörige Metrik im Wetter-Metriken-
    Tab abwählen, Wertebereiche-Tab öffnen, speichern (ohne die Zeile aktiv
    zu entfernen) und die Persistenz auf unveränderten Korridor-Eintrag
    prüfen.

## Known Limitations

- **`hourly_metrics` (Stundenverlauf) bleibt unerreichbar:** C1 betrifft nur
  `display_config.active_metrics` (Übersichtstabelle). Der Stundenverlauf-
  Zugang ist Scheibe C2 (#1299/#1287) und bleibt bis dahin ausschließlich im
  Layout-Tab konfigurierbar.
- **Idealwerte-Pool (Compare) bleibt bei 15 Metriken (F004-Korrektur; 15 seit #1285):** `COMPARE_METRIC_DEFS`
  (`corridorEditorState.ts:238-254`) wird von C1 nicht angetastet — die
  Entkopplung betrifft nur, WER `active_metrics` schreibt, nicht welche
  Metriken im Idealwerte-Tab wählbar sind.
- **`snow_line`-Korridor-Mapping-Lücke (neu identifiziert, Adversary-Punkt):**
  `alertMetricTable.ts::CATALOG_TO_ALERT_METRICS`/`activeAlertableMetrics()`
  ist NICHT direkt für den #1293-Fix wiederverwendbar — dessen Ausgabe wird
  gegen `ALERTABLE_METRICS` (13 Delta-Alarm-Metriken) gefiltert, und
  `snow_line` fehlt dort seit der Konsolidierung in `freezing_level`
  (Issue #959), obwohl `ROUTE_METRIC_DEFS` „Schneefallgrenze" weiterhin als
  eigenständigen Korridor führt. Implementation Details Abschnitt 4 löst dies
  über eine separate, kleine Mapping-Konstante (`snowfall_limit` →
  `snow_line`), die ausschließlich `buildRoutePool` betrifft und
  `ALERTABLE_METRICS`/die Alerts-Tab-Delta-Alarme unberührt lässt. Ohne diese
  gezielte Ergänzung wäre der „Schneefallgrenze"-Korridor nach dem #1293-Fix
  dauerhaft nicht mehr auswählbar — Adversary MUSS dies verifizieren.
  - Die vier reinen Vergleichs-Metriken ohne Alarm-Anbindung
    (`snow_depth_cm`, `sunny_hours_h`, `cloud_avg_pct`, `uv_index_max`,
    `alarmCapable=false`) sind von C1 nicht betroffen — sie schrieben schon
    vor C1 nie `active_metrics` über `notify`.
- **`CompareEditor.svelte` (Legacy) bleibt unverändert** — die Route ist seit
  Scheibe S3 umgeleitet und wird mit F2 gelöscht; C1 baut ausschließlich im
  Hub (`CompareTabs.svelte`).
- **Epic #1230-Konvergenz (Scheiben 5-7) wird nicht vorweggenommen:**
  Persistenz bleibt `briefings/{id}.json` mit `kind="vergleich"`, kein
  Zugriff auf noch nicht gebaute #1230-Strukturen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0026 (vorläufig — `docs/adr/README.md` ist als Index
  aktuell veraltet, gepflegt bis 0022; der tatsächliche Dateibestand in
  `docs/adr/` reicht bereits bis 0025 und enthält zwei Nummern-Kollisionen
  (0018, 0025) aus parallelen Sessions. Die nächste freie Nummer ist beim
  tatsächlichen Anlegen des ADR-Dokuments — spätestens im Implementierungs-
  Commit, der den `adr_guard`-Gate-Dateien berührt — erneut zu prüfen.)
- **Rationale:** Zwei echte, schwer umkehrbare Architekturentscheidungen
  liegen vor: (1) Der 1027-zeilige `WeatherMetricsTab` wird geteilt statt für
  Compare dupliziert — Vorbild `AlarmeTab.svelte`, Fortführung der bereits in
  ADR-0021 (geteilte `DeviationAlertEngine`) etablierten Linie „ein
  Baustein, `context`-Dispatch" für Trip/Compare (CLAUDE.md
  Trip/Compare-Teilungs-Invariante). (2) `active_metrics` wird bewusst vom
  `notify`-Flag der Korridore entkoppelt — bislang implizit dieselbe
  Datenquelle für zwei unterschiedliche Nutzer-Absichten (Alarm vs.
  Mail-Inhalt), was strukturell zur Attrappen-Klasse führte, die Epic #1301
  beseitigt. Beide Entscheidungen betreffen dauerhaft mehrere Systemteile
  (Trip-Editor, Compare-Editor, Δ-Wächter, Compare-Renderpfad) und sind nicht
  lokal auf eine Datei begrenzt — damit ADR-pflichtig nach den Faustregeln in
  `docs/adr/README.md`.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1311, Scheibe C1 von Epic #1301
- 2026-07-18 (GREEN): Implementation Details präzisiert — Katalogquelle im
  Vergleich-Kontext ist `COMPARE_METRIC_DEFS` (Compare-Namensraum), nicht der
  Trip-Katalog `GET /api/metrics`; Begründung Namensraum-Inkompatibilität
  (nur so echte Mail-Wirkung, AC-2/AC-8). ACs unverändert.
