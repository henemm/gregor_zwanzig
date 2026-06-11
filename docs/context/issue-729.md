# Context: Issue #729 — render_compact(segments=[]) wirft IndexError

## Request Summary
`render_compact` greift `segments[0]` ohne Leer-Prüfung (Z.87, 150, 151) → bei leerer
Segment-Liste `IndexError`. Defensiver Guard soll einen minimalen Body statt Exception liefern.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compact.py` | Enthält `render_compact` — hier der Fix (Guard) |
| `src/services/trip_report_scheduler.py:371` | Bestehender Vorab-Guard (`if not segments: return False`) — kein Prod-Risiko aktuell |
| `tests/tdd/test_issue_722_email_compact.py` | Bestehende #722-Tests; neuer RED-Test für Leerfall hier |
| `docs/specs/modules/issue_722_email_compact_format.md` | Spec des Renderers (#722) |

## Existing Patterns
- Pure-Function-Renderer, baut `lines: list[str]`, gibt ASCII-String zurück
- Scheduler guardet leere Segmente bereits VOR dem Renderer (Defense-in-Depth fehlt im Renderer selbst)

## Dependencies
- Upstream: `app.models.SegmentWeatherData`, `UnifiedWeatherDisplayConfig`
- Downstream: `render_email` (compact-Pfad), Scheduler

## Risks & Considerations
- LOW-Priorität, kein aktuelles Prod-Risiko (Scheduler-Guard greift vorher)
- Reiner Renderer-Härtungs-Fix — keine Schema-Änderung, keine Mandanten-Pfade betroffen
- Guard darf bestehenden Nicht-Leer-Pfad nicht verändern (Backward Compatibility #722)
