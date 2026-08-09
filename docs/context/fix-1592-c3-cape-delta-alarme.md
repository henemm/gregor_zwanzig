# Context: #1592 Scheibe C3 — CAPE-Δ-Alarme (Schwellenfamilie 3)

**Workflow:** `fix-1592-c3-cape-delta-alarme` · **Issue:** #1592 · **Basis:** `origin/main` `0461ed63`
**Vorgänger live:** B0+C0+C1 (PR #1611), C2 (PR #1612, `ac1343e1`)

## Request Summary

Die letzte noch modellblinde CAPE-Schwellenfamilie sind die **Änderungsalarme** (Δ): ein
Sprung von 500 J/kg (Katalog-Default) bzw. 1200/600/200 (Empfindlichkeitsstufen) löst
unabhängig davon aus, aus welchem Wettermodell der Wert stammt. Bei AROME ist dieser Sprung
praktisch unerreichbar, bei ECMWF beiläufig.

## Zentrale Feststellung dieser Phase: der Zuschnitt von gestern greift zu kurz

Das Vorgänger-Kontextdokument (`docs/context/fix-1592-cape-modellschwelle.md:258`) schneidet
C3 auf **„nur Beleg-Gate"** zu: kein Alarm, wenn die Modell-Herkunft unbekannt ist. Dasselbe
Dokument benennt zwei Zeilen weiter oben (`:27`) den eigentlichen Fehler aber anders:

> Ein Änderungsbetrag von 500 J/kg ist bei AROME (gemessenes Maximum 840) praktisch
> unerreichbar und bei ECMWF (Maximum 3670) beiläufig.

Diese beiden Aussagen passen nicht zusammen. Bei AROME **ist** die Herkunft bekannt
(`meteofrance_arome`) — ein Beleg-Gate lässt den Fall durch und die 500/600 bleiben stehen.
Der benannte Fehler wäre nach C3 unverändert vorhanden.

### Gemessen (2026-08-08, offline, dieser Worktree)

Der Zuschnitt „nur Gate" stützte sich auf die Annahme, im Ortsvergleich und nach einem
Schnappschuss-Reload gebe es keine Herkunft. **Beides trifft für den Alarmpfad nicht zu:**

```
ALARM-PFAD    cape_model_id = 'icon_d2'   (echte Provider-Meta)
ANZEIGE-PFAD  cape_model_id = None        (summarize_points, model="aggregate")
SERIALISIERT  cape_model_id -> icon_d2
DESERIALISIERT cape_model_id = 'icon_d2'
```

- **Ortsvergleich:** Es gibt **zwei** Compare-Pipelines. Die *Anzeige*-Pipeline aggregiert über
  Orte (`weather_metrics.py:1093`, `model="aggregate"`) und hat keine Herkunft. Die
  *Alarm*-Pipeline holt je Ort einen einzelnen Provider-Abruf
  (`compare_location_weather_source.py:103-119` → `segment_weather.py:280-281` →
  `weather_metrics.py:802`) und trägt die **echte** Herkunft. Die im Vorgängerdokument
  (`:276-279`) als „dauerhafte Lücke, bewusst" notierte Verstummung des Ortsvergleichs
  existiert im Alarmpfad **nicht**.
- **Schnappschuss:** `_serialize_summary`/`_deserialize_summary`
  (`weather_snapshot.py`, geteilt mit `compare_weather_snapshot.py:25-29`) reichen
  `cape_model_id` unverändert durch. Nur die separat rekonstruierte Stundenreihe bekommt
  `meta.model="snapshot"` (`weather_snapshot.py:281`) — ein anderes Objekt. Der Feldkommentar
  in `app/models.py:447-454`, der „Schnappschuss-Reload" als `None`-Fall nennt, beschreibt
  damit den Lesepfad falsch.

**Folge:** Ein reines Beleg-Gate würde in beiden Alarmpfaden fast nie greifen. Es bewachte
nur noch den Restfall „unbekanntes Modell" — und ließe den Fehler, wegen dessen das Issue
existiert, unangetastet.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/weather_change_detection.py:598-658` | **Die** Vergleichsstelle: `triggered = abs(delta) > threshold` (`:632`) |
| `src/services/weather_change_detection.py:820-850` | `_classify_severity` — `delta/schwelle`, ≥1,5 MODERATE, ≥2,0 MAJOR |
| `src/services/weather_change_detection.py:628-630` | Präzedenz: `_ordinal_levels`-Sonderpfad je Metrik (#1460) |
| `src/services/weather_change_detection.py:51` | `_ALERT_METRIC_TO_SUMMARY_FIELD[CAPE] = "cape_max_jkg"` |
| `src/services/weather_change_detection.py:456-560` | `from_alert_rules()` — füllt `_thresholds` **pro Trip**, nicht pro Segment |
| `src/app/metric_catalog.py:337` | `default_change_threshold=500.0` |
| `src/app/metric_catalog.py:807-828` | `get_change_detection_map()` |
| `src/services/alert_preset.py:62` | `(AlertMetric.CAPE, DELTA, 1200, 600, 200)` |
| `src/services/compare_alert.py:44,447-457` | Ortsvergleich: alle Metriken hart auf `"standard"` → CAPE Δ 600 |
| `src/services/deviation_alert_engine.py:172-198,283-284` | Detektor-Auswahl, generischer Wrapper (keine CAPE-Logik) |
| `src/services/trip_alert.py:335-350,604-636` | Trip-Seite derselben Kette |
| `src/app/model_registry.py:120-142` | `CAPE_THRESHOLDS_JKG` (11 Einträge), `cape_threshold_jkg()` |
| `src/providers/thunder_routing.py:64-85` | `thunder_region_for(lat, lon)` → `FR`/`DE_ALPEN`/`EU_REST` |
| `src/app/models.py:454` | `SegmentWeatherSummary.cape_model_id` |
| `src/app/models.py:324-329,371-384,472-489` | Koordinaten am Vergleichspunkt: `segment.start_point.lat/lon` |
| `scripts/eichung_cape_schwelle.py` | Eichlauf B0 (Historical Forecast API) |
| `frontend/src/lib/generated/alertPresetThresholds.generated.json:2-7` | `cape: {entspannt:1200, standard:600, sensibel:200, kind:"delta"}` |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:50-55,231-242` | `levelToThreshold()` rendert **eine Zahl**: `Δ ≥ 600 J/kg` |
| `scripts/generate_alert_preset_table.py` · `tests/tdd/test_alert_preset_table_parity.py` | Generator + Frische-Ratsche |

## Existing Patterns

- **Abstain-Muster (C1/C2, kanonisch):** `providers/thunder_enrichment.py:172-187` löst
  `cape_threshold_jkg(effective_cape_model_id(meta), thunder_region_for(lat, lon))` auf; ist
  das Ergebnis `None`, trägt CAPE **kein** Signal bei — „keine Aussage", nicht „unauffällig".
  Abgesichert syntaktisch durch einen keyword-only Parameter **ohne Default**
  (`output/metric_format.py:315-372`), damit ein vergessener Aufruf hart bricht statt still
  zurückzufallen.
- **Sonderpfad je Metrik im Δ-Loop:** `_ordinal_levels` (#1460) behandelt Gewitterstufen
  bereits abweichend von `abs(delta) > threshold` — die Bauform für einen CAPE-Sonderpfad
  existiert an derselben Stelle.
- **Aggregationsregel `"agreement"`** (`weather_metrics.py:837,1196-1203`): uneinige Herkunft
  über Segmente → `None`, nie ein zufälliger Erstwert.
- **Eichverfahren (dokumentiert, PO-Recherche):** Quantil-Mapping über eine Konvektionssaison
  (April–September), `x aus A → F_B⁻¹(F_A(x))`; praktisch „Perzentil des jeweiligen Modells"
  statt Absolutwert. Historische Läufe aus Open-Meteos Historical Forecast API.

## Dependencies

- **Upstream:** `model_registry` (Eichtabelle, Normalisierung), `thunder_routing` (Gebiet),
  `SegmentWeatherSummary.cape_model_id` (Herkunft), `alert_preset._PRESET_TABLE` (Ladder).
- **Downstream:** Trip-Alarmzeilen (Mail/SMS/Telegram), Ortsvergleichs-Alarme,
  `WeatherChange.threshold` (wird im Alarmtext mitgeführt), Frontend-Anzeige der
  Empfindlichkeitsstufen, `alertPresetThresholds.generated.json` + Parität-Ratsche.

## Existing Specs & ADRs

- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` (B0+C0+C1) — Abstain-Regel `:137-140`,
  Familie 3 ausdrücklich ausgeklammert `:32-38`.
- `docs/specs/modules/fix_1592_c2_cape_riskengine.md` (C2) — Familie 3 ausgeklammert `:29-33`.
- `docs/context/fix-1592-cape-modellschwelle.md` — Vorgänger-Kontext; C3-Zuschnitt `:245,258`.
- **ADR-0048** „Modellabhängige Schwellen statt einer Zahl" — Grundsatz: *feste Schwellen nie
  über Modellgrenzen tragen*; hält fest, dass Δ-Alarme (C3) noch nicht umgestellt sind.
- **ADR-0009** Alerts sind Δ-Wächter gegen den letzten Briefing-Stand.
- **ADR-0043** Die Empfindlichkeitsstufe ist der **einzige** Alarm-Regler — eine
  modellabhängige Zahl darf keinen zweiten Regler einführen, sondern muss dieselbe Stufe
  gebietsweise gleich *bedeuten* lassen.

## Belegte und unbelegte Zahlen

Für die Δ-Werte **1200/600/200** und den Katalog-Default **500** gibt es **keine dokumentierte
Quelle** — weder im Repo (`docs/specs/_archive/modules/issue_846_alert_preset.md:87`,
`docs/specs/modules/feat_864_859_alert_presets.md:128` führen sie ohne Herleitung) noch
veröffentlicht. Auch das eigene Gedächtnis kennt eine veröffentlichte Eichung nur für CAPE-
**Niveaus**, nicht für Sprungbeträge.

Auffällig: Die vier Zahlen sind glatte Vielfache der alten, modellblinden Niveau-Schwelle von
1000 J/kg — 1,2 / 0,6 / 0,2 bzw. 0,5. Das ist eine **Rekonstruktion, keine Fundstelle**; sie
ist plausibel, aber nirgends belegt.

## Wege zu einer modellabhängigen Δ-Schwelle (für die Analysephase)

1. **Anteil der geeichten Niveau-Schwelle** — Δ-Schwelle = Faktor × `cape_threshold_jkg(modell,
   gebiet)`, Faktoren 1,2/0,6/0,2 aus der heutigen Leiter. Kein neuer Messlauf; verhält sich
   dort, wo die geeichte Schwelle 1000 beträgt, exakt wie heute. Schwäche: der Anker 1000 ist
   selbst unbelegt.
2. **Eigener Δ-Eichlauf** — `scripts/eichung_cape_schwelle.py` erweitern: die API-Antwort
   enthält `hourly.time` bereits, das Skript liest es nur nicht aus (`:169-179`). Tagesmaxima
   bilden, Differenzen, 95. Perzentil. **Keine neuen Abrufe** (~13 Abrufe gesamt, Antwort in
   Sekunden), gleiche Saison, gleiche Referenzpunkte.
3. **Nur Beleg-Gate** (Zuschnitt von gestern) — behebt den benannten Fehler nicht, s.o.

## Risks & Considerations

- **Die Schwelle steuert auch die Eskalation.** `_classify_severity` rechnet
  `delta/schwelle`; MAJOR ab Faktor 2. Unter AROME ist Faktor 2 bei 500 rechnerisch kaum
  erreichbar, unter ECMWF beiläufig — der Modellfehler wirkt doppelt: beim Auslösen **und**
  bei der Dringlichkeit.
- **Die Schwelle wird pro Trip aufgelöst, gebraucht wird sie pro Segment.** `_thresholds` ist
  ein Dict pro Service-Instanz; Modell und Gebiet variieren je Segment. Die Auflösung muss
  deshalb **in** `detect_changes()` erfolgen, nicht bei der Konstruktion.
- **Frontend zeigt eine feste Zahl.** `levelToThreshold()` rendert `Δ ≥ 600 J/kg`; der Typ
  erzwingt `number`. Wird die wirksame Schwelle gebietsabhängig, ist die Anzeige nicht mehr
  wörtlich wahr. Zu entscheiden: Anzeige unverändert lassen (nominale Leiter) oder umformulieren.
- **ADR-0043-Konflikt vermeiden:** Eine modellabhängige Zahl darf nicht als zweiter Regler
  auftreten. Sie ist die *Umrechnung* derselben Empfindlichkeitsstufe in die jeweilige
  Modellwelt — das ist genau der Zweck von ADR-0048.
- **Empfindlichkeit steigt.** Die geeichten Niveau-Schwellen liegen überwiegend unter 1000
  (FR/AROME 300, DE_ALPEN/ICON-EU 360). Weg 1 senkt die Δ-Schwellen dort deutlich →
  **mehr** Alarme als heute. Das ist der beabsichtigte Effekt („in Frankreich löst nie aus"),
  muss aber vor der Freigabe beziffert werden.
- **Abgrenzung #1601:** Ob Anker und frischer Wert aus **derselben** Quelle stammen, prüft
  weiterhin niemand. Gemessen: der Anker trägt eine echte, eingefrorene `cape_model_id`, der
  frische Wert eine aktuelle — sie können abweichen. Bleibt eigenes Ticket, direkt nach C3.

## Analysis

### Type
Bug (Schwellenfehler mit nutzersichtbarer Wirkung im Alarmpfad)

### Entscheidung: Umrechnung statt Messreihe (PO 2026-08-08)

Auf die Frage nach der Δ-Eichung: **„was ist ein pragmatischer Weg? Du bist schon wieder
dabei daraus ein Forschungsprojekt zu machen."** Der eigene Δ-Messlauf entfällt damit.

Gewählt: **Weg 1 — die bestehende Leiter in die jeweilige Modellwelt umrechnen.**

```
wirksame Δ-Schwelle = Preset-Zahl × cape_threshold_jkg(modell, gebiet) / 1000
```

Die 1000 ist kein neu gesetzter Wert, sondern die bis Scheibe C1 überall gültige
CAPE-Schwelle — genau die Welt, für die die Leiter 1200/600/200 geschrieben wurde. Wo die
geeichte Schwelle 1000 beträgt, ändert sich nichts. Keine neue Tabelle, kein Abruf, keine
erfundene Zahl.

### Gemessene Wirkung (alle 11 geeichten Kombinationen)

| Modell × Gebiet | geeicht | entspannt | standard | sensibel | Faktor |
|---|---|---|---|---|---|
| meteofrance_arome × FR | 300 | 1200 → 360 | 600 → **180** | 200 → 60 | 0,30 |
| icon_d2 × FR | 300 | 1200 → 360 | 600 → 180 | 200 → 60 | 0,30 |
| icon_eu × EU_REST | 300 | 1200 → 360 | 600 → 180 | 200 → 60 | 0,30 |
| meteofrance_arome × EU_REST | 310 | 1200 → 372 | 600 → 186 | 200 → 62 | 0,31 |
| icon_d2 × DE_ALPEN | 300 | 1200 → 360 | 600 → 180 | 200 → 60 | 0,30 |
| icon_eu × DE_ALPEN | 360 | 1200 → 432 | 600 → 216 | 200 → 72 | 0,36 |
| meteofrance_arome × DE_ALPEN | 380 | 1200 → 456 | 600 → 228 | 200 → 76 | 0,38 |
| ecmwf_ifs04 × EU_REST | 420 | 1200 → 504 | 600 → 252 | 200 → 84 | 0,42 |
| ecmwf_ifs04 × DE_ALPEN | 650 | 1200 → 780 | 600 → 390 | 200 → 130 | 0,65 |
| ecmwf_ifs04 × FR | 710 | 1200 → 852 | 600 → 426 | 200 → 142 | 0,71 |
| icon_eu × FR | 850 | 1200 → 1020 | 600 → 510 | 200 → 170 | 0,85 |

🔴 **Alle Faktoren liegen unter 1 — die Δ-Schwellen sinken überall, nicht nur in Frankreich.**
Das ist die ehrliche Folge davon, dass die alte 600 an nichts geeicht war: an keinem der
Referenzpunkte erreicht das 95. Perzentil der Modellklimatologie 1000 J/kg. Es bedeutet
**mehr CAPE-Änderungsalarme als heute**, am stärksten unter AROME und ICON-D2 (Faktor 0,30).
Diese Zahl gehört vor die Freigabe.

**Eine untere Grenze ist bereits eingebaut** und muss nicht erfunden werden: die Eichtabelle
selbst hat den Boden `MIN_THRESHOLD_JKG = 300` (`scripts/eichung_cape_schwelle.py:70`).
Der Umrechnungsfaktor kann deshalb nicht unter 0,30 fallen.

### Technischer Ansatz

1. **Auflösung in `detect_changes()`**, nicht bei der Konstruktion — Modell und Gebiet
   variieren je Segment, `_thresholds` ist aber ein Dict pro Service-Instanz. Andockpunkt ist
   der bestehende Sonderpfad je Metrik (`weather_change_detection.py:628-630`, `_ordinal_levels`).
2. **Ein Nachschlag, zwei Wirkungen:** `cape_threshold_jkg(...)` liefert `None` → **kein
   Alarm** (Abstain, identisch zu C1/C2, deckt den ursprünglich geplanten Beleg-Gate-Fall ab);
   liefert eine Zahl → Umrechnung.
3. **Die wirksame Schwelle muss ins Ereignis.** `WeatherChange.threshold` wird nicht nur im
   Alarmtext genannt (`output/renderers/alert/render.py:494`), sondern dort **nachgeprüft**
   (`output/renderers/alert/model.py:97-104`, `over_thr`) und zur Sortierung benutzt
   (`render.py:725`). Trüge das Ereignis die nominale Zahl, während mit der umgerechneten
   ausgelöst wurde, stünde im Alarm „unter Schwelle" — und die Reihenfolge wäre falsch.
4. **Referenzwert benannt ablegen**, nicht als nackte 1000 im Code: Konstante in
   `model_registry.py` mit Begründung (die vor #1592 universelle Schwelle).
5. **Anzeige** (PO: in dieser Scheibe mitmachen): `levelToThreshold()` gibt für CAPE heute
   `Δ ≥ 600 J/kg` zurück — eine Zahl, die so nirgends mehr wirkt. Sie wird als Richtwert
   gekennzeichnet und um den Hinweis auf die Umrechnung ergänzt. Die generierte Datei und
   ihr Typ (`number`) bleiben unverändert, damit Generator und Frische-Ratsche nicht brechen.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/app/model_registry.py` | MODIFY | Referenzniveau-Konstante + Umrechnungsfunktion |
| `src/services/weather_change_detection.py` | MODIFY | CAPE-Sonderpfad in `detect_changes()`: Abstain + Umrechnung + wirksame Schwelle ins Ereignis |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | CAPE-Schwellentext als Richtwert kennzeichnen |
| `frontend/src/lib/components/alerts-tab/issue_864_alert_metric_levels.test.ts` | MODIFY | Erwartung für CAPE nachziehen (`:75`) |
| `tests/tdd/test_cape_delta_modellschwelle.py` | CREATE | Verhaltenstests (Umrechnung, Abstain, Ereignis-Schwelle, Eskalationsstufe) |

**Nicht angefasst:** `alert_preset.py` (die Leiter bleibt die nominale Empfindlichkeitsstufe —
ADR-0043: ein Regler), `metric_catalog.py`, `compare_alert.py` (erbt die Wirkung über
dieselbe `detect_changes()`), Generator und generierte Datei.

### Scope Assessment
- Dateien: 3 Produktiv (2 Python, 1 TypeScript) + 2 Test
- Geschätzt: ~55 Produktiv / ~90 Test
- Risiko: **MEDIUM** — schmaler Eingriff, aber nutzersichtbar in Alarmmenge und -text
- Scope-Art: **full-stack** (Frontend berührt ⇒ Browser-Gate beim Ausliefern greift)

### Offene Punkte für die Spec
- Wortlaut des Anzeige-Hinweises (PO entscheidet über die ACs)
- Ob der Alarmtext die Umrechnung erwähnt oder nur die wirksame Zahl nennt

## Testlage

Kein einziger bestehender Test verbindet `cape_model_id`/Gebiet mit dem Δ-Alarmpfad — dieser
Bereich ist heute testfrei. Betroffene Bestandstests:

- `tests/unit/test_change_detection.py:417,490-505` (Katalog-Default 500 für `cape_max_jkg`)
- `tests/tdd/test_issue_846_alert_preset.py:237-243` (`test_ac6_entspannt_cape_threshold_1200_delta`)
- `tests/tdd/test_alert_preset_table_parity.py` (Frische-Ratsche Generat)
- `tests/unit/test_alert_metric_identity_delivery.py:73,80,112,120,260-282`
- `tests/tdd/test_compare_alert_metric_gating.py`
