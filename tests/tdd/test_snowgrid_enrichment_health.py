"""TDD RED -- Issue #1992 Amendment: Health-Journal von SNOWGRID.

Spec: docs/specs/modules/feat_1992_geosphere_health_amendment.md (AC-1..AC-3).
Vorbild: tests/tdd/test_thunder_enrichment_health_journal.py (#1581).

Deckt hier ab: AC-1 (echter Fehler in `fetch_snowgrid` -> `path="snowgrid"`,
`outcome="unavailable"`, Rueckgabe bleibt `(None, None)`), AC-2 (regulaerer
Abruf -> `outcome="ok"`), AC-3 (Regressions-Leitplanke, WICHTIGSTES AC:
`fetch_combined`/`fetch_forecast` duerfen NIEMALS an einem SNOWGRID-Fehler
scheitern -- auch nicht an einer generischen, NICHT-httpx Exception).

===========================================================================
Kein Mock-Theater
===========================================================================
Der Netzzugriff wird durch eine Ersatzklasse fuer `httpx.Client` vertreten,
die ECHTE `httpx.Response`-Objekte liefert bzw. echte `httpx`-Exceptions
wirft (Muster `_ScriptedClient`, tests/unit/test_radar_upstream_failure.py)
-- kein `Mock()`, kein `patch()` von Rueckgabewerten. Fuer AC-3 wird gezielt
`fetch_snowgrid` selbst per Monkeypatch zum Scheitern gebracht (so von der
Spec als Testmethode benannt) -- das beobachtete Verhalten ist danach der
ECHTE Rueckgabewert/die ECHTEN Datenpunkte von `fetch_combined()`/
`fetch_forecast()`, kein interner Aufruf-Zaehler. Das Journal wird ECHT
geschrieben und als JSONL geparst gelesen -- kein Substring-Test.

===========================================================================
Erwartete Rotfaerbung
===========================================================================
Alle Tests hier sind heute rot:
* AC-1/AC-2: `path="snowgrid"` existiert im Journal ueberhaupt nicht (weder
  `PATH_SNOWGRID` noch ein Aufruf von `log_enrichment_call` in
  `fetch_snowgrid`) -- jede Journal-Zusicherung scheitert an "keine Zeile".
* AC-3: `fetch_combined()` ruft `fetch_snowgrid()` heute UNGESCHUETZT auf
  (kein try/except). Wirft `fetch_snowgrid` eine generische Exception (hier
  `KeyError`, wie von der Spec als Beispiel genannt), propagiert sie durch
  `fetch_combined()` und (da `fetch_forecast()`s aeusseres except nur
  `httpx.HTTPStatusError`/`httpx.RequestError` faengt) auch durch
  `fetch_forecast()` bis zum Testaufruf -- `pytest.fail()` macht diesen
  Fehlschlag als klaren RED-Befund sichtbar statt eines unklaren Tracebacks.

Ausfuehrung:
    uv run pytest tests/tdd/test_snowgrid_enrichment_health.py \
        --disable-socket --allow-unix-socket -v
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import httpx
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from providers.geosphere import GeoSphereProvider  # noqa: E402

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")

_LAT, _LON = 46.40, 12.52  # innerhalb SNOWGRID_BOUNDS (Alpen)


# ---------------------------------------------------------------------------
# Fake-Client -- ersetzt den httpx.Client der GeoSphereProvider-Instanz,
# liefert ECHTE httpx.Response-Objekte bzw. wirft ECHTE httpx-Exceptions.
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, antwort_fn) -> None:
        self._antwort_fn = antwort_fn

    def get(self, url: str, *a, **kw):
        return self._antwort_fn(url)

    def close(self) -> None:
        pass


def _antwort_404(url: str) -> httpx.Response:
    """Nicht-retryable HTTP-Fehler (404 ist nicht in RETRY_STATUS_CODES
    {502,503,504}) -- vermeidet tenacity-Retries mit Wartezeit im Test."""
    return httpx.Response(
        404, request=httpx.Request("GET", url), json={"error": "not found"},
    )


def _wirft_timeout(url: str):
    """`httpx.TimeoutException` (Basisklasse, NICHT `ReadTimeout`) --
    `_is_retryable_error` prueft explizit nur auf `ConnectError`/
    `ReadTimeout`, die Basisklasse loest also KEINEN Retry aus."""
    raise httpx.TimeoutException("Zeitueberschreitung im Test")


def _wirft_request_error(url: str):
    """`httpx.RequestError` (Basisklasse) -- ebenfalls kein Retry-Trigger."""
    raise httpx.RequestError("Verbindungsfehler im Test")


def _antwort_snowgrid_erfolg(url: str) -> httpx.Response:
    body = {
        "features": [{"properties": {"parameters": {
            "snow_depth": {"data": [0.10, 0.15, 0.20]},
            "swe_tot": {"data": [10.0, 15.0, 20.0]},
        }}}],
    }
    return httpx.Response(200, request=httpx.Request("GET", url), json=body)


def _antwort_nwp_erfolg(url: str) -> httpx.Response:
    """Gueltige AROME-Antwort fuer `fetch_nwp_forecast` -- noetig, damit
    `fetch_combined()`/`fetch_forecast()` in AC-3 ueberhaupt bis zum
    SNOWGRID-Aufruf durchlaufen. Der Open-Meteo-Wolken-Zusatzabruf
    (`_fetch_openmeteo_clouds`, laeuft bei `fetch_forecast()` IMMER mit)
    ist selbst fail-soft -- ein Fehlschlag dort wird geschluckt und liefert
    nur leere Wolkendaten, deshalb wirft dieser Fake fuer jede
    open-meteo.com-URL bewusst einen (abgefangenen) Fehler."""
    if "open-meteo.com" in url:
        raise httpx.RequestError("Wolken-Zusatzabruf im Test nicht verkabelt")
    jetzt = datetime.now(timezone.utc)
    ts = [
        (jetzt + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M+00:00")
        for h in range(1, 4)
    ]
    body = {
        "timestamps": ts,
        "features": [{"properties": {"parameters": {
            "t2m": {"data": [10.0, 10.5, 11.0]},
            "u10m": {"data": [1.0, 1.0, 1.0]},
            "v10m": {"data": [1.0, 1.0, 1.0]},
            "ugust": {"data": [2.0, 2.0, 2.0]},
            "vgust": {"data": [2.0, 2.0, 2.0]},
            "rr_acc": {"data": [0.0, 0.0, 0.0]},
            "snow_acc": {"data": [0.0, 0.0, 0.0]},
            "snowlmt": {"data": [None, None, None]},
            "tcc": {"data": [0.5, 0.5, 0.5]},
            "rh2m": {"data": [50, 50, 50]},
            "sp": {"data": [101300, 101300, 101300]},
        }}}],
    }
    return httpx.Response(200, request=httpx.Request("GET", url), json=body)


# ---------------------------------------------------------------------------
# Journal-Helfer -- bewusst lokale Kopie (Testplumbing, kein geteilter
# Prueflingsbaustein), s. Docstring test_thunder_enrichment_health_journal.py.
# ---------------------------------------------------------------------------

def _journalpfad() -> Path:
    from app.loader import get_data_root
    return get_data_root().joinpath(*_JOURNAL_UNTERPFAD)


def _zeilen() -> List[dict]:
    pfad = _journalpfad()
    if not pfad.is_file():
        return []
    return [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]


def _snowgrid_zeilen() -> List[dict]:
    return [z for z in _zeilen() if z.get("path") == "snowgrid"]


def _letzte_snowgrid_zeile() -> dict:
    zeilen = _snowgrid_zeilen()
    assert zeilen, (
        f"Keine Journalzeile mit path='snowgrid' in {_journalpfad()} -- "
        f"vorhandene Zeilen: {_zeilen()}. Ohne PATH_SNOWGRID/den Journal-"
        f"Aufruf in fetch_snowgrid() entsteht die Datei gar nicht erst."
    )
    return zeilen[-1]


# ---------------------------------------------------------------------------
# AC-1: echter Fehler -> outcome="unavailable", Rueckgabe bleibt (None, None)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bezeichnung,antwort_fn",
    [
        ("httpx.HTTPStatusError (404)", _antwort_404),
        ("httpx.TimeoutException", _wirft_timeout),
        ("httpx.RequestError", _wirft_request_error),
    ],
)
def test_ac1_snowgrid_fehler_schreibt_unavailable_und_bleibt_fail_soft(
    bezeichnung: str, antwort_fn,
) -> None:
    assert _snowgrid_zeilen() == [], (
        f"Testaufbau ({bezeichnung}): Journal muss vor dem Abruf leer sein."
    )
    provider = GeoSphereProvider(client=_FakeClient(antwort_fn))

    ergebnis = provider.fetch_snowgrid(_LAT, _LON)

    assert ergebnis == (None, None), (
        f"AC-1 ({bezeichnung}): fetch_snowgrid() muss bei einem Fehler "
        f"weiterhin (None, None) liefern (fail-soft, unveraendertes "
        f"Rueckgabeverhalten), bekommen {ergebnis!r}"
    )

    zeile = _letzte_snowgrid_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-1 ({bezeichnung}): erwartet outcome='unavailable', bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )


# ---------------------------------------------------------------------------
# AC-2: regulaerer Abruf -> outcome="ok"
# ---------------------------------------------------------------------------

def test_ac2_snowgrid_erfolg_schreibt_ok_zeile() -> None:
    assert _snowgrid_zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein."
    )
    provider = GeoSphereProvider(client=_FakeClient(_antwort_snowgrid_erfolg))

    ergebnis = provider.fetch_snowgrid(_LAT, _LON)

    assert ergebnis == (20.0, 20.0), (
        f"Testaufbau: unerwartetes Parse-Ergebnis {ergebnis!r} -- die "
        f"Journalzeile unten wuerde einen anderen Ausgang beschreiben."
    )

    zeilen = _snowgrid_zeilen()
    assert len(zeilen) == 1, (
        f"AC-2: erwartet GENAU eine snowgrid-Zeile, bekommen {len(zeilen)}: "
        f"{zeilen}"
    )
    assert zeilen[0].get("outcome") == "ok", (
        f"AC-2: erwartet outcome='ok', bekommen {zeilen[0].get('outcome')!r} "
        f"(ganze Zeile: {zeilen[0]})"
    )
    unverfuegbar = [z for z in zeilen if z.get("outcome") == "unavailable"]
    assert unverfuegbar == [], (
        f"AC-2: bei Erfolg darf keine 'unavailable'-Zeile entstehen, "
        f"gefunden: {unverfuegbar}"
    )


# ---------------------------------------------------------------------------
# AC-3 (Regressions-Leitplanke, wichtigstes AC): SNOWGRID-Fehler darf die
# Grundvorhersage NIEMALS zum Scheitern bringen -- auch keine httpx-Klasse.
# ---------------------------------------------------------------------------

def _snowgrid_wirft_generisch(lat: float, lon: float):
    """Simuliert einen Fehler INNERHALB von `_parse_snowgrid_response`
    (z.B. unerwartete API-Antwortform) -- eine `KeyError`, wie von der Spec
    selbst als Beispiel benannt. KEINE `httpx`-Klasse: der spezifische
    Except in `fetch_snowgrid` selbst (Punkt 2 der Spec) faengt diese
    Exception NICHT -- nur eine zusaetzliche, breitere Absicherung in
    `fetch_combined` (Punkt 3) kann sie auffangen. Genau das ist die
    Leitplanke, die dieser Test bewacht."""
    raise KeyError("unerwartete SNOWGRID-Antwortform (simuliert)")


def test_ac3_snowgrid_fehler_laesst_grundvorhersage_nicht_scheitern() -> None:
    ort = Location(latitude=_LAT, longitude=_LON, name="Testort")

    # -- fetch_combined() direkt --
    provider = GeoSphereProvider(client=_FakeClient(_antwort_nwp_erfolg))
    provider.fetch_snowgrid = _snowgrid_wirft_generisch  # type: ignore[method-assign]

    try:
        kombiniert = provider.fetch_combined(
            lat=_LAT, lon=_LON, include_snow=True,
        )
    except Exception as e:  # noqa: BLE001 -- genau das ist die Zusicherung
        pytest.fail(
            f"AC-3: fetch_combined() darf NIEMALS an einem SNOWGRID-Fehler "
            f"scheitern (Regressions-Leitplanke fehlt), bekommen "
            f"{type(e).__name__}: {e}"
        )

    assert kombiniert.data, (
        "Testaufbau: fetch_combined() lieferte keine Datenpunkte -- dann "
        "prueft der Test unten nichts Sinnvolles."
    )
    assert all(dp.snow_depth_cm is None for dp in kombiniert.data), (
        "AC-3: bei einem SNOWGRID-Fehler duerfen keine Schneefelder gesetzt "
        "sein (die Grundvorhersage bleibt unbeschaedigt, aber ohne Schnee)."
    )

    # -- fetch_forecast() (der tatsaechliche Provider-Protokoll-Einstieg) --
    provider2 = GeoSphereProvider(client=_FakeClient(_antwort_nwp_erfolg))
    provider2.fetch_snowgrid = _snowgrid_wirft_generisch  # type: ignore[method-assign]

    try:
        vorhersage = provider2.fetch_forecast(ort)
    except Exception as e:  # noqa: BLE001
        pytest.fail(
            f"AC-3: fetch_forecast() darf NIEMALS an einem SNOWGRID-Fehler "
            f"scheitern, bekommen {type(e).__name__}: {e}"
        )

    assert vorhersage.data, (
        "Testaufbau: fetch_forecast() lieferte keine Datenpunkte."
    )
    assert all(dp.snow_depth_cm is None for dp in vorhersage.data), (
        "AC-3: auch ueber fetch_forecast() duerfen bei einem SNOWGRID-"
        "Fehler keine Schneefelder gesetzt sein."
    )
