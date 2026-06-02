# Context: Bug #541 + #543 + #544 — Token-Cleanup, native Checkboxen, Tailwind-Rest

## Request Summary

Drei kleine, chirurgische Frontend-Fixes aus dem retrospektiven Adversary-Audit (#510):
1. **#543** — `Step3Weather` + `Step5Reports` benutzen noch native `<input type="checkbox">` statt der Atomic-Komponente `<Checkbox>` — das bricht den projektweiten Guard-Test `test_ac3_no_native_checkboxes_outside_component`.
2. **#544** — `WeatherConfigDialog.svelte` hat noch eine Tailwind-Klasse `hover:bg-muted/50` (Residual von vor der Token-Migration), die laut Spec #285 AC-4 entfernt werden soll.
3. **#541** — Alte Farb-Token-Aliasse (`--g-good`, `--g-warn`, `--g-bad`) müssen aus dem gesamten `frontend/src/` entfernt und durch die kanonischen Namen (`--g-success`, `--g-warning`, `--g-danger`) ersetzt werden; danach werden die drei Brücken-Aliasse aus `app.css` gelöscht.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte:227` | native Checkbox (`<input type="checkbox">`) → #543 |
| `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte:79,103,122,170` | 4× native Checkbox → #543 |
| `frontend/src/lib/components/ui/checkbox/Checkbox.svelte` | Ziel-Komponente für Migration (#543); Props: `checked`, `disabled`, `onchange`, `children` (Snippet) |
| `frontend/src/lib/components/WeatherConfigDialog.svelte:225` | `hover:bg-muted/50` → ersetzen durch `.metric-row:hover { background: var(--g-surface-2); }` — #544 |
| `frontend/src/app.css:73-75,158-160` | Brücken-Aliasse + ursprüngliche Definition der alten Token — #541 |
| 35 weitere `.svelte`-Dateien unter `frontend/src/` | Vorkommen von `--g-good`, `--g-warn`, `--g-bad` → #541 |
| `tests/tdd/test_issue_278_form_controls.py::test_ac3_no_native_checkboxes_outside_component` | Guard-Test, der durch #543 rot ist |

### Vollständige Liste betroffener Dateien für #541 (Token-Rename)

```
frontend/src/lib/components/alerts-tab/AlertsTab.svelte
frontend/src/lib/components/atoms/Switch.svelte
frontend/src/lib/components/briefings-tab/BriefingsTab.svelte
frontend/src/lib/components/compare/CompareMatrix.svelte
frontend/src/lib/components/compare/CompareTabs.svelte
frontend/src/lib/components/compare/CompareWizard.svelte
frontend/src/lib/components/compare/LocationsRail.svelte
frontend/src/lib/components/compare/RecommendationBanner.svelte
frontend/src/lib/components/compare/steps/Step2Orte.svelte
frontend/src/lib/components/compare/steps/Step5Versand.svelte
frontend/src/lib/components/edit/EditStagesPanelNew.svelte
frontend/src/lib/components/mobile/MBtn.svelte
frontend/src/lib/components/mobile/MSwitch.svelte
frontend/src/lib/components/mobile/Toast.svelte
frontend/src/lib/components/molecules/AlertRow.svelte
frontend/src/lib/components/molecules/BriefingTimelineRow.svelte
frontend/src/lib/components/molecules/Field.svelte
frontend/src/lib/components/molecules/StagePill.svelte
frontend/src/lib/components/preview/SmsPhoneFrame.svelte
frontend/src/lib/components/shared/OutputLayoutEditor.svelte
frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte
frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte
frontend/src/lib/components/trip-detail/BucketSection.svelte
frontend/src/lib/components/trip-detail/ChannelFidelityBubble.svelte
frontend/src/lib/components/trip-detail/ChannelFidelityEmail.svelte
frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte
frontend/src/lib/components/trip-detail/ChannelLimitMarkers.svelte
frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte
frontend/src/lib/components/trip-detail/TripTabs.svelte
frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte
frontend/src/lib/components/trip-wizard/Stepper.svelte
frontend/src/lib/components/trip-wizard/TripWizardShell.svelte
frontend/src/routes/_design/+page.svelte
frontend/src/routes/_design-system/+page.svelte
frontend/src/routes/_home/TripKachel.svelte
```

## Existing Patterns

- **Checkbox-Migration:** `<Checkbox>` aus `$lib/components/ui/checkbox` hat Props `checked`, `disabled`, `onchange`, `children` (als Svelte Snippet); der native `<input>` ist darin opacity:0 versteckt (Atom-Pattern).
- **Chip-Checkboxen in Step5Reports:** Die `channel-chips` Snippet-Funktion (ab Zeile ~160) verwendet native Checkboxen mit custom `class="chip"`-Labels und `disabled`-Support — hier muss geprüft werden, ob die Atomic-Komponente passt oder ob das Chip-Layout eine separate Behandlung braucht.
- **Token-Mapping:**
  - `--g-good` → `--g-success`
  - `--g-warn` → `--g-warning`
  - `--g-bad` → `--g-danger`
- **Kontrast-Tests:** `tests/tdd/test_issue_278_form_controls.py` enthält Guard-Test für Checkboxen; Kontrast-Tests in `frontend/tests/` prüfen Token-Verwendung.

## Dependencies

- **#543 upstream:** `$lib/components/ui/checkbox/Checkbox.svelte` (Ziel-Komponente vorhanden)
- **#541 upstream:** `app.css` Brücken-Aliasse (werden erst am Ende entfernt, wenn alle Vorkommen umgestellt sind)
- **#541 downstream:** Kontrast-Tests müssen weiterhin grün bleiben (Token-Werte ändern sich nicht, nur die Namen)

## Execution Plan (Reihenfolge)

1. **#543** — 5 native Checkboxen in Step3Weather + Step5Reports ersetzen (Guard-Test wird grün)
2. **#544** — `hover:bg-muted/50` in WeatherConfigDialog durch Token-basiertes Hover-CSS ersetzen
3. **#541** — Alle `--g-good`/`--g-warn`/`--g-bad` Vorkommen in 35 Dateien umbenennen, danach Brücken-Aliasse aus `app.css` entfernen

## Risks & Considerations

- **Chip-Checkboxen (#543):** Die Checkboxen in `channelChips` (Step5Reports:170) sind in styled `<label class="chip">` eingebettet — die Atomic-`<Checkbox>`-Komponente rendert ihr eigenes Label. Lösung: Checkbox als kontrollierten Input ohne children-Snippet verwenden, das Chip-Label bleibt außen (wie schon in anderen Projektstellen).
- **`atoms/Switch.svelte` (#541):** Benutzt `--g-good`, `--g-warn`, `--g-bad` als JS-Objekt-Keys (`good:`, `warn:`, `bad:`) — diese Keys sind intern (nicht CSS-Variablen), müssen NICHT umbenannt werden. Nur `var(--g-xxx)` Referenzen umbenennen.
- **`app.css` Reihenfolge (#541):** Erst alle Vorkommen umbenennen, DANN Brücken-Aliasse entfernen — nicht umgekehrt (würde visuellen Bruch verursachen).
- **Keine Backend-Änderungen** — rein frontend-seitig.
