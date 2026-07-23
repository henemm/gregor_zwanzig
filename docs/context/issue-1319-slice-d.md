# Context: #1319 Scheibe D — N (Nacht-Tiefsttemperatur) nur im Abendbriefing

**Workflow:** issue-1319-slice-d
**Issue:** #1319 (Epic, OPEN) — Scheibe D
**Typ:** Änderung an bestehendem Verhalten (N-Logik in den Kurzformen)

## PO-Entscheidungen (2026-07-23)
- **DEC-1 Scope = (a)+(b):** N erscheint **nur im Abendbriefing** UND zeigt den **echten
  Nacht-Tiefstwert am Schlafplatz** (aus `night_weather`, Ankunft→06:00 am Etappenziel),
  NICHT mehr das Tagessegment-Minimum. Beide Teile gehören zu Scheibe D.
- **DEC-2 Morgen-Darstellung:** N wird morgens **komplett weggelassen** (Token entfällt,
  kein Platzhalter) — vgl. Epic-Beispiel `E9: D17 R...` ohne N. (Tech-Lead-Default)
- **DEC-3 Große E-Mail-Tabelle unberührt:** Der „🌙 Nacht am Ziel"-Block
  (`trip_report.py::_extract_night_rows`, `dc.show_night_block`, `email/html.py`) bleibt
  wie er ist (erscheint bewusst in beiden Report-Typen, #1313; nicht Teil des Epics, das
  betrifft nur die **Kurzformen**). (Tech-Lead-Default)
- **DEC-4 Keine Datenmigration:** reine Render-Logik, keine Persistenzänderung. (Tech-Lead-Default)

## Analysis

### Ist-Zustand (feature-planner)
N (Nacht-Tiefsttemperatur) erscheint heute **unbedingt in Morgen UND Abend**, in allen drei
Kurzformen — und der **Wert stammt aus den Tages-/Wandersegmenten**, nicht aus `night_weather`.
Effektiv zeigt N heute die „kälteste Wanderstunde" (oft der frühe Start), nicht die
Übernachtungs-Tiefsttemperatur am Ziel. Die echte Nacht-Tiefsttemperatur (~3–5 Uhr) liegt
außerhalb des 04–19-Tagesfensters und wird von `build_day_window_points` gar nicht erfasst.
`docs/reference/sms_format.md:91` spezifiziert N bereits als „Wert AM letzten GEO-Punkt der
Etappe" — Code ist davon abgedriftet. `night_weather` ist vorhanden und pro Report-Typ korrekt
an der letzten Etappe verankert (`trip_report_scheduler.py:1212-1225`).

### Delta (a) Sichtbarkeit + (b) Wert-Quelle — beide (DEC-1)
| Datei | Änderung |
|---|---|
| `src/output/tokens/builder.py:222-232` | N-Token nur bei `report_type == "evening"` bauen (Hardcode-Gate, da N keine `MetricSpec` hat); `_visible`-Pfad Z.75-81 |
| `src/output/renderers/sms_trip.py:105-133` | N-Wert (b) aus `night_weather`-Tiefst statt `day_min` aus Segmenten; `_segments_to_normalized_forecast` |
| `src/output/renderers/compact_summary.py:117-207` | `report_type` durchreichen; `_format_temperature` morgens ohne Min; Abend-Min aus night_weather |
| `src/output/renderers/trip_report.py:752-776` | `report_type` an `_generate_compact_summary`/`format_stage_summary` übergeben (fehlt aktuell) |
| `src/output/renderers/narrow.py:497-501,252-304` | Kurzübersicht-Temperaturzeile report_type-gaten; Nacht-Min-Quelle; `_tg_vortag_line` prüfen |

### Scope Assessment
- Files: 5 (alle Python-Renderer/Tokens). Kein Go, kein Frontend, keine Persistenz.
- Estimated LoC: (a) ~60 + (b) Wert-Quelle ~60–100 → grob +120–180/-40. Voraussichtlich unter 250; beobachten.
- Risk Level: **MEDIUM** — mehrere Bestandstests hardcoden N in Morgen-SMS (`test_sms_daywindow_aggregation.py:317,427,499,527`, `test_issue_245_sms_stage_colon.py`, `test_telegram_footer_metric_gating.py`, `test_issue_831_mobile_einfach.py`, `test_epic_140_preview_endpoints.py`, `test_sms_unknown_on_missing_data.py`, `test_bug305_mobile_email.py`, `test_sms_preview_matches_sent.py` u.a.) → müssen angepasst werden (strukturelle Assertion-Änderung, kein Regressionsbug). Wert-Quelle (b) muss Konsistenz mit der großen Tabelle wahren (dieselbe night_weather-Quelle).

### Konsistenz-Anspruch (Epic #1319 Punkt 6)
Alle drei Kurzformen (SMS, E-Mail-Kurzzusammenfassung, Telegram-Fußzeile/Kurzübersicht) müssen
gleich behandelt werden: morgens kein N, abends N aus night_weather.

### Offene Detailfragen (Tech-Lead-Default, in Spec festlegen)
- E-Mail-Kurzzusammenfassung morgens: nur `t_max` zeigen (kein Bereich), abends `night_min–t_max`.
- Telegram `_tg_vortag_line` „Temp min ±X°C": im Morgenbriefing konsistent entfallen (Punkt 6),
  sofern es eine Vorhersage-Aussage ist; in Spec präzisieren.
