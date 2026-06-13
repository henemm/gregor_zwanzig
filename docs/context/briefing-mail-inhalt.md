# Kontext: briefing-mail-inhalt

Drei zusammengehörige Änderungen am Inhalt der Trip-Briefing-E-Mail. Ein Workflow, ein Deploy.

## AC-1 — Mobil-Tabelle erscheint zuverlässig (Bug, im echten Client bestätigt)

Stundentabellen liegen doppelt vor: Desktop (`class="section desktop-only"`) und Mobil (`class="mobile-compact"`). Umschaltung NUR über `@media (max-width:600px)` mit `!important`. Gmail-Typ-Clients wenden den @media-Block nicht an → Desktop unterdrückt, Mobil nie eingeblendet → leere Tabelle.

**Fix:** Mobile-First. Mobil-Variante standardmäßig sichtbar (Inline `display:block`), Desktop standardmäßig versteckt, Desktop nur via `@media (min-width:601px)` einblenden.

- CSS-Block: `src/output/renderers/email/html.py:659-668`
- Mobil-Div inline display:none: `html.py:338` (und ggf. 365 Nacht-Block)
- Desktop-Tabellen: `html.py:317, 331, 358`
- Mobil-Renderer `_render_mobile_compact_rows` (`html.py:114-192`) bleibt unverändert.
- Constraint #636 AC-5: Desktop-Tabelle (`_render_html_table`) byte-identisch.
- **Test-Update Pflicht:** `tests/tdd/test_bug305_mobile_email.py` AC-9/AC-10 prüfen Desktop-First-Logik → nach Mobile-First invertiert korrekt, müssen im selben Schritt angepasst werden.

## AC-2 — Wetter-Kürzel raus aus dem Betreff (Bug)

Betreff trägt kryptische SMS-Tokens „D15 W19 G36". Nutzer (kein Techniker) versteht sie nicht.

**Fix:** D/W/G (und TH:/HR:) gar nicht erst bauen. MainRisk-Wort (Gewitter/Sturm), Etappenname, ReportType BLEIBEN.

- Token-Bau: `src/formatters/trip_report.py:486-496` (entfernen)
- Einziger Aufrufer: `trip_report.py:160-167`
- `src/output/subject.py:102-116` behandelt leere Token-Liste korrekt (kein trailing „—").
- **Spec-Konflikt:** `docs/specs/modules/output_subject_filter.md` v1.1 (A4/AC-6) schreibt D/W/G vor → Spec mit anpassen (Kürzel als abgelöst markieren).
- **Golden-Update:** `tests/golden/test_subject_golden.py` enthält D/W/G in erwarteten Strings → aktualisieren.

## AC-3 — Vortags-Vergleich: metrik-getrieben, relevanz-gefiltert (Erweiterung)

Heute nutzt `summarize_day_comparison` (`src/services/day_comparison.py:62-112`) nur temp_max + precip_sum. `compare()` berechnet 6 Deltas, summarize wirft Wind/Böen/Gewitter weg.

**Soll (recherchiert: Apple-Wetter-Apps + Reiter SUMTIME content-selection):**
1. Metrik-getrieben — nur die für den Trip ausgewählten Metriken (`display_config.metrics`, enabled).
2. Relevanz-Filter — Metrik nur in den Satz, wenn Delta die Spürbarkeitsschwelle überschreitet. Sonst Schweigen. Gewitter nur bei echter Level-Änderung.
3. Richtung + Größenordnung; gefühlte Temperatur (wind_chill) bevorzugt vor Lufttemperatur, wenn beide ausgewählt.
4. Antwort-zuerst, ein Satz/kompakte Aufzählung, **max. 4–6** nach |delta|/Relevanz sortiert. 0 spürbare Änderungen → „heute ähnliches Wetter wie gestern".

**Architektur (Plan-Agent):**
- `summarize_day_comparison(comparison, *, selected_metrics=None)` — Fallback auf alte temp/precip-Logik wenn None → bestehende Aufrufer/Tests grün.
- `DayComparisonEntry` additiv erweitern (neue Felder default MISSING): wind_chill_min, cloud_avg, uv_index_max, sunshine_sum, pop_max, visibility_min, dewpoint_avg, freezing_level, humidity_avg, pressure_avg.
- `compare()` befüllt neue Felder aus `SegmentWeatherSummary` (Felder existieren bereits, models.py:331-376).
- `_missing_entry()` um neue Felder erweitern (sonst AttributeError).
- Interne Mapping-Konstante `metric_id → DayComparisonEntry-Attribut` (summary_fields zeigen auf SegmentWeatherSummary-Namen, nicht auf Entry-Attribute).
- Schwellen: `MetricDefinition.default_change_threshold` aus `src/app/metric_catalog.py` (temp/wind_chill 5°C, wind/gust 20km/h, precip 10mm, cloud 30%, uv 3.0, pop 20%, …). Ggf. für Temperatur feiner kalibrieren (Apps nutzen ~3°C).
- Renderer: `html.py:572`, `plain.py:130` → `selected_metrics=dc.metrics` durchreichen (display_config liegt vor).

**Backward-Compat-Schutz:** #748-Tests (6 Felder), #750-Integration (`"Vortag: heute" in html`), #752 Telegram `_tg_vortag_line` (greift nur 6 feste Felder) bleiben grün.

## Scope
5 Python-Dateien + 1 Spec. ~145 LoC netto. Reihenfolge: AC-2 → AC-1 → AC-3.
