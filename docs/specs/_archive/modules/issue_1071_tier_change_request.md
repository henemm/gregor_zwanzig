---
entity_id: issue_1071_tier_change_request
type: module
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [tiers, account, mail]
---

# Issue #1071: Level-Änderungs-Antrag (Tiers-4)

## Approval

- [ ] Approved

## Purpose

Gibt einem eingeloggten Nutzer im Account-Bereich die Möglichkeit, eine Änderung seines Nutzer-
levels (Free/Standard/Premium) zu beantragen, ohne dass diese Änderung automatisch wirksam wird.
Der Antrag wird per Read-Modify-Write in dessen `user.json` vermerkt (`requested_tier`/
`requested_at`) und löst eine Benachrichtigungsmail an den Product Owner aus, der die tatsächliche
Freigabe weiterhin manuell durch direktes Setzen von `tier` vornimmt. Das ist Slice 4 (letztes
Slice) aus Epic #1067 (`docs/specs/modules/epic_user_tiers_overview.md`), aufbauend auf dem in
Slice 1 (#1068) eingeführten `Tier`-Feld. Ohne dieses Slice hätte ein Nutzer, der auf ein höheres
Level wechseln möchte (z.B. um SMS-Alerts nutzen zu können, seit #1069), keinen erkennbaren Weg,
diesen Wunsch zu äußern, außer den PO außerhalb des Produkts zu kontaktieren.

## Source

- **File:** `internal/handler/auth.go` (neuer Handler)
- **Identifier:** `func RequestTierChangeHandler(s *store.Store, cfg config.Config) http.HandlerFunc`

> **PFLICHT — Schicht-Hinweis:** Betrifft zwei Schichten:
> - **Go-API** (`internal/config/config.go`, `internal/model/user.go`, `internal/mail/tier_change.go`,
>   `internal/handler/auth.go`, `internal/router/router.go`) — neuer authentifizierter Endpoint,
>   Persistenz des Antrags, Mail-Versand an den PO.
> - **Frontend** (`frontend/src/routes/account/+page.svelte`) — Formular zur Antragstellung in der
>   bestehenden Account-Karte, liest ausschließlich die bereits von Slice 1/2 gelieferten
>   `profile.tier`/`profile.requested_tier`/`profile.requested_at`-Felder, keine eigene Fachlogik.
>
> Kein Python-Core-Anteil in diesem Slice — die Tier→Channel-Enforcement-Logik aus #1069/#1070
> bleibt unverändert; dieses Slice ändert nur, WIE ein `tier`-Wechsel angestoßen (nicht: wie er
> durchgesetzt) wird.

## Estimated Scope

- **LoC:** ~175-210 Produktionscode (Backend ~125-140, Frontend ~50-70), plus ~150-220 Tests
- **Files:** 8 (5 Backend-Produktionscode + 1 Test + 1 Frontend + Env-Dateien)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issue_1068_tier_model_display` (Slice 1) | spec (module) | Liefert `User.Tier`, `profileResponse.Tier` und den Frontend-Typ `UserTier` — Grundlage für Validierung ("bereits aktuelles Level") und Anzeige |
| `issue_1069_tier_channel_gating` (Slice 2) | spec (module) | Liefert das etablierte Muster für additive `profileResponse`-Felder (`sms_allowed`) — Vorbild für `requested_tier`/`requested_at` |
| `docs/specs/modules/epic_user_tiers_overview.md` | spec (epic) | Gesamtkontext, PO-Entscheidung "Vermerk in user.json + E-Mail an PO, keine Antragsliste/Genehmigungs-UI" (Zeilen 161-162) |
| `internal/model/user.go` (`type User struct`) | module | Trägt die neuen Felder `RequestedTier`/`RequestedAt` |
| `internal/mail/reset.go` (`BuildResetMail`) | module | Vorbild für neue `BuildTierChangeRequestMail`-Funktion (Plain+HTML, deutsche Texte) |
| `internal/handler/auth.go` (`ForgotPasswordHandler`) | module | Vorbild für nicht-blockierenden Mail-Versand (Goroutine + 20s-Timeout) |
| `internal/store/user.go` (`LoadUser`/`SaveUser`) | module | Read-Modify-Write-Persistenz, unverändert wiederverwendet |

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/config/config.go` | MODIFY | Neues Feld `PoEmail string \`envconfig:"PO_EMAIL" default:"gregor_zwanzig@henemm.com"\`` — eigenes Präfix, da `GZ_MAIL_TO` bislang ausschließlich vom Python-Core gelesen wird und eine andere Namenskonvention hat |
| `.env` / `.env.example` / `.env.tpl` | MODIFY | `PO_EMAIL`-Eintrag ergänzen, analog bestehenden SMTP-Einträgen |
| `internal/model/user.go` | MODIFY | Neue Felder `RequestedTier string \`json:"requested_tier,omitempty"\`` und `RequestedAt *time.Time \`json:"requested_at,omitempty"\`` — Pointer-Typ zwingend, da Go's `encoding/json`-`omitempty` bei `time.Time`-Structs nicht greift (Zero-Value würde als `"0001-01-01T00:00:00Z"` serialisiert statt weggelassen) |
| `internal/mail/tier_change.go` | CREATE | `BuildTierChangeRequestMail(username, currentTier, requestedTier string) mail.Mail` — Plain+HTML, deutsche Texte, analog `reset.go` |
| `internal/handler/auth.go` | MODIFY | Neuer `RequestTierChangeHandler(s *store.Store, cfg config.Config) http.HandlerFunc`; `profileResponse`/`toProfileResponse()` um `requested_tier`/`requested_at` erweitert |
| `internal/router/router.go` | MODIFY | `r.Post("/api/auth/tier-change-request", handler.RequestTierChangeHandler(deps.Store, *deps.Config))` in der authentifizierten Gruppe (NICHT in der Public-Path-Allowlist von `internal/middleware/auth.go`) |
| `frontend/src/routes/account/+page.svelte` | MODIFY | Neues Formular "Level-Wechsel beantragen" (Select mit Tier-Optionen + Button) in der bestehenden Tier-Badge-Card; Pending-Hinweis clientseitig aus `requested_tier vorhanden UND requested_tier !== tier` abgeleitet |
| `internal/handler/auth_tier_change_test.go` | CREATE | Go-`httptest`: Erfolgsfall, Validierungsfälle (`invalid_tier`, `already_current_tier`), Zwei-Nutzer-Test, Mail-Fehler-blockiert-Save-nicht-Test |

## Implementation Details

**Endpoint-Vertrag:** `POST /api/auth/tier-change-request`, authentifiziert über die bestehende
Session-Middleware (`middleware.UserIDFromContext(r.Context())` — niemals `"default"`). Body
`{"requested_tier": "free"|"standard"|"premium"}`.

**Ablauf im Handler (analog `UpdateProfileHandler` + `ForgotPasswordHandler`):**
1. `user, err := s.LoadUser(userId)` — 404 `{"error":"not_found"}` falls kein Nutzer.
2. JSON-Body dekodieren; unbekannter/leerer `requested_tier`-Wert (nicht in
   `free`/`standard`/`premium`) → `400 {"error":"invalid_tier"}`.
3. `requested_tier` identisch zum effektiven aktuellen Tier (nach demselben Default-Fallback wie
   `toProfileResponse()`, also `""`/unbekannt → `"free"`) → `400 {"error":"already_current_tier"}`.
4. Read-Modify-Write: nur `user.RequestedTier` und `user.RequestedAt = &now` setzen, restliches
   Objekt unverändert übernehmen, `s.SaveUser(*user)` — Store-Fehler → `500 {"error":"store_error"}`.
5. **Erst nach erfolgreichem Save** `200 {"status":"ok"}` an den Client zurückgeben.
6. Mail an `cfg.PoEmail` per Goroutine + `select`/`time.After(20*time.Second)` (1:1 Muster aus
   `ForgotPasswordHandler`, Zeilen 250-266): Fehler/Timeout wird nur geloggt (`log.Printf`), hat
   **keinen** Einfluss auf die bereits gesendete HTTP-Response. Ist `cfg.PoEmail == ""`, wird dies
   geloggt, der Antrag bleibt trotzdem gespeichert und die Response bleibt `200`.

**Mail-Inhalt (`BuildTierChangeRequestMail`):** Betreff und Text nennen Nutzername, aktuelles Level,
gewünschtes Level und Zeitpunkt des Antrags — rein informativ für den PO, kein Freigabe-Link, kein
Interaktionselement (keine Genehmigungs-UI in diesem Slice).

**Frontend:** Neues Formular in der bestehenden Account-Karte (Tier-Badge, `+page.svelte:578-643`),
State-Machine analog `sendTest(channel)` (`idle`/`loading`/`ok`/`error`). Select-Optionen aus dem
bereits vorhandenen `UserTier`-Typ (`frontend/src/lib/types.ts:501`). Nach erfolgreichem
`api.post`-Call wird `data.profile` neu geladen bzw. lokal mit der Server-Antwort gemergt, sodass
`requested_tier`/`requested_at` sofort im UI sichtbar sind. Der Pending-Hinweis ("Level-Wechsel zu
X beantragt am ...") wird ausschließlich aus dem Vergleich `requested_tier` vs. `tier` abgeleitet —
kein eigener lokaler "Antrag gestellt"-Client-State, der nach einem Reload verloren ginge.

## Expected Behavior

- **Input:** `POST /api/auth/tier-change-request` mit `{"requested_tier": "standard"}` von einem
  authentifizierten Nutzer, dessen aktuelles `tier` `"free"` ist.
- **Output:** `200 {"status":"ok"}`; `GET /api/auth/profile` liefert danach zusätzlich
  `"requested_tier": "standard"` und `"requested_at": "<RFC3339-Zeitstempel>"`; eine Mail an die
  konfigurierte `PO_EMAIL`-Adresse wird ausgelöst (asynchron, blockiert die Response nicht).
- **Side effects:** `user.json` des anfragenden Nutzers wird um zwei Felder ergänzt
  (Read-Modify-Write, alle übrigen Felder bleiben unverändert). Das effektive `tier`-Feld selbst
  wird durch diesen Endpoint **nicht** verändert — nur der PO kann es durch direktes Bearbeiten der
  Datei setzen. Kein Effekt auf andere Nutzer, keine Antragsliste, kein Freigabe-Workflow.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer mit aktuellem Level `free` / When er
  `POST /api/auth/tier-change-request` mit `{"requested_tier": "standard"}` aufruft / Then
  antwortet der Server mit `200 {"status":"ok"}` und ein anschließender `GET /api/auth/profile`
  für denselben Nutzer liefert `"requested_tier": "standard"` sowie ein nicht-leeres
  `"requested_at"`.
  - Test: Echter HTTP-Call (`httptest.NewRequest`/`httptest.NewRecorder`, kein Mock der
    Fachlogik) gegen den registrierten Handler mit einem präparierten Test-User (`tier: "free"`
    in dessen `user.json`), danach echter zweiter Call gegen `GetProfileHandler` und Prüfung der
    geparsten JSON-Felder im Response-Body.

- **AC-2:** Given ein eingeloggter Nutzer / When er `{"requested_tier": "gold"}` (unbekannter Wert)
  sendet / Then antwortet der Server mit `400 {"error":"invalid_tier"}`, und ein nachfolgender
  `GET /api/auth/profile`-Call zeigt weiterhin `requested_tier` als leer/nicht vorhanden — der
  ungültige Antrag wurde nicht persistiert.
  - Test: Echter HTTP-Call mit `requested_tier: "gold"`, Prüfung von Statuscode und Error-Body,
    anschließend echter Profile-Call zur Bestätigung, dass kein Antrag gespeichert wurde
    (Verhaltensnachweis über die tatsächliche API-Antwort, nicht über Dateiinhalt-Grep).

- **AC-3:** Given ein eingeloggter Nutzer mit aktuellem Level `standard` / When er
  `{"requested_tier": "standard"}` (identisch zum aktuellen Level) sendet / Then antwortet der
  Server mit `400 {"error":"already_current_tier"}`.
  - Test: Echter HTTP-Call mit einem präparierten Test-User (`tier: "standard"`) und identischem
    `requested_tier` im Body, Prüfung des Statuscodes und der Fehlermeldung im echten
    Response-Body.

- **AC-4:** Given zwei verschiedene, echte Test-Nutzer (`user_a`, `user_b`) mit unterschiedlichem
  aktuellem Level / When beide unabhängig voneinander unterschiedliche Level beantragen (z.B.
  `user_a` beantragt `standard`, `user_b` beantragt `premium`) / Then enthält `user_a`s `user.json`
  ausschließlich `user_a`s Antrag und `user_b`s `user.json` ausschließlich `user_b`s Antrag — keine
  Cross-User-Vermischung der `requested_tier`/`requested_at`-Werte.
  - Test: Zwei echte HTTP-Calls mit unterschiedlichem Auth-Kontext (zwei verschiedene
    `user_id`s über `middleware.UserIDFromContext`, nicht `"default"`), danach zwei echte
    `GET /api/auth/profile`-Calls je Nutzer und Vergleich der zurückgegebenen Werte — Pflicht-Test
    laut Projektregel für jeden nutzerbezogenen Endpoint.

- **AC-5:** Given eine SMTP-Konfiguration, die beim Mail-Versand fehlschlägt (z.B. nicht
  erreichbarer Host oder ungültige Credentials) / When ein Nutzer einen gültigen Tier-Change-Antrag
  stellt / Then antwortet der Server trotzdem mit `200 {"status":"ok"}` innerhalb der üblichen
  Antwortzeit (keine Blockade durch den 20s-Mail-Timeout), UND ein nachfolgender
  `GET /api/auth/profile`-Call zeigt, dass `requested_tier`/`requested_at` dennoch gespeichert
  wurden.
  - Test: Echter HTTP-Call gegen den Handler mit einer absichtlich fehlerhaften SMTP-Konfiguration
    (z.B. nicht erreichbarer Host, kein Mock von `mail.Send`/`SendWithFallback` selbst, sondern
    echte Zielkonfiguration ins Leere), Messung, dass die HTTP-Response ankommt ohne auf den
    kompletten 20s-Timeout zu warten (Response muss zeitnah zurückkommen, da sie VOR dem
    Goroutine-Start erfolgt), und Bestätigung der Persistenz über einen echten Profile-Call.

- **AC-6:** Given ein Nutzer hat erfolgreich einen Tier-Change-Antrag gestellt / When
  `GET /api/auth/profile` für diesen Nutzer aufgerufen wird / Then enthält die JSON-Antwort sowohl
  `requested_tier` als auch `requested_at`; für einen Nutzer, der noch nie einen Antrag gestellt
  hat, fehlen beide Felder in der Antwort (bzw. sind leer/nicht vorhanden dank `omitempty` bzw.
  Pointer-`nil`).
  - Test: Echter Profile-Call für einen Test-User mit gestelltem Antrag (Felder vorhanden) und
    echter Profile-Call für einen zweiten Test-User ohne Antrag (Felder fehlen), Prüfung anhand
    des geparsten JSON gegen die tatsächliche API-Antwort.

- **AC-7:** Given ein eingeloggter Nutzer öffnet die Account-Seite und stellt über das neue
  Formular einen Level-Änderungs-Antrag / When der Antrag erfolgreich abgeschickt wurde / Then
  zeigt die Seite sichtbar einen Pending-Hinweis (z.B. "Level-Wechsel zu Standard beantragt"), und
  dieser Hinweis bleibt auch nach einem Neuladen der Seite sichtbar, solange der PO das Level noch
  nicht manuell angeglichen hat.
  - Test: Playwright-E2E gegen Staging als eingeloggter Test-Nutzer: Account-Seite öffnen,
    Ziel-Level im Select auswählen, Formular abschicken, sichtbaren Pending-Hinweis im echten DOM
    prüfen (`toBeVisible()`), Seite neu laden (`page.reload()`), Hinweis erneut im DOM prüfen —
    kein Quelltext-Check, echter Browser-Zustand nach echtem Server-Roundtrip.

## Known Limitations

- **Kein Dedup gegen wiederholte Anträge.** Klickt ein Nutzer das Formular mehrfach hintereinander
  mit demselben Ziel-Level, wird jedes Mal erneut eine Mail an den PO ausgelöst (kein Cooldown,
  keine Erkennung "Antrag bereits identisch offen"). Für MVP bewusst akzeptiert (siehe Analyse),
  sollte bei tatsächlich beobachtetem Mail-Spam als eigenes Folge-Issue behandelt werden.
- **Kein Clear-/Zurückzieh-Endpoint.** Ein einmal gestellter Antrag kann vom Nutzer nicht selbst
  zurückgezogen werden. Der Pending-Zustand verschwindet ausschließlich dadurch, dass der PO das
  `tier`-Feld manuell auf den beantragten Wert setzt — dann stimmen `tier` und `requested_tier`
  wieder überein und der clientseitig abgeleitete Pending-Hinweis verschwindet automatisch.
- **"Last write wins" bei mehrfachen Anträgen desselben Nutzers.** Stellt derselbe Nutzer
  nacheinander mehrere Anträge mit unterschiedlichen Ziel-Leveln, überschreibt jeder neue Antrag
  `requested_tier`/`requested_at` des vorherigen vollständig — es gibt keine Historie und keine
  Warteschlange offener Anträge.
- **Keine Genehmigungs-UI, keine Antragsliste, keine Zahlungsanbindung.** Der PO sieht nur die
  Benachrichtigungsmail und muss `tier` weiterhin manuell in der jeweiligen `user.json` setzen
  (PO-Entscheidung, Epic-Overview Zeilen 161-162) — unverändert seit Slice 1.
- **Kein serverseitiges Rate-Limiting auf diesem Endpoint** über die bestehende Session-Auth
  hinaus. Da der Endpoint keine Werte verändert, die außerhalb des eigenen Accounts wirken, und
  keine Enumeration ermöglicht, wurde ein zusätzlicher IP-Rate-Limiter (wie bei
  `forgot-password`/`register`) für dieses Slice als nicht notwendig bewertet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Erweiterung etablierter Strukturen — zwei neue `omitempty`-Felder auf
  `model.User` und `profileResponse` (gleiches Muster wie `sms_allowed` aus Slice 2), ein neuer
  Handler nach dem 1:1 kopierten Read-Modify-Write- und Goroutine-Mail-Muster aus
  `UpdateProfileHandler`/`ForgotPasswordHandler`, ein neues kleines Mail-Template-Modul analog
  `reset.go`, ein neues Config-Feld nach demselben `envconfig`-Muster wie alle SMTP-Felder. Keine
  neue Architektur-Schicht, kein neuer Persistenz-Mechanismus, kein Cross-Language-Aspekt (anders
  als Slice 2/3) — daher kein eigenständiges ADR-Dokument nötig.

## Changelog

- 2026-07-07: Initial spec created
