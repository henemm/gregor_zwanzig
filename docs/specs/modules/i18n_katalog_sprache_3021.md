---
entity_id: i18n_katalog_sprache_3021
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
workflow: fix-3021-katalog-sprache
tags: [i18n, epic-2644, issue-3021, frontend, bugfix]
---

# i18n: Vergleichs-Metrik-Katalog in Nutzersprache laden

**Issue:** #3021 · **Epic:** #2644 · **ADR:** ADR-0104

## Approval

- [ ] Approved

## Purpose

Der Frontend-Lader des Vergleichs-Metrik-Katalogs ruft `/api/compare/metrics` ohne Sprachangabe auf. Englischsprachige Nutzer sehen deshalb die Begründung „stündlich nicht wählbar" (z. B. bei Sonnenstunden) im Metrik-Reiter des Ortsvergleichs auf Deutsch. Der Lader soll die Nutzersprache mitschicken und die Antworten je Sprache getrennt zwischenspeichern; deutsche Nutzer sehen unverändert Deutsch.

## Source

- **File:** `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts`
- **Identifier:** `fetchCompareMetricCatalogOnce`, Modul-Cache `cachedResponse`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend. Der Python-Endpoint (`api/routers/compare.py`, `?lang=` seit #2751) und der Go-Proxy (reicht die Query durch, nur `user_id` wird entfernt) bleiben unverändert.

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Der Lader liegt bereits unter `shared/` und bedient beide Seiten (`loadRouteExtraMetricDefs` für Trip, `loadCompareMetricCatalog`/`loadCompareSelectionEntries` für Ortsvergleich). Es entsteht keine neue Komponente.
> - **Mandantentrennung:** Der Katalog ist statisch und nutzerunabhängig; keine Nutzerdaten werden bewegt. Der Cache ist nach Sprache, nicht nach Nutzer getrennt. Die Sprache kommt aus dem `locale`-Store des angemeldeten Nutzers.
> - **Kanäle:** Nicht betroffen (reine Editor-Anzeige, keine Briefing- oder Alarm-Inhalte, keine Protokoll-Token).

## Estimated Scope

- **LoC:** +~20/-~8 Produktivcode, +~120 Tests
- **Files:** 4 (1 Produktivcode)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/api` (`api.get`) | module | Abruf von `/api/compare/metrics` |
| `$lib/i18n/locale` (`locale`, `Lang`) | module | Aktuelle Nutzersprache |
| `svelte/store` (`get`) | library | Sprache in `.ts`-Modul lesen (Konvention wie `tr()`) |
| `api/routers/compare.py`, `src/output/renderers/compare_metric_catalog.py` | endpoint | liefert `hourlyNotSelectableReason` je `lang` (`en` → englisch, sonst deutsch) |
| `internal/handler/proxy.go` | proxy | reicht `lang` unverändert durch |
| #2751 | Issue | führte `lang` am Endpoint ein |
| ADR-0104 | adr | Zweisprachigkeit, Kennungen nie übersetzen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` | MODIFY | Sprache per `get(locale)` lesen, `?lang=de\|en` anhängen, Cache als `Map<Lang, Promise>` |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/katalog_sprache_3021.test.ts` | CREATE | `node --test`, Netzgrenze `globalThis.fetch` |
| `frontend/e2e/fix-1350-compare-metric-select.staging.spec.ts` | MODIFY | `page.route`-Muster query-tolerant (route und unroute identisch) |
| `frontend/e2e/fix-3021-katalog-sprache.staging.spec.ts` | CREATE | Staging-Nachweis EN und DE |

## Implementation Details

`fetchCompareMetricCatalogOnce()` liest die Sprache über `get(locale)`, normalisiert auf `'en'` oder `'de'`, ruft `/api/compare/metrics?lang=<lang>` auf und speichert das Promise in einer `Map<Lang, Promise<CompareMetricCatalogResponse>>`. Schlägt ein Abruf fehl, wird nur der Eintrag dieser Sprache entfernt, damit „Wiederholen" neu lädt und der Cache der anderen Sprache erhalten bleibt. Die öffentlichen Signaturen (`loadCompareMetricCatalog`, `loadRouteExtraMetricDefs`, `loadCompareSelectionEntries`) bleiben unverändert, die Verbraucher müssen nicht angepasst werden.

Sprachwechsel im Konto (`SpracheAuswahl.svelte`, ohne Seiten-Neuladen) wirkt beim nächsten Öffnen des Editors, weil die Verbraucher beim Einhängen neu laden und dann den Cache-Eintrag der neuen Sprache treffen. Live-Umschalten eines bereits offenen Editors ist nicht nötig.

Sprachunabhängig bleiben `key`, `metric_id`, `aggregation`, `ordinalLabels`, `label` und `aggregation_label`; nur `hourlyNotSelectableReason` ändert sich mit der Sprache. Dadurch entsteht beim Sprachwechsel kein Schein-Diff im Dirty-Check des Hubs.

Verworfen: `lang` als Parameter durch alle Verbraucher reichen (mehr als 6 Aufrufstellen, gleiche Wirkung, mehr Fläche).

E2E-Falle: In `fix-1350-compare-metric-select.staging.spec.ts` fängt `page.route('**/api/compare/metrics', …)` nur URLs ohne Query ab; mit `?lang=…` würde die Fehlerzustand-Prüfung rot. Muster auf `'**/api/compare/metrics*'` ändern.

## Expected Behavior

- **Input:** Öffnen eines Editors, der den Metrik-Katalog lädt (Ortsvergleich-Metrik-Reiter, Trip-Wertebereiche), mit Nutzersprache `en` oder `de`.
- **Output:** Anfrage trägt `lang=<Sprache>`; die Begründung im Stundenverlauf-Block (testid `compare-layout-hourly-reason-<metric_id>`) steht in der Nutzersprache.
- **Side effects:** Je Sprache höchstens ein erfolgreicher Abruf pro Seiten-Load; keine Änderung an gespeicherten Daten.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch / When er im Ortsvergleich den Metrik-Reiter mit dem Stundenverlauf-Block öffnet / Then steht die Begründung, warum Sonnenstunden nicht stündlich wählbar sind, auf Englisch und nicht mehr auf Deutsch.
  - Test: `katalog_sprache_3021.test.ts` (`node --test`, `globalThis.fetch` als Netzgrenze): mit `locale=en` trägt die Anfrage `lang=en`, die englische Begründung wird unverändert durchgereicht. Staging-Playwright `fix-3021-katalog-sprache.staging.spec.ts`: EN-Nutzer sieht `compare-layout-hourly-reason-sunshine` englisch.

- **AC-2:** Given ein Nutzer mit Sprache Deutsch / When er denselben Metrik-Reiter öffnet / Then sieht er die Begründung wie bisher auf Deutsch, und Metrik-Namen, Auswertungen und Auswahl sind unverändert.
  - Test: `katalog_sprache_3021.test.ts`: mit `locale=de` trägt die Anfrage `lang=de`, Einträge sind gleich zum bisherigen Verhalten. Staging-Playwright: DE-Nutzer sieht `compare-layout-hourly-reason-sunshine` deutsch.

- **AC-3:** Given ein Nutzer wechselt im Konto die Sprache ohne Seiten-Neuladen von Deutsch auf Englisch / When er anschließend den Editor erneut öffnet / Then wird der Katalog in der neuen Sprache geladen und die Begründung erscheint englisch, ohne dass die Seite neu geladen werden muss.
  - Test: `katalog_sprache_3021.test.ts`: nach `locale.set('de')` Abruf, dann `locale.set('en')` zweiter Abruf mit `lang=en` und englischer Begründung (kein veralteter Cache).

- **AC-4:** Given der Katalog wurde in einer Sprache bereits geladen / When ein weiterer Editor oder Reiter in derselben Sprache geöffnet wird / Then erfolgt kein zweiter Netzabruf und alle Bereiche zeigen denselben Katalog.
  - Test: `katalog_sprache_3021.test.ts`: zwei Ladeaufrufe (`loadCompareMetricCatalog` und `loadRouteExtraMetricDefs`) bei gleicher Sprache ergeben genau einen `fetch`-Aufruf.

- **AC-5:** Given der Abruf des Katalogs schlägt fehl / When der Nutzer im Fehlerzustand „Wiederholen" wählt / Then wird der Katalog erneut geladen und erscheint; ein Fehler in einer Sprache entwertet nicht den bereits geladenen Katalog der anderen Sprache.
  - Test: `katalog_sprache_3021.test.ts`: erster `fetch` wirft, zweiter Aufruf lädt neu und liefert Daten; geladener Eintrag der anderen Sprache bleibt ohne neuen Abruf. Staging-Playwright `fix-1350-compare-metric-select.staging.spec.ts` (Fehlerzustand mit query-toleranter Route) bleibt grün.

- **AC-6:** Given zwei Nutzer, einer mit Englisch und einer mit Deutsch / When beide den Metrik-Reiter öffnen / Then sieht jeder die Begründung nur in seiner Sprache, und die Auswahl der Metriken (Kennungen, Auswertungsarten) ist für beide identisch, sodass im Hub kein falscher „Ungespeichert"-Zustand durch den Sprachwechsel entsteht.
  - Test: `katalog_sprache_3021.test.ts`: Kennungen (`key`, `metric_id`, `aggregation`, `ordinalLabels`) der Einträge sind bei `en` und `de` gleich; nur `hourlyNotSelectableReason` unterscheidet sich. Staging-Playwright mit zwei Nutzern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN locale=en WHEN der Katalog geladen wird THEN trägt die Anfrage `lang=en` und die englische Begründung kommt an
- [ ] Test 2: GIVEN locale=de WHEN der Katalog geladen wird THEN trägt die Anfrage `lang=de`
- [ ] Test 3: GIVEN Katalog in `de` geladen WHEN locale auf `en` wechselt und erneut geladen wird THEN zweite Anfrage mit `lang=en`, kein alter Cache
- [ ] Test 4: GIVEN gleiche Sprache WHEN mehrere Ableitungen laden THEN genau ein Abruf
- [ ] Test 5: GIVEN Abruf fehlgeschlagen WHEN erneut geladen wird THEN neuer Abruf; Eintrag der anderen Sprache unberührt
- [ ] Test 6: Staging-Playwright: EN-Nutzer sieht Begründung englisch, DE-Nutzer deutsch; Fehlerzustand + Wiederholen in `fix-1350-…staging.spec.ts` weiter grün

## Definition of Done

- AC-1 bis AC-6 erfüllt; Test 1–6 aus dem Test Plan grün, kein bestehender Test gelöscht, `fix-1350-compare-metric-select.staging.spec.ts` weiter grün.
- Adversary-Verdict VERIFIED: eine Mutation des Laders (z. B. `lang` weglassen oder ein gemeinsamer Cache für beide Sprachen) wird von einem Test gefangen.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden (EN-Nutzer sieht Begründung bei Sonnenstunden englisch, DE-Nutzer deutsch), Prod-Deploy mit Selftest-Exit 0.
- Issue #3021 geschlossen; Epic #2644 bleibt offen, solange weitere Kind-Issues offen sind.

## Known Limitations

- Ein bereits geöffneter Editor schaltet die Begründung nicht live um; die Sprachwahl liegt auf der Kontoseite, der Wechsel wirkt beim nächsten Öffnen.
- `label` und `aggregation_label` der Katalogantwort bleiben deutsch; das Frontend übersetzt sie über das Register (#2654/#2659). Der Wertebereiche-Reiter des Trips zeigt keinen Server-Begründungstext.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Setzt die Zweisprachigkeit am Nutzer um; kein neues ADR nötig, da nur eine Lücke im bestehenden Katalog-Abruf geschlossen wird.

## Changelog

- 2026-11-16: Initial spec created (Issue #3021)
