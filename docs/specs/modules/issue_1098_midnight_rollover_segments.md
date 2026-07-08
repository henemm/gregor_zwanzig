---
entity_id: issue_1098_midnight_rollover_segments
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [bug, trip-segments, midnight, briefing]
---

# Issue #1098 — Tages-Rollover in convert_trip_to_segments

## Approval

- [ ] Approved

## Purpose

Eine echt über Mitternacht laufende Etappe (z. B. Start 22:00, Ziel-Wegpunkt 00:30) soll
end-to-end die **korrekte** Ziel-Ankunftszeit (00:30 am Folgetag) liefern und als gültiges
Segment überleben. Aktuell verliert `convert_trip_to_segments` die Tages-Info: `wp_times`
enthält nackte Uhrzeiten, alle werden mit einem einzigen `target_date` kombiniert — das
Über-Nacht-Segment läuft still in den `end_dt <= start_dt`-Klemm-Guard und die Ziel-Ankunft
wird falsch (01:15 statt 00:30).

## Source

- **File:** `src/services/trip_segments.py`
- **Identifier:** `convert_trip_to_segments` (Segment-Schleife Z.147–219, Kombination mit
  `target_date` Z.166–175)

## Estimated Scope

- **LoC:** ~20 (+16/-4)
- **Files:** 1 Quell-Datei (`src/services/trip_segments.py`) + 1 Testdatei
  (`tests/tdd/test_issue_1004_startzeit_ssot.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_interpolate_missing_times` | intern | Liefert bereits monotone Über-Mitternacht-Interpolation (#1091), aber als nackte `time` |
| `_known_time_for_index` | intern | Startzeit-Prioritätskette pro Wegpunkt (#1004) |
| `TripSegment`, `datetime.combine` | Modell/stdlib | Segment-DTO mit voller UTC-`datetime` |

## Implementation Details

Nach `wp_times = _interpolate_missing_times(known_times)` einen parallelen Tages-Offset-Vektor
bilden — der Tag wird **nur bei strikt fallender Uhrzeit** gegenüber dem letzten bekannten
Wegpunkt erhöht:

```
day = 0
prev = None
wp_days = []
for t in wp_times:
    if t is not None and prev is not None and t < prev:   # STRIKT fallend = Tagesgrenze
        day += 1
    wp_days.append(day)
    if t is not None:
        prev = t
```

In der Segment-Schleife die Datums-Kombination pro Wegpunkt mit dem jeweiligen Tages-Offset:

```
start_dt = datetime.combine(target_date + timedelta(days=wp_days[i]),   wp1_start)...
end_dt   = datetime.combine(target_date + timedelta(days=wp_days[i+1]), wp2_start)...
```

Der `end_dt <= start_dt`-Guard (Z.177) bleibt **unverändert** — er fängt weiterhin nur
kollabierte **gleiche** (`==`) Zeiten ab (AC-5 Naismith-Klemme), nicht mehr den echten
Übergang. Das Ziel-Segment (Z.221–248) erbt den korrekten Tag automatisch über
`segments[-1].end_time`; keine Änderung dort.

## Expected Behavior

- **Input:** `Trip` mit einer Etappe, deren Wegpunkt-Zeiten über Mitternacht fallen
  (z. B. `arrival_override` 22:00 → None → 00:30), plus `target_date`.
- **Output:** `List[TripSegment]` mit einem gültigen Über-Nacht-Segment; `end_time` des
  letzten regulären Segments liegt auf `target_date + 1` (00:30), Ziel-Segment erbt diese Zeit.
- **Side effects:** keine. Rückgabetyp unverändert → alle 5 Aufrufer-**Dateien** (`trip_forecast`,
  `trip_report_scheduler`, `preview_service`, `trip_command_processor`, `trip_alert`; 7–8 Call-Sites)
  unberührt — der Tages-Offset ist ein beweisbarer No-Op (`wp_days` bleibt 0) für jede nicht-fallende
  Zeitfolge.

## Acceptance Criteria

- **AC-1 (echte Über-Mitternacht-Etappe überlebt mit korrekter Ziel-Ankunft):**
  Given eine Etappe mit zwei Wegpunkten, deren maßgebliche Startzeiten 22:00 und 00:30 sind
  (`arrival_override` 22:00 am Start-Wegpunkt, 00:30 am Ziel-Wegpunkt), gespeichert und neu
  geladen / When `convert_trip_to_segments(trip, target_date)` gerufen wird / Then enthält die
  Segmentliste ein gültiges Segment mit `end_time` auf `target_date + 1 Tag` um 00:30 (nicht
  01:15, nicht am selben Tag) und das Ziel-Segment startet zu genau dieser 00:30-Zeit.
  - Test: echter `convert_trip_to_segments`-Aufruf mit realem `Trip`/`Stage`; geprüft werden
    die UTC-`datetime`-Werte `start_time`/`end_time` der zurückgegebenen `TripSegment`-Objekte
    (Datum + Uhrzeit), nicht Dateiinhalt.

- **AC-2 (AC-5-Regressionsschutz — Naismith-Klemme kollabiert weiter geloggt):**
  Given eine Etappe mit später Startzeit 22:00 und mehreren Wegpunkten, deren berechnete
  Ankunftszeiten von Naismith auf 23:59 geklemmt werden / When die Segmente gebaut werden /
  Then bleibt das erste Segment (Start 22:00) erhalten, die geklemmten Folgesegmente (gleiche
  Zeit 23:59==23:59) werden weiterhin am `end_dt <= start_dt`-Guard mit Warnung übersprungen,
  und die Liste ist nie leer.
  - Test: bestehender `test_ac5_spaete_startzeit_kein_totalausfall` bleibt grün (Regressions-
    Wächter); prüft erste Segment-Startzeit == 22:00 und WARNING-Log bei Kollaps.

- **AC-3 (normaler Tagestrip unverändert):**
  Given eine gewöhnliche Etappe mit monoton steigenden Wegpunkt-Zeiten am selben Tag
  (z. B. 08:00 → 12:00) / When die Segmente gebaut werden / Then liegen alle `start_time`/
  `end_time` am `target_date` selbst (kein Tages-Offset), Verhalten bit-identisch zu vorher.
  - Test: echter `convert_trip_to_segments`-Aufruf; alle Segment-`datetime` tragen das
    Ausgangsdatum, keine Verschiebung auf den Folgetag.

## Known Limitations

- **Mischfall 22:00 → 23:59 (Naismith-Klemme) → 00:30 (echter Override):** Der Tages-Offset-Walk
  rettet in diesem seltenen Sub-Fall das Segment `23:59 → 00:30` (31 Min) statt es zu verwerfen,
  weil 00:30 strikt < 23:59 als Folgetag gilt. Das ist konsistent und eher korrekter, embettet
  aber die 23:59-Klemme als reale Startzeit. **Kein Ziel-AC** — außerhalb des #1098-Scopes
  (echte Über-Mitternacht-Etappen); wird bewusst so belassen.
- **None-Wegpunkte:** Bei fehlender Zeit (`wp_times[i] is None`) greift der bestehende
  `cumulative_time`-Fallback; der Tages-Offset behält den aktuellen Tag bei (Best-Effort,
  unverändertes Vorverhalten).
- **Mehrere Mitternachtsübergänge:** durch monotonen Tages-Zähler (nicht Boolean) robust,
  auch wenn praktisch extrem selten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Lokaler Bugfix innerhalb einer bestehenden Funktion, keine neue Schnittstelle,
  kein neues Muster — die datetime-über-Mitternacht-Logik ist bereits durch #1091 etabliert.
  `[no-adr]` im Commit.

## Changelog

- 2026-07-08: Initial spec created (Adversary-Folge #1091)
