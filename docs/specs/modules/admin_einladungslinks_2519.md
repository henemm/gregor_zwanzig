---
entity_id: admin_einladungslinks_2519
type: module
created: 2026-10-06
updated: 2026-10-06
status: approved
version: "1.0"
tags: [admin, auth, tier, einladung, registrierung, issue-2519]
---

# Admin-Einladungslinks (Level direkt per Link vergeben)

## Approval

- [x] Approved (PO-Freigabe 2026-10-06)

## Purpose

Ein Admin kann einzelne externe Personen per Link einladen und ihnen beim Registrieren direkt ein Level (Free/Standard/Premium) mitgeben, ohne dass sie einen Tier-Antrag stellen müssen. Die offene Registrierung bleibt unverändert daneben bestehen; die E-Mail-Bestätigung bleibt auch über Einladungslink Pflicht (ADR-0066). Issue #2519, baut auf Admin-Rolle (ADR-0078), Admin-API und Admin-UI (S3/S4) auf.

## Source

- **File:** `internal/store/invite.go` (neu), `internal/handler/admin_invites.go` (neu), `internal/handler/auth.go`, `internal/model/invite.go` (neu), `internal/router/router.go`, `cmd/server/main.go`, `frontend/src/routes/register/+page.server.ts`, `frontend/src/routes/register/+page.svelte`, `frontend/src/routes/admin/+page.server.ts`, `frontend/src/routes/admin/+page.svelte`, `frontend/src/lib/admin.ts`, `frontend/src/lib/types.ts`
- **Identifier:** `InviteStore` (`Create`, `List`, `Revoke`, `Peek`, `Redeem`, `Rollback`), `handler.AdminCreateInviteHandler` / `AdminListInvitesHandler` / `AdminRevokeInviteHandler`, `handler.InviteCheckHandler`, `authRequest.Invite`, `RegisterHandler` (erweitert)

> **Schicht-Hinweis:** Go-API (Kern) plus SvelteKit-Frontend (Register-Seite, Admin-Seite). Kein Python-Core. Der Store liegt unter `internal/store/` und arbeitet über alle Nutzer hinweg, daher `// gz-store-scope-exempt:`-Kommentar an den Methoden (Guard-Tests). Die Admin-Seite nutzt nur Atoms/Molecules (Import-Guard #470).

## Estimated Scope

- **LoC:** ~450-550 Code ohne Tests (Go ~300, Frontend ~200). Das überschreitet das Workflow-Limit von 250 LoC: `workflow.py set-field loc_limit_override 500` (bei Bedarf 650) ist nötig.
- **Files:** 12 Code-Dateien (6 neu/modifiziert Go, 6 Frontend) plus Tests und ADR-0084
- **Effort:** high

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `internal/model/invite.go` | CREATE | `Invite`-Datensatz: id, token_hash, tier, note, created_at, created_by, used_by, used_at, revoked_at |
| `internal/store/invite.go` | CREATE | `InviteStore` mit Mutex, atomarem Schreiben auf `DataDir/invites.json` (Muster `TelegramTokenStore`) |
| `internal/handler/admin_invites.go` | CREATE | Drei Admin-Handler plus öffentlicher Vorab-Check `InviteCheckHandler` |
| `internal/handler/auth.go` | MODIFY | `authRequest.Invite`; Einlösung in `RegisterHandler`, Tier aus Einladung |
| `internal/router/router.go` | MODIFY | Routen, `Deps.InviteStore`; Vorab-Check hinter `NewIPRateLimiter(5, time.Hour)`, öffentlich |
| `cmd/server/main.go` | MODIFY | `InviteStore` erzeugen und in `router.Deps` verdrahten |
| `frontend/src/routes/register/+page.server.ts` | MODIFY | `load` liest `?invite=`, Vorab-Check serverseitig; Action reicht `invite` weiter, mappt `invite_invalid` |
| `frontend/src/routes/register/+page.svelte` | MODIFY | Hinweis-Banner, Hidden-Field, Google-Knopf bei Einladung ausgeblendet |
| `frontend/src/routes/admin/+page.server.ts` | MODIFY | Lädt `/api/admin/invites` mit; Actions erstellen/widerrufen |
| `frontend/src/routes/admin/+page.svelte` | MODIFY | Card „Einladungen": Formular, Link-Anzeige mit Kopieren-Knopf, Tabelle, ConfirmDialog |
| `frontend/src/lib/admin.ts`, `frontend/src/lib/types.ts` | MODIFY | `Invite`-Typen, Statuslabels, Fehlertexte |
| `docs/adr/0084-*.md` | CREATE | ADR-0084 (schreibt die Implementierung) plus Eintrag im ADR-Index |
| `internal/store/invite_concurrency_test.go`, `internal/router/admin_invites_test.go`, `frontend/src/routes/admin/__tests__/`, `frontend/src/routes/register/__tests__/` | CREATE/MODIFY | Tests zu den ACs |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RequireAdmin` (`internal/middleware/admin.go`) | middleware | Schützt alle Einladungs-Admin-Routen (403 `{"error":"forbidden"}`), ADR-0078 |
| `AuthMiddleware` | middleware | Anonyme Aufrufe der Admin-Routen → 401 |
| `TelegramTokenStore` (`internal/handler/telegram_connect.go`) | module | Vorbild für globale Einmal-Token-Datei (Mutex, Temp-Datei + Rename) |
| `writeFileAtomic` (`internal/store/write.go`) | function | Atomares Schreiben von `invites.json` |
| `RegisterHandler`, `dispatchVerificationMail` | function | Bestehender Registrierungsablauf, E-Mail-Bestätigung bleibt Pflicht (ADR-0066) |
| `model.User.Tier`, `EffectiveTier` | model | Level wird direkt als `Tier` gesetzt; `RequestedTier` bleibt leer |
| `AdminSetUserTierHandler` | function | Vorbild für exakte Whitelist free/standard/premium, `adminJSON`/`adminError` |
| `NewIPRateLimiter` | middleware | Rate-Limit für öffentlichen Vorab-Check und Registrierung |
| Frontend Atoms/Molecules (Card, PageHeader, Btn, ConfirmDialog) | component | Admin-UI ohne neue Organismen |
| ADR-0066, ADR-0078 | adr | E-Mail-Bestätigungspflicht; Admin-Rolle über `GZ_ADMIN_USER_IDS` |

## Implementation Details

**1. Persistenz (Tech-Lead-Entscheidung).** Neue globale Datei `data/invites.json`, nicht pro Nutzer: Eine Einladung gehört keinem Nutzer, der Eingeladene existiert beim Erstellen noch nicht. `InviteStore` folgt `TelegramTokenStore`: in-process `sync.Mutex`, atomares Schreiben (Temp-Datei + Rename), Injektion über `router.Deps`. Datensatz: `id` (kurz, zufällig, für Admin-Aktionen), `token_hash` (SHA-256), `tier`, `note`, `created_at`, `created_by`, `used_by`, `used_at`, `revoked_at`. Kein Ablaufdatum in v1 (PO: nicht zwingend).

**2. Token.** 32 Byte `crypto/rand`, base64url. Gespeichert wird nur der SHA-256-Hash; ein Dateileck liefert damit keine einlösbaren Links. Der vollständige Link `/register?invite=<token>` wird dem Admin nur einmal direkt in der Antwort auf das Erstellen gezeigt. Verlorener Link: widerrufen und neu erstellen.

**3. Admin-Endpunkte** (alle hinter `AuthMiddleware` + `RequireAdmin`):
- `POST /api/admin/invites` mit `{tier, note}` → 201 `{invite, link}`. Ungültiges `tier` → 400 (exakte Whitelist free/standard/premium), Note max. 200 Zeichen.
- `GET /api/admin/invites` → Liste ohne Token; Status offen/benutzt/widerrufen; `used_by` inkl. Benutzername/E-Mail, falls auflösbar.
- `POST /api/admin/invites/{id}/revoke` → nur offene Einladungen widerrufbar, benutzte → 409.

**4. Öffentlicher Vorab-Check.** `GET /api/auth/invite/{token}` ohne Auth, rate-limited wie Register: 200 `{tier}` bei offener Einladung, sonst 404 `invite_invalid`. Nach außen keine Unterscheidung zwischen benutzt, widerrufen und unbekannt.

**5. Registrierung.** `authRequest` bekommt optional `invite`. Gesetzt und ungültig → 400 `invite_invalid`, es wird kein Konto angelegt (kein stilles Free-Konto). Reihenfolge in `RegisterHandler`: alle Validierungen (Username, Passwort, E-Mail, `UserExists`, `email_taken`) laufen vor dem Einlösen, damit ein Tippfehler die Einladung nicht verbrennt. Dann wird die Einladung unter dem Mutex reserviert (`used_by`/`used_at` gesetzt und persistiert) vor `SaveUser`; Nutzer entsteht mit `Tier=<invite.tier>`, `RequestedTier` leer. Schlägt `SaveUser` oder `ProvisionUserDirs` fehl, wird die Reservierung zurückgerollt. Bei zwei parallelen Registrierungen mit demselben Token gewinnt genau eine, die andere erhält 400 `invite_invalid`. E-Mail-Bestätigung unverändert Pflicht.

**6. Register-Seite.** `load` liest `url.searchParams.get('invite')` und macht den Vorab-Check serverseitig. Gültig: Hinweis „Du wurdest eingeladen — Level: <Level>", Hidden-Field `invite`. Ungültig: klarer Hinweis, dass die Einladung nicht (mehr) gültig ist, normale Registrierung (Free) bleibt möglich. Bei Einladungslink ist der Google-Knopf ausgeblendet, weil OAuth/Passkey/Magic-Link keine Einladung kennen.

**7. Admin-UI auf `/admin`.** Neue Card „Einladungen": Level-Auswahl (Default Standard), Notiz, Knopf „Einladung erstellen"; nach Erstellen Link mit Kopieren-Knopf und Hinweis „nur jetzt sichtbar". Tabelle mit Notiz, Level, erstellt am, Status (Offen / Benutzt von <Name> am <Datum> / Widerrufen am <Datum>) und Aktion „Widerrufen" (nur bei offen, mit ConfirmDialog).

**8. Logging.** Erstellen, Widerrufen, Einlösen werden mit Invite-ID geloggt, nie mit Token.

**Begründung Alternativen:** Pro-Nutzer-Ablage scheidet aus (kein Eigentümer). Klartext-Token scheidet aus (Dateileck). Einlösen nach `SaveUser` scheidet aus (Race: zwei Konten). Atomarität gilt innerhalb eines gregor-api-Prozesses (siehe Known Limitations).

## Expected Behavior

- **Input:** Admin: `{tier, note}`. Besucher: `/register?invite=<token>` plus Formular (Benutzername, Passwort, E-Mail, verstecktes `invite`).
- **Output:** Admin erhält Link und Listeneintrag; Besucher erhält ein Konto mit dem vorgegebenen Level, Anmeldung nach E-Mail-Bestätigung.
- **Side effects:** Schreibt `data/invites.json`; Einlösung setzt `used_by`/`used_at`; Konto wird mit `Tier` ohne Tier-Antrag angelegt; Logeinträge mit Invite-ID.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Admin / When er auf /admin eine Einladung mit Level Standard und Notiz „Tante Erna" erstellt / Then sieht er einmalig einen vollständigen Link `/register?invite=…` mit Kopieren-Knopf und die Einladung erscheint in der Liste mit Status „Offen", Level und Notiz.
  - Test: Router-Test mit Admin-Session: POST erstellt (201, Link enthält Token), GET-Liste zeigt Status offen; Frontend-Test: Admin-Seite zeigt Link und Tabellenzeile.

- **AC-2:** Given eine offene Einladung mit Level Premium / When eine Person über den Link registriert und anschließend die E-Mail bestätigt / Then hat ihr Konto Level Premium ohne offenen Tier-Antrag, und die Anmeldung gelingt erst nach der E-Mail-Bestätigung.
  - Test: Router-Test: Registrierung mit Token → 201, gespeichertes Konto hat Tier premium, RequestedTier leer; Login vor Bestätigung abgelehnt, nach Bestätigung erfolgreich.

- **AC-3:** Given eine bereits eingelöste Einladung / When eine zweite Person denselben Link zum Registrieren nutzt / Then wird die Registrierung mit `invite_invalid` abgelehnt und es entsteht kein Konto.
  - Test: Router-Test: zweite Registrierung → 400 `invite_invalid`, Nutzer existiert nicht (Store-Prüfung).

- **AC-4:** Given eine offene Einladung / When zwei Personen gleichzeitig mit demselben Link registrieren / Then entsteht genau ein Konto, die andere Registrierung erhält 400 `invite_invalid`.
  - Test: Nebenläufigkeitstest mit parallelen Goroutinen gegen `InviteStore.Redeem` und gegen den Register-Handler (analog `telegram_token_concurrency_test.go`): genau ein Erfolg, genau ein neues Konto.

- **AC-5:** Given eine vom Admin widerrufene Einladung / When jemand den Link zum Registrieren nutzt / Then wird die Registrierung abgelehnt, kein Konto entsteht, und die Liste zeigt „Widerrufen am <Datum>".
  - Test: Router-Test: Revoke (200), Register → 400 `invite_invalid`; Revoke einer benutzten Einladung → 409.

- **AC-6:** Given eine offene Einladung und eine bereits vergebene E-Mail-Adresse / When die Registrierung deshalb mit `email_taken` scheitert / Then bleibt die Einladung offen und ist mit korrigierter Eingabe weiterhin einlösbar.
  - Test: Router-Test: erster Versuch 409 `email_taken`, Einladung weiter „offen"; zweiter Versuch mit freier E-Mail → 201.

- **AC-7:** Given eine eingelöste Einladung / When der Admin die Einladungsliste öffnet / Then steht dort „Benutzt von <Name> am <Datum>".
  - Test: Router-Test: GET-Liste nach Einlösung enthält `used_by` mit Benutzername und `used_at`; Frontend-Test: Tabelle zeigt den Statustext.

- **AC-8:** Given ein normaler Nutzer (zweiter Nutzer, kein Admin) und ein anonymer Besucher / When sie Einladungen erstellen, auflisten oder widerrufen / Then erhält der Nicht-Admin 403 und der anonyme Besucher 401 auf allen drei Endpunkten, und der Nicht-Admin sieht keine Einladungen.
  - Test: Router-Test mit zwei Nutzern (Admin legt Einladung an, Nicht-Admin ruft POST/GET/revoke auf → 403, ohne Session → 401; die Einladung bleibt unverändert offen).

- **AC-9:** Given eine erstellte Einladung / When `data/invites.json` und die Admin-Liste untersucht werden / Then kommt der Token-Klartext in keiner von beiden vor (nur Hash bzw. keine Tokenfelder).
  - Test: Router-Test: Link-Token aus der POST-Antwort wird weder in der rohen Datei noch im GET-Listen-Body gefunden; Hash in der Datei entspricht SHA-256 des Tokens.

- **AC-10:** Given die offene Registrierung ohne Einladungslink / When jemand sich wie bisher registriert / Then entsteht ein Konto mit Level Free, und die Registrierung verhält sich unverändert.
  - Test: Bestehende Register-Router-Tests bleiben grün; neuer Test: Registrierung ohne `invite` → 201, EffectiveTier free.

- **AC-11:** Given die Seite `/register?invite=…` / When sie mit gültigem Link geladen wird / Then zeigt sie „Du wurdest eingeladen — Level: <Level>“; bei ungültigem Link den Hinweis „Einladung nicht (mehr) gültig, normale Registrierung weiter möglich“; in beiden Fällen ist der Google-Knopf ausgeblendet. Ohne `invite`-Parameter bleibt die Seite unverändert (Google-Knopf sichtbar).
  - Test: Frontend-Test (`register/__tests__`): load/Render mit gültigem und ungültigem Token prüft Hinweistext und Fehlen des Google-Knopfs; ohne `invite` bleibt der Knopf sichtbar (falls Google aktiv).

- **AC-12:** Given ein ungültiges Level oder eine Notiz über 200 Zeichen / When der Admin eine Einladung erstellt / Then wird die Anfrage mit 400 abgelehnt und nichts gespeichert.
  - Test: Router-Test: tier „gold" → 400, Notiz mit 201 Zeichen → 400, Liste bleibt leer.

## Known Limitations

- **Kein Ablaufdatum** in v1 (PO: nicht zwingend); offene Einladungen gelten bis zur Einlösung oder zum Widerruf.
- **Link nur einmal sichtbar:** Nur der Hash wird gespeichert; verlorener Link → widerrufen und neu erstellen.
- **Nur Formular-Registrierung:** Google-OAuth, Passkey und Magic-Link kennen keine Einladung (`auth_oauth.go`, `passkey.go`, `auth_magic.go`); bei Einladungslink wird der Google-Knopf deshalb ausgeblendet.
- **In-process Mutex:** Die atomare Einlösung setzt genau einen gregor-api-Prozess je Umgebung voraus (wie bei `TelegramTokenStore`). Mehrere Prozesse auf derselben Datendatei sind nicht abgesichert.
- Ein Konto, das nach Einlösung nie bestätigt wird, verbraucht die Einladung trotzdem; der Admin erstellt dann eine neue.
- Das Level wirkt ab Konto-Anlage; spätere Änderung läuft über die bestehende Admin-Tier-Setzung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0084 (neu, schreibt die Implementierung)
- **Rationale:** Einladungslinks als globale Token-Datei mit Hash-Speicherung, Einlösung nur über Formular-Registrierung. Betrifft die Entscheidungsflächen Auth und Datenmodell/Persistenz; Abweichung von der Pro-Nutzer-Ablage unter `data/users/<user_id>/` sowie die bewusste v1-Beschränkung auf Formular-Registrierung müssen dokumentiert sein.

## Changelog

- 2026-10-06: Initial spec created (Issue #2519)
