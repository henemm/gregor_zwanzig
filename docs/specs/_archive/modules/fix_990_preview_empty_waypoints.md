---
entity_id: fix_990_preview_empty_waypoints
type: bugfix
created: 2026-07-11
updated: 2026-07-11
status: implemented
version: "1.0"
tags: [backend, preview, bugfix]
---

# Issue #990 — Vorschau zeigt generische Fehlermeldung bei wegpunktlosen Etappen

## Approval

- [x] Approved (2026-07-11)

## Purpose

Der Trip-Detail Vorschau-Tab (E-Mail + SMS) zeigt bei Etappen mit weniger als
2 Wegpunkten die generische Fehlermeldung "Vorschau konnte nicht geladen
werden" statt der spezifischen, bereits im Frontend vorbereiteten
Wegpunkt-Hinweismeldung (`PREVIEW_ERROR_NO_WAYPOINTS` aus Issue #421). Ursache:
`PreviewService._resolve_target_date` wählt die erste Etappe mit
`date >= today` (bzw. im Fallback die erste Etappe überhaupt), ohne zu prüfen,
ob diese Etappe genug Wegpunkte hat, um überhaupt gerendert zu werden. Der
nachgelagerte Fehlertext nennt daher nie das Wort „waypoint", wodurch die
Frontend-Erkennung aus #421 nie greift.

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `PreviewService._resolve_target_date` (Zeile 52-71), `PreviewService._build_report` (Zeile 96-100)

> **Schicht-Hinweis:** Kern-Fix ist **Python-Core/Domain-Backend**
> (`src/services/preview_service.py`, FastAPI Core über `api.main:app`). Kein
> Frontend-Touch nötig — `frontend/src/lib/components/preview/previewHelpers.ts`
> (`friendlyPreviewError`) existiert bereits aus Issue #421 und matcht das
> Wort „waypoint" case-insensitive im `detail`-Text. `trip_segments.py`
> (geteilte SSoT mit `TripAlertService`) bleibt ebenfalls unverändert.

## Estimated Scope

- **LoC:** ~100-150 (inkl. Tests)
- **Files:** 2 Pflicht (`src/services/preview_service.py`, `tests/tdd/test_epic_140_preview_endpoints.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_segments.py` (`convert_trip_to_segments`, Zeile 106-123) | bestehend, unverändert | Definiert die Waypoint-Mindestschwelle (`< 2` → `[]`, Zeile 120) — SSoT, die Fix referenziert statt dupliziert; geteilt mit `TripAlertService` |
| `api/routers/preview.py` (Zeile 40-47) | bestehend, unverändert | Mappt `LookupError`→404, `ValueError`→422 — nur der Fehlertext-Inhalt ändert sich, nicht das Exception-Mapping |
| `frontend/src/lib/components/preview/previewHelpers.ts` (`friendlyPreviewError`, Zeile 47-57) | bestehend, unverändert | Vertrag aus Issue #421: zeigt `PREVIEW_ERROR_NO_WAYPOINTS` nur, wenn `detail` das Wort „waypoint" (case-insensitive) enthält |
| `docs/specs/modules/preview_service.md` (AC-3) | bestehend, wird als Folge-Doku aktualisiert | Beschreibt aktuell den generischen `LookupError`-Text — nach Fix muss AC-3 die Text-Differenzierung widerspiegeln |

## Implementation Details

Zwei-Zweig-Fix, ausschließlich in `preview_service.py`:

```
_resolve_target_date(trip, given_date):
    - given_date gesetzt: unverändert ISO parsen und zurückgeben
      (Text-Differenzierung passiert unten in _build_report, nicht hier)
    - given_date leer (Auto-Resolve):
      - Zukunfts-Suche: überspringt jede Stage mit < 2 Wegpunkten,
        nimmt die erste renderbare Stage mit date >= today
      - Fallback (keine renderbare Stage >= today gefunden): überspringt
        ebenfalls Stages mit < 2 Wegpunkten, nimmt die erste renderbare
        Stage überhaupt (sortiert nach Datum)
      - keine einzige Stage im Trip ist renderbar (weder Zukunft noch
        Fallback): wirft Error, dessen Text das Wort "waypoint" enthält

_build_report(trip, target, report_type, demo):
    - segments = scheduler._convert_trip_to_segments(trip, target) liefert []
    - Unterscheidung bei explizitem target_date (Auto-Resolve liefert durch
      obigen Fix ohnehin nie eine nicht-renderbare Stage):
      - trip.get_stage_for_date(target) is None
        → generischer Text "Keine Stage am {target} ..." (kein "waypoint",
          echter Datum-falsch-Fall, Frontend zeigt generische Meldung)
      - trip.get_stage_for_date(target) existiert, aber Stage hat < 2
        Wegpunkte → Text MUSS "waypoint" enthalten (matcht Frontend-Regex
        aus #421), z.B. "Stage am {target} hat zu wenige waypoints ..."
```

Waypoint-Schwelle (`< 2`) wird nicht neu kodifiziert, sondern aus
`trip_segments.py` referenziert bzw. mit derselben Konstante/demselben
Vergleichsausdruck gehalten, damit die Zahl nicht an zwei Stellen gepflegt
werden muss.

## Expected Behavior

- **Input:** `trip_id`, `user_id`, `report_type`, optionales `target_date` (ISO) — wie bisher.
- **Output:** Unverändert bei renderbaren Stages (Email-HTML bzw. SMS-Tupel). Bei nicht-renderbaren Stages (egal ob per Auto-Resolve übersprungen oder per explizitem `target_date` getroffen): Fehlertext enthält das Wort „waypoint", HTTP-Code bleibt 404 (`LookupError`, konsistent mit bestehendem Vertrag aus `docs/specs/modules/preview_service.md` AC-3).
- **Side effects:** Keine. Reine Steuerungslogik-Änderung in der Etappen-Auswahl und im Fehlertext; kein Versand, kein Datei-Write.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen früheste künftige (oder als Fallback: früheste überhaupt) Etappe weniger als 2 Wegpunkte hat, aber eine spätere Etappe ausreichend Wegpunkte besitzt / When der Nutzer den Vorschau-Tab ohne explizites Datum öffnet (Auto-Resolve) / Then überspringt die Vorschau die wegpunktlose Etappe und zeigt die Vorschau der nächsten renderbaren Etappe an, ohne Fehlermeldung.
  - Test: E-Mail- bzw. SMS-Vorschau für einen Trip mit einer wegpunktlosen ersten Etappe und einer vollständigen zweiten Etappe aufrufen und prüfen, dass der Inhalt der zweiten (renderbaren) Etappe angezeigt wird statt eines Fehlers.
  - Test-Name: `tests/tdd/test_epic_140_preview_endpoints.py::TestIssue990WaypointSkip::test_ac1_auto_resolve_skips_stage_without_waypoints`

- **AC-2:** Given eine Etappe mit weniger als 2 Wegpunkten existiert an einem bestimmten Datum / When der Nutzer im Vorschau-Tab genau dieses Datum explizit auswählt (`target_date` gesetzt) / Then zeigt die Vorschau die spezifische Wegpunkt-Hinweismeldung „Diese Etappe hat noch keine Wegpunkte...", nicht die generische Fehlermeldung.
  - Test: Vorschau mit explizitem `target_date` auf die wegpunktlose Etappe anfragen, HTTP-404-Antwort auswerten und prüfen, dass `detail` das Wort „waypoint" enthält (case-insensitive) — dies ist die Bedingung, die `friendlyPreviewError` im Frontend zur spezifischen Meldung führt.
  - Test-Name: `tests/tdd/test_epic_140_preview_endpoints.py::TestIssue990WaypointSkip::test_ac2_explicit_date_on_empty_stage_error_contains_waypoint`

- **AC-3:** Given der Nutzer wählt im Vorschau-Tab ein Datum, an dem der Trip überhaupt keine Etappe hat (z.B. weit außerhalb des Tourzeitraums) / When er die Vorschau für dieses Datum abruft / Then zeigt die Vorschau weiterhin die generische Fehlermeldung „Vorschau konnte nicht geladen werden", NICHT die Wegpunkt-Hinweismeldung.
  - Test: Vorschau mit explizitem `target_date` auf ein Datum ohne jede Stage anfragen und prüfen, dass die HTTP-404-`detail` das Wort „waypoint" NICHT enthält — Regressionsschutz gegen Fehlklassifikation eines echten „Datum falsch"-Falls als Wegpunkt-Problem.
  - Test-Name: `tests/tdd/test_epic_140_preview_endpoints.py::TestIssue990WaypointSkip::test_ac3_explicit_date_without_any_stage_stays_generic`

- **AC-4:** Given ein Trip, bei dem sämtliche Etappen weniger als 2 Wegpunkte haben (weder eine künftige noch eine als Fallback nutzbare Etappe ist renderbar) / When der Nutzer den Vorschau-Tab ohne explizites Datum öffnet / Then zeigt die Vorschau eine Fehlermeldung, deren Text das Wort „waypoint" enthält, statt in einen unklaren oder textlosen Fehlerzustand zu laufen.
  - Test: Vorschau für einen Trip aufrufen, dessen sämtliche Etappen `< 2` Wegpunkte haben, und prüfen, dass die resultierende HTTP-404-`detail` „waypoint" enthält (case-insensitive).
  - Test-Name: `tests/tdd/test_epic_140_preview_endpoints.py::TestIssue990WaypointSkip::test_ac4_all_stages_without_waypoints_error_contains_waypoint`

- **AC-5:** Given ein Trip mit ausschließlich normal-renderbaren Etappen (jede Etappe hat mindestens 2 Wegpunkte) / When der Nutzer die Vorschau ohne explizites Datum öffnet / Then bleibt das bestehende Auswahlverhalten unverändert — es wird weiterhin die erwartete Etappe (nächste künftige bzw. im Fallback die erste Etappe) angezeigt, keine Regression.
  - Test: Vorschau für das bestehende Fixture `gr221-mallorca` (alle 4 Etappen mit je 4 Wegpunkten, Daten in der Vergangenheit → Fallback-Zweig greift) aufrufen und prüfen, dass weiterhin die erste Etappe korrekt gerendert wird — deckt den bestehenden Test `test_resolve_target_date_returns_first_future_stage` als Regressionsschutz ab.
  - Test-Name: `tests/tdd/test_epic_140_preview_endpoints.py::TestIssue990WaypointSkip::test_ac5_fully_renderable_trip_selection_unchanged`

## Known Limitations

- `src/services/trip_segments.py` (`convert_trip_to_segments`) bleibt bewusst
  unverändert. Es ist die geteilte SSoT für die Waypoint-Mindestschwelle und
  wird auch vom Alert-Pfad (`TripAlertService`) genutzt — der Fix referenziert
  diese Schwelle, dupliziert sie aber nicht in `preview_service.py`.
- Der E2E-Seed (`frontend/e2e/global.setup.ts:83-88`, Stage `e2e-stage-3` mit
  `waypoints: []`) wird absichtlich NICHT gefixt. Er dient bewusst als
  Regressionsfall dafür, dass die neue, spezifische Wegpunkt-Meldung im
  E2E-Lauf weiterhin ausgelöst und sichtbar wird — ein Fix des Seeds würde
  diesen Testpfad stumm machen.
- Der Fix ändert nur den Fehlertext und die Etappen-Auswahl-Reihenfolge, nicht
  das HTTP-Status-Code-Mapping (`LookupError`→404 bleibt bestehen, konsistent
  mit AC-3 aus `docs/specs/modules/preview_service.md`).
- Trip komplett ohne Etappen (`stages=[]`) bleibt separat behandelt:
  ValueError→422 (unverändert seit vor dem Fix), NICHT der
  waypoint-LookupError→404-Pfad — das war ursprünglich in dieser Spec unklar
  formuliert und wurde durch einen Adversary-Fund (F001) klargestellt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix innerhalb einer bestehenden Methode
  (`_resolve_target_date` / `_build_report`), keine neue Komponente, kein
  neuer Datenfluss, kein neuer externer Vertrag — die bestehende
  Frontend-Fehlererkennung aus #421 und das bestehende Exception-Mapping in
  `api/routers/preview.py` bleiben unverändert. Es entsteht keine
  architekturrelevante Entscheidung, die eine ADR rechtfertigt.

## Changelog

- 2026-07-11: Implementiert, Adversary-Fund F001 (Trip mit stages=[] fälschlich als Wegpunkt-Fall behandelt) im Fix-Loop 1 behoben, VERIFIED, 28/28 Tests grün
- 2026-07-11: Spec erstellt (Issue #990)
