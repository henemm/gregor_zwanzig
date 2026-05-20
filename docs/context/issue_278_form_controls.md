# Context: Issue #278 — Branded Form Controls (Checkbox & Select)

## Request Summary

Alle nativen `<input type="checkbox">` und `<select>`-Elemente in der App sollen durch wiederverwendbare, design-konforme UI-Komponenten (`Checkbox.svelte` und `Select.svelte`) ersetzt werden. Aktuell rendern alle Checkboxen als system-blaues OS-Default (iOS/macOS), was visuell inkonsistent mit dem Design-System ist.

## Scope

**35+ native Checkboxen** in 11 Dateien, **~20 native Selects** in 10 Dateien.

## Related Files

### Neu zu erstellen

| Datei | Zweck |
|-------|-------|
| `frontend/src/lib/components/ui/checkbox/Checkbox.svelte` | Neue gebrandete Checkbox-Komponente |
| `frontend/src/lib/components/ui/checkbox/index.ts` | Export |
| `frontend/src/lib/components/ui/select/Select.svelte` | Neue gebrandete Select-Komponente |
| `frontend/src/lib/components/ui/select/index.ts` | Export |

### Checkboxen ersetzen (11 Dateien)

| Datei | Anzahl Checkboxen | data-testid? |
|-------|-------------------|--------------|
| `src/routes/trips/+page.svelte` | 7 | nein |
| `src/lib/components/edit/EditWeatherSection.svelte` | 1 | ja (`metric-checkbox-{id}`) |
| `src/lib/components/edit/EditReportConfigSection.svelte` | 9 | ja (diverse) |
| `src/lib/components/trip-wizard/steps/ReportRow.svelte` | 1 | ja |
| `src/lib/components/trip-wizard/steps/ChannelToggle.svelte` | 1 | nein |
| `src/lib/components/compare/LocationsRail.svelte` | 4 | nein |
| `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 2 | nein |
| `src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | 1 | nein |
| `src/lib/components/SubscriptionForm.svelte` | 7 | ja |
| `src/lib/components/WeatherConfigDialog.svelte` | 1 | nein |
| `src/lib/components/trip-detail/SavePresetDialog.svelte` | 1 | nein |

### Selects ersetzen (10 Dateien)

| Datei | Anzahl Selects | data-testid? |
|-------|----------------|--------------|
| `src/routes/trips/+page.svelte` | 2 | ja |
| `src/routes/compare/+page.svelte` | 1 | nein |
| `src/routes/weather/+page.svelte` | 2 | ja |
| `src/lib/components/LocationForm.svelte` | 1 | nein |
| `src/lib/components/SubscriptionForm.svelte` | 4 | nein |
| `src/lib/components/WeatherConfigDialog.svelte` | 1 | nein |
| `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 3 | ja |
| `src/lib/components/alerts-tab/AlertMetricRow.svelte` | 1 | ja |
| `src/lib/components/compare/PresetHeader.svelte` | 4 | nein |
| `src/lib/components/edit/EditWeatherSection.svelte` | 1 | ja |

## Existing Patterns

### Vorhandenes MetricCheckbox.svelte (trip-detail/)

`src/lib/components/trip-detail/MetricCheckbox.svelte` — nutzt `<button role="checkbox" aria-checked>` mit SVG-Checkmark. Dieses Muster ist **nicht** das Ziel für die neue Checkbox (zu komplex, keine native-input-Semantik für Formulare). Die neue `Checkbox.svelte` soll native `<input type="checkbox">` visuell überschreiben via absolutem Positionieren + custom `<span>`.

### UI-Komponenten-Muster (Btn.svelte, input.svelte)

- Svelte 5 `$props()` mit `...restProps` für unbekannte HTML-Attribute
- `export { default as X } from './X.svelte'` in index.ts
- Keine Tailwind-Utility-Klassen in neuen UI-Primitiven — reines Design-Token-CSS

### Design-Token-Referenz (app.css)

Relevante Tokens für Checkbox & Select:
- `--g-ink` — Primärfarbe (checked state)
- `--g-ink-faint` — Border (unchecked)
- `--g-ink-muted` — Sekundärtext, Chevron-Color
- `--g-paper` — Background (unchecked)
- `--g-accent` — Focus-Ring
- `--g-radius-xs` (2px) — Checkbox-Radius
- `--g-radius-sm` (4px) — Select-Radius
- `--g-text-sm` (13px) — Schriftgröße
- `--g-font-ui` — Font-Family
- `--g-s-2` (8px) — Gap

## Abhängigkeiten

### Upstream (was unsere Komponenten nutzen)
- Design-Token-Variablen in `app.css`
- Svelte 5 `$props()` / `$bindable()`

### Downstream (was nach der Änderung angepasst wird)
- Alle 11 Checkbox-Dateien importieren `Checkbox` aus `$lib/components/ui/checkbox`
- Alle 10 Select-Dateien importieren `Select` aus `$lib/components/ui/select`
- Playwright-Tests mit `data-testid` müssen unverändert bleiben (via `...rest` weitergereicht)

## Existing Specs

- `docs/specs/modules/issue_180_alert_metric_table.md` — AlertMetricRow ist betroffene Datei
- `docs/specs/modules/issue_259_briefings_tab.md` — BriefingsTab ist betroffene Datei
- `docs/reference/design_system.md` — Token-Referenz

## Besonderer Hinweis: Pending Changes (Issue #277)

9 Dateien im Working Tree haben Pending Changes für Issue #277 (CSS-Variablen-Fallbacks entfernen). Diese Änderungen sind **unabhängig** von #278. Developer Agent muss auf dem aktuellen Stand (inkl. #277-Änderungen) implementieren.

## Risks & Considerations

1. **data-testid-Forwarding:** `...rest`-Props müssen zum nativen `<input>` und `<select>` weitergeleitet werden — sonst brechen Playwright-Tests.
2. **bind:checked vs. onchange:** Verschiedene Callsites nutzen `bind:checked`, andere `checked + onchange`. Die Checkbox-Komponente muss beides unterstützen (`$bindable()`).
3. **bind:value auf Select:** Die neue Select-Komponente muss `bind:value` korrekt durchreichen (`$bindable()`).
4. **Indeterminate-State:** Nur in `LocationsRail.svelte` und ggf. WeatherConfig nötig (dort mit `-` Symbol). Selten, aber Checkbox-API muss es unterstützen.
5. **Label-Wrapping:** Checkboxen sind teils in `<label>`-Tags eingebettet, teils standalone. Die neue `<Checkbox>`-Komponente enthält ein eigenes `<label>` — bestehende Wrapper-Labels müssen entfernt werden.
6. **Svelte 5 Children-Snippet:** Label-Text wird als `{@render children()}` übergeben, nicht als Slot.
7. **SubscriptionForm.svelte:** Größte Einzeldatei mit 7 Checkboxen + 4 Selects — sorgfältig prüfen.
