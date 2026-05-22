# Context: Bug #328 — SavePresetDialog font-sizes + Hex-Farben → Tokens

## Request Summary

Design-Compliance-Bug (Label AP-010c): `SavePresetDialog.svelte` enthält 7 hardcodierte
`font-size`-Werte und 2 Inline-Hex-Farben. Diese sollen durch Design-System-Tokens
(`--g-text-*`, `--g-danger`, `--g-paper`) ersetzt werden — mit **einer dokumentierten
Ausnahme** für den iOS-Zoom-Schutz.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | **Zieldatei** — alle 9 Verstöße im `<style>`-Block |
| `frontend/src/app.css` | Single Source of Truth für Tokens (`--g-text-*` Z.109–117, `--g-paper` Z.58, `--g-danger` Z.75) |
| `docs/design-system/ANTI-PATTERNS.md` | AP-007 (Inline-Hex) Z.145; font-size-Verbot (Label "AP-010") |
| `docs/design-system/TOKENS.md` | Token-Sollwerte (`--g-text-*` Z.82–90, `--g-paper` Z.13, `--g-danger`) |
| `docs/specs/modules/bug_272_ios_input_font_size.md` | **Vorgänger** — hat die 16px-`@media`-Regel in genau diese Datei eingefügt (iOS-Zoom-Schutz) |

## Verifizierte Verstöße (aktuelle Zeilennummern == Issue)

| Zeile | Selektor | Ist | Soll |
|-------|----------|-----|------|
| 175 | `.field-label` | `font-size: 0.8125rem` | `--g-text-xs` |
| 187 | `.field input/textarea` | `font-size: 0.875rem` | `--g-text-sm` |
| 193 | `.field-inline` | `font-size: 0.875rem` | `--g-text-sm` |
| 197 | `.summary` | `font-size: 0.8125rem` | `--g-text-xs` |
| 204 | `.error` | `font-size: 0.8125rem` | `--g-text-xs` |
| 205 | `.error` | `color: #dc2626` | `--g-danger` |
| 210 | `.btn-primary/.btn-secondary` | `font-size: 0.875rem` | `--g-text-sm` |
| 217 | `.btn-primary` | `color: #fff` | `--g-paper` |
| 230 | `@media .field textarea` | `font-size: 16px` | **bleibt 16px** + `/* iOS zoom guard */` |

## Existing Patterns

- **Token-Cleanup-Issues:** #323 (Hex-Fallbacks), #324 (Magic-Pixel-Spacing), #277 (CSS-Variable-Fallbacks)
  haben dasselbe Muster (Hardcode → Token) bereits etabliert. Reines CSS-Refactoring, kein Logik-Change.
- **Token-Definitionen** liegen ausschließlich in `frontend/src/app.css` (`:root`-Block).

## Dependencies

- **Upstream:** `frontend/src/app.css` (Token-Werte). Keine Backend-/Go-/Python-Berührung.
- **Downstream:** Nur die Dialog-Komponente selbst — gescopetes CSS, keine externen Konsumenten.

## Existing Specs

- `docs/specs/modules/bug_272_ios_input_font_size.md` — direkter Vorgänger an dieser Datei (iOS-Guard).
- `docs/specs/modules/issue_323_hex_fallbacks_cleanup.md` / `bug_324_magic_pixel_spacing.md` — Muster-Vorbild.

## Risks & Considerations

1. **KRITISCH — iOS-Zoom-Regression (Bug #272):** Der Issue-Body schlägt `16px → --g-text-md` vor,
   aber `--g-text-md` ist **15px**. iOS Safari zoomt bei Eingabefeldern mit `font-size < 16px` —
   die 16px-Zeile (Z.230) ist der Scoped-Override aus Bug #272 und MUSS exakt 16px bleiben.
   **AC-1 löst das korrekt:** 16px ist als Ausnahme erlaubt, sofern ein `/* iOS zoom guard */`-Kommentar
   dabeisteht. Der Body-Text widerspricht hier dem eigenen Acceptance-Criterion → **AC-1 ist maßgeblich**.

2. **Farb-Mappings sind keine Pixel-Treue:**
   - `#dc2626` (helleres Rot) → `--g-danger` = `#b33a2a` (Backstein-Rot). Sichtbar anderer Ton.
   - `#fff` (reinweiß) → `--g-paper` = `#f6f4ee` (warmes Off-White) als Text auf Accent-Button.
   - **AC-3 fordert „identisch"** — das kollidiert mit dem Sinn der Tokenisierung (Wechsel zur
     System-Farbe). Intention ist „korrekte System-Farbe verwenden", nicht „alten Hex erhalten".
     In Phase 3 (Spec) klarstellen.

3. **`--g-paper` als Button-Text-Farbe ist semantisch grenzwertig:** `--g-paper` heißt „App-Hintergrund".
   Es gibt **keinen** dedizierten „weiß-auf-Accent"-Token. Der Codebase ist uneinheitlich:
   viele Komponenten nutzen weiterhin `color: #fff` auf Accent-Buttons (AlertsTab, BriefingsTab, …),
   nur `MetricCheckbox.svelte` nutzt bereits `var(--g-paper)`. Wir folgen der Issue-Vorgabe (`--g-paper`),
   merken aber an, dass ein `--g-on-accent`-Token systemweit sauberer wäre (separates Backlog-Thema).

4. **font-size rem→Token verkleinert leicht:** `0.8125rem`=13px → `--g-text-xs`=11px; `0.875rem`=14px →
   `--g-text-sm`=13px. Minimale Schriftverkleinerung, vom Issue akzeptiert (keine font-size in AC-3).

5. **Label-Diskrepanz (kein Blocker):** In `ANTI-PATTERNS.md` ist „AP-010" = „Cockpit-Style Startseite",
   nicht font-size. Das Issue-Label „AP-010c" meint die font-size-Klasse. Nur eine Benennungs-Frage.

## Acceptance Criteria (aus Issue)

- **AC-1:** grep `font-size:\s*[0-9]` → keine Treffer (Ausnahme Z.230 mit `/* iOS zoom guard */`).
- **AC-2:** grep `color:\s*#` → keine Treffer mehr.
- **AC-3:** Dialog visuell — Fehler-Rot + Hintergrund konsistent zum Design-System.

---

## Analyse & Strategie (Phase 2)

**Typ:** Design-Compliance-Cleanup (als „bug" gelabelt). Vollständig spezifiziert, kein
Untersuchungsbedarf → keine Agent-Fan-Out-Recherche nötig (1 Datei, ~9 Zeilen, kein Logik-Change).

**Vorgehen — 1:1 Token-Ersetzung im `<style>`-Block, ohne Hex-Fallback** (folgt etabliertem Muster,
z.B. `Select.svelte`, `Checkbox.svelte`, `StageCard.svelte` → `font-size: var(--g-text-sm)`):

| Zeile | Aktion |
|-------|--------|
| 175, 197, 204 | `0.8125rem` → `var(--g-text-xs)` |
| 187, 193, 210 | `0.875rem` → `var(--g-text-sm)` |
| 205 | `#dc2626` → `var(--g-danger)` |
| 217 | `#fff` → `var(--g-paper)` |
| 230 | **unverändert 16px**, nur `/* iOS zoom guard (#272) — exakt 16px, sonst Auto-Zoom */` ergänzen |

**Tech-Lead-Entscheidung zu AC-3 (keine User-Frage):** „Identisch" wird als „Design-System-konform"
gelesen, nicht „pixelgleich zum alten Hex". Tokenisierung wechselt bewusst zur System-Farbe
(`--g-danger` #b33a2a statt #dc2626; `--g-paper` #f6f4ee statt #fff). Das ist der Zweck des Issues.
Visuell minimal, semantisch korrekt.

**Backlog-Notiz (out of scope):** Ein dedizierter `--g-on-accent`-Token für „helle Schrift auf
farbigem Grund" wäre systemweit sauberer als `--g-paper` und würde die Inkonsistenz (viele
Komponenten nutzen weiter `#fff`) auflösen. Separates Aufräum-Issue, nicht Teil von #328.

**Scope:** 1 Datei (`SavePresetDialog.svelte`), 8 echte Ersetzungen + 1 Kommentar ≈ 9 LoC.
Weit unter dem 250-LoC-Limit. Frontend-Asset → zählt ohnehin nicht ins LoC-Budget.

**Risiken:** Nur das in Phase 1 dokumentierte iOS-Zoom-Risiko (Z.230) — durch „16px bleibt" gebannt.
