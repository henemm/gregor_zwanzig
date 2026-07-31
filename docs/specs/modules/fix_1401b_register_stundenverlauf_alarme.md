---
entity_id: fix_1401b_register_stundenverlauf_alarme
type: module
created: 2026-07-31
updated: 2026-07-31
status: implemented
version: "1.0"
tags: [compare, trip, metric-catalog, naming, alerts, frontend, trip-compare-sharing]
workflow: fix-1401b-register
---

# Fix #1401 Scheibe B: Stundenverlauf und Alarme lesen aus dem Namensregister

## Approval

- [x] Approved

## Purpose

Scheiben A1/A2a/A2b haben die serverseitigen Compare-Auswahlflächen und die
Vergleichs-Mail-Tabellen auf das zentrale Wetter-Namensregister
(`src/app/metric_catalog.py`) zurückgeführt. Zwei Frontend-Flächen tippen
ihre Anzeigenamen weiterhin selbst: der **Stundenverlauf** im
Ortsvergleich (`compareHourlyMetricDefs.ts`, 10 eigene Namen) und die
**Alarme-Tabelle** (`AlertMetricLevelTable.svelte`, 14 eigene Namen, mit
einer zweiten, teils divergenten Textquelle `alertMetricLabels.ts`). Diese
Spec führt beide Flächen auf das Register zurück und behebt dabei zwei
konkrete, an einer echten Divergenz nachgewiesene Beschriftungsfehler
(Temperaturänderung/Niederschlagsänderung, s. u.).

## Source

- **File:** `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts`
- **Identifier:** `ALL_HOURLY_METRICS`
- **File:** `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`
- **Identifier:** Template-Loop `{#each ALL_HOURLY_METRICS as metric}`
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `load()` (Zeile ~386-414), Vergleichs-`$effect`-Block
  (Zeile ~441-454)
- **File:** `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte`
- **Identifier:** lokale Konstante `METRIC_LABELS`
- **File:** `frontend/src/lib/utils/alertMetricLabels.ts`
- **Identifier:** `ALERT_METRIC_LABELS`

> Schicht-Hinweis: reine Frontend-Änderung (`frontend/src/lib/components/...`,
> `frontend/src/lib/utils/...`), keine Go-Beteiligung. `src/app/metric_catalog.py`
> wird ausschließlich lesend referenziert (Werte werden zitiert bzw. per
> bereits produktivem `GET /api/metrics`-Endpoint konsumiert), nicht
> verändert.

## Estimated Scope

- **LoC:** ~90-130 Produktivcode (2 neue Crosswalk-Dateien + 5 Änderungen an
  bestehenden Dateien) + ~150-260 Tests (5-6 Testdateien, neu oder erweitert)
  → **~240-390 Netto-Zeilen gesamt**. Liegt damit vermutlich über dem
  250-Zeilen-Deckel; realistische Einordnung erst nach TDD-RED möglich
  (Präzedenz A2b: Testvolumen wurde dort ebenfalls unterschätzt). Bei
  Überschreitung: `workflow.py set-field loc_limit_override` mit PO-Rückfrage,
  kein eigenmächtiger Split (Teil 1/Teil 2 hängen nicht ursächlich
  voneinander ab, ein Schnitt wäre aber ein neuer Zwischenzustand mit
  teilweise noch altem Vokabular — analog zur A2b-Begründung gegen
  Zwischenschnitte).
- **Files:** 7 Produktivdateien (2 neu, 5 geändert), 5-6 Testdateien (neu
  oder erweitert).
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`_METRICS`, `label_de`) | READ | Quelle der Ziel-Beschriftungen (zitiert, nicht importiert — Python/TS-Grenze) |
| `GET /api/metrics` (`MetricCatalog`, `MetricEntry.label`) | READ (Teil 1, Laufzeit) | Stundenverlauf bezieht Labels live über diesen bereits produktiven Endpoint |
| `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts::COMPARE_TO_ALERT_METRIC` | REFERENZ | Vorbild-Muster für einen kleinen, stabilen ID-Crosswalk zwischen zwei Namensräumen |
| `docs/specs/modules/fix_1401_a2_mailtabellen.md` (A2a/A2b) | REFERENZ | Vorbild für Kollisions-Umgang und Beleg-/Test-Stil dieser Scheibe |
| `docs/adr/0037-datengetriebener-ausblick-aus-metrik-katalog.md` | REFERENZ | Bestätigt das bereits etablierte Prinzip „eine Compare-Ausgabefläche, ein Katalog" — kein neuer ADR-Auslöser |

## Implementation Details

### Teil 1: Stundenverlauf (Vergleich) — Laufzeit-Katalog

**Design-Entscheidung:** Der Stundenverlauf bezieht seine Labels **live**
über `GET /api/metrics` (denselben Endpoint, den der Trip-Kontext bereits
lädt), nicht über hartkodierte Textduplikate. Grund: der Endpoint ist
bereits produktiv, statisch/read-only (kein `user_id`-Bezug), und
`WeatherMetricsTab.svelte` lädt ihn im Route-Kontext ohnehin schon.

1. **`frontend/src/lib/components/compare/compareHourlyMetricDefs.ts`** —
   `ALL_HOURLY_METRICS` verliert das getippte `label`-Feld je Eintrag
   (`key`/`defaultOff` bleiben). Die `HourlyMetricDef`-Interface-Doku wird
   entsprechend angepasst (kein `label` mehr Pflichtfeld für die
   Anzeige-Quelle — bleibt als Fallback-Text erhalten, s. Punkt 4).

2. **NEU: `frontend/src/lib/components/compare/compareHourlyCatalogIds.ts`**
   — Crosswalk-Tabelle (Muster: `compareMetricMapping.ts::COMPARE_TO_ALERT_METRIC`)
   FE-Hourly-Key → Katalog-`id`:

   ```
   temp_c        → temperature
   wind_chill_c  → wind_chill
   wind_kmh      → wind
   gust_kmh      → gust
   precip_mm     → precipitation
   uv_index      → uv_index
   thunder_level → thunder
   pop_pct       → rain_probability
   visibility_m  → visibility
   wind_dir_deg  → wind_direction
   ```

   Exportiert zusätzlich eine reine, testbare Funktion
   `resolveHourlyMetricLabel(key: string, catalog: MetricCatalog, fallback: string): string`
   — liefert `catalog[HOURLY_KEY_TO_CATALOG_ID[key]]?.label ?? fallback`.

3. **`frontend/src/lib/components/shared/WeatherMetricsTab.svelte`** —
   neuer `$effect`-Block (analog dem bestehenden Vergleichs-Guard
   Zeile ~441-454, gleiches Doppel-Fetch-Vermeidungsmuster), der im
   Vergleichs-Kontext `catalog` (bislang nur im Route-Zweig befüllt)
   zusätzlich per `api.get<MetricCatalog>('/api/metrics')` lädt — fail-soft
   (`.catch(() => {})`, `catalog` bleibt `{}` bei Fehler, kein neuer
   Fehlerzustand). Der veraltete Kommentar an Zeile ~798-800
   („`/api/metrics` wird im Vergleich nie geladen") wird korrigiert. Der
   `catalog`-State wird an `CompareHourlyLayoutControls` durchgereicht
   (neue Prop, s. Punkt 4).

   **Wichtig:** Der Stundenverlauf-Block (Zeile ~1013-1017) liegt bewusst
   **außerhalb** des `compareCatalogLoaded`/`compareCatalogError`-Gates
   (Kommentar Zeile ~1010-1012: „ein fehlgeschlagener Katalog-Abruf darf
   die Stundenverlauf-Steuerung nicht unerreichbar machen"). Der neue
   `/api/metrics`-Fetch für Teil 1 darf diese Erreichbarkeits-Garantie
   **nicht** einschränken — bei fehlendem/fehlgeschlagenem Katalog bleibt
   der Block sichtbar und bedienbar, nur mit Fallback-Labels (Punkt 4).

4. **`frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte`**
   — neue Prop `catalog?: MetricCatalog` (Default `{}`). Der bestehende
   `{#each ALL_HOURLY_METRICS as metric}`-Block löst das Label je Eintrag
   über `resolveHourlyMetricLabel(metric.key, catalog, metric.label)` auf.
   `metric.label` (aus `compareHourlyMetricDefs.ts`) bleibt als
   Übergangsnetz-Fallback erhalten (bewusste Entscheidung, s. AC-7), zeigt
   dabei bei `thunder_level`/`visibility_m` noch den alten Text — das ist
   der einzige Fall, in dem alter Text sichtbar bliebe, und ausschließlich
   bei nicht geladenem Katalog. Auch `hourlyMetricById` (Zeile ~78-82, für
   die Reihenfolge-Ansicht `WeatherV2Reihenfolge`) nutzt dieselbe
   Auflösung.

**Sichtbare Änderung bei korrekt geladenem Katalog** (`src/app/metric_catalog.py`,
zitiert):
- `thunder_level`: „Gewitter-Risiko" → **„Gewitter"** (`id="thunder"`,
  `label_de="Gewitter"`, Zeile 256)
- `visibility_m`: „Sicht" → **„Sichtweite"** (`id="visibility"`,
  `label_de="Sichtweite"`, Zeile 384)
- Alle übrigen 8 Einträge (Temperatur, Gefühlte Temperatur, Wind, Böen,
  Niederschlag, UV-Index, Regenwahrscheinlichkeit, Windrichtung): Katalog-
  und bisheriger FE-Text sind bereits identisch — keine sichtbare Änderung.

### Teil 2: Alarme (Trip + Vergleich, geteilte Komponente) — statischer Crosswalk

**Design-Entscheidung (Abweichung zu Teil 1, bewusst):** `alertMetricLabels.ts`
wird von **vielen** Stellen ohne geladenen Metrik-Katalog konsumiert
(`TripEditView.svelte`, `AlertRuleRow.svelte` im Alert-Regel-Editor u. a.,
s. Blast-Radius unten) — ein Laufzeit-Fetch wie in Teil 1 würde dort eine
neue Netzwerkabhängigkeit für reine Label-Anzeige einführen. Stattdessen
werden die betroffenen `label_de`-Werte **statisch** auf den heutigen
Katalog-Wortlaut nachgezogen (wie A1 es für die vier Auswahlflächen
ursprünglich tat) — ohne automatisierten Cross-Language-Wächter gegen
künftige `metric_catalog.py`-Änderungen (s. Known Limitations).

1. **`frontend/src/lib/utils/alertMetricLabels.ts`** — `ALERT_METRIC_LABELS`
   behält Struktur und alle Einträge; nur `label_de` folgender drei
   Einträge wird auf den Katalog-Wortlaut geändert:

   | AlertMetric | Katalog-`id` | Alt | Neu (`metric_catalog.py`-Zitat) |
   |---|---|---|---|
   | `cape` | `cape` | `'CAPE'` | `'Gewitterenergie (CAPE)'` (Zeile 273) |
   | `temperature_min` | `temperature` (Kollisionsfall) | `'Tiefsttemperatur'` | `'Temperatur (Minimum)'` |
   | `temperature_max` | `temperature` (Kollisionsfall) | `'Höchsttemperatur'` | `'Temperatur (Maximum)'` |

   Kein Kollisions-Suffix-Mechanismus zur Laufzeit nötig (anders als A2b):
   `temperature_min`/`temperature_max` sind bereits zwei getrennte
   `AlertMetric`-Schlüssel im selben `Record` — jeder trägt seinen
   Zusatz direkt und fest im `label_de`-Wert.

   Einheit/Vergleichsoperator (`unit`, `comparison`) bleiben unverändert —
   keine Katalog-Felder, weiterhin lokal gepflegt.

2. **NEU: `frontend/src/lib/utils/alertMetricCatalogIds.ts`** — dokumentiert
   den Crosswalk als benannte Konstanten (kein Laufzeit-Verhalten, nur
   Vollständigkeits-Nachweis + Selbstdokumentation):

   ```
   ALERT_METRIC_TO_CATALOG_ID: Record<AlertMetric, string> = {
     wind_gust: 'gust', precipitation_sum: 'precipitation',
     thunder_level: 'thunder', snow_line: 'snowfall_limit',
     cape: 'cape', visibility: 'visibility', humidity: 'humidity',
     freezing_level: 'freezing_level', fresh_snow: 'fresh_snow',
     temperature_min: 'temperature', temperature_max: 'temperature',
   }

   NON_CATALOG_ALERT_METRICS: ReadonlySet<AlertMetric> = new Set([
     'temperature_change', 'wind_change', 'precipitation_change',
   ])
   ```

   **`DELTA_ONLY_METRICS`** (`alert-rules-editor/alertRuleDefaults.ts`)
   wird explizit **nicht** wiederverwendet: es enthält zusätzlich
   `thunder_level` (Issue #297 — dort delta-only im Sinne des
   Regel-**Modus**, weil eine diskrete Ordinal-Metrik keinen sinnvollen
   Absolut-Alarm hat), aber `thunder_level` **hat** eine gültige
   1:1-Katalog-Entsprechung (`thunder`, Label „Gewitter", bereits korrekt
   in beiden bisherigen Textquellen). `DELTA_ONLY_METRICS` beschreibt
   Regel-Modus-Semantik, `NON_CATALOG_ALERT_METRICS` beschreibt
   Label-Herkunfts-Semantik — unterschiedliche Fragen, unterschiedliche
   Antwortmengen. Eine Wiederverwendung hätte `thunder_level` fälschlich
   als „hat keine Katalog-Entsprechung" markiert.

   `snow_line → snowfall_limit`: Katalog `id="snowfall_limit"`,
   `label_de="Schneefallgrenze"` (`src/app/metric_catalog.py:297`) —
   identisch mit dem heutigen `AlertMetric`-Text, keine sichtbare Änderung.
   (Hinweis: `LEGACY_ALERT_METRIC_MAP` in `alertMetricLabels.ts` enthält
   zusätzlich `snow_line: 'freezing_level'` aus Issue #959 — dieser Eintrag
   ist durch `normalizeAlertMetric()`s Prüfreihenfolge [`raw in
   ALERT_METRIC_LABELS` zuerst] praktisch unerreichbar, da `snow_line`
   selbst ein gültiger `AlertMetric`-Schlüssel ist. Vorbestehende
   Auffälligkeit, nicht Teil dieser Scheibe — Nebenbefund-Kandidat #1199,
   kein nutzersichtbares Fehlverhalten.)

3. **`frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte`**
   — lokale Konstante `METRIC_LABELS` (14 Einträge) entfällt vollständig.
   Zeile 96 (`label={METRIC_LABELS[metric] ?? metric}`) liest stattdessen
   `label={ALERT_METRIC_LABELS[metric]?.label_de ?? metric}` (Import aus
   `$lib/utils/alertMetricLabels`).

   Damit behoben, **ohne eigene Logik**, allein durch Wegfall der
   Zweitquelle:
   - `temperature_change`: „Temperatursturz" (bisher `AlertMetricLevelTable.svelte`)
     → **„Temperaturänderung"** (bisher schon in `alertMetricLabels.ts`,
     Zeile 22) — behobene Divergenz, DELTA_ONLY_METRICS-Mitglied,
     `NON_CATALOG_ALERT_METRICS`.
   - `precipitation_change`: „Regenänderung" (bisher `AlertMetricLevelTable.svelte`)
     → **„Niederschlagsänderung"** (bisher schon in `alertMetricLabels.ts`,
     Zeile 24) — behobene Divergenz.
   - `wind_change`: „Windänderung" in beiden Quellen bereits identisch —
     keine sichtbare Änderung.
   - `cape`, `temperature_min`, `temperature_max`: übernehmen die unter
     Punkt 1 geänderten `label_de`-Werte.
   - Alle übrigen 8 Einträge: unverändert (Quellen stimmten bereits
     überein).

**Blast Radius — betrifft beide Kontexte gleichzeitig:**
`AlertMetricLevelTable.svelte` wird eingebunden von `alerts-tab/AlertsTab.svelte`
(Trip, Legacy-Pfad) **und** `shared/AlarmeTab.svelte` (geteilter Organismus,
`context="route"|"vergleich"` — trotz veraltetem Kopfkommentar
„UNGEWIRED in dieser Scheibe (S2)" produktiv in beiden Kontexten eingebunden,
verifiziert per Grep: `CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte`,
`TripTabs.svelte`, `AlarmeScheduleTab.svelte`, `VersandTab.svelte`,
`WeatherMetricsTab.svelte`. Der stale Kommentar wird hier nicht korrigiert —
kosmetischer Doku-Drift ohne Verhaltensbezug, Nebenbefund-Kandidat #1199).
Jede Label-Änderung wirkt also **sofort in Trip UND Vergleich zugleich** —
beabsichtigt (ein Register), aber AC-6 prüft das explizit.

**Zusätzliche automatisch mitgezogene Konsumenten von `alertMetricLabels.ts`**
(kein eigener Codepfad nötig, aber Adversary-relevant): `frontend/src/lib/components/edit/TripEditView.svelte`,
`frontend/src/lib/components/trip-detail/TripOverview.svelte`,
`frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte`,
`frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`,
`frontend/src/lib/components/alerts-tab/alertMetricTable.ts`.

## Expected Behavior

- **Input:** Ein Nutzer öffnet den Stundenverlauf-Bereich eines
  Ortsvergleichs (Hub oder `/compare/new`) bzw. die Alarme-Tabelle eines
  Trips oder Vergleichs.
- **Output:** Stundenverlauf-Checkboxen zeigen die Katalog-Namen
  (`thunder_level` → „Gewitter", `visibility_m` → „Sichtweite", Rest
  unverändert). Die Alarme-Tabelle zeigt für `cape` „Gewitterenergie
  (CAPE)", für `temperature_min`/`temperature_max` „Temperatur
  (Minimum)"/„Temperatur (Maximum)", für `temperature_change`/
  `precipitation_change` die vereinheitlichten Änderungs-Labels — identisch
  in Trip- und Vergleichs-Kontext.
- **Side effects:** Keine Persistenz-Änderung — Speicher-Keys
  (`temp_c`, `wind_gust`, `temperature_min` etc.) bleiben unverändert,
  betroffen ist ausschließlich die Anzeige-Beschriftung.

## Acceptance Criteria

- **AC-1:** Given der Stundenverlauf-Katalog `ALL_HOURLY_METRICS` und ein
  vollständig geladener Metrik-Katalog (`GET /api/metrics`) / When
  `resolveHourlyMetricLabel()` für `thunder_level` bzw. `visibility_m`
  aufgerufen wird / Then liefert sie „Gewitter" bzw. „Sichtweite" (statt der
  bisherigen „Gewitter-Risiko"/„Sicht") — für alle übrigen 8 Hourly-Keys
  liefert sie exakt den bisherigen Text (keine unbeabsichtigte Änderung).
  - Test: `frontend/src/lib/components/compare/compareHourlyCatalogIds.test.ts`
    (neu) — ruft `resolveHourlyMetricLabel()` für alle 10 Hourly-Keys mit
    einem Katalog-Fixture-Objekt auf und vergleicht jedes Ergebnis gegen den
    erwarteten Text (die zwei Änderungen UND die acht Unveränderten).

- **AC-2:** Given der Ortsvergleichs-Kontext (`context="vergleich"`) von
  `WeatherMetricsTab.svelte` / When die Komponente mountet / Then wird
  zusätzlich zu `GET /api/compare/metrics` (bestehend) auch
  `GET /api/metrics` geladen und das Ergebnis an
  `CompareHourlyLayoutControls` durchgereicht — der Stundenverlauf-Block
  bleibt dabei unabhängig vom Erfolg dieses zusätzlichen Ladevorgangs
  sichtbar und bedienbar (kein neues Gate).
  - Test: Erweiterung von
    `frontend/src/lib/components/shared/__tests__/compare_hourly_layout_controls_structure.test.ts`
    (AST-Test mit dem echten Svelte-Compiler, gleiches Muster wie
    bestehende Tests der Datei) — prüft, dass `CompareHourlyLayoutControls.svelte`
    eine `catalog`-Prop deklariert und im Label-Ausdruck des
    `{#each ALL_HOURLY_METRICS}`-Blocks referenziert (statt nur
    `metric.label`); separater Test für `WeatherMetricsTab.svelte`, dass der
    Vergleichs-`$effect`-Block einen `/api/metrics`-Aufruf enthält, der
    NICHT im selben Gate wie der Stundenverlauf-Render-Block steht (Struktur:
    Fetch-Effect und `{#if sections.includes('stundenverlauf')}`-Block sind
    unabhängige AST-Knoten).

- **AC-3:** Given die Alarme-Tabelle zeigt eine aktive Metrik mit
  1:1-Katalog-Entsprechung (`wind_gust`, `precipitation_sum`,
  `thunder_level`, `snow_line`, `cape`, `visibility`, `humidity`,
  `freezing_level`, `fresh_snow`) / When `AlertMetricLevelTable` gerendert
  wird / Then zeigt jede Zeile den Katalog-`label_de`-Wert — insbesondere
  `cape` als „Gewitterenergie (CAPE)" statt „CAPE".
  - Test: Erweiterung von `frontend/src/lib/utils/alertMetricLabels.test.ts`
    — Assertion `ALERT_METRIC_LABELS['cape'].label_de === 'Gewitterenergie (CAPE)'`
    plus je eine Assertion für die 8 unveränderten 1:1-Metriken (Regressionsschutz).

- **AC-4:** Given ein Nutzer hat sowohl `temperature_min` als auch
  `temperature_max` als aktive Alarm-Metriken konfiguriert / When die
  Alarme-Tabelle gerendert wird / Then zeigt die eine Zeile „Temperatur
  (Minimum)" (statt bisher „Tiefsttemperatur") und die andere „Temperatur
  (Maximum)" (statt bisher „Höchsttemperatur") — beide gleichzeitig lesbar
  unterscheidbar, keine Verwechslungsgefahr durch identischen Text.
  - Test: Erweiterung von `frontend/src/lib/utils/alertMetricLabels.test.ts`
    — Assertions für `temperature_min`/`temperature_max` gegen die neuen
    Werte; explizite Vorher/Nachher-Dokumentation im Testkommentar (PO-Sicht:
    sichtbare Änderung).

- **AC-5:** Given die drei Delta-Metriken ohne Katalog-Entsprechung
  (`temperature_change`, `wind_change`, `precipitation_change`) / When
  `NON_CATALOG_ALERT_METRICS` (neu) gegen alle 14 `AlertMetric`-Werte
  geprüft wird / Then enthält die Menge exakt diese drei Metriken, und für
  jede der übrigen 11 Metriken existiert ein auflösbarer Eintrag in
  `ALERT_METRIC_TO_CATALOG_ID`, dessen Ziel-`id` eine tatsächlich im
  Katalog vorhandene Größe ist (kein still ergänzter Ausreißer ohne erneute
  bewusste Entscheidung). Zusätzlich: `AlertMetricLevelTable` zeigt für
  `temperature_change` „Temperaturänderung" (statt bisher divergent
  „Temperatursturz") und für `precipitation_change`
  „Niederschlagsänderung" (statt bisher divergent „Regenänderung") — beide
  Textquellen sind jetzt eine.
  - Test: `frontend/src/lib/utils/alertMetricCatalogIds.test.ts` (neu) —
    (a) Vollständigkeits-Test: `NON_CATALOG_ALERT_METRICS.size === 3` und
    Set-Inhalt exakt `{temperature_change, wind_change, precipitation_change}`;
    (b) für jeden `AlertMetric`-Wert außerhalb dieser Menge existiert ein
    String-Eintrag in `ALERT_METRIC_TO_CATALOG_ID` (kein `undefined`);
    (c) Vollabdeckungs-Test analog `alertMetricLabels.test.ts`s
    „alle 9 aktuellen AlertMetric-IDs" (dort jetzt 14) — Set ∪ Crosswalk-Keys
    ergibt exakt alle 14 `AlertMetric`-Werte, keine Lücke, keine
    Doppelzählung. Separat: Assertion, dass
    `ALERT_METRIC_LABELS['temperature_change'].label_de === 'Temperaturänderung'`
    UND (per AST-Test analog AC-2-Muster oder direktem Quelltext-Vergleich
    der beiden vormaligen Werte) dass `AlertMetricLevelTable.svelte` keine
    eigene `METRIC_LABELS`-Konstante mehr deklariert.

- **AC-6:** Given `AlarmeTab.svelte` wird einmal mit `context="route"` und
  einmal mit `context="vergleich"` für dieselbe aktive Metrik (z. B.
  `cape`) instanziiert / When `AlertMetricLevelTable` in beiden Fällen
  rendert / Then zeigen beide Kontexte identisch „Gewitterenergie (CAPE)"
  — es gibt keinen zweiten, kontextabhängigen Label-Pfad (Trip/Compare-
  Teilungs-Invariante, CLAUDE.md).
  - Test: neu, `frontend/src/lib/components/shared/__tests__/alarme_tab_shared_labels.test.ts`
    — prüft strukturell (AST oder Quell-Analyse), dass `AlarmeTab.svelte`
    in **beiden** `context`-Zweigen dieselbe `AlertMetricLevelTable`-Instanz
    (nicht zwei verschiedene Imports/Komponenten) mit denselben
    `activeMetrics`/`levels`-Bindungspfaden einbindet, UND dass
    `AlertMetricLevelTable.svelte` selbst keinen `context`-Parameter besitzt
    (die Komponente kann strukturell nicht zwischen den Kontexten
    unterscheiden — das beweist Gleichheit stärker als ein
    Werte-Vergleich).

- **AC-7:** Given der Metrik-Katalog (`GET /api/metrics`) im
  Vergleichs-Kontext ist noch nicht geladen oder der Ladevorgang ist
  fehlgeschlagen / When der Stundenverlauf-Block gerendert wird / Then
  zeigt jede Checkbox den bisherigen hartkodierten Text aus
  `ALL_HOURLY_METRICS[].label` als Fallback (kein leerer/kaputter Text, kein
  Absturz) — der Block bleibt vollständig bedienbar.
  - Test: Erweiterung von `compareHourlyCatalogIds.test.ts` —
    `resolveHourlyMetricLabel(key, {}, fallbackText)` liefert `fallbackText`
    unverändert für alle 10 Keys (leeres/fehlendes Katalog-Objekt simuliert
    den Fail-Soft-Fall).

## Known Limitations

- **Scheibe C (#1401)** — Begründung statt Leerstelle bei fehlenden
  Größen — ist separates Ticket, nicht Teil dieser Lieferung.
- **S4/#1357** — Auswertung als frei wählbares Element ist NICHT Teil
  dieser Scheibe. Die Kollisions-Lösung für `temperature_min`/
  `temperature_max` ist eine feste Beschriftungsregel (statisch im
  `label_de`-Wert verankert), keine UI zum Wählen der Auswertung.
- **Renderer-Mail-Gate (#811) nicht betroffen** — reine Frontend-Änderung,
  keine Datei unter `src/output/renderers/email/*.py` o. ä. angefasst.
- **`src/app/metric_catalog.py` wird nicht verändert** — nur lesend
  referenziert/zitiert (Teil 2) bzw. zur Laufzeit über den bestehenden
  Endpoint konsumiert (Teil 1).
- **Teil 2 hat keinen automatisierten Cross-Language-Wächter.** Die
  `label_de`-Werte in `alertMetricLabels.ts` sind statische Kopien des
  heutigen `metric_catalog.py`-Wortlauts (per Hand nachgezogen, mit
  Datei:Zeile zitiert). Ändert sich künftig ein `label_de`-Wert im
  Backend-Katalog für eine der 11 crosswalk-fähigen Metriken, driftet
  `alertMetricLabels.ts` wieder still auseinander — dasselbe Risiko, das
  A1 für die vier Auswahlflächen ursprünglich hatte, dort aber inzwischen
  durch Laufzeit-Konsum geschlossen ist. Ein Rückbau auf Laufzeit-Fetch für
  Teil 2 wäre eine größere Änderung (Threading eines Katalog-Props durch
  mindestens 5 zusätzliche Konsumenten, s. Blast Radius) und ist bewusst
  nicht Teil dieser Lieferung.
- **`AlarmeTab.svelte`-Kopfkommentar „UNGEWIRED in dieser Scheibe (S2)"
  bleibt unkorrigiert** — veraltet (Komponente ist produktiv verdrahtet,
  s. Implementation Details), aber kosmetischer Doku-Drift ohne
  Verhaltensbezug. Nebenbefund-Kandidat für Sammel-Issue #1199.
- **`LEGACY_ALERT_METRIC_MAP`-Eintrag `snow_line: 'freezing_level'`
  (`alertMetricLabels.ts`) bleibt unangetastet** — vorbestehende
  Auffälligkeit (praktisch unerreichbar wegen Prüfreihenfolge in
  `normalizeAlertMetric()`), nicht Teil des Issues, kein
  nutzersichtbares Fehlverhalten. Nebenbefund-Kandidat #1199.
- **Fail-Soft-Fallback (Teil 1) ist eine bewusste Grenze, kein Bug:** bei
  nicht geladenem Katalog zeigt der Stundenverlauf für `thunder_level`/
  `visibility_m` vorübergehend noch den alten Text („Gewitter-Risiko"/
  „Sicht") statt der neuen Katalog-Begriffe. Das betrifft ausschließlich
  diese zwei Einträge und ausschließlich den Fehlerfall des zusätzlichen
  Ladevorgangs.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec setzt das in A1/A2/ADR-0037 bereits etablierte
  und PO-freigegebene Prinzip „Compare-Ausgabeflächen leiten ihre
  Beschriftung aus dem zentralen Metrik-Katalog ab statt redaktionell zu
  duplizieren" auf die letzten beiden verbliebenen Flächen (Stundenverlauf,
  Alarme) fort — keine neue Grundsatzentscheidung. Die bewusste
  Design-Abweichung zwischen Teil 1 (Laufzeit-Fetch) und Teil 2 (statischer
  Crosswalk) ist eine lokale Umsetzungsentscheidung dieser Spec (begründet
  in Implementation Details), kein Entscheidungsraum, der laut CLAUDE.md
  einen ADR auslöst (Kanäle, Provider, Datenmodell/Persistenz, Auth,
  Editor-Paradigma, Test-/Deploy-Strategie sind nicht betroffen).

## Changelog

- 2026-07-31: Implementiert und verifiziert (Adversary VERIFIED, 54/54
  Tests grün).
- 2026-07-31: Initial spec created (Fix #1401 Scheibe B, Etappe von Epic
  #1372 / Dach #1374). Katalog-Werte gegen `src/app/metric_catalog.py`
  verifiziert (nicht geraten); Ausnahme-Set `NON_CATALOG_ALERT_METRICS`
  bewusst NICHT auf `DELTA_ONLY_METRICS` gestützt (enthält `thunder_level`,
  das eine gültige Katalog-Entsprechung hat — unterschiedliche Semantik).
