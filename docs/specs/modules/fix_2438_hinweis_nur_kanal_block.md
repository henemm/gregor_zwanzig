---
entity_id: fix_2438_hinweis_nur_kanal_block
type: module
created: 2026-10-20
updated: 2026-10-20
status: draft
version: "1.0"
tags: [frontend, editor, hinweis, kanaele, trip, ortsvergleich, ausblick, adr-0050]
workflow: fix-2438-hinweis-nur-kanal-block
---

# Fix #2438: Abwahl-Hinweis nur in den Kanal-Blöcken, nicht im Ausblick

## Approval

- [ ] Approved

## Purpose

Nachbesserung zu Feature #2438 (PR #2582). Der Hinweis „Ein Kanal zeigt höchstens, was in der
Grundauswahl gewählt ist …" (`wm2-aus-hinweis`) erscheint auf Staging zusätzlich im Ausblick-Block
des Ortsvergleichs. Dort ist er fachlich falsch platziert (PO-Entscheid 2026-10-20): Er soll nur in
den beiden Kanal-Blöcken stehen — Trip-Kanal-Reiter und Ortsvergleich-Kanal-Reiter. Zusätzlich
werden die Staging-Specs so eingegrenzt, dass sie nur den Kanal-Block messen; ohne das bleibt das
Staging-Gate rot (Strict-Mode-Doppeltreffer, 21 statt 9 Reihenfolge-Zeilen), und #2438 kann nicht
nach Produktion.

## Source

- **Datei:** `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte`
- **Identifier:** `<p data-testid="wm2-aus-hinweis">` (Z. ~222), neue Opt-in-Prop `showAbwahlHinweis`
- Einbettungen: `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Ortsvergleich-Kanal ~Z. 1529, Trip-Kanal ~Z. 1720), `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` (Ausblick, unverändert)

## Estimated Scope

- **LoC:** ~+30/−10
- **Files:** 5–6 (alle `frontend/`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| WeatherV2Reihenfolge.svelte | Baustein | rendert Aus-Gruppe und Hinweis |
| WeatherMetricsTab.svelte | Einbettung | beide Kanal-Blöcke |
| CompareOutlookLayoutControls.svelte | Einbettung | Ausblick (nur E-Mail), darf keinen Hinweis zeigen |
| feat_2438_kanal_abwahl_hinweis | Spec | Ursprungsfeature; AC-1…AC-7 bleiben außer der hier präzisierten Platzierung gültig |

## Implementation Details

```
WeatherV2Reihenfolge: neue Prop showAbwahlHinweis?: boolean (Default false).
  <p wm2-aus-hinweis> nur rendern, wenn offColumns !== undefined UND showAbwahlHinweis === true.
WeatherMetricsTab: beide Kanal-Einbettungen (Trip, Ortsvergleich) übergeben showAbwahlHinweis.
CompareOutlookLayoutControls / CompareHourlyLayoutControls: unverändert (Default false).
Staging-Specs: Locatoren auf [data-testid=weather-metrics-kanal-reihenfolge] eingrenzen.
```

Opt-in mit Default „aus", damit künftige Einbettungen den Hinweis nicht ungewollt erben. Kein
Compare-Sonderbau — Trip und Ortsvergleich nutzen weiterhin denselben Baustein.

## Expected Behavior

- **Input:** Nutzer öffnet im Trip- oder Ortsvergleich-Editor den Werte-Reiter.
- **Output:** Hinweis sichtbar in jedem Kanal-Reiter (E-Mail/Telegram/SMS) beider Editoren; im Ausblick-Block und in der Grundauswahl nicht.
- **Side effects:** keine; keine Daten- oder Verhaltensänderung, `wm2-aus-row` und „Wiederherstellen" unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip im Editor, Werte-Reiter, Kanal-Reiter E-Mail/Telegram/SMS / When der Nutzer den Reiter öffnet / Then ist genau ein `wm2-aus-hinweis` sichtbar, und zwar im Kanal-Block (`weather-metrics-kanal-reihenfolge`)
  - Test: Staging-E2E `kanal-grenzen-und-hinweise.staging.spec.ts`, Locator auf den Kanal-Block eingegrenzt; Unit: Render mit `showAbwahlHinweis=true` enthält den Hinweis

- **AC-2:** Given ein Ortsvergleich im Editor, Werte-Reiter, Kanal-Reiter / When der Nutzer den Reiter öffnet / Then ist genau ein Hinweis im Kanal-Block sichtbar, erzeugt vom selben Baustein wie beim Trip
  - Test: Staging-E2E `kanal-grenzen-ortsvergleich.staging.spec.ts` (Hinweis-Locator eingegrenzt)

- **AC-3:** Given ein Ortsvergleich, Werte-Reiter, Ausblick-Block (nur E-Mail) mit Aus-Gruppe / When der Nutzer ihn betrachtet / Then erscheint dort kein `wm2-aus-hinweis`, die Aus-Gruppe selbst bleibt unverändert sichtbar
  - Test: Unit: Render mit `offColumns` ohne `showAbwahlHinweis` zeigt keinen Hinweis; Staging-E2E: Hinweis-Anzahl im Ausblick-Block ist 0

- **AC-4:** Given ein Kanal-Reiter und der Ausblick-Block liegen im selben Werte-Reiter / When die Trip-Spec #1719 AC-3 die Reihenfolge-Zeilen zählt / Then zählt sie nur den Kanal-Block (9 statt 21 `wm2-reihenfolge-row`) und die Spec ist grün
  - Test: Staging-E2E `kanal-grenzen-und-hinweise.staging.spec.ts` ohne Strict-Mode-Fehler

- **AC-5:** Given die globale Grundauswahl-Ansicht (kein Kanal-Reiter) / When der Nutzer sie öffnet / Then erscheint dort weiterhin kein Abwahl-Hinweis
  - Test: Unit: Render ohne `offColumns` zeigt keinen Hinweis

- **AC-6:** Given eine Einbettung von `WeatherV2Reihenfolge` mit `offColumns`, die `showAbwahlHinweis` nicht setzt / When sie gerendert wird / Then erbt sie den Hinweis nicht (Default aus)
  - Test: Unit-Render ohne Prop, mit `offColumns=[]` und befüllt

## Affected Files

- `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` (MODIFY)
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (MODIFY)
- `frontend/src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts` (MODIFY)
- `frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts` (MODIFY)
- `frontend/e2e/kanal-grenzen-ortsvergleich.staging.spec.ts` (MODIFY)
- `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` (unverändert, nur Referenz)

## Test Plan

- Unit (`kanal_abwahl_hinweis.test.ts`, `node --test`, SSR-Render): Prop `showAbwahlHinweis=true` → Hinweis (AC-1); `offColumns` ohne Prop → kein Hinweis (AC-3, AC-6); ohne `offColumns` → kein Hinweis (AC-5).
- Staging-E2E: `kanal-grenzen-und-hinweise.staging.spec.ts` (AC-1, AC-4) und `kanal-grenzen-ortsvergleich.staging.spec.ts` (AC-2, AC-3), Locatoren auf den Kanal-Block eingegrenzt.
- Mutations-Gegenprobe: Default der Prop auf `true` drehen bzw. Übergabe in einer Kanal-Einbettung entfernen → je ein Test muss rot werden.

## Known Limitations

- Wortlaut, Mobile-Verhalten (320/375 px, Kontrast) und Keine-Handlungsempfehlung des Hinweises bleiben wie in `feat_2438_kanal_abwahl_hinweis` (AC-5, AC-6 dort) — hier nicht neu spezifiziert.
- Prod-Deploy von #2438 steht bis zu diesem Fix aus.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Platzierungskorrektur eines UI-Hinweises über Opt-in-Prop; ADR-0050 (Kanal wählt nur ab) bleibt unberührt.

## Changelog

- 2026-10-20: Initial spec created
