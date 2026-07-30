# Context: fix-1412-versandweg-basis

Issue: [#1412](https://github.com/henemm/gregor_zwanzig/issues/1412) — Empfänger-Schutz strukturell verankern.
Zuschnitt-Entscheidung (PO-go 2026-07-29): eigenständig, **nicht** als Scheibe von #1337. Begründung im Issue-Kommentar.

## Request Summary

Der Schutz davor, dass eine Nachricht den falschen Empfänger erreicht, ist heute in jedem Versandkanal einzeln nachgebaut. Ziel: ein gemeinsamer Versandweg, durch den jeder Versand muss, mit der Empfänger-Prüfung im gemeinsamen Pfad statt in den Einzel-Implementierungen.

## Kernbefund der Bestandsaufnahme

Der Issue-Text nimmt „vier Inseln mit demselben Schutz" an. Die Erhebung widerlegt das in drei Punkten:

1. **Es sind fünf Sendewege, nicht vier** — der Go-Prozess versendet eigenständig per SMTP (Passwort-Reset, E-Mail-Verifikation, Magic-Link, PO-Info), mit einem zweiten, handgepflegten Regelwerk.
2. **Die Inseln sind nicht gleichartig.** Nur E-Mail (Python) hat eine Empfängerprüfung, die im **Produktivbetrieb** greift. Telegram und SMS haben ausschließlich Test-Modus-Guards, die außerhalb des Testbetriebs No-Ops sind.
3. **Der Kanal-Sammelpunkt existiert nur auf dem Papier.** `get_channel()` (`src/output/channels/base.py:65`) hat im gesamten Produktivcode genau **einen** Aufrufer — die Debug-CLI. Alle 25 anderen Versandwege bauen die Kanal-Objekte direkt.

## Versandwege — vollständige Erhebung

### Python (26 Wege)

| Gruppe | Fundstellen | Sammelpunkt |
|---|---|---|
| CLI-Report | `src/app/cli.py:257,259,261,281,283,285` | **einziger** `get_channel()`-Aufrufer |
| Trip-Briefing (Mail/SMS/Telegram-Kurzstil/Telegram-Bubbles) | `src/services/notification_service.py:1275, 315, 332, 354` | direkte Kanal-Instanzen |
| Hinweise („keine Wetterdaten", „Briefing unvollständig") | `notification_service.py:422, 429, 436, 394` | dito |
| Alert-Dispatch (Abweichung + Radar) | `notification_service.py:1071, 1085, 1092, 1105` | dito |
| Amtliche Warnung Trip | `notification_service.py:665, 681, 686, 703` | dito |
| Amtliche Warnung Ortsvergleich | `notification_service.py:885, 911, 922, 941` | dito |
| Compare-Briefing | `notification_service.py:758, 773, 791` | dito |
| Inbound-Antworten (Mail/Telegram) | `notification_service.py:1120, 1143, 1162` | dito |
| Telegram ändern/löschen/quittieren | `notification_service.py:1179, 1200, 1215` → `telegram.py:467, 425, 500` | nicht `send()` |
| Service-Fehler-Mail | `notification_service.py:1311` | direkt |
| Radar-Alert-Mail (Standalone) | `src/services/radar_alert_service.py:96` | am NotificationService vorbei |
| Kanal-Test („Test-Mail senden") | `src/services/channel_test_service.py:33-34, 38-39` | direkt |
| Bot-Menü beim Start | `api/main.py:33` → `telegram.py:523` | umgeht `send()` |
| **Sinks** (Mail/SMS/Telegram-Abfang für Tests) | `notification_service.py:663, 751, 883, 1069` / `701, 789, 939` / `771, 909, 920` | ersetzen den Transport vollständig |
| ~~**Eigener SMTP-Weg**~~ | ~~`src/app/core.py:20-23`~~ | **ERLEDIGT mit S3a** (`e9cb8e4a`, 2026-07-30) — Datei ersatzlos gelöscht, Wiederkehr durch Struktur-Test verhindert |
| MQ-Nachricht an Claude-Instanzen | `src/lib/mq_notify.py:45` | kein Endnutzer-Empfänger |

Sink-Herkunft: `src/services/trip_alert.py:783, 890, 1013`, `compare_alert.py:135`, `compare_radar_alert.py:117`, `compare_official_alert.py:134`, `scheduler_dispatch_service.py:295 ff.`

Auslöser-Endpunkte (versenden nicht selbst): `api/routers/notify.py:23`, `api/routers/scheduler.py:171, 220, 28-129`, `api/routers/webhook.py:51`, `api/routers/debug.py:115` (Staging-only, Empfänger fest verdrahtet).

**Faktischer Sammelpunkt heute:** `src/services/notification_service.py` — 18 der 26 Wege laufen dort durch. Das ist der realistische Ort für den gemeinsamen Weg, nicht `base.py`.

### Go (4 eigenständige Sendeanlässe)

| Anlass | Aufrufer | Empfänger |
|---|---|---|
| Passwort-Reset | `internal/handler/auth.go:282` | `user.MailTo`, Rückfall `user.Email` (`auth.go:237-239`) |
| E-Mail-Verifikation | `internal/handler/auth.go:689`, Test-Zweig `:682` | `user.MailTo`, Rückfall `user.Email` (`auth.go:621-623`) |
| Level-Wechsel-Antrag | `internal/handler/auth.go:848` | `cfg.PoEmail` (`internal/config/config.go:39`) |
| Magic-Link-OTP | `internal/handler/auth_magic.go:114` | eingegebene Adresse (`auth_magic.go:62, 123`) |

Alle vier über `SendWithFallback` (`internal/mail/sender.go:529`) → `Send` (`:430`) → `dialAndSend` (`:379`).

Alle **Wetter-/Briefing-/Alert-Nachrichten** ruft Go nur bei Python an (`internal/scheduler/scheduler.go:372-374, 407-409`; `internal/handler/proxy.go:257`; `internal/handler/compare_preset.go:561`). Go spricht **nie** mit Telegram oder seven.io; der einzige Telegram-Code in Go ist der eingehende Webhook-Forward (`internal/handler/telegram_webhook.go:37, 63`).

## Schutzschichten — Ist-Zustand

### E-Mail Python — vier Schichten, produktiv wirksam
| Schicht | Fundstelle | Bedingung |
|---|---|---|
| Staging-darf-nicht-Resend (`__init__`) | `email.py:337-343` | `env=="staging"` **und** Host enthält „resend" |
| Test-Modus-darf-nicht-Resend (`__init__`) | `email.py:344-351` | `is_test_mode` **und** Host enthält „resend" |
| Resend-Allowlist (`send`) | `email.py:428-475` | Zweig `if "resend" in host` |
| Lokal-Guard (`send`) | `email.py:476-514` | `else`-Zweig, nur `@henemm.com` |

Hilfsfunktionen: `_load_resend_allowlist` `:179`, `_normalized_addrs_for_guard` `:71`, `_is_reserved_test_domain` `:148`, `_raw_contains_test_mailbox` `:125`, `_is_local_mail_domain` `:169`.

Die Verzweigung bei `:428/:476` ist seit #1235 **erschöpfend** — kein Empfänger fällt durch. Verbleibende Ausprägungen des #1235-Musters siehe „Risiken".

### Telegram Python — drei Guards, alle No-Op in Produktion
`_guard_test_mode_chat_id` `telegram.py:153` (Früh-Ausstieg `:162`) · `_guard_test_mode_bot_token` `:174` (`:181`) · `_guard_test_mode_target_chat` `:192` (`:199`).
Aufrufstellen: `send` `:330-331`, Fallback ohne parse_mode `:395-396`, `delete_message` `:438-439`, `edit_message_text` `:475-476`, `set_my_commands` `:530`.
**Ohne Guard:** `answer_callback_query` `:500-521`, `get_my_commands` `:548-571`.
`_post` `:267-304` ist der **bereits vorhandene** gemeinsame Ausgang, bleibt aber ausdrücklich guard-frei (Docstring `:274-278`).

### SMS Python — ein Guard, absenderseitig
`_guard_test_mode_sandbox_key` `sms.py:32-49`, Früh-Ausstieg `:39`, Aufruf `:53` vor `httpx.post` `:61`.
`sms_to` (`sms.py:55`) wird **nie** geprüft — weder Nummernraum noch Testnummer.

### Console — keine Guards nötig (`console.py:27-39`, kein Egress)

### Go — zwei Guards, nur auf dem Resend-Host
`recipientBlocked` `sender.go:331` (steigt bei Nicht-Resend-Host mit `nil` aus, `:332`) · `resendBlocked` `:64` · `recipientBlockedForVerification` `:463` (host-unabhängig) · `rawContainsTestMailbox` `:260` · `isReservedTestDomain` `:136` · `loadResendAllowlist` `:184`.
Reihenfolge `Send`: `recipientBlocked` → `resendBlocked` → `dialAndSend` (`:430-437`); Begründung im Code `:322-325` (sonst wäre der Allowlist-Guard unter `go test` toter Code).
`egress.SMTPAllowed` `internal/egress/guard.go:98`, aufgerufen als erste Anweisung in `dialAndSend` `sender.go:379`.

## Existing Patterns

- **Kopierkette statt Struktur.** Jeder Test-Modus-Guard nennt im Docstring sein Vorbild: `email.py` #1219 → `telegram.py::_guard_test_mode_chat_id` #1288 → `sms.py::_guard_test_mode_sandbox_key` #1336 → `telegram.py::_guard_test_mode_bot_token` #1363. Die Regel ist immer dieselbe: „im Test-Modus ist ausschließlich der Test-Zugang erlaubt."
- **Fail-closed als Kompensation einer Config-Lücke.** `for_testing()` (`config.py:241-271`) benutzt `Testwert or Prodwert` (`:254-256`, `:268-270`) — fehlt der Testwert, bleibt still der Prod-Wert stehen. Die drei Kanal-Guards sind die einzige Kompensation dieser drei Zeilen.
- **Sink statt Mock als Nachweisform** (ADR-0006). Vorbild: `tests/tdd/test_telegram_test_isolation.py:78-89` — Sentinel auf `httpx.post`, der bei Berührung wirft. Stille beweist „vor dem Transport geblockt".
- **Inventar-Parität mechanisch erzwingen.** `tests/test_egress_inventory_drift.py:65-107` gleicht Python- und Go-Hostliste Zeile für Zeile ab. Das ist die einzige mechanische Go/Python-Paritätsprüfung im Bestand — und sie deckt nur Hosts ab, nicht die Guard-Logik.

## Dependencies

**Upstream:** `src/app/config.py` (`is_test_mode` `:139`, `for_testing()` `:241`, `with_user_profile()` `:278`, `is_test_user_id()` `:30`), `src/app/loader.py:1038` (`get_data_root`), `data/users/<id>/user.json` (Allowlist-Quelle, Kriterium `email_verified_at`), `src/app/egress_guard.py`, `internal/egress/`.

**Downstream:** `src/services/notification_service.py` (18 Wege), `src/services/scheduler_dispatch_service.py`, `src/services/trip_alert.py`, `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py`, `radar_alert_service.py`, `channel_test_service.py`, `inbound_telegram_reader.py`, `api/routers/{notify,scheduler,webhook,debug}.py`, `internal/handler/{auth,auth_magic,proxy,compare_preset}.go`, `internal/scheduler/scheduler.go`.

## Existing Specs

**Lebend** (`docs/specs/modules/`): `egress_guard.md`, `egress_guard_go.md`, `egress_guard_sms.md`, `egress_guard_telegram.md`, `test_email_routing_stalwart.md`, `compare_dispatch_observability_telegram_guard.md`, `smtp_mailer.md`, `python_user_channels.md`, `user_profile_channels.md`, `channel_test_button.md`.

**Archiviert — sämtliche Mail-Empfänger-Guards** (`docs/specs/_archive/modules/`): `issue_1147_resend_recipient_invariant.md`, `fix_1219_resend_allowlist.md`, `fix_1219_email_verify.md`, `fix_1219_verify_flow_2a{,_ii}.md`, `fix_1219_verify_flow_2b.md`, `issue_1235_stalwart_recipient_guard.md`, `issue_1122_resend_default_deny.md`, `issue_879_test_mail_resend_isolation.md`, `_archive/bugfix/bug_198_notify_test_resend.md`. Dazu `docs/specs/tests/no_resend_for_tests.md`.

Vier lebende Tests verweisen im Kopf auf die **Live-Pfade** dieser archivierten Dateien (`tests/tdd/test_resend_recipient_allowlist.py:3`, `test_stalwart_recipient_guard.py:3`, `test_issue_1147_resend_recipient_invariant.py:3`, `test_resend_verified_allowlist.py:4`) — die Pfade existieren dort nicht mehr.

**ADRs:** 0006 (keine Mocks, E2E gegen Staging) · 0012 (Telegram `parse_mode=HTML`, begründet den 400-Fallback als eigenen Sendeweg) · 0014 (Multi-Bubble: pro Bubble eine frische `TelegramOutput`-Instanz → Guards müssen pro Instanz greifen) · 0015 (Dual-Stack Go+Python dauerhaft → erklärt, warum jeder Guard zweimal existieren muss) · 0017 (ein `src/output/`-Paket mit `channels/`) · 0003 (Mandantentrennung, kein `"default"`-Fallback) · 0004 (Signal entfernt) · 0028 (Test-Isolation netzwerkseitig).

**Kein ADR deckt den Empfängerschutz ab** — bei elf dokumentierten Vorfällen (`tests/tdd/test_issue_1147_resend_recipient_invariant.py:8`) und einer prozess- wie sprachübergreifenden Grundsatzentscheidung. Auch `docs/reference/critical_lessons.md` enthält dazu keinen Eintrag.

## Tests — Nachweisqualität

**Am Transport-Rand (echter „hat die Leitung verlassen?"-Nachweis):**
`tests/tdd/test_telegram_test_isolation.py` (Sentinel `:78-89`) · `test_telegram_test_mode_guard.py` (`httpx.post` `:57-78`, `smtplib.SMTP` `:278-302`) · `test_sms_test_isolation.py` (`:52-63`) · `test_egress_guard.py` (`:60-80`) · `test_egress_guard_async.py` (`:48-57`) · `test_telegram_rate_limit.py:590-618`.

**E-Mail: kein Sink** — Nachweis über Exception-Typ (`test_issue_1147_resend_recipient_invariant.py:140-159`). Der Dial passiert real, unterschieden wird „Guard hat geworfen" vs. „echter SMTP-Fehler". Fehlrichtung ist fail-safe (falsch-ROT möglich, falsch-GRÜN nicht).

**Nur isolierter Guard-Aufruf — die von #1412 benannte Schwachstelle:**
`tests/unit/test_no_resend_for_tests.py:85-118` · `test_issue_1122_resend_default_deny.py:48-158` · `test_email_routing_stalwart.py:11-98` · `internal/mail/sender_allowlist_test.go:15-17` (dokumentiert ausdrücklich, dass am `Send()`-Pfad vorbei geprüft wird) · `sender_verified_allowlist_test.go` (alle 7) · `verify_send_test.go:36,52,76,96,137`.
**Die Go-Seite hat keinen einzigen Transport-Sink** — `net/smtp` lässt sich nicht patchen.

**Reihenfolge-Absicherung:** Go explizit (`internal/mail/recipient_guard_test.go:11-13`, über den vollen `Send()`-Pfad, Unterscheidung am Fehlertext) · Python Telegram indirekt (`test_telegram_rate_limit.py:590-618`) · **Python E-Mail: keine**.

## Risks & Considerations

### Bestätigte Lücken, die der Umbau schließen muss

**R1 — Der Go-Fallback umgeht den Empfänger-Guard (Sicherheitslücke, verifiziert).**
`SendWithFallback` (`internal/mail/sender.go:529-547`) behandelt jeden Fehler außer „535" als wiederholbar. Ein von `recipientBlocked` **absichtlich** geblockter Empfänger erzeugt einen Fehler ohne „535" → `Send(fallbackCfg, …)` (`:542`). Da der Fallback-Host kein „resend" enthält, steigt `recipientBlocked` dort mit `nil` aus (`:332`) — die bewusst blockierte Mail geht raus. Betrifft alle vier Go-Sendeanlässe. Ob `GZ_FALLBACK_SMTP_HOST` in Prod gesetzt ist: nicht prüfbar (`/etc/gregor/mail-prod.env` ist root-only). **Der Code-Pfad existiert unabhängig davon.** Wörtliche Wiederholung des #1235-Musters.

**R2 — Der Go-Mailweg hat auf dem produktiven Host gar keinen Empfänger-Guard.**
`recipientBlocked` `sender.go:332` steigt bei Nicht-Resend-Hosts sofort aus. Produktiv konfiguriert ist `GZ_SMTP_HOST="mail.henemm.com"` (Stalwart). Python hat für genau diesen Pfad seit #1235 den Lokal-Guard (`email.py:476-514`); Go hat kein Gegenstück, und `internal/mail/sender_allowlist_test.go:141-148` schreibt das als **gewolltes** Verhalten fest.

**R3 — Telegram und SMS haben im Produktivbetrieb keine Empfängerprüfung.**
Alle Guards sind No-Ops bei `is_test_mode == False`. Eine falsche `telegram_chat_id` oder `sms_to` im Nutzerprofil fängt nichts ab. Genau die Konstellation (Prozess-Signal statt Empfänger-Prüfung), die #1147 für Mail als unzureichend verworfen hat.

**R4 — `with_user_profile` überschreibt im Testbetrieb mit echten Empfängern.**
`config.py:307-313`: `mail_to` und `sms_to` werden **immer** aus dem Profil übernommen, `telegram_chat_id` nur wenn `not force_test`. Für Mail fängt die Allowlist das ab. **Für SMS fängt nichts es ab** — die echte Rufnummer steht im Test-Modus im Payload (`sms.py:55`), nur der Sandbox-Key verhindert die Zustellung. Dünnste Stelle im Bestand.

**R5 — Zwei getrennte, handgepflegte Regelwerke ohne Kopplung.**
Duplizierte Konstanten ohne mechanischen Abgleich: Test-Postfächer `sender.go:86-89` ↔ `email.py:33`; Roh-Regex `sender.go:248` ↔ `email.py:49-51`; reservierte Domains `sender.go:103-121` ↔ `email.py:143-145`. `LOCAL_MAIL_DOMAINS` (`email.py:40`) hat in Go **keine** Entsprechung. Gemessene Abweichungen:

| Fall | Python | Go |
|---|---|---|
| `fremd@gmail.com` über `mail.henemm.com` | blockiert (`email.py:496`) | **durchgelassen** (`sender.go:332`) |
| `"Emmrich, Henning" <henning@henemm.com>` | erlaubt (`@`-Filter `email.py:449-451`) | **blockiert** (Fragment `"emmrich` nicht in Allowlist, `sender.go:350-355`) |
| `x@sub.example.com` | erlaubt | blockiert (`sender.go:113`) |
| `a@b@example.com` | blockiert (letztes `@`) | durchgelassen (erstes `@`, `sender.go:138`) |
| Allowlist-Eintrag mit Plus-Adresse | matcht nie (`email.py:222`) | matcht nie (`sender.go:212-215`) — gemeinsamer latenter Fehler |

Fall 2 ist nutzersichtbar: wer seine Empfängeradresse mit Anzeigename und Komma einträgt, bekommt keine Passwort-Reset- und keine Magic-Link-Mail.

**R6 — Funktionsfähiger, ungeschützter Sendeweg ohne Aufrufer.**
`src/app/core.py:20` — eigener `smtplib.SMTP` + `sendmail`, Empfänger aus `os.getenv("MAIL_TO")` (`core.py:10`). Keine Allowlist, keine Domain-Prüfung, kein Test-Modus-Guard. Produktiver Aufrufer nicht gefunden (nur `tests/test_core.py:7`).

**R7 — Die mitgegebene Chat-Kennung wird auf dem Telegram-Weg verworfen.**
`NotificationService.send_telegram_message()` (`notification_service.py:1148`) und `send_command_reply_telegram()` (`:1129`) nehmen `chat_id` entgegen, reichen ihn aber nicht an `TelegramOutput.send()` weiter (`:1137-1143`, `:1159-1162`) — der tatsächliche Empfänger ist `settings.telegram_chat_id` (`telegram.py:333`). `chat_id` dient nur der Fehlermeldung (`:1145`, `:1164`). Nur `_process_start_command` gleicht das von Hand aus (`inbound_telegram_reader.py:405`, `model_copy`). Nutzersichtbare Folge an `inbound_telegram_reader.py:170`: schreibt eine unbekannte Person dem Bot, geht die „Registrierung erforderlich"-Antwort an den konfigurierten Chat statt an die Person. Eigenständiger Fehler — aber zugleich das stärkste Argument für den gemeinsamen Weg: ein Pfad, der den Empfänger verpflichtend entgegennimmt, macht diesen Fehler unbaubar.

### Umbau-Risiken

- **Produktivcode im Sicherheitspfad.** Ein Fehler heißt „Mails gehen nicht mehr raus" oder „Mails gehen an die Falschen". Staging-Nachweis vor Prod ist Pflicht.
- **Nachweisform.** Der Beleg muss ein **echter Versandversuch an eine gesperrte Adresse** sein, der geblockt wird (Sink am Transport-Rand). Ein isolierter Guard-Aufruf hat bei #1288 den Fehler nicht bemerkt.
- **ADR-0012/0014 erhalten.** Zieht man die Telegram-Guards nach `_post`, müssen der 400-HTML-Fallback und die Fail-soft-Logik unberührt bleiben; Multi-Bubble erzeugt pro Bubble eine frische Instanz.
- **Der Go-Prozess ist eine eigene Sprache.** ADR-0015 hält den Dual-Stack fest — ein gemeinsamer Weg kann kein gemeinsamer *Code* sein. Realistisch ist ein Paritäts-Zwang nach Vorbild `tests/test_egress_inventory_drift.py`, der die Guard-**Regeln** koppelt, nicht nur die Hostliste.
- **Der Sammelpunkt liegt nicht dort, wo #1412 ihn vermutet.** Nicht `base.py` ist der Hebel, sondern `notification_service.py` (18 von 26 Wegen) plus `telegram.py::_post` (bereits vorhanden, nur ungenutzt für Guards).
- **LoC.** Der Umbau berührt Mail-Renderer-nahe Dateien nicht, aber `src/output/channels/*` — das **Renderer-Commit-Gate #811** greift, sobald `channels/email.py` staged wird: `test_issue_811_mode_matrix.py` grün + frischer `briefing_mail_validator.py`-Lauf sind Pflicht.

---

# Analysis

## Type
Struktureller Umbau im Sicherheitspfad (GitHub-Label `bug`, Arbeitsform Feature).

## Betriebs-Tatsachen (gemessen, nicht abgeleitet)

`sudo grep` auf `/etc/gregor/mail-prod.env` (wird von beiden Prod-Units **nach** der Repo-`.env` geladen und überschreibt sie):

| Variable | Wert in Prod | Folge |
|---|---|---|
| `GZ_SMTP_HOST` | `smtp.resend.com` | Produktiv läuft der **Resend-Zweig** — in Python (`email.py:428`) wie in Go (`sender.go:332`). Beide Empfänger-Guards **feuern** also im Normalbetrieb. |
| `GZ_FALLBACK_SMTP_HOST` | **nicht gesetzt** | Der Go-Fallback ist inert (`sender.go:538` steigt bei leerem Host aus). |
| `GZ_IMAP_HOST` | `mail.henemm.com` | Der **Python**-Fallback ist scharf — `self._fallback_host = settings.imap_host` (`email.py:360`). |

**Das dreht die Bewertung aus der Kontext-Phase:**

- **R2 (Go ohne Guard auf Stalwart) ist heute nicht akut** — produktiv ist der Host Resend, der Guard greift. Der Defekt bleibt strukturell (eine Änderung des Hosts legt ihn frei) und `sender_allowlist_test.go:141-148` schreibt ihn als gewollt fest, aber es ist keine offene Lücke.
- **R1 (Go-Fallback umgeht den Guard) ist heute inert, nicht offen** — mangels konfiguriertem Fallback-Host. Der Code-Pfad ist eine gesetzte Umgebungsvariable von „scharf" entfernt.
- **Neu und dafür live: dieselbe Lücke existiert in Python — und dort ist sie aktiv.** Verifiziert: die Guard-Entscheidung fällt einmalig gegen `self._host` (`email.py:428/476`); die beiden Fallback-Zweige (`:580-596`, `:622-635`) dialen danach `self._fallback_host` mit **denselben** Empfängern. Der Guard des Fallback-Hosts (Lokal-Guard, nur `@henemm.com`) läuft nie. Beide realen Nutzer haben `mail_to` auf gmail.com — bei einer Resend-Störung gehen ihre Briefings über Stalwart raus, das extern weiterrelayt (infra#114).

Gemeinsame Wurzel aller drei: **die Guard-Entscheidung ist an den geplanten, nicht an den tatsächlich benutzten Postausgang gebunden.** Das ist die eigentliche Ausprägung des #1235-Musters und der erste Fixpunkt.

## Technical Approach

### Schnitt: eine gekapselte Transportfunktion je Kanal (nicht Basisklasse, nicht NotificationService)

- **Basisklasse (`base.py`) verworfen:** deckt nur `send()`. Die realen Vorfälle passierten anderswo — `telegram.py:425/467/500/523`, der 400-Fallback `:386-423`, die beiden E-Mail-Fallback-Dials. Dazu sind die `send()`-Signaturen unvereinbar (`email.py:369-379` mit `to`/`html`/`mail_type` vs. `sms.py:51`).
- **NotificationService verworfen:** belegbar umgehbar (`radar_alert_service.py:96`, `channel_test_service.py:33-39`, `api/main.py:33`, `api/routers/debug.py:113-119`) und sieht den Transport nicht.
- **Gewählt:** je Kanal genau eine Engstelle. Telegram: `_post` (`telegram.py:267-304`, existiert bereits, bekommt `chat_id` schon durchgereicht `:284`). SMS: neue `_post`-Kapselung um `httpx.post` (`sms.py:61-66`). E-Mail: neue `_dial_and_send(host, …)`, benutzt von der Primärschleife (`:536`) **und beiden Fallback-Zweigen** — Vorbild ist die Go-Seite, die das mit `dialAndSend` (`sender.go:374`) schon so trennt.

Vollständige Umgehungs-Prüfung (`grep smtplib\.|httpx.post` über `src/` + `api/` außerhalb `channels/`): `src/app/core.py:20-23` (fällt ersatzlos, R5), `src/lib/mq_notify.py:45` und `inbound_telegram_reader.py:397` (beide localhost, kein Endnutzer), Sinks (kein Egress). **Nichts bleibt übrig.** Ein AST-Struktur-Test (~40 LoC, Prüfdatum +90 Tage) sichert das ab.

ADR-0012/0014 halten: der 400-Fallback ruft `_post` mit derselben `chat_id` (`telegram.py:404`) — gleiches Urteil; die Guards werfen `OutputConfigError`, kein `httpx.HTTPError`, das Fail-soft-Verhalten (`:463`, `:497`) bleibt. Multi-Bubble baut je Bubble eine frische Instanz (`notification_service.py:344`), `_post` ist Instanzmethode.
**Nebenwirkung, positiv:** `_post` bedient auch `answer_callback_query` (`:513`), `set_my_commands` (`:536`), `get_my_commands` (`:558`) mit `chat_id=None`. Regel: Empfängerprüfung nur bei `chat_id is not None`, Token-Guard immer. Damit ist die offene Frage 3 der Kontext-Phase ohne eigene Regel beantwortet.

### Empfängervertrag: geschlossener Zweck-Aufzählungstyp statt Host-`if`

Datenlage geprüft (`internal/model/user.go:16-18, 32`): Verifikations-Zeitstempel existiert **nur** für E-Mail (`EmailVerifiedAt`). Kein `telegram_verified_at`, kein `sms_verified_at`.
Telegram ist faktisch trotzdem verifiziert — die Chat-ID entsteht im Deep-Link-Fluss (`internal/handler/telegram_connect.go` + `inbound_telegram_reader.py:388-405`) und kommt vom Telegram-Server. **Leck:** `PUT /api/auth/profile` nimmt `telegram_chat_id` als Freitext (`internal/handler/auth.go:544, 587-589`). Härtung: im PUT nur noch Leerstring (= trennen) zulassen. Dann ist das Feld verifiziert per Konstruktion — ohne neues Feld, ohne Migration. SMS bekommt in diesem Umbau keinen Verifikationsfluss.

Drei bedingungslose Prüfungen im gekapselten Transport:
1. **Empfänger explizit übergeben** — der Transport greift nicht mehr selbst nach `settings.<feld>` (`telegram.py:333`). Macht R7 unbaubar.
2. **Herkunftsbindung über Zweck:** `user_profile` · `inbound_reply` · `operator` (`cfg.PoEmail`) · `verification` (Adresse per Definition unverifiziert, engerer Guard wie `sender.go:463`). Kein Zweck ⇒ Block. Voraussetzung: `Settings` trägt heute keine `user_id` (geprüft, `config.py` kennt sie nur als Parameter) — `with_user_profile()` (`:278-313`) muss sie mitschreiben. Ein Feld.
3. **Formprüfung bedingungslos:** reservierte Test-Domains, Testpostfach-Fangnetz, Steuerzeichen; SMS zusätzlich E.164 + Testnummernraum; Telegram numerische ID.

**Warum ein Zweck-Typ und kein Host-`if`:** genau die Lehre aus #1235. Ein `if` über den Host lässt immer einen Zweig übrig; eine geschlossene Aufzählung mit Default-Block nicht.

### Go/Python-Parität: geteilte Fall-Tabelle + Regel-ID-Abgleich

ADR-0015 schließt gemeinsamen Code aus. Mechanismus:
- `tests/fixtures/recipient_guard_cases.json` — Felder `id`, `sides`, `channel`, `purpose`, `host`, `recipient`, `profiles`, `expect` (`allow`/`block`), `rule`, `since_issue`.
- Zwei Läufer: `tests/test_recipient_guard_parity.py`, `internal/mail/recipient_guard_parity_test.go`. Beide lösen die Tabelle **relativ zur eigenen Testdatei** auf (Pfadregel #1409), nie über den Hauptrepo-Pfad.
- **Die eigentliche Kopplung:** jede Guard-Funktion registriert ihre Regel-ID in einer Konstantenliste; beide Läufer prüfen, dass die Menge der IDs im Quelltext exakt der Menge in der Tabelle entspricht — Vorbild `tests/test_egress_inventory_drift.py:65-107`, auf IDs statt Hosts. Neue Regel einseitig ⇒ Tabelle unvollständig ⇒ **beide** Suiten rot.
- Verworfen: interpretiertes Regelwerk in beiden Sprachen (mehr Fläche als der Fehler), Go fragt Python-Endpoint (koppelt Passwort-Reset an Python-Verfügbarkeit), Codegenerierung (Build-Kette für ~200 Zeilen).

### Die fünf Divergenzen — Festlegung

| Fall | Urteil |
|---|---|
| `fremd@gmail.com` über `mail.henemm.com` | **Fehler, Python hat recht** — aber Pythons *Regel* taugt für Go nicht (s. Risiken). Go-Regel: verifizierte Profil-Allowlist **oder** Zweck `verification`/`operator`, **nicht** „lokale Domain". |
| `"Emmrich, Henning" <henning@henemm.com>` | **Fehler, Python hat recht.** Python vereinigt `getaddresses()` mit dem Trennzeichen-Split (`email.py:105-107`); Go splittet erst an Komma (`sender.go:348`). Go muss `mail.ParseAddressList` **vor** den Split setzen. Nutzersichtbar. |
| `x@sub.example.com` | **Fehler, Go hat recht** (`sender.go:113`); Python kennt keine Suffixe der reservierten SLDs (`email.py:143-166`). Python nachziehen. |
| `a@b@example.com` | **Entscheidung:** syntaktisch ungültig ⇒ Block, beidseitig, per echtem Parsen statt Trennzeichen-Arithmetik. |
| Plus-Adresse als Allowlist-Eintrag | **Fehler auf beiden Seiten, nutzersichtbar.** Eintrag ungekappt gespeichert (`email.py:222`, `sender.go:212-215`), Empfänger plus-gekappt normalisiert (`email.py:64-68`). Festlegung: gegen **beide** Formen vergleichen; das Fangnetz (`email.py:125-140`) bleibt unberührt. |

## Scheiben

Jede für sich prüfbar und ausrollbar; zu keinem Zeitpunkt weniger Schutz als vorher. **Je Scheibe ein eigener Workflow** (LoC-Limit 250).

| # | Inhalt | Nachweis | Frontend | grob |
|---|---|---|---|---|
| **S1** | **Guard an den tatsächlich benutzten Postausgang binden.** Python: `_dial_and_send(host, …)`, Primär- und **beide** Fallback-Zweige darauf (`email.py:536, 580, 622`). Go: Guard-Fehler als eigener Typ, `SendWithFallback` (`:529-547`) bricht bei diesem Typ ab statt am `535`-Stringvergleich. Schließt die live Python-Lücke **und** den inerten Go-Pfad. | Fallback-Dial an eine auf dem Fallback-Host unerlaubte Adresse wird geblockt (Sink am Transportrand); Go-Test über den vollen `SendWithFallback`-Pfad: kein zweiter Sendeversuch | nein | 2 Quell- + 2 Testdateien, ~120 LoC |
| **S2** | Fall-Tabelle + zwei Paritäts-Läufer + die vier Divergenzen auflösen | Tabelle rot vor Fix, grün nach Fix; Gegenprobe: eine Regel-ID einseitig entfernen ⇒ beide Suiten rot | nein | ~5 Dateien, ~200-250 LoC |
| ~~**S3**~~ → **S3a (erledigt) + S3b (offen)** | Zuschnitt geteilt (PO-go 2026-07-30, ~332 LoC über dem Limit). **S3a live (`e9cb8e4a`):** `email.py::_dial_and_send`, `core.py`+`test_core.py` gelöscht, Struktur-Test `smtplib`-Teil. **S3b offen:** Telegram-Guards nach `_post`, `sms.py::_post`, Struktur-Test `httpx`-Teil | Sentinel-Sink je Kanal (`test_telegram_test_isolation.py:78-89`) | nein | S3a ~221, S3b ~111 LoC · **Gate #811 nur bei S3a** |
| **S4a/b** | Empfängervertrag scharf: `Settings.user_id`, Zweck-Parameter an allen Aufrufstellen, Herkunftsprüfung im Transport. Telegram (a), dann SMS (b). Zwingend mit gemeinsamem Test-Helper. | Staging: Versand an fremde Chat-ID geblockt, echtes Briefing kommt an (Telegram-Kurzstil als billiger Beleg) | nein | ~300-500 LoC → **LoC-Override nötig, PO-Freigabe** |
| **S5** | Go zieht den Vertrag nach (R2), PUT-Härtung `telegram_chat_id` (`auth.go:587-589`), **ADR „Empfängerschutz"** (fehlt komplett), die vier ins Leere zeigenden Spec-Verweise in den Testköpfen | Go-Paritätsläufer grün, ADR-Index-Drift-Test grün | nur evtl. `account/+page.svelte:246` | ~200 LoC |

**Dieser Workflow liefert S1.** S2-S5 bekommen eigene Workflows.

## Scope Assessment (S1)
- Dateien: `src/output/channels/email.py`, `internal/mail/sender.go` + je eine Testdatei
- LoC: ~120 (added+deleted)
- Risiko: **HOCH** — produktiver Sicherheitspfad, live genutzter Fallback

## Risks & Considerations (Umbau)

- **Teuerste Fehlerart: Go darf Pythons Lokal-Guard nicht 1:1 bekommen.** Beide realen Nutzer haben `mail_to` auf gmail.com; Go verschickt Reset (`auth.go:282`), Verifikation (`:689`) und Magic-Link (`auth_magic.go:114`) an genau solche Adressen. „Auf Nicht-Resend-Host nur `@henemm.com`" (`email.py:476-514`) würde in Go **jeden Login-Wiederherstellungsweg** abschneiden.
- **Legitimer Versand, der bei S4 blockieren könnte:** Reset/Magic-Link/Verifikation an unverifizierte Adressen (braucht Zweck `verification`) · Inbound-Antwort an unbekannte Person (`inbound_telegram_reader.py:161-183`, braucht `inbound_reply`) · `/start`-Bestätigung (`:405`, der Chat ist gerade erst registriert — Go schreibt, Python liest, Race beachten) · Betreiber-Mail an `cfg.PoEmail` (`auth.go:848`, braucht `operator`) · Kanal-Test (`channel_test_service.py:25`).
- **Test-Massenumbau bei S4:** 58 Teststellen setzen erfundene `telegram_chat_id` (z.B. `test_952_onset_alert_fidelity.py:258`, `test_issue_816_alert_deviation.py:139`), 12 setzen `sms_to`, 20 Dateien fangen `httpx.post` ab und laufen wirklich durch den Kanal. Ohne gemeinsamen Test-Helper sprengt das jedes LoC-Limit.
- **Tests, die sich drehen müssen:** `internal/mail/sender_allowlist_test.go:141-148` (`TestRecipientBlocked_StalwartHostGuardInactive`) — schreibt das heutige Verhalten als gewollt fest, einziger Go-Test dieser Bauart. Mittelbar: `sender_test.go` (13), `recipient_guard_test.go` (21), `verify_send_test.go` (9).
  Python: `test_email_routing_stalwart.py`, `test_stalwart_recipient_guard.py`, `test_resend_recipient_allowlist.py`, `test_resend_verified_allowlist.py`, `test_issue_1122_resend_default_deny.py`, `tests/unit/test_no_resend_for_tests.py` prüfen isoliert — bei Verlagerung in den Dial müssen sie auf den neuen Aufrufpunkt umgestellt werden, sonst prüfen sie eine Funktion, die niemand mehr aufruft (**falsches Grün, exakt das #1288-Muster**).
  `test_issue_671_bot_menu_autoset.py` kann rot werden, weil `get_my_commands`/`answer_callback_query` erstmals den Token-Guard bekommen.
- **Nachweisform:** Sink am Transportrand, nie über einen Sink-Pfad des NotificationService (die erzeugen keinen Egress). Go hat keinen Transport-Sink (`net/smtp` nicht patchbar) — dort bleibt „Fehler kam vor dem Dial zurück" (`sender_egress_test.go:28-44`).
- **Rebase:** `origin/main` steht auf `9cdb492c` (#1362 S5b aus fremder Sitzung), dieser Arbeitsstand auf `323c4a83`. Vor dem ersten Commit nachziehen — das Commit-Gate misst den Sitzungs-Worktree.

## Offene Punkte
- LoC-Override für S4 braucht PO-Freigabe (zu gegebener Zeit, nicht jetzt).
- Rot-Umfang der Go-Tests nach S5 lässt sich erst nach dem Umbau messen.
