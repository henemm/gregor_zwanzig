# Context: fix-2143-inbound-mail-spoofing

## Request Summary
Issue #2143 (Blocker): Ein gefälschter `From:`-Header genügt, um Trip-Kommandos (u.a. `abbruch`, `startdatum`, `ruhetag`, `skip`) eines beliebigen Nutzers auszulösen — `_authorize()` prüft den Absender nur gegen `mail_to` des per `From:` selbst aufgelösten Nutzers (tautologisch), es gibt weder SPF/DKIM-Auswertung noch eine `email_verified_at`-Prüfung noch eine Mehrfachtreffer-Erkennung beim Inbound.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/inbound_email_reader.py:104-235` | `_process_single`, `_authorize` (tautologisch), `_resolve_settings_for_sender` — Kern des Bugs |
| `src/app/loader.py:1229-1253` | `lookup_user_by_email` — nimmt ersten Treffer, keine Mehrfachtreffer-Erkennung |
| `src/app/loader.py:1256-1309` | `lookup_user_by_telegram_chat_id` (Issue #2141) — **Vorbild-Pattern**: trennt `real_matches`/`test_matches`, bei `len(real_matches)>1` → `None` statt Zufallstreffer |
| `src/services/inbound_telegram_reader.py:181-196, 307-319` | `user_id == "default"`-Gate nach Lookup — **fehlt beim Email-Reader komplett** |
| `src/services/inbound_telegram_reader.py:427ff.` | Out-of-Band-Token-Verifikation (`/start TOKEN`) als Identitätsnachweis-Vorbild |
| `src/app/config.py:148-150` | `Settings.mail_to/mail_from/inbound_address` — **kein `email_verified_at`-Feld deklariert** |
| `src/app/config.py:366-416` | `with_user_profile()` — lädt `user.json`, setzt Felder explizit; `email_verified_at` würde durch `extra="ignore"` (L117) sonst still verworfen |
| `src/app/config.py:201-214` | Präzedenzfall: `premium_sms_reply_to`/`_at` wurden genau wegen dieses Silent-Drop-Problems explizit deklariert |
| `src/output/channels/email.py:242-291` | Einziger bestehender `email_verified_at`-Check (Outbound-Pfad) — Muster: `if not profile.get("email_verified_at"): continue` |
| `src/services/trip_command_processor.py` | Alle schreibenden Handler (`_apply_ruhetag` L1582, `_shift_start` L1658, `_apply_pause` L1806, `_apply_skip` L1829, `_cancel_trip` L2090, `_resume_trip` L2104) rufen `save_trip(trip, user_id)` — mandantengescoped über `msg.user_id` aus `InboundMessage` |
| `docs/specs/modules/inbound_command_channels.md` | v1.3, §5 „Sender-Authentifizierung" (L257-274) beschreibt die **alte Single-User-Fassung** — nicht mehr deckungsgleich mit dem realen Code, muss mitgepflegt werden |
| `docs/adr/0003-multi-tenant-isolation.md` | **Zentral**: „Rückfall auf `'default'` in einem authentifizierten Pfad ist verboten — Cross-User-Datenleck". `lookup_user_by_email(...) or "default"` ohne nachgeschaltetes Gate verstößt genau dagegen |
| `tests/tdd/test_bug_inbound_email_loop.py` | Bestehende `_authorize()`-Unit-Tests, direkte `Settings(...)`-Konstruktion — Signaturänderung an `_authorize` bricht diese, müssen mitgezogen werden |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py` | Mock-frei, echter IMAP/SMTP-Roundtrip gegen `gregor-test@henemm.com`; `_make_user`/`_base_email_settings`-Helper als Muster für neuen Zwei-Nutzer-Test |
| `data/users/tg-live-e2e/user.json` | Einziges reale User-Profil im Repo — **hat kein** `email_verified_at` (Feld ist optional/nicht überall vorhanden) |
| `scripts/migrate_1219_email_verified.py` | Backfill-Skript für `email_verified_at` bei `henning`/`steffi` (Prod-Profile vermutlich gesetzt, im Repo nicht verifizierbar) |

## Existing Patterns

- **Telegram-Inbound-Autorisierung (#2141/#1019) ist das direkte Vorbild:**
  1. Lookup trennt echte von Test-Nutzern und lehnt bei Mehrfachtreffer explizit ab (`None`, nicht Zufallsgewinner).
  2. Ein expliziter Gate-Check `if user_id == "default":` NACH dem Lookup verhindert, dass ein nicht zugeordneter Absender überhaupt an den Command-Prozessor gelangt — sendet stattdessen einen Registrierungs-Hinweis.
  3. Identität wird zusätzlich durch ein Out-of-Band-Token verifiziert, nicht nur durch eine vom Client mitgeschickte ID.
- **`email_verified_at`-Konvention:** RFC3339-String (`"2026-01-01T00:00:00Z"`), reiner Truthy-Check, kein Bool. Bereits etabliertes Muster im Outbound-Pfad (`email.py:291`).
- **Silent-Field-Drop-Falle:** Ein Profilfeld, das nicht explizit in `Settings` deklariert ist, verschwindet beim `model_copy`/Pydantic-Load (`extra="ignore"`) — muss also, analog zu `premium_sms_reply_to`, explizit als `Settings`-Feld ergänzt werden, bevor `_authorize()` darauf zugreifen kann.
- **ADR-0003-Prinzip:** kein ungeschützter `"default"`-Fallback in einem authentifizierten Pfad.

## Dependencies

- **Upstream:** `Settings`-Klasse (`app/config.py`), `user.json`-Schema (`app/loader.py`), IMAP-Fetch liefert volle RFC822-Header inkl. potenziellem `Authentication-Results` (Stalwart) — **Format unbekannt, kein Mitschnitt einer echten eingehenden Fremd-Mail im Repo vorhanden.**
- **Downstream:** `TripCommandProcessor.process()` (alle schreibenden Trip-Mutationen), `NotificationService.send_command_reply_email()` (Bestätigungsmail an den — bislang ungeprüften — Absender).

## Existing Specs

- `docs/specs/modules/inbound_command_channels.md` (v1.3) — §5 Sender-Auth ist veraltet, muss im Rahmen dieses Fixes aktualisiert werden (sonst erneute Drift wie bereits jetzt zwischen Spec und Code).
- `docs/adr/0003-multi-tenant-isolation.md` — Leitplanke, kein neues ADR nötig, der Fix setzt ADR-0003 nur konsequent um.

## Risks & Considerations

- **SPF/DKIM-Header-Format — GEKLÄRT (Analyse-Phase, Live-Forensik auf der Produktiv-Stalwart-Instanz):** Die frühere 400-Mail-Stichprobe zeigte 0 Treffer, weil das Testpostfach ausschließlich per authentifizierter SMTP-Submission (Resend/Loopback) befüllt wird — dieser Pfad läuft NICHT durch die anonyme Port-25-Pipeline. Direkte Prüfung von `/home/hem/henemm-infra/stalwart` (Docker-Container `stalwart-mail`, Logs, Blob-Store) bestätigt: **Stalwart führt SPF/DKIM/DMARC/IPREV-Checks auf jeder anonymen Inbound-SMTP:25-Verbindung durch (Stock-Verhalten, keine explizite Config) und schreibt einen vollständigen `Authentication-Results: mail.henemm.com; dkim=…; spf=…; dmarc=…`-Header (RFC 8601) in zugestellte Mails** — verifiziert an echten zugestellten Nachrichten. Die Checks sind **advisory, kein Hard-Reject** bei Fail. `henemm.com` publiziert `DMARC p=reject`. → **Option A (SPF/DKIM via `Authentication-Results` auswerten) ist ohne Infra-Änderung umsetzbar und ist der einzige Baustein, der die eigentliche Forgery-Lücke schließt** (reine Eindeutigkeits-/Verifiziert-Prüfung ohne Transport-Auth würde einen Spoof mit korrekt geratener/bekannter `mail_to`-Adresse eines ECHTEN, verifizierten Nutzers nicht verhindern). Kritischer Umsetzungspunkt: nur den **ersten** `Authentication-Results`-Header auswerten (Stalwart prependt, ein Angreifer könnte einen zweiten gefälschten Header mit `pass` anhängen) + `authserv-id == eigener Hostname` prüfen — sonst trivial umgehbar. **Testbarkeits-Lücke:** Der etablierte E2E-Testpfad (authentifizierte Submission → IMAP-Loopback gegen `gregor-test@henemm.com`) erzeugt strukturell NIE einen echten `Authentication-Results`-Header — Kern-Tests brauchen daher eine versionierte, aus echten (anonymisierten) Stalwart-Logs abgeleitete Header-Fixture; ein Live-E2E-Nachweis der tatsächlichen Verdrahtung braucht eine echte externe Testmail (z.B. Gmail-Testkonto) an die Staging-Inbound-Adresse.
- **Spec-Drift:** `inbound_command_channels.md` §5 und „Known Limitations" beschreiben noch die Single-User-Welt — Doku-Update ist Teil des Scopes, sonst wächst die Lücke weiter.
- **Breaking Change für Bestandsprofile ohne `email_verified_at`:** Erwartung „nur verifizierte Adressen dürfen Kommandos auslösen" bedeutet, dass Profile ohne gesetztes Feld (wie das reale `tg-live-e2e`-Fixture) künftig abgelehnt werden — muss in ACs und Testfixtures korrekt reflektiert sein.
- **`_authorize`-Signaturänderung** bricht bestehende Tests in `test_bug_inbound_email_loop.py` (direkte `Settings(...)`-Konstruktion ohne `email_verified_at`/Header-Parameter) — müssen mitgezogen werden.
- **Zwei-Nutzer-Testpflicht** laut CLAUDE.md: jeder nutzerbezogene Endpoint MUSS mit zwei verschiedenen Nutzern getestet werden — hier zusätzlich mit Spoofing-Szenario (Mail von A mit `From: b@…`).

## Analysis

### Type
Bug (Security, kein Feature) — Root Cause bestätigt durch `bug-intake`-Agent, strategische Bewertung durch `Plan`-Agent inkl. Live-Verifikation des Stalwart-Verhaltens.

### Root Cause
`_authorize()` (`inbound_email_reader.py:188-202`) ist tautologisch: der Nutzer wird bereits aus dem `From:`-Header aufgelöst (`lookup_user_by_email`), und derselbe Header wird danach gegen exakt dieses Profil geprüft. Drei Nebendefekte verstärken die Lücke: `lookup_user_by_email` löst Mehrfachtreffer nicht auf (erster gewinnt statt Ablehnung), `email_verified_at` wird nur im Outbound-Pfad geprüft, und es gibt kein `user_id == "default"`-Gate (ADR-0003-Verstoß) wie beim Telegram-Pendant.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_email_reader.py` | MODIFY | `_authorize()` umbauen: `Authentication-Results`-Header parsen (nur erster Treffer, `authserv-id`-Check, `spf=pass` UND `dkim=pass` bzw. `dmarc=pass` als Alignment, sonst fail-closed) + `email_verified_at`-Pflicht (Truthy). `_process_single`/`_resolve_settings_for_sender`: `user_id == "default"`-Gate ergänzen. |
| `src/app/loader.py` | MODIFY | `lookup_user_by_email` analog `lookup_user_by_telegram_chat_id` (#2141) umbauen: real/test-Trennung, Mehrfachtreffer → `None` statt erster Treffer. |
| `src/app/config.py` | MODIFY | `email_verified_at` explizit als `Settings`-Feld deklarieren (Präzedenzfall `premium_sms_reply_at`, L201-214) — sonst Silent Drop durch `extra="ignore"`. |
| `tests/tdd/test_bug_inbound_email_loop.py` | MODIFY | Bestehende `_authorize()`-Tests an neue Signatur/Parameter (Header, `email_verified_at`) anpassen. |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py` | MODIFY | Test-Bypass-Strategie für fehlenden `Authentication-Results`-Header im Submission-Loopback-Pfad (Entscheidung: siehe „Technical Approach"). |
| Neue Testdatei (Kern) | CREATE | Zwei-Nutzer-Spoofing-Test + Adversary-Test „zweiter gefälschter AR-Header" mit versionierter, echter (anonymisierter) `Authentication-Results`-Fixture. |
| `docs/specs/modules/inbound_command_channels.md` | MODIFY | §5 „Sender-Authentifizierung" von Single-User- auf Multi-User-Fassung aktualisieren (schließt bestehende Spec-Drift). |

### Scope Assessment
- Files: 7 (4 Quellcode/Doku MODIFY, 2 Tests MODIFY, 1 Test CREATE)
- Estimated LoC: +400/-700 grob (abhängig von der Test-Bypass-Entscheidung für den AR-Header-Check)
- Risk Level: **HIGH** (kritischer Auth-Pfad, Breaking Change für Profile ohne `email_verified_at`, Testarchitektur-Eingriff)

### Technical Approach
**Hybrid B+A** (Empfehlung des Plan-Agenten, selbst geprüft und übernommen):
- **B — Identitäts-Basis:** Eindeutigkeits-Fix im Lookup (analog #2141) + `email_verified_at`-Pflicht (Truthy-Check wie Outbound) + `user_id == "default"`-Gate (ADR-0003-konform, analog Telegram). Notwendig, aber allein NICHT ausreichend — ein Spoof mit der `mail_to`-Adresse eines echten, verifizierten Nutzers würde sonst weiterhin durchgehen.
- **A — Transport-Authentifizierung:** `Authentication-Results`-Header auswerten (Stalwart liefert das produktiv, empirisch verifiziert). Nur erster Header, `authserv-id`-Abgleich gegen eigenen Hostname, `spf=pass` UND `dkim=pass` (oder `dmarc=pass` als Alignment) gefordert — sonst fail-closed ablehnen (entspricht wörtlich der Issue-Erwartung: „Kommandos nur bei SPF/DKIM pass; sonst verwerfen und loggen").
- **C — Reply-Token:** zurückgestellt/dokumentiert als Future Enhancement, nicht Teil dieses Fixes — A liefert bereits eine produktiv vorhandene, ausreichend robuste Transport-Authentifizierung; C würde Go+Python+Briefing-Integration erfordern, ohne zusätzlichen Sicherheitsgewinn gegenüber A+B.
- **Test-Strategie (selbst entschieden, keine PO-Frage nötig):** Kern-Layer bekommt eine versionierte, aus echten Stalwart-Logs abgeleitete (anonymisierte) `Authentication-Results`-Header-Fixture für deterministische Unit-Tests der Parse-/Validierungslogik (inkl. Adversary-Fall „zweiter gefälschter Header"). Live-E2E-Layer bekommt einen Test mit echter externer Testmail (z.B. Gmail-Testkonto) an die Staging-Inbound-Adresse, um die tatsächliche Verdrahtung nachzuweisen — der bestehende Submission-Loopback-Test bleibt für die übrigen (nicht-Auth-bezogenen) ACs bestehen, wird aber um einen expliziten Kommentar ergänzt, warum er den AR-Header-Pfad nicht abdeckt.
- **`spf=none`/`dmarc=none`-Verhalten:** fail-closed (ablehnen) — direkt aus der Issue-Erwartung „nur bei pass" ableitbar, keine offene Policy-Frage.

### Dependencies
1. `email_verified_at` als `Settings`-Feld deklarieren (Grundlage für alles Weitere)
2. `lookup_user_by_email`-Eindeutigkeitsfix (unabhängig von A, kann parallel/zuerst)
3. `_authorize()`-Umbau: `email_verified_at`-Pflicht + `Authentication-Results`-Parsing + `user_id == "default"`-Gate
4. Spec-Doku-Update (§5) — parallel zur Implementierung, nicht danach
5. Zwei-Nutzer- + Spoofing-Adversary-Tests zuletzt, als Abnahmekriterium
6. Prod-Datencheck (`henning`/`steffi` haben `email_verified_at` gesetzt) — Ops-Aufgabe, Blocker für Deploy, nicht für Spec/Code

### Open Questions
Keine offenen Fragen an den PO — alle drei vom Plan-Agenten aufgeworfenen Punkte sind technisch selbst entscheidbar (Test-Strategie oben festgelegt) bzw. bereits durch die Issue-Erwartung beantwortet (`spf=none` → fail-closed) bzw. ein Deploy-Ops-Task ohne Spec-Relevanz (Prod-Datencheck).
