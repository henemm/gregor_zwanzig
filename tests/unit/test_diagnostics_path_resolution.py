"""Diagnose-/Cache-Journale folgen der Datenwurzel zur LAUFZEIT (Issue #1633).

Vier Modul-Konstanten binden ihren Pfad heute beim Import fest und repo-relativ
(`Path("data/...")`), statt ihn beim Schreiben ueber `app.loader.get_data_root()`
aufzuloesen. Folge: der Python-Kern schreibt in den Programmordner, die Go-API
liest an der Produktiv-Datenwurzel — das Health-Signal ist tot.

Spec: docs/specs/modules/fix_1633_datenwurzel_diagnose_journale.md (AC-1..AC-4).

Jeder Test prueft ZWEI Dinge: die Datei landet unter der gesetzten Datenwurzel
UND es entsteht kein `data/`-Ordner neben dem Arbeitsverzeichnis. Ohne die
Gegenprobe waere ein Fix gruen, der zusaetzlich weiter am falschen Ort schreibt.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

WORKTREE = Path(__file__).resolve().parents[2]


def _pruefe_ziel(wurzel: Path, arbeitsordner: Path, rel: str) -> Path:
    """Gegenprobe zuerst, dann Zielpfad — die Reihenfolge macht die Fehlermeldung
    aussagekraeftig: sie nennt, WO stattdessen geschrieben wurde."""
    daneben = sorted(str(p.relative_to(arbeitsordner)) for p in arbeitsordner.rglob("*"))
    assert not daneben, (
        f"Neben dem Arbeitsverzeichnis {arbeitsordner} ist etwas entstanden: "
        f"{daneben} — die Datenwurzel {wurzel} wurde nicht beachtet."
    )
    ziel = wurzel / rel
    assert ziel.exists(), f"{rel} fehlt unter der Datenwurzel {wurzel}"
    return ziel


@pytest.fixture(params=["GZ_DATA_DIR", "_DATA_ROOT"])
def datenwurzel(request, tmp_path, monkeypatch):
    """Datenwurzel NACH dem Import umstellen, Arbeitsverzeichnis daneben legen.

    Beide Wege werden geprueft, weil ``get_data_root()`` sie unterschiedlich
    gewichtet (``_DATA_ROOT`` > ``GZ_DATA_DIR``): ein Fix, der nur die
    Umgebungsvariable liest, faellt sonst nicht auf. Die autouse-Fixture #1133
    setzt ``_DATA_ROOT`` bereits — fuer den ENV-Weg muss sie geraeumt werden.
    """
    from app import loader

    wurzel, arbeitsordner = tmp_path / "datenwurzel", tmp_path / "arbeitsordner"
    wurzel.mkdir()
    arbeitsordner.mkdir()
    if request.param == "GZ_DATA_DIR":
        monkeypatch.setattr(loader, "_DATA_ROOT", None, raising=False)
        monkeypatch.setenv("GZ_DATA_DIR", str(wurzel))
    else:
        monkeypatch.delenv("GZ_DATA_DIR", raising=False)
        monkeypatch.setattr(loader, "_DATA_ROOT", str(wurzel), raising=False)
    monkeypatch.chdir(arbeitsordner)
    return wurzel, arbeitsordner


def test_prueflinge_stammen_aus_diesem_checkout():
    """Pfadregel #1409: aus einem Worktree darf nicht die Hauptrepo-Kopie
    geprueft werden — sonst meldet dieser Test falsches Gruen."""
    from providers import call_log, openmeteo
    from services.official_alerts import warn_egress

    for modul in (call_log, openmeteo, warn_egress):
        assert Path(modul.__file__).resolve().is_relative_to(WORKTREE), modul.__file__


def test_ac1_openmeteo_journal_folgt_der_datenwurzel(datenwurzel):
    from providers import call_log

    wurzel, arbeitsordner = datenwurzel
    call_log.log_api_call("https://api.open-meteo.com/v1/forecast", 200)

    ziel = _pruefe_ziel(wurzel, arbeitsordner, "diagnostics/openmeteo_calls.jsonl")
    assert json.loads(ziel.read_text().splitlines()[-1])["status"] == 200


def test_ac1_provider_wrapper_schreibt_in_dieselbe_datenwurzel(datenwurzel):
    """`openmeteo.py` traegt eine ZWEITE Konstante fuer dieselbe Zieldatei
    (Risiko 4 der Analyse) — der Wrapper spiegelt sie vor dem Delegieren an
    `call_log`. Wer nur die erste Fundstelle umstellt, faellt hier auf."""
    from providers.openmeteo import OpenMeteoProvider

    wurzel, arbeitsordner = datenwurzel
    OpenMeteoProvider()._log_api_call("https://api.open-meteo.com/v1/ecmwf", 503, "boom")

    ziel = _pruefe_ziel(wurzel, arbeitsordner, "diagnostics/openmeteo_calls.jsonl")
    assert json.loads(ziel.read_text().splitlines()[-1])["error"] == "boom"


def test_ac2_warn_journal_folgt_der_datenwurzel(datenwurzel, monkeypatch):
    from services.official_alerts import warn_egress

    # tests/conftest.py lenkt die Modul-Konstante WARN_CALLS_PATH global auf eine
    # Wegwerf-Datei um. Bliebe die Umlenkung stehen, bewiese ein gruener Test nur
    # die Fixture, nicht die Datenwurzel. Der urspruengliche repo-relative Wert
    # wird deshalb zurueckgesetzt: der Schreibvorgang darf ihm nicht mehr folgen.
    monkeypatch.setattr(
        warn_egress,
        "WARN_CALLS_PATH",
        Path("data/diagnostics/warn_service_calls.jsonl"),
        raising=False,
    )
    wurzel, arbeitsordner = datenwurzel
    warn_egress.log_warn_service_call(
        "meteoalarm", "feeds.meteoalarm.org", status=200, cache_hit=False, ok=True
    )

    ziel = _pruefe_ziel(wurzel, arbeitsordner, "diagnostics/warn_service_calls.jsonl")
    assert json.loads(ziel.read_text().splitlines()[-1])["service"] == "meteoalarm"


def test_ac3_verfuegbarkeits_cache_folgt_der_datenwurzel(datenwurzel):
    from providers.openmeteo import OpenMeteoProvider

    wurzel, arbeitsordner = datenwurzel
    provider = OpenMeteoProvider()
    ergebnis = {
        "probe_date": date.today().isoformat(),
        "models": {"icon_d2": {"available": ["cape"], "unavailable": []}},
    }
    provider._save_availability_cache(ergebnis)

    ziel = _pruefe_ziel(wurzel, arbeitsordner, "cache/model_availability.json")
    assert json.loads(ziel.read_text()) == ergebnis
    # Lesen muss derselben Wurzel folgen, sonst waere der Cache nach dem Fix tot.
    assert provider._load_availability_cache() == ergebnis


def test_ac4_wurzel_wird_beim_schreiben_aufgeloest_nicht_beim_import(tmp_path, monkeypatch):
    """Kern des Fehlers: eine Modul-Konstante wird beim Import gebunden, also vor
    jeder Fixture. Hier wird die Wurzel ZWISCHEN zwei Schreibvorgaengen
    umgestellt — die zweite Zeile muss der neuen Wurzel folgen."""
    from app import loader
    from providers import call_log

    erste, zweite, arbeitsordner = tmp_path / "a", tmp_path / "b", tmp_path / "cwd"
    for ordner in (erste, zweite, arbeitsordner):
        ordner.mkdir()
    monkeypatch.delenv("GZ_DATA_DIR", raising=False)
    monkeypatch.chdir(arbeitsordner)

    monkeypatch.setattr(loader, "_DATA_ROOT", str(erste), raising=False)
    call_log.log_api_call("https://api.open-meteo.com/v1/frueh", 200)
    monkeypatch.setattr(loader, "_DATA_ROOT", str(zweite), raising=False)
    call_log.log_api_call("https://api.open-meteo.com/v1/spaet", 200)

    rel = "diagnostics/openmeteo_calls.jsonl"
    assert not (arbeitsordner / "data").exists(), "repo-relativer data/-Ordner entstanden"
    assert (zweite / rel).exists(), f"zweite Zeile folgte der neuen Wurzel {zweite} nicht"
    assert "spaet" in (zweite / rel).read_text()
    assert (erste / rel).exists(), f"erste Zeile fehlt unter {erste}"
    assert "spaet" not in (erste / rel).read_text(), "Wurzelwechsel blieb wirkungslos"
