---
entity_id: issue_421_preview_error_message
type: bugfix
created: 2026-05-27
updated: 2026-05-27
status: done
version: "1.0"
tags: [frontend, ux, preview, i18n, error-handling]
---

# Issue #421 — Vorschau-Fehlermeldung benutzerfreundlich auf Deutsch

## Approval

- [x] Approved (2026-05-27)

## Purpose

Der Trip-Detail Vorschau-Tab (E-Mail + SMS) hängt bei Backend-Fehlern den rohen
HTTP-Statuscode und JSON-Body unverändert an die UI-Meldung — z. B.
`Vorschau konnte nicht geladen werden (HTTP 422). {"detail":"Stage must have at
least one waypoint"}`. Dieser englische technische Rohtext ist für Endnutzer
unverständlich und nicht actionable. Eine zentrale Übersetzungsfunktion ersetzt
ihn durch verständliches, handlungsleitendes Deutsch.

Quelle: SOLL-IST-Audit #404 Phase 3, Finding **M-07**.

## Source

- **File (neu):** `frontend/src/lib/components/preview/previewHelpers.ts`
- **Identifier (neu):** `friendlyPreviewError(status: number, body: string): string` + Konstanten `PREVIEW_ERROR_GENERIC`, `PREVIEW_ERROR_NO_WAYPOINTS`
- **File (geändert):** `frontend/src/lib/components/preview/EmailIframe.svelte` (Z. 18–21 `!res.ok`-Zweig, Z. 25–29 `catch`-Zweig)
- **File (geändert):** `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` (Z. 24–28 `!res.ok`-Zweig, Z. 31–35 `catch`-Zweig)

Schicht: **Frontend / SvelteKit** (produktive Oberfläche). Kein Backend-/Go-Touch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/preview/EmailIframe.svelte` | Verwender | E-Mail-Vorschau-Frame, ruft Funktion in `!res.ok` + `catch` auf |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | Verwender | SMS-Vorschau-Frame, identisches Aufruf-Muster |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Kontext | Einbettung beider Frames im Vorschau-Tab (Z. 126–127) — unverändert |
| `api/routers/preview.py` | Upstream | Liefert Statuscodes 404/422/503; FastAPI serialisiert `detail` als JSON-String |
| `internal/handler/preview_proxy.go` | Upstream | Reicht Status + Body verbatim durch; 502 bei „upstream unreachable" |

## Implementation Details

### Neue Pure-Function in `previewHelpers.ts`

```ts
export const PREVIEW_ERROR_GENERIC =
  'Vorschau konnte nicht geladen werden. Bitte später erneut versuchen.';
export const PREVIEW_ERROR_NO_WAYPOINTS =
  'Diese Etappe hat noch keine Wegpunkte. Bitte im Wegpunkt-Editor ' +
  'mindestens einen Start- und Zielpunkt festlegen.';

// Übersetzt einen HTTP-Fehler der Vorschau-Endpoints in verständliches Deutsch.
// Schlüsselt auf den inhaltlichen Signal-Text (detail enthält "waypoint"),
// nicht auf den numerischen Code — resilient gegen Status-Drift im Backend.
// Parst body defensiv als JSON; wirft niemals.
export function friendlyPreviewError(status: number, body: string): string {
  let detail = '';
  try {
    const parsed = JSON.parse(body);
    if (parsed && typeof parsed.detail === 'string') detail = parsed.detail;
  } catch {
    detail = body ?? '';
  }
  if (/waypoint/i.test(detail)) return PREVIEW_ERROR_NO_WAYPOINTS;
  return PREVIEW_ERROR_GENERIC;
}
```

### Verkabelung in beiden Frames (identisch)

```ts
// Vorher (Bug — roher Statuscode + JSON-Body):
const detail = await res.text();
error = `Vorschau konnte nicht geladen werden (HTTP ${res.status}). ${detail}`;

// Nachher:
error = friendlyPreviewError(res.status, await res.text());
```

```ts
// catch-Zweig — vorher: `Netzwerkfehler: ${msg}` → nachher: generische Meldung.
// AbortError-Early-Return bleibt unverändert (kein Fehler bei absichtlichem Abbruch).
}).catch((err: unknown) => {
  if (err instanceof Error && err.name === 'AbortError') return;
  error = PREVIEW_ERROR_GENERIC;
  loading = false;
});
```

Import in beiden Komponenten um `friendlyPreviewError, PREVIEW_ERROR_GENERIC` erweitert.

## Expected Behavior

- **Input:** HTTP-Antwort eines Vorschau-Endpoints (`status` + roher `body`) oder ein Netzwerk-/Abbruch-Fehler.
- **Output:** Verständliche deutsche Klartext-Meldung im Fehler-`<p>` der jeweiligen Vorschau.
- **Side effects:** Keine. Reine String-Transformation; Markup, Lade-/Fehler-State und AbortController-Logik unverändert.

## Acceptance Criteria

**AC-1:** Given die Backend-Antwort `status=422` mit Body `{"detail":"Stage must have at least one waypoint"}` / When `friendlyPreviewError(status, body)` aufgerufen wird / Then liefert sie exakt `PREVIEW_ERROR_NO_WAYPOINTS` (Wegpunkt-Hinweis auf Deutsch, mit Aufforderung zum Wegpunkt-Editor).
- Test: (populated after /tdd-red)

**AC-2:** Given ein beliebiger anderer Fehler-Body (z. B. `status=503` „weather provider down", `status=404` „trip not found", leerer Body oder Plain-Text ohne „waypoint") / When `friendlyPreviewError(status, body)` aufgerufen wird / Then liefert sie exakt `PREVIEW_ERROR_GENERIC` und das Ergebnis enthält weder eine HTTP-Statuszahl noch die JSON-Zeichen `{` oder `}`.
- Test: (populated after /tdd-red)

**AC-3:** Given ein nicht-JSON-parsbarer oder leerer Body (`''`, `'<<<kaputt'`, `undefined`-artiger Roh-String mit „waypoint" als reiner Text) / When `friendlyPreviewError` aufgerufen wird / Then wirft sie nie und matcht „waypoint" auch im Roh-String (Fallback) → Wegpunkt-Hinweis, sonst generische Meldung.
- Test: (populated after /tdd-red)

**AC-4:** Given die Dateien `EmailIframe.svelte` und `SmsPhoneFrame.svelte` nach dem Fix / When ihr Quelltext per Source-Inspection geprüft wird / Then enthält keine der beiden mehr die rohe Konkatenation `HTTP ${res.status}` oder `${detail}` oder `Netzwerkfehler:`, beide importieren und verwenden `friendlyPreviewError`, und der `AbortError`-Early-Return im `catch`-Zweig bleibt erhalten.
- Test: (populated after /tdd-red)

## Known Limitations

- Die Erkennung „leere Wegpunkte" schlüsselt auf das Substring `waypoint` (case-insensitive) im `detail`-Feld — bewusst inhaltlich statt auf Statuscode 422, um robust gegen Backend-Status-Drift zu sein. Ändert das Backend den englischen Wortlaut grundlegend (kein „waypoint" mehr), fällt die Meldung auf den generischen Text zurück (kein Crash, nur weniger spezifisch).
- FastAPI-Request-Validierungsfehler (z. B. fehlende Query-Parameter) liefern `detail` als Array statt String → wird als generischer Fehler behandelt (kein „waypoint"-Match). Aus dem UI-Pfad nicht auslösbar, da `type` kontrolliert ist.
- Signal-/Telegram-Vorschau laufen nicht über diese beiden Frames (nur E-Mail + SMS im Tab) und sind nicht im Scope.

## Changelog

- 2026-05-27: Implementiert (3 Dateien), 33/33 Tests grün, Adversary VERIFIED, Doku aktualisiert
- 2026-05-27: Spec erstellt (Issue #421)
