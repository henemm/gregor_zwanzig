# Context: Bug #327 — Hardcodierte font-sizes in TripHero.svelte

## Request Summary

`frontend/src/lib/components/trip-detail/TripHero.svelte` nutzt 5 freie `font-size`-rem-Werte ohne Token-Anbindung. Diese sollen auf die `--g-text-*` Design-System-Tokens umgestellt werden. Reiner Token-Refactor ohne Logik- oder Layout-Änderung — gleiche Familie wie #322/#323/#324.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | **Einzige zu ändernde Datei.** 5 hardcodierte `font-size` im `<style>`-Block (Z. 59, 64, 70, 86, 92) |
| `frontend/src/app.css` (Z. 109–117) | Single Source of Truth der `--g-text-*` Skala |
| `docs/design-system/ANTI-PATTERNS.md` (Z. 317–323) | Regel **AP-017 „Drift in der Schrift-Skala"** — verbietet font-sizes ausserhalb der Token-Skala |
| `docs/design-system/TOKENS.md` | Typografie-Skala-Doku (vom Issue referenziert) |
| `docs/specs/modules/epic_135_step3_trip_hero.md` | Spec der Komponente (Verhalten unverändert) |

## Token-Mapping (app.css Z. 109–117 = IST-Wahrheit)

| TripHero-Stelle | Aktueller Wert | Ziel-Token | Token-px (app.css) | Δ px |
|-----------------|----------------|------------|--------------------|------|
| Z. 59 `.trip-hero-title` | `1.5rem` (24px) | `--g-text-2xl` | 24px | **0** ✓ exakt |
| Z. 64 `.trip-hero-region` | `0.875rem` (14px) | `--g-text-sm` | 13px | **−1** |
| Z. 70 `.trip-hero-date-range` | `0.875rem` (14px) | `--g-text-sm` | 13px | **−1** |
| Z. 86 `.eyebrow` | `0.6875rem` (11px) | `--g-text-xs` | 11px | **0** ✓ exakt |
| Z. 92 `.stat-value` | `1rem` (16px) | `--g-text-md` | 15px | **−1** |

## Existing Patterns

- **#322/#323/#324** waren die direkten Vorgänger derselben Design-Compliance-Aufräum-Serie (WIcon, Hex-Fallbacks, Magic-Pixel-Spacing). Muster: ein Anti-Pattern, eng umrissener Datei-Scope, reines Token-Mapping, kein Verhaltens-Change.
- **app.css** liefert die Tokens als Custom-Properties ohne Fallback (`--g-text-sm: 13px;`). Konsistent mit der Codebase wird das Token **ohne Hex-/px-Fallback** referenziert — vgl. Issue #277 (CSS-Variable-Fallbacks bereinigen) und #323 (Hex-Fallbacks raus). Also `font-size: var(--g-text-sm);`, NICHT `var(--g-text-sm, 0.875rem)`.

## Dependencies

- **Upstream:** TripHero importiert Utils (`tripHero.ts`) + `TopoBg` — beide unberührt.
- **Downstream:** TripHero wird im Overview-Tab der Trip-Detail-Seite (`/trips/[id]`) gerendert. Keine anderen Konsumenten von TripHero-CSS-Klassen.

## Existing Specs

- `docs/specs/modules/epic_135_step3_trip_hero.md` — Verhalten/Datenmodell unverändert. Eine neue AC-N-Spec für den Refactor wird in Phase 3 erstellt (Bug-Spec mit AC-1/AC-2 aus dem Issue).

## Risks & Considerations

1. **AP-Nummer im Issue falsch:** Issue-Titel/-Body sprechen von „AP-010". In `ANTI-PATTERNS.md` ist AP-010 = „Cockpit-Style Startseite". Der tatsächlich einschlägige Pattern ist **AP-017 „Drift in der Schrift-Skala"**. Inhaltlich identisch gemeint — nur die Referenz im Issue ist veraltet. Spec sollte AP-017 korrekt zitieren.

2. **−1px Drift bei 3 von 5 Werten:** Issue-Tabelle sagt „0.875rem (14px) → --g-text-sm" und „1rem (16px) → --g-text-md", aber die Tokens sind in app.css **13px** bzw. **15px**. Mapping auf die Skala verkleinert Region, Datum und Stat-Wert um je 1px. Das ist der **intendierte Snap an die Skala** (genau der Zweck von AP-017), aber AC-2 fordert „sehen identisch aus". 1px ist innerhalb visueller Toleranz; bei Fresh-Eyes-Vergleich ist das festzuhalten. Keine Abweichung von der Issue-Vorgabe — der Issue-Autor hat die Tokens explizit so gewählt.

3. **Scope-Disziplin:** 30 weitere Komponenten haben ebenfalls hardcodierte font-sizes. Diese sind **out of scope** — #327 betrifft ausschliesslich TripHero.svelte (Serien-Prinzip: ein File pro Issue).

4. **Kein iOS-Zoom-Konflikt:** Body-Inputs brauchen ≥16px (AP-017 Mobile-Minimum / Bug #272). TripHero enthält keine Eingabefelder — irrelevant.

## Analyse (Phase 2)

**Typ:** Trivialer Design-Compliance-Refactor (kein Defekt mit unbekannter Ursache → keine Agenten-Investigation nötig). Ursache ist bekannt und vollständig spezifiziert.

**Bestehende Tests:** `frontend/e2e/trip-detail-hero.spec.ts` (Playwright, Trip `e2e-cockpit-test`) prüft Sichtbarkeit, Text und H1-Tag der Hero-TestIDs — **nicht** font-size. Der Refactor bricht diese Tests nicht. Keine Vitest-Unit-Tests für TripHero-CSS vorhanden.

**Test-Strategie (analog #324):** grep-basierte Assertion als TDD-RED.
- **RED:** Test, der `TripHero.svelte` nach `font-size:\s*[0-9]` durchsucht und Treffer ⇒ Fail erwartet (= AC-1). Schlägt jetzt fehl (5 Treffer).
- **GREEN:** 5 font-size auf `var(--g-text-*)` umstellen ⇒ 0 Treffer ⇒ Test grün.
- **Visuelle Prüfung (AC-2):** Fresh-Eyes-Screenshot-Vergleich von `/trips/[id]` Overview-Tab. −1px-Drift bei Region/Datum/Stat-Wert dokumentieren.

**Empfehlung:** 1:1 dem Issue-Mapping folgen, Tokens **ohne** px-Fallback referenzieren (Konsistenz mit #277/#323). AP-Referenz in der Spec auf **AP-017** korrigieren.

**Scope:**
- Quellcode: **1 Datei** (TripHero.svelte), **5 geänderte Zeilen**.
- Zusätzlich: 1 Spec + 1 grep-RED-Test.
- LoC-Delta: ~5 (weit unter 250-Limit).
- Risiko: minimal. Einziger Diskussionspunkt = bewusster −1px-Snap (siehe Risiko 2).
