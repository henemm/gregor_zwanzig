---
entity_id: admin_rolle_s3_admin_api
type: module
created: 2026-09-29
updated: 2026-09-29
status: draft
version: "1.0"
tags: [admin, auth, tier, kontosperre, scheduler, inbound, epic-2138]
---

# Admin-Rolle S3: Admin-API (Nutzerliste, Tier setzen, Konto sperren)

## Approval

- [ ] Approved

## Purpose

Ein Admin kann heute weder sehen, welche Nutzer es gibt, noch deren Tier ändern oder ein
Konto sperren. Diese Scheibe liefert drei geschützte Endpunkte unter `/api/admin/users`
(Liste, Tier setzen, Sperren/Entsperren). Die Sperre ist keine Scheinsperre: Ein
gesperrtes Konto bekommt keine Session mehr, keine Briefings/Alarme und kann keine
Befehle per E-Mail, Telegram oder Premium-SMS auslösen. Scheibe S3 von vier in Issue
#2155 (Epic #2138); baut auf S1 (Admin-Rolle, ADR-0078) und S2 (Status-Token, ADR-0079) auf.

## Source

- **File:** `internal/model/user.go`, `internal/store/user.go`,
  `internal/handler/admin_users.go` (neu), `internal/handler/auth.go`,
  `internal/handler/premium_sms_connect.go`, `internal/scheduler/scheduler.go`,
  `internal/router/router.go`, `src/services/inbound_email_reader.py`,
  `src/services/inbound_telegram_reader.py`, `src/app/loader.py`
- **Identifier:** `model.User.Disabled` (neu), `Store.SetUserDisabled` (neu),
  `Store.SetUserTierAdmin` (neu), `handler.AdminListUsersHandler` /
  `AdminSetUserTierHandler` / `AdminSetUserDisabledHandler` (neu),
  `issueSessionWithoutVerificationGate` (erweitert), `filterOutTestUsers` (erweitert),
  `loader.is_user_disabled` (neu)

> **Schicht-Hinweis:** Go-API (Kern der Scheibe) plus Python-Core (nur die beiden
> Inbound-Reader und ein Loader-Helfer). Kein Frontend (S4). `model/user.go` und
> `store/user.go` sind schema-relevant ⇒ der Pre-Snapshot-Hook `data_schema_backup.py`
> löst bei den Edits automatisch aus.

## Scope

### Ziele

- Nutzerliste, Tier setzen, Konto sperren/entsperren nur für Admins.
- Sperre wirkt auf allen Wegen: Session-Ausgabe (alle fünf Ausgabewege),
  bestehende Sitzungen, Scheduler (alle 7 Fan-out-Jobs), Premium-SMS-Zuordnung,
  E-Mail- und Telegram-Inbound.

### Nicht-Ziele

- **`/admin`-UI ist S4**, nicht Teil dieser Scheibe. Die DTO-Form ist der Vertrag für S4.
- **Die Admin-Liste in `GZ_ADMIN_USER_IDS` bleibt unverändert** (ADR-0078): S3 legt
  keine Admins an und entzieht keine Adminrechte, sondern sperrt nur Konten.
- Kein neuer Lock auf `user.json` (siehe Known Limitations).
- Keine Änderung an `address_owner` und der Telegram-Eindeutigkeitsprüfung (siehe Known Limitations).

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `internal/model/user.go` | MODIFY | Typisiertes Feld `Disabled bool json:"disabled,omitempty"` |
| `internal/store/user.go` | MODIFY | Roh-Merge-Methoden `SetUserDisabled`, `SetUserTierAdmin` (setzt `tier`, löscht `requested_tier` und `requested_at`); bestehendes `SetUserTier` (Staging-Seed) unverändert; `// gz-store-scope-exempt:` |
| `internal/handler/admin_users.go` | CREATE | DTO + drei Handler |
| `internal/handler/auth.go` | MODIFY | Sperrprüfung in `issueSessionWithoutVerificationGate` vor `AddSession` ⇒ 403 `account_disabled`; Ladefehler fail-closed |
| `internal/scheduler/scheduler.go` | MODIFY | `filterOutTestUsers` lässt zusätzlich gesperrte Konten aus; Log nennt den Grund |
| `internal/handler/premium_sms_connect.go` | MODIFY | Gesperrte Konten sind im Learn-Handler keine Kandidaten |
| `src/app/loader.py` | MODIFY | Helfer `is_user_disabled(user_id, data_dir)` analog `is_test_user_id` |
| `src/services/inbound_email_reader.py` | MODIFY | Nach dem Lookup: gesperrt ⇒ stumm verwerfen + Log |
| `src/services/inbound_telegram_reader.py` | MODIFY | dito für Telegram |
| `internal/router/router.go` | MODIFY | Drei Routen mit `r.With(requireAdmin)` |
| `docs/adr/0080-kontosperre.md`, `docs/adr/README.md` | CREATE/MODIFY | ADR Kontosperre + Index (Index-Drift-Test) |
| `docs/reference/api_contract.md` | MODIFY | DTO und drei Endpunkte nachtragen |
| Tests | CREATE/MODIFY | siehe Test Plan |

### Estimated Changes

- Files: ca. 10 produktiv (Go 7, Python 3) plus Tests und Doku
- LoC: ca. +250 produktiv (Go ca. +190, Inbound ca. +60), knapp am Limit von 250 ⇒
  `workflow.py set-field loc_limit_override 500` ist eingeplant; `docs/`/`*.md` zählen nicht.
  Ein Abspalten des Inbound-Teils als eigene Scheibe ist ausdrücklich KEIN Mittel
  (Deploy läuft ohne Halt, S3 ginge sonst als Scheinsperre allein live).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware/admin.go` (`RequireAdmin`) | dependency | 403 `{"error":"forbidden"}` für Nicht-Admins (S1) |
| `internal/router/router.go` (`r.With(requireAdmin)`) | reference-pattern | Routen-Schutzmuster aus S1/S2 |
| `internal/store/user.go` (`ListUserIDs`, `SetUserTier`) | dependency | Grundlage der Liste; `SetUserTier` ist das Vorbild für den Roh-Merge |
| `internal/store/sessions.go` (`ClearSessions`) | dependency | Widerruf bestehender Sitzungen beim Sperren |
| `internal/handler/auth.go` (`issueSessionWithoutVerificationGate`) | dependency | Einzige produktive Stelle für `AddSession` + `SetSessionCookie` |
| `internal/scheduler/user_run_state.go` (`UserRecord`) | dependency | `last_trip_report_run` je Nutzer (aus S2) |
| `internal/handler/session_issuance_test.go` | dependency | Guard-Test über alle Ausgabewege |
| `internal/router/admin_trigger_test.go` (`adminTestRouter`) | reference-pattern | Zwei-Nutzer-Router-Tests |
| `src/app/loader.py` (`lookup_user_by_email`, `lookup_user_by_telegram_chat_id`) | dependency | Nutzerzuordnung im Inbound; bleibt unverändert |
| ADR-0078 / ADR-0079 | reference-pattern | Admin-Begriff, fail-closed-Muster |
| ADR-0080 (neu) | new | Kontosperre: Reichweite, Reihenfolge, Restrisiko |

## API-Vertrag

Schutz für alle drei Routen: ohne Session 401 (globale `AuthMiddleware`), ohne Admin
403 `{"error":"forbidden"}` (`requireAdmin`).

**`GET /api/admin/users`** → 200:

```json
{"users":[{"id":"alice","email":"alice@example.org","display_name":"Alice",
  "tier":"free","requested_tier":"premium","requested_at":"2026-09-20T08:00:00Z",
  "email_verified_at":"2026-09-01T10:00:00Z","created_at":"2026-09-01T09:58:00Z",
  "disabled":false,"is_test_user":false,
  "last_trip_report_run":{"time":"2026-09-29T05:00:00Z","status":"ok","error":""}}]}
```

Eigenes DTO, nicht `model.User`: nie `password_hash`, `passkey_credentials`, Token-/Code-Felder.
`last_trip_report_run` ist `null` ohne Eintrag im Nutzer-Laufzustand.

**`PUT /api/admin/users/{id}/tier`**, Body `{"tier":"free|standard|premium"}` → 200 mit dem
aktualisierten Listeneintrag. 400 bei ungültigem Tier (exakte Whitelist, kein
`EffectiveTier`-Fallback) oder kaputtem JSON; 404 bei unbekannter oder ungültiger ID
(Path-Traversal).

**`PUT /api/admin/users/{id}/disabled`**, Body `{"disabled":true|false}` → 200 mit dem
aktualisierten Listeneintrag. 404 bei unbekannter ID. 409 `{"error":"cannot_disable_self"}`,
wenn der Admin sein eigenes Konto sperren will (eigenes Entsperren ist idempotent erlaubt,
andere Admins dürfen gesperrt werden). Scheitert `ClearSessions`: 500, das Flag bleibt
gesetzt (sicherer Zustand), Wiederholung ist idempotent.

**Login-Verweigerung:** 403 `{"error":"account_disabled"}` an der Session-Ausgabe.

## Implementation Details

1. **Modell.** `Disabled` ist ein typisiertes Feld in `model.User`. Fast alle Schreiber
   (Profil-PUT, Tier-Antrag, Passkey, Register) laden typisiert und schreiben per `SaveUser`
   komplett zurück; ein nur roh gesetztes Feld verschwände beim nächsten Profil-Speichern.
   Der Profil-PUT dekodiert in eine explizite Struktur (email, display_name, mail_to, sms_to,
   telegram_chat_id, passkey_prompt_dismissed) und kann `disabled` weder setzen noch
   zurücksetzen. Python schreibt `user.json` nicht.
2. **Roh-Merge.** `SetUserDisabled` und `SetUserTierAdmin` lesen `user.json` als
   `map[string]json.RawMessage` und schreiben nur die Zielfelder (CLAUDE.md „Read-Modify-Write
   mit Merge"). Unbekannte Felder bleiben erhalten. `SetUserTierAdmin` setzt `tier` und löscht
   `requested_tier` UND `requested_at`; sonst zeigt die Konto-Seite weiter einen offenen Antrag
   und `TierRequestHealth` zählt falsch. Python-Tier-Konsumenten lesen `user.json` je Aufruf
   frisch, eine Cache-Invalidierung ist nicht nötig.
3. **Sperren, Reihenfolge.** (1) `disabled=true` per Roh-Merge, (2) `ClearSessions(id)`,
   (3) Read-after-Write zur Bestätigung. Umgekehrt könnte ein paralleler Login nach dem Clear
   wieder eine Session erhalten. Die Middleware bleibt unverändert: bestehende Sitzungen fallen
   über `ClearSessions`, da `AuthMiddleware` `user.json` nicht liest.
4. **Entsperren.** Nur das Flag entfernen, keine Session-Wiederherstellung; der Nutzer meldet sich neu an.
5. **Ausgabe-Sperre.** `issueSessionWithoutVerificationGate` prüft nach der Credential-Prüfung
   und vor `AddSession` das Flag. Falsches Passwort bleibt 401 (kein Existenz-Leak), erst der
   authentifizierte Inhaber erhält 403 `account_disabled`. Da Passwort, Magic-Link, Passkey,
   OAuth und `ChangePasswordHandler` (umgeht das Mail-Gate) alle hier ausstellen, deckt EINE
   Prüfung alle Wege. Ladefehler ⇒ fail-closed (keine Session).
6. **Scheduler.** `runForAllUsers` läuft für alle 7 Fan-out-Jobs über `filterOutTestUsers`, das je
   Nutzer bereits das Profil lädt. Dort fallen gesperrte Konten zusätzlich heraus; Ladefehler
   bleibt fail-open (wie bisher). Die globalen Jobs `inboundCommands` und `premiumSmsPoll`
   iterieren nicht über Nutzer und bleiben unverändert.
7. **Premium-SMS.** `PostPremiumSmsLearnHandler` sammelt Kandidaten über `ListUserIDs`; gesperrte
   Konten werden übersprungen. Der Python-SMS-Reader übernimmt die `user_id` aus der Antwort.
8. **E-Mail-/Telegram-Inbound.** Die Prüfung sitzt NACH dem Lookup im Reader, nicht im Lookup
   selbst; sonst fiele der Absender in den Zweig „unbekannter Absender" und bekäme einen
   Registrierungshinweis. Gesperrt ⇒ stumm verwerfen, loggen, kein Befehl, keine Antwort.
   Der Helfer `loader.is_user_disabled` liest `user.json` frisch (Muster `is_test_user_id`).
9. **Router.** Drei Routen mit `r.With(requireAdmin)`; `{id}` wird gegen `ListUserIDs`/gültige
   ID-Form geprüft ⇒ Path-Traversal liefert 404.

## Test Plan

Keine Mocks (Mock-Theater verboten); Router-Tests über den echten Router mit
`adminTestRouter(t, adminUserIDs)` und Zwei-Nutzer-Muster; Python-Tests mit aufgezeichneten,
versionierten Fixtures ohne Netz. Testdateien nach Verhalten benannt.

| Testdatei | Art | Deckt |
|-----------|-----|-------|
| `internal/router/admin_users_test.go` (neu) | Kern, echter Router, zwei Nutzer | AC-1 bis AC-9 |
| `internal/handler/session_issuance_test.go` (erweitern) | Kern, Guard | AC-10 |
| `internal/scheduler/disabled_users_filter_test.go` (neu) | Kern | AC-11 |
| `internal/handler/premium_sms_connect_test.go` (erweitern) | Kern | AC-12 |
| `tests/tdd/test_inbound_disabled_account.py` (neu) | Kern, Fixtures, `--disable-socket` | AC-13 |

**Mutations-Gegenprobe (Pflicht für den Adversary):** Sperrprüfung in
`issueSessionWithoutVerificationGate` entfernt ⇒ AC-7/AC-10 rot; `ClearSessions` entfernt ⇒
AC-6 rot; Löschen von `requested_at` entfernt ⇒ AC-3 rot; Filter in `filterOutTestUsers`
entfernt ⇒ AC-11 rot; Prüfung im Reader entfernt ⇒ AC-13 rot; Prüfung vor dem Lookup statt
danach ⇒ AC-13 (Registrierungshinweis) rot. Mutation nur per String-Ersetzung mit externer
Sicherungskopie.

**Staging-Nachweis:** per API mit dem Staging-Admin `gz-staging-admin` (aus S2,
`.claude/staging_admin.env`); der Staging-Datenbestand ist für `hem` nicht lesbar, daher
Nachweis über die Antworten der drei Endpunkte plus Login-Versuch eines Test-Kontos
(gesperrt ⇒ 403, entsperrt ⇒ 200). Nicht Messbares wird als `NOT_MEASURABLE_ON_STAGING`
gemeldet, kein PASS erfunden. Keine Sammelversände über echte Nutzer.

## Expected Behavior

- **Input:** Admin-Session mit drei Routen; Nicht-Admin- und Anonym-Aufrufe; Login-Versuche
  gesperrter Konten; eingehende E-Mails/Telegram-Nachrichten gesperrter Absender.
- **Output:** siehe API-Vertrag; Sperre ⇒ 401 auf bestehende Sitzung, 403 `account_disabled` beim Login.
- **Side effects:** `user.json` erhält `disabled` bzw. geändertes `tier` (ohne
  `requested_tier`/`requested_at`); `sessions.json` des gesperrten Nutzers wird geleert. Keine Migration:
  `omitempty` lässt Bestandsdaten unverändert.

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer, davon ein Admin (Kennung in `GZ_ADMIN_USER_IDS`) / When die
  Routen `GET /api/admin/users`, `PUT /api/admin/users/{id}/tier` und
  `PUT /api/admin/users/{id}/disabled` ohne Sitzung bzw. mit der Sitzung des Nicht-Admins
  aufgerufen werden / Then antwortet der Server ohne Sitzung mit 401 und für den Nicht-Admin mit
  403 `{"error":"forbidden"}` — auf allen drei Routen, und es ändert sich kein Datensatz.
  - Test: `internal/router/admin_users_test.go`

- **AC-2:** Given zwei angelegte Nutzer mit Passwort-Hash und Passkey-Daten / When der Admin
  `GET /api/admin/users` aufruft / Then enthält die Antwort beide Nutzer mit den Feldern
  `id`, `email`, `display_name`, `tier`, `requested_tier`, `requested_at`, `email_verified_at`,
  `created_at`, `disabled`, `is_test_user`, `last_trip_report_run` (`null` ohne Lauf), und der
  Rohtext der Antwort enthält weder `password_hash` noch `passkey` noch Token-/Code-Felder.
  - Test: `internal/router/admin_users_test.go`

- **AC-3:** Given Nutzer A hat einen offenen Tier-Antrag (`requested_tier`, `requested_at`) und
  in `user.json` steht ein unbekanntes Zusatzfeld / When der Admin das Tier von A auf `premium`
  setzt / Then hat A Tier `premium`, `requested_tier` UND `requested_at` sind aus `user.json`
  entfernt, das Zusatzfeld ist unverändert vorhanden (Roh-Merge), und Nutzer B behält sein
  bisheriges Tier unverändert.
  - Test: `internal/router/admin_users_test.go` (Zwei-Nutzer-Test, Roh-Datei-Vergleich)

- **AC-4:** Given ein Admin und ein bestehender Nutzer / When das Tier `gold` gesetzt wird,
  der JSON-Body kaputt ist, oder die ID unbekannt bzw. eine Path-Traversal-ID (`../x`) ist /
  Then antwortet der Server bei `gold` und kaputtem JSON mit 400, bei unbekannter oder
  Path-Traversal-ID mit 404, und es wird nichts geschrieben.
  - Test: `internal/router/admin_users_test.go`

- **AC-5:** Given Nutzer A hat eine gültige Sitzung / When der Admin A sperrt / Then
  antwortet der Server auf die bisherige Sitzung von A sofort mit 401, die Liste zeigt
  `disabled: true` für A, und Nutzer B mit eigener Sitzung ist unberührt (weiter 200).
  - Test: `internal/router/admin_users_test.go`

- **AC-6:** Given der Admin sperrt Nutzer A / When die Reihenfolge der Schritte geprüft wird /
  Then ist `disabled` zuerst gesetzt und erst danach `ClearSessions` ausgeführt; scheitert
  `ClearSessions`, antwortet der Server mit 500 und das Flag bleibt gesetzt, und ein
  wiederholter Aufruf ist idempotent und liefert 200.
  - Test: `internal/router/admin_users_test.go` (Store-Fehlerinjektion über echtes,
    schreibgeschütztes Sessions-Verzeichnis)

- **AC-7:** Given Nutzer A ist gesperrt / When A sich mit richtigem Passwort anmeldet / Then
  antwortet der Server mit 403 `{"error":"account_disabled"}` und setzt keinen Sitzungscookie;
  bei falschem Passwort antwortet er weiterhin mit 401 (kein Hinweis auf die Sperre).
  - Test: `internal/router/admin_users_test.go`

- **AC-8:** Given Nutzer A ist gesperrt / When A versucht, per Profil-PUT (auch mit
  mitgeschicktem Feld `disabled:false`) sein Konto zu ändern, oder der Admin Nutzer A wieder
  entsperrt / Then bleibt `disabled` durch den Profil-PUT unverändert (kein Zurücksetzen,
  kein Setzen), und nach dem Entsperren durch den Admin gelingt der Login wieder (200), ohne
  dass eine frühere Sitzung wiederhergestellt wird (alte Sitzung weiter 401).
  - Test: `internal/router/admin_users_test.go`

- **AC-9:** Given ein Admin / When er sein eigenes Konto sperren will / Then antwortet der Server
  mit 409 `{"error":"cannot_disable_self"}` und das Flag bleibt unverändert; sein eigenes
  Entsperren ist idempotent erlaubt (200), und ein anderer Admin ist sperrbar (200).
  - Test: `internal/router/admin_users_test.go`

- **AC-10:** Given die fünf Wege der Session-Ausgabe (Passwort, Magic-Link, Passkey, OAuth,
  Passwort ändern) / When das Konto gesperrt ist / Then verweigert jeder dieser Wege die Ausgabe
  mit 403 `account_disabled`, weil alle über `issueSessionWithoutVerificationGate` laufen; der
  Guard-Test `session_issuance_test.go` kennt den neuen Verweigerungsfall und wird rot, wenn
  eine Stelle `AddSession` an der Sperrprüfung vorbei aufruft.
  - Test: `internal/handler/session_issuance_test.go` (erweitert)

- **AC-11:** Given ein gesperrtes und ein aktives Konto / When einer der 7 Fan-out-Jobs des
  Schedulers über die Nutzer läuft / Then wird für das gesperrte Konto nichts ausgeliefert
  und der Log nennt den Grund; kann das Profil eines Nutzers nicht geladen werden, bleibt er
  im Lauf (fail-open, wie bisher).
  - Test: `internal/scheduler/disabled_users_filter_test.go`

- **AC-12:** Given ein gesperrtes und ein aktives Konto mit passendem Lernkandidaten / When
  der Premium-SMS-Learn-Handler die Zuordnung sucht / Then ist das gesperrte Konto kein
  Kandidat und wird dem eingehenden Absender nicht zugeordnet.
  - Test: `internal/handler/premium_sms_connect_test.go` (erweitert)

- **AC-13:** Given ein gesperrter Nutzer mit bekannter E-Mail-Adresse bzw. Telegram-Chat-ID
  / When der E-Mail- bzw. Telegram-Reader eine Nachricht dieses Absenders mit einem Befehl
  verarbeitet (aufgezeichnete Fixtures, kein Netz) / Then wird die Nachricht stumm verworfen
  und geloggt, es wird kein Befehl ausgeführt, keine Antwort gesendet und KEIN
  Registrierungshinweis verschickt; ein aktiver Absender wird weiterhin normal bedient.
  - Test: `tests/tdd/test_inbound_disabled_account.py`

- **AC-14:** Given der Staging-Stand dieser Scheibe / When mit `gz-staging-admin` per API
  Liste, Tier-Setzen und Sperren/Entsperren eines Test-Kontos ausgeführt werden / Then
  entspricht die Antwortmatrix (401/403/200, gesperrt ⇒ Login 403, entsperrt ⇒ Login 200)
  den ACs 1 bis 9, und nicht messbare Punkte sind als `NOT_MEASURABLE_ON_STAGING` benannt.
  - Test: manueller Nachweis im Deploy-Schritt (`/e2e-verify`)

## Known Limitations

- **Lost Update (Restrisiko, bewusst nicht verschwiegen).** Es gibt keinen Pro-Nutzer-Lock
  auf `user.json`. Die gefährliche Richtung ist NICHT Admin gegen Admin, sondern diese: Ein
  typisierter Nutzer- oder Hintergrund-Schreiber (Profil-PUT, Tier-Antrag, Passkey,
  Telegram-Connect, Magic-Link und weitere, ca. 20 `SaveUser`-Aufrufer) lädt `user.json`
  VOR dem Admin-Schreiben und speichert DANACH. Er setzt `disabled` still auf `false`
  zurück (bzw. `tier` auf den alten Wert). Der Read-after-Write im Admin-Handler fängt das
  NICHT, weil er vor dem Überschreiben läuft. Mildernd: Nach dem Sperren sind alle Sitzungen
  gelöscht, der gesperrte Nutzer kann also selbst keine Profil-Schreiber mehr auslösen; das
  Fenster betrifft nur Anfragen, die im Millisekundenbereich parallel laufen. Die Liste zeigt
  den Ist-Zustand, der Admin sieht eine verlorene Sperre und kann sie wiederholen. Ein neuer
  Lock ohne Mitwirkung aller `SaveUser`-Aufrufer brächte keinen Schutz ⇒ bewusst kein Lock.
  Dokumentiert in dieser Spec und in ADR-0080.
- **Bewusst NICHT gefiltert: `store/address_owner.go` (`forEachRealAccount`).** Eine gesperrte
  Adresse bleibt vergeben; es gibt keinen Übernahmeweg über ein gesperrtes Konto.
- **Bewusst NICHT gefiltert: Eindeutigkeitsprüfung in `telegram_connect.go`.** Die
  Telegram-Chat-ID eines gesperrten Kontos bleibt vergeben.
- **Kein Registrierungshinweis für gesperrte Absender.** Sie werden stumm verworfen; der
  Absender erfährt die Sperre nicht über den Inbound-Kanal.
- **Issue #2155 bleibt nach S3 offen** (S4-UI folgt).

### Betroffene Dokumentation (nachzuziehen)

| Datei | Anpassung |
|---|---|
| `docs/adr/0080-kontosperre.md` (neu) + `docs/adr/README.md` | Entscheidung: Sperre wirkt auf allen Wegen, Reihenfolge, Restrisiko Lost Update |
| `docs/reference/api_contract.md` | DTO `AdminUser` und die drei Endpunkte, Fehlercode `account_disabled` |

## Changelog

- 2026-09-29: Initial spec created (#2155 S3)
