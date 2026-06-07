# Context: #643 — Compare-Detail-Hub `/compare/[id]` 1:1 nach screen-compare-detail.jsx

## Request Summary
Paket 2 von #582 (Compare-Design-Fidelity, Epic #575): Compare-Detail-Hub `/compare/[id]`
1:1 nach JSX-Vorlage angleichen; Pixel-Diff-Gate `G-compare-detail` bestehen.

## Befund (kritisch — Schwester-Fall zu #581)
Die Hub-Substanz ist **bereits live** und JSX-treu:
- Tab-Hub `CompareTabs.svelte` mit Kontext-Header, Status-Streifen, Tab-Leiste,
  Orte/Idealwerte/Layout/Versand/Vorschau wurde unter **#582** geliefert
  (`8dd45ccd`), + Folge-Fixes #589/#590/#591/#601/#609.
- IST ist **Signal-frei** (korrekt, #610).

Die Vorlagen sind dagegen **veraltet**:
- JSX `screen-compare-detail.jsx` enthält noch **Signal** (Z. 19/242/266) → älter als #610.
- SOLL `G-compare-detail.png` zeigt ein **altes Einseiten-Layout OHNE Tab-Leiste**
  (Header → Status-Streifen → Ranking-Liste) UND den Kanal „Email · Signal" +
  Demo-Daten „Skitouren Hochkönig". Doppelt veraltet.

→ Ein Pixel-Diff <10 % gegen diesen SOLL ist strukturell unmöglich, und ein
„1:1"-Nachbau wäre eine **Regression** (Signal & Einseiten-Layout zurückholen).
Memory-Lehre #581: „JSX=Wahrheit gilt nur, wenn JSX die NEUESTE Absicht ist …
Schwester #582 identisch" → **PO-Entscheidung nötig.**

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/[id]/+page.svelte` | Hub-Header (live, JSX-treu, Signal-frei) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | 6-Tab-Hub (live) |
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx` | JSX-Vorlage — **stale (Signal)** |
| `claude-code-handoff/current/soll/G-compare-detail.png` | SOLL — **stale (no-tab + Signal + Demo-Daten)** |
| `.claude/hooks/design_fidelity_diff.py` | `G-compare-detail` → `/compare` (falsche URL, Z. 38) |

## Existing Patterns
- #581: Trip-Detail-Fidelity-Handoff als überholt geschlossen (Substanz live, JSX/SOLL stale).
- #582-Liste (Paket 1): live, Threshold-Override 30 % mit dokumentierter SOLL-Staleness.

## Risks & Considerations
- Blindes 1:1 gegen stale SOLL = Regression (Signal/Einseiten-Layout).
- Pixel-Gate G-compare-detail mappt auf `/compare` statt `/compare/[id]` (Tool-Bug).
