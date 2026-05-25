# Context: issue-371-atoms

## Request Summary
#371 (Teil Epic #368): `frontend/src/lib/components/atoms/` mit 13 Atomen aus `atoms.jsx` aufbauen — kanonische Atom-Schicht, 1:1 an Claude-Design-Sandbox. Bestehende `ui/`-Pendants als Basis/Alias, backward-compatible (C6).

## Schlüssel-Erkenntnis: NICHT 13 Greenfield
9 der 13 Atome existieren bereits als `ui/`-Komponenten. Nur 4 sind neu.

| Atom | Status | Einstufung (vs. atoms.jsx) |
|------|--------|----------------------------|
| Eyebrow | existiert (ui/eyebrow) | klein: `color`-Prop fehlt |
| Pill | existiert (ui/pill) | klein: tone-Namen abweichend (default/success/warning/danger ↔ neutral/good/warn/bad), `ghost` fehlt |
| Btn | existiert (ui/btn) | klein: `quiet`-Variante fehlt (hat dafür mehr Varianten) |
| Dot | existiert (ui/dot) | klein: tone-Default + size-als-Zahl, tone-Liste zu groß |
| WIcon | existiert (ui/wicon, #322) | klein: `kind`-Default, `color`-Token-Default |
| ElevSparkline | existiert (ui/elev-sparkline) | klein: `stroke`/`fill`-Props, Default-Maße |
| Card | existiert (ui/card) | **Compound-Primitive — BLEIBT (Epic #368)** |
| Input | existiert (ui/input) | shadcn-Form, reicher; `leftIcon/error/mono/size` ergänzen |
| TopoBg | existiert (ui/topo) | CSS-Background statt inline-SVG (funktional gleich) |
| **Switch** | **NEU** | aus atoms.jsx (3 sizes × 5 tones, lg≥44px, role=switch) |
| **SectionH** | **NEU** | eyebrow/title/kicker/right |
| **AvatarStack** | **NEU** | users[], überlappende Avatare |
| **KV** | **NEU** | label/value (Legacy, bevorzugt DetailRow) |

## Architektur-Spannung
- **atoms.jsx nutzt React-Inline-Styles.** Das Projekt nutzt etabliert `data-slot` + `app.css`-Tokens (Issues #277/#284/#285/#323/#324) — das ist die GEWOLLTE Svelte-Architektur, kein Defizit.
- **Epic #368 sagt explizit:** „Compound-Primitive bleiben: Dialog/Table/Select/**Card** behalten ihre reichere, barrierefreie Code-Form." → Kein blinder Sandbox-1:1-Neuschrieb von Card/Input.
- **PO-Leitlinie (Memory):** „Bestehendes nicht leichtfertig umbauen, vieles ist schon gut."

## Risiko bei Prop-Angleichung
tone-Umbenennung (Pill: default→neutral, success→good …) bricht ALLE bestehenden Aufrufer, außer mit backward-compat-Mapping. Hoher Aufrufer-/Test-Aufwand vs. niedriger Nutzen (Aufrufer können später bei Screen-Migration umziehen).

## Empfehlung (Tech Lead)
**Bridge-Ansatz (minimal-invasiv):** `atoms/`-Schicht als kanonische Heimat, die bestehende `ui/`-Atome re-exportiert/dünn umhüllt (Sandbox-Prop-Namen via Mapping unterstützt, alte bleiben gültig), Compound-Primitive (Card/Input) in ihrer reicheren Form behält, und die 4 neuen Atome (Switch, SectionH, AvatarStack, KV) neu baut. Tiefere Aufrufer-Migration → opportunistisch bei Screen-Migration (#368 Phase 2). Niedriges Risiko, erfüllt #371-AC, kein Bruch bestehender Routes.

**Alternative (volle Konsolidierung):** Props strikt an Sandbox angleichen + alle Aufrufer migrieren. Sauberere 1:1-Übereinstimmung, aber mittel-hohes Risiko + großer Test-Aufwand an funktionierender UI.
