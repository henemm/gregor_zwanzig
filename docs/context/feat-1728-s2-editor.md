# Context: feat-1728-s2-editor (Scheibe 2 — Frontend/Editor)

> Erhoben 2026-08-15 im Worktree `intake-1728`, Basis `c18f8eb7` (S1 live als `5056726a`
> auf `origin/main`). Belege sind an diesem Stand gemessen.

## Request Summary

Scheibe 2 zu #1728: Der Editor-Abschnitt „05 — Auswertungen" (Trip-Kontext) entfällt
ersatzlos, weil der zugrundeliegende Mechanismus (`MetricConfig.aggregations`) seit
Scheibe 1 an keinem Ausgabeort mehr wirkt. Zusätzlich fehlen den vier neuen
Tagesrichtungs-Größen und `wind_chill_night` eigene Kürzel-Zeilen im Abschnitt
„04 — Schwellwerte". Pflicht-Klickpfad im Browser als Nachweis (PO-Leitplanke).

## 🔴 Wichtigster Befund: ein Teil ist durch Scheibe 1 bereits erledigt

**Die vier neuen Größen erscheinen bereits heute automatisch in „02 — Grundauswahl".**
Die Liste ist vollständig katalog-getrieben:
- `WeatherMetricsTab.svelte:495-503` lädt `GET /api/metrics` roh in `catalog`.
- `WeatherV2Grundauswahl.svelte:31-55` iteriert `CATEGORY_ORDER` und darunter `catalog[cat]`
  — **kein ID-Filter**, jede Metrik der Kategorie wird gerendert.
- Alle vier neuen Größen tragen `category="temperature"` (`metric_catalog.py`), dieselbe
  Kategorie wie `temperature` selbst — sie stehen also bereits als Toggle-Buttons da.

**Konsequenz für den Zuschnitt:** Scheibe 2 muss dort **nichts** tun. Der verbleibende
Umfang ist kleiner als ursprünglich angenommen.

## Related Files

| File | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Zentrale, geteilte Editor-Komponente (context `route`\|`vergleich`). Enthält beide betroffenen Blöcke |
| `frontend/src/lib/components/shared/weather-metrics-tab/aggregationSelection.ts` | Wird mit dem 05-Block **de facto totes Gepäck** — nur noch von `AggregationMetricRow.svelte:28` (Typ-Import, `mode='single'`-Zweig) und Tests referenziert |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | **NICHT vollständig entfernbar** — `mode='multiple'`-Zweig wird von Compare/Ausblick genutzt (s. Risiken) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | `ROUTE_ONLY_SECTIONS` (`:42`) — `'auswertungen'` muss raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/aggregation_selection.test.ts` | 225 Zeilen, testet ausschließlich den 05-Block — fällt komplett |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts` | Prüft `:38-40` explizit auf Anwesenheit von `'auswertungen'` — muss umgeschrieben werden |
| `api/routers/config.py:30-68` (`GET /api/sms-symbols`) | Bereits generisch — iteriert `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` ohne feste ID-Liste. Liefert die neuen Kürzel bereits, **kein Backend-Change nötig** |

## Existing Patterns

**Die Kürzel-Zeilen-Erweiterung ist ein reines Copy-Paste-Muster.** Der komplette Block:

```svelte
<!-- Fix #1613: Mehrfach-Symbol-Metriken ohne Schwellwert (kein onChange/levels). -->
{#if !buckets.off.includes('temperature')}
<MultiSymbolMetricRow
    metricId="temperature"
    label={metricById['temperature']?.label ?? 'Temperatur'}
    symbols={metricSymbols['temperature'] ?? []}
/>
{/if}
{#if !buckets.off.includes('temperature_night')}
<MultiSymbolMetricRow
    metricId="temperature_night"
    label={metricById['temperature_night']?.label ?? 'Nacht-Tiefsttemperatur'}
    symbols={metricSymbols['temperature_night'] ?? []}
/>
{/if}
{#if !buckets.off.includes('wind_chill')}
<MultiSymbolMetricRow
    metricId="wind_chill"
    label={metricById['wind_chill']?.label ?? 'Gefühlte Temperatur'}
    symbols={metricSymbols['wind_chill'] ?? []}
/>
{/if}
```
(`WeatherMetricsTab.svelte:1692-1713`, Abschnitt „04 — Schwellwerte",
`{#if sections.includes('sms_schwellen')}` `:1584` … `:1718`)

**`metricSymbols`** kommt bereits generisch aus `GET /api/sms-symbols`
(`WeatherMetricsTab.svelte:183-186`, `Object.fromEntries((smsSymbols?.metrics ?? []).map(...))`)
— kein Frontend-Change nötig, damit die neuen Kürzel dort ankommen. Bestätigt:
`api/routers/config.py:55-57` baut `all_metric_ids` aus `SMS_SYMBOL_BY_METRIC` +
`SMS_MULTI_SYMBOLS_BY_METRIC`, beide von Scheibe 1 bereits um die vier neuen IDs
erweitert (`metric_catalog.py:710-716`).

**Fünf neue Zeilen nach diesem Muster** (fünftes = `wind_chill_night`, PO-bestätigt
mitzunehmen):

| metricId | Default-Label (Fallback) | Erwartetes Kürzel-Ergebnis |
|---|---|---|
| `temperature_day_low` | „Tages-Tiefsttemperatur (Gehzeit)" | `K` |
| `temperature_day_high` | „Tages-Höchsttemperatur (Gehzeit)" | `D` |
| `wind_chill_day_low` | „Gefühlte Tages-Tiefsttemperatur (Gehzeit)" | `FK` |
| `wind_chill_day_high` | „Gefühlte Tages-Höchsttemperatur (Gehzeit)" | `FD` |
| `wind_chill_night` | „Gefühlte Nacht-Tiefsttemperatur" (`metric_catalog.py:221`) | `FN` |

`wind_chill` selbst behält seine bestehende Zeile (`WC` weiterhin daran gebunden, DEC-3
aus Scheibe 1) — **unverändert**, keine Anpassung nötig.

## Der 05-Block im Detail (zu entfernen)

- Kommentar+Block: `WeatherMetricsTab.svelte:1720-1757` (38 Zeilen)
- Reines `{#if}...{/if}`-Fragment: `:1727-1757` (31 Zeilen)
- Guard: `{#if sections.includes('auswertungen') && aggregationMetricIds.length}`

**State-Variablen, exklusiv am Block (fallen mit):**
- `aggregationMetricIds` (`$derived`, `:344-348`) — Lesestellen nur `:1727`, `:1737`
- `showsAggregationChoice` (Import `:58`, Aufruf `:346`) — einzige Verwendung

**`aggregationsMap` (`$state`, `:235`) bleibt vorerst** — hängt noch im Speicherweg
(`buildWeatherConfigMetrics(…, aggregationsMap)`, `metricsEditor.ts:338-379`,
Feld `aggregations` `:369`) und in Dirty-Vergleich/Laden/Reset (`:370,376,380,444,461,837,854`).
Nur die UI-Schreibstelle (`onSelect`-Callback `:1743-1750`) ist exklusiv am Block.
**Entfernung von `aggregationsMap` selbst ist Scheibe 3**, nicht diese Scheibe.

**Absicherung gegen erneutes Rendern:** `'auswertungen'` aus `ROUTE_ONLY_SECTIONS`
(`weatherMetricsTabSections.ts:42`) entfernen — doppelt abgesichert mit dem Entfernen
des `{#if}`-Blocks selbst (Verteidigung in der Tiefe, wie im Bestand üblich).

## Mount-Punkte (context-Verteilung)

6 reale Einhängungen von `<WeatherMetricsTab …>`:

| Datei:Zeile | context |
|---|---|
| `edit/TripEditView.svelte:201` | `route` (Default) |
| `trip-new/TripNewEditor.svelte:825` (Desktop) | `route` |
| `trip-new/TripNewEditor.svelte:1053` (Mobile) | `route` |
| `compare/CompareTabs.svelte:1396` | `vergleich` |
| `compare-new/CompareNewEditor.svelte:394` | `vergleich` |
| `compare-new/CompareNewEditor.svelte:491` | `vergleich` |

**„05" ist doppelt auf `route` beschränkt** — sowohl über `ROUTE_ONLY_SECTIONS` als auch
strukturell: der `vergleich`-Zweig (`{#if context === 'vergleich'}` ab `:1253`) nimmt
ohnehin einen komplett anderen Render-Pfad, der 05-Block-Code liegt nur im `route`-Zweig.

## Dependencies

- **Upstream:** `GET /api/metrics` (Grundauswahl-Katalog), `GET /api/sms-symbols`
  (Kürzel) — beide bereits vollständig durch Scheibe 1 versorgt, kein Backend-Change.
- **Downstream (NICHT anfassen, obwohl gleiche Komponente):**
  - `AggregationMetricRow.svelte` `mode='multiple'`-Zweig (`:78-93`) — genutzt von
    `WeatherMetricsTab.svelte:1308-1315` (Compare-Grundauswahl „02") und
    `CompareOutlookLayoutControls.svelte:161-164` (3-Tages-Ausblick). Nur der
    `mode='single'`-Zweig (`:49-51,66-77`) gehört zum 05-Block.
  - `compareAggregationGrouping.ts`, `compareMetricSelection.ts` — unabhängige
    Compare/Ausblick-Mechanik, nicht Teil dieser Scheibe.

## Existing Specs

| Spec | Rolle |
|---|---|
| `docs/specs/modules/feat_1728_s1_temp_aufloesung.md` | Vorgänger-Scheibe, freigegeben, live. Nennt Scheibe 2 explizit als „Wegfall des Bedienabschnitts 05" |
| `docs/specs/modules/trip_aggregation_selection.md` (#1357) | Ursprüngliche Spec des jetzt abzuschaffenden Abschnitts |
| `docs/specs/modules/compare_metric_order.md` § „Abgeloeste Festlegung" | Löst die frühere `compare_weather_metrics_tab.md`-Festlegung zu `ROUTE_ONLY_SECTIONS` ab (2026-07-18) |

## Vorbestehende, unabhängige Lücke (bewusst mitgenommen)

`wind_chill_night` hat **heute keine** Kürzel-Zeile im Editor — sein Kürzel `FN`
(`metric_catalog.py:224`, `compact_label="TFN"`, zur Laufzeit `"FN"` durch
Register-Ableitung) wird nirgends angezeigt. Älter als #1728, PO-bestätigt: bei dieser
Gelegenheit mitgenommen, da dieselbe Stelle und dasselbe Muster betroffen sind.

## Klickpfad-Nachweis (PO-Leitplanke)

**Kein bestehender Test deckt die 05-Block-Testids ab.** `metric-aggregations`,
`aggregation-metric-row-*`, `aggregation-option-*` kommen in `frontend/e2e/**` nirgends
vor. Einziger Treffer für `aggregation-choices-` ist `compare-outlook-metric-selection.
staging.spec.ts:190` — dort geht es um eine **bekannte Testid-Kollision** zwischen zwei
`mode='multiple'`-Aufrufern im Vergleich (beide ohne `testidPrefix` erzeugen
`aggregation-choices-temperature`), die der Test bewusst ausschließt — nicht der
05-Block.

30 Playwright-Specs berühren den Metriken-Reiter allgemein, davon **6 in der
CI-Positivliste** (`.github/ci_e2e_specs.txt`, 45 Dateien gesamt, wächst-nur-Ratsche,
Aufnahme erst nach 3× grün im **Zielverbund**, s. CLAUDE.md).

**Neuer Klickpfad muss:**
1. Trip-Editor öffnen, prüfen dass „05 — Auswertungen" **nicht mehr existiert**
   (negativer Nachweis — Selektor darf nicht gefunden werden).
2. Die fünf neuen Kürzel-Zeilen in „04 — Schwellwerte" sichtbar prüfen (positiver
   Nachweis, testid oder Textinhalt).
3. Vergleich-Editor **unverändert** bleibt (Regressionsschutz) — mindestens ein
   Sichtprüfungspunkt, dass `AggregationMetricRow mode='multiple'` dort weiterhin
   funktioniert.

## Risks & Considerations

1. **`AggregationMetricRow` nicht vollständig löschen** — sonst bricht Compare-Grundauswahl
   und 3-Tages-Ausblick. Nur den `mode='single'`-Zweig entfernen oder die Komponente ganz
   stehen lassen und nur ihren Trip-Aufrufer entfernen (letzteres ist der sicherere Weg,
   kleinerer Diff).
2. **`aggregation_selection.test.ts` fällt komplett (225 Zeilen)** — vier ACs (AC-5/6/8/9)
   der alten Spec #1357 werden dadurch unbewacht. Prüfen, ob eine davon noch eine gültige
   Zusicherung enthält (z. B. Roundtrip-Verhalten von `aggregationsMap`), die migriert
   werden muss, statt einfach gelöscht zu werden.
3. **`weatherMetricsTabSections.test.ts:38-40`** prüft aktuell POSITIV auf `'auswertungen'`
   im Route-Kontext — muss auf eine Negativ-Prüfung umgestellt werden (Regressionsschutz:
   der Abschnitt darf nie wiederkehren).
4. **Testid-Kollision im Vergleich** (`aggregation-choices-temperature`, doppelt vergeben)
   ist ein vorbestehender Bestandsbefund, nicht Teil dieser Scheibe — nicht versehentlich
   mitreparieren, sonst Scope-Creep.
5. **e2e-Positivliste:** ein neuer Klickpfad-Spec kann nicht sofort aufgenommen werden
   (Filter B verlangt 3× grün im Zielverbund). Das ist normal, keine Blockade dieser
   Scheibe — die Spec sollte das benennen, damit niemand „E2E bestanden" vor Erfüllung
   der Aufnahmekriterien behauptet.
6. **`WeatherMetricsTab.svelte` ist eine sehr große, geteilte Datei** (>1750 Zeilen,
   context `route`/`vergleich` in einer Komponente). Jede Änderung dort ist ein
   Pendant-Gate-Kandidat (`pendant_gate.py`) — hier greift er nicht (bestehende Datei,
   keine Neuanlage), aber sorgfältig prüfen, dass nichts versehentlich in den
   `vergleich`-Zweig hineinwirkt.

---

# Analysis (Phase 2)

## Type

**Feature** (planmäßige Folgescheibe, kein Fehlverhalten).

## Die alten ACs (#1357) — was wirklich weiterlebt

`docs/specs/modules/trip_aggregation_selection.md` AC-5/6/8/9 im Wortlaut geprüft gegen
`aggregation_selection.test.ts` (225 Zeilen):

| AC | Spec-Zusage | Tatsächlich getestet in der Datei | Überlebt den Wegfall? |
|---|---|---|---|
| AC-5 | keine Auswahl bei nur 1 Auswertung | `showsAggregationChoice()` + Quelltext-Grep auf den 05-Block | **Nein** — der Block selbst ist der Prüfgegenstand |
| AC-6 | Speichern-Laden-Roundtrip bleibt erhalten | **Nur einseitig:** `buildWeatherConfigMetrics(...)`-Payload-Bau + Quelltext-Grep, dass `WeatherMetricsTab.svelte` `aggregationsMap` an die Funktion durchreicht. **Kein echter Speicher-Lade-Zyklus getestet** | **Teilweise** — der reine Funktionsaufruf-Teil (`buildWeatherConfigMetrics` mit `aggregationsMap`) bleibt gültig, solange `aggregationsMap` im Speicherweg bleibt (Kontext-Dokument: bestätigt, Scheibe 3 entfernt es erst). Der Quelltext-Grep auf den UI-Block ist hinfällig |
| AC-8 | leere `aggregations` versteckt die Mail-Kachel | Datei testet stattdessen nur, dass `buildWeatherConfigMetrics` eine leere Liste in den Payload schreibt — **nicht** die Spec-Zusage selbst (die ist Backend, `test_trip_aggregation_pill_selection.py::test_empty_selection_hides_pill`) | **Payload-Teil bleibt gültig** (reine Funktionsprüfung), UI-Herleitung hinfällig |
| AC-9 | Ortsvergleich bekommt die Auswertungswahl nicht | Duplikat von `weatherMetricsTabSections.test.ts` — **derselbe Fakt wird zweimal geprüft**, hier zusätzlich mit einem Quelltext-Grep auf `AggregationMetricRow.svelte` | **Nein**, redundant — `weatherMetricsTabSections.test.ts` ist die kanonische Prüfstelle und bleibt (mit angepasster Route-Zeile) bestehen |

**Schlussfolgerung:** `aggregation_selection.test.ts` fällt **nicht restlos ins Leere** —
die reinen `buildWeatherConfigMetrics`-Funktionsaufrufe (Teile von AC-6/AC-8) prüfen eine
Funktion, die unabhängig von der UI-Komponente weiterlebt (Scheibe 3 entfernt sie erst).
Diese Teile sind zu **migrieren**, nicht ersatzlos zu löschen — sonst verliert
`buildWeatherConfigMetrics(..., aggregationsMap)` seinen einzigen Frontend-Test, bevor
Scheibe 3 die Funktion überhaupt anfasst.

## `weatherMetricsTabSections.test.ts` — Format-Vorbild und Konflikt

37 Zeilen, ein Testfall pro Zusicherung, direkter Funktionsaufruf (kein Rendering).
**Zeile 38–40 widerspricht der neuen Zusage direkt** (`'route'` enthält `'auswertungen'`)
— dieser Fall wird **ersetzt**, nicht ergänzt, durch das Gegenteil. Der Dateikopf
(Zeile 3–11) bestätigt bereits das Muster: „bewusst kein neuer RED-Nachweis, sondern
eigenständige Funktionsdatei" — dieselbe Konvention gilt für die Ersetzung.

## Klickpfad — Format-Vorbild existiert bereits im Repo

`frontend/e2e/issue-494-trip-edit-design.spec.ts:208-216` ist ein direktes Vorbild für
genau diesen Fall: Testname „AC-N: … existieren NICHT mehr im DOM", Kommentar mit
Herkunft, ein `toHaveCount(0)` je entferntem Testid. Zweites Vorbild:
`versand-tab.spec.ts:142-163` (Element nach Umzug in anderen Tab verschwunden).
**Kein neues Muster nötig — Bestandsmuster übernehmen.**

## `MultiSymbolMetricRow` — Testid-Konvention für die fünf neuen Zeilen

`MultiSymbolMetricRow.svelte:17,21`: `data-testid="sms-multi-symbol-row-{metricId}"`
(Zeile) und `data-testid="sms-symbol-badge-{metricId}-{symbol}"` (je Kürzel-Badge).
**Fertige, stabile Selektoren für den Klickpfad** — kein neues Testid-Schema nötig.

`multiSymbolMetricRowWiring.test.ts` (137 Zeilen) ist ein reiner Quelltext-Regex-Test
(kein Svelte-Rendering-Harness verfügbar) und das **Vorbild für die Verdrahtungsprüfung**
der fünf neuen Zeilen: Import vorhanden, Gate-Block-Muster
`{#if !buckets.off.includes('<id>')}...{/if}`, Prop-Bindung nicht hartcodiert. Mechanisch
erweiterbar, geringes Risiko.

## Scope Assessment

- Frontend-Dateien: `WeatherMetricsTab.svelte` (Löschung 05-Block ~38 Zeilen, Ergänzung
  5 Zeilen-Blöcke ~45 Zeilen), `weatherMetricsTabSections.ts` (1 Zeile), 3 Testdateien
  (1 gelöscht/migriert, 1 angepasst, 1 erweitert), 1 neuer Playwright-Spec
- Kein Backend-Change (bereits vollständig durch Scheibe 1 versorgt — bestätigt: sowohl
  `/api/metrics` als auch `/api/sms-symbols` sind generisch)
- Geschätzt: **~120-150 Zeilen Produktiv-Delta**, deutlich unter dem 250er-Budget
- Risiko: **LOW-MEDIUM** — größtes Risiko ist versehentliches Berühren des
  `AggregationMetricRow mode='multiple'`-Zweigs (Compare/Ausblick)

## Empfehlung

Vier Arbeitspakete, in dieser Reihenfolge:
1. Fünf `MultiSymbolMetricRow`-Blöcke ergänzen (mechanisch, nach Bestandsmuster)
2. 05-Block löschen + `ROUTE_ONLY_SECTIONS` bereinigen
3. Tests migrieren: `aggregation_selection.test.ts` → nur die UI-unabhängigen
   `buildWeatherConfigMetrics`-Fälle in eine neu benannte Datei überführen (Namensregel:
   nach Verhalten, nicht nach Issue), Rest löschen; `weatherMetricsTabSections.test.ts:38-40`
   auf Negativ drehen; `multiSymbolMetricRowWiring.test.ts` um 5 Fälle erweitern
4. Playwright-Klickpfad nach Bestandsmuster (`issue-494-trip-edit-design.spec.ts`-Stil)

## Open Questions

Keine — Muster, Testids und Testkonventionen sind vollständig im Bestand vorgefunden,
keine Design-Entscheidung offen. Direkt zu `/30-write-spec`.
