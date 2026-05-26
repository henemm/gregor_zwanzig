# Context: Issue #377 — Contrast-Audit der Ink-Skala (WCAG-AA auf weißer Card)

## Request Summary
Kontrast-Audit aller Ink-/Accent-/Semantic-Tokens auf den drei produktiven Hintergründen (`--g-card`, `--g-card-alt`, `--g-paper`): messen → klassifizieren → bereinigen. Folgewerk zum PO-Leitprinzip „hoher Kontrast = Lesbarkeit" und zur Surface-Migration #378 (weiße Cards). Liefert Audit-Report, TOKENS.md-Freigabe-Spalte, Code-Cleanup der Token-Verstöße und eine Showcase-Sektion.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/app.css` | **Kanonische Token-Werte** (Zeilen 57–90 named-Set, 139–160 numbered-Set). Single Source of Truth. |
| `docs/design-system/TOKENS.md` | Token-Doku mit „Verwendung"-Spalte (§2 Ink, §3 Accent, §4 Semantic). Braucht neue „Freigabe"-Spalte. |
| `docs/design-system/CONTRAST-AUDIT.md` | **Zu erstellen** — Audit-Report mit Kontrast-Matrix + grep-Anhang. |
| `frontend/src/routes/_design/+page.svelte` | Bestehende Showcase-Route (443 Z., `data-testid`-Sektionen). Issue nennt sie `/_design-system` → gemeint ist `/_design`. Neue Sektion „Kontrast-Belege". |
| `frontend/src/lib/brand/BrandWordmark.svelte` | Z.33–34: `--g-ink-4` für `inkDot` + `inkCaption` („v0.20 · wetter-briefing") → **Caption = echter Inhalt = Verstoß-Kandidat**. |
| `frontend/src/lib/brand/BrandSidebar.svelte` | Z.64: `--g-ink-4` für inaktives Nav-Item. |
| `frontend/src/lib/tokens-bridge.test.ts` | Z.39: testet `--g-ink-4 == #9a958a`. Bridge-Test aus Epic #368/#369. |

## Verwendungs-Inventar (gemessen)
| Muster | Treffer | Bewertung |
|---|---|---|
| `--g-ink-faint` (gesamt, **named**) | 181 | dominanter Token im echten Code |
| └ davon als `color:` | 50 | **echte Text-Kandidaten — klassifizieren** |
| └ davon als `border*:` | 62 | OK (kein WCAG-Text-Minimum, außer Form-Input §1.4.11) |
| └ davon als `background*:` | 3 | OK (dekorativ) |
| `--g-ink-4` (gesamt, **numbered**) | 5 | nur BrandWordmark (2×), BrandSidebar (1×), app.css-Def, Bridge-Test |
| `--g-accent` als `color:` | 25 | prüfen auf Underline/Bold (C4) |
| `--g-warn` als `color:` | 8 | prüfen auf Body-Text < 14 pt → ggf. PO-Eskalation (C5) |

## Existing Patterns
- **Showcase-Route** `routes/_design/+page.svelte` nutzt durchgängig `<section data-testid="...">`-Blöcke (atoms, wordmark, brand, form-controls, card, table, dialog, accordion, …). Neue Sektion fügt sich als weiterer `data-testid="contrast-section"`-Block ein.
- **TOKENS.md** Tabellen-Format: `| Token | Wert | Verwendung |` — Freigabe-Spalte additiv anhängen.
- **Token-Bridge** (`tokens-bridge.test.ts`): Tests prüfen Token-Existenz/-Wert via `hasDecl()`. Pattern für reproduzierbare Token-Assertions.

## Token-Divergenz (KRITISCH — Kern-Risiko)
In `app.css` existieren **zwei parallele Token-Sets** mit teils abweichenden Werten:

| Konzept | named-Set (real verwendet) | numbered-Set (Issue-Matrix) | Wert gleich? |
|---|---|---|---|
| faint/4 | `--g-ink-faint #9c9a90` (181×) | `--g-ink-4 #9a958a` (5×) | **nein** (9c9a90 vs 9a958a) |
| muted/3 | `--g-ink-muted #5c5a52` | `--g-ink-3 #6b675c` | **nein** |
| warn | `--g-warning #c8882a` | `--g-warn #c08a1a` (8× color) | **nein** |
| info | `--g-info #2a6cb3` (einzig def.) | Issue-Matrix nennt `#2c5a8c` | **nein** — Issue-Wert existiert nicht im Code |

→ Die Issue-Vorab-Matrix rechnet mit dem **numbered-Set**, der echte Code nutzt überwiegend das **named-Set**. Das Audit muss die **tatsächlich in `app.css` definierten** Werte messen und Abweichungen zur Issue-Matrix melden (Issue verlangt das explizit: „Claude Code soll re-messen und Abweichungen melden").

## Dependencies
- **Upstream:** `app.css` (Token-Werte), PO-Leitprinzip (CLAUDE.md „Design-Leitprinzipien"), WCAG 2.1 §1.4.3/§1.4.6/§1.4.11.
- **Downstream:** Alle 26+ Komponenten, die `--g-ink-faint`/`--g-ink-4`/`--g-accent`/`--g-warn` als Textfarbe nutzen. Showcase-Route `_design`.
- **Mess-Tool:** Issue empfiehlt `wcag-contrast`-npm-Paket oder `axe-core`. Reproduzierbares Tool nötig (kein Hand-Rechnen).

## Existing Specs / Verwandte Arbeit
- `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md` — PO-Leitprinzip + Ursprungs-Beobachtung (`--g-ink-4` 2.85:1).
- Memory [[project_issue_378_surface_stack]] — Surface-Stack #378 (weiße Cards) live+verifiziert; Basis für dieses Audit.
- Memory [[project_atomic_design_alignment]] — Epic #368 (#369 Token-Bridge, #374 Showcase). `brand/`-Komponenten + `tokens-bridge.test.ts` + `_design`-Route stammen daher.
- `docs/design-system/TOKENS.md` — kanonische Doku.

## Risks & Considerations
- **R1 — Token-Divergenz:** Welches Set ist kanonisch? Audit muss beide messen; Fixes betreffen real `--g-ink-faint` (181×), nicht `--g-ink-4` (5×). Klären in Phase 2.
- **R2 — LoC-Limit 250:** 50 `color:`-Stellen mit `--g-ink-faint` sind potenzielle Fixes in `.svelte`/`.css` (zählen mit; `docs/`/`.md` nicht). Viele sind aber legitim (Placeholder/Disabled/Border) → echte Fix-Menge erst nach Klassifikation. Ggf. `loc_limit_override` nötig.
- **R3 — PO-Freigabe für Wert-Änderungen (C6):** Token-Namen/-Werte NICHT ohne PO ändern. `--g-warn`-Body-Text-Funde → eskalieren statt selbst Wert anpassen (Edge-Case-Empfehlung: Symbol-Affordance statt Wertänderung, um Brand-Konsistenz mit `--g-weather-sun` zu wahren).
- **R4 — Route-Name:** Issue sagt `/_design-system`, real existiert `/_design`. Auf bestehende Route setzen, nicht neu anlegen.
- **R5 — Showcase-Größe:** `_design/+page.svelte` ist bereits 443 Z.; Kontrast-Sektion additiv, Bestehendes nicht umbauen (Memory [[feedback_careful_changes]]).
- **R6 — Caption-Definition in TOKENS.md:** §2 listet `--g-ink-4` als „Captions" — widerspricht WCAG (Captions = Inhalt). Doku-Korrektur Teil des Scopes.

## Analyse-Ergebnisse (Phase 2)

### Gemessene Kontraste (reproduzierbar, WCAG 2.1 §1.4.3, Python relative-luminance)
| Token | Wert | card #fff | card-alt #faf8f1 | paper #f6f4ee | Freigabe |
|---|---|---|---|---|---|
| `--g-ink` | #1a1a18 | 17.43 | 16.40 | 15.85 | **AAA-text** |
| `--g-ink-2` | #45433d | 9.89 | 9.31 | 8.99 | **AAA-text** |
| `--g-ink-3` | #6b675c | 5.65 | 5.31 | 5.13 | **AA-text** |
| `--g-ink-muted` | #5c5a52 | 6.91 | 6.50 | 6.28 | **AA-text** (knapp unter AAA) |
| `--g-ink-4` | #9a958a | 2.98 | 2.81 | 2.71 | **FAIL** (decorative only) |
| `--g-ink-faint` | #9c9a90 | 2.82 | 2.66 | 2.57 | **FAIL** (decorative only) |
| `--g-accent` | #c45a2a | 4.34 | 4.08 | 3.94 | **AA-large only** — Body-Text fällt durch! |
| `--g-accent-deep` | #8c3e1a | 7.45 | 7.01 | 6.77 | **AAA-text** (paper nur AA) |
| `--g-good` | #3d6b3a | 6.25 | 5.88 | 5.68 | **AA-text** |
| `--g-warn` | #c08a1a | 3.05 | 2.87 | 2.77 | **AA-large** (card), FAIL card-alt/paper |
| `--g-warning` | #c8882a | 3.00 | 2.82 | 2.72 | **FAIL** (decorative) |
| `--g-bad` | #a83232 | 6.63 | 6.24 | 6.03 | **AA-text** |
| `--g-danger` | #b33a2a | 5.91 | 5.56 | 5.37 | **AA-text** |
| `--g-info` | #2a6cb3 | 5.39 | 5.07 | 4.90 | **AA-text** |
| `--g-success` | #3a7d44 | 5.00 | 4.71 | 4.55 | **AA-text** (paper grenzwertig) |

### Abweichungen zur Issue-Vorab-Matrix
- **`--g-accent` 4.34:1 statt 4.55:1** → entgegen Issue-Annahme NICHT AA-text, nur AA-large. Accent als Body-Textfarbe ist ein echter Verstoß (nicht nur AAA-Lücke).
- **`--g-info` real #2a6cb3 (5.39:1 AA), nicht #2c5a8c** — Issue-Wert existiert nicht im Code.
- `--g-warn` real schlechter (3.05 card / FAIL paper) als Issue (3.7:1).
- `--g-accent-deep` real 7.45 (Issue 7.9), auf paper nur AA.

### grep-Audit-Klassifikation (gemessen)
| Audit | Funde | Verstöße (FIX) | OK |
|---|---|---|---|
| `--g-ink-faint` als `color:` | 47 | **47** (alle echter Text: Eyebrows, Hints, Captions, Empty-States, Counter, Meta, Table-Header) | 0 |
| `--g-ink-4` als `color:` | 2 | **2** (BrandWordmark `inkDot`+`inkCaption` = Untertitel) | 0 |
| `--g-accent` als `color:` | 14 | **3** (TablePreview `.indicator-cell`, TripHeader `.h1-shortcode`, ActiveMetricRow `.mode-btn.active` — Farbe ohne Underline/Bold + unter AA) | 11 (Links mit Underline/Bold) |
| `--g-warn` als `color:` | **0** | 0 | — → **C5/PO-Eskalation entfällt** |

### Mess-Werkzeug
Kein npm-Paket (`wcag-contrast`/`axe-core`) installiert. Empfehlung: **Python-Script** (relative-luminance, keine Dependencies, reproduzierbar) als Audit-Tool — erzeugt die Matrix für CONTRAST-AUDIT.md + Showcase-Daten.

### Strategie / Empfehlung
**Ersetzungsregeln (mit bestehenden Token, KEINE Wert-Änderung → C6 gewahrt):**
1. `--g-ink-faint`/`--g-ink-4` als **Textfarbe** → `--g-ink-muted` (6.9:1, AA mit Reserve, bleibt im produktiven named-Set). Border-/Background-/Placeholder-Nutzung bleibt unberührt.
2. 3 `--g-accent`-Body-Text-Stellen → `--g-accent-deep` (7.45:1 AAA) — saubere Lösung statt Underline-Krücke.
3. `--g-warn`: keine Aktion (0 Textfunde).

**Token-Divergenz (named vs. numbered):** außerhalb dieses Audits (separater Rename-Issue, Memory `project_atomic_design_alignment`). Audit dokumentiert beide Werte, fixt mit dem dominanten named-Set.

### Scope
- **Dateien:** ~28 `.svelte` + `app.css` (Token-Fixes) + `_design/+page.svelte` (Showcase) + 1 Mess-Script ≈ **~30 Code-Dateien**. ⚠️ deutlich über 4–5-Datei-Flag.
- **LoC:** ~47 Text-Fixes + 3 Accent-Fixes + Showcase-Sektion (~100–150 Z.) + Script (~60 Z.) ≈ **~250–350 LoC** → ⚠️ `loc_limit_override` (z.B. 500) nötig. Doku (CONTRAST-AUDIT.md, TOKENS.md) zählt nicht.
- **Risiko gering:** mechanische, homogene Ersetzung; nur Text wird dunkler (genau das PO-Prinzip „Lesbarkeit gewinnt"); keine Logik. Hinweis: einige Fundstellen sind über zentrale Klassen (`[data-slot="eyebrow"]`, `.g-th` in app.css) fixbar → reduziert effektive Datei-Anzahl. Spec klärt Zentralisierung.

## Acceptance Criteria (aus Issue, Phase-3-Vorlage)
1. `docs/design-system/CONTRAST-AUDIT.md` mit vollständiger Matrix (Ink/Accent/Semantic × {Card, Card-Alt, Paper}), reproduzierbar gemessen.
2. TOKENS.md um „Freigabe"-Spalte (AAA-text / AA-text / AA-large / decorative only).
3. grep-Audit `--g-ink-4`/`--g-ink-faint` + Klassifikation (Placeholder OK vs. Caption FIX) als Anhang.
4. Fixes der Caption-/Help-Text-Verstöße (`--g-ink-faint`/`--g-ink-4` → `--g-ink-muted`/`--g-ink-3`).
5. grep-Audit `--g-accent` als `color:` → Underline/Bold sicherstellen.
6. grep-Audit `--g-warn` als `color:` auf Body-Text → PO-Eskalation.
7. Showcase-Sektion „Kontrast-Belege" in `/_design` (Swatch + Zahl + Pass/Fail-Badge).
