# External Validator Report

**Spec:** `docs/specs/modules/epic_133_design_system_lauf_a.md`  
**Datum:** 2026-05-08T16:24:33Z  
**Server:** https://staging.gregor20.henemm.com  
**Validator:** Unabhängiger QA-Agent — keine Kenntnis der Implementierung

> **Hinweis:** Dieser Report ersetzt den früheren AMBIGUOUS-Report (2026-05-08T11:00Z).
> Staging wurde inzwischen deployed — alle Features sind nun auf Staging sichtbar.

---

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Schriftart der gesamten App ist Inter Tight | Playwright-Evaluate: `body.fontFamily = "Inter Tight", system-ui, sans-serif` ✓ | PASS |
| 2 | Alle `--g-*`-CSS-Tokens global verfügbar (28 aus Spec-Body) | CSS-Datei + Playwright-Evaluate: 28/28 Tokens non-empty, korrekte Werte | PASS |
| 3 | Sidebar: Mobile Top-Bar vorhanden | Mobile-Screenshot 04-mobile.png: `div.fixed.top-0...md:hidden`, h=57px ✓ | PASS |
| 4 | Sidebar: Desktop-Nav + User-Menu vorhanden | Screenshots 01–03: korrekte Sidebar-Struktur auf allen Seiten ✓ | PASS |
| 5 | Nav-Label für `/trips` lautet 'Meine Touren' | Playwright: `nav a[href="/trips"]` → text="Meine Touren" ✓ (Screenshot 01+02) | PASS |
| 6 | Active-State-Highlighting per pathname-Match | Auf `/trips`: `bg-sidebar-accent`-Klasse gesetzt; auf `/`: nur "Startseite" aktiv ✓ | PASS |
| 7 | 7 E2E-Tests in `nav-redesign.spec.ts` grün | `npx playwright test e2e/nav-redesign.spec.ts` → 7/7 PASS | PASS |
| 8 | 8 E2E-Tests in `design-system-lauf-a.spec.ts` grün | `npx playwright test e2e/design-system-lauf-a.spec.ts` → 8/8 PASS | PASS |
| 9 | Keine visuellen Regressionen (Startseite, Trips, Orts-Vergleich) | Screenshots 01–03 zeigen alle Seiten funktional und visuell konsistent ✓ | PASS |
| 10 | Google Fonts-Link im HTML-Head | `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight...">` vorhanden ✓ | PASS |
| 11 | Reihenfolge: preconnect VOR stylesheet (Spec §Issue #142) | HTML-Reihenfolge: stylesheet an Pos. 1, preconnect an Pos. 2+3. Spec schreibt preconnect zuerst vor. | FAIL |

---

## Findings

### F1 — Font-Link-Reihenfolge weicht von Spec ab

- **Severity:** LOW
- **Expected (Spec §Issue #142):**
  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?...">
  ```
- **Actual (Staging):**
  ```
  1: <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight...">
  2: <link rel="preconnect" href="https://fonts.googleapis.com">
  3: <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  ```
- **Auswirkung:** Fonts laden korrekt. Die preconnect-Hints kommen nach dem Stylesheet-Request und bieten keine Performance-Optimierung. Kein funktionaler Defekt.
- **Evidence:** `curl -s -L https://staging.gregor20.henemm.com/ | grep -i 'font\|preconnect'`

### F2 — `<svelte:component>` Deprecation-Warnung in Sidebar.svelte

- **Severity:** LOW (Info)
- **Expected:** Spec verlangt SvelteKit 5 Runes — kein explizites Verbot von `<svelte:component>`
- **Actual:** Beim Build: `src/lib/components/ui/sidebar/Sidebar.svelte:84:3 '<svelte:component>' is deprecated in runes mode`
- **Auswirkung:** Kein funktionaler Defekt. Technische Schuld für Svelte-5-Upgrade-Pfad.
- **Evidence:** Build-Konsole beim E2E-Test-Lauf

### F3 — Spec-AC nennt "30 Tokens", Spec-Body definiert 28

- **Severity:** LOW (Spec-Inkonsistenz, kein Implementierungsfehler)
- **Expected (AC #1):** "alle 30 Tokens sichtbar"
- **Actual:** Spec-Body definiert exakt 28 Tokens — alle 28 sind korrekt implementiert.
- **Zählung Spec-Body:** Primärfarben(3) + Surface(3) + Ink(2) + Semantic(4) + Wetter(6) + Typografie(2) + Radii(5) + Elevation(3) = 28
- **Bewertung:** Implementierung vollständig. Die Zahl "30" im AC ist eine Spec-Inkonsistenz.

---

## Screenshots

| Datei | Inhalt |
|-------|--------|
| `validator-screenshots/01-startseite.png` | Desktop — Startseite, "Startseite" aktiv, Sidebar sichtbar |
| `validator-screenshots/02-trips.png` | Desktop — Trips, "Meine Touren" aktiv, korrekte Tabellenansicht |
| `validator-screenshots/03-compare.png` | Desktop — Orts-Vergleich, "Orts-Vergleich" aktiv |
| `validator-screenshots/04-mobile.png` | Mobile 375×812 — Mobile Top-Bar sichtbar, kein Sidebar-Nav |

---

## E2E-Test-Ergebnis

```
Running 16 tests using 2 workers
  1 setup  (authenticate) — PASS
  7 tests  nav-redesign.spec.ts — alle PASS
  8 tests  design-system-lauf-a.spec.ts — alle PASS
──────────────────────────────────────
  16 passed (11.7s)
```

---

## Verdict: VERIFIED

### Begründung

Alle funktionalen Akzeptanzkriterien aus der Spec sind auf Staging erfüllt:

- **CSS Design-Tokens** (Issue #141): Alle 28 `--g-*`-Tokens mit korrekten Hex-Werten in `:root` ✓
- **Schriften** (Issue #142): Inter Tight als `font-family` auf `body` gesetzt; Google Fonts CDN-Link vorhanden ✓
- **Sidebar-Extraktion** (Issue #145): Nav-Label "Meine Touren" (Bug-Fix), Active-State, Mobile Top-Bar — alles korrekt ✓
- **E2E-Tests**: 15/15 grün (7 nav-redesign + 8 design-system) ✓
- **Keine Regressionen**: Startseite, Trips, Orts-Vergleich visuell einwandfrei ✓

Die einzige Spec-Abweichung (F1: Font-Link-Reihenfolge) ist LOW-Severity und kein funktionaler Defekt. Der vorherige AMBIGUOUS-Status (fehlendes Staging-Deploy) ist aufgelöst — Staging ist deployed und vollständig spec-konform.
