---
entity_id: sms_nummer_verifikation
type: module
created: 2026-09-22
updated: 2026-09-22
status: draft
version: "1.0"
workflow: feat-2406-sms-verifikation
tags: [security, multi-user, auth, sms, issue-2406, issue-2153, epic-2138]
---

# SMS-Nummer-Verifikation vor erstem Versand (#2406)

## Approval

- [ ] Approved

## Purpose

Die SMS-Nummer im Profil (`sms_to`) wird heute roh gespeichert und ist sofort wirksam — jeder
Trip-/Compare-/Alarm-Versand adressiert sie ungeprüft. Diese Spec führt eine E.164-Formatprüfung
beim Speichern und einen Bestätigungscode per SMS ein: eine Nummer wird erst dann tatsächlich
beliefert, wenn ihr Besitzer den an genau diese Nummer verschickten Code eingegeben hat. Ziel ist,
Versand an fremde Nummern auf Betreiberkosten (Mail-Bombing-Analogon für SMS, teurer als E-Mail)
strukturell zu verhindern. Scheibe S3 von #2153 (Epic #2138), Sicherheitsrisiko, Priorität hoch.

## Source

- **File:** `internal/model/user.go`, `internal/store/user.go`, `internal/handler/auth.go`,
  `internal/handler/sms_verify.go` (neu), `internal/handler/staging_sms_code.go` (neu),
  `internal/router/router.go`, `api/routers/internal.py`, `src/app/config.py`,
  `scripts/backfill_2406_sms_verified.py` (neu)
- **Identifier:** `model.User` (neue Felder), `UpdateProfileHandler`, `PostSmsVerifyHandler` (neu),
  `PostSmsResendHandler` (neu), `StagingSmsCodeHandler` (neu), `with_user_profile`

> **Schicht-Hinweis:** Betrifft alle drei Schichten — Go-API (`internal/`), Python-Core (`api/`,
> `src/app/config.py`, `src/output/channels/sms.py` bleibt unverändert als Transport), SvelteKit-
> Frontend (`frontend/src/routes/account/+page.svelte`, geteilte Kanal-Anzeige-Bausteine). Zusätzlich
> zwei Deploy-Skripte im Repo `henemm-infra` (`scripts/deploy-gregor-prod.sh`,
> `scripts/auto-deploy-gregor-staging.sh`) — Begründung siehe „Deploy-Reihenfolge" unten.
> **Timing-Hinweis (henemm-infra ist ein Arbeitsbaum, sofort live):** die beiden Skript-Änderungen
> dürfen NICHT während der laufenden Implementierung dieser Spec (`/50`) in `henemm-infra` committet
> werden — der Cronjob liest den Arbeitsbaum direkt (siehe
> `reference_infra_arbeitsbaum_ist_sofort_live_cron_laeuft_aus_dem_repo`). Sie gehören unmittelbar
> vor den Merge dieser Scheibe, in einer eigenen, kurzen Änderung an `henemm-infra`.

## Abgrenzung

Nicht Teil dieser Scheibe (Sammel-Issue #2153, spätere Scheiben):

- SMS-Tageslimit (S4) und allgemeine Quoten (S5) — die hier eingeführte Mengenbremse deckt
  ausschließlich den Code-Versand ab, nicht den normalen Trip-/Compare-Versand.
- Adress-Aliasing-Erkennung für Telefonnummern (z. B. Schreibvarianten derselben Nummer über die
  E.164-Normalisierung hinaus).
- Persistenter Limiter-State über Restarts hinweg (wie bei `profile_mail_ratelimit.md` begründet:
  Single-Instanz-Deployment, Restarts sind nicht angreifergesteuert).
- Premium-SMS (`premium_sms_reply_to`, eigener Handshake) — unberührt.

## Estimated Scope

- **LoC:** production ~420 (Go ~230, Python ~60, Frontend ~130), Skript ~90, Tests ~370–420 (inkl.
  einer neuen Playwright-E2E-Spec) → Gesamt deutlich über dem 250-LoC-Limit — `loc_limit_override
  700` in `/40` nötig. Begründung wie bei `adresswechsel_nach_bestaetigung.md`: der Schema-/Handler-
  Kern (neue Felder, Pending-Logik, Code-Handshake, Fail-closed-Sperre im Versandpfad) hat nur EINEN
  sinnvollen Lieferzeitpunkt: ein additiver „Vorbereitung"-Schnitt ohne die Sperre wäre wirkungslos,
  und die Sperre ohne Backfill wäre die Aussperr-Falle aus Designpunkt 6. **Rückfallebene, falls die
  Umsetzung in `/40`/`/50` trotz Override strukturell nicht trägt:** Aufteilung in Vorbereitung
  (additive Felder, Code-Handshake, Backfill-Skript, noch keine Sperre in `config.py`) und
  Scharfschaltung (Sperre + Deploy-Reihenfolge) innerhalb von #2406 — analog #2304/#2271. Nur als
  Rückfallebene, nicht als Default (PO-Vorgabe: eine Spec, eine Lieferung).
- **Files:** ~14 Produktivdateien im Hauptrepo (Go 6, Python 2, Frontend 6) + 1 neues Skript + 2
  Dateien im Repo `henemm-infra` (Deploy-Skripte, zählen nicht zum gregor_zwanzig-LoC-Limit) + ~9
  Testdateien (davon 1 Playwright-E2E, 1 infra-seitig)
- **Effort:** high (Auth-Kernpfad, Schema-Änderung, neuer Go→Python-Versandweg, Deploy-Reihenfolge,
  Risk Level HIGH)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/user.go` | MODIFY | Drei neue `User`-Felder (`SmsVerifiedNumber`, `SmsVerifiedAt`, `PendingSmsTo`) + neuer `SmsVerificationCode`-Struct. Schema-relevant ⇒ Pre-Snapshot-Hook, Read-Modify-Write |
| `internal/store/e164.go` | CREATE | `IsValidE164(s string) bool` |
| `internal/store/user.go` | MODIFY | `SaveSmsVerification`/`LoadSmsVerification`/`DeleteSmsVerification` (Klon der `*VerificationToken`-Methoden, Zeilen 204/220/240) |
| `internal/handler/auth.go` | MODIFY | `UpdateProfileHandler` (Zeilen 1067-1069 ersetzt): E.164-Prüfung, `smsFieldChanged`-Prädikat, Pending-/Direkt-Logik, Tier-Gate, Mengenbremse, Dispatch. `toProfileResponse` (Zeilen 774-813): `SmsVerified`, `PendingSmsTo` |
| `internal/handler/sms_verify.go` | CREATE | Code-Erzeugung (`generateSmsCode`, `issueSmsVerificationCode`), Versand-Dispatch (`dispatchSmsVerificationCode`, Test-Seam `sendSmsCodeFn`), `PostSmsVerifyHandler`, `PostSmsResendHandler` (inkl. Tier-Gate) |
| `internal/handler/staging_sms_code.go` | CREATE | `StagingSmsCodeHandler` — nur `GZ_ENV=staging`, ausschließlich eigene Sitzung |
| `internal/router/router.go` | MODIFY | `smsFloodLimiter`-Instanz, drei neue Routen, `UpdateProfileHandler`-Aufruf um Limiter-Parameter erweitert |
| `api/routers/internal.py` | MODIFY | `POST /api/_internal/sms/verification-code` |
| `src/app/config.py` | MODIFY | `with_user_profile` (Zeilen 427-431): fail-closed `sms_to`-Override, symmetrisch normalisierter Vergleich |
| `scripts/backfill_2406_sms_verified.py` | CREATE | Bauart `backfill_2271_email_verified.py` |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Code-Eingabe, Pending-Hinweis, „Code erneut senden", Fehlermeldungen (`invalid_sms_number`/`429`/`invalid_code`) |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Zeile 119 (`sms: !!profile?.sms_to && profile?.sms_allowed !== false`) → zusätzlich `profile?.sms_verified`. Context-aware (`context="route"\|"vergleich"`, Zeile 32) — Dual-Context-AC gilt hier |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `profile`-State-Typ (Zeile 244) um `sms_verified`/`pending_sms_to` erweitert — beschreibt nur, was der Profil-Endpunkt liefert; keine Render-Verzweigung für den SMS-Kanalstatus in diesem Reiter, kein Dual-Context-Testnachweis nötig (Korrektur nach Adversary-Finding F001, siehe Changelog) |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` | MODIFY | Reine Ableitungsfunktion ohne `context`-Parameter — kein Dual-Context-Test nötig, wird von beiden Callern gemeinsam genutzt |
| `frontend/src/lib/components/shared/versand-tab/channelContactLabel.ts` | MODIFY | Wie oben: kontextfreie Hilfsfunktion |
| `frontend/e2e/feat-2406-sms-verify.spec.ts` | CREATE | Live-E2E gegen Staging (AC-17) |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | MODIFY | Backfill-Aufruf zwischen Binary-Swap und Service-Start, Trap-Erweiterung `GREGOR_API_STOPPED` |
| `henemm-infra/scripts/auto-deploy-gregor-staging.sh` | MODIFY | Expliziter `stop gregor-api-staging` vor dem neuen Backfill-Aufruf |
| `henemm-infra/tests/test_gregor_sms_backfill_deploy_order.py` | CREATE | Reihenfolge-/Trap-Assertion, Muster `test_gregor_venv_permissions.py` (AC-11) |

**Korrektur gegenüber dem Kontext-Dokument:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
(nicht unter `shared/`, sondern unter `components/edit/`) instanziiert `VTSchedulePlan` fest mit
`context="route"` (Zeile 317) — es ist ein Trip-**only**-Wrapper ohne eigenen `context`-Zweig, kein
Baustein, der unter `context="vergleich"` erneut gerendert wird. Es taucht in dieser Tabelle bewusst
NICHT als eigene Zeile auf; eine Änderung dort (falls nötig) ist eine Konsequenz der Änderung an
`VTBriefingChannels.svelte`/`WeatherMetricsTab.svelte`, kein eigenständiger Berührungspunkt.

## Scope

**In dieser Lieferung (S3 von #2153, Epic #2138):**

- E.164-Formatprüfung beim Speichern (§2) und der komplette Code-Handshake — Erzeugen, Versenden,
  Bestätigen, erneut Senden (§§3–4) — sowie der Staging-Testweg (§5).
- Die fail-closed-Sperre an der Python-Versand-Wirkstelle (`with_user_profile`, §9): eine
  unbestätigte oder ausstehende Nummer erreicht `Settings.sms_to` nie.
- Tier-Gate vor JEDEM Code-Versand an beiden Entry-Points (Profil-Update UND Resend, §2/§4) sowie
  eine eigenständige Mengenbremse (3 Code-Versuche/Stunde je Nutzer, §2).
- Das Backfill-Skript für Bestandskonten (§10) und die zugehörige Deploy-Reihenfolge inkl.
  Trap-Erweiterung in `henemm-infra` (§11).
- Die Frontend-Anzeige des Pending-/Bestätigt-Status (§6, `VTBriefingChannels.svelte`,
  `EditReportConfigSection.svelte`, kontextfreie Helfer).
- Der Live-E2E-Nachweis über den vollständigen Ablauf im Browser (AC-17).
- Vollständige Datei-Liste: siehe `### Affected Files` unter `## Estimated Scope` oben.

**Nicht in dieser Lieferung** (Details siehe `## Abgrenzung` oben):

- SMS-Tageslimit (S4) und allgemeine Quoten (S5) aus dem Sammel-Issue #2153 — spätere Scheiben.
- Adress-Aliasing-Erkennung für Telefonnummern über die E.164-Normalisierung hinaus.
- Persistenter Limiter-State über Restarts hinweg (Single-Instanz-Deployment, Restarts sind nicht
  angreifergesteuert).
- Premium-SMS (`premium_sms_reply_to`, eigener Handshake) — unberührt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/user.go` (`EmailVerificationToken`, Zeile 66) | Go-Struct (Vorbild) | Adressgebundenes Token mit Hash+Ablauf — Vorlage für `SmsVerificationCode` |
| `internal/store/user.go` `SaveVerificationToken`/`LoadVerificationToken`/`DeleteVerificationToken` (Zeilen 204/220/240) | Go-Store-Methoden (Vorbild) | Ein-Datei-je-Konto-Muster für `sms_verification.json` |
| `internal/handler/premium_sms_link_code.go` (`generatePremiumSmsLinkCode`, Zeile 48) | Go-Funktion (Vorbild) | `crypto/rand`-Bauart für den Code — hier numerisch statt alphanumerisch |
| `internal/handler/staging_verify_token.go` | Go-Handler (Vorbild, abweichend übernommen) | Staging-only-Registrierung nur bei `GZ_ENV=staging`; **abweichend**: dieser Handler nimmt die Kennung aus dem Request-Body (beliebiges Konto), unserer nutzt AUSSCHLIESSLICH die eigene Sitzung (Designvorgabe 7) |
| `internal/handler/profile_mail_ratelimit.go` (`MailFloodLimiter`, `NewMailFloodLimiter`) | Go-Struct (Wiederverwendung) | Schlüsselbasierter Zwei-Ebenen-Limiter (User- + Ziel-Bucket, Reserve/Cancel ohne Teilverbrauch) — eine ZWEITE, eigenständige Instanz für SMS-Codes (kein geteiltes Kontingent mit Mail) |
| `internal/store/address_owner.go` (`NormalizeEmailAddress`, Zeile 21) | Go-Funktion (Vorbild) | Platzierungsmuster für den neuen `internal/store/e164.go` — generische Validatoren leben im `store`-Paket |
| `internal/coreauth/transport.go` (`Install`) | Go-Paket | Hängt `X-GZ-Core-Auth` automatisch an jeden `http.DefaultTransport`-Aufruf gegen `cfg.PythonCoreURL` — der neue interne Aufruf braucht keinen eigenen Header-Code |
| `internal/handler/forecast.go` (`forecastReservePfad`, Zeile 23) | Go-Handler (Vorbild) | Zeigt das Muster „Go ruft `/api/_internal/...` mit Timeout und JSON-Decode auf" (ADR-0076) |
| `api/routers/internal.py` | Python-Router (Erweiterung) | Alle Routen hinter `X-GZ-Core-Auth` (ADR-0062); neuer Endpunkt reiht sich hier ein |
| `src/app/config.py` `with_user_profile` (Zeilen 394–445), `can_send_sms` (447–453) | Python-Funktionen | Wirkstelle der Fail-closed-Sperre — `sms_to` erreicht `Settings` nur bei bewiesener Nummer |
| `api/routers/scheduler.py:234` (`Settings().with_user_profile(user_id)`) | Python-Funktion (Vorbild) | Baut den `Settings`-Kontext für den internen Versand-Endpunkt |
| `src/output/channels/sms.py` (`SMSOutput`), `seven_io_base.py` (`SevenIoChannelBase.send`) | Python-Klassen | Einziger seven.io-Transport — Sandbox-Zwang (#1336) und Herkunftssperre (#1476) bleiben dort, unverändert |
| `internal/model/tier.go` (`SmsAllowed`, `EffectiveTier`) | Go-Funktionen | Tier-Gate vor JEDEM Code-Versand (Profil-Update UND Resend) |
| `scripts/backfill_2271_email_verified.py`, `scripts/migrate_1250_briefings.py` | Python-Skripte (Vorbild) | Dry-Run-Default/`--execute`/Backup/Idempotenz-Bauart; `migrate_1250_briefings.py` zusätzlich als Deploy-Schritt-Vorbild (Position im Skript **bewusst abweichend**, siehe unten) |
| `henemm-infra/tests/test_gregor_venv_permissions.py` | Python-Test (Vorbild) | Reihenfolge-Assertion über Zeilen-Index in den Deploy-Skripten — Muster für den neuen Deploy-Order-Test |
| `docs/adr/0062-python-core-authentifiziert-gegenueber-go.md`, `docs/adr/0076-go-dockt-ueber-internen-endpunkt-an-das-kontingent-gate-an.md` | ADRs | Tragen den neuen internen Endpunkt bereits — kein neues ADR nötig (siehe „Architektur-Entscheidung") |

## Implementation Details

### 1) Schema (`internal/model/user.go`, Read-Modify-Write, Pre-Snapshot-Hook)

Drei neue Felder auf `User`, alle `omitempty` (Bestandsdaten laden unverändert):

```go
SmsVerifiedNumber string     `json:"sms_verified_number,omitempty"`
SmsVerifiedAt     *time.Time `json:"sms_verified_at,omitempty"`
PendingSmsTo      string     `json:"pending_sms_to,omitempty"`
```

Neuer Struct (gleiche Datei, neben `EmailVerificationToken`):

```go
type SmsVerificationCode struct {
    CodeHash       string    `json:"code_hash"`
    ExpiresAt      time.Time `json:"expires_at"`
    Number         string    `json:"number"`
    FailedAttempts int       `json:"failed_attempts,omitempty"`
}
```

`Number` ist die zu beweisende Nummer (== `PendingSmsTo` bzw. bei einem erstmals unbestätigten
`sms_to` == `sms_to`) — bindet den Code an die Nummer, exakt wie `EmailVerificationToken.Address`.

`internal/store/user.go`: `SaveSmsVerification`/`LoadSmsVerification`/`DeleteSmsVerification`, ein
Eins-zu-eins-Klon von `SaveVerificationToken`/`LoadVerificationToken`/`DeleteVerificationToken`
(Zeilen 204/220/240), Datei `data/users/<id>/sms_verification.json`. Ein neuer Wechsel überschreibt
die Datei vollständig (wie beim E-Mail-Token) — der alte Code samt Fehlversuchszähler ist damit
entwertet.

`internal/store/e164.go` (neu, Muster `address_owner.go:21`):

```go
func IsValidE164(s string) bool // ^\+[1-9]\d{7,14}$ — "+", keine führende 0, 8–15 Ziffern gesamt
```

### 2) `UpdateProfileHandler` (`internal/handler/auth.go`, ersetzt Zeilen 1067–1069)

**E.164-Prüfung VOR jedem Schreibzugriff** (wie die Display-Name-Prüfung, Zeilen 882–894): ein
nicht-leerer, ungültiger Wert → `400 {"error":"invalid_sms_number"}`, nichts wird verändert. Ein
leerer String bleibt erlaubt (Entfernen).

**Änderungs-Prädikat (Kernpunkt, schließt den wahrscheinlichsten Implementierungsfehler).**
🔴 Der Deref von `*update.SmsTo` MUSS innerhalb der Nil-Prüfung stehen — `account/+page.svelte`
schickt `sms_to` zwar bei jedem Speichern mit, aber andere Aufrufer (Tests, künftige Clients) dürfen
das Feld auslassen; ein Deref davor crasht den Handler bei jedem Request ohne `sms_to`:

```go
var newSmsTo string
if update.SmsTo != nil {
    newSmsTo = strings.TrimSpace(*update.SmsTo)
}
smsFieldChanged := update.SmsTo != nil &&
    newSmsTo != user.SmsTo && newSmsTo != user.PendingSmsTo
```

Der Vergleich läuft gegen **beide** Felder — `sms_to` UND `pending_sms_to` — nicht nur gegen
`sms_to`. Grund: `account/+page.svelte:353-372` schickt `sms_to` bei **jedem** Profil-Speichern mit,
auch bei einer reinen `display_name`-Änderung. Eine naive Prüfung `update.SmsTo != nil` (der heutige
Code, Zeile 1067) würde bei jedem Speichern einen neuen Code auslösen — ein bezahlter SMS-Versand pro
Klick auf „Speichern", unabhängig vom Inhalt. Der zweite Teil des Vergleichs (`!= user.PendingSmsTo`)
macht zusätzlich das erneute Absenden eines bereits ausstehenden Werts zum No-op (kein doppelter
Versand, kein Kontingentverbrauch).

**Drei Zweige, wenn `smsFieldChanged`:**

```go
switch {
case newSmsTo == "":
    // Entfernen — AC-9: räumt vollständig auf, keine überlebende Pending-Bestaetigung.
    user.SmsTo, user.PendingSmsTo = "", ""
    user.SmsVerifiedNumber, user.SmsVerifiedAt = "", nil
    deleteSmsVerification = true // s.DeleteSmsVerification(userId) nach SaveUser
case user.SmsVerifiedNumber == "" || user.SmsVerifiedNumber != user.SmsTo:
    // Keine wirksame bestaetigte Nummer (Erst-Eintrag ODER Bestandskonto vor Backfill/nach
    // Entfernen) — direkt schreiben, wie beim unbestaetigten E-Mail-Fall. sms_to traegt die
    // neue Nummer sofort, bleibt aber wegen Designpunkt 1 (Versand-Wirkstelle) bis zur
    // Bestaetigung fail-closed gesperrt.
    user.SmsTo = newSmsTo
    user.PendingSmsTo = ""
    smsCodeTarget = newSmsTo
default:
    // Bestaetigte Nummer bleibt wirksam; die neue wartet als Pending (kein Sofort-Umbiegen).
    user.PendingSmsTo = newSmsTo
    smsCodeTarget = newSmsTo
}
```

**Tier-Gate VOR jedem Code-Versand (gilt für BEIDE Entry-Points, Profil-Update UND Resend §4 —
Designvorgabe 6 ist unqualifiziert).** `sendSmsCode := smsCodeTarget != "" &&
model.SmsAllowed(model.EffectiveTier(user.Tier))`. Ist der Tarif nicht SMS-fähig, wird `sms_to`/
`pending_sms_to` zwar wie oben beschrieben gesetzt (ein Free-Nutzer darf die Nummer eintragen), aber
**kein** Code verschickt und **kein** Kontingent verbraucht. Der Weg zurück ist NICHT „Wert erneut
speichern" (das würde als No-op erkannt, `smsFieldChanged` bliebe `false`), sondern der bestehende
„Code erneut senden"-Knopf (§4) — der prüft das Tier-Gate zum Zeitpunkt des Klicks erneut und
funktioniert nach einem Tarif-Upgrade normal.

**Mengenbremse VOR `SaveUser`** (Muster #2404, Zeile 1098), nur wenn `sendSmsCode`: eine **zweite,
eigenständige** `MailFloodLimiter`-Instanz (`smsFloodLimiter`, `NewMailFloodLimiter(3, time.Hour)` →
`Retry-After: 1200`) wird geprüft: `!smsFloodLimiter.Allow(userId, smsCodeTarget)` → `429`,
`Retry-After`-Header, **kein** `SaveUser` (kein Teilzustand, auch nicht für gleichzeitig geänderte
harmlose Felder). Eine eigenständige Instanz statt der geteilten `mailFloodLimiter`: ein SMS-Angriff
soll nicht das E-Mail-Kontingent verbrauchen und umgekehrt. Drei statt zehn pro Stunde — SMS kostet
Geld, ein Tippfehler plus ein Korrekturversuch passen komfortabel hinein, ein Missbrauchsversuch mit
vielen fremden Nummern nicht.

Nach `SaveUser`: bei `sendSmsCode` (Tier-Gate UND Mengenbremse bestanden) wird
`dispatchSmsVerificationCode(cfg, userId, smsCodeTarget)` asynchron aufgerufen — Muster
`dispatchVerificationMail` (Goroutine, Timeout), mit Test-Seam `sendSmsCodeFn` analog
`sendVerificationMailFn` (Zeile 1128).

### 3) Code-Erzeugung und -Versand (`internal/handler/sms_verify.go`, neu)

`generateSmsCode() (string, error)`: 6 Ziffern aus `crypto/rand` (Muster `randomStringFromAlphabet`,
`premium_sms_link_code.go:63`, Alphabet `"0123456789"`, Länge 6). `issueSmsVerificationCode(s
*store.Store, userId, number string) (string, error)`: erzeugt den Code, bcrypt-hasht ihn
(`bcrypt.DefaultCost`), persistiert `SmsVerificationCode{CodeHash, ExpiresAt: now+10min, Number:
number}` über `s.SaveSmsVerification` — **vor** dem eigentlichen Sendeversuch (Muster
`dispatchVerificationMail`/`auth.go:787`, AC-7 aus #2304: der Code muss auch ohne funktionierenden
Versand existieren, für Staging-E2E). `dispatchSmsVerificationCode` ruft danach den internen
Python-Endpunkt auf; schlägt der Versand fehl, bleibt der Code trotzdem gültig (Nutzer kann per
Resend erneut versuchen).

`sendSmsCodeFn` (Test-Seam, package-private Funktionsvariable, Default = echter HTTP-Aufruf): POST
gegen `cfg.PythonCoreURL + "/api/_internal/sms/verification-code"`, JSON-Body `{"user_id":
userId, "to": number, "code": code}`, `http.Client{Timeout: 10 * time.Second}` (derselbe
`http.DefaultTransport`, den `coreauth.Install` patcht — kein eigener Header-Code nötig, Muster
`forecast.go`). Nicht-2xx oder Transportfehler werden geloggt, aber lösen **keinen** Fehler im
aufrufenden `UpdateProfileHandler`-Response aus (Muster E-Mail: Profil-Update antwortet `200`
unabhängig vom Ausgang des asynchronen Versands).

### 4) Bestätigen und erneut senden (`internal/handler/sms_verify.go`)

`POST /api/auth/sms/verify` (anmeldepflichtig, `userId` aus Auth-Kontext, **niemals** aus dem
Body — kein zweiter Angriffsvektor wie bei `ResendVerificationHandler`, das dort bewusst *username*
akzeptiert, weil es unauthentifiziert ist; dieser Endpunkt ist es nicht):

- Lädt `sms_verification.json` des angemeldeten Kontos. Fehlt sie oder ist `ExpiresAt` überschritten
  oder `FailedAttempts >= 5` → `400 {"error":"code_expired"}`.
- `bcrypt.CompareHashAndPassword` gegen den übermittelten Code.
  - Falsch: `FailedAttempts++`, gespeichert; erreicht der neue Wert 5 → die Datei wird gelöscht
    (Code verfällt sofort, kein sechster Versuch nötig) → Antwort in jedem Fehlerfall `400
    {"error":"invalid_code"}` (erst NACH Erreichen von 5 wechselt eine erneute Anfrage auf
    `code_expired`, weil dann keine Datei mehr existiert).
  - Richtig: Read-Modify-Write — frisches `LoadUser`, dann: ist `PendingSmsTo` gesetzt, wird es zu
    `SmsTo` befördert und geleert; `SmsVerifiedNumber = user.SmsTo`, `SmsVerifiedAt = jetzt`,
    `SaveUser`, `DeleteSmsVerification`. Antwort `200` mit dem aktualisierten Profil (Muster
    `toProfileResponse`).

`POST /api/auth/sms/resend` (anmeldepflichtig): Zielnummer = `PendingSmsTo`, sonst `SmsTo` (wie
`dispatchVerificationMail`s Adressauswahl). Ist keine Nummer gesetzt → `400 {"error":"no_number"}`.
**Tier-Gate zuerst** (`model.SmsAllowed(model.EffectiveTier(user.Tier))`, identische Prüfung wie in
§2) — ohne SMS-fähigen Tarif → `400 {"error":"sms_not_allowed"}`, kein Kontingentverbrauch, kein
Versand. Erst danach dieselbe Mengenbremse (`smsFloodLimiter.Allow(userId, ziel)`) wie beim
Profil-Update — bei Erfolg `issueSmsVerificationCode` + `dispatchSmsVerificationCode` (überschreibt
einen evtl. bestehenden Code samt Fehlversuchszähler, exakt wie ein zweiter Adresswechsel das
E-Mail-Token entwertet, `adresswechsel_nach_bestaetigung.md` §„Adressgebundenes Token").
**Präzisierung zum abgelösten Code (AC-16, in `/50` entschieden):** Wird ein Code durch einen neueren
ersetzt (Nummernwechsel oder Resend), liefert eine spätere Eingabe des alten Codes `invalid_code`,
nicht `code_expired`. Es wird bewusst nur EIN Hash persistiert — ein abgelöster Code ist damit von
einem Rateversuch mechanisch nicht unterscheidbar, und ein zweiter, nur zur Unterscheidung des
Fehlertextes gehaltener Hash wäre zusätzliche Angriffsfläche ohne Nutzen für den Nutzer. `code_expired`
bleibt den beiden Fällen vorbehalten, in denen die Datei tatsächlich nichts (mehr) hergibt: Ablauf und
verbrauchte Fehlversuche (bzw. gelöschte Datei nach Entfernen der Nummer).

**Nummernbindung beim Einlösen (Pflicht, AC-4c):** Vor dem Hash-Vergleich prüft der Handler, dass
`SmsVerificationCode.Number` mit der gerade zu beweisenden Nummer des Kontos übereinstimmt
(`PendingSmsTo`, ersatzweise `SmsTo`) — sonst `400 {"error":"invalid_code"}`. Ohne diese Prüfung
bestätigte ein Code, der auf eine fremde Nummer ausgestellt wurde, die Nummer des Kontos.

**Der Fehlversuchszähler wird dadurch bei jedem Resend zurückgesetzt — die Mengenbremse (3/h je
Nutzer UND Ziel) ist deshalb der eigentliche Brute-Force-Riegel, nicht allein die 5-Versuche-Grenze
pro Code**: Ohne die Bremse könnte beliebig oft resendet und dabei der Fehlversuchszähler beliebig
oft auf 0 zurückgesetzt werden. Das Tier-Gate an dieser zweiten Stelle ist zugleich der reguläre Weg
zurück nach einem Tarif-Upgrade (siehe §2, Known Limitations).

### 5) Staging-Code-Weg (`internal/handler/staging_sms_code.go`, neu)

`POST /api/auth/sms/staging-code`, registriert **nur** bei `GZ_ENV == "staging"` (Muster
`router.go:87`). **Abweichend vom E-Mail-Vorbild** (`staging_verify_token.go`, das eine beliebige
`username` aus dem Body nimmt und damit für JEDES Konto ein Token zieht): dieser Handler ignoriert den
Body vollständig und arbeitet **ausschließlich** auf `middleware.UserIDFromContext(r.Context())` —
Designvorgabe 7 verlangt „nur für den eigenen Nutzer". Zielnummer: `PendingSmsTo`, sonst `SmsTo`; ist
keine gesetzt → `404`. Er **mintet einen frischen Code** über `issueSmsVerificationCode` (überschreibt
einen eventuell bereits über den normalen Profil-Update-Pfad ausgelösten, real — aber im
Sandbox-Modus folgenlos — „versendeten" Code) und gibt ihn im Klartext zurück, **ohne** einen
Sendeversuch zu machen. Grund für das Neu-Minten statt Auslesen: es wird ausschließlich der bcrypt-Hash
persistiert, der Klartext existiert nur im Moment der Erzeugung — identisch zur Begründung bei
`StagingVerificationTokenHandler`. Der reguläre `POST /api/auth/sms/verify` bleibt der einzige Weg,
der `SmsVerifiedNumber`/`SmsVerifiedAt` setzt — der Testweg prüft den echten Bestätigungspfad mit,
statt ihn zu umgehen. Der Pfad liegt unter `/api/auth/...` — **nicht** unter `/api/debug/`,
`/api/internal/` oder `/api/webhooks/telegram/`, den drei von `AuthMiddleware` pauschal befreiten
Präfixen — und steht **nicht** in der Public-Allowlist, ist also anmeldepflichtig.

### 6) `toProfileResponse` (`internal/handler/auth.go:774-813`)

Zwei neue Felder: `SmsVerified bool` (`u.SmsVerifiedNumber != "" && u.SmsVerifiedNumber ==
u.SmsTo`) und `PendingSmsTo string` (`u.PendingSmsTo`).

### 7) Router (`internal/router/router.go`)

```go
smsFloodLimiter := handler.NewMailFloodLimiter(3, time.Hour) // Issue #2406 — eigenes Kontingent
r.Post("/api/auth/sms/verify", handler.PostSmsVerifyHandler(deps.Store))
r.Post("/api/auth/sms/resend", handler.PostSmsResendHandler(deps.Store, *deps.Config, smsFloodLimiter))
if os.Getenv("GZ_ENV") == "staging" {
    r.Post("/api/auth/sms/staging-code", handler.StagingSmsCodeHandler(deps.Store))
}
```
`UpdateProfileHandler`-Aufruf (Zeile 95) bekommt `smsFloodLimiter` als zusätzlichen Parameter.

### 8) Python: interner Versand-Endpunkt (`api/routers/internal.py`)

```python
class SmsVerificationCodeRequest(BaseModel):
    user_id: str
    to: str
    code: str

@router.post("/api/_internal/sms/verification-code")
def send_sms_verification_code(req: SmsVerificationCodeRequest):
    settings = Settings().with_user_profile(req.user_id).model_copy(update={"sms_to": req.to})
    if not settings.can_send_sms():
        return JSONResponse(status_code=422, content={"error": "sms_not_configured"})
    try:
        SMSOutput(settings).send("", f"Dein Gregor20-Bestaetigungscode: {req.code}")
    except (OutputConfigError, OutputError) as exc:
        return JSONResponse(status_code=502, content={"error": "sms_send_failed"})
    return {"status": "sent"}
```

Muster `api/routers/scheduler.py:234` (`Settings().with_user_profile(user_id)`). `model_copy(update=
{"sms_to": req.to})` überschreibt die Zielnummer mit der vom Go-Prozess bereits validierten,
NICHT-notwendigerweise-persistierten Nummer (bei `pending_sms_to` steht sie noch nicht in `user.json`
als `sms_to`) — `with_user_profile` selbst liest nur `sms_to` aus dem Profil, das reicht hier nicht.
Die `is_test_user`/`env == "staging"`-Sandbox-Weiche (`config.py:408`) bleibt dabei vollständig
erhalten, weil sie **vor** dem `model_copy`-Override in `with_user_profile` greift.

### 9) Python: Versand-Wirkstelle (`src/app/config.py`, Fail-closed-Sperre)

**Designpunkt 1, der eigentliche Wächter.** In `with_user_profile` (Zeile 427-431, `overrides`-Dict)
wird `sms_to` nicht mehr ungeprüft übernommen:

```python
sms_verified_number = (profile.get("sms_verified_number") or "").strip()
raw_sms_to = (profile.get("sms_to") or "").strip()
overrides = {
    "mail_to": profile.get("mail_to") or None,
    "sms_to": raw_sms_to if (sms_verified_number and sms_verified_number == raw_sms_to) else None,
    "email_verified_at": profile.get("email_verified_at") or None,
}
```

**Normalisierungs-Symmetrie (Pflicht, sonst Aussperr-Falle nach dem Backfill):** der Vergleich
`sms_verified_number == raw_sms_to` läuft auf **beiden Seiten identisch getrimmt** (`.strip()`, wie
oben). Das Backfill-Skript (Abschnitt 10) schreibt `sms_verified_number` als **byteidentische Kopie**
des zum Zeitpunkt des Laufs gelesenen `sms_to`-Werts (kein eigenes Trimmen dort) — träfe der
Vergleich hier ungetrimmt auf eine Bestandsnummer mit Leerzeichen am Rand, während der Nutzer sie
später über das (trimmende) Profil-Update erneut speichert, verwürfe eine asymmetrische Prüfung
genau das Konto, das der Backfill eigentlich schützen sollte. Deshalb: **beide** Seiten des Vergleichs
werden hier — an der Wirkstelle — gleich behandelt, unabhängig davon, ob die gespeicherten Rohwerte
sauber sind.

Damit erreicht eine nicht-bestätigte oder gerade erst pending gewordene Nummer `Settings.sms_to`
**nie** — jeder SMS-Versand (`sms.py::_resolve_recipient`, alle Alarm-/Briefing-Kanal-Auflösungen, die
`with_user_profile`/`can_send_sms()` nutzen) blockt fail-closed, ohne dass diese Aufrufer selbst etwas
über Verifikation wissen müssen (Konzeptuelles Gegenstück zu `email.py:294`s Resend-Allowlist-Guard).
`can_send_sms()` (Zeile 447-453) selbst bleibt unverändert — es prüft weiterhin nur, ob `sms_to`
überhaupt gesetzt ist; die Fail-closed-Entscheidung fällt bereits vorher in `with_user_profile`.

### 10) Backfill-Skript (`scripts/backfill_2406_sms_verified.py`, neu)

Eins-zu-eins-Bauart `backfill_2271_email_verified.py`: Dry-Run-Default, `--root` Pflicht,
`--backup-dir`, `--execute`, tar.gz-Backup vor jeder Änderung, Read-Modify-Write (nur die zwei neuen
Felder werden ergänzt, alles andere bleibt Byte für Byte erhalten), Idempotenz (ein Konto mit bereits
gesetztem `sms_verified_number` wird übersprungen, **keine** Lesepfad-Ausnahme „Feld fehlt ⇒ gilt als
bestätigt"). Plan-Kriterium: `sms_to` ist nicht-leer UND `sms_verified_number` ist noch nicht
gesetzt. Setzt dann `sms_verified_number = sms_to` (unverändert übernommen, siehe
Normalisierungs-Symmetrie oben) und `sms_verified_at = <UTC-Zeitstempel des Laufs>`. Konten mit
leerem `sms_to` werden übersprungen (nichts zu bestätigen). **Bekannte Grenze (wie beim E-Mail-
Vorbild):** eine heute bereits fremd eingetragene Nummer wird ebenfalls als bestätigt übernommen — die
Lücke schließt sich nur für künftige Änderungen.

### 11) Deploy-Reihenfolge (Pflicht, kein Implementierungsdetail — Designpunkt 6)

**Befund, der die Positionierung erzwingt:** `store.SaveUser` (`internal/store/user.go:76`)
marshalt den **typisierten** `model.User`-Struct neu — es ist **kein** Read-Modify-Write auf rohem
JSON (anders als die Python-Skripte). Ein `LoadUser` mit einer ALTEN Binary (die `sms_verified_number`
noch nicht kennt) verwirft dieses Feld beim `Unmarshal` stillschweigend; ein nachfolgender `SaveUser`
— egal wodurch ausgelöst, nicht nur durch ein Profil-Update — schreibt das Feld dann nicht mehr
zurück. Läuft der Backfill, während noch die alte `gregor-api`-Binary läuft, und schreibt diese Binary
in der Zwischenzeit `user.json` eines gerade nachgetragenen Kontos irgendeinmal neu (Profil-Update,
Passwortwechsel, Selbstheilung bei Login — jeder beliebige `SaveUser`-Aufruf, nicht nur einer aus
diesem Feature), verschwindet der Nachtrag wieder — die Sperre aus Abschnitt 9 greift danach für
dieses Konto erneut, obwohl es bereits nachgetragen war. **Das Argument gilt unabhängig davon, ob
Python `user.json` je schreibt** (geprüft: nein, siehe unten) — es hängt ausschließlich an `SaveUser`
im Go-Prozess.

**Geprüft** (Grep über `src/`): Python liest `user.json` nur (`config.py`, `loader.py`, u. a.), es
gibt keinen Python-Schreibpfad auf diese Datei — nur `gregor-api` (Go) schreibt sie. Der Zeitraum, in
dem das Fenster geschlossen werden muss, ist also exakt die Zeit, in der **gregor-api** aktiv sein
könnte, nicht die, in der gregor-python aktiv ist.

**Abweichung von der wörtlichen Vorgabe „exakt nach Präzedenz `migrate_1250_briefings.py`", bewusst
und begründet:** `migrate_1250_briefings.py` migriert `trips/`/`compare_presets.json` — Dateien, die
`model.User`/`SaveUser` nie berührt; für diese Migration ist die Position **vor** dem Go-Binary-Swap
(während die alte `gregor-api`-Binary noch läuft) unschädlich, weil kein Go-Code diese Dateien je
zurückschreibt. Für den SMS-Backfill, der `user.json` ändert, gilt das **nicht** — hier ist die
Position kritisch. Übernommen wird daher ausschließlich die **Skript-Bauart** (Dry-Run/`--execute`/
Backup/Idempotenz/fail-closed-Abbruch), **nicht** die Skript-**Position** im Deploy-Ablauf.

**Prod (`deploy-gregor-prod.sh`):** Aufruf zwischen `mv gregor-api.new gregor-api` (Zeile 419, alte
Binary ist damit ersetzt, ABER noch nicht gestartet) und `sudo systemctl start gregor-api` (Zeile
439) — an dieser Stelle ist gregor-python bereits seit Zeile 279 gestoppt, gregor-api ist seit Zeile
418 gestoppt und noch nicht neu gestartet: **kein Prozess im System kann in diesem Moment
`user.json` schreiben.** Aufruf identisch zum Migrations-Schritt (`sudo -u claude-gregor bash -c "cd
'$REPO_DIR' && python3 scripts/backfill_2406_sms_verified.py --root /var/lib/gregor/users
--execute"`), fail-closed (`exit 1` bei Fehler, Deploy-Abbruch). Die Backup-Zielangabe in der
Fehlermeldung MUSS den tatsächlichen Pfad nennen (`/var/lib/gregor/.backups`, aus `root.parent /
".backups"` — **nicht** `$REPO_DIR/.backups` wie in der vorbestehenden Migrationsschritt-Meldung ein
paar Zeilen darüber; diese vorbestehende Ungenauigkeit wird hier NICHT mitkorrigiert, siehe „Known
Limitations").

**Trap-Erweiterung (Pflicht, schließt eine sonst neu entstehende Lücke):** `cleanup_on_exit`
(Zeile 122-134) restartet heute bei einem Fehlschlag ausschließlich `gregor-python`
(`GREGOR_PYTHON_STOPPED`). Bricht der neue Backfill-Schritt fail-closed ab (oder ein danach folgender
Schritt wie `switch_frontend_release`, der schon heute in diesem Fenster liegt), bliebe `gregor-api`
**dauerhaft gestoppt** — ein Totalausfall der Go-API ohne Selbstheilung, dieselbe Fehlerklasse wie
henemm-infra#148 (dort wurde das Sicherheitsnetz für gregor-python eingeführt, gregor-api hatte zu dem
Zeitpunkt noch keinen vergleichbaren Stop/Start-Zweischritt im Skript). Die Erweiterung führt
`GREGOR_API_STOPPED=1` analog `GREGOR_PYTHON_STOPPED` ein (gesetzt direkt nach `sudo systemctl stop
gregor-api`, Zeile 417) und ergänzt `cleanup_on_exit` um `[ "$GREGOR_API_STOPPED" = "1" ] && sudo
systemctl start gregor-api` im Fehlerpfad — die zur Binary bereits umbenannte, zum Fehlerzeitpunkt neue
Datei liegt zu diesem Zeitpunkt bereits unter dem finalen Namen (Zeile 419 lief vor dem Backfill), der
Restart startet also den NEUEN Code, nicht den alten — inhaltlich korrekt, weil der Checkout selbst
längst auf `origin/main` steht.

**Staging (`auto-deploy-gregor-staging.sh`):** hier gibt es (anders als Prod) **keinen** expliziten
Stop/Swap-Zweischritt für `gregor-api-staging`, nur ein `systemctl restart` (Zeile 266) NACH Go-Build
und Frontend-Build — die alte Binary läuft bis zu diesem `restart` durch, also über den kompletten
Migrations-/Build-Zeitraum hinweg. Minimal-invasive Änderung: `sudo systemctl stop
gregor-api-staging` unmittelbar **vor** dem neuen Backfill-Aufruf einfügen (an der Position, an der
heute `migrate_1250_briefings.py` läuft, Zeile 229), Backfill-Aufruf danach, die bestehenden
`restart`-Zeilen (264/266/268) bleiben unverändert — ein `restart` auf einen bereits gestoppten Dienst
startet ihn einfach, kein Verhaltensunterschied. `migrate_1250_briefings.py` selbst bleibt an seiner
heutigen Position (unschädlich, siehe Begründung oben) — nur der neue SMS-Backfill-Aufruf zieht mit
dem vorgezogenen `stop` um.

## Expected Behavior

- **Input:** `PUT /api/auth/profile {"sms_to": "..."}`; `POST /api/auth/sms/verify {"code": "..."}`;
  `POST /api/auth/sms/resend`; interner Aufruf `POST /api/_internal/sms/verification-code`; Backfill-
  Skript gegen eine Datenwurzel (mit/ohne `--execute`).
- **Output:** `400 invalid_sms_number` bei ungültigem Format; `200` mit `pending_sms_to`/`sms_verified`
  im Profil bei gültiger Änderung; `429` + `Retry-After` bei ausgeschöpfter Mengenbremse; `200` und
  beförderte Nummer bei korrektem Code; `400 invalid_code`/`code_expired`/`sms_not_allowed` sonst.
- **Side effects:** ein Code-Versand pro tatsächlicher Nummernänderung (nicht pro Profil-Speichern),
  und nur bei SMS-fähigem Tarif; `sms_verification.json` entsteht/wird überschrieben/gelöscht; kein
  SMS-Versand (Trip, Compare, Alarme) adressiert je eine unbestätigte Nummer.

## Acceptance Criteria

- **AC-1:** Given ein Konto, dessen `sms_verified_number` NICHT (mehr) mit `sms_to` übereinstimmt
  (z. B. `user.json` direkt editiert, oder eine Nummer wurde geändert, ohne den Code zu bestätigen) /
  When irgendein Aufrufer über `with_user_profile`/`can_send_sms()` versucht, eine SMS an dieses
  Konto zu adressieren / Then bleibt `Settings.sms_to` leer (`None`), der Versand unterbleibt
  fail-closed — unabhängig davon, WIE der Mismatch entstanden ist.
  - Test: zwei Python-Kern-Tests. (a) `user.json` direkt mit `sms_to="+491511111111",
    sms_verified_number="+491512222222"` präparieren, `with_user_profile(user_id).sms_to` prüft
    `None`. (b) `SMSOutput(with_user_profile(user_id))._resolve_recipient()` bzw. `send()` mit
    demselben Fixture löst `ChannelBlockedError`/kein Versand aus (Test auf dem tatsächlichen
    Versandpfad, nicht nur am Schreibweg).

- **AC-2:** Given eine Nummer im Format `+49abc` (kein E.164) sowie eine gültige `+491511234567` /
  When beide per `PUT /api/auth/profile` gesendet werden / Then wird die ungültige mit `400
  {"error":"invalid_sms_number"}` abgelehnt und NICHTS gespeichert, die gültige mit `200`
  angenommen; ein leerer String (`""`) wird in beiden Fällen als „Nummer entfernen" akzeptiert.
  - Test: drei Handler-Tests (ungültig, gültig, leer) gegen `internal/handler/auth_test.go`-Muster;
    bei der ungültigen prüft der Test zusätzlich, dass `user.json` byteidentisch zum Vorher-Zustand
    bleibt.

- **AC-3:** Given ein Konto mit bereits bestätigter Nummer A / When im Profil eine neue Nummer B
  eingetragen wird / Then bleibt A wirksam (`sms_to == A`, `sms_verified == true` in der
  Profil-Antwort), B erscheint als `pending_sms_to`, und erst nach `POST /api/auth/sms/verify` mit
  dem korrekten Code wandert B nach `sms_to`, `sms_verified_number` wechselt auf B.
  - Test: Handler-Test-Sequenz (PUT → Verifikations-Datei lesen (Test-Seam liefert den Klartext, kein
    echter Versand nötig) → POST verify) prüft `sms_to`/`pending_sms_to`/`sms_verified_number` nach
    jedem Schritt.

- **AC-4:** Given ein frisch ausgestellter Code / When (a) 10 Minuten und 1 Sekunde verstreichen und
  dann verifiziert wird, (b) fünfmal hintereinander ein falscher Code gesendet wird und danach der
  RICHTIGE, (c) eine fremde, nicht zur Nummer passende Nummer über einen manipulierten Code-Hash
  simuliert wird / Then scheitert die Bestätigung in allen drei Fällen (`code_expired` bei (a) und
  nach dem fünften Fehlversuch in (b), `invalid_code` bei den ersten vier Fehlversuchen in (b) und bei
  (c)) — `sms_verified_number` bleibt in keinem der drei Fälle gesetzt.
  - Test: drei Handler-Tests mit künstlich vorgespultem `ExpiresAt` bzw. wiederholten Fehlversuchen;
    nach jedem prüft der Test `SmsVerifiedNumber == ""`.

- **AC-5:** Given ein Konto mit bereits eingetragener, unveränderter `sms_to`-Nummer / When das Profil
  mehrfach hintereinander NUR mit geändertem `display_name` gespeichert wird (das Frontend schickt
  `sms_to` dabei unverändert mit) / Then wird KEIN neuer Code versendet und KEIN Kontingent aus dem
  SMS-Limiter verbraucht — anschließend sind noch alle 3 Versuche der Mengenbremse für eine ECHTE
  Nummernänderung verfügbar.
  - Test: fünf `PUT /api/auth/profile`-Requests mit identischem `sms_to`, wechselndem `display_name`;
    Test-Seam (`sendSmsCodeFn`-Aufrufzähler) zeigt `0` Aufrufe; ein danach folgender echter
    Nummernwechsel löst noch normal einen Code aus (kein vorzeitiges 429).

- **AC-6:** Given ein Konto hat sein SMS-Code-Kontingent (3/h je Nutzer) für die eigene Kennung bereits
  ausgeschöpft / When es eine weitere, bisher unbenutzte Nummer einträgt / Then antwortet der Endpoint
  mit `429`, `Retry-After: 1200`, und `SaveUser` unterbleibt vollständig — auch für gleichzeitig
  geänderte harmlose Felder im selben Request.
  - Test: Muster `profile_mail_ratelimit_test.go` AC-1/AC-6, aber gegen die eigenständige
    `smsFloodLimiter`-Instanz — zusätzlich ein Test, der zeigt, dass das MAIL-Kontingent dabei
    unangetastet bleibt (kein geteiltes Kontingent).

- **AC-7:** Given ein Konto mit Tarif `free` / When (a) es über `PUT /api/auth/profile` eine gültige,
  neue Nummer einträgt UND (b) es anschließend `POST /api/auth/sms/resend` aufruft / Then wird die
  Nummer in (a) wie beschrieben gespeichert (pending oder direkt), aber in KEINEM der beiden Fälle
  wird `sendSmsCodeFn` aufgerufen — kein Code, keine SMS, kein Kontingentverbrauch an BEIDEN
  Entry-Points.
  - Test: Handler-Test mit `Tier: "free"`, prüft (a) `PUT`-Antwort UND Aufrufzähler `0`, danach (b)
    `POST /api/auth/sms/resend` erwartet `400 {"error":"sms_not_allowed"}` UND Aufrufzähler bleibt
    `0`.

- **AC-8:** Given zwei Konten A und B / When B in seinem eigenen Profil exakt die (echte)
  Mobilfunknummer von A einträgt / Then erhält NUR das Gerät hinter dieser Nummer den Code (an A's
  physisches Gerät, nicht an B); B kann den Code folglich nie korrekt eingeben, `sms_verified_number`
  bleibt für B's Konto leer, und aus B's Konto geht dauerhaft KEINE SMS an diese Nummer. Kein
  Endpunkt dieser Scheibe fällt auf `"default"` zurück — jede Kennung kommt aus
  `middleware.UserIDFromContext`.
  - Test: Zwei-Nutzer-Handler-Test; B trägt A's (Fixture-)Nummer ein, Test simuliert KEINE
    Code-Eingabe für B (kein Zugriff auf den Klartext außerhalb des Test-Seams), prüft danach über
    `with_user_profile("B")` bzw. den Versandpfad, dass B's Konto weiterhin fail-closed gesperrt ist.

- **AC-9:** Given ein Konto mit ausstehender (`pending_sms_to`) oder unbestätigter (`sms_to` ohne
  `sms_verified_number`) Nummer / When `sms_to` per Profil-Update auf einen leeren String gesetzt
  wird / Then werden `sms_to`, `pending_sms_to`, `sms_verified_number` und `sms_verified_at`
  gemeinsam geleert, UND die zugehörige `sms_verification.json` wird gelöscht — ein später
  irgendwie wieder auftauchender alter Code kann die entfernte Nummer nicht mehr bestätigen.
  - Test: Handler-Test; nach dem Leeren existiert `data/users/<id>/sms_verification.json` nicht mehr
    (Dateisystem-Check), alle vier Felder sind leer/`nil`.

- **AC-10:** Given eine Datenwurzel mit Konten, deren `sms_to` gesetzt, aber `sms_verified_number`
  noch nicht gesetzt ist, sowie Konten ohne `sms_to` / When das Backfill-Skript zunächst ohne, dann
  mit `--execute` läuft, und ein zweiter `--execute`-Lauf folgt / Then ändert der Dry-Run keine Datei;
  der erste `--execute`-Lauf setzt `sms_verified_number`/`sms_verified_at` NUR für Konten mit
  nicht-leerem `sms_to` und lässt alle übrigen Felder byteidentisch; der zweite `--execute`-Lauf
  ändert an den bereits nachgetragenen Konten NICHTS (Idempotenz, WERT-Vergleich vor/nach, nicht nur
  „ist gesetzt").
  - Test: Python-Skript-Test (Muster der `backfill_2271_email_verified.py`-Testreihe, sofern
    vorhanden, sonst neu analog AC-1..AC-3 dieser Vorbild-Spec) auf einem `tmp_path`-Baum mit
    gemischten Fixture-Konten.

- **AC-11:** Given der neue Deploy-Schritt (Backfill zwischen Binary-Swap und Service-Start) / When
  die Skripte auf statische Reihenfolge- und Trap-Invarianten geprüft werden / Then (a) steht der
  Backfill-Aufruf in `deploy-gregor-prod.sh` NACH `mv gregor-api.new gregor-api` und VOR `sudo
  systemctl start gregor-api`, (b) enthält `cleanup_on_exit` einen `GREGOR_API_STOPPED`-Zweig, der
  `sudo systemctl start gregor-api` auslöst, (c) steht in `auto-deploy-gregor-staging.sh` ein
  `sudo systemctl stop gregor-api-staging` VOR dem Backfill-Aufruf.
  - Test: `henemm-infra/tests/test_gregor_sms_backfill_deploy_order.py` (neu, `#
    doc-compliance-test` — reine Skript-Struktur ist nicht anders prüfbar, Muster
    `test_gregor_venv_permissions.py`: Zeilen-Index-Vergleiche, kein echter Deploy-Lauf). Drei
    Assertions exakt für (a), (b), (c) oben, je mit Zeilen-Index-Vergleich (`sync_index <
    backfill_index < start_index` analog `test_normalisierung_nach_uv_sync_und_vor_dienststart`).

- **AC-12:** Given ein vom Backfill nachgetragenes Konto, dessen ursprünglicher `sms_to`-Wert
  Leerzeichen am Rand trägt (Altbestand, `" +491511234567 "`) / When der Nutzer die Nummer später über
  `PUT /api/auth/profile` (trimmend) exakt gleich, aber ohne die Leerzeichen erneut speichert (kein
  inhaltlicher Unterschied für den Nutzer) / Then bleibt das Konto danach weiterhin sendefähig — der
  Vergleich in `with_user_profile` behandelt beide Seiten symmetrisch getrimmt, kein stiller
  Rückfall in die Aussperr-Falle.
  - Test: Python-Kern-Test: Fixture mit ungetrimmtem `sms_to`/`sms_verified_number` (Backfill-Zustand
    simuliert), danach `sms_to` auf den getrimmten Wert gesetzt (Profil-Update-Effekt simuliert,
    `sms_verified_number` bleibt unangetastet aus dem Backfill) → `with_user_profile(...).sms_to` ist
    weiterhin gesetzt (nicht `None`).

- **AC-13:** Given ein Konto mit `pending_sms_to` / When das Profil geladen wird (`GET
  /api/auth/profile`) / Then enthält die Antwort `pending_sms_to` und `sms_verified` (Bool); die
  Kontoseite zeigt daraufhin die Code-Eingabe, einen Pending-Hinweis mit „Code erneut senden" und
  ordnet `400 invalid_sms_number`/`429`/`400 invalid_code`/`400 sms_not_allowed` auf verständliche
  deutsche Fehlermeldungen ab.
  - **Wortlaut zu `invalid_code` (PO-Entscheid 2026-09-23):** Der Anzeigetext muss BEIDE Fälle
    abdecken, die hinter diesem einen Fehlercode stehen — den Tippfehler UND den abgelösten Code
    nach Neuanforderung oder Nummernwechsel. Beide sind serverseitig nicht unterscheidbar, weil
    bewusst nur EIN Hash persistiert wird (§4 „Präzisierung zum abgelösten Code", AC-16). Tragende
    Aussagen: nur der zuletzt angeforderte Code gilt, ältere verfallen, und zwar ausgelöst durch
    Neuanforderung oder Nummernwechsel.
  - Test: Go-Handler-Test für die Response-Felder; Frontend-Test (`node --test`, kein Vitest) für die
    bedingte Anzeige und die Fehlertext-Zuordnung (Muster `adresswechsel_nach_bestaetigung.md` AC-17).
    Die drei tragenden Aussagen des `invalid_code`-Texts werden als Inhalts-Wächter geprüft
    (`frontend/src/routes/account/__tests__/profile_save_error.test.ts`, `assert.match` auf die
    Aussagen, nicht auf den Satz byteweise — der Wortlaut darf redaktionell wandern).

- **AC-14:** Given dieselbe Profil-Antwort mit `sms_verified: false, pending_sms_to: "+49..."` / When
  die Bausteine, die den SMS-Kanalstatus tatsächlich rendern — `VTBriefingChannels.svelte`
  (context-bewusst, `context="route"|"vergleich"`, aus `VersandTab.svelte` in BEIDEN Kontexten
  eingehängt) und `EditReportConfigSection.svelte` (Trip-Editor, `context="route"` fest verdrahtet,
  kein Dual-Context-Baustein) — den SMS-Kanal anzeigen / Then zeigen beide „eingetragen,
  unbestätigt" statt „SMS aktiv" — bei `VTBriefingChannels.svelte` identisch unter `context="route"`
  UND `context="vergleich"`. Beide Bausteine beziehen den Statustext ausschließlich aus dem
  kontextfreien Helfer `channelConnectionStatus.ts` (kein eigener Textzweig je Baustein);
  `channelContactLabel.ts` liefert ergänzend die Kontakt-Beschriftung, ebenfalls kontextfrei.
  `WeatherMetricsTab.svelte` rendert an KEINER Stelle einen SMS-Kanalstatus — der Reiter
  konfiguriert nur, welche Metriken je Kanal erscheinen (`channelBuckets`), nicht ob ein Kanal
  sendebereit ist — und ist deshalb KEIN Pflicht-Baustein dieser AC; die dortige Typ-Erweiterung um
  `sms_verified`/`pending_sms_to` (Zeile 244) bleibt bestehen, weil sie beschreibt, was der
  Profil-Endpunkt liefert, löst aber keine Render-Verzweigung aus (Korrektur nach Adversary-Finding
  F001, siehe Changelog).
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts`
    rendert `VTBriefingChannels.svelte` echt (SSR) je einmal mit `context="route"` und einmal mit
    `context="vergleich"` und prüft `data-testid="channel-status-sms"` auf „eingetragen,
    unbestätigt" sowie Identität zwischen beiden Kontexten (Pendant-Regel, CLAUDE.md); zusätzlich
    ein direkter Test des kontextfreien Helfers `channelConnectionStatus` (mit Gegenprobe: eine
    bestätigte Nummer bleibt „hinterlegt"). Für `EditReportConfigSection.svelte` (Trip-Editor) gilt
    derselbe Nachweis in eigener Datei:
    `frontend/src/lib/components/edit/__tests__/sms_unbestaetigt_trip_editor.test.ts` rendert die
    Komponente echt (SSR, `profileOverride`) und prüft für die unbestätigte Nummer (a) den
    Status-Text `channel-status-sms` = „eingetragen, unbestätigt", (b) die Baustein-eigene
    Kanal-Verfügbarkeit (Zeile 123) über `disabled` der SMS-Checkbox und (c) den Textinhalt des
    `channel-sms-hint`-Zweigs (Zeile 427, „nicht bestätigt" — nicht „fehlt", weil drei Zweige
    dasselbe Testid tragen), dazu die Gegenprobe mit `sms_verified: true` (schaltbar, kein Hinweis).

- **AC-15:** Given ein Router, der ohne `GZ_ENV=staging` gebaut wurde (Produktionslage) / When `POST
  /api/auth/sms/staging-code` aufgerufen wird / Then antwortet er `404`. Given `GZ_ENV=staging` und
  eine angemeldete Sitzung mit `pending_sms_to` gesetzt / When derselbe Endpunkt aufgerufen wird /
  Then liefert er den Klartext-Code FÜR DIESES Konto, unabhängig vom Body-Inhalt — ein zweites,
  fremdes Konto lässt sich über diesen Endpunkt NICHT abfragen (er liest ausschließlich die eigene
  Sitzungskennung).
  - Test: drei Handler-Tests — (a) `GZ_ENV` ungesetzt → 404 und keine `sms_verification.json`
    entsteht; (b) `GZ_ENV=staging`, Body enthält bewusst eine FREMDE `username`/`user_id` → die
    Antwort betrifft trotzdem das eigene, angemeldete Konto (Body wird ignoriert); (c) danach macht
    der gelieferte Code den regulären `POST /api/auth/sms/verify` erfolgreich.

- **AC-16:** Given ein Konto hat eine ausstehende Nummer B / When vor deren Bestätigung eine DRITTE
  Nummer C eingetragen wird / Then ersetzt C vollständig B als `pending_sms_to`, der für B ausgestellte
  Code (samt Fehlversuchszähler) ist wertlos — eine spätere Eingabe des B-Codes scheitert mit
  `400 {"error":"invalid_code"}`, weil `sms_verification.json` bereits auf C zeigt und der B-Code
  gegen den dort liegenden Hash nicht passt. `sms_verified_number` bleibt dabei auf der alten,
  bestätigten Nummer A; der für C ausgestellte Code bestätigt normal.
  - Test: Handler-Test-Sequenz: PUT (B) → PUT (C) → POST verify mit dem für B ausgestellten
    (Test-Seam-)Code → `400 invalid_code`; POST verify mit dem für C ausgestellten Code → `200`.

- **AC-17 (Live-E2E):** Given ein Testkonto auf Staging (SMS-fähiger Tarif) / When es im Browser
  (a) eine neue Nummer im Profil einträgt, (b) über `POST /api/auth/sms/staging-code` den
  Klartext-Code für das eigene Konto holt (Ersatz für echten SMS-Empfang), (c) den Code in der
  Kontoseite einträgt und bestätigt / Then zeigt die Kontoseite danach die Nummer als „bestätigt" an,
  der Pending-Hinweis verschwindet — der komplette reale Ablauf einmal durch den Browser.
  - Test: neue Playwright-Spec `frontend/e2e/feat-2406-sms-verify.spec.ts` gegen Staging (Muster
    `fix-2271-email-verify-gate.spec.ts`), Teil des `/e2e-verify`-Laufs.

## Test Plan

Testschichten und die dafür in dieser Lieferung tatsächlich angelegten Dateien (Stand
`/50-implement`, gegen den Ist-Stand per `ls`/`grep` geprüft, nicht aus dem Gedächtnis).

### Kern-Schicht — Go

- `internal/handler/sms_verification_test.go` — AC-2, AC-3, AC-4, AC-7, AC-8, AC-9, AC-13, AC-16
  (externes Testpaket `handler_test`, echter `router.New`, Muster `verify_resend_test.go`)
- `internal/handler/sms_verify_ratelimit_test.go` — AC-5, AC-6 (Mengenbremse, eigenständige
  `smsFloodLimiter`-Instanz)
- `internal/handler/sms_staging_code_test.go` — AC-15 (Staging-Testweg, nur eigene Sitzung)
- Teil des CI-Checks `go-test` (einer der sechs Pflicht-Checks der CI-Ampel)

### Kern-Schicht — Python

- `tests/test_sms_versand_nur_bestaetigte_nummer.py` — AC-1, AC-8 (Python-Teil), AC-12
  (Fail-closed-Sperre an der Wirkstelle `with_user_profile`, Sentinel statt Netz-Mock)
- `tests/test_sms_verification_code_endpoint.py` — §8, interner Endpunkt
  `POST /api/_internal/sms/verification-code`
- `tests/test_sms_verified_backfill.py` — AC-10 (Backfill-Skript, echter Prozess gegen `tmp_path`,
  relativ zur Testdatei aufgelöst)
- Befehl (aus den Datei-Kopfkommentaren übernommen, je Datei identisch):
  `uv run pytest <datei> -v -rA --disable-socket`

### Kern-Schicht — Frontend (`node --test`, KEIN Vitest)

- `frontend/src/lib/components/shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts`
  — AC-14 und der kontextfreie Teil von AC-13: prüft den kontextfreien Helfer
  `channelConnectionStatus` sowie `VTBriefingChannels.svelte`, je einmal mit `context="route"` und
  einmal mit `context="vergleich"` gerendert (`WeatherMetricsTab.svelte` rendert keinen
  SMS-Kanalstatus und ist seit der Korrektur nach Adversary-Finding F001 kein Pflicht-Baustein von
  AC-14 mehr, siehe Changelog).
- `frontend/src/lib/components/edit/__tests__/sms_unbestaetigt_trip_editor.test.ts` — AC-14 für den
  zweiten rendernden Baustein `EditReportConfigSection.svelte` (Trip-Editor): echtes SSR-Rendern
  über `profileOverride`, geprüft werden Status-Text, die Baustein-eigene `disabled`-Steuerung der
  SMS-Checkbox (Zeile 123) und der Textinhalt des `channel-sms-hint`-Zweigs (Zeile 427), je mit
  Gegenprobe für die bestätigte Nummer. Beide Wirkstellen sind per Rückdreh-Gegenprobe belegt (zwei
  getrennte Mutationen, jeweils genau ein roter Test; Protokoll in
  `docs/artifacts/feat-2406-sms-verifikation/test-green-output.txt`).
- `frontend/src/lib/components/shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts`
  — AC-6 (aus #1510, Regressionsnetz): Testid-Parität `channel-status-sms` zwischen
  `VTBriefingChannels.svelte` und `EditReportConfigSection.svelte`, geprüft für ein vollständig
  bestätigtes Profil. Den unbestätigten Fall für `EditReportConfigSection.svelte` deckt
  `sms_unbestaetigt_trip_editor.test.ts` ab (siehe oben).
- `frontend/src/routes/account/__tests__/sms_verify_kontoseite.test.ts` — AC-13 (Frontend-Teil:
  Code-Eingabe, Pending-Hinweis, „Code erneut senden", echtes SSR-Rendern der Kontoseite)
- `frontend/src/routes/account/__tests__/profile_save_error.test.ts` — AC-13 (Inhalts-Wächter für
  die drei tragenden Aussagen des `invalid_code`-Anzeigetexts, PO-Entscheid 2026-09-23)

### Infra-Struktur (`# doc-compliance-test`, kein echter Deploy-Lauf)

- `henemm-infra/tests/test_gregor_sms_backfill_deploy_order.py` — AC-11 (Zeilen-Index-Vergleich der
  Deploy-Reihenfolge und der Trap-Erweiterung, Muster `test_gregor_venv_permissions.py`)

### Live-E2E (nur im `/e2e-verify`-Lauf gegen Staging, nicht Teil des Kern-Testlaufs)

- `frontend/e2e/feat-2406-sms-verify.spec.ts` — AC-17 (kompletter Ablauf im Browser: Nummer
  eintragen → Staging-Code holen → bestätigen → Anzeige „bestätigt")

## Definition of Done

- [ ] Versand adressiert ausschließlich eine bestätigte Nummer — `with_user_profile`/`can_send_sms()`
  liefern `sms_to` nur bei `sms_verified_number == sms_to` (AC-1, AC-8, AC-12)
- [ ] E.164-Formatprüfung sitzt VOR jedem Schreibzugriff; ungültiges Format wird abgelehnt, nichts
  wird gespeichert (AC-2)
- [ ] Pending-Verhalten korrekt: eine bestätigte Nummer bleibt wirksam, eine neue wartet als
  `pending_sms_to` bis zur Bestätigung; eine dritte Nummer ersetzt eine ausstehende vollständig
  (AC-3, AC-16)
- [ ] Code-Härtung greift: Ablauf nach 10 Minuten, Sperre nach 5 Fehlversuchen, Nummernbindung beim
  Einlösen (AC-4)
- [ ] Kein Code-Versand bei reinem Feld-Rauschen (unverändertes `sms_to` bei anderen
  Profil-Änderungen), kein Kontingentverbrauch dabei (AC-5)
- [ ] Mengenbremse (3 Code-Versuche/Stunde je Nutzer, eigenständige Instanz ohne geteiltes
  Mail-Kontingent) greift vor `SaveUser` (AC-6)
- [ ] Tier-Gate greift vor JEDEM Code-Versand an beiden Entry-Points — Profil-Update UND Resend
  (AC-7)
- [ ] Zwei-Nutzer-Nachweis: aus Konto B geht dauerhaft keine SMS an eine von B nur behauptete,
  tatsächlich A gehörende Nummer; kein Endpunkt fällt auf `"default"` zurück (AC-8)
- [ ] Entfernen einer Nummer räumt `sms_to`/`pending_sms_to`/`sms_verified_number`/`sms_verified_at`
  und die Verifikationsdatei vollständig auf (AC-9)
- [ ] Backfill-Skript trägt Bestandskonten nach — Dry-Run ändert nichts, `--execute` ist idempotent,
  Normalisierungs-Symmetrie hält auch nach Trimm-Differenzen (AC-10, AC-12)
- [ ] Deploy-Reihenfolge steht: Backfill zwischen Binary-Swap und Service-Start (Prod),
  `GREGOR_API_STOPPED`-Trap-Erweiterung, vorgezogener Stop in Staging (AC-11)
- [ ] Frontend zeigt Pending-/Bestätigt-Status verständlich und kontext-übergreifend identisch unter
  `context="route"` und `context="vergleich"`; der Trip-Editor (`EditReportConfigSection.svelte`)
  sperrt den SMS-Schalter bei unbestätigter Nummer und nennt den Grund (AC-13, AC-14)
- [ ] Staging-Testweg liefert den Klartext-Code ausschließlich für die eigene, angemeldete Sitzung
  und antwortet außerhalb `GZ_ENV=staging` mit 404 (AC-15)
- [ ] Live-E2E-Spec durchläuft den kompletten Ablauf gegen Staging im Browser (AC-17)
- [ ] Alle in `## Test Plan` gelisteten Testschichten sind grün

## Known Limitations

- **Tarifwechsel allein löst noch keinen Code aus.** Ein Free-Konto, das eine Nummer einträgt (kein
  Versand, AC-7) und später auf `standard`/`premium` wechselt, muss die Nummer NICHT erneut
  speichern — der reguläre Weg zurück ist der „Code erneut senden"-Knopf im Pending-Hinweis (§4), der
  das Tier-Gate zum Zeitpunkt des Klicks erneut prüft und bei SMS-fähigem Tarif normal funktioniert.
  Kein aktives Sicherheitsproblem, nur eine UX-Kante (der Nutzer muss aktiv „erneut senden" klicken,
  statt dass ein Upgrade automatisch einen Code auslöst).
- **Backfill übernimmt auch fremd eingetragene Bestandsnummern** (wie beim E-Mail-Vorbild) — die Lücke
  schließt sich nur für künftige Änderungen.
- **Der Prozess-lokale Limiter-State** (`smsFloodLimiter`) überlebt einen Neustart von `gregor-api`
  nicht — akzeptiert, analog `profile_mail_ratelimit.md`.
- **Kein SMS-Aliasing-Schutz:** unterschiedliche Schreibweisen derselben physischen Nummer (z. B. mit/
  ohne führende `0` vor der Landesvorwahl außerhalb von E.164) werden nicht erkannt — außerhalb des
  Scopes dieser Scheibe (S5, Quoten/Aliasing).
- **`sms_verification.json` wird nie exportiert** (DSGVO-Export, `exportErlaubteDateienExakt`,
  `internal/store/user.go:263-276`, ist eine exakte Positivliste, die neue Datei fehlt dort bewusst —
  wie beim E-Mail-Token). Die drei neuen `user.json`-Felder erscheinen automatisch im Export
  (`exportFilterUserJSON` reicht generisch alles außer der Geheimnisliste durch), ohne Codeänderung an
  der Export-Logik.
- **Die vorbestehende, fehlerhafte Backup-Pfad-Angabe** in der Fehlermeldung des bestehenden
  `migrate_1250`-Deploy-Schritts (`deploy-gregor-prod.sh`, nennt `$REPO_DIR/.backups` statt des
  tatsächlichen `root.parent/.backups`) wird durch diese Spec NICHT korrigiert — außerhalb des Scopes,
  nur die NEUE Fehlermeldung des SMS-Backfill-Schritts bekommt den korrekten Pfad.
- **Der Metrik-Reiter (`WeatherMetricsTab.svelte`) zeigt bewusst keinen SMS-Bestätigungsstand.** Der
  Reiter konfiguriert nur, welche Metriken je Kanal erscheinen (`channelBuckets`); ob ein Kanal
  sendebereit ist, steht im Versand-Reiter (`VTBriefingChannels.svelte`) und im Trip-Editor
  (`EditReportConfigSection.svelte`). Die Typ-Erweiterung um `sms_verified`/`pending_sms_to` in
  `WeatherMetricsTab.svelte` (Zeile 244) bleibt bestehen, weil sie beschreibt, was der
  Profil-Endpunkt liefert — sie löst aber keine eigene Anzeige aus (AC-14-Korrektur nach
  Adversary-Finding F001, siehe Changelog).
## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die entscheidende Frage ist, ob diese Scheibe eine dokumentierte Entscheidung
  zurücknimmt oder einschränkt — das tut sie nicht. ADR-0062 hat bereits entschieden, dass der
  Python-Core Go-Aufrufe über `X-GZ-Core-Auth` authentifiziert; ADR-0076 hat bereits entschieden, dass
  Go sich über einen internen Core-Endpunkt an eine Python-seitige Logik andockt, statt sie in Go
  nachzubauen — genau dieses Muster wendet der neue `POST /api/_internal/sms/verification-code`-
  Endpunkt an (Go generiert/prüft den Code, Python bleibt der einzige seven.io-Transport). Ein
  zweiter seven.io-Client in Go WÄRE die Abweichung von diesem Muster; das Unterlassen ist Konformität,
  keine neue Entscheidung. `docs/adr/README.md` wird deshalb NICHT angefasst — das hält
  `tests/test_adr_index_drift.py` vollständig aus dieser Scheibe heraus.
  **Hinweis zur Prüfmethode:** Die höchste vergebene ADR-Nummer (0077) wurde gegen den lokalen
  Worktree-Stand geprüft, NICHT gegen `git show origin/main:docs/adr/README.md` (CLAUDE.md-Vorgabe für
  neue ADR-Nummern) — weil diese Spec auf „keine ADR nötig" landet, ist die Nummernfrage irrelevant;
  sollte `/50-implement` wider Erwarten doch ein ADR für nötig befinden, MUSS die Nummer dort frisch
  gegen `origin/main` geprüft werden.

## Changelog

- 2026-09-22: Initial spec created (Issue #2406, S3 aus #2153, Epic #2138). Kontext-Dokument
  `docs/context/feat-2406-sms-verifikation.md`.
- 2026-09-22: Nach Advisor-Review 1 überarbeitet — Deploy-Reihenfolge und Trap-Erweiterung
  konkretisiert (Positionsabweichung von `migrate_1250_briefings.py` begründet), `smsFieldChanged`-
  Vergleich gegen `PendingSmsTo` erweitert, Normalisierungs-Symmetrie AC-12 ergänzt, eigenständige
  Limiter-Instanz statt geteiltem Mail-Kontingent.
- 2026-09-22: Nach Advisor-Review 2 korrigiert — Nil-Deref in der `smsFieldChanged`-Prüfung behoben,
  „### Affected Files"-Tabelle nachgetragen, Live-E2E-Playwright-AC-17 ergänzt, Tier-Gate auf den
  Resend-Endpoint ausgeweitet (AC-7 deckt jetzt beide Entry-Points, Known-Limitation-Widerspruch
  aufgelöst), Frontend-Dateizuordnung gegen den Ist-Stand geprüft (`EditReportConfigSection.svelte`
  ist ein Trip-only-Wrapper, kein Dual-Context-Baustein; `channelConnectionStatus.ts`/
  `channelContactLabel.ts` sind kontextfrei), AC-11-Test konkret benannt (`#doc-compliance-test`,
  Zeilen-Index-Muster `test_gregor_venv_permissions.py`), Typo korrigiert.
- 2026-09-22 (`/50-implement`): **AC-16 präzisiert — ein abgelöster Code liefert `invalid_code`
  statt `code_expired`**, weil mit einem einzigen persistierten Hash der abgelöste Code von einem
  Rateversuch mechanisch nicht unterscheidbar ist; ein zweiter Hash nur zur Unterscheidung des
  Fehlertextes wäre zusätzliche Angriffsfläche ohne Nutzerwert (RED-Befund 1 des Kontext-Dokuments).
  `§4` um diese Präzisierung und um die in AC-4c geforderte, dort bislang nicht genannte
  Nummernbindung beim Einlösen ergänzt (RED-Befund 3).
- 2026-09-22 (`/50-implement`): **§2 Änderungs-Prädikat präzisiert** — der No-op-Vergleich gegen
  `PendingSmsTo` gilt nur für eine nicht-leere Nummer (`newSmsTo == "" || newSmsTo !=
  user.PendingSmsTo`). Der wörtliche Ausdruck der Spec verschluckte das Entfernen (AC-9), sobald
  `PendingSmsTo` selbst leer war — beide sind dann gleich, und die Aufräum-Änderung fiel aus.
- 2026-09-22 (`/50-implement`): **§11 Deploy-Schritt bekommt einen `[ -f … ]`-Wächter** in beiden
  Skripten. `henemm-infra` ist ein Arbeitsbaum, aus dem der Cron direkt liest; ein Deploy aus einem
  gregor-Stand ohne das Backfill-Skript (Scheibe noch nicht gemerged, parallele Sitzungen) darf nicht
  fail-closed abbrechen. Existiert das Skript, gilt fail-closed unverändert. Der infra-Test prüft
  deshalb die `python3 …`-AUFRUF-Zeile (nicht die erste Zeile mit dem Dateinamen) und zusätzlich, dass
  der Wächter im selben Fenster liegt — eine Verschärfung, keine Aufweichung.
- 2026-09-23 (`/50-implement`, PO-Entscheid): **AC-13 um die Wortlaut-Vorgabe zu `invalid_code`
  ergänzt** — der Anzeigetext deckt beide Fälle ab (Tippfehler UND abgelöster Code nach
  Neuanforderung/Nummernwechsel), weil die beiden serverseitig nicht unterscheidbar sind
  (Querverweis §4/AC-16). Die drei tragenden Aussagen sind jetzt von einem Inhalts-Wächter in
  `profile_save_error.test.ts` bewacht; die Rückdreh-Gegenprobe auf den alten Wortlaut ließ zuvor
  keinen Test rot werden (`/code/i` in `sms_verify_kontoseite.test.ts` passt auf beide Fassungen).
- 2026-09-23: **Pflicht-Sektionen `## Scope`, `## Definition of Done`, `## Test Plan` nachgetragen**
  (CI-Gate `ci_spec_gate.py` verlangt sie, Regex `^#{2,3}\s*<Pattern>` gegen die Sektionsüberschrift —
  geprüft statisch am Quelltext des Gates unter
  `agent-os-openspec/3.30.4/scripts/ci_spec_gate.py:53-58/168`, siehe Hinweis unten). `## Scope`
  fasst `## Estimated Scope`/`### Affected Files` (enthalten) und `## Abgrenzung` (nicht enthalten)
  zusammen, ohne sie zu ersetzen. `## Test Plan` benennt die real angelegten Testdateien je Schicht
  (gegen den Ist-Stand per `ls`/`grep` geprüft) mit den aus den jeweiligen Datei-Kopfkommentaren
  übernommenen Ausführungsbefehlen. `## Definition of Done` leitet eine Checkliste rein aus den
  bestehenden AC-1..AC-17 ab. Keine inhaltliche Änderung an einer bestehenden AC, keine Nummerierung
  verändert. **Offener Befund aus dieser Nacharbeit (kein neuer, nur sichtbar gemacht):** für
  `WeatherMetricsTab.svelte` (AC-14) wurde keine eigens benannte SMS-Dual-Context-Testdatei gefunden —
  siehe Hinweis im `## Test Plan`-Abschnitt „Kern-Schicht — Frontend". **Der Gate-Lauf selbst konnte
  nicht ausgeführt werden** (dieser Bearbeitung stand kein Bash-Werkzeug zur Verfügung) — die
  Sektionsanforderung wurde ausschließlich statisch aus dem Gate-Quelltext abgeleitet, nicht durch
  einen tatsächlichen Lauf bestätigt.
- 2026-09-23 (Adversary-Finding F001, Tech-Lead-Korrektur): **AC-14 korrigiert** — die Zusicherung
  nannte `WeatherMetricsTab.svelte` fälschlich als zweiten Pflicht-Baustein, der den SMS-Kanalstatus
  „eingetragen, unbestätigt" rendert. Nachgemessen (Orchestrator, gegen den Ist-Stand):
  `WeatherMetricsTab.svelte` lädt `profile` (Zeile 498-510), liest es aber an keiner Stelle für eine
  Kanal-Status-Anzeige — der Reiter konfiguriert nur, welche Metriken je Kanal erscheinen
  (`channelBuckets`, Zeilen 261/464/771), nicht ob ein Kanal sendebereit ist. Der **offene Befund aus
  dem vorherigen Changelog-Eintrag ist damit erledigt** — es fehlte kein Test, die AC-Zusicherung
  selbst war falsch. AC-14 nennt jetzt `VTBriefingChannels.svelte` (dual-context, Pflicht-
  Testnachweis für beide Kontexte) und `EditReportConfigSection.svelte` (Trip-Editor, `context="route"`
  fest verdrahtet) als die tatsächlich rendernden Bausteine, dazu die kontextfreien Helfer
  `channelConnectionStatus.ts`/`channelContactLabel.ts`. Die `- Test:`-Zeile benennt jetzt real
  existierende Testdateien: `sms_unbestaetigt_kanalstatus.test.ts` (VTBriefingChannels + Helfer,
  Pfad per `Glob` geprüft) sowie die indirekte Deckung von `EditReportConfigSection.svelte` über
  denselben Helferaufruf — mit der ehrlichen Einschränkung, dass dessen lokale `disabled`-Bedingung
  und der `channel-sms-hint`-Zweig keinen eigenen Render-Test in dieser Scheibe haben (neu in
  `## Known Limitations`). Folgeänderungen: `### Affected Files`-Zeile zu `WeatherMetricsTab.svelte`
  (Dual-Context-Klausel entfernt, Begründung ergänzt), `## Scope`-Aufzählung (`WeatherMetricsTab.svelte`
  durch `EditReportConfigSection.svelte` ersetzt), `## Test Plan`-Abschnitt „Kern-Schicht — Frontend"
  (Offener-Befund-Absatz durch die korrigierte Darstellung ersetzt, `channel_checkbox_dedupe_render.test.ts`
  als weitere Testdatei ergänzt), zwei neue `## Known Limitations`-Bullets. **Keine neue UI wurde
  gebaut** — die Typ-Erweiterung in `WeatherMetricsTab.svelte` (Zeile 244) bleibt unverändert bestehen,
  weil sie kostenlos beschreibt, was der Profil-Endpunkt liefert. AC-1..AC-13 und AC-15..AC-17
  bleiben wörtlich unverändert, Nummerierung unverändert (weiterhin AC-1..AC-17).
- 2026-09-23 (Adversary-Nachtrag zu AC-14): **Die im vorherigen Eintrag als Known Limitation
  eingetragene UI-Testlücke ist geschlossen und die Limitation damit gestrichen.** Neue Testdatei
  `frontend/src/lib/components/edit/__tests__/sms_unbestaetigt_trip_editor.test.ts` (`node --test`,
  echtes SSR-Rendern von `EditReportConfigSection.svelte` über `profileOverride`) bewacht jetzt die
  beiden Baustein-eigenen Wirkstellen im Trip-Editor: die lokale Kanal-Verfügbarkeit (Zeile 123,
  `disabled` der SMS-Checkbox) und den `channel-sms-hint`-Zweig (Zeile 427); zusätzlich wird der
  Status-Text `channel-status-sms` jetzt auch in diesem Baustein gemessen statt nur über den
  gemeinsamen Helfer argumentiert. Der Hinweis wird über seinen TEXT geprüft, nicht über die bloße
  Anwesenheit des Testids — drei sich ausschließende Zweige tragen dasselbe Testid, eine
  Anwesenheitsprüfung bliebe bei einer Rückdrehung grün. Rückdreh-Gegenprobe (reiner String-Ersatz,
  externe Sicherungskopie, md5sum-Beleg, keine git-Kommandos): Entfernen von
  `&& !!profile?.sms_verified` in Zeile 123 macht **genau** den `disabled`-Test rot (Hinweis-Test
  bleibt grün); Neutralisieren der Bedingung in Zeile 427 macht **genau** den Hinweis-Test rot
  (`disabled`-Test bleibt grün) — zwei getrennte Wächter für zwei getrennte Wirkstellen. Die übrigen
  Tests rund um Komponente und Helfer (`channel_checkbox_dedupe_render.test.ts`,
  `sms_unbestaetigt_kanalstatus.test.ts`, `channel_connection_status.test.ts`,
  `report_config_uses_shared_schedule.test.ts`) blieben unter beiden Mutationen grün — das belegt,
  dass die vorbestehende Abdeckung diese Stellen tatsächlich nicht erreichte. Protokoll (rot + grün,
  volle Ausgabe): `docs/artifacts/feat-2406-sms-verifikation/test-green-output.txt`. Folgeänderungen
  in dieser Spec: AC-14 `- Test:`-Zeile, `## Test Plan` („Kern-Schicht — Frontend", zwei Bullets),
  Abnahme-Checkliste. **Keine Logikänderung an `EditReportConfigSection.svelte`** — die Bedingung war
  bereits korrekt, nur unbewacht. Die zweite Known Limitation (Metrik-Reiter zeigt bewusst keinen
  SMS-Bestätigungsstand) bleibt bestehen. ACs bleiben wörtlich unverändert (weiterhin AC-1..AC-17).
