# Context: feat-3228-windrichtung-mail (Epic #3222, Scheibe S2)

## Request Summary
Gegenwind (Trip) bzw. Wind aus markierten Sektoren (Ortsvergleich) in der
Briefing-Mail und der Vergleichs-Mail sichtbar machen: abgeleitetes Feld
`wind_unerwuenscht_kmh` je Segment/Ort/Stunde befüllen und die WDir-Zelle über
die normale Ampel (obere Grenzen in km/h) färben. Spec: `docs/specs/modules/feat_3222_windrichtung.md`
(freigegeben 2026-11-20), ACs dieser Scheibe: AC-1, AC-2, AC-3, AC-5, AC-6, AC-8, AC-15.
Epic-Kontext (Abschnitte A-G): `docs/context/feat-3222-windrichtung.md`.

## Stand nach S1 (auf main)
- `src/services/windrichtung.py`: `wind_unerwuenscht_kmh(modus, sektoren, wind_kmh, herkunft_deg, peilung_deg)`,
  `gegenwind_kmh`, `sektor_kmh`, `sektor_von` (= `degrees_to_compass(lang=de)`), `segment_peilung_deg(segment)`
  (Luftlinie `start_point`->`end_point`, `None` unter 300 m). Alle OHNE Aufrufer.
- `src/utils/geo.py:49` `mean_direction_deg` (vektoriell), `bearing_deg`. Ohne Aufrufer.
- `src/app/ampel.py:327` `_verschmelzen` kopiert schon `modus`/`sektoren`; `deviation_count` kennt sie.
- `src/app/ampel.py:369` `AMPEL_LESER` enthält `wind_direction` NOCH NICHT -> `schwellen_aus_ampel`
  liefert `{}` -> keine Färbung. `hat_ampel()` (Z. 375) ist das Tor für alle Renderer.
- Vorlage `radtour` hat `wind_direction` modus=gegenwind, 10/20/30, alarm_ab orange (S1).

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/app/ampel.py:369-401` | `AMPEL_LESER`, `hat_ampel`, `schwellen_aus_ampel`, `ampel_stufe`, `ampel_schaerfe`, `schlimmster_index` (Z. 520) |
| `src/app/models.py:461-560` | `SegmentWeatherSummary` (neues Feld `wind_unerwuenscht_kmh`), `wind_direction_avg_deg` Z. 508 |
| `src/app/user.py:133` | `LocationResult.wind_direction_avg` -> Ortsvergleich braucht analog `wind_unerwuenscht_kmh` |
| `src/services/weather_metrics.py:960,990,1121,1306,1421` | Segment-Aggregat inkl. `_compute_wind_direction` (schon zirkulär) |
| `src/services/segment_weather.py` | baut Segment-Wetter (Segment-Geometrie verfügbar -> Peilung) |
| `src/services/comparison_engine.py:325-333,441` | Orts-Aggregat, eigenes zirkuläres Mittel (Duplikat), befüllt `LocationResult` |
| `src/output/renderers/email/helpers.py:66-130,205-222` | `should_merge_wind_dir`, `dp_to_row` (Stundenzeile), Zeilen-Aggregat mit `_wind_dir_deg` (zirkulär) |
| `src/output/renderers/email/helpers.py:725-760,933` | `_ampel_dot_severity`, `ampel_level`, `fmt_val` Zweig `wind_dir` |
| `src/output/renderers/email/html.py:206-256,568-590,640-665` | `_row_risk`, `_COL_KEY_TO_METRIC_ID` (ohne `wind_dir`), Zelltönung `ampel_level` |
| `src/output/renderers/email/compare_html.py:363,440-485,815-830,1200-1215` | CV2-Zeile `wind_direction_avg` (ohne `sev`), `_hour_zeilen`/`hat_ampel`, Zellfärbung `sev_fn(value)`, Stunden-Zelle mit angehängtem Kompass |
| `src/output/renderers/narrow.py:26,88,280,600-640` | Kurzform (`_cell`, `@h` nur bei `hat_ampel`) – wird durch `AMPEL_LESER`-Erweiterung mitbetroffen (eigentlich S3) |
| `src/output/renderers/trip_report.py:547,709` | zweiter `_dp_to_row`-Pfad (Telegram/Trip-Report) |
| `src/output/tokens/metrics.py:63-73` | `schlimmster_index`-Nutzung für Tokens/`@h` |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | Validatoren gegen echte Staging-Mail (Renderer-Gate) |
| `docs/reference/mail_validators.md`, `docs/reference/gates_und_ratschen.md` | Modus-Matrix-Test + Renderer-Commit-Gate |

## Existing Patterns
- Färbung = `severity_for(metric_id, wert, ampel=...)` bzw. `ampel_level`; Tor ist `hat_ampel`. Wert ist immer
  der Messwert der Spalte. Für Windrichtung ist der Spaltenwert aber GRAD, gefärbt werden muss nach dem
  abgeleiteten km/h-Wert -> der Wert für die Ampel muss getrennt vom Anzeigewert in die Zeile (z. B.
  `row["_wind_unerwuenscht_kmh"]`, analog `_wind_dir_deg`) bzw. Compare-Zeile mit eigenem Wertschlüssel.
- Zirkuläres Mittel existiert dreifach (weather_metrics, comparison_engine, helpers) – S1-`mean_direction_deg` wäre
  die gemeinsame Quelle; Konsolidierung nur, wenn ohnehin angefasst.
- Abgeleitete Aggregatfelder: Max der Stunden (Spec Entscheidung 1).

## Dependencies
- Upstream: `services/windrichtung.py`, `utils/geo.py`, `app/ampel.py` (resolve_ampel liefert modus/sektoren),
  `output/metric_format.severity_from_thresholds` (unverändert, ADR-0106).
- Downstream: alle Renderer, die `hat_ampel`/`AMPEL_LESER` fragen (Mail, narrow/SMS, Telegram, Tokens `@h`),
  Alarm (`ampel_alarm.py`, erst S3).

## Existing Specs
- `docs/specs/modules/feat_3222_windrichtung.md` (Epic-Spec, approved). Für S2 ggf. Scheiben-Spec ableiten.
- ADR-0106 (Ampel einzige Bewertung), ADR-0095 (Kanalparität), ADR-0126 (Richtung als Skalar, aus S1).

## Risks & Considerations
1. **WDir ist im Standard mit der Wind-Spalte verschmolzen** (`should_merge_wind_dir`, Modus `scale` = Default):
   Dann gibt es keine eigene WDir-Zelle, die Windzelle ist schon nach Windstärke gefärbt. In Analyse klären,
   was „WDir-Zelle färben“ im Merge-Fall heißt (Kompass-Teil hervorheben vs. höhere der beiden Stufen) –
   ggf. Produktfrage an PO, falls Spec es nicht hergibt.
2. **`AMPEL_LESER` erweitern wirkt kanalweit**: `narrow.py` (`@h`), Tokens, Telegram fragen `hat_ampel` mit dem
   Spaltenwert (Grad!). Ohne Gegenmaßnahme würden Gradzahlen gegen km/h-Grenzen geprüft (z. B. 350° -> rot).
   S3-Kanäle müssen bis dahin den abgeleiteten Wert bekommen oder `wind_direction` dort ausgenommen bleiben.
3. **Peilung je Segment**: `dp_to_row` kennt das Segment nicht; Peilung muss beim Zeilenbau durchgereicht werden
   (Briefing pro Segment-Tabelle). Zwei Zeilenpfade (`helpers.dp_to_row`, `trip_report._dp_to_row`).
4. **Ortsvergleich-Vererbung (F002 aus S1)**: `validate_ampel` ohne `kontext` in `_abo_ampel`/`loader.py`; ein
   Ortsvergleich, der `gegenwind` (Vorlage `radtour`) erbt, muss `None` liefern (kein Peilung) – passiert automatisch,
   weil `peilung_deg=None` -> `None`; per Test absichern.
5. **AC-8 Byte-Gleichheit**: Alt-Trip ohne `modus` -> `None` -> keine Färbung; Mail-Modus-Matrix muss unverändert bleiben.
6. **AC-10/F003**: Briefing Nutzer B ungefärbt an der Mail-Stelle per Mutation nachweisen.
7. **AC-15 Exposition**: F7 (`wind_exposition`) wirkt in Risk-Engine/`sms_trip`/`trip_report`; „höchste Stufe gewinnt“
   – prüfen, wo Gesamtstufe gebildet wird, nicht addieren.
8. **Renderer-Gate**: Mail-Inhalts-Commits brauchen frischen Modus-Matrix-Test + Validator gegen zugestellte
   Staging-Mail (Stalwart). LoC-Budget S2 ca. 200 (max 250).
9. Spec-Zeilenangaben (`narrow.py:623`, `helpers.py:741/758`) stimmen nur grob; Pfade liegen unter
   `src/output/renderers/...`.

## Analysis

### Type
Feature (Scheibe S2 von Epic #3222)

### Tech-Lead-Entscheidungen
1. **Merge-Fall (Default `format_mode=scale`, Kompass in der Wind-Zelle):** Variante (a). Die Wind-Zelle
   bekommt `max(Stufe Windstärke, Stufe wind_unerwuenscht_kmh)`, konsistent für Tönung, Ampelpunkt
   (`fmt_val`) und Zeilenpunkt (`_row_risk`). Gedeckt durch Spec Entscheidung 6 („Zelle in Ampelfarbe“)
   und Entscheidung 8/AC-15 („höchste Stufe gewinnt, nicht addieren“); keine PO-Rückfrage nötig.
   Verworfen: (b) separat getönter Kompass-Chip (ca. 45 LoC, Outlook-Risiko, Klartext-Parität offen),
   (c) Merge aufheben bei modus≠aus (ca. 50 LoC + 6 Aufrufer, Spaltenwechsel nur für Radtour).
   Roh-Modus (eigene WDir-Spalte): Zelle wird über den `wind_dir`-Zweig im `_FALLBACK` getönt, Wert =
   `_wind_unerwuenscht_kmh` statt Grad.
2. **Kein `AMPEL_LESER`-Ausbau in S2** (Abweichung von Spec-Wortlaut, technisch): Leck-Pfad
   `narrow._overview_line` (narrow.py:623/628) würde Grad gegen km/h-Grenzen prüfen; zusätzlich
   `tests/helpers/metrik_listen_scan.py:289-300` betroffen. Stattdessen `AMPEL_ABGELEITET = {"wind_direction"}`,
   `schwellen_aus_ampel` liest `AMPEL_LESER | AMPEL_ABGELEITET`, `hat_ampel` bleibt unverändert
   (Test: `hat_ampel(..., "wind_direction")` weiterhin False). S3 nimmt `hat_ampel` + Kurzkanäle dazu.
3. **Keine Modellfelder in S2** (`SegmentWeatherSummary`/`LocationResult` erst S3, Alarm braucht sie):
   Mail-Zellen sind Stundenzeilen; Wert stundenweise im Renderer über Seitenkanal
   `row["_wind_unerwuenscht_kmh"]`, nur gesetzt bei modus≠aus und bestimmbarem Wert (AC-5, AC-8 strukturell).
   Ortsvergleich live aus `loc.hourly_data` (Muster `_daily_summary`, compare_html.py:676); Engine hat keine Ampel.
4. **Gemeinsame Quelle:** neuer Zeilen-Helfer in `src/services/windrichtung.py` (ampel, dp, peilung) ->
   `wind_unerwuenscht_kmh(...)`; beide Zeilenpfade nutzen ihn. Peilung einmal je Segment via
   `segment_peilung_deg(seg_data.segment)` in `trip_report._extract_hourly_rows` (Aufrufe 189/337, Zeilenbau 547).
   `helpers.extract_hourly_rows` ist tot; `helpers.dp_to_row` nur von narrow.py:280 genutzt (bis S3 ohne Wert).
5. **AC-15:** Exposition F7 wirkt nicht auf die Mail (`exposed_sections` ungenutzt in email/__init__.py:62,
   `_determine_risk` ohne Aufrufer, nur SMS „GratWind“ sms_trip.py:146). Absicherung per Test: Zelle und
   Zeilenpunkt = max der Ampelstufen, keine Addition.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/ampel.py | MODIFY | `AMPEL_ABGELEITET`, `schwellen_aus_ampel` (~4 LoC) |
| src/services/windrichtung.py | MODIFY | Zeilenwert-Helfer (~12 LoC) |
| src/output/renderers/trip_report.py | MODIFY | Peilung je Segment, Ampel, `_dp_to_row`-Seitenkanal (~15 LoC) |
| src/output/renderers/email/helpers.py | MODIFY | Stufen-Helfer max(), `fmt_val` Ampelpunkt (~18 LoC) |
| src/output/renderers/email/html.py | MODIFY | Tönung Merge + `wind_dir`-Fallback, `_row_risk` (~18 LoC) |
| src/output/renderers/email/compare_html.py | MODIFY | Stunden-Merge-Zelle, CV2-Zeile `wind_direction_avg` mit `sev` (~28 LoC) |
| .claude/hooks/briefing_mail_validator.py | MODIFY | Tönungsprüfung Wind-Zelle Radtrip (AC-1/2/3/5) |
| .claude/hooks/email_spec_validator.py | MODIFY | Zelle Skiort gefärbt, Vergleichsort ungefärbt (AC-6) |
| tests/tdd/test_feat_3228_*.py | CREATE | Renderer-Tests je AC, AC-8 Byte-Gleichheit, geerbtes `gegenwind` im Ortsvergleich -> keine Färbung, Merge+Roh, Nutzer B ungefärbt (F003) |

### Scope Assessment
- Files: 6 src + 2 Validatoren + Tests
- Estimated LoC: ca. +95..110 Code (Budget 200, max 250)
- Risk Level: MEDIUM (Mail-Renderer, Renderer-Gate; Altbestand durch Seitenkanal-nur-wenn-gesetzt geschützt)

### Gates / bestehende Tests, die grün bleiben müssen
`tests/tdd/test_issue_811_mode_matrix.py` (frisch, sha-gebunden), `briefing_mail_validator.py` gegen zugestellte
Staging-Mail (`renderer_mail_gate.py`), `tests/test_briefing_modus_matrix_sprachen.py`,
`test_channel_metric_matrix.py`, `test_compare_katalog_schwellen.py`, i18n-Wächter.

### Bekannte Lücken (bewusst, S3)
- Nachtblöcke (`aggregate_night_block`, trip_report:603) haben kein Segment -> im Modus gegenwind kein Wert;
  Modus sektoren wäre möglich, in S2 nicht umgesetzt.
- Spec-Dateiliste nennt `narrow.py` und `models.py` in S2 -> wandern nach S3 (wirken in S2 nicht auf die Mail).

### Open Questions
- keine (Merge-Fall durch Spec Entscheidung 6/8 gedeckt)

## RED-Phase: Schnittstellen-Annahmen der Tests (für /50-implement)
Tests: `tests/tdd/test_feat_3228_windrichtung_mail.py` (Briefing), `tests/tdd/test_feat_3228_windrichtung_mail_compare.py` (Ortsvergleich). 10 rot, 15 grün (Regressionswächter).
1. `app.ampel.AMPEL_ABGELEITET` enthält `"wind_direction"`; `schwellen_aus_ampel(radtour, "wind_direction") == {yellow:10, orange:20, red:30}`; `hat_ampel(..., "wind_direction")` bleibt False.
2. `TripReportFormatter()._extract_hourly_rows(seg_data, dc)` behält 2-Argument-Signatur, Ampel aus `resolve_ampel(dc)`; setzt `row["_wind_unerwuenscht_kmh"]` nur bei modus≠aus und bestimmbarem Wert, sonst fehlt der Schlüssel. Muss auch mit dem per `dataclasses.replace` kollabierten `dc` in `format_email` funktionieren.
3. Merge-Modus: Zelltönung, Ampelpunkt (`fmt_val`) und Zeilenpunkt (`_row_risk`) = max(Stufe Windstärke, Stufe Gegenwind). Tests setzen gust=10.
4. Roh-Modus: WDir-Zelle (`data-label="WDir"`) nach `_wind_unerwuenscht_kmh` getönt, nie nach Grad.
5. Vergleich: Übersichtszeile „Windrichtung" (`wind_direction_avg`) bekommt Stufe aus Sektorwert live aus `hourly_data`; verschmolzene Stunden-Windzelle = max beider Stufen; geerbtes `gegenwind` → kein Wert.
6. HTML-Erkennung: Zelltönung `background:<tone_css(level)[0]>` im öffnenden `<td data-label="Wind">`; Punkt `border-radius:50%;background:<_AMPEL_DOT_COLORS[level][0]>`; Vergleich-Übersicht `background:transparent` = ungefärbt.
