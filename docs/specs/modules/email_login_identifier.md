---
entity_id: email_login_identifier
type: feature
created: 2026-11-02
updated: 2026-11-02
status: approved
version: "1.0"
workflow: feat-2194-email-login
tags: [auth, login, email, epic-2138]
---

# E-Mail-Adresse als Login-Identifier (#2194)

## Approval

- [x] Approved (2026-11-02, Freigabe im Workflow-State)

## Purpose

Nutzer melden sich mit ihrer E-Mail-Adresse an, statt sich einen separaten Benutzernamen zu merken. Intern bleibt das Konto an eine stabile, undurchsichtige Kennung (`u-<8hex>`) gebunden, damit Ordnernamen, Sitzungen, Passkeys und Admin-Liste unberührt bleiben und keine personenbezogene Adresse in Pfaden oder Logs steht (Epic #2138, Multi-User-Readiness).

## Source

- **File:** `internal/handler/auth.go` (Login, Passwort vergessen, Verify-Resend, Registrierung), `internal/handler/passkey.go`, `internal/store/login_lookup.go` (neu)
- **Identifier:** `Store.FindUsersByLoginEmail`, `store.NewOpaqueUserID`, `AuthHandler.Login`

> **Schicht-Hinweis:** Backend-Logik liegt in der **Go-API** (`internal/`), die Oberfläche im **Frontend** (`frontend/src/...`). Der Python-Core wird nicht verändert (das ID-Muster `^[a-zA-Z0-9_-]+$` bleibt in Go und Python identisch; `u-<8hex>` passt hinein).
> **Trip/Ortsvergleich-Teilung:** nicht betroffen (reine Auth-Änderung, kein Trip-/Compare-Pendant).
> **Mandantentrennung:** Es werden Nutzerdaten aufgelöst; Tests laufen mit zwei verschiedenen Nutzern (AC-15). `user_id` kommt weiter aus dem Auth-Kontext bzw. der aufgelösten ID, nie `"default"`.
> **Kanäle:** Briefing-/Alarm-Inhalt ist nicht betroffen.

## Estimated Scope

- **LoC:** Backend ca. +400 Code / +500 Tests; Frontend, E2E, Skripte ca. +300/-200
- **Files:** ca. 40 (viele Ein-Zeilen-Anpassungen in Tests und Fixtures)
- **Effort:** medium bis high; Risiko MEDIUM (zentraler Auth-Pfad, aber additiv, keine Datenmigration)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/login_lookup.go` | CREATE | `FindUsersByLoginEmail`, `NewOpaqueUserID` |
| `internal/handler/auth.go` | MODIFY | `@`-Weiche in Login, Passwort vergessen, Verify-Resend; Registrierung ohne frei gewählten Namen; Einladungs-Redeem mit generierter ID |
| `internal/handler/passkey.go` | MODIFY | Passkey-Login mit Kennung: `@`-Weiche; öffentliche Registrierung mit generierter ID |
| `internal/handler/staging_verify_token.go` | MODIFY | `@`-Weiche E-Mail/ID |
| `internal/handler/auth_magic.go`, `internal/handler/auth_oauth.go` | MODIFY (optional) | gemeinsamen Generator nutzen, nur wenn klein |
| `internal/handler/login_email_test.go` | CREATE | Go-Tests Login per E-Mail (Timing, 0/1/n Treffer, Testkonto, Konto ohne email, zwei Nutzer) |
| `internal/store/login_lookup_test.go` | CREATE | Go-Tests Lookup und ID-Generator |
| `internal/handler/auth_test.go`, Passkey- und Invite-Tests | MODIFY | Anpassung an generierte IDs |
| `frontend/src/routes/{login,register,forgot-password,reset-password,account}/` | MODIFY | Feld „E-Mail" (`autocomplete="email webauthn"`), Registrierung ohne Benutzername |
| `frontend/src/lib/passkey.ts` | MODIFY | Kennung = E-Mail |
| `frontend/src/lib/i18n/messages/{de,en}/auth.json`, Katalog-Tests, `__tests__/fixtures/auth/*.html` | MODIFY | Texte „Benutzername" wird „E-Mail" |
| `frontend/e2e/global.setup.ts`, `helpers.ts`, `passkey-login.spec.ts`, `e2eTestUserResolution.test.ts` | MODIFY | Feldselektor; Testkonten weiter per ID |
| `scripts/setup-validator-user.sh`, `tests/helpers/staging_admin_session.py`, `.claude/hooks/e2e_frontend_browser_gate.py`, betroffene `tests/tdd/*.py` | MODIFY | Selektor-/Body-Kompatibilität |
| `docs/adr/0105-email-als-login-identifier.md`, `docs/adr/README.md` | CREATE/MODIFY | Neue Auth-Entscheidung, Index-Drift-Test |
| `docs/reference/api_contract.md` (§19) | MODIFY | Vertrag Login/Forgot/Resend/Register/Passkey |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Store` (Verzeichnis = ID) | module | Konto laden, Kollisionsprüfung der neuen ID |
| `NormalizeEmailAddress` | function | Trim + Kleinschreibung der Adresse vor dem Vergleich |
| `model.IsTestAccount` | function | Testkonten vom E-Mail-Lookup ausschließen |
| `burnDummyCompare` (#2163) | function | gleicher bcrypt-Aufwand bei jedem Ausgang |
| Verify-Gate (ADR-0066) | rule | Login nur mit bestätigter E-Mail |
| Adress-Eindeutigkeit (ADR-0067) | rule | Quelle der Eindeutigkeit echter Konten |
| Einladungen (ADR-0084) | module | `invites.Redeem` mit generierter ID |
| Admin-ID-Liste (ADR-0078) | rule | bleibt unberührt (IDs stabil) |
| E2E-Helpers / Validator-Skript (#1517) | tooling | müssen lauffähig bleiben |

## Implementation Details

### Entscheidungen (Tech Lead, verbindlich)

- **Opake stabile ID plus E-Mail-Lookup (V2):** Ordnername bleibt die ID; Login sucht das Konto über die E-Mail. E-Mail als Ordnername wurde verworfen (Verstoß gegen das ID-Muster, personenbezogene Daten in Pfaden/Logs/Backups, Adresswechsel wäre ein Ordner-Umzug, bricht Session-Cookie, WebAuthn-UserHandle, Admin-Liste, Einladungen). Keine Datenmigration.
- **Lookup-Schlüssel nur `email`, nicht `mail_to`.** `ResolveAddressOwner` ist für Login ungeeignet (matcht `mail_to`, Magic-Link-Übernahme-Semantik). Neu: `Store.FindUsersByLoginEmail(addr)` vergleicht nur `u.Email` (normalisiert), schließt Testkonten aus, liefert alle Treffer, ist fail-closed bei unlesbarer `user.json`.
- **Weiche am `@`:** Eingabe mit `@` führt zum E-Mail-Lookup, ohne `@` bleibt der bisherige ID-Pfad unverändert (`@` ist in IDs verboten, die Weiche ist eindeutig). Gilt für Login, Passwort vergessen, Verify-Resend, Passkey-Login mit Kennung und `staging_verify_token`.
- **ID-Pfad bleibt dauerhaft** (Testkonten, Fixture `tg-live-e2e`, Validator-Konto, Bestandskonten ohne `email`). Die Oberfläche fragt nur noch die E-Mail ab.
- **Mehrfachtreffer = wie kein Treffer:** `burnDummyCompare`, 401 `invalid_credentials`, Log nur mit Anzahlen. Nicht gegen alle Passwörter prüfen (Timing würde die Anzahl verraten, die Reihenfolge würde entscheiden). Bei 0, 1 und n Treffern läuft genau ein bcrypt-Vergleich, die Antwort ist identisch. Ausweg für Betroffene bleibt der ID-Login.
- **Neue Konten** (Passwort-Registrierung, öffentliche Passkey-Registrierung) erhalten `u-<8hex>` über `store.NewOpaqueUserID(prefix)` (crypto/rand, Kollisionsprüfung, Retry). Der Registrier-Body-`username` wird nur für Testkonten (`is_test_user=true`) akzeptiert.
- **Reset-/Verify-Links bleiben `?user=<id>`** (intern, keine E-Mail-Adresse in URL/Referer). Reset-Confirm-Body bleibt `{username,token,new_password}`.
- **Login-Antwort** `{"id": <aufgelöste ID>}` statt Echo der Eingabe.
- **Rate-Limits:** alle Auth-Limiter sind IP-basiert (`internal/router/router.go`), daher kein doppeltes Kontingent über ID und E-Mail.
- **Nicht Teil dieses Tickets:** Kopplung `email`/`mail_to` beim Adresswechsel (bestehende Logik bleibt), neue Härtung von `is_test_user`.

### Messergebnisse (Spec-Vorbereitung)

1. **Prod-Bestand:** Das Startup-Log von `gregor-api` (2026-11-01) meldet `address collisions: 0 address(es) held by more than one account`. Aktuell gibt es keine echten E-Mail-Duplikate; die Mehrfachtreffer-Regel bleibt als Schutz trotzdem.
2. **`is_test_user` bei `POST /api/auth/register`** ist heute ohne Admin-Recht setzbar (`internal/handler/auth.go`, ca. Zeilen 65 und 162). Daher ist „Body-`username` nur bei `is_test_user=true`" kein neuer Angriffsweg. Bekannter Ist-Zustand; eine Absicherung ist ausdrücklich nicht Teil dieses Tickets.

### Implementierungsschritte (eine Spec, eine Auslieferung)

- **S1 Backend-Lookup und Weiche:** `login_lookup.go` mit `FindUsersByLoginEmail`; `@`-Weiche in Login, Passwort vergessen, Verify-Resend, Passkey-Login-Begin, `staging_verify_token`. Tests: `internal/store/login_lookup_test.go`, `internal/handler/login_email_test.go` (echte Handler gegen temporäres Datenverzeichnis, kein Mock-Theater).
- **S2 Registrierung mit opaker ID:** `NewOpaqueUserID`; Passwort-Register, öffentliche Passkey-Registrierung, Einladungs-Redeem mit generierter ID; Body-`username` nur für Testkonten (Reihenfolge-Regel #1517 prüfen). Tests: Erweiterung von `auth_test.go`, Passkey- und Invite-Tests, `internal/store/login_lookup_test.go` (Generator: Format, Kollision/Retry).
- **S3a Frontend und i18n:** Felder und Texte „E-Mail" (de/en), `autocomplete="email webauthn"`, Registrierung ohne Benutzername, `passkey.ts`. Tests per `node --test` (Katalog-Tests, Fixture-Tests `frontend/src/lib/i18n/...`, Auth-Routen-Fixtures).
- **S3b E2E und Skripte:** `global.setup.ts`, `helpers.ts`, `passkey-login.spec.ts`, `e2eTestUserResolution.test.ts` (node --test), `setup-validator-user.sh`, `staging_admin_session.py`, Browser-Gate-Hook; Testkonten loggen weiter per ID ein.

Dazu kommen ADR-0105 (neue Auth-Entscheidung, Verweis auf ADR-0066/0067/0072/0078/0084) mit Eintrag in `docs/adr/README.md` und die Aktualisierung von `docs/reference/api_contract.md` §19.

## Expected Behavior

- **Input:** Login-/Passwort-vergessen-/Resend-/Passkey-Kennung mit `@` (E-Mail) oder ohne `@` (Konto-ID); Registrierung mit E-Mail und Passwort.
- **Output:** Erfolgreicher Login liefert `{"id": <aufgelöste ID>}` und setzt das Session-Cookie der aufgelösten ID. Fehlschläge liefern 401 `invalid_credentials` ohne Hinweis, ob eine Adresse existiert.
- **Side effects:** Neue Konten erhalten das Verzeichnis `data/users/u-<8hex>/`. Bestandskonten, Ordner, Sessions und Passkeys bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Konto mit bestätigter E-Mail-Adresse und Passwort / When der Nutzer sich mit dieser E-Mail-Adresse (auch in anderer Groß-/Kleinschreibung oder mit Leerzeichen am Rand) und dem richtigen Passwort anmeldet / Then ist er angemeldet und die Antwort enthält `{"id": <ID seines Kontos>}`, nicht die eingegebene Adresse.
  - Test: Go-Handlertest `login_email_test.go` legt Konto an, loggt per E-Mail ein und prüft Status 200, Cookie und Antwort-`id`.

- **AC-2:** Given ein bestehendes Konto mit ID, z.B. `alice` / When der Nutzer sich mit der ID (ohne `@`) und dem richtigen Passwort anmeldet / Then funktioniert der Login unverändert wie bisher, auch für Konten ohne hinterlegte E-Mail-Adresse.
  - Test: Go-Handlertest mit zwei Konten (eines mit, eines ohne `email`), Login jeweils per ID erfolgreich.

- **AC-3:** Given eine E-Mail-Adresse, die bei keinem, genau einem oder mehreren echten Konten als `email` steht / When jemand sich mit dieser Adresse und einem falschen oder (bei mehreren Treffern) auch dem richtigen Passwort anmeldet / Then lautet die Antwort in allen Fällen 401 `invalid_credentials` mit identischem Antwortkörper, und es läuft in jedem Fall genau ein bcrypt-Vergleich (bei 0 und n Treffern der Dummy-Vergleich).
  - Test: Go-Test zählt bcrypt-Läufe über die vorhandene Zählstelle des #2163-Timing-Schutzes für 0, 1 und 2 Treffer und vergleicht Status und Body.

- **AC-4:** Given ein Konto, das als Testkonto markiert ist und eine E-Mail-Adresse trägt / When sich jemand mit dieser Adresse und dem richtigen Passwort anmeldet / Then wird 401 `invalid_credentials` geliefert; mit der Konto-ID und demselben Passwort gelingt der Login.
  - Test: Go-Handlertest mit Testkonto, Login per E-Mail scheitert, Login per ID gelingt.

- **AC-5:** Given ein Konto, bei dem die Adresse nur als abweichende Zustelladresse `mail_to` steht, nicht als `email` / When sich jemand mit dieser Adresse anmeldet / Then wird das Konto nicht gefunden (401 `invalid_credentials`), weil der Login-Lookup ausschließlich `email` vergleicht.
  - Test: Go-Test mit Konto `email=a@x.de`, `mail_to=b@x.de`; Login mit `b@x.de` scheitert, mit `a@x.de` gelingt.

- **AC-6:** Given Konten mit und ohne bestätigte E-Mail-Adresse / When sich ein Nutzer mit unbestätigter E-Mail per E-Mail-Adresse anmeldet / Then bleibt der Login nach ADR-0066 gesperrt wie beim ID-Login, und es wird kein früherer Erfolg durch den neuen Pfad ermöglicht.
  - Test: Go-Test mit unbestätigtem Konto, Login per E-Mail und per ID liefern denselben Sperr-Status.

- **AC-7:** Given ein Nutzer, der „Passwort vergessen" mit einer E-Mail-Adresse auslöst / When die Adresse zu einem Konto gehört, zu keinem oder zu mehreren / Then ist die Antwort immer dieselbe neutrale Bestätigung (gleicher Status und Body, kein Hinweis auf Existenz), und nur im Fall genau eines Treffers geht die Reset-Mail mit dem Link `?user=<ID>` an dieses Konto.
  - Test: Go-Test ruft den Endpunkt mit bekannter, unbekannter und doppelter Adresse auf, vergleicht Antworten und prüft den Mail-Versand im Test-Transport.

- **AC-8:** Given ein Konto mit noch unbestätigter E-Mail-Adresse / When der Nutzer „Bestätigungsmail erneut senden" mit seiner E-Mail-Adresse auslöst / Then erhält er dieselbe neutrale Antwort wie bei einer unbekannten Adresse, und die Bestätigungsmail mit Link `?user=<ID>` geht nur an das eindeutig gefundene Konto.
  - Test: Go-Test für Resend mit bekannter, unbekannter und mehrfach vergebener Adresse.

- **AC-9:** Given ein Konto mit registriertem Passkey / When der Nutzer den Passkey-Login mit Kennung startet und dort seine E-Mail-Adresse eingibt / Then wird die Anmeldung für das richtige Konto eröffnet; bei unbekannter, mehrfach vergebener oder Testkonto-Adresse kommt dieselbe Antwort wie bei einer unbekannten Kennung, ohne Hinweis auf Existenz.
  - Test: Go-Test `passkey`-Login-Begin mit E-Mail (bekannt, unbekannt, doppelt, Testkonto) und Vergleich der Antworten.

- **AC-10:** Given ein neuer Nutzer ohne Konto / When er sich mit E-Mail-Adresse und Passwort registriert (ohne `is_test_user`) / Then erhält sein Konto eine automatisch erzeugte ID im Format `u-<8 Hex-Zeichen>`, ein im Body mitgesendeter `username` wird ignoriert, und der Ordner `data/users/u-<8hex>/` existiert.
  - Test: Go-Handlertest Register mit und ohne `username` im Body, Prüfung des ID-Formats und des Ordners.

- **AC-11:** Given eine Registrierung mit `is_test_user=true` und gewünschtem `username` / When die Anfrage gesendet wird / Then wird das Testkonto mit genau dieser ID angelegt, sodass Validator-Skript, Fixture-Konten und E2E-Zweitnutzer mit festen IDs weiter funktionieren (bekannter Ist-Zustand: `is_test_user` ist heute ohne Admin-Recht setzbar, eine Absicherung ist nicht Teil dieses Tickets).
  - Test: Go-Handlertest Register als Testkonto mit fester ID, anschließender ID-Login; Ablauf entspricht der Reihenfolge von `setup-validator-user.sh` (#1517).

- **AC-12:** Given eine gültige Einladung (ADR-0084) / When ein neuer Nutzer sie bei der Registrierung einlöst / Then wird die Einladung mit der generierten `u-<8hex>`-ID als Einlöser verbunden und nicht mit einem Nutzernamen aus dem Formular.
  - Test: Go-Test Register mit Einladungscode, Prüfung des gespeicherten Einlösers gegen die erzeugte ID.

- **AC-13:** Given eine öffentliche Passkey-Registrierung / When ein neuer Nutzer sie abschließt / Then erhält das Konto ebenfalls eine generierte `u-<8hex>`-ID, und zwei Registrierungen liefern verschiedene IDs (Kollisionen werden wiederholt, nie überschrieben).
  - Test: Go-Test Passkey-Registrierung zweimal; IDs unterschiedlich und im erwarteten Format; Generator-Test mit vorbelegter Kollision.

- **AC-14:** Given die Login-, Registrier- und Passwort-vergessen-Seiten in Deutsch und Englisch / When ein Nutzer sie öffnet / Then fragen die Seiten nach „E-Mail" bzw. „Email" statt nach „Benutzername", das Registrierformular hat kein Benutzername-Feld mehr, und das Login-Feld trägt `autocomplete="email webauthn"`.
  - Test: `node --test` der i18n-Katalog- und Auth-Fixture-Tests prüft die gerenderten Beschriftungen und Attribute in de und en; kein Dateiinhalt-Check als Verhaltensnachweis.

- **AC-15:** Given zwei verschiedene Nutzer A und B mit je eigenen Daten / When A sich per E-Mail und B sich per ID anmeldet und beide ihre Konto-Daten abrufen / Then sieht jeder ausschließlich die eigenen Daten, und die Session von A kann die Daten von B nicht lesen; eine fremde E-Mail-Adresse löst nie das Konto des anderen auf.
  - Test: Go-Zwei-Nutzer-Test in `login_email_test.go` über den echten Router mit zwei Sessions.

- **AC-16:** Given die bestehenden E2E-Setups, das Validator-Skript und die Staging-Hilfsfunktionen / When sie nach der Änderung laufen / Then können Testkonten weiter per ID registriert und eingeloggt werden (Validator-Konto auch ohne E-Mail), und die E2E-Selektoren treffen das neue E-Mail-Feld.
  - Test: `node --test` für `e2eTestUserResolution.test.ts`, Ausführung von `setup-validator-user.sh` gegen Staging in `/e2e-verify`, Staging-Login-Hilfen in `tests/helpers/`.

- **AC-17:** Given das Repository nach der Umsetzung / When ein Entwickler die Architekturdokumente liest / Then ist die Entscheidung in ADR-0105 festgehalten und im ADR-Index eingetragen, und `docs/reference/api_contract.md` §19 beschreibt Login, Passwort vergessen, Resend, Registrierung und Passkey-Kennung mit E-Mail, `@`-Weiche und Antwort `{"id": ...}`.
  - Test: bestehender `tests/test_adr_index_drift.py` bleibt grün; doc-compliance-Test für die Vertrags-Abschnitte (`# doc-compliance-test`).

## Known Limitations

- Bestandsdaten haben aktuell keine doppelten echten Adressen (Messung 2026-11-01). Entstehen künftig Duplikate, gelingt der E-Mail-Login für diese Adresse nicht; der ID-Login bleibt der Ausweg.
- Bestandskonten behalten ihre selbst gewählten IDs (kein Umbenennen, keine Migration); sie können sich per E-Mail oder per ID anmelden.
- Konten ohne `email` und Testkonten sind nur per ID erreichbar.
- `is_test_user` bei der Registrierung ist ohne Admin-Recht setzbar (Ist-Zustand, nicht Teil dieses Tickets).
- Die Kopplung von `email` und `mail_to` beim Adresswechsel bleibt unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0105 (neu, `docs/adr/0105-email-als-login-identifier.md`)
- **Rationale:** Auth-Entscheidungsfläche (Identität, Datenmodell). Opake stabile ID mit E-Mail-Lookup statt E-Mail als Ordnername; verwandt mit ADR-0031, 0060, 0066, 0067, 0072, 0078, 0084.

## Changelog

- 2026-11-02: Initial spec created (Issue #2194, Epic #2138)
