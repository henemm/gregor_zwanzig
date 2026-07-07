# Context: Feature-1071 Level-Änderungs-Antrag (Tiers-4)

## Request Summary
Nutzer kann im Account-Bereich eine Level-Änderung (Tier) beantragen. Antrag wird per
Read-Modify-Write in `user.json` vermerkt (`requested_tier`/`requested_at`) und löst eine
Benachrichtigungsmail an den PO aus. Keine Genehmigungs-UI, keine Zahlungsanbindung — Freigabe
erfolgt weiterhin manuell durch den PO (direktes Setzen von `tier`).

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/user.go:10-23` | `User`-Struct, `Tier string` bereits vorhanden (Slice 1). Neue Felder `RequestedTier`/`RequestedAt` ergänzen, analog `PasswordResetToken` (Zeilen 25-28) als Vorbild für Zeitstempel-Paar. |
| `internal/handler/auth.go` | `UpdateProfileHandler` (439-501) = Vorbild Read-Modify-Write; `ForgotPasswordHandler` (167-270) = Vorbild Mail-Versand aus Handler; `middleware.UserIDFromContext(r.Context())` überall zur User-ID-Extraktion. Neuer Endpoint `RequestTierChangeHandler` analog `ChangePasswordHandler` (516-556). |
| `internal/store/user.go:48-79` | `LoadUser`/`SaveUser` — Volles Objekt lesen/schreiben, sicher für Read-Modify-Write, solange Handler nur die zwei neuen Felder mutiert. |
| `internal/mail/sender.go` | `Send`/`SendWithFallback` (50, 99) — synchron; Call-Sites nutzen Goroutine mit 20s-Timeout (Beispiel `auth.go:211-266`), damit HTTP-Response nicht blockiert. |
| `internal/mail/reset.go:14-38` | Vorbild für neue `BuildTierChangeRequestMail(...)`-Funktion (Plain+HTML, deutsche Texte). |
| `internal/config/config.go` | **Kein** Config-Feld für PO-E-Mail-Adresse. `.env` hat `GZ_MAIL_TO` — wird bisher nur von Python gelesen. Neues Feld nötig, z.B. `PoEmail string envconfig:"PO_EMAIL" default:"gregor_zwanzig@henemm.com"`. |
| `internal/router/router.go:61-62` | Registrierungsmuster (`r.Get`, `r.Put`) — neuer Eintrag `r.Post("/api/auth/tier-change-request", ...)` in derselben authentifizierten Gruppe (nicht in Public-Path-Allowlist von `internal/middleware/auth.go`). |
| `frontend/src/routes/account/+page.svelte:578-643` | Tier-Badge-Card (Zeilen 584-588, `tierLabel`-Helper 44-51). Formular-Vorbilder: `save()` (161-176, `api.put`), `changePassword()` (119-146, Client-Validierung + Error-Mapping), `sendTest(channel)` (94-111, Status-State-Machine idle/loading/ok/error — nächstliegendes Muster für "Antrag abschicken"). |
| `frontend/src/lib/types.ts:501` | `UserTier = 'free' \| 'standard' \| 'premium'` bereits vorhanden, wiederverwendbar für Select-Optionen. Kein zentraler `Profile`-Typ (duck-typed Zugriff über `data.profile?.xyz`). |

## Existing Patterns
- **Read-Modify-Write auf `user.json`**: immer `LoadUser` → gezielt Felder mutieren → `SaveUser(*user)`. Niemals Replace (Projekt-Grundsatz, BUG-DATALOSS-GR221 #102).
- **User-ID aus Auth-Kontext**: `middleware.UserIDFromContext(r.Context())`, niemals `"default"` (Cross-User-Leck-Grundsatz).
- **Mail-Versand nicht-blockierend**: Goroutine + `select` mit `time.After(20*time.Second)`, Fehler nur geloggt, HTTP-Response wartet nicht.
- **Frontend-Formular-Feedback**: lokale `successMsg`/`errorMsg`-States pro Card, `setTimeout`-Ausblenden nach ~4s; Error-Body als `{ detail?: string; error?: string }` gecastet.
- **Go-Handler-Tests**: `httptest.NewRequest` + `httptest.NewRecorder` + `h.ServeHTTP`, siehe `internal/handler/auth_test.go`, speziell `auth_password_reset_mail_test.go` für Mail-auslösende Endpoints.

## Dependencies
- Upstream: `internal/store` (LoadUser/SaveUser), `internal/mail` (Send/SendWithFallback), `internal/middleware` (UserIDFromContext), `internal/config` (Config-Struct für PO-E-Mail).
- Downstream: Kein bekannter Konsument von `RequestedTier`/`RequestedAt` außerhalb dieses Slices — PO setzt `tier` manuell nach Prüfung der Mail, kein automatisierter Downstream-Trigger geplant.

## Existing Specs
- `docs/specs/modules/epic_user_tiers_overview.md` — Epic-Overview, Slice 4 exakt beschrieben (Zeilen 140-147, PO-Entscheidungen 161-164).
- `docs/specs/modules/issue_1068_tier_model_display.md`, `issue_1069_tier_channel_gating.md`, `alert_daily_limit.md` — Vorgänger-Slices, gleiches Code-Pattern.
- Artefakt-Konvention: `docs/artifacts/feature-XXXX-<slug>/` je Slice (adversary-dialog.md, test-red-output.txt) — für #1071 fortsetzen unter `docs/artifacts/feature-1071-tier-change-request/`.

## Risks & Considerations
- **PO-E-Mail-Adresse fehlt in Go-Config** — muss in Spec-Phase geklärt werden (neues Config-Feld vs. Wiederverwendung `GZ_MAIL_TO`/`SMTPFrom`).
- **Typisierung `RequestedAt` — KORRIGIERT nach Verifikation:** `time.Time` (Value-Typ) mit `omitempty` funktioniert **nicht** wie zunächst angenommen — Go's `encoding/json` `omitempty` greift nicht bei Structs, ein Zero-Value würde als `"0001-01-01T00:00:00Z"` serialisiert statt weggelassen. **Muss `*time.Time` (Pointer) sein**, damit `nil` = "kein offener Antrag" eindeutig ist.
- **Keine Playwright-E2E-Tests** für `/account`/Tier bisher gefunden — Test-Strategie in TDD-RED-Phase muss entscheiden zwischen Go-`httptest` (Backend-Verhalten) und ggf. neuem E2E-Test fürs Formular (Projekt-Regel: „Backend-Bug: echter HTTP-Call" — hier Feature, kein Bug, aber gleiches Prinzip: echtes Verhalten beweisen, kein Mock).
- **Route nicht in Public-Path-Allowlist aufnehmen** (`internal/middleware/auth.go`) — Endpoint muss authentifiziert bleiben.
- **Zwei-Nutzer-Test-Pflicht** (Projekt-Regel): Endpoint muss mit zwei verschiedenen `user_id`s getestet werden, um Cross-User-Leck auszuschließen.

## Analysis

### Type
Feature (Slice 4 eines laufenden Epics, kein Bug)

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/config/config.go` | MODIFY | Neues Feld `PoEmail string envconfig:"PO_EMAIL" default:"gregor_zwanzig@henemm.com"` |
| `.env` / `.env.example` / `.env.tpl` | MODIFY | `PO_EMAIL`-Eintrag ergänzen |
| `internal/model/user.go` | MODIFY | Neue Felder `RequestedTier string` (omitempty) und `RequestedAt *time.Time` (Pointer, siehe Risiko unten) |
| `internal/mail/tier_change.go` | CREATE | `BuildTierChangeRequestMail(username, currentTier, requestedTier string) mail.Mail` — Plain+HTML, analog `reset.go` |
| `internal/handler/auth.go` | MODIFY | Neuer `RequestTierChangeHandler`; `profileResponse`/`toProfileResponse` um `requested_tier`/`requested_at` erweitern |
| `internal/router/router.go` | MODIFY | `r.Post("/api/auth/tier-change-request", ...)` in authentifizierter Gruppe registrieren |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Formular "Level-Wechsel beantragen" in bestehender Account-Karte, State-Machine analog `sendTest()` |
| `internal/handler/auth_tier_change_test.go` | CREATE | Go-httptest: Zwei-Nutzer-Test, Validierungsfälle, Mail-Fehler-blockiert-Save-nicht-Test |

### Scope Assessment
- Files: 8 (5 Backend-Produktionscode + 1 Test + 1 Frontend + Env-Dateien)
- Estimated LoC: ~175–210 Produktionscode (Backend ~125–140, Frontend ~50–70), plus ~150–220 Tests
- Risk Level: LOW — additive Felder (`omitempty`), kein bestehender Lesepfad verändert, etabliertes Pattern aus 3 Vorgänger-Slices
- Liegt über der Epic-Grobschätzung (~100 LoC/3 Dateien, wegen fehlendem Config-Feld + eigenem Mail-Template), bleibt aber deutlich unter dem 250-LoC-Workflow-Limit

### Technical Approach
- `POST /api/auth/tier-change-request`, authentifiziert, Body `{"requested_tier": "free"|"standard"|"premium"}`.
- Validierung: unbekannter Wert → `400 {"error":"invalid_tier"}`; identisch zum aktuellen effektiven Tier → `400 {"error":"already_current_tier"}`.
- Read-Modify-Write: `LoadUser` → `RequestedTier` + `RequestedAt = &now` setzen → `SaveUser` → **erst danach** `200 {"status":"ok"}`.
- Mail an `cfg.PoEmail` per Goroutine + 20s-Timeout (1:1 `ForgotPasswordHandler`-Muster), Fehler nur geloggt, beeinflusst niemals Save oder Response. `PoEmail == ""` → loggen, trotzdem 200.
- `RequestedAt` als `*time.Time` (Pointer-Pflicht wegen `omitempty`-Struct-Gotcha, siehe Risiken).
- Kein Clear-Endpoint: Pending-Zustand wird im Frontend clientseitig aus `requested_tier vorhanden UND requested_tier !== tier` abgeleitet — verschwindet automatisch, sobald PO `tier` manuell angleicht.
- Mail-Spam durch wiederholte Klicks ist für MVP akzeptiert (kein Dedup), sollte aber bewusst in der Spec stehen.

### Dependencies
- Reihenfolge: (1) Config-Feld → (2) Model-Felder → (3) Mail-Template (parallel zu 1/2) → (4) TDD-RED gegen Handler → (5) Handler-Implementierung → (6) Router-Registrierung → (7) Frontend (braucht 5/6 lokal lauffähig).
- Kein Downstream-Konsument von `RequestedTier`/`RequestedAt` außerhalb dieses Slices.

### Open Questions
- [x] PO-E-Mail-Adresse: neues Config-Feld `PoEmail`/`PO_EMAIL`, **nicht** `GZ_MAIL_TO` wiederverwenden (unterschiedliche Präfix-Konvention, nur Python liest `GZ_MAIL_TO`)
- [x] `RequestedAt`-Typisierung: `*time.Time` (Pointer), nicht `time.Time`
- [ ] Keine offenen Fragen mehr an den User — Spec-Phase kann direkt mit obigem Ansatz starten
