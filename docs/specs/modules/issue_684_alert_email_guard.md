---
entity_id: issue_684_alert_email_guard
type: module
created: 2026-06-09
updated: 2026-06-09
status: active
version: "1.0"
tags: [alert, deliverability, multi-channel, bugfix]
---

# Issue #684 — Symmetrischer `can_send_email()`-Guard im Alert-Versand

## Approval

- [x] Approved (PO 'go', 2026-06-09)

## Purpose

Verhindert False-Positive-Zustellung von Briefing-Alerts: Throttle-Sperrzeit und Cockpit-Alert-Log („Alarme · letzte 24 h") dürfen nur gesetzt werden, wenn mindestens ein für den Alert **effektiver** Kanal tatsächlich **konfiguriert/zustellbar** ist. Der E-Mail-Pfad erhält denselben `can_send_email()`-Guard, den Telegram- und Radar-Pfad bereits haben.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._send_alert`, `TripAlertService.check_and_send_alerts`

## Estimated Scope

- **LoC:** ~25
- **Files:** 1 (`src/services/trip_alert.py`) + Tests
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings.can_send_email` | function | Prüft SMTP-Konfiguration (host/user/pass/mail_to) |
| `Settings.can_send_telegram` | function | Prüft Telegram-Konfiguration |
| `TripAlertService._effective_alert_channels` | method (#638) | Liefert effektive Kanäle pro Trip |

## Implementation Details

```
_send_alert(...) -> bool   # vorher: -> None
    effective_channels = self._effective_alert_channels(trip)
    send_email    = "email" in effective_channels
    send_telegram = "telegram" in effective_channels

    deliverable_any = False

    # E-Mail: NEU mit can_send_email()-Guard (Symmetrie zu Telegram/Radar)
    if send_email and self._settings.can_send_email():
        deliverable_any = True
        try:
            EmailOutput(...).send(...)        # best-effort: Send-Fehler nur geloggt
        except Exception as e:
            logger.error(...)

    if send_telegram and self._settings.can_send_telegram():
        deliverable_any = True
        try:
            TelegramOutput(...).send(...)
        except Exception as e:
            logger.error(...)

    # undeliverable-Logging (sms/unbekannt) unverändert
    return deliverable_any

check_and_send_alerts(...):
    ...
    delivered = self._send_alert(trip, fresh_weather, significant)
    if not delivered:
        logger.warning("Alert not deliverable on any effective channel for trip ... — kein Throttle/Log")
        return False
    # Snapshot-Update + Throttle (Z.168) + Alert-Log (Z.174) + return True
    #   nur noch im delivered-Fall
```

**Semantik „zustellbar":** Kanal ist in `effective_channels` UND `can_send_X()` == True. Der eigentliche Send bleibt **best-effort** — ein SMTP-/Netzfehler bei konfiguriertem Kanal koppelt das Recording NICHT (Anti-Pattern #656, Rate-Limit-Flakiness). Nur „Kanal gar nicht konfiguriert" unterdrückt Throttle/Log.

## Expected Behavior

- **Input:** Trip mit `effective_channels`, Settings mit/ohne SMTP- bzw. Telegram-Konfiguration.
- **Output:** `check_and_send_alerts` gibt `True` nur bei mind. einem zustellbaren effektiven Kanal.
- **Side effects:** Throttle (`_last_alert_times` + Persistenz), Alert-Log (`_append_alert_log`), Snapshot-Update — alle nur im zustellbaren Fall.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen effektive Alert-Kanäle ausschließlich `email` sind, und Settings ohne SMTP-Konfiguration (`can_send_email()==False`), aber mit konfiguriertem Telegram / When `check_and_send_alerts` mit signifikanten Wetter-Changes läuft / Then gibt die Methode `False` zurück, es wird **kein** Alert-Log-Eintrag geschrieben und die Throttle-Sperrzeit (`_last_alert_times`) bleibt für diesen Trip unverändert (kein neuer Zeitstempel).
  - Test: Echter `TripAlertService` mit Real-Settings (SMTP-Felder leer), email-only `alert_rules`/`effective_channels`, echte Snapshot-Daten mit erzwungenen Changes; Rückgabewert + Alert-Log-Datei-State + Throttle-Dict vor/nach prüfen (Verhaltensnachweis, kein Dateiinhalt-Grep auf Quellcode).

- **AC-2:** Given ein Trip mit effektivem Kanal `email` und vollständig konfiguriertem SMTP (`can_send_email()==True`) / When `check_and_send_alerts` mit signifikanten Changes läuft / Then wird die E-Mail tatsächlich versendet und per IMAP im Test-Postfach (`gregor-test@henemm.com`) nachweisbar empfangen, die Methode gibt `True` zurück, ein Alert-Log-Eintrag wird geschrieben und die Throttle-Sperrzeit wird gesetzt.
  - Test: Mock-freier E2E mit echtem Stalwart-SMTP/IMAP (Referenz `tests/tdd/test_html_email.py`); Empfang + Rückgabewert + Alert-Log + Throttle verifizieren.

- **AC-3:** Given ein Trip mit effektivem Kanal `email`, konfiguriertem SMTP, aber einem transienten Send-Fehler (z.B. Server-seitig nicht erreichbar) / When der Alert versendet wird / Then bleibt das Recording erhalten (best-effort): Methode gibt `True` zurück, Throttle + Alert-Log werden gesetzt — das Recording ist NICHT an den Send-Erfolg gekoppelt (kein #656-Anti-Pattern).
  - Test: Echter `TripAlertService`, SMTP-Felder konfiguriert aber auf nicht-erreichbaren Host gezeigt (echter ConnectionError aus `EmailOutput.send`, kein Mock); Rückgabewert `True` + Throttle/Log gesetzt trotz Send-Exception.

- **AC-4:** Given ein Trip mit effektivem Kanal `telegram` (email NICHT effektiv), konfiguriertem Telegram / When `check_and_send_alerts` läuft / Then ist das bisherige Telegram-Verhalten unverändert (Rückgabe `True`, Throttle/Log gesetzt) — die Änderung ist regressionsfrei zum bestehenden Telegram-Pfad.
  - Test: Echter `TripAlertService`, telegram-only effektive Kanäle, `can_send_telegram()==True`; Rückgabewert + Recording prüfen.

## Out of Scope

- Radar-Alert-Pfad (`check_radar_alerts`, Z.520-594) — bereits korrekt (Referenz-Pattern).
- SMS-Kanal-Zustellung (weiterhin out-of-scope, nur `undeliverable`-Logging).
- Cockpit-Frontend-Anzeige (liest nur den Alert-Log, keine Änderung nötig).

## Changelog

- 2026-06-09: Initial spec — F003 aus #638-Adversary-Review (symmetrischer `can_send_email()`-Guard, Throttle/Log nur bei zustellbarem Kanal). PO 'go'.
