---
entity_id: issue-609-sms-profil-feld
type: module
created: 2026-06-05
updated: 2026-06-05
status: implemented
version: "1.0"
tags: [go, sveltekit, sms, account, profile, user-model, trips, compare]
---

<!-- Issue #609 — SMS-Rufnummer im Admin-Interface pro Nutzer konfigurierbar machen -->

# SMS-Rufnummer im Nutzerprofil und in Trip/Vergleichs-Kanalauswahl

## Approval

- [ ] Approved

## Purpose

Ergaenzt das Nutzerprofil um ein `sms_to`-Feld (Handynummer im internationalen Format), damit der SMS-Kanal aus Issue #608 eine Empfaengernummer erhaelt. Zusaetzlich wird SMS als waehlbarer Kanal in der Trip-Report-Konfiguration und im Vergleichs-Wizard (Step 5) ergaenzt — analog zu E-Mail und Telegram. Ein bestehender Feldname-Mismatch (`sms_phone` vs. `sms_to`) in `EditReportConfigSection.svelte` wird dabei behoben.

## Source

- **File:** `internal/model/user.go` (ERWEITERT) — `SmsTo string`-Feld im `User`-Struct
- **File:** `internal/handler/auth.go` (ERWEITERT) — `sms_to` in `profileResponse` + `UpdateProfileHandler`
- **File:** `internal/handler/profile_test.go` (ERWEITERT) — Test fuer `sms_to`-Roundtrip
- **File:** `frontend/src/routes/account/+page.svelte` (ERWEITERT) — `smsTo`-State, Eingabefeld, `save()`-Integration
- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (ERWEITERT) — `sms_phone`→`sms_to` fix + SMS-Checkbox-UI
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` (ERWEITERT) — `sendSms`-Feld
- **File:** `frontend/src/lib/components/compare/steps/Step5Versand.svelte` (ERWEITERT) — SMS-ChannelToggle + Profil-Context
- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte` (ERWEITERT) — `sms_to` im Profil-Context

> **Schicht-Hinweis:** Die Persistenz (`SmsTo string` in `User`) und der API-Handler liegen in der **Go-API** (`internal/`). Die UI-Aenderungen liegen im **SvelteKit-Frontend**. Das Python-Backend liest `user.SmsTo` bereits via JSON-Persistenz — keine Python-Aenderung noetig.

## Estimated Scope

- **LoC:** ~120
- **Files:** 8
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/user.go` | go package | `User`-Struct erhaelt `SmsTo string \`json:"sms_to,omitempty"\`` — wird in `data/users/{id}/user.json` persistiert |
| `PUT /api/auth/profile` | Go API endpoint | Nimmt `sms_to` als optionales Feld entgegen; bestehender Handler wird additiv erweitert |
| `GET /api/auth/profile` (`profileResponse`) | Go API endpoint | Gibt `sms_to` zurueck damit das Frontend den gespeicherten Wert anzeigen kann |
| `$lib/api.ts` — `api.put()` | SvelteKit helper | Sendet `sms_to` im bestehenden `save()`-Call mit |
| `SMSOutput` (`src/outputs/sms.py`) | Python backend | Liest `user.SmsTo` aus der JSON-Persistenz — Downstream-Abhaenger, wird durch diese Spec erst einsatzbereit |
| `EditReportConfigSection.svelte` | SvelteKit component | Trip-Report-Kanal-Auswahl — behebt `sms_phone`→`sms_to` Feldname-Mismatch, ergaenzt SMS-Checkbox |
| `compareWizardState.svelte.ts` | SvelteKit state | Vergleichs-Wizard-State — ergaenzt `sendSms: boolean` |
| `Step5Versand.svelte` | SvelteKit component | Compare-Wizard Step 5 — ergaenzt SMS-ChannelToggle analog zu E-Mail/Telegram |
| `CompareTabs.svelte` | SvelteKit component | Holt Profil fuer Wizard — ergaenzt `sms_to` in Typdefinition und Profile-Context |

## Implementation Details

### Step 1: Go-Model erweitern (`internal/model/user.go`, +1 LoC)

```go
type User struct {
    // ... bestehende Felder ...
    MailTo   string `json:"mail_to,omitempty"`
    SmsTo    string `json:"sms_to,omitempty"` // NEU
    // ... weitere bestehende Felder ...
}
```

`omitempty` stellt sicher, dass bestehende `user.json`-Dateien ohne das Feld weiterhin geladen werden koennen — kein Schema-Migration-Skript noetig (additives Feld).

### Step 2: API-Response erweitern (`internal/handler/auth.go`, +3 LoC)

`profileResponse`-Struct um `SmsTo string \`json:"sms_to,omitempty"\`` ergaenzen:

```go
type profileResponse struct {
    // ... bestehende Felder ...
    MailTo string `json:"mail_to,omitempty"`
    SmsTo  string `json:"sms_to,omitempty"` // NEU
    // ...
}
```

In `toProfileResponse()` (oder inline-Befuellung):

```go
resp.SmsTo = user.SmsTo // NEU
```

### Step 3: Update-Handler erweitern (`internal/handler/auth.go`, +4 LoC)

`UpdateProfileHandler` liest `sms_to` aus dem Request-Body und schreibt es in das User-Objekt. Muster identisch zu `mail_to`:

```go
if v, ok := body["sms_to"]; ok {
    user.SmsTo = v
}
```

Read-Modify-Write-Muster: bestehendes User-Objekt laden, nur das explizit gesendete Feld ueberschreiben, Rest unveraendert speichern. Leerer String (`""`) ist erlaubt (Feld loeschen).

### Step 4: Frontend-Eingabefeld (`frontend/src/routes/account/+page.svelte`, ~15 LoC)

**Neuer Svelte-5-State** (nach dem `mailTo`-State):

```typescript
let smsTo = $state(data.profile?.sms_to ?? '');
```

**Markup-Block** (direkt nach dem `mail_to`-Input, in der Kanaele-Card):

```html
<label class="block text-sm font-medium text-gray-700">Handynummer (SMS)</label>
<input
  type="tel"
  bind:value={smsTo}
  placeholder="+49XXXXXXXXXX"
  class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
/>
<p class="mt-1 text-xs text-gray-500">Internationales Format, z.B. +49151XXXXXXXX</p>
```

**Erweiterung der `save()`-Funktion** — `sms_to` wird immer mitgesendet (auch als leerer String, um Loeschen zu ermoeglichen):

```typescript
await api.put('/api/auth/profile', {
    mail_to: mailTo,
    sms_to: smsTo,
    // ... weitere bestehende Felder ...
});
```

### Step 5: Test ergaenzen (`internal/handler/profile_test.go`, ~15 LoC)

Test-Case fuer `sms_to`-Roundtrip: PUT mit `sms_to: "+49151XXXXXXXX"` → GET → Response enthaelt `sms_to: "+49151XXXXXXXX"`. Identisches Muster wie bestehende `mail_to`-Tests.

### Step 6: Trip-Report-Kanal-UI (`frontend/src/lib/components/edit/EditReportConfigSection.svelte`, ~15 LoC)

- Profile-Interface: `sms_phone?: string` → `sms_to?: string`
- `availableChannels.sms`: `!!profile?.sms_phone` → `!!profile?.sms_to`
- SMS-Checkbox-Block nach dem Telegram-Block ergaenzen (analog E-Mail-Block):

```html
<!-- SMS -->
<div class="text-sm">
  <span data-testid="channel-sms" class="inline-flex items-center gap-2">
    <Checkbox
      checked={send_sms}
      disabled={!availableChannels.sms}
      onchange={(e) => { send_sms = (e.target as HTMLInputElement).checked; }}
    >SMS{profile?.sms_to ? ` (${profile.sms_to})` : ''}</Checkbox>
  </span>
</div>
{#if !availableChannels.sms}
  <div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
    Handynummer fehlt — <a href="/account" ...>im Account einrichten</a>
  </div>
{/if}
```

### Step 7: Compare-Wizard State (`frontend/src/lib/components/compare/compareWizardState.svelte.ts`, ~10 LoC)

`sendSms = $state(false)` ergaenzen, `hasActiveChannel()` und `toCompareConfig()` um `send_sms: this.sendSms` erweitern.

### Step 8: Compare Step 5 + CompareTabs (`Step5Versand.svelte` + `CompareTabs.svelte`, ~15 LoC)

- `CompareTabs.svelte`: `userProfile`-Typdefinition um `sms_to?: string` erweitern, `setContext('compare-wizard-profile', {..., sms_to: userProfile.sms_to})`
- `Step5Versand.svelte`: Profil-Context-Typ um `sms_to?: string` erweitern, `ChannelToggle` fuer SMS ergaenzen analog Telegram, `allChannelsOff`-Check um `sendSms` erweitern

## Expected Behavior

- **Input:** Nutzer traegt eine Handynummer im internationalen Format (`+49151XXXXXXXX`) in das Profilfeld ein und klickt "Speichern". Leer lassen ist erlaubt.
- **Output:** `PUT /api/auth/profile` schreibt den Wert nach `data/users/{id}/user.json` als `"sms_to"`. Folgeaufruf `GET /api/auth/profile` gibt `sms_to` zurueck; Eingabefeld zeigt den gespeicherten Wert.
- **Side effects:** `SMSOutput` im Python-Backend liest `user.SmsTo` beim naechsten `channel="sms"`-Aufruf — nach dem Speichern wird die eingetragene Nummer fuer den Versand verwendet.

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| `sms_to` fehlt im PUT-Body (aeltere Clients) | Feld bleibt unveraendert (Read-Modify-Write im Handler) |
| `sms_to: ""` im PUT-Body | Feld wird auf leer gesetzt (Loeschen gewuenscht) |
| Bestehende `user.json` ohne `sms_to`-Feld | Wird als `""` geladen (Go `omitempty`, kein Fehler) |
| `channel="sms"` ohne gespeicherte Nummer | `SMSOutput` schlaegt mit konfiguriertem Fehler fehl (Verhalten von #608, ausserhalb dieses Scopes) |

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer oeffnet die Account-Seite (`/account`) / When die Seite geladen wird / Then ist ein Eingabefeld fuer die Handynummer mit `placeholder="+49XXXXXXXXXX"` sichtbar und zeigt den bisher gespeicherten Wert an (oder ist leer wenn noch keine Nummer hinterlegt ist)
  - Test: Playwright gegen Staging — Account-Seite laden, Feld mit data-testid oder label "Handynummer" finden, Wert pruefen

- **AC-2:** Given ein eingeloggter Nutzer hat `+49151TESTXXXX` ins Handynummer-Feld eingetragen / When er "Speichern" klickt / Then antwortet `PUT /api/auth/profile` mit HTTP 200 und `GET /api/auth/profile` liefert anschliessend `sms_to: "+49151TESTXXXX"` in der JSON-Response
  - Test: Go-Integrationstest (profile_test.go) — PUT mit `sms_to` senden, GET ausfuehren, Wert in Response vergleichen

- **AC-3:** Given ein Nutzer speichert das Profil ohne eine Handynummer einzutragen (Feld leer) / When `PUT /api/auth/profile` abgesendet wird / Then antwortet das Backend mit HTTP 200 und der Nutzer erhaelt keine Fehlermeldung — leeres Feld ist kein Pflichtfeld
  - Test: Go-Integrationstest — PUT mit `sms_to: ""` senden, HTTP-Status 200 pruefen

- **AC-4:** Given eine bestehende `user.json`-Datei ohne `sms_to`-Feld (vor diesem Feature angelegt) / When `GET /api/auth/profile` aufgerufen wird / Then liefert die Response valides JSON ohne Fehler, `sms_to` fehlt oder ist leer, und alle anderen Profilfelder sind unveraendert vorhanden
  - Test: Go-Unittest — User-Struct aus JSON ohne `sms_to` laden, auf leeren String pruefen, andere Felder intakt

- **AC-5:** Given ein Nutzer hat eine Handynummer im Profil gespeichert / When er die Report-Konfiguration eines Trips oeffnet (Trip-Report-Editor, Bereich "Kanaele") / Then ist eine SMS-Checkbox sichtbar und aktivierbar; ohne gespeicherte Nummer ist die Checkbox deaktiviert und ein Hinweis-Link zum Account erscheint
  - Test: Playwright gegen Staging — Trip-Report-Editor laden, data-testid="channel-sms" pruefen

- **AC-6:** Given ein Nutzer hat eine Handynummer im Profil gespeichert / When er im Vergleichs-Wizard Schritt 5 (Versand) landet / Then ist ein SMS-Toggle sichtbar — analog zu E-Mail und Telegram; ohne gespeicherte Nummer ist der Toggle deaktiviert
  - Test: Playwright gegen Staging — Vergleichs-Wizard bis Step 5 navigieren, SMS-Toggle (data-testid="compare-step5-channel-sms") pruefen

## Known Limitations

- Keine clientseitige Format-Validierung des Telefonnummern-Formats: Der `type="tel"`-Input des Browsers gibt kein einheitliches Feedback. Serverseitige Validierung ist ebenfalls nicht vorgesehen (kein Pflichtfeld, kein Regex-Check) — fehlerhaft eingetragene Nummern fuehren erst beim SMS-Versand zu einem Fehler.
- Das Feld traegt keinen Badge oder Verbindungstest in der Kanalubersicht — im Gegensatz zu `mail_to`. Das entspricht dem Scope dieses Issues; ein Verbindungstest fuer SMS waere ein eigenes Feature.

## Changelog

- 2026-06-05: Initial spec — basierend auf Analyse zu Issue #609; Downstream-Abhaenger: SMSOutput aus Issue #608
- 2026-06-05: v1.1 — Scope erweitert auf Trip-Report-Editor (AC-5) und Vergleichs-Wizard Step 5 (AC-6) nach PO-Feedback; Feldname-Mismatch `sms_phone`→`sms_to` in EditReportConfigSection dokumentiert
- 2026-06-05: IMPLEMENTED — Alle ACs erfuellt; docs/reference/api_contract.md aktualisiert mit `sms_to`-Feld in User-Model und Profile-Endpoints
