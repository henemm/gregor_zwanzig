---
entity_id: issue_1113_partial_outage_guard
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [briefing, scheduler, weather, incident, bug]
---

<!-- Issue #1113 — Trip-Briefing Teilausfall-Guard -->

# Issue 1113 — Trip-Briefing Teilausfall-Guard (>75 %-Schwelle + Retry + Hinweis)

## Approval

- [x] Approved (PO 'go' 2026-07-08)

## Purpose

Verhindert, dass ein Trip-Briefing mit größtenteils fehlenden Wetterdaten unbemerkt
versendet wird. Der bestehende Totalausfall-Guard (#1012) greift nur bei 100 % Ausfall
aller Segmente; beim Incident vom 2026-07-08 (open-meteo 503, 5 von 6 Segmenten ohne
Daten) ging das Briefing trotzdem unverändert raus. Erweitert den Guard auf eine
Schwelle (>75 % fehlende Segmente → zurückhalten wie Totalausfall), fügt bei
Teilausfall unterhalb der Schwelle einen deutlichen Hinweis auf die fehlenden
Abschnitte hinzu, und mildert kurze 503-Aussetzer durch Retry/Backoff beim
Wetter-Fetch pro Segment ab.

## Source

- **File:** `src/services/trip_report_scheduler.py` — `_send_trip_report_outcome()`
  (Guard, ca. Z.616-654), `_fetch_weather()` (Fetch-Schleife mit Error-Platzhaltern,
  ca. Z.904-943), `_process_pending_markers()` (Nachliefer-Mechanik #1012, ca. Z.213 ff.
  — bleibt unverändert, nutzt dieselbe Schwelle mit)
- **File:** `src/services/notification_service.py` — `TripReportRequest` (DTO,
  ca. Z.54-90, neues Feld für den Teilausfall-Hinweis), `_apply_prefixes()`
  (Präfix-Injektion E-Mail/Telegram, ca. Z.556-590, Vorbild `catchup_prefix`)

> Python-Core-Backend (`src/services/`) — kein Frontend-, kein Go-API-Anteil.
> Renderer-Dateien (`src/output/renderers/email/*`, Renderer-Commit-Gate #811)
> werden NICHT angefasst — der Hinweis läuft über den bestehenden
> Präfix-Injektions-Mechanismus in `notification_service.py`, analog zu
> `catchup_prefix`.

## Estimated Scope

- **LoC:** ~+80/-10 (unter 250-Limit)
- **Files:** 2 Source (`trip_report_scheduler.py`, `notification_service.py`)
  + 1 neue Testdatei (`tests/tdd/test_issue_1113_partial_outage_guard.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_send_no_data_hint`-Pfad (#1012) | intern | Totalausfall-Zweig wird bei >75 % Ausfall identisch mitgenutzt (Hinweis-Mail + `_write_pending_marker`) |
| `_process_pending_markers()` (#1012 b2) | intern | Nachliefer-Mechanik bleibt unverändert, schließt mit der neuen Schwelle konsistent an den Incident-Verlauf an |
| `catchup_prefix`-Mechanismus (`notification_service.py`, `_apply_prefixes`) | intern | Vorbild/Mechanik für den neuen Teilausfall-Hinweis in E-Mail (Plain+HTML) und erster Telegram-Bubble |
| `_fetch_weather(provider=...)`-Injection-Seam (Issue #483 Demo-Mode-Muster) | intern | Mock-freier Test-Zugang für 503-Simulation via FixtureProvider |
| On-Demand-Pfad (`on_demand=True`, #1007) | intern | Muss weiterhin weder Hinweis-Versand noch Marker erzeugen — Guard-Erweiterung darf diese Ausnahme nicht brechen |
| `tests/tdd/test_issue_1012_no_data_guard.py` | Test | Regressionsschutz — muss nach dem Fix weiterhin grün sein |

## Implementation Details

**(a) Schwelle statt Total-Ausfall — `_send_trip_report_outcome()`.** Ersetzt die
binäre Prüfung `all(s.has_error for s in segment_weather)` durch eine
Verhältnis-Berechnung:

```
error_count = sum(1 for s in segment_weather if s.has_error)
error_ratio = error_count / len(segment_weather) if segment_weather else 1.0

if not segment_weather or error_ratio > 0.75:
    # identischer Zweig wie bisheriger Totalausfall (#1012):
    # send_no_data_hint + _write_pending_marker, return "no_weather"
    ...
elif error_count > 0:
    # Teilausfall unterhalb der Schwelle: Hinweis-Präfix statt Rückhalten
    missing = ", ".join(s.segment.name for s in segment_weather if s.has_error)
    request.partial_outage_hint = (
        f"Hinweis: Für folgende Abschnitte liegen aktuell keine Wetterdaten vor "
        f"({missing}) — eine Aktualisierung wird nachgeliefert."
    )
```

Die `>0.75`-Schwelle ist strikt "mehr als 75 %" (3/4 = 75 % sendet noch,
5/6 ≈ 83 % wird zurückgehalten — siehe AC-3). Der Rückhalte-Zweig bleibt
bit-identisch zum bestehenden #1012-Code (gleicher `send_no_data_hint`-Aufruf,
gleicher `_write_pending_marker`-Aufruf, gleicher `return "no_weather"`) —
On-Demand-Ausnahme (`if not on_demand:`) bleibt erhalten.

**(b) Teilausfall-Hinweis — `notification_service.py`.** Neues Feld
`partial_outage_hint: str | None = None` auf `TripReportRequest` (analog
`catchup_prefix`), neuer Zweig in `_apply_prefixes()`:

```
elif request.partial_outage_hint:
    if report.email_plain:
        report.email_plain = f"{request.partial_outage_hint}\n\n{report.email_plain}"
    if report.email_html:
        report.email_html = self._inject_html_hint(report.email_html, request.partial_outage_hint)
    if report.telegram_bubbles:
        report.telegram_bubbles[0] = f"{request.partial_outage_hint}\n\n{report.telegram_bubbles[0]}"
```

Kein Eingriff in Renderer-Dateien — `_inject_html_hint` existiert bereits und
wird wiederverwendet.

**(c) Retry/Backoff — `_fetch_weather()`.** Pro Segment bis zu 2 Wiederholungen
bei Exception, mit kurzem Backoff (z. B. 1s/2s), bevor der `has_error=True`-
Platzhalter erzeugt wird:

```
for segment in segments:
    for attempt in range(RETRY_ATTEMPTS + 1):  # RETRY_ATTEMPTS = 2
        try:
            data = service.fetch_segment_weather(segment, enrich_ensemble=False)
            weather_data.append(data)
            break
        except Exception as e:
            if attempt < RETRY_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
                continue
            logger.error(f"Weather fetch failed for segment {segment.segment_id} after retries: {e}")
            weather_data.append(SegmentWeatherData(..., has_error=True, ...))
```

Retry-Budget bewusst klein gehalten (2 Versuche, Sekunden-Backoff), damit der
synchrone 5-Minuten-Cron-Lauf über alle User nicht gesprengt wird. Der
Injection-Seam `provider=` bleibt für Tests nutzbar — ein FixtureProvider kann
pro Segment gezielt N-mal fehlschlagen, um Retry-Erschöpfung zu simulieren.

## Expected Behavior

- **Input:** `segment_weather`-Liste aus `_fetch_weather()` mit einem Mix aus
  validen und `has_error=True`-Segmenten (Fehlerquote 0–100 %)
- **Output:**
  - Fehlerquote > 75 %: kein Briefing-Versand, stattdessen Hinweis-Nachricht
    („Wetterdienst nicht erreichbar …") + Pending-Marker (identisch zu #1012)
  - Fehlerquote 0 % < x ≤ 75 %: Briefing wird versendet, mit Hinweis-Zeile zu
    den fehlenden Abschnitten in E-Mail (Plain+HTML) und erster Telegram-Bubble
  - Fehlerquote 0 %: unverändertes Verhalten
- **Side effects:** Retry verlängert die Laufzeit von `_fetch_weather()` pro
  fehlgeschlagenem Segment um bis zu `RETRY_ATTEMPTS * BACKOFF_SECONDS`-Sekunden;
  On-Demand-Pfad (`on_demand=True`) erzeugt in keinem Zweig Marker/Hinweis-Versand

## Acceptance Criteria

- **AC-1:** Given ein regulärer Trip-Briefing-Lauf, bei dem mehr als 75 % der
  Etappen-Segmente keine Wetterdaten liefern (z. B. 5 von 6) / When der Versand
  ansteht / Then wird kein Briefing versendet, sondern die kurze Hinweis-Nachricht
  („Wetterdienst nicht erreichbar …") über die konfigurierten Kanäle versendet und
  ein Nachliefer-Marker geschrieben — identisch zum bestehenden
  Totalausfall-Verhalten (#1012).
  - Test: Echter Trip mit 6 Segmenten, FixtureProvider liefert für 5 Segmente
    einen Fehler; `_send_trip_report_outcome()` liefert `"no_weather"`, echte
    Hinweis-Mail wird an `gregor-test@henemm.com` zugestellt (IMAP-Verifikation),
    `pending_briefings.json` enthält einen neuen Eintrag.

- **AC-2:** Given ein Lauf mit mindestens einem, aber höchstens 75 % fehlenden
  Segmenten (z. B. 1 von 6) / When das Briefing versendet wird / Then enthält es
  an oberster Stelle einen deutlichen Hinweis, welche Abschnitte ohne Daten sind
  und dass eine Aktualisierung nachgeliefert wird — in E-Mail (HTML und
  Plaintext) und in der ersten Telegram-Bubble (Mechanik analog `catchup_prefix`).
  - Test: Echter Trip mit 6 Segmenten, FixtureProvider liefert für 1 Segment
    einen Fehler; zugestellte Test-Mail (IMAP) enthält den Hinweistext samt
    Segment-Bezeichnung an oberster Stelle in Plain- und HTML-Teil.

- **AC-3:** Given exakt 75 % fehlende Segmente (3 von 4) / Then wird gesendet
  (Schwelle ist strikt „mehr als 75 %"); Given 5 von 6 fehlend (83 %) / Then
  wird zurückgehalten.
  - Test: Zwei echte Läufe (4-Segment-Trip mit 3 Fehlern; 6-Segment-Trip mit
    5 Fehlern) beweisen die Grenzfälle je gegen die tatsächliche
    `_send_trip_report_outcome()`-Rückgabe und den Mail-Zustellstatus.

- **AC-4:** Given der Wetter-Provider antwortet für ein Segment mit einem
  transienten Fehler (z. B. HTTP 503) / When das Segment abgerufen wird / Then
  wird der Abruf bis zu 2-mal mit kurzem Backoff wiederholt, bevor das Segment
  als fehlerhaft (`has_error`) gilt.
  - Test: FixtureProvider wirft für ein Segment beim 1. und 2. Versuch einen
    Fehler und liefert beim 3. Versuch valide Daten — `_fetch_weather()`
    liefert für dieses Segment `has_error=False` mit echten Werten (kein
    Erschöpfungs-Fall). Zweiter Test: FixtureProvider wirft durchgehend 3×
    Fehler — Segment landet nach genau 3 Versuchen als `has_error=True`.

- **AC-5:** Given On-Demand-Abruf (#1007) oder manueller Test-Versand / Then
  erzeugt der neue Guard weder Hinweis-Versand noch Nachliefer-Marker
  (bestehende Semantik unverändert).
  - Test: Gleicher Teilausfall-/Totalausfall-Fall wie AC-1/AC-2, aber mit
    `on_demand=True` bzw. Test-Versand-Pfad — keine neue Hinweis-Mail, kein
    neuer Eintrag in `pending_briefings.json`.

- **AC-6:** Given Totalausfall aller Segmente / Then bleibt das Verhalten aus
  #1012 unverändert (Hinweis + Marker + stündliche Nachlieferung); bestehende
  Tests `tests/tdd/test_issue_1012_no_data_guard.py` bleiben grün.
  - Test: `uv run pytest tests/tdd/test_issue_1012_no_data_guard.py` läuft nach
    der Implementierung ohne Anpassung grün durch.

## Known Limitations

- Provider-Fallback auf alternative Wetterdienste (brightsky/geosphere) ist
  bewusst außerhalb dieses Fixes — separates Issue #1115.
- Monitoring-Sichtbarkeit für Teilausfälle (z. B. eigener Status im
  `/api/scheduler/status`-Endpoint) ist bewusst außerhalb dieses Fixes —
  separates Issue #1114.
- Die Schwelle (>75 %) und das Retry-Budget (2 Versuche) sind fest im Code
  verankert, nicht pro Trip/User konfigurierbar — PO-Entscheidung 2026-07-08
  hält das für ausreichend, da die Schwelle ein Betriebs-, kein Nutzer-Parameter
  ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweitert einen bestehenden, bereits spezifizierten Guard-
  Mechanismus (#1012) um eine Schwelle und wiederverwendet den bestehenden
  Präfix-Injektions-Mechanismus (`catchup_prefix`-Vorbild) — keine neue
  Architektur-Entscheidung, reine Erweiterung etablierter Muster.

## Changelog

- 2026-07-08: Implementiert inkl. Adversary-Fixes F001-F005 + has_error-Rückgabepfad bestätigt
- 2026-07-08: Initial spec erstellt — Issue #1113, Incident-getrieben (Root
  Cause 2026-07-07/08 open-meteo-Ausfall, Log-Forensik in
  `docs/context/fix-1113-partial-outage-guard.md`)
