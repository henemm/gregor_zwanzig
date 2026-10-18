---
entity_id: fix_1791_kuerzel_marken_320px
type: module
created: 2026-10-18
updated: 2026-10-18
status: draft
version: "1.0"
workflow: fix-1791-kuerzel-marken-320
tags: [frontend, reihenfolge, kuerzel, responsive, issue-1791, epic-2507]
---

# #1791 — Kürzel-Marken im Reihenfolge-Bereich bleiben bei 320 px vollständig lesbar

## Approval

- [ ] Approved

## Purpose

Im Bereich „Reihenfolge" (Trip-Editor und alle Ortsvergleich-Flächen) sind die Kürzel-Marken
„Mail" und „Kurzform" bei 320 px Fensterbreite beschnitten und werden vom Roh/Einfach-Umschalter
überlagert. Der Fix gibt den Marken unter 900 px die volle Zeilenbreite, indem die
Bedienelemente in eine eigene zweite Rasterzeile wandern, und repariert den Prüftest, der
320 px seit #1719 S4 ausgenommen hatte und dabei ein Messartefakt mitschleppte.

## Source

- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte`
- **Identifier:** CSS-Regeln `.row`, `.controls` und der Block `@media (max-width: 899px)`
- **Zweite Datei:** `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts` (Prüftest-Reparatur)
- Issue #1791 (Epic #2507); Vorgänger-Spec `fix_1719_s4_kuerzel_vereinheitlichung.md`
  (Nachtrag 2026-08-12 b: „Beim Schließen gehören die 320-px-Zeile und der `mobileNavZone`-Block
  zurück bzw. weg.")
- Kontext und Messbefund: `docs/context/fix-1791-kuerzel-marken-320.md`

**Schicht:** reines Frontend (SvelteKit). Kein Go-, kein Python-Anteil.

## Messbefund (Staging `eaf35b5e9`, 2026-10-18)

| Aussage | Befund |
|---|---|
| Ortsvergleich, 320 px (Blöcke `weather-metrics-stundenverlauf`, `compare-layout-outlook-metrics`; Zeilen wind, precipitation, thunder, gust, rain_probability, sunshine) | Zeilenbreite 222 px, Textspalte 11 px, Marken `clientWidth` 9 / `scrollWidth` 22–47, Roh/Einfach-Umschalter überlagert die Marken |
| Trip, 320 px (nur Gewitter) | Textspalte 43 px, Marke 41/47, 6 px Überstand |
| 375 px | kein Befund (Textspalte ≥ 66 px) |
| „Von der Bottom-Nav verdeckt" | **Kein Produktfehler.** Jede Zeile lässt sich über die Nav hinausscrollen (`mobile-scroll-pad` 86 px); mittig gemessen trifft `elementFromPoint` in 16/16 Messungen die Marke. Ursache ist der Prüftest: `scrollIntoViewIfNeeded()` (Z.212) scrollt nicht, wenn die Zeile teilweise hinter der fixierten Nav steht |

Rechnung der Ursache: 222 − 32 (Polster) − 28 (Position) − 16 (Griff) − 30 (3 Lücken) − 105
(`.controls` mit Umschalter + „Aus") = 11 px für die Textspalte.

## Estimated Scope

- **LoC:** ca. +25/−15 in der Komponente, ca. +/−30 im Prüftest
- **Files:** 2
- **Effort:** low–medium
- **Risiko:** MEDIUM — geteilte Komponente (Trip + drei Vergleichs-Flächen), Ziehzeile (ADR-0024)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Segmented` (`$lib/components/atoms`) | component | Roh/Einfach-Umschalter in `.controls` |
| `DragHandle.svelte` (`shared/dnd/`) | component | Ziehgriff, Wurzelelement `.drag-handle` — Position im Raster ist nur über Auto-Platzierung relevant |
| `SortableList` (ADR-0024) | component | umschließt die Zeilen, Ziehgeste (`cursor: grab`) |
| `WeatherMetricsTab.svelte`, `CompareHourlyLayoutControls.svelte`, `CompareOutlookLayoutControls.svelte` | component | Nutzer der geteilten Komponente |
| `fix_1719_s4_kuerzel_vereinheitlichung.md` | spec | AC-10..AC-14 dürfen nicht brechen, AC-12-Gegenprobe muss scharf bleiben |
| `frontend/e2e/playwright.kuerzel-marken-sichtbar.staging.config.ts`, `kuerzel-marken-sichtbar.staging.setup.ts` | test infra | Staging-Config und Anmeldung des Prüftests (unverändert) |
| Strukturtests `shared/__tests__/weather_metric_kuerzel_marken.test.ts`, `weather_metric_name_forms_visible.test.ts`, `metricKuerzelLegende.test.ts` | test | lesen die Komponente; müssen grün bleiben |

## Implementation Details

### Komponente (nur innerhalb `@media (max-width: 899px)`)

Außerhalb der Media-Query ändert sich **kein Zeichen** — sonst wird die Gegenprobe zu AC-12
(Bruchzone 900–1300 px: Name kürzt, Marke nie) blind.

1. **`.row` (Ziehzeile) wird zweizeilig.** Die Ziehzeile bekommt unter 900 px drei Spalten
   (`28px 16px 1fr`) statt vier. Zeile 1 enthält Position, Ziehgriff und `.label-cell`
   (Name + Marken) und damit die volle Zeilenbreite für die Textspalte; Zeile 2 enthält
   `.controls`, über alle Spalten (`grid-column: 1 / -1`, `grid-row: 2`) und rechtsbündig.
   Das Raster darf als `grid-template-areas` oder mit expliziten `grid-column`/`grid-row`
   formuliert werden. Position und Griff werden von der Auto-Platzierung in Zeile 1,
   Spalten 1 und 2 gesetzt; `.label-cell` bekommt `grid-column: 3`. Der Griff (Komponente
   `DragHandle`, Klasse `.drag-handle` liegt in einer fremden Komponente) wird deshalb
   **nicht** per Klassenselektor angefasst — kein `:global`.
2. **`.controls` wird unter 900 px wieder waagerecht.** Die bisherige Regel
   `flex-direction: column; align-items: flex-end` entfällt, weil `.controls` jetzt die ganze
   Zeilenbreite hat; es gilt `flex-direction: row; flex-wrap: wrap; justify-content: flex-end`
   (Roh/Einfach und „Aus" nebeneinander, bei Platzmangel umbrechend).
3. **`.row.aus-row` bleibt unberührt.** Die Zeilen der Gruppe „Aus in diesem Kanal" haben
   weder Position noch Ziehgriff und nur einen kleinen „Ein"-Knopf; `grid-template-columns:
   1fr auto` aus `.row.aus-row` (Spezifität 2 Klassen) bleibt bestehen und der Name hat bei
   320 px ca. 150 px. Die neue Mobil-Regel wird deshalb auf `.row:not(.aus-row)` bzw. nur auf
   die Kinder-Platzierung der Ziehzeile begrenzt, damit `grid-column`/`grid-row` nie in die
   Aus-Zeile durchschlagen. Entscheidung: Aus-Zeilen werden **nicht** zweizeilig. Falls der
   Prüftest dort bei 320 px eine Marke beschnitten misst, wird `aus-row` unter 900 px
   ebenfalls auf zwei Zeilen gestellt (Label oben, „Ein" darunter rechts) — das ist dann
   Teil dieses Tickets, kein Folge-Ticket.
4. **Unverändert:** `.row { cursor: grab }`, Padding, `.label-cell { flex-wrap: wrap }`,
   Umbruch-Notausgang der Marken (`white-space: normal`), Markup (kein Eingriff in das
   `{#snippet row}`, damit keine neue Array-Referenz entsteht — Lehre aus #1719 S3).

### Trip/Ortsvergleich-Teilung

Die Komponente ist für Trip und alle Vergleichs-Flächen **dieselbe**. Der Fix ist ein
einziger CSS-Block ohne Kontext-Parameter und ohne Compare-eigenen Zweig; es entsteht keine
neue Komponente, daher greift die Pendant-Sperre nicht und es gibt nichts zu begründen.

### Prüftest `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`

1. **Z.66:** `{ klasse: 'Kleines Handy', width: 320, height: 568 }` wieder in `AUFLOESUNGEN`;
   der erklärende Ausnahme-Kommentar (Z.55–65) entfällt. Damit sind es wieder 14 Auflösungen.
2. **Z.212 (und analog Z.374/375, Z.560):** statt `scrollIntoViewIfNeeded()` wird die Zeile
   mittig ins Sichtfenster gescrollt (`el.scrollIntoView({ block: 'center' })` per
   `evaluate`), damit die fixierte Bottom-Nav die Zeile nicht anschneidet.
3. **Z.292–297:** die Abschaltung der Überdeckungs-Bedingung unter 900 px (`mobileNavZone`)
   entfällt; Bedingung 4 (`elementFromPoint`) gilt wieder in **allen** Auflösungen. Das ist
   durch Punkt 2 möglich und wird durch den Messbefund (16/16 Treffer bei mittigem Scrollen)
   gedeckt.
4. **Z.496–503 (und die Entsprechung im Vergleichs-Test):** die feste Zeilenzahl-Erwartung
   (`TRIP_METRIKEN.length`) wird je `wm2-reihenfolge-row`-Block geprüft. Seit #2049 gibt es im
   Ortsvergleich zwei solcher Blöcke (Kanal und 3-Tages-Vorschau); die Erwartung ist die
   Summe der Zeilen je Block, nicht 6. Heute schlägt AC-10 mit „12 statt 6" fehl — dieser
   Fehlschlag ist ein Testfehler und wird im selben Ticket behoben.

## Expected Behavior

- **Input:** Reihenfolge-Bereich in Trip-Editor oder Ortsvergleich-Fläche bei Fensterbreite
  < 900 px (insbesondere 320 px).
- **Output:** Jede Ziehzeile zeigt oben Position, Griff, Name und beide Marken (volle Breite),
  darunter rechtsbündig Roh/Einfach und „Aus". Ab 900 px sieht die Zeile aus wie bisher.
- **Side effects:** keine; reines Layout.

## Acceptance Criteria

- **AC-1:** Given der Ortsvergleich-Editor bei 320×568 mit den Blöcken Stundenverlauf und
  Ausblick und den Zeilen wind, precipitation, thunder, gust, rain_probability, sunshine /
  When der Bereich „Reihenfolge" geladen und jede Zeile mittig ins Sichtfenster gescrollt
  wird / Then erfüllt in **allen** Zeilen **beider** Blöcke jede Marke die fünf
  Sichtbarkeits-Bedingungen aus #1719-S4 (Text nicht beschnitten `clientWidth ≥ scrollWidth`,
  innerhalb der Zeile, im Sichtfenster, von keinem Nachbarelement überdeckt, Text exakt).
  - Test: Staging-Playwright `kuerzel-marken-sichtbar.staging.spec.ts` (AC-13-Test, Vergleich)
    bei 320 px; heute rot (clientWidth 9 / scrollWidth 22–47), nach dem Fix grün. Live-Schicht;
    das ist der Bug-Nachweis aus Nutzersicht.

- **AC-2:** Given der Trip-Editor bei 320×568 mit der Größe Gewitter in der Reihenfolge /
  When der Bereich „Reihenfolge" geladen wird / Then ist die Kurzform-Marke des Gewitters
  vollständig sichtbar (kein Überstand, `clientWidth ≥ scrollWidth`) und die Zeile erfüllt
  alle fünf Bedingungen.
  - Test: Staging-Playwright, AC-10/AC-11-Test (Trip) bei 320 px; heute rot (6 px Überstand),
    nach dem Fix grün.

- **AC-3:** Given eine Ziehzeile bei 320 px, deren Größe den Roh/Einfach-Umschalter hat /
  When die Zeile angezeigt wird / Then liegen Umschalter und „Aus" in einer eigenen Zeile
  **unter** Name und Marken, überlagern keine Marke (`elementFromPoint` in der Mitte jeder
  Marke trifft die Marke) und sind weiterhin bedienbar (Klick auf „Einfach" schaltet den
  Modus, Klick auf „Aus" entfernt die Größe aus dem Kanal).
  - Test: Staging-Playwright bei 320 px; Bounding-Box des `.controls`-Elements liegt
    vollständig unterhalb der des `.label-cell`, danach echter Klick auf Umschalter und „Aus".

- **AC-4:** Given der Trip-Editor und der Ortsvergleich bei 375×667 / When der Bereich
  „Reihenfolge" geladen wird / Then gibt es unverändert keine Verletzung der fünf Bedingungen
  und keinen waagerechten Seitenscroll (`documentElement.scrollWidth ≤ innerWidth + 1`).
  - Test: Staging-Playwright, dieselben Läufe wie AC-1/AC-2 über die Auflösungsliste
    (375, 390, 414, 600, 768, 899) — alle Breiten unter 900 px grün, nicht nur 320 px.

- **AC-5:** Given eine Fensterbreite ab 900 px (Media-Query-Rand 901 px und Bruchzone
  960/1024 px) / When die Ziehzeile gerendert wird / Then steht `.controls` weiterhin
  **rechts neben** dem Namen in derselben Rasterzeile, die Marken sind einzeilig, und bei
  Platzmangel kürzt der **Name**, nie eine Marke.
  - Test: Staging-Playwright AC-12-Test bei 960 px und 1024 px unverändert grün, zusätzlich
    Prüfung bei 901 px, dass `.controls` und `.label-cell` dieselbe vertikale Mitte teilen
    (Controls nicht unter dem Label). Gegenprobe siehe Abschnitt „Mutations-Gegenprobe".

- **AC-6:** Given der Reihenfolge-Bereich bei einer Breite unter 900 px / When der Nutzer
  eine Zeile am Ziehgriff auf eine andere Position zieht / Then landet sie an der
  Zielposition, der Stand wird gespeichert und bleibt nach dem Neuladen erhalten; die Zeilen
  der Gruppe „Aus in diesem Kanal" bleiben unverändert aufgebaut (Name + „Ein"-Knopf in
  einer Zeile, ohne Griff und Position), der „Ein"-Knopf holt die Größe zurück.
  - Test: Staging-Playwright AC-14-Test (Ziehen) zusätzlich bei einer Breite unter 900 px
    (z. B. 375 px); plus Prüfung der Aus-Zeile (kein `.drag-handle`, „Ein" im Sichtfenster
    und nicht von der Marke überlagert) bei 320 px.

- **AC-7:** Given der Prüftest `kuerzel-marken-sichtbar.staging.spec.ts` / When er gegen
  Staging läuft / Then enthält die Auflösungsliste 320×568, die Zeile wird mittig
  gescrollt, die Überdeckungs-Prüfung gilt in allen Auflösungen (keine `mobileNavZone`-
  Abschaltung mehr), und die Zeilenzahl wird je `wm2-reihenfolge-row`-Block erwartet, sodass
  der Test bei zwei Blöcken nicht mit „12 statt 6" fehlschlägt.
  - Test: der Prüftest selbst läuft vollständig grün (AC-5, AC-10/11, AC-12, AC-13, AC-14
    der #1719-S4-Spec); Nachweis der Reparatur: bei zurückgenommenem Fix (Mutation 1) ist er
    bei 320 px rot, bei angewandtem Fix grün — er misst also weder durch das Nav-Artefakt
    noch verfehlt er den echten Fehler.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Ortsvergleich bei 320 px WHEN Reihenfolge geladen und Zeile mittig
  gescrollt THEN Marken aller Zeilen beider Blöcke vollständig sichtbar (AC-1) — rot vor Fix.
- [ ] Test 2: GIVEN Trip bei 320 px mit Gewitter WHEN Reihenfolge geladen THEN Kurzform-Marke
  ohne Überstand (AC-2) — rot vor Fix.
- [ ] Test 3: GIVEN 320 px WHEN Umschalter und „Aus" bedient THEN sie liegen unter dem Label,
  überlagern keine Marke und funktionieren (AC-3).
- [ ] Test 4: GIVEN 901/960/1024 px WHEN gerendert THEN Controls rechts neben dem Label,
  Name kürzt, Marke nie (AC-5) — muss bei Mutation 2 rot werden.
- [ ] Test 5: GIVEN Breite < 900 px WHEN Zeile gezogen THEN neue Position gespeichert; Aus-Zeile
  intakt (AC-6).
- [ ] Test 6 (Kern, deterministisch): die Strukturtests `weather_metric_kuerzel_marken.test.ts`,
  `weather_metric_name_forms_visible.test.ts` und `metricKuerzelLegende.test.ts` laufen nach
  dem CSS-Umbau grün (Markup unverändert). **Ehrlich benannt:** Dieser Kern-Test beweist die
  Breite **nicht** — er bewacht nur, dass Namensformen und Legende im Markup bleiben. Den
  Bug-Nachweis für 320 px liefert ausschließlich die Live-Schicht (Staging-Spec).

### Schichten

| Schicht | Inhalt |
|---|---|
| Live-E2E (Staging) | AC-1 bis AC-7; Bug-Nachweis rot vor / grün nach Fix; Playwright läuft nicht in der CI-Ampel (#1771), daher von Hand im Workflow zu fahren |
| Kern | bestehende Strukturtests unter `shared/__tests__/` bleiben grün; `svelte-check` und `frontend-test` der CI-Ampel |

## Mutations-Gegenprobe (Pflicht)

Mutationen **nur per String-Ersetzung** in der Komponente, mit **externer Sicherungskopie**
(z. B. `cp` nach dem Session-Scratchpad) und Rückspielen der Kopie danach. **Nie**
`git checkout`, `git stash` oder `git reset`.

| # | Mutation | Erwartung |
|---|---|---|
| 1 | Neue Mobil-Regel (Zweizeilen-Raster) innerhalb der Media-Query entfernen bzw. auskommentieren | Prüftest bei 320 px rot (AC-1/AC-2), 375 px und ab 900 px unverändert grün |
| 2 | Zweizeilen-Raster **auch ab 900 px** wirksam machen (Media-Query-Bedingung entfernt oder `max-width` auf 5000 px) | Ab 900 px sitzt `.controls` unter dem Label: AC-5 / AC-12-Gegenprobe muss rot werden. Bleibt sie grün, bewacht sie nichts — das ist ein Finding |
| 3 | Beschränkung auf `.row:not(.aus-row)` entfernen, sodass `grid-row: 2` in die Aus-Zeile durchschlägt | AC-6 (Aus-Zeile) muss rot werden |
| 4 | Mittiges Scrollen im Prüftest durch `scrollIntoViewIfNeeded()` ersetzen | Der Test misst wieder das Nav-Artefakt; zu prüfen ist, dass das auffällt (Bedingung 4 rot bei 320 px trotz angewandtem Fix) — dokumentiert, warum mittiges Scrollen Pflicht ist |

Leitfrage: Ist die Zusicherung an der Stelle geprüft, an der sie **wirkt** (gerenderte
Geometrie bei 320 px) — nicht nur dort, wo der Code steht? Meldet der Adversary eine
Mutation, die kein Test fängt, ist das ein Finding.

## Known Limitations

- Die Playwright-Specs laufen nicht in der CI-Ampel (#1771); die Bewachung gegen Rückfall
  entsteht erst, sobald sie dort aufgenommen werden.
- Die Zeilen werden höher (zweizeilig) unter 900 px; ob das gut aussieht, ist keine
  Geometriefrage — dafür Screenshot-Sichtung (fresh-eyes) bei 320 px.
- Der Kern-Strukturtest allein beweist die Breite nicht (siehe Test 6).
- „Von der Bottom-Nav verdeckt" wird bewusst **nicht** im Produkt „behoben": die Nav deckt
  Inhalt nur am Seitenende ab, und `mobile-scroll-pad` löst das bereits.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0024 SortableList wird eingehalten, nicht geändert)
- **Rationale:** reine CSS-Anpassung innerhalb eines bestehenden Notausgangs (#1719 S4); keine
  Entscheidungsfläche (Kanal, Provider, Datenmodell, Auth, Editor-Paradigma) berührt.

## Changelog

- 2026-10-18: Initial spec created (Workflow fix-1791-kuerzel-marken-320)
