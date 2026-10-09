# Context: fix-2542-staging-befehl-pruefweg

## Request Summary
Auf Staging soll der Antworttext von `status` und der STARTDATUM-Verschiebung über den
**echten** Befehlseingang prüfbar werden, ohne SPF/DKIM zu fälschen. Danach #2441 neu
verifizieren und per `/70-deploy #2441` ausliefern. Erst dann ist #2542 erledigt
(PO-Kommentar).

## Kernbefund (gemessen 2026-10-08, Intake)

**Es braucht voraussichtlich keinen neuen Produktcode und keinen Test-Eingang, der die Prüfung umgeht.**

- Die Testmails zu #2441 kamen über die **authentifizierte Submission (Port 587)**. Dieser Weg
  trägt strukturell **nie** einen `Authentication-Results`-Header (bekannt seit #2143 F003,
  `docs/context/fix-2143-inbound-mail-spoofing.md:49,84`). Darum verwarf der Staging-Eingang
  die Mails (count=0).
- **Messung, anonyme Einlieferung auf Port 25** an `178.104.143.19` (= `mail.henemm.com`),
  `MAIL FROM gregor-test@henemm.com`, Empfänger `gregor-test@henemm.com`. Stalwart setzt diesen Header:
  ```
  mail.henemm.com; spf=none (helo) ...; spf=pass (domain of gregor-test@henemm.com
  designates 178.104.143.19 as permitted sender) smtp.mailfrom=gregor-test@henemm.com;
  iprev=pass; dmarc=pass header.from=henemm.com
  ```
  Der echte Parser `parse_authentication_results` liefert dafür:
  `{'spf':'pass','iprev':'pass','dmarc':'pass'}` mit `authserv-id == mail.henemm.com`.
  Ergebnis: **Die Prüfung `_spf_dkim_pass` ist BESTANDEN.**
- **Warum das legitim ist:** Der SPF-Eintrag von `henemm.com` lautet
  `v=spf1 include:send.resend.com a:mail.henemm.com -all`. Der eigene Server **ist**
  autorisierter Absender für `henemm.com`; DMARC ist `p=quarantine` und aligned.
  Gefälscht wird nichts.
- **Querbeleg:** Echte Gmail-Mails im Prod-Postfach tragen ebenfalls `dkim=pass` und
  `spf=pass` (das spätere `spf=` überschreibt `spf=none` aus HELO, weil im
  Parser-Dict der letzte Wert gewinnt).
- **Im Staging-Postfach** `gregor-staging@` trägt keine der 155 Mails einen
  AR-Header. Alle kamen über 587.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/inbound_email_reader.py:286-333` | `_authorize` → Absender-Allowlist (`mail_to` / Inbound-Adresse), `email_verified_at`, `_spf_dkim_pass` (nur ERSTER AR-Header, authserv-id == `mail_server_hostname`, Default `mail.henemm.com`, `src/app/config.py:238`) |
| `src/services/inbound_email_reader.py:39-60` | `parse_authentication_results`. Pro Methode gewinnt der letzte Wert |
| `src/services/inbound_email_reader.py:156-160,205-207` | TO-Filter beim Poll; abgelehnte Mails werden still als Seen markiert |
| `src/services/trip_command_processor.py:978` | `TripCommandProcessor.process` erzeugt den Antworttext (kanalunabhängig) |
| `src/services/notification_service.py:1969` | `send_command_reply_email` antwortet an `mail_to` des Nutzers; auf Staging über Test-SMTP (`config.py:406-409`) |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py:207` | **`_deliver_mail_anonymous`** existiert bereits: anonyme Port-25-Einlieferung, Empfänger nur das eigene Testpostfach |
| `tests/tdd/test_befehle_email_live.py` | Live-Muster #2417 AC-26: Port 25 → `poll_and_process` → Antwort per IMAP. Plus-Adress-`To:` + TO-Filter, damit nur die eigene Mail angefasst wird. **Läuft lokal im Testprozess, nicht gegen die Staging-Dienste.** |
| `tests/tdd/_befehl_e2e_fixtures.py` | Gemeinsame Befehls-E2E-Helfer |
| `api/routers/scheduler.py:173` | `POST /api/scheduler/inbound-commands` stößt den IMAP-Poll an. Über Go nur für Admins → auf Staging direkt Core 8001 + `X-GZ-Core-Auth` |
| `.claude/commands/e2e-verify.md` | Staging-Verifikationsablauf. Hier fehlt das Rezept „Befehl per echtem Mail-Eingang auf Staging“ |
| `docs/specs/modules/fix_2441_etappennummer_status.md` | ACs von #2441: AC-1, 2, 3, 4, 6, 7, 9 sind auf Staging noch offen |

## Existing Patterns
- Live-Befehls-E2E über anonyme Port-25-Einlieferung (#2417 AC-26, #1009/#1019).
- Staging-Mailprüfung nur über **Wegwerf-Nutzer `gregor-test+…`**: Das Hauptkonto schickt an `gregor-staging@` (Memory #2422 S6b).
- Ein Staging-Sammellauf/Poll ist über Go admin-only. Der Weg ist Kern 8001 + `X-GZ-Core-Auth` (Memory #2422 S3).
- Staging-Login braucht `/home/hem/gregor_zwanzig_staging/.env`, nicht die Projekt-`.env`.
- Staging-Datenbestand ist für `hem` nicht lesbar. Nutzer und Trip also über die Staging-API anlegen (`id` ist Pflicht).

## Dependencies
- Upstream: Stalwart-Eingang Port 25 (setzt AR), DNS-SPF/DMARC von `henemm.com`, Staging-Poll
  von `gregor-staging@henemm.com` (`GZ_INBOUND_ADDRESS`), Staging-Test-SMTP für die Antwort.
- Downstream: `/e2e-verify` (Befehls-ACs), Prod-Gate für #2441 und künftige Befehls-Tickets.

## Existing Specs
- `docs/specs/modules/inbound_command_channels.md`
- `docs/specs/modules/trip_command_processor.md`
- `docs/specs/modules/fix_2441_etappennummer_status.md`
- `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md`

## Offene Punkte für /20-analyse
1. **Ablauf auf Staging Ende-zu-Ende:**
   - Wegwerf-Nutzer mit `mail_to = gregor-test+<tag>@henemm.com` anlegen.
   - `email_verified_at` setzen; der Bestätigungslink kommt per IMAP aus `gregor-test`.
   - Trip mit Etappen anlegen.
   - Port 25 an `gregor-staging@henemm.com` mit `From`/`MAIL FROM` = `mail_to`, Betreff `[Trip] status`.
   - Poll über Kern 8001 auslösen oder Cron abwarten.
   - Antwort per IMAP aus `gregor-test` lesen; sie geht an die Plus-Adresse.

   Zu prüfen: Akzeptiert die Allowlist eine Plus-Adresse als Absender? Liefert Stalwart Plus-Adressen in das Basispostfach aus?
2. **Liefergegenstand:** live-markiertes Prüfwerkzeug (Skript oder `staging`-Test) plus Rezept in `/e2e-verify`. Wahrscheinlich kein Produktcode.
3. **Telegram/SMS:** Ist laut Ticket nicht nötig; E-Mail reicht als echter Eingang für den
   Antworttext, weil der Prozessor kanalunabhängig ist. Kanal-spezifische Formate (SMS-Kürze)
   deckt #2441 über die Vorschau-Endpunkte ab. In der Analyse zu bestätigen.

## Risks & Considerations
- **Nie** an fremde Domains auf Port 25 einliefern (Relay-Versuch). Empfänger ausschließlich `@henemm.com`-Testpostfächer.
- Das geteilte Postfach `gregor-test` darf nicht flächig als Seen markiert werden. Daher TO-Filter und Plus-Adresse.
- Abgelehnte Mails werden still verworfen. Das Werkzeug muss count=0 als **Fehlschlag** melden, nicht als „leer“.
- Kein Bypass der #2143-Prüfung. Ein „gesicherter Test-Eingang“ wäre nur der Rückfall, mit Blast Radius High.
- Abschlussbedingung: #2441 per `/70-deploy` live, Selftest Exit 0.

## Analysis

### Type
Feature (Prüfwerkzeug/Tooling). Kein Produktcode-Defekt: Der Eingang verwirft die #2441-Testmails zu Recht, weil sie über Port 587 kamen und damit keinen `Authentication-Results`-Header tragen.

### Gemessene Staging-Fakten (2026-10-08, nur Werte ohne Secret aus `/home/hem/gregor_zwanzig_staging/.env`)
- `GZ_ENV=staging`, `GZ_IMAP_USER=gregor-staging@henemm.com`, `GZ_INBOUND_ADDRESS=gregor-staging@henemm.com`,
  `GZ_TEST_SMTP_USER=gregor-test`, `GZ_TEST_MAIL_FROM=gregor-test@henemm.com`, `GZ_TEST_IMAP_USER=gregor-test`.
- Der globale Poll (`api/routers/scheduler.py:173`, `Settings()` ohne `for_testing`) liest `gregor-staging@` mit dem TO-Filter
  `gregor-staging@henemm.com` (`inbound_email_reader.py:156-160`). Der `To:`-Header der Testmail MUSS also `gregor-staging@henemm.com` sein.
- Pro Nutzer gilt `with_user_profile` → auf Staging immer `for_testing()` (`config.py:404`). Daraus folgen `mail_from=gregor-test@henemm.com`
  und `inbound_address=gregor-test@henemm.com`. `_authorize` (`inbound_email_reader.py:294`) verwirft `sender == mail_from`.
  **Folge:** `mail_to` des Wegwerf-Nutzers MUSS eine Plus-Adresse `gregor-test+<tag>@henemm.com` sein, und `From:` muss **exakt** dieselbe Adresse tragen.
  `lookup_user_by_email` vergleicht exakt, ohne Plus-Stripping (`loader.py:1382ff`). Mehrdeutig (Rest eines früheren Laufs mit gleicher Adresse) ⇒ `None` ⇒ stumm verworfen. Darum braucht jeder Lauf einen **eindeutigen Tag**, und am Ende wird aufgeräumt.
- SPF/DMARC: Envelope `MAIL FROM` auf `@henemm.com` über Port 25 an `mail.henemm.com` ⇒ Stalwart setzt `spf=pass … dmarc=pass`, authserv-id `mail.henemm.com` ⇒ `_spf_dkim_pass` besteht. Das ist legitim: SPF `a:mail.henemm.com`.
- `email_verified_at`: Gesetzt wird es nur über `POST /api/auth/verify-email` (Go). Das Token kommt aus `POST /api/auth/verify-email/staging-token`
  (nur bei `GZ_ENV=staging`, anmeldepflichtig, `api_contract.md:3776-3810`). Eine Adressänderung **nach** der Verifikation läuft in den
  `PendingContactAddress`-Fluss (`internal/handler/auth.go:1195-1200`). Reihenfolge daher: Nutzer gleich mit der Plus-Adresse anlegen, dann Staging-Token holen, dann verifizieren.
- Poll-Takt: Go-Cron `*/5` (`internal/scheduler/scheduler.go:309`). Der manuelle Trigger geht direkt an Kern 8001 mit `X-GZ-Core-Auth`
  (Secret `GZ_CORE_SHARED_SECRET`, `api/main.py:125-167`). **Erfolgssignal ist die Antwortmail im IMAP-Postfach `gregor-test` innerhalb des Timeouts, nicht `count`.**
  Hat der Cron die Mail schon verarbeitet, liefert der Trigger `count=0`, obwohl alles funktioniert. `count` dient nur der Diagnose.
- Antwortweg: `send_command_reply_email` geht an `mail_to` (Plus-Adresse) über Stalwart-Test-SMTP und landet im Basispostfach `gregor-test`.
  Belegt ist das durch das bestehende Wegwerf-Nutzer-Muster (#2422 S6b). Dort per Header-`To:` filtern, nie das geteilte Postfach flächig auf Seen setzen.

### AC-Kanal-Matrix für #2441 (offene ACs 1, 2, 3, 4, 6, 7, 9)
| AC | Kern | Staging-Messweg |
|----|------|-----------------|
| AC-1 | `status` und `heute` nennen dieselbe Etappennummer | E-Mail-Eingang (neu). Der Trip muss so datiert sein, dass „heute“ auf eine bekannte Etappe fällt |
| AC-2 | „02: X“/„02 – X“ werden zu „Etappe N: X“ | E-Mail-Eingang. Gezielt gebaute Etappennamen nötig |
| AC-3 | „2 Seen Runde“, „1. Pass“, „03:“ | E-Mail-Eingang. Gezielt gebaute Etappennamen |
| AC-4 | Verschiebe-Vorschau und Bestätigung nennen dieselbe Nummer | E-Mail-Eingang, **Dialog in zwei Schritten**: Das Werkzeug muss nach der Vorschau die Bestätigungsmail senden. Das Bestätigungsformat klärt die Spec aus `trip_command_processor.py` |
| AC-9 | Zählung chronologisch bei nicht chronologischer Listenreihenfolge | E-Mail-Eingang. Die Etappen werden in vertauschter Reihenfolge angelegt |
| AC-6 | Kurzform/EN: ASCII „-“, GSM-7 | **Nicht über E-Mail erreichbar.** `_en` wird nur für `channel in ("premium_sms","sms")` oder `englisch` (Telegram) gesetzt (`trip_command_processor.py:763,980`). Der Premium-SMS-Befehlsweg ist auf Staging durch die Herkunftssperre strukturell abgeschaltet (Memory `reference_premium_sms_kommandoweg_auf_staging_strukturell_tot`). Präzedenz #2417: Kern-Test durch den echten `inbound_sms_reader`, dazu die SMS-Vorschau-Endpunkte auf Staging und ein Dialog-Nachtest nach dem Prod-Deploy |
| AC-7 | `status` über alle vier Kanäle mit gleicher Zahl | E-Mail: neuer Weg. SMS/Premium-SMS: wie AC-6. Telegram: Antwort nicht abgreifbar (der Bot schreibt in den Chat). Bleiben die geteilte `numbered_stage_label`-Vorschau (bereits gemessen) und der Kern-Test |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/tools/staging_befehl_pruefen.py` (Name in der Spec) | CREATE | Staging-Prüfwerkzeug: legt einen Wegwerf-Nutzer mit Plus-Adresse an, verifiziert ihn per Staging-Token, legt einen Trip mit gebauten Etappen an, liefert über Port 25 an `gregor-staging@` ein, löst den Poll über Kern 8001 aus (oder wartet den Cron ab), liest die Antwort per IMAP aus `gregor-test` (TO-Filter), unterstützt den Dialog in zwei Schritten und räumt am Ende auf. Exit ≠ 0, wenn die Antwort ausbleibt |
| `tests/tdd/test_befehle_email_live.py` / `_befehl_e2e_fixtures.py` | READ/ggf. MODIFY | Echte Helfer wiederverwenden (`_deliver_*_anonymous`, `_imap`, `_find_reply_by_subject`, `_peek_msg`), gegebenenfalls in ein gemeinsames Modul heben |
| `tests/tdd/test_staging_befehl_pruefweg.py` | CREATE | Kern-Tests des Werkzeugs, deterministisch: Adress-/Header-Bau, Abbruch ohne Antwort, Tag-Eindeutigkeit, Relay-Sperre (nur `@henemm.com`) |
| `.claude/commands/e2e-verify.md` | MODIFY | Neues Rezept „Befehl per echtem Mail-Eingang auf Staging“ nach Schritt 2 (ca. Z. 95), plus Hinweis zur AC-Kanal-Matrix für SMS/Telegram |
| `src/`, `api/`, `internal/` | — | **Keine Änderung.** Die #2143-Prüfung bleibt unangetastet |

### Scope Assessment
- Dateien: 3–4
- Geschätzter LoC-Umfang: Werkzeug ca. +200, Tests ca. +120, Doku ca. +40. Das Werkzeug unter `.claude/` zählt eventuell nicht zum LoC-Limit; das in der Spec prüfen
- Risk Level: LOW für Produktion, weil kein Produktcode betroffen ist. MEDIUM operativ, wegen echter Einlieferung in geteilte Postfächer und Aufräumen auf Staging

### Technical Approach
Port-25-Einlieferung analog #2417 AC-26 / #1009, jetzt aber gegen die **laufenden Staging-Dienste** statt eines lokalen Polls. Nutzer und Trip werden über die Staging-API angelegt (Login über `/home/hem/gregor_zwanzig_staging/.env`, `id` ist Pflicht). Die Verifikation läuft über den Staging-Token-Endpunkt. Ausgelöst wird über Kern 8001 + `X-GZ-Core-Auth`, als Rückfall dient der Cron. Ausgewertet wird die Antwort im IMAP-Postfach.
Leitplanken: Empfänger nur `@henemm.com`-Testpostfächer (keine Relay-Versuche), eindeutiger Tag pro Lauf, Aufräumen im `finally`, keine Secrets in Ausgaben.
Plan/Sonnet-Schritt: Die strategische Bewertung (Ansatz, Risiko, Reihenfolge, AC-Kanal-Matrix) hat der Advisor-Review übernommen; ein zusätzlicher Plan-Agent hätte nur dieselbe Matrix wiederholt.

### Dependencies
Stalwart Port 25 (setzt AR) · DNS SPF/DMARC `henemm.com` · Staging-Kern 8001 + Core-Secret · Go-Endpunkte `verify-email/staging-token`, `verify-email` · Staging-Cron `*/5` · Downstream: `/e2e-verify` und `/70-deploy #2441`.

### Open Questions
- [x] **PO-Entscheid 2026-10-08: „Wie bei #2417“.** E-Mail wird echt auf Staging geprüft; SMS/Premium-SMS/Telegram über Kern-Tests mit echtem Eingang, Staging-Vorschau und Handy-Nachtest nach dem Prod-Deploy. Kein Telegram-/SMS-Prüfweg in #2542. Ursprüngliche Frage: Für SMS, Premium-SMS und Telegram gibt es auf Staging keinen echten Befehlseingang mit abgreifbarer Antwort (Premium-SMS ist dort bewusst abgeschaltet, Telegram-Antworten landen im Chat). Reicht für #2441 AC-6/AC-7 die bewährte Kombination aus Kern-Test durch den echten SMS-Eingang, gemessener Vorschau auf Staging und Handy-Nachtest nach dem Prod-Deploy (wie bei #2417)? Die Alternative wäre, dass #2542 auch einen Telegram-/SMS-Prüfweg auf Staging baut, mit deutlich größerem Umfang.
- [ ] Bestätigungsformat des Verschiebe-Dialogs (AC-4): in der Spec aus `trip_command_processor.py` ablesen, kein PO-Thema.
