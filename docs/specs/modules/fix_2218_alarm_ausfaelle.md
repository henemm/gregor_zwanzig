---
entity_id: fix_2218_alarm_ausfaelle
type: module
created: 2026-10-08
updated: 2026-10-08
status: draft
version: "1.0"
tags: [observability, alerts, health, trip, compare]
---

# Alarm-Ausfälle nicht mehr stumm (Issue #2218, Scheibe B, Epic #2505)

## Approval

- [ ] Approved — PO (Henning)

## Purpose

Wenn der Wetterabruf für einen Alarm scheitert, bleibt das heute unsichtbar oder
geht im Dauerrauschen unter. Beim Trip-Alarm erzeugt die Meldung „No fresh weather
data" rund 1350 Treffer, weil ein legitim leeres Ergebnis (Etappe schon absolviert,
beginnt erst morgen) und ein echter Abruffehler in dieselbe leere Liste münden. Beim
Ortsvergleich-Alarm wird der Fehler eines einzelnen Ortes nur geloggt, ein dauerhaft
scheiternder Ort fällt still aus. Das Health-Journal zählt zudem nur je Pfad, nicht
je Trip oder Ort.

Diese Scheibe macht die Ausfälle für den Betreiber sichtbar (Health-Journal und
`/api/scheduler/status`), **ohne** zu ändern, ob oder wann alarmiert wird, und ohne
neue Nutzermeldung. Es betrifft alle vier Kanäle gleichermaßen nicht, weil nur die
Betreiber-Beobachtbarkeit erweitert wird.

Umfang: genau drei Einträge aus dem Sammel-Issue #2218 — **B1-09**, **B2-70**,
**C5-32**. Erweitert `fix_1581_enrichment_health` (Journal + Aggregator).

## Source

- **File:** `src/providers/enrichment_health.py` (MODIFY), `src/services/trip_alert.py`
  (MODIFY), `src/services/compare_alert.py` (MODIFY),
  `internal/scheduler/enrichment_health.go` (MODIFY)
- **Identifier:** `providers.enrichment_health.log_enrichment_call` (neues optionales
  Argument `unit`, neue Konstante `PATH_ALERT_FETCH = "alert_fetch"`),
  `services.trip_alert.TripAlertService._fetch_fresh_weather` und die Aufrufstelle
  `trip_alert.py` ~688, `services.compare_alert.CompareAlertService._detect_triggered_locations`
  (~525-551), `scheduler.aggregateEnrichmentCalls` / `scheduler.EnrichmentHealth`

**Schicht:** Python-Core (Schreiben), Go-API (Lesen/Aggregieren). Kein Frontend.

## Estimated Scope

- **LoC:** ca. 180-220 inkl. Tests (unter dem Limit 250)
- **Files:** 6 · **Acceptance Criteria:** 11
- **Effort:** medium

| Datei | Aktion | LoC (ca.) |
|---|---|---|
| `src/providers/enrichment_health.py` | MODIFY (Pfad-Konstante, Argument `unit`) | 10-15 |
| `src/services/trip_alert.py` | MODIFY (leer vs. gescheitert trennen, Journal, Warning entfällt im Normalfall) | 30-40 |
| `src/services/compare_alert.py` | MODIFY (Journal je Ort) | 15-20 |
| `internal/scheduler/enrichment_health.go` | MODIFY (`failed_units`) | 35-45 |
| `tests/test_alert_stumme_ausfaelle.py` | CREATE | 80-110 |
| `internal/scheduler/enrichment_health_test.go` | MODIFY (Tests `failed_units`, Altzeilen, zwei Nutzer) | 50-70 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root()` | intern | Journalpfad weiter bei JEDEM Aufruf frisch aufgelöst (Falle #1633) |
| `fix_1581_enrichment_health` | Spec (approved) | Journal-Format, Go-Aggregator, fail-soft; wird hier nur erweitert |
| `SegmentWeatherService.fetch_segment_weather` | intern | Quelle der Abruffehler je Segment |
| `_evaluate_one_location` | intern | Quelle der Ortsfehler |
| ADR-0018 „Fallback ohne Kaschieren" | Architektur | Fordert wachsendes Health-Signal je degradierbarem Pfad |

## Implementation Details

**1. Journal (`enrichment_health.py`, C5-32 Schreibseite):**
`log_enrichment_call(path, outcome, detail=None, unit=None)`. Das Feld `unit` wird
**nur** in die JSONL-Zeile geschrieben, wenn es gesetzt ist; Zeilen der bestehenden
Aufrufer bleiben byte-identisch zu heute. Neuer Pfad `PATH_ALERT_FETCH = "alert_fetch"`
(eigener Pfad, damit ein Alarm-Abruf-Ausfall nicht hinter einem gesunden Pfad wie
`radar_nowcast` verschwindet). Fail-soft bleibt: jeder Fehler wird geschluckt.

**2. Trip-Alarm (B1-09):** `_fetch_fresh_weather` unterscheidet intern drei Zahlen:
übersprungene Segmente (absolviert/morgen), versuchte Segmente, gescheiterte
Segmente. Die Rückgabe der Liste bleibt unverändert. Auswertung an der Aufrufstelle:

| Lage | Journal | Log |
|---|---|---|
| leer, 0 Versuche (alles legitim übersprungen) | **kein** Eintrag | nur `logger.debug` |
| Abruf gescheitert (mindestens ein Segment warf) | `alert_fetch`, `unavailable`, `unit = <user_id>/<trip_id>` | `logger.error` je Segment wie bisher; Dauer-`logger.warning("No fresh weather data …")` entfällt |
| Abruf erfolgreich (kein Segment warf, mindestens eines geliefert) | `alert_fetch`, `ok`, gleiche `unit` | — |
| Mischfall (ein Segment warf, ein anderes lieferte) | `alert_fetch`, `unavailable` (Teilausfall zählt als Ausfall), **kein** `ok` | `logger.error` je gescheitertem Segment |

`return False` bei leerem Ergebnis bleibt **exakt** (fail-closed): es ändert sich
nie, ob alarmiert wird. Wird `fresh_weather` von außen übergeben, wird nichts
gejournalt (es gab keinen Abruf).

**3. Ortsvergleich-Alarm (B2-70):** In `_detect_triggered_locations` schreibt der
bestehende `except` zusätzlich `alert_fetch`/`unavailable` mit
`unit = <user_id>/<preset_id>/<location_id>`; der Logeintrag bleibt. Eine ohne
Ausnahme beendete Ortsauswertung (Treffer oder kein Treffer) schreibt `ok` mit
derselben `unit`. Die Schleife läuft nach einem Fehler weiter, das Ergebnis
`(sent, failed)` der Presets bleibt unverändert — Presets werden **nicht**
fälschlich als `failed` gewertet.

**4. Go-Aggregator (C5-32 Leseseite):** Zusätzlich zur unveränderten Pfad-Ebene
(`last_attempt_at`, `last_success_at`, `last_fallback_at`, `last_fallback_detail`,
`self_throttled`) liefert jeder Pfad `failed_units`: Liste der Einheiten, deren
**neuester** Eintrag `unavailable` ist (aktuell scheiternd). Ein späterer `ok`-Eintrag
derselben `unit` entfernt sie. Gedeckelt auf 20 Einträge (neueste Ausfälle zuerst),
stabil sortiert. Zeilen ohne `unit` (Altzeilen, andere Pfade) werden weiter für die
Pfad-Ebene gelesen und tragen nichts zur Liste bei. Ein Pfad ohne scheiternde
Einheit liefert eine leere Liste `[]`, nie `null`.

## Expected Behavior

- **Input:** jeder Alarm-Abruflauf (Trip: ein Aufruf je Trip-Check; Ortsvergleich:
  ein Aufruf je Ort und Preset-Check).
- **Output:** JSONL-Zeilen in `diagnostics/enrichment_calls.jsonl` mit Pfad
  `alert_fetch`; `/api/scheduler/status` → `enrichment_health.alert_fetch.failed_units`
  nennt aktuell scheiternde Einheiten.
- **Side effects:** keine auf den fachlichen Ablauf. Alarmentscheidung, Versand,
  Drosselung, Rückgabewerte bleiben unverändert. Keine Nutzermeldung, kein neuer
  Kanal-Text.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Segmente alle bereits absolviert sind oder erst
  morgen beginnen / When der Alarm-Check läuft und die frische Wetterliste leer
  bleibt / Then entsteht KEIN Journal-Eintrag mit `unavailable` für den Pfad
  `alert_fetch` und kein Warn-Logeintrag „No fresh weather data" — der Normalfall
  ist kein Ausfall.

- **AC-2:** Given ein Trip mit einem laufenden Segment, dessen Wetterabruf eine
  Ausnahme wirft / When der Alarm-Check läuft / Then steht im Journal ein Eintrag
  mit Pfad `alert_fetch`, Ergebnis `unavailable` und einer `unit`, die Nutzer-ID
  und Trip-ID enthält, und der Check liefert weiterhin `False` (kein Alarm).

- **AC-3:** Given ein Trip, dessen Wetterabruf gelingt / When der Alarm-Check
  läuft / Then steht im Journal ein Eintrag `alert_fetch`/`ok` mit derselben `unit`
  wie im Fehlerfall, sodass ein späterer Erfolg einen früheren Ausfall dieser
  Einheit ablöst.

- **AC-4:** Given ein Ortsvergleich-Preset mit drei Orten, bei dem die Auswertung
  des mittleren Ortes eine Ausnahme wirft / When `_detect_triggered_locations`
  läuft / Then steht für genau diesen Ort ein Eintrag `alert_fetch`/`unavailable`
  mit `unit` aus Nutzer-ID, Preset-ID und Ort-ID, die beiden anderen Orte werden
  weiter ausgewertet (mit `ok`-Einträgen), und das Preset wird nicht als
  gescheitert gezählt.

- **AC-5:** Given die Journaldatei enthält für eine Einheit erst einen
  `unavailable`-, danach einen `ok`-Eintrag / When der Go-Aggregator
  `enrichment_health` bildet / Then fehlt diese Einheit in `failed_units`; liegt
  der `unavailable`-Eintrag dagegen zeitlich NACH dem `ok`, steht sie darin.

- **AC-6:** Given eine Journaldatei mit Altzeilen ohne Feld `unit` (z. B. `thunder`,
  `radar_nowcast`) neben neuen Zeilen mit `unit` / When der Aggregator läuft /
  Then bleiben `last_attempt_at`, `last_success_at`, `last_fallback_at`,
  `last_fallback_detail` und `self_throttled` jedes Pfades unverändert gegenüber
  dem Stand vor dieser Änderung, und Altzeilen führen weder zu einem Fehler noch zu
  einem Eintrag in `failed_units`.

- **AC-7:** Given ein Alarm-Check, bei dem der Abruf scheitert oder leer ist /
  When der Check vor und nach dieser Änderung mit identischen Eingaben läuft /
  Then sind Rückgabewert, gesendete Alarme und Drosselungszustand identisch
  (fail-closed bleibt: leeres Wetter ⇒ kein Alarm); nur das Journal hat
  zusätzliche Einträge.

- **AC-8:** Given zwei verschiedene Nutzer A und B mit je einem scheiternden Trip
  bzw. Ort gleicher Bezeichnung / When beide Alarm-Läufe Einträge schreiben und der
  Aggregator liest / Then trägt jede `unit` ihre eigene Nutzer-ID als Präfix, und
  ein `ok`-Eintrag von Nutzer A löscht die Einheit von Nutzer B nie aus
  `failed_units` (und umgekehrt).

- **AC-9:** Given das Journal ist nicht beschreibbar (Zielpfad ist ein Verzeichnis)
  / When ein Trip- oder Ortsvergleich-Alarmlauf mit Abruffehler durchläuft / Then
  propagiert keine Ausnahme aus dem Journalschreiben, und Rückgabe sowie Versand
  entsprechen dem Lauf ohne Journalfehler (fail-soft bleibt gewahrt).

- **AC-10:** Given mehr als 20 gleichzeitig scheiternde Einheiten im Journal /
  When der Aggregator `failed_units` bildet / Then enthält die Liste höchstens 20
  Einträge (die zuletzt gescheiterten), und ein Pfad ohne scheiternde Einheit
  liefert eine leere Liste statt `null`.

- **AC-11:** Given ein Trip mit zwei laufenden Segmenten, von denen der Abruf des
  einen wirft und der des anderen liefert / When der Alarmlauf die frischen
  Wetterdaten holt / Then steht genau ein `unavailable`-Eintrag mit der Trip-`unit`
  im Journal und kein `ok`-Eintrag, und die gelieferten Daten werden wie bisher
  weiterverwendet (Alarmentscheidung unverändert).

## Tests

Verhaltenstests ohne Mock-Theater; geprüft wird die echte Journaldatei.

- **`tests/test_alert_stumme_ausfaelle.py` (Python, Kern-Schicht):** nutzt die
  bestehende Isolations-Fixture für die Datenwurzel (tmp, `get_data_root()` zeigt
  dorthin) und liest nach dem Lauf die echte JSONL-Datei. Provider-Abruf wird nur
  an der Systemgrenze ersetzt (Fake-Provider, der wirft bzw. liefert); die zu
  testende Trennlogik läuft echt. Deckt AC-1 bis AC-4, AC-11, AC-7 (Vorher-/Nachher-
  Vergleich der Rückgabe), AC-8 (Journal mit zwei Nutzern), AC-9 (Journalpfad als
  Verzeichnis). Gegenprobe-Pflicht: ein Test, der rot wird, wenn „leer + 0 Versuche"
  fälschlich als Ausfall gebucht wird (AC-1), und einer für „Abruf gescheitert wird
  als Normalfall behandelt" (AC-2).
- **`internal/scheduler/enrichment_health_test.go` (Go):** neue Tests neben den
  bestehenden, mit echter JSONL-Datei im Temp-Verzeichnis (Muster der vorhandenen
  Tests dort). Deckt AC-5, AC-6 (Altzeilen), AC-8 (zwei Nutzer), AC-10 (Deckel,
  leere Liste).
- **Mutations-Gegenprobe (Pflicht, Adversary):** (a) Normalfall-Prüfung „0
  Versuche" entfernen ⇒ AC-1-Test rot; (b) `ok` löscht Einheit nicht ⇒ AC-5 rot;
  (c) Nutzer-Präfix aus `unit` entfernen ⇒ AC-8 rot; (d) Preset bei Ortsfehler als
  `failed` werten ⇒ AC-4 rot. Per String-Ersetzung mit externer Sicherungskopie,
  nie `git checkout/stash/reset`.

## Known Limitations

- Das Journal bleibt append-only ohne Rotation (wie in #1581).
- Die Aggregation über `failed_units` bewertet nur den neuesten Eintrag je
  Einheit, keine Mindestdauer des Ausfalls; Schwellen bildet die externe
  Auswertung.
- Der Status-Endpoint ist token-gesperrt (nur Betreiber, `X-GZ-Status-Token`);
  deshalb dürfen `unit`-Werte die Nutzer-ID als Präfix tragen. Würde der Endpoint
  je für Nutzer geöffnet, müsste dieser Punkt neu bewertet werden.

## Out of Scope

- **Monitor-Skript:** Die Auswertung in `henemm-infra/scripts/check-gregor20.sh`
  (z. B. EXT_FAIL, wenn eine Einheit länger als `ENRICHMENT_MAX_AGE_H` in
  `failed_units` steht) ist ausdrücklich NICHT Teil dieser Scheibe, sondern ein
  Folgeschritt in `henemm-infra`. Das Skript bleibt kompatibel, weil die
  Pfad-Ebene unverändert ist.
- Keine Nutzermeldung, kein neuer Kanal-Text.
- Weitere Einträge aus #2218, die offen bleiben: **C5-02, C5-15, C5-37, B2-71,
  C5-47, C5-53**.

## Architektur-Entscheidung (ADR)

**ADR-Nr.:** keine neue — Umsetzung von ADR-0018

**Rationale:** Umsetzung von ADR-0018 (Fallback ohne Kaschieren) für die
Alarm-Abrufe. Entscheidungen: eigener Pfad `alert_fetch` statt Wiederverwendung
von `radar_nowcast`; optionales Feld `unit` statt je Einheit eigener Pfadnamen
(hält das Pfad-Vokabular klein, Altzeilen bleiben gültig); Einheitenliste in Go
statt Schwellenentscheidung (Rohdaten, wie in #1581).

## Changelog

- 2026-10-08: Initial spec created (Issue #2218 Scheibe B, Analyse
  `docs/context/fix-2218-alarm-stumme-ausfaelle.md`).
- 2026-10-08: AC-11 (Mischfall: Teilausfall zählt als Ausfall) ergänzt nach PO-Briefing-Anmerkung.
