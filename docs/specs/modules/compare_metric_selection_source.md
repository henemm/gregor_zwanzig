---
entity_id: compare_metric_selection_source
type: feature
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [compare, metrics, frontend, ssot]
workflow: fix-1350-compare-metric-select
---

# Compare-Metrik-Auswahlliste: Quelle = Backend-Endpoint

## Approval

- [ ] Approved

## Purpose

Die Checkbox-Auswahlliste wählbarer Metriken im Ortsvergleich-Editor
(`WeatherMetricsTab.svelte`, `context='vergleich'`) bezieht ihre Einträge künftig
aus dem in Teil 1 gebauten Backend-Endpoint `GET /api/compare/metrics` statt aus
dem statischen Frontend-Import `COMPARE_METRIC_DEFS`. Das ist Teil 2 von Issue
#1350 (Strangler-Migration, siehe `compare_metric_catalog_endpoint.md`): eine
neue selektierbare Backend-Metrik erscheint danach ohne Frontend-Code-Änderung
auch im Vergleich. **Nur die Auswahlliste** — Schwellen-Slider/Pool/Winner-Box
(`COMPARE_METRIC_DEFS`, `compareMetricDefs.ts`) bleiben unverändert Teil 3.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `{#if context === 'vergleich'}`-Zweig (Z.701–726),
  `{#each COMPARE_METRIC_DEFS as def (def.metric)}`-Liste (Z.713–723),
  `toggleCompareMetric()` (Z.643–649)

> Schicht-Hinweis: reine Frontend-Arbeit (`frontend/src/...`, SvelteKit).
> Go-Proxy (`internal/router/router.go:155`) und Python-Endpoint
> (`api/routers/compare.py`) sind aus Teil 1 bereits live (Commit `a824a6cc`) —
> **nicht anfassen**.

## Estimated Scope

- **LoC:** ~120–170 (neuer Fetch-/Ladezustand im Vergleich-Zweig + Fehler-/
  Loading-Shells analog Route-Zweig, Typ-Definitionen, Tests). Deutlich unter
  dem 250-LoC-Workflow-Limit.
- **Files:** 3–4 (geändert: `WeatherMetricsTab.svelte`, `frontend/src/lib/types.ts`;
  ggf. neu: ein kleiner Test-File; `frontend/src/lib/api.ts` nur falls ein
  dedizierter Wrapper statt des generischen `api.get<T>()` gewählt wird — nicht
  zwingend, da `api.get` bereits pfad-generisch ist)
- **Effort:** low–medium (Fetch-Pattern ist im selben File für `context='route'`
  bereits vollständig vorhanden und wird 1:1 für den Vergleich-Zweig gespiegelt;
  Sorgfaltspflicht liegt im `key`→`metric`-Mapping und im Fehlerzustand)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/compare/metrics` (Teil 1, `a824a6cc`) | backend endpoint | Neue autoritative Quelle der Auswahlliste — liefert `{"metrics":[{key,label,unit,decimals,higherIsBetter,kind,…}]}`, 25 Einträge, Reihenfolge = heutige `ALL_METRICS`-Reihenfolge |
| `frontend/src/lib/api.ts::api.get<T>()` | frontend module | Bestehender generischer GET-Client (Z.29) — Vorbild/Nutzung für die neue Anbindung, kein neues Auth-/Fehlerhandling nötig (401-Redirect etc. bereits zentral) |
| `frontend/.../trip-detail/metricsEditor.ts::MetricCatalog` | frontend type | Vorbild-Musterstruktur für den Trip-Katalog-Typ — Compare bekommt einen eigenen, kleineren Typ (Feldnamen weichen ab: `key` statt Record-Struktur) |
| `frontend/.../shared/corridor-editor/corridorEditorState.ts::COMPARE_METRIC_DEFS` | frontend module | **Bleibt unverändert** (Schwellen-Slider/Pool/Winner-Box, Teil 3) — wird von der Auswahlliste nicht mehr referenziert, aber nicht entfernt |
| `frontend/.../weather-metrics-tab/weatherMetricsCompareSave.ts::hydrateWeatherMetricsFromPreset` | frontend module | Default-„alle Keys aktiv"-Fallback bleibt auf `COMPARE_METRIC_DEFS` (Z.25) — **nicht anfassen** |
| `CompareTabs.svelte` (Hub) / `TripNewEditor`-Analogon `/compare/new` | frontend module | Beide mounten `WeatherMetricsTab` im `context='vergleich'` — der neue Fetch muss in beiden Fällen laufen (`createMode` eingeschlossen) |

## Implementation Details

**1. Neuer Katalog-Typ (`frontend/src/lib/types.ts`):** ein schlankes Interface
für einen Endpoint-Eintrag, z.B. `CompareMetricCatalogEntry` mit mindestens
`key: string` und `label: string`; weitere Felder (`unit`, `decimals`,
`higherIsBetter`, `kind`, `rangeMin/rangeMax/step`, `enumValues`,
`ordinalLabels`) dürfen mitgeführt werden (für Teil 3), müssen in Teil 2 aber
nicht konsumiert werden. Response-Hülle: `{ metrics: CompareMetricCatalogEntry[] }`.

**2. Fetch im Vergleich-Zweig (`WeatherMetricsTab.svelte`):** neuer lokaler
State — analog `catalog`/`catalogLoaded`/`loadError` des Route-Zweigs (Z.310ff),
aber eigenständig benannt (z.B. `compareCatalog`, `compareCatalogLoaded`,
`compareCatalogError`), damit der bestehende Route-Fetch-Zustand unangetastet
bleibt. Eine neue Funktion `loadCompareMetricCatalog()` ruft
`api.get<{ metrics: CompareMetricCatalogEntry[] }>('/api/compare/metrics')` auf,
setzt bei Erfolg `compareCatalog` + `compareCatalogLoaded = true`, bei Fehler
`compareCatalogError` (Catch-Block analog `load()`, Z.328–330: `(e as
{error?:string})?.error ?? 'Fehler beim Laden der Metriken'`).

**3. Auslösung nur für den Vergleich-Kontext:** ein neuer `$effect`, der —
analog dem bestehenden Route-Guard (Z.343–346: `if (context === 'route' &&
Object.keys(catalog).length === 0) load();`) — bei `context === 'vergleich' &&
!compareCatalogLoaded && !compareCatalogError` genau einmal
`loadCompareMetricCatalog()` auslöst. Der Guard verhindert Doppel-Fetches bei
Re-Render und läuft unabhängig vom Route-`$effect` (Z.343). Kein
`scheduleAutoSave()`/PUT-Aufruf in diesem Pfad — reines Lesen (AC-5).

**4. Fehler-/Ladezustand analog Route-Zweig, aber INNERHALB des
`{#if context === 'vergleich'}`-Blocks** (der Block returnt heute komplett, bevor
der bestehende `{:else if loadError}`/`{:else if !catalogLoaded}` des
Route-Zweigs greift — die neuen Zustände brauchen daher eigene Verzweigungen
im Vergleich-Block selbst, nicht die bestehenden Route-Shells):
```
{#if context === 'vergleich'}
  {#if compareCatalogError}
    <!-- load-error-shell analog Z.727-732, eigener data-testid -->
    <Btn onclick={loadCompareMetricCatalog}>Wiederholen</Btn>
  {:else if !compareCatalogLoaded}
    <!-- loading-shell analog Z.734-736 -->
  {:else}
    <!-- bisheriger Card-Inhalt, Liste jetzt aus compareCatalog -->
  {/if}
{:else if loadError} ...
```
Kein still leerer Editor bei Endpoint-Ausfall (D2, AC-4).

**5. Listenquelle wechselt (Z.713):** `{#each COMPARE_METRIC_DEFS as def
(def.metric)}` wird zu `{#each compareCatalog as entry (entry.key)}`; im
Template wird `entry.key` überall dort verwendet, wo bisher `def.metric` stand
(`toggleCompareMetric(entry.key)`, `wiz?.activeMetricKeys.includes(entry.key)`,
`data-testid="weather-metrics-vergleich-row-{entry.key}"`), `entry.label` statt
`def.label`. `toggleCompareMetric()` selbst (Z.643–649) bleibt unverändert —
sie operiert bereits auf einem reinen `metric: string`-Parameter, unabhängig
von der Quelle.

**6. `createMode`/`/compare/new`:** kein Sonderfall nötig — der neue `$effect`
greift über `context === 'vergleich'` unabhängig davon, ob ein bestehender
Vergleich oder ein neuer angelegt wird (beide teilen dieselbe Komponenten-
Instanz).

**Explizit NICHT Teil dieser Spec:** `COMPARE_METRIC_DEFS`,
`corridorEditorState.ts`, `compareMetricDefs.ts::ALL_METRICS`,
`weatherMetricsCompareSave.ts`-Default-Fallback (Z.25), Schwellen-Slider,
Winner-Box, Persistenz-Format von `display_config.active_metrics` — alles
unverändert (Teil 3 / bestehendes Verhalten).

## Expected Behavior

- **Input:** Öffnen des Vergleich-Editors (Hub-Detail oder `/compare/new`) mit
  `context='vergleich'`.
- **Output:** Die Checkbox-Auswahlliste zeigt exakt die Metriken aus
  `GET /api/compare/metrics` in Endpoint-Reihenfolge mit deren `label`;
  Toggle-Verhalten und Persistenz (`display_config.active_metrics`) bleiben
  unverändert (Keys bit-identisch).
- **Side effects:** ein zusätzlicher `GET /api/compare/metrics`-Request beim
  ersten Öffnen des Vergleich-Zweigs (einmalig, kein PUT/Save-Nebeneffekt).

## Acceptance Criteria

- **AC-1:** Given der Vergleich-Editor wird geöffnet (Hub-Detail oder
  `/compare/new`) / When die Auswahlliste rendert / Then zeigt sie exakt die
  25 Metriken aus der echten `GET /api/compare/metrics`-Antwort in
  Endpoint-Reihenfolge mit den dort gelieferten Labels — nicht gegen die alte
  `COMPARE_METRIC_DEFS`-Konstante geprüft, sondern gegen die tatsächliche
  Endpoint-Antwort.
  - Test: Kern-Test rendert `WeatherMetricsTab` mit `context='vergleich'` gegen
    eine fixierte, aus dem echten Endpoint gezogene Fixture-Antwort und prüft
    Anzahl + Reihenfolge + Labels der gerenderten Zeilen (Component-Test, kein
    Dateiinhalt-Grep).

- **AC-2:** Given ein Backend-Katalog mit einem zusätzlichen (neuen)
  Metrik-Eintrag, der in `COMPARE_METRIC_DEFS` nicht existiert / When der
  Vergleich-Editor mit dieser erweiterten Fixture-Antwort geladen wird / Then
  erscheint der neue Eintrag in der Auswahlliste — ohne jede Frontend-Code-
  Änderung.
  - Test: Kern-Test mit einer um einen synthetischen Eintrag erweiterten
    Katalog-Fixture; Assertion, dass die gerenderte Liste den zusätzlichen
    Eintrag (Checkbox + Label) enthält.

- **AC-3:** Given ein Nutzer wählt im Vergleich-Editor eine Metrik an oder ab /
  When der Toggle ausgelöst wird / Then wird `display_config.active_metrics`
  weiterhin mit dem korrekten Key (z.B. `temp_max_c`) aktualisiert, genau ein
  Save pro Toggle-Klick, und ein bestehendes Preset lädt mit unveränderter
  Auswahl (Regressionsschutz für die bestehende Persistenz-Kette).
  - Test: bestehender bzw. neuer Kern-Test auf `toggleCompareMetric` +
    Save-Zähler (analog vorhandenem PUT-Count-Muster), kein manueller
    Dateiinhalt-Check.

- **AC-4:** Given `GET /api/compare/metrics` schlägt fehl (Netzwerkfehler oder
  Non-2xx) / When der Vergleich-Editor geöffnet wird / Then zeigt die
  Komponente einen sichtbaren Fehlerzustand mit „Wiederholen"-Button — keine
  still leere Auswahlliste, kein Schreibzugriff möglich, solange der Fehler
  ansteht.
  - Test: Kern-Test mockt einen fehlschlagenden `api.get`-Call für
    `/api/compare/metrics` und prüft, dass der Fehler-Shell-Testid sichtbar
    ist und die Metrik-Liste NICHT gerendert wird.

- **AC-5:** Given der Vergleich-Editor wird zum ersten Mal geöffnet / When der
  Katalog-Fetch abläuft und erfolgreich zurückkommt / Then löst allein das
  Laden KEINEN Speichervorgang aus (kein PUT an das Backend durch den
  Ladevorgang selbst, nur durch einen expliziten Nutzer-Toggle).
  - Test: Kern-Test zählt PUT-Aufrufe (Save) über den kompletten Ladezyklus
    (Mount → Fetch-Resolve) und erwartet `0`, bevor ein Toggle ausgelöst wird.

- **AC-6:** Given die Migration ist abgeschlossen / When `COMPARE_METRIC_DEFS`
  (`corridorEditorState.ts`) und `compareMetricDefs.ts::ALL_METRICS` inspiziert
  werden / Then existieren beide unverändert weiter und werden von anderen,
  nicht in dieser Spec geänderten Stellen (Schwellen-Editor, Winner-Box,
  `weatherMetricsCompareSave.ts`-Default-Fallback) weiterhin importiert — die
  Auswahlliste ist die einzige umgestellte Konsumentenstelle.
  - Test: bestehende Tests für Schwellen-Editor/Winner-Box/Save-Default-
    Fallback bleiben unverändert grün (Regressionsschutz, kein neuer Test
    nötig — Abwesenheit einer Regression durch unveränderten Testlauf belegt).

## Known Limitations

- Die Auswahlliste zeigt künftig ausschließlich Metriken, die der Endpoint
  liefert — fällt der Endpoint dauerhaft aus (nicht nur transient), bleibt der
  Vergleich-Editor an dieser Stelle unbedienbar (Fehlerzustand statt Fallback
  auf die alte Konstante). Das ist eine bewusste Entscheidung (D2): ein
  stiller Fallback auf `COMPARE_METRIC_DEFS` würde die Strangler-Migration
  unterlaufen und die SSoT-Eigenschaft (AC-2) wieder aufweichen.
  Fehlerkommunikation über sichtbaren Retry-Button mindert das Risiko.
  Persistenz und Rendering laufen unabhängig vom Katalog-Fetch weiter — nur
  die Auswahl-UI ist betroffen.
- `COMPARE_METRIC_DEFS`/`compareMetricDefs.ts` bleiben bis Teil 3 eine zweite,
  parallele Metrik-Quelle (Schwellen/Pool/Winner-Box) — die Doppelpflege
  besteht bis dahin fort, genau wie in Teil 1 dokumentiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Frontend-Konsum-Wechsel eines bereits bestehenden,
  additiven Read-Endpoints — keine neue Entscheidungsfläche (Kanäle,
  Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-
  Strategie) betroffen. Folgt der in Teil 1 bereits festgelegten
  SSoT-Migrationsrichtung (Epic #1230, Trip/Compare-Konvergenz) — keine neue
  Grundsatzentscheidung, nur deren nächster Schritt.

## Changelog

- 2026-07-23: Initial spec created (Teil 2 von 3, Issue #1350, Strangler-Migration)
