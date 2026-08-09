# Context: fix-1601-modellwechsel-alarm

Issue #1601 · Standard Track · Basis `origin/main` = `4725c3f3` · erstellt 2026-08-09

## Request Summary

Der Änderungs-Alarm vergleicht den gespeicherten CAPE-Wert mit dem frisch abgerufenen, ohne
zu prüfen, ob beide vom selben Wettermodell stammen. Wechselt zwischen zwei Läufen das
liefernde Modell, springt die Zahl allein deshalb — und löst einen Alarm aus, obwohl sich das
Wetter nicht geändert hat.

## Was seit #1592 bereits steht (gemessen, nicht aus dem Ticket gelesen)

Das Issue schreibt: „das konkrete Modell steht im Schnappschuss gar nicht erst". **Das gilt
nicht mehr.** Scheibe C0 hat `SegmentWeatherSummary.cape_model_id` eingeführt
(`src/app/models.py:454`); der Serialisierer schreibt alle nicht-leeren Felder generisch mit
(`weather_snapshot.py:201-215`, `vars()`-basiert), der Leser holt sie generisch zurück
(`:218-234`, `dataclasses.fields`-basiert). Das Feld musste dafür nirgends eigens angemeldet
werden.

**Beleg am laufenden Produktivsystem**, nicht am Code:
`/var/lib/gregor/users/henning/weather_snapshots/5f534011_2026-08-09.json`, geschrieben
2026-08-09 05:00 UTC — jede Etappe trägt `"cape_model_id": "icon_d2"` neben ihrem
`cape_max_jkg`.

Die Hartcodierung `model="snapshot"` beim Laden (`weather_snapshot.py:281`) betrifft **nur**
die rekonstruierte Stunden-Zeitreihe (`NormalizedTimeseries.meta`), nicht das Aggregat. Das
Aggregat wird getrennt über `_deserialize_summary(data["aggregated"])` gelesen. Die Herkunft
im Schnappschuss überlebt das Laden also unverändert.

**Zu bauen bleibt allein der Vergleich.** Heute liest der Δ-Pfad ausschließlich die Herkunft
des **frischen** Werts (`weather_change_detection.py:630` — `new_summary.cape_model_id`);
`old_summary.cape_model_id` wird an keiner Stelle gelesen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/weather_change_detection.py:598-694` | Δ-Zweig; der CAPE-Sonderpfad `:622-634` ist der Andockpunkt des Guards |
| `src/services/deviation_alert_engine.py:207-221` | **Einziger** live erreichbarer Aufrufer von `detect_changes()` |
| `src/services/trip_alert.py:265` | Trip-Alarm → `DeviationAlertEngine.evaluate()` |
| `src/services/compare_alert.py:371-374` | Ortsvergleich-Alarm → dieselbe Engine |
| `src/app/model_registry.py:64-72,148-169` | `effective_cape_model_id()`, `cape_delta_threshold_jkg()` — das bestehende Abstain-Muster |
| `src/app/models.py:454` | `cape_model_id` am Etappen-Aggregat |
| `src/services/weather_metrics.py:802` | Befüllung: `cape_model_id=effective_cape_model_id(timeseries.meta)` |
| `src/services/weather_snapshot.py:201-234` | Generische Serialisierung beider Richtungen |
| `src/services/compare_weather_snapshot.py:63,93` | Ortsvergleich benutzt **denselben** Serialisierer |
| `src/providers/openmeteo.py:1030` | Log-Zeile des Modellwechsels (`Model fallback: … → next endpoint`) |
| `tests/tdd/test_cape_delta_modellschwelle.py` | 9 Tests zum CAPE-Δ-Sonderpfad — fachlicher Ort für den Regressionstest |

## Existing Patterns

- **Abstain statt Rateschätzung:** „unbekannte Herkunft" und „Kombination ohne Eichwert"
  heißen im `model_registry` an jedem Nachschlagort identisch `None`, und `None` führt im
  Δ-Pfad zu `continue` — kein Alarm, kein Ersatzwert. Der Guard aus #1601 ist derselbe
  Gedanke, eine Ebene früher: nicht „welcher Wert", sondern „vergleichbar überhaupt?".
- **Sonderpfad vor der Delta-Berechnung:** Der Ordinal-Sonderfall (`_ordinal_levels`) und der
  CAPE-Sonderfall sitzen beide **vor** `delta = new - old`. Dort gehört auch der Guard hin.
- **Kein Default an der Signaturgrenze:** #1592 hat bewusst Parameter ohne Default gesetzt,
  damit ein vergessener Aufruf hart bricht statt still zu raten.

## Dependencies

- **Upstream:** `model_registry` (Normalisierung + Eichung), `thunder_routing.thunder_region_for`
  (Gebietsbestimmung), Aggregation in `weather_metrics`.
- **Downstream:** beide Alarmwege (Trip, Ortsvergleich) — sie teilen sich `DeviationAlertEngine`.
  Ein Guard hier wirkt auf beide gleichzeitig; das ist gewollt und entspricht der
  Trip/Compare-Teilungsregel.

## Existing Specs

- `docs/specs/modules/fix_1592_c3_cape_delta_alarme.md` — die Scheibe, auf der #1601 aufsetzt
- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` — Befund A/B, Scheibenfolge
- `docs/context/fix-1592-cape-modellschwelle.md` Abschnitt „Befund B" — die Erstbeschreibung
- ADR-0009 (Vergleichsanker), ADR-0025 (Einstiegsfunktion als Prüfort)

## Realitätsbeleg: tritt der Fall überhaupt auf?

Ja, gemessen in den Produktivlogs (`journalctl -u gregor-python`):

| Zeitraum | Modellwechsel |
|---|---|
| letzte 14 Tage | 2 (28.07. `meteofrance_arome`, 30.07. `icon_d2`, beide „transient") |
| letzte 60 Tage | 10+, darunter am 08.07. vier 503-bedingte Wechsel binnen einer Sekunde |

Bemerkenswert: **kein einziger CAPE-Lückenfüller-Fallback** in 14 Tagen (0 Treffer auf
`Fallback … filled` mit `cape`). Der Modellwechsel passiert also nicht über
`meta.fallback_model`, sondern über den Endpunkt-Wechsel des Primärmodells — genau der Weg,
den `effective_cape_model_id()` über `meta.model` abbildet.

Weil der Rückfall **transient** ist, wirkt er doppelt: Lauf N schreibt den Anker mit AROME,
Lauf N+1 vergleicht mit ICON (Falschalarm), Lauf N+2 ist wieder AROME (zweiter Falschalarm in
Gegenrichtung).

## Risks & Considerations

1. **Der Guard unterdrückt — das ist die eigentliche Gefahr.** Zu weit gefasst, verschwinden
   echte Gewitter-Änderungsalarme lautlos. Dieses Fehlerbild hatten wir schon zweimal (#1584:
   Regel konnte strukturell nie auslösen; #1555: Alarme wurden system-weit nie zugestellt).
   Der Adversary-Lauf muss gezielt prüfen, ob bei **gleichem** Modell noch alles feuert.
2. **Altbestand ohne Herkunft.** Anker von vor dem 08.08. tragen `cape_model_id: None`. Fasst
   der Guard „None vs. icon_d2" als Modellwechsel auf, schweigen die Alarme, bis der Anker
   einmal neu geschrieben ist. Für Trips ist das harmlos (täglicher Report überschreibt), für
   den Ortsvergleich siehe Punkt 3. Die Alternative — „None heißt egal" — wäre die
   gefährlichere Wahl, weil sie genau den unbelegten Fall durchwinkt.
3. **OFFEN, nicht gemessen: trägt der Ortsvergleich die Herkunft wirklich?** Die Code-Kette
   spricht dafür (`CompareLocationWeatherSource.fetch` → `SegmentWeatherService` →
   `WeatherMetricsService:802`, also derselbe Weg wie beim Trip). **Ein Beleg am laufenden
   System fehlt aber:** alle 13 Compare-Anker in Produktion stammen vom 31.07. und tragen das
   Feld nicht — seither wurde kein Compare-Report versendet, und #1584 Scheibe C verwirft
   Anker älter als 26 h ohnehin. Die Aussage bleibt damit hergeleitet. Nachweis gehört in die
   Spec (Staging: Compare-Report auslösen, geschriebenen Anker aufmachen).
4. **Reichweite der Regel.** Herkunft gibt es nur für CAPE. Andere Metriken (Wind,
   Niederschlag) streuen zwischen Modellen ebenfalls, tragen aber keine Herkunftsangabe — ein
   Guard für sie wäre nicht baubar, ohne das Fundament zu verbreitern. Spec-Entscheidung:
   Scheibe bleibt auf CAPE.
5. **Toter Code als Falle.** `trip_alert.py:604-632` enthält ein zweites, unerreichbares
   `_detect_all_changes` (seit #1168 ersetzt). Wer den Guard dort einbaut, härtet einen Pfad,
   den niemand geht — bekanntes Muster aus dem Memory („Adversary härtet ggf. den falschen
   Pfad"). Der Prüfort ist `DeviationAlertEngine`.

## Analysis

### Type

Bug. Fehlende Prüfung im Δ-Pfad, kein neues Verhalten.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/weather_change_detection.py` | MODIFY | Guard nach `threshold = effective_threshold` (:634): `old_summary.cape_model_id != new_summary.cape_model_id` ⇒ `continue` |
| `tests/tdd/test_cape_delta_modellschwelle.py` | MODIFY | 3 Testfälle + Helfer mit getrennter Alt-/Neu-Herkunft (der bestehende `_cape_pair`, :88-111, kennt nur EINEN gemeinsamen Wert) |

### Scope Assessment

- Produktivcode: 1 Datei, 3-6 LoC · Test: 1 Datei, 50-90 LoC · **Summe ~55-95 LoC** (Limit 250)
- Risiko: MEDIUM — winziger Eingriff, aber im unbeaufsichtigten Alarm-Pfad

### Technical Approach

Der Guard sitzt **nach** dem bestehenden Schwellen-Abstain, nicht davor. Das ist keine
Stilfrage: `cape_delta_threshold_jkg()` bricht bereits ab, wenn die Herkunft des **frischen**
Werts unbelegt ist. Nach dieser Zeile ist `new_summary.cape_model_id` also garantiert belegt —
der Vergleich prüft damit faktisch nur noch die Alt-Seite und kann bei gleichem Modell
strukturell nicht fälschlich unterdrücken. Stünde der Guard davor, meldete er „Modellwechsel",
wo in Wahrheit gar kein zweites Modell im Spiel ist, sondern schlicht keine Eichung vorliegt.

### Entscheidung: `None` zählt als Abweichung (Regel a)

Von drei denkbaren Regeln ist nur diese konsistent zum bestehenden Code:

- **(a) `alt != neu` ⇒ kein Alarm, `None` zählt mit** ← gewählt
- (b) nur bei zwei belegten, verschiedenen Werten ⇒ kein Alarm: behandelt „unbekannt" auf der
  Alt-Seite als alarmwürdig, während dieselbe Unbekanntheit auf der Neu-Seite seit C3 zum
  Abstain führt. Widersprüchlich — und erzeugt beim ersten Lauf nach jedem Anker-Neuaufbau
  genau den Fehlalarm, den #1601 beseitigen soll.
- (c) wie (a), aber mit eigenem Grund „nicht belegt": verhaltensgleich, verlangt aber
  Begründungs-Infrastruktur pro Metrik, die es nicht gibt (`detect_changes` kennt kein
  Reason-Tracking; `EvaluationResult.suppressed_reason` sitzt eine Ebene höher und kennt drei
  feste Werte). Aufwand ohne Abnehmer.

### Gegenangriff auf diese Analyse (analysis-challenger, VERDICT CONFIRMED)

Alle vier Kernbehauptungen halten am Code stand — insbesondere zwei, die ich nur hergeleitet
hatte: Das Aggregat wird auf dem gesamten Weg vom geladenen Vergleichspunkt bis zur
Vergleichsstelle **nirgends neu gebaut** (`point_weather.py:96-110` und
`deviation_alert_engine.py:74-77` reichen dasselbe Objekt durch), und die Log-Zeile
„Model fallback" bedeutet tatsächlich einen Wechsel der Modellwelt: die fünf Einträge in
`REGIONAL_MODELS` sind disjunkt und bilden 1:1 auf sich selbst ab, der erfolgreiche Kandidat
landet über `_parse_response()` in `meta.model`. Kein Endpunktwechsel innerhalb derselben Welt.

### Zwei Befunde aus dem Gegenangriff

**1. Gemischte Etappen sind kein Altbestands-, sondern ein Dauerfall.** Die Aggregation setzt
`cape_model_id` nur, wenn alle Segmente einer Etappe dasselbe Modell tragen — sonst `None`
(`weather_metrics.py:837,1196-1203`, Regel `agreement`). Eine Etappe an einer Modell-Gitter-
grenze liefert damit **jeden Tag** `None`. Wichtig für die Einordnung: dort greift schon heute
der C3-Abstain (Neu-Seite unbelegt), CAPE-Änderungsalarme feuern dort also bereits seit
gestern nie — **das ist Erbe von #1592 C3, nicht Folge dieses Guards.** Der Guard fügt genau
einen Fall hinzu: Alt gemischt (`None`), Neu einheitlich ⇒ kein Alarm. Das ist fachlich
richtig, weil ein Mischwert und ein Einzelmodellwert nicht vergleichbar sind.
Gemessen: der heutige Produktiv-Trip hat 5 von 5 Etappen einheitlich `icon_d2`, also keinen
Mischfall. Für Grenzrouten (Korsika/Festland) liegt **keine Messung** vor.

**2. Ein zugestellter Falschalarm durch Modellwechsel ist NICHT belegt.** Der Mechanismus ist
belegt (10+ Modellwechsel in 60 Tagen), die Auswirkung nicht. Im Alarm-Log aller drei Nutzer
stehen genau **2 CAPE-Änderungsalarme** (05.08. LOW, 06.08. MODERATE, beide
`reason: forecast_change`) — an beiden Tagen gab es keinen Modellwechsel. Die Begründung für
#1601 bleibt damit: der Weg ist offen und wird begangen, ein Schaden ist noch nicht
nachgewiesen. Das ist ein Argument für den Fix, aber keins für Eile.
(Messhinweis: die Alarm-Logs haben je Nutzer zwei Formate — Liste bzw. Objekt mit `entries`.
Wer die falsche Ebene liest, zählt 0 statt 2.)

### Open Questions (für die Spec)

- [ ] Nachweis, dass der Ortsvergleich die Herkunft wirklich mitschreibt — am laufenden System,
      nicht am Code. In Produktion gibt es keinen frischen Compare-Vergleichspunkt.
- [ ] Soll ein Grenzrouten-Dauerschweigen (Befund 1) als eigener Befund gegen #1592 C3
      gebucht werden? Betrifft nicht diese Scheibe.

## Testabdeckung heute

18 Testdateien fassen `detect_changes` an; die einzige, die den CAPE-Sonderpfad direkt prüft,
ist `tests/tdd/test_cape_delta_modellschwelle.py` (9 Tests, inkl. `test_ac7_…`, das bewusst
über `DeviationAlertEngine` — also den Live-Pfad — geht).

**Kein einziger Test prüft Herkunfts-Identität zwischen alter und neuer Basis.** Der Helper
`_seg(...)` (Zeile 89-106) setzt für alt und neu immer denselben Modellschlüssel; ein
Modellwechsel kommt in keinem Testfall vor. Die Lücke aus dem Issue ist damit bestätigt.
