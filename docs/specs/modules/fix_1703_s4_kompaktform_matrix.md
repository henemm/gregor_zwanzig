---
entity_id: fix_1703_s4_kompaktform_matrix
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [metrics, compact, telegram, matrix-test, epic-1703]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 4. Schliesst Flaechen 6+7
     aus docs/reference/metric_output_matrix.md §4.2/§6 (Kompaktform-
     Varianten und Telegram-Kurzform). Reine Charakterisierung/Regressions-
     Absicherung, KEIN Produktivcode-Fix. -->

# Kompaktform-Varianten und Telegram-Kurzform absichern (#1703 Scheibe 4)

## Approval

- [ ] Approved

## Purpose

`tests/tdd/test_channel_metric_matrix.py` (Option C, EIN Register, keine
neue Datei — #1677 B, `metric_output_matrix.md` §5) um eine vierte Achse
(`AC-S4-n`) erweitern, analog Scheibe 1 (`AC-S1-n`) und Scheibe 2
(`AC-S2-n`) in derselben Datei. Ziel sind die vier Ausgabeorte, an denen
Wetterdaten in **Kompaktform** erscheinen — Kurz-E-Mail, mobile
Kompaktzeilen innerhalb der Vollmail, Fließtext-Kompakt-Zusammenfassung
(Trip und Compare) sowie Telegram-Kurzform. Diese Orte sind bisher
unbewacht (Flächen 6+7, `docs/reference/metric_output_matrix.md` §4.2/§6).

**Kein Produktivcode-Fix ist Auftrag dieser Scheibe.** Auch dort, wo die
Recherche eine strukturelle Eigenheit aufdeckt (Resolver-Divergenz Ort 1
vs. Ort 5, Positivliste in Ort 3), hält diese Scheibe den gemessenen
Ist-Zustand als Test fest, statt ihn zu verändern.

### Korrektur gegenüber der ursprünglichen Fassung (Adversary-Finding F001, gemessen 2026-08-12)

Die erste Fassung dieser Spec behauptete in AC-S4-3 und AC-S4-8 — und im
„Prüfhinweis für den Adversary" als **MUSS**-Bedingung —, dass die Absenz
von `confidence` an Ort 1 (`render_compact()`) und Ort 3
(`format_stage_summary()`) durch dasselbe zentrale `_is_selectable()`-Gate
(`models.py:684`) bewirkt wird wie an Ort 5 (Telegram). Die vorgeschriebene
Mutations-Gegenprobe (`_SELECTABLE_GATE_EXEMPT` um `"confidence"` erweitert)
widerlegt das: **nur** `test_ac_s4_14_telegram_narrow_confidence_absent`
wurde rot, AC-S4-3 und AC-S4-8[`confidence`] blieben grün, obwohl das Gate
`confidence` in diesem Zustand durchlässt.

Tatsächliche, jeweils **lokale und gate-unabhängige** Schutzursache
(im Code verifiziert, nicht vermutet):

| Ort | Warum `confidence` dort nie erscheint |
|---|---|
| Ort 1 `render_compact()` | `build_metrics_summary_pills()` iteriert über die feste Whitelist `_PILL_CATALOG_ORDER` (`src/output/renderers/email/helpers.py:1271-1276`, Schleife Z. 1872-1874) und überspringt jede Metrik, die dort nicht steht. `"confidence"` steht nicht drin. |
| Ort 3 `format_stage_summary()` | `src/output/renderers/compact_summary.py` enthält überhaupt keinen `if`/`elif`-Zweig für `"confidence"` (0 Treffer in der Datei) — dieselbe Positivlisten-Mechanik wie bei AC-S4-9/AC-S4-10. |
| Ort 5 `render_telegram_bubbles()` | **Hier** wirkt das zentrale Gate tatsächlich — per Mutations-Gegenprobe bestätigt (AC-S4-14 wird korrekt rot). |

**Konsequenz für diese Spec:** AC-S4-3 und AC-S4-8 sind unten auf die
gemessene Ursache umformuliert; die Tests selbst und das Produktivverhalten
bleiben unverändert (`confidence` erscheint nachweislich an keinem der
Orte). Beide ACs bleiben als Regression-Baseline ihres jeweiligen
Choke-Points bestehen — sie belegen aber **nicht** die Gate-Wirkung, das
tut allein AC-S4-14. Der „Prüfhinweis für den Adversary" ist entsprechend
korrigiert. Kein Produktivcode-Fix (unverändertes Purpose oben).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core, ausschließlich
> Testcode (`tests/tdd/`). Kein Frontend, keine Go-Beteiligung.

Vier Ausgabeorte:

1. `src/output/renderers/email/compact.py::render_compact()` (Z. 96) —
   Kurz-E-Mail. Nutzt `resolve_trip_active_metrics()`
   (`trip_metric_ids.py:54-56`, Fallback auf `DEFAULT_TRIP_METRIC_IDS` bei
   leerer Auswahl + `altbestand=True`).
2. `src/output/renderers/email/html.py::_render_mobile_compact_rows()`
   (Z. 878) — mobile Kompaktzeilen INNERHALB der Vollmail. Reiner
   Präsentations-Layer ohne eigene Selektionslogik (nimmt
   `allowed_col_keys`/`col_order` vom Aufrufer entgegen).
3. `src/output/renderers/compact_summary.py::CompactSummaryFormatter
   .format_stage_summary()` (Trip-Wrapper, Z. 47ff) — Fließtext-Kompakt-
   Zusammenfassung. Handgeschriebene if/elif-Kette für genau diese
   Positivliste: `temperature`, `temperature_night`, `wind_chill`,
   `wind_chill_night`, `cloud_total`, `precipitation`, `rain_probability`,
   `wind`, `gust`, `wind_direction`, `thunder` (~10 von 26 wählbaren
   Katalog-Metriken).
4. `src/output/renderers/compact_summary.py::format_location_summary()`
   (Compare-Wrapper, Z. 625) — TOTES GLEIS, nirgends mehr aufgerufen seit
   Rework #1300 (PO-Entscheid 2026-07-17,
   `docs/specs/modules/rework_1300_compare_summary_block_removal.md`;
   verifiziert per grep in `compare_html.py`/`comparison.py`, keine
   Treffer).
5. `src/output/renderers/narrow.py::render_telegram_bubbles()` (Z. 625) —
   Telegram-Kurzform. Nutzt `dc.get_enabled_metric_ids()`
   (`models.py:802-804`, KEIN Fallback — Divergenz zu Ort 1).

**Ausdrücklich UNVERÄNDERT (reine Prüfziele, kein Edit):** alle fünf oben
genannten Funktionen, `resolve_trip_active_metrics()`
(`trip_metric_ids.py:54-56`), `DEFAULT_TRIP_METRIC_IDS`,
`get_enabled_metric_ids()` (`models.py:802-804`),
`get_metrics_for_channel()`/`_is_selectable()` (`models.py:684`/`629-650`).

## Bindende Test-Architektur-Entscheidung (PFLICHT, empirisch verifiziert — Prüfort = Wirkort)

Tests für Orte 1/3/5 MÜSSEN über
`TripReportFormatter().format_email(report_type="morning"|"evening", ...)`
laufen (Vorbild: bestehende `_mail_table()`/`_telegram_cells()`-Helfer in
der Testdatei) — **NICHT** isolierter Direktaufruf der nackten Funktionen
mit `_single_metric_dc()`/`_two_metric_dc()`. Grund: `format_email()`
filtert `dc` IMMER über `get_metrics_for_channel()`
(`_is_selectable()`-Gate, `models.py:684`, #1585) BEVOR diese drei
Funktionen die Metrikliste sehen — verifiziert, dass `report_type` in
JEDER Produktiv-Aufrufstelle hart auf `("morning", "evening")`
beschränkt ist (`preview_service.VALID_REPORT_TYPES`).

- Für `render_compact()`: `email_format="compact"` als Parameter (früher
  Return-Zweig in `email/__init__.py:109`, liefert
  `("", compact_text)`).
- Für `render_telegram_bubbles()`: läuft in `trip_report.py` bereits über
  eigens vorgefilterte `_dc_telegram` (Kommentar bei
  `trip_report.py:270-281`, Adversary-Fix einer früheren Scheibe —
  referenzieren, nicht neu erklären).

Ein isolierter Aufruf mit synthetischem `dc` würde die vorgelagerte
Kollabierung umgehen und — wie bei Scheibe 3 gezeigt — den falschen
Choke-Point prüfen.

## Estimated Scope

- **LoC:** ~150-250 Testcode (15 ACs, davon die Mehrzahl mit echtem
  Mehrfach-Render gegen die tatsächliche Produktionspipeline). Kein
  Produktivcode-Delta.
- **Files:** 1 (`tests/tdd/test_channel_metric_matrix.py`, Erweiterung —
  kein neues Modul, s. Test-Namensregel CLAUDE.md).
- **Effort:** medium — vier unterschiedliche Choke-Points mit
  unterschiedlicher Resolver-Logik (Fallback vs. kein Fallback,
  Positivliste vs. generischer Katalog), mehr Fallunterscheidungen als
  Scheibe 3.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_channel_metric_matrix.py` (AC-S1-n/AC-S2-n-Block) | REFERENZ (Teststil, gleiche Datei) | Vorbild für Helfer (`_mail_table()`/`_telegram_cells()`), Parametrisierungsstil über `_METRICS` |
| `docs/specs/modules/fix_1703_s3_selectable_metrics.md` | REFERENZ (Vorgänger-Scheibe) | Format-Vorbild dieser Spec; belegt "Prüfort = Wirkort"-Pflicht am selben Register |
| `docs/reference/metric_output_matrix.md` §4.2/§6 | WIRD AKTUALISIERT (Doku-Nachtrag) | Definition of Done: Flächen 6+7 auf "erledigt, Wächter: …" umtragen |
| Issue #1214 Scheibe 5c | REFERENZ (PO-Entscheid) | Positivliste von `format_stage_summary()` ist akzeptierter Dauerzustand, keine Erweiterung in dieser Scheibe |
| `docs/specs/modules/rework_1300_compare_summary_block_removal.md` | REFERENZ | Beleg, dass `format_location_summary()` totes Gleis ist |
| `src/app/trip_metric_ids.py::resolve_trip_active_metrics()`/`DEFAULT_TRIP_METRIC_IDS` | UNVERÄNDERT | Resolver für Ort 1, Fallback-Verhalten wird charakterisiert, nicht geändert |
| `src/app/models.py::get_enabled_metric_ids()` (Z. 802-804) | UNVERÄNDERT | Resolver für Ort 5, KEIN Fallback — Divergenz wird charakterisiert |
| Issue #1199 | Ziel für Nebenbefund | Resolver-Divergenz Ort 1 vs. Ort 5 wird dort gebucht (Eintrag 2026-08-12), kein eigenes Issue |

## Implementation Details

Vier neue Testgruppen in `tests/tdd/test_channel_metric_matrix.py`,
Namenspräfixe disambiguieren die drei "compact"-Verwechslungsorte
(PFLICHT):

- `test_ac_s4_1_email_compact_*` (Ort 1, `render_compact()`)
- `test_ac_s4_2_mobile_compact_rows_*` (Ort 2, `_render_mobile_compact_rows()`)
- `test_ac_s4_3_compact_summary_*` (Ort 3, `format_stage_summary()`)
- `test_ac_s4_4_telegram_narrow_*` (Ort 5, `render_telegram_bubbles()`)

Ort 1 und Ort 5 laufen als generische Achse über `_METRICS`
(`selectable=True`-Teilmenge), parametrisiert wie AC-S1/AC-S3 aus den
Vorgänger-Scheiben. Ort 3 läuft NICHT generisch über `_METRICS`, sondern
über die feste, im Code handgeschriebene Positivliste (s. Source Punkt 3)
plus eine Gegenprobe mit Metriken außerhalb dieser Liste. Ort 2 bekommt
keine eigene Achse, nur einen einzelnen Charakterisierungstest. Ort 4
bekommt keinen Test (totes Gleis).

## Expected Behavior

- **Input:** der zentrale Metrik-Katalog `_METRICS` (unverändert), Trip-
  Konfigurationen mit gezielt einzeln/kombiniert aktivierten bzw.
  deaktivierten Metriken, ein Fall mit leerer Auswahl (Fallback-Test Ort
  1), keine echten PO-Daten.
- **Output:** ein neuer, grüner Testblock in
  `tests/tdd/test_channel_metric_matrix.py`, der für alle vier
  Kompaktform-Ausgabeorte den gemessenen Ist-Zustand absichert —
  einschließlich der beiden strukturellen Eigenheiten (Positivliste Ort
  3, Resolver-Divergenz Ort 1 vs. Ort 5) als bewusst nicht gefixte
  Charakterisierung.
- **Side effects:** keine. Kein Produktivcode-Edit, keine neue
  Persistenz, kein neues Pflicht-Gate (Erweiterung des bestehenden
  #1677-B-Gates).

## Acceptance Criteria

### Ort 1 — `render_compact()` (Kurz-E-Mail)

- **AC-S4-1 (generische Achse — aktivierte wählbare Metrik erscheint):**
  Given ein Trip mit genau einer wählbaren Metrik aus `_METRICS`
  (`selectable=True`) aktiviert (`enabled=True`), parametrisiert über den
  Katalog / When `render_compact()` über `format_email(email_format=
  "compact", ...)` gerendert wird / Then erscheint diese Metrik (Symbol
  oder Token) im kompakten Text, und keine andere wählbare Metrik
  erscheint.
  - Test: echtes Rendering über `TripReportFormatter().format_email()`
    mit `email_format="compact"`, parametrisiert über eine Teilmenge von
    `_METRICS` (Vorbild AC-S1/AC-S3-Muster).

- **AC-S4-2 (Fallback bei leerer Auswahl):** Given ein Trip ohne jede
  aktivierte Metrik (leere Auswahl, `altbestand=True`-Pfad) / When
  `resolve_trip_active_metrics()` intern den Fallback zieht und
  `render_compact()` darüber läuft / Then erscheinen die Metriken aus
  `DEFAULT_TRIP_METRIC_IDS` im kompakten Text — keine leere Ausgabe.
  - Test: Trip-Fixture mit leerer `metrics`-Liste, echtes Rendering wie
    AC-S4-1, Assertion auf Nicht-Leere UND auf die konkreten
    Default-IDs.

- **AC-S4-3 (confidence nirgends, auch mit theoretisch persistiertem
  `enabled=True`):** Given `confidence.selectable=False` / When ein Trip
  mit `MetricConfig(metric_id="confidence", enabled=True)` über
  `render_compact()` gerendert wird / Then erscheint "confidence"/
  "Sicherheit" nicht im kompakten Text — Ursache ist die feste
  Pillen-Katalog-Whitelist `_PILL_CATALOG_ORDER`
  (`email/helpers.py:1271-1276`), die `"confidence"` nicht enthält und
  deshalb in `build_metrics_summary_pills()` (Z. 1872-1874) überspringt,
  **unabhängig** vom zentralen `_is_selectable()`-Gate.
  - **Korrektur gegenüber der ursprünglichen Fassung (Adversary-Finding
    F001, 2026-08-12):** hier stand zuvor „das `_is_selectable()`-Gate
    wirkt auch hier, obwohl `render_compact()` einen eigenen Resolver
    nutzt". Die Mutations-Gegenprobe (`_SELECTABLE_GATE_EXEMPT` um
    `"confidence"` erweitert) lässt AC-S4-3 fälschlich GRÜN — dieser Ort
    prüft die Gate-Bedingung nicht und kann sie strukturell auch nicht
    prüfen (s. Known Limitations 5). Die Gate-Wirkung beweist AC-S4-14.
  - Test: wie AC-S4-1, Negativ-Assertion, Regression-Baseline des
    Kurz-E-Mail-Choke-Points (kein Gate-Nachweis).

- **AC-S4-4 (deaktivierte Metrik erscheint nicht):** Given eine wählbare
  Metrik mit `enabled=False` / When `render_compact()` darüber läuft /
  Then erscheint sie nicht im kompakten Text.
  - Test: wie AC-S4-1, Negativ-Fall derselben Parametrisierung.

### Ort 2 — `_render_mobile_compact_rows()` (mobile Kompaktzeilen in der Vollmail)

- **AC-S4-5 (keine eigene Selektionslogik, Charakterisierung):** Given
  `_render_mobile_compact_rows()` erhält `allowed_col_keys`/`col_order`
  vom Aufrufer (Präsentations-Layer ohne eigenen Filter) / When die
  Funktion mit einer vom Aufrufer bereits reduzierten Spaltenliste
  aufgerufen wird / Then rendert sie exakt diese Liste ohne zusätzliche
  Filterung oder Auslassung — deckt sich mit dem bestehenden Bestand
  AC-13 (voller Mail-Renderpfad), keine eigenständige Achse nötig.
  - Test: ein Aufruf mit einer bewusst gekürzten `allowed_col_keys`-Liste,
    Assertion, dass genau diese Spalten im HTML-Fragment erscheinen —
    kein Vollständigkeits-Loop über `_METRICS`.

### Ort 3 — `format_stage_summary()` (Fließtext-Kompakt-Zusammenfassung, Trip)

- **AC-S4-6 (Positivliste — alle 10 Einträge erscheinen bei
  Aktivierung):** Given eine Trip-Konfiguration mit allen 10
  Positivlisten-Metriken aktiviert (`temperature`, `temperature_night`,
  `wind_chill`, `wind_chill_night`, `cloud_total`, `precipitation`,
  `rain_probability`, `wind`, `gust`, `wind_direction`, `thunder`) / When
  `format_stage_summary()` läuft / Then erscheint zu jeder der 10 eine
  Erwähnung im Fließtext.
  - Test: parametrisiert über die feste Positivliste, echtes Rendering.

- **AC-S4-7 (Nichtscope — Metriken außerhalb der Positivliste erscheinen
  nie, Charakterisierung des Dauerzustands):** Given eine wählbare
  Metrik aus `_METRICS`, die NICHT in der Positivliste steht
  (~16 verbleibende Katalog-Metriken), aktiviert (`enabled=True`) / When
  `format_stage_summary()` läuft / Then erscheint sie NICHT im
  Fließtext — dies ist kein Bug, sondern PO-Entscheid (#1214 Scheibe 5c),
  diese Scheibe erweitert die Positivliste NICHT.
  - Test: parametrisiert über `_METRICS` minus Positivliste, Negativ-
    Assertion, Kommentar mit Verweis auf #1214 Scheibe 5c.

- **AC-S4-8 (confidence nirgends):** Given `confidence.selectable=False`
  / When ein Trip mit `confidence.enabled=True` über
  `format_stage_summary()` gerendert wird / Then erscheint "confidence"/
  "Sicherheit" nicht im Fließtext — Ursache ist dieselbe strukturelle
  Positivlisten-Mechanik wie bei AC-S4-9/AC-S4-10: `compact_summary.py`
  hat überhaupt keinen `if`/`elif`-Zweig für `"confidence"` (0 Treffer in
  der Datei), **unabhängig** vom zentralen `_is_selectable()`-Gate.
  - **Korrektur gegenüber der ursprünglichen Fassung (Adversary-Finding
    F001, 2026-08-12):** dieser AC wurde zuvor gemeinsam mit AC-S4-3 und
    AC-S4-14 als „aktiver Gate-Choke-Point" geführt. Die
    Mutations-Gegenprobe lässt ihn fälschlich GRÜN — er ist
    Regression-Baseline, kein Gate-Nachweis (s. Known Limitations 5).
  - Test: wie AC-S4-7, Spezialfall confidence, Regression-Baseline.

- **AC-S4-9 (temperature_cold — nicht in Positivliste, erscheint nicht,
  Charakterisierung):** Given `temperature_cold` (selectable=False,
  exemptiert in `_SELECTABLE_GATE_EXEMPT`) NICHT in der Positivliste
  steht / When ein Trip mit `temperature_cold.enabled=True` über
  `format_stage_summary()` gerendert wird / Then erscheint "TmpMin"/
  "temperature_cold" nicht im Fließtext — anders als beim Mail-
  Spalten-Fallback (Scheibe 3, AC-5) hat `format_stage_summary()` keinen
  `remaining`-Fallback-Mechanismus, die Exemption wirkt hier nicht.
  - Test: echtes Rendering, Negativ-Assertion, expliziter Kommentar zur
    Divergenz gegenüber Scheibe 3 AC-5.

- **AC-S4-10 (cape — nicht in Positivliste, erscheint nicht):** Given
  `cape` (selectable=False, NICHT exemptiert) NICHT in der Positivliste
  steht / When ein Trip mit `cape.enabled=True` über
  `format_stage_summary()` gerendert wird / Then erscheint "CAPE"/"CP"
  nicht im Fließtext.
  - Test: wie AC-S4-9, Regression-Baseline gegen S3-AC-2-Muster.

- **AC-S4-11 (deaktivierte Positivlisten-Metrik erscheint nicht):**
  Given eine Positivlisten-Metrik mit `enabled=False` / When
  `format_stage_summary()` läuft / Then erscheint sie nicht im
  Fließtext.
  - Test: parametrisiert über die Positivliste, Negativ-Fall.

### Ort 4 — `format_location_summary()` (Compare-Wrapper, totes Gleis)

Kein AC. Charakterisierung genügt im Fließtext (s. Known Limitations) —
die Funktion ist seit #1300 (2026-07-17) von keinem Aufrufer mehr
erreichbar; ein Test würde totes Verhalten prüfen, keinen Nutzerpfad.

### Ort 5 — `render_telegram_bubbles()` (Telegram-Kurzform)

- **AC-S4-12 (generische Achse — aktivierte wählbare Metrik
  erscheint):** Given ein Trip mit genau einer wählbaren Metrik aus
  `_METRICS` aktiviert (`enabled=True`), parametrisiert über den Katalog
  / When `render_telegram_bubbles()` über die vorgefilterte
  `_dc_telegram` (`trip_report.py:270-281`) gerendert wird / Then
  erscheint diese Metrik in der Telegram-Bubble, keine andere wählbare
  Metrik erscheint.
  - Test: echtes Rendering über `TripReportFormatter().format_email()`
    mit Telegram-Pfad, Vorbild `_telegram_cells()`-Helfer im Bestand.

- **AC-S4-13 (leere Auswahl — KEIN Fallback, Resolver-Divergenz zu Ort 1,
  Charakterisierung als Ist-Zustand):** Given ein Trip ohne jede
  aktivierte Metrik / When `get_enabled_metric_ids()`
  (`models.py:802-804`) intern aufgerufen wird und
  `render_telegram_bubbles()` darüber läuft / Then bleibt die
  Telegram-Ausgabe leer bzw. ohne Metrik-Bubbles — anders als Ort 1
  (AC-S4-2), wo `resolve_trip_active_metrics()` auf
  `DEFAULT_TRIP_METRIC_IDS` zurückfällt. Diese Divergenz wird hier als
  gemessener Ist-Zustand festgehalten, NICHT gefixt (s. Known
  Limitations, Nebenbefund #1199).
  - Test: Trip-Fixture mit leerer `metrics`-Liste, echtes Rendering wie
    AC-S4-12, Assertion auf Abwesenheit jeder Default-Metrik-Bubble —
    Gegenstück zu AC-S4-2, bewusst mit anderem erwartetem Ergebnis.

- **AC-S4-14 (confidence nirgends):** Given `confidence.selectable=False`
  / When ein Trip mit `confidence.enabled=True` über
  `render_telegram_bubbles()` gerendert wird / Then erscheint
  "confidence"/"Sicherheit" nicht in der Telegram-Ausgabe.
  - Test: wie AC-S4-12, Negativ-Assertion, Regression-Baseline gegen
    S3-AC-1-Muster (dort Mail/Compare, hier Telegram als vierter
    Choke-Point).

- **AC-S4-15 (deaktivierte Metrik erscheint nicht):** Given eine
  wählbare Metrik mit `enabled=False` / When
  `render_telegram_bubbles()` darüber läuft / Then erscheint sie nicht.
  - Test: wie AC-S4-12, Negativ-Fall derselben Parametrisierung.

## Known Limitations

1. **Compare-Wrapper (`format_location_summary()`) ist totes Gleis,
   keine Testabdeckung nötig.** Nirgends mehr aufgerufen seit #1300
   (2026-07-17). Ein Test würde ein Verhalten prüfen, das keinen
   Nutzerpfad mehr erreicht — kein AC in dieser Scheibe.
2. **Positivliste von `format_stage_summary()` bleibt Dauerzustand**
   (PO-Entscheid 2026-08-12, Anschluss an #1214 Scheibe 5c). Die
   verbleibenden ~16 wählbaren Katalog-Metriken erscheinen dort
   strukturell nie — AC-S4-7 hält das als akzeptierte Charakterisierung
   fest, keine Erweiterung der Liste ist Auftrag dieser Scheibe.
3. **Resolver-Divergenz** (`resolve_trip_active_metrics()` mit
   `DEFAULT_TRIP_METRIC_IDS`-Fallback in Ort 1 vs.
   `get_enabled_metric_ids()` ohne Fallback in Ort 5) ist am jeweiligen
   Wirkort neutralisiert — beide Orte verhalten sich innerhalb ihres
   eigenen Kontexts konsistent, die Divergenz zeigt sich nur im
   Seitenvergleich (AC-S4-2 vs. AC-S4-13). Strukturell bleibt sie
   fragil: ein künftiger Refactor, der beide Resolver zusammenlegt,
   könnte das Fallback-Verhalten unbeabsichtigt auf Telegram
   übertragen oder umgekehrt entfernen. Bereits als Nebenbefund in
   **#1199 gebucht (Eintrag vom 2026-08-12)** — kein neues Issue, kein
   Fix in dieser Scheibe.
4. **Nicht Gegenstand dieser Scheibe (Epic-Vorgabe):** die übrigen
   Flächen aus `metric_output_matrix.md` §4.2 (Alarm-Renderer-Matrix
   Scheibe 1, Ausblick-Tabelle Scheibe 2, `get_all_metrics()`-
   Blindstelle Scheibe 3, Compare-Zellwert, Einheiten,
   Frontend-Register, Trip-SMS-Kaskade) — nur Flächen 6+7
   (Kompaktform-Varianten + Telegram-Kurzform) sind Ziel dieser
   Scheibe.
5. **Für Ort 1 und Ort 3 ist ein „echter" Gate-Test strukturell nicht
   möglich — das ist eine Grenze, keine Lücke** (Adversary-Finding F001,
   2026-08-12). Ein Test, der die Wirkung des zentralen
   `_is_selectable()`-Gates an diesen beiden Orten beweist, bräuchte eine
   Katalog-Metrik, die **gleichzeitig** (a) in `_PILL_CATALOG_ORDER`
   (`email/helpers.py:1271-1276`) bzw. in der Positivliste von
   `format_stage_summary()` steht **und** (b) `selectable=False` ist.
   Eine solche Metrik existiert im Katalog derzeit nicht: die
   `selectable=False`-Menge (`confidence`, `temperature_cold`, `cape`)
   ist disjunkt zu beiden Listen. Solange das so bleibt, sind AC-S4-3 und
   AC-S4-8 Regression-Baselines ihres jeweiligen Choke-Points — die
   Gate-Wirkung wird ausschließlich von AC-S4-14 (Ort 5, Telegram)
   bewacht. Wird künftig eine gelistete Metrik auf `selectable=False`
   gesetzt, entsteht die Testbarkeit von selbst und der Nachweis ist
   nachzuziehen.

## Definition of Done

Nach grünem Testlauf **zusätzlich zum Code-Merge** (Epic-Vorgabe, nicht
optional): `docs/reference/metric_output_matrix.md` §4.2 „Flächen 6+7"
und §6 „Scheibe 4" aktualisieren — von einer offenen Beschreibung auf
einen Verweis auf den neuen Wächter umstellen (Testdatei + die neuen
AC-Nummern in `tests/tdd/test_channel_metric_matrix.py`), analog wie
Scheibe 3 markiert wurde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** reine Testerweiterung eines bereits etablierten,
  budgetierten Gates (#1677 B); keine neue Entscheidungsfläche (kein
  Kanal, kein Provider, kein Datenmodell-, Auth- oder
  Editor-Paradigma-Wechsel). Analog zu Scheibe 3.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie
WIRKT — oder nur dort, wo der Code steht?** Konkret: Orte 1/3/5 MÜSSEN
gegen den ECHTEN Renderpfad (`TripReportFormatter().format_email()`)
getestet werden, nicht gegen isolierte Direktaufrufe — genau die Falle,
die Scheibe 3 bereits einmal aufgedeckt hat (s. „Bindende
Test-Architektur-Entscheidung" oben).

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- `_SELECTABLE_GATE_EXEMPT` um `"confidence"` erweitern — welcher Test
  wird rot? MUSS **genau AC-S4-14** sein (Ort 5, Telegram — der einzige
  Ort, an dem das zentrale Gate die entscheidende Variable ist).
  AC-S4-3 (Ort 1) und AC-S4-8 (Ort 3) bleiben dabei **erwartungsgemäß
  grün**: sie sind durch lokale, gate-unabhängige Mechanismen geschützt
  (Pillen-Katalog-Whitelist bzw. fehlender `confidence`-Zweig, s.
  „Korrektur gegenüber der ursprünglichen Fassung" und Known Limitations
  5). **Diese Erwartung wurde am 2026-08-12 korrigiert** — die frühere
  Fassung forderte hier alle drei Tests rot und definierte damit eine
  Bedingung, die der Code strukturell nicht erfüllen kann (Finding F001).
- Die Positivliste in `format_stage_summary()` um eine Metrik aus dem
  Nichtscope-Set kürzen (eine bereits gelistete entfernen) — MUSS
  AC-S4-6 rot werden lassen (Vollständigkeits-Fang).
- Den Fallback in `resolve_trip_active_metrics()` deaktivieren (leere
  Auswahl liefert `[]` statt `DEFAULT_TRIP_METRIC_IDS`) — MUSS AC-S4-2
  rot werden lassen, AC-S4-13 bleibt davon unberührt (anderer Resolver).
- `get_enabled_metric_ids()` um denselben Fallback-Mechanismus erweitern
  wie Ort 1 — MUSS AC-S4-13 rot werden lassen (die Divergenz-Assertion
  erwartet explizit KEINEN Fallback).

## Changelog

- 2026-08-12: Initial spec created (Epic #1703, Scheibe 4). Vier
  Ausgabeorte (Kurz-E-Mail, mobile Kompaktzeilen, Fließtext-Zusammen-
  fassung Trip, Telegram-Kurzform) gegen den echten Renderpfad
  spezifiziert; Compare-Wrapper als totes Gleis ausgeschlossen;
  Resolver-Divergenz Ort 1 vs. Ort 5 als Nebenbefund #1199 gebucht statt
  in dieser Scheibe gefixt.
- 2026-08-12: **Korrektur nach Adversary-Runde 1 (Finding F001, HIGH).**
  AC-S4-3 und AC-S4-8 behaupteten fälschlich denselben
  `_is_selectable()`-Gate-Mechanismus wie AC-S4-14; die
  Mutations-Gegenprobe zeigt, dass Ort 1 und Ort 3 durch unabhängige,
  lokale Mechanismen geschützt sind (Pillen-Katalog-Whitelist
  `_PILL_CATALOG_ORDER` bzw. fehlender `confidence`-Zweig in
  `compact_summary.py`) und nur Ort 5 den Gate-Mechanismus tatsächlich
  demonstriert. Korrigiert: neuer Abschnitt „Korrektur gegenüber der
  ursprünglichen Fassung", AC-S4-3- und AC-S4-8-Wortlaut,
  Adversary-Prüfhinweis (Erwartung: genau AC-S4-14 rot), neue Known
  Limitation 5 (echter Gate-Test für Ort 1/3 mangels passender
  Katalog-Metrik strukturell unmöglich). Dazu die beiden Docstrings in
  `tests/tdd/test_channel_metric_matrix.py`. Kein Produktivcode-Delta,
  keine Assertion-Änderung — Produktivverhalten war und bleibt korrekt.
