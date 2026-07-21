---
entity_id: issue_514_compare_vorschau_tab
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [frontend, compare, preview, svelte]
---

# Compare-Vorschau-Tab: Echte E-Mail-Vorschau (Issue #514)

## Approval

- [ ] Approved

## Purpose

Den Platzhaltertext im „Vorschau"-Tab von `/compare/[id]` durch eine echte E-Mail-Vorschau
ersetzen. Beide Backend-Endpoints sind vorhanden. Das Design folgt dem kanonischen
`HubPreview`-Muster aus `screen-trip-detail.jsx` (Design-Referenz: `docs/design-requests/
orts-vergleich/gregor-zwanzig/project/`).

## Source

- **Hauptdatei:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Tests:** `frontend/src/lib/components/compare/__tests__/issue_517_compare_tabs.test.ts`

## Estimated Scope

- **LoC:** ~90 (80 CompareTabs.svelte + 10 Testdatei)
- **Files:** 2
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/_validator/compare-email-preview` | aufgerufen | Rendert Compare-E-Mail HTML (Go-Proxy → Python); Input: `{profile, time_window, target_date, winner_tags}`; Output: `{html: string}` |
| `POST /api/compare/presets/{id}/send` | aufgerufen | Löst Test-Briefing aus (Stub); Output: `{status: "queued"}` |
| `$lib/api::api.post` | importiert | Standard-Fetch-Wrapper; wirft bei non-ok; generisch typisierbar |
| `$lib/components/atoms::Segmented` | bereits importiert | Kanal-Umschalter; Props: `options`, `selected`, `onselect` |
| `$lib/types::ComparePreset` | konsumiert | Felder: `id`, `profil`, `hour_from`, `hour_to` |
| `screen-trip-detail.jsx::HubPreview` | Referenz | Kanonische Design-Vorlage für Vorschau-Tab-Layout |

## Design Reference

Quelle: `docs/design-requests/orts-vergleich/gregor-zwanzig/project/screen-trip-detail.jsx`,
Funktion `HubPreview` (Zeilen 166–185).

**Layout-Struktur:**

```
┌── Header-Zeile ──────────────────────────────────────────────────────────┐
│ EYEBROW: Vorschau · Verifikation                [Email][SMS / Signal]     │
│ H2: So sieht dein nächstes Briefing aus                                  │
│ Untertitel (--g-ink-3)                  MONO: Beispielwerte · kein Wetter │
└──────────────────────────────────────────────────────────────────────────┘
┌── Preview-Fläche ─────────────────────────────────────────────────────────┐
│  background: #e9e6dc  border-radius: var(--g-r-3)  border: 1px solid rule │
│  display:flex; justify-content:center; padding:24px                        │
│    ┌──────────────────────┐  width: 680px (Email)                          │
│    │  <iframe srcdoc>     │       oder 380px (SMS deaktiviert)             │
│    └──────────────────────┘                                                │
└───────────────────────────────────────────────────────────────────────────┘
   [Test-Briefing jetzt senden]  ← Btn variant="quiet", volle Breite, mt-4
   [Feedback-Zeile: Erfolg / Fehler]
```

## Implementation Details

### Zustandsvariablen (in `<script>`)

```typescript
import { api } from '$lib/api.js';

// Vorschau-Kanal
let previewChannel = $state<'email' | 'sms'>('email');

// Preview-Lade-Zustand
let previewHtml  = $state('');
let previewLoading = $state(false);
let previewError = $state<string | null>(null);

// Send-Zustand
let sendQueued  = $state(false);
let sendLoading = $state(false);
let sendError   = $state<string | null>(null);
```

### Auto-Load (`$effect`)

```typescript
$effect(() => {
    if (activeTab !== 'vorschau') return;
    // Reset bei erneutem Tab-Öffnen
    previewHtml = '';
    previewError = null;
    previewLoading = true;
    const controller = new AbortController();
    api.post<{ html: string }>(
        '/api/_validator/compare-email-preview',
        {
            profile: preset.profil,
            time_window: [preset.hour_from, preset.hour_to],
            target_date: new Date().toISOString().slice(0, 10),
            winner_tags: []
        }
    ).then(r => {
        previewHtml = r.html;
    }).catch((e: unknown) => {
        previewError =
            e && typeof e === 'object' && 'error' in e
                ? String((e as { error: unknown }).error)
                : e instanceof Error ? e.message
                : 'Vorschau konnte nicht geladen werden';
    }).finally(() => {
        previewLoading = false;
    });
    return () => controller.abort();
});
```

### Kanal-Umschalter-Optionen

```typescript
const PREVIEW_CHANNELS = [
    { value: 'email', label: 'Email' },
    { value: 'sms',   label: 'SMS / Signal' },
];
```

### Send-Funktion

```typescript
async function handleSend() {
    if (sendLoading) return;
    sendLoading = true;
    sendError = null;
    sendQueued = false;
    try {
        await api.post(`/api/compare/presets/${preset.id}/send`, {});
        sendQueued = true;
    } catch (e: unknown) {
        const body = e as { detail?: string; error?: string };
        sendError = body?.detail ?? body?.error ?? 'Versand fehlgeschlagen';
    } finally {
        sendLoading = false;
    }
}
```

### Template (ersetzt Zeilen 203–211 in CompareTabs.svelte)

```svelte
{#if activeTab === 'vorschau'}
<div class="tab-panel" data-testid="compare-detail-panel-vorschau">

  <!-- Header-Zeile: Eyebrow + H2 + Untertitel | Kanal-Umschalter + Disclaimer -->
  <div class="preview-header">
    <div class="preview-header-text">
      <Eyebrow>Vorschau · Verifikation</Eyebrow>
      <h2 class="preview-title">So sieht dein nächstes Briefing aus</h2>
      <p class="preview-subtitle">
        Pixel-Vorschau zum Gegencheck deiner Konfiguration.
        Gelesen wird das echte Briefing im jeweiligen Kanal.
      </p>
    </div>
    <div class="preview-header-right">
      <Segmented
        options={PREVIEW_CHANNELS}
        selected={previewChannel}
        onselect={(v) => previewChannel = v}
      />
      <span class="preview-disclaimer">Beispielwerte · kein Live-Wetter</span>
    </div>
  </div>

  <!-- Preview-Fläche -->
  <div class="preview-stage">
    {#if previewLoading}
      <p class="preview-loading" data-testid="compare-preview-loading">
        Vorschau wird geladen…
      </p>
    {:else if previewError}
      <p class="preview-error" data-testid="compare-preview-error">{previewError}</p>
    {:else if previewHtml}
      <div style="width: {previewChannel === 'email' ? '680px' : '380px'}">
        <iframe
          data-testid="compare-preview-iframe"
          srcdoc={previewHtml}
          sandbox="allow-same-origin"
          title="E-Mail-Vorschau"
        ></iframe>
      </div>
    {/if}
    {#if previewChannel === 'sms'}
      <p class="preview-sms-hint" data-testid="compare-preview-sms-hint">
        SMS/Signal-Vorschau ist noch nicht verfügbar.
      </p>
    {/if}
  </div>

  <!-- Test-Briefing senden -->
  <div class="preview-send">
    {#if sendQueued}
      <p class="send-success" data-testid="compare-send-success">
        Briefing wurde zur Zustellung vorgemerkt.
      </p>
    {:else}
      <Btn
        variant="quiet"
        disabled={sendLoading}
        onclick={handleSend}
        data-testid="compare-send-btn"
      >
        {sendLoading ? 'Wird gesendet…' : 'Test-Briefing jetzt senden'}
      </Btn>
    {/if}
    {#if sendError}
      <p class="send-error" data-testid="compare-send-error">{sendError}</p>
    {/if}
  </div>

</div>
{/if}
```

### CSS-Ergänzungen

```css
.preview-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 24px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}
.preview-header-text { max-width: 680px; }
.preview-title {
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin: 6px 0 6px;
    color: var(--g-ink);
}
.preview-subtitle {
    font-size: 0.84375rem;
    color: var(--g-ink-3);
    line-height: 1.5;
    margin: 0;
}
.preview-header-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    flex-shrink: 0;
}
.preview-disclaimer {
    font-family: var(--g-font-mono);
    font-size: 0.625rem;
    color: var(--g-ink-4);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.preview-stage {
    display: flex;
    justify-content: center;
    padding: 24px;
    background: #e9e6dc;
    border-radius: var(--g-r-3, 0.75rem);
    border: 1px solid var(--g-rule, #d8d3c7);
    margin-bottom: 1rem;
    min-height: 120px;
    flex-direction: column;
    align-items: center;
}
.preview-stage iframe {
    width: 100%;
    min-height: 500px;
    border: 0;
    display: block;
}
.preview-loading {
    font-size: 0.875rem;
    color: var(--g-ink-3);
    margin: 0;
}
.preview-error { font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0; }
.preview-sms-hint { font-size: 0.875rem; color: var(--g-ink-3); margin: 0.5rem 0 0; font-style: italic; }
.preview-send { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-start; }
.send-success { font-size: 0.875rem; color: var(--g-good, #16a34a); margin: 0; }
.send-error   { font-size: 0.875rem; color: var(--g-danger, #dc2626); margin: 0; }

@media (max-width: 899px) {
    .preview-header { flex-direction: column; align-items: flex-start; }
    .preview-header-right { align-items: flex-start; }
    .preview-stage { padding: 12px; }
}
```

## Acceptance Criteria

**AC-1:** Given der Nutzer öffnet `/compare/[id]?tab=vorschau`, When der Tab geladen ist, Then startet automatisch ein Lade-Vorgang gegen `POST /api/_validator/compare-email-preview` — kein manueller Button nötig. (`data-testid="compare-preview-loading"` sichtbar während des Ladens)

**AC-2:** Given der Vorschau-Request ist erfolgreich, When das HTML zurückkommt, Then wird es in einem `<iframe srcdoc=… sandbox="allow-same-origin">` mit `data-testid="compare-preview-iframe"` angezeigt, zentriert auf warmem Grau-Hintergrund (`#e9e6dc`).

**AC-3:** Given der Vorschau-Tab aktiv ist, When das Layout gerendert wird, Then ist `Eyebrow` „Vorschau · Verifikation" und `h2` „So sieht dein nächstes Briefing aus" sichtbar.

**AC-4:** Given der Vorschau-Tab aktiv ist, When das Layout gerendert wird, Then ist ein `Segmented`-Umschalter mit den Optionen „Email" und „SMS / Signal" sichtbar.

**AC-5:** Given der Nutzer klickt „Test-Briefing jetzt senden" (`data-testid="compare-send-btn"`), When der Request erfolgreich ist, Then erscheint `data-testid="compare-send-success"` mit Text „Briefing wurde zur Zustellung vorgemerkt." — der Button verschwindet.

**AC-6:** Given die Preview-API einen Fehler zurückgibt, When der Tab geladen wird, Then zeigt `data-testid="compare-preview-error"` eine deutsche Fehlermeldung.

**AC-7:** Given der Nutzer wählt „SMS / Signal" im Kanal-Umschalter, When der Tab neu rendert, Then wird `data-testid="compare-preview-sms-hint"` angezeigt (kein iframe für SMS — kein Backend-Endpoint).

**AC-8:** Given `CompareTabs.svelte`, When der Source-Text geprüft wird, Then enthält er: `/api/_validator/compare-email-preview`, `srcdoc`, `sandbox`, `/api/compare/presets/` und `/send`, `Vorschau · Verifikation`, `#e9e6dc`. — Nicht mehr enthalten: `CompareEmail implementiert ist`.

## Test-Anpassungen (`issue_517_compare_tabs.test.ts`)

Das bestehende AC-8-describe-Block muss aktualisiert werden:

**Entfernen:**
```typescript
test("Placeholder-Text 'CompareEmail implementiert ist' vorhanden", ...)
```

**Ersetzen durch (3 neue Tests):**
```typescript
test("Source enthält Preview-Endpoint", () =>
    assert.ok(getSrc().includes('/api/_validator/compare-email-preview'), ...));
test("Source enthält iframe srcdoc + sandbox", () =>
    assert.ok(getSrc().includes('srcdoc') && getSrc().includes('sandbox'), ...));
test("Source enthält Send-Endpoint", () =>
    assert.ok(getSrc().includes('/api/compare/presets/') && getSrc().includes('/send'), ...));
test("Source enthält Design-Heading", () =>
    assert.ok(getSrc().includes('Vorschau · Verifikation'), ...));
```

**Bestehende Tests die bestehen bleiben:**
- `'Postfach gelesen'` → entfällt als Substring, muss angepasst werden zu `'jeweiligen Kanal'`
- `'Test-Briefing senden'` → bleibt Substring von „Test-Briefing jetzt senden" ✓

## Out of Scope

- SMS/Signal-Preview-Rendering (kein Backend-Endpoint)
- Kanal-Constraint-Logik (Spaltenanzahl pro Kanal)
- Echter Versand (Send-Endpoint ist Stub)
- Echte Wetterdaten in der Vorschau (Python-Endpoint nutzt Stub-Daten)
