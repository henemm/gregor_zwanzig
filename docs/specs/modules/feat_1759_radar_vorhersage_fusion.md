---
entity_id: feat_1759_radar_vorhersage_fusion
type: module
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [gewitter, radar, fusion, thunder_enrichment]
---

# Radar-Nowcast-Override der Vorhersage-Gewitterstufe (#1759)

## Approval

- [ ] Approved

## Purpose

Die bestehende Radar-Beobachtung (`RadarNowcastService.get_nowcast().is_convective`) fließt bisher
nur in den `/jetzt`-Alarmpfad ein, nicht in die angezeigte Vorhersage-Gewitterstufe
(`dp.thunder_level`) der Briefing-Stundentabelle. Diese Spec verdrahtet Regel 1 aus dem
Gesamtkonzept ("Beobachtung schlägt Vorhersage"): eine aktuelle konvektive Radar-Beobachtung
oder hohe Blitzdichte im engen Zeitfenster um `now()` hebt `dp.thunder_level` mindestens auf MED
an — sie senkt nie.

## Source

- **File:** `src/providers/thunder_enrichment.py`
- **Identifier:** `enrich_thunder()` (Aufrufort des neuen Override), neue Funktion
  `_apply_radar_override()`

Schicht: Python-Core/Domain-Backend (`src/providers/`) — kein Frontend-, kein Go-API-Anteil.
`enrich_thunder()` ist bereits der einzige Prod-Aufrufpfad für Trip UND Ortsvergleich
(`src/providers/openmeteo.py:1209` bzw. `:1223`), Regel 1 landet damit automatisch auf beiden
Flächen ohne separaten Compare-Codepfad.

## Estimated Scope

- **LoC:** ~150-220 (40-70 Produktivcode, 80-150 Tests)
- **Files:** 2 (`src/providers/thunder_enrichment.py` MODIFY, neue Testdatei CREATE)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py::RadarNowcastService.get_nowcast()` | upstream | liefert `NowcastResult.is_convective` und (perspektivisch) Blitzdichte-Basis für den Override |
| `src/providers/thunder_enrichment.py::_fuse_thunder_levels()` | upstream | bestehende 4-Signal-Fusion, läuft VOR dem neuen Override, bleibt unverändert |
| `src/app/models.py::ForecastDataPoint.thunder_level` / `.thunder_level_signals` | downstream | Zielfelder des Override |
| `src/output/renderers/trip_report.py::_dp_to_row()` | downstream | liest `dp.thunder_level` für die Briefing-Stundentabelle — automatisch betroffen, kein Renderer-Change nötig |
| ADR-0025 (eine Gewitter-Quelle je Kanal-Ausgabe) | constraint | Override mündet in dieselbe `dp.thunder_level`-Quelle, verletzt ADR-0025 nicht |
| ADR-0057 (additive Zweitquellen, Fusionsort bleibt `_fuse_thunder_levels()`) | constraint | siehe Abschnitt „Architektur-Entscheidung (ADR)" unten — Override liegt bewusst AUSSERHALB dieses Fusionsorts |

## Implementation Details

```
enrich_thunder(reihe, location, bereits_befragt=None):
    ... bestehender Code unveraendert bis Zeile 289 ...
    _fuse_thunder_levels(reihe.data, cape_leiter, potenzial_leiter)   # bestehend, unveraendert

    _apply_radar_override(reihe.data, location)                       # NEU

def _apply_radar_override(data: list[ForecastDataPoint], location: Location) -> None:
    now = _naiv_utc(datetime.now(timezone.utc))  # dp.ts ist laut Hausnorm (models.py:230) IMMER naiv-UTC
    fenster = [dp for dp in data if abs((dp.ts - now).total_seconds()) <= 90 * 60]
    if not fenster:
        return
    try:
        result = RadarNowcastService().get_nowcast(
            location.latitude, location.longitude, priority="user_briefing",
        )
    except Exception:
        logger.warning("Radar-Override fehlgeschlagen", exc_info=True)
        return

    ausgeloest = result.is_convective or _blitzdichte_ueber_override_schwelle(result)
    if not ausgeloest:
        return

    for dp in fenster:
        if dp.thunder_level is None or _rang(dp.thunder_level) < _rang(ThunderLevel.MED):
            dp.thunder_level = ThunderLevel.MED
        if dp.thunder_level_signals is None:
            dp.thunder_level_signals = []
        if "radar" not in dp.thunder_level_signals:
            dp.thunder_level_signals.append("radar")
```

- `dp.ts` ist laut Hausnorm **naiv-UTC** (`ForecastDataPoint.__post_init__`, `models.py:230` —
  erzwingt naiv-UTC, auch bei tz-aware Eingabe). Der Fenster-Vergleich läuft deshalb über den
  bestehenden Helper `_naiv_utc()` (`thunder_enrichment.py:73`), NICHT über einen direkten
  Vergleich mit `datetime.now(timezone.utc)` (das wirft `TypeError: can't subtract
  offset-naive and offset-aware datetimes` — im RED-Lauf 2026-08-19 gefunden). Kein lokaler
  Wanduhr-Vergleich, keine `local_hour()`-Umrechnung (die bekannte Zeitzonenfalle des Projekts
  betrifft die Anzeige, nicht diesen Vergleich).
- `get_nowcast()` wird **1× je Reihe/Location** aufgerufen, nur wenn mindestens ein `dp` im
  Fenster liegt (Performance-Gate, kein Call je Datenpunkt).
- Der Deckel hebt an, wenn die bestehende Fusion `None` ("keine Aussage") ODER eine Stufe unter
  MED ergeben hat; er lässt eine bereits `MED`/`HIGH` eingestufte Stunde unverändert bzw. senkt
  nie.
- try/except um den `get_nowcast()`-Call, analog zum bestehenden Muster um
  `_fetch_lightning_density()` (`thunder_enrichment.py:279-282`): schlägt der Call fehl, bleibt
  `is_convective` implizit unwirksam, kein Override, kein Crash.

## Expected Behavior

- **Input:** Zeitreihe (`reihe.data: list[ForecastDataPoint]`) nach abgeschlossener
  4-Signal-Fusion, plus `location` (lat/lon) für den Radar-Abruf.
- **Output:** an Datenpunkten im ±90-Min-Fenster um `now()` ggf. angehobenes `dp.thunder_level`
  (mindestens `MED`) und um `"radar"` ergänztes `dp.thunder_level_signals` — beides in-place,
  kein Rückgabewert (folgt dem bestehenden `enrich_thunder()`-Muster).
- **Side effects:** ein zusätzlicher Live-`get_nowcast()`-Call je Reihe/Briefing- bzw.
  Vergleichslauf, wenn ein `dp` im Fenster liegt (nicht je Datenpunkt).

## Acceptance Criteria

- **AC-1:** Given eine Vorhersage-Reihe, deren 4-Signal-Fusion für die aktuelle Stunde `LOW`
  oder keine Aussage (`None`) ergeben hat, und eine Radar-Beobachtung mit `is_convective=True`
  im ±90-Min-Fenster um `now()` / When `enrich_thunder()` läuft / Then ist `dp.thunder_level`
  für diesen Datenpunkt mindestens `MED`.
  - Test: Zeitreihe mit einem `dp` in der aktuellen Stunde ohne bzw. mit niedriger
    Gewitterstufe füttern, Radar-DI-Seam liefert `is_convective=True`, Briefing-Erzeugung
    aufrufen, resultierende Stundentabelle zeigt für diese Stunde mindestens die mittlere
    Gewitter-Stufe.

- **AC-2:** Given ein Datenpunkt, dessen 4-Signal-Fusion bereits `HIGH` ergeben hat, und eine
  Radar-Beobachtung mit `is_convective=True` im Fenster / When `enrich_thunder()` läuft / Then
  bleibt `dp.thunder_level` unverändert bei `HIGH` (kein Absenken durch den Override, aber auch
  keine Erhöhung über die vorhandene Stufe hinaus).
  - Test: Zeitreihe mit `dp` füttern, dessen Fusionssignale `HIGH` erzwingen, Radar-DI-Seam
    liefert `is_convective=True`, nach `enrich_thunder()` zeigt die Stundentabelle weiterhin
    die höchste Gewitterstufe, keine sichtbare Änderung.

- **AC-3:** Given eine Radar-Beobachtung mit `is_convective=True`, deren zugehöriger Zeitstempel
  außerhalb des ±90-Minuten-Fensters um `now()` liegt / When `enrich_thunder()` läuft / Then hat
  der Override keine Wirkung auf `dp.thunder_level` dieses weit entfernten Datenpunkts (bleibt
  beim Ergebnis der 4-Signal-Fusion).
  - Test: Zeitreihe mit einem `dp` mehrere Stunden in der Zukunft und Radar-DI-Seam mit
    `is_convective=True` füttern, nach `enrich_thunder()` zeigt die Stundentabelle für diesen
    fernen Datenpunkt exakt den Wert der reinen 4-Signal-Fusion, unverändert.

- **AC-4:** Given eine Radar-Beobachtung mit `is_convective=False`, aber einer Blitzdichte über
  der neuen, eigenen Override-Schwelle, im ±90-Min-Fenster / When `enrich_thunder()` läuft /
  Then wird der Override trotzdem ausgelöst und `dp.thunder_level` auf mindestens `MED`
  angehoben.
  - Test: Zeitreihe mit `dp` in der aktuellen Stunde, Radar-DI-Seam liefert
    `is_convective=False`, Blitzdichte-Eingabe über der neuen Override-Schwelle setzen,
    resultierende Stundentabelle zeigt mindestens die mittlere Gewitterstufe.

- **AC-5:** Given ein fehlschlagender Radar-Abruf (Exception im `get_nowcast()`-Call) im
  ±90-Min-Fenster / When `enrich_thunder()` läuft / Then bleibt `dp.thunder_level` beim
  Ergebnis der 4-Signal-Fusion, kein Crash, kein unbehandelter Fehler propagiert nach oben.
  - Test: Radar-DI-Seam wirft eine Exception, Briefing-Erzeugung für eine Reihe mit `dp` in der
    aktuellen Stunde durchlaufen lassen — Aufruf schließt fehlerfrei ab, Stundentabelle zeigt
    unverändert das Ergebnis der 4-Signal-Fusion.

- **AC-6:** Given ein durch den Override ausgelöster Datenpunkt / When `enrich_thunder()`
  abgeschlossen ist / Then enthält `dp.thunder_level_signals` `"radar"` zusätzlich zu allen
  zuvor durch die 4-Signal-Fusion eingetragenen Zutaten (nicht ersetzend).
  - Test: Zeitreihe mit `dp`, dessen 4-Signal-Fusion bereits ein Signal (z. B. `"cape"`)
    einträgt, Radar-Override zusätzlich auslösen, geprüft wird, dass die Herkunfts-Anzeige der
    Stundentabelle sowohl das ursprüngliche Signal als auch die Radar-Herkunft ausweist.

- **AC-7:** Given ein Ortsvergleichs-Lauf mit derselben Ausgangslage wie AC-1 (Radar konvektiv
  im Fenster, Fusion vorher `LOW`/`None`) / When die Ortsvergleichs-Erzeugung `enrich_thunder()`
  durchläuft / Then zeigt die Ortsvergleichs-Ausgabe für diesen Ort/diese Stunde dieselbe
  Anhebung auf mindestens `MED` wie der Trip-Pfad (kein separater Ortsvergleich-Codepfad).
  - Test: Ortsvergleichs-Erzeugung für einen Ort mit `dp` in der aktuellen Stunde und
    Radar-DI-Seam mit `is_convective=True` durchlaufen, resultierende Vergleichsausgabe zeigt
    für diesen Ort mindestens die mittlere Gewitterstufe — identisches Verhalten zum
    Trip-Pfad aus AC-1.

## Known Limitations

- **TODO: PO/Meteorologie-Kalibrierung** — die konkrete Zahl der neuen, eigenen
  Blitzdichte-Override-Schwelle (AC-4) ist noch nicht kalibriert. Sie muss getrennt von der
  bestehenden LPI-/Blitzdichte-Leiter der normalen 4-Signal-Fusion (`lpi_low_min`/`lpi_med_min`/
  `lpi_high_min` in `thunder_level_from_signals()`) gepflegt werden, um eine Verwechslung der
  beiden Fusionsstufen zu vermeiden. Bis zur Kalibrierung ist AC-4 mit einem im Test explizit
  benannten Platzhalterwert zu belegen (kein erfundener "Ist-Vokabular"-Wert in der Produktion).
- `RadarNowcastService.priority="user_briefing"` ist laut `forecast_budget.py` rate-limit-frei
  — dieselbe Eigenschaft gilt bereits für die bestehenden Aufrufstellen (`/jetzt`,
  Radar-Alarm) und wird hier unverändert übernommen, nicht neu bewertet.
- Zusätzliche Latenz: ein Live-Radar-Call je Ort und Briefing-/Vergleichslauf (nicht je
  Datenpunkt), zusätzlich zum bestehenden `HTTPX_TIMEOUT=8.0`. Bei 9-15 Orten im Ortsvergleich
  potenziell spürbar — nicht Teil dieser Spec, ggf. separates Perf-Ticket, falls in der
  Praxis auffällig.
- `_apply_radar_override()` selbst hat kein Fenster-übergreifendes Gedächtnis: läuft
  `enrich_thunder()` mehrfach hintereinander für dieselbe Reihe (z. B. Retry), wird
  `get_nowcast()` erneut aufgerufen — kein Caching auf dieser Ebene, folgt dem bestehenden
  `RadarNowcastService`-internen Cache.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0057 (Ergänzung empfohlen, kein neuer ADR)
- **Rationale:** ADR-0057 erlaubt additive Zweitquellen, hält aber fest, dass der Fusionsort
  `_fuse_thunder_levels()`/`thunder_level_from_signals()` bleibt — "kein zweiter Fusionsort".
  Der hier beschriebene Radar-Override ist bewusst KEIN gleichrangiges fünftes
  `max_thunder()`-Signal, sondern ein bedingter Post-Fusion-Deckel mit eigenem Zeitfenster-Gate
  ("mind. MED, nie tiefer", nur ±90 Min um `now()`) — das sprengt die in ADR-0057
  beschriebene additive `max()`-Symmetrie strukturell. Empfehlung: ADR-0057 um einen Abschnitt
  ergänzen, der diesen zweiten, deckelnden Mechanismus als bewusste Ausnahme von "kein zweiter
  Fusionsort" benennt (Fusionsort für die 4 gleichrangigen Signale bleibt unverändert; der
  Override liegt strukturell danach, nicht daneben). Diese Spec verfasst den ADR-Text nicht
  selbst — nur die Zuordnungsempfehlung.

## Changelog

- 2026-08-19: Initial spec created (Issue #1759, PO-Entscheide zu Override-Bedingung,
  Zeitfenster und Deckel-Ziel vom selben Tag übernommen)
- 2026-08-20: RED-Phase-Korrektur (kein Scope-/AC-Wechsel): Implementation-Details-Skizze nutzt
  `_naiv_utc()` statt direktem tz-aware-Vergleich (RED-Lauf fand `TypeError` gegen `dp.ts`).
  AC-4-Datenquelle nach kurzer Rückfrage beim ursprünglich freigegebenen Stand bestätigt:
  bestehende `lightning_density_per_km2_3h`, keine neue Datenquelle.
