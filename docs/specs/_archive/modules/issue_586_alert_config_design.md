---
entity_id: issue_586_alert_config_design
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
issue: 586
tags: [alerts-tab, frontend, design-fidelity, jsx, modecard, alertmetrictable, alertmetricrow, cooldown, quiet-hours, preview, tokens, svelte, issue-586]
---

# Issue #586 — Alert-Config Design-Fidelity 1:1 nach screen-alert-config.jsx

## Approval

- [ ] Approved

## Purpose

Der Desktop-Alerts-Tab weicht in Layout und visueller Struktur erheblich von der verbindlichen JSX-Vorlage (`screen-alert-config.jsx`) ab: Das ModeCard-Grid ist auf Desktop komplett ausgeblendet, der Seiten-Header existiert nicht, AlertMetricTable hat weder Card-Wrapper noch Header-Row, und die Cooldown-/QuietHours-/Preview-Sektionen folgen nicht der JSX-Typografie und -Struktur. Dieses Issue bringt alle sechs betroffenen Komponenten sowie den fehlenden Design-Token `--g-info-deep` pixelgenau auf den JSX-Stand — ausschließlich visuelle Anpassungen, keine Änderungen an der Geschäftslogik.

## Source

- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte`
- **MODIFY:** `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte`
- **MODIFY:** `frontend/src/app.css`

> **Schicht-Hinweis:** Alle Änderungen liegen in `frontend/src/` (SvelteKit-UI). Go-API und Python-Backend bleiben unberührt.

## Estimated Scope

- **LoC:** ~180
- **Files:** 7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `screen-alert-config.jsx` | Design-Quelle (`claude-code-handoff/current/jsx/`) | Verbindliche JSX-Vorlage für alle Layout- und Styling-Entscheidungen |
| `Card` | Atom (`$lib/components/atoms`) | Wrapper mit `padding={0}` für AlertMetricTable — bereits verfügbar |
| `SectionH` | Atom (`$lib/components/atoms`) | Abschnitts-Header mit `eyebrow` + `title` — bereits verfügbar |
| `Eyebrow` | Atom (`$lib/components/atoms`) | Kleingedruckte Beschriftung in Header-Row und Cards — bereits verfügbar |
| `alertMetricTable.ts` | TS-Modul (`alerts-tab/`) | `deriveAlertMode`, `applyModeToRowState` — wird NICHT geändert |
| `alertRuleDefaults.ts` | TS-Modul (`alert-rules-editor/`) | `DELTA_ONLY_METRICS` — wird NICHT geändert |
| `alertMetricTable.test.ts` | Test-Datei (`alerts-tab/`) | Bestehende Unit-Tests — dürfen nicht brechen |
| `app.css` | Design-Token-Datei | Neuer Token `--g-info-deep: #1a4a7a` (dunklere Variante zu `--g-info: #2a6cb3`) |

## Implementation Details

### 1. `app.css` — Token `--g-info-deep` ergänzen

Im Token-Block direkt nach `--g-info: #2a6cb3` eintragen:

```css
--g-info-deep: #1a4a7a;
```

Begründung: JSX `AlertChangeRow` nutzt `var(--g-info-deep)` für negative Delta-Werte (blau, analog zu `--g-accent-deep` für positive Werte). Der Token fehlt aktuell.

### 2. `AlertsTab.svelte` — Desktop-Header + ModeCard-Grid immer sichtbar

**Problem:** `.mobile-header`, `.mode-picker` und `.section-heading` haben `display: none` als Default; nur im `@media (max-width: 899px)`-Block werden sie eingeblendet. Auf Desktop bleibt damit der gesamte Auslöse-Modus-Bereich unsichtbar.

**Lösung:**

a) Desktop-Header-Block hinzufügen (immer sichtbar, entspricht JSX lines 48–54):

```svelte
<div class="desktop-header">
  <Eyebrow>Alert-Briefings · Sofort-Benachrichtigung</Eyebrow>
  <h1 class="desktop-h1">Wann soll ein Alert ausgelöst werden?</h1>
  <p class="desktop-subtext">
    Alerts kommen zwischen Morning- und Abend-Briefing. Du wählst, ob sie auf
    <strong>Änderungen seit letztem Briefing</strong> (Δ) reagieren, auf
    <strong>absolute Schwellwerte</strong>, oder beides.
  </p>
</div>
```

b) `SectionH` vor dem ModeCard-Grid einfügen:
```svelte
<SectionH eyebrow="Auslöse-Modus" title="Was triggert einen Alert?" />
```

c) ModeCard-Grid auf Desktop als 3-Spalten-Grid sichtbar machen. Das bestehende `.mode-picker` mit `display: none` entfernen; stattdessen immer sichtbar, responsive:

```css
/* Desktop: 3-Spalten-Grid */
.mode-picker {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}

/* ModeCard vollständige Stile nach JSX */
.mode-card {
  padding: 18px;
  border-radius: 4px;
  cursor: pointer;
  background: transparent;
  border: 1px solid var(--g-rule);
  transition: all 120ms;
  text-align: left;
  font: inherit;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 0;
}
.mode-card.active {
  background: var(--g-card);
  border: 2px solid var(--g-accent);
}
.mode-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.mode-radio-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--g-rule);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.mode-card.active .mode-radio-dot {
  border-color: var(--g-accent);
}
.mode-radio-inner {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--g-accent);
}
.mode-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--g-ink);
}
.mode-card.active .mode-title {
  color: var(--g-accent-deep);
}
.mode-desc {
  font-size: 13px;
  color: var(--g-ink-2);
  line-height: 1.5;
  margin-bottom: 10px;
}
.mode-example {
  font-size: 11px;
  color: var(--g-ink-3);
  padding-top: 10px;
  border-top: 1px solid var(--g-rule-soft);
  line-height: 1.5;
  font-family: var(--g-font-mono);
}
```

d) ModeCard-Template-Struktur mit `mode-header-row` und Radio-Dot anpassen:

```svelte
<button class="mode-card" class:active={selectedMode === m.id} ...>
  <div class="mode-header-row">
    <Eyebrow>{m.eyebrow}</Eyebrow>
    <span class="mode-radio-dot">
      {#if selectedMode === m.id}<span class="mode-radio-inner"></span>{/if}
    </span>
  </div>
  <span class="mode-title">{m.title}</span>
  <span class="mode-desc">{m.desc}</span>
  <span class="mode-example">{m.example}</span>
</button>
```

e) `SectionH` vor `AlertMetricTable` einfügen:
```svelte
<SectionH eyebrow="Schwellwerte" title="Pro Metrik festlegen" />
```

f) Bestehende Mobile-only-Blöcke (`mobile-header`, alte `mode-picker`-CSS, `section-heading`) entfernen. Der neue Desktop-Header ersetzt `.mobile-header`. Die `.mobile-footer` und Mobile-Footer-CSS (Issue #414) bleiben unverändert erhalten.

### 3. `AlertMetricTable.svelte` — Card-Wrapper + Header-Row

**Problem:** Kein Card-Wrapper, kein visueller Header mit Spaltenbezeichnungen.

**Lösung:**

a) Atoms-Import ergänzen:
```svelte
import { Card, Eyebrow } from '$lib/components/atoms';
```

b) Template umbauen: `alert-metric-table`-div in `<Card padding={0}>` einbetten, Header-Row davor einfügen:

```svelte
<Card padding={0}>
  <div class="table-header">
    <div></div>
    <Eyebrow>Metrik</Eyebrow>
    <Eyebrow>Δ-Änderung (seit letztem Briefing)</Eyebrow>
    <Eyebrow>Absoluter Schwellwert</Eyebrow>
  </div>
  <div class="alert-metric-table" data-testid="alert-metric-table">
    {#each ALL_ALERT_METRICS as m (m)}
      <AlertMetricRow metric={m} bind:state={rowState[m]} />
    {/each}
  </div>
</Card>
```

c) Header-Row CSS:
```css
.table-header {
  display: grid;
  grid-template-columns: 32px 200px 1fr 1fr;
  gap: 0;
  padding: 12px 20px;
  background: var(--g-card-alt);
  border-bottom: 1px solid var(--g-rule);
  align-items: center;
}
```

d) Bestehende `.alert-metric-table`-Styles (border, border-radius, background) entfernen — die liegen jetzt in der Card.

### 4. `AlertMetricRow.svelte` — 4-Spalten-Grid nach JSX

**Problem:** Aktuell 8-Spalten-Grid (`11rem 4.5rem 6rem 3rem 4.5rem 6rem 3rem 1fr`) — stark abweichend von JSX 4 Spalten (`32px 200px 1fr 1fr`).

**Lösung:**

a) Grid auf 4 Spalten umstellen:
```css
.metric-row {
  display: grid;
  grid-template-columns: 32px 200px 1fr 1fr;
  gap: 0;
  padding: 14px 20px;
  border-bottom: 1px solid var(--g-rule-soft);
  align-items: center;
}
.metric-row.disabled {
  opacity: 0.45;
}
```

b) Spalte 1 — Zeilen-Toggle (enabled/disabled für die gesamte Zeile): Neuer `rowEnabled`-State aus `state.absEnabled || state.deltaEnabled`. Toggle-Klick setzt beide `absEnabled` und `deltaEnabled` (unter Beachtung von `DELTA_ONLY_METRICS`):

```svelte
let rowEnabled = $derived(state.absEnabled || state.deltaEnabled);
function toggleRow() {
  const enable = !rowEnabled;
  if (enable) {
    state.deltaEnabled = true;
    if (!isDeltaOnly) state.absEnabled = true;
  } else {
    state.absEnabled = false;
    state.deltaEnabled = false;
  }
}
```

Switch-Span nach JSX-Muster:
```svelte
<label style="cursor: pointer">
  <span
    class="row-switch"
    class:on={rowEnabled}
    onclick={toggleRow}
    role="switch"
    aria-checked={rowEnabled}
    tabindex="0"
  >
    <span class="row-switch-knob"></span>
  </span>
</label>
```

```css
.row-switch {
  display: inline-block;
  width: 30px;
  height: 16px;
  border-radius: 9px;
  background: var(--g-rule);
  position: relative;
  transition: background 120ms;
}
.row-switch.on { background: var(--g-accent); }
.row-switch-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  transition: left 120ms;
}
.row-switch.on .row-switch-knob { left: 16px; }
```

c) Spalte 2 — Label + Unit:
```svelte
<div>
  <div class="metric-label">{info?.label_de ?? metric}</div>
  <div class="metric-unit mono">{info?.unit ?? ''}</div>
</div>
```

```css
.metric-label { font-size: 13px; font-weight: 600; }
.metric-unit { font-size: 10px; color: var(--g-ink-4); font-family: var(--g-font-mono); }
```

d) Spalte 3 — Delta-Input (wenn `state.deltaEnabled`) oder "— deaktiviert —":
```svelte
<div>
  {#if state.deltaEnabled}
    <div class="threshold-row">
      <span class="mono threshold-label">Δ ≥</span>
      <input type="number" class="threshold-input" bind:value={state.deltaThreshold} ... />
      <span class="mono threshold-unit">{info?.unit ?? ''}</span>
    </div>
  {:else}
    <span class="mono disabled-label">— deaktiviert —</span>
  {/if}
</div>
```

e) Spalte 4 — Abs-Input (wenn `state.absEnabled && !isDeltaOnly`) oder "— deaktiviert —":
```svelte
<div>
  {#if state.absEnabled && !isDeltaOnly}
    <div class="threshold-row">
      <span class="mono threshold-label">{info?.absLabel ?? 'über'}</span>
      <input type="number" class="threshold-input" bind:value={state.absThreshold} ... />
      <span class="mono threshold-unit">{info?.unit ?? ''}</span>
    </div>
  {:else}
    <span class="mono disabled-label">— deaktiviert —</span>
  {/if}
</div>
```

f) **Severity-Select beibehalten** — als 5. Spalte (funktionale Erweiterung über JSX hinaus, Grid anpassen auf `32px 200px 1fr 1fr auto`).

```css
.threshold-input {
  width: 64px;
  padding: 6px 8px;
  border: 1px solid var(--g-rule);
  border-radius: 3px;
  font-size: 13px;
  font-family: var(--g-font-mono);
  text-align: right;
}
.threshold-row { display: flex; align-items: baseline; gap: 6px; }
.threshold-label { font-size: 11px; color: var(--g-ink-3); }
.threshold-unit { font-size: 11px; color: var(--g-ink-3); }
.disabled-label { font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); }
```

### 5. `AlertCooldownCard.svelte` — Eyebrow + JSX-Input-Style

a) Atoms-Import ergänzen: `import { Eyebrow } from '$lib/components/atoms';`

b) `<h4>` durch `<Eyebrow>` ersetzen: `<Eyebrow>Cooldown</Eyebrow>`

c) Hint-Text auf JSX-Wortlaut aktualisieren: "Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten."

d) Input-Style auf JSX-Vorgabe setzen:
```css
.cooldown-input {
  width: 80px;
  padding: 8px 10px;
  border: 1px solid var(--g-rule);
  border-radius: 3px;
  font-size: 14px;
  font-family: var(--g-font-mono);
}
```

### 6. `AlertQuietHoursCard.svelte` — Eyebrow + JSX-Input-Style

a) Atoms-Import ergänzen: `import { Eyebrow } from '$lib/components/atoms';`

b) `<h4>` durch `<Eyebrow>` ersetzen: `<Eyebrow>Stille Stunden</Eyebrow>`

c) Hint-Text auf JSX-Wortlaut aktualisieren: "In diesem Zeitraum keine Alerts senden — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit."

d) Checkbox-Toggle beibehalten (funktionale Erweiterung über JSX hinaus).

e) Time-Input-Style auf JSX-Vorgabe (analog Cooldown-Input):
```css
.time-input {
  width: 80px;
  padding: 8px 10px;
  border: 1px solid var(--g-rule);
  border-radius: 3px;
  font-size: 14px;
  font-family: var(--g-font-mono);
}
```

### 7. `AlertPreviewCard.svelte` — SectionH-Header + Card-Wrapper-Styling

a) Atoms-Import ergänzen: `import { SectionH } from '$lib/components/atoms';`

b) `SectionH` in `AlertsTab.svelte` vor `AlertPreviewCard` einfügen (nicht in der Komponente selbst, da sie eigenständig wiederverwendbar bleiben soll):
```svelte
<SectionH eyebrow="Beispiel-Alert" title="So sieht ein ausgelöster Alert aus" />
<AlertPreviewCard {trip} {alertRules} />
```

c) `AlertPreviewCard.svelte`: `<h4>` entfernen. Card-Container-Style angleichen (border `1px solid var(--g-rule)`, maxWidth 720px, kein box-shadow). iframe-Wrapper beibehalten.

## Expected Behavior

- **Input:** Nutzer öffnet den Alerts-Tab in Trip-Detail auf Desktop (≥900px).
- **Output:**
  - Header mit Eyebrow "Alert-Briefings · Sofort-Benachrichtigung", H1, Subtext-Paragraph sichtbar.
  - SectionH "Auslöse-Modus / Was triggert einen Alert?" darunter.
  - 3-Spalten-ModeCard-Grid sichtbar; aktive Karte hat 2px Accent-Border, Radio-Dot ausgefüllt, Titel in `--g-accent-deep`.
  - SectionH "Schwellwerte / Pro Metrik festlegen" vor der Tabelle.
  - AlertMetricTable in Card-Wrapper; Header-Row mit grauem Hintergrund (`--g-card-alt`) und Eyebrow-Labels.
  - AlertMetricRow: 4 Spalten (Switch | Label+Unit | Delta | Abs) + Severity-Spalte; disabled Zeilen bei Opacity 0.45.
  - AlertCooldownCard und AlertQuietHoursCard: Eyebrow-Titel, JSX-konformer Hint-Text, Mono-Input 80px.
  - AlertPreviewCard: SectionH-Abschnitt davor, kein h4-Doppel-Titel.
- **Side effects:**
  - `--g-info-deep` in app.css verfügbar für alle Komponenten (JSX-AlertChangeRow nutzt ihn für negative Deltas).
  - Bestehende Tests (`alertMetricTable.test.ts`, `alertPreviewHelpers.test.ts`) bleiben grün — keine Änderungen an Logik-Modulen.
  - Mobile-Layout (Issue #414 — fixierter Footer, Mobile-Header, Mobile-Modus-Picker) bleibt erhalten.

## Acceptance Criteria

**AC-1:** Given Desktop-Viewport (≥900px) und Alerts-Tab geöffnet / When die Seite gerendert wird / Then ist der H1 "Wann soll ein Alert ausgelöst werden?" sichtbar im DOM oberhalb des ModeCard-Grids (nicht via `display: none` versteckt).

- Test: (populated after /tdd-red)

**AC-2:** Given Desktop-Viewport und Alerts-Tab geöffnet / When die Seite gerendert wird / Then sind alle drei ModeCards (`data-testid="mode-card-delta"`, `mode-card-absolute"`, `mode-card-both"`) sichtbar in einem 3-Spalten-Grid mit `display: grid`.

- Test: (populated after /tdd-red)

**AC-3:** Given ModeCard "Beides" ist aktiv (Default) / When eine ModeCard gerendert wird / Then hat die aktive Card `border: 2px solid var(--g-accent)` und `background: var(--g-card)`, der Titel-Span hat `color: var(--g-accent-deep)`, und der Radio-Dot-Inner-Span ist im DOM sichtbar.

- Test: (populated after /tdd-red)

**AC-4:** Given AlertMetricTable wird gerendert / When der Benutzer den Tab öffnet / Then ist die Tabelle in einen `Card padding={0}`-Wrapper eingebettet, und eine Header-Row mit `background: var(--g-card-alt)` und `border-bottom: 1px solid var(--g-rule)` ist oberhalb der Datenzeilen sichtbar, mit Eyebrow-Labels "Metrik", "Δ-Änderung (seit letztem Briefing)" und "Absoluter Schwellwert".

- Test: (populated after /tdd-red)

**AC-5:** Given eine AlertMetricRow für eine normale (nicht delta-only) Metrik / When `state.deltaEnabled = false` und `state.absEnabled = false` / Then hat die Zeile `opacity: 0.45`, Spalte 3 zeigt den Text "— deaktiviert —" und Spalte 4 zeigt den Text "— deaktiviert —".

- Test: (populated after /tdd-red)

**AC-6:** Given AlertCooldownCard wird gerendert / When der Tab geöffnet wird / Then ist der Titel als `Eyebrow`-Atom gerendert (nicht als `h4`), der Hint-Text entspricht "Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten", und das Input hat `width: 80px`, `font-family: var(--g-font-mono)`.

- Test: (populated after /tdd-red)

**AC-7:** Given AlertQuietHoursCard wird gerendert / When der Tab geöffnet wird / Then ist der Titel als `Eyebrow`-Atom gerendert (nicht als `h4`), der Hint-Text entspricht "In diesem Zeitraum keine Alerts senden — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit.", die Time-Inputs haben `width: 80px` und `font-family: var(--g-font-mono)`, und der Checkbox-Toggle ist weiterhin sichtbar.

- Test: (populated after /tdd-red)

**AC-8:** Given `app.css` wird geladen / When eine Komponente `var(--g-info-deep)` verwendet / Then ist der Token definiert als `#1a4a7a` (dunkles Blau, sichtbar unterschiedlich von `--g-info: #2a6cb3`).

- Test: (populated after /tdd-red)

**AC-9:** Given AlertsTab auf Desktop / When die Seite gerendert wird / Then sind zwei `SectionH`-Elemente sichtbar: eines mit `eyebrow="Auslöse-Modus"` vor dem ModeCard-Grid und eines mit `eyebrow="Schwellwerte"` vor der AlertMetricTable.

- Test: (populated after /tdd-red)

**AC-10:** Given bestehende Tests `alertMetricTable.test.ts` und `alertPreviewHelpers.test.ts` / When `npm run test` (oder `node --test`) ausgeführt wird nach den Design-Änderungen / Then laufen alle bestehenden Tests weiterhin grün durch ohne Änderungen an den Testdateien.

- Test: (populated after /tdd-red)

## Known Limitations

- **AlertMetricRow Severity-Select:** Die JSX-Vorlage zeigt keinen Severity-Select — er ist eine funktionale Erweiterung. Er wird als 5. Spalte (auto-width) rechts der 4 JSX-Spalten beibehalten, damit kein Datenverlust entsteht.
- **AlertQuietHoursCard Checkbox-Toggle:** JSX zeigt immer beide Inputs; die Checkbox-Toggle-Logik (ein-/ausblenden) ist eine funktionale Erweiterung aus Issue #181. Sie bleibt erhalten.
- **AlertPreviewCard iframe vs. statisches HTML:** JSX zeigt ein statisches HTML-E-Mail-Template inline. Der API-basierte iframe (`/api/trips/{id}/alert-preview`) ist eine deutliche funktionale Verbesserung und wird beibehalten; nur das Card-Styling und der SectionH-Header werden angeglichen.
- **Mobile-Breakpoint (≤899px):** Die Mobile-only-Blöcke (fixierter Footer, Mobile-H1, Mobile-Modus-Picker) aus Issue #414 bleiben unverändert erhalten. Auf Mobile wird der neue Desktop-Header per CSS ausgeblendet; das ModeCard-Grid benutzt auf Mobile weiterhin `display: flex` statt Grid.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/app.css` | Frontend/Tokens | MODIFY — `--g-info-deep` Token | ~2 |
| 2 | `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Frontend | MODIFY — Desktop-Header, SectionH, ModeCard-Grid immer sichtbar, vollständige ModeCard-Styles nach JSX | ~70 |
| 3 | `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | Frontend | MODIFY — Card-Wrapper, Header-Row, Atoms-Import | ~20 |
| 4 | `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | Frontend | MODIFY — 4-Spalten-Grid, Zeilen-Switch, Label+Unit-Spalte, Delta/Abs-Spalten nach JSX | ~60 |
| 5 | `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Frontend | MODIFY — Eyebrow statt h4, Hint-Text, Input-Style | ~10 |
| 6 | `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Frontend | MODIFY — Eyebrow statt h4, Hint-Text, Input-Style | ~10 |
| 7 | `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | Frontend | MODIFY — h4 entfernen, Card-Styling angleichen | ~10 |

**Gesamt:** ~182 LoC netto, 7 Dateien (alle bestehend, keine neuen Komponenten)

## Changelog

- 2026-06-04: Initial spec für Issue #586 — Alert-Config Design-Fidelity 1:1 nach screen-alert-config.jsx. Desktop-Header, ModeCard-Grid auf Desktop, AlertMetricTable Card+Header-Row, AlertMetricRow 4-Spalten-Grid nach JSX, Cooldown/QuietHours Eyebrow+Input-Style, PreviewCard SectionH, Token --g-info-deep. 10 Acceptance Criteria im AC-N Given/When/Then-Format. Bestehende Logik-Module und Tests unberührt.
