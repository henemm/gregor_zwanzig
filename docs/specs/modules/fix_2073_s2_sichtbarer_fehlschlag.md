---
entity_id: fix_2073_s2_sichtbarer_fehlschlag
type: module
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [observability, track-resolution, diagnostics]
---

# #2073 Scheibe 2 — Der stille Fehlschlag der Track-Auflösung wird sichtbar

## Approval

- [x] Approved — PO „go" 2026-08-22

## Purpose

Wenn die gemessene Wegstrecke einer Trip-Etappe nicht aus dem GPX-Bestand aufgelöst werden kann,
scheitert das heute geräuschlos: `resolve_stage_track_km` kennt den Grund (schlechtester
Wegpunkt-Abstand bzw. Abweichung zwischen Kandidaten) und wirft ihn weg, die Ortsangabe in Alarmen
fällt auf „Segment N" zurück, niemand erfährt davon. Bei #2070 war eine eigens beauftragte Messung
nötig, um 3 von 13 betroffene Etappen zu finden. Diese Scheibe erhebt den Grund statt ihn zu
verwerfen, protokolliert ihn nutzerbezogen und lässt ihn beim Betreiber als wachsendes Signal
zählen — sie erfüllt damit die ausdrückliche Folgepflicht aus ADR-0018 („Neue degradierbare
Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen: Marker in Daten + wachsendes
Health-Signal").

## Source

- **File:** `src/services/track_resolution.py`
- **Identifier:** `_match_track`, `_ergebnisse_sind_gleich`, `backfill_stage_distances`

## Estimated Scope

- **LoC:** ~+130 Python, ~+60 Go, plus Tests — das LoC-Limit von 250/Workflow wird voraussichtlich
  überschritten; `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 3 MODIFY, 2 CREATE (`trip_segments.py` wird nur aufgerufen, nicht geändert)
- **Effort:** medium — reines Journal-I/O ohne Persistenz-Änderung; die Sorgfalt liegt in der
  Melderegel (Fehlalarm-Freiheit) und in der Datenschutzgrenze zwischen Python und Go.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/enrichment_health.py` | module | Vorbild für fail-soft JSONL-Journal, Pfad frisch je Aufruf über den Loader auflösen (Falle #1633) |
| `src/services/alert_briefing_anchor.py` (`record_alert_anchor_rejected`) | module | Vorbild für **nutzerbezogene** Ablage unter `get_data_dir(user_id) / "diagnostics"` |
| `internal/scheduler/briefing_health.go` (`analyzeAlertAnchorRejections`, `aggregateCorruptTrips`) | module | Vorbild für das Go-Aggregat (Streak + Recent-Count per Glob über alle Nutzer) |
| `app.loader.get_data_dir` | function | Nutzerbezogener Datenpfad, Mandantentrennung (ADR-0003) |
| `src/services/track_resolution.py` (`_failed_lookups`) | module | Bestehende Prozess-Dämpfung, an deren Stelle der Journal-Aufruf hängt |

### Schicht-Hinweis (geprüft)

Betroffen sind ausschließlich **Python-Core** (`src/services/`, `src/providers/` als Vorbild) und
**Go-API** (`internal/scheduler/`). Kein Frontend, kein `internal/model/*.go`, kein `internal/store/`.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/track_resolution.py` | MODIFY | `_match_track` und `_ergebnisse_sind_gleich` erhalten je einen additiven, optionalen Ausgabeparameter für den Grund (Default `None`, bestehende Aufrufer unverändert); `backfill_stage_distances` ruft das Journal an der Stelle, an der heute `_failed_lookups.add(key)` passiert (Zeile 205), sowie beim Kurzschluss „bereits vermessen, aber unplausibel" (Zeilen 193–196) |
| `src/services/trip_segments.py` | UNVERÄNDERT (wiederverwendet) | `stage_measured_distances` (Zeilen 113–151) bleibt **unangetastet**. Die Plausibilitätsregel für Stelle 2 wird nicht dupliziert und nicht umgebaut, sondern aufgerufen: liefert sie `None`, obwohl jeder Wegpunkt einen Wert trägt, ist das genau der Fall `implausible_measurement`. Grund für diesen Zuschnitt: die Funktion kennt weder `user_id` noch `trip_id` (Signatur nimmt nur Wegpunkte) — sie könnte gar nicht nutzerbezogen protokollieren, und sie in den Renderer-Pfaden mit einem Ausgabeparameter zu versehen hieße, eine geteilte Funktion für einen Diagnosezweck aufzubohren |
| `src/services/track_resolution_health.py` | CREATE | Schreibseite des nutzerbezogenen Journals `data/users/<user_id>/diagnostics/track_resolution_failures.jsonl`, Vorbild `alert_briefing_anchor.record_alert_anchor_rejected` |
| `internal/scheduler/briefing_health.go` | MODIFY | Neue Funktion nach Vorbild `analyzeAlertAnchorRejections`; zwei neue Top-Level-Schlüssel `track_resolution_failure_streak_since` und `track_resolution_failures_recent_count` unter `/api/scheduler/status` |
| `tests/tdd/test_track_resolution_failure_visibility.py` | CREATE | Wächter je Grund, Melderegel (1-km-Grenze), Datenschutzgrenze, Fail-soft |
| `internal/scheduler/briefing_health_test.go` | MODIFY | Go-Wächter fürs Aggregat (Streak, Recent-Count, leeres Journal, beschädigte Zeile) |

**Nicht berührt:** `src/app/models.py`, `internal/model/*.go`, `internal/store/store.go`, Frontend,
Mail-Renderer. Kein Datenschema-Backup-Hook, keine Migration, kein Renderer-Gate.

## Implementation Details

**1. Grund erheben statt verwerfen.** `_match_track` (`track_resolution.py:49-67`) kennt in
`best_dist` den Abstand des am wenigsten passenden Wegpunkts zum nächstgelegenen Trackpunkt.
`_ergebnisse_sind_gleich` (`:83-103`) kennt in der paarweisen Prüfung die maximale Abweichung
zwischen zwei Kandidaten. Beide geben den Wert über einen additiven, optionalen Ausgabeparameter
heraus (z. B. `out: Optional[dict] = None`, dort hineinschreiben statt zurückgeben, damit die
Signatur für Bestandsaufrufer unverändert bleibt). Bei Default `None` ändert sich am Verhalten
nichts — die 1177 Zeilen in `tests/tdd/test_track_resolution_legacy_trip.py` bleiben unangetastet.

**2. Melderegel.** Ein Fehlschlag wird nur protokolliert, wenn der beste Kandidat jeden Wegpunkt
bis auf **höchstens 1 km** trifft — dann gehört die GPX plausibel zu dieser Route, und ihr
Scheitern ist eine Nachricht. Liegt der beste Kandidat weiter weg, hat der Trip schlicht keine
passende Aufzeichnung: Schweigen, kein Eintrag. Die Schwelle ist gemessen (nicht geschätzt): ein
echter Beinahe-Treffer liegt bei 111 m, der nächste unbeteiligte Kandidat bei 4.673 m, ein fremder
Trip bei > 600 km. 1 km liegt mit Faktor 9 zum Beinahe-Treffer und Faktor 4,7 zum nächsten
unbeteiligten Kandidaten sicher in der Lücke dazwischen. Konstante mit sprechendem Namen im Modul
(z. B. `FAILURE_REPORT_TOLERANCE_KM = 1.0`), Herleitung als Kommentar an Ort und Stelle.

**3. Ablage.** Eine JSONL-Zeile je Etappe und Grund nach
`data/users/<user_id>/diagnostics/track_resolution_failures.jsonl`. Felder: `ts` (UTC ISO 8601),
`trip_id`, `stage_id`, `reason`, `detail` (Freitext/Zahl, je nach Grund — z. B. der gemessene
Abstand in Metern oder die maximale Abweichung). Neues Modul
`src/services/track_resolution_health.py`, Vorbild `enrichment_health.py` (fail-soft, Pfad bei
JEDEM Aufruf frisch über den Loader auflösen, nie als Modulkonstante binden — Falle #1633) und
`alert_briefing_anchor.record_alert_anchor_rejected` (nutzerbezogene Ablage über
`get_data_dir(user_id)`, nie global).

**4. Gründe-Vokabular:**
- `no_candidate_within_tolerance` — der beste Kandidat gehört plausibel zur Route (≤ 1 km),
  verfehlt aber mindestens einen Wegpunkt innerhalb der 10-m-Zuordnungstoleranz.
- `ambiguous_result` — mehrere Kandidaten passen, liefern aber widersprüchliche Wegstrecken.
- `implausible_measurement` — bereits gespeicherte Werte vorhanden, aber eine Teilstrecke ist
  kürzer als die Luftlinie oder die Werte steigen nicht streng monoton (Stelle 2,
  `trip_segments.stage_measured_distances`).

**5. Eine einzige Einhängestelle für Stelle 1:** `backfill_stage_distances`
(`track_resolution.py:159-228`). Der Journal-Aufruf hängt an derselben Stelle, an der heute
`_failed_lookups.add(key)` passiert (Zeile 205) — dadurch höchstens EINE Zeile je Etappe und
Prozess, ohne neue Dämpfungslogik. Zusätzlich wird der Fall „bereits vermessen" (Zeilen 193–196)
geprüft: sind die vorhandenen Werte unplausibel, entsteht dort eine
`implausible_measurement`-Zeile, obwohl die Auflösung selbst gar nicht läuft. Das Kriterium wird
**nicht nachgebaut**, sondern durch Aufruf von `trip_segments.stage_measured_distances` erhoben —
liefert sie `None`, obwohl jeder Wegpunkt einen Wert trägt, ist der Fall erkannt. Damit gibt es
weiterhin genau **eine** Definition von „unplausibel"; eine zweite Kopie würde beim nächsten
Schwellen-Wechsel still auseinanderlaufen. **Nur bei
`persist=True`** wird protokolliert — der Vorschau-Pfad (`persist=False`) darf nichts hinterlassen.

**6. Betreiber-Aggregat in Go.** `internal/scheduler/briefing_health.go` bekommt eine neue Funktion
nach dem Vorbild von `analyzeAlertAnchorRejections` (Zeilen 221–270): Glob über
`users/*/diagnostics/track_resolution_failures.jsonl`, Zeitstempel dekodieren, Streak- und
Recent-Count-Logik unverändert übernehmen (Gap-Schwelle analog zur bestehenden Kadenzwahl dort
begründen). Zwei neue Top-Level-Schlüssel unter `/api/scheduler/status`:
`track_resolution_failure_streak_since` (RFC3339, leer wenn kein laufender Streak) und
`track_resolution_failures_recent_count` (Fehlschläge der letzten 24 h, summiert über alle
Nutzer). **Datenschutzgrenze wörtlich einhalten (#252): aus dem Journal wird auf der Go-Seite
AUSSCHLIESSLICH der Zeitstempel dekodiert — niemals `trip_id`, `stage_id`, `reason` oder die
Nutzerkennung** (die Go-Struct trägt nur `Ts string`, wie `anchorRejectedEntry`).

**7. Fail-soft überall.** Jeder Journal-Fehler wird geschluckt (`except Exception` mit
`logger.warning`, Vorbild `record_alert_anchor_rejected`); Diagnose darf den Alarmlauf nie
gefährden (ADR-0038, Zeitgrenze je Nutzerlauf). Auf Go-Seite: eine unlesbare Nutzerdatei oder eine
beschädigte Zeile wird übersprungen, nie ein Panic.

## Expected Behavior

- **Input:** Ein Alarm- oder Briefing-Lauf ruft `backfill_stage_distances(trip, user_id,
  target_date, persist=True)` für eine Etappe auf, deren Track-Auflösung aus einem der drei
  bekannten Gründe scheitert (oder deren bereits gespeicherte Werte unplausibel sind).
- **Output:** Der Rückgabewert von `backfill_stage_distances` ist unverändert (der Trip, ggf.
  unvermessen); zusätzlich entsteht — nur wenn die Melderegel greift — genau eine JSONL-Zeile im
  Diagnose-Verzeichnis des betroffenen Nutzers.
- **Side effects:** Datei-Append unter `data/users/<user_id>/diagnostics/track_resolution_failures.jsonl`;
  keine Änderung an Trip-Daten, keine Exception nach außen bei Schreibfehler.

## Acceptance Criteria

- **AC-1:** Given eine Etappe, deren GPX-Bestand bis auf einen einzelnen, knapp abseits liegenden
  Wegpunkt zur Route passt (bester Kandidat ≤ 1 km, aber > 10 m Zuordnungstoleranz an einem
  Wegpunkt) / When `backfill_stage_distances(..., persist=True)` aufgerufen wird / Then entsteht
  eine Journalzeile mit `reason="no_candidate_within_tolerance"` und dem gemessenen Abstand in
  Metern in `detail`.
  - Test: Journaldatei nach dem Aufruf einlesen und auf genau einen Eintrag mit passendem `reason`
    und plausiblem `detail`-Wert prüfen (kein Dateiinhalt-String-Check, sondern geparstes JSON).

- **AC-2:** Given ein Trip ohne jede passende Aufzeichnung (bester Kandidat liegt weit jenseits der
  1-km-Meldegrenze, z. B. > 4 km) / When dieselbe Auflösung wie in AC-1 läuft, aber mit diesem
  weiter entfernten Kandidaten / Then entsteht **keine** Journalzeile — obwohl unter AC-1-Bedingung
  (derselbe Trip, aber ein Kandidat innerhalb 1 km) sehr wohl eine entstünde.
  - Test: Zwei Varianten desselben Etappen-Setups laufen lassen (Kandidat nah / Kandidat fern) und
    Journalzeilen-Anzahl vergleichen: 1 vs. 0. Nur „0" allein bewiese nicht, dass die Regel
    überhaupt greifen könnte.

- **AC-3:** Given mehrere GPX-Kandidaten, die zu widersprüchlichen Wegstrecken führen (Abweichung
  über der Ergebnisgleichheits-Toleranz) / When die Auflösung läuft / Then entsteht eine
  Journalzeile mit `reason="ambiguous_result"` und der maximalen gemessenen Abweichung in `detail`.
  - Test: Zwei präparierte GPX-Dateien mit bewusst abweichenden Wegstrecken einspielen, Journalzeile
    auf `reason` und numerisches `detail` prüfen.

- **AC-4:** Given eine Etappe, deren Track sich eindeutig auflösen lässt / When
  `backfill_stage_distances` erfolgreich vermisst / Then entsteht keine Fehlschlag-Zeile im
  Journal.
  - Test: Nach erfolgreichem Aufruf Journaldatei-Existenz bzw. Zeilenanzahl prüfen — muss
    unverändert (0 oder keine neue Zeile) bleiben.

- **AC-5:** Given eine Etappe, deren Auflösung im selben Prozess bereits einmal fehlgeschlagen ist
  / When ein zweiter Auflösungsversuch für dieselbe Etappe im selben Prozess läuft / Then bleibt es
  bei genau einer Journalzeile — der bestehende `_failed_lookups`-Cache dämpft weiterhin.
  - Test: `backfill_stage_distances` zweimal nacheinander mit identischen Argumenten aufrufen,
    Journalzeilen-Anzahl bleibt bei 1.

- **AC-6:** Given eine Etappe, deren Auflösung scheitert / When `backfill_stage_distances` mit
  `persist=False` aufgerufen wird (Vorschau-Pfad) / Then entsteht keine Journalzeile.
  - Test: Denselben Fehlschlagsfall wie AC-1 mit `persist=False` aufrufen, Journaldatei bleibt leer
    bzw. unverändert.

- **AC-7:** Given zwei verschiedene Nutzer mit je einem Auflösungsfehlschlag / When beide
  Auflösungen laufen / Then liegt jede Journalzeile ausschließlich im Diagnose-Verzeichnis des
  jeweils eigenen Nutzers, keine Vermischung.
  - Test: Zwei Nutzer-Datenverzeichnisse anlegen, je einen Fehlschlag auslösen, beide Journaldateien
    einzeln lesen und prüfen, dass jede genau die Zeile des eigenen Nutzers enthält.

- **AC-8:** Given das Diagnose-Verzeichnis ist nicht beschreibbar (z. B. Berechtigung entzogen) /
  When die Auflösung fehlschlägt und protokollieren will / Then liefert `backfill_stage_distances`
  unverändert sein reguläres Ergebnis (den unvermessenen Trip), kein Fehler dringt nach außen.
  - Test: Verzeichnis vor dem Aufruf schreibgeschützt machen, Aufruf darf keine Exception werfen und
    muss denselben Rückgabewert liefern wie ohne Schreibschutz.

- **AC-9:** Given eine Etappe mit bereits gespeicherten, aber unplausiblen Wegpunkt-Distanzen (eine
  Teilstrecke kürzer als die Luftlinie) / When `backfill_stage_distances` aufgerufen wird und den
  Kurzschluss „bereits vermessen" nimmt / Then entsteht eine Journalzeile mit
  `reason="implausible_measurement"`, obwohl die eigentliche Auflösung übersprungen wird.
  - Test: Etappe mit vorbelegten, aber unplausiblen `distance_from_start_km`-Werten übergeben,
    Journalzeile auf `reason` prüfen.

- **AC-10:** Given zwei verschiedene Nutzer mit je mindestens einem Fehlschlag innerhalb der
  Streak-Gap-Schwelle / When das Go-Aggregat `/api/scheduler/status` bildet / Then summiert
  `track_resolution_failures_recent_count` beide Nutzer, und
  `track_resolution_failure_streak_since` nennt den frühesten Zeitpunkt der zusammenhängenden
  Serie.
  - Test: Zwei Journaldateien unter zwei Nutzerverzeichnissen mit passenden Zeitstempeln anlegen,
    Aggregatfunktion aufrufen und beide Rückgabewerte gegen die erwarteten Werte prüfen.

- **AC-11:** Given ein Journal mit vollen Zeilen (inkl. `trip_id`, `stage_id`, `reason`, echter
  Nutzerkennung im Pfad) / When das Go-Aggregat es liest / Then enthält weder die interne
  Entry-Struktur noch der ausgegebene Status-Schlüssel Trip-, Etappen- oder Nutzerkennung — nur
  Zeitstempel-abgeleitete Werte.
  - Test: Go-Unit-Test prüft, dass die Decoder-Struct ausschließlich das Feld `Ts` besitzt (Analogie
    zu `anchorRejectedEntry`), und dass eine Journalzeile mit zusätzlichen Feldern trotzdem korrekt
    verarbeitet wird (JSON-Unmarshal ignoriert Unbekanntes, es wird nichts durchgereicht).

- **AC-12:** Given kein Journal vorhanden (frischer Deploy, noch nie ein Fehlschlag) / When das
  Go-Aggregat läuft / Then meldet es `track_resolution_failure_streak_since=""` und
  `track_resolution_failures_recent_count=0`, ohne Fehler.
  - Test: Aggregatfunktion gegen ein leeres bzw. nicht existierendes Datenverzeichnis aufrufen,
    Rückgabewerte auf die Leer-/Null-Defaults prüfen.

- **AC-13:** Given ein Journal mit einer beschädigten (nicht als JSON parsbaren) Zeile zwischen
  zwei gültigen Zeilen / When das Go-Aggregat es liest / Then wird die beschädigte Zeile
  übersprungen, die beiden gültigen Zeilen zählen weiter.
  - Test: Journaldatei mit einer kaputten Zwischenzeile präparieren, Aggregatfunktion aufrufen,
    `recent_count` muss die zwei gültigen Zeilen zeigen, kein Absturz.

- **AC-14:** Given zwei Kandidaten, deren schlechtester Wegpunkt-Abstand exakt auf der
  1-km-Meldegrenze bzw. deutlich darüber liegt / When die Melderegel angewendet wird / Then wird
  der Grenzfall (genau 1 km) gemeldet, der klar darüber liegende Fall nicht.
  - Test: Zwei Etappen-Fälle mit `best_dist` = 1000 m und z. B. 4000 m durchlaufen lassen,
    Journalzeilen-Anzahl 1 vs. 0 prüfen (Grenzwert-Wächter analog zum bestehenden AC-12-Muster in
    `test_track_resolution_legacy_trip.py`).

## Known Limitations

- Geprüft wird nur die Etappe des jeweiligen Zieldatums, nicht der ganze Trip —
  `backfill_stage_distances` arbeitet datumsbezogen; andere Etappen desselben Trips bekommen ihren
  Journal-Eintrag erst, wenn sie selbst als Ziel-Etappe eines Laufs aufgerufen werden.
- Der `_failed_lookups`-Cache wird nie geleert; nach einem Prozess-Neustart kann dieselbe Etappe
  erneut eine Journalzeile erzeugen (bestehendes Verhalten, unverändert von dieser Scheibe).
- Diese Scheibe liefert **keine** Anzeige für den Wanderer im Editor oder Briefing — das ist eine
  eigene Scheibe mit Schema- und Frontend-Anteil (zwei Schema-Gates, eigenes LoC-Budget).
- Der externe Monitor (`check-gregor20.sh`) wertet die neuen Status-Schlüssel noch nicht aus; das
  liegt in `henemm-infra` und ist nicht Teil dieser Scheibe.
- Der Grund `implausible_measurement` (Stelle 2) hat bewusst **keine** Dämpfung — ein dauerhaft
  kaputter Trip erzeugt bei der realen Alarmkadenz (alle 15 min) bis zu ~96 Journalzeilen pro Tag
  und kann damit den 24-h-Recent-Count des Betreiber-Aggregats dominieren. Gemessen im
  Adversary-Lauf (20 Aufrufe = 20 Zeilen). Bewusste Entscheidung nach Präzedenzfall
  `alert_anchor_rejected.jsonl`; eine Dämpfung wäre eine eigene Scheibe.
- Kein Fix für den separat gefundenen Defekt, dass Go (`naismith.go:124`) einen unplausiblen, aber
  positiven Wert benutzt statt zurückzufallen — das ist ein Rechenfehler, kein Sichtbarkeitsproblem,
  und gehört in ein eigenes Ticket.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR — diese Scheibe erfüllt die bestehende Folgepflicht aus **ADR-0018**
  wörtlich (Marker in Daten + wachsendes Health-Signal für einen neuen degradierbaren Datenpfad).
  Bindende Randbedingungen aus zwei weiteren ADRs gelten unverändert: **ADR-0003**
  (Mandantentrennung — das Journal liegt zwingend unter `data/users/<user_id>/`, nie global, nie
  `"default"`) und **ADR-0031** (dateibasierte Persistenz — JSONL-Append, kein neues
  Speichersystem).
- **Rationale:** Das bereits bestehende globale Journal `enrichment_calls.jsonl`
  (`src/providers/enrichment_health.py`) wurde bewusst **nicht** wiederverwendet: es kennt nur
  systemweite Pfad-Namen (`thunder`, `radar_nowcast`, …), nicht die einzelne betroffene Etappe. Der
  auslösende Fall #2070 — ein einzelner Trip degradiert wochenlang still, während andernorts
  laufend erfolgreiche Auflösungen passieren — wäre mit einem global nach `path` aggregierten
  Journal **nicht** gefangen worden, weil ein beliebiger erfolgreicher Lauf irgendeines Nutzers das
  Signal für alle überdeckt hätte. Das nutzerbezogene Muster aus `alert_briefing_anchor.py`
  (`record_alert_anchor_rejected`, bereits zweifach im Projekt umgesetzt: `corrupt_trips.json`
  #1262, `alert_anchor_rejected.jsonl` #1661) löst das strukturell: volle Details beim Nutzer, nur
  Zähler und Zeitstempel über die Grenze zum Betreiber-Aggregat.

## Changelog

- 2026-08-22: Initial spec created
- 2026-08-22 (nach der Staging-Messung): AC-12 traf den Wortlaut nur zur Hälfte. Der Endpoint
  meldet ohne laufende Serie `track_resolution_failure_streak_since` als **`null`**, nicht als
  leeren String — der Go-Handler legt den intern zurückgegebenen `""` nicht in die Antwort-Map
  (`briefing_health.go:179-188`), womit das Feld dem `null` seiner Nachbarn folgt. Der AC-Test
  prüfte die interne Hilfsfunktion, nicht den ausgelieferten JSON-Schlüssel — dieselbe Naht, die
  ADR-0018 sichtbar machen will, war im Nachweis selbst ungemessen. Die AC-Absicht (neutraler
  Leerwert, `recent_count=0`, kein Fehler) ist erfüllt; korrigiert wurde die **Beschreibung** in
  `docs/reference/api_contract.md`, nicht das Verhalten — auf `""` umzustellen bräche die
  Konsistenz mit `provider_error_*` und `alert_anchor_rejected_*`, auf die der Monitor in
  `henemm-infra` bereits rechnet.
