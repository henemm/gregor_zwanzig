---
entity_id: issue_189_preview_tab_integration
type: module
created: 2026-05-16
updated: 2026-05-17
status: approved
version: "1.0"
tags: [frontend, preview, trip-detail, epic-140]
parent_spec: docs/specs/modules/epic_140_output_vorschau.md
---

# Issue #189 — Vorschau-Integration in Trip-Übersicht

## Approval

- [x] Approved (User, 2026-05-17 — Workflow-Retrofit: Code/Tests bereits committed, Phase 7 Validate folgt)

## Purpose

Frontend-Komponenten und Tab-Integration für die in Epic #140 (Master-Spec) vorgesehene Output-Vorschau. Email wird via `<iframe srcdoc>` direkt aus dem Backend-Endpoint gerendert, SMS in einem iOS-Phone-Frame mit Zeichenzähler. Damit ist die Vorschau identisch zur tatsächlich versendeten Mail bzw. SMS — eine Render-Quelle, kein Drift.

## Source

> **Schicht-Hinweis:** Diese Spec betrifft ausschließlich das **Frontend (SvelteKit)**. Die Backend-Endpoints `/api/preview/{trip_id}/email|sms` existieren bereits (`api/routers/preview.py`, `src/services/preview_service.py`, committed 2026-05-11) und werden in diesem Workflow nicht angefasst.

### Neu

- **File:** `frontend/src/lib/components/preview/EmailIframe.svelte` (NEU)
  - **Identifier:** `<EmailIframe tripId type date? />`
- **File:** `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` (NEU)
  - **Identifier:** `<SmsPhoneFrame tripId type date? />`
- **File:** `frontend/src/lib/components/preview/previewHelpers.ts` (NEU)
  - **Identifier:** `buildPreviewUrl`, `defaultReportType`, `charCountStatus`
- **File:** `frontend/src/lib/components/preview/index.ts` (NEU) — Barrel-Export

### Patch

- **File:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
  - **Identifier:** Tab-Content für `value === 'preview'` ersetzt Placeholder (Zeile 38, 89)

### Bestand (bleibt)

- `api/routers/preview.py` — Backend-Endpoints (unverändert)
- `src/services/preview_service.py` — Render-Orchestrierung (unverändert)
- `frontend/src/lib/components/email-preview/` — `headerStats.ts` + `EmailPreviewHeader.svelte` aus altem #183 bleiben für etwaige Mini-Header-Verwendung; **nicht** Teil dieser Spec

### Patch (Go-API-Proxy — Hot-Fix für Master-Spec-Lücke)

- **File:** `internal/handler/preview_proxy.go` (NEU) — `PreviewProxyHandler(pythonURL, channel)`
- **File:** `internal/handler/preview_proxy_test.go` (NEU) — 6 Tests
- **File:** `cmd/server/main.go` (Patch) — 2 Route-Registrierungen

Grund: Backend-Endpoint in `api/routers/preview.py` ist seit 11.05. committed, aber der Go-API-Proxy leitete `/api/preview/{trip_id}/email|sms` nicht an Python:8001 weiter — Validator gegen Staging gab HTTP 404. Pattern analog zu `LoadedTripProxyHandler`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/preview/{trip_id}/email` | bestehender Endpoint | Liefert HTML-String der Vorschau |
| `GET /api/preview/{trip_id}/sms` | bestehender Endpoint | Liefert `{subject, token_line, char_count}` |
| `TripTabs.svelte` | bestehende Komponente | Tab-Slot `preview` (Zeile 29) wird befüllt |
| `bits-ui` Tabs | externe Lib | Bereits in TripTabs verwendet |
| Design-System Tokens (`tokens.css`) | bestehend | `--g-accent`, `--g-paper`, `--g-ink`, `--g-r-3`, `--g-shadow-1` |

## Implementation Details

### `previewHelpers.ts` (Pure Functions)

```ts
export type ReportType = 'morning' | 'evening';

export function buildPreviewUrl(
  channel: 'email' | 'sms',
  tripId: string,
  type: ReportType,
  date?: string,
): string {
  const qs = new URLSearchParams({ type });
  if (date) qs.set('date', date);
  return `/api/preview/${encodeURIComponent(tripId)}/${channel}?${qs.toString()}`;
}

export function defaultReportType(now: Date = new Date()): ReportType {
  // Vor 14 Uhr lokal → Morgen-Briefing, sonst Abend-Briefing
  return now.getHours() < 14 ? 'morning' : 'evening';
}

export type CharCountStatus = 'ok' | 'warn' | 'over';

export function charCountStatus(n: number, limit = 160): CharCountStatus {
  if (n > limit) return 'over';
  if (n > limit - 16) return 'warn'; // letzte 10 % Puffer
  return 'ok';
}
```

### `EmailIframe.svelte`

- Props: `tripId: string`, `type: ReportType`, `date?: string`
- `$effect` lädt `buildPreviewUrl('email', ...)` per `fetch`, schreibt `html`-Text in `<iframe srcdoc>`
- `sandbox="allow-same-origin"` (kein JS im iframe nötig)
- States: `loading`, `error`, `ready` — Loading-Indikator + Fehlermeldung mit HTTP-Status-Code
- Höhe: `min-height: 600px`, `width: 100 %`
- iframe-Wrapper nutzt `--g-paper` als Hintergrund, `--g-r-3` als Border-Radius, `--g-shadow-1`

### `SmsPhoneFrame.svelte`

- Props: `tripId: string`, `type: ReportType`, `date?: string`
- `$effect` lädt `buildPreviewUrl('sms', ...)`, parst JSON `{subject, token_line, char_count}`
- iOS-Dark-Frame: 320 px breit, schwarzes abgerundetes Rechteck (`border-radius: 36px`, `background: #1a1a18`), oben eine kleine „Notch"-Anmutung (`::before` mit `width: 60px, height: 18px`), darin eine helle Bubble (`background: var(--g-paper)`) mit der `token_line` in JetBrains Mono
- Unterhalb: Zeichenzähler `N/160` mit Status-Farbe aus `charCountStatus()`
- Legende **außerhalb** des Frames (kleine Lesehilfe „Spec-Format SMS — Token-Reihenfolge: …")
- Hinweis-Pill außerhalb wenn `subject` als Stub kommt (siehe Known Limitations)

### Tab-Integration in `TripTabs.svelte`

Innerhalb von `<Tabs.Content value="preview">` ersetzt der Placeholder durch:

```svelte
{#if tab.value === 'preview' && trip}
  <div class="preview-shell">
    <div class="preview-controls">
      <label>
        <input type="radio" bind:group={previewType} value="morning" /> Morgen
      </label>
      <label>
        <input type="radio" bind:group={previewType} value="evening" /> Abend
      </label>
    </div>
    <div class="preview-grid">
      <EmailIframe tripId={trip.id} type={previewType} />
      <SmsPhoneFrame tripId={trip.id} type={previewType} />
    </div>
  </div>
{:else if tab.value === 'overview' && trip}
  ...
```

- `previewType: ReportType = $state(defaultReportType())`
- Layout side-by-side (Memory: Frontend = Desktop-Planungstool, Side-by-Side ist normal)
- Imports oben im `<script>`: `EmailIframe`, `SmsPhoneFrame`, `defaultReportType`, Typ `ReportType`

### Auth

`fetch()` läuft über den Go-Proxy (gleiche Origin), Session-Cookie geht automatisch mit, der Proxy injiziert `user_id` in den Backend-Request. **Frontend hängt keinen `user_id`-Query-Param an.**

## Expected Behavior

- **Input:** Tab „Vorschau" wird im Trip-Detail-View aktiviert.
- **Output:** Email-Vorschau (iframe) + SMS-Vorschau (Phone-Frame) nebeneinander, Morning/Evening-Umschalter darüber. Bei Backend-Fehler klare Meldung im jeweiligen Frame.
- **Side effects:** Keine — Backend-Endpoints lösen Wetter-Fetch + Render aus (Cache-Verhalten unverändert), aber kein Versand, kein Logbuch-Eintrag.

## Acceptance Criteria

- **AC-1:** Given Trip-Detail-Ansicht mit gültigem Trip / When der Tab „Vorschau" aktiv wird / Then werden `EmailIframe` und `SmsPhoneFrame` nebeneinander gerendert, mit `previewType = defaultReportType()` als Initial-Wert.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `<EmailIframe tripId="..." type="morning" />` montiert / When das Backend `GET /api/preview/.../email?type=morning` mit HTTP 200 antwortet / Then steht das gelieferte HTML im `srcdoc` des inneren `<iframe>` (kein leeres iframe, kein Loading-State mehr sichtbar).
  - Test: (populated after /tdd-red)

- **AC-3:** Given `<SmsPhoneFrame tripId="..." type="morning" />` montiert / When das Backend mit JSON `{subject, token_line, char_count}` antwortet / Then zeigt der Phone-Frame die `token_line` in JetBrains Mono und darunter den Zähler `<char_count>/160` mit Status-Farbe.
  - Test: (populated after /tdd-red)

- **AC-4:** Given Vorschau-Tab ist aktiv mit `previewType = 'morning'` / When der User auf das „Abend"-Radio klickt / Then triggern beide Komponenten einen neuen Backend-Fetch mit `type=evening`, alte Inhalte werden ersetzt (kein Mischzustand).
  - Test: (populated after /tdd-red)

- **AC-5:** Given Backend antwortet mit HTTP 404 (kein Stage am Datum), 422 (ungültiger Type) oder 503 (Wetter-Provider down) / When eine der Vorschau-Komponenten lädt / Then wird statt iframe/Token eine sichtbare Fehlermeldung mit HTTP-Status und Server-Detail gerendert, keine leere Fläche.
  - Test: (populated after /tdd-red)

- **AC-6:** Given Pure-Function `charCountStatus(n, limit=160)` / When mit `n = 100, 150, 160, 161` aufgerufen / Then liefert sie `ok, warn, warn, over` in dieser Reihenfolge (Schwellen: ≥161 = over, 145…160 = warn, ≤144 = ok).
  - Test: (populated after /tdd-red)

- **AC-7:** Given Pure-Function `buildPreviewUrl('email', 'gr20', 'morning')` / When ohne Date-Param aufgerufen / Then liefert sie `/api/preview/gr20/email?type=morning` (keine `date`-Query, korrektes URL-Encoding für `trip_id`).
  - Test: (populated after /tdd-red)

- **AC-8:** Given Frontend-Komponenten gerendert in einer Browser-Session / When der Browser die Komponenten mountet / Then nutzen sie Design-System-Tokens (`--g-paper`, `--g-ink`, `--g-accent`, `--g-r-3`, `--g-shadow-1`) statt hartkodierter Farben — Smoke-Check via DOM-Inspector.
  - Test: (populated after /tdd-red)

- **AC-9:** Given laufender Go-API-Proxy / When `GET /api/preview/{trip_id}/email?type=morning` mit gültigem Auth-Cookie aufgerufen wird / Then proxiet Go den Aufruf an Python:8001/api/preview/{trip_id}/email mit `?user_id=…&type=morning` und gibt die Python-Response (HTML-Body, korrekter Content-Type) durch.
  - Test: internal/handler/preview_proxy_test.go (6 Tests, GREEN)

## Known Limitations

- **SMS-Inhalt ist noch Stub:** Das Backend (`preview_service.render_sms_preview`, Zeile 130-143) liefert aktuell den **Email-Subject** als `token_line`, nicht das echte Spec-Format-Token (`KHW_00B: N3 D11 R3.8 …`). Frontend zeigt damit zwar einen plausiblen String, aber kein Format-konformes SMS-Token. **Dieser Workflow ändert das Backend nicht.** Echtes Spec-Token wird in Folge-Workflow #188 nachgereicht. Im Phone-Frame ist daher eine kleine Hinweis-Pill „SMS-Token-Pipeline folgt (#188)" außerhalb des Frames sichtbar, solange der Stub aktiv ist (Erkennung: heuristisch, z. B. Token enthält Leerzeichen mit Großbuchstaben-Wörtern statt nur Tokens).
- **iframe-CSS-Isolation:** Backend-HTML muss alle Styles inline mitliefern. Das Mail-Pipeline tut das ohnehin — keine Anpassung nötig. Aber: Wenn Epic #236 (Mail-Templates ans Design-System) noch nicht umgesetzt ist, sieht die Vorschau das **alte** Mail-Design (das ist korrekt — die echte Mail sieht ja auch noch so aus).
- **Aktivitätsprofil-Signatur:** Profil-basierte visuelle Differenzierung der Mail (Wintersport ≠ Wandern …) ist Bestandteil von Epic #236, nicht dieses Workflows. Frontend reicht den User-Cookie weiter, Mail-HTML kommt wie es kommt.
- **Mobile Layout:** Side-by-Side ist Desktop-first (Memory-Konvention: Frontend = Desktop-Planungstool). Auf schmalen Viewports stapeln die beiden Komponenten in CSS-Grid via `grid-template-columns: 1fr` unterhalb von ~960 px.
- **Wetter-Provider-Call bei jeder Vorschau:** Erste Vorschau triggert echten Wetter-Fetch. Backend-Cache greift, kein neuer Code nötig.

## Changelog

- 2026-05-16: Initial spec — Frontend-Sub-Spec zu Epic #140 / Issue #189, Master-Spec `epic_140_output_vorschau.md`
