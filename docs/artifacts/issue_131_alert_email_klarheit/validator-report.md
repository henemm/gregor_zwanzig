# External Validator Report

**Spec:** `docs/specs/modules/issue_131_alert_email_klarheit.md`
**Datum:** 2026-05-14T06:45+02:00
**Server:** https://staging.gregor20.henemm.com
**Validator-Modus:** Isoliert (kein src/, kein git, kein docs/artifacts/ der Implementierer-Session)

## Vorbemerkung

Diese Spec ist code-zentriert: Sie verlangt Verhalten von Python-Funktionen
(`format_metric_value`, `format_change_line`, `build_segment_label`,
`WeatherChange.segment_id`, `from_display_config`) und das Entfernen von
totem Code in `src/formatters/trip_report.py`.

Als External Validator habe ich nur Zugriff auf:

1. Die laufende App via HTTPS (`https://staging.gregor20.henemm.com`)
2. Die Spec selbst

Ich darf **nicht** in `src/`, `git log`, `git diff` oder `docs/artifacts/`
(Implementierer-Spuren) lesen.

## Verfügbarkeits-Probe

| Probe | Ergebnis |
|-------|----------|
| `GET /api/health` | `200 {"python_core":"ok","status":"ok","version":"0.1.0"}` |
| `GET /api/scheduler/status` | `200`, fünf Jobs, alle `last_run: null`, scheduler `running: true` |
| `GET /api/trips` (mit Validator-Cookie) | `200`, 9 Trips sichtbar, davon 1 mit `display_config` (`validator-test-with-dc`) |

Server läuft, Validator-Cookie greift.

## Sichtbarkeits-Analyse pro Acceptance Criterion

Für jedes AC wurde geprüft, ob das beschriebene Verhalten von außen
(also ohne Code-Zugriff) beobachtbar ist.

| # | Expected Behavior (Kurzform) | Beobachtbar über öffentliche API? | Verdict |
|---|------------------------------|-----------------------------------|---------|
| AC-1 | `WeatherChange.segment_id` immer gesetzt | **Nein** — internes Detector-Feld, kein Endpoint exponiert | UNKLAR |
| AC-2 | `from_display_config` nutzt `enabled` statt `alert_enabled` | **Nein** — interner Detector-Bau, kein Preview-/Trace-Endpoint | UNKLAR |
| AC-3 | Fallback auf `from_trip_config()` bei fehlender `display_config` | **Nein** — selber Detector-Pfad ohne API-Sichtbarkeit | UNKLAR |
| AC-4 | `format_metric_value("m", 12240.0) == "12.240 m"` | **Nein** — Pure-Function ohne API-Wrap | UNKLAR |
| AC-5 | `format_metric_value("%", 63.0) == "63 %"` / signed `"+34 %"` | **Nein** — Pure-Function ohne API-Wrap | UNKLAR |
| AC-6 | `format_metric_value("°C", 12.5) == "12,5 °C"` / `"−2,3 mm"` | **Nein** — Pure-Function ohne API-Wrap | UNKLAR |
| AC-7 | `format_change_line(...)` rendert "Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)" | **Nein** — kein Render-Preview-Endpoint | UNKLAR |
| AC-8 | HTML- und Plain-Mail haben je eine Zeile pro Change mit Segment-Bezug | **Nein** — kein Mail-Preview, kein Trigger, kein Mail-Verlauf-Endpoint; Scheduler-`last_run` für `alert_checks` ist `null` (Job ist seit Start nicht gelaufen, nächster Lauf 2026-05-14T09:00) | UNKLAR |
| AC-9 | `grep "Wetteränderungen" src/formatters/trip_report.py` ist leer | **Verboten** — Validator darf `src/` nicht lesen | UNKLAR |

## Endpoint-Probing (negativ-Beweis)

Geprüfte Pfade, alle `404`:

```
/api/alert/test                  /api/alerts/test
/api/alerts                      /api/alerts/history
/api/changes                     /api/weather-changes
/api/alert/preview               /api/email/preview
/api/preview                     /api/email/test
/api/render-alert                /api/render/alert
/api/render/change-line          /api/send-alert
/api/email/send-test             /api/trips/<id>/alert
/api/trips/<id>/alert/test       /api/trips/<id>/alerts
/api/trips/<id>/alert-preview    /api/trips/<id>/email-preview
/api/trips/<id>/report-preview   /api/trips/<id>/preview
/api/trips/<id>/forecast         /api/validator/alert-preview
/api/validator/format-metric     /api/format-metric-value
/api/_validator/format-metric    /api/_debug/last-alert
/api/scheduler/jobs              /api/scheduler/run/alert_checks
/api/scheduler/trigger/alert_checks
/api/scheduler/jobs/alert_checks/run
/api/auth/me                     /api/auth/whoami
/api/_routes                     /api/_internal/alert/trigger
```

→ Es existiert **kein** öffentlicher Endpoint, mit dem die in der Spec
versprochenen Format-Resultate oder das Alert-Mail-Rendering geprüft
werden können. Der Scheduler-Job `alert_checks` hat seit Start nicht
gefeuert (`last_run: null`, nächster Lauf 09:00) — selbst wenn er
liefe, würde die resultierende E-Mail an einen echten Empfänger gehen
und mir nicht als Validator-Artefakt zur Verfügung stehen.

## Findings

### Finding 1 — Komplette Spec ist von außen nicht widerlegbar
- **Severity:** HIGH (blockiert Validierung)
- **Expected:** AC-1 bis AC-9 mit beobachtbarem Output prüfen
- **Actual:** Acht von neun Kriterien betreffen interne Funktionen ohne
  API-Sichtbarkeit. Das neunte (AC-9) ist explizit ein Code-Grep, den
  ich als External Validator nicht durchführen darf. Die App liefert
  keine Preview-/Trace-/Last-Mail-Endpoints.
- **Evidence:** Endpoint-Probing-Tabelle oben, alle 404.

### Finding 2 — Spec verlangt Verifikation, gibt aber keinen Pfad dafür
- **Severity:** MEDIUM (Prozess-Problem)
- **Expected:** Spec hat 9 ACs in Given/When/Then-Form — der External
  Validator soll laut Setup das Ergebnis von außen widerlegen können.
- **Actual:** ACs sind als Unit-Test-Vorlagen formuliert
  (`format_metric_value("m", 12240.0)` → String). Sie sind durch
  pytest beweisbar, aber nicht durch HTTP. Eine Lücke zwischen
  „Spec verlangt es" und „Validator kann es prüfen".
- **Evidence:** Spec-Sektion „Acceptance Criteria" Z. 242-298.

## Empfehlung zur Beobachtbarkeit (vor erneutem Validator-Lauf)

Mindestens **einer** der folgenden Endpoints sollte existieren, damit
diese Spec von außen sinnvoll prüfbar wird (gemäß Memory-Regel „Bei
AMBIGUOUS Sichtbarkeit nachrüsten"):

1. **`GET /api/_validator/format-metric?unit=m&value=12240`**
   → `{"formatted": "12.240 m"}` — würde AC-4 bis AC-6 abdecken.

2. **`POST /api/trips/<id>/alert-preview`** mit synthetischen
   `WeatherChange`-Daten im Body → liefert die generierten HTML- und
   Plain-Text-Mails zurück. Würde AC-7 und AC-8 abdecken.

3. **`GET /api/_validator/detector-thresholds?trip=<id>`**
   → zeigt die vom Detector aufgebauten Thresholds + welchen
   Konfig-Pfad er genommen hat (`from_display_config` /
   `from_trip_config`). Würde AC-2 und AC-3 abdecken.

Ohne mindestens einen davon bleibt die Spec für einen isolierten
External Validator unprüfbar.

## Verdict: AMBIGUOUS

### Begründung

Die Spec ist von außen nicht widerlegbar **und** nicht bestätigbar:

- Die geforderten Änderungen leben fast vollständig in internen
  Python-Funktionen ohne API-Oberfläche.
- AC-9 verlangt explizit Code-Lese-Zugriff (`grep src/...`), den der
  External Validator nicht hat.
- Der Scheduler-Job `alert_checks` ist seit Server-Start nicht
  gefeuert (`last_run: null`), und selbst sein Output (eine echte
  Alert-Mail an einen User) wäre dem Validator nicht zugänglich.
- Es gibt keinen Test-/Preview-/Trace-Endpoint.

Das ist kein BROKEN (ich habe keine widerlegende Evidenz gefunden) und
kein VERIFIED (ich habe auch keine bestätigende Evidenz). Daher
**AMBIGUOUS**.

Nächster Schritt: Mindestens einen der oben genannten Sichtbarkeits-
Endpoints einbauen, dann erneut validieren. Alternativ kann der Owner
diese Spec als „nur durch pytest verifizierbar" einstufen und auf den
External-Validator-Lauf bewusst verzichten — dann wäre das hier kein
Block, sondern eine dokumentierte Lücke.
