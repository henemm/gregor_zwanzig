---
entity_id: feat_1457_s2a_blitzdichte_meteofrance
status: draft
type: module
created: 2026-08-02
updated: 2026-08-02
version: "1.0"
tags: [gewitter, provider, meteofrance, s2a]
---

# Blitzdichte von Météo-France ins Datenmodell

## Approval

- [ ] Approved

## Purpose

Météo-France sagt für Frankreich und Korsika die **erwartete Blitzdichte** voraus
(`LITOTA3`, „Average lightning strike density over 3 hours"). Dieser Wert wird
abgerufen und in ein **eigenes Feld** des gemeinsamen Datenmodells gelegt — regulär
bei jeder Vorhersage, nicht nur bei Ausfall der Hauptquelle.

Erste Scheibe von S2 (#1457) aus dem Gewitter-Konzept #1419. **Für Korsika ist das
die beste verfügbare Gewitterquelle** (1,3 km Maschenweite, direkte Blitzvorhersage
statt Potenzialgröße).

## Source

- **File:** `src/providers/meteofrance.py`, `src/app/models.py`
- **Identifier:** `MeteoFranceDirectProvider.fetch_thunder_signals()` (neu),
  `ForecastDataPoint.lightning_density_per_km2_3h` (neu)

**Schicht:** Python-Core (`src/providers/`, `src/app/`). Keine Go-API, kein Frontend.

## Estimated Scope

- **LoC:** ~100 Quellcode + ~130 Tests = **~230**
- **Files:** 2 geändert, 1 Testdatei neu
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Météo-France WCS | externer Dienst | Zugang besteht seit #1143, kein neuer Vertrag |
| `rasterio` (`MemoryFile`) | Bibliothek | Punktwert aus der Antwort lesen (Muster `_read_point_value`) |
| `region_routing.direct_provider_for` | intern | bestimmt, ob ein Ort zu Frankreich gehört |

## Implementation Details

```
Muster: Anreicherung, exakt wie `enrich_ensemble` bei Open-Meteo
  (openmeteo.py:640-680, 1050-1052) — best-effort, fail-soft, nie werfend.

1. ForecastDataPoint bekommt ein neues Feld:
     lightning_density_per_km2_3h: Optional[float] = None
   BEWUSST eigenes Feld, NICHT gemeinsam mit dem DWD-Blitzpotenzial
   (andere Groesse, andere Skala — s. #1419 Abschnitt 3.1).

2. MeteoFranceDirectProvider.fetch_thunder_signals(location, ...)
     -> Dict[datetime, Optional[float]]
   Coverage LITOTA3__GROUND___<lauf>, Muster _fetch_series,
   EIGENES Zeitbudget (nicht das der Grundvorhersage).
   Jede Ausnahme -> {} , nie werfen.

3. Anreicherung greift, wenn der Ort nach Frankreich faellt.
   Default eingeschaltet. Fehlt ein Wert -> Feld bleibt None.
```

## Expected Behavior

- **Input:** eine Position mit Zeitraum
- **Output:** dieselbe Vorhersage wie heute, zusätzlich mit gefülltem Blitzdichte-Feld
  an französischen/korsischen Orten
- **Side effects:** zusätzliche HTTP-Abrufe an Météo-France (Kosten s. Known Limitations)

## Acceptance Criteria

- **AC-1:** Given eine Position auf Korsika (GR20, 42.22 N / 9.07 O) / When eine
  Vorhersage abgerufen wird / Then trägt mindestens ein Zeitpunkt einen Blitzdichte-Wert
  aus Météo-France, während dieselbe Abfrage heute für alle Zeitpunkte leer bleibt.
  - Test: Gegen eine aufgezeichnete Météo-France-Antwort wird nachgewiesen, dass der
    Wert am Datenpunkt ankommt; ohne die Änderung ist das Feld durchgängig leer.

- **AC-2:** Given Météo-France liefert für einen Zeitpunkt keinen Wert / When die
  Vorhersage gebaut wird / Then bleibt das Feld **leer** — es wird **nie** auf 0
  gesetzt.
  - Test: Eine Antwort ohne Wert für eine Stunde erzeugt an diesem Zeitpunkt `None`;
    ein Test, der 0 erwartet, muss fehlschlagen. „Keine Aussage" ist nicht „keine
    Gefahr" (#1419 Abschnitt 5).

- **AC-3:** Given der Abruf der Blitzdichte scheitert vollständig (Serverfehler,
  Zeitüberschreitung, Netzfehler) / When eine Vorhersage abgerufen wird / Then wird sie
  **trotzdem vollständig geliefert**, nur ohne Blitzdichte — der Fehler kippt die
  Vorhersage nicht.
  - Test: Ein Abruf, der eine Ausnahme wirft, führt zu einer vollständigen Vorhersage
    mit Temperatur und Wind und leerem Blitzdichte-Feld. Gegenprobe: Wird das Werfen im
    Anreicherungspfad zugelassen, muss der Test rot werden.

- **AC-4:** Given die Blitzdichte-Abrufe brauchen ungewöhnlich lange / When das
  Zeitbudget der Anreicherung erschöpft ist / Then bricht **nur die Anreicherung** ab,
  und die Grundvorhersage behält ihr eigenes, unangetastetes Budget.
  - Test: Mit künstlich kleingesetztem Anreicherungsbudget gegen einen langsamen
    lokalen Server endet der Aufruf innerhalb der Grenze und liefert die
    Grundvorhersage; die Laufzeit belegt, dass nicht auf das große Budget gewartet
    wurde. (Muster `tests/tdd/test_meteofrance_direct_fallback.py:476-517`.)

- **AC-5:** Given eine Aufrufstelle, die den Anreicherungs-Schalter nicht ausdrücklich
  setzt / When sie eine Vorhersage für einen französischen Ort abruft / Then wird die
  Blitzdichte **trotzdem** geholt — der Standardwert schützt.
  - Test: Ein Aufruf ohne den Schalter füllt das Feld. (#1448-Lehre: Ein Schutz, der an
    einem durchzureichenden Parameter hängt, ist kein Schutz.)

- **AC-6:** Given ein Ort außerhalb Frankreichs / When eine Vorhersage abgerufen wird /
  Then findet **kein** Météo-France-Abruf statt und das Feld bleibt leer.
  - Test: Für einen Ort in den Alpen wird nachgewiesen, dass kein Abruf ausgelöst wird —
    sonst entstehen sinnlose Abrufe außerhalb des Modellgebiets.

## Known Limitations

1. **Hagel ist nicht Teil dieser Scheibe.** `DIAG_GRELE` lieferte am Messtag klare
   Werte (4,9 gegen 0,0), aber der Beschreibungs-Endpunkt antwortet dauerhaft mit
   HTTP 502 — die **Bedeutung und Einheit sind ungeklärt**. Auf einer Vermutung zu
   bauen wäre bei einem Sicherheitssignal falsch. Eigene Scheibe, sobald geklärt.
2. **Abrufkosten.** Météo-France liefert einen Wert je Größe **und Stunde**; heute
   entstehen ~96 Abrufe je Ort, diese Scheibe fügt bis zu 24 hinzu. Bewusst bezahlt
   (PO-Vorgabe „maximale Qualität"), aber der Grund für das getrennte Zeitbudget.
3. **Enge Ostgrenze.** Das Frankreich-Rechteck endet bei 9,7 O (`region_routing.py:36`);
   Petra Piana liegt bei 9,07 O. Für Korsika trägt es, die Marge ist aber klein — ein
   Ort weiter östlich fiele heraus. Wird in **S2c** (Lückenfüller) aufgefangen.
4. **Noch nichts für den Nutzer sichtbar.** Der Wert liegt im Datenmodell; Stufe (S3)
   und Ausgaben (S5) folgen. Bewusst: Erst wenn das Signal verlässlich anliegt, kann
   eine Warnung darauf aufsetzen.
5. **Nur Frankreich und Korsika.** Alpen und Deutschland folgen in S2b über den DWD.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine für diese Scheibe
- **Rationale:** Additives Feld und ein zusätzlicher Anreicherungsaufruf nach
  bestehendem Muster (`enrich_ensemble`) — keine neue Entscheidungsfläche. Die
  **größenabhängige Zuständigkeit** (Gewitter aus einer anderen Quelle als Temperatur)
  wird erst in **S2b** entschieden und braucht dort ein ADR im Muster von **ADR-0041**.

## Changelog

- 2026-08-02: Initial spec created (Issue #1457 S2a, Konzept #1419)
