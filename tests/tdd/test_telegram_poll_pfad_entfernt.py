"""Rückbau des Telegram-Poll-Pfads (#1369).

Der Poll-Pfad (`getUpdates` mit rohem Bot-Token) lief an den Egress-Guards aus
#1363 vorbei und hatte seit der Webhook-Umstellung (#637) keinen Aufrufer.
Er ist entfernt; der Webhook-Eingang bleibt.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_endpoint_inbound_telegram_existiert_nicht(monkeypatch):
    """AC-1: POST /api/scheduler/inbound-telegram -> 404 (Route entfernt)."""
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", "tdd-1369")
    client = TestClient(app, headers={"X-GZ-Core-Auth": "tdd-1369"})

    resp = client.post("/api/scheduler/inbound-telegram")

    assert resp.status_code == 404, f"Endpoint existiert noch: {resp.status_code}"
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/scheduler/inbound-telegram" not in paths

    # Route-Inventar: kein Telegram-Pfad unter einem anderen Namen. Erlaubt
    # sind nur der Webhook-Eingang (Go leitet /api/webhooks/telegram/{secret}
    # intern hierhin) und die Kanal-Vorschau.
    erlaubt = {"/api/internal/telegram-webhook", "/api/preview/{trip_id}/telegram"}
    telegram_routen = {p for p in paths if "telegram" in p.lower()}
    assert telegram_routen <= erlaubt, (
        f"Unerwartete Telegram-Route(n): {sorted(telegram_routen - erlaubt)}"
    )
    scheduler_telegram = {
        p for p in paths if p.startswith("/api/scheduler") and "telegram" in p.lower()
    }
    assert not scheduler_telegram, f"Scheduler-Telegram-Route: {scheduler_telegram}"


def test_reader_hat_keinen_poll_pfad():
    """AC-2: kein _get_updates / poll_and_process / _offset mehr."""
    from services.inbound_telegram_reader import InboundTelegramReader

    reader = InboundTelegramReader()
    for name in ("_get_updates", "poll_and_process", "_offset"):
        assert not hasattr(InboundTelegramReader, name), f"Klasse hat noch {name}"
        assert not hasattr(reader, name), f"Instanz hat noch {name}"

    # Kein direkter Telegram-API-Zugang mehr im Modul (frueher: httpx.get auf
    # TELEGRAM_API_BASE/getUpdates). Modul-Attribute statt Quelltext-Lesen
    # (Hygiene-Gate #765 verbietet Code-String-Asserts auf Produkt-Quelltext).
    import services.inbound_telegram_reader as modul

    assert not hasattr(modul, "TELEGRAM_API_BASE"), "TELEGRAM_API_BASE noch vorhanden"
    # Keine Netz-Primitive auf Modulebene (auch nicht unter Alias).
    import types

    netz_module = {"httpx", "requests", "urllib", "urllib.request", "socket",
                   "http", "http.client", "aiohttp", "urllib3"}
    for attr, wert in vars(modul).items():
        assert attr not in {"httpx", "requests", "socket", "aiohttp", "urllib3"}, attr
        if isinstance(wert, types.ModuleType):
            assert wert.__name__ not in netz_module, (
                f"Reader importiert Netz-Modul {wert.__name__} als {attr}"
            )
        herkunft = getattr(wert, "__module__", None) or ""
        if callable(wert) and herkunft.split(".")[0] in {
            "httpx", "requests", "socket", "aiohttp", "urllib3"
        } or herkunft in {"urllib.request", "http.client"}:
            raise AssertionError(f"Netz-Primitive {attr} aus {herkunft} importiert")

    # Kompilierter Code (Laufzeit-Objekte, kein Quelltext-Lesen): keine
    # Funktion des Moduls -- egal unter welchem Namen, auch mit lokalem
    # Import -- referenziert ein Netz-Primitiv oder die getUpdates-Methode.
    verboten_namen = {"httpx", "requests", "urllib", "urlopen", "socket",
                      "create_connection", "aiohttp", "urllib3", "HTTPConnection",
                      "HTTPSConnection"}

    def _codes(obj, gesehen):
        if id(obj) in gesehen:
            return
        gesehen.add(id(obj))
        if isinstance(obj, type):
            for wert in vars(obj).values():
                yield from _codes(wert, gesehen)
            return
        if isinstance(obj, (staticmethod, classmethod)):
            obj = obj.__func__
        if isinstance(obj, property):
            for f in (obj.fget, obj.fset, obj.fdel):
                if f is not None:
                    yield from _codes(f, gesehen)
            return
        code = getattr(obj, "__code__", None)
        if isinstance(obj, types.CodeType):
            code = obj
        if code is None:
            return
        yield code
        for konst in code.co_consts:
            if isinstance(konst, types.CodeType):
                yield from _codes(konst, gesehen)

    gesehen: set[int] = set()
    funde = []
    for wert in list(vars(modul).values()):
        if getattr(wert, "__module__", None) != modul.__name__:
            continue
        for code in _codes(wert, gesehen):
            namen = set(code.co_names) & verboten_namen
            texte = [k for k in code.co_consts if isinstance(k, str) and "getupdates" in k.lower()]
            if namen or texte:
                funde.append((code.co_qualname, sorted(namen), texte))
    assert not funde, f"Netz-/Poll-Zugriff im Reader: {funde}"


def test_webhook_eingang_bleibt():
    """AC-3 (Schutz): die Befehlsverarbeitung des Webhooks existiert weiter."""
    from services.inbound_telegram_reader import InboundTelegramReader

    assert callable(getattr(InboundTelegramReader, "_process_update", None))
    assert callable(getattr(InboundTelegramReader, "_process_start_command", None))


def test_doku_nennt_rueckbau():
    """AC-5: keine offene Rest-Lücke / kein Notfall-Fallback mehr in der Doku."""
    # doc-compliance-test
    egress = (REPO / "docs/specs/modules/egress_guard_telegram.md").read_text()
    webhook = (REPO / "docs/specs/modules/telegram_webhook_inbound.md").read_text()

    assert "Rest-Lücke `_get_updates`" not in egress
    assert "nicht löschen — Notfall-Fallback" not in webhook
    assert "Poll-Job reaktivieren" not in webhook
    assert "Poll-Job-Reaktivierung" not in webhook
    assert "#1369" in webhook
