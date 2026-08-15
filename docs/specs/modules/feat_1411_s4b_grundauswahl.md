---
entity_id: feat_1411_s4b_grundauswahl
type: feature
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [frontend, compare-editor, metric-catalog, epic-1372, issue-1411]
---

<!-- Issue #1411 — Epic #1372 Scheibe S4b Scheibe 1, Dach #1374 -->

# Ortsvergleich-Grundauswahl: eine Zeile je Wettergröße mit Mengen-Wahl (Issue #1411)

## Approval

- [x] Approved — PO Henning, 2026-07-29 („go" auf die neun ACs in Alltagssprache vorgelegt)

## Purpose

Im Ortsvergleich zeigt die Karte „Wetter-Metriken" heute 26 flache Zeilen —
je eine pro Kombination aus Wettergröße und Auswertung. „Temperatur" und
„gefühlte Temperatur" erscheinen dadurch als je zwei getrennte Zeilen
(Höchst-/Tiefstwert), obwohl es sich fachlich um eine Größe handelt. Diese
Lieferung führt sie zu **einer** Zeile je Größe zusammen (24 statt 26): Bietet
der Katalog für eine Größe mehrere Auswertungen an, bekommt die Zeile **je
Auswertung ein unabhängig ankreuzbares Kästchen** — Höchst- und Tiefstwert
dürfen gleichzeitig aktiv sein. Größen mit nur einer Auswertung (22 von 24)
bleiben eine einfache Checkbox-Zeile ohne zusätzliches Bedienelement. Am
Speicherformat, an der Reihenfolge-Liste darunter und an der versendeten Mail
ändert sich nichts.

## Source

> **Schicht-Hinweis:** Reines Frontend. Kein Go-Eingriff (`display_config`
> bleibt opake Map, `internal/model/trip.go`), kein Python-Eingriff (der
> Katalog-Endpoint `GET /api/compare/metrics` liefert bereits alle nötigen
> Felder — `metric_id`, `aggregation`, `aggregation_label`, `label`, `key`).

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:900-921`
  (Block `context === 'vergleich'`, Card „Wetter-Metriken", Abschnitt
  `grundauswahl`) — heutige flache Checkbox-Liste, wird durch gruppierte
  Zeilen ersetzt
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte`
  — bestehender geteilter Baustein aus #1357 (Trip-Seite, Einzelwahl über
  sich ausschließende Möglichkeiten inkl. synthetischer „Spanne"), bekommt
  einen zweiten Darstellungs-/Auswahlmodus für die Mengen-Wahl des Vergleichs
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/compareAggregationGrouping.ts`
  (NEU) — Pure Function, gruppiert die flache `compareCatalog`-Antwort nach
  `metric_id`
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:31-35`
  — Kommentar korrigieren: kein neuer Abschnitt `'auswertungen'` für den
  Vergleich (s. „Bewusste Abweichung von der Vorbereitung" unten)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts`,
  `compareMetricSelection.ts` — unverändert, nur als Beleg, dass Toggle-Pfad
  und Speicherformat von dieser Änderung nicht berührt werden

## Estimated Scope

- **LoC:** eigene Schätzung **~250–280 LoC** (Kernumfang ohne Doku/Spec),
  davon ca. 170–190 LoC Kern (Grouping-Funktion + Komponenten-Erweiterung +
  Markup-Ersatz in `WeatherMetricsTab.svelte` + Kommentarkorrektur) und ca.
  80–90 LoC Testanpassungen an den drei bestehenden E2E-Spezifikationen.
  Reine Unit-Tests für die neue Grouping-Funktion zählen nach
  Projektkonvention nicht gegen die Kern-Grenze. Das 250er-Limit ist damit
  eng bis leicht überschritten — die Analyse nannte 180–310 LoC, diese Spec
  grenzt auf die wahrscheinlichere obere Hälfte ein, weil die drei
  bestehenden E2E-Dateien strukturell umgeschrieben werden müssen (s. u.),
  nicht nur in Werten angepasst. **Kein Override wird hier beantragt** —
  entscheidet sich am echten Diff in der Implementierungsphase.
- **Files:** 1 neue Datei (Grouping-Funktion) + 3 geänderte Frontend-Dateien
  (Komponente, Markup, Sections-Kommentar) + 3 bestehende E2E-Spezifikationen
  (umgeschrieben) + mind. 1 neue Unit-Testdatei.
- **Effort:** medium (ein geteilter Baustein bekommt einen echten
  Verhaltensunterschied als Parameter, plus drei strukturell brechende
  Bestands-E2E-Tests).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AggregationMetricRow.svelte` (#1357) | component | Bestehender geteilter Baustein — wird um einen Mengen-Wahl-Modus erweitert statt einer Compare-Zweitkomponente (Trip/Compare-Teilungs-Invariante, CLAUDE.md) |
| `GET /api/compare/metrics` → `compare_metric_catalog.py::get_compare_metric_catalog()` | API (unberührt) | Liefert bereits `metric_id`/`aggregation`/`aggregation_label`/`label`/`key` je der 26 Zeilen — kein neues Feld nötig |
| `compareMetricOrder.ts::toggleCompareMetricKeyFromState()` | function (unberührt) | Bleibt der einzige Umschalt-Pfad; jedes Kästchen ruft ihn weiterhin mit dem jeweiligen einzelnen Katalog-`key` auf |
| `WeatherV2Reihenfolge.svelte` (#1359) | component (unberührt) | Reihenfolge-Liste bleibt bei getrennten Zeilen je `key` — bewusst nicht Teil dieser Lieferung |
| `weatherMetricsTabSections.ts` | module | Kommentar zu `'auswertungen'`/#1411 muss korrigiert werden — die Lösung fügt keinen neuen Abschnitt hinzu |
| `trip_aggregation_selection.md` (#1357) | Spec (Referenz, unberührt) | Beschreibt die Trip-seitige Einzelwahl mit Spanne-Logik — bewusst NICHT das Vorbild für die Auswahl-Semantik hier (Mengen-Wahl statt Einzelwahl, s. Implementation Details) |
| `fix-1350-compare-metric-select.staging.spec.ts`, `compare-active-metrics-format.staging.spec.ts`, `compare-editor-slice4.spec.ts` | Test (Bestand) | Gehen von „eine Zeile pro Katalog-`key`" aus (`weather-metrics-vergleich-row-{key}`) — müssen auf „eine Zeile pro `metric_id`, Kästchen je Option" umgeschrieben werden, nicht nur in Werten angepasst |

## Implementation Details

### 1. Gruppierung: flacher Katalog → 24 Zeilen

`compareAggregationGrouping.ts` (neu) exportiert eine reine Funktion, die die
26 flachen `compareCatalog`-Einträge nach `metric_id` gruppiert, in
Fundreihenfolge (erstes Auftreten bestimmt Zeilenposition):

```
groupCompareCatalog(catalog: CompareSelectionEntry[]): {
  metric_id: string;
  label: string;
  options: { key: string; aggregation: string; aggregation_label: string }[];
}[]
```

Ergebnis: 24 Gruppen, 22 davon mit genau einer Option, `temperature` und
`wind_chill` mit je zwei. Die Optionsliste einer Gruppe enthält **nur**, was
der Katalog tatsächlich für diese `metric_id` liefert — kein fest verdrahtetes
„Höchst-/Tiefstwert"-Paar. Bietet der Katalog künftig für eine Größe eine
Auswertung nicht (mehr) an, verschwindet das zugehörige Kästchen von selbst,
ohne Sonderfall-Code (Invariante: kein stilles Verwerfen von etwas, das
angeboten wird, aber auch keine Erfindung von etwas, das nicht angeboten
wird).

### 2. `AggregationMetricRow.svelte`: neuer Modus statt neuer Komponente

Der Baustein bekommt einen zusätzlichen Parameter (Name/Signatur ist
Implementierungsdetail, z. B. `mode: 'single' | 'multiple' = 'single'`):

- `mode='single'` (Default, Trip-Verhalten unverändert): genau ein
  `selectedChoiceId` aktiv, Klick auf eine Option macht sie exklusiv aktiv —
  bitidentisch zum heutigen `AggregationMetricRow`, keine Verhaltensänderung
  für die Trip-Seite.
- `mode='multiple'` (neu, Vergleich): mehrere Optionen gleichzeitig aktiv
  (`selectedChoiceIds: string[]` statt `selectedChoiceId: string | null`),
  Klick auf eine Option toggelt **nur diese eine** unabhängig von den
  anderen — kein Ausschluss, keine „Spanne"-Zusammenfassung.

Die Wahlmöglichkeiten (`choices`) im Vergleichs-Fall sind die rohen
Katalog-Optionen einer Gruppe (`{id: key, label: aggregation_label}`) — nicht
`aggregationChoices()` aus `aggregationSelection.ts` (die erzeugt die
Trip-spezifische synthetische „Spanne"-Möglichkeit, die der Vergleich nicht
braucht, s. Analyse).

**Struktureller Hinweis für die Implementierung:** `AggregationMetricRow`
rendert heute `<tr>`/`<td>` für eine Tabellenzeile (Einsatzort: Card „05 —
Auswertungen", `<table class="threshold-table">`). Die Vergleichs-Grundauswahl
nutzt bislang `<label>`-Zeilen in einer `<div>`-Liste. Empfehlung: die
Grundauswahl-Liste auf dieselbe `<table class="threshold-table">`-Machform
umstellen, die an anderer Stelle in derselben Datei bereits für Card-Inhalte
verwendet wird (Konsistenz statt Parallelstruktur) — sowohl einfache
Einzel-Optionen-Zeilen als auch Mehrfach-Optionen-Zeilen werden dann als
`<tr>` gerendert. Einfache Zeilen (22 von 24 Größen) behalten ihr heutiges
Aussehen (Checkbox + Label + nicht-interaktives Auswertungs-Label), sie
laufen NICHT durch die erweiterte `AggregationMetricRow`, sondern bleiben die
bestehende einfache Zeilenform (kein wirkungsloses Bedienelement,
Attrappen-Verbot).

### 3. `WeatherMetricsTab.svelte:900-921`: Markup-Ersatz

Der `{#each compareCatalog as entry}`-Block wird durch `{#each
groupCompareCatalog(compareCatalog) as group}` ersetzt:

- `group.options.length === 1` → einfache Checkbox-Zeile wie heute,
  Test-ID `weather-metrics-vergleich-row-{metric_id}` (statt bisher
  `-{key}` — für Einzel-Optionen-Gruppen ist `key === options[0].key`,
  praktisch nur eine Umbenennung der Test-ID-Quelle), `checked` weiterhin
  aus `materializedActiveMetricKeys.includes(options[0].key)`, `onchange`
  weiterhin `toggleCompareMetric(options[0].key)`.
- `group.options.length > 1` → Zeile mit Label + N Kästchen (via
  `AggregationMetricRow` `mode='multiple'`), Zeilen-Test-ID
  `weather-metrics-vergleich-row-{metric_id}`, je Kästchen
  `weather-metrics-vergleich-option-{metric_id}-{aggregation}` (z. B.
  `weather-metrics-vergleich-option-temperature-max`). Jedes Kästchen ruft
  bei Klick unverändert `toggleCompareMetric(option.key)` auf — derselbe
  Katalog-`key` (`temp_max_c`/`temp_min_c`), derselbe Mechanismus wie heute.

### 4. Bewusste Abweichung von der Vorbereitung in `weatherMetricsTabSections.ts`

`weatherMetricsTabSections.ts:31-35` trägt aktuell den Kommentar:

> „Issue #1357: 'auswertungen' … ist vorerst ebenfalls route-exklusiv … Er
> zieht mit #1411 nach."

Das war eine Vorab-Vermutung aus der #1357-Spec, **keine PO-Festlegung**. Die
tatsächliche PO-Entscheidung für #1411 (2026-07-29) ist eine andere: die
Mengen-Wahl entsteht **innerhalb** des bestehenden Abschnitts `'grundauswahl'`
(beide Kontexte bereits enthalten), **kein** neuer Abschnitt `'auswertungen'`
für `context='vergleich'`. `ROUTE_ONLY_SECTIONS` bleibt unverändert
(`'auswertungen'` bleibt darin, weiterhin ausschließlich für die
Trip-Segmented-Control-Karte „05 — Auswertungen" reserviert — die bleibt vom
Vergleich unberührt). Der Kommentar an `ROUTE_ONLY_SECTIONS` wird korrigiert,
damit er nicht als offene/vergessene Verknüpfung zu #1411 gelesen wird.

> **Korrektur 2026-08-15 (Issue #1728 Scheibe 2):** Der Abschnitt
> „05 — Auswertungen" und mit ihm der Eintrag `'auswertungen'` in
> `ROUTE_ONLY_SECTIONS` sind seither ersatzlos entfernt — nicht mehr nur
> route-exklusiv „reserviert", sondern in keinem Kontext mehr vorhanden.
> Diese Abweichungs-Begründung bleibt als historische Entscheidung korrekt
> (Compare bekam bewusst keinen eigenen Auswertungen-Abschnitt), ist aber
> keine Ist-Beschreibung von `weatherMetricsTabSections.ts` mehr. Details:
> `docs/specs/modules/feat_1728_s2_editor.md`.

## Expected Behavior

- **Input:** dieselbe Katalogantwort wie heute (`GET /api/compare/metrics`,
  26 Zeilen), dieselbe gespeicherte Auswahl (`display_config.active_metrics`,
  Format `{metric_id, aggregation}` seit #1373 — **bereits im Zielformat,
  keine Migration nötig**, s. AC-6).
- **Output:** die Grundauswahl-Card zeigt 24 Zeilen statt 26; bei Temperatur
  und gefühlter Temperatur sind Höchst- und Tiefstwert unabhängig
  an-/abwählbar. `wiz.activeMetricKeys`, die Reihenfolge-Liste und die
  versendete Mail (HTML wie Klartext) bleiben unverändert.
- **Side effects:** keine neuen API-Calls, kein neuer Persistenz-Pfad —
  reine Darstellungs-Umstellung derselben Daten.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet im Ortsvergleich den Reiter
  Wetter-Metriken / When die Grundauswahl-Karte lädt / Then sieht er für
  jede der 24 Wettergrößen genau eine Zeile — nicht mehr 26 Zeilen mit
  getrennten „Temperatur"- und „gefühlte Temperatur"-Einträgen für
  Höchst-/Tiefstwert.
  - Test: Grouping-Funktion liefert 24 Gruppen aus dem echten 26-Zeilen-Katalog; Darstellungstest zählt 24 Zeilen im DOM.

- **AC-2:** Given die Zeile „Temperatur" bietet zwei Kästchen (Höchstwert,
  Tiefstwert) / When der Nutzer beide anhakt / Then sind beide gleichzeitig
  aktiv — das Anhaken des einen deaktiviert das andere nicht.
  - Test: beide Kästchen nacheinander anklicken, danach beide als aktiv geprüft (kein exklusives Verhalten wie beim Trip).

- **AC-3:** Given der Nutzer hat Höchst- und Tiefstwert der Temperatur aktiv
  / When er das Tiefstwert-Kästchen wieder abwählt / Then bleibt das
  Höchstwert-Kästchen unverändert aktiv — ein Kästchen wirkt nie auf das
  andere.
  - Test: Ausgangszustand beide aktiv, Tiefstwert abwählen, Höchstwert bleibt angehakt geprüft.

- **AC-4:** Given eine Wettergröße mit nur einer im Katalog angebotenen
  Auswertung (z. B. Wind, Niederschlag — 22 von 24 Größen) / When der Nutzer
  die Grundauswahl betrachtet / Then erscheint dafür kein zusätzliches
  Auswertungs-Bedienelement, nur die gewohnte Checkbox zum An-/Abwählen der
  Größe.
  - Test: Grouping-Funktion liefert für diese Größen eine Options-Liste der Länge 1; Darstellungstest prüft, dass keine Mehrfach-Kästchen-Zeile gerendert wird.

- **AC-5:** Given ein Nutzer aktiviert bei der Temperatur ausschließlich den
  Tiefstwert (Höchstwert bleibt aus) und speichert / When er den Vergleich
  danach neu lädt / Then ist weiterhin ausschließlich der Tiefstwert aktiv —
  kein Datenverlust und kein fälschliches Mit-Aktivieren des Höchstwerts.
  - Test: Speichern-Laden-Roundtrip über den echten Persistenzpfad, Assert auf identische Auswahl nach Reload.

- **AC-6:** Given ein bestehender Vergleich, dessen `display_config.active_metrics`
  bereits im Format `{metric_id, aggregation}` gespeichert ist (Regelfall
  seit #1373) / When die Grundauswahl-Karte nach dieser Änderung lädt / Then
  wird die bestehende Auswahl unverändert korrekt angezeigt — **keine
  Migration ist nötig**, weil das Speicherformat bereits dem Zielformat
  entspricht.
  - Test: Fixture mit Neuformat-Eintrag laden, Assert auf korrekt angehakte Kästchen ohne jede Schreiboperation.

- **AC-7:** Given ein Vergleich mit Temperatur Höchst- **und** Tiefstwert
  aktiv / When die Vergleichs-Mail gerendert und tatsächlich zugestellt wird
  / Then zeigen sowohl der HTML- als auch der Klartext-Teil derselben Mail
  weiterhin zwei getrennte Spalten für Höchst- und Tiefstwert, in
  unveränderter Reihenfolge — Zahl für Zahl identisch zu einer Mail vor
  dieser Änderung.
  - Test: echte Staging-Mail vor/nach der Änderung senden und über `email_spec_validator.py` sowie manuellen Klartext-Vergleich gegenprüfen (der Pflicht-Validator liest nur HTML — der Klartext-Teil braucht die zusätzliche manuelle Prüfung, bekannter blinder Fleck).

- **AC-8:** Given Temperatur Höchst- und Tiefstwert sind beide aktiv / When
  der Nutzer die Reihenfolge-Liste unterhalb der Grundauswahl betrachtet /
  Then zeigt sie weiterhin zwei getrennte, unabhängig sortierbare Zeilen
  „Temperatur / Maximum" und „Temperatur / Minimum" — die Zusammenfassung in
  der Grundauswahl-Karte ändert nichts an der Reihenfolge-Liste.
  - Test: DOM-Test der Reihenfolge-Liste nach Aktivieren beider Kästchen, Assert auf zwei getrennte Zeilen.

- **AC-9:** Given der Reiter Wetter-Metriken im Ortsvergleich / When der
  Nutzer ihn öffnet / Then erscheint die Mengen-Wahl für Temperatur/gefühlte
  Temperatur innerhalb desselben Abschnitts wie die übrige Grundauswahl —
  es entsteht **kein** separater dritter Abschnitt „Auswertungen" für den
  Vergleich (abweichend von einer früheren Vorab-Vermutung im Code-Kommentar
  von `weatherMetricsTabSections.ts`, die mit dieser Lieferung korrigiert
  wird).
  - Test: Sections-Funktionstest prüft, dass `weatherMetricsTabSections('vergleich')` weiterhin keinen Eintrag `'auswertungen'` enthält.

## Known Limitations

- **Reihenfolge-Liste bleibt zweigeteilt (bewusst, s. AC-8):** eine
  Grundauswahl-Zeile korrespondiert nach dieser Änderung mit bis zu zwei
  Reihenfolge-Zeilen — das ist ein gewollter Bruch in der 1:1-Beziehung
  zwischen beiden Karten, keine Inkonsistenz, die behoben werden muss. Eine
  Zusammenführung der Reihenfolge-Liste wäre #1406-Scope und stünde im
  Widerspruch zu „zwei Spalten gleichzeitig in der Mail".
- **#1406 (drei Kombi-Elemente, Ausblick-Speicherfeld,
  `compareHourlyMetricDefs.ts`/`compareMetricMapping.ts`) ist vollständig
  außerhalb dieses Umfangs.**
- **Kein Migrationsschritt:** das Speicherformat war bereits vor dieser
  Lieferung im Zielformat (`{metric_id, aggregation}`, seit #1373) — AC-6
  macht das explizit prüfbar, statt es stillschweigend vorauszusetzen.
- **`AggregationMetricRow.svelte` trägt nach dieser Lieferung zwei
  Auswahl-Semantiken (Einzelwahl/Mengenwahl) hinter einem Modus-Parameter.**
  Das ist die bewusste Umsetzung der Trip/Compare-Teilungs-Invariante
  (CLAUDE.md) statt einer Compare-Zweitkomponente — akzeptierter Trade-off:
  die Komponente wird dadurch etwas komplexer, aber es entsteht kein
  Duplikat mit eigenem Pflegeaufwand.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster — Erweiterung eines
  bestehenden geteilten Bausteins um einen Parameter, keine neue Komponente,
  kein neuer Persistenz-Pfad, kein neuer Kanal, keine Provider-/
  Auth-/Editor-Paradigmenänderung.

## Test-Plan

Kern-Schicht (deterministisch), Testdateien nach Verhalten benannt (nicht
nach Issue-Nummer):

| AC | Testfall |
|----|----------|
| AC-1, AC-4 | `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/compareAggregationGrouping.test.ts` — 24 Gruppen aus dem 26-Zeilen-Katalog, Einzel- vs. Mehrfach-Optionen-Gruppen |
| AC-2, AC-3 | `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/aggregation_row_multi_select.test.ts` (oder Erweiterung von `aggregation_selection.test.ts`) — unabhängiges Toggeln im `mode='multiple'`, Einzelwahl im `mode='single'` bleibt bitidentisch (Regressionsschutz Trip-Seite) |
| AC-5, AC-6 | `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/compareMetricSelection.test.ts` (erweitert) — Roundtrip mit Neuformat-Fixture |
| AC-7 | Staging: `email_spec_validator.py` (Pflicht-Dispatch für Orts-Vergleich-Mails) + manueller Klartext-Vergleich derselben Mail |
| AC-8 | DOM-Test in bestehender Reihenfolge-Suite oder E2E-Erweiterung von `compare-editor-slice4.spec.ts` |
| AC-9 | `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts` (falls noch nicht vorhanden, sonst erweitert) |

**Bestehende E2E-Spezifikationen — UMSCHREIBEN, nicht nur Werte anpassen**
(gehen strukturell von „eine Zeile pro Katalog-`key`", bis zu 26 Zeilen,
aus):

- `frontend/e2e/fix-1350-compare-metric-select.staging.spec.ts` — Zeilenzahl-
  Assertion (`toHaveCount(catalog.metrics.length)`) auf 24 Gruppen umstellen,
  Toggle-Test auf `temp_max_c` über das neue Options-Test-ID
  (`weather-metrics-vergleich-option-temperature-max`) statt der alten
  Zeilen-Checkbox ansprechen.
- `frontend/e2e/compare-active-metrics-format.staging.spec.ts` — Row-Locator-
  Helper (`weather-metrics-vergleich-row-{key}`) auf Gruppen-/Options-
  Test-IDs umstellen.
- `frontend/e2e/compare-editor-slice4.spec.ts` — Checkbox-Selektor
  (`.cm-desktop [data-testid^="weather-metrics-vergleich-row-"] input`) auf
  die neue verschachtelte Struktur (Zeile ODER Zeile+Optionen) anpassen.

**Renderer-Commit-Gate:** entfällt hier — es werden keine
Mail-Inhalts-Dateien geändert (reine Frontend-Darstellung, Renderer/
`display_config`-Auflösung unberührt).

## Changelog

- 2026-07-29: Initial spec created — Issue #1411, Epic #1372 Scheibe S4b
  Scheibe 1, Dach #1374; PO-Entscheidung vom 2026-07-29 (Mengen-Wahl statt
  Einzelwahl, Erweiterung von `AggregationMetricRow.svelte` statt
  Zweitkomponente, Verbleib im Abschnitt `grundauswahl`).
