# Context: Issue #421 — Vorschau-Fehlermeldung benutzerfreundlich auf Deutsch

## Request Summary
Im Trip-Detail Vorschau-Tab (E-Mail + SMS) erscheint bei fehlenden Wegpunkten der
rohe englische JSON-Fehler `Vorschau konnte nicht geladen werden (HTTP 422).
{"detail":"Stage must have at least one waypoint"}`. Diese Roh-Ausgabe soll durch
eine verständliche, actionable deutsche Meldung ersetzt werden.

Quelle: SOLL-IST-Audit #404 Phase 3, Finding **M-07** (`docs/analysis/epic_404_phase3_soll_ist_vergleich.md:360`).

## Fehler-Kette (komplett verstanden)
1. `src/app/trip.py:98` — `Stage.__post_init__` wirft `ValueError("Stage must have at least one waypoint")` wenn `waypoints` leer.
2. `api/routers/preview.py` (email Z.47–48 / sms Z.76–77) — fängt `ValueError` → `HTTPException(status_code=422, detail=str(e))`. FastAPI serialisiert zu **echtem JSON** `{"detail":"Stage must have at least one waypoint"}` (doppelte Anführungszeichen; das Issue zeigt Python-repr-Stil mit einfachen).
3. `internal/handler/preview_proxy.go:44–46` — Go-Proxy reicht Statuscode + Body **verbatim** durch.
4. **Frontend (Bug-Ort):** `res.text()` wird roh an die Meldung gehängt.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/preview/EmailIframe.svelte:18-21` | E-Mail-Vorschau: `error = `…(HTTP ${res.status}). ${detail}`` mit rohem `res.text()` |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte:24-27` | SMS-Vorschau: identisches Roh-Muster |
| `frontend/src/lib/components/preview/previewHelpers.ts` | Gemeinsame Pure-Functions (URL-Bau etc.) — idealer Ort für `friendlyPreviewError()` |
| `frontend/src/lib/components/preview/__tests__/previewHelpers.test.ts` | Test-Stil-Vorbild: `node:test` + `--experimental-strip-types`, mock-frei |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:126-127` | Verwender: Vorschau-Tab zeigt `<EmailIframe>` + `<SmsPhoneFrame>` nebeneinander |
| `api/routers/preview.py` | Backend-Statuscodes: 404 / 422 / 503 / (Proxy: 502) — relevant für Mapping |

## Existing Patterns
- **Pure-Function + node:test (mock-frei):** `previewHelpers.ts` exportiert reine Funktionen, die in `__tests__/previewHelpers.test.ts` ohne Mocks per `node --experimental-strip-types --test` getestet werden. Genau das Muster für eine neue `friendlyPreviewError(status, body)`-Funktion.
- **Bereits benutzerfreundliche Referenz:** `AlertPreviewCard.svelte:38` zeigt schon nur `'Vorschau konnte nicht geladen werden'` ohne Roh-Detail — gewünschtes Zielverhalten.
- **Fehler-State-Rendering:** Beide Frames haben `error = $state<string|null>(null)` + `{:else if error}<p class="state-msg error">{error}</p>` — nur die Text-Erzeugung ändert sich, nicht das Markup.

## Dependencies
- **Upstream (liefert Fehler):** Python-Backend `preview.py` Statuscodes (404 nicht gefunden, 422 Validierung/leere Wegpunkte, 503 Wetter-Provider, 502 Proxy upstream unreachable) + Netzwerk-Catch (`AbortError` wird ignoriert).
- **Downstream (zeigt Fehler):** `TripTabs.svelte` Vorschau-Tab. Kein anderer Verwender der beiden Frames.

## Existing Specs
- `docs/specs/modules/issue_189_preview_tab_integration.md` — Frontend-Preview-Tab (beide Frames stammen hierher)
- `docs/specs/modules/epic_140_output_vorschau.md` — Master-Spec Output-Vorschau
- `docs/specs/modules/preview_service.md` — Backend-Preview-Service

## Mapping-Vorschlag (für Spec/Analyse zu verfeinern)
| Situation | Bedingung | Deutsche Meldung |
|-----------|-----------|------------------|
| Leere Wegpunkte | Status 422 + `detail` enthält „waypoint" | „Diese Etappe hat noch keine Wegpunkte. Bitte im Wegpunkt-Editor mindestens einen Start- und Zielpunkt festlegen." |
| Sonstiger Fehler / Netzwerk | alle übrigen Status / catch | „Vorschau konnte nicht geladen werden. Bitte später erneut versuchen." |

`friendlyPreviewError(status, body)` parst `body` defensiv als JSON (Fallback: Roh-String-Substring), liest `detail`, matcht case-insensitive auf „waypoint". Niemals Roh-JSON oder HTTP-Code ans UI.

## Risks & Considerations
- **Doppelt fixen, eine Quelle:** Beide Frames müssen dieselbe zentrale Funktion nutzen (Memory: Duplikate konsolidieren), sonst driftet die Meldung.
- **JSON-Parse robust:** Body kann valides JSON, Plain-Text oder leer sein → defensiv parsen, nie werfen.
- **Detail-Substring statt exaktem Vergleich:** Backend-Wortlaut könnte sich ändern; case-insensitive Substring „waypoint" ist stabiler als Volltext-Match. Trade-off in Spec festhalten.
- **Keine neuen Status-Lecks:** Generische Fallback-Meldung darf weder `HTTP <code>` noch JSON enthalten (Kern des Bugs).
- **Frontend-only:** Kein Backend-/Daten-Schema-Touch → Post-Push nur Staging-Smoke + visuelle Prüfung, keine Mail-Verifikation nötig.
- **Scope-Disziplin:** Signal/Telegram-Vorschau laufen NICHT über diese Frames (nur E-Mail + SMS im Tab) — nicht überdehnen.

## Analyse-Entscheidung (Phase 2)

**Typ:** Bug, in Phase 1 vollständig root-caused (komplette Kette Backend→Anzeige). Keine zusätzlichen Explore-/bug-intake-Agenten nötig — nichts mehr zu entdecken.

**Empfohlener Ansatz (Tech-Lead, eine Empfehlung):**
Neue Pure-Function `friendlyPreviewError(status: number, body: string): string` in `previewHelpers.ts`. Beide Frames rufen sie an **zwei** Stellen auf:
1. `if (!res.ok)`-Zweig — ersetzt die rohe `…(HTTP ${status}). ${detail}`-Konkatenation.
2. `.catch()`-Zweig — ersetzt `Netzwerkfehler: ${msg}` durch die generische Meldung (AbortError-Early-Return bleibt unverändert).

**Begründung:** Eine Quelle statt zwei driftende Texte; Pure-Function ist mock-frei testbar (bestehendes `node:test`-Muster); Markup/State-Logik bleibt unangetastet — minimal-invasiv.

**Tests bestätigt frei:** Kein bestehender Test fixiert das alte Roh-Verhalten. `data-testid="email-iframe-error"` / `"sms-error"` vorhanden → E2E-Prüfung in Phase 7 möglich.

**Wortlaut:** Im Issue bereits vorgegeben → verbatim übernehmen, keine Rückfrage nötig.

**Scope:** 3 Quelldateien (`previewHelpers.ts`, `EmailIframe.svelte`, `SmsPhoneFrame.svelte`) + 1 Testdatei. Geschätzt ~30–40 LoC netto — deutlich unter 250-Limit. Frontend-only.
