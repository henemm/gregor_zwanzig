"""TDD RED -- Issue #1648: Radar-DPC (Protezione Civile) ist als NowCast-Quelle
ersatzlos entfernt; der Italien-Zweig laeuft direkt auf ARPAE ICON-2I.

SPEC: docs/specs/modules/fix_1648_radar_dpc_entfernen.md (AC-5, AC-6 + die in
den Implementation Details festgelegte Bbox-Umbenennung).

Kern-Schicht: deterministisch, netzfrei, KEIN `live`-Marker. Kein Mock-Theater
(CLAUDE.md) und -- wichtig -- KEIN Dateiinhalt-Check: die Abwesenheit wird
ueber das VERHALTEN des Importsystems und der Provider-Registry belegt, nicht
ueber `assert "..." not in file.read_text()`.

Pfadregel (#1409): dieser Test importiert den Prueflings ueber den normalen
`src`-Importpfad, den `tests/conftest.py` relativ zum Repo-Wurzelverzeichnis
DIESER Datei aufsetzt -- kein fester Hauptrepo-Pfad.

RED-Erwartung vor der Implementierung:
- `providers.radar_dpc` existiert noch -> kein `ModuleNotFoundError`,
- `available_providers()` enthaelt noch `"radar_dpc"`,
- `RadarNowcastService._fetch_radar_dpc` existiert noch,
- `_SOURCE_LABELS` traegt noch den Radar-Quellen-Eintrag `"DPC"`,
- `services.radar_service._within_italy_radar` existiert noch nicht (heisst
  noch `_within_dpc`),
- `radar-api.protezionecivile.it` steht noch im Egress-INVENTORY.
"""
from __future__ import annotations

import importlib
import sys

import pytest

# Reale Koordinaten (Werte identisch zu den Bestandstests, damit die
# Wahrheitswerte vor/nach der Umbenennung direkt vergleichbar bleiben).
_VIZZAVONA_LAT, _VIZZAVONA_LON = 42.1244, 9.1339   # GR20, Korsika -> in der IT-Radar-Box
_KHW_LAT, _KHW_LON = 46.20, 12.85                  # Karnischer Hoehenweg -> in der IT-Radar-Box
_MARSEILLE_LAT, _MARSEILLE_LON = 43.2965, 5.3698   # lon 5.37 < 6.5 -> ausserhalb
_ROME_LAT, _ROME_LON = 41.90, 12.50                # Mittelitalien -> in der IT-Radar-Box


# ===========================================================================
# AC-5: Der Provider ist weg -- belegt am Verhalten, nicht am Dateiinhalt
# ===========================================================================

def test_ac5_radar_dpc_module_is_gone():
    """AC-5: `import providers.radar_dpc` wirft `ModuleNotFoundError`.

    `sys.modules` wird vorher geleert, damit ein frueher in derselben
    pytest-Session erfolgter Import das Ergebnis nicht faelschlich gruen
    faerbt (Import-Cache statt Dateisystem-Wahrheit).
    """
    sys.modules.pop("providers.radar_dpc", None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("providers.radar_dpc")


def test_ac5_radar_dpc_not_in_provider_registry():
    """AC-5: die Provider-Registry kennt `radar_dpc` nicht mehr -- weder als
    Name in `available_providers()` noch als aufloesbare Factory."""
    from providers.base import ProviderNotFoundError, available_providers, get_provider

    assert "radar_dpc" not in available_providers(), (
        "AC-5: `radar_dpc` darf nicht mehr in der Provider-Registry stehen, "
        f"tatsaechlich: {sorted(available_providers())}"
    )

    with pytest.raises(ProviderNotFoundError):
        get_provider("radar_dpc")


def test_ac5_radar_service_has_no_dpc_fetch_method():
    """AC-5: die DPC-Abrufmethode der NowCast-Kette existiert nicht mehr."""
    from services.radar_service import RadarNowcastService

    assert not hasattr(RadarNowcastService, "_fetch_radar_dpc"), (
        "AC-5: `RadarNowcastService._fetch_radar_dpc` muss ersatzlos entfallen"
    )


def test_ac5_dpc_is_no_longer_an_offered_radar_source_label():
    """AC-5: `"DPC"` ist keine Radar-Quelle mehr -- der Label-Katalog
    (`_SOURCE_LABELS`, Single Source of Truth fuer `format_now_text` UND den
    Body-Builder in `trip_alert.check_radar_alerts`) darf den Schluessel nicht
    mehr fuehren. Geprueft wird die nutzersichtbare Wirkung: `source_label()`
    liefert fuer `"DPC"` keinen ausformulierten Radar-Quellentext mehr,
    sondern faellt auf den Rohschluessel zurueck.

    Nicht betroffen: die amtliche Warnquelle `DpcSource` mit ihrem internen
    `source="dpc"` (AC-3) -- anderer Katalog, andere Datenquelle.
    """
    from services.radar_service import RadarNowcastService

    label = RadarNowcastService().source_label("DPC")

    assert label == "DPC", (
        "AC-5: fuer den entfernten Radar-Schluessel darf es keinen "
        f"ausformulierten Quellen-Text mehr geben (war: {label!r})"
    )
    assert "Protezione" not in label, (
        f"AC-5: kein Text darf 'DPC' noch als Radarquelle benennen (war: {label!r})"
    )


# ===========================================================================
# Bbox-Umbenennung (_within_dpc -> _within_italy_radar), Pure Function
# Muster: test_ac2_within_arome_france_bbox aus test_feature_734_...
# ===========================================================================

def test_within_italy_radar_bbox_keeps_previous_truth_values():
    """Die Italien-Radar-Box heisst nach der Umbenennung
    `_within_italy_radar` und liefert fuer dieselben Koordinaten exakt
    dieselben Wahrheitswerte wie vorher `_within_dpc` (Werte 36.0-47.5 /
    6.5-19.0 unveraendert)."""
    import services.radar_service as rs

    within = getattr(rs, "_within_italy_radar", None)
    assert callable(within), (
        "`_within_italy_radar` muss existieren (Umbenennung von `_within_dpc` "
        "-- die Box beschreibt ein Gebiet, keinen Anbieter)"
    )

    assert within(_VIZZAVONA_LAT, _VIZZAVONA_LON) is True
    assert within(_KHW_LAT, _KHW_LON) is True
    assert within(_ROME_LAT, _ROME_LON) is True
    assert within(_MARSEILLE_LAT, _MARSEILLE_LON) is False

    # Grenzwerte inklusiv -- unveraendert gegenueber der Vorher-Implementierung.
    assert within(36.0, 6.5) is True
    assert within(47.5, 19.0) is True
    assert within(35.999, 12.0) is False
    assert within(47.501, 12.0) is False


def test_dpc_named_bbox_symbols_are_gone_from_radar_service():
    """Die Umbenennung ist eine echte Umbenennung, kein zusaetzlicher Alias:
    die anbieterbenannten Symbole existieren nicht mehr. Ein stehen
    gelassener Alias wuerde `services/official_alerts/dpc.py` erlauben,
    weiter den alten Namen zu importieren -- genau die Kopplung, die AC-3
    sichtbar machen soll."""
    import services.radar_service as rs

    for name in ("_within_dpc", "_DPC_LAT_MIN", "_DPC_LAT_MAX", "_DPC_LON_MIN", "_DPC_LON_MAX"):
        assert not hasattr(rs, name), (
            f"`services.radar_service.{name}` muss durch den gebietsbenannten "
            "Namen ersetzt sein (Umbenennung, kein Alias)"
        )


# ===========================================================================
# AC-6: Egress-Inventar (Python-Seite)
# ===========================================================================

def test_ac6_dpc_radar_host_removed_from_egress_inventory():
    """AC-6: der Radar-DPC-Host steht nicht mehr im Python-Egress-Inventar.
    Die Go-Zwillingsliste bewacht der bestehende
    `tests/test_egress_inventory_drift.py`."""
    from app.egress_guard import INVENTORY

    assert "radar-api.protezionecivile.it" not in INVENTORY, (
        "AC-6: der Radar-DPC-Host muss aus dem Egress-Inventar entfernt sein"
    )


def test_ac6_official_dpc_warning_host_is_a_different_host():
    """AC-6 (Gegenprobe): der amtliche DPC-Warn-Abruf haengt an einem ANDEREN
    Host (`raw.githubusercontent.com`, `DPC_ZIP_URL`) als die entfernte
    Radarquelle -- die Egress-Loeschung kann den Warnpfad also gar nicht
    treffen. Bewusst KEINE INVENTORY-Aussage zu diesem Host: er steht dort
    (gemessen am Stand 4e5098a7) ueberhaupt nicht drin, der Bulletin-Abruf
    laeuft im Test ueber einen echten lokalen `http.server` (s.
    `tests/tdd/test_dpc_bulletin_source.py`).
    """
    from services.official_alerts.dpc import DPC_ZIP_URL

    assert "raw.githubusercontent.com" in DPC_ZIP_URL, (
        "Vorbedingung: der amtliche DPC-Bulletin-Abruf laeuft ueber "
        f"raw.githubusercontent.com (war: {DPC_ZIP_URL})"
    )
    assert "protezionecivile.it" not in DPC_ZIP_URL, (
        "AC-6: der amtliche Warnpfad darf den entfernten Radar-Host nicht "
        f"benutzen (war: {DPC_ZIP_URL})"
    )
