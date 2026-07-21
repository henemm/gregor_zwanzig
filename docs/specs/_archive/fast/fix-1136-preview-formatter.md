# Mini-Spec: E-Mail-Vorschau-Regress beheben (#1136)

## Was ändert sich
- `PreviewService._render_email` (`src/services/preview_service.py:144-167`) ruft aktuell
  `scheduler._formatter.format_email(...)` auf — dieses Attribut existiert seit dem
  #1051-Refactor (ADR-0017 Slice 2) nicht mehr auf `TripReportSchedulerService`.
- Fix: `_render_email` instanziiert stattdessen direkt `TripReportFormatter()` aus
  `src.output.renderers.trip_report` — exakt das Muster, das der reguläre Versand-Pfad
  in `NotificationService.__init__` (`src/services/notification_service.py:175`) bereits
  verwendet (`self._formatter = TripReportFormatter()`).
- Der `scheduler`-Parameter wird für Segmente/Wetter/Stage-Stats weiterhin gebraucht,
  aber nicht mehr für den Formatter-Zugriff.

## Was darf sich nicht ändern
- Der Versand-Pfad (`NotificationService.send_trip_report`) bleibt unberührt.
- Die an `format_email(...)` übergebenen Parameter/Werte in `_render_email` bleiben
  inhaltlich identisch — nur die Quelle des Formatter-Objekts ändert sich.
- Kein Verhalten außerhalb der Vorschau (`render_email_preview` / `_run_pipeline`) wird
  berührt.

## Manuelle Test-Schritte
1. Auf Staging: Trip-Detail öffnen, E-Mail-Vorschau für einen bestehenden Trip aufrufen.
2. Vorschau muss ohne `AttributeError` rendern (HTML sichtbar, keine 500er-Antwort).
3. Versand-Pfad (Test-Mail auslösen) bleibt unverändert funktionsfähig.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `uv run pytest tests/tdd/test_issue_1004_ssot_callers.py::test_ac3_alle_vier_produkt_pfade_konsistent` → RED vor Fix, GREEN nach Fix
- [ ] `uv run pytest tests/tdd/test_epic_140_preview_endpoints.py` → RED vor Fix, GREEN nach Fix
