---
entity_id: fix_2896_kontrast_zierpunkt_avatar
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [frontend, kontrast, design-system, wortmarke, avatar, wcag-aa, adr-0008]
---

# Kontrast: Logo-Punkt der Wortmarke und Avatar-Initialen (#2896)

## Approval

- [ ] Approved

## Purpose

Zwei Texte liegen unter WCAG-AA (4,5:1): der Punkt der Wortmarke „gregor.zwanzig" (im Issue als „Zierzeichen ':.'" bezeichnet, `--g-ink-4` = 2,46:1 auf der Desktop-Sidebar bei 1280 px) und die Initialen im Konto-Kreis (Weiß auf `--g-accent` = 4,34:1). Die Spec hebt den Logo-Punkt auf `--g-ink-3` und legt die Avatar-Initialen auf den dunkleren Grund `--g-accent-deep`.

Folgeticket aus #2371 (Epic #2508). Leitprinzip: „Hoher Kontrast = Lesbarkeit" (`docs/reference/design_system.md`, PO-bestätigt 2026-05-25).

## Source

- **File:** `frontend/src/lib/brand/BrandWordmark.svelte` (Logo-Punkt, Zeile ~34, ~57, ~74) und die Avatar-Stile in `frontend/src/lib/components/ui/sidebar/BottomNav.svelte`, `KontoSheet.svelte`, `frontend/src/lib/brand/BrandUserBadge.svelte`
- **Identifier:** `inkDot` (Wortmarke), `.konto-kreis__avatar`, `.konto__avatar`, `avatarBg`

> **Schicht:** ausschließlich Frontend (SvelteKit, `frontend/src/...`). Keine Go-API-, keine Python-Änderung, keine Datenänderung. Die Wortmarke wird über `ui/wordmark/Wordmark.svelte` und `ui/sidebar/Sidebar.svelte` auf allen Seiten gerendert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Kein Trip-/Compare-Pendant betroffen. Wortmarke und Avatar sind seitenübergreifende Shell-Bausteine; es gibt keine Komponente, die in zwei Varianten existiert. Es entsteht keine neue Komponente. Die drei Avatar-Stellen werden gleich gezogen (ein Muster).
> - **Mandantentrennung:** nicht betroffen (keine Nutzerdaten bewegt; der Avatar zeigt nur Initialen des angemeldeten Nutzers, Quelle unverändert).
> - **Kanäle:** nicht betroffen (reine UI-Farbänderung; kein Briefing- oder Alarm-Inhalt).

## Scope

**Im Scope**

- `BrandWordmark.svelte`: `inkDot` hell `--g-ink-4` → `--g-ink-3`; dunkel `rgba(246,244,238,0.45)` → `rgba(246,244,238,0.55)`; Marker `audit:exempt — Wordmark/Logo-Glyph` am Punkt entfällt (2 Stellen und Kommentar).
- Avatar-Grund `--g-accent` → `--g-accent-deep` in `BottomNav.svelte` (`.konto-kreis__avatar`), `KontoSheet.svelte` (`.konto__avatar`) und `BrandUserBadge.svelte` (`avatarBg` bei `accent=true`).
- Golden-Dateien nachziehen, die genau diese Farben festschreiben.
- Playwright-Staging-Test erweitern (1280 px für den Punkt, 390 px für Avatar).
- Eine Doku-Zeile in `docs/reference/design_system.md` (Abschnitt „8 · Logo").

**Nicht im Scope**

- Logo-Akzent „zwanzig" (`--g-accent` auf Papier 4,34:1): Markenfarbe, nicht im Issue (siehe Known Limitations).
- Token-Definitionen in `frontend/src/app.css` bleiben unverändert.
- Dark-Mode-Wert von `--g-ink-3` (#2400), Danger-Rot (#1831).
- Layout, Größen, Schrift, Klickverhalten von Wortmarke und Avatar.

## Estimated Scope

- **LoC:** Quellcode ca. +8 / -8, Tests ca. +90 (Kern ca. 50, Staging ca. 40)
- **Files:** 4 Quelldateien, 1 Doku, 1 neuer Kern-Test, 1 erweiterter E2E-Test, ca. 12 Golden-Dateien (mechanisch)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Design-Tokens | `--g-ink-3` `#6b675c`, `--g-accent-deep` `#8c3e1a`, `--g-paper-deep` `#ecead9`, `--g-ink` (dunkler Grund der Wortmarken-Variante); unverändert |
| `docs/adr/0008-kontrast-vor-optik.md` | ADR | Text ≥ 4,5:1, `--g-ink-4` nur Placeholder/Disabled |
| `docs/specs/modules/ink4_kontrast_2371.md`, `fix_2879_kontrast_wcag_aa.md` | Vorgänger-Specs | gleiche Lösung (Token-Anwendung), Messlogik |
| `frontend/e2e/ink4-kontrast.staging.spec.ts` | Bestehender Staging-Test | wird um 1280 px und Avatar erweitert (`messeKontrast`) |
| `frontend/src/lib/__tests__/ink4_waechter.test.ts` | Ratsche | prüfen: Zählwert bleibt gleich oder sinkt |
| `frontend/src/routes/_home/__tests__/onboarding_kontrast_und_katalogtreue.test.ts` | Muster | Vorbild für Kern-Test (`kontrast(token(...), token(...))`, `compile` aus `svelte/compiler`) |

## Implementation Details

```
Berechnete Werte (WCAG-Formel):
  Logo-Punkt hell:   --g-ink-3 #6b675c auf --g-paper-deep #ecead9 = 4,66  (vorher ink-4: 2,46)
                     --g-ink-3 auf --g-paper #f6f4ee = 5,13
  Logo-Punkt dunkel: rgba(246,244,238,0.55) auf --g-ink = 5,59           (vorher 0.45: 4,18)
  Avatar:            #ffffff auf --g-accent-deep #8c3e1a = 7,45          (vorher auf --g-accent: 4,34)
  BrandUserBadge:    --g-paper auf --g-accent-deep = 6,77                (vorher auf --g-accent: 3,94)

1. Kern-Test zuerst schreiben, rot gegen den Ist-Stand:
   frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts (node --test)
   - rendert BrandWordmark (hell und dunkel) und BrandUserBadge (accent=true) mit
     svelte/compiler bzw. SSR-Render, liest die gerenderte Punkt-/Avatar-Farbe
   - liest die Token-Hex-Werte aus app.css, rechnet den Kontrast (Alpha gegen den Grund gemischt)
   - Avatar-CSS von BottomNav/KontoSheet: kompiliertes CSS, Regel .konto-kreis__avatar /
     .konto__avatar, background-Token + color gegen Kontrast
2. BrandWordmark: inkDot + Kommentar + 2 Marker
3. BottomNav, KontoSheet, BrandUserBadge: Avatar-Grund --g-accent-deep
4. Golden-Dateien (frontend/src/routes/__tests__/fixtures/auth/*.de.html (4),
   tests/golden/f3_home_listen/*.html (6), tests/golden/f4_konto_admin_nav/navigation.{de,en}.html)
   gezielt nachziehen, nur dort, wo Punktfarbe oder Avatar-Grund festgeschrieben ist
5. Staging-Test erweitern (Abschnitt Geplante Tests)
6. design_system.md Abschnitt 8: ein Satz zu Punktfarbe (--g-ink-3) und Avatar-Grund (--g-accent-deep)
```

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new`, `/compare/new` oder `/archiv` am Desktop (1280 px) bzw. mobil (390x844).
- **Output:** Der Punkt der Wortmarke in der Desktop-Sidebar ist mit mindestens 4,5:1 lesbar. Die Initialen im Konto-Kreis (Mobil-Navigation) und im Konto-Blatt stehen auf dunklerem Orange mit mindestens 4,5:1. Kein Text dort hat die berechnete Farbe `#9a958a` (Regression #2371).
- **Side effects:** Keine. Logo-Punkt wird etwas dunkler, Konto-Kreis dunkleres Orange; Layout und Logik unverändert.

## Acceptance Criteria

- **AC-1:** Given die Seiten `/trips/new`, `/compare/new` und `/archiv` bei 1280 px Breite mit der Desktop-Sidebar / When der Kontrast des Wortmarken-Punkts (berechnete Textfarbe gegen den effektiven Hintergrund der Sidebar) gemessen wird / Then beträgt er mindestens 4,5:1 und die Farbe ist nicht `#9a958a`.
  - Test: Playwright-Messlauf gegen Staging (Viewport 1280x800), `getComputedStyle(...).color` des Punkt-Spans in der Sidebar-Wortmarke und effektiver Hintergrund, WCAG-Formel wie `messeKontrast`; vorher rot (2,46), nachher >= 4,5 auf allen drei Seiten.

- **AC-2:** Given das Archiv `/archiv` bei 390x844 mit der Mobil-Navigation und dem Konto-Kreis / When der Kontrast der Avatar-Initialen (`.konto-kreis__avatar`, Textfarbe gegen Hintergrundfarbe) gemessen wird / Then beträgt er mindestens 4,5:1.
  - Test: Playwright-Messlauf gegen Staging (390x844) liest berechnete Farbe und Hintergrund des Konto-Kreis-Avatars; vorher rot (4,34), nachher >= 4,5 (erwartet 7,45).

- **AC-3:** Given das geöffnete Konto-Blatt (`KontoSheet`) bei 390x844 / When der Kontrast der Avatar-Initialen (`.konto__avatar`) gemessen wird / Then beträgt er mindestens 4,5:1 und entspricht dem Wert des Konto-Kreises (gleicher Grund, ein Muster).
  - Test: Playwright-Messlauf gegen Staging öffnet über den Konto-Kreis das Konto-Blatt, misst berechnete Farbe und Hintergrund des Avatars und vergleicht mit AC-2.

- **AC-4:** Given die dunkle Variante der Wortmarke (`dark`) auf dunklem Grund / When der Kontrast des Punkts (Alpha 0,55 gegen den dunklen Grund gemischt) berechnet wird / Then beträgt er mindestens 4,5:1.
  - Test: Kern-Test (`node --test`) rendert `BrandWordmark` mit `dark=true`, liest die gerenderte Punktfarbe und den Grund-Token aus `app.css`, mischt den Alphawert und prüft >= 4,5 (erwartet 5,59); Gegenprobe: mit Alpha 0,45 muss der Test rot werden (4,18).

- **AC-5:** Given der Kern-Test für die helle Wortmarke und `BrandUserBadge accent=true` / When Punktfarbe gegen `--g-paper-deep` und `--g-paper` bzw. Initialen gegen den Avatar-Grund berechnet werden / Then liegen alle Werte bei mindestens 4,5:1 (Punkt 4,66 bzw. 5,13; Badge 6,77).
  - Test: Kern-Test (`node --test`) misst am gerenderten Markup (kein Dateiinhalt-Check) mit Token-Werten aus `app.css`; die Verfälschung „Punkt zurück auf `--g-ink-4`" bzw. „Badge zurück auf `--g-accent`" muss rot werden.

- **AC-6:** Given die Seiten `/trips/new`, `/compare/new` und `/archiv` bei 390x844 (Regression aus #2371) / When jeder sichtbare Textknoten geprüft wird / Then hat kein Textknoten die berechnete Farbe `#9a958a` (außer `::placeholder` und `:disabled`-Inputs), und die bestehenden Prüfungen (gesperrte Tabs, deaktiviertes Speichern, Trip/Compare-Parität) bleiben grün.
  - Test: bestehender Staging-Test `ink4-kontrast.staging.spec.ts` (AC-1, AC-2, AC-3, AC-5 aus #2371) läuft unverändert grün; der Logo-Punkt ist am Mobil-Viewport nicht sichtbar und erzeugt keinen Treffer.

## Geplante Tests

| Schicht | Test | Nachweis |
|---------|------|----------|
| Kern (deterministisch, ohne Netz) | `frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts` (neu, `node --test`, Muster `onboarding_kontrast_und_katalogtreue.test.ts`: gerenderte Komponente + Token aus `app.css`, `kontrast(token(...), token(...))`) | AC-4, AC-5 |
| Live-E2E (nur in `/e2e-verify`) | `frontend/e2e/ink4-kontrast.staging.spec.ts` erweitert: Viewport 1280x800 für Logo-Punkt auf drei Seiten, 390x844 für Avatar (Kreis und Konto-Blatt) | AC-1, AC-2, AC-3, AC-6 |
| Bestandstests | `ink4_waechter.test.ts` (Zählwert bleibt gleich oder sinkt), Golden-Dateien (auth-Fixtures, `tests/golden/f3_home_listen/*`, `f4_konto_admin_nav/*`) | prüfen, nur gezielt nachziehen |
| Fresh-Eyes | Screenshot Sidebar (1280) und Konto-Kreis (390) | Wortmarke bleibt als Marke erkennbar, Avatar lesbar, Layout unverändert |

Die Frontend-Tests laufen über `node --test` (kein Vitest; `frontend/package.json`: `node --import ./test-lib-loader.mjs --experimental-strip-types --test`). Kein Mock-Theater; Verhaltensnachweis aus gerendertem DOM bzw. echtem Browser.

## Dateiliste (geplant)

| Datei | Änderung |
|-------|----------|
| `frontend/src/lib/brand/BrandWordmark.svelte` | MODIFY |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | MODIFY |
| `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte` | MODIFY |
| `frontend/src/lib/brand/BrandUserBadge.svelte` | MODIFY |
| `frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts` | CREATE |
| `frontend/e2e/ink4-kontrast.staging.spec.ts` | MODIFY |
| `frontend/src/routes/__tests__/fixtures/auth/*.de.html` (4) | MODIFY (Golden) |
| `tests/golden/f3_home_listen/*.html` (6), `tests/golden/f4_konto_admin_nav/navigation.{de,en}.html` | MODIFY (Golden, nur falls betroffen) |
| `docs/reference/design_system.md` (Abschnitt 8 · Logo) | MODIFY (ein Satz) |
| `frontend/src/lib/__tests__/ink4_waechter.test.ts` | CHECK |
| `frontend/src/app.css` | unverändert |

## Test Plan

Siehe `## Geplante Tests`: Kern-Test (AC-4, AC-5) zuerst rot schreiben, dann Implementierung; Staging-Messlauf für AC-1 bis AC-3 und AC-6 in `/e2e-verify`; Golden-Dateien und Ratsche prüfen; Fresh-Eyes-Blick auf Sidebar und Konto-Kreis.

## Definition of Done

- AC-1 bis AC-6 erfüllt und nachgewiesen (Kern-Schicht grün, Staging-Messlauf grün).
- Logo-Punkt (hell/dunkel) und alle drei Avatar-Stellen bei mindestens 4,5:1; kein `audit:exempt` mehr am Logo-Punkt.
- Golden-Dateien konsistent, Ratsche `ink4_waechter` grün (Zählwert nicht gestiegen).
- Alle 6 CI-Checks grün, Deploy und Selftest ohne Befund.

## Known Limitations

- Der Logo-Akzent „zwanzig" (`--g-accent` auf Papier 4,34:1) bleibt bewusst außerhalb des Scopes: Markenfarbe, nicht im Issue genannt. Eine Anhebung wäre eine Markenentscheidung (eigenes Ticket).
- WCAG 1.4.3 nimmt Logos formal von der Kontrastpflicht aus. Die Anhebung des Punkts erfolgt trotzdem, weil das PO-Issue sie verlangt und das Design-Leitprinzip „hoher Kontrast gewinnt" sie stützt.
- Weiß auf `--g-accent` ist bereits das Maximum für diesen Grund; mehr Kontrast geht nur über den dunkleren Grund. Der Konto-Kreis wird dadurch sichtbar dunkler orange.
- Der Staging-Messlauf braucht eine eingeloggte Staging-Sitzung (Staging-`.env`); lokaler Nachweis ersetzt ihn nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Anwendung vorhandener Tokens (`--g-ink-3`, `--g-accent-deep`) nach ADR-0008 „Kontrast vor Optik" und `design_system.md`; keine neue Entscheidungsfläche, keine Abweichung von einem bestehenden ADR.

## Changelog

- 2026-11-09: Initial spec created (Issue #2896, Folge aus #2371, Epic #2508)
- 2026-11-09: Validierung (Phase 7): zusätzlich mechanisch geändert `frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts` (zwei Golden-Hashes `wordmarkLeft`/`wordmarkNone`, gebildet über das gerenderte Wortmarken-HTML, in dem die Punktfarbe steht). Der wirkungslose Marker `audit:exempt: Markenname/Logo` an der Wortmarke ist mit entfallen (`contrast_audit.py` wertet ihn nicht aus).
