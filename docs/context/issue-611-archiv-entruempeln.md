# Context: Issue #611 — Archiv entrümpeln (reines Archiv für Trips + Vergleiche)

## Request Summary
Die Archiv-Seite hat eine nie spezifizierte Forecast-Analytik-Schicht (Accuracy-%, `AccuracyBar`, „Was passiert ist", Summen-Statistik). Diese soll komplett raus; stattdessen ein reines Archiv für **zwei** Objekttypen (Trips + Orts-Vergleiche) mit genau zwei Aktionen pro Eintrag: **Wieder aktivieren** und **Löschen**. Maßgeblich ist `claude-code-handoff/current/jsx/screen-archive.jsx`.

## Kanonisches Mockup (Soll = finaler Code)
- `claude-code-handoff/current/jsx/screen-archive.jsx` — 1:1-Quelle (Epic #575)
- `claude-code-handoff/current/soll/H-archive.png` — Soll-Bild
- Tabellen-Grid: `2fr 1fr 1fr auto` (Name+Tag · Umfang · Archiviert · Aktionen)
- Filter-Pills `Alle · Trips · Vergleiche` mit Count-Badges (ersetzen Sortier-Tabs)
- Typ-Tag: Pill mono uppercase; Vergleich = grün (#3d6b3a), Trip = neutral
- Aktionen: `Wieder aktivieren` (Btn ghost, reactivate-Icon) + `Löschen` (danger, trash, Confirm)
- Footer: „N von M Einträgen · Trips auto-archiviert nach Trip-Ende"

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/archiv/+page.svelte` | Komplett-Rewrite zur JSX-Vorlage; Analytik raus |
| `frontend/src/routes/archiv/+page.server.ts` | Lädt aktuell nur Trips + archive/stats; muss zusätzlich archivierte Vergleiche laden, stats entfernen |
| `frontend/src/routes/archiv/archiveHelpers.ts` | `formatEventSummary` wird obsolet; ggf. neue Typ-Merge-Helfer |
| `frontend/src/routes/archiv/issue_388.test.ts` | Prüft AccuracyBar/Stats → muss angepasst/ersetzt werden |
| `frontend/src/routes/archiv/issue_559_archiv_summary.test.ts` | Prüft „Was passiert ist"-Summary → obsolet |
| `frontend/src/lib/types.ts:231-253` | Trip-Typ: `accuracy_pct/headline/briefings_count/alerts_count` entfernen |
| `internal/model/trip.go:73-95` | Backend-Felder #583 entfernen (AccuracyPct/Headline/BriefingsCount/AlertsCount) |
| `internal/model/compare_preset.go:13-27` | **Kein `archived_at`** → Feld `ArchivedAt *time.Time` ergänzen |
| `internal/handler/compare_preset.go` | Delete existiert (224); State-/Archive-PATCH fehlt |
| `internal/handler/trip.go:262` | `UpdateTripStateHandler` (archive+reaktivieren) — existiert ✓ |
| `internal/handler/trip.go:388` | `DeleteTripHandler` — existiert ✓ |
| `internal/handler/archive_stats.go` | `/api/archive/stats` wird obsolet für Archiv |
| `frontend/src/routes/compare/+page.svelte` | Entry-Point: „Archivieren"-Aktion für Vergleiche (damit sie ins Archiv wandern) |

## Bestehende Backend-Endpoints (vorhanden)
- Trip archivieren/reaktivieren: `PATCH /api/trips/{id}/state` `{archived: true|false}` (read-modify-write, schonend)
- Trip löschen: `DELETE /api/trips/{id}`
- Vergleich löschen: `DELETE /api/compare/presets/{id}`
- Vergleiche listen: `GET /api/compare/presets`

## Lücken für #611
1. **Vergleiche haben keinen Archiv-Zustand** — `ComparePreset.ArchivedAt` fehlt; kein State-Endpoint; keine Archivier-Aktion auf der Compare-Seite. Ohne das kann das Archiv nie einen Vergleich enthalten (AC „beide Typen").
2. **Frontend-Buttons leer** — Trash-Button (Zeile 240) und kein Reaktivieren-Button im Archiv.
3. **Analytik-Felder** (#583) noch im Trip-Model + Frontend-Typ + Seed.

## Dependencies
- Upstream: `gz_session`-Cookie, `GZ_API_BASE`, Go-Store (`data/users/{uid}/trips/`, `compare_presets.json`)
- Downstream: Compare-Seite (Reaktivieren-Ziel), Trips-Seite (Reaktivieren-Ziel)

## Schema-Touch (CLAUDE.md Daten-Schema-Regel!)
- `internal/model/trip.go` und `compare_preset.go` sind schema-relevant → `data_schema_backup.py`-Hook erstellt Pre-Snapshot.
- Entfernte Trip-Felder sind optionale Pointer (`*int`, `string`) → Removal verlustfrei für Bestandsdaten (keine genutzten Nutzdaten).
- Neues `ArchivedAt *time.Time` auf ComparePreset ist additiv (omitempty) → bestehende `compare_presets.json` bleiben gültig.

## Risks & Considerations
- **Scope/LoC:** Frontend-Rewrite + Backend-Compare-Archiv + Feld-Cleanup + Tests > 250 LoC-Softlimit → ggf. splitten statt LoC-Override (Memory-Regel).
- **Design-Fidelity-Gate** (#603): Pixel-Diff gegen `H-archive.png` blockt Issue-Close. Inline-Styles 1:1 aus JSX kopieren.
- **Bestehende Tests** (issue_388, issue_559) prüfen die jetzt zu entfernende Analytik → müssen mit-aktualisiert werden, sonst rot.
- **Reaktivieren-Override:** Alte PO-Notiz „Trip kann NICHT zurück" ist durch #611 explizit aufgehoben (PO-Override 2026-06-05).
