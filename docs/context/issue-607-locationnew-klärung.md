# Context: Issue #607 — LocationNew Design-Klärung

## Request Summary
Issue #607 ist eine Design-Klärungsfrage: Welche von zwei fundamental verschiedenen LocationNew-Modal-Varianten ist die Wahrheit? Die Entscheidung blockt Issue #588 (Design-Fidelity 1:1).

## Die zwei Varianten

### Variante A — JSX (aktuell live)
- Datei: `claude-code-handoff/current/jsx/screen-location-new.jsx`
- Implementation: `frontend/src/lib/components/compare/LocationNewModal.svelte`
- Primäre Eingabe: Smart-Import (URL/Koordinaten-Eingabe)
- **3 Sektionen:** (1) Verortung · Smart-Import, (2) Benennung, (3) Meteorologische Brille (Aktivitätsprofil)
- Hat BEREITS: Gruppe, Aktivitätsprofil, Mini-Map

### Variante B — SOLL-PNG
- Datei: `claude-code-handoff/current/soll/M-location-new.png`
- Konzept: Karte links (interaktiv, Pin-Click) + Formular rechts
- Zusätzliche Features: **Wetter-Template-Feld** (fehlt in Variante A)
- Kein Smart-Import

## Related Files
| Datei | Relevanz |
|-------|----------|
| `claude-code-handoff/current/jsx/screen-location-new.jsx` | Bindende JSX-Quelle (3 Sektionen) |
| `frontend/src/lib/components/compare/LocationNewModal.svelte` | Live-Implementierung (248 Zeilen) |
| `docs/design-requests/issue_588_location_new_variante_klaerung.md` | Design-Request-Beschreibung |
| `claude-code-handoff/current/soll/M-location-new.png` | SOLL-Variante B |

## Pixel-Diff Befund
- Diff zwischen IST (Variante A) und SOLL-PNG (Variante B): **62,95 %**
- Kein Implementierungs-Drift — Quell-Konflikt zweier fundamental verschiedener Designs

## Wichtige Regel
Memory `feedback_jsx_always_truth.md`: **"JSX ist IMMER die Wahrheit"** — bei JSX vs SOLL-Konflikt gewinnt JSX automatisch.

## Feature-Delta
Das einzige echte Feature-Gap in Variante A: **Wetter-Template-Feld** (Variante B hat es, Variante A nicht). Dies wäre ein separates Feature-Issue.

## Dependencies
- Issue #588 (Design-Fidelity LocationNew) wartet auf diese Klärung
- `LocationNewModal.svelte` ist die aktive Live-Implementierung
