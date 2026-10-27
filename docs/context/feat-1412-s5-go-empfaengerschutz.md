# Context: feat-1412-s5-go-empfaengerschutz

## Request Summary

Issue #1412, Scheibe S5: Go zieht den Empfängerschutz nach (Divergenz **D1**). Dazu gehören das ADR „Empfängerschutz“ und die offenen Sollwerte aus Nebenbefund **C3-20**. D1 ist die letzte Ausnahme im Paritäts-Prüfwerkzeug. Ihre Frist läuft am **2026-10-28** ab, danach werden beide Läufer rot.

## Korrekturen an der Ausgangslage (Repo-Stand 2026-10-13, gegengeprüft)

- **PUT-Profil-Härtung ist bereits erledigt** (#2141, `b39ff6a79`, 2026-09-07). `internal/handler/auth.go:1270-1280` übernimmt bei `telegram_chat_id` nur den Leerstring („Telegram trennen“). Einziger Setz-Weg ist der localhost-gesperrte Einmal-Token-Flow `/start TOKEN` → `PostTelegramConnectHandler` (`internal/handler/telegram_connect.go:269-326`, Setzen bei `:318`). Weitere Schreiber gibt es weder in Go, noch in Python, noch im Frontend (`frontend/src/routes/account/+page.svelte:459` sendet nur `''`). Tests dazu: `internal/handler/profile_telegram_chat_id_test.go:56,92,119`. Die Known Limitation in der S4a-Spec (`fix_1412_s4a_...md:271-275`, zitiert „auth.go:544, :587-589“) ist **veraltet**. Für S5 bleibt hier nur, die Spec-Notiz nachzuziehen und den Punkt im ADR festzuhalten.
- **Go versendet keine Briefings und keine Alerts.** Go hat keinen eigenen Telegram- oder SMS-Client. SMS-Codes gehen über den Python-Core (`sms_verify.go:96-118`), Telegram nimmt Go nur als Webhook an und leitet ihn weiter.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/mail/sender.go:387-435` | `recipientBlocked`: **D1**. Bei einem Host ohne „resend“ (`:388`) gibt es `return nil`. Fangnetz `rawContainsTestMailbox` (`:394`), Allowlist (`:207-245`, nur verifizierte Profile, `mail_to` sonst `email`) und `PoEmailFromEnv` (`:406`) greifen erst danach |
| `internal/mail/sender.go:498-506, 584-624` | `Send` (recipientBlocked → resendBlocked → dialAndSend), `SendVerificationMail`, `SendWithFallback` (`ErrGuardBlocked` = kein Fallback, S1) |
| `internal/mail/sender.go:531-574` | `recipientBlockedForVerification`: schon heute **ohne Host-Weiche** (Fangnetz, Steuerzeichen, eine nackte addr-spec, reservierte Domain). Kommentar „genau EIN Aufrufer“ (`:579-580`) veraltet, es sind 4 |
| `internal/mail/sender.go:335-374, 290-293` | `splitRecipientField`, `rawContainsTestMailbox`: Go-Seite von C3-20 |
| `internal/handler/auth.go:421, 477-523` | Passwort-Reset über `SendWithFallback` → `Send`; Empfänger `MailTo` sonst `Email`, auch unbestätigt; Test-User über Google-SMTP |
| `internal/handler/auth.go:1716, 1744` | Tier-Antrag an `cfg.PoEmail` (Default `gregor_zwanzig@henemm.com`, `config.go:13`) über `Send` |
| `internal/handler/auth.go:1479-1536`, `auth_magic.go:123`, `auth_oauth.go:352-371`, `account_delete_code.go:150-157` | Verifikations-, Magic-, Google-Hinweis- und Lösch-Code-Mail über `SendVerificationMail` (bei Test-User über `SendWithFallback`). **Nicht** von D1 betroffen |
| `internal/egress/guard.go:65-107`, `inventory.go:42` | Egress-Wächter: auf Staging (`GZ_ENV=staging`) ist SMTP nur zu `mail.henemm.com` erlaubt |
| `src/output/channels/email.py:746-806` (Resend-Zweig), `:807-840` (Sonst-Zweig #1235), `:79` `LOCAL_MAIL_DOMAINS={"henemm.com"}`, `:229-236` `_is_local_mail_domain` (rstrip "."), `:121-174` `_normalized_addrs_for_guard` | Python-Vorbild. Nicht-Resend-Zweig: nur `@henemm.com`, reservierte Domains blocken, Fangnetz **bewusst aus** (gregor-test@ lokal erlaubt) |
| `src/output/channels/recipient.py:34-38` | `RecipientPurpose` = `user_profile`, `inbound_reply`; `verification` erst S4b (nur Docstring) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | 17 Fälle, 2 davon auf `mail.henemm.com` (D1 `fremd@gmail.com` soll=block, N2b `henning@henemm.com.` soll=allow). Ausnahme D1 (seite go, ist allow, frist 2026-10-28), `ausnahmen_hoechstzahl: 1`, `verzweigungen_go: 35` |
| `tests/test_mail_recipient_parity.py` | Python-Läufer. AC-3 verlangt das Entfernen der Ausnahme, sobald gemessen == soll; AC-6 schlägt bei abgelaufener Frist an. Verzweigungsratsche (AST, ca. `:581-640`), `EXPIRY` `:59, :669` |
| `internal/mail/recipient_parity_test.go` | Go-Läufer, ruft `recipientBlocked` direkt auf (`:204-211`); Ratsche zählt nur `guardRegionFuncs` (`:346-354`) |
| `docs/analysis/triage-1199-2026-09-08.md:435` | C3-20 (`, garbage`, ` garbage`, gequoteter Local-Part); keine `garbage`-Fälle in `faelle.json` |
| `docs/adr/README.md:151` | höchste ADR = 0086 → **neues ADR 0087 „Empfängerschutz“** |

## Existing Patterns

- **Zweige statt Einheitsregel (Python):** Der Resend-Zweig verwendet die Allowlist verifizierter Profile. Der lokale Relay-Zweig erlaubt nur die eigene Domain. Reservierte Test-Domains blocken immer. Go spiegelt bisher nur den Resend-Zweig.
- **Zweckgetrennte Guards (Go):** `recipientBlockedForVerification` ist eine eigene, schärfere Formprüfung für Mails an unbestätigte Adressen. Das ist faktisch der „Zweck `verification`“ auf der Mail-Seite, nur ohne Namen.
- **Staging-Ersatzwege statt echter Mail:** `internal/handler/staging_verify_token.go` (#2304), `staging_sms_code.go`.
- **Paritätsratsche:** Ausnahmen mit Frist; Messung == Soll erzwingt das Entfernen der Ausnahme.

## Dependencies

- Upstream: Allowlist (`data/users/*/user.json`, `email_verified_at`), `config.PoEmailFromEnv`, Egress-Wächter, Stalwart → Resend-Relay (infra#114).
- Downstream: Passwort-Reset und Tier-Antrag (Go, `Send`). Fallback-Pfad (`SendWithFallback`). Paritäts-Läufer beider Sprachen. 8 Go-Tests mit `Host: "127.0.0.1"`, die den ungeschützten Stalwart-Pfad festnageln (u.a. `sender_allowlist_test.go:141` `TestRecipientBlocked_StalwartHostGuardInactive`, `recipient_guard_test.go:102`, `resend_guard_test.go:100`); `sender_integration_test.go:55` (Tag integration).

## Existing Specs

- `docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md` (S1, verweist das ADR an S5 `:402-407`)
- `fix_1412_s2a_regelwerk_paritaet.md` (Prüfwerkzeug; D1 → S5 `:78`, N2b-Warnung `:171`)
- `fix_1412_s2b_divergenzen_aufloesen.md` (nur D1 bleibt, `:132, :140`)
- `fix_1412_s3a_transport_kapselung_mail.md`, `fix_1412_s3b_telegram_sms_ausgang.md`
- `fix_1412_s4a_empfaengervertrag_telegram.md` (Known Limitation PUT-Profil veraltet)

## Risks & Considerations

1. **Welche Regel bekommt Go auf Stalwart?**
   - Die **Python-Lokalregel** (nur `@henemm.com` plus reservierte Domains) hält D1 und N2b paritätisch, weil rstrip(".") nötig ist. Verlust: Reset-Mails an Fremdadressen über Stalwart.
   - Die Variante **„Host-Weiche streichen“** (Resend-Regel überall) blockiert über das Fangnetz zusätzlich gregor-test@ und gregor-staging@ sowie alle unverifizierten Empfänger. Sie wäre auch **nicht paritätisch** zu Python. N2b kippt dann in eine echte Divergenz.
2. **Wirkung in Prod:** Prod-Go sendet über Resend (Zweig unverändert). Fällt Resend aus, geht der Fallback über Stalwart; dort griffe die neue Regel. Wer dann eine Reset-Mail an eine Fremdadresse anfordert, bekommt sie nicht. Das ist eine Verhaltensänderung, sie muss sichtbar sein (Log, Fehler) und darf nicht still bleiben.
3. **Passwort-Reset an unbestätigte Adressen:** Der Reset geht heute auch an unbestätigte `Email`. Im Resend-Zweig blockt die Allowlist das bereits. Ob Reset ein eigener Zweck sein soll (wie Verification), ist eine Designfrage für die Analyse.
4. **Staging-Nachweis:** Der Pflicht-Nachweis „echter Versandversuch an eine gesperrte Adresse wird geblockt“ ist auf Staging über den Go-Reset-Pfad (Stalwart) möglich. Die Staging-`.env` (`GZ_GOOGLE_SMTP_HOST` für Test-User) ist aus dem Repo nicht belegbar und muss auf Staging gemessen werden.
5. **Bestandstests:** 8 Go-Tests nageln „Stalwart ungeschützt“ fest. Sie müssen bewusst umgestellt werden, nicht gelöscht, und jeweils mit Gegenprobe.
6. **C3-20:** Sollwerte für `, garbage`, ` garbage` und den gequoteten Local-Part fehlen. Eine Messung scheiterte lokal am fehlenden Import `anyascii`. Fälle in `faelle.json` aufnehmen; die Sollwerte festzulegen ist eine PO-taugliche Fachfrage („soll eine Adresse mit Anhängsel geblockt werden?“). Der Vorschlag wäre Block (sicher).
7. **Regel-Budget:** kein neues Gate. Die Ratsche verkleinert sich (Ausnahme D1 fällt weg, `ausnahmen_hoechstzahl` 1 → 0).
8. **S4b offen:** Der Mail-Zweck `verification` existiert in Go faktisch schon (eigener Guard). S5 hängt deshalb **nicht** an S4b.

## Analysis

### Type
Feature (Schließen einer strukturellen Schutzlücke + Paritätsabschluss), Issue #1412 Scheibe S5.

### Gemessene Betriebs-Tatsachen (2026-10-14, nicht abgeleitet)
- **Prod-Go:** `GZ_SMTP_HOST=smtp.resend.com` (über `/etc/gregor/mail-prod.env`, Messung aus `fix-1412-versandweg-basis.md:182-188`), `GZ_FALLBACK_SMTP_HOST` **nicht gesetzt** ⇒ in Prod ändert S5 heute **nichts** am Normalbetrieb; die neue Regel greift nur, falls jemand den Host/Fallback auf Stalwart stellt (genau dafür ist sie da).
- **Staging-Go:** `GZ_SMTP_HOST="mail.henemm.com"` (Stalwart, Primärweg!), `GZ_GOOGLE_SMTP_HOST="smtp.gmail.com"`; Egress-Wächter erlaubt auf Staging SMTP nur zu `mail.henemm.com` ⇒ der Google-Weg ist auf Staging ohnehin tot. Ein Passwort-Reset eines **normalen** Staging-Kontos trifft die neue Regel **direkt** (kein Fallback-Rezept nötig).
- **Staging-Log lesbar:** `journalctl -u gregor-api-staging` funktioniert für `hem` ⇒ Block-Nachweis über Logzeile ist messbar (Reset antwortet aus Anti-Enumeration-Gründen immer „ok“).
- **Google-SMTP-Pfad** (Test-Konten, `auth.go:487-503`, eingeführt #124 `password_reset_mail.md:80`): Zweck war nur „Test-User nicht über Resend“. Keine Begründung für Versand an Fremddomains belegt; Test-/Wegwerf-Konten nutzen `gregor-test+…@henemm.com`.
- **Python-Envelope:** `send()` übergibt die Empfängerliste unverändert an `server.sendmail` (`email.py:543`, `:717-719`); der Nicht-Resend-Guard prüft dagegen eine gefilterte Sicht (`_normalized_addrs_for_guard`, Fragmente ohne `@` verworfen, `:821`) ⇒ Guard-/Envelope-Mismatch bei C3-20-Fall A.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/mail/sender.go` | MODIFY | `recipientBlocked`: Host-Weiche bleibt (Resend ⇒ Allowlist wie bisher), **Nicht-Resend ⇒ Python-Lokalregel** (nur `henemm.com` nach `rstrip(".")`/lowercase, reservierte Domains block, leere/@-lose Kandidaten block, Fangnetz `rawContainsTestMailbox` bewusst AUS). Klarer Fehlertext mit `ErrGuardBlocked`. Kommentar „genau EIN Aufrufer“ (`:579-580`) korrigieren |
| `internal/handler/auth.go` | MODIFY | Reset-Goroutine: bei `ErrGuardBlocked` eindeutige Logzeile (Host-Klasse, kein Klartext-Empfänger nötig); Antwort bleibt `{"status":"ok"}` |
| `src/output/channels/email.py` | MODIFY | C3-20 A: Guard und Envelope auf dieselbe Liste bringen bzw. Fragment ohne `@` ⇒ block (Mechanik in Spec festlegen) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | MODIFY | Ausnahme D1 entfernen, `ausnahmen_hoechstzahl` 1→0, neue Fälle C3-20 A/B/C je Host (+ „Nachname, Vorname <a@henemm.com>“ ungequotet), `verzweigungen_go` auf neuen Wert (Ratsche verlangt exakte Zahl) |
| `internal/mail/recipient_parity_test.go`, `tests/test_mail_recipient_parity.py` | MODIFY (ggf.) | nur falls Läufer neue Fallform brauchen |
| `internal/mail/resend_guard_test.go:100`, `recipient_guard_test.go:102`, `fallback_guard_test.go:66`, `sender_allowlist_test.go:141`, `sender_egress_test.go:56` (prüfen) | MODIFY | Tests, die „Stalwart ungeschützt“ festnageln, auf neues Soll umstellen (Fremdadresse block / `@henemm.com` allow), nicht löschen; Gegenprobe |
| 5 Testköpfe: `sender_allowlist_test.go:12`, `recipient_guard_test.go:9`, `resend_guard_test.go:12`, `sender_verified_allowlist_test.go:6`, `verify_send_test.go:9` | MODIFY | tote Spec-Verweise → `docs/specs/_archive/modules/…` (Plan sprach von vier, es sind **fünf**) |
| `docs/adr/0087-empfaengerschutz.md` + `docs/adr/README.md` | CREATE/MODIFY | ADR „Empfängerschutz“ |
| `docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md:271-275` | MODIFY | veraltete Known Limitation (PUT-Härtung erledigt #2141) korrigieren |
| `docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md` | CREATE | Spec |

### Scope Assessment
- Produktive Dateien: 3 (`sender.go`, `auth.go`, `email.py`), geschätzt +60–90 LoC produktiv; Tests/Fixtures +100–150; Docs zählen nicht.
- LoC-Stand laut `workflow.py status`: +0/250 — Override voraussichtlich nicht nötig, da nur produktive Spec-Dateien zählen.
- Risk Level: **MEDIUM** — Prod-Normalbetrieb unberührt (Resend), aber Staging-Verhalten ändert sich (Reset an Fremdadressen dort geblockt) und 5 Bestandstests drehen ihr Soll.

### Technical Approach (Empfehlung, nach Gegenprüfung)
**Variante A′: Eine Regel für alle Nicht-Resend-Hosts = Python-Lokalregel. KEINE Google-Ausnahme.**
Abweichung von der Plan-Empfehlung (Variante B mit Google-Ausnahme per Hostname-Substring) — Begründung:
1. Die Google-Ausnahme wäre eine ungeprüfte Lockerung per Namensraten (`"google"|"gmail"` im Host) und eine Go-only-Divergenz, die die Ratsche als Ausnahme führen müsste. Kein belegter Bedarf (Test-Konten → `@henemm.com`).
2. Auf Staging ist der Google-Weg durch den Egress-Wächter ohnehin gesperrt; in Prod nicht nachweislich konfiguriert.
3. Fail-closed: jeder Nicht-Resend-Host (Stalwart, Google, künftige) bekommt die strenge Lokalregel ⇒ Mails an Fremdadressen nur noch über Resend mit verifizierter Allowlist. Das ist der Kern des ADR.
4. Vollständige Parität zu Python (D1 und N2b bleiben paritätisch, keine neue Ausnahme).

Varianten-Vergleich:
| Variante | Nicht-Resend-Regel | D1 | N2b | Test-Konten (Google) | Prod heute | Ratsche |
|---|---|---|---|---|---|---|
| **A′ (empfohlen)** | Lokalregel für alle | gelöst | allow, paritätisch | Fremdadresse geblockt (kein belegter Bedarf, Staging-Egress sperrt Google ohnehin) | unverändert (Resend) | Ausnahmen 0 |
| B (Plan) | Lokalregel + Google ausgenommen per Substring | gelöst | paritätisch | unverändert | unverändert | braucht Go-Ausnahme, Hostname-Raten |
| C Host-Weiche streichen | Resend-Regel überall | gelöst | kippt (Divergenz) | geblockt | unverändert | neue Divergenz, gregor-test@ auf Staging geblockt |
| D Frist verlängern | keine | offen | — | — | — | Ausnahme bleibt — nur Notausgang |

**C3-20-Sollwerte (Tech-Lead-Entscheid, im Zweifel blocken; erscheint als AC in der Spec):**
- A `a@henemm.com, garbage` ⇒ **block** auf beiden Hosts (Python ändern: Guard sieht, was der Postausgang bekommt).
- B `a@henemm.com garbage` ⇒ **allow** (wie `a@henemm.com`, beide Seiten heute gleich; nur festnageln).
- C `"x y"@henemm.com` ⇒ Resend **block** (nicht in Allowlist), Stalwart **allow** (Domain lokal).
- Zusatzfall `Nachname, Vorname <a@henemm.com>` (ungequotet) ⇒ Soll in Spec festlegen; erwartet block (fail-closed), gequotete Form allow.

**ADR 0087 „Empfängerschutz“** — Inhalt: (a) Grundsatz: Fremdadressen nur über Resend + verifizierte Allowlist; jeder andere Postausgang nur eigene Domain; Test-Domains immer gesperrt; Entscheidung am **tatsächlich benutzten** Postausgang (S1). (b) Zwecke: `user_profile`, `inbound_reply`, `verification` (Go faktisch via `recipientBlockedForVerification`, host-unabhängig). (c) Fangnetz Test-Postfach nur auf Resend. (d) C3-20-Sollwerte. (e) Telegram-`chat_id` nur über Einmal-Token-Flow (#2141). (f) Go versendet keine Briefings/Alerts. (g) Paritäts-Prüfwerkzeug als Wächter (Python+Go gegen gemeinsame Sollwerte).

### Staging-Nachweis (geplant)
Normales Staging-Konto (ohne Testflag) mit Fremdadresse ⇒ Reset anfordern ⇒ `journalctl -u gregor-api-staging` zeigt Guard-Block; Gegenprobe: Wegwerf-Konto `gregor-test+…@henemm.com` ⇒ Reset-Mail kommt im Stalwart-Testpostfach an.

### Dependencies
- Upstream: Allowlist (`data/users/*/user.json`), Egress-Wächter, Stalwart-Relay (infra#114), S1 (`ErrGuardBlocked` ⇒ kein Fallback).
- Downstream: Passwort-Reset, Tarif-Antrag (an `gregor_zwanzig@henemm.com` ⇒ lokal, unberührt), Test-Konto-Verifikation über `SendWithFallback`, beide Paritäts-Läufer. Hängt **nicht** an S4b.
- Frist: Ausnahme D1 läuft **2026-10-28** ab.

### Open Questions
- [x] Regel auf Nicht-Resend — entschieden: A′ (Tech Lead).
- [x] C3-20-Sollwerte — entschieden (s. o.), Freigabe über Spec-ACs.
- [ ] Python-Mechanik für Fall A (gleiche Liste für Guard+Envelope vs. „Fragment ohne @ ⇒ block“) — in `/30-write-spec` festlegen; Präferenz: gleiche Liste.
