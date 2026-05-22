# Context: Bug AP-010d — Hardcodierte font-sizes in WeatherMetricsPreviewCard.svelte

## Request Summary
Issue #329: Die 4 hardcodierten `font-size`-rem-Werte in `WeatherMetricsPreviewCard.svelte` durch die `--g-text-*` Typografie-Tokens des Design-Systems ersetzen (AP-010-Compliance). Reine CSS-Drift-Bereinigung, keine Logik-Änderung.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | **Einzige zu ändernde Datei** — 4 font-size-Treffer im `<style>`-Block (Z. 55, 60, 74, 79) |
| `frontend/src/app.css` (Z. 109–117) | Single Source of Truth der `--g-text-*` Skala: xs=11px, sm=13px, md=15px |
| `docs/design-system/TOKENS.md` (Z. 82–90) | Token-Dokumentation der Typografie-Skala |
| `docs/design-system/ANTI-PATTERNS.md` → AP-010 | Definition des Anti-Patterns "hardcodierte font-size" |
| `frontend/src/lib/components/trip-detail/index.ts` (Z. 11) | Re-Export der Komponente (keine Änderung nötig) |

## Konkrete Fundstellen & Token-Mapping
| Zeile | Selektor | Ist-Wert | Soll-Token | Token-px |
|-------|----------|----------|-----------|----------|
| 55 | `.card-title` | `1rem` | `var(--g-text-md)` | 15px |
| 60 | `.empty-state` | `0.875rem` | `var(--g-text-sm)` | 13px |
| 74 | `:global(.chips .chip)` | `0.75rem` | `var(--g-text-xs)` | 11px |
| 79 | `.edit-link` | `0.875rem` | `var(--g-text-sm)` | 13px |

## Existing Patterns
- **`var(--g-text-*)`-Nutzung** ist im Code etabliert: `EditWeatherSection.svelte`, `StageCard.svelte`, `AlertRuleRow.svelte`, `Select.svelte`, `Checkbox.svelte`, sowie `app.css` selbst (Btn-Slots Z. 203–206).
- **Direkte Vorlagen (gleiche AP-Drift-Reihe):**
  - `docs/specs/modules/issue_323_hex_fallbacks_cleanup.md` (AP-007 Hex-Literale → Tokens)
  - `docs/specs/modules/bug_324_magic_pixel_spacing.md` (AP-008 Magic-Pixel → `--g-s-*`)
  - `docs/specs/modules/issue_322_wicon_komponente.md` (AP-009 Emojis → SVG)

## Dependencies
- **Upstream:** `--g-text-*` CSS-Custom-Properties aus `app.css` (global, im `<style>`-Block direkt verfügbar — auch in `:global()`-Selektoren).
- **Downstream:** Komponente wird im Trip-Detail Overview-Tab (rechte Spalte, Epic #135 Step 5) gerendert. Keine API-/Daten-Berührung.

## Existing Specs
- `docs/specs/modules/epic_135_step5_right_column.md` — Ursprungs-Spec der Komponente (§3)
- Vorlagen siehe „Existing Patterns" oben.

## Risks & Considerations
- **px-Drift (wichtigster Punkt):** Die rem-Werte entsprechen 16/14/12px, die Tokens liefern 15/13/11px → jeder Wert wird **1px kleiner**. Das ist die *beabsichtigte* Konsequenz der Vereinheitlichung auf die Token-Skala, kein Bug. AC-2 ("Layout unverändert") meint das Layout-Konzept, nicht pixelgenaue Identität. Sollte beim Fresh-Eyes-Check beobachtet, dem User aber transparent gemacht werden.
- Issue-Annahme „0.6875rem nächster Token" für `0.75rem` ist gegenstandslos — es gibt keinen 0.6875rem-Token; `--g-text-xs` (11px) ist die korrekte und kleinste Stufe.
- **Trivialer Umfang (~4 LoC):** Kein spec-writer nötig (Memory: kein Spec-Writer für Triviales). Issue enthält bereits gültiges AC-N-Format (AC-1/AC-2) — der `workflow_gate`-Hook ist damit zufrieden.
- Reine Frontend-CSS-Änderung → Post-Push: Staging-Validierung per visuellem Vergleich (Playwright/Screenshot), kein Backend-/Mail-Test.

## Analyse-Ergebnis (Phase 2)

### Befund
Root Cause ist trivial und vollständig geklärt — kein bug-intake-Agent / keine Explore-Agents nötig (Schwergewichts-Prozess wäre Theater bei 4 Zeilen CSS). Die Komponente (Epic #135 Step 5) wurde vor der Token-Disziplin geschrieben und nutzt feste rem-Werte statt der Typografie-Skala.

### Bestehende Tests
- `frontend/e2e/trip-detail-overview-right.spec.ts` (324 Z.) prüft **nur** Sichtbarkeit, Preset-Inhalt, Chip-Anzeige und Edit-Link-Navigation — **keine** font-sizes / kein `getComputedStyle`. → Bleibt nach der Änderung garantiert grün, kein Funktions-Regress.
- Kein Selektor (`.card-title`/`.chip`/`.edit-link`) wird außerhalb der Datei überschrieben; keine Media-Queries im `<style>`-Block. Ersetzung ist isoliert.

### Entscheidung: Fallbacks weglassen
`var(--g-text-md)` **ohne** Fallback (nicht `var(--g-text-md, 15px)`). Begründung: Tokens sind in `app.css` Z. 109–117 garantiert definiert; die Design-System-Linie #277 + #323 hat Fallbacks bei definierten Tokens konsequent entfernt (AP-007). Konsistenz schlägt die abweichende Btn-Slot-Schreibweise in app.css.

### Test-Strategie (für Phase 5 TDD RED)
- **AC-1** → statischer Quellcode-Test: Datei darf kein `font-size:\s*[0-9]` mehr enthalten (echter Source-Assert, **kein Mock** — Memory-konform).
- **AC-2** → visueller Vergleich Playwright + Fresh-Eyes-Inspector (1px-Drift beobachten, kein Layout-Bruch erwartet).

### Scope
- **Dateien:** 1 (`WeatherMetricsPreviewCard.svelte`) + 1 Test-Datei (AC-1-Guard)
- **LoC:** ~4 geänderte Style-Zeilen + kleiner Guard-Test (deutlich unter 250-Limit)
- **Risiko:** ausschließlich der dokumentierte 1px-Drift (beabsichtigt).
