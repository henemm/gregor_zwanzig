# Context: Issue #326 — Hardcodierte font-sizes in Alert-Karten → Tokens

## Request Summary

Zwei Komponenten im `alerts-tab/`-Verzeichnis nutzen hardcodierte `font-size`-Werte
(und einige Spacing-/Radius-Werte) statt der Design-System-Tokens. Sie sollen auf
`--g-text-*` (Typografie), `--g-s-*` (Spacing) und `--g-radius-*` (Radius) umgestellt
werden. Reiner Token-Refactor, keine Logik- oder Markup-Änderung.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Enthält 4× `font-size` + Spacing/Radius-Literale + tote `.toggle-label`-Regel |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Enthält 3× `font-size` + Spacing/Radius-Literale |
| `frontend/src/app.css` | Single Source of Truth für alle Tokens (`--g-text-*`, `--g-s-*`, `--g-radius-*`) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Rendert beide Karten (Alerts-Tab der Trip-Detail-Ansicht) — Render-Pfad für den visuellen Check |
| `docs/design-system/ANTI-PATTERNS.md` | AP-017 (Schrift-Skala), AP-008 (Spacing) |
| `docs/design-system/TOKENS.md` | Token-Tabelle |

## Existing Patterns

- **#324 (bug_324_magic_pixel_spacing)** ist das direkte Vorbild: 17 Magic-Pixel-Werte in 6
  Komponenten auf `--g-s-*` umgestellt — gleicher reiner Token-Refactor. #324 ließ die
  Komponenten jeweils **vollständig** compliant zurück (alle padding/margin/gap), nicht nur
  die im Issue genannten Einzelwerte.
- **#323 / #277** behandelten Farb-/Hex-Fallback-Bereinigung (AP-007).
- Token-Referenz aus `app.css`:
  - `--g-text-xs: 11px` · `--g-text-sm: 13px` · `--g-text-md: 15px`
  - `--g-s-1: 4px` · `--g-s-2: 8px` · `--g-s-3: 12px` · `--g-s-4: 16px`
  - `--g-radius-sm: 0.25rem` · `--g-radius-md: 0.5rem`

## Dependencies

- **Upstream:** `app.css` (Token-Definitionen). Keine JS-/Datenabhängigkeit.
- **Downstream:** `AlertsTab.svelte` rendert beide Karten. Keine weiteren Konsumenten
  (grep bestätigt: nur Import in `AlertsTab.svelte`).

## Existing Specs

- Keine bestehende Spec für die Alert-Karten selbst. Verwandt:
  `docs/specs/modules/issue_180_alert_metric_table.md` (Alert-Konfigurator, integriert die Karten),
  `docs/specs/modules/bug_324_magic_pixel_spacing.md` (Token-Refactor-Vorbild).

## Konkreter Befund (IST → SOLL)

### AlertQuietHoursCard.svelte
| IST | SOLL | Regel |
|-----|------|-------|
| `font-size: 0.875rem` (card-title, time-row label) | `--g-text-sm` | AP-017 |
| `font-size: 0.8125rem` (midnight-hint) | `--g-text-xs` | AP-017 |
| `.toggle-label { … gap: 0.375rem; font-size: 0.875rem }` | **Regel entfernen** | Tote CSS — `.toggle-label` existiert nicht im Markup (Checkbox-Komponente wird genutzt). Löst zugleich das 6px-Problem (kein Token). |
| `padding: 1rem` / `gap: 1rem` | `var(--g-s-4)` | AP-008 |
| `margin-bottom: 0.5rem` / `gap: 0.5rem` / `margin: 0.5rem 0 0` | `var(--g-s-2)` | AP-008 |
| `padding: 0.25rem 0.5rem` | `var(--g-s-1) var(--g-s-2)` | AP-008 |
| `border-radius: 0.5rem` / `0.25rem` | `var(--g-radius-md)` / `var(--g-radius-sm)` | Radius-Token |
| `min-height: 36px`, `border: 1px` | **bleibt** | Semantische Control-Höhe / Trennlinie (AP-008 erlaubt) |

### AlertCooldownCard.svelte
| IST | SOLL | Regel |
|-----|------|-------|
| `font-size: 0.875rem` (card-title, unit) | `--g-text-sm` | AP-017 |
| `font-size: 0.8125rem` (hint) | `--g-text-xs` | AP-017 |
| `padding: 1rem` | `var(--g-s-4)` | AP-008 |
| `margin: 0 0 0.5rem` / `gap: 0.5rem` / `margin: 0.5rem 0 0` | `var(--g-s-2)` | AP-008 |
| `padding: 0.25rem 0.5rem` | `var(--g-s-1) var(--g-s-2)` | AP-008 |
| `border-radius: 0.5rem` / `0.25rem` | `var(--g-radius-md)` / `var(--g-radius-sm)` | Radius-Token |
| `width: 80px`, `min-height: 36px`, `border: 1px` | **bleibt** | Semantische Feld-/Control-Maße |

## Risks & Considerations

1. **Issue-Mapping-Tabelle ist faktisch falsch.** Das Issue behauptet `--g-text-sm` = 14px
   und `--g-text-xs` = 12px. `app.css` sagt aber `sm` = 13px, `xs` = 11px. Konsequenz für AC-3
   („Token-Werte sind äquivalent"): Pixel-identisch ist es **nicht** (−1px bei 0.875rem, −2px bei
   0.8125rem). **Entscheidung (Tech-Lead):** Wir folgen den Token-**Namen** des Issues
   (0.875rem→sm, 0.8125rem→xs), denn das erhält die visuelle Hierarchie (Titel > Hint) und ist
   exakt der Sinn von AP-017 (Snap auf die kanonische Skala). Die 1–2px-Deltas liegen auf
   sekundärem Meta-Text und sind nicht wahrnehmbar. Keine User-Rückfrage nötig.
2. **Scope-Entscheidung:** Issue nennt explizit nur font-size + zwei Spacing-Werte, die ACs
   testen nur font-size. **Empfehlung:** Beide Dateien — analog #324 — **vollständig**
   tokenisieren (font-size + alle padding/margin/gap + border-radius + tote Regel raus), statt sie
   halb-compliant zu lassen und ein Folge-Issue zu provozieren. Die Dateien sind winzig
   (LoC-Delta < ~40, weit unter dem 250-Limit).
3. **Out-of-Scope-Beobachtung (nicht Teil dieses Workflows):** Beide Karten haben
   `background: var(--g-surface-1, #fff)`. `--g-surface-1` ist definiert (#edeae1), der Hex-Fallback
   `#fff` ist also tot **und** falsch (AP-007). Gehört thematisch zur Farb-Fallback-Bereinigung
   (#323/#277), nicht zu AP-017. Wird hier nur notiert, nicht angefasst.
4. **Visueller Vergleich (AC-3):** Render-Pfad ist Trip-Detail → Tab „Alarme" (`AlertsTab.svelte`).
   Fresh-Eyes/Screenshot-Vergleich vor/nach gegen Staging.
