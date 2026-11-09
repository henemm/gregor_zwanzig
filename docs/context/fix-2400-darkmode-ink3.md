# Context: fix-2400-darkmode-ink3

## Request Summary
Issue #2400 (Epic #2508): Im dunklen Modus erreicht Text in `--g-ink-3` (Footer-Links, Eyebrow) nur 3,51:1 statt WCAG-AA 4,5:1.

## Kernbefund (Messung auf Staging, 2026-11-09)
Der dunkle Modus ist nur zur Hälfte gebaut. `applyDarkMode()` in `frontend/src/routes/+layout.svelte:111-152`
überschreibt allein 18 shadcn-Tokens (`--color-*`) per Inline-Style auf `<html>`. Die gesamte
Gregor-Palette (`--g-paper`, `--g-card`, `--g-surface-*`, `--g-ink`, `--g-ink-2..4`, `--g-rule*`, `app.css:181-230`)
bleibt hell. Folge: Body wird dunkel (`oklch(0.145 0 0)`), Karten bleiben weiß.

Gemessen auf der Startseite (ausgeloggt, 1280 px, `localStorage gz-dark=1`):
- Wortmarke „gregor" (`--g-ink`) 1,20:1, Überschrift „Das Wetter für deine Etappe" 1,20:1, Button „Anmelden" 1,20:1 — praktisch unsichtbar
- Untertitel (`--g-ink-2`) 2,12:1, Versionszeile (`--g-ink-muted`) 3,04:1, Eyebrow (`--g-ink-3`) 3,72:1
- Karten-Überschriften (weiß auf weißer Karte, über `--color-foreground`) unsichtbar
- 10 von 30 Textelementen unter 4,5:1
Screenshot: Scratchpad der Sitzung (nicht eingecheckt).

=> #2400 ist ein Symptom. Ein einzelner Dark-Wert für `--g-ink-3` würde den Text auf den weiß bleibenden Karten
verschlechtern (heller Grauton auf Weiß) und die übrigen unsichtbaren Texte nicht beheben.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/+layout.svelte:111-152, 166, 220` | `darkVars`, `applyDarkMode`, Umschalter, Persistenz `localStorage gz-dark` |
| `frontend/src/app.css:53-90` | `@property`/`@theme`: `--color-*` zeigen auf `--g-*` |
| `frontend/src/app.css:181-230` | Gregor-Tokens `:root` (nur hell) |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte`, `Sidebar.svelte` | Umschalter „Dunkles Design" |
| `frontend/src/routes/_design/+page.svelte` | Design-Seite, zeigt Token-Werte |

## Nutzung der Gregor-Tokens (Fundstellen in Svelte/CSS)
`--g-ink` 236 · `--g-ink-2` 118 · `--g-ink-3` 314 · `--g-ink-4` 76 · `--g-paper` 91 · `--g-card` 128 · `--g-rule` 280

## Existing Patterns
- Dark-Werte als Inline-Style-Map in `+layout.svelte` (kein `.dark`-Klassen-Scope, kein `prefers-color-scheme`).
- Kontrast-Kerntests messen am gerenderten Markup mit Token-Werten aus `app.css` (#2371, #2896, `node --test`).

## Existing Specs
- `docs/specs/modules/ink4_kontrast_2371.md`, `fix_2896_kontrast_zierpunkt_avatar.md` (schließen #2400 explizit aus)
- `docs/specs/modules/design_optimierungen.md` (Dark-Mode-Umschalter im Konto-Menü)
- Ursprung Umschalter: #70 (geschlossen)

## Risks & Considerations
- Vollständige Dark-Palette berührt jede Seite optisch (hoher Blast Radius), technisch aber zentral an einer Stelle.
- Hart codierte Farben in Komponenten (`#fff`, `rgba(26,26,24,…)`, z. B. `--g-nav-glass`) folgen Tokens nicht.
- Mails sind nicht betroffen (eigener Renderer).
- Produktfrage: Dark Mode vollständig bauen oder Umschalter bis dahin ausblenden (Label `go-live-pflicht`).

## PO-Entscheidung (2026-11-09)
Henning: „Ganz fertig bauen". Scope von #2400 wird erweitert auf eine vollständige Dark-Palette aller
Gregor-Tokens an zentraler Stelle plus Lesbarkeitsprüfung jeder Seite (inkl. Footer/Eyebrow aus #2400).
Nicht gewählt: Umschalter ausblenden; nur `--g-ink-3` anpassen.
Neubewertung Intake: Scope Medium, Blast Radius High (jede Seite), Unsicherheit Medium → Summe 4:
Analyse getrennt und gründlich.

## Analysis

### Type
Bug (Symptom #2400) mit PO-erweitertem Scope zum Feature „vollständiger Dark Mode“ (PO 2026-11-09: „Ganz fertig bauen“).

### Befunde (3x Explore + Plan, 2026-11-09)
- Mechanik heute: `darkVars` (18 `--color-*`) per Inline-Style auf `<html>`, erst nach Hydrierung (`if (browser)`), `localStorage gz-dark`. `--g-*` (≈2.500 Nutzungen in ≈174 Svelte-Dateien) bleiben hell ⇒ Mischzustand (body dunkel, Karten weiß, Text weiß auf weiß).
- Kein FOUC-Schutz: `app.html` ohne Inline-Skript, `theme-color` statisch `#f6f4ee`, kein `color-scheme`.
- Kein `@custom-variant dark` ⇒ `dark:`-Klassen in `ui/input`, `ui/badge` folgen dem OS (prefers-color-scheme), nicht dem Schalter.
- Harte Farben, die im Dark brechen: `background:#fff` CorridorEditor.svelte:616, CorridorEditorMobile.svelte:538; `bg-white/40` ProfileEditor.svelte:117; `#8a1f1f` OfflineSperre.svelte:165; SaveIndicator.svelte (9 Hex); Tailwind-Statusboxen `bg-green-50/bg-amber-50/text-*-800` (~91 Treffer in 13 Dateien: account 49, login, verify-email, magic-link, reset-password, forgot-password, gpx-upload). Gewollt fix: weiße Schrift auf Akzent-/Statusflächen, Switch-Knöpfe, Scrims, SVG-Häkchen, Wetter-/Risikofarben (nur Kontrast prüfen).
- Außerhalb Root-Layout: `static/offline.html` (eigenes helles CSS). Keine weiteren Layouts/Resets. Leaflet-Kacheln bleiben hell (hinnehmbar).
- Keine CSP gefunden (svelte.config.js, hooks.server.ts, henemm-infra/nginx) ⇒ Inline-Skript in `app.html` zulässig. Kommt später CSP: `kit.csp` mit Hash/Nonce.
- Altbefund: Weiß auf `--g-accent #c45a2a` = 4,34:1 (schon hell unter AA). `#b5521f` = 5,01:1.
- Akzent-Nutzung: 8× `background: var(--g-accent)`, 6× `color: var(--g-accent)`, 4 Dateien mit `bg-accent/text-accent` ⇒ Trennung Fläche/Text ist überschaubar.
- Keine Spec/ADR zu Dark Mode. `ink4_kontrast_2371.md` und `fix_2896_…` schließen #2400 explizit aus. Alle Kontrastmessungen (Unit `token()`-Regex auf app.css, e2e `TOKEN_RGB`/`messeTextknotenImBrowser`) nur hell. `scripts/contrast_audit.py`, `routes/_design/+page.svelte` hart kodiert hell.
- Tests, die beim Mechanikwechsel zwingend angepasst werden: `e2e/theme-bridge.spec.ts` AC-5, `e2e/mobile-konto-sheet.spec.ts:85-95` (prüfen Inline-Style `--color-background`).

### Variantenvergleich Mechanik
| Kriterium | A: `:root[data-theme="dark"]`-Block in app.css + Inline-Skript in app.html | B: `darkVars` um `--g-*` erweitern |
|---|---|---|
| Werte-Quelle | CSS neben hellen Tokens (eine SSOT) | ~60 Einträge TS-Map, Drift zu app.css |
| Hell-Blitz | behoben (Attribut vor erstem Paint) | bleibt |
| `theme-color`/`color-scheme` | im Skript gesetzt | erst nach Hydrierung |
| `dark:`-Varianten | per `@custom-variant dark` an Attribut gebunden | folgen weiter dem OS |
| Unit-testbar | ja (Regex auf Dark-Block) | schwer |
Entscheidung (Tech Lead): **A**. `darkVars` entfällt; `--color-*` folgen automatisch über `@theme` → `var(--g-*)`; bewusst gesetzt im Dark-Block nur `--color-border/-input` (Linien-Token, 3:1 nach WCAG 1.4.11).

### Paletten-Startwerte Dark (nachgerechnet, WCAG)
Flächen: paper/surface-0 `#141412` · card/surface-1 `#1d1d1a` · card-alt `#252522` · surface-raised `#222220` · surface-2/paper-deep `#2a2a26` · rule `#3a3a35` · rule-soft `#2c2c28`.
| Text-Token | Hex | paper | card | card-alt | surface-2 |
|---|---|---|---|---|---|
| ink | `#f1efe8` | 16,03 | 14,68 | 13,36 | 12,52 |
| ink-2 | `#d2cfc4` | 11,82 | 10,83 | 9,85 | 9,24 |
| ink-3 / ink-muted | `#aaa699` | 7,57 | 6,94 | 6,31 | 5,92 |
| ink-4 (nur Placeholder/Disabled, ADR-0008) | `#6f6c63` | 3,51 | 3,22 | 2,93 | 2,74 |
| accent als Text | `#e07a4a` | 6,19 | 5,67 | 5,16 | 4,84 |
| success | `#6fbf6a` | 8,20 | 7,51 | 6,83 | 6,41 |
| warn | `#e0a83a` | 8,64 | 7,91 | 7,20 | 6,74 |
| danger | `#ee7a7a` | 6,76 | 6,20 | 5,64 | 5,28 |
| info | `#7aa9dc` | 7,50 | 6,87 | 6,25 | 5,86 |
Akzent: Rollen trennen — Fläche mit weißer Schrift `#b5521f` (5,01:1, hell UND dunkel, behebt Altbefund 4,34), Akzent als Text hell = bisher, dunkel `#e07a4a`. Neue Tokens `--g-accent-text`, `--g-on-accent`. Statusboxen über neue Token-Paare `--g-ok-bg/-fg`, `--g-warn-bg/-fg`, `--g-danger-bg/-fg` (hell + dunkel). Nav-Glas/Hairline/Highlight/Schatten eigene Dark-Werte (Glas `rgba(20,20,18,0.86)`, Schatten schwarz mit höherer Deckung).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/app.css | MODIFY | Dark-Block `:root[data-theme="dark"]` für alle Flächen/Ink/Rule/Nav/Shadow/Akzent-/Status-Tokens; `@custom-variant dark`; neue Rollen-Tokens |
| frontend/src/app.html | MODIFY | Inline-Skript vor Paint: `gz-dark` → `data-theme`, `color-scheme`, `theme-color` |
| frontend/src/routes/+layout.svelte | MODIFY | `darkVars` raus, `applyDarkMode` setzt nur Attribut/color-scheme/theme-color |
| ~15–27 Svelte-Dateien mit harten Farben (CorridorEditor(+Mobile), ProfileEditor, OfflineSperre, SaveIndicator, account, login, register, verify-email, magic-link, reset-/forgot-password, gpx-upload, Akzent-Flächen-Stellen) | MODIFY | auf Tokens umstellen |
| frontend/static/offline.html | MODIFY | Mini-Skript + Dark-Variablen (gleiche Werte) |
| frontend/e2e/theme-bridge.spec.ts, mobile-konto-sheet.spec.ts | MODIFY | auf `data-theme` + berechnete Werte umstellen |
| frontend/e2e/helpers.ts | MODIFY | Dark-Tokens/Messung |
| neuer Unit-Test (node --test) | CREATE | Dark-Palette-Kontrast aus app.css + Weiß-auf-Akzent hell/dunkel |
| neuer Ratschen-Test | CREATE | harte Farben in src (#fff, bg-white, bg-<farbe>-NN, text-<farbe>-NNN, rgba(26,26,24) außerhalb Tokens); Ausnahmeliste darf nur sinken |
| neuer e2e-Durchlauf | CREATE | alle Routen (aus Routenbaum) im Dark, 1280 + 390 px, Textkontrast ≥4,5, kein Hell-Blitz |
| scripts/contrast_audit.py, routes/_design/+page.svelte | MODIFY | Dark mitführen (oder aus app.css lesen) |
| docs/reference/design_system.md, docs/design-system/TOKENS.md | MODIFY | Dark-Palette dokumentieren |

### Scope Assessment
- Files: ~25–35
- Estimated LoC: +450/-150 (app.css ~90, Komponenten ~200, Tests ~250)
- Risk Level: HIGH (jede Seite optisch betroffen); Mitigation: Ganzseiten-Kontrastmessung im Dark über alle Routen als Gate, Hellmodus-Regression über bestehende Kontrasttests.

### Technical Approach
Variante A, ein Workflow/ein PR (Epic themenweise abschließen), Reihenfolge innerhalb: (1) Palette als roter Unit-Test, (2) Mechanik app.css/app.html/layout + e2e-Umstellung, (3) Messlauf aller Routen im Dark ⇒ Verstoßliste, (4) Rollen-Tokens Akzent/Status, harte Farben, offline.html, (5) Ratsche scharf, wenn Liste leer. Hellmodus bleibt optisch gleich bis auf Akzentfläche `#c45a2a`→`#b5521f` (AA-Reparatur nach ADR-0008, PO-bestätigtes Leitprinzip). Bestehende Kontrasttests: Regex muss den ersten (hellen) Treffer behalten — Dark-Block hinter `:root` stellen.

### Dependencies
`@theme`-Mapping `--color-*`→`--g-*` (app.css:66-89), `@property --color-*` (initial hell, unkritisch), Umschalter in Sidebar.svelte:194-204 und KontoSheet.svelte:70-73 (nur Callback, unverändert), Service Worker liefert offline.html.

### Open Questions
- [x] Mechanik A vs. B → A (Tech Lead)
- [x] CSP verbietet Inline-Skript? → keine CSP gefunden
- [x] Akzent-Rollen → Fläche `#b5521f` + Text-Token (Tech Lead, ADR-0008)
- [x] offline.html → mitziehen (nachts relevant, kleiner Aufwand)
- [x] Systemeinstellung (prefers-color-scheme) als Startwert ohne gespeicherte Wahl → nein, nicht verlangt; Schalter bleibt einzige Quelle
- [x] Leaflet-Kacheln → bleiben hell (externe Kacheln)
