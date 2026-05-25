# Context: #361 — Metriken-Editor Spalten/Detail/Aus + Reihenfolge + Multi-Kanal-Vorschau

## Request Summary

Frontend-Teil von Epic #331 (Teil 2; Teil 1 = #360 Backend, LIVE). Der Wetter-Metriken-Editor
bekommt pro Metrik die Zuordnung „eigene Spalte / Detail-Wert / aus" plus Reihenfolge, und
eine Live-Vorschau in allen 4 Kanälen (Email/Telegram/Signal/SMS) mit Warn-Badge bei
Spalten-Überlauf. Speichert über das bestehende Trip-Save. Vorschau serverseitig über den
#360-Renderer (kein JS-Duplikat).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Host des Editors; speichert via `PUT /api/trips/{id}/weather-config` (Z. 233/237: spreizt `display_config`, ergänzt `metrics`) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Pure Editor-Logik: `enabledMap`+`friendlyMap`, `INDICATOR_MAP` (=„mode"), `CATEGORY_ORDER`, `selectTableColumns` (nimmt ALLE aktiven → muss bucket/order + Kanal-Limit lernen) |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte`, `MetricCheckbox.svelte`, `TablePreview.svelte`, `SavePresetDialog.svelte`, `PresetRow.svelte` | Bestehende Editor-Bausteine (Epic #138 #174–178) |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte`, `frontend/src/lib/components/WeatherConfigDialog.svelte` | **#345**-Konsolidierungskandidaten — Doppelung, mit #361 zusammen denken |
| `frontend/src/lib/components/preview/EmailIframe.svelte`, `SmsPhoneFrame.svelte`, `previewHelpers.ts` | Vorschau-Fundament; `buildPreviewUrl` kennt nur `'email' \| 'sms'` → um `'signal' \| 'telegram'` erweitern |
| `frontend/src/lib/types.ts` | `WeatherConfigMetric`/`DisplayConfig` = `{metric_id, enabled, use_friendly_format?, horizons?}` → **+`bucket`/`order`** (additiv) |
| `api/routers/preview.py` | Python-Vorschau: nur `email` + `sms`. **+`signal`/`telegram`** ergänzen, die `render_narrow` (#360) nutzen |
| `internal/handler/preview_proxy.go`, `cmd/server/main.go:131-132` | Go-Proxy `PreviewProxyHandler(pythonURL, channel)` für email/sms → Routen für signal/telegram ergänzen |
| `src/output/renderers/channel_layout.py`, `narrow.py` (#360) | Backend-Renderer + `CHANNEL_LIMITS` — Quelle der Wahrheit für die Vorschau |
| `src/app/models.py` `MetricConfig`, `src/app/loader.py` | bucket/order existieren backendseitig bereits (#360), inkl. Persistenz + Legacy-Migration |

## Existing Patterns

- **Editor-State:** zwei `Record<id, bool>`-Maps (`enabledMap`, `friendlyMap`) + dirty-Snapshot. #361 ergänzt Bucket-Zuordnung (primary/secondary) + Reihenfolge — entweder dritte Map `bucketMap` + Order-Array, oder Umstieg auf Listen-Modell. Sorgsam: bestehende Maps/dirty-Logik nicht unnötig brechen.
- **„mode" = `use_friendly_format`**, UI-Steuerung über `INDICATOR_MAP` (bereits vorhanden). „aus" = `enabled=false`. (Konsistent mit #360.)
- **Vorschau:** Go-Proxy reicht an Python weiter, Session-Cookie + user_id serverseitig. Char-Count-Status für SMS in `previewHelpers`.
- **Save:** Read-Modify-Write — Tab spreizt bestehendes `display_config` und ergänzt Felder (Muster wie #180/#259). Go-`/weather-config`-Handler + Python-Loader müssen bucket/order durchreichen (Loader tut es schon).

## Dependencies

- **Upstream (was #361 nutzt):** #360-Renderer (`render_for_channel`/`render_narrow`/`CHANNEL_LIMITS`), bestehende Editor-Bausteine, preview_service (Epic #140), `INDICATOR_MAP`.
- **Downstream (was #361 ändert):** `display_config.metrics[].{bucket,order}` (additiv), neue Preview-Endpoints (signal/telegram), `buildPreviewUrl`-Typ, ggf. konsolidierter Editor (#345).

## Existing Specs

- `docs/specs/modules/issue_360_signal_channel_renderer.md` — Backend-Renderer (Teil 1, LIVE)
- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — bestehender Metriken-Editor
- `docs/specs/modules/preview_service.md`, `issue_189_preview_tab_integration.md` — Vorschau-Fundament
- `docs/specs/modules/issue_285_weather_section_restyle.md` — EditWeatherSection/WeatherConfigDialog
- #345-Issue — Editor-Konsolidierung (zu koordinieren)

## Design Reference (beschafft 2026-05-24)

Design-Handoff war doch zugänglich (gzip-Archiv via `curl`, nicht `WebFetch`). Relevante
Artboards liegen jetzt im Repo unter `docs/design/epic_331_output_layout/`:

- `screen-metrics-editor.jsx` (Desktop, 796 Z.) — **der zentrale Editor-Screen**.
- `screen-metrics-editor-mobile.jsx`, `screen-signal-cols-mobile.jsx` — Mobile.
- `screen-output-preview.jsx` (+mobile) — Multi-Kanal-Vorschau-Layout.
- `signal-layout.jsx` + `Gregor 20 - Signal Layout.html` — Signal-Constraint-Begründung (OK/Broken/Fixed-Demo, 6-Spalten-Limit, Bubble ≈ 272 px).

**Editor-Struktur (Desktop, aus `screen-metrics-editor.jsx`):**
- Breadcrumb + dirty-Pill „Ungespeicherte Änderungen" + Verwerfen/Speichern.
- H1 „Welche Werte gehen in das Briefing — und wie?" + Intro + „Wie funktioniert das genau?"-Link → About-Dialog (Kanal-Tabelle).
- 2-Spalten-Grid `300px 1fr`: links **Preset-Liste** + „Als Preset speichern"; rechts gestapelt:
  1. **Bucket „Spalten"** (primary): sortierbare Zeilen, je Zeile Index · Label+Einheit+Kürzel · Roh/Skala-Toggle (nur wenn `INDICATOR_MAP`) · `→ Detail`/`✕` · ↑↓. `ChannelLimitMarkers` (Badges „Signal 7/6", „Telegram 7/8" — färben sich bei Überschreitung). Trenner an Position 6: „↓ ab hier bei Signal automatisch als Detail-Zeile".
  2. **Bucket „Detail-Werte"** (secondary): analog, `↑ Spalte`/`✕`.
  3. **`ChannelPreviewBlock`**: 4 Karten (Email/Telegram/Signal/SMS), Mono-Tabelle + Detail-Zeile + Badge „⚠ N Spalten verschoben".
  4. **„Nicht im Briefing"** (off, eingeklappt): nach Gruppe, `+ Spalte`/`+ Detail`.
- UI-Sprache (verbindlich): „Spalte" / „Detail" / „Aus" / „Reihenfolge" / „Roh / Skala".
- `applyChannel(primary, secondary, maxCols)` + `autoAssign` (Top 6 nach prio → primary) — identisch zum Backend gedacht.

## Abgleichpunkt #360 ↔ Design — GEKLÄRT (kein Backend-Umbau)

Geprüft am maßgeblichen Signal-Layout-Artboard (`signal-layout.jsx::OverflowTableOk`):
Header der „OK · 6 Spalten"-Tabelle ist `hh   °C  W  G  R%  ☁` = **6 Spalten INKLUSIVE
Uhrzeit** (5 Werte + Uhrzeit). „Broken · 9 Spalten" = `hh °C gef W G R% Cl Sun Sich`
(Uhrzeit + 8). ⇒ Das Design zählt die Uhrzeit mit — **identisch zu #360** (`max_table_cols=6`
inkl. Zeit ⇒ Signal-Demo `Zt T W G P% R`). Der Widerspruch lag nur in der `applyChannel`/
`autoAssign`-Hilfsfunktion des **Editor-Mockups** (zählt 6 Metrik-Spalten) — das ist eine
Mockup-Ungenauigkeit, NICHT der verbindliche Renderer.

**Konsequenz:** #360 bleibt unverändert. Der Editor wird an die Backend-Definition angeglichen:
Signal-Spalten-Budget = **5 wählbare Metrik-Spalten** (+ feste Uhrzeit = 6), Telegram = **7**
(+ Uhrzeit = 8), Email ∞, SMS 0. `ChannelLimitMarkers` + Auto-Verteilung im Frontend zählen
die Uhrzeit NICHT als wählbar (sie ist immer Spalte 0). Vorschau läuft serverseitig über
#360-`render_narrow` ⇒ zeigt automatisch die Backend-Realität.

## Risks & Considerations

- **Design-Blocker AUFGELÖST** (s.o.) — Artboards liegen im Repo.
- **#345-Overlap:** Drei Orte konfigurieren Wetter-Metriken (WeatherMetricsTab, EditWeatherSection, WeatherConfigDialog). Bucket/Order-Editor nur EINMAL bauen (konsolidiert), sonst Drift.
- **Keine Renderer-Duplikation:** Multi-Kanal-Vorschau MUSS serverseitig über #360-Renderer laufen (neue signal/telegram-Preview-Endpoints), nicht die Layout-Logik in JS nachbauen — sonst zwei Quellen der Wahrheit.
- **Schema additiv:** bucket/order nur ergänzen, Bestandsdaten erhalten (Loader-Migration #360 deckt das ab; Frontend darf beim Save keine Felder verlieren).
- **Pflicht-Spalte Zeit:** im Backend implizit Spalte 0 — Frontend-„hour als primary[0]" entfällt als eigener Metrik-Eintrag (kein `hour`-Metrik im Katalog).
- **Mobile-Adaption** (Bucket-Cards + Sheet) — Design nötig.
