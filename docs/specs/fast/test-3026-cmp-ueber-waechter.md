# Mini-Spec: test-3026-cmp-ueber-waechter

Issue #3026 (Nebenbefund F001 aus #2783, Epic #2644). Reine Test-Ergänzung, kein Produktionscode.

## Was ändert sich
- Neuer Wirkpfad-Test für die Metrik-Auflösung im Alarm (`_resolve_metric_id` in
  `src/output/renderers/alert/project.py`). Einziges mehrdeutiges Feld im Katalog ist
  `temp_min_c` (Metriken `temperature` mit cmp „über“ und `temperature_cold` mit cmp „unter“).
- Der Test geht über den öffentlichen Weg `to_alert_message` mit einem Δ-Ereignis (ohne Ampel-Art)
  auf `temp_min_c`:
  - Richtung `increase` → das Alarm-Ereignis trägt die Metrik `temperature` (cmp „über“).
  - Richtung `decrease` → das Alarm-Ereignis trägt die Metrik `temperature_cold` (cmp „unter“).
- Zusätzlich die Funktion direkt: `_resolve_metric_id("temp_min_c", "increase") == "temperature"`
  und `… "decrease") == "temperature_cold"`, je mit Prüfung, dass `cmp` der gewählten Metrik passt.

## Was darf sich nicht ändern
- Kein Produktionscode wird geändert; Alarmtexte bleiben byte-identisch.
- `cmp`-Werte „über“/„unter“ sind Protokoll-Token und werden nie übersetzt (ADR-0104).
- Ampel-Ereignisse auf `temp_min_c` meinen weiter immer die Kälteseite (#2793 S2b).

## Acceptance Criteria
**AC-1:** Given ein Δ-Alarmereignis auf `temp_min_c` mit Richtung `increase`, When daraus die Alarmnachricht gebaut wird, Then trägt das Ereignis die Metrik `temperature` (cmp „über“).
**AC-2:** Given dasselbe Ereignis mit Richtung `decrease`, When die Alarmnachricht gebaut wird, Then trägt das Ereignis die Metrik `temperature_cold` (cmp „unter“).
**AC-3:** Given die Mutation `"über"` → `"ueber"` in `_resolve_metric_id`, When der neue Test läuft, Then wird er rot (Mutations-Gegenprobe).

## Manuelle Test-Schritte
1. Neuen Test einzeln ausführen → grün.
2. Mutation `"über"` → `"ueber"` (String-Ersetzung mit Sicherungskopie) → Test rot; zurücksetzen.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `tests/tdd/test_issue_3026_resolve_metric_id_richtung.py`
