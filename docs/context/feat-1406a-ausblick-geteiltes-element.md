# Kontext + Analyse: Issue #1406 Scheibe A — Ausblick auf das geteilte Kombi-Element

Stand: 2026-07-30, Commit-Basis `worktree-ws-overview-0725` (Arbeitskopie).
Epic #1372 S4b Scheibe 2 (nach #1411, S4b Scheibe 1, `74557cdf`, live).

## Auftrag laut Issue #1406 (letzter Kommentar, 2026-07-30 07:00)

> **A — Ausblick auf das geteilte Element.** `CompareOutlookLayoutControls.svelte`
> weicht demselben `WeatherV2Reihenfolge`, das Trip und Uebersicht nutzen.
> Frontend-only, Speicherformat unveraendert, **Mail unberuehrt**.

## Zentraler Befund: die Prämisse ist zur Hälfte bereits erfüllt

`CompareOutlookLayoutControls.svelte` (`frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`)
besteht heute aus **zwei** Blöcken:

1. **Zeilen 96–114:** eine eigene, flache Checkbox-Liste — `{#each catalog as entry}`
   über den **rohen** (ungruppierten) Compare-Katalog. Jeder `(metric_id, aggregation)`-
   Eintrag ist eine eigene Zeile, z. B. „Temperatur" taucht darin **zweimal** auf
   (`temp_max_c`, `temp_min_c`), mit `aggregation_label` als Zusatz-Badge daneben.
2. **Zeilen 120–136:** `WeatherV2Reihenfolge` — **derselbe** Baustein, den Trip
   (`WeatherMetricsTab.svelte:1116`) und die Vergleichs-Übersicht
   (`WeatherMetricsTab.svelte:975`) verwenden. Ziehgriff, Positionsnummern,
   `aggregation_label`-Badge, „Aus"-Button — 1:1 identisch eingebunden
   (`primaryColumns`, `metricById`, `onRemove`, `onDndReorder`, `onMode`).

**Der Sortier-/Zuordnungsteil (Block 2) ist also bereits der geteilte Baustein.**
Was fehlt, ist nicht „dasselbe Element bekommen", sondern: Block 1 zeigt noch das
**alte, ungruppierte** Auswahlmuster von vor #1411. Die Vergleichs-Übersicht hat
mit #1411 (`74557cdf`, live) genau dieses Muster bereits abgelöst
(`WeatherMetricsTab.svelte:918–948`): der Katalog wird über
`groupCompareCatalog()` (`weather-metrics-tab/compareAggregationGrouping.ts:38`)
nach `metric_id` gruppiert — eine Zeile je Wettergröße, bei mehreren Auswertungen
(aktuell nur `temperature`, `wind_chill`) über `AggregationMetricRow` mit
`mode="multiple"` unabhängig ankreuzbare Kästchen statt zwei getrennter Zeilen.

Die Outlook-eigene Auswahlliste zieht diese Vereinheitlichung **nicht** nach —
sie ist damit die letzte Stelle, die noch das Vor-#1411-Muster zeigt, obwohl sie
denselben Katalog (`compareCatalog`, GET `/api/compare/metrics`) als `catalog`-Prop
bereits erhält (`WeatherMetricsTab.svelte:1028`).

## 1. Delta Ist → Soll (mit Datei:Zeile)

| | Ist | Soll |
|---|---|---|
| Sortierung/Aus | `WeatherV2Reihenfolge` (`CompareOutlookLayoutControls.svelte:120–136`) | **unverändert** — bereits der geteilte Baustein |
| Auswahl (oben) | Flache `{#each catalog as entry}`-Liste, `<label class="outlook-metric-row">` (`CompareOutlookLayoutControls.svelte:100–114`), 24 Zeilen inkl. „Temperatur" zweimal | `{#each groupCompareCatalog(catalog) as group}` — dasselbe Muster wie `WeatherMetricsTab.svelte:918–948`: Einzelzeile bei einer Auswertung, `AggregationMetricRow mode="multiple"` bei mehreren |
| Handler | `makeOutlookMetricHandler`/`isOutlookMetricActive` bleiben — sie togglen bereits einzelne Katalog-Keys, unabhängig vom Anzeigemuster | **unverändert übernehmbar**, `onToggle`-Signatur von `AggregationMetricRow` passt direkt (`(metricId, key) => …`) |
| Speicherformat | `wiz.outlookMetricKeys` → `display_config.outlook_metrics` (`compareEditorSave.ts:139,341`) | **unverändert** — reine Anzeigeänderung, keine Feldänderung |

**Es gibt keine Fähigkeit der Compare-eigenen Fläche, die im geteilten `WeatherV2Reihenfolge`
fehlt** (Frage 1 aus dem Auftrag) — `WeatherV2Reihenfolge` kann grundsätzlich nur
anzeigen/sortieren/entfernen, was bereits in `primaryColumns` steht; das „Hinzufügen"
einer Größe zur Auswahl war noch nie seine Aufgabe, weder bei Trip noch bei der
Übersicht. Dafür ist strukturell immer eine zweite, davor liegende Auswahl-Komponente
zuständig (Trip: `WeatherV2Grundauswahl`; Übersicht: die `groupCompareCatalog`-Liste
in `WeatherMetricsTab.svelte`). Der Ausblick braucht dieselbe zweite Komponente —
er hat sie, nur noch im alten (Vor-#1411-)Muster. Kein fehlender Parameter an
`WeatherV2Reihenfolge` nötig.

## 2. Renderer-Pfad: berührt Scheibe A `email/outlook.py`? NEIN, belegt in beide Richtungen

**Warum nicht:** `render_outlook_table`/`build_outlook_row` (`src/output/renderers/email/outlook.py`)
sind laut ADR-0037 der **vollständig geteilte** Ausblick-Baustein zwischen Trip und
Vergleich. Trip ruft ihn ohne `metrics`-Parameter auf:
- `src/output/renderers/email/html.py:1189` — `render_outlook_table(multi_day_trend, show_acc=True)`, kein `metrics=`
- `src/output/renderers/email/plain.py:281` — `render_outlook_plain(multi_day_trend, show_acc=True)`, kein `metrics=`

→ Trip-Ausblick ist **gar nicht konfigurierbar** und bleibt es (kein Regressionsrisiko
für die Trip-Mail durch diese Scheibe).

Nur der Vergleichs-Pfad übergibt `metrics=outlook_metrics`:
`src/output/renderers/comparison.py:284` → `email/compare_html.py:936` (`render_outlook_table(..., metrics=outlook_metrics)`).
Die Auswahl kommt aus `resolve_outlook_metrics()` (`src/output/renderers/compare_outlook_metric_ids.py:45`),
die wiederum ausschließlich `display_config.outlook_metrics` liest — genau das Feld,
das Scheibe A **unverändert** weiterschreibt.

**Scheibe A ändert an keiner Stelle**, welche Python-Funktion mit welchen Argumenten
aufgerufen wird — nur, mit welcher Svelte-Komponente der Nutzer die Liste befüllt, die
am Ende in `outlookMetricKeys` landet. `resolve_outlook_metrics`/`outlook_columns`/
`render_outlook_table` bleiben unangetastet.

⇒ **Renderer-Commit-Gate (#811) und `briefing_mail_validator.py` gehören NICHT in den
Pflichtumfang** dieser Scheibe (keine der Gate-Dateien — `src/output/renderers/email/*.py`,
`src/output/renderers/{trip_report,sms_trip,compact_summary}.py`, `src/output/renderers/alert/*.py`,
`src/output/channels/email.py` — wird berührt). Der Paritäts-Wächter
`tests/tdd/test_trip_outlook_parity.py` bleibt grün, ohne dass diese Scheibe ihn
überhaupt anfassen muss.

## 3. Wirkt jedes Element? (Invariante 1)

**Ja, bereits heute — das ist kein Bug, den Scheibe A behebt.** Beleg der
Reihenfolge-Wirkung bis in die Mail (End-zu-Ende, ohne Neu-Messung, aus dem
Code nachvollzogen):

1. Ziehgeste → `handleOutlookDndReorder` setzt `wiz.outlookMetricKeys = newOrder` und
   löst `onOutlookCommit` aus (`CompareOutlookLayoutControls.svelte:78–81`).
2. Speichern → `toStoredActiveMetrics()` mapt **ohne Sortierung** (`.map`, keine
   Neuordnung: `compareMetricSelection.ts:127–137`) — Reihenfolge bleibt erhalten.
3. `resolve_outlook_metrics()` iteriert die Liste linear, **kein `set`**
   (`compare_outlook_metric_ids.py:59` ff., Kommentar bestätigt „kein set").
4. `outlook_columns()` baut die Spalten in exakt dieser Reihenfolge
   (`compare_outlook_metric_ids.py:90` ff.).

Die Reihenfolge ist also seit der Lieferung von #1361 Befund 2/#1368 (`8fc4d210`,
live 2026-07-27) bereits wirksam. Ebenso das „Aus" (entfernt aus derselben Liste,
gleicher Pfad). Es gibt in der heutigen Fläche **keine** Bedienelemente ohne Wirkung
und **keine** Wirkung ohne Bedienelement — der ADR-0037-Umbau hat das bereits
hergestellt. Scheibe A ist damit eine **Konsistenz-/Entdopplungs-Korrektur** der
Auswahl-Optik (altes vs. neues Gruppierungsmuster), keine Reparatur einer
Attrappe.

## 4. Datenerhalt beim Wechsel der Bedienfläche

**Kein Risiko, solange die Umsetzung reinen Anzeige-Tausch bleibt.** Die
Materialisierung (`materializeOutlookMetricKeys`, `weather-metrics-tab/compareMetricOrder.ts:39`)
und der Umschalt-Pfad (`toggleOutlookMetricKeyFromState`, ebd. `:44`) bleiben beim
Wechsel auf `groupCompareCatalog` unverändert — sie arbeiten auf einzelnen
Katalog-Keys (`entry.metric` / `group.options[].key`), nicht auf der
Darstellungsform. `groupCompareCatalog()` ist laut eigenem Vertrag „verlustfrei"
(`compareAggregationGrouping.ts:31`, AC-8 aus #1411): jeder Schlüssel taucht
danach genau einmal in genau einer Options-Liste auf. Ein Bestandsvergleich mit
gespeicherten `outlookMetricKeys` (z. B. `['temp_max_c']`) zeigt nach dem Wechsel
exakt dasselbe Kästchen als angehakt — nur eingebettet in eine gruppierte statt
einer flachen Zeile.

**Wo trotzdem hingesehen werden muss (Risiko, s. Abschnitt 5):** `AggregationMetricRow`
vergibt **hartkodierte** Testids ohne Kontext-Präfix (`aggregation-metric-row-{metricId}`,
`AggregationMetricRow.svelte:44`). Setzt Scheibe A dieselbe Komponente für die
Ausblick-Gruppe „Temperatur" ein, während die Übersicht dieselbe Gruppe auf
derselben Editor-Seite ebenfalls zeigt, entstehen **zwei** Elemente mit
`data-testid="aggregation-metric-row-temperature"` im selben DOM — kein Daten-,
aber ein Testbarkeits-Risiko (s. u.).

## 5. Scoping

**Frontend-only**, bestätigt in Abschnitt 2 (kein Python-Renderer-Pfad berührt,
kein Go-Eingriff — `outlook_metrics` liegt unter `display_config`, das
`handler/config_merge.go::mergeConfigMap` generisch merged).

**Betroffene Dateien (Schätzung):**

| Datei | Art | ~LoC |
|---|---|---|
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | Auswahl-Block ersetzen (Zeilen 96–114 raus, `groupCompareCatalog`+`AggregationMetricRow`-Block rein, analog `WeatherMetricsTab.svelte:918–948`) | ~40–60 |
| `frontend/src/lib/components/shared/weather-metrics-tab/AggregationMetricRow.svelte` | **nur falls** Testid-Kollision (Abschnitt 6) behoben wird — optionaler `testidPrefix`-Parameter | ~5–10 |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareAggregationGrouping.ts` | keine Änderung — bereits generisch nutzbar | 0 |
| `frontend/src/lib/components/compare/__tests__/compareOutlookMetricSelection.test.ts` | keine Änderung nötig — testet reine Save-Funktionen, unabhängig vom Auswahl-Markup | 0 |
| neu: `frontend/src/lib/components/shared/__tests__/compare_outlook_layout_controls_structure.test.ts` | AST-Struktur-Nachweis (Vorbild `compare_hourly_layout_controls_structure.test.ts`) | ~60–90 |

**Größenordnung: ca. 100–160 LoC**, deutlich unter dem 250-LoC-Kernbudget — auch
mit dem optionalen `AggregationMetricRow`-Parameter aus Abschnitt 6.

## 6. Nachweisbarkeit

**Kein bestehender Test bricht strukturell.** Geprüft:

- `frontend/src/lib/components/compare/__tests__/compareOutlookMetricSelection.test.ts`
  (AC-12/AC-13) testet ausschließlich `buildComparePresetSavePayload`/
  `normalizeStoredActiveMetrics` — reine Funktionen auf `outlookMetricKeys`,
  unabhängig von der Svelte-Markup-Form. Bleibt grün.
- `frontend/src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts`
  prüft nur die Sektions-Reihenfolge (`'ausblick'` als Eintrag), nicht das
  Innenleben der Komponente. Bleibt grün.
- Kein AST-/Struktur-Test verankert heute `compare-layout-outlook-metric-{entry.metric}`
  oder die flache `{#each catalog as entry}`-Form (Gegenprobe: `grep` auf
  `compare-layout-outlook` und `weather-metrics-ausblick` über `frontend/e2e/`
  liefert **keinen** Treffer — keine Playwright-Spezifikation hängt heute an
  diesen Testids).

**Was für die TDD-RED-Phase zu bauen ist** (Empfehlung, nicht Teil dieser Analyse):
ein AST-Struktur-Test nach dem Vorbild
`frontend/src/lib/components/shared/__tests__/compare_hourly_layout_controls_structure.test.ts`
(Svelte-Compiler-Parse, kein DOM/vitest im Repo) — Nachweis, dass
`CompareOutlookLayoutControls.svelte` über `groupCompareCatalog(...)` statt über
den rohen `catalog` iteriert, analog dem `{#each ALL_HOURLY_METRICS as metric}`-Nachweis
dort. Zusätzlich ein Roundtrip-Test, der eine Gruppe mit zwei Optionen
(„Temperatur max/min") durch die neue Markup-Form UND `buildComparePresetSavePayload`
schickt — Beleg, dass beide Kästchen weiterhin unabhängig in `outlookMetricKeys`
landen (Mengen-Wahl bleibt erhalten, analog #1411 AC-2/AC-3, aber für den
Ausblick statt die Übersicht).

## Offene Entscheidungen für den PO

**Eine echte Entscheidung, kein Blocker für den Start der Spec-Phase:**

Soll `AggregationMetricRow` einen optionalen `testidPrefix` (oder ähnlich)
bekommen, damit Übersicht und Ausblick auf derselben Editor-Seite **nicht**
denselben `data-testid="aggregation-metric-row-temperature"` doppelt ins DOM
schreiben?

- **Ohne Fix:** funktioniert im Betrieb identisch (kein Nutzer-Effekt), aber ein
  künftiger Playwright-Test, der `getByTestId('aggregation-metric-row-temperature')`
  verwendet, trifft zwei Elemente und muss auf `.first()`/`:visible` ausweichen
  (im Projekt bereits als akzeptiertes Muster bei doppelten Testids etabliert,
  s. `reference_dnd_e2e_scroll_and_flip_traps`/vergleichbare Fälle).
- **Mit Fix:** ein optionaler Parameter (~5–10 LoC), sauberer für künftige E2E-Tests,
  aber ein zusätzlicher, wenn auch kleiner Eingriff in eine bereits von Trip UND
  Übersicht genutzte geteilte Komponente.

**Empfehlung:** Fix mitnehmen (klein, verhindert eine bekannte Testfalle von
vornherein, statt sie erst bei der nächsten E2E-Schreibung erneut zu entdecken).
Kein Blocker — beide Varianten sind technisch tragfähig, die Entscheidung betrifft
nur Testkomfort, nicht Nutzerverhalten.

## Risiken (insbesondere Trip-Mail)

- **Trip-Mail: kein Risiko.** Belegt in Abschnitt 2 — der Trip-Aufruf von
  `render_outlook_table`/`render_outlook_plain` bleibt ohne `metrics`-Parameter,
  Scheibe A ändert keine Zeile in `src/output/renderers/`. Der Paritäts-Wächter
  `tests/tdd/test_trip_outlook_parity.py` bleibt unberührt und muss nicht neu
  laufen, um grün zu bleiben (er testet Code, den diese Scheibe nicht anfasst).
- **Testid-Kollision** bei Wiederverwendung von `AggregationMetricRow` für die
  Ausblick-Gruppe — s. „Offene Entscheidungen" oben. Betrifft nur Test-Tooling,
  nicht die Mail oder das Nutzerverhalten.
- **Verwechslungsgefahr in der Spec-Phase:** Der Auftragstext („bekommt dasselbe
  Sortier-/Zuordnungs-Element") liest sich, als fehle der Sortierbaustein noch
  komplett. Er ist aber bereits da (Abschnitt 1). Wird die Spec auf Basis des
  Auftragstexts statt des Code-Ist-Stands geschrieben, droht ein Umbau, der den
  bereits funktionierenden `WeatherV2Reihenfolge`-Teil unnötig anfasst und damit
  ein Regressionsrisiko für eine Fläche eröffnet, die heute schon korrekt live ist
  (`8fc4d210`, 2026-07-27). Die Spec sollte den Scope explizit auf den
  Auswahl-Block (Zeilen 96–114) eingrenzen.
