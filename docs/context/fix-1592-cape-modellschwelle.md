# Context: fix-1592-cape-modellschwelle

**Issue:** #1592 · **Track:** Full Process · **Zuschnitt (PO-go 2026-08-08):** Scheibe C (abstain) zuerst, Scheibe B (Schwelle je Modell) danach
**Erhoben:** 2026-08-08, drei parallele Explore-Agenten, gegen `963e673e`

## Request Summary

Die feste CAPE-Schwelle von 1000 J/kg wird auf Werte angelegt, die aus unterschiedlichen
Wettermodellen mit **unterschiedlicher Parcel-Definition** stammen. In Frankreich (AROME,
Most-Unstable-CAPE) löst sie nachweislich **nie** aus, bei ECMWF in 65 % aller Stunden.
Scheibe C beendet zunächst die daraus folgende **Falschaussage**; Scheibe B ersetzt die eine
Schwelle durch eine geeichte Tabelle je Modell.

## Der eigentliche Befund: es sind vier Schwellenfamilien, nicht eine

Der Issue-Text nennt die Fusion. Gemessen wirken **vier** voneinander unabhängige
CAPE-Schwellen, alle modellblind, alle aus derselben Katalog-Definition
(`src/app/metric_catalog.py:328-352`):

| # | Familie | Zahl | Wirkung | Deckelung |
|---|---|---|---|---|
| 1 | **Fusion** `metric_format.py:315-323, 360` | 1000 (`risk_thresholds["medium"]`) | CAPE → `ThunderLevel.LOW` in `dp.thunder_level` | ja, nie über „leicht" |
| 2 | **RiskEngine** `risk_engine.py:57-60` | 1000 / 2000 (dieselbe Tabelle) | `Risk(THUNDERSTORM, MODERATE\|HIGH)` im Trip-Report | **nein — bis HIGH** |
| 3 | **Δ-Alarme** `metric_catalog.py:337`, `alert_preset.py:23,62`, `compare_alert.py:43,61` | 500 (Fallback) bzw. Preset 1200/600/200 | Alarmzeilen in Mail/SMS/Telegram und im Ortsvergleich | eskaliert bis MAJOR |
| 4 | **Anzeige** `metric_catalog.py:346-347`, `trip_report.py:719-721` | Ampel 300/800/1500, Höhepunkt 1000 | Zellfarbe in allen Tabellen, Zeile „⚡ Hohe Gewitterenergie" | – |

**Familie 3 ist die unterschätzte.** Ein Änderungsbetrag von 500 J/kg ist bei AROME
(Maximum 840 gemessen) praktisch unerreichbar und bei ECMWF (Maximum 3670) beiläufig.
Dieselbe Empfindlichkeitsstufe bedeutet je nach Gebiet etwas völlig anderes — und das trifft
den Alarmpfad, also den Teil des Produkts, der ohne Zutun des Nutzers laufen soll.

Familie 4 fällt mit „CAPE unsichtbar" (#1585, Konzept-Rang 5) ohnehin weg — sie ist hier nur
der Vollständigkeit halber verzeichnet und **kein Arbeitsgegenstand**.

## Zweiter Befund: die Schwelle ist nicht stumm, sie behauptet etwas

`thunder_level_from_signals()` hängt bei vorhandenem, aber unterschwelligem CAPE
`ThunderLevel.NONE` in die Signalliste — also „aktiv geprüft, unauffällig", nicht „keine
Aussage". Unter AROME ist das **immer** der Fall. Das ist die Fehlerklasse „leer ≠ unbekannt"
aus #1492, und es ist genau das, was Scheibe C behebt.

Bewacht wird das heutige Verhalten von `tests/tdd/test_thunder_level_from_signals_fusion.py`,
Fall `test_ac6_cape_gedeckelt_bei_leicht[500.0 → NONE]`.

## Die Modell-Herkunft: vorhanden, aber sie stirbt unterwegs

```
REGIONAL_MODELS[i]["id"]                    openmeteo.py:120-161  ("icon_d2", "meteofrance_arome", …)
   │ select_model() — first-match-wins über bounds nach priority   openmeteo.py:472-510
   ▼
ForecastMeta.model = model_id               openmeteo.py:823-825
   ├─ 5xx-Fallback tauscht das Modell AUS und markiert fallback_reason="model_5xx"   :1075-1078
   └─ Lückenfüller WEATHER-05b: fallback_model + fallback_metrics=[Parameternamen]   :1161-1169
   ▼
NormalizedTimeseries.meta.model    ← HIER ist die Fusion (thunder_enrichment.py:165). Herkunft verfügbar.
   │ compute_extended_metrics() liest NUR .data, nie .meta        weather_metrics.py:715-810, 938-941
   ▼
SegmentWeatherSummary(cape_max_jkg=…)       models.py:388-431  ← KEIN Herkunftsfeld. Hier stirbt sie.
   │ weather_snapshot._serialize_summary()                        weather_snapshot.py:201-215
   ▼
JSON-Schnappschuss (nur "provider", nicht das Modell)
   │ _deserialize_timeseries()                                    weather_snapshot.py:281
   ▼
Reload: ForecastMeta(model="snapshot")      ← Originalmodell unwiderruflich ersetzt
```

**Gute Nachricht für Familie 1:** Die Fusion sitzt oberhalb der Sterbestelle. `meta` ist dort
im Zugriff — `_fuse_thunder_levels(reihe.data)` bekommt es heute bloß nicht übergeben
(`thunder_enrichment.py:84, 165`). Ein Parameter mehr, kein neuer Mechanismus.

**Gute Nachricht für die Feld-Herkunft:** Der Lückenfüller führt zwar nur *ein*
`fallback_model` je Reihe, aber `fallback_metrics` nennt die Parameternamen. Für CAPE genügt
das vollständig: steht `"cape"` darin, gilt `fallback_model`, sonst `meta.model`.
(`cape` ist nachfüllbar — `_PARAM_TO_FIELD["cape"]`, `openmeteo.py:394`.)

**Schlechte Nachricht für Familien 2 und 3:** Beide arbeiten auf `SegmentWeatherSummary`,
also unterhalb der Sterbestelle. Sie brauchen ein zusätzliches Feld. Additiv ist das
schnappschuss-sicher — `_deserialize_summary` filtert über `dataclasses.fields()` und
ignoriert Unbekanntes still (`weather_snapshot.py:218-234`); alte Schnappschüsse laden weiter,
das Feld bleibt dort `None`. **Aber:** ein rückwirkendes Nachtragen gibt es nicht.

**Zwei Pfade haben die Herkunft nie:**
- Ortsvergleich: `summarize_points()` baut sich `model="aggregate"` (`weather_metrics.py:1077`),
  weil der Aufrufer nur eine nackte Punktliste übergibt.
- Nach Schnappschuss-Roundtrip: `model="snapshot"`.

## Kein einheitliches Modell-Vokabular

`meta.model` enthält je nach Provider etwas anderes:

| Quelle | Wert | Beleg |
|---|---|---|
| Open-Meteo | technische `id`: `icon_d2`, `meteofrance_arome`, `icon_eu`, `metno_nordic`, `ecmwf_ifs04` | `openmeteo.py:823-825` |
| DWD direkt | `"ICON-D2"` | `dwd.py:530-532` |
| Météo-France direkt | `"AROME-HIGHRES"` | `meteofrance.py:791-793` |
| GeoSphere | `"AROME"` bzw. `"NOWCAST"` | `geosphere.py:499-501, 614-616` |
| künstlich | `"aggregate"`, `"snapshot"`, `"fixture"` | s.o. |

Eine Schwellentabelle je Modell (Scheibe B) braucht deshalb **zuerst eine normalisierte
Schlüsselmenge** — `"AROME"`, `"AROME-HIGHRES"` und `"meteofrance_arome"` sind dieselbe
Modellwelt, `"snapshot"` ist gar keine.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/metric_format.py:315-370` | `_cape_low_min_jkg()`, `thunder_level_from_signals()` — Familie 1, Hauptschauplatz Scheibe C |
| `src/providers/thunder_enrichment.py:84-103, 165` | `_fuse_thunder_levels()` — hier muss die Herkunft ankommen |
| `src/services/risk_engine.py:57-60` | Familie 2, ungedeckelt bis HIGH |
| `src/app/metric_catalog.py:328-352` | Alle vier Zahlen; Ort einer künftigen Tabelle je Modell (Scheibe B) |
| `src/services/alert_preset.py:23,62` · `src/services/compare_alert.py:43,61` | Familie 3, Δ-Schwellen Trip + Ortsvergleich |
| `src/app/models.py:81-95` (`ForecastMeta`), `:388-431` (`SegmentWeatherSummary`) | Herkunft vorhanden / Herkunft fehlt |
| `src/services/weather_metrics.py:715-810, 938-941, 1055-1089` | Aggregation; `_compute_cape`; `summarize_points` (Compare, `model="aggregate"`) |
| `src/services/weather_snapshot.py:201-234, 273-281` | Persistenz; Roundtrip ersetzt das Modell durch `"snapshot"` |
| `src/providers/openmeteo.py:120-161, 394, 472-535, 823-825, 1075-1078, 1131-1172` | Modellwahl, 5xx-Fallback, Lückenfüller |

## Existing Patterns

- **Quellenabhängige Fallunterscheidung gibt es** — `thunder_routing.py:63-67` (`_REGIONS`,
  first-match-wins) plus getrennte Vertretungstabelle `_VERTRETUNG` (`:88-92`, ADR-0047).
  Das ist das Vorbild für „Tabelle statt Sonderfall im Code".
- **Eine modell-/quellenabhängige numerische Schwelle gibt es NIRGENDS.** Weder im RiskEngine
  noch in `weather_metrics` wird `meta.model` oder `grid_res_km` für Schwellenlogik gelesen.
  Scheibe B baut damit ein Muster, das es im Repo noch nicht gibt — das ist der eigentliche
  Architektur-Anteil dieser Arbeit.
- **Geteilte Leiter statt Kopien** — `_thunder_level_from_ladder()` (`metric_format.py:305-322`)
  ist die DRY-Vorgabe aus #1474c/#1481: jedes Signal bringt nur seine vier Zahlen mit.

## Dependencies

- **Upstream:** Open-Meteo-Modellwahl und Lückenfüller (`openmeteo.py`), Direktprovider
  (`dwd.py`, `meteofrance.py`, `geosphere.py`), Katalog (`metric_catalog.py`).
- **Downstream:** `dp.thunder_level` → laut **ADR-0025 die einzige Rohdatenquelle jeder
  Gewitteraussage in allen Kanälen** (Mail, SMS, Telegram, Ortsvergleich, Cockpit).
  Dazu Risikoübersicht im Trip-Report, Δ-Alarme, Wetter-Schnappschuss als Alarm-Vergleichsbasis.

## Existing Specs & ADRs

| Dokument | Was bindet |
|---|---|
| **ADR-0025** (Akzeptiert) | Genau eine Rohdatenquelle der Gewitteraussage: `dp.thunder_level`. Kein Kanal leitet Gewitter aus einem Aggregat ab. Beweispflicht: Tests durch die echte Einstiegsfunktion. |
| **ADR-0047** (Akzeptiert) | Vertretung zwischen Direktquellen; jedes Signal behält seine eigene Schwellentabelle, „keine Vermischung". |
| `feat_1474_gewitter_befund_stufen.md` | **AC-6:** CAPE gedeckelt bei LOW, eskaliert nie (500→NONE, 1200→LOW, 2630→LOW). **AC-7:** „keine Aussage" (`None`) ≠ „geprüft unauffällig" (`NONE`). **AC-8:** schärfstes Signal gewinnt. |
| `feat_1474c_blitzpotenzial_stufen.md` | **AC-7:** die 8 Bestandstests in `test_thunder_level_from_signals_fusion.py` müssen unverändert grün bleiben. |
| `docs/specs/modules/risk_engine.md` | Erkennbar **veraltet** — der seit #1474 produktive `LOW`-Zweig fehlt im Spec-Text. |
| `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.4b | Der Befund selbst, Rang 0 im Fahrplan. |

⚠️ Spec-Status ist im Repo kein Gültigkeitssignal (306 von 355 stehen auf `draft`). Die oben
zitierten ACs wurden vom Agenten **gegen den Code gegengeprüft** und sind live.

## Tests, die durch die Arbeit rot werden

| Test | Was er festnagelt | Betroffen von |
|---|---|---|
| `tests/tdd/test_thunder_level_from_signals_fusion.py::test_ac6_cape_gedeckelt_bei_leicht` | 500→NONE, 1200→LOW, 2630→LOW **ohne Modellangabe** | Scheibe C |
| dito `::test_ac6_gegenprobe_hohes_cape_eskaliert_nicht_auf_med_oder_high` | CAPE 2630 wird nicht MED/HIGH | Scheibe C (Signatur) |
| `tests/unit/test_configurable_thresholds.py::test_cape_risk_thresholds` | `{"medium":1000,"high":2000}` wörtlich | Scheibe B |
| `tests/integration/test_risk_engine.py::test_cape_high` / `::test_cape_moderate` | RiskEngine-Eskalation an 1000/2000 | Scheibe B, Familie 2 |

Eine Änderung an der **Zahl** `risk_thresholds["cape"]["medium"]` zieht beide Pfade
gleichzeitig rot — die Zahl wird an zwei Stellen mit unterschiedlicher Bedeutung gelesen.

## Risks & Considerations

1. **Die offene Kernfrage für `/20-analyse`: für welches Modell gilt die 1000 überhaupt als
   belegt?** Wenn für keines, wäre striktes „abstain, wo nicht belegt" gleichbedeutend mit
   „CAPE trägt vorerst nirgends bei" — auch in Deutschland, wo es heute auslöst. Das ist eine
   Produktentscheidung, keine technische. Zu klären, bevor eine Spec entsteht.
2. **Stiller Parameter-Rückfall vermeiden.** Ein `model: str | None = None` mit
   Bestandsverhalten bei `None` wäre bequem und genau das bekannte Anti-Muster: Aufrufer, die
   die Herkunft nicht übergeben, sähen aus wie geprüft. Sauberer: die Herkunft ist Pflicht,
   unbekannt heißt abstain — mit der Folge, dass die Bestandstests ihre Aufrufe explizit
   machen müssen (berührt den Regressionsanker AC-7 aus feat_1474c, formal, nicht inhaltlich).
3. **ADR-Pflicht prüfen.** Solange nur die Schwelle modellabhängig wird, ist es additiv.
   Sobald die Grundsatzentscheidung „CAPE misst Energie, kein Ereignis ⇒ Deckelung auf LOW"
   angetastet wird oder eine Tabelle je Modell als neues Muster entsteht, ist ein ADR fällig.
4. **Zwei Pfade ohne Herkunft** (Ortsvergleich `"aggregate"`, Schnappschuss `"snapshot"`)
   müssen in der Spec ausdrücklich behandelt werden — sonst entscheidet dort der Zufall.
5. **Scheibe B braucht Eichdaten** aus der Historical Forecast API. Kontingentlage vorher
   prüfen (`/api/scheduler/status`-Block aus #1329, Radar-Pfad dominiert den Verbrauch).
6. **Wirkung messen, nicht behaupten.** Der Nachweis für C/B gehört an die zugestellte
   Ausgabe bzw. an `dp.thunder_level` am Ort — ein grüner Funktionstest allein zeigt bei
   diesem Befund nachweislich nichts.

## Nebenbefunde (kein Arbeitsgegenstand)

- `src/services/comparison_engine.py:278-292` kommentiert „Thunder/CAPE/PoP for wandern
  scoring", CAPE fließt aber nachweislich **nicht** in `comparison_scoring.py` ein.
  Irreführender Kommentar → Sammel-Issue #1199.
- `docs/specs/modules/configurable_thresholds.md` (Z. 446, 472, 576) führt das CAPE-Raster auf
  eine **„WHO thunderstorm energy scale"** zurück. Die WHO publiziert keine CAPE-Skala; im
  ganzen Repo gibt es keinen weiteren Beleg. Erfundene Quellenangabe seit 2026-02-16 → #1199.

---

# Analysis

## Type

**Bug** mit entwurfsförmigem Fix — der Defekt läuft produktiv, die Behebung baut aber ein
Muster, das es im Repo noch nicht gibt (quellenabhängige numerische Schwelle).

## Befund A — die 1000 J/kg ist für kein Modell belegt

| Station | Beleg |
|---|---|
| Einführung | `78de329e` (2026-02-12) „CAPE (>=1000 J/kg) in Email-Highlights und Segment-Risk-Assessment" — **ohne Quellenangabe, ohne Issue-Bezug** |
| Verschiebung in den Katalog | `413caaa7`/`eff3e703` (2026-02-16) — nur verschoben, nicht hergeleitet |
| Anzeige-Ampel 300/800/1500 | `0b2cc5ed` (2026-07-22) — ausdrücklich als **PO-Schätzung** markiert, keine externe Quelle |
| Externer Anker | Gesamtkonzept 3.5b: NWS/SPC-Leiter 1000/2500/4000 — nennt **keine CAPE-Variante** |

Es gibt im Repo **keine** Stelle, die die 1000 einer Parcel-Variante (Mixed-Layer,
Most-Unstable, Surface-Based) zuordnet. Folge für Scheibe C: „abstain, wo nicht belegt"
bedeutet streng gelesen, dass CAPE **vorerst nirgends** beiträgt — auch in Deutschland.

## Befund B — der Δ-Pfad vergleicht Werte aus verschiedenen Modellen

`weather_change_detection.detect_changes()` (`:606-632`) hält `old.aggregated.cape_max_jkg`
gegen `new.aggregated.cape_max_jkg`. **Kein Abgleich der Herkunft** — nicht einmal der
`provider`-String wird verglichen; das Modell steht im Schnappschuss gar nicht erst
(`weather_snapshot.py:61-116` persistiert nur `segments[0].provider`).

Wechselt zwischen zwei Läufen das liefernde Modell (5xx-Rückfall, `openmeteo.py:1000-1078`),
wird AROME-CAPE gegen ICON-CAPE verrechnet. Weil `_classify_severity` (`:820-850`)
`ratio = |Δ| / Schwelle` rechnet (≥2,0 → MAJOR), kann **allein der Modellwechsel** einen
schwersten Alarm erzeugen, ohne dass sich das Wetter geändert hat. Kein Guard, kein Test.

## Technischer Ansatz (empfohlen)

1. **Neues Feld statt Kontextobjekt:** `SegmentWeatherSummary.cape_model_id: Optional[str] = None`
   — der **normalisierte** Schlüssel, nicht der Rohwert aus `meta.model`. Schnappschuss-sicher;
   alte Daten laden mit `None`, und `None` heißt korrekterweise „nicht belegt".
2. **Neues Modul `src/app/model_registry.py`** nach dem Vorbild `thunder_routing._REGIONS`:
   `normalize_model_id(raw) -> str | None` bündelt das uneinheitliche Vokabular
   (`icon_d2`/`ICON-D2`, `meteofrance_arome`/`AROME-HIGHRES`/`AROME`, …) auf kanonische
   Schlüssel; `aggregate`/`snapshot`/`fixture`/Unbekanntes → `None`. Scheibe B erweitert
   **dieselbe** Tabelle um Zahlen, statt eine zweite zu bauen.
3. **Fallback-Vorrang für CAPE:** steht `"cape"` in `meta.fallback_metrics`, gilt
   `meta.fallback_model`, sonst `meta.model`.
4. **Drei Andockpunkte:**
   - Familie 1: `_fuse_thunder_levels()` reicht die Herkunft durch;
     `thunder_level_from_signals()` bekommt einen **keyword-only Parameter ohne Default**.
   - Familie 2: **eigene** `_check_cape()` in `risk_engine.py` — keine CAPE-Sonderlogik in
     `_check_catalog_metric()`, das generisch für sechs weitere Metriken arbeitet.
   - Familie 3: Gate vor der Delta-Berechnung in `detect_changes()`, analog zum bestehenden
     Ordinal-Sonderfall.
5. **Kein stiller Rückfall, doppelt abgesichert:** syntaktisch (kein Default an der
   Signaturgrenze → fehlender Aufruf bricht hart) und semantisch (unbekannt → `None` → an
   allen drei Stellen wie „nicht belegt" behandelt).

## Scheibenfolge

| Scheibe | Inhalt | Wirkungsnachweis | LoC (Prod/Test) |
|---|---|---|---|
| **C0** | Fundament: `cape_model_id`, `model_registry.py`, Befüllung in `weather_metrics.py` — **verhaltensneutral** | AROME-Segment trägt den kanonischen Schlüssel, Compare-Segment `None` | ~60 / ~25 |
| **C1** | Familie 1 (Fusion) | `dp.thunder_level` liefert bei unbelegtem Modell und hohem CAPE `None` statt `LOW` — über die echte Einstiegsfunktion (ADR-0025) | ~35 / ~50 |
| **C2** | Familie 2 (RiskEngine) | Trip-Risikoübersicht zeigt kein `THUNDERSTORM MODERATE/HIGH` mehr aus reinem CAPE | ~35 / ~35 |
| **C3** | Familie 3 (Δ-Alarme), nur Beleg-Gate | Δ-CAPE-Sprung bei unbelegtem Modell erzeugt keine Alarmzeile | ~40 / ~40 |
| **B** | geeichte Tabelle je Modell (Historical Forecast API) | Überschreitungshäufigkeit je Modell vergleichbar | eigener Workflow |

C0 ist Voraussetzung, C1–C3 danach in beliebiger Reihenfolge. Alle Scheiben unter dem
LoC-Limit von 250.

## Risiko

- **Sichtbarste Änderung ist Familie 2.** Der RiskEngine-Pfad ist heute der **einzige** Weg zu
  `THUNDERSTORM MODERATE/HIGH` allein aus CAPE — die Fusion deckelt ohnehin auf `LOW`. Ist die
  Beleg-Menge zunächst leer, verschwindet dieses Risiko **überall**, auch in Deutschland.
  ⚠️ Dieselbe Eskalation widerspricht allerdings der Projektentscheidung „CAPE misst Energie,
  kein Ereignis" (#1585, feat_1474 AC-6). Ihr Verschwinden ist damit eher eine Korrektur als
  ein Verlust.
- **CAPE als einziges Signal:** strukturell selten — `thunder_routing` deckt über den
  ICON-EU-Lückenfüller fast überall ein Blitzsignal ab. Aber bei fail-soft-Ausfall der
  Gewitterquelle (`enrich_thunder` schluckt Ausnahmen) war CAPE bisher der letzte Auslöser.
  Dort wird aus „kein Gewitter" ein „keine Aussage" — korrekt nach AC-7, aber sichtbar.
- **Dauerhafte Lücke, bewusst:** Ortsvergleich (`model="aggregate"`) und Schnappschuss-Reload
  (`model="snapshot"`) haben nie Herkunft ⇒ CAPE-Δ-Alarme im Ortsvergleich verstummen
  **dauerhaft**, nicht nur bis Scheibe B. Muss als akzeptierter Scope-Schnitt in der Spec
  stehen, sonst wirkt es später wie ein Fehler.

## Eichung ist verfügbar — gemessen 2026-08-08

Die Historical Forecast API liefert die Modellklimatologie ohne Sammelphase: eine
Konvektionssaison (Juni–August 2025), fünf Modelle, 2208 Stunden je Modell, Antwort in
Sekunden. **Kein eigenes Archiv nötig, kein Blocker für die Eichung.**

Anteil der Stunden mit CAPE ≥ 1000 J/kg (Saison-Klimatologie):

| Modell | GR20 / Petra Piana | München |
|---|---|---|
| AROME | 0,5 % (P99 = **720**) | 0,7 % |
| ICON-D2 | keine Abdeckung (Gebietsgrenze) | 1,0 % |
| ICON-EU | **8,1 %** | 1,4 % |
| ECMWF | 3,6 % | 4,1 % |
| GFS | 3,5 % | 3,7 % |

🔴 **Der Ort streut so stark wie das Modell.** ICON-EU überschreitet auf Korsika 8,1 %, in
München 1,4 % — Faktor 6 im selben Modell. Eine Tabelle **nur je Modell reicht nicht**; sie
braucht eine Gebietsdimension. Entscheidung: die bereits bestehenden Gewitter-Zuständigkeits-
gebiete aus `thunder_routing` als Gebietsraster — bounded, als statische Tabelle im Repo
prüfbar, ohne Abrufe zur Laufzeit. Perzentil je einzelnem Ort wäre genauer, kostet Abrufe je
Ort plus Zwischenspeicherung ⇒ als spätere Verfeinerung notiert, nicht in dieser Arbeit.

### Verhältnis zu den Zahlen im Issue (Klarstellung)

Die Zahlen im Issue (AROME 0,0 % · ICON-D2 17,3 % · ICON-EU 31,9 % · ECMWF 65,3 % · GFS 40,3 %)
stammen aus einer **Episoden**-Messung in **Südfrankreich** am laufenden Vorhersagefenster.
Am 2026-08-08 nachgemessen, gleicher Ort, gleiches Verfahren: 0,0 / 14,5 / 50,4 / 52,4 / 19,0 %
— **die Messung reproduziert, der Kernbefund steht.** Die Saison-Tabelle oben ist eine andere
Größe (Klimatologie, andere Orte) und **kein** Widerspruch dazu. Beide werden gebraucht: die
Episode belegt den Fehler, die Saison ist die Eichgrundlage.

## Reihenfolge (PO-Entscheidung 2026-08-08, ersetzt „C dann B")

Der Eichlauf kommt **zuerst**. Damit ist die Beleg-Menge nie leer, und die im Risikoteil
beschriebene Verstummung in Deutschland tritt gar nicht erst ein.

| Scheibe | Inhalt |
|---|---|
| **B0** | Eichlauf: einmaliges Auswertungsskript → statische Tabelle Modell × Gebiet |
| **C0** | Fundament: `cape_model_id`, `model_registry.py`, Befüllung — nimmt die Tabelle auf |
| **C1** | Familie 1 (Fusion) |
| **C2** | Familie 2 (RiskEngine) |
| **C3** | Familie 3 (Δ-Alarme), Beleg-Gate |

„Abstain" bleibt nötig, aber nur noch dort, wo **wirklich keine Herkunft existiert**
(Ortsvergleich `model="aggregate"`, Schnappschuss-Reload `model="snapshot"`, unbekannte
Modelle) — nicht flächendeckend.

## Entschiedene Punkte

- [x] Umfang: Familien 1, 2 und 3 (Familie 4 entfällt mit #1585)
- [x] Reihenfolge: Eichlauf zuerst, dann Fundament, dann die drei Wirkstellen
- [x] Befund B (Falschalarm durch Modellwechsel): **eigenes Bug-Ticket**, direkt nach C3
