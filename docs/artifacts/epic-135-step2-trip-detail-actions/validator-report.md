# External Validator Report

**Spec:** docs/specs/modules/epic_135_step2_trip_detail_actions.md
**Datum:** 2026-05-12T11:14:00Z
**Server:** https://staging.gregor20.henemm.com
**Trip-IDs:**
- `validator-test-1` (kein Shortcode, Stage-Datum live mutiert)
- `e16976b5` (Shortcode `valnoth231330`)

## Checklist

| #  | Expected Behavior (verkürzt) | Beweis | Verdict |
|----|------------------------------|--------|---------|
| 1  | Kein Flag + Stage heute → `'active'` / "Aktiv" | Server: `paused_at=undefined archived_at=undefined stage=2026-05-12` → Badge **"Aktiv"** (Screenshot `v2_ac1.png`) | PASS |
| 2  | `archived_at` UND `paused_at` gesetzt → `'archived'` / "Archiviert" | Server: beide Timestamps gesetzt → Badge **"Archiviert"** (Screenshot `v2_ac2.png`) | PASS |
| 3  | `paused_at` gesetzt + Stage heute → `'paused'` / "Pausiert" | Server: nur paused_at + Stage 2026-05-12 → Badge **"Pausiert"** (Screenshot `v2_ac3.png`) | PASS |
| 4  | Keine Flags + Stage nicht heute → `'planned'` / "Geplant" | Server: keine Flags + Stage 2026-07-01 → Badge **"Geplant"** (Screenshot `v2_ac4.png`) | PASS |
| 5  | `PATCH /state {"paused":true}` → 200 + `paused_at` befüllt | Response: HTTP 200, `paused_at:"2026-05-12T11:08:20.014008314Z"` | PASS |
| 6  | `PATCH /state {"paused":false}` → 200, kein `paused_at` mehr | Response: HTTP 200, `paused_at` fehlt im JSON (omitempty) | PASS |
| 7  | Idempotenter zweiter `paused:true` → 200, Trip bleibt pausiert (neuer Timestamp) | Erst-Timestamp `11:08:20.014…`, zweit-Timestamp `11:08:21.045…`, HTTP 200 | PASS |
| 8  | `PATCH /api/trips/<nichtexistent>/state` → 404 | Response: `{"error":"not_found"}`, HTTP 404 | PASS |
| 9  | `PUT /api/trips/{id}` ohne `paused_at`-Feld lässt Feld unverändert | Pre: `paused_at:"…21.045…"` → PUT-Body ohne `paused_at` → Post: identischer `paused_at:"…21.045…"` | PASS |
| 10 | Shortcode hat Vorrang im Breadcrumb (`KHW 403`-Pattern) | Trip `e16976b5` mit Shortcode `valnoth231330` → `breadcrumb-current` rendert exakt `valnoth231330` | PASS |
| 11 | Ohne Shortcode → Trip-Name als Fallback | Trip `validator-test-1` (kein Shortcode) → `breadcrumb-current` rendert `Validator Test` | PASS |
| 12 | Active-Trip: Badge `Aktiv` + Pill-Tone `success` | Trip ohne Flags + Stage heute → Badge-DOM: `<span data-slot="pill" data-tone="success" data-testid="trip-detail-status-badge">Aktiv</span>` | PASS |
| 13 | Click Pause → PATCH `{"paused":true}` → Badge "Pausiert" + Button-Label "Fortsetzen", ohne Reload | Captured Request: `PATCH /api/trips/validator-test-1/state {"paused":true}`; Badge nach 1.5s: `Pausiert`; Pause-Button-Label: `Fortsetzen` | PASS |
| 14 | Click Archive öffnet Dialog ohne PATCH | Nach Click: `trip-detail-archive-confirm-dialog` sichtbar; captured PATCH-Requests: 0 | PASS |
| 15 | Click Cancel schließt Dialog, Status unverändert | Dialog nach Cancel: nicht sichtbar; Badge unverändert `Pausiert`; PATCH-Requests: 0 | PASS |
| 16 | Click Confirm → PATCH `{"archived":true}` → Badge "Archiviert" + Pause-Button raus aus DOM | Captured Request: `PATCH … {"archived":true}`; Badge: `Archiviert`; `trip-detail-action-pause` Count: 0 | PASS |
| 17 | Archivierter Trip → Archive-Button-Label `Reaktivieren`, kein Pause-Button | Archive-Label: `Reaktivieren`; `trip-detail-action-pause` Count: 0 | PASS |
| 18 | Pausierter Trip → Pause-Label `Fortsetzen`, Archive-Button mit `Archivieren` sichtbar | Pause-Label: `Fortsetzen`; Archive-Label: `Archivieren`; beide visible: true | PASS |
| 19 | Nach Page-Reload bleibt pausierter Zustand erhalten | Nach `page.reload()`: Badge `Pausiert`, Pause-Label `Fortsetzen` | PASS |
| 20 | TabList weiterhin sichtbar mit 6 Tabs nach allen Aktionen | `trip-detail-tab-list` visible: true; `role=tab` count: 6 (overview, stages, weather, briefings, alerts, preview) | PASS |

## Findings

Keine. Alle 20 Acceptance Criteria sind durch echte Requests gegen Staging-API + Browser-Inspektion mit Playwright belegt.

## Methodik (für Reproduzierbarkeit)

1. **Backend (AC-5 bis AC-9):** Direkte `curl`-Requests mit dem mitgelieferten `gz_session`-Cookie gegen `https://staging.gregor20.henemm.com/api/trips/validator-test-1/state` und `/api/trips/validator-test-1`.
2. **Frontend (AC-10 bis AC-20):** Headless-Chromium via Playwright, `addCookies` mit `gz_session`. Navigation auf `/trips/<id>#overview`, danach Element-Lookups via `getByTestId` und Click-Aktionen mit Request-Interception.
3. **Status-Hierarchie (AC-1 bis AC-4):** Pro AC ein frischer Browser-Context, weil SvelteKit/CDN-Caching beim Wiederverwenden eines Contexts veraltete Daten lieferte (erkennbar im ersten Lauf: 0 API-Calls beim zweiten `goto`). Mit Cache-Busting-Query-Param `?_cb=<timestamp>` + frischen Contexts wurden alle vier Zustände korrekt gerendert.
4. **Trip-State-Mutation:** Über `PATCH /api/trips/{id}/state` für Flags, über `PUT /api/trips/{id}` für Stage-Datum-Manipulation. Nach jedem Test wurde der Trip in einen sauberen Zustand zurückgesetzt (paused: false, archived: false, Stage-Datum 2026-05-04).

## Beweis-Artefakte

Screenshots unter `/tmp/validator-screenshots/`:
- `ac10_shortcode.png` — Breadcrumb mit `valnoth231330`
- `ac11_noshortcode.png` — Breadcrumb mit Trip-Namen
- `ac12_active_badge.png` — Badge "Aktiv" mit Tone success
- `ac13_after_pause.png` — Badge "Pausiert", Pause-Label "Fortsetzen"
- `ac14_archive_dialog.png` — Confirm-Dialog offen
- `ac15_after_cancel.png` — Dialog geschlossen, Status unverändert
- `ac16_after_confirm.png` — Badge "Archiviert", kein Pause-Button
- `ac19_after_reload.png` — Persistenz nach Reload
- `ac20_tablist.png` — Tab-Navigation 6 Tabs sichtbar
- `v2_ac1.png` bis `v2_ac4.png` — Status-Hierarchie-Beweise

Voller Validation-Log: `/tmp/validator-screenshots/validation-output.txt`

## Verdict: VERIFIED

### Begründung

Alle 20 in der Spec aufgeführten Acceptance Criteria liefern unter realen Bedingungen gegen die Staging-Instanz das in der Spec beschriebene Verhalten — nachgewiesen durch HTTP-Statuscodes, Response-Bodies und gerenderte DOM-Inhalte inkl. Screenshot-Evidenz.

Insbesondere widerlegt die Validierung mehrere Angriffspunkte:
- **Status-Hierarchie** (`archived > paused > date-based`) hält stand: Trip mit beiden Flags zeigt "Archiviert", Trip mit nur `paused_at` + Stage heute zeigt "Pausiert" (nicht "Aktiv").
- **PUT-Isolation** (AC-9) hält stand: `PUT /api/trips/{id}` ohne `paused_at` im Body lässt das Feld im Store unverändert — kein versehentliches Reset durch den bestehenden Update-Handler.
- **DOM-Sichtbarkeitsregel** (AC-16/AC-17) hält stand: Pause-Button ist bei archiviertem Trip nicht nur disabled, sondern komplett aus dem DOM entfernt (Count: 0).
- **Reaktivität ohne Reload** (AC-13) hält stand: Nach Pause-Click wechseln Badge und Button-Label innerhalb von 1.5s — keine Page-Navigation.
- **Persistenz** (AC-19) hält stand: Nach Browser-Reload werden die Flags korrekt aus dem Backend geladen und gerendert.

Keine Verhaltenslücke, kein Spec-Drift, kein Screenshot-Diff fehlt.
