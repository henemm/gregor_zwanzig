---
entity_id: issue_377_contrast_audit
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [frontend, design-system, wcag, accessibility, tokens, audit]
---

<!-- Issue #377 — Contrast-Audit der Ink-Skala (WCAG-AA auf weißer Card) -->

# Issue 377 — Contrast-Audit der Ink-Skala (WCAG-AA auf weißer Card)

## Approval

- [ ] Approved

## Purpose

Reproduzierbar messen, dokumentieren und bereinigen, dass alle als Textfarbe verwendeten Design-Tokens auf den drei produktiven Hintergründen (`--g-card`, `--g-card-alt`, `--g-paper`) WCAG-AA (4.5:1 normaler Text) erfüllen. Das Issue ist direktes Folgewerk zum PO-Leitprinzip „hoher Kontrast = Lesbarkeit" (CLAUDE.md) und zur Surface-Migration #378 (weiße Cards `--g-card #ffffff`), die den Mess-Kontext verschärft hat: Tokens, die auf beigem Untergrund knapp bestanden, können auf weißem Untergrund durchfallen oder umgekehrt.

## Source

- **File:** `scripts/contrast_audit.py` (NEU, ~70 LoC) — reproduzierbares Mess-Script
- **File:** `docs/design-system/CONTRAST-AUDIT.md` (NEU) — Audit-Report mit Matrix + grep-Anhang
- **File:** `docs/design-system/TOKENS.md` (ERWEITERT) — neue „Freigabe"-Spalte in §2 Ink, §3 Accent, §4 Semantic; §2 Korrektur: `--g-ink-4` nicht mehr als „Captions"
- **File:** `frontend/src/app.css` (FIX) — zentrale `color:`-Klassen (`[data-slot="eyebrow"]`, `.g-th`) auf `--g-ink-muted`
- **File:** `frontend/src/routes/_design/+page.svelte` (ERWEITERT) — neue Sektion `data-testid="contrast-section"`
- **Files:** ~28 `frontend/src/**/*.svelte` (FIX) — `--g-ink-faint`/`--g-ink-4` als `color:` → `--g-ink-muted`; 3 `--g-accent`-Body-Text-Stellen → `--g-accent-deep`

> **Schicht:** Frontend/Design-System. Mess-Script ist Python (kein npm-Paket nötig). Alle Fixes betreffen `frontend/src/` und `docs/design-system/`. Kein Go-API- und kein Python-Backend-Code ist betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Frontend — CSS | Kanonische Token-Werte (named-Set Z.57–90, numbered-Set Z.139–160). Single Source of Truth für alle Kontrast-Messungen |
| `docs/design-system/TOKENS.md` | Dokumentation | Bestehende Token-Doku; wird um „Freigabe"-Spalte erweitert |
| `frontend/src/routes/_design/+page.svelte` | Frontend — SvelteKit | Bestehende Showcase-Route; additiv um Kontrast-Sektion ergänzt |
| `frontend/src/lib/tokens-bridge.test.ts` | Test | Referenz-Pattern für Token-Assertions via `hasDecl()` |
| WCAG 2.1 §1.4.3 | Standard | Kontrast-Mindestanforderung (4.5:1 normaler Text, 3:1 großer Text ≥18pt/14pt bold) |
| PO-Leitprinzip (CLAUDE.md) | Anforderung | „Bei Konflikt zwischen weicher Optik und Lesbarkeit gewinnt Lesbarkeit" — bindet Token-Wert-Änderungs-Verbot (C6) |
| Memory `project_issue_378_surface_stack` | Upstream | Surface-Stack #378 (weiße Cards) live; definiert Mess-Kontext `--g-card #ffffff` |

## Implementation Details

### Schritt 1 — Mess-Script `scripts/contrast_audit.py`

Python-Script ohne externe Dependencies. Berechnet relative Luminanz nach WCAG 2.1 Formel und Kontrastverhältnis für alle Token-Farben gegenüber den drei Hintergrund-Werten.

```python
# Kernfunktionen (keine Abhängigkeiten außer stdlib)
def _linearize(c: float) -> float:
    """sRGB-Kanal → linear (WCAG 2.1 Anhang)."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def relative_luminance(hex_color: str) -> float:
    """Hex-Farbe (#rrggbb) → relative Luminanz [0..1]."""
    r, g, b = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

def contrast_ratio(fg: str, bg: str) -> float:
    """Kontrastverhältnis zweier Farben (immer >= 1.0)."""
    L1, L2 = relative_luminance(fg), relative_luminance(bg)
    bright, dark = max(L1, L2), min(L1, L2)
    return (bright + 0.05) / (dark + 0.05)
```

Script gibt eine Markdown-Tabelle aller Tokens × Hintergründe mit Verhältnis und WCAG-Klasse (AAA-text / AA-text / AA-large / FAIL) aus. Ablage: `scripts/contrast_audit.py` (zählt zu LoC).

### Schritt 2 — Audit-Report `docs/design-system/CONTRAST-AUDIT.md`

Vollständige Kontrast-Matrix (Tabelle, per Script erzeugt) aller Ink/Accent/Semantic-Tokens auf `#ffffff` (card), `#faf8f1` (card-alt), `#f6f4ee` (paper). Anhang: grep-Audit mit Fundstellen-Klassifikation. Doku-Datei (zählt nicht zu LoC).

Kanonische Messwerte (Phase-2-gemessen, Python relative-luminance):

| Token | Wert | card #fff | card-alt #faf8f1 | paper #f6f4ee | Freigabe |
|---|---|---|---|---|---|
| `--g-ink` | #1a1a18 | 17.43 | 16.40 | 15.85 | AAA-text |
| `--g-ink-2` | #45433d | 9.89 | 9.31 | 8.99 | AAA-text |
| `--g-ink-3` | #6b675c | 5.65 | 5.31 | 5.13 | AA-text |
| `--g-ink-muted` | #5c5a52 | 6.91 | 6.50 | 6.28 | AA-text |
| `--g-ink-4` | #9a958a | 2.98 | 2.81 | 2.71 | FAIL — decorative only |
| `--g-ink-faint` | #9c9a90 | 2.82 | 2.66 | 2.57 | FAIL — decorative only |
| `--g-accent` | #c45a2a | 4.34 | 4.08 | 3.94 | AA-large only (Body-Text FAIL) |
| `--g-accent-deep` | #8c3e1a | 7.45 | 7.01 | 6.77 | AAA-text |
| `--g-good` | #3d6b3a | 6.25 | 5.88 | 5.68 | AA-text |
| `--g-warn` | #c08a1a | 3.05 | 2.87 | 2.77 | AA-large (card), FAIL sonst |
| `--g-warning` | #c8882a | 3.00 | 2.82 | 2.72 | FAIL |
| `--g-bad` | #a83232 | 6.63 | 6.24 | 6.03 | AA-text |
| `--g-danger` | #b33a2a | 5.91 | 5.56 | 5.37 | AA-text |
| `--g-info` | #2a6cb3 | 5.39 | 5.07 | 4.90 | AA-text |
| `--g-success` | #3a7d44 | 5.00 | 4.71 | 4.55 | AA-text |

Abweichungen zur Issue-Vorab-Matrix (im Report dokumentieren):
- `--g-accent` real 4.34:1 (nicht 4.55) → NICHT AA-text. Body-Text-Verstoß.
- `--g-info` real `#2a6cb3` (5.39:1); Issue-Wert `#2c5a8c` existiert nicht im Code.
- `--g-warn` real 3.05:1 (schlechter als Issue-Annahme 3.7:1).
- `--g-accent-deep` real 7.45:1 (Issue-Annahme 7.9:1).

### Schritt 3 — TOKENS.md erweitern

Neue Spalte „Freigabe" additiv in §2 Ink, §3 Accent, §4 Semantic. Werte: `AAA-text` / `AA-text` / `AA-large` / `decorative only`. §2-Korrektur: `--g-ink-4` NICHT mehr als „Captions" beschreiben (WCAG: Captions = Inhalt, FAIL-Token ungeeignet).

### Schritt 4 — Code-Fixes (52 Stellen, KEINE Token-Wert-Änderung)

**Ersetzungsregel A — 86 `--g-ink-faint`-Textstellen über 3 Mechanismen → `--g-ink-muted` (6.9:1):**
- CSS `color: var(--g-ink-faint)` → `color: var(--g-ink-muted)` — 47 Funde / 27 Dateien (2× zentral in app.css: `[data-slot="eyebrow"]`, `.g-th`).
- Tailwind `text-[var(--g-ink-faint)]` → `text-[var(--g-ink-muted)]` — 37 Funde / 14 Dateien (v.a. Trip-Wizard + trip-detail/waypoints).
- Svelte style-Binding `'var(--g-ink-faint)'` → `'var(--g-ink-muted)'` — 2 Funde (CompareKachel, TripKachel Status-Farben).

Border-/Background-/Placeholder-/`bg-[…]`/`border-[…]`-Nutzung von `--g-ink-faint` bleibt unberührt (kein WCAG-Text-Minimum). **Hinweis:** Die Phase-2-Vorab-Messung erfasste nur CSS `color:` (47); die Tailwind- und Binding-Mechanismen (39) wurden erst in Phase 6 via erweitertem `contrast-audit.test.ts` aufgedeckt — Scope entsprechend vergrößert.

**Ersetzungsregel A2 — `--g-ink-4` als Textfarbe (Svelte style-Bindings, 3 Stellen):**
`--g-ink-4` wird nicht als CSS-`color:`-Literal, sondern via `$derived`/Ternary in inline-styles genutzt:
- `BrandWordmark.svelte:34` `inkCaption` (Untertitel „v0.20 · wetter-briefing") → `var(--g-ink-muted)` (echter Text).
- `BrandSidebar.svelte:64` Count-Badge (inaktiv, 10 px) → `var(--g-ink-muted)` (echter Text/Zahl).
- `BrandWordmark.svelte:33` `inkDot` (Punkt-Glyph im Wordmark „gregor**.**zwanzig") → **WCAG §1.4.3 Logo-exempt**: behält `var(--g-ink-4)`, erhält `// audit:exempt — Wordmark/Logo-Glyph, kein Lesetext`-Kommentar (Issue erlaubt audit:exempt). Respektiert die bewusste Wordmark-Gestaltung aus #293.

**Ersetzungsregel B — `--g-accent` als Textfarbe (Adversary-korrigiert):**
`--g-accent` (4.34:1) ist NICHT AA-text. Affordance zählt nur als **Ruhezustand**-`text-decoration: underline` (NICHT `:hover`-only, NICHT `font-weight`), Large-Text oder Logo. Alle anderen accent-Textstellen → `--g-accent-deep` (7.45:1).
- **→ accent-deep (13):** `CreateGroupDialog.required`, `SavePresetDialog.required`, `TablePreview.indicator-cell`, `Step1Profile:64/97` (Sterne); `PreviewCard.cta-link`, `BriefingPreviewCard.edit-link`, `WeatherMetricsPreviewCard.edit-link`, `DetailCard.card-action`, `app.css [data-variant="link"]` (alle `text-decoration:none`/hover-only); `AlertRuleRow.pair-indicator`; `Stepper` aktive Step-Zahl.
- **→ bleibt accent + `audit:exempt` (6):** `TripHeader.h1-shortcode` (Large/h1), `BrandWordmark` „zwanzig" 2× (Logo), `WaypointRow` Check-Icon (§1.4.11).
- **→ bleibt accent, OK (echte Ruhezustand-Underline, 4):** `WeatherMetricsTab.link-btn`, `EditReportConfigSection` 3× Account-Links.

**Ersetzungsregel C — `--g-warn`:**
Keine Aktion. grep-Audit ergab 0 `color:`-Funde.

### Schritt 5 — Showcase-Sektion `_design/+page.svelte`

Neue `<section data-testid="contrast-section">` additiv an bestehendes Seitenende anfügen. Pro Token: Farbswatch (CSS `background-color`), Token-Name, Hex-Wert, Kontrast-Zahl auf `#ffffff`, Pass/Fail-Badge. Bestehendes nicht umbauen. Sektion ist rein dekorativ-dokumentativ, kein interaktiver State.

### LoC-Budget und Override

~47 Text-Fixes + 2 `--g-ink-4`-Fixes + 3 Accent-Fixes + Showcase (~100–120 Z.) + Script (~70 Z.) = ca. 250–350 LoC. `loc_limit_override 500` am Workflow-Start setzen.

## Expected Behavior

- **Input:** Bestehende `app.css` Token-Definitionen und `frontend/src/**/*.svelte`-Dateien mit Token-Nutzung
- **Output:** (1) `scripts/contrast_audit.py` erzeugt Kontrast-Matrix als Stdout; (2) `CONTRAST-AUDIT.md` dokumentiert Matrix + grep-Anhang; (3) `TOKENS.md` hat Freigabe-Spalte; (4) alle 52 FIX-Stellen nutzen konforme Tokens; (5) `_design`-Route zeigt Kontrast-Sektion
- **Side effects:** Visuell wirken alle betroffenen Eyebrows, Hints, Captions, Empty-States, Table-Header und Counters minimal dunkler (`--g-ink-muted #5c5a52` statt `--g-ink-faint #9c9a90`) — exakt das PO-Prinzip „Lesbarkeit gewinnt"

## Acceptance Criteria

- **AC-1:** Given `scripts/contrast_audit.py` mit dem WCAG-Referenzpaar schwarz (#000000) auf weiß (#ffffff) / When das Script ausgeführt wird / Then gibt es 21.0:1 (±0.05) aus und klassifiziert diesen Wert als AAA-text

- **AC-2:** Given `scripts/contrast_audit.py` mit `--g-ink-faint #9c9a90` auf `--g-card #ffffff` / When das Script ausgeführt wird / Then gibt es einen Wert < 3.0:1 aus und klassifiziert ihn als FAIL

- **AC-3:** Given `scripts/contrast_audit.py` mit `--g-ink-muted #5c5a52` auf `--g-card #ffffff` / When das Script ausgeführt wird / Then gibt es einen Wert >= 4.5:1 aus und klassifiziert ihn als AA-text oder besser

- **AC-4:** Given `docs/design-system/CONTRAST-AUDIT.md` nach Auslieferung / When man die Datei öffnet / Then enthält sie eine Markdown-Tabelle mit allen 15 Token-Zeilen, den drei Hintergrund-Spalten (card / card-alt / paper) und einer Freigabe-Spalte sowie einen grep-Anhang mit Fundstellen-Klassifikation

- **AC-5:** Given `docs/design-system/TOKENS.md` nach Auslieferung / When man §2 (Ink) öffnet / Then enthält jede Token-Zeile eine „Freigabe"-Spalte mit einem der Werte AAA-text / AA-text / AA-large / decorative only, und `--g-ink-4` ist NICHT mehr als „Captions" beschrieben

- **AC-6:** Given die 47 `--g-ink-faint`-Textstellen und 3 `--g-ink-4`-Textnutzungen in `frontend/src/` / When ein node:test (analog `tokens-bridge.test.ts`) alle .svelte/.css auf `color: var(--g-ink-faint)` und auf `var(--g-ink-4)` als Textfarbe durchsucht / Then findet er 0 `--g-ink-faint`-`color:`-Stellen und jede verbleibende `var(--g-ink-4)`-Nutzung ist entweder border/background oder mit `audit:exempt` markiert (Logo-Glyph)

- **AC-7:** Given die nackten `--g-accent`-Body-Text-Stellen `CreateGroupDialog.svelte` `.required`, `SavePresetDialog.svelte` `.required`, `TablePreview.svelte` `.indicator-cell` / When ein Test alle Dateien auf `color: var(--g-accent)` ohne begleitendes `text-decoration` oder `font-weight ≥ 600` prüft / Then findet er keine derartige Stelle mehr (Large-Text-h1 und 600er-Buttons sind per WCAG AA-large/C4 zulässig und bleiben)

- **AC-8:** Given `frontend/src/routes/_design/+page.svelte` nach Auslieferung / When man die Route im Browser oder per Playwright aufruft / Then ist ein Element mit `data-testid="contrast-section"` vorhanden, das mindestens 15 Token-Swatches mit sichtbarer Kontrast-Zahl und Pass/Fail-Badge enthält

- **AC-9:** Given alle verbleibenden `color: var(--g-ink-faint)` und `color: var(--g-ink-4)` Nutzungen im Codebase / When man grep ausführt / Then betreffen alle verbleibenden Funde ausschließlich `border`, `background`, `placeholder` oder `outline` — keine `color:`-Property

- **AC-10:** Given `--g-warn #c08a1a` / When grep auf `color: var(--g-warn)` in `frontend/src/` läuft / Then sind 0 Fundstellen vorhanden (keine Aktion nötig, PO-Eskalation entfällt)

## Known Limitations

- Token-Divergenz (named `--g-ink-faint` vs. numbered `--g-ink-4`, `--g-ink-muted` vs. `--g-ink-3`, `--g-warn` vs. `--g-warning`) ist OUT OF SCOPE für dieses Issue — wird dokumentiert, aber nicht umbenannt. Ein separater Rename-Issue ist nötig.
- Token-Werte dürfen nicht geändert werden (PO-Constraint C6): Lösungsstrategie setzt ausschließlich auf Token-Neuzuweisung innerhalb des vorhandenen Sets.
- `--g-success #3a7d44` ist auf `--g-paper #f6f4ee` grenzwertig (4.55:1). Knapp AA. Kein Fix in diesem Issue; Beobachtung im Audit-Report dokumentieren.
- `--g-warn` besteht nur auf `--g-card` als AA-large (3.05:1), scheitert auf card-alt/paper. Da 0 `color:`-Funde vorliegen, ist keine Aktion nötig. Bei zukünftiger warn-Textnutzung gilt PO-Eskalation.
- Zentralisierungscheck (app.css `[data-slot="eyebrow"]` + `.g-th`) kann die effektive Datei-Anzahl reduzieren — konkreter Umfang erst beim Implementieren messbar.

## Test Coverage

Tests in `tests/tdd/test_issue_377_contrast_audit.py`:
- `test_contrast_ratio_black_on_white` — WCAG-Referenz: 21.0:1 ±0.05
- `test_contrast_ratio_white_on_white` — 1.0:1 (kein Kontrast)
- `test_ink_faint_fails_on_card` — `--g-ink-faint #9c9a90` auf `#ffffff` < 3.0:1
- `test_ink_muted_passes_on_card` — `--g-ink-muted #5c5a52` auf `#ffffff` >= 4.5:1
- `test_accent_fails_body_text` — `--g-accent #c45a2a` auf `#ffffff` < 4.5:1 (FAIL)
- `test_accent_deep_passes` — `--g-accent-deep #8c3e1a` auf `#ffffff` >= 4.5:1

Tests in `frontend/src/lib/contrast-audit.test.ts` (Vitest, analog tokens-bridge.test.ts):
- `test_no_ink_faint_color_in_fixed_files` — liest relevante .svelte-Dateien, assertet 0 Funde für `color: var(--g-ink-faint)` in FIX-Dateien
- `test_no_ink_4_color_in_fixed_files` — analog für `color: var(--g-ink-4)`
- `test_no_naked_accent_body_text` — prüft die 3 FIX-Svelte-Dateien auf abwesendes `color: var(--g-accent)` ohne `text-decoration`
- `test_contrast_section_exists_in_design_route` — liest `_design/+page.svelte`, assertet dass `data-testid="contrast-section"` vorkommt

## Changelog

- 2026-05-25: Initial spec erstellt — Issue #377, Contrast-Audit WCAG-AA auf weißer Card; Phase-2-Messwerte eingearbeitet (Python relative-luminance); 10 AC-N mit Given/When/Then
- 2026-05-25 (TDD-RED): Accent-FIX-Liste nach präziser Inspektion korrigiert — `TripHeader.h1-shortcode` (Large-Text/h1, AA-large erfüllt) und `ActiveMetricRow.mode-btn.active` (font-weight:600, C4) sind KEINE Verstöße; echte nackte Stellen sind `CreateGroupDialog.required`, `SavePresetDialog.required`, `TablePreview.indicator-cell`. `--g-ink-4`-Textnutzung läuft über Svelte style-Bindings (BrandWordmark/BrandSidebar); Wordmark-Punkt bleibt als Logo-Glyph `audit:exempt`. AC-6/AC-7 + Regel A/A2/B entsprechend präzisiert. Prinzip und Scope unverändert.
- 2026-05-25 (TDD-GREEN): Audit-Lücke geschlossen — `--g-ink-faint` als Textfarbe wird auch über Tailwind `text-[var(…)]` (37×) und Svelte style-Bindings (2×) genutzt, nicht nur CSS `color:` (47×). `contrast-audit.test.ts` auf alle 3 Mechanismen erweitert; 39 zusätzliche Stellen (v.a. Trip-Wizard) auf `--g-ink-muted` umgestellt. Gesamt 86 ink-faint-Textfixes + 2 ink-4 + 3 accent. Tests: Python 8/8, node 4/4, Build Exit 0.
- 2026-05-25 (Adversary-Fix): Validator fand echten §1.4.3-Verstoß — 4 Links (PreviewCard/BriefingPreviewCard/WeatherMetricsPreviewCard/DetailCard) + app.css btn-link-variant nutzten `--g-accent` mit Underline NUR im `:hover` (Ruhezustand `text-decoration:none`). AC-7-Test war zu lax (`/text-decoration:/` matchte auch `none`). Test block-genau verschärft (nur Ruhezustand-underline zählt, kein hover-Leak, alle 3 Mechanismen + audit:exempt). 13 accent-Textstellen → accent-deep, 6 exempt (Large/Logo/Icon), 4 OK (echte underline). Tests: Python 8/8, node 4/4, Build Exit 0, C6 gewahrt.
- 2026-05-25 (Adversary-Fix 2+3): Zwei weitere Mechanismen aufgedeckt — CSS-Fallback `color: var(--g-accent, #hex)` (MetricGroup) und JS-Binding `'var(--g-accent)'` via statusColors-Map (TripKachel). Beide → accent-deep. Test deckt jetzt alle 5 Textfarb-Mechanismen ab (color/fallback/text-[]/style:color=""/`'var()'`-binding). 4 Brand-Icon/bg-Bindings als §1.4.11-exempt markiert. Erschöpfende Endprüfung: 0 ungefangene FAIL-Token-Textstellen. Python 8/8, node 4/4, Build Exit 0.
