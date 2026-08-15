"""AC-2 (#1765/#1839 Scheibe A): Kein Route-Handler ist Koroutine ohne echtes ``await``.

Spec: docs/specs/modules/fix_1765_1839_sa_vorschau_entblockung.md

Ein ``async def``-Handler ohne ``await`` laeuft bei Starlette DIREKT im
Event-Loop-Thread statt im Threadpool — waehrend seiner synchronen Arbeit ist
der gesamte Python-Core taub (belegt in AC-1, ``test_event_loop_bleibt_frei.py``).

Geprueft wird an der **fertig gebauten Anwendung** (``app.routes`` →
``inspect.iscoroutinefunction``), nicht am Quelltext einer bestimmten Datei:
Sonst wuerde nur die Schreibweise geprueft und ein per ``add_api_route``
registrierter oder in einem neuen Modul angelegter Handler bliebe unbemerkt.

Die Ausnahme ist bewusst als **Eigenschaft** formuliert, nicht als Dateiliste:
Ein Handler darf genau dann Koroutine sein, wenn sein eigener Rumpf tatsaechlich
``await``/``async for``/``async with`` verwendet. Eine Ausnahmeliste
("alles in gpx.py ist erlaubt") wuerde erodieren, sobald dort ein zweiter,
await-loser Handler entsteht.

Bekannte Grenze — unerreichbares ``await`` (Adversary-Fund F001, 2026-08-15)
---------------------------------------------------------------------------
``_nutzt_echtes_await()`` zaehlt jeden ``await``-Knoten per AST, **ohne zu
pruefen, ob er im Kontrollfluss ueberhaupt erreichbar ist**. Ein Handler der
Bauform::

    async def handler():
        if False:
            await asyncio.sleep(0)   # nie erreicht, macht den Test gruen
        time.sleep(3)                # blockiert trotzdem den Event-Loop

kommt hier **gruen** durch, obwohl er genau den Fehler enthaelt, den dieser
Test verhindern soll. Der Adversary hat das mit einer echten Sonde belegt.

Das wird hingenommen, nicht behoben: Keiner der 13 heute umgestellten Handler
nutzt dieses Muster, und eine Erreichbarkeitsanalyse (konstante Bedingungen
auswerten, toten Code erkennen) waere fuer diesen Wachzweck unverhaeltnismaessig
aufwaendig und selbst wieder fehleranfaellig. Der Test soll einfach bleiben —
die Grenze soll nur nicht unsichtbar sein.

Zweite Verteidigungslinie ist ``tests/unit/test_event_loop_bleibt_frei.py``:
Der misst an einem echten uvicorn-Server die **tatsaechliche** Blockade
(``/health``-Antwortzeit waehrend einer laufenden Vorschau) und wuerde einen so
gebauten Handler auffliegen lassen. Allerdings deckt er nur die
**Vorschau-Handler** ab — fuer die Handler in ``validator``, ``internal`` und
``notify`` gibt es diese zweite Linie nicht.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from fastapi.routing import APIRoute


def _nutzt_echtes_await(func) -> bool:
    """Enthaelt der EIGENE Rumpf der Funktion ``await``/``async for``/``async with``?

    Verschachtelte Funktionsdefinitionen werden bewusst uebersprungen — ein
    ``await`` in einer inneren Koroutine rechtfertigt nicht, dass die aeussere
    Route-Funktion selbst ``async def`` ist.
    """
    try:
        quelle = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError):
        return False
    baum = ast.parse(quelle)
    # ast.parse liefert Module → FunctionDef/AsyncFunctionDef als einziges Kind.
    rumpf = baum.body[0].body if baum.body else []

    gefunden = False

    class _Sucher(ast.NodeVisitor):
        def visit_Await(self, node):  # noqa: N802
            nonlocal gefunden
            gefunden = True

        def visit_AsyncFor(self, node):  # noqa: N802
            nonlocal gefunden
            gefunden = True
            self.generic_visit(node)

        def visit_AsyncWith(self, node):  # noqa: N802
            nonlocal gefunden
            gefunden = True
            self.generic_visit(node)

        def visit_FunctionDef(self, node):  # noqa: N802
            return  # verschachtelte Definition: nicht der eigene Rumpf

        def visit_AsyncFunctionDef(self, node):  # noqa: N802
            return

    sucher = _Sucher()
    for knoten in rumpf:
        sucher.visit(knoten)
    return gefunden


def _fundstelle(func) -> str:
    modul = getattr(func, "__module__", "?")
    try:
        zeile = func.__code__.co_firstlineno
    except AttributeError:
        zeile = "?"
    return f"{modul}:{zeile} {getattr(func, '__qualname__', func)}"


def test_kein_route_handler_ist_koroutine_ohne_await():
    """AC-2: An der gebauten App ist kein Handler Koroutine, ausser er nutzt ``await``.

    Heute (vor Ae1) sind das 13 Verstoesse in 4 Routern; ``gpx.parse_gpx``
    (``await file.read()``) ist der einzige berechtigte ``async def``.
    """
    from api.main import app

    verstoesse = []
    berechtigt = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        endpoint = route.endpoint
        if not inspect.iscoroutinefunction(endpoint):
            continue
        if _nutzt_echtes_await(endpoint):
            berechtigt.append(_fundstelle(endpoint))
            continue
        verstoesse.append(f"  {_fundstelle(endpoint)}  ({', '.join(sorted(route.methods))} {route.path})")

    assert not verstoesse, (
        f"{len(verstoesse)} Route-Handler sind 'async def' OHNE jedes 'await' und "
        "blockieren damit den Event-Loop waehrend ihrer synchronen Arbeit "
        "(AC-2, Spec fix_1765_1839_sa_vorschau_entblockung.md).\n"
        "Abhilfe: 'async def' → 'def', dann fuehrt Starlette sie im Threadpool aus.\n"
        + "\n".join(sorted(verstoesse))
        + f"\n\nBerechtigt (nutzen echtes await): {berechtigt or 'keine'}"
    )


def test_gpx_upload_bleibt_die_einzige_berechtigte_koroutine():
    """Gegenprobe zur Ausnahme: ``parse_gpx`` nutzt echtes ``await`` und darf bleiben.

    Ohne diesen Test koennte AC-2 auch dadurch 'erfuellt' werden, dass jemand
    ``parse_gpx`` mit-umstellt und das ``await file.read()`` dabei zerbricht.
    """
    from api.routers.gpx import parse_gpx

    assert inspect.iscoroutinefunction(parse_gpx), (
        "parse_gpx muss 'async def' bleiben — es nutzt 'await file.read()'."
    )
    assert _nutzt_echtes_await(parse_gpx), (
        "parse_gpx enthaelt kein 'await' mehr — dann darf es auch keine "
        "Koroutine mehr sein (die Ausnahme in AC-2 haengt an der Eigenschaft, "
        "nicht am Dateinamen)."
    )
