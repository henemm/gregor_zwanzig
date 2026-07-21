---
entity_id: issue_918_alert_preview_4ch
type: module
created: 2026-06-30
updated: 2026-06-30
status: draft
version: "1.0"
tags: [alert, preview, renderer, slice-3, issue-918]
---

# Alert-Vorschau über alle vier Kanäle (Slice 3 von #914)

## Approval

- [ ] Approved

## Purpose

Die Alert-Vorschau im Frontend soll für einen synthetischen Alert **exakt das**
zeigen, was auch versendet würde — und zwar für **alle vier Kanäle** (Betreff,
E-Mail, Telegram, SMS). Heute liefert der Vorschau-Endpunkt nur E-Mail-HTML und
erzeugt sie über den **alten** `TripReportFormatter`-Pfad statt über den
kanonischen Slice-2-Renderer (#917). Slice 3 schließt diese Lücke: ein Renderer,
ein Ergebnis — Vorschau == Versand.

## Source

- **File:** `api/routers/validator.py` — `alert_preview` (POST `/api/trips/{id}/alert-preview`)
- **File:** `src/output/renderers/alert/` — kanonische Renderer (`render_subject`,
  `render_email`, `render_telegram`, `render_sms`) + Projektion (`to_alert_message`)
- **File:** `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte`
- **File:** `tests/integration/test_issue_221_validator_endpoints.py` (AC-4 anpassen)

## Estimated Scope

- Files: 3 MODIFY (Backend-Endpunkt, Frontend-Karte, Integrationstest)
- LoC: ~+90 / -40
- Risk: LOW–MEDIUM (nur Vorschau/Tooling-Pfad + isolierte Frontend-Karte; kein
  Versand, kein Scheduler, keine Persistenz, keine Auth)

## Dependencies

- Upstream: Slice 2 (#917) — `src/output/renderers/alert/render.py` + `project.py`.
- Downstream: Go-Proxy `internal/handler/proxy.go::AlertPreviewProxyHandler`
  (reicht JSON transparent durch → **keine** Änderung nötig).
- Out of scope: Briefing-SMS-Fidelity (`ChannelFidelitySMS.svelte`) → **#923**.

## Implementation Details

1. **Endpunkt (`alert_preview`):** statt `TripReportFormatter().format_email(...)`:
   - `msg = to_alert_message(changes, segments, trip_obj.name, tz=UTC, stand_at=<now HH:MM>)`
   - `subject = render_subject(msg)`
   - `email_html, email_plain = render_email(msg)`
   - `telegram = render_telegram(msg)`
   - `sms = render_sms(msg)`
   - Response: `{"subject", "email_html", "email_plain", "telegram", "sms"}`.
   - `user_id`-Mandantentrennung (Query, vom Proxy injiziert) bleibt unverändert;
     **kein** `"default"`-Fallback im authentifizierten Pfad.
2. **Frontend (`AlertPreviewCard.svelte`):** Response-Typ auf
   `{subject, email_html, email_plain, telegram, sms}`. Anzeige:
   - Betreff als eigene Zeile (`data-testid="alert-preview-subject"`)
   - E-Mail als iframe `srcdoc={email_html}` (`alert-preview-iframe`, bestehend)
   - Telegram als Textblock (`alert-preview-telegram`)
   - SMS als Mono-Block mit Zeichen-Zähler (`alert-preview-sms`)
3. **Test `test_issue_221` AC-4:** erwartete Plain-Zeile auf das kanonische
   Renderer-Format umstellen (Werte 12.240 m / 38.440 m / Schwelle 1.000 m bleiben
   prüfbar). AC-5 (seiteneffektfrei) und AC-6 (404) unverändert gültig.

## Expected Behavior

Ein POST mit Changes + Segment-Zeiten liefert vier zueinander konsistente,
plausible Kanal-Texte. Die Frontend-Karte rendert alle vier sichtbar. Es werden
keine E-Mails versendet und keine Throttle-/Snapshot-Dateien geschrieben.

## Acceptance Criteria

- **AC-1:** Given ein gültiger Trip eines Users mit ≥1 Change im Body / When POST
  `/api/trips/{id}/alert-preview?user_id=<eigner>` aufgerufen wird / Then enthält
  die JSON-Antwort die nicht-leeren String-Felder `subject`, `email_html`,
  `email_plain`, `telegram` und `sms`.

- **AC-2:** Given derselbe Request / When die vier Texte erzeugt werden / Then
  stammen sie nachweislich aus dem kanonischen Slice-2-Renderer
  (`src/output/renderers/alert/render.py`) — d.h. `subject` beginnt mit
  `[<trip_short>]`, `email_html` ist ein `<html>`-Dokument mit der Renderer-H1, und
  `sms` ist reines ASCII mit Länge ≤ 140 (keine Ausgabe des alten
  `TripReportFormatter`).

- **AC-3:** Given ein Body mit Sichtweite-Change (`old=12240, new=38440,
  threshold=1000`) / When der Endpunkt rendert / Then enthält `email_plain` die
  kanonische Change-Zeile mit den formatierten Werten `12.240 m`, `38.440 m` und
  der Schwelle `1.000 m`, und `email_html` enthält dieselben Werte.

- **AC-4:** Given derselbe Vorschau-Request wird 3× hintereinander gesendet / When
  jeweils 200 zurückkommt / Then bleibt die Mtime der Throttle-/Snapshot-Dateien
  des Users unverändert (Endpunkt ist strikt seiteneffektfrei, kein SMTP).

- **AC-5:** Given ein Trip, der User B gehört / When User A (oder ein nicht
  existierender User) `/api/trips/{id}/alert-preview?user_id=A` aufruft / Then
  antwortet der Endpunkt mit 404 und gibt **keine** Renderer-Texte preis
  (kein Cross-User-Datenleck).

- **AC-6:** Given die geladene Alerts-Tab-Vorschau im Frontend mit ≥1 aktiver
  Alert-Regel / When der Nutzer „Vorschau laden" klickt / Then zeigt
  `AlertPreviewCard` sichtbar getrennt Betreff, E-Mail (iframe), Telegram-Text und
  SMS-Text (Test-IDs `alert-preview-subject`, `alert-preview-iframe`,
  `alert-preview-telegram`, `alert-preview-sms`), gespeist ausschließlich aus der
  Backend-Antwort (kein TS-Renderer im Frontend, ADR-0011).

## Known Limitations

- Bei synthetischen Stub-Segmenten ist `distance_from_start_km` 0.0 → die
  km-Spanne in der Vorschau kann „km 0–0" zeigen. Akzeptierte Limitation: die
  Vorschau prüft **Format-Treue**, nicht reale Geografie.
- `occurred_at` wird vom Vorschau-Body nicht geliefert → SMS-Token ohne `@HH`.
  Entspricht dem definierten Verhalten des Renderers.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Vorschau zieht fertige Texte vom Backend; kein zweiter
  Renderer in TypeScript). Slice 3 ist die Frontend-seitige Erfüllung dieser ADR
  für den Alert-Pfad.

## Changelog

- 2026-06-30: Initiale Spec (Slice 3 von #914, Issue #918).
