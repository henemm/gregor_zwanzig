---
entity_id: epic_140_output_vorschau
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [epic, frontend, backend, preview, output, iframe]
---

<!-- Epic #140 — Output-Vorschau: Email + SMS — Architektur: Option C (Hybrid) -->

# Epic 140 — Output-Vorschau (Hybrid-Architektur)

## Approval

- [ ] Approved

## Purpose

Vorab anzeigen, wie das nächste Trip-Briefing aussehen wird — Email-Vorschau als **Faksimile** der echten Mail, SMS-Vorschau im iPhone-Frame mit Zeichenzähler.

**Architektur-Entscheidung (Option C):**
- Email: Backend rendert das vollständige HTML genau wie die echte Mail, Frontend zeigt es in einem `<iframe srcdoc>`.
- SMS: Backend liefert die Token-Zeile, Frontend rendert den Phone-Frame drumherum.

Damit: **eine Render-Quelle**, kein Drift-Risiko zwischen Vorschau und echtem Versand.

## Source

### Backend (NEU)

- **File:** `api/routers/preview.py` (NEU) — zwei Endpoints
- **File:** `src/services/preview_service.py` (NEU) — orchestriert Trip-Load → Wetter-Fetch → Render
- **Endpoint:** `GET /api/preview/{trip_id}/email?type=morning|evening&date=YYYY-MM-DD` → HTML-String
- **Endpoint:** `GET /api/preview/{trip_id}/sms?type=morning|evening&date=YYYY-MM-DD` → JSON `{subject, token_line, char_count}`

### Frontend (NEU)

- **File:** `frontend/src/lib/components/preview/EmailIframe.svelte` (NEU) — iframe-Wrapper mit `srcdoc`
- **File:** `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` (NEU) — iOS-Dark-Frame 320px + Zeichenzähler
- **File:** `frontend/src/routes/trips/[id]/edit/+page.svelte` (ERWEITERT) — Tab "Vorschau"

### Bestand (bleibt)

- `src/output/renderers/email/html.py` — Backend-HTML-Renderer
- `src/output/tokens/builder.py` — SMS-Token-Builder
- `src/services/trip_report_scheduler.py` — Echter Versand (separates Modul, nicht betroffen)
- `frontend/src/lib/components/email-preview/` — pure-function `headerStats.ts` + `EmailPreviewHeader.svelte` (aus #183, in dieser Architektur **optional** für Mini-Header in Trip-Übersicht; nicht in der Vollvorschau)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportFormatter.format_email()` | bestehend | Erzeugt komplettes Email-HTML |
| `build_token_line()` | bestehend | Erzeugt SMS-Token-Zeile |
| `SegmentWeatherService.fetch_segment_weather()` | bestehend | Liefert Wetter-Daten — wird vom Preview-Service gerufen |
| `Trip`-Loader aus `src/app/loader.py` | bestehend | Lädt Trip aus `data/users/<uid>/trips/<id>.json` |
| `epic_191_state_migration` etc. | bestehend | Workflow-Toolchain (kein direkter Bezug) |

## Implementation Details

### Backend-Endpoint `GET /api/preview/{trip_id}/email`

```python
# api/routers/preview.py
@router.get("/api/preview/{trip_id}/email", response_class=HTMLResponse)
async def preview_email(
    trip_id: str,
    type: str = "morning",  # "morning" | "evening"
    user_id: str = Query(...),  # via Go-Proxy aus Session
    date: str | None = None,  # ISO date, default = nächste Stage-Datum
):
    service = PreviewService(Settings().with_user_profile(user_id))
    html = service.render_email_preview(trip_id, report_type=type, target_date=date)
    return HTMLResponse(content=html)
```

### Backend-Endpoint `GET /api/preview/{trip_id}/sms`

```python
@router.get("/api/preview/{trip_id}/sms")
async def preview_sms(trip_id: str, type: str = "morning", user_id: str = Query(...), date: str | None = None):
    service = PreviewService(Settings().with_user_profile(user_id))
    token_line, subject = service.render_sms_preview(trip_id, report_type=type, target_date=date)
    return {
        "subject": subject,
        "token_line": token_line,
        "char_count": len(token_line),
    }
```

### `PreviewService` (NEU, ~120 LoC)

```python
class PreviewService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.formatter = TripReportFormatter(settings)
    
    def render_email_preview(self, trip_id: str, *, report_type: str, target_date: str | None) -> str:
        trip = self._load_trip(trip_id)
        stage = trip.get_stage_for_date(target_date or self._next_stage_date(trip))
        segments = self.formatter._convert_trip_to_segments(trip, stage.date)
        weather = SegmentWeatherService().fetch_segment_weather(segments)
        # ... DaylightWindow, ThunderForecast, Highlights ...
        return self.formatter.format_email(...)
    
    def render_sms_preview(self, ...) -> tuple[str, str]:
        # Token-Builder aufrufen
        ...
```

### Frontend — `EmailIframe.svelte`

```svelte
<script lang="ts">
  interface Props { tripId: string; type: 'morning' | 'evening'; date?: string }
  let { tripId, type, date }: Props = $props();
  
  let html = $state('');
  let loading = $state(true);
  let error = $state<string | null>(null);
  
  async function load() {
    loading = true;
    try {
      const params = new URLSearchParams({ type, ...(date && { date }) });
      const resp = await fetch(`/api/preview/${tripId}/email?${params}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      html = await resp.text();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }
  $effect(() => { load(); });
</script>

{#if loading}<p>Lade Vorschau…</p>
{:else if error}<p class="text-red-600">Fehler: {error}</p>
{:else}
  <iframe srcdoc={html} title="Email-Vorschau" class="w-full min-h-[600px] border" sandbox="allow-same-origin"></iframe>
{/if}
```

### Frontend — `SmsPhoneFrame.svelte`

iOS-Dark-Frame (320×640 px), in der Mitte die Token-Zeile umbruchfrei, darunter Zeichenzähler `N/160`. Legende **außerhalb** des Frames.

### Frontend — Tab-Integration in Trip-Detail

```svelte
<!-- frontend/src/routes/trips/[id]/edit/+page.svelte -->
<script>
  import EmailIframe from '$lib/components/preview/EmailIframe.svelte';
  import SmsPhoneFrame from '$lib/components/preview/SmsPhoneFrame.svelte';
  let activeTab = $state<'edit' | 'preview'>('edit');
  let previewType = $state<'morning' | 'evening'>('morning');
</script>

<nav>
  <button onclick={() => activeTab = 'edit'}>Bearbeiten</button>
  <button onclick={() => activeTab = 'preview'}>Vorschau</button>
</nav>

{#if activeTab === 'edit'}<TripEditView trip={data.trip} />
{:else}
  <div class="flex gap-4">
    <EmailIframe tripId={data.trip.id} type={previewType} />
    <SmsPhoneFrame tripId={data.trip.id} type={previewType} />
  </div>
{/if}
```

## Acceptance Criteria

- **AC-1:** Given Trip mit gültiger Stage und Wetter-Daten / When `GET /api/preview/{trip_id}/email?type=morning` läuft / Then HTTP 200 mit `Content-Type: text/html` und HTML-Body, der bit-identisch zur echten Mail-Render-Pipeline ist (`TripReportFormatter.format_email()` aufgerufen, kein eigener Renderer)
- **AC-2:** Given Trip ohne gültige Stage am gegebenen Datum / When der Endpoint gerufen wird / Then HTTP 404 mit klarer Fehlermeldung "Keine Stage am Datum X gefunden"
- **AC-3:** Given Trip eines anderen Users (`user_id` aus Session != Trip-Owner) / When der Endpoint gerufen wird / Then HTTP 403 (Auth-Check über bestehende Go-Proxy-Logik plus User-Owner-Check)
- **AC-4:** Given `GET /api/preview/{trip_id}/sms?type=morning` / When der Endpoint läuft / Then JSON `{"subject": "...", "token_line": "<=160 Zeichen>", "char_count": N}` zurück, wobei `token_line == build_token_line(...)` (identisch zur echten SMS)
- **AC-5:** Given `<EmailIframe tripId="..." type="morning" />` im Frontend / When die Komponente gemountet wird / Then Loading-State → Backend-Call → iframe mit `srcdoc` zeigt die echte Vorschau
- **AC-6:** Given `<SmsPhoneFrame ... />` / When die Komponente gemountet wird / Then iOS-Dark-Frame 320 px breit, Token-Zeile in der Mitte, Zeichenzähler `N/160` unterhalb, Legende außerhalb
- **AC-7:** Given Trip-Detail-Route `/trips/[id]/edit` / When der Tab "Vorschau" aktiv ist / Then `EmailIframe` und `SmsPhoneFrame` werden nebeneinander gerendert, Umschalter Morning/Evening sichtbar
- **AC-8:** Given Backend-Endpoints sind down (Service-Crash) / When Frontend ruft sie / Then Frontend zeigt Fehler-Meldung, kein leeres iframe
- **AC-9:** Given Pure-function-Test (Node) für die Preview-Service-Hauptlogik / When `uv run pytest tests/tdd/test_preview_service.py` läuft / Then mindestens 3 Tests grün: (a) Email-HTML enthält Trip-Name + Stage-Name, (b) SMS-Token <=160 Zeichen, (c) Fehler bei fehlender Stage

## Expected Behavior

- **Input:** Trip-ID + Report-Type + optionales Datum (aus URL bzw. Frontend-Props)
- **Output:** HTML-String (Email) oder JSON mit Token-Zeile (SMS); Frontend zeigt das im iframe bzw. Phone-Frame
- **Side effects:** Keine — Vorschau berührt keinen Versand, keinen Logbuch-Eintrag, keine Wetter-Cache-Mutation außer normalem Fetch-Cache

## Known Limitations

- **Wetter-Provider-Calls bei jeder Vorschau:** Erste Vorschau triggert echten Wetter-Fetch. Mitigation: Service nutzt bestehenden Wetter-Cache (kein Spec-Change nötig).
- **Mock-Modus für leere Stages:** Wenn Trip noch keine Wetter-Daten hat (z.B. Zukunfts-Stage außerhalb Forecast-Range), liefert Endpoint 404. Mock-Modus mit Dummy-Wetter wäre eigener Folge-Issue.
- **Sub-Issues #184-187 werden mit Option C obsolet:** Header/Quick-Take/Stirnlampe/Tabellen sind Teil des Backend-HTMLs, nicht separate Frontend-Komponenten. **Empfehlung an PO:** #184-187 schließen mit Verweis auf diese Spec; nur #183 (bereits fertig, kann als Mini-Header in Trip-Übersicht weiterverwendet werden), #188 (SMS-Frame) und #189 (Tab-Integration) bleiben als eigenständige Issues.
- **iframe-Sandbox:** `sandbox="allow-same-origin"` reicht für reine Anzeige. Keine Skripte im iframe nötig — Backend-HTML ist statisch.
- **Auth pro Endpoint:** Go-Proxy hängt `user_id` aus Session an Query (siehe Bug #199 Fix). Python-Endpoint prüft zusätzlich Trip-Owner.

## Changelog

- 2026-05-11: Initial spec — Epic #140 mit Architektur-Option C (Hybrid: Backend-HTML + Frontend-iframe für Email, Backend-Token + Frontend-Frame für SMS)
