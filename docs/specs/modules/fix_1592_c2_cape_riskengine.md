---
entity_id: fix_1592_c2_cape_riskengine
type: bugfix
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [gewitter, cape, risk-engine, model-registry, deckelung, issue-1592]
---

# CAPE wird in der RiskEngine nicht mehr doppelt gezählt — Eichlücke ICON-D2×FR geschlossen (Issue #1592 Scheibe C2)

## Approval

- [x] Approved — PO-„go" 2026-08-08 (die sieben ACs wurden auf Deutsch vorgelegt und freigegeben;
      Beleg: Issue #1592, Kommentar „Spec freigegeben — Scheibe C2")

## Purpose

`RiskEngine` bewertet CAPE heute ein zweites Mal gegen eine eigene, unbelegte Katalogleiter
(1000/2000 J/kg) — obendrauf zu der Fusion, die CAPE in Scheibe 1 bereits geeicht und auf
`ThunderLevel.LOW` gedeckelt einhängt. `_deduplicate()` behält je Risikotyp die höchste Stufe,
also gewinnt die ungedeckelte zweite Zählung und unterläuft damit die Deckelung, die ADR-0048
und `feat_1474` AC-6 zusichern. Diese Scheibe streicht die zweite Zählung ersatzlos (Teil 2) und
schließt nebenbei die eine echte Lücke der Eichtabelle aus Scheibe 1, `("icon_d2", "FR")`, indem
sie je Gebiet eine geordnete Liste von Referenzpunkten statt eines einzelnen Punkts einführt
(Teil 1) — Korsika deckt ICON-D2 nicht ab, ein zweiter Punkt in den französischen Alpen schon.

**Bewusst NICHT Teil dieser Scheibe:** Familie 3 (Δ-Alarm-Beleg-Gate) bleibt bei der festen
Katalogschwelle — eigene Folgescheibe (C3). Der Same-Model-Guard für den Δ-Alarm-Pfad ist ein
eigenes Bug-Ticket (Spec S1, Known Limitations). `sms_trip.py::_detect_risk` liest weiterhin nur
`assessment.risks[0]`; diese Scheibe entschärft nur die Nebenwirkung (ungedeckeltes CAPE
verdrängt das Grat-Label), behebt aber nicht die Ursache (Known Limitations unten).

## Source

- **File:** `src/services/risk_engine.py`, `src/app/metric_catalog.py`,
  `scripts/eichung_cape_schwelle.py`, `src/app/model_registry.py`
- **Identifier:** `RiskEngine.assess_segment()` (Regel 2 entfällt),
  `RiskEngine._check_catalog_metric()` (bleibt generisch, unverändert),
  `MetricDefinition.risk_thresholds` bei `"cape"` (entfernt),
  `_REGION_REFERENCE_POINTS` (wird zu geordneter Liste je Gebiet),
  `CAPE_THRESHOLDS_JKG` (ein Eintrag `("icon_d2", "FR")` kommt hinzu, alle zehn
  bestehenden Einträge bleiben unverändert)

**Schicht:** ausschließlich Python-Core (`src/services/`, `src/app/`) plus das bestehende
einmalige Auswertungsskript unter `scripts/`. Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+60/−30 (Workflow-Limit 250, unverdächtig).
- **Files:** 4 Quelldateien (2 modifiziert an der Risiko-Regel, 2 an der Eichung), 2 Testdateien
  modifiziert, mindestens 1 Testdatei neu (Kernfall/Gegenprobe/Abstain über
  `RiskEngine.assess_segment()`, s. „Tests" unten).
- **Effort:** low-medium — Teil 2 ist eine Streichung an einer klar begrenzten Stelle; Teil 1
  ändert eine Datenstruktur (Punkt → Liste) an zwei bereits bestehenden Modulen, führt aber
  keinen neuen Mechanismus ein.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| ADR-0048 | bindende Vorgabe, unverändert gültig | „Feste Schwellen werden nie über Modellgrenzen getragen" + „die Deckelung bleibt" (Punkt „Unberührt bleibt..."). Diese Scheibe stellt die Deckelung erst her, ändert die Entscheidung nicht |
| `feat_1474_gewitter_befund_stufen.md` AC-6 | Regressionsanker | „CAPE misst Energie, kein Ereignis" — eskaliert nie über LOW. C2 macht diese Zusicherung an der RiskEngine erstmals wirksam |
| `fix_1592_s1_cape_modellschwelle.md` (Scheibe 1) | Grundlage, unverändert | `model_registry.effective_cape_model_id()`, `thunder_routing.thunder_region_for()`, `thunder_level_from_signals()`, `enrich_thunder()` — C2 fasst keinen dieser Bausteine an |
| `src/app/model_registry.CAPE_THRESHOLDS_JKG` | erweitert, nicht ersetzt | bekommt einen zusätzlichen Eintrag `("icon_d2", "FR")`; alle zehn bestehenden Werte bleiben identisch |
| `tests/tdd/test_cape_model_threshold.py`, `test_model_registry_normalization.py`, `test_cape_model_id_*.py`, `test_thunder_enrichment_fuses_level_shared_path.py` | **unverändert grün zu halten** | sichern die Grundlage aus Scheibe 1; keine dieser Dateien steht in `.github/ci_tdd_excludes.txt` |

## Teil 1 (Eichpunkt-Liste) — die eine echte Lücke der Eichtabelle schließen

**Befund:** `scripts/eichung_cape_schwelle.py::_REGION_REFERENCE_POINTS` führt heute genau **einen**
Referenzpunkt je Gebiet. Für FR ist das Korsika (42.22, 9.07) — der GR20-Referenzpunkt. Korsika
liegt aber **außerhalb des ICON-D2-Gitters** (gemessen: Archiv-API, drei Julitage 2025,
`models=icon_d2`, 0 Werte). Deshalb fehlt `("icon_d2", "FR")` in `CAPE_THRESHOLDS_JKG`, obwohl
ICON-D2 in Frankreich real als AROME-Fallback zum Zug kommt (`providers.openmeteo.REGIONAL_MODELS`,
Priorität 2). Ohne Eintrag liefert `cape_threshold_jkg("icon_d2", "FR")` `None` — CAPE trägt dort
über den Fallback-Pfad strukturell nie zur Gewitterstufe bei, obwohl ICON-D2 andernorts real
Werte liefert.

**Änderung:** `_REGION_REFERENCE_POINTS` wird von `dict[str, tuple[float, float]]` zu
`dict[str, list[tuple[float, float]]]` — je Gebiet eine **geordnete** Liste von Referenzpunkten
statt eines einzelnen. `calibrate()` versucht für jedes (Modell, Gebiet)-Paar die Punkte der
Liste **der Reihe nach**; der **erste** Punkt, an dem das Modell tatsächlich CAPE-Werte liefert
(mindestens ein Wert ≠ `null`), bestimmt die Eichung dieser Kombination. Liefert **kein** Punkt
der Liste einen Wert, entsteht weiterhin kein Tabelleneintrag (unverändertes Verhalten aus
Scheibe 1, Abschnitt 1 Punkt 4).

**Punktlisten:**
- `FR`: `[(42.22, 9.07), (45.00, 6.50)]` — Korsika bleibt **erster** Punkt (dadurch bleiben alle
  heute belegten Werte für FR unverändert, da jedes bisher belegte Modell dort bereits Werte
  liefert). Zweiter Punkt: französische Alpen (45.00, 6.50) — vom PO gemessen (Archiv-API, drei
  Julitage 2025, `models=icon_d2`): 72 Werte, max 670 J/kg. Liegt auch im AROME-Gebiet, ist also
  für beide in FR geführten Modelle gültig.
- `DE_ALPEN`, `EU_REST`: unverändert je ein Punkt (bestehende Werte aus Scheibe 1) — keine
  gemessene Lücke, keine Änderung nötig.

**Warum keine dritte Kombination ergänzt wird — zwei gemessene Nicht-Lücken:**
- `icon_d2 × EU_REST` ist eine leere Menge: die einzige Fläche, wo ICON-D2-Gitter und
  EU_REST-Gebiet zusammenfallen, liegt unterhalb 43,17° N (darüber beginnt laut
  `thunder_routing._REGIONS` das Gebiet DE_ALPEN); an vier dort geprüften Punkten liefert
  ICON-D2 überall 0 Werte. Ein dritter FR-Punkt für EU_REST würde also nichts eichen, was der
  Produktivpfad je erreicht.
- `metno_nordic × *`: der **Produktiv**-Endpunkt `/v1/metno` liefert überhaupt kein CAPE
  (Stockholm, Jotunheimen, Tromsø je 0 Werte; Gegenprobe `/v1/dwd-icon` am selben Ort: 48 Werte).
  Wo kein Wert je ankommt, fehlt keine Schwelle — ein zusätzlicher Referenzpunkt würde daran
  nichts ändern.

Beide Fälle sind Known Limitations, nicht offene Lücken (s. unten, mit den Messwerten).

**Warum die Alpen und nicht das Rhône-Tal** (beide Kandidaten liefern ICON-D2-Werte): Die
Punktwahl entscheidet über die Schwelle. Vorab gemessen an der vollen Saison April–September
2025, n = 4392 Stunden je Punkt:

| Kandidat | P95 | Schwelle `max(P95, 300)` |
|---|---|---|
| **Französische Alpen 45,00/6,50** | 230 | **300,0** (Untergrenze greift) |
| Rhône-Tal 44,50/4,80 | 390 | 390,0 |

Gewählt werden die **Alpen**: gleiche Landschaftsart wie der erste FR-Punkt (Korsika, Gebirge)
und passend zur Zielgruppe, die im Gebirge unterwegs ist. Das Rhône-Tal würde eine
Flachland-Klimatologie auf Bergetappen anwenden — derselbe Fehler wie der dieses Issues, nur
eine Ebene tiefer.

**`src/app/model_registry.py`:** `CAPE_THRESHOLDS_JKG` bekommt einen zusätzlichen Eintrag
`("icon_d2", "FR"): 300.0` — der Wert des erneuten Skriptlaufs für den zweiten FR-Punkt
(max(P95, 300.0), dieselbe Regel wie alle bestehenden Einträge, ADR-0048 Punkt 2). Der
Kommentarblock über der Tabelle wird um die Punktliste ergänzt; die bestehende Begründung
„fehlende Kombinationen ... haben BEWUSST keinen Eintrag" wird präzisiert auf die zwei verbliebenen
gemessenen Nicht-Lücken (`icon_d2 × EU_REST`, `metno_nordic × *`). Alle zehn bisher belegten
Werte bleiben **byte-identisch** — das ist der tragende Regressionsschutz dieser Scheibe (AC-2).

## Teil 2 (RiskEngine) — die zweite CAPE-Zählung streichen

**Befund** (`context/fix-1592-c2-cape-riskengine.md`, gemessen):

```
CAPE=2500  thunder_level_max=LOW   ->  thunderstorm/low, thunderstorm/high
CAPE=2500  thunder_level_max=None  ->  thunderstorm/high
CAPE=1500  thunder_level_max=None  ->  thunderstorm/moderate
```

`_check_catalog_metric(agg, "cape", agg.cape_max_jkg, RiskType.THUNDERSTORM, risks)`
(`risk_engine.py:57-59`, Regel 2) zählt CAPE gegen die unbelegte Leiter 1000/2000 — obendrauf zu
`_check_thunder` (Regel 1), das `thunder_level_max` bereits als `Risk(THUNDERSTORM, …)` einhängt.
`_deduplicate()` behält je `RiskType` die höchste Stufe; die ungedeckelte zweite Zählung gewinnt
gegen die gedeckelte erste. Bei fehlender Fusions-Aussage (`thunder_level_max is None`, genau der
Zustand, den Scheibe 1 für unbekannte Modell-Herkunft erzeugt) macht CAPE allein daraus ein
**hohes** Gewitterrisiko — dieselbe Fehlerklasse wie in Scheibe 1, nur mit umgekehrtem Vorzeichen
(dort wurde „nicht belegt" als Entwarnung ausgegeben, hier als Alarm).

**Warum keine eigene, gedeckelte `_check_cape`-Regel (verworfene Option B):** Beide produktiven
Aufrufer von `assess_segment()` (`stage_weather.py:104`, `sms_trip.py:600`) arbeiten mit live über
`compute_extended_metrics()` berechneten Summaries, bei denen `enrich_thunder()` bereits gelaufen
ist. Erreicht `agg.cape_max_jkg` die kalibrierte Schwelle, hat die Stunde mit diesem Maximalwert
bei der Fusion mindestens `ThunderLevel.LOW` erhalten ⇒ `thunder_level_max >= LOW` ⇒
`_check_thunder` liefert das Risiko bereits. Eine zweite, korrekt auf LOW gedeckelte
`_check_cape`-Regel wäre nach `_deduplicate()` ein reiner No-op — ein Baustein, dessen
Verfälschung nichts am Ergebnis von `assess_segment()` ändert, bewacht nichts (Mutations-Probe im
Kontextdokument bestätigt das).

**Änderung:**
1. `risk_engine.py`: Regel 2 (Zeilen 57-59, Aufruf von `_check_catalog_metric(agg, "cape", …)`)
   entfällt ersatzlos. `_check_catalog_metric` selbst bleibt unverändert — sie bedient weiterhin
   Wind, Böe, Niederschlag, Regenwahrscheinlichkeit, Wind-Chill und Sichtweite (die verbleibenden
   sechs Aufrufer in `assess_segment()`).
2. `metric_catalog.py:348`: `risk_thresholds={"medium": 1000.0, "high": 2000.0}` beim
   `MetricDefinition`-Eintrag `"cape"` wird entfernt (Feld hat einen Default, kein Pflichtfeld —
   nach dem Streichen von Regel 2 gibt es im gesamten Produktivcode keinen Leser mehr; gemessen
   per `grep` über `src/`, `api/`: `risk_thresholds` wird ausschließlich in
   `risk_engine.py:151` gelesen, also genau an der Stelle, die diese Scheibe anfasst).
   `display_thresholds` (Ampel-Farben, 300/800/1500) und `highlight_threshold` bleiben
   unverändert — andere Konsumenten, von dieser Scheibe unberührt.

## Tests

**Werden rot (die Zusicherung selbst ist der Bug — ersetzt, nicht repariert):**
- `tests/integration/test_risk_engine.py::test_cape_high` — prüft heute `CAPE=2500` ⇒
  `Risk(THUNDERSTORM, HIGH)`. Ersetzt durch den AC-4/AC-5-Nachweis unten.
- `tests/integration/test_risk_engine.py::test_cape_moderate` — prüft heute `CAPE=1500` ⇒
  `Risk(THUNDERSTORM, MODERATE)`. Entfällt ersatzlos (kein Ersatzverhalten — CAPE ohne
  Fusions-Aussage erzeugt künftig kein Risiko, AC-5).
- `tests/unit/test_configurable_thresholds.py::test_cape_risk_thresholds` — prüft heute
  `get_metric("cape").risk_thresholds == {"medium": 1000.0, "high": 2000.0}`. Kehrt sich um zu
  AC-7 (leer/entfernt).
- `tests/unit/test_trip_report_formatter_v2.py::TestRiskPopCape::test_extreme_cape_high_risk` —
  prüfte `_determine_risk()` (`TripReportFormatter`, kein Produktiv-Aufrufer, `trip_report.py:822`)
  mit `thunder_level_max=ThunderLevel.NONE` und `cape=2500`, erwartete `"high"`. Dieselbe Lage wie
  `test_cape_high` oben — CAPE allein erzeugt ein Risiko, obwohl die Fusion „geprüft, kein
  Gewitter" sagt. Nachträglich gefunden am 2026-08-08 durch den CI-gespiegelten Vollsuite-Lauf
  (nicht durch die vorherige Test-Recherche, s. Changelog).
- `tests/unit/test_trip_report_formatter_v2.py::TestRiskPopCape::test_moderate_cape_medium_risk` —
  dieselbe Lage, `cape=1200`, erwartete `"moderate"`. Ebenfalls nachträglich gefunden.

**Neu (Kernfall, Gegenprobe, Abstain — über die echte Einstiegsfunktion):** eine neue
Testdatei/-klasse in `tests/integration/test_risk_engine.py` (oder ein neuer Testmodul im selben
Verzeichnis, Namensregel „nach Verhalten" — z. B. `test_cape_no_double_count`), die
`RiskEngine().assess_segment()` end-to-end mit gesetztem `agg.cape_max_jkg` UND
`agg.thunder_level_max` aufruft (beide Felder direkt auf dem Summary-Fixture gesetzt — keine
Fusion nötig, das ist bereits durch die C1-Testfamilie gedeckt). Deckt AC-3/AC-4/AC-5 ab.

**Müssen grün bleiben (Grundlage aus Scheibe 1, unverändert von dieser Scheibe berührt):**
`tests/tdd/test_cape_model_threshold.py`, `tests/tdd/test_model_registry_normalization.py`,
`tests/tdd/test_cape_model_id_*.py`, `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py`.
Sowie die übrigen `TestRiskEngine*`-Fälle in `test_risk_engine.py` (Wind, Böe, Niederschlag,
Regenwahrscheinlichkeit, Wind-Chill, Sichtweite, Wind-Exposition, Confidence, Dedup) — Nachweis
für AC-6.

**Neu für Teil 1:** ein Test, der mindestens zwei der zehn bestehenden `CAPE_THRESHOLDS_JKG`-Werte
gegen die konkrete Zahl festnagelt (u. a. `("meteofrance_arome", "FR") == 300.0`, der Wert, der in
Scheibe 1 selbst als Kernfall diente) UND prüft, dass `("icon_d2", "FR")` jetzt ein Eintrag ist —
Nachweis für AC-1/AC-2.

## Was sich für den Nutzer ändert

| Fall | heute | nach C2 |
|---|---|---|
| CAPE 2500, Fusion sagt „leicht" | Etappe **rot** (Cockpit-Ampel) | Etappe **gelb** — der Deckel aus ADR-0048 wirkt endlich |
| CAPE 2500, Fusion sagt „keine Aussage" (`thunder_level_max is None`) | Etappe **rot** | Etappe **grün** |
| CAPE 1500, Fusion sagt „keine Aussage" | Etappe **gelb** | Etappe **grün** |

Betroffen: Cockpit-/Etappen-Ampel `services/stage_weather.py:97-133` (`GET
/api/internal/trips/{id}/stage-weather`, `HIGH` ⇒ rot, `MODERATE` ⇒ gelb) und, als
Nebenwirkung, die SMS/Alert-Grat-Erkennung (`sms_trip.py::_detect_risk`, s. Known Limitations).
Zeile 2 und 3 sind der Preis dieser Scheibe. Sie setzen `thunder_level_max is None` voraus, also
eine Etappe **ohne jedes** Gewittersignal — auch ohne Wettercode, Blitzdichte und Blitzpotenzial,
denn jedes einzelne davon setzt die Stufe bereits. Erreichbar ist das im Wesentlichen dort, wo
die Gewitter-Anreicherung ausgefallen ist. Die naheliegende zweite Ursache — fehlende
Modell-Herkunft aus Ortsvergleich (`aggregate`) und Schnappschuss-Reload (`snapshot`) — greift
hier **nicht**: diese Pfade rufen `assess_segment()` gar nicht auf (nachgemessen, s. Known
Limitations). Nach Teil 1 bleiben als Kalibrierungslücken nur noch `icon_d2 × EU_REST` und
`metno_nordic × *`, und beide sind gemessen leere Mengen.

## Known Limitations

- **Ortsvergleich (`aggregate`) und Schnappschuss-Reload (`snapshot`) erreichen die RiskEngine
  nicht.** Nachgemessen (Scheibe 1, im Kontext bestätigt): kein Snapshot-/Vergleichs-Konsument
  ruft `assess_segment()`. Die dort ohnehin fehlende Modell-Herkunft (Scheibe 1, Abschnitt 2)
  wirkt sich auf diese Scheibe folglich gar nicht aus.
- **`icon_d2 × EU_REST` bleibt ohne Eintrag** — gemessen: die einzige Fläche, in der
  ICON-D2-Gitter und EU_REST-Gebiet zusammenfallen, liegt unterhalb 43,17° N (Grenze zu
  DE_ALPEN); an vier dort geprüften Punkten liefert ICON-D2 überall 0 Werte. Kein Mangel,
  sondern eine leere Menge.
- **`metno_nordic × *` bleibt ohne Eintrag** — gemessen: der Produktiv-Endpunkt `/v1/metno`
  liefert überhaupt kein CAPE (Stockholm, Jotunheimen, Tromsø je 0 Werte; Gegenprobe
  `/v1/dwd-icon` am selben Ort: 48 Werte). Wo kein Wert ankommt, fehlt keine Schwelle.
- **Ungedeckeltes CAPE verdrängt heute das Grat-Label in der SMS — C2 entschärft das nur als
  Nebenwirkung, behebt es nicht.** `_deduplicate()` sortiert `HIGH` nach vorn
  (`risk_engine.py:240-251`), `sms_trip.py::_detect_risk` liest nur `assessment.risks[0]`
  (`sms_trip.py:607`). Solange CAPE ungedeckelt `THUNDERSTORM/HIGH` erzeugen konnte, schob sich
  das vor ein `WIND_EXPOSITION/MODERATE` und der Grat-Hinweis fehlte in der Kurznachricht. Nach
  C2 kann CAPE allein kein `HIGH` mehr erzeugen — das Symptom tritt seltener auf —, aber die
  Ursache (`_detect_risk` liest nur das oberste Risiko statt gezielt nach `WIND_EXPOSITION` zu
  suchen) bleibt bestehen und kann von jedem anderen `HIGH`-Risiko weiterhin ausgelöst werden.
  Eigenes Ticket, falls gewünscht.
- **Ein Referenzpunkt-Kandidat je fehlender Kombination, nicht systematisch alle Gebiete
  durchsucht.** Diese Scheibe schließt genau die eine Lücke, die Issue #1592 nennt
  (`icon_d2 × FR`). Ob weitere Gebiete von einer zweiten Punktliste profitieren würden, ist nicht
  geprüft — spätere Verfeinerung, kein Bestandteil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0048 gilt unverändert.
- **Rationale:** ADR-0048 legt bereits fest, dass die Deckelung von CAPE auf `LOW` bestehen
  bleibt („Unberührt bleibt die Produktentscheidung aus feat_1474 AC-6 ... Die Schwelle wird
  variabel, die Deckelung bleibt") und dass Familie 2 (RiskEngine) in einer eigenen Scheibe
  folgt („Die Familien RiskEngine (C2) und Δ-Alarme (C3) sind in dieser Scheibe noch nicht
  umgestellt"). Diese Scheibe **stellt diese bereits getroffene Entscheidung erst her** — sie
  entfernt eine Regel, die der Entscheidung zuwiderlief, führt aber kein neues Prinzip, kein
  neues Raster und keine neue Schwellenlogik ein. Kein neuer ADR nötig.

## Acceptance Criteria

- **AC-1 (Eichlücke geschlossen, mit Begründung):** Given die Punktliste des Gebiets FR enthält
  jetzt zwei Referenzpunkte (Korsika zuerst, dann die französischen Alpen) / When das Eichskript
  für `icon_d2 × FR` läuft und am ersten Punkt keine Werte findet / Then versucht es den zweiten
  Punkt, findet dort Werte, und die committete Eichtabelle `CAPE_THRESHOLDS_JKG` trägt einen
  Eintrag `("icon_d2", "FR")` mit dem Wert **300,0**.
  - Test: `CAPE_THRESHOLDS_JKG[("icon_d2", "FR")] == 300.0`. Der Schlüssel existiert **nur
    dann**, wenn der zweite Punkt tatsächlich befragt wurde — am ersten liefert ICON-D2 keine
    Werte. Der exakte Wert nagelt zusätzlich den gewählten Punkt fest: der verworfene
    Rhône-Kandidat hätte 390,0 ergeben, ein Test auf „≥ 300" würde beide durchlassen.

- **AC-2 (Regressionsschutz, tragend — Umstellung auf Punktlisten verändert keinen bestehenden
  Wert):** Given die Umstellung von `_REGION_REFERENCE_POINTS` von Einzelpunkt auf geordnete
  Liste je Gebiet / When alle zehn heute belegten (Modell, Gebiet)-Kombinationen erneut
  nachgeschlagen werden / Then liefern sie ausnahmslos denselben Zahlenwert wie vor der
  Umstellung — insbesondere `("meteofrance_arome", "FR") == 300.0`.
  - Test: mindestens zwei bestehende Einträge (darunter `("meteofrance_arome", "FR")`) werden
    fest gegen ihren bisherigen Zahlenwert geprüft. Würde die Punktlisten-Umstellung
    versehentlich die Reihenfolge vertauschen oder einen anderen Punkt zuerst prüfen, fiele
    dieser Test durch.

- **AC-3 (Kernfall — genau eine Zählung statt zwei):** Given ein Segment mit hohem CAPE (2500
  J/kg), dessen Fusions-Ergebnis „leicht" ist (`thunder_level_max == ThunderLevel.LOW`) / When
  `RiskEngine.assess_segment()` aufgerufen wird / Then enthält das Ergebnis **genau ein**
  `Risk(THUNDERSTORM, …)` der Stufe `LOW` — vorher enthielt es zusätzlich ein
  `Risk(THUNDERSTORM, HIGH)`.
  - Test: über die echte Einstiegsfunktion `RiskEngine().assess_segment()`, nicht über eine
    interne Hilfsmethode.

- **AC-4 (Gegenprobe zur Deckelung — funktioniert für jeden CAPE-Wert):** Given ein Segment mit
  einem extrem hohen CAPE-Wert (z. B. 50000 J/kg) und `thunder_level_max == ThunderLevel.LOW` /
  When `assess_segment()` aufgerufen wird / Then erzeugt die RiskEngine kein
  `Risk(THUNDERSTORM, …)` über der Stufe, die `thunder_level_max` vorgibt — unabhängig davon, wie
  hoch CAPE numerisch ist.
  - Test: CAPE=50000 mit `thunder_level_max=LOW` liefert weiterhin nur `LOW`, niemals
    `MODERATE`/`HIGH`.

- **AC-5 (Abstain — fehlende Fusions-Aussage erzeugt kein Alarm-Risiko):** Given ein Segment mit
  vorhandenem CAPE-Wert (z. B. 2500 J/kg oder 1500 J/kg), aber `thunder_level_max is None`
  („keine Aussage") / When `assess_segment()` aufgerufen wird / Then enthält das Ergebnis **kein**
  `Risk(THUNDERSTORM, …)` — vorher lieferte derselbe Fall `HIGH` bzw. `MODERATE`.
  - Test: CAPE=2500 und CAPE=1500, jeweils mit `thunder_level_max=None`, liefern in beiden
    Fällen keine `THUNDERSTORM`-Risiken.

- **AC-6 (generischer Katalogpfad bleibt für die übrigen sechs Metriken unverändert):** Given die
  bestehenden Regeln für Wind, Böe, Niederschlag, Regenwahrscheinlichkeit, Wind-Chill und
  Sichtweite in `_check_catalog_metric()` / When das Streichen der CAPE-Regel implementiert wird
  / Then verhalten sich alle sechs übrigen Aufrufer unverändert — dieselben Eingaben liefern
  dieselben Risiken wie vor der Änderung.
  - Test: die bestehende `TestRiskEngine*`-Suite in `test_risk_engine.py` für Wind, Böe,
    Niederschlag, Regenwahrscheinlichkeit, Wind-Chill, Sichtweite bleibt unverändert grün (kein
    neuer Test nötig, Regressionsnachweis über den unveränderten Bestand).

- **AC-7 (tote Konfiguration entfernt):** Given `MetricDefinition` für `"cape"` trug bisher
  `risk_thresholds={"medium": 1000.0, "high": 2000.0}` / When die CAPE-Regel aus der RiskEngine
  gestrichen ist / Then ist `get_metric("cape").risk_thresholds` entfernt oder leer, und kein
  Produktivpfad liest den Wert mehr (`display_thresholds`, `highlight_threshold` bleiben
  unverändert bestehen).
  - Test: `get_metric("cape").risk_thresholds` ist `None`/leer bzw. das Attribut existiert mit
    Default; `grep -r "risk_thresholds" src/ api/` zeigt keinen Leser mehr außerhalb von
    `risk_engine.py:151` (dem generischen, CAPE-freien Pfad).

## Changelog

- 2026-08-08: Initial spec created (Issue #1592, Scheibe C2).
- 2026-08-08: Zwei weitere rot werdende Tests nachgetragen
  (`TestRiskPopCape::test_extreme_cape_high_risk`,
  `::test_moderate_cape_medium_risk`), gefunden durch den CI-gespiegelten Vollsuite-Lauf, nicht
  durch die vorherige Spec-Erstellung/Test-Recherche erfasst.
