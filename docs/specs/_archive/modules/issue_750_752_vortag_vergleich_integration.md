---
entity_id: issue_750_752_vortag_vergleich_integration
type: module
created: 2026-06-11
updated: 2026-06-11
status: implemented
version: "1.0"
tags: [vortag-vergleich, scheduler, email, telegram, day-comparison]
---

# Vortag-Vergleich-Integration (F4 #750 + F6 #752)

## Approval

- [x] Approved

## Purpose

Schließt den fertig gebauten Vortag-Vergleich an den echten Briefing-Versand an: Der
Scheduler lädt beim Versand den gestrigen Snapshot, berechnet einmalig die `DayComparison`
und reicht sie in die E-Mail (HTML + Plain, über die bisher verwaisten #749-Renderer) und
in eine neue kompakte Telegram-Zeile. Fehlt der Vortag, passiert nichts (kein Absturz,
kein leerer Block).

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportScheduler._send_trip_report`
- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter.format_email`
- **File:** `src/app/models.py`
- **Identifier:** `TripReportConfig.show_yesterday_comparison`
- **File:** `src/output/renderers/email/__init__.py`
- **Identifier:** `render_email`
- **File:** `src/output/renderers/email/html.py`, `src/output/renderers/email/plain.py`
- **Identifier:** `render_html` / `render_plain` (Verdrahtung der `render_day_comparison_*`)
- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `render_narrow` (F6: Telegram-Kurzform)

Alle Symbole liegen im **Python-Backend** (`src/...`, FastAPI/Scheduler). Keine Go- oder
SvelteKit-Schicht betroffen (Frontend-Toggle ist Slice F5, OOS).

## Estimated Scope

- **LoC:** ~110 (F4 ~60 + F6 ~50) + Renderer-Verdrahtung
- **Files:** 7 (scheduler, formatter, models, email/__init__, html, plain, narrow)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DayComparisonService.compare(today, yesterday)` | service (#748) | Delta-Berechnung |
| `WeatherSnapshotService.load_dated(trip_id, date)` | service (#747) | Vortag-Snapshot laden |
| `render_day_comparison_html` / `render_day_comparison_plain` | renderer (#749) | E-Mail-Sektion |

## Implementation Details

```
# 1. Scheduler (_send_trip_report), nach Wetter-Fetch, vor format_email:
day_comparison = None
show_yc = trip.report_config.show_yesterday_comparison if trip.report_config else True
if show_yc:
    try:
        from services.weather_snapshot import WeatherSnapshotService
        from services.day_comparison import DayComparisonService
        yday = WeatherSnapshotService(self._user_id).load_dated(
            trip.id, target_date - timedelta(days=1))
        if yday:
            day_comparison = DayComparisonService().compare(segment_weather, yday)
    except Exception as e:
        logger.warning(f"Vortag-Vergleich übersprungen für {trip.id}: {e}")
        day_comparison = None
# → an format_email(..., day_comparison=day_comparison)

# 2. models.TripReportConfig:
show_yesterday_comparison: bool = True   # #750: Vortag-Vergleich-Sektion

# 3. format_email: neues optionales kwarg day_comparison=None
#    → an render_email(..., day_comparison=day_comparison)
#    → an render_narrow(..., day_comparison=day_comparison)

# 4. render_email → render_html / render_plain bekommen day_comparison;
#    render_html / render_plain rufen render_day_comparison_html/plain auf und
#    fügen die Sektion an definierter Stelle ein (nach Ausblick-Block).

# 5. render_narrow (F6): neue "Vortag:"-Zeile, max 3 Metriken absteigend nach
#    |delta|; entfällt komplett wenn day_comparison None/leer.
```

## Expected Behavior

- **Input:** `segment_weather` (heute), `target_date`, `user_id`, `report_config`.
- **Output:** E-Mail-HTML+Plain mit Vortag-Vergleich-Sektion (wenn Snapshot da + Toggle an);
  Telegram-`telegram_text` mit `Vortag:`-Zeile (wenn Snapshot da).
- **Side effects:** Lesen des datierten Snapshots; keine Schreibvorgänge zusätzlich.

## Acceptance Criteria

**AC-1:** Given ein Trip mit gespeichertem Vortag-Snapshot (gestern) und heutigen
Wetterdaten / When der Scheduler `_send_trip_report` ausführt / Then enthält der erzeugte
E-Mail-Report (HTML **und** Plain) eine Vortag-Vergleich-Sektion mit den Deltas.
  - Test: Echter Scheduler-Lauf mit zwei datierten Snapshots; `format_email`-Ergebnis
    prüfen — `email_html` und `email_plain` enthalten die gerenderten Delta-Werte.

**AC-2:** Given ein Trip **ohne** Vortag-Snapshot (z. B. erster Tourtag) / When der
Scheduler `_send_trip_report` ausführt / Then wird `day_comparison=None` übergeben, der
Report wird normal erzeugt (kein Absturz, keine leere Sektion, kein Error-Log).
  - Test: Scheduler-Lauf ohne Vortag-Snapshot; `_send_trip_report` liefert True,
    `email_plain` enthält **keinen** "Vortag-Vergleich"-Block.

**AC-3:** Given `show_yesterday_comparison=False` in `TripReportConfig` bei vorhandenem
Vortag-Snapshot / When `_send_trip_report` läuft / Then wird der Snapshot **nicht** geladen
und die Sektion erscheint **nicht** in der Mail.
  - Test: Trip mit Toggle False + Vortag-Snapshot; `email_html`/`email_plain` ohne
    Vortag-Sektion.

**AC-4:** Given `format_email` wird **ohne** `day_comparison`-Argument aufgerufen (alter
Aufrufstil) / When der Report erzeugt wird / Then funktioniert das rückwärtskompatibel
(Default `None`, keine Sektion, kein Fehler).
  - Test: `format_email(...)` ohne `day_comparison`-kwarg; liefert validen `TripReport`.

**AC-5:** Given zwei Trips verschiedener Nutzer mit je eigenem Vortag-Snapshot / When beide
Reports erzeugt werden / Then lädt der Scheduler je den Snapshot des **eigenen** `user_id`
(`WeatherSnapshotService(self._user_id)`), keine Cross-User-Vermischung.
  - Test: Snapshots für `userA` und `userB` mit unterschiedlichen Deltas; je Report zeigt
    nur die eigenen Werte.

**AC-6:** Given ein Vortag-Snapshot mit mehreren abweichenden Metriken / When das
Telegram-Briefing (`render_narrow` / `telegram_text`) erzeugt wird / Then enthält es eine
`Vortag:`-Zeile mit **maximal 3** Metriken, absteigend nach Abweichungsgröße sortiert.
  - Test: `render_narrow(..., day_comparison=...)` mit 5 abweichenden Metriken; Output hat
    genau 3 Metriken, größte `|delta|` zuerst.

**AC-7:** Given **kein** Vortag-Snapshot / When das Telegram-Briefing erzeugt wird / Then
entfällt die `Vortag:`-Zeile komplett (kein leerer Block).
  - Test: `render_narrow(..., day_comparison=None)`; Output enthält kein "Vortag".

## Known Limitations

- Frontend-Toggle für `show_yesterday_comparison` ist OOS (Slice F5, separates Feature).
- `load_dated` heißt so (nicht `load_for_date` wie in #750-Issue-Wording).
- Telegram-Kurzform sortiert nach absolutem Delta; Temperatur ist neutral (keine
  Richtungspfeile), wird aber für die Top-3-Auswahl mit `|delta|` berücksichtigt.

## Changelog

- 2026-06-11: Initial spec created (F4 #750 + F6 #752 kombiniert)
