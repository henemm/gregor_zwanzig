# Context: Konsolidierung Wetter-Editoren (#345)

> Letzte offene Aufgabe des Epic **#304** (Pro-Metrik-Zeithorizont + "Im Profil speichern").
> Sub-Issues #342 (Backend), #343 (HorizonChip-UI), #344 (/account-Karte) sind **geschlossen**.
> Mit dem Abschluss von #345 kann #304 geschlossen werden.

## Request Summary

Zwei veraltete, parallele Wetter-Editoren entfernen bzw. zusammenführen, sodass es eine
zentrale, wiederverwendbare Metrik-Konfigurations-Komponente gibt — mit den Features aus
Sub-Issue #343 (HorizonChip pro Metrik, Presets, Snapshot/Undo).

## Ausgangslage: Drei Editoren, zwei davon veraltet

Ein Trip kann seine Wetter-Config heute auf **zwei** Wegen bearbeiten:

| Weg | Route | Container | Editor | Horizons? | Save-Flow |
|-----|-------|-----------|--------|-----------|-----------|
| Edit-Maske | `/trips/[id]/edit` | `TripEditView` | **`EditWeatherSection`** (alt) | ❌ | `PUT /api/trips/{id}` (ganzes Trip-Objekt, `display_config`) |
| Detail-Tab | `/trips/[id]` | `TripTabs` | **`WeatherMetricsTab`** (neu, Ziel) | ✅ | `PUT /api/trips/{id}/weather-config` (nur Metriken) |

Zusätzlich existiert ein **Modal** für Listen-Schnellzugriff:

| Modal | Verwender (3×) | Horizons? | Save-Flow |
|-------|----------------|-----------|-----------|
| **`WeatherConfigDialog`** | `/subscriptions`, `/locations`, `/trips` (Liste) | ❌ | `onsave`-Callback → `PUT /{entity}/{id}/weather-config` |

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | **Zu löschen.** Alter Editor, `bind:displayConfig`, keine Horizons. |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Einziger Importeur von EditWeatherSection (Z. 8, 113). Umstellen. Sammelt alle Trip-Felder, speichert via `PUT /api/trips/{id}` (Z. 50–74). |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Modal, 3 Verwender. Status klären (modernisieren vs. ersetzen). Keine Horizons. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | **Ziel-Komponente.** Prop `trip: Trip`, HorizonChip, Presets, Snapshot/Undo. Eigener API-Call `PUT /api/trips/{id}/weather-config` (Z. 221–248). |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Nutzt HorizonChip pro Metrik-Reihe. |
| `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte` | Atom-Komponente (#343). |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Mountet `TripEditView` (Z. 7). |
| `frontend/src/routes/trips/[id]/+page.svelte` | Mountet `TripTabs` (Z. 111). |
| `frontend/src/routes/subscriptions/+page.svelte` | WeatherConfigDialog (Z. 10, 264), `handleWeatherSave` Z. 113–125. |
| `frontend/src/routes/locations/+page.svelte` | WeatherConfigDialog (Z. 10, 196), `handleWeatherSave` Z. 89–101. |
| `frontend/src/routes/trips/+page.svelte` | WeatherConfigDialog (Z. 9, 586), `handleWeatherSave` Z. 246–258. |

## Existing Patterns

- **WeatherMetricsTab als autonomer Tab:** lädt Katalog/Templates/UserPresets selbst, hält
  `enabledMap`/`friendlyMap`/`horizonsMap`, macht eigenen API-Call. Nimmt nur `trip: Trip`.
  Wiederverwendbar exportiert via `trip-detail/index.ts:13`.
- **EditWeatherSection als gebundene Inline-Sektion:** `bind:displayConfig` (Zwei-Wege), kein
  eigener Save — der Container (TripEditView) speichert das Gesamt-Trip-Objekt.
- **WeatherConfigDialog als entity-agnostisches Modal:** `entityName` + `currentConfig` + `onsave`/`onclose`-Callbacks; der jeweilige Aufrufer übernimmt den API-Call.

## Dependencies

- **Upstream:** `Trip.display_config.metrics[]` (Backend-Schema aus #342, inkl. `horizons`),
  Metrik-Katalog-Endpoint, Template-/Preset-Endpoints.
- **Downstream:** Drei Routen am Modal (subscriptions/locations/trips), die Trip-Edit-Maske,
  der Trip-Detail-Tab.

## Existing Specs

- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — Metrik-Editor-UI-Komponenten (MetricGroup, MetricCheckbox, …).
- `docs/specs/modules/issue_285_weather_section_restyle.md` — Restyle EditWeatherSection + WeatherConfigDialog auf Brand-Tokens (wird durch Löschung teilweise obsolet).
- `docs/specs/ux_redesign_navigation.md` — Ursprungs-Vision Pro-Metrik-Zeithorizont.
- Sub-Issue-Specs #342/#343/#344 unter `docs/specs/modules/`.

## Risks & Considerations

1. **Zwei unterschiedliche Save-Flows.** WeatherMetricsTab speichert eigenständig via
   `/weather-config`; TripEditView speichert das ganze Trip-Objekt via `PUT /api/trips/{id}`.
   Einbettung 1:1 würde **zwei konkurrierende Speicher-Wege** in der Edit-Maske erzeugen
   (Doppel-Save, möglicher Daten-Konflikt). → In Phase 2 entscheiden: WeatherMetricsTab um
   einen gebundenen/Save-losen Modus erweitern **oder** Wetter-Sektion aus der Edit-Maske
   entfernen und auf den Detail-Tab verweisen.
2. **Horizons ohne Etappen-Datum.** Subscriptions/Locations haben kein Etappen-Startdatum →
   heute/morgen/übermorgen ist dort fachlich sinnlos (Issue-Risiko explizit benannt).
   HorizonChips dürfen im Modal für diese Entitäten **nicht** erscheinen.
3. **Datenverlust-Risiko (CLAUDE.md Schema-Regel).** `display_config` ist Persistenz-relevant.
   Beim Umbau der Edit-Maske Read-Modify-Write/Merge sicherstellen — kein Überschreiben des
   ganzen `display_config` mit UI-Teilstand (Anti-Pattern BUG-DATALOSS-GR221).
4. **`issue_285_weather_section_restyle`** stylte beide alten Editoren — nach Löschung prüfen,
   ob dort Tote-Referenzen/Doku bereinigt werden müssen.
5. **AC-3 Mehrdeutigkeit:** "modernisiertes Modal **oder** Verweis auf Detail-Seite" — die
   Produkt-Entscheidung (Modal behalten vs. abschaffen) ist offen und muss vor der Spec
   getroffen werden.

## Offene Entscheidungen → an Claude Design delegiert (2026-05-24)

Die offenen Punkte sind UX-/Produkt-Entscheidungen, keine reinen Implementierungs-Details.
Auf PO-Wunsch an **Claude Design** delegiert. Formelle Anforderung:
`docs/design-requests/issue_345_weather_editor_consolidation.md` (Fragen F1–F3).

- **F1 — Schnell-Fenster (WeatherConfigDialog):** behalten/vereinheitlichen, mit Horizonten bei
  Touren, oder abschaffen?
- **F2 — Tour-Bearbeiten-Maske (EditWeatherSection/TripEditView):** Wetter-Abschnitt behalten +
  modernisieren oder streichen (nur noch Detail-Tab)?
- **F3 — Horizonte bei Abos/Orten:** ausblenden bestätigen (kein Datum).

**Workflow pausiert** bis Design-Antwort vorliegt. Danach: Phase 3 (Spec) auf Basis der
Design-Entscheidung. Erkannte technische Leitplanken für die Spec unabhängig vom Design:
gemeinsame innere Editor-Komponente extrahieren (DRY), Save per Read-Modify-Write/Merge
(kein Überschreiben der ganzen `display_config`), `EditWeatherSection.svelte` löschen.
