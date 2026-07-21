---
entity_id: fix_1226_register_verify
type: bugfix
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [auth, mail, verification, oauth, passkey, register]
workflow: fix-1226-register-verify
---

<!-- Issue #1226 — Drei Kontoerstellungspfade umgehen den #1219-Verifikations-Trigger -->

# Fix #1226 — Verifikationsmail bei allen drei Kontoerstellungspfaden auslösen

## Approval

- [ ] Approved

## Purpose

Issue #1226 behauptet ursprünglich, die klassische Registrierung (`RegisterHandler`)
verifiziere die E-Mail-Adresse nicht. Recherche zeigt: der Username/Passwort-Pfad
erfasst heute **gar keine** E-Mail-Adresse — die Prämisse trifft dort nicht direkt zu.
Stattdessen wurde der eigentliche Root-Cause gefunden: **drei** Kontoerstellungspfade
setzen `user.Email` direkt, ohne den bestehenden, aus Issue #1219 (Scheibe 2a-i)
etablierten Verifikations-Trigger `dispatchVerificationMail` (`internal/handler/auth.go:591`)
aufzurufen. Dadurch bleibt `EmailVerifiedAt` bei neu angelegten Konten für immer `nil` —
diese Adressen sind laut Resend-Allowlist (`loadResendAllowlist`, #1219) dauerhaft vom
Versand ausgeschlossen, ohne dass der Nutzer je eine Chance zur Bestätigung bekommt.

Einer der drei Pfade — **Google-OAuth-Neuanlage** (`createOAuthUser` in
`internal/handler/auth_oauth.go`) — ist ein echter, aktiv genutzter Live-Bug: neue
Google-Nutzer erhalten nie eine Bestätigungsmail und bleiben dauerhaft von
Resend-Zustellung ausgeschlossen. Der zweite Pfad —
`PasskeyRegisterPublicFinishHandler` (`internal/handler/passkey.go:512`, Issue #466) —
hat dieselbe Lücke, ist aber vom Frontend aktuell nicht verdrahtet (niedrigere Priorität).
Der dritte Pfad ist eine Erweiterung, keine reine Bugfix: die klassische Registrierung
bekommt auf PO-Wunsch (2026-07-11) ein neues Pflichtfeld `email`, das denselben
Verifikations-Trigger auslöst — bisher konnte sich dort niemand überhaupt für
E-Mail-Versand qualifizieren.

Fix: alle drei Pfade rufen nach erfolgreicher Kontoerstellung `dispatchVerificationMail`
auf — dasselbe, unveränderte Muster aus #1219, nur auf drei weitere Aufrufstellen
übertragen.

## Source

> **Schicht-Hinweis:** Ausschließlich Go-API (`internal/`, Production-API Port 8090)
> + SvelteKit-Frontend (`frontend/src/routes/register/`). Kein Python-Core betroffen.

- **File:** `internal/handler/auth.go` — `RegisterHandler` (Z.29), `authRequest` (Z.24,
  bekommt neues Feld `Email string`), `dispatchVerificationMail` (Z.591, wiederverwendeter
  Sende-Helper aus #1219, unverändert). Referenzmuster: `UpdateProfileHandler` (Z.499),
  Adressänderungs-Erkennung + Dispatch (Z.543-570).
- **File:** `internal/handler/auth_oauth.go` — `createOAuthUser` (Z.193, setzt `user.Email`
  direkt, KEIN Dispatch), `googleOAuthCallbackHandlerInternal` (Z.82, Aufrufer, hat `cfg`
  bereits verfügbar).
- **File:** `internal/handler/passkey.go` — `PasskeyRegisterPublicFinishHandler` (Z.512,
  setzt `user.Email = entry.Email` direkt, KEIN Dispatch, KEIN `cfg`-Parameter bisher),
  `PasskeyRegisterPublicBeginHandler` (Z.467, Precedent für minimale
  `strings.Contains(email, "@")`-Formatprüfung, Z.481).
- **File:** `internal/router/router.go` — drei Verdrahtungsstellen: `RegisterHandler`
  (Z.43), `GoogleOAuthCallbackHandler` (Z.76, `cfg` bereits durchgereicht, keine
  Signaturänderung nötig), `PasskeyRegisterPublicFinishHandler` (Z.117).
- **File:** `frontend/src/routes/register/+page.svelte` — Formular hat nur
  `username`/`password`/`confirmPassword` (Z.20-53), braucht neues Pflichtfeld `email`
  (type="email", required).
- **File:** `frontend/src/routes/register/+page.server.ts` — `actions.default` (Z.13),
  POST an `/api/auth/register` (Z.25-29), `email` muss ergänzt und Fehlerfall
  `invalid_email` auf verständliche deutsche Meldung gemappt werden.

## Estimated Scope

- **LoC:** ~80 LoC Produktionscode; Gesamt-Diff inkl. Tests realistisch ~250-400 LoC
- **Files:** 9 (`internal/handler/auth.go`, `internal/handler/auth_oauth.go`,
  `internal/handler/passkey.go`, `internal/router/router.go`,
  `internal/handler/auth_test.go`, `internal/handler/auth_oauth_test.go` (neu),
  `internal/handler/passkey_public_test.go`, `frontend/src/routes/register/+page.svelte`,
  `frontend/src/routes/register/+page.server.ts`)
- **Effort:** medium-high (Auth-Pfad, aber etabliertes #1219-Muster wird nur auf drei
  weitere Call-Sites übertragen — kein neues Konzept)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dispatchVerificationMail` (`internal/handler/auth.go:591`) | function | Bestehender, unveränderter #1219-Sende-Helper — erzeugt Token, wählt Test-User→Gmail vs. echte User→Resend-SMTP-Weiche, verschickt asynchron (20s-Timeout-Goroutine) |
| `sendVerificationMailFn` (`internal/handler/auth.go:583`) | Test-Seam | Package-private Funktionsvariable, Default `mail.SendVerificationMail` — Tests beobachten Dispatch ohne echten SMTP-Dial |
| `Store.SaveUser` / `Store.ProvisionUserDirs` | function | Bestehende Persistenzschritte, unverändert, laufen VOR dem neuen Dispatch-Aufruf |
| `validUsernameRe` (`internal/handler/auth.go`) | regex | Bestehende Username-Validierung, Precedent für Fehlercode-Stil (`validation failed`) |
| `strings.Contains(email, "@")` (`internal/handler/passkey.go:481`) | Precedent | Minimale Formatprüfung, wird 1:1 für das neue `RegisterHandler`-Pflichtfeld übernommen — kein `net/mail.ParseAddress`, keine Uniqueness-Prüfung |
| `internal/mail.IsTestUser` | function | Namens-Heuristik, entscheidet innerhalb von `dispatchVerificationMail` Gmail- vs. Resend-SMTP-Weiche — unverändert |

## Implementation Details

### 1. `RegisterHandler` — neues Pflichtfeld `email` + Dispatch

```go
type authRequest struct {
    Username string `json:"username"`
    Password string `json:"password"`
    Email    string `json:"email"`
}

func RegisterHandler(s *store.Store, bcryptCost int, cfg config.Config) http.HandlerFunc {
    // ... bestehende Username-/Passwort-Validierung unverändert ...
    if req.Email == "" {
        // 400 {"error":"validation failed"} — Pflichtfeld fehlt
    }
    if !strings.Contains(req.Email, "@") {
        // 400 {"error":"invalid_email"} — eigener Fehlercode, getrennt von generischem
        // "validation failed", damit das Frontend gezielt mappen kann
    }
    // ... UserExists-Check, Konto anlegen, user.Email = req.Email setzen ...
    // NACH SaveUser + ProvisionUserDirs:
    dispatchVerificationMail(s, cfg, userId, user)
}
```

### 2. `googleOAuthCallbackHandlerInternal` — Dispatch nur bei tatsächlicher Neuanlage

Nach dem bestehenden `createOAuthUser`-Aufruf (nur im `else`-Zweig, d.h. `existingUser ==
nil`) wird `dispatchVerificationMail(s, *cfg, newUser.ID, newUser)` ergänzt.
`createOAuthUser`-Signatur bleibt unverändert. Beim Login eines **bestehenden**
OAuth-Nutzers (`existingUser != nil`) wird **kein** Dispatch ausgelöst — sonst bekäme
ein Nutzer bei jedem Login eine neue Bestätigungsmail (Spam-Regression).

### 3. `PasskeyRegisterPublicFinishHandler` — neuer `cfg`-Parameter + Dispatch

Signatur bekommt `cfg config.Config` als neuen Parameter. Nach dem bestehenden
`SaveUser`+`ProvisionUserDirs`-Block wird `dispatchVerificationMail(s, cfg, newUser.ID,
&newUser)` ergänzt. `PasskeyRegisterPublicBeginHandler` bleibt unverändert (dort wird
nur die E-Mail entgegengenommen, nicht das Konto angelegt).

### 4. `router.go` — drei Call-Sites anpassen

- Z.43: `handler.RegisterHandler(deps.Store, bcrypt.DefaultCost, *deps.Config)`
- Z.76: keine Änderung nötig (`GoogleOAuthCallbackHandler` hat `deps.Config` bereits)
- Z.117: `handler.PasskeyRegisterPublicFinishHandler(deps.Store, deps.WebAuthn,
  deps.ChallengeStore, deps.Config.SessionSecret, *deps.Config)`

### 5. Reservierte Test-Domains — bewusst KEIN neuer Guard in diesem Fix

**Korrektur 2026-07-11 (Fix-Loop, vor Adversary-Phase):** Die ursprüngliche Fassung
dieses Abschnitts behauptete, `recipientBlockedForVerification`
(`internal/mail/sender.go:449`) prüfe keine reservierten Testdomains. Das ist
FALSCH — genauere Code-Prüfung zeigt: die Funktion ruft `isReservedTestDomain()`
auf (`sender.go:486`) und blockt reservierte RFC-2606-Domains genauso wie die
beiden literalen Test-Postfächer. Bestätigt durch den bestehenden, unveränderten
Test `TestSendVerificationMail_ReservedTestDomainBlocked`
(`internal/mail/verify_send_test.go:24`, PASS).

Der Guard sitzt aber NICHT in `dispatchVerificationMail` (Handler-Ebene,
`auth.go:591`) selbst, sondern eine Schicht tiefer, in der *echten*
`mail.SendVerificationMail`-Implementierung, die `dispatchVerificationMail`
asynchron in einer Fire-and-Forget-Goroutine aufruft. Konsequenz für dieses Fix:

- Auf Handler-Ebene (`RegisterHandler`/OAuth/Passkey) wird `dispatchVerificationMail`
  für JEDE Adresse gleich behandelt — Token wird erzeugt, Sendeversuch wird
  gestartet, unabhängig von der Domain. Die HTTP-Response (Konto angelegt, 201)
  ist davon nicht betroffen.
- Der tatsächliche Sendeversuch an eine reservierte Testdomain (z.B.
  `foo@example.com`) schlägt anschließend INNERHALB der Goroutine fehl (nur
  geloggt, nicht an den Aufrufer propagiert) — es geht real KEINE Mail raus.
  Das ist unverändertes, korrekt funktionierendes #1219-Sicherheitsnetz
  (identisch für `UpdateProfileHandler` seit Scheibe 2a-i) und wird durch
  diesen Fix weder neu eingeführt noch verändert.
- AC-7 (siehe unten) testet bewusst nur die Handler-Ebene (via
  `sendVerificationMailFn`-Testseam, der die tiefere Guard-Schicht per
  Definition nicht durchläuft) — das AC belegt "Dispatch wird aufgerufen",
  nicht "Mail wird tatsächlich zugestellt". Beide Aussagen sind für sich
  korrekt, dürfen aber nicht verwechselt werden.

## Expected Behavior

- **Input:** `POST /api/auth/register` mit `username`, `password`, `email`.
- **Output:** bei fehlendem/leerem `email` → 400 `{"error":"validation failed"}`; bei
  `email` ohne `@` → 400 `{"error":"invalid_email"}`; bei gültigem `email` → Konto wird
  angelegt (`user.Email` gesetzt), Session-Cookie gesetzt wie bisher, UND
  `dispatchVerificationMail` wird aufgerufen (Token gespeichert, Sendeversuch
  gestartet).
- **Input:** Google-OAuth-Callback mit `sub`, `email`, `email_verified=true` für einen
  bisher unbekannten `sub`.
- **Output:** neues Konto wird via `createOAuthUser` angelegt UND
  `dispatchVerificationMail` wird aufgerufen. Bei bekanntem `sub` (Login) wird
  **kein** Dispatch ausgelöst.
- **Input:** `POST` an `PasskeyRegisterPublicFinishHandler` mit gültiger Attestation
  und zuvor via Begin-Handler übermittelter `email`.
- **Output:** neues Konto wird angelegt UND `dispatchVerificationMail` wird
  aufgerufen.
- **Side effects:** `dispatchVerificationMail` erzeugt pro Aufruf einen neuen 24h-Token
  (`SaveVerificationToken`) und startet einen asynchronen Sendeversuch (Goroutine,
  20s-Timeout) — identisch zum bestehenden #1219-Verhalten, keine neuen Nebenwirkungen.

## Acceptance Criteria

- **AC-1:** Given ein `POST /api/auth/register`-Request ohne `email`-Feld (leer oder
  fehlend) mit sonst gültigem `username`/`password` / When der Request verarbeitet
  wird / Then antwortet der Server mit 400 und einer Validierungsfehler-Antwort, und
  es wird KEIN Konto angelegt.
  - Test: `RegisterHandler` mit Request-Body ohne `email` aufrufen, Statuscode 400
    prüfen, danach `s.UserExists(username)` auf `false` prüfen (kein Konto entstanden).

- **AC-2:** Given ein `POST /api/auth/register`-Request mit `email` ohne `@`-Zeichen
  (z.B. `"nicht-valide"`) und sonst gültigen Feldern / When der Request verarbeitet
  wird / Then antwortet der Server mit 400 und dem eigenen Fehlercode `invalid_email`
  (getrennt vom generischen `validation failed`), und es wird KEIN Konto angelegt.
  - Test: `RegisterHandler` mit `email: "nicht-valide"` aufrufen, Statuscode 400 und
    Response-Body-Feld `error == "invalid_email"` prüfen, `s.UserExists` auf `false`
    prüfen.

- **AC-3:** Given ein `POST /api/auth/register`-Request mit gültigem `email`
  (`user@beispiel.de`) und sonst gültigen Feldern / When der Request verarbeitet wird
  / Then wird das Konto mit gesetzter `Email` angelegt UND der Verifikations-Dispatch
  wird genau einmal für diesen neuen Nutzer ausgelöst.
  - Test: `sendVerificationMailFn`-Testseam durch Test-Double ersetzen,
    `RegisterHandler` mit gültigem `email` aufrufen, Statuscode 200/201 und gesetztes
    Session-Cookie prüfen, danach beobachten dass der Testseam genau einmal mit der
    registrierten Adresse aufgerufen wurde — kein echter SMTP-Dial.

- **AC-4:** Given ein Google-OAuth-Callback für einen `sub`, der noch KEINEM
  bestehenden Konto zugeordnet ist (Erstanmeldung) / When der Callback verarbeitet
  wird / Then wird ein neues Konto mit `user.Email` aus der Google-Antwort angelegt
  UND der Verifikations-Dispatch wird genau einmal ausgelöst.
  - Test: `googleOAuthCallbackHandlerInternal` mit Fake-Token-/Userinfo-Server
    (`GoogleOAuthCallbackHandlerWithEndpoints`-Muster) für einen unbekannten `sub`
    aufrufen, `sendVerificationMailFn`-Testseam beobachten (genau ein Aufruf mit der
    neuen Adresse), `s.FindUserByOAuthSub` bestätigt das neu angelegte Konto.

- **AC-5:** Given ein Google-OAuth-Callback für einen `sub`, der bereits einem
  bestehenden Konto zugeordnet ist (Login, keine Neuanlage) / When der Callback
  verarbeitet wird / Then wird KEIN neues Konto angelegt und der
  Verifikations-Dispatch wird NICHT ausgelöst (Regressionsschutz gegen Mail-Spam bei
  jedem Login).
  - Test: Bestehendes OAuth-Konto vorab anlegen, `googleOAuthCallbackHandlerInternal`
    für denselben `sub` erneut aufrufen, `sendVerificationMailFn`-Testseam beobachten
    (null Aufrufe), Session-Cookie wird trotzdem gesetzt (Login funktioniert normal).

- **AC-6:** Given eine abgeschlossene `PasskeyRegisterPublicFinishHandler`-Anfrage mit
  gültiger Attestation und einer zuvor im Begin-Schritt übermittelten `email` / When
  die Anfrage verarbeitet wird / Then wird ein neues passwortloses Konto mit gesetzter
  `Email` angelegt UND der Verifikations-Dispatch wird genau einmal ausgelöst.
  - Test: `PasskeyRegisterPublicFinishHandler` mit Fixture-Attestation und
    Challenge-Store-Eintrag (inkl. `Email`) aufrufen, `sendVerificationMailFn`-Testseam
    beobachten (genau ein Aufruf), `s.UserExists(entry.UserID)` bestätigt Konto.

- **AC-7:** Given ein `POST /api/auth/register`-Request mit einer reservierten
  Test-Domain-Adresse (`foo@example.com`) und sonst gültigen Feldern / When der
  Request verarbeitet wird / Then wird das Konto trotzdem angelegt (E-Mail ist nur
  Pflichtfeld, kein Domain-Guard bei der Registrierung selbst), UND der
  Verifikations-Dispatch wird wie bei jeder anderen Adresse ausgelöst — es gibt
  bewusst KEINEN neuen Domain-Guard in diesem Fix (Bestandsverhalten von
  `dispatchVerificationMail`, siehe Implementation Details Punkt 5).
  - Test: `RegisterHandler` mit `email: "foo@example.com"` aufrufen, Statuscode
    200/201 prüfen, `sendVerificationMailFn`-Testseam beobachten (genau ein Aufruf mit
    `foo@example.com` als Empfänger) — belegt, dass kein domainbasierter Guard den
    Dispatch verhindert.

- **AC-8:** Given zwei unterschiedliche Nutzer registrieren sich unabhängig
  voneinander mit unterschiedlichen `email`-Adressen über `RegisterHandler` /
  When beide Registrierungen abgeschlossen sind / Then hat jeder Nutzer sein eigenes,
  isoliertes Verifikations-Token (`SaveVerificationToken` pro `userId`), und der
  Dispatch für Nutzer A enthält ausschließlich die Adresse von Nutzer A (keine
  Cross-User-Vermischung von Empfängern oder Tokens).
  - Test: Zwei `RegisterHandler`-Aufrufe mit unterschiedlichen `username`/`email`
    nacheinander ausführen, `sendVerificationMailFn`-Testseam-Aufrufe paarweise den
    jeweiligen `userId`/Empfänger-Adressen zuordnen, prüfen dass Nutzer A niemals das
    Token oder die Adresse von Nutzer B im Dispatch sieht.

## Known Limitations

- **Doppelte Bestätigung bei Google-OAuth:** Google verifiziert die E-Mail-Adresse
  bereits (`email_verified=true` in der Userinfo-Antwort), Gregor Zwanzig verlangt
  trotzdem einen eigenen Double-Opt-In über `dispatchVerificationMail` — PO-Entscheidung
  (konsistent zu #1219 Scheibe 1), kein technischer Fehler. Nutzer bestätigt seine
  Adresse effektiv zweimal.
- **Kein Schutz gegen fremde E-Mail-Adressen bei Register:** Der neue `email`-Pflicht-
  check ist rein formal (`strings.Contains(email, "@")`), es gibt keine Prüfung, ob der
  Registrierende tatsächlich Zugriff auf die angegebene Adresse hat, außer dem
  bestehenden IP-Rate-Limiter (5/h). Akzeptiertes Risiko, konsistent zum bereits
  bestehenden, schwächeren Passkey-Precedent — der eigentliche Schutz ist der
  Double-Opt-In selbst (ohne Klick auf den Bestätigungslink bleibt die Adresse
  unverifiziert und von Resend-Versand ausgeschlossen).
- **Domain-Guard existiert, aber eine Schicht tiefer als `dispatchVerificationMail`
  selbst:** Korrigiert am 2026-07-11 — `dispatchVerificationMail` (Handler-Ebene)
  hat keinen eigenen Domain-Check, ruft aber `mail.SendVerificationMail` auf, deren
  `recipientBlockedForVerification` reservierte RFC-2606-Testdomains SEHR WOHL
  blockt (bestätigt durch `TestSendVerificationMail_ReservedTestDomainBlocked`).
  Eine Registrierung mit `foo@example.com` legt also ein Konto an und startet den
  Dispatch (Handler-Ebene, siehe AC-7), aber es geht real KEINE Mail raus — der
  Sendeversuch scheitert innerhalb der Fire-and-Forget-Goroutine am bestehenden
  #1219-Guard. Unverändertes, korrekt funktionierendes Bestandsverhalten, hier
  nicht neu eingeführt oder verändert — keine echte Limitation, sondern eine
  Klarstellung zur Schichtung.
- **Passkey-Public-Pfad ungenutzt vom Frontend:** Der Fix ist trotzdem sinnvoll (API
  bleibt über `router.go:117` erreichbar, gleicher Root-Cause wie die anderen beiden
  Pfade), aber niedrigere Priorität/Testtiefe vertretbar als OAuth (aktiv genutzt) und
  Register (PO-Wunsch, neues Pflichtfeld).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Härtung/Erweiterung des bestehenden, durch #1219 etablierten
  Verifikations-Trigger-Musters (`dispatchVerificationMail`) auf drei weitere,
  strukturell unterschiedliche Aufrufstellen — kein neuer Architekturbaustein, keine
  neue Technologieentscheidung. Bewusst KEINE gemeinsame Abstraktionsfunktion für alle
  drei Handler (Plan-Agent-Empfehlung): die drei Handler sind strukturell zu
  verschieden (unterschiedliche Vorbedingungen/Rückgabewerte), eine erzwungene
  Abstraktion würde mehr Umbau als Nutzen bringen.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1226, PO-Entscheidung 2026-07-11 (alle
  drei Pfade zusammen, E-Mail-Pflichtfeld bei Register)
- 2026-07-11 (Fix-Loop, während Phase 6, vor Adversary): Implementation Details
  Punkt 5 + zugehörige Known Limitation korrigiert — ursprüngliche Behauptung
  "kein Domain-Guard im Verifikations-Dispatch" war sachlich falsch.
  `recipientBlockedForVerification` (`internal/mail/sender.go:486`) blockt
  reservierte Testdomains sehr wohl, nur eine Schicht tiefer als
  `dispatchVerificationMail` selbst (bestätigt durch bestehenden Test
  `TestSendVerificationMail_ReservedTestDomainBlocked`). Kein AC geändert, keine
  Testerwartung geändert — nur die erklärende Prosa korrigiert.
