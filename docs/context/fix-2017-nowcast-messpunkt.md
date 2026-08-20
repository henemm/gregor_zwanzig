# Context: fix-2017-nowcast-messpunkt

Issue: [#2017](https://github.com/henemm/gregor_zwanzig/issues/2017) · Track: Full Process · Phase 1 (Kontext)

## Request Summary

Der Radar-/Nowcast-Alarm fragt das Wetter am **Startpunkt des aktiven Segments** ab — dem Wegpunkt, den der Wanderer bereits passiert hat. Gemeldet wird damit Wetter für einen Ort, an dem der Nutzer zum genannten Zeitpunkt nicht mehr steht. Gemessen (Issue-Kommentar, echte KHW-Tour): Median 2,68 km Versatz **während der Gehphasen**, in 68 % der Geh-Minuten liegt der Onset gar nicht mehr im abgefragten Segment.

## 🔴 Zentraler Befund: die Sollformulierung ist mit einem Abruf nicht erreichbar

Das Issue nennt als fachlich richtig „die **Position zum Onset-Zeitpunkt**". Der Code-Ablauf macht das mit einem einzigen Abruf **prinzipiell unmöglich** — es ist ein Zirkelschluss:

| Schritt | Code | Konsequenz |
|---|---|---|
| 1 | `lat/lon = active.start_point` (`trip_alert.py:1257-1259`) | Ort steht fest, **bevor** irgendetwas über das Wetter bekannt ist |
| 2 | `radar_svc.get_nowcast(lat, lon, priority="polling")` (`:1265`) | Abruf erfolgt |
| 3 | `onset_minutes` entsteht in `_derive_result()` (`radar_service.py:543-599`) | erster Frame im 180-Min-Fenster über der Niederschlagsschwelle |
| 4 | `_onset_dt = now_utc + timedelta(minutes=result.onset_minutes)` (`:1282`) | **Erst hier** ist der Onset-Zeitpunkt bekannt — der Abruf ist längst gelaufen |

**Man kann die Position zum Onset-Zeitpunkt nicht abfragen, ohne den Onset zu kennen, und man kennt den Onset erst nach der Abfrage.** Jede Lösung muss diesen Zirkel brechen. Die Optionen:

- **Onset-frei schätzen** (Issue-Variante 1): Position zu einem *festen* Zeitpunkt im Vorwarnfenster (z. B. Mitte) — braucht den Onset nicht, ein Abruf, deterministisch.
- **Zweistufig/iterativ**: erst abfragen, Onset lesen, dann an der Onset-Position erneut abfragen — zwei Abrufe, und das Ergebnis kann zwischen den Stufen widersprüchlich werden (anderer Ort ⇒ anderer Onset ⇒ andere Position …).
- **Trajektorie** (Variante 3): pro Vorhersage-Zeitschritt die zugehörige Position auswerten — löst den Zirkel sauber auf, weil jeder Zeitschritt seine eigene Position mitbringt; teuerste Variante.

Das ist **keine** Ablehnung des Issue-Ziels, sondern die Feststellung, dass „Position zum Onset-Zeitpunkt" bei einem Abruf nur als *Näherung* zu haben ist. Die Spec muss die Näherung benennen, statt exakte Onset-Treue zu versprechen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py:1257-1260` | **Der Fehler.** `lat/lon` fix aus `active.start_point`, Kommentar sagt „Genau EIN get_nowcast-Call pro Trip an Segment-Startpunkt" |
| `src/services/trip_alert.py:1265` | `radar_svc.get_nowcast(lat, lon, priority="polling")` |
| `src/services/trip_alert.py:1270` | `radar_alert_due(result, threshold_min=20)` — **Inline-Literal**, keine Konstante (#2009 macht daraus `RADAR_ONSET_THRESHOLD_MIN=55`) |
| `src/services/trip_alert.py:1282` | `_onset_dt` — erst hier ist der Onset-Zeitpunkt bekannt |
| `src/services/trip_alert.py:126-129` | `radar_alert_due()` — `onset is not None and onset <= threshold_min` |
| `src/services/trip_alert.py:1155` | `resolve_current_segment(trip, now_utc, today)` |
| `src/services/trip_alert.py:1357-1362` | `RadarAlertRequest` bekommt `segment_id`, `km_from`, `km_to` aus `active` |
| `src/services/trip_segments.py:363-413` | `resolve_current_segment()` — Vorrangkette heute → gestern → Vorschau → None; schaut **nie vorwärts** |
| `src/services/trip_segments.py:345-360` | `select_active_segment()` — `None`, wenn alle Segmente vorbei |
| `src/services/trip_segments.py:108-342` | `convert_trip_to_segments()` — genau **ein** Kalendertag |
| `src/services/radar_service.py:170` | `get_nowcast(self, lat, lon, priority="user_briefing")` — kein `elevation_m`, kein Positions-/Zeitfenster |
| `src/services/radar_service.py:543-599` | `_derive_result()` — Onset rein zeitbasiert für den EINEN Punkt |
| `src/services/radar_cache.py:72-75` | Cache-Schlüssel `f"{round(lat,4)}_{round(lon,4)}_{region}"`, TTL 300s |
| `src/app/models.py:407-430` | `TripSegment` — trägt `start_time`/`end_time` (UTC), `duration_hours`, `distance_km` |
| `src/app/models.py:360-365` | `GPXPoint` — `lat`, `lon`, `elevation_m`, **kein Name** |
| `src/app/trip.py:61-86` | `Waypoint` — `name: str` Pflichtfeld, `elevation_m: int` ohne Optional |
| `src/utils/geo.py:19-29` | `haversine_km()` — einziger vorhandener Geo-Baustein (SSoT, #1027) |
| `src/core/naismith.py:81-127` | Gehzeit **kumulativ mit Steigung**, nicht linear nach Distanz |

## Existing Patterns

- **Segmente sind zeitlich lückenlos und aufsteigend**: `end_time` von Segment *i* ist bitgenau `start_time` von Segment *i+1* (`trip_segments.py:172-253`), das Ziel-Segment schließt genauso an. Zu einem Zeitpunkt T gilt normalerweise genau ein Segment. Ausnahme: der Guard `end_dt <= start_dt` (`:200-218`) **überspringt** ein Wegpunktpaar bei nicht vorwärtslaufender Zeit — dann fehlt ein Segment ersatzlos, keine synthetische Füllung.
- **Ortsfestes Ziel-Segment ohne Flag**: erkennbar an `segment_id == "Ziel"` (String statt int), `start_point == end_point`, `distance_km == 0.0`. Sauberster Filter für „bewegt sich": `isinstance(segment.segment_id, int)` bzw. `distance_km > 0`.
- **Gehzeit über Naismith** (`src/core/naismith.py`): `dist_km/speed_flat + ascent_m/speed_ascent + descent_m/speed_descent`, Wanderer 4 km/h flach, 300 m/h Aufstieg, 500 m/h Abstieg. Die Segment-Start-/Endzeiten tragen dieses Ergebnis bereits — **innerhalb** eines Segments (= ein Wegpunktpaar) gibt es keine Zwischenpunkte, dort ist lineare Interpolation nach Zeitanteil die einzig verfügbare Auflösung.
- **Ortsangabe im Alarm** (`output/renderers/alert/segments.py:91-111`): `format_alert_location()` → `location_label` (nur Ortsvergleich) → „Etappe N" → Fallback „km von–bis". Der Text nennt **keinen Wegpunktnamen**, ist also von einer Positionsverlegung nicht automatisch betroffen.
- **Fenster-Konvention aus #1417/#1146** (`output/renderers/day_window.py:186-229`): inklusiver Start, exklusives Ende, Sonderfall letztes Segment inklusiv.

## Dependencies

**Upstream (was wir nutzen):** `resolve_current_segment()` · `convert_trip_to_segments()` · `TripSegment` · `GPXPoint` · `haversine_km()` · `RadarNowcastService.get_nowcast()` · `ForecastBudgetGate`

**Downstream (was auf uns aufsetzt):** `RadarAlertRequest` → `notification_service` → Renderer aller vier Kanäle · Alarm-Logging/Metriken · Throttle-/Kanal-Gates

## 🔴 Keine wiederverwendbare Interpolation vorhanden

Breite Suche (`interpolate`, `lerp`, `fraction`, `progress`, `position_at`, `along_route`, `bearing`) in `src/`, `internal/`, `api/`: **keine Funktion interpoliert eine Position entlang einer Strecke.** `_interpolate_missing_times()` (`trip_segments.py:59-105`) interpoliert nur **Zeiten**, keine Geo-Position. Die räumliche Interpolation ist neu zu bauen; `haversine_km()` taugt nur zur Distanzprüfung, nicht zur Positionsberechnung.

## API-Budget: Variante 1 ist praktisch kostenneutral (geprüft)

Das Issue vermutet Kostenneutralität für den einfachen Mittelweg. Der Code bestätigt das für den tragenden Verbrauchsstrom:

| Größe | Wert | Fundstelle |
|---|---|---|
| Open-Meteo-Tageslimit | 10.000 | — |
| Intern gesetztes Budget | **9.000** | `services/forecast_budget.py:40-42` |
| `polling` wird abgewiesen ab | 80 % | `forecast_budget.py` (`POLLING_THRESHOLD`) |
| nur noch `user_briefing` ab | 95 % | `forecast_budget.py` (`BRIEFING_ONLY_THRESHOLD`) |
| Radar-Alarm-Takt | `7,22,37,52 * * * *` = 96×/Tag je Job | `internal/scheduler/scheduler.go:199,202` |
| Cache-TTL | 300 s | `radar_cache.py` |

**Kernargument:** Der Alarm läuft alle 900 s, der Cache lebt 300 s — zwischen zwei Läufen ist der Eintrag **immer** abgelaufen. Der Trip-Poll profitiert schon heute nie von seinem eigenen Vorlauf-Cache. Eine wandernde Koordinate ändert die **Zahl** der Abrufe dieses Stroms daher nicht.

**Zwei Randverluste, beide klein:**
- *Trip↔Compare-Dedup*: Compare misst an **festen Preset-Orten** (`compare_radar_alert.py:126-129,342`, Docstring `:13-16` — „keine Etappen/Segmente"). Ein gemeinsamer Cache-Treffer setzt exakte Koordinatengleichheit auf 4 Nachkommastellen voraus — Zufall, kein Regelfall.
- */jetzt-Nutzerbefehl* (`trip_command_processor.py:1369,1375`) fragt `stage.waypoints[0]` ab, oft identisch mit dem Segment-Startpunkt. Innerhalb von 300 s um einen Poll-Tick spart das heute einen echten Fetch; bei wandernder Koordinate trifft es seltener. Ohne Nutzungsdaten nicht quantifizierbar, aber keine 96×/Tag-Größenordnung.

**Zählweise geklärt:** `record_cache_hit()`/`record_cache_miss()` (`forecast_budget.py:83-91`) sind reine Beobachtungszähler und schreiben **nicht** in `calls_today`. Nur `record_call()` (`:76-81`) zählt, und zwar unmittelbar vor dem echten HTTP-Request (`radar_service.py:464`). Ein Koordinatenwechsel für sich kostet also **nichts** — nur ein dadurch zusätzlich ausgelöster realer Fetch kostet.

## 🔴 Der Fehler steht an ZWEI Stellen — die zweite wiegt schwerer

Alle fünf `get_nowcast()`-Aufrufer des Repos, vollständig geprüft:

| Datei:Zeile | Zweck | Positionsquelle | Vom #2017-Muster betroffen? |
|---|---|---|---|
| `src/services/trip_alert.py:1265` | Trip-Radar-Alarm, Onset-Schwelle 20 (nach #2009: 55) Min | `active.start_point` via `resolve_current_segment()` | **Ja — der im Issue beschriebene Kernbug** |
| `src/services/trip_report_scheduler.py:1815` | `_build_starkregen_hint()` — Starkregen-Kurzfristhinweis im planmäßigen Briefing, Horizont bis **180 Min** | `active.start_point`, **eigene lokale Segmentwahl** (`:1780-1789`) statt des geteilten Bausteins | **Ja — gleicher Mechanismus, größeres Fehlerfenster** |
| `src/services/trip_command_processor.py:1375` | `/jetzt`-Inbound-Kommando | `stage.waypoints[0]` — **erster Wegpunkt des Tages**, nicht einmal das aktive Segment | Andere Fehlerklasse (Sofort-Abfrage, kein Onset-Zirkel) — **eigenständiger Befund**, siehe Risiko 12 |
| `src/services/compare_radar_alert.py:342` | Ortsvergleich-Radar-Alarm | `loc.lat/lon` eines festen Presets | Nein — ortsfest per Definition |
| `src/providers/thunder_enrichment.py:255` | `_apply_radar_override()`, Fenster ±90 Min um jetzt | `location.lat/lon` der Reihe | Nein — Teil der akzeptierten Aggregations-Vereinfachung „ein Ort deckt die Reihe", kein Onset-Zirkel |

**Warum die zweite Stelle schwerer wiegt:** Der Alarmpfad begrenzt auf `onset_minutes <= 20` (nach #2009: 55). Der Starkregen-Hinweis kennt **keinen Minuten-Grenzwert auf den Onset** — er filtert nur auf `intensity_label == HEAVY` (`:1820`) und akzeptiert damit jeden Onset im vollen **180-Minuten**-Fenster (`NOWCAST_HORIZON_MIN = 180`, `radar_service.py:70`). Bei drei Stunden Vorlauf ist der Wanderer regelmäßig ein bis zwei Segmente weiter — der Hinweis nennt Starkregen für einen Ort, an dem er zum genannten Zeitpunkt längst nicht mehr ist, teils für einen, den die Route gar nicht mehr berührt.

**Abgrenzung gilt an beiden Stellen gleich:** nur Geh-Segmente; das ortsfeste Ziel-Segment wird von der lokalen Auswahlschleife wie jedes andere behandelt, ist dann aber der tatsächliche Standort — kein Versatz.

**Konsequenz für den Zuschnitt:** Beide Stellen teilen denselben Mechanismus und sollten über **einen gemeinsamen Baustein** korrigiert werden, statt zweimal getrennt — entspricht der Code-Teilungs-Konvention des Projekts. Dass `trip_report_scheduler.py` heute eine eigene Segmentwahl mitbringt (bewusst ohne Vortags-Rückgriff, Docstring `:1761-1771`, #1667 S3), ist dabei zu respektieren: geteilt wird die **Positionsberechnung**, nicht die Segmentwahl.

## Existing Specs

- `docs/specs/modules/fix_1329_c2_radar_nowcast_cache.md` — Radar-Cache + Anbindung an `ForecastBudgetGate` (ADR-0033: „ein Kontingent, ein Zähler")
- `docs/specs/modules/fix_2009_nowcast_vorlauf.md` — **nur auf `origin/fix-2009-nowcast-vorlauf`**, noch nicht auf `main` (lesbar per `git show origin/fix-2009-nowcast-vorlauf:<pfad>`). Status approved (PO-Freigabe 2026-08-20). Hebt `RADAR_ONSET_THRESHOLD_MIN` 20 → **55** als **eine geteilte Konstante** in `radar_service.py` (Muster `NOWCAST_HORIZON_MIN`, #1439) und ersetzt damit die heute doppelt gepflegten Literale in `trip_alert.py:1270` und `compare_radar_alert.py:53`. ACs: AC-1 geteilte Konstante treibt beide Pfade · AC-2/AC-3 Auslöseraster 8/23/38/53 für Trip und Compare · AC-4 Tagesbezug bei Mitternachts-Überlauf (E-Mail/Telegram) · AC-5 Tages-Suffix `TH@0:23+1` für SMS/Premium-SMS · **AC-6 Segment-Ende-Guard** (nur Trip; Compare kennt keine Segmente) — unterdrückt Alarme, deren Onset nach dem Segmentende liegt, mit Unterdrückungs-Log
- `radar_nowcast*.md` (mehrere) — Quellen-/Provider-Basis-Specs
- `docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md` · `fix_1914_radar_telegram_style.md` — nachgelagerte Kanal-/Darstellungsfragen

## Risks & Considerations

1. **🔴 Tagesgrenze.** `convert_trip_to_segments()` deckt **nur einen Kalendertag** ab, `resolve_current_segment()` schaut nur rückwärts. Bei 55 Min Vorlauf kann der Zielzeitpunkt über das Ende des Ziel-Segments hinauslaufen ⇒ `select_active_segment()` liefert `None`. Entweder Folgetag selbst nachladen (`target_date + 1 day`) oder bewusst am Tagesende klemmen. Fail-Soft nötig: Ruhetag ohne Stage oder < 2 Wegpunkte ⇒ leere Liste.
2. **🔴 Höhe muss mitwandern** (Abstimmung #1991, Session `gregor-zwanzig-ad`, Commit `892e0631`). Nach deren Merge trägt `get_nowcast` ein `elevation_m`; verlegt man die Koordinate ohne die Höhe, fragt man den neuen Ort mit alter Höhe ab. Gemessen an 3300 m: bis 2,4 mm Niederschlagsdifferenz, Wettercode in 11 von 48 Stunden abweichend — im Gebirge entscheidet das über Regen oder Schnee. Höhe ist verlässlich vorhanden (`Waypoint.elevation_m: int` ohne Optional, GPX-Import erzwingt sie über `gpx_parser.py:178-181`), muss aber **interpoliert** werden wie die Koordinate.
3. **🔴 Segment-Ende-Guard aus #2009 ist mit unserem Merge ersatzlos zu entfernen** — inklusive AC-6 und `tests/tdd/test_radar_alert_segment_end_guard.py`. Der Guard gleicht den falschen Messpunkt aus, statt ihn zu beheben; nach der Korrektur würde er **richtige** Alarme verwerfen. Dokumentiert in Commit `87644e6a` (Known Limitations der #2009-Spec) — dadurch vorgesehener Rückbau, kein stiller Spec-Widerruf.
4. **🔴 Zwei bestehende Tests schreiben den Bug fest.** `tests/tdd/test_issue_822_radar_nowcast_segment.py`: **AC-3** prüft exakte Gleichheit mit `active.start_point` (reißt sicher), **AC-2** (`test_ac2_segment_selection_by_time`) prüft dieselbe Koordinate mit Toleranz `< 0.01°` ≈ 1,1 km (reißt bei realistischem Versatz ebenfalls). Beide bewusst und begründet anpassen, nicht beiläufig.
5. **Nur Geh-Segmente betroffen.** Das ortsfeste Ziel-Segment macht 65,5 % der überwachten Zeit aus, der Ortsfehler ist dort exakt null. Wer über das ganze Tagesfenster mittelt, misst Median 0 km und hält den Befund für harmlos. Die Beispiel-Mail aus #2009 („🏁 Ziel · Gewitter in 8 Min") stammt aus diesem Segment und ist **kein** Beleg für den Bug.
6. **Reihenfolge.** `src/services/trip_alert.py` ist dreifach belegt: #1991 (`:1265`, committet, geht zuerst) → #2009 (`:1270` + Guard, Scheibe 1 grün `977c774f`, Scheibe 2 wartet) → #2017 (`:1257-1259`). Vereinbart und von beiden Sessions bestätigt.
7. **Drosselung ist nicht unterscheidbar — aber dokumentiert.** `radar_alert_due()` behandelt `onset_minutes=None` bei Drosselung wie „echt trocken". Bewusster Trade-off („a missed poll beats a quota outage", `radar_service.py:94-98`), festgehalten in den Known Limitations von `fix_1329_c2_radar_nowcast_cache.md:529-534`. **Kein blinder Fleck, nicht Teil dieses Tickets.**
8. **Kein Ortsname für den Zwischenpunkt.** `GPXPoint` trägt keinen Namen; ein interpolierter Punkt liegt namenlos zwischen zwei Wegpunkten. Da der Alarmtext ohnehin „Etappe N" / „km von–bis" nutzt, entsteht daraus kein Zwang — aber die Frage, ob `km_from`/`km_to` nach der Verlegung noch die richtige Aussage machen, gehört in die Spec.
10. 🔴 **Zweite Fundstelle bestätigt** (`trip_report_scheduler.py:1809-1810`, Horizont 180 Min, kein Onset-Grenzwert). Das Issue sagt „betrifft nur den Trip-Pfad" — beide Stellen *sind* Trip-Pfad. Die zweite ist im Issue nicht genannt, teilt aber Mechanismus und Lösung. **Zuschnitt-Entscheidung für die Spec:** beide gemeinsam über einen geteilten Baustein, oder #2017 auf den Alarmpfad begrenzen und die zweite Stelle als Folge-Issue führen. Empfehlung: gemeinsam — getrennte Lösungen desselben Problems sind laut Projektkonvention ein Verstoß, und die zweite Stelle wiegt schwerer.
11. **LoC-Budget — entschärft.** Mit dem Schnitt in zwei Scheiben (siehe Analyse) bleibt jede Scheibe unter 250 LoC; **kein Override nötig**.
12. **Nebenbefund `/jetzt`** (`trip_command_processor.py:1375`): fragt `stage.waypoints[0]` ab — den **ersten Wegpunkt des Tages**, nicht das aktive Segment. Wer nachmittags „jetzt" fragt, bekommt das Wetter vom Tagesstart, potenziell zweistellige Kilometer entfernt. Andere Fehlerklasse als #2017 (kein Onset-Zirkel, sondern falscher Bezugspunkt für eine Sofortabfrage), aber nutzersichtbar. **In der Analyse bewerten, ob eigenes Issue** — nicht stillschweigend in #2017 mitnehmen.
13. **AST-Wächter aus #1480** (Session `gregor-zwanzig-15`): nach dessen Merge wird jeder PR rot, der eine lokale ThunderLevel-Zuordnung anlegt. Vorgabe `thunder_ordinal()` / `THUNDER_LABEL_DE` / `thunder_ampel_band()`. Für #2017 voraussichtlich nicht einschlägig (Geometrie, keine Stufenlogik).

---

# Analysis

## Type

**Bug** — nutzersichtbares Fehlverhalten, PO-Einstufung „kritisch, höchste Priorität". Zugleich (siehe Framing unten) die **dritte Stufe einer dokumentierten Verfeinerungskette**, nicht die Korrektur einer Nachlässigkeit.

## Framing: #2017 ist Stufe 3, nicht Stufe 1

| Stufe | Issue | Abfragepunkt | Beleg |
|---|---|---|---|
| 1 | #656 | `waypoints[0]` — erster Wegpunkt des Tages | `docs/specs/modules/radar_nowcast.md:69` |
| 2 | #822 | `active.start_point` — Start des aktiven Segments | `tests/tdd/test_issue_822_radar_nowcast_segment.py:7-8,384-469` |
| **3** | **#2017** | **Position zum relevanten Zeitpunkt (interpoliert)** | dieses Ticket |

Die Ursprungs-Spec benennt die Näherung ausdrücklich als bekannte Grenze: **„'Aktuelle Position' = repräsentativer Punkt der heutigen Etappe, kein Live-GPS"** (`radar_nowcast.md:110`). Der Kommentar `trip_alert.py:1257` („Genau EIN get_nowcast-Call…") ist eine bewusste Budget-Entscheidung aus #1329, keine Schlamperei.

**Konsequenz:** Die neue Spec **aktualisiert diese Known Limitation**, statt sie neu zu erfinden — und liefert damit zugleich die saubere Begründung für die Anpassung der beiden bugfestschreibenden Tests (Risiko 4) und für den Guard-Rückbau (Risiko 3).

## Der Zirkelschluss ist beweisbar, nicht nur plausibel

Ein Abruf liefert eine Zeitreihe (`frames`) über bis zu 180 Min — aber **`RadarFrame` trägt überhaupt kein lat/lon**: die Felder sind `timestamp`, `precip_mm_h`, `is_convective` (`src/providers/brightsky.py:32-37`). Alle Frames stammen aus **einem** `_fetch_frames_with_fallback(lat, lon)` für **eine** fixe Koordinate (`radar_service.py:170-241`); `_derive_result()` filtert nur nach `f.timestamp`, nie nach Ort (`:543-599`). Auch die Provider-Ebene liefert bewusst Punkt-, keine Flächenabfragen (`geosphere.py:69`: „using timeseries for point queries (grid requires bbox)").

⇒ Eine Trajektorie (Position × Zeit) ist mit einem Abruf **strukturell unmöglich** — der Datentyp kann sie nicht tragen. Variante 3 kostet zwingend n Abrufe.

## Der Ortsfehler liegt außerhalb der Modellauflösung

| Quelle | Zellgröße | Fundstelle |
|---|---|---|
| GeoSphere INCA | **1 km** | `geosphere.py:71` (`nowcast-v1-15min-1km`) |
| AROME-FR | **1,3 km** | `openmeteo.py:127`, `meteofrance.py:794` |
| ICON-D2 | **2 km** | `openmeteo.py:132-135` |
| ARPAE ICON-2I | **2 km** | `radar_service.py:250` |

Der gemessene Median-Versatz von **2,68 km** entspricht dem **1,3- bis 2,7-Fachen** der Zellgröße der für den KHW relevanten Quellen (Abdeckung über die Bbox-Konstanten `radar_service.py:37-61`). Der Fehler liegt strukturell **außerhalb einer einzelnen Gitterzelle** — er verschwindet nicht im Modellrauschen. Das ist ein eigenständiges Argument für die fachliche Relevanz und gehört in die Spec.

## Präzisionsgrenze (PO-bestätigt, gehört als Known Limitation in die Spec)

Das System kennt die Ist-Position nicht und wird sie nie kennen — der Wanderer ist offline oder auf Satellit. **Das ist der Daseinszweck des Produkts, kein Mangel**: Online-Warnsysteme mit Live-Position existieren zahllos und helfen im Gebirge nicht (PO-Entscheid 2026-08-20). Kein GPS/Check-in vorschlagen.

Was die Korrektur leistet und was nicht, quantifiziert:

- Sei `p_plan` der geplante Fortschrittsanteil im Segment, `p_real` der tatsächliche.
- Fehler Startpunkt = `p_real` · Fehler Interpolation = `|p_plan − p_real|`
- **Die Interpolation ist mindestens so gut wie der Startpunkt, solange `p_real >= p_plan/2`** — also solange der Wanderer wenigstens die Hälfte des planmäßig erwarteten Fortschritts erreicht hat.
- Erst bei über 50 % Rückstand kann der Startpunkt zufällig näher liegen — dann aber „näher an falsch", nie richtig.

⇒ Die Korrektur beseitigt den **systematischen** Bias (der Startpunkt liegt *immer* zurück, nie voraus), nicht die **stochastische** Abweichung vom Plan. Genau so formulieren, statt „korrekte Position" zu versprechen.

**Randfall Vorschau-Zweig:** Liegt `now_utc` noch vor dem ersten Segment des Tages (Wanderer auf der Hütte), liefert `resolve_current_segment()` das erste Segment als Vorschau (`trip_segments.py:412`). Dort ist Fortschritt **0** die richtige Antwort. Der Fortschrittsanteil ist auf `[0,1]` zu klemmen und der Vorschau-Fall (`p_plan = 0`) vom aktiven Fall (`p_plan = elapsed/duration`) zu unterscheiden — sonst entsteht am Tagesbeginn ein Scheinfehler, wo keiner ist.

## Zweite Fundstelle — Formulierung präzisiert

`trip_report_scheduler.py:1809-1810` teilt den Mechanismus, Horizont 180 Min ohne Onset-Grenzwert. **Aber der gerenderte Text nennt gar keinen Ort:** `format_starkregen_hint()` (`output/renderers/email/starkregen_hint.py:18-27`) gibt nur `"{intensity_label} ab ca. {time_str} (in ~{onset_minutes} Min)."` aus — kein Etappenname, kein km-Bereich.

Der Schaden ist damit **nicht** „falscher Ortsbezug", sondern: **kein Ortsbezug ⇒ der Leser bezieht die Aussage selbstverständlich auf sich selbst, obwohl sie an einem Ort berechnet wurde, an dem er nicht ist.** Das verschärft die Fehlinterpretation, statt sie zu entschärfen.

## Affected Files

### Scheibe A — Baustein (sofort startbar, unabhängig von #1991/#2009)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_segments.py` | MODIFY | `position_at_time(trip, active, segment_date, at) -> GPXPoint` — lineare Interpolation von lat/lon/**elevation_m** nach Zeitanteil; Vorwärtssuche über Segment- und Tagesgrenze; Ziel-Segment stationär; Fortschritt auf `[0,1]` geklemmt; fail-soft auf letzten `end_point` |
| `tests/tdd/test_position_at_time.py` | CREATE | Within-Segment · Segmentgrenze · **Tagesgrenze** · Ziel-Segment stationär · Vorschau-Zweig (`p=0`) · Höhen-Interpolation · Fail-soft-Klemme |

### Scheibe B — Wiring (blockiert bis #1991 **und** #2009 auf `main`)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_alert.py` | MODIFY | `:1257-1265` — Abrufpunkt `position_at_time(at = now + RADAR_ONSET_THRESHOLD_MIN//2)`, Höhe mitgeben |
| `src/services/trip_report_scheduler.py` | MODIFY | `:1809-1815` — analog mit `NOWCAST_HORIZON_MIN//2`; **eigene Segmentwahl bleibt unangetastet** (#1667 S3) |
| `src/services/trip_alert.py` | MODIFY | Segment-Ende-Guard aus #2009 **ersatzlos entfernen** |
| `tests/tdd/test_radar_alert_segment_end_guard.py` | DELETE | zusammen mit AC-6 der #2009-Spec |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | MODIFY | **AC-2 und AC-3** auf den interpolierten Punkt umschreiben, mit Begründung aus der Verfeinerungskette |
| `docs/specs/modules/radar_nowcast.md` | MODIFY | Known Limitation `:110` fortschreiben |

## Scope Assessment

| Scheibe | Dateien | LoC (geschätzt) | Risiko |
|---|---|---|---|
| A | 2 | +180…220 | **LOW** — reiner Zusatzcode, keine Berührung mit fremden Branches |
| B | 6 | +60…100 saldiert (Guard-Rückbau zieht ab) | **MEDIUM** — kritischer Alarmpfad, zwei Fundstellen, Testanpassung |

**Kein `loc_limit_override` nötig.** Beide Scheiben bleiben unter 250 LoC.

## Technical Approach (Empfehlung)

**Variante 1 — Position zur Mitte des Vorwarnfensters, ein Abruf, Baustein in `src/services/trip_segments.py`.**

- **Warum nicht Variante 3 (Trajektorie):** strukturell unmöglich ohne n Abrufe (`RadarFrame` trägt keine Position). Für ein 55-Minuten-Fenster mit linearer Bewegung wäre der Aufwand ohnehin unverhältnismäßig.
- **Warum nicht Variante 2 (zwei Abrufe):** fachlich *schlechter*, nicht nur teurer — anderer Ort ⇒ anderer Onset ⇒ andere Position, das Ergebnis kann in sich widersprüchlich werden. Zudem doppeltes Budget.
- **Warum `trip_segments.py` und nicht `geo.py`:** `geo.py` ist Distanz-/Kompass-SSoT ohne Trip-Kenntnis (#1027). Die Interpolation braucht Segment- und Tagesgrenzen-Logik, die `trip_segments.py` bereits hält — dessen Docstring nennt es „SSoT for segment conversion, shared between briefing and radar alert" (`:4-5`). Dieselbe lineare Näherung wie die bestehende Zeit-Interpolation.
- **Geteilt wird die Positionsberechnung, nicht die Segmentwahl.** Beide Aufrufer übergeben ihr eigenes `(active, segment_date)`; der Baustein weiß nicht, woher es stammt.
- **Offset-Quelle:** je Aufrufer die halbe **bereits vorhandene** Konstante — `RADAR_ONSET_THRESHOLD_MIN//2` (Alarm) bzw. `NOWCAST_HORIZON_MIN//2` (Starkregen-Hinweis). Keine neue Konstante.

## Dependencies

- **Scheibe A:** keine. Sofort startbar.
- **Scheibe B:** #1991 (`elevation_m` an `get_nowcast`) **und** #2009 (geteilte Schwelle + der zu entfernende Guard) müssen auf `main` sein. Beide sind es **noch nicht** (`git merge-base --is-ancestor` gegen `892e0631` und `977c774f`: beide nein). Vor Beginn von Scheibe B am Code verifizieren, dass der Guard tatsächlich existiert — nicht aus der Doku annehmen.

## Open Questions

- [ ] Keine offenen **technischen** Fragen. Die Variantenwahl wird durch die laufende Messung (Restfehler je Variante) quantitativ untermauert; fällt sie unerwartet aus, wird die Empfehlung angepasst.
- [ ] **Zuschnitt-Bestätigung durch die Spec-Freigabe:** beide Fundstellen gemeinsam (Empfehlung) vs. nur der Alarmpfad.

## Nebenbefunde (nicht Teil dieses Tickets)

| Befund | Einordnung |
|---|---|
| `/jetzt` fragt `stage.waypoints[0]` ab — den Tagesstartpunkt (`trip_command_processor.py:1375`) | nutzersichtbar, andere Fehlerklasse ⇒ **eigenes Issue** prüfen |
| `starkregen_hint.py:4-5` Docstring nennt „60-Minuten-Nowcast-Fenster", real sind es seit #1945 **180** | stale Doku ⇒ Sammel-Issue **#1199** |
| Interpolierter Punkt kann theoretisch eine andere **Region** treffen (`_region_bucket()`) und damit eine andere Datenquelle | seltener Grenzfall an Modellgrenzen ⇒ **#1199**, kein Blocker |
| Drosselung ununterscheidbar von „trocken" | bereits dokumentiert (`fix_1329_c2…:529-534`), kein Handlungsbedarf |

## Wirksamkeitsmessung der Varianten (eigene Messung, 2026-08-20)

**Grundlage:** Trip `5f534011` „KHW 403", 13 Etappen, 51 Geh-Segmente, 3.595 Geh-Minuten, gelesen über `GET /api/_internal/trip/{id}/loaded`; Segmente über den echten `convert_trip_to_segments()`. Nur gelesen und gerechnet. Skript und Rohergebnis im Session-Scratchpad.
**Sanity-Check:** V0 bei H=55/worst case (Median 2,73 km) deckt sich mit der Vorgänger-Messung im Issue (H=53, Median 2,68 km) — Methodik konsistent.

**H = 55 min (Alarmpfad nach #2009), gleichverteilter Onset, n = 43.140**

| Variante | Median | p75 | p90 | Max | > 2 km | richtiges Segment |
|---|---|---|---|---|---|---|
| **V0 (heute)** | 1,99 | 2,89 | 3,68 | 6,53 | **49,7 %** | 63,9 % |
| **V1 (Mitte)** | **0,37** | 0,67 | 0,92 | 1,82 | **0,0 %** | 79,6 % |
| V1b (Fensterende) | 0,65 | 1,20 | 1,70 | 3,64 | 4,8 % | 64,0 % |
| V2 (zwei Abrufe) | 0,30 | 0,55 | 0,81 | 1,65 | 0,0 % | 97,5 % |
| V3 (Trajektorie) | 0,00 | — | — | — | 0 % | 100 % |

**H = 180 min (Starkregen-Kurzfristhinweis), gleichverteilter Onset, n = 133.015**

| Variante | Median | p75 | p90 | Max | > 2 km | richtiges Segment |
|---|---|---|---|---|---|---|
| **V0 (heute)** | 3,22 | 4,77 | 6,33 | 9,08 | **75,4 %** | 23,8 % |
| **V1 (Mitte)** | **0,73** | 1,64 | 2,45 | 5,31 | 17,6 % | 54,5 % |
| V1b (Fensterende) | 1,03 | 2,81 | 4,29 | 7,56 | 35,7 % | 41,1 % |
| V2 (zwei Abrufe) | 0,46 | 1,33 | 2,11 | 3,80 | 11,6 % | 65,0 % |
| V3 (Trajektorie) | 0,00 | — | — | — | 0 % | 100 % |

Worst case (Onset = H): H=55 → V0 2,73 / V1 0,82 · H=180 → V0 5,23 / V1 1,42. Kein Tages-Überlauf in irgendeiner Kombination (0 übersprungene Onset-Punkte) — Risiko 1 ist real, aber auf dieser Tour nicht getroffen.

### Ableitungen

1. **V1 holt den Löwenanteil:** Median-Verbesserung **Faktor 5,4×** bei H=55 (−81 %), Faktor 4,4× bei H=180 (−77 %). Bei H=55 fällt der Anteil grober Fehler (> 2 km) von **49,7 % auf 0,0 %**.
2. **V2 lohnt den doppelten Verbrauch nicht:** Zugewinn gegenüber V1 nur **70 m** im Median bei H=55 (p90: 110 m). Der große Sprung liegt bei V0→V1, nicht bei V1→V2.
   ⚠️ **Und die Messung ist zu V2 wohlwollend:** Sie setzt den Fehler auf das *Minimum* beider Abrufe — als wüsste man hinterher, welcher der richtige war. Genau das weiß man nicht; die Auswahl wäre derselbe Zirkelschluss. Real ist V2 also **schlechter** als hier ausgewiesen.
3. **Restfehler V1 bei H=55 unbedenklich:** Median 370 m, p90 920 m — deutlich unter der Zellgröße der Radarquellen (1–2 km) und weit unter der Ausdehnung einer Gewitterzelle.
4. **Restfehler V1 bei H=180 real spürbar:** p90 2,45 km, 17,6 % über 2 km (worst case 39,6 %). Das erreicht die Zellgröße. **Der 180-Minuten-Pfad bleibt auch nach der Korrektur ungenauer** — das ist offen zu benennen.

### Entscheidung: V1 für **beide** Pfade

Die Messung legt für den 180-Minuten-Pfad V2 nahe. Dagegen und für **V1 überall**:

- **V2 ist nicht sauber entscheidbar.** Zwei Abrufe liefern zwei Onsets; welcher gilt, ist genau die Frage, die man ohne Onset nicht beantworten kann. Die Messung umgeht das per `min()` — im Betrieb gibt es dieses Wissen nicht.
- **Ein Mechanismus, ein Baustein.** Zwei verschiedene Bauformen für dieselbe Fehlerursache widersprechen der Code-Teilungs-Konvention.
- **V1 holt auch bei H=180 noch 77 %** des Fehlers — von „völlig falsch verortet" (75,4 % über 2 km) auf „meist brauchbar" (17,6 %).
- **Der eigentliche Schaden des 180-Minuten-Pfads ist ein anderer:** Sein Text nennt **gar keinen Ort** (`starkregen_hint.py:18-27`), weshalb der Leser die Aussage auf sich bezieht. Dagegen hilft kein zweiter Abruf, sondern eine Ortsangabe im Text. Das ist die wirksamere Folgearbeit — **eigenes Issue**, weil es Mail-Inhalt ändert (Renderer-Gate) und damit einen anderen Zuschnitt hat.

⇒ **Restfehler bei H=180 wird als Known Limitation in die Spec geschrieben**, mit den Zahlen aus dieser Messung, plus Verweis auf das Folge-Issue zur Ortsangabe.
