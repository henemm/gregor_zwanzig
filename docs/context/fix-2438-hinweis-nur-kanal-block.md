# Context: fix-2438-hinweis-nur-kanal-block

## Request Summary
Nachbesserung zu #2438 (PR #2582, gemergt a8414240f): Der Abwahl-Hinweis `wm2-aus-hinweis`
erscheint auf Staging zusätzlich im Ausblick-Block. PO-Entscheid 2026-10-20: Hinweis NUR in den
beiden Kanal-Blöcken (Trip-Kanal-Reiter, Ortsvergleich-Kanal-Reiter), NICHT im Ausblick.

## Befund (Staging, a8414240f, 2 Läufe reproduzierbar)
- `kanal-grenzen-und-hinweise.staging.spec.ts`: 6 rot. 5x Playwright-Strict-Mode (2 Treffer:
  `weather-metrics-kanal-reihenfolge` + `compare-layout-outlook-metrics`), 1x #1719 AC-3
  (21 statt 9 `wm2-reihenfolge-row`, weil der Ausblick-Block im selben `weather-metrics-tab` liegt).
- Prod-Deploy NICHT erfolgt, kein Staging-Nachweis geschrieben.

## Ursache
`WeatherV2Reihenfolge.svelte` rendert den Hinweis überall dort, wo `offColumns !== undefined`
(Zeile ~222). Drei Einbettungen übergeben `offColumns`:
| Einbettung | Datei:Zeile | Soll |
|---|---|---|
| Trip-Kanal-Reiter | WeatherMetricsTab.svelte:1720 | Hinweis JA |
| Ortsvergleich-Kanal-Reiter | WeatherMetricsTab.svelte:1529 | Hinweis JA |
| Ausblick (nur E-Mail, activeChannel="email" fest) | CompareOutlookLayoutControls.svelte:247 | Hinweis NEIN |
`CompareHourlyLayoutControls.svelte:258` übergibt kein `offColumns` -> kein Hinweis (ok).

## Related Files
| File | Relevanz |
|---|---|
| frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte | Hinweis-Rendering, braucht Schalter |
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | zwei Kanal-Einbettungen |
| frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte | Ausblick, darf keinen Hinweis zeigen |
| frontend/src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts | Unit (SSR-Render) |
| frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts, kanal-grenzen-ortsvergleich.staging.spec.ts | Locator auf Kanal-Block eingrenzen |

## Existing Patterns
- Opt-in-Props am geteilten Baustein statt Compare-Sonderkomponente (Code-Teilung Trip/Ortsvergleich).

## Risiken
- #1719-AC-3 (21 statt 9) ist vom Ausblick-Block verursacht, nicht vom Hinweis: Ursache = Locator zählt
  `wm2-reihenfolge-row` im ganzen Tab. Mit `weather-metrics-kanal-reihenfolge` eingrenzbar; gehört
  zur selben Locator-Eingrenzung (Trip-Spec), sonst bleibt Staging-Gate rot.
- Schalter-Default so wählen, dass neue Einbettungen den Hinweis nicht ungewollt erben.

## Analysis

### Type
Bug (Nachbesserung zu #2438; Hinweis erscheint zusätzlich im Ausblick-Block)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte | MODIFY | Opt-in-Prop `showAbwahlHinweis?: boolean` (Default false); `<p wm2-aus-hinweis>` (Z. 222) nur bei true |
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | MODIFY | Z. 1538 (Ortsvergleich-Kanal) und Z. 1729 (Trip-Kanal) übergeben `showAbwahlHinweis` |
| frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte | KEINE Änderung | Z. 257 übergibt Prop nicht -> kein Hinweis (Default greift) |
| frontend/src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts | MODIFY | Fälle: Prop true -> Hinweis; offColumns ohne Prop (Ausblick) -> KEIN Hinweis |
| frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts | MODIFY | Locator auf `weather-metrics-kanal-reihenfolge` eingrenzen (Strict-Mode, #1719 AC-3: 21 statt 9 Zeilen) |
| frontend/e2e/kanal-grenzen-ortsvergleich.staging.spec.ts | MODIFY | Z. 224 Hinweis-Locator eingrenzen |

### Scope Assessment
- Files: 5-6, Estimated LoC: +30/-10, Risk Level: LOW (isolierter UI-Schalter, Default = aus)

### Technical Approach
Opt-in-Prop statt Entfernen/Kontext-Weiche: Default false, damit neue Einbettungen den Hinweis nicht erben. Kein Compare-Sonderbau (Code-Teilung bleibt). Staging-Specs: Locator auf Kanal-Block eingrenzen; sonst bleibt das Staging-Gate rot, auch wenn der Hinweis korrekt ist.

### Dependencies
`offColumns !== undefined` steuert weiterhin die Aus-Gruppe; der Hinweis ist nur ein Kind darin (Z. 178-224). CompareHourlyLayoutControls übergibt kein `offColumns` -> unberührt.

### Open Questions
- Keine (PO-Entscheid 2026-10-20: Hinweis nur in den beiden Kanal-Blöcken). Prod-Deploy von #2438 steht bis zu diesem Fix aus.
