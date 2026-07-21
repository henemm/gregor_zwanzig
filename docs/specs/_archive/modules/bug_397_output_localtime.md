# Spec: Briefing-Ausgabe durchgängig in Ortszeit (Bugs #397 / #398 / #399)

**Status:** Draft — wartet auf PO-Approval
**Created:** 2026-05-26
**Issues:** #397 (hoch, user-gemeldet), #398 (Nacht-Sektion), #399 (Mitternacht-Filter)
**Verwandte Spec:** `docs/specs/bugfix/utc_localtime_display.md` (Vorarbeit — diese Spec vollendet sie)
**Schweregrad:** hoch — Wanderer treffen Tour-Entscheidungen anhand der angezeigten Zeiten.

## Problem & Ursache

Segment-Zeiten werden intern **korrekt als UTC** geführt (validiert in `segment_weather.py:210-226`). Beim **Anzeigen** ist die Umrechnung in Ortszeit jedoch **unvollständig** — ein früherer Fix konvertierte nur die Tabellen-Datenzeilen (`_dp_to_row` nutzt `local_hour`), nicht aber Überschriften, Filter und Ankunftsstunde:

- **#397 (Header↔Tabelle):** Segment-Überschrift zeigt `start_time.strftime('%H:%M')` = **UTC** („08:00–10:00"), die Tabellen-Zeilen darunter zeigen `local_hour(...)` = **Ortszeit** (10, 11, 12). → Widerspruch. Die Zeilen-Auswahl (UTC-Stunde) ist intern konsistent — es reicht, **die Überschrift auf Ortszeit umzustellen**, dann passen Überschrift und Tabelle zusammen.
- **#398 (Nacht 2 h zu spät):** `_extract_night_rows` vergleicht `local_dt.hour >= arrival_hour`, aber `arrival_hour = last_seg.segment.end_time.hour` ist **UTC** (`trip_report.py:89`). Für CEST (UTC+2) ist die Grenze 2 h zu niedrig.
- **#399 (leere Tabelle über Mitternacht):** Stunden-Filter `start_h <= dp.ts.hour <= end_h` ist bei Mitternachts-Übergang (`start_h > end_h`, z. B. 23…1) **nie erfüllbar** → 0 Zeilen. Betrifft `trip_report._extract_hourly_rows:197` und `segment_weather.py:166`.

**Wichtige Befund-Korrektur:** Die in #399 genannten Modul-Funktionen `extract_hourly_rows`/`extract_night_rows` in `src/output/renderers/email/helpers.py` sind **toter Code** (keine Aufrufer in `src/`). Die **lebenden** Extraktoren sind die Formatter-Methoden in `src/formatters/trip_report.py`. Der Fix muss den lebenden Pfad treffen.

## Lösung

Die UTC→Ortszeit-Umrechnung am Anzeige-/Filter-Rand **vervollständigen**, mit den bestehenden Helfern `local_fmt` / `local_hour` aus `src/utils/timezone.py`. Interne Pipeline bleibt 100 % UTC.

1. **Segment-/Ziel-Überschriften → Ortszeit** (`local_fmt(t, tz)` statt `t.strftime`):
   `email/html.py` (236-237, 249-250, 285), `email/plain.py` (174, 176, 183), `narrow.py` (184-185), `email/helpers.py:build_segment_label` (521-522, braucht `tz`-Parameter), `formatters/sms_trip.py` (213). Report-Datums-Header (`html.py:201`, `plain.py:122`, `narrow.py:174`) ebenfalls auf Ortszeit, damit bei Mitternachts-Segmenten Datum + Zeit zusammenpassen.
2. **arrival_hour → Ortszeit:** `trip_report.py:89` `arrival_hour = local_hour(last_seg.segment.end_time, self._tz)`; analog `sms_trip.py:71`.
3. **Mitternachts-Übergang im Filter:** `trip_report._extract_hourly_rows` (197) und `segment_weather.py` (166):
   ```python
   include = (start_h <= h <= end_h) if start_h <= end_h else (h >= start_h or h <= end_h)
   ```
4. **Toter Code:** `extract_hourly_rows`/`extract_night_rows` in `helpers.py` entfernen (Konsolidierung; nur wenn keine Test-Abhängigkeit — sonst dort mitfixen statt Inkonsistenz zu hinterlassen).

## Acceptance Criteria

**AC-1 (#397):** Given ein Segment mit UTC-Fenster 08:00–10:00 und Ortszeit CEST (UTC+2), When das E-Mail-/Narrow-Briefing gerendert wird, Then zeigt die Segment-Überschrift „10:00–12:00" und die Tabellen-Zeilen darunter 10, 11, 12 — Überschrift und Tabelle nennen **dieselbe** Zeitbasis (Ortszeit).

**AC-2 (#398):** Given ein Trip mit letzter Ankunft 20:00 Ortszeit (18:00 UTC) in CEST, When das Abend-Briefing die Nacht-Sektion erzeugt, Then beginnt der Nachtblock bei der **lokalen** Ankunftsstunde (ab 20:00), nicht 2 h später.

**AC-3 (#399):** Given ein Segment mit Fenster, das Mitternacht überschreitet (z. B. 23:00–01:00), When die Tabelle gefiltert/aggregiert wird, Then enthält sie die Datenpunkte beider Seiten der Mitternacht (nicht leer).

**AC-4 (keine Regression):** Given ein Segment ohne Mitternachts-Übergang in UTC (z. B. 08:00–10:00), When gerendert wird, Then identische Zeilenauswahl wie zuvor (gleiche Datenpunkte), nur Überschrift jetzt Ortszeit.

**AC-5 (UTC-Sonderfall):** Given Zeitzone = UTC (Fallback), When gerendert wird, Then bleiben Überschrift und Tabelle exakt wie heute (keine Verschiebung).

**AC-6 (Kanal-Konsistenz):** Given dasselbe Segment, When E-Mail-HTML, Plaintext, Narrow (Signal/Telegram) und SMS gerendert werden, Then zeigen **alle** Kanäle dieselbe lokale Überschrift-Zeit.

## Tests (mock-frei)

- Echte `TripReportFormatter.format_email()`-Aufrufe mit konstruierten CEST-Segmenten (UTC-Eingabe, ZoneInfo("Europe/Berlin")) — Assert auf gerenderten HTML/Plain/Narrow-String: Überschrift-Zeit == Tabellen-Zeit (AC-1), Nachtblock-Startstunde (AC-2), Mitternachts-Segment liefert Zeilen (AC-3).
- UTC-Fallback-Fall (AC-5) und Nicht-Wrap-Regression (AC-4).
- Keine `Mock()`/`patch()` — echte Formatter-Pipeline mit echten ForecastDataPoint-Fixtures.

## Risiken

- **Datums-Header bei Mitternachts-Segmenten:** Lokale Umrechnung kann das angezeigte Datum verschieben (UTC 23:00 = lokal 01:00 nächster Tag) — gewollt, aber Tests müssen das absichern.
- **`tz` muss bis `build_segment_label` + `sms_trip` durchgereicht werden** (heute teils nicht). Signatur-Erweiterung, abwärtskompatibel mit Default `ZoneInfo("UTC")`.
- **Toter helpers.py-Code:** Entfernen kann Tests brechen, die ihn direkt importieren → vor Entfernen Test-Referenzen prüfen.
- LoC: mittel (Header-Sites + 2 Filter + arrival_hour + Tests). Ggf. `loc_limit_override`.
