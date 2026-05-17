---
entity_id: issue_202_region_feld
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
issues: [202]
tags: [trip, region, go, typescript, sveltekit, frontend, wizard, trip-detail, issue-202]
---

# Issue 202 — Trip: Region-Feld einführen

## Approval

- [ ] Approved

## Purpose

Erweitert das Trip-Datenmodell um ein optionales `region`-Feld (Freitext, max. 50 Zeichen), das die geografische Region eines Trips benennt (z.B. „Korsika", „Mallorca"). Das Feld wird in Wizard Step 1 erfasst, im TripHero unterhalb des Trip-Namens angezeigt wenn gesetzt, und durch das bestehende Read-Modify-Write-Muster des Update-Handlers verlustfrei durchgereicht — Trips ohne Region bleiben unverändert.

## Source

- **EDIT:** `internal/model/trip.go` — `Region string \`json:"region,omitempty"\`` nach `Activity`-Feld im Trip-Struct
- **EDIT:** `internal/handler/trip.go` — `Region *string \`json:"region,omitempty"\`` im `tripUpdateRequest`-DTO + Merge-Zeile im UpdateTripHandler
- **EDIT:** `frontend/src/lib/types.ts` — `region?: string` im `Trip`-Interface nach `activity`
- **EDIT:** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` — `region = $state('')` + Trim-Guard + Zuweisung in `toTripPayload()`
- **EDIT:** `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` — optionales „Region"-Eingabefeld nach Shortcode-Feld (maxlength=50)
- **EDIT:** `frontend/src/lib/components/trip-detail/TripHero.svelte` — bedingter Region-Absatz `{#if trip.region}` zwischen H1-Titel und Zeitraum-Zeile
- **EDIT:** `frontend/e2e/global.setup.ts` — `region: "Korsika"` zum E2E-Seed-Trip hinzufügen
- **EDIT:** `frontend/e2e/trip-detail-hero.spec.ts` — 2 neue Testfälle: Region sichtbar wenn gesetzt, Region nicht im DOM wenn abwesend

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip` Go-Struct (`internal/model/trip.go`) | intern | Bekommt neues `Region`-Feld; identisches `omitempty`-Muster wie `Shortcode` und `Activity` |
| `tripUpdateRequest` (`internal/handler/trip.go`) | intern | DTO-Pointer `*string` für optionales Patch-Feld; Merge-Zeile schreibt nur wenn nicht nil |
| `UpdateTripHandler` (`internal/handler/trip.go`) | intern | Bestehender Read-Modify-Write-Handler; lässt `existing.Region` unverändert wenn `req.Region == nil` |
| `Trip`-Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typisierung; `region?: string` nach `activity`-Feld |
| `WizardState` (`wizardState.svelte.ts`) | intern | Svelte-5-State-Klasse; `region`-State und `toTripPayload()` analog zum `shortcode`-Muster |
| `Step1Profile.svelte` | intern | Wizard-Formular; erhält optional beschriftetes Input-Feld mit maxlength-Attribut |
| `TripHero.svelte` | intern | Overview-Tab-Komponente; rendert `{#if trip.region}` zwischen Titel und Datumsbereich |
| `global.setup.ts` | intern | Playwright-E2E-Seed; muss `region` im Test-Trip setzen damit Hero-Spec es sehen kann |
| `trip-detail-hero.spec.ts` | intern | Bestehende Playwright-Spec; bekommt 2 neue ACs für Region-Anzeige und Region-Abwesenheit |
| `internal/store/store.go` | intern | Keine Änderung nötig — Full-JSON-Replace; neues Struct-Feld wird automatisch persistiert |

## Implementation Details

### §1 Go-Struct `internal/model/trip.go`

Neues Feld nach `Activity` (Zeile ~77):

```go
Shortcode string `json:"shortcode,omitempty"`
Activity  string `json:"activity,omitempty"`
Region    string `json:"region,omitempty"`
```

Kein separater Typ, kein Enum — reiner `string`. `omitempty` stellt sicher, dass Trips ohne Region kein `"region":""` im JSON bekommen.

### §2 Update-Handler `internal/handler/trip.go`

Im `tripUpdateRequest`-DTO neues Pointer-Feld ergänzen (exakt wie `AvalancheRegions`-Muster, aber skalarer Typ):

```go
type tripUpdateRequest struct {
    // ... bestehende Felder
    Region *string `json:"region,omitempty"`
}
```

Im Handler-Body nach den anderen Merge-Zeilen:

```go
if req.Region != nil {
    existing.Region = *req.Region
}
```

Wenn `req.Region == nil` (Feld im PATCH-Body nicht enthalten), bleibt `existing.Region` unverändert — Bestandsdaten-Schutz ohne explizite Migration.

### §3 TypeScript `frontend/src/lib/types.ts`

Im `Trip`-Interface nach der `activity`-Zeile:

```typescript
export interface Trip {
    id: string;
    name: string;
    shortcode?: string;
    activity?: ActivityType;
    region?: string;           // NEU
    stages: Stage[];
    // ... restliche Felder unverändert
}
```

### §4 WizardState `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`

Neue State-Property in der Klasse (nach `shortcode`):

```typescript
shortcode = $state('');
region    = $state('');
```

In `toTripPayload()` nach der shortcode-Trim-Guard-Zuweisung:

```typescript
const sc = this.shortcode.trim();
if (sc) trip.shortcode = sc;

const reg = this.region.trim();
if (reg) trip.region = reg;
```

Wenn `region` leer oder nur Whitespace, wird das Feld nicht an die API gesendet — `existing.Region` im Go-Handler bleibt dadurch unverändert (Read-Modify-Write greift).

Beim Laden eines bestehenden Trips in den Wizard (Edit-Pfad, falls vorhanden) muss `state.region = trip.region ?? ''` gesetzt werden — analog zu `shortcode`. Betrifft nur den Wizard-Edit-Pfad, nicht `TripEditView.svelte`.

### §5 Step1Profile `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`

Neues Formular-Feld nach dem Shortcode-Block, vor dem Startdatum-Feld:

```svelte
<label>
    <span>Region <span class="text-[var(--g-ink-faint)]">(optional)</span></span>
    <input
        type="text"
        data-testid="trip-wizard-step1-region"
        maxlength="50"
        placeholder="z.B. Korsika, Mallorca"
        bind:value={state.region}
    />
</label>
```

Stilklassen analog zu den anderen Eingabefeldern im Step1-Formular. Kein Pflichtfeld, kein Validator, kein Live-Counter für verbleibende Zeichen (maxlength-Browser-Enforcement reicht).

### §6 TripHero `frontend/src/lib/components/trip-detail/TripHero.svelte`

Zwischen `<h1 data-testid="trip-hero-title">` und dem `{#if dateRange}`-Block:

```svelte
<h1 data-testid="trip-hero-title" class="trip-hero-title">{trip.name}</h1>
{#if trip.region}
    <p data-testid="trip-hero-region" class="trip-hero-region">{trip.region}</p>
{/if}
{#if dateRange}
    <p data-testid="trip-hero-date-range" class="trip-hero-date-range">{dateRange}</p>
{/if}
```

CSS-Klasse `.trip-hero-region` im `<style>`-Block nach `.trip-hero-title`:

```css
.trip-hero-region {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--g-ink-faint, #6b7280);
    margin-top: -0.25rem;
}
```

Der Absatz wird nur gerendert wenn `trip.region` truthy ist — leerer String und `undefined` führen zu keinem DOM-Element.

### §7 E2E-Seed `frontend/e2e/global.setup.ts`

Im `page.request.post('/api/trips', { data: { ... } })`-Objekt `region: "Korsika"` ergänzen:

```typescript
data: {
    id: TRIP_ID,
    name: 'E2E Cockpit Test Trip',
    region: 'Korsika',           // NEU
    stages: [...],
    // ...
}
```

### §8 E2E-Spec `frontend/e2e/trip-detail-hero.spec.ts`

Zwei neue Testfälle als separate `test()`-Blöcke oder `describe`-Erweiterung:

1. **Region sichtbar:** Navigiert zu `/trips/e2e-cockpit-test`, wechselt auf Overview-Tab, prüft `data-testid="trip-hero-region"` auf `innerText === "Korsika"`.
2. **Region absent:** Erstellt einen temporären Trip ohne `region`-Feld via API, navigiert, prüft dass kein Element mit `data-testid="trip-hero-region"` im DOM vorhanden ist, löscht den Trip wieder.

### §9 TestID-Inventar

| TestID | Element | Neu/Bestehend | Zweck |
|--------|---------|---------------|-------|
| `trip-hero-region` | `<p>` | NEU | Region-Anzeige im Hero; nur im DOM wenn `trip.region` truthy |
| `trip-wizard-step1-region` | `<input type="text">` | NEU | Region-Eingabe in Wizard Step 1 |
| `trip-hero` | `<div>` Wrapper | bestehend | Hero-Container (unverändert) |
| `trip-hero-title` | `<h1>` | bestehend | Trip-Name (unverändert) |
| `trip-hero-date-range` | `<p>` | bestehend | Zeitraum-Zeile (unverändert) |

### §10 Datei-Liste und LoC-Schätzung

| Art | Datei | Änderung | LoC |
|-----|-------|----------|-----|
| EDIT | `internal/model/trip.go` | 1 Zeile Struct-Feld | +1 |
| EDIT | `internal/handler/trip.go` | 1 DTO-Feld + 3 Merge-Zeilen | +4 |
| EDIT | `frontend/src/lib/types.ts` | 1 Zeile Interface-Feld | +1 |
| EDIT | `wizardState.svelte.ts` | 1 State-Property + 2 Payload-Zeilen | +3 |
| EDIT | `Step1Profile.svelte` | ~7 Zeilen Label+Input-Block | +7 |
| EDIT | `TripHero.svelte` | 3 Template-Zeilen + 5 CSS-Zeilen | +8 |
| EDIT | `global.setup.ts` | 1 Seed-Zeile | +1 |
| EDIT | `trip-detail-hero.spec.ts` | 2 neue Testfälle (~15 Zeilen) | +15 |
| **Summe** | | | **~40 LoC** |

Kein LoC-Override nötig (40 LoC << 250-Limit).

## Expected Behavior

- **Input:** Trip-JSON mit optionalem `"region": "Korsika"` aus `data/users/<user>/trips/<id>.json`; PATCH-Body mit `"region": "..."` oder ohne `region`-Feld.
- **Output:**
  - Go-Backend: `Trip.Region` wird in JSON mit `omitempty` serialisiert — kein `"region":""` für leere Trips.
  - PATCH ohne `region`-Feld: `existing.Region` bleibt erhalten.
  - PATCH mit `"region": ""` (leerer String): `existing.Region` wird auf `""` gesetzt (cleared).
  - TripHero: `data-testid="trip-hero-region"` ist nur im DOM wenn `trip.region` truthy.
  - Wizard Step 1: Region-Input ist sichtbar, optional, begrenzt auf 50 Zeichen.
- **Side effects:** Keine Migration nötig — bestehende Trips ohne `region`-Feld im JSON werden bei Load normal eingelesen (`Region` bleibt Go-Zero-Value `""`), `omitempty` verhindert dass das leere Feld zurückgeschrieben wird.

## Acceptance Criteria

- **AC-1:** Given ein Trip-JSON mit `"region": "Korsika"` / When der Go-Handler den Trip via `GET /api/trips/{id}` ausliefert / Then enthält die JSON-Antwort `"region": "Korsika"` als String-Feld im Trip-Objekt.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip ohne `region`-Feld im JSON / When der Go-Handler den Trip via `GET /api/trips/{id}` ausliefert / Then fehlt das `region`-Feld in der JSON-Antwort vollständig (kein `"region": ""`).
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit `region: "Korsika"` / When `PATCH /api/trips/{id}` mit einem Body gesendet wird, der das `region`-Feld nicht enthält / Then bleibt `trip.region` nach dem PATCH unverändert `"Korsika"` (Read-Modify-Write).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit gesetztem `region`-Wert / When die Trip-Detail-Seite im Overview-Tab geöffnet wird / Then ist `data-testid="trip-hero-region"` sichtbar und zeigt den Region-Wert als Text an — positioniert unterhalb von `data-testid="trip-hero-title"` und oberhalb von `data-testid="trip-hero-date-range"`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip ohne `region`-Feld (undefined oder leerer String) / When die Trip-Detail-Seite im Overview-Tab geöffnet wird / Then existiert kein Element mit `data-testid="trip-hero-region"` im DOM — kein leerer Absatz, kein Leerraum.
  - Test: (populated after /tdd-red)

- **AC-6:** Given der Benutzer öffnet Wizard Step 1 / When das Formular gerendert ist / Then ist das Region-Eingabefeld mit `data-testid="trip-wizard-step1-region"` sichtbar, das Label enthält den Text „(optional)", und das Feld ist nicht als Pflichtfeld markiert — der Wizard-Weiter-Button bleibt ohne Region-Eingabe aktiv.
  - Test: (populated after /tdd-red)

- **AC-7:** Given der Region-Input in Wizard Step 1 / When der Benutzer mehr als 50 Zeichen eingibt / Then verhindert das `maxlength="50"`-Attribut die Eingabe des 51. Zeichens — der Browser enforced das Limit ohne JavaScript-Validator.
  - Test: (populated after /tdd-red)

- **AC-8:** Given der Benutzer gibt „Mallorca" in das Region-Feld ein und schließt den Wizard ab / When der Trip gespeichert wird (POST `/api/trips`) / Then enthält der API-Request `"region": "Mallorca"` und der anschließend abgerufene Trip gibt `region: "Mallorca"` zurück.
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein bestehender Trip mit `region: "Korsika"` / When der Trip im Wizard geöffnet und Step 1 geladen wird / Then ist das Region-Eingabefeld mit dem Wert „Korsika" vorbelegt.
  - Test: (populated after /tdd-red)

- **AC-10:** Given alle 9 produktiv existierenden Trips ohne `region`-Feld / When jeder Trip über die API geladen wird / Then funktionieren alle bestehenden Felder (name, stages, report_config etc.) unverändert — keine Regression durch das neue Feld.
  - Test: (populated after /tdd-red)

## Known Limitations

- **TripEditView.svelte ausgenommen:** Das direkte Edit-Formular (nicht Wizard) bekommt kein Region-Eingabefeld. Benutzer können Region nur über den Wizard setzen oder über direkten API-PATCH. Das ist eine bewusste Einschränkung dieses Issues — Edit-View-Erweiterung als Folge-Issue falls nötig.
- **Keine Trip-Listen-Spalte:** Region erscheint nicht in der Trip-Übersichtsliste — deferred per Issue-Spezifikation.
- **Kein Autocomplete, kein Reverse-Geocoding:** Das Feld ist reiner Freitext ohne Vorschläge. Nutzereingabe ist kanonisch; keine Normalisierung.
- **PATCH mit leerem String cleared das Feld:** `PATCH { "region": "" }` setzt `existing.Region = ""`. Das ist korrektes Verhalten, aber `omitempty` sorgt dafür dass der Wert danach nicht im GET zurückkommt. Wizard sendet bei leerem Trim-Guard kein `region`-Feld — kein versehentliches Clearing.

## Changelog

- 2026-05-17: Initial spec — Issue #202 (Region-Feld). 8 Dateien (alle EDIT), ~40 LoC. Go-Struct + DTO + TypeScript-Interface + Wizard-State + Step1-Input + TripHero-Conditional + E2E-Seed + E2E-Spec. 10 Acceptance Criteria im AC-N-Format. TestID-Inventar (2 neue IDs).
