---
entity_id: issue_376_channel_preview_select
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [frontend, bug, "#376", "#278", "#272", "#365"]
---

# Issue #376 — ChannelPreviewBlock auf Select.svelte migrieren

## Approval

- [ ] Approved

## Purpose

Beseitigt eine #278-Regel-Verletzung: das mit #365 eingeführte native `<select>` für die
mobile Kanal-Auswahl in `ChannelPreviewBlock.svelte` wird durch die kanonische
Projekt-Komponente `Select.svelte` ersetzt. Dadurch wird `test_ac4_no_native_selects_outside_component`
grün und das Pre-Commit-Gate blockiert nicht länger jeden sauberen Backend-Commit.

## Source

- **File:** `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte`
- **Identifier:** mobile Kanal-Dropdown (`<select bind:value={mobileChannel}>`, Z. 75) + CSS-Block `.ch-select select` (Z. 138–146)

> Schicht: **Frontend / User-UI** (SvelteKit, produktive Oberfläche auf gregor20.henemm.com).
> Keine Go-API-, keine Python-Backend-, keine Daten-Schema-Berührung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/select/Select.svelte` | UI-Komponente | Ziel-Komponente (gebrandetes `<select>` mit appearance:none + Chevron, `$bindable()` value, restProps-Forwarding) |
| `frontend/src/lib/components/ui/select/index.ts` | Barrel | Import-Quelle `$lib/components/ui/select` |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | UI-Komponente | Kind, vom gewählten `mobileChannel` gesteuert — Render-Verhalten muss identisch bleiben |
| `frontend/src/app.css` | Stylesheet | Globaler #272-iOS-Guard (Z. 457–462) + `--g-text-sm: 13px` (Z. 110) |

## Implementation Details

```svelte
<!-- 1. Import im <script>-Block ergänzen -->
import { Select } from '$lib/components/ui/select';

<!-- 2. Natives <select> (Z. 75) durch <Select> ersetzen; Optionen unverändert -->
<Select bind:value={mobileChannel} data-testid="channel-preview-mobile-select">
  {#each CHANNELS as c}
    <option value={c.id}>{c.label}</option>
  {/each}
</Select>

<!-- 3. Toten CSS-Block `.ch-select select { … }` (Z. 138–146) entfernen -->

<!-- 4. Scoped iOS-Zoom-Guard (#272) ergänzen — Muster wie SavePresetDialog.svelte:337-341 -->
@media (max-width: 767px) {
  .ch-select :global(.gz-select select) {
    font-size: 16px; /* iOS-Zoom-Guard (#272) — überschreibt --g-text-sm aus Select.svelte */
  }
}
```

Spezifität: `.ch-select :global(.gz-select select)` = `(0,2,1)` schlägt Select.sveltes
`.gz-select select` `(0,1,1)` → 16px gewinnt auf iOS-Viewports.

## Expected Behavior

- **Input:** Keine API-/Daten-Änderung. Komponente erhält dieselben Props (`primary`, `secondary`, `metricById`, `shortById`).
- **Output:** Mobiles Dropdown rendert als gebrandetes `Select` (eigener Chevron, Design-Token-Styling) statt System-blau; 4 Optionen (email/telegram/signal/sms), Default `'signal'`.
- **Side effects:** Keine. `rg '<select\b'` über `frontend/src` liefert danach Treffer ausschließlich in `Select.svelte`.

## Acceptance Criteria

- **AC-1:** Given das Projekt-Repository / When `rg '<select\b' frontend/src --glob='*.svelte' -l` ausgeführt wird / Then ist `ChannelPreviewBlock.svelte` **nicht** mehr in den Treffern, sodass `test_ac4_no_native_selects_outside_component` grün ist (einziger Treffer: `Select.svelte`).
  - Test: (populated after /tdd-red)

- **AC-2:** Given das migrierte mobile Dropdown / When ein Nutzer auf einem Viewport ≤899px einen anderen Kanal auswählt / Then bleibt `mobileChannel` via `bind:value` korrekt gebunden und `ChannelPreviewCard` zeigt die gewählte Kanal-Karte (Default `'signal'`, Optionen email/telegram/signal/sms) — Verhalten identisch zum nativen `<select>`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Attribut `data-testid="channel-preview-mobile-select"` / When der DOM gerendert wird / Then landet es über das restProps-Forwarding von `Select.svelte` auf dem nativen `<select>`, sodass der bestehende Playwright-/Test-Selektor unverändert funktioniert.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein iOS-Viewport mit `max-width: 767px` / When das mobile Kanal-Dropdown fokussiert wird / Then beträgt die effektive `font-size` des nativen `<select>` exakt `16px` (scoped Override schlägt Select.sveltes `--g-text-sm`=13px) → kein iOS-Auto-Zoom, #272-Schutz bleibt für dieses Dropdown erhalten.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein sauberer `origin/main`-Arbeitsbaum / When das Pre-Commit-Gate die volle `uv run pytest`-Suite fährt / Then ist `tests/tdd/test_issue_278_form_controls.py` vollständig grün (insb. `test_ac4`) und ein Backend-Commit wird nicht länger durch diesen Test blockiert.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Mobile-Breakpoint-Lücke (768–899px):** Das Dropdown ist ab `≤899px` sichtbar, der iOS-Guard greift (wie der globale app.css-Guard und das #272-Präzedenz-Muster) nur `≤767px`. Im Bereich 768–899px (Tablet) rendert das `<select>` mit 13px — dort ist iOS-Auto-Zoom praktisch irrelevant. Bewusst konsistent mit dem etablierten #272-Muster gewählt.
- **Nebenbefund (nicht in Scope):** `Select.svelte` rendert app-weit mit `--g-text-sm`=13px und überschreibt den globalen #272-Guard für **alle** Dropdowns. Eine zentrale Konsolidierung (16px-Mobile-Guard direkt in `Select.svelte`) hätte größeren Blast-Radius und gehört in einen separaten Issue.

## Changelog

- 2026-05-25: Initial spec created (#376)
