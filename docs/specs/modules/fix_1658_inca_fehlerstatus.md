---
entity_id: fix_1658_inca_fehlerstatus
type: module
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.0"
tags: [observability, providers, radar]
---

# INCA-Fehlerstatus wird nicht mehr verschluckt (Issue #1658, Scheibe S2)

## Approval

- [ ] Approved

## Purpose

`fetch_nowcast()` verschluckt heute jeden HTTP-Fehlerstatus des INCA-Nowcast-Abrufs
lautlos (`return None`). Der einzige Aufrufer steigt daraufhin über einen frühen
`return []` aus, ohne das bestehende Ausfall-Merkzeichen zu setzen — die zentrale
Gesundheitsbuchung aus #1581 bucht einen echten INCA-Ausfall dadurch fälschlich als
`ok`. Diese Spec macht den Fehlerstatus sichtbar, ohne den bestehenden
Buchungsmechanismus zu verdoppeln.

## Source

- **File:** `src/providers/geosphere.py` (MODIFY, `fetch_nowcast`),
  `src/services/radar_service.py` (MODIFY, Warn-Logzeile in `_fetch_geosphere_inca`)
- **Identifier:** `providers.geosphere.GeoSphereProvider.fetch_nowcast`
  (Zeilen 477-496), `services.radar_service.RadarNowcastService._fetch_geosphere_inca`
  (Zeilen 736-769)

**Schicht:** Python-Core (`src/providers/`, `src/services/`). Kein Frontend, keine
Go-API betroffen — die Leseseite (`internal/scheduler/enrichment_health.go`,
`/api/scheduler/status`) existiert bereits (#1581) und liest weiterhin dasselbe
Merkzeichen; diese Scheibe ändert nur, ob das Merkzeichen im Fehlerstatus-Fall
überhaupt gesetzt wird.

## Estimated Scope

- **LoC:** ~15-25 (Produktivcode) + Tests
- **Files:** 2 Produktivdateien + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.base.ProviderRequestError` | intern (bereits vorhanden, `base.py:175-187`) | Trägt einen optionalen `status_code`; wird hier für den INCA-Fehlerstatus verwendet statt eines neuen Ausnahmetyps |
| `services.radar_service.RadarNowcastService._fetch_geosphere_inca` (`except Exception`, Zeilen 766-769) | intern, bestehend | Fängt die durchgereichte Ausnahme bereits korrekt ab und setzt `_inca_unavailable_this_call = True` — wird durch diese Scheibe nur ERREICHBAR gemacht, nicht verändert |
| `services.radar_service.RadarNowcastService.get_nowcast` (`elif`-Kette, Zeilen 534-541) | intern, bestehend, GESCHÜTZT | Die zentrale Bewertung bucht bereits korrekt `fallback` vs. `ok` vs. `unavailable`, sobald das Merkzeichen zuverlässig gesetzt wird — bleibt unverändert |
| `providers.enrichment_health` (`OUTCOME_OK`/`OUTCOME_FALLBACK`/…) | intern, bestehend (#1581) | Vokabular und Journal-Schreibweg — diese Scheibe fügt keinen zweiten Schreibweg hinzu |
| `_within_inca()` (`radar_service.py:1149-1153`) | intern | Definiert die Koordinaten-Box, innerhalb derer ein Test überhaupt den GeoSphere-INCA-Zweig durchläuft |

## Implementation Details

**1. `fetch_nowcast()` reicht den Fehlerstatus durch, statt ihn zu verschlucken**
(`geosphere.py:492-496`):

```
try:
    data = self._request(ENDPOINTS["nowcast"], lat, lon, NOWCAST_PARAMS)
    return self._parse_nowcast_response(data)
except httpx.HTTPStatusError as e:
    raise ProviderRequestError(
        "geosphere",
        f"NOWCAST request failed with status {e.response.status_code}",
        status_code=e.response.status_code,
    ) from e
```

`ProviderRequestError` ist bereits im Modul importiert (`geosphere.py:40`) und wird
an anderer Stelle im Provider bereits genutzt — kein neuer Ausnahmetyp. Der
Statuscode landet über den f-String in der Ausnahme-Nachricht, damit er in jeder
Stelle sichtbar ist, die `str(e)` verwendet (z. B. eine Logzeile), ohne dass der
Aufrufer eigens auf `e.status_code` zugreifen muss.

**2. Der bestehende Aufrufer ändert sich NICHT strukturell** — sein
`try/except Exception as e` (`radar_service.py:743-769`) fängt die neue Ausnahme
bereits korrekt ab, weil `ProviderRequestError` eine `Exception`-Unterklasse ist.
Zu prüfen/ggf. anzupassen ist ausschließlich, dass die bestehende Zeile

```
logger.warning(f"GeoSphere INCA failed, falling back: {e}")
```

(Zeile 767) den Statuscode tatsächlich sichtbar macht — das ist durch Schritt 1
automatisch der Fall, da `str(e)` bei `ProviderError`-Unterklassen die übergebene
`message` enthält (`base.py:130-134`: `f"[{provider}] {message}"`). Kein weiterer
Code-Eingriff an dieser Zeile nötig, sofern die Nachricht aus Schritt 1 den
Statuscode enthält — das ist Teil der Abnahme (AC-2), keine optionale Ausschmückung.

**3. Ausdrücklich NICHT:** kein `log_enrichment_call(...)` direkt in
`fetch_nowcast()` (Snowgrid-Muster, `geosphere.py:369-382`). Das erzeugte eine
zweite, von der zentralen `elif`-Kette unabhängige Journalzeile pro Aufruf — und
genau die zentrale Kette ist die einzige Stelle, die weiß, ob nach dem
INCA-Fehlschlag eine Vertretung geliefert hat (`fallback`) oder gar nichts
(`unavailable`). Ein zweiter Schreibort würde diese Unterscheidung unterlaufen
und im Journal zwei widersprüchliche Zeilen pro Abruf hinterlassen.

## Expected Behavior

- **Input:** ein INCA-Nowcast-Abruf (`fetch_nowcast`) für eine Koordinate innerhalb
  der INCA-Box, bei dem der Upstream mit einem HTTP-Fehlerstatus antwortet.
- **Output:** `fetch_nowcast()` liefert nicht mehr `None`, sondern lässt eine
  `ProviderRequestError` mit `status_code` und einer den Statuscode nennenden
  Nachricht durchreichen. `_fetch_geosphere_inca()` fängt sie, loggt eine
  Warnzeile mit dem Statuscode und setzt `_inca_unavailable_this_call = True`.
  Die zentrale Buchung in `get_nowcast()` bucht daraufhin `OUTCOME_FALLBACK`
  (wenn eine andere Quelle liefert) oder `OUTCOME_UNAVAILABLE` (wenn keine
  Quelle liefert) statt `OUTCOME_OK`.
- **Side effects:** keine auf den fachlichen Datenfluss — liefert eine
  Ersatzquelle Frames, bleibt das Nowcast-Ergebnis für den Nutzer unverändert
  (nur die Journalzeile ändert sich von `ok` zu `fallback`). Der Fall „INCA
  antwortet regulär mit HTTP 200 und meldet keinen Niederschlag" bleibt
  unverändert `ok`.

## Acceptance Criteria

- **AC-1:** Given eine Koordinate innerhalb der INCA-Box (`_within_inca()`) UND
  der INCA-Nowcast-Endpunkt antwortet mit einem HTTP-Fehlerstatus (z. B. 500) UND
  eine nachgelagerte Quelle liefert ein gültiges Ergebnis / When
  `RadarNowcastService.get_nowcast()` diesen Abruf durchläuft / Then enthält das
  Health-Journal (`enrichment_calls.jsonl`, `path="radar_nowcast"`) eine Zeile mit
  `outcome="fallback"` und `detail` gleich dem Namen der tatsächlich verwendeten
  Ersatzquelle — ausdrücklich NICHT `outcome="ok"`.
  - Test: Journal vor dem Aufruf leeren, `get_nowcast()` für eine INCA-Koordinate
    aufrufen, danach die letzte `radar_nowcast`-Zeile auf `outcome` UND `detail`
    prüfen — nicht nur auf Existenz einer Zeile.

- **AC-2:** Given derselbe INCA-Fehlerstatus-Fall wie AC-1 / When
  `_fetch_geosphere_inca()` die Ausnahme fängt / Then enthält die dabei
  ausgegebene Warn-Logzeile den HTTP-Statuscode der fehlgeschlagenen Antwort
  (z. B. sichtbar als `"500"` im Log-Text).
  - Test: `caplog` auf Level WARNING, denselben Fehlerstatus-Fall wie AC-1
    auslösen und den Statuscode als Teilstring im Log-Mitschnitt nachweisen —
    der Test wird rot, wenn der Statuscode aus der Nachricht entfernt wird.

- **AC-3:** Given eine Koordinate innerhalb der INCA-Box UND der INCA-Nowcast-
  Endpunkt antwortet regulär (HTTP 200) mit einer strukturell gültigen, aber
  niederschlagsfreien Antwort / When `get_nowcast()` diesen Abruf durchläuft /
  Then bleibt der Ausgang `outcome="ok"`, es entsteht KEINE Warnzeile und
  `_inca_unavailable_this_call` bleibt `False`. Ein regulärer „nichts zu
  melden"-Fall darf nicht als Ausfall gebucht werden.
  - Test: gescriptete HTTP-200-Antwort mit leeren/nullwertigen
    Niederschlagsfeldern, danach Journalzeile auf `outcome="ok"` prüfen UND
    `caplog` auf Abwesenheit einer WARNING-Zeile für diesen Aufruf prüfen.

- **AC-4:** Given derselbe INCA-Fehlerstatus-Fall wie AC-1 / When
  `get_nowcast()` einmal durchläuft / Then enthält das Journal danach GENAU EINE
  neue Zeile mit `path="radar_nowcast"` — kein zweiter Buchungsort (z. B. direkt
  in `fetch_nowcast()`) erzeugt eine weitere, womöglich widersprüchliche Zeile.
  - Test: Zeilenzahl für `path="radar_nowcast"` vor und nach dem Aufruf zählen,
    Differenz muss exakt 1 sein.

- **AC-5:** Given der Nachweis für AC-1 bis AC-4 / When die Testfälle aufgebaut
  werden / Then erfolgt die Simulation des INCA-Fehlerstatus AUSSCHLIESSLICH über
  eine gescriptete HTTP-Antwort auf `httpx`-Ebene (Muster `_ScriptedClient`,
  `tests/unit/test_radar_upstream_failure.py:83-105`) für eine Koordinate
  innerhalb `_within_inca()`, NICHT über ein Monkeypatch von
  `GeoSphereProvider.fetch_nowcast` als Ganzes. Ein Test, der die Methode
  komplett ersetzt, springt über die Schluckstelle hinweg und beweist den Fix
  nicht (siehe „Bestehender blinder Wächter" unten).
  - Test: der neue Testfall verwendet nachweislich einen `httpx.Client`-Double,
    der eine echte `httpx.Response` mit Fehlerstatus zurückgibt, statt
    `monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", ...)`.

## Bestehender blinder Wächter

`tests/tdd/test_radar_inca_fallback_journal.py` (AC-6/AC-7 dieser Testdatei,
aus #1581/#1992) ersetzt `GeoSphereProvider.fetch_nowcast` komplett durch eine
Funktion, die direkt `RuntimeError` wirft bzw. ein Erfolgsergebnis zurückgibt.
Diese Ersetzung springt über die in dieser Spec behandelte Schluckstelle
(`except httpx.HTTPStatusError: return None`, `geosphere.py:495-496`) hinweg —
sie prüft die zentrale `elif`-Kette in `get_nowcast()`, nicht ob ein echter
HTTP-Fehlerstatus dorthin überhaupt durchdringt. Der Test ist deshalb heute
grün, obwohl der in dieser Spec behobene Bug existiert, und bleibt nach diesem
Fix unverändert grün (Regressionsschutz, keine Doppelabdeckung). Der neue
Nachweis (AC-1 bis AC-5) muss zwingend eine Ebene tiefer ansetzen — auf
HTTP-Ebene —, sonst wiederholt er denselben Blindfleck.

## Nicht in dieser Scheibe

- **Scheibe S4 des Tickets** (Gesundheitssignal für anhaltende Ausfälle,
  `/api/scheduler/status`-Anschluss) ist durch #1581 bereits geliefert und
  nicht Teil dieser Arbeit — diese Scheibe macht nur das bestehende
  Merkzeichen im Fehlerstatus-Fall erreichbar.
- **Threading-Frage zu `_inca_unavailable_this_call`:** das Merkzeichen ist ein
  Instanzattribut ohne Sperre; zwei gleichzeitige `get_nowcast()`-Aufrufe auf
  derselben Instanz könnten es gegenseitig überschreiben. Nicht neu durch
  diesen Fix, nicht belegt als produktiv auftretend → Sammel-Issue (#1199),
  kein Teil dieser Scheibe.
- **Netzwerkfehler und strukturell leere Antworten** (`httpx.ConnectError`,
  `httpx.RequestError`, `_parse_nowcast_response` wirft `ValueError` bei
  `not features`) sind bereits heute korrekt verdrahtet — sie propagieren
  ungefangen aus `fetch_nowcast()` und werden vom bestehenden
  `except Exception`-Block korrekt gebucht. Diese Scheibe ändert daran nichts.

## Known Limitations

- Der Statuscode wird als Teil der Ausnahme-Nachricht (String) transportiert,
  nicht als strukturiertes Feld im Health-Journal — `outcome`/`detail` bleiben
  beim bestehenden #1581-Vokabular (`fallback`/`unavailable`), das nicht
  zwischen Fehlerstatus, Timeout und leerer Antwort unterscheidet. Das ist ein
  Nicht-Ziel dieser Scheibe (s. #1581 Known Limitations: „unterscheidet
  bewusst NICHT, welche Quelle ausfiel").

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — löst ADR-0018 („Modell-Fallback ohne Kaschieren")
  für den zuvor unvollständig verdrahteten INCA-Fehlerstatus-Fall vollständig
  ein; kein neues Grundsatzmuster.
- **Rationale:** Der bestehende Mechanismus aus #1581 (zentrale Bewertung in
  `get_nowcast()`, `ProviderRequestError` mit `status_code` aus #1115) reicht
  aus, um den Fehlerstatus sichtbar zu machen — es braucht weder einen neuen
  Ausnahmetyp noch einen zweiten Buchungsort. Die Lücke war ausschließlich das
  stille `return None` in `fetch_nowcast()`.

## Changelog

- 2026-08-23: Initial spec created (Issue #1658 Scheibe S2, Analyse
  `docs/context/fix-1658-inca-fehlerstatus.md`).
