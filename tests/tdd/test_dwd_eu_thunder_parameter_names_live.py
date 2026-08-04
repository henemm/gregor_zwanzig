"""Live-Test — #1457 S2c AC-6: die Naht zum echten DWD-ICON-EU-Dienst.

Spec: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md (AC-6, PFLICHT)

WARUM PFLICHT: Bei S2a hiess dieselbe Falle `LITOTA3` — der Abrufname kam beim
Dienst 0-mal vor, jeder Abruf lief lautlos in 404, und 24 aufgezeichnete Tests
blieben gruen, weil sie alle nur eine Testdatei lasen und die Naht zum Dienst
nie beruehrten. `decision_matrix.md` Z.36 fuehrt `lpi_con_max` bislang
ausdruecklich als UNVERIFIZIERTEN Kurznamen.

Dieser Test liest Abrufname, Lauf und URL-Bau AUS DEM PRODUKTIVCODE
(`providers.dwd_eu`), nie als zweite, hart hineingeschriebene Zeichenkette —
sonst prueft er sich selbst und verpasst die naechste Umbenennung.

Marker `live`: laeuft NICHT im Commit-Gate (`addopts` schliesst `live` aus),
nur explizit via `pytest -m live`.

RED-GRUND: `providers.dwd_eu` existiert nicht -> ModuleNotFoundError.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tests.tdd._dwd_eu_fixtures import dwd_eu  # noqa: E402


@pytest.mark.live
def test_ac6_hinterlegter_parameter_existiert_beim_echten_dienst():
    """AC-6: Given den im Produktivcode hinterlegten ICON-EU-Parameternamen
    fuer Blitzpotenzial, When gegen `opendata.dwd.de` geprueft wird, Then
    existiert die erwartete Datei tatsaechlich (HTTP 200) — kein lautloser 404.
    """
    modul = dwd_eu()
    param = tuple(modul.THUNDER_PARAMS)[0]
    lauf = modul._thunder_run_candidates(datetime.now(timezone.utc))[0]
    url = modul._build_url(lauf, 1, param)
    assert url.startswith("https://opendata.dwd.de/"), (
        f"Der Test wuerde nicht den echten Dienst pruefen — URL: {url}"
    )

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        with client.stream("GET", url) as antwort:
            status = antwort.status_code

    assert status == 200, (
        f"HTTP {status} fuer '{param}' unter {url}. Entweder heisst der "
        "Parameter beim DWD anders (Namensfalle wie `LITOTA3` bei S2a — dann "
        "laeuft im Betrieb JEDER Abruf lautlos in 404), oder der Dateiname "
        "folgt nicht dem ICON-EU-Schema (`icon-eu_europe_...`, Suffix in "
        "GROSSBUCHSTABEN — anders als bei ICON-D2), oder der gewaehlte Lauf "
        "ist noch nicht veroeffentlicht"
    )


@pytest.mark.live
def test_ac6_der_gewaehlte_lauf_ist_beim_dienst_veroeffentlicht():
    """AC-6, zweite Haelfte: Given den vom Code fuer 'jetzt' gewaehlten
    ICON-EU-Lauf, When das Parameter-Verzeichnis beim echten Dienst abgefragt
    wird, Then enthaelt es genau diesen Lauf.

    Trennt die beiden moeglichen Ursachen eines 404 oben voneinander: falscher
    Name/falsches Schema oder zu knapper Sicherheitsabstand (gemessen braucht
    ICON-EU 3,6-4,5 h bis zur Veroeffentlichung).
    """
    modul = dwd_eu()
    param = tuple(modul.THUNDER_PARAMS)[0]
    lauf = modul._thunder_run_candidates(datetime.now(timezone.utc))[0]
    url = f"{modul.BASE_URL}{lauf.hour:02d}/{param}/"

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        antwort = client.get(url)

    assert antwort.status_code == 200, (
        f"Das Lauf-Verzeichnis {url} antwortet mit HTTP {antwort.status_code} "
        "— der Parameter-Ordner existiert dort nicht"
    )
    kennung = lauf.strftime("%Y%m%d%H")
    assert kennung in antwort.text, (
        f"Der vom Code gewaehlte Lauf {kennung} liegt nicht im Verzeichnis "
        f"{url} — der Sicherheitsabstand reicht nicht (S2a-Lehre: dort waren "
        "3 h zu knapp)"
    )
