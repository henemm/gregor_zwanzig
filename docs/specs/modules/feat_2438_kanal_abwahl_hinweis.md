---
entity_id: feat_2438_kanal_abwahl_hinweis
type: module
created: 2026-10-19
updated: 2026-10-19
status: draft
version: "1.0"
tags: [frontend, editor, hinweis, kanaele, trip, ortsvergleich, adr-0050]
workflow: feat-2438-kanal-abwahl-hinweis
---

# Feature #2438 (S2b von #2422, Epic #2507): Editor-Hinweis „Kanal kann nur abwählen" (B6)

## Approval

- [ ] Approved

## Purpose

In den Kanal-Reitern (E-Mail, Telegram, SMS) des Werte-Reiters kann man Metriken nur abwählen, nie
hinzufügen. Was in der Grundauswahl nicht gewählt ist, erscheint in keinem Kanal (ADR-0050,
Regel 1–3). Der Editor sagt das bisher nicht; der Nutzer sucht eine fehlende Metrik vergeblich in
„Aus in diesem Kanal". Diese Spec ergänzt eine beschreibende Hinweiszeile an genau dieser Stelle —
im geteilten Baustein, also identisch in Trip- und Ortsvergleich-Editor. Keine Verhaltens- und keine
Datenänderung.

## Source

- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` (Schicht: Frontend)
- **Identifier:** Gruppe `wm2-aus-gruppe`; Text aus `frontend/src/lib/components/shared/layout-tab/ltChannels.ts::ltKanalAbwahlHinweisText`

## Scope

Affected Files (alle Frontend):

- `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` — neue reine Textfunktion
- `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` — Hinweiszeile
- `frontend/src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts` — neu
- `frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts` — erweitert

## Estimated Scope

- **LoC:** ~60
- **Files:** 4
- **Effort:** low

## Test Plan

- Unit (`kanal_abwahl_hinweis.test.ts`, `node --test`): exakter Wortlaut der Textfunktion (AC-6); Rendering von `WeatherV2Reihenfolge` mit `offColumns=[]` und befüllt (AC-3), ohne `offColumns` (AC-4), beide `context`-Werte (AC-2).
- E2E (Staging, `kanal-grenzen-und-hinweise.staging.spec.ts`): Hinweis sichtbar im Trip- und im Ortsvergleich-Editor je Kanal-Reiter (AC-1, AC-2); 320/375 px ohne Überlauf, Kontrast (AC-5).
- Regression: `channelOffGroupListBuilding.test.ts` und `kanal-abwahl-bleibt-reversibel.staging.spec.ts` bleiben grün (AC-7).
- Fresh-Eyes-Inspektion der Screenshots (UI-Änderung).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherV2Reihenfolge.svelte` | Komponente | wird in Trip-Kanalsicht, Vergleich-Übersicht und Vergleich-Ausblick eingebunden; `offColumns !== undefined` ⇔ Kanal-Sicht |
| `ltChannels.ts` (`ltCapNoteText`) | Muster | Hinweistext als reine, ohne Renderharness testbare Funktion |
| ADR-0050 | Entscheidung | Grundauswahl = Maximum, Kanal wählt nur ab |

## Implementation Details

```
ltKanalAbwahlHinweisText(): string
  → "Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist.
     Was dort fehlt, erscheint in keinem Kanal."

WeatherV2Reihenfolge.svelte, innerhalb {#if offColumns !== undefined} / .aus-gruppe:
  nach der {#each offColumns}-Liste, IMMER (auch bei leerer Gruppe):
  <p class="aus-hinweis" data-testid="wm2-aus-hinweis">{ltKanalAbwahlHinweisText()}</p>
```

Darstellung: Textfarbe mit Kontrast ≥ 4.5:1 (kein `--g-ink-4`), Zeilenumbruch, lesbar bis 320 px.
Sichtbarkeit dauerhaft statt bedingt: die Kanal-Sicht kennt global Abgewähltes nicht; die Regel
gilt unabhängig davon, ob gerade etwas fehlt. Die globale Grundauswahl-Sicht (ohne `offColumns`)
bekommt den Hinweis nicht. „Grundauswahl" ist die in der UI sichtbare Beschriftung („02 — Grundauswahl").

## Expected Behavior

- **Input:** Nutzer öffnet im Trip- oder Ortsvergleich-Editor den Werte-Reiter und wechselt in einen Kanal-Reiter.
- **Output:** Unter der Gruppe „Aus in diesem Kanal" steht der Hinweis, in jedem Kanal-Reiter gleich lautend.
- **Side effects:** keine; kein Schreibzugriff, keine Persistenz, keine Auslieferungsänderung.

## Acceptance Criteria

- **AC-1:** Given ein Trip im Editor, Werte-Reiter, Kanal-Reiter E-Mail/Telegram/SMS / When der Nutzer den Reiter öffnet / Then steht unter „Aus in diesem Kanal" der Hinweis „Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal." (`wm2-aus-hinweis`)
  - Test: E2E auf Staging im Trip-Editor, je Kanal-Reiter Text sichtbar.
- **AC-2:** Given ein Ortsvergleich im Editor, Werte-Reiter, Kanal-Reiter / When der Nutzer den Reiter öffnet / Then erscheint derselbe Hinweis, vom selben Baustein erzeugt (keine Compare-Sonderkomponente)
  - Test: E2E auf Staging im Ortsvergleich-Editor + Unit-Test rendert den Baustein mit beiden `context`-Werten.
- **AC-3:** Given ein Kanal-Reiter, in dem keine Metrik abgewählt ist (leere Aus-Gruppe) / When der Nutzer ihn öffnet / Then ist der Hinweis trotzdem sichtbar
  - Test: Unit-Test mit `offColumns=[]`.
- **AC-4:** Given die globale Grundauswahl-Ansicht (kein Kanal-Reiter) / When der Nutzer sie öffnet / Then erscheint dort kein Abwahl-Hinweis
  - Test: Unit-Test ohne `offColumns` ⇒ `wm2-aus-hinweis` fehlt.
- **AC-5:** Given Handybreite 320 px und 375 px / When der Hinweis angezeigt wird / Then umbricht er ohne horizontales Scrollen und hat Kontrast ≥ 4.5:1 zum Hintergrund
  - Test: Playwright-Messung (scrollWidth ≤ clientWidth, berechnete Farbe) bei 320 und 375 px; Fresh-Eyes-Inspektion der Screenshots.
- **AC-6:** Given der Hinweistext / When er geprüft wird / Then enthält er nur Beschreibung der Regel, keine Handlungsempfehlung und keine Kanal-Zuordnung (gilt unverändert in allen drei Kanal-Reitern E-Mail/Telegram/SMS; Premium-SMS hat keinen eigenen Reiter und sendet den SMS-Text, ADR-0049; Telegram-Kurzform folgt SMS)
  - Test: Unit-Test der Textfunktion (exakter Wortlaut, kein Imperativ/„solltest").
- **AC-7:** Given die bestehende Aus-Gruppe und Wiederherstellen-Funktion / When der Hinweis ergänzt ist / Then verhalten sich `wm2-aus-row`, „Wiederherstellen" und Kanal-Abwahl unverändert
  - Test: bestehende `channelOffGroupListBuilding.test.ts` und `kanal-abwahl-bleibt-reversibel.staging.spec.ts` bleiben grün.

## Known Limitations

- Hinweis ist dauerhaft sichtbar, nicht bedingt auf „es fehlt tatsächlich etwas" (bräuchte neue Datenführung; bewusst nicht Teil).
- Der Ortsvergleich-Ausblick (`CompareOutlookLayoutControls`) nutzt denselben Baustein und zeigt den Hinweis daher ebenfalls.
- B9 ist nicht Teil (erledigt in S2a).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; setzt ADR-0050 (Regel 1–3) im Editor sichtbar um
- **Rationale:** reine Erklärung einer bestehenden Regel, kein neues Verhalten

## Changelog

- 2026-10-19: Initial spec created (#2438)
