---
entity_id: compare_email
type: feature
created: 2025-12-28
updated: 2025-12-28
status: approved
version: "1.0"
tags: [ui, nicegui, compare, email]
---

# Compare E-Mail Enhancement

## Approval

- [x] Approved (2025-12-28)

## Purpose

Erweiterung des Forecast-Vergleichs um E-Mail-Versand mit konfigurierbarem Zeitfenster. Ermoeglicht den Versand von Skigebiet-Rankings per E-Mail mit stundenweisen Details fuer die relevanten Tagesstunden (z.B. 9:00-16:00).

## Source

- **File:** `src/web/pages/compare.py`
- **Identifier:** `filter_data_by_hours()`, `format_compare_email()`, UI-Erweiterungen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastDataPoint` | dataclass | Forecast-Datenpunkte mit Timestamp |
| `outputs.email.EmailOutput` | class | E-Mail-Versand via SMTP |
| `app.config.Settings` | class | SMTP-Konfiguration |
| `nicegui` | external | UI-Framework |

## Scope: Ticket 1 (MVP)

**Enthalten:**
- Zeit-Filter Funktion
- E-Mail-Format Funktion
- UI: Zeitfenster-Dropdowns (Start/End Stunde)
- UI: Stunden-Tabelle pro Location
- UI: Sofort-E-Mail Button

**NICHT enthalten (Ticket 2):**
- Subscription-System
- Scheduled E-Mail-Versand
- Persistente Konfiguration

## Implementation Details

### 1. Zeit-Filter Funktion

```python
def filter_data_by_hours(
    data: List[ForecastDataPoint],
    start_hour: int,  # z.B. 9
    end_hour: int,    # z.B. 16
) -> List[ForecastDataPoint]:
    """Filtert Forecast auf bestimmte Tagesstunden."""
    return [dp for dp in data if start_hour <= dp.ts.hour < end_hour]
```

### 2. E-Mail-Format Funktion

```python
def format_compare_email(
    results: List[Dict],
    time_window: Tuple[int, int],
    forecast_hours: int,
    top_n_details: int = 3,
) -> str:
    """Formatiert Vergleichsergebnis als Plain-Text E-Mail."""
```

### 3. UI-Erweiterungen

- Zwei Dropdowns fuer Start-/End-Stunde (6:00-20:00)
- Stunden-Tabelle pro Location (expandierbar)
- "Per E-Mail senden" Button (nur wenn SMTP konfiguriert)

## E-Mail Format

```
============================================================
  SKIGEBIETE-VERGLEICH
  Datum: 29.12.2024 18:00 | Forecast: 48h
  Aktivzeit: 09:00-16:00
============================================================

RANKING (3 Locations)
------------------------------------------------------------
 #  Location                  Score   Schnee   Wind    Temp
------------------------------------------------------------
 1  Stubaier Gletscher          82    +15cm    25km/h   -3C
 2  Soelden                     78     +8cm    32km/h   -1C
 3  Hochgurgl                   71     +5cm    45km/h   -5C
------------------------------------------------------------

EMPFEHLUNG: Stubaier Gletscher (Score 82)
  Schneehoehe: 180cm | Neuschnee: +15cm | Sonne: ~5h

------------------------------------------------------------
STUNDEN-DETAILS: Stubaier Gletscher
------------------------------------------------------------
Sa 28.12.
  09:00   -3C   12km/h   30%    -
  10:00   -2C   15km/h   25%    -
  11:00   -1C   18km/h   20%   +1cm
  ...

============================================================
Generiert von Gregor Zwanzig
============================================================
```

## Expected Behavior

- **Input:** Klick auf "Per E-Mail senden" nach Vergleich
- **Output:** Plain-Text E-Mail mit Ranking und Stunden-Details
- **Side effects:**
  - E-Mail wird via SMTP versendet
  - UI zeigt Erfolgs-/Fehlermeldung

## Validation

- SMTP muss konfiguriert sein (`settings.can_send_email()`)
- Mindestens eine Location muss verglichen worden sein
- Zeitfenster: start_hour < end_hour

## Known Limitations

- Nur Sofort-Versand (kein Scheduling in MVP)
- Zeitfenster nicht persistent (nur UI-State)
- Plain-Text nur (kein HTML)

## Follow-up: Ticket 2 (Backlog)

Fuer spaetere Erweiterung:
- `CompareSubscription` Datenmodell
- Persistenz in `data/users/default/compare_subscriptions.json`
- Settings-UI fuer Subscription-Verwaltung
- Scheduler-Integration (CLI/Cron)

## Changelog

- 2025-12-28: Initial spec created
