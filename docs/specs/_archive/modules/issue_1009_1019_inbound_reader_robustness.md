---
entity_id: issue_1009_1019_inbound_reader_robustness
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [inbound, email, telegram, robustness, security, multi-user]
---

<!-- Issue #1009 (Reprocessing-Loop) + Issue #1019 (default-Fallback-Datenleck) -->

# Issue 1009 + 1019 — Inbound-Reader Robustheit

## Approval

- [ ] Approved

## Purpose

Zwei Robustheits-/Sicherheitslücken im Inbound-Verarbeitungspfad schließen:
(#1009) eine unbehandelte Exception in der Kommando-Verarbeitung oder im
Antwortversand lässt eine E-Mail dauerhaft `UNSEEN`, was bei gleichzeitigem
Ausfall beider Mailwege zu einer Endlos-Reprocessing-Schleife führt;
(#1019) ein unbekannter Telegram-Absender wird aktuell wie ein regulärer
Nutzer verarbeitet (Fallback auf `user_id="default"`), wodurch er reale
Betreiber-Trip-Daten unter `data/users/default/` abfragen könnte. Beide Fixes
härten bestehende, bereits größtenteils robuste Pfade an ihren verbleibenden
Schwachstellen ab, ohne deren Grundarchitektur zu verändern.

## Source

- **File:** `src/services/inbound_email_reader.py` — `_process_single` (Z.94-159)
- **File:** `src/services/inbound_telegram_reader.py` — `_process_update` (Z.141-259)

> **Schicht-Hinweis:** Beide Dateien liegen in `src/services/` (Python-Core /
> Domain-Backend, läuft über `api.main:app` bzw. den Scheduler-Cronjob).
> Kein Frontend-, kein Go-API-Anteil in diesem Scope.

## Estimated Scope

- **LoC:** Produktion ~30-40, Tests ~60-100 (gesamt ~90-140)
- **Files:** 6 (2 Produktion, 2 Test, 2 Doku-Update)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripCommandProcessor.process()` (`src/services/trip_command_processor.py`) | intern | Wirft ggf. Exception, die #1009 auslöst; liefert `CommandResult` |
| `NotificationService.send_command_reply_email/telegram` | intern | Antwortversand; kann bei SMTP/Telegram-Totalausfall werfen |
| `loader.lookup_user_by_telegram_chat_id` (`src/app/loader.py`) | intern | Liefert `None` bei unbekanntem Chat — Basis für #1019-Gate |
| `Settings.with_user_profile(user_id)` (`src/app/config.py`) | intern | Liefert globale Settings zurück, wenn `user.json` fehlt (Grund für das Datenleck-Risiko bei `"default"`) |
| `docs/adr/0003-multi-tenant-isolation.md` | ADR | Grundsatzentscheidung gegen `"default"`-Fallback in authentifizierten Pfaden; thematisch einschlägig, formal nicht verletzt (Inbound ist unauthentifiziert) |
| `docs/specs/modules/issue_572_multi_user_inbound_routing.md` | Spec | Ursprungs-Spec des `"default"`-Fallbacks (AC-3/AC-4, freigegeben 2026-06-03) — wird durch diese Spec ergänzt, nicht ersetzt |

## Implementation Details

### #1009 — E-Mail: try/except/finally um Verarbeitung + Antwortversand

In `_process_single` (`src/services/inbound_email_reader.py`) umschließt ein
`try/except/finally` die Schritte 5 (`processor.process()`, Z.148-149) und 6
(`send_command_reply_email`, Z.154-155). Das `\Seen`-Flag (Z.158) wandert in
den `finally`-Zweig, sodass es in jedem Fall gesetzt wird — analog zum
bereits korrekten Offset-Pattern des Telegram-Readers (`poll_and_process`,
Z.106-110: Offset wird vor dem try fortgeschrieben, damit ein Fehler in einem
Update nicht die nächste Poll-Runde blockiert).

```python
# 5. Delegate to processor + 6. Reply — beide unter einem gemeinsamen
# try/finally, damit "Seen" in jedem Fall gesetzt wird (#1009)
try:
    result = processor.process(inbound)
    if user_settings.can_send_email() and not result.suppress_email_reply:
        self._notification_service.send_command_reply_email(result, user_settings)
    return 1
except Exception:
    logger.exception(f"Fehler bei Verarbeitung/Versand fuer trip_id={trip_id!r}")
    return 0
finally:
    imap.store(uid, "+FLAGS", "\\Seen")
```

Kein Retry, keine zusätzliche Fehler-Mail an den Absender (könnte selbst
scheitern) — Best-effort-Logging reicht, Monitoring läuft separat
(`henemm-infra/check-gregor20.sh`).

### #1019 — Telegram: Autorisierungs-Gate nach User-Resolution

In `_process_update` (`src/services/inbound_telegram_reader.py`) wird direkt
nach `_resolve_user_for_chat` (Z.166) und **vor** `_find_active_trip` (Z.169)
ein Gate eingefügt:

```python
# Resolve user-scoped settings for this chat_id
user_id, user_settings = self._resolve_user_for_chat(chat_id, settings)

# #1019: unbekannter Absender (kein User-Match) erhaelt Registrierungs-Hinweis,
# KEINE Trip-/Wetterdaten. Betreiber-Account faellt hier nie hinein, da
# `henning` regulaer per telegram_chat_id registriert ist.
if user_id == "default":
    mid = self._notification_service.send_telegram_message(
        chat_id=chat_id,
        subject="Registrierung erforderlich",
        body=(
            "Dieser Chat ist noch nicht mit einem Gregor-Zwanzig-Konto "
            "verknuepft. Sende /start gefolgt von deinem Token (zu finden "
            "im Account-Bereich auf gregor20.henemm.com)."
        ),
        settings=settings,
    )
    if mid is not None:
        self.sent_message_ids.append(mid)
    return True

# Aktiven Trip ermitteln (user-scoped)
trip = self._find_active_trip(user_id)
```

Die Antwort wird mit den **globalen** `settings` (nicht `user_settings`)
gesendet, da für einen unbekannten Chat keine user-spezifischen
Telegram-Settings existieren, die verwendet werden dürften — die Nachricht
geht direkt an die anfragende `chat_id`, unabhängig von Nutzer-Settings.

**Wortlaut zur Freigabe (PO):**

> "Dieser Chat ist noch nicht mit einem Gregor-Zwanzig-Konto verknüpft.
> Sende /start gefolgt von deinem Token (zu finden im Account-Bereich auf
> gregor20.henemm.com)."

Kurz, freundlich, nennt den `/start`-Mechanismus, verrät keine Trip- oder
Wetterdaten.

E-Mail benötigt keinen äquivalenten neuen Gate — `_authorize()` (Z.185-199)
fängt unbekannte Absender bereits vor Erreichen von `TripCommandProcessor`
ab (bestehendes, bereits getestetes Verhalten, s.
`tests/tdd/test_bug_inbound_email_loop.py`).

## Expected Behavior

- **Input (#1009):** `TripCommandProcessor.process()` oder der nachfolgende
  `send_command_reply_email`-Call wirft eine Exception (z.B. weil beide
  Mailwege gleichzeitig ausfallen).
- **Output (#1009):** Die E-Mail wird trotzdem als `\Seen` markiert, der
  Fehler wird geloggt, kein Reprocessing beim nächsten Poll-Zyklus.
- **Input (#1019):** Ein Telegram-Update kommt von einer `chat_id`, für die
  `lookup_user_by_telegram_chat_id` keinen Treffer liefert.
- **Output (#1019):** Der Absender erhält den Registrierungs-Hinweis, keine
  Trip- oder Wetterdaten werden geladen oder verschickt.
- **Side effects:** Keine Änderung am Erfolgspfad in beiden Readern; keine
  Änderung an `list_all_user_ids`/`lookup_user_by_*` selbst.

## Acceptance Criteria

- **AC-1 (korrigiert nach RED-Phase-Befund):** Given eine eingehende E-Mail
  mit gültigem Trip-Bezug, bei der `TripCommandProcessor.process()` oder
  `send_command_reply_email` eine Exception wirft (simuliert z.B. durch einen
  fehlerhaften Processor-Stub ohne Mock-Ersatz der echten IMAP/SMTP-Kommunikation)
  / When `_process_single` diese Nachricht verarbeitet / Then wird die Mail
  per `imap.store(uid, "+FLAGS", "\\Seen")` als gelesen markiert und beim
  nächsten `poll_and_process()`-Aufruf nicht erneut verarbeitet.
  - **Hinweis:** Ein realer IMAP-Test gegen `gregor-test@henemm.com` in der
    RED-Phase hat gezeigt, dass `imap.fetch(uid, "(RFC822)")`
    (`inbound_email_reader.py` Z.101) die Mail bereits serverseitig implizit
    als `\Seen` markiert, sobald sie abgerufen wird — unabhängig vom Ausgang
    der nachfolgenden Verarbeitung (Standard-IMAP-Verhalten für
    `RFC822`/`BODY[]` ohne `.PEEK`). Die in #1009 befürchtete
    Endlos-Reprocessing-Schleife ist mit dem unveränderten Code daher
    strukturell nicht reproduzierbar (empirisch bestätigt: zwei
    aufeinanderfolgende Polls verarbeiten dieselbe Mail nie zweimal, auch bei
    erzwungenem Fehler in `process()`). AC-1 ist damit **kein RED-Beweis
    eines reproduzierbaren Bugs mehr**, sondern ein Regressions-/
    Härtungstest: er bestätigt, dass die Mail in jedem Fall `\Seen` wird und
    kein Reprocessing stattfindet — sowohl vor als auch nach dem
    try/except/finally-Fix.
  - Test: Realer IMAP-Roundtrip gegen `gregor-test@henemm.com` — Mail mit
    einem Trip-Namen senden, der einen bekannten Fehlerzustand auslöst
    (z.B. nicht-existenter Trip mit gleichzeitig blockiertem Notification-Pfad),
    danach per IMAP-Flag-Abfrage bestätigen, dass die Mail `\Seen` ist und ein
    zweiter Poll-Lauf sie nicht nochmal aufgreift.

- **AC-2:** Given eine eingehende E-Mail mit gültigem Trip-Bezug und
  erfolgreicher Verarbeitung / When `_process_single` diese Nachricht
  verarbeitet / Then bleibt das Verhalten unverändert gegenüber dem Stand
  vor diesem Fix — Antwort-Mail wird verschickt (außer
  `suppress_email_reply`), Rückgabewert `1`, Mail wird `\Seen` markiert.
  - Test: Realer IMAP/SMTP-Roundtrip mit einer regulären, erfolgreich
    verarbeitbaren Befehls-Mail (z.B. `status`) — Bestätigungs-Mail wird via
    IMAP im Test-Postfach empfangen und inhaltlich geprüft (kein
    Dateiinhalt-Check, sondern echte E-Mail-Zustellung).

- **AC-3:** Given ein Telegram-Update von einer `chat_id`, für die kein
  `user.json` mit passendem `telegram_chat_id` existiert / When
  `_process_update` dieses Update verarbeitet / Then erhält der Absender den
  Registrierungs-Hinweis-Text (mit `/start`-Hinweis), es werden keine
  Trip-Daten geladen und keine Wetterdaten verschickt.
  - Test: Live-Telegram-Test gegen den Staging-Bot (`GZ_TELEGRAM_LIVE=1`,
    Staging-Bot-Credentials) mit einer `chat_id`, die in keinem
    `data/users/*/user.json` registriert ist — empfangene Bot-Antwort wird
    per Telegram-API abgerufen und auf den Registrierungs-Hinweis geprüft.

- **AC-4:** Given ein Telegram-Update vom registrierten Betreiber-Account
  (`chat_id` matcht `data/users/henning/user.json::telegram_chat_id`) / When
  `_process_update` dieses Update verarbeitet / Then wird der reguläre
  Multi-User-Pfad durchlaufen (kein `"default"`-Fallback, kein
  Registrierungs-Hinweis), Trip-Status/Wetterdaten werden normal geliefert —
  explizite Regression-AC, da genau dieser Fall bei einer naiven
  Fix-Variante (blindes Blockieren von `"default"`) hätte brechen können.
  - Test: Live-Telegram-Test gegen den Staging-Bot mit der registrierten
    Betreiber-`chat_id` — regulärer Befehl (z.B. `status`) liefert die
    erwartete Trip-Antwort, keine Registrierungs-Meldung.

## Known Limitations

- E-Mail-Pfad erhält keinen äquivalenten Autorisierungs-Gate-Umbau, da
  `_authorize()` bereits vor Erreichen von `TripCommandProcessor` greift —
  nur der Telegram-Pfad hatte die Lücke.
- Der `"default"`-Fallback als solcher (in `_resolve_settings_for_sender`
  bzw. `_resolve_user_for_chat`) bleibt technisch bestehen — er wird nur für
  die Telegram-Kommando-Verarbeitung nicht mehr genutzt, um Daten
  auszuliefern. Ein vollständiges Entfernen des Fallback-Mechanismus selbst
  ist nicht Teil dieses Scopes.
- #1009-Fix ist ein defensiver Backstop für einen seltenen Restfall
  (gleichzeitiger Ausfall beider Mailwege oder unerwarteter Fehler im
  finalen Versand-Schritt) — er ersetzt nicht die bereits bestehende
  Fail-Soft-Behandlung von Wetterdienst-Ausfällen oder die
  Retry-Kaskade in `src/output/channels/email.py`.
- **RED-Phase-Befund (2026-07-07):** `imap.fetch(uid, "(RFC822)")` markiert
  die Mail bereits serverseitig implizit als `\Seen`, sobald sie abgerufen
  wird (Standard-IMAP-Verhalten ohne `.PEEK`) — unabhängig davon, ob die
  nachfolgende Verarbeitung erfolgreich ist. Die in #1009 ursprünglich
  befürchtete Endlos-Reprocessing-Schleife ist damit strukturell nicht
  reproduzierbar. Praktische Konsequenz des unveränderten Ist-Zustands:
  schlägt die Verarbeitung fehl, wird der Befehl still verworfen (kein
  Retry, keine Nutzer-Rückmeldung, nur ein Log-Eintrag) — kein Loop, aber
  auch keine Sichtbarkeit für den Absender. PO-Entscheidung: Der
  try/except/finally-Fix wird trotzdem umgesetzt (macht die
  Fehlerbehandlung explizit statt vom Zufall der impliziten
  Fetch-Semantik abhängig; kein Verhaltensrisiko). Eine Umstellung auf
  `BODY.PEEK[]` (würde eine echte Fehler-Rückmeldung an den Nutzer
  ermöglichen, ließe aber auch das Dauerschleifen-Risiko real werden) ist
  bewusst NICHT Teil dieses Scopes — zu invasiv/riskant für den Nutzen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Bezug: ADR-0003, Multi-Tenant-Isolation)
- **Rationale:** ADR-0003 verbietet den `"default"`-Fallback explizit nur in
  authentifizierten Pfaden; Inbound-Reader sind formal unauthentifiziert,
  daher kein direkter ADR-Verstoß und keine neue ADR nötig. Die
  Schutzintention des ADR (kein Cross-User-Datenleck) wird hier durch einen
  gezielten Autorisierungs-Gate umgesetzt, ohne die Grundarchitektur des
  Fallback-Mechanismus (spezifiziert in `issue_572_multi_user_inbound_routing.md`,
  AC-3/AC-4) zu verändern. AC-3/AC-4 jener Spec bleiben für die
  **User-ID-Auflösung** gültig — diese Spec ergänzt einen zusätzlichen Gate
  für die **Telegram-Kommando-Verarbeitung**, der greift, bevor der
  Fallback-Wert an nachgelagerte Datenzugriffe weitergereicht wird.

## Changelog

- 2026-07-07: Initial spec erstellt — Issue #1009 (Reprocessing-Loop) +
  Issue #1019 (default-Fallback-Datenleck), gebündelt in einem Workflow
- 2026-07-07: AC-1 nach RED-Phase-Befund korrigiert (IMAP-Fetch markiert
  bereits implizit \Seen — Reprocessing-Loop nicht reproduzierbar; PO
  entscheidet: Fix trotzdem als Härtung umsetzen, kein BODY.PEEK-Scope).
