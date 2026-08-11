---
entity_id: feat_1679_lpi_schwellen_region_tabelle
type: feature
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [gewitter, lpi, model-registry, thunder-fusion, issue-1679]
---

# LPI-Blitzpotenzial bekommt eine belegte, gebietsabhängige Schwellenleiter statt der interpolierten 5/20/50 (Issue #1679, LPI-Teil)

## Approval

- [x] Approved

## Purpose

Die Gewitter-Fusion (`thunder_level_from_signals()`) übersetzt das DWD-Blitzpotenzial (LPI,
J/kg) heute über EINE feste, gebietsblinde Leiter (5/20/50 J/kg), deren mittlere Schwelle (20)
nicht belegt, sondern interpoliert ist. Bína et al. (Atmospheric Research 2022 / ASR Copernicus
2022, COSMO-D2 — dieselbe Modellfamilie wie ICON-D2) belegen stattdessen durchgehend **1/30/50
J/kg**. Eine reine Konstanten-Änderung wäre jedoch falsch: Das Europa-Lückenfüller-Modell
ICON-EU (`lpi_con_max`) teilt sich heute dieselbe Leiter wie ICON-D2, liefert aber strukturell
deutlich höhere Werte (gemessener Faktor 51× am unteren Ende, Issue #1678) — eine globale
Umstellung auf 1/30/50 würde die Fehlalarmquote für jeden Ort außerhalb Alpen/Frankreich sofort
verschlechtern. Diese Scheibe löst das durch eine **gebietsabhängige Tabelle** nach dem
bestehenden, bereits produktiv gehärteten Muster `model_registry.CAPE_THRESHOLDS_JKG`
(Issue #1592/ADR-0048): das ICON-D2-Gebiet (DE_ALPEN) bekommt sofort die belegte 1/30/50-Leiter,
das ICON-EU-Gebiet (EU_REST) bleibt unverändert auf 5/20/50, bis Issue #1678 dafür eine eigene,
eingemessene Leiter liefert.

**Bewusst NICHT Teil dieser Scheibe:** die CIN-Paarung aus #1679 (hängt an #1531, liefert
`cin_ml`, eigene Spec-Freigabe offen), die eigene Eichung für ICON-EU/`lpi_con_max` (#1678 —
diese Scheibe liefert nur die Tabellen-Infrastruktur mit dem unveränderten Interim-Wert für
`EU_REST`) und die Herkunfts-Anzeige der Stufe im Ortsvergleich (#1680).

## Source

- **File:** `src/app/model_registry.py`, `src/output/metric_format.py`,
  `src/providers/thunder_enrichment.py`
- **Identifier:** `LPI_THRESHOLDS_JKG` / `lpi_thresholds_jkg()` (beide neu,
  `model_registry.py`), `thunder_level_from_signals()` (Signaturänderung, drei neue
  keyword-only Parameter, `metric_format.py`), `_fuse_thunder_levels()`/`enrich_thunder()`
  (Signaturänderung bzw. Erweiterung, `thunder_enrichment.py`)

**Schicht:** ausschließlich Python-Core (`src/app/`, `src/output/`, `src/providers/`). Kein Go,
kein Frontend — LPI ist keine wählbare Metrik (wie CAPE/Blitzdichte auch), diese Scheibe ändert
nur die interne Schwellen-Bestimmung, keine Bedienoberfläche.

## Estimated Scope

- **LoC:** ~70-100 Quellcode (neue Tabelle + Lookup-Funktion, Parameter-Erweiterung an zwei
  Funktionen, Entfernung von drei Modul-Konstanten, Kommentar-Aktualisierung) + ~60-100 Tests
  (überwiegend mechanische Ein-Parameter-Ergänzungen, s. Implementation Details) ≈ **130-200
  gesamt** — voraussichtlich unter dem 250-LoC-Workflow-Limit, aber knapp genug, dass der
  tatsächliche Testumfang beim Implementieren geprüft werden sollte; reißt es,
  `workflow.py set-field loc_limit_override 500` mit PO-Freigabe vor Fortsetzung.
- **Files:** 3 geändert (Quellcode), 8 Testdateien angepasst (0 neu, 0 gelöscht). Die
  Testdatei-Liste ist gegenüber dem Kontext-Dokument **korrigiert und erweitert** — s.
  „Scope-Korrektur" in Implementation Details.
- **Effort:** medium — das Muster selbst ist 1:1 aus #1592/ADR-0048 übernommen (kein neuer
  Mechanismus), aber der Blast Radius reicht über mehr Aufrufstellen von
  `_fuse_thunder_levels()` als in der Analyse-Phase erfasst, weil auch diese interne Funktion
  einen neuen Pflichtparameter ohne Default bekommt (Konsistenz-Anforderung aus #1592 C1: „kein
  stiller Rückfall gilt auf der GANZEN Kette").

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5b/3.7 | bindender Rahmen | Beleg-Quelle für 1/30/50 J/kg (Bína et al.); Abschnitt 3.7 nennt ICON-EU explizit als „eigene Leiter — zu eichen", bis dahin nicht gleichwertig |
| ADR-0048 | Vorbild/Referenz | „Modellabhängige Schwellen statt einer Zahl" — dieselbe Grundsatzentscheidung, hier zum zweiten Mal angewendet (erstmals CAPE, jetzt LPI) |
| `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` | Vorbild-Spec | exaktes Muster: Region-Tabelle statt globaler Konstante, keyword-only ohne Default, einmalige Auflösung je Reihe in `enrich_thunder()` |
| `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md` | Vorgänger-Scheibe, wird hier PRÄZISIERT | führte `lightning_potential_jkg` als viertes Fusions-Signal mit der globalen 5/20/50-Leiter ein; diese Scheibe ersetzt die globale Leiter durch die Region-Tabelle, ohne `_thunder_level_from_ladder()` (die geteilte Übersetzungslogik, DRY-Pflicht #1481) anzufassen |
| `providers.thunder_routing._REGIONS`/`thunder_region_for()` | bestehende Infrastruktur, unverändert genutzt | liefert das Gebiet, das für LPI das liefernde Modell bereits eindeutig festlegt (DE_ALPEN → ICON-D2, EU_REST → ICON-EU) — kein zweites Raster, anders als bei CAPE genügt hier die Region allein als Tabellenschlüssel (kein `model_id` nötig) |
| Issue #1678 | Folgearbeit, NICHT Teil dieser Scheibe | eigene, eingemessene ICON-EU-Leiter; diese Scheibe liefert nur die Tabellen-Infrastruktur mit dem unveränderten Interim-Wert für `EU_REST` |
| Issue #1531 | explizit AUSSER Scope | CIN-Paarung des Gesamt-Issues #1679, hängt an einem eigenen `cin_ml`-Feld |
| Issue #1680 | explizit AUSSER Scope | Herkunfts-Anzeige der Stufe im Ortsvergleich |

## Implementation Details

### 1. Neue Tabelle + Lookup in `model_registry.py` (Vorbild `CAPE_THRESHOLDS_JKG`)

```python
# Blitzpotenzial-Schwellen je Gebiet (Issue #1679). Belegt: Bina et al.,
# Atmospheric Research 2022 / ASR Copernicus 2022, COSMO-D2 (2,2 km,
# dieselbe Modellfamilie wie ICON-D2): "skilful forecast ... for LPI
# thresholds 30, 40 and 50 J/kg", Nachweisschwelle "LPI > 1 J/kg".
# EU_REST: UNVERAENDERTER Interim-Wert (5/20/50) -- ICON-EU (lpi_con_max)
# liefert strukturell deutlich hoehere Werte als ICON-D2 (Faktor 51x am
# unteren Ende, Issue #1678); eine eigene, eingemessene Leiter folgt dort.
# FR bekommt bewusst KEINEN Eintrag -- AROME liefert dort Blitzdichte,
# kein LPI (thunder_routing._REGIONS).
LPI_THRESHOLDS_JKG: Dict[str, Tuple[float, float, float]] = {
    "DE_ALPEN": (1.0, 30.0, 50.0),
    "EU_REST": (5.0, 20.0, 50.0),
}


def lpi_thresholds_jkg(region: Optional[str]) -> Optional[Tuple[float, float, float]]:
    """(low, med, high)-Schwellenleiter fuer Blitzpotenzial (LPI, J/kg) je
    Gebiet. `None`, wenn `region` `None` ist oder keine Kalibrierung fuer
    das Gebiet vorliegt (z.B. FR) -- beide Faelle identisch "nicht belegt"
    (analog `cape_threshold_jkg()`)."""
    if region is None:
        return None
    return LPI_THRESHOLDS_JKG.get(region)
```

### 2. `metric_format.py` — drei neue keyword-only Parameter ohne Default, alte Konstanten entfernt

Die Modul-Konstanten `_LIGHTNING_POTENTIAL_LOW_MIN/MED_MIN/HIGH_MIN` (Zeilen 284-293, inkl. des
Kommentars „20 J/kg NICHT publiziert, interpoliert") werden **entfernt** — nicht als stiller
Fallback erhalten. An ihrer Stelle bleibt ein kurzer Verweis auf die neue Tabelle:

```python
# Blitzpotenzial-Schwellen: seit Issue #1679 region-abhaengig, siehe
# `app.model_registry.LPI_THRESHOLDS_JKG`/`lpi_thresholds_jkg()`. Keine
# globale Konstante mehr hier -- ein Aufrufer ohne aufgeloeste Region
# bekommt bewusst KEIN Signal statt einer falschen Schwelle.
```

`thunder_level_from_signals()` bekommt drei neue keyword-only Parameter OHNE Default (exaktes
Muster von `cape_threshold_jkg` seit #1592 C1):

```python
def thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
    *,
    cape_threshold_jkg: Optional[float],
    lpi_low_min: Optional[float],
    lpi_med_min: Optional[float],
    lpi_high_min: Optional[float],
) -> Optional[ThunderLevel]:
    ...
    if (lightning_potential_jkg is not None
            and lpi_low_min is not None
            and lpi_med_min is not None
            and lpi_high_min is not None):
        signals.append(_thunder_level_from_ladder(
            lightning_potential_jkg, lpi_low_min, lpi_med_min, lpi_high_min,
        ))
```

`_thunder_level_from_ladder()` selbst bleibt UNVERÄNDERT (DRY-Pflicht #1481, geteilte
Übersetzungslogik) — nur welche drei Zahlen hineingereicht werden, ändert sich.

### 3. `thunder_enrichment.py` — Region einmal je Reihe auflösen, für CAPE UND LPI mitnutzen

`_fuse_thunder_levels()` bekommt einen dritten Pflichtparameter (ein Tupel statt drei Einzelwerte,
um die Zahl der Aufrufstellen-Änderungen klein zu halten — die drei-Parameter-Aufteilung ist nur
an der öffentlichen Grenze `thunder_level_from_signals()` gefordert):

```python
def _fuse_thunder_levels(
    data: list,
    cape_threshold_jkg: Optional[float],
    lpi_thresholds: Optional[Tuple[float, float, float]],
) -> None:
    from output.metric_format import thunder_level_from_signals

    lpi_low, lpi_med, lpi_high = lpi_thresholds or (None, None, None)
    for dp in data:
        fused = thunder_level_from_signals(
            dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
            dp.lightning_potential_lpi_jkg,
            cape_threshold_jkg=cape_threshold_jkg,
            lpi_low_min=lpi_low, lpi_med_min=lpi_med, lpi_high_min=lpi_high,
        )
        if fused is not None:
            dp.thunder_level = fused
```

`enrich_thunder()` löst die Region EINMAL auf und nutzt sie für BEIDE Lookups (CAPE war bereits
so implementiert, LPI dockt an dieselbe Auflösung an — kein zweiter Auflösungs-Ort):

```python
from app.model_registry import (
    cape_threshold_jkg, effective_cape_model_id, lpi_thresholds_jkg,
)
from providers.thunder_routing import thunder_region_for

region = thunder_region_for(location.latitude, location.longitude)
schwelle = cape_threshold_jkg(effective_cape_model_id(reihe.meta), region)
lpi_leiter = lpi_thresholds_jkg(region)

_fuse_thunder_levels(reihe.data, schwelle, lpi_leiter)
```

### Scope-Korrektur gegenüber dem Kontext-Dokument (wichtig)

Die Analyse-Phase (`docs/context/gewitter-1679-lpi-schwellen.md`) listet nur zwei anzupassende
Testdateien (`test_dwd_eu_thunder_signal_fetch.py`,
`test_thunder_ladder_shared_across_signals.py`) und drei „CHECK"-Dateien. Eine Verifikation
gegen den Code (`grep -rn "_fuse_thunder_levels(" --include="*.py" .`) zeigt: **drei weitere
Testdateien rufen `_fuse_thunder_levels()` direkt mit nur zwei Argumenten auf** und brechen mit
`TypeError`, sobald der dritte Pflichtparameter eingeführt wird — sie fehlten in der
Analyse-Liste komplett:

| Datei | Aufrufstellen | Nötige Änderung |
|---|---|---|
| `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py` | 4 (`_fuse_thunder_levels(x, None)` an vier Stellen) | drittes Argument `None` ergänzen |
| `tests/tdd/test_hail_flag_wmo_signal.py` | 2 | drittes Argument `None` ergänzen |
| `tests/tdd/test_hail_no_advice_text_and_thunder_level_guard.py` | 2 | drittes Argument `None` ergänzen |

Für die von der Analyse bereits erkannten `thunder_level_from_signals()`-Direktaufrufer gilt:
Dateien mit bestehendem `_fusion()`/`_call()`-Wrapper (`test_thunder_level_from_signals_fusion.py`,
9 Aufrufstellen in 8 Testfunktionen; `test_thunder_potential_level_classification.py`) brauchen
NUR eine Änderung am Wrapper selbst — die einzelnen Testaufrufe bleiben unangetastet:

- `test_thunder_level_from_signals_fusion.py`: `_fusion()` ergänzt
  `kwargs.setdefault("lpi_low_min", None)` (und `lpi_med_min`/`lpi_high_min`) — die neun
  bestehenden Aufrufe testen ausschließlich Blitzdichte/CAPE/„keine Aussage", LPI soll dort
  ohnehin nicht mitzählen (Regressionsanker, s. AC-3-Nachbarschaft weiter unten).
- `test_thunder_potential_level_classification.py`: `_fusion()` ergänzt STATTDESSEN
  `kwargs.setdefault(...)` mit den ECHTEN `EU_REST`-Werten aus
  `model_registry.lpi_thresholds_jkg("EU_REST")` (nicht `None`) — diese Datei testet genau die
  LPI-Ladder-Werte und wird damit zum AC-3-Regressionsanker (s. u.), ohne dass ihre acht
  Prüfwerte sich ändern müssen.
- `test_cape_not_selectable.py` (2 Aufrufstellen, kein Wrapper): jede Stelle einzeln um
  `lpi_low_min=None, lpi_med_min=None, lpi_high_min=None` ergänzen.
- `test_dwd_eu_thunder_signal_fetch.py` (Zeilen 361-395): Import der drei entfernten
  Modul-Konstanten ersetzen durch `model_registry.lpi_thresholds_jkg("EU_REST")`; der Import von
  `_thunder_level_from_ladder` bleibt gültig (diese Funktion wird nicht angefasst).
- `test_thunder_ladder_shared_across_signals.py` (Zeilen 44-112): dieselbe Ersetzung — die drei
  `mf._LIGHTNING_POTENTIAL_*`-Referenzen weichen einem `model_registry.lpi_thresholds_jkg(...)`-
  Lookup; welche Region dabei verwendet wird, ist für diesen strukturellen DRY-Test beliebig,
  `EU_REST` hält die Werte am nächsten am bisherigen Stand.

## Expected Behavior

- **Input:** ein LPI-Rohwert (`lightning_potential_lpi_jkg`) an einem Datenpunkt, plus die über
  `thunder_region_for(location.latitude, location.longitude)` aufgelöste Region.
- **Output:** `dp.thunder_level` spiegelt die gebietsabhängige Einstufung — im DE_ALPEN-Gebiet
  eskaliert LPI jetzt bereits ab 1 J/kg (vorher 5), im EU_REST-Gebiet bleibt die Einstufung bei
  5/20/50 unverändert, im FR-Gebiet trägt LPI weiterhin kein Signal bei (unverändert, da AROME
  kein LPI liefert).
- **Side effects:** keine neuen Abrufe, keine neuen Felder — reine Umstellung der
  Schwellen-Quelle, analog zu #1592 C1 bei CAPE.

## Acceptance Criteria

- **AC-1 (Tabelle + Lookup — zwei Einträge, FR bewusst ausgespart):** Given
  `model_registry.LPI_THRESHOLDS_JKG` nach dieser Änderung / When sie gegen die drei
  Regionsnamen aus `thunder_routing._REGIONS` (`"FR"`, `"DE_ALPEN"`, `"EU_REST"`) sowie `None`
  geprüft wird / Then trägt sie GENAU zwei Einträge (`"DE_ALPEN": (1.0, 30.0, 50.0)`,
  `"EU_REST": (5.0, 20.0, 50.0)`), `lpi_thresholds_jkg("FR")` liefert `None`,
  `lpi_thresholds_jkg(None)` liefert ebenfalls `None`.
  - Test: Tabelleninhalt direkt geprüft (Länge, Schlüssel, Werte) plus Lookup für alle vier
    Eingaben (drei Regionsnamen + `None`), ohne Netzabruf.
  - Gegenprobe: Bekäme `"FR"` versehentlich einen Eintrag (z. B. Copy-Paste aus
    `CAPE_THRESHOLDS_JKG`, wo FR sehr wohl Einträge hat), läge die Tabellenlänge bei 3 statt 2
    und `lpi_thresholds_jkg("FR")` läge bei einem Tupel statt `None` — der Test muss beides
    fangen.

- **AC-2 (DE_ALPEN — LPI zwischen 1 und 30 J/kg liefert LOW, nicht mehr NONE wie mit der alten
  5er-Schwelle):** Given LPI-Rohwerte 1.0 / 2.0 / 29.9 / 30.0 J/kg im DE_ALPEN-Gebiet
  (ICON-D2-Zuständigkeit) / When `thunder_level_from_signals()` mit den für DE_ALPEN
  aufgelösten Schwellen (`lpi_thresholds_jkg("DE_ALPEN")` = `(1.0, 30.0, 50.0)`) aufgerufen
  wird / Then liefert sie der Reihe nach LOW / LOW / LOW / MED — insbesondere der Wert 2.0 J/kg,
  der mit der alten globalen 5er-Schwelle `NONE` ergeben hätte, liefert jetzt `LOW`.
  - Test: vier Aufrufe mit den genannten Werten und den DE_ALPEN-Schwellen, Rückgaben gegen die
    Tabelle geprüft; zusätzlich ein expliziter Vergleichsaufruf bei 2.0 J/kg mit den ALTEN
    Werten (5.0/20.0/50.0 als Schwellen), der `NONE` liefert — Beweis, dass der Unterschied
    real ist, nicht nur ein anderer Rückgabewert derselben Schwelle.
  - Gegenprobe: Bliebe `enrich_thunder()`/`_fuse_thunder_levels()` fälschlich bei der alten
    globalen 5/20/50-Schwelle (z. B. weil die Region-Auflösung nicht bis zur Fusion durchgereicht
    wird), läge 2.0 unter 5.0 und die Fusion läge bei `NONE` statt `LOW` — der Test muss das
    fangen.

- **AC-3 (EU_REST — unverändert zur alten globalen 5/20/50-Leiter, wichtigster
  Regressionstest):** Given dieselben acht Prüfwerte aus `feat_1474c` AC-1 (4.9 / 5.0 / 19.9 /
  20.0 / 49.9 / 50.0 sowie die PO-Messwerte 88.2 und 0.9 J/kg) im EU_REST-Gebiet / When
  `thunder_level_from_signals()` mit den für EU_REST aufgelösten Schwellen
  (`lpi_thresholds_jkg("EU_REST")` = `(5.0, 20.0, 50.0)`) aufgerufen wird / Then liefert sie
  exakt dieselben acht Ergebnisse wie vor dieser Änderung (NONE/LOW/LOW/MED/MED/HIGH/HIGH/NONE)
  — EU_REST bleibt von der DE_ALPEN-Korrektur unberührt.
  - Test: `tests/tdd/test_thunder_potential_level_classification.py` (bisher globale Werte)
    wird auf die EU_REST-Schwellen umgestellt (s. Implementation Details, Scope-Korrektur) und
    bleibt mit denselben acht Erwartungswerten grün — dieselbe Datei dient als
    Regressionsanker, keine neue Testdatei nötig.
  - Gegenprobe: Bekäme EU_REST versehentlich die neue DE_ALPEN-Leiter (vertauschte
    Dictionary-Zuordnung — GENAU das vom PO in der Analyse benannte Risiko), läge 4.9 J/kg
    fälschlich bei `LOW` statt `NONE` (weil 4.9 ≥ 1.0) — der Test muss das fangen.

- **AC-4 (unbekannte/fehlende Region — kein Signal, kein TypeError, kein stiller Fallback):**
  Given `region=None` (z. B. weil die Koordinaten fehlen) ODER ein unbekannter Regionsname
  (z. B. `"XX"`) / When `lpi_thresholds_jkg(region)` aufgerufen wird / Then liefert sie `None`.
  Given ZUSÄTZLICH ein Aufruf von `thunder_level_from_signals()` mit
  `lpi_low_min=lpi_med_min=lpi_high_min=None` bei einem hohen `lightning_potential_jkg`
  (z. B. 88.2 J/kg), alle anderen Signale `None` / Then liefert die Fusion `None` (keine
  Aussage), NICHT `ThunderLevel.HIGH`.
  - Test: `lpi_thresholds_jkg(None)` und `lpi_thresholds_jkg("XX")` beide `None`;
    Fusionsaufruf mit den drei `None`-Schwellen und `lightning_potential_jkg=88.2` liefert
    `None`.
  - Gegenprobe: Fiele die Implementierung bei fehlender Region auf einen Default-Wert zurück
    (z. B. die alten globalen 5/20/50 als „Sicherheitsnetz"), läge 88.2 weit über 50 und die
    Fusion lieferte fälschlich `HIGH` statt `None` — der Test muss das fangen. Genau das ist der
    Fehler, den das keyword-only-ohne-Default-Muster strukturell verhindern soll.

- **AC-5 (TypeError ohne die neuen Parameter — kein stiller Rückfall über die gesamte Kette):**
  Given ein Aufruf von `thunder_level_from_signals()` OHNE die drei keyword-only Parameter
  `lpi_low_min`/`lpi_med_min`/`lpi_high_min` / When der Aufruf ausgeführt wird / Then bricht er
  mit `TypeError` — exakt das Muster von `cape_threshold_jkg` seit #1592 C1. Given ZUSÄTZLICH
  ein Aufruf von `_fuse_thunder_levels()` ohne den neuen `lpi_thresholds`-Parameter / Then
  bricht auch dieser mit `TypeError` — die Pflicht gilt auf der GANZEN Kette
  (Aufrufer-Grenze UND interner Durchreichungspunkt), nicht nur an der öffentlichen
  Fusionsfunktion.
  - Test: zwei `pytest.raises(TypeError)`-Blöcke, einer je Funktion.
  - Gegenprobe: Bekämen die drei Parameter (an einer der beiden Stellen) versehentlich einen
    Default `= None`, würde der jeweilige Aufruf klaglos durchlaufen (mit stillschweigend
    deaktiviertem LPI-Signal) statt zu brechen — der Test muss das fangen.

- **AC-6 (FR-Gebiet bleibt vom LPI-Ladder-Umbau komplett unberührt):** Given ein Datenpunkt im
  FR-Gebiet (Blitzdichte-Pfad, AROME liefert kein LPI, `lightning_potential_jkg` bleibt
  strukturell `None`) mit gesetzter Blitzdichte / When die Fusion über den regulären
  Produktionspfad (`enrich_thunder()`) läuft / Then bleibt `dp.thunder_level` identisch zum
  Verhalten vor dieser Änderung — ausschließlich Blitzdichte (und ggf. Wettercode/CAPE)
  bestimmen die Stufe.
  - Test: bestehender FR-Regressionstest (Muster
    `test_thunder_enrichment_fuses_level_shared_path.py`, Blitzdichte-Fixture) läuft nach
    dieser Änderung unverändert grün; zusätzlich `lpi_thresholds_jkg("FR")` direkt auf `None`
    geprüft (Wiederholung aus AC-1, hier aber am Produktionspfad statt isoliert).
  - Gegenprobe: Bekäme `"FR"` versehentlich einen Tabelleneintrag (Wiederholung des
    AC-1-Fehlers) UND läge an einem FR-Ort dennoch ein `lightning_potential_jkg`-Wert vor
    (z. B. durch eine fehlerhafte Fallback-Quelle), würde die Fusion plötzlich ein LPI-Signal
    werten, das es vorher nie gab — der Test muss unverändertes Verhalten zeigen.

## Known Limitations

- **EU_REST bleibt bei einer teils interpolierten Leiter.** Die 20-J/kg-Schwelle
  („leicht"→„mittel") ist für ICON-EU weiterhin NICHT publiziert, sondern innerhalb der belegten
  Außengrenzen interpoliert (unverändert seit `feat_1474c`) — Auflösung erst mit #1678.
- **Kein neues Raster.** Der Wirkbereich bleibt vollständig an `thunder_routing._REGIONS`
  gebunden, inklusive dessen bekannter Grenzen (z. B. das ICON-D2-Rechteck ist rund 17 % größer
  als das eigentliche Modellgebiet).
- **Region statt Modell × Region als Schlüssel.** Anders als bei CAPE genügt bei LPI die Region
  allein als Tabellenschlüssel, weil `thunder_routing._REGIONS` das liefernde Modell für LPI
  bereits eindeutig festlegt (DE_ALPEN → ICON-D2, EU_REST → ICON-EU) — das ist bewusst
  einfacher als das CAPE-Muster, kein Fehler.
- **Momentanwert-vs-60-Minuten-Maximum-Unterschied bleibt bestehen.** ICON-D2 liefert LPI als
  Momentanwert, ICON-EU als 60-Minuten-Maximum (s. `feat_1474c` Known Limitations) — beide
  landen weiterhin im selben Feld `lightning_potential_lpi_jkg`. Die neue Region-Tabelle ändert
  daran nichts, weil DE_ALPEN weiterhin ausschließlich von ICON-D2 und EU_REST weiterhin
  ausschließlich von ICON-EU beliefert wird.
- **CIN-Paarung nicht Teil dieser Scheibe** — hängt an #1531 (liefert `cin_ml`), separates
  Ticket.
- **Herkunfts-Anzeige der Stufe im Ortsvergleich nicht Teil dieser Scheibe** — das ist #1680.
- **Keine neue Datenbeschaffung.** Diese Scheibe verwertet ausschließlich bereits produktiv
  befüllte Werte (`lightning_potential_lpi_jkg`) — kein zusätzlicher Abruf, kein
  Kontingent-Verbrauch (#1329).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0048**
  (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`).
- **Rationale:** Diese Scheibe wendet dieselbe Grundsatzentscheidung wie ADR-0048 (Tabelle statt
  fester Zahl bei einer quellenabhängigen numerischen Schwelle) zum zweiten Mal an — erstmals
  für CAPE (#1592), jetzt für LPI (#1679). Es entsteht keine neue Architektur-Entscheidungsfläche:
  das Prinzip „unbekannte Herkunft/Kalibrierung → `None` statt geratener Ersatzwert" und das
  bestehende Gebietsraster aus `thunder_routing` werden unverändert wiederverwendet, nur auf ein
  zweites Signal (LPI statt CAPE) angewendet.

## Changelog

- 2026-08-10: Initial spec created (Issue #1679, LPI-Teil; CIN-Teil ausdrücklich außerhalb des
  Scopes, hängt an #1531).
