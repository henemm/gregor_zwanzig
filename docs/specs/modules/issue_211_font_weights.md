---
entity_id: issue_211_font_weights
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [211]
parent_epic: 133
tags: [frontend, sveltekit, design-system, epic-133, issue-211]
---

# Issue #211 — Schrift-Weights vervollständigen (Inter Tight + JetBrains Mono)

## Approval

- [ ] Approved

## Purpose

Der Google-Fonts-Link in `frontend/src/app.html` lädt aktuell nur unvollständige Schriftgewichte (Inter Tight: 400/500/600; JetBrains Mono: 400). Headings mit `font-weight: 700` und Mono-Text in 500/600 werden vom Browser synthetisch fett gerendert, was sichtbar weniger sauber rendert als echtes Bold/Semibold. Diese Spec führt die fehlenden Weights nach: Inter Tight 700, JetBrains Mono 500 und 600. Die Änderung ist eine einzelne HTML-Zeile, der dazugehörige E2E-Test sichert den Status für die Zukunft.

## Source

- **EDIT:** `frontend/src/app.html` — Google-Fonts-`<link>` um drei Weights erweitern (1 Zeile)
- **NEU:** `frontend/e2e/font-weights.spec.ts` — Playwright-Test, der die geladenen Weights in der URL prüft
- **Identifier:** kein Code-Identifier, nur HTML-Attribut

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.html` | bestehend (EDIT) | Lädt Google-Fonts beim ersten Seitenaufruf; nach Änderung enthält der URL-Parameter alle Spec-Weights |
| Google Fonts Service | extern | Liefert die WOFF2-Dateien für die zusätzlichen Weights |
| `frontend/src/app.css` Z. 100–115 | bestehend | Setzt `font-family: 'Inter Tight'` und `font-family: 'JetBrains Mono'`; nutzt Weights über `font-weight`-CSS-Regeln in Komponenten |

## Implementation Details

### §1 Edit `frontend/src/app.html`

Aktuelle Zeile (Z. 7):

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
```

Neue Zeile:

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
```

Geändert wurden zwei `wght@…`-Parameter:
- Inter Tight: `400;500;600` → `400;500;600;700`
- JetBrains Mono: `400` → `400;500;600`

Alles andere (preconnect, display=swap) bleibt unverändert.

### §2 Neuer Test `frontend/e2e/font-weights.spec.ts`

Playwright-Test, der die Startseite lädt und das `<link>`-Element zu fonts.googleapis.com inspiziert. Prüft, dass der `href` die Spec-konformen `wght@…`-Werte enthält.

```typescript
import { test, expect } from '@playwright/test';

test.describe('Issue #211 — Schrift-Weights vollständig geladen', () => {
  test('AC-1: Google-Fonts-Link enthält Inter Tight 400;500;600;700', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('Inter+Tight:wght@400;500;600;700');
  });

  test('AC-2: Google-Fonts-Link enthält JetBrains Mono 400;500;600', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('JetBrains+Mono:wght@400;500;600');
  });

  test('AC-3: Google-Fonts-Link enthält display=swap', async ({ page }) => {
    await page.goto('/');
    const linkHref = await page
      .locator('link[rel="stylesheet"][href*="fonts.googleapis.com"]')
      .first()
      .getAttribute('href');
    expect(linkHref).toContain('display=swap');
  });
});
```

`/` ist auth-gated → leitet auf `/login` weiter. Der `<link>` ist im selben `app.html` enthalten, also auf jeder Route präsent. Test funktioniert ohne Login.

### §3 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| EDIT | `frontend/src/app.html` | Schrift-Weights ergänzen (1 Zeile geändert) | 0 (Längen-neutral) |
| NEU | `frontend/e2e/font-weights.spec.ts` | Playwright-Test für die 3 ACs | ~35 |
| **Summe** | | | **~35 LoC** |

Unter Default-LoC-Limit 250. Kein Override nötig.

## Expected Behavior

- **Input:** keine Laufzeit-Inputs. Beim Seitenaufruf lädt der Browser den Stylesheet von Google Fonts.
- **Output:** 
  - Browser kann Inter Tight in Weights 400/500/600/700 nativ rendern (echtes Bold statt synthetisches).
  - Browser kann JetBrains Mono in Weights 400/500/600 nativ rendern.
  - Im DOM: `<link>` mit den oben angegebenen `wght@…`-Werten.
- **Side effects:**
  - Minimal mehr Traffic (zusätzliche Font-Dateien beim ersten Request, ~10–20 KB total).
  - Keine Code-Pfad-Änderung in Komponenten.

## Acceptance Criteria

- **AC-1:** Given das Frontend wird geladen / When der DOM-`<link>` zu fonts.googleapis.com inspiziert wird / Then enthält der `href` exakt den Substring `"Inter+Tight:wght@400;500;600;700"`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Frontend wird geladen / When der DOM-`<link>` zu fonts.googleapis.com inspiziert wird / Then enthält der `href` exakt den Substring `"JetBrains+Mono:wght@400;500;600"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Frontend wird geladen / When der DOM-`<link>` zu fonts.googleapis.com inspiziert wird / Then enthält der `href` den Substring `"display=swap"`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Visuelle Verifikation:** Der Test prüft die URL-Struktur, nicht das tatsächliche Glyph-Rendering. Optisch sauberes Bold/Semibold ist Bonus-Sichtprüfung post-deploy.
- **Traffic-Mehrkosten:** ~10–20 KB zusätzliche Font-Daten beim ersten Aufruf. Vernachlässigbar.
- **Synthetisches Bold-Fallback:** Falls Google Fonts kurzzeitig nicht erreichbar wäre, würde der Browser weiter synthetisches Bold zeigen — das ist der Status Quo, kein Regress.

## Changelog

- 2026-05-13: Initial spec — Issue #211 (Epic #133 Sub-Story 4 von 6). Schrift-Weights für Inter Tight (700) und JetBrains Mono (500, 600) im Google-Fonts-Link ergänzen. 3 ACs zur URL-Strukturprüfung via Playwright. Trivial-Scope (~35 LoC, 1 Zeile Edit, 1 neue Test-Datei).
