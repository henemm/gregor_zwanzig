# Context: fix-2147-c-google-verknuepfung

## Request Summary
Issue #2147, Scheibe C (letzte Scheibe; A, B1, B2 live). Google-Login legt bei unbekanntem Google-`sub` kein
Zweitkonto mehr an, wenn die Google-Adresse einem bestehenden **bestätigten** Konto gehört — stattdessen
Verknüpfung. Dazu ein Kollisionszähler für Bestandsduplikate beim Serverstart (nur Zahlen, keine Adressen) und
das übergreifende ADR „Adress-Eindeutigkeit". Danach kann #2147 geschlossen werden.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth_oauth.go:81-208` | Callback: `FindUserByOAuthSub` (:156) → bekannt: `selfHealEmailVerification` (:172) / unbekannt: `createOAuthUser` (:174) + `dispatchVerificationMail` (:185) → `hasVerifiedEmail` (:194) → `issueSession` (:202) |
| `internal/handler/auth_oauth.go:210-239` | `createOAuthUser`: `Email=MailTo=email` roh (nicht normalisiert), **keine Adresssperre, keine Belegt-Prüfung** — einziger kontoanlegender Pfad außerhalb von B1 |
| `internal/store/user.go:449-464` | `FindUserByOAuthSub`: Linearscan, unlesbare Konten still übersprungen (nicht fail-closed), Testkonten nicht ausgenommen |
| `internal/store/address_owner.go` | `NormalizeEmailAddress` :21, `EffectiveContactAddress` :29, `HasLoginCredentials` :39, `forEachRealAccount` :47 (fail-closed, Testkonten raus), `ResolveAddressOwner` :73, `IsAddressTakenByOtherAccount` :115 |
| `internal/store/address_lock.go:17` | `LockEmailAddress(normalized) unlock` — Sperre je Adresse im Prozess |
| `internal/handler/auth.go:1140-1164` | `selfHealEmailVerification` (eigene ToLower/TrimSpace-Normalisierung) |
| `internal/handler/auth.go:1207ff`, `:1120ff` | `dispatchVerificationMail`, `issueVerificationToken` (adressgebunden, 24 h) |
| `internal/handler/auth.go:155-222` | `hasVerifiedEmail`, `issueSession`, `issueSessionWithoutVerificationGate` |
| `internal/handler/auth_magic.go:179-260` | Vorbild Lock + `resolveMagicLinkAccount` (Free/Owned/Ambiguous) |
| `internal/handler/auth.go:101-118, 898-988, 561-619` | B1/B2-Prüfungen (Register, Profil mit sortiertem Sperren inline :925-941, Verify-Einlösen) |
| `internal/handler/passkey.go:481-562` | B1 Passkey Begin/Finish |
| `internal/model/user.go` | Email :12, PasswordHash :13, PasskeyCredentials :14, MailTo :16, OAuthProvider :19, OAuthSub :20, EmailVerifiedAt :32, PendingContactAddress/Field :50-51 — **genau ein OAuth-Platz je Konto** |
| `cmd/server/main.go` | Start: config, Secrets-Fail-Fast :40-55, store.New :62, Seed-User :70-87, scheduler :113-122 — **keine Store-Checks beim Start** |
| `internal/scheduler/tier_request_health.go:26` | Vorbild für rein numerische Konten-Zählung (nie user_id/E-Mail), eingebunden in `Scheduler.Status()` `scheduler.go:765,829-834` |
| `internal/handler/proxy.go:20` / `router.go:162,241` | `/api/health`, `/api/scheduler/status` — beide öffentlich (`middleware/auth.go:50`) |
| `frontend/src/routes/login/+page.svelte`, `+page.server.ts:10-14` | liest `?error=` **nicht** — `oauth_failed`/`email_not_verified` aus dem OAuth-Redirect sind heute unsichtbar |
| `docs/adr/README.md` | endet mit 0066 → neues ADR **0067** |

## Existing Patterns
- **Adress-Eindeutigkeit (A/B1/B2):** normalisieren → `LockEmailAddress` → frisch laden → `ResolveAddressOwner` bzw.
  `IsAddressTakenByOtherAccount` → schreiben unter Lock; Mehrdeutigkeit neutral, Log ohne Adresse.
- **„Bestätigt gilt pro Adresse":** Inhaber X nur, wenn `EmailVerifiedAt != nil` UND X seine wirksame Kontaktadresse ist.
  🔴 `AddressOwned` allein heißt NICHT bestätigt (Owned auch für 1 unbestätigtes zugangsloses Konto, :95-97).
- **Übernahme-Regel Magic-Link** (Konten mit Zugangsdaten nie übernehmen) passt für C NICHT: C verknüpft bewusst
  Konten mit Passwort/Passkey — Schutz kommt aus „bestätigter Inhaber + Google `email_verified`".
- **Öffentliche Zähler:** nur Zahlen (TierRequestHealth-Muster).
- **OAuth-Tests:** `oauthFakeServers(t, sub, email)` `auth_oauth_test.go:238-262` + `GoogleOAuthCallbackHandlerWithEndpoints`;
  Zwei-Nutzer-/Race-/fail-closed-Muster in `magic_link_address_ownership_test.go`, `address_uniqueness_write_paths_test.go`.

## Dependencies
- Upstream: Google Userinfo (`sub`, `email`, `email_verified`), Store (`address_owner.go`, `address_lock.go`, `user.go`),
  Verifikationsmail-Pfad, Session-Gate #2271 / ADR 0066.
- Downstream: Login-Seite (Fehleranzeige), Magic-Link-Übernahme (`HasLoginCredentials` wird nach Verknüpfung wahr),
  B2-Pending-Logik (ausstehende Adresse ist nicht belegt), Profil-/Konto-Seite (OAuth-Anzeige, falls vorhanden).

## Existing Specs
- `docs/specs/modules/magic_link_adress_eindeutigkeit.md` (A) — Out of Scope :152-154 beschreibt C; ADR-Verweis :260-262
- `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md` (B1) — Out of Scope :188-190, Known Limitation Bestandsduplikate :354-355
- `docs/specs/modules/adresswechsel_nach_bestaetigung.md` (B2) — gibt an C weiter: :414-419 (Magic-Link sieht Pending nicht), :423-426 (Bestandsduplikate), :435-440 (Seitenkanal `token expired`)
- `docs/specs/modules/google_oauth_login.md` (#425, draft) — „kein Account-Linking in v1" (:41, :232) → wird durch C abgelöst
- `docs/adr/0066-login-erfordert-bestaetigte-email-adresse.md` — Google-Pfad :35/:43/:93-102

## Risks & Considerations
- 🔴 **Kontoübernahme durch Verknüpfung:** Verknüpfen nur, wenn (a) Google `email_verified=true` UND (b) genau ein
  bestätigter Inhaber, dessen wirksame Kontaktadresse die Google-Adresse ist. Eine Adresse nur im Nebenfeld oder nur
  als `PendingContactAddress` darf NICHT reichen.
- **Offene Entscheidungen für die Analyse/Spec:**
  - Belegte, aber nicht bestätigte/mehrdeutige Adresse: Neukonto ablehnen (neuer Fehler) oder wie heute anlegen?
    B1-Logik spricht für Ablehnen — sonst bleibt Google der Doppel-Adress-Pfad.
  - Bestehendes Konto trägt schon einen **anderen** Google-`sub` (nur ein OAuth-Platz): ablehnen, nicht überschreiben.
  - Muss der Nutzer die Verknüpfung bestätigen oder wird still verknüpft (plus Hinweis-Mail an die Kontoadresse)?
  - Sitzungen des bestehenden Kontos beenden? (Magic-Link-Übernahme macht `ClearSessions` nur bei unbestätigt.)
  - Bekannter `sub`, dessen Google-Adresse inzwischen einem anderen Konto gehört — Verhalten bleibt (Login per `sub`)?
- **Race:** zwei parallele Google-Callbacks gleicher Adresse bzw. Google-Callback parallel zu Register → unter
  `LockEmailAddress` + Re-Check; `FindUserByOAuthSub` ebenfalls unter Lock erneut prüfen (sonst doppelter sub).
- **fail-closed:** `FindUserByOAuthSub` überspringt unlesbare Konten still → im Verknüpfungspfad Lesefehler nicht ignorieren.
- **Normalisierung:** `createOAuthUser` speichert roh — auf `NormalizeEmailAddress` umstellen (Bestandsdaten nicht migrieren).
- **Kollisionszähler:** Start-Log + ggf. numerisches Feld im öffentlichen Status; NIE Adressen oder user_ids ausgeben.
  Kostet einen Konten-Scan beim Start (Kontenzahl klein). Testkonten ausnehmen (`forEachRealAccount`) oder getrennt zählen?
- **Frontend:** OAuth-Fehler sind auf `/login` heute unsichtbar — ein neuer Ablehnungsgrund bräuchte eine Anzeige
  (sonst stummer Rücksprung). Scope-Frage.
- **Staging-Messbarkeit:** echter Google-Login auf Staging nicht automatisierbar → Kern-Tests mit Fake-Google-Servern;
  Zähler über Status-Endpoint/Journal messbar.
- **LoC:** Handler + Store + Start + Frontend-Anzeige + Tests → `loc_limit_override` wahrscheinlich nötig.

## Analysis

### Type
Feature (Sicherheitslücke schließen: letzter Schreibpfad für Doppel-Adressen + Account-Linking)

### Klassifikation `ResolveAddressOwner` (selbst gelesen, `address_owner.go:73-107`)
- genau 1 bestätigter Inhaber → Owned (bestätigt)
- 0 Inhaber → Free
- 0 bestätigt, genau 1 Inhaber, X = wirksame Adresse, **ohne** Zugangsdaten → Owned (unbestätigt, übernehmbar)
- alles andere → Ambiguous: u. a. 1 unbestätigter Inhaber **mit** Zugangsdaten; Inhaber nur im Nebenfeld; >1 Inhaber
- Pending-Adressen (B2) sind unsichtbar → Free

### Entscheidungstabelle Google-Callback, unbekannter `sub` (entschieden)
Unter `LockEmailAddress(Normalize(google.email))`; zuerst `FindUserByOAuthSub` **unter Lock erneut** (Treffer → Bestandszweig).

| Adresslage | Verhalten |
|---|---|
| Free (auch: nur als Pending eines anderen Kontos) | Neukonto wie heute, Adresse **normalisiert**; Pending ≠ belegt bleibt B2-Regel (Einlösen später → `409 address_taken`) |
| Owned, bestätigt, Konto ohne `OAuthSub` | **verknüpfen**: `OAuthProvider/OAuthSub` per RMW setzen, `EmailVerifiedAt` NICHT anfassen, kein ClearSessions, **Hinweis-Mail** an die wirksame Adresse |
| Owned, bestätigt, Konto hat schon **anderen** `OAuthSub` | ablehnen, nie überschreiben |
| Owned, unbestätigt + zugangslos | übernehmen wie Magic-Link A: frisch laden, Re-Check Zugangsdaten + wirksame Adresse, `EmailVerifiedAt` setzen, `OAuthSub` setzen, `ClearSessions` |
| Ambiguous (unbestätigt mit Zugangsdaten / Nebenfeld / mehrdeutig) | ablehnen, **kein** Neukonto, **keine** Übernahme |
| Lesefehler | fail-closed `oauth_failed`, nichts schreiben |

Alle inhaltlichen Ablehnungen → **ein** neutraler Redirect-Code `oauth_link_failed` (keine Enumeration); Log nur IDs/Anzahl.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth_oauth.go` | MODIFY | Entscheidungstabelle, Lock, Re-Check, Normalisierung, Hinweis-Mail-Aufruf |
| `internal/handler/auth.go` bzw. Mail-Hilfe | MODIFY | Hinweis-Mail „Google-Anmeldung wurde verknüpft" (bestehender Versandweg, wirksame bestätigte Adresse) |
| `internal/store/…` (neu, z. B. `address_collisions.go`) | CREATE | numerischer Kollisionszähler (fail-soft, Testkonten raus) |
| `cmd/server/main.go` | MODIFY | Zähler nach `store.New` einmal loggen (nur Zahlen) |
| `frontend/src/routes/login/+page.server.ts`, `+page.svelte` | MODIFY | `?error=` lesen: `oauth_link_failed`, `oauth_failed`, `email_not_verified` → deutsche neutrale Texte |
| `internal/handler/*oauth*_test.go`, Store-Test, Frontend-Test | CREATE/MODIFY | Tabelle, Zwei-Nutzer, Race gleicher `sub`, fail-closed, Log ohne Adresse |
| `docs/adr/0067-…`, `docs/adr/README.md`, `google_oauth_login.md`, `api_contract.md` | CREATE/MODIFY | ADR Adress-Eindeutigkeit (A/B1/B2/C gesamt), „kein Linking in v1" abgelöst |

### Scope Assessment
- Files: ~8 Code + Tests + Doku
- Estimated LoC: Produktiv ~+180, Tests ~+400 → `loc_limit_override` nötig, **kein weiterer Schnitt** (Zähler/ADR rein additiv)
- Risk Level: HIGH (Auth, Kontozuordnung)

### Technical Approach
Store-Primitive (`LockEmailAddress`, `ResolveAddressOwner`, `EffectiveContactAddress`, `HasLoginCredentials`) direkt im
OAuth-Pfad nutzen. **Kein Refactoring von `auth_magic.go`** (live, sicherheitskritisch — ~15 Zeilen Dopplung billiger).
Verknüpfen läuft weiter durch das Gate `hasVerifiedEmail` (`auth_oauth.go:194`). Zähler nur als Start-Log, nicht im
öffentlichen Status-Endpoint (kein Scan pro Poll, niemand verlangt es).

### Dependencies
Upstream: Store-Adressbausteine A/B1/B2, Verifikations-/Hinweis-Mailversand (B2-Allowlist deckt bestätigte Adresse),
Session-Gate ADR 0066. Downstream: Magic-Link (verknüpftes Konto hat Zugangsdaten → nie übernehmbar, gewollt),
Login-Seite.

### Entschiedene Punkte / Restrisiken (für Spec + ADR)
- Google-Workspace-Admin kann `email_verified` für Domain-Adressen ausstellen → bekannte Restlücke, ADR dokumentiert
  sie als akzeptiert (gleiche Risikoklasse wie heutiger Neuanlagepfad).
- Bestandsduplikate: C **misst** (Zähler), löst nicht auf — Auflösung erst nach Messung, falls Zahl > 0.
- B2-Übergaben „Magic-Link sieht Pending nicht" und Seitenkanal `token expired` bleiben LOW → ADR „akzeptiert" + #1199.
- Messbarkeit: echter Google-Login auf Staging nicht fahrbar → Callback-ACs Kern-only (Fake-Google-Server);
  Staging: Login-Fehlertexte per `?error=` im Browser, Zähler-Logzeile im Staging-Journal. Registrierbudget 5/h geteilt;
  `mail_to` von `validator-issue110` nie ändern.
