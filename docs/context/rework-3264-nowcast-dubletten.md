# Context: rework-3264-nowcast-dubletten

## Request Summary
Issue #3264 (Teil von #1196, abgespalten aus #3208, Gruppe G5 Nowcast/Radar): die Testdateien
656/660 (`intensity_to_text`) und 734/761 (Routing-Kette) auf doppelte Zusicherungen prüfen und
Dopplungen entfernen. Kriterium wie #3208 (`docs/context/rework-3208-doppelte-tests.md`): entfernt wird
nur, was identisch ist (Funktion + Eingabe + Erwartung) oder echte Teilmenge einer bleibenden
Zusicherung; „ähnlich" (andere Schicht, andere Werte, anderer Eingangsweg) bleibt.
Je Gruppe Mutationsnachweis vorher/nachher, Kern-Schicht 100 % grün.

## Related Files
| File | Relevance |
|------|-----------|
| tests/tdd/test_feature_656_radar_nowcast.py (313) | `test_ac2_intensity_to_text_levels` (Z. 118–126): 4 Stufen über Default-Argument |
| tests/tdd/test_feature_660_convective_stage.py (245) | `test_ac1_intensity_non_convective_unchanged` (Z. 112–122): dieselben 4 Raten mit `is_convective=False` + Default bei 8.0 |
| tests/tdd/test_feature_734_arome_france_nowcast.py (175) | `test_ac2_chain_routing_berlin_radar_atlantic_global` (live): Korsika/Berlin/Atlantik |
| tests/tdd/test_feature_761_icon_d2_nowcast.py (158) | `test_ac2_chain_routing_precedence` (xfail #1144, strict=False): Slowenien/Berlin/Schweiz-West/Atlantik |
| src/services/radar_service.py:627–647 | `intensity_to_text(mm_per_h, is_convective=False, hail=False)` — Produktionsstelle G5a |
| src/services/radar_service.py (`get_nowcast`) | Routing-Kette RADOLAN→…→global — Produktionsstelle G5b |

## Existing Patterns
- Methode und Kriterium aus #3208/#3263 (Mutation per String-Ersetzung mit externer Sicherungskopie,
  nie `git checkout/stash/reset`), Mutationsprotokoll vorher/nachher unter `docs/artifacts/`.

## Dependencies
- Upstream: nur Testcode; Produktionscode unverändert.
- Downstream: Spec-Tabellen nennen Testnamen: `docs/specs/modules/radar_nowcast.md:102`
  (`test_ac2_intensity_to_text_levels` bei AC-2) → Verweis auf den bleibenden 660-Test umstellen;
  `docs/specs/modules/radar_nowcast_icon_d2.md:121` (`test_ac2_chain_routing_precedence`, bleibt bestehen).
  `docs/specs/_archive/...` ist Archiv, bleibt unverändert.

## Existing Specs
- `docs/specs/modules/radar_nowcast.md`, `radar_nowcast_icon_d2.md`, `radar_nowcast_france.md`.

## Analysis (Summe 1: Kontext und Analyse in einem Durchgang, selbst gegen Quelltext geprüft 2026-11-23)

### G5a — 656/660 `intensity_to_text`: echte Teilmenge
- `656::test_ac2_intensity_to_text_levels` ruft `intensity_to_text(r)` für r ∈ {0.0, 0.3, 2.5, 8.0}.
- `660::test_ac1_intensity_non_convective_unchanged` ruft `intensity_to_text(r, is_convective=False)` für
  dieselben vier Raten mit denselben Erwartungen, plus `intensity_to_text(8.0)` über das Default-Argument.
- Default ist `is_convective=False` (radar_service.py:628) → Aufruf mit Default ≡ Aufruf mit `False`.
  Der Default-Pfad selbst bleibt durch Z. 122 in 660 bewacht (Mutation Default→True fängt 660).
- ⇒ 656-Test ist echte Teilmenge → **entfernen**; Spec-Verweis `radar_nowcast.md:102` auf
  `test_feature_660_convective_stage.py::test_ac1_intensity_non_convective_unchanged` umstellen.

### G5b — 734/761 Routing-Kette: zwei wörtlich gleiche Asserts
- `get_nowcast(_BERLIN) == "radar"` und `get_nowcast(_ATLANTIC) == "minutely_15"` stehen identisch
  (gleiche Koordinaten 52.52/13.40 bzw. 35.0/−40.0) in beiden Kettentests.
- Bleibt in 734 (live, wirksam); in 761 steht der Test unter `xfail(strict=False)` (#1144), dort fangen
  diese Asserts ohnehin nichts. ⇒ **Berlin- und Atlantik-Assert aus 761 entfernen**; Slowenien und
  Schweiz-West (AROME-Vorrang vor ICON-D2) bleiben, Docstring anpassen.
- Der „dritte" gleiche Assert aus #3208 ist nach strengem Kriterium **kein** Duplikat:
  `ac4_*_convective_drives_intensity` (734/761) prüft `is_convective`/`intensity_label` mit anderer Quelle
  ("AROME-FR" vs "ICON-D2") und anderen Raten (0.3/2.0 vs 0.4/3.0) → ähnlich, bleibt.
  Ebenso `within(_ATLANTIC) is False`: andere Funktion (`_within_arome_france` vs `_within_icon_d2`) → bleibt.

### Weiteres in 656/660 geprüft — bleibt
- 656 `ac4_radar_alert_*` ↔ 660 `ac4_radar_alert_convective_marked_once_then_throttles`: anderer Fall (konvektiv).
- 656 `format_now_text_*` ↔ 660 `ac3_derive_result_convective_label_and_text`: andere Eingaben.

### Nebenbefund (nicht in diesem Ticket)
- `761::test_ac4_icon_d2_convective_drives_intensity` trägt `@pytest.mark.live` samt Kommentar
  „Dialt real Open-Meteo/AROME", ist aber deterministisch (`_derive_result` mit festen Frames) → läuft nur in
  der Live-Schicht statt im Kern. → Sammel-Issue #1199.
- `761::test_ac2_chain_routing_precedence` macht echte Netzaufrufe ohne `live`-Marker; `xfail` verdeckt das.

## Risks & Considerations
- Mutationsnachweis G5b nur in der Live-Schicht beobachtbar (734-Test ist `live`), Messung mit `-m live`.
- Kern-Schicht der vier Dateien muss 100 % grün bleiben.

## Analysis (Phase 2, 2026-11-23 — Befunde aus Summe 1 gegen Quelltext erneut bestätigt)

### Type
Rework (Test-Bereinigung, kein Produktionscode)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_feature_656_radar_nowcast.py | MODIFY | `test_ac2_intensity_to_text_levels` entfernen (echte Teilmenge von 660 `test_ac1_intensity_non_convective_unchanged`) |
| tests/tdd/test_feature_761_icon_d2_nowcast.py | MODIFY | in `test_ac2_chain_routing_precedence` Berlin- und Atlantik-Assert entfernen, Docstring anpassen; Konstante `_BERLIN_LAT/_LON` (Z. 30) wird danach unbenutzt → mit entfernen. `_ATLANTIC_*` bleibt (Z. 71 `within`) |
| docs/specs/modules/radar_nowcast.md:102 | MODIFY | AC-2-Verweis auf `test_feature_660_convective_stage.py::test_ac1_intensity_non_convective_unchanged` umstellen |
| docs/specs/modules/radar_nowcast_icon_d2.md:121 | — | bleibt (Testname besteht weiter) |
| docs/artifacts/rework-3264-nowcast-dubletten/ | CREATE | Mutationsprotokoll vorher/nachher (G5a Kern, G5b Live) |

### Scope Assessment
- Files: 3 MODIFY + 1 Artefakt
- Estimated LoC: +~5 / −~20
- Risk Level: LOW (nur Testcode, jede entfernte Zusicherung bleibt an anderer Stelle bewacht)

### Technical Approach
1. Mutationsnachweis VORHER: G5a — Mutation in `intensity_to_text` (z. B. Schwelle 2.5→„Leichter Regen“, Default `is_convective=False→True`) muss von 656 UND 660 gefangen werden; G5b — Mutation RADOLAN-Box/Global-Fallback in `get_nowcast` muss von 734 (`-m live`) gefangen werden. Mutation per String-Ersetzung mit externer Sicherungskopie.
2. Entfernen wie oben.
3. Mutationsnachweis NACHHER: dieselben Mutationen werden weiterhin gefangen (660 bzw. 734).
4. Kern-Schicht der vier Dateien 100 % grün (benannte Dateien, `-m "not live"`).

### Dependencies
Keine Produktionsabhängigkeiten; nur Spec-Testverweise (s. o.).

### Open Questions
- keine (Kriterium aus #3208 übernommen, PO-Freigabe betrifft nur die Spec)
