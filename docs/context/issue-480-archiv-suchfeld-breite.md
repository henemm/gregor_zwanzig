# Context: Issue #480 — Archiv Suchfeld-Breite

## Request Summary
Das Suchfeld im Archiv-Screen (`/archiv`) nimmt nur ~40% der Toolbar-Breite ein, weil es per `flex:0 0 380px` auf 380px fixiert ist. SOLL: volle verfügbare Breite.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/archiv/+page.svelte` | Einzige betroffene Datei; Zeile 92: Toolbar-Div, Zeile 93: Such-Wrapper mit `flex:0 0 380px` |
| `docs/design-requests/issue_15_atomic_design/spec/screen-archive.jsx` | JSX-Vorlage (hat ebenfalls 380px — Audit-Finding M-08 übersteuert das) |
| `docs/analysis/epic_404_phase3_soll_ist_vergleich.md` | Quelle des Findings M-08 |

## Existing Patterns
- Andere Seiten (subscriptions, locations, trips) nutzen `max-w-xs` oder keine Breitenbeschränkung für Suchfelder
- Wenn Suche + weitere Controls in einer Flex-Row stehen, wächst das Suchfeld mit `flex:1`
- Die Sortierkontrolle (`Segmented`) behält ihren natürlichen Inhalt-Platz; der Rest geht ans Suchfeld

## Root Cause
```html
<!-- IST: fixes 380px -->
<div style="position:relative;flex:0 0 380px">

<!-- SOLL: wächst auf verfügbaren Rest -->
<div style="position:relative;flex:1">
```

## Dependencies
- Upstream: keine — rein CSS
- Downstream: keine — keine anderen Komponenten referenzieren diesen Block

## Existing Specs
- `docs/specs/modules/issue_388_archiv_atomic.md` — Archiv-Atomic-Migration (implementiert, Issue #388 geschlossen)

## Risks & Considerations
- Trivialer CSS-Einzeiler, kein Logik-Risiko
- JSX-Design-Vorlage hat ebenfalls `380px` — Audit M-08 hat das als Bug klassifiziert, also SOLL-Vorlage hier ignorieren
- Kein LoC-Budget-Problem (< 5 LoC Änderung)
