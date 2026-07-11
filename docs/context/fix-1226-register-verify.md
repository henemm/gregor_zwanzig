# Context: fix-1226-register-verify

## Request Summary
Issue #1226 behauptet, die Registrierung (`RegisterHandler`) verifiziere die E-Mail-Adresse eines Nutzers nicht, wodurch dieser still von Resend-Versand blockiert wird. Recherche zeigt: der Username/Passwort-Registrierungspfad erfasst heute **gar keine** E-Mail-Adresse — die beschriebene Prämisse trifft dort nicht zu. Stattdessen wurden **zwei echte, bereits existierende** Lücken mit identischem Root-Cause gefunden: Google-OAuth- und Passkey-Public-Registrierung setzen `user.Email` direkt, ohne den bestehenden Verifikations-Versand auszulösen. PO-Entscheidung (2026-07-11): Alle drei Pfade werden in diesem Workflow zusammen behoben — inkl. neuem Pflichtfeld „E-Mail" bei der klassischen Registrierung.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go` | `RegisterHandler` (Z.29) — braucht neues Pflichtfeld `Email` in `authRequest` (Z.24) + Verifikations-Trigger. `dispatchVerificationMail` (Z.591) ist der wiederverwendbare Sende-Helper (bereits vorhanden, Issue #1219). `UpdateProfileHandler` (Z.499) ist das Referenzmuster: `addressChanged` wird auch bei Erst-Setzen (leer→Wert) true (Z.544-553) und triggert den Versand (Z.568-570). |
| `internal/handler/auth_oauth.go` | `createOAuthUser` (Z.193) setzt `user.Email` direkt aus Google-Antwort, OHNE `EmailVerifiedAt` und OHNE Verifikationsmail — echter Live-Bug. Aufrufer `googleOAuthCallbackHandlerInternal` (Z.82) hat bereits `cfg *config.Config` verfügbar. |
| `internal/handler/passkey.go` | `PasskeyRegisterPublicFinishHandler` (Z.512) setzt `user.Email = entry.Email` direkt (Z.551), gleiche Lücke. Signatur hat aktuell KEIN `cfg` — muss ergänzt werden. Endpoint ist verdrahtet (`router.go:113-117`), aber vom Frontend aktuell **nicht genutzt** (kein Aufrufer in `frontend/src`) — Issue #466 V2 Add-on, still reachable via API. |
| `internal/router/router.go` | Drei Verdrahtungsstellen müssen bei Signaturänderungen angepasst werden: Z.43 (`RegisterHandler`), Z.76 (`GoogleOAuthCallbackHandler`, ruft intern `googleOAuthCallbackHandlerInternal` → hat `cfg` schon), Z.113-117 (`PasskeyRegisterPublicBeginHandler`/`FinishHandler`). |
| `frontend/src/routes/register/+page.svelte` | Formular hat nur `username`/`password`/`confirmPassword` (Z.20-53) — braucht neues Pflichtfeld `email` (type="email", required). |
| `frontend/src/routes/register/+page.server.ts` | `actions.default` (Z.13) liest FormData und postet an `/api/auth/register` (Z.25-29) — `email` muss ergänzt und ans Backend durchgereicht werden; Fehlerfälle (ungültige/fehlende E-Mail) müssen gemappt werden. |
| `internal/model/user.go` | `User.Email` (Z.12), `User.MailTo` (Z.16), `User.EmailVerifiedAt` (Z.32) — bestehende Felder, keine Schemaänderung nötig. |
| `internal/mail/sender.go` | `loadResendAllowlist` (Z.177) — Eignungskriterium ist ausschließlich `EmailVerifiedAt != ""`; das ist der Mechanismus, der unverifizierte Adressen stumm blockt. Keine Änderung nötig, nur Referenz zum Verständnis der Blockade. |

## Existing Patterns
- **Verifikations-Trigger-Muster (Issue #1219 Scheibe 2a-i):** `UpdateProfileHandler` setzt bei jeder tatsächlichen Änderung von `Email`/`MailTo` (inkl. Erst-Setzen von leer auf Wert) `EmailVerifiedAt = nil` und ruft danach `dispatchVerificationMail(s, cfg, userId, user)` auf. Dieses Muster ist 1:1 auf die drei Registrierungspfade übertragbar — `dispatchVerificationMail` ist bereits generisch genug (nimmt `userId` + `*model.User`).
- **Test-Domain-Guards:** `dispatchVerificationMail` selbst verschickt nichts an reservierte Testdomains (via nachgelagerten Allowlist-Check beim tatsächlichen Versand) — für Registrierungs-Tests mit synthetischen Adressen relevant.
- **Passkey-Public-Email-Validierung:** `PasskeyRegisterPublicBeginHandler` (Z.479) nutzt eine minimale Prüfung `strings.Contains(req.Email, "@")` — Präzedenzfall für die Formatprüfung im neuen `RegisterHandler`-Pflichtfeld (kein `net/mail.ParseAddress`, keine Uniqueness-Prüfung im Bestandscode).
- **Google-OAuth-E-Mail:** kommt bereits von Google verifiziert, ABER unser System kennt nur die eigene `EmailVerifiedAt`-Zeitstempel-Allowlist — Google-seitige Verifikation zählt hier nicht automatisch (Scope-Entscheidung: eigener Double-Opt-In bleibt Pflicht, konsistent zu Scheibe 1).

## Dependencies
- Upstream: `internal/config.Config` (SMTP-Felder), `internal/store.Store.SaveVerificationToken`/`ProvisionUserDirs`/`SaveUser`, `internal/mail.SendVerificationMail`/`BuildVerificationMail`/`IsTestUser`.
- Downstream: Resend-Allowlist (`loadResendAllowlist`) entscheidet später beim tatsächlichen Mail-Versand, ob eine Adresse durchgelassen wird — unverändert.

## Existing Specs
- Kein dedizierter Spec für #1219 Scheibe 2a-i auffindbar unter `docs/specs/modules/` (Suche ergebnislos) — Referenz ist der Code selbst + Issue-Historie (#1219, Scheibe 2a-i/2a-ii/2b).

## Risks & Considerations
- **Signaturänderungen kaskadieren:** `RegisterHandler`, `googleOAuthCallbackHandlerInternal`-Kette (eigentlich schon `cfg`-fähig) und `PasskeyRegisterPublicFinishHandler`/`PasskeyRegisterPublicBeginHandler` (falls Begin auch involviert) ändern sich — bestehende Tests in `auth_test.go`, `auth_oauth_test.go`, `passkey_test.go` müssen mit angepasst werden (Aufrufer-Updates, kein Verhaltensbruch für Bestandslogik).
- **Blast Radius bleibt High:** Auth + drei Kontoerstellungspfade + Resend-Sendepfad — Zwei-Nutzer-Testpflicht (`CLAUDE.md` Mandantenfähigkeit) gilt hier nicht direkt (kein bestehender Nutzer betroffen), aber Cross-Path-Konsistenz muss geprüft werden.
- **Keine aktiven Produktiv-Nutzer** (Memory: `project-no-active-production-users`) — kein Migrations-Risiko für Bestandsdaten, nur Neuanlage betroffen.
- **E-Mail-Format-Validierung im neuen Pflichtfeld:** Bestandscode nutzt nirgends strenge Validierung (`net/mail.ParseAddress`); Empfehlung für Spec: minimaler `strings.Contains(email, "@")`-Check konsistent zum Passkey-Precedent, keine Uniqueness-Prüfung (Profil-Update hat auch keine).
- **Passkey-Public-Pfad ungenutzt vom Frontend:** Fix ist trotzdem sinnvoll (API bleibt erreichbar, gleicher Root-Cause), aber niedrigere Priorität/Testtiefe vertretbar als OAuth (aktiv genutzt) und Register (PO-Wunsch).

## Analysis

### Type
Bug (OAuth + Passkey-Public, echte Live-Lücken) + Feature (Pflichtfeld E-Mail bei Register) — in einem Workflow, gleicher Root-Cause: drei Kontoerstellungspfade umgehen den zentralen Verifikations-Trigger.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | `authRequest` + `Email string`; `RegisterHandler` bekommt `cfg config.Config`, validiert E-Mail (Pflicht, minimaler `strings.Contains(email, "@")`-Check wie Passkey-Precedent), setzt `user.Email`, ruft nach `SaveUser`+`ProvisionUserDirs` `dispatchVerificationMail` auf. Eigener Fehlercode für ungültige E-Mail (z.B. `invalid_email`), getrennt von generischem `validation failed`. |
| `internal/handler/auth_oauth.go` | MODIFY | `googleOAuthCallbackHandlerInternal` ruft nach `createOAuthUser` zusätzlich `dispatchVerificationMail(s, *cfg, userId, newUser)` auf (nur bei tatsächlicher Neuanlage, nicht bei bestehendem User). `createOAuthUser`-Signatur bleibt unverändert. |
| `internal/handler/passkey.go` | MODIFY | `PasskeyRegisterPublicFinishHandler` bekommt `cfg config.Config` als neuen Parameter, ruft nach `SaveUser`+`ProvisionUserDirs` `dispatchVerificationMail` auf. `PasskeyRegisterPublicBeginHandler` unverändert. |
| `internal/router/router.go` | MODIFY | Drei Call-Sites anpassen: `RegisterHandler(deps.Store, bcrypt.DefaultCost, *deps.Config)`, OAuth-Kette (Config bereits durchgereicht, keine Signaturänderung nötig), `PasskeyRegisterPublicFinishHandler(deps.Store, deps.WebAuthn, deps.ChallengeStore, deps.Config.SessionSecret, *deps.Config)`. |
| `internal/handler/auth_test.go` | MODIFY+CREATE | 4 bestehende `RegisterHandler(...)`-Call-Sites um `cfg`-Parameter ergänzen; neue Tests: fehlende E-Mail → 400, ungültige E-Mail → 400, gültige E-Mail → Dispatch ausgelöst (via `sendVerificationMailFn`-Testseam). |
| `internal/handler/auth_oauth_test.go` | CREATE | Neuer Happy-Path-Test für Kontoerstellung via OAuth (existiert noch nicht) — Fake-Token-/Userinfo-Server via `GoogleOAuthCallbackHandlerWithEndpoints`, prüft NUR den Verifikations-Dispatch-Aspekt (Scope bewusst eng gehalten, kein Ausbau auf `ProvisionUserDirs`-Fehlerfälle o.ä.). |
| `internal/handler/passkey_public_test.go` | MODIFY | 6 bestehende `PasskeyRegisterPublicFinishHandler(...)`-Call-Sites um `cfg`-Parameter ergänzen, 1 neuer Assert für ausgelösten Dispatch. |
| `frontend/src/routes/register/+page.svelte` | MODIFY | Neues Pflichtfeld `email` (type="email", required), zwischen Username und Passwort. |
| `frontend/src/routes/register/+page.server.ts` | MODIFY | `email` aus FormData lesen, ans Backend durchreichen, neuen `invalid_email`-Fehlercode auf verständliche deutsche Fehlermeldung mappen. |

### Scope Assessment
- Files: 9
- Estimated LoC: Produktionscode ~80 LoC; Gesamt-Diff inkl. Tests realistisch ~250-400 LoC
- Risk Level: MEDIUM-HIGH (Auth-Pfad, aber etabliertes Muster aus #1219 wird nur auf drei weitere Call-Sites übertragen — kein neues Konzept)

### Technical Approach
Drei separate `dispatchVerificationMail`-Aufrufstellen statt einer gemeinsamen Helper-Funktion (Plan-Agent-Empfehlung, bestätigt) — die drei Handler sind strukturell zu verschieden (unterschiedliche Vorbedingungen/Rückgabewerte), eine erzwungene Abstraktion würde mehr Umbau als Nutzen bringen. `dispatchVerificationMail` selbst bleibt unverändert (kein `EmailVerifiedAt = nil`-Reset nötig, da neue User nie ein vorheriges Verifikationsdatum haben).

Reihenfolge: RegisterHandler zuerst (einfachster Testaufbau, etabliert das Muster) → OAuth (Live-Bug, höhere Priorität, aufwendiger zu testen) → Passkey (niedrigste Priorität/Nutzung, rein mechanische Wiederholung).

### Dependencies
Wie im Context-Abschnitt dokumentiert — keine neuen Abhängigkeiten, ausschließlich Wiederverwendung bestehender Bausteine (#1219).

### Entschiedene Punkte (statt offener Fragen)
- **Google-OAuth trotz google-seitiger Verifikation:** eigener Double-Opt-In bleibt Pflicht (PO-Entscheidung, konsistent zu Scheibe 1) — Known Limitation für Spec: Nutzer bestätigt E-Mail-Besitz zweimal (einmal gegenüber Google, einmal gegenüber Gregor Zwanzig).
- **Fehlergranularität:** eigener Fehlercode `invalid_email` getrennt von generischem `validation failed` (technische Entscheidung, kein Product-Call).
- **Missbrauchspotenzial (fremde E-Mail bei Register):** akzeptiertes Risiko, keine zusätzliche Mitigation über den bestehenden IP-Rate-Limiter (5/h) hinaus — konsistent zum bereits bestehenden, schwächeren Passkey-Precedent. Als Known Limitation im Spec dokumentieren, nicht als Blocker behandeln.
- **OAuth-Test-Scope:** neuer Happy-Path-Test bewusst eng auf den Verifikations-Dispatch begrenzt, kein Ausbau auf andere OAuth-Aspekte (Scope-Disziplin).
