# Mini-Spec: #914 Slice 4 — Alert-SMS-Versand anschließen

## Was ändert sich

- `src/services/trip_alert.py`: `render_sms` wird aus `output.renderers.alert.render` importiert
- In `_dispatch_deviation_alert`: SMS-Block nach dem Telegram-Block einfügen —
  `if send_sms and self._settings.can_send_sms()`: `render_sms(msg)` aufrufen, `SMSOutput` senden
- `send_sms = "sms" in effective_channels` als Steuervariable (analog zu `send_email`/`send_telegram`)
- F003-Kommentar entfällt (SMS ist jetzt zustellbar); `known_channels` um `"sms"` erweitern

## Was darf sich nicht ändern

- Email- und Telegram-Dispatch bleiben unverändert
- `render_sms`, `SMSOutput`, `can_send_sms()` werden nicht verändert — nur eingebunden
- Bestehende Tests bleiben grün

## Acceptance Criteria

**AC-1:** Given ein Trip mit `send_sms=True` und gültigem `sms_api_key`/`sms_to`,
When ein Abweichungs-Alert ausgelöst wird,
Then wird `render_sms(msg)` aufgerufen und der Text via `SMSOutput.send()` verschickt
(verifiziert durch direkten Aufruf von `_dispatch_deviation_alert` mit SMS-Settings).

**AC-2:** Given ein Trip mit `send_sms=False` oder fehlendem API-Key,
When ein Alert ausgelöst wird,
Then wird `SMSOutput` nicht instantiiert (kein Fehler, kein Versuch).

**AC-3:** Given SMS-Versand schlägt fehl (z.B. HTTP-Fehler),
When `SMSOutput.send()` wirft `OutputError`,
Then wird der Fehler geloggt, aber Email/Telegram laufen durch (`deliverable_any` bleibt True).

## Manuelle Test-Schritte

1. SMS-Config in `.env` setzen (`GZ_SMS_API_KEY`, `GZ_SMS_TO`)
2. Trip mit `send_sms=True` konfigurieren
3. Alert manuell triggern (oder Unit-Test mit SMS-Settings)
4. Log prüft auf "SMS sent" — kein "not yet deliverable"

## Inline-Test

- [ ] `test_dispatch_sends_sms_when_configured`: SMS-Settings + `send_sms=True` → `SMSOutput.send` wird aufgerufen
- [ ] `test_dispatch_skips_sms_when_not_configured`: `send_sms=False` → `SMSOutput` nicht instantiiert
- [ ] `test_dispatch_sms_error_does_not_block_email`: SMS wirft, Email läuft trotzdem durch
