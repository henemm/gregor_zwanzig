"""Die Anbieter-Registry wird auch bei gleichzeitigem Erstzugriff VOLLSTAENDIG
gefuellt, bevor ein Thread in ihr nachschlaegt (#1765 B1, Staging-Regression).

Auf Staging gemessen (Stand 4451e39d, Preset cp-21e198c1b74020dd, 3 Orte): Der
ERSTE Vergleichs-Vorschau-Aufruf nach einem Dienst-Neustart lieferte fuer zwei
der drei Orte ``Fehler: [Unknown provider: openmeteo. Available: geosphere]
Provider not found``; der zweite Aufruf (Dienst warm) war vollstaendig.
Ursache ist ein Check-then-Act-Rennen in ``src/providers/base.py``: ``if not
_PROVIDER_FACTORIES: _load_providers()`` meldet "schon geladen", sobald der
ERSTE Anbieter (``geosphere``) eingetragen ist -- die uebrigen (``openmeteo``
& Co.) folgen erst danach. Seriell war das nie ausloesbar; erst die
Parallelisierung der Vergleichs-Vorschau (#1765 B1) macht es real.

Geprueft wird die WIRKUNG -- ob ein gleichzeitig zugreifender Thread den
Anbieter tatsaechlich bekommt --, nicht die Anwesenheit eines ``Lock()`` im
Quelltext. Muster wie tests/unit/test_timezone_singleton_threadsicher.py.
"""

from __future__ import annotations

import threading

import pytest


@pytest.fixture
def kalte_registry(monkeypatch):
    """Versetzt die Anbieter-Registry in den Zustand direkt nach einem
    Dienst-Neustart (leer, nie geladen) und stellt sie danach wieder her.

    Das Fertig-Flag MUSS hier mit zurueckgesetzt werden -- eine geleerte
    Registry mit gesetztem Flag waere fuer alle Folgetests dauerhaft "geladen"
    und damit leer.
    """
    from providers import base as basis

    # tests/conftest.py::_use_fixture_provider setzt GZ_TEST_FIXTURE_DIR fuer
    # jeden nicht-live-Test. ``get_provider("openmeteo")`` gibt damit VOR jeder
    # Registry-Pruefung den FixtureProvider zurueck -- der Pruefling waere nie
    # erreicht und dieser Test immer gruen, auch ohne Fix.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)

    vorher_registry = dict(basis._PROVIDER_FACTORIES)
    vorher_flag = basis._providers_loaded
    basis._PROVIDER_FACTORIES.clear()
    basis._providers_loaded = False
    try:
        yield basis
    finally:
        basis._PROVIDER_FACTORIES.clear()
        basis._PROVIDER_FACTORIES.update(vorher_registry)
        basis._providers_loaded = vorher_flag


def _ladefenster_aufreissen(basis, monkeypatch):
    """Haelt das Zeitfenster zwischen der ERSTEN und der zweiten Registrierung
    offen -- ohne diese Verbreiterung ist das Rennen zu schnell und der Test
    waere auch ohne Fix zufaellig gruen.

    Returns:
        ``(erste_eingetragen, freigabe)`` -- ``erste_eingetragen`` ist gesetzt,
        sobald genau EIN Anbieter in der Registry steht (der Moment, in dem
        ``if not _PROVIDER_FACTORIES`` faelschlich "gefuellt" meldet).
        ``freigabe`` laesst den ladenden Thread weiterlaufen; bleibt sie aus
        (gesicherter Fall: die anderen Threads haengen an der Sperre), laeuft
        er nach 1 s in die Zeitschranke.
    """
    echtes_register = basis.register_provider
    erste_eingetragen = threading.Event()
    freigabe = threading.Event()

    def langsam_registrieren(name, factory):
        echtes_register(name, factory)
        if not erste_eingetragen.is_set():
            erste_eingetragen.set()
            freigabe.wait(timeout=1.0)

    monkeypatch.setattr(basis, "register_provider", langsam_registrieren)
    return erste_eingetragen, freigabe


def _threads_starten_und_abwarten(ziele):
    """Startet die Threads, wartet ab -- und laesst eine Ausnahme in einem
    Thread den TEST scheitern. Ohne das Einsammeln wuerde pytest sie nur als
    Warnung zeigen und der Test bliebe gruen, obwohl ein Thread abgestuerzt
    ist.
    """
    abstuerze: list[tuple[str, BaseException]] = []
    sperre = threading.Lock()

    def umhuellt(name, ziel):
        def lauf():
            try:
                ziel()
            except BaseException as e:  # noqa: BLE001
                with sperre:
                    abstuerze.append((name, e))

        return lauf

    threads = [threading.Thread(target=umhuellt(n, z), name=n) for n, z in ziele]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive(), (
            f"Thread {t.name} haengt -- Verklemmung beim Laden der Registry?"
        )
    assert not abstuerze, (
        "Ausnahme in einem gleichzeitig laufenden Thread: "
        f"{[(n, repr(e)) for n, e in abstuerze]}"
    )


def test_gleichzeitiger_erstzugriff_findet_jeden_anbieter(
    kalte_registry, monkeypatch
):
    """Drei Threads (= drei Orte einer Vergleichs-Vorschau) greifen zeitgleich
    auf die kalte Registry zu; KEINER darf ``ProviderNotFoundError`` sehen.

    Thread "ort1" startet das Laden, "ort2"/"ort3" setzen exakt in dem Moment
    auf, in dem erst ein einziger Anbieter eingetragen ist.
    """
    basis = kalte_registry
    erste_eingetragen, freigabe = _ladefenster_aufreissen(basis, monkeypatch)

    ergebnisse: dict[str, object] = {}
    fehler: dict[str, BaseException] = {}
    sperre = threading.Lock()

    def hole(schluessel: str, wartet: bool):
        def lauf():
            try:
                if wartet:
                    assert erste_eingetragen.wait(timeout=10), (
                        "Das Laden der Registry hat nie begonnen"
                    )
                anbieter = basis.get_provider("openmeteo")
                with sperre:
                    ergebnisse[schluessel] = anbieter
            except BaseException as e:  # noqa: BLE001
                with sperre:
                    fehler[schluessel] = e
            finally:
                if wartet:
                    freigabe.set()

        return lauf

    _threads_starten_und_abwarten(
        [
            ("ort1", hole("ort1", wartet=False)),
            ("ort2", hole("ort2", wartet=True)),
            ("ort3", hole("ort3", wartet=True)),
        ]
    )

    assert not fehler, (
        "Gleichzeitig zugreifende Orte bekamen keinen Anbieter: "
        f"{ {k: repr(v) for k, v in fehler.items()} }. Genau das war die auf "
        "Staging gemessene Regression ('Unknown provider: openmeteo. "
        "Available: geosphere') beim ersten Vorschau-Aufruf nach einem "
        "Dienst-Neustart. Abhilfe: doppelt gepruefte Sperre mit separatem "
        "Fertig-Flag in providers/base.py -- 'Registry nicht leer' ist NICHT "
        "'Registry fertig geladen'."
    )
    assert set(ergebnisse) == {"ort1", "ort2", "ort3"}
    for schluessel, anbieter in ergebnisse.items():
        assert anbieter.name == "openmeteo", (
            f"{schluessel} bekam '{anbieter.name}' statt 'openmeteo'"
        )


def test_gleichzeitiger_erstzugriff_liefert_vollstaendige_anbieterliste(
    kalte_registry, monkeypatch
):
    """``available_providers()`` darf waehrend des Erstladens keine
    UNVOLLSTAENDIGE Liste zurueckgeben (dieselbe Luecke, zweite Fundstelle).

    Ohne Sperre sieht der zweite Thread nur den bereits eingetragenen ersten
    Anbieter -- die Liste waere ``["geosphere"]``.
    """
    basis = kalte_registry
    erste_eingetragen, freigabe = _ladefenster_aufreissen(basis, monkeypatch)

    listen: dict[str, list[str]] = {}

    def lader():
        basis.available_providers()

    def mitleser():
        try:
            assert erste_eingetragen.wait(timeout=10)
            listen["mitleser"] = basis.available_providers()
        finally:
            freigabe.set()

    _threads_starten_und_abwarten([("lader", lader), ("mitleser", mitleser)])

    assert "openmeteo" in listen.get("mitleser", []), (
        "Ein gleichzeitiger Aufruf sah nur eine TEILWEISE gefuellte Registry: "
        f"{listen.get('mitleser')}. Genau diese Teilliste erschien auf Staging "
        "im Fehlertext ('Available: geosphere')."
    )


def test_registry_wird_bei_gleichzeitigem_erstzugriff_genau_einmal_geladen(
    kalte_registry, monkeypatch
):
    """Gegenprobe zur naheliegenden Billig-Loesung: Ein Fix, der bei jedem
    Fehlschlag einfach nachlaedt (``if name not in _PROVIDER_FACTORIES:
    _load_providers()``), bekaeme die Tests oben ebenfalls gruen -- und wuerde
    bei jedem Kaltstart die Anbieter-Module mehrfach gleichzeitig importieren.
    Hier wird die Zahl der Ladevorgaenge selbst geprueft: genau EINER.
    """
    basis = kalte_registry
    erste_eingetragen, freigabe = _ladefenster_aufreissen(basis, monkeypatch)

    echtes_laden = basis._load_providers
    ladevorgaenge: list[int] = []

    def zaehlendes_laden():
        ladevorgaenge.append(1)
        echtes_laden()

    monkeypatch.setattr(basis, "_load_providers", zaehlendes_laden)

    def erster():
        basis.get_provider("openmeteo")

    def spaeter():
        try:
            assert erste_eingetragen.wait(timeout=10)
            basis.get_provider("openmeteo")
        finally:
            freigabe.set()

    _threads_starten_und_abwarten(
        [("erster", erster), ("zweiter", spaeter), ("dritter", spaeter)]
    )

    assert len(ladevorgaenge) == 1, (
        f"Die Registry wurde {len(ladevorgaenge)}x geladen statt genau 1x -- "
        "gleichzeitige Erstzugriffe importieren die Anbieter-Module mehrfach."
    )
