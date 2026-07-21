# Mini-Spec: fix-827-812-alert-throttle-dedup

Issues: #827, #812

## Was ändert sich

### #827 — Radar-Alert: Throttle/alert_log nur bei tatsächlicher Zustellung

- In `check_radar_alerts` (`src/services/trip_alert.py`, ~Z.686–693) werden `_append_alert_log`
  und `_radar_throttle_times`/`_save_radar_throttle` auch dann geschrieben, wenn beide Kanäle
  (`send_email`, `send_telegram`) für den Trip deaktiviert sind → stummes Throttling.
- Fix: `delivered`-Flag einführen (default `False`). Es wird `True`, wenn mindestens einer
  der Versand-Zweige tatsächlich ausgeführt wurde (E-Mail- oder Telegram-Block betreten,
  kein Exception-Pfad). Recording (`_append_alert_log` + Throttle) nur bei `delivered=True`.
- Bei transienten Fehlern (Exception im Versand-Block) bleibt Recording-Verhalten wie bisher
  (F001-Semantik: Fehler ≠ bewusste Deaktivierung).

### #812 — ActiveAlertableMetricIDs dedupliziert nicht

- `ActiveAlertableMetricIDs` (`internal/model/trip.go:155-187`) gibt bei Duplikat-`metric_id`
  in `display_config.metrics` denselben Wert mehrfach zurück → `SyncAlertRules` erzeugt zwei
  Regeln für dieselbe Metrik.
- Fix: `seen`-Set in der Loop; jede Metrik-ID wird max. einmal an `ids` angehängt.
- Test: Go-Unit-Test mit Duplikat-Input → genau eine Regel im Output von `SyncAlertRules`.

## Was darf sich nicht ändern

- F001-Semantik: Bei transienten SMTP-/Netzfehlern bleibt das Recording-Verhalten unverändert
  (kein Regressions-Risiko auf den normalen Alert-Pfad).
- `SyncAlertRules`-Logik (Threshold/Kind-Migration, Delta-wins-absolute) bleibt unberührt;
  nur die Eingabe-Liste wird dedupliziert.
- Keine Breaking Changes an API-Signaturen.

## Manuelle Test-Schritte

1. Trip mit deaktivierten Kanälen (`send_email=False`, `send_telegram=False`) konfigurieren.
2. Radar-Alert manuell triggern (oder Unit-Test mit Mocked-Kanälen).
3. Prüfen: `radar_alert_throttle.json` und `alert_log.json` dürfen **nicht** aktualisiert werden.
4. Trip mit aktiviertem E-Mail-Kanal: Alert triggern → Recording muss weiterhin schreiben.

## Acceptance Criteria

**AC-1:** Given ein Trip mit `send_email=False` und `send_telegram=False`, When ein Radar-Alert ausgelöst wird, Then werden `alert_log.json` und `radar_alert_throttle.json` nicht geschrieben.

**AC-2:** Given ein Trip mit aktiviertem E-Mail-Kanal, When ein Radar-Alert ausgelöst wird, Then werden `alert_log.json` und `radar_alert_throttle.json` wie bisher geschrieben (keine Regression).

**AC-3:** Given `display_config.metrics` enthält dieselbe `metric_id` zweimal (enabled=true), When `ActiveAlertableMetricIDs` aufgerufen wird, Then enthält die Rückgabe die ID genau einmal und `SyncAlertRules` erzeugt genau eine Regel.

## Inline-Tests (werden während Implementierung geschrieben)

- [ ] `test_radar_alert_no_recording_when_all_channels_disabled` — Python, `trip_alert.py`
- [ ] Go-Test `TestActiveAlertableMetricIDsDeduplicated` — doppelter metric_id → exakt 1 Regel
