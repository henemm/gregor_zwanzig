# Context: Ausblick-Tabelle Trip + Compare (#1703 Scheibe 2)

**Workflow:** `feat-1703-s2-ausblick-matrix`
**Issue:** #1703 (Epic), Scheibe 2
**Erstellt:** 2026-08-11
**Branch:** `feat-1703-s2-ausblick-matrix` (von `origin/main` `e21f4f48`)

## Request Summary

Die Metrik×Kanal-Matrix (`tests/tdd/test_channel_metric_matrix.py`, Gate #1677 B) um
eine Achse für die **Ausblick-Tabelle** erweitern, damit die laut
`docs/reference/metric_output_matrix.md` §4.1 größte unbewachte Fläche ("Fläche 2")
geschlossen wird. Vorbild und Leitplanken: Scheibe 3 (erledigt) und Scheibe 1 (erledigt),
beide in derselben Testdatei.

## Der zentrale Befund: die Prämisse der Scheibe stimmt so nicht

Issue-Text und `metric_output_matrix.md:74/94` sagen, `outlook_columns()` "speist beide
Mail-Familien". **Gemessen ist das falsch.** Alle sechs Aufrufstellen des geteilten
Renderers, vollständig:

| Aufrufstelle | Familie | `metrics=` |
|---|---|---|
| `src/output/renderers/email/html.py:1357` | Trip | **nein** |
| `src/output/renderers/email/plain.py:338` | Trip | **nein** |
| `src/services/trip_report_scheduler.py:1844` | Trip | **nein** |
| `src/output/renderers/comparison.py:348` | Compare | ja |
| `src/output/renderers/email/compare_html.py:1101` (`build_outlook_row`) | Compare | ja |
| `src/output/renderers/email/compare_html.py:1175` (`render_outlook_table`) | Compare | ja |

Keine Wrapper, kein `functools.partial`, keine kwargs-Durchreichung — jede Stelle ruft
literal auf.

**Konsequenz:** `outlook_columns()` wird ausschließlich vom Ortsvergleich erreicht.
Der Trip-Ausblick läuft im festen Legacy-Spaltenpfad. Eine Metrik-Achse im Sinne von
"jede Katalogmetrik erscheint als Spalte" existiert für den Trip **strukturell nicht** —
der Nutzer kann dort keine Ausblick-Spalten wählen.

Das ist kein Defekt, sondern der dokumentierte Bestandsschutz: `test_compare_outlook_metric_selection.py`
AC-9 hält ausdrücklich fest, dass eine fehlende Auswahl die bisherigen sieben festen
Spalten liefert.

## Die tatsächliche Lücke (nachgemessen)

Der Ortsvergleich-Ausblick ist katalog-getrieben und **teilweise** bewacht:
`tests/tdd/test_compare_outlook_metric_selection.py` (433 Z., #1361/#1368) prüft das
Auswahl-*Prinzip* — nur gewählte Spalten erscheinen (AC-1), Klartext deckungsgleich zu
HTML (AC-2), leere Auswahl entfernt den Block (AC-8), fehlende Auswahl behält die sieben
Legacy-Spalten (AC-9), unbekannte Einträge werden verworfen und geloggt (AC-10).

Dafür benutzt die Datei **genau zwei** fest getippte Auswahlen (`:35-36`):
`{"metric_id": "temperature", "aggregation": "max"}` und
`{"metric_id": "precipitation", "aggregation": "sum"}`, dazu zwei ungültige Paare
(`einhorn/max`, `confidence/min`, `:410-412`).

Repo-weite Gegenprobe: **kein** Test paart `get_compare_metric_catalog()` mit dem
Ausblick-Renderer. Die Treffer auf den Compare-Katalog in `tests/` betreffen den
Endpunkt, die Stundentabelle, die Formatmigration und `cape` — nie den Ausblick.

> **Die Lücke ist also nicht das Auswahl-Prinzip, sondern die Katalog-Deckung:
> 2 von 25 Paaren sind je durch den Ausblick-Renderer gelaufen.** Für die übrigen 23
> kann heute kein Test sagen, ob sie eine Spalte ergeben, welchen Kopf sie trägt und ob
> die Zelle einen plausiblen Wert zeigt.

## Die Soll-Menge (gemessen, nicht getippt)

Quelle: `src/output/renderers/compare_metric_catalog.py`.

- `COMPARE_METRIC_CATALOG` (`:76-162`) — kuratierte Liste, **26** Roh-Einträge
- `get_compare_metric_catalog()` (`:251-322`) reichert an und filtert `selectable=False`
  heraus (`:284-285`) → **25** ausgelieferte Einträge; es fällt genau `cape_max_jkg`
  weg (`cape.selectable=False` seit #1585, `metric_catalog.py:382`)
- `key_for(metric_id, aggregation)` (`:239-248`) — Umkehrindex über die **rohe** Liste,
  also vor dem Filter

Die 25 Paare tragen je `metric_id` + `aggregation`; `label` und `aggregation_label`
entstehen erst zur Aufrufzeit aus `get_metric(metric_id).label_de` bzw.
`aggregation_label_de(aggregation)` — im Katalog steht kein getippter Name.

**Formzweige:** genau **1× `kind="ordinal"`** (`thunder_level_max`), genau **1× `kind="enum"`**
(`precip_type_dominant`), **23× `kind="range"`**. Damit sind alle drei Zweige von
`format_outlook_value()` (`compare_outlook_metric_ids.py:117-145`) durch die Soll-Menge
belegbar.

**Zweite Hürde nach dem Katalog:** `outlook_columns()` verlangt zusätzlich
`summary_field_for(metric_id, aggregation) is not None` (`compare_outlook_metric_ids.py:98-100`).
Laufzeitgeprüft lösen alle 25 ausgelieferten Paare auf einen `SegmentWeatherSummary`-Feldnamen
auf — die Doppelbedingung ist heute also deckungsgleich, aber nicht per Konstruktion.
Genau das macht sie zu einem lohnenden Wächter-Punkt.

**Vorhandener getippter Größenanker:** `tests/tdd/test_compare_metric_catalog_endpoint.py:519`
behauptet `len(get_compare_metric_catalog()) == 25`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/compare_outlook_metric_ids.py` | `outlook_columns()` (`:78`), `format_outlook_value()` (`:117`), `resolve_outlook_metrics()` (`:45`) — Prüfling |
| `src/output/renderers/compare_metric_catalog.py` | Soll-Mengen-Quelle: `COMPARE_METRIC_CATALOG` (`:76`), `get_compare_metric_catalog()` (`:251`), `key_for()` (`:239`) |
| `src/output/renderers/email/outlook.py` | Geteilter Renderer; katalog-getriebener Zweig `:148-172` (HTML) / `:342-351` (Klartext) / `:520-535` (Zeilenbau) |
| `src/app/metric_catalog.py` | `summary_field_for()` (`:608-619`), `_METRICS` (`:92-590`, 28 Einträge), `get_all_metrics()` (`:701`) |
| `src/app/models.py` | `SegmentWeatherSummary` (`:388-468`) — Zielfelder der Auflösung |
| `src/output/renderers/comparison.py` | `render_compare_email()`, Klartext-Aufruf `:348` |
| `src/output/renderers/email/compare_html.py` | Compare-HTML-Aufrufe `:1101`/`:1175`; `_fmt_thunder` (`:204`), `_fmt_precip_type` (`:244`) |
| `tests/tdd/test_channel_metric_matrix.py` | Zieldatei der neuen Achse (1568 Z.) |
| `tests/tdd/test_compare_outlook_metric_selection.py` | Bestehende Prinzip-Prüfung (433 Z.) — Abgrenzung, nicht Ersatz |
| `tests/unit/test_compare_hourly_catalog_columns.py` + `tests/helpers/hourly_columns.py` | **Vorbild** für "rechnen statt tippen" + Vakuum-Schutz |
| `tests/tdd/test_trip_outlook_parity.py` + `tests/fixtures/outlook_trip_parity/` | Byte-Golden des Trip-Legacy-Pfads — darf nicht brechen |

## Existing Patterns

**Bauschema der Matrix-Datei** (aus Scheibe 1 und 3, beide in derselben Datei):

1. Soll-Menge aus einer **benannten Produktivkonstante** rechnen
   (`_alarm_soll_ids()` `:1068-1077` aus `_ALERT_METRIC_TO_CATALOG_ID`;
   `_NON_SELECTABLE_METRIC_IDS` `:531` aus `_METRICS`)
2. **Vakuum-Schutz** mit Mindestgröße gegen stilles Schrumpfen
   (`_ALARM_SOLL_MINDESTGROESSE = 8` `:1082`, geprüft `:1247-1321`)
3. Ausnahmen nie kopieren, sondern aus dem Produktivmodul lesen
   (`_SELECTABLE_GATE_EXEMPT` aus `app.models:643`)
4. Ist-Werte aus dem **echten Renderpfad**, nicht aus Hilfsfunktionen —
   `TripReportFormatter().format_email()`, HTML per Regex geparst (`_mail_table()` `:288-315`).
   Kein `Mock`/`patch` in der Datei (0 Treffer).

**Vorbild `tests/helpers/hourly_columns.py:100-158`:** Soll-Mengen-Funktion plus
`assert_soll_menge_ist_plausibel()` (Katalog ≥ 24, Ausnahmemenge nicht leer,
Rechnung `len(soll) == len(katalog) - 1 - len(ausgenommen)`).

**Echte Compare-Mail mit Ausblick-Auswahl** (kürzester Weg, aus
`test_compare_outlook_metric_selection.py:109-127`):

```python
from output.renderers.comparison import render_compare_email
html, text = render_compare_email(
    result, outlook_enabled=True,
    outlook_metrics=[{"metric_id": "temperature", "aggregation": "max"}],
)
```

Ein Aufruf liefert **HTML und Klartext** — deckt den bekannten Klartext-blinden Fleck
des Mail-Validators mit ab.

## Dependencies

- **Upstream:** `compare_metric_catalog` → `metric_catalog` (`get_metric`, `summary_field_for`,
  `selectable`), `models.SegmentWeatherSummary`
- **Downstream:** `email/outlook.py` (beide Familien), `compare_html.py`, `comparison.py`;
  Änderungen am Renderer treffen Trip **und** Compare

## Existing Specs

- `docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md` — Vorgängerscheibe, Spec-Struktur
- `docs/specs/modules/fix_1703_s3_selectable_metrics.md` — Vorgängerscheibe
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — Ursprungsspec des Auswahl-Ausblicks
- `docs/reference/metric_output_matrix.md` §4.1 (Fläche 2), §6 (Scheibe 2) — Definition of Done
- ADR-0037 (datengetriebene Ausblick-Spalten), ADR-0005/#710 (`confidence` nicht wählbar)

## Verdachtsmomente — Ergebnis der Messung (2026-08-11)

1. **`hail` erreicht den Ausblick nie — WIDERLEGT.** `outlook_columns()` setzt den
   Schlüssel tatsächlich nie, aber die Produktions-Aufrufstelle injiziert ihn:
   `outlook.py:532` ruft `format_outlook_value(..., {**col, "hail": _hail})`. Gemessen:
   `format_outlook_value(ThunderLevel.MED, {**spalte, "hail": True})` → `'mittel · Hagel: ja'`.
   Der Docstring beschreibt korrekt, dass der **Aufrufer** den Schlüssel ergänzt.
2. **Doppelbedingung Katalog ∧ `summary_field_for` — BESTÄTIGT deckungsgleich.**
   Alle 25 ausgelieferten Paare überstehen beide Prüfungen; `resolve_outlook_metrics()`
   verwirft keines, `outlook_columns()` liefert 25 Spalten. Deckungsgleich, aber nicht
   erzwungen → lohnender Wächterpunkt.
3. **Dublettenlogik der Spaltenbeschriftung — BESTÄTIGT wirksam.** Bei voller Auswahl
   entstehen `Temperatur Maximum`/`Temperatur Minimum` und
   `Gefühlte Temperatur Minimum`/`Gefühlte Temperatur Maximum`; **keine** doppelten Köpfe.
4. **`temperature`+`avg`** ist zentral auflösbar (`temp_avg_c`), im Compare-Katalog nicht
   vertreten — offene Frage, aber ohne Nutzerwirkung (nicht wählbar, also kein Defekt).

## Risks & Considerations

- **Geteilter Renderer:** jede Produktivänderung an `email/outlook.py` trifft die Trip-Mail.
  Schutz: `tests/fixtures/outlook_trip_parity/` (Byte-Golden, laut README **nie**
  nachziehen — ein roter Lauf ist ein Befund) und `tests/golden/email/outlook-thunder-day-night.txt`.
- **Renderer-Commit-Gate** greift, sobald eine Datei unter `src/output/renderers/email/*.py`
  gestaged wird (`renderer_mail_gate.py`) — dann sind `test_issue_811_mode_matrix.py` +
  ein frischer Validator-Lauf Pflicht. Bei reiner Test-Scheibe entfällt das.
- **Katalog-Wächter-Grenze** (Lehre aus Scheibe 1, Finding F001): Ein Test, der sein Soll
  aus `get_compare_metric_catalog()` liest, bewacht **Vollständigkeit**, nicht
  **Zuordnung**. Eine Vertauschung *im Katalog* bliebe grün. Muss in der Spec als Grenze
  benannt und, wo ein redundanter Alt-Wächter existiert, im Testdocstring verlinkt werden.
- **Abgrenzung zu Scheibe 4:** Telegram (`narrow.py:571` `_outlook_lines()`) und
  Kompakt-Mail (`email/compact.py:227-238`) haben **eigene** Ausblick-Implementierungen,
  die `outlook.py` gar nicht importieren. Sie gehören nicht in diese Scheibe.
- **LoC:** Scheibe 1 lag mit Schätzung um Faktor 2,75 daneben (Override auf 600 nötig).
  Hier vorab realistisch schätzen.

---

# Analysis (2026-08-11)

## Type

**Feature** (Wächter-Achse) — **mit** einem dabei gefundenen, nutzersichtbaren Produktivdefekt.

## Hauptbefund: fünf Ausblick-Spalten sind dauerhaft leer

Gemessen über den echten Mail-Pfad (`render_compare_email()` mit allen 25 Katalogpaaren,
reich besetzte Stundenpunkte): **20 von 25 Zellen zeigen einen Wert, 5 zeigen `–`** —
in HTML **und** Klartext, an jedem der drei Ausblickstage.

| Spalte | Summary-Feld | Stundenwert im Datensatz |
|---|---|---|
| Schneehöhe | `snow_depth_cm` | `snow_depth_cm=30.0` gesetzt |
| Neuschnee | `snow_new_sum_cm` | `snow_new_24h_cm=4.0` gesetzt |
| Windrichtung | `wind_direction_avg_deg` | `wind_direction_deg=210.0` gesetzt |
| Gefühlte Temperatur Minimum | `wind_chill_min_c` | `wind_chill_c` gesetzt |
| Gefühlte Temperatur Maximum | `wind_chill_max_c` | `wind_chill_c` gesetzt |

**Ursache, isoliert:** `services/weather_metrics.py:1071` `summarize_points()` ist eine
**handgepflegte Aufzählung** von Zusatz-Aggregaten. Sie ruft `compute_basis_metrics()` plus
elf namentlich verdrahtete `_compute_*`-Regeln (`:1097-1111`). Die fünf Regeln für die
obigen Felder existieren als Methoden und sind im **Trip**-Pfad
`compute_extended_metrics()` (`:752-760`) angeschlossen — in `summarize_points()` nie.

**Nachgemessen, dass der Fix trägt:** alle fünf Methoden liefern auf dem Compare-Eingang
korrekte Werte (`_compute_snow_depth`→30.0, `_compute_fresh_snow`→16.0,
`_compute_wind_direction`→210, `_compute_wind_chill`→5.0, `_compute_wind_chill_max`→23.0).

**Kein dokumentierter Vorsatz — im Gegenteil:** Der Kommentar `:763-765` hält die
*spiegelbildliche* Lücke fest (#1391: Schneefallgrenze fehlte im **Trip**-Pfad, obwohl
`summarize_points()` sie setzte). #1324 und #1392 sind Flicken an derselben Naht. Zwei
handgepflegte Listen, die deckungsgleich bleiben müssten, sind dreimal auseinandergelaufen.

**Nutzerwirkung:** Wer im Ortsvergleich eine dieser fünf Größen für den 3-Tages-Ausblick
wählt, bekommt dauerhaft eine Strichspalte — unabhängig vom Wetter. Nach der
Nebenbefund-Triage ist das Kategorie (a), nutzersichtbares Fehlverhalten.

## Entscheidung: die Trip-Seite bekommt keine Achse

Die im Kontext offene Frage ist beantwortet — **negativ, mit Begründung**: Ein
Abdeckungs-Wächter für die festen sieben Trip-Spalten wäre schwächer als der bestehende
Schutz. `tests/tdd/test_trip_outlook_parity.py` vergleicht das **gesamte** Ausblick-HTML
und den Klartext byte-genau gegen `tests/fixtures/outlook_trip_parity/`. Jede stille
Erweiterung oder Beschneidung des Legacy-Pfads ist dort bereits rot — strenger, als eine
Metrik-Achse es je wäre. Eine zweite Prüfung desselben Sachverhalts wäre Regel-Zuwachs
ohne Fang.

Scheibe 2 ist damit **Compare-only**. Das ist keine Verkleinerung des Auftrags, sondern
die Korrektur einer falschen Prämisse im Issue-Text: Der Trip-Ausblick hat keine
wählbaren Spalten, also auch keine Metrik×Kanal-Fläche.

## Affected Files

| Datei | Typ | Beschreibung |
|---|---|---|
| `src/services/weather_metrics.py` | MODIFY | Die fünf fehlenden `_compute_*`-Regeln in `summarize_points()` verdrahten (`:1097-1111`) |
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | Neue Achse AC-S2-1..n (Ausblick × Compare-Katalog) |
| `tests/helpers/outlook_columns.py` | CREATE | Soll-Mengen-Ableitung + `assert_soll_menge_ist_plausibel()` (Vorbild `hourly_columns.py`) |
| `docs/specs/modules/fix_1703_s2_ausblick_matrix.md` | CREATE | Spec |
| `docs/reference/metric_output_matrix.md` | MODIFY | Fläche 2 + Scheibe 2 umtragen (Definition of Done) |

## Scope Assessment

- **Dateien:** 5 (3 Code/Test, 2 Doku)
- **Geschätzte LoC (zählend):** ~+300 (Test-Achse ~200, Helfer ~70, Produktivfix ~10,
  Anpassung roter Bestandstests ~20). Doku zählt nicht.
- **Risiko:** MITTEL

**LoC-Warnung:** Das überschreitet das 250er-Limit. Bei Scheibe 1 lag die Schätzung um
Faktor 2,75 daneben; ich schätze hier bewusst großzügig und hole die Freigabe für
`loc_limit_override 600` zusammen mit der Spec-Freigabe ein, statt sie später als
Prozess-Unterbrechung nachzureichen.

## Technischer Ansatz

1. **Soll-Menge rechnen, nicht tippen:** Helfer leitet die 25 Paare aus
   `get_compare_metric_catalog()` ab. Vakuum-Schutz analog `hourly_columns.py:130-158`
   (Mindestgröße, Rechnung `len(ausgeliefert) == len(roh) - len(nicht_selectable)`).
2. **Prüfort = Wirkort:** Ist-Werte aus `render_compare_email()` — ein Aufruf liefert HTML
   **und** Klartext, beide aus derselben `outlook_columns()`-Quelle. Damit ist der
   bekannte Klartext-blinde Fleck des Mail-Validators mit abgedeckt.
3. **Drei Ebenen, aufsteigend streng:** (a) jede Katalogmetrik ergibt eine Spalte,
   (b) jeder Spaltenkopf ist eindeutig, (c) **jede Zelle trägt einen Wert** bei
   vorhandenem Stundenwert — Ebene (c) ist die, die den Defekt fängt.
4. **Der Produktivfix bekommt einen reziproken Wächter,** keine Fünferliste: beide
   Aggregationspfade (`compute_extended_metrics` ↔ `summarize_points`) gegeneinander
   halten — dieselbe Bauart wie `_HANDLED_UNITS` in Scheibe 1. Sonst ist die nächste
   Drift wieder unbewacht.

## Risiken

- **Der Fix wirkt über den Ausblick hinaus.** `summarize_points()` speist auch die
  Compare-Übersichtstabelle (`compare_html.py:627`) und die Kompakt-Zusammenfassung
  (`compact_summary.py:651`). Dort erscheinen künftig Werte, wo bisher Striche standen —
  gewollt, aber Bestandstests/Goldens können rot werden. In RED zu messen, nicht zu raten.
- **Katalog-Wächter-Grenze (Scheibe-1-Lehre F001):** Eine Achse, die ihr Soll aus
  `get_compare_metric_catalog()` liest, bewacht Vollständigkeit, nicht Zuordnung. Als
  Grenze in die Spec, nicht stillschweigend.
- **Trip-Paritäts-Golden** darf nicht brechen; `summarize_points()` ist nicht der
  Trip-Aggregator, ein Bruch wäre also ein Signal, kein Nachziehgrund.

## Open Questions

- [ ] Keine blockierenden. `temperature`+`avg` (im Compare-Katalog nicht vertreten) wird
      als Beobachtung in der Spec vermerkt, nicht in dieser Scheibe geändert.
