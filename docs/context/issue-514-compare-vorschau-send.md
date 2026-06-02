# Context: Issue #514 — Compare-Vorschau-Tab: Placeholder durch echte Preview ersetzen

## Request Summary

Der "Vorschau"-Tab auf `/compare/[id]` zeigt einen Platzhaltertext statt einer echten
Briefing-Vorschau. Die Backend-Endpoints dafür existieren bereits — es fehlt nur die
Frontend-Anbindung in `CompareTabs.svelte`.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Hauptdatei — "vorschau"-Tab (Zeilen 203–211) enthält den Placeholder |
| `frontend/src/lib/components/compare/CompareDetail.svelte` | Thin-Shell-Wrapper, delegiert an CompareTabs |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | Referenz-Pattern: Load-on-click mit iframe |
| `frontend/src/lib/components/preview/EmailIframe.svelte` | Referenz-Pattern: iframe-Display für HTML |
| `internal/handler/proxy.go:399` | `CompareEmailPreviewProxyHandler` — leitet POST an Python weiter |
| `internal/handler/compare_preset.go:247` | `SendComparePresetHandler` — Stub, gibt `{"status":"queued"}` zurück |
| `api/routers/validator.py:341` | Python-Endpoint, rendert Compare-HTML aus Stub-Daten |
| `src/output/renderers/email/compare_html.py` | Python-Renderer, gibt vollständiges HTML zurück |
| `frontend/src/lib/types.ts:444` | `ComparePreset`-Interface mit `profil`, `hour_from`, `hour_to`, `id` |
| `docs/design-requests/issue_504_compare_preview_send.md` | Design-Entscheidung: Vorschau = Verifikations-Tab mit Kanal-Umschalter + Test-senden |
| `frontend/src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts` | Bestehende Tests — nicht brechen |
| `frontend/src/lib/components/compare/__tests__/issue_517_compare_tabs.test.ts` | Bestehende Tab-Tests |

## Existing Patterns

- **Load-on-click mit iframe:** `AlertPreviewCard.svelte` — "Vorschau laden"-Button, dann
  API-Call, HTML in `<iframe srcdoc>` (sandboxed)
- **iframe-Display:** `EmailIframe.svelte` — sandboxed iframe mit `sandbox="allow-same-origin"`
- **API-Calls:** `api.post()` aus `$lib/api` (überall verwendet)

## API-Infrastruktur

### Vorschau-Endpoint (existiert, Go → Python)
```
POST /api/_validator/compare-email-preview
Body: {
  profile: string,          // preset.profil (ActivityProfile-Wert)
  time_window: [number, number],  // [preset.hour_from, preset.hour_to]
  target_date: string,      // heute ISO-8601
  winner_tags: []           // leer für Vorschau
}
Response: { html: string }  // vollständiges HTML-Dokument
```

### Test-Senden-Endpoint (existiert, Stub)
```
POST /api/compare/presets/{id}/send
Response: { status: "queued" }
```

## Dependencies

- **Upstream:** `ComparePreset` (preset.profil, preset.hour_from, preset.hour_to, preset.id)
- **Downstream:** Keine — nur visuell im Tab

## Risks & Considerations

- Der Preview-Endpoint ist ein `_validator`-Pfad (Auth via `gz_session`-Cookie) → kein CORS-Problem, gleiche Origin
- `send`-Endpoint ist ein **Stub** — löst keinen echten Versand aus. Das ist für Phase 1 OK, Nutzer muss informiert werden
- Python-Renderer nutzt Stub-Daten (kein echter Wetterdaten-Fetch) — Vorschau zeigt fiktiven Ort, nicht echte Orte aus dem Preset. Das sollte im UI klar kommuniziert werden
- Scope ist **nur** der Vorschau-Tab in `CompareTabs.svelte` — keine anderen Tabs, kein neues Routing, kein Go-Code
