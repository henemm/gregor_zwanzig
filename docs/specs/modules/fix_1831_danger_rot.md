---
entity_id: fix_1831_danger_rot
type: bugfix
created: 2026-11-10
updated: 2026-11-10
status: draft
version: "1.0"
workflow: fix-1831-danger-rot
tags: [frontend-only, kontrast, wcag-aa, design-system, danger-token, issue-1831, epic-2508]
---

# Danger-Rot vollständig auf #a83232 (Issue #1831, Epic #2508)

## Approval

- [ ] Approved

## Purpose

Der Wechsel des Danger-Rots von `#b33a2a` auf `#a83232` ist halb stehen geblieben: Der Löschen-Knopf zeigt zwei Rottöne (Fläche alt, Schrift und Rand neu), und die Design-Seite nennt für `--g-danger` noch den alten Wert mit Kontrast 5.91. Tech-Lead-Entscheid: `#a83232` gilt (gültiger Token-Wert, höherer Kontrast 6.63, Leitprinzip „Hoher Kontrast = Lesbarkeit"). Diese Spec zieht Fläche, Fallback, Doku-Seite, Messskript und E2E-Erwartungen auf diesen einen Wert nach.

## Source

- **File:** `frontend/src/app.css`
- **Identifier:** `@property --color-destructive` (Zeile ca. 61) und `[data-slot="btn"][data-variant="destructive"]` (Zeilen ca. 518-525)

> **Schicht:** nur Frontend (SvelteKit), ein Messskript und E2E-Tests.
> **Trip/Ortsvergleich-Teilung:** nicht betroffen; die Knopf-Variante ist ein geteilter Baustein, alle Verwender (TripNewEditor, EditStagesPanelNew, PremiumSmsLinkCard, account, locations, _design) profitieren ohne eigene Änderung.
> **Mandantentrennung:** nicht betroffen (keine Nutzerdaten).
> **Kanäle / Mail:** nicht betroffen. Der E-Mail-Renderer (`src/output/renderers/email/design_tokens.py` `G_DANGER = '#b33a2a'`, `helpers.py` `ampel_red`) ist eine eigene Token-Welt, durch `tests/tdd/test_official_alert_badge_color.py` und `test_email_design_tokens.py` bewacht; Angleichen wäre eine Mail-Inhaltsänderung mit Renderer-Gate und gehört in ein eigenes Issue. Ebenso NICHT Teil: Zusammenlegen von `--g-bad` und `--g-danger`.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/app.css` (Zeile ca. 61) | MODIFY | `@property --color-destructive` initial-value auf `rgb(168, 50, 50)` |
| `frontend/src/app.css` (Zeilen ca. 518-525) | MODIFY | Destructive-Fläche `color-mix(in oklab, var(--g-danger) 10%, transparent)`, Hover 18 % statt rgba-Literal |
| `frontend/src/routes/_design/+page.svelte` (Zeile ca. 37) | MODIFY | `--g-danger` auf `#a83232`, 6.63, AA |
| `scripts/contrast_audit.py` (Zeile ca. 27) | MODIFY | `--g-danger` auf `#a83232` (Quelle der Design-Seiten-Zahlen) |
| `frontend/e2e/btn-feature-parity.spec.ts` (Zeilen ca. 104, 111) | MODIFY | Erwartung `rgb(168, 50, 50)` |
| `frontend/e2e/theme-bridge.spec.ts` (Zeilen ca. 58-68) | MODIFY | AC-4-Erwartung `rgb(168, 50, 50)` |
| `frontend/src/lib/__tests__/danger_flaeche_kontrast.test.ts` | CREATE | `node --test`, Muster `speicheranzeige_ruhe_kontrast.test.ts` |
| `.github/ci_e2e_specs.txt` | MODIFY (bedingt) | beide E2E-Specs aufnehmen, nur bei 3× grün (Filter B), sonst Folge-Issue |

## Estimated Scope

- Files: 7-8
- LoC: ca. +60 / -10 (davon ca. 50 Test)
- Effort: low, Risiko LOW (nur Farbwerte einer Knopf-Variante und Doku, keine Logik, keine Daten)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Tokens `--g-danger` (hell `#a83232`, dunkel `#ee7a7a`) | Design-Token | einzige Rot-Quelle der Knopf-Fläche |
| Tokens `--g-paper`, Card-Fläche | Design-Token | Untergründe der Kontrastmessung (hell card `#ffffff`, paper `#f6f4ee`; dunkel card `#1d1d1a`, paper `#141412`) |
| `scripts/contrast_audit.py` | Skript | Quelle der Kontrastzahlen auf der Design-Seite |
| Bestehendes `color-mix(in oklab, var(--token) N%, …)`-Muster in `app.css` (Zeilen ca. 473-515) | Muster | theme-sicherer Weg für Tönungsflächen |
| `speicheranzeige_ruhe_kontrast.test.ts` | Testmuster | Auflösung von Tokens aus `app.css` für Hell und Dunkel |
| Issue #2400 | Vorgänger | Muster „Zahlen gemessen, nicht geschätzt" |

## Implementation Details

1. **Fläche per `color-mix`** aus `--g-danger` statt rgba-Literal `rgba(179,58,42,.10)` bzw. `.18`: Ruhe 10 %, Hover 18 %. Damit gibt es keine zweite Rot-Quelle mehr, und die Fläche ist automatisch im Dunkelmodus aus dem Dunkel-Rot (`#ee7a7a`) getönt; heute ist sie dort theme-blind das alte Hell-Rot.
2. **`@property`-Fallback** `--color-destructive` auf `rgb(168, 50, 50)` angleichen (greift nur vor der Token-Auflösung).
3. **Design-Seite und `contrast_audit.py`** auf `#a83232` / 6.63; die Zahl stammt aus dem Skript, nicht aus einer Schätzung.
4. **E2E-Erwartungen** in beiden Specs auf `rgb(168, 50, 50)`.
5. **RED-Nachweis:** der neue node-Test ist gegen das heutige `app.css` rot (Literal `179, 58, 42` vorhanden, Fallback weicht ab, Hover hell auf paper mit altem Rot 4.11 unter 4,5).
6. **Gemessene Kontraste** (WCAG-Formel, Alpha-Mischung), Schrift `--g-danger` auf getönter Fläche:

| Fall | ohne Fläche | Fläche 10 % | Hover 18 % |
|---|---|---|---|
| Hell `#a83232` auf card `#ffffff` | 6.63 | 5.67 | 4.97 |
| Hell `#a83232` auf paper `#f6f4ee` | 6.03 | 5.18 | 4.56 |
| Hell alt `#b33a2a` auf paper (heutige Fläche) | 5.37 | 4.64 | 4.11 (FAIL) |
| Dunkel `#ee7a7a` auf card `#1d1d1a` | 6.20 | 5.34 | 4.64 |
| Dunkel `#ee7a7a` auf paper `#141412` | 6.76 | 5.91 | 5.15 |
| Dunkel heute (alte Hell-Fläche auf `#1d1d1a`) | - | 5.79 | 5.43 |

Engster Zielfall: Hover hell auf paper 4.56. Dunkel wird minimal schwächer als heute (5.34 statt 5.79), bleibt klar über AA.

## Expected Behavior

- **Input:** jeder `Btn variant="destructive"` (Löschen-Dialoge, Archiv, Listen-Kebab) sowie `text-destructive`/`bg-destructive` im Hell- und Dunkelmodus.
- **Output:** Fläche, Schrift und Rand erscheinen im selben Rot (`#a83232` bzw. die daraus per `color-mix` abgeleitete Tönung); im Dunkelmodus aus `#ee7a7a`. Die Design-Seite nennt den richtigen Wert samt gemessenem Kontrast.
- **Side effects:** Die Löschen-Fläche wird im Hellmodus minimal rötlicher-neutral statt rostig-orange; im Dunkelmodus erstmals im Dunkel-Rot getönt.

## Definition of Done

- Jeder Löschen-Knopf zeigt in Hell- und Dunkelmodus Fläche, Schrift und Rand aus demselben Rot (`--g-danger`); im Web-CSS gibt es keine zweite Rot-Quelle `#b33a2a` mehr.
- Schriftkontrast auf der getönten Fläche ≥ 4,5:1 in allen acht gemessenen Fällen (AC-3).
- Design-Seite nennt `--g-danger` `#a83232` mit 6.63, Zahl aus `scripts/contrast_audit.py`.
- Neuer node-Test und beide angepassten E2E-Specs grün; CI-Positivliste nur bei 3× grün ergänzt, sonst Folge-Issue angelegt.
- Auf Staging per `/e2e-verify` nachgewiesen, nach Produktion ausgeliefert, Selftest Exit 0.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer im Hellmodus sieht einen Löschen-Knopf (`Btn variant="destructive"`) / When der Knopf in Ruhe und beim Überfahren dargestellt wird / Then stammen Fläche, Schrift und Rand aus demselben Rot `#a83232` (Fläche als 10-%- bzw. 18-%-Tönung daraus per `color-mix`), und im Web-CSS (`app.css`) kommt der alte Wert `#b33a2a` bzw. `rgb(179, 58, 42)` nirgends mehr vor.
  - Test: Verhaltensnachweis am echten Knopf: E2E `btn-feature-parity.spec.ts` liest die berechnete Schrift-, Rand- und Flächenfarbe (`getComputedStyle`) und prüft, dass alle drei aus `rgb(168, 50, 50)` stammen (Fläche = 10-%-Mischung davon). Ergänzend rechnet `danger_flaeche_kontrast.test.ts` die aufgelöste Flächenfarbe aus den Tokens von `app.css` (Muster `speicheranzeige_ruhe_kontrast.test.ts`), statt nur nach einem Literal zu suchen.

- **AC-2:** Given ein Nutzer im Dunkelmodus sieht einen Löschen-Knopf / When die Fläche des Knopfes berechnet wird / Then ist sie aus dem Dunkel-Rot `--g-danger` (`#ee7a7a`) getönt und nicht mehr aus dem Hell-Rot `#a83232` bzw. `#b33a2a`.
  - Test: `danger_flaeche_kontrast.test.ts` löst `--g-danger` im Dark-Block auf und prüft, dass die Fläche aus `var(--g-danger)` gemischt wird (kein themenblindes Literal); die berechnete Mischfarbe entspricht `#ee7a7a` bei 10 %.

- **AC-3:** Given der Löschen-Knopf auf Card- oder Papier-Untergrund in Hell und Dunkel / When die Schrift `--g-danger` auf der getönten Fläche (10 % Ruhe, 18 % Hover) gemessen wird / Then liegt das Kontrastverhältnis in allen acht Fällen bei mindestens 4,5:1: hell card 5.67 / 4.97, hell paper 5.18 / 4.56, dunkel card 5.34 / 4.64, dunkel paper 5.91 / 5.15.
  - Test: `danger_flaeche_kontrast.test.ts` rechnet WCAG-Kontrast mit Alpha-Mischung gegen die aus `app.css` aufgelösten Tokens (Schwelle 4,5, engster Fall hell paper Hover 4.56).

- **AC-4:** Given die Seite wird geladen, bevor die Tokens aufgelöst sind / When der Fallback von `--color-destructive` (`@property`-initial-value) ausgewertet wird / Then ist er `rgb(168, 50, 50)` und damit gleich dem hellen `--g-danger`.
  - Test: `danger_flaeche_kontrast.test.ts` liest den initial-value und vergleicht ihn mit `--g-danger` aus dem hellen `:root`-Block; E2E `theme-bridge.spec.ts` AC-4 liest `--color-destructive` am Element.

- **AC-5:** Given ein Nutzer öffnet die Design-Seite `/_design` / When er die Kontrasttabelle für `--g-danger` im Hellmodus liest / Then steht dort `#a83232` mit Kontrast 6.63 (AA), gemessen über `scripts/contrast_audit.py` und nicht geschätzt.
  - Test: Nutzernachweis ist die Design-Seite im Staging (angezeigter Wert `#a83232` / 6.63 ablesen); die Zahl selbst stammt aus `scripts/contrast_audit.py`, dessen Ausgabe für `--g-danger` 6.63 ergeben muss.

- **AC-6:** Given die beiden E2E-Specs `btn-feature-parity.spec.ts` und `theme-bridge.spec.ts` / When sie gegen Staging laufen / Then erwarten beide `rgb(168, 50, 50)` und sind grün; sie werden nur dann in `.github/ci_e2e_specs.txt` aufgenommen, wenn sie dreimal hintereinander grün waren, sonst entsteht ein Folge-Issue.
  - Test: beide Specs dreimal laufen lassen, Ergebnis dokumentieren; Positivliste nur bei 3× grün ändern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN das heutige `app.css` WHEN `danger_flaeche_kontrast.test.ts` läuft THEN rot (Literal `179, 58, 42` und abweichender Fallback), nach dem Fix grün.
- [ ] Test 2: GIVEN Hell und Dunkel, card und paper WHEN Schrift auf 10-%- und 18-%-Fläche gemessen wird THEN alle acht Werte mindestens 4,5:1.
- [ ] Test 3: GIVEN der Dark-Block WHEN die Destructive-Fläche aufgelöst wird THEN stammt sie aus `--g-danger` (`#ee7a7a`).
- [ ] Test 4: GIVEN `btn-feature-parity.spec.ts` und `theme-bridge.spec.ts` WHEN sie gegen Staging laufen THEN grün mit `rgb(168, 50, 50)`.
- [ ] Test 5: GIVEN `scripts/contrast_audit.py` WHEN ausgeführt THEN `--g-danger` `#a83232` = 6.63.

Aufruf Test 1-3: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/__tests__/danger_flaeche_kontrast.test.ts`. Keine Mocks.

## Known Limitations

- Der E-Mail-Renderer behält `#b33a2a` (eigenes Issue, Renderer-Gate).
- `--g-bad` und `--g-danger` bleiben Duplikate; Zusammenlegen ist nicht Teil dieses Issues.
- Dunkel wird der Schriftkontrast auf der Fläche minimal schwächer (5.34 statt 5.79), bleibt über AA.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Vollzug eines schon getroffenen Token-Werts (`#a83232`) nach dem Leitprinzip „Hoher Kontrast = Lesbarkeit"; keine neue Entscheidungsfläche, kein neues Token.

## Changelog

- 2026-11-10: Initial spec created (Issue #1831, Epic #2508).
