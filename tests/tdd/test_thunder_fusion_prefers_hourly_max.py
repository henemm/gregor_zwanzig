"""TDD RED — Issue #1757 (Epic #1419), Variante A mit Messauflage.

SPEC: docs/specs/modules/feat_1757_lpi_max_fusion.md (PO-Freigabe 2026-08-19)

Die Gewitter-Fusion bezieht das Blitzpotenzial heute ausschliesslich aus dem
DWD-MOMENTANWERT ``lightning_potential_lpi_jkg``. Das seit Issue #1531
zusaetzlich abgerufene STUNDENMAXIMUM ``lightning_potential_max_lpi_jkg``
(ICON-D2 / DE_ALPEN) wird nie gelesen. Backtest 2026-08-11: 1 von 18 echten
Gewitterstunden erkannt (Recall 5,6 %) -- der Momentanwert am Stundenrand
verfehlt Gewitter systematisch.

Diese Scheibe stellt die Wertauswahl in ``_fuse_thunder_levels()``
(``src/providers/thunder_enrichment.py``) auf das Stundenmaximum um, mit dem
Momentanwert als Rueckfall, wo kein Stundenmaximum vorliegt.

RED-Ursache (heute): ``_fuse_thunder_levels()`` reicht unveraendert
``dp.lightning_potential_lpi_jkg`` an ``thunder_level_from_signals()``
durch. Ein gesetztes ``lightning_potential_max_lpi_jkg`` bleibt damit
wirkungslos (AC-1, AC-2, AC-5 rot); der Rueckfall und das Nichts-Verhalten
(AC-3, AC-4) sowie die unveraenderte Fusionsgrenze (AC-6) sind
Bestandsverhalten und sichern es gegen Ueber-Erfuellung dieser Scheibe ab.

Testart: Kern-Schicht, deterministisch, KEIN Netz, KEINE Mocks -- echte
``ForecastDataPoint``-Objekte durch den ECHTEN Produktionspfad
``_fuse_thunder_levels()``, exakt wie
``test_thunder_enrichment_fuses_level_shared_path.py`` es bereits tut. Die
Schwellenleiter kommt aus ``app.model_registry.lpi_thresholds_jkg()`` --
AUFGELOEST und bei jedem Aufruf ausdruecklich genannt, kein Default
(PO-Korrektur 2026-08-08, ADR-0025).
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

# Pruefling relativ zur EIGENEN Testdatei aufloesen -- nie ueber einen festen
# Hauptrepo-Pfad, sonst kommt im Worktree falsches Gruen aus fremdem Code.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.model_registry import lpi_thresholds_jkg  # noqa: E402
from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402

_DE_ALPEN = lpi_thresholds_jkg("DE_ALPEN")   # (1.0, 30.0, 50.0)
_EU_REST = lpi_thresholds_jkg("EU_REST")     # (7.14, 23.81, 86.16)


def _punkt(**felder) -> ForecastDataPoint:
    """Datenpunkt, an dem NUR das Blitzpotenzial ein Signal tragen kann:
    Wettercode, Blitzdichte und CAPE sind ``None``, die CAPE-Leiter wird als
    ``None`` hereingereicht. Eine beobachtete Stufe kann damit ausschliesslich
    aus dem Blitzpotenzial stammen."""
    return ForecastDataPoint(
        ts=datetime.now(timezone.utc),
        thunder_level=None,
        lightning_density_per_km2_3h=None,
        cape_jkg=None,
        hail_potential_grau_gsp=None,
        **felder,
    )


# =============================================================================
# AC-1: Stundenmaximum hat Vorrang vor dem Momentanwert
# =============================================================================

def test_ac1_stundenmaximum_schlaegt_momentanwert():
    """AC-1: beide Felder gesetzt (Stundenmaximum 40,0 J/kg, Momentanwert
    12,0 J/kg), DE_ALPEN-Leiter (1/30/50). Die Stufe muss aus 40,0 entstehen
    (MED, weil 30 <= 40 < 50), NICHT aus 12,0 (das ergaebe LOW, weil
    1 <= 12 < 30).

    Die beiden Werte sind bewusst so gewaehlt, dass sie auf VERSCHIEDENEN
    Sprossen derselben Leiter landen -- sonst waere das Ergebnis unabhaengig
    von der Auswahl gleich und der Test bewiese nichts.
    """
    dp = _punkt(
        lightning_potential_max_lpi_jkg=40.0,
        lightning_potential_lpi_jkg=12.0,
    )

    _fuse_thunder_levels([dp], None, _DE_ALPEN)

    assert dp.thunder_level == ThunderLevel.MED, (
        f"Erwartet ThunderLevel.MED (aus dem Stundenmaximum 40,0 J/kg ueber "
        f"die DE_ALPEN-Leiter {_DE_ALPEN}), erhalten {dp.thunder_level!r}. "
        f"{ThunderLevel.LOW!r} bedeutet: die Fusion hat weiterhin den "
        "Momentanwert 12,0 J/kg gelesen und das Stundenmaximum ignoriert."
    )


# =============================================================================
# AC-2: 0,0 ist ein MESSWERT, kein Fehlen (Mutationsprobe gegen `or`)
# =============================================================================

def test_ac2_stundenmaximum_null_komma_null_gilt_und_faellt_nicht_zurueck():
    """AC-2: Stundenmaximum exakt ``0.0`` ("in dieser Stunde kein
    Blitzpotenzial") bei einem Momentanwert von 200,0 J/kg. Es gilt ``0.0``
    -- Stufe NONE ueber die DE_ALPEN-Leiter -- NICHT die Stufe, die 200,0
    ergaebe (HIGH, weil 200 >= 50).

    MUTATIONSPROBE (Spec AC-2, Gegenprobe): Wird die Auswahl als
    ``dp.lightning_potential_max_lpi_jkg or dp.lightning_potential_lpi_jkg``
    geschrieben statt mit einer ausdruecklichen ``is not None``-Pruefung,
    wertet Python die ``0.0`` als unwahr und faellt still auf 200,0 zurueck.
    Dieser Test wird dann rot: er saehe HIGH statt NONE. Genau dafuer ist der
    Momentanwert hier zwei Sprossen ueber dem Stundenmaximum gewaehlt.

    Der Test prueft zusaetzlich, dass die Stufe ``ThunderLevel.NONE`` ist und
    nicht ``None``: ``0.0`` ist "aktiv geprueft, unauffaellig", nicht "keine
    Aussage" (Bestandsunterscheidung aus #1474c/F001).
    """
    dp = _punkt(
        lightning_potential_max_lpi_jkg=0.0,
        lightning_potential_lpi_jkg=200.0,
    )

    _fuse_thunder_levels([dp], None, _DE_ALPEN)

    assert dp.thunder_level == ThunderLevel.NONE, (
        f"Erwartet ThunderLevel.NONE (aus dem Stundenmaximum 0,0 J/kg, das "
        f"jede Sprosse der DE_ALPEN-Leiter {_DE_ALPEN} unterschreitet), "
        f"erhalten {dp.thunder_level!r}. {ThunderLevel.HIGH!r} bedeutet: die "
        "Auswahl hat 0,0 als 'fehlt' gewertet und ist auf den Momentanwert "
        "200,0 J/kg zurueckgefallen -- genau der `or`-Fehler, den AC-2 "
        "ausschliesst. `None` bedeutet: das Stundenmaximum wurde gar nicht "
        "gelesen."
    )
    assert dp.thunder_level_signals == ["blitzpotenzial"], (
        "Ein Stundenmaximum von 0,0 J/kg ist ein geprueftes Signal und muss "
        "als Traeger genannt werden, sobald die Fusion ein Ergebnis liefert: "
        f"erwartet ['blitzpotenzial'], erhalten {dp.thunder_level_signals!r}"
    )


# =============================================================================
# AC-3: Rueckfall auf den Momentanwert, wo kein Stundenmaximum vorliegt
# =============================================================================

def test_ac3_ohne_stundenmaximum_traegt_der_momentanwert_weiter():
    """AC-3: ``lightning_potential_max_lpi_jkg`` ist ``None`` (der Regelfall
    ausserhalb DE_ALPEN -- ICON-EU befuellt dieses Feld nicht), Momentanwert
    8,0 J/kg, EU_REST-Leiter (7,14 / 23,81 / 86,16). Der Momentanwert wird
    verwendet, Stufe LOW -- identisch zum Verhalten VOR dieser Aenderung.

    Der echte Grund fuer die EU_REST-Leiter an dieser Stelle: dort entsteht
    der Rueckfall im Betrieb ueberhaupt erst (``dwd_eu.py:114`` bildet
    ``lpi_con_max`` auf ``lpi`` ab). Ohne diesen Test koennte ein harter
    Wechsel ohne Rueckfall das Blitzpotenzial-Signal ausserhalb der Alpen
    still abschalten.
    """
    dp = _punkt(
        lightning_potential_max_lpi_jkg=None,
        lightning_potential_lpi_jkg=8.0,
    )

    _fuse_thunder_levels([dp], None, _EU_REST)

    assert dp.thunder_level == ThunderLevel.LOW, (
        f"Erwartet ThunderLevel.LOW (Momentanwert 8,0 J/kg ueber der "
        f"EU_REST-Nachweisschwelle {_EU_REST[0]}), erhalten "
        f"{dp.thunder_level!r}. `None` bedeutet: der Rueckfall auf den "
        "Momentanwert fehlt -- das Blitzpotenzial-Signal waere ausserhalb "
        "DE_ALPEN ersatzlos abgeschaltet."
    )
    assert dp.thunder_level_signals == ["blitzpotenzial"], (
        "Der Rueckfall muss dieselbe Herkunft nennen wie zuvor: erwartet "
        f"['blitzpotenzial'], erhalten {dp.thunder_level_signals!r}"
    )


# =============================================================================
# AC-4: beide Felder None -> das Blitzpotenzial traegt nichts bei
# =============================================================================

def test_ac4_beide_felder_none_erzeugen_kein_blitzpotenzial_signal():
    """AC-4: BEIDE Blitzpotenzial-Felder ``None``, alle uebrigen Signale
    ebenfalls ``None``. Die Fusion liefert "keine Aussage" --
    ``dp.thunder_level`` bleibt unangetastet ``None`` und
    ``dp.thunder_level_signals`` enthaelt KEINEN
    ``"blitzpotenzial"``-Eintrag.

    Gegenprobe: wuerde die neue Auswahl bei fehlenden Werten einen
    naheliegenden ``0.0``-Fail-soft-Default einsetzen, entstuende aus "kein
    Signal" ein geprueftes Signal mit Stufe NONE -- dieser Test faengt das.
    """
    dp = _punkt(
        lightning_potential_max_lpi_jkg=None,
        lightning_potential_lpi_jkg=None,
    )

    _fuse_thunder_levels([dp], None, _DE_ALPEN)

    assert dp.thunder_level is None, (
        f"dp.thunder_level ist {dp.thunder_level!r} statt None -- ohne "
        "jeden Blitzpotenzial-Wert darf die Fusion keine Aussage treffen "
        "(kein 0,0-Ersatzwert)"
    )
    assert "blitzpotenzial" not in (dp.thunder_level_signals or []), (
        "dp.thunder_level_signals nennt 'blitzpotenzial' als Traeger, "
        "obwohl beide Quellfelder None sind: "
        f"{dp.thunder_level_signals!r}"
    )


# =============================================================================
# AC-5: Herkunftsname bleibt "blitzpotenzial", auch aus dem Stundenmaximum
# =============================================================================

def test_ac5_herkunft_heisst_weiterhin_blitzpotenzial():
    """AC-5: der Wert stammt ausschliesslich aus dem Stundenmaximum
    (Momentanwert ``None``, Stundenmaximum 40,0 J/kg, DE_ALPEN). Die Herkunft
    heisst weiterhin exakt ``"blitzpotenzial"`` -- es entsteht KEIN neuer
    Signalname (etwa ``"blitzpotenzial_max"``) und keine zweite Beschriftung
    (``app.thunder_scale.THUNDER_SIGNAL_LABEL_DE`` bleibt vierschluessig).

    Die Fusion ist statistik-blind: sie bekommt EINE Zahl und EINE Leiter.
    Welche Statistik die Zahl traegt, entscheidet allein der Aufrufer.
    """
    from app.thunder_scale import THUNDER_SIGNAL_LABEL_DE

    dp = _punkt(
        lightning_potential_max_lpi_jkg=40.0,
        lightning_potential_lpi_jkg=None,
    )

    _fuse_thunder_levels([dp], None, _DE_ALPEN)

    assert dp.thunder_level == ThunderLevel.MED, (
        f"Vorbedingung: 40,0 J/kg aus dem Stundenmaximum muessen ueber die "
        f"DE_ALPEN-Leiter {_DE_ALPEN} MED ergeben, erhalten "
        f"{dp.thunder_level!r} -- das Stundenmaximum wird nicht gelesen"
    )
    assert dp.thunder_level_signals == ["blitzpotenzial"], (
        "Die Herkunft muss unveraendert ['blitzpotenzial'] heissen, auch "
        "wenn der Wert aus dem Stundenmaximum stammt, erhalten "
        f"{dp.thunder_level_signals!r}"
    )
    assert set(THUNDER_SIGNAL_LABEL_DE) == {
        "wettercode", "blitzdichte", "cape", "blitzpotenzial",
    }, (
        "Die Signalmenge ist geschlossen -- diese Scheibe darf keinen "
        f"neuen Signalnamen einfuehren: {sorted(THUNDER_SIGNAL_LABEL_DE)}"
    )


# =============================================================================
# AC-6: die oeffentliche Fusionsgrenze bleibt unveraendert
# =============================================================================

_ERWARTETE_POSITIONSPARAMETER = [
    "wettercode_level",
    "lightning_density",
    "cape_jkg",
    "lightning_potential_jkg",
]

_ERWARTETE_KEYWORD_PARAMETER = [
    "cape_threshold_jkg",
    "cape_med_min",
    "cape_high_min",
    "cin_jkg",
    "lpi_low_min",
    "lpi_med_min",
    "lpi_high_min",
]


def _positions_und_keyword_parameter(func):
    sig = inspect.signature(func)
    positional = [
        name for name, p in sig.parameters.items()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    keyword_only = [
        name for name, p in sig.parameters.items() if p.kind is p.KEYWORD_ONLY
    ]
    return positional, keyword_only


def test_ac6_fusionsgrenze_nimmt_weiterhin_genau_einen_blitzpotenzial_wert():
    """AC-6: ``thunder_level_from_signals()`` und ``thunder_signal_carriers()``
    nehmen weiterhin GENAU EINEN Blitzpotenzial-Wert an DERSELBEN
    Positionsstelle (viertes Positionsargument ``lightning_potential_jkg``)
    entgegen -- kein zweiter LPI-Parameter, keine Signaturaenderung.

    Warum das eine eigene Zusicherung braucht: der naheliegende, falsche Weg
    waere, beide Zahlen an die Fusion zu reichen und dort auszuwaehlen. Dann
    saesse die Statistik-Entscheidung in ``metric_format.py`` statt beim
    Aufrufer, und die Fusion waere nicht mehr statistik-blind
    (Kontext-Dokument, Existing Patterns; ADR-0025).
    """
    from output.metric_format import (
        thunder_level_from_signals, thunder_signal_carriers,
    )

    for func in (thunder_level_from_signals, thunder_signal_carriers):
        positional, keyword_only = _positions_und_keyword_parameter(func)
        assert positional == _ERWARTETE_POSITIONSPARAMETER, (
            f"{func.__name__}: Positionsparameter geaendert. Erwartet "
            f"{_ERWARTETE_POSITIONSPARAMETER}, erhalten {positional}"
        )
        assert keyword_only == _ERWARTETE_KEYWORD_PARAMETER, (
            f"{func.__name__}: Keyword-Parameter geaendert. Erwartet "
            f"{_ERWARTETE_KEYWORD_PARAMETER}, erhalten {keyword_only}"
        )
        lpi_parameter = [
            n for n in positional + keyword_only
            if "lpi" in n.lower() or "lightning_potential" in n.lower()
        ]
        assert lpi_parameter == [
            "lightning_potential_jkg", "lpi_low_min", "lpi_med_min",
            "lpi_high_min",
        ], (
            f"{func.__name__}: es darf GENAU EINEN Blitzpotenzial-WERT geben "
            f"(neben den drei Leitersprossen), erhalten {lpi_parameter}"
        )


def test_ac6_alter_aufruf_mit_dem_bestehenden_argumentmuster_laeuft_weiter():
    """AC-6, zweiter Teil: ein bestehender Aufruf mit dem alten
    Argumentmuster (vier Positionsargumente + die keyword-only Leitern) laeuft
    unveraendert durch und liefert dasselbe Ergebnis wie zuvor -- die
    Umstellung passiert im AUFRUFER, nicht an der Grenze.
    """
    from output.metric_format import (
        thunder_level_from_signals, thunder_signal_carriers,
    )

    leitern = dict(
        cape_threshold_jkg=None, cape_med_min=None, cape_high_min=None,
        cin_jkg=None,
        lpi_low_min=_EU_REST[0], lpi_med_min=_EU_REST[1],
        lpi_high_min=_EU_REST[2],
    )

    stufe = thunder_level_from_signals(None, None, None, 8.0, **leitern)
    traeger = thunder_signal_carriers(None, None, None, 8.0, **leitern)

    assert stufe == ThunderLevel.LOW, (
        f"Der bestehende Aufruf mit 8,0 J/kg an vierter Position muss ueber "
        f"die EU_REST-Leiter {_EU_REST} unveraendert LOW liefern, erhalten "
        f"{stufe!r}"
    )
    assert traeger == ["blitzpotenzial"], (
        f"Erwartet ['blitzpotenzial'] als Traeger, erhalten {traeger!r}"
    )
