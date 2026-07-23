# Analyse: fix-1332-compare-official-alerts

Issue: #1332 — Ortsvergleich meldet amtliche Warnungen anders als das Trip-Briefing
(SMS gar nicht, Telegram ungefiltert). `priority:high`, `triage:a` (nutzersichtbar,
sicherheitsrelevant).

## Type

**Bug** (Divergenz-Fix / Konvergenz Trip↔Compare). Reiner Renderer-Fix — kein Datenmodell-Fix.

## Root Cause (verifiziert gegen aktuellen main, HEAD 5bc92985)

1. **Compare-SMS zeigt Warnungen gar nicht** — `src/output/renderers/comparison.py`
   `render_compare_sms` (469–539) + Helfer `_sms_location_part` (449–466) /
   `_channel_metric_cells` (340–358) lesen ausschließlich `_CHANNEL_METRICS`
   (Temp/Wind/Sonne/Wolken/Schnee). `loc_result.official_alerts` wird im SMS-Pfad
   **nirgends** gelesen.
2. **Compare-Telegram rendert ungefiltert & ohne Kürzel** — `comparison.py:401–404`
   (`render_compare_telegram`) ruft `render_official_alerts_plain()` aus
   `src/output/renderers/alert/official_alerts.py:234–252`. Diese Funktion hat **keinen
   Stufenfilter** (auch gelb/grün) und **kein Kürzel** — jede Warnung erscheint als
   ausgeschriebener Satz `"Amtliche Warnung: {label}"`.
   (Issue-Behauptung „Datei existiert nicht mehr" war falsch — Pfad ist
   `renderers/alert/official_alerts.py`.)
3. **Trip macht es seit #1318 richtig** — Filter ab `MIN_SMS_LEVEL` (orange), Kürzel aus
   `src/output/tokens/hazard_symbols.py`.

## Datenverfügbarkeit

Kein Datenproblem: `LocationResult.official_alerts` (`src/app/user.py:160`) ist derselbe
Typ wie im Trip-Pfad, befüllt in `src/services/comparison_engine.py:223–224` über
dieselbe Quelle (`services.official_alerts.get_official_alerts_with_status`). Daten liegen
im Compare-Renderpfad vollständig vor.

## Geteilte Trip-Bausteine (TEILEN, nicht nachbauen — PO-Invariante)

- **SMS:** `_official_alert_entries(segments, tz) -> tuple[(kürzel, stufe, stunde), ...]`
  in `src/output/renderers/sms_trip.py:93–118`. Filtert `alert.level < MIN_SMS_LEVEL:
  continue`, Kürzel via `sms_symbol_for()`. **Aber:** an `list[SegmentWeatherData]`
  gebunden, nicht an `LocationResult`.
- **Telegram:** `build_official_alert_notices(trip|None, tagged_alerts)` +
  `render_official_alert_telegram()` (`official_alerts.py:1692 / 1415`). Laut Docstring
  (`official_alerts.py:124–126`) ist `OfficialAlertNotice` **explizit kontext-agnostisch**
  („Trip UND Ortsvergleich füllen dasselbe DTO"); `trip=None` wird bereits akzeptiert.
  Die Wiederverwendung war architektonisch vorgesehen, nur nie für Compare verdrahtet.

## Affected Files

| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/comparison.py` | MODIFY | Compare-SMS: Warn-Block pro Ort (ab orange). Compare-Telegram: Level-Filter + `build_official_alert_notices`/`render_official_alert_telegram` statt `render_official_alerts_plain`. |
| `src/output/renderers/sms_trip.py` | evtl. MODIFY | Nur falls gemeinsamer Kern von `_official_alert_entries` extrahiert wird (siehe Technischer Ansatz). |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Bedingung `context !== 'vergleich'` (Zeile 665) entfernen → Kürzel-Legende auch im Vergleich (nach Backend-Fix). |
| `tests/...` | CREATE | Kern-Tests Compare-SMS + Compare-Telegram mit amtlichen Warnungen (echte Fixtures). |

## Scope Assessment

- Files: 3 Code + 1 Test
- Est. LoC: +~90 / -~10 (unter 250-Limit)
- Risk Level: **MEDIUM** — betrifft zwei versendete Kanäle; Trip-Pfad darf nicht brechen.

## Technischer Ansatz (Empfehlung)

**Compare ruft die geteilte Kürzel-/Filter-Logik auf; Trip-Datei möglichst nicht umbauen.**

- **Telegram (risikoarm):** direkt `build_official_alert_notices(trip=None, ...)` +
  `render_official_alert_telegram()` verwenden, Level-Filter `>= MIN_SMS_LEVEL` davor —
  diese Bausteine sind bereits kontext-agnostisch, kein Nachbau.
- **SMS:** Der geteilte Kern ist die Abbildung `OfficialAlert → (kürzel, stufe, stunde)`
  via `sms_symbol_for()` + `MIN_SMS_LEVEL`. Da `_official_alert_entries` an
  `SegmentWeatherData` hängt, den **inneren, alert-basierten Kern** in eine gemeinsam
  nutzbare Funktion ziehen (Eingabe `list[OfficialAlert]`), die sowohl `sms_trip.py` als
  auch `comparison.py` aufrufen — so wird echt geteilt statt dupliziert. Fallback, falls
  Trip-Umbau zu riskant: schlanker Compare-Adapter, der dieselben Bausteine
  (`sms_symbol_for`, `MIN_SMS_LEVEL`, Token-Builder) aufruft (kein zweiter Katalog).
  **Finale Schnittfrage in /30-write-spec entscheiden.**

## Design-Entscheidung (PO-go 2026-07-23)

Compare-SMS: **Warn-Marker pro Ort direkt am Ort** (nicht aggregiert), **nur ab Stufe
orange**. Beispiel: `Chamonix 18/8 !TH:H`. Verdrängt bei Platzmangel über die bestehende
Kürzungs-Kaskade ggf. eine Metrik-Zelle — Sicherheit vor weicher Optik (Design-Leitprinzip).

## Konvergenz-Bezug

PO-Invariante Trip/Compare-Teilung: der Fix schließt genau die Divergenz, die #1318 für
Trip geschlossen hat. Nach dem Backend-Fix entfällt die kontextabhängige Ausblendung der
Legende in `WeatherMetricsTab.svelte`.

## Open Questions

- [ ] /30: Gemeinsamen Kern aus `_official_alert_entries` extrahieren (echtes Teilen, berührt
      Trip-Datei) **oder** Compare-Adapter (kein Trip-Umbau)? Empfehlung: Extraktion, sofern
      Charakterisierungs-Test den Trip-SMS-Pfad unverändert absichert.
