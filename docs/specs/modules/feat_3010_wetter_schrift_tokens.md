---
entity_id: feat_3010_wetter_schrift_tokens
type: refactor
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3010-wetter-schrift-tokens
tags: [design-system, tokens, waechter, epic-2913]
---

# Wetter-Schrift aus Schrift-Tokens statt Abstands-Tokens (#3010)

## Approval

- [ ] Approved

## Purpose

Schriftgrößen in den Bausteinen (Wetter-Reiter, Stille Stunden, EinstellTabelle) kommen heute aus Abstands-Tokens (`font-size: var(--g-s-3|4)`). Das ist unsichtbar falsch, weil der Bausteine-Wächter jedes `var(--g-*)` akzeptiert. Die Größen werden pixelgleich auf neue Schrift-Stufen umgestellt, ein Wächter färbt jeden Rückfall rot (ADR-0112, Epic #2913).

## Source

- **File:** `frontend/src/app.css`
- **Identifier:** Schriftskala `--g-text-*` in `:root` (neu: `--g-text-12px`, `--g-text-16px`)

## Scope

### In Scope

- Neue Stufen `--g-text-12px` (12 px) und `--g-text-16px` (16 px) in `:root` von `frontend/src/app.css` bei der Schriftskala; Zeile je Stufe in der Schrift-Tabelle von `docs/reference/design_system.md`. Das Dunkel-Theme überschreibt nur Farben, ein Eintrag genügt.
- Alle 9 Fundstellen pixelgleich umstellen: MetrikZeile (3x, 12 px), VorlageKarte (1x, 12 px), GrenzenEditor (3x: 12, 12, mobil 16 px), StilleStunden (mobil 16 px), EinstellTabelle (12 px).
- Neue Wächter-Regel in `tokenGruende` (`frontend/src/lib/__tests__/bausteine_waechter_regeln.ts`): `font-size` mit `var(--g-s-` ist ein Grund; gilt für alle Baustein-Ordner (atoms, molecules, organisms). Hart, Bestand 0, keine Ratsche.
- Wächter-Tests in `frontend/src/lib/__tests__/bausteine_waechter.test.ts` (rot bei Rückfall, grün mit `--g-text-*`).
- Nachweis: berechnete Schriftgröße im Browser vorher = nachher; Ganzseitenbild Mockup gegen Staging.

### Nicht-Ziele

- Mockup-Abweichungen angleichen (VorlageKarte 11,5 px, GrenzenEditor-Beschriftungen 10 px bleiben wie heute; 10 px widerspräche zudem dem Leitprinzip Lesbarkeit).
- Andere `--g-size-*`-font-sizes umstellen (14, 12,5, 18 px usw.).
- Die 16 px der mobilen Eingabefelder ändern (iOS-Zoom-Schutz bleibt).

> Schicht: ausschließlich Frontend (`frontend/src/...`). Kein Trip/Vergleich-Pendant betroffen (Bausteine sind bereits geteilt), keine Nutzerdaten, keine Briefing-/Alarm-Inhalte, daher keine Kanalwirkung.

## Estimated Scope

- **LoC:** ~+60/-12
- **Files:** 10 (app.css, design_system.md, 5 Komponenten, Wächter-Regeln, Wächter-Test, ggf. Ausnahmen-Liste)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/app.css | MODIFY | Stufen `--g-text-12px`, `--g-text-16px` |
| docs/reference/design_system.md | MODIFY | Zeilen in der Schrift-Tabelle |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | 3 Fundstellen |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | MODIFY | 1 Fundstelle |
| frontend/src/lib/components/organisms/wetter-tab/GrenzenEditor.svelte | MODIFY | 3 Fundstellen |
| frontend/src/lib/components/organisms/zustellung-tab/StilleStunden.svelte | MODIFY | 1 Fundstelle (mobil) |
| frontend/src/lib/components/molecules/EinstellTabelle.svelte | MODIFY | 1 Fundstelle |
| frontend/src/lib/__tests__/bausteine_waechter_regeln.ts | MODIFY | Regel in `tokenGruende` |
| frontend/src/lib/__tests__/bausteine_waechter.test.ts | MODIFY | Tests rot/grün |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0112 | ADR | Oberflächen nur aus Design-System-Bausteinen, Werte über `var(--g-*)` |
| docs/reference/design_system.md | Doku | Schriftskala, Leitprinzip Lesbarkeit |
| bausteine_waechter_regeln.ts | Wächter | `tokenGruende`, Ausnahmen-Ratsche |
| fix_2913_metrikliste_mockup, feat_2913_abgleich_ganzseite | Specs | Bestehende Mess-Zusicherungen am Wetter-Reiter bleiben unverändert grün |
| playwright.2913-metrikliste.staging.config.ts, Agent mockup-bildpruefer | Test-Werkzeug | Ganzseitenbild gegen Staging |

## Implementation Details

1. Wächter-Regel und Tests zuerst (rot gegen den Bestand mit 9 Fundstellen).
2. Stufen in `app.css` anlegen: `--g-text-12px: 12px;` und `--g-text-16px: 16px;` direkt bei `--g-text-xs..5xl`; Tabelle in `design_system.md` ergänzen (Zwischenstufen: Kleinschrift 12 px, Zoom-Schutz 16 px).
3. 9 Fundstellen: `var(--g-s-3)` wird `var(--g-text-12px)`, `var(--g-s-4)` wird `var(--g-text-16px)`; Werte identisch, keine Layout-Änderung.
4. Wächter-Regel: in `tokenGruende(eigenschaft, wertRoh)` bei `eigenschaft === 'font-size'` und Wert mit `var(--g-s-` ein Grund "Schriftgröße aus Abstands-Token, nur --g-text-*".
5. Nachweis vor/nach per berechneter Schriftgröße; danach Ganzseitenbild Staging.

## Expected Behavior

- **Input:** Wetter-Reiter, Zustellung (Stille Stunden), EinstellTabelle in Hell und Dunkel, Breiten 1280/1024/390.
- **Output:** Optisch unverändert: gleiche Schriftgrößen wie vorher.
- **Side effects:** Keine; Wächter meldet künftig Schrift aus Abstands-Token.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter-Test (`frontend/src/lib/__tests__/bausteine_waechter.test.ts`): Fixture mit `font-size: var(--g-s-3)` ist rot, mit `var(--g-text-12px)` grün; echter Quellbaum ohne Fund der neuen Regel (AC-5, AC-6).
- [ ] Token-Test: `--g-text-12px` = 12px und `--g-text-16px` = 16px in `:root` von `app.css` (AC-1).
- [ ] Staging-E2E (Playwright, berechnete Schriftgröße): MetrikZeile/VorlageKarte/EinstellTabelle 12 px, mobile Eingabefelder 16 px (AC-2 bis AC-4).
- [ ] Ganzseitenbild Mockup gegen Staging mit `mockup-bildpruefer` (AC-7).

## Acceptance Criteria

- **AC-1:** Given die App ist im Hell- oder Dunkel-Theme geladen / When die berechnete Schriftgröße der Tokens `--g-text-12px` und `--g-text-16px` am Wurzelelement gelesen wird / Then liefern sie 12 px und 16 px.
  - Test: Browser-Test liest `getComputedStyle(document.documentElement)` je Token in beiden Themes.

- **AC-2:** Given der Wetter-Reiter eines Trips und eines Orts-Briefings ist geöffnet / When die berechnete Schriftgröße von Knopf, Untertitel, Aktions-Label und Erklärtext einer Metrik-Zeile sowie der VorlageKarte-Option gemessen wird / Then beträgt sie je 12 px, identisch zum Stand vor der Umstellung.
  - Test: Staging-Playwright misst `font-size` per `getComputedStyle` vorher und nachher und vergleicht.

- **AC-3:** Given die Mobil-Ansicht (390 px) mit GrenzenEditor und Stille Stunden / When die Eingabefelder fokussiert und gemessen werden / Then bleibt die Schriftgröße 16 px (kein iOS-Zoom), Gruppenname und Feldlabel bleiben bei 12 px.
  - Test: Staging-Playwright bei 390 px misst `font-size` der Eingabefelder und Labels.

- **AC-4:** Given die EinstellTabelle wird dargestellt (Zustellung und Vorschauseite) / When die Schriftgröße des Untertitels gemessen wird / Then ist sie 12 px wie vorher.
  - Test: Browser-Test misst `getComputedStyle` des Untertitels im Zustand vor und nach der Umstellung.

- **AC-5:** Given ein Baustein in atoms, molecules oder organisms setzt `font-size: var(--g-s-3)` / When der Bausteine-Wächter läuft / Then schlägt er mit dem Grund "Schriftgröße aus Abstands-Token" fehl, und mit `font-size: var(--g-text-sm)` oder `var(--g-text-12px)` läuft er grün.
  - Test: Wächter-Test füttert beide Varianten in allen drei Baustein-Ordnern und erwartet rot bzw. grün; vor der Umstellung ist der Quellbaum-Test mit 9 Fundstellen rot.

- **AC-6:** Given alle 9 Fundstellen sind umgestellt / When der Wächter den echten Quellbaum prüft / Then meldet er keine Schriftgröße aus Abstands-Token mehr (Bestand 0), und alle bestehenden Wächter-Tests bleiben grün.
  - Test: Quellbaum-Wächter-Test über alle Baustein-Ordner, 0 Treffer der neuen Regel.

- **AC-7:** Given die Ganzseitenbilder Mockup gegen Staging (Trip und Orte, DE und EN, 1280/1024/390 px) / When der Bildprüfer sie vor und nach der Umstellung vergleicht / Then zeigt sich keine Änderung der Schriftgrößen oder Zeilenhöhen (Erklärtext-Zeile höchstens 124 px).
  - Test: `playwright.2913-metrikliste.staging.config.ts` nimmt die Paare auf, Agent mockup-bildpruefer bewertet; Soll/Ist-Bild geht an den PO.

## Known Limitations

- Die Abweichungen zum Mockup (11,5 px in VorlageKarte, 10 px in GrenzenEditor) bleiben bestehen und werden bei Bedarf als eigenes Issue behandelt.
- Das Ganzseitenbild läuft nur gegen Staging nach dem Push, nicht in CI.

## Definition of Done

- [ ] Spec freigegeben (ACs auf Deutsch).
- [ ] Wächter-Tests zuerst rot (Bestand 9), nach Umstellung grün.
- [ ] Stufen in `app.css` und `design_system.md`; 9 Fundstellen umgestellt, Bestand 0.
- [ ] Berechnete Schriftgrößen vorher = nachher belegt.
- [ ] Ganzseitenbild Staging ohne Größenänderung, Bildpruefer-Urteil liegt vor.
- [ ] Alle 6 CI-Checks grün, Prod-Deploy und Selftest erfolgreich.
- [ ] Soll/Ist-Bild an den PO; Issue #3010 geschlossen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0112 (keine neue nötig)
- **Rationale:** Präzisiert nur die bestehende Regel "Schrift über `var(--g-*)`": für `font-size` gelten ausschließlich Schrift-Tokens. Kein Abweichen von einer Entscheidung.

## Changelog

- 2026-11-19: Initial spec created
