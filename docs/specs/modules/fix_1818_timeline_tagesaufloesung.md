---
entity_id: fix_1818_timeline_tagesaufloesung
type: module
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [telegram, timeline, snapshot, bug]
---

# Timeline-Tagesaufloesung: Datenluecke statt Tourplanungs-Aussage

## Approval

- [ ] Approved

## Purpose

Die Telegram-Abfragen `timeline_heute`, `timeline_morgen`, `glance` und `heute_gewitter` melden
heute eine fehlende Wetterlage fuer einen Tag faelschlich als **„Keine Etappe geplant"** — eine
Aussage ueber die Tourplanung, obwohl das System nur etwas ueber den Datenbestand weiss. Diese
Spec aendert die vier betroffenen Formatierer so, dass sie (a) einen fehlenden Tag zuerst aus
bereits vorhandenen datierten Snapshots decken, bevor sie aufgeben, und (b) im verbleibenden
Fall ehrlich zwischen „keine Daten" und „keine Etappe" unterscheiden.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `_fmt_timeline` (:1007), `_fmt_glance` (:929, :933), `_fmt_gewitter` (:944),
  `_aggregate_day` (:837-877), Query-Dispatch (:505-560)

> **Schicht-Hinweis:** Python-Core / Domain-Backend (`src/services/`), FastAPI-Core-seitige
> Telegram-Inbound-Verarbeitung. Kein Go-API-, kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~80-120
- **Files:** 2-3
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_snapshot.py` (`WeatherSnapshotService.load_dated`) | module | Liest den tagesdatierten Snapshot `{trip_id}_{YYYY-MM-DD}.json` als Rueckfallquelle, rein lesend |
| `src/services/weather_extractor.py` (`timeline`) | module | Liefert die ungefilterten Segmentpunkte aus dem undatierten Anker; bleibt unveraendert, wird nur mit den ggf. um den Rueckfall ergaenzten Rohdaten aufgerufen |
| `src/services/trip_segments.py` (`convert_trip_to_segments`) | module | Netzfreie Segmentbildung je Tag — beantwortet „existiert an diesem Tag ueberhaupt eine Etappe?" unabhaengig vom Wetter-Anker |
| `src/services/trip_report_scheduler.py` (`_write_briefing_anchor`) | module | Erzeugt sowohl den undatierten Anker als auch den datierten Snapshot; wird von dieser Spec **nicht** veraendert, nur als Quelle gelesen |
| `src/services/trip_alert.py` (`_get_cached_weather`) | module | Kollisionsflaeche: liest denselben undatierten Anker fuer den Alarm-Δ-Vergleich; muss durch diese Aenderung unberuehrt bleiben (siehe Known Limitations) |

## Implementation Details

**Gestufte Quellenauflösung je angefragtem Tag.** Fuer jeden angefragten Tag (`heute`/`morgen`)
prueft der Formatierer zuerst, ob der bereits geladene undatierte Anker (`{trip_id}.json`, via
`weather_extractor.timeline()`) Segmentpunkte fuer diesen Tag traegt (bestehende
`_aggregate_day`-Filterung nach `local_dt(p.arrival_time, tz).date() == target_date`). Ist das
nicht der Fall, wird `WeatherSnapshotService.load_dated(trip_id, target_date)` als Rueckfall
gelesen — rein lesend, kein neuer Schreibpfad. Liefert auch das nichts, gibt es fuer diesen Tag
keine Daten.

**Aussage von Datenverfuegbarkeit trennen.** Nur wenn beide Quellen leer sind, entscheidet
`services.trip_segments.convert_trip_to_segments(trip, target_date)` — eine netzfreie,
rein tourplan-basierte Segmentbildung ohne Wetterdaten — ob an diesem Tag ueberhaupt eine Etappe
existiert:
- Etappe vorhanden, aber keine Wetterdaten → ehrliche Fehlanzeige „noch keine Wetterdaten fuer
  {label} ({datum})" mit Verweis auf das Kommando, das fuer diesen Tag ein Briefing zustellt.
- Keine Etappe an diesem Tag → die bestehende Aussage „Keine Etappe geplant" bleibt (sie ist in
  diesem Fall zutreffend).

Diese Unterscheidung wird in allen vier betroffenen Formatierern (`_fmt_timeline:1007`,
`_fmt_glance` heute-Zweig `:929`, `_fmt_glance` morgen-Zweig `:933`, `_fmt_gewitter:944`)
umgesetzt — nicht nur an einer Stelle, da alle vier auf `_aggregate_day` aufsetzen und alle vier
denselben Denkfehler wiederholen (Challenger-Befund, siehe `docs/context/fix-1818-timeline-zweitagesanker.md`).

**Kein On-Demand-Abruf im Abfragepfad.** Der bestehende Nachlade-Helper
`_fetch_and_save_snapshot` (`trip_command_processor.py:278-316`) wird von dieser Aenderung
**nicht** aufgerufen und nicht erweitert. Fehlt ein Tag auch nach dem Rueckfall auf den
datierten Snapshot, bleibt die Antwort eine ehrliche Fehlanzeige statt eines API-Abrufs.

**Nicht-Ziele (explizit ausgeschlossen):** `_write_briefing_anchor`
(`trip_report_scheduler.py:1505-1512`), `WeatherSnapshotService.save()`, `save_dated()` sowie
jeglicher Code in `trip_alert.py` bleiben unveraendert. Diese Spec fuegt **keinen** neuen
Schreibpfad auf Snapshot-Dateien hinzu.

### Architektur-Begruendung: keine geteilte Funktion mit `trip_alert.py`

`trip_alert.py:629-750` (#1916/#1661) implementiert bereits eine gestufte Quellenkette fuer
Wetterdaten (Briefing-Anker → rollierender Alarm-Anker → undatierter Rueckfall). Die hier
gebaute Kette ist bewusst **keine** gemeinsame Funktion mit jener, weil Anzeige und
Δ-Vergleich unterschiedliche Vertrauensregeln haben: `briefing_backed` (ADR-0009/#1699)
entscheidet, ob Daten als **Vergleichsbasis** fuer den Abweichungs-Alarm taugen — fuer die
reine **Anzeige** einer Timeline ist diese Frage bedeutungslos, denn hier wird nichts
verglichen, sondern nur der zuletzt bekannte Wert gezeigt. Eine geteilte Funktion muesste das
Kriterium `briefing_backed` parametrisieren und wuerde beide Aufrufer aneinander koppeln —
eine Aenderung am Alarm-Vertrauensmodell haette dann ungewollt Auswirkungen auf die
Timeline-Anzeige und umgekehrt.

### Begruendung gegen den Nachlade-Weg

Open-Meteo Free-Tier ist auf 10.000 Anfragen/Tag begrenzt und in Produktion real erschoepft
(`docs/specs/modules/fix_1329_forecast_cache_budget.md:19-22`, HTTP 429 im Prod-Log). Zusaetzlich
schreibt `_fetch_and_save_snapshot` (`trip_command_processor.py:278-316`) den Anker mit
`briefing_backed=False` — ein Abruf ueber den Abfragepfad wuerde damit einen vorhandenen
briefing-gestuetzten Anker ueberschreiben und die Alarm-Vergleichsbasis zerstoeren
(`trip_alert.py:738-742` verwirft nicht-briefing-gestuetzte Basen). Der Rueckgriff auf bereits
vorhandene datierte Snapshots ist dagegen kostenlos und veraendert keinen Schreibzustand.

## Expected Behavior

- **Input:** Telegram-Kommandos `timeline_heute`, `timeline_morgen`, `glance`, `heute_gewitter`
  fuer einen Trip, dessen undatierter Wetter-Anker nur einen der beiden Tage traegt.
- **Output:** Fuer den fehlenden Tag entweder (a) Stundenwerte aus dem passenden datierten
  Snapshot, falls vorhanden, oder (b) eine ehrliche Datenluecken-Meldung mit Verweis auf das
  briefing-ausloesende Kommando, falls eine Etappe existiert, oder (c) die unveraenderte Aussage
  „Keine Etappe geplant", falls tatsaechlich keine Etappe an diesem Tag existiert.
- **Side effects:** Keine. Es wird nichts geschrieben, kein Netzabruf ausgeloest, kein Feld eines
  bestehenden Ankers veraendert.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat für morgen eine Etappe und der Wetter-Anker trägt nur den
  heutigen Tag / When der Nutzer `timeline_morgen` abfragt / Then meldet die Antwort, dass für
  morgen noch keine Wetterdaten vorliegen, und behauptet NICHT „Keine Etappe geplant".
  - Test: Zwei aufeinanderfolgende, einander ueberschreibende Briefing-Schreibvorgaenge bauen
    einen Anker auf, der nur „heute" traegt; der Nutzer fragt per Telegram-Kommando
    `timeline_morgen` ab und liest eine Datenluecken-Meldung statt einer Tourplanungs-Aussage.

- **AC-2:** Given ein Trip hat für morgen KEINE Etappe (Ruhetag oder Tag nach Tourende) / When
  der Nutzer `timeline_morgen` abfragt / Then bleibt die Antwort „Keine Etappe geplant" — diese
  Aussage ist dann zutreffend.
  - Test: Ein Trip, dessen letzte Etappe heute endet, wird per `timeline_morgen` abgefragt; der
    Nutzer liest weiterhin „Keine Etappe geplant" und keine Datenluecken-Meldung.

- **AC-3:** Given der undatierte Anker trägt morgen (das Abend-Briefing lief zuletzt) und ein
  datierter Snapshot für heute existiert / When der Nutzer `timeline_heute` abfragt / Then
  zeigt das System die Stundenwerte des heutigen Tages aus dem datierten Snapshot.
  - Test: Nach einem simulierten Abend-Briefing (Anker traegt morgen) und einem vorhandenen
    `{trip_id}_{heute}.json` fragt der Nutzer `timeline_heute` ab und sieht konkrete
    Stundenwerte statt einer Fehlanzeige.

- **AC-4:** Given der undatierte Anker und ein datierter Snapshot tragen denselben Tag mit
  unterschiedlichen Werten / When dieser Tag abgefragt wird / Then stammen die angezeigten
  Werte aus dem undatierten Anker, nicht aus dem datierten Snapshot.
  - Test: Ein Anker und ein datierter Snapshot fuer denselben Tag mit bewusst unterschiedlichen
    Temperaturwerten werden angelegt; der Nutzer fragt den Tag ab und liest den Wert aus dem
    Anker, nicht aus dem Snapshot.

- **AC-5:** Given ein Trip hat an beiden Tagen Etappen, der Anker trägt nur einen davon und
  für den anderen existiert kein datierter Snapshot / When der Nutzer `glance` abfragt / Then
  meldet die Zeile des fehlenden Tages fehlende Wetterdaten, während die Zeile des vorhandenen
  Tages unverändert aggregiert bleibt.
  - Test: Ein Trip mit Etappen an beiden Tagen, Anker traegt nur heute, kein datierter Snapshot
    fuer morgen; der Nutzer fragt `glance` ab und sieht in einer Antwort sowohl die aggregierte
    heutige Zeile als auch die Datenluecken-Zeile fuer morgen.

- **AC-6:** Given ein Trip hat heute eine Etappe, der Anker trägt nur morgen und für heute
  existiert kein datierter Snapshot / When der Nutzer `heute_gewitter` abfragt / Then meldet
  die Antwort fehlende Wetterdaten für heute statt „Keine Etappe geplant — kein
  Gewitter-Status".
  - Test: Anker traegt nur morgen, kein datierter Snapshot fuer heute, Trip hat heute eine
    Etappe; der Nutzer fragt `heute_gewitter` ab und liest eine Datenluecken-Meldung statt
    „Keine Etappe geplant — kein Gewitter-Status".

- **AC-7:** Given eine der Abfragen timeline/glance/gewitter wird bei fehlenden Daten
  beantwortet / When die Antwort erzeugt wird / Then löst sie keinen Wetter-Abruf aus und
  verändert keine Snapshot-Datei; insbesondere bleibt das Feld `briefing_backed` eines
  vorhandenen Ankers unverändert.
  - Test: Vor und nach der Abfrage wird der Dateiinhalt (Aenderungszeitstempel und
    `briefing_backed`-Feld) des undatierten Ankers verglichen; ausserdem wird nachgewiesen,
    dass kein HTTP-Aufruf an den Wetter-Provider stattfand.

- **AC-8:** Given die ehrliche Fehlanzeige erscheint / When der Nutzer sie liest / Then
  verweist sie auf das Kommando, das für diesen Tag ein Briefing auslöst, und sagt
  ausschließlich die Zustellung des Briefings zu — sie verspricht nicht, dass sich die
  Timeline-Ansicht danach füllt.
  - Test: Der Nutzer liest den Text der Datenluecken-Meldung und findet darin den Verweis auf
    das briefing-versendende Kommando sowie eine Formulierung, die nur die Zustellung des
    Briefings zusagt, nicht das nachtraegliche Fuellen der Timeline-Ansicht (das On-Demand-
    Kommando `morgen` schreibt laut `trip_report_scheduler.py:1495-1501` keinen Anker).

## Known Limitations

- Der dritte, seltene Ankerzustand aus `send_test_report`/`select_test_stage`
  (`trip_report_scheduler.py:981-1050`), bei dem der Anker weder heute noch morgen traegt,
  sondern einen beliebigen Fallback-Tag, wird durch die tagesgenaue Aufloesung automatisch mit
  abgedeckt, ist aber nicht Gegenstand eines eigenen Acceptance-Criterion.
- Die Ankerstruktur besitzt weiterhin nur ein einziges `target_date`-Feld auf oberster Ebene;
  diese Spec aendert daran nichts. Jeder kuenftige Code, der `target_date` als Torwaechter fuer
  „welche Tage traegt der Anker" nutzt, bekommt weiterhin nur eine halbe Wahrheit.
- `trip_alert.py:629-750` bleibt unveraendert und behaelt seine eigene, unabhaengige
  Quellenkette fuer den Δ-Vergleich; ein zweitaegiger Anker wuerde dort weiterhin ohne
  Tagesfilter gelesen — das ist Bestandsverhalten und nicht Teil dieses Fixes, aber jede
  Implementierung MUSS durch einen Test nachweisen, dass sie an dieser Lesestelle nichts
  veraendert (siehe AC-7).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine lokale Korrektur der Lesepfade in vier bestehenden
  Formatierern, keine neue Persistenz-, Auth- oder Kanalentscheidung. Die betroffenen
  Vertrauensregeln (`briefing_backed`, ADR-0009) bleiben unveraendert; es wird lediglich eine
  zusaetzliche, rein lesende Quelle (datierter Snapshot) in eine bestehende Anzeige-Kette
  eingefuegt.

## Nachweisführung

- **Bestandsfixturen verdecken den Bug.** `tests/tdd/test_issue_651_telegram_query_glance.py:108-119`
  und `tests/tdd/test_timeline_folgt_der_ortszeit.py:95-101` bauen den Anker **künstlich mit
  beiden Tagen in EINEM `save()`-Aufruf** auf. Der Produktionspfad — zwei getrennte, einander
  überschreibende Briefing-Läufe — kommt in keinem bestehenden Test vor. Ein RED-Test MUSS den
  Anker über **zwei aufeinanderfolgende, einander überschreibende Schreibvorgänge** aufbauen
  (analog zu zwei `_write_briefing_anchor`-Läufen), sonst ist er trivial grün.
- **AC-2 ist der Gegenfall zu AC-1** und existiert, um eine Bedingungs-Inversion („Etappe
  vorhanden?" verdreht) fangbar zu machen. Ohne AC-2 bleibt diese Mutation unsichtbar.
- **AC-4 existiert**, um eine Vertauschung der Quellen-Reihenfolge (datierter Snapshot vor
  undatiertem Anker gelesen) fangbar zu machen. Undatierter und datierter Snapshot müssen dafür
  bewusst **unterschiedliche Werte** tragen — identische Fixturen machen den Test wirkungslos.
- Tests lösen ihren Prüfling **relativ zur eigenen Testdatei** auf, nie über den festen
  Hauptrepo-Pfad, damit sie im Worktree korrekt gegen den lokalen Stand laufen.

## Changelog

- 2026-08-21: Initial spec created
