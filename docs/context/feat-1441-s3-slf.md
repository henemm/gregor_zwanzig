# Context: feat-1441-s3-slf

## Request Summary
#1441 Scheibe S3: den amtlichen Schweizer Lawinen-Lagebericht des SLF als weitere Quelle neben
avalanche.report (S1) anbinden — gleiche Darstellung in allen vier Kanälen und im Ortsvergleich,
inklusive der Entwarnung aus S2. PO-Entscheid 16.10.2026: SLF bleibt in #1441, Issue offen bis SLF live.

## Live-Messung der SLF-Schnittstelle (16.10.2026)
- `GET https://aws.slf.ch/api/bulletin/caaml/de/json` → 200 `{"bulletins":[]}` (außerhalb der Saison leer, kein 404).
- `GET …/caaml/de/json?activeAt=2026-03-01T08:00:00Z` → 200, 29 KB, 6 Bulletins, 132 Regionen (`CH-xxxx`),
  `validTime` 07:00Z–16:00Z, `nextUpdate` 16:00Z (SLF hat Morgen- und Abend-Ausgabe).
- Kein API-Key. Swagger-UI unter `https://aws.slf.ch/api/warningregion/geojson` (liefert HTML, keine Geometrie).
- `…/caaml/de/geojson?activeAt=…` existiert ebenfalls (FeatureCollection mit Bulletin-Properties).
- **Format-Unterschiede zu avalanche.report (relevant für den Parser):**
  - `dangerRatings[]` tragen **keine** `elevation` — die Höhengrenze steht nur in `avalancheProblems[].elevation`
    (z. B. `lowerBound: 2000`). S1-Parser (`_elevation` auf dem Rating) würde „Stufe 3" ohne Höhe zeigen.
  - `dangerRatings[].customData.CH.subdivision` = `minus|neutral|plus` (amtliche Feinstufe „3-", „3+").
  - Problem-`customData.CH.coreZoneText` liefert amtlichen Kerntext, z. B. „Gefahrenstufe "erheblich" (3-) an allen Expositionen über 2000m."
  - Kein Link-/Quellenfeld im Bulletin → Bulletin-URL muss konstruiert werden (SLF/White-Risk-Seite).
  - Problemtyp-Vokabular identisch (CAAML6: `persistent_weak_layers`, `gliding_snow`, …).
- **Regionsumrisse:** `https://regions.avalanches.org/micro-regions/CH_micro-regions.geojson.json` → 200, 156 KB,
  149 Features (`properties.id` = `CH-xxxx`, MultiPolygon, CRS84) — gleiche EAWS-Quelle (CC0) wie die S1-Dateien.
  149 Umrisse vs. 132 Regionen im Bulletin 01.03. → nicht jede Mikroregion erscheint in jedem Bulletin.
- Rohdaten der Messung: Scratchpad `slf/latest.json` (Bulletin 2026-03-01), `slf/f_914c20.json` (CH-Umrisse) — in
  `/40` als aufgezeichnete Fixtures nach `tests/fixtures/…` übernehmen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/avalanche_report.py` | S1-Quelle: Tabelle `AVALANCHE_REGION_TABLE` :74 (`AvalancheRegionConfig` :57, `_row()` :65 fest auf avalanche.report-URL), Parser `_rated` :133, `_carrier` :112, `_elevation` :88, `_problems` :124, `parse_region_alert` :158, `RegionMapper` :216, `covers()` :222 (nur BBox), `_candidates` :247, Fehlersemantik 404/abgelaufen → leer + `mark_not_covered`, 5xx → unavailable, `fetch` :269 (höchste Stufe, dann kleinste dedup_id). `BULLETIN_URL` hart auf avalanche.report. |
| `src/services/official_alerts/data/` + `README.md:20-31` | Regionsdateien `avalanche_regions_{key}.geojson.json` (EAWS-Mikroregionen). Noch **keine** `CH-`-Datei. |
| `src/services/official_alerts/__init__.py:7,56,74` | Registry; avalanche_report als letzte Quelle (Kommentar :53-55, „zuerst registriert gewinnt"). |
| `src/services/official_alerts/region_mapper.py`, `geo_ray_cast.py` | `regions_at` liefert alle Treffer sortiert; Ray-Cast ohne Kantentoleranz, deterministisch. |
| `src/services/official_alerts/warn_egress.py` | `cached_fetch` (:396, `not_covered_statuses`, TTL `WARN_SUCCESS_TTL` 1800 s), Host-Logging. |
| `src/app/egress_guard.py:51-55`, `internal/egress/inventory.go:40-43` | Host-Allowlist/Inventar — `aws.slf.ch` eintragen; Drift-Test `tests/test_egress_inventory_drift.py`. |
| `src/output/renderers/alert/official_alerts.py:105-131,181` | `_SOURCE_LABELS` (Quellenlabel je `"<prefix>:<key>"`, sonst roher String) — SLF-Eintrag nötig. Text/Telegram via `_is_eaws`/`avalanche_bulletin_text` :149,159,178,883. |
| `src/services/compare_official_alert.py:441` | Ortsvergleich-Quellenfilter nimmt Präfix vor dem ersten `:`. |
| `src/output/tokens/hazard_symbols.py`, `src/output/adapters/trip_result.py:210`, `src/output/renderers/email/compare_html.py:573,889` | Kanäle quellenneutral über hazard `avalanche_bulletin` (SMS `AV1`–`AV5`, Mail-Chip). |
| `src/services/official_alert_allclear.py` | S2-Entwarnung hängt an `source` = Registry-Name; Quellenwechsel ⇒ keine Entwarnung. |

## Existing Patterns
- S1-Tabellenzeile = neue Region ohne Code (AC-8 der S1-Spec) — aber `_row()` erzwingt die avalanche.report-URL;
  SLF braucht anderen Abruf-Endpunkt (ein Dokument für ganz CH), anderen Bulletin-Link, Höhe aus Problemen.
  Zu entscheiden in `/20`: eigene Quelle `SlfSource` mit geteiltem CAAML-Parser vs. Erweiterung der Tabelle.
- Hazard `avalanche_bulletin`, `scale="eaws"`, `native_level` 1–5, `level=min(native,4)` (ADR-0089 „zweite Skala").
- Saisonende fail-soft: leer + `mark_not_covered`, kein „nicht abrufbar".

## Dependencies
- Upstream: `aws.slf.ch` (CAAML6-JSON), EAWS-Regionsdatei CH (statisch eingecheckt), `warn_egress`, `egress_guard`.
- Downstream: alle Alert-Renderer (Mail, Telegram, SMS, Premium-SMS), Ortsvergleich-Mail/Vorschau, Alarm-Eskalation,
  S2-Entwarnung (`official_alert_allclear`).

## Existing Specs
- `docs/specs/modules/avalanche_report_bulletin.md` — S1 (AC-1…AC-22); nennt SLF als „Slice 2" (:53, :405) → auf S3 nachziehen.
- `docs/specs/modules/feat_1441_s2_entwarnung.md` — Entwarnung, `source`-Bindung (:81,135,171).
- `docs/adr/0089-lawinen-lagebericht-zweite-skala.md`, ADR-0090 (Entwarnung), ADR-0016 (Registry).
- `docs/specs/data_sources.md:218,242` — kein PENDING-Antrag für SLF → Antrag #7 nötig (Prozess :212-216).
- `docs/reference/decision_matrix.md:40`, `docs/reference/sms_format.md:287,639`.

## Risks & Considerations
- **Höhenangabe:** SLF-Höhe steckt im Problem, nicht im Rating → ohne Anpassung fehlt „oberhalb 2000 m". Wörtlich übernehmen, keine eigene Umdeutung (Haftung, ADR-0089).
- **Feinstufe 3-/3+:** amtliche Angabe; ob sie gezeigt wird, ist eine Darstellungsfrage (SMS-Länge!) → Spec.
- **Morgen-/Abend-Ausgabe:** Bulletin 16:00Z abgelöst; Abendbulletin gilt für den Folgetag — Gültigkeitsfilter und TTL prüfen; Folgeperiode ist keine Entwarnung (S2).
- **Grenze AT/CH (Silvretta, Samnaun, Rätikon):** Regionen beider Quellen können sich berühren; quellenübergreifendes Dedup in `base.py` pro Gefahrenart. Registry-Reihenfolge festlegen.
- **Bestandstest:** `tests/test_avalanche_report_coverage.py:32,64` erwartet Zürich „nicht abgedeckt" — gilt für die S1-Quelle; Zürich liegt außerhalb der SLF-Mikroregionen? (prüfen; Mittelland ist nicht SLF-Warngebiet).
- **Leere Antwort außerhalb der Saison** ist 200 + `[]`, nicht 404 → muss als „nicht abgedeckt", nicht „nicht abrufbar" gelten.
- **Lizenz/Namensnennung:** SLF-Nutzungsbedingungen für die API prüfen (Quellenangabe Pflicht).
- **Staging:** Egress-Guard blockt Warn-Hosts → Live-Beleg wie bei S1/S2 nur über Kern-Tests mit aufgezeichneten Bulletins; erster echter Beleg zur Wintersaison.
- Datenquellen-Antrag (`data_sources.md`) ist Prozess-Pflicht vor Implementierung.

## Rohdaten-Ablage (absolute Pfade, sitzungsübergreifend)
Der Eintrag „Scratchpad `slf/…`" oben bezieht sich auf diese Dateien (in `/40` nach `tests/fixtures/…` übernehmen):
- Ältere Sitzung: `/tmp/claude-1000/-home-hem-gregor-zwanzig--claude-worktrees-logical-bouncing-newt/ec73e860-f525-4ccc-ac6b-da66bd47497d/scratchpad/slf/`
  — `latest.json` (Bulletin 2026-03-01 Morgen), `f_914c20.json` (CH-Mikroregionen, 149 Umrisse), `caaml_de.json` (leere Saison `{"bulletins":[]}`), `f_*.json`.
- Analyse-Sitzung: `/tmp/claude-1000/-home-hem-gregor-zwanzig--claude-worktrees-logical-bouncing-newt/554b20c1-7241-46ae-935b-5c363249b1de/scratchpad/slf/`
  — `at_2026-03-01T17:30:00Z.json` (Abend-Ausgabe), `at_2026-03-02T06:00:00Z.json` (dieselbe Abend-Ausgabe, früh am Folgetag), `at_2026-03-02T08:00:00Z.json` (Morgen-Update), `rechtliches.html`, `bulletin_page.html`.
- Scratchpads sind flüchtig (/tmp): falls weg, mit `curl "https://aws.slf.ch/api/bulletin/caaml/de/json?activeAt=<ISO>"` reproduzierbar.

## Analysis

### Type
Feature (Scheibe S3 von #1441)

### Gemessene Fakten (Analyse 16.10.2026)
- **Ausgaben:** Abend-Ausgabe gilt 16:00Z → Folgetag 16:00Z (`nextUpdate` 07:00Z), das Morgen-Update ab 07:00Z bis 16:00Z löst sie ab.
  Ohne `activeAt` liefert die API also immer genau eine gültige Ausgabe. Der bestehende Filter `valid_to >= now`
  (`avalanche_report.py:260`) passt. Keine offene Frage mehr.
- **Höhe:** `dangerRatings[]` ohne `elevation`. Ein Bulletin hat **mehrere Probleme mit verschiedenen Höhen**, jedes mit eigener
  `dangerRatingValue` + `validTimePeriod`. Beispiel Abend 01.03.: Rating `considerable`/minus, Probleme
  `persistent_weak_layers` {lowerBound 2000} = considerable, `wet_snow` {upperBound 2200} = moderate.
  Zweites Bulletin: Rating `moderate`/plus, **beide** Probleme moderate mit 2000↑ bzw. 2200↓ → mehrdeutig.
  Vorkommen: nur `upperBound` („unterhalb 2200 m"), Renderer kann das schon (`official_alerts.py:143,166`);
  `lowerBound: 0` bei Stufe 1 (= keine Begrenzung).
- **Mittelland:** `CH-9211` (Zürich, Bern) liegt in der Umrissdatei, erscheint aber in **keinem** der 4 aufgezeichneten Bulletins
  (132/133 Regionen gegen 149 Umrisse).
- **Lizenz:** `https://www.slf.ch/de/ueber-das-slf/rechtliches/` enthält nur Haftungsausschluss + Eigenverantwortung,
  **keine ausdrückliche Weiterverwendungs-Lizenz** für die API (anders als avalanche.report CC BY 4.0). Regionsumrisse: EAWS CC0.
- **Bulletin-Link:** `https://www.slf.ch/de/lawinenbulletin-und-schneesituation/` → 200 (die API hat kein Link-Feld).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/caaml.py` | CREATE | Reine CAAML-Funktionen aus avalanche_report.py herausgelöst (`_parse_time`, `_elevation`, `_time_of_day`, `_carrier`, `_problems`, `_rated`, `_find_region`, Konstanten) + Höhe-aus-Problem-Fallback |
| `src/services/official_alerts/avalanche_report.py` | MODIFY | Importiert aus `caaml.py`; Verhalten S1 unverändert |
| `src/services/official_alerts/slf.py` | CREATE | `SlfSource` (Registry-Name `slf_bulletin`, `source="slf_bulletin:CH-xxxx"`), ein Abruf für ganz CH über `warn_egress.cached_fetch`, `covers()` per Polygon, Leere = nicht zuständig, Bulletin-Link, `dedup_id=avalanche_bulletin:CH-xxxx` |
| `src/services/official_alerts/data/avalanche_regions_CH.geojson.json` (+ README) | CREATE | EAWS-CH-Mikroregionen (CC0, 156 KB, Daten, LoC-frei) |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(SlfSource())` direkt nach `AvalancheReportSource` (:56), `__all__` |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `_SOURCE_LABELS` (:122-131) um SLF-Label ergänzen |
| `src/app/egress_guard.py` + `internal/egress/inventory.go` | MODIFY | `aws.slf.ch` als `BLOCKED` (Drift-Test `tests/test_egress_inventory_drift.py:72`) |
| `docs/specs/data_sources.md` | MODIFY | Antrag #7 SLF (PENDING → PO) |
| `docs/specs/modules/avalanche_report_bulletin.md` | MODIFY | „Slice 2" (:53, :405) → Verweis auf S3-Spec |
| `docs/adr/0089-…` (Nachtrag) oder neues ADR + `docs/adr/README.md` | MODIFY/CREATE | ADR-0089 sagt „weiteres Land = Tabelleneintrag, kein Parser-Code" (Z. 41); SLF weicht ab → in `/30` Nachtrag bzw. Folge-ADR festhalten (Index-Drift-Test) |
| `tests/test_slf_bulletin_*.py`, `tests/fixtures/slf/…`, `tests/helpers/` | CREATE | Parser/Höhe/Leere/Abdeckung/Reihenfolge/Kanäle/Entwarnung mit aufgezeichneten Bulletins |

### Scope Assessment
- Files: ~8 produktiv + Daten + Tests/Fixtures + Docs
- Estimated LoC: produktiv ~+145/-15 (unter 250)
- Risk Level: MEDIUM (zentrale Lawinen-Quelle wird refaktoriert; neue Quelle ist erst zur Wintersaison live belegbar)

### Technical Approach
**Variante A (empfohlen): eigene Quelle `SlfSource` + geteiltes Modul `caaml.py`.**
| Kriterium | A: `SlfSource` + `caaml.py` | B: Zeile in `AVALANCHE_REGION_TABLE` |
|---|---|---|
| Bestandstests S1 | bleiben grün | brechen (Tabellen-Test erwartet 4 Zeilen/Host; `covers(Zürich)` würde True) |
| Abruf | eigene Regel: 1 Dokument CH, `[]` = nicht zuständig | `_fetch_document` (:230) muss verzweigen |
| Entwarnung S2 | eigener Registry-Name → saubere `source`-Bindung | AT↔CH innerhalb einer Quelle vermischt |
| Risiko S1 | nur Verschiebung reiner Funktionen | Config-Flags im S1-Code |
| ADR-0089 | weicht formal ab → Nachtrag/ADR | formal konform, faktisch gestreckt |
Renderer und Kanäle sind hazard-basiert (`avalanche_bulletin`) und bleiben unverändert (Mail, Telegram, SMS `AV1`–`AV5`, Premium-SMS, Ortsvergleich, Entwarnung).

**Höhenregel (technische Entscheidung, als AC vorlegen):** nur wenn das Rating keine `elevation` hat (S1 unberührt) →
Probleme mit `dangerRatingValue == mainValue` des Träger-Ratings und passender `validTimePeriod`; alle mit gleicher Grenze →
diese Grenze wörtlich; verschiedene Grenzen → **keine Höhe** (nichts erfinden, #1405). `lowerBound 0` → keine Höhe.

**Abdeckung:** `covers()`/Abruf nur, wenn der Punkt per Polygon (`RegionMapper.regions_at`) in einer CH-Mikroregion liegt —
nicht nur über die BBox (die reicht bis Vorarlberg/Westtirol/Aosta/Schwarzwald: sonst „SLF nicht abrufbar" bei Innsbruck).
**Restfall Mittelland (`CH-9211`):** wird nie bewertet. Bei SLF-Ausfall drohte Zürich/Bern ein falscher Ausfallhinweis →
in `/30` entscheiden: nie bewertete Regionen aus der eingecheckten Regionsdatei weglassen oder Ausschlussliste
(Beleg vorher mit weiteren aufgezeichneten Bulletins Dez./Jan. erhärten). In `/30` prüfen, wie `base.py` „nicht abrufbar" aus `covers()` ableitet.

**Leere Saison:** 200 `{"bulletins":[]}` → `mark_not_covered`, kein Ausfall (Ist-Pfad `_candidates` „kein Bulletin für Region" → nicht zuständig).

**Ortsvergleich-Quellenfilter** (`compare_official_alert.py:441`): leer/None lässt alles durch (Ist-Verhalten, #1258).
Es gibt keine Quellenauswahl im Frontend; explizite Altlisten (`['meteoalarm']`) schließen schon heute `avalanche_report` aus.
SLF verhält sich identisch → kein zusätzlicher Handlungsbedarf, aber ein Test „ohne `sources` erscheint SLF".

**Registry-Reihenfolge:** `SlfSource` direkt nach `AvalancheReportSource`; AT/CH-Polygone sind disjunkt, Gleichstand nur theoretisch.
Reihenfolge per Test festschreiben.

### Dependencies
- Upstream: `aws.slf.ch` (CAAML6-JSON, ohne Key), EAWS-CH-Umrisse (statisch), `warn_egress.cached_fetch` (TTL 1800 s), `egress_guard`.
- Downstream (unverändert, quellenneutral): Alert-Renderer aller vier Kanäle, Ortsvergleich-Mail/Vorschau, Eskalation,
  S2-Entwarnung (`official_alert_allclear`, bindet an Registry-Name), Label-Lookup `official_alert_source_label`.
- Bestandstests mit Quellen-Isolierung: `tests/test_avalanche_report_ausfall_sichtbarkeit.py:40` (filtert per Name),
  `tests/test_avalanche_report_coverage.py:189-196` (Zählung je Name) → SLF darf sie nicht beeinflussen.

### Open Questions
- [ ] **PO (Antrag #7, mit Spec-Freigabe):** SLF-Daten weiterverwenden trotz fehlender ausdrücklicher API-Lizenz,
      mit Quellenangabe „WSL-Institut für Schnee- und Lawinenforschung SLF" + Bulletin-Link + Haftungshinweis?
      (Alternative: vorher schriftliche Anfrage beim SLF.)
- [ ] **PO (als AC-Vorschlag in `/30`):** amtliche Feinstufe 3-/3+ in Mail und Telegram-Vollform anzeigen; SMS/Premium-SMS bleiben `AV<Ziffer>` (ADR-0089).
- [ ] `/30`: Mittelland-Restfall (nie bewertete Regionen) festlegen; Form des ADR-0089-Nachtrags.
- [ ] Live-Beleg erst zur Wintersaison (wie S1/S2); Issue bleibt bis SLF live offen (PO-Entscheid 16.10.).

## /30 — Nachmessung und PO-Entscheide (17.10.2026)

### PO-Entscheide (AskUserQuestion, 17.10.2026)
- **Antrag #7 SLF-Nutzung:** nutzen mit Quellenangabe „WSL-Institut für Schnee- und Lawinenforschung SLF", Link zum
  Originalbericht und Hinweis „maßgeblich ist der Originalbericht". Parallel schriftliche Anfrage beim SLF
  (Entwurf liefert Claude; Versand durch PO). Lehnt das SLF ab ⇒ Quelle abschalten (Registrierung entfernen).
- **Feinstufe 3-/3+:** in Mail und Telegram-Langform anzeigen („Stufe 3- (erheblich)"); SMS, Premium-SMS und
  Telegram-Kurzform bleiben `AV<Ziffer>` wie bei allen Lawinendiensten (ADR-0089).

### Nachmessung (17.10.2026, `docs/artifacts/feat-1441-s3-slf/fetch_samples.py`, Rohdaten in `raw/`)
| activeAt | Bulletins | bewertete Regionen | CH-9211 | Ratings ohne `elevation` |
|---|---|---|---|---|
| 2025-12-20T08Z | 5 | 120 | nein | 5/5 |
| 2026-01-15T08Z | 9 | 134 | nein | 9/9 |
| 2026-02-10T08Z | 11 | 135 | nein | 11/11 |
| 2026-03-01T08Z | 6 | 132 | nein | 6/6 |
| 2026-04-10T08Z | 10 | 129 | nein | 15/15 |
- 149 Umrisse; in keiner der 5 Stichproben bewertet: CH-8214, -8215, -8216, -8222…-8228, CH-9111, CH-9211, CH-9311.
  Die übrigen schwanken (120–135) ⇒ es gibt keine feste Liste „nie bewertet".
- **Entscheid Mittelland (technisch):** keine Ausschlussliste. `covers()` = Punkt in CH-Mikroregion (Polygon).
  Region nicht im Bulletin ⇒ „nicht zuständig" (F001-Semantik, kompensiert nichts). Bei SLF-Ausfall zählt SLF dort als
  ausgefallen; der Ausfallhinweis entsteht laut Kompensationsregel (`base.py:199`, #1348) nur, wenn ALLE zuständigen
  Quellen ausfallen (MeteoAlarm deckt CH) ⇒ kein Fehlalarm. Known Limitation.
- **Bestandstests:** `test_avalanche_report_ausfall_sichtbarkeit.py:40` lässt `slf_bulletin` in der Registry; die
  Testpunkte (Tirol, Zell am See) liegen außerhalb der CH-Polygone ⇒ grün nur, weil `covers()` per Polygon prüft
  (nicht BBox). `test_avalanche_report_coverage.py` isoliert per `only_source` ⇒ unberührt.
- **MeteoAlarm-Lawine (`avalanche`, AW) neben `avalanche_bulletin` (AV):** bewusste Doppelung wie S1 (S1-Spec :115-120, AC-11) gilt auch für CH.
- **Pro-Quelle-Journal (#1422):** leere Saison (200 `[]`) muss als erfolgreiche „nicht zuständig"-Antwort protokolliert werden.
- **ADR:** neues ADR-0091 (Abweichung von ADR-0089 Z. 41 „weiteres Land = Tabelleneintrag"), Index in `docs/adr/README.md`.
