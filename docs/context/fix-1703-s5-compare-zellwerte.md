# Context: Epic #1703 Scheibe 5 — Compare-Zellwert-Vollständigkeit

## Request Summary

Epic #1703, Scheibe 5: Über die reine Zeilen-EXISTENZ hinaus in
`tests/tdd/test_channel_metric_matrix.py` (Achse `AC-S5-n`, Fortsetzung S1-S4)
prüfen, dass jede Zelle der Compare-Übersichtstabelle (HTML **und** Klartext)
einen plausiblen Wert trägt, UND dass HTML und Klartext derselben Mail für
dieselbe Wetterlage dieselbe Zahl zeigen. Ziel laut
`docs/reference/metric_output_matrix.md` Fläche 4 / Abschnitt 6 Scheibe 5.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py:305-371` (`CV2_METRICS`) | Soll-Menge der Scheibe: 26 Einträge = `warn` + **25 Metrik-Zeilen**. Zellwert kommt aus `_metric_value(loc, m["key"], summary)` (:644), formatiert per `m["fmt"]` (Sonderfälle: `_fmt_thunder`, `_fmt_precip_type`, `_fmt_visibility_overview`) oder generisch `_fmt_metric(value, m.get("decimals"), m.get("unit"))` (:703-709, Default `decimals=0`, `None` → `"—"` U+2014 Em-Dash). |
| `src/output/renderers/comparison.py:70-120` (`_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS`) | Klartext-Pendant. **Wert-Quelle bereits geteilt**: importiert `_metric_value` direkt aus `compare_html.py` (Zeile 30-36) — kein zweiter Berechnungsweg. Formatierung dagegen **nicht** einheitlich: teils dieselben geteilten Formatter (`_fmt_thunder`, `_fmt_precip_type`, `_fmt_visibility_overview`), teils eigene Lambdas mit `:.0f`/`:.1f`, teils der katalog-getriebene `format_value(metric_id, v, style="plain")` — drei parallele Formatierungswege für denselben Zahlenwert. |
| `tests/tdd/test_channel_metric_matrix.py` (3157 Zeilen; endet aktuell bei `test_ac_s4_14_telegram_narrow_confidence_absent` :3150) | Bestehender Matrix-Wächter (Option C, #1514). `AC-S5-n` wäre die fünfte Achse. |
| `tests/tdd/test_channel_metric_matrix.py:2703-2860` (AC-S2-8, Scheibe 2) | **Direktes Vorbild-Muster**: `_s2_erwartete_tageswerte()` (:2703) rechnet Soll-Werte unabhängig aus rohen `ForecastDataPoint`-Stundenwerten (max/min/sum), `_s2_erwartungen_sind_unterscheidbar()` (:2737) ist eine Vakuum-Gegenprobe (verglichene Felder müssen selbst unterscheidbare Werte tragen, sonst wäre eine Vertauschung unsichtbar), `test_ac_s2_8_ausblick_zelle_zeigt_den_gerechneten_wert` (:2808) prüft die Soll-Zahl an der ECHTEN Mail (HTML-Spaltenindex + `_s2_klartext_ausblick()`-Parser :2260). |
| `tests/unit/test_compare_mail_metric_link_completeness.py` | Bestehender Row-Existenz-Wächter (`test_every_overview_row_links_to_the_central_catalog`) — prüft nur, dass jede `CV2_METRICS`-Zeile ein auflösbares `metric_id`+`aggregation` trägt, **keine** Wertprüfung. Genau die Lücke, die Scheibe 5 schließt. |
| `src/services/weather_metrics.py:927-1015` (`_compute_wind_direction`, `_compute_cloud_low/mid/high`, `_compute_freezing_level`, `_compute_snowfall_limit`) | Rohberechnung der "Klasse A/B"-Felder — alle bereits mit `round()` auf `int` normalisiert, bevor sie ins `LocationResult` bzw. die Live-Aggregation wandern. |

## Existing Patterns

- **Achsen-Erweiterung statt neues Register** (Option C): `AC-S5-*`-Tests in
  derselben Datei, mit Docstring-Block der Scope/Nicht-Scope festhält (Vorbild
  Kopf von S1-S4).
- **Soll-Menge GERECHNET, nie getippt**: für Scheibe 5 ist die Soll-Menge
  `CV2_METRICS` selbst (25 Metrik-Zeilen + `warn`) — **nicht**
  `get_compare_metric_catalog()` (anderes Key-Vokabular, primär Scheibe-2-Scope
  für die Ausblick-Tabelle).
- **"Rechnen statt tippen" sichert Vollständigkeit, nie Zuordnung** (S2-Lehre,
  F001 HIGH): eine Vertauschung zweier Felder blieb in S2 trotz gerechneter
  Soll-Menge grün, weil kein Test die *Zahlenwerte* prüfte. AC-S2-8 schließt
  das mit unabhängig aus Rohdaten gerechneten Erwartungswerten — direktes
  Vorbild für Scheibe 5.
- **Prüfort = Wirkort**: gegen die echte Mail (`render_compare_email()`, HTML
  und Klartext in einem Aufruf), nicht gegen isolierte Renderer-Direktaufrufe.

## Dependencies

- **Upstream:** `_metric_value()` (compare_html.py:644) als gemeinsame
  Wert-Quelle; `_DAILY_AGGREGATE_FIELD` (:608) entscheidet Engine-Feld vs.
  Live-Ableitung (`_daily_summary()` → `summarize_points()`); Roh-Berechnung
  in `weather_metrics.py` (`_compute_*`-Methoden, Zeilen 793-1015).
- **Downstream:** `render_compare_email()` (Versandpfad) ruft beide Renderer
  für dieselbe `ComparisonResult` auf.

## Existing Specs

- `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md`,
  `fix_1703_s2_ausblick_matrix.md`, `fix_1703_s3_selectable_metrics.md`,
  `fix_1703_s4_kompaktform_matrix.md` — Vorbild-Format der Vorscheiben.
  AC-S2-8 in S2 ist das direkte technische Vorbild.
- `docs/specs/modules/issue_1110_compare_mail_v2.md` — Klartext-Renderer-Vertrag.
- `docs/reference/metric_output_matrix.md` Abschnitt 4.2 (Fläche 4), Abschnitt 6
  (Scheibe-5-Text).

## Risks & Considerations

- **Kernrisiko laut Matrix-Dokument:** Doppel-Quellen-Historie #1356 (HTML und
  Klartext liefen bei der **Reihenfolge** einmal auseinander, weil zwei
  unabhängige Listen dieselbe Semantik doppelt trugen — inzwischen mit
  `_ordered_rows()`/#1359 gefixt). Dieselbe Zwei-Listen-Architektur (`CV2_METRICS`
  vs. `_PLAIN_ROWS`) besteht strukturell weiter — jetzt für **Werte/Formatierung**
  statt Reihenfolge.
- **Wert-Quelle ist bereits geteilt** (`_metric_value` importiert, kein zweiter
  Berechnungsweg) — geringeres Risiko als ursprünglich vom Matrix-Dokument
  suggeriert. Das eigentliche Risiko liegt in der **Formatierung**, nicht im Wert.
- **Verifizierter, konkreter Fund (kein Verdacht):** Fehlender Wert wird
  unterschiedlich dargestellt — HTML zeigt `—` (U+2014, Em-Dash, `_fmt_metric`
  Zeile 705), Klartext zeigt `-` (U+002D, ASCII-Hyphen, `comparison.py:249`)
  für **dieselbe** fehlende Zelle. Muss in der Spec entschieden werden:
  Charakterisierung (Ist-Zustand bewachen) oder Fix (Angleichung)?
- **Widerlegter Verdacht aus der Erstrecherche:** `wind_direction_avg` und
  `cloud_low/mid/high_avg` formatieren in `comparison.py` ohne `:.0f`-Rundung
  (`f"{v}°"`/`f"{v}%"`) — sah zunächst wie ein Rundungs-Divergenzrisiko aus.
  Nachgemessen in `weather_metrics.py:946-1015`: alle vier Werte werden an der
  Berechnungsquelle bereits mit `round()` auf `int` normalisiert, bevor sie das
  `LocationResult` erreichen — kein tatsächliches Divergenzrisiko unter
  heutigen Typannahmen. **Lehre für die Spec:** nicht bei der Formatierungs-
  Zeile stehenbleiben, sondern bis zur Berechnungsquelle zurückverfolgen.
- **Drei parallele Formatierungswege in `_PLAIN_ROWS`**: (a) geteilte Formatter
  (`_fmt_thunder`, `_fmt_precip_type`, `_fmt_visibility_overview` — importiert,
  kein Risiko), (b) eigene Lambdas mit expliziter Dezimalstellen-Angabe (meist
  deckungsgleich mit `CV2_METRICS`-`decimals`, aber nicht automatisch
  gehalten — reine Konvention, kein Wächter), (c) katalog-getriebener
  `format_value(metric_id, v, style="plain")` (temp_max/min, wind_max,
  gust_max, wind_chill_min/max, cloud_avg, snow_depth_cm, sunny_hours,
  dewpoint_avg) — eine **dritte**, unabhängige Formatierungsquelle neben
  `_fmt_metric`+`decimals`-Dict. Ob `format_value(..., style="plain")` und
  `_fmt_metric(..., decimals=CV2_METRICS[...]["decimals"])` für dieselbe Größe
  immer dieselbe Nachkommastellenzahl liefern, ist **ungeklärt** — zu klären in
  der Analyse/Spec, ggf. per Sub-Agent-Nachmessung je Feld.
- **`warn`-Zeile** (amtliche Warnungen) hat keinen numerischen "Zellwert" im
  engeren Sinn — vermutlich analog Scheibe 2 aus der 25er-Soll-Menge
  ausgenommen; zu bestätigen in der Spec.
- **Risiko laut Matrix-Dokument: mittel. Größe: mittel.**

## Analysis

### Type
Feature (Erweiterung des bestehenden Matrix-Wächters um eine neue Achse,
primär Charakterisierung — ggf. mit punktuellem Fix, falls der
Fehlzeichen-Fund oder eine Formatierungs-Divergenz als echter Bug eingestuft
wird).

### Bestätigter Kernbefund (eigene Nachrecherche, mit Code-Zeilen verifiziert)

1. **Wert-Quelle bereits geteilt, Formatierung nicht.** `comparison.py`
   importiert `_metric_value` direkt aus `compare_html.py` — keine zweite
   Wert-Berechnung. Divergenzrisiko sitzt ausschließlich in der Formatierung,
   die auf drei unterschiedliche Arten passiert (s. Risks).
2. **Ein realer, unabhängig verifizierter Darstellungs-Unterschied:** fehlender
   Wert → HTML `—` (U+2014) vs. Klartext `-` (U+002D). Bytegenau nachgemessen
   (`od -c`), kein Interpretationsfehler.
3. **Ein zunächst vermuteter Rundungs-Unterschied (`wind_direction_avg`,
   `cloud_*_avg`) ist bei Nachmessung KEIN echtes Risiko** — die
   Berechnungsquelle rundet bereits auf `int`. Dieser Punkt ist explizit als
   widerlegt dokumentiert, um eine falsche Spec-Prämisse zu vermeiden (Lehre
   aus S2 F001: falsche Prämissen in ACs sind der teuerste Fehlertyp).
4. **Soll-Menge = `CV2_METRICS`, 25 Metrik-Zeilen + `warn`** — bytegenau
   ausgezählt, deckt sich mit der Fläche-2-Aussage aus S2 ("25 Paare"), ist
   aber eine **andere** Liste (Compare-Übersicht statt Ausblick-Tabelle).

### Affected Files (voraussichtlich)
| File | Change Type | Description |
|------|-------------|--------------|
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | Neue Achse `AC-S5-1..n`, Vorbild AC-S2-8: unabhängig aus Rohdaten gerechnete Erwartungswerte, gegen echte HTML-Zelle UND echte Klartext-Zeile geprüft, plus Vakuum-Gegenprobe. |
| `docs/specs/modules/fix_1703_s5_compare_zellwerte.md` | CREATE | Spec analog S1-S4. |
| `docs/reference/metric_output_matrix.md` | MODIFY | Fläche 4 nach Abschluss auf neuen Wächter umtragen (DoD). |
| `src/output/renderers/comparison.py` bzw. `compare_html.py` | MÖGLICH, unklar | Nur falls der Em-Dash/Hyphen-Fund oder eine gefundene Formatierungs-Divergenz als Fix statt Charakterisierung eingestuft wird — **PO-Entscheidung nötig, s. Open Questions**. |

### Scope Assessment
- Files: 2-4 (Testdatei, Spec, Matrix-Dokument-Update, ggf. 1 Produktivdatei
  bei Fix-Entscheidung)
- Estimated LoC: Testcode ~150-300 Zeilen (Vorbild AC-S2-8 war für 5 Felder
  bereits ~150 Zeilen inkl. Helfer; 25 Metrik-Zeilen sind größer, aber
  vermutlich nicht linear — viele Felder teilen sich Formatierungslogik und
  können gruppiert parametrisiert werden statt einzeln ausgeschrieben)
- Risk Level: MEDIUM — die Formatierungs-Divergenz ist ein echtes,
  unstrukturiertes Feld (drei parallele Wege), nicht trivial durchzuzählen wie
  bei S1/S3 (Soll-Menge aus einer einzelnen Quelle).

### Technical Approach (Empfehlung)

**Primär Charakterisierung, mit einer offenen Fix-Frage.** Analog S1-S4: die
Wert-Quelle ist bereits korrekt geteilt (kein Produktivcode-Fehler dort). Die
Formatierungs-Divergenzen sind ein eigener Befund — ob sie als akzeptierter
Ist-Zustand bewacht oder als Fix behandelt werden, ist eine PO-Entscheidung
(insbesondere der Em-Dash/Hyphen-Fund, der nutzersichtbar in jeder Mail mit
fehlenden Werten auftritt).

Testaufbau nach AC-S2-8-Muster:
1. Erwartungswerte unabhängig aus `hourly_data`/Roh-Timeseries rechnen (nicht
   aus `_metric_value` oder `summarize_points()` abschreiben) für eine
   Stichprobe der 25 Zeilen — mindestens je einen Vertreter pro
   Formatierungsweg (a/b/c aus Risks), nicht alle 25 einzeln.
2. Gegen die echte Mail prüfen: HTML-Zelle (Positions-/Label-Auflösung wie
   `derive_row_labels()`) UND Klartext-Zeile (`_PLAIN_ROWS`-Parser analog
   `_s2_klartext_ausblick()`).
3. Vakuum-Gegenprobe: verglichene Testfälle müssen selbst unterscheidbare
   Werte tragen.
4. Fehlzeichen-Konsistenz (`—` vs. `-`) als eigener AC — Charakterisierung
   oder Fix je nach PO-Entscheidung.

### Open Questions (für Spec-Freigabe zu klären)

- [ ] **(a) Em-Dash/Hyphen-Divergenz:** Charakterisieren (Ist-Zustand
      bewachen) oder fixen (Klartext auf `—` angleichen, oder HTML auf `-`)?
      Nutzersichtbar, aber kosmetisch — passt eher zum Muster
      "Nebenbefund/Sammel-Eintrag" als zu einem eigenen Fix, sofern der PO
      nicht widerspricht.
- [ ] **(b) Formatierungs-Stichprobe vs. Vollabdeckung:** Reicht ein
      Vertreter je Formatierungsweg (a/b/c), oder soll `format_value(...,
      style="plain")` gegen `_fmt_metric(..., decimals=...)` für ALLE
      betroffenen Felder (temp_max/min, wind_max, gust_max, wind_chill_min/max,
      cloud_avg, snow_depth_cm, sunny_hours, dewpoint_avg — 9 Felder) einzeln
      auf Dezimalstellen-Gleichheit geprüft werden? Empfehlung: alle 9, da
      `format_value` ein Katalog-Pfad ist, der sich unabhängig vom
      `CV2_METRICS`-`decimals`-Dict ändern kann (kein Wächter hält sie heute
      zusammen).
- [ ] **(c) `warn`-Zeile:** aus der Soll-Menge ausnehmen (kein Zellwert im
      engeren Sinn), analog Scheibe-2-Vorgehen?

## Related Non-Scope

- Scheibe 6 (Form-Wächter Grammatik-Klassen) — Fläche 8, unabhängige Achse.
- Scheibe 7/8 (Reihenfolge/Compare-Kanal-Tabs) — Fläche 5, blockiert bis 7a.
- Reihenfolge-Aspekt von #1356 ist bereits durch `_ordered_rows()`/#1359
  gefixt — nicht erneut Gegenstand dieser Scheibe.
