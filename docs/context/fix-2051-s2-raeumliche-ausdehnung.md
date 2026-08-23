# Context: #2051 S2 — Räumliche Ausdehnung des Regenereignisses

**Issue:** #2051 (Scheiben-Ticket, bleibt offen) · **Scheibe:** S2 · **Track:** Full Process
**Branch:** `feat-2051-s2-raeumliche-ausdehnung` · **Basis:** `origin/main` @ `eed94a8f`
**Erstellt:** 2026-08-23

## Request Summary

Ein Regenereignis wird heute als **Punkt** gemeldet („Regen bei km 10 in 90 Minuten"). S2 soll
die **räumliche Ausdehnung** ergänzen — als km-Spanne entlang der Reststrecke („Nass km 8–12"),
damit der Nutzer sie selbst mit seiner Route verschneiden kann. Laut Ticket ist das „der
eigentliche Kern" des Vorgangs.

Grundprinzip aus dem Ticket: **nur Daten über das Wetter, keine Rechnung über den Nutzer.**
Keine Ankunftszeiten, keine Handlungsempfehlung.

## Related Files

### Abruf-Seite (hier entsteht die Ausdehnung neu)
| Datei | Relevanz |
|---|---|
| `src/services/radar_service.py:465` | `get_nowcast(lat, lon, …)` — nimmt **genau einen** Punkt. Kein Bulk-/Grid-Weg bei keinem Provider. |
| `src/services/radar_service.py:692-722` | Provider-Fallbackkette nach Bounding-Box: BrightSky/RADOLAN · GeoSphere INCA (AT) · ARPAE · AROME-FR · ICON-D2 · Open-Meteo `minutely_15` |
| `src/services/radar_service.py:806-884` | `_fetch_openmeteo_15` — gemeinsamer Funnel aller Open-Meteo-Zweige, **einziger Ort mit Budget-Gate** (`:828`) |
| `src/services/radar_service.py:736-769` | `_fetch_geosphere_inca` — **ungegated**, nur der Convective-Sidecar läuft übers Budget |
| `src/services/radar_service.py:927-1139` | `_derive_result()` — leitet alle Felder aus **derselben** Frame-Liste ab |
| `src/services/trip_alert.py:1408-1472` | Trip-Alarm: **ein** `get_nowcast`-Call an der interpolierten Planposition zur Fenstermitte (`now + 27 Min`) |
| `src/services/compare_radar_alert.py:382-392` | Ortsvergleich: Schleife über Preset-Orte → **mehrere** Calls, sequenziell. Muster existiert bereits. |
| `src/services/trip_report_scheduler.py:1880` | Briefing-Kurzfristhinweis, ebenfalls ein Call |

### Streckengeometrie
| Datei | Relevanz |
|---|---|
| `src/services/trip_segments.py:555-627` | `position_at_time()` — liefert lat/lon/`distance_from_start_km` zu einem Zeitpunkt. Baustein für Punktwahl. |
| `src/services/trip_segments.py:516-552` | `_interpolate_point()` — lineare Interpolation zwischen Segmentgrenzen |
| `src/services/trip_segments.py:113-151` | `stage_measured_distances` — **km sind je Etappe neu normiert** („jeder Tag zählt neu seine Kilometer") |
| `src/services/trip_segments.py:154` | `measured_segment_km()` — nur bei `seg.distance_measured` |
| `src/app/trip.py:61-131` | `Waypoint` (`distance_from_start_km`, seit #2036) und `Stage` (typ. 3–7 Waypoints) |
| `src/app/models.py:364-441` | `GPXPoint`/`GPXTrack` (dichter Track, 400–650 Punkte, separat unter `data/users/<u>/gpx/`), `TripSegment` |
| `src/utils/geo.py` | `haversine_km` (Luftlinie) |

### Render-Seite (kann km-Spannen bereits)
| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/segments.py:91-128` | `format_alert_location()` — 4 Stufen: Label > **gemessene km-Spanne** > Segmentkennung > Luftlinien-Rückfall. `:108` nennt die geschätzte Zahl selbst „glaubwürdig aussehender Unsinn". |
| `src/output/renderers/alert/model.py:314` | `km_span(events)` — reine Min/Max-Hülle über eine gegebene Eventliste, **keine** Nachbarschaftslogik |
| `src/output/renderers/alert/render.py:188-207` | `_location_of()` — speist Betreff, Mailkörper und Telegram-Langform gemeinsam |
| `src/services/notification_service.py:1436-1490` | `_dispatch_alert_message()` — **die geteilte Naht** Trip ↔ Ortsvergleich (ADR-0021) |

### Die sieben Textstellen
1. Betreff — `render.py:967` → `_render_subject_onset()` `:474`
2. E-Mail Trip **und** Mehr-Orte — `render.py:1146` (eine Funktion für beide)
3. Telegram rich — `render.py:1288` → `_render_telegram_onset()` `:771`
4. Telegram Kurzstil — **keine eigene Stelle**: schickt den fertigen `sms_body` (`notification_service.py:1596-1601`). KHW fährt diesen Stil.
5. SMS / Premium-SMS — `render.py:1450` → `_render_sms_onset()` `:895-964`
6. Briefing-Kurzfristhinweis — `src/output/renderers/email/starkregen_hint.py:19-89`, eigenständig, **trägt heute keine km-Angabe**
7. Kommando-Antwort `/jetzt` — `radar_service.py:563` `format_now_text()`, eigenständig

## Existing Patterns

- **Additive Feldergänzung am `NowcastResult`** — so liefen S1 (`event_end_minutes`,
  `event_ongoing_beyond_horizon`) und S3 (`source_reach_minutes`,
  `LOCATION_SHARPNESS_LIMIT_MIN`). S2 folgt demselben Muster mit **eigenem Feldnamen**.
- **Kanal-Kaskade** (S3, E6): Langform bekommt alles, Kurzform wählt ab. Grundauswahl ist das
  Maximum, der Kanal darf nur streichen.
- **Mehrere Punkte in einer Schleife** — `compare_radar_alert.py:382` macht das heute schon
  pro Preset-Ort. Kein Bulk-Request, sequenziell, jeder Punkt zahlt eigenes Cache-Lookup.
- **Budget-Gate** — `ForecastBudgetGate` (`forecast_budget.py:36-74`): `DAILY_BUDGET=9000`,
  `polling` ab 80 % geblockt, `alert_check` ab 95 %, `user_briefing` nie. Fail-open.
  Zähler `<data_root>/diagnostics/forecast_budget.json`, UTC-Tagesgrenze.

## Messgrundlage (Produktion, KHW 403, Trip `5f534011`, 13 Etappen)

| Größe | Wert |
|---|---|
| Etappenlänge Luftlinie | Min 4,99 · Median 9,21 · Max 12,74 km |
| Etappenlänge gemessen (4 Etappen) | 6,11 – 14,03 km |
| **Vermessungsgrad** | **4 von 13 Etappen (31 %)** haben `distance_from_start_km` an allen Waypoints |
| Gehzeit je Etappe | Min 1,7 h · Median 5,23 h · Max 7,0 h |
| Radar-Horizont | 180 Min (`_NOWCAST_HORIZON_MIN`, seit #1945) |

**Folgerung:** Der 3-h-Horizont deckt typischerweise **weniger als eine Etappe** ab. „Reststrecke"
kann deshalb sinnvoll als *Rest der aktiven Etappe* geschnitten werden — was auch nötig ist, weil
es keine über Etappen hinweg kumulierte km-Zählung gibt.

### Abruf-Volumen (Produktion, `diagnostics/enrichment_calls.jsonl`, `path=radar_nowcast`)

| Tag | echte Radar-Fetches |
|---|---|
| 2026-08-20 | 68 |
| 2026-08-21 | 161 |
| 2026-08-22 | 127 |
| 2026-08-23 (bis 05:52 UTC) | 29 |

- Trip-Alarm-Poll: `7,22,37,52 * * * *` = **96 Läufe/Tag** (`internal/scheduler/scheduler.go:199-202`)
- Ortsvergleich-Poll: ebenfalls 96/Tag, zeitgleich
- Briefing-Hinweis: ≤ 1×/Tag pro Trip (innerhalb `briefing_dispatch`)
- **Cache-Trefferquote 1,5 %** — strukturell, weil die Abfrageposition mit der geplanten Gehzeit
  mitwandert (`trip_alert.py:1421-1425`) und das Poll-Intervall (900 s) die Cache-TTL (300 s)
  ohnehin überschreitet.
- **Multiplikator:** ≈ 95 × (N−1) zusätzliche echte Calls pro Tag und Trip.
  N=3 → ≈ 190/Tag · N=5 → ≈ 380/Tag. Gegen 9000 Budget: unkritisch.

## Rasterauflösung der Quellen

| Quelle | Zellgröße | Fundstelle |
|---|---|---|
| GeoSphere INCA (AT — **KHW**) | 1 km | `providers/geosphere.py:71` (`nowcast-v1-15min-1km`) |
| AROME-FR | 1,3 km | `providers/openmeteo.py:127` |
| ICON-D2 | 2 km | `providers/openmeteo.py:132-135` |
| ARPAE ICON-2I | 2 km | `radar_service.py:250` |

Ein Punktabstand von 2 km liefert bei INCA (1 km) unterscheidbare Werte; bei ICON-D2/ARPAE
(2 km Zellen) liegt er genau an der Zellgröße und ist grenzwertig. 5 km wäre bei allen Quellen
klar über der Zellgröße — aber bei 5–13 km Etappenlänge blieben davon nur 1–3 Punkte.

## Dependencies

- **Upstream:** `position_at_time()`, `haversine_km()`, `RadarNowcastCacheService` (TTL 300 s,
  Schlüssel = Koordinate auf 4 Nachkommastellen ≈ 11 m), `ForecastBudgetGate`
- **Downstream:** `NowcastResult` → `OnsetEvent` → `_dispatch_alert_message()` → alle vier Kanäle;
  zusätzlich die zwei eigenständigen Formulierer (`starkregen_hint.py`, `format_now_text()`)

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/fix_2017_nowcast_messpunkt.md` | **AC-12 Budget-Invariante** („genau ein Abruf"), Variante-3-Ablehnung, Known Limitation 5 (`km_from`/`km_to` = Segment-Lage) und 7 (Cache-Sharing) |
| `docs/specs/modules/feat_2051_s1_dauer_und_ende.md` | S1, live: `event_end_minutes`, `event_ongoing_beyond_horizon` |
| `docs/specs/modules/feat_2051_s3_reichweite_und_guete.md` | S3, live: `source_reach_minutes`, `LOCATION_SHARPNESS_LIMIT_MIN=60`, Kanal-Kaskade E6 |
| `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` | SMS-Zielbild, Token-Grammatik, `km5-18:`-Form |
| `docs/specs/modules/fix_1945_nowcast_horizon.md` | Horizont 60 → 180 Min |
| ADR-0021 | Trip und Ortsvergleich teilen Rendering/Versand |

## Risks & Considerations

### R1 — AC-12 aus #2017 wird zwangsläufig gebrochen (muss bewusst abgelöst werden)
Die #2017-Spec (`created: 2026-08-20`) schreibt „genau **ein** `get_nowcast()`-Aufruf je Trip"
als Test-Invariante fest und verwarf die Mehrfach-Abfrage als „unverhältnismäßig". Das Ticket
#2051 ist vom **2026-08-21** — einen Tag jünger — und beauftragt genau diese Mehrfach-Abfrage
ausdrücklich, samt Hinweis auf die nötige Budget-Entscheidung. Der Auftrag sticht die Ablehnung,
aber die Ablösung muss **dokumentiert** erfolgen (Projektregel: keine stille Rücknahme).

**Betroffene Wächter:**
| Test | Assert |
|---|---|
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:532` `test_ac3_nowcast_called_at_segment_coordinates` | `call_count == 1` (`:611`) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:1282` `test_2017_ac12_genau_ein_get_nowcast_aufruf_je_lauf` | `== 1` (`:1304`, `:1308`) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py:1329` `test_2017_fadv1_…` | `call_count == 1` (`:1417`) |
| `tests/tdd/test_trip_report_scheduler_starkregen_hint.py:331` `test_ac12_starkregen_hinweis_ruft_get_nowcast_genau_einmal` | `len(calls) == 1` (`:360`) |
| `tests/unit/test_radar_nowcast_cache_sharing.py` (11 Funktionen, Z.82-537) | feste Aufrufzahlen 1 bzw. 2 |

`tests/tdd/test_starkregen_kurzfristhinweis.py` prüft nur `>= 1` und kollidiert **nicht**.
Der Ortsvergleich hat **keinen** „genau 1"-Wächter — dort sind mehrere Calls bereits normal.

### R2 — 9 von 13 Etappen sind unvermessen
`format_alert_location()` gibt eine km-Spanne nur bei `km_measured=True` aus und verwirft die
Schätzung sonst bewusst. Auf 69 % der KHW-Etappen läge damit **keine belastbare km-Spanne** vor.
Die Spec braucht eine definierte Antwort für diesen Fall. Denkbare Richtung (in der Analyse zu
prüfen): Ausdehnung über **Wegpunktnamen** statt Kilometer ausdrücken — Waypoints existieren auf
allen Etappen, und `format_alert_location()` kennt die Segmentkennungs-Stufe bereits.
Keine Bewertung der Trip-Konfiguration des PO; das ist reine Messgrundlage.

### R3 — Es gibt keinen „betroffene Punkte → Spanne"-Baustein
Weder in `corridor_threshold.py` noch sonst im Code existiert eine Verschmelzungs-/Cluster-Logik.
`km_span(events)` ist eine reine Min/Max-Hülle über eine vorgegebene Liste. Die Punkt-zu-Spanne-
Logik entsteht neu — inklusive der Frage, wie **mehrere getrennte Zonen** (nass bei km 2–4 *und*
km 9–11) behandelt werden: zwei Spannen, oder eine Hülle km 2–11? Eine Hülle würde trockene
Strecke als nass ausweisen.

### R4 — SMS schneidet hart bei 140 Zeichen ab
`render_sms(limit=140)` → `_render_sms_onset()` endet mit `body[:limit]` (`render.py:964`) —
reine Abschneidung, kein Soft-Wrap. Eine breitere Ortsangabe (`km 8-12` statt `km 10`) kann
hinten Information verdrängen. Die Kanal-Kaskade muss das entscheiden, und ein AC muss den
Grenzfall messen.

### R5 — GeoSphere INCA hat kein dokumentiertes Kontingent
Der für Österreich (und damit den KHW) maßgebliche Pfad läuft **ungegated**. Bei N=5 wären es
≈ 480 Abrufe/Tag/Trip gegen eine Behörden-API ohne bekanntes Limit. Kein Budget-Problem im Sinne
des Open-Meteo-Deckels, aber ein eigenes Betriebsrisiko — die Spec sollte den Radar-Pfad
ebenfalls unter ein Gate stellen oder die Punktzahl konservativ wählen.

### R6 — `km_from`/`km_to` sind bereits belegt
Sie tragen die **Segment-Lage der Etappe** (`notification_service.py:189-190`, gesetzt in
`trip_alert.py`, gelesen in `segments.py:91-111`). #2017 Known Limitation 5 hält ausdrücklich
fest, dass sie **nicht** verändert werden. Die Ereignis-Ausdehnung braucht ein **eigenes
Feldpaar** — sonst laufen zwei Bedeutungen auf denselben Namen.

### R7 — Der Cache trägt nicht
1,5 % Trefferquote, strukturell bedingt. Zusätzliche Punkte kosten real. Zugleich brechen
zusätzliche Koordinaten pro Lauf die Erwartungen in `test_radar_nowcast_cache_sharing.py`,
soweit diese auf festen Aufrufzahlen statt auf Schlüsselgleichheit beharren.

### R8 — #2036 liefert keinen Baustein für S2 (geklärt)
Beide Aussagen stimmten, sie betrafen Verschiedenes. #2036 (Spec
`docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md`, GREEN-Commit `b6ca31e3`, PR #2055)
ersetzt die auf einem Garmin inReach unverortbare Segmentnummer (`Seg 3`) durch eine **gemessene**
Kilometerangabe — und regelt allein die **Quellenqualität eines einzelnen km-Werts** je Wegpunkt
(`Waypoint.distance_from_start_km`, `TripSegment.distance_measured`, `km_measured` an den vier
Event-Typen). `km_from`/`km_to` waren auch vorher schon die Distanzen der beiden Segment-Grenzen;
#2036 ändert nur, **wie** sie ermittelt werden und **ob** sie gezeigt werden dürfen.

**Für S2 folgt daraus kein Baustein.** Es gibt keine Funktion, die aus „betroffen / nicht
betroffen je Punkt" eine zusammenhängende Zone ableitet. Die nächstliegende Funktion
`stage_measured_distances()` (`trip_segments.py:113-151`) normiert und validiert
Track-Koordinaten einer Etappe (strikt monoton, nie kürzer als Luftlinie, Etappenstart = 0 km),
kennt aber keine Wetterwerte und keine Schwellen. R3 bleibt damit unverändert bestehen.

**Nebenbefund (nicht Teil dieses Zuschnitts):** `evaluate_corridor_thresholds()`
(`src/services/corridor_threshold.py:68`) hat seit #1460 **keinen Aufrufer in `src/`** — belegt
per `grep -rn "evaluate_corridor_thresholds(" --include="*.py" src/ tests/`: nur die Definition
selbst plus zwei Testdateien. #2036 hat an diesem unerreichbaren Renderpfad dennoch
Konsistenzpflege betrieben (Commit `7a0f8ca9`). → Sammel-Issue #1199.

## Analysis (Phase 2, 2026-08-23)

### Type
**Feature** (Scheibe eines Scheiben-Tickets, additiv zu S1/S3)

### Technischer Ansatz

**Abfragepunkte:** Fester **Abstand von 2 km** statt fester Punktzahl — bei 5–13 km Etappenlänge
skaliert ein Abstand automatisch, eine feste Zahl tastet kurze Etappen zu dicht und lange zu grob
ab. Gedeckelt bei **6 Punkten je Lauf**; das deckt 12 km Reststrecke ab (Etappen-Median 9,2 km).
Untergrenze 1 Punkt bei Reststrecke < 2 km — dort bleibt das heutige Verhalten exakt erhalten.
2 km liegt über der INCA-Zellgröße (1 km), liefert dort also unterscheidbare Werte.

**Andockstelle:** Die Schleife entsteht am Aufrufort in `trip_alert.py:1408-1472`, nach dem
Muster von `compare_radar_alert.py:382-392`. `get_nowcast()` bleibt Ein-Punkt-API — **keine
Signaturänderung** an `radar_service.py`. Das Budget-Gate greift automatisch je Aufruf.

**Wichtige Erkenntnis zur Geometrie:** Die Abfragepunkte brauchen **kein**
`distance_from_start_km`. `position_at_time()` interpoliert lat/lon über die GPX-Geometrie
unabhängig vom Vermessungsgrad. Die **Messung** funktioniert damit auf allen 13 Etappen — nur
die **Beschriftung** unterscheidet sich. Für die Platzierung der Punkte genügt eine
Luftlinien-Distanz zwischen Wegpunkten (`haversine_km`); das ist zulässig, weil sie nie als Zahl
ausgegeben wird. Nur die *ausgegebene* km-Zahl braucht echte Messung — genau die Trennung, die
#2036 eingeführt hat.

**Punkt → Zone:** Neue, eigenständige Logik (kein Baustein vorhanden, R3/R8). Benachbarte nasse
Punkte verschmelzen; **ein trockener Punkt trennt**, er überbrückt nicht. Begründung: Der
Punktabstand liegt bereits an der Auflösungsgrenze der Quelle, ein trockener Messpunkt ist echtes
Signal. Überbrücken würde trockene Strecke als nass ausweisen — das wäre eine erfundene Aussage.

**Mehrere Zonen:** **Getrennt ausweisen, nie als Hülle.** Eine Hülle km 2–11 bei nass km 2–4 und
km 9–11 würde die trockene Mitte falsch darstellen. Die Kanal-Kaskade kürzt: Langform zeigt alle
Zonen, Kurzform maximal eine (die nächstgelegene).

**Zeitangabe:** **Pro Zone**, nicht global — früheste `onset_minutes` und späteste
`event_end_minutes` unter den Punkten der jeweiligen Zone. Eine globale Spanne über getrennte
Zonen ordnete Zeiten der falschen Zone zu. Reine Min/Max-Aggregation über Wetterdaten, keine
Rechnung über den Nutzer.

**Teilausfall:** Punkte ohne Daten werden aus der Zonenbildung ausgeschlossen — weder nass noch
trocken, echte Lücke. Bei Totalausfall kein S2-Text, wie heute.

### Gemessenes Zeichenbudget (echte Renderfunktionen, nicht geschätzt)

| Fall | String | Länge | Rest bis 140 |
|---|---|---|---|
| Regen, nur Beginn | `Ziel: R2.5@18:00` | 16 | 124 |
| Regen, Beginn+Ende | `Ziel: R2.5@18:00@20:00` | 22 | 118 |
| km-Spanne statt Punkt | `km 8-12: R3.1@18:00` | 19 | 121 |
| Worst-Case Einzelereignis | `km 8-12: TH@Sa0:23 >@Sa4:47? R12.5` | 34 | 106 |

**Spanne statt Punkt kostet 1 Zeichen** (`km 8-12` = 7 gegen `🏁 Ziel` = 6). Platz ist reichlich.
**Premium-SMS fährt dasselbe Limit** — `notification_service.py:1666` (SMS) und `:1680` (Premium)
senden denselben gerenderten String, ohne zweite Kürzung.

**Randbedingung aus #2078 (Parallelsession, Merge heute):** Der Ortsname im Onset-Pfad wird
künftig auf **24 Zeichen** gekappt (`render.py:958/960/962`, `_render_sms_onset` und
`_render_sms_onset_shift_only`). `format_alert_location()` bleibt unangetastet. S2 läuft über
diese Kopf-Zweige, ist also automatisch geschützt — **aber** eine Wegpunktnamen-Darstellung
(„zwischen Obstanser-See-Hütte und Porzehütte", ~44 Zeichen) würde dort mitten im Wort
abgeschnitten. Das entscheidet die Kanal-Kaskade für R2: Namen nur in der Langform.

### Abzulösende Zusicherung (R1, präzisiert)

Die vier `== 1`-Tests werden auf eine **belegbare Obergrenze** umgeschrieben
(`<= MAX_NOWCAST_CALLS_PER_TRIP_RUN`, per Modulreferenz gelesen, nicht als Literal dupliziert).
Drei Ergänzungen, ohne die der Umbau die Zusicherung verwässern würde:

1. **Zwei Zähl-Nähte, nicht eine.** `test_2017_ac12_…` und `test_ac12_starkregen_hinweis_…`
   zählen sowohl am `get_nowcast`-Seam (`dienst.calls`) als auch am `frame_source`-Seam
   (`frames.call_count`). Beide müssen wachsen.
2. **Koordinaten-Menge mitprüfen.** Jeder umgebaute Test braucht einen neuen Assert, dass alle
   abgefragten Punkte auf der erwarteten Reststrecke liegen und keine Duplikate enthalten —
   sonst geht beim Lockern der Zahl die heutige Ortsschärfe-Zusicherung („ein Abruf, und zwar am
   richtigen Ort") still verloren.
3. **Positivkontrolle:** Bei Reststrecke < 2 km bleibt `== 1`. Ohne diesen Randfall misst der
   Obergrenzen-Assert nicht, ob überhaupt gedeckelt wird.

`test_2017_fadv1_…` (`:1329`) zählt nicht pro Trip getrennt — muss beim Umbau aufgetrennt werden,
damit „kaputter Trip verbraucht 0 Kontingent" bei N > 1 erhalten bleibt.
Von den 11 Cache-Sharing-Tests ist einer zu prüfen:
`test_end_to_end_trip_and_compare_radar_paths_share_one_fetch` (`:329`) bricht, wenn keine der N
neuen Trip-Koordinaten mehr exakt auf der Compare-Koordinate liegt.

### Scope Assessment

| | |
|---|---|
| Produktiv | ~300–350 LoC |
| Tests | ~200 LoC |
| Risiko | **MEDIUM–HIGH** (Alarmkette im laufenden Betrieb, neue Abrufstrategie) |

**Über dem 250-LoC-Limit.** Empfohlener Unter-Zuschnitt:
- **S2a** — Mehrpunktabfrage (`trip_segments.py`, `trip_alert.py`), Punkt-zu-Zone-Verschmelzung
  (neues Modul), Ablösung der AC-12-Wächter, neue `NowcastResult`/`OnsetEvent`-Felder, **eine**
  Textstelle als End-to-End-Beweis. ~180–220 produktiv + ~150 Test.
- **S2b** — restliche sechs Textstellen, Kanal-Kaskade, km/Wegpunktname-Darstellung für
  unvermessene Etappen, Paritätstest. ~120–150 produktiv + ~100 Test.

### Dependencies
Unverändert (siehe oben). **Zeitliche Abhängigkeit:** #2078 merged heute und etabliert die
24-Zeichen-Konvention im Kopf — S2 setzt darauf auf, fasst die Kurzfassung vorher nicht an.

## Offene Entscheidungen (kommen mit den ACs zur PO-Freigabe)

1. **Abrufbudget:** Wie viele Punkte entlang der Reststrecke (N), in welchem Abstand, mit
   welcher Priorität? Empfehlungsgrundlage: Budget unkritisch, Rasterauflösung INCA 1 km,
   Etappen 5–13 km.
2. **Unvermessene Etappen:** km-Spanne unterdrücken, oder Ausdehnung über Wegpunktnamen
   ausdrücken?
3. **Mehrere getrennte Zonen:** getrennt ausweisen oder als Hülle zusammenfassen?
4. **Kanal-Kaskade:** Trägt die SMS-Kurzform die Spanne, angesichts des harten 140-Zeichen-
   Schnitts? (Auf der Hütte ist Premium-SMS die einzige ankommende Fassung.)
