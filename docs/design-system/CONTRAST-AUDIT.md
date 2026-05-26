# Kontrast-Audit der Ink-Skala (WCAG-AA auf weißer Card)

**Issue:** #377 · **Stand:** 2026-05-25 · **Mess-Werkzeug:** `scripts/contrast_audit.py` (WCAG 2.1 §1.4.3 relative-luminance, reproduzierbar, ohne Dependencies)

Folgewerk zum PO-Leitprinzip „hoher Kontrast = Lesbarkeit" und zur Surface-Migration #378 (weiße Cards `--g-card #ffffff`). Re-Messung erzeugt mit:

```bash
python3 scripts/contrast_audit.py
```

## 1. Kontrast-Matrix (alle Tokens × 3 produktive Hintergründe)

WCAG-Schwellen: **AAA-text** ≥ 7:1 · **AA-text** ≥ 4.5:1 · **AA-large** ≥ 3:1 (Text ≥ 18 pt oder ≥ 14 pt bold) · sonst **FAIL**.

| Token | Wert | card #ffffff | card-alt #faf8f1 | paper #f6f4ee |
|---|---|---|---|---|
| `--g-ink` | #1a1a18 | 17.43 (AAA-text) | 16.40 (AAA-text) | 15.85 (AAA-text) |
| `--g-ink-2` | #45433d | 9.89 (AAA-text) | 9.31 (AAA-text) | 8.99 (AAA-text) |
| `--g-ink-3` | #6b675c | 5.65 (AA-text) | 5.31 (AA-text) | 5.13 (AA-text) |
| `--g-ink-muted` | #5c5a52 | 6.91 (AA-text) | 6.50 (AA-text) | 6.28 (AA-text) |
| `--g-ink-4` | #9a958a | 2.98 (FAIL) | 2.81 (FAIL) | 2.71 (FAIL) |
| `--g-ink-faint` | #9c9a90 | 2.82 (FAIL) | 2.66 (FAIL) | 2.57 (FAIL) |
| `--g-accent` | #c45a2a | 4.34 (AA-large) | 4.08 (AA-large) | 3.94 (AA-large) |
| `--g-accent-deep` | #8c3e1a | 7.45 (AAA-text) | 7.01 (AAA-text) | 6.77 (AA-text) |
| `--g-good` | #3d6b3a | 6.25 (AA-text) | 5.88 (AA-text) | 5.68 (AA-text) |
| `--g-warn` | #c08a1a | 3.05 (AA-large) | 2.87 (FAIL) | 2.77 (FAIL) |
| `--g-warning` | #c8882a | 3.00 (FAIL) | 2.82 (FAIL) | 2.72 (FAIL) |
| `--g-bad` | #a83232 | 6.63 (AA-text) | 6.24 (AA-text) | 6.03 (AA-text) |
| `--g-danger` | #b33a2a | 5.91 (AA-text) | 5.56 (AA-text) | 5.37 (AA-text) |
| `--g-info` | #2a6cb3 | 5.39 (AA-text) | 5.07 (AA-text) | 4.90 (AA-text) |
| `--g-success` | #3a7d44 | 5.00 (AA-text) | 4.71 (AA-text) | 4.55 (AA-text) |

## 2. Abweichungen zur Issue-Vorab-Matrix

Das Issue lieferte eine Sandbox-Vorab-Berechnung; die Re-Messung gegen die echten `app.css`-Werte ergab:

| Token | Issue-Annahme | Gemessen (card) | Konsequenz |
|---|---|---|---|
| `--g-accent` | 4.55 (AA-text) | **4.34 (AA-large)** | Accent ist als normaler Body-Text **nicht** AA-konform — nur AA-large. Strenger als gedacht. |
| `--g-info` | #2c5a8c | **#2a6cb3 (5.39)** | Issue-Hexwert existiert nicht im Code; realer Wert ist AA-text. |
| `--g-warn` | 3.7 | **3.05 (card), FAIL sonst** | Schlechter als angenommen. |
| `--g-accent-deep` | 7.9 | **7.45 (card), 6.77 (paper)** | Auf paper nur AA-text statt AAA. |

## 3. Verwendungs-Freigabe (siehe TOKENS.md)

- **Body-Text (< 14 pt):** nur `--g-ink`, `--g-ink-2`, `--g-ink-3`, `--g-ink-muted`.
- **decorative only** (Placeholder, Disabled, Logo-Glyphen, Border): `--g-ink-4`, `--g-ink-faint`.
- `--g-accent` als Textfarbe: nur Large-Text (≥18 pt / ≥14 pt bold) **oder** mit Underline/`font-weight ≥ 600`. Für reinen Body-Text → `--g-accent-deep`.
- Semantic-Farben (`--g-good/-bad/-danger/-info/-success`) sind AA-text-tauglich. `--g-warn`/`--g-warning` nur AA-large bzw. FAIL → nicht für Body-Text.

## 4. grep-Audit: Fundstellen-Klassifikation (`frontend/src/`)

### `--g-ink-faint` als Textfarbe — **86 Funde über 3 Mechanismen → alle gefixt** (`→ --g-ink-muted`)
Wichtig: `--g-ink-faint` wird als Textfarbe über **drei** CSS-/Markup-Mechanismen genutzt. Ein Audit nur auf CSS `color:` (wie die Phase-2-Vorab-Schätzung) ist unvollständig:

| Mechanismus | Funde | Beispiele |
|---|---|---|
| CSS `color: var(--g-ink-faint)` | 47 (27 Dateien) | Eyebrows, Hints, Empty-States, Counter, Table-Header; zentral `[data-slot="eyebrow"]` + `.g-th` in app.css |
| Tailwind `text-[var(--g-ink-faint)]` | 37 (14 Dateien) | Trip-Wizard (Step1–4, Stepper, WaypointRow, StageRow, ChannelToggle, TemplatePicker), trip-detail/waypoints (WaypointCard, PauseStageView, EtappenStrip), WaypointsPanel, EditStagesPanelNew |
| Svelte style-Binding `'var(--g-ink-faint)'` | 2 | CompareKachel (Status-Farbe), TripKachel (Status „draft") |

Alle 86 waren echter Lesetext / funktionale Icons (Drag-Handles, Upload-Icon → §1.4.11). Verifiziert via `contrast-audit.test.ts` (prüft alle drei Mechanismen).
**Verbleibend OK (unberührt):** `--g-ink-faint` als `border`/`border-color` (~108×), `background`/`bg-[…]` (~8×), `box-shadow`, `outline`, `--color-input` — kein WCAG-Text-Minimum.

### `--g-ink-4` als Textfarbe (Svelte style-Bindings) — 3 Funde → **2 gefixt, 1 exempt**
| Stelle | Inhalt | Aktion |
|---|---|---|
| `BrandWordmark.svelte:34` `inkCaption` | Untertitel „v0.20 · wetter-briefing" | → `--g-ink-muted` (echter Text) |
| `BrandSidebar.svelte:64` Count-Badge inaktiv | kleine Zahl (10 px) | → `--g-ink-muted` (echter Text) |
| `BrandWordmark.svelte:33` `inkDot` | Punkt-Glyph in „gregor**.**zwanzig" | **audit:exempt** — Wordmark/Logo-Glyph (WCAG §1.4.3 logo-exempt), bewusste Gestaltung #293 |

### `--g-accent` als Textfarbe (color: / Tailwind / style-Binding) — **13 gefixt, 6 exempt, 4 OK**
`--g-accent` (4.34:1) erfüllt **nicht** AA-text (4.5:1). Wichtige Korrektur ggü. erster Annahme (Adversary-Finding): **Underline nur im `:hover` (Ruhezustand `text-decoration: none`) ist KEINE Affordance** — WCAG §1.4.1 (Use-of-Color) ≠ §1.4.3 (Kontrast). Nur Ruhezustand-Underline, Large-Text oder Logo zählen.

> **Audit-Lehre — fünf Textfarb-Mechanismen:** Eine Farbe wird im Code über mind. 5 Wege zu Text: CSS `color:`, CSS-Fallback `color: var(--t, #hex)`, Tailwind `text-[var(--t)]`, Svelte-Direktive `style:color="var(--t)"`, JS-Binding `'var(--t)'` (z.B. `statusColors`-Maps via `style:color={...}`). Der automatisierte Test (`contrast-audit.test.ts`) prüft alle fünf. SVG `fill`/`stroke` = §1.4.11 (separat, s.u.).

**→ `--g-accent-deep` (7.45:1) umgestellt (14):**
| Stelle | Grund |
|---|---|
| `CreateGroupDialog.required`, `SavePresetDialog.required`, `Step1Profile:64/97` | Pflichtfeld-Sterne, keine Affordance |
| `TablePreview.indicator-cell` | Daten-Zelle |
| `PreviewCard.cta-link`, `BriefingPreviewCard.edit-link`, `WeatherMetricsPreviewCard.edit-link`, `DetailCard.card-action`, `app.css [data-variant="link"]` | Links mit `text-decoration:none` im Ruhezustand (Underline nur `:hover`) — echte §1.4.3-Verstöße |
| `AlertRuleRow.pair-indicator` | 11 px Label, weight allein reicht nicht |
| `Stepper` aktive Step-Zahl | Text auf accent-tint |
| `TripKachel` `statusColors.aktiv` | Status-Text „aktiv" via JS-Binding (`style:color={map}`) |

**Bleibt `--g-accent` + `audit:exempt` (10, dokumentierte Ausnahmen):**
- Text-exempt (3): `TripHeader.h1-shortcode` (Large/h1), `BrandWordmark` „zwanzig" 2× (Markenname/Logo §1.4.3).
- §1.4.11-Icon/-Grafik (kein Lesetext, accent 4.34 > 3:1): `WaypointRow` Check-Icon, `BrandIcon`/`BrandIconSquare`-Prop-Defaults, `BrandSidebar.iconColor` (SVG stroke/fill), `BrandUserBadge.avatarBg` (Hintergrund).

**Bleibt `--g-accent`, OK ohne Markierung (echte Ruhezustand-Underline, 4 Stellen):**
| Stelle | Grund |
|---|---|
| `WeatherMetricsTab.link-btn` | `text-decoration: underline` im Block |
| `EditReportConfigSection` (3× Account-Links) | inline `text-decoration:underline` |

### `--g-warn` als `color:` — **0 Funde** → keine Aktion (PO-Eskalation aus C5 entfällt)

## 5. Bekannte Grenzfälle (kein Fix in #377)

- `--g-success #3a7d44` auf `--g-paper` = 4.55:1 — gerade noch AA, sehr knapp. Beobachten.
- `--g-warn`/`--g-warning` fallen für Body-Text durch — werden aktuell nicht als Textfarbe genutzt; bei künftiger Textnutzung gilt PO-Eskalation (Wert anpassen oder Symbol-Affordance).
- Token-Divergenz (named `--g-ink-faint` vs. numbered `--g-ink-4`, `--g-ink-muted` vs. `--g-ink-3`, `--g-warn` vs. `--g-warning`) ist OUT OF SCOPE — eigener Rename-Issue. Werte hier nur dokumentiert, nicht geändert (PO-Constraint C6).
- **SVG-Chart-Strokes (§1.4.11 Non-Text-Kontrast, OUT OF SCOPE für #377):** Höhenprofil-Datenkurven nutzen `stroke="var(--g-ink-faint)"` (2.82:1 < 3:1) in `ProfileEditor.svelte` (`<polyline>` Z.140-Bereich) und `ProfileChart.svelte:80`. Das sind bedeutungstragende Grafik-Objekte und fallen unter WCAG §1.4.11 (3:1-Minimum), nicht unter den Text-Kontrast-Audit (§1.4.3) dieses Issues. **Empfehlung Folge-Issue:** Datenkurven → `--g-ink-3`/`--g-ink-muted` anheben. Die gestrichelten Gitter-Hilfslinien (`stroke-dasharray`, `stroke-width:0.5`) sind dekorativ und §1.4.11-exempt. Das Issue grenzt §1.4.11-Themen explizit als eigene Accessibility-Issues ab.

## 6. Showcase

Visuelle Beleg-Sektion `data-testid="contrast-section"` auf der internen Route `/_design` — Token-Swatch + Kontrast-Zahl (auf `#ffffff`) + Pass/Fail-Badge je Token.
