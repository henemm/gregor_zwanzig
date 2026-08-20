---
entity_id: alarm_testeinspeisung
type: feature
created: 2026-08-18
updated: 2026-08-18
status: draft
workflow: feat-1948-s2-testeinspeisung
version: "1.0"
tags: [alarm, testing, validator]
---

# Alarm-Testmeldungs-Einspeisung (Scheibe S2, Issue #1948)

## Approval

- [ ] Approved

## Purpose

Der zustandslose Preview-Endpoint `POST /api/trips/{trip_id}/alert-preview` rendert heute nur
zwei der drei Alarm-Zweige (Δ-Abweichung, Radar-Onset). Scheibe S1 (#1948) hat den rohen
Eingangs-Mitschnitt aller drei Zweige geschaffen (`src/services/alert_input_capture.py`) — diese
Scheibe schließt die Ausgabe-Seite: der fehlende dritte Payload-Typ (amtliche Warnung) wird
ergänzt, und alle drei S1-Mitschnittformate werden ohne Transformation direkt in den Endpoint
einspeisbar. Damit lässt sich für jede real aufgezeichnete oder frei formulierte Testmeldung
sehen, wie sie über alle vier Kanäle (E-Mail/HTML+Plain, Telegram, SMS, Betreff) gerendert würde
— die Beweisgrundlage, gegen die künftige Format-Scheiben (S3+) verifiziert werden.

## Source

- **File:** `api/routers/validator.py` (`AlertPreviewBody`, `alert_preview`), `src/services/validator_render_service.py` (`render_alert_preview`), `src/services/radar_service.py` (`_capture_nowcast_frames`)
- **Identifier:** `AlertPreviewBody`, `render_alert_preview()`

> Schicht: Python-Core (`api/`, `src/services/`) — kein Go-/Frontend-Anteil in dieser Scheibe.
> Keine neue Route, daher keine Proxy-Änderung in `internal/`.

## Estimated Scope

- **LoC:** ~200-250 (produktiv; Tests separat)
- **Files:** 3 Code-Dateien geändert (`api/routers/validator.py`, `src/services/validator_render_service.py`, `src/services/radar_service.py`) + 5-7 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/official_alerts.py::build_official_alert_notices` | function | Baut aus `(OfficialAlert, segment_ids)`-Paaren die `OfficialAlertNotice`-DTOs — identische Eingangsform wie die neue `OfficialAlertPayload`-Liste |
| `src/output/renderers/alert/official_alerts.py` | module | Vier Vorlagen-Renderer (Subject/HTML+Plain/Telegram/SMS) — NUR aufgerufen, `official_alerts.py:1896-2104` (#1929-Sperrzone) bleibt unangetastet |
| `src/services/notification_service.py::send_official_alert` (Z. 829-882) | method | Render-Sequenz-Vorlage — wird in `validator_render_service.py` gespiegelt, nicht importiert (Preview braucht keinen Versandpfad) |
| `src/services/trip_segments.py::convert_trip_to_segments` | function | Liefert reale Segment-Zeiten des Trips für die Zweig-a-Synthese ohne `segment_times` |
| `src/services/trip_day.py::trip_local_today` | function | Bestimmt den `target_date` für `convert_trip_to_segments` (gleiches Muster wie `trip_alert.py:344`) |
| `src/services/radar_service.py::RadarService._derive_result`, `_SOURCE_LABELS` | method/attribute | Leitet aus rohen Frames ein `NowcastResult` ab; liefert die menschenlesbaren Quellen-Label |
| `src/services/alert_input_capture.py` (S1) | module | Liefert das Mitschnitt-Dateiformat, das 1:1 (Zweig a) bzw. mit minimaler `jq`-Extraktion (Zweig b/c) eingespeist wird |

## Implementation Details

### Vier exklusive Payload-Typen an EINEM Endpoint

`AlertPreviewBody` (`api/routers/validator.py:237-240`) bekommt zwei neue optionale Felder,
`segment_times` wird optional (Default bleibt leere Liste):

```python
class OfficialAlertPayload(BaseModel):
    source: str
    hazard: str
    level: int
    label: str
    valid_from: str | None = None
    valid_to: str | None = None
    url: str | None = None
    region_label: str | None = None
    dedup_id: str | None = None
    segment_ids: list[str] = Field(default_factory=list)


class NowcastFramePayload(BaseModel):
    timestamp: str
    precip_mm_h: float
    is_convective: bool = False


class NowcastFramesPayload(BaseModel):
    source: str
    frames: list[NowcastFramePayload]
    km_from: float = 0.0
    km_to: float = 0.0


class AlertPreviewBody(BaseModel):
    changes: list[ChangePayload] = Field(default_factory=list)
    segment_times: list[SegmentTimePayload] = Field(default_factory=list)
    onset: OnsetPayload | None = None
    official: list[OfficialAlertPayload] | None = None
    nowcast_frames: NowcastFramesPayload | None = None
```

Der 422-Guard (`api/routers/validator.py:256-262`) wird von einem binären XOR auf eine
Vier-Wege-Exklusivität erweitert:

```python
provided = [bool(body.onset), bool(body.changes), bool(body.official), bool(body.nowcast_frames)]
if sum(provided) != 1:
    raise HTTPException(422, "Body muss genau einen von 'onset', 'changes', 'official' oder "
                              "'nowcast_frames' enthalten")
```

**Invariante:** Keine neue Route — `internal/router/router.go:167` und
`internal/handler/proxy.go:297-335` (Go-Proxy-Registrierung inkl. `user_id`-Injektion) bleiben
unverändert, da derselbe bestehende Endpoint erweitert wird.

### Zweig-a-Replay: `segment_times` optional

Fehlt `segment_times`, werden die Segment-Zeiten der in `changes` genannten `segment_id`s aus
dem bereits geladenen Trip synthetisiert:

```python
if not body.segment_times and body.changes:
    today = trip_local_today(trip_obj, datetime.now(timezone.utc))
    real_segments = {str(s.segment_id): s for s in convert_trip_to_segments(trip_obj, today)}
    synthesized = []
    for c in body.changes:
        seg = real_segments.get(c.segment_id)
        if seg is None:
            raise HTTPException(422, f"Unbekannte segment_id '{c.segment_id}' im Trip")
        synthesized.append(SegmentTimePayload(
            segment_id=c.segment_id,
            start=seg.start_time.strftime("%H:%M"),
            end=seg.end_time.strftime("%H:%M"),
        ))
    body.segment_times = synthesized
```

Damit ist der `payload.changes`-Teil einer S1-Mitschnittdatei
`data/users/<uid>/alert_input/forecast_change_*.json` (Hülle: `{capture_id, captured_at,
entity_type, entity_id, payload: {"changes": [...]}}`, `alert_input_capture.py:67-73`) ohne
Transformation als `{"changes": <payload.changes>}` einspeisbar.

### Zweig b (NEU): `official`

Render-Sequenz aus `notification_service.py:846-882` in `validator_render_service.py` gespiegelt
(nicht importiert — die Preview braucht weder Versandkanäle noch Trip-Notification-Historie):

```python
def _render_official_preview(trip_obj: Trip, payloads: list) -> dict:
    from services.official_alerts.models import OfficialAlert
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_mail_plain,
        render_official_alert_sms, render_official_alert_subject,
        render_official_alert_telegram, render_warn_block,
    )
    # _official_source_label_for/_official_source_url_for stehen in
    # notification_service.py:240/292, nicht in official_alerts.py -- Import
    # von dort (oder Extraktion in ein geteiltes Modul, falls der zyklische
    # Import services.notification_service <-> services.validator_render_service
    # sich als problematisch erweist).
    alert_tz = _alert_tz_for_trip(trip_obj)
    tagged = [
        (OfficialAlert(source=p.source, hazard=p.hazard, level=p.level, label=p.label,
                        valid_from=_parse_dt(p.valid_from), valid_to=_parse_dt(p.valid_to),
                        url=p.url, region_label=p.region_label, dedup_id=p.dedup_id),
         p.segment_ids)
        for p in payloads
    ]
    dto_notices = build_official_alert_notices(trip_obj, tagged)
    source_label = _official_source_label_for(dto_notices)
    stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
    subject = render_official_alert_subject(dto_notices, prefix=trip_obj.name, tz=alert_tz)
    html = render_warn_block(dto_notices, variant="standalone", source_label=source_label,
                              source_url=_official_source_url_for(dto_notices),
                              stand_at=stand_at, tz=alert_tz, context_label=trip_obj.name)
    plain = render_official_alert_mail_plain(dto_notices, source_label=source_label,
                                              stand_at=stand_at, tz=alert_tz,
                                              context_label=trip_obj.name)
    telegram = render_official_alert_telegram(dto_notices, prefix=trip_obj.name,
                                               source_label=source_label, tz=alert_tz)
    sms = render_official_alert_sms(dto_notices, prefix=trip_obj.name, source_label=source_label)
    return {"subject": subject, "email_html": html, "email_plain": plain,
            "telegram": telegram, "sms": sms}
```

**Invariante:** `official_alerts.py:1896-2104` (#1929-Sperrzone, SMS-Renderpfad `_tag_hour`…
`render_official_alert_sms`) wird ausschließlich AUFGERUFEN — keine Zeile darin ändert sich.
Antwortform bleibt `subject/email_html/email_plain/telegram/sms` (ADR-0011), identisch zu den
bestehenden Zweigen a/c.

**Beispiel-Payload (Ist-Vokabular, analog Test-Fixtures `tests/tdd/test_meteoalarm_feed_italien.py`
und Spec `fix_1744_alarm_format_angleichen.md`):**

```json
{
  "official": [
    {"source": "geosphere_warn", "hazard": "thunderstorm", "level": 3,
     "label": "Gewitter", "segment_ids": ["1", "2"]}
  ]
}
```

Erwartete SMS-Form (seit #1948 S5, `fix_1948_s5_amtliche_sms_zielbild.md`): `Seg 1-2: !TH:M`.

### Zweig c (NEU): Replay `nowcast_frames`

Serverseitig via `RadarService._derive_result`-Logik (`radar_service.py:521`):

```python
def _render_nowcast_replay(trip_obj: Trip, body_nf) -> dict:
    from services.radar_service import RadarService, RadarFrame
    frames = [
        RadarFrame(timestamp=datetime.fromisoformat(f.timestamp),
                   precip_mm_h=f.precip_mm_h, is_convective=f.is_convective)
        for f in body_nf.frames
    ]
    svc = RadarService()
    result = svc._derive_result(frames, body_nf.source, now=datetime.now(timezone.utc))
    if result.onset_minutes is None:
        return {"onset_detected": False, "subject": None, "email_html": None,
                "email_plain": None, "telegram": None, "sms": None}
    alert_tz = _alert_tz_for_trip(trip_obj)
    onset_time = datetime.now(timezone.utc) + timedelta(minutes=result.onset_minutes)
    onset_payload = OnsetPayload(
        onset_minutes=result.onset_minutes,
        onset_time=local_fmt(onset_time, alert_tz)[-5:],  # "HH:MM"-Anteil
        km_from=body_nf.km_from, km_to=body_nf.km_to,
        is_convective=result.is_convective,
        intensity_label=result.intensity_label,
        source_label=RadarService._SOURCE_LABELS.get(result.source, result.source),
    )
    body_for_render = AlertPreviewBody(onset=onset_payload)
    out = render_alert_preview(trip_obj, body_for_render)
    out["onset_detected"] = True
    return out
```

`source_label` über das Mapping `RadarService._SOURCE_LABELS` (`radar_service.py:223`);
`km_from`/`km_to` default `0.0`, wenn im Body nicht übergeben. Kein Nowcast-Ergebnis in den
Frames (kein `onset_minutes`) ⇒ Antwort mit explizitem Leerbefund (`onset_detected: false`,
alle Render-Felder `null`) statt HTTP 500.

### S1-Erweiterung (einzige Änderung an S1-Code): `is_convective` je Frame im Mitschnitt

`radar_service.py:660-676` (`_capture_nowcast_frames`) schreibt das `is_convective`-Feld additiv
in jeden Frame-Eintrag mit — es liegt an dieser Stelle bereits auf `RadarFrame.is_convective` vor
(gesetzt in `_load_fixture`/`_fetch_frames_with_fallback`), wird heute im Mitschnitt nur nicht
mitgeschrieben:

```python
"frames": [
    {"timestamp": f.timestamp.isoformat(), "precip_mm_h": f.precip_mm_h,
     "is_convective": f.is_convective}
    for f in frames
],
```

Damit deckt eine Zweig-c-S1-Mitschnittdatei (`data/debug/alert_input/nowcast/*.json`) ab sofort
alle Pflichtfelder von `NowcastFramesPayload` ab und ist per `jq '.payload'` direkt einspeisbar.

### Einspeise-Mechanik (clientseitig, dokumentiert)

Kein serverseitiges Datei-Lesen per Pfadparameter (Path-Traversal-/Mandanten-Risiko) — die
Capture-JSON wird clientseitig extrahiert und im Request-Body übergeben:

```bash
# Zweig a: S1-Mitschnitt 1:1 einspeisen
CAPTURE=data/users/<uid>/alert_input/forecast_change_trip_<trip_id>_<ts>.json
jq -c '{changes: .payload.changes}' "$CAPTURE" | \
  curl -s -X POST "https://staging.gregor20.henemm.com/api/trips/<trip_id>/alert-preview?user_id=<uid>" \
    -H 'Content-Type: application/json' -d @-

# Zweig c: S1-Mitschnitt 1:1 einspeisen (nach der additiven is_convective-Erweiterung)
CAPTURE=data/debug/alert_input/nowcast/<key>_<ts>.json
jq -nc --argjson nf "$(jq -c '.payload' "$CAPTURE")" '{nowcast_frames: $nf}' | \
  curl -s -X POST "https://staging.gregor20.henemm.com/api/trips/<trip_id>/alert-preview?user_id=<uid>" \
    -H 'Content-Type: application/json' -d @-
```

## Expected Behavior

- **Input:** `POST /api/trips/{trip_id}/alert-preview?user_id=<uid>` mit Body, der GENAU EINEN
  von `changes` (+optional `segment_times`), `onset`, `official`, `nowcast_frames` enthält.
- **Output:** bestehende Vier-Kanal-Form `{subject, email_html, email_plain, telegram, sms}`
  (ADR-0011); Zweig c ergänzt `onset_detected: bool`.
- **Side effects:** keine — kein Versand, kein Throttle-/`alert_log`-Write, keine Persistenz.
  Bestandsverhalten der zwei existierenden Typen (`onset`, `changes`+`segment_times`) bleibt
  bit-identisch.

## Acceptance Criteria

- **AC-1:** Given ein Preview-Request enthält mehr als einen oder keinen der vier Payload-Typen (`changes`, `onset`, `official`, `nowcast_frames`), When der Endpoint aufgerufen wird, Then antwortet er mit HTTP 422 und einer Meldung, die alle vier zulässigen Typen benennt.
  - Test: vier Kombinationen (leer, zwei gleichzeitig, drei gleichzeitig, alle vier) real gegen den Endpoint schicken, 422 in jedem Fall nachweisen.

- **AC-2:** Given ein Preview-Request mit `changes`, aber ohne `segment_times`, für einen real geladenen Trip mit bekannten `segment_id`s, When der Endpoint gerendert wird, Then werden die Segment-Zeiten aus dem Trip synthetisiert und das Rendering liefert dieselbe Ausgabe wie ein äquivalenter Request mit explizit mitgelieferten `segment_times`.
  - Test: einmal mit synthetisierten, einmal mit explizit gleichwertigen `segment_times` denselben Trip anfragen, Antworten byte-identisch vergleichen.

- **AC-3:** Given ein Preview-Request mit `changes`, dessen `segment_id` im geladenen Trip nicht existiert, When der Endpoint gerendert wird, Then antwortet er mit HTTP 422 und einer Meldung, die die unbekannte `segment_id` benennt.
  - Test: `changes` mit einer erfundenen `segment_id` gegen einen realen Trip-Fixture schicken, 422 mit der ID im Fehlertext nachweisen.

- **AC-4:** Given ein Preview-Request mit `official` (Liste von `OfficialAlertPayload`), When der Endpoint gerendert wird, Then enthält die Antwort für alle fünf Felder (`subject`, `email_html`, `email_plain`, `telegram`, `sms`) nicht-leeren Text, der die übergebenen `hazard`/`level`/`label`-Werte widerspiegelt.
  - Test: eine `official`-Payload mit `source="geosphere_warn"`, `hazard="thunderstorm"`, `level=3`, `label="Gewitter"` senden, alle fünf Antwortfelder auf Inhalt prüfen (kein reiner String-Contains, sondern Struktur-/Wertevergleich gegen die erwartete Renderer-Ausgabe).

- **AC-5:** Given dieselbe `OfficialAlert`-Eingabe wird einmal über den Preview-Endpoint (`official`) und einmal direkt über `send_official_alert`s Renderer-Aufrufe (`build_official_alert_notices` → `render_official_alert_sms`/`render_official_alert_telegram`/`render_warn_block`) gerendert, When beide Ergebnisse verglichen werden, Then sind SMS-, Telegram- und HTML-Ausgabe byte-identisch (Fidelity, keine Zeile in der #1929-Sperrzone wird umgangen).
  - Test: gleiche `OfficialAlert`+`segment_ids` durch beide Pfade schicken, Textvergleich der drei Ausgaben.

- **AC-6:** Given ein Preview-Request mit `nowcast_frames`, dessen Frames einen Regen-Onset innerhalb des Nowcast-Horizonts enthalten, When der Endpoint gerendert wird, Then leitet er `onset_minutes`/`intensity_label`/`is_convective` über dieselbe `_derive_result`-Logik ab wie der Live-Radar-Pfad und rendert daraus ein vollständiges Preview mit `onset_detected: true`.
  - Test: Frames-Fixture mit bekanntem Onset (z. B. `precip_mm_h` über der Trockenschwelle in Frame 3) senden, `onset_minutes` und `sms`-Inhalt gegen die erwartete Ableitung prüfen.

- **AC-7:** Given ein Preview-Request mit `nowcast_frames`, dessen Frames keinen Regen-Onset im Nowcast-Horizont enthalten, When der Endpoint gerendert wird, Then antwortet er mit HTTP 200 und `onset_detected: false` sowie `null`-Renderfeldern, statt eine Exception zu werfen oder HTTP 500 zu liefern.
  - Test: Frames-Fixture ausschließlich mit `precip_mm_h` unter der Trockenschwelle senden, 200 + `onset_detected: false` nachweisen.

- **AC-8:** Given `RadarService.get_nowcast` schreibt (nach der S1-Erweiterung) einen Zweig-c-Mitschnitt, When die Datei gelesen wird, Then trägt jeder Frame-Eintrag zusätzlich zu `timestamp`/`precip_mm_h` das Feld `is_convective`, das dem tatsächlichen `RadarFrame.is_convective`-Wert entspricht.
  - Test: `get_nowcast` mit injizierten Frames aufrufen, von denen mindestens einer `is_convective=True` trägt, geschriebene Mitschnittdatei auf das Feld prüfen.

- **AC-9:** Given ein Preview-Request beliebigen Typs (inkl. `official` und `nowcast_frames`) wird verarbeitet, When der Response zurückkommt, Then wurde weder eine E-Mail/SMS/Telegram-Nachricht tatsächlich verschickt noch ein Eintrag in `alert_log` oder eine Throttle-Markierung geschrieben.
  - Test: vor und nach dem Request den Zustand von `alert_log`, Throttle-Store und (injiziertem) Mail-/SMS-Sink vergleichen — unverändert.

- **AC-10:** Given zwei verschiedene Nutzer A und B mit je eigenen Trips, When Nutzer A versucht, `alert-preview` für einen Trip von Nutzer B aufzurufen, Then antwortet der Endpoint mit HTTP 404, und ein Request mit dem jeweils eigenen Trip liefert für beide Nutzer unabhängig voneinander ein korrektes Rendering.
  - Test: zwei reale `user_id`-Werte mit je eigenem Trip-Fixture, Cross-User-Zugriff UND Self-Access für beide Nutzer prüfen.

- **AC-11:** Given ein Preview-Request im bestehenden Format (`onset` oder `changes`+explizit mitgelieferten `segment_times`), When der Endpoint nach dieser Erweiterung aufgerufen wird, Then ist die Antwort byte-identisch zum Verhalten vor dieser Scheibe (Bestandsschutz, bestehende Tests `test_issue_221_validator_endpoints.py`/`test_issue_918_alert_preview_4ch.py` bleiben grün ohne Anpassung).
  - Test: bestehende Testsuite unverändert laufen lassen; zusätzlich ein Request mit explizitem `segment_times` gegen den Endpoint vor und nach dem Merge vergleichen (Snapshot).

## Known Limitations

- **Zweig-b-Roh-Body-Replay ist NICHT Teil von S2.** Testmeldungen für Zweig b werden strukturiert
  als `OfficialAlertPayload` formuliert, nicht als roher Provider-Response. Die vier
  Provider-Parser (`geosphere_warn._extract_alerts`, `meteo_forets._extract_alert`,
  `meteoalarm._extract_alerts_from_cap`, `dpc._alerts_for_zone`) anzubinden würde die Scheibe
  sprengen — bleibt Folgearbeit, sollte der PO Roh-Replay für Zweig b priorisieren.
- DPC/CAP-XML-Provider werden von S1 gar nicht mitgeschnitten (`resp.json()`-Lücke bei
  XML-Antworten) — ein S1-Nebenbefund, kein S2-Blocker, da S2 ohnehin nur strukturierte
  `official`-Payloads entgegennimmt.
- `cooldown_display` bleibt bei Zweig-c-Replay immer `None` — ein echter Cooldown-Zustand
  existiert im zustandslosen Preview-Endpoint nicht und lässt sich aus reinen Frames nicht
  rekonstruieren.
- Kein serverseitiges Datei-Lesen per Pfadparameter — Testende müssen die S1-Mitschnittdatei
  selbst per `jq` extrahieren und im Request-Body übergeben (dokumentiertes Rezept oben).
- `official_alerts.py:1896-2104` (#1929-Sperrzone) bleibt unangetastet — nur aufgerufen.
- Keine neue Route ⇒ Go-Proxy (`internal/router/router.go:167`, `internal/handler/proxy.go:297-335`)
  bleibt unverändert.

## Open Questions

1. Bleibt der Zweig-c-Replay (`nowcast_frames`, Radar-Onset-Ableitung) Teil dieser Scheibe S2,
   oder wird er als eigene Scheibe S2b abgetrennt? **Empfehlung (Tech-Lead):** drinlassen —
   Mehrumfang gegenüber Zweig a+b allein liegt bei ~40-60 LoC, die `_derive_result`-Logik ist
   bereits vollständig entkoppelt aufrufbar, und eine Abtrennung würde die Verifikations-Kette
   für Format-Scheibe S3+ (die alle drei Zweige braucht) künstlich in zwei PRs zerreißen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweitert einen bereits etablierten, dokumentierten Endpoint (`alert-preview`,
  ADR-0011 Mehrkanal-Preview) additiv um zwei neue exklusive Payload-Typen — keine neue Route,
  keine neue Persistenztechnologie, keine Rücknahme einer bestehenden Architekturentscheidung.
  Kein ADR-würdiger Grundsatzentscheid.

## Changelog

- 2026-08-18: Initial spec created (Scheibe S2 aus #1948, Tech-Lead-Design-Entscheide 2026-08-18).
