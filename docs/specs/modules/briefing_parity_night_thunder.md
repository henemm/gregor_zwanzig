---
entity_id: briefing_parity_night_thunder
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [renderer, scheduler, briefing, mail, night-block, thunder-forecast]
---

<!-- Issue #1313 — Briefing-Parität Morgen/Abend -->

# Briefing-Parität Morgen/Abend (Issue #1313)

## Approval

- [ ] Approved

## Purpose

Zwei PO-Entscheidungen vom 2026-07-18 zur E-Mail-Briefing-Struktur:
**E1** unterdrückt die Sektion „⚡ Gewitter-Vorschau" in E-Mail-Briefings genau
dann, wenn der Mehrtages-Ausblick in derselben Mail aktiv ist (beide zeigen
seit #1275 dieselbe Datenquelle — Dopplung). **E2** hebt das Nacht-Block-Gate
`report_type == "evening"` auf zwei Codestellen auf, sodass „🌙 Nacht am Ziel"
auch im Morgenbriefing erscheint, gesteuert ausschließlich über
`dc.show_night_block`.

## Source

- **File:** `src/output/renderers/email/html.py:1084-1097` — E1: HTML-Rendering der Gewitter-Vorschau
- **File:** `src/output/renderers/email/html.py:1271-1279` — E1: `show_outlook`/`trend_html`-Handling, Quelle für `outlook_active`
- **File:** `src/output/renderers/email/plain.py:235-244` — E1: Plain-Text-Pendant der Gewitter-Vorschau
- **File:** `src/services/trip_report_scheduler.py:830` — E2: Fetch-Gate für `night_weather` in `_fetch_night_weather()`
- **File:** `src/output/renderers/trip_report.py:109` — E2: Render-Gate für `night_rows`

> **Schicht:** Python-Core / Domain-Backend (`src/services/`, `src/output/renderers/`) — FastAPI Core (`api.main:app`), kein Go-/Frontend-Anteil betroffen.

## Estimated Scope

- **LoC:** ~15-25 (4 Zeilen Logik + Tests)
- **Files:** 4 Quelldateien + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_build_thunder_forecast_from_trend_or_fetch` (`trip_report_scheduler.py:1495`, #1275) | intern | Baut `thunder_forecast` EINMAL kanalübergreifend — bleibt UNVERÄNDERT, Suppression darf nicht hier passieren (sonst verliert SMS/Telegram das TH+-Token) |
| `report_config_resolver.py:131` (`show_multi_day_trend`, #1208) | intern | Bestimmt pro Report-Typ, ob der Ausblick aktiv ist (Default `["evening"]`, `src/app/loader.py:835`) — kein Änderungsbedarf |
| `dc.show_night_block` (`UnifiedWeatherDisplayConfig`) | intern | Einfaches Config-Feld, Default `True`, gilt bereits report-typ-unabhängig — kein neues Feld nötig |
| `preview_service.py:184-219` (#1297, Vorschau=Versand) | intern | Ruft dieselben Renderer wie der Versand — E1/E2 wirken automatisch in der Vorschau; `night_weather` fehlt dort separat (Issue #1315, NICHT Teil dieser Spec) |
| `renderer_mail_gate.py` (#811, Commit-Gate) | Tooling | `email/html.py` + `email/plain.py` sind Mail-Inhalts-Dateien → vor Commit `test_issue_811_mode_matrix.py` grün + frischer `briefing_mail_validator.py`-Lauf nötig |

## Implementation Details

### E1 — Gewitter-Vorschau nur ohne aktiven Ausblick

```python
# src/output/renderers/email/html.py, vor Zeile 1084
outlook_active = show_outlook and bool(multi_day_trend)

thunder_html = ""
if thunder_forecast and not outlook_active:
    ...  # unverändert
```

```python
# src/output/renderers/email/plain.py, Zeile 235
if thunder_forecast and not outlook_active:
    lines.append("━━ Gewitter-Vorschau ━━")
    ...  # unverändert
```

`outlook_active` in `plain.py` entspricht der bereits vorhandenen Bedingung
`show_outlook and multi_day_trend` aus Zeile 244 (dort für den Ausblick-Block
selbst genutzt) — für die Suppression an Zeile 235 vorzuziehen bzw. als
gemeinsame lokale Variable zu extrahieren, damit beide Stellen exakt
dieselbe Bedingung teilen (keine Drift zwischen Anzeige- und
Suppressions-Logik).

`show_outlook` und `multi_day_trend` sind an beiden Renderer-Funktionen
bereits als Parameter/lokale Variablen vorhanden (siehe Verwendung in
`html.py:1271` bzw. `plain.py:244`) — keine neuen Parameter nötig.

Der Scheduler (`_build_thunder_forecast_from_trend_or_fetch`,
`trip_report_scheduler.py:1495`) bleibt unverändert: `thunder_forecast` wird
weiterhin für ALLE Kanäle gebaut und durchgereicht. Die Suppression passiert
ausschließlich in den beiden E-Mail-Renderern — SMS (`sms_trip.py`, TH+-Token,
Vertrag #874) und Telegram (`narrow.py`) erhalten `thunder_forecast`
unverändert und sind von dieser Spec nicht betroffen.

### E2 — Nacht-Block auch im Morgenbriefing

```python
# src/services/trip_report_scheduler.py, Zeile 828-831 (vorher)
# 4. Night weather (evening reports only)
night_weather = None
if report_type == "evening" and segment_weather:
    night_weather = self._fetch_night_weather(segment_weather[-1])
```

```python
# nachher — Report-Typ-Bedingung entfernt
# 4. Night weather (both report types — Issue #1313)
night_weather = None
if segment_weather:
    night_weather = self._fetch_night_weather(segment_weather[-1])
```

```python
# src/output/renderers/trip_report.py, Zeile 107-109 (vorher)
# Night rows (evening only)
night_rows = []
if report_type == "evening" and night_weather and dc.show_night_block:
```

```python
# nachher — Report-Typ-Bedingung entfernt, Steuerung nur über show_night_block
# Night rows (both report types — Issue #1313, gated via dc.show_night_block)
night_rows = []
if night_weather and dc.show_night_block:
```

`_fetch_night_weather()` ist bereits generisch (letztes Segment der jeweiligen
Etappe, unabhängig vom Report-Typ) — für `morning` ergibt sich automatisch die
Nacht nach der HEUTIGEN Ankunft (`_get_target_date()`: morning=heute,
evening=morgen), identisch zur bisherigen Abend-Semantik (Ankunft →
06:00 Folgetag).

## Expected Behavior

- **Input:** E-Mail-Briefing-Rendering (HTML + Plain) mit `thunder_forecast`,
  `night_weather`, `multi_day_trend`, `show_outlook`, `dc.show_night_block`,
  `report_type` ∈ {`morning`, `evening`}
- **Output:**
  - Gewitter-Vorschau erscheint nur, wenn `thunder_forecast` vorhanden UND
    kein aktiver Mehrtages-Ausblick in derselben Mail (`outlook_active=False`)
  - Nacht-Block erscheint bei `dc.show_night_block=True` unabhängig vom
    Report-Typ, mit Fenster Ankunft → 06:00 Folgetag
- **Side effects:** Ein zusätzlicher Provider-API-Call pro Trip/Tag für
  Morgenbriefings (Night-Weather-Fetch, PO-akzeptiert). Keine Änderung an
  SMS-/Telegram-Renderern oder am Scheduler-Aufbau von `thunder_forecast`.

## Acceptance Criteria

- **AC-1:** Given ein E-Mail-Briefing mit aktivem Mehrtages-Ausblick
  (`show_outlook=True` und Trend-Daten vorhanden) / When es gerendert wird /
  Then erscheint die Sektion „⚡ Gewitter-Vorschau" NICHT (weder HTML noch
  Plain-Text).
  - Test: HTML- und Plain-Text-Ausgabe eines Briefings mit
    `show_outlook=True` + gefüllten `multi_day_trend`-Zeilen rendern und
    prüfen, dass „Gewitter-Vorschau" in keiner der beiden Ausgaben vorkommt.

- **AC-2:** Given ein E-Mail-Briefing OHNE aktiven Mehrtages-Ausblick (z.B.
  Morgen-Default) / When Gewitterdaten für +1/+2 vorliegen / Then erscheint
  die Gewitter-Vorschau unverändert.
  - Test: HTML- und Plain-Text-Ausgabe eines Briefings mit `show_outlook=False`
    (oder leerem `multi_day_trend`) und gesetztem `thunder_forecast` rendern
    und prüfen, dass die +1/+2-Einträge sichtbar sind.

- **AC-3:** Given ein Morgenbriefing mit `show_night_block=True` / When es
  gerendert wird / Then erscheint „🌙 Nacht am Ziel" mit Fenster Ankunft
  (heutige Etappe) bis 06:00 Folgetag — identisch zur bisherigen
  Abend-Semantik.
  - Test: Morgenbriefing (`report_type="morning"`) mit vorhandenem
    `segment_weather` rendern und prüfen, dass der Nacht-Block mit
    korrektem Zeitfenster erscheint (Regressionsvergleich gegen bisheriges
    Abend-Verhalten mit vertauschtem `target_date`).

- **AC-4:** Given ein Morgenbriefing mit `show_night_block=False` / When es
  gerendert wird / Then erscheint keine Nacht-Sektion.
  - Test: Morgenbriefing mit `dc.show_night_block=False` rendern und prüfen,
    dass „Nacht am Ziel" in der Ausgabe fehlt.

- **AC-5:** Given SMS-/Telegram-Versand mit Gewitterdaten / When gerendert
  wird / Then bleibt das TH+-Token bzw. die Kurzform von E1 unberührt (keine
  Regression).
  - Test: Bestehende SMS- (`sms_trip.py`, TH+-Token, Vertrag #874) und
    Telegram-Renderer-Tests laufen unverändert grün; kein neuer
    `outlook_active`-Bezug in diesen Renderern.

- **AC-6:** Given ein Abendbriefing / When es gerendert wird / Then bleibt
  die Nacht-Sektion unverändert vorhanden und die Gewitter-Vorschau ist genau
  dann unterdrückt, wenn der Ausblick aktiv ist — sonst keine
  Verhaltensänderung am Abend-Pfad.
  - Test: Abendbriefing mit Standard-Config (`show_outlook` Default für
    evening aktiv) rendern — Nacht-Block vorhanden, Gewitter-Vorschau fehlt;
    zusätzlich Abendbriefing mit `show_outlook=False` rendern — Nacht-Block
    weiterhin vorhanden, Gewitter-Vorschau erscheint wie vor #1313.

## Test-Plan

Kern-Schicht (deterministisch, echte Rendering-Aufrufe, keine Mocks/kein
Mock-Theater), neue Testdatei benannt nach Verhalten:
`tests/tdd/test_briefing_parity_night_thunder.py` (NICHT
`test_issue_1313_*.py` — Namensregel, `test_naming_gate.py`).

Abdeckung je AC:

| AC | Testfall |
|----|----------|
| AC-1 | `test_thunder_forecast_suppressed_when_outlook_active` |
| AC-2 | `test_thunder_forecast_shown_when_outlook_inactive` |
| AC-3 | `test_night_block_shown_in_morning_report` |
| AC-4 | `test_night_block_hidden_when_show_night_block_false_morning` |
| AC-5 | `test_sms_telegram_thunder_token_unaffected` (ggf. Ergänzung eines
  bestehenden SMS-/Telegram-Tests statt neuer Datei) |
| AC-6 | `test_evening_report_night_and_thunder_unchanged_outside_dopplung` |

**Betroffene Bestandstests** (aus Kontext-Analyse, ggf. Golden-Anpassungen
nötig, wenn Ausblick+Gewitter-Vorschau bisher kombiniert erwartet wurden):

- `test_issue_956_night_rows_date_bug.py`
- `test_issue_956_email_pixel_diff.py`
- `test_thunder_forecast_stage_consistency.py`
- `test_thunder_forecast_trend_reuse.py`
- `test_issue_721_email_outlook.py`
- `test_preview_thunder_matches_sent.py`

**Renderer-Commit-Gate #811 (Pflicht vor Commit):** da `email/html.py` und
`email/plain.py` Mail-Inhalts-Dateien sind, blockiert
`renderer_mail_gate.py` den Commit, bis (1) `tests/tdd/test_issue_811_mode_matrix.py`
grün ist UND (2) ein frischer `briefing_mail_validator.py`-Lauf gegen eine
echte Staging-Testmail erfolgreich war.

## Known Limitations

- `preview_service.py` übergibt `night_weather` bisher nicht separat an den
  Renderer — dadurch zeigt die Vorschau den Nacht-Block (auch nach E2) unter
  Umständen nicht, obwohl der Versand ihn enthält. Das ist eine bestehende
  Lücke, NICHT Teil dieser Spec — siehe Issue #1315.
- E2 verursacht einen zusätzlichen Provider-API-Call pro Trip/Tag für
  Morgenbriefings (Night-Weather-Fetch) — PO-akzeptiert, keine
  Kostengrenze definiert.
- E1 wirkt nur auf die beiden E-Mail-Renderer (HTML/Plain). SMS und Telegram
  zeigen die Gewitter-Vorschau-Kurzform unverändert weiter, auch wenn im
  selben Versandlauf eine E-Mail mit aktivem Ausblick existiert — das ist
  gewollt (kanalspezifische Darstellung, kein SMS-Ausblick-Ersatz).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues strukturelles Muster — reine Render-Bedingung
  (Sektions-Sichtbarkeit abhängig von einer bereits vorhandenen Variable)
  plus Entfernen einer Report-Typ-Bedingung an zwei bestehenden Gates.
  Keine neue Datenquelle, kein neuer Kanal, keine Schema-Änderung.

## Changelog

- 2026-07-18: Initial spec created — Issue #1313
