---
entity_id: feat_1406a_ausblick_geteiltes_element
type: feature
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [frontend, compare-editor, metric-catalog, epic-1372, issue-1406]
---

<!-- Issue #1406 Scheibe A — Epic #1372 S4b Scheibe 2, Dach #1374 -->

# Ortsvergleich-Ausblick: Auswahl-Block auf das gruppierte Muster von #1411 heben (Issue #1406 Scheibe A)

## Approval

- [x] Approved — PO Henning, 2026-07-30 (Freigabe auf die acht ACs in Alltagssprache)

## Purpose

Der 3-Tages-Ausblick des Ortsvergleichs (`CompareOutlookLayoutControls.svelte`)
besteht aus zwei Blöcken: einer Auswahl-Liste oben und einer Reihenfolge-Liste
darunter. Die Reihenfolge-Liste ist **bereits heute** derselbe geteilte
Baustein (`WeatherV2Reihenfolge`), den Trip und Übersichts-Vergleich nutzen —
sie ist **nicht** Teil dieser Lieferung. Die Auswahl-Liste darüber zeigt noch
das alte, ungruppierte Muster von vor #1411: 26 flache Zeilen, „Temperatur"
darunter zweimal (Höchst-/Tiefstwert getrennt). Diese Lieferung stellt **nur**
diesen Auswahl-Block auf dasselbe gruppierte Muster um, das die
Vergleichs-Übersicht seit #1411 zeigt: eine Zeile je Wettergröße (24 statt
26), bei mehreren Auswertungen mit unabhängig ankreuzbaren Kästchen statt
zwei getrennter Zeilen.

## ⚠️ Nicht-Umfang (bewusste Abgrenzung gegen den Auftragstext)

Der Auftragstext von #1406 liest sich, als fehle dem Ausblick das
Sortier-/Zuordnungs-Element komplett. Das ist **nicht der Fall**:
`WeatherV2Reihenfolge` ist seit `8fc4d210` (2026-07-27, Issue #1361 Befund
2/#1368) bereits 1:1 derselbe Baustein wie bei Trip und Übersicht — Ziehgriff,
Positionsnummern, `aggregation_label`-Badge, „Aus"-Button funktionieren bis in
die Mail. Diese Scheibe rührt **keine Zeile** in
`CompareOutlookLayoutControls.svelte:116-136` an. Ein Umbau dieses bereits
korrekten Teils wäre reines Regressionsrisiko an einer funktionierenden
Fläche — AC-5 macht das als Regressionsschutz explizit prüfbar.

## Source

> **Schicht-Hinweis:** Reines Frontend. Kein Go-Eingriff (`display_config`
> bleibt opake Map), kein Python-Eingriff (der Katalog-Endpoint
> `GET /api/compare/metrics` liefert die nötigen Felder bereits, unverändert
> seit #1373/#1401) und kein Renderer-Eingriff (s. „Mail unberührt" unten).

- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte:96-114`
  (Auswahl-Block — flache `{#each catalog as entry}`-Liste, wird durch die
  gruppierte Form ersetzt)
- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte:116-136`
  (Reihenfolge-Block, `WeatherV2Reihenfolge` — **UNVERÄNDERT**, Nicht-Umfang
  s. o.)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte`
  — bestehender geteilter Baustein (aus #1357, `mode='multiple'` seit #1411),
  bekommt einen optionalen `testidPrefix`-Parameter (s. Implementation
  Details 2)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/compareAggregationGrouping.ts`
  — bestehende reine Funktion `groupCompareCatalog()`, **keine Änderung**,
  bereits generisch für jeden flachen Compare-Katalog nutzbar

## Estimated Scope

- **LoC:** ca. **100–160** (Kernumfang ohne Doku/Spec) — deutlich unter dem
  250-LoC-Kernbudget. Kein Override wird beantragt.
- **Files:** 2 geänderte Frontend-Dateien (`CompareOutlookLayoutControls.svelte`,
  `AggregationMetricRow.svelte`) + 1 neue Testdatei (AST-Struktur-Nachweis).
- **Effort:** low — Wiederverwendung zweier bestehender, bereits produktiver
  Bausteine (`groupCompareCatalog`, `AggregationMetricRow mode='multiple'`),
  keine neue Logik.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `groupCompareCatalog()` (`compareAggregationGrouping.ts`, #1411) | function (unberührt) | Gruppiert den flachen Compare-Katalog nach `metric_id` — identisch für Übersicht und Ausblick, kein zweiter Gruppierungs-Code |
| `AggregationMetricRow.svelte` `mode='multiple'` (#1411) | component (erweitert um `testidPrefix`) | Rendert die Mehrfach-Kästchen-Zeile; Übersicht nutzt sie bereits produktiv, der Ausblick wird ihr zweiter Aufrufer |
| `materializeOutlookMetricKeys()`, `toggleOutlookMetricKeyFromState()` (`compareMetricOrder.ts`) | function (unberührt) | Bleiben der einzige Materialisierungs-/Umschalt-Pfad; jedes Kästchen ruft ihn weiterhin mit dem jeweiligen einzelnen Katalog-`key` auf — Anzeigeform ändert daran nichts |
| `WeatherV2Reihenfolge.svelte` (#1359/#1368) | component (unberührt, Nicht-Umfang) | Reihenfolge-/„Aus"-Block bleibt exakt wie heute — s. Nicht-Umfang |
| `render_outlook_table`/`render_outlook_plain` (`src/output/renderers/email/outlook.py`) | Renderer (unberührt, ADR-0037) | Geteilter Ausblick-Renderer zwischen Trip und Vergleich; Trip ruft ihn ohne `metrics`-Parameter (`email/html.py:1189`, `email/plain.py:281`), Vergleich liest ausschließlich `display_config.outlook_metrics` über `resolve_outlook_metrics()` — diese Scheibe ändert an keiner Stelle, welche Python-Funktion mit welchen Argumenten aufgerufen wird |
| `tests/tdd/test_trip_outlook_parity.py` + `tests/fixtures/outlook_trip_parity/` | Test/Golden (unberührt) | Paritäts-Wächter zwischen Trip- und Vergleichs-Ausblick — bleibt grün, **wird nie angepasst**; ein rotes Golden heißt, die Trip-Mail wurde verändert, nicht dass das Golden falsch ist |
| `compareOutlookMetricSelection.test.ts` | Test (unberührt/erweitert) | Testet ausschließlich `buildComparePresetSavePayload`/`normalizeStoredActiveMetrics` — reine Funktionen auf `outlookMetricKeys`, unabhängig von der Markup-Form; liefert auch den deterministischen Roundtrip-Beleg für AC-6 |

## Implementation Details

### 1. Auswahl-Block: Markup-Ersatz (Zeilen 96–114)

Der `{#each catalog as entry}`-Block wird durch `{#each
groupCompareCatalog(catalog) as group (group.metric_id)}` ersetzt — analog
zum bereits produktiven Muster in `WeatherMetricsTab.svelte:918-948`:

- `group.options.length === 1` (22 von 24 Größen): einfache Checkbox-Zeile
  wie heute, Testid `compare-layout-outlook-metric-{group.metric_id}`
  (bisherige Test-ID-Quelle war `entry.metric` — für Einzel-Optionen-Gruppen
  gilt `group.options[0].key === entry.metric`, also praktisch nur eine
  Umbenennung der Quelle), `checked` weiterhin aus
  `isOutlookMetricActive(group.options[0].key)`, `onchange` weiterhin
  `makeOutlookMetricHandler(group.options[0].key)`.
- `group.options.length > 1` (Temperatur, gefühlte Temperatur): Zeile über
  `AggregationMetricRow mode="multiple"`, `options={group.options}`,
  `selectedChoiceIds={materializedOutlookKeys}`, `onToggle={(_mid, key) =>
  makeOutlookMetricHandler(key)()}` — derselbe Umschalt-Pfad wie heute, nur
  über den bestehenden Baustein statt Handinline-Checkbox aufgerufen.

`materializedOutlookKeys`, `isOutlookMetricActive`, `makeOutlookMetricHandler`
(Zeilen 47–57) bleiben **unverändert** — sie togglen bereits einzelne
Katalog-Keys, unabhängig vom Anzeigemuster.

### 2. `AggregationMetricRow.svelte`: optionaler `testidPrefix`

**Tech-Lead-Entscheidung (aufzunehmen):** `AggregationMetricRow` vergibt
heute hartkodierte Testids ohne Kontext-Präfix — `<tr
data-testid="aggregation-metric-row-{metricId}">` und je Kästchen
`data-testid="weather-metrics-vergleich-option-{metricId}-{aggregation}"`.
Setzt der Ausblick dieselbe Komponente für dieselbe Wettergröße
(„Temperatur") ein, während die Übersicht diese Gruppe auf derselben
Editor-Seite ebenfalls zeigt, entstehen **zwei** Elemente mit identischem
`data-testid` im selben DOM.

Die Komponente bekommt daher einen optionalen `testidPrefix`-Parameter
(~5–10 LoC):

- **Ohne Angabe (Default):** exakt die heutigen Testids
  (`aggregation-metric-row-{metricId}`,
  `weather-metrics-vergleich-option-{metricId}-{aggregation}`) — die
  Übersicht (bestehender Aufrufer, #1411) ändert sich dadurch **nicht**.
- **Mit Angabe** (z. B. `testidPrefix="compare-layout-outlook"`): Zeile und
  Kästchen tragen einen davon abgeleiteten, unterscheidbaren Testid (Form ist
  Implementierungsdetail, z. B. `{testidPrefix}-metric-row-{metricId}` /
  `{testidPrefix}-option-{metricId}-{aggregation}`) — konsistent mit der
  bestehenden `compare-layout-outlook-*`-Namensfamilie der übrigen
  Ausblick-Testids in derselben Datei.

**Begründung:** verhindert eine im Projekt bereits bekannte Testfalle
(doppelte `data-testid`, Behelf über `.first()`/`:visible`) von vornherein,
statt sie erst beim nächsten Playwright-Test zu entdecken. Kein
Nutzer-Effekt — reines Test-Tooling.

### 3. Reihenfolge-Block (Zeilen 116–136): keine Änderung

`WeatherV2Reihenfolge`-Aufruf, `handleOutlookDndReorder`, `onOutlookRemove`,
`outlookMetricById`, `noopOutlookMode` bleiben Zeile für Zeile wie heute.

## Expected Behavior

- **Input:** dieselbe Katalogantwort wie heute (`GET /api/compare/metrics`),
  dieselbe gespeicherte Auswahl (`display_config.outlook_metrics`, Format
  `[{metric_id, aggregation}]` seit #1373 — **keine Migration**).
- **Output:** der Auswahl-Block zeigt 24 statt 26 Zeilen; bei Temperatur und
  gefühlter Temperatur sind Höchst- und Tiefstwert unabhängig an-/abwählbar.
  `wiz.outlookMetricKeys`, die Reihenfolge-Liste und die versendete Mail
  (HTML wie Klartext, Trip wie Vergleich) bleiben unverändert.
- **Side effects:** keine neuen API-Calls, kein neuer Persistenz-Pfad — reine
  Darstellungs-Umstellung derselben Daten.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet im Ortsvergleich-Editor den
  3-Tages-Ausblick / When der Auswahl-Block darüber lädt / Then sieht er für
  jede der 24 Wettergrößen genau eine Zeile — nicht mehr 26 Zeilen mit
  getrennten „Temperatur"-Einträgen für Höchst- und Tiefstwert.
  - Test: neuer AST-Struktur-Test prüft, dass der Auswahl-Block über
    `groupCompareCatalog(catalog)` iteriert statt über den rohen `catalog`.

- **AC-2:** Given die Zeile „Temperatur" im Ausblick-Auswahl-Block bietet
  zwei Kästchen (Höchstwert, Tiefstwert) / When der Nutzer beide anhakt /
  Then sind beide gleichzeitig als Ausblick-Spalte aktiv — das Anhaken des
  einen deaktiviert das andere nicht.
  - Test: AST-Struktur-Test weist den `AggregationMetricRow
    mode="multiple"`-Zweig für Mehrfach-Optionen-Gruppen nach; das
    unabhängige Toggle-Verhalten selbst ist bereits durch die bestehenden
    #1411-Tests der Komponente bewiesen (`mode='multiple'` unverändert) und
    wird hier nicht erneut getestet.

- **AC-3:** Given eine Wettergröße mit nur einer im Katalog angebotenen
  Auswertung (22 von 24 Größen, z. B. Wind, Niederschlag) / When der Nutzer
  den Ausblick-Auswahl-Block betrachtet / Then erscheint dafür kein
  zusätzliches Auswertungs-Bedienelement, nur die gewohnte einzelne Checkbox.
  - Test: derselbe AST-Struktur-Test prüft, dass der Zweig für
    Einzel-Optionen-Gruppen weiterhin die einfache Checkbox-Zeile rendert
    (kein `AggregationMetricRow`-Aufruf für diese Gruppen).

- **AC-4:** Given ein Vergleich mit bereits gespeicherter Ausblick-Auswahl
  (z. B. nur Tiefstwert der Temperatur aktiv, Höchstwert aus) / When der
  Auswahl-Block nach dieser Änderung lädt / Then zeigt er exakt dieselbe
  Auswahl — kein Datenverlust und keine fälschliche Mit-Aktivierung durch den
  Wechsel der Bedienfläche.
  - Test: bestehender `compareOutlookMetricSelection.test.ts` (Pure-Function-
    Roundtrip auf `outlookMetricKeys`) bleibt unverändert grün, weil er
    markup-unabhängig ist; zusätzlich prüft der neue Struktur-Test, dass
    beide Zweige `checked`/`selectedChoiceIds` weiterhin aus
    `materializedOutlookKeys` ableiten (derselbe Ursprung wie heute).

- **AC-5:** Given der Ausblick-Auswahl-Block wurde auf das gruppierte Muster
  umgestellt / When der Nutzer im darunterliegenden Reihenfolge-Block eine
  Größe zieht oder über den „Aus"-Button entfernt / Then wirkt das exakt wie
  vor dieser Änderung — Reihenfolge-/„Aus"-Funktion, die bereits produktiv
  läuft (`8fc4d210`), wird durch den Umbau des Auswahl-Blocks nicht berührt.
  - Test: neuer Struktur-Test weist nach, dass der `WeatherV2Reihenfolge`-
    Aufruf (Zeilen 116–136: `primaryColumns`, `onRemove`, `onDndReorder`)
    im AST unverändert vorhanden ist — Regressionsschutz für die bereits
    funktionierende Fläche.

- **AC-6:** Given ein Vergleich mit aktivem 3-Tages-Ausblick und einer
  Ausblick-Auswahl inkl. Temperatur Höchst- **und** Tiefstwert / When die
  Vergleichs-Mail gerendert wird / Then zeigen HTML- und Klartext-Teil des
  Ausblick-Abschnitts weiterhin dieselben Spalten in derselben Reihenfolge,
  Zahl für Zahl identisch zu einer Mail vor dieser Änderung — reiner
  Frontend-Auswahl-Umbau ohne Renderer-Wirkung.
  - Test: **deterministischer Nachweisweg, kein echter Mailversand nötig**
    (Tech-Lead-Entscheidung, PO informiert, 2026-07-30). Begründung: die
    Scheibe berührt den Mail-Pfad nachweislich nicht — der Trip-Aufruf
    bleibt ohne `metrics`-Parameter, der Vergleichs-Pfad liest ausschließlich
    `display_config.outlook_metrics`, das diese Scheibe unverändert
    weiterschreibt; ein echter Versand kostet zudem Kontingent beim
    Wetterdienst, das derzeit knapp ist (#1329). Beleg: (a) Roundtrip-Test
    über den echten Speicherpfad zeigt, dass `display_config.outlook_metrics`
    bei gleicher Auswahl vor und nach der Änderung **zeichengleich** ist,
    und (b) `tests/tdd/test_trip_outlook_parity.py` bleibt gegen sein
    unverändertes Golden grün. **Bedingung:** weicht der gespeicherte Wert
    doch ab, ist AC-6 nicht mehr deterministisch belegbar — dann ist die
    Staging-Mail-Verifikation (echter Versand, `email_spec_validator.py`,
    plus manueller Klartext-Vergleich) nachzuholen, bevor „E2E bestanden"
    gesagt werden darf.

- **AC-7:** Given eine Trip-Mail (kein Ortsvergleich) mit 3-Tages-Ausblick /
  When sie nach dieser Änderung gerendert wird / Then ist sie unverändert —
  der Trip-Ausblick-Aufruf bleibt ohne `metrics`-Parameter, weil diese
  Scheibe ausschließlich die Compare-Auswahlfläche im Frontend ändert und
  keine Zeile in `src/output/renderers/` berührt.
  - Test: `tests/tdd/test_trip_outlook_parity.py` gegen das bestehende
    Golden bleibt grün, **ohne dass das Golden angepasst wird** — ein rotes
    Golden wäre der Beweis, dass diese Scheibe entgegen der Spec doch den
    Renderer-Pfad berührt hat.

- **AC-8:** Given Übersicht und Ausblick zeigen auf derselben
  Editor-Seite gleichzeitig eine Mehrfach-Optionen-Zeile für „Temperatur" /
  When beide Karten geladen sind / Then tragen die jeweiligen Zeilen- und
  Kästchen-Elemente unterscheidbare `data-testid`-Werte — kein doppeltes
  `data-testid` im DOM.
  - Test: Struktur-Test prüft, dass der Ausblick-Aufruf von
    `AggregationMetricRow` einen `testidPrefix` ungleich dem
    Übersichts-Default übergibt.

## Known Limitations

- **#1406 (weitere Kombi-Elemente, u. a. `compareHourlyMetricDefs.ts`/
  `compareMetricMapping.ts`) ist außerhalb dieses Umfangs.** Diese Spec
  deckt ausschließlich Scheibe A (Ausblick-Auswahl-Block) ab.
- **Reihenfolge-Liste bleibt zweigeteilt bei Mehrfach-Auswertungen** (analog
  #1411 AC-8, hier für den Ausblick): sind Höchst- und Tiefstwert der
  Temperatur beide aktiv, zeigt `WeatherV2Reihenfolge` weiterhin zwei
  getrennte, unabhängig sortierbare Zeilen. Das ist unverändertes
  Bestandsverhalten, keine neue Einschränkung dieser Lieferung.
- **`AggregationMetricRow.svelte` trägt nach dieser Lieferung drei
  Verwendungskontexte** (Trip-Einzelwahl via `mode='single'`,
  Übersichts-Mengenwahl und Ausblick-Mengenwahl via `mode='multiple'` +
  `testidPrefix`) hinter einem gemeinsamen Baustein. Akzeptierter
  Trade-off analog #1411: die Komponente wird dadurch etwas
  konfigurierbarer, aber es entsteht kein Duplikat mit eigenem
  Pflegeaufwand (Trip/Compare-Teilungs-Invariante, CLAUDE.md).
- **Renderer-Commit-Gate (#811) und `briefing_mail_validator.py` sind NICHT
  Teil des Pflichtumfangs** — diese Scheibe ändert keine der Gate-Dateien
  (`src/output/renderers/email/*.py`,
  `src/output/renderers/{trip_report,sms_trip,compact_summary}.py`,
  `src/output/renderers/alert/*.py`, `src/output/channels/email.py`); der
  echte Versand + `email_spec_validator.py` ist für AC-6 nur der
  Eskalationspfad, falls der deterministische Nachweis (s. AC-6) doch eine
  Abweichung zeigt.
- **AC-6 wird deterministisch (ohne Mailversand) geprüft** — bewusste
  Tech-Lead-Entscheidung, PO informiert (2026-07-30), zur Schonung des
  derzeit knappen Open-Meteo-Kontingents (#1329). Ein echter Versand ist
  nur fällig, wenn der Roundtrip-Test eine Abweichung im gespeicherten
  Wert zeigt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster — Wiederverwendung zweier
  bereits produktiver, geteilter Bausteine (`groupCompareCatalog`,
  `AggregationMetricRow mode='multiple'`) an einer dritten Einsatzstelle,
  plus ein optionaler Konfigurationsparameter an einem bestehenden
  Baustein. Kein neuer Persistenz-Pfad, kein neuer Kanal, keine
  Provider-/Auth-/Editor-Paradigmenänderung. ADR-0037 (geteilter
  Ausblick-Renderer) bleibt unberührt, da kein Renderer-Code geändert wird.

## Test-Plan

Kern-Schicht (deterministisch), Testdatei nach Verhalten benannt:

| AC | Testfall |
|----|----------|
| AC-1, AC-3 | neu: `frontend/src/lib/components/shared/__tests__/compare_outlook_metric_selection_structure.test.ts` (AST-Struktur, Vorbild `compare_hourly_layout_controls_structure.test.ts`) — Block iteriert `groupCompareCatalog(catalog)`, Einzel- vs. Mehrfach-Options-Zweig vorhanden |
| AC-2 | derselbe Struktur-Test — `AggregationMetricRow mode="multiple"`-Aufruf mit `options={group.options}` nachgewiesen; unabhängiges Toggle-Verhalten selbst bereits durch bestehende #1411-Tests der Komponente abgedeckt, hier nicht erneut geprüft |
| AC-4 | bestehender `frontend/src/lib/components/compare/__tests__/compareOutlookMetricSelection.test.ts` bleibt unverändert grün (kein Change nötig) + Struktur-Test prüft `checked`/`selectedChoiceIds`-Herkunft aus `materializedOutlookKeys` |
| AC-5 | derselbe Struktur-Test — `WeatherV2Reihenfolge`-Aufruf (Zeilen 116–136) im AST unverändert vorhanden |
| AC-6 | **deterministisch, kein Versand:** Roundtrip-Test `display_config.outlook_metrics` (zeichengleich vor/nach über den echten Speicherpfad, `compareOutlookMetricSelection.test.ts` erweitert oder neuer Test) + `tests/tdd/test_trip_outlook_parity.py` gegen unverändertes Golden. Staging-Mailversand (`email_spec_validator.py` + manueller Klartext-Vergleich) nur als Eskalationspfad, falls der Roundtrip-Test eine Abweichung zeigt (Kontingent-Schonung, #1329) |
| AC-7 | `tests/tdd/test_trip_outlook_parity.py` gegen unverändertes Golden `tests/fixtures/outlook_trip_parity/` — bleibt grün ohne Golden-Anpassung |
| AC-8 | derselbe Struktur-Test — Ausblick-Aufruf von `AggregationMetricRow` übergibt `testidPrefix` ungleich dem Übersichts-Default |

**Keine bestehende Test-/E2E-Datei bricht strukturell** — geprüft:
`compareOutlookMetricSelection.test.ts` testet ausschließlich Pure-Functions
auf `outlookMetricKeys`, unabhängig von der Markup-Form; kein
Playwright-Test in `frontend/e2e/` referenziert die heutigen
`compare-layout-outlook-metric-*`-Testids (Gegenprobe: keine Treffer beim
Durchsuchen von `frontend/e2e/` auf `compare-layout-outlook`).

**Renderer-Commit-Gate (#811):** entfällt — es werden keine
Mail-Inhalts-Dateien geändert (reine Frontend-Darstellung, `outlook.py`/
`resolve_outlook_metrics()` unberührt).

## Changelog

- 2026-07-30: Initial spec created — Issue #1406 Scheibe A, Epic #1372 S4b
  Scheibe 2, Dach #1374. Scope explizit auf den Auswahl-Block (Zeilen
  96–114) begrenzt; der bereits geteilte Reihenfolge-Block
  (`WeatherV2Reihenfolge`, Zeilen 116–136) ist ausdrücklich Nicht-Umfang.
- 2026-07-30: AC-6-Nachweisweg auf deterministisch (Roundtrip +
  Paritäts-Wächter) umgestellt, echter Mailversand nur als Eskalationspfad
  (Tech-Lead-Entscheidung, PO informiert — Kontingent-Schonung #1329).
  Approval-Vermerk ergänzt (PO Henning, 2026-07-30).
