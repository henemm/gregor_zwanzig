<!-- gregor-zwanzig-handoff: stable_id=pro-metric-horizon-and-template-save -->
## Problem

`EditWeatherSection.svelte` (heute) zeigt Metriken nur als On/Off-Checkboxen. Die Spec verlangt mehr:

`docs/specs/ux_redesign_navigation.md`:

> ### Pro-Metrik-Zeithorizont
> Jede Metrik kann einen eigenen Zeithorizont haben:
> ```
> Gewitter:     ✓ heute  ✓ morgen  ✓ übermorgen
> Temperatur:   ✓ heute  ○ morgen  ○ übermorgen
> ```

> Angepasstes Template **im Profil speichern** für Wiederverwendung bei neuen Trips.

Zwei separate Features, die zusammengehören.

## Files

- `src/lib/components/edit/EditWeatherSection.svelte` — pro-Metrik 3 Horizon-Pills hinzufügen
- `src/lib/components/edit/SaveTemplateDialog.svelte` — **neu**
- `src/routes/account/+page.svelte` — Templates-Sektion zum Verwalten gespeicherter Templates

## Datenmodell

Metric-Konfiguration pro Display-Config-Eintrag:

```ts
interface DisplayMetric {
  metric_id: string;
  enabled: boolean;
  use_friendly_format: boolean;
  horizons: { today: boolean; tomorrow: boolean; day_after: boolean };
}
```

User-saved Templates:

```ts
interface UserWeatherTemplate {
  id: string;
  name: string;
  base_template_id: string | null;     // 'alpen-trekking', or null if from scratch
  metrics: DisplayMetric[];
  created_at: string;
}
```

API:
- `GET /api/user/weather-templates`
- `POST /api/user/weather-templates`
- `PATCH /api/user/weather-templates/:id`
- `DELETE /api/user/weather-templates/:id`

## Required UI changes

### 1. Horizon pills per metric row

Zwischen Metric-Label und Roh/Indikator-Toggle drei Tap-Targets:

```svelte
<div class="metric-row">
  <Checkbox bind:checked={metric.enabled}>
    <span>{metric.label}</span>
  </Checkbox>
  <HorizonChip label="heute"      bind:active={metric.horizons.today} />
  <HorizonChip label="morgen"     bind:active={metric.horizons.tomorrow} />
  <HorizonChip label="übermorgen" bind:active={metric.horizons.day_after} />
  {#if metric.hasFormat}
    <Segmented value={metric.use_friendly_format ? 'indikator' : 'roh'} … />
  {/if}
</div>
```

```css
.horizon-chip {
  padding: 3px 9px;
  border-radius: var(--g-radius-pill);
  border: 1px solid var(--g-ink-faint);
  background: transparent;
  font-family: var(--g-font-data); font-size: 9px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--g-ink-muted);
  cursor: pointer;
}
.horizon-chip[aria-pressed="true"] {
  background: var(--g-ink);
  border-color: var(--g-ink);
  color: var(--g-paper);
}
```

### 2. "Im Profil speichern" Button

Am unteren Rand des Wetter-Editors:

```svelte
<div class="weather-actions">
  <Btn variant="outline" onclick={openSaveDialog}>Im Profil speichern</Btn>
</div>
```

Dialog asks for a name, optional description, then POSTs to `/api/user/weather-templates`.

### 3. Template-Dropdown picks from saved + builtin

Im `weather-template-select`:

```svelte
<Select bind:value={selectedTemplate}>
  <optgroup label="Eingebaut">
    <option value="alpen-trekking">Alpen-Trekking (Sommer)</option>
    <option value="kuesten-wandern">Küsten-Wandern</option>
    <option value="skitouren">Skitouren</option>
    <option value="kanu-kajak">Kanu/Kajak</option>
    <option value="wintersport-piste">Wintersport (Piste)</option>
  </optgroup>
  {#if userTemplates.length > 0}
    <optgroup label="Deine Profile">
      {#each userTemplates as t}
        <option value="user:{t.id}">{t.name}</option>
      {/each}
    </optgroup>
  {/if}
</Select>
```

### 4. Account → Templates-Sektion

Auf `/account` neue Sektion „Wetter-Profile":
- Liste deiner gespeicherten Templates
- Pro Template: Name, Anzahl Metriken, „Bearbeiten" + „Löschen"

## Acceptance criteria

- [ ] Jede Metrik-Reihe hat 3 Horizon-Pills (heute/morgen/übermorgen).
- [ ] Pills sind unabhängig vom Checkbox-State togglebar.
- [ ] Im Tour-Wizard Step 3 und im Trip-Edit Wetter-Tab: gleiche Komponente.
- [ ] „Im Profil speichern" Button öffnet Dialog, speichert via API.
- [ ] Template-Select listet Builtin und User-Profile in separaten optgroups.
- [ ] `/account` hat „Wetter-Profile"-Sektion zum Verwalten.

## 📎 Screenshots

**Soll: Pro-Metrik-Horizont im Wizard**

![soll-1D](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1D-wizard-step3-wetter.png)