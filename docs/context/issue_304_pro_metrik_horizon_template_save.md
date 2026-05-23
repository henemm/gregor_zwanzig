---
issue: 304
workflow: issue_304_pro_metrik_horizon_template_save
created: 2026-05-22
status: phase1_context
---

# Context: Issue #304 — Pro-Metrik-Zeithorizont + "Im Profil speichern"

## Request Summary

Issue #304 verlangt zwei UX-Bausteine, die in der Soll-Spec `ux_redesign_navigation.md` skizziert sind:

1. **Pro-Metrik-Zeithorizont:** Jede Metrik-Zeile im Wetter-Editor bekommt drei Toggle-Pills `heute / morgen / übermorgen` (unabhängig vom On/Off-Checkbox).
2. **„Im Profil speichern":** Aktuelle Auswahl (Metriken + Horizonte) als wiederverwendbares User-Profil sichern, verwalten und beim Anlegen neuer Trips wieder auswählen.

Issue nennt UI-Datei `EditWeatherSection.svelte` und drei API-Endpoints (GET/POST/PATCH/DELETE `/api/user/weather-templates`).

## Entscheidungen aus Phase 1 (User-Antworten, 2026-05-23)

| Frage | Entscheidung |
|---|---|
| Editor-Scope | **Konsolidieren** — `EditWeatherSection.svelte` (alter Editor) entfernen, überall die `WeatherMetricsTab`-Komponenten (`MetricGroup`/`MetricCheckbox`/`SavePresetDialog`/`TablePreview`) verwenden. |
| Horizon-Wirkung | **Backend filtert Mail/SMS-Briefings.** Ist `today=false` für eine Metrik, taucht sie in der heute-Spalte des Reports nicht auf. Report-Renderer muss `horizons` auswerten. |
| Profil-Verwaltung | **Eigene Karte „Wetter-Profile" auf `/account`** (Name + Metrik-Zahl + Umbenennen + Löschen pro Eintrag). Bestehende Read-only-Builtin-Card bleibt darunter sichtbar. |
| API | **`/api/metric-presets` erweitern** (PATCH-Route ergänzen, Modell um `horizons` erweitern). Kein paralleler `/api/user/weather-templates`-Pfad. |

## Wichtige Vorab-Klärung (an User)

**Doppelte Wetter-Editoren in der Codebasis** — entscheidet sich, wo „Pro-Metrik-Horizont" umgesetzt wird:

| Komponente | Pfad | Verwendung heute |
|---|---|---|
| `EditWeatherSection.svelte` | `frontend/src/lib/components/edit/` | Trip-Wizard (Step Wetter) und im Trip-Edit-Form |
| `WeatherMetricsTab.svelte` | `frontend/src/lib/components/trip-detail/` | Trip-Detail-Seite, „Wetter"-Tab (Epic #138, neueres Design) |

Die zweite Komponente hat bereits **Sub-Komponenten** (`MetricGroup`, `MetricCheckbox`, `SavePresetDialog`, `TablePreview`, `PresetRow`) **und** die User-Preset-Endpoints `GET/POST/DELETE /api/metric-presets`. Sie verfügt **nicht** über Horizons.

Issue #304 wirkt so, als wäre der Autor von der älteren `EditWeatherSection.svelte` ausgegangen. Vor Spec-Erstellung muss geklärt werden:
- Konsolidierung beider Editoren auf eine Komponente?
- Oder: Pro-Metrik-Horizont nur in `WeatherMetricsTab` (Trip-Detail) und parallel im Wizard-Step?

## Related Files

### Frontend — Wetter-Editor (UI)
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Älterer Editor (Wizard + Trip-Edit). Heute: Checkbox + optional Roh/Indikator-Segmented. **Keine Horizons.** |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Neuer Editor (Trip-Detail-Tab, Epic #138). Hat Save-Preset-Dialog, dirty-State, TablePreview. **Keine Horizons.** |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Eine Metrik-Zeile (Checkbox + ModeBtn-Pill). Wäre Ort für 3 Horizon-Pills. |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte` | Gruppen-Container (Temperatur/Wind/…). |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Existierender Dialog „Als Preset speichern" — speichert via `POST /api/metric-presets`. **Schickt nur metric-IDs, keine Horizons.** |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Selektierbare Preset-Zeile. |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Live-Vorschau der gewählten Metriken (Tabelle). |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Modaler Editor (alter Pfad). |
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | `[data-slot]`-Muster (issue_285), Vorbild für HorizonChip. |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Tone-Varianten — könnte für aktiv/inaktiv-Look genutzt werden. |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Variant `outline` (für „Im Profil speichern"). |

### Frontend — Account- und Wizard-Seiten
| Datei | Relevanz |
|---|---|
| `frontend/src/routes/account/+page.svelte` | Konto-Seite. Hat heute eine **Read-only** Card „Wetter-Templates" (Builtins). Issue verlangt verwaltete User-Profile-Sektion. |
| `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte` | Aktueller Wizard-Step 3 (Wegpunkte) — Issue spricht von „Wizard Step 3 Wetter", was so heute **nicht existiert**. Wizard hat 4 Schritte: Profile/Stages/Waypoints/Briefings. |

### Backend — Persistenz
| Datei | Relevanz |
|---|---|
| `internal/model/metric_preset.go` | `MetricPreset` mit `Metrics []string` + `FriendlyIDs []string`. **Keine Horizons.** |
| `internal/handler/metric_preset.go` | GET/POST/DELETE — **kein PATCH** vorhanden. |
| `internal/store/store.go` (L323+) | `LoadMetricPresets`/`SaveMetricPresets` — JSON-Array unter `data/users/{uid}/metric_presets.json`. |
| `cmd/server/main.go` (L128–131) | Route-Registrierung. |
| `internal/model/trip.go` (L76) | `Trip.DisplayConfig map[string]interface{}` — schwach typisiert, akzeptiert beliebige Erweiterungen. Hier landen heute `metrics` (`{metric_id, enabled, use_friendly_format}`). Horizons müssten als zusätzliches Feld pro Metric-Eintrag rein. |
| `internal/handler/weather_config.go` | `PutTripWeatherConfigHandler` — Trip-Speicherung der Display-Config. |

### Specs / Dokumentation
| Datei | Relevanz |
|---|---|
| `docs/specs/ux_redesign_navigation.md` (§„Schritt 3: Wetter-Template") | Ursprünglicher Soll-Entwurf — ASCII-Mockup mit Horizon-Pills. |
| `docs/specs/modules/epic_138_174_178_metriken_ui.md` | Aktuell implementiertes Metric-Editor-System. |
| `docs/specs/modules/issue_285_weather_section_restyle.md` | Brand-Token-Restyle für `EditWeatherSection`. Liefert Segmented `[data-slot]`-Pattern. |

## Existing Patterns

- **`[data-slot]`-Komponenten** (Pill, Btn, Segmented) — neues HorizonChip soll diesem Muster folgen, nicht eigenes CSS.
- **Read-Modify-Write für Trip-Persistenz** (PFLICHT laut CLAUDE.md / BUG-DATALOSS-GR221) — beim Speichern Horizons additiv zum bestehenden `display_config` ergänzen, **niemals** ersetzen.
- **Dirty-State + „Verwerfen"-Button** (in `WeatherMetricsTab`) — als Vorbild für UX.
- **Existing `MetricPreset`-Endpoints** sind die natürliche Heimat für User-Templates — Issue nennt zwar `/api/user/weather-templates`, aber die bestehende Route `/api/metric-presets` deckt 90% ab und sollte erweitert werden statt parallel geführt zu werden (siehe Memory `feedback_consolidate_duplicates.md`).

## Dependencies

- **Upstream (was unser Code nutzt):**
  - `MetricCatalog` aus `/api/metrics` (bleibt unverändert)
  - `MetricPreset`-Storage in `data/users/{uid}/metric_presets.json`
- **Downstream (was unser Code beeinflusst):**
  - **E-Mail-/SMS-Report-Renderer** — wenn Horizons echte Funktion bekommen sollen (Metrik nur an Tag X anzeigen), muss `internal/render/` o.ä. das auswerten. Issue erwähnt das **nicht explizit** — Klärung notwendig: ist Horizon nur UI-Hinweis, oder filtert Backend die Anzeige?
  - **TablePreview** muss Horizon-Spalten visualisieren.
  - **Trip-Wizard Step 3** (wenn Wetter dort einzieht — heute nicht der Fall).

## Existing Specs

- `docs/specs/ux_redesign_navigation.md` — Soll-Konzept (April 2026).
- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — Ist-Zustand des Metric-Editors.
- `docs/specs/modules/issue_285_weather_section_restyle.md` — Token-Restyle, Segmented-Komponente.

## Risks & Considerations

1. **Doppelter Wetter-Editor** (`EditWeatherSection` vs. `WeatherMetricsTab`) — Konsolidierung vs. parallele Pflege. **Klärung mit User vor Phase 3.**
2. **Backend-Wirkung der Horizons unklar.** Issue beschreibt nur das Datenmodell, nicht die Folge. Drei Lesarten:
   - (a) Nur UI-Anzeige: Horizons werden gespeichert, Reports rendern unverändert.
   - (b) Filter: Metrik wird in Tages-Spalte nur ausgegeben wenn Horizon aktiv.
   - (c) Pro-Tag-Konfiguration ersetzt globale Metric-Auswahl. → Klärung Phase 2.
3. **Daten-Schema-Reworks** (CLAUDE.md PFLICHT): Erweiterung `display_config.metrics[]` um `horizons` ist additiv, aber MetricPreset-Schema-Erweiterung ist nicht ganz so trivial — `Metrics []string` muss zu `Metrics []DisplayMetric` o.ä. werden. Backup + Roundtrip-Test Pflicht.
4. **Issue erwähnt einen Wizard-Step „Wetter"** — den gibt es so im 4-Step-Wizard nicht (Schritte sind Profile/Stages/Waypoints/Briefings). Klärung: neuer Step einbauen oder Feature nur in Trip-Detail/-Edit?
5. **`/api/user/weather-templates` vs. existierende `/api/metric-presets`** — neuen parallelen Endpoint-Stamm zu bauen schafft Duplikate. Bestehende Endpoints erweitern statt verdoppeln.
6. **Sprachkonsistenz** (Memory `feedback_terminology_consistency.md`): Issue mixt „Templates" und „Profile". Im Code & UI ist „Preset" / „Profil" etabliert — bei Spec auf eine Bezeichnung festlegen.
7. **LoC-Budget 250** — wird bei vollem Scope (UI + Backend-Modell + neue PATCH-Route + Account-Sektion + Wizard-Integration + Migration) überschritten. Override oder Aufteilung in Sub-Issues planen.
