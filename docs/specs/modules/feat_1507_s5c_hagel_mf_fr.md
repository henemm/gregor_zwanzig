---
entity_id: feat_1507_s5c_hagel_mf_fr
type: module
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "1.0"
tags: [gewitter, hagel, meteofrance, epic-1419, issue-1507, s5c]
---

# Météo-France-Hagel-Rohwert für FR/Korsika — Scheibe S5c

## Approval

- [ ] Approved

## Purpose

Für Orte im AROME-FR-Zuständigkeitsgebiet (`fr_direct`, Frankreich/Korsika) gibt
es heute **keinen** Hagel-Rohwert von Météo-France — `hail_flag` wird dort
ausschließlich aus dem Open-Meteo-WMO-Code abgeleitet (#1475 S5a), der Hagel nur
**bejahen**, nie **verneinen** kann. Diese Scheibe (S5c von 3 zu #1475, Block C
von #2257, Epic #1419) holt zusätzlich einen echten Hagel-Rohwert von AROME —
analog zum bestehenden Blitzdichte-Abruf (#1457 S2a) — und legt ihn in ein
**neues, eigenes Feld**. Sie leitet daraus **kein** `hail_flag` ab und
kombiniert ihn **nicht** mit dem WMO-Code — das ist Scope-Ausschluss dieser
Scheibe (s. AC-4, Known Limitations).

## Source

- **File:** `src/providers/meteofrance.py`, `src/app/models.py`
- **Identifier:** neue Coverage-Konstante (Name erst nach AC-1 final),
  `MeteoFranceDirectProvider.fetch_hail_signals_multi()` (neu, dünner Wrapper
  analog `fetch_thunder_signals_multi`), `ForecastDataPoint.hail_potential_mf`
  (neu, Platzhaltername — s. Open Questions)

**Schicht:** Python-Core (`src/providers/`, `src/app/`). Kein Go-API-DTO-Fund,
kein Frontend — dieselbe Abgrenzung wie bei #1475 S5a: das neue Feld wird in
dieser Scheibe an keiner Stelle gerendert.

> **Schicht-Hinweis geprüft:** Alle betroffenen Symbole liegen im Python-Core
> (`src/providers/meteofrance.py`, `src/app/models.py`). Go-API (`internal/`,
> `cmd/`) ist nicht betroffen, SvelteKit-Frontend (`frontend/src/...`) ist
> nicht betroffen.

## Estimated Scope

- **LoC:** ~45–75 Produktivcode (`meteofrance.py`, `models.py`) + vergleichbarer
  Testumfang (1 Live-Test-Datei für AC-1, 1–2 Kern-Testdateien für
  fail-soft/Budget-Verhalten)
- **Files:** 2 Produktivdateien geändert, keine neue Produktivdatei; 1–2
  Testdateien neu
- **Effort:** medium — Risiko liegt nicht im Umfang, sondern in der
  Namens-/Einheiten-Unsicherheit (externe Abhängigkeit von
  Météo-France-Dokumentation, s. AC-1)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1475 S5a (`ForecastDataPoint.hail_flag`, live, Commit `2a72175b`) | Upstream, geschlossen | Datenmodell-/Renderer-Grundlage; diese Scheibe ändert daran NICHTS — `hail_flag` bleibt unverändert |
| #1457 S2a (`LIGHTNING_COVERAGE`, `fetch_thunder_signals_multi`, geteilter Zwischenspeicher `thunder_window_cache`) | interner Code, live | direkte Blaupause für Coverage-Abruf-Muster (Sammelabruf über Rechteck, Budget/Deadline, fail-soft) |
| Météo-France WCS | externer Dienst | Zugang besteht seit #1143, kein neuer Vertrag; Kontingent 100 Anfragen/Minute pro Konto (PO-bestätigt, s. #1457 S2a AC-9) |
| `thunder_routing.thunder_provider_for` | intern | bestimmt die Gewitter-Zuständigkeit (nicht die Grundvorhersage-Tabelle, #1457 S2a AC-12) — für den Hagel-Abruf identisch zu verwenden |
| `tests/tdd/test_thunder_coverage_name_live.py` | Vorbild, existierende Testdatei | Muster für den AC-1-Live-Test dieser Scheibe |

## Implementation Details

```
REIHENFOLGE-ABHÄNGIGKEIT (PFLICHT, PO-Vorgabe 2026-09-20):
  AC-1 MUSS gruen sein, BEVOR ein Coverage-Name in Produktivcode verdrahtet
  wird. AC-2/AC-3 setzen einen bestandenen AC-1 voraus — kein Name aus der
  Konzept-Tabelle #1419 oder aus dem >1 Monat alten Issue-Beleg (2026-08-03)
  wird ungeprueft uebernommen (S2a-Lehre: `LITOTA3` existierte beim Dienst
  nicht, jeder Abruf endete lautlos in 404).

1. AC-1 (TDD-RED, VOR jeder Implementierung):
   Neue Datei `tests/tdd/test_hail_coverage_name_live.py`, 1:1-Muster
   `test_thunder_coverage_name_live.py`:
     - `pytest.mark.live`, `dotenv_env`-Fixture, `_require_meteofrance_key()`
     - EIN `GetCapabilities`-Abruf (Kontingent-Schonung, Muster der
       Blaupause)
     - prueft den in einer neuen Konstante (z.B. `HAIL_COVERAGE`) im
       Produktivcode hinterlegten Namen GEGEN die echte Antwort — nicht
       gegen einen zweiten, fest hineingeschriebenen Vergleichsstring
     - Kandidaten (Issue-Beleg 2026-08-03, ZU VERIFIZIEREN, nicht zu
       uebernehmen): `HAIL__GROUND_OR_WATER_SURFACE`,
       `GRAUPEL__GROUND_OR_WATER_SURFACE`
     - zusaetzlich: `DescribeCoverage` des verifizierten Namens abrufen und
       Einheit (`uom`)/Bezeichnung protokollieren (Vorbild: Blitzdichte-
       Kommentar `meteofrance.py:188-191`, "Average lightning strike
       density over 3 hours", uom `km-3`) — Ergebnis fliesst als Kommentar
       an der neuen Konstante UND als Docstring-Klaerung in `models.py` ein
     - ist die Beschreibung nicht erreichbar/die Einheit nicht klar
       dokumentiert: gemaess Analyse (Risks) wird NUR der Rohwert
       gespeichert, keine Schwelle/Flag-Ableitung erzwungen (s. AC-3, AC-4)

2. Coverage-Abruf parametrisieren, NICHT kopieren:
   Der Blitzdichte-Sammelabruf (`fetch_thunder_signals_multi`,
   `meteofrance.py:588ff`) ist auf `LIGHTNING_COVERAGE` zugeschnitten. Der
   Coverage-ID-Teil wird parametrisiert (z.B.
   `_fetch_coverage_signals_multi(coverage_base, locations, start, end)`),
   damit Hagel denselben Mechanismus (Rechteck-Sammelabruf, geteilter
   Zwischenspeicher `thunder_window_cache`, Budget/Deadline, fail-soft,
   `thunder_routing`-Zustaendigkeit) nutzt statt ihn zu duplizieren.
   `fetch_thunder_signals_multi` UND das neue
   `fetch_hail_signals_multi` werden zu duennen Wrappern um die
   parametrisierte Funktion. Lauf-/Fenster-Logik
   (`_thunder_run_candidates`, `THUNDER_RUN_SAFETY_HOURS`) wird
   uebernommen; 404-Ruckfallstufen bleiben PRO COVERAGE separat pruefbar
   (Hagel kann andere Verfuegbarkeitszeiten haben als Blitzdichte).

3. Budget TEILEN, nicht verdoppeln (AC-5):
   Der Hagel-Abruf nutzt dasselbe `FETCH_DEADLINE_SECONDS`-Zeitbudget wie
   die Blitzdichte innerhalb DESSELBEN Anreicherungslaufs — kein zweites,
   unabhaengiges Vollbudget. Reicht das gemeinsame Budget wegen des
   Hagel-Abrufs nicht mehr fuer beide Coverages, bricht NUR die
   Anreicherung ab (Muster #1457 S2a AC-4), die Grundvorhersage bleibt
   unberuehrt.

4. Datenmodell (models.py):
   ForecastDataPoint bekommt EIN neues Feld (Platzhaltername, final erst
   nach AC-1):
     hail_potential_mf: Optional[float] = None
   Exakt nach Vorbild `hail_potential_grau_gsp` (S5b-Pendant, DWD,
   `models.py:165`): reiner Rohwert, KEIN Einfluss auf `hail_flag`.
   BEWUSST eigenes Feld, nicht mit `hail_potential_grau_gsp`
   zusammengelegt (andere Quelle, andere Einheit/Skala, #1419 Abs. 3.1) —
   auch wenn beide fachlich "Hagel-Rohwert" heissen.

5. Anreicherung:
   Greift nur fuer Orte, die laut `thunder_routing.thunder_provider_for`
   dem `fr_direct`-Provider zugeordnet sind (AC-6, identisch zur
   Blitzdichte-Zustaendigkeit) — kein Abruf ausserhalb des
   AROME-FR-Zuststaendigkeitsgebiets.

6. `hail_flag` bleibt UNANGETASTET (AC-3/AC-4):
   Kein Zugriff, keine Kombination mit dem WMO-Code in dieser Scheibe.
   `MeteoFranceDirectProvider.fetch_forecast` setzt strukturell KEINEN
   `wmo_code` (Architektur-Befund) — eine Cross-Provider-Fusion
   (Rohwert + WMO-Code -> `hail_flag`) braeuchte eine feldweise
   Provider-Fusion, die es aktuell nicht gibt. Das ist eine eigene,
   groessere Architekturaenderung und AUSDRUECKLICH NICHT Teil dieser
   Scheibe.
```

## Expected Behavior

- **Input:** eine Position im AROME-FR-Zuständigkeitsgebiet mit Zeitraum
- **Output:** dieselbe Vorhersage wie heute, zusätzlich mit gefülltem
  Hagel-Rohwert-Feld (`hail_potential_mf`) an französischen/korsischen Orten,
  sofern verfügbar; `hail_flag` bleibt exakt wie ohne diese Scheibe
- **Side effects:** zusätzliche HTTP-Abrufe an Météo-France, geteiltes Budget
  mit dem Blitzdichte-Abruf (kein Verdopplungseffekt bei Kontingent/Laufzeit)

## Acceptance Criteria

- **AC-1 (Sperr-Voraussetzung, Live-Namens-/Einheiten-Verifikation):** Given
  der echte Météo-France-WCS-Dienst / When ein `pytest.mark.live`-Test
  (`tests/tdd/test_hail_coverage_name_live.py`, Vorbild
  `test_thunder_coverage_name_live.py`) eine frische `GetCapabilities`-Antwort
  abfragt / Then kommt der im Produktivcode hinterlegte Hagel-Coverage-Name
  darin vor UND `DescribeCoverage` liefert eine dokumentierte Einheit/Bedeutung
  für diesen Namen — beides gegen die echte Antwort geprüft, nicht gegen einen
  zweiten fest hineingeschriebenen Vergleichsstring.
  - Test: Live-Test liest den Namen aus der Produktivkonstante (nicht aus
    einer Kopie im Test) und prüft ihn gegen die echte API-Antwort. Gegenprobe:
    Ein Test, der nur einen historischen Beleg (Issue-Kommentar 2026-08-03)
    ungeprüft übernimmt, beweist NICHTS über den heutigen Zustand des Dienstes
    (S2a-Lehre: `LITOTA3` existierte beim Dienst nicht, alle 24 damaligen
    Kern-Tests blieben trotzdem grün, weil sie eine aufgezeichnete Datei
    lasen).
  - **Reihenfolge:** Ohne grünen AC-1 wird KEIN Name in Produktivcode
    verdrahtet — AC-2 und AC-3 setzen einen bestandenen AC-1 voraus.

- **AC-2 (Rohwert-Abruf, fail-soft):** Given ein Ort im AROME-FR-
  Zuständigkeitsgebiet (`thunder_routing.thunder_provider_for` liefert
  `fr_direct`) / When eine Vorhersage über den regulären Anreicherungsweg
  abgerufen wird / Then liefert der neue Coverage-Abruf pro Stunde einen
  Rohwert best-effort — `None` bei Fehler, Zeitüberschreitung oder außerhalb
  des Modellgebiets, **niemals** `0`; ein scheiternder Abruf kippt die
  Grundvorhersage nicht.
  - Test: Gegen eine aufgezeichnete AROME-Antwort ohne Wert für eine Stunde
    entsteht an diesem Zeitpunkt `None`. Ein Test, der `0` erwartet, muss
    fehlschlagen. Gegenprobe Fehlerfall: Ein Abruf, der eine Ausnahme wirft,
    führt zu einer vollständigen Vorhersage mit unverändertem
    Temperatur-/Windfeld und leerem Hagel-Rohwert-Feld — wird das Werfen im
    Anreicherungspfad zugelassen, muss der Test rot werden (Muster #1457 S2a
    AC-2/AC-3).

- **AC-3 (Speicherung ohne Ableitung — Scope-Grenze dieser Scheibe):** Given
  ein Datenpunkt, für den der neue Hagel-Rohwert erfolgreich abgerufen wurde /
  When der Datenpunkt gebaut wird / Then landet der Wert ausschließlich im
  neuen Feld (`hail_potential_mf`); `ForecastDataPoint.hail_flag` bleibt für
  diesen Punkt **exakt identisch** zu einem Lauf ohne diese Scheibe — keine
  Kombination mit dem WMO-Code, keine Schwellen-/Flag-Ableitung.
  - Test: Regressionstest rendert denselben Datenpunkt einmal mit und einmal
    ohne den neuen Hagel-Rohwert-Abruf, vergleicht `hail_flag`. Ergebnis muss
    identisch sein (`None`, da `fr_direct` keinen `wmo_code` führt).
    Gegenprobe (Mutationskandidat): Wird der neue Rohwert versehentlich in
    eine `hail_flag`-Ableitung eingespeist, muss dieser Test rot werden.

- **AC-4 (Scope-Ausschluss als Known Limitation, architektonisch begründet):**
  Given der neue Hagel-Rohwert von Météo-France UND der bestehende
  WMO-Code-basierte `hail_flag` (#1475 S5a) / When beide für denselben
  Zeitpunkt/Ort vorliegen / Then bleiben sie **unverbunden** — eine
  Cross-Provider-Kombination (Rohwert + WMO-Code → gemeinsame Ableitung) ist
  **nicht** Teil dieser Scheibe, weil `MeteoFranceDirectProvider.fetch_forecast`
  strukturell keinen `wmo_code` setzt und eine feldweise Provider-Fusion
  bräuchte, die architektonisch nicht existiert.
  - Test: Ein struktureller Test bestätigt, dass `MeteoFranceDirectProvider`
    an keiner Stelle `hail_flag` liest oder setzt — nur das neue Rohwertfeld.
    Dokumentation als explizite Known Limitation (kein stillschweigendes
    Weglassen).

- **AC-5 (Budget-Teilung, kein Verdopplungseffekt):** Given ein
  Anreicherungslauf für einen Ort im AROME-FR-Gebiet / When sowohl Blitzdichte
  als auch der neue Hagel-Rohwert abgerufen werden / Then teilen sich beide
  Abrufe **dasselbe** Zeitbudget (`FETCH_DEADLINE_SECONDS`) — kein zweites,
  unabhängiges Vollbudget für Hagel.
  - Test: Mit künstlich kleingesetztem gemeinsamem Anreicherungsbudget gegen
    einen langsamen lokalen Server endet der kombinierte Aufruf (Blitzdichte +
    Hagel) innerhalb der EINEN Budgetgrenze; die Laufzeit belegt, dass kein
    zweites unabhängiges Budget existiert (Muster #1457 S2a AC-4,
    `tests/tdd/test_meteofrance_direct_fallback.py:476-517`).

## Known Limitations

1. **Keine Kombination mit `hail_flag` in dieser Scheibe** (s. AC-4).
   `MeteoFranceDirectProvider` führt keinen `wmo_code` — eine
   Cross-Provider-Feldfusion wäre eine eigene, größere Architekturänderung.
   Für Stunden, die von `fr_direct` bedient werden, bleibt `hail_flag`
   strukturell `None`, solange keine Folgescheibe diese Fusion baut.
2. **Einheit/Schwelle ggf. weiterhin ungeklärt.** Liefert `DescribeCoverage`
   (AC-1) keine ausreichend klare, veröffentlichte Bedeutung/Einheit, bleibt
   es beim reinen Rohwert ohne Schwellen-/Flag-Ableitung — keine eigene
   Kalibrierung (Epic-Prinzip, Analogon zu #1456-Schließung und zum S5b-Zustand
   von `hail_potential_grau_gsp`).
3. **Nur Frankreich und Korsika.** Deutschland/Alpen/Österreich bleiben beim
   jeweils eigenen Rohwert (`hail_potential_grau_gsp` bzw. WMO-Code) — S5b
   (#1506, DWD ICON-D2) ist eine separate, `status:deferred`-Scheibe.
4. **Noch nichts für den Nutzer sichtbar.** Der Wert liegt im Datenmodell;
   kein Renderer-Anschluss in dieser Scheibe (analog S5b-Zustand von
   `hail_potential_grau_gsp`) — Kanal-Renderer, die `hail_flag`/
   `format_hail_note` konsumieren, brauchen KEINE Änderung.
5. **Kontingent-Teilung, kein neues Drossel-Konzept.** Der zusätzliche
   Coverage-Typ nutzt den bestehenden geteilten Zwischenspeicher und dasselbe
   Zeitbudget (AC-5) — das bereits bekannte Restrisiko einer aktiven
   Rate-Limit-Drosselung (#1457 S2a Known Limitation 0/AC-9-Restrisiko) wird
   durch diese Scheibe weder gelöst noch verschärft, solange der zusätzliche
   Coverage-Typ im selben Rechteck-Sammelabruf mitläuft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Bezug auf **ADR-0007** (Daten statt Empfehlungen,
  aktiv, nicht abgelöst).
- **Rationale:** Diese Scheibe fügt ein additives Rohwertfeld nach
  bestehendem Muster (`hail_potential_grau_gsp`) und einen zusätzlichen,
  parametrisierten Coverage-Abruf nach bestehendem Muster
  (`fetch_thunder_signals_multi`) hinzu — keine neue Entscheidungsfläche
  (Provider, Datenmodell-Grundprinzip, Auth, Editor-Paradigma). ADR-0007
  bleibt unverändert in Kraft: der neue Wert ist ein reiner Rohwert ohne
  Handlungsempfehlung, in dieser Scheibe ohnehin ohne jeden Renderer-Anschluss.
  Eine Cross-Provider-Feldfusion (s. AC-4/Known Limitation 1) wäre eine
  eigene Architekturentscheidung und bräuchte, sobald sie verfolgt wird, ein
  eigenes ADR im Muster von ADR-0041 — nicht Teil dieser Spec.

## Changelog

- 2026-09-20: Initial spec created (Issue #1507 S5c, Epic #1419, Block C von
  #2257; PO-Entsperrung 2026-09-20 mit Pflicht-Vorarbeit AC-1).
