# Context: fix-2147-email-eindeutig

## Request Summary

PO-Vorgabe (2026-09-13): **Eine E-Mail-Adresse darf es im System nur einmal geben.** Issue #2147
(Magic-Link nimmt den ersten Treffer → Session im fremden Konto) und #2311 (Magic-Link mit
`mail_to`-Adresse legt Zweitkonto an) werden gemeinsam gelöst.

Arbeitsannahme aus dem Intake (in der Spec vom PO zu bestätigen): eindeutig sind die
**Konto-Adressen** `email` und `mail_to`, kreuzweise, case-insensitive. Empfängerlisten
(Mitwanderer) fallen nicht darunter.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:63-120` | Register — setzt `Email=MailTo=req.Email` roh; Z. 75 Kommentar „keine Uniqueness-Prüfung (Spec)"; 409 nur für Username |
| `internal/handler/auth.go:720-812` | PUT `/api/auth/profile` — keine Normalisierung/Uniqueness; Verifikations-Reset bei Adresswechsel existiert (Z. 768-777) |
| `internal/handler/auth.go:858-882` | `selfHealEmailVerification` — vergleicht nachgewiesene Adresse gegen `MailTo` (Rückfall `Email`) |
| `internal/handler/auth_magic.go:61-77, 202-227` | Magic-Link-Request: `FindUserByEmail`, bei Nicht-Treffer **sofort** Neuanlage (`m-xxxx`) schon beim Code-Anfordern; immer 200 |
| `internal/handler/auth_oauth.go:156-240` | Google-OAuth sucht **nur** per `OAuthSub`, legt sonst `g-xxxx` mit Email=MailTo an → Duplikat zu bestehendem Passwort-/Magic-Konto |
| `internal/handler/passkey.go:455-584` | Öffentliche Passkey-Registrierung: Begin merkt Mail, Finish speichert Email/MailTo; 409 nur Username |
| `internal/store/user.go:409-476` | `FindUserByEmail` (nur `Email`, erster Treffer, kein Testnutzer-Filter), `FindUserByOAuthSub`, `FindUserByTelegramChatID` (Testnutzer-Filter) |
| `internal/store/user.go:19-88` | `ListUserIDs` (Verzeichnis-Scan), `LoadUser`, `SaveUser` (atomar, **ohne Lock**) |
| `internal/handler/telegram_connect.go:171, 205-208` | **Vorlage:** `telegramConnectMu` hält Prüfung+Speichern unter globalem Lock (#2141, TOCTOU) |
| `internal/model/test_user.go:36` | `IsTestUserID` |
| `internal/mail/sender.go:205-240` | Resend-Allowlist liest Email+MailTo aller bestätigten Konten (Map, mehrfach egal) |
| `cmd/server/main.go:61-83` | Start nach `store.New` — Andockpunkt für einen Duplikat-Report beim Start |
| `src/app/loader.py:1232-1285` | `lookup_user_by_email` — vergleicht **nur `mail_to`**; ≥2 echte Treffer → `None` + error (#2143); Testnutzer: echter Treffer gewinnt (#1013) |
| `src/app/loader.py:1287` | `lookup_user_by_telegram_chat_id` — gleiches Muster |
| `src/services/inbound_email_reader.py:130-134, 218-262` | `None` → Abbruch, kein Kommando; `_authorize` prüft SPF/DKIM, `email_verified_at` |
| `frontend/src/routes/register/+page.server.ts:39-40` | 409 fest auf „Benutzername bereits vergeben" verdrahtet — neuer 409-Grund bräuchte Unterscheidung |
| `frontend/src/routes/account/+page.svelte:286-301, 449-451, 490-497` | Nur `mail_to` editierbar; Fehler wird roh (`body.detail ?? body.error`) angezeigt |

## Existing Patterns

- **Eindeutigkeit mit Besitz-Semantik:** Telegram-Chat-ID (#2141) — Spec `docs/specs/modules/telegram_chat_id_ownership.md`, Handler-Lock `telegramConnectMu`, 409 `chat_id_already_linked`, Testnutzer ausgenommen (`IsTestUserID`), Re-Connect desselben Nutzers erlaubt. Tests: `internal/handler/telegram_connect_uniqueness_test.go` (Zwei-Nutzer-Muster).
- **Mehrdeutigkeit fail-closed:** Python `lookup_user_by_email` gibt bei ≥2 echten Treffern `None` zurück (#2143).
- **Enumeration:** Magic-Link, Forgot-Password, Resend antworten immer neutral 200. Register und Passkey-Begin geben schon heute 409 für vergebene **Usernames**.
- **Normalisierung:** keine Hilfsfunktion; inline `ToLower(TrimSpace)` nur in `auth_magic.go:61,145`, `auth.go:859`. Register/Profil/Passkey/OAuth speichern roh.
- **Migrationen:** eigene Kommandos (`cmd/migrate1257`, `cmd/migrate1258`) bzw. Python-Skript (`scripts/migrate_1219_email_verified.py`), nicht beim Serverstart.

## Dependencies

- **Upstream:** `store.ListUserIDs/LoadUser/SaveUser`, `model.IsTestUserID`, Bestätigungsmail (`internal/mail/verify.go`), Login-Gate #2271 (ADR-0066).
- **Downstream:** Magic-Link-Login, Google-Login, Passkey-Login/-Registrierung, Profil-Speichern im Frontend (`/account`), Registrierungsseite, Inbound-Mail-Zuordnung (Python), Resend-Allowlist, E2E-Setups auf Staging.

## Existing Specs

- `docs/specs/modules/user_auth_endpoints.md` (:141/:197) — Register, 409 nur Username
- `docs/specs/modules/register_page.md` (:85/:142)
- `docs/specs/modules/account_page.md`, `account_page_extend.md`, `user_profile_channels.md`, `konto_erweitern.md`
- `docs/specs/_archive/modules/issue_449_magic_link.md` — Magic-Link
- `docs/specs/modules/google_oauth_login.md`
- `docs/specs/modules/passkey_webauthn.md`, `passkey_konto_verwaltung.md`
- `docs/specs/modules/email_verify_vorbereitung_2304.md`, `email_verify_scharfschaltung_2271.md`
- `docs/specs/modules/telegram_chat_id_ownership.md` — **Vorlage**
- `docs/reference/api_contract.md` §19: Register 2625-2658 (Z. 2642 „no uniqueness check"), Profil 3019-3064 (Z. 2999 „mail_to can differ from email"), Telegram-409 3065-3100
- ADRs: 0060, 0062, 0066 — keine behandelt Adress-Eindeutigkeit ⇒ vermutlich **neues ADR** nötig (Entscheidungsfläche Auth/Datenmodell)

## Risks & Considerations

1. **Bestandsdaten mit Duplikaten (unbekannt).** `/var/lib/gregor` und `/var/lib/gregor-staging` sind aus der Sitzung nicht lesbar. Wahrscheinlich gibt es auf Prod/Staging schon Dubletten (Google-OAuth legt bei bestehender Adresse immer ein Zweitkonto an; Magic-Link-Neuanlage schon beim Code-Anfordern). Eine harte Regel darf bestehende Konten **nicht aussperren** (Lehre #2271/#2304). Messung nötig — nur Zählung, keine Adressen ausgeben.
2. **Enumeration:** 409 „Adresse vergeben" bei Registrierung macht Adressen abfragbar (#2163). Abwägung: Usernames sind heute schon abfragbar; Alternative neutrale Antwort + Hinweismail an den Besitzer.
3. **Magic-Link-Neuanlage beim Code-Anfordern** erzeugt Konten für fremde Adressen (Spam/Besetzen einer Adresse: Angreifer fordert Code für `opfer@…` an → Konto `m-xxxx` besetzt die Adresse, das Opfer kann sich nicht mehr registrieren). Mit Uniqueness wird das zu einem **Besetz-Angriff** — Neuanlage sollte erst nach bestätigtem Code erfolgen oder unbestätigte Konten dürfen keine Adresse blockieren.
4. **Unbestätigte Konten als Adress-Besetzer allgemein:** Wer bei Register/Profil fremde Adresse einträgt, sperrt den echten Besitzer aus. Frage für die Spec: Zählt nur eine **bestätigte** Adresse als vergeben, oder jede?
5. **Google-OAuth:** bestehendes Konto mit gleicher (von Google bestätigter) Adresse → verknüpfen oder abweisen? Verknüpfen = Account-Übernahme-Risiko nur, wenn Google-Mail unbestätigt; Google liefert `email_verified`.
6. **Nebenläufigkeit:** kein Store-Lock; Prüfung+Speichern muss unter einem globalen Lock (Muster `telegramConnectMu`) über **alle** Schreibpfade laufen, sonst TOCTOU.
7. **Testnutzer:** Python-Tests (`test_issue_1013_telegram_test_isolation.py:142-154`) teilen bewusst `mail_to` zwischen echtem und Test-Nutzer; Staging-Skript `scripts/setup_staging_validator_trip.py` schreibt `gregor-test@henemm.com` direkt in ein Validator-Konto. Ausnahme für Testnutzer analog #2141 nötig.
8. **Frontend:** Registrierung zeigt jeden 409 als „Benutzername vergeben"; Konto-Seite zeigt Fehlercodes roh → beide brauchen eine verständliche Meldung.
9. **Python-Lookup** vergleicht nur `mail_to`, Go-Magic-Link nur `email` — nach der Regel sollten beide dasselbe Adressverständnis haben (beide Felder).
10. **Performance:** Jede Prüfung ist Verzeichnis-Scan über alle Konten — bei heutiger Nutzerzahl unkritisch, bei Register/Profil-Update akzeptabel.

## Analysis

### Type

Bug (Sicherheitslücke #2147) + Produktregel „Adresse nur einmal" (PO 2026-09-13).

### Scheibenschnitt (Tech-Lead-Entscheid)

LoC-Limit 250 Prod je Workflow; Gesamtumfang ~250 Prod + ~410 Test ⇒ drei Scheiben. #2147 bleibt bis Scheibe C offen.

| Scheibe | Inhalt | Issue | Prod/Test-LoC |
|---|---|---|---|
| **A (dieser Workflow)** | Magic-Link: keine Kontoanlage beim Anfordern, Auflösung erst beim Einlösen unter gemeinsamem Adress-Lock; `FindUserByEmail` über `email`+`mail_to`, Mehrdeutigkeit fail-closed; Schutz gegen vorab angelegte Fremdkonten | #2147 | ~120 / ~180 |
| B | Register / Profil / Passkey: 409 `email_taken` bei Kollision, Frontend-Meldungen, Normalisierung beim Speichern, Python-Lookup über beide Felder | #2147 + #2311 | ~90 / ~180 |
| C | Google-Login: bestehendes **bestätigtes** Konto gleicher Adresse verknüpfen statt Zweitkonto; Start-Report Kollisionszähler (ohne Adressen); ADR „Adress-Eindeutigkeit" | #2147 | ~40 / ~80 |

### Entscheidungen (Tech Lead, begründet — in der Spec als ACs)

1. **Adressbegriff:** `email` und `mail_to` kreuzweise, getrimmt, ohne Groß-/Kleinschreibung. Empfängerlisten nicht betroffen. Testnutzer (`IsTestUserID`) sind ausgenommen (Muster #2141).
2. **Unbestätigt versperrt nie den Weg des echten Besitzers.** Wer eine Adresse per Magic-Link nachweist, gelangt in das Konto, das diese Adresse trägt. Ist dieses Konto noch unbestätigt, konnte es jeder mit fremder Adresse angelegt haben ⇒ beim Einlösen werden alle Zugänge entfernt, die ohne Adressnachweis entstanden sind (Passwort, Passkeys, Google-Verknüpfung, bestehende Sitzungen); danach bestätigt. Abwehr gegen „Pre-Account-Hijacking" (Sudhodanan/Paverd 2022). Datenverlust: keiner (unbestätigte Konten können seit #2271 nicht einloggen, tragen also praktisch keine Daten; die Konto-Daten bleiben erhalten).
3. **Auflösung bei Mehrfachtreffer:** genau ein bestätigtes Konto → dieses; kein bestätigtes, genau ein unbestätigtes → dieses (mit Regel 2); sonst (≥2 bestätigte oder ≥2 unbestätigte) → **kein Login**, neutrale Fehlermeldung, Log-Eintrag ohne Adresse. Bestandsduplikate sperren niemanden aus: Passwort-/Passkey-Login laufen kontobezogen, ohne Adresssuche.
4. **Magic-Link-Anfordern legt kein Konto mehr an** (behebt das Belegen fremder Adressen durch bloßes Anfordern). Kontoanlage erst beim erfolgreichen Einlösen, wenn kein Konto die Adresse trägt.
5. **Gemeinsamer Lock** im Store-Paket (nicht pro Handler), damit Scheiben B/C denselben Lock benutzen (TOCTOU, Muster `telegramConnectMu`).
6. **Enumeration:** Magic-Link bleibt neutral (immer 200). Die 409-Frage bei Registrierung gehört zu Scheibe B; Entscheid dort: 409 mit verständlicher Meldung (Usernames sind schon heute abfragbar, neutrale Antwort brächte keinen Sicherheitsgewinn, aber Support-Last).
7. **Bekannte Restlücke, nicht in A:** Klick auf eine Bestätigungsmail, die ein Fremder durch Eintragen der Opfer-Adresse ausgelöst hat, bestätigt dessen Konto (Social Engineering). Mail-Text-Härtung → Scheibe B.

### Affected Files (Scheibe A)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/user.go` | MODIFY | `FindUserByEmail` → Auflösung über beide Felder, Testnutzer-Filter, Mehrdeutigkeit als Fehler; Adress-Lock + Normalisierungshelfer |
| `internal/handler/auth_magic.go` | MODIFY | Request ohne Kontoanlage; Verify löst unter Lock auf, legt ggf. an, entfernt Fremdzugänge bei unbestätigtem Konto |
| `internal/handler/auth.go` | MODIFY (klein) | ggf. `selfHealEmailVerification` wiederverwenden/anpassen |
| `internal/store/user_magic_test.go`, `internal/handler/auth_magic_test.go` | MODIFY | bestehende Tests `CreatesNewUserForUnknownEmail` ändern Semantik (Anlage erst bei Verify) |
| neuer Test `internal/handler/magic_link_address_ownership_test.go` | CREATE | Zwei-Nutzer-Tests |
| `docs/specs/modules/magic_link_adress_eindeutigkeit.md` | CREATE | Spec |
| `docs/reference/api_contract.md` | MODIFY | Magic-Link-Semantik |

### Scope Assessment

- Files: ~5 Prod/Test + Doku
- Estimated LoC: ~+120/-30 Prod, ~180 Test
- Risk Level: HIGH (Auth-Kernpfad)

### Dependencies

`store.ClearSessions` (sessions.go:199), `IsTestUserID`, `issueSession`, `selfHealEmailVerification`, Login-Gate #2271 (ADR-0066).

### Open Questions

- [ ] Bestandsduplikate auf Prod/Staging zählen (Sitzung kann `/var/lib/gregor` nicht lesen) — Spec ist duplikat-tolerant, Messung nur bestätigend; ggf. über Instanz `security` (ACL `r-x`).
