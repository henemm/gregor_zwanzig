# Context: feat-917-alert-renderer (#914 Slice 2)

## Request Summary
Vier reine Renderer (Betreff · Email · Telegram · SMS), die einen ausgelösten
Abweichungs-Alert generisch über die Metrik-Registry projizieren — gemäß den in
#914 spezifizierten Formaten (informativer Betreff, Pfeil/Δ%/Schwellseite,
km-Spanne, SMS-Token mit severity-Sortierung + `+k`-Überlauf). Ersetzt die heutigen
verteilten Renderer und entfernt die letzte doppelte SMS-Code-Quelle.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` | **Single Source** (Slice 1): `sms_code`, `decimals`, `cmp` + Accessoren `get_sms_code/get_decimals/get_cmp`, `get_label_for_field(summary_field)`, `format_metric_value`. `summary_fields`-Map liefert die Brücke summary_field→metric_id |
| `src/app/models.py:408` | `WeatherChange` (metric=summary_field, old/new_value, delta, threshold, severity, direction, segment_id, **occurred_at** aus Slice 1) — die heutige Event-Quelle |
| `src/output/renderers/email/alert_compact.py` | Heutiger knapper Alert-Renderer (#816) — **wird ersetzt** |
| `src/formatters/sms_trip.py:44` | `SMS_SYMBOL_BY_METRIC` (doppelt/widersprüchlich) + `format_alert_sms()` — **Dedup-Ziel** |
| `src/services/trip_alert.py:848` | `_send_alert` baut Betreff statisch + ruft `render_deviation_alert` — **Einbindungspunkt** |
| `src/services/weather_change_detection.py:519` | F003-RESIDUAL: `_ALERT_METRIC_COMPARISON.get(rule.metric, "above")` toter Fallback |
| `src/output/renderers/email/helpers.py:739` | `build_segment_label` — bestehende km-Ableitung aus Segmenten |
| `docs/adr/0011-...md` | Architektur-Vorgabe: EIN Backend-Renderer, reine Funktionen, Registry-Single-Source |

## Existing Patterns
- **Reine-Funktions-Renderer** unter `src/output/renderers/<channel>/` (email/sms/text_report) — neues `alert/`-Modul fügt sich ein.
- **Katalog-getriebene Formatierung:** `format_metric_value(unit, value)`, `get_label_for_field`, `get_sms_code` — Renderer kennt keine Metrik namentlich (C9).
- **severity-Sortierung** existiert bereits zweifach (alert_compact `_strength`, format_alert_sms `_severity_order`) — wird zum einmaligen Helfer konsolidiert.
- **km-Ableitung** aus Segmenten via `distance_km` (kumulativ) — heute in `build_segment_label`.

## Datenmodell (aus #914)
`AlertEvent{metric_id, value_from, value_to, threshold, cmp, occurred_at, km_from, km_to}`,
`AlertMessage{trip_short, stand_at, events[]}`. Abgeleitete Helfer (einmalig):
`arrow`, `delta_pct`, `over_thr`, `side_label`, `severity`, `km_span`.
**Gap:** `WeatherChange` trägt `metric`=summary_field (nicht catalog metric_id) und
**kein** km_from/km_to → Projektion WeatherChange[]+Segmente→AlertMessage nötig
(field→metric_id via `summary_fields`-Reverse-Map; km aus Segment-`distance_km`).

## Dependencies
- **Upstream:** metric_catalog (Slice 1), WeatherChange (Detector), Segment-Geometrie (distance_km).
- **Downstream:** `_send_alert` (Email+Telegram heute; SMS-Kanal noch out-of-scope für Versand, aber SMS-Renderer wird gebaut), Renderer-Mail-Gate (Modus-Matrix + alert-Validator).

## Risks & Considerations
- **Renderer-Mail-Gate** greift (berührt Mail-Inhalts-Dateien): Modus-Matrix-Vertragstest + `briefing_mail_validator.py` gegen echte Staging-Mail vor Commit.
- **Offene PO-Entscheidung Temperatur-SMS-Codes:** Slice 1 `T`/`TN` vs. #914-Tabelle `N`/`D` — in Spec-Freigabe klären.
- **F003-RESIDUAL:** toten Fallback härten (KeyError/Assertion statt `.get(..., "above")`).
- **cmp-Quelle:** Renderer braucht `cmp` (über/unter) aus Katalog je metric_id, nicht `direction` (increase/decrease) aus WeatherChange — Brücke sauber bauen.
- **GSM-7/ASCII ≤140** für SMS, Unicode-Pfeile NUR in Email/Telegram (kippen SMS-Limit).
- Keine Deutung/Empfehlung (C1), Betreff-Reihenfolge fix (C2), generisch (C9), ein Renderer (C10).

## Analysis

### Type
Feature (Slice 2 von Epic #914).

### Technical Approach
Neues Modul `src/output/renderers/alert/` in 3 Dateien:
- `model.py` — `AlertEvent` + `AlertMessage` (frozen dataclasses) + einmalige reine Helfer `arrow/delta_pct/over_thr/side_label/severity/km_span/direction` (arbeiten auf `AlertEvent`).
- `project.py` — `to_alert_message(changes, segments, trip_name, *, tz, stand_at) → AlertMessage`. **Einzige** Stelle, die `WeatherChange` kennt. Löst die drei Gaps: (a) field→metric_id-Reverse-Map über `_METRICS[].summary_fields`; (b) `cmp` aus Katalog je metric_id statt `direction`; (c) km_from/km_to aus `segment.start_point/end_point.distance_from_start_km`.
- `render.py` — `render_subject/render_email/render_telegram/render_sms` als reine Funktionen `AlertMessage → str` (Email: `(html, plain)`-Vertrag wie heute).

**Begründung AlertMessage-Modell (statt direkt über WeatherChange):** ADR-0011 verlangt es; WeatherChange ist strukturell unpassend (metric=summary_field, direction≠cmp, kein km). Die Projektion ist der eigentliche Wert des Slices und hält die Renderer generisch (C9/C10).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/alert/model.py` | CREATE | Dataclasses + 7 Helfer (~70 LoC) |
| `src/output/renderers/alert/project.py` | CREATE | Projektion + field→metric_id-Map (~55) |
| `src/output/renderers/alert/render.py` | CREATE | 4 Renderer (~110) |
| `src/services/trip_alert.py` | MODIFY | `_send_alert`: msg bauen, 4 Renderer speisen, Betreff dynamisch, Telegram eigenes Format (~10) |
| `src/services/weather_change_detection.py:519` | MODIFY | F003-RESIDUAL: `.get(rule.metric,"above")` → `[rule.metric]` (~2) |
| `src/app/metric_catalog.py` | MODIFY | ggf. `get_metric_id_for_field`-Helfer (~8) |
| `src/output/renderers/email/alert_compact.py` | DELETE | ersetzt (−89); Alt-Tests migrieren |

### Scope Assessment
- Files: 7 · Neue Produktiv-LoC: ~255 (knapp über Limit 250). Override (+~10) ODER Dedup herausnehmen (Entscheidung 2) hält am Limit.
- Risk Level: **MEDIUM-HIGH** — produktive Email/Telegram-Alerts; Renderer-Mail-Gate beim Löschen von `alert_compact.py`; Dedup-Risiko (Fremdpfad).

### Key Findings
- `format_alert_sms` (sms_trip.py) ist **toter Code** (kein Aufrufer) — irrelevant für Versand, aber Alt-Tests existieren.
- `render_deviation_alert` wird von 3 Test-Dateien direkt importiert → bei Löschung migrieren.
- `SMS_SYMBOL_BY_METRIC` ist **NICHT** der Alert-SMS-Pfad, sondern Briefing-Token (preview_service.py:201, trip_report.py:201) — Dedup ändert Briefing-SMS + bricht test_624/test_872.
- SMS-Kanal im **Versand** bleibt out-of-scope (`known_channels={email,telegram}`); `render_sms` wird gebaut + via Fixtures getestet, nicht verdrahtet.

### Open Questions (PO-Entscheidung) — GEKLÄRT 2026-06-30
- [x] **Temperatur-SMS-Codes → `N`/`D`** (PO): `temperature` (Tageshoch, cmp über) bekommt `D`, `temperature_cold` (Nachttief, cmp unter) bekommt `N`. Katalog-Stammdaten in diesem Slice von `T`/`TN` auf `D`/`N` ändern; zugehörige Slice-1-Tests anpassen. Kollision prüfen (kein bestehendes `N`/`D`).
- [x] **SMS_SYMBOL_BY_METRIC-Dedup → fällt aus Slice 2 raus** (PO): „Stehende Kürzel sind Gesetz" — Briefing-SMS-Token (`TH:`, `TH+`, `SFL` …) bleiben unangetastet. `sms_trip.py`/`preview_service.py`/`trip_report.py` werden NICHT angefasst. Begründung: die Briefing-Token-Grammatik (Suffixe `:`/`+` kodieren Schwellrelation) ist eine bewusst getrennte Verantwortung vom Alert-`sms_code`. Folge: ADR-0011 Ziel-3 („Doppelte Mappings entfernen") wird für den Briefing-Pfad bewusst NICHT umgesetzt → ADR-Notiz in der Spec.
- [x] **Renderer-Scope → EIN kanonischer Renderer, Radar als Folge-Issue** (PO): #917 baut `AlertMessage` als **die** kanonische Alert-Render-Quelle (general, NICHT „deviation-only"; reserviertes `source`-Feld vorhalten) und migriert den Abweichungs-Alert (`_send_alert`) darauf. Der zweite heutige Render-Pfad — **Radar-/Nowcast-Alert** (`check_radar_alerts` → `outputs/radar_alert.py`, Datenform `NowcastResult{onset_minutes, source∈{radar,INCA,AROME-FR,minutely_15}, is_convective}`) — konvergiert in einem **Folge-Issue** auf denselben Renderer (inkl. Quelle-Zeile in der Mail, analog Haupt-Mail). Onset-Ereignis braucht dort eine eigene kleine Format-Entscheidung (kein Δ%/`A→B`). Design-Pflicht in #917: das Modell darf die spätere Radar-Konvergenz NICHT verbauen.
