---
entity_id: issue_1068_tier_model_display
type: module
created: 2026-07-07
updated: 2026-07-07
status: implemented
version: "1.0"
tags: [tiers, monetization, epic-1067, account]
---

# Issue #1068: Nutzerlevel-Datenmodell + Anzeige im Account

## Approval

- [ ] Approved

## Purpose

Führt ein neues Feld `Tier` (`free`/`standard`/`premium`, Default `free` bei Fehlen/leerem Wert)
auf dem bestehenden Go-User-Modell ein, gibt es über `GET /api/auth/profile` aus und zeigt es als
Badge im Account-Bereich an. Das ist Slice 1 aus Epic #1067 (`docs/specs/modules/epic_user_tiers_overview.md`)
— reine Sichtbarkeit des eigenen Levels, keine Durchsetzung von Channel- oder Frequenz-Limits.

## Source

- **File:** `internal/model/user.go`
- **Identifier:** `type User struct`

## Estimated Scope

- **LoC:** ~80-120
- **Files:** 4
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/user.go` (`Store.LoadUser`/`SaveUser`) | module | Reines JSON-Unmarshal/Marshal — persistiert das neue `Tier`-Feld automatisch, keine Änderung nötig, keine Migration |
| `docs/specs/modules/epic_user_tiers_overview.md` | spec (epic) | Liefert Gesamtkontext, PO-Entscheidungen (Default-Level "free", kein Zwangs-Rewrite) und Slice-Schnitt für Folge-Arbeit |

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/user.go:10-22` | MODIFY | Neues Feld `Tier string \`json:"tier,omitempty"\`` im `User`-Struct, analog zu bestehenden optionalen String-Feldern (`MailTo`, `SmsTo`) |
| `internal/handler/auth.go:363-373` (`profileResponse`) | MODIFY | Neues Feld `Tier string \`json:"tier"\`` OHNE `omitempty` — immer in der Response enthalten |
| `internal/handler/auth.go:385-410` (`toProfileResponse()`) | MODIFY | Default-Fallback: `tier := u.Tier; if tier == "" { tier = "free" }` — Fallback greift NUR hier (Lesezeitpunkt), nicht beim Speichern |
| `frontend/src/routes/account/+page.svelte:589-606` | MODIFY | Neues, immer sichtbares Badge für den Tier-Wert im Bereich "Benachrichtigungen" bzw. direkt daneben, mit deutschem/großgeschriebenem Label ("Free"/"Standard"/"Premium") |
| `frontend/src/lib/types.ts` | MODIFY (Zusatz) | Neuer Typ-Export `export type UserTier = 'free' \| 'standard' \| 'premium';` — reine Ergänzung, kein bestehendes Interface wird verändert |

## Implementation Details

**Go-Modell (`internal/model/user.go`):** Das `User`-Struct bekommt ein weiteres optionales
String-Feld nach dem etablierten Muster der übrigen Kontaktfelder. Leerer String bedeutet "kein
Tier gesetzt" und wird ausschließlich beim Response-Mapping (nicht beim Speichern) als `"free"`
interpretiert.

**API-Response (`internal/handler/auth.go`):** `profileResponse.Tier` wird ohne `omitempty`
deklariert, damit das Feld auch bei leerem Wert im JSON auftaucht (nie einfach fehlt). Der
Default-Fallback auf `"free"` lebt ausschließlich in `toProfileResponse()`. Kein Schreibpfad
(`Store.SaveUser`, `user.go`) darf implizit `"free"` in eine bestehende `user.json` zurückschreiben
— das würde jede Bestandsdatei bei jedem Save unnötig anfassen, obwohl das Verhalten (Anzeige als
"free") bereits ohne diese Schreiboperation korrekt ist.

**Frontend-Typ (`frontend/src/lib/types.ts`):** Da es aktuell kein `Profile`/`UserProfile`-Interface
im Frontend gibt (`data.profile` bleibt lose typisiert `any` aus `.json()`), ist der neue Typ
`UserTier` ein eigenständiger Export ohne Berührung bestehender Typen. Er dient als Grundlage für
Folge-Slices (Channel-Gating), wird in diesem Slice aber nur für das Badge-Label-Mapping (Groß-
schreibung) genutzt.

**Frontend-Anzeige (`frontend/src/routes/account/+page.svelte`):** Anders als die bestehenden
bedingten Badges (`{#if data.profile.mail_to}`) ist das Tier-Badge unbedingt sichtbar — jeder
Nutzer hat immer einen Tier-Wert (mindestens "free"). Platzierung im bestehenden Bereich
"Benachrichtigungen" (Zeilen 589-606) oder als eigener kleiner Block direkt darüber/darunter,
gestylt wie die bestehenden `<Badge variant="secondary">`-Elemente. Label-Mapping:
`free` → "Free", `standard` → "Standard", `premium` → "Premium".

## Expected Behavior

- **Input:** `GET /api/auth/profile` (userscoped über `middleware.UserIDFromContext`), zusätzlich
  der rohe Zustand der `user.json`-Datei des angefragten Nutzers (Feld `tier` vorhanden/fehlend/leer/gesetzt).
- **Output:** JSON-Response mit Feld `tier` (immer einer von `free`/`standard`/`premium`); Account-Seite
  zeigt ein Badge mit dem passenden deutschen Label.
- **Side effects:** Keine — reines Lesen und Anzeigen, kein Schreibpfad wird durch dieses Slice verändert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer, dessen `user.json` kein `tier`-Feld enthält (Neuanlage oder
  Bestandsnutzer vor diesem Feature) / When dieser Nutzer sich einloggt und `GET /api/auth/profile`
  aufgerufen wird / Then enthält die JSON-Antwort `"tier": "free"`.
  - Test: Echter HTTP-Call gegen `/api/auth/profile` (eingeloggter Test-User ohne `tier`-Feld in
    seiner Persistenzdatei) gegen die Staging-API; Prüfung des geparsten JSON-Felds `tier == "free"`
    im Response-Body (kein Datei-Read, kein Mock).

- **AC-2:** Given ein Nutzer, dessen `user.json` explizit `"tier": "standard"` enthält / When
  `GET /api/auth/profile` für diesen Nutzer aufgerufen wird / Then enthält die JSON-Antwort
  `"tier": "standard"` unverändert (kein Downgrade auf "free").
  - Test: Echter HTTP-Call gegen `/api/auth/profile` mit einem zweiten Test-User, dessen
    Persistenzdatei vorab mit `tier: standard` präpariert wurde; Prüfung des Response-Felds.
    Zusammen mit AC-1 als Zwei-Nutzer-Test gegen Cross-User-Datenleck abgesichert.

- **AC-3:** Given ein eingeloggter Nutzer öffnet die Account-Seite (`/account`) / When die Seite
  vollständig geladen ist / Then ist im Account-Bereich ein für den Nutzer sichtbares Element zu
  sehen, das seinen aktuellen Level ("Free", "Standard" oder "Premium") anzeigt — unabhängig davon,
  ob Kontaktdaten (E-Mail/Telegram) konfiguriert sind.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer: `/account` öffnen, prüfen dass ein
    sichtbares Element mit Text "Free" (oder dem tatsächlich gesetzten Level) im Account-Bereich
    gerendert ist (`page.getByText(...)`/`toBeVisible()` gegen das echte DOM, kein Quelltext-Check).

- **AC-4:** Given ein Bestandsnutzer, dessen `user.json` kein `tier`-Feld enthält / When
  `GET /api/auth/profile` für diesen Nutzer aufgerufen wird und die Response `tier: "free"`
  zurückliefert / Then bleibt die zugrunde liegende `user.json`-Datei danach byteidentisch zum
  Zustand vor dem Aufruf (kein Feld wird nachträglich in die Datei geschrieben).
  - Test: Vor dem HTTP-Call einen Hash/die Bytes der Test-`user.json` erfassen, den echten
    `/api/auth/profile`-Call ausführen, danach die Datei erneut lesen und mit dem vorherigen Zustand
    vergleichen (Beweis über tatsächliches Dateiverhalten, nicht über Quellcode-Inspektion des
    Handlers).

## Known Limitations

- **Kein Enforcement:** Dieses Slice liefert ausschließlich Anzeige. Channel-Gating (welche
  Versand-Kanäle je Level erlaubt sind) und Alert-/Update-Frequenz-Limits je Level sind explizit
  NICHT Teil dieses Scopes — sie folgen in weiteren Slices aus Epic #1067
  (`docs/specs/modules/epic_user_tiers_overview.md`, Slice 2 Channel-Gating, Slice 3
  Alert-Frequenz), für die noch keine eigenen Issue-Nummern vergeben sind.
- **Kein Level-Änderungs-Antrag:** Ein Nutzer kann in diesem Slice sein Level nicht selbst ändern
  oder eine Änderung beantragen — das ist Folge-Arbeit (Slice 4 aus Epic #1067).
- **Kein Admin-Werkzeug:** Level-Zuweisung erfolgt weiterhin ausschließlich manuell durch direktes
  Setzen von `tier` in der jeweiligen `user.json` durch den Product Owner.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Feld-Ergänzung nach bereits etabliertem Muster (optionales String-Feld
  mit `omitempty` auf dem bestehenden `User`-Struct, Response-Mapping in der einzigen existierenden
  Übersetzungsstelle `toProfileResponse()`). Keine neue Persistenzschicht, kein neuer
  Architektur-Layer, keine strukturelle Entscheidung nötig.

## Changelog

- 2026-07-07: Initial spec created
- 2026-07-07: Implementiert, validiert (Adversary VERIFIED), Folge-Issue #1074 für ungültige
  tier-Werte (Nachverfolgung)
