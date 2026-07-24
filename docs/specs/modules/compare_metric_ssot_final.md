---
entity_id: compare_metric_ssot_final
type: feature
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [compare, metrics, frontend, backend, ssot]
workflow: fix-1350-compare-metric-ssot-final
---

# Compare-Metrik-SSoT: Schwellen-Editor + Aufräumen (Teil 3 von 3)

## Approval

- [ ] Approved

## Purpose

Teil 3 (letzter Teil) von Issue #1350 schließt die Strangler-Migration ab: der
Schwellen-Editor des Ortsvergleichs (`COMPARE_METRIC_DEFS`, `corridorEditorState.ts`,
Pool + Zeilen in `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`) bezieht seine
Metrik-Definitionen aus `GET /api/compare/metrics` (Teil 1, live seit `a824a6cc`)
statt aus dem statischen Frontend-Import `compareMetricDefs.ts::ALL_METRICS`. Danach
fällt `compareMetricDefs.ts` **ersatzlos** — der Backend-Katalog ist die einzige
verbleibende Quelle für Label/Einheit/Wertebereich/`kind` der 25 Ortsvergleich-Metriken.
Zusätzlich räumt dieser Teil bestätigten Totcode auf (Winner-Box `CompareMatrix.svelte`/
`HourlyMatrix.svelte`) und zieht das Profil-Feature (`IDEAL_DEFAULTS` u.a.) in seinen
einzig verbleibenden natürlichen Ort (`corridorEditorState.ts`) um. Persistenz-Format
(`corridors[]`/`ideal_ranges`/`active_metrics`/`metric_alert_levels`) bleibt bitgleich —
Datenverlust-Klasse (CLAUDE.md „Daten-Schema-Reworks").

## Source

- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
  (Kern-Umbau), `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
  + `CorridorEditorMobile.svelte` (Async-Konsum), `src/output/renderers/compare_metric_catalog.py`
  (Backend-Anreicherung `alarmCapable`)
- **Identifier:** `COMPARE_METRIC_DEFS`/`CompareMetricDef`/`buildComparePool`/
  `addCompareRow`/`buildComparePrefillRows`/`buildCompareCorridorSavePayload`
  (`corridorEditorState.ts:219-483`), `COMPARE_METRIC_CATALOG`
  (`compare_metric_catalog.py:25-78`)

> Schicht-Hinweis: **Frontend** (`frontend/src/...`, SvelteKit) für die eigentliche
> Migration + Aufräumen; **EIN Backend-Touch** (Python-Core,
> `src/output/renderers/compare_metric_catalog.py` + dessen Test
> `tests/tdd/test_compare_metric_catalog_endpoint.py`) für das neue `alarmCapable`-Feld
> (D1, Hybrid). Kein Go-Touch (Proxy-Route existiert bereits seit Teil 1, unverändert).

## Estimated Scope

- **LoC:** **groß, >250 — LoC-Limit-Override erforderlich.** Realistische Bandbreite
  ~550–800 Netto-Zeilen (Diff, nicht nur Nettoadditionen), zusammengesetzt aus:
  - Backend: ~40–60 (25× `alarmCapable`-Feld + Testerweiterung + `api_contract.md`-Zeile)
  - Neues FE-Modul (Katalog-Fetch + Mapper, modul-weiter Cache): ~70–100
  - `corridorEditorState.ts`: Umzug Profil-Feature (D3) + Parametrisierung
    (`defs`-Argument statt Modul-Konstante) + Löschen `COMPARE_METRIC_DEFS`/
    `_COMPARE_ALARM_KEYS`: ~80–120 Netto (Verschiebung zählt beidseitig im Diff)
  - `CorridorEditor.svelte` + `CorridorEditorMobile.svelte`: Async-Ladezustand,
    `$effect`, Fehler-/Loading-Shells, `defs`-Durchreichen an alle Aufrufe: ~80–130
    je Datei (~160–260 zusammen)
  - Tote-Code-Löschung (D2, bestätigt): `CompareMatrix.svelte` (191 Zeilen),
    `HourlyMatrix.svelte` (98 Zeilen), `compare_matrix_dead_code.test.ts` (52 Zeilen),
    `compareMetricDefs.ts` (141 Zeilen) = **482 Zeilen Löschung**
  - Test-Chirurgie: `issue_462.test.ts` (2 Referenzen entfernen), 2 `describe`-Blöcke
    aus `compareEditorSlice3.test.ts` entfernen (~65 Zeilen), `issue_718_idealwert_validation.test.ts`
    komplett löschen (96 Zeilen, ausschließlich Tests der toten `validateIdealRanges`)
  - Neue Kern-Tests: Katalog→Def-Mapper-Parität, Save-Payload-Parität, Lade-/Fehlerzustand
- **Files:** ~17–19 (neu: 1 FE-Loader-Modul; geändert: `corridor_metric_catalog.py`,
  dessen Test, `api_contract.md`, `corridorEditorState.ts`, `corridorEditorState.test.ts`,
  `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `compareHubWizardBridge.ts`,
  `compareWizardState.svelte.ts`, `compareEditorSave.ts`, `CompareNewEditor.svelte`,
  `issue_462.test.ts`, `compareEditorSlice3.test.ts`; gelöscht: `compareMetricDefs.ts`,
  `CompareMatrix.svelte`, `HourlyMatrix.svelte`, `compare_matrix_dead_code.test.ts`,
  `issue_718_idealwert_validation.test.ts`)
- **Effort:** high — nicht wegen Komplexität pro Datei, sondern wegen der Zahl der
  betroffenen Stellen und weil ein bisher **synchroner** Modul-Konstante-Konsum
  (`COMPARE_METRIC_DEFS` wird heute beim Komponenten-Mount SOFORT gelesen) zu einem
  **asynchronen** Ladepfad wird — das größte Einzelrisiko dieses Teils (s.
  Implementation Details Punkt 5).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/compare/metrics` (Teil 1, `a824a6cc`) | backend endpoint | Neue autoritative Quelle für Label/Unit/`kind`/Wertebereich/Ordinal-Labels — bereits live, wird um `alarmCapable` erweitert (D1) |
| `frontend/.../weather-metrics-tab/compareMetricSelection.ts::toCompareSelectionEntries` (Teil 2) | frontend module | Vorbild-Mapper (Endpoint-Antwort → schlanke FE-Form) — Teil 3 baut einen analogen, aber vollständigeren Mapper (`CompareMetricDef` statt nur `{metric,label}`) |
| `frontend/.../shared/WeatherMetricsTab.svelte` (Teil 2, eigener Fetch/Cache) | frontend module | **Bleibt funktional unverändert** — optionale interne Umstellung auf den neuen geteilten Loader (Doppel-Fetch-Vermeidung) ist erlaubt, ändert aber kein Teil-2-AC/-Verhalten |
| `src/services/compare_alert.py::_SUMMARY_KEY_TO_CATALOG_ID` | module | Autoritative Liste der 10 alarmfähigen Keys — Quelle für das neue `alarmCapable`-Feld im Backend-Katalog (D1); NICHT verändern, nur lesen |
| `frontend/.../compare/compareHubWizardBridge.ts`, `compareWizardState.svelte.ts`, `compareEditorSave.ts` | frontend module | Importieren `IdealRange` aus `compareMetricDefs.ts` — Import-Pfad muss auf `corridorEditorState.ts` umgebogen werden (D3), Typ selbst unverändert |
| `frontend/.../compare-new/CompareNewEditor.svelte` | frontend component | Importiert `PROFILE_METRICS_WITH_SCALES`/`ProfileKey` aus `compareMetricDefs.ts` — Import-Pfad umbiegen, nutzt nur `.key`/`.label` (D3-Reduktion verträglich) |
| `frontend/.../compare/issue_462.test.ts` | frontend test | Referenziert `CompareMatrix.svelte`-Inhalt (Card/Table-Namespace-Check) + `HourlyMatrix.svelte`-Pfad (Style-Migrations-Liste) — beide Referenzen entfernen (D2) |
| `frontend/.../compare/compareEditorSlice3.test.ts` (245 Zeilen) | frontend test | Enthält 2 unabhängige `describe`-Blöcke zu `ALL_METRICS`/`deriveIdealText` (tot, entfernen) UND unabhängige Tests zu `buildComparePresetSavePayload`/`rehydrateActiveMetrics` (bleiben) — **nur die 2 Blöcke + ihre Imports entfernen, Datei bleibt** |
| `frontend/.../compare/issue_718_idealwert_validation.test.ts` (96 Zeilen) | frontend test | Testet ausschließlich `validateIdealRanges` (verifiziert: kein Produktiv-Konsument) — **ganze Datei löschen** |

## Implementation Details

**1. Backend — `alarmCapable` (D1, Hybrid):** `compare_metric_catalog.py` bekommt pro
Eintrag ein neues Feld `alarmCapable: bool`, `True` für genau die 10 Keys aus
`compare_alert._SUMMARY_KEY_TO_CATALOG_ID` (`temp_max_c`, `temp_min_c`, `wind_max_kmh`,
`gust_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`,
`snow_new_sum_cm`, `cape_max_jkg`, `freezing_level_m`), sonst `False`. Der bestehende
Drift-Assert (Keys ↔ `compare_metric_ids.py`) bleibt unverändert; optional ein zweiter
Assert, dass `alarmCapable`-Keys ⊆ Katalog-Keys sind (defensiv, kein neuer
Datenverlust-Pfad). `test_compare_metric_catalog_endpoint.py`: `required_base`-Set um
`alarmCapable` erweitern (AC-2-Test) und `EXPECTED_METRICS`-Fixture + Vergleichsschleife
(AC-3-Test) um `alarmCapable` pro Key ergänzen. `docs/reference/api_contract.md`:
Response-DTO-Abschnitt um `alarmCapable` ergänzen + Changelog-Zeile.
`defaultMin`/`defaultMax` bleiben **bewusst nicht** im Backend-Katalog (dünne
FE-UX-Tabelle, s. Punkt 3) — Präzedenz: Trip (`ROUTE_METRIC_DEFS`) hält Startwerte
ebenfalls FE-seitig.

**2. Neues FE-Modul — geteilter Katalog-Loader (Async-Kernbaustein):** neue Datei
`frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts`
(reine TS-Logik, kein Svelte-Import, lauffähig unter `node --experimental-strip-types`
analog `corridorEditorState.ts`):
- `buildCompareMetricDefs(response: CompareMetricCatalogResponse): CompareMetricDef[]` —
  reiner, testbarer Mapper: `metric = entry.key`, `label = entry.label`,
  `unit = entry.unit ?? ''`, `step = entry.step ?? 1`, `kind = entry.kind === 'ordinal'
  ? 'ordinal' : 'range'` (Plattdrücken von `enum` auf `range` wie heute —
  `precip_type_dominant` bleibt im Editor ein Zahlen-Slider mit Scale `[0,100]`, keine
  abweichende Darstellung, unverändertes Bestandsverhalten), `ordinalLabels =
  entry.ordinalLabels`, `scale = kind === 'ordinal' ? [0, (entry.ordinalLabels?.length
  ?? 1) - 1] : [entry.rangeMin ?? 0, entry.rangeMax ?? 100]`, `alarmCapable =
  entry.alarmCapable ?? false` (aus Backend, D1), `defaultMin`/`defaultMax` aus der
  dünnen FE-Tabelle (Punkt 3, per `metric`-Lookup, Fallback `null`/`null`).
- `loadCompareMetricCatalog(): Promise<CompareMetricDef[]>` — ruft
  `api.get<CompareMetricCatalogResponse>('/api/compare/metrics')` auf, mappt via
  `buildCompareMetricDefs`, **cached das Promise modul-weit** (einmal pro Seiten-Load,
  nicht pro Komponenten-Instanz) — verhindert Doppel-Fetch, falls sowohl
  `WeatherMetricsTab` (Teil 2) als auch `CorridorEditor` im selben Seiten-Load fetchen.
  Ein Fehler invalidiert den Cache (nächster Aufruf fetcht erneut — kein dauerhaft
  gecachter Fehlerzustand).

**3. Dünne FE-Defaults-Tabelle (D1, bleibt FE-seitig):** `_COMPARE_DEFAULTS` (14 Keys,
heute in `corridorEditorState.ts:256-271`) bleibt unverändert bestehen (Inhalt 1:1
übernommen), wird aber vom neuen Mapper (Punkt 2) statt von `COMPARE_METRIC_DEFS =
ALL_METRICS.map()` gelesen. `_COMPARE_ALARM_KEYS` (heute FE-Liste, `corridorEditorState.ts:235-238`)
**entfällt ersatzlos** — `alarmCapable` kommt jetzt aus dem Backend-Feld (Punkt 1).

**4. `corridorEditorState.ts` — Parametrisierung statt Modul-Konstante:**
`COMPARE_METRIC_DEFS`/`COMPARE_METRIC_DEF_BY_ID` als Modul-Konstante entfallen
(Grund: sie hingen synchron an `ALL_METRICS`-Import, der jetzt async über den Loader
kommt). Die drei Konsumenten-Funktionen bekommen ein explizites `defs:
CompareMetricDef[]`-Argument statt des impliziten Modul-Zugriffs:
- `buildComparePool(corridors, defs)` (baut `COMPARE_METRIC_DEF_BY_ID` lokal aus `defs`)
- `addCompareRow(rows, poolLeft, metric, defs, ctxDefaults?, wasActive?)`
- `buildComparePrefillRows(profileKey, defs)`

`buildCompareCorridorSavePayload` bleibt **unverändert** — sie liest nur aus
bereits gebauten `CorridorRowState`-Zeilen (die ihre `kind`/`ordinalLabels`/
`alarmCapable`-Felder schon beim Zeilenbau kopiert bekommen haben), keine
Def-Lookup-Abhängigkeit zur Laufzeit.

**5. D3 — Profil-Feature zieht in `corridorEditorState.ts` um:** `ProfileKey`,
`IdealRange`, `IDEAL_DEFAULTS` (Inhalt unverändert übernommen) ziehen komplett in
`corridorEditorState.ts` (natürlicher, einziger verbleibender Ort — kein neues File,
da `corridorEditorState.ts` bereits `CompareMetricDef`/`COMPARE_METRIC_DEFS`-Nachfolger
beheimatet). `PROFILE_METRICS_WITH_SCALES` wird auf Keys+Label reduziert (die
Konsumenten lesen ausschließlich `m.key`/`m.label`, verifiziert in `CompareNewEditor.svelte:159-160`
und `corridorEditorState.ts::buildComparePrefillRows`):
```ts
export const PROFILE_METRICS_WITH_SCALES: Record<ProfileKey, { key: string; label: string }[]> = {
  WINTERSPORT:     [{ key: 'snow_depth_cm', label: 'Schneehöhe' }, ...],
  ...
};
```
Werte 1:1 aus den heutigen `MetricDef`-Objekten übernommen (nur `key`/`label`
extrahiert, keine neuen Labels erfunden). Fünf Import-Umbiegungen (Pfad ändert sich
von `'../../compare/compareMetricDefs.ts'`/`'./compareMetricDefs'` zu
`'./corridorEditorState.ts'` bzw. relativer Pfad): `compareWizardState.svelte.ts`,
`compareHubWizardBridge.ts`, `compareEditorSave.ts`, `CompareNewEditor.svelte`,
`CorridorEditor.svelte`/`CorridorEditorMobile.svelte` (importieren `ProfileKey` bereits
von `compareMetricDefs.ts`, Pfad umbiegen). Tote Exporte `deriveIdealText`/
`validateIdealRanges` werden **nicht** mit umgezogen (D3 betrifft nur das
Profil-Feature) — sie werden mit ihren Tests gelöscht (s. Punkt 7).

**6. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte` — Async-Konsum (größtes
Einzelrisiko, identisch in beiden Dateien):** heute wird `initial =
computeInitialCompare()` **synchron beim Skript-Start** ausgewertet (`rows`/`poolLeft`
sofort aus `COMPARE_METRIC_DEFS` gebaut, Zeile 73-75 `CorridorEditor.svelte`), inkl.
sofortigem `syncToWizard()`-Aufruf für den Fresh-Create-Fall (Zeile 121). Das ist mit
einem Fetch nicht mehr möglich. Neue Struktur (nur `context==='vergleich'`-Zweig
betroffen — `context==='route'` bleibt unverändert synchron, `ROUTE_METRIC_DEFS` wird
NICHT migriert):
- `let compareDefs = $state<CompareMetricDef[] | null>(null)`, `let compareDefsError =
  $state<string | null>(null)`, `rows`/`poolLeft`/`unknownCorridors` initial `$state([])`
  für den vergleich-Zweig.
- `$effect`, das bei `context === 'vergleich' && compareDefs === null &&
  !compareDefsError` genau einmal `loadCompareMetricCatalog()` aufruft (Guard analog
  Teil-2-Muster in `WeatherMetricsTab.svelte:381`), bei Erfolg `compareDefs` setzt UND
  danach `computeInitialCompare(compareDefs)` + ggf. `syncToWizard()`-Prefill ausführt
  (das, was heute synchron beim Skript-Start passiert), bei Fehler `compareDefsError`.
- Neue Fehler-/Lade-Shells **innerhalb** des `context==='vergleich'`-Renderpfads
  (eigene `data-testid`, z.B. `corridor-editor-vergleich-load-error`/`-loading`,
  „Wiederholen"-Button analog Teil 2) — kein still leerer Editor bei Endpoint-Ausfall
  (AC-4). Reines Laden löst kein `syncToWizard()`/PUT aus außer dem einmaligen
  Fresh-Create-Prefill (das ist bereits heute ein reines State-Schreiben ohne PUT,
  Verhalten bleibt gleich).
- Alle Aufrufstellen von `addCompareRow(...)`/`buildComparePrefillRows(...)` bekommen
  `compareDefs` (non-null zu diesem Zeitpunkt, da Zeilen erst nach erfolgreichem Laden
  gerendert werden) als zusätzliches Argument durchgereicht.

**7. D2 — Tote Winner-Box + tote Funktionen löschen:**
`frontend/.../compare/CompareMatrix.svelte` (191 Zeilen) + `HourlyMatrix.svelte`
(98 Zeilen) + `__tests__/compare_matrix_dead_code.test.ts` (52 Zeilen, Bestandsnachweis
für den jetzt gelöschten Zustand — Test selbst wird überflüssig) ersatzlos löschen.
`issue_462.test.ts`: die `HourlyMatrix.svelte`-Zeile aus der Style-Migrations-Pfadliste
(Zeile 39) und den `CompareMatrix.svelte`-Card/Table-Namespace-Check (Zeilen 127-131)
entfernen. `compareEditorSlice3.test.ts`: **nur** die beiden `describe`-Blöcke
„ALL_METRICS — vollständiger Metrik-Katalog" und „deriveIdealText" (samt der 2
zugehörigen jetzt toten Imports, Zeilen ~19-28) entfernen — die Datei bleibt mit ihren
übrigen, unabhängigen Tests (`buildComparePresetSavePayload`/`rehydrateActiveMetrics`)
bestehen. `issue_718_idealwert_validation.test.ts` (96 Zeilen) **komplett löschen** —
verifiziert: testet ausschließlich die tote `validateIdealRanges`, kein anderer Inhalt.

**8. `compareMetricDefs.ts` löschen (141 Zeilen):** nach Punkt 3–7 hat keine Datei mehr
einen Import daraus — ersatzlose Löschung.

**Explizit NICHT Teil dieser Spec:** Persistenz-Format (`corridors[]`/`ideal_ranges`/
`active_metrics`/`metric_alert_levels`) unverändert; `weatherMetricsCompareSave.ts`
(Default-Fallback bleibt auf die neue `corridorEditorState.ts`-Quelle verweisen, nur
Importpfad ändert sich falls nötig — Inhalt/Verhalten unverändert); Go-Proxy/Endpoint
(Teil 1, unverändert); `WeatherMetricsTab.svelte`s Teil-2-Fetch bleibt lauffähig auch
ohne Umstellung auf den neuen Loader (Umstellung optional, kein AC).

## Expected Behavior

- **Input:** Öffnen des Schwellen-Editors (Idealwerte-Tab, Hub-Detail oder
  `/compare/new`) mit `context='vergleich'`.
- **Output:** Pool + Zeilen zeigen exakt die Metriken/Felder, die heute
  `COMPARE_METRIC_DEFS` liefert (Label/Einheit/Skala/`kind`/Ordinal-Labels/
  `alarmCapable`/Default-Von-Bis) — jetzt aus `GET /api/compare/metrics` gebaut;
  eine neue Backend-Metrik erscheint im Pool ohne Frontend-Code-Änderung.
  Speicher-Payload (`corridors`/`ideal_ranges`/`metric_alert_levels`) bitgleich zu
  heute für dieselben Nutzereingaben.
- **Side effects:** ein zusätzlicher `GET /api/compare/metrics`-Request beim ersten
  Öffnen des Schwellen-Editors (gecacht, kein Doppel-Fetch bei erneutem Öffnen
  innerhalb desselben Seiten-Loads); kein zusätzliches PUT durch den Ladevorgang.

## Acceptance Criteria

- **AC-1:** Given der Schwellen-Editor (`CorridorEditor`/`CorridorEditorMobile`,
  `context='vergleich'`) wird geöffnet / When Pool und Zeilen rendern / Then stammen
  sie aus der echten `GET /api/compare/metrics`-Antwort; eine um einen synthetischen
  Eintrag erweiterte Katalog-Fixture erscheint im Pool — ohne jede
  Frontend-Code-Änderung.
  - Test: Kern-Test rendert den Editor gegen eine fixierte, aus dem echten Endpoint
    gezogene Fixture-Antwort (Standard-25 + eine erweiterte Variante mit
    Zusatzeintrag) und prüft Pool-Inhalt/-Reihenfolge (Component-Test, kein
    Dateiinhalt-Grep).

- **AC-2 (Charakterisierung, Parität):** Given alle 25 Keys / When die aus dem
  Endpoint gebauten `CompareMetricDef`-Objekte (`buildCompareMetricDefs`) gegen eine
  aus dem heutigen `COMPARE_METRIC_DEFS`-Stand eingefrorene Fixture verglichen werden
  / Then stimmen `scale`/`step`/`kind`/`ordinalLabels`/`alarmCapable`/`defaultMin`/
  `defaultMax` für jeden Key exakt überein.
  - Test: Kern-Test vergleicht `buildCompareMetricDefs(fixtureResponse)` (Fixture aus
    einem echten `/api/compare/metrics`-Antwort-Mitschnitt) Feld für Feld gegen die
    eingefrorene 25-Einträge-Erwartung — kein Datei-Grep, sondern Wertevergleich.

- **AC-3:** Given der Backend-Katalog / When `GET /api/compare/metrics` inspiziert
  wird / Then trägt jeder Eintrag `alarmCapable`, `true` für genau die 10 heutigen
  Alarm-Keys (`temp_max_c`, `temp_min_c`, `wind_max_kmh`, `gust_max_kmh`,
  `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`, `snow_new_sum_cm`,
  `cape_max_jkg`, `freezing_level_m`), sonst `false`; die „Warnen"-Button-Sperre für
  nicht-alarmfähige Metriken im Editor bleibt unverändert wirksam.
  - Test: Backend-Kern-Test (Erweiterung von `test_compare_metric_catalog_endpoint.py`)
    prüft `alarmCapable` je Key gegen die 10er-Liste; FE-Kern-Test prüft, dass
    `addCompareRow`/`buildCompareCorridorSavePayload` für `alarmCapable===false`-Zeilen
    `notify` weiterhin ignorieren (bestehendes Verhalten, jetzt datengetrieben statt
    über die gelöschte FE-Liste `_COMPARE_ALARM_KEYS`).

- **AC-4 (Async-Robustheit):** Given `GET /api/compare/metrics` schlägt fehl
  (Netzwerkfehler oder Non-2xx) / When der Schwellen-Editor geöffnet wird / Then zeigt
  er einen sichtbaren Fehlerzustand mit „Wiederholen"-Button — kein still leerer/
  kaputter Editor; reines Laden (Mount → Fetch-Resolve, ohne Nutzer-Interaktion) löst
  kein `syncToWizard()`-Schreiben und kein PUT aus, das über das bestehende
  Fresh-Create-Prefill-Verhalten hinausgeht.
  - Test: Kern-Test mockt einen fehlschlagenden `api.get`-Call für
    `/api/compare/metrics`, prüft sichtbaren Error-Shell-Testid + keine gerenderten
    Zeilen; zweiter Test zählt PUT-/`ws`-Schreib-Aufrufe über den Ladezyklus vor jeder
    Nutzer-Geste (analog Teil-2-PUT-Count-Muster).

- **AC-5 (Persistenz bitgleich):** Given identische Nutzereingaben (Zeilen, Von/Bis,
  notify/mark) / When `buildCompareCorridorSavePayload` aufgerufen wird / Then ist das
  Ergebnis (`corridors`/`ideal_ranges`/`active_metrics`/`metric_alert_levels`)
  bitidentisch zum Verhalten vor dieser Migration; ein bestehendes Preset lädt mit
  unveränderten Schwellen; `addCompareRow`-Default-Von-Bis (`defaultMin`/`defaultMax`)
  und `buildComparePrefillRows`-Startwerte bleiben unverändert.
  - Test: bestehende `corridorEditorState.test.ts`-Suite (angepasst auf die neue
    `defs`-Parameter-Signatur, gleiche Erwartungswerte) bleibt grün; neuer Kern-Test
    ruft `buildCompareCorridorSavePayload` mit denselben Fixture-Eingaben wie vor der
    Migration auf und vergleicht den Payload gegen die alte Erwartung.

- **AC-6 (Profil-Feature unverändert):** Given der Compare-Create-Wizard (Fresh-Create,
  Profil-Prefill) / When ein Aktivitätsprofil gewählt wird / Then befüllt
  `buildComparePrefillRows` dieselben Zeilen mit denselben Idealwerten wie vor dem
  Umzug von `IDEAL_DEFAULTS`/`ProfileKey`/`PROFILE_METRICS_WITH_SCALES` nach
  `corridorEditorState.ts`.
  - Test: bestehende Prefill-Tests aus `corridorEditorState.test.ts` bleiben grün
    (Import-Pfad angepasst, Erwartungswerte unverändert); `CompareNewEditor.svelte`
    zeigt weiterhin die korrekten Profil-Metrik-Labels (Regressionsschutz, bestehender
    Test/E2E unverändert grün).

- **AC-7 (SSoT-Abschluss + Aufräumen):** Given die Migration ist abgeschlossen / When
  `compareMetricDefs.ts` gesucht wird / Then existiert die Datei nicht mehr; kein
  Import verweist mehr darauf; `CompareMatrix.svelte`/`HourlyMatrix.svelte` und ihr
  Dead-Code-Guard-Test sind gelöscht; `npm run check` (TypeScript) und der Frontend-Build
  laufen ohne Fehler; alle verbleibenden Compare-/Corridor-Testsuiten sind grün.
  - Test: `grep -r "compareMetricDefs" frontend/src` liefert keine Treffer (Bestandsnachweis,
    kein Verhaltens-AC — reiner Abwesenheitsnachweis, ergänzt durch grünen Build/Check
    als eigentlichen Verhaltensnachweis); `npm run check` + `npm run build` Exit 0;
    `node --test` über die betroffenen Testdateien Exit 0.

## Known Limitations

- Die Umstellung von `WeatherMetricsTab.svelte` (Teil 2) auf den neuen geteilten
  Loader (`compareMetricCatalogLoader.ts`) ist **optional** — sie würde Doppel-Fetches
  vollständig eliminieren, ist aber kein AC dieser Spec, um das Risiko für bereits
  produktiv verifiziertes Teil-2-Verhalten nicht unnötig zu erhöhen. Wird sie
  vorgenommen, müssen Teil-2-Tests unverändert grün bleiben (reiner Fetch-Quelle-Tausch,
  identische Rückgabeform via `toCompareSelectionEntries`).
  - **Why:** Trade-off zwischen „ein Fetch weniger" und „unnötige Berührung
    verifizierten Codes" — Tech-Lead-Neigung: nur anfassen, wenn der Diff dadurch
    tatsächlich kleiner statt größer wird.
- `precip_type_dominant` bleibt im Editor als generischer `range`-Zweig (Scale
  `[0,100]`) statt eines echten Enum-Steuerelements geführt — eine seit Teil 1
  bekannte, hier nicht reparierte Frontend-Eigenart (außerhalb des Scopes).
- Nach dieser Migration gibt es **keine** zweite Quelle mehr für den Compare-Katalog —
  fällt `GET /api/compare/metrics` dauerhaft aus, ist sowohl die Auswahlliste (Teil 2)
  als auch der Schwellen-Editor (Teil 3) betroffen. Das ist die bewusste Endstufe der
  Strangler-Migration (kein stiller Fallback auf eine FE-Konstante, die es nach diesem
  Teil nicht mehr gibt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Abschluss ersetzt einen bereits in Teil 1/2 begonnenen,
  additiven Read-Pfad durch seinen letzten verbleibenden Frontend-Konsumenten — keine
  neue Entscheidungsfläche (Kanäle, Provider, Auth, Editor-Paradigma, Test-/
  Deploy-Strategie). Das Persistenz-Format (Datenmodell-Entscheidungsfläche) bleibt
  explizit unverändert (AC-5). Die SSoT-Migrationsrichtung selbst (Backend als
  autoritative Quelle für Compare-Metrik-Präsentation) wurde bereits mit Teil 1
  festgelegt und ist Teil der laufenden Trip/Compare-Konvergenz (Epic #1230) — dieser
  Teil vollzieht nur deren letzten, bereits angekündigten Schritt.

## Changelog

- 2026-07-23: Initial spec created (Teil 3 von 3, Issue #1350, Strangler-Migration,
  SSoT-Abschluss + Aufräumen)
