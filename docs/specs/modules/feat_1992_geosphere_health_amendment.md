---
entity_id: feat_1992_geosphere_health_amendment
type: module
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [observability, providers, health, geosphere]
---

# GeoSphere Health Journal Amendment (SNOWGRID, Gewitter-Zusatzquelle, Radar-Nowcast/INCA)

## Approval

- [ ] Approved

## Purpose

Drei GeoSphere-Datenpfade fallen bei echtem Ausfall fail-soft still aus, ohne dass das
im bestehenden `enrichment_health`-Journal (#1581, `docs/specs/modules/fix_1581_enrichment_health.md`,
bereits geliefert und in `main`) sichtbar wird: SNOWGRID (Schneetiefe), die additive
Gewitter-Zusatzquelle (cape/cin über `geosphere` in `DE_ALPEN`, #1758) und der
INCA-spezifische Anteil des Radar-Nowcasts. Diese Spec ist ein **Amendment** — sie
schließt drei Lücken **innerhalb** des bestehenden Journals, baut kein neues.

## Source

- **File:** `src/providers/geosphere.py` (MODIFY), `src/providers/enrichment_health.py`
  (MODIFY), `src/providers/openmeteo.py` (unverändert — s. Architektur-Entscheidung 1),
  `src/providers/thunder_enrichment.py` (MODIFY), `src/services/radar_service.py`
  (MODIFY)
- **Identifier:** `GeoSphereProvider.fetch_snowgrid`/`fetch_combined` (geosphere.py),
  `providers.enrichment_health.PATH_SNOWGRID`/`PATH_THUNDER_ADDITIVE` (neu),
  `thunder_enrichment._fetch_lightning_density` (additiver Zweig, ~589-608),
  `radar_service.RadarService._fetch_geosphere_inca`/`get_nowcast`

**Schicht:** ausschließlich Python-Core (`src/providers/`, `src/services/`).
**Kein Go-Code betroffen** — s. Architektur-Entscheidung 3 (Korrektur der Analyse).
Kein Frontend betroffen.

## Estimated Scope

- **LoC:** ~90-120 Produktionscode + ~320-420 Tests ≈ **~450 gesamt**. Kleiner als
  #1581 (dort 900), aber über dem Standard-Limit 250 — `loc_limit_override` auf
  **500** empfohlen.
- **Files:** 5 Produktionsdateien (davon `openmeteo.py` NICHT geändert, s. u.) + 3-4
  neue/erweiterte Testdateien
- **Effort:** medium

| Datei | Aktion | LoC (ca.) |
|---|---|---|
| `src/providers/enrichment_health.py` | MODIFY (2 neue Konstanten + Kommentar) | 10-15 |
| `src/providers/geosphere.py` | MODIFY (`fetch_snowgrid` Except erweitern + journalen; `fetch_combined` eigenes try/except) | 25-35 |
| `src/providers/thunder_enrichment.py` | MODIFY (additiver Zweig journalt) | 10-15 |
| `src/services/radar_service.py` | MODIFY (neues Flag + Fallback-Unterscheidung in `get_nowcast`) | 10-15 |
| `tests/tdd/test_snowgrid_enrichment_health.py` | CREATE | 100-140 |
| `tests/tdd/test_thunder_additive_enrichment_health.py` | CREATE | 90-130 |
| `tests/tdd/test_radar_inca_fallback_journal.py` | CREATE | 70-100 |
| `internal/scheduler/enrichment_health_test.go` | KEINE Änderung nötig (s. AC-8) | 0 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.enrichment_health.log_enrichment_call` | intern, bestehend (#1581) | Gemeinsamer, bereits fail-soft abgesicherter Schreibweg — wird nur mit neuen `path`-Werten aufgerufen, keine Änderung an der Funktion selbst |
| `internal.scheduler.aggregateEnrichmentCalls`/`EnrichmentHealth` | intern, bestehend (#1581) | Gruppiert bereits generisch nach `entry.Path` als String — kein Enum, kein `switch` über erlaubte Pfadwerte (verifiziert, s. AC-8) |
| `providers.thunder_routing.thunder_providers_for` | intern, bestehend | Liefert für `DE_ALPEN` `("de_direct", "geosphere")` — `geosphere` ist die einzige additive Quelle, nie Primärquelle |
| ADR-0018 „Modell-Fallback ohne Kaschieren" | Architektur | Deckt bereits alle drei hier geschlossenen Lücken ab, keine neue Grundsatzentscheidung nötig |
| `docs/specs/modules/fix_1581_enrichment_health.md` | Spec (Vorgänger) | Vorbild für Format, Outcome-Vokabular (`ok`/`fallback`/`unavailable`/`self_throttled`) und Choke-Point-Prinzip |

## Implementation Details

### 1. Neue Journal-Pfade (`src/providers/enrichment_health.py`)

```python
PATH_THUNDER = "thunder"
PATH_THUNDER_ADDITIVE = "thunder_additive"   # neu
PATH_RADAR_NOWCAST = "radar_nowcast"
PATH_SNOWGRID = "snowgrid"                    # neu
```

`PATH_THUNDER_ADDITIVE` ist **absichtlich getrennt** von `PATH_THUNDER`, nicht
`detail`-Varianten desselben Pfads — s. Architektur-Entscheidung 2.

### 2. SNOWGRID (`src/providers/geosphere.py::fetch_snowgrid`, Zeilen 365-375)

`fetch_snowgrid` ist der EINE Choke-Point für BEIDE Aufrufer (`fetch_combined` als
GeoSphere-Primärpfad und `openmeteo.py::_enrich_snow` als Best-effort-Anreicherung,
wenn Open-Meteo Primärquelle ist) — journalen genau hier deckt beide automatisch ab,
ohne doppelte Einträge:

```python
try:
    ...
    return self._parse_snowgrid_response(data)
except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as e:
    log_enrichment_call(PATH_SNOWGRID, OUTCOME_UNAVAILABLE, detail=str(e)[:200])
    return None, None
```

Bei Erfolg (nach `return self._parse_snowgrid_response(data)`, aber vor dem
`return`) `log_enrichment_call(PATH_SNOWGRID, OUTCOME_OK)`.

Das Except wird von `httpx.HTTPStatusError` auf `(HTTPStatusError, TimeoutException,
RequestError)` erweitert — dieselbe Klasse, die `fetch_thunder_signals_named` schon
fängt (Zeile 424). Das bleibt **fail-soft** (kein Verhaltenswechsel: weiterhin
`return None, None`), schließt aber eine echte, heute bestehende Lücke: ein Timeout
oder Verbindungsfehler (nicht `HTTPStatusError`) propagiert HEUTE unverändert durch
`fetch_snowgrid` hindurch (s. Punkt 3).

### 3. Regressions-Leitplanke (`fetch_combined`, ~Zeile 597) — WICHTIGSTES AC

`fetch_combined` ruft `fetch_snowgrid` heute **ungeschützt** auf. Selbst nach der
Erweiterung in Punkt 2 bleibt ein Restrisiko: ein Fehler INNERHALB von
`_parse_snowgrid_response` (z. B. `KeyError`/`ValueError` bei unerwarteter
API-Antwortform) ist kein `httpx`-Fehler und wird von KEINEM der beiden Excepts
gefangen — er propagiert durch `fetch_combined` bis in `fetch_forecast`s äußeres
`except httpx.HTTPStatusError`/`except httpx.RequestError` (Zeilen 268-273), die ihn
ebenfalls nicht fangen, und crasht damit die **komplette Grundvorhersage** wegen
eines Fehlers in der optionalen Schneeanreicherung.

```python
if include_snow and ts.data:
    try:
        snow_depth_cm, swe_kgm2 = self.fetch_snowgrid(lat, lon)
    except Exception as e:
        log_enrichment_call(PATH_SNOWGRID, OUTCOME_UNAVAILABLE, detail=f"combined:{e}"[:200])
        snow_depth_cm, swe_kgm2 = None, None
    if snow_depth_cm is not None:
        ...
```

Das ist ein bewusst **breiter** `except Exception` als zweite Verteidigungslinie
(Defense-in-Depth) zusätzlich zum spezifischen `httpx`-Except in `fetch_snowgrid`
selbst — die Grundvorhersage darf UNTER KEINEN Umständen an SNOWGRID scheitern, egal
welche Fehlerklasse.

### 4. Additive Gewitter-Zusatzquelle (`thunder_enrichment.py::_fetch_lightning_density`, ~589-608)

Die `for quelle in zusatz:`-Schleife journalt heute NICHTS — weder Erfolg noch
Fehlschlag. `PATH_THUNDER_ADDITIVE` mit `detail=quelle` (nicht `PATH_THUNDER`, s.
Architektur-Entscheidung 2):

```python
for quelle in zusatz:
    if quelle == bereits_befragt:
        continue
    try:
        eintraege = _hole_eintraege(quelle, location, von, bis)
    except Exception:
        logger.warning("Zusatzquelle '%s' fehlgeschlagen", quelle, exc_info=True)
        log_enrichment_call(PATH_THUNDER_ADDITIVE, OUTCOME_UNAVAILABLE, quelle)
        continue
    if not any(werte for _feld, werte in eintraege):
        log_enrichment_call(PATH_THUNDER_ADDITIVE, OUTCOME_OK, quelle)
        continue
    gefuellt = _wende_eintraege_an(reihe, eintraege, basis)
    log_enrichment_call(PATH_THUNDER_ADDITIVE, OUTCOME_OK, quelle)
    if gefuellt:
        logger.info(...)
```

`OUTCOME_OK` auch bei leerer-aber-gültiger Antwort — dieselbe Regel wie bei der
Primärquelle (#1581, „kein Gewitter in Sicht" ist ein Erfolg).

### 5. Radar-Nowcast — INCA-spezifischer Fehlschlag (`radar_service.py`)

`_derive_result`s `data_unavailable`-Formel (Zeilen 583-593) bleibt **unverändert**
(Architektur-Entscheidung 4 — sie treibt Alarm-Unterdrückung, s.
`test_radar_upstream_failure.py`, und ist über `and not frames` bereits korrekt: sie
darf nur True sein, wenn am Ende wirklich keine Frames vorliegen). Stattdessen ein
neues, eigenes Flag, das den bestehenden Journal-Aufruf in `get_nowcast()`
(bereits aus #1581 Scheibe 2 vorhanden, Zeilen ~225-241) erweitert:

```python
# Reset (an beiden bestehenden Reset-Stellen, Zeilen 138-139 und 186-187):
self._inca_unavailable_this_call = False

# In _fetch_geosphere_inca(), except-Zweig (Zeile ~399-400):
except Exception as e:
    logger.warning(f"GeoSphere INCA failed, falling back: {e}")
    self._inca_unavailable_this_call = True
    return []

# In get_nowcast(), bestehender Journal-Block erweitert:
if result.throttled:
    log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_SELF_THROTTLED)
elif result.data_unavailable:
    log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_UNAVAILABLE)
elif getattr(self, "_inca_unavailable_this_call", False):
    log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_FALLBACK, source)
else:
    log_enrichment_call(PATH_RADAR_NOWCAST, OUTCOME_OK)
```

`_within_inca(lat, lon)` = False (Ort außerhalb der INCA-Bbox) → `_fetch_geosphere_inca`
wird nie aufgerufen, Flag bleibt `False`, unverändertes Verhalten.

## Expected Behavior

- **Input:** jeder Abruf von SNOWGRID (`fetch_snowgrid`, über beide Aufrufer), der
  additiven Gewitter-Zusatzquelle (`geosphere` in `DE_ALPEN`) und des
  INCA-Anteils des Radar-Nowcasts, unabhängig vom Ausgang.
- **Output:** zusätzliche JSONL-Zeilen in `data/diagnostics/enrichment_calls.jsonl`
  mit `path="snowgrid"` bzw. `path="thunder_additive"`; für `path="radar_nowcast"`
  zusätzlich der Ausgang `outcome="fallback"` (bisher nie geschrieben). Beide neuen
  `path`-Werte erscheinen automatisch als eigene Schlüssel unter
  `enrichment_health` in `/api/scheduler/status`, OHNE Go-Code-Änderung (AC-8).
- **Side effects:** keine auf den fachlichen Datenfluss — Schneetiefe,
  Gewittersignale und Radar-Nowcast-Ergebnisse bleiben unverändert, auch bei
  nicht beschreibbarem Journal (Fail-soft, geerbt von `log_enrichment_call`).
  `PATH_THUNDER`/`PATH_RADAR_NOWCAST`-Einträge der Primärpfade bleiben unverändert
  (außer dem neuen `fallback`-Ausgang bei Radar, AC-6).

## Acceptance Criteria

- **AC-1:** Given SNOWGRID antwortet mit einem echten Fehler (`httpx.HTTPStatusError`,
  `TimeoutException` oder `RequestError`) / When `fetch_snowgrid()` durchläuft
  (egal ob aufgerufen über `fetch_combined` oder `openmeteo.py::_enrich_snow`) /
  Then wird eine Journalzeile mit `path="snowgrid"`, `outcome="unavailable"`
  geschrieben, und die Funktion liefert weiterhin `(None, None)` (fail-soft,
  unverändertes Rückgabeverhalten).
  - Test: Fake-Provider/HTTP-Mock, der `fetch_snowgrid` mit je einer der drei
    Exception-Klassen scheitern lässt (3 Fälle, auch `TimeoutException` — die
    heute NICHT gefangen wird), danach Journal auf `path="snowgrid"`/`unavailable`
    prüfen UND den Rückgabewert `(None, None)` verifizieren.

- **AC-2:** Given SNOWGRID antwortet normal / When `fetch_snowgrid()` durchläuft /
  Then wird eine Journalzeile mit `path="snowgrid"`, `outcome="ok"` geschrieben.
  - Test: Erfolgreichen Abruf faken, Journal auf genau eine `ok`-Zeile für
    `path="snowgrid"` prüfen, keine `unavailable`-Zeile.

- **AC-3 (Regressions-Leitplanke, wichtigstes AC):** Given `fetch_snowgrid` wirft
  eine beliebige Exception (auch eine NICHT-httpx-Exception, z. B. ein simulierter
  Parsing-Fehler) / When `fetch_combined()` bzw. `fetch_forecast()` durchläuft /
  Then liefert der Aufruf trotzdem ein `NormalizedTimeseries`-Ergebnis mit den
  übrigen Wetterdaten (ohne Schneefelder), OHNE dass eine Exception propagiert —
  die Grundvorhersage scheitert NIEMALS an einem SNOWGRID-Fehler.
  - Test: `fetch_snowgrid` per Monkeypatch/Mock so präparieren, dass es eine
    generische `Exception` wirft (nicht nur eine `httpx`-Klasse), `fetch_combined()`
    UND `fetch_forecast()` aufrufen, beide liefern ein Ergebnis mit
    `ts.data` befüllt und `snow_depth_cm is None` auf allen Punkten — kein
    `ProviderRequestError`, keine unbehandelte Exception. Mutations-Gegenprobe:
    das `try/except` um den `fetch_snowgrid`-Aufruf in `fetch_combined` entfernen
    → genau dieser Test wird rot (Nachweis, dass er die Leitplanke tatsächlich
    bewacht, nicht nur den bereits vorhandenen inneren Except von
    `fetch_snowgrid`).

- **AC-4:** Given die additive Gewitter-Zusatzquelle (`geosphere` in `DE_ALPEN`,
  #1758) scheitert (`_hole_eintraege` wirft) / When
  `_fetch_lightning_density()` die Zusatzquellen-Schleife durchläuft / Then wird
  eine Journalzeile mit `path="thunder_additive"`, `outcome="unavailable"`,
  `detail="geosphere"` geschrieben — getrennt von `path="thunder"` (Primärquelle).
  Heute hinterlässt dieser Fall NICHTS außer einem `logger.warning`.
  - Test: additive Quelle scheitern lassen (Primärquelle `de_direct` erfolgreich),
    danach Journal auf die `thunder_additive`-Zeile prüfen UND verifizieren, dass
    KEINE zusätzliche Zeile unter `path="thunder"` für dasselbe Ereignis entsteht
    (Trennungsnachweis).

- **AC-5:** Given die additive Gewitter-Zusatzquelle liefert (mit oder ohne
  gefüllte Werte) / When die Zusatzquellen-Schleife durchläuft / Then wird eine
  Journalzeile mit `path="thunder_additive"`, `outcome="ok"`, `detail="geosphere"`
  geschrieben, und die Primärquelle (`path="thunder"`) bleibt in Anzahl und Inhalt
  ihrer Journalzeilen unverändert zum Stand ohne diese Änderung.
  - Test: additive Quelle erfolgreich (einmal mit gefüllten, einmal mit leeren
    Werten) durchlaufen lassen, `thunder_additive`/`ok` in beiden Fällen prüfen;
    Regressionsvergleich der `thunder`-Zeilenzahl vor/nach der Änderung.

- **AC-6:** Given der Radar-Nowcast fällt für einen INCA-zuständigen Ort auf eine
  andere Quelle zurück (INCA-Abruf scheitert, aber `_fetch_frames_with_fallback`
  findet danach z. B. ICON-D2 mit Frames) / When `get_nowcast()` den Miss-Zweig
  durchläuft / Then wird eine Journalzeile mit `path="radar_nowcast"`,
  `outcome="fallback"`, `detail="ICON-D2"` geschrieben — NICHT `outcome="ok"`.
  Heute erscheint dieser Fall identisch zu einem gesunden INCA-Abruf.
  - Test: `_fetch_geosphere_inca` scheitern lassen (Exception in der internen
    `fetch_nowcast`-Kette), `_fetch_icon_d2` erfolgreich faken, Journal auf
    `fallback`/`detail="ICON-D2"` statt `ok` prüfen. Gegenprobe: ohne die
    Änderung (Flag/`elif`-Zweig per String-Ersetzung entfernt) schreibt derselbe
    Testaufbau `outcome="ok"` — der Test muss genau daran rot werden.

- **AC-7:** Given INCA liefert selbst erfolgreich Frames (`source="INCA"`) / When
  `get_nowcast()` durchläuft / Then bleibt die Journalzeile unverändert
  `outcome="ok"` (Regressionsschutz für das #1581-Verhalten — dieses AC stellt
  sicher, dass die neue `elif`-Verzweigung den bisherigen Erfolgsfall nicht
  versehentlich in `fallback` verwandelt).
  - Test: INCA erfolgreich faken (kein Fallback nötig), Journal auf `ok` prüfen,
    `_inca_unavailable_this_call` bleibt `False`.

- **AC-8:** Given zwei neue `path`-Werte (`snowgrid`, `thunder_additive`) tauchen
  im Journal auf, OHNE dass `internal/scheduler/enrichment_health.go` geändert
  wurde / When `/api/scheduler/status` abgefragt wird / Then erscheinen beide
  automatisch als eigene Schlüssel unter `enrichment_health`, mit denselben
  Rohdaten-Feldern (`last_attempt_at`/`last_success_at`/`last_fallback_at`/
  `self_throttled`) wie `thunder`/`radar_nowcast`. Beweist, dass der bestehende
  Go-Aggregator bereits generisch über `path` gruppiert (kein geschlossenes
  Vokabular, kein `switch`) — korrigiert die ursprüngliche Analyse-Annahme, ein
  Go-Gegenstück sei nötig.
  - Test: Journal-Datei direkt mit synthetischen Zeilen für `path="snowgrid"`
    und `path="thunder_additive"` befüllen (Python-Seite unverändert lassen),
    bestehenden Go-Testaufbau (`enrichmentLine`/`enrichmentEntry` aus
    `enrichment_health_test.go`) wiederverwenden und beide neuen Schlüssel im
    Aggregat nachweisen — kein Code in `enrichment_health.go` wird dafür
    angefasst.

## Known Limitations

- **`at_direct`-Fallback (ADR-0047, `openmeteo.py:1091-1096`) bleibt außerhalb des
  Scopes.** Ein Fehlschlag dort eskaliert bereits sichtbar (`raise last_error`),
  kein stiller Ausfall im Sinne dieses Tickets; #1581 hatte GeoSphere hier bewusst
  ohne Vertretungs-Eintrag gelassen — das bleibt unverändert.
- **Schwellenwert-Entscheidungen (wie lange gilt ein Ausfall als kritisch) bleiben
  außerhalb des Codes**, wie bei #1581 — Aufgabe des externen Monitorings
  (`henemm-infra/check-gregor20.sh`). `path="snowgrid"` und `path="thunder_additive"`
  sind fachlich NICHT briefing-kritisch (analog `radar_nowcast`); Empfehlung fürs
  externe Skript: langes Frischefenster, EXT-FAIL statt CORE.
- **`fetch_thunder_signals_named` und `fetch_nowcast` in `geosphere.py` selbst
  bekommen KEINE eigene Journal-Anbindung** (obwohl die ursprüngliche Analyse das
  vorschlug) — ihre einzigen Aufrufer (`thunder_enrichment.py` und
  `radar_service.py::get_nowcast()`) journalen bereits an einem gemeinsamen,
  choke-point-nahen Ort (Primärquelle seit #1581, additiv und INCA-Fallback neu in
  dieser Spec). Ein zweiter Journal-Aufruf auf Provider-Ebene würde für dasselbe
  logische Ereignis eine doppelte Zeile erzeugen und `last_attempt_at` künstlich
  verdoppeln, ohne zusätzliche Beobachtbarkeit zu gewinnen.
- **`_derive_result()`s `data_unavailable`-Formel bleibt unangetastet.** Sie treibt
  die Alarm-Unterdrückung (`trip_alert.py`, `test_radar_upstream_failure.py`) und
  ist für den Fall „am Ende liegen wirklich keine Frames vor" bereits korrekt. Die
  INCA-spezifische Beobachtbarkeit läuft bewusst über einen separaten Pfad
  (`outcome="fallback"`), nicht über eine Änderung dieser Formel — eine Änderung
  dort hätte das Risiko, den bestehenden, gut getesteten Alarm-Unterdrückungspfad
  zu verändern, obwohl das fachlich nicht nötig ist (Fallback-Frames sind nutzbare
  Daten, kein Ausfall im Sinne von `data_unavailable`).
- **`enrichment_calls.jsonl` bleibt append-only ohne Rotation**, wie in #1581
  festgelegt — unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue ADR — Amendment zu ADR-0018 (bestehender Grundsatz
  „wachsendes Health-Signal für jeden degradierbaren Pfad" deckt alle drei Lücken
  bereits ab) und faktische Fortsetzung der in #1581 getroffenen Entscheidungen
  (kein eigenes ADR-Dokument für #1581 selbst — Amendment lief über ADR-0047).
- **Rationale:**
  1. **SNOWGRID journalt an EINEM Choke-Point (`fetch_snowgrid` selbst), nicht an
     beiden Aufrufern.** `openmeteo.py::_enrich_snow` bleibt unverändert — sein
     `except Exception: pass` fängt nach dieser Änderung realistisch nur noch
     Bugs im Anreicherungs-Glue-Code (`_stamp_snow`), NICHT mehr echte
     SNOWGRID-Fehlschläge (die journalen bereits vorher in `fetch_snowgrid`
     selbst, ohne Exception zu propagieren). Das weicht von der ursprünglichen
     Analyse ab (die eine zweite Journal-Stelle in `openmeteo.py` vorschlug) —
     eine zweite Stelle hätte für denselben SNOWGRID-Abruf potenziell doppelt
     journalt oder wäre inkonsistent leer geblieben, je nachdem welcher der
     beiden `except`-Blöcke zuerst greift.
  2. **`thunder_additive` ist ein EIGENER Pfad, nicht `detail` unter
     `thunder`.** Der Go-Aggregator bildet pro `path` genau EIN
     `last_success_at`. Würde die additive Quelle unter `path="thunder"`
     mitschreiben, könnte ein Erfolg der PRIMÄRQUELLE (`de_direct`) einen
     zeitgleichen Ausfall der additiven GeoSphere-Quelle im Aggregat
     überdecken — genau die Vermengung, die dieses Ticket beheben soll. Ein
     eigener Pfad macht GeoSphere-additive-Ausfälle unabhängig von der
     Primärquelle sichtbar.
  3. **Keine Änderung an `internal/scheduler/enrichment_health.go` nötig** —
     verifiziert: `aggregateEnrichmentCalls()` gruppiert bereits generisch nach
     `entry.Path` als freiem String (keine Konstanten-Liste, kein `switch` über
     erlaubte Pfadwerte; die vorhandenen `enrichmentOutcome*`-Konstanten
     beziehen sich auf `outcome`, nicht auf `path`). Ein neuer `path`-Wert
     erscheint automatisch als zusätzlicher Schlüssel im
     `EnrichmentHealth()`-Ergebnis. Die ursprüngliche Analyse ging von einem
     „geschlossenen Vokabular" aus — das trifft für `outcome` zu (dort SIND es
     feste Konstanten), aber nicht für `path`. AC-8 belegt das explizit.
  4. **INCA-Fallback nutzt das bestehende `outcome="fallback"`-Vokabular**, statt
     ein neues Flag in `NowcastResult`/`_derive_result` einzuführen. Das
     vermeidet jede Berührung der bereits ausführlich getesteten
     `data_unavailable`-Formel (Alarm-Unterdrückung) und ist konsistent mit dem
     bereits für `PATH_THUNDER` etablierten Muster „Primärquelle fiel aus, eine
     Ersatzquelle hat geliefert" = `fallback`.

## Changelog

- 2026-08-20: Initial spec created (Issue #1992, Analyse
  `docs/context/feat-1992-geosphere-health-journal.md`). Drei Abweichungen von der
  Analyse dokumentiert: (a) kein Go-Code nötig (Aggregator bereits generisch über
  `path`), (b) `geosphere.py::fetch_thunder_signals_named`/`fetch_nowcast` bekommen
  KEINE eigene Journal-Anbindung (Choke-Point liegt bereits beim jeweiligen
  Aufrufer), (c) INCA-Beobachtbarkeit läuft über das bestehende
  `outcome="fallback"`-Vokabular statt über eine Erweiterung von
  `_derive_result()`s `data_unavailable`-Formel.
