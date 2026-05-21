# Context: bug-281-290-stagestrip

## Request Summary
Zwei unabhängige Bugs im Cockpit-Bereich: (#290) falscher Hex-Fallback bei `--g-accent` in StageDetailRow; (#281) Stage-Pills in StageStrip wrappen auf mehrere Zeilen statt einzeilig mit Ellipsis zu kürzen.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Z. 230: `var(--g-accent, #3b82f6)` → falscher blauer Fallback |
| `frontend/src/routes/_cockpit/StagePill.svelte` | Rendert Label direkt in Pill ohne Truncation |
| `frontend/src/routes/_cockpit/StageStrip.svelte` | Wrapper mit `overflow-x-auto`, braucht Fade-Mask |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | `inline-flex`-Span ohne `white-space`/`min-width` |
| `frontend/src/app.css` | Z. 309–323: `[data-slot="pill"]` Block — kein `white-space: nowrap` |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Vorhanden, Tones: weather + semantic (kein accent) |

## Existing Patterns
- CSS-Token-Fallbacks ohne Hex per Konvention (Issue #277): `var(--g-token)` ohne Fallback wenn Token in `app.css` definiert
- `--g-accent: #c45a2a` (Burnt Orange) ist korrekt in `:root [data-theme="light"]` definiert, löst sich immer auf
- Dot-Komponente: `data-tone` = weather-Töne + semantic; `data-size` = xs/sm/md
- Aktive Pill nutzt bereits `tone='accent'` → orange Hintergrund, keine Extra-Dot nötig

## Issue #290 — Fix (trivial, 1 Zeile)

```diff
- background: var(--g-accent, #3b82f6);
+ background: var(--g-accent);
```

Einzige Stelle mit falschem Fallback (Rest hat `#c45a2a`-Fallbacks oder keinen).

## Issue #281 — Änderungen

**StagePill.svelte** (Hauptfix):
- Wrapper-`<span>` erhält `class="stage-pill"` + `class:muted` + `class:active` + `title={label}`
- Innerer `<span class="stage-pill__label">` mit `overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100%`
- `max-width: 180px` auf `.stage-pill`
- `.stage-pill.active .stage-pill__label { font-weight: 600; }`

**app.css** (Z. 309–317 Pill-Block):
- `max-width: 100%; min-width: 0; white-space: nowrap;` ergänzen

**StageStrip.svelte** (Fade-Mask):
- Wrapper-`<div class="strip-wrap">` (relative) um bestehenden Strip
- `<div class="strip-fade-right" aria-hidden="true">` — gradient to `--g-paper`

## Dot-Komponente
Kein 'accent' tone in CSS definiert. Da aktive Pill ohnehin orange (accent) ist: **kein Dot** — AC "visually distinct" durch Hintergrundfarbe + bold label erfüllt.

## Dependencies
- Upstream: `Pill.svelte` (gemeinsame Basiskomponente — Änderung an app.css betrifft alle Pill-Nutzer)
- Downstream: Cockpit-Startseite (StageStrip in Home-View), alle Stellen wo `Pill` genutzt wird

## Risks & Considerations
- `white-space: nowrap` im globalen Pill-Block wirkt auf alle Pill-Instanzen → prüfen ob andere Stellen Pills mit bewusstem Zeilenumbruch nutzen (unwahrscheinlich, da Chips/Tags immer einzeilig)
- `max-width: 180px` auf StagePill ist lokal gescopet (nicht im globalen Pill-Block)
- Fade-Mask nutzt `var(--g-paper)` — muss mit dem echten Hintergrund der Strip-Sektion übereinstimmen
