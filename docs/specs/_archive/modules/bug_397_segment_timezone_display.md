---
entity_id: bug_397_segment_timezone_display
type: bugfix
created: 2026-05-26
updated: 2026-05-26
status: implemented
version: "1.0"
tags: [bugfix, timezone, email, sms, segment, cest, utc, issue-397]
---

<!-- Issue #397 — Segment-Zeitangaben in E-Mail-Headern zeigen UTC statt lokaler Zeit (CEST = 2h Versatz) -->

# Issue #397 — Bug-Fix: Segment-Zeitangaben in UTC statt lokaler Zeit

## Approval

- [x] Approved

## Zweck

Segment-Header in E-Mail und Schmalformat-Ausgaben (Signal/Telegram) zeigen Uhrzeiten direkt aus UTC-Datetimes (`segment.start_time`, `segment.end_time`), obwohl die Tabellen-Zeilen darunter korrekt `local_fmt(dp.ts, tz)` aus `utils/timezone.py` verwenden. Für Nutzer in CEST (UTC+2) ergibt das einen Versatz von zwei Stunden zwischen Header-Zeile und Tabellen-Zeilen derselben Sektion. Der Fix ersetzt alle direkten `.strftime('%H:%M')`-Aufrufe auf Segment-Zeitstempeln durch `local_fmt(seg.start_time, tz)` / `local_fmt(seg.end_time, tz)`, ergänzt `narrow.py` um den fehlenden Import und erweitert `build_segment_label` um einen `tz`-Parameter.

## Quelle / Source

**Geänderte Dateien:**

- `src/output/renderers/email/helpers.py` — `build_segment_label`: neuer `tz: ZoneInfo`-Parameter, UTC-`.strftime`-Aufrufe → `local_fmt`
- `src/output/renderers/email/html.py` — 5 Stellen: Ziel-Header (Zeilen 236–237), normaler Header (Zeilen 249–250), Nacht-Sektion (Zeile 285)
- `src/output/renderers/email/plain.py` — 3 Stellen: Ziel-Header (Zeile 174), normaler Header (Zeile 176), Nacht-Sektion (Zeile 183)
- `src/output/renderers/narrow.py` — 2 Stellen (Zeilen 184–185); zusätzlich: `from utils.timezone import local_fmt` importieren

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Backend-Layer (`src/output/renderers/`). Frontend, Go-API und Datenmodelle sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils/timezone.py` — `local_fmt(ts, tz)` | Hilfsfunktion | Konvertiert UTC-Datetime in lokale Zeitzone und formatiert als `HH:MM`-String |
| `src/output/renderers/email/helpers.py` — `build_segment_label` | Funktion | Baut Wetteränderungs-Label für Segment-Header; erhält neuen `tz`-Parameter |
| `src/output/renderers/email/html.py` | Renderer | HTML-E-Mail; hat bereits `tz: ZoneInfo` Parameter und `local_fmt`-Import |
| `src/output/renderers/email/plain.py` | Renderer | Plaintext-E-Mail; hat bereits `tz: ZoneInfo` Parameter und `local_fmt`-Import |
| `src/output/renderers/narrow.py` | Renderer | Schmalformat (Signal/Telegram); hat `tz: ZoneInfo` Parameter, aber fehlt `local_fmt`-Import |
| `zoneinfo.ZoneInfo` | Python stdlib | Zeitzonendaten-Typ, der durch den Call-Stack bereits übergeben wird |

## Implementation Details

### 1. `helpers.py` — `build_segment_label` um `tz`-Parameter erweitern

```python
# Vorher:
def build_segment_label(change, segments):
    ...
    start = s.segment.start_time.strftime("%H:%M")
    end = s.segment.end_time.strftime("%H:%M")

# Nachher:
def build_segment_label(change, segments, tz: ZoneInfo):
    ...
    start = local_fmt(s.segment.start_time, tz)
    end = local_fmt(s.segment.end_time, tz)
```

`from utils.timezone import local_fmt` und `from zoneinfo import ZoneInfo` als Imports ergänzen (sofern noch nicht vorhanden).

### 2. Aufrufer von `build_segment_label` — `tz=tz` übergeben

Beide Aufrufer haben bereits `tz` im Scope:

- `html.py` Zeile 372: `build_segment_label(change, segments)` → `build_segment_label(change, segments, tz=tz)`
- `plain.py` Zeile 160: `build_segment_label(change, segments)` → `build_segment_label(change, segments, tz=tz)`

### 3. `html.py` — direkte `.strftime`-Aufrufe auf Segment-Zeitstempeln ersetzen

```python
# Ziel-Segment-Header (Zeilen 236–237):
# Vorher:
seg.start_time.strftime('%H:%M')
seg.end_time.strftime('%H:%M')
# Nachher:
local_fmt(seg.start_time, tz)
local_fmt(seg.end_time, tz)

# Normaler Segment-Header (Zeilen 249–250): identisches Muster
# Nacht-Sektion (Zeile 285):
# Vorher: last_seg.end_time.strftime('%H:%M')
# Nachher: local_fmt(last_seg.end_time, tz)
```

`local_fmt` ist bereits importiert; kein neuer Import nötig.

### 4. `plain.py` — direkte `.strftime`-Aufrufe auf Segment-Zeitstempeln ersetzen

```python
# Ziel-Segment-Header (Zeile 174): seg.start_time.strftime / seg.end_time.strftime → local_fmt(…, tz)
# Normaler Segment-Header (Zeile 176): identisches Muster
# Nacht-Sektion (Zeile 183): last_seg.end_time.strftime('%H:%M') → local_fmt(last_seg.end_time, tz)
```

`local_fmt` ist bereits importiert; kein neuer Import nötig.

### 5. `narrow.py` — fehlenden Import ergänzen und `.strftime` ersetzen

```python
# Import ergänzen (bisher fehlend):
from utils.timezone import local_fmt

# Zeilen 184–185:
# Vorher:
start = seg.start_time.strftime("%H:%M")
end = seg.end_time.strftime("%H:%M")
# Nachher:
start = local_fmt(seg.start_time, tz)
end = local_fmt(seg.end_time, tz)
```

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/output/renderers/email/helpers.py` | ~5 (Parameter + 2 Substitutionen + Imports) | ja |
| `src/output/renderers/email/html.py` | ~5 (5 Substitutionen) | ja |
| `src/output/renderers/email/plain.py` | ~3 (3 Substitutionen) | ja |
| `src/output/renderers/narrow.py` | ~3 (Import + 2 Substitutionen) | ja |
| **Gesamt (zählend)** | **~16** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** `NormalizedForecast` mit Segmenten, deren `start_time`/`end_time` als UTC-`datetime`-Objekte vorliegen; `tz: ZoneInfo` wird durch den bestehenden Renderer-Stack übergeben (z.B. `ZoneInfo("Europe/Paris")` für GR20-Touren)
- **Output:** Alle Segment-Header-Uhrzeiten in E-Mail (HTML + Plaintext) und Schmalformat zeigen die lokale Uhrzeit; Tabellen-Zeilen darunter waren bereits korrekt und bleiben unverändert — kein Versatz mehr sichtbar
- **Side effects:** Keine. `local_fmt` ist eine reine Funktion ohne Seiteneffekte. Für UTC-Touren (tz=UTC) ist das Ergebnis identisch zu vorher.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer in CEST (UTC+2) mit einer Tour in Frankreich / When eine E-Mail mit Segment-Headern gerendert wird / Then zeigen Ziel-Header, normale Segment-Header und die Nacht-Sektion dieselben Uhrzeiten wie die Tabellen-Zeilen darunter (kein 2-Stunden-Versatz zwischen Header und Tabelleninhalt)
  - Test: `tests/tdd/test_issue_397_segment_timezone.py::test_render_plain_segment_header_local_time_cest`

- **AC-2:** Given eine Tour mit Wetteränderungen, die `build_segment_label` aufruft / When der Renderer `html.py` oder `plain.py` ein Wetteränderungs-Label baut / Then enthält das Label die lokale Uhrzeit statt UTC (z.B. "10:00–12:00" statt "08:00–10:00" in CEST)
  - Test: `tests/tdd/test_issue_397_segment_timezone.py::test_build_segment_label_local_time_cest`

- **AC-3:** Given `narrow.py` rendert eine Schmalformat-Ausgabe (Signal/Telegram) für eine CEST-Tour / When Segment-Zeiten in der Ausgabe erscheinen / Then zeigen `start` und `end` lokale Uhrzeiten, weil `local_fmt` korrekt importiert und aufgerufen wird
  - Test: `tests/tdd/test_issue_397_segment_timezone.py::test_render_narrow_segment_header_local_time_cest`

## Known Limitations

- **`report_date`-Formatierung unberührt:** `report_date = ...strftime("%d.%m.%Y")` betrifft nur das Datum (keine Uhrzeitproblematik für Standard-Touren) und wird nicht geändert.
- **Legacy-Methoden in `trip_report.py`:** Toter Code mit analogen `.strftime`-Aufrufen auf UTC-Zeitstempeln; wird in separaten Issues #398 und #399 adressiert, nicht im Scope dieses Fixes.
- **Kein echter E2E-Netzwerktest:** Der Korrektheitsbeweis basiert auf Unit-Tests mit UTC-Datetimes und bekannten Offsets; eine echte IMAP-Verifikation mit CEST-Tour würde ein Staging-Fixture in Nicht-UTC-Zeitzone erfordern.

## Out of Scope

- `trip_report.py` Legacy-Renderer (Issues #398, #399)
- `extract_hourly_rows`-Filter (intern UTC-konsistent, kein Bug)
- Änderungen am Datenmodell oder an `utils/timezone.py`
- Neue Zeitzonenkonfiguration oder ENV-Variablen

## Changelog

- 2026-05-26: Initial spec erstellt. Ersetzt alle direkten `.strftime('%H:%M')`-Aufrufe auf Segment-Zeitstempeln in 4 Renderer-Dateien durch `local_fmt(seg.{start,end}_time, tz)`. Erweitert `build_segment_label` um `tz`-Parameter. Ergänzt fehlenden `local_fmt`-Import in `narrow.py`. Behebt 2-Stunden-Versatz zwischen Segment-Header und Tabellen-Zeilen für CEST-Nutzer (Issue #397).
