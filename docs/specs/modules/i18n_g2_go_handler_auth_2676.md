---
entity_id: i18n_g2_go_handler_auth_2676
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2676, go, frontend, model-haiku]
---

# i18n G2: Go-Handler Auth und Konto auf WriteError mit Katalog umstellen

**Issue:** #2676 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 5

## Approval

- [ ] Approved

## Purpose

Wer sich anmeldet, registriert, sein Passwort ändert, einen Passkey verwaltet oder als Admin Konten und Einladungen bearbeitet, bekommt Fehler künftig als `{"code","message"}` in seiner Sprache (Deutsch oder Englisch) statt als nacktes Code-Wort. Die Handler schreiben ihre Fehler nicht mehr selbst, sondern über `WriteError` aus G1; die Texte stehen in den Katalogen `auth` und `konto`. Statuscodes, Abläufe und Logzeilen bleiben unverändert.

## Source

- **File:** `internal/handler/auth.go`, `auth_magic.go`, `auth_oauth.go`, `passkey.go`, `admin_users.go`, `admin_invites.go`, `account_delete_code.go`, `sms_verify.go`
- **Identifier:** `RegisterHandlerWithInvites`, `LoginHandler`, `issueSession`, `ForgotPasswordHandler`, `ResetPasswordHandler`, `VerifyEmailHandler`, `UpdateProfileHandler`, `ChangePasswordHandler`, `RequestTierChangeHandler`, `MagicLinkRequestHandler`, `MagicLinkVerifyHandler`, `writeJSONError` (entfällt), `adminError` (entfällt)

> **Schicht-Hinweis:** Go-API (`internal/handler`), plus drei Frontend-Stellen, die heute auf die alten Fehlerwörter mit Leerzeichen prüfen. Kein Python-Code.
>
> **Dateinamen:** Die Muster der Issue-Beschreibung (`passkey*.go`, `magic_link*.go`, `tier*.go`) treffen im Repo auf `passkey.go` und `auth_magic.go`; Tier-Handler (`RequestTierChangeHandler`, `AdminSetUserTierHandler`) stehen in `auth.go` und `admin_users.go`. Die „Flood-Limiter-Meldungen" sind Antworten `rate_limit_exceeded` in `auth.go`, `account_delete_code.go` und `internal/middleware/ratelimit.go`; `profile_mail_ratelimit.go` selbst enthält keinen Text. Die Middleware-Antwort stellt G3 um.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen, kein Trip- oder Compare-Pendant. Geteilte Texte (`not_found`, `store_error`, `unauthorized`, `invalid_request`, `internal_error`, `rate_limit_exceeded`) liegen seit G1 in `fehler.*` und werden nicht dupliziert.
> - **Mandantentrennung:** Die Handler laden weiter über die `user_id` aus dem Auth-Kontext; die Sprache der Antwort kommt aus dem Kontext (G1), nie aus einer Nutzerkennung im Request-Body. Test mit zwei Nutzern (AC-4).
> - **Kanäle:** Das Paket schreibt nur HTTP-Fehlerantworten. Briefing- und Alarm-Inhalte (E-Mail, Telegram, SMS, Premium-SMS) sind nicht berührt; die Konto-Mails in `account_delete_code.go` und `auth_oauth.go` gehören zu G4.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `internal/handler/auth.go` | MODIFY | ca. 84 Fehlerstellen auf `WriteError`; Alt-Wörter auf Codes (Tabelle unten) |
| `internal/handler/auth_magic.go` | MODIFY | 13 Stellen |
| `internal/handler/auth_oauth.go` | MODIFY | 3 JSON-Fehlerstellen (`google_oauth_not_configured`, `internal_error`); die redirect-basierten Codes in `googleOAuthFail` bleiben Query-Parameter und unverändert; die Mail-Funktion `buildGoogleLinkNoticeMail` ist G4 |
| `internal/handler/passkey.go` | MODIFY | `writeJSONError` (48 Aufrufer) entfällt, Aufrufer rufen `WriteError(w, r, status, code, nil)` |
| `internal/handler/admin_users.go` | MODIFY | `adminError` (14 Aufrufer) entfällt, Aufrufer rufen `WriteError` |
| `internal/handler/admin_invites.go` | MODIFY | 10 Aufrufer von `adminError` |
| `internal/handler/account_delete_code.go` | MODIFY | 5 Fehlerstellen (Alt-Code `internal` wird `internal_error`); `buildDeleteCodeMail` ist G4 |
| `internal/handler/sms_verify.go` | MODIFY | 1 Fehlerstelle |
| `internal/i18n/messages/de/auth.json`, `internal/i18n/messages/en/auth.json` | MODIFY | 23 Schlüssel `auth.fehler.*` |
| `internal/i18n/messages/de/konto.json`, `internal/i18n/messages/en/konto.json` | MODIFY | 9 Schlüssel `konto.fehler.*` |
| `docs/reference/i18n_glossar.md` | MODIFY | eine Zeile `Level (Tarifstufe)` → `level` (als erster Commit, siehe Known Limitations) |
| `docs/reference/api_contract.md` | MODIFY | Fehlertabellen der Abschnitte 19 und Admin: Codes laut Tabelle unten |
| `frontend/src/routes/verify-email/+page.server.ts` | MODIFY | Zeile 48: `body.error === 'token expired'` → `body.code === 'token_expired'` |
| `frontend/src/routes/reset-password/+page.server.ts` | MODIFY | Zeile 37: gleicher Vergleich |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Zeile 322: `body?.error === 'wrong password'` → `body?.code === 'wrong_password'` |
| bestehende Go-Tests in `internal/handler/*_test.go` und `internal/router/*_test.go` | MODIFY | Tests, die die alten Wörter mit Leerzeichen erwarten, erwarten den neuen Code (Fundstellen per `grep -rn "invalid credentials\|invalid token\|token expired\|wrong password\|validation failed\|internal error\|invalid request\|user already exists\|invalid display_name" internal`) |
| `internal/handler/auth_fehler_zweisprachig_test.go` | CREATE | Tests zu den ACs 1 bis 4 |
| `frontend/src/routes/reset-password/__tests__/abgelaufener_link.test.ts` | CREATE | AC-5 |

## Estimated Scope

- **LoC:** ca. 180 hinzugefügte und ca. 420 entfernte Zeilen (je Fehlerstelle ersetzt eine Zeile `WriteError(...)` den Block aus Header, `WriteHeader` und `w.Write`); Katalogdaten ca. 130 Zeilen zusätzlich. Wegen der Zahl der Stellen `loc_limit_override 500` einplanen.
- **Files:** 18 geänderte oder neue Dateien plus die angepassten Bestandstests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2675 (G1) | Paket | `WriteError`, `Lang`-Middleware, Suchkette `auth.fehler.*`/`konto.fehler.*` (Voraussetzung) |
| #2646 (S1) | Paket | Sprachfeld am Nutzer, damit `en`-Nutzer im Test existieren |
| #2679 (G5) | Paket | Wächter; nach diesem Paket bleiben nur die Mail-Dateien (G4) in der Allowlist |
| `internal/i18n` | Modul | Katalog |
| `docs/reference/i18n_glossar.md` | Doku | bindende Wortwahl und Verbotsliste |
| ADR-0104 | ADR | Sprache am Nutzer |

## Implementation Details

**Muster (aus G1).** `WriteError(w, r, status, code, nil)`; Header wie `Retry-After` setzt der Handler vorher selbst. Das Alt-Feld `error` in der Antwort trägt weiter den `code`, daher bleiben alle bereits snake_case benannten Codes (`store_error`, `not_found`, `email_taken`, `invite_invalid`, `rate_limit_exceeded` …) für Clients identisch.

**Beispiel-Umstellung** `internal/handler/auth.go:329-333` (LoginHandler, falsches Passwort), vorher:

```go
if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(401)
	w.Write([]byte(`{"error":"invalid credentials"}`))
	return
}
```

nachher:

```go
if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
	WriteError(w, r, http.StatusUnauthorized, "invalid_credentials", nil)
	return
}
```

Dasselbe gilt für `passkey.go:43-47`: die Funktion `writeJSONError` wird gelöscht, jeder Aufruf `writeJSONError(w, http.StatusNotFound, "not_found")` wird zu `WriteError(w, r, http.StatusNotFound, "not_found", nil)`; in `admin_users.go:60-62` entsprechend `adminError`. Die Kopf-Zeile `w.Header().Set("Content-Type", "application/json")` am Anfang von Handlern, die auch Erfolgsantworten schreiben, bleibt.

**Alt-Wörter auf Codes (Pflicht, damit der Code stabil und snake_case ist):**

| bisher in `auth.go` / `auth_magic.go` | neuer `code` |
|---|---|
| `invalid request` | `invalid_request` |
| `validation failed` | `validation_failed` |
| `internal error` | `internal_error` |
| `invalid credentials` | `invalid_credentials` |
| `user already exists` | `user_already_exists` |
| `invalid token` | `invalid_token` |
| `token expired` | `token_expired` |
| `wrong password` | `wrong_password` |
| `invalid display_name` | `invalid_display_name` |
| `internal` (account_delete_code.go) | `internal_error` |

**Katalog-Namensraum:** `auth.fehler.<code>` für Anmeldung, Registrierung, Tokens, Passkey, Magic-Link; `konto.fehler.<code>` für Profil, Passwort, Level-Antrag, Admin, Löschung. Die Schlüssel der Start-Codes (`not_found`, `store_error`, `unauthorized`, `forbidden`, `invalid_request`, `internal_error`, `rate_limit_exceeded`, `validation_error`, `bad_request`) existieren seit G1 in `fehler.json` und werden nicht erneut angelegt. Jede Stelle, die einen Code neu einführt, bekommt ihren Schlüssel in **beiden** Sprachdateien.

**Beispiel-Schlüssel (de | en), alle Texte verbindlich:**

| Schlüssel | de | en |
|---|---|---|
| `auth.fehler.invalid_credentials` | Benutzername oder Passwort ist falsch. | Username or password is incorrect. |
| `auth.fehler.user_already_exists` | Dieser Benutzername ist bereits vergeben. | This username is already taken. |
| `auth.fehler.email_taken` | Diese E-Mail-Adresse wird bereits verwendet. | This email address is already in use. |
| `auth.fehler.invalid_email` | Bitte gib eine gültige E-Mail-Adresse an. | Please enter a valid email address. |
| `auth.fehler.validation_failed` | Die Eingaben sind unvollständig oder ungültig. | The input is incomplete or invalid. |
| `auth.fehler.invite_invalid` | Die Einladung ist ungültig oder bereits verwendet. | The invitation is invalid or has already been used. |
| `auth.fehler.email_not_verified` | Bitte bestätige zuerst deine E-Mail-Adresse. | Please confirm your email address first. |
| `auth.fehler.account_disabled` | Dieses Konto ist gesperrt. | This account is disabled. |
| `auth.fehler.invalid_token` | Der Link ist ungültig. | The link is invalid. |
| `auth.fehler.token_expired` | Der Link ist abgelaufen. | The link has expired. |
| `auth.fehler.address_taken` | Diese Adresse gehört bereits zu einem anderen Konto. | This address already belongs to another account. |
| `auth.fehler.invalid_or_expired_code` | Der Code ist ungültig oder abgelaufen. | The code is invalid or has expired. |
| `auth.fehler.max_attempts_exceeded` | Zu viele Fehlversuche. Fordere einen neuen Code an. | Too many failed attempts. Request a new code. |
| `auth.fehler.google_oauth_not_configured` | Die Anmeldung mit Google ist nicht eingerichtet. | Sign-in with Google is not set up. |
| `auth.fehler.webauthn_begin_failed` | Der Passkey-Vorgang konnte nicht gestartet werden. | The passkey process could not be started. |
| `auth.fehler.begin_failed` | Der Vorgang konnte nicht gestartet werden. | The process could not be started. |
| `auth.fehler.invalid_body` | Die Anfrage enthält keine gültigen Daten. | The request contains no valid data. |
| `auth.fehler.attestation_invalid` | Der Passkey konnte nicht überprüft werden. | The passkey could not be verified. |
| `auth.fehler.challenge_expired_or_missing` | Die Passkey-Anfrage ist abgelaufen. Bitte starte sie neu. | The passkey request has expired. Please start again. |
| `auth.fehler.user_mismatch` | Die Anfrage gehört nicht zu diesem Konto. | The request does not belong to this account. |
| `auth.fehler.missing_credential_id` | Die Passkey-Kennung fehlt. | The passkey ID is missing. |
| `auth.fehler.invalid_credential_id` | Die Passkey-Kennung ist ungültig. | The passkey ID is invalid. |
| `auth.fehler.cannot_remove_last_passkey_without_password` | Der letzte Passkey kann nur entfernt werden, wenn ein Passwort gesetzt ist. | The last passkey can only be removed if a password is set. |
| `konto.fehler.wrong_password` | Das Passwort ist falsch. | The password is incorrect. |
| `konto.fehler.invalid_display_name` | Der Anzeigename ist ungültig (höchstens 50 Zeichen, keine Steuerzeichen). | The display name is invalid (at most 50 characters, no control characters). |
| `konto.fehler.invalid_sms_number` | Die SMS-Nummer ist ungültig. Bitte im Format +491701234567 angeben. | The SMS number is invalid. Please use the format +491701234567. |
| `konto.fehler.invalid_tier` | Das gewünschte Level ist ungültig. | The requested level is invalid. |
| `konto.fehler.already_current_tier` | Du hast dieses Level bereits. | You already have this level. |
| `konto.fehler.mail_failed` | Die E-Mail konnte nicht versendet werden. | The email could not be sent. |
| `konto.fehler.cannot_disable_self` | Du kannst dein eigenes Konto nicht sperren. | You cannot disable your own account. |
| `konto.fehler.invite_used` | Die Einladung wurde bereits verwendet. | The invitation has already been used. |
| `konto.fehler.note_too_long` | Die Notiz ist zu lang. | The note is too long. |

**Redirect- und Maschinen-Pfade bleiben:** `googleOAuthFail` (Weiterleitung mit Query-Parameter), `status:"ok"`-Antworten von `ForgotPasswordHandler` (Anti-Enumeration) und alle `log.Printf`-Zeilen bleiben wörtlich unverändert (Logs sind deutsch, bei Umlauten mit `// i18n-log`).

**Frontend-Stellen.** Die drei oben genannten Vergleiche werden von `error`-Wörtern mit Leerzeichen auf `code` umgestellt; die dort angezeigten Texte („Token abgelaufen", „Ungültiger Token") ziehen erst F1/F4 in den Katalog, hier ändert sich nur der Vergleich. Vitest-Fakes, die die Alt-Wörter liefern, werden mitgezogen (`grep -rn "token expired\|wrong password" frontend/src`).

**Allowlist-Eintrag (G5):** keiner. Die G2-Dateien enthalten außer den Mail-Bauern (`account_delete_code.go`, `auth_oauth.go`, beide G4) keine deutschen Nutzertexte; ihre Einträge bleiben bis G4 stehen. Der Veraltet-Test des Wächters beweist, dass für die übrigen G2-Dateien nie ein Eintrag nötig war.

**Glossar:** `Level` kommt in Mails und im Frontend („Level-Wechsel") vor, steht aber noch nicht im Glossar. Dieses Paket trägt als erste Änderung die Zeile `Level (Tarifstufe) | level` ein; „Tarif" ergänzt G3.

## Expected Behavior

- **Input:** Anfragen an Auth-, Profil-, Passkey-, Magic-Link-, Admin-Nutzer-, Admin-Einladungs- und Lösch-Code-Endpunkte, die in einen Fehlerzweig laufen.
- **Output:** gleicher HTTP-Status wie bisher; Body `application/json` mit `code`, `message` (Nutzersprache), Übergangsfeld `error` (= `code`) und `detail`.
- **Side effects:** keine. Insbesondere keine Änderung an `user.json`, Sitzungen, Tokens oder Logzeilen.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit Sprache `en` / When er sein Profil mit der SMS-Nummer `12345` speichert / Then antwortet die API mit 400, `code` `invalid_sms_number` und der englischen `message` „The SMS number is invalid. Please use the format +491701234567.", und seine `user.json` bleibt byte-identisch.
  - Test: internal/handler/auth_fehler_zweisprachig_test.go — echter `UpdateProfileHandler` mit Sitzung des `en`-Nutzers im Temp-Datenverzeichnis; Body und Dateivergleich.

- **AC-2:** Given ein angemeldeter Nutzer mit Sprache `de` / When er denselben ungültigen Wert sendet / Then ist der Status 400, `code` und Alt-Feld `error` lauten `invalid_sms_number`, und die `message` steht auf Deutsch laut Katalog.
  - Test: internal/handler/auth_fehler_zweisprachig_test.go — gleicher Aufruf mit `de`-Nutzer; zusätzlich Registrierung mit E-Mail ohne `@` liefert 400 `invalid_email` mit der Meldung der Besuchersprache.

- **AC-3:** Given ein Besucher ohne Anmeldung / When er sich mit falschem Passwort anmeldet, einmal mit `Accept-Language: en` und einmal ohne Header / Then antwortet die API beide Male mit 401 und `code` `invalid_credentials`, auf Englisch („Username or password is incorrect.") bzw. auf Deutsch („Benutzername oder Passwort ist falsch."), und es bleibt bei einer einheitlichen Antwort für „Nutzer unbekannt" und „Passwort falsch".
  - Test: internal/handler/auth_fehler_zweisprachig_test.go — echter `LoginHandler` hinter der echten `Lang`-Middleware; unbekannter Nutzer und falsches Passwort liefern byte-gleiche Bodies.

- **AC-4:** Given zwei Nutzer A (`en`) und B (`de`) / When beide gleichzeitig eine abgelehnte Profil-Änderung senden / Then erhält jeder die Meldung seiner Sprache, und keiner sieht Daten oder Sprache des anderen.
  - Test: internal/handler/auth_fehler_zweisprachig_test.go — parallele Anfragen beider Sitzungen; `user.json` beider Nutzer vorher/nachher identisch.

- **AC-5:** Given die Frontend-Stellen für Link-Prüfung und Passwortwechsel / When die API `{"code":"token_expired"}` bzw. `{"code":"wrong_password"}` liefert / Then zeigen Seite „Passwort zurücksetzen" und Konto-Seite weiterhin dieselben Hinweise wie vorher („Token abgelaufen" bzw. die Passwort-falsch-Meldung).
  - Test: frontend/src/routes/reset-password/__tests__/abgelaufener_link.test.ts — echte `load`/`actions` mit gefaktem `fetch`-Ergebnis der Go-API (kein Spiegel der eigenen Logik: der Test bildet die neue API-Antwort nach); Konto-Seite im bestehenden Konto-Test.

- **AC-6:** Given der Wächter aus G5 / When `go test ./internal/i18n/...` nach der Umstellung läuft / Then ist er grün, und in den G2-Dateien (außer den zwei Mail-Dateien aus G4) findet er keinen deutschen Nutzertext; `writeJSONError` und `adminError` existieren nicht mehr.
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — unverändert ausgeführt; Adversary-Punkt „Allowlist-Eintrag des Pakets entfernt?" ist hier „kein Eintrag nötig".

## Known Limitations

- **Annahme (kein „wortgleich"):** Die Go-Handler lieferten bisher nur Codes, keine deutschen Sätze (das Frontend übersetzt selbst). Die deutschen Katalogtexte sind daher neu, nicht wortgleich zu einem Altzustand. Bestandsverhalten (Status, Codes, Abläufe, Logs) bleibt gleich.
- **Annahme (Issue-Skizze):** Die AC-Skizze nennt `email_invalid` für das Profil. Im Code heißt der Code bei der Registrierung `invalid_email` und das Profil prüft keine E-Mail-Form, sondern SMS-Nummer und Anzeigename; die ACs nutzen daher `invalid_sms_number` und `invalid_email` mit den realen Codes.
- **Annahme (Glossar):** `Level` wird als Zeile ergänzt, weil Mails und Frontend den Begriff schon nutzen; „Tarif" ergänzt G3.
- Die Namen `invalid_tier`, `already_current_tier` und `cannot_disable_self` stammen aus dem Code und behalten ihre englische Form (stabile Codes); nur die Meldung ist sprachabhängig.
- Mehrfache Fälle mit identischem Code und unterschiedlichem Text gibt es in den G2-Dateien nicht; wo G3 das braucht, nutzt es die Variante aus G1.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Fehlertexte der Go-API folgen der Nutzersprache über den Katalog; der stabile `code` bleibt die Maschinenschnittstelle.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
