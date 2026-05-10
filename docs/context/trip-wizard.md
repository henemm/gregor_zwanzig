---
entity_id: context_trip_wizard
type: context
created: 2026-05-09
updated: 2026-05-09
status: phase1_complete
related_issues: [136, 160, 161, 162, 163, 164, 165, 100]
related_epics: [133, 134]
tags: [sveltekit, frontend, wizard, trip-creation, epic-136]
---

# Context: Trip-Wizard (Epic #136)

## Request Summary

User möchte den Trip-Wizard auf `/trips/new` neu bauen — 4 Schritte (Profil/Eckdaten,
GPX-Import, Etappen & Wegpunkte, Briefings & Kanäle) gemäß Design-System aus Epic #133
und passend zum Trip-Cockpit aus Epic #134. Der bestehende Wizard wird ersetzt.

## Epic-Struktur

Epic #136 ist in 6 Sub-Issues zerlegt:

| Issue | Titel | Inhalt |
|-------|-------|--------|
| #160 | Wizard: Shell + 4-Schritt-Stepper | Wrapper-Layout, Stepper-Komponente, Vor/Zurück-Navigation |
| #161 | Step 1: Aktivitätsprofil + Eckdaten | 5 ProfileChips (Trekking/Skitour/Hochtour/Klettersteig/MTB) + Name/Kürzel/Zeitraum |
| #162 | Step 2: GPX-Multi-Upload + Drag-Sort + Pause | Drop-Zone, sortierbare Etappen-Liste, Pausentag, Etappen-Nummerierung (T01…) |
| #163 | Step 3: KI-Waypoints bestätigen | Etappen links, Waypoint-Confirm-UI rechts (Höhenprofil + Bestätigen/Verwerfen) |
| #164 | Step 4: Briefings & Kanäle | Kanal-Toggles, ReportRow, ThresholdRow (Böen, Niederschlag, Gewitter, Schneefallgrenze) |
| #165 | Trip-Vorlagen | Rechte Spalte in Step 2: GR20, Karnischer Höhenweg, Stubaier Höhenweg |

## Bestehender Code (wird ersetzt)

| Datei | Aktuelle Rolle |
|-------|----------------|
| `frontend/src/routes/trips/new/+page.svelte` | Mount-Point (3 Zeilen) — bleibt, ruft neuen Wizard |
| `frontend/src/routes/trips/new/+page.server.ts` | Leerer Loader — bleibt unverändert |
| `frontend/src/lib/components/wizard/TripWizard.svelte` | Alter 4-Step-Container (Route/Etappen/Wetter/Reports) — wird ersetzt |
| `frontend/src/lib/components/wizard/WizardStepper.svelte` | Alte Stepper-Komponente — Referenz, wahrscheinlich neu |
| `frontend/src/lib/components/wizard/WizardStep1Route.svelte` | Trip-Name + GPX-Multi-Upload — Logik (uploadGpx, naturalSort, computeDefaultStartDate) wandert in Step 2 |
| `frontend/src/lib/components/wizard/WizardStep2Stages.svelte` | Stage-CRUD — fließt teilweise in Step 3 ein |
| `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | Display-Config — fließt teilweise in Step 4 ein |
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | Report-Config — fließt in Step 4 ein |

**Auch im Edit-Modus relevant:** `TripWizard.svelte` wird vom `/trips/[id]/edit/+page.svelte` (Read-Path)
verwendet. Edit-Pfad muss beim Refactor nicht zwingend mit umgestellt werden — kann erst danach folgen.

## Verfügbare Atoms (Design-System Lauf B, Epic #133)

| Atom | Pfad | Verwendung im Wizard |
|------|------|----------------------|
| `Btn` | `$lib/components/ui/btn` | Weiter, Zurück, Speichern, Pause einfügen |
| `GCard` | `$lib/components/ui/g-card` | Container für Step-Content, Profil-Chips, Vorlagen-Karten |
| `Pill` | `$lib/components/ui/pill` | Profil-Chip (selektiert: tone="accent"), Etappen-Pills (T01, T02...) |
| `Eyebrow` | `$lib/components/ui/eyebrow` | Step-Titel-Eyebrow ("Schritt 2 von 4") |
| `Dot` | `$lib/components/ui/dot` | Stepper-Done/Pending-Indikator |
| `TopoBg` | `$lib/components/ui/topo` | Optional als Hintergrund auf Profil-Chips |
| `ElevSparkline` | `$lib/components/ui/elev-sparkline` | Step 3: Höhenprofil pro Etappe |

shadcn-Komponenten (`Button`, `Input`, `Label`, `Dialog`, `Card`) sind weiterhin verfügbar — bei Form-Feldern
weiterhin nutzbar (kein Atom-Ersatz für Inputs in Lauf B).

## Datenmodell (Soll & Ist)

### Bestand (Trip Type, frontend/src/lib/types.ts + internal/model/trip.go)

```typescript
Trip {
  id, name,
  stages: Stage[],
  avalanche_regions?, aggregation?, weather_config?, display_config?, report_config?
}
Stage  { id, name, date, waypoints, start_time? }
Waypoint { id, name, lat, lon, elevation_m, time_window? }
```

### Lücken für Wizard-Anforderungen

| Feature im Wizard | Fehlt im Modell? | Hinweis |
|-------------------|-------------------|---------|
| Aktivitätsprofil pro Trip | Nur `aggregation.profile` (string) | Backend hat 4 Werte (`wintersport, wandern, summer_trekking, allgemein`); Wizard verlangt 5 Profile (Trekking/Skitour/Hochtour/Klettersteig/MTB) — Mapping/Erweiterung nötig |
| Trip-Kürzel (Slug, z.B. „GR20") | **fehlt komplett** | Neues Feld in Trip-Modell (FE+BE) |
| Trip-Zeitraum (start_date, end_date) | implizit aus `stages[].date` | Kann derived bleiben oder explizit werden |
| Pausentag | **fehlt komplett** | Stage ohne `waypoints` (oder Flag `is_pause`) — Modellentscheidung |
| Etappen-Nummerierung (T01, T02…) | **fehlt** | Im Wizard generiert; ggf. nur in UI, oder als `stage.label` persistieren |
| KI-Vorschläge für Wegpunkte (Wetterscheiden) | **fehlt** | Status-Feld auf Waypoint (proposed/confirmed/rejected) oder separater AI-Vorschlag-Endpoint |
| Briefing-Konfiguration mit Schwellen (Böen, Niederschlag, Gewitter, Schneefall) | teils in `report_config` | Schwellenwerte/Alert-Konfiguration ist Epic #139 — Step 4 setzt nur Grundgerüst |
| Trip-Vorlagen (GR20, KHW, Stubai) | **fehlt** | Statische JSONs im Repo oder gehärteter Endpoint |

### ActivityProfile — Konflikt zwischen Spec und Wizard

`docs/specs/modules/activity_profile.md` definiert 4 kanonische Werte. Epic #136 verlangt 5
neue Profil-Typen — keiner davon deckungsgleich. Optionen:

1. **Backend erweitern** auf 5 oder mehr Werte (FE-Chips → Enum-Werte 1:1).
2. **Frontend-Mapping** Chips → bestehende 4 Werte (Skitour/Hochtour → Wintersport, Trekking → Summer-Trekking, Klettersteig/MTB → Allgemein).
3. **Beide Felder**: Trip hat `profile` (Aggregations-Semantik, 4 Werte) UND `activity` (UI-Semantik, 5+ Werte).

Diese Entscheidung gehört in Phase 2 (Analyse). Der Tech-Lead-Vorschlag
ist Option 1 mit sauberer Erweiterung des Enums (saubere Single-Source-of-Truth, Spec §A8 sieht
genau diesen Fall vor: Whitelist-Erweiterung in `subscription.go` + Spec-Update).

## Existierende Specs

| Spec | Bezug |
|------|-------|
| `docs/specs/modules/activity_profile.md` | Kanonisches Enum (4 Werte) — Erweiterung dokumentieren |
| `docs/specs/modules/epic_133_design_system_lauf_a.md` | Tokens, Schriften (Lauf A) |
| `docs/specs/modules/epic_133_design_system_lauf_b.md` | Atoms (Lauf B) — vollständig deployed |
| `docs/specs/modules/epic_134_startseite_cockpit.md` | Cockpit-Pattern, `_cockpit/`-Ordner, Safari-Best-Practices |
| `docs/specs/modules/gpx_multi_import.md` | Multi-Upload + naturalSort — Logik bereits in `WizardStep1Route.svelte` |
| `docs/specs/modules/trip_wizard_w1.md` / `_w2.md` / `_w3.md` | **Alter** Wizard — historische Referenz, nicht 1:1 übernehmen |
| `docs/specs/modules/gpx_parser.md` | GPX-Parser-Verhalten |
| `docs/specs/modules/elevation_analysis.md` | Möglicherweise Basis für KI-Waypoint-Vorschläge (Step 3) |
| `docs/specs/modules/hybrid_segmentation.md` | Segmentierungs-Logik — relevant für Wetterscheiden-Erkennung |

## API-Endpoints (vorhanden)

| Endpoint | Status | Verwendung |
|----------|--------|-----------|
| `POST /api/trips` | vorhanden | Trip anlegen (Step 4 → Speichern) |
| `PUT /api/trips/{id}` | vorhanden | Trip ändern (Edit-Pfad) |
| `GET /api/trips` | vorhanden | Trip-Liste |
| `POST /api/gpx/upload` (über `uploadGpx()`) | vorhanden | GPX → Stage |
| KI-Waypoints / Wetterscheiden | **fehlt** | Neuer Endpoint nötig (Step 3) — vermutlich Backend-Logik in Python |
| Trip-Vorlagen | **fehlt** | Statisches JSON oder Endpoint |

## Phase-2-Funde (Recherche-Agents)

### KI-Waypoint-Vorschläge — **Backend ist fertig**

- `src/core/elevation_analysis.py` erkennt GIPFEL/TAL/PASS aus GPX-Höhenprofilen (Sliding-Window)
- `src/core/hybrid_segmentation.py` verschiebt Segmentgrenzen an erkannte Wetterscheiden (±20 Min Constraint)
- `compute_full_segmentation()` in `src/web/pages/gpx_upload.py:66-86` ist die Pipeline: parse → segments → waypoints → optimize
- Endpoint: `POST /api/gpx/parse` (Python FastAPI) liefert bereits Segments + Waypoint-Vorschläge
- Tests: `tests/unit/test_hybrid_segmentation.py`, `tests/unit/test_elevation_analysis.py`
- **Konsequenz für Step 3:** Frontend kann Vorschläge direkt rendern — keine neue Backend-Arbeit nötig

### Vorlagen-Daten (Issue #165)

- **KHW (Karnischer Höhenweg):** komplett — 13 GPX-Stages in `data/users/default/gpx/KHW_*` + 3 Test-Fixtures in `frontend/e2e/fixtures/`
- **Stubaier Höhenweg:** 2 JSON-Templates in `examples/stubai_*.json` (Skitour-Aggregation)
- **GR20 (Korsika):** **fehlt** — nur Golden-Outputs für SMS/Email-Tests, keine GPX-Files
- **Konsequenz für Step 5:** Sub-Issue #165 ist später realisierbar; GR20-Daten müssen extern beschafft werden (oder Skope anpassen)

### Recycling-Potenzial alter Wizard

| Datei | Wiederverwendbar | Empfehlung |
|-------|------------------|------------|
| `WizardStepper.svelte` | 100% | behalten — generisch |
| `TripWizard.svelte` | 60% | Save-Logik & Navigations-Skelett übernehmen |
| `WizardStep1Route.svelte` | 20% | GPX-Logik (`handleFiles`, `commitPending`, `addManualStage`) wandert in neuen Step 2 |
| `WizardStep2Stages.svelte` | 40% | Stage-CRUD extrahieren als `wizardHelpers.ts` |
| `WizardStep3Weather.svelte` | 0% | löschen — Wetter-Metriken ist eigenes Epic #138 |
| `WizardStep4ReportConfig.svelte` | 0% | komplett neu — Schema unterscheidet sich |

**Wichtig:** `frontend/src/lib/components/edit/TripEditView.svelte` importiert ALLE vier alten Step-Komponenten als Accordion. Wenn die alten gelöscht werden, bricht der Edit-Pfad. Das ist eine Querbeziehung, die in der Strategie berücksichtigt werden muss.

## Risiken & offene Fragen für Phase 2

1. **Big-Bang vs. inkrementell:** Der Wizard ist ein einzelnes Frontend-Feature aus Sicht des
   Users, aber 6 Sub-Issues. Empfehlung: pro Sub-Issue ein eigener TDD-Lauf, beginnend mit
   #160 (Shell). Master-Spec auf Epic-Ebene, Sub-Specs pro Issue.

2. **Bestehender Wizard:** Während des Refactors gleichzeitig nutzbar halten oder in einem PR
   ersetzen? Empfehlung: ersetzen, sobald Step 1+2 äquivalent sind. Edit-Pfad
   (`/trips/[id]/edit`) verweist auf den alten `TripWizard` — separates Issue für Edit-Refactor.

3. **Aktivitätsprofil-Erweiterung:** Backend-Enum von 4 auf 5+ Werte erweitern (Ja/Nein und
   welche Werte) — Tech-Lead-Empfehlung an User vor Spec.

4. **KI-Waypoints (Step 3):** Backend-seitige Vorschlagslogik existiert vermutlich noch nicht
   als Endpoint — entweder neuer Service oder Step 3 zunächst mit manueller Waypoint-Liste
   (KI-Vorschläge als Folge-Issue).

5. **Trip-Vorlagen:** Drei konkrete Routen (GR20, KHW, Stubai) — wo liegen die GPX-Files?
   Wahrscheinlich in einem öffentlichen Static-Ordner oder als Repo-Fixtures.

6. **Pausentag-Modellierung:** Stage ohne Wegpunkte vs. Flag `is_rest_day` vs. eigener Typ.
   Bestehender Code (`addManualStage`) erlaubt schon leere Stages — Lösung mit Flag wäre
   unaufdringlich.

7. **Bug #100 schließen:** Der neue Wizard adressiert die alten Verwirrungen (Naming, Manuell-
   anlegen ohne Feedback) implizit. Issue #100 nach erfolgreicher Implementation schließen
   (mit Verweis auf Epic #136).

8. **Safari-Kompatibilität:** Factory Pattern für `onclick` (siehe CLAUDE.md, NiceGUI-Hinweis
   gilt nicht — SvelteKit nutzt benannte Funktionen wie im Cockpit-Spec, das reicht).

## Nächster Schritt

Phase 2 — Analyse: Tech-Lead-Empfehlungen formulieren, Sub-Issue-Reihenfolge festlegen,
Modell-Entscheidungen treffen, dann pro Sub-Issue einen eigenen Spec-Lauf.
