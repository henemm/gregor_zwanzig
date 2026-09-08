---
entity_id: user_recipient_fallback
type: bugfix
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
workflow: "fix-2144-mail-to-fallback"
tags: [auth, multi-user, email, telegram, sms, recipient-fallback, cross-tenant]
---

# User Recipient Fallback

## Approval

- [ ] Approved

## Purpose

Neue Nutzer, deren Profil kein explizites `mail_to`/`telegram_chat_id`/`sms_to` trägt,
bekommen ihre Briefings heute über den globalen `.env`-Fallback
(`GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO`) zugestellt — die zeigen auf die
Betreiber-Adresse. Diese Spec schließt den Fallback an der Quelle
(`with_user_profile()`) und macht die drei Versandkanäle robust gegen den dadurch
entstehenden „kein Empfänger bekannt"-Fall, statt an eine leere Adresse zu senden.

## Source

- **File:** `src/app/config.py`
- **Identifier:** `Settings.with_user_profile()`

## Estimated Scope

- **LoC:** ~90–150 Produktionscode (4× Go-Handler ~1 Zeile, `config.py` ~20–30 Zeilen,
  3 Kanalklassen ~15–25 Zeilen je Datei), zusätzlich ~150–250 Testcode — Summe liegt
  nahe am 250-LoC-Workflow-Limit, `loc_limit_override` ist wahrscheinlich nötig.
- **Files:** ~9 Produktionsdateien (4 Go-Handler, `config.py`, 3 Kanalklassen,
  `operations_playbook.md`) + ~6–9 Testdateien (neu/erweitert).
- **Effort:** medium (bestehendes `ChannelBlockedError`-Muster wiederverwendbar, aber
  hoher Blast Radius: Auth + alle drei Versandkanäle für alle Nutzer).

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/auth.go` | MODIFY | `RegisterHandler`: `model.User{...}` um `MailTo: req.Email` ergänzen (Passwort-Weg). |
| `internal/handler/auth_magic.go` | MODIFY | Magic-Link-Registrierung: analog `MailTo` setzen. |
| `internal/handler/auth_oauth.go` | MODIFY | OAuth-Registrierung: analog `MailTo` setzen. |
| `internal/handler/passkey.go` | MODIFY | Passkey-Registrierung (`newUser` in `PasskeyRegisterFinishHandler`, ~Zeile 536): `MailTo: entry.Email` setzen. |
| `src/app/config.py` | MODIFY | `with_user_profile()`: `mail_to`/`sms_to` und (außerhalb `force_test`) `telegram_chat_id` immer explizit setzen (auch auf `None`), statt nur bei vorhandenem Profilwert zu überschreiben. |
| `src/output/channels/email.py` | MODIFY | Empfänger-Prüfung vor Versand: fehlendes `self._to` (und kein `to`-Override) → `ChannelBlockedError(reason_code="email_no_recipient")` statt Versand an `[None]`. |
| `src/output/channels/telegram.py` | MODIFY | Analoge Prüfung für `chat_id` → `ChannelBlockedError(reason_code="telegram_no_chat_id")`. |
| `src/output/channels/sms.py` | MODIFY | `_validate_config()`/`_resolve_recipient()` differenzieren: fehlender `sms_to` bekommt eigenen `reason_code="sms_no_recipient"`, getrennt von fehlender API-Konfiguration. |
| `docs/reference/operations_playbook.md` | MODIFY (Doku, zählt nicht gegen LoC-Limit) | Fallback-Passage korrigieren: Skip mit Log/`reason_code` statt globaler Fallback. |
| Tests (neu/erweitert, je Bereich) | CREATE/MODIFY | Je Registrierungsweg, `with_user_profile()`-Unit-Tests für alle drei Felder, Kanal-Guard-Tests, Zwei-Nutzer-Integrationstest, Regressionstest Compare-Preset-Pfad. |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/channels/base.py` (`ChannelBlockedError`, `OutputConfigError`) | Basisklasse | Bestehendes Sperr-Muster mit `reason_code` — wird für Email/Telegram/SMS wiederverwendet, nicht neu erfunden. |
| `src/output/channels/premium_sms.py` (`_resolve_recipient`) | Referenzmuster | Zeigt das etablierte „kein Empfänger bekannt ⇒ `ChannelBlockedError`"-Vorgehen, das diese Spec auf Email/Telegram/SMS überträgt. |
| `src/services/notification_service.py` (`_record_block_reason_code`, `blocked_channels`/`blocked_reason_codes`) | Aufrufer | Fängt jede Exception mit `reason_code`-Attribut bereits generisch ab und bucht sie in `NotificationResult` — keine Änderung an diesem Buchungsmechanismus nötig, er greift automatisch, sobald die Kanäle `ChannelBlockedError` werfen. |
| `internal/store/user.go` (`SaveUser`) | Schreibpfad | Schreibt `user.json` komplett neu bei der Registrierung (kein Read-Modify-Write nötig, Datei existiert noch nicht). |
| `src/services/scheduler_dispatch_service.py:412-431` | Abgrenzung | Compare-Preset-Versand hat bereits einen eigenen, bewusst unveränderten `ValueError`-Guard (#1452) für fehlenden `mail_to` — bleibt von dieser Spec unangetastet. |
| `docs/specs/modules/user_auth_endpoints.md` | Verwandte Spec | RegisterHandler-Spec, kennt bisher kein `MailTo`-AC — diese Spec ergänzt das Verhalten, ohne die bestehende Spec zu ersetzen. |

## Implementation Details

**Go — vier Registrierungswege setzen `MailTo`:**

```go
// internal/handler/auth.go, auth_magic.go, auth_oauth.go, passkey.go
newUser := model.User{
    Email:  email,   // bereits vorhanden
    MailTo: email,   // NEU — dieselbe Adresse, mit der sich der Nutzer registriert
    // ... übrige Felder unverändert
}
```

Bei `passkey.go` liegt die E-Mail-Adresse bereits als `entry.Email` vor (validiert mit
`@`-Pflicht im Begin-Handler) und wird im Finish-Handler bereits für `newUser.Email`
verwendet — `MailTo: entry.Email` ist eine reine Ergänzung derselben Zeile, keine neue
Datenquelle.

**Python — `with_user_profile()` verliert den stillen Fallback:**

```python
overrides["mail_to"] = profile.get("mail_to") or None
overrides["sms_to"] = profile.get("sms_to") or None
if not force_test:
    overrides["telegram_chat_id"] = profile.get("telegram_chat_id") or None
# bestehender force_test-Zweig (Zeile ~398) bleibt sonst unverändert:
# Test-/Staging-Nutzer nutzen weiterhin ausschließlich for_testing()s Chat-ID.
```

Die bisherige Frühausstiegs-Bedingung `if not overrides: return base` entfällt für
diese drei Felder faktisch, weil `overrides` jetzt immer mindestens `mail_to` und
`sms_to` trägt — `GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO` wirken damit nur noch
dort, wo `with_user_profile()` nie aufgerufen wird (Legacy-CLI).

**Kanäle — sauberer Abbruch statt Versand an leere Adresse:**

Analog zu `PremiumSmsOutput._resolve_recipient()`: vor dem eigentlichen Versand prüft
jeder Kanal seinen aufgelösten Empfänger und wirft bei Fehlen `ChannelBlockedError`
mit einem neuen, kanalspezifischen `reason_code` (`email_no_recipient`,
`telegram_no_chat_id`, `sms_no_recipient`) statt eine leere/`None`-Adresse an den
Transport zu reichen. `notification_service.py` bucht das automatisch über den
bestehenden `_record_block_reason_code()`-Mechanismus in `blocked_channels`/
`blocked_reason_codes` — dort ist keine Änderung nötig.

Diese Kanal-Guards sind nötig, weil nicht jeder Versandpfad vorab mit
`can_send_email()`/`can_send_telegram()`/`can_send_sms()` gated ist: die
Alarm-/Compare-Pfade tun das bereits (dort ist der Fix bereits strukturell wirksam,
sobald `with_user_profile()` `None` statt des globalen Werts liefert), der
Trip-Briefing-Hauptpfad (`notification_service.py`, E-Mail-Zweig ~Zeile 552) ruft
`EmailOutput.send()` dagegen unconditional auf — ohne Kanal-Guard würde er nach der
`config.py`-Änderung an eine leere Adresse zu senden versuchen, statt sauber zu
überspringen.

## Expected Behavior

- **Input:** Registrierung über einen der vier Wege; anschließender Versandversuch für
  einen Trip mit aktivierten Kanälen, für die das Profil keinen expliziten Empfänger
  gesetzt hat.
- **Output:** `user.json` enthält `mail_to = <Registrierungs-E-Mail>` sofort nach
  Registrierung. Versandversuche mit fehlendem Empfänger werden pro Kanal sauber mit
  `ChannelBlockedError`/`reason_code` übersprungen — nicht an den Betreiber oder einen
  anderen Nutzer zugestellt, kein harter Absturz.
- **Side effects:** `GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO` verlieren ihre
  Empfänger-Rolle für alle Pfade, die über `with_user_profile()` laufen (praktisch
  alle produktiven Versandpfade); sie bleiben nur für die Legacy-CLI wirksam. Der
  Compare-Preset-Pfad (#1452) bleibt unverändert (eigener `ValueError`-Guard).

## Acceptance Criteria

- **AC-1:** Given ein neuer Nutzer registriert sich über einen der vier Wege (Passwort, Magic-Link, OAuth, Passkey) / When das Nutzerkonto angelegt und `user.json` geschrieben wird / Then enthält `user.json` das Feld `mail_to` mit der bei der Registrierung verwendeten E-Mail-Adresse — für alle vier Wege, nicht nur einen.
  - Test: vier Tests (je Registrierungsweg), die den jeweiligen HTTP-Handler mit isoliertem Test-Store aufrufen und danach `mail_to` im gespeicherten `User`-Objekt bzw. `user.json` prüfen.

- **AC-2:** Given ein Nutzerprofil (`user.json`) ohne `mail_to`- und ohne `sms_to`-Feld, `GZ_MAIL_TO`/`GZ_SMS_TO` sind in der Umgebung auf die Betreiber-Adresse gesetzt / When `Settings.with_user_profile(user_id)` aufgerufen wird / Then hat das zurückgegebene `Settings`-Objekt `mail_to is None` und `sms_to is None` — nicht die globalen `.env`-Werte.
  - Test: neuer Unit-Test, der ein Fixture-`user.json` ohne diese Felder anlegt und `with_user_profile()` gegen `None` statt gegen den globalen Wert prüft.

- **AC-3:** Given ein Nutzerprofil ohne `telegram_chat_id`, der Nutzer ist KEIN Test-/Staging-Nutzer (`force_test` inaktiv), `GZ_TELEGRAM_CHAT_ID` ist auf den Betreiber-Chat gesetzt / When `with_user_profile()` aufgerufen wird / Then ist `telegram_chat_id is None` im Ergebnis; für einen Test-/Staging-Nutzer bleibt der bestehende `force_test`-Sonderfall unverändert (dort entscheidet weiterhin ausschließlich die Test-Chat-ID aus `for_testing()`, unabhängig vom Profilinhalt).
  - Test: neuer Unit-Test mit zwei Fällen (Normal-Nutzer vs. Test-Nutzer), der beide Verhalten explizit gegeneinander prüft.

- **AC-4:** Given `settings.mail_to` ist `None`, ein Trip hat `send_email=True` / When der Versand über `EmailOutput.send()` (bzw. `notification_service.send_trip_report`) ausgelöst wird / Then wird keine SMTP-Verbindung mit leerer/`None`-Empfängeradresse aufgebaut, sondern der Kanal wirft `ChannelBlockedError` mit einem neuen `reason_code` (`email_no_recipient`); die E-Mail geht an niemanden.
  - Test: neuer Test mit `--disable-socket` (kein echter Verbindungsversuch zulässig), der `EmailOutput(settings).send(...)` mit `mail_to=None` aufruft und `ChannelBlockedError` samt `reason_code` prüft, ergänzt um einen Test auf `notification_service.send_trip_report()`-Ebene, der bestätigt, dass `sent_channels` „email" nicht enthält und kein SMTP-Aufbau erfolgt.

- **AC-5:** Given `settings.telegram_chat_id` ist `None` / When `TelegramOutput(settings).send(...)` aufgerufen wird / Then wirft der Kanal `ChannelBlockedError` mit eigenem `reason_code` (`telegram_no_chat_id`) statt einen Request an die Telegram-API mit leerer `chat_id` zu senden.
  - Test: neuer Test mit `--disable-socket`, der die Exception samt `reason_code` prüft, ohne dass ein tatsächlicher API-Call versucht wird.

- **AC-6:** Given `settings.sms_to` ist `None`, `settings.seven_api_key` ist gesetzt (API-Konfiguration vollständig bis auf den Empfänger) / When `SMSOutput(settings).send(...)` aufgerufen wird / Then wirft der Kanal `ChannelBlockedError` mit `reason_code` (`sms_no_recipient`), erkennbar unterscheidbar von einer fehlenden API-Konfiguration (nicht mehr der bisherige undifferenzierte `OutputConfigError`, der beide Ursachen in einer Meldung vermischt).
  - Test: neuer/erweiterter Test, der die zwei Fälle „fehlender `sms_to`" vs. „fehlender `seven_api_key`" an unterschiedlichen `reason_code`-Werten unterscheidet.

- **AC-7:** Given Nutzer A hat `mail_to` im Profil gesetzt, Nutzer B ist frisch registriert und hat kein `mail_to` im Profil, beide haben einen Trip mit `send_email=True` / When der Versand für beide Nutzer nacheinander ausgelöst wird / Then erhält Nutzer A seine Mail an die eigene Adresse; für Nutzer B wird der Versand mit `ChannelBlockedError`/`reason_code` übersprungen — weder der Betreiber noch Nutzer A erhalten Nutzer B's Briefing.
  - Test: neuer Integrationstest (Kern-Schicht, `--disable-socket`/lokaler Test-Sink statt echtem SMTP), der zwei `user.json`-Fixtures anlegt und die tatsächlichen Zielempfänger beider Versandversuche gegeneinander prüft.

- **AC-8:** Given ein Compare-Preset ohne `mail_to` (Alt-Verhalten aus #1452) / When der Compare-Preset-Versand über `scheduler_dispatch_service.py` ausgelöst wird / Then wirft der Pfad weiterhin denselben `ValueError` wie vor diesem Fix — unverändertes Fehlerverhalten, kein Wechsel auf `ChannelBlockedError`/Skip für diesen Pfad.
  - Test: bestehender Test zu #1452 (Compare-Preset ohne Empfänger) läuft nach diesem Fix unverändert grün, ohne Anpassung der Assertion.

- **AC-9:** Given `docs/reference/operations_playbook.md` beschreibt aktuell nur den Override-Fall („`user.json.mail_to` überschreibt `GZ_MAIL_TO`") / When die Doku nach diesem Fix gelesen wird / Then beschreibt der Abschnitt zusätzlich den Fehl-Fall korrekt als „Skip mit Log/`reason_code`" statt als globalen Fallback auf `GZ_MAIL_TO`/`GZ_TELEGRAM_CHAT_ID`/`GZ_SMS_TO`.
  - Test: `# doc-compliance-test` — prüft, dass die Passage die Skip-Formulierung enthält und nicht mehr behauptet, ein fehlender Profilwert falle auf die globale `.env`-Adresse zurück.

## Known Limitations

- **Kein Backfill für Bestandsnutzer:** Bereits registrierte Nutzer ohne `mail_to` im
  Profil werden von diesem Fix nicht rückwirkend verändert — das korrigierte
  Verhalten (Skip statt Fehlversand) greift automatisch beim nächsten Versandversuch,
  weil `with_user_profile()` bei jedem Aufruf neu ausgewertet wird.
- **Telegram-Onboarding bleibt zweistufig:** `telegram_chat_id` wird weiterhin bei
  keinem der vier Registrierungswege gesetzt (das Feld wird erst durch eine
  Bot-Interaktion gelernt, nachträglich über den Settings-Endpoint,
  `auth.go:675`) — ein frisch registrierter Nutzer hat also bis zur ersten
  Bot-Interaktion `telegram_chat_id = None` und wird für Telegram sauber
  übersprungen, das ist beabsichtigt, kein Nebeneffekt dieses Fixes.
- **LoC-Limit:** Die Gesamtänderung (Produktionscode + Tests über 9+ Dateien) liegt
  wahrscheinlich nahe oder über dem 250-LoC-Workflow-Limit — `loc_limit_override` ist
  im Workflow-State voraussichtlich nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer Entscheidungspunkt — die Spec korrigiert eine
  Implementierungslücke gegen ein bereits dokumentiertes Prinzip (CLAUDE.md: „echte
  `user_id` aus Auth-Kontext durchreichen, niemals auf `default`/globale Werte
  zurückfallen"). Das Empfänger-Auflösungsmuster (`ChannelBlockedError` +
  `reason_code`) ist bereits etabliert (`premium_sms.py`) und wird hier nur auf drei
  weitere Kanäle übertragen, nicht neu entworfen.

## Changelog

- 2026-09-08: Initial spec created (Issue #2144)
