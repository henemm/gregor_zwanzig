# Context: Issue #121 — Prognose-Konfidenz im Report

## Request Summary

Empfänger eines Reports soll erkennen, **wie sicher** eine Prognose ist — pro Tag (SMS) und pro Stunde (E-Mail). Datenquelle ist die OpenMeteo Ensemble API (200+ Member). Drei neue optionale DTO-Felder (`confidence_pct`, `spread_t2m_k`, `spread_precip_mm`) + Lead-Time-gecapte Berechnung + Anzeige als 1-Zeichen-Symbol in SMS (`+`/`~`/`?`) und als eigene Spalte „Sicherheit" in E-Mail. Neuer Risk-Typ `LOW_CONFIDENCE` bei Hoch-Risiko + Konfidenz < 40 %.

## Related Files

### DTOs & Modelle

| Datei | Relevanz |
|------|----------|
| `src/app/models.py` (~Z. 80–122) | `ForecastDataPoint` Python — drei neue Optional-Felder anhängen |
| `internal/model/forecast.go` (~Z. 44–75) | `ForecastDataPoint` Go — Pointer-Felder anhängen |
| `src/output/tokens/dto.py` | `NormalizedForecast`, `DailyForecast`, `Token` — Confidence muss durch die Pipeline durchgereicht werden |

### Provider (OpenMeteo Ensemble)

| Datei | Relevanz |
|------|----------|
| `src/providers/openmeteo.py` | 5 regionale Modelle. Ensemble-Endpoint `/v1/ensemble` muss neu angesprochen + in stündliche Datenpunkte gemerged werden |
| `src/services/trip_forecast.py` | Aggregation in `SegmentWeatherSummary` — `confidence_pct_min` als neue aggregierte Metrik? |

### Risk Engine

| Datei | Relevanz |
|------|----------|
| `src/services/risk_engine.py` (~Z. 31–227) | Neuer `RiskType.LOW_CONFIDENCE`, Trigger: bestehender Hoch-Risk + `confidence_pct < 40` |
| `internal/risk/engine.go` (~Z. 1–100) | Go-Pendant, gleiches Pattern |

### Output (SMS + E-Mail)

| Datei | Relevanz |
|------|----------|
| `src/output/tokens/builder.py` (~Z. 127+) | Pro-Tag-Konfidenz-Symbol als neuer Token. Priorität in Truncation-Reihenfolge festlegen |
| `src/output/renderers/email/html.py` | Neue Spalte „Sicherheit" + Klartext-Hinweis bei < 60 % in T+0–72 h |
| `src/output/renderers/email/plain.py` | Plain-Text-Variante, gleiche Spalte |

### Specs & Reference

| Datei | Relevanz |
|------|----------|
| `docs/reference/sms_format.md` (v2.0) | Anhebung auf v2.1 — Symbole `+`/`~`/`?` haben in v2.0 keine Format-Bedeutung, Kollision geprüft |
| `docs/reference/renderer_email_spec.md` | E-Mail-Layout — wo „Sicherheit"-Spalte einfügen |
| `docs/specs/modules/output_token_builder.md` (v1.1) | Token-Builder-Vertrag, muss neuen Token aufnehmen |
| `docs/specs/modules/output_channel_renderers.md` | Renderer-Architektur |
| `docs/specs/modules/risk_engine.md` (v2.0) | Risk-Assessment-Logik, neuer Type |
| `docs/specs/modules/forecast_confidence.md` | **Neu zu erstellen** — Master-Spec |

### Tests (Pattern-Vorbilder)

| Datei | Relevanz |
|------|----------|
| `tests/integration/test_risk_engine.py` | No-Mocks-Pattern, echte `SegmentWeatherData` + `MetricCatalog` |
| `tests/unit/test_openmeteo_endpoint_routing.py` | TDD-RED-Pattern, 3-tuple-Assertions |
| `tests/tdd/test_html_email.py` | `TestRealGmailE2E` — Pflicht-Referenz für E-Mail-Tests via echtes Gmail SMTP + IMAP |

## Existing Patterns

1. **Optional-Felder in DTOs:** `Optional[T] = None` als Default. Loader nutzt `.get()`-Pattern → Backward-Compat ohne Migration. Vorbild: `pop_pct` in `ForecastDataPoint` (heute einziges probabilistisches Feld).
2. **DTO synchron Python ↔ Go:** Beide DTOs werden parallel erweitert, Pointer-Felder in Go (`*int`, `*float64`).
3. **Aggregation in `SegmentWeatherSummary`:** Min/Max über Stunden-Datenpunkte (`temp_min_c`, `wind_max_kmh`, …). Konfidenz folgt `_min`-Logik (worst-case-Anzeige).
4. **Risk-Engine-Pattern:** Enum `RiskType` + `MetricCatalog`-Threshold + Dedup per Type, max Level gewinnt. `LOW_CONFIDENCE` fügt sich ein.
5. **Token-Truncation per Priorität:** `PRIORITY` Dict in `builder.py`. Neuer Confidence-Token braucht expliziten Prioritätswert.
6. **SMS-Constraint:** GSM-7, ≤160 Zeichen. Symbole `+` (0x2B), `~` (0x7E), `?` (0x3F) sind alle GSM-7-Standard.
7. **OpenMeteo-Modell-Selektion:** `select_model(lat, lon) -> (model_id, grid_res_km, endpoint)`. Ensemble braucht eigenen Endpoint-Pfad.
8. **Test-Lokationen:** Salzburg (Alpen) + Pollença (Mittelmeer) als Standard-Paar für Provider-Tests.

## Dependencies

- **Upstream:** OpenMeteo Ensemble API (`/v1/ensemble`) — neue API-Anbindung im bestehenden Provider-Modul.
- **Downstream:** Token-Builder, E-Mail-Renderer (HTML + Plain), Risk-Engine, Aggregation in `SegmentWeatherSummary`.
- **DTO-Persistenz:** `ForecastDataPoint` wird in Trip-State/Forecast-Cache serialisiert — Loader/Saver mit `.get()`-Default.

## Existing Specs

- `docs/specs/modules/output_token_builder.md` — Token-Builder
- `docs/specs/modules/output_channel_renderers.md` — Renderer-Architektur
- `docs/specs/modules/risk_engine.md` — Risk-Assessment
- `docs/reference/sms_format.md` v2.0 — SMS-Format (wird v2.1)
- `docs/reference/renderer_email_spec.md` — E-Mail-Layout

**Lücken (neu zu erstellen):**
- `docs/specs/modules/forecast_confidence.md` — Master-Spec für dieses Feature
- Provider-Spec für Ensemble-Routing (oder Erweiterung bestehender OpenMeteo-Spec)

## Risks & Considerations

1. **Backward-Compat:** Bestehende serialisierte Forecasts haben keine Konfidenz-Felder. Loader-Pattern `.get(key, None)` muss eingehalten werden (Issue #102-Lehre: Schema-Backup-Hook greift automatisch).
2. **Ensemble-Coverage:** Nicht alle regionalen Modelle haben Ensemble-Daten (z.B. MetNo Nordic). Fallback-Strategie: ECMWF Ensemble global oder `confidence_pct = None` mit Klartext-Hinweis.
3. **Lead-Time-Cap muss bei Spread=0 wirken:** Stabile Hochlagen +5d produzieren sonst trügerische 95 %. Cap ist obligatorisch, nicht optional.
4. **SMS-Truncation:** Neuer Token kostet bei Mehrtages-Trips pro Tag 1 Zeichen + Separator. Bei langen Trips ggf. Priorität niedrig setzen oder erst ab unsicheren Tagen rendern.
5. **Klartext-Hinweis nur bei < 60 % in T+0–72 h:** Sonst Visual Noise bei stabilen Lagen. Schwelle in Spec festnageln.
6. **Symbol-Kollision in SMS:** `+`, `~`, `?` haben in `sms_format.md` v2.0 keine reservierte Bedeutung — geprüft im Issue. Falls Token-Parser doch Sonderzeichen nutzt: in Phase 2 verifizieren.
7. **OpenMeteo Attribution:** CC-BY 4.0 — kommerziell erlaubt mit Attribution. Footer im E-Mail-Renderer prüfen.
8. **Risk-Type `LOW_CONFIDENCE` Trigger-Definition:** „Hoch-Risiko" muss präzise definiert sein (welche bestehenden Types? welche Level?). Vermeidung Doppel-Alarm.

## Phase-2-Entscheidung: Zerlegung in zwei Workflows

**Begründung:** ~300 LoC Code + ~230 LoC Tests über 16 Dateien aus 5 Bereichen sind zu viel für eine einzelne Spec und einen Developer-Agenten. Sauberer Schnitt entlang der natürlichen Grenze „Daten erzeugen" vs. „Daten anzeigen". Produktive Nutzer existieren nicht — Zerlegung dient Spec-Qualität und Adversary-Reviewbarkeit, nicht Live-Rollback-Sicherheit.

### Workflow 1: Backend (`issue-121-confidence-backend`)

**Scope:** Daten erzeugen — kein Output ändert sich.

| Datei | Änderung | LoC |
|------|----------|-----|
| `src/app/models.py` | 3 Optional-Felder zu `ForecastDataPoint` | ~5 |
| `internal/model/forecast.go` | 3 Pointer-Felder, `json:omitempty` | ~5 |
| `src/providers/openmeteo.py` | `_fetch_ensemble_spread()`, Merge in `_parse_response()`, Lead-Time-Cap bei Berechnung | ~80 |
| `src/services/aggregation.py` + `src/services/trip_forecast.py` | `confidence_pct_min` in `SegmentWeatherSummary` | ~20 |
| `src/services/risk_engine.py` | `RiskType.LOW_CONFIDENCE` + `_check_confidence()` | ~30 |
| `internal/risk/engine.go` + `internal/model/risk.go` | Go-Pendant | ~30 |
| `docs/reference/api_contract.md` | 3 Felder dokumentieren | ~10 |
| `docs/specs/modules/forecast_confidence.md` (Master) | Vollständige Spec | ~150 (Doku, zählt nicht) |
| `docs/specs/modules/risk_engine.md` | LOW_CONFIDENCE-Sektion | ~10 (Doku) |

**Code-LoC:** ~170, **Tests:** ~140, **Doku:** ~170. Wahrscheinlich `loc_limit_override` 300 nötig.

**Liefert:** Konfidenz-Daten fließen vollständig, Risk-Engine reagiert. Output-Renderer ignoriert Felder weiterhin (None-tolerant).

### Workflow 2: Output (`issue-121-confidence-output`)

**Scope:** SMS-Symbol + E-Mail-Spalte + Klartext-Hinweis.

| Datei | Änderung | LoC |
|------|----------|-----|
| `src/output/tokens/builder.py` | Symbol `"C"` zu `PRIORITY` + `POSITIONAL`, Builder-Loop | ~25 |
| `src/app/metric_catalog.py` | `MetricDefinition(id="confidence", ...)` | ~15 |
| `src/output/renderers/email/html.py` + `plain.py` | Klartext-Hinweis bei `<60 %` in T+0-72h | ~30 |
| `docs/reference/sms_format.md` | v2.0 → v2.1 | ~20 (Doku) |
| `docs/reference/renderer_email_spec.md` | Spalte „Sicherheit" + Hinweis-Regel | ~15 (Doku) |
| `docs/specs/modules/output_token_builder.md` | Confidence-Token-Regel | ~10 (Doku) |
| `docs/specs/modules/output_channel_renderers.md` | Spalte + Hinweis | ~10 (Doku) |
| `docs/specs/modules/issue_121_confidence_output.md` (neu) | Sub-Spec, referenziert Master | ~60 (Doku) |

**Code-LoC:** ~70, **Tests:** ~120 (E-Mail-E2E + Token-Builder), **Doku:** ~115. Im Limit.

**Liefert:** Vollständiges Feature — SMS zeigt `+`/`~`/`?`, E-Mail hat „Sicherheit"-Spalte + Klartext-Hinweis.

### Specs

- **Master-Spec:** `docs/specs/modules/forecast_confidence.md` — vollständige AC-N-Akzeptanzkriterien, Konfidenz-Formel, Lead-Time-Cap-Tabelle, Datenfluss-Diagramm. Wird in Workflow 1 geschrieben.
- **Backend-Sub-Spec:** Wird in Workflow 1 als Teil der Master-Spec abgehandelt (kein separates File).
- **Output-Sub-Spec:** `docs/specs/modules/issue_121_confidence_output.md` — Wird in Workflow 2 geschrieben, referenziert Master.

### Reihenfolge

Workflow 1 zuerst (Backend), nach Abschluss Workflow 2 (Output). Workflow 2 setzt erfolgreich-fließende Konfidenz-Daten voraus.

### Aktueller Workflow

`issue-121-forecast-confidence` wird als **Workflow 1 (Backend)** verwendet. Nach Abschluss startet ein neuer Workflow `issue-121-confidence-output`.
