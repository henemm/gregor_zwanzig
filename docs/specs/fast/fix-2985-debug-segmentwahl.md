# Mini-Spec: fix-2985-debug-segmentwahl

Issue #2985 (Rest aus #1982, Paritäts-Bestandsaufnahme #1986 Eintrag NEU-4). PO-Auftrag: keine doppelte Rechnung für dieselbe Aufgabe.

## Was ändert sich
- Die Staging-Debug-Route `POST /api/debug/trigger-radar-alert` (`api/routers/debug.py`) bestimmt die Etappe nicht mehr mit einer eigenen Kopie („heute, aktiv oder erstes“), sondern über den gemeinsamen Baustein `resolve_current_segment` (`src/services/trip_segments.py`), den auch `TripAlertService.check_radar_alerts` nutzt.
- Die Auswahl wandert in eine kleine, benannte Hilfsfunktion `_pick_debug_segment(trip, now_utc, today)` in `api/routers/debug.py`:
  1. Liefert `resolve_current_segment` ein Segment → genau dieses (inkl. Vortags-Rückgriff bei Ankunft nach Mitternacht).
  2. Sonst Test-Seam-Rückfall (nur Debug, Staging-Testdaten liegen oft in der Vergangenheit): erstes Segment von heute, sonst erstes Segment des ersten Etappendatums mit Segmenten.
  3. Sonst `None` → Antwort `no_segment` wie bisher.
- Die eigene Schleife „aktiv oder erstes“ in der Route entfällt; der Docstring-Hinweis „geht NICHT über resolve_current_segment“ wird berichtigt.

## Was darf sich nicht ändern
- Route bleibt staging-only (sonst 404), Empfänger bleibt `gregor-test@henemm.com`, kein Throttle-Eintrag.
- Antwortformat (`status`, `trip_id`, `segment`) unverändert.
- `resolve_current_segment` selbst wird nicht angefasst.
- Ist heute ein Segment aktiv, wählt die Route dasselbe Segment wie vorher.

## Acceptance Criteria
- **AC-1:** Given ein Trip, dessen gestrige Etappe nach Mitternacht ankommt und jetzt noch aktiv ist, und heute keine Etappe, When die Debug-Segmentwahl läuft, Then liefert sie genau das Segment, das `resolve_current_segment` liefert (das aktive Segment von gestern), nicht das erste Segment des Trips.
- **AC-2:** Given ein Trip mit heute aktivem Segment, When die Debug-Segmentwahl läuft, Then liefert sie dieses aktive Segment (unverändertes Verhalten).
- **AC-3:** Given ein Trip, dessen Etappen alle in der Vergangenheit liegen (keine aktive, keine Vorschau), When die Debug-Segmentwahl läuft, Then liefert sie über den Test-Seam-Rückfall das erste Segment der ersten Etappe statt `None`.
- **AC-4:** Given die Mutation, dass die Hilfsfunktion `resolve_current_segment` nicht mehr aufruft (eigene Heute-Schleife), When der neue Test läuft, Then wird AC-1 rot (Mutations-Gegenprobe).

## Manuelle Test-Schritte
1. Neuen Test einzeln ausführen → grün.
2. Mutation (Aufruf von `resolve_current_segment` durch `None` ersetzen, String-Ersetzung mit Sicherungskopie) → AC-1-Test rot; zurücksetzen.
3. Bestehende Tests zur Debug-Route (`tests/tdd/test_issue_830_radar_alert_validator.py`, `tests/test_user_id_default_guard.py`) bleiben grün.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `tests/tdd/test_issue_2985_debug_segmentwahl.py` — echte Trip-Objekte, kein Mock, ruft `_pick_debug_segment` direkt.
