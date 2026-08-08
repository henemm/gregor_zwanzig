---
entity_id: fix_1592_s1_cape_modellschwelle
type: bugfix
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [gewitter, cape, model-registry, thunder-fusion, issue-1592]
---

# CAPE bekommt eine geeichte Schwelle je Modell und Gebiet statt einer erfundenen 1000 (Issue #1592, Scheiben B0+C0+C1)

## Approval

- [x] Approved — PO-„go" 2026-08-08, Beleg als Kommentar in Issue #1592

## Purpose

Die Gewitter-Fusion (`thunder_level_from_signals()`, Familie 1) bewertet CAPE heute gegen EINE
feste Schwelle (1000 J/kg), egal welches Wettermodell den Wert geliefert hat. CAPE ist aber ein
**modellabhängiges Konstrukt** — je nach Parcel-Definition bedeutet derselbe Zahlenwert etwas
anderes (AROME/Most-Unstable liegt strukturell niedriger als ECMWF/GFS). Ergebnis: in Frankreich
(AROME, GR20 inbegriffen) überschreitet CAPE die 1000er-Marke praktisch nie — CAPE trägt dort
faktisch NIE zur Gewitterstufe bei, obwohl reale, bestätigte Gewitterlagen dort CAPE-Werte weit
über dem lokal Üblichen zeigen. In Deutschland/Mitteleuropa dagegen wird dieselbe Marke deutlich
häufiger überschritten. Diese Scheibe ersetzt die eine erfundene Zahl durch eine **geeichte
Tabelle je Modell × Gebiet** (das 95. Perzentil der Modellklimatologie, mindestens 300 J/kg) und
sorgt dafür, dass CAPE dort, wo die Modell-Herkunft unbekannt ist (Ortsvergleich,
Schnappschuss-Reload), ehrlich **keine Aussage** trifft statt fälschlich "kein Gewitter" zu
behaupten.

**Bewusst NICHT Teil dieser Scheibe:** Familie 2 (`RiskEngine._check_cape`, die
Trip-Risikoübersicht) und Familie 3 (Δ-Alarm-Beleg-Gate) nutzen weiterhin die feste
1000/2000-J/kg-Katalogschwelle — sie sind eigene Folgescheiben (C2, C3). Der Same-Model-Guard für
den Δ-Alarm-Pfad (Befund B aus der Analyse: ein Modellwechsel zwischen zwei Läufen kann heute
allein einen Alarm auslösen) ist ein eigenes Bug-Ticket. Ebenfalls nicht Teil: Perzentil je
einzelnem Ort statt je Gebiet (spätere Verfeinerung), und Familie 4 (Anzeige-Ampel) — die entfällt
ohnehin mit #1585 ("CAPE unsichtbar").

## Source

- **File:** `scripts/eichung_cape_schwelle.py` (neu), `src/app/model_registry.py` (neu),
  `src/app/models.py`, `src/services/weather_metrics.py`, `src/output/metric_format.py`,
  `src/providers/thunder_enrichment.py`, `src/providers/thunder_routing.py`
- **Identifier:** `normalize_model_id()`, `effective_cape_model_id()`, `cape_threshold_jkg()`
  (alle neu, `model_registry.py`), `SegmentWeatherSummary.cape_model_id` (neues Feld),
  `thunder_region_for()` (neu, `thunder_routing.py`), `thunder_level_from_signals()`
  (Signaturänderung, `metric_format.py`), `_fuse_thunder_levels()`/`enrich_thunder()`
  (`thunder_enrichment.py`)

**Schicht:** ausschließlich Python-Core (`src/app/`, `src/services/`, `src/output/`,
`src/providers/`) plus ein einmaliges Auswertungsskript unter `scripts/`. Kein Go, kein Frontend
— CAPE ist bereits eine normale, wählbare Metrik; diese Scheibe ändert nur die interne
Schwellen-Bestimmung, keine Bedienoberfläche.

## Estimated Scope

- **LoC:** ~140-190 Quellcode (davon ~40-60 die statische Eichtabelle, keine Logik) + ~150-220
  Tests. Das einmalige Skript selbst zählt nicht gegen den Laufzeitpfad, ist aber Repo-Code und
  zählt gegen das 250-LoC-Workflow-Limit — je nach Testumfang ist
  `workflow.py set-field loc_limit_override 500` wahrscheinlich nötig, mit PO-Freigabe vor
  Implementierungsbeginn.
- **Files:** 6 geändert, 2 neu (`scripts/eichung_cape_schwelle.py`, `src/app/model_registry.py`),
  mehrere Testdateien neu/erweitert.
- **Effort:** medium-high — die Eichung selbst ist unkompliziert (ein Skript, eine API), aber das
  Muster "quellenabhängige numerische Schwelle als Tabelle" existiert im Repo noch nirgends
  (s. Architektur-Entscheidung) und berührt eine sicherheitsrelevante Stelle (Gewitter-Aussage).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.4b/3.5b | bindender Rahmen | Rang-0-Befund dieser Arbeit; NWS/SPC-Leiter als externer Anker für die 300-J/kg-Untergrenze |
| ADR-0025 | bindende Vorgabe | Genau eine Rohdatenquelle der Gewitteraussage (`dp.thunder_level`); `thunder_level_from_signals()` bleibt der einzige Fusionsort |
| ADR-0047 | Vorbild | Gebiets-/Quellenraster über first-match-wins-Tabelle (`thunder_routing._REGIONS`) — dasselbe Muster liefert hier das Gebietsraster für die Eichung |
| `feat_1474_gewitter_befund_stufen.md` AC-6/AC-7 | Regressionsanker, wird hier PRÄZISIERT | AC-6 ("CAPE gedeckelt bei LOW, eskaliert nie") bleibt gültig, jetzt mit variabler statt fester Schwelle. AC-7 ("keine Aussage" ≠ "geprüft unauffällig") wird durch diese Scheibe auf CAPE bei unbekannter Modell-Herkunft ausgeweitet |
| `feat_1474c_blitzpotenzial_stufen.md` AC-7 | Regressionsanker | Bestandstests in `test_thunder_level_from_signals_fusion.py` — **gemessen 2026-08-08 in der RED-Phase: ALLE 8 Fälle brechen**, nicht nur die CAPE-bezogenen. Weil der neue Parameter keyword-only **ohne Default** ist, bricht jeder Aufruf ohne ihn mit `TypeError` — auch die reinen Blitzdichte-/Blitzpotenzial-Fälle mit `cape_jkg=None`. Die frühere Fassung dieser Zeile („die blitzpotenzialbezogenen Fälle bleiben unverändert") war eine Vermutung und ist widerlegt. **Anpassung ist mechanisch und gewollt:** jeder Aufruf nennt die Schwelle künftig ausdrücklich (`cape_threshold_jkg=None`, wo keine Herkunft im Spiel ist). Genau das ist der Zweck des fehlenden Defaults — kein Aufrufer kann die Herkunft stillschweigend übergehen. Die **Erwartungswerte** der 8 Fälle bleiben unverändert; AC-7 aus feat_1474c gilt inhaltlich fort |
| `tests/unit/test_configurable_thresholds.py::test_cape_risk_thresholds`, `tests/integration/test_risk_engine.py::test_cape_high`/`::test_cape_moderate` | **unverändert grün zu halten** | Familie 2 (RiskEngine) liest die Katalogschwelle direkt (`get_metric("cape").risk_thresholds`), nicht über `thunder_level_from_signals()` — diese Scheibe fasst RiskEngine nicht an, diese Tests dürfen sich nicht bewegen |
| Open-Meteo Historical Forecast API (`historical-forecast-api.open-meteo.com`) | externe Datenquelle | liefert die Modellklimatologie für B0 ohne eigenes Archiv; gemessen 2026-08-08, Antwort in Sekunden |
| `weather_snapshot.py::_deserialize_summary` | bestehender Schutzmechanismus | filtert Unbekanntes über `dataclasses.fields()` — macht das neue additive Feld `cape_model_id` schnappschuss-sicher, ohne Migration |

## Abschnitt 1 (B0) — Einmaliges Eichskript, statische Tabelle im Repo

**Die Eichregel** (wörtlich): Schwelle je Modell × Gebiet = **das 95. Perzentil der
CAPE-Klimatologie dieses Modells in diesem Gebiet über eine Konvektionssaison (April–September),
mindestens aber 300 J/kg.**

Begründung: Ein reines Perzentil würde in klimatologisch ruhigen Gebieten bei absurd niedrigen
Absolutwerten auslösen — 300 J/kg ist die Untergrenze, unterhalb derer Konvektion nach jeder
Parcel-Definition marginal ist (Untergrenze der NWS/SPC-Leiter, Gesamtkonzept 3.5b). Ein reiner
Absolutwert wäre genau der Fehler, den #1592 behebt. Die Kombination aus Perzentil und
Mindestwert ist das operationell übliche Verfahren (ECMWF Extreme Forecast Index: Seltenheit
relativ zur Modellklimatologie, nicht Absolutwert).

**Skript `scripts/eichung_cape_schwelle.py`** (einmalig ausgeführt, kein Laufzeit-Abruf):

1. Modelle: die fünf in `openmeteo.REGIONAL_MODELS` tatsächlich produktiv wählbaren IDs
   (`meteofrance_arome`, `icon_d2`, `metno_nordic`, `icon_eu`, `ecmwf_ifs04`) — GFS wird von
   Gregor Zwanzig nie ausgewählt (nicht in `REGIONAL_MODELS`) und bleibt daher außen vor, obwohl
   es in der Analyse-Messung zu Vergleichszwecken auftaucht.
2. Gebiete: die bestehenden Gewitter-Zuständigkeitsgebiete aus `thunder_routing._REGIONS` (FR,
   DE_ALPEN, EU_REST) — **kein zweites Raster**. Je Gebiet EIN dokumentierter Referenzpunkt (fest
   im Skript als Konstante, mit Begründung im Kommentar; für FR/DE_ALPEN dieselben Punkte wie in
   der Analyse-Messung — GR20/Refuge de Petra Piana bzw. München-Raum —, für EU_REST ein neu
   gewählter, repräsentativer Punkt).
3. Für jede (Modell, Gebiet)-Kombination: Abruf `hourly=cape&models=<id>` gegen die Historical
   Forecast API für die letzte vollständige Konvektionssaison (April–September), 95. Perzentil
   der stündlichen Reihe berechnen, `max(perzentil, 300.0)`.
4. Liefert die API für eine Kombination keine (oder eine leere) Reihe — das Modellgitter deckt
   den Referenzpunkt nicht ab —, entsteht **kein** Tabelleneintrag. Das ist kein Fehler: eine
   fehlende Kombination verhält sich am Lookup-Ort identisch zu unbekannter Herkunft (Abschnitt
   3), also Abstain statt eines geratenen Werts.
5. Ergebnis wird als statisches Python-Literal `CAPE_THRESHOLDS_JKG:
   dict[tuple[str, str], float]` in `src/app/model_registry.py` committed. **Die
   Schlüsselreihenfolge ist verbindlich `(model_id, region)`** — dieselbe Reihenfolge wie die
   Parameter von `cape_threshold_jkg(model_id, region)`. Ohne diese Festlegung schlägt der
   Nachschlag bei vertauschter Reihenfolge mit `KeyError` fehl, und die Tests zu AC-1/AC-7/AC-8
   blieben aus dem falschen Grund rot. Eine erneute
   Eichung (neue Saison, geändertes Modellgitter) ist ein manueller, bewusster Schritt — kein
   automatischer Cronjob, keine Laufzeit-Abhängigkeit von der Historical Forecast API.

## Abschnitt 2 (C0) — Fundament: normalisierte Modell-Herkunft bis ins Aggregat

**Neues Modul `src/app/model_registry.py`** (Vorbild `thunder_routing._REGIONS`, Tabelle statt
Sonderfall im Code):

- `normalize_model_id(raw: Optional[str]) -> Optional[str]` bündelt das uneinheitliche
  Vokabular auf den jeweiligen Open-Meteo-Technik-Schlüssel als kanonischen Wert:
  `"icon_d2"`/`"ICON-D2"` → `"icon_d2"`; `"meteofrance_arome"`/`"AROME-HIGHRES"`/`"AROME"` →
  `"meteofrance_arome"`; `"icon_eu"` → `"icon_eu"`; `"metno_nordic"` → `"metno_nordic"`;
  `"ecmwf_ifs04"` → `"ecmwf_ifs04"`. `"aggregate"`, `"snapshot"`, `"fixture"`, `"NOWCAST"` und
  jeder unbekannte Wert → `None`.
- `effective_cape_model_id(meta: ForecastMeta) -> Optional[str]` bündelt die Fallback-Vorrang-
  Regel EINMAL für beide Nutzstellen (C0 und C1, DRY): steht `"cape"` in
  `meta.fallback_metrics`, gilt `normalize_model_id(meta.fallback_model)`, sonst
  `normalize_model_id(meta.model)`.
- `cape_threshold_jkg(model_id: Optional[str], region: Optional[str]) -> Optional[float]`
  schlägt `CAPE_THRESHOLDS_JKG` nach; `None`, wenn `model_id` oder `region` `None` ist, oder
  keine Kalibrierung für die Kombination vorliegt (Abschnitt 1, Punkt 4) — beide Fälle heißen am
  Lookup-Ort identisch "nicht belegt".

**`SegmentWeatherSummary.cape_model_id: Optional[str] = None`** (`app/models.py`, additiv) —
der **normalisierte** Schlüssel, nicht der Rohwert aus `meta.model`. Alte Schnappschüsse laden
mit `None` (`_deserialize_summary` filtert Unbekanntes bereits still über
`dataclasses.fields()`); ein rückwirkendes Nachtragen für historische Daten gibt es nicht.

**Befüllung:**
- `weather_metrics.compute_extended_metrics()` (Trip-Pfad): setzt
  `cape_model_id=effective_cape_model_id(timeseries.meta)` auf das erzeugte Summary.
- `weather_metrics.summarize_points()` (Ortsvergleichs-Pfad): baut sich, wie bisher,
  `ForecastMeta(model="aggregate", ...)` — `effective_cape_model_id()` normalisiert das
  automatisch zu `None`. Kein Sonderfall-Code nötig, die Normalisierung erledigt das.

## Abschnitt 3 (C1) — Die Fusion nutzt die kalibrierte Schwelle statt der festen 1000

**`thunder_routing.py`** bekommt `thunder_region_for(lat: float, lon: float) -> Optional[str]`
— nutzt DASSELBE `_REGIONS`-Raster (first-match-wins) wie `thunder_provider_for()`, liefert aber
den Gebietsnamen statt des Provider-Namens. Kein zweites Raster (harte Vorgabe der Analyse).

**`metric_format.thunder_level_from_signals()`** bekommt einen keyword-only Parameter OHNE
Default: `cape_threshold_jkg: Optional[float]`. Er ersetzt den bisherigen internen Aufruf von
`_cape_low_min_jkg()` (die feste Katalog-1000 — dieser Helfer wird entfernt, sein einziger
Aufrufer war diese Funktion; Familie 2/RiskEngine liest die Katalogschwelle direkt und ist
unberührt). **Kein `= None`-Rückfall:** ein Aufrufer, der vergisst, die Herkunft aufzulösen und
den Parameter zu setzen, bricht mit `TypeError` — nicht still auf Bestandsverhalten.

Verhalten bei vorhandenem `cape_jkg`:
- `cape_threshold_jkg is None` (Herkunft unbekannt ODER keine Kalibrierung für die Kombination)
  → CAPE trägt **kein** Signal zur Fusion bei — `cape_jkg` wird NICHT in die Signalliste
  aufgenommen, unabhängig von seinem Wert. Das ist der Unterschied zwischen "keine Aussage" und
  "geprüft, unauffällig" (feat_1474 AC-7) und der Kern des zweiten Befunds aus der Analyse.
- `cape_threshold_jkg` vorhanden, `cape_jkg >= cape_threshold_jkg` → `ThunderLevel.LOW`
  ("leicht"), wie bisher gedeckelt — eskaliert NIE auf `MED`/`HIGH` (CAPE misst Energie, kein
  Ereignis, unverändert aus feat_1474 AC-6).
- `cape_threshold_jkg` vorhanden, `cape_jkg < cape_threshold_jkg` → `ThunderLevel.NONE`
  (geprüft, unauffällig).

**`thunder_enrichment._fuse_thunder_levels()`/`enrich_thunder()`:** `enrich_thunder()` hat
bereits `reihe.meta` UND `location` — löst daraus EINMAL je Reihe
`cape_threshold_jkg(effective_cape_model_id(reihe.meta), thunder_region_for(location.latitude,
location.longitude))` auf und reicht das fertige Ergebnis an `_fuse_thunder_levels()` durch (ein
Parameter mehr, kein neuer Mechanismus — wie in der Analyse vorgezeichnet).

## Known Limitations

- **Ortsvergleich und Schnappschuss-Reload haben strukturell keine Modell-Herkunft.**
  `summarize_points()` baut sich `model="aggregate"`, ein Schnappschuss-Reload liefert
  `model="snapshot"` — beide normalisieren zu `None`. CAPE trägt dort **dauerhaft** nicht zur
  Gewitterstufe bei, nicht nur bis zu einer Folgescheibe. Das ist ein bewusster Scope-Schnitt
  dieser Arbeit, kein Fehler: eine Herkunft, die nie erhoben wurde, kann nicht nachgetragen
  werden, ohne die Aufrufer strukturell zu ändern (eigenes Folgeticket, falls gewünscht).
- **Nicht jede (Modell, Gebiet)-Kombination hat eine kalibrierte Schwelle.** Kombinationen, deren
  Modellgitter den gewählten Referenzpunkt eines Gebiets nicht abdeckt (z. B. `icon_d2` weit
  außerhalb seines Rechtecks), fehlen bewusst in der Tabelle und verhalten sich wie unbekannte
  Herkunft (Abstain) — nicht wie ein Fehler.
- **Ein Referenzpunkt je Gebiet, nicht je Ort.** Die Analyse-Messung zeigt, dass CAPE innerhalb
  eines Modells je nach Ort stark streut (ICON-EU: Faktor 6 zwischen Korsika und München). Ein
  Perzentil je einzelnem Trip-/Vergleichsort wäre genauer, kostet aber Abrufe je Ort plus
  Zwischenspeicherung — als spätere Verfeinerung notiert, nicht Teil dieser Scheibe.
- **Familie 2 (RiskEngine) und Familie 3 (Δ-Alarme) bleiben bei der festen 1000/2000-J/kg-
  Katalogschwelle**, bis C2 bzw. C3 sie auf dieselbe kalibrierte Tabelle umstellen. Bis dahin
  können zwei verschiedene CAPE-Schwellen für dieselbe Vorhersage gleichzeitig gültig sein (die
  neue kalibrierte für die Gewitterstufe, die alte feste für die Risikoübersicht) — bewusst
  akzeptiert, um die Scheibe klein zu halten.
- **GFS ist nicht Teil der Kalibrierung**, weil Gregor Zwanzig es nie als Wettermodell auswählt
  (kein Eintrag in `openmeteo.REGIONAL_MODELS`). Taucht in der Analyse-Messung nur zu
  Vergleichszwecken auf.
- **Die Eichtabelle ist statisch, nicht selbstaktualisierend.** Eine neue Konvektionssaison oder
  ein geändertes Modellgitter macht eine erneute, bewusste Ausführung des Skripts nötig — es
  gibt keinen Cronjob und keine Drift-Erkennung, wenn ein Modell seine Klimatologie verschiebt.
- **Same-Model-Guard für Δ-Alarme (Befund B der Analyse)** — ein Modellwechsel zwischen zwei
  Läufen kann heute allein einen Alarm auslösen, ohne dass sich das Wetter geändert hat — ist
  NICHT Teil dieser Scheibe (eigenes Bug-Ticket, direkt im Anschluss an C3 geplant).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** **ADR-0048** — `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`,
  Status „Akzeptiert", angelegt 2026-08-08, im Index eingetragen.
- **Rationale:** Im gesamten Repo gibt es bisher **keine** modell-/quellenabhängige numerische
  Schwelle — weder RiskEngine noch `weather_metrics` lesen `meta.model` oder `grid_res_km` für
  Schwellenlogik. Diese Scheibe führt genau dieses Muster ein (Tabelle Modell × Gebiet statt
  eines Einzelwerts) und macht es damit zu einer Architektur-Entscheidungsfläche im Sinne von
  CLAUDE.md ("Provider", "Datenmodell"). Ein ADR hält fest: warum eine Tabelle statt eines
  Einzelwerts, warum das bestehende Gebietsraster aus `thunder_routing` wiederverwendet statt ein
  zweites erfunden wird, und warum unbekannte Herkunft zu Abstain statt zu einem Default-Wert
  führt. Das ADR wird vor der Implementierung dieser Scheibe angelegt, damit die
  Grundsatzentscheidung nicht nur im Code, sondern auch an der dafür vorgesehenen, auffindbaren
  Stelle steht.

## Acceptance Criteria

**Fundament (B0 + C0)**

- **AC-1 (Eichtabelle existiert, ist nachvollziehbar, respektiert die Untergrenze):** Given das
  neue Auswertungsskript wird gegen die Open-Meteo Historical Forecast API für eine
  Konvektionssaison (April–September) ausgeführt / When es für jedes verfügbare Modell ×
  Gebiet-Paar läuft / Then entsteht eine statische, versionierte Tabelle im Repo, deren Werte
  ausnahmslos mindestens 300 J/kg betragen — auch dort, wo das rohe 95. Perzentil niedriger
  läge, greift die Untergrenze.
  - Test: die committete Tabelle wird OHNE Netzabruf gegen ihre eigene Konstruktionsregel
    geprüft (jeder Wert ≥ 300,0). Zusätzlich muss **mindestens ein** Eintrag **exakt 300,0**
    betragen (dort greift die Untergrenze, weil das rohe 95. Perzentil darunter liegt) **und
    mindestens ein** Eintrag **strikt zwischen 300 und 1000** liegen (dort greift sie nicht).
    Wäre die Untergrenze fälschlich als fester Wert implementiert, wären ALLE Einträge 300 und
    der Test fällt durch.
  - Bewusst **nicht** an ein bestimmtes Modell × Gebiet-Paar gebunden: welcher Eintrag auf der
    Grenze landet, hängt vom Eichzeitraum ab und verschiebt sich bei einer Neueichung. Eine
    frühere Fassung dieses Tests nannte `icon_d2 × DE_ALPEN` als Beispiel für „strikt dazwischen";
    mit dem spezifizierten Zeitraum April–September landet gerade dieser Eintrag selbst auf 300
    (rohes P95 ≈ 280). Die Zusicherung gilt der **Regel**, nicht einem Zahlenpaar.

- **AC-2 (normalisierte Herkunft landet additiv im Aggregat, alte Daten bleiben unberührt):**
  Given eine reguläre Trip-Vorhersage für einen Ort im AROME-Gebiet (GR20/Korsika) / When das
  Tagesaggregat berechnet wird / Then trägt `SegmentWeatherSummary.cape_model_id` den
  normalisierten Schlüssel des tatsächlich liefernden Modells (z. B. `"meteofrance_arome"`),
  NICHT den unveränderten Rohwert. Given STATTDESSEN ein alter, bereits gespeicherter
  Wetter-Schnappschuss ohne dieses Feld wird geladen / Then lädt er unverändert und
  `cape_model_id` ist `None`.
  - Test: reguläre Aggregation eines AROME-Orts prüft den Feldwert direkt; Laden eines
    vorbestehenden JSON-Schnappschusses (ohne das neue Feld, unverändert aus dem Bestand) schlägt
    nicht fehl und liefert `cape_model_id is None`.

- **AC-3 (Ortsvergleich hat strukturell keine Herkunft — das Aggregat sagt das ehrlich, nicht
  stillschweigend):** Given eine Tagesaggregation über eine reine Punktliste (Ortsvergleichs-Pfad,
  `summarize_points()`) mit einem hohen CAPE-Wert / When das Aggregat berechnet wird / Then ist
  `cape_model_id` `None` — unabhängig davon, wie hoch der CAPE-Wert ist.
  - Test: `summarize_points()` mit einer Punktliste, deren CAPE-Werte deutlich über jeder
    denkbaren Schwelle liegen, liefert trotzdem `cape_model_id is None`.

- **AC-4 (das uneinheitliche Modell-Vokabular wird auf einen gemeinsamen Schlüssel gebündelt):**
  Given die unterschiedlichen Roh-Bezeichnungen für dieselbe Modellwelt (`"icon_d2"` von
  Open-Meteo und `"ICON-D2"` vom DWD-Direktprovider; `"meteofrance_arome"`, `"AROME-HIGHRES"` und
  `"AROME"` für dieselbe AROME-Familie) / When `normalize_model_id()` aufgerufen wird / Then
  liefert sie für jede Schreibweise derselben Modellwelt DENSELBEN kanonischen Schlüssel, und für
  `"aggregate"`/`"snapshot"`/`"fixture"`/unbekannte Werte `None`.
  - Test: mehrere Roh-Werte je Modellfamilie geprüft, alle liefern denselben Schlüssel; die
    künstlichen Werte liefern `None`.

**Fusion (C1)**

- **AC-5 (Kernfall — GR20/AROME trägt jetzt zur Gewitterstufe bei, wo es vorher strukturell
  NIE konnte):** Given ein Datenpunkt auf dem GR20 (AROME-Gebiet) mit einem CAPE-Wert, wie er in
  der Analyse real für dieses Gebiet gemessen wurde (840 J/kg), Wettercode und Blitzdichte ohne
  Signal / When die Vorhersage über den regulären Weg abgerufen und die Gewitterstufe fusioniert
  wird / Then liefert `dp.thunder_level` "leicht" (`ThunderLevel.LOW`) — mit der alten, festen
  1000er-Schwelle wäre dieser reale Wert NIE über "kein Gewitter" hinausgekommen, weil AROME
  strukturell fast nie 1000 J/kg erreicht.
  - Test: Ende-zu-Ende durch die echte Einstiegsfunktion (`enrich_thunder()`/`fetch_forecast()`,
    ADR-0025) mit einer AROME-Fixture, CAPE=840 → Ergebnis muss `LOW` sein. Gegenprobe: Bleibt
    die feste 1000er-Katalogschwelle statt der kalibrierten Tabelle im Einsatz, liefert derselbe
    Aufruf `NONE` — der Test muss diesen Unterschied fangen.

- **AC-6 (Gegenfall — unbekannte Herkunft liefert "keine Aussage", nicht "kein Gewitter"):**
  Given ein Ort ohne Modell-Herkunft — entweder aus dem Ortsvergleich (`model="aggregate"`) oder
  nach einem Schnappschuss-Reload (`model="snapshot"`) — mit einem hohen CAPE-Wert, alle anderen
  Signale ebenfalls ohne Wert / When die Gewitterstufe fusioniert wird / Then liefert die Fusion
  `None` ("keine Aussage"), NICHT `ThunderLevel.NONE` ("geprüft, unauffällig").
  - Test: Fusion mit unbekannter Herkunft (Ortsvergleichs- bzw. Schnappschuss-Pfad) und hohem
    CAPE, alle anderen Signale `None` → Ergebnis `None`. Gegenprobe: Fällt die Implementierung bei
    unbekannter Herkunft auf die alte feste Schwelle zurück, liefert derselbe Aufruf fälschlich
    `ThunderLevel.NONE` (behauptet eine geprüfte Entwarnung, die es nicht gab) statt `None` — der
    Test muss das fangen.

- **AC-7 (Deutschland bleibt praktisch funktionsfähig, jetzt auf belegter statt erfundener
  Grundlage):** Given ein Datenpunkt im ICON-D2/ICON-EU-Gebiet mit einem CAPE-Wert oberhalb der
  für dieses Modell und Gebiet kalibrierten Schwelle (laut Eichtabelle) / When die Gewitterstufe
  fusioniert wird / Then liefert sie weiterhin "leicht" (`LOW`) — die deutsche Erkennung
  funktioniert praktisch weiter, ruht aber jetzt auf einer gemessenen statt einer erfundenen
  Zahl.
  - Test: Fusion mit ICON-D2- bzw. ICON-EU-Herkunft und einem CAPE-Wert oberhalb der für diese
    Kombination kalibrierten Schwelle liefert `LOW`.

- **AC-8 (Deckelung bleibt bestehen, unabhängig von der Schwellenherkunft):** Given ein sehr
  hoher CAPE-Wert weit über jeder denkbaren kalibrierten Schwelle, egal welches Modell / When die
  Fusion läuft / Then bleibt das Ergebnis bei "leicht" (`LOW`), eskaliert NIE auf "mittel"/"hoch"
  — dieselbe Deckelungs-Zusicherung wie in feat_1474 AC-6, jetzt mit variabler statt fester
  Schwelle.
  - Test: Fusion mit CAPE=5000 J/kg und bekannter, kalibrierter Herkunft liefert `LOW`, nicht
    `MED`/`HIGH`.

## Changelog

- 2026-08-08: Initial spec created (Issue #1592, Scheiben B0+C0+C1, PO-Zuschnitt "Eichlauf
  zuerst" vom selben Tag).
