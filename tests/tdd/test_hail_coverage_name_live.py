"""TDD RED -- #1507 (S5c zu #1475, Epic #1419, Block C von #2257): Live-
Namensverifikation fuer den Hagel-Coverage-Abruf von Meteo-France,
PFLICHT-VORARBEIT vor jeder Implementierung (PO-Kommentar 2026-09-20 zu
Issue #1507).

Spec: docs/specs/modules/feat_1507_s5c_hagel_mf_fr.md (AC-1)

1:1-Muster `test_thunder_coverage_name_live.py` (#1457 S2a Fix): die im
Issue-Kommentar vom 2026-08-03 genannten Kandidatennamen
(`HAIL__GROUND_OR_WATER_SURFACE`, `GRAUPEL__GROUND_OR_WATER_SURFACE`) sind
>1 Monat alt und werden HIER frisch gegen eine echte `GetCapabilities`-
Antwort geprueft -- aus der PRODUKTIVKONSTANTE gelesen, nicht als zweiter,
hart hineingeschriebener Vergleichsstring (S2a-Lehre: `LITOTA3` existierte
beim Dienst nicht, alle 24 damaligen Kern-Tests blieben trotzdem gruen, weil
sie nur eine aufgezeichnete Datei lasen).

Die Konstante (`meteofrance.HAIL_COVERAGE`) existiert VOR der
Implementierung noch nicht -- dieser Test ist bewusst ROT (AttributeError),
bis die GREEN-Phase sie anlegt UND den Namen frisch verifiziert hat. Ohne
gruenen AC-1 wird KEIN Name in Produktivcode verdrahtet (Spec, Reihenfolge-
Abhaengigkeit).

Marker `live`: laeuft NICHT im Commit-Gate, nur explizit via `pytest -m live`.
Kontingent (100 Anfragen/Minute): EIN `GetCapabilities`-Abruf liefert alles
Noetige.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from providers import meteofrance as mf  # noqa: E402


def _require_meteofrance_key() -> None:
    if not os.environ.get("GZ_METEOFRANCE_APIKEY"):
        pytest.skip("GZ_METEOFRANCE_APIKEY nicht konfiguriert (.env)")


# Issue #1196 Klasse B: kein modulweites `load_dotenv()` mehr. Autouse-
# Fixture fordert stattdessen die geteilte `dotenv_env`-Fixture aus
# tests/conftest.py an, bevor JEDER Test dieser Datei laeuft.
@pytest.fixture(autouse=True)
def _dotenv(dotenv_env):
    yield


@pytest.mark.live
def test_hail_coverage_name_existiert_beim_dienst():
    """AC-1: Given den echten Meteo-France-WCS-Dienst, When
    `GetCapabilities` abgefragt wird, Then kommt der im Produktivcode
    hinterlegte Hagel-Coverage-Name (`meteofrance.HAIL_COVERAGE`) darin vor
    -- aus der Konstante gelesen, nicht als zweiter, fest hineingeschriebener
    Vergleichsstring.
    """
    _require_meteofrance_key()

    response = httpx.get(
        f"{mf.BASE_URL}GetCapabilities",
        params={"service": "WCS", "version": "2.0.1"},
        headers={"apikey": os.environ["GZ_METEOFRANCE_APIKEY"]},
        timeout=30.0,
    )
    response.raise_for_status()
    angebot = response.text

    # AC-1: der Name selbst muss beim Dienst existieren -- aus der Konstante
    # gelesen. Existiert die Konstante noch nicht (Zustand vor der
    # Implementierung), wirft dieser Zugriff einen AttributeError -- das ist
    # die erwartete RED-Evidenz dieser Scheibe.
    assert mf.HAIL_COVERAGE in angebot, (
        f"Der im Code hinterlegte Hagel-Coverage-Name "
        f"'{mf.HAIL_COVERAGE}' kommt in GetCapabilities nicht vor -- der "
        "Dienst kennt ihn nicht (die im Issue #1507 genannten Kandidaten "
        "sind >1 Monat alt und muessen frisch verifiziert werden, "
        "S2a-Lehre: LITOTA3 existierte beim Dienst ebenfalls nicht)"
    )

    # AC-1 (Adversary #1507 F002): der BASISNAME allein beweist zu wenig.
    # Waere `HAIL_COVERAGE_SUFFIX` leer, hiesse die gebildete ID
    # `HAIL__..._2026-09-20T09.00.00Z` — sie enthaelt den Basisnamen genauso
    # UND ist zusaetzlich ein PRAEFIX der richtigen, voll lauf-qualifizierten
    # ID. Ein Teilstring-Vergleich gegen das Gesamtdokument ueberlebt solche
    # Mutationen deshalb prinzipiell. Abgerufen wird aber die VOLLE ID; nur
    # sie darf ueber "existiert beim Dienst" entscheiden.
    #
    # Darum: die angebotenen IDs aus `<wcs:CoverageId>` herausloesen und auf
    # EXAKTE Mengenzugehoerigkeit pruefen — das schliesst die ganze
    # Praefix-Klasse aus, nicht nur den einen Suffix-Fall.
    ids = set(
        re.findall(
            r"<(?:\w+:)?CoverageId>\s*([^<]+?)\s*</(?:\w+:)?CoverageId>",
            angebot,
        )
    )
    assert ids, (
        "Aus GetCapabilities liess sich keine einzige Coverage-ID "
        "herausloesen — das Antwortformat hat sich geaendert; die Pruefung "
        "unten liefe sonst gegen eine leere Menge und waere wertlos"
    )

    # Denselben Weg gehen wie der Produktivcode: Lauf-Kandidaten aus der
    # AKTUELLEN Zeit (das Lauf-Datum wechselt mehrmals taeglich — ein fester
    # Beleg von heute waere morgen falsch), primaerer Lauf = Kandidat 0.
    laeufe = mf._thunder_run_candidates(datetime.now(timezone.utc))
    primaer_id = (
        f"{mf.HAIL_COVERAGE}___{mf._run_str(laeufe[0])}"
        f"{mf.HAIL_COVERAGE_SUFFIX}"
    )
    assert primaer_id in ids, (
        f"Die vom Code gebildete Hagel-Coverage-ID '{primaer_id}' steht "
        "nicht im Angebot — entweder stimmt das Perioden-Suffix "
        f"('{mf.HAIL_COVERAGE_SUFFIX}') nicht, oder der Sicherheitsabstand "
        "zum Lauf reicht nicht. Jeder Abruf endete damit lautlos in 404 "
        "(S2a-Lehre: LITOTA3)"
    )
