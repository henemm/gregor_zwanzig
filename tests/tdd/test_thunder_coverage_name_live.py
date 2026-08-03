"""Live-Test zu #1457 S2a Fix (2026-08-03) — haelt die Naht zum echten Dienst.

Spec: docs/specs/fast/fix-1457-s2a-echte-abrufnamen.md (AC-2, AC-3)

Der urspruengliche Fehler (Coverage-Name `LITOTA3` existiert beim Dienst nicht,
Lauf-Ermittlung zu knapp) blieb unbemerkt, weil KEINER der 24 Kern-Tests die
Naht zum echten Meteo-France-Dienst beruehrt — alle lesen eine aufgezeichnete
Datei. Dieser Test liest den Coverage-Namen UND den vom Code ermittelten Lauf
AUS DEM PRODUKTIVCODE (`providers.meteofrance`), nicht als zweiten,
hart hineingeschriebenen Vergleichsstring — sonst prueft er sich selbst und
faengt die naechste Umbenennung wieder nicht. Beides wird gegen die echte
`GetCapabilities`-Antwort geprueft.

Marker `live`: laeuft NICHT im Commit-Gate, nur explizit via `pytest -m live`.
Kontingent (100 Anfragen/Minute): EIN Abruf liefert alles Noetige.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from providers import meteofrance as mf  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _require_meteofrance_key() -> None:
    if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
        pytest.skip("GZ_METEOFRANCE_APIKEY nicht konfiguriert (.env)")


@pytest.mark.live
def test_coverage_name_und_ermittelter_lauf_existieren_beim_dienst():
    """AC-2/AC-3: Given den echten Meteo-France-WCS-Dienst, When
    `GetCapabilities` abgefragt wird, Then kommt der IM PRODUKTIVCODE
    hinterlegte Blitzdichte-Coverage-Name darin vor, UND der vom Code fuer
    „jetzt" ermittelte primaere Lauf-Kandidat steht im Angebot."""
    _require_meteofrance_key()

    response = httpx.get(
        f"{mf.BASE_URL}GetCapabilities",
        params={"service": "WCS", "version": "2.0.1"},
        headers={"apikey": os.environ["GZ_METEOFRANCE_APIKEY"]},
        timeout=30.0,
    )
    response.raise_for_status()
    angebot = response.text

    # AC-2: der Name selbst muss beim Dienst existieren — aus der Konstante
    # gelesen, kein zweiter Vergleichsstring.
    assert mf.LIGHTNING_COVERAGE in angebot, (
        f"Der im Code hinterlegte Coverage-Name '{mf.LIGHTNING_COVERAGE}' "
        "kommt in GetCapabilities nicht vor — der Dienst kennt ihn nicht "
        "(oder hat ihn erneut umbenannt)"
    )

    # AC-3: der vom Code fuer "jetzt" ermittelte Lauf muss angeboten werden —
    # aus der echten Kandidaten-Funktion gelesen, nicht im Test nachgerechnet.
    laeufe = mf._thunder_run_candidates(datetime.now(timezone.utc))
    primaer_id = f"{mf.LIGHTNING_COVERAGE}___{mf._run_str(laeufe[0])}"
    assert primaer_id in angebot, (
        f"Der vom Code ermittelte Lauf '{primaer_id}' steht nicht im "
        "Angebot — der Sicherheitsabstand reicht nicht (oder wieder nicht)"
    )
