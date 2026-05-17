# Context: Issue #188 — SMS-Preview Spec-Format

## Request Summary

Der SMS-Preview-Endpoint (`GET /api/preview/{trip_id}/sms`) liefert aktuell den getrimmten Email-Subject statt einer echten SMS-Token-Zeile gemäß `sms_format.md` v2.0. Das Frontend (Phone-Frame aus #189) zeigt deshalb eine Stub-Pill mit "SMS-Token-Pipeline folgt (#188)". Diese Token-Pipeline ist jetzt zu verkabeln.

## Bestehender Stand (was schon da ist)

| Baustein | Datei | Status |
|---|---|---|
| iOS-Phone-Frame (320px, Dark) | `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | ✅ aus #189 |
| Zeichenzähler (/160) mit ok/warn/over | `frontend/src/lib/components/preview/previewHelpers.ts` (`charCountStatus`) | ✅ aus #189 |
| Legende außerhalb Frame | `SmsPhoneFrame.svelte` Z. 67 | ✅ aus #189 |
| Stub-Pill (verschwindet automatisch) | `SmsPhoneFrame.svelte` Z. 42–46 (`isStub`-Heuristik) | ✅ — entfällt sobald Backend echte Tokens liefert |
| SMS-Endpoint Go-Proxy → FastAPI | `api/routers/preview.py:53` | ✅ funktional |
| SMS-Token-Builder (sms_format.md v2.0) | `src/output/tokens/builder.py` (`build_token_line`) | ✅ vollständig, Vigilance/Fire/Wintersport/Confidence |
| SMS-Renderer (Truncation) | `src/output/renderers/sms/__init__.py` (`render_sms`) | ✅ |
| Trip→TokenLine-Adapter | `src/formatters/sms_trip.py` (`SMSTripFormatter.format_sms`) | ✅ — segments→NormalizedForecast→TokenLine→Text |

## Was fehlt (Scope #188)

**`PreviewService.render_sms_preview()` benutzt aktuell Email-Subject als Proxy** (`src/services/preview_service.py:121–144`):

```python
subject = report.email_subject
token_line = subject if len(subject) <= 160 else subject[:160]
return subject, token_line
```

Stattdessen soll es:
1. Wie `render_email_preview` Segments + Wetter holen (`_build_report`-Pipeline)
2. `SMSTripFormatter().format_sms(segment_weather, stage_name=...)` aufrufen
3. Echten v2.0-Token-String zurückgeben (z.B. `Paliri: N8 D24 R0.2@6(1.4@16) ...`)

## Related Files

| File | Relevance |
|---|---|
| `src/services/preview_service.py` | **Zu ändern** — `render_sms_preview()` Umstellung auf Token-Pipeline |
| `src/formatters/sms_trip.py` | Wird aufgerufen (`SMSTripFormatter.format_sms`) |
| `src/output/tokens/builder.py` | Indirekt — Sanitization (Umlaute, 10-Char-Truncation) auf `stage_name` |
| `src/output/renderers/sms/__init__.py` | Indirekt — Truncation/Render |
| `api/routers/preview.py` | Unverändert — gibt einfach durch, `char_count = len(token_line)` |
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | Unverändert — Stub-Pill verschwindet automatisch (Heuristik: enthält `:`/`@` → kein Stub) |
| `tests/tdd/test_epic_140_preview_endpoints.py` | Bestehende Tests erweitern (T3-Block ist SMS-Endpoint) |
| `docs/reference/sms_format.md` v2.1 | SSOT für Token-Format |
| `docs/specs/modules/preview_service.md` | Sub-Spec wird aktualisiert (Known Limitations entfernt) |

## Existing Patterns

- **`_build_report()`-Pipeline** (preview_service.py:68–103) liefert bereits Trip, target-date, `segment_weather` (List[SegmentWeatherData]) und ruft `format_email()` damit auf. Dieselben Segments können direkt an `format_sms()` gehen.
- **Stage-Name-Source**: `trip.get_stage_for_date(target).name` — wird in `_build_report` schon ermittelt (`stage_name` Variable, Z. 87–88). Sanitisierung (Umlaute, 10-Char) macht `_sanitize_stage_name()` im Builder automatisch.
- **Error-Mapping**: FastAPI-Router mappt schon `FileNotFoundError/LookupError → 404`, `ValueError → 422`, `RuntimeError → 503`. Bleibt unverändert.

## Dependencies

- **Upstream:** `TripReportSchedulerService._convert_trip_to_segments` + `_fetch_weather` (bereits genutzt)
- **Downstream:** Go-Proxy `/api/preview/.../sms` → Frontend `SmsPhoneFrame.svelte` (über `buildPreviewUrl`)

## Existing Specs

- `docs/reference/sms_format.md` (v2.1) — Token-Format SSOT
- `docs/specs/modules/preview_service.md` (v1.0) — enthält explizit "Known Limitation: SMS-Token-Zeile wird aktuell aus email_subject getrimmt … Echte Token-Pipeline ist Folge-Issue." Dieser Folge-Issue ist #188.
- `docs/specs/modules/output_channel_renderers.md` (β3) — Channel-Renderer-Split, definiert `format_sms`-Adapter-Vertrag

## Scope-Entscheidung (2026-05-17)

**In Scope für #188:** Nur Forecast-Tokens (N, D, R, PR, W, G, TH, TH+, C).

**Out of Scope (Folge-Issues):**
- Vigilance HR/TH (Météo France) — kein Provider angebunden
- Fire Z:/M: (Korsika) — kein Provider angebunden
- Wintersport SN/SN24+/SFL/AV/WC — Provider nur teilweise vorhanden, im SMS-Trip-Pfad nicht verkabelt

**Begründung:** Vorschau zeigt das was die echte Mail/SMS liefert. Fehlende Datenquellen können in der Vorschau nicht "eingebaut" werden — sie würden auch in der echten Mail nichts liefern.

## Risks & Considerations

1. **Stage ohne Namen**: Wenn `stage_name` leer ist, fällt der Builder mit `ValueError` aus. Default `"Etappe"` (wie im SMSTripFormatter bereits gesetzt) muss greifen.
2. **Wetter-Provider-Doppel-Call**: `render_email_preview` und `render_sms_preview` rufen heute beide `_build_report()` separat auf → 2 Wetter-Fetches pro Vorschau-Render. Akzeptabel da Cache greift, aber im Hinterkopf behalten falls UI parallel beide lädt.
3. **`isStub`-Heuristik im Frontend**: Aktuell prüft Frontend ob Token-Line `:` und `@` enthält → wenn echtes Spec-Format (`Stage: N8 D24 …`) ankommt, ist `isStub=false` und Stub-Pill verschwindet automatisch. **Kein Frontend-Code-Change nötig** — gut.
4. **Vigilance/Fire/Wintersport**: Builder gibt diese nur aus, wenn `forecast.provider == "meteofrance"` / `country == "FR"` / `profile == "wintersport"`. Aktuelle `_segments_to_normalized_forecast()` in `sms_trip.py` setzt keinen Provider/Country → diese Tokens werden derzeit **nie** geliefert. Für #188 vermutlich okay (Issue-Beispiel `KHW_00B: N3 D11 R3.8 PR68%@13 W12@11 G25@12 TH5%@12 HR:L@12 Z:WATCH:2447` zeigt zwar HR/Z, aber das ist illustrativ). **Klären in Phase 2/3.**
5. **Issue-Beispiel-Format weicht von v2.0 ab**: Issue zeigt `R3.8` (ohne Threshold/Peak), `PR68%@13` (kompakt ohne Peak), `Z:WATCH:2447` (neuer Z-Wert). v2.0 sagt `R0.2@6(1.4@16)` etc. **Issue-Beispiel ist vermutlich Pseudo-Format, echte SSOT ist `sms_format.md` v2.1.** In Spec-Phase explizit machen.
6. **Char-Count**: Backend liefert schon `char_count`, Frontend rechnet aber selbst über `payload.char_count`. Bei v2.0-Output kann der String >160 sein → `render_sms()` truncated bereits gemäß Priority §6. Sicherstellen dass Frontend-Char-Count das tatsächliche `len(token_line)` zeigt.

## Tests im Bestand

- `tests/tdd/test_epic_140_preview_endpoints.py` — hat T1–T4 Blöcke für PreviewService + Endpoints, vermutlich SMS-Tests mit Subject-Heuristik (zu prüfen/erweitern in Phase 5 RED)
- `tests/e2e/test_e2e_story3_reports.py:252–271` — alte `test_sms_format_compact` prüft noch `E1:`/`E2:`-Legacy-Format → wahrscheinlich Bestands-Bug oder hat veraltete Assertion. Nicht Scope von #188 außer es bricht.
