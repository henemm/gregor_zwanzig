# Context: fix-3021-katalog-sprache

## Request Summary
Issue #3021 (Epic #2644, Spur A): Der Frontend-Lader des Vergleichs-Metrik-Katalogs ruft
`GET /api/compare/metrics` ohne `?lang=` auf. Englische Nutzer sehen dadurch die
katalogseitigen Texte (vor allem die Begründung „stündlich nicht wählbar", z. B. Sonnenstunden)
auf Deutsch. Ziel: Nutzersprache anhängen, Modul-Cache je Sprache trennen bzw. bei
Sprachwechsel neu laden; deutsche Nutzer unverändert.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts:84-99` | `cachedResponse` (ein Promise je Seiten-Load) + `fetchCompareMetricCatalogOnce()` ruft `/api/compare/metrics` ohne `lang`. Einzige Fetch-Stelle; alle drei Ableitungen (`loadCompareMetricCatalog`, `loadRouteExtraMetricDefs`, `loadCompareSelectionEntries`) hängen daran. |
| `api/routers/compare.py:11-28` | Endpoint kennt `lang` (#2751): `en` → englisch, alles andere → `de`. Go-Proxy reicht Query durch (laut Issue). |
| `src/output/renderers/compare_metric_catalog.py:366-450` | `get_compare_metric_catalog(lang)` — `lang` wirkt **nur** auf `hourlyNotSelectableReason`; `label`, `aggregation_label` bleiben deutsch (Frontend übersetzt diese selbst über Register/`metricLabel`/`metricAggregationLabel`, #2654/#2659). |
| `src/output/renderers/compare_hourly_metric_ids.py:71-99` | `hourly_exclusion_reason(metric_id, lang)` — Begründungen sunshine, temperature_night, wind_chill_night, Tagesrichtungen. |
| `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte:300-308` | Zeigt `group.hourly_not_selectable_reason` (testid `compare-layout-hourly-reason-<metric_id>`) — hier wird der deutsche Text für EN-Nutzer sichtbar. Eingebunden aus `WeatherMetricsTab.svelte:1601`, Katalog per Prop. |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts:29,75` | reicht `hourlyNotSelectableReason` in die Auswahl-Einträge durch. |
| `frontend/src/lib/i18n/locale.ts` | `locale`-Store (`writable<Lang>`), gesetzt in `routes/+layout.svelte:43-45` aus `data.lang` und live in `account/SpracheAuswahl.svelte:17` (Sprachwechsel ohne Seiten-Neuladen). |
| `frontend/src/lib/i18n/index.ts` | exportiert `locale`, `get` aus svelte/store für `.ts`-Module (`tr()` liest `get(locale)`). |

Verbraucher des Loaders: `CompareTabs.svelte` (Hub-Hydration 378/484/526/573), `CompareNewEditor.svelte:212`,
`TripNewEditor.svelte:32` (`loadRouteExtraMetricDefs`), `WetterTabInhalt.svelte:20`, `WeatherMetricsTab.svelte:138/575`.

## Existing Patterns
- Promise-Cache auf Modulebene mit Invalidierung bei Fehler (`cachedResponse`, `cachedRegister` im selben Modul).
- `.ts`-Module lesen die Sprache per `get(locale)` (Konvention `docs/reference/i18n_konventionen.md`; `tr()` in `i18n/index.ts`).
- Statische Kataloge mit Sprachparameter als Query statt Kontosprache (#2751-Begründung im Endpoint-Docstring).
- Tests im Frontend: `node --test` (kein Vitest), Mapper-Tests in `wetter-tab/__tests__/`, `corridorEditorState.test.ts`.

## Dependencies
- Upstream: `$lib/api` (`api.get`), Python-Endpoint `/api/compare/metrics?lang=`, Go-Proxy.
- Downstream: alle oben genannten Verbraucher; die Einträge dienen auch als **Kennungen** (`key`, `metric_id`, `aggregation`, `ordinalLabels` als Gewitter-Stufen-ID). Diese sind sprachunabhängig (Backend übersetzt nur die Begründung) — muss so bleiben.

## Existing Specs
- `docs/specs/modules/i18n_p12_python_ratsche_rest_2751.md` — führte `lang` am Endpoint ein.
- `docs/specs/modules/i18n_f10_vergleich_flaechen_2659.md`, F5 (#2654) — Frontend-Übersetzung von Namen/Auswertung.
- `docs/specs/modules/compare_metric_ssot_final.md` — Loader-Ursprung (#1350).

## Risks & Considerations
- **Cache je Sprache:** Sprachwechsel im Konto ohne Neuladen → bei einem einzigen Cache bliebe die alte Sprache. Cache als Map `lang → Promise`.
- **Hydration/Dirty-Check (CompareTabs):** Grundzustand wird aus Katalog-Einträgen gebaut; wechselt nur der Begründungstext, darf kein Schein-Diff entstehen (Kennungen gleich).
- Issue nennt „Wertebereiche-Reiter"; der sprachabhängige Servertext erscheint tatsächlich im Stundenverlauf-Block (Ortsvergleich, Layout). In der Analyse prüfen, ob im Wertebereiche-Reiter (Trip + Vergleich) weitere deutsche Reste aus der Katalog-Antwort sichtbar sind (z. B. `label` der Zusatz-Definitionen in `buildRouteMetricDefsFromCatalog`).
- SSR: `get(locale)` beim Serverrendern; der Loader läuft clientseitig in `onMount`/Effekten — prüfen.
- Kanal-Parität/Protokoll-Token unberührt (reine Editor-Anzeige).

## Analysis

### Type
Bug (i18n-Lücke, ADR-0104). Analyse inline durchgeführt (Umfang: eine Fetch-Stelle), Befunde unten am Code verifiziert.

### Verifizierte Befunde
1. **Einzige Fetch-Stelle:** `compareMetricCatalogLoader.ts:91-101` (`fetchCompareMetricCatalogOnce`) ruft `api.get('/api/compare/metrics')` ohne Query. Alle Ableitungen (`loadCompareMetricCatalog`, `loadRouteExtraMetricDefs`, `loadCompareSelectionEntries`) hängen daran — Fix an einer Stelle wirkt überall.
2. **Go-Proxy reicht die Query durch:** `internal/handler/proxy.go:67` (`stripUserIDQuery(r.URL.RawQuery)` → nur `user_id` wird entfernt, `lang` bleibt). Keine Go-Änderung nötig.
3. **Python-Endpoint fertig:** `api/routers/compare.py:12-28`, `lang=en` → Englisch, sonst Deutsch. Sprachabhängig ist **nur** `hourlyNotSelectableReason` (`compare_metric_catalog.py:442`). Kennungen (`key`, `metric_id`, `aggregation`, `ordinalLabels`), `label`, `aggregation_label` sind sprachunabhängig → kein Schein-Diff im Dirty-Check, Umkehr-Index (`toCompareSelectionEntries`) bleibt gültig.
4. **Sichtbare Stelle:** `CompareHourlyLayoutControls.svelte:300-304` (testid `compare-layout-hourly-reason-<metric_id>`, z. B. `sunshine`, `temperature_night`, `wind_chill_night`) — Stundenverlauf-Block im Metrik-Reiter des Ortsvergleichs. Im Trip-Wertebereiche-Reiter liefert der Katalog nur Zusatz-Definitionen; deren Namen übersetzt das Frontend bereits über das Register (#2654/#2659), dort ist kein Server-Begründungstext sichtbar.
5. **Unit-Test-Stubs sind robust:** Fetch-Stubs vergleichen `new URL(...).pathname` oder `url.includes('/api/compare/metrics')` → eine angehängte Query bricht sie nicht.
6. **Falle E2E:** `frontend/e2e/fix-1350-compare-metric-select.staging.spec.ts:260/279` fängt per `page.route('**/api/compare/metrics', …)` ab. Playwright-Globs (1.59.1) matchen die volle URL inkl. Query → mit `?lang=de` greift die Route nicht mehr, AC-4 (Fehlerzustand + Wiederholen) würde rot. Muster auf `'**/api/compare/metrics?*'` bzw. `'**/api/compare/metrics*'` anpassen (route und unroute identisch).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` | MODIFY | Sprache per `get(locale)` lesen, Query `?lang=<de|en>` anhängen; `cachedResponse` → `Map<Lang, Promise>` (Fehler invalidiert nur den Eintrag dieser Sprache) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/katalog_sprache_3021.test.ts` | CREATE | `node --test`: Netzgrenze `globalThis.fetch`; locale=en → Anfrage trägt `lang=en`, Begründung englisch durchgereicht; locale=de → `lang=de`; Sprachwechsel → zweite Anfrage mit neuer Sprache (kein alter Cache); gleiche Sprache → kein zweiter Fetch |
| `frontend/e2e/fix-1350-compare-metric-select.staging.spec.ts` | MODIFY | Route-Glob query-tolerant |
| `frontend/e2e/fix-3021-katalog-sprache.staging.spec.ts` | CREATE | Staging: EN-Nutzer sieht `compare-layout-hourly-reason-sunshine` englisch, DE-Nutzer deutsch |

### Scope Assessment
- Files: 4 (1 Produktivcode)
- Estimated LoC: +~20/-~8 Produktivcode, +~120 Tests
- Risk Level: LOW — eine Fetch-Stelle, Kennungen sprachunabhängig, Backend unverändert

### Technical Approach
`fetchCompareMetricCatalogOnce()` liest `get(locale)` (Konvention `.ts`-Module, wie `tr()`), normalisiert auf `'en'|'de'`, holt `/api/compare/metrics?lang=<lang>` und cached je Sprache in einer `Map<Lang, Promise<CompareMetricCatalogResponse>>`. Öffentliche Signaturen bleiben gleich (keine Verbraucher-Änderung). Sprachwechsel im Konto (`SpracheAuswahl.svelte`, ohne Seiten-Neuladen) wirkt beim nächsten Öffnen des Editors, weil die Verbraucher in `onMount`/Effekten neu laden und dann den Cache-Eintrag der neuen Sprache treffen. Live-Umschalten eines bereits offenen Editors ist nicht nötig (Sprachwahl liegt auf der Kontoseite).
Verworfen: `lang` als Funktionsparameter durch alle Verbraucher reichen (6+ Aufrufstellen, mehr Fläche, gleiche Wirkung).

### Dependencies
`$lib/api`, `$lib/i18n/locale` (`locale`-Store, `Lang`), `svelte/store` `get`. Downstream unverändert.

### Open Questions
- keine (Produktverhalten durch ADR-0104 und Issue festgelegt)
