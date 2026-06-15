# Context: Issue #830 — Radar-Alert-Mail testbar machen

## Request Summary
Radar-Alert-Mails haben keinen dedizierten Validator und keinen Test-Seam: echter Regen ist nötig
um den Alert auszulösen. Gefordert: Staging-Trigger-Endpoint + `radar_alert_mail_validator.py` + Gate-Erweiterung.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/services/trip_alert.py:550–696` | `check_radar_alerts()` — baut Mail-Body inline, kein `mail_type`-Header gesetzt |
| `src/services/radar_service.py` | `RadarNowcastService`, `NowcastResult`, `format_now_text()` |
| `src/outputs/email.py` | `EmailOutput.send()` / `build_mime_message()` — nimmt `mail_type` seit #733 |
| `api/routers/scheduler.py` | Referenz-Pattern für neue Router; `trigger_radar_alert_checks()` vorhanden |
| `api/main.py` | Router-Registrierung |
| `src/app/config.py` | `Settings` (GZ_-Prefix, pydantic-settings) — `GZ_ENV` fehlt noch |
| `.claude/hooks/briefing_mail_validator.py` | Referenzimplementierung Validator |
| `.claude/hooks/email_spec_validator.py` | Referenzimplementierung 2 |
| `.claude/hooks/renderer_mail_gate.py` | Gate — `_MAIL_PATTERNS` muss erweitert werden |
| `/home/hem/henemm-infra/systemd/gregor-python-staging.service` | Staging liest `.env` aus `gregor_zwanzig_staging/` |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Bestehende Radar-Alert-Tests (Referenz) |
| `tests/tdd/test_773_alert_e2e.py` | Radar-Alert-E2E-Referenz |
| `tests/tdd/test_issue_733_briefing_mail_validator.py` | Validator-Test-Referenz |

## Existing Patterns

### Mail-Typ-Header (seit #733)
`EmailOutput.send(subject, body, plain_text_body=..., mail_type="xyz")` → setzt `X-GZ-Mail-Type` Header.
Radar-Alert-Call in `trip_alert.py:675` übergibt `mail_type` **nicht** — das muss ergänzt werden.

### Staging-Detection
`GZ_ENV` existiert **nicht** im Settings-Modell. Staging-Service liest `.env` aus
`/home/hem/gregor_zwanzig_staging/.env`. Lösung: `GZ_ENV: str = "production"` in Settings
hinzufügen → Staging setzt `GZ_ENV=staging` in seiner `.env`.

### Validator-Pattern (briefing_mail_validator.py)
- IMAP-Fetch aus `gregor-test@henemm.com` (Creds via `GZ_IMAP_*`)
- Erkennt Mail am `X-GZ-Mail-Type`-Header
- Falscher Mail-Typ → No-Op (Exit 0)
- Fehlender Header → Exit 1
- Plausibilitätsprüfung (nicht String-Presence)
- Schreibt YAML-Log in `.claude/workflows/_log/`

### Renderer-Mail-Gate (#811)
Blockiert `git commit` wenn Mail-Inhalts-Dateien gestaged sind und kein frischer Nachweis vorliegt.
Aktuelle Patterns: `src/output/renderers/email/*.py`, `src/formatters/*.py`, `src/outputs/email.py`.
**Lücke:** `src/outputs/radar_alert.py` fehlt in den Patterns (und die Datei existiert noch nicht).

### Router-Registration
Neuer Router `api/routers/debug.py` → in `api/main.py` eintragen (nur Staging-guarded, kein
Nginx-Exposure nötig da Port 8001 intern).

## Dependencies

- **Upstream:** `trip_alert.TripAlertService.check_radar_alerts()`, `radar_service.RadarNowcastService`
- **Downstream:** `renderer_mail_gate.py` konsumiert Log aus `radar_alert_mail_validator.py` (neues Gate)
- **Staging-ENV:** `/home/hem/gregor_zwanzig_staging/.env` muss `GZ_ENV=staging` erhalten

## Extraction-Entscheidung

Der Radar-Alert-Body wird aktuell **inline in `check_radar_alerts()`** gebaut (trip_alert.py:644–665).
Die Spec erwartet `src/outputs/radar_alert.py` als neue Datei — daher wird der Body in eine
pure Funktion `build_radar_alert_body(result, segment_label, cooldown_display, source_label)` extrahiert.
Das macht den Gate-Scope präzise und testbar ohne Side-Effects.

## Risks & Considerations

- **`GZ_ENV`-Addition zu Settings:** keine Breaking-Change, Default `"production"` → Prod-Verhalten unverändert
- **Staging-.env:** muss manuell `GZ_ENV=staging` erhalten (1-Zeilen-Schritt, aber nicht automatisiert)
- **Trigger-Endpoint braucht Test-Trip:** Endpoint muss einen beliebigen aktiven Trip laden (oder
  Fallback auf fest-kodierten Test-Trip); kein HTTP-Parameter für trip_id (Spec: Response enthält `trip_id`)
- **Validator findet "falsche" Mail:** max_scan=50 + X-GZ-Mail-Type-Filter → robust gegen parallele Mails
- **Gate-Extension:** `radar_alert_mail_validator.py` schreibt eigenes Log-File-Pattern
  (`*_radar_alert_validation.yaml`) — Gate muss diesen Pattern-Namen kennen

## Existing Specs

- `docs/specs/modules/radar_nowcast.md` — Radar-Nowcast-Spec
- `docs/reference/mail_validators.md` — Validator-Dispatch-Tabelle (muss ergänzt werden)
- `docs/specs/modules/briefing_mail_validator.md` — Validator-Referenz-Spec
