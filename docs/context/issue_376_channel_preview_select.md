# Context: Issue #376 — ChannelPreviewBlock auf Select.svelte migrieren

## Request Summary

Das native `<select>` für die mobile Kanal-Auswahl in `ChannelPreviewBlock.svelte`
(eingeführt mit #365) verletzt die #278-Regel „native `<select>` nur in Select.svelte".
Dadurch ist `test_ac4_no_native_selects_outside_component` rot, was auf `origin/main`
**jeden sauberen Backend-Commit über das Pre-Commit-Gate blockiert**. Lösung: das native
`<select>` durch die Projekt-Komponente `Select.svelte` ersetzen.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | **Zu ändern.** Enthält das native `<select>` (Z. 75) + zugehöriges CSS (`.ch-select select`, Z. 138–146). |
| `frontend/src/lib/components/ui/select/Select.svelte` | Ziel-Komponente. Rendert `<span.gz-select><select appearance:none {...rest}>{children}</select><svg.chevron/></span>`. |
| `frontend/src/lib/components/ui/select/index.ts` | Export `{ Select }` — Import-Quelle: `$lib/components/ui/select`. |
| `tests/tdd/test_issue_278_form_controls.py` | `test_ac4` (Z. 259–276) ist der rote Test (rg `<select\b` über `frontend/src`, Treffer nur in `Select.svelte` erlaubt). |
| `docs/specs/modules/issue_278_form_controls.md` | Spec der gebrandeten Form-Controls (Regel-Grundlage). |
| `frontend/src/app.css` | Globaler iOS-Zoom-Guard #272 (Z. 457–462) + `--g-text-sm: 13px` (Z. 110). |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Kind-Komponente, vom `<select>` gesteuert (`mobileChannel`). **Kein** eigenes `<select>`, nicht betroffen. |

## Existing Patterns

Migrations-Muster aus #278-migrierten Komponenten (z. B. `PresetHeader.svelte`,
`alerts-tab/AlertMetricRow.svelte`):

```svelte
import { Select } from '$lib/components/ui/select';

<Select class="..." data-testid="..." bind:value={...}>
  {#each OPTS as o}
    <option value={o.id}>{o.label}</option>
  {/each}
</Select>
```

- `bind:value` funktioniert (Select.svelte nutzt `$bindable()`).
- `data-testid` + restliche Attribute landen via `{...restProps}` auf dem nativen `<select>`
  (Playwright-Kompatibilität bleibt → `channel-preview-mobile-select` muss erhalten bleiben).
- `class`-Prop landet auf dem `.gz-select`-Wrapper-`<span>`.
- Konkrete Migration: `<select bind:value={mobileChannel} data-testid="…">…</select>`
  → `<Select bind:value={mobileChannel} data-testid="…">…</Select>`; `{#each}`/`<option>`
  bleiben unverändert. Lokaler CSS-Block `.ch-select select { … }` wird überflüssig.

## Dependencies

- **Upstream (was wir nutzen):** `Select.svelte` (Design-Token-CSS, Chevron, appearance:none).
- **Downstream (was uns nutzt):** `ChannelPreviewCard.svelte` über die `mobileChannel`-Bindung.
  Render-Verhalten muss identisch bleiben (Default `'signal'`, 4 Optionen email/telegram/signal/sms).

## Existing Specs

- `docs/specs/modules/issue_278_form_controls.md` — Form-Control-Regel (Quelle des Tests).
- #365-Design-Referenz: `docs/design/epic_331_output_layout/screen-metrics-editor.jsx` (Z. 555–650).

## Risks & Considerations

1. **iOS-Auto-Zoom (#272) — Hauptrisiko.** Der globale Guard (`app.css:458`, `select { font-size:16px }`
   bei `≤767px`) hat Element-Spezifität `(0,0,1)`. `Select.svelte` setzt `.gz-select select
   { font-size: var(--g-text-sm) }` = **13px** mit Spezifität `(0,1,1)` → überschreibt den Guard.
   Der bisherige lokale Guard (`font-size:16px` in `.ch-select select`) ginge bei naiver Migration
   verloren → mobiles Kanal-Dropdown könnte beim Fokus wieder zoomen. Klärung in Analyse/Spec:
   scoped Override (Präzedenz: #272 nutzte scoped Override in SavePresetDialog) vs. globalen Guard
   spezifischer machen vs. bewusst akzeptieren.

2. **Parallel-Session-Koordination.** Laut Issue-Hinweis + Memory wird `ChannelPreviewBlock.svelte`
   gleichzeitig in einer parallelen Sitzung bearbeitet (uncommittete Änderungen im Haupt-Tree).
   Diese Sitzung arbeitet isoliert im Worktree `worktree-peaceful-questing-globe` (Branch ab `f4cdb93`,
   committeter Stand = mit nativem `<select>`). Beim Ausliefern Merge-Kollision auf dieser Datei
   möglich → vor Commit/Deploy Abgleich mit der parallelen Arbeit.

3. **`data-testid` erhalten.** `channel-preview-mobile-select` muss auf dem nativen `<select>`
   bleiben (Select.svelte forwardet restProps → erfüllt, aber explizit verifizieren).

4. **Mobile-Breakpoint-Lücke (768–899px).** ChannelPreviewBlock zeigt das Dropdown ab `≤899px`,
   der globale iOS-Guard greift nur `≤767px`. Schon im Status quo besteht im Bereich 768–899px kein
   16px-Schutz aus app.css; relevant nur falls Punkt 1 über den globalen Guard gelöst werden soll.

5. **Reiner Frontend-Fix.** Keine Backend-/Daten-Schema-Berührung. E2E-Verifikation ist
   frontend-only (visuell), keine Mail.

---

## Analysis & Decision (Phase 2)

### Typ
**Bug / Regression** — kein mysteriöser Bug, sondern eine bekannte #278-Regel-Verletzung,
eingeführt durch #365. Root-Cause aus Phase 1 eindeutig; kein bug-intake-Agent nötig
(Over-Processing bei trivialem Komponententausch vermieden).

### Lösungsansatz (eine Empfehlung)

`<select>` → `<Select>` migrieren **und** den #272-iOS-Zoom-Schutz für dieses Dropdown
per scoped Override erhalten:

1. Import ergänzen: `import { Select } from '$lib/components/ui/select';`
2. `<select bind:value={mobileChannel} data-testid="channel-preview-mobile-select"> … </select>`
   → `<Select bind:value={mobileChannel} data-testid="channel-preview-mobile-select"> … </Select>`
   (`{#each}` + `<option>` unverändert).
3. Toten CSS-Block `.ch-select select { … }` (Z. 138–146) entfernen.
4. Scoped iOS-Guard ergänzen (Muster wie `SavePresetDialog.svelte:337-341`):
   ```css
   @media (max-width: 767px) {
     .ch-select :global(.gz-select select) {
       font-size: 16px; /* iOS-Zoom-Guard (#272) — überschreibt --g-text-sm aus Select.svelte */
     }
   }
   ```
   Spezifität `(0,2,1)` schlägt Select.sveltes `.gz-select select` `(0,1,1)` → 16px gewinnt auf iOS.

**Begründung:** Das native Element war der Auslöser von #278-test_ac4 (rot). Select.svelte ist
die kanonische #278-Komponente. Der scoped Override verhindert, dass die naive Migration den
bereits gefixten #272-Bug für dieses Dropdown reaktiviert (Select.svelte rendert mit
`--g-text-sm`=13px < 16px). Kein User-Entscheid nötig: best-practice-Erhalt einer zuvor
gefixten Verhaltensweise via etabliertem Projektmuster.

### Scope
- **Dateien:** 1 (`ChannelPreviewBlock.svelte`). ✅ unter 4–5.
- **LoC:** ~ +8 / −9 (netto < 5). ✅ weit unter 250.
- **Backend:** keine Berührung. E2E frontend-only (visuell), keine Mail.

### Nebenbefund (NICHT Teil von #376 — möglicher Folge-Issue)
Select.svelte setzt app-weit `.gz-select select { font-size: var(--g-text-sm) }` = 13px mit
Spezifität `(0,1,1)`, die den globalen #272-Guard `select{16px}` `(0,0,1)` überschreibt.
**Alle** Select.svelte-Instanzen rendern damit auf iOS < 16px → latente #272-Regression
app-weit (durch #278 eingeführt). Sauberste Konsolidierung wäre ein 16px-Mobile-Guard
direkt in Select.svelte (fixt alle Dropdowns zentral) — größerer Blast-Radius, daher
separater Issue. Für #376 bleibt der Scope eng (nur ChannelPreviewBlock).

### Test-Auswirkung
- `test_ac4_no_native_selects_outside_component` (#278): rot → grün (ChannelPreviewBlock ist
  laut `rg '<select\b'` die **einzige** verbleibende Datei).
- `test_key_files_import_select` (#278): unberührt (ChannelPreviewBlock nicht in der Liste).
