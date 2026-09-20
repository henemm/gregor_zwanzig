---
entity_id: fix_1761_korsika_arome_sidecar
type: module
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "1.0"
tags: [radar, nowcast, korsika, provider, sidecar]
---

# Korsika im Radar-Nowcast: AROME-FR mit ARPAE-Gewitter-Sidecar (Issue #1761)

## Approval

- [ ] Approved

## Purpose

Korsika (GR20) läuft im Radar-Nowcast künftig auf der schärferen Météo-France-AROME-FR-Niederschlagsauflösung (1,5 km) statt auf ARPAE ICON-2I (2 km) — bisher griff die (viel größere) Italien-Bounding-Box vor der Frankreich-Box, und Korsika liegt komplett darin: eine Reihenfolge-Nebenwirkung, keine fachliche Entscheidung (bereits so benannt in #1648). Weil AROME-FR an Korsika-Koordinaten strukturell keinen `weather_code` liefert (live gemessen, siehe Known Limitations), wird die Gewitter-/Hagel-Erkennung (`is_convective`/`hail`) per Sidecar-Merge aus ARPAE ICON-2I ergänzt (PO-Entscheidung 2026-09-20) — analog zum bestehenden INCA+Sidecar-Muster (`_merge_convective`).

## Source

- **File:** `src/services/radar_service.py` (erweitert)
- **Identifier:** neue Bbox-Konstanten `_CORSICA_LAT_MIN/_MAX`, `_CORSICA_LON_MIN/_MAX`, neuer Helper `_within_corsica`, neue Methode `RadarNowcastService._fetch_corsica_arome_fr`, erweiterte `_fetch_frames_with_fallback` und `_region_bucket`
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~55–75 produktiv, ~90–130 Tests
- **Files:** 1 Kern-Datei (MODIFY), 1 Testdatei (MODIFY, 2 Assertions + Docstrings), 1 Testdatei (CREATE), 2 Spec-Dateien (MODIFY, Known-Limitations/Changelog); zusätzlich (Adversary-Finding F001, siehe Changelog): 1 weitere Spec-Datei (`fix_1648_radar_dpc_entfernen.md`, Changelog-Zeile), 1 weitere Testdatei (`test_radar_nowcast_italy_arpae_only.py`, Koordinatentausch)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService._fetch_arome_france_hd` | method (bestehend) | Liefert AROME-FR-Niederschlags-Frames (1,5 km) für Korsika |
| `RadarNowcastService._fetch_italy_arpae` | method (bestehend) | Liefert ARPAE-ICON-2I-Frames inkl. echtem `weather_code` — hier NUR als Sidecar für `is_convective`/`hail`, nicht als Fallback-Quelle |
| `RadarNowcastService._merge_convective` | method (bestehend) | Merged `is_convective`/`hail` aus dem nächstgelegenen Sidecar-Frame (Toleranz 5 Min) — unverändert wiederverwendet |
| `RadarNowcastService._fetch_openmeteo_15` | method (bestehend) | Gemeinsamer, budget-gegateter Funnel (#1329 C2) — trägt automatisch sowohl den AROME- als auch den ARPAE-Sidecar-Aufruf |
| `_ITALY_RADAR_LAT_MIN/_MAX/_LON_MIN/_MAX` | constant (bestehend, UNVERÄNDERT) | Bleibt exakt wie heute — Kopplung zu `DpcSource.covers()` (`official_alerts/dpc.py`) darf nicht angetastet werden |
| `services.official_alerts.dpc.DpcSource` | service (bestehend, UNBERÜHRT) | Importiert `_ITALY_RADAR_*` direkt; Regressionswächter `tests/tdd/test_dpc_official_alert_bbox.py` |
| `tests/tdd/test_radar_nowcast_italy_arpae_only.py::test_ac1_italy_mainland_uses_arpae_with_future_frames` | test (bestehend, MODIFY durch F001) | Vormals `test_ac1_gr20_vizzavona_uses_arpae_with_future_frames`, Koordinate auf Rom (41.90/12.50) gewechselt, weil Vizzavona seit #1761 nicht mehr über ARPAE läuft — bewacht weiterhin die #1648-Zusicherung |

## Implementation Details

### 1. `src/services/radar_service.py` — neue Korsika-Bbox

Eigenständige, real gemessene Ausdehnung (`tests/tdd/test_thunder_signal_enrichment.py:30`),
platziert bei den übrigen Bbox-Konstanten. Bewusst **nicht** durch Verkleinern von
`_ITALY_RADAR_*` gelöst — diese Konstanten sind an `DpcSource.covers()` gekoppelt.

```python
# Korsika bounding box (real gemessene AROME-FR-Ausdehnung, Issue #1761).
# Eigenstaendig -- NICHT durch Verkleinern von _ITALY_RADAR_* geloest,
# wegen der Kopplung zu DpcSource.covers() (official_alerts/dpc.py).
_CORSICA_LAT_MIN = 41.30
_CORSICA_LAT_MAX = 43.11
_CORSICA_LON_MIN = 8.39
_CORSICA_LON_MAX = 9.60


def _within_corsica(lat: float, lon: float) -> bool:
    return (
        _CORSICA_LAT_MIN <= lat <= _CORSICA_LAT_MAX
        and _CORSICA_LON_MIN <= lon <= _CORSICA_LON_MAX
    )
```

### 2. `src/services/radar_service.py` — Quellen-Kette, Korsika-Check VOR Italien

`_fetch_frames_with_fallback`, neuer Block direkt vor der bestehenden `_within_italy_radar`-Prüfung:

```python
if _within_corsica(lat, lon):
    frames = self._fetch_corsica_arome_fr(lat, lon, elevation_m)
    if frames:
        return frames, "AROME-FR"

if _within_italy_radar(lat, lon):
    frames = self._fetch_italy_arpae(lat, lon, elevation_m)
    if frames:
        return frames, "ARPAE-2I"
```

Liefert `_fetch_corsica_arome_fr` leer (AROME-FR-Ausfall), gibt es KEIN `return` — die Prüfung
läuft zum nächsten `if` weiter. Weil jede Korsika-Koordinate geometrisch auch innerhalb der
Italien-Box liegt, greift automatisch der bisherige ARPAE-Vollpfad. Das beantwortet die in der
Analyse offene Fallback-Frage („Durchfallen zur bisherigen Kette") ohne Zusatzcode — reiner
Effekt der Box-Überlappung.

### 3. `src/services/radar_service.py` — `_region_bucket` synchron nachziehen

Docstring-Pflicht (bestehend): dieselbe Reihenfolge wie `_fetch_frames_with_fallback`, sonst
divergieren Cache-Schlüssel und tatsächlich abgerufene Quelle.

```python
if _within_corsica(lat, lon):
    return "corsica"
if _within_italy_radar(lat, lon):
    return "italy_radar"
```

### 4. `src/services/radar_service.py` — neue Methode `_fetch_corsica_arome_fr`

Analog zum bestehenden Sidecar-Muster in `_fetch_geosphere_inca`.

```python
def _fetch_corsica_arome_fr(
    self, lat: float, lon: float, elevation_m: Optional[int] = None
) -> list:
    """AROME-FR-Niederschlag (1,5 km) fuer Korsika, Gewitter/Hagel per
    ARPAE-Sidecar. AROME-FR liefert an Korsika-Koordinaten strukturell
    KEINEN weather_code (Live-Befund 2026-09-20, Issue #1761) -- ohne
    Sidecar waere is_convective/hail fuer JEDEN Frame False, obwohl
    Niederschlag korrekt anliegt. ARPAE deckt denselben Punkt geometrisch
    ab und fuehrt weather_code nativ; hier NUR als Sidecar genutzt, NICHT
    als Fallback-Quelle (PO-Entscheidung 2026-09-20).
    """
    frames = self._fetch_arome_france_hd(lat, lon, elevation_m)
    if not frames:
        return frames
    sidecar = self._fetch_italy_arpae(lat, lon, elevation_m)
    if sidecar:
        self._merge_convective(frames, sidecar)
    else:
        # ADR-0018 / Muster aus _fetch_geosphere_inca: ein gescheiterter
        # Sidecar-Call darf NIE lautlos als "kein Gewitter" gelten.
        self._convective_checked = False
    return frames
```

### 5. `tests/tdd/test_feature_734_arome_france_nowcast.py` — bestehende Erwartung ändern

`test_ac1_arome_france_real_fetch_returns_arome_source` und
`test_ac2_chain_routing_berlin_radar_atlantic_global` erwarten für Korsika (42.18/9.0) heute
`source == "ARPAE-2I"` (so gesetzt durch #1648) — muss auf `source == "AROME-FR"` geändert
werden, Docstrings entsprechend („Italien-Radar-Box vor AROME-FR" → „Korsika-Box vor
Italien-Radar-Box"). `test_ac2_within_arome_france_bbox` bleibt unverändert (die AROME-FR-Box
selbst ändert sich nicht, nur die Prüfreihenfolge davor).

### 6. `docs/specs/modules/radar_nowcast.md` — Known-Limitations-Zeile

Die Zeile „Für Italien (inkl. Korsika, PO-Entscheidung 2026-07-09) liefert seit Issue #1648
ausschließlich ARPAE ICON-2I … den Nowcast" wird korrigiert: Korsika hat jetzt einen eigenen,
vorgeschalteten Zweig (AROME-FR + ARPAE-Sidecar), Italien (ohne Korsika) bleibt bei ARPAE.
Neue Changelog-Zeile, keine stillschweigende Überschreibung — die alte Aussage war zum
damaligen Zeitpunkt zutreffend dokumentiert (siehe dortiger Changelog-Eintrag 2026-07-09).

### 7. `docs/specs/modules/radar_nowcast_france.md` — Changelog-Ergänzung

AC-1 dieser Spec behauptet bereits seit 2026-06-11, dass Korsika über AROME-FR läuft — das war
durch die Box-Reihenfolge nie tatsächlich erreichbar. Changelog-Zeile ergänzen: mit #1761 wird
diese Aussage für Korsika erstmals real eingelöst (inkl. ARPAE-Sidecar für Konvektion, was die
ursprüngliche AC-1-Fassung noch nicht vorsah).

## Expected Behavior

- **Input:** Koordinate innerhalb der Korsika-Box (41,30–43,11 N / 8,39–9,60 O).
- **Output:** `NowcastResult.source == "AROME-FR"`, Niederschlags-Frames aus AROME-FR (1,5 km),
  `is_convective`/`hail` aus dem ARPAE-Sidecar übernommen (Toleranz 5 Min); bei Sidecar-Ausfall
  `convective_checked == False` statt einem stillen `False`.
- **Side effects:** ein zusätzlicher `_fetch_openmeteo_15`-Aufruf pro Korsika-Nowcast (Sidecar)
  — läuft durch denselben budget-gegateten Funnel wie bisher (#1329 C2), keine neue
  Drosselungslogik nötig.

## Acceptance Criteria

- **AC-1:** Given die reale Korsika-Koordinate Vizzavona (42,1244/9,1339) / When
  `RadarNowcastService.get_nowcast()` ohne Dependency-Injection läuft / Then ist
  `result.source == "AROME-FR"` (nicht mehr `"ARPAE-2I"`) mit ≥1 realem Frame, dessen
  `precip_mm_h` numerisch ≥ 0 ist.
  - Test: aktualisierter `test_ac1_arome_france_real_fetch_returns_arome_source` (live) in
    `test_feature_734_arome_france_nowcast.py`. Kein Mock.

- **AC-2:** Given ein AROME-FR-Frame ohne `weather_code` (strukturell, echter Live-Fall) und ein
  ARPAE-Sidecar-Frame mit `weather_code=96` zum selben Zeitpunkt (±5 Min, echte `RadarFrame`-
  Objekte per Instanzmethoden-Ersatz statt Fetch) / When `_fetch_corsica_arome_fr` beide
  zusammenführt / Then trägt der zurückgegebene AROME-Frame `is_convective=True`, `hail=True`
  — übernommen aus dem ARPAE-Sidecar, nicht aus AROME selbst.
  - Test: DI-Ersatz von `_fetch_arome_france_hd` und `_fetch_italy_arpae` durch echte
    Funktionen, die feste `RadarFrame`-Listen zurückgeben (kein `Mock`/`patch`). Assert
    `frames[i].is_convective is True` und `hail is True`.

- **AC-3:** Given AROME-FR liefert Niederschlags-Frames, aber der ARPAE-Sidecar-Fetch liefert
  `[]` (simulierter Ausfall via Instanzmethoden-Ersatz) / When `_fetch_corsica_arome_fr` läuft /
  Then bleiben die AROME-Niederschlags-Frames erhalten, `RadarNowcastService._convective_checked`
  wird `False`, und `NowcastResult.convective_checked` sowie der gerenderte `format_now_text`-
  Satz ("Gewitter-Check nicht verfügbar.") spiegeln den Ausfall — kein stilles "kein Gewitter"
  (ADR-0018).
  - Test: deterministisch, DI-Ersatz von `_fetch_italy_arpae` durch eine Funktion, die `[]`
    liefert. Assert `result.convective_checked is False` und der Text enthält den Hinweis.

- **AC-4:** Given eine Korsika-Koordinate (z. B. Conca, GR20-Ostküste, 41,7481/9,3548) / When
  sowohl `_region_bucket` als auch `_within_corsica` ausgewertet werden / Then liefern beide
  konsistent "Korsika" (`_region_bucket(lat, lon) == "corsica"` UND `_within_corsica(lat, lon)
  is True`) — Cache-Schlüssel und tatsächlich abgerufene Quelle divergieren nicht (Adversary-
  Risiko: nur eine der beiden Stellen geändert).
  - Test: pure-function Assert für dieselbe Koordinate, kein Netz.

- **AC-5:** Given zwei Koordinaten unmittelbar beidseits der Straße von Bonifacio (41,30/9,00 =
  Korsika-Südspitze, INKLUSIVE; 41,29/9,00 = Sardinien, AUSSERHALB) / When `_within_corsica` und
  `_region_bucket` ausgewertet werden / Then wird ausschließlich die nördliche Koordinate als
  Korsika (`"corsica"`) klassifiziert, die südliche bleibt unverändert im Italien-Bucket
  (`"italy_radar"`) — Sardinien wird nicht mitgenommen.
  - Test: parametrisierter Grenzwerttest, kein Netz.

- **AC-6:** Given eine Korsika-Koordinate, bei der `_fetch_arome_france_hd` künstlich `[]`
  liefert (Instanzmethoden-Ersatz, simulierter AROME-Ausfall) / When `_fetch_frames_with_fallback`
  läuft / Then fällt die Kette auf den vollen Italien-Zweig zurück (`source == "ARPAE-2I"` über
  den regulären `_fetch_italy_arpae`-Aufruf), NICHT direkt auf `minutely_15` — dieselbe
  Ausfalltiefe wie vor der Änderung.
  - Test: DI-Ersatz von `_fetch_arome_france_hd` durch eine Funktion, die `[]` liefert; assert
    `source == "ARPAE-2I"`.

- **AC-7 (Regressionsschutz):** Given die bestehenden `_ITALY_RADAR_LAT_MIN/_MAX/_LON_MIN/_MAX`-
  Konstanten und `DpcSource.covers()` / When der Korsika-Fix eingebaut ist / Then bleibt
  `tests/tdd/test_dpc_official_alert_bbox.py` unverändert grün, insbesondere
  `DpcSource().covers(42.1244, 9.1339) is True` — die amtliche italienische Warnzuständigkeit
  für Korsika ändert sich nicht.
  - Test: bestehender Test, keine Codeänderung an `_ITALY_RADAR_*` oder `dpc.py` nötig; Kern-
    Testlauf muss ihn unverändert grün zeigen.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion |
|----|--------------|
| AC-1 | `test_feature_734_arome_france_nowcast.py::test_ac1_arome_france_real_fetch_returns_arome_source` (MODIFY), `::test_ac2_chain_routing_berlin_radar_atlantic_global` (MODIFY) |
| AC-2 | `test_fix_1761_korsika_arome_sidecar.py::test_ac2_sidecar_merges_convective_from_arpae` |
| AC-3 | `test_fix_1761_korsika_arome_sidecar.py::test_ac3_sidecar_failure_sets_convective_checked_false` |
| AC-4 | `test_fix_1761_korsika_arome_sidecar.py::test_ac4_region_bucket_matches_within_corsica` |
| AC-5 | `test_fix_1761_korsika_arome_sidecar.py::test_ac5_sardinia_boundary_excluded` |
| AC-6 | `test_fix_1761_korsika_arome_sidecar.py::test_ac6_arome_failure_falls_back_to_arpae` |
| AC-7 | `tests/tdd/test_dpc_official_alert_bbox.py` (unverändert, Regressionswächter); zusätzlich betroffen (Adversary-Finding F001): `tests/tdd/test_radar_nowcast_italy_arpae_only.py::test_ac1_italy_mainland_uses_arpae_with_future_frames` (Koordinatentausch, siehe Dependencies) |

Neue Testdatei: `tests/tdd/test_fix_1761_korsika_arome_sidecar.py` (mock-frei, DI via
Instanzmethoden-Ersatz mit echten Objekten, Muster aus `test_issue_1161_inca_convective.py`).

## Known Limitations

- AROME-FR liefert an Korsika-Koordinaten weiterhin STRUKTURELL keinen `weather_code`
  (Open-Meteo-seitige Einschränkung, kein Bug bei uns) — die Gewitter-/Hagel-Erkennung hängt
  vollständig vom ARPAE-Sidecar ab. Fällt ARPAE zur selben Zeit aus, in der AROME-FR erfolgreich
  liefert, ist die Konvektionsprüfung für diesen einen Aufruf unbeantwortet
  (`convective_checked=False`), nicht falsch-negativ.
- Der Sidecar-Merge kostet einen zweiten `_fetch_openmeteo_15`-Aufruf pro Korsika-Nowcast
  (doppelter Verbrauch gegenüber dem reinen ARPAE-Pfad vor #1761) — geteilt mit dem
  budget-gegateten Funnel (#1329 C2), keine separate Drosselung.
- Die Korsika-Box ist eigenständig und deckt sich NICHT mit der gesamten AROME-FR-Box
  (`_within_arome_france`) — sie ist eine engere, real gemessene Teilmenge. Koordinaten
  außerhalb der Korsika-Box, aber innerhalb der AROME-FR-Box (Festland-Frankreich, Alpen,
  Pyrenäen), sind von diesem Fix nicht betroffen und laufen unverändert ohne Sidecar auf
  reinem AROME-FR.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Fail-soft ohne Kaschieren) + ADR-0041 Muster C (Rechteck-Vorfilter mit
  nachgelagertem Filter) — **kein neues ADR**.
- **Rationale:** ADR-0018 deckt bereits exakt das hier verwendete Sidecar-Fail-soft-Muster ab
  (`_convective_checked=False` bei Sidecar-Ausfall, wortgleich zum bestehenden INCA-Pfad).
  ADR-0041 Muster C rechtfertigt, dass die Italien-Box (`_ITALY_RADAR_*`) als grober Vorfilter
  für `DpcSource.covers()` unangetastet bleiben darf, weil die neue Korsika-Prüfung VOR ihr
  greift, ohne sie selbst zu verändern. Diese Spec fügt keine neue Architektur-Entscheidung
  hinzu, sondern wendet zwei bestehende auf einen neuen Fall an.

## Changelog

- 2026-09-20: Initial spec created (Issue #1761), inkl. PO-Entscheidung Sidecar-Merge
  (Variante 2) statt reiner Umschaltung.
- 2026-09-20: Scope-Nachtrag — Adversary-Finding F001: Test `test_radar_nowcast_italy_arpae_only.py`
  durch Korsika-Koordinaten-Umlenkung betroffen; Fix via Koordinaten-Umbau (Variante a). Zusätzliche
  Testdatei + dritte Spec-Datei (`fix_1648_radar_dpc_entfernen.md`) geändert. Übersteigt ursprüngliche
  Estimated Scope (2 Spec-Dateien → 3, +1 Testdatei unerwartet).
