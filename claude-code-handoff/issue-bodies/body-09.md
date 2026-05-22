<!-- gregor-zwanzig-handoff: stable_id=trip-wizard-4-steps -->
## Problem

`/trips/new` rendert aktuell ein flaches Formular (Name + Etappen + Wegpunkte als Lat/Lon-Inputs + separate Wetter/Reports-Dialoge). Die Spec verlangt einen **geführten 4-Schritt-Wizard** der den User durch Route → Etappen → Wetter → Reports lotst.

`docs/specs/ux_redesign_navigation.md §2 "Wizard"` definiert die 4 Schritte explizit.

## Files (neu)

- `src/routes/trips/new/+page.svelte` (umbauen oder neu)
- `src/lib/components/wizard/WizardShell.svelte` — Stepper-Header + Footer-Nav
- `src/lib/components/wizard/steps/RouteStep.svelte` — GPX drag-drop, Multi/Auto-Split
- `src/lib/components/wizard/steps/EtappenStep.svelte` — Etappen-Liste, drag-sortierbar
- `src/lib/components/wizard/steps/WetterStep.svelte` — Template wählen + Pro-Metrik-Horizont
- `src/lib/components/wizard/steps/ReportsStep.svelte` — Report-Typen + Kanäle

## Required: WizardShell

```svelte
<script lang="ts">
  let { step = 1, total = 4, title, helperText, children, primary, secondary, onBack, onPrimary } = $props();
</script>

<div class="wizard">
  <header class="wizard__head">
    <span class="wizard__eyebrow">Schritt {step} von {total} · Neue Tour</span>
    <h2 class="wizard__title">{title}</h2>
    <Stepper {step} {total} labels={['Route','Etappen','Wetter','Reports']} />
  </header>
  <div class="wizard__body">{@render children()}</div>
  <footer class="wizard__foot">
    {#if step > 1}<Btn variant="outline" onclick={onBack}>← Zurück</Btn>{/if}
    <span class="wizard__helper">{helperText}</span>
    {#if secondary}<Btn variant="ghost" onclick={secondary.onClick}>{secondary.label}</Btn>{/if}
    <Btn variant="primary" onclick={onPrimary}>{primary} →</Btn>
  </footer>
</div>
```

## Required: 4 steps

### Step 1 — Route
- Trip-Name + Region (optional) Inputs
- Drop-Zone mit dashed accent border
- "1 Datei = Auto-Split / N Dateien = je 1 Etappe"
- Sekundär: „Manuell anlegen" Link

### Step 2 — Etappen
- Auto-Split-Ergebnis als sortierbare Kartenliste (drag handle ≡)
- Pro Etappe: Nummer · Name (editable) · Datum · km · ↑Höhenmeter · Wegpunkte-Zähler · Vorschläge-Counter (orange dashed pill)
- CTA: „Zusammenführen" / „+ Etappe einschieben" / „Pausentag"

### Step 3 — Wetter-Template
- Profile-Select (Alpen-Trekking, Skitouren, Küsten…)
- Liste der Metriken — pro Metrik 3 Horizon-Pills (heute / morgen / übermorgen) toggle-bar
- Sekundär: „Im Profil speichern" (für eigene angepasste Templates)
- Wenn vom Default abgewichen: Visual indicator („3 angepasst")

### Step 4 — Reports & Kanäle
- 4 Report-Typen als Cards: Abend-Briefing, Morgen-Update, Warnungen (Wachhund), Trend-Vorschau
- Pro Card: Checkbox aktiv/inaktiv · Uhrzeit (außer Wachhund) · Metriken-Liste · Kanal-Chips (E-Mail / Signal / SMS) · „+ Kanal" für mehr
- Primary „Tour speichern"

## Acceptance criteria

- [ ] `/trips/new` zeigt WizardShell mit Stepper.
- [ ] Schritt 1: GPX-Upload funktioniert, Auto-Split detected.
- [ ] Schritt 2: Etappen drag-sortierbar; Pausentag einfügbar.
- [ ] Schritt 3: Template lädt Default-Metriken; Pro-Metrik-Horizont editierbar.
- [ ] Schritt 4: 4 Report-Typen mit eigenen Metrik-Sets und Kanal-Auswahl.
- [ ] Zurück-Button erhält State über alle Schritte.
- [ ] „Tour speichern" am Ende von Step 4 erstellt den Trip und navigiert zur Detail-Seite.

## 📎 Screenshots

**Soll: Storyboard mit allen 4 Schritten**

![soll-1B](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1B-wizard-step1-route.png)

![soll-1C](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1C-wizard-step2-etappen.png)

![soll-1D](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1D-wizard-step3-wetter.png)

![soll-1E](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow1E-wizard-step4-reports.png)