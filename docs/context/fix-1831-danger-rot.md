# Context: fix-1831-danger-rot

## Request Summary
Issue #1831 (Epic #2508): Der Wechsel des Danger-Rots von `#b33a2a` auf `#a83232` ist halb stehen geblieben. Der Löschen-Knopf zeigt zwei Rottöne (Fläche alt, Schrift/Rand neu), und die Design-Seite nennt für `--g-danger` den alten Wert mit Kontrast 5.91. Tech-Lead-Entscheid: `#a83232` gilt (gültiger Token-Wert, höherer Kontrast 6.63, Leitprinzip „Hoher Kontrast = Lesbarkeit“).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/app.css:61` | `@property --color-destructive` initial-value `rgb(179, 58, 42)`: alter Wert (Fallback vor Token-Auflösung) |
| `frontend/src/app.css:82` | `--color-destructive: var(--g-danger)`: Brücke, korrekt |
| `frontend/src/app.css:224-225` | Hell: `--g-danger`/`--g-bad` = `#a83232` (gültig) |
| `frontend/src/app.css:308-309` | Dunkel: `--g-danger`/`--g-bad` = `#ee7a7a` |
| `frontend/src/app.css:518-525` | `[data-variant="destructive"]` Fläche `rgba(179,58,42,.10)`, Hover `.18`: alt, und im Dunkelmodus gleich (theme-blind) |
| `frontend/src/routes/_design/+page.svelte:37` | Hell-Tabelle `--g-danger` `#b33a2a` 5.91: falsch |
| `scripts/contrast_audit.py:27` | Quelle der Design-Seiten-Zahlen, führt `--g-danger` noch als `#b33a2a` |
| `frontend/e2e/btn-feature-parity.spec.ts:104,111` | erwartet `rgb(179, 58, 42)` (rot) |
| `frontend/e2e/theme-bridge.spec.ts:58-68` | AC-4 erwartet `rgb(179, 58, 42)` (rot) |
| `.github/ci_e2e_specs.txt` | beide Specs bisher nicht in der CI-Positivliste |

## Existing Patterns
- Hover-/Tönungsflächen werden schon per `color-mix(in oklab, var(--token) N%, …)` aus dem Token abgeleitet (app.css:473, 484, 488, 515). Das ist der theme-sichere Weg für die Destructive-Fläche.
- Design-Seite: Kontrastzahlen stammen aus `scripts/contrast_audit.py` (Hell: card #ffffff; Dunkel: card #1d1d1a), nicht geschätzt (#2400-Muster).

## Dependencies
- Upstream: Tokens `--g-danger` (hell/dunkel), `--g-paper`/Card als Untergrund.
- Downstream: alle `Btn variant="destructive"` (Löschen-Dialoge, Archiv, Listen-Kebab), Tailwind-Klassen `text-destructive`/`bg-destructive` über `--color-destructive`.

## Existing Specs
- `docs/specs/modules/fix_2879_kontrast_wcag_aa.md`, `ink4_kontrast_2371.md`: Muster für Kontrast-Fixes mit Messung.
- `docs/specs/modules/design_system_drift_fixes.md`, `rework_2881_design_system_bereinigung.md`: Token-Drift.

## Risks & Considerations
- Fläche per `color-mix` aus `--g-danger` ändert auch den Dunkelmodus (heute: altes Hell-Rot 10 % auf Dunkel). Schriftkontrast `--g-danger` auf der getönten Fläche in beiden Themes nachrechnen (≥ 4,5:1).
- `@property`-Fallback greift nur vor Token-Auflösung; angleichen genügt.
- Zwei E2E-Specs nach Fix grün → Kandidaten für die CI-Positivliste (Filter B: 3× grün), optional im selben PR.
- `--g-bad` und `--g-danger` sind Duplikate; Zusammenlegen ist NICHT Teil dieses Issues.

## Analysis

### Type
Bug (Token-Wechsel `#b33a2a` → `#a83232` unvollständig). Wert-Entscheid steht: `#a83232` (Tech Lead, siehe oben).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/app.css:61` | MODIFY | `@property --color-destructive` initial-value → `rgb(168, 50, 50)` |
| `frontend/src/app.css:518-525` | MODIFY | Destructive-Fläche `color-mix(in oklab, var(--g-danger) 10%, transparent)`, Hover 18 % — theme-sicher statt rgba-Literal |
| `frontend/src/routes/_design/+page.svelte:37` | MODIFY | `--g-danger` → `#a83232`, 6.63, AA |
| `scripts/contrast_audit.py:27` | MODIFY | `--g-danger` → `#a83232` (Quelle der Design-Seiten-Zahlen) |
| `frontend/e2e/btn-feature-parity.spec.ts:104,111` | MODIFY | Erwartung `rgb(168, 50, 50)` |
| `frontend/e2e/theme-bridge.spec.ts:58-68` | MODIFY | AC-4-Erwartung `rgb(168, 50, 50)` |
| `frontend/src/lib/__tests__/danger_flaeche_kontrast.test.ts` | CREATE | `node --test`: liest app.css, prüft (a) kein `179, 58, 42` mehr im Web-CSS, (b) `@property`-Fallback == `--g-danger` hell, (c) Schrift `--g-danger` auf getönter Fläche (10 %/18 %) ≥ 4,5:1 in Hell und Dunkel (Muster `speicheranzeige_ruhe_kontrast.test.ts`) |
| CI-Positivliste `ci_e2e_specs.txt` | MODIFY (optional) | beide Specs aufnehmen, sofern 3× grün (Filter B) |

### Kontrast-Messung (WCAG-Formel, Alpha-Mischung)
| Fall | ohne Fläche | Fläche 10 % | Hover 18 % |
|---|---|---|---|
| Hell `#a83232` auf card `#ffffff` | 6.63 | 5.67 | 4.97 |
| Hell `#a83232` auf paper `#f6f4ee` | 6.03 | 5.18 | 4.56 |
| Hell alt `#b33a2a` auf paper (heutige Fläche) | 5.37 | 4.64 | **4.11 (FAIL)** |
| Dunkel `#ee7a7a` auf card `#1d1d1a` | 6.20 | 5.34 | 4.64 |
| Dunkel `#ee7a7a` auf paper `#141412` | 6.76 | 5.91 | 5.15 |
| Dunkel heute (alte Hell-Fläche auf `#1d1d1a`) | — | 5.79 | 5.43 |

Alle Zielwerte ≥ 4,5:1. Engster Fall: Hover hell auf paper 4.56 → Test mit Schwelle 4,5 sichert das. Dunkel wird minimal schwächer als heute (5.34 statt 5.79), bleibt klar über AA, und die Fläche ist erstmals im Dunkel-Rot getönt.

### Scope Assessment
- Files: 6–8
- Estimated LoC: +60/-10 (davon ~50 Test)
- Risk Level: LOW — nur Farbwerte einer Knopf-Variante und Doku; keine Logik, keine Daten.

### Technical Approach
1. `color-mix` aus `--g-danger` statt rgba-Literal (bestehendes Muster app.css:473 ff.): keine zweite Rot-Quelle mehr, automatisch richtig im Dunkelmodus.
2. `@property`-Fallback angleichen.
3. Design-Seite + `contrast_audit.py` auf `#a83232`/6.63 (gemessen, oben).
4. Zwei E2E-Erwartungen auf `rgb(168, 50, 50)`; RED-Nachweis: neuer node-Test rot gegen heutiges app.css (Literal + Fallback).
5. CI-Positivliste: beide Specs aufnehmen, wenn im PR 3× grün; sonst Folge-Issue.

### Abgrenzung (bewusst NICHT Teil)
- E-Mail-Renderer (`src/output/renderers/email/design_tokens.py` `G_DANGER = '#b33a2a'`, `helpers.py` `ampel_red`): eigene Token-Welt der Mail, durch `tests/tdd/test_official_alert_badge_color.py:88` und `test_email_design_tokens.py:49` ausdrücklich gegen Kollateraländerung bewacht. Angleichen wäre Mail-Inhaltsänderung mit Renderer-Gate → eigenes Issue.
- Zusammenlegen `--g-bad`/`--g-danger`.

### Dependencies
Verwender `Btn variant="destructive"`: TripNewEditor, EditStagesPanelNew, PremiumSmsLinkCard, account, locations, _design. Alle profitieren ohne eigene Änderung.

### Open Questions
- keine (Wert entschieden; Mail-Abgrenzung ist Tech-Lead-Entscheid)
