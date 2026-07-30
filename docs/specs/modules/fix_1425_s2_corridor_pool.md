---
entity_id: fix_1425_s2_corridor_pool
type: feature
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [trip, corridor-editor, metric-catalog, wertebereiche]
---

# Trip-Wertebereiche-Pool aus zentralem Katalog (#1425 Schritt 2, Teil 1)

## Approval

- [ ] Approved

## Purpose

Der Trip-Korridor-Editor (Reiter „Wertebereiche", `context="route"`) bietet
Nutzer:innen heute nur 6 fest verdrahtete Wettergrößen als Wertebereich an
(`ROUTE_METRIC_DEFS`), obwohl der zentrale Metrik-Katalog 26 wählbare Größen
kennt. Der Ortsvergleich hatte dasselbe Problem und hat es in #1373 bereits
gelöst, indem er seinen Pool aus dem zentralen Katalog (`GET
/api/compare/metrics`) aufbaut. Diese Spec überträgt denselben Ansatz auf den
Trip-Pool: ~17 zusätzliche Metriken werden wählbar, ohne die bestehenden 6
oder den Compare-Pfad zu verändern. Die Gewitter-Skalen-Vereinheitlichung
(Prozent vs. Ordinal-Katalogskala inkl. Datenmigration) ist explizit NICHT
Teil dieser Spec — `thunder_level` bleibt unverändert die alte
Prozent-Definition, ein Folge-Workflow behandelt das gesondert.

Schritt 2, Teil 1 von Issue #1425 (Kind von Epic #1372, Dach-Epic #1374).

## Source

- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **Identifier:** `ROUTE_METRIC_DEFS`, `ROUTE_CORRIDOR_CATALOG_IDS`, `buildRoutePool()`

> **Schicht-Hinweis:** Alle Änderungen dieser Spec sind Frontend-only
> (`frontend/src/lib/components/shared/corridor-editor/...`,
> `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`). Kein Go-API-,
> kein Python-Core-Eingriff. Der wiederverwendete Endpoint
> `GET /api/compare/metrics` (`api/routers/compare.py:11-22`) bleibt
> unverändert.

## Estimated Scope

- **LoC:** ~150-250 (überwiegend Tests)
- **Files:** ~6-7
- **Effort:** medium (geteilte Komponente, aber additiv/lesend, kein
  Schreibpfad, keine Backend-Änderung, keine Datenmigration)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/compare/metrics` (`api/routers/compare.py:11-22`) | endpoint | Zentraler kuratierter Metrik-Katalog (26 Einträge, Rohform `CompareMetricCatalogEntry` inkl. `metric_id`) — bleibt unverändert |
| `fetchCompareMetricCatalogOnce()` (`compareMetricCatalogLoader.ts`) | function | Promise-Cache für den Katalog-Fetch — wird von Route mitgenutzt, kein zweiter Request |
| `buildComparePool()` (`corridorEditorState.ts:397-420`) | function | Vorbild-Pattern (Parameter statt Modulkonstante, `unknownCorridors`-Datenerhalt) — bleibt unverändert, nur als Referenz |
| `CorridorEditor.svelte` / `CorridorEditorMobile.svelte` | component | Aufrufer von `buildRoutePool`; brauchen denselben async Ladepfad wie `context==='vergleich'` |
| `tests/tdd/test_alert_metric_mapping_parity.py` | test | Parst `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS` per Regex aus der TS-Datei — bricht bei Umbenennung/Entfernung dieser Konstanten (Regressionsschutz, keine Änderung erwartet) |
| `weatherMetricsTabCorridorCoupling.test.ts` | test | Bestehende 6er-Fälle gegen `buildRoutePool` — müssen unverändert grün bleiben |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` | MODIFY | `buildRoutePool()` bekommt neuen optionalen Parameter `extraDefs: RouteMetricDef[] = []`, angehängt an die byte-identisch bleibenden `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS` |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` (oder neue Datei im selben Verzeichnis) | MODIFY/CREATE | Neuer Mapper `buildRouteMetricDefsFromCatalog(entries: CompareMetricCatalogEntry[]): RouteMetricDef[]` — filtert Duplikate über `metric_id` gegen `ROUTE_CORRIDOR_CATALOG_IDS`, bildet Rest auf `RouteMetricDef` ab; `CompareMetricDef`/`buildCompareMetricDefs()` bleiben unverändert |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | `context==='route'` bekommt denselben `$effect`-Ladepfad (Fetch + Ladezustand) wie `context==='vergleich'` (bisher bewusst synchron, Kommentar Zeile 92-96) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | dito für die mobile Variante |
| Frontend-Unit-Tests zu `corridorEditorState.ts` (bestehende Testdatei erweitern) | MODIFY | Neue Fälle: Duplikat-Ausschluss, `thunder` bleibt aussen vor, Katalog-Reihenfolge, `unknownCorridors`-Datenerhalt |
| `frontend/.../__tests__/weatherMetricsTabCorridorCoupling.test.ts` | MODIFY | Bestehende 6er-Fälle bleiben grün; ggf. ergänzende Fälle für erweiterten Pool |

**Explizit NICHT geändert:** `tests/tdd/test_alert_metric_mapping_parity.py` (Regressionsschutz — bricht das Skript dennoch, ist das ein Alarmsignal für eine versehentliche Umbenennung der geschützten Konstanten, kein akzeptiertes Ziel dieser Spec). `internal/model/trip.go` (`Corridor.Metric`) bleibt unverändert — kein serverseitiges Enum, keine Validierung, war schon vorher so.

## Implementation Details

**Datenfluss (analog #1373, siehe `buildComparePool` als Vorbild):**

1. `fetchCompareMetricCatalogOnce()` liefert die 26 rohen
   `CompareMetricCatalogEntry`-Objekte (inkl. `metric_id`) — derselbe Cache,
   den der Compare-Pfad schon nutzt, kein zweiter Netzwerk-Request.
2. Neuer Mapper `buildRouteMetricDefsFromCatalog(entries)`:
   - schließt Einträge aus, deren `metric_id` in der Menge
     `{gust, precipitation, temperature, thunder, snowfall_limit,
     freezing_level}` (= Schlüsselmenge von `ROUTE_CORRIDOR_CATALOG_IDS`)
     liegt — das schließt `thunder_level_max` automatisch mit aus, kein
     Sonderfall für die Gewitter-Ausklammerung nötig;
   - schließt zusätzlich Einträge aus, die serverseitig als
     `_COMPARE_RANGE_UNSUPPORTED` markiert sind (`precip_type_dominant`,
     `wind_direction_deg` — kein sinnvoller Slider-Wertebereich);
   - bildet die verbleibenden ~17 Einträge auf `RouteMetricDef` ab
     (`metric, label, unit, scale, step, defaultMin, defaultMax`) — kein
     `kind`/`ordinalLabels` nötig, da Ordinal-Fälle bereits durch die Filter
     draußen sind;
   - `defaultMin`/`defaultMax` werden aus der bereits bestehenden
     `_COMPARE_DEFAULTS`-Tabelle (`corridorEditorState.ts:259-292`) übernommen
     (Schlüssel = Katalog-`key`, identisch zum Compare-Pfad) — verhindert
     strukturell den #1424-Fehler (beidseitig offene Zeile blockt
     `validateCorridorRows` direkt nach dem Hinzufügen). Keine zweite
     Default-Tabelle, geteilt mit Compare;
   - behält die Katalog-Reihenfolge bei (keine eigene Sortierung).
3. `buildRoutePool(corridors, extraDefs: RouteMetricDef[] = [])` iteriert
   über `[...ROUTE_METRIC_DEFS, ...extraDefs]` statt nur über
   `ROUTE_METRIC_DEFS`. `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS`
   selbst bleiben byte-identisch (Testschutz für
   `test_alert_metric_mapping_parity.py`).
4. Datenerhalt: wie bei `buildComparePool` unbekannte Metrik-IDs in
   gespeicherten Korridoren nicht still verwerfen, sondern über das
   bestehende `unknownCorridors`-Pattern durchreichen — auch wenn aktuell
   kein Bestandskorridor eine der neuen 17 IDs referenziert (Pool war bisher
   auf 6 begrenzt), gilt das Pattern für künftige Katalog-Änderungen.
5. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`: `context==='route'`
   bekommt denselben `$effect`-Ladepfad wie `context==='vergleich'` (Fetch
   des Katalogs + Ladezustand-Anzeige), damit das erste Rendern nicht mit
   einer unvollständigen 6er-Liste startet und dann nachlädt (kein Ruckler,
   kein Race).

**Bewusst unverändert:**
- `CompareMetricDef`, `buildCompareMetricDefs()`, `buildComparePool()` —
  keine Rückwirkung auf den Compare-Pfad (Trip/Compare-Teilungs-Invariante).
- `thunder`/`thunder_level` — bleibt die alte, fest verdrahtete
  Prozent-Definition aus `ROUTE_METRIC_DEFS`; Gewitter-Skalen-Migration ist
  ein separater Folge-Workflow.
- Notify/Bedienelemente: Der Korridor-Editor hat nur noch den
  „Markieren"-Button (`mark`, Zeile 347-350) — der „Warnen"-Button wurde
  bereits in #1371 entfernt. Neue Metriken zeigen automatisch dasselbe
  einzige Bedienelement wie die alten 6, keine Fallunterscheidung nötig.
- Kein neuer Backend-Endpoint, kein serverseitiges Enum für
  `Corridor.Metric` (Go) — rein clientseitige Erweiterung.

## Expected Behavior

- **Input:** Nutzer:in öffnet den Trip-Editor, Reiter „Wertebereiche"
  (`context="route"`).
- **Output:** Die Metrik-Auswahl zeigt die bisherigen 6 Metriken plus ~17
  zusätzliche aus dem zentralen Katalog (23 insgesamt), in Katalog-Reihenfolge,
  ohne Duplikate, ohne `thunder_level` als zusätzlichen Eintrag.
- **Side effects:** Keine. Kein zusätzlicher Netzwerk-Request (Cache-Reuse),
  keine Änderung an Persistenz-Format oder Backend-Validierung, kein
  Verhaltenswechsel im Compare-Pfad.

## Acceptance Criteria

- **AC-1:** Given der Trip-Korridor-Editor (Reiter „Wertebereiche") ist
  geöffnet, When die Metrik-Auswahl geladen ist, Then enthält sie die
  bisherigen 6 Metriken plus die ~17 neuen Katalog-Metriken (23 insgesamt) in
  Katalog-Reihenfolge, ohne dass eine Metrik doppelt erscheint.
  - Test: Editor öffnen (Playwright/manuell), Anzahl und Reihenfolge der
    Einträge im Metrik-Dropdown/-Liste zählen und mit der erwarteten
    23er-Liste in Katalog-Reihenfolge vergleichen — kein Dateiinhalt-Check.

- **AC-2:** Given der zentrale Katalog enthält Einträge, deren `metric_id`
  bereits über die alten 6 Trip-Metriken abgedeckt ist (z.B.
  `temp_max_c`/`temp_min_c` für `temperature`, `gust_max_kmh` für `gust`),
  When der erweiterte Pool aufgebaut wird, Then erscheint keine dieser
  Größen ein zweites Mal in der Auswahl.
  - Test: Unit-Test ruft `buildRoutePool` mit den aus dem Katalog erzeugten
    `extraDefs` auf und prüft, dass jede `metric`-ID im Ergebnis-Pool genau
    einmal vorkommt (kein zweiter „Temperatur"- oder „Böen"-Eintrag).

- **AC-3:** Given `thunder_level` wird heute als Prozent-Wert (0-100)
  gespeichert und der Katalog kennt `thunder_level_max` als 3-stufige
  Ordinalskala, When der Pool erweitert wird, Then bleibt in der Auswahl nur
  die alte Prozent-Definition von `thunder` sichtbar — keine zusätzliche
  oder ersetzende Ordinal-Variante.
  - Test: Unit-Test prüft, dass der erweiterte Pool genau eine Metrik mit
    ID `thunder` enthält und deren Skala (min/max/step/label) exakt der
    bisherigen `ROUTE_METRIC_DEFS`-Definition entspricht.

- **AC-4:** Given ein Trip hat einen gespeicherten Wertebereich für eine der
  bisherigen 6 Metriken (z.B. Niederschlag), When der Korridor-Editor mit
  dem erweiterten Pool neu geladen wird, Then bleibt der gespeicherte Wert
  unverändert sichtbar und editierbar — kein stilles Verwerfen.
  - Test: Trip mit bestehendem Korridor öffnen, Editor lädt, gespeicherter
    Min/Max-Wert erscheint unverändert im entsprechenden Feld.

- **AC-5:** Given der Ortsvergleich-Editor (`context="vergleich"`) nutzt
  denselben geteilten Baustein, When der Trip-Pool erweitert wird, Then
  zeigt der Ortsvergleich weiterhin exakt seine bisherige Metrik-Liste und
  sein bisheriges Verhalten (`buildComparePool`/`CompareMetricDef`
  unverändert).
  - Test: Bestehende Compare-Korridor-Tests laufen unverändert grün;
    manuell den Ortsvergleich-Editor öffnen und die Metrik-Auswahl mit dem
    Stand vor dieser Änderung vergleichen — keine neue, fehlende oder
    umsortierte Zeile.

- **AC-6:** Given der Trip-Korridor-Editor lädt den Metrik-Katalog jetzt
  asynchron (wie der Ortsvergleich), When die Seite/der Reiter „Wertebereiche"
  geöffnet wird, Then zeigt die Oberfläche einen erkennbaren Ladezustand statt
  kurzzeitig nur die alten 6 Metriken anzuzeigen und dann nachzuladen.
  - Test: Editor öffnen und beobachten (Playwright-Wartebedingung oder
    manuell mit gedrosseltem Netzwerk) — kein sichtbares Aufpoppen/Nachladen
    der zusätzlichen Metriken nach initialem Rendern der alten 6.

## Known Limitations

- Die Gewitter-Skalen-Vereinheitlichung (Prozent vs. Ordinal, inkl.
  Datenmigration bestehender `thunder`-Korridore) ist bewusst nicht Teil
  dieser Spec — Folge-Workflow.
- Es gibt kein serverseitiges Enum für `Corridor.Metric` (Go,
  `internal/model/trip.go:72`) — eine ungültige Metrik-ID würde weiterhin
  klaglos gespeichert. Das ist ein vorbestehender Zustand, kein neues Risiko
  durch diese Änderung.
- `TRIP_CORRIDOR_METRIC_TO_COL_KEY` (`src/output/renderers/email/html.py:555-569`)
  bleibt als Übergangs-Mapping bestehen — dessen Auflösung ist Teil eines
  späteren Cleanup-Schritts in Issue #1425, nicht dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine rein additive Erweiterung eines
  bestehenden, bereits durch ADR-freie Praxis etablierten Musters (der
  Ortsvergleich hat denselben Katalog-Ansatz in #1373 ohne eigenes ADR
  eingeführt, siehe `docs/specs/modules/feat_1373_s2_ein_katalog.md`). Es
  wird kein neuer Provider, Kanal, kein neues Datenmodell und keine neue
  Auth-/Persistenz-Entscheidung getroffen — der wiederverwendete Endpoint
  (`/api/compare/metrics`) und die Filterlogik sind Implementierungsdetail
  innerhalb des bereits entschiedenen "ein zentraler Katalog"-Ansatzes
  (ADR-0037 grenzt einen verwandten, aber separaten Anwendungsfall ab:
  Ausblick-Ableitung aus dem Katalog). Ein Blick in `docs/adr/README.md`
  zeigt keinen bestehenden ADR-Eintrag speziell zum Korridor-Editor oder
  zur Trip/Compare-Katalog-Teilung.

## Changelog

- 2026-07-30: Initial spec created
