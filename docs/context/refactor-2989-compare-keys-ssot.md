# Context: refactor-2989-compare-keys-ssot (Issue #2989)

## Request Summary

Folge-Issue aus der Paritaets-Bestandsaufnahme #1986 (Eintrag NEU-8, PO-Auftrag
2026-08-19: „keinen doppelten Code fuer die gleiche Aufgabe"). Die Frontend-Liste
`COMPARE_METRIC_KEYS` ist eine Handkopie der Ortsvergleich-Katalog-Schluessel.
Ziel: aus dem Backend-Katalog laden statt Kopie; der Paritaetstest wird
ueberfluessig oder bleibt als Regressionswaechter.

## Was die Kopie heute traegt (zwei Bedeutungen!)

1. **Menge:** „nie eingestellt" (`active_metrics === null`) = alle Katalog-Groessen.
2. **Reihenfolge:** Mail-Standardfolge fuer Altbestand. Liste ist bewusst auf die
   Renderer-Folge `CV2_ZEILEN` (`src/output/renderers/email/compare_html.py`, ohne
   `warn`) gezogen (#1359 Scheibe 1), uebersetzt ueber
   `FRONTEND_TO_RENDERER_METRIC_ID` (`src/output/renderers/compare_metric_ids.py`).

Belegt 2026-11-26: der Katalog `get_compare_metric_catalog()` liefert die Schluessel
in **anderer** Reihenfolge (beginnt `snow_depth_cm, snow_new_sum_cm, ...`), die Kopie
beginnt `temp_max_c, wind_max_kmh, ...` = CV2-Folge. Ein naives „Keys aus dem
Endpoint" wuerde die Mail-Reihenfolge eines Alt-Vergleichs beim ersten Speichern
ungefragt umwerfen (genau der #1359-Fehler).

## Related Files

| Datei | Rolle |
|---|---|
| `frontend/src/lib/components/shared/wetter-tab/corridorEditorState.ts:512` | Definition `COMPARE_METRIC_KEYS` (Kopie) |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts:23` | `materializeActiveMetricKeys(null)` → Kopie (synchron) |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts:192` | `bisherigeZeilen` sortiert Alt-Schluessel nach Rang in der Kopie |
| `frontend/src/lib/components/shared/wetter-tab/compareMetricCatalogLoader.ts` | geteilter Promise-Cache fuer `GET /api/compare/metrics` (je Sprache) |
| `api/routers/compare.py:11` | Endpoint, liefert `{"metrics": [...]}` |
| `src/output/renderers/compare_metric_catalog.py` | Backend-Katalog (SSOT der Menge) |
| `src/output/renderers/email/compare_html.py` (`CV2_ZEILEN`) | SSOT der Standard-Reihenfolge (#1356) |
| `src/output/renderers/compare_metric_ids.py` | Katalog-Schluessel ↔ Renderer-ID |
| `internal/router/router.go:350` | Go-Proxy, reicht Antwort unveraendert durch |

Synchrone Aufrufer von `materializeActiveMetricKeys`:
`AlarmeTab.svelte:261,274`, `CompareTabs.svelte:476`, `anlegeVorbelegung.ts:129`,
`wertebereicheVergleichSpeicherung.ts:47`; dazu `ampelSchreiben.ts` (Speicherpfad).

Tests, die die Kopie importieren: `__tests__/compareMetricKeysParity.test.ts`
(liest Live-Python-Katalog, vergleicht **sortiert** → prueft nur Menge),
`__tests__/corridorEditorCapeExclusion.test.ts`, `corridorEditorState.test.ts`,
`shared/__tests__/compareMetricOrder.test.ts`,
`compare/__tests__/fix_3061_hub_hydrierer.test.ts`.

## Existing Patterns

- Katalog-Lader mit modulweitem Promise-Cache; Hub-Hydration (`compareHubHydration.ts`)
  wartet den Katalog bereits ab, bevor der Dirty-Check-Grundzustand gesetzt wird (#1373 F001).
- Backend-Seite: `_sort_by_cv2_order` leitet die Klartext-Folge aus `CV2_ZEILEN` ab
  (fail-fast bei Abweichung) — Vorbild fuer eine abgeleitete Standardfolge.

## Existing Specs

`compare_metric_default_order_ssot.md` (#1356, CV2 als Reihenfolge-SSOT),
`compare_metric_order.md` (#1359), `feat_3047_einstellung_gleich_mail_pruefkatalog.md`,
`fix_3061_ausblick_alle_groessen.md`, `feat_1585_cape_selectable_false.md`,
`paritaets_bestandsaufnahme.md` (#1986).

## Risks

- **Reihenfolge-Drift** (s. oben): Standardfolge muss mit ausgeliefert werden.
- **`null` vs. `[]`:** steht die Liste synchron noch nicht bereit, darf
  `materializeActiveMetricKeys(null)` NICHT `[]` liefern — `[]` heisst „bewusst leer"
  und wuerde beim Speichern alle Mail-Zeilen abwaehlen (Datenverlust-Klasse #102).
- **Synchron → asynchron:** fuenf Aufrufer erwarten die Liste sofort.
- **Scope:** Backend (Endpoint/Katalog) + Lader + zwei Verbraucher + Kopie loeschen +
  Testanpassungen → Grenze 4–5 Dateien knapp.
- Kein Nutzerdatenbezug im Endpoint (statischer Katalog) → kein Zwei-Nutzer-Test noetig.

## Analysis

**Type:** Feature (Refactoring, Doppelung aufloesen, kein Nutzerverhalten neu)

### Affected Files (Change Type)

| Datei | Change |
|---|---|
| `src/output/renderers/compare_metric_catalog.py` | MODIFY: `default_order()` aus `CV2_ZEILEN` (ohne `warn`) ueber `key_for(metric_id, aggregation)` abgeleitet, fail-fast gegen waehlbare Katalog-Keys |
| `api/routers/compare.py` | MODIFY: Antwort additiv um `default_order` erweitern (Go-Proxy reicht durch) |
| `frontend/.../wetter-tab/compareMetricCatalogLoader.ts` | MODIFY: Typ + modulweiter Speicher fuer `default_order`, im geteilten Promise-Chain befuellt; `getCompareDefaultOrder(): string[] \| null` |
| `frontend/.../weather-metrics-tab/compareMetricOrder.ts` | MODIFY: `materializeActiveMetricKeys(null)` liest den Speicher (Kopie) |
| `frontend/.../wetter-tab/ampelSchreiben.ts` | MODIFY: `bisherigeZeilen` rangiert ueber den Speicher |
| `frontend/.../wetter-tab/corridorEditorState.ts` | MODIFY: `COMPARE_METRIC_KEYS` loeschen |
| Tests: `compareMetricKeysParity.test.ts` (DELETE, ersetzt durch Backend-Waechter), `corridorEditorCapeExclusion.test.ts`, `compareMetricOrder.test.ts`, `fix_3061_hub_hydrierer.test.ts` (Seed statt Import) | MODIFY |

### Verworfene Varianten

| Variante | Dateien | LoC | Grund |
|---|---|---|---|
| A: `default_order` im Endpoint + FE-Speicher | ~6 prod + Tests | ~200-260 | **gewaehlt** |
| B: Kopie als Rueckfall behalten | 4-5 | ~100 | Kopie bleibt, Ziel verfehlt |
| C: Katalog selbst in CV2-Folge sortieren | 2-3 | ~30 + Folgeschaeden | aendert Anzeigefolge der Auswahlliste und Trip-Zusatzdefinitionen |

### Ladezeitpunkt je Verbraucher (geprueft)

- `AlarmeTab.svelte:261,274`, `CompareTabs.svelte:476`: Ergebnis wird mit `catalog ?? []` verrechnet, ohne Katalog ohnehin leer, harmlos.
- `anlegeVorbelegung.ts:129`: Aufrufer `CompareNewEditor.svelte:410-414` bricht ab, solange der Katalog fehlt: sicher.
- `wertebereicheVergleichSpeicherung.ts:47`: `erstelleWertebereicheVergleichSpeicherung` hat 2026-11-26 keinen Produktions-Aufrufer; `corridorSnapshotAus` laeuft im Hub nach der Hydration (die den Katalog abwartet, #1373 F001).
- `ampelSchreiben.ts:192`: `altSchluessel` stammt aus `altSchluesselAusKatalog` (`ampelModell.ts:314`), Katalog also geladen.

### Scope / Risk

Mittel. Produktion ~6 Dateien (eine davon nur Loeschung), Tests zusaetzlich; Ziel ±250 LoC gesamt.
Kernrisiko Datenverlust-Klasse: ungeladen darf „nie eingestellt" NIE als `[]` gespeichert werden.

### Technical Approach

1. Backend RED: Test `default_order` == CV2-Folge (ohne `warn`) in Katalog-Schluesseln, Menge == waehlbarer Katalog.
2. Backend: Feld ableiten + ausliefern.
3. Lader: Feld speichern (sprachunabhaengig, erste Antwort fuellt).
4. `materializeActiveMetricKeys(null)`: geladen → Kopie der Standardfolge; ungeladen → `[]` nur fuer Anzeige-Ableitungen.
   Speicherpfad `vergleichSpeicherPayload`: ist die Standardfolge ungeladen und `active_metrics` nie gesetzt, wird `active_metrics` NICHT geschrieben (bleibt „nie eingestellt").
5. `COMPARE_METRIC_KEYS` loeschen; Frontend-Paritaetstest entfaellt (ersetzt durch Backend-Waechter + FE-Test, dass der Speicher aus der Antwort befuellt wird).

### Open Questions

Keine Produktfrage: Nutzer sieht keine Aenderung (Menge und Reihenfolge bleiben gleich).
