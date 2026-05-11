# Context: epic-140-output-vorschau

## Request Summary

Frontend-Vorschau für Briefing-Reports: vollständige Email-Tabellenansicht als 7 Svelte-Komponenten (Header, Quick-Take, Stirnlampe, Segment-Tabellen, Etappen+Summary, Footer) + SMS-Preview im Phone-Frame mit Token-Zeile. Integration als Tab "Vorschau" in der Trip-Detail-Ansicht.

## Sub-Issues (alle offen)

| # | Inhalt | Stand |
|---|--------|-------|
| #183 | Email-Preview: Header (Eyebrow + Trip + Stats) | **Pure-function fertig** (`headerStats.ts`, 6 Tests). Svelte-Komponente offen. |
| #184 | Email-Preview: Quick-Take + Wetter-Tags (ok/warn/risk/info) | offen |
| #185 | Email-Preview: Stirnlampe-Block (DaylightBar SVG) | offen |
| #186 | Email-Preview: Segment-Tabellen + RiskDot-Ampel | offen |
| #187 | Email-Preview: Nächste Etappen + Summary + Footer | offen |
| #188 | SMS-Preview: Phone-Frame + Token-Zeile + /160 | offen |
| #189 | Vorschau-Integration in Trip-Übersicht (Tab) | offen — braucht alle anderen |

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/email-preview/` | Ziel-Ordner — `headerStats.ts` schon da |
| `frontend/src/lib/components/ui/eyebrow/` | Bestehende Eyebrow-Komponente — wird im Header genutzt |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Vorbild für SVG-Komponenten (DaylightBar in #185) |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Trip-Detail-Route — Tab "Vorschau" muss hier rein (#189) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Aktuelle Trip-Detail-View — wird um Tab erweitert |
| `frontend/src/lib/types.ts` | Trip/Stage/Waypoint-Typen — Datenmodell für Props |

## Backend-Quellen (für Daten + Format-Definition)

| File | Zweck |
|------|-------|
| `src/output/renderers/email/html.py` | Backend rendert Email-HTML — Format-Vorbild |
| `src/output/renderers/sms/` | Backend baut SMS-Token-Zeile |
| `src/output/tokens/builder.py` | Token-Zeilen-Generator (`KHW_00B: N3 D11 R3.8 ...`) |
| `src/services/daylight_service.py` | `DaylightWindow` mit `usable_start`/`usable_end` — Quelle für Stirnlampe |
| `docs/reference/sms_format.md` v2.0 | **Single Source of Truth** für SMS-Token-Format |
| `docs/reference/renderer_email_spec.md` | Email-Layout-Definition |

## Existing Specs

- `docs/specs/modules/output_channel_renderers.md` — Backend-Channel-Renderer (β3)
- `docs/specs/modules/output_token_builder.md` — Token-Builder
- `docs/specs/modules/output_subject_filter.md` — Subject-Generierung
- `docs/specs/modules/issue_183_email_preview_header.md` — bereits geschrieben (teilfertig)

## Existing Patterns

- **Pure-function in `.ts`, Visual in `.svelte`** — Wegen Test-Setup (`node --experimental-strip-types`, kein Svelte-Compiler im Test). Logik in `*.ts`, Svelte nur als dünner Wrapper.
- **SVG-Komponenten** — `ElevSparkline.svelte` als Vorbild für DaylightBar (#185).
- **Tab-Navigation** — Trip-Übersicht-Route hat noch keine Tab-Logik (Epic #135 #155). Wenn #189 vor #155 kommt, muss Tab-Struktur improvisiert werden.

## Dependencies

- **Upstream (was wir brauchen):**
  - Trip-Daten (lokal aus Svelte-State oder Backend-API)
  - Wetter-Daten pro Etappe (Backend-API `/api/forecast` oder ähnlich)
  - DaylightWindow-Daten (Backend-Endpoint nötig oder im Frontend nachbauen?)
  - Risk-Bewertung pro Segment (Backend liefert)

- **Downstream (was uns nutzt):**
  - #189 Vorschau-Tab — komponiert alle 6 Email-Bauteile + SMS-Frame
  - Mögliche spätere Nutzung in Trip-Übersicht (#159 "rechte Spalte" könnte Mini-Vorschau zeigen)

## Risks & Considerations

| Risiko | Mitigation |
|--------|-----------|
| **Render-Duplikation Backend ↔ Frontend** | Email-Layout wird im Backend (`html.py`) und Frontend (7 Svelte-Komponenten) parallel gepflegt. Drift möglich. Mitigation: Spec `renderer_email_spec.md` ist Single Source — beide Renderer müssen sich daran halten. |
| **Wetter-Daten im Frontend** | Vorschau braucht echte Daten (sonst sinnlose Platzhalter). Entweder Backend-Endpoint `/api/preview?trip_id=...` oder nur Mock-Daten in Demo-Route. **Entscheidung in /2-analyse.** |
| **Tab-Navigation noch nicht da** | Epic #135 (#155 Tab-Navigation) ist nicht abgeschlossen. #189 könnte vor #155 fertig sein → entweder warten oder lokale Tab-Struktur. |
| **#183 Svelte-Komponente fehlt** | Pure-function ist committed (0268d42), aber `EmailPreviewHeader.svelte` braucht Browser-Session. Gilt analog für alle anderen Sub-Issues mit `.svelte`-Komponenten. |
| **SVG-Komplexität (DaylightBar #185)** | DaylightWindow hat `usable_start`/`usable_end` + Dämmerung + Wolken-Korrektur. SVG-Mapping nicht trivial. Pure-function-Logik separat von Svelte. |
| **SMS-Token-Parsing (#188)** | Frontend braucht Backend-API oder eigenes Parsing der Token-Zeile. **Empfehlung:** Backend-Endpoint liefert fertige Zeile, Frontend zeigt nur. Kein Token-Parsing im Frontend. |
| **Browser-Hook blockt UI-Komponenten** | `ui_screenshot_gate.py` blockt neue `.svelte`-Files ohne BEFORE-Screenshot. Jede UI-Komponente braucht Session mit Browser-Zugang. |
| **Backend-API-Coverage** | Es gibt aktuell keine `/api/preview/{trip_id}/email|sms`-Endpoints. Müssten neu gebaut werden — separater Workflow im Python-Backend nötig vor #189. |

## Architektur-Entscheidung (offen, für /2-analyse)

**Option A (volle Render-Duplikation):**
- Frontend baut 7 Svelte-Komponenten, rendert Email komplett selbst
- Wetter-Daten via existierenden Backend-API
- Vorteil: schöne Komponenten-Hierarchie, gut für UI-Iteration
- Nachteil: zwei Render-Quellen → Drift-Risiko

**Option B (iframe-Mirror):**
- Backend bekommt `/api/preview/email?trip_id=...` der das fertige HTML liefert
- Frontend rendert das HTML in einem iframe (mit `srcdoc`)
- Vorteil: ein Render-Code, kein Drift
- Nachteil: weniger Svelte-Bauteile, weniger UI-Iteration im Frontend

**Option C (Hybrid):**
- Email-Preview: iframe-Mirror (Option B)
- SMS-Preview: Frontend rendert Phone-Frame + Backend-gelieferte Token-Zeile
- Tab-Integration als Frontend-Logik

Issue-Beschreibungen sprechen für **Option A** (sie zerlegen die Email in 7 Komponenten). Aber Option B/C wäre wartungsärmer. Klärung im /2-analyse.

## Out of Scope

- Backend-Render-Refactoring (existiert schon, bleibt)
- Echte Wetter-API-Calls aus dem Frontend
- E-Mail-Send-Logik (separat, Bug #198 ist gefixt)
- Trip-Tab-Navigation als Infrastruktur (#155, Epic #135)
