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

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
_REPO_ROOT = _SRC.parent
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


# ---------------------------------------------------------------------------
# #1531 S1 AC-8: dieselbe Mutations-Gegenprobe wie beim ICON-D2-Waechter
# (test_dwd_thunder_parameter_names_live.py) -- der EU-Waechter ist heute
# sogar noch enger festgenagelt: `[0]` statt `[0, 1]`, also EIN einzelner
# fest gewaehlter Index. String-Ersetzung mit externer Sicherungskopie im
# Testkoerper, garantierte Rueckschreibung in `finally`, NIE per
# `git checkout/stash/reset` (CLAUDE.md "Mutations-Gegenprobe ist PFLICHT").
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_ac8_mutations_gegenprobe_erfundener_parameter_an_letzter_position_wird_heute_nicht_gefangen():
    """AC-8: Given `THUNDER_PARAMS` des ICON-EU-Providers traegt einen
    erfundenen Namen an letzter Position, When der Live-Waechter darauf
    laeuft, Then MUSS er rot werden (AC-8-Zusage).

    HEUTIGER Befund (RED-Grund dieses Tests): der Waechter liest
    ausschliesslich `tuple(modul.THUNDER_PARAMS)[0]` -- bei einem zweiten,
    angehaengten (erfundenen) Eintrag bleibt er GRUEN, weil Index 0 weiterhin
    der gueltige `lpi_con_max`-Name ist. Dieser Test wird erst GREEN, wenn
    der Waechter dynamisch ALLE Eintraege prueft.
    """
    dwd_eu_pfad = _SRC / "providers" / "dwd_eu.py"
    original_quelltext = dwd_eu_pfad.read_text(encoding="utf-8")
    alte_zeile = 'THUNDER_PARAMS = ("lpi_con_max",)'
    assert alte_zeile in original_quelltext, (
        "Die erwartete THUNDER_PARAMS-Zeile wurde in dwd_eu.py nicht gefunden "
        "-- die Mutation kann nicht angesetzt werden. KEINE Aenderung vorgenommen."
    )
    fake_param = "erfundener_gewitterparameter_1531_ac8"
    neue_zeile = f'THUNDER_PARAMS = ("lpi_con_max", "{fake_param}")'
    mutierter_quelltext = original_quelltext.replace(alte_zeile, neue_zeile, 1)
    assert mutierter_quelltext != original_quelltext, "Mutation griff nicht"

    guard_datei = Path(__file__).resolve()
    try:
        dwd_eu_pfad.write_text(mutierter_quelltext, encoding="utf-8")
        ergebnis = subprocess.run(
            [sys.executable, "-m", "pytest", "-m", "live", "-q",
             str(guard_datei), "-k", "test_ac6_hinterlegter_parameter_existiert_beim_echten_dienst"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=120,
        )
    finally:
        dwd_eu_pfad.write_text(original_quelltext, encoding="utf-8")
        zurueckgelesen = dwd_eu_pfad.read_text(encoding="utf-8")
        assert zurueckgelesen == original_quelltext, (
            "RUECKSCHREIBUNG FEHLGESCHLAGEN -- dwd_eu.py weicht vom Original ab!"
        )

    assert ergebnis.returncode != 0, (
        "AC-8: der Waechter MUSS rot werden, wenn THUNDER_PARAMS einen "
        "erfundenen Namen an letzter Position traegt. Er blieb GRUEN -- "
        "heute, weil er nur Index 0 prueft (ein Waechter, der nicht "
        f"scheitern kann, bewacht nichts). Ausgabe:\n"
        f"{ergebnis.stdout}\n{ergebnis.stderr}"
    )
