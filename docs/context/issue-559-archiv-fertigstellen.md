# Context: Issue #559 — Archiv-Seite fertigstellen

## Request Summary

Die Archiv-Seite (`/archiv`) hat drei nicht verdrahtete Funktionen: den „Briefing-Verlauf öffnen"-Button, den „Als Vorlage neu anlegen"-Button und die Spalte „Was passiert ist" zeigt nur `—`. Alle drei sollen fertiggestellt werden.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/archiv/+page.svelte` | Hauptseite — alle drei Buttons/Spalten sind hier, aber ohne Handler |
| `frontend/src/routes/archiv/+page.server.ts` | Lädt `trips` + `archiveStats` (briefings/alerts per tripId) |
| `frontend/src/routes/archiv/archiveHelpers.ts` | Hilfsfunktionen für Archiv-Logik |
| `frontend/src/routes/trips/new/+page.svelte` | Wizard-Startseite — soll Vorlage-Daten annehmen |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | WizardState-Klasse — alle Felder für Vorlage vorhanden |
| `internal/store/store.go` | `LoadBriefingLog()`, `BriefingCountByTrip()`, `AlertCountByTrip()` |
| `internal/handler/archive_stats.go` | `GET /api/archive/stats` — Aggregat-Counts, kein Detail |
| `internal/model/trip.go` | Trip-Modell mit allen Konfigurationsfeldern |
| `cmd/server/main.go` | API-Router — hier wird der neue Endpoint registriert |

## Existing Patterns

- **Briefing-Log-Zugriff:** `store.WithUser(userID).LoadBriefingLog()` → `[]BriefingLogEntry{TripID, Kind, SentAt, Channels}`. Bereits genutzt in `archive_stats.go` und `cockpit.go`.
- **Handler-Registrierung:** `r.Get("/api/...", handler.XyzHandler(s))` in `cmd/server/main.go`. Pattern vollständig etabliert.
- **Wizard vorausfüllen:** `WizardState` hat `stages`, `activity`, `briefings`, `alertRules`, `weatherMetrics`, `channelLayouts`. Felder können nach Konstruktion gesetzt werden. Übergabe via URL-Query-Param `?from={tripId}` und `+page.server.ts`-Load.
- **Archiv-Stats:** `archiveStats.briefings[trip.id]` und `archiveStats.alerts[trip.id]` sind bereits im Page-Load vorhanden — für AC-3 reicht ein Frontend-Only-Compute.
- **Modal-Pattern:** Für die Verlauf-Ansicht gibt es Modal-Komponenten in `$lib/components/organisms`; alternativ eine eigene Route `/archiv/[id]/history`.

## Dependencies

- **Upstream (AC-1):** `LoadBriefingLog()` im Store — liefert alle Einträge, nach TripID gefiltert im neuen Handler.
- **Upstream (AC-2):** `GET /api/trips/{id}` (bestehend) liefert alle Konfigurationsfelder; Wizard-State-Initialisierung clientseitig.
- **Upstream (AC-3):** `archiveStats` — bereits im Page-Load vorhanden, kein Backend-Änderungsbedarf.
- **Downstream:** Keine anderen Seiten abhängig von den neuen Endpoints.

## Existing Specs

- `docs/specs/modules/issue_388_archiv_atomic.md` — Archiv-Atomics (abgeschlossen)

## Entscheidungen aus dem Issue-Body

- **AC-3 Auto-Summary:** Das Issue lässt offen (Auto vs. Freitext). Da `briefings[id]` und `alerts[id]` bereits geladen sind, ist Auto-Summary ohne Backend-Aufwand umsetzbar: `"3 Briefings, 1 Alert"`. Freitext würde ein neues Datenbankfeld erfordern. → **Empfehlung: Auto-Summary** (bestehende Daten, kein neues Schema).

## Scope der Implementierung

### AC-1: Briefing-Verlauf
- **Backend:** Neuer Handler `BriefingHistoryHandler` → `GET /api/trips/{id}/briefing-history`
  - Filter: Alle `BriefingLogEntry` wo `TripID == id`
  - Response: `[{sent_at, kind, channels}]` (ohne trip_id, ist implizit)
- **Frontend:** Neue Route `/archiv/[id]/history` (eigene Seite, kein Modal — Modal würde komplexes Zustandsmanagement erfordern bei unbekannter Eintrags-Anzahl)
  - Zeigt chronologische Liste: Datum, Kanal(e), Typ (morning/evening)

### AC-2: Als Vorlage kopieren
- **Backend:** Kein neuer Endpoint nötig — `GET /api/trips/{id}` (bereits vorhanden)
- **Frontend:** 
  - `/trips/new?from={tripId}` — `+page.server.ts` lädt den Trip und übergibt `templateTrip` als `data`
  - `WizardState` bekommt neue Methode `fromTemplate(trip)`: füllt `stages` (nur Anzahl/Namen, keine Waypoints/Daten), `activity`, `alertRules`, `weatherMetrics`

### AC-3: "Was passiert ist"-Spalte
- **Frontend-Only:** `archiveStats` ist bereits vorhanden, Auto-Summary aus `briefings[trip.id]` + `alerts[trip.id]`
- Format: `"12 Briefings · 3 Alerts"` (oder `"12 Briefings"` wenn Alerts = 0)

## Risks & Considerations

- **BriefingLogEntry fehlt Subject:** Das Log speichert `Kind` (morning/evening) und `Channels`, aber keinen Betreff/Preview. Die Verlauf-Ansicht kann daher nur Datum + Typ + Kanal zeigen — kein „Betreff" wie im Issue erwähnt. Ist annehmbar (Datenstruktur liegt so vor).
- **Wizard-Vorlage ohne Waypoints:** Etappen werden als leere Stages kopiert (nur Name + Anzahl). Dates werden geleert (kein Datum im Archiv sinnvoll). Explizit dokumentieren im UI.
- **„Treffer"-Spalte (Forecast-Accuracy):** Bleibt auf `—` — kein Backend-Feld. Ist bereits als `null` in `archiveStats` und außerhalb von #559.
