"""RED-Tests: GPX-Upload muss pro Nutzer isoliert ablegen (Issue #1352).

SPEC: docs/specs/modules/issue_1352_gpx_user_isolation.md

Nachweis laeuft ueber den echten Endpoint POST /api/gpx/parse (TestClient
gegen api.main:app), mit echten Komoot-GPX-Dateien und echter Datei-Ein-/
Ausgabe -- keine Mocks, kein patch().
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE_DIR = _REPO_ROOT / "data" / "users" / "default" / "gpx"
# Zwei verschiedene reale Komoot-Exporte -- nur LESEN, nie ueberschreiben.
_SAMPLE_A = _SAMPLE_DIR / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
_SAMPLE_B = _SAMPLE_DIR / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"


def _sample(path: Path) -> bytes:
    """Reale GPX-Fixtur einlesen (absoluter Pfad, unabhaengig vom cwd)."""
    assert path.exists(), f"Fixtur-GPX fehlt: {path}"
    return path.read_bytes()


@pytest.fixture
def datenbaum(monkeypatch, tmp_path):
    """Isolierter Datenbaum mit produktionsnahem Arbeitsverzeichnis.

    Die autouse-Fixture ``_isolate_data_root`` (tests/conftest.py, Issue
    #1133) biegt ``app.loader._DATA_ROOT`` bereits auf ein tmp-Verzeichnis um;
    darunter liegen die Zielordner ``users/<user_id>/gpx``.

    Zusaetzlich zeigt hier ``./data`` im Arbeitsverzeichnis auf genau diesen
    isolierten Baum. In Produktion laeuft der Dienst mit dem Repo-Root als
    Arbeitsverzeichnis, wo ``./data`` ebenfalls DER Datenbaum ist -- der heute
    noch cwd-relative Schreibzugriff aus ``services.gpx_processing`` landet
    damit im Test dort, wo er auch in Produktion landet (im geteilten
    ``users/default/gpx``), statt im echten Repo-Datenbaum. Nach dem Fix ist
    die Verknuepfung wirkungslos, weil das Upload-Ziel ueber
    ``get_data_dir(user_id)`` absolut aufgeloest wird.
    """
    from app.loader import get_data_root

    root = get_data_root()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").symlink_to(root)
    return root


def _gpx_dir(user_id: str) -> Path:
    from app.loader import get_data_dir

    return get_data_dir(user_id) / "gpx"


def _dateien(verzeichnis: Path) -> set[str]:
    return {p.name for p in verzeichnis.glob("*.gpx")} if verzeichnis.exists() else set()


def _upload(client, inhalt: bytes, dateiname: str, user_id=None, **params):
    query = dict(params)
    if user_id is not None:
        query["user_id"] = user_id
    return client.post(
        "/api/gpx/parse",
        params=query,
        files={"file": (dateiname, inhalt, "application/gpx+xml")},
    )


def test_upload_landet_im_ordner_des_hochladenden_nutzers(datenbaum):
    """AC-1.

    GIVEN: zwei Nutzer laden je eine eigene GPX-Datei hoch
    WHEN: beide Uploads abgeschlossen sind
    THEN: jede Datei liegt im Ordner des jeweils hochladenden Nutzers, beim
          anderen Nutzer taucht keine neue Datei auf
    """
    from api.main import app

    client = TestClient(app)

    antwort_a = _upload(client, _sample(_SAMPLE_A), "alice-tour.gpx", user_id="alice")
    antwort_b = _upload(client, _sample(_SAMPLE_B), "bob-tour.gpx", user_id="bob")

    assert antwort_a.status_code == 200, antwort_a.text
    assert antwort_b.status_code == 200, antwort_b.text

    assert _dateien(_gpx_dir("alice")) == {"alice-tour.gpx"}, (
        f"alice-Ordner {_gpx_dir('alice')} enthaelt "
        f"{_dateien(_gpx_dir('alice'))} statt nur die eigene Datei"
    )
    assert _dateien(_gpx_dir("bob")) == {"bob-tour.gpx"}, (
        f"bob-Ordner {_gpx_dir('bob')} enthaelt "
        f"{_dateien(_gpx_dir('bob'))} statt nur die eigene Datei"
    )
    assert _dateien(_gpx_dir("default")) == set(), (
        "Uploads landeten im geteilten default-Ordner: "
        f"{_dateien(_gpx_dir('default'))}"
    )


def test_gleicher_dateiname_zweier_nutzer_ueberschreibt_nicht(datenbaum):
    """AC-2 (Kernnachweis).

    GIVEN: zwei Nutzer laden eine Datei mit exakt demselben Dateinamen, aber
           unterschiedlichem Inhalt hoch
    WHEN: beide Uploads nacheinander laufen
    THEN: beide Inhalte bleiben byte-genau erhalten, keiner ueberschreibt den
          anderen
    """
    from api.main import app

    client = TestClient(app)
    inhalt_alice = _sample(_SAMPLE_A)
    inhalt_bob = _sample(_SAMPLE_B)
    assert inhalt_alice != inhalt_bob, "Fixturen muessen unterscheidbar sein"

    assert _upload(client, inhalt_alice, "wanderung.gpx", user_id="alice").status_code == 200
    assert _upload(client, inhalt_bob, "wanderung.gpx", user_id="bob").status_code == 200

    pfad_alice = _gpx_dir("alice") / "wanderung.gpx"
    pfad_bob = _gpx_dir("bob") / "wanderung.gpx"

    assert pfad_alice.exists(), f"alice-Datei fehlt: {pfad_alice}"
    assert pfad_bob.exists(), f"bob-Datei fehlt: {pfad_bob}"
    assert pfad_alice.read_bytes() == inhalt_alice, (
        f"{pfad_alice} wurde ueberschrieben oder veraendert"
    )
    assert pfad_bob.read_bytes() == inhalt_bob, (
        f"{pfad_bob} wurde ueberschrieben oder veraendert"
    )


def test_praeparierter_dateiname_bricht_nicht_in_fremden_ordner_aus(datenbaum):
    """AC-3.

    GIVEN: ein Nutzer laedt eine GPX-Datei mit Verzeichnis-Aufstiegen im
           Dateinamen hoch (``../../bob/gpx/x.gpx``)
    WHEN: der Upload verarbeitet wird
    THEN: die Datei liegt unter ihrem reinen Namen im eigenen Ordner, der
          Ordner des anderen Nutzers bleibt unveraendert und ausserhalb des
          Datenbaums entsteht nichts
    """
    from api.main import app

    bob_gpx = _gpx_dir("bob")
    bob_gpx.mkdir(parents=True, exist_ok=True)
    (bob_gpx / "bestand.gpx").write_bytes(_sample(_SAMPLE_B))
    bob_vorher = {p.name: p.read_bytes() for p in bob_gpx.iterdir()}

    client = TestClient(app, raise_server_exceptions=False)
    antwort = _upload(
        client, _sample(_SAMPLE_A), "../../bob/gpx/x.gpx", user_id="alice"
    )

    assert antwort.status_code == 200, antwort.text

    bob_nachher = {p.name: p.read_bytes() for p in bob_gpx.iterdir()}
    assert bob_nachher == bob_vorher, (
        f"bob-Ordner {bob_gpx} wurde veraendert: "
        f"{sorted(bob_nachher)} statt {sorted(bob_vorher)}"
    )
    assert _dateien(_gpx_dir("alice")) == {"x.gpx"}, (
        f"alice-Ordner {_gpx_dir('alice')} enthaelt "
        f"{_dateien(_gpx_dir('alice'))} statt {{'x.gpx'}}"
    )
    ausserhalb = sorted(p for p in Path.cwd().rglob("x.gpx") if not p.is_symlink())
    assert not ausserhalb, f"Datei ausserhalb des Datenbaums geschrieben: {ausserhalb}"


def test_upload_ohne_nutzer_wird_abgewiesen_und_schreibt_nichts(datenbaum):
    """AC-4.

    GIVEN: eine Anfrage an den Upload-Endpoint ohne erkennbaren Nutzer
    WHEN: die Anfrage verarbeitet wird
    THEN: sie wird mit Fehlerstatus abgewiesen und es entsteht kein neuer
          Eintrag in einem geteilten oder nutzerlosen Ordner
    """
    from api.main import app

    client = TestClient(app)
    antwort = _upload(client, _sample(_SAMPLE_A), "heimatlos.gpx")

    assert antwort.status_code == 422, (
        f"Upload ohne user_id lieferte {antwort.status_code} statt 422"
    )
    geschrieben = sorted(str(p) for p in datenbaum.rglob("*.gpx"))
    assert not geschrieben, f"Upload ohne user_id hat geschrieben: {geschrieben}"


def test_praeparierte_nutzerkennung_bricht_nicht_in_fremden_ordner_aus(datenbaum):
    """AC-6.

    GIVEN: bob hat eine GPX-Datei in seinem Ordner, und jemand ruft den
           Endpoint mit einer Nutzerkennung auf, die Verzeichnis-Aufstiege
           enthaelt (``../users/bob``)
    WHEN: der Upload verarbeitet wird
    THEN: die Anfrage wird abgewiesen und bobs Ordner ist byte-genau unveraendert
    """
    from api.main import app

    bob_gpx = _gpx_dir("bob")
    bob_gpx.mkdir(parents=True, exist_ok=True)
    (bob_gpx / "bestand.gpx").write_bytes(_sample(_SAMPLE_B))
    bob_vorher = {p.name: p.read_bytes() for p in bob_gpx.iterdir()}

    client = TestClient(app, raise_server_exceptions=False)
    antwort = _upload(
        client, _sample(_SAMPLE_A), "eindringling.gpx", user_id="../users/bob"
    )

    bob_nachher = {p.name: p.read_bytes() for p in bob_gpx.iterdir()}
    assert bob_nachher == bob_vorher, (
        f"bob-Ordner {bob_gpx} wurde veraendert: "
        f"{sorted(bob_nachher)} statt {sorted(bob_vorher)}"
    )
    assert antwort.status_code == 400, (
        f"Praeparierte Nutzerkennung lieferte {antwort.status_code} statt 400: "
        f"{antwort.text}"
    )


@pytest.mark.parametrize("kennung", ["..", "", "a/b", "../../../tmp"])
def test_unbrauchbare_nutzerkennung_wird_abgewiesen(datenbaum, kennung):
    """AC-6 (weitere Formen).

    GIVEN: eine Nutzerkennung, die keinen gueltigen Ordnernamen bezeichnet
    WHEN: ein Upload damit versucht wird
    THEN: die Anfrage wird abgewiesen und es entsteht keine neue Datei im
          Datenbaum
    """
    from api.main import app

    vorher = sorted(str(p) for p in datenbaum.rglob("*.gpx"))
    client = TestClient(app, raise_server_exceptions=False)
    antwort = _upload(client, _sample(_SAMPLE_A), "eindringling.gpx", user_id=kennung)

    assert antwort.status_code == 400, (
        f"Kennung {kennung!r} lieferte {antwort.status_code} statt 400: {antwort.text}"
    )
    assert sorted(str(p) for p in datenbaum.rglob("*.gpx")) == vorher, (
        f"Kennung {kennung!r} hat in den Datenbaum geschrieben"
    )


@pytest.mark.parametrize("kennung", ["default", "validator-issue110", "alice"])
def test_echte_nutzerkennungen_werden_weiterhin_akzeptiert(datenbaum, kennung):
    """AC-6 (Gegenprobe).

    GIVEN: die real vorkommenden Formen von Nutzerkennungen
    WHEN: ein Upload damit laeuft
    THEN: er wird angenommen und landet im Ordner dieses Nutzers -- die Pruefung
          sperrt keine echten Nutzer aus
    """
    from api.main import app

    client = TestClient(app)
    antwort = _upload(client, _sample(_SAMPLE_A), "tour.gpx", user_id=kennung)

    assert antwort.status_code == 200, (
        f"Legitime Kennung {kennung!r} wurde abgewiesen: {antwort.text}"
    )
    assert _dateien(_gpx_dir(kennung)) == {"tour.gpx"}, (
        f"Ordner von {kennung!r} enthaelt {_dateien(_gpx_dir(kennung))}"
    )


def test_upload_liefert_weiterhin_dieselben_fachlichen_daten(datenbaum):
    """AC-5 (Regressionswaechter).

    GIVEN: eine gueltige GPX-Datei, wie sie vor der Aenderung verarbeitet wurde
    WHEN: derselbe Upload durchgefuehrt wird
    THEN: die Antwort liefert dieselben fachlichen Daten (Name, Datum,
          Wegpunkte mit Position und Hoehe)
    """
    from api.main import app

    client = TestClient(app)
    antwort = _upload(
        client,
        _sample(_SAMPLE_A),
        "regression.gpx",
        user_id="alice",
        stage_date="2026-06-15",
        start_hour=7,
    )

    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["name"], "Etappenname fehlt"
    assert daten["date"] == "2026-06-15"
    assert isinstance(daten["waypoints"], list) and daten["waypoints"]
    wp = daten["waypoints"][0]
    assert isinstance(wp["lat"], (int, float))
    assert isinstance(wp["lon"], (int, float))
    assert isinstance(wp["elevation_m"], int)
