# Issue 14 · Output-Layout-System (Spalten · Detail · Aus + Kanal-Constraints)

**Type:** Backend + Frontend Architecture
**Priority:** Mid (depends on existing Metriken-Editor)
**Design Reference:**
- Desktop: `Gregor 20 - Redesign v2.html` → Section "03 · Trip-Konfiguration" → Artboard **Wetter-Metriken-Editor · Spalten-Layout & Multi-Channel-Vorschau**
- Signal-Constraints: `Gregor 20 - Signal Layout.html` → Section "Spalten-Constraint"

---

## Problem

Bisher kennen wir nur "Metrik ein/aus" pro Trip. Das reicht nicht:

- **Email** kann beliebig viele Spalten anzeigen, eine kompakte HTML-Tabelle ist gewünscht
- **Signal** rendert Mono-Tabellen — aber Bubble-Breite begrenzt auf ≈ 6 Spalten (Detail in [body-14-signal-constraint](#) und im Design dokumentiert)
- **Telegram** ähnlich, etwas mehr Platz (8 Spalten)
- **SMS** ist 140 Zeichen, hat überhaupt keine Tabelle — alles Fließtext

Wir brauchen ein einheitliches Modell, das **eine User-Konfiguration** auf alle Kanäle anwendet, ohne pro Kanal jedes Mal manuell zu konfigurieren.

---

## Konzept

Jede Metrik einer Tour bekommt drei Eigenschaften:

| Eigenschaft | Werte                              | Bedeutung |
|---|---|---|
| `bucket`    | `"primary"` / `"secondary"` / `"off"` | "eigene Spalte" / "Detail-Wert" / "nicht ausgeben" |
| `order`     | 0 … n-1                            | Reihenfolge innerhalb des Buckets |
| `mode`      | `"raw"` / `"indicator"`           | Zahl ("11,6 °C") oder Skala ("mild") |

Der **Renderer wendet pro Kanal die jeweiligen Constraints an**: was nicht in die Spalten passt, wandert in die Detail-Zeile. Was auch da nicht passt (z. B. SMS), fällt für diesen Kanal weg.

```
USER-KONFIG (1×)               RENDERER (1× pro Kanal)
─────────────────              ──────────────────────────────────────
primary:                       Email     → Tabelle: alle 8 primary
  [hh, °C, Wind, Böen,                     Detail-Zeile: 4 secondary
   R%, Wolken, Sicht,
   gef.]                       Telegram  → Tabelle: erste 8 primary
                                          Detail-Zeile: 4 secondary
secondary:                                (alle Spalten passen, nichts demoted)
  [Niedersch., Globalstr.,
   UV, Druck]                  Signal    → Tabelle: erste 6 primary
                                          Detail-Zeile: 2 primary + 4 secondary
off:                                      ⚠ 2 Spalten verschoben
  [Luftf., Taupunkt, …]
                               SMS       → flacher Text bis 140 Zeichen:
                                          "T 12 · W 11 · B 30 · R 0% · …"
```

---

## Backend

### Datenmodell (Datenbank)

```python
# Per-Trip-Konfiguration (eine Zeile in tour_metric_config)
class TourMetricConfig(Base):
    tour_id: UUID                      # FK
    metric_id: str                     # z.B. "temp", "wind", "rainProb"
    bucket: Enum["primary", "secondary", "off"]
    order: int                         # eindeutig innerhalb (tour_id, bucket)
    mode: Enum["raw", "indicator"]     # default "raw"

    # composite unique key (tour_id, metric_id)
```

**Optional V2** — pro-Kanal-Override (nicht in V1 nötig, aber Schema vorbereitet):

```python
class TourMetricChannelOverride(Base):
    tour_id: UUID
    metric_id: str
    channel: Enum["email", "telegram", "signal", "sms"]
    bucket: Optional[Enum["primary", "secondary", "off"]]  # null = follow global
    skip: bool = False                 # in diesem Kanal komplett weglassen
```

### Kanal-Constraints (Konstante, hard-coded)

```python
CHANNEL_LIMITS = {
    "email":    {"max_table_cols": None,  "max_bytes": None},   # unbegrenzt
    "telegram": {"max_table_cols": 8,     "max_bytes": 4096},
    "signal":   {"max_table_cols": 6,     "max_bytes": 1800},
    "sms":      {"max_table_cols": 0,     "max_bytes": 140},
}
```

> Begründung der Grenzen → siehe `Gregor 20 - Signal Layout.html`, Artboard "Constraint-Tabelle". Bubble-Content-Breite ≈ 272 px, Monospace-Zeichenbreite bei iOS-Menlo @ Default-Size = ~10,2 px → ~26 Zeichen → 6 Spalten zuverlässig. Telegram-Bubble breiter. Email unbegrenzt (kann Tabellen-Scroll). SMS hat keine Tabelle, GSM-7 = 160 Zeichen, wir konservativ 140.

### Renderer-Algorithmus

```python
def render_for_channel(channel: str, config: list[TourMetricConfig]) -> RenderedReport:
    limits = CHANNEL_LIMITS[channel]
    max_cols = limits["max_table_cols"]

    primary  = sorted([c for c in config if c.bucket == "primary"],   key=lambda c: c.order)
    secondary = sorted([c for c in config if c.bucket == "secondary"], key=lambda c: c.order)

    if max_cols is None:           # Email → alle primary in Tabelle
        in_table = primary
        overflow = []
    elif max_cols == 0:            # SMS → keine Tabelle
        in_table = []
        overflow = primary
    else:
        in_table = primary[:max_cols]
        overflow = primary[max_cols:]

    detail = overflow + secondary    # überzählige + sekundäre = Detail-Zeile

    return RenderedReport(
        table_columns=in_table,
        detail_values=detail,
        demoted_count=len(overflow),    # für Logging/Debug
    )
```

### Output-Formate

| Kanal | Tabelle | Detail-Zeile |
|---|---|---|
| **Email**    | HTML `<table>` mit Spalten | HTML `<p>` mit `·`-Trennung |
| **Telegram** | Monospace-Block in Code-Fence ``` | Fließtext-Zeile |
| **Signal**   | Monospace-Block (body-range MONOSPACE auf den Stunden-Zeilen) | Fließtext-Zeile mit `·`-Trennung |
| **SMS**      | — | komplett flach: `KHW · 12°C · W11 · B30 · R0% …`, gekürzt bei 140 |

### API-Endpoints

```
GET /api/tour/:id/metric-config
    → { "config": [ {metric_id, bucket, order, mode}, ... ] }

PUT /api/tour/:id/metric-config
    Body: { "config": [ ... ] }
    Validation:
      - bucket="primary" hat keine Loops in order
      - max 1 Eintrag pro metric_id
      - "hour" muss primary[0] sein (s. Constraint C2 unten)

POST /api/tour/:id/metric-config/auto-distribute
    → wendet Auto-Verteilung an (s. unten) und gibt das Ergebnis zurück.
    Frontend nutzt das auch lokal für Preview, ohne den Endpoint aufzurufen.
```

### Constraints (Backend-validiert)

| C   | Regel                                                              |
|-----|--------------------------------------------------------------------|
| C1  | `len([c for c in config if c.bucket=="primary"]) ≥ 1`              |
| C2  | `metric_id="hour"` muss vorhanden sein mit `bucket="primary", order=0` |
| C3  | `order` ist eindeutig & lückenlos `0..n-1` innerhalb eines Buckets |
| C4  | `mode="indicator"` nur erlaubt wenn `metric_id` in `INDICATOR_MAP`  |

Bei Verletzung: HTTP 422 mit `{ "field": "...", "code": "C2", "message": "..." }`.

### Auto-Verteilung (Heuristik)

Wird angewendet:
- bei Erstanlage einer Tour (`POST /api/tour`)
- wenn User auf "Auto-Verteilung" klickt
- bei Preset-Wechsel (überschreibt vorhandene Config)

```python
METRIC_PRIORITY = {
    # höhere Zahl = wichtiger
    "hour": 100,
    "temp": 95, "wind": 90, "gust": 88, "rainProb": 85, "precip": 78,
    "feels": 70, "cloud": 65, "thunder": 60, "snowfall": 55, "visibility": 55,
    "freezeLine": 50, "uv": 45, "windDir": 40, "snowDepth": 35, "precipType": 35,
    "cloudLow": 30, "newSnow": 30, "humidity": 25, "sunshine": 25,
    "radiation": 22, "dewpoint": 20, "pressure": 18, "cape": 15,
    "cloudMid": 12, "cloudHigh": 10, "soilTemp": 10,
}

def auto_distribute(metrics_in_tour: set[str]) -> list[TourMetricConfig]:
    """Auto-Verteilung: hour → primary[0]. Danach die 5 wichtigsten nach
    PRIORITY → primary[1..5]. Rest aus 'metrics_in_tour' → secondary.
    Alles andere → off (separate Tabelle: nicht in der Config, aber UI zeigt).
    """
    ordered = sorted(metrics_in_tour - {"hour"}, key=lambda m: -METRIC_PRIORITY.get(m, 0))
    primary = ["hour"] + ordered[:5]
    secondary = ordered[5:]
    return [
        TourMetricConfig(metric_id=m, bucket="primary",   order=i, mode="raw")
        for i, m in enumerate(primary)
    ] + [
        TourMetricConfig(metric_id=m, bucket="secondary", order=i, mode="raw")
        for i, m in enumerate(secondary)
    ]
```

**Wichtig**: Die Schwelle "5 nach hour" entspricht dem Signal-Limit. Damit ist auto-distribute Signal-safe.

### Migration für bestehende Touren

Existierende Touren haben `metric_set: list[str]` (alle aktiv). Migration:

```python
for tour in tours:
    if not tour.metric_config:  # noch nicht migriert
        config = auto_distribute(set(tour.metric_set))
        tour.metric_config = config
```

---

## Frontend

### Hauptscreen

**File:** `screen-metrics-editor.jsx` (Desktop) — bereits implementiert als Mockup.

Bereiche:
1. **Preset-Spalte** (links) — wechselt die Metriken-Auswahl, triggert intern Auto-Verteilung
2. **Spalten-Editor** (rechts oben) — sortierbare Liste der `primary`-Metriken mit:
   - Reihenfolge ↑↓
   - Modus-Toggle (Roh/Skala) wo `INDICATOR_MAP` existiert
   - Aktionen: `→ Detail`, `✕ Aus`
3. **Detail-Editor** (rechts mitte) — Liste der `secondary`-Metriken, gleiches Pattern
4. **Multi-Channel-Vorschau** (rechts mitte) — 4 Mini-Cards (Email · Telegram · Signal · SMS) mit echtem Renderer-Output. Zeigt Live, was wo landet. Zeigt Warn-Badge wenn Kanal-Limit überschritten ("⚠ 2 Spalten verschoben").
5. **"Nicht im Briefing"** (rechts unten, collapsed) — verfügbare Metriken nach Gruppe, mit `+ Spalte` / `+ Detail` Buttons

### Mobile-Adaption (V1.5)

`screen-metrics-editor-mobile.jsx` muss um dasselbe Modell ergänzt werden. Pattern in `screen-signal-cols-mobile.jsx` skizziert (3 Bucket-Cards + Sheet für Aktionen). Mobile lässt die Multi-Channel-Vorschau auf eine reduzierte Form: ein Drop-down zum Channel-Wechsel, dann je 1 Vorschau-Bubble.

### Validierungen vor Save (Frontend)

Frontend prüft C1–C4 vor dem PUT-Call und zeigt Toast bei Fehler. Erspart Backend-Roundtrip.

---

## Acceptance Criteria

- [ ] Datenmodell `tour_metric_config` + Migration für Bestands-Touren
- [ ] `GET / PUT /api/tour/:id/metric-config` mit Validierungen C1–C4
- [ ] `POST /api/tour/:id/metric-config/auto-distribute` (idempotent)
- [ ] Renderer `render_for_channel(channel, config)` mit Unit-Tests:
  - Email: kein Limit, kein `demoted`
  - Signal: 6 primary → 6 in_table, 0 demoted
  - Signal: 9 primary → 6 in_table, 3 demoted in Detail
  - SMS: alles flach, gekürzt bei 140
- [ ] Existierende Email- und Signal-Templates auf `RenderedReport` umgestellt
- [ ] Frontend `screen-metrics-editor.jsx` zeigt Multi-Channel-Vorschau live aus lokalem State (Renderer-Logik dupliziert: gleiche Funktion in JS)
- [ ] Preset-Wechsel überschreibt Config (mit Confirm-Dialog wenn dirty)
- [ ] Performance: Renderer-Output für ein Briefing < 50 ms

## Edge Cases

| Case | Verhalten |
|---|---|
| User entfernt "hour" aus primary | Frontend blockt — Pflicht-Spalte. Hint sichtbar. |
| primary leer | Backend: HTTP 422 C1. Frontend zeigt Inline-Fehler. |
| User hat 12 primary, schaltet auf SMS-Channel | Ausgabe ist eine flache Zeile, gekürzt bei 140. Logs `demoted=12`. |
| Tour ohne metric_config aufgerufen | Backend: auto-distribute fallback, einmal persistiert. |
| Indicator-Mode bei Metrik ohne INDICATOR_MAP | Backend ignoriert, rendert raw. Frontend zeigt diesen Toggle gar nicht. |

## Out of Scope (Folge-Issues)

- Pro-Kanal-Overrides (`TourMetricChannelOverride`) — V2
- Drag-and-Drop fürs Sortieren (V1 nutzt ↑↓ Buttons)
- Custom-Indicator-Schwellen pro User
- Mehrsprachigkeit (alles aktuell DE-hart)
