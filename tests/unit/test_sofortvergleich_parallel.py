"""AC-7 (#1765 Scheibe B1b): Der SOFORTVERGLEICH ``GET /api/compare``
verarbeitet seine Orte GLEICHZEITIG und antwortet in der angeforderten
Ortsreihenfolge.

Spec: docs/specs/modules/fix_1765_b1b_versand_sofortvergleich_parallel.md

RED-Grund: ``run_comparison()`` ruft ``ComparisonEngine.run()`` mit der VOLLEN
Ortsliste auf (api/routers/compare.py:71) -- ein Aufruf, nacheinander
abgearbeitet. Der Treffpunkt-Test laeuft damit heute in seine Zeitschranke.

Pruefort = Wirkort: der ECHTE Router laeuft unter ``TestClient``, geprueft wird
der JSON-Antwortkoerper. Ersetzt ist nur die teure Wetter-Naht (echte
Subklasse, kein Mock) und die Ortsquelle (Haus-Muster
tests/tdd/test_hail_flag_metrics_catalog_and_compare_api.py:100).
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from app.user import SavedLocation

WORKTREE = Path(__file__).resolve().parents[2]
ZIELDATUM = date(2026, 7, 8)
ZEITSCHRANKE = 5.0  # s -- endlich, damit ein serieller Lauf in die Sperre
#                     laeuft statt den Testlauf haengen zu lassen.
ORTE = [
    SavedLocation(id="sv-a", name="Alphastadt", lat=47.2, lon=11.0, elevation_m=1000),
    SavedLocation(id="sv-b", name="Bravoberg", lat=46.5, lon=11.3, elevation_m=1100),
    SavedLocation(id="sv-c", name="Charliedorf", lat=46.0, lon=12.0, elevation_m=1200),
]


@pytest.fixture
def client():
    import api.routers.compare as compare_mod
    from fastapi.testclient import TestClient

    from api.main import app

    # Pfadregel #1409: aus dem Worktree darf nicht die Hauptrepo-Kopie geprueft
    # werden -- sonst meldet dieser Test falsches Gruen.
    assert Path(compare_mod.__file__).resolve().is_relative_to(WORKTREE), (
        compare_mod.__file__
    )
    return TestClient(app)


@pytest.fixture
def thread_fehler():
    """pytest meldet eine Ausnahme in einem Worker-Thread nur als WARNUNG -- ein
    Test kann gruen sein, waehrend ein Thread abstuerzt. Hier wird sie zum
    Testfehler."""
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = gesammelt.append
    yield gesammelt
    threading.excepthook = alt
    assert not gesammelt, (
        "Ausnahme(n) in Worker-Threads -- pytest haette sie nur als Warnung "
        f"gemeldet: {[(e.exc_type, e.exc_value) for e in gesammelt]}"
    )


def _naht(monkeypatch, haken):
    """Ortsquelle und Wetter-Naht ersetzen; ``haken(ort)`` erzwingt Treffpunkt
    bzw. Verzoegerung. Der Wert kommt ueber ``loc.id``, nicht ueber den
    Aufrufindex."""
    import app.loader as loader_mod
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    monkeypatch.setattr(loader_mod, "load_all_locations", lambda *a, **kw: list(ORTE))

    class _StubEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            orte = list(kwargs["locations"] if "locations" in kwargs else args[0])
            teile = []
            for ort in orte:
                haken(ort)
                teile.append(LocationResult(location=ort, score=50, temp_max=20.0))
            return ComparisonResult(
                locations=teile, time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", ZIELDATUM),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _StubEngine)


def _abfrage(client):
    """Die Orte werden in DERSELBEN Reihenfolge angefordert, in der die
    Ortsquelle sie fuehrt -- der Endpunkt filtert ueber die Quelle
    (api/routers/compare.py:44), 'angefordert' und 'aufgeloest' fallen damit
    zusammen und die Zusicherung ist eindeutig."""
    ids = ",".join(o.id for o in ORTE)
    return client.get(
        f"/api/compare?location_ids={ids}&target_date={ZIELDATUM.isoformat()}"
        "&time_window_start=9&time_window_end=16"
    )


def test_ac7_sofortvergleich_verarbeitet_die_orte_gleichzeitig(
    client, monkeypatch, thread_fehler
):
    """AC-7 (Gleichzeitigkeit): Drei Orte melden sich an einer Treffpunkt-Sperre
    an. Nacheinander verarbeitet erreicht der zweite Ort den Treffpunkt nie --
    die Sperre laeuft in ihre Zeitschranke und KEIN Ort kommt durch.
    Uhrunabhaengig.

    Pflichtmutation: ``MAX_PARALLEL_LOCATIONS = 1`` muss diesen Test rot
    machen."""
    treffpunkt = threading.Barrier(len(ORTE))
    durch: list[str] = []
    sperre = threading.Lock()

    def am_treffpunkt(ort):
        try:
            treffpunkt.wait(timeout=ZEITSCHRANKE)
        except threading.BrokenBarrierError:
            return
        with sperre:
            durch.append(ort.id)

    _naht(monkeypatch, am_treffpunkt)
    antwort = _abfrage(client)

    assert antwort.status_code == 200, antwort.text
    assert sorted(durch) == [o.id for o in ORTE], (
        f"Nur {sorted(durch)} von {[o.id for o in ORTE]} erreichten den "
        "Treffpunkt -- GET /api/compare berechnet die Orte nacheinander statt "
        "gleichzeitig (AC-7). Erwartet: run_comparison ruft "
        "run_comparison_parallel(..., call_source='vergleich') statt "
        "ComparisonEngine.run (api/routers/compare.py:71)."
    )
    assert [e["id"] for e in antwort.json()["locations"]] == [o.id for o in ORTE]


def test_ac7_antwort_folgt_der_angeforderten_reihenfolge(
    client, monkeypatch, thread_fehler
):
    """AC-7 (Reihenfolge): Der zuerst angeforderte Ort braucht am laengsten,
    der zuletzt angeforderte am kuerzesten -- die Fertigstellung ist damit
    gegen die Einreichung gedreht. Die Antwort muss trotzdem der angeforderten
    Reihenfolge folgen. Seriell entsteht die Drehung nicht; sie wird deshalb
    erst gefordert, wenn sie moeglich ist (Treffpunkt erreicht)."""
    treffpunkt = threading.Barrier(len(ORTE))
    verzoegerung = {"sv-a": 0.30, "sv-b": 0.15, "sv-c": 0.0}
    fertig: list[str] = []
    erreicht: list[str] = []
    sperre = threading.Lock()

    def gedreht(ort):
        try:
            treffpunkt.wait(timeout=ZEITSCHRANKE)
            with sperre:
                erreicht.append(ort.id)
        except threading.BrokenBarrierError:
            pass
        time.sleep(verzoegerung[ort.id])
        with sperre:
            fertig.append(ort.id)

    _naht(monkeypatch, gedreht)
    antwort = _abfrage(client)

    assert antwort.status_code == 200, antwort.text
    if len(erreicht) == len(ORTE):  # gleichzeitig -- erst dann ist die Drehung da
        assert fertig == ["sv-c", "sv-b", "sv-a"], (
            f"Vorbedingung verletzt: Fertigstellungsreihenfolge {fertig} ist "
            "nicht gegen die Einreichungsreihenfolge gedreht -- ohne Drehung "
            "prueft die eigentliche Zusicherung nichts."
        )
    geliefert = [e["id"] for e in antwort.json()["locations"]]
    assert geliefert == [o.id for o in ORTE], (
        "AC-7: Die JSON-Antwort muss die Orte in der angeforderten Reihenfolge "
        f"listen, geliefert wurde {geliefert} bei Fertigstellung {fertig}."
    )


def test_ac8_jeder_ortsabruf_traegt_die_quelle_vergleich(
    client, monkeypatch, thread_fehler
):
    """AC-8 (zweite Wirkstelle): AC-8 gilt fuer BEIDE Aufrufstellen -- der
    Versandpfad ist in tests/unit/test_compare_versand_parallel.py bewacht, hier
    der Sofortvergleich ueber den ECHTEN Router.

    Die Quelle wird dort ausgelesen, wo das Journal sie sieht: im Thread, der den
    Abruf ausfuehrt. Dort taucht keiner der 11 Stack-Marker mehr auf (auch nicht
    ``compare``, denn die Router-Frames bleiben im aufrufenden Thread) -- nur ein
    ausdrueckliches ``call_source='vergleich'`` ueberlebt den Threadwechsel.
    Pflichtmutation: ``call_source`` in api/routers/compare.py:83 weglassen muss
    DIESEN Test rot machen; die Mutation am Versandpfad darf ihn NICHT roetten."""
    from providers.call_log import resolve_call_source

    gesehen: dict[str, str] = {}
    sperre = threading.Lock()

    def merkt_die_quelle(ort):
        with sperre:
            gesehen[ort.id] = resolve_call_source()

    _naht(monkeypatch, merkt_die_quelle)
    antwort = _abfrage(client)

    assert antwort.status_code == 200, antwort.text
    assert gesehen == {o.id: "vergleich" for o in ORTE}, (
        f"AC-8: Im Verarbeitungs-Thread jedes Ortes wurde {gesehen} als Quelle "
        "aufgeloest -- erwartet ueberall 'vergleich'. GET /api/compare muss "
        "call_source='vergleich' ausdruecklich setzen (ein ThreadPoolExecutor "
        "reicht den ContextVar-Kontext nicht an seine Arbeiter weiter)."
    )
