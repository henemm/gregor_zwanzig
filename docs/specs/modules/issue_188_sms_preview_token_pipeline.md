---
entity_id: issue_188_sms_preview_token_pipeline
type: module
created: 2026-05-17
updated: 2026-05-17
status: active
version: "1.0"
tags: [backend, preview, sms, epic-140, wiring]
---

<!-- Issue #188 — Sub-Spec von preview_service / Epic #140 -->

# Issue #188 — SMS-Vorschau auf echte Token-Pipeline

## Approval

- [x] Approved (2026-05-17, implementiert)

## Purpose

`PreviewService.render_sms_preview()` liefert aktuell den getrimmten Email-Subject als SMS-Vorschau (siehe `preview_service.md` "Known Limitations"). Diese Spec verkabelt den Endpoint auf die existierende SMS-Token-Pipeline (`SMSTripFormatter.format_sms` → `build_token_line` → `render_sms`), damit die Vorschau exakt das ausgibt, was die echte SMS gemäß `sms_format.md` v2.1 (SSOT) zeigen würde.

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `PreviewService.render_sms_preview()` (umzubauen), `PreviewService._build_report()` (Helper-Signatur erweitern)

> **Schicht-Hinweis:** Reines Python-Backend. Kein Go-API-Touch (Proxy gibt unverändert durch). Kein SvelteKit-Touch (`SmsPhoneFrame.svelte` erkennt echte Spec-Tokens automatisch über `isStub`-Heuristik und blendet die Stub-Pill aus).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.formatters.sms_trip.SMSTripFormatter` | bestehend | Adapter: segments → NormalizedForecast → TokenLine → v2.0-String |
| `src.output.tokens.builder.build_token_line` | bestehend | Token-Konstruktion gemäß sms_format.md v2.1 §2/§3 |
| `src.output.renderers.sms.render_sms` | bestehend | Truncation + finale String-Render, ≤160 Zeichen |
| `services.trip_report_scheduler.TripReportSchedulerService` | bestehend | Liefert `segment_weather: list[SegmentWeatherData]` über `_convert_trip_to_segments` + `_fetch_weather` |
| `app.trip.Trip.get_stage_for_date` | bestehend | Liefert Stage-Objekt mit `.name` für `stage_name` |
| `docs/reference/sms_format.md` v2.1 | Reference | SSOT für Token-Format und Truncation-Priorität |

## Implementation Details

### Helper-Signatur erweitern

`_build_report()` (heute Z. 68–103) liefert aktuell nur den fertigen `TripReport`. Wir geben zusätzlich die Segments und den Stage-Name zurück, damit `render_sms_preview` denselben Vorlauf wiederverwenden kann ohne Doppel-Fetch:

```python
def _build_report(self, trip, target, report_type):
    # ... bestehender Pipeline-Code ...
    report = scheduler._formatter.format_email(...)
    return report, segment_weather, stage_name  # statt nur report
```

`render_email_preview()` greift weiterhin nur auf `report.email_html` zu, ignoriert die zusätzlichen Rückgaben.

### `render_sms_preview` Umbau

```python
def render_sms_preview(self, trip_id, *, user_id="default",
                      report_type="morning", target_date=None) -> tuple[str, str]:
    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Ungültiger report_type '{report_type}'")
    trip = self._load_trip(trip_id, user_id)
    target = self._resolve_target_date(trip, target_date)
    report, segment_weather, stage_name = self._build_report(trip, target, report_type)

    from src.formatters.sms_trip import SMSTripFormatter
    token_line = SMSTripFormatter().format_sms(
        segment_weather,
        stage_name=stage_name or "Etappe",
    )
    return report.email_subject, token_line
```

`SMSTripFormatter.format_sms()` ruft intern `build_token_line(...)` und `render_sms(...)` auf — sanitisiert den Stage-Name (Umlaute, 10-Char-Truncation) und enforced ≤160-Zeichen-Truncation gemäß §6.

### Out of Scope (eigene Folge-Issues, sobald Provider angebunden)

- Vigilance-Tokens `HR:`/`TH:` (Météo France Vigilance API noch nicht angebunden)
- Fire-Tokens `Z:`/`MAX`/`M:` (risque-prevention-incendie.fr nicht angebunden)
- Wintersport-Tokens `SN`/`SN24+`/`SFL`/`AV`/`WC` (im SMS-Trip-Pfad nicht verkabelt)

Diese Tokens erscheinen automatisch in der Vorschau sobald die jeweiligen Provider in `_segments_to_normalized_forecast` (sms_trip.py) Metadaten setzen — ohne weiteren Eingriff am PreviewService nötig.

## Expected Behavior

- **Input:** `trip_id`, `user_id`, `report_type` ∈ {"morning","evening"}, optional `target_date` (ISO-Datum)
- **Output:** Tupel `(email_subject, token_line)` — `token_line` ist sms_format.md v2.1-konformer String, beginnt mit `{StageName}:`, enthält Forecast-Tokens in §2-Reihenfolge, ≤160 Zeichen
- **Side effects:** Wetter-Provider-Calls über bestehende Pipeline (Cache greift), kein Versand, kein Logbuch-Eintrag

## Acceptance Criteria

- **AC-1:** Given existierender Trip mit Stage am Zieldatum und verfügbaren Wetterdaten / When `render_sms_preview` ausgeführt wird / Then enthält `token_line` einen `:`-Trenner nach dem Stage-Prefix und mindestens ein Forecast-Token in `{Symbol}{Wert}`-Form (z.B. `N`, `D`, `R`, `PR`, `W`, `G`, `TH:`, `TH+:`, `C`)
  - Test: (populated after /tdd-red)

- **AC-2:** Given Token-Pipeline läuft erfolgreich / When `token_line` zurückgegeben wird / Then ist `len(token_line) <= 160` (sms_format.md §1 Maximal-Länge)
  - Test: (populated after /tdd-red)

- **AC-3:** Given Trip mit Stage-Name "Étappe-Süden-7" (Umlaute, >10 Zeichen) / When `render_sms_preview` läuft / Then beginnt `token_line` mit einem ASCII-Stage-Prefix ≤10 Zeichen + `:` (Sanitization gemäß sms_format.md §3.1, z.B. `Etappe-Su:`)
  - Test: (populated after /tdd-red)

- **AC-4:** Given derselbe Trip + dieselben Wetterdaten + identische Eingabe / When `render_sms_preview` zweimal aufgerufen wird / Then ist `token_line` bit-identisch (Determinismus gemäß `build_token_line`-Vertrag)
  - Test: (populated after /tdd-red)

- **AC-5:** Given GET `/api/preview/{trip_id}/sms` über den FastAPI-Router mit existierendem Trip / When erfolgreich gerendert / Then ist `char_count == len(token_line)` und das JSON-Feld `token_line` enthält keinen Email-Subject-Pattern (kein `[Trip] Stage — Morgen — ...`, sondern Spec-Tokens)
  - Test: (populated after /tdd-red)

## Known Limitations

- Vigilance/Fire/Wintersport-Tokens werden nicht ausgegeben — siehe "Out of Scope". Sind eigene Folge-Issues, sobald Provider angebunden.
- Bei UI, die Email- und SMS-Vorschau parallel rendert, zwei separate `_build_report`-Calls (zwei Wetter-Fetches mit Cache-Hit auf dem zweiten). Akzeptabel, kein Optimierungs-Bedarf für #188.

## Changelog

- 2026-05-17: Initial spec für Issue #188
