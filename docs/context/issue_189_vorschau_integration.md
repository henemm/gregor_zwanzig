---
workflow: issue_189_vorschau_integration
phase: 1-context
issue: 189
epic: 140
created: 2026-05-17
---

# Context: Issue #189 — Vorschau-Integration in Trip-Übersicht

## Request Summary

Tab „Vorschau" im Trip-Detail-View rendert Email-Faksimile (iframe) und SMS-Phone-Frame nebeneinander, basierend auf den bereits existierenden Backend-Endpoints `/api/preview/{trip_id}/{email|sms}`. Teil von Epic #140 (Output-Vorschau, Option C Hybrid).

## Ausgangslage — Wichtig!

**Der Code für #189 ist bereits committed (16. Mai 2026):**

| Commit | Datum | Inhalt |
|--------|-------|--------|
| `2ce9d68` | 11.05. | `feat(api): Preview-Endpoints für Email + SMS (Epic #140, Issue #189-Vorbereitung)` — Backend |
| `caadacc` | 16.05. | `feat(frontend): Output-Vorschau-Tab mit Email-iframe + SMS-Phone-Frame (Issue #189)` — Frontend |
| `a74c018` | 16.05. | `fix(go-api): /api/preview/{trip_id}/email|sms an Python proxien (Issue #189)` — Go-Proxy |

**Aber:** Issue ist **OPEN** auf GitHub, Spec ist `status: draft`, Workflow wurde nie offiziell durchlaufen (kein `/6-validate`, kein `/7-deploy`-Eintrag). Endpoints antworten auf Staging + Prod mit HTTP 401 (Auth-Wand, erwartet — heißt: Endpoints sind deployed).

→ **Aufgabe in Phase 2:** Klären, was zwischen „committed/deployed" und „Issue schließbar" noch fehlt. Vermutlich: Approval der Spec, Validierung gegen Staging (Browser-Session mit eingeloggtem User), Doku-Updates.

## Related Files

### Specs

| File | Relevance |
|------|-----------|
| `docs/specs/modules/issue_189_preview_tab_integration.md` | **Sub-Spec für #189** (draft, 9 AC's, sehr detailliert) |
| `docs/specs/modules/epic_140_output_vorschau.md` | Master-Spec Epic #140 (Option C Hybrid-Architektur) |
| `docs/specs/modules/preview_service.md` | Backend-Sub-Spec (approved) |

### Backend (deployed, unverändert)

| File | Relevance |
|------|-----------|
| `api/routers/preview.py` | FastAPI-Router mit beiden Endpoints, Auth via `user_id`-Query |
| `src/services/preview_service.py` | Render-Orchestrierung (Trip-Load → Wetter-Fetch → format_email/SMS) |

### Go-Proxy (deployed)

| File | Relevance |
|------|-----------|
| `internal/handler/preview_proxy.go` | Proxy-Handler, injiziert `user_id` aus Session-Cookie |
| `internal/handler/preview_proxy_test.go` | 6 Tests, GREEN |
| `cmd/server/main.go:112-113` | Route-Registrierung `/api/preview/{trip_id}/{email\|sms}` |

### Frontend (committed)

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/preview/EmailIframe.svelte` | iframe-Wrapper, `sandbox="allow-same-origin"`, Lade-/Fehler-States |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | iOS-Dark-Frame 320px + Token-Bubble + Char-Counter + Stub-Pill |
| `frontend/src/lib/components/preview/previewHelpers.ts` | Pure Functions: `buildPreviewUrl`, `defaultReportType`, `charCountStatus` |
| `frontend/src/lib/components/preview/index.ts` | Barrel-Export |
| `frontend/src/lib/components/preview/__tests__/previewHelpers.test.ts` | Pure-Function-Tests (AC-1, AC-6, AC-7) — Node `node:test` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | **Tab „Vorschau" bereits verkabelt** (Zeilen 95-109): Morning/Evening-Radio, Side-by-Side-Grid mit `EmailIframe` + `SmsPhoneFrame` |

### Bestand (nicht angefasst)

- `frontend/src/lib/components/email-preview/` — `headerStats.ts` + `EmailPreviewHeader.svelte` aus Issue #183 bleiben für etwaige Mini-Header-Verwendung; **nicht** Teil von #189
- `src/output/renderers/email/html.py` — Backend-HTML-Renderer, vom PreviewService konsumiert
- `src/output/tokens/builder.py` — SMS-Token-Builder

## Existing Patterns

- **Hybrid-Vorschau (Option C):** Backend rendert HTML genau wie echte Mail → eine Render-Quelle, kein Drift. Frontend zeigt nur an, transformiert nicht.
- **Go-Proxy für User-Auth:** Python-Endpoints brauchen `user_id`-Query; Go-Proxy liest Session-Cookie und hängt ihn an. Frontend kümmert sich nicht um Auth-Details (`credentials: 'same-origin'` reicht).
- **Pure-Function-Tests via Node `node:test`:** Gleiches Muster wie Issue #183 (`headerStats.test.ts`) — keine Vitest, kein JSDOM.
- **iframe-Sandbox:** `sandbox="allow-same-origin"` für statisches Mail-HTML (kein JS-Bedarf).
- **Design-System-Tokens:** `--g-paper`, `--g-ink`, `--g-accent`, `--g-r-3`, `--g-shadow-1` mit Fallbacks (`var(--g-r-3, var(--g-radius-lg, 0.75rem))` — Drift zwischen tokens.css und app.css ist bekannt).
- **Stub-Heuristik im Frontend:** SmsPhoneFrame erkennt heuristisch, ob das Backend echtes Spec-Token oder Email-Subject-Stub liefert (`:` als Marker) und zeigt eine „SMS-Token-Pipeline folgt (#188)"-Pill.
- **Tabs via `bits-ui`:** TripTabs nutzt `Tabs.Root/List/Trigger/Content`, Hash-Sync via `history.replaceState`.

## Dependencies

- **Upstream (was die Vorschau konsumiert):**
  - `TripReportFormatter.format_email()` — echter Mail-Renderer
  - `build_token_line()` / `email_subject` — SMS-Token (aktuell noch Stub aus Subject)
  - `SegmentWeatherService.fetch_segment_weather()` — Wetter-Daten
  - `Settings.with_user_profile(user_id)` — User-Scoping
- **Downstream (was die Vorschau konsumiert):**
  - `TripTabs.svelte` rendert die beiden Vorschau-Komponenten
  - Keine weiteren Konsumenten (Vorschau hat keine Side Effects, keine Persistenz)

## Existing Specs

- `docs/specs/modules/issue_189_preview_tab_integration.md` — Sub-Spec für #189 (draft, 9 AC's)
- `docs/specs/modules/epic_140_output_vorschau.md` — Master Epic #140
- `docs/specs/modules/preview_service.md` — Backend (approved)

## Risks & Considerations

1. **Doppel-Implementierung-Risiko:** Code ist schon da. Wenn Phase 5/6 (`/tdd-red` + `/implement`) durchläuft, könnte der Workflow versuchen, bestehenden Code erneut zu schreiben oder als „fehlt noch" zu behandeln. → Phase 2 muss klar abgrenzen: was ist da, was fehlt.

2. **Spec-Approval offen:** `issue_189_preview_tab_integration.md` ist `status: draft`. Ohne Approval blockt der Workflow-Gate vermutlich weitere Code-Edits. PO-Approval einholen.

3. **SMS-Token ist Stub:** Backend liefert aktuell Email-Subject als `token_line`, kein echtes Spec-Format-Token (`KHW_00B: N3 D11 …`). Echtes Token kommt mit Issue #188. Frontend zeigt korrekt eine Hinweis-Pill, aber wenn der User echtes SMS-Format erwartet, müssen wir das vorher klarstellen.

4. **E2E-Verifikation steht aus:** Vorschau-Tab wurde nie offiziell mit eingeloggtem User durch den Browser geklickt. AC-2, AC-3, AC-4, AC-5, AC-8 sind Komponenten-AC's, die laut Spec „in Phase 7 per E2E-Hook gegen den laufenden Server verifiziert" werden sollen.

5. **iframe-CSS-Drift zu Epic #236:** Mail-Templates sind noch nicht ans Design-System angepasst (Epic #236). Vorschau zeigt damit das alte Mail-Design — das ist konsistent (echte Mail sieht ja auch noch so aus), aber visuell evtl. nicht erwartungskonform.

6. **Auth-Test-Pfad:** Smoke-Test gegen Endpoints liefert 401 (richtig — nicht eingeloggt). Echte Verifikation braucht Browser-Session oder Playwright mit Login-Fixture.

7. **Side-by-Side vs. Mobile:** Layout ist Desktop-first (Memory-Konvention), unter ~960 px stapeln die Komponenten. Konsistent mit „Frontend = Desktop-Planungstool".

## Nächste Schritte

→ Phase 2 (`/2-analyse`): Delta zwischen Ist (committed/deployed) und Soll (Issue schließbar) bestimmen. Vermutliche Schwerpunkte:
- Spec von draft → approved (PO-Entscheidung)
- E2E-Verifikation gegen Staging mit Browser-Session
- Visual-Smoke-Check der Tab-Vorschau im Frontend
- Doku-Updates (CLAUDE.md „Implementierte Module" um `output_preview` o.ä. ergänzen?)
- Issue auf GitHub schließen

## Phase-2-Befund (2026-05-17)

### Automatisierte Tests — alle grün

| Suite | Stand | Deckt AC |
|-------|-------|----------|
| Frontend `previewHelpers.test.ts` (Node `node:test`) | 13/13 grün | AC-1, AC-6, AC-7 |
| Python `pytest -k preview` (Test-Manifest des preview_service) | 16/16 grün | AC-1..5 der `preview_service.md` |
| Go `TestPreviewProxy*` (6 Tests) | 6/6 grün | AC-9 (Go-Proxy) |

Damit sind **5 von 9 AC's automatisiert verifiziert** (AC-1, AC-6, AC-7, AC-9 vollständig + Teile durch Python-Service-Tests abgedeckt).

### Offene AC's (brauchen Browser mit eingeloggtem User)

- **AC-2:** EmailIframe lädt Backend-HTML, schreibt in `srcdoc` (kein leeres iframe)
- **AC-3:** SmsPhoneFrame zeigt `token_line` (JetBrains Mono) + `char_count`/160
- **AC-4:** Morning↔Evening-Umschalter triggert neuen Fetch, kein Mischzustand
- **AC-5:** HTTP 404/422/503 werden sichtbar gerendert (Fehler-Meldung)
- **AC-8:** Design-System-Tokens (`--g-paper`, `--g-ink`, `--g-accent`, `--g-r-3`, `--g-shadow-1`) statt hartkodierter Farben — DOM-Inspector

### Strategische Entscheidung

**Workflow-Retrofit statt Doppelimplementierung:** Phasen 3/4/5/6 überspringen, weil Code/Tests/Specs vorhanden sind. Direkt nach Approval zu Phase 7 (Validate) — Browser-E2E gegen Staging mit eingeloggtem User.

User-Entscheidung 2026-05-17: ✅ Spec approven + Phase 7 (Validate).

### Scope

- Code-Änderungen: **0 LoC** (alles schon committed)
- Doku-Update: ~5-10 LoC (CLAUDE.md „Implementierte Module" um `output_preview` ergänzen)
- Browser-Verifikation: 1 Login-Session auf `https://staging.gregor20.henemm.com`, Tab Vorschau, Screenshots
