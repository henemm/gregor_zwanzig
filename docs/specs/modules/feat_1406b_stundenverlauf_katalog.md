---
entity_id: feat_1406b_stundenverlauf_katalog
type: feature
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [metric-catalog, compare, hourly, epic-1372, issue-1406, issue-1435]
workflow: feat-1406b-stundenverlauf-katalog
---

<!-- Issue #1406 Scheibe B — Epic #1372 / Etappe E2 von #1435, Dach #1374 -->

# Ortsvergleich-Stundenverlauf: Auswahl UND Auflösung auf den zentralen Wetterkatalog heben (Issue #1406 Scheibe B)

## Approval

- [x] Approved — PO Henning, 2026-08-01 („go")

## Purpose

Der Stundenverlauf im Ortsvergleich bietet heute 10 Wettergrößen an
(Temperatur, gefühlte Temperatur, Wind, Böen, Niederschlag, UV-Index,
Gewitter-Risiko, Regenwahrscheinlichkeit, Sicht, Windrichtung). Der zentrale
Wetterkatalog (`src/app/metric_catalog.py`) führt 24 wählbare Größen — alle
mit einem echten Stundenwert (`dp_field`). Die 14 fehlenden (Luftfeuchtigkeit,
Taupunkt, CAPE, Schneefallgrenze, Niederschlagsart, Bewölkung
gesamt/tief/mittel/hoch, Sonnenstunden, Luftdruck, Nullgradgrenze,
Schneehöhe, Neuschnee) fehlen nicht, weil sie technisch nicht darstellbar
wären — sie fehlen, weil neben dem zentralen Katalog ein eigenes,
zehngliedriges Vokabular gepflegt wird, das inzwischen an **vier** Stellen
existiert (Frontend-Anzeigeliste, Frontend-Übersetzung, Backend-Auflösung,
Renderer-Spaltenliste). Diese Lieferung stellt Bedienfläche UND
Auflösungspfad in einem Zug auf den Katalog um und führt die vier Stellen
auf eine zusammen — sonst wächst genau das Muster, gegen das Epic #1372/
Ticket #1435 antritt. Nach der Umstellung wählt der Nutzer im Stundenverlauf
aus demselben Vorrat wie bei einer Tour.

## Source

> **Schicht-Hinweis:** Full-Stack (anders als die Schwester-Scheibe A/Ausblick,
> die reines Frontend war) — Backend-Resolver und Mail-Prüfer-Allowlist müssen
> zwingend mitgehen, sonst kann der Nutzer 24 Größen anhaken, von denen nur 10
> ankommen (stiller Verlust, Invariante 2 aus Epic #1372). Kein Go-Eingriff
> (`hourly_metrics` liegt unter der opaken `display_config`-Map).

Die vier Vokabular-Orte, die zusammengeführt werden:

- **File:** `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts`
  — **Identifier:** `ALL_HOURLY_METRICS` (10 Einträge), plus die
  Toggle-/Materialisierungs-/Reihenfolge-Funktionen des Moduls
- **File:** `frontend/src/lib/components/compare/compareHourlyCatalogIds.ts`
  — **Identifier:** `HOURLY_KEY_TO_CATALOG_ID` (10 Aliasse, neu mit #1401 B),
  `resolveHourlyMetricLabel()`
- **File:** `src/output/renderers/compare_hourly_metric_ids.py` —
  **Identifier:** `FRONTEND_TO_HOURLY_METRIC_ID` (10 Einträge, bildet auf
  `dp_field`-Namen ab), `resolve_hourly_metrics()`
- **File:** `src/output/renderers/email/compare_html.py` — **Identifier:**
  `HOUR_METRICS` (9 Spalten-Einträge, `:338-347`), `_visible_hour_metrics()`,
  `has_visible_hour_columns()`, `_should_merge_wind_dir()` (`:686-726`)

Zusätzlich im Umfang (Nachweis- bzw. Prüfer-Lücke, kein fünfter
Vokabular-Ort):

- **File:** `src/services/validator_render_service.py` — **Identifier:**
  `render_compare_email_preview()` (`:147-173`), ruft `render_compare_html()`
  heute **ohne** `hourly_metrics` auf und zeigt deshalb immer die volle
  Spaltenmenge, unabhängig von der Auswahl
- **File:** `.claude/hooks/email_spec_validator.py` — **Identifier:**
  `_HOUR_COLUMNS_V2` (`:528-533`, 16 Einträge) — Pflicht-Prüfer-Allowlist,
  muss um die 14 neuen `col_label`-Werte erweitert werden

## Estimated Scope

- **LoC:** ~230–300 Produktivcode + ~250–350 Testcode (neue Ratsche AC-10,
  neuer Trip-Paritätstest AC-7, neuer Vorschau-Paritätstest AC-8, Umschrieb
  von `compare_hourly_layout_controls_structure.test.ts`, Anpassung der
  bestehenden Resolver-/Renderer-Tests) + ~60–120 Doku-Zeilen (diese Spec,
  Kontext-Nachtrag, ADR-Vermerk). **Gesamt ~540–770 Zeilen**; auf den
  250er-Rahmen zählen Produktivcode **und** Tests, `docs/`/`*.md` nicht.
  Der Override auf 600 ist deshalb Pflicht und vorab vereinbart.

  Aufschlüsselung des Produktivteils: Die Alt-Analyse
  (`docs/context/feat-1406b-stundenverlauf-katalog.md`) hatte `compare_html.py`
  mit `~+50/−90` veranschlagt und dabei angenommen, hier sei noch eigene
  Ampel-Logik abzulösen — das ist **nicht mehr richtig**: `_sev_temp` bis
  `_sev_cape` sind seit #1377 B2 bereits Ein-Zeilen-Wrapper um `severity_for()`.
  Es entfällt nur die `_fmt_*`-Formatierhälfte (`:164-232`), plus 14 neue
  `HOUR_METRICS`-Einträge kommen hinzu — die Netto-Reduktion fällt kleiner
  aus als ursprünglich geschätzt. Grobe Verteilung:
  - `compare_hourly_metric_ids.py` (Nachfolger-Resolver, generische
    Katalog-Auflösung statt zehn Literalen): ~+70/−40
  - `compare_html.py` (14 neue `HOUR_METRICS`-Einträge, `_fmt_*`-Hälfte durch
    `format_value(metric_id, value, style="bare")` ersetzt, Enum-Sonderfälle
    Gewitter/Niederschlagsart bleiben): ~+55/−45
  - `frontend/.../CompareHourlyLayoutControls.svelte` (Grundauswahl auf
    `groupCompareCatalog` umgestellt): ~+50/−25
  - `compareHourlyMetricDefs.ts` (135 Zeilen) + `compareHourlyCatalogIds.ts`
    (42 Zeilen): entfallen weitgehend; die Toggle-/Materialisierungs-/
    Reihenfolge-Hilfsfunktionen werden geprüft, ob sie unverändert nach
    `compareMetricOrder.ts` passen (dort existieren mit
    `materializeOutlookMetricKeys`/`toggleOutlookMetricKeyFromState` bereits
    strukturell identische Funktionen für den Ausblick) — best case reiner
    Wegfall, worst case ~20 Zeilen Adapter
  - `validator_render_service.py` (Vorschau-Lücke schließen, `hourly_metrics`
    durchreichen): ~+10
  - `.claude/hooks/email_spec_validator.py` (`_HOUR_COLUMNS_V2` um 14
    `col_label`-Werte erweitern): ~+15

  **Sollte die tatsächliche Umsetzung über 250 Kern-LoC hinausgehen** (nach
  heutiger Schätzung wahrscheinlich, da vier Vokabular-Stellen
  zusammengeführt werden, nicht nur eine Liste ausgetauscht wird), ist vor
  Implementierungsbeginn `workflow.py set-field loc_limit_override 600` zu
  setzen — der Rahmen ist laut Auftrag vorab auf 600 vereinbart, die Anfrage
  selbst ersetzt das nicht (kein LoC-Override ohne ausdrückliche Freigabe).
- **Files:** 4 Kern-Produktivdateien geändert
  (`compare_hourly_metric_ids.py`, `compare_html.py`,
  `CompareHourlyLayoutControls.svelte`, `validator_render_service.py`), 1
  Prüfer-Datei erweitert (`email_spec_validator.py`), 2 Frontend-Dateien
  entfallen bzw. schrumpfen fast vollständig (`compareHourlyMetricDefs.ts`,
  `compareHourlyCatalogIds.ts`); mehrere bestehende Tests angepasst (s.
  Test-Plan), mindestens 2 neue Testdateien (Ratsche, Vorschau-Parität).
- **Effort:** medium — die einzelnen Umbauten sind für sich genommen klein,
  der Aufwand steckt in der widerspruchsfreien Zusammenführung von vier
  Stellen plus dem lückenlosen Bestandsschutz für Alt-Presets.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py::get_all_metrics()`/`get_metric()` | READ | Liefert alle 24 selektierbaren Größen inkl. `dp_field`, `col_label`, `decimals`, `display_thresholds` — einzige Quelle für die Erweiterung |
| `src/output/metric_format.py::format_value()`/`severity_for()` | READ (neue Konsumenten) | Bereits generische, katalog-getriebene Formatierung/Ampel (Issue #1214/#1377 B2); ersetzt die `_fmt_*`-Hälfte in `compare_html.py` für alle Größen außer den beiden Enum-Sonderfällen |
| `frontend/.../weather-metrics-tab/compareAggregationGrouping.ts::groupCompareCatalog()` (#1411) | function (unverändert) | Gruppiert einen flachen Compare-Katalog nach `metric_id`; für den Stundenverlauf entartet jede Gruppe strukturbedingt zum Ein-Options-Zweig (keine Mehrfach-Auswertung je Rohwert) |
| `frontend/.../weather-metrics-tab/AggregationMetricRow.svelte` (#1411/#1406a) | component (unverändert) | Ein-Options-Zweig wird für die Stundenverlauf-Checkbox mitgenutzt, analog Übersicht/Ausblick |
| `frontend/.../compareMetricOrder.ts::materializeOutlookMetricKeys()`/`toggleOutlookMetricKeyFromState()` | function (Wiederverwendungs-Kandidat) | Strukturell identische Materialisierungs-/Toggle-Semantik wie die heutigen `compareHourlyMetricDefs.ts`-Funktionen — vor dem Neubau prüfen, ob direkte Wiederverwendung möglich ist (Trip/Compare-Teilungs-Invariante gilt sinngemäß auch zwischen Ausblick und Stundenverlauf) |
| `email/helpers.py::should_merge_wind_dir()` (Trip) | Muster (READ-only, kein Import) | Referenz-Semantik für den Windrichtungs-Merge; Compare hat mit `_should_merge_wind_dir()` bereits eine eigene, äquivalente Funktion — bleibt unverändert bestehen, wird nicht ersetzt |
| `comparison.py::render_compare_plain()` | READ (Verbraucher, unverändert) | Importiert `_visible_hour_metrics`/`_should_merge_wind_dir`/`derive_row_labels` bereits aus `compare_html.py` — kein zweiter blinder Fleck HTML-vs-Klartext, muss aber nach der Erweiterung weiterhin dieselbe Quelle lesen |
| `src/services/scheduler_dispatch_service.py:373-378`, `report_config_resolver.py:230,254,278` | READ (Versandpfad, unverändert) | Reichen `hourly_metrics` bereits lückenlos vom Preset bis zum Renderer durch — diese Scheibe ändert an der Signatur nichts |
| `.claude/hooks/briefing_mail_validator.py` | Test/Gate (Renderer-Commit-Gate #811) | Pflichtlauf vor jedem Commit an `compare_html.py`; Reihenfolge beachten: `email_spec_validator.py`-Erweiterung MUSS vor dem ersten produktiven Testversand mit neuen Spalten vorliegen |

## Implementation Details

### 1. Backend-Resolver wird generisch statt eine zehnte Literal-Kopie

`compare_hourly_metric_ids.py::FRONTEND_TO_HOURLY_METRIC_ID` wird um die 14
fehlenden Katalog-IDs erweitert — nicht als zehn weitere Handeinträge,
sondern indem `resolve_hourly_metrics()` primär `get_all_metrics()` befragt
(Katalog-ID → `dp_field`) und nur für die **zehn historischen Kurzschlüssel**
(`temp_c`, `wind_chill_c`, `wind_kmh`, `gust_kmh`, `precip_mm`, `uv_index`,
`thunder_level`, `pop_pct`, `visibility_m`, `wind_dir_deg`) eine feste
Alias-Tabelle auf ihre Katalog-ID bleibt. Ein gespeicherter Wert kann damit
entweder ein alter Kurzschlüssel oder eine Katalog-ID direkt sein — beide
lösen auf. Nicht auflösbare Werte werden weiterhin sichtbar verworfen
(Log-Warnung, unverändertes Muster aus #1361 Befund 3), nicht still.

### 2. Vier Vokabular-Orte werden zu einem

- `compare_hourly_metric_ids.py` wird die alleinige Backend-Quelle für
  Schlüssel → Katalog-ID/`dp_field`.
- `compareHourlyCatalogIds.ts` (Frontend-Übersetzung, 42 Zeilen) entfällt —
  ihre Alias-Tabelle war bereits eine zeichengleiche Kopie der einen Hälfte
  von Punkt 1 und wird durch denselben Katalog-Bezug ersetzt, den Übersicht/
  Ausblick bereits nutzen (der Stundenverlauf-Auswahlblock zeigt künftig
  direkt die Katalog-Labels, keine separate Übersetzungstabelle mehr).
- `compareHourlyMetricDefs.ts::ALL_HOURLY_METRICS` (10 Einträge) entfällt als
  eigenständiges Vokabular; die verbleibenden reinen Funktionen (Toggle,
  Materialisierung, Reihenfolge) werden entweder direkt durch die
  äquivalenten Ausblick-Funktionen in `compareMetricOrder.ts` ersetzt oder
  — falls das Merge-Signal-Sonderverhalten (`wind_dir_deg`, `defaultOff`)
  eine eigenständige Fassung erzwingt — in dieselbe Datei überführt, mit
  Begründung im Code-Kommentar, warum kein direkter Reuse möglich war.
- `HOUR_METRICS` in `compare_html.py` bleibt die einzige Renderer-seitige
  Spaltenliste (HTML **und** Klartext lesen sie bereits gemeinsam), wächst
  von 9 auf 24 Einträge.

### 3. Formatierung: generischer Aufruf statt Einzel-`_fmt_*`

Für alle Größen außer den beiden Enum-Typen (`thunder_level`, `precip_type`)
ersetzt `format_value(metric_id, value, style="bare")` (`metric_format.py`)
die bisherigen `_fmt_deg`/`_fmt_kmh`/`_fmt_rain`/`_fmt_uv`/`_fmt_pop`/
`_fmt_visibility`-Einzelfunktionen — `style="bare"` liefert die reine Zahl
ohne Einheiten-Suffix, weil die Einheit bereits in der Einheiten-Legende
unter der Stundentabelle steht (bestehendes Muster, s.
`_fmt_visibility`-Kommentar). Die Ampel-Seite ruft weiterhin `severity_for()`
direkt auf (bereits generisch, unverändert). `_fmt_thunder`/`_sev_thunder`
und `_fmt_precip_type` bleiben als benannte Ausnahmen bestehen — Enum-Werte
lassen sich nicht generisch runden/formatieren (analog `_fmt_thunder`-Vorbild
für den Alarm-Renderer).

### 4. Grundauswahl: gruppiertes Muster statt flacher Zehnerliste

`CompareHourlyLayoutControls.svelte` stellt den oberen Auswahl-Block auf
`groupCompareCatalog()` + `AggregationMetricRow` um — dasselbe Muster wie
Übersicht (#1411) und Ausblick (#1406 Scheibe A). Da der Stundenverlauf
strukturell keine Mehrfach-Auswertung je Größe kennt (ein Rohwert pro
Stunde hat nur eine Darstellung), nimmt jede Gruppe immer den
Ein-Options-Zweig — die Umstellung ist einfacher als bei Übersicht/Ausblick,
liefert aber dieselbe Konsistenz: eine Zeile je der 24 Katalog-Größen, aus
derselben Katalogquelle (`GET /api/compare/metrics`) wie die anderen beiden
Blöcke, statt einer vierten, eigenständig geladenen/übersetzten Liste. Der
darunterliegende Reihenfolge-Block (`WeatherV2Reihenfolge`, ADR-0024) bleibt
unverändert — er ist bereits der geteilte Baustein und nicht Teil dieser
Änderung.

### 5. Windrichtung bleibt Compare-eigene, aber unveränderte Sonderregel

`_should_merge_wind_dir()` in `compare_html.py` bleibt bestehen — sie ist
kein Vokabular-Duplikat im Sinne dieser Scheibe (sie prüft nur Mitgliedschaft
in der Auswahl, keine Formatierung/Übersetzung), sondern eine
Renderer-Regel, strukturell analog zu `should_merge_wind_dir()` im Trip.
`wind_dir_deg`/`wind_direction_deg` bleibt ein reines Merge-Signal ohne
eigene `HOUR_METRICS`-Spalte.

### 6. Vorschau-Lücke schließen

`render_compare_email_preview()` (`validator_render_service.py:147-173`)
bekommt ein optionales `hourly_metrics`-Feld im Request-Body und reicht es an
`render_compare_html()` durch — analog zum bereits vorhandenen
`hourly_enabled`-Parameter zwei Zeilen darüber. Ohne diese Änderung würde der
eigene Nachweis dieser Scheibe (AC-8) am falschen Endpunkt vorbeiprüfen
(Muster aus #1435 E3b: `build_token_line()` ohne `profile=`).

### 7. Prüfer-Allowlist erweitern

`_HOUR_COLUMNS_V2` (`email_spec_validator.py:528-533`) bekommt die 14 neuen
`col_label`-Werte aus dem Katalog hinzugefügt (Werte gegen `metric_catalog.py`
verifiziert, s. Tabelle unten) — die frühere Blockade durch eine
Parallel-Sitzung (#1420) ist aufgelöst, diese Erweiterung ist jetzt Teil des
Pflichtumfangs dieser Scheibe, nicht mehr ausgeklammert.

| Katalog-ID | `col_label` |
|---|---|
| `humidity` | `Humid` |
| `dewpoint` | `Cond°` |
| `cape` | `CAPE` |
| `snowfall_limit` | `SnowL` |
| `precip_type` | `PType` |
| `cloud_total` | `Cloud` |
| `cloud_low` | `CldLow` |
| `cloud_mid` | `CldMid` |
| `cloud_high` | `CldHi` |
| `sunshine` | `Sun` |
| `pressure` | `hPa` |
| `freezing_level` | `0°Line` |
| `snow_depth` | `SnowH` |
| `fresh_snow` | `NewSn` |

## Expected Behavior

- **Input:** Ein Nutzer öffnet im Ortsvergleich-Editor den Stundenverlauf-Block
  und wählt zusätzlich zu den zehn bisherigen Größen z. B. „Luftfeuchtigkeit"
  aus; speichert.
- **Output:** Die nächste Vergleichs-Mail (HTML und Klartext) zeigt für jeden
  Ort eine zusätzliche Spalte „Humid" mit dem stündlichen Feuchtewert. Ein
  Vergleich, der nie angefasst wurde, zeigt weiterhin exakt die bisherigen
  Spalten in der bisherigen Reihenfolge.
- **Side effects:** Telegram und SMS bleiben unverändert (kennen keinen
  Stundenverlauf). Die Vorschau im Editor zeigt ab jetzt dieselben Spalten
  wie die zugestellte Mail.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet im Ortsvergleich-Editor den Stundenverlauf
  / When der Auswahl-Block darüber lädt / Then sieht er für jede der 24
  Katalog-Größen eine Zeile, dargestellt über denselben gruppierten Baustein
  wie bei Übersicht und Ausblick — nicht mehr die alte flache Liste mit nur
  10 Einträgen.
  - Test: AST-Struktur-Test (Nachfolger von
    `compare_hourly_layout_controls_structure.test.ts`) weist nach, dass der
    Auswahl-Block über `groupCompareCatalog(...)` iteriert statt über
    `ALL_HOURLY_METRICS`, und dass alle 24 Katalog-Größen als Gruppe
    auftauchen (Vakuum-Schutz: Anzahl explizit >0 und ==24 behauptet).

- **AC-2:** Given ein Nutzer wählt im Stundenverlauf eine bisher nicht
  angebotene Größe (z. B. Luftfeuchtigkeit) zusätzlich aus / When die
  Vergleichs-Mail zugestellt wird / Then erscheint die Größe als eigene
  Spalte in der Stundentabelle — sowohl im HTML-Teil als auch im
  Klartext-Teil derselben Mail, mit übereinstimmenden Werten.
  - Test: echter Staging-Versand (s. „Nachweisführung"), IMAP-Abruf,
    Zahl-für-Zahl-Vergleich der neuen Spalte zwischen HTML- und
    Klartext-Teil.

- **AC-3:** Given ein Nutzer hat eine Größe im Stundenverlauf abgewählt /
  When die Mail erneut zugestellt wird / Then fehlt die zugehörige Spalte
  wieder; wählt er alle Größen ab, entfällt die Stundentabelle vollständig
  (keine Zeit-only-Tabelle) — heutiges Verhalten über
  `has_visible_hour_columns()` bleibt erhalten.
  - Test: bestehender `tests/unit/test_compare_hourly_metrics_config.py`
    (bzw. Nachfolgedatei, Name nach Verhalten) für die Leerauswahl-Regel,
    ergänzt um mindestens eine der 14 neuen Größen als Ab-/Anwahlfall.

- **AC-4 (Bestandsschutz):** Given ein Ortsvergleich wurde vor dieser Änderung
  mit den alten Kurzschlüsseln gespeichert (z. B. `temp_c`, `wind_kmh`) / When
  er nach der Umstellung geladen und eine Mail dafür erzeugt wird / Then zeigt
  die Mail exakt dieselben Spalten wie vor der Umstellung — keine Migration,
  kein stiller Spaltenverlust, kein automatisches Hinzufügen der 14 neuen
  Größen.
  - Test: Roundtrip-Test mit Fixture im Alt-Format (10 Kurzschlüssel) gegen
    `resolve_hourly_metrics()` vor und nach der Umstellung — identisches
    Ergebnis.

- **AC-5:** Given ein Nutzer hat für Stundenverlauf, Übersicht und Ausblick
  jeweils eine eigene Reihenfolge/Auswahl eingestellt / When alle drei
  Bereiche derselben Mail gerendert werden / Then bleibt jede Reihenfolge
  unabhängig von den anderen beiden — die Zusammenführung der
  Vokabular-Stellen ändert nichts an der bestehenden Trennung der drei
  Speicherfelder (`hourly_metrics`, `active_metrics`, `outlook_metrics`).
  - Test: Fixture mit drei unterschiedlichen Reihenfolgen je Bereich; Mail
    zeigt alle drei unverändert getrennt.

- **AC-6:** Given eine Stundentabelle mit aktiver Windrichtung UND aktiver
  Wind-Spalte / When die Zeile gerendert wird / Then erscheint die
  Windrichtung weiterhin als Kompasstext in derselben Zelle wie der
  Wind-Wert — keine eigene Spalte, identisch zum bisherigen Verhalten und zur
  Trip-Mail-Semantik (`should_merge_wind_dir`).
  - Test: bestehender Merge-Test für `_should_merge_wind_dir()` bleibt grün,
    unverändert; ergänzend eine Zeile mit einer der 14 neuen Größen daneben
    aktiv, um zu belegen, dass der Merge nicht durch die Erweiterung gestört
    wird.

- **AC-7 (Trip unberührt):** Given eine Tour (kein Ortsvergleich) mit
  Stundenverlauf in der Mail / When sie nach dieser Änderung gerendert wird /
  Then ist sie zeichengleich zu einer Mail vor der Änderung — diese Scheibe
  ändert `email/helpers.py`/`trip_report.py` nicht, Compare ruft weiterhin nur
  `format_value`/`severity_for` auf, importiert aber nicht die
  Trip-Orchestrierung (`dp_to_row`/`extract_hourly_rows`).
  - Test: eigener Paritätstest (Vorbild `tests/tdd/test_trip_outlook_parity.py`
    aus Scheibe A) gegen ein bestehendes Golden — bleibt grün, ohne dass das
    Golden angepasst wird.

- **AC-8 (Vorschau-Parität):** Given ein Nutzer betrachtet im Editor die
  Mail-Vorschau mit einer eingeschränkten Stundenverlauf-Auswahl / When die
  Vorschau gerendert wird / Then zeigt sie exakt dieselben Spalten wie die
  zugestellte Mail für dieselbe Auswahl — nicht mehr pauschal alle Spalten.
  - Test: Aufruf von `render_compare_email_preview()` mit gesetztem
    `hourly_metrics`-Feld; Spaltenmenge im Ergebnis-HTML entspricht der
    Auswahl, nicht der vollen Liste.

- **AC-9 (Pflicht-Prüfer nimmt korrekte Mail ab):** Given eine zugestellte
  Vergleichs-Mail enthält eine oder mehrere der 14 neu wählbaren Spalten /
  When `email_spec_validator.py` gegen diese Mail läuft / Then meldet er
  Exit 0 (keine „unbekannte Spalte"-Ablehnung); eine Mail mit einer
  erfundenen Spalte wird weiterhin abgelehnt.
  - Test: Validator-Lauf gegen die in AC-2 erzeugte Staging-Mail (Exit 0) +
    bestehender Negativtest mit einer nicht existierenden Spaltenbezeichnung
    (Exit ≠ 0, unverändert).

- **AC-10 (Ratsche gegen Nachwachsen):** Given ein neuer vierter/fünfter
  Vokabular-Ort für die Zuordnung Stundenverlaufs-Schlüssel → Katalog-Größe
  entsteht künftig versehentlich wieder / When der Ratschen-Test läuft /
  Then schlägt er fehl und benennt die zusätzliche Fundstelle konkret — er
  behauptet dabei selbst die Anzahl der geprüften Quellen (>0) und die
  erwartete Anzahl (genau 1), damit ein Regex-Wächter, der nichts findet,
  nicht fälschlich grün bleibt.
  - Test: neue Datei, s. „Wirksamkeitsnachweis der Ratsche".

- **AC-11 (Sonnenschein sichtbar ausgenommen):** Given ein Nutzer öffnet die
  Grundauswahl des Stundenverlaufs / When er die Liste durchsieht / Then
  erscheint „Sonnenstunden" dort **mit sichtbarer Begründung nicht
  anwählbar** — nicht kommentarlos fehlend. Der Hinweis nennt den Grund
  („stündlich nur als Einstrahlung verfügbar") und verweist auf Bewölkung
  und UV-Index als die Größen, die dieselbe Frage stündlich beantworten.
  Wird sie dennoch über gespeicherte Daten erzwungen, erzeugt sie **keine**
  Stundenspalte.
  - Test: Struktur-Test der Grundauswahl (Eintrag vorhanden, Zustand
    „nicht anwählbar", Begründungstext nicht leer) + Renderer-Test
    (`sunshine` in `hourly_metrics` ⇒ keine zusätzliche Spalte).

  **Nachtrag nach Freigabe — PO-Entscheid 2026-08-01.** Die ursprüngliche
  Analyse hielt fest, es gebe „keine Kategorie *technisch nicht
  darstellbar*". Das stimmt für 23 der 24 Größen. `sunshine` ist die
  Ausnahme: Der Katalog führt sie als **Tagesgröße** (`unit="h"`,
  `default_aggregations=("sum",)`, `summary_fields={"sum": "sunny_hours"}`),
  ihr `dp_field` ist aber `dni_wm2` — die stündliche **Direkteinstrahlung in
  W/m²**, aus der die Sonnenstunden erst berechnet werden. Der
  Katalogeintrag ist damit **nicht fehlerhaft**; fehlerhaft wäre nur, den
  Rohwert stündlich unter der Beschriftung „Sonnenstunden" mit Einheit „h"
  auszugeben.

  Fachliche Begründung der Ausnahme: Die Frage, die die stündliche
  Einstrahlung beantwortet (wie stark brennt die Sonne gerade), beantworten
  **Bewölkung** und **UV-Index** bereits — beide sind stündlich vorhanden und
  für Tourenentscheidungen unmittelbar lesbar. Eine dritte Spalte mit
  „340 W/m²" brächte in einer Kurzübersicht keinen Zusatznutzen und schüfe
  eine Doppeldeutigkeit: dieselbe Größe hieße in der Tagesübersicht „Sonne
  in Stunden" und im Stundenverlauf „Watt pro Quadratmeter".

  **Folge für die Zahlen dieser Spec:** 24 Katalog-Größen − 1 Merge-Signal
  (Windrichtung, erzeugt nie eine eigene Spalte) − 1 ausgenommene
  (`sunshine`) = **22 Wert-Spalten** plus „Zeit". Wo diese Spec oder der
  Kontext von 23 oder 24 Spalten spricht, gilt 22.

  Eine spätere Aufnahme der Einstrahlung als eigenständige Größe (eigener
  Name, eigene Einheit W/m²) bleibt möglich, ist aber **nicht Teil dieser
  Lieferung**.

## Wirksamkeitsnachweis der Ratsche

**Prüfdatum: 2026-10-30** (Regel-Budget, CLAUDE.md).

Erfahrung aus #1435 E3a: zwei Wächter waren grün, ohne je etwas geprüft zu
haben. Die Ratsche aus AC-10 gilt deshalb erst als geliefert, wenn folgender
Nachweis erbracht und im PR/Commit protokolliert ist:

1. In einer lokalen, nicht committeten Kopie wird absichtlich eine zweite,
   von `compare_hourly_metric_ids.py` abweichende Mapping-Stelle angelegt
   (z. B. ein zusätzliches, lokal in `CompareHourlyLayoutControls.svelte`
   hartcodiertes Alias-Objekt für eine der 24 Größen).
2. Der Ratschen-Test wird gegen diese verfälschte Kopie ausgeführt.
3. Die Ausgabe wird protokolliert und muss zeigen: (a) der Test schlägt fehl
   (nicht grün, nicht übersprungen), (b) die Fehlermeldung benennt die
   zusätzliche Fundstelle konkret (Datei, nicht nur „assertion failed").
4. Die Verfälschung wird danach zurückgenommen; der reguläre, korrekte Code
   läuft grün.
5. **Ergänzt nach Adversary-Befund F002 (2026-08-01):** derselbe Nachweis wird
   zusätzlich mit dem **verteilten** Vokabular geführt — jedes Alias-Paar in
   einem eigenen Objekt-Literal, einmal innerhalb einer Datei und einmal über
   fünf verschiedene Produktivdateien. Beide Fälle müssen rot sein und jede
   Fundstelle mit Datei und Zeile benennen. Der Gegenbeweis gehört dazu: die
   legitimen Alarm-Nachbarn (`utils/alertMetricCatalogIds.ts`,
   `molecules/AlertRow.svelte`) bleiben unverändert grün.
6. **Ergänzt nach Adversary-Befund F004 (2026-08-01):** derselbe Nachweis noch
   einmal mit dem Vokabular in **berechneter Schreibweise**
   (`{ ["temp_c"]: "temperature", … }`) — rot mit Datei und Zeile, danach nach
   Rücknahme wieder grün.

Ohne diesen protokollierten Nachweis gilt die Ratsche als nicht abgenommen,
unabhängig davon, ob sie „grün" ist.

## Nachweisführung

Der Nachweis läuft über den **echten Versandpfad** auf Staging, nicht über
den Vorschau-Endpunkt — auch nachdem dessen Lücke (AC-8) geschlossen ist,
weil der Pflicht-Prüfer (`email_spec_validator.py`) ausschließlich eine
tatsächlich per IMAP zugestellte Mail liest, keine Vorschau-Antwort:

1. Ein Test-Vergleich mit erweiterter Stundenverlauf-Auswahl (mindestens eine
   der 14 neuen Größen zusätzlich zu einer bestehenden) wird angelegt.
2. **Ein** Testversand, Empfänger ausschließlich `gregor-test@henemm.com`
   (kein Sammelversand über echte Touren — Kontingent-Schonung, #1329).
3. IMAP-Abruf der zugestellten Mail.
4. `.claude/hooks/email_spec_validator.py` gegen die zugestellte Mail —
   Exit 0 ist Pflichtbedingung für „E2E bestanden" (AC-9).
5. Zahl-für-Zahl-Vergleich der neuen Spalte zwischen HTML- und Klartext-Teil
   sowie mit der Vorschau-Antwort (AC-8) — nicht nur „Feld hat sich
   geändert".
6. Erst danach die Vorschau-Parität (AC-8) separat über den Preview-Endpunkt
   prüfen (kostet kein zusätzliches Kontingent, da ohne Live-Wetterdaten
   stubbar).

## Known Limitations

- **Telegram und SMS kennen keinen Stundenverlauf.** `hourly_metrics`
  erreicht ausschließlich die E-Mail — unverändert seit #1106.
- **Eine Mail mit vielen gewählten Größen wird breit** (bis zu 24 Spalten ×
  Orte × Stunden). Die Auswahl liegt beim Nutzer, es wird nichts automatisch
  hinzugefügt — die Folge wird hier ausdrücklich benannt statt verschwiegen:
  eine E-Mail mit allen 24 Größen für mehrere Orte kann auf schmalen
  Bildschirmen/in manchen Mail-Clients unhandlich werden. Kein Teil dieser
  Lieferung begrenzt die Anzahl aktiv gewählter Größen.
- **Compare ruft `format_value`/`severity_for` nur AUF, importiert aber nicht
  die Tour-Orchestrierung** (`dp_to_row`/`extract_hourly_rows` aus
  `email/helpers.py`) — diese erwarten ein volles
  `UnifiedWeatherDisplayConfig`, das der Vergleich nicht hat. Geteilt ist die
  Formel, nicht die Aufrufsignatur. Ein künftiger Versuch, Compare direkt auf
  die Trip-Orchestrierung umzustellen, ist eine eigene, hier nicht
  gelieferte Änderung mit Regressionsrisiko für die Tour-Mail.
- **`groupCompareCatalog()` entartet für den Stundenverlauf strukturell immer
  zum Ein-Options-Zweig** — der Baustein bringt hier keine funktionale
  Mehrfachauswahl (wie bei Temperatur im Ausblick), sondern ausschließlich
  die Konsolidierung der Datenquelle. Kein neues Bedienelement für den
  Nutzer, nur eine andere interne Herkunft der Liste.
- **Die Frontend-Ratsche (AC-10) sieht nur Objekt-Literale — und das Register
  ihrer Ausnahmen ist ihre eigentliche Grenze.** Nach Adversary-Befund F002
  (2026-08-01) zählt jedes einzelne Alias-Paar als Fund; die frühere Schwelle
  „mindestens zwei Paare in EINEM Literal" ließ sich umgehen, indem man das
  vollständige Vokabular auf lauter Ein-Paar-Literale verteilte — auch über
  mehrere Dateien hinweg. Das ist gefangen (Nachweise im Workflow-Artefakt).
  Was weiterhin **nicht** gefangen wird, ausdrücklich benannt:
  - Ein Vokabular, das **nicht als Objekt-Literal** geschrieben ist:
    `new Map([['temp_c','temperature']])`, Tupel-Arrays,
    `Object.fromEntries(...)` oder `switch`/`if`-Ketten.
  - Berechnete Schlüssel sind **gefangen**, solange der Ausdruck wörtlich
    dasteht (`{ ["temp_c"]: "temperature" }` — Adversary-Befund F004,
    2026-08-01). Offen bleibt nur der Fall, in dem der Schlüssel erst zur
    Laufzeit entsteht (`{ [KONST]: "temperature" }`, Funktionsaufruf,
    Verkettung).
  - Zielwerte, die nicht der Register-Schreibweise folgen (`^[a-z][a-z0-9_]*$`)
    — z. B. camelCase oder Anzeigetexte. Bewusste Grenze: sonst schlüge jede
    Beschriftungs-Tabelle an.
  - Dateien unter `__tests__/` sowie `*.test.ts`/`*.spec.ts` werden nicht
    gescannt (sonst meldete sich der Wächter selbst).
  - Das Register `BEKANNTE_KOLLISIONEN` (heute genau zwei Einträge, beide
    `thunder_level` aus dem Alarm-Vokabular) ist technisch umgehbar, indem man
    eine neue Fundstelle mit erfundener Begründung einträgt. Dagegen hilft nur
    das Review — die Ratsche macht den Vorgang aber **sichtbar** statt
    statistisch zu verdecken, und tote Register-Einträge fallen durch einen
    eigenen Test auf.
- **Bestehender Struktur-Test `compare_hourly_layout_controls_structure.test.ts`
  bricht strukturell**, weil er heute explizit die Schleife
  `{#each ALL_HOURLY_METRICS as metric}` nachweist — er wird durch diese
  Scheibe umgeschrieben (nicht ersatzlos gelöscht), analog dem Vorbild
  `compare_outlook_metric_selection_structure.test.ts` aus Scheibe A.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Kein neuer Architektur-Grundsatz im Sinne der
  CLAUDE.md-ADR-Trigger (Kanäle, Provider, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie unberührt). Es ist eine Fortsetzung bereits
  etablierter Praxis: Registerherrschaft über Renderer-/Editor-Vokabulare
  (fortgeführt aus #1214/#1373/#1401/#1406a/#1411 sowie #1435 E1a/E1b/E3a/
  E3b) wird hier auf den letzten verbliebenen Compare-eigenen
  Vokabular-Bereich angewandt. `ADR-0024` (geteilter Sortier-Baustein) bleibt
  unberührt, da der Reihenfolge-Block dieser Scheibe nicht angefasst wird.

## Test-Plan

Kern-Schicht (deterministisch), Testdateien nach Verhalten benannt:

| AC | Testfall |
|----|----------|
| AC-1 | AST-Struktur-Test (Nachfolger `compare_hourly_layout_controls_structure.test.ts`): Iteration über `groupCompareCatalog(...)`, 24 Gruppen nachgewiesen |
| AC-2, AC-9 | Staging-Versand + IMAP + `email_spec_validator.py`, s. „Nachweisführung" |
| AC-3 | Unit-Test Leerauswahl-Regel (`has_visible_hour_columns`), erweitert um eine der 14 neuen Größen |
| AC-4 | Roundtrip-Test `resolve_hourly_metrics()` mit Alt-Format-Fixture, vor/nach zeichengleich |
| AC-5 | Fixture-Test: drei unabhängige Reihenfolgen (Stundenverlauf/Übersicht/Ausblick) bleiben getrennt |
| AC-6 | bestehender `_should_merge_wind_dir`-Test bleibt grün + eine Zeile mit neuer Größe daneben |
| AC-7 | neuer Paritätstest (Vorbild `test_trip_outlook_parity.py`) gegen unverändertes Golden |
| AC-8 | Aufruf `render_compare_email_preview()` mit `hourly_metrics`, Spaltenmenge = Auswahl |
| AC-10 | neue Ratschen-Testdatei, s. „Wirksamkeitsnachweis der Ratsche" |

**Renderer-Commit-Gate (#811):** greift, sobald `compare_html.py` gestaged
wird. Reihenfolge: erst `_HOUR_COLUMNS_V2`-Erweiterung committen/verifizieren
(unabhängig prüfbar, kein Mailversand nötig), dann `email_spec_validator.py`
+ `briefing_mail_validator.py` grün gegen eine Mail mit den neuen Spalten,
erst dann Commit an `compare_html.py`.

## Changelog

- 2026-08-01: Initial spec created — Issue #1406 Scheibe B / #1435 Etappe E2.
  Basiert auf `docs/context/feat-1406b-stundenverlauf-katalog.md` inkl.
  Nachtrag vom 2026-08-01 (vier Vokabular-Orte statt drei, Beschriftungen
  bereits aus dem Register, Ampel-Schätzung korrigiert, Vorschau-Lücke
  aufgenommen). Alle `col_label`-Werte gegen den aktuellen Stand von
  `src/app/metric_catalog.py` verifiziert, nicht geraten.
