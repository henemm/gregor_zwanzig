# Context: Issue #455 — Compare-Hauptbühne Frontend

## Request Summary

Der Haupt-Screen `/compare` soll in ein 3-Spalten-Layout umgebaut werden: linke Locations-Rail (240px), mittlerer Hauptbereich (flex) mit Compare-Preset, Empfehlungs-Banner, Vergleichs-Matrix und Stunden-Verlauf, sowie rechtes Sidepanel (320px) mit Auto-Briefings (Subscriptions).

## Status der Abhängigkeiten

| Issue | Titel | Status | Tatsächlicher Stand |
|-------|-------|--------|---------------------|
| #453 | Locations-Verwaltung (Rail-Komponente) | OPEN | `LocationsRail.svelte` existiert bereits (aus #249/#301) |
| #454 | Compare-Engine Backend | OPEN | `internal/compare/engine.go` + `POST /api/compare/run` registriert in `main.go:136` |

**Wichtig:** Die Implementierungen der Abhängigkeiten existieren bereits im Code, sind aber als Issues noch offen (wahrscheinlich neu geplante Sub-Issues von Epic #246). Effektiv kann #455 auf vorhandene Basis aufbauen.

## Vorhandene Komponenten (können direkt verwendet werden)

| Datei | Quelle | Zustand |
|-------|--------|---------|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | #249/#301 | ✓ vollständig, inkl. Gruppen, Multi-Select, Profil-Chips |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | #251 | ✓ vollständig (Datum, Von/Bis, Profil, Forecast-Horizont) |
| `frontend/src/lib/components/compare/RecommendationBanner.svelte` | #251 | ✓ vollständig (Winner-Score, Tags, Pill) |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | #251 | ✓ vollständig (Profil-Metriken, Best-Value grün, Mini-Bars) |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | #251 | ✓ vollständig (Top-3, Stundenwerte) |
| `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | #301 | ✓ für Sidepanel verwendbar (zeigt Subscriptions als Kachelraster) |
| `frontend/src/lib/components/compare/CompareList.svelte` | #439 | ✓ aktuell in /compare eingebaut (wird durch #455 als Sidepanel-Alternative) |

## Was #455 tatsächlich bauen muss

Die aktuelle `/compare/+page.svelte` ist 49 Zeilen und zeigt NUR die CompareList (Subscription-Übersicht). Es fehlt der vollständige 3-Spalten-Interaktions-Screen.

**Neue Bausteine:**
1. `/compare/+page.svelte` umbau auf 3-Spalten-Layout
2. Interaktions-Logik: Locations auswählen → `POST /api/compare/run` → Ergebnisse anzeigen
3. Leerer Zustand (< 2 Orte): Hinweis-Banner statt Matrix (AC-5)
4. `/compare/+page.server.ts` erweitern (bereits lädt locations + subscriptions + groups — passt)

**Keine neuen Komponenten nötig** — alle 5 Hauptkomponenten existieren, nur die Page-Orchestrierung fehlt.

## Route-Entscheidung

Das 3-Spalten-Layout ERSETZT die aktuelle `/compare`-Seite. Die Subscription-Übersicht (CompareList/AutoReportsOverview) wandert ins rechte Sidepanel. Route bleibt `/compare`.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/compare/+page.svelte` | Wird komplett umgebaut (49 → ~180 LoC) |
| `frontend/src/routes/compare/+page.server.ts` | Lädt bereits locations+subscriptions+groups — passt |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Linke Spalte |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | Mitte: Kopf |
| `frontend/src/lib/components/compare/RecommendationBanner.svelte` | Mitte: Winner-Banner |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | Mitte: Matrix |
| `frontend/src/lib/components/compare/HourlyMatrix.svelte` | Mitte: Stunden-Verlauf |
| `frontend/src/lib/components/compare/AutoReportsOverview.svelte` | Rechte Spalte (Sidepanel) |
| `frontend/src/lib/types.ts` | CompareRow, CompareResult, CompareWinner, CompareMetrics |
| `internal/compare/types.go` | Backend CompareRequest/CompareResult |
| `internal/handler/compare_run.go` | POST /api/compare/run Handler |

## API-Schnittstelle

```
POST /api/compare/run
Body: { location_ids: string[], date: string, profile: "WINTERSPORT"|"ALPINE_TOURING"|"SUMMER_TREKKING"|"ALLGEMEIN" }
Response: CompareResult { rows: CompareRow[], winner?: CompareWinner, hourly: Record<string, ForecastDataPoint[]> }
```

Endpoint ist bereits registriert (`main.go:136`). Engine ist vollständig implementiert.

## Design-Referenz

`claude-code-handoff/soll-audit-2026-05-27/handoff-5/gregor-zwanzig/project/screen-compare.jsx`

Zeigt:
- `CompareLocationsRail` (links, 240px, gruppiert, suchbar, Multi-Select mit Checkboxen)
- `CompareField`-Zeile (Settings-Card: Datum, Von, Bis, Forecast, Profil)
- `RecommendationBanner` (Winner mit Score + Tags)
- `CompareMatrix` (Tabelle Metriken × Orte, Best-Value grün, MiniBar)
- `HourlyMatrix` (Top-3 Stunden-Verlauf)
- Rechtes Sidepanel: Subscriptions-Liste + Letzter-Versand-Card

## Abhängigkeiten

- **Upstream:** `POST /api/compare/run` (Go-Backend, bereits vorhanden), `GET /api/locations` (vorhanden), `GET /api/subscriptions` (vorhanden), `GET /api/groups` (vorhanden)
- **Downstream:** Keine weiteren Frontend-Features abhängig von dieser Page

## Risiken & Überlegungen

1. **Route-Konflikt:** Aktuell ist `/compare` die Subscription-Übersicht (#439). Umbau bedeutet CompareList verschwindet als Standalone — sie wandert ins Sidepanel. Kein Rückschritt, da alle Subscription-Funktionen (Toggle, Löschen, Neu) weiter über Wizard/Edit erreichbar.
2. **#453/#454 formal noch offen:** Practical kein Blocker da Implementierungen vorhanden; koordination mit dem User nötig.
3. **LoC-Limit:** Page-Orchestrierung ~180 LoC; alle Komponenten fertig. Bleibe unter 250-Limit.
4. **Leerer Zustand:** AC-5 verlangt Hinweis-Banner wenn < 2 Orte ausgewählt — statt leerer Matrix.
5. **Profil-Wechsel:** AC-4 verlangt reaktiven Update ohne Seiten-Reload — `$derived`-Logik in der Page.
