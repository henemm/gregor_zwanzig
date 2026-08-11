---
entity_id: fix_1703_s3_selectable_metrics
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [metrics, selectable, matrix-test, epic-1703, non-selectable]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 3 -- PO-Reihenfolge: MUSS
     zuerst laufen. Schliesst Flaeche 3 aus docs/reference/metric_output_matrix.md
     §4.1: get_all_metrics() filtert selectable=False heraus, jeder
     Vollstaendigkeitstest, der ueber get_all_metrics() iteriert (Scheiben
     1/2/4/5), erbt strukturell diese Blindstelle. -->

# Nicht-wählbare Register-Metriken: die `get_all_metrics()`-Blindstelle schließen (#1703 Scheibe 3)

## Approval

- [ ] Approved

## Purpose

`get_all_metrics()` (`src/app/metric_catalog.py:693-701`) liefert
`[m for m in _METRICS if m.selectable]` — jeder Vollständigkeitstest, der
über diese Funktion iteriert (das werden die Scheiben 1/2/4/5 in
`tests/tdd/test_channel_metric_matrix.py` tun), kann `selectable=False`-
Metriken strukturell nie sehen. Das ist keine Lücke in einem einzelnen
Test, sondern eine Blindstelle **aller** künftigen Matrix-Achsen gleichzeitig
(`docs/reference/metric_output_matrix.md` §4.1, "Fläche 3"). Diese Scheibe
schließt sie mit einem kleinen, generischen Wächter, der stattdessen über
`_METRICS` iteriert und für jede nicht-wählbare Register-Metrik mit
Ausgabefeldern (`sms_code`, `alert_label`, `summary_fields`, …) prüft, dass
sie GENAU dort ankommt (oder GENAU dort NICHT ankommt), wo ihr dokumentierter
Sollzustand es vorschreibt — heute drei Fälle (`confidence`, `cape`,
`temperature_cold`), je mit eigenem Sollzustand, keiner gemeinsamen Formel.

**Kein Produktivcode-Fix ist Auftrag dieser Scheibe.** Ziel ist ausschließlich
ein neuer, zukunftssichernder Wächter in einer bestehenden, bereits
budgetierten Testdatei (#1677 B, Option C aus `metric_output_matrix.md` §5 —
Matrix-Test achsenweise erweitern, kein zweites Register, kein neues
Pflicht-Gate).

### Korrektur gegenüber dem Kontext-Dokument (gemessen 2026-08-10)

`docs/context/feat-1703-s3-selectable-metrics.md` behauptet unter „Risks",
die Stundentabellen-Frage sei „EMPIRISCH GEKLÄRT": `temperature_cold`
erscheine **nicht** als eigene Stundenspalte, weil `dp_field="t2m_c"`
identisch mit der Spalte „Temp" sei und eine Dublette wäre — „korrekt und
braucht keinen Fallback". Ein direkter Render-Test gegen
`TripReportFormatter().format_email(...)` mit `build_default_display_config()`
widerlegt das:

```
row = fmt._dp_to_row(data[0], config)
# {'time': '00', 'temp': 12.0, 'temp_cold': 12.0, 'felt': 8.0, ...}
```

Die Spalte **erscheint** — als „TmpMin" am Ende der Kopfzeile (`['Time',
'Temp', 'Feels', 'Wind', 'Gust', 'Rain', 'Thdr', 'SnowL', 'Cloud', 'Sun',
'TmpMin', 'Risk']`), mit **identischem Zahlenwert** zu „Temp" in jeder
Stunde. Grund: `TripReportFormatter._dp_to_row()`/`_aggregate_night_block()`
(`trip_report.py:627`/`534`) — die tatsächlich produktiv aufgerufenen
Zeilen-Baumethoden — haben **keinen** eigenen `.selectable`-Check; sie
verlassen sich vollständig auf die vorgelagerte Kollabierung
`dc.get_metrics_for_channel("email", report_type)` (`trip_report.py:135-138`),
und die IST exemption-bewusst (`_is_selectable()`, `models.py:629`) —
`temperature_cold` übersteht sie also und erreicht die Zeilen-Builder
unverändert `enabled=True`. Der im Kontext-Dokument (und im ursprünglichen
Auftragstext dieser Scheibe) zitierte `.selectable`-Check in
`email/helpers.py::dp_to_row()`/`aggregate_night_block()` (Zeile 120/177) ist
eine **zweite, produktiv ungenutzte** Implementierung gleichen Namens — kein
Aufrufer in `src/` erreicht sie über den Trip-Mail-Pfad (nur die
modul-eigene, selbst nirgends aufgerufene `extract_hourly_rows()` und ~13
Testdateien, die sie isoliert aufrufen). Details, Einordnung und
Scope-Entscheidung: s. „Known Limitations".

**Konsequenz für diese Spec:** AC-6 unten hält den **gemessenen** Ist-Zustand
fest (Charakterisierung: die Dublette existiert), nicht die im
Kontext-Dokument angenommene Abwesenheit. Ob die Dublette selbst ein
Nebenbefund für #1199 ist, entscheidet der PO/Team-Lead bei Spec-Freigabe —
diese Spec fixt sie nicht (kein Produktivcode-Auftrag, s. Purpose oben).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core, ausschließlich Testcode.
> Kein Frontend, keine Go-Beteiligung.

- **File:** `tests/tdd/test_channel_metric_matrix.py`
- **Identifier:** neue parametrisierte Testfunktionen, die den bestehenden
  AC-13/14/15-Block (#1677 B) um eine vierte Achse ergänzen. Iterationsbasis
  ist `app.metric_catalog._METRICS` (Modul-Liste, Zeilen 92-593), NICHT
  `get_all_metrics()` — genau das ist die zu schließende Blindstelle.

**Ausdrücklich UNVERÄNDERT (reine Prüfziele, kein Edit):**

- `src/app/metric_catalog.py` — `_METRICS`/`_METRICS_BY_ID` (Z. 92-593/593),
  `get_all_metrics()` (Z. 693-701, die Blindstelle selbst — bleibt bewusst
  bestehen, sie ist für ihre eigentlichen Aufrufer `/api/metrics` und
  Trip-Editor korrekt; nur Vollständigkeitstests dürfen sie nicht mehr als
  einzige Iterationsbasis nutzen), drei `selectable=False`-Definitionen:
  `temperature_cold` (Z. 120-129), `confidence` (Z. 322-331), `cape`
  (Z. 351-383)
- `src/app/models.py` — `_SELECTABLE_GATE_EXEMPT` (Z. 626, aktuell
  `frozenset({"temperature_cold"})`), `_is_selectable()` (Z. 629-650),
  `_filter_metrics_by_report_type()` (Z. 653-686), gemeinsamer Choke-Point für
  `get_metrics_for_channel()`/`get_metrics_for_report_type()` (Z. 797-842)
- `src/output/renderers/trip_report.py` — `TripReportFormatter.format_email()`
  Kollabierungsschritt `dc.get_metrics_for_channel("email", report_type)`
  (Z. 135-138, DER eigentliche Choke-Point für Trip-Mail+Stundentabelle),
  `_dp_to_row()` (Z. 627-662), `_aggregate_night_block()` (Z. 534),
  `_visible_cols()` (Z. 668-673)
- `src/output/renderers/email/helpers.py` — `resolve_metric_col_order()`
  (Z. 302-315, raw `.selectable`-Check ohne Exemption, dokumentierte
  Ausnahme via `remaining`-Fallback), `dp_to_row()`/`aggregate_night_block()`/
  `visible_cols()` neuer Pfad (Z. 103-137/157-235/253-293 — **nicht** Ziel
  dieser Scheibe, s. Known Limitations)
- `src/output/renderers/email/html.py` — `remaining`-Fallback-Zweig
  (Z. 678-682), `_col_order = resolve_metric_col_order(dc)` (Z. 1021)
- `src/services/weather_change_detection.py` — `is_alert_metric_active()`
  (Z. 181-238), `_ALERT_METRIC_TO_CATALOG_ID[AlertMetric.TEMPERATURE_MIN] =
  ("temperature_cold", "temperature")` (Z. 85)
- `src/services/compare_alert.py` — `_SUMMARY_KEY_TO_CATALOG_ID["temp_min_c"]
  = "temperature_cold"` (Z. 59), `_display_config_from_active_metrics()`
  (Z. 475-524)
- `src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()`
  (Z. 284, raw `.selectable`-Check)
- `src/output/renderers/compare_metric_ids.py::_non_selectable_keys()`
  (Z. 140, raw `.selectable`-Check, `resolve_enabled_metrics()`)

## Estimated Scope

- **LoC:** ~110-170 Testcode (8 ACs, davon 3 mit echtem Mehrfach-Render
  gegen die tatsächliche Produktionspipeline — `TripReportFormatter().format_email()`,
  Telegram-rich, Compare —, 1 generischer Parametrisierungs-Block über
  `_METRICS`). Kein Produktivcode-Delta.
- **Files:** 1 (`tests/tdd/test_channel_metric_matrix.py`, Erweiterung —
  kein neues Modul, s. Test-Namensregel CLAUDE.md).
- **Effort:** low. Doku selbst nennt „klein" (`metric_output_matrix.md` §6
  Scheibe 3: „Risiko: niedrig. Größe: klein."); die Recherche bestätigt das —
  einzige Komplexität ist das korrekte Anzapfen der ECHTEN Produktionspfade
  (s. Korrektur oben), nicht die Testmenge selbst.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_cape_not_selectable.py` | REFERENZ (Teststil, Regression-Baseline) | `TestAlertEngineExcludesCape` (AC-9-Muster: Größe + Kollateralschaden-Wächter) ist Vorbild für AC-2/AC-8 unten. `TestEmailTableExcludesCapeColumn::test_dp_to_row_excludes_cape_col_key` testet **nicht** den produktiven Trip-Mail-Pfad (s. Known Limitations) — bleibt unangetastet, wird hier nicht als Beleg für AC-2/AC-6 herangezogen |
| `tests/tdd/test_issue_715_confidence_not_selectable.py` | REFERENZ (Teststil) | Vorbild für AC-1 (API-Exclusion, `/api/metrics`) |
| `tests/tdd/test_compare_alert_metric_gating.py::test_f002_guard_temp_min_active_min_temp_delta_fires` | REFERENZ (Bestand, bleibt grün) | Deckt AC-4 (Compare-Aktivierung `temperature_cold`) bereits ab — kein redundanter Test, nur generische Mitabsicherung über AC-8 |
| `tests/unit/test_mail_column_order.py::test_legacy_config_without_order_keeps_catalog_order` | REFERENZ (Bestand, bleibt grün) | Hält bereits fest, dass „TmpMin" am Ende der Spaltenreihenfolge steht (`remaining`-Fallback) — Vorbild für AC-5, Beleg für die Korrektur oben |
| `src/app/models.py::_SELECTABLE_GATE_EXEMPT` | UNVERÄNDERT | Klein, benannt, darf nur schrumpfen (#1585-Kommentar) — AC-8 spiegelt exakt diese Menge, keine eigene Kopie |
| `docs/reference/metric_output_matrix.md` §4.1/§6 | WIRD AKTUALISIERT (Doku-Nachtrag) | Definition of Done: „Fläche 3"/„Scheibe 3" auf „erledigt, Wächter: …" umtragen (s. u.) |
| `docs/adr/0005-confidence-not-selectable-metric.md` | REFERENZ | Grundsatz-ADR `selectable=False`, unverändert |

## Implementation Details

Neue Testachse in `tests/tdd/test_channel_metric_matrix.py`, parametrisiert
über `[m for m in _METRICS if not m.selectable]` (heute exakt 3 Einträge)
statt über das bestehende `_ALL_METRIC_IDS = [m.id for m in get_all_metrics()]`.
Zwei Gruppen von Assertions, je nachdem ob die Metrik in
`_SELECTABLE_GATE_EXEMPT` steht:

**Gruppe A — nicht exemptiert (heute: `confidence`, `cape`):** MUSS an
KEINEM der geprüften Choke-Points erscheinen:
1. Trip-Mail-Spaltenreihenfolge (`resolve_metric_col_order()` UND — Prüfort
   = Wirkort — der tatsächlich gerenderte `<thead>` von
   `TripReportFormatter().format_email()`)
2. Compare-Katalog (`get_compare_metric_catalog()`, per `metric_id`)
3. Compare-Auswahlauflösung (`resolve_enabled_metrics()`, per `key`)
4. Alarm-Aktivität (`is_alert_metric_active()`), NUR falls die Metrik einen
   `alert_metrics`-Eintrag trägt (bei `confidence`: keiner — dieser Punkt
   entfällt dann strukturell, nicht durch eine leere Assertion)

**Gruppe B — exemptiert (heute: `temperature_cold`):** die generische
„muss überall fehlen"-Regel gilt NICHT — stattdessen verweist der Test auf
die spezifischen AC-3 bis AC-7 unten (Kältealarm MUSS aktiv sein,
Compare-Aktivierung MUSS wirken, Mail-Spalte MUSS über den
`remaining`-Fallback erscheinen, Stundenspalte erscheint HEUTE als
Dublette, Compare-Katalog bleibt strukturell leer).

Diese Zweiteilung spiegelt exakt die Bedingung, die `_is_selectable()`
(`models.py:644`) selbst prüft — der Test dupliziert damit keine eigene,
zweite Definition von „ist wählbar", sondern liest `_SELECTABLE_GATE_EXEMPT`
direkt aus `app.models` (wie es der Produktivcode auch tut).

## Expected Behavior

- **Input:** der zentrale Metrik-Katalog `_METRICS` (unverändert), drei
  synthetische Fixtures (ein Trip mit `confidence`/`cape`/`temperature_cold`
  jeweils `enabled=True`; ein Compare-Preset mit `temp_min_c` in
  `active_metrics`), keine echten PO-Daten.
- **Output:** ein neuer, grüner Testblock in
  `tests/tdd/test_channel_metric_matrix.py`, der die drei heutigen
  `selectable=False`-Fälle UND jede künftige `selectable=False`-Metrik ohne
  Testcode-Änderung gegen dieselbe Grundregel prüft.
- **Side effects:** keine. Kein Produktivcode-Edit, keine neue Persistenz,
  kein neues Pflicht-Gate (Erweiterung des bestehenden #1677-B-Gates).

## Acceptance Criteria

- **AC-1 (confidence — nirgends, trotz `summary_fields`):** Given
  `confidence.selectable=False`, `default_enabled=False`, KEIN `sms_code`,
  KEIN `alert_label`, aber `summary_fields={"min": "confidence_pct_min"}` /
  When ein Trip mit `MetricConfig(metric_id="confidence", enabled=True)`
  über `TripReportFormatter().format_email()` (Mail-Spaltenreihenfolge),
  `render_for_channel("telegram", ...)` (Telegram-rich) und
  `get_compare_metric_catalog()` (Compare-Katalog) geprüft wird / Then
  erscheint `confidence`/„Sicherheit" an KEINER dieser drei Stellen — die
  drei erlaubten Erscheinungsorte (E-Mail-Textblock `build_confidence_hint()`,
  SMS-Symbol `C+/C~/C?`, interne Aggregation/`confidence_pct_min` in
  `risk_engine.py`/`outlook.py`) bleiben von dieser Prüfung unberührt und
  unverändert.
  - Test: echtes Rendering wie AC-13/14 im selben File; Regression-Baseline
    gegen `test_issue_715_confidence_not_selectable.py` (API-Exclusion bleibt
    dort, wird hier nicht dupliziert).

- **AC-2 (cape — nirgends, TROTZ `sms_code="CP"`/`alert_label="CAPE"`,
  Mutations-Gegenprobe-Ziel):** Given `cape.selectable=False`,
  `default_enabled=False`, MIT `sms_code="CP"` UND `alert_label="CAPE"` /
  When dieselben drei Stellen wie AC-1 geprüft werden UND zusätzlich
  `is_alert_metric_active(AlertMetric.CAPE, dc)` mit `cape.enabled=True` /
  Then erscheint CAPE nirgends — kein „CP"-Token in der Mail-Spaltenliste,
  kein Compare-Katalog-Eintrag, UND `is_alert_metric_active()` liefert
  `False` trotz `enabled=True`.
  - Test: wie AC-1, plus direkter `is_alert_metric_active`-Aufruf (Vorbild
    `test_cape_not_selectable.py::TestAlertEngineExcludesCape`). **Dies ist
    der explizite Mutations-Gegenprobe-Fall:** würde `_SELECTABLE_GATE_EXEMPT`
    versehentlich um `"cape"` erweitert, MUSS mindestens die
    Mail-Spaltenreihenfolge-Assertion dieses AC rot werden (s. „Prüfhinweis
    für den Adversary").

- **AC-3 (temperature_cold — Kältealarm MUSS aktiv bleiben, Trip-Pfad):**
  Given ein Trip mit `temperature_cold` in Default-Konfiguration (Dataclass-
  Default `enabled=True`, kein `default_enabled` gesetzt — s.
  `build_default_display_config()`) / When
  `is_alert_metric_active(AlertMetric.TEMPERATURE_MIN, dc)` geprüft wird /
  Then liefert es `True` — der Kältealarm bleibt funktional, obwohl
  `temperature_cold.selectable=False` ist.
  - **Korrektur gegenüber dem ursprünglichen Auftragstext (Adversary-Finding
    F001, 2026-08-10):** Ursache ist NICHT die Exemption in
    `_SELECTABLE_GATE_EXEMPT`. `is_alert_metric_active()`
    (`src/services/weather_change_detection.py:224-234`) liest
    `_SELECTABLE_GATE_EXEMPT` an keiner Stelle — der eigentliche Grund ist
    die OR-Tupel-Abbildung `_ALERT_METRIC_TO_CATALOG_ID[TEMPERATURE_MIN] =
    ("temperature_cold", "temperature")`
    (`src/services/weather_change_detection.py:85`): das mitgemappte, selbst
    `selectable=True`/`enabled=True` Glied `"temperature"` trägt das
    Ergebnis per `any(...)` über beide Katalog-IDs. Mutations-Gegenprobe
    (`_SELECTABLE_GATE_EXEMPT` komplett geleert) lässt AC-3 fälschlich GRÜN
    — die Exemption-Wirkung für `temperature_cold` wird stattdessen von
    AC-5 bewiesen (Mail-Spalte über den `remaining`-Fallback — dort IST die
    Exemption die entscheidende Variable). AC-3 bleibt als
    Regression-Baseline für den Kältealarm bestehen (schützt gegen den
    historisch dokumentierten Tupel-OR-Abbau, `weather_change_detection.py:
    210-218`), beweist aber NICHT die Exemption-Wirkung.
  - Test: direkter `is_alert_metric_active`-Aufruf mit einem
    `UnifiedWeatherDisplayConfig`, das explizit
    `MetricConfig(metric_id="temperature_cold", enabled=True)` trägt (Vorbild
    Assertion-Stil `test_cape_not_selectable.py::TestAlertEngineExcludesCape`,
    hier der positive Gegenfall). Kein neuer Redundanz-Test nötig, falls beim
    Implementieren ein bereits bestehender Test exakt diese Zusicherung hält
    (zu verifizieren: `tests/tdd/test_issue_914_slice1_foundation.py`,
    `tests/unit/test_issue_222_alert_rules_detection.py` grep-geprüft, aber
    keiner der Treffer ruft `is_alert_metric_active(TEMPERATURE_MIN, ...)`
    mit `temperature_cold` direkt auf — nach heutigem Stand ist dies ein
    echt neuer Test).

- **AC-4 (temperature_cold — Compare-Aktivierung MUSS wirken, Regression-
  Baseline):** Given ein Compare-Preset mit `active_metrics` enthält
  `"temp_min_c"` / When `compare_alert.py::_display_config_from_active_metrics()`
  daraus eine `display_config` baut und `is_alert_metric_active(
  AlertMetric.TEMPERATURE_MIN, ...)` sie auswertet / Then gilt die Min-
  Temperatur als aktiv.
  - Test: bereits Bestand, bleibt grün —
    `tests/tdd/test_compare_alert_metric_gating.py::test_f002_guard_temp_min_active_min_temp_delta_fires`.
    Diese Scheibe fügt keinen zweiten, redundanten Test hinzu; die generische
    Parametrisierung (AC-8) verankert denselben Choke-Point zusätzlich
    zukunftssichernd (falls `_SELECTABLE_GATE_EXEMPT` künftig um eine zweite
    ID wächst, deckt AC-8 automatisch mit ab, ob deren Compare-Aktivierung
    ebenfalls funktioniert).

- **AC-5 (temperature_cold — Mail-Spaltenreihenfolge über den
  `remaining`-Fallback, Prüfort = Wirkort):** Given ein Trip mit Default-
  Konfiguration (`temperature_cold.enabled=True`, keine eigene `order`) /
  When die Trip-Mail über `TripReportFormatter().format_email()` gerendert
  wird — NICHT nur `resolve_metric_col_order()` isoliert aufgerufen / Then
  erscheint die Spalte „TmpMin" im tatsächlichen `<thead>` der HTML-Tabelle,
  an letzter Position (`remaining`-Fallback, `email/html.py:678-682`),
  OBWOHL `resolve_metric_col_order(dc)` selbst `"temp_cold"` NICHT in seiner
  Rückgabeliste führt (dokumentierte Bestands-Abweichung,
  `models.py:619-625`).
  - Test: wie `test_mail_column_order.py::_mail_columns` (Regex gegen den
    echten `<thead>`, kein isolierter Funktionsaufruf) — Regression-
    Baseline gegen `test_legacy_config_without_order_keeps_catalog_order`.

- **AC-6 (temperature_cold — Stundentabelle: GEMESSENE Dublette, KEINE
  Fixierung dieser Scheibe):** Given derselbe Default-Trip / When die
  Stundenzeilen der Trip-Mail gerendert werden
  (`TripReportFormatter._dp_to_row()`/`_aggregate_night_block()`,
  `trip_report.py` — nicht die gleichnamigen, produktiv ungenutzten
  Funktionen in `email/helpers.py`, s. Known Limitations) / Then erscheint
  HEUTE (gemessen 2026-08-10) eine eigene Stundenspalte „TmpMin" NEBEN
  „Temp", mit für dieselbe Stunde IDENTISCHEM Zahlenwert (beide lesen
  `dp_field="t2m_c"`) — eine echte Dublette. Dies widerspricht der im
  Kontext-Dokument als „empirisch geklärt" bezeichneten Annahme (s.
  Purpose/Korrektur oben); dieser AC hält den Ist-Zustand als
  Charakterisierung fest, ohne ihn zu bewerten oder zu fixen.
  - Test: wie AC-5, Assertion auf Anwesenheit BEIDER Spalten („Temp" und
    „TmpMin") im `<thead>` UND auf identischen Zellwert für dieselbe Stunde
    (kein Bug-Fix-Test, reine Charakterisierung des heutigen Verhaltens —
    Vorbild AC-2 in `fix_1677_sms_reihenfolge.md`, dort für Byte-Identität).

- **AC-7 (temperature_cold — Compare-Katalog bleibt strukturell leer):**
  Given `get_compare_metric_catalog()`/das rohe `COMPARE_METRIC_CATALOG` /
  When beide auf `metric_id=="temperature_cold"` geprüft werden / Then
  taucht kein Eintrag auf — nicht weil ein `.selectable`-Filter ihn
  entfernt, sondern weil `COMPARE_METRIC_CATALOG` ihn nie enthalten hat
  (`temperature_cold` ist eine reine Trip-Alarm-Pseudogröße ohne
  Compare-Entsprechung).
  - Test: `"temperature_cold" not in {e["metric_id"] for e in
    COMPARE_METRIC_CATALOG}` — Charakterisierung, aber zukunftssichernd
    (würde jemand ihn versehentlich ergänzen, wird dieser Test rot, bevor
    ein `.selectable`-Filter ihn stillschweigend wieder herausfiltert).

- **AC-8 (generisch, zukunftssichernd — die eigentliche Blindstellen-
  Reparatur):** Given `[m for m in _METRICS if not m.selectable]` (heute:
  `confidence`, `cape`, `temperature_cold` — NICHT hartkodiert, sondern aus
  dem Katalog abgeleitet) / When pro Metrik geprüft wird, ob ihre `id` in
  `_SELECTABLE_GATE_EXEMPT` steht / Then gilt für JEDE NICHT gelistete
  Metrik dieselbe Grundregel aus AC-1/AC-2 (erscheint an keinem der
  ID-verankerten Choke-Points: `resolve_metric_col_order()`-Rückgabe,
  `get_compare_metric_catalog()`-Metrik-IDs, `resolve_enabled_metrics()`-
  Ergebnis; UND, sofern ein `alert_metrics`-Eintrag existiert, gilt sie über
  `is_alert_metric_active()` nie als aktiv) — für JEDE gelistete Metrik wird
  stattdessen auf die spezifischen ACs 3-7 verwiesen, die Regel wird NICHT
  generisch erzwungen (die Exemption macht eine pauschale „muss fehlen"-
  Aussage dort falsch).
  - Test: EIN parametrisierter Testlauf über `_METRICS` (gefiltert auf
    `selectable=False`, heute 3 Fälle, mit `_SELECTABLE_GATE_EXEMPT`-
    Verzweigung direkt aus `app.models` importiert, keine zweite Kopie der
    Ausnahmeliste). Deckt automatisch eine künftige vierte
    `selectable=False`-Metrik ab, ohne dass diese Testdatei erneut
    angefasst werden muss — das ist der strukturelle Reparaturanteil dieser
    Scheibe (`metric_output_matrix.md` §4.1: „die Wirkung ist strukturell:
    sie repariert die Aussagekraft jeder künftigen Achse mit").

## Known Limitations

1. **`email/helpers.py::dp_to_row()`/`aggregate_night_block()`/`visible_cols()`
   (neuer Pfad, Horizon-Filter) sind produktiv ungenutzt für den Trip-Mail-
   Pfad, werden aber von ~13 Testdateien isoliert aufgerufen** (u. a.
   `test_cape_not_selectable.py`, `test_issue_715_confidence_not_selectable.py`,
   `test_trip_mail_corridor_mark.py`, `test_issue_911_mail_details.py`).
   Der echte Produktionspfad läuft über `TripReportFormatter._dp_to_row()`/
   `_aggregate_night_block()`/`_visible_cols()` (`trip_report.py`), die KEINEN
   eigenen `.selectable`-Check tragen und sich vollständig auf die
   vorgelagerte, exemption-bewusste Kollabierung (`get_metrics_for_channel`,
   `trip_report.py:135-138`) verlassen. Für `confidence`/`cape` ist das Ist-
   Verhalten heute trotzdem korrekt (beide werden bereits VOR `_dp_to_row()`
   aus `dc.metrics` entfernt, weil sie nicht exemptiert sind) — die
   ~13 Tests prüfen also eine funktional äquivalente, aber strukturell
   andere (und produktiv tote) Funktion. Das ist eine „Prüfort ≠ Wirkort"-
   Lücke bei GRÜNEN, nicht ROTEN Tests — kein aktueller Fehlbetrieb, aber ein
   Befund im Sinne von CLAUDE.md („Ist die Zusicherung dort geprüft, wo sie
   WIRKT?"). **Nicht Gegenstand dieser Scheibe** (Scope ist ausschließlich
   Fläche 3, die `get_all_metrics()`-vs-`_METRICS`-Blindstelle) — Empfehlung:
   Sammel-Eintrag in #1199, kein eigenes Issue (keine aktuell falsche
   Auslieferung, reine Testarchitektur-Präzisierung).
2. **Die gemessene `temperature_cold`-Stundenspalten-Dublette (AC-6) wird
   NICHT gefixt.** Diese Scheibe hält sie als Charakterisierung fest; ob sie
   ein eigener Nebenbefund (#1199) oder ein Issue wird (nutzersichtbar: eine
   real ausgelieferte Mail zeigt zwei Spalten mit identischen Zahlen), ist
   PO-/Team-Lead-Entscheidung bei Spec-Freigabe, keine Vorentscheidung
   dieser Spec.
3. **Nicht Gegenstand dieser Scheibe (Epic-Vorgabe):** die Alarm-Renderer-
   Matrix (Scheibe 1, Fläche 1: `alert/render.py`), die Ausblick-Tabelle
   (Scheibe 2, Fläche 2: `outlook_columns()`), und die übrigen 7 unbewachten
   Flächen aus `metric_output_matrix.md` §4.2 (Compare-Zellwert, Reihenfolge
   jenseits E-Mail/Telegram-rich, Kurzform-/Kompakt-Varianten, Telegram-
   Kurzform, Einheiten, Frontend-Register, Trip-SMS-Kaskade) — nur Fläche 3
   (die `get_all_metrics()`-vs-`_METRICS`-Blindstelle selbst) ist Ziel.
4. **`app/metric_catalog.py:615/661/869/945`** (katalog-interne
   `.selectable`-Checks, z. B. `get_metric`-Familien, Template-Filter) sind
   KEIN externer Ausgabeort (Bestand, bereits so im Kontext-Dokument
   eingeordnet) — kein AC prüft sie gezielt.
5. **`get_all_metrics()` selbst bleibt unverändert.** Sie ist für ihre
   eigentlichen Aufrufer (`/api/metrics`, Trip-Editor-Metrikauswahl) korrekt
   — das Ziel ist, dass VOLLSTÄNDIGKEITSTESTS sie nicht mehr als einzige
   Iterationsbasis verwenden, nicht ihre Filterlogik zu ändern.

## Definition of Done

Nach grünem Testlauf **zusätzlich zum Code-Merge** (Epic-Vorgabe, nicht
optional): `docs/reference/metric_output_matrix.md` §4.1 „Fläche 3" und §6
„Scheibe 3" aktualisieren — den Absatz von einer offenen Beschreibung („kann
… nicht sehen") auf einen Verweis auf den neuen Wächter umstellen (Testdatei
+ die neuen AC-Nummern in `tests/tdd/test_channel_metric_matrix.py`), analog
wie andere geschlossene Punkte im Dokument markiert werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** reine Testerweiterung eines bereits etablierten,
  budgetierten Gates (#1677 B); keine neue Entscheidungsfläche (kein Kanal,
  kein Provider, kein Datenmodell-, Auth- oder Editor-Paradigma-Wechsel).
  ADR-0005 (`selectable=False`-Grundsatz) bleibt unverändert gültig — diese
  Scheibe testet ihn nur an einer bisher unbewachten Stelle nach.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Konkret für diese Spec: mehrere ACs
wurden bewusst gegen den ECHTEN Renderpfad (`TripReportFormatter().format_email()`)
statt gegen isolierte Hilfsfunktionen formuliert — genau weil eine isolierte
Prüfung hier nachweislich (s. Korrektur oben) die falsche Funktion getroffen
hätte.

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- **Primärfall (explizit im Auftrag):** `_SELECTABLE_GATE_EXEMPT` um
  `"cape"` erweitern (`models.py:626`) — welcher Test wird rot? MUSS
  mindestens AC-2 sein (Mail-Spaltenreihenfolge UND/ODER
  `is_alert_metric_active(CAPE, ...)` kippt auf `True`). Bleibt der Testlauf
  grün, prüft AC-2 nicht die tatsächliche Exemption-Bedingung, sondern nur
  eine hartkodierte `"cape"`-Zeichenkette.
- Denselben Mutationstest mit `"confidence"` statt `"cape"` wiederholen —
  fängt AC-1/AC-8 das ebenfalls, obwohl `confidence` keinen `sms_code`/
  `alert_label` trägt (die ID-verankerten Choke-Points müssen unabhängig
  von Feld-Existenz greifen)?
- `_SELECTABLE_GATE_EXEMPT` komplett leeren (`frozenset()`) — MUSS AC-5
  (Mail-Spalten-Fallback für `temperature_cold`) rot werden lassen. **Korrektur
  (Adversary-Finding F001, 2026-08-10):** AC-3 (Kältealarm) bleibt bei dieser
  Mutation erwartungsgemäß GRÜN — `is_alert_metric_active()` liest
  `_SELECTABLE_GATE_EXEMPT` nicht (s. Korrektur-Hinweis bei AC-3 oben); AC-3
  ist kein Fang für diese Mutation. Der zu AC-3 gehörige Mutationsfall ist
  stattdessen die Tupel-OR-Ersetzung weiter unten.
- Den `remaining`-Fallback in `email/html.py:678-682` entfernen (nur
  `ordered`, kein `+ remaining`) — fängt AC-5 das (temperature_cold
  verschwindet komplett statt nur die Position zu ändern)?
- In `is_alert_metric_active()` die Tupel-OR-Prüfung (Z. 231-234) durch eine
  Glied-für-Glied-Prüfung ersetzen (jedes Element einzeln statt `any(...)`)
  — fängt AC-3 das (der historisch dokumentierte Beinahe-Fehler aus dem
  Code-Kommentar `weather_change_detection.py:210-218`)?

## Changelog

- 2026-08-10: Initial spec created (Epic #1703, Scheibe 3). Implementation-
  Details-Ansatz gegen den aktuellen Code verifiziert, nicht unbesehen aus
  dem Kontext-Dokument übernommen: die dortige Behauptung, die
  Stundentabellen-Frage für `temperature_cold` sei „empirisch geklärt"
  (Abwesenheit = korrekt), erwies sich bei direktem Rendering-Test als
  widerlegt (Dublette „TmpMin"/„Temp" mit identischem Wert) — Ursache ist
  eine zweite, produktiv ungenutzte `dp_to_row()`-Implementierung in
  `email/helpers.py`, die der Kontext-Doku fälschlich als der reale
  Choke-Point galt. AC-6 und die „Known Limitations" wurden entsprechend
  korrigiert, s. Abschnitt „Korrektur gegenüber dem Kontext-Dokument".
