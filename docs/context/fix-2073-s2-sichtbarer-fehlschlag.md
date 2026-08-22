# Context: #2073 Scheibe 2 — der stille Fehlschlag der Track-Auflösung

> Scheibe 1 (`1e0ee151`, live 2026-08-22) hat die **Regel** repariert: mehrere passende GPX-Dateien
> führen nicht mehr automatisch zum Abbruch, entscheidend ist Ergebnisgleichheit. Scheibe 2 ist der
> zweite, ausdrücklich eigenständige Teil desselben Tickets: **wenn die Auflösung scheitert, erfährt
> es niemand.**

## Request Summary

Die Auflösung der gemessenen Wegstrecke einer Etappe scheitert geräuschlos: sie liefert `None`, die
Ortsangabe fällt auf „Segment N" zurück, und weder Nutzer noch Betreiber bekommen davon etwas mit.
Bei #2070 war eine eigens beauftragte Messung nötig, um festzustellen, dass 3 von 13 Etappen
betroffen waren. Scheibe 2 soll den Fehlschlag **mit Grund** sichtbar machen.

## Der Wirkpfad (gemessen, nicht vermutet)

```
GPX-Bestand data/users/<uid>/gpx/
        │
        ▼  resolve_stage_track_km()          ← STILLE STELLE 1 (4 Abbruchgründe)
   distance_from_start_km je Wegpunkt
        │
        ▼  backfill_stage_distances()  → save_trip (Read-Modify-Write)
        │
        ├─► stage_measured_distances()       ← STILLE STELLE 2 (3 Verwerfungsgründe)
        │        │
        │        ▼ TripSegment.distance_measured = False
        │        ▼ format_alert_location() → "Segment N"      (#2036)
        │
        └─► Go: segmentDistanceKm()          ← STILLE STELLE 3
                 ▼ Rückfall auf Luftlinie → zu optimistische Ankunftszeit  (#2042)
```

**Das ist der zentrale Befund dieser Kontextphase: es gibt drei stille Stellen, nicht eine.** Das
Ticket benennt nur die erste. Eine Sichtbarkeit, die allein an `resolve_stage_track_km()` hängt,
wäre ein blinder Wächter für die beiden anderen — der Nutzer sieht in allen drei Fällen dasselbe
(„Segment N", Luftlinien-Gehzeit), die Ursachen sind aber verschieden.

### Stille Stelle 1 — `src/services/track_resolution.py`

| Zeile | Abbruchgrund | Begründungswert vorhanden? |
|---|---|---|
| 128–129 | keine Wegpunkte / GPX-Verzeichnis fehlt | ja (trivial) |
| 65 (`_match_track`) | ein Wegpunkt liegt > 10 m vom nächsten Trackpunkt | **ja — `best_dist` ist berechnet und wird verworfen** |
| 144–145 | kein einziger Kandidat passt | ja (`len(matches) == 0`) |
| 146–147 | Kandidaten liefern abweichende Ergebnisse | **ja — `_ergebnisse_sind_gleich()` kennt die Abweichung und verwirft sie** |
| 137–141 | GPX-Datei nicht lesbar | wird bereits als `logger.warning` protokolliert |

Der Grund ist an jeder Stelle **bereits bekannt** und wird weggeworfen. Sichtbarkeit heißt hier
nicht „neu messen", sondern „nicht mehr verwerfen".

Zusätzlich: `_failed_lookups` (Zeile 156, Schlüssel `(user_id, trip_id, stage_id)`, wird nie
geleert) merkt sich nur **dass** etwas fehlschlug, nicht **warum**.

### Stille Stelle 2 — `src/services/trip_segments.py:113-151`

`stage_measured_distances()` verwirft **bereits aufgelöste** Werte still, wenn (1) ein Wegpunkt
keinen Wert trägt, (2) die Werte nicht streng monoton steigen, (3) eine Teilstrecke kürzer ist als
die Luftlinie. Ergebnis identisch: `distance_measured=False` → „Segment N".

### Stille Stelle 3 — `internal/model/naismith.go:122-129`

Ohne gemessene Strecke rechnet die Gehzeit mit Luftlinie. Das ist genau der Fehler, den #2042
beheben sollte — und er kehrt still zurück, sobald die Auflösung scheitert. Folge ist eine **zu
kurze** Gehzeit, also eine zu optimistische Ankunftszeit.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/track_resolution.py` | Stille Stelle 1; alle vier Abbruchgründe, `_failed_lookups` |
| `src/services/trip_segments.py:113-151` | Stille Stelle 2 (Plausibilitätsprüfung verwirft Messwerte) |
| `internal/model/naismith.go:122-129` | Stille Stelle 3 (Gehzeit fällt auf Luftlinie) |
| `src/output/renderers/alert/segments.py:92-128` | wo „Segment N" tatsächlich entsteht (`format_alert_location`) |
| `src/services/trip_alert.py:1176` | Aufrufer Alarmlauf (`persist=True`) |
| `src/services/trip_report_scheduler.py:1995, 2016-2017` | Aufrufer Briefing (`persist=True`) / Vorschau (`persist=False`) |
| `src/providers/enrichment_health.py:53` | **Schreibseite des bestehenden Health-Journals** — der wahrscheinliche Andockpunkt |
| `internal/scheduler/enrichment_health.go:83, 129` | Leseseite; gruppiert **generisch nach `path`** |
| `src/app/loader.py:1757` | `_deep_merge_preserve_unknown` — Rückschreibweg |
| `frontend/src/lib/types.ts:32-48` | Wegpunkt-Typ im Frontend (kennt `distance_from_start_km` nicht) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Etappen-Editor, möglicher Ort einer Nutzer-Anzeige |
| `tests/tdd/test_track_resolution_legacy_trip.py` | 1177 Zeilen, AC-1..AC-12 — prüft **ob** `None`, nie **warum** |

## Existing Patterns — es gibt bereits ein fertiges Muster für genau dieses Problem

**ADR-0018 („Modell-Fallback mit Ausweichen, aber ohne Kaschieren")** formuliert eine ausdrückliche
Folgepflicht:

> „Neue degradierbare Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen (Marker in
> Daten + wachsendes Health-Signal)."

Die Track-Auflösung ist ein solcher Pfad — sie degradiert auf Segmentsprache bzw. Luftlinie. Das
etablierte Muster ist ein Dreiklang:

1. **Journal** — JSONL-Zeile je Ereignis, fail-soft, Diagnose darf den Fachablauf nie stören
   (`src/providers/enrichment_health.py:75-88`: jeder Fehler wird geschluckt).
2. **Aggregat** — Go liest das Journal und bildet Rohzeitstempel je Pfad, **ohne** Schwellenentscheid
   (`internal/scheduler/enrichment_health.go:129-170`).
3. **Endpunkt** — eigener Top-Level-Schlüssel unter `/api/scheduler/status`; die Eskalation formt
   der externe Monitor `check-gregor20.sh` aus `jetzt − last_success_at`.

**Entscheidender Hebel für den Umfang:** Der Go-Aggregator gruppiert **generisch nach dem freien
String `path`** (`enrichment_health.go:83-87`, ausdrücklich so abgesichert in #1992 AC-8). Ein neuer
Pfadwert in `src/providers/enrichment_health.py` erscheint damit **ohne jede Go- oder
Frontend-Änderung** im Status-Endpunkt.

Weitere Vorbilder:

- **Slot-Vermerk mit `outcome`** (`briefing_slots.json`) — Fehlschlag am Objekt selbst vermerkt.
- **`pending_briefings.json`** — Fehlschlag erzeugt einen Nachliefer-Vermerk mit `error_details`,
  den der Infra-Monitor bei Alter > 3 h eskaliert.
- **#1346 (`docs/context/bugfix_1346_silent_briefing_outage.md`)** — der Präzedenzfall „im Status
  sichtbar, aber nirgends laut": dort war die Lehre, dass Sichtbarkeit ohne aktive Meldung nicht
  reicht.
- **`data/users/<uid>/diagnostics/`** existiert im Produktivbestand bereits
  (`corrupt_trips.json`, `alert_anchor_rejected.jsonl`) — nutzerbezogene Diagnose hat also schon
  einen Ablageort.

## Dependencies

- **Upstream:** `core.gpx_parser.parse_gpx`, `utils.geo.haversine_km`, `app.loader.get_data_dir` /
  `get_data_root` / `save_trip`.
- **Downstream:** Alarm-Ortsangabe (#2036), Gehzeiten/Ankunftszeiten (#2042), amtlicher Warnblock
  (`notification_service._measured_event_km`), Wetter-Schnappschuss
  (`weather_snapshot.py:467, 556`).

## Existing Specs & ADRs

| Dokument | Was daraus gilt |
|---|---|
| `docs/specs/modules/fix_2073_track_ergebnisgleichheit.md` | Scheibe 1; enthält **keine** Fehlschlag-Sichtbarkeit — das ist genau diese Scheibe |
| `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` | AC-11 Eindeutigkeit, AC-12 Vollständigkeit, 10-m-Toleranz |
| `docs/specs/modules/fix_2042_gehzeit_wegstrecke.md` | zweiter Verbraucher der gemessenen Strecke |
| `docs/context/fix-2073-ergebnisgleichheit.md` | Messung am Produktivbestand; Fail-soft-Muster; `_failed_lookups` |
| **ADR-0018** | **Nicht-Kaschieren-Invariante — die normative Grundlage dieser Scheibe** |
| ADR-0003 | Mandantentrennung: nutzerbezogene Diagnose nie global, nie `"default"` |
| ADR-0031 | dateibasierte Persistenz unter `data/users/<user_id>/` |

## Risks & Considerations

1. **Blinder Wächter durch Teilabdeckung.** Deckt die Sichtbarkeit nur Stelle 1 ab, bleiben Stelle 2
   und 3 still — und der Nutzer sieht denselben Effekt ohne Erklärung. Muss in der Spec ausdrücklich
   entschieden werden.
2. **Zwei verschiedene Adressaten.** Betreiber (Health-Signal, wachsend, Monitor-tauglich) und
   Nutzer (Etappe X ist nicht vermessen, deshalb Segmentsprache). Das Ticket nennt beide („weder im
   Editor noch im Briefing noch im Log an sichtbarer Stelle"). Ob eine oder zwei Flächen entstehen,
   ist die zentrale Spec-Entscheidung.
3. **Diagnose darf den Fachablauf nie stören.** Der Alarmlauf hat eine Zeitobergrenze (ADR-0038);
   das bestehende Journal-Muster ist deshalb konsequent fail-soft. Jede neue Schreibstelle muss das
   übernehmen.
4. **Rauschen.** `backfill_stage_distances` läuft in **jedem** Alarm- und Briefing-Lauf. Ein
   Journal-Eintrag je Lauf und Etappe erzeugt ohne Dämpfung viele gleichlautende Zeilen. Der
   `_failed_lookups`-Cache dämpft das innerhalb eines Prozesses bereits — als Nebenwirkung, nicht
   als Zusicherung.
5. **Nicht jeder Fehlschlag ist ein Defekt.** Ein Trip ohne GPX-Bestand ist der Normalfall, kein
   Ausfall. Ein Health-Signal, das darauf anspringt, wäre Sicherheits-Theater und würde gegen die
   Readiness-Regel verstoßen. Die Spec muss trennen: „nie versucht / nichts vorhanden" vs.
   „vorhanden, aber nicht auflösbar".
6. **Wegpunkt im Editor verschieben.** Wird ein Wegpunkt verschoben, bleibt die gespeicherte
   `distance_from_start_km` per Spread (`EditStagesPanelNew.svelte:646`) erhalten — der Messwert
   gehört dann zur alten Position. In der Analyse zu prüfen, ob das eine eigene stille
   Falschangabe ist (dann Nebenbefund → #1199 oder eigenes Ticket).
7. **Testlage.** Die 1177 Zeilen Bestandstests prüfen ausschließlich **ob** `None` herauskommt.
   Jeder Grund braucht einen eigenen Wächter, sonst ist die Begründungslogik unbewacht.

## Korrigierte Fehlannahmen aus der Recherche

Zwei Behauptungen der Explore-Agenten habe ich nachgeprüft und **widerlegt** — sie stehen hier,
damit sie in der Analyse nicht erneut als Faktum auftauchen:

- „Es gibt keine GPX-Fläche im Frontend" — **falsch**: `frontend/src/routes/gpx-upload/+page.svelte`
  sowie `EditRouteSection.svelte`, `TripNewEditor.svelte`, `EtappenStrip.svelte`.
- „Das Frontend wirft `distance_from_start_km` beim Speichern still weg, weil der TypeScript-Typ es
  nicht kennt" — **falsch**: TypeScript-Interfaces entfernen zur Laufzeit nichts, und der Editor
  reicht Wegpunkte per Spread (`{...w}`) durch. Nur **neu angelegte** Wegpunkte
  (`EditStagesPanelNew.svelte:613`) haben das Feld naturgemäß nicht.

## Offene Fragen für `/20-analyse`

1. Deckt Scheibe 2 alle drei stillen Stellen ab oder nur die Auflösung?
2. Betreiber-Sichtbarkeit über das bestehende `enrichment_calls.jsonl` (Pfad `track_resolution`,
   null Go-Änderung) oder eigenes nutzerbezogenes Journal unter `data/users/<uid>/diagnostics/`?
3. Braucht es überhaupt eine Nutzer-Fläche im Editor — oder reicht die Sichtbarkeit dort, wo die
   Folge auftritt (Briefing/Alarm)? Das ist eine Produktfrage für den PO, formuliert als AC.
4. Wie wird „nie versucht" von „versucht und gescheitert" unterschieden, ohne Fehlalarme für Trips
   ohne GPX-Bestand?

---

# Analysis

## Type

Bug — Observability-Lücke. Kein Fehlverhalten der Berechnung, sondern ein Fehlschlag ohne Spur.

## Messung am Produktivbestand (2026-08-22, `users/henning`, nur lesend)

Alles Folgende ist **gemessen**, nicht geschätzt — die Skripte liegen im Session-Scratchpad.

### Wie oft scheitert die Auflösung heute?

| Trip | Etappen | Ergebnis |
|---|---|---|
| KHW 403 | 13 | 12 aufgelöst, 1 bereits vermessen → **13/13 in Ordnung** |
| GR221 Mallorca | 4 | **4/4 aufgelöst** (Tag 1 über die Dubletten-Toleranz aus Scheibe 1) |
| Graveltour im Münsterland | 3 | 0 aufgelöst — nächster Kandidat **612 km** entfernt |
| Lottis Abschiedfahrradtour | 3 | 0 aufgelöst — nächster Kandidat **605 km** entfernt |

**Null** Mehrdeutigkeits-Fehlschläge. Die sechs Fehlschläge sind ausnahmslos Trips **ohne eigene
GPX** — der Normalfall, kein Defekt.

**Folge für den Entwurf:** Der Fehlschlag, den das Ticket meint, tritt heute **überhaupt nicht auf**;
er ist prospektiv (verschobener Wegpunkt, erneut hochgeladene Kopie). Ein Signal, das stumpf auf
„nicht auflösbar" anspringt, würde dauerhaft auf sechs kerngesunden Etappen feuern — Sicherheits-
Theater statt Überwachung, und ein Verstoß gegen die Readiness-Regel.

### Löst Stelle 2 real aus?

**Nein.** Kein einziges Wegpunktpaar im gesamten Produktivbestand ist nicht-monoton oder kürzer als
die Luftlinie. Stelle 2 ist ein realer Codepfad mit **null** Vorkommen im Bestand.

### Die Melderegel — messbar begründet statt geraten

Getestet wurde, wie weit der **beste verworfene** Kandidat je Etappe danebenliegt:

| Fall | Abstand |
|---|---|
| Echter Beinahe-Treffer (zweite Aufzeichnung derselben Route, Mallorca Tag 2) | **111 m** |
| Nächster unbeteiligter Kandidat (Nachbaretappe derselben Tour) | **4.673 m** |
| Fremder Trip (Münsterland gegen Mallorca-GPX) | **> 600.000 m** |

Faktor **42** zwischen „gehört plausibel zu dieser Route" und „gehört nicht dazu".

Die naheliegende Alternative — nach der **Zahl** getroffener Wegpunkte zu unterscheiden — wurde
gemessen und **verworfen**: Nachbaretappen teilen sich die Hütte und treffen dadurch 1–2 Wegpunkte;
die zweite Mallorca-Aufzeichnung trifft 2 von 4. Beide liegen bei 50 % — die Trefferzahl trennt die
Fälle **nicht**. Der Abstand trennt sie sauber.

## Befunde des Analysis-Challengers (geprüft, nicht übernommen)

| Finding | Bewertung nach eigener Prüfung |
|---|---|
| **A — Stelle 1 und 2 sind wirklich unabhängig** | **Bestätigt.** Zwei Wegpunkte auf demselben Trackpunkt ⇒ `span == 0` ⇒ Stelle 2 feuert, obwohl Stelle 1 erfolgreich war. Und: trägt jeder Wegpunkt schon einen (veralteten) Wert, wird Stelle 1 **gar nicht erst aufgerufen** (`track_resolution.py:193-196`), Stelle 2 kann trotzdem greifen. |
| **A(b) — meine Referenz in Risk #6 war falsch** | **Bestätigt und korrigiert.** `EditStagesPanelNew.svelte:646` ist der Umbenennen-Handler, keine Verschiebung. Nachgeprüft: in dieser Datei gibt es **keinen** Handler, der `lat`/`lon` eines bestehenden Wegpunkts ändert (nur `handleMapClick`, Zeile 610, legt neue an). Risk #6 ist damit **nicht belegt** und fällt. |
| **B(b) — Go akzeptiert einen falschen Wert, statt zurückzufallen** | **Bestätigt — und es ist kein Sichtbarkeitsproblem, sondern ein eigener Defekt.** `naismith.go:124` prüft nur `delta >= 0`; die Luftlinien-Untergrenze aus `trip_segments.py:148` fehlt dort. Ein positiver, aber zu kleiner Wert, den Python korrekt verwirft, wird von Go **benutzt** → zu kurze Gehzeit. Gehört **nicht** in diese Scheibe (Sichtbarkeit), sondern in ein eigenes Ticket. |
| **B(a) — Granularitätsbruch** | **Bestätigt.** Python entscheidet je Etappe alles-oder-nichts, Go je Wegpunktpaar. Beide können für dieselbe Etappe unterschiedlich urteilen. Ebenfalls eigener Befund, nicht Sichtbarkeit. |
| **C — `enrichment_calls.jsonl` ist der falsche Ort** | **Bestätigt, und das kippt meine Vorzugsvariante.** Das Journal liegt an der globalen Datenwurzel und wird nur nach `path` aggregiert. Sobald **irgendein** Nutzer **irgendeine** Etappe auflöst, steht dort „gerade eben erfolgreich" — während ein einzelner Trip seit Wochen still degradiert. Genau der #2070-Fall wäre **nicht** gefangen worden. Trip-Kennungen in das globale Journal zu schreiben verbietet ADR-0003. |
| **D/E — Prämisse trägt, kein vierter Verbraucher** | Bestätigt. |

Der parallel beauftragte Plan-Agent empfahl genau diesen globalen Journal-Weg als Bauform A. Ich
folge ihm **nicht** — aus Grund C und weil seine Abgrenzung „kein Signal, wenn das GPX-Verzeichnis
leer ist" an der Messung scheitert: die sechs Münsterland-Etappen haben ein **volles**
GPX-Verzeichnis, nur eben mit Dateien anderer Touren. Sie wären nach seinem Vokabular
`no_candidate_within_tolerance` und damit dauerhaft meldepflichtig. Brauchbar aus seinem Bericht
sind die additive Signaturerweiterung (unten) und die Rauschbegrenzung über `_failed_lookups`.

## Der tragfähige Andockpunkt: das nutzerbezogene Diagnose-Muster

`internal/scheduler/briefing_health.go:200-208, 357-381` zeigt ein im Projekt bereits **zweifach**
umgesetztes Muster (`corrupt_trips.json` #1262, `alert_anchor_rejected.jsonl` #1661):

1. **Python schreibt mit vollem Detailgrad** nach `data/users/<uid>/diagnostics/<name>` — dort darf
   Etappen- und Trip-Kennung stehen, es ist das Verzeichnis genau dieses Nutzers.
2. **Go aggregiert über alle Nutzer per Glob** und lässt dabei **ausdrücklich nur Zähler und
   Zeitstempel** über die Grenze (`briefing_health.go:203-205`: „Privacy (#252): only the timestamp
   is decoded — NEVER entity_id or reason").
3. Ergebnis erscheint in `/api/scheduler/status`, die Eskalation formt der externe Monitor.

Damit lösen sich Finding C und die ADR-0003-Frage in einem Zug: „welche Etappe" steht beim Nutzer,
„wie viele und seit wann" beim Betreiber.

## Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/track_resolution.py` | MODIFY | Grund erheben statt verwerfen (additiver optionaler Ausgabeparameter, Default `None` — bestehende Aufrufer unverändert); Journal-Aufruf an der Stelle, an der `_failed_lookups` gesetzt wird |
| `src/services/trip_segments.py` | MODIFY | Stelle 2: Verwerfungsgrund melden statt still `None` |
| `src/services/track_resolution_health.py` | CREATE | Schreibseite des nutzerbezogenen Journals, Vorbild `alert_briefing_anchor.record_alert_anchor_rejected` |
| `internal/scheduler/briefing_health.go` | MODIFY | Aggregat über alle Nutzer (Zähler + Streak), Vorbild `aggregateCorruptTrips` |
| `tests/tdd/test_track_resolution_failure_visibility.py` | CREATE | Wächter je Grund + Melderegel + Datenschutzgrenze |
| `internal/scheduler/briefing_health_test.go` | MODIFY | Go-Wächter fürs Aggregat |

**Nicht berührt:** `src/app/models.py`, `internal/model/*.go`, `internal/store/store.go` — **kein**
Datenschema-Backup-Hook, keine Migration, kein Frontend, kein Renderer-Gate.

## Scope Assessment

- Dateien: 4 MODIFY, 2 CREATE
- Geschätzt: ~+130 Python, ~+60 Go, plus Tests → **LoC-Limit 250 wird voraussichtlich überschritten**,
  `loc_limit_override 500` einplanen
- Risiko: **MEDIUM** — reines Journal-I/O, keine Persistenz-Änderung; das Risiko liegt in der
  Melderegel (Fehlalarm-Freiheit) und in der Datenschutzgrenze zwischen Python und Go

## Technical Approach (Empfehlung)

1. **Grund erheben, nicht neu messen.** `_match_track` kennt den schlechtesten Wegpunkt-Abstand
   (`track_resolution.py:64`), `_ergebnisse_sind_gleich` kennt die Abweichung (`:98-101`). Beide
   geben ihn über einen additiven, optionalen Ausgabeparameter heraus; bei Default `None` ändert
   sich nichts, die 1177 Bestandszeilen bleiben unangetastet.
2. **Melderegel:** gemeldet wird nur, wenn der beste Kandidat jeden Wegpunkt bis auf **≤ 1 km**
   trifft — dann gehört die GPX plausibel zu dieser Route und ihr Scheitern ist eine Nachricht.
   Darüber: Schweigen, der Trip hat schlicht keine passende Aufzeichnung. Begründung ist die
   Messung oben (111 m gegen 4.673 m; die Schwelle liegt mit Faktor 9 bzw. 4,7 in der Lücke).
3. **Ablage:** `data/users/<uid>/diagnostics/track_resolution_failures.jsonl`, eine Zeile je
   Etappe und Grund, mit Etappenkennung und Messwert.
4. **Rauschbegrenzung:** Der Journal-Aufruf hängt an derselben Stelle wie `_failed_lookups.add`
   (`track_resolution.py:205`) — damit höchstens **eine** Zeile je Etappe und Prozess, ohne neue
   Dämpfungslogik. Nur bei `persist=True` (der Vorschau-Pfad darf nichts hinterlassen).
5. **Betreiber-Aggregat:** Zähler + Streak in `briefing_health`, **niemals** Etappen-, Trip- oder
   Nutzerkennung — die Datenschutzgrenze aus #252 gilt wörtlich.
6. **Fail-soft:** Jeder Journal-Fehler wird geschluckt. Diagnose darf den Alarmlauf nie gefährden
   (ADR-0038).

## Abgrenzung — was diese Scheibe NICHT liefert

- **Keine Nutzer-Fläche im Editor.** Ein Etappen-Badge braucht ein neues Feld im Datenmodell
  (Python **und** Go), ein Frontend-Typ und eine Komponente — zwei Schema-Gates und ein eigenes
  LoC-Budget. Das ist eine eigene Scheibe und eine Produktentscheidung.
- **Kein Fix für Finding B.** Dass Go einen unplausiblen Wert benutzt, statt zurückzufallen, ist ein
  Rechenfehler, kein Sichtbarkeitsproblem → eigenes Ticket.

## Open Questions

- [ ] Reicht dem PO die abrufbare, gezählte Sichtbarkeit — oder muss die Nutzer-Fläche mit in diese
      Scheibe? (Entscheidet sich an der Spec-Freigabe.)
- [ ] Finding B (Go benutzt unplausible Werte) als eigenes Ticket anlegen — bestätigt der PO das als
      nutzersichtbares Fehlverhalten, ist es Triage-Kategorie (a) und damit ein eigenes Issue.
