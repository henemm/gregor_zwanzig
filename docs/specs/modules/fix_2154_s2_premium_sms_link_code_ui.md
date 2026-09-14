---
entity_id: fix_2154_s2_premium_sms_link_code_ui
type: module
created: 2026-09-13
updated: 2026-09-13
status: draft
version: "1.0"
tags: [premium-sms, frontend, account, garmin]
---

<!-- Issue #2154 (Scheibe B -- Konto-Oberflaeche), Teil von Epic #2138.
     Baut auf Scheibe A (fix_2154_premium_sms_verknuepfungscode.md, LIVE seit
     2026-09-13, 29b5ae91) auf, OHNE deren Backend-Vertrag zu aendern. Loest
     KEINE bestehende Spec ab -- ist die dort in "Out of Scope" angekuendigte
     Folgearbeit. -->

# Premium-SMS Verknüpfungscode — Scheibe B: Konto-Oberfläche im Frontend

## Approval

- [ ] Approved

## Purpose

Scheibe A hat einen Verknüpfungs-Code eingeführt, der die Garmin-inReach-
Rufnummer eines Nutzers sicher mit dessen Konto verbindet
(`GET`/`POST /api/auth/premium-sms-link-code`), aber ausschließlich als
programmatischen Endpoint — ein Premium-Nutzer hat aktuell keine Möglichkeit,
diesen Code über die Oberfläche zu sehen oder zu erneuern. Diese Scheibe
ergänzt die Kontoseite (`/account`) um genau diese Karte: Status anzeigen,
Code erzeugen bzw. erneuern, den zurückgegebenen Klartext einmalig anzeigen.

## Source

- **File:** `frontend/src/routes/account/+page.svelte` (MODIFY) — bindet die
  neue Karte ein, hält `$state`/`api.post`-Aufrufe, nur sichtbar bei
  `data.profile?.tier === 'premium'`
- **File:** `frontend/src/routes/account/+page.server.ts` (MODIFY) — `GET
  /api/auth/premium-sms-link-code` in den bestehenden `Promise.all`-Block
  aufnehmen, Ergebnis fail-closed auf `premiumSmsLinkCodeExists: boolean`
  normalisieren
- **File:** `frontend/src/lib/components/account/PremiumSmsLinkCard.svelte`
  (CREATE) — rein props-getriebene Darstellungskomponente (kein eigener
  State außer dem Dialog-Sichtbarkeits-Flag, das von `+page.svelte` kommt),
  Vorbild `VTBriefingChannels.svelte`
- **File:**
  `frontend/src/lib/components/account/__tests__/premium_sms_link_card_render.test.ts`
  (CREATE) — echtes serverseitiges Rendern (`svelte/server`) der Komponente
  je Props-Kombination, Vorbild
  `frontend/src/lib/components/shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts`
- **File:** `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.ts` (CREATE) —
  reine, Svelte-freie Entscheidungsfunktionen nach Vorbild
  `presetCardHelpers.ts`
- **File:** `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.test.ts`
  (CREATE) — `node --test`-Unit-Tests für die Helper-Funktionen
- **File:**
  `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts`
  (CREATE) — ruft die `load`-Funktion aus `+page.server.ts` direkt mit
  gestubbtem `fetch` auf und prüft das zurückgegebene Objekt

> **Schicht-Hinweis:** Ausschließlich Frontend (`frontend/src/...`,
> SvelteKit). Kein Go-API-Code, kein Python-Core-Code wird angefasst.
> `internal/handler/premium_sms_link_code.go` bleibt unverändert — geprüft
> gegen den aktuellen Stand (Scheibe A), Response-Verträge s. Dependencies.

## Estimated Scope

- **LoC:** ~350-460 (inkl. aller drei Test-Dateien) — deutlich über der
  Grobschätzung aus der Kontext-Phase (~120-180), weil erst die Extraktion
  einer props-getriebenen Komponente plus reiner Entscheidungsfunktionen für
  Dialog/Fehler/Fail-closed die Karte ohne Component-Test-Framework
  (kein jsdom in diesem Repo) überhaupt beweisbar macht. `loc_limit_override
  500` in `/40-tdd-red` wird voraussichtlich benötigt — Entscheidung dort
  anhand des tatsächlichen RED-Umfangs, nicht durch Kürzen der Testdecke.
- **Files:** 7 (2 MODIFY, 5 CREATE)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md` | Vorbild/Vertrag | Scheibe-A-Spec — Backend-Vertrag der beiden Endpoints, unverändert konsumiert |
| `internal/handler/premium_sms_link_code.go` | module (read-only) | `POST` liefert `{"code": "..."}` einmalig, Fehler als Klartext (`http.Error`, NICHT JSON) — s. Implementation Details |
| `docs/reference/api_contract.md:3323-3378` | Vertrag | Vollständige Beschreibung beider Endpoints inkl. Fehlerfälle |
| `frontend/src/routes/account/+page.svelte:303-568` (Telegram-Karte) | Vorbild | Zustand aus `data.*`, Aktion per `api.*`, lokales `$state`-Update ohne Reload |
| `frontend/src/routes/account/+page.svelte:387-422` (`showLogoutAllDialog`) | Vorbild | Bestätigungsdialog vor irreversibler Aktion |
| `frontend/src/lib/utils/presetCardHelpers.ts` + `.test.ts` | Vorbild | Reine, Svelte-freie Helper-Funktionen, `node --test`-testbar |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | Vorbild | Props-getriebene Komponente statt Logik direkt in der Route-Seite — macht Zustände per SSR-Render einzeln beweisbar |
| `frontend/src/lib/components/shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts` | Vorbild | `svelte/server`-Rendern ohne Mock, inkl. `isDisabled()`-Helper für `disabled`-Attribute |
| `frontend/src/lib/api.ts:134-138,163-167` | module | Fehlerform bei Nicht-JSON-Backend-Antwort (`{error: "HTTP <status>"}`) UND bei Netzfehler (`Error` mit `.message`) — Grundlage für `errorMessageFrom` |
| `internal/model/tier.go::PremiumSmsAllowed/EffectiveTier` | module (read-only) | Bestätigt: `profile.tier` (Response von `GET /api/auth/profile`, `internal/handler/auth.go:676`) ist bereits `EffectiveTier`-normalisiert — die UI-Sichtbarkeitsgrenze `tier === 'premium'` deckt sich mit der Kandidatenfilterung in `premium_sms_connect.go:76` |

## Implementation Details

### Reine Entscheidungslogik (`premiumSmsLinkCodeHelpers.ts`)

Sechs kleine, Svelte-freie Funktionen tragen jede beobachtbare Verzweigung,
damit sie ohne Component-Interaktions-Test beweisbar sind (dieses Repo hat
kein jsdom, nur `node --test` + `svelte/server`, s. Known Limitations):

```ts
function shouldShowPremiumSmsLinkCard(tier: UserTier | undefined): boolean
function needsRenewConfirmation(exists: boolean): boolean
function resolveGenerateClick(exists: boolean, busy: boolean):
  'call-post' | 'confirm-dialog' | 'noop'
function resolveDialogAction(decision: 'confirm' | 'cancel'):
  'call-post' | 'none'
function deriveLinkCodeExists(
  response: { exists?: boolean } | null | undefined
): boolean   // fail-closed: alles außer explizit {exists:false} => true
function errorMessageFrom(e: unknown, fallback: string): string
```

`resolveGenerateClick` und `resolveDialogAction` sind die beiden Stellen,
an denen `+page.svelte` tatsächlich verzweigt: der Klick-Handler ruft nur
`resolveGenerateClick` auf (Erzeugen/Erneuern-Button), der Dialog-Handler
nur `resolveDialogAction` (Bestätigen/Abbrechen). Beide geben ausschließlich
`'call-post'`/`'confirm-dialog'`/`'noop'`/`'none'` zurück — jede
Verzweigung ist damit eine `node --test`-Assertion, nicht nur eine
Behauptung über den Svelte-Code, der sie aufruft.

`errorMessageFrom` prüft in dieser Reihenfolge: `.detail` (falls das Backend
je JSON mit Klartext liefert) → `.error`, sofern er NICHT dem Muster
`/^HTTP \d+$/` entspricht (s. u.) → `.message` (Netzfehler-Fall aus
`$lib/api.ts:163-167`, ein echtes `Error`-Objekt mit deutschem Text) →
fester Fallback-Text.

### Props-getriebene Karte statt Logik in `+page.svelte`

`PremiumSmsLinkCard.svelte` bekommt ausschließlich Props:
`{ tier, exists, codeValue, busy, errorMsg, showRenewConfirm,
onGenerateOrRenewClick, onDialogConfirm, onDialogCancel }` — kein eigener
API-Aufruf, kein eigener `$state` außer dem, was zur reinen Darstellung
gehört. Das macht jede Sichtbarkeits-/Anzeige-Kombination per `svelte/server`
ohne volle `/account`-Seite (samt `data.trips`, `data.scheduler` usw.)
render- und prüfbar — Vorbild `VTBriefingChannels.svelte` plus dessen
`isDisabled()`-Test-Helper für das `disabled`-Attribut. `+page.svelte` hält
weiterhin allen `$state` (`linkCodeExists`, `linkCodeValue`, `linkCodeBusy`,
`linkCodeErrorMsg`, `showRenewConfirm`) und den `api.post`-Aufruf — die
Komponente reicht nur die Callback-Ergebnisse durch.

`linkCodeValue` lebt ausschließlich in diesem lokalen `$state`, das **nie**
Teil von `data`/`PageData` wird und **nie** über `+page.server.ts` läuft —
strukturelle Grundlage von AC-7 (Reload löscht den Code), geprüft über die
`load`-Funktion selbst (s. Test Plan), nicht über eine Textsuche im
Quellcode.

### Fail-closed Anfangszustand (`+page.server.ts`)

`GET /api/auth/premium-sms-link-code` wird wie `profile` per `Promise.all`
mit Cookie-Weiterreiche geladen; bei Netzfehler/Non-200 liefert die Kette
`null` (wie die anderen Einträge), `deriveLinkCodeExists(null)` normalisiert
das serverseitig auf `true`. Begründung: fälschlich `false` anzunehmen hieße,
„Code erzeugen" ohne Bestätigung anzuzeigen — ein Klick würde dann einen
tatsächlich funktionierenden Code entwerten, ohne dass der Nutzer je gefragt
wurde. Ein irrtümliches `true` kostet höchstens einen zusätzlichen
Bestätigungsklick.

### Fehlerformat des Backends (Abweichung vom Telegram-Vorbild)

`premium_sms_link_code.go` antwortet bei Fehlern mit `http.Error(w, "...",
status)` — **Klartext, keine JSON-Struktur**, anders als
`docs/reference/api_contract.md:3353` dokumentiert (dort steht
`{"error":"failed to generate code"}`; das ist Dokumentations-Drift, siehe
Known Limitations, kein Ziel dieser Scheibe). `$lib/api.ts:134` fängt das
über `res.json().catch(() => ({error: \`HTTP ${res.status}\`}))` ab — der
Aufrufer bekommt also `{error: "HTTP 500", status: 500}`, niemals `.detail`.
`errorMessageFrom` filtert `/^HTTP \d+$/` heraus und zeigt einen festen
deutschen Text statt der rohen Zeichenkette „HTTP 500".

`data-testid`-Konvention: `premium-sms-link-card`, `premium-sms-link-generate`,
`premium-sms-link-renew`, `premium-sms-link-code-value`,
`premium-sms-link-renew-confirm`, `premium-sms-link-renew-cancel`,
`premium-sms-link-error`.

## Expected Behavior

- **Input:** Klick auf „Code erzeugen"/„Code erneuern" (ggf. nach
  Bestätigungsdialog); serverseitiger Anfangszustand aus `+page.server.ts`
- **Output:** `POST /api/auth/premium-sms-link-code` liefert `{"code": "..."}`
  einmalig; die Karte zeigt ihn nur für die Dauer der Seiten-Sitzung (kein
  Reload-fester State)
- **Side effects:** keine neuen — der bestehende Endpoint aus Scheibe A wird
  lediglich aus der Oberfläche statt nur programmatisch aufgerufen; kein
  neuer Schreibpfad, kein neues Datenschema

## Acceptance Criteria

- **AC-1:** Given ein Premium-Nutzer hat noch keinen Verknüpfungscode
  (`exists === false`) / When die Karte gerendert wird / Then zeigt sie den
  Button „Code erzeugen" und keinerlei Code-Klartext.
  - Test: `svelte/server`-Render von `PremiumSmsLinkCard` mit
    `{ tier: 'premium', exists: false, codeValue: null }` — HTML enthält
    `data-testid="premium-sms-link-generate"`, HTML enthält NICHT
    `data-testid="premium-sms-link-renew"` und NICHT
    `data-testid="premium-sms-link-code-value"`.

- **AC-2:** Given ein Premium-Nutzer ohne bestehenden Code klickt auf „Code
  erzeugen" / When der `POST`-Aufruf erfolgreich zurückkommt / Then wird der
  zurückgegebene Klartext-Code einmalig angezeigt, mit dem Hinweis, dass er
  nicht erneut erscheint.
  - Test: `resolveGenerateClick(false, false) === 'call-post'` (`node
    --test`, beweist den Klickpfad); zusätzlich `svelte/server`-Render mit
    `codeValue: 'AB3CD9F'` — HTML enthält
    `data-testid="premium-sms-link-code-value"` UND den Hinweistext „wird
    nicht erneut angezeigt".

- **AC-3:** Given ein Premium-Nutzer hat bereits einen Code
  (`exists === true`) / When die Karte gerendert wird / Then zeigt sie
  „Code erneuern" statt „Code erzeugen", ohne den Code selbst preiszugeben.
  - Test: `needsRenewConfirmation(true) === true`; `svelte/server`-Render mit
    `{ exists: true, codeValue: null }` — HTML enthält
    `data-testid="premium-sms-link-renew"`, HTML enthält NICHT
    `data-testid="premium-sms-link-generate"` und NICHT den Klartext-Testid.

- **AC-4:** Given ein bestehender Code ist vorhanden / When der Nutzer auf
  „Code erneuern" klickt / Then öffnet sich zuerst ein Bestätigungsdialog,
  OHNE dass bereits ein `POST`-Aufruf stattgefunden hat.
  - Test: `resolveGenerateClick(true, false) === 'confirm-dialog'`, niemals
    `'call-post'`; `svelte/server`-Render mit `showRenewConfirm: true` zeigt
    den Dialog-Markup (`premium-sms-link-renew-confirm`/`-cancel`), ohne dass
    ein `codeValue` gesetzt sein muss.

- **AC-5:** Given der Bestätigungsdialog für „Code erneuern" ist offen / When
  der Nutzer bestätigt / Then läuft derselbe `POST`-Aufruf wie bei AC-2 und
  der neu zurückgegebene Code ersetzt die Anzeige.
  - Test: `resolveDialogAction('confirm') === 'call-post'` — identischer
    Rückgabewert wie `resolveGenerateClick(false, false)`, beweist, dass
    Bestätigen denselben Aktionscode auslöst wie Erst-Erzeugen (kein
    zweiter, potenziell abweichender POST-Pfad).

- **AC-6:** Given der Bestätigungsdialog für „Code erneuern" ist offen / When
  der Nutzer abbricht / Then wird KEIN `POST`-Aufruf ausgelöst und der
  vorherige Zustand bleibt unverändert.
  - Test: `resolveDialogAction('cancel') === 'none'`, niemals `'call-post'`
    — die reine Funktion beweist strukturell, dass Abbrechen nie postet.

- **AC-7:** Given ein Nutzer hat gerade einen neuen Code angezeigt bekommen
  / When die Seite neu geladen wird / Then ist der Klartext-Code nicht mehr
  sichtbar, die Karte zeigt nur noch „Code vorhanden" (kein GET liefert den
  Code je erneut, Backend hält nur den Hash).
  - Test: `load()` aus `+page.server.ts` direkt aufrufen (gestubbtes
    `fetch`, das für `/api/auth/premium-sms-link-code` `{"exists": true}`
    liefert) — das zurückgegebene Objekt enthält `premiumSmsLinkCodeExists:
    true` und **kein** Feld, das einen Code-Klartext trägt (Prüfung auf den
    tatsächlichen Rückgabewert der Funktion, nicht auf Quelltext).

- **AC-8:** Given ein Nutzer mit Tier `free` oder `standard` / When die
  Karte gerendert wird / Then erscheint sie gar nicht (kein Hinweistext,
  kein Platzhalter).
  - Test: `shouldShowPremiumSmsLinkCard('free') === false`,
    `('standard') === false`, `(undefined) === false`; zusätzlich auf
    Staging messbar (bestehendes Nicht-Premium-Testkonto, s. Test Plan).

- **AC-9:** Given der `POST`-Aufruf schlägt fehl (Backend-500 ODER
  Netzfehler) / When die Antwort ausgewertet wird / Then zeigt die Karte
  eine verständliche Fehlermeldung statt eines stillen Absturzes oder der
  rohen Zeichenkette „HTTP 500".
  - Test: `errorMessageFrom({ error: 'HTTP 500', status: 500 }, 'Code-
    Vorgang fehlgeschlagen') === 'Code-Vorgang fehlgeschlagen'`;
    `errorMessageFrom(new Error('Ohne Verbindung...'), 'fallback') ===
    'Ohne Verbindung...'` (Netzfehler-Fall über `.message`);
    `svelte/server`-Render mit `errorMsg` gesetzt zeigt
    `data-testid="premium-sms-link-error"`.

- **AC-10:** Given der initiale Statusabruf
  (`GET /api/auth/premium-sms-link-code`) in `+page.server.ts` schlägt fehl
  oder liefert eine leere/unerwartete Antwort / When die Seite dennoch
  gerendert wird / Then gilt der Code als vorhanden (fail-closed) — ein
  transienter Fehler darf nie einen unbestätigten Erzeugen-Klick
  ermöglichen, der einen tatsächlich funktionierenden Code stillschweigend
  entwertet.
  - Test: `deriveLinkCodeExists(null) === true`,
    `deriveLinkCodeExists(undefined) === true`,
    `deriveLinkCodeExists({}) === true`,
    `deriveLinkCodeExists({ exists: false }) === false`,
    `deriveLinkCodeExists({ exists: true }) === true`; zusätzlich `load()`
    mit einem `fetch`-Stub, der `res.ok === false` liefert, muss
    `premiumSmsLinkCodeExists: true` zurückgeben.

- **AC-11:** Given ein `POST`-Aufruf läuft bereits (`busy === true`) / When
  der Nutzer den Button während der laufenden Anfrage erneut klickt / Then
  löst der Klick keinen zweiten `POST`-Aufruf aus und beide Buttons sind
  sichtbar deaktiviert.
  - Test: `resolveGenerateClick(false, true) === 'noop'` und
    `resolveGenerateClick(true, true) === 'noop'`; `svelte/server`-Render
    mit `busy: true` — `isDisabled()` (Vorbild-Helper aus
    `premium_sms_context_gating_render.test.ts`) liefert `true` für den
    jeweils sichtbaren Button.

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein echtes Backend):

- `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.test.ts` (CREATE):
  - `shouldShowPremiumSmsLinkCard` — premium/free/standard/undefined (AC-8)
  - `needsRenewConfirmation` — true/false (AC-3, AC-4)
  - `resolveGenerateClick` — alle Kombinationen aus `exists`/`busy` (AC-2,
    AC-4, AC-11)
  - `resolveDialogAction` — confirm/cancel (AC-5, AC-6)
  - `deriveLinkCodeExists` — null/undefined/leeres Objekt/explizite Werte
    (AC-10)
  - `errorMessageFrom` — `HTTP <n>`-Filter, `.detail`-Vorrang,
    `.message`-Fall (Netzfehler), Fallback (AC-9)
- `frontend/src/lib/components/account/__tests__/premium_sms_link_card_render.test.ts`
  (CREATE), echtes `svelte/server`-Rendern von `PremiumSmsLinkCard` je
  Props-Kombination (AC-1, AC-2, AC-3, AC-4, AC-9, AC-11)
- `frontend/src/routes/account/__tests__/premium_sms_link_code_load.test.ts`
  (CREATE): `load()` mit gestubbtem `fetch` — Erfolg, Non-200, Netzfehler
  (AC-7, AC-10)

Adversary-Mutationsprobe (Pflicht, `/50-implement`): gezielt verfälschen und
prüfen, dass ein Test rot wird, für — den `resolveGenerateClick`- bzw.
`resolveDialogAction`-Aufruf im jeweiligen Handler in `+page.svelte`
entfernen/vertauschen, `linkCodeValue` versehentlich in `data`/`PageData`
durchreichen, das `disabled`-Attribut der Buttons von `busy` entkoppeln.
Leitfrage laut `.claude/agents/implementation-validator.md`: ist die
Zusicherung an der Stelle geprüft, an der sie wirkt (Wiring in
`+page.svelte`), nicht nur dort, wo die reine Funktion oder die
Darstellungskomponente stehen.

Staging (`/e2e-verify`): AC-8 ist real messbar — auf Staging existiert
bereits ein Nicht-Premium-Testkonto; ein Login mit diesem Konto muss zeigen,
dass die Karte auf `/account` fehlt. Alle übrigen ACs (Erzeugen/Erneuern,
Klartext-Anzeige, Reload-Verhalten) sind auf Staging strukturell NICHT
prüfbar, weil dort kein Premium-Testkonto existiert — dieselbe Einschränkung,
die bereits Scheibe A auf 3 von 12 ACs beschränkt hat. Für diese ACs trägt
ausschließlich die Kern-Schicht den Nachweis. Playwright/`ci_e2e_specs.txt`
wird für diese Karte nicht ergänzt, da ohne Premium-Testkonto kein
zusätzlicher Beweis entstünde.

## Known Limitations

- **Kein „zuletzt erzeugt am"-Zeitstempel.** Der Backend-Endpoint aus
  Scheibe A liefert nur `{"exists": bool}`, keinen Zeitpunkt. Die Anzeige
  bleibt bewusst auf Ja/Nein beschränkt — keine Lücke dieser Scheibe.
- **Automatisierte Tests beweisen Props→Markup und reine Entscheidungslogik
  vollständig, NICHT die echte Klick-Interaktion im Browser.** Dieses Repo
  hat kein jsdom; `svelte/server` rendert nur serverseitig, ohne
  Event-Handling. Dass ein realer Button-Klick tatsächlich
  `resolveGenerateClick`/`resolveDialogAction` aufruft und deren Ergebnis
  korrekt verdrahtet, ist NICHT automatisiert bewiesen — abgesichert über
  die Adversary-Mutationsprobe an der Wiring-Stelle und den Pflicht-Check
  durch `fresh-eyes-inspector` (UI-Änderung).
- **Auf Staging existiert kein Premium-Testkonto.** Nur AC-8 (Karte fehlt
  für Nicht-Premium) ist dort real prüfbar — dieselbe strukturelle Grenze
  wie bei Scheibe A. Playwright-E2E für diese Karte entfällt deshalb.
- **Backend gated nicht nach Tier.** `POST`/`GET
  /api/auth/premium-sms-link-code` prüfen nur die Session, nicht den Tier
  des Nutzers — jeder angemeldete Nutzer könnte den Endpoint direkt (ohne
  UI) aufrufen. Die UI-Sichtbarkeitsgrenze `tier === 'premium'` ist eine
  UX-Entscheidung, kein Sicherheitsgate; ein Code eines Nicht-Premium-Nutzers
  bleibt wirkungslos, weil `premium_sms_connect.go` nur `EffectiveTier ==
  'premium'`-Kandidaten berücksichtigt (Scheibe A, unverändert). Keine
  Änderung an dieser Scheibe.
- **`api_contract.md:3353` dokumentiert ein JSON-Fehlerformat, das der
  Handler nicht liefert** (`http.Error` = Klartext). Diese Scheibe behebt
  die Doku-Drift nicht (Backend unverändert lassen), sondern baut die
  Fehlerbehandlung gegen das tatsächliche Verhalten (`errorMessageFrom`
  filtert `HTTP <n>`). Eine spätere Korrektur der Doku bzw. des Handlers ist
  eigenständige Folgearbeit.
- **Fail-closed-Asymmetrie:** Schlägt der initiale Statusabruf transient
  fehl, obwohl der Nutzer noch nie einen Code erzeugt hat, zeigt die Karte
  unnötig „Code erneuern" mit Bestätigungsdialog statt „Code erzeugen" —
  ein zusätzlicher, aber harmloser Klick. Bewusst in Kauf genommen, weil die
  Alternative (fail-open) einen bestehenden Code ungefragt gefährden könnte.

## Out of Scope

- Jede Änderung an `internal/handler/premium_sms_link_code.go` oder anderen
  Scheibe-A-Dateien — Backend-Vertrag bleibt exakt wie spezifiziert.
- Korrektur der Dokumentations-Drift in `api_contract.md:3353`
  (JSON- vs. Klartext-Fehlerformat) — eigenständige Folgearbeit, kein
  UI-Blocker.
- Zeitstempel „zuletzt erzeugt" — Backend liefert ihn nicht, kein Umbau des
  Datenmodells in dieser Scheibe.
- Playwright-E2E-Spezifikation für diese Karte — mangels Premium-Testkonto
  auf Staging strukturell nicht beweiskräftig, s. Test Plan.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (bestehendes ADR-0049 reicht)
- **Rationale:** ADR-0049 legt Premium-SMS als vierten Kanal fest; diese
  Scheibe ist reine Oberfläche für einen in Scheibe A bereits entschiedenen
  Sicherheitsmechanismus (Verknüpfungscode) und folgt etablierten
  UI-Mustern derselben Seite (Telegram-Karte, Passkey-Bestätigungsdialog,
  props-getriebene Komponente nach `VTBriefingChannels`-Vorbild). Kein neuer
  Architektur-Grundsatz, daher kein neues ADR.

## Changelog

- 2026-09-13: Initial spec created
