---
workflow: epic-8-output-preview
github_issue: 140
created: 2026-05-16
supersedes: docs/context/epic-140-output-vorschau.md (Stand 2026-05-11, vor Architektur-Entscheidung)
---

# Context: EPIC 8 — Output-Vorschau (Email + SMS)

## Request Summary

Vorschau-Tab in der Trip-Übersicht, der zeigt, wie das nächste Briefing aussehen wird:
- **Email:** vollständige HTML-Tabelle (Header, Quick-Take, Stirnlampe, Segment-Tabellen, Ziel, Upcoming, Summary, Footer)
- **SMS:** iOS-Phone-Frame mit Token-Zeile (`KHW_00B: N3 D11 R3.8 …`) + Zeichenzähler (/160)

GitHub Issue: [#140](https://github.com/henemm/gregor_zwanzig/issues/140) (Epic-Label).

## Sub-Issues — Aktueller Stand (2026-05-16)

| # | Inhalt | Status |
|---|--------|--------|
| #183 | Email-Preview: Header | CLOSED |
| #184 | Email-Preview: Quick-Take + Wetter-Tags | **CLOSED (obsolet durch Option C)** |
| #185 | Email-Preview: Stirnlampe-Block | **CLOSED (obsolet durch Option C)** |
| #186 | Email-Preview: Segment-Tabellen + RiskDot | **CLOSED (obsolet durch Option C)** |
| #187 | Email-Preview: Nächste Etappen + Summary + Footer | **CLOSED (obsolet durch Option C)** |
| #188 | SMS-Preview: Phone-Frame + Spec-Token-Pipeline | **OFFEN — eigener Folge-Workflow** (Backend muss echtes Spec-Token bauen) |
| #189 | Vorschau-Integration in Trip-Übersicht (Tab) | **OFFEN — Scope dieses Workflows** |

## Architektur-Entscheidung (bereits getroffen: Option C — Hybrid)

Spec `docs/specs/modules/epic_140_output_vorschau.md` (committed 2026-05-11) legt fest:

```
Backend (Python, FastAPI):
  ├─ GET /api/preview/{trip_id}/email?type=morning|evening&date=ISO → HTML-String
  └─ GET /api/preview/{trip_id}/sms?type=morning|evening&date=ISO   → {subject, token_line, char_count}

Frontend (SvelteKit):
  ├─ EmailIframe.svelte   → <iframe srcdoc={htmlFromBackend} />
  └─ SmsPhoneFrame.svelte → iOS-Mockup + Backend-Token + Zähler
```

**Backend = Single Source of Truth**, Frontend zeigt nur. Kein Drift, keine doppelte HTML-/Token-Logik.

## Bereits committed (Stand 2026-05-16)

| Datei | Status |
|-------|--------|
| `api/routers/preview.py` (~3 KB) | ✓ 2 Endpoints (email + sms) |
| `src/services/preview_service.py` (~10 KB) | ✓ Trip-Load + Render-Orchestrierung |
| `src/output/renderers/email/html.py` `render_html()` | ✓ HTML-Renderer existiert |
| `src/output/tokens/builder.py` `build_token_line()` | ✓ SMS-Token-Builder existiert |
| `frontend/src/lib/components/email-preview/headerStats.ts` + Tests | ✓ Pure-Function GREEN |
| `frontend/src/lib/components/email-preview/EmailPreviewHeader.svelte` | ✓ aus #183 |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` Zeile 29 | ✓ `preview`-Tab im Array, Zeile 38 Placeholder |
| `docs/specs/modules/epic_140_output_vorschau.md` | ✓ Master-Spec |

## Bereits geschlossene Nebenarbeiten

- #183 Email-Header (CLOSED)
- #155 Tab-Navigation (CLOSED, Epic #135 Step 1)
- #152, #158, #159 Trip-Übersicht-Spalten (CLOSED)

## Related Files (Frontend-Ziele für offene Sub-Issues)

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/email-preview/` | Ziel-Ordner für alle Email-Bausteine (#184-#187) |
| `frontend/src/lib/components/ui/eyebrow/` | Bestehende Eyebrow-Komponente — bereits im Header |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | SVG-Vorbild für DaylightBar (#185) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Slot für `preview`-Content (#189) |
| `frontend/src/lib/types.ts` | Trip/Stage/Waypoint-Typen |

## Backend-Quellen (SSOT für Format)

| File | Zweck |
|------|-------|
| `src/output/renderers/email/html.py` | HTML-Render-Funktion (wird via iframe gespiegelt) |
| `src/output/tokens/builder.py` | SMS-Token-Zeile (Frontend zeigt nur) |
| `src/services/daylight_service.py` | `DaylightWindow` (für #185) |
| `docs/reference/sms_format.md` v2.1 | **SSOT** SMS-Token-Format |
| `docs/reference/renderer_email_spec.md` | Email-Layout-Definition |

## Existing Specs

- `docs/specs/modules/epic_140_output_vorschau.md` — Master-Spec Hybrid-Architektur
- `docs/specs/modules/output_channel_renderers.md` (β3) — Backend-Channel-Renderer
- `docs/specs/modules/output_token_builder.md` — Token-Builder
- `docs/specs/modules/output_text_report_renderer.md` (β4) — Text-Renderer
- `docs/specs/modules/issue_183_email_preview_header.md` — Header-Komponente

## Dependencies

- **Upstream (existiert):** Backend-Preview-Endpoints, Render-Funktionen, Tab-Slot in TripTabs.svelte.
- **Downstream (wird ausgebaut):** Trip-Übersicht (#159 Mini-Vorschau-Idee), Cockpit-Startseite (#152 könnte später Quick-Preview zeigen).

## Risks & Open Questions

| Risiko | Hinweis |
|--------|---------|
| **Daten-Freshness** | Preview lädt echte Wetter-Daten. Bei lange laufenden Trips: Cache-Verhalten klären (Provider-Adapter cacht?). |
| **iframe-Styling** | `srcdoc`-iframes erben kein Eltern-CSS — Email-HTML muss alle Styles inline mitliefern (so wie für echte Mails). |
| **Phone-Frame-Pixel-Treue** | iOS-Stil ist optisch sensibel — Design-System hat keine fertigen iOS-Tokens. Eigene SVG-/CSS-Mockup nötig. |
| **Zeichenzähler exakt** | `char_count` muss vom Backend kommen, damit Frontend nicht falsch zählt (UTF-8, Emoji). |
| **`report_config` pro Trip** | Trip kann mehrere Briefings (Morgen/Abend) haben → Tab braucht Briefing-Auswahl (Dropdown). |
| **User-Scoped Trip-Load** | Preview-Service nutzt `user_id`. Go-Proxy injiziert ihn — Bug #199 angeblich gefixt, bei Tests verifizieren. |
| **Sub-Issue-Reihenfolge** | Reihenfolge zu wählen in Phase 2. Vorschlag: erst **#189** (Tab-Integration mit iframe + Backend-Daten als MVP) → liefert sofortige sichtbare End-to-End-Vorschau. Danach Bausteine #184-#188 als Nice-to-have für native Svelte-Bauteile, falls die iframe-Lösung Schwächen zeigt. |

## Phase 2 Ergebnis — Scope-Entscheidung (User bestätigt 2026-05-16)

- **Dieser Workflow:** nur Issue **#189** (Tab-Integration mit Email-iframe + SMS-Phone-Frame). Geschätzter Scope ~5 Dateien, ~250 LoC.
- **#184-#187 geschlossen** als obsolet (Option C macht native Svelte-Email-Bauteile unnötig).
- **#188 vertagt** auf eigenen Folge-Workflow: dort wird im Backend (`preview_service.render_sms_preview`) der echte Spec-Format-Token gebaut (`KHW_00B: N3 D11 R3.8 …`) statt des aktuellen Email-Subject-Stubs. Bis dahin zeigt der Phone-Frame den Email-Subject als Token-Inhalt.

## Befund: SMS-Backend ist Stub

`src/services/preview_service.py:130-143` liefert für SMS-Preview den **Email-Subject** als Token (gekürzt auf 160 Zeichen). Das ist kein Spec-Format-Token. Frontend kann gegen den Endpoint bauen, aber die SMS-Vorschau wird inhaltlich erst mit Folge-Workflow #188 sinnvoll.

## Out of Scope

- Backend-Render-Refactor (existiert, bleibt)
- E-Mail-Send-Logik
- Mobile Phone-Frame-Animationen
- Echte iOS-Render-Treue (Mockup reicht)
