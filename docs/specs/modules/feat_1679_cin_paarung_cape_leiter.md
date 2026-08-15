---
entity_id: feat_1679_cin_paarung_cape_leiter
type: feature
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [gewitter, cape, cin, model-registry, thunder-fusion, issue-1679]
---

# CAPE bekommt eine belegte Leiter (1000/2500/4000 J/kg), gepaart mit der Konvektionshemmung CIN (Issue #1679, CIN-Teil)

## Approval

- [ ] Approved

## Purpose

Die Gewitter-Fusion (`thunder_level_from_signals()`) übersetzt CAPE heute binär: erreicht der Wert
die geeichte, modell-/gebietsabhängige Schwelle (`model_registry.cape_threshold_jkg()`, #1592),
liefert CAPE `ThunderLevel.LOW` — sonst `NONE`. Eine Eskalation auf `MED`/`HIGH` ist strukturell
ausgeschlossen (`feat_1474_gewitter_befund_stufen.md` AC-6: „CAPE gedeckelt bei LOW, eskaliert
nie"). Diese Deckelung existiert nur, weil die Gegengröße fehlte: CAPE beschreibt verfügbare
Energie, aber nicht, ob diese Energie überhaupt abgerufen wird — dafür steht die Konvektionshemmung
(CIN, „Cap"). Seit Issue #1531 (heute gemergt, live) steht `cin_ml` als
`dp.convective_inhibition_jkg` zur Verfügung.

Diese Scheibe ersetzt die pauschale LOW-Deckelung durch das bereits PO-finalisierte Zielverfahren
aus `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5 + 3.7 Schritt 2: CAPE bekommt eine
publizierte, dreistufige Leiter (NWS/SPC: schwach < 1000 · mäßig 1000–2500 · stark 2500–4000 ·
extrem > 4000 J/kg), regions-/modellskaliert über die bereits produktive
`model_registry.cape_delta_threshold_jkg()` (kein neuer Kalibrierungslauf). Wie weit diese Leiter
tatsächlich zählt, bestimmt CIN in vier belegten Bändern (Penn State/COMET, SPC:
−25/−50/−100/−200 J/kg) — von „zählt voll" bis „kein Beitrag". Fehlt CIN (strukturell der Fall bei
Météo-France/AROME, Frankreich/Korsika), bleibt die heutige Notbremse „höchstens LOW" als sicherer
Rückfall bestehen — das FR-Gebiet ist damit von dieser Scheibe **verhaltensgleich** betroffen.

Abschnitt 10.2 des Gesamtkonzepts bestätigt ausdrücklich: „Keine offenen Grundsatzfragen mehr. Was
bleibt, ist Arbeit, nicht Entscheidung." Diese Spec formalisiert eine bereits abgeschlossene
Design-Entscheidung, trifft keine neue.

**Bewusst NICHT Teil dieser Scheibe:** die Feineichung der ICON-EU-LPI-Leiter (#1678), das
Einhängen von `sdi_2` (Rang 8, „nach Rang 7"), die Herkunfts-Anzeige der Stufe im Ortsvergleich
(#1680).

## Source

- **File:** `src/app/model_registry.py`, `src/output/metric_format.py`,
  `src/providers/thunder_enrichment.py`
- **Identifier:** `cape_ladder_thresholds_jkg()` (neu, `model_registry.py`, nutzt die bestehenden
  `cape_threshold_jkg()`/`cape_delta_threshold_jkg()`), `thunder_level_from_signals()`
  (Signaturänderung: CAPE-Zweig ersetzt binäre Prüfung durch Leiter+CIN-Dämpfung,
  `metric_format.py`), `_fuse_thunder_levels()`/`_schwellen_fuer_reihe()`/`enrich_thunder()`
  (Erweiterung um CIN-Durchreichung, `thunder_enrichment.py`)

**Schicht:** ausschließlich Python-Core (`src/app/`, `src/output/`, `src/providers/`). Kein Go,
kein Frontend — CAPE ist keine wählbare Metrik (`selectable=False`, #1585), diese Scheibe ändert
nur die interne Fusionslogik, keine Bedienoberfläche.

## Estimated Scope

- **LoC:** ~60-90 Quellcode (neue Leiter-Funktion + CIN-Bänder-Klassifikation in
  `model_registry.py`, CAPE-Zweig-Umbau in `metric_format.py` inkl. „eine Stufe weniger"/„höchstens
  LOW"-Hilfsfunktion über `thunder_ordinal()`, Parametererweiterung in `thunder_enrichment.py`) +
  ~120-160 Tests (überwiegend mechanische Ergänzung eines weiteren keyword-only-Parameters an
  bestehenden Aufrufstellen, s. u.) ≈ **180-250 gesamt** — an der 250-LoC-Workflow-Grenze; beim
  Implementieren tatsächlichen Umfang prüfen, bei Überschreitung
  `workflow.py set-field loc_limit_override 500` mit PO-Freigabe.
- **Files:** 3 geändert (Quellcode), **8 Testdateien** angepasst (0 neu, 0 gelöscht) — Liste unten
  gegen den AKTUELLEN Code verifiziert (`grep -rn "_fuse_thunder_levels(\|thunder_level_from_signals("
  --include="*.py" .`, Stand 2026-08-11, NACH dem LPI-Merge `8cd43763`).
- **Effort:** medium — das Skalierungsmuster (`cape_delta_threshold_jkg`) und das
  keyword-only-ohne-Default-Muster existieren bereits (#1592/#1679-LPI); neu ist ausschließlich die
  Verknüpfungslogik zweier Leitern (CAPE-Leiter × CIN-Band → effektive Stufe), die es in dieser
  Form noch nicht gibt.

### Verifizierte Aufrufstellen (Stand 2026-08-11, ersetzt Vermutungen aus der Analyse-Phase)

| Datei | Reale Aufrufe (kein Docstring/Kommentar) | Nötige Änderung |
|---|---|---|
| `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py` | 4× `_fuse_thunder_levels(data, cape_thr, lpi_thr)` (Zeilen 367f, 415, 449) | viertes Argument (CIN-Info) ergänzen |
| `tests/tdd/test_hail_flag_wmo_signal.py` | 2× `_fuse_thunder_levels(x, None, None)` | viertes Argument `None` ergänzen |
| `tests/tdd/test_hail_no_advice_text_and_thunder_level_guard.py` | 2× `_fuse_thunder_levels(x, None, None)` | viertes Argument `None` ergänzen |
| `tests/tdd/test_lpi_threshold_region_table.py` | 1× Wrapper `_call()` (Zeile 45-48) + 2× Direktaufruf (AC-5-TypeError-Tests, Zeilen 220/242) | Wrapper einmalig ergänzen; die beiden AC-5-Tests bleiben inhaltlich TypeError-Tests für die LPI-Parameter — prüfen, ob sie nach der Erweiterung noch denselben Fehler auslösen oder ob ein eigener AC-5-Test für den neuen CIN-Parameter nötig wird (s. AC-8 unten) |
| `tests/tdd/test_thunder_ladder_shared_across_signals.py` | 4× Direktaufruf `mf.thunder_level_from_signals(...)` (Zeilen 54, 59, 105, 110) | je Aufruf neuen keyword-only Parameter ergänzen |
| `tests/tdd/test_thunder_potential_level_classification.py` | 1× Wrapper `_fusion()` (Zeile 28-43) | Wrapper einmalig ergänzen |
| `tests/tdd/test_cape_not_selectable.py` | 2× Direktaufruf (Zeilen 330, 343) | je Aufruf ergänzen |
| `tests/tdd/test_thunder_level_from_signals_fusion.py` | 1× Wrapper `_fusion()` (Zeile 37-46) | Wrapper einmalig ergänzen |
| `tests/tdd/test_cape_model_threshold.py` | 0 reale Aufrufe (nur Docstring-Erwähnung) | **keine Änderung nötig** |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5 + 3.7 Schritt 1/2 | bindender Rahmen, PO-finalisiert | vollständige Rechenvorschrift (CAPE-Leiter + CIN-Bänder), Abschnitt 10.2 bestätigt „keine offene Entscheidung" |
| `feat_1474_gewitter_befund_stufen.md` AC-6 | **wird durch diese Scheibe fachlich revidiert** | AC-6 lautete „CAPE gedeckelt bei LOW, eskaliert nie" — gilt danach nur noch für CIN in den Bändern „großer Deckel"/„unbekannt"; bei schwacher/moderater Hemmung erreicht CAPE jetzt MED/HIGH. Kein Widerspruch, sondern eine dokumentierte Erweiterung (Gesamtkonzept 3.5: „Die CAPE-Deckelung ist belegt ersetzbar") |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | Vorbild/Referenz, keine neue ADR nötig | dieselbe Grundsatzentscheidung („Tabelle/Skalierung statt einer festen Zahl") zum dritten Mal angewendet — erstmals CAPE-Basisschwelle (#1592), dann LPI (#1679-LPI-Teil), jetzt CAPE-Leiter + CIN (#1679-CIN-Teil) |
| `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` | Vorbild-Spec | `cape_threshold_jkg()`, keyword-only ohne Default |
| `docs/specs/modules/fix_1592_c3_cape_delta_alarme.md` | Infrastruktur, wiederverwendet | `cape_delta_threshold_jkg()`/`CAPE_REFERENZ_NIVEAU_JKG` — ursprünglich für Delta-Alarm-Empfindlichkeit gebaut, hier zweckfremd, aber strukturell identisch für die CAPE-Leiter genutzt |
| `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` | Vorbild/Muster, unverändert | identisches Issue, LPI-Teil bereits live; liefert Format- und Testvorlage |
| `src/app/thunder_scale.py::thunder_ordinal()` | bestehende Infrastruktur, unverändert genutzt | kanonische Ordnung (NONE=0/LOW=1/MED=2/HIGH=3) für „eine Stufe weniger" und „höchstens LOW" |
| Issue #1531 | Blocker, jetzt aufgelöst | liefert `dp.convective_inhibition_jkg` |
| Issue #1678, #1680 | explizit AUSSER Scope | eigene ICON-EU-LPI-Eichung bzw. Herkunfts-Anzeige |

## Implementation Details

### 1. Neue Leiter-Funktion in `model_registry.py` (nutzt bestehende Skalierung)

```python
# CAPE-Leiter (Issue #1679, CIN-Teil). Belegt: NWS/SPC, mehrfach unabhaengig
# publiziert -- "Weak instability: less than 1000 J/kg, Moderate: 1000 to
# 2500, Strong: 2500-4000, Extreme: greater than 4000" (Gesamtkonzept 3.5b).
# Regions-/modellskaliert ueber die BESTEHENDE cape_delta_threshold_jkg()
# (Issue #1592 C3) -- KEIN neuer Kalibrierungslauf: die LOW-Schwelle ist
# unveraendert cape_threshold_jkg(), MED/HIGH sind proportional dazu skaliert
# (identisches Verhaeltnis wie in der publizierten Leiter, verankert an der
# bereits geeichten Modell-/Gebiets-Schwelle statt an einer zweiten,
# unbelegten Zahl).
def cape_ladder_thresholds_jkg(
    model_id: Optional[str], region: Optional[str]
) -> Optional[Tuple[float, float, float]]:
    """(low, med, high)-CAPE-Leiter, region-/modellskaliert. `None`, wenn
    keine Kalibrierung fuer (model_id, region) vorliegt -- identisch zu
    cape_threshold_jkg()."""
    low = cape_threshold_jkg(model_id, region)
    if low is None:
        return None
    med = cape_delta_threshold_jkg(2500.0, model_id, region)
    high = cape_delta_threshold_jkg(4000.0, model_id, region)
    return (low, med, high)
```

### 2. CIN-Bänder-Klassifikation (neu, `model_registry.py` oder `metric_format.py` — Ablageort beim
Implementieren am bestehenden Muster ausrichten, z. B. neben `_thunder_level_from_ladder`)

Vier Bänder nach Gesamtkonzept 3.7 Schritt 2 (Eckpunkte −25/−50/−100/−200 J/kg, Penn State/COMET +
SPC belegt):

| CIN (J/kg) | Wirkung auf die CAPE-Leiter |
|---|---|
| `cin >= -25` (schwacher Deckel) | volle Leiter — Ergebnis unverändert |
| `-50 <= cin < -25` (moderat) | eine Stufe weniger (`thunder_ordinal(ergebnis) - 1`, Boden `NONE`) |
| `-100 <= cin < -50` (großer Deckel) | höchstens `LOW` (`min(ergebnis, LOW)` über `thunder_ordinal`) |
| `cin < -100` (Deckel hält) | `NONE`, unabhängig vom CAPE-Wert |
| `cin is None` (unbekannt) | höchstens `LOW` — identisch zum heutigen Verhalten, sicherer Rückfall |

Ausdrücklich (Gesamtkonzept 3.7, Rasmussen & Blanchard 1998): CIN ist Auslöse-Filter, kein
Schweremaß — sie darf **dämpfen, nie anheben**. Die Implementierung darf deshalb an keiner Stelle
ein Ergebnis über die volle Leiter hinaus anheben, auch nicht bei extrem schwachem CIN.

### 3. `thunder_level_from_signals()` — CAPE-Zweig ersetzt binäre Prüfung

Der heutige Zweig (Zeile ~362-363):

```python
if cape_jkg is not None and cape_threshold_jkg is not None:
    signals.append(ThunderLevel.LOW if cape_jkg >= cape_threshold_jkg else ThunderLevel.NONE)
```

wird ersetzt durch: CAPE gegen die drei Leiter-Schwellen mit `_thunder_level_from_ladder()`
übersetzen (DRY-Pflicht #1481, Funktion bleibt unverändert), dann CIN-Dämpfung anwenden. Neue
keyword-only Parameter OHNE Default (exaktes Muster von `cape_threshold_jkg`/`lpi_low_min` seit
#1592 C1 / #1679-LPI): `cape_med_min`, `cape_high_min`, `cin_jkg` — `cape_threshold_jkg` bleibt als
Name für die LOW-Schwelle bestehen (Bestandsparameter, keine Umbenennung, minimiert Änderungen an
Aufrufstellen, die CIN nicht betrifft).

```python
def thunder_level_from_signals(
    wettercode_level: Optional[ThunderLevel],
    lightning_density: Optional[float],
    cape_jkg: Optional[float],
    lightning_potential_jkg: Optional[float] = None,
    *,
    cape_threshold_jkg: Optional[float],
    cape_med_min: Optional[float],
    cape_high_min: Optional[float],
    cin_jkg: Optional[float],
    lpi_low_min: Optional[float],
    lpi_med_min: Optional[float],
    lpi_high_min: Optional[float],
) -> Optional[ThunderLevel]:
    ...
    if cape_jkg is not None and cape_threshold_jkg is not None:
        if cape_med_min is not None and cape_high_min is not None:
            basis = _thunder_level_from_ladder(
                cape_jkg, cape_threshold_jkg, cape_med_min, cape_high_min,
            )
        else:
            basis = ThunderLevel.LOW if cape_jkg >= cape_threshold_jkg else ThunderLevel.NONE
        signals.append(_gedaempft_durch_cin(basis, cin_jkg))
```

**Wichtig:** `cape_med_min`/`cape_high_min` bleiben (anders als `cape_threshold_jkg`) mit einer
Rückfalloption auf das binäre Bestandsverhalten versehen (`else`-Zweig), falls für eine
Modell-/Gebiets-Kombination `cape_threshold_jkg()` einen Wert liefert, aber
`cape_ladder_thresholds_jkg()` aus irgendeinem Grund nicht — das kann nach aktuellem Code
tatsächlich NIE auseinanderfallen (beide hängen an derselben `CAPE_THRESHOLDS_JKG`-Tabelle), ist
aber ein bewusster Sicherheits-Fallback, kein struktureller Bedarf. **Beim Implementieren prüfen,
ob dieser Fallback tatsächlich nötig ist oder ob beide Parameter ebenso hart (ohne Fallback,
TypeError-Pflicht) wie `cape_threshold_jkg` selbst behandelt werden sollen** — Konsistenz-Präzedenz
(#1592 C1: „kein stiller Rückfall gilt auf der GANZEN Kette") spricht für die harte Variante ohne
`else`-Zweig; das ist hier bewusst als Prüfpunkt markiert, weil beide Varianten AC-kompatibel sind
und die endgültige Wahl beim Implementieren gegen die tatsächliche Aufrufkette (`_schwellen_fuer_reihe`)
zu treffen ist.

`_gedaempft_durch_cin()` (neu, privat, neben `_thunder_level_from_ladder`):

```python
def _gedaempft_durch_cin(basis: ThunderLevel, cin_jkg: Optional[float]) -> ThunderLevel:
    if cin_jkg is None or cin_jkg < -50:
        return min(basis, ThunderLevel.LOW, key=thunder_ordinal) if cin_jkg is None or cin_jkg >= -100 else ThunderLevel.NONE
    if cin_jkg >= -25:
        return basis
    # -50 <= cin_jkg < -25: eine Stufe weniger
    ziel_ordinal = max(thunder_ordinal(basis) - 1, 0)
    return _THUNDER_LEVEL_BY_ORDINAL[ziel_ordinal]
```

(Pseudocode zur Orientierung — beim Implementieren in klare, getrennte `if`-Zweige je Band
auflösen statt der verschachtelten Bedingung oben; Lesbarkeit vor Kompaktheit. Für die
Ordinal→Enum-Rückabbildung existiert noch keine Hilfsfunktion — entweder `_THUNDER_LEVEL_BY_ORDINAL`
als kleines Dict neu anlegen oder `thunder_scale.py` um eine entsprechende Umkehrfunktion
erweitern, je nachdem was beim Implementieren als sauberer bewertet wird.)

### 4. `thunder_enrichment.py` — CIN einmal je Reihe/Datenpunkt durchreichen

`_schwellen_fuer_reihe()` löst zusätzlich die CAPE-Leiter auf (ersetzt `cape_threshold_jkg(...)`
durch `cape_ladder_thresholds_jkg(...)`, liefert ein Tupel statt eines einzelnen Werts):

```python
from app.model_registry import (
    cape_ladder_thresholds_jkg, effective_cape_model_id, lpi_thresholds_jkg,
)
...
region = thunder_region_for(location.latitude, location.longitude)
return (
    cape_ladder_thresholds_jkg(effective_cape_model_id(reihe.meta), region),
    lpi_thresholds_jkg(region),
)
```

`_fuse_thunder_levels()` bekommt CIN **je Datenpunkt** (nicht je Reihe wie CAPE-Schwelle/LPI-Leiter
— CIN ist ein Rohwert an `dp.convective_inhibition_jkg`, keine Konstante über die Reihe):

```python
def _fuse_thunder_levels(
    data: list,
    cape_ladder: Optional[Tuple[float, float, float]],
    lpi_thresholds: Optional[Tuple[float, float, float]],
) -> None:
    cape_low, cape_med, cape_high = cape_ladder or (None, None, None)
    lpi_low, lpi_med, lpi_high = lpi_thresholds or (None, None, None)
    for dp in data:
        fused = thunder_level_from_signals(
            dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
            dp.lightning_potential_lpi_jkg,
            cape_threshold_jkg=cape_low, cape_med_min=cape_med, cape_high_min=cape_high,
            cin_jkg=dp.convective_inhibition_jkg,
            lpi_low_min=lpi_low, lpi_med_min=lpi_med, lpi_high_min=lpi_high,
        )
        if fused is not None:
            dp.thunder_level = fused
```

## Expected Behavior

- **Input:** ein CAPE-Rohwert (`dp.cape_jkg`), ein CIN-Rohwert (`dp.convective_inhibition_jkg`,
  kann `None` sein), plus die über `thunder_region_for()`/`effective_cape_model_id()` aufgelöste
  Modell-/Gebiets-Kombination.
- **Output:** `dp.thunder_level` kann jetzt bei schwacher/moderater Hemmung auf `MED`/`HIGH`
  eskalieren, wo es vorher strukturell bei `LOW` endete. Bei großer/unbekannter Hemmung bleibt das
  Verhalten unverändert zu heute (`LOW` als Obergrenze). Bei sehr großer Hemmung (`< -100`)
  trägt CAPE gar nichts mehr bei.
- **Side effects:** keine neuen Abrufe, kein zusätzliches Kontingent (`cin_ml` wird bereits seit
  #1531 mitgeholt) — reine Umstellung der Fusionslogik.

## Acceptance Criteria

- **AC-1 (Neue Leiter-Funktion — drei Werte, proportional zur bestehenden Kalibrierung):** Given
  `model_registry.cape_ladder_thresholds_jkg(model_id, region)` für eine kalibrierte Kombination
  (z. B. `("icon_d2", "DE_ALPEN")`, `cape_threshold_jkg` liefert dort `300.0`) / When die Funktion
  aufgerufen wird / Then liefert sie `(300.0, 750.0, 1200.0)` — LOW unverändert die bestehende
  Schwelle, MED/HIGH im selben Verhältnis wie die publizierte Leiter (2500/1000 = 2,5×,
  4000/1000 = 4×) auf die kalibrierte Schwelle skaliert.
  - Test: direkter Aufruf gegen mindestens zwei verschiedene Modell-/Gebiets-Kombinationen mit
    bekannter `cape_threshold_jkg()`, Ergebnis gegen die erwartete Skalierung geprüft.
  - Gegenprobe: Würde MED/HIGH mit der UNSKALIERTEN NWS-Leiter (2500/4000 direkt) statt der
    regionsskalierten Version berechnet, läge das Ergebnis für ein Gebiet mit
    `cape_threshold_jkg` ≠ 1000 (z. B. 300 in DE_ALPEN) falsch — der Test muss diese Abweichung
    fangen.

- **AC-2 (unbekannte/fehlende Kombination — kein Signal, kein TypeError):** Given `model_id=None`
  ODER `region=None` ODER eine Kombination ohne Eintrag in `CAPE_THRESHOLDS_JKG` / When
  `cape_ladder_thresholds_jkg()` aufgerufen wird / Then liefert sie `None` — identisch zu
  `cape_threshold_jkg()`.
  - Test: mindestens drei Fälle (fehlendes Modell, fehlende Region, unbekannte Kombination).
  - Gegenprobe: Fiele die Funktion auf einen Default (z. B. die rohe NWS-Leiter 1000/2500/4000)
    zurück, läge ein Ergebnis vor, wo `None` erwartet wird — der Test muss das fangen.

- **AC-3 (schwacher Deckel — CAPE zählt voll, erreicht MED/HIGH):** Given CIN-Werte 0 / −10 / −24,9
  J/kg (alle im Band „schwacher Deckel", `>= -25`) und ein CAPE-Wert, der auf der vollen Leiter
  `MED` erreichen würde / When `thunder_level_from_signals()` mit CAPE-Leiter und diesen
  CIN-Werten aufgerufen wird / Then liefert sie in allen drei Fällen `MED` — unverändert zur
  vollen Leiter, KEINE Dämpfung.
  - Test: drei Aufrufe mit den genannten CIN-Werten, identisches CAPE (im MED-Band), Ergebnis
    jeweils `MED`. Zusätzlich ein Fall mit CAPE im HIGH-Band und CIN=0 → `HIGH`, als Beweis, dass
    die Eskalation über `LOW` hinaus TATSÄCHLICH möglich ist (Kern-Regressionsanker gegen die
    alte AC-6-Deckelung).
  - Gegenprobe: Bliebe die alte Deckelung (`min(..., LOW)`) versehentlich für JEDES CIN-Band aktiv,
    läge das Ergebnis bei `LOW` statt `MED`/`HIGH` — der Test muss das fangen. Das ist der
    wichtigste Test dieser Spec: Er beweist die Kernänderung.

- **AC-4 (moderater Deckel — eine Stufe weniger):** Given CIN-Werte −25 / −40 / −49,9 J/kg (Band
  „moderat") und ein CAPE-Wert, der auf der vollen Leiter `HIGH` erreichen würde / When die Fusion
  läuft / Then liefert sie in allen drei Fällen `MED` (eine Stufe unter `HIGH`). Given zusätzlich
  ein CAPE-Wert im LOW-Band mit CIN=−30 / Then liefert die Fusion `NONE` (eine Stufe unter `LOW`,
  Boden erreicht — keine negative Stufe).
  - Test: vier Aufrufe wie beschrieben, Ergebnisse gegen die erwartete „eine Stufe runter"-Regel
    geprüft, inklusive Bodenfall (`LOW` → `NONE`, nicht `LOW` → `LOW` oder ein Fehler).
  - Gegenprobe: Würde „eine Stufe weniger" fälschlich als „höchstens LOW" (statt relativ zur
    Basisstufe) interpretiert, läge das HIGH-Beispiel bei `LOW` statt `MED` — der Test muss das
    fangen.

- **AC-5 (großer Deckel und unbekanntes CIN — identisch zum heutigen Verhalten, wichtigster
  Regressionstest):** Given CIN-Werte −50 / −75 / −99,9 J/kg (Band „großer Deckel") UND
  zusätzlich `cin_jkg=None` (unbekannt), jeweils mit einem CAPE-Wert, der auf der vollen Leiter
  `HIGH` erreichen würde / When die Fusion läuft / Then liefert sie in ALLEN VIER Fällen `LOW` —
  identisch zum Verhalten vor dieser Änderung (`feat_1474` AC-6, jetzt auf diese beiden Bänder
  eingeschränkt statt generell).
  - Test: vier Aufrufe, alle liefern `LOW`, unabhängig davon wie hoch CAPE über der LOW-Schwelle
    liegt.
  - Gegenprobe: Läge `cin_jkg=None` versehentlich im Band „schwacher Deckel" (z. B. durch ein
    `or 0`-Muster, das `None` als `0` behandelt), würde CAPE bei unbekannter Hemmung plötzlich bis
    `HIGH` eskalieren — genau der Fehler, den die AC-5-Notbremse verhindern soll. Der Test muss
    das fangen.

- **AC-6 (Deckel hält — kein Beitrag):** Given CIN-Werte −100 / −150 / −200 J/kg (Band „Deckel
  hält") mit einem sehr hohen CAPE-Wert (z. B. weit über der HIGH-Schwelle) / When die Fusion
  läuft / Then trägt CAPE `NONE` bei — unabhängig von seiner Höhe.
  - Test: drei Aufrufe mit extremem CAPE und den genannten CIN-Werten, Ergebnis jeweils `NONE`.
  - Gegenprobe: Würde „kein Beitrag" fälschlich als „höchstens LOW" (statt `NONE`) umgesetzt,
    läge das Ergebnis bei `LOW` statt `NONE` — der Test muss das fangen.

- **AC-7 (FR-Gebiet bleibt vom CAPE-Ladder-Umbau verhaltensgleich, weil CIN dort strukturell
  fehlt):** Given ein Datenpunkt im FR-Gebiet (Météo-France/AROME liefert kein `cin_ml`,
  `dp.convective_inhibition_jkg` bleibt strukturell `None`) mit einem CAPE-Wert über der
  FR-Schwelle / When die Fusion über den regulären Produktionspfad (`enrich_thunder()`) läuft /
  Then liefert sie `LOW` — identisch zum Verhalten vor dieser Änderung, weil `cin_jkg=None`
  automatisch ins AC-5-Band fällt.
  - Test: bestehender FR-Regressionstest (Muster aus `test_thunder_enrichment_fuses_level_shared_path.py`)
    läuft nach dieser Änderung unverändert grün.
  - Gegenprobe: Bekäme FR versehentlich einen CIN-Fallback-Wert ungleich `None` (z. B. `0`, was im
    Band „schwacher Deckel" läge), würde CAPE dort plötzlich bis `HIGH` eskalieren — ein Verhalten,
    das nirgends belegt ist (Météo-France liefert dort keine Hemmungsgröße). Der Test muss das
    fangen.

- **AC-8 (TypeError ohne die neuen Parameter — kein stiller Rückfall über die gesamte Kette):**
  Given ein Aufruf von `thunder_level_from_signals()` OHNE `cin_jkg` (keyword-only, ohne Default)
  / When der Aufruf ausgeführt wird / Then bricht er mit `TypeError` — exaktes Muster von
  `cape_threshold_jkg`/`lpi_low_min`. Given zusätzlich ein Aufruf von `_fuse_thunder_levels()` mit
  dem alten (Zwei-Werte-)Signatur-Muster statt der jetzt vierteiligen Cape-Leiter / Then bricht
  auch dieser mit `TypeError`.
  - Test: zwei `pytest.raises(TypeError)`-Blöcke, einer je Funktion. **Muss beim Implementieren
    gegen den finalen `_fuse_thunder_levels()`-Signatur-Entwurf abgeglichen werden** — je nachdem,
    ob `cape_med_min`/`cape_high_min` (Implementation Details Punkt 3) hart oder mit Fallback
    behandelt werden, ändert sich, welcher konkrete Aufruf hier fehlschlägt.
  - Gegenprobe: Bekäme `cin_jkg` einen Default `= None`, würde ein Aufruf ohne CIN-Angabe
    klaglos durchlaufen und automatisch ins „unbekannt"-Band fallen, statt den Aufrufer zu zwingen,
    die Hemmung ausdrücklich zu nennen — der Test muss das fangen.

## Known Limitations

- **CAPE-Leiter-MED/HIGH sind keine eigenständig publizierten Zahlen für jedes Modell**, sondern
  proportional aus der bereits geeichten LOW-Schwelle (#1592, 95. Perzentil der
  Modellklimatologie) abgeleitet. Das überträgt eine Klimatologie-Kalibrierung, die ursprünglich
  nur für die LOW-Schwelle erhoben wurde, auf zwei weitere Punkte derselben Leiter — fachlich
  begründet (gleiche Modellwelt, gleiches Verhältnis wie die publizierte NWS-Leiter), aber keine
  unabhängige Kalibrierung von MED/HIGH selbst.
- **CIN-Bänder sind NICHT regions-/modellabhängig**, anders als die CAPE-Leiter — die publizierten
  Eckpunkte (Penn State/COMET, SPC) sind allgemeine atmosphärenphysikalische Aussagen, keine
  modellspezifische Kalibrierung.
- **CIN als Auslöse-Filter, nicht als Schweremaß** (Rasmussen & Blanchard 1998: CIN sagt Schwere
  nur schwach vorher) — die Implementierung darf CIN deshalb ausschließlich dämpfend einsetzen,
  nie verstärkend.
- **FR/Korsika bleibt strukturell ohne CIN-Signal** — Météo-France/AROME liefert `cin_ml` nicht;
  das Gebiet fällt automatisch und dauerhaft in den „unbekannt"-Fallback (höchstens LOW), bis eine
  neue Quelle das ändert (außerhalb dieser Scheibe, vgl. Gesamtkonzept Abschnitt 3.7 Tabelle
  „CAPE + Hemmung: CAPE ja, Hemmung nein ⇒ bleibt gedeckelt").
- **`cape_med_min`/`cape_high_min`-Fallback-Frage ist beim Implementieren zu entscheiden** (s.
  Implementation Details Punkt 3) — beide Varianten (hart ohne Fallback vs. mit `else`-Zweig)
  erfüllen die ACs dieser Spec unverändert; die Wahl hat aber Auswirkung auf AC-8's exakten
  Fehlerort.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0048**
  (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`).
- **Rationale:** Dritte Anwendung desselben Prinzips (Tabelle/Skalierung statt fester Zahl) —
  erstmals CAPE-Basisschwelle (#1592), dann LPI (#1679-LPI), jetzt CAPE-Leiter + CIN-Dämpfung.
  Keine neue Architektur-Entscheidungsfläche.
- **Revidiert (fachlich, nicht architektonisch) `feat_1474_gewitter_befund_stufen.md` AC-6**: „CAPE
  gedeckelt bei LOW, eskaliert nie" gilt ab dieser Scheibe nur noch für die CIN-Bänder „großer
  Deckel" und „unbekannt" — bei schwacher/moderater Hemmung erreicht CAPE jetzt MED/HIGH. Diese
  Revision ist im Gesamtkonzept (Abschnitt 3.5, PO-finalisiert) bereits dokumentiert und
  entschieden, keine neue Entscheidung dieser Spec.

## Changelog

- 2026-08-11: Initial spec created (Issue #1679, CIN-Teil; LPI-Teil bereits live seit `8cd43763`).
