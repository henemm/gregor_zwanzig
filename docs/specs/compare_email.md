---
entity_id: compare_email
type: feature
created: 2025-12-28
updated: 2025-12-31
status: approved
version: "4.0"
tags: [ui, nicegui, compare, email, scheduler]
entities: [comparesubscription, comparisonengine, comparisonresult, locationresult]
---

# Compare Subscription Scheduler

## Approval

- [x] Approved (2025-12-28)
- [x] Updated v3.0 (2025-12-29): HTML Email, Single Processor Architecture

## Purpose

Automatischer E-Mail-Versand von Skigebiet-Vergleichen nach konfigurierbarem Schedule.

Use Case: "Jeden Freitag um 18:00 bekomme ich eine E-Mail mit dem Ranking meiner Skigebiete fuer das Wochenende (9-16 Uhr)."

**Kernprinzip:** Ein Prozessor generiert die Daten, verschiedene Renderer stellen sie dar.
Website und E-Mail zeigen IDENTISCHE Inhalte, nur in unterschiedlichem Format/Layout.

## Architecture

```
ComparisonEngine.run(locations, time_window, target_date)
    → ComparisonResult (Dataclass mit allen Metriken)
        ↓
        ├─ WebRenderer.render(result) → NiceGUI UI
        └─ EmailRenderer.render(result) → HTML Email
```

**Keine Code-Duplizierung!** Änderungen am Prozessor wirken sich auf beide Outputs aus.

## Source

- **File:** `src/app/user.py` - CompareSubscription Dataclass
- **File:** `src/app/loader.py` - Load/Save Funktionen
- **File:** `src/web/pages/compare.py` - ComparisonEngine + Renderer
- **File:** `src/app/cli.py` - --run-subscriptions Command
- **File:** `src/web/pages/subscriptions.py` - Verwaltungs-UI

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

### 2. ComparisonResult Dataclass

```python
@dataclass
class ComparisonResult:
    """Ergebnis eines Skigebiet-Vergleichs."""
    locations: List[LocationResult]  # Sortiert nach Score
    time_window: Tuple[int, int]     # (start_hour, end_hour)
    target_date: date                # Forecast-Datum
    created_at: datetime             # Erstellungszeitpunkt

@dataclass
class LocationResult:
    """Ergebnis einer einzelnen Location."""
    location: SavedLocation
    score: int
    snow_depth_cm: Optional[float]
    snow_new_cm: Optional[float]
    temp_min: Optional[float]
    temp_max: Optional[float]
    wind_max: Optional[float]
    wind_chill_min: Optional[float]
    cloud_avg: Optional[int]
    sunny_hours: Optional[int]
    hourly_data: List[ForecastDataPoint]  # Gefilterte Stunden
    # v3.2: Neue Felder
    wind_direction_avg: Optional[int]     # Durchschnittliche Windrichtung (Grad)
    gust_max_kmh: Optional[float]         # Maximale Boeengeschwindigkeit
    cloud_low_avg: Optional[int]          # Durchschn. tiefe Bewoelkung (fuer Wolkenlage)
```

### 3. Renderer Interface

```python
def render_comparison_html(result: ComparisonResult) -> str:
    """Rendert ComparisonResult als HTML (fuer Email)."""

def render_comparison_ui(result: ComparisonResult, container: ui.element) -> None:
    """Rendert ComparisonResult in NiceGUI UI."""
```

Beide Renderer verwenden DASSELBE ComparisonResult - garantiert identische Inhalte.

### 4. UI-Erweiterungen

- Zwei Dropdowns fuer Start-/End-Stunde (6:00-20:00)
- Stunden-Tabelle pro Location (expandierbar)
- "Per E-Mail senden" Button (nur wenn SMTP konfiguriert)

### 5. Effektive Bewoelkung (Hoehenkorrektur)

Hochlagen (>2500m) sind oft UEBER den tiefen Wolken.
Das Wetter-Symbol muss dies beruecksichtigen.

**Regel:**
```
Wenn elevation >= 2500m:
  effektive_bewoelkung = (cloud_mid + cloud_high) / 2
  (tiefe Wolken sind unter der Location → ignorieren)

Sonst:
  effektive_bewoelkung = cloud_total
  (alle Wolkenschichten betreffen die Location)

Wetter-Symbol = basiert auf effektive_bewoelkung
```

**Wolkenschicht-Hoehen:**
- Low clouds: 0 - 2km → unter Hochlagen (>2500m)
- Mid clouds: 2 - 6km → betrifft alle Bergstationen
- High clouds: >6km → betrifft alle

**Beispiel Hintertuxer Gletscher (3000m):**
- cloud_total = 80% (hoch, weil viele tiefe Wolken)
- cloud_low = 100% (Nebel im Tal)
- cloud_mid = 0%, cloud_high = 0%
- → effektive_bewoelkung = 0% → ☀️ Sonne

### 6. Sonnenstunden-Berechnung (KONSISTENZ!)

**Sonnenstunden MUSS die effektive Bewoelkung nutzen!**

```
Fuer jede Stunde im Zeitfenster:
  effektive_cloud = berechne_effektive_bewoelkung(elevation, cloud_low, cloud_mid, cloud_high, cloud_total)
  wenn effektive_cloud < 30%: sunny_hour += 1
```

**WICHTIG:** Sonnenstunden und Wolkenlage muessen KONSISTENT sein!
- Wenn Wolkenlage = "klar" (cloud_low < 20% bei Hochlage) → Sonnenstunden > 0
- Wenn Wolkenlage = "in Wolken" → Sonnenstunden klein

## E-Mail Format (HTML) - EXAKTE SPEZIFIKATION

**KRITISCH:** Es darf nur EINEN HTML-Renderer geben (`render_comparison_html`).
Die UI-Button-Funktion muss diesen Renderer verwenden, KEINE separate Implementierung!

### Header-Bereich

```
H1: "⛷️ Skigebiete-Vergleich"
P:  "📅 Forecast für: [Wochentag, DD.MM.YYYY]"
P:  "🕐 Zeitfenster: [HH]:00 - [HH]:00"
P:  "📝 Erstellt: [DD.MM.YYYY HH:MM]"
```

### Winner-Box

```
H2: "🏆 Empfehlung: [Location Name]"
P:  "Score: [N] | ❄️ [N]cm Schnee | ☀️ ~[N]h Sonne"
```

### Vergleichstabelle - EXAKTE ZEILEN

| Zeile | Label | Format | Grün-Markierung |
|-------|-------|--------|-----------------|
| 1 | Header | "#[N] [Location Name]" | - |
| 2 | Score | "[N]" | Höchster Wert |
| 3 | Schneehöhe | "[N]cm" oder "-" | Höchster Wert |
| 4 | Neuschnee | "+[N]cm" oder "-" | Höchster Wert |
| 5 | Wind/Böen | "[W]/[B] [Richtung]" z.B. "10/41 SW" | Niedrigster Wind |
| 6 | Temperatur (gefühlt) | "[N]°C" | Höchster Wert (wärmer) |
| 7 | Sonnenstunden | "~[N]h" oder "0h" (NICHT "-" bei 0!) | Höchster Wert |
| 8 | Bewölkung | "[N]%" | Niedrigster Wert |
| 9 | Wolkenlage | Siehe unten | - |

**Wolkenlage-Werte (Zeile 9):**
- `elevation >= 2500m AND cloud_low > 30%`: "☀️ über Wolken" (grün)
- `cloud_low > 50%`: "☁️ in Wolken" (grau)
- `cloud_low < 20%`: "✨ klar" (grün)
- Sonst: "🌤️ leicht"

### Stunden-Tabelle

Für Top-N Locations (default: 3):

| Zeit | #1 [Name] | #2 [Name] | #3 [Name] |
|------|-----------|-----------|-----------|
| 09:00 | [Symbol][Temp]°C | ... | ... |
| 10:00 | ... | ... | ... |
| ... | ... | ... | ... |

**Wetter-Symbol basiert auf effektiver Bewölkung** (siehe Effektive Bewölkung).

### Footer

```
"Generiert von Gregor Zwanzig ⛷️"
```

### Formatierungsregeln

1. **Sonnenstunden:** `0` zeigt "0h" an, NICHT "-"
2. **Wind kombiniert:** Eine Zeile für Wind/Böen/Richtung: "10/41 SW"
3. **Keine Gradangabe:** Windrichtung nur als Himmelsrichtung (N, NE, E, SE, S, SW, W, NW)
4. **Grün-Markierung:** Bester Wert bekommt grünen Hintergrund + fette Schrift

## Expected Behavior

- **Input:** Klick auf "Per E-Mail senden" nach Vergleich
- **Output:** HTML E-Mail mit Ranking und Stunden-Details (identisch zur Web-UI)
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

## Follow-up: Ticket 2 (Backlog)

Fuer spaetere Erweiterung:
- `CompareSubscription` Datenmodell
- Persistenz in `data/users/default/compare_subscriptions.json`
- Settings-UI fuer Subscription-Verwaltung
- Scheduler-Integration (CLI/Cron)

## Changelog

- 2025-12-31: v4.0 - Exakte E-Mail Spezifikation
  - BREAKING: Nur noch EIN Renderer (`render_comparison_html`)
  - `format_compare_email` muss entfernt werden (Code-Duplizierung)
  - Wind/Böen/Richtung in EINER Zeile: "10/41 SW"
  - Keine Gradangabe bei Windrichtung
  - Sonnenstunden: 0 zeigt "0h" (nicht "-")
  - Wolkenlage-Zeile ist PFLICHT
  - Exakte Tabellen-Struktur definiert (9 Zeilen)
- 2025-12-30: v3.2 - Windrichtung, Boeen, Neuschnee
  - Neue Felder: wind_direction_avg, gust_max_kmh, snow_new_cm
  - Windrichtung als Durchschnitt im Zeitfenster (Gradangabe + Himmelsrichtung)
  - Boeengeschwindigkeit als Maximum im Zeitfenster
  - Neuschnee in cm (aus AROME snow_acc, bereits in cm konvertiert)
- 2025-12-29: v3.1 - Effektive Bewoelkung fuer Hochlagen
  - Wetter-Symbol beruecksichtigt Hoehe der Location
  - Hochlagen (>2500m) ignorieren tiefe Wolken (cloud_low)
  - Zeigt korrekt Sonne wenn Location ueber den Wolken liegt
- 2025-12-29: v3.0 - Single Processor Architecture, HTML Email
  - Refactoring: Ein ComparisonEngine, zwei Renderer (Web + Email)
  - HTML statt Plain-Text E-Mail
  - Garantiert identische Inhalte in Web und Email
- 2025-12-28: Initial spec created
