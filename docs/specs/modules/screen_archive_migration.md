# Spec: Archiv-Bildschirm — archivierte Trips + Wiederherstellen (Issue #388, Epic #368 Phase 2, Screen 3/6)

**Status:** Draft — wartet auf PO-Approval
**Created:** 2026-05-26
**Issue:** #388 · Design `spec/screen-archive.jsx` (stark gekürzt) · Retrospektive verschoben → #396
**PO-Entscheidungen:** (1) Schlanke Liste aus echten Daten, KEINE erfundenen Genauigkeits-/Briefing-/Alarm-Daten. (2) Einzige relevante Aktion = **Wiederherstellen** (zurück in den aktiven Zustand).

## Zweck

`/archiv` ist heute ein leerer Platzhalter (kein Loader). Ersetzt durch eine Liste der **archivierten** Trips (`deriveTripStatus(t) === 'archived'`) mit der Aktion **Wiederherstellen** je Trip. Genauigkeits-Retrospektive entfällt (keine Datenquelle → #396).

## Scope

- **Daten:** Trips client-seitig laden (`api.get<Trip[]>('/api/trips')`, Muster wie `routes/trips/+page.svelte`), filtern auf `deriveTripStatus(trip, now) === 'archived'` (aus `$lib/utils/tripStatus`).
- **Wiederherstellen:** Button je Zeile → `api.patch('/api/trips/{id}', { archived: false })` (exakt der „Dearchivieren"-Mechanismus aus der Touren-Liste #295) → bei Erfolg Trip aus der lokalen Liste entfernen (er ist nicht mehr archiviert). Fehler → Fehlermeldung, Liste unverändert.
- **Löschen (endgültig, nach Rückfrage):** Button je Zeile → öffnet einen Bestätigungs-`Dialog` (Muster wie Touren-Liste #295: deleteTarget + Dialog mit Trip-Name + Warnung „endgültig/irreversibel") → bei Bestätigung `api.del('/api/trips/{id}')` → bei Erfolg aus Liste entfernen; Abbrechen/Fehler → Liste unverändert. KEIN Löschen ohne Bestätigung.
- **Seite** `frontend/src/routes/archiv/+page.svelte`: Header (Eyebrow „Workspace · Vergangene Trips", H1 „Archiv", knappe Beschreibung), Such-Feld (`Input` rounded), Sortierung via `Segmented` (**Neueste** = Enddatum absteigend / **Etappen** = Anzahl absteigend; KEIN „Genauigkeit"), Liste als `Card` mit Zeilen: Name (Link `/trips/[id]`), Etappen-Anzahl, Zeitraum, Aktionen **Wiederherstellen** + **Löschen** (`Btn`, Löschen als danger/ghost). Leerzustand (`EmptyState`), Fußzeile mit Zähler. Nur Phase-1-Bibliothek (inkl. `Dialog`).
- **Weggelassen** (keine Datenquelle → kein Fake, #396): Genauigkeit/Forecast-Treffer, Briefings-Zähler, Alarme, Schlagzeilen, „Briefing-Verlauf"- und „Als Vorlage"-Aktion.
- Terminologie „Trip"/„Trips" (kein „Tour"). Tokens 1:1.

## Acceptance Criteria

**AC-1:** Given Trips mit `deriveTripStatus === 'archived'`, When `/archiv` lädt, Then listet die Seite genau diese; aktive/geplante/pausierte erscheinen NICHT.

**AC-2:** Given ein archivierter Trip, When die Zeile rendert, Then zeigt sie Name (Link `/trips/{id}`), Etappen-Anzahl, Zeitraum und einen **Wiederherstellen**-Button.

**AC-3 (Wiederherstellen):** Given Klick auf „Wiederherstellen", When der PATCH `{ archived: false }` erfolgreich ist, Then verschwindet der Trip aus der Archiv-Liste (zurück in aktiv/geplant in der Touren-Liste); bei API-Fehler bleibt er stehen + Fehlerhinweis. KEIN optimistisches Entfernen vor Erfolg.

**AC-4:** Given Suche/Sortierung, When genutzt, Then filtert nach Name, sortiert Neueste (Enddatum desc, Default) / Etappen (Anzahl desc). Keine Genauigkeits-Sortierung.

**AC-5:** Given keine archivierten Trips, When `/archiv` lädt, Then `EmptyState` („Noch keine archivierten Trips.").

**AC-6 (kein Fake):** KEINE Genauigkeits-/Briefing-/Alarm-/Schlagzeilen-Elemente, kein erfundener Wert.

**AC-7 (Terminologie + keine Regression):** `trip-terminology`-Guard grün (kein „Tour" in `/archiv`), `contrast-audit` 5/5, `svelte-check` sauber für Archiv-Dateien, `vite build` grün, `/archiv` lädt.

**AC-8 (Löschen mit Bestätigung):** Given Klick auf „Löschen", When der Button gedrückt wird, Then erscheint ein Bestätigungs-`Dialog` mit Trip-Name und Warnung „endgültig/irreversibel" — der Trip wird NICHT sofort gelöscht. When der User bestätigt, Then `api.del('/api/trips/{id}')` und bei Erfolg Entfernen aus der Liste; bei Abbrechen/API-Fehler bleibt der Trip unverändert. Kein Löschen ohne Bestätigung.

## Tests (mock-frei)

- Unit `archiv/archiveHelpers.ts` (node:test, echte Trip-DTO-Fixtures): Filter `archived` + Sortierung Neueste/Etappen. RED zuerst.
- E2E (Staging): `/archiv` authentifiziert lädt; archivierte Trips bzw. Leerzustand; „Wiederherstellen" sichtbar; kein „Tour", kein Genauigkeits-Wert. (Wiederherstellen-Mutation wird gegen einen Test-Trip nur geprüft, wenn ein archivierter Validator-Trip existiert — sonst Render-/Leerzustands-Beleg.)

## Risiken

- Restore-PATCH-Vertrag (`{ archived: false }`) muss dem Backend entsprechen — identisch zur Touren-Liste, daher abgesichert.
- Validator-Testdaten: evtl. kein archivierter Trip → Leerzustand (valide); Wiederherstellen-Pfad dann nur per Unit-Test/Code-Review belegt.
- LoC: Seite + Helper + Test, < 250.
