# Context: issue-372-molecules

## Request Summary
#372 (Epic #368): `frontend/src/lib/components/molecules/` mit 10 Molecules aus `molecules.jsx`. Desktop UND Mobile über `dense`/`last`/`compact`/`size`-Props (C3, keine separaten Mobile-Varianten). Bauen auf #371-Atomen auf.

## Stand: 10/10 NEU (Greenfield)
Keine der 10 existiert als eigenständige `.svelte`. `molecules/` existiert nicht. (StagePill war bisher nur inline in StageStrip-Kontext, #281/#290 — jetzt eigenständig.)

## Atom-Abhängigkeiten (#371, bereits gebaut in atoms/)
- ChannelRow → **Switch**
- BriefingScheduleRow → **Switch**
- BriefingTimelineRow → **Dot** + **ChannelChip** (molecule)
- AlertRow → **WIcon**
- DetailRow → optional WIcon (icon-Prop)
- Field/Stat/StagePill/ThresholdRow → keine harten Atom-Deps

## Props (body-15 §Molecules + molecules.jsx)
- **Field**: label, hint, error, side, dense + Snippet
- **DetailRow**: label, value, sub, icon, right, mono, divider dashed|solid|none
- **StagePill**: stage {code, risk}, state active|done|future|muted; `data-state`
- **ChannelRow**: kind, target, active, sub, onToggle, dense, last (ohne dense = Card-Layout `--g-card-alt`; mit dense = Reihe + bottom-border `--g-rule-soft`)
- **ChannelChip**: kind, active, compact (compact = 24×24-Tile)
- **BriefingTimelineRow**: report {when,kind,etappe,channels,status}, dense (dense = 24×24 ChannelChip compact, kein Suffix)
- **BriefingScheduleRow**: label, sub, time, enabled, onToggle, last
- **ThresholdRow**: label, value, divider, last, editable, onEdit
- **Stat**: label, value, sub, unit, tone default|accent, layout stack|inline, size sm|md|lg, mono (leerer value → Em-Dash `—`)
- **AlertRow**: alert {kind,when,msg,channel?}, variant icon|dot|plain, divider, last

## Konvertierungs-Regeln (body-15)
- Callback-Props (onToggle/onEdit) → Svelte-Events/`bind:`.
- Element-Props (icon/right) → Snippets.
- `dense`/`last`/`compact`/`size` steuern Desktop+Mobile (keine M-Varianten).

## Edge Cases
- Stat value=""/null → Em-Dash `—`.
- ChannelRow onToggle=undefined aber active → Switch read-only.
- Unbekannte state/variant/tone/divider → Default-Fallback.

## Risiken
- **Kontrast-Schutznetz aktiv:** Parallel-Session hat `contrast-audit.test.ts` (#377) eingeführt — Molecules müssen WCAG-AA-Text-Kontrast wahren (echter Text ≥ 4.5:1, `--g-ink-4` nur Placeholder/Disabled). Beim Rebase greift der Test.
- Token-Disziplin C1 (var(--g-*), kein verbotener Inline-Hex).
- SSR-fest. Reines Frontend, kein Backend. Bibliothek inert bis Showcase #374.
- Atom-Importe aus `$lib/components/atoms` müssen korrekt sein (#371 ist auf main).
