<!-- gregor-zwanzig-handoff: stable_id=output-layout-system -->
# Issue 14 · Output-Layout-System (Spalten · Aus + Kanal-Constraints)

**Type:** Backend + Frontend Architecture
**Priority:** Mid (depends on existing Metriken-Editor)
**Design Reference:**
- Desktop: `screen-metrics-editor.jsx` → Sektion „Reihenfolge & Darstellung"
- v2-Tab: `screen-trip-edit-v2-weather.jsx` → `WetterMetrikenTabV2`

> **Modell-Entscheidung (2026-06-06, PO Henning):**
> Das kanonische Modell hat **zwei Buckets** (`spalte` / `aus`) und **zwei Modi**
> (`raw` / `indicator`). Es gibt **keine Detail-Zeile** und **keine Formate
> Skala oder Symbol** — diese sind ersatzlos entfallen. Signal ist seit
> 2026-06-05 kein Kanal mehr (nur noch Email · Telegram · SMS).

---

## Problem

Bisher kennt das System nur „Metrik ein/aus" pro Trip. Das reicht nicht:

- **Email** kann beliebig viele Spalten anzeigen — HTML-Tabelle gewünscht
- **Telegram** rendert Mono-Tabellen, Breite begrenzt auf **8 Spalten**
- **SMS** hat keine Tabelle, alles Fließtext bis 140 Zeichen

Wir brauchen ein einheitliches Modell, das **eine User-Konfiguration** auf alle
drei Kanäle anwendet, ohne pro Kanal manuell einzustellen.

---

## Konzept

Jede Metrik eines Trips bekommt drei Eigenschaften:

| Eigenschaft | Werte               | Bedeutung |
|---|---|---|
| `bucket`    | `"spalte"` / `"off"` | in Briefing-Tabelle · nicht ausgeben |
| `order`     | 0 … n-1             | Reihenfolge in der Tabelle (links → rechts) |
| `mode`      | `"raw"` / `"indicator"` | Zahl (`11,6 °C`) oder Indikator (`mild`) |

Der **Renderer wendet pro Kanal die jeweiligen Constraints an**: was über das
Spalten-Limit hinausgeht, fällt für diesen Kanal weg (kein Fallback in eine
Detail-Zeile — es gibt keine).

```
USER-KONFIG (1×)               RENDERER (1× pro Kanal)
─────────────────              ──────────────────────────────────────
spalte:                        Email    → Tabelle: alle 10 Spalten
  [hh, °C, gef., Wind,
   Böen, R%, Gewitter,         Telegram → Tabelle: erste 8 Spalten
   Sicht, Wolken, UV]                    ⚠ 2 Spalten nicht darstellbar
                                          (Reihenfolge entscheidet, was drin ist)
aus:
  [Luftf., Taupunkt, …]        SMS      → flacher Text bis 140 Zeichen:
                                          „T 12 · W 11 · B 30 · R 0% · …"
```

---

## Backend

### Datenmodell (Datenbank)

```python
# Per-Trip-Konfiguration (eine Zeile pro Metrik in trip_metric_config)
class TripMetricConfig(Base):
    trip_id:   UUID                       # FK
    metric_id: str                        # z.B. "temp", "wind", "rainProb"
    bucket:    Enum["spalte", "off"]      # "spalte" = in Tabelle; "off" = nicht ausgeben
    order:     int                        # 0-basiert, eindeutig pro (trip_id, bucket="spalte")
    mode:      Enum["raw", "indicator"]   # default "raw"

    # composite unique key (trip_id, metric_id)
```

**Optional V2** — pro-Kanal-Override (nicht in V1 nötig, aber Schema vorbereiten):

```python
class TripMetricChannelOverride(Base):
    trip_id:   UUID
    metric_id: str
    channel:   Enum["email", "telegram", "sms"]
    skip:      bool = False   # in diesem Kanal komplett weglassen
```

### Kanal-Constraints (Konstante, hard-coded)

```python
CHANNEL_LIMITS = {
    "email":    {"max_table_cols": None, "max_bytes": None},   # unbegrenzt
    "telegram": {"max_table_cols": 8,    "max_bytes": 4096},
    "sms":      {"max_table_cols": 0,    "max_bytes": 140},
}
```

> **Telegram-Begründung:** Mono-Bubble-Breite erlaubt zuverlässig 8 Spalten.
> Designnachweis: `screen-metrics-editor.jsx` → `ME_CHANNELS`.
> Signal ist kein Kanal mehr (entfernt 2026-06-05).

### Renderer-Algorithmus

```python
def render_for_channel(channel: str, config: list[TripMetricConfig]) -> RenderedReport:
    limits = CHANNEL_LIMITS[channel]
    max_cols = limits["max_table_cols"]

    active = sorted(
        [c for c in config if c.bucket == "spalte"],
        key=lambda c: c.order
    )

    if max_cols is None:       # Email → alle Spalten
        in_table = active
        dropped  = []
    elif max_cols == 0:        # SMS → keine Tabelle
        in_table = []
        dropped  = active
    else:                      # Telegram → erste N Spalten
        in_table = active[:max_cols]
        dropped  = active[max_cols:]

    # Keine Detail-Zeile — dropped Metriken sind in diesem Kanal schlicht weg.
    return RenderedReport(
        table_columns=in_table,
        dropped_count=len(dropped),   # für Logging/Warn-Badge im Frontend
    )
```

### Output-Formate

| Kanal | Tabelle | Überlauf |
|---|---|---|
| **Email**    | HTML `<table>` mit allen Spalten | — (kein Limit) |
| **Telegram** | Monospace-Block in Code-Fence ` ``` ` | Metriken fallen weg; optionaler „Tages-Max"-Anhang als Fließtext (User-Toggle) |
| **SMS**      | — | komplett flach: `KHW · 12°C · W11 · B30 · R0% …`, gekürzt bei 140 |

### API-Endpoints

```
GET  /api/trip/:id/metric-config
     → { "config": [ {metric_id, bucket, order, mode}, ... ] }

PUT  /api/trip/:id/metric-config
     Body: { "config": [ ... ] }
     Validation: C1–C4 (s. unten)

POST /api/trip/:id/metric-config/auto-distribute
     → wendet Heuristik an, persistiert und gibt Ergebnis zurück.
     Frontend nutzt gleiche Logik lokal für Live-Vorschau.
```

### Constraints (Backend-validiert)

| C   | Regel |
|-----|-------|
| C1  | Mindestens 1 Metrik mit `bucket="spalte"` |
| C2  | `metric_id="hour"` muss `bucket="spalte", order=0` sein |
| C3  | `order` ist eindeutig und lückenlos `0..n-1` innerhalb aller Metriken mit `bucket="spalte"` |
| C4  | `mode="indicator"` nur erlaubt wenn `metric_id` in `INDICATOR_MAP` |

Bei Verletzung: HTTP 422 mit `{ "field": "...", "code": "C2", "message": "..." }`.

### Auto-Verteilung (Heuristik)

Wird angewendet bei:
- Erstanlage eines Trips
- Klick auf „Profil laden" (Preset-Wechsel)
- explizitem „Auto-Verteilung"-Button

```python
METRIC_PRIORITY = {
    "hour": 100,
    "temp": 95, "wind": 90, "gust": 88, "rainProb": 85, "precip": 78,
    "feels": 70, "cloud": 65, "thunder": 60, "snowfall": 55, "visibility": 55,
    "freezeLine": 50, "uv": 45, "windDir": 40, "snowDepth": 35,
    "cloudLow": 30, "newSnow": 30, "humidity": 25, "sunshine": 25,
    "dewpoint": 20, "pressure": 18, "cape": 15,
}

def auto_distribute(metrics_in_trip: set[str]) -> list[TripMetricConfig]:
    """hour → spalte[0]. Die N-1 höchst-priorisierten → spalte.
    Alle übrigen → off.
    N = Telegram-Limit (8) — damit ist auto-distribute Telegram-safe.
    """
    ordered = sorted(metrics_in_trip - {"hour"}, key=lambda m: -METRIC_PRIORITY.get(m, 0))
    in_table = ["hour"] + ordered[:7]   # 1 + 7 = 8 = Telegram-Limit
    off      = ordered[7:]
    return (
        [TripMetricConfig(metric_id=m, bucket="spalte", order=i, mode="raw")
         for i, m in enumerate(in_table)] +
        [TripMetricConfig(metric_id=m, bucket="off",    order=0, mode="raw")
         for m in off]
    )
```

### Migration für bestehende Trips

Bestehende Trips haben `metric_set: list[str]` (alle aktiv, kein Bucket-Modell).

```python
for trip in trips:
    if not trip.metric_config:
        config = auto_distribute(set(trip.metric_set))
        trip.metric_config = config
```

Trips mit altem Schema `bucket="primary"/"secondary"` werden migriert:
- `"primary"` → `"spalte"` (1:1)
- `"secondary"` → `"off"` (Detail-Bucket existiert nicht mehr)

---

## Frontend

### Hauptscreen

**File:** `screen-metrics-editor.jsx` (Desktop) / `screen-trip-edit-v2-weather.jsx` (Trip-Edit v2)

Bereiche:
1. **Preset-Bar** — lädt Profil, triggert Auto-Verteilung
2. **Grundauswahl** — Metrik-Chips (aktiv/inaktiv), gruppiert nach Kategorie
3. **Reihenfolge & Darstellung** — sortierbare Liste aller `spalte`-Metriken:
   - Pfeil-Buttons ↑↓ für Reihenfolge
   - Modus-Toggle (Roh / Einfach) nur wenn Metrik `indicatorCapable`
   - „Aus"-Button entfernt Metrik aus dem Briefing
4. **Kanäle** — Email / Telegram / SMS on/off
5. **Live-Vorschau** (sticky rechts oder Sektion unten) — zeigt Renderer-Output
   pro Kanal. Warn-Badge wenn Telegram-Limit überschritten.

**Kein Detail-Bucket, kein „→ Detail"-Button.** Der einzige Zustandswechsel
unterhalb von „aktiv in Spalte" ist „aus".

### Telegram-Überlauf-Handling im Frontend

Wenn `spalte`-Metriken > 8:
- Schnittlinie (`✂ ab hier Telegram-Limit`) in der Reihenfolge-Liste
- Warn-Badge auf Telegram-Kanal-Karte
- Optionaler Toggle „Tages-Max für übrige Metriken" — hängt Überlauf-Metriken
  als kompakte Tages-Zusammenfassung unter die Tabelle (kein Spalten-Slot)

### Validierungen vor Save (Frontend)

Frontend prüft C1–C4 vor dem PUT-Call und zeigt Toast bei Fehler.

---

## Acceptance Criteria

- [ ] Datenmodell `trip_metric_config` mit `bucket ∈ {spalte, off}` + Migration
- [ ] `GET / PUT /api/trip/:id/metric-config` mit Validierungen C1–C4
- [ ] `POST /api/trip/:id/metric-config/auto-distribute` (idempotent, Telegram-safe = ≤ 8 spalte)
- [ ] Renderer `render_for_channel(channel, config)` mit Unit-Tests:
  - Email: kein Limit, `dropped=0`
  - Telegram, 6 spalte → 6 in_table, 0 dropped
  - Telegram, 10 spalte → 8 in_table, 2 dropped
  - SMS: alles flach, gekürzt bei 140
- [ ] Migrations-Skript: `bucket="secondary"` → `"off"`, `bucket="primary"` → `"spalte"`
- [ ] Frontend `screen-metrics-editor.jsx` zeigt Schnittlinie + Warn-Badge bei Telegram-Überlauf
- [ ] Live-Vorschau läuft lokal aus State (Renderer-Logik als JS-Port, kein API-Call nötig)
- [ ] Preset-Wechsel überschreibt Config (mit Confirm-Dialog wenn dirty)
- [ ] Performance: Renderer-Output für ein Briefing < 50 ms

## Edge Cases

| Case | Verhalten |
|---|---|
| User entfernt „hour" aus spalte | Frontend blockt — Pflicht-Spalte. Hint sichtbar. |
| Alle Metriken auf „aus" | Backend: HTTP 422 C1. Frontend zeigt Inline-Fehler. |
| 12 Spalten, Kanal SMS | Ausgabe flache Zeile, gekürzt bei 140. `dropped=12` geloggt. |
| Trip ohne metric_config | Backend: auto-distribute als Fallback, einmal persistiert. |
| mode="indicator" ohne INDICATOR_MAP | Backend ignoriert, rendert raw. Frontend zeigt Toggle gar nicht. |
| Alter bucket="secondary" in DB | Migration → "off" (s. Migrations-Skript). |

## Out of Scope (Folge-Issues)

- Pro-Kanal-Overrides (`TripMetricChannelOverride`) — V2
- Drag-and-Drop fürs Sortieren (V1 nutzt ↑↓ Buttons)
- Custom-Indicator-Schwellen pro User
