# Spec: Wetter-Editor-Konsolidierung — Touren-Teil (#345)

- **Issue:** #345 (letzter offener Teil von Epic #304)
- **Created:** 2026-05-25
- **Status:** Draft — wartet auf Approval
- **Workspace:** `/home/hem/gz-workspaces/issue-345` (Branch `ws/issue-345`, basiert auf origin/main inkl. #361)
- **Design-Quelle:** Claude Design, `docs/design-requests/issue_345_assets/` (`screen-weather-consolidation.jsx` → `WEKEditFormDrop`, `WEKQuickPanelDrop`)

## Kontext

Nach Abschluss von **#361** lebt der vollständige Wetter-Metriken-Editor im
Tour-Detail-Tab „Wetter-Briefing" (`WeatherMetricsTab.svelte`, erreichbar via
`/trips/{id}#weather`). Er kann Spalten/Detail/Aus, Reihenfolge, Zeithorizonte,
Roh/Skala, Presets und 4-Kanal-Vorschau. Die Editor-Logik liegt wiederverwendbar in
`frontend/src/lib/components/trip-detail/metricsEditor.ts` (u. a. `buildBucketSummary`,
`buildPresetSummary`).

Daneben existieren noch **zwei veraltete Wetter-Editoren**, die beim Speichern die komplette
`display_config` **überschreiben** (verlieren Buckets/Reihenfolge/Horizonte — Datenverlust):

- `EditWeatherSection.svelte` (in der Tour-Bearbeiten-Maske `TripEditView.svelte`).
- `WeatherConfigDialog.svelte` (Schnell-Fenster, aufgerufen aus `/trips`, `/locations`, `/subscriptions`).

Claude Designs Entscheidung: Wetter hat **genau eine** Bearbeitungsstelle (der Detail-Tab);
alle anderen Stellen sind read-only bzw. verweisen dorthin (AP-013).

## Scope dieser Lieferung (Touren-Teil)

Beseitigt beide Alt-Editoren **für Touren** und behebt damit das Touren-Datenverlust-Risiko —
schließt #304.

**NICHT in dieser Lieferung (→ #362):** der Orts-/Abo-Editor (`context="ort"/"abo"` mit
ScoreToggle). Solange dieser fehlt, bleibt `WeatherConfigDialog.svelte` für `/locations` und
`/subscriptions` bestehen (Funktion erhalten, #345 AC-3). Die Datei wird daher noch **nicht**
gelöscht, nur ihre Verwendung in der Touren-Liste entfernt.

## Betroffene Dateien

| Datei | Aktion |
|-------|--------|
| `frontend/src/lib/components/edit/TripEditView.svelte` | Accordion-Sektion „Wetter": Editor → read-only Profil-Zusammenfassung + Link; `display_config` nicht mehr aus dieser Maske speichern |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | **löschen** |
| `frontend/src/lib/components/edit/WeatherSummaryCard.svelte` | **neu**: read-only Profil-Zusammenfassung + Link „Im Wetter-Tab bearbeiten →" |
| `frontend/src/routes/trips/+page.svelte` | Kebab-Eintrag „Wetter-Konfiguration": öffnet nicht mehr den Dialog, sondern navigiert zu `/trips/{id}#weather`; `WeatherConfigDialog`-Import + `weatherConfigTarget`-State + `handleWeatherSave` entfernen |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | nur lesend wiederverwenden (`buildBucketSummary`/`buildPresetSummary`); ggf. winzige Helper-Extraktion für die Summary aus `display_config` |

## Acceptance Criteria

**AC-1:** Given eine Tour in der Bearbeiten-Maske (`/trips/{id}/edit`), When ich den Abschnitt
„Wetter" öffne, Then sehe ich eine **read-only** Profil-Zusammenfassung (Profilname/Preset +
Anzahl Spalten/Detail/aktive Metriken aus `display_config`) und einen Link „Im Wetter-Tab
bearbeiten →", aber **keine** bearbeitbaren Metrik-Checkboxen/Toggles mehr.

**AC-2:** Given die Bearbeiten-Maske, When ich „Tour speichern" klicke, Then wird die
`display_config` durch diesen Save **nicht verändert** (kein Überschreiben der im Wetter-Tab
gesetzten Buckets/Horizonte) — nur Identitäts-/Stammdaten (Name, Etappen, Alarmregeln, Reports)
werden gespeichert.

**AC-3:** Given die Codebasis, When ich nach `EditWeatherSection` suche, Then ist
`EditWeatherSection.svelte` gelöscht und es gibt **keinen** Import mehr darauf.

**AC-4:** Given die Touren-Liste (`/trips`), When ich im Kebab-Menü „Wetter-Konfiguration"
wähle, Then werde ich zum Tour-Detail-Wetter-Tab (`/trips/{id}#weather`) navigiert und es
öffnet sich **kein** Schnell-Fenster mehr; der `WeatherConfigDialog` wird in `/trips` nicht
mehr eingebunden.

**AC-5:** Given der Link „Im Wetter-Tab bearbeiten →" in der Bearbeiten-Maske, When ich ihn
klicke, Then lande ich auf `/trips/{id}#weather` mit aktivem Wetter-Briefing-Tab.

**AC-6:** Given `/locations` und `/subscriptions`, When ich dort die Wetter-Konfiguration
öffne, Then funktioniert sie unverändert weiter (`WeatherConfigDialog` bleibt dort bestehen) —
diese Lieferung fasst sie nicht an.

## Risiken & Datensicherheit

- **Datenverlust (CLAUDE.md Schema-Regel):** Der eigentliche Zweck ist, das Überschreiben von
  `display_config` durch die Edit-Maske zu beenden. Verifikation: Tour im Wetter-Tab
  konfigurieren (Buckets/Horizonte), dann in der Bearbeiten-Maske „Tour speichern" — die
  Wetter-Konfiguration muss unverändert bleiben.
- **Save-Flow TripEditView:** `display_config` aus dem `PUT /api/trips/{id}`-Payload nehmen
  bzw. unverändert aus dem geladenen Trip durchreichen (Read-Modify-Write-Merge), NICHT aus
  einem UI-Teilstand neu bauen.
- **Mobile:** read-only Karte + Link müssen auch im Card-Stack/Mobile-Layout funktionieren.

## Out of Scope

- Orts-/Abo-Editor (`context`), ScoreToggle → #362.
- Vollständiges Löschen von `WeatherConfigDialog.svelte` → mit #362, wenn Orte/Abos einen
  Ersatz-Editor haben.
- Änderungen am Editor selbst (kam aus #361).
