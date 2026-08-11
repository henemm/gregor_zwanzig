"""TDD RED -- #1531 S1: DWD ICON-EU liefert die Energiegroessen
(cape_ml, cape_con, cin_ml) fuer Rest-Europa.

Spec: docs/specs/modules/feat_1531_s1_dwd_gewittergroessen.md
Abgedeckte ACs hier (Provider-Ebene): AC-1 (Teil), AC-6.
(AC-8 -> Mutations-Gegenprobe in test_dwd_eu_thunder_parameter_names_live.py.)

===========================================================================
EMPIRISCHE VERMESSUNG DES ECHTEN DIENSTES (2026-08-11, opendata.dwd.de)
===========================================================================
1. ABRUFNAMEN -- bestaetigt. Unter `.../icon-eu/grib/00/` existieren die
   Ordner `cape_ml`, `cape_con`, `cin_ml` (identisches Dateischema wie
   `lpi_con_max`: `icon-eu_europe_..._<PARAM_GROSS>.grib2.bz2`).
2. WERTE (Lauf 2026-08-11T00Z, Zeitschritt +000, Abruzzen 41,8125 N /
   13,3750 O -- dieselbe Koordinate wie die bestehende `lpi_con_max`-
   Aufzeichnung): `cape_ml` = 20,75 J/kg, `cape_con` = 0,9375 J/kg,
   `cin_ml` = 104,47 J/kg -- alle drei real und von Null verschieden.
3. NEBENBEFUND (nicht Teil der Spec-Vorbedingung -- die nennt `cin_ml` bei
   ICON-EU ausdruecklich als "ungemessen"): auch bei ICON-EU traegt `cin_ml`
   den Marker -999,9 (min. gemessen -999,9, an vielen Gitterpunkten). Diese
   Datei nutzt das NICHT fuer eine eigene AC-2-Zusicherung (Spec: "AC-2 gilt
   zunaechst fuer ICON-D2") -- der Fund gehoert in den Abschlussbericht.
4. DATEIGROESSEN: deutlich groesser als die bestehende `lpi_con_max`-
   Aufzeichnung (177 KB), weil `cape_ml`/`cape_con`/`cin_ml` KONTINUIERLICHE
   Felder sind (an praktisch jedem Gitterpunkt ein Wert): 507 KB, 815 KB,
   534 KB (offset +000, kleinster gemessener Zeitschritt).

RED-GRUND (heute, unveraenderter Code): `providers.dwd_eu.THUNDER_PARAMS`
traegt nur `("lpi_con_max",)`; `ForecastDataPoint` hat weder
`cape_ml_jkg` noch `convective_inhibition_jkg`.

Testart: Provider-Ebene, lokaler `ThreadingHTTPServer` (Muster
test_dwd_eu_thunder_signal_fetch.py, `_dwd_eu_fixtures.eu_server` mit dem
neuen `fixtures=`-Dispatch). Kein echtes Netz, trotzdem `pytestmark =
pytest.mark.live` (identisches Vorbild, CI-Vermessung #1196).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tests.tdd._dwd_eu_fixtures import (  # noqa: E402
    ABRUZZEN, FIXTURE, FIXTURE_CAPE_CON, FIXTURE_CAPE_ML, FIXTURE_CIN_ML,
    dwd_eu, eu_server, rohwert_an,
)

pytestmark = pytest.mark.live

# Ort ausserhalb jedes ICON-EU-Feldbereichs mit echten Daten -- dient nur der
# Rest-Europa-Gebiets-Zustaendigkeit (Spec AC-6), hier per bestehendem
# ABRUZZEN-Ort geprueft, der die Aufzeichnungen traegt.


def _fixtures_dict() -> dict:
    """Parameter->Bytes fuer alle vier ICON-EU-Gewittersignale (bestehend +
    drei neue), damit ein Test alle gleichzeitig unterschiedlich beantwortet
    bekommt (Muster: `_dwd_eu_fixtures.eu_server(..., fixtures=...)`)."""
    return {
        "lpi_con_max": FIXTURE.read_bytes(),
        "cape_ml": FIXTURE_CAPE_ML.read_bytes(),
        "cape_con": FIXTURE_CAPE_CON.read_bytes(),
        "cin_ml": FIXTURE_CIN_ML.read_bytes(),
    }


# ---------------------------------------------------------------------------
# AC-1 -- Provider-Haelfte: die drei neuen Signale kommen mit ihrem Rohwert an.
# ---------------------------------------------------------------------------

def test_ac1_drei_neue_energiesignale_kommen_mit_ihrem_rohwert_an(monkeypatch):
    """AC-1: Given Aufzeichnungen fuer `cape_ml`, `cape_con` und `cin_ml`
    (Abruzzen, echte Werte), When `fetch_thunder_signals_named` am
    ICON-EU-Provider laeuft, Then tragen alle drei Signale ein Ergebnis mit
    genau dem Rohwert der jeweiligen Aufzeichnung."""
    modul = dwd_eu()
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with eu_server(monkeypatch, fixtures=_fixtures_dict()):
        ergebnis = modul.DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, start + timedelta(hours=3),
        )

    erwartungen = {
        "cape_ml": rohwert_an(FIXTURE_CAPE_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude),
        "cape_con": rohwert_an(FIXTURE_CAPE_CON.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude),
        "cin_ml": rohwert_an(FIXTURE_CIN_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude),
    }
    for signal, erwartet in erwartungen.items():
        assert erwartet > 0, f"Aufzeichnung fuer '{signal}' traegt an Abruzzen keinen echten Wert"
        werte = [v for v in ergebnis.get(signal, {}).values() if v is not None]
        assert werte, f"Signal '{signal}' fehlt komplett im Ergebnis {sorted(ergebnis)}"
        assert any(abs(v - erwartet) < 0.001 for v in werte), (
            f"Signal '{signal}': Werte {sorted(set(werte))} treffen nicht den "
            f"Rohwert der Aufzeichnung ({erwartet})"
        )


def test_ac1_gegenprobe_drei_signale_bleiben_unterscheidbar(monkeypatch):
    """AC-1, Gegenprobe: Given drei GETRENNTE Aufzeichnungen mit
    unterschiedlichen Rohwerten, When die Signale geholt werden, Then landet
    kein Wert im falschen Signal (z.B. `cape_con`-Wert im `cin_ml`-Feld) --
    sonst waeren AC-1 UND AC-6 (getrennte Felder) trotz falscher Zuordnung
    gruen."""
    modul = dwd_eu()
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    roh_cape_ml = rohwert_an(FIXTURE_CAPE_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    roh_cape_con = rohwert_an(FIXTURE_CAPE_CON.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    roh_cin_ml = rohwert_an(FIXTURE_CIN_ML.read_bytes(), ABRUZZEN.latitude, ABRUZZEN.longitude)
    werte_dreier = sorted({round(roh_cape_ml, 2), round(roh_cape_con, 2), round(roh_cin_ml, 2)})
    assert len(werte_dreier) == 3, (
        f"Die drei Aufzeichnungen tragen an Abruzzen keine drei unterscheidbaren "
        f"Werte ({werte_dreier}) -- der Test koennte eine Vertauschung nicht erkennen"
    )

    with eu_server(monkeypatch, fixtures=_fixtures_dict()):
        ergebnis = modul.DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, start + timedelta(hours=3),
        )

    cape_con_werte = [v for v in ergebnis.get("cape_con", {}).values() if v is not None]
    assert cape_con_werte and all(abs(v - roh_cape_ml) > 0.01 for v in cape_con_werte), (
        f"cape_con-Werte {cape_con_werte} treffen den cape_ml-Rohwert "
        f"({roh_cape_ml}) -- die Signale sind vertauscht"
    )


# ---------------------------------------------------------------------------
# AC-6 -- ICON-EU befuellt NUR die drei Energiegroessen, sdi_2/uh_max* bleiben
# `None` (die bietet ICON-EU laut Spec-Vorbedingung nicht an).
# ---------------------------------------------------------------------------

def test_ac6_icon_eu_liefert_nur_die_drei_energiegroessen_kein_sdi2_kein_uh_max(
    monkeypatch,
):
    """AC-6: Given einen Ort im ICON-EU-Gebiet, When die Anreicherung laeuft,
    Then werden `cape_ml`, `cape_con`, `cin_ml` befuellt, und der Provider
    bietet weder `sdi_2` noch irgendeine `uh_max*`-Variante an -- ICON-EU hat
    diese Groessen laut Spec-Vorbedingung schlicht nicht im Angebot.
    """
    modul = dwd_eu()
    params = tuple(modul.THUNDER_PARAMS)
    assert set(params) & {"sdi_2", "uh_max", "uh_max_med", "uh_max_low"} == set(), (
        f"THUNDER_PARAMS des ICON-EU-Providers traegt {params} -- eine dieser "
        "vier D2-exklusiven Groessen wird angeboten, obwohl ICON-EU sie laut "
        "Spec-Vorbedingung nicht bereitstellt"
    )
    assert {"cape_ml", "cape_con", "cin_ml"} <= set(params), (
        f"THUNDER_PARAMS des ICON-EU-Providers {params} deckt nicht alle drei "
        "erwarteten Energiegroessen ab"
    )
