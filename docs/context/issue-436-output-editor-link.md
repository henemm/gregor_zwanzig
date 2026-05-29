# Context: Issue #436 — „Inhalt im Output-Editor anpassen"-Link

## Request Summary

Der Wizard-Step 5 (Reports) soll laut Mockup einen Link „Inhalt im Output-Editor anpassen →" haben, der auf den Layout/Output-Editor in Trip-Detail verweist. Da im Wizard noch kein Trip existiert, muss der Link anders platziert werden — Issue #436 entscheidet die Strategie und implementiert sie.

## Ist-Zustand

| Datei | Befund |
|-------|--------|
| `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte` | Kein Link vorhanden (war in #428 bewusst Out-of-Scope) |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `save()` navigiert nach `goto('/trips')` — TODO-Kommentar verweist auf epic-135; `created.id` aus der API-Antwort wird mit `void created` verworfen |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Hat bereits `<a href="#weather">Bearbeiten →</a>` in der Übersichts-Spalte |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Hat bereits `<a href="#briefings">Bearbeiten →</a>` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab `weather` (Label "Wetter-Briefing") enthält `WeatherMetricsTab` mit `OutputLayoutEditor.svelte` |
| `frontend/src/routes/trips/[id]/+page.svelte` | `initialTab` aus URL-Hash: `page.url.hash.replace(/^#/, '')` |

## Lösungsstrategie (Issue-Empfehlung: Option 3)

Issue #436 empfiehlt **Option 3**: Link im Wizard weglassen (Wizard = Erstellung, nicht Editierung), dafür in Trip-Detail sichtbar machen.

### Was ist schon getan?

- `WeatherMetricsPreviewCard` hat bereits einen „Bearbeiten →"-Link → `#weather`
- `BriefingPreviewCard` hat bereits einen „Bearbeiten →"-Link → `#briefings`

### Was fehlt noch?

1. **Wizard save → Trip-Detail-Navigation**: `wizardState.save()` navigiert aktuell nach `/trips` statt nach `/trips/[created.id]`. Das TODO aus epic-135 ist längst erfüllt — die Trip-Detail-Page `/trips/[id]` existiert. Die API-Antwort (`created`) wird schon empfangen, nur verworfen. Fix: `void created` entfernen, `goto(\`/trips/${created.id}\`)` statt `/trips`.

2. **„Inhalt im Output-Editor anpassen →" im Trip-Detail**: `WeatherMetricsPreviewCard` hat den Link bereits (`Bearbeiten →` → `#weather`). Der Link-Text könnte spezifischer sein; die Funktionalität ist aber schon da. Ggf. nur Label-Anpassung nötig.

3. **Step 5 bleibt ohne Link** (bestätigt Option 3 — kein Handlungsbedarf).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `save()` → Navigation nach Save |
| `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte` | Step 5 — kein Link nötig |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Existierender Link → `#weather` |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Referenz-Pattern für Preview-Cards |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Values; `weather` = OutputLayoutEditor |
| `frontend/src/routes/trips/[id]/+page.svelte` | Hash-Navigation, `initialTab` |

## Dependencies

- **Upstream**: API `POST /api/trips` liefert `Trip` mit `.id` zurück (bereits genutzt, nur verworfen)
- **Downstream**: `WeatherMetricsTab` → `OutputLayoutEditor.svelte` (bereits vorhanden, kein Änderungsbedarf)

## Risks & Considerations

- `void created` ist ein absichtliches `eslint`-Muster (suppress unused-variable warning). Wenn wir `created.id` nutzen, muss `void` entfernt werden.
- Hash-Navigation (`/trips/[id]#weather`) funktioniert nur wenn die Trip-Detail-Page den Hash in `initialTab` auswertet — das tut sie bereits via `page.url.hash`.
- Kleine Scope: nur `wizardState.svelte.ts` (save-Navigation) + optional Label-Anpassung in `WeatherMetricsPreviewCard.svelte`.
