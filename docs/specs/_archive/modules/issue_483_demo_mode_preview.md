---
entity_id: issue_483_demo_mode_preview
type: module
created: 2026-05-31
updated: 2026-05-31
status: implemented
version: "1.0"
tags: [frontend, backend, preview, demo-mode, fixture, issue-483]
parent_spec: docs/specs/modules/issue_189_preview_tab_integration.md
---

# Issue #483 — Demo-Modus im Vorschau-Tab

## Approval

- [x] Approved

## Purpose

Der Vorschau-Tab im Trip-Detail öffnet aktuell sofort Live-API-Calls gegen OpenMeteo. Schlägt der Provider fehl (Trip in der Vergangenheit, API-Limit erreicht), sehen alle Segmente "Wetterdaten nicht verfügbar" — der Tab ist de facto unbrauchbar. Dieser Workflow führt einen Demo-Modus als Startzustand ein: der Tab lädt immer zunächst mit Fixture-Daten (FixtureProvider), sodass die Vorschau-Darstellung zuverlässig funktioniert; der User kann danach explizit auf "Echte Wetterdaten laden" klicken.

## Source

> **Schicht-Hinweis:** Diese Spec betrifft drei Schichten gleichzeitig: **Python-Backend** (`src/services/`), **Go-API-Router** (`api/routers/`), und **Frontend (SvelteKit)** (`frontend/src/lib/components/`). Alle Schichten bekommen additive Änderungen — kein bestehendes Verhalten wird entfernt.

### Patch Backend

- **File:** `src/services/trip_report_scheduler.py`
  - **Identifier:** `_fetch_weather(segments, provider=None)` — optionaler `provider`-Parameter, rückwärtskompatibel (Default `None` = bisheriges Verhalten)

- **File:** `src/services/preview_service.py`
  - **Identifier:** `PreviewService._build_report(trip, target, report_type, demo=False)` — `demo: bool = False`-Parameter; `_FIXTURE_DIR`-Konstante; FixtureProvider-Weiche

- **File:** `api/routers/preview.py`
  - **Identifier:** alle 4 Endpoint-Funktionen (email, sms, signal, telegram) — `demo: bool = Query(False)`

### Patch Frontend

- **File:** `frontend/src/lib/components/preview/previewHelpers.ts`
  - **Identifier:** `buildPreviewUrl` — optionaler `demo?: boolean` Parameter

- **File:** `frontend/src/lib/components/preview/EmailIframe.svelte`
  - **Identifier:** `<EmailIframe>` — `demo?: boolean` Prop

- **File:** `frontend/src/lib/components/preview/SmsPhoneFrame.svelte`
  - **Identifier:** `<SmsPhoneFrame>` — `demo?: boolean` Prop

- **File:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
  - **Identifier:** Vorschau-Tab-Block — `demoMode = $state(true)`, Demo-Banner, Button "Echte Wetterdaten laden"

### Neu (Tests)

- **File:** `tests/tdd/test_epic_140_preview_endpoints.py`
  - **Identifier:** `TestT6DemoMode` — neue Testklasse, echte Endpoints mit `?demo=1`

- **File:** `frontend/src/lib/components/preview/__tests__/previewHelpers.test.ts`
  - **Identifier:** `buildPreviewUrl` mit `demo=true`

## Estimated Scope

- **LoC:** ~120 netto
- **Files:** 9 (7 Produktion + 2 Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `FixtureProvider` | bestehender Provider (`src/providers/fixture.py`) | Liefert Wetterdaten aus lokalen JSON-Fixtures statt Live-API; instanziert mit `_FIXTURE_DIR` |
| `_FIXTURE_DIR` | Konstante (neu in `preview_service.py`) | `Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"` — relativ zur Datei, kein ENV nötig |
| `TripReportSchedulerService._fetch_weather` | bestehende Methode | Wird um optionalen `provider`-Parameter erweitert; Demo-Pfad injiziert FixtureProvider |
| `GET /api/preview/{trip_id}/email` | bestehender Endpoint | Bekommt `?demo=1` Query-Parameter |
| `GET /api/preview/{trip_id}/sms` | bestehender Endpoint | Bekommt `?demo=1` Query-Parameter |
| `GET /api/preview/{trip_id}/signal` | bestehender Endpoint | Bekommt `?demo=1` Query-Parameter |
| `GET /api/preview/{trip_id}/telegram` | bestehender Endpoint | Bekommt `?demo=1` Query-Parameter |
| `buildPreviewUrl` | bestehende Pure-Function (`previewHelpers.ts`) | Erweitert um optionalen `demo?: boolean`; hängt `?demo=1` an URL wenn `true` |
| `EmailIframe.svelte` | bestehende Komponente | Bekommt `demo` Prop, reicht an `buildPreviewUrl` weiter |
| `SmsPhoneFrame.svelte` | bestehende Komponente | Bekommt `demo` Prop, reicht an `buildPreviewUrl` weiter |
| `TripTabs.svelte` | bestehende Komponente | Hält `demoMode`-State, zeigt Demo-Banner + Umschalt-Button |

## Implementation Details

### 1. `trip_report_scheduler.py` — Provider-Injection

```python
def _fetch_weather(self, segments, provider=None):
    """Holt Wetterdaten. Optional: provider-Instanz injizieren (Demo-Modus)."""
    if provider is None:
        provider = get_provider(self.settings)
    # restlicher Code unverändert — provider statt get_provider()-Aufruf
```

Rückwärtskompatibel: alle bestehenden Aufrufe ohne Argument verhalten sich wie bisher.

### 2. `preview_service.py` — FixtureProvider-Weiche

```python
from pathlib import Path

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"

class PreviewService:
    def _build_report(self, trip, target, report_type, demo: bool = False):
        from services.trip_report_scheduler import TripReportSchedulerService
        from providers.fixture import FixtureProvider

        scheduler = TripReportSchedulerService(self.settings)
        segments = scheduler._convert_trip_to_segments(trip, target)
        if not segments:
            raise LookupError(...)

        provider = FixtureProvider(_FIXTURE_DIR) if demo else None
        segment_weather = scheduler._fetch_weather(segments, provider=provider)
        ...

    def render_email_preview(self, trip_id, *, user_id, report_type, target_date, demo=False):
        ...
        report, *_ = self._build_report(trip, target, report_type, demo=demo)
        return report.email_html

    def render_sms_preview(self, trip_id, *, user_id, report_type, target_date, demo=False):
        ...
        report, segment_weather, stage_name, trip_tz = self._build_report(
            trip, target, report_type, demo=demo
        )
        ...
```

Gleiche Erweiterung für `render_signal_preview` und `render_telegram_preview`, falls vorhanden.

### 3. `api/routers/preview.py` — Query-Parameter

```python
from fastapi import Query

@router.get("/{trip_id}/email")
async def preview_email(
    trip_id: str,
    type: str = "morning",
    date: str | None = None,
    demo: bool = Query(False),
    ...
):
    html = service.render_email_preview(
        trip_id, ..., demo=demo
    )
    return HTMLResponse(html)
```

Analoges Muster für `/sms`, `/signal`, `/telegram`.

### 4. `previewHelpers.ts` — Demo-Parameter

```ts
export function buildPreviewUrl(
  channel: 'email' | 'sms' | 'signal' | 'telegram',
  tripId: string,
  type: ReportType,
  date?: string,
  demo?: boolean,
): string {
  const qs = new URLSearchParams({ type });
  if (date) qs.set('date', date);
  if (demo) qs.set('demo', '1');
  return `/api/preview/${encodeURIComponent(tripId)}/${channel}?${qs.toString()}`;
}
```

### 5. `EmailIframe.svelte` + `SmsPhoneFrame.svelte` — Demo-Prop

Beide Komponenten bekommen `demo?: boolean = false` als Prop und reichen ihn an `buildPreviewUrl` weiter. Kein weiteres UI-Verhalten in diesen Komponenten.

### 6. `TripTabs.svelte` — Demo-State + Banner

```svelte
<script>
  let demoMode = $state(true);
</script>

{#if tab.value === 'preview' && trip}
  <div class="preview-shell">
    {#if demoMode}
      <div class="demo-banner" role="status">
        Vorschau mit Beispieldaten.
        <button onclick={() => (demoMode = false)}>Echte Wetterdaten laden</button>
      </div>
    {/if}
    <div class="preview-controls">
      <!-- Morning/Evening-Radio unverändert -->
    </div>
    <div class="preview-grid">
      <EmailIframe tripId={trip.id} type={previewType} demo={demoMode} />
      <SmsPhoneFrame tripId={trip.id} type={previewType} demo={demoMode} />
    </div>
  </div>
{/if}
```

Wenn `demoMode` auf `false` wechselt, ergibt die reaktive Bindung automatisch einen neuen Fetch mit `demo=false` (Live-Daten).

### 7. Tests

**Backend (`TestT6DemoMode`):**
- Echte Endpoints (kein Mock), `?demo=1`
- Prüft: HTTP 200, Response-Body enthält Trip-Name
- Setzt voraus: Fixture-Dateien in `fixtures/openmeteo/` vorhanden

**Frontend (`previewHelpers.test.ts`):**
- Pure-Function-Test: `buildPreviewUrl('email', 'gr20', 'morning', undefined, true)` → URL enthält `demo=1`
- Pure-Function-Test: `buildPreviewUrl('email', 'gr20', 'morning')` → URL enthält KEIN `demo=`

## Expected Behavior

- **Input:** Vorschau-Tab wird geöffnet. `demoMode` startet als `true`.
- **Output:** Beide Vorschau-Komponenten laden sofort mit Fixture-Daten; Demo-Banner sichtbar. Nach Klick auf "Echte Wetterdaten laden" wechselt `demoMode` auf `false`, beide Komponenten fetchen erneut mit Live-Wetter.
- **Side effects:** Kein Versand, kein Logbuch-Eintrag. Provider-Injection ist thread-safe (Instanz wird lokal erzeugt, nicht global gesetzt).

## Acceptance Criteria

- **AC-1:** Given Trip-Detail-Ansicht mit gültigem Trip / When der Tab "Vorschau" zum ersten Mal aktiv wird / Then ist `demoMode = true`, beide Komponenten senden `?demo=1` an den Backend-Endpoint, und der Demo-Banner ist sichtbar.

- **AC-2:** Given Demo-Banner ist sichtbar / When der User auf "Echte Wetterdaten laden" klickt / Then wechselt `demoMode` auf `false`, der Banner verschwindet, und beide Komponenten führen einen neuen Fetch ohne `?demo=1` durch.

- **AC-3:** Given `GET /api/preview/{trip_id}/email?demo=1` mit gültigem Auth-Cookie und Trip / When der Endpoint aufgerufen wird / Then antwortet er HTTP 200 mit HTML, das den Trip-Namen enthält — unabhängig davon ob der Trip in der Vergangenheit liegt oder OpenMeteo nicht erreichbar ist.

- **AC-4:** Given `buildPreviewUrl('email', 'gr20', 'morning', undefined, true)` / When die Funktion aufgerufen wird / Then enthält die zurückgegebene URL den Query-Parameter `demo=1` und keinen leeren `demo=`-Eintrag.

- **AC-5:** Given `buildPreviewUrl('sms', 'gr20', 'evening')` ohne demo-Argument / When die Funktion aufgerufen wird / Then enthält die zurückgegebene URL keinen `demo`-Parameter.

- **AC-6:** Given Vorschau-Tab ohne Demo-Modus (nach Klick auf "Echte Wetterdaten laden") / When der Endpoint mit `?demo=0` oder ohne `demo`-Parameter aufgerufen wird / Then ist das Verhalten identisch zum bisherigen Stand — alle bestehenden Endpoint-Tests bleiben grün.

## Known Limitations

- **Signal/Telegram Endpoints:** Wenn `render_signal_preview` oder `render_telegram_preview` in `preview_service.py` noch nicht existieren, wird der `demo`-Parameter nur für Email und SMS wirksam. Der Query-Parameter in den Endpunkten ist trotzdem vorhanden (schadet nicht).
- **Fixture-Vollständigkeit:** Der FixtureProvider liefert nur Daten, die in `fixtures/openmeteo/` abgelegt sind. Fehlt eine Fixture-Datei für einen bestimmten Koordinatenbereich, kann der Demo-Modus ebenfalls einen Fehler werfen. Das ist ein bekanntes Verhalten des FixtureProviders (Issue #263) und kein neuer Bug.
- **Kein Caching zwischen Demo und Live:** Der Wechsel von `demoMode = true` zu `false` triggert immer einen vollen neuen Fetch. Ein clientseitiger Cache ist nicht Teil dieses Workflows.

## Changelog

- 2026-05-31: Initial spec — Demo-Modus für Vorschau-Tab (Issue #483)
