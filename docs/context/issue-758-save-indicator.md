# Context: Issue #758 — Speicher-Status-Indikator (Trips & Ortsvergleiche)

## Request Summary
Beim Editieren von Trips und Ortsvergleichen kann der Nutzer nicht erkennen, ob seine
Änderung gespeichert wurde. PO vermutet Auto-Save, aber es gibt kein sichtbares Feedback.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Zentral & immer sichtbar in Trip-Detail — Andock-Stelle Trip-Indikator. Hat eigenen Name-Save (`nameSaving`/`nameSaveError`). |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Etappen-Save (`saving`/`saveSuccess`/`saveError`), Button + Auto-Save bei Datum (`handleDateChange` → `void save()`). |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | report_config Button-Save (`saving`/`statusMsg`) + Auto-Save Kanäle (`handleChannelChange`, nur console.error). |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | display_config.metrics Save (`saving`/`saveSuccess`/`saveError`). |
| `frontend/src/routes/trips/[id]/+page.svelte` | Trip-Detail-Container, rendert TripHeader über allen Tabs, hält `onTripUpdate`. |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Ortsvergleich-Editor. Hat „Ungespeichert"-Pill (dirty) + expliziten Speichern-Button (`handleSave`). |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | `saveComparePreset()` PUT /api/compare/presets/{id}. Hat bereits `saveStatus: idle\|saving\|ok\|error` + `saveError` — **wird aber nirgends gerendert**. |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Round-Trip-Spread-Payload (#679 Datenschutz). |
| `frontend/src/lib/api.ts` | `api.put/post` wirft `ApiError` bei HTTP-Fehler. |

## Existing Patterns
- **Dezentral & fragmentiert:** Jede Trip-Edit-Komponente hat eigene isolierte
  `saving`/`saveSuccess`/`saveError`-Variablen mit lokalem Button-Feedback. Kein globaler Status.
- **Compare:** `saveStatus`-State existiert vollständig (idle/saving/ok/error), wird aber
  nicht angezeigt; sichtbar ist nur eine „Ungespeichert"-Pill (dirty) + Aktiv/Pausiert-Dot.
- **Inkonsistenz Auto-Save vs. Button:** Etappen-Datum & Kanäle speichern still automatisch
  (kein/kaum Feedback), Etappen-Waypoints/Briefing-Zeitplan/Metriken brauchen Button-Klick.
- Save überwiegend `await` mit try/catch; ein paar fire-and-forget (`void save()`, console.error).

## Dependencies
- Upstream: `api.ts` (HTTP), `goto()` (Navigation nach Compare-Save).
- Downstream: keine — reines UI-Feedback, keine Datenschema-Änderung.

## Existing Specs
- Keine bestehende Spec zu Save-Status. Verwandt: #498 (Auto-Save-Persistenz Etappen-Datum),
  #690/#691 (Auto-Save Metrik-Profile / Trip-New), #724 (Inline-Name-Save-Fehler-Feedback).

## Risks & Considerations
- **Scope-Creep:** Verteilt über ~6 Komponenten. Saubere Lösung = ein schlanker geteilter
  Status-Store + EIN Indikator pro Editor-Oberfläche (TripHeader / CompareEditor), statt
  Props durch 4 Ebenen zu fädeln.
- **PO-Annahme teils falsch:** „jede Änderung automatisch gespeichert" stimmt nicht durchgängig —
  Trip-Editor ist gemischt (Auto-Save + Buttons). Diese Inkonsistenz ist selbst Teil der Verwirrung.
- Frontend-only, keine Persistenz-Änderung → geringes Datenverlust-Risiko (kein Schema-Rework).
- E2E gegen Staging via staging-validator (Playwright), da UI-Feature.
