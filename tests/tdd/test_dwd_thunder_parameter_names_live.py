"""Live-Test — #1457 S2b AC-6: die Naht zum echten DWD-Open-Data-Dienst.

Spec: docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md (AC-6, PFLICHT)

WARUM DIESER TEST PFLICHT IST: Bei S2a hiess dieselbe Falle `LITOTA3` — der
Abrufname kam beim Meteo-France-Dienst 0-mal vor, jeder Abruf lief lautlos in
404, und 24 aufgezeichnete Tests blieben gruen, weil sie alle nur eine
Testdatei lasen und die Naht zum Dienst nie beruehrten. Genau diese Naht
prueft dieser Test.

Er liest Abrufnamen UND Lauf AUS DEM PRODUKTIVCODE (`providers.dwd`), nie als
zweite, hart hineingeschriebene Zeichenkette — sonst prueft er sich selbst und
verpasst die naechste Umbenennung.

Vermessung 2026-08-03 (Ergebnis, das diesen Test moeglich macht):
- `lpi`, `lpi_max` und `grau_gsp` existieren als Parameter-Ordner unter
  `.../icon-d2/grib/<HH>/`; je Lauf liegen dort 49 `regular-lat-lon`-Dateien
  (Zeitschritte 000..048, stuendlich) im identischen Namensmuster wie die vier
  bestehenden Basis-Parameter.
- Der Lauf 15:00Z war um 16:21:57 UTC vollstaendig veroeffentlicht (~1 h 22
  nach Lauf-Zeitpunkt); der Abstand von `_latest_run` (3-6 h) reicht also.

Marker `live`: laeuft NICHT im Commit-Gate (`addopts` schliesst `live` aus),
nur explizit via `pytest -m live`. Ein Abruf je Parameter, HEAD-artig klein
gehalten (Stream, sofort geschlossen).
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

from providers import dwd  # noqa: E402


@pytest.mark.live
@pytest.mark.parametrize("param_index", [0, 1])
def test_ac6_hinterlegte_gewitter_parameter_existieren_beim_echten_dienst(param_index):
    """AC-6: Given die im Produktivcode hinterlegten DWD-Parameternamen fuer
    Blitzpotenzial und Hagel, When gegen das echte Verzeichnis auf
    `opendata.dwd.de` geprueft wird, Then existiert die erwartete Datei
    tatsaechlich (HTTP 200) — kein lautloser 404.
    """
    params = tuple(dwd.THUNDER_PARAMS)
    assert len(params) >= 2, (
        f"`dwd.THUNDER_PARAMS` traegt {params} — erwartet werden mindestens "
        "zwei Signale (Blitzpotenzial und Hagel)"
    )
    param = params[param_index]

    lauf = dwd._thunder_run_candidates(datetime.now(timezone.utc))[0]
    url = dwd._build_url(lauf, 1, param)
    assert url.startswith("https://opendata.dwd.de/"), (
        f"Der Test wuerde nicht den echten Dienst pruefen — URL: {url}"
    )

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            status = response.status_code

    assert status == 200, (
        f"HTTP {status} fuer '{param}' unter {url}. Entweder heisst der "
        "Parameter beim DWD anders (Namensfalle wie `LITOTA3` bei S2a — dann "
        "laeuft im Betrieb JEDER Abruf lautlos in 404), oder der vom Code "
        "gewaehlte Lauf ist noch nicht veroeffentlicht (dann reicht der "
        "Sicherheitsabstand nicht)"
    )


@pytest.mark.live
def test_ac6_der_gewaehlte_lauf_ist_beim_dienst_veroeffentlicht():
    """AC-6, zweite Haelfte: Given den vom Code fuer 'jetzt' gewaehlten
    ICON-D2-Lauf, When das Lauf-Verzeichnis beim echten Dienst abgefragt wird,
    Then enthaelt es den Parameter-Ordner des Blitzpotenzials.

    Trennt die beiden moeglichen Ursachen eines 404 oben voneinander:
    falscher Name oder zu knapper Sicherheitsabstand.
    """
    lauf = dwd._thunder_run_candidates(datetime.now(timezone.utc))[0]
    param = tuple(dwd.THUNDER_PARAMS)[0]
    url = f"{dwd.BASE_URL}{lauf.hour:02d}/{param}/"

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url)

    assert response.status_code == 200, (
        f"Das Lauf-Verzeichnis {url} antwortet mit HTTP "
        f"{response.status_code} — der Parameter-Ordner existiert dort nicht"
    )
    kennung = lauf.strftime("%Y%m%d%H")
    assert kennung in response.text, (
        f"Der vom Code gewaehlte Lauf {kennung} liegt nicht im Verzeichnis "
        f"{url} — der Sicherheitsabstand von `_thunder_run_candidates` reicht "
        "nicht (S2a-Lehre: dort waren 3 h zu knapp)"
    )
