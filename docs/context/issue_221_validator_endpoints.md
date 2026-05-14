# Context: Issue #221 — Validator-Sichtbarkeits-Endpoints

## Request Summary

Drei Read-/Render-Endpoints einbauen, damit der External Validator (Issue #110)
interne Format-, Detector- und Alert-Mail-Logik von außen prüfen kann.
Auslöser: Issue #131 lieferte AMBIGUOUS-Verdict, weil 8 von 9 ACs reine
Python-Funktionen ohne API-Oberfläche waren (Validator-Report:
`docs/artifacts/issue_131_alert_email_klarheit/validator-report.md`).

Ziel-Endpoints (alle authentifiziert via `gz_session`-Cookie, Prefix `/api/_validator/`):

1. `GET  /api/_validator/format-metric?unit=m&value=12240[&signed=true]`
   → `{"formatted": "12.240 m"}` — Wrapper um `app.metric_catalog.format_metric_value`.
2. `POST /api/trips/{id}/alert-preview` mit Body `{changes:[…], …}`
   → `{"html": "<…>", "plain": "Segment 2 …"}` — Alert-Mail rendern ohne Versand.
3. `GET  /api/_validator/detector-thresholds?trip={id}`
   → `{"config_source": "from_display_config", "thresholds": {…}}`
   — zeigt den Detector-Auswahlpfad für den Trip.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` (`format_metric_value`, Z. 534-567) | Pure-Function, die Endpoint #1 nur wrappen muss. |
| `src/output/renderers/email/helpers.py` (`format_change_line`, `build_segment_label`) | Nutzt der Validator über Endpoint #2 für „Segment 2 (14:00–16:00) — …"-Zeilen. |
| `src/output/renderers/email/html.py::render_email` | Erzeugt HTML inkl. Alert-Section. Endpoint #2 muss diese Pipeline triggern können — aber ohne Versand. |
| `src/output/renderers/email/plain.py::render_email` (Plain-Variante) | Plaintext-Output für Endpoint #2. |
| `src/formatters/trip_report.py::TripReportFormatter.format_email` (Z. 48-150) | Akzeptiert `changes=…` und liefert `TripReport.email_html`/`.email_plain` — sauberer Aufrufpfad für Endpoint #2. |
| `src/services/weather_change_detection.py::WeatherChangeDetectionService` (`from_display_config` Z. 156-184, `from_trip_config` Z. 121-154, `from_alert_rules` Z. 186-229, `_thresholds`) | Endpoint #3 ruft die korrekte Factory auf und gibt das `_thresholds`-Dict zurück. |
| `src/services/trip_alert.py::TripAlertService._select_change_detector` (Z. 153-167) | Kanonische Auswahllogik (alert_rules > display_config > report_config > defaults) — Endpoint #3 nutzt sie 1:1. |
| `src/app/loader.py::load_all_trips`, `_trip_to_dict` | User-scoped Trip-Hydration für Endpoint #2 (`{id}`-Lookup) und Endpoint #3. |
| `src/app/models.py::WeatherChange, SegmentWeatherData, SegmentWeatherSummary` (Z. 311-396) | DTOs, die Endpoint #2 aus dem JSON-Body rekonstruiert. |
| `api/routers/internal.py` | Vorbild für `/api/_internal/…`-Style-Router (Issue #115). Endpoint #1 + #3 folgen diesem Muster. |
| `api/routers/preview.py` | Vorbild für trip-id-basierte Render-Endpoints mit Query-Param `user_id` (Bug #199-Pattern). |
| `api/main.py` | Router-Registrierung (1 Zeile pro neuem Router). |
| `internal/handler/proxy.go::LoadedTripProxyHandler` (Z. 160-188) | Vorbild-Proxy für `_internal`-Pfade (chi.URLParam + appendUserID). |
| `internal/handler/proxy.go::ProxyHandler` / `ProxyPostHandler` / `CompareProxyHandler` | Vorbilder für GET-/POST-Proxy. |
| `internal/middleware/auth.go::AuthMiddleware` (Z. 31-58) | Globale Cookie-Auth — neue `_validator`-Pfade NICHT auf die Whitelist setzen. |
| `cmd/server/main.go` | Route-Registry — pro Endpoint eine Zeile (siehe Z. 106 für `/_internal/…`-Beispiel). |

## Existing Patterns

- **Validator-only Endpoint via Pfad-Prefix (Issue #115):** `/api/_internal/...` ist
  durch die globale `AuthMiddleware` automatisch Cookie-geschützt (kein Whitelist-Eintrag).
  Go-Proxy hängt `?user_id=<aus-context>` an, Python liest aus Query-Param. Wir nutzen
  dasselbe Pattern mit Prefix `/api/_validator/` für Endpoint #1 + #3 — sie sind
  rein Tooling/Observability, nicht versionsstabil.
- **Trip-ID-Endpoint mit Query-Auth (Bug #199):** `/api/trips/{id}/...` (z.B.
  Preview-Endpoints) erwartet im Python-Layer `user_id` als Query-Param, der vom
  Go-Proxy injiziert wird. Endpoint #2 folgt diesem Muster (`/api/trips/{id}/alert-preview`).
- **Single Source of Truth für Alert-Mail-Rendering:** `TripReportFormatter.format_email(...)`
  liefert mit `report_type="alert"` und `changes=[…]` direkt das gewünschte
  `TripReport(email_html, email_plain)` — kein neuer Render-Pfad nötig.
- **Detector-Auswahl:** `TripAlertService._select_change_detector(trip)` ist bereits
  die kanonische Logik. Endpoint #3 ruft sie auf, statt sie zu duplizieren.
- **Pure-Function-Wrapper (Endpoint #1):** Minimal-Endpoint analog `/api/_internal/...`
  — 5–10 LoC FastAPI-Handler, der direkt die Catalog-Funktion ruft.

## Dependencies

- **Upstream:**
  - `src.app.metric_catalog.format_metric_value` (für #1)
  - `src.services.trip_alert.TripAlertService._select_change_detector` (für #3)
  - `src.app.loader.load_all_trips` (für #2, #3 — User-Scope)
  - `src.formatters.trip_report.TripReportFormatter.format_email` (für #2)
  - DTOs aus `src.app.models`: `WeatherChange`, `SegmentWeatherData`, `SegmentWeatherSummary`, `TripSegment` (für #2 Body-Reconstruction)

- **Downstream:**
  - External Validator (`.claude/validate-external.sh`) — direkter Konsument.
  - Keine UI-/Frontend-Kopplung, keine anderen Services.

## Existing Specs

- `docs/specs/modules/validator_internal_loaded_endpoint.md` — Vorbild-Struktur,
  Issue #115. Beschreibt Auth-Flow (Cookie → Go → Python via Query-Param).
- `docs/specs/modules/external_validator_auth.md` — Issue #110, Auth-Kontext.
- `docs/specs/modules/issue_131_alert_email_klarheit.md` — inhaltliche Quelle der
  ACs, die mit diesen Endpoints prüfbar werden sollen.
- `docs/artifacts/issue_131_alert_email_klarheit/validator-report.md` — AMBIGUOUS-Begründung, Endpoint-Empfehlung.

## Risks & Considerations

- **Body-Reconstruction für Endpoint #2:** Synthetische `SegmentWeatherData`-Objekte
  vollständig aus JSON zu bauen ist invasiv (NormalizedTimeseries, ForecastDataPoint,
  TripSegment …). Pragmatischer Weg: minimale Body-Struktur akzeptieren — User schickt
  nur `changes` (Liste von `WeatherChange`-Feldern) + optional `segments`-Stubs
  (`segment_id`, `start_time`, `end_time`, `aggregated`-Subset). Renderer braucht
  `segments` nur für `build_segment_label`. Rest (Hourly-Tabellen) bei
  `report_type="alert"` minimal halten.
- **Auth-Kollision:** Globale `AuthMiddleware` greift bei allen `_validator/`-Pfaden.
  Kein Whitelist-Bypass nötig, kein eigener Auth-Code-Pfad. Bei Endpoint #2
  zusätzlich Trip-Owner-Check via `load_all_trips(user_id)` — wer fremde
  `trip_id` schickt, kriegt 404 (Bug #199-Pattern).
- **Keine echte Mail:** Endpoint #2 darf NICHT `EmailOutput.send` aufrufen. Wir nutzen
  `TripReportFormatter.format_email(...)` und geben das `TripReport`-Objekt zurück —
  das Senden steckt im `TripAlertService._send_alert`, das wir NICHT betreten.
- **Production-Sicherheit:** `_validator/`-Pfade sind cookie-geschützt, also auf Prod
  nur für eingeloggte Nutzer erreichbar. Da kein Validator-User in Prod existiert
  (Spec `external_validator_auth.md` „Known Limitations"), läuft das Risiko gegen Null;
  zusätzlich aber prüfen, ob wir die Pfade auf Prod komplett deaktivieren wollen.
  Tech-Lead-Vorschlag: vorerst keine Stage-spezifische Deaktivierung — Cookie reicht.
- **Scope-Begrenzung gemäß Issue #221:**
  - AC-1 (`segment_id`-Pflicht) und AC-9 (Code-Grep) bleiben pytest-only. Issue
    selbst stuft sie explizit als „durch HTTP nicht sinnvoll prüfbar" ein.
- **LoC-Budget:** Defaults sind 250 LoC. Drei Endpoints (Python-Handler + Go-Proxy +
  Routen-Eintrag) liegen vermutlich um die 200–300 LoC inkl. Tests. Vor RED-Phase
  ggf. `loc_limit_override 400` setzen.

## Next Step

Phase 2: Analyse — Body-Shape für Endpoint #2 finalisieren, Response-Format für
Endpoint #3 (`config_source`-Werte), Test-Strategie skizzieren.
