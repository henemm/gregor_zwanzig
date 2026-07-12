# Context: #1235 — Empfänger-Guard auch auf dem Stalwart-Pfad

## Request Summary

Aktives Mail-Leck (86 Mails/48h an externe Fake-Adressen, zuletzt 2026-07-12 08:28,
Beweis: Resend-Sent-Log via infra): Der komplette Empfänger-Guard greift nur auf
Resend-Hosts; Staging/Tests senden zwingend über Stalwart → ungeschützt → Stalwart
relayt extern an Resend (infra#114). Fix: Guard bedingungslos, mit Erlaubnis für
lokale Zustellung. Root-Cause-Analyse: MQ 48151 von infra, am Code verifiziert.

## Verifizierte Fakten

### Guard-Struktur (email.py, Stand b8a03b4d)

- `send()`-Guard-Block: **alles** unter `if "resend" in (self._host or "").lower():`
  (Zeile ~407) — Allowlist-Prüfung (#1219), `_is_reserved_test_domain` (RFC-2606),
  `_raw_contains_test_mailbox`. Davor existiert KEIN bedingungsloser Guard.
- Hilfsfunktionen (modul-level, wiederverwendbar): `_normalized_addrs_for_guard` (:64),
  `_raw_contains_test_mailbox` (:118), `_is_reserved_test_domain` (:141, RFC-2606 inkl.
  Trailing-Dot/BARE-TLD-Härtung), `_load_resend_allowlist` (:162, positive Allowlist aus
  verifizierten Nutzerprofilen via `get_data_root()`), `_mask_addr_for_log` (:211).
- Weitere Guards (bleiben): #924 Staging-nie-Resend (:316), #879 Test-Modus-nie-Resend,
  #1122 Default-Deny in `Settings._resend_default_deny` (config.py:163-186): OHNE
  `GZ_RESEND_ALLOWED`-Token (und in pytest IMMER) wird jeder Resend-Host auf Stalwart
  umgelenkt → **Stalwart ist der De-facto-Standardpfad für alles außer der Prod-Unit.**

### Host-Matrix

| Umgebung | smtp_host | Guard heute |
|---|---|---|
| Prod-Unit (GZ_RESEND_ALLOWED=1) | smtp.resend.com | ✅ Allowlist + Reserved + Test-Mailbox |
| Staging (#924-Zwang) | mail.henemm.com | ❌ KEIN Guard |
| for_testing() / Test-User | mail.henemm.com | ❌ KEIN Guard |
| pytest (auch mit Token, #1122) | mail.henemm.com | ❌ KEIN Guard |

### Leck-Quellen (Agent-Report, verifiziert an Staging-Daten)

E2E-/Playwright-Tests legen Compare-Presets mit Fake-Empfängern an, die in
`data/users/default/compare_presets.json` auf Staging PERSISTIEREN und vom Scheduler
regulär mitversendet werden: `test@example.com` (mind. 2 Alt-Presets „Adversary681
Test", „ReVal681 Test F001"), `e@x.invalid` (test_compare_official_alert-Muster),
diverse `*-test@example.com` aus frontend/e2e/*.spec.ts. Versandweg: Scheduler →
`EmailOutput.send(recipients)` → kein Filter → Stalwart → Relay. Der Fix im
zentralen `send()`-Guard deckt ALLE diese Aufrufer ab (kein Scheduler-Sonderfilter
nötig). Hinweis: „Validator-1025"-Versand 11:36 an gregor-test@ war unser legitimer
E2E-Lauf (lokale Zustellung — muss erlaubt bleiben).

### Testlandschaft (Agent-Report)

- `tests/tdd/test_resend_recipient_allowlist.py` — **AC-4 verankert die Lücke als
  „bewusste Design-Entscheidung"** („GIVEN Stalwart-Host … THEN Allowlist-Guard greift
  NICHT"). Diese Design-Annahme ist durch infra#114 widerlegt → AC-4-Test wird
  INVERTIERT (RED-Kandidat) — dokumentierte, begründete Verhaltensänderung, kein
  stilles Umschreiben.
- `test_resend_verified_allowlist.py` (AC-1..7), `test_issue_1147_resend_recipient_invariant.py`
  (inkl. F001..5-Bypass-Härtungen: Case/Semikolon/Control-Chars), `test_issue_879_*`,
  `test_issue_1122_*`, `test_927_smtp_fallback.py` — Muster: EmailOutput mit
  Fake-Settings, Exception VOR SMTP-Connect (deterministisch, Kern-Schicht);
  echte Zustellung nur mit `@pytest.mark.email`.
- `test_issue_1147_...` AC-3 beweist: gregor-test@-Zustellung über Stalwart MUSS
  weiter funktionieren (unser gesamtes Mail-Gate-/E2E-System hängt daran!).

## Fix-Richtung (aus MQ 48151, von infra vorgegeben)

Guard-Bedingung von `if resend-in-host` erweitern auf: Resend-Pfad = Vollprüfung wie
heute; **Nicht-Resend-Pfad (Stalwart)**: nicht-lokale Empfänger durchlaufen dieselbe
Prüfkette (Allowlist ODER lokal), reservierte Test-Domains IMMER blocken; lokale
Empfänger (`@henemm.com` inkl. gregor-test@/gregor-staging@ und Plus-Adressen) bleiben
erlaubt (Stalwart stellt lokal zu, kein Relay — Zustell-Postfächer der Validatoren!).

### Offene Tech-Entscheidungen für die Analyse/Spec

1. **Definition „lokal":** Hardcode `henemm.com` vs. aus `mail_from`/`inbound_address`-
   Domain abgeleitet vs. neues Setting (`GZ_LOCAL_MAIL_DOMAIN`). Bestand: `TEST_MAILBOXES`
   ist bereits hartkodiert `…@henemm.com` (email.py:33); Stalwart bedient genau
   henemm.com. → Tendenz: Konstante `LOCAL_MAIL_DOMAINS = frozenset({"henemm.com"})`
   neben TEST_MAILBOXES, gleiche Härtungs-Normalisierung wie `_is_reserved_test_domain`
   (Trailing-Dot, Case, `_normalized_addrs_for_guard`-Kandidaten).
2. **Allowlist auf Stalwart-Pfad:** Externe Empfänger, die in der #1219-Allowlist stehen
   (echte verifizierte Nutzer), über Stalwart zulassen? Stalwart würde sie an Resend
   relayen (infra#114 noch offen) — das wäre der reguläre Staging-Briefing-Fall an
   echte Nutzer, den es nicht geben soll (Staging soll NIE echte Nutzer anschreiben,
   vgl. `with_user_profile`-force_test). → Tendenz: auf Nicht-Resend-Pfaden externe
   Empfänger KOMPLETT blocken (nur lokal erlaubt), strenger als Resend-Pfad. Muss in
   der Spec explizit entschieden werden (Adversary-Frage vorwegnehmen).
3. Fail-Verhalten: gleiche `OutputConfigError` + Masked-Logging wie #1219 (konsistent).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/channels/email.py` | Guard-Umbau in `send()` (~:407) + neue Lokal-Prüfung; Mail-GATE-Datei (#811: channels/email.py in Gate-Liste!) |
| `src/app/config.py:163-186` | #1122-Default-Deny — unverändert, aber im Zusammenspiel dokumentieren |
| `tests/tdd/test_resend_recipient_allowlist.py` | AC-4 invertieren (RED); restliche ACs müssen unverändert grün bleiben |
| `tests/tdd/test_issue_1147_resend_recipient_invariant.py` | Bypass-Härtungs-Muster für neue Stalwart-Fälle wiederverwenden; AC-3 (gregor-test@-Zustellung) = Regressions-Anker |
| `data/users/default/compare_presets.json` (Staging) | Alt-Presets mit example.com-Empfängern — nach dem Fix blockt der Versand sie laut (Warning-Log); Aufräumen der Alt-Daten = separater Deploy-Schritt/Nebenbefund |

## Risks & Considerations

- **Renderer-Mail-Gate #811 greift** (`src/output/channels/email.py` ist Gate-Datei):
  Matrix-Test + briefing_mail_validator mit echter Test-Mail vor Commit — die Test-Mail
  geht an gregor-test@ über Stalwart und beweist damit gleich die Lokal-Erlaubnis.
- **Selbst-Blockade-Risiko:** Zu strenger Fix blockiert unsere eigene E2E-/Gate-Kette
  (gregor-test@). Deshalb Lokal-Erlaubnis als expliziter AC mit echter Zustellung.
- Staging-Scheduler versendet Alt-Presets mit Fake-Empfängern weiter — nach Fix
  erwartbar geblockte Versuche im Log (kein Fehler, gewollt); infra-Wächter
  (check-gregor20.sh 3b) soll danach 0 Treffer zeigen.
- infra baut parallel Relay-Allowlist am Stalwart (zweite Verteidigung) — unabhängig.
- pytest-Läufe treffen den neuen Guard (Stalwart-Pfad ist pytest-Standard per #1122)
  — bestehende Tests, die `send()` mit Fake-Empfängern + Mail-Sink nutzen, könnten
  neu blocken → Testlauf-Sweep nötig (Mock-/Sink-Tests konstruieren meist vor SMTP).
