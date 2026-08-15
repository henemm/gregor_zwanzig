"""AC-1 (#1765/#1839 Scheibe A): Der Python-Core bleibt waehrend einer laufenden
Vorschau erreichbar.

Spec: docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md
Kontext/Messung: docs/context/fix-1765-1839-vorschau-laufzeit.md (M1)

Heute deklariert ``api/routers/preview.py`` seine Handler ``async def``, ohne ein
einziges ``await`` zu enthalten. Starlette fuehrt solche Handler DIREKT im
Event-Loop-Thread aus (statt im Threadpool) — waehrend der synchronen
Wetterabrufe ist der gesamte Prozess taub. Auf Staging gemessen: ``/api/health``
war 74,5 von 75,8 Sekunden nicht binnen 2 s erreichbar (25 Timeouts in Folge),
der Go-Health-Handler meldete ``python_core: unavailable`` — das hat am
2026-08-12 einen unnoetigen Neustart von ``gregor-python-staging`` ausgeloest.

**Aufbau: echter uvicorn-Server in einem eigenen Thread, gebaut aus den ECHTEN
Routern** (``api.routers.preview`` + ``api.routers.health``), abgefragt ueber
echte HTTP-Verbindungen gegen ``127.0.0.1``.

Warum NICHT ``TestClient``: Zwei getrennte ``TestClient``-Instanzen haetten je
einen eigenen Event-Loop — die langsame Anfrage liefe isoliert und der Test
waere STILL IMMER GRUEN, unabhaengig davon, ob der Handler ``async def`` oder
``def`` ist. Genau diese Falle benennt die Spec im Testplan. Ein echter Server
hat genau einen Loop, wie im Betrieb (uvicorn ohne ``--workers``).

Ersetzt wird nur der **Vorschau-Dienst** (die teure, fremde Arbeit) durch einen
kuenstlich langsamen Stub — der Handler selbst, seine Registrierung und der
Server-Lauf sind die echten. Geprueft wird die Wirkung (antwortet ``/health``
waehrend der Blockade?), nicht die Schreibweise im Quelltext.

Netzfrei: alle Verbindungen gehen an ``127.0.0.1`` (vom Egress-Waechter
ausdruecklich erlaubt), es wird kein Wetterdienst aufgerufen.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

#: So lange haelt der Vorschau-Stub den Handler fest. Muss deutlich ueber der
#: Health-Grenze liegen, damit die Health-Abfrage garantiert INNERHALB der
#: Blockade stattfindet (wird zusaetzlich per Event nachgeprueft).
BLOCK_SEKUNDEN = 5.0

#: Dieselbe Grenze, die der Go-Health-Handler setzt
#: (``internal/handler/proxy.go:19``) — darueber gilt Python als "unavailable".
HEALTH_GRENZE_SEKUNDEN = 2.0


def _freier_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _laufender_server(app: FastAPI):
    """Startet ``app`` in einem echten uvicorn-Server in einem eigenen Thread.

    Ein Prozess, EIN Event-Loop — genau wie im Betrieb (uvicorn ohne
    ``--workers``). Das ist der Punkt: ein zweiter Loop wuerde die Blockade
    unsichtbar machen.
    """
    port = _freier_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error", lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, name="uvicorn-core", daemon=True)
    thread.start()

    basis = f"http://127.0.0.1:{port}"
    frist = time.monotonic() + 15
    while time.monotonic() < frist:
        try:
            if httpx.get(f"{basis}/health", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        pytest.fail("uvicorn-Testserver ist nicht innerhalb von 15 s hochgekommen")

    try:
        yield basis
    finally:
        server.should_exit = True
        thread.join(timeout=15)


@pytest.fixture
def laufender_core():
    """Echter Server mit den echten Health- und Vorschau-Routern."""
    from api.routers import health, preview

    app = FastAPI()
    app.include_router(health.router)
    app.include_router(preview.router)
    with _laufender_server(app) as basis:
        yield basis


def _health_dauer(basis: str) -> float | None:
    """Sekunden bis zur ``/health``-Antwort, oder ``None`` bei Zeitueberschreitung."""
    beginn = time.monotonic()
    try:
        antwort = httpx.get(f"{basis}/health", timeout=HEALTH_GRENZE_SEKUNDEN)
    except httpx.TimeoutException:
        return None
    assert antwort.status_code == 200, (
        f"/health lieferte {antwort.status_code} statt 200: {antwort.text[:200]}"
    )
    return time.monotonic() - beginn


class _LangsameVorschau:
    """Steht fuer die echte, langsame Wetterarbeit (gemessen 25–121 s).

    Kein Mock-Theater: Der Stub spiegelt keine Erwartung zurueck, er ersetzt
    nur die Dauer. Die Zusicherung wird am Handler und am Server gemessen.
    """

    def __init__(self, gestartet: threading.Event) -> None:
        self._gestartet = gestartet

    def _blockieren(self):
        self._gestartet.set()
        time.sleep(BLOCK_SEKUNDEN)

    def render_email_preview(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self._blockieren()
        return "<html>fertig</html>"

    def render_all_channels(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self._blockieren()
        return {"subject": "s", "email_html": "<html/>", "telegram": "t",
                "sms": "x", "sms_char_count": 1}


@pytest.mark.parametrize(
    "pfad, methode, ersetztes_attribut",
    [
        pytest.param(
            "/api/preview/beliebig/email", "GET", "_build_service",
            id="trip-vorschau",
        ),
        pytest.param(
            "/api/preview/compare/preset-x", "POST", "ComparePreviewService",
            id="vergleichs-vorschau",
        ),
    ],
)
def test_health_antwortet_waehrend_laufender_vorschau(
    laufender_core, monkeypatch, pfad, methode, ersetztes_attribut,
):
    """AC-1: Waehrend eine Vorschau berechnet wird, antwortet ``/health``
    binnen 2 s — nicht erst nach Abschluss der Vorschau.

    ``/health`` ist der Python-Endpunkt, den der Go-Weiterleiter fuer
    ``/api/health`` mit 2 s Frist abfragt (``internal/handler/proxy.go:19``).
    """
    from api.routers import preview

    blockade_laeuft = threading.Event()
    vorschau_fertig = threading.Event()
    langsam = _LangsameVorschau(blockade_laeuft)
    monkeypatch.setattr(
        preview, ersetztes_attribut, lambda *a, **kw: langsam, raising=True,
    )

    ziel = f"{laufender_core}{pfad}"

    def vorschau_anstossen():
        try:
            httpx.request(
                methode, ziel, params={"user_id": "default"},
                timeout=BLOCK_SEKUNDEN + 20,
            )
        except httpx.HTTPError:
            pass
        finally:
            vorschau_fertig.set()

    anfrage = threading.Thread(target=vorschau_anstossen, name="vorschau", daemon=True)
    anfrage.start()
    assert blockade_laeuft.wait(timeout=15), (
        "Der Vorschau-Stub wurde nie erreicht — der Testaufbau misst nichts. "
        f"Ziel war {methode} {ziel}."
    )

    dauer = _health_dauer(laufender_core)
    noch_am_rechnen = not vorschau_fertig.is_set()
    anfrage.join(timeout=BLOCK_SEKUNDEN + 25)

    if dauer is None:
        pytest.fail(
            f"/health hat waehrend der laufenden Vorschau ({methode} {pfad}) "
            f"nicht innerhalb von {HEALTH_GRENZE_SEKUNDEN} s geantwortet. Der "
            "Vorschau-Handler ist 'async def' ohne 'await' und laeuft damit im "
            "Event-Loop-Thread statt im Threadpool — der gesamte Python-Core ist "
            "waehrend der Vorschau taub (Go meldet 'python_core: unavailable', "
            "Staging-Messung M1: 74,5 von 75,8 s stumm). Abhilfe: 'async def' → "
            "'def' (AC-1, Spec fix_1765_1839_sa_vorschau_entblockung.md)."
        )

    assert noch_am_rechnen, (
        "Die Vorschau war bereits fertig, als /health antwortete — der Test "
        "haette dann nichts ueber den blockierten Zustand ausgesagt. "
        f"BLOCK_SEKUNDEN={BLOCK_SEKUNDEN} zu klein?"
    )
    assert dauer < HEALTH_GRENZE_SEKUNDEN, (
        f"/health brauchte {dauer:.2f} s (Grenze {HEALTH_GRENZE_SEKUNDEN} s)"
    )


# ---------------------------------------------------------------------------
# Kontrollgruppe — ABSICHTLICH schon in der RED-Phase gruen.
#
# Kein fehlgeschlagener RED-Test und kein Ersatz fuer den Test oben: Sie belegt,
# dass der Messaufbau ueberhaupt zwischen beiden Zustaenden UNTERSCHEIDET. Ohne
# sie waere ein still immer roter Aufbau (falscher Port, Server tot, Server zu
# klein dimensioniert) von einem echten Befund nicht zu trennen — und nach der
# Umstellung waere nicht belegt, dass 'def' die Ursache war und nicht ein
# Zufall. Sie ist der im Spec-Testplan als verifiziert benannte Bauplan,
# hier mit BEIDEN Armen im selben Lauf.
# ---------------------------------------------------------------------------


def _blockierender_router(gestartet: threading.Event, koroutine: bool):
    from fastapi import APIRouter

    router = APIRouter()

    def arbeiten():
        gestartet.set()
        time.sleep(BLOCK_SEKUNDEN)
        return {"ok": True}

    if koroutine:
        async def blockieren():  # kein 'await' — heutiger Zustand der 13 Handler
            return arbeiten()
    else:
        def blockieren():
            return arbeiten()

    router.add_api_route("/blockieren", blockieren, methods=["GET"])
    return router


@pytest.mark.parametrize(
    "koroutine, erwartet_stumm",
    [
        pytest.param(True, True, id="async-def-ohne-await-blockiert"),
        pytest.param(False, False, id="def-blockiert-nicht"),
    ],
)
def test_kontrollgruppe_der_messaufbau_unterscheidet_beide_zustaende(
    koroutine, erwartet_stumm,
):
    """Identische blockierende Arbeit, einziger Unterschied: ``async def`` vs ``def``.

    Erwartung (im Prototyp gemessen, Kontextdokument): ``async def`` → Timeout
    nach ~2,02 s; ``def`` → HTTP 200 nach ~0,03 s.
    """
    from api.routers import health

    gestartet = threading.Event()
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(_blockierender_router(gestartet, koroutine))

    with _laufender_server(app) as basis:
        fertig = threading.Event()

        def anstossen():
            try:
                httpx.get(f"{basis}/blockieren", timeout=BLOCK_SEKUNDEN + 20)
            except httpx.HTTPError:
                pass
            finally:
                fertig.set()

        anfrage = threading.Thread(target=anstossen, daemon=True)
        anfrage.start()
        assert gestartet.wait(timeout=15), "Blockierender Handler nie erreicht"

        dauer = _health_dauer(basis)
        noch_am_rechnen = not fertig.is_set()
        anfrage.join(timeout=BLOCK_SEKUNDEN + 25)

    assert noch_am_rechnen, "Arbeit war schon fertig — Messfenster verfehlt"
    if erwartet_stumm:
        assert dauer is None, (
            f"/health antwortete nach {dauer:.2f} s, obwohl ein 'async def'-Handler "
            "ohne 'await' den Event-Loop blockieren MUSS. Der Messaufbau kann "
            "die Blockade nicht sehen — jedes gruene Ergebnis des Tests oben "
            "waere damit wertlos."
        )
    else:
        assert dauer is not None, (
            "/health war stumm, obwohl der blockierende Handler ein 'def' ist und "
            "damit im Threadpool laufen muss. Entweder ist der Messaufbau kaputt "
            "oder Starlette verteilt 'def'-Handler nicht mehr in den Threadpool."
        )
        assert dauer < HEALTH_GRENZE_SEKUNDEN
