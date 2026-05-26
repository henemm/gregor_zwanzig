# Context: Issue #382 — Select.svelte iOS-Auto-Zoom (latente #272-Regression)

## Request Summary
`Select.svelte` setzt `font-size: var(--g-text-sm)` (= 13px) auf `.gz-select select` mit CSS-Spezifität (0,1,1). Der globale iOS-Zoom-Guard in `app.css` hat nur Spezifität (0,0,1) und verliert — alle 14 Einsatzorte zoomen auf iOS beim Fokus rein.

## Related Files
| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/ui/select/Select.svelte` | Hauptdatei — hier liegt der Bug (Zeile 39: `font-size: var(--g-text-sm)`) |
| `frontend/src/app.css` | Globaler iOS-Guard (Z. 457–462), Kommentar-Warnung (Z. 440–441) |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Referenz-Implementierung: scoped `@media`-Override (Z. 337–342) |

## Einsatzorte (14 Dateien)
| Datei | Kontext |
|-------|---------|
| `SubscriptionForm.svelte` | Abo-Formular |
| `compare/NewLocationWizard.svelte` | Ortsvergleich-Wizard |
| `compare/PresetHeader.svelte` | Preset-Auswahl |
| `compare/CreateGroupDialog.svelte` | Gruppen-Dialog |
| `LocationForm.svelte` | Locations-Formular |
| `alerts-tab/AlertMetricRow.svelte` | Alert-Konfigurator |
| `WeatherConfigDialog.svelte` | Wetter-Konfiguration |
| `trip-detail/ChannelPreviewBlock.svelte` | Kanal-Vorschau |
| `routes/weather/+page.svelte` | Wetter-Seite |
| `routes/_design/+page.svelte` | Design-Showcase |
| `routes/trips/+page.svelte` | Trips-Übersicht |
| `alert-rules-editor/AlertRuleRow.svelte` | Alert-Regeln |
| `routes/compare/+page.svelte` | Compare-Seite |
| `lib/components/ui/select/index.ts` | Re-Export |

## Bestehende Muster
- **app.css Z. 440–441:** Explizite Warnung: `font-size NICHT setzen — sonst überschreibt die Klassen-Specificity (0,1,0) die iOS-Safari-Schutzregel`
- **SavePresetDialog.svelte:** Scoped `@media (max-width: 767px) { .field input, .field textarea { font-size: 16px; } }` — das etablierte Fix-Muster für Komponenten mit eigenem `font-size`

## Ursache
```
.gz-select select { font-size: var(--g-text-sm); }  /* Spez. (0,1,1) — GEWINNT */
@media (...) { input, select, textarea { font-size: 16px; } }  /* Spez. (0,0,1) — VERLIERT */
```

## Fix-Strategie
Identisches Muster wie `SavePresetDialog.svelte`: in `Select.svelte` `<style>` einen scoped `@media (max-width: 767px)`-Block ergänzen, der `.gz-select select` auf `font-size: 16px` setzt. Gleichspezifisch mit der Basisregel, aber durch Quelltextreihenfolge hinten → gewinnt auf Mobile.

## Risks & Considerations
- Kein Risiko für Desktop (Media Query greift nur ≤767px)
- Svelte-Scoping (Hash-Attribut) erhöht effektive Spezifität beider Regeln gleichermaßen → kein neues Spezifitätsproblem
- Kein anderer Code muss geändert werden (Fix liegt ausschließlich in `Select.svelte`)
