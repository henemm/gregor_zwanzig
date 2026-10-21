# Context: feat-1737-alarm-stundenzeilen

## Request Summary
Issue #1737: Der Abweichungsalarm soll den betroffenen Zeitraum so zeigen wie das Trip-Briefing — eine Zeile je Stunde mit Uhrzeit und Stufe (ROH) bzw. farbigem Punkt (EINFACH), damit klar ist, *wann* sich *was* geändert hat. PO hat am 2026-10-20 bestätigt: volle Stundenansicht gewünscht, obwohl die „-67 %“-Anzeige bereits weg ist.

## Ist-Stand (wichtig)
- Die Prozentanzeige aus dem Issue-Screenshot ist seit #1948 S6 (Commit 0fb21f54f, PR #2026, 2026-08-21) entfernt. Die Mail zeigt heute Stufenwort alt→neu, „N Stufen“ und „stärkste Stunde HH:MM“.
- `delta_pct` (`src/output/renderers/alert/model.py:286`) existiert noch, hat aber keinen Aufrufer.
- Offen ist nur der Stundenverlauf.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py` | Alle Alarm-Kanäle: `render_email` :1349 (HTML+Plain), `render_telegram` :1483, `render_sms`/`_sms_token` :1619/:1539, `render_subject` :1202, Mehr-Ereignis-Zeilen :1393-1431, `_when_suffix` :304, `_val`/`_thunder_word` :49/:87. `render_deviation_alert` :1812 ist ein Kompat-Shim, den nur noch Tests aufrufen |
| `src/output/renderers/alert/model.py` | `AlertEvent` :16-85 — nur EIN Zeitpunkt (`occurred_at`); hier käme ein Stundenreihen-Feld hinzu |
| `src/output/renderers/alert/project.py` | `to_alert_message` :311, Bau von `AlertEvent` :366; frische Stundenreihe über `eintrag = _find_segment(...)` bereits greifbar (für `_remaining_fields`). `to_multi_point_alert_message` ~:445 (Ortsvergleich) hat KEINE Stundenreihe |
| `src/services/weather_change_detection.py` | Detektor `detect_changes` :737 vergleicht nur `aggregated` (:765f); `_peak_occurred_at` :407 liest die neue Stundenreihe nur für den Spitzenzeitpunkt |
| `src/services/weather_snapshot.py` | Alarm-Anker (ADR-0056) `save_alarm_anchor` :241 / `load_alarm_anchor` :282 speichert die ALTE Prognose stündlich (`"hourly"`, :531-544) |
| `src/services/trip_alert.py` | `_detect_all_changes` :1734, Anker-Laden :1393/:1494, Aufruf `send_deviation_alert` :3065 (übergibt nur die frische Prognose, nicht den Anker); `telegram_style` :479 |
| `src/services/notification_service.py` | `send_deviation_alert` :960, `send_multi_location_deviation_alert` :1036, `_dispatch_alert_message` :1807 (Render pro Kanal :1867-1876; SMS-Text auch für Premium-SMS + Telegram-Kurzform) |
| `src/output/renderers/email/helpers.py` | Briefing-Zellformat `fmt_val` :762 (Gewitter :804-836, Punkt via `_ampel_dot_css` :666), `build_format_modes` :1247, `build_html_indicator_keys` :1264, `build_friendly_keys` :1226 |
| `src/output/renderers/email/html.py` / `plain.py` | Briefing-Stundentabelle `_render_html_table` :659, `_render_mobile_hour_list` :320, `_render_text_table` :61 |
| `src/output/renderers/sms_trip.py` | SMS-eigene Formatlogik :99-106 |
| `src/services/compare_alert_preview_service.py`, `validator_render_service.py:224`, `radar_alert_service.py:100` | Weitere Aufrufer derselben Renderer |
| `src/app/models.py` | `WeatherChange` :602ff, `AlertMetric` :1233 |

## Existing Patterns
- Ein Backend-Renderer für alle Alarm-Kanäle (ADR-0011); Trip und Ortsvergleich teilen Engine und Renderer (ADR-0021).
- Briefing entscheidet pro Kanal zwischen Wort/Zahl und Punkt über die Anzeige-Konfiguration des Trips (`display_config`, Kanal-Kaskade). Der Alarm-Renderer liest diese Konfiguration bisher NICHT (nur `telegram_style`).
- Stufenwörter im Alarm kommen bereits aus dem Briefing-Register (#1948 S6, #1401b).
- Mail rendert Ampel als CSS-Punkte, nicht als Emojis (#2220).

## Dependencies
- Upstream: Detektor (Tagesaggregat), Alarm-Anker (alte Stundenreihe), frische Prognose (`SegmentWeatherData.timeseries`), Trip-`display_config`.
- Downstream: alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS), Ortsvergleich-Alarm, Alarm-Vorschau (Compare), Validator-Render-Service, Radar-Alarm.

## Existing Specs / ADRs
- ADR-0009, ADR-0011, ADR-0013, ADR-0021, ADR-0056
- `docs/specs/modules/alert_render_foundation.md`, `fix_1703_s1_alert_renderer_matrix.md`, `fix_1861_1865_alarm_mail_klarheit.md`, `fix_1948_s6_alarm_stufenwort.md`, `fix_2020_alarm_zeitangaben.md`, `fix_2020_alarm_blickrichtung.md`, `feat_2050_s4c_ein_ereignis_ein_alarm.md`, `feat_1701_alarm_premium_sms.md`, `fix_1401b_register_stundenverlauf_alarme.md`, `trip_alert.md`

## Risks & Considerations
- **Alte Stundenwerte:** liegen im Anker vor, werden aber nicht bis zum Renderer durchgereicht → neuer Parameter von `send_deviation_alert` nötig. Fehlt der Anker (erster Alarm), muss die Darstellung ohne „alt“-Spalte auskommen.
- **Ortsvergleich:** `to_multi_point_alert_message` hat keine Stundenreihe — Parität klären (alle Flächen sollen gleich antworten, CLAUDE.md).
- **Kanalbreite:** SMS/Premium-SMS ≤160 Zeichen — dort kann es keine echte Stundentabelle geben, nur eine verdichtete Stundenspanne. „Jeder Kanal beantwortet dieselbe Frage“ (Epic #2133): Uhrzeit des Ereignisses muss überall erkennbar sein.
- **Mehr-Ereignis- und Mehr-Metrik-Alarme:** Stundenzeilen pro Ereignis vs. gemeinsame Tabelle — Darstellungsentscheidung für die Spec.
- **Anzeigemodus:** ROH vs. EINFACH muss aus der Trip-Konfiguration kommen (Kanal-Kaskade wie im Briefing), nicht hart verdrahtet.
- **Bestandstests:** ca. 88 Testdateien referenzieren den Alert-Renderer, darunter byte-genaue Strukturtests (`test_957_alert_mail_literal_structure.py`).
- **Gates:** `renderer_mail_gate.py` verlangt für `alert/*` Matrix-Nachweis + `radar_alert_mail_validator.py`; wird `email/helpers.py` angefasst, zusätzlich Briefing- und Compare-Nachweis.
- **Nur Daten, keine Handlungsempfehlung** (Produktregel) — Stundenzeilen zeigen Werte, keine Ratschläge.

## Analysis

### Type
Feature (Issue trägt Label `type:bug`, inhaltlich aber neue Darstellung: Stundenverlauf im Abweichungsalarm). Prozentanzeige ist seit #1948 S6 weg; offen ist allein „wann hat sich was geändert“.

### Befunde der Recherche
- **Alte Stundenwerte vorhanden, aber nicht durchgereicht.** `check_and_send_alerts` (`src/services/trip_alert.py:627`) hat `cached_weather` (Quelle laut `_get_cached_weather` :1303: Briefing-Anker > rollierender Alarm-Anker > undatierter Rückfall; alle `List[SegmentWeatherData]` mit `timeseries`) im Scope, übergibt bei :938 an `_send_alert` (:3016) aber nur `fresh_weather`; `send_deviation_alert` (`notification_service.py:960`) bekommt keine alte Reihe.
- **Ortsvergleich symmetrisch:** `CompareWeatherSnapshotService.save` (`compare_weather_snapshot.py:53-80`) speichert `hourly` vollständig; `_evaluate_one_location` (`compare_alert.py:599`) hat `cached[0].timeseries` im Scope, reicht nur `fresh_point`/`changes`/`anchor_fetched_at` weiter → `send_multi_location_deviation_alert` (:1040) → `to_multi_point_alert_message` ohne Stundenreihe.
- **`WeatherChange`** (`models.py:~602`) trägt nur Aggregat alt/neu + `occurred_at` (Spitze, `_peak_occurred_at` `weather_change_detection.py:407`, filtert auf Segmentfenster :445). Kein Zeitfenster.
- **`AlertEvent`** (`alert/model.py:16`) hat kein Stundenfeld; additiv erweiterbar (Muster `segment_id`, `location_label`).
- **Renderer kennt keinen Anzeigemodus.** `AlertMessage`/`AlertEvent` ohne `format_mode`; Projektion baut ohne `display_config`.
- **Wiederverwendung:** `ampel_level` (`email/helpers.py:731`, metric_id-basiert) und `_ampel_dot_css` (:666) direkt nutzbar. `fmt_val` (:762) braucht col_key-indizierte `format_modes`/`indicator_keys`; das Telegram-Briefing ruft es bereits ohne HTML nur mit `friendly_keys` auf (`narrow.py:83-88`) → derselbe Zellformatierer ist für Telegram-Alarmzeilen nutzbar, damit Telegram-Alarm und Telegram-Briefing gleich aussehen. Modus-Auflösung: `loader._resolve_format_mode` :60 / `helpers._effective_format_mode` :56 / `build_format_modes` :1247 / `get_metrics_for_channel` (`models.py:939`, Kanal-Kaskade).
- **Stufen gibt es nicht für alle Metriken.** Ampelfähig nur wind, gust, precipitation, rain_probability, cape (`_AMPEL_CAPABLE_METRIC_IDS` helpers :1264); Gewitter hat eigenen Stufenpfad (`is_level=True`, einzige Level-Metrik). Temperatur u. a. haben keine Stufe.
- **Stundengröße:** fast alle Katalogmetriken haben `dp_field` (`metric_catalog.py`); Summen (Niederschlag, Neuschnee) entstehen aus Stundenwerten (`precip_1h_mm`). Ausnahme `precip_heavy_onset_utc` (Zeitpunkt, läuft schon als `OnsetShiftEvent`).
- **Specs/ADRs:** keine Entscheidung, die eine Stundenansicht im Alarm ausschließt oder fordert; keine ROH/EINFACH-Regel für Alarme. `fix_1948_s6` (Nicht-Ziele, Z. 82): „SMS bleibt bei LEVELS“ — gilt für die Stufen-Tokens; eine zusätzliche Zeitspanne ändert die Tokens nicht und ist damit verträglich. Zeitformat `local_fmt %H:%M` laut fix_1948_s6 mit #2009 abgestimmt → übernehmen, nicht neu erfinden.
- Keine parallele Arbeit: `git log HEAD..origin/main --grep "#1737"` leer (2026-10-20).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/model.py` | MODIFY | `AlertEvent.hours` (Tupel Stundenzeilen: Ortszeit, alt, neu, Stufe alt/neu), Anzeigemodus je Kanal an `AlertMessage` |
| `src/output/renderers/alert/project.py` | MODIFY | `to_alert_message` + `to_multi_point_alert_message`: Stundenzeilen aus alter (Anker) und neuer Reihe bauen, Paarung per UTC-`ts` im Segmentfenster, Ortszeit über bestehenden `_tz_for_location` |
| `src/output/renderers/alert/render.py` | MODIFY | E-Mail (Einzel `_datablock_single` :1271, Mehr-Ereignis :1393-1431), Telegram :1483, SMS/Premium-SMS :1619 (Zeitspanne, LEVELS-Tokens bleiben) |
| `src/output/renderers/alert/hours.py` | CREATE (evtl.) | schmaler Helfer: betroffene Stunden bestimmen, Zelle ROH/EINFACH (nutzt `ampel_level`/`_ampel_dot_css`/Gewitter-Wort) — vermeidet Eingriff in `email/helpers.py` |
| `src/services/trip_alert.py` | MODIFY | `cached_weather` an `_send_alert` → `send_deviation_alert` durchreichen |
| `src/services/notification_service.py` | MODIFY | `send_deviation_alert`, `send_multi_location_deviation_alert`, `_dispatch_alert_message`: alte Reihe + `display_config` an Projektion/Renderer |
| `src/services/compare_alert.py` | MODIFY | `cached[0]` pro Ort als `anchor_points` mitgeben |
| `src/services/compare_alert_preview_service.py` | MODIFY | Vorschau zeigt dieselben Stundenzeilen wie der Versand |
| `src/services/validator_render_service.py` | MODIFY (prüfen) | Aufrufer desselben Renderers mitziehen |
| Tests (neu, nach Verhalten benannt, z. B. `tests/tdd/test_alert_hour_rows.py`) | CREATE | Kern-Tests mit aufgezeichneter Anker-/Frisch-Reihe, alle 4 Kanäle, Trip + Ortsvergleich, ROH/EINFACH, ohne Anker |
| Bestandstests (`test_957_alert_mail_literal_structure.py`, `test_issue_918_alert_preview_4ch.py` u. a.) | MODIFY (ggf.) | an neue Struktur anpassen, wo sie Zeilenzahl festschreiben |

**Ausdrücklich NICHT betroffen:** Radar-/Onset-Alarm (`radar_alert_service.py`, `OnsetShiftEvent`) — trägt keine Stufen-Abweichung je Stunde, sondern einen Einsatzzeitpunkt; amtlicher Alarm (eigener Renderer); `delta_pct` bleibt tot (Prozent bleibt weg).

### Scope Assessment
- Files: ~9 produktiv + Tests
- Estimated LoC: +400 bis +480 / −30 (Schätzung, produktiv)
- Risk Level: MEDIUM — zentraler, von allen vier Kanälen und beiden Flächen geteilter Renderer; aber additiv (ohne Stundenreihe bleibt heutige Ausgabe).
- **Ein Workflow, keine Scheiben:** alle vier Kanäle + Ortsvergleich in EINER Spec (Epic-Regel „themenweise abschließen“; Kanäle müssen dieselbe Frage beantworten, Epic #2133). LoC-Limit per `workflow.py set-field loc_limit_override 500` anheben, sobald `status` den realen Stand zeigt.

### Technical Approach (Empfehlung)
Variante „alt→neu je Stunde, Modus aus der Trip-Konfiguration“:
1. Alte Reihe (Anker) und neue Reihe bis zur Projektion durchreichen (Trip und Ortsvergleich gleich).
2. Projektion bildet je Ereignis die **betroffenen Stunden**: Stunden im Segmentfenster, gepaart per UTC-Zeitstempel. Betroffen ist eine Stunde, wenn sich **die Stufe ändert** (Metriken mit Stufe: ampelfähige + Gewitter) bzw. — bei Metriken ohne Stufe — wenn **die Stundendifferenz die Alarmschwelle der Metrik erreicht**. Zusammenhängender Bereich von erster bis letzter betroffener Stunde.
3. Ohne alte Reihe (kein/alter Anker ohne `hourly`, Stunde fehlt): Zeile zeigt nur den neuen Wert; ohne jede Stundenreihe bleibt die heutige Darstellung.
4. Anzeigemodus je Kanal aus `display_config` über dieselbe Auflösung wie das Briefing (`_resolve_format_mode`, Kanal-Kaskade).
5. Kanalformen: E-Mail = Tabellenzeilen „HH:MM | alt → neu“ (ROH: Stufenwort/Wert wie Briefing; EINFACH: CSS-Punkte); Telegram = Zeilenliste mit demselben Zellformat wie das Telegram-Briefing; SMS/Premium-SMS = verdichtete Zeitspanne „HH–HH“ am bestehenden Token (LEVELS-Tokens unverändert, ≤160 Zeichen).

### Begründete Defaults für die Spec (vom PO über die ACs freizugeben)
- **alt→neu je Stunde** — vom Issue gefordert („war Stufe 3, jetzt 1 — zu welcher Uhrzeit?“).
- **ROH/EINFACH folgt dem Briefing desselben Kanals** — vom Issue gefordert („kenne ich bereits“).
- **Höchstens 6 Stundenzeilen je Ereignis**; längere Bereiche: die 6 stärksten Stunden in Zeitreihenfolge + Hinweiszeile „betroffen HH:MM–HH:MM“. (Mail bleibt auf dem Handy lesbar.)
- **Mehr-Ereignis-/Mehr-Metrik-Alarm:** je Ereignis ein eigener Stundenblock unter seiner Kopfzeile (bestehende Struktur bleibt, keine Kreuztabelle).
- **Ortsvergleich:** Stundenzeilen je betroffenem Ort, gleiche Kappung.
- **Summen-Metriken:** Summe bleibt in der Ereignis-Kopfzeile, Stundenzeilen zeigen die Stundenwerte.
- **Zeitformat:** Ortszeit `HH:MM` wie bisher (`local_fmt`, mit #2009 abgestimmt).
- **Ohne Anker:** nur neuer Wert, ohne Zusatzhinweis (heutiger Alarm gibt auch keinen).

### Dependencies
- Upstream: Alarm-Anker Trip (`weather_snapshot.py:241/282`), Compare-Snapshot (`compare_weather_snapshot.py`), frische Prognose `SegmentWeatherData.timeseries`, `display_config`-Kaskade.
- Downstream: E-Mail, Telegram, SMS, Premium-SMS; Trip- und Ortsvergleich-Alarm; Alarm-Vorschau; Validator-Render-Service.
- Gates: `renderer_mail_gate` (Matrix-Nachweis + `radar_alert_mail_validator.py` für `alert/*`); `email/helpers.py` möglichst nicht anfassen (sonst zusätzlich Briefing-/Compare-Nachweis).

### Open Questions
- [x] alt→neu oder nur neu? → alt→neu (Issue)
- [x] Darstellungsmodus? → wie Briefing je Kanal (Issue)
- [ ] Kappung (6 Zeilen) und Ortsvergleich je Ort — als Default in der Spec, Freigabe über die ACs in `/30`
