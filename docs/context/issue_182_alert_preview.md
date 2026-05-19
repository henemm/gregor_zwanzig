# Context: Issue #182 — Alert-Preview (Email)

## Request Summary

Im Alerts-Tab (`/trips/[id]#alerts`) soll eine visuelle Vorschau erscheinen,
wie eine Alert-E-Mail tatsächlich aussehen würde. Die Vorschau zeigt einen
Email-Ausschnitt mit Δ-Bullet-Liste (Änderungen) + kompakter Tabelle
(nur geänderte Etappen). Teil von Epic #139 (Alert-Konfigurator).

## Status der Vorarbeiten

| Issue | Status | Was gebaut wurde |
|-------|--------|-----------------|
| #180 | Abgeschlossen | `AlertMetricTable.svelte` (9 Metriken, Toggle + Inputs) |
| #181 | Abgeschlossen | `AlertCooldownCard.svelte` + `AlertQuietHoursCard.svelte` |
| #221 | Abgeschlossen | `POST /api/trips/{id}/alert-preview` Backend-Endpoint (vollständiger Email-Renderer) |
| #222 W1/W2 | Abgeschlossen | Python `TripAlertService` + Frontend `AlertsPreviewCard` |

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Container — hier wird die Preview eingebaut |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | Existierender Block (oben im Tab) |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Existierender Block (Mitte) |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Existierender Block (Mitte) |
| `frontend/src/lib/components/preview/EmailIframe.svelte` | Referenz-Pattern für iframe-Rendering von Backend-HTML |
| `frontend/src/lib/components/preview/previewHelpers.ts` | URL-Builder-Pattern |
| `api/routers/validator.py` | Backend `POST /api/trips/{id}/alert-preview` (Payload → HTML+Plain) |
| `internal/handler/proxy.go` | `AlertPreviewProxyHandler` (Z. 221–260) — Go-Proxy bereits implementiert |
| `cmd/server/main.go` | Route Z. 111: `r.Post("/api/trips/{id}/alert-preview", ...)` |
| `frontend/src/lib/types.ts` | `AlertRule`, `Trip` TypeScript-Typen |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Label/Unit-Mapping je AlertMetric |

## Backend-Endpoint

`POST /api/trips/{id}/alert-preview`

Payload:
```json
{
  "changes": [
    {
      "metric": "wind_gust",
      "old_value": 45, "new_value": 78, "delta": 33,
      "threshold": 60, "severity": "warning",
      "direction": "increase", "segment_id": "1"
    }
  ],
  "segment_times": [
    { "segment_id": "1", "start": "08:00", "end": "12:00" }
  ]
}
```

Response: `{ "html": "...", "plain": "..." }`

Der Endpoint ist auth-geschützt (Cookie), kein user_id im Frontend nötig
(Go-Proxy injiziert ihn). Seiteneffektfrei (kein SMTP, kein Throttle).

## Existierende Patterns

### EmailIframe.svelte
- Fetcht per `$effect` bei Prop-Änderung
- Zeigt Loading/Error/iframe
- Nutzt `buildPreviewUrl()` für URL-Konstruktion

### AlertsTab.svelte (aktueller Aufbau)
1. `<AlertMetricTable />` (bind:alert_rules)
2. `<div class="cards-row">` mit CooldownCard + QuietHoursCard
3. `<div class="actions">` mit Speichern-Button + Feedback

## Analyse-Ergebnis: Implementierungsstrategie

### Metric-Name-Mapping (kritisch)

`ChangePayload.metric` erwartet Python-Wetter-Feldnamen, NICHT die TypeScript-AlertMetric-Namen.
Mapping aus `src/services/weather_change_detection.py`:

**Absolute-Regeln** (`_ALERT_METRIC_TO_SUMMARY_FIELD`):
```
wind_gust          → "gust_max_kmh"     / direction: "above"
precipitation_sum  → "precip_sum_mm"    / direction: "above"
temperature_min    → "temp_min_c"       / direction: "below"
temperature_max    → "temp_max_c"       / direction: "above"
thunder_level      → "thunder_level_max"/ direction: "above"
snow_line          → "freezing_level_m" / direction: "above"
```

**Delta-Regeln** (`_ALERT_DELTA_METRIC_TO_FIELDS`, erstes Feld der Tuple):
```
temperature_change → "temp_min_c"       / direction: "increase"
wind_change        → "wind_max_kmh"     / direction: "increase"
precipitation_change → "precip_sum_mm"  / direction: "increase"
```

Severity-Mapping: `info→"minor"`, `warning→"moderate"`, `critical→"major"`

### Synthetische Demo-Änderungen

Pro aktivierter AlertRule:
- `new_value = threshold * 1.2` (20% über Schwelle)
- `old_value` = für absolute-rules: `threshold * 0.8`; für delta-rules: `0`
- `delta = new_value - old_value`
- `segment_id = stages[0]?.id ?? "1"` (alle Changes auf erstem Segment)
- `segment_times`: `{ start: "08:00", end: "17:00" }` (Stub-Zeiten)

### Scope (final)

| Datei | Aktion | LoC |
|-------|--------|-----|
| `alerts-tab/AlertPreviewCard.svelte` | NEU | ~105 |
| `alerts-tab/AlertsTab.svelte` | +Import +1 Tag | +5 |
| **Total** | 2 Dateien | ~110 |

### Trigger

Expliziter Button-Klick ("Vorschau laden"). Kein Auto-Load.
Button disabled wenn keine aktiven Regeln vorhanden.

## Abhängigkeiten

- Upstream: `AlertsTab` (Props: `trip: Trip`)
- Downstream: keine (nur Display)
- Backend: Endpoint existiert

## Risiken & Überlegungen

1. **Trip ohne Stages**: Das Backend braucht `segment_times` — Trip-Stages kommen
   aus `trip.stages`. Falls leer: leere Array → Backend-Stub fängt das ab
   (`validator-stub`-Segment wird intern generiert).

2. **Segment-Zeit-Mapping**: Trip-Stages haben kein `start_time`/`end_time` direkt
   im Frontend-Typ — nur `date`. Stub-Zeiten "08:00"/"18:00" sind akzeptabel
   für Vorschau-Zwecke.

3. **Loading-State**: Der iframe-Ansatz braucht einen `POST`-Call (nicht GET) —
   `EmailIframe.svelte` nutzt `fetch()` direkt, nicht `<iframe src="...">`.
   Derselbe `fetch`-Ansatz funktioniert für POST.

4. **Wann neu laden?**: Die Preview soll nach dem Speichern der Regeln aktualisiert
   werden. Lösungsansatz: ein `$derived`-Key aus den gespeicherten `alertRules`
   triggert `$effect`.
