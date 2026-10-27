# Context: fix-2160-account-loeschung-reste

## Request Summary
Issue #2160 (Teil von Epic #2138 Multi-User). `DELETE /api/auth/account` löscht nur `data/users/<id>/`
und verlangt keine Re-Authentifizierung. Gefordert: Löschung räumt Telegram-Tokens und OTPs des Nutzers,
Re-Auth (Passwort oder frischer Magic-Code) vor der Löschung, Reaper für In-Memory-Stores, Test „kein
Eintrag mit User-ID in `telegram_tokens.json` nach Löschung".

## Korrektur am Issue-Befund (Stand origin/main 2026-10-03)
- **`sessionBlacklist` existiert nicht mehr.** Seit #2129 / ADR-0060 gibt es eine persistente
  Sitzungs-Allowlist (`data/users/<id>/sessions.json`, `store/sessions.go`). Löschen des Ordners
  entwertet alle Sessions dauerhaft, auch über Neustart. → Blacklist-Punkt und dessen Reaper entfallen.
- **„PII-Issue"/briefing_log-Anonymisierung:** kein offenes Issue gefunden; `briefing_log.json`/`alert_log.json`
  liegen im Nutzerordner und werden mitgelöscht. Log-Zeilen enthalten User-IDs (z. B. `auth.go:695`) —
  verwandt: `docs/specs/modules/pii_log_masking.md`. Nicht Teil dieses Tickets.
- Reaper nötig nur noch für **`otpStore`** und **`TelegramTokenStore.tokens`**.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go:296-322` | `DeleteAccountHandler`: kein Body, keine Re-Auth, kein Locking, kein Aufräumen außerhalb des Ordners; 404/500/200 |
| `internal/handler/auth.go:243-294` | `LoginHandler`, bcrypt-Vergleich `:280` |
| `internal/handler/auth.go:1462-1525` | `ChangePasswordHandler` — **Re-Auth-Muster** (`old_password`, 403 `wrong password`) |
| `internal/handler/auth_magic.go:37-44,81,162,179` | `otpEntry{code,expiresAt,attempts}`, `var otpStore sync.Map` keyed by normalisierter E-Mail, TTL 15 min, kein Reaper; Anfordern braucht keinen Account (#2147) |
| `internal/handler/auth_magic.go:262ff` | `createMagicLinkUser` (Konten `m-{8hex}` ohne Passwort) |
| `internal/handler/telegram_connect.go:17-94` | `TelegramTokenStore` (`tokens map`, `mu`), `load` filtert abgelaufene, `save` nicht atomar/Fehler verschluckt, `CreateToken` TTL 24h Literal `:80`, `ResolveAndDelete :88`; Connect-Handler `:194-219` (LoadUser→SaveUser-Fenster) |
| `internal/store/user.go:381-387` | `DeleteUser` = `ValidUserID` + `os.RemoveAll` |
| `internal/store/address_owner.go:21,29,39` | `NormalizeEmailAddress`, `EffectiveContactAddress`, `HasLoginCredentials` |
| `internal/store/sessions.go:99-165` | Session-Allowlist |
| `internal/middleware/auth.go:24,41-60,152` | Session-TTL 400 d, Public-Allowlist, `ClearSessionCookie` |
| `internal/router/router.go:28,39,50,100,122,129-131` | Route DELETE account `:100`, PUT password `:122`, Deps-Injektion TelegramTokenStore |
| `cmd/server/main.go:66,107,110,124` | Instanziierung Token-Store, kein Graceful Shutdown |
| `internal/scheduler/user_run_state.go:23,57,214,296` | globale `scheduler_user_state.json` — hat bereits `Prune` für verschwundene Nutzer |
| `frontend/src/routes/account/+page.svelte:488-502,1270,1405-1420` | Lösch-Button, Dialog, `api.del('/api/auth/account')` |
| `frontend/src/lib/api.ts:200` | `api.del` ohne Body — muss für Re-Auth erweitert werden |
| `frontend/e2e/issue-314-empty-state.spec.ts:214-240` | prüft nur Dialog-Öffnen |
| `frontend/e2e/kanal-an-aus-kette.staging.spec.ts:289` | DELETE ohne Body als Aufräumschritt — **bricht bei Re-Auth-Pflicht** |

## Existing Patterns
- **Re-Auth:** `ChangePasswordHandler` (Body `old_password`, bcrypt, 403). Ohne-Passwort-Konten (Magic-Link, Passkey, Google-OAuth) brauchen alternativen Nachweis (frischer Magic-Code an die eigene Adresse, `EffectiveContactAddress`).
- **Reaper:** `ChallengeStore.gc()` (`handler/challenge_store.go:51-61`, `time.Tick(1min)` im Konstruktor), `IPRateLimiter.cleanupLoop` (`middleware/ratelimit.go:40,60`, Ticker 10 min), `MailFloodLimiter.cleanupLoop` (`handler/profile_mail_ratelimit.go:50,122`). Keine mit Context/Stop.
- **Globale-Dateien-Bereinigung:** `scheduler_user_state` Prune beim nächsten Lauf.
- **Tests:** `newTestStore(t)` (`trip_write_test.go:15`), `middleware.ContextWithUserID`, `NewTelegramTokenStore(t.TempDir())`; Zwei-Nutzer-Muster in `telegram_connect_uniqueness_test.go`, `router/admin_trigger_test.go:297`; `auth_magic_test.go` greift direkt auf `otpStore` zu.

## Dependencies
- Upstream: store (`LoadUser`, `DeleteUser`, Sessions), bcrypt, `NormalizeEmailAddress`, Mailversand Magic-Code.
- Downstream: Frontend Account-Seite, E2E-Aufräumschritte (Staging-Spec), `api.del`.

## Existing Specs / ADRs
- `docs/specs/modules/account_deletion.md` (draft; Known Limitation „Keine Bestätigungsabfrage auf API-Ebene")
- `docs/specs/modules/session_allowlist.md`, `telegram_chat_id_ownership.md`, `magic_link_adress_eindeutigkeit.md`, `account_page_extend.md`, `user_data_export.md`
- ADR-0030 (HMAC-Cookie), ADR-0060 (Widerrufsliste), ADR-0066 (Login braucht bestätigte E-Mail)
- `docs/reference/api_contract.md:179, :2618`

## Risks & Considerations
- **Auth-/Destruktiv-Pfad:** Re-Auth darf weder umgehbar sein noch Ohne-Passwort-Konten aussperren.
- **Mandantentrennung:** Räumung nur Einträge mit eigener `user_id`; Pflicht-Test mit zwei Nutzern (B bleibt unberührt).
- **OTPs sind per E-Mail gekeyt**, nicht per User-ID → Räumung über alle Adressen des Nutzers (`Email`, `MailTo`, `PendingContactAddress`). Ein OTP für eine fremde Adresse ist kein Nutzerdatum.
- **Race:** paralleler Telegram-Connect zwischen `LoadUser` und `SaveUser` könnte Ordner neu anlegen (aus Code abgeleitet, unverifiziert).
- **`save()` nicht atomar, Fehler verschluckt** — Räumung muss Persistenz wirklich erreichen (Test liest Datei).
- **Bestandsaufrufer brechen:** Staging-E2E-Aufräumschritt ohne Body; Frontend-Dialog braucht Eingabefeld/Code-Schritt.
- Re-Auth-Brute-Force: DELETE hat keinen Rate-Limiter.

## Analysis

### Type
Bug (Sicherheit/Datenschutz, Multi-User-Epic #2138) — Schwere Mittel.

### Verifizierte Fakten (2026-10-03)
- **Login-Methoden** (`internal/model/user.go:13,14,19-20`): `PasswordHash`, `PasskeyCredentials`, `OAuthSub/OAuthProvider`, Magic-Link ohne Feld. **Konten ohne Passwort existieren** (Magic-Link `m-…`, Passkey-only, Google-only) → Passwort-Re-Auth allein sperrt sie aus.
- **Jedes Konto hat eine E-Mail** (Pflichtfeld `auth.go:80`, alle Anlagewege setzen `Email`/`MailTo`). Bestätigt (`EmailVerifiedAt`) sofort nur bei Magic-Link (`auth_magic.go:280`); Register/OAuth/Passkey starten unbestätigt.
- **Adressänderung** (`auth.go:1094-1119`): Bei bestätigtem Konto geht eine Änderung der **wirksamen** Adresse (`EffectiveContactAddress` = `mail_to` sonst `email`, `address_owner.go:29`) erst über `PendingContactAddress` + Bestätigung; das **inaktive** Feld ist direkt schreibbar. Bei unbestätigtem Konto wird direkt geschrieben.
- **Einziger Löschweg:** `DeleteAccountHandler` (`auth.go:296-322`) → `store.DeleteUser` (`store/user.go:381`). Kein Admin-, Retention- oder Python-Löschpfad.
- **Globale Reste mit Nutzerbezug:** `data/telegram_tokens.json` (Eintrag `{UserID, ExpiresAt}`, `telegram_connect.go:17-102`, `save()` nicht atomar, Fehler verschluckt, einziger Erzeuger `GetTelegramLinkHandler:124`), `otpStore` (in-memory, keyed by normalisierter Adresse, TTL 15 min, max 3 Versuche, Prüfung inline in `MagicLinkVerifyHandler:169`). `ChallengeStore` hat bereits gc, `scheduler_user_state.json` bereits Prune → kein Handlungsbedarf.
- **Offenes Login-OTP nach Löschung ist einlösbar** → `createMagicLinkUser` legt sofort ein neues Konto an. Deshalb OTPs aktiv mitlöschen (Ticket-Forderung, kein Reaper-Ersatz).
- **Body-Transport:** Proxy `frontend/src/routes/api/[...path]/+server.ts:19-21` und `send()` (`api.ts:105`) reichen Bodies auch bei DELETE durch; `api.del` (`api.ts:200`) hat aber keinen Body-Parameter.
- **Staging-E2E-Gast** (`kanal-an-aus-kette.staging.spec.ts:188-213`) ist Passwort-Konto (Register + Staging-Verify-Token + Login) → Aufräumschritt `:289` kann per Passwort bestätigen.
- **Bestehende Tests:** `internal/handler/delete_account_test.go` (Ordner weg, Cookie/Sessions geleert, 404) — keine Re-Auth, keine Reste, kein Zwei-Nutzer-Test.
- **ADR:** keines zu Re-Auth vor destruktiven Aktionen. Verwandt: ADR-0060, -0066, -0067.

### Technical Approach (Empfehlung, Tech-Lead-Entscheid)
1. **Neuer Endpunkt `POST /api/auth/account/delete`** mit Body `{password?: string, code?: string}`; alter `DELETE /api/auth/account` entfällt (DELETE-mit-Body ist semantisch undefiniert; Auth-Endpunkte sind POST-Stil). `api_contract.md` nachziehen.
2. **Re-Auth (Sudo-Mode-Muster wie GitHub/Google):**
   - Konto mit `PasswordHash` → `password` (bcrypt, wie `ChangePasswordHandler` `auth.go:1462-1525`, 403 `wrong_password`) **oder** `code`.
   - Konto ohne Passwort → nur `code`.
   - **Lösch-Code:** neuer Endpunkt `POST /api/auth/account/delete-code` schickt 6-stelligen Code an `EffectiveContactAddress(user)`. Eigener Store **keyed by UserID**, getrennt vom Login-`otpStore` → ein Login-OTP taugt nicht als Lösch-Bestätigung und umgekehrt. TTL 15 min, max 3 Fehlversuche (Zähler vor Vergleich), einmalig (CompareAndDelete).
   - **Invariante Empfangsadresse:** Code geht ausschließlich an die *wirksame* Adresse — bei bestätigten Konten ist die nur über Bestätigung änderbar, ein Sitzungsdieb kann sie nicht umbiegen. Bei unbestätigten Konten kann der Sitzungsinhaber die Adresse ohnehin selbst setzen und bestätigen; der Code beweist dann dieselbe Adresskontrolle wie die E-Mail-Bestätigung — kein Schutzverlust, aber auch keine Aussperrung. Da jedes Konto eine Adresse hat, gibt es keinen „keine Methode"-Fall.
   - Passkey als Nachweis: bewusst nicht (eigene WebAuthn-Zeremonie, ~150 LoC mehr Risiko; Code deckt Passkey-Konten ab).
3. **Aufräumen in gemeinsamer Funktion** (nicht im Handler verstreut), Reihenfolge: Re-Auth prüfen (Fehler ⇒ keinerlei Seiteneffekt) → `telegramConnectMu` nehmen → `TelegramTokenStore.RemoveByUser(id)` (persistiert; Fehler ⇒ 500, Ordner bleibt, Nutzer kann wiederholen) → Login-OTPs für `Email`, `MailTo`, `PendingContactAddress` löschen → Lösch-Code entfernen → `DeleteUser` → Cookie löschen.
4. **`TelegramTokenStore.save()`** atomar (Temp-Datei + `os.Rename`) mit Fehlerrückgabe; `CreateToken` gibt Fehler weiter, `GetTelegramLinkHandler` antwortet dann 500 statt eines nie gespeicherten Tokens.
5. **Reaper:** testbare `gc(now)` für `otpStore`, `TelegramTokenStore` und Lösch-Code-Store (Muster `ChallengeStore.gc`, `challenge_store.go:51-61`); Start über Ticker aus `cmd/server/main.go`, nicht im Konstruktor (keine Goroutinen in Tests). OTP-Einträge mit `attempts>=3` erst nach Ablauf entfernen (sie sind die Sperre).
6. **Race Telegram-Connect** (`telegram_connect.go:194-219`, LoadUser→SaveUser könnte gelöschten Ordner als Zombie neu anlegen): Connect lädt den Nutzer erst unter `telegramConnectMu`; Löschung nimmt denselben Mutex. ~5 LoC.
7. **Rate-Limit:** `IPRateLimiter(5, 15min)` auf `/account/delete`; `IPRateLimiter(3, 15min)` + Mindestpause pro Nutzer (Mail-Flood-Limiter wiederverwenden, falls passend) auf `/account/delete-code`.
8. **Frontend:** Lösch-Dialog (`frontend/src/routes/account/+page.svelte:1405-1420`) bekommt Passwortfeld (falls Konto Passwort hat) bzw. „Code an <Adresse> senden" + Codefeld; Aufruf per `api.post`. Ob das Konto ein Passwort hat, muss das Profil-DTO liefern (prüfen, ob schon vorhanden).
9. **Staging-E2E** `kanal-an-aus-kette.staging.spec.ts:289` auf `POST …/delete {password}` umstellen.

### Affected Files
| File | Change | Beschreibung |
|------|--------|--------------|
| `internal/handler/auth.go` | MODIFY | Lösch-Handler mit Re-Auth, gemeinsame Aufräumfunktion |
| `internal/handler/account_delete_code.go` | CREATE | Lösch-Code-Store, Versand-Endpunkt, gc |
| `internal/handler/auth_magic.go` | MODIFY | `gc(now)` für otpStore, Löschen per Adressliste |
| `internal/handler/telegram_connect.go` | MODIFY | `RemoveByUser`, atomares `save()` mit Fehler, `gc`, Connect lädt unter Mutex |
| `internal/router/router.go` | MODIFY | neue Routen + Rate-Limiter, alte DELETE-Route weg |
| `cmd/server/main.go` | MODIFY | Reaper-Start |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Bestätigungs-Dialog |
| `frontend/e2e/kanal-an-aus-kette.staging.spec.ts` | MODIFY | Aufräumschritt mit Passwort |
| `internal/handler/delete_account_test.go` | MODIFY | auf neuen Endpunkt, Re-Auth-Fälle |
| `internal/handler/*_test.go` (neu, verhaltensbenannt) | CREATE | Zwei-Nutzer-Reste-Test, Reaper, Race |
| `docs/specs/modules/account_deletion.md` | MODIFY | Spec erweitern (Known Limitation streichen) — keine neue Spec |
| `docs/reference/api_contract.md` | MODIFY | Endpunktwechsel |
| `docs/adr/` | CREATE | ADR „Re-Auth vor Kontolöschung (Passwort oder Lösch-Code)" — Auth-Entscheidungsfläche |

### Scope Assessment
- Dateien: ~9 Code + Tests + 3 Doku
- Geschätzte LoC: +300–380 produktiv (über Limit 250 → `loc_limit_override 500` in Phase 4 setzen; Epic-Regel: nicht abspalten)
- Risiko: **MITTEL** — Auth-/destruktiver Pfad; Frontend-Dialog größter Brocken; Code-Zustellung nur auf Staging messbar (Wegwerf-Nutzer `gregor-test+…`, IMAP).

### Pflicht-Tests (für /40)
- Zwei Nutzer: A löscht → kein Eintrag mit A's ID in `telegram_tokens.json` (Datei von Platte lesen), B's Token + Ordner unberührt.
- Falsches Passwort → 403, Ordner + Tokens bleiben. Ohne Nachweis → 400/403, nichts gelöscht.
- Passwortloses Konto: Passwortweg abgelehnt, Code-Weg löscht.
- Login-OTP als Lösch-Code abgelehnt; A's Lösch-Code löscht nicht B.
- Login-OTP für A's Adressen nach Löschung nicht mehr einlösbar (kein neues Konto).
- gc entfernt abgelaufene Einträge aller drei Stores, behält gültige.
- Telegram-Connect nach Löschung legt keinen Ordner neu an.
- `save()`-Fehler ⇒ Löschung 500, Ordner bleibt.

### Open Questions
- Keine PO-Fragen. Technische Wahlpunkte (Passwort-Konten dürfen auch per Code löschen; kein Passkey-Nachweis; POST statt DELETE) sind oben entschieden.
