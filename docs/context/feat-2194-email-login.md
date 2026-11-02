# Context: feat-2194-email-login

## Request Summary
Issue #2194 (Epic #2138, PO-beauftragt 2026-09-08): Die E-Mail-Adresse soll der eindeutige Login-Identifier
werden, statt eines separat gewählten Benutzernamens. Zustell-Adresse (`mail_to`) bleibt konzeptionell getrennt.

## Kernbefunde (Ist-Stand)
- Es gibt **kein eigenes Username-Feld**: der Benutzername IST `User.ID` und damit Verzeichnisname
  `data/users/<id>/` (`internal/store/user.go:50`).
- ID-Muster `^[a-zA-Z0-9_-]+$` (`internal/store/pathsafe.go:20`, Python-Parität `src/app/loader.py:1294`,
  `tests/unit/test_user_id_pattern_parity.py`) — `@` und `.` verboten. E-Mail kann heute weder ID noch Ordnername sein.
- ID-Entstehung: Passwort-Register = frei gewählter Username (`auth.go:88-95,157`); öffentliche Passkey-Registrierung
  = frei gewählt (`passkey.go:458,570`, vom Frontend nicht genutzt); Magic-Link = `m-<8hex>` (`auth_magic.go:276-303`);
  Google = `g-<8hex>` (`auth_oauth.go:383-412`). Alle vier setzen `Email = MailTo = normalisierte Adresse`.
- **Opake IDs existieren also bereits** (Magic-Link, Google) — Muster für „ID nicht aus Nutzereingabe".
- Login-Formular akzeptiert **nur die ID** (`auth.go:309-357`, `ValidUserID` → `LoadUser`); E-Mail ergibt 401.
  Ebenso ID-basiert: Passwort vergessen `{username}` (`auth.go:454-570`), Reset `{username,token,new_password}`
  + Link `?user=<id>` (`internal/mail/reset.go:15`), Verify-Link `?user=<id>` (`internal/mail/verify.go:14`),
  Resend `{username}` (`auth.go:1504-1550`), Passkey-Login mit Kennung `{username}` (`passkey.go:164-198`).
- Adress-Lookup: nur `ResolveAddressOwner` / `IsAddressTakenByOtherAccount` (`internal/store/address_owner.go:78,118`),
  linear über alle Nicht-Testkonten, vergleicht `email` ODER `mail_to`. Normalisierung `NormalizeEmailAddress`
  = TrimSpace+ToLower (`:19-23`), Sperre `LockEmailAddress`. **Testkonten sind von der Eindeutigkeit ausgenommen**.
  Bestandsduplikate nur gezählt (`address_collisions.go`). ADR-0067.
- Session-Cookie `{userId}.{sessionId}.{ts}.{sig}` (`internal/middleware/auth.go:133-137`) — ID-basiert, bleibt unberührt
  wenn ID stabil bleibt.
- WebAuthn: UserHandle/Name/DisplayName = `u.ID` (`internal/model/user.go:155-161`) — Bestands-Passkeys hängen an der ID.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go` | Register/Login/Forgot/Reset/Verify/Resend — alle `username`-basiert |
| `internal/handler/auth_magic.go`, `auth_oauth.go` | Muster opaker ID (`m-`/`g-`), Adressauflösung |
| `internal/handler/passkey.go` | Passkey-Login mit Kennung, öffentliche Registrierung |
| `internal/store/address_owner.go`, `pathsafe.go`, `user.go` | Adress-Lookup, ID-Muster, Verzeichnis |
| `internal/model/user.go`, `test_user.go` | Modell, WebAuthn-Handle, Testkonto-Erkennung |
| `internal/mail/reset.go`, `verify.go` | Links mit `?user=<id>` |
| `internal/handler/staging_verify_token.go`, `admin_users.go` | `{username}`-Body, Admin-Liste `id`+`email` |
| `frontend/src/routes/{login,register,forgot-password,reset-password,account}/` | Username-Felder/Labels |
| `frontend/src/lib/passkey.ts`, `lib/i18n/messages/{de,en}/auth.json` | Passkey-Login mit Kennung, Texte |
| `scripts/setup-validator-user.sh`, `frontend/e2e/global.setup.ts`, `frontend/e2e/helpers.ts`, `tests/helpers/staging_auth.py` | Test-/Validator-Konten registrieren/loggen per `username`, Validator teils **ohne E-Mail** |
| `docs/reference/api_contract.md` §19 (:3155ff), :3973-4050 | Vertrag der Auth-Endpunkte |

## Existing Patterns
- Opake ID bei Neuanlage (Magic-Link `m-<hex>`, Google `g-<hex>`).
- Adressauflösung zentral über `ResolveAddressOwner` unter `LockEmailAddress` (#2147, #2311).
- Reihenfolge-Regel #1517 hält das Validator-Skript lauffähig (`auth.go:100-105`).

## Dependencies
- Upstream: Store (Verzeichnis = ID), Adress-Index, Mail-Links, Session-Cookie, WebAuthn-Handle.
- Downstream: Frontend-Auth-Routen, E2E-Setup/-Helpers, Validator-Skripte, Admin-Liste (`GZ_ADMIN_USER_IDS` = ID-Liste,
  ADR-0078), Einladungen (`invites.Redeem(req.Invite, req.Username)`, `auth.go:175`), Testkonto-Fixture `tg-live-e2e`.

## Existing Specs / ADRs
- Specs: `user_auth_endpoints.md`, `register_page.md`, `sveltekit_login_refactor.md`, `magic_link_adress_eindeutigkeit.md`,
  `adress_eindeutigkeit_schreibpfade.md`, `passkey_webauthn.md`, `google_login_adress_verknuepfung.md`,
  `email_verify_scharfschaltung_2271.md`, `testkonto_profilfeld.md`, `fix_1517_validator_register_order.md`,
  `i18n_f1_auth_routen_2650.md`, `account_page.md`.
- ADRs: 0003, 0031 (Persistenz `data/users/{user_id}/`), 0060 (Sessions), 0066 (Login nur mit bestätigter E-Mail),
  0067 (Adress-Eindeutigkeit), 0072 (Testkonto), 0078 (Admin-ID-Liste), 0084 (Einladungen).

## Risks & Considerations
- **Kernentscheidung:** E-Mail als Ordnername (PII in Pfaden/Logs/Backups, Migration, Adresswechsel = Ordner-Umzug)
  vs. **opake, stabile ID** + Login-Lookup per E-Mail. Letzteres folgt dem bestehenden `m-`/`g-`-Muster, braucht
  keine Datenmigration der Ordner und lässt Sessions/Passkeys/Admin-IDs unberührt.
- Bestandskonten mit selbst gewähltem Username: Login mit altem Namen weiter erlauben (Übergang) oder nur E-Mail?
- Bestandskonten **ohne E-Mail** möglich (`omitempty`, Pflicht erst seit #1226; Validator-Skript ohne E-Mail).
- Testkonten sind von der Adress-Eindeutigkeit ausgenommen → Login per E-Mail ist für Testkonten nicht eindeutig.
- Login per E-Mail ist ein Lookup über `email` ODER `mail_to`? (abweichende Kontaktadresse, #2311) — klären.
- Konto-Enumeration/Timing bei Login/Forgot per E-Mail (#2163-Härtung nicht zurückdrehen).
- Prod-Bestand nicht einsehbar aus dem Worktree (`/var/lib/gregor/users` → `sudo -n -u claude-gregor`).
- Viele Test-/E2E-/Skript-Stellen (36 Dateien mit `"username"`) — Staging-E2E und Validator dürfen nicht brechen.
- Daten-Schema-Regel (Read-Modify-Write, kein Replace) bei jeder Bestandsmigration.

## Analysis

### Type
Feature (Epic #2138, Multi-User-Readiness)

### Tech-Lead-Entscheidungen (keine PO-Fragen)
- **Variante V2:** Ordnername bleibt eine **stabile opake ID**; Login sucht das Konto über die E-Mail-Adresse.
  Begründung: E-Mail als Ordnername verstößt gegen das ID-Muster (Go/Python-Parität), legt PII in Pfade/Logs/Backups,
  macht jeden Adresswechsel zum Ordner-Umzug und bricht Session-Cookie, WebAuthn-UserHandle, `GZ_ADMIN_USER_IDS`, Einladungen.
- **Lookup-Schlüssel nur `email`, nicht `mail_to`.** `ResolveAddressOwner` ist für Login **ungeeignet** (matcht `mail_to`,
  liefert Magic-Link-Übernahme-Semantik). Neu: `Store.FindUsersByLoginEmail(addr)`: nur `u.Email` (NormalizeEmailAddress),
  ohne Testkonten (`model.IsTestAccount`), alle Treffer, fail-closed bei unlesbarer `user.json`.
- **Weiche am `@`:** Eingabe mit `@` → E-Mail-Lookup; ohne `@` → bisheriger ID-Pfad unverändert (`@` ist in IDs verboten,
  Weiche eindeutig). Gilt für Login, Passwort vergessen, Verify-Resend, Passkey-Login mit Kennung, `staging_verify_token`.
- **ID-Pfad bleibt dauerhaft** (kein Folgeticket „Fallback entfernen"): nötig für Testkonten, Fixture `tg-live-e2e`,
  Validator und Bestandskonten ohne `email`. Die UI fragt nur noch die E-Mail ab.
- **Mehrfachtreffer** auf dem E-Mail-Pfad (Bestandsduplikate echter Konten) = **wie kein Treffer**: `burnDummyCompare`,
  401 `invalid_credentials`, Log nur mit Anzahlen. Nicht gegen alle Passwörter prüfen (Timing verrät Anzahl, Reihenfolge entschiede).
  Ausweg bleibt der ID-Login. 0/1/n Treffer → identischer Aufwand (genau ein bcrypt-Lauf), identische Antwort.
- **Testkonten nur per ID** (nicht per E-Mail auffindbar) — beseitigt die Mehrdeutigkeit (Testkonten sind von ADR-0067 ausgenommen).
- **Neue Konten (Passwort-Register, öffentliche Passkey-Registrierung) bekommen `u-<8hex>`** über einen gemeinsamen
  Generator `store.NewOpaqueUserID(prefix)` (crypto/rand, Kollisionsprüfung, Retry). Umzug von `m-`/`g-` auf den Generator optional, wenn klein.
- **Registrier-Body `username` nur noch für Testkonten** (`is_test_user=true`) akzeptiert, sonst generiert.
  Hält `scripts/setup-validator-user.sh`, Fixture-Konten und E2E-Zweitnutzer mit festen IDs lauffähig (#1517-Reihenfolge prüfen).
  E2E-Helpers loggen Testkonten weiter **per ID** ein (keine Umstellung der Helpers auf E-Mail-Login für Testkonten).
- **Reset-/Verify-Links bleiben `?user=<id>`** (intern, keine PII in URL/Referer). Reset-Confirm-Body bleibt `{username,token,new_password}`.
- **Kopplung `email`/`mail_to` beim Adresswechsel:** nicht Teil dieses Tickets, bestehende Logik bleibt.
- **Rate-Limits:** alle Auth-Limiter sind IP-basiert (`internal/router/router.go:64-97`) → kein doppeltes Kontingent über ID+E-Mail.
- **Login-Antwort** `{"id": <aufgelöste ID>}` statt Echo der Eingabe.
- **ADR-0066** (Login nur mit bestätigter Mail) und der #2163-Timing-Schutz bleiben unverändert wirksam.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/login_lookup.go` (o. ä.) | CREATE | `FindUsersByLoginEmail`, `NewOpaqueUserID` |
| `internal/handler/auth.go` | MODIFY | Weiche in Login (:309-375), Forgot (:454-570), Resend (:1504-1550); Register ohne Namen (:88-218), Invite-Redeem mit generierter ID |
| `internal/handler/passkey.go` | MODIFY | Login-Begin mit Kennung (:164-198) Weiche; öffentliche Registrierung (:451-499) generierte ID |
| `internal/handler/staging_verify_token.go` | MODIFY | Weiche E-Mail/ID |
| `internal/handler/auth_magic.go`, `auth_oauth.go` | MODIFY (optional) | gemeinsamen Generator nutzen |
| Go-Tests (`auth_test.go`, passkey-, register_invite-Tests, neu `login_email_test.go`) | MODIFY/CREATE | Timing, 0/1/n Treffer, Testkonto nicht per E-Mail, Konto ohne email, zwei Nutzer |
| `frontend/src/routes/{login,register,forgot-password,reset-password,account}/` | MODIFY | Feld „E-Mail" (`autocomplete="email webauthn"`), Register ohne Benutzername, Account-Anzeige/Resend |
| `frontend/src/lib/passkey.ts` | MODIFY | Kennung = E-Mail |
| `frontend/src/lib/i18n/messages/{de,en}/auth.json` + Katalog-Tests, `__tests__/fixtures/auth/*.html` | MODIFY | Texte „Benutzername" → „E-Mail" |
| `frontend/e2e/global.setup.ts`, `helpers.ts`, `passkey-login.spec.ts`, `e2eTestUserResolution.test.ts` | MODIFY | Feldselektor; Testkonten weiter per ID |
| `scripts/setup-validator-user.sh`, `tests/helpers/staging_admin_session.py`, `.claude/hooks/e2e_frontend_browser_gate.py`, betroffene `tests/tdd/*.py` | MODIFY | Selektor-/Body-Kompatibilität |
| `docs/adr/00NN-email-als-login-identifier.md` + `docs/adr/README.md` | CREATE/MODIFY | Neue Auth-Entscheidung (Index-Drift-Test) |
| `docs/reference/api_contract.md` §19 (:3155ff, :3973-4050) | MODIFY | Vertrag Login/Forgot/Resend/Register/Passkey |
| `docs/specs/modules/email_login_identifier.md` | CREATE | Spec |

### Scope Assessment
- Files: ~40 (davon viele Ein-Zeilen-Anpassungen in Tests/Fixtures)
- Estimated LoC: Backend ~+400 Code / ~+500 Tests; Frontend+E2E+Skripte ~+300/-200
- Risk Level: **MEDIUM** — zentraler Auth-Pfad, aber additiv (ID-Pfad bleibt), keine Datenmigration
- **Schnitt:** EINE Spec, EINE Auslieferung (kein Issue abspalten). Implementierung in Schritten wegen LoC-Limit:
  S1 Backend-Lookup + Weiche · S2 Registrierung opake ID · S3a Frontend/i18n · S3b E2E/Skripte.
  Ein gemeinsamer Deploy ist unkritisch (E-Mail-Login und opake Registrierung kommen gleichzeitig).

### Technical Approach
V2: opake ID + E-Mail-Lookup nur über `email` + `@`-Weiche + dauerhafter ID-Pfad (Testkonten/Altkonten).

| Kriterium | V1 E-Mail als Ordner | **V2 opake ID + Lookup + ID-Pfad** | V3 opake ID, nur E-Mail |
|---|---|---|---|
| Migration | Ordner-Umzug aller Konten | keine | Konten ohne email ausgesperrt |
| PII in Pfaden/Logs | ja | nein | nein |
| Sessions/Passkeys/Admin-IDs | brechen | unberührt | unberührt |
| Validator/E2E-Konten | brechen | laufen | brechen |
| Aufwand/Risiko | hoch/hoch | mittel/niedrig | mittel/hoch |

### Dependencies
Store (Verzeichnis = ID), `NormalizeEmailAddress`, `model.IsTestAccount`, `burnDummyCompare` (#2163), Verify-Gate (ADR-0066),
Invites (ADR-0084), Admin-ID-Liste (ADR-0078, unberührt), E2E-Helpers/Validator-Skript (#1517).

### Open Questions (Messschritte für die Spec, keine PO-Fragen)
- [ ] Prod-Bestand: Anzahl Konten ohne `email` und Anzahl echter E-Mail-Duplikate (nur Zahlen, keine PII). Aus dem Worktree blockt
      der Wächter `sudo -u claude-gregor`; Weg: Startup-Log `address collisions: N address(es)…` (`internal/store/address_collisions.go:60`)
      im Journal von `gregor-api` lesen, oder `infra` per MQ um reine Anzahlen bitten.
- [ ] Prüfen, ob `is_test_user` bei der Registrierung heute ohne Admin-Recht setzbar ist. Falls ja, ist „`username` nur für Testkonten"
      kein neuer Angriffsweg; sonst die Absicherung in der Spec festlegen.
