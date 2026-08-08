"""TDD RED — Issue #1592 Scheibe C2.

SPEC: docs/specs/modules/fix_1592_c2_cape_riskengine.md AC-1 .. AC-7 (AC-6 ohne
neuen Test, s. Spec).

`RiskEngine` zaehlt CAPE heute ZWEIMAL: einmal ueber die Fusion
(`thunder_level_max`, bereits in Scheibe 1 auf `ThunderLevel.LOW` gedeckelt)
und einmal ueber eine eigene, unbelegte Katalogleiter (1000/2000 J/kg) in
`_check_catalog_metric(agg, "cape", ...)`. `_deduplicate()` behaelt je
`RiskType` die hoechste Stufe -- die ungedeckelte zweite Zaehlung gewinnt
gegen die gedeckelte erste und unterlaeuft damit ADR-0048.

Diese Datei deckt:
- AC-1: Eichluecke `("icon_d2", "FR")` in `CAPE_THRESHOLDS_JKG` geschlossen.
- AC-2: Regressionsschutz -- bestehende Eichwerte bleiben byte-identisch
  (dieser Test ist JETZT SCHON gruen und MUSS es in Phase GREEN bleiben).
- AC-3: Kernfall -- genau EIN THUNDERSTORM-Risiko statt zwei.
- AC-4: Gegenprobe -- Deckelung wirkt unabhaengig vom CAPE-Zahlenwert.
- AC-5: Abstain -- fehlende Fusions-Aussage erzeugt kein Alarm-Risiko.
- AC-7: tote `risk_thresholds`-Konfiguration bei "cape" entfernt.

AC-6 braucht keinen neuen Test (Spec: Nachweis ueber den unveraenderten
Bestand in `test_risk_engine.py`).

Keine Mocks, kein `patch()`, kein `MagicMock`: echte DTOs, echte
`RiskEngine().assess_segment()`, echter `MetricCatalog`.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.model_registry import CAPE_THRESHOLDS_JKG
from app.metric_catalog import get_metric
from app.models import (
    GPXPoint,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.risk_engine import RiskEngine


# --- Helper: Eichskript relativ zur Testdatei laden (niemals fest
# verdrahteter Hauptrepo-Pfad, s. Gate `test_repo_path_hardcoding_ratchet.py`
# / #1409) ---

def _load_region_reference_points() -> dict:
    """Liest `_REGION_REFERENCE_POINTS` per AST direkt aus dem Quelltext von
    `scripts/eichung_cape_schwelle.py` -- KEIN `import`/`exec_module`.

    Grund (gemessen, s. Issue #1592 Nachtrag): Pythons Bytecode-Cache
    invalidiert `scripts/__pycache__/*.pyc` nur auf Sekunden-Genauigkeit ueber
    die mtime. Schreibt eine Mutations-Gegenprobe die Quelle und die `.pyc`
    in derselben Sekunde, haelt Python die vorhandene `.pyc` fuer aktuell und
    ein `import`/`exec_module` laedt die VERALTETE Fassung -- der Test saehe
    dann eine Verfaelschung nicht (falsches Gruen bei der Gegenprobe) bzw.
    ein falsches Rot bei unveraendertem Quelltext. `ast.parse()` +
    `ast.literal_eval()` fuehrt den Modulrumpf gar nicht erst aus und
    beruehrt damit keinen Bytecode-Cache."""
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "eichung_cape_schwelle.py"
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))

    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
            node.targets[0], ast.Name
        ):
            target = node.targets[0]
        if target is not None and target.id == "_REGION_REFERENCE_POINTS" and node.value is not None:
            return ast.literal_eval(node.value)

    raise AssertionError(
        f"_REGION_REFERENCE_POINTS nicht in {script_path} gefunden -- "
        "Konstante umbenannt, geloescht oder Datei verschoben? Dieser Test "
        "kann ohne sie nichts pruefen und darf deshalb nicht still gruen "
        "werden."
    )


# --- Helper (gleichwertig zu tests/integration/test_risk_engine.py) ---

def _make_segment_weather(
    thunder_level_max: ThunderLevel | None = None,
    cape_max_jkg: float | None = None,
) -> SegmentWeatherData:
    """Erzeugt ein minimales SegmentWeatherData fuer Risk-Tests.

    Beide Felder (`thunder_level_max`, `cape_max_jkg`) werden direkt auf dem
    Summary-Fixture gesetzt -- keine Fusion noetig, die ist bereits durch die
    C1-Testfamilie (`test_thunder_level_from_signals_fusion.py`) gedeckt.
    """
    point = GPXPoint(lat=47.0, lon=13.0, elevation_m=1500, distance_from_start_km=0.0)
    segment = TripSegment(
        segment_id=1,
        start_point=point,
        end_point=point,
        start_time=datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=6.0,
        ascent_m=400,
        descent_m=200,
    )
    summary = SegmentWeatherSummary(
        thunder_level_max=thunder_level_max,
        cape_max_jkg=cape_max_jkg,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# ─────────────────────── AC-1 — Eichluecke geschlossen ───────────────────

def test_icon_d2_fr_eichluecke_geschlossen():
    """AC-1: Given die FR-Punktliste enthaelt jetzt zwei Referenzpunkte
    (Korsika zuerst, dann franz. Alpen 45.00/6.50) / When das Eichskript fuer
    icon_d2 x FR laeuft und am ersten Punkt (Korsika) keine ICON-D2-Werte
    findet / Then versucht es den zweiten Punkt, findet dort Werte, und die
    committete Eichtabelle traegt ("icon_d2", "FR") == 300.0.

    RED-Ursache (heute): `_REGION_REFERENCE_POINTS["FR"]` ist ein einzelner
    Punkt (Korsika), der ausserhalb des ICON-D2-Gitters liegt -- das Skript
    kann fuer diese Kombination nie einen Wert erheben, der Schluessel fehlt
    in CAPE_THRESHOLDS_JKG, direkter Zugriff wirft KeyError.
    """
    key = ("icon_d2", "FR")
    assert key in CAPE_THRESHOLDS_JKG, (
        f"CAPE_THRESHOLDS_JKG hat keinen Eintrag fuer {key} -- der Schluessel "
        "entsteht nur, wenn die FR-Punktliste einen zweiten Referenzpunkt "
        "(franzoesische Alpen, 45.00/6.50) enthaelt UND das Eichskript ihn "
        "tatsaechlich befragt hat, nachdem der erste Punkt (Korsika) keine "
        "ICON-D2-Werte liefert. Vorhandene Schluessel: "
        f"{sorted(CAPE_THRESHOLDS_JKG.keys())}"
    )
    value = CAPE_THRESHOLDS_JKG[key]
    assert value == 300.0, (
        f"CAPE_THRESHOLDS_JKG[{key}] == {value!r}, erwartet 300.0 "
        "(max(P95=230, 300) am zweiten FR-Punkt, franzoesische Alpen). "
        "Ein Wert von 390.0 waere der verworfene Rhone-Tal-Kandidat -- "
        "falscher Punkt gewaehlt."
    )


# ──────────────── AC-2 — Regressionsschutz (JETZT SCHON GRUEN) ───────────

def test_bestehende_cape_schwellen_unveraendert():
    """AC-2 (Regressionsschutz, tragend): Given die Umstellung von
    `_REGION_REFERENCE_POINTS` von Einzelpunkt auf geordnete Liste je Gebiet
    / When alle bereits belegten (Modell, Gebiet)-Kombinationen erneut
    nachgeschlagen werden / Then liefern sie ausnahmslos denselben Zahlenwert
    wie vor der Umstellung.

    Dieser Test ist JETZT SCHON GRUEN (Regressionsschutz, kein RED-Nachweis)
    und MUSS es in Phase GREEN bleiben -- er bewacht, dass die COMMITTETE
    TABELLE `CAPE_THRESHOLDS_JKG` unveraendert bleibt.

    ACHTUNG (Mutations-Gegenprobe, gemessen): dieser Test liest nur die
    bereits committete Tabelle, NICHT die Punktliste im Eichskript. Eine
    vertauschte Reihenfolge in `_REGION_REFERENCE_POINTS["FR"]` wirkt sich
    erst beim naechsten Skriptlauf auf die Tabelle aus -- dieser Test bleibt
    dabei gruen und faengt die Vertauschung NICHT. Die Reihenfolge selbst
    bewacht `test_fr_referenzpunkte_reihenfolge_korsika_zuerst` unten, direkt
    an der Datenstruktur, in der sie wirkt.
    """
    arome_fr = CAPE_THRESHOLDS_JKG[("meteofrance_arome", "FR")]
    assert arome_fr == 300.0, (
        f'CAPE_THRESHOLDS_JKG[("meteofrance_arome", "FR")] == {arome_fr!r}, '
        "erwartet 300.0 -- dieser Wert diente in Scheibe 1 selbst als "
        "Kernfall und darf durch die Punktlisten-Umstellung nicht verschoben "
        "werden."
    )

    icon_eu_fr = CAPE_THRESHOLDS_JKG[("icon_eu", "FR")]
    assert icon_eu_fr == 850.0, (
        f'CAPE_THRESHOLDS_JKG[("icon_eu", "FR")] == {icon_eu_fr!r}, erwartet '
        "850.0 -- ein zweiter Bestandswert mit anderem Zahlenwert als "
        "meteofrance_arome/FR, damit ein Test, der beide gegenprueft, nicht "
        "zufaellig durch einen einzigen falschen Konstantwert bestehen kann."
    )


def test_fr_referenzpunkte_reihenfolge_korsika_zuerst():
    """AC-2 (Regressionsschutz, Reihenfolge): Given
    `_REGION_REFERENCE_POINTS["FR"]` im Eichskript / Then steht Korsika
    (42.22, 9.07) an Position 0 und die franzoesischen Alpen (45.00, 6.50)
    an Position 1.

    Diese Reihenfolge traegt inhaltlich: `calibrate()` fragt die Punkte
    eines Gebiets der Reihe nach ab und uebernimmt den ERSTEN Punkt, der
    Werte liefert, als Eichgrundlage (s. `eichung_cape_schwelle.py`,
    `calibrate()`). Korsika liefert fuer alle bereits belegten FR-Modelle
    (u. a. `meteofrance_arome`) Werte -- steht es an Position 0, bleiben die
    zehn bestehenden Eichwerte unveraendert. Eine Vertauschung wuerde beim
    naechsten Eichlauf still einen anderen Referenzpunkt (die Alpen) fuer
    diese Modelle heranziehen und deren Schwellen verschieben, OHNE dass
    `CAPE_THRESHOLDS_JKG` sich sofort aendert -- die committete Tabelle ist
    ja nur ein eingefrorener Snapshot des letzten Laufs.

    Ergaenzt `test_bestehende_cape_schwellen_unveraendert`: jener Test
    bewacht die committete Tabelle (den Snapshot), dieser Test bewacht die
    Datenstruktur, aus der ein KUENFTIGER Snapshot entsteht.
    """
    region_points = _load_region_reference_points()
    fr_points = region_points["FR"]

    assert fr_points[0] == (42.22, 9.07), (
        f'_REGION_REFERENCE_POINTS["FR"][0] == {fr_points[0]!r}, erwartet '
        "(42.22, 9.07) (Korsika). Korsika muss an Position 0 stehen, weil "
        "calibrate() den ERSTEN Punkt mit Werten als Eichgrundlage "
        "uebernimmt -- alle zehn bereits committeten FR-Eichwerte wurden "
        "gegen Korsika erhoben. Stuende ein anderer Punkt zuerst, wuerde "
        "der naechste Eichlauf diese Werte still verschieben, ohne dass "
        "ein Test es meldet, solange nur die committete Tabelle geprueft "
        "wird."
    )
    assert fr_points[1] == (45.00, 6.50), (
        f'_REGION_REFERENCE_POINTS["FR"][1] == {fr_points[1]!r}, erwartet '
        "(45.00, 6.50) (franzoesische Alpen). Dieser zweite Punkt ist die "
        "Quelle fuer (\"icon_d2\", \"FR\") == 300.0 (AC-1) -- ICON-D2 deckt "
        "Korsika nicht ab, calibrate() faellt deshalb auf ihn zurueck. "
        "Faellt er weg oder rueckt er auf Position 0, verliert die Tabelle "
        "diesen Eintrag oder erhebt ihn gegen den falschen Punkt."
    )


# ─────────────────── AC-3 — Kernfall: genau eine Zaehlung ────────────────

def test_cape_hoch_mit_leichter_fusion_erzeugt_genau_ein_low_risiko():
    """AC-3 (Kernfall): Given ein Segment mit hohem CAPE (2500 J/kg), dessen
    Fusions-Ergebnis "leicht" ist (thunder_level_max == ThunderLevel.LOW) /
    When RiskEngine.assess_segment() aufgerufen wird / Then enthaelt das
    Ergebnis GENAU EIN Risk(THUNDERSTORM, ...) der Stufe LOW.

    RED-Ursache (heute, gemessen): Regel 1 (`_check_thunder`) haengt
    Risk(THUNDERSTORM, LOW) ein, Regel 2 (`_check_catalog_metric(agg,
    "cape", ...)`) zaehlt CAPE=2500 zusaetzlich gegen die ungedeckelte Leiter
    1000/2000 und haengt Risk(THUNDERSTORM, HIGH) ein.
    `_deduplicate()` behaelt je RiskType die hoechste Stufe -> heraus kommen
    ZWEI Eintraege vor der Deduplizierung, und nach der Deduplizierung
    gewinnt HIGH gegen den gedeckelten LOW-Befund -- die Deckelung aus
    ADR-0048 wird unterlaufen.

    Nutzt die echte Einstiegsfunktion assess_segment(), nicht
    _check_thunder()/_check_catalog_metric() direkt.
    """
    seg = _make_segment_weather(
        thunder_level_max=ThunderLevel.LOW, cape_max_jkg=2500.0
    )

    assessment = RiskEngine().assess_segment(seg)

    thunder_risks = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
    assert len(thunder_risks) == 1, (
        f"assess_segment() lieferte {len(thunder_risks)} THUNDERSTORM-Risiken "
        f"({[r.level for r in thunder_risks]!r}), erwartet genau 1. Die "
        "Katalog-Regel fuer CAPE zaehlt offenbar zusaetzlich zur Fusion -- "
        "genau die doppelte Zaehlung, die diese Scheibe streicht."
    )
    assert thunder_risks[0].level == RiskLevel.LOW, (
        f"Die verbleibende THUNDERSTORM-Stufe ist {thunder_risks[0].level!r}, "
        "erwartet RiskLevel.LOW -- die ungedeckelte zweite CAPE-Zaehlung "
        "(Leiter 1000/2000 J/kg) darf die gedeckelte Fusions-Aussage nicht "
        "mehr ueberschreiben."
    )


# ────────────── AC-4 — Gegenprobe: Deckelung fuer JEDEN CAPE-Wert ────────

def test_extrem_hohes_cape_eskaliert_nicht_ueber_die_fusion_hinaus():
    """AC-4 (Gegenprobe zur Deckelung): Given ein Segment mit einem extrem
    hohen CAPE-Wert (50000 J/kg) und thunder_level_max == ThunderLevel.LOW /
    When assess_segment() aufgerufen wird / Then erzeugt die RiskEngine kein
    Risk(THUNDERSTORM, ...) ueber der Stufe, die thunder_level_max vorgibt --
    UNABHAENGIG davon, wie hoch CAPE numerisch ist.

    RED-Ursache (heute): 50000 J/kg liegt weit ueber der Katalogleiter-
    Schwelle "high" (2000 J/kg) -> Regel 2 erzeugt Risk(THUNDERSTORM, HIGH),
    das nach _deduplicate() den gedeckelten LOW-Befund verdraengt.
    """
    seg = _make_segment_weather(
        thunder_level_max=ThunderLevel.LOW, cape_max_jkg=50000.0
    )

    assessment = RiskEngine().assess_segment(seg)

    thunder_risks = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
    levels_over_low = [
        r.level for r in thunder_risks if r.level != RiskLevel.LOW
    ]
    assert not levels_over_low, (
        f"assess_segment() lieferte THUNDERSTORM-Risiken oberhalb LOW: "
        f"{levels_over_low!r} (alle THUNDERSTORM-Stufen: "
        f"{[r.level for r in thunder_risks]!r}), obwohl thunder_level_max == "
        "LOW gesetzt war. CAPE=50000 J/kg darf die Deckelung NIEMALS "
        "durchbrechen, unabhaengig vom numerischen CAPE-Wert."
    )
    assert len(thunder_risks) == 1 and thunder_risks[0].level == RiskLevel.LOW, (
        f"Erwartet genau ein Risk(THUNDERSTORM, LOW), gefunden: "
        f"{[(r.type, r.level) for r in thunder_risks]!r}."
    )


# ───────────────── AC-5 — Abstain: keine Fusions-Aussage ─────────────────

@pytest.mark.parametrize(
    "cape_max_jkg",
    [2500.0, 1500.0],
    ids=["cape-2500-vormals-high", "cape-1500-vormals-moderate"],
)
def test_cape_ohne_fusions_aussage_erzeugt_kein_alarm_risiko(cape_max_jkg):
    """AC-5 (Abstain): Given ein Segment mit vorhandenem CAPE-Wert (2500 oder
    1500 J/kg), aber thunder_level_max is None ("keine Aussage") / When
    assess_segment() aufgerufen wird / Then enthaelt das Ergebnis KEIN
    Risk(THUNDERSTORM, ...).

    RED-Ursache (heute, gemessen): CAPE=2500 mit thunder_level_max=None
    liefert Risk(THUNDERSTORM, HIGH); CAPE=1500 liefert
    Risk(THUNDERSTORM, MODERATE) -- die Katalog-Regel macht aus "keine
    Fusions-Aussage" faelschlich einen Alarm, obwohl kein einziges
    Gewittersignal (Wettercode, Blitzdichte, Blitzpotenzial) vorlag.
    """
    seg = _make_segment_weather(
        thunder_level_max=None, cape_max_jkg=cape_max_jkg
    )

    assessment = RiskEngine().assess_segment(seg)

    thunder_risks = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
    assert thunder_risks == [], (
        f"assess_segment() lieferte bei cape_max_jkg={cape_max_jkg!r} und "
        f"thunder_level_max=None dennoch THUNDERSTORM-Risiken: "
        f"{[(r.type, r.level) for r in thunder_risks]!r}, erwartet keines. "
        '"Keine Aussage" (thunder_level_max is None) darf kein Alarm-Risiko '
        "erzeugen -- CAPE allein, ohne Fusions-Ergebnis, ist kein Ereignis."
    )


# ───────────────────── AC-7 — tote Konfiguration entfernt ────────────────

def test_cape_metric_hat_keine_risk_thresholds_mehr():
    """AC-7: Given MetricDefinition fuer "cape" trug bisher
    risk_thresholds={"medium": 1000.0, "high": 2000.0} / When die CAPE-Regel
    aus der RiskEngine gestrichen ist / Then ist get_metric("cape").
    risk_thresholds entfernt oder leer.

    RED-Ursache (heute): das Feld traegt noch die alte Katalogleiter.
    """
    risk_thresholds = get_metric("cape").risk_thresholds
    assert not risk_thresholds, (
        f'get_metric("cape").risk_thresholds == {risk_thresholds!r}, '
        "erwartet leer/None -- nach dem Streichen von Regel 2 in "
        "assess_segment() gibt es im gesamten Produktivcode keinen Leser "
        "mehr fuer diesen Wert, die tote Konfiguration muss entfernt sein."
    )
