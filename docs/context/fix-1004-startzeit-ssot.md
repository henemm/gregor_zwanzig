# Context: fix-1004-startzeit-ssot (Issue #1004)

## Request Summary
Der #995-Fix (Gruppe A, Commit 34929cd3) ist wirkungslos: E-Mails/Segmenttabellen rechnen
weiterhin ab der alten GPX-Import-Zeit (z.B. 07:00) statt ab der konfigurierten Etappen-
Startzeit. PO-Vorgabe (verbindlich, Issue #1004 Kommentar): Es gibt genau EINE maßgebliche
Startzeit pro Etappe — `stage.start_time` — und das gilt für ALLE Trips inkl. Bestand,
ohne Migration und ohne Alt/Neu-Sonderfall.

## Warum der #995-Fix wirkungslos war (bewiesen)
1. **Flag nie persistiert:** `time_window_origin` wird nur in `gpx_processing.py` in-memory
   gesetzt. Weder `src/app/loader.py` (Waypoint-Parsing Z.269-279, Schreibpfad Z.1016-1017)
   noch `internal/model/trip.go` kennen das Feld → beim ersten Speichern weg, Scheduler lädt
   `origin=None` → `time_window` gewinnt wieder.
2. **Bestand ausgenommen:** `origin=None` wird als „manuell" (autoritativ) behandelt — alle
   vor dem Fix importierten Trips zeigen per Spec-„Known Limitation" das alte Verhalten
   weiter. Beweis in echten Daten: `data/users/henning/trips/74de939c.json`, Etappe
   „nach Sassenberg": `start_time=14:00`, Waypoint `time_window=07:00-07:00`, `origin=null`.

## Kern-Befund für den Neuansatz
**`Waypoint.time_window` ist ausschließlich ein GPX-Import-Artefakt.** Es gibt KEINEN Weg,
es manuell zu setzen: kein Frontend-Edit (WaypointRow.svelte:47-48 zeigt es nur an), kein
Go-Handler schreibt es (nur Trip-Roundtrip `internal/model/trip.go:72`), Python schreibt es
nur beim Import (`gpx_processing.py:145,161`). Die „manuell gesetzte time_window", die #995
per Flag schützen wollte, existiert im Produkt nicht. Der legitime manuelle Per-Wegpunkt-
Mechanismus ist `arrival_override` (Issue #303, `internal/handler/trip.go:322-330`).

**`arrival_calculated` ist immer frisch:** `store.SaveTrip` (`internal/store/store.go:179-187`)
ruft bei JEDEM Speichern `ComputeStageArrivals` auf (`internal/model/naismith.go:104-122`) —
Kaskade startet bei `stage.StartTime` (Default 08:00), `arrival[0] = start_time`. Ändert der
User die Etappen-Startzeit, sind alle `arrival_calculated` sofort korrekt. Python-Seite hat
Self-Heal (`trip_segments.py:66-69`, nur wenn ALLE None).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_segments.py:86-130` | SSoT `convert_trip_to_segments()` — Prioritätskette; `time_window` steht (mit totem Flag-Check) weiterhin OBEN für wp1 UND wp2. **Kernänderung hier.** |
| `src/services/gpx_processing.py:143-163` | Setzt `time_window` + totes `time_window_origin` beim Import. Flag-Zeilen entfernen; `time_window` selbst bleibt (Roundtrip/Anzeige), verliert nur Autorität. |
| `src/app/trip.py:83` | Totes Feld `Waypoint.time_window_origin` — entfernen (nie persistiert, nach Kettenfix funktionslos). |
| `src/services/trip_report_scheduler.py`, `src/services/preview_service.py`, `src/services/trip_command_processor.py`, `src/services/trip_alert.py` | Die 4 SSoT-Aufrufer — profitieren automatisch, müssen aber End-to-End nachgewiesen werden. |
| `internal/model/naismith.go:104-122` + `internal/store/store.go:179-187` | Beleg: `arrival_calculated`-Kaskade startet immer bei `stage.StartTime` — Fallback-Glied der Kette ist damit stets aktuell. |
| `frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte:47-48` | Zeigt `waypoint.time_window` (alte Importzeit) als Info-Text — widerspricht nach dem Fix der „einen Zeit". Kandidat: auf `arrival_calculated` umstellen oder entfernen (PO entscheidet via AC). |
| `tests/tdd/test_issue_995_segment_start_time.py` | Bestehende In-Memory-Tests aus #995 — kodieren `origin=None ≈ manuell` als Soll; müssen an die neue Regel angepasst/ersetzt werden. |
| `data/users/henning/trips/74de939c.json` | Echter Bestandstrip als Abnahme-Referenz (start_time 14:00 vs. time_window 07:00). |

## Existing Patterns
- **Prioritätskette nach Fix:** `arrival_override` (manuell, #303) > `stage.start_time`
  (i==0) > `arrival_calculated` (Naismith, immer frisch ab start_time) > Default 08:00.
  `time_window` fliegt komplett aus der Kette — kein Flag, keine Migration nötig.
- **Roundtrip-Erhalt:** `time_window` bleibt in Persistenz/DTO erhalten (Read-Modify-Write,
  BUG-DATALOSS-GR221-Regel) — es wird nur nie mehr als Startzeit-Quelle gelesen.
- **AC-Test-Vorgabe (#1004, verbindlich):** Abnahme aus Nutzersicht gegen echten
  Bestandstrip auf Staging — Persistenz-Roundtrip inklusive, keine In-Memory-Ersatztests.

## Dependencies
- Upstream: `stage.start_time` (Trip-Editor, Go-PATCH), `arrival_calculated`
  (ComputeStageArrivals bei jedem SaveTrip), `arrival_override` (#303).
- Downstream: Briefing-Mail (Stundentabellen), Trip-Detail-Stundentabelle
  (preview_service), Telegram/SMS-Segmente (trip_command_processor), Alert-Segmentfenster
  (trip_alert) — alle über dieselbe SSoT-Funktion.

## Existing Specs
- `docs/specs/modules/issue_995_mail_bugs_bundle.md` — Gruppe A wird durch diesen Fix
  ersetzt (Flag-Ansatz verworfen, Known Limitation „keine Migration" entfällt).
- `docs/specs/modules/issue_783_776_778_briefing_fixes.md` — dokumentiert die alte Kette
  `time_window > arrival_override > stage.start_time > arrival_calculated` (wird obsolet).
- `docs/specs/modules/issue_802_fahrrad_segment_zeit.md` — ComputeStageArrivals-Verhalten.

## Risks & Considerations
- **Historie:** Die Kette wurde 4× angefasst (trips_time_window_lost, #783, #802, #995);
  `time_window` blieb bisher oben aus Angst vor „bewusst gesetzten" Werten. Diese Angst ist
  jetzt widerlegt (kein Schreibpfad existiert) — im Spec-Dokument festhalten, damit Patch Nr. 5
  der letzte ist.
- **Zwischenzeiten ändern sich:** Für i>0 lieferte bisher die Import-`time_window` die
  Segmentgrenzen (z.B. „Seg 2 Start 09:00"); künftig `arrival_calculated` (Naismith ab neuer
  start_time). Das ist gewollt (eine konsistente Kaskade), verändert aber sichtbare
  Zwischenzeiten auch bei Trips, deren start_time zufällig der Importzeit entspricht.
- **Anzeige im Wizard:** `WaypointRow` zeigt weiterhin die alte Importzeit als Text —
  ohne Frontend-Anpassung bleibt eine widersprüchliche Anzeige (nur Anzeige, keine Rechnung).
- **`end_dt <= start_dt`-Guard (`trip_segments.py:144-148`):** Segmente werden bei
  nicht-monotonen Zeiten verworfen — nach Umstellung auf durchgängige Naismith-Kaskade
  strukturell unwahrscheinlicher, aber im Test abdecken (später Start, kurze Etappe).
- **Kein Schema-Rework:** Persistenzformat unverändert (nur totes Python-Feld entfernt,
  das nie serialisiert wurde) — trotzdem löst `trip.py`-Edit den Backup-Hook aus (ok).

## Analysis

### Type
Bug (Re-Fix von #995 Gruppe A mit verworfenem Ansatz; PO-Vorgabe in #1004 verbindlich).

### Challenger-Verdict (analysis-challenger, 2026-07-03): NEEDS REVIEW — Funde eingearbeitet
1. **Naismith-Mitternachts-Klemme (bestätigt, in Scope als Guard-Anpassung/Test):**
   `src/core/naismith.py:66-72` kappt `arrival_calculated` bei `23:59`. Späte
   `stage.start_time` (z.B. 22:00) + lange Etappe → mehrere Wegpunkte identisch `23:59` →
   `end_dt <= start_dt`-Guard (`trip_segments.py:144-148`) verwirft Folgesegmente still.
   Heute maskiert (time_window gewinnt), nach dem Fix erstmals erreichbar. Muss im
   TDD-RED als Testfall rein; Verhalten: letzte Segmente dürfen kollabieren, aber das
   ERSTE Segment und alle nicht geklemmten müssen erhalten bleiben (kein Totalausfall).
2. **Fünfter time_window-Leser (bestätigt, Legacy, out of scope):**
   `src/services/trip_forecast.py:145-155` liest `waypoint.time_window` direkt fürs
   Wetter-Abfragefenster — einziger Aufrufer ist der Legacy-CLI-Pfad
   (`src/app/cli.py:228-229`, `--trip`), NICHT der Produkt-Scheduler/Mail/Telegram/Alert-
   Pfad. Wird transparent im PO-Freigabetext genannt + Folge-Issue.
3. **`gpx_to_stage_data()` (`gpx_processing.py:230-241`)** — der echte Wizard-Upload-
   Endpunkt gab das #995-Flag NIE weiter (Dict ohne `time_window_origin`) — noch direkterer
   Beweis der Wirkungslosigkeit.
4. **`docs/reference/api_contract.md:669-675`** dokumentiert das Flag — muss beim Fix
   mit bereinigt werden (SSoT-Doku).
5. **`frontend/src/routes/_home/cockpitHelpers.ts:31-37` `stageWindow()`** — aktuell
   aufruferlose TS-Kopie derselben falschen Kette; laut `issue_568_home_redesign.md` für
   spätere Anbindung vorgesehen → NICHT löschen, sondern auf neue Regel umstellen
   (sonst reproduziert die Anbindung später exakt #1004). Zweiter Challenger-Fund:
   `api_contract.md` referenziert das Flag zusätzlich im Changelog (Z.2384-2388).
   Zusatz-Beleg: auch Python-`save_trip()` (`loader.py:1197-1201`) berechnet
   `compute_stage_arrivals()` bei jedem Save — arrival_calculated ist beidseitig frisch.
6. **Schema-Restrisiko (akzeptiert):** `PUT /api/trips/{id}` ersetzt Stages aus dem
   Request-Body; `time_window` ist unvalidiertes Roundtrip-Feld. Kein aktiver Client
   schreibt es; nach dem Fix ohnehin nie mehr autoritativ → Risiko gegenstandslos.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_segments.py` | MODIFY | `time_window` aus beiden Kettenzweigen (wp1/wp2) entfernen; Guard-Verhalten bei 23:59-Klemme testgesichert |
| `src/app/trip.py` | MODIFY | totes Feld `time_window_origin` entfernen |
| `src/services/gpx_processing.py` | MODIFY | `time_window_origin`-Zeilen entfernen (Feld `time_window` bleibt als Anzeige-/Roundtrip-Artefakt) |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | `stageWindow()` auf neue Prioritätsregel umstellen (für #568 vorgesehen, aktuell aufruferlos) |
| `docs/reference/api_contract.md` | MODIFY | Flag-Doku ersetzen durch neue Kette |
| `tests/tdd/test_issue_995_segment_start_time.py` | MODIFY/REPLACE | an neue Regel anpassen (origin-Semantik entfällt) |
| `tests/tdd/test_issue_1004_*.py` | CREATE | Nutzersicht-Tests inkl. Persistenz-Roundtrip + Klemm-Fall |

### Scope Assessment
- Files: ~7 (Code 4, Doku 1, Tests 2) — Risk Level: MEDIUM (zentrale Zeitkette, 4 Produkt-Aufrufer)
- Estimated LoC: ±80 Code, +150 Tests

### Technical Approach
`time_window` verliert jede Autorität in `convert_trip_to_segments()`. Neue Kette:
`arrival_override` > `stage.start_time` (nur i==0) > `arrival_calculated` (immer frisch,
da Go `ComputeStageArrivals` bei jedem SaveTrip ab `stage.StartTime` kaskadiert) >
Default 08:00. Kein Flag, keine Migration — wirkt sofort für ALLE Trips inkl. Bestand
(Beweis: `74de939c.json` hat bereits korrekte `arrival_calculated` 14:00/14:21/14:46).

### Open Questions
Keine — Legacy-CLI-Pfad und Mitternachts-Klemme werden im PO-Freigabetext transparent
benannt (Lehre aus #995: keine versteckten Known Limitations).
