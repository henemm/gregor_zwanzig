---
entity_id: briefing_mail_inhalt
type: module
created: 2026-06-13
updated: 2026-06-13
status: live
version: "1.1"
tags: [email, renderer, briefing, mobile, subject, vortag-vergleich, day-comparison]
---

# Briefing-Mail-Inhalt: Mobile-First, Betreff bereinigt, Vortag metrik-getrieben

## Approval

- [x] Approved

## Purpose

Drei zusammengehörige Korrekturen am Inhalt der Trip-Briefing-E-Mail in einem einzigen
Workflow und Deploy. Erstens: Die Stundentabellen erscheinen in Gmail-artigen Clients,
die `@media`-Queries ignorieren, derzeit leer — ein Mobile-First-Ansatz (Mobil standardmäßig
sichtbar, Desktop per `@media` eingeblendet) behebt dies. Zweitens: Der Betreff enthält
kryptische SMS-Kürzel (`D15 W19 G36`), die Nicht-Techniker nicht lesen können — die
Token-Erzeugung wird entfernt, der lesbare Betreff bleibt. Drittens: Die
Vortags-Einordnungszeile nennt heute nur Temperatur und Niederschlag, ignoriert alle
anderen ausgewählten Metriken und filtert nicht nach spürbarer Änderung — durch
metrik-getriebenenes, relevanzgefiltertes Summarizing (inspiriert von Apple-Wetter-App-Design
und Reiter et al. SUMTIME content-selection) wird die Zeile inhaltlich relevant.

## Source

- **File:** `src/output/renderers/email/html.py` (CSS-Block, Inline-Display-Attribute)
- **File:** `src/formatters/trip_report.py` (D/W/G-Token-Bau)
- **File:** `src/services/day_comparison.py` (`DayComparisonEntry`, `compare()`, `summarize_day_comparison()`)
- **File:** `src/output/renderers/email/html.py:572` und `plain.py:130` (selected_metrics-Durchreichung)
- **File:** `docs/specs/modules/output_subject_filter.md` (D/W/G-Whitelist als abgelöst markieren)
- **File:** `tests/tdd/test_bug305_mobile_email.py` (AC-9/AC-10 auf Mobile-First invertieren)
- **File:** `tests/golden/test_subject_golden.py` (D/W/G-Erwartungen aktualisieren)

## Estimated Scope

- **LoC:** ~145 netto
- **Files:** 7 (5 Python + 1 Spec + 1 Golden-Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/models.py` (`SegmentWeatherSummary`) | module | Quell-Felder für neue `DayComparisonEntry`-Attribute |
| `src/app/metric_catalog.py` (`MetricDefinition.default_change_threshold`) | module | Spürbarkeitsschwellen pro Metrik für Relevanz-Filter |
| `src/services/day_comparison.py` (`DayComparisonEntry`, `compare()`) | module | Wird um neue Felder erweitert (AC-3) |
| `src/output/subject.py` | module | Behandelt leere Token-Liste korrekt — bleibt unverändert |
| `#636` (`_render_html_table`, `_render_mobile_compact_rows`) | feature | Desktop-Tabelle muss byte-identisch bleiben (AC-1-Constraint) |
| `#748` / `#750` / `#752` | feature | Backward-Compat-Schutz: bestehende Vortag-Tests müssen grün bleiben |
| `tests/tdd/test_bug305_mobile_email.py` | test | AC-9/AC-10 prüfen aktuell Desktop-First — werden im selben Schritt invertiert |

## Implementation Details

```
AC-2 zuerst (kleinste Änderung, kein HTML-Risiko):
  src/formatters/trip_report.py:486-496 — D/W/G-Token-Bau entfernen.
  Einziger Aufrufer ist trip_report.py:160-167 (übergibt tokens=[]).
  subject.py:102-116 behandelt leere Liste bereits korrekt (kein trailing "—").
  docs/specs/modules/output_subject_filter.md — D/W/G-Whitelist-Bullet als abgelöst markieren.
  tests/golden/test_subject_golden.py — Erwartungs-Strings ohne D/W/G aktualisieren.

AC-1 (Mobile-First-Umstellung):
  html.py:659-668 (CSS-Block):
    .desktop-only { display: none; }
    @media (min-width: 601px) { .desktop-only { display: table !important; }
                                 .mobile-compact { display: none !important; } }
  html.py:317, 331, 358 (Desktop-Table-Tags): keine Inline-Style-Änderung nötig,
    CSS-Klasse .desktop-only steuert Sichtbarkeit.
  html.py:338 (und ggf. 365 Nacht-Block, Mobil-Div):
    Inline style="display:block" setzen (Mobile-First-Default sichtbar).
  _render_mobile_compact_rows (html.py:114-192): unverändert.
  _render_html_table: byte-identisch (Constraint #636 AC-5).
  tests/tdd/test_bug305_mobile_email.py AC-9/AC-10: Assertions auf Mobile-First invertieren
    (Mobil sichtbar ohne @media, Desktop versteckt ohne @media).

AC-3 (Vortag metrik-getrieben):
  src/services/day_comparison.py — DayComparisonEntry additiv erweitern:
    Neue Felder (default MISSING/None): wind_chill_min, cloud_avg, uv_index_max,
    sunshine_sum, pop_max, visibility_min, dewpoint_avg, freezing_level,
    humidity_avg, pressure_avg.
  compare() — neue Felder aus SegmentWeatherSummary befüllen
    (Felder existieren bereits in models.py:331-376).
  _missing_entry() — neue Felder mit None/MISSING initialisieren (sonst AttributeError).
  Interne Mapping-Konstante metric_id → DayComparisonEntry-Attribut hinzufügen.
  summarize_day_comparison(comparison, *, selected_metrics=None):
    selected_metrics=None → bisherige temp/precip-Logik (Backward-Compat).
    selected_metrics gesetzt → nur enabled Metriken aus der Liste.
    Relevanz-Filter: MetricDefinition.default_change_threshold pro Metrik.
      Schwellen (Richtwerte, aus metric_catalog.py kalibrieren):
        temp/wind_chill ≥ 3–5 °C, wind/gust ≥ 20 km/h, precip ≥ 10 mm,
        cloud ≥ 30 %, uv ≥ 3.0, pop ≥ 20 %.
    Richtung + Größenordnung im Satz nennen.
    wind_chill bevorzugt vor temp_max wenn beide ausgewählt.
    Gewitter nur bei echter Level-Änderung (ordinal-Delta ≠ 0).
    max. 4–6 Änderungen nach |delta| absteigend sortiert.
    0 spürbare Änderungen → "heute ähnliches Wetter wie gestern".
  html.py:572 → selected_metrics=dc.metrics durchreichen.
  plain.py:130 → selected_metrics=dc.metrics durchreichen.
```

## Expected Behavior

- **Input (AC-1):** gerendertes HTML einer Briefing-Mail mit Desktop- und Mobil-Stundentabellen
- **Output (AC-1):** `.mobile-compact` hat Inline `display:block`; `.desktop-only` ist per CSS-Klasse standardmäßig `none`; Desktop wird NUR via `@media (min-width:601px)` eingeblendet
- **Input (AC-2):** Briefing-Mail-Rendering mit befülltem `SegmentWeatherSummary`
- **Output (AC-2):** Betreff enthält keine D/W/G/TH:/HR:-Token; Etappenname, ReportType-DE und ggf. MainRisk-Wort bleiben
- **Input (AC-3):** `summarize_day_comparison(comparison, selected_metrics=["wind","precip","thunder"])`
- **Output (AC-3):** Einzeiliges Deutsch-Summary nur für enabled Metriken mit Delta über Spürbarkeitsschwelle, max. 4–6 Punkte sortiert nach |delta|; bei 0 Treffern: „heute ähnliches Wetter wie gestern"
- **Side effects:** `output_subject_filter.md` wird aktualisiert; Golden-Tests werden angepasst; bestehende `#748/#750/#752`-Tests bleiben grün

## Acceptance Criteria

**AC-1:** Given eine Briefing-Mail mit Stundentabellen, die für Desktop (`class="desktop-only"`) und Mobil (`class="mobile-compact"`) doppelt vorliegen / When der HTML-Mail-Body ohne Anwendung von `@media`-Queries betrachtet wird (z.B. Gmail-Web-Client) / Then ist die Mobil-Variante sichtbar (Inline `display:block` oder kein Inline-Verstecken), während die Desktop-Variante standardmäßig versteckt ist (CSS-Klasse `.desktop-only` hat `display:none` ohne `@media`); `_render_html_table` und `_render_mobile_compact_rows` bleiben byte-identisch.
  - Test: `build_mime_message()` auf einem echten Trip rendern, HTML-Part parsen; `re.search(r'class="mobile-compact"[^>]*style="[^"]*display\s*:\s*none', html)` darf NICHT matchen; Desktop-CSS-Block ohne `@media`-Wrapper enthält `display:none` für `.desktop-only`; mit `@media (min-width:601px)` wird `.desktop-only` wieder eingeblendet.

**AC-2:** Given ein Trip-Briefing wird als E-Mail versendet / When der Betreff erzeugt wird / Then enthält der Betreff weder `D\d+`, `W\d+`, `G\d+` noch `TH:` oder `HR:` als Substring; Etappenname, Shortcode/Trip-Name und ReportType-DE (Morgen/Abend) bleiben unverändert erhalten.
  - Test: `tests/golden/test_subject_golden.py` mit aktualisierten Erwartungs-Strings; zusätzlich `re.search(r'\b[DWG]\d+\b|TH:|HR:', subject)` darf None zurückgeben für jede Golden-Fixture.

**AC-3:** Given ein Trip mit `display_config.metrics = ["wind", "precip", "thunder", "temperature"]` und einem Vortags-Snapshot, in dem Wind um 25 km/h zunahm und die Temperatur sich um 1 °C änderte / When `summarize_day_comparison(comparison, selected_metrics=["wind","precip","thunder","temperature"])` aufgerufen wird / Then nennt der zurückgegebene Text „Wind" (Delta ≥ Spürbarkeitsschwelle), nennt aber NICHT die Temperatur (Delta < Schwelle), und enthält NICHT „precip" oder „thunder" (keine Änderung); bei 0 spürbaren Änderungen lautet der Text „heute ähnliches Wetter wie gestern".
  - Test: `DayComparisonEntry` mit wind_max.delta=+25, temp_max.delta=+1, precip_sum.delta=0, thunder.delta=0; `summarize_day_comparison(..., selected_metrics=["wind","precip","thunder","temperature"])` → assert "Wind" in result, assert "Temperatur" not in result; separater Test mit allen Deltas unter Schwellen → assert result == "heute ähnliches Wetter wie gestern".

**AC-4:** Given `summarize_day_comparison(comparison, selected_metrics=None)` (Fallback) / When aufgerufen / Then verhält sich die Funktion identisch zum bisherigen Verhalten (temp + precip, ohne Spürbarkeitsschwellen-Filter); die bestehenden Tests aus `#748`, `#750` und `#752` bleiben grün ohne Änderung.
  - Test: alle `test_day_comparison_service.py`-Tests und `#750/#752`-Integrationstests laufen unverändert durch; `summarize_day_comparison(comparison)` gibt denselben String wie bisher zurück.

**AC-5:** Given `wind_chill` und `temperature` beide in `selected_metrics` und beide über der Spürbarkeitsschwelle / When `summarize_day_comparison()` aufgerufen wird / Then erscheint `wind_chill` (gefühlte Temperatur) im Summary-Text und `temperature` (Lufttemperatur) wird ausgelassen (kein Duplikat).
  - Test: `DayComparisonEntry` mit `wind_chill_min.delta=-8` und `temp_max.delta=-6`; `summarize_day_comparison(..., selected_metrics=["temperature","wind_chill"])` → assert "gefühlte" oder "wind_chill"-Label in result, assert keine doppelte Temperatur-Nennung.

**AC-6:** Given `tests/tdd/test_bug305_mobile_email.py` AC-9 und AC-10 / When die Mobile-First-Umstellung deployed ist / Then prüfen die angepassten Tests, dass die Mobil-Variante OHNE `@media`-Query sichtbar ist (nicht versteckt), und die Desktop-Variante OHNE `@media`-Query versteckt ist; die Tests sind grün auf dem neuen Stand und würden rot gehen, wenn die Desktop-First-Logik wieder eingeführt wird.
  - Test: Die aktualisierten AC-9/AC-10-Assertions in `test_bug305_mobile_email.py` laufen grün; stichprobenartige Mutation (Inline `display:none` auf Mobil-Div setzen) lässt AC-9 rot werden.

## Known Limitations

- Die AC-1-Umstellung schützt vor `@media`-ignorierenden Clients (Gmail Web, viele Corporate-Clients). Native Mail-Apps (Apple Mail, Thunderbird), die `@media` respektieren, zeigen weiterhin die korrekte Ansicht — das Verhalten ändert sich dort nicht.
- AC-3 nutzt `MetricDefinition.default_change_threshold` als Spürbarkeitsschwelle. Metriken ohne eigene Schwelle im Katalog werden mit dem temp-Fallback (5 °C) behandelt; eine feinere Kalibrierung pro Metrik kann separat erfolgen.
- `summarize_day_comparison(selected_metrics=None)` bleibt Backward-Compat — alle Aufrufer ohne `display_config` (z.B. Tests aus #748) erhalten weiterhin das bisherige temp/precip-Summary.
- Betreff-Spec `output_subject_filter.md` wird in-place angepasst (D/W/G als abgelöst); die Spec-Version wird auf v1.2 hochgezogen.

## Test Plan

1. **AC-2 — Golden-Test (kein Mock, Render-Test):**
   `tests/golden/test_subject_golden.py` — alle Fixture-Subjekte neu rendern, D/W/G-Regex auf jeden zurückgegebenen Betreff prüfen. Kein Mock, kein `patch()`.

2. **AC-1 — HTML-Render-Test (kein Mock):**
   `build_mime_message()` mit einem echten `SegmentWeatherSummary`-Fixture aufrufen (analog `test_bug305_mobile_email.py`). HTML-Part extrahieren, per String-/Regex-Suche CSS-Regeln und Inline-Styles prüfen. Mutation-Probe: Inline `display:block` vom Mobil-Div entfernen → AC-9-Test wird rot.

3. **AC-3, AC-4, AC-5 — Unit-Tests ohne Mock:**
   `DayComparisonEntry` direkt mit kontrollierten Delta-Werten instantiieren (keine Netz-Calls, kein `patch()`). `summarize_day_comparison()` aufrufen, Rückgabe-String assertieren. Deckt auch Backward-Compat (AC-4) und wind_chill-Präferenz (AC-5).

4. **AC-6 — Test-Update-Verifikation:**
   Nach Invertierung von AC-9/AC-10 in `test_bug305_mobile_email.py`: `uv run pytest tests/tdd/test_bug305_mobile_email.py` muss vollständig grün sein.

5. **MIME-Validierung (AC-1, Integration):**
   `briefing_mail_validator.py` auf einer lokal gerenderten `build_mime_message()`-Mail ausführen — Exit 0 beweist, dass der Mobile-First-Umbau keine Strukturregression eingebracht hat.

6. **Regressions-Schutz:**
   `uv run pytest tests/tdd/test_day_comparison_service.py tests/tdd/test_issue_790_briefing_simplify.py` — alle bestehenden Vortag-Tests (#748/#750/#752) müssen ohne Änderung grün bleiben.

## Changelog

- 2026-06-13: v1.0 → v1.1 **LIVE DEPLOYED** — AC-1 (Mobile-First Stundentabelle), AC-2 (D/W/G aus Betreff), AC-3 (Vortag metrik-getrieben gefiltert) alle implementiert und getestet. Backend +98 LoC (html.py +24, plain.py +6, day_comparison.py +68). CSS-Block Mobil-Standard sichtbar (`display:block`), Desktop CSS-Klasse `.desktop-only` standardmäßig `none` (kein `@media` nötig). Betreff nun lesbar ohne Kürzel: `[GZ#GRANK] Tag 3: Valldemossa → Sóller — Morgen — Gewitter`. Vortag-Zeile nutzt `selected_metrics` + `MetricDefinition.default_change_threshold` (wind ≥20km/h, temp ≥3°C, etc.), wind_chill bevorzugt vor temp, max 4–6 Änderungen, bei 0 Treffern "heute ähnliches Wetter wie gestern". Briefing-Mail-Validator Exit 0. Test-Befunde #795-Neben (#796 Gewitter-Logik, #797 Orts-Vergleich-Token-Filter).
- 2026-06-13: v1.0 — Initial spec, drei ACs aus `docs/context/briefing-mail-inhalt.md`. Issue offen.
