# Context: fix-990-preview-empty-waypoints

## Request Summary
Trip-Detail Vorschau-Tab zeigt bei Etappen mit <2 Wegpunkten die generische
Fehlermeldung "Vorschau konnte nicht geladen werden" statt der spezifischen
Wegpunkt-Hinweismeldung — weil `_resolve_target_date` die früheste Etappe
≥heute wählt, ohne zu prüfen, ob sie renderbar ist.

## Root-Cause (verifiziert gegen aktuellen Code, Issue-Kommentar 2026-07-09)

1. `PreviewService._resolve_target_date` (`src/services/preview_service.py:52-71`)
   wählt die erste Stage mit `date >= today`, unabhängig von Wegpunkt-Anzahl.
2. `convert_trip_to_segments` (`src/services/trip_segments.py:106-123`) liefert
   `[]`, wenn `len(stage.waypoints) < 2`.
3. `_build_report` (`preview_service.py:96-100`) wirft bei leeren Segments
   `LookupError(f"Keine Stage am {target} im Trip '{trip.id}'")` — Text
   irreführend, denn die Stage existiert, hat nur keine Wegpunkte.
4. Router (`api/routers/preview.py:40-47`) mappt `LookupError` → HTTP 404.
5. Frontend `friendlyPreviewError` (`frontend/src/lib/components/preview/previewHelpers.ts:47-57`)
   zeigt `PREVIEW_ERROR_NO_WAYPOINTS` nur, wenn `detail` das Wort „waypoint"
   enthält (case-insensitive). Der aktuelle deutsche Text tut das nicht →
   generische Meldung.
6. `demo=1` (Beispieldaten) tauscht nur den Wetter-Provider (Zeile 102-107)
   — der Leere-Segmente-Check passiert **davor**, daher hilft Demo-Modus nicht.

## Wichtiger Zusatzfund

`docs/specs/modules/issue_421_preview_error_message.md` (Issue #421, done,
2026-05-27) hat `friendlyPreviewError` explizit für den Fall „Stage hat keine
Wegpunkte" gebaut — mit der **Annahme**, das Backend liefere
`{"detail":"Stage must have at least one waypoint"}` (422). Tatsächlich liefert
`preview_service.py` in diesem Fall aber die generische 404-Meldung ohne
„waypoint" im Text. #421 und #990 sind zwei Hälften desselben Bugs — #421 hat
die Frontend-Seite vorbereitet, aber die Backend-Seite hat nie den erwarteten
Text/Code geliefert.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/preview_service.py` | `_resolve_target_date` (Etappen-Wahl), `_build_report` (Fehler-Text) — Kern-Fix hier |
| `src/services/trip_segments.py` | `convert_trip_to_segments` — liefert `[]` bei <2 Wegpunkten, unverändert (SSoT, wird auch von Alerts genutzt) |
| `frontend/src/lib/components/preview/previewHelpers.ts` | `friendlyPreviewError` — bereits vorhanden, matcht „waypoint" im `detail`-Text, KEINE Änderung nötig wenn Backend-Text angepasst wird |
| `api/routers/preview.py` | Mappt `LookupError`→404, `ValueError`→422 — unverändert, nur Fehlertext-Inhalt ändert sich |
| `frontend/e2e/global.setup.ts:83-88` | Seed-Stage `e2e-stage-3` hat `waypoints: []` — Testtrip löst den Bug reproduzierbar aus |
| `docs/specs/modules/issue_421_preview_error_message.md` | Bereits done, definiert Frontend-Vertrag: `detail` muss „waypoint" enthalten |
| `docs/specs/modules/preview_service.md` | Bestehende Spec für `PreviewService`, AC-3 beschreibt aktuelles (fehlerhaftes) Verhalten — muss aktualisiert werden |

## Existing Patterns

- `trip.get_stage_for_date(d)` (`src/app/trip.py:230-235`) — exakte Datums-Suche, kein Waypoint-Check.
- `trip.get_future_stages(from_date)` (`src/app/trip.py:237-242`) — liefert sortierte künftige Stages, ließe sich für „nächste renderbare Stage" wiederverwenden.
- Waypoint-Mindestanzahl (2) ist bereits an einer Stelle kodifiziert: `trip_segments.py:119` (`len(stage.waypoints) < 2`). Kein zweites Vorkommen dieser Schwelle im Code — Fix sollte sie nicht duplizieren, sondern denselben Gedanken (>=2 Wegpunkte) in der Etappen-Wahl wiederverwenden.

## Dependencies

- **Upstream:** `PreviewService._resolve_target_date` wird nur innerhalb `preview_service.py` selbst aufgerufen (3 Call-Sites: `render_email_preview`, `render_sms_preview`, `render_telegram_preview`) — kein externer Konsument.
- **Downstream:** `api/routers/preview.py` (Exception→HTTP-Mapping), Frontend-Frames (`EmailIframe.svelte`, `SmsPhoneFrame.svelte`) über `friendlyPreviewError`.

## Risks & Considerations

- **Edge Case „alle künftigen Etappen leer":** Wenn *keine* künftige Stage ≥2 Wegpunkte hat, muss der Fix trotzdem eine verständliche Fehlermeldung liefern (nicht in eine Endlosschleife/Exception ohne Text laufen).
- **Explizites `target_date`-Query-Param:** Wenn der Aufrufer ein konkretes Datum übergibt (nicht nur Auto-Resolve), und genau diese Stage <2 Wegpunkte hat, sollte der Fehlertext ebenfalls „waypoint" enthalten (gleicher Fix-Punkt in `_build_report`, nicht nur in `_resolve_target_date`).
- **Fallback-Zweig** (`preview_service.py:68-70`, „keine Stage ≥heute" → nimm erste Stage überhaupt) hat denselben Blind-Fleck und sollte konsistent mit demselben Renderbar-Kriterium behandelt werden.
- **`trip_segments.py` bleibt unverändert** — geteilte SSoT mit Alert-Pfad (`TripAlertService`), Änderungen dort hätten größeren Blast Radius als nötig.
- **E2E-Seed-Fix** (`global.setup.ts`) behebt nur den Testtrip, nicht die Bug-Klasse — trotzdem sinnvoll, damit der E2E-Lauf nicht mehr tagesabhängig „sporadisch" grün/rot ist.

## Existing Specs
- `docs/specs/modules/preview_service.md` — AC-3 muss nach Fix aktualisiert werden (Unterscheidung „keine Stage am Datum" vs. „Stage ohne Wegpunkte")
- `docs/specs/modules/issue_421_preview_error_message.md` — Known Limitations Abschnitt referenziert genau diese Backend-Lücke implizit, jetzt geschlossen

## Analysis

### Type
Bug (Label `type:bug`)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/preview_service.py` | MODIFY | `_resolve_target_date`: nicht-renderbare Stages (<2 Wegpunkte) überspringen, in beiden Zweigen (Zukunfts-Suche + Fallback „erste Stage überhaupt"); `_build_report`: Fehlertext bei explizitem `target_date` differenzieren zwischen „keine Stage am Datum" (generisch) und „Stage existiert, zu wenig Wegpunkte" (Text muss „waypoint" enthalten, matcht Frontend-Regex aus #421) |
| `tests/tdd/test_epic_140_preview_endpoints.py` | MODIFY | Neue Tests: Skip-Verhalten bei nicht-renderbarer Stage, Fehlertext-Differenzierung, Edge-Case „alle Stages <2 Wegpunkte" |
| `frontend/src/lib/components/preview/previewHelpers.ts` | KEINE ÄNDERUNG | `friendlyPreviewError` matcht bereits „waypoint" case-insensitive — kein Touch nötig |
| `frontend/e2e/global.setup.ts` | OPTIONAL | Seed-Stage bleibt absichtlich leer als E2E-Regressionsfall für die neue Frontend-Meldung (kein Fix am Seed selbst) |
| `docs/specs/modules/preview_service.md` | MODIFY | AC-3 aktualisieren |

### Scope Assessment
- Files: 2 Pflicht (preview_service.py + Tests), optional 1 Doku
- Estimated LoC: ~100-150 (inkl. Tests)
- Risk Level: LOW — `_resolve_target_date` hat nur 3 interne Call-Sites, kein externer Konsument. Bestehender Test `test_resolve_target_date_returns_first_future_stage` gegen Fixture `gr221-mallorca` empirisch geprüft: alle 4 Stages haben 4 Wegpunkte (Datum in Vergangenheit → Fallback-Zweig greift, bleibt aber renderbar) → Test bricht durch den Fix nicht.

### Technical Approach
Zwei-Zweig-Fix in `preview_service.py`:
1. `_resolve_target_date` überspringt Stages mit `len(waypoints) < 2` in Zukunfts-Suche UND Fallback; findet sich gar keine renderbare Stage, wirft die Methode selbst einen Fehler mit „waypoint" im Text (statt eine nicht-renderbare Stage zurückzugeben, die erst später in `_build_report` mit irreführendem Text scheitert).
2. `_build_report` differenziert beim expliziten `target_date`-Fall (kein Auto-Resolve, User hat Datum explizit gewählt): `trip.get_stage_for_date(target)` prüfen — existiert keine Stage → generischer „keine Stage am Datum"-Text (echter 404-Fall, kein „waypoint" nötig); existiert die Stage, aber `convert_trip_to_segments` liefert `[]` → Text muss „waypoint" enthalten.
3. Waypoint-Schwelle (`< 2`) nicht duplizieren — aus `trip_segments.py` referenzieren statt neu kodifizieren.
4. `trip_segments.py` selbst bleibt unverändert (geteilte SSoT mit Alert-Pfad `TripAlertService`).

### Dependencies
Reihenfolge: (1) `_build_report`-Fehlertext für expliziten `target_date`-Fall, (2) `_resolve_target_date` Waypoint-Filter für Auto-Resolve, (3) Unit-Tests für beide Fälle.

### Open Questions
- [ ] Soll bei „gar keine renderbare Stage im ganzen Trip" ein `ValueError` (→422) oder `LookupError` (→404) geworfen werden? Empfehlung: `LookupError`→404 bleibt konsistent mit AC-3 der bestehenden Spec, nur der Text ändert sich.
