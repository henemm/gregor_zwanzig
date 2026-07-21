# Spec: fix-839-fmt-val-thresholds

Issue: #839

## Kontext

Seit Commit `945a824c` ("Restore _fmt_val") schlagen 5 Unit-Tests fehl. Ursache: Commit #759
hat den Metrik-Katalog von 3-stufig auf 4-stufige Ampeln umgestellt (gelb/orange/rot). Der
"blue"-Schwellwert für `precipitation` und `rain_probability` existiert seitdem nicht mehr im
Katalog. Commit `945a824c` hat `_fmt_val` restauriert, aber weiterhin `dt.get("blue")` abgefragt
— was nie greift → Backgrounds werden nie gerendert.

Zwei unabhängige Root Causes:

1. **Stale Katalog-Test-Erwartungen** — 3 Tests erwarten alte Threshold-Dictionaries
2. **`_fmt_val` sucht "blue" statt aktuellem Schlüssel** — precip sucht orange(5.0mm),
   pop sucht red(80.0%)

## Änderungen

### 1. `tests/unit/test_configurable_thresholds.py`

- `test_gust_display_thresholds` (Zeile ~48): `{"yellow": 50.0, "red": 80.0}` → `{"yellow": 50.0, "orange": 65.0, "red": 80.0}`
- `test_precipitation_display_thresholds` (Zeile ~73): `{"blue": 5.0}` → `{"yellow": 1.0, "orange": 5.0, "red": 10.0}`
- `test_rain_probability_display_thresholds` (Zeile ~83): `{"blue": 80.0}` → `{"yellow": 30.0, "orange": 60.0, "red": 80.0}`

### 2. `src/formatters/trip_report.py`

- `_fmt_val` für `precip` (~Zeile 706): `dt.get("blue")` → `dt.get("orange")`
- `_fmt_val` für `pop` (~Zeile 748): `dt.get("blue")` → `dt.get("red")`

Kein neuer Produktivcode, kein neues Verhalten — nur Reparatur des unterbrochenen Rendering-Pfades.

## Was darf sich nicht ändern

- HTML-Farbe `#e3f2fd` (blau) für Regen-Metriken bleibt
- `gust`-HTML-Logik (nutzt bereits korrekt `red`/`yellow`) bleibt unverändert
- Alle anderen `_fmt_val`-Pfade bleiben unverändert
- Katalog-Werte selbst werden nicht geändert

## Acceptance Criteria

**AC-1:** Given `_fmt_val("precip", 6.0, html=True)` aufgerufen wird (6.0mm >= orange-Schwelle 5.0mm), When der Formatter ausgeführt wird, Then enthält das Ergebnis `background:#e3f2fd` und die HTML-Span-Struktur.

**AC-2:** Given `_fmt_val("pop", 85.0, html=True)` aufgerufen wird (85% >= red-Schwelle 80%), When der Formatter ausgeführt wird, Then enthält das Ergebnis `background:#e3f2fd` und die HTML-Span-Struktur.

**AC-3:** Given die 3 Katalog-Tests für gust/precipitation/rain_probability laufen, When pytest ausgeführt wird, Then stimmen alle Erwartungen mit den aktuellen Katalog-Definitionen überein (4-stufige Ampeln).

**AC-4:** Given alle 5 vormals roten Tests laufen, When pytest ausgeführt wird, Then sind alle 5 grün ohne dass andere Tests im selben Modul neu rot werden.
