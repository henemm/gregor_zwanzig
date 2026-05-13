---
entity_id: issue_211_font_weights
type: context
created: 2026-05-13
issues: [211]
parent: 133
---

# Context + Analyse: Issue #211 — Schrift-Weights vervollständigen

## Request Summary

Google-Fonts-Link in `frontend/src/app.html` erweitern, damit Inter Tight (700) und JetBrains Mono (500, 600) geladen werden statt vom Browser synthetisch fett gerendert.

## Ist

`frontend/src/app.html` Z. 7:
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
```

- Inter Tight: 400, 500, 600
- JetBrains Mono: 400
- `display=swap` ✓ vorhanden
- `preconnect` zu fonts.googleapis.com + fonts.gstatic.com ✓ vorhanden

## Soll (laut #211)

- Inter Tight: 400, 500, 600, **700**
- JetBrains Mono: 400, **500, 600**

## Änderung

Eine Zeile:
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
```

## Test-Strategie

**E2E (Playwright):** Test prüft, dass das `<link>`-Element die erwarteten Weights in der URL hat. Datei: `frontend/e2e/font-weights.spec.ts`.

Alternative (zu komplex): Visueller Snapshot mit Heading in `font-weight: 700` und Pixel-Diff. Nicht im Scope, da unverhältnismäßig.

## Akzeptanz

- Link enthält Inter Tight `wght@400;500;600;700`
- Link enthält JetBrains Mono `wght@400;500;600`
- Keine 404er im Network-Tab (manuelle Sichtprüfung post-deploy)
- Bestehende Komponenten brechen nicht (Schmaler Schrift-Fallback bleibt)

## Datei-Plan

| Art | Datei | LoC |
|-----|-------|-----|
| EDIT | `frontend/src/app.html` | +0/-0 (1 Zeile geändert, gleiche Länge) |
| NEU | `frontend/e2e/font-weights.spec.ts` | ~30 |
| **Summe** | | **~30 LoC** |

Unter dem 250er Default-LoC-Limit, kein Override nötig.

## Risiken

- Keine. Trivial.
