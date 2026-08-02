"""Eine unbekannte Wettergroesse verschwindet nicht wortlos aus der Ausgabe.

Issue #1466 Arbeitspaket 1 (Dach #1196), Spec:
``docs/specs/modules/fix_1466_kern_suite_gruen.md`` AC-1/AC-2.

Zwei Aufloesungspfade verwerfen heute eine im zentralen Register unbekannte
``metric_id`` kommentarlos (``get_metric(...)`` -> ``except KeyError:
continue``): ``normalize_hourly_metrics()`` (#1406 B -- ausgerechnet die
Lieferung, die Groessen AUS dem Register aufloest) und
``build_trip_corridor_id_map()`` (#1425 S2b).

Das Hausmuster fuer diesen Fall existiert bereits: Verworfenes sammeln und
NACH der Schleife per ``logger.warning`` mit Issue-Bezug melden
(``compare_metric_ids.resolve_enabled_metrics()``, ``official_alerts/dpc.py``).
Festgenagelt wird hier die einzige Eigenschaft, die dem Betrieb hilft: die
verworfene Kennung MUSS im Meldungstext stehen -- ein ``logger.debug("skip")``
erfuellt das nicht.

Test-Politik: Kernschicht, keine Mocks. Aufgerufen wird die echte Funktion
gegen das echte Register; fuer AC-2 wird der Katalog durch eine echte,
wohlgeformte Katalogzeile mit einer nicht existierenden ``metric_id``
ergaenzt (Eingabedaten, kein Verhaltens-Double).
"""
from __future__ import annotations

import logging

import pytest

from app.metric_catalog import get_metric
from output.renderers import compare_metric_catalog
from output.renderers.compare_hourly_metric_ids import normalize_hourly_metrics
from output.renderers.email.html import build_trip_corridor_id_map

# Eine Kennung, die es im zentralen Register nicht gibt und nie geben wird
# (Schreibweise einer alten Frontend-Kopie). Ihre Abwesenheit wird im Test
# selbst nachgewiesen, statt sie zu behaupten.
UNKNOWN_METRIC_ID = "temperatur_gefuehlt_alt"


def _records_naming(caplog, needle: str) -> list[logging.LogRecord]:
    """Alle Protokollzeilen, in deren FERTIGEM Text ``needle`` vorkommt.

    ``getMessage()`` statt ``record.msg``: das Referenzmuster uebergibt die
    verworfene Liste als Argument (``logger.warning("%s ohne ...", dropped)``)
    -- im Rohformat stuende dort nur ``%s``.
    """
    return [r for r in caplog.records if needle in r.getMessage()]


def test_unknown_metric_id_in_register_is_really_unknown():
    """Vorbedingung beider Nachweise: ``UNKNOWN_METRIC_ID`` ist im zentralen
    Register tatsaechlich nicht auffindbar. Ohne diese Gegenprobe koennte ein
    spaeterer Registerzuwachs beide Tests still zu Attrappen machen."""
    with pytest.raises(KeyError):
        get_metric(UNKNOWN_METRIC_ID)


# --- AC-1: normalize_hourly_metrics() ---------------------------------------


def test_normalize_hourly_metrics_names_the_dropped_metric_id_in_the_log(caplog):
    """
    GIVEN eine gespeicherte Stundenauswahl aus zwei aufloesbaren Kennungen und
      einer, die das Register nicht kennt
    WHEN ``normalize_hourly_metrics()`` sie aufloest
    THEN steht die verworfene Kennung WOERTLICH in einer Protokollzeile der
      Stufe WARNING oder hoeher -- und die restliche Auswahl kommt unveraendert
      und in Reihenfolge heraus.
    """
    caplog.set_level(logging.DEBUG)

    resolved = normalize_hourly_metrics(["temp_c", UNKNOWN_METRIC_ID, "wind"])

    assert resolved == ["temperature", "wind"], (
        "Die aufloesbaren Groessen muessen unveraendert und reihenfolge-erhaltend "
        f"durchgehen. Code reference: {resolved}"
    )

    naming = _records_naming(caplog, UNKNOWN_METRIC_ID)
    assert naming, (
        "Die unbekannte Kennung wurde kommentarlos verworfen -- keine einzige "
        "Protokollzeile nennt sie. Beheben nach dem Hausmuster "
        "(compare_metric_ids.resolve_enabled_metrics: sammeln + logger.warning "
        "mit Issue-Bezug NACH der Schleife). Code reference: "
        f"src/output/renderers/compare_hourly_metric_ids.py::normalize_hourly_metrics, "
        f"protokolliert wurde: {[r.getMessage() for r in caplog.records]}"
    )
    assert any(r.levelno >= logging.WARNING for r in naming), (
        "Die Kennung taucht nur unterhalb von WARNING auf -- eine "
        "Debug-Zeile erreicht den Betrieb nicht (Hausmuster ist "
        "logger.warning). Code reference: "
        f"{[(r.levelname, r.getMessage()) for r in naming]}"
    )


def test_normalize_hourly_metrics_stays_quiet_when_everything_resolves(caplog):
    """Gegenprobe zu AC-1: eine vollstaendig aufloesbare Auswahl (historischer
    Kurzschluessel UND Katalog-ID gemischt) darf KEINE Warnung ausloesen.

    Ohne diese Haelfte waere ein "warne immer"-Rueckfall gruen -- und der
    Betrieb bekaeme eine Dauerwarnung, die niemand mehr liest.
    """
    caplog.set_level(logging.DEBUG)

    resolved = normalize_hourly_metrics(["temp_c", "wind", "precipitation"])

    assert resolved == ["temperature", "wind", "precipitation"]
    noisy = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not noisy, (
        "Eine vollstaendig aufloesbare Auswahl hat gewarnt -- die Meldung darf "
        "nur bei tatsaechlichem Verlust kommen. Code reference: "
        f"{[r.getMessage() for r in noisy]}"
    )


# --- AC-2: build_trip_corridor_id_map() -------------------------------------


def _catalog_entry_for(metric_id: str) -> dict:
    """Eine echte Zeile des Compare-Katalogs -- Vorlage fuer die praeparierte."""
    for entry in compare_metric_catalog.COMPARE_METRIC_CATALOG:
        if entry.get("metric_id") == metric_id:
            return dict(entry)
    raise AssertionError(f"Katalogzeile fuer {metric_id!r} nicht gefunden")


def test_build_trip_corridor_id_map_names_the_unresolvable_entry_in_the_log(
    caplog, monkeypatch
):
    """
    GIVEN ein Compare-Katalog aus einer aufloesbaren Zeile und einer zweiten,
      wohlgeformten Zeile, deren ``metric_id`` das Register nicht kennt
    WHEN ``build_trip_corridor_id_map()`` die Korridor-Zuordnung baut
    THEN steht die unaufloesbare Kennung WOERTLICH in einer Protokollzeile der
      Stufe WARNING oder hoeher -- statt wortlos zu verschwinden -- und die
      aufloesbare Zeile steht unveraendert in der Zuordnung.

    Der Katalog wird als ECHTE Eingabedatenzeile ersetzt (Kopie einer
    Bestandszeile mit getauschter ``metric_id``), nicht als Verhaltens-Double:
    Register, Aufloesung und Zuordnungsaufbau laufen unveraendert echt.
    """
    resolvable = _catalog_entry_for("wind")
    broken = dict(resolvable)
    broken["key"] = "kaputte_groesse_max"
    broken["metric_id"] = UNKNOWN_METRIC_ID
    monkeypatch.setattr(
        compare_metric_catalog, "COMPARE_METRIC_CATALOG", [resolvable, broken]
    )
    caplog.set_level(logging.DEBUG)

    id_map = build_trip_corridor_id_map()

    assert id_map.get(resolvable["key"]) == get_metric("wind").col_key, (
        "Die aufloesbare Katalogzeile fehlt in der Korridor-Zuordnung. "
        f"Code reference: {id_map}"
    )
    assert broken["key"] not in id_map, (
        "Die unaufloesbare Zeile darf nicht in der Zuordnung landen -- sie "
        f"soll gemeldet, nicht geraten werden. Code reference: {id_map}"
    )

    naming = _records_naming(caplog, UNKNOWN_METRIC_ID)
    assert naming, (
        "Die unaufloesbare Katalogzeile verschwand wortlos -- keine "
        "Protokollzeile nennt ihre Kennung. Code reference: "
        "src/output/renderers/email/html.py::build_trip_corridor_id_map, "
        f"protokolliert wurde: {[r.getMessage() for r in caplog.records]}"
    )
    assert any(r.levelno >= logging.WARNING for r in naming), (
        "Die Kennung taucht nur unterhalb von WARNING auf -- eine Debug-Zeile "
        "erreicht den Betrieb nicht. Code reference: "
        f"{[(r.levelname, r.getMessage()) for r in naming]}"
    )


def test_build_trip_corridor_id_map_stays_quiet_for_the_real_catalog(caplog):
    """Gegenprobe zu AC-2: mit dem ECHTEN Katalog darf keine Warnung fallen.

    Die Tages-Summen (``aggregation == "sum"``) und die Enum-Zeile
    (``kind == "enum"``) werden bewusst uebersprungen -- das ist eine
    dokumentierte Auswahlregel, kein Aufloesungsverlust. Wer sie mitmeldet,
    erzeugt eine Dauerwarnung ueber korrektes Verhalten; alle uebrigen Zeilen
    des Bestandskatalogs sind aufloesbar (im Test nachgerechnet).
    """
    caplog.set_level(logging.DEBUG)

    id_map = build_trip_corridor_id_map()

    assert id_map, "Korridor-Zuordnung ist leer -- der Nachweis liefe ins Leere."
    noisy = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not noisy, (
        "Der Bestandskatalog hat eine Warnung ausgeloest, obwohl jede nicht "
        "uebersprungene Zeile aufloesbar ist -- vermutlich werden die bewusst "
        "ausgenommenen Summen-/Enum-Zeilen als Verlust gemeldet. Code "
        f"reference: {[r.getMessage() for r in noisy]}"
    )
