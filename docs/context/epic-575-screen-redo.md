# Context: Epic #575 — Design-Fidelity Redo (alle Screens 1:1)

## Request Summary

Alle 13 Sub-Issues von #575 wurden fälschlicherweise geschlossen, obwohl die Svelte-Screens
gegenüber den JSX-Vorgaben sichtbar gedriftet sind. Der Pilot-Diff von #603 zeigte 51,5 % Differenz
beim Compare-Screen (Schwelle: 10 %). Aufgabe: Sub-Issues wieder öffnen, jeden Screen 1:1 aus
dem JSX übersetzen, mit dem Pixel-Diff-Tool verifizieren und erst dann schließen.

## Drift-Ursachen (aus #603 Issue-Body)

1. **JSX als Skizze gelesen** — Inline-Styles (`style={{ padding: "22px 26px" }}`) konzeptionell
   übersetzt statt zeichengenau kopiert
2. **Fehlende Backend-Felder** — JSX-Mock-Daten haben `sub.region`, `sub.profileLabel`,
   `sub.lastSent`; fehlen im TypeScript-Typ → UI-Elemente weggelassen
3. **Re-Architektur während Übernahme** — Inline-Styles in Tailwind/CSS-Klassen übersetzt,
   Genauigkeit geht verloren
4. **Erfundene Conditional-States** — Loading-States, Empty-States, Fallbacks eingebaut,
   die die eigentliche Variante verdrängten
5. **Vorhandene Komponenten als „fertig" wiederverwendet** ohne gegen aktuelles JSX zu diffen

## Gate (gebaut in #603)

- `.claude/hooks/design_fidelity_diff.py --screen <id>` — Playwright-Screenshot + Pixel-Diff
- Exit 0 = diff < 10 % (PASS), Exit 1 = Fail
- `.claude/hooks/pre_issue_close_design_gate.py` — blockt `gh issue close` ohne diff-pass-Artefakt
- Artefakte: `docs/artifacts/<workflow>/design-diff-<screen>.json` + Diff-PNG

## Sub-Issues und Zuordnung

| Issue | Screen | JSX-Quelle | SOLL-Screenshots | Svelte-Datei |
|-------|--------|-----------|-----------------|--------------|
| #576 [A] | tokens.css Sync | `tokens.css` | — | `frontend/src/app.css` |
| #577 [B] | Atoms | `atoms.jsx` | — | `frontend/src/lib/components/atoms/` |
| #578 [C] | Molecules+Organisms | `molecules.jsx`, `organisms.jsx` | — | `frontend/src/lib/components/molecules/`, `organisms/` |
| #579 [D] | Home | `screen-home.jsx` | `D-home-*.png` | `frontend/src/routes/+page.svelte` |
| #580 [E] | Trips-Liste | `screen-trips.jsx` | `E-trips-list-variant.png` | `frontend/src/routes/trips/+page.svelte` |
| #581 [F] | Trip-Detail | `screen-trip-detail.jsx` | `F-trip-detail-*.png` | `frontend/src/routes/trips/[id]/+page.svelte` |
| #582 [G] | Compare | `screen-compare-list.jsx`, `screen-compare-detail.jsx` | `G-compare-*.png` | `frontend/src/routes/compare/+page.svelte`, `compare/[id]/+page.svelte` |
| #583 [H] | Archiv | `screen-archive.jsx` | `H-archive.png` | `frontend/src/routes/archiv/+page.svelte` |
| #584 [I] | Wizard | `screen-trip-wizard.jsx` | `I-wizard-step*.png` | `frontend/src/routes/trips/new/+page.svelte` |
| #585 [J] | Waypoint-Editor | `screen-waypoint-editor.jsx` | `J-waypoint-editor-*.png` | `frontend/src/routes/trips/[id]/edit/+page.svelte` |
| #586 [K] | Alert-Config | `screen-alert-config.jsx` | `K-alert-config-list.png` | Trip-Detail Alerts-Tab |
| #587 [L] | Metrics-Editor | `screen-metrics-editor.jsx` | `L-metrics-editor-*.png` | Trip-Detail Metriken-Tab |
| #588 [M] | Location-New | `screen-location-new.jsx` | `M-location-new.png` | Modal-Komponente |

## SCREEN_URL_MAP (aktuell in diff tool — unvollständig)

Vorhanden: G-compare-uebersicht-kacheln, D-home-*, E-trips-list-variant,
F-trip-detail-overview, G-compare-wizard-step1, H-archive, I-wizard-step1-route

Fehlen noch: F-trip-detail-wetter, F-trip-detail-reports-*, G-compare-detail,
G-compare-edit, J-waypoint-editor-*, K-alert-config-list, L-metrics-editor-*,
M-location-new, I-wizard-step2-5

## Vorgehen (Übernahme-Protokoll, PO-bestätigt)

1. JSX 1:1 lesen — `screen-X.jsx` + `atoms.jsx` + `tokens.css`
2. Inline-Styles als `style:` oder `style=""` 1:1 übernehmen — **kein Tailwind-Übersetzen**
3. Backend-Feld-Pre-Check: Mock-Daten im JSX gegen TypeScript-Typen diffen
4. Keine Re-Architektur während Übernahme
5. Keine erfundenen Conditional-States
6. Diff-Tool: `design_fidelity_diff.py --screen <id>` → muss < 10 % sein
7. Erst bei PASS: `gh issue close` (wird sonst geblockt)

## Reihenfolge

Screens mit direkten SOLL-PNGs und höchster Sichtbarkeit zuerst:
1. #579 Home (priority:high)
2. #580 Trips-Liste (priority:high)
3. #581 Trip-Detail (priority:high)
4. #582 Compare (priority:medium, Pilot-Beweis nötig)
5. #583 Archiv
6. #584 Wizard
7. #585 Waypoint-Editor
8. #586 Alert-Config
9. #587 Metrics-Editor
10. #588 Location-New
11. #578 Molecules+Organisms (abhängig von Screens)
12. #577 Atoms (Basis)
13. #576 Tokens (wahrscheinlich ok)

## Risiken

- **SCREEN_URL_MAP unvollständig** → muss für alle Screens erweitert werden, bevor Diff läuft
- **Staging-Abhängigkeit** → Diff-Tool braucht Login-Session gegen Staging
- **Scope creep** → Kein Refactoring, keine neuen Features während Übernahme
- **Re-Drift-Gefahr** → Nach Diff-Pass keine weiteren unverifizierten Änderungen

## Abhängigkeiten

- `claude-code-handoff/current/jsx/` — Alle JSX-Dateien (Quelle der Wahrheit)
- `claude-code-handoff/current/soll/` — SOLL-PNGs (visuelle Referenz)
- `.claude/validator.env` — Staging-Credentials für Playwright
- `python3 .claude/hooks/design_fidelity_diff.py` — Gate-Tool
