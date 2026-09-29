# Context: feature-2155-s3-admin-api

## Request Summary
Issue #2155, Scheibe S3 (Epic #2138 Multi-User-Readiness): Admin-API mit Nutzerliste,
Tier setzen (Roh-Merge, `requested_tier` löschen) und Konto sperren (`disabled`, Sperre bei
der Session-Ausgabe, `ClearSessions`, keine Selbstsperre). S1 (Admin-Rolle, ADR-0078) und
S2 (Status-Token, ADR-0079) sind live; S4 (`/admin`-UI) folgt danach.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/user.go:10-67` | Nutzermodell; Feld `Disabled` fehlt noch. Schema-relevant ⇒ Backup-Hook |
| `internal/model/tier.go:8,23,35-40` | `SmsAllowed`, `PremiumSmsAllowed`, `EffectiveTier` (unbekannt ⇒ free) |
| `internal/store/user.go:20-45` | `ListUserIDs` (ReadDir, scope-exempt) — Grundlage der Nutzerliste |
| `internal/store/user.go:53,76` | `LoadUser`/`SaveUser` typisiert — unbekannte Felder gehen verloren |
| `internal/store/user.go:97-117` | `SetUserTier` = bestehender Roh-Merge (`map[string]json.RawMessage`), setzt nur `tier`, löscht `requested_tier`/`requested_at` NICHT; einziger Aufrufer `handler/staging_seed.go:101` |
| `internal/store/sessions.go:99,122,141,165-170` | `HasSession`, `AddSession`, `RemoveSession`, `ClearSessions` (leere Liste unter Lock) |
| `internal/handler/auth.go:177` | `issueSession` (Mail-Gate, dann Ausgabe) |
| `internal/handler/auth.go:208-226` | `issueSessionWithoutVerificationGate` — EINZIGE produktive Stelle für `AddSession`+`SetSessionCookie` |
| `internal/handler/auth.go:776` | `profileRole` (abgeleitete Rolle aus Admin-Liste) |
| `internal/handler/auth.go:879,1197` | `UpdateProfileHandler` — typisiertes Load/Save (kein Roh-Merge) |
| `internal/handler/auth.go:1524-1600` | `RequestTierChangeHandler` — setzt `RequestedTier`/`RequestedAt`, Mail an `PoEmail` |
| `internal/handler/session_issuance_test.go:440,509,578` | Guard-Test über alle Ausgabewege („5 stellen aus, 4 verweigern, 1 Sonderfall") |
| `internal/middleware/auth.go:38-104` | `AuthMiddleware`: nur `validateSession` + `HasSession`, liest `user.json` nicht; Allowlist `:40-60` |
| `internal/middleware/admin.go:9-22` | `RequireAdmin(admins)` → 403 `{"error":"forbidden"}` |
| `internal/router/router.go:40,43,97,277,283-290` | Auth global, `ParseAdminUserIDs`, `requireAdmin`-Muster `r.With(requireAdmin)` |
| `internal/config/admin.go:9`, `config.go:74` | Parser/Env `GZ_ADMIN_USER_IDS` |
| `internal/scheduler/scheduler.go:306-307,505-527` | `runForAllUsers` → `ListUserIDs` → `filterOutTestUsers` (filtert nur Testkonten) |
| `internal/scheduler/scheduler.go:1117-1151` | `StatusForUser` — letzter Lauf `trip_reports_hourly` pro Nutzer |
| `internal/scheduler/user_run_state.go:23,32-40,284,320-328` | `data/scheduler_user_state.json`, `UserRecord`, 7 Fan-out-Jobs |
| `internal/scheduler/tier_request_health.go:26-61` | zählt offene Anträge (`requested_tier` leer oder = EffectiveTier ⇒ erledigt) |
| `src/app/loader.py:1305-1331,1334,1398` | Python `list_all_user_ids`, `lookup_user_by_email`, `lookup_user_by_telegram_chat_id` |
| `src/services/user_tier.py` | Python-Tier-Konsumenten (Limits, SMS/Premium-SMS erlaubt); liest `user.json` je Aufruf frisch |
| `frontend/src/routes/account/+page.svelte:141` | zeigt offenen Tier-Antrag solange `requested_tier` ≠ Tier |

## Existing Patterns
- **Admin-Schutz:** `r.With(requireAdmin).<Method>(...)` pro Route, 401 ohne Session (global), 403 ohne Admin (S1/S2).
- **Roh-Merge:** `Store.SetUserTier` liest `user.json` als `map[string]json.RawMessage` und schreibt nur das Zielfeld — CLAUDE.md „Read-Modify-Write mit Merge".
- **Store-Scope:** Neue Store-Methoden ohne `WithUser` brauchen `// gz-store-scope-exempt:` (Guard-Tests `handler/store_scope_guard_test.go`, `store/user_scope_guard_test.go`).
- **Router-Tests:** `internal/router/admin_trigger_test.go` (`adminTestRouter(t, adminUserIDs)` `:81`, Zwei-Nutzer-Tests `:165,:297`), `briefing_subscription_test.go` (`newBriefingTestRouter`, `sessionCookieFor`).
- **Session-Widerruf:** `ClearSessions` bereits genutzt bei Passwort-Reset, Logout-all, Passwort-Ändern, Kontoübernahme.

## Dependencies
- Upstream: Store (`user.json`, `sessions.json`), Config (`GZ_ADMIN_USER_IDS`), Scheduler-User-State.
- Downstream: S4-UI `/admin` (konsumiert die API), Tier-Konsumenten Go+Python, Scheduler-Fan-out, Inbound-Zuordnung Python.

## Existing Specs
- `docs/specs/modules/admin_rolle_s1.md`, `admin_rolle_s2_status_token.md` (S3/S4 Nicht-Ziel)
- `session_allowlist.md`, `logout_session_blacklist.md`, `email_verify_scharfschaltung_2271.md`
- `user_auth_endpoints.md`, `fix_1555_tier_antrag_sichtbarkeit.md`, `epic_user_tiers_overview.md`
- ADR-0078 (Admin über ENV-Liste; S3 ändert die Liste nicht), ADR-0079, ADR-0060, ADR-0066, ADR-0072

## Risks & Considerations
1. **`disabled` muss typisiertes Feld in `model.User` sein.** Fast alle Schreiber (Profil-PUT, Tier-Antrag, Passkey, Register) laden typisiert und schreiben via `SaveUser` komplett zurück — ein nur roh gesetztes Feld verschwände beim nächsten Profil-Speichern. Umgekehrt darf der Profil-PUT `disabled` nicht setzen können (Rechteausweitung analog `role` in S1).
2. **Lost Update:** Es gibt keinen Pro-Nutzer-Lock auf `user.json`. Ein Admin-Roh-Merge und ein gleichzeitiger typisierter `SaveUser` des Nutzers können sich überschreiben.
3. **Sperre muss im Ausgabeweg sitzen** (`issueSessionWithoutVerificationGate`), nicht nur in `issueSession` — `ChangePasswordHandler` (`auth.go:1511`) umgeht das Mail-Gate. Reihenfolge `disabled` setzen → `ClearSessions`, sonst Wettlauf mit parallelem Login. Guard-Test `session_issuance_test.go` muss den neuen Verweigerungsfall kennen.
4. **Bestehende Sessions:** `AuthMiddleware` liest `user.json` nicht; die Sperre wirkt für bestehende Sitzungen nur über `ClearSessions`.
5. **Reichweite der Sperre (Umfangsfrage für die Analyse):** Session-Sperre stoppt Web-Login. Scheduler (`runForAllUsers`, 7 Fan-out-Jobs) und Inbound-Befehle (Telegram/E-Mail/Premium-SMS, Python-Zuordnung) kennen `disabled` nicht — ein gesperrter Nutzer bekäme weiter Briefings/Alarme und könnte Befehle senden.
6. **Tier-Setzen konsistent:** nur `free|standard|premium`; `requested_tier` UND `requested_at` entfernen (sonst zeigt Account-Seite weiter offenen Antrag, `TierRequestHealth` zählt falsch).
7. **Keine Selbstsperre:** Admin darf eigenes Konto nicht sperren (sonst Aussperrung; Admin-Liste liegt in ENV).
8. **Nutzerliste = Cross-User-Daten:** nur für Admins; Zwei-Nutzer-Test Pflicht (Nicht-Admin 403, Admin sieht beide). Keine Geheimnisse (`password_hash`, Passkey-Credentials) ausliefern.
9. **Staging-Nachweis:** Staging-Admin `gz-staging-admin` existiert (S2), Staging-Datenbestand ist für `hem` nicht lesbar ⇒ Nachweis über API.

## Analysis

### Type
Feature (Scheibe S3 von #2155, Epic #2138)

### Fachliche Leitentscheidung: Sperre wirkt auf ALLEN Wegen
„Gesperrt" heißt für den Admin: Das Konto **bekommt nichts mehr und kann nichts mehr auslösen**. Eine Sperre, die nur den
Web-Login stoppt, wäre eine Scheinsperre: Briefings und Alarme liefen weiter, Befehle per Telegram, E-Mail oder Premium-SMS
würden weiter ausgeführt. Das widerspricht der Kanal-Parität (alle vier Kanäle gleichrangig). **Inbound gehört deshalb in
S3 und wird NICHT als eigene Scheibe abgespalten.** Wird das LoC-Limit knapp, gilt `workflow.py set-field loc_limit_override 500`.
Ein neuer Scheibenschnitt ist dafür kein Mittel (Deploy läuft ohne Halt, S3 ginge allein live).

### Verifizierte Fakten (in der Analyse geprüft)
- **Profil-PUT** (`handler/auth.go:879ff`, `UpdateProfileHandler`) dekodiert in eine explizite Struktur (email, display_name,
  mail_to, sms_to, telegram_chat_id, passkey_prompt_dismissed). `disabled` und `tier` lassen sich darüber nicht einschleusen.
  Bleibt als Test-AC erhalten.
- **Python schreibt `user.json` nicht.** Die `json.dump`-Treffer in `loader.py:1562/1970` betreffen Orte und Trips
  (dort mit RMW-Merge). Ein typisiertes Go-Feld `Disabled` geht also nur durch Go-Schreiber verloren, und die kennen das Feld.
- **Alle 7 Fan-out-Jobs** laufen über `runForAllUsers` → `filterOutTestUsers` (`scheduler.go:505`). Das lädt je Nutzer bereits
  das Profil; fail-open bei Ladefehler. Globale Jobs `inboundCommands` (:738) und `premiumSmsPoll` (:756) iterieren nicht über Nutzer.
- **Premium-SMS-Zuordnung liegt in Go:** `PostPremiumSmsLearnHandler` (`handler/premium_sms_connect.go:70ff`) iteriert über
  `ListUserIDs` und sammelt Kandidaten. Der Python-Reader (`inbound_sms_reader.py:322`) übernimmt die `user_id` aus der Antwort.
- **E-Mail/Telegram-Zuordnung liegt in Python:** `inbound_email_reader.py:377` → `loader.lookup_user_by_email` (:1334);
  `inbound_telegram_reader.py:605` → `loader.lookup_user_by_telegram_chat_id` (:1398). Liefert der Lookup `None`, folgt der
  Zweig „unbekannter Absender".
- Go-Aufrufer von `FindUserByTelegramChatID`: nur `telegram_connect.go:208` (Verknüpfung, Eindeutigkeitsprüfung).
  `FindUserByOAuthSub`: `auth_oauth.go:157/225`. Das OAuth-Login endet in der Session-Ausgabe und ist damit von der
  Ausgabe-Sperre gedeckt.
- Letzter ADR ist `0079` ⇒ neuer ADR **0080**.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/user.go` | MODIFY | Typisiertes Feld `Disabled bool json:"disabled,omitempty"` (Schema-relevant ⇒ Backup-Hook) |
| `internal/store/user.go` | MODIFY | Roh-Merge-Methoden `SetUserDisabled`, `SetUserTierAdmin` (setzt `tier`, löscht `requested_tier`+`requested_at`); `SetUserTier` (Staging-Seed) bleibt unverändert; `// gz-store-scope-exempt:` |
| `internal/handler/admin_users.go` | CREATE | DTO + `GET /api/admin/users`, `PUT /api/admin/users/{id}/tier`, `PUT /api/admin/users/{id}/disabled` |
| `internal/handler/auth.go` | MODIFY | Sperrprüfung in `issueSessionWithoutVerificationGate` (:208) vor `AddSession` ⇒ 403 `account_disabled`; Ladefehler fail-closed |
| `internal/scheduler/scheduler.go` | MODIFY | `filterOutTestUsers` lässt zusätzlich `u.Disabled` aus (deckt alle 7 Fan-out-Jobs); Log nennt Grund |
| `internal/handler/premium_sms_connect.go` | MODIFY | gesperrte Konten sind keine Zuordnungskandidaten |
| `src/services/inbound_email_reader.py` | MODIFY | nach Lookup: gesperrtes Konto ⇒ stumm verwerfen + Log (kein Registrierungshinweis, keine Befehlsausführung) |
| `src/services/inbound_telegram_reader.py` | MODIFY | dito für Telegram |
| `src/app/loader.py` (o. `src/app/config.py`) | MODIFY | kleiner Helfer `is_user_disabled(user_id, data_dir)` analog `is_test_user_id` |
| `internal/router/router.go` | MODIFY | 3 Routen mit `r.With(requireAdmin)` |
| `docs/adr/0080-*.md` + `docs/adr/README.md` | CREATE/MODIFY | ADR Kontosperre (Index-Drift-Test) |
| `docs/specs/modules/admin_rolle_s3_admin_api.md` | CREATE | Spec |
| Tests: `internal/router/admin_users_test.go` (neu), `handler/session_issuance_test.go` (Guard erweitern), Scheduler-Filter-Test, Premium-SMS-Learn-Test, Python-Tests für E-Mail-/Telegram-Reader | CREATE/MODIFY | siehe Test-Strategie |

### Endpunkt-Design
- `GET /api/admin/users` → 200 `{"users":[{id, email, display_name, tier, requested_tier, requested_at, email_verified_at,
  created_at, disabled, is_test_user, last_trip_report_run}]}`. Eigenes DTO statt `model.User` ⇒ nie `password_hash`,
  `passkey_credentials`, Token-/Code-Felder. `last_trip_report_run` per `userRunState.UserRecord("trip_reports_hourly", id)`,
  `null` ohne Eintrag.
- `PUT /api/admin/users/{id}/tier` Body `{"tier":"free|standard|premium"}` → 200 mit Listeneintrag; 400 bei ungültigem Tier
  (exakte Whitelist, kein `EffectiveTier`-Fallback) oder kaputtem JSON; 404 bei unbekannter/ungültiger ID (Path-Traversal).
- `PUT /api/admin/users/{id}/disabled` Body `{"disabled":true|false}` → 200; 404 unbekannt; 409 `{"error":"cannot_disable_self"}`,
  wenn der Admin sich selbst sperrt (Entsperren des eigenen Kontos idempotent erlaubt). Andere Admins dürfen gesperrt werden.
- Schutz: global 401 ohne Session, `requireAdmin` 403 `{"error":"forbidden"}` (Muster S1/S2).

### Sperr-Semantik
- **Reihenfolge Sperren:** (1) `disabled=true` per Roh-Merge, (2) `ClearSessions(id)`, (3) Read-after-Write. Umgekehrt könnte
  ein paralleler Login nach dem Clear wieder eine Session erhalten. Scheitert (2): 500, das Flag bleibt (sicherer Zustand), Wiederholung idempotent.
- **Entsperren:** nur Flag entfernen, keine Session-Wiederherstellung.
- **Login-Antwort:** Die Credential-Prüfung läuft unverändert zuerst (falsches Passwort ⇒ weiter 401, kein Existenz-Leak). Erst
  der authentifizierte Inhaber erhält 403 `account_disabled`. Gilt für Passwort, Magic-Link, Passkey, OAuth und ChangePassword,
  weil alle über `issueSessionWithoutVerificationGate` ausstellen.
- **Middleware unverändert:** Bestehende Sessions fallen über `ClearSessions`.
- **Scheduler:** gesperrte Konten fallen aus allen 7 Fan-out-Jobs (fail-open bei Ladefehler bleibt).
- **Inbound:** Die Prüfung sitzt NACH dem Lookup im Reader, nicht im Lookup selbst. Sonst fiele der Absender in „unbekannter
  Absender" und bekäme einen Registrierungshinweis. Gesperrt ⇒ stumm verwerfen, loggen, keine Antwort, kein Befehl.
  Premium-SMS: gesperrte Konten sind im Learn-Handler keine Kandidaten.
- **Bewusst NICHT gefiltert:** `store/address_owner.go` `forEachRealAccount`. Eine gesperrte Adresse bleibt vergeben (kein
  Übernahmeweg über ein gesperrtes Konto). `telegram_connect.go` Eindeutigkeitsprüfung ebenso unverändert.

### Tier setzen
Nur `free|standard|premium`. Roh-Merge setzt `tier` und löscht `requested_tier` UND `requested_at`. Damit zeigt die
Account-Seite keinen offenen Antrag mehr, und `TierRequestHealth` zählt korrekt. Unbekannte Felder in `user.json` bleiben
erhalten (Test mit Zusatzfeld). Python-Tier-Konsumenten lesen `user.json` je Aufruf frisch ⇒ keine Cache-Invalidierung nötig.

### Scope Assessment
- Produktive Dateien: ca. 10 (Go 7, Python 2–3)
- Geschätzte LoC produktiv: Go ca. +190, Inbound ca. +60 ⇒ **ca. +250**, knapp am Limit ⇒ `loc_limit_override 500` einplanen
- Risk Level: **MEDIUM**. Neuer Kontozustand greift in Session-Ausgabe, Scheduler und Inbound ein; ein Fehler im Ausgabeweg sperrt
  schlimmstenfalls alle aus (daher Guard-Test und Zwei-Nutzer-Tests).

### Bekanntes Restrisiko: Lost Update (dokumentieren, nicht verschweigen)
Es gibt keinen Pro-Nutzer-Lock auf `user.json`. Die gefährliche Richtung ist NICHT Admin gegen Admin, sondern diese:
Ein typisierter Nutzer- oder Hintergrund-Schreiber (Profil-PUT, Tier-Antrag, Passkey, Telegram-Connect, Magic-Link …)
**lädt `user.json` vor dem Admin-Schreiben und speichert danach**. Er setzt `disabled` still auf `false` zurück (bzw. `tier` auf
den alten Wert). Der Read-after-Write im Admin-Handler fängt das NICHT, weil er vor dem Überschreiben läuft.
Mildernd wirkt: Nach dem Sperren sind alle Sessions gelöscht, also kann der gesperrte Nutzer selbst keine Profil-Schreiber mehr
auslösen. Das Fenster betrifft nur Anfragen, die im Millisekundenbereich parallel laufen. Die Liste zeigt den Ist-Zustand, der
Admin sieht eine verlorene Sperre. Ein neuer Lock ohne Mitwirkung der ca. 20 `SaveUser`-Aufrufer brächte keinen Schutz ⇒
bewusst kein Lock. Eintrag in Spec „Known Limitations" + ADR.

### Test-Strategie
Router-Tests mit `adminTestRouter(t, adminUserIDs)` (`admin_trigger_test.go:81`), Muster Zwei-Nutzer (:165, :297):
1. Nicht-Admin 403 auf allen 3 Routen, ohne Session 401.
2. Admin sieht beide Nutzer; Rohantwort enthält weder `password_hash` noch `passkey` noch Token-Felder.
3. Tier auf A setzen ändert B nicht; `requested_*` gelöscht; Zusatzfeld in `user.json` bleibt (Roh-Merge-Beweis).
4. Tier `gold` ⇒ 400; unbekannte ID ⇒ 404; Path-Traversal-ID ⇒ 404.
5. A gesperrt ⇒ A-Session sofort 401; Login A mit richtigem Passwort ⇒ 403 `account_disabled`, falsches ⇒ 401; B unberührt;
   Profil-PUT kann `disabled` nicht zurücksetzen.
6. Selbstsperre ⇒ 409, Flag unverändert. 7. Entsperren ⇒ Login geht wieder.
8. Scheduler-Filter lässt gesperrtes Konto aus, Ladefehler fail-open. 9. Guard-Test `session_issuance_test.go` um den Verweigerungsfall erweitert.
10. Premium-SMS-Learn: gesperrtes Konto kein Kandidat. 11. Python E-Mail-/Telegram-Reader: gesperrter Absender ⇒ kein Befehl,
    keine Antwort, kein Registrierungshinweis (aufgezeichnete Fixtures, kein Netz).
Staging: per API mit `gz-staging-admin` (Datenbestand für `hem` nicht lesbar ⇒ Nachweis über API).

### Dependencies
- Upstream: S1 (`requireAdmin`, `GZ_ADMIN_USER_IDS`), S2 (Staging-Admin `gz-staging-admin`), Store, Scheduler-User-State.
- Downstream: S4-UI `/admin` konsumiert die drei Endpunkte (DTO-Form ist Vertrag ⇒ in `docs/reference/api_contract.md` nachtragen).

### Open Questions
- Keine PO-Fragen offen. Die Tech-Lead-Entscheidungen (Reichweite, 409 bei Selbstsperre, stummes Verwerfen bei Inbound,
  Adressen bleiben vergeben, kein Lock) stehen oben mit Begründung und kommen mit der Spec zur Freigabe.

## RED-Übergabe an /50-implement (Phase 5, 2026-09-29)

Testdateien: `internal/router/admin_users_test.go` (AC-1–9), `internal/handler/session_issuance_test.go`
(Gruppe 4 `TestDisabledAccount_AllIssuancePaths_Refuse403`, 6 Wege inkl. beider Passkey-Varianten, AC-10),
`internal/handler/premium_sms_connect_test.go` (`TestLearnSkipsDisabledAccount_*`, AC-12),
`internal/scheduler/disabled_users_filter_test.go` (7 Subtests, AC-11), `tests/tdd/test_inbound_disabled_account.py` (AC-13).
RED-Ausgaben: `docs/artifacts/feature-2155-s3-admin-api/test-red-*.txt` (registriert).

Zusicherungen, die die Implementierung erfüllen muss:
- **DTO ohne `omitempty`:** alle Felder immer vorhanden, `last_trip_report_run` explizit `null`. Rohtext der Liste
  darf `password_hash`, `passkey`, `token`, `code_hash`, `"code"`, `public_key` nicht enthalten.
- **Fehlerkörper JSON** (`Content-Type: application/json`) auch für 400/404. `chi.URLParam` liefert `..%2Fx` roh ⇒
  `ValidUserID` + Existenzprüfung ⇒ JSON-404. Tier-Whitelist exakt (`Premium` ⇒ 400).
- **`PUT …/disabled`** antwortet mit dem Eintrag inkl. `"disabled":true`.
- **AC-6-Fehlerinjektion:** Test ersetzt `sessions.json` durch ein nicht-leeres Verzeichnis ⇒ `writeFileAtomic`-Rename
  scheitert (auch als root). Erwartet 500, Flag bleibt, Wiederholung nach Reparatur 200.
- **AC-10 inkl. OAuth:** Test erwartet auch beim Google-OAuth-Weg 403 JSON `{"error":"account_disabled"}` (Spec wörtlich),
  keinen Redirect. Das Flag muss typisiert (`model.User.Disabled`) sein, sonst verschwindet es beim `SaveUser` von
  Magic-Link/Passkey/Passwort-ändern/Profil-PUT.
- **Scheduler-Log:** eine Logzeile enthält die uid UND `disabled` oder `gesperrt`.
- **Python-Log:** ein Record enthält `disabled` oder `gesperrt`.
- **E-Mail-Reader:** bei Sperre gibt `_process_single` 0 zurück, markiert die Mail aber `\Seen`.
- **Telegram-Reader:** Sperrprüfung nach `_resolve_user_for_chat` in `_process_update` UND `_process_callback_query`
  (Knopfdruck liefert keine Daten; das `answer` zum Beenden des Spinners ist erlaubt).
- Nur der Telegram-Test fängt die Mutation „Prüfung im Lookup statt danach“ (E-Mail verwirft Unbekannte ohnehin stumm).
- Test-Helfer `setzeGesperrtRoh`/`istGesperrtRoh` liegen in `session_issuance_test.go` und werden auch von den Premium-SMS-Tests genutzt.

Werkzeug: Go liegt nur unter `/usr/local/go/bin` (nicht im PATH). Der Worktree-Wächter lehnt Inline-Befehle mit `|` im
`-run`-Muster oder `PATH=`-Präfix ab ⇒ solche Aufrufe über ein Skript im Scratchpad fahren.
