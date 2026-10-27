# Context: fix-1791-kuerzel-marken-320

## Request Summary
#1791 (Epic #2507): Im Reihenfolge-Bereich werden Kürzel-Marken bei 320 px Fensterbreite zusammengequetscht bzw. beschnitten. Auf Staging am 2026-10-18 (`eaf35b5e9`) nachgestellt: Der Teil „von der Bottom-Nav verdeckt" ist ein Messartefakt des Prüftests, der Teil „beschnitten" ist ein echter Produktfehler.

## Messbefund (Staging, Viewport von Anfang an 320×568 / 375×667)
- **Verdeckt = Artefakt.** Jede Zeile lässt sich über die Nav hinausscrollen (`mobile-scroll-pad` 86 px, Inhaltsende y=482 < Nav-Oberkante 498). Mittig gemessen trifft `elementFromPoint` in 16/16 Messungen die Marke. Ursache im Test: `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts:212` — `scrollIntoViewIfNeeded()` scrollt nicht, wenn die Zeile teilweise hinter der fixierten Nav steht.
- **Beschnitten bei 320 px = echt**, scroll-unabhängig.
  - Ortsvergleich, Blöcke `weather-metrics-stundenverlauf` und `compare-layout-outlook-metrics` (Zeilen wind, precipitation, thunder, gust, rain_probability, sunshine): Textspalte 11 px (Zeilenbreite 222 px), Marken clientWidth 9 / scrollWidth 22–47, der Roh/Einfach-Umschalter überlagert die Marken.
  - Trip (nur Gewitter): Textspalte 43 px, Marke 41/47, 6 px Überstand, lesbar.
  - 375 px: kein Befund (Textspalte ≥ 66 px).
- Beide Editoren sind bei 320/375 px direkt erreichbar (die Aussage im Ticket „Tab existiert bei 320 px nicht" gilt nicht mehr).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | Ursache: `.row` Zeile 307 `grid-template-columns: 28px 16px 1fr auto`; Steuer-Spalte (`.controls`, Zeilen 157–171, `Segmented` Roh/Einfach + „Aus") ~105 px; `.label-cell` Zeile 333 `min-width: 0`; Mobil-Regel `@media (max-width: 899px)` ab Zeile ~462 stapelt nur `.controls` untereinander, nicht den Umschalter selbst. Rechnung: 222 − 32 − 28 − 16 − 30 − 105 = 11 px. |
| `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts` | Prüftest: Zeile 66 nimmt 320 px aus der Auflösungsliste; Zeile 212 `scrollIntoViewIfNeeded`; Zeilen 292–297 `mobileNavZone` (Verdeckt-Prüfung unter 900 px abgeschaltet); Zeilen 496–503 Zeilenzahl 6 — seit #2049 gibt es zwei `wm2-reihenfolge-row`-Blöcke (Kanal + 3-Tages-Vorschau) ⇒ AC-10 heute rot mit „12 statt 6". |
| `frontend/e2e/playwright.kuerzel-marken-sichtbar.staging.config.ts`, `kuerzel-marken-sichtbar.staging.setup.ts` | Staging-Config und Anmelde-Setup des Prüftests |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `CompareHourlyLayoutControls.svelte`, `CompareOutlookLayoutControls.svelte` | Nutzer der geteilten Komponente (Trip und Ortsvergleich) |

## Existing Patterns
- Bereits vorhandener Mobil-Notausgang aus #1719 S4 (`@media (max-width: 899px)`): Name bricht um, Marken brechen zwischen Kürzeln, `.controls` gestapelt. Der Fix erweitert diese Regel, er ersetzt sie nicht.
- Trip/Ortsvergleich-Teilung (PO-Vorgabe): Die Komponente ist geteilt — ein Fix wirkt in beiden. Kein Compare-eigener Zweig.
- AC-12 (Bruchzone 900–1300 px) verlangt: Name darf kürzen, Marke nie. Die Gegenprobe zu AC-12 darf durch den Fix nicht blind werden — Änderungen gelten nur unter 900 px.

## Dependencies
- Upstream: `Segmented` (`$lib/components/atoms`), Registerdaten für `col_label` / `kurzform`.
- Downstream: Trip-Editor (Reiter Wetter-Metriken) und alle drei Vergleichs-Flächen; Vitest-/Node-Strukturtests unter `shared/__tests__/` (`weather_metric_kuerzel_marken.test.ts`, `weather_metric_name_forms_visible.test.ts`, `metricKuerzelLegende.test.ts`) lesen die Komponente.

## Existing Specs
- `docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md` — Vorgänger (AC-10/11/12/13/14, Status draft); definiert die fünf Sichtbarkeits-Bedingungen.

## Risks & Considerations
- Fix-Schnitt: unter 900 px `.controls` in eine eigene zweite Rasterzeile (z.B. `grid-template-areas`) — betrifft Drag-Griff-Zeile (`cursor: grab`, ADR-0024 SortableList) und `.row.aus-row` (hat eigenes `grid-template-columns: 1fr auto`); Ziehgeste (AC-14) darf nicht brechen.
- Prüftest-Reparatur gehört ins selbe Ticket (CLAUDE.md: Kern-/Live-Schicht nicht rot liegenlassen): 320 px wieder in die Liste, mittig scrollen, `mobileNavZone` entfernen, Zeilenzahl je Block.
- Der Staging-Test ist Live-Schicht; Bug-Nachweis „aus Nutzersicht" muss dort rot vor / grün nach dem Fix laufen. Kern-Strukturtest allein beweist die Breite nicht.
- Mutations-Gegenprobe Pflicht: Fix zurücknehmen ⇒ welcher Test wird rot?

## Analysis

### Type
Bug (nutzersichtbar nur bei 320 px; "verdeckt" = Messartefakt des Prüftests)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte | MODIFY | Unter 900 px: `.row` auf zweizeiliges Raster (`grid-template-areas`): Zeile 1 = Pos/Griff/Label+Marken (volle Breite), Zeile 2 = `.controls`. `.row.aus-row` bleibt `1fr auto` (eigene Regel prüfen). Nur innerhalb `@media (max-width: 899px)`, damit die Gegenprobe zu AC-12 (900–1300 px) scharf bleibt. |
| frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts | MODIFY | 320 px wieder in Auflösungsliste (Z.66); Scroll mittig statt `scrollIntoViewIfNeeded` (Z.212); `mobileNavZone` entfernen (Z.292–297); Zeilenzahl je Block statt 6 (Z.496–503, seit #2049 zwei Blöcke). |
| frontend/src/lib/components/shared/__tests__/ (Strukturtests) | PRÜFEN | `weather_metric_kuerzel_marken.test.ts` u.a. lesen die Komponente; dürfen durch CSS-Umbau nicht brechen. |

### Scope Assessment
- Files: 2 (+ ggf. 1 Strukturtest)
- Estimated LoC: +25/-15 Komponente, +/-30 Spec
- Risk Level: MEDIUM — geteilte Komponente (Trip + 3 Vergleichsflächen), Drag-Zeile (AC-14, ADR-0024)

### Technical Approach
Reines CSS-Layout unter 900 px: Steuerelemente (Roh/Einfach + „Aus") in eigene zweite Rasterzeile unter dem Label, dadurch bekommt die Textspalte die volle Zeilenbreite (statt 11 px). Kein neuer Code-Zweig für Trip/Compare. Prüftest repariert im selben Ticket; Bug-Nachweis aus Nutzersicht = Staging-Spec bei 320 px rot vor / grün nach Fix. Mutations-Gegenprobe: Media-Query-Regel zurücknehmen ⇒ 320-px-Fall muss rot werden; Gegenprobe AC-12 darf nicht blind werden.

### Dependencies
`Segmented` (atoms), Registerdaten `col_label`/`kurzform`; Nutzer: WeatherMetricsTab, CompareHourly-/CompareOutlookLayoutControls; Vorgänger-Spec fix_1719_s4_kuerzel_vereinheitlichung.md.

### Open Questions
- [ ] Keine für den PO. Technisch in Spec zu klären: `aus-row` und Ziehgriff-Bereich bei zweizeiligem Raster.
