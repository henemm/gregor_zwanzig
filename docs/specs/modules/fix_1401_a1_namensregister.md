---
entity_id: fix_1401_a1_namensregister
type: bugfix
created: 2026-07-27
updated: 2026-07-27
status: draft
workflow: fix-1401-namensregister-a
version: "1.0"
tags: [compare, metric-catalog, naming, trip-compare-sharing]
---

# Fix #1401 Scheibe A1: Ein Namensregister für den Ortsvergleich

## Approval

- [x] Approved — PO Henning, 2026-07-27 („Go"): Acceptance Criteria, die acht
  Namensentscheidungen und die einmalige Anhebung des Änderungsbudgets auf 350
  Zeilen für diesen Workflow.

## Purpose

Dieselbe Wettergröße heißt heute an jeder Auswahlfläche im Ortsvergleich
anders ("Temperatur max" / "Temperatur" / "Wind" / "Windspitzen"), weil der
Ortsvergleich seit S2 (#1373) zwar eine Verbindung zum zentralen
Wetterkatalog kennt (`metric_id`/`aggregation` je Eintrag), den Namen selbst
aber weiterhin redaktionell getippt ausgibt statt aus dieser Verbindung
abzuleiten. Diese Spec führt den Anzeigenamen aller vier serverseitig
gespeisten Compare-Auswahlflächen (Grundauswahl, Reihenfolge, 3-Tages-
Ausblick, Wertebereiche) auf **eine Quelle** zurück — den zentralen
Wetterkatalog (`metric_catalog.py`) — und macht die Auswertung
(Maximum/Minimum/Mittel/Summe) zu einem eigenen, daneben angezeigten
Element statt eines Teils des Namens.

Etappe S2-Nachzügler von Epic #1372 (Kind von Dach-Epic #1374), Ticket #1401
Scheibe A1. Löst die Katalog-seitige Kursänderung gegenüber der S2-Entscheidung
„Compare-Namen bleiben kuratiert" ab (s. Abschnitt „ADR-Bezug").

## Source

- **File:** `src/output/renderers/compare_metric_catalog.py`
- **Identifier:** `COMPARE_METRIC_CATALOG`, `get_compare_metric_catalog()`
- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition.label_de`, `get_metric()`

> Schicht-Hinweis: Backend-Änderung ist Python-Core (`src/app/`,
> `src/output/renderers/`), keine Go-Beteiligung (reine Weiterleitung in
> `internal/router/router.go:122,155`, unverändert). Die vier betroffenen
> Frontend-Flächen liegen ausschließlich unter
> `frontend/src/lib/components/shared/` (SvelteKit, geteilte Bausteine
> Trip/Compare) — siehe Dependencies.

## Estimated Scope

**LoC-Risiko vorab:** Die realistische Summe liegt über dem 250-Zeilen-Deckel
(s. Rechenweg unten, Gesamt ~260-330 Netto-Zeilen). Das ist eine ehrliche
Neubewertung gegenüber der Grobschätzung im Kontext-Dokument (~120-180 Zeilen),
die nur den Backend-Teil erfasste — die vier Frontend-Flächen sind laut
Auftrag zwingender Teil von A1 (sonst zeigt die Grundauswahl "Temperatur"
zweimal ununterscheidbar, ein neuer Bug statt einer Behebung). Empfehlung s.
Ende dieses Abschnitts.

### Rechenweg

**Backend:**

| Datei | Änderung | Netto-Zeilen |
|---|---|---|
| `src/app/metric_catalog.py` | `sunshine.label_de`: "Sonnenschein" → "Sonnenstunden" (einzige nötige Registeränderung — die anderen 7 Namensentscheidungen gewinnen bereits mit dem heutigen Registerwert, s. Namensentscheidungen-Tabelle) | ~1 |
| `src/output/renderers/compare_metric_catalog.py` | 26 Literale verlieren das getippte `"label"`-Feld (Ableitung statt Tippen); neue `_AGGREGATION_LABELS`-Übersetzungstabelle (4 Einträge: max/min/avg/sum); `get_compare_metric_catalog()` berechnet `label` über `get_metric(entry["metric_id"]).label_de` (KeyError = sichtbares Scheitern, kein Auffangen) und ergänzt `aggregation_label`; Docstring-Update | ~70-100 |
| `tests/tdd/test_compare_metric_catalog_endpoint.py` | `EXPECTED_METRIC_ORIGIN`-Fixture: 8 Label-Werte aktualisiert (7 wechseln auf den Registerwert, s. Tabelle); neue Tests: Ableitung == `label_de` für alle 26, `aggregation_label`-Mapping korrekt, sichtbares Scheitern bei unbekannter `metric_id` (Vorbild: `duplicate_metric_aggregation_pairs(entries=...)`, injizierbare Testkopie statt Mutation des echten Katalogs) | ~60-90 |

**Backend-Summe:** ~130-190 Netto-Zeilen (deckt sich mit der ursprünglichen
Grobschätzung).

**Frontend (vier serverseitig gespeiste Flächen):**

| Datei | Änderung | Netto-Zeilen |
|---|---|---|
| `frontend/src/lib/types.ts` | `CompareMetricCatalogEntry.aggregation_label?: string` (additiv, analog `aggregation`); `MetricEntry.aggregation_label?: string` (analog vorhandenem `col_label?`) | ~4 |
| `frontend/.../weather-metrics-tab/compareMetricSelection.ts` | `CompareSelectionEntry.aggregation_label?: string`; bedingtes Durchreichen in `toCompareSelectionEntries()` (analog `metric_id`/`aggregation`) | ~6 |
| `frontend/.../corridor-editor/compareMetricCatalogLoader.ts` | `CompareMetricDef` bekommt `aggregationLabel?: string`; `buildCompareMetricDefs()` reicht es durch | ~6 |
| `frontend/.../corridor-editor/corridorEditorState.ts` | `CorridorRowState.aggregationLabel?: string`; Durchreichen in den drei Stellen, die eine Zeile aus einem `CompareMetricDef` bauen (`buildCorridorState`, `addRow`, `buildComparePrefillRows`) | ~10-15 |
| `frontend/.../weather-metrics-tab/WeatherV2Reihenfolge.svelte` | Ein neues, bedingtes `<span class="aggregation-badge">` neben dem bestehenden `col-badge`-Muster (Zeile ~74-76), plus CSS-Klasse — **geteilte Komponente, keine Compare-eigene Kopie** | ~12-18 |
| `frontend/.../WeatherMetricsTab.svelte` | Grundauswahl-Zeile (vergleich-Zweig, ~Zeile 878): zweites `<span>` für die Auswertung; `compareMetricById`-Map (~Zeile 769-773) reicht `aggregation_label` mit durch | ~8-10 |
| `frontend/.../CompareOutlookLayoutControls.svelte` | eigene Checkbox-Liste (~Zeile 103): zweites `<span>`; `outlookMetricById`-Map (~Zeile 63-67) reicht `aggregation_label` mit durch | ~8-10 |
| `frontend/.../corridor-editor/CorridorEditor.svelte` + `CorridorEditorMobile.svelte` | Zeile + Pool-Button: zweites `<span>` neben `row.label`/`m.label`, je Datei | ~14-18 |
| Frontend-Test-Anpassungen | `compareMetricSelection.test.ts`, `compareMetricCatalogParity.test.ts`, `corridorEditorState.test.ts` — Fixtures um `aggregation_label` ergänzt, neue Assertions für Durchreichen; keine der acht Label-String-Änderungen wird hier geprüft (das ist Backend-Zuständigkeit) | ~30-45 |

**Frontend-Summe:** ~100-135 Netto-Zeilen.

**Gesamt:** ~230-325 Netto-Zeilen (Mitte ~275) — **überschreitet den 250-Zeilen-
Deckel voraussichtlich**, auch bei vorsichtiger Schätzung.

### Empfehlung

Ein Split würde bedeuten: Backend liefert zuerst (Namen ändern sich am
Endpoint), Frontend folgt separat. Dazwischen zeigt die Grundauswahl
"Temperatur" zweimal ohne Unterscheidung — ein **neuer, selbstverschuldeter
Bug**, live auf Staging und potenziell auf Prod (Deploy läuft autonom aus
jeder Session, s. CLAUDE.md „Post-Push-Workflow"). Ein Split ist daher
sachlich schlechter als eine Lieferung über dem Deckel.

**Empfehlung:** `workflow.py set-field loc_limit_override 350` für diesen
Workflow, mit PO-Zustimmung (kein Override ohne Erlaubnis). Fällt die
tatsächliche Umsetzung kleiner aus als die obere Schätzung (z. B. weil die
Badge-Erweiterung in `WeatherV2Reihenfolge.svelte` ein vorhandenes Feld
wiederverwenden kann statt ein neues zu definieren), wird der Override nicht
gebraucht — das ist eine unabhängige Implementierungsentscheidung.

- **Files:** 12 mit Codeänderung (3 Backend inkl. Test, 9 Frontend inkl. 3
  Tests), keine Go-Datei.
- **Effort:** medium (Backend-Ableitung ist klein, die vier Frontend-Flächen
  sind viele kleine, gleichartige Änderungen an geteilten Bausteinen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`get_metric`, `label_de`) | READ (+1 Zeile Edit) | Zielquelle des Anzeigenamens; `get_metric()` wirft `KeyError`, wenn eine `metric_id` nicht existiert — genau der Mechanismus für „kein stilles Verwerfen" |
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | `label` wird abgeleitet statt getippt; `aggregation_label` wird neues Ausgabefeld |
| `api/routers/compare.py` | CHECK | reicht `get_compare_metric_catalog()` unverändert durch (kein Feldfilter, geprüft am Code, S2-Erkenntnis gilt weiter) — keine Codeänderung erwartet |
| `frontend/src/lib/types.ts` | MODIFY | `CompareMetricCatalogEntry`/`MetricEntry` um `aggregation_label?` ergänzen |
| `frontend/.../weather-metrics-tab/compareMetricSelection.ts` | MODIFY | `CompareSelectionEntry` + `toCompareSelectionEntries()` reichen `aggregation_label` durch |
| `frontend/.../corridor-editor/compareMetricCatalogLoader.ts` | MODIFY | `buildCompareMetricDefs()` reicht `aggregation_label` in `CompareMetricDef` durch |
| `frontend/.../corridor-editor/corridorEditorState.ts` | MODIFY | `CorridorRowState` führt `aggregationLabel` durch die drei Zeilen-Bau-Funktionen |
| `frontend/.../weather-metrics-tab/WeatherV2Reihenfolge.svelte` | MODIFY | geteilte Komponente (Trip UND Compare) bekommt ein optionales Auswertungs-Badge — wirkt nur, wo das Feld gesetzt ist (Compare), Trip unverändert |
| `frontend/.../WeatherMetricsTab.svelte` | MODIFY | Grundauswahl (vergleich-Zweig) + `compareMetricById`-Map |
| `frontend/.../CompareOutlookLayoutControls.svelte` | MODIFY | eigene Checkbox-Liste + `outlookMetricById`-Map |
| `frontend/.../corridor-editor/CorridorEditor.svelte` + `CorridorEditorMobile.svelte` | MODIFY | Zeile + Pool-Button zeigen die Auswertung als zweites Element |
| `tests/tdd/test_compare_metric_catalog_endpoint.py` | MODIFY | Fixture-Update (8 Labels) + 3 neue Kern-Tests |
| `frontend/.../weather-metrics-tab/__tests__/compareMetricSelection.test.ts`, `corridor-editor/__tests__/compareMetricCatalogParity.test.ts`, `corridor-editor/corridorEditorState.test.ts` | MODIFY | Fixtures um `aggregation_label` ergänzt, Durchreich-Assertions |
| `src/output/renderers/email/compare_html.py`, `src/output/renderers/comparison.py` | READ-ONLY (Beweis) | importieren `compare_metric_catalog.py` **nicht** (geprüft, kein Treffer) — Mail-Renderer bleibt von dieser Lieferung strukturell unberührt |
| `src/output/renderers/compare_metric_ids.py` (`resolve_enabled_metrics`) | READ-ONLY (Beweis) | löst ausschließlich über `key` (z. B. `temp_max_c`) auf, nie über `.label` — Namensänderung kann die Mail-Auflösung nicht brechen |

**Nicht Teil dieser Lieferung:** `docs/adr/`, `.claude/hooks/email_spec_validator.py`,
`src/output/renderers/email/compare_html.py` (`CV2_METRICS`/`HOUR_METRICS`),
`frontend/.../compareHourlyMetricDefs.ts`, `AlertMetricLevelTable.svelte`,
`ROUTE_METRIC_DEFS` — s. Known Limitations.

## Implementation Details

**1. Register-Korrektur (einzige Zeile in `metric_catalog.py`):**
`sunshine.label_de` wechselt von "Sonnenschein" auf "Sonnenstunden" — die
Compare-Formulierung gewinnt hier, weil sie die Einheit (h) korrekt benennt.
Alle sieben übrigen Namensentscheidungen (s. Tabelle unten) gewinnen bereits
mit dem heutigen Registerwert — dort ändert sich nur die Compare-Anzeige
(weil sie jetzt vom Register abgeleitet wird), nicht das Register selbst.

**2. Ableitung in `compare_metric_catalog.py`:** Die 26 Dict-Literale
verlieren ihr getipptes `"label"`. `get_compare_metric_catalog()` berechnet
`label = get_metric(entry["metric_id"]).label_de` je Eintrag zur Aufrufzeit
(nicht am Modul-Import, damit ein späterer Registerfehler den Server nicht
am Start crasht, sondern der Endpoint-Aufruf sichtbar mit `KeyError`
scheitert — Fehlerbehandlung/HTTP-Status ist Implementierungsdetail, nicht
Teil dieser Spec). Eine neue, kleine Übersetzungstabelle
`_AGGREGATION_LABELS = {"max": "Maximum", "min": "Minimum", "avg": "Mittel",
"sum": "Summe"}` liefert `aggregation_label`. `key` bleibt unverändert
(Rückwärtskompatibilität, ungetestet durch diese Lieferung nicht berührt).

**3. Testbarkeit des „kein stilles Verwerfen"-Pfads:** Nach dem Vorbild von
`duplicate_metric_aggregation_pairs(entries: list[dict] | None = None)`
(bereits in derselben Datei) bekommt die Ableitungsfunktion einen optionalen
`entries`-Parameter, damit ein Test eine kaputte Kopie (unbekannte
`metric_id`) injizieren kann, ohne den echten Katalog zu mutieren oder zu
monkeypatchen.

**4. Frontend-Durchreichung:** `aggregation_label` folgt exakt dem
Durchreichungs-Muster, das S2 Scheibe A für `metric_id`/`aggregation`
etabliert hat (`toCompareSelectionEntries()`, bedingtes Spreaden, keine
erfundenen `undefined`-Schlüssel — sonst bricht der strikte `deepEqual` aus
#1350). Dasselbe Muster gilt für `buildCompareMetricDefs()`
(compareMetricCatalogLoader.ts) Richtung Wertebereiche-Editor.

**5. Anzeige als getrenntes Element:** `WeatherV2Reihenfolge.svelte` zeigt
bereits ein Badge-Muster (`m.col_label`, Zeile ~74-76) neben Name und
Einheit — die Auswertung bekommt ein gleichartiges, eigenes Badge
(`m.aggregation_label`), kein neuer Darstellungsmechanismus. Die Grundauswahl
(Checkbox-Liste in `WeatherMetricsTab.svelte` vergleich-Zweig und in
`CompareOutlookLayoutControls.svelte`) sowie die Wertebereiche-Zeile/-
Pool-Buttons (`CorridorEditor.svelte`/`CorridorEditorMobile.svelte`) bekommen
je ein zusätzliches `<span>` für die Auswertung neben dem Namen — visuell
zwei Elemente, nicht ein zusammengesetzter String (Purpose: „Auswertung
erscheint als eigenes Element daneben, nicht mehr darin").

**6. Geteilte Bausteine bleiben geteilt:** Alle fünf berührten Svelte-Dateien
liegen unter `frontend/src/lib/components/shared/` und werden bereits von
Trip UND Compare genutzt (`WeatherV2Reihenfolge.svelte`) bzw. sind
Compare-eigene, aber strukturell zum Trip-Pendant analoge Bausteine
(`CompareOutlookLayoutControls.svelte`, `CorridorEditor.svelte`). Das neue
Feld ist überall optional und wirkt nur, wo es gesetzt ist — der Trip-Zweig
bleibt unverändert, weil `metric_catalog`-gespeiste `MetricEntry`-Objekte
(`/api/metrics`) `aggregation_label` schlicht nicht setzen (Trip-Metriken
haben ohnehin nur eine feste Aggregation je Anzeige, keine Mehrdeutigkeit).

## Expected Behavior

- **Input:** Ein Nutzer öffnet die Wetter-Metriken- oder Wertebereiche-Ansicht
  eines Ortsvergleichs (Hub oder Anlege-Seite).
- **Output:** `GET /api/compare/metrics` liefert für jeden der 26 Einträge
  weiterhin `key` und `label` (jetzt vom zentralen Katalog abgeleitet, ohne
  Auswertung im Namen) sowie zusätzlich `aggregation_label` (deutsch
  beschriftet: Maximum/Minimum/Mittel/Summe). Grundauswahl, Reihenfolge,
  3-Tages-Ausblick und Wertebereiche zeigen Name und Auswertung als zwei
  optisch getrennte Elemente in derselben Zeile/demselben Button. Für
  dieselbe Größe erscheint überall derselbe Name (z. B. "Temperatur" für
  sowohl `temp_max_c` als auch `temp_min_c`, unterschieden nur noch durch das
  Auswertungs-Element).
- **Side effects:** Referenziert ein Compare-Katalogeintrag künftig eine
  `metric_id`, die im zentralen Katalog nicht (mehr) existiert, scheitert der
  Aufruf sichtbar (Exception mit der fehlenden ID im Text), statt eine
  leere oder erfundene Bezeichnung anzuzeigen. Die Vergleichs-Mail (HTML,
  Klartext, Telegram, SMS) zeigt für dieselbe Auswahl exakt dieselben Zeilen
  wie vor dieser Umstellung — sie liest ihre Spaltenköpfe über ein anderes,
  von dieser Lieferung nicht berührtes Vokabular (`CV2_METRICS`/
  `HOUR_METRICS`, s. Known Limitations).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet die Metrik-Grundauswahl im Ortsvergleich
  (Hub oder Anlege-Seite) / When er die Liste durchsieht / Then zeigt jede
  Zeile denselben Namen wie die entsprechende Größe im Trip-Editor (z. B.
  "Temperatur" statt "Temperatur max"/"Temp max"), und die Auswertung
  (Maximum/Minimum/Mittel/Summe) steht als eigenes, optisch abgesetztes
  Element daneben.
  - Test: `tests/frontend/.../weatherMetricsTabVergleichLabels.test.ts` (Node,
    neu) — rendert die Grundauswahl-Zeilen aus einer Beispiel-Katalogantwort
    und prüft, dass Name und Auswertungs-Element als zwei getrennte Werte
    vorliegen, nicht als ein zusammengesetzter String.

- **AC-2:** Given ein Nutzer öffnet die Grundauswahl / When zwei Einträge
  derselben Wettergröße mit unterschiedlicher Auswertung existieren (z. B.
  "Temperatur max" und "Temperatur min") / Then bleiben beide als getrennte,
  einzeln wähl- und unterscheidbare Zeilen erhalten — der gemeinsame Name
  macht sie nicht ununterscheidbar.
  - Test: Kern-Test gegen `GET /api/compare/metrics` — beide Einträge tragen
    denselben `label`-Wert, aber unterschiedliche `key`/`aggregation_label`
    (Erweiterung von `tests/tdd/test_compare_metric_catalog_endpoint.py`).

- **AC-3:** Given ein bestehender Vergleich mit einer gespeicherten,
  nicht-leeren Metrik-Auswahl / When vor und nach dieser Umstellung je eine
  Mail erzeugt wird / Then zeigen beide Mails dieselben Zeilen in derselben
  Reihenfolge mit denselben Werten — in HTML **und** Klartext gleichermaßen.
  **Einzige zugelassene Abweichung** (PO-Entscheidung 2026-07-27, s. Changelog):
  die Spaltenüberschriften des 3-Tages-Ausblicks tragen künftig den
  Registernamen; die Auswertung wird dort nur ergänzt, wenn dieselbe Größe
  mehrfach gewählt ist (sonst stünden zwei gleich beschriftete Spalten
  nebeneinander). Übersichtstabelle und Stundentabelle bleiben unverändert.
  - Test: echte Staging-Mail vor/nach über das Test-Postfach
    (`tests/live/test_compare_mail_unaffected_by_label_source.py`, Marker
    `live`/`email`/`staging`), ausgewertete Struktur verglichen (HTML- und
    Klartext-Teil, nicht nur der Klartext-blinde-Fleck-anfällige HTML-Teil).

- **AC-4:** Given eine künftige Compare-Katalogzeile referenziert eine
  `metric_id`, die im zentralen Wetterkatalog nicht existiert / When der
  Katalog abgefragt wird / Then scheitert der Aufruf sichtbar (Exception mit
  der fehlenden ID im Fehlertext), statt eine leere oder erfundene
  Bezeichnung zurückzugeben.
  - Test: `tests/tdd/test_compare_metric_catalog_endpoint.py::test_unknown_metric_id_fails_visibly`
    (neu) — injiziert eine Testkopie mit unbekannter `metric_id` (kein
    Monkeypatch des echten Katalogs) und prüft, dass eine Exception mit der
    ID im Text geworfen wird.

- **AC-5:** Given ein Vergleich mit einer bereits gespeicherten Metrik-Auswahl
  im alten String-Format oder im neuen `{metric_id, aggregation}`-Format aus
  #1373 Scheibe B / When der Editor die Auswahl lädt und ohne weitere
  Änderung speichert / Then bleibt die Auswahl unverändert erhalten — diese
  Umstellung ändert weder Lese- noch Schreibverhalten der Persistenz.
  - Test: Erweiterung von
    `frontend/src/lib/components/compare/__tests__/compareActiveMetricsStorageFormat.test.ts`
    um beide Formate gegen den neuen (umbenannten) `label`-Wert — Auflösung
    bleibt über `key`, nicht über `label`.

- **AC-6:** Given ein Nutzer öffnet den Wertebereiche-Editor (Schwellen) im
  Ortsvergleich (Desktop oder Mobile) / When er die Metrik-Pool-Liste oder
  eine bereits hinzugefügte Zeile ansieht / Then zeigt sie denselben Namen
  wie Grundauswahl und Trip-Editor, mit der Auswertung als eigenem Element.
  - Test: Erweiterung von
    `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts`
    — Zeilen- und Pool-Objekte tragen `label` und `aggregationLabel` getrennt.

## Namensentscheidungen (Freigabe mit dieser Spec)

Diese acht Wettergrößen weichen heute zwischen Ortsvergleich und zentralem
Register redaktionell voneinander ab. Mit dieser Spec entscheidet der PO,
welche Formulierung künftig überall gilt:

| Größe | heute Vergleich | heute Register | Entscheidung | Begründung |
|---|---|---|---|---|
| `wind`/max | Windspitzen | Wind | **Wind** | „Spitzen" sind sachlich die Böen (eigene Größe) — die heutige Vergleichs-Benennung ist irreführend; Register gewinnt |
| `sunshine`/sum | Sonnenstunden | Sonnenschein | **Sonnenstunden** | benennt die Einheit (h) korrekt; Vergleich gewinnt, Register wird angepasst |
| `cape`/max | Gewitter-Energie (CAPE) | Gewitterenergie (CAPE) | **Gewitterenergie (CAPE)** | Rechtschreibung; Register gewinnt |
| `wind_chill`/min | Gefühlte Temp. min | Gefühlte Temperatur | **Gefühlte Temperatur** | Auswertung steht künftig daneben, die Abkürzung entfällt; Register gewinnt |
| `wind_chill`/max | Gefühlte Temp. max | Gefühlte Temperatur | **Gefühlte Temperatur** | dito |
| `cloud_low`/avg | Wolken tief | Tiefe Wolken | **Tiefe Wolken** | grammatisch korrekt; Register gewinnt |
| `cloud_mid`/avg | Wolken mittel | Mittelhohe Wolken | **Mittelhohe Wolken** | dito |
| `cloud_high`/avg | Wolken hoch | Hohe Wolken | **Hohe Wolken** | dito |

Mit „go"/„freigabe" zu dieser Spec bestätigt der PO diese acht
Namensentscheidungen ausdrücklich.

## Known Limitations

- **`col_label` (Tabellenkopf-Kurzformen) bleibt unverändert englisch** —
  PO-Entscheidung 2026-07-27, bestätigt #849/#862. Jede Änderung dort zöge
  über `email/helpers.py:465-473`, `trip_report.py:503-524`,
  `email/html.py:1334`, `email/plain.py:293` sofort in die Trip-Mail; nicht
  Teil dieser Lieferung.
- **Mail-Renderer-Tabellen `CV2_METRICS`/`HOUR_METRICS`**
  (`src/output/renderers/email/compare_html.py:206-276`) bleiben unverändert
  — eigene Lieferung Scheibe A2 (dort auch: 15 CV2-Zeilen ohne `metric_id`
  nachtragen, Vollständigkeits-Wächter).
- **`.claude/hooks/email_spec_validator.py` wird nicht angefasst** — eigenes
  Gate-Ticket mit Gold-Standard-Test, muss vor A2 geliefert sein, nicht vor
  A1 (A1 ändert keine Mail-Spaltenköpfe, der Validator bleibt unberührt
  wirksam).
- **Hartkodierte Frontend-Listen** Stundenverlauf
  (`compareHourlyMetricDefs.ts`) und Alarme (`AlertMetricLevelTable.svelte`)
  bleiben unverändert — Scheibe B.
- **Trip-Wertebereiche (`ROUTE_METRIC_DEFS`)** bleiben unverändert — bereits
  als #1384 in Etappe S6 terminiert; diese Lieferung ändert nur den
  Compare-Zweig des Wertebereiche-Editors (`CompareMetricDef`, nicht
  `RouteMetricDef`).
- **Kein neues Persistenzformat, keine Migration** — `display_config.active_metrics`
  bleibt exakt wie in #1373 Scheibe B beschrieben; `key` (der Auswahl-
  Schlüssel) ändert sich in dieser Lieferung nicht.
- **Widersprüchliches SMS-Kürzel (`snow_depth`)** und **divergente
  Alarm-Namenskopie** (`alertMetricLabels.ts` vs. `AlertMetricLevelTable.svelte`)
  sind bekannte Nebenbefunde aus der Analyse, gehören aber nicht zu dieser
  Lieferung (Sammel-Issue #1199 bzw. Scheibe B).

## ADR-Bezug

Diese Spec löst die in `docs/specs/modules/feat_1373_s2_ein_katalog.md:341-356`
dokumentierte S2-Entscheidung „Compare-Namen bleiben kuratiert" ab: die
Messung von S2 hatte drei Gründe genannt, warum eine mechanische Ableitung
ausscheidet — (1) redaktionelle Abweichung der Labels, (2) Wertebereiche/
`kind`/`ordinalLabels` existieren nur Compare-seitig, (3) drei Größen ohne
Tages-Auswertungsfeld (#1392). A1 widerlegt **nur Grund (1)**: die acht
abweichenden Labels werden hiermit explizit aufgelöst (Tabelle oben), der
Rest der Ableitung bleibt auf `label_de` beschränkt — Wertebereiche, `kind`
und Ordinal-Labels bleiben weiterhin kuratiert in `compare_metric_catalog.py`
(Gründe 2/3 gelten unverändert fort, keine Vollableitung).

**Empfehlung: kein neues ADR.** Es existiert kein formales ADR-Dokument zu
dieser Entscheidung (die S2-Spec selbst führte „ADR-Nr.: keine"); die
Kursänderung betrifft eine redaktionelle Namenskonvention, keine der in
CLAUDE.md genannten ADR-Auslöser-Kategorien (Kanäle, Provider, Datenmodell/
Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie). Diese Spec
zusammen mit dem Freigabe-Changelog der S2-Spec dokumentiert die Abweichung
ausreichend nachvollziehbar. Unsicherheit: falls der PO die Namenskonvention
selbst als grundsätzliche Leitlinie (analog Design-Leitprinzipien) verstanden
wissen will, wäre ein schlankes ADR trotzdem vertretbar — das ist eine
Ermessensfrage, keine technische Notwendigkeit.

## Changelog

- 2026-07-27 (nach GREEN): **AC-3 präzisiert.** Die Annahme „A1 fasst die Mail
  gar nicht an" war unvollständig: `src/output/renderers/compare_outlook_metric_ids.py:98`
  liest den Anzeigenamen der Ausblick-Spalten **direkt** aus
  `COMPARE_METRIC_CATALOG` (nicht über `compare_html.py`, deshalb in der
  Vor-Analyse nicht gefunden). Nach dem Entfernen des getippten Labels bricht
  der Auflöser dort. Umgestellt auf `get_compare_metric_catalog()`; die
  Auswertung wird nur bei mehrfach gewählter Größe angehängt, damit die dort
  dokumentierte Vorgabe „keine zwei gleich beschrifteten Spalten" bestehen
  bleibt. **PO-Entscheidung 2026-07-27: mitziehen lassen** — der Ausblick ist
  eine der vier Flächen, die diese Lieferung vereinheitlicht; ihn künstlich
  auf dem alten Namen zu halten würde genau die Divergenz erzeugen, die #1401
  beseitigt. Änderungsbudget im selben Zug auf 600 Zeilen angehoben
  (PO-Freigabe; Produktivcode-Anteil 154 Zeilen, Rest Nachweise).
- 2026-07-27: Initial spec created (Fix #1401 Scheibe A1, Etappe
  S2-Nachzügler von Epic #1372/Dach #1374). Umfangsschätzung inkl. der vier
  Frontend-Flächen deutlich über die reine Backend-Grobschätzung aus dem
  Kontext-Dokument hinaus neu berechnet (~230-325 statt ~120-180 Zeilen) —
  LoC-Override-Empfehlung dokumentiert, kein Split empfohlen (Split würde
  eine sichtbar schlechtere Zwischen-Ausprägung produzieren: doppelte
  ununterscheidbare Namen).
