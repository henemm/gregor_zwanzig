# Context: #2051 S2b — Ausdehnung auf die übrigen Kanäle

Erstellt 2026-08-23 · Workflow `feat-2051-s2b-ausdehnung-kanaele` · Standard-Track

## Request Summary

S2a hat die räumliche Ausdehnung eines Regenereignisses als km-Zonen eingeführt
(`rain_extent.derive_rain_zones()`, `OnsetEvent.rain_zones`) und **eine** Textstelle
bespielt. S2b soll die Angabe auf die übrigen Textstellen und Kanäle bringen, die
Kanal-Kaskade festlegen, das SMS-Zeichenbudget klären und die Darstellung für
unvermessene Etappen liefern.

## Ausgangslage: der Baustein existiert bereits

`_onset_extent_suffix()` (`src/output/renderers/alert/render.py:614-639`) ist der
S2a-Baustein nach dem Muster von `_onset_end_suffix` (S1) und `_onset_reach_suffix`
(S3): „anhängbares Stück oder LEER". Er hängt heute an **genau einer** Aufrufstelle,
während die S1/S3-Bausteine an vier hängen.

| Aufrufstelle | Datei:Zeile | S1/S3 | S2a extent |
|---|---|---|---|
| Betreff, Einzel-Event | `render.py:479-486` | ja | **nein** |
| Betreff, Bündel >1 Event | `render.py:477-478` | nein (trägt gar keine Suffixe) | nein |
| E-Mail Trip, Einzelort | `render.py:739-742` | ja | **ja — die einzige** |
| E-Mail Mehr-Orte/Bündel | `render.py:658-660` | ja | nein |
| Telegram rich | `render.py:810-813` | ja | **nein** |
| SMS / Premium-SMS | `render.py:869-924`, zusammengesetzt `:945-964` | ja | **nein** (kein Token) |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py` | Alle Langform-Suffixe, Betreff, Telegram rich, Kurzform-Bau (`_render_sms_onset`, `_sms_onset_ende`, `_sms_onset_sharpness_marker`) |
| `src/output/renderers/alert/model.py:172-178` | `OnsetEvent.rain_zones`, `km_measured` |
| `src/services/rain_extent.py` | `RainZone(km_from, km_to, onset_minutes, event_end_minutes)`, `derive_rain_zones()` |
| `src/services/notification_service.py:267, :1395-1427` | `RadarAlertRequest.rain_zones`, Trip-Produktivpfad (führt alles) |
| `src/services/validator_render_service.py:117-172` | Alert-Preview-Nachweisfläche — führt S1+S3, **nicht** `rain_zones`/`km_measured` |
| `src/output/renderers/alert/project.py:621-663` | Ortsvergleich-Bündel — setzt `rain_zones` bewusst nicht (S2a AC-15) |
| `src/services/trip_segments.py:119-157, :683-716` | `stage_measured_distances()`, `points_along_remaining_route()` |
| `src/services/starkregen_hint.py:19-89` | Briefing-Kurzfristhinweis |
| `src/services/trip_report_scheduler.py:1876-1913` | Quelle des Kurzfristhinweises — **Ein-Punkt-Abfrage** |
| `src/services/radar_service.py:626-678` | `/jetzt`-Kommandotext |

## Existing Patterns

- **Suffix-Baustein-Muster:** jede Zusatzangabe ist eine Funktion `_onset_*_suffix(e) -> str`,
  die entweder ein anhängbares ` · Text`-Stück oder `""` liefert. Die Schwellen-/
  `None`-Entscheidung fällt vorher in `project.py`, im Renderer steht nur ein `None`-Check.
- **Kurzform ist englisch** (`R`, `TH`, `now`), Trennzeichen `@` (Zeitpunkt), `>`
  (Untergrenze), `?` (Unschärfe).
- **Kanal-Kaskade als Code-Mechanismus existiert NICHT.** Jede Aufrufstelle verkettet
  ihre Suffixe einzeln. „Grundauswahl = Maximum, Kanal wählt ab" ist heute eine
  Konvention in den Specs, kein zentraler Schalter.

## Risks & Considerations

### R1 — Drei der „sechs Textstellen" sind nicht bespielbar wie gedacht

- **E-Mail Mehr-Orte** (`render.py:658`) läuft ausschließlich über den
  Ortsvergleich-Bündelpfad; der Trip-Radar-Pfad baut immer genau ein Event
  (`notification_service.py:1433`). Da der Ortsvergleich kein Streckenkonzept hat
  (S2a AC-15), bliebe die Angabe dort dauerhaft leer — ein Anhängen ist ein No-op,
  das nur die Parität dokumentiert.
- **Briefing-Kurzfristhinweis** speist sich aus einer **Ein-Punkt-Abfrage**
  (Segmentmitte, `trip_report_scheduler.py:1876-1882`) und transportiert ein rohes
  6er-Tupel, kein `OnsetEvent`. Zonen gibt es dort nicht — sie müssten erst durch
  eine eigene Mehrpunkt-Verdrahtung entstehen (das ist S2a-Arbeit im Hinweis-Pfad,
  nicht Textverteilung).
- **`/jetzt`** ist laut Docstring (`trip_command_processor.py:1536`) eine Sofortabfrage
  am Standort, ohne Reststrecken-Konzept; `NowcastResult` trägt kein Zonenfeld.

### R2 — Wegpunktnamen: ERLEDIGT, die Prämisse war falsch (nachgemessen 2026-08-23)

**Die S2a-Spec-Aussage „9 von 13 Etappen zeigen keine Ausdehnung" ist eine
Momentaufnahme des Datenbestands, keine Aussage über die Laufzeit.** Nachgemessen:

- `backfill_stage_distances()` (`src/services/track_resolution.py:264-344`) rüstet die
  Kilometrierung aus dem GPX-Bestand nach. Der Alarmpfad ruft sie **selbst auf**, für
  die Etappe von `today`, **vor** der Segmentauflösung (`trip_alert.py:1385`).
- Zur Alarmzeit ist die aktive Etappe damit vermessen, unabhängig vom persistierten
  Stand. Die Ausdehnung erscheint also auf **jeder** Etappe, wenn sie gebraucht wird.
- ⇒ Eine Ersatzdarstellung für unvermessene Etappen wird nicht gebraucht. Der
  Wegpunktnamen-Punkt aus der S2a-Spec entfällt in S2b **ersatzlos**.

Nebenbefund aus derselben Messung: Der persistierte Nachtrag geht in der
Ausblick-Schleife wieder verloren (verlorener Update, `trip_report_scheduler.py:2385-2396`)
→ **#2109**, plus Gegenbeleg an #2058. Betrifft S2b nicht, weil der Alarmpfad ohnehin
selbst nachrüstet.

Die ursprüngliche Datenlage-Erhebung bleibt hier stehen, weil sie erklärt, warum
„zwischen X und Y" auch bei künftigem Bedarf nicht ohne Weiteres baubar wäre:

- `GPXPoint` (der Zonen-Abfragepunkt, `models.py:363-370`) trägt **kein Namensfeld**
  und keine Rück-Identität zu einem Wegpunkt; `points_along_remaining_route()`
  interpoliert rein geometrisch.
- Die persistierten `Waypoint.name` tragen in den echten Prod-Daten generische Labels
  (`Start`, `Seg 3 Start`, `GIPFEL`, `TAL`, `Ziel`) — auch auf den vermessenen Etappen.
  Die echten Hütten-/Ortsnamen stehen nur als zusammengesetzter String im `Stage.name`
  (z. B. `06: Almgasthof Valentinalm nach Zollnersee Hütte`).
- Die einzige Koordinate→Name-Logik (`_match_gpx_waypoints`,
  `src/core/elevation_analysis.py:114ff`) läuft einmalig beim GPX-Upload; die
  Quell-GPX ist vom persistierten Trip aus nicht mehr referenzierbar (kein
  `gpx_path`-Feld).

Die einzige Abhilfe wäre Datenpflege an den Trip-Etappen — **im Ticket als Nicht-Ziel
gesetzt** („Änderungen an der Trip-Konfiguration des PO"). Da der Punkt nach R2 oben
entfällt, ist das keine offene Frage mehr, sondern nur noch dokumentierter Grund.

## Zuschnitt-Entscheidung S2b (2026-08-23)

**In S2b:**
1. `_onset_extent_suffix` an den E-Mail-Betreff (`render.py:486`) und an Telegram rich
   (`render.py:813`) — der Baustein existiert, es ist derselbe Handgriff wie S1/S3.
2. Ein Zonen-Token in der Kurzform (`_render_sms_onset`) — wirkt zugleich auf SMS,
   Premium-SMS und Telegram-Kurzstil, die denselben Text tragen. Muss durch
   Konstruktion ins 140-Zeichen-Budget passen (R3), GSM-7 ist unkritisch.
3. `validator_render_service.py` um `rain_zones`/`km_measured` erweitern — ohne das
   ist kein AC dieser Scheibe auf Staging messbar (R4).
4. Mehr-Orte-Zweig (`render.py:659`): Suffix anhängen als dokumentierter No-op, damit
   die Parität der Aufrufstellen nicht schweigend auseinanderläuft.

**Nicht in S2b, eigene Scheiben:**
- Briefing-Kurzfristhinweis — braucht erst eine Mehrpunkt-Abfrage im Hinweis-Pfad (R1).
- `/jetzt` — Sofortabfrage ohne Reststreckenbezug (R1).
- Wegpunktnamen — entfällt ersatzlos (R2).

### R3 — SMS-Budget wird durch Konstruktion gehalten, nicht durch Kappung

Im Alarm-SMS-Pfad gibt es **keine** Prioritäts-Kürzung. `body[:140]`
(`render.py:996`) ist eine Reißleine, die laut Bestandstest
`tests/tdd/test_onset_ende_sms_budget.py:107-137` im Normalfall nie greifen darf
(Nachweis: `render(limit=140) == render(limit=4000)` im Extremfall). Ein Zonen-Token
muss also von vornherein ins Budget passen. Der Bindestrich ist GSM-7-Basisalphabet
(`tests/tdd/_gsm7_charset.py:22`) — `km8-12` ist zeichensatzsicher, ein Septet je
Zeichen.

Telegram-Kurzstil und Premium-SMS haben **keinen eigenen Renderer** — sie senden
denselben SMS-Text (`notification_service.py:1599-1615`, `:1680`, `:1694`). Eine
Änderung am Kurzform-Token wirkt damit auf drei Kanäle gleichzeitig.

### R4 — Ohne Ergänzung der Preview-Fläche ist kein Staging-Nachweis möglich

`validator_render_service.py:117-172` baut sein `OnsetEvent` ohne `rain_zones` und
ohne `km_measured`. Das ist genau die Lücke, die die S2a-Lieferung als „nicht
gemessen" gebucht hat. Solange sie offen ist, kann kein AC dieser Scheibe über
`POST /api/trips/{id}/alert-preview` auf Staging gemessen werden.

### R5 — Vier unabhängige `OnsetEvent`-Konstruktionsstellen

`radar_alert_service.py:60` (Legacy, führt nichts), `validator_render_service.py:117`,
`notification_service.py:1395` (Produktivpfad, führt alles), `project.py:621`
(Ortsvergleich). Jede Feldergänzung muss gegen alle vier geprüft werden, sonst
entsteht wieder eine stille Lücke.

## Existing Specs

- `docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md` — Vorgänger, benennt
  S2b-Scope in „Known Limitations" und „Nicht-Ziele"
- `docs/specs/modules/feat_2051_s3_reichweite_und_guete.md` — Bauplan des
  Textstellen-Fächers und der Kurzform-Abwahl
- `docs/specs/modules/fix_2017_nowcast_messpunkt.md` — Ein-Punkt-Zusicherung, von S2a
  für den Alarmpfad abgelöst
- `docs/specs/modules/fix_2036_*` — Regel „km-Zahlen nur bei vermessener Etappe"
