---
entity_id: feat_1983_gewitter_modelllauf_mehrheit
type: feature
created: 2026-09-19
updated: 2026-09-19
status: implemented
version: "1.0"
tags: [gewitter, ensemble, epic-1419, epic-2181]
---

<!-- Issue #1983 (Gewitter S6 aus Epic #1419) — PO-Entscheid 2026-09-19 (Henning), s.
     docs/context/feat-1983-modelllauf-mehrheit.md -->

# Feature #1983 — Gewitter-Stufe nach Modellauf-Mehrheit

## Approval

- [x] Approved

## Purpose

Die Gewitter-Stufen-Regel (Issue #1419 Abschnitt 4) benennt seit langem ein nie verdrahtetes
Kriterium: "Mehrheit der Modellläufe hebt an, Minderheit dämpft". Dieses Feature verdrahtet es
als fünftes Fusionssignal `modelllauf` (nur anhebend) und als Dämpfer auf die vier
Einzelmodell-Signale (nur bei ausgeprägter Uneinigkeit der Ensemble-Läufe). Ziel ist
ausdrücklich, die dokumentierte KHW-Überprognose (#2181/#2206: 9 von 13 Tagen "hoch" gegen
1 realen Gewittertag) zu **bekämpfen, nicht zu verstärken** — eine reine Anhebung (wie im
Ticket ursprünglich benannt) hätte das Gegenteil bewirkt, deshalb der PO-Entscheid "beides,
mit Schwellen" (2026-09-19).

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider._fetch_ensemble_spread`

Python-Core-Feature (`src/providers/`, `src/services/`, `src/app/`). Kein Go-, kein
Frontend-Anteil — die Stufe fließt über die bestehende Fusion (ADR-0025) unverändert in alle
vier Kanal-Renderer.

## Estimated Scope

- **LoC:** ~180–280 (Schätzung; Ticket-Vorgabe LoC-Limit 250/Workflow — bei Überschreitung
  `workflow.py set-field loc_limit_override 500` in /40–/50, **nicht** auf eine Scheibe
  verengen, s. `docs/reference/gates_und_ratschen.md`)
- **Files:** 4 MODIFY + 1 CREATE (Test) + 1 MODIFY (Test-Ergänzung Wächter)
- **Effort:** high — Risk Level HIGH (alle vier Kanäle, direkte Gegenmaßnahme zur
  dokumentierten Überprognose, Sicherheits-Invariante "Beobachtung nie gedämpft")

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.thunder_scale.union_of_max_carriers` | intern | S2-Aggregationsregel (#1680) — wird für die Anhebung wiederverwendet, keine zweite Fusionsregel |
| `app.thunder_scale.thunder_ordinal` / `_THUNDER_ORDER` | intern | kanonische Sortierordnung, Grundlage des neuen Ein-Stufen-Dämpfers |
| `output.metric_format._gedaempft_durch_cin` | Muster | Vorlage für "eine Stufe dämpfen, nie unter NONE" — Struktur wiederverwendet, nicht der Code selbst (CIN-Bänder sind CAPE-spezifisch) |
| `providers.thunder_enrichment._apply_radar_override` | intern | Sicherheits-Invariante "Beobachtung schlägt Modell" — Dämpfung darf einen bereits radar-bestätigten Datenpunkt nicht mehr anfassen |
| `app.models.ForecastDataPoint.thunder_probability_pct` | intern | vorbereitetes, bisher leeres Feld (#1474 AC-10) — wird in dieser Scheibe erstmals befüllt |
| `services.trip_report_scheduler._enrich_ensemble_for_trip` / `_apply_ensemble_spreads` | intern | einziger Einbaupunkt für Hauptlauf, Ausblick und Gewitter-Fallback — ein Codepfad für alle drei |

## Architektur-Befund: Warum die Dämpfung NICHT wie `_gedaempft_durch_cin` in `_signal_levels()` sitzen kann

Der Ticket-Auftrag verlangt das CIN-Muster ("Modifikator innerhalb von `_signal_levels`").
Der tatsächliche Aufrufpfad widerspricht dem:

- Die Fusion (`_fuse_thunder_levels` → `thunder_level_from_signals` → `_signal_levels`,
  `metric_format.py:433-596`) läuft **je Segment, beim Wetterabruf**
  (`SegmentWeatherService.fetch_segment_weather` → `OpenMeteoProvider.fetch_forecast` →
  `thunder_enrichment.enrich_thunder`), aufgerufen aus
  `trip_report_scheduler.py:_fetch_weather:2211` — dort **immer mit
  `enrich_ensemble=False`** ("Bug #288: Skip ensemble per-segment").
- Der Ensemble-Abruf (Modellauf-Anteil) passiert **danach**, einmal je Trip/Aufruf, in
  `_enrich_ensemble_for_trip` (`trip_report_scheduler.py:2294-2362`, aufgerufen von `:1432`,
  `:2527`, `:2996`) und schreibt nur noch auf bereits fertig fusionierte `DataPoint`-Objekte.
- An dieser Stelle liegen die vier ROHEN Einzelsignale (Wettercode, Blitzdichte, CAPE,
  Blitzpotenzial) nicht mehr vor — nur noch `dp.thunder_level` (das bereits gebildete
  Maximum) und `dp.thunder_level_signals` (die Namen der Signale, die dieses Maximum
  getragen haben). Ein Parameter `ensemble_anteil_pct` in `_signal_levels()` wäre an dieser
  Stelle unerreichbar, ohne den Ensemble-Abruf vor den Wetterabruf zu ziehen — das würde die
  "1 Abruf/Trip"-Struktur (#288) komplett umbauen und ist außerhalb des Scopes dieses Tickets.

**Lösung (mathematisch gleichwertig, ohne Umbau der Abrufreihenfolge):** "Eine Stufe dämpfen"
ist eine für ALLE Ordinalstufen gleiche, monotone (nicht-fallende) Abbildung
`f(NONE)=NONE, f(LOW)=NONE, f(MED)=LOW, f(HIGH)=MED`. Für eine monotone Abbildung, die auf
jedes Element einer Menge gleich angewendet wird, gilt `f(max(S)) = max(f(s) für s in S)` —
Dämpfen des bereits fusionierten Maximums um eine Stufe liefert exakt dasselbe Ergebnis wie
"jedes Einzelsignal um eine Stufe dämpfen und neu fusionieren". Die Trägerliste
(`thunder_level_signals`) bleibt bei diesem Schritt unverändert, AUSSER das gedämpfte
Ergebnis fällt auf `NONE` — dann wird sie geleert (`thunder_signal_carriers()`-Regel: "kein
Gewitter hat keine Herkunft"). Ein Datenpunkt mit `dp.thunder_level is None` ("keine
Aussage") bleibt beim Dämpfen `None` — nichts zu dämpfen.

Für die Anhebung gilt dasselbe Prinzip einfacher: `modelllauf` ist ein fünftes Signal auf
Stufe `HIGH` (Skalen-Obergrenze), das neue Maximum ist deshalb immer `HIGH`. Die neue
Trägerliste wird über die bestehende, für genau diesen Zweck gebaute Aggregationsregel
`app.thunder_scale.union_of_max_carriers([(dp.thunder_level, dp.thunder_level_signals),
(ThunderLevel.HIGH, ["modelllauf"])])` gebildet — keine zweite Fusionsregel neben der
kanonischen (ADR-0025), volle Wiederverwendung von #1680 S2.

**Warum in `app/thunder_scale.py`, nicht in `output/metric_format.py`:** Der Aufrufort
(`trip_report_scheduler.py`) ist per Wächter `test_scheduler_has_no_output_imports`
(#1365) von einem Import der Darstellungsschicht `output.metric_format` ausgeschlossen —
genau das Muster, das `thunder_scale.py` bereits für `thunder_ordinal`/
`union_of_max_carriers` löst. Die neuen Helfer (Ein-Stufen-Dämpfer, Anhebungs-Wrapper)
gehören aus demselben Grund dorthin.

## Sicherheits-Invariante: Radar-Override wird nicht angetastet

`_apply_radar_override` (`thunder_enrichment.py:219-276`) läuft **vor** dem Ensemble-Schritt
im tatsächlichen Aufrufpfad (es ist Teil von `enrich_thunder()`, das je Segment beim
Wetterabruf läuft, `:2211` — strikt vor `_enrich_ensemble_for_trip` bei `:1432`/`:2527`/
`:2996`). Die im Ticket verlangte Reihenfolge ("Dämpfung wirkt vor dem Radar-Override, der
danach weiterhin anhebt") entspricht damit **nicht** der Code-Realität — real läuft der
Override zeitlich zuerst. Die Sicherheits-Garantie wird deshalb nicht über Reihenfolge,
sondern über einen expliziten Schutz hergestellt: Die Dämpfung überspringt jeden
Datenpunkt, dessen `dp.thunder_level_signals` bereits `"radar"` enthält (Markierung durch
`_apply_radar_override:273-276`). Die Anhebung ist von dieser Ausnahme NICHT betroffen — ein
radar-bestätigter Punkt darf durch `modelllauf` zusätzlich auf `HIGH` gehoben werden, das
verletzt "nie gedämpft" nicht.

Zusätzlich liest `_apply_radar_override` (`:265-267`) den ROHEN
`dp.lightning_density_per_km2_3h`, nicht die (ggf. gedämpfte) `dp.thunder_level`-Stufe — der
Override bleibt dadurch strukturell unabhängig von jeder Dämpfung, unabhängig von der
Aufrufreihenfolge. Wichtig für die Implementierung: **nicht** "reparieren" zu einer Prüfung
gegen `dp.thunder_level`, das würde die Unabhängigkeit zerstören.

**Amtliche Warnungen** sind kein Fusionssignal (`_signal_levels()` kennt genau vier
Schlüssel: `wettercode`, `blitzdichte`, `cape`, `blitzpotenzial`, `metric_format.py:433-486`)
— sie laufen über einen eigenen Pfad (`official_alert_source_label`,
`thunder_scale.py:131` nur als Namens-Referenz, keine Fusionsbeteiligung gefunden). "Nie
gedämpft" ist für amtliche Warnungen damit strukturell erfüllt, nicht extra zu bauen.

## Implementierung — Abruf (`src/providers/openmeteo.py`)

`_fetch_ensemble_spread` (`:722-807`) bekommt zusätzlich `weather_code` im `hourly`-Parameter
(bisher nur `temperature_2m,precipitation`, `:740`). Je Stunde:

1. Sammle alle `weather_code_member*_<modell>`- sowie die unsuffixierten
   Kontrolllauf-Schlüssel für `modell ∈ {icon_seamless, gfs_seamless}` (Muster wie
   `temp_keys`/`precip_keys`, `:770-771`) — **ausdrücklich NICHT** `weather_code_ecmwf_ifs04`
   (liefert keine Member, Nebenbefund #1199, hier bewusst nicht mitgefixt für Spread/
   Confidence, aber für den NEUEN Anteil explizit ausgeschlossen).

   **Korrektur (verifiziert in /40, 2026-09-19, gegen die aufgezeichnete Fixture
   `tests/fixtures/openmeteo_ensemble/wolayersee_2026-09-19_weather_code.json`):** Die
   Kontrolllauf-Schlüssel sind **nicht** unsuffixiert auf `icon_seamless`/`gfs_seamless`,
   sondern tragen den vollen API-Modellnamen: `weather_code_icon_seamless_eps` (ICON-EPS) und
   `weather_code_ncep_gefs_seamless` (GEFS) — bei GEFS zusätzlich mit anderem Präfix als beim
   Modellnamen der Anfrage (`gfs_seamless` in `models=`, aber `ncep_gefs_seamless` im
   Antwortschlüssel). Die tatsächliche Filterregel der Implementierung ist deshalb generischer
   als „unsuffixierter Schlüssel je Modell": alle Schlüssel, die mit `weather_code` beginnen
   und nicht `ecmwf` enthalten (`k.startswith("weather_code") and "ecmwf" not in k`,
   `openmeteo.py`), erfasst damit sowohl Member- als auch Kontrolllauf-Spalten ohne Kenntnis
   der genauen Modell-Suffixe. Fund bestätigt Known Limitation 5 als in dieser Implementierung
   geklärt.
2. Zähle je Stunde die gültigen (nicht-`None`) Codes unter diesen Schlüsseln = `n_valid`.
   `n_valid < ENSEMBLE_THUNDER_MIN_MEMBERS` (Konstante, Wert 20, eigene Stelle in
   `openmeteo.py` neben `THUNDER_CODES`) ⇒ diese Stunde liefert `thunder_member_share_pct =
   None` ("keine Aussage", AC-8).
3. Sonst: Anteil = 100 × (Anzahl Codes ∈ `THUNDER_CODES` {95,96,99}) / `n_valid`, gerundet
   auf ganze Prozent, `int`.
4. Exakter Schlüsselname des Kontrolllaufs ist gegen die reale API-Antwort zu verifizieren
   (curl-Beleg 19.09. bestätigt nur das Member-Muster `weather_code_memberNN_<modell>`, nicht
   den Kontrolllauf-Namen) — in /40 gegen eine aufgezeichnete Fixture prüfen, nicht raten.

**Rückgabetyp:** Der bisherige 2-Tupel-Rückgabewert `Dict[datetime, Tuple[Optional[float],
Optional[float]]]` wird zu einer benannten Struktur (`NamedTuple EnsembleHourStats
(spread_t2m_k, spread_precip_mm, thunder_member_share_pct)`), keine 3er-Tupel-Anonymität
(Adversary-Risiko: Vertauschung von Position 2/3). Betrifft ALLE Konsumenten (s. Affected
Files) — ein 2-Tupel-Entpacken (`s_t, s_p = spread`) bricht sonst mit `ValueError`.

## Implementierung — Anker & Anwendung (`src/services/trip_report_scheduler.py`)

**Anker je Etappe (statt Tour-Ende, `:2294-2330`):** Alle drei Aufrufer von
`_enrich_ensemble_for_trip` (`:1432` Hauptlauf, `:2527` Ausblick, `:2996` Gewitter-Fallback)
übergeben bereits ein etappen-spezifisches `weather_data` — der Anker selbst ist aber HEUTE
bei allen drei identisch: `next((s.last_waypoint for s in reversed(trip.stages) if
s.waypoints), None)` sucht immer den letzten Wegpunkt der **ganzen Tour**, unabhängig davon,
welche Etappe gerade übergeben wurde (Befund, widerspricht der Ticket-Annahme "Ausblick-Abrufe
existieren bereits je Etappe" — nur der AUFRUF ist je Etappe, der ANKER nicht). Neue Regel:
Anker = letzter Wegpunkt (`end_point`) des letzten Segments in `weather_data` (dasselbe
"letzter Punkt trägt"-Muster wie heute, nur auf die tatsächlich übergebene Etappe verengt,
statt eine neue Heuristik wie "höchster Punkt" einzuführen — minimaler, nachvollziehbarer
Diff). `GPXPoint.elevation_m` wird wie heute durchgereicht.

**Folge für `confidence_pct` (#288):** Der Anker ändert sich für ALLE drei Aufrufer — nicht
nur den Hauptlauf. `confidence_pct`/`confidence_pct_min` kann sich dadurch für
Hauptlauf-, Ausblick- UND Fallback-Zeilen leicht verschieben (andere Koordinate = anderer
Spread). Das ist eine beabsichtigte Nebenwirkung der Korrektur (der heutige globale Anker war
für Etappen-Gewitteraussagen ohnehin ungeeignet), kein Regressionsrisiko — in /60 gegen die
bestehenden `confidence_pct`-Tests prüfen, ob eine Toleranz nötig wird.

**Abrufzahl unverändert:** Die Korrektur ändert die KOORDINATE des einen Abrufs je Aufruf von
`_enrich_ensemble_for_trip`, nicht die ANZAHL der Aufrufe — weiterhin genau 1 Ensemble-Abruf
je Aufruf, unverändert 1 (Hauptlauf) + bis 3 (Ausblick) + N (Fallback je künftiger Etappe) je
Briefing-Fenster (Messung AC-1 bleibt gültig, s.u.).

**Anwendung (`_apply_ensemble_spreads`, `:2362-2427`):** Je `DataPoint` mit einer Stunde, für
die `thunder_member_share_pct` nicht `None` ist:

- `dp.thunder_probability_pct = share_pct` (immer, unabhängig von Anhebung/Dämpfung/neutral —
  das Feld transportiert den rohen Anteil, AC-Feld-Semantik aus #1474 AC-10 bleibt: `None` =
  "keine Aussage").
- `share_pct >= MODELLLAUF_ANHEBUNG_MIN_PCT (60)`: neuer Stand über
  `union_of_max_carriers()` wie oben beschrieben (Stufe wird `HIGH`).
- `share_pct < MODELLLAUF_DAEMPFUNG_MAX_PCT (10)` UND `"radar" not in (dp.thunder_level_signals
  or [])`: Stufe um eine Stufe dämpfen (Trägerliste unverändert, außer Ergebnis `NONE`).
- sonst (`10 <= share_pct < 60`, oder `share_pct >= 60` UND `<10` schließen sich nach
  Konstruktion aus): keine Veränderung.

Die beiden neuen Helfer (Dämpfer, Anhebungs-Wrapper) leben in `app/thunder_scale.py` (s.o.),
`_apply_ensemble_spreads` ruft sie auf.

## Abgrenzung: `fetch_forecast(enrich_ensemble=True)`-Pfad bleibt außen vor

`OpenMeteoProvider.fetch_forecast` (`:949-968`, `:1148-1178`) hat `enrich_ensemble=True` als
DEFAULT und enthält eine zweite, unabhängige Kopie derselben Spread-Propagierung — aufgerufen
u.a. von `services/trip_forecast.py:156` und `services/forecast.py:85` (nicht vom
Trip-Briefing-Scheduler; der ruft `_fetch_ensemble_spread` direkt und setzt in
`_fetch_weather` stets `enrich_ensemble=False`). Die Typänderung von `_fetch_ensemble_spread`
bricht dort mechanisch das 2-Tupel-Entpacken (`:1171 s_t, s_p = spread`) — MUSS für die neue
Struktur angepasst werden, DAMIT der Code lädt. Ob dieser Pfad zusätzlich
`thunder_probability_pct`/Dämpfung bekommen soll, ist laut PO-Abgrenzung (Punkt 10, "kein
Ortsvergleich") NICHT Teil dieses Tickets — `trip_forecast.py`/`forecast.py` werden nicht auf
Verwendung geprüft, ob sie zum Trip-Briefing oder zu einer anderen Fläche gehören. Diese
Spec beschränkt die S6-Semantik (Signal `modelllauf`, Dämpfung) auf den
`trip_report_scheduler`-Pfad; der `fetch_forecast`-interne Pfad bekommt nur die
Typ-Anpassung, keine neue Semantik (Known Limitation, s.u.).

## Messung / Kosten (AC-1)

**Belegt (19.09.2026):**
- `/v1/ensemble` liefert `weather_code_memberNN_<modell>` je Member (curl-Beleg, Punkt
  Wolayersee). Eine ungültige Variable löst einen API-Fehler aus, kein stilles `null`.
- Der heutige Abruf (`openmeteo.py:738-743`) liefert 145 Spalten: ICON-EPS 39 Member +
  Kontrolle (40), GEFS 30 Member + Kontrolle (31). **`ecmwf_ifs04` liefert bei Open-Meteo
  keine Member mehr** — kostet Gewicht im Abruf, trägt aber keinen Lauf zur neuen
  Mehrheits-Berechnung bei (deshalb Ausschluss oben, Punkt 1).
- Ensemble-Abrufe je Briefing-Fenster: 1 (Hauptlauf, `:1432`) + bis 3 (Ausblick, `:2527`) +
  Gewitter-Fallback je künftiger Etappe (`:2996`). 2 Fenster/Tag/Trip (morgens/abends).
- Ensemble-Abrufe laufen **am internen Budget-Zähler vorbei** (`record_call()` nur in
  `segment_weather.py:196`, `forecast_budget.py:40`) — Risiko, nicht in diesem Ticket zu
  fixen.
- Prod-Status (`/api/scheduler/status`, 19.09.): 3 Nutzer gesamt, `forecast_budget.calls_today
  = 0`, letzter Gewitterabruf 05.09. (KHW-Ende) — aktuell keine aktive Tour. Realistische
  Spitzenlast laut Bestand: 1–3 gleichzeitig aktive Trips.

**Inferenz (NICHT gemessen, kein Gewichts-Header in der API-Antwort):** Open-Meteo gewichtet
Ensemble-Abrufe nach Member × Variablen; einziger Anhaltspunkt ist das Doku-Beispiel (1
Variable × ICON-EPS 40 Member, 7 Tage ≈ 4,0 gewichtete Calls). Daraus abgeleitet: der heutige
Abruf (2 Variablen) ≈ 14 gewichtete Calls, mit `weather_code` als dritter Variable ≈ 21.

**Ergebnis:** Je Trip und Tag heute bis ≈ 140 gewichtete Ensemble-Calls (5 Abrufe × 14 × 2
Fenster), mit `weather_code` im selben Abruf ≈ 210. Bei 1–3 aktiven Trips ≈ 200–650 von
10.000/Tag (Open-Meteo Free-Tier; interner Deckel 9000 ist ein anderer Zähler, s.o.) ⇒
**Kosten tragbar** — die Anker-Korrektur (Punkt oben) ändert die Koordinate, nicht die Anzahl
der Abrufe, die Messung bleibt für die gewählte Architektur gültig. Diese Sektion erfüllt
AC-1 ("Messung liegt schriftlich vor, bevor Code entsteht").

## Schwellen-Herkunft

Für "Anteil Ensemble-Member mit Gewittercode" existiert **keine publizierte Kalibrierung** —
anders als bei `_gedaempft_durch_cin` (ECMWF TM 852) gibt es hier keine externe Quelle, die
konsultiert werden könnte. Die drei Schwellen (60 %, 10 %, 20 Member) sind deshalb
**vorläufig, konservativ gewählt**, mit derselben Begründungspflicht wie bei jeder anderen
unkalibrierten Schwelle im Projekt:

- **Globale Ensembles unterdispersiv für Konvektion:** ICON-EPS (~26 km) und GEFS (~25 km)
  parametrisieren Gewitter, statt sie aufzulösen — hohe Member-Anteile mit Gewittercode sind
  dadurch selten und, wenn sie auftreten, eher aussagekräftig. Die Anhebung greift deshalb
  erst bei **deutlicher Mehrheit (≥ 60 %)**, nicht bei einfacher Mehrheit (>50 %) — PO-Ziel
  ist ausdrücklich, die KHW-Überprognose (#2181/#2206) nicht zu verstärken.
- **Die Dämpfung greift erst bei < 10 %** (nicht z.B. < 30 %), damit echte Gewittertage, die
  in unterdispersiven Ensembles typischerweise NIEDRIGE Member-Anteile zeigen, nicht
  systematisch weggedämpft werden — eine zu hohe Dämpfungsschwelle würde das
  Über-/Unterprognose-Problem nur in die andere Richtung verschieben.
- **20 Member als Mindestzahl:** deutlich über der bestehenden Spread-Mindestzahl (5,
  `openmeteo.py:800-801` — bewusst ZWEI verschiedene Mindestwerte für zwei verschiedene
  Aussagen, nicht harmonisieren: Spread/Confidence ist eine Streuungsmessung, die
  Mehrheitsfrage braucht eine belastbare Stichprobe für einen Prozentsatz). 20 von möglichen
  ≥69 (39+30, ohne Kontrollläufe) ist konservativ oberhalb dessen, was zu Beginn des
  Vorhersagehorizonts an Modellabdeckung typischerweise ausfällt.
- **10–59 % bleibt neutral**, um ein drittes, unbegründetes Band zu vermeiden — jede Zahl
  dazwischen wäre ebenso unbelegt wie 60/10 selbst.

**Eichung/Nachweisbarkeit:** `src/services/forecast_capture.py:82` (Mitschnitt aus #2030)
zeichnet auf Aggregat-Ebene nur eine benannte Feldliste auf (u.a. `thunder_level_max`), KEINE
Member-Rohdaten und AKTUELL auch KEIN `thunder_probability_pct`. Eine Nachrechnung der 9
überprognostizierten KHW-Tage anhand dieser Schwellen ist damit **nicht möglich** — die
Wirkung auf die dokumentierte Überprognose bleibt unbelegt, bis eine künftige Saison mit
laufendem Mitschnitt Daten liefert. Eine Eichung ist frühestens zur Saison 2027 möglich, UND
NUR, wenn `thunder_probability_pct` zusätzlich in `forecast_capture.py` aufgenommen wird
(welche Stundenstatistik dafür ins Aggregat ginge — Maximum oder Mittelwert der Etappe — ist
offen, Folgepunkt, nicht Teil dieses Tickets).

Die drei Schwellen werden als benannte Konstanten an EINER Stelle geführt:
`ENSEMBLE_THUNDER_MIN_MEMBERS` (`openmeteo.py`, Abrufschicht) sowie
`MODELLLAUF_ANHEBUNG_MIN_PCT`/`MODELLLAUF_DAEMPFUNG_MAX_PCT` (`app/thunder_scale.py`,
Domänenschicht, neben `union_of_max_carriers`).

## Betroffene Dateien

| File | Change | Beschreibung |
|---|---|---|
| `src/providers/openmeteo.py:722-807` | MODIFY | `weather_code` mitabrufen, Anteil je Stunde berechnen (≥20-Member-Regel, `ecmwf_ifs04` ausgeschlossen), Rückgabetyp auf benannte Struktur (`EnsembleHourStats`) umstellen; neue Konstante `ENSEMBLE_THUNDER_MIN_MEMBERS` |
| `src/providers/openmeteo.py:1148-1178` | MODIFY | Entpacken des geänderten Rückgabetyps in `fetch_forecast(enrich_ensemble=True)` — nur Typanpassung, KEINE neue Semantik (s. Abgrenzung oben) |
| `src/app/thunder_scale.py` | MODIFY | neue Konstanten `MODELLLAUF_ANHEBUNG_MIN_PCT`/`MODELLLAUF_DAEMPFUNG_MAX_PCT`, Ein-Stufen-Dämpfer, Anhebungs-Wrapper (nutzt `union_of_max_carriers`); Label `"modelllauf": "Modellläufe"` in `THUNDER_SIGNAL_LABEL_DE` |
| `src/services/trip_report_scheduler.py:2294-2362` | MODIFY | Anker aus `weather_data` (letztes Segment) statt `trip.stages`-Tour-Ende |
| `src/services/trip_report_scheduler.py:2362-2427` | MODIFY | `_apply_ensemble_spreads`: `dp.thunder_probability_pct` setzen, Anhebung/Dämpfung anwenden, Radar-Schutz |
| `tests/tdd/test_thunder_probability_field_prepared_empty.py` | PRÜFEN, ggf. ERGÄNZEN | nutzt `FixtureProvider`, nicht den Ensemble-Pfad — bleibt nach heutigem Verständnis grün (Feld bleibt bei diesem Provider leer) und gilt WEITER für den Fixture-Pfad; in /40 verifizieren, NICHT annehmen, dass er bricht |
| `tests/tdd/test_thunder_modelllauf_mehrheit.py` | CREATE | Kerntests zu allen ACs, aufgezeichnete Ensemble-Fixture (inkl. `weather_code`-Spalten) |

## Testplan

- **Kernschicht, deterministisch**, aufgezeichnete ECHTE Ensemble-Antwort als Fixture (kein
  Mock, der nur die eigene Annahme spiegelt) — eine neue Fixture mit `weather_code`-Spalten
  ist nötig, da die bestehende `fixtures/openmeteo/`-Fixture (Wächtertest) über den
  `FixtureProvider`-Pfad läuft, nicht über `_fetch_ensemble_spread`.
- Testdatei nach Verhalten benannt: `tests/tdd/test_thunder_modelllauf_mehrheit.py` (nicht
  nach Issue-Nummer).
- Zwei-Nutzer-Test entfällt begründet: kein Endpoint, keine Mandanten-Grenze betroffen — reine
  Domänen-/Provider-Logik ohne `user_id`-Bezug.
- Abgedeckte Verhaltensfälle (Muster: `_gedaempft_durch_cin`-Testsuite):
  - Anteil exakt 60 % hebt an, 59 % nicht.
  - Anteil exakt 10 % dämpft NICHT (Grenze gehört zum neutralen Band), 9,999→9 dämpft.
  - Dämpfung MED→LOW, LOW→NONE (Trägerliste wird bei NONE geleert), HIGH→MED.
  - Ausfall (`{}` vom Abruf) ⇒ `thunder_probability_pct=None`, kein Signal, keine Dämpfung,
    Stufe identisch zum Stand ohne S6.
  - Teilantwort: eine Stunde mit 15 gültigen Codes (< 20) ⇒ für GENAU diese Stunde `None`,
    Nachbarstunden mit ≥20 unberührt.
  - Radar-Schutz: ein Datenpunkt mit `"radar"` in `thunder_level_signals` UND Anteil < 10 %
    wird NICHT gedämpft.
  - Monotonie-Eigenschaft: für denselben Ausgangs-`dp.thunder_level` sinkt das Ergebnis nie,
    wenn der Anteil steigt (< 10 % ≤ 10–59 % ≤ ≥ 60 % in Stufen-Ordinalen).
  - Alle vier Kanal-Renderer (Mail `output/renderers/email/thunder_branch.py`, Telegram
    `output/renderers/text_report`, SMS `output/renderers/sms`, Premium-SMS über
    `channel_layout.render_for_channel`) zeigen für denselben angehobenen/gedämpften
    Datenpunkt dieselbe Stufe — ein Test pro Kanal auf denselben Fixture-Datenpunkt.
  - `confidence_pct`-Berechnung bleibt bei unverändertem Spread bit-identisch (Regressionstest
    gegen bestehende Tests von `compute_confidence_pct`).

## Known Limitations

1. **`fetch_forecast(enrich_ensemble=True)`-interner Pfad** (`trip_forecast.py:156`,
   `services/forecast.py:85`) bekommt nur die Typanpassung, keine `modelllauf`-Semantik —
   mögliche Inkonsistenz zwischen Trip-Briefing-Pfad und diesen Aufrufern, falls sie
   ebenfalls Gewitterstufen anzeigen. Nicht untersucht, ob das zutrifft — Folgepunkt.
2. **Keine Eichung möglich** (fehlender Member-Mitschnitt), s. Schwellen-Herkunft — die
   Wirkung auf die 9 überprognostizierten KHW-Tage bleibt unbelegt.
3. **Ensemble-Abrufe laufen am internen Budget-Zähler vorbei** (`forecast_budget.py:40`,
   `record_call()` nur `segment_weather.py:196`) — bestehendes Risiko, nicht in diesem
   Ticket behoben.
4. **`ecmwf_ifs04` kostet weiterhin Gewicht ohne Nutzen** im Spread-/Confidence-Teil des
   Abrufs (nur für die neue Mehrheits-Berechnung ausgeschlossen) — Sammel-Eintrag #1199.
5. ✅ **Kontrolllauf-Schlüsselname geklärt (verifiziert in /40, 2026-09-19).** Die Annahme
   "unsuffixierter Schlüssel je Modell" traf in der Form nicht zu — die echten Schlüssel sind
   `weather_code_icon_seamless_eps` und `weather_code_ncep_gefs_seamless` (voller API-Name,
   kein einfaches `<modell>`-Suffix, GEFS zusätzlich mit abweichendem Präfix). Die
   Implementierung filtert deshalb generisch über `startswith("weather_code") and "ecmwf" not
   in k` statt über eine feste Modellnamen-Liste — Details in "Implementierung — Abruf",
   Punkt 1, Korrektur-Hinweis.
6. **Alarm-Pfad** (`trip_alert.py:2461-2466`, `enrich_ensemble=False`) bleibt unverändert —
   ausdrücklich Out of Scope (Kontingent-Erwägung, s. Context-Datei).

## Acceptance Criteria

- **AC-1:** Given der Verbrauch eines Ensemble-Abrufs mit zusätzlichem `weather_code` ist noch
  unbekannt / When diese Spec vor der Implementierung geschrieben wird / Then liegt die
  Messung schriftlich in der Sektion "Messung / Kosten" vor (heute ≈14, mit `weather_code`
  ≈21 gewichtete Calls je Abruf, ≈200–650 von 10.000/Tag bei 1–3 aktiven Trips) und trägt die
  Kosten-Entscheidung.
  - Test: Vorhandensein und Plausibilität der Zahlen in dieser Spec, kein Code nötig.

- **AC-2:** Given eine Stunde, für die mindestens 20 Ensemble-Member einen gültigen
  Wettercode geliefert haben und mindestens 60 % davon einen Gewittercode (95/96/99) tragen /
  When die Stunde fusioniert wird / Then trägt die Stufe dieser Stunde mindestens `HIGH`
  ("hoch"), das Fusionssignal `modelllauf` erscheint in `thunder_level_signals` mit der
  Beschriftung "Modellläufe".
  - Test: Given/When wie oben (Fixture-Stunde mit 65 % Gewittercode-Anteil) / Then
    `dp.thunder_level == ThunderLevel.HIGH` UND `"modelllauf" in dp.thunder_level_signals`.

- **AC-3:** Given eine Stunde mit einem Gewittercode-Anteil zwischen 10 % und 59 % (jeweils
  einschließlich) / When die Stunde fusioniert wird / Then trägt `modelllauf` NICHT zur
  Fusion bei — kein Eintrag `"modelllauf"` in `thunder_level_signals`, die Stufe bleibt
  ausschließlich von den vier bestehenden Signalen bestimmt.
  - Test: Fixture-Stunde mit 45 % Anteil, `dp.thunder_level_signals` enthält kein
    `"modelllauf"`, Stufe unverändert gegenüber dem Stand ohne S6.

- **AC-4:** Given eine Stunde mit einem Gewittercode-Anteil unter 10 % (nur wenige Läufe) und
  einem bereits vorhandenen Einzelmodell-Signal (z.B. `cape` auf `MED`) / When die Stunde
  fusioniert wird / Then wird die fusionierte Stufe um GENAU eine Stufe gesenkt (hier: `MED`
  → `LOW`, nutzersichtbar verlässt der Wert damit die vierstufige Leiter nach ADR-0064),
  niemals unter `NONE`.
  - Test: Fixture-Stunde mit 5 % Anteil und Ausgangsstufe `MED` ⇒ Ergebnis `LOW`; Ausgangsstufe
    `HIGH` ⇒ Ergebnis `MED` ("hoch" wird zu "Gewitter möglich"); Ausgangsstufe `LOW` ⇒ Ergebnis
    `NONE` mit geleerter Trägerliste.

- **AC-5:** Given eine Stunde mit einem Gewittercode-Anteil zwischen 10 % (einschließlich) und
  59 % (einschließlich) / When die Stunde fusioniert wird / Then bleibt die fusionierte Stufe
  unverändert — weder Anhebung noch Dämpfung; die Grenzwerte sind eindeutig zugeordnet: genau
  60 % gehört zur Anhebung (AC-2), genau 10 % gehört NICHT zur Dämpfung (AC-4 greift erst
  darunter).
  - Test: Fixture-Stunden mit exakt 10 % und exakt 59 % Anteil ⇒ Stufe jeweils unverändert.

- **AC-6:** Given zwei Stunden mit identischem Ausgangssignal-Satz, aber unterschiedlichem
  Gewittercode-Anteil / When beide fusioniert werden / Then sinkt die fusionierte Stufe nie,
  wenn der Anteil steigt — die Reihenfolge (<10 % ≤ 10–59 % ≤ ≥60 %) bildet sich monoton in
  den Ordinalstufen NONE≤LOW≤MED≤HIGH ab.
  - Test: dieselbe Ausgangsstufe mit drei verschiedenen Anteilen (5 %, 30 %, 70 %) durchlaufen
    lassen, Ergebnis-Ordinale müssen nicht-fallend sein.

- **AC-7:** Given der Ensemble-Abruf schlägt fehl oder liefert eine leere Antwort (`{}`) /
  When die Etappe trotzdem fusioniert und ausgeliefert wird / Then bleibt
  `thunder_probability_pct` bei jedem betroffenen Datenpunkt `None`, kein `modelllauf`-Signal
  entsteht, keine Dämpfung greift — die Stufe entspricht exakt dem Stand ohne S6 (niemals
  `NONE`/0 allein wegen des Ausfalls).
  - Test: `_fetch_ensemble_spread` liefert `{}` (Muster wie Bestandstest AC-6 aus #121) ⇒
    Stufe/Signale unverändert gegenüber einem Lauf ohne S6-Code.

- **AC-8:** Given eine einzelne Stunde innerhalb eines ansonsten erfolgreichen Ensemble-Abrufs
  liefert weniger als 20 gültige Wettercode-Werte (Teilantwort) / When diese Stunde
  fusioniert wird / Then bleibt `thunder_probability_pct` NUR für diese Stunde `None`, ohne
  Anhebung oder Dämpfung — Nachbarstunden mit ≥20 gültigen Werten sind davon unberührt.
  - Test: Fixture mit einer 15-Member-Stunde neben einer 40-Member-Stunde ⇒ erste Stunde
    `None`/unverändert, zweite Stunde regulär angewandt.

- **AC-9:** Given ein Datenpunkt, dessen Stufe bereits durch den Radar-Override
  (Beobachtung, `_apply_radar_override`) auf mindestens `MED` gehoben wurde (`"radar"` in
  `thunder_level_signals`) und dessen Gewittercode-Anteil gleichzeitig unter 10 % liegt /
  When die Ensemble-Dämpfung angewendet wird / Then wird dieser Datenpunkt NICHT gedämpft —
  die Beobachtung schlägt das Modell. Eine Anhebung durch `modelllauf` (≥60 %) bleibt am
  selben Datenpunkt weiterhin möglich.
  - Test: Fixture-Stunde mit `thunder_level_signals=["radar"]`, Stufe `MED`, Anteil 5 % ⇒
    Stufe bleibt `MED`; dieselbe Stunde mit Anteil 65 % ⇒ Stufe wird `HIGH`.

- **AC-10:** Given eine Stunde mit angehobener (`modelllauf`, ≥60 %) oder gedämpfter (<10 %)
  Stufe / When der Trip-Report für alle vier Kanäle gerendert wird / Then zeigen Mail,
  Telegram, SMS und Premium-SMS für diese Stunde dieselbe Stufe — keine kanalspezifische
  Sonderlogik (ADR-0025, eine Fusion speist alle Renderer über `dp.thunder_level`).
  - Test: ein Fixture-Datenpunkt, vier Renderer-Aufrufe, Stufenvergleich (Render-Wert bzw.
    Textbaustein je Kanal auf dieselbe zugrunde liegende Stufe zurückführbar).

- **AC-11:** Given der Trip-Report-Hauptlauf für eine bestimmte Etappe / When
  `_enrich_ensemble_for_trip` den Ensemble-Anker bestimmt / Then liegt der Anker auf einem
  Wegpunkt DIESER Etappe (letztes Segment aus dem übergebenen `weather_data`), nicht mehr auf
  dem letzten Wegpunkt der gesamten Tour.
  - Test: Trip mit ≥2 Etappen, `_enrich_ensemble_for_trip` für die erste Etappe aufgerufen ⇒
    die an `_fetch_ensemble_spread` übergebene `Location` entspricht einem Wegpunkt der
    ersten, nicht der letzten Etappe.

- **AC-12:** Given ein Briefing mit Hauptlauf, bis zu drei Ausblicks-Etappen und dem
  Gewitter-Fallback / When das Briefing erzeugt wird / Then bleibt die Zahl der
  Ensemble-API-Aufrufe je Aufruf von `_enrich_ensemble_for_trip` bei genau 1 — die
  Anker-Korrektur ändert die abgefragte Koordinate, nicht die Aufrufzahl.
  - Test: Zähler-Mock auf `_fetch_ensemble_spread`-Aufrufhäufigkeit über einen kompletten
    Trip-Report-Lauf, Vergleich mit dem Stand vor dieser Änderung.

- **AC-13:** Given die bestehende `confidence_pct`-Berechnung (Spread aus `temperature_2m`/
  `precipitation`) / When die neue `weather_code`-Abfrage und der neue Rückgabetyp eingeführt
  werden / Then bleibt `compute_confidence_pct()` für identischen Spread-Input bit-identisch
  — `confidence_pct` ist keine wählbare Metrik (ADR-0005/#710) und wird durch dieses Ticket
  nicht in seiner Formel verändert (nur die Koordinate kann sich durch AC-11 verschieben,
  s. Risiko-Hinweis).
  - Test: bestehende `compute_confidence_pct`-Tests bleiben grün, ein neuer Test vergleicht
    Spread-Werte vor/nach der Typumstellung auf Gleichheit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** [ADR-0073](../../adr/0073-modelllauf-mehrheit-als-daempfendes-fusionssignal.md)
  (angelegt, Status Akzeptiert, Index-Drift-Test grün)
- **Rationale:** Bisher galt in der Gewitter-Fusion die Regel "ein Signal kann nur fehlen
  (`None`) oder anheben — nie senkt ein Signal eine bereits höhere Stufe eines ANDEREN
  Signals" (CAPE wird durch CIN gedämpft, aber CIN ist Teil DESSELBEN Signals, kein externer
  Dämpfer über die Fusionsgrenze hinweg). `modelllauf` ist das erste Signal, das absichtlich
  die Ergebnisse der VIER ANDEREN, unabhängig berechneten Einzelmodell-Signale nachträglich
  senkt — eine neue Semantik-Klasse an der Gewitterstufe, die dokumentiert werden sollte,
  bevor ein künftiges sechstes Signal denselben Mechanismus kopiert oder fälschlich annimmt,
  die Fusion sei rein additiv (max-only). Ergänzt ADR-0025 (eine Fusion, eine Skala) um den
  Fall "ein Signal darf senken", ohne ADR-0025 selbst zu widerrufen.

## Changelog

- 2026-09-19: Initial spec created (Issue #1983, PO-Entscheid "beides, mit Schwellen")
- 2026-09-19: Implementiert und GREEN (`src/providers/openmeteo.py`, `src/app/thunder_scale.py`,
  `src/services/trip_report_scheduler.py`, Kerntests
  `tests/tdd/test_thunder_modelllauf_mehrheit.py` mit Fixture
  `tests/fixtures/openmeteo_ensemble/wolayersee_2026-09-19_weather_code.json`). ADR-0073
  angelegt und im Index verzeichnet (`tests/test_adr_index_drift.py` grün). Known Limitation 5
  (Kontrolllauf-Schlüsselname) in /40 gegen die echte Fixture geklärt — Details bei
  "Implementierung — Abruf" Punkt 1 und Known Limitations Punkt 5. Status auf `implemented`,
  Approval nachgezogen.
