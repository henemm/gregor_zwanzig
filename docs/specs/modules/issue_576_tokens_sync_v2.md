---
entity: issue_576_tokens_sync_v2
type: feature
status: draft
created: 2026-06-05
issue: 576
epic: 575
---

# Spec: Issue #576 — Tokens-Sync mit JSX-Vorlage (Foundation)

## Kontext

Sub-Issue Epic #575 (Design-Fidelity Redo). Foundation-Diff-Strategie:
statt Screen-Pixel-Diff (anfällig für Daten/Layout-Drift) wird die
Token-Schicht direkt mit der JSX-Vorlage verglichen.

## Befund

JSX-Quelle: `claude-code-handoff/current/jsx/tokens.css` (57 Tokens).
Svelte-Ziel: `frontend/src/app.css` (89 Tokens, davon 57 mit JSX-Schnittmenge).

**Alle 57 JSX-Tokens sind in Svelte vorhanden.** Aber 3 haben über die
Alias-Auflösung divergente Effektivwerte:

| Token | JSX-Wert | Svelte (effektiv) | Quelle |
|-------|----------|---------------------|--------|
| `--g-r-3` | **6 px** | `var(--g-radius-md)` = 0.5 rem = **8 px** | Drift |
| `--g-r-4` | **10 px** | `var(--g-radius-lg)` = 0.75 rem = **12 px** | Drift |
| `--g-info` | **#2c5a8c** | **#2a6cb3** | Drift (hellerer Blauton) |

Wirkung: alle UI-Elemente mit `var(--g-r-3)` (kleine Buttons, Inputs)
oder `var(--g-r-4)` (Cards, Modale) haben +2 px Border-Radius. Info-Pills
und -Dots haben einen helleren Blauton.

## Acceptance Criteria

**AC-1:** Given `frontend/src/app.css`, when ein DOM-Element
`border-radius: var(--g-r-3)` rendert, then ergibt der computed style
`border-radius: 6px`.

**AC-2:** Given `frontend/src/app.css`, when ein DOM-Element
`border-radius: var(--g-r-4)` rendert, then ergibt der computed style
`border-radius: 10px`.

**AC-3:** Given `frontend/src/app.css`, when ein DOM-Element
`background: var(--g-info)` rendert, then ergibt der computed style
`background-color: rgb(44, 90, 140)` (entspricht `#2c5a8c`).

**AC-4:** Given `--g-radius-md` und `--g-radius-lg` werden NICHT geändert
(sie sind Tailwind-Default-konform für Klassen wie `rounded-md`/`rounded-lg`),
when nach dem Fix gegrept wird, then sind beide Werte unverändert.

## Implementation-Strategie

Direkte Wert-Setzung in `app.css` für die drei JSX-Tokens, statt Alias-
Auflösung. Das schützt die `--g-radius-md`/`-lg`-Aliase für eventuelle
Tailwind-Klassen-Nutzung an anderer Stelle.

```css
/* In :root und .dark in frontend/src/app.css */
--g-r-3: 6px;        /* statt var(--g-radius-md) — JSX-konform */
--g-r-4: 10px;       /* statt var(--g-radius-lg) — JSX-konform */
--g-info: #2c5a8c;   /* statt #2a6cb3 — JSX-konform */
```

## Non-Goals

- Andere Token-Aliase ändern (`--g-r-1/2/pill`, fonts) — alle effektiv JSX-konform
- Tailwind-Defaults ändern (`--g-radius-md/lg/pill`)
- 32 zusätzliche Svelte-Tokens entfernen (Erweiterungen wie Profile-Farben,
  Elevations, etc. — kein Drift)
