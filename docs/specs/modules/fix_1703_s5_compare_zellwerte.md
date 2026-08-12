---
entity_id: fix_1703_s5_compare_zellwerte
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [metrics, compare, overview, matrix-test, epic-1703]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 5. Schliesst Flaeche 4 aus
     docs/reference/metric_output_matrix.md §4.2/§6 (Compare-Uebersichtstabelle:
     Zellwert je Metrik, HTML/Klartext-Paritaet). Reine Charakterisierung +
     zwei neue, generische Struktur-Achsen (Formatierungs-Konsistenz,
     Fehlzeichen), KEIN Produktivcode-Fix. -->

# Compare-Zellwert-Vollständigkeit (#1703 Scheibe 5)

## Approval

- [ ] Approved

## Purpose

`tests/tdd/test_channel_metric_matrix.py` (Option C, EIN Register, keine neue
Datei — #1677 B) um eine fünfte Achse (`AC-S5-n`) erweitern, analog Scheibe 1
(`AC-S1-n`), Scheibe 2 (`AC-S2-n`) und Scheibe 4 (`AC-S4-n`) in derselben
Datei. Ziel ist die Compare-**Übersichtstabelle** (`CV2_METRICS`,
`compare_html.py:305-371`, 25 Metrik-Zeilen + `warn`): über die reine
Zeilen-**Existenz** hinaus soll geprüft werden, dass jede Zelle einen
plausiblen, unabhängig gerechneten Wert trägt — und dass HTML und Klartext
derselben Mail für dieselbe Wetterlage dieselbe Zahl zeigen.

**Kein Produktivcode-Fix ist Auftrag dieser Scheibe.** Die Wert-Quelle ist
bereits geteilt (`comparison.py` importiert `_metric_value` direkt aus
`compare_html.py`, kein zweiter Berechnungsweg) — das eigentliche Risiko
liegt in der Formatierung, nicht im Wert selbst, und wird hier
charakterisiert, nicht verändert.

### Korrektur der Scheiben-Prämisse: Fläche 4 ist nicht „nur Zeilen-Existenz",
### sondern 15 von 25 Zeilen bereits wertgeprüft

`metric_output_matrix.md` §4.2 (Zeile 250) behauptet pauschal: „nur
Zeilen-Existenz ist bewacht; ein falscher Wert in der Zelle bleibt grün."
**Bei Nachmessung im Bestand trifft das nur noch auf 10 der 25 Zeilen zu.**
Drei Vorläufer-Issues (#1296, #1324, #1351) haben beim Ergänzen fehlender
Zeilen bereits Wert+Paritäts-Tests mitgeliefert:

| Zeile(n) | Testdatei::Testfunktion | Prüft |
|---|---|---|
| temp_min, gust_max, freezing_level | `tests/unit/test_compare_extra_daily_metrics.py::test_selected_{temp_min,gust_max,freezing_level}_metric_appears_in_overview_matrix` + `::test_plaintext_shows_the_three_remaining_new_rows` | HTML-Wert gegen `WeatherMetricsService`, Klartext-Wert gegen dieselbe Referenz |
| wind_direction_avg, wind_chill_min, cloud_low/mid/high_avg, humidity_avg, dewpoint_avg, pressure_avg, precip_type, snowfall_limit | `tests/unit/test_compare_metric_parity.py::test_selected_*_metric_appears_in_overview_matrix` + `::test_plaintext_shows_all_ten_new_rows` | dieselbe Bauart, 10 Zeilen |
| wind_chill_max | `tests/test_wind_chill_max_selectable.py::test_compare_html_renderer_shows_wind_chill_max_value` + `::test_compare_plain_renderer_shows_wind_chill_max_value` | dieselbe Bauart, 1 Zeile |
| thunder_max | `tests/tdd/test_thunder_low_output_channels.py::test_ac11_compare_html_zeigt_leicht` (Teil der laut `metric_output_matrix.md` „bestbewachten" Gewitter-Achse, 6 Renderpfade inkl. Compare-HTML) | Zellwert + Zell-Ampel für das Gewitter-Signal |

Macht **14 + 1 = 15 der 25 Zeilen** bereits wertgeprüft. Die verbleibenden
**10** Zeilen (`temp_max, wind_max, cloud_avg, sunny_hours, snow_depth_cm,
snow_new_cm, precip_sum, pop_max, uv_max, visibility_min`) haben **keine**
unabhängige Wert-Zusicherung — nur eine grobe Regressions-Prüfung mit
getippten Literalen für drei von ihnen
(`test_existing_{fifteen,eleven}_metrics_unchanged_after_{addition,fix}`,
HTML-only, kein Klartext-Abgleich) und generische
Plausibilitäts-/Format-Prüfung durch den Mail-Validator
(`tests/unit/test_compare_mail_overview_plausibility_coverage.py`), die einen
*unplausiblen* Wert findet, aber keinen *falschen* (z. B. eine Feldvertauschung
mit einem ebenso plausiblen Nachbarwert).

**Konsequenz für den Zuschnitt dieser Scheibe:** kein Duplikat der 15 bereits
gedeckten Zeilen — stattdessen (a) die 10 ungedeckten Zeilen neu abgesichert
(AC-S5-2), (b) zwei generische Achsen ergänzt, die *keine* der 25 Bestandstests
prüft: Formatierungs-Konsistenz zwischen `format_value()` und
`_fmt_metric`/`CV2_METRICS`-`decimals` (AC-S5-4) und die
Fehlzeichen-Divergenz HTML vs. Klartext (AC-S5-5), (c) ein Abhängigkeits-Anker
auf die 15 bereits gedeckten Zeilen, damit ein künftiges stilles Löschen
dieser Testdateien nicht unbemerkt eine Lücke reißt (AC-S5-6, Lehre aus
Scheibe 1/2 F001: „rechnen statt tippen" sichert Vollständigkeit nur, wenn die
Abhängigkeit selbst bewacht ist).

### Entscheidung der drei offenen Fragen (PO-Empfehlung dieser Spec)

1. **Em-Dash/Hyphen-Divergenz (HTML `—` vs. Klartext `-` bei fehlendem
   Wert):** **charakterisieren, nicht fixen.** Kosmetisch, keine
   Fehlinformation (beide Zeichen sind für den Leser eindeutig „kein Wert") —
   passt ins Sammel-Issue #1199, kein eigener Fix in dieser Scheibe (AC-S5-5
   hält den Ist-Zustand fest, ein künftiger *stiller* Wechsel eines der beiden
   Zeichen fällt aber auf).
2. **Formatierungs-Stichprobe vs. Vollabdeckung (`format_value(...,
   style="plain")` gegen `_fmt_metric(..., decimals=...)`):** **alle
   gemessenen Felder einzeln**, nicht nur eine Stichprobe. Kein bestehender
   Wächter hält `format_value` und den `CV2_METRICS`-`decimals`-Dict
   synchron; ein künftiges Auseinanderlaufen (z. B. eine Katalog-Änderung an
   `temperature.decimals`) muss feldgenau auffallen, nicht nur „irgendwo".
   **Korrektur gegenüber dem Context-Dokument:** dort war von „9 Feldern" die
   Rede — bytegenau nachgezählt sind es **10** (`temp_max, temp_min, wind_max,
   gust_max, wind_chill_min, wind_chill_max, cloud_avg, snow_depth_cm,
   sunny_hours, dewpoint_avg`; die Aufzählung im Context-Dokument nannte
   dieselben zehn Felder, nur die Summe war um eins daneben — Lehre aus
   Scheibe 2 F001: falsche Prämissen in ACs sind der teuerste Fehlertyp,
   deshalb hier vor dem Schreiben der ACs am Code nachgezählt statt aus dem
   Context-Dokument übernommen).
3. **`warn`-Zeile aus der 25er-Soll-Menge ausnehmen:** **ja**, analog Scheibe
   2 (Ausblick-Tabelle) und dem bestehenden Wächter
   `test_compare_mail_metric_link_completeness.py`, der die Warn-Zeile aus
   demselben Grund überspringt: sie zeigt gestapelte Warn-Chips, keinen
   numerischen Wert.

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core, ausschließlich Testcode
> (`tests/tdd/`). Kein Frontend, keine Go-Beteiligung.

- **File (Prüfling HTML):** `src/output/renderers/email/compare_html.py` —
  `CV2_METRICS` (:305-371), `_fmt_metric` (:703), `_metric_value` (:644),
  `_DAILY_AGGREGATE_FIELD` (:608), `_render_overview_row` (:712)
- **File (Prüfling Klartext):** `src/output/renderers/comparison.py` —
  `_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` (:70-120), `render_comparison_text`
  (:143-258, Fehlzeichen-Zeile :249), `_fmt_overview_cell` (:505)
- **File (Formatierungsquelle 3):** `src/output/metric_format.py` —
  `format_value()` (:67-117, `_NO_VALUE = "–"` U+2013, **im Compare-
  Übersichtspfad nicht erreichbar**, s. „Die Fehlzeichen-Lage" unten)
- **File (Wächter):** `tests/tdd/test_channel_metric_matrix.py`

**Ausdrücklich UNVERÄNDERT (reine Prüfziele, kein Edit):** `CV2_METRICS`,
`_fmt_metric`, `_metric_value`, `_DAILY_AGGREGATE_FIELD`, `_PLAIN_ROWS`,
`_DAILY_PLAIN_ROWS`, `format_value`, `render_compare_email`.

## Bindende Test-Architektur-Entscheidung (PFLICHT, Prüfort = Wirkort)

Alle **neuen** Tests dieser Scheibe (AC-S5-2, AC-S5-3, AC-S5-5) MÜSSEN über
`render_compare_email(result, ...)` — **einen** Aufruf, der HTML und Klartext
zurückgibt — laufen, nicht über zwei isolierte Aufrufe von
`render_compare_html()`/`render_comparison_text()`. Grund: `render_compare_email`
ist der tatsächliche Produktions-Einstiegspunkt („Single entry point for all
compare-email render callers", `comparison.py:415`); ein isolierter
Doppelaufruf bewiese Paritätsfreiheit nur unter der (hier zutreffenden, aber
nicht selbstverständlichen) Annahme, dass beide Funktionen rein und
seiteneffektfrei sind. Die Vorgänger-Tests aus #1296/#1324 riefen beide
Renderer separat auf demselben `ComparisonResult` — das war für ihren Zweck
ausreichend, aber diese Scheibe folgt dem strengeren Muster aus Scheibe 2
(AC-S2-8: „ein Aufruf liefert beide Formen"), um die Klartext-blinde-Fleck-
Erfahrung aus #1366 nicht zu wiederholen.

## Estimated Scope

- **LoC:** ~200-280 Testcode (6 ACs, eine generische Achse mit 10 Zeilen, zwei
  Stichproben-Achsen, ein Struktur-Check über 10 Katalogfelder, ein
  Abhängigkeits-Anker). Kein Produktivcode-Delta.
- **Files:** 3 (`tests/tdd/test_channel_metric_matrix.py` Erweiterung,
  `docs/specs/modules/fix_1703_s5_compare_zellwerte.md` CREATE,
  `docs/reference/metric_output_matrix.md` MODIFY als Definition-of-Done-Schritt
  — zählt nicht gegen das LoC-Limit, `docs/` ist ausgenommen).
- **Effort:** medium — kleiner als Scheibe 2/4, weil ein erheblicher Teil der
  Fläche bereits durch #1296/#1324/#1351 gedeckt ist (s. Korrektur-Abschnitt).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/output/renderers/email/compare_html.py::CV2_METRICS`/`_metric_value`/`_fmt_metric` | Prüfling (HTML) | Zeilen-Definition, Wert-Auflösung, generische Formatierung |
| `src/output/renderers/comparison.py::_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS`/`render_compare_email` | Prüfling (Klartext + kombinierter Einstieg) | Klartext-Formatierung, Fehlzeichen-Zweig (:249) |
| `src/output/metric_format.py::format_value`/`src/app/metric_catalog.py::get_metric` | Formatierungsquelle 3 | Katalog-`decimals` für die 10 `format_value`-Felder |
| `src/services/weather_metrics.py::summarize_points`/`WeatherMetricsService.compute_basis_metrics` | Soll-Wert-Quelle (Klasse B / Klasse A mit Trip-Regel) | unabhängig gerechnete Erwartungswerte für die 10 neu geprüften Zeilen |
| `tests/unit/test_compare_metric_parity.py`, `test_compare_extra_daily_metrics.py`, `tests/test_wind_chill_max_selectable.py`, `tests/tdd/test_thunder_low_output_channels.py` | Abhängigkeits-Anker (AC-S5-6) | die bereits 15 wertgeprüften Zeilen — dürfen nicht unbemerkt verschwinden |
| `tests/unit/test_compare_mail_metric_link_completeness.py` | Abgrenzung | Zeilen-**Existenz** (Register-Verknüpfung), nicht Zellwert — bleibt unverändert |
| `docs/specs/modules/fix_1703_s2_ausblick_matrix.md` (AC-S2-8) | Vorbild-Muster | „Soll unabhängig aus Rohdaten rechnen" + Vakuum-Gegenprobe |

## Implementation Details

### Die 10 neu zu prüfenden Zeilen — Klasse A vs. Klasse B

`_metric_value()` liest zwei strukturell verschiedene Wege (`compare_html.py:644-654`):

- **Klasse A** (kein Eintrag in `_DAILY_AGGREGATE_FIELD`): `getattr(loc, key,
  None)` — der Renderer liest ein bereits fertiges `LocationResult`-Feld,
  ohne selbst zu aggregieren. Betroffen: `temp_max, wind_max, cloud_avg,
  sunny_hours, snow_depth_cm, snow_new_cm` (6 der 10).
- **Klasse B** (Eintrag in `_DAILY_AGGREGATE_FIELD`): Engine-Feld hat
  Vorrang, sonst Live-Ableitung über `_daily_summary()` →
  `summarize_points(loc.hourly_data)`. Betroffen: `precip_sum, pop_max,
  uv_max, visibility_min` (4 der 10; `thunder_max` ist ebenfalls Klasse B,
  aber s. Known Limitations — nicht Teil dieser Achse).

**Soll-Berechnung je Klasse** (kein Wert wird aus dem Renderer selbst
abgeschrieben):

| Zeile | Klasse | Soll-Regel |
|---|---|---|
| `temp_max`, `wind_max`, `cloud_avg`, `sunny_hours` | A | `WeatherMetricsService().compute_basis_metrics(ts).{temp_max_c,wind_max_kmh,cloud_avg_pct,sunny_hours}` über dieselben rohen `ForecastDataPoint` — dieselbe kanonische Trip-Regel, die bereits die 15 gedeckten Zeilen als Referenz nutzen |
| `snow_depth_cm`, `snow_new_cm` | A, ohne Trip-Regel erreichbar | direkt auf `LocationResult` gesetzter, unterscheidbarer Literalwert (analog `cloud_low_avg` in #1324) — die Renderer-Zusicherung ist „liest das richtige Feld, formatiert richtig, zeigt in HTML+Klartext denselben Wert", **nicht** „die Aggregationsformel stimmt" (die liegt in der ComparisonEngine, außerhalb dieses Renderers, s. Known Limitations) |
| `precip_sum` (sum), `pop_max` (max), `uv_max` (max), `visibility_min` (min) | B, Live-Ableitung | aus rohen Stundenwerten nach der bei `summarize_points()` (`weather_metrics.py:470-481`) hinterlegten Regel gerechnet — Muster identisch zu `_S2_NEUE_FELDER_REGEL` (AC-S2-8) |

**Vakuum-Gegenprobe (PFLICHT):** alle 10 Testwerte müssen paarweise
unterscheidbar sein — sonst bliebe eine Feldvertauschung in
`_DAILY_AGGREGATE_FIELD` oder eine falsche Zeilen-Zuordnung in `CV2_METRICS`
unsichtbar (Lehre aus AC-S2-8/F001).

**`visibility_min` Einheiten-Hinweis:** die Zeile nutzt `_fmt_visibility_overview`
(m → km-Umrechnung), nicht den generischen `_fmt_metric`-Pfad — die
Ist-Wert-Extraktion muss den Faktor 1000 kennen, sonst meldet der Test einen
falschen Mismatch.

### Engine-Vorrang (AC-S5-3) — Stichprobe, kein Vollabdeckungs-Anspruch

Die Vorrangregel `if value is not None: return value` (vor der
Live-Ableitung, `compare_html.py:648-651`) ist **generischer, feldunabhängiger
Code** — sie wird nicht elfmal dupliziert. Ein Nachweis an zwei Feldern
(`precip_sum`, `pop_max`; beide generischer `_fmt_metric`-Pfad, unterschiedliche
Nachkommastellen 1 vs. 0) genügt, um die Regel zu demonstrieren. Bisher
**ungetestet**: alle bestehenden Klasse-B-Tests aus #1296/#1324 setzen
bewusst **kein** Engine-Feld und prüfen nur den Live-Fallback (Kommentar
`test_compare_extra_daily_metrics.py:86-89`: „bekommen bewusst KEIN
`LocationResult`-Feld").

### Formatierungs-Konsistenz (AC-S5-4) — 10 Felder, rein strukturell

Kein Rendering nötig — reiner Katalog-Abgleich: für jedes der 10 Felder wird
`get_metric(<im Klartext-Lambda tatsächlich übergebene metric_id>).decimals`
(oder 0 bei `None`) gegen `CV2_METRICS[<key>].get("decimals")` (oder 0 bei
fehlend, `_fmt_metric`-Default) gehalten:

| CV2-Key | Klartext ruft `format_value(...)` mit | gemessen: Katalog-`decimals` | gemessen: `CV2_METRICS`-`decimals` |
|---|---|---|---|
| `temp_max`, `temp_min` | `"temperature"` | 0 | 0 (kein Eintrag) |
| `wind_max` | `"wind"` | 0 | 0 |
| `gust_max` | `"wind"` | 0 | 0 |
| `wind_chill_min`, `wind_chill_max` | `"temperature"` ⚠️ | 0 | 0 |
| `dewpoint_avg` | `"temperature"` ⚠️ | 0 | 0 |
| `cloud_avg` | `"cloud_total"` | 0 | 0 |
| `snow_depth_cm` | `"snow_depth"` | 0 | 0 |
| `sunny_hours` | `"sunshine"` (style `"bare"`, manueller `"h"`-Suffix) | 1 | 1 |

**Verifizierter Nebenbefund (⚠️, keine Fehlfunktion heute):** die
Klartext-Lambdas für `wind_chill_min`, `wind_chill_max` und `dewpoint_avg`
rufen `format_value("temperature", ...)` — mit der Katalog-ID der
**Temperatur**, nicht mit der eigenen ID (`"wind_chill"`/`"dewpoint"`). Heute
ohne sichtbare Wirkung, weil `wind_chill.decimals` und `dewpoint.decimals`
beide (über den `None`-Default) ebenfalls 0 sind — bei einer künftigen
unabhängigen Katalog-Änderung (z. B. `wind_chill.decimals = 1`) würde die
Klartext-Zeile trotzdem bei 0 Nachkommastellen bleiben, weil sie faktisch die
`temperature`-Konfiguration liest. AC-S5-4 hält diese drei Zeilen **einzeln**
fest (nicht nur aggregiert), damit ein künftiges Auseinanderlaufen sofort die
richtige Zeile benennt. Nebenbefund-Eintrag in #1199 vorgesehen, kein Fix
dieser Scheibe (kosmetisch, aktuell folgenlos).

### Die Fehlzeichen-Lage (AC-S5-5) — zwei Zeichen im Übersichtspfad, nicht drei

| Zeichen | Bedeutung | Quelle | Im Compare-Übersichtspfad erreichbar? |
|---|---|---|---|
| `—` (U+2014, EM DASH) | Wert fehlt | `_fmt_metric(None, …)` (`compare_html.py:705`) | **ja** — HTML-Zellen ohne Wert, generischer `_fmt_metric`-Pfad |
| `-` (U+002D, ASCII HYPHEN) | Wert fehlt | `render_comparison_text()` Zeile 249 (`else "-"`, VOR jedem `fmt`-Aufruf) | **ja** — Klartext-Zeilen ohne Wert, für ALLE Zeilen (auch die drei mit eigenem `fmt`) |
| `–` (U+2013, EN DASH) | Wert fehlt | `format_value()`s `_NO_VALUE` (`metric_format.py:96`) | **nein** — die Klartext-Lambdas prüfen `value is not None` bereits VOR dem `format_value`-Aufruf; dieser Zweig ist im Compare-Übersichtspfad strukturell tot |

AC-S5-5 prüft also eine **zwei**-Zeichen-Divergenz, nicht drei — wer hier drei
Striche vermutet, verwechselt eine im Modul existierende, aber an dieser
Stelle unerreichbare Konstante mit dem tatsächlich gerenderten Zeichen (Lehre
aus S2s eigener Fehlzeichen-Tabelle: „irgendein Strich" ist keine Prüfung).
Geprüft wird eine Stichprobe von zwei generischen `_fmt_metric`-Zeilen
(`temp_max`, `cloud_avg`) mit fehlendem Wert — die drei Zeilen mit eigenem
`fmt` (`thunder_max`, `visibility_min`, `precip_type`) haben ihre eigene
None-Behandlung und sind hier ausdrücklich **nicht** geprüft (Known
Limitations).

## Expected Behavior

- **Input:** dieselben `CV2_METRICS`/`_PLAIN_ROWS`-Register (unverändert), ein
  `LocationResult` mit gezielt gesetzten Klasse-A-Feldern und einem reich
  besetzten `hourly_data`-Satz für die Klasse-B-Live-Ableitung, keine echten
  PO-Daten.
- **Output:** ein neuer, grüner Testblock in
  `tests/tdd/test_channel_metric_matrix.py`, der die 10 bislang ungeprüften
  Zellen der Compare-Übersichtstabelle wertmäßig absichert, die
  Formatierungs-Konsistenz zwischen den drei Formatierungswegen strukturell
  festhält, die Fehlzeichen-Divergenz charakterisiert und die 15 bereits
  gedeckten Zeilen über einen Abhängigkeits-Anker vor stillem Wegfall schützt.
- **Side effects:** keine. Kein Produktivcode-Edit, keine neue Persistenz,
  kein neues Pflicht-Gate (Erweiterung des bestehenden #1677-B-Gates).

## Acceptance Criteria

- **AC-S5-1 (Soll-Menge gerechnet, Bucket-Vollständigkeit):** Gegeben
  `CV2_METRICS` ohne die `warn`-Zeile, wenn die zu prüfende Soll-Menge
  bestimmt wird, dann sind es genau 25 Metrik-Zeilen (Vakuum-Schutz ≥ 20,
  analog AC-S2-2), und die Aufteilung „15 bereits wertgeprüft (AC-S5-6) + 10
  neu geprüft (AC-S5-2)" ergibt exakt diese 25 — ohne Überschneidung, ohne
  Lücke.
  - Test: `len(CV2_METRICS) - 1 == 25` (minus Warn-Zeile) plus
    `len(bereits_gedeckt) + len(neu_geprueft) == 25` und
    `bereits_gedeckt.isdisjoint(neu_geprueft)`, beide Mengen aus dem
    Produktivmodul (`CV2_METRICS`-Keys) gerechnet, nicht getippt.

- **AC-S5-2 (die 10 ungeprüften Zeilen zeigen den gerechneten Wert, HTML UND
  Klartext):** Gegeben ein `LocationResult` mit den 10 Zeilen aus der obigen
  Tabelle auf paarweise unterscheidbare Werte gesetzt bzw. aus rohen
  Stundenwerten gerechnet, wenn die echte Vergleichs-Mail über
  `render_compare_email()` gerendert wird, dann zeigt sowohl die HTML-Zelle
  als auch die Klartext-Zeile jeder der 10 Zeilen exakt den erwarteten,
  formatierten Wert — kein Fehlzeichen, kein vertauschtes Feld.
  - Test: Vakuum-Gegenprobe vor der Wert-Zusicherung (analog
    `_s2_erwartungen_sind_unterscheidbar`); HTML-Zellenauflösung über die
    `min-width:760px`-Übersichtstabelle (Muster `_overview_rows()` aus
    `test_compare_metric_parity.py`), Klartext-Zeilenauflösung über
    `derive_row_labels(..., form="long")` + Label-Präfix-Parsing (Muster
    `_plain_row_value()`).

- **AC-S5-3 (Klasse B: Engine-Feld hat Vorrang vor Live-Ableitung,
  Stichprobe):** Gegeben ein `LocationResult`, bei dem sowohl das
  Engine-Tagesfeld (`precip_sum_mm`, `pop_max_pct`) als auch `hourly_data`
  gesetzt sind, mit voneinander abweichenden Werten, wenn die echte
  Vergleichs-Mail gerendert wird, dann zeigt die Zelle (HTML wie Klartext)
  den Engine-Wert, nicht den aus den Stundenwerten live abgeleiteten Wert.
  - Test: zwei Felder genügen (generischer, feldunabhängiger Code-Pfad in
    `_metric_value()`, s. Implementation Details) — kein Anspruch auf alle 11
    Klasse-B-Zeilen.

- **AC-S5-4 (Formatierungs-Konsistenz `format_value` vs. `_fmt_metric`/
  `CV2_METRICS`-`decimals`, 10 Felder einzeln):** Gegeben die 10 Zeilen, deren
  Klartext-Formatierung über den katalog-getriebenen
  `format_value(metric_id, v, style=...)` läuft (`temp_max, temp_min,
  wind_max, gust_max, wind_chill_min, wind_chill_max, cloud_avg,
  snow_depth_cm, sunny_hours, dewpoint_avg` — bytegenau nachgezählt, s.
  Korrektur oben), wenn die Nachkommastellen aus `get_metric(<im Lambda
  verwendete metric_id>).decimals` (Klartext-Pfad) gegen
  `CV2_METRICS[...]["decimals"]`/`_fmt_metric`-Default (HTML-Pfad) gehalten
  werden, dann stimmen sie für jedes der 10 Felder **einzeln** überein —
  heute alle bei 0 außer `sunny_hours` (1 auf beiden Seiten).
  - Test: reiner Struktur-Vergleich, kein Rendering nötig; parametrisiert
    über die 10 Felder, jeder Fehlschlag benennt genau das betroffene Feld.
    Hält zusätzlich den `wind_chill`/`dewpoint`-vs-`temperature`-Nebenbefund
    fest (Kommentar mit Verweis auf #1199).

- **AC-S5-5 (Fehlzeichen-Charakterisierung, zwei Zeichen):** Gegeben eine
  Zelle einer generischen `_fmt_metric`-Zeile (`temp_max` oder `cloud_avg`)
  ohne verfügbaren Wert, wenn die echte Vergleichs-Mail gerendert wird, dann
  zeigt HTML `—` (U+2014 EM DASH) und Klartext `-` (U+002D ASCII HYPHEN) für
  dieselbe fehlende Zelle — diese Divergenz wird als gemessener Ist-Zustand
  **charakterisiert, nicht gefixt** (PO-Entscheidung dieser Spec, s. Purpose).
  Ein künftiger stiller Wechsel eines der beiden Zeichen fällt auf.
  - Test: bytegenauer Zeichenvergleich (`ord()` bzw. Codepoint-Assertion,
    keine visuelle „sieht aus wie"-Prüfung); der dritte, im Modul existierende
    En-Dash-Zweig (`format_value`s `_NO_VALUE`) ist hier ausdrücklich NICHT
    Gegenstand (strukturell unerreichbar, s. Implementation Details).

- **AC-S5-6 (Abhängigkeits-Anker auf die 15 bereits wertgeprüften Zeilen):**
  Gegeben die vier Testdateien, die heute die Wert+Paritäts-Prüfung für 15 der
  25 Zeilen tragen (`test_compare_metric_parity.py`,
  `test_compare_extra_daily_metrics.py`, `test_wind_chill_max_selectable.py`,
  `test_thunder_low_output_channels.py`), wenn diese Scheibe abgeschlossen
  ist, dann benennt ein Anker-Test genau diese Dateien/Funktionen namentlich
  und schlägt sichtbar fehl, wenn eine davon nicht mehr importierbar ist oder
  eine der genannten Testfunktionen verschwindet.
  - Test: Muster `AC-S2-7` (Abhängigkeits-Anker auf einen getippten
    Größenanker) — hier auf vier Dateien statt einer erweitert, jede einzeln
    benannt, damit ein Fehlschlag sofort sagt, welche Zeile(n) verwaist sind.

## Known Limitations

1. **`thunder_max` ist bewusst nicht Teil von AC-S5-2/AC-S5-5.** Die Zeile
   nutzt einen eigenen, mehrargumentigen Formatierer (`_fmt_thunder` mit
   Hagel-Kennzeichen und Signal-Herkunft, `compare_html.py:744-752`) und ist
   bereits über die dedizierte Gewitter-Testsuite
   (`test_thunder_low_output_channels.py`, laut `metric_output_matrix.md`
   „bestbewachter Fall", 6 Renderpfade inkl. Compare-HTML) charakterisiert.
   Eine zweite, generische Prüfung hier wäre Regel-Zuwachs ohne Fang.
2. **Klasse-A-Zeilen ohne Trip-Regel (`snow_depth_cm`, `snow_new_cm`) prüfen
   Feldmapping + Formatierung, nicht die Aggregationsformel.** Die
   ComparisonEngine, die diese `LocationResult`-Felder aus rohen Stundendaten
   befüllt, liegt außerhalb dieses Renderers und dieser Scheibe.
3. **Die drei Zeilen mit eigenem `fmt` (`thunder_max`, `visibility_min`,
   `precip_type`) sind von AC-S5-5 ausgenommen.** Ihre eigene
   None-Behandlung (`_fmt_thunder(None,…)`, `_fmt_visibility_overview(None)`,
   `_fmt_precip_type(None)`) ist hier nicht nachgemessen — mögliches Ziel
   einer künftigen Scheibe, kein Fund dieser.
4. **`format_value`s `_NO_VALUE`-Zweig (En-Dash, U+2013) ist im
   Compare-Übersichtspfad strukturell unerreichbar** (s. Implementation
   Details „Die Fehlzeichen-Lage") — nicht mit den zwei tatsächlich
   gerenderten Zeichen zu verwechseln.
5. **Stundentabelle (`HOUR_METRICS`) ist NICHT Gegenstand dieser Scheibe** —
   andere Tabelle, bereits durch `tests/unit/test_compare_hourly_catalog_columns.py`
   gedeckt (laut `metric_output_matrix.md` „der einzige echte
   Wirkungs-Vollständigkeitstest im Bestand").
6. **Reihenfolge (Fläche 5) und Form-Dimension (Fläche 8) sind nicht
   Gegenstand.** Reihenfolge ist bereits durch `_ordered_rows()`/#1359
   gefixt (Doppel-Quellen-Historie #1356) und Gegenstand von Scheibe 7;
   Formen (Grammatik-Klassen) sind Scheibe 6.
7. **Ausblick-Tabelle (Scheibe 2, `outlook_columns()`) ist eine andere
   Tabelle mit anderer Metrikliste** (`get_compare_metric_catalog()`, 25
   Paare für den 3-Tages-Ausblick) — nicht zu verwechseln mit `CV2_METRICS`
   (25 Zeilen für den Tageswert-Übersichtsblock). Beide Listen haben
   zufällig dieselbe Größe (25), sind aber inhaltlich unabhängig.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Konkret: AC-S5-2/3/5 MÜSSEN gegen die
ECHTE Mail (`render_compare_email()`) laufen, nicht gegen isolierte
`_metric_value()`-Direktaufrufe.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- In `_DAILY_AGGREGATE_FIELD` (`compare_html.py:608`) die Zuordnung zweier
  der vier Klasse-B-Felder aus AC-S5-2 vertauschen (z. B. `precip_sum` ↔
  `pop_max`) — MUSS AC-S5-2 rot werden lassen (Feldvertauschungs-Fang, Lehre
  aus AC-S2-8/F001).
- Den Vorrang-Zweig in `_metric_value()` (`compare_html.py:648-651`)
  entfernen (immer live ableiten, Engine-Feld ignorieren) — MUSS AC-S5-3 rot
  werden lassen.
- `_fmt_metric`s None-Rückgabe (`compare_html.py:705`) von `"—"` auf `"–"`
  ändern (Em-Dash → En-Dash) — MUSS AC-S5-5 rot werden lassen (beweist, dass
  der bytegenaue Zeichenvergleich wirklich das Zeichen prüft, nicht nur „ist
  ein Strich vorhanden").
- Für EIN Feld aus AC-S5-4 (z. B. `snow_depth`) `decimals` im Katalog
  (`metric_catalog.py`) probeweise auf `1` setzen — MUSS **genau die
  `snow_depth_cm`-Teilprüfung** von AC-S5-4 rot werden lassen, keine der
  anderen neun (Feld-Granularitäts-Fang).

## Definition of Done

- [ ] AC-S5-1 bis AC-S5-6 grün
- [ ] Adversary-Verdict VERIFIED, alle vier Pflicht-Mutationen gefangen
- [ ] `docs/reference/metric_output_matrix.md`: Fläche 4 (§4.2, Zeile 250) und
      Scheibe 5 (§6) auf erledigt umgetragen, inkl. der Korrektur „14 von 25
      bereits wertgeprüft" (Doku darf die pauschale Alt-Aussage nicht
      unkorrigiert stehen lassen)
- [ ] Issue #1703 Scheiben-Checkbox gesetzt, Ergebnis kommentiert

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** reine Testerweiterung eines bereits etablierten,
  budgetierten Gates (#1677 B); keine neue Entscheidungsfläche (kein Kanal,
  kein Provider, kein Datenmodell-, Auth- oder Editor-Paradigma-Wechsel).
  Analog zu Scheibe 3/4.

## Changelog

- 2026-08-12: Initial spec created (Epic #1703, Scheibe 5). Scheiben-Prämisse
  gegen den Bestand nachgemessen: 15 von 25 Zeilen bereits über #1296/#1324/
  #1351/Gewitter-Suite wertgeprüft, statt der pauschal „unbewacht"
  behaupteten Fläche 4. Zuschnitt entsprechend auf die 10 ungeprüften Zeilen
  plus zwei neue generische Achsen (Formatierungs-Konsistenz,
  Fehlzeichen-Charakterisierung) plus Abhängigkeits-Anker reduziert. Drei
  offene Fragen aus dem Context-Dokument entschieden: Em-Dash/Hyphen
  charakterisieren statt fixen, alle 10 (korrigiert von „9") Formatierungs-
  Felder einzeln statt Stichprobe, `warn`-Zeile ausgenommen.
