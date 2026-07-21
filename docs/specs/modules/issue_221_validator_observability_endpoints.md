---
entity_id: issue_221_validator_observability_endpoints
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [validator, api, observability, tooling, alerts]
---

# Validator Observability Endpoints (Issue #221)

## Approval

- [ ] Approved

## Purpose

Drei cookie-geschützte Read-/Render-Endpoints für den External Validator
(Issue #110), damit interne Python-Funktionen rund um Alert-Mail-Format,
Detector-Auswahl und Metric-Formatierung von außen prüfbar werden. Behebt
das strukturelle Validator-Loch, das Issue #131 als AMBIGUOUS markiert hat
(8 von 9 ACs ohne API-Sichtbarkeit, siehe
`docs/artifacts/issue_131_alert_email_klarheit/validator-report.md`).

Die Endpoints sind explizit Tooling-/Observability-API, nicht versionsstabil
und nicht für Frontend/Endbenutzer.

## Source

- **File:** `api/routers/validator.py` (NEU), `api/main.py`,
  `internal/handler/proxy.go`, `cmd/server/main.go`
- **Identifier:**
  - Python: `format_metric` (Endpoint #1), `alert_preview` (Endpoint #2),
    `detector_thresholds` (Endpoint #3)
  - Go: `ValidatorFormatMetricProxyHandler`, `AlertPreviewProxyHandler`,
    `DetectorThresholdsProxyHandler`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.app.metric_catalog.format_metric_value` | aufgerufen | Pure-Function-Wrapper für Endpoint #1 (Issue #131 AC-4/5/6 prüfbar). |
| `src.formatters.trip_report.TripReportFormatter.format_email` | aufgerufen | SSoT-Renderer für Endpoint #2 (`report_type="alert"`, `changes=…`). |
| `src.services.trip_alert.TripAlertService._select_change_detector` | aufgerufen | Kanonische Detector-Auswahllogik für Endpoint #3 (alert_rules > display_config > report_config > defaults). |
| `src.services.weather_change_detection.WeatherChangeDetectionService` | konsumiert | Endpoint #3 liest `_thresholds`-Dict des gewählten Detectors. |
| `src.app.loader._parse_trip` + `get_trips_dir` | aufgerufen | User-scoped Trip-Lookup für Endpoint #2 + #3 via Helper `_load_trip_for_validator` (Begründung siehe Implementation Details). |
| `src.app.models.WeatherChange, SegmentWeatherData, SegmentWeatherSummary, TripSegment, NormalizedTimeseries, ForecastMeta, Provider` | konsumiert | DTOs für Stub-Konstruktion im Body von Endpoint #2. |
| `internal/middleware/auth.go::AuthMiddleware` | genutzt | Globale `gz_session`-Cookie-Auth — `_validator/`- und `alert-preview`-Pfade NICHT auf die Whitelist. |
| `internal/handler/proxy.go::appendUserID` | genutzt | Anti-Spoofing-Pattern (Bug #199) — Go-Proxy injiziert authentifizierten `user_id` als Query-Param. |
| `external_validator_auth` (Spec) | konsumiert | Validator-Launcher injiziert Cookie in `claude --print`-Prompt. |
| `validator_internal_loaded_endpoint` (Spec) | Referenz | Vorbild-Struktur für `_internal`/`_validator`-Pfade (Issue #115). |

## Implementation Details

### Loader-Adapter: Warum nicht `load_all_trips` direkt

Der Validator-Router nutzt **nicht** `load_all_trips(user_id)`, sondern zwei
modul-private Helper im Router selbst. Grund: Der Production-Loader führt zwei
Auto-Transformationen aus, die für Validator-Beobachtung problematisch sind:

1. **`Trip.__post_init__` wirft `ValueError` bei `stages=[]`.** Test-Fixtures
   für AC-7 (Trip mit nur `alert_rules`) und AC-9 (Trip mit nur `report_config`)
   brauchen keinen vollständigen Wanderpfad — sie würden vom Loader verworfen.
2. **`_migrate_legacy_alert_rules`** baut aus `report_config.change_threshold_*`
   synthetische `alert_rules` mit `enabled = report_config.alert_on_changes` und
   **`build_default_display_config_for_profile`** injiziert ein profilabhängiges
   Default-`display_config`. Konsequenz: ein Trip, der User-seitig **nur**
   `report_config` hat (AC-9-Fall), wird nach Loader-Pass nicht mehr unterscheidbar
   von einem Trip mit echten `alert_rules` — der Validator würde immer
   `from_alert_rules` sehen, obwohl der User keine Regel angelegt hat.

Lösung im Router:

- **`_load_trip_raw(user_id, trip_id) → dict | None`**: liest die JSON-Datei via
  `get_trips_dir(user_id)` direkt (kein Parsing, keine Migration).
- **`_load_trip_for_validator(user_id, trip_id) → Trip | None`**: ruft
  `_load_trip_raw` und delegiert an `_parse_trip`. **Wenn** `data["stages"]` leer
  ist, wird **nur dann** ein einzelner Placeholder-Stage injiziert (mit einem
  trivialen Waypoint), damit `Trip.__post_init__` durchläuft. Produktionsdaten
  mit echten Stages werden nicht angefasst.
- **`_config_source_from_raw(raw, trip_obj) → str`**: ermittelt `config_source`
  aus dem **rohen** JSON (welche Keys hat der User explizit gesetzt?), spiegelt
  aber die Auswahlpriorität aus `TripAlertService._select_change_detector`
  (alert_rules > display_config > report_config > defaults). Das `thresholds`-Dict
  kommt unverändert aus dem hydrierten Detector — der Validator beobachtet damit
  zwei Aspekte sauber getrennt: was hat der User konfiguriert (`config_source`)
  und was tut der Production-Detector tatsächlich (`thresholds`).

### `api/routers/validator.py` — NEU

Drei Endpoints in einem Router. Stub-Konstruktion für Endpoint #2 als
Modul-privater Helper, damit der Test-Pattern aus
`tests/unit/test_issue_131_alert_klarheit.py::_make_segment_data` 1:1 wiederverwendet
werden kann.

```python
from datetime import datetime, time, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.app.loader import load_all_trips
from src.app.metric_catalog import format_metric_value
from src.app.models import (
    ChangeSeverity, ForecastMeta, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment, WeatherChange,
)
from src.formatters.trip_report import TripReportFormatter
from src.services.trip_alert import TripAlertService

router = APIRouter()


# --- Endpoint #1 -------------------------------------------------------

@router.get("/api/_validator/format-metric")
async def format_metric(
    unit: str = Query(..., description="Unit code: m, km, hPa, %, km/h, °C, mm"),
    value: float = Query(...),
    signed: bool = Query(False),
):
    """Wrapper um app.metric_catalog.format_metric_value für Issue #131 AC-4..AC-6."""
    return {"formatted": format_metric_value(unit, value, signed=signed)}


# --- Endpoint #3 -------------------------------------------------------

def _effective_detector_source(trip) -> str:
    """Spiegelt TripAlertService._select_change_detector — welcher Factory-Pfad
    wird vom hydrierten Trip tatsächlich gewählt (nach Loader-Auto-Migration)."""
    active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
    if active_rules:
        return "from_alert_rules"
    if trip.display_config and trip.display_config.get_enabled_metrics():
        return "from_display_config"
    if trip.report_config:
        return "from_trip_config"
    return "defaults"


@router.get("/api/_validator/detector-thresholds")
async def detector_thresholds(
    trip: str = Query(..., description="Trip-ID"),
    user_id: str = Query(...),
):
    raw = _load_trip_raw(user_id, trip)
    trip_obj = _load_trip_for_validator(user_id, trip)
    if trip_obj is None or raw is None:
        raise HTTPException(404, f"Trip {trip} nicht gefunden für User {user_id}")

    detector = TripAlertService(user_id=user_id)._select_change_detector(trip_obj)

    # config_source: User-Intent aus rohem JSON (was hat der User explizit gesetzt?)
    config_source = _config_source_from_raw(raw, trip_obj)
    # effective_detector: was _select_change_detector nach Loader-Migration nimmt
    effective_source = _effective_detector_source(trip_obj)

    return {
        "config_source": config_source,
        "effective_detector": effective_source,
        "thresholds": dict(detector._thresholds),
    }


# --- Endpoint #2 -------------------------------------------------------

class ChangePayload(BaseModel):
    metric: str
    old_value: float
    new_value: float
    delta: float
    threshold: float
    severity: str  # "minor" | "moderate" | "major"
    direction: str  # "increase" | "decrease" | "above" | "below"
    segment_id: str

class SegmentTimePayload(BaseModel):
    segment_id: str
    start: str  # "HH:MM"
    end: str    # "HH:MM"

class AlertPreviewBody(BaseModel):
    changes: list[ChangePayload] = Field(..., min_length=1)
    segment_times: list[SegmentTimePayload] = Field(..., min_length=1)


def _stub_segment(seg_time: SegmentTimePayload) -> SegmentWeatherData:
    """Minimaler Renderer-Stub. Pattern aus test_issue_131_alert_klarheit.py."""
    today = datetime.now(timezone.utc).date()
    start_h, start_m = (int(p) for p in seg_time.start.split(":"))
    end_h, end_m = (int(p) for p in seg_time.end.split(":"))
    start_dt = datetime.combine(today, time(start_h, start_m), tzinfo=timezone.utc)
    end_dt = datetime.combine(today, time(end_h, end_m), tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=seg_time.segment_id,
        start_time=start_dt,
        end_time=end_dt,
        # weitere TripSegment-Felder mit minimalen Defaults (location etc.)
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.OPENMETEO, model="validator-stub",
                run=datetime.now(timezone.utc), grid_res_km=1.0, interp="stub",
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


@router.post("/api/trips/{trip_id}/alert-preview")
async def alert_preview(
    trip_id: str,
    body: AlertPreviewBody,
    user_id: str = Query(...),
):
    trip_obj = next(
        (t for t in load_all_trips(user_id) if t.id == trip_id), None
    )
    if trip_obj is None:
        raise HTTPException(404, f"Trip {trip_id} nicht gefunden für User {user_id}")

    changes = [
        WeatherChange(
            metric=c.metric, old_value=c.old_value, new_value=c.new_value,
            delta=c.delta, threshold=c.threshold,
            severity=ChangeSeverity(c.severity),
            direction=c.direction, segment_id=c.segment_id,
        )
        for c in body.changes
    ]
    segments = [_stub_segment(st) for st in body.segment_times]

    report = TripReportFormatter().format_email(
        segments=segments,
        trip_name=trip_obj.name,
        report_type="alert",
        display_config=trip_obj.display_config,
        changes=changes,
    )
    return {"html": report.email_html, "plain": report.email_plain}
```

### `api/main.py` — Router einbinden

```python
from api.routers import (..., validator)
app.include_router(validator.router)
```

### `internal/handler/proxy.go` — Drei Proxy-Handler

Analog `LoadedTripProxyHandler` (Z. 160-188). `appendUserID` injiziert
`user_id` aus Auth-Context, Path-Params via `chi.URLParam`.

```go
// GET /api/_validator/format-metric — Pure-GET-Pass-Through (kein user_id nötig
// für die Pure-Function, aber Auth via globaler Middleware bleibt zwingend).
func ValidatorFormatMetricProxyHandler(pythonURL string) http.HandlerFunc { ... }

// POST /api/trips/{id}/alert-preview
func AlertPreviewProxyHandler(pythonURL string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        query := appendUserID(r.URL.RawQuery, middleware.UserIDFromContext(r.Context()))
        url := pythonURL + "/api/trips/" + id + "/alert-preview?" + query
        // Body + Content-Type weiterleiten, Response durchreichen.
    }
}

// GET /api/_validator/detector-thresholds?trip=<id>
func DetectorThresholdsProxyHandler(pythonURL string) http.HandlerFunc { ... }
```

### `cmd/server/main.go` — Drei Route-Einträge

```go
r.Get("/api/_validator/format-metric",        handler.ValidatorFormatMetricProxyHandler(cfg.PythonCoreURL))
r.Get("/api/_validator/detector-thresholds",  handler.DetectorThresholdsProxyHandler(cfg.PythonCoreURL))
r.Post("/api/trips/{id}/alert-preview",       handler.AlertPreviewProxyHandler(cfg.PythonCoreURL))
```

## Expected Behavior

- **Input:**
  - Endpoint #1: `GET /api/_validator/format-metric?unit=<u>&value=<v>[&signed=true]`
  - Endpoint #2: `POST /api/trips/{id}/alert-preview` mit JSON-Body
    `{changes:[…], segment_times:[…]}`
  - Endpoint #3: `GET /api/_validator/detector-thresholds?trip=<id>`
  - Alle drei: gültiges `gz_session`-Cookie (sonst 401 durch globale AuthMiddleware).
- **Output:**
  - #1: `200 {"formatted": "<string>"}` exakt aus `format_metric_value(...)`.
  - #2: `200 {"html": "<string>", "plain": "<string>"}` — vollständiger
    Alert-Mail-Render-Output, identisch zur Production-Mail (gleicher Renderer-Pfad).
  - #3: `200 {"config_source": "<…>", "effective_detector": "<…>", "thresholds": {"<field>": <threshold>, …}}`.
    `config_source` reflektiert User-Intent aus rohem JSON (was der User explizit angelegt hat).
    `effective_detector` reflektiert den von `TripAlertService._select_change_detector` tatsächlich gewählten Factory-Pfad nach Loader-Hydration (inkl. Auto-Migration und Default-Profile-Config). Beide Felder nehmen Werte aus
    `from_alert_rules | from_display_config | from_trip_config | defaults`. Sie können divergieren — das ist nicht ein Bug, sondern die zentrale Beobachtung, die dieser Endpoint sichtbar macht.
  - 404 bei unbekanntem Trip (User-Scope), 401 ohne Cookie, 422 bei
    invalidem JSON-Body (FastAPI-Default).
- **Side effects:** Keine. Endpoint #2 ruft `format_email` direkt — KEIN
  `TripAlertService._send_alert`, KEIN SMTP-Call, KEIN Snapshot-Update,
  KEIN Throttle-File-Write.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Validator (gültiges `gz_session`-Cookie) / When er `GET /api/_validator/format-metric?unit=m&value=12240` aufruft / Then antwortet der Server mit `200 OK` und Body `{"formatted": "12.240 m"}` (DE-Tausender-Trenner, keine Dezimalstellen, kein Vorzeichen).

- **AC-2:** Given ein eingeloggter Validator / When er `GET /api/_validator/format-metric?unit=%&value=33.5&signed=true` aufruft / Then antwortet der Server mit `200 OK` und Body `{"formatted": "+34 %"}` (Integer, kaufmännische Rundung, ASCII-Plus als signed-Präfix).

- **AC-3:** Given ein nicht eingeloggter Client (kein `gz_session`-Cookie oder ungültig) / When er `GET /api/_validator/format-metric?unit=m&value=12240` aufruft / Then antwortet der Server mit `401 Unauthorized` durch die globale `AuthMiddleware`, kein Body-Leak.

- **AC-4:** Given ein eingeloggter Validator und ein existierender Trip mit `id="t1"` im User-Scope / When er `POST /api/trips/t1/alert-preview` mit Body `{"changes":[{"metric":"visibility_min_m","old_value":12240,"new_value":38440,"delta":26200,"threshold":1000,"severity":"moderate","direction":"increase","segment_id":"2"}],"segment_times":[{"segment_id":"2","start":"14:00","end":"16:00"}]}` aufruft / Then antwortet der Server mit `200 OK` und einem Body, der `html` und `plain` als Strings enthält, beide den Teilstring `"Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)"` (Plain) bzw. seine HTML-Entsprechung enthalten.

- **AC-5:** Given ein eingeloggter Validator und ein Trip im User-Scope / When er `POST /api/trips/<id>/alert-preview` mit beliebigen synthetischen `changes` aufruft / Then werden weder SMTP-Mails versendet, noch Throttle-Dateien beschrieben, noch Weather-Snapshots geupdated — der Endpoint ist seiteneffektfrei und kann beliebig oft wiederholt werden, ohne Production-Zustand zu ändern.

- **AC-6:** Given ein eingeloggter Validator (`user_id=A`) und ein Trip mit `id="t2"`, der zu User `B` gehört / When der Validator `POST /api/trips/t2/alert-preview` aufruft / Then antwortet der Server mit `404 Not Found`, weil `load_all_trips(A)` `t2` nicht enthält (User-scoped Loader). Kein 403, kein Datenleak.

- **AC-7:** Given ein eingeloggter Validator und ein Trip mit mindestens einer aktivierten `AlertRule` (`enabled=True`) / When er `GET /api/_validator/detector-thresholds?trip=<id>` aufruft / Then enthält die Antwort sowohl `"config_source": "from_alert_rules"` als auch `"effective_detector": "from_alert_rules"`, und das `thresholds`-Dict listet exakt die summary-Felder, die von den aktivierten Regeln abgedeckt sind (z. B. `temp_min_c` für eine Temperatur-Delta-Regel).

- **AC-8:** Given ein eingeloggter Validator und ein Trip ohne `alert_rules`, aber mit `display_config`, in dem `Sichtweite.enabled=True` ist / When er `GET /api/_validator/detector-thresholds?trip=<id>` aufruft / Then enthält die Antwort sowohl `"config_source": "from_display_config"` als auch `"effective_detector": "from_display_config"`, und `thresholds` enthält `visibility_min_m` mit dem MetricCatalog-Default (`1000`).

- **AC-9:** Given ein eingeloggter Validator und ein Trip ohne `alert_rules` und ohne explizite `display_config`, aber mit `report_config` und `alert_on_changes=True` / When er `GET /api/_validator/detector-thresholds?trip=<id>` aufruft / Then enthält die Antwort `"config_source": "from_trip_config"` (User-Intent, raw JSON) und `"effective_detector": "from_alert_rules"` (Loader-Migration baut aus den `change_threshold_*`-Werten enabled AlertRules), und `thresholds` spiegelt die User-Werte: `thresholds[temp_min_c] == report_config.change_threshold_temp_c`, `thresholds[wind_max_kmh] == report_config.change_threshold_wind_kmh`, `thresholds[precip_sum_mm] == report_config.change_threshold_precip_mm`.

- **AC-10:** Given die drei neuen Endpoints sind deployed auf Staging / When der External Validator `bash .claude/validate-external.sh docs/specs/_archive/modules/issue_131_alert_email_klarheit.md` erneut ausführt / Then kippt das Verdict von `AMBIGUOUS` (Vor-Zustand laut `docs/artifacts/issue_131_alert_email_klarheit/validator-report.md`) auf `VERIFIED` (AC-1 und AC-9 bleiben pytest-only, gelten aber als „dokumentierte Lücke" und blocken nicht).

- **AC-11:** Given ein Trip ohne `alert_rules` und ohne explizite `display_config`, mit `report_config{alert_on_changes=False, change_threshold_*}` / When der Validator `GET /api/_validator/detector-thresholds?trip=<id>` aufruft / Then enthält die Antwort `"config_source": "from_trip_config"` (raw-JSON-Sicht) und `"effective_detector": "from_display_config"` (Loader-Auto-Migration injiziert Default-Display-Config; AlertRules werden mit `enabled=False` migriert), und `thresholds` zeigt MetricCatalog-Defaults (nicht die User-`change_threshold_*`-Werte). Die Divergenz ist die zentrale Validator-Beobachtung dieses Endpoints.

## Known Limitations

- **Stub-Segmente in Endpoint #2 simulieren nur die Alert-Section** der Mail.
  Stündliche Wetter-Tabellen, Night-Block, Multi-Day-Trend etc. sind in der
  Preview leer/leer-skelettiert. Das ist akzeptabel, weil das Ziel die
  Verifikation der Change-Zeilen (AC-7/AC-8 aus Issue #131) ist, nicht die
  vollständige Mail.
- **Endpoint #2 nutzt `TripSegment` mit minimalen Defaults** — falls
  `TripSegment` Pflichtfelder hat, die im Stub fehlen würden, muss der
  Helper diese Defaults setzen (Phase 5 RED deckt das mit einem Smoke-Test ab).
- **`detector._thresholds` ist privater State** der `WeatherChangeDetectionService`.
  Endpoint #3 koppelt sich bewusst daran. Bei Signatur-Änderung muss der
  Endpoint mitgezogen werden — wird durch Tests in Phase 5 abgesichert.
- **Production-Verfügbarkeit:** Endpoints sind auf Prod erreichbar (gleicher
  Code-Pfad), aber ohne Validator-User dort funktional irrelevant. Memory-Regel
  „Validator nur gegen Staging" gilt weiter — wir deaktivieren auf Prod
  nicht zusätzlich.
- **AC-1 und AC-9 aus Issue #131** (segment_id-Pflicht im Detector, Code-Grep
  nach totem Renderer-Block) bleiben pytest-only. Issue #221 schließt sie
  explizit aus dem Scope aus.
- **Loader-Auto-Migration** (`_migrate_legacy_alert_rules` +
  `build_default_display_config_for_profile`) macht die User-Intent-Aspekte
  unsichtbar, sobald `load_all_trips` läuft. Endpoint #3 nutzt daher den
  Router-internen Helper `_config_source_from_raw`, der aus der rohen Trip-JSON
  ermittelt, was der User wirklich angelegt hat. Wenn die Migrations-Logik
  geändert wird, muss der Helper mitgezogen werden — Tests
  (`tests/integration/test_issue_221_validator_endpoints.py::test_ac9_*`)
  sichern das ab.
- **Test-Fixtures dürfen `stages=[]` schreiben.** Der Validator-Loader-Helper
  injiziert in dem Fall einen Placeholder-Stage, weil `Trip.__post_init__`
  sonst die Datei verwirft. Production-Trips haben immer mindestens einen
  Stage und sind nicht betroffen.

## Changelog

- 2026-05-30: Sister-Spec Issue #464 dokumentiert neuen Endpoint `POST /api/_validator/compare-email-preview` für Compare-E-Mail-Renderer-Observability. Komplementär: #221/Endpoint#2 prüft Alert-Mail-Format, #464 prüft Compare-Mail-Format (Winner-Tags, Header-Sektion). Ort-Vergleich ist kein Trip-Kontext, daher kein `user_id`-Inject nötig.
- 2026-05-29: Sister-Spec Issue #448 dokumentiert neuen Endpoint `/api/_validator/metrics-for-channel` für Kaskaden-Sichtbarkeit bei Metric-Channel-Auflösung. Komplementär zu Endpoint #3 (Alert Detector-Auswahl).
- 2026-05-14: Initial spec — Issue #221 (External Validator: Sichtbarkeits-Endpoints)
- 2026-05-14: Loader-Adapter dokumentiert — Router nutzt
  `_load_trip_for_validator` + `_config_source_from_raw` statt direkt
  `load_all_trips`, um Auto-Migration und leere Stages der Test-Fixtures
  korrekt zu behandeln (Spec-Intent bleibt: Validator sieht User-Intent,
  nicht Post-Migration-State).
- 2026-05-14: Endpoint #3 Response erweitert um `effective_detector` (was
  `TripAlertService._select_change_detector` tatsächlich nimmt) zusätzlich
  zu `config_source` (User-Intent aus rawem JSON). AC-7..AC-9 angepasst,
  neue AC-11 für `alert_on_changes=False`-Divergenz (Adversary-Finding).
