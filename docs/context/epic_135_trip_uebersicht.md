# Context: Epic #135 — Trip-Übersicht Haupt-Bühne

## Request Summary

Epic #135 soll die Trip-Detail-Seite (`/trips/[id]`) als vollständige Haupt-Bühne mit Tab-Navigation, Hero, linker und rechter Spalte liefern. Der Kern des Epics ist bereits vollständig implementiert. Offen sind drei Follow-up-Issues, von denen #202 (Region-Feld) der sinnvollste nächste Schritt ist.

---

## Implementierungsstand

**Alle 5 Steps von Epic #135 sind bereits umgesetzt:**

| Step | Beschreibung | Komponente | Status |
|------|-------------|-----------|--------|
| Step 1 | Tab-Navigation (6 Tabs + Hash-Sync) | `TripTabs.svelte` | ✅ fertig |
| Step 2 | Breadcrumb + Status-Badge + Pause/Archivieren | `TripHeader.svelte` | ✅ fertig |
| Step 3 | Trip-Hero (Name, Zeitraum, 3 Stat-Kacheln) | `TripHero.svelte` | ✅ fertig |
| Step 4 | Linke Spalte: SVG-Profil + Stage-Row-Liste | `TripOverview.svelte`, `FullProfile.svelte`, `StageList.svelte`, `StageDetailRow.svelte` | ✅ fertig |
| Step 5 | Rechte Spalte: 4 Vorschau-Karten | `BriefingPreviewCard`, `WeatherMetricsPreviewCard`, `AlertsPreviewCard`, `PreviewCard` | ✅ fertig |

---

## Offene Follow-up Issues

### #202 — Region-Feld einführen (Priorität: mittel) ← EMPFEHLUNG

**Was fehlt:**
- Backend (`internal/model/trip.go`): `Region string \`json:"region,omitempty"\`` in `Trip`-Struct fehlt
- Frontend (`src/lib/types.ts`): `region?: string` in `Trip`-Interface fehlt (in `Location` ist es schon da)
- Frontend `TripHero.svelte`: Region unter dem Titel anzeigen wenn gesetzt
- Frontend `Step1Profile.svelte` (Wizard): Optional-Feld "Region" (Freitext, max 50 Zeichen)
- Frontend `wizardState.svelte.ts`: `region = $state('')` + in `toTripPayload()` einbauen

**Keine Abhängigkeiten** — vollständig in sich, kein anderes Feature blockiert/geblockt.

### #203 — Stage-Row: Wetter-Summary + Risiko-Pill (Priorität: mittel, komplex)

Braucht Backend-Endpoint-Erweiterung und hängt von Alert-Konfigurator (Epic #139) ab. Nicht für jetzt.

### #206 — weather_config.preset_name (Priorität: low)

Backend + Frontend, aber low priority.

---

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go` | Trip-Struct → `Region` Feld hinzufügen |
| `internal/store/store.go` | JSON-Persistenz → prüfen ob neues Feld automatisch durchläuft |
| `frontend/src/lib/types.ts` | `Trip`-Interface → `region?: string` |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | Region unterhalb des Titels anzeigen |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Neues Eingabefeld "Region" |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `region`-State + `toTripPayload()` |
| `docs/specs/modules/epic_135_step3_trip_hero.md` | Step-3-Spec — wird um Region erweitert |

## Existing Patterns

- **Optionale Felder im Backend:** `shortcode`, `activity` sind `omitempty` — gleicher Ansatz für `region`
- **Wizard-State-Felder:** `shortcode = $state('')` in `wizardState.svelte.ts`, in `toTripPayload()` mit `trim()`-Guard eingesetzt — gleicher Ansatz für `region`
- **Step1Profile Inputs:** 3 Felder (Name Pflicht, Kürzel optional, Startdatum Pflicht) — Region wird als 4. optionales Feld nach Kürzel eingefügt, gleicher CSS-Ansatz
- **TripHero Stat-Tiles:** `$derived` + Conditional-Rendering mit `{#if dateRange}` — Region analog

## Dependencies

- **Upstream:** Backend `model.Trip` → Go-Struct → JSON-API → Frontend `types.ts` → Komponenten
- **Downstream:** Nichts hängt von `region` ab (neues Feld)

## Risks & Considerations

- **Read-Modify-Write Pflicht (CLAUDE.md):** Bei Edit-Handlern das bestehende Trip-Objekt laden und nur `region` setzen — nicht das ganze Objekt aus dem UI-State neu bauen
- **Persistenz:** Store liest/schreibt JSON generisch — neues Feld wird automatisch persistiert, solange der Go-Struct die json-Tags hat
- **Wizard vs. Edit-View:** Region kommt in Step1Profile (Wizard) und möglicherweise auch in der Edit-View (`TripEditView.svelte`) — Edit-View-Scope abhängig von Issue-Definition (Issue #202 nennt es nicht explizit, nur Wizard + Hero)
- **Längenvalidierung max 50:** Frontend-seitig via `maxlength="50"` reicht; Backend keine Pflicht (konsistent mit shortcode-Ansatz)
