# Context: Issue #675 — Startzeiten je Etappe editieren können

## Request Summary
Der Nutzer möchte pro Etappe eine eigene Startzeit setzen können — z.B. am ersten Tag erst um 15 Uhr starten, weil er an dem Tag anreist. Aktuell startet jede Etappe implizit um den Naismith-Default **08:00**; es gibt im Frontend kein Eingabefeld dafür.

## Kernbefund
Die **gesamte Backend-, Persistenz- und Berechnungs-Infrastruktur existiert bereits.** Das Feld `start_time` (Format `"HH:MM"`) ist im Datenmodell, im Persistenz-JSON, in der Naismith-Engine (Go **und** TS) und im API-Merge schon angelegt — es wird nur nirgends durch eine UI befüllt. **Dies ist ein Frontend-only-Feature: ein Zeit-Eingabefeld pro Etappe + Mutations-Handler.**

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | **Hauptlücke.** Rendert `StageDateField` (Z. 257), aber kein Startzeit-Feld. `arrivals` (Z. 78–80) berechnet schon aus `activeStage.start_time`. `handleDateChange` (Z. 92) = Vorbild für immutablen Mutations-Handler. `save()` (Z. 51) PUTet kompletten `stages[]`. |
| `frontend/src/lib/components/edit/StageDateField.svelte` | Vorbild-Komponente: dünner Wrapper um `<input type="date">` mit Label + Chip + `onchange`-Callback. Analog dazu ein `StageTimeField` (`<input type="time">`). |
| `frontend/src/lib/utils/naismith.ts` | `computeArrivalTimes(stage, start_time)` + `parseStartMinutes()` → Default `"08:00"` bei leer/ungültig. Verbraucht `start_time` bereits. |
| `frontend/src/lib/types.ts` (Z. 52) | `Stage.start_time?: string` existiert bereits. |
| `internal/model/trip.go` (Z. 72) | Go-Modell: `StartTime *string \`json:"start_time,omitempty"\``. |
| `internal/model/naismith.go` (Z. 23–24, 82) | `parseStartMinutes(stage.StartTime)`, Default `"08:00"`, Validierung (>23h/>59min → Default). |
| `internal/handler/trip.go` (Z. 155–248) | PUT-Handler: RMW-Merge, `Stages *[]model.Stage`, ruft nach Update `ComputeStageArrivals()` (Z. 225) und `SaveTrip()` (Z. 238). |
| `internal/store/store.go` (Z. 159–177) | `SaveTrip()` serialisiert `start_time` ins User-JSON. |

## Existing Patterns
- **Immutabler Stage-Mutations-Handler:** `handleDateChange` setzt `stages = stages.map(...)` und fasst nur die betroffene Etappe an — exakt das Muster für `handleStartTimeChange`.
- **Dünne Feld-Komponente mit `onchange`-Callback** (StageDateField) — Parent übernimmt via Handler, nicht via Event-Fischen. Svelte-5 `$props/$bindable/$derived`.
- **Live-Recompute:** `arrivals` ist `$derived` aus `activeStage.start_time` → Setzen der Startzeit aktualisiert die Wegpunkt-Ankunftszeiten sofort (auch ohne Speichern).
- **RMW-Merge im Go-Handler** schützt Bestandsfelder — `start_time` wird nur überschrieben wenn `stages` mitgeschickt wird.

## Dependencies
- **Upstream (was die UI nutzt):** `Stage.start_time`-Feld, `computeArrivalTimes`, PUT `/api/trips/{id}`.
- **Downstream (was das Feld konsumiert):** Naismith-Ankunftszeiten in `WaypointCard`/Profil; Go-`ComputeStageArrivals` beim Speichern; Snapshot-/Briefing-Zeitfenster nutzen perspektivisch die Etappen-Startzeit.

## Existing Specs
- Kein dediziertes Spec für `start_time`-UI. Verwandt: `docs/design-requests/stage_date_edit.md` (#498, das Datum-Pendant).
- Naismith-Verhalten bereits durch `internal/model/naismith_test.go` (AC-1/AC-2/F002) und `frontend/.../naismith.test.ts` abgesichert.

## Risks & Considerations
- **Geltungsbereich der Startzeit:** Naismith rechnet **pro Etappe** (jede Etappe startet neu bei ihrer eigenen `start_time`). Tag-1-15:00 betrifft nur Tag 1 — korrekt für den Use Case. Keine kaskadierende Wirkung auf Folgetage (anders als beim Datum-Cascade).
- **Default-Treue:** Leeres/ungesetztes `start_time` muss weiterhin als 08:00 gerechnet werden (alt-treu — Bestands-Trips ohne Feld dürfen sich nicht ändern).
- **Validierung:** `<input type="time">` liefert nativ `"HH:MM"`; Go validiert ohnehin (>23/>59 → Default). Leeren-Zustand (Feld geräumt) sauber als „kein Override" behandeln.
- **Mobile-Parität:** EditStagesPanelNew hat Desktop- **und** Mobile-Markup (@media ≤899px). Das Feld muss in beiden erscheinen (vgl. #661-Lehre: getByTestId zählt display:none-DOM).
- **Mandantentrennung:** PUT `/api/trips` läuft bereits user-isoliert; kein neuer Endpoint nötig.
- **Wiederverwendung:** Editor ist sowohl in `/trips/new` (eingebettet, `showSave=false`, #658) als auch in der Trip-Bearbeitung aktiv → Feld erbt automatisch in beide Kontexte.
