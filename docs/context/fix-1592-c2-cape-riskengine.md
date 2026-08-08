# Context: fix-1592-c2-cape-riskengine

**Issue:** #1592 Scheibe C2 · **Track:** Full Process · **Vorgänger:** Scheibe 1 (B0+C0+C1),
live seit `64e50203`, Spec `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md`, ADR-0048.

## Request Summary

Die zweite Wirkstelle der unbelegten CAPE-Schwelle schließen: `RiskEngine` bewertet CAPE
heute über den generischen Katalogpfad gegen 1000/2000 J/kg und erzeugt daraus
`Risk(THUNDERSTORM, MODERATE|HIGH)`. Sie soll stattdessen die in Scheibe 1 eingeführte
geeichte Schwelle je Modell × Gebiet verwenden und bei unbekannter Herkunft schweigen.

## Kernbefund — gemessen, nicht gelesen

Der Issue-Text beschreibt C2 als „dieselbe unbelegte 1000, nur ungedeckelt". Gemessen am
laufenden Code ist es mehr: **die RiskEngine unterläuft die Deckelung, die ADR-0048 und
feat_1474 AC-6 zusichern.**

```
CAPE=2500  thunder_level_max=LOW   ->  thunderstorm/low, thunderstorm/high
CAPE=2500  thunder_level_max=None  ->  thunderstorm/high
CAPE=1500  thunder_level_max=None  ->  thunderstorm/moderate
CAPE= 900  thunder_level_max=None  ->  (kein Risiko)
```

Die Kette dahinter:

1. Die Fusion (`metric_format.thunder_level_from_signals`, Scheibe C1) hängt CAPE ≥ geeichter
   Schwelle als `ThunderLevel.LOW` ein — **auf LOW gedeckelt**, ausdrücklich „misst Energie,
   kein Ereignis".
2. Dieses Ergebnis landet als `thunder_level_max` im Aggregat und wird von
   `RiskEngine._check_thunder` (`risk_engine.py:121-135`) zu `Risk(THUNDERSTORM, LOW)`.
3. **Danach zählt `RiskEngine` dieselbe Größe ein zweites Mal:**
   `_check_catalog_metric(agg, "cape", …)` (`risk_engine.py:56-58`) gegen die Katalogleiter
   1000 → `MODERATE`, >2000 → `HIGH`.
4. `_deduplicate()` behält je `RiskType` die höchste Stufe — also gewinnt der ungedeckelte
   CAPE-Zweig.

Zeile 2 der Messung ist der schärfere Fall: Liefert die Fusion `None` („keine Aussage" —
genau der Zustand, den Scheibe C1 für unbekannte Herkunft erzeugt), macht CAPE allein daraus
ein **hohes** Gewitterrisiko. Das ist dieselbe Fehlerklasse wie in C1, nur mit umgekehrtem
Vorzeichen: dort wurde „nicht belegt" als Entwarnung ausgegeben, hier als Alarm.

**Folge für den Zuschnitt:** Die im Intake vermutete Frage („wie leite ich `MODERATE`/`HIGH`
aus einem einzigen Eichwert ab?") ist nachgelagert. Zuerst zu klären ist, ob CAPE in der
RiskEngine überhaupt eine **eigene, zweite** Stufe tragen darf, wo es über `thunder_level_max`
bereits vertreten ist.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/risk_engine.py:56-58` | Der Prüfling: CAPE im generischen Katalogpfad |
| `src/services/risk_engine.py:121-135` | `_check_thunder` — CAPE ist hier über die Fusion schon vertreten |
| `src/services/risk_engine.py:137-173` | `_check_catalog_metric` — generisch, wird von 7 weiteren Metriken genutzt; darf nicht CAPE-spezifisch werden |
| `src/app/metric_catalog.py:348` | `risk_thresholds={"medium": 1000.0, "high": 2000.0}` — die unbelegte Leiter |
| `src/app/model_registry.py` | Fertig aus C0/B0: `normalize_model_id`, `effective_cape_model_id`, `CAPE_THRESHOLDS_JKG`, `cape_threshold_jkg(modell, gebiet)` |
| `src/providers/thunder_routing.py:70-86` | `thunder_region_for(lat, lon)` — dasselbe Raster, kein zweites |
| `src/providers/thunder_enrichment.py:171-186` | **Vorbild**: so löst C1 Modell + Gebiet auf und übergibt die Schwelle |
| `src/output/metric_format.py:314-370` | Die Fusion mit der Deckelung, die C2 nicht brechen darf |
| `src/app/models.py:454` | `SegmentWeatherSummary.cape_model_id` (aus C0) |
| `src/app/models.py:371-385` | `TripSegment.start_point: GPXPoint` — die Koordinate für das Gebiet |
| `src/services/weather_metrics.py:802, 837, 1196-1204` | Befüllung und Etappen-Aggregation von `cape_model_id` (Regel `agreement`) |

## Existing Patterns

- **Herkunft auflösen** (C1, `thunder_enrichment.py:176-182`): `cape_threshold_jkg(effective_cape_model_id(meta), thunder_region_for(lat, lon))` — einmal je Reihe, kein neuer Mechanismus.
- **Abstain-Muster** (ADR-0048 Punkt 5): fehlende Herkunft ⇒ **kein** Signal, insbesondere kein `NONE`. „Keine Aussage" ≠ „geprüft, unauffällig".
- **Kein stiller Rückfall** (ADR-0048 Punkt 6): der Schwellenparameter der Fusion ist keyword-only **ohne Default** — wer die Herkunft vergisst, bricht hart.
- **Uneinigkeit ⇒ `None`** (`weather_metrics.py:1196-1204`, Regel `agreement`): stimmen die Herkünfte mehrerer Segmente einer Etappe nicht überein, gilt keine.

## Dependencies

- **Upstream:** `app.metric_catalog.get_metric`, `app.model_registry`, `providers.thunder_routing`, `SegmentWeatherData.segment.start_point`, `SegmentWeatherSummary.cape_model_id`.
- **Downstream:** siehe „Dependents" unten.

## Dependents — wo das CAPE-Risiko heute wirkt

Produktive Aufrufer der RiskEngine (selbst nachgemessen, `grep` über `src/` und `api/`):

| Aufrufer | Wirkung | Unterscheidet HIGH von MODERATE? |
|---|---|---|
| `src/services/stage_weather.py:97-133` | Cockpit-/Etappen-Ampel `red`/`yellow`/`green`, ausgeliefert über `GET /api/internal/trips/{id}/stage-weather` | **ja** — `HIGH` ⇒ rot, `MODERATE` ⇒ gelb |
| `src/output/renderers/sms_trip.py:501` (`_detect_risk`) | Alert-/SMS-Pfad, sucht das Grat-Label | indirekt, s. Befund unten |

**Nicht** an der RiskEngine hängen (gegen die erste Agenten-Auskunft nachgeprüft): die
E-Mail-Gewitterspalte und die Telegram-Kurzübersicht lesen `ThunderLevel` direkt, nicht das
`RiskAssessment`. `trip_report.py:822 _determine_risk()` hat **keinen** produktiven Aufrufer —
nur Tests rufen es (`test_wind_exposition_pipeline.py`). Ebenso ist `TokenLine.main_risk`
(`tokens/dto.py:122`) nirgends im Produktivcode befüllt; `subject.py:161` übersetzt damit
faktisch immer `None`.

### Nebenbefund: ungedeckeltes CAPE verdrängt das Grat-Label in der SMS

`_deduplicate()` sortiert `HIGH` nach vorn (`risk_engine.py:240-251`); `_detect_risk()` liest
nur `assessment.risks[0]` (`sms_trip.py:607`). Gemessen:

```
heute  (CAPE ungedeckelt)  -> risks[0] = thunderstorm/high
gedeckelt (LOW)            -> risks[0] = wind_exposition/moderate
```

Ein allein von CAPE erzeugtes `THUNDERSTORM/HIGH` schiebt sich damit vor ein
`WIND_EXPOSITION/MODERATE`, und die Schleife in `sms_trip.py:498-506` findet „GratWind"
nicht mehr — der Grat-Hinweis fehlt in der Kurznachricht. Die Ursache liegt in
`_detect_risk` („nur das oberste Risiko"), nicht in CAPE; die ungedeckelte CAPE-Eskalation
löst sie nur aus. C2 entschärft das als Nebenwirkung, behebt es aber nicht.

## Reichweite der Katalog-Zahlen — selbst nachgemessen

`risk_thresholds` wird im gesamten Produktivcode **nur** in `risk_engine.py:151` gelesen
(`grep` über `src/`, `api/`). Die CAPE-Zahlen 1000/2000 wirken also ausschließlich an der
Stelle, die C2 anfasst — ein Umbau dort berührt keine Ampel und kein Rendering.

**Gegenprobe zu zwei Fehlzuordnungen aus der Test-Recherche** (beide selbst nachgesehen, der
Agent hatte sie C2 zugeschlagen):

- `test_compare_cape_severity_ampel.py` prüft `_sev_cape` → `severity_for("cape", …)`, das
  liest `display_thresholds` (300/800/1500), **nicht** `risk_thresholds`. Dass 1000 dort
  „warn" und 2000 „danger" ergibt, ist Zufall der Ampelstufen — von C2 unberührt.
- `test_friendly_format_email_and_alerts.py::test_cape_extreme_*` hängt an
  `highlight_threshold=1000.0`, ebenfalls eine andere Katalogzahl.

## Tests, die C2 wirklich bewegt

| Test | Zusicherung heute | Erwartung |
|---|---|---|
| `tests/integration/test_risk_engine.py::test_cape_high` | CAPE ≥ 2000 ⇒ `Risk(THUNDERSTORM, HIGH)` | **muss rot werden** — genau diese Zusicherung ist der Bug |
| `tests/integration/test_risk_engine.py::test_cape_moderate` | 1000 ≤ CAPE < 2000 ⇒ `MODERATE` | **muss rot werden** |
| `tests/unit/test_configurable_thresholds.py:104::test_cape_risk_thresholds` | Katalog trägt `{"medium": 1000, "high": 2000}` | rot, falls die Leiter aus dem Katalog verschwindet |

Alles aus der C0/C1-Familie (`test_cape_model_threshold.py`, `test_model_registry_normalization.py`,
`test_cape_model_id_*.py`, `test_thunder_enrichment_fuses_level_shared_path.py`) muss **grün
bleiben** — es sichert die Grundlage, auf der C2 aufsetzt. Keine dieser Dateien steht in
`.github/ci_tdd_excludes.txt`; alle laufen auf CI.

## Risks & Considerations

1. **Doppelzählung ist der eigentliche Gegenstand.** Wird nur die Schwelle ausgetauscht und
   die zweite Zählung bleibt, bleibt der Deckel aus ADR-0048 weiter unterlaufen — der Fix
   wäre halb.
2. **`_check_catalog_metric` ist generisch** und bedient sieben weitere Metriken. CAPE braucht
   einen **eigenen** Zweig (`_check_cape`), keine Sonderlogik im gemeinsamen Pfad — das war
   bereits die Vorgabe im Intake-Kommentar des Issues.
3. **Abstain kostet hier ein bestehendes Signal.** Wo die Herkunft fehlt (Ortsvergleich
   `aggregate`, Schnappschuss-Reload `snapshot`, Etappen mit uneinheitlicher Herkunft), fällt
   das CAPE-Risiko ersatzlos weg. Das ist gewollt, muss aber in der Spec als Known Limitation
   stehen — und die Fusion über `thunder_level_max` deckt diese Fälle ohnehin nicht ab.
4. **Die Koordinate muss stimmen.** Das Gebiet kommt aus `segment.start_point`; bei langen
   Etappen über eine Gebietsgrenze hinweg ist das eine Näherung — dieselbe, die
   `thunder_routing` produktiv schon trifft. Kein neues Raster einführen.
5. **Persistenz:** `cape_model_id` ist bereits additiv im Aggregat. C2 braucht **kein** neues
   Feld und fasst den Schnappschuss nicht an.
6. **Eichung nicht erfinden (PO-Vorgabe 2026-08-08).** Braucht C2 eine zweite Stufe, wird sie
   zuerst in veröffentlichter, operationell genutzter Eichung gesucht — mit ausdrücklicher
   Angabe der Parcel-Variante — und erst bei belegter Fehlanzeige aus historischen Daten
   abgeleitet. Mahnung aus Scheibe 1: die Spec `configurable_thresholds.md` schrieb das
   CAPE-Raster einer „WHO thunderstorm energy scale" zu, die es nicht gibt.

---

## Analysis

### Type
Bug (Fehlverhalten im ausgelieferten Pfad).

### Beleglage der Schwellen — Ergebnis, Reihenfolge nach PO-Vorgabe

**Stufe 1 — eigenes Gedächtnis (hätte zuerst kommen müssen):** Die Skala
`<300 marginal · 300–1000 moderat · 1000–2500 stark · 2500–4000 sehr stark · >4000 extrem`
lag bereits als PO-Recherche vom 2026-08-08 vor, samt Parcel-Tabelle je Modell
(ICON = `CAPE_ML` Mixed-Layer, Météo-France = `CAPE_INS` Most-Unstable) und dem
Quantil-Mapping-Verfahren. Ebenso die Präzedenzfälle #1506 (keine Schwelle gefunden ⇒ PO
stellte zurück) und #1474c (LPI 5/20/50, Mittelwert interpoliert und als Known Limitation
ausgewiesen).

**Stufe 2 — veröffentlichte Eichung, an der Primärquelle nachgeprüft:** SPC Mesoanalysis Help
(spc.noaa.gov/exper/mesoanalysis/help/sfcoa.html) trägt die Leiter wörtlich —
`weak <1000 · moderate 1000–2500 · strong 2500–4000 · extreme >4000` — und bindet sie im
selben Absatz an das Beispiel *„lifting the „non-virtual" surface parcel"*, also an **SBCAPE**.
Dieselbe Seite definiert SB/MU/ML sauber, gibt aber für MUCAPE und MLCAPE **keine eigene
Stufeneinteilung**. Für AROME und ICON existiert keine veröffentlichte CAPE-Schwellen-
dokumentation, für die Umrechnung zwischen den Varianten keine belegte Quelle.

⇒ **Für keines unserer beiden Hauptmodelle gibt es eine übernehmbare Leiter.** Nebenbefund:
die Katalogzahlen 1000/**2000** sind nicht einmal die SPC-Leiter (die wäre 1000/**2500**/4000) —
eine dritte, nirgends belegte Variante.

**Stufe 3 — historische Daten:** verfügbar (`scripts/eichung_cape_schwelle.py`, ein zweiter
Perzentilrang wäre `quantiles(...)[94]` → `[98]`, derselbe Abruf). **Wird nach dem Befund
unten nicht gebraucht.**

### Die Stufenfrage stellt sich nicht — CAPE ist bereits vertreten

Beide produktiven Aufrufer von `assess_segment` (`stage_weather.py:104`, `sms_trip.py:600`)
arbeiten mit live über `compute_extended_metrics()` berechneten Segment-Summaries. Dort ist
`enrich_thunder()` bereits gelaufen; die Fusion hat jede Stunde gegen **dieselbe** kalibrierte
Schwelle geprüft. Erreicht `agg.cape_max_jkg` die Schwelle, hat die Stunde mit diesem
Maximalwert bei der Fusion mindestens `ThunderLevel.LOW` erhalten ⇒ `thunder_level_max >= LOW`
⇒ `_check_thunder` liefert das Risiko bereits.

Eine korrekt gedeckelte eigene `_check_cape` (Option B) wäre nach `_deduplicate()` damit ein
**No-op** — sie könnte nur noch ein Signal erzeugen, das ohnehin schon da ist. Mutations-Probe
bestätigt das von der anderen Seite: Mutanten in `_check_cape` änderten den
`assess_segment`-Ausgang nicht, solange `_check_thunder` mitläuft. Ein Baustein, dessen
Verfälschung nichts bewirkt, bewacht nichts.

### Technical Approach — Empfehlung: Option A

**Die CAPE-Regel in der RiskEngine ersatzlos streichen** (`risk_engine.py:56-58`).

| | Option A (streichen) | Option B (`_check_cape`, LOW-gedeckelt) | Option C (zwei Stufen) |
|---|---|---|---|
| Doppelzählung weg | ja | ja | ja |
| Deckel aus ADR-0048 gehalten | ja | ja | **nein — Verstoß** |
| Neue Eichung nötig | nein | nein | ja, und keine belegte vorhanden |
| Wirkung gegenüber heute | — | **keine** (No-op) | — |
| Mutations-testbar | gut | schlecht (Mutanten sterben nicht) | schlecht |
| LoC | ~50–100 | ~150–220 | ~180–260 (Limit 250) |

Option C scheidet doppelt aus: Widerspruch zu ADR-0048 („die Deckelung bleibt") **und** keine
belegte HIGH-Schwelle. Option B baut Code ohne Wirkung. Option A entfernt die
Deckel-Unterlaufung und lässt CAPE dort wirken, wo alle Gewittersignale zusammenlaufen — in
der Fusion.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/risk_engine.py` | MODIFY | Regel 2 (CAPE) entfällt; `_check_catalog_metric` bleibt generisch für die übrigen 6 Metriken |
| `src/app/metric_catalog.py` | MODIFY | `risk_thresholds` bei `cape` entfernen — nach dem Streichen toter Konfigurationswert |
| `tests/integration/test_risk_engine.py` | MODIFY | `test_cape_high`/`test_cape_moderate` ersetzen durch den Nachweis, dass CAPE **nur noch** über `thunder_level_max` wirkt |
| `tests/unit/test_configurable_thresholds.py` | MODIFY | `test_cape_risk_thresholds` entfällt bzw. kehrt sich um |

### Scope Assessment
Dateien: 4 · geschätzt +60/−30 LoC · Risiko: MEDIUM (zentraler Risiko-Pfad, aber enge Fläche).

### Was sich für den Nutzer ändert

| Fall | heute | nach A |
|---|---|---|
| CAPE 2500, Fusion sagt „leicht" | Etappe **rot** | Etappe **gelb** — der Deckel wirkt endlich |
| CAPE 2500, Fusion sagt „keine Aussage" | Etappe **rot** | **grün** |
| CAPE 1500, Fusion sagt „keine Aussage" | Etappe gelb | grün |

Der zweite und dritte Fall sind der Preis. Sie treten nur ein, wo die Modell-Herkunft fehlt
oder keine Kalibrierung vorliegt — gemessen: `icon_d2×FR`, `icon_d2×EU_REST`, alle
`metno_nordic`-Kombinationen. Ortsvergleich (`aggregate`) und Schnappschuss-Reload
(`snapshot`) erreichen die RiskEngine **gar nicht** (nachgemessen: kein Snapshot-Konsument
ruft `assess_segment`) — die im Kontext-Abschnitt oben befürchtete Reichweite war zu groß
geschätzt.

### Open Questions

- [ ] Akzeptiert der PO „rot → grün" bei fehlender Modell-Herkunft als Known Limitation
      (analog zur bereits akzeptierten Fusions-Limitation in ADR-0048)? Alternative wäre,
      die drei Lücken der Eichtabelle zu schließen, statt an dieser Stelle zu schweigen.
