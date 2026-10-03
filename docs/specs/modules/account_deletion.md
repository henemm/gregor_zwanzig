---
entity_id: account_deletion
type: module
created: 2026-04-16
updated: 2026-10-03
status: draft
version: "2.0"
tags: [go, auth, account-deletion, f15, reauth, multi-user, "2160"]
---

# F15 Phase 3 — Account Deletion (mit Re-Authentifizierung und Restebereinigung)

## Approval

- [ ] Approved

## Purpose

Eingeloggte Nutzer können ihren Account löschen. Alle Nutzerdaten werden kaskadierend entfernt (Orte, Trips, Abos, GPX, Snapshots, `user.json`). **Seit #2129/ADR-0060:** `data/users/{id}/sessions.json` liegt im gelöschten Verzeichnis, damit sind alle Anmeldungen des Nutzers auf allen Geräten ungültig.

**Seit #2270:** `GET /api/auth/export` liefert die lesende Gegenrichtung (siehe `docs/specs/modules/user_data_export.md`).

**Neu mit #2160 (Epic #2138 Multi-User):** Die Löschung war bisher (a) ohne Nachweis möglich — ein gestohlenes Sitzungs-Cookie genügte — und (b) ließ sie Daten mit Nutzerbezug außerhalb des Nutzerordners zurück (Telegram-Tokens in `data/telegram_tokens.json`, offene Login-OTPs im Speicher, die nach der Löschung sofort ein neues Konto anlegen konnten). Jetzt verlangt die Löschung einen frischen Nachweis (Passwort ODER Lösch-Code per E-Mail) und räumt alle Reste des Nutzers, ohne andere Nutzer zu berühren.

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `DeleteAccountHandler` (wird zum POST-Handler mit Re-Auth), gemeinsame Aufräumfunktion `deleteAccountCascade`; neu `internal/handler/account_delete_code.go`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.DeleteUser` (`internal/store/user.go`) | module | Entfernt `data/users/{id}/` |
| `store.EffectiveContactAddress`, `NormalizeEmailAddress` (`internal/store/address_owner.go`) | module | Empfangsadresse des Lösch-Codes, Schlüssel der Login-OTPs |
| `ChangePasswordHandler` (`auth.go`) | function | Muster für bcrypt-Re-Auth, 403 |
| `otpStore` (`internal/handler/auth_magic.go`) | module | Login-OTPs je Adresse; werden bei Löschung entfernt und bekommen `gc(now)` |
| `TelegramTokenStore` (`internal/handler/telegram_connect.go`) | module | `RemoveByUser`, atomares `save()`, `gc(now)` |
| `telegramConnectMu` | module | Serialisiert Telegram-Connect und Löschung |
| `MailFloodLimiter` (`profile_mail_ratelimit.go`), `IPRateLimiter` (`middleware/ratelimit.go`) | module | Rate-Limits auf beiden neuen Endpunkten |
| Mailversand (Magic-Code-Pfad) | module | Zustellung des Lösch-Codes über Resend |
| `golang.org/x/crypto/bcrypt` | library | Passwortvergleich |
| `docs/specs/modules/session_allowlist.md`, `telegram_chat_id_ownership.md`, `magic_link_adress_eindeutigkeit.md` | spec | Verwandte Mechanik, nicht verändert |
| ADR-0060, ADR-0066, ADR-0067 | adr | Sitzungs-Allowlist, bestätigte Adresse, Adress-Eindeutigkeit |

## Scope

### In Scope

- Neuer Endpunkt `POST /api/auth/account/delete` (Body `{password?, code?}`); der alte `DELETE /api/auth/account` entfällt ersatzlos (DELETE mit Body ist semantisch undefiniert, Auth-Endpunkte sind POST-Stil).
- Neuer Endpunkt `POST /api/auth/account/delete-code` — sendet einen 6-stelligen Lösch-Code an die wirksame Adresse.
- Eigener Lösch-Code-Store (Schlüssel UserID), getrennt vom Login-OTP-Store.
- Gemeinsame Aufräumfunktion: Telegram-Tokens, Login-OTPs aller Adressen, Lösch-Code, Nutzerordner.
- Atomares `TelegramTokenStore.save()` mit Fehlerrückgabe.
- Reaper `gc(now)` für `otpStore`, `TelegramTokenStore`, Lösch-Code-Store; Start aus `cmd/server/main.go`.
- Race-Schutz Telegram-Connect gegen Löschung (kein Zombie-Ordner).
- Rate-Limits, Frontend-Dialog, Staging-E2E-Aufräumschritt, ADR, `api_contract.md`.

### Out of Scope

- `sessionBlacklist` (existiert seit #2129/ADR-0060 nicht mehr; die Allowlist stirbt mit dem Nutzerordner) — kein Reaper dafür nötig.
- PII-Log-Masking (User-IDs in Log-Zeilen, z. B. `auth.go:695`) — eigenes Thema, siehe `docs/specs/modules/pii_log_masking.md`.
- Passkey als Re-Auth-Nachweis (eigene WebAuthn-Zeremonie; Passkey-Konten löschen über den Code).
- Soft-Delete / Backup vor Löschung, Admin-seitige Nutzerlöschung.
- `scheduler_user_state.json` (hat bereits `Prune`) und `ChallengeStore` (hat bereits gc).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | Lösch-Handler mit Re-Auth, `deleteAccountCascade`, Profil-DTO-Feld `has_password` |
| `internal/handler/account_delete_code.go` | CREATE | Lösch-Code-Store, Versand-Endpunkt, `gc(now)` |
| `internal/handler/auth_magic.go` | MODIFY | `gc(now)` für `otpStore`, Entfernen per Adressliste |
| `internal/handler/telegram_connect.go` | MODIFY | `RemoveByUser`, atomares `save()` mit Fehler, `gc(now)`, Connect lädt unter Mutex |
| `internal/router/router.go` | MODIFY | Neue Routen mit Rate-Limitern, alte DELETE-Route entfernt |
| `cmd/server/main.go` | MODIFY | Reaper-Ticker starten |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Bestätigungs-Dialog (Passwort bzw. Code) |
| `frontend/e2e/kanal-an-aus-kette.staging.spec.ts` | MODIFY | Aufräumschritt `:289` auf `POST …/account/delete {password}` |
| `internal/handler/delete_account_test.go` | MODIFY | Auf neuen Endpunkt, Re-Auth-Fälle |
| `internal/handler/account_deletion_leftovers_test.go` | CREATE | Zwei-Nutzer-Reste-Test, Lösch-Code, Race, `save()`-Fehler |
| `internal/handler/store_reaper_test.go` | CREATE | `gc(now)` aller drei Stores |
| `docs/adr/0081-reauth-vor-kontoloeschung.md` | CREATE | ADR „Re-Auth vor Kontolöschung (Passwort oder Lösch-Code)", Status Akzeptiert; Index `docs/adr/README.md` ergänzen |
| `docs/reference/api_contract.md` | MODIFY | Endpunktwechsel, neue Endpunkte, `has_password` |
| `docs/specs/modules/account_deletion.md` | MODIFY | Diese Spec |

### Estimated Changes

- Files: 9 Code, 3 Test, 3 Doku
- LoC: +300/-40 produktiv (über dem 250er-Limit; `loc_limit_override 500` in Phase 4, Epic-Regel: nicht abspalten)

## Implementation Details

### Befund Profil-DTO (geprüft)

`profileResponse` (`internal/handler/auth.go:733ff`) enthält **kein** „hat Passwort"-Feld; vorhanden ist nur `has_passkey`. `model.User.PasswordHash` ist `json:"password_hash,omitempty"` und wird nie ausgeliefert. Konsequenz: `profileResponse` bekommt ein neues, immer vorhandenes Feld `has_password` (bool, abgeleitet aus `PasswordHash != ""`, nie der Hash), Muster `has_passkey`. Das Frontend entscheidet am Wert, ob es ein Passwortfeld zeigt; die Code-Variante steht immer zur Wahl. Konten ohne Passwort existieren (Magic-Link `m-…`, Passkey-only, Google-only), Passwort-Re-Auth allein würde sie aussperren.

### Re-Auth (Sudo-Mode)

- Konto mit `PasswordHash`: `password` (bcrypt, 403 `wrong_password`) ODER `code`.
- Konto ohne Passwort: nur `code`; ein mitgeschicktes `password` wird abgelehnt (403 `wrong_password`).
- Lösch-Code: `POST /api/auth/account/delete-code` erzeugt 6-stelligen Code, speichert ihn im eigenen Store (Schlüssel UserID: `code`, `expiresAt`, `attempts`) und verschickt ihn ausschließlich an `EffectiveContactAddress(user)`. TTL 15 Minuten, maximal 3 Fehlversuche (Zähler wird vor dem Vergleich erhöht), einmalig (CompareAndDelete). Ein Login-OTP ist kein gültiger Lösch-Code und umgekehrt.
- Invariante Empfangsadresse: Bei bestätigten Konten ist die wirksame Adresse nur über Bestätigung änderbar (`PendingContactAddress`), ein Sitzungsdieb kann sie nicht umbiegen. Bei unbestätigten Konten beweist der Code dieselbe Adresskontrolle wie die E-Mail-Bestätigung — kein Schutzverlust, keine Aussperrung. Jedes Konto hat eine Adresse, einen „keine Methode"-Fall gibt es nicht.

### Datenfluss Löschung

Reihenfolge in `deleteAccountCascade` (Details: Analyse `docs/context/fix-2160-account-loeschung-reste.md`):

1. Re-Auth prüfen — Fehler ⇒ keinerlei Seiteneffekt.
2. `telegramConnectMu` nehmen.
3. `TelegramTokenStore.RemoveByUser(userID)` mit Persistierung — Fehler ⇒ 500, Ordner bleibt, Wiederholung möglich.
4. Login-OTPs für `Email`, `MailTo`, `PendingContactAddress` (normalisiert) aus `otpStore` entfernen.
5. Lösch-Code des Nutzers entfernen.
6. `DeleteUser(userID)`.
7. Cookie löschen, 200 `{"status":"deleted"}`.

Nur Einträge mit eigener `user_id` bzw. eigenen Adressen werden entfernt. Ein OTP für eine fremde Adresse ist kein Nutzerdatum.

### Weitere Bausteine

- **`TelegramTokenStore.save()`:** Temp-Datei + `os.Rename`, Fehler wird zurückgegeben; `CreateToken` reicht ihn weiter, `GetTelegramLinkHandler` antwortet bei Fehler 500 statt eines nie gespeicherten Tokens.
- **Reaper:** testbare `gc(now)` je Store (Muster `ChallengeStore.gc`, `challenge_store.go`); Start über Ticker aus `main.go`, nicht im Konstruktor (keine Goroutinen in Tests). Login-OTPs mit `attempts>=3` werden erst nach Ablauf entfernt (sie sind die Sperre).
- **Race Telegram-Connect:** Connect lädt den Nutzer erst unter `telegramConnectMu`; die Löschung nimmt denselben Mutex. Ein Connect nach der Löschung findet keinen Nutzer und legt keinen Ordner neu an.
- **Rate-Limits:** `IPRateLimiter(5, 15min)` auf `/account/delete`; `IPRateLimiter(3, 15min)` plus Mindestpause je Nutzer (Mail-Flood-Limiter) auf `/account/delete-code`.
- **Frontend:** Dialog in `account/+page.svelte` zeigt bei `has_password` ein Passwortfeld, immer zusätzlich „Code an <Adresse> senden" mit Codefeld; Aufruf per `api.post`.
- **Staging-E2E:** Gast in `kanal-an-aus-kette.staging.spec.ts` ist Passwort-Konto; Aufräumschritt `:289` sendet `POST /api/auth/account/delete` mit `{password}`.

### Fehlerfälle

| Situation | HTTP | Fehlercode |
|-----------|------|-----------|
| Nicht eingeloggt | 401 | Middleware |
| Weder `password` noch `code` im Body | 400 | `reauth_required` |
| Falsches Passwort / Passwort bei passwortlosem Konto | 403 | `wrong_password` |
| Falscher, abgelaufener, verbrauchter oder gesperrter Lösch-Code | 403 | `invalid_code` |
| Nutzer existiert nicht (mehr) | 404 | `not_found` |
| Rate-Limit überschritten | 429 | `rate_limit_exceeded` (einheitlich mit `IPRateLimiter` und Mail-Flood-Limiter) |
| Token-Store-Persistenz oder `DeleteUser` scheitert | 500 | `internal` (Ordner bleibt, wiederholbar) |
| Code-Versand: Mail kann nicht zugestellt werden | 502 | `mail_failed` (kein Code gespeichert) |

## Expected Behavior

- **Eingeloggt + gültiger Nachweis + `POST /api/auth/account/delete`:** Nutzerordner, Telegram-Tokens, Login-OTPs aller eigenen Adressen und Lösch-Code sind weg; alle Sessions ungültig; Cookie gelöscht.
- **Ohne oder mit falschem Nachweis:** nichts wird gelöscht, keine Nebenwirkung.
- **Nicht eingeloggt:** 401.
- **Nach Löschung:** Login schlägt fehl; ein zuvor offenes Login-OTP legt kein neues Konto an.

## Test Plan

### Automated Tests (TDD RED)

Verhaltensbenannte Dateien (siehe Affected Files), kein Mock-Theater, `newTestStore(t)` und echte Dateien (`NewTelegramTokenStore(t.TempDir())`).

- [ ] Test 1 (Zwei-Nutzer-Pflicht): GIVEN Nutzer A und B mit je einem Telegram-Token, WHEN A löscht mit korrektem Passwort, THEN enthält die von Platte gelesene `telegram_tokens.json` keine A-ID, B-Token und B-Ordner sind unberührt.
- [ ] Test 2: GIVEN falsches Passwort, WHEN POST delete, THEN 403, Ordner und Tokens bleiben.
- [ ] Test 3: GIVEN Body ohne Nachweis, WHEN POST delete, THEN 400, nichts gelöscht.
- [ ] Test 4: GIVEN passwortloses Konto, WHEN Passwort gesendet, THEN 403; WHEN gültiger Lösch-Code gesendet, THEN 200 und Ordner weg.
- [ ] Test 5: GIVEN offenes Login-OTP für A's Adresse, WHEN dieses als `code` gesendet, THEN 403; und A's Lösch-Code löscht B nicht.
- [ ] Test 6: GIVEN Login-OTPs für A's `Email`, `MailTo`, `PendingContactAddress`, WHEN A gelöscht wurde, THEN ist keines einlösbar (kein neues Konto).
- [ ] Test 7: GIVEN Lösch-Code, WHEN 3 Fehlversuche, THEN auch der richtige Code wird abgelehnt; WHEN abgelaufen oder bereits benutzt, THEN 403.
- [ ] Test 8: GIVEN abgelaufene und gültige Einträge in `otpStore`, Token-Store, Lösch-Code-Store, WHEN `gc(now)`, THEN abgelaufene weg, gültige bleiben; OTP mit `attempts>=3` bleibt bis Ablauf.
- [ ] Test 9: GIVEN gelöschter Nutzer, WHEN Telegram-Connect-Request, THEN wird kein Ordner neu angelegt.
- [ ] Test 10: GIVEN Token-Store-Persistenz scheitert, WHEN Löschung, THEN 500 und Ordner bleibt.
- [ ] Test 11: GIVEN Lösch-Code-Anforderung, WHEN Nutzer A mit abweichender `Email`/`MailTo`, THEN geht der Code an `EffectiveContactAddress`.
- [ ] Test 12: GIVEN Profil eines Passwort-Kontos und eines passwortlosen Kontos, WHEN GET Profil, THEN `has_password` true bzw. false, nie ein Hash.
- [ ] Test 13 (Frontend, Staging-Spec): GIVEN Passwort-Konto, WHEN Dialog mit Passwort bestätigt, THEN Konto gelöscht, Weiterleitung auf Login.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer mit Passwort, When er `POST /api/auth/account/delete` mit seinem korrekten Passwort aufruft, Then antwortet der Server 200 `{"status":"deleted"}`, sein Ordner `data/users/<id>/` ist entfernt und das Sitzungs-Cookie gelöscht.
- **AC-2:** Given der Endpunkt `DELETE /api/auth/account` existierte bisher, When er nach der Änderung aufgerufen wird, Then löscht er nichts mehr (Route entfernt, 404/405) und nur `POST /api/auth/account/delete` löscht Konten.
- **AC-3:** Given ein eingeloggter Nutzer, When er die Löschung mit falschem Passwort anfordert, Then antwortet der Server 403 `wrong_password` und weder Ordner, Telegram-Tokens, Login-OTPs noch Lösch-Code werden verändert.
- **AC-4:** Given ein eingeloggter Nutzer, When er die Löschung ohne Passwort und ohne Code anfordert, Then antwortet der Server 400 `reauth_required` und es wird nichts gelöscht.
- **AC-5:** Given ein eingeloggter Nutzer, When er `POST /api/auth/account/delete-code` aufruft, Then wird ein 6-stelliger Code ausschließlich an seine wirksame Adresse (`EffectiveContactAddress`, also `mail_to` sonst `email`) verschickt und im eigenen, nach UserID geschlüsselten Store gespeichert.
- **AC-6:** Given ein Nutzer mit gültigem Lösch-Code, When er die Löschung mit diesem `code` (ohne Passwort) anfordert, Then wird das Konto gelöscht, und derselbe Code ist danach nicht erneut verwendbar (einmalig).
- **AC-7:** Given ein Konto ohne Passwort (Magic-Link, Passkey-only oder Google-only), When es Passwort-Nachweis sendet, Then 403 `wrong_password`; When es einen gültigen Lösch-Code sendet, Then wird es gelöscht und ist nicht ausgesperrt.
- **AC-8:** Given ein offenes Login-OTP (Magic-Link-Code) für die Adresse des Nutzers, When er es als Lösch-`code` sendet, Then 403 `invalid_code`; und ein Lösch-Code ist als Login-OTP nicht einlösbar (getrennte Stores).
- **AC-9:** Given ein Lösch-Code, When er abgelaufen ist (TTL 15 Minuten), bereits einmal benutzt wurde oder dreimal falsch eingegeben wurde, Then antwortet der Server 403 `invalid_code`, auch bei danach richtigem Code.
- **AC-10:** Given Nutzer A und Nutzer B haben je einen Telegram-Token, When A sein Konto löscht, Then enthält die von Platte gelesene `data/telegram_tokens.json` keinen Eintrag mit A's User-ID, während B's Token und B's Ordner unverändert bleiben.
- **AC-11:** Given offene Login-OTPs für A's `Email`, `MailTo` und `PendingContactAddress`, When A sein Konto gelöscht hat, Then ist keines dieser OTPs mehr einlösbar und es entsteht dadurch kein neues Konto; OTPs für fremde Adressen bleiben unberührt.
- **AC-12:** Given ein offener Lösch-Code von Nutzer A, When Nutzer B mit diesem Code löschen will, Then wird B nicht gelöscht (403) und A's Konto bleibt unberührt; A's Lösch-Code wird bei A's Löschung entfernt.
- **AC-13:** Given der Telegram-Token-Store kann nicht persistiert werden, When die Löschung läuft, Then antwortet der Server 500, der Nutzerordner bleibt erhalten und die Löschung ist wiederholbar.
- **AC-14:** Given `TelegramTokenStore.save()` schreibt, When es unterbrochen oder fehlerhaft wird, Then entsteht keine halbe Datei (Temp-Datei + Rename), und `GET`-Link-Erzeugung antwortet bei Speicherfehler 500 statt einen nie gespeicherten Token auszugeben.
- **AC-15:** Given abgelaufene und gültige Einträge in `otpStore`, Telegram-Token-Store und Lösch-Code-Store, When `gc(now)` läuft, Then sind abgelaufene Einträge entfernt, gültige bleiben, und OTPs mit `attempts>=3` bleiben bis zum Ablauf bestehen; der Reaper wird aus `cmd/server/main.go` gestartet, nicht aus Konstruktoren.
- **AC-16:** Given ein Nutzer wurde gelöscht, When anschließend ein Telegram-Connect für ihn eintrifft, Then legt er keinen Nutzerordner neu an (Connect und Löschung serialisiert über `telegramConnectMu`).
- **AC-17:** Given wiederholte Aufrufe, When `/account/delete` mehr als 5 Mal oder `/account/delete-code` mehr als 3 Mal innerhalb von 15 Minuten von derselben IP kommen, Then antwortet der Server 429.
- **AC-18:** Given ein Nutzer öffnet den Löschen-Dialog auf der Account-Seite, When sein Profil `has_password` true liefert, Then sieht er ein Passwortfeld, und in jedem Fall die Möglichkeit „Code an <Adresse> senden" mit Codefeld; bestätigt er korrekt, wird er ausgeloggt und das Konto gelöscht.
- **AC-19:** Given ein Passwort-Konto und ein passwortloses Konto, When das Profil geladen wird, Then liefert `GET /api/auth/profile` `has_password` true bzw. false (immer vorhanden) und nie den Passwort-Hash.
- **AC-20:** Given der Staging-E2E-Gast ist ein Passwort-Konto, When der Aufräumschritt in `kanal-an-aus-kette.staging.spec.ts` ausgeführt wird, Then räumt `POST /api/auth/account/delete` mit `{password}` das Konto weg und der Lauf endet ohne Fehler.
- **AC-21:** Given die Änderung ist umgesetzt, When die Doku geprüft wird, Then existiert ADR `docs/adr/0081-reauth-vor-kontoloeschung.md` (im Index `docs/adr/README.md`) und `docs/reference/api_contract.md` beschreibt beide neuen Endpunkte, den entfallenen DELETE und `has_password`.

## Known Limitations

- Kein Soft-Delete — Daten sind unwiderruflich weg.
- Die API-Bestätigungsabfrage ist mit #2160 gelöst (Re-Auth per Passwort oder Lösch-Code); die frühere Limitation entfällt.
- Seed-User kann sich selbst löschen (wird beim nächsten Restart neu erstellt, falls AUTH_PASS gesetzt).
- Passkey ist kein eigener Nachweis (Passkey-Konten nutzen den Lösch-Code).
- Log-Zeilen mit User-IDs bleiben (Thema `pii_log_masking`).
- Code-Zustellung ist nur auf Staging messbar (Wegwerf-Nutzer `gregor-test+…`, IMAP).

## Changelog

- 2026-04-16: Initial spec (F15 Phase 3 — Account Deletion, GitHub Issue #53)
- 2026-09-06: Session-Invalidierung durch #2129 (ADR-0060) auf alle Geräte ausgeweitet — Details dort, nicht hier nachpflegen.
- 2026-09-09: Querverweis auf #2270 (Datenexport, lesende Gegenrichtung) ergänzt — Details dort, nicht hier nachpflegen.
- 2026-10-03: #2160 — Re-Auth (Passwort oder Lösch-Code), neuer Endpunkt `POST /api/auth/account/delete` statt `DELETE`, Restebereinigung (Telegram-Tokens, Login-OTPs, Lösch-Code), atomares Token-`save()`, Reaper `gc(now)`, Telegram-Connect-Race, Rate-Limits, Frontend-Dialog, `has_password` im Profil. Known Limitation „Keine Bestätigungsabfrage auf API-Ebene" gelöst. Version 2.0.
