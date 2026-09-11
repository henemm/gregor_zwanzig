---
entity_id: email_verify_vorbereitung_2304
type: module
created: 2026-09-11
updated: 2026-09-11
status: draft
version: "1.0"
tags: ["auth", "email-verification", "epic-2138"]
---

# E-Mail-Verifikation: Vorbereitung vor der Login-Pflicht (#2304)

## Approval

- [ ] Approved

## Purpose

Bereitet die künftige Login-Pflicht aus #2271 vor, ohne selbst irgendjemanden auszusperren: trägt bestehende Konten in Produktion und Staging als bestätigt nach, lässt Magic-Link- und Google-OAuth-Logins die Bestätigung bei Adressgleichheit selbst herstellen, und schafft einen Resend-Endpoint sowie einen staging-only Testweg, damit auch zur Laufzeit neu erzeugte Test-Konten überhaupt bestätigbar werden. Scheibe 1 von 2 aus #2146/#2271 (Epic #2138); die Scharfschaltung selbst ist ausdrücklich nicht Teil dieser Spec.

## Source

- **File:** `scripts/backfill_2271_email_verified.py` (neu), `internal/handler/auth.go` (Resend-Handler), `internal/handler/auth_magic.go`, `internal/handler/auth_oauth.go` (Selbstheilung), neue Handler-Datei für den staging-only Testweg, `internal/router/router.go` + `internal/middleware/auth.go` (Routing/Allowlist)
- **Identifier:** `main` (Backfill-Skript), `ResendVerificationHandler` (neu), `dispatchVerificationMail`, `VerifyEmailHandler`, `issueSession`

> Vier Bausteine, ein Ziel: niemand wird durch die spätere Login-Pflicht ausgesperrt.

## Abgrenzung

Nicht Teil dieser Scheibe — gehört zu #2271 („Scharfschaltung"):

- Das Login-Gate selbst (Deny-Zweig in `issueSession`), das unbestätigte Passwort- und Passkey-Logins blockiert.
- Das Entfernen des Auto-Logins bei der öffentlichen Passkey-Registrierung (Anmeldeweg 6).
- Die Frontend-Fehlermeldung „E-Mail nicht bestätigt" im Login-Flow.
- Das neue ADR, das ADR-0060 / `docs/specs/modules/session_allowlist.md` fortschreibt.
- Die noch offene PO-Entscheidung zur Antwortform des künftigen Gates (403 mit Klartext-Fehler vs. einheitliches 401) — bleibt #2271 vorbehalten und wird hier nicht vorweggenommen.

Diese Spec beschreibt ausschließlich Bausteine, die für sich harmlos sind: Sie schalten nichts scharf und sperren niemanden aus.

## Estimated Scope

- **LoC:** ~230
- **Files:** 7
- **Effort:** medium

### Affected Files

| File | Change Type |
|------|-------------|
| `scripts/backfill_2271_email_verified.py` | CREATE |
| `internal/handler/auth.go` | MODIFY (Resend-Handler) |
| `internal/handler/auth_magic.go` | MODIFY (Selbstheilung) |
| `internal/handler/auth_oauth.go` | MODIFY (Selbstheilung + Redirect-Vorprüfung) |
| neue Handler-Datei staging-only Testweg | CREATE |
| `internal/router/router.go` + `internal/middleware/auth.go` | MODIFY (Routing/Allowlist) |
| `internal/handler/export_test.go` | MODIFY (Testbrücke `ObserveVerificationMailForTest` zur bestehenden Naht `sendVerificationMailFn`; trägt den AC-7-Nachweis, weil er gegen den echten, voll verdrahteten Router laufen muss und `package handler_test` sonst nicht an die paketprivate Naht käme) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dispatchVerificationMail` (`internal/handler/auth.go:760`) | Go-Funktion | Erzeugt und versendet das Verifikations-Token; vom neuen Resend-Endpoint aufgerufen — keine neue Versandlogik nötig |
| `VerifyEmailHandler` (`internal/handler/auth.go:434`) | Go-Handler | Einzige Stelle, die `EmailVerifiedAt` per Token setzt; nimmt auch das vom staging-only Testweg gelieferte Token entgegen |
| `FindUserByEmail` (`internal/store/user.go:428`) | Go-Store-Methode | Löst beim Magic-Link-Login (`auth_magic.go:64`) die nachgewiesene Adresse auf ein Konto auf — Grundlage für den Adressabgleich in der Selbstheilung |
| `NewIPRateLimiter` (`internal/router/router.go`, Muster `forgotLimiter`) | Go-Middleware-Fabrik | Begrenzt den neuen Resend-Endpoint auf 5 Aufrufe/Stunde je IP, wie beim bestehenden Forgot-Password-Pfad |
| Public-Allowlist (`internal/middleware/auth.go:50-63`) | Go-Middleware-Konfiguration | Muss den Resend-Endpoint per **exaktem** Pfad freischalten; der staging-only Testweg darf NICHT unter einem bereits pauschal freigeschalteten Präfix (`/api/debug/`, `/api/internal/`, `/api/webhooks/telegram/`) liegen — sonst wird er trotz Absicht öffentlich aufrufbar |

## Implementation Details

**1. Nachtrag-Skript.** `scripts/backfill_2271_email_verified.py`, neu, nach dem Vorbild von `scripts/migrate_1219_email_verified.py` (Dry-Run-Default, `--execute`, Pflicht-`--root`, tar.gz-Backup vor jedem `--execute`-Lauf, Read-Modify-Write, Idempotenz — bereits gesetztes `email_verified_at` wird übersprungen). Anders als das Vorbild: keine feste Positivliste, sondern **alle** Konten unter `--root`, deren `user.json` noch kein `email_verified_at` trägt. Wird je einmal mit `--execute` gegen Produktion (`/var/lib/gregor/users/`, betrifft nur `default`) und Staging (`/var/lib/gregor-staging/users/`, betrifft alle 63 Bestandskonten) gefahren.

**2. Selbstheilung bei Magic-Link und Google-OAuth.** In `auth_magic.go:186` (nach erfolgreicher Code-Prüfung, vor `issueSession`) und `auth_oauth.go:181` (nach `FindUserByOAuthSub`/`createOAuthUser`, vor `issueSession`) wird der Nutzer geladen, die nachgewiesene Adresse mit der effektiven Kontaktadresse verglichen (`user.MailTo`, ersatzweise `user.Email` — dieselbe Vorrangregel wie `dispatchVerificationMail`, `auth.go:761-764`) und bei Übereinstimmung `EmailVerifiedAt` per Read-Modify-Write gesetzt, falls es noch nicht gesetzt ist. Bei Abweichung (z. B. `MailTo` wurde im Profil auf eine andere Adresse gestellt) bleibt das Feld unangetastet — die Anmeldung selbst ist davon unabhängig und gelingt in jedem Fall, S1 sperrt noch nichts.

**3. Resend-Endpoint.** `POST /api/auth/verify-email/resend`, Nutzlast `{"username": "..."}` (keine Adresse — verhindert Adress-zu-Konto-Zuordnung, analog `ForgotPasswordHandler`). Antwortet immer `200 {"status":"ok"}`, unabhängig davon, ob das Konto existiert, bereits bestätigt ist oder keine Kontaktadresse hinterlegt hat (enumerationsfrei, R4). Bei existierendem, unbestätigtem Konto mit Kontaktadresse ruft er `dispatchVerificationMail` — keine neue Versandlogik. Ratenlimit `NewIPRateLimiter(5, time.Hour)` wie `forgotLimiter`. Braucht einen **exakten** Eintrag in der Public-Allowlist (`internal/middleware/auth.go:51-59`), z. B. `r.URL.Path == "/api/auth/verify-email/resend"`.

Wichtig für AC-7 ohne Live-Mailversand: `dispatchVerificationMail` persistiert das Token via `SaveVerificationToken` bereits bei `auth.go:787` — **vor** den SMTP-Konfigurationsprüfungen (`:801-808`). Der Token-Nachweis ist damit deterministisch prüfbar, ohne dass ein SMTP-Server konfiguriert sein muss.

**4. Staging-Testweg.** Neuer Handler, registriert nur wenn `os.Getenv("GZ_ENV") == "staging"` (Muster `router.go:215`, #830). **Anmeldepflichtig** — dafür darf der Pfad NICHT unter einem der pauschal freigeschalteten Präfixe liegen (`/api/debug/`, `/api/internal/`, `/api/webhooks/telegram/` — `middleware/auth.go:61-63`); ein Pfad wie `/api/debug/...` wäre trotz Zugriffsschutz-Absicht öffentlich aufrufbar. Der endgültige Routenname ist Implementierungsdetail, muss aber nachweislich außerhalb dieser drei Präfixe liegen und darf NICHT in die Public-Allowlist eingetragen werden. Der Handler nimmt eine Ziel-`username` aus dem Request entgegen, erzeugt und persistiert ein Token über denselben Mechanismus wie `dispatchVerificationMail` (`SaveVerificationToken`), liefert das Klartext-Token in der Antwort zurück und setzt `EmailVerifiedAt` selbst NICHT. Der reguläre `POST /api/auth/verify-email` (`VerifyEmailHandler`) bleibt der einzige Weg, der das Feld danach setzt — der Testweg prüft damit den echten Produktionspfad mit, statt ihn zu umgehen.

## Expected Behavior

- **Input:** Aufruf des Nachtrag-Skripts gegen eine Datenwurzel (mit/ohne `--execute`); HTTP-Login über Magic-Link oder Google-OAuth; `POST` auf den Resend-Endpoint mit `{"username"}`; `POST` auf den staging-only Testweg mit einer Ziel-`username` durch einen angemeldeten Nutzer.
- **Output:** gesetzte bzw. unverändert erhaltene `email_verified_at`-Zeitstempel; enumerationsfreie `200 {"status":"ok"}`-Antworten des Resend-Endpoints; ein Klartext-Verifikations-Token in der Antwort des Staging-Testwegs; `404` für den Staging-Testweg außerhalb von `GZ_ENV=staging`.
- **Side effects:** tar.gz-Backup des vollen Datenbaums vor jedem `--execute`-Lauf des Nachtrag-Skripts, der tatsächlich Konten ändert (ein `--execute`-Lauf ohne zu ändernde Konten schreibt nichts und braucht daher keine Sicherung); asynchroner Mailversand (Goroutine, 20s-Timeout) bei erfolgreichem Resend; kein Login wird durch diese Scheibe gesperrt — S1 ändert kein beobachtbares Anmeldeverhalten für bestehende Nutzer.

## Acceptance Criteria

- **AC-1:** Given ein Konto ohne `email_verified_at` und weitere gesetzte Felder (Trips, Empfänger, Passwort-Hash) / When das Nachtrag-Skript mit `--execute` über dessen Datenwurzel läuft / Then trägt das Konto danach `email_verified_at`, und alle übrigen Felder stehen unverändert wie vorher.
  - Test: Vergleicht das vollständige verbleibende Profil-Dict vor und nach dem Lauf feldweise auf Gleichheit (nicht nur einzelne handverlesene Felder) und prüft zusätzlich, dass `email_verified_at` gesetzt ist.

- **AC-2:** Given dieselbe Datenwurzel unmittelbar nach einem `--execute`-Lauf / When das Skript ein zweites Mal mit `--execute` läuft / Then bleibt jeder bereits gesetzte Zeitstempel unverändert erhalten.
  - Test: Prüft, dass der Zeitstempel-WERT nach dem zweiten Lauf identisch mit dem Wert nach dem ersten Lauf ist — „ist weiterhin gesetzt" allein genügt nicht, da das ein stilles Überschreiben nicht fangen würde.

- **AC-3:** Given eine Datenwurzel mit unbestätigten Konten / When das Skript ohne `--execute` läuft / Then wird keine einzige Datei verändert, und die Ausgabe benennt die Konten, die ein Lauf ändern würde.
  - Test: Vergleicht Dateiinhalt (Bytes bzw. geparste Dicts) vor und nach dem Dry-Run auf vollständige Gleichheit und prüft zusätzlich, dass die Stdout-Ausgabe jedes Konto der **richtigen** der beiden Listen zuordnet — die Konten ohne `email_verified_at` bilden vollständig die „Zu aktualisieren"-Liste, ein Konto mit vorbestehendem Zeitstempel vollständig die „Übersprungen"-Liste. Bloßes Vorkommen der Konto-ID im Stdout genügt nicht: das würde ein Skript durchwinken, das ein zu änderndes Konto fälschlich als übersprungen meldet — und genau dieser Probelauf ist die Entscheidungsgrundlage für den echten Lauf gegen die Produktivdaten.

- **AC-4:** Given ein Konto ohne `email_verified_at`, dessen effektive Kontaktadresse eine bestimmte Adresse ist / When sich dieses Konto erfolgreich per Magic-Link an genau diese Adresse anmeldet / Then trägt das Konto danach `email_verified_at`.
  - Test: Durchläuft den echten Magic-Link-HTTP-Fluss (Request/Verify), lädt den Nutzer danach über den Store neu und prüft `EmailVerifiedAt` — nicht durch direkten Aufruf einer internen Adressvergleichs-Funktion.

- **AC-5:** Given ein Konto ohne `email_verified_at`, dessen `mail_to` auf eine ANDERE Adresse zeigt als die per Magic-Link nachgewiesene / When die Magic-Link-Anmeldung erfolgreich ist / Then bleibt `email_verified_at` ungesetzt, und die Anmeldung gelingt trotzdem.
  - Test: Prüft nach demselben HTTP-Fluss beide Hälften — `EmailVerifiedAt` bleibt `nil`, UND die Anmeldung liefert `200` mit gültigem Session-Cookie.

- **AC-6:** Given ein bestehendes OAuth-Konto ohne `email_verified_at`, dessen effektive Kontaktadresse der von Google bestätigten Adresse entspricht / When sich das Konto erneut per Google anmeldet / Then trägt es danach `email_verified_at`.
  - Test: Durchläuft den Google-OAuth-Callback-Handler mit einer Store-Fixture (kein echter Google-Aufruf nötig), lädt den Nutzer danach über den Store neu und prüft `EmailVerifiedAt`.

- **AC-7:** Given ein Konto mit hinterlegter Kontaktadresse und ohne gültigen Verifikations-Token / When jemand den Resend-Endpoint für dieses Konto aufruft / Then existiert danach ein gültiger Verifikations-Token für das Konto, und die Antwort ist `200 {"status":"ok"}`.
  - Test: Ruft den Resend-Endpoint auf, beobachtet den bestehenden `sendVerificationMailFn`-Seam (`auth.go:829`) als Recorder (realer Seam, kein Mock-Theater) und prüft, dass die Zieladresse die effektive Kontaktadresse ist, das mitgeschickte Token danach von `VerifyEmailHandler` akzeptiert wird, UND dass Statuscode und Antwortkörper des Resend-Aufrufs `200 {"status":"ok"}` sind.

- **AC-8:** Given eine Kennung, zu der kein Konto existiert, und eine Kennung, zu der eines existiert / When der Resend-Endpoint für beide aufgerufen wird / Then sind Statuscode und Antwortkörper in beiden Fällen zeichengleich.
  - Test: Ruft den Endpoint für beide Kennungen auf und vergleicht Statuscode und Antwortkörper byteweise auf Gleichheit.

- **AC-9:** Given ein Router, der ohne gesetztes `GZ_ENV` gebaut wurde (die Produktionslage) / When der Staging-Testweg aufgerufen wird / Then antwortet er mit 404, und kein Token wird erzeugt.
  - Test: Prüft beide Hälften — `404` auf den Aufruf, UND dass im Verifikations-Token-Store danach kein neuer Eintrag für das Zielkonto existiert.

- **AC-10:** Given ein Router mit `GZ_ENV=staging` und ein angemeldeter Nutzer / When der Staging-Testweg für ein unbestätigtes Konto aufgerufen wird / Then liefert er ein Token, das der reguläre Verifikations-Endpoint anschließend annimmt, und erst dieser setzt `email_verified_at`.
  - Test: Beobachtet die Reihenfolge — `EmailVerifiedAt` ist unmittelbar nach dem Staging-Aufruf noch `nil`, wird erst nach einem anschließenden erfolgreichen `POST /api/auth/verify-email` mit dem gelieferten Token gesetzt.

- **AC-11:** Given ein Konto, dessen `email_verified_at` bereits gesetzt ist / When der Staging-Testweg dafür aufgerufen wird, ohne dass das gelieferte Token eingelöst wird / Then bleibt der bestehende Zeitstempel unverändert.
  - Test: Prüft, dass der Zeitstempel-WERT nach dem Aufruf identisch mit dem Wert davor ist — nicht nur, dass weiterhin irgendein Wert gesetzt ist.
- **AC-12:** Given ein Router mit `GZ_ENV=staging` / When der Staging-Testweg ohne gültiges Anmelde-Merkmal aufgerufen wird / Then wird er mit 401 abgewiesen, und es entsteht kein Verifikations-Token für das genannte Konto.
  - Test: Ruft den Testweg ohne Sitzungs-Cookie auf und prüft beides — den 401 UND dass danach kein Token für die Zielkennung im Speicher liegt. Bewacht die Präfix-Falle: Läge der Pfad unter `/api/debug/`, `/api/internal/` oder `/api/webhooks/telegram/`, gäbe die Middleware ihn pauschal frei (`internal/middleware/auth.go:61-63`) und der Aufruf lieferte ein Token statt 401.

## Known Limitations

- S1 ändert kein Login-Verhalten — unbestätigte Konten bleiben bis zur Scharfschaltung in #2271 uneingeschränkt anmeldefähig. Das ist beabsichtigt: Vorbereitung ohne Aussperr-Risiko.
- Passwort- und Passkey-Logins bekommen keine Selbstheilung — nur Magic-Link und OAuth beweisen Mailbox- bzw. Adressbesitz und können das Feld deshalb setzen.
- Ein angemeldeter Staging-Nutzer kann über den Testweg ein Token für ein fremdes Konto anfordern (siehe Risiko unten).
- Der Staging-Testweg existiert nur, solange `GZ_ENV=staging` gesetzt ist; ein Rückbau ist nicht Teil dieser Scheibe.
- ~~Kein AC prüft eigenständig, dass der Staging-Testweg tatsächlich eine Anmeldung verlangt.~~ **Geschlossen durch AC-12** (nachgetragen 2026-09-11): Ein Implementierungs-Constraint ohne Test ist kein Wächter — ein späteres Verschieben des Pfads unter ein pauschal freigeschaltetes Präfix würde von keinem Test gefangen.

## Risiko

Ein angemeldeter Staging-Nutzer kann über den staging-only Testweg ein Verifikations-Token für ein beliebiges fremdes Konto anfordern — der Endpoint prüft nur, DASS jemand angemeldet ist, nicht WESSEN Konto verifiziert werden soll. Das gilt als hinnehmbar, weil:

- der Endpoint in Produktion nicht existiert (`GZ_ENV != "staging"` → 404, AC-9),
- er nur ein Token ausgibt, das über den regulären Resend-Weg ohnehin an die hinterlegte Kontaktadresse dieses Kontos gegangen wäre — kein neuer Informationsgewinn, nur ein anderer Zustellweg ohne Mailversand,
- er `EmailVerifiedAt` nicht selbst setzt, sondern zwingend den echten `VerifyEmailHandler` durchläuft (AC-10).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** S1 nimmt keine dokumentierte Entscheidung zurück. ADR-0060 und `docs/specs/modules/session_allowlist.md` (alle sechs Anmeldewege stellen ein Sitzungsmerkmal aus) bleiben unberührt — S1 blockiert keinen Anmeldeweg und entfernt kein Auto-Login; das bleibt #2271 (S2) vorbehalten.

## Changelog

- 2026-09-11: Initial spec created (Issue #2304, S1 aus #2271/#2146, Epic #2138)
- 2026-09-11: Docs-Nachzug — „Estimated Scope" korrigiert (`Files: 6` → `7`), passend zu den
  bereits 7 Zeilen der Affected-Files-Tabelle (`internal/handler/export_test.go` war dort schon
  gelistet).
