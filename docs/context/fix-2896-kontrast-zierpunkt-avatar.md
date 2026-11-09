# Context: fix-2896-kontrast-zierpunkt-avatar

## Request Summary
Folgeticket aus #2371: Zwei Textstellen liegen unter WCAG AA (4,5:1) und sollen angehoben werden:
(1) das „Zierzeichen ':.'" auf /trips/new, /compare/new, /archiv bei 1280 px (2,46:1),
(2) die Avatar-Initialen im Konto-Kreis im Archiv (4,34:1).

## Ursachen (belegt)
- **„':.'" ist der Punkt der Logo-Wortmarke „gregor.zwanzig"**: Der AC-1-Detektor in
  `frontend/e2e/ink4-kontrast.staging.spec.ts:58-71` meldet Treffer als `span: "."`; im Issue verkürzt zu ':.'.
  Quelle: `frontend/src/lib/brand/BrandWordmark.svelte:34` `inkDot = dark ? 'rgba(246,244,238,0.45)' : 'var(--g-ink-4)'`
  (markiert `audit:exempt — Wordmark/Logo-Glyph`), verwendet in Zeile ~57 und ~74.
  Nur bei 1280 px sichtbar, weil die Desktop-Sidebar (`ui/sidebar/Sidebar.svelte:81` → `ui/wordmark/Wordmark.svelte`
  → `BrandWordmark`) auf `--g-paper-deep` liegt; #9a958a darauf = 2,46:1.
- **Avatar-Initialen 4,34:1** = `#ffffff` auf `--g-accent` (#c45a2a), gerechnet: 4,34. Fundstellen:
  - `frontend/src/lib/components/ui/sidebar/BottomNav.svelte:161-173` `.konto-kreis__avatar` (Mobile-Konto-Kreis, im Archiv gemessen)
  - `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte:115-127` `.konto__avatar` (gleiches Muster, Konto-Blatt; nicht gemessen, gleicher Fehler)
  - `frontend/src/lib/brand/BrandUserBadge.svelte:22,27` `--g-paper` auf `--g-accent` bei `accent=true` (3,94:1), sonst auf `--g-ink` (ok). Nur in `BrandSidebar` (Design-Seite /_design) genutzt.

## Rechenwerte (WCAG-Formel)
| Vordergrund | Hintergrund | Verhältnis |
|---|---|---|
| #ffffff | #c45a2a (--g-accent) | 4,34 |
| #f6f4ee (--g-paper) | #c45a2a | 3,94 |
| #ffffff | #8c3e1a (--g-accent-deep) | 7,45 |
| #f6f4ee | #8c3e1a | 6,77 |
| #6b675c (--g-ink-3) | #f6f4ee | 5,13 |

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/brand/BrandWordmark.svelte | Logo-Punkt in --g-ink-4 (+ dark-Variante rgba 0.45) |
| frontend/src/lib/components/ui/sidebar/BottomNav.svelte | Avatar weiß auf Akzent |
| frontend/src/lib/components/ui/sidebar/KontoSheet.svelte | Avatar weiß auf Akzent (Pendant) |
| frontend/src/lib/brand/BrandUserBadge.svelte | Avatar paper auf Akzent (accent=true) |
| frontend/e2e/ink4-kontrast.staging.spec.ts | Bestehender Staging-Kontrasttest (#2371), nur 390 px |
| docs/specs/modules/ink4_kontrast_2371.md | Vorgänger-Spec |
| docs/reference/design_system.md:25,66,237ff | Regel: ink-4 nur Placeholder/Disabled; Akzent; Logo-Abschnitt |

## Existing Patterns
- #2371 hat ink-4-Text auf `--g-ink-3` angehoben (5,13:1) und den Staging-Test mit TreeWalker auf #9a958a gebaut.
- `--g-accent-deep` (#8c3e1a) ist der etablierte dunklere Akzent für Text/Links (z. B. „Bearbeiten →").

## Dependencies
- Upstream: Design-Tokens in `frontend/src/app.css` (`--g-ink-3`, `--g-ink-4`, `--g-accent`, `--g-accent-deep`).
- Downstream: Wortmarke erscheint auf jeder Seite (Desktop-Sidebar, Login, ggf. Mobile-Header); Avatar in Mobile-Nav und Konto-Blatt.
  Golden-/Snapshot-Tests, die Wortmarken-Markup enthalten, ggf. nachziehen.

## Existing Specs
- `docs/specs/modules/ink4_kontrast_2371.md`, `docs/specs/modules/fix_2879_kontrast_wcag_aa.md`

## Risks & Considerations
- WCAG 1.4.3 nimmt Logos formal aus; das Issue (PO) verlangt trotzdem Anhebung, Design-Leitprinzip „hoher Kontrast gewinnt" stützt das.
  Die `audit:exempt`-Markierung am Logo-Punkt entfällt dann.
- Dark-Variante der Wortmarke (`rgba(246,244,238,0.45)`) mitbetrachten, damit der Logo-Punkt in beiden Varianten konsistent ist.
- Avatar: Hintergrund auf `--g-accent-deep` statt Textfarbe zu ändern (Weiß auf Akzent ist das Maximum, mehr geht nur über dunkleren Grund).
- Staging-Test um 1280-px-Viewport erweitern, sonst bleibt der Logo-Punkt ungeprüft.

## Analysis

### Type
Bug (Kontrast unter WCAG AA, Folge aus #2371)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/brand/BrandWordmark.svelte | MODIFY | `inkDot`: hell `--g-ink-4` → `--g-ink-3` (4,66 auf paper-deep, 5,13 auf paper); dunkel `rgba(246,244,238,0.45)` → `0.55` (4,18 → 5,59 auf `--g-ink`, gleich wie Caption). `audit:exempt` am Punkt entfällt (2 Stellen + Kommentar Z. 34) |
| frontend/src/lib/components/ui/sidebar/BottomNav.svelte | MODIFY | `.konto-kreis__avatar` background `--g-accent` → `--g-accent-deep` (Weiß 4,34 → 7,45) |
| frontend/src/lib/components/ui/sidebar/KontoSheet.svelte | MODIFY | `.konto__avatar` gleich (Pendant, gleicher Fehler) |
| frontend/src/lib/brand/BrandUserBadge.svelte | MODIFY | `avatarBg` bei `accent=true` → `--g-accent-deep` (paper 3,94 → 6,77) |
| frontend/src/routes/__tests__/fixtures/auth/*.de.html (4) | MODIFY | Golden: Punktfarbe `--g-ink-4` → `--g-ink-3` |
| tests/golden/f3_home_listen/*.html (6), tests/golden/f4_konto_admin_nav/navigation.{de,en}.html | MODIFY | Golden nachziehen (Punktfarbe, ggf. Avatar) |
| frontend/e2e/ink4-kontrast.staging.spec.ts | MODIFY | Zweiter Viewport 1280 px (Logo-Punkt in Desktop-Sidebar) + Avatar-Kontrast >= 4,5 im Archiv (390 px) |
| frontend/src/lib/__tests__/ink4_waechter.test.ts | CHECK | Ratsche zählt exempt-Zeilen nicht; nach Wechsel auf ink-3 kein ink-4 mehr am Punkt, Zählwert bleibt gleich oder sinkt |

### Scope Assessment
- Files: 4 Quell-Dateien + 1 E2E + ~12 Golden-Dateien (mechanisch)
- Estimated LoC: Quellcode ~+8/-8, Test ~+40
- Risk Level: LOW — reine Farbwerte, keine Logik; sichtbare Wirkung: Logo-Punkt etwas dunkler, Konto-Kreis dunkleres Orange

### Technical Approach
- Logo-Punkt: vorhandenes Token `--g-ink-3` (gleiche Lösung wie #2371), keine neue Farbe. Das PO-Issue verlangt die Anhebung trotz formaler WCAG-Logo-Ausnahme; Design-Leitprinzip „hoher Kontrast gewinnt“ stützt das. Logo-Akzent „zwanzig“ (`--g-accent` 4,34 auf paper) bleibt außerhalb des Scopes (Markenfarbe, nicht im Issue).
- Avatar: Weiß ist schon das hellste Mögliche, also dunkleren Grund wählen: etabliertes `--g-accent-deep` (bereits für Akzent-Text genutzt). Alle drei Avatar-Stellen gleich ziehen (Konsistenz, ein Muster).
- Nachweis aus Nutzersicht: Staging-Test rechnet Kontrast aus berechneten Farben (vorhandene `messeKontrast`-Logik) bei 1280 px auf /trips/new, /compare/new, /archiv für den Wortmarken-Punkt und bei 390 px für die Avatar-Initialen; vorher rot (2,46 bzw. 4,34), nachher >= 4,5.
- Kern-Schicht: Unit-Test, der die gerenderte Wortmarke (hell/dunkel) und die Avatar-CSS auf Token prüft und den Kontrast über die Token-Werte aus app.css rechnet (Muster `onboarding_kontrast_und_katalogtreue.test.ts`: `kontrast(token(...), token(...))`).

### Dependencies
- Tokens aus `frontend/src/app.css` (`--g-ink-3` #6b675c, `--g-accent-deep` #8c3e1a, `--g-paper-deep` #ecead9) — unverändert.
- Wortmarke auf allen Seiten (Sidebar, Login, Passwort-Seiten, Startseite) → Golden-Dateien.

### Open Questions
- keine (Farbwahl folgt etablierten Tokens und #2371)

## TDD-RED-Stand (Phase 5, 2026-11-09)

- Kern-Test `frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts`: 9 von 12 rot (Punkt hell 2,46/2,71, dunkel 4,17, Badge 3,94, Konto-Kreis/-Blatt 4,34); 3 Gegenproben grün.
- Staging-Messlauf `frontend/e2e/ink4-kontrast.staging.spec.ts` (#2896-Block): 4 rot (Punkt = #9a958a auf drei Seiten, Konto-Kreis 4,34).
- **Hinweis für /50-implement:** `frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts` hält SHA-Goldens `wordmarkLeft`/`wordmarkNone` des de-Renders der Wortmarke; die neue Punktfarbe ändert den Render ⇒ diese beiden Hashes gezielt nachziehen (Golden, Spec-Scope „Golden-Dateien nachziehen").
- Frontend-Abhängigkeiten fehlten im Worktree: `cd frontend && npm ci` vor `npm test`.
