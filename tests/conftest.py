# ensures the 'src' directory is on sys.path for imports like 'from app import ...'
import dataclasses
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

# Issue #1755: Option --loopback-own-ports fuer den sicheren Offline-Volllauf
# (Loopback nur zu selbst gebundenen Ports), siehe tests/_loopback_port_guard.py.
_tests_dir = str(Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
pytest_plugins = ["_loopback_port_guard"]

# ---------------------------------------------------------------------------
# Issue #1196 Klasse B: geteilte .env-Fixture statt Modul-weitem load_dotenv()
# ---------------------------------------------------------------------------

_DOTENV_PATH = root / ".env"


@pytest.fixture(scope="module")
def dotenv_env():
    """Laedt Werte aus der Worktree-``.env`` NUR fuer Tests, die dies per
    Fixture anfordern -- ersetzt das fruehere modulweite ``load_dotenv()`` auf
    Modulebene mehrerer Live-/E-Mail-Testdateien.

    Root Cause (#1196 Klasse B): ein ``load_dotenv()``-Aufruf auf Modulebene
    laeuft beim COLLECT, nicht beim Testlauf -- unabhaengig davon, ob der
    jeweilige Test spaeter per Marker deselektiert wird. Jeder Volllauf, der
    eine dieser Dateien nur EINSAMMELT, schrieb damit die komplette lokale
    ``.env`` dauerhaft (kein Teardown) nach ``os.environ`` und kontaminierte
    andere, spaeter im selben Prozess laufende Tests (Beleg: der
    Vorbelegungs-Waechter in ``tests/tdd/_telegram_live_fixture.py``,
    ``test_issue_1014_live_optin.py::test_with_optin_gate_returns_true_and_sources_env``).

    MODULE-Scope + eigenes ``pytest.MonkeyPatch()`` statt der
    function-scoped ``monkeypatch``-Fixture, damit auch module-scoped
    Fixtures (z.B. ``session_cookie`` in den Account-Page-Live-Tests) diese
    Fixture anfordern koennen (eine function-scoped Fixture waere dort ein
    Scope-Mismatch). Bewusst NICHT session-scoped: dann blieben die Werte
    bis zum Ende des Laufs in ``os.environ`` und traefen jedes spaeter
    laufende Modul -- exakt die Verschmutzung, die hier abgestellt wird.
    Mit Modul-Scope werden sie am Ende des anfordernden Moduls zurueckgerollt.
    Nur FEHLENDE Keys werden gesetzt -- Vorrang fuer bereits gesetzte Werte
    (Shell-Export, CI), analog ``load_dotenv(override=False)``. Fehlt die
    ``.env`` (CI), ist die Fixture ein No-op.
    """
    if not _DOTENV_PATH.exists():
        yield
        return

    from dotenv import dotenv_values

    mp = pytest.MonkeyPatch()
    try:
        for key, value in dotenv_values(_DOTENV_PATH).items():
            if value is not None and key not in os.environ:
                mp.setenv(key, value)
        yield
    finally:
        mp.undo()


# Issue #346: force all tests onto the offline FixtureProvider so pytest runs
# never hit the live Open-Meteo API (and exhaust the server-IP rate limit).
_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "openmeteo")


@pytest.fixture(autouse=True)
def _use_fixture_provider(request):
    """Activate the offline fixture provider for every test.

    Tests marked ``@pytest.mark.live`` get no fixture override — they hit the
    real API (contract-test obligation, mock ban). Function scope ensures
    clean ENV isolation between tests.
    """
    if request.node.get_closest_marker("live"):
        old = os.environ.pop("GZ_TEST_FIXTURE_DIR", None)
        yield
        if old is not None:
            os.environ["GZ_TEST_FIXTURE_DIR"] = old
    else:
        os.environ["GZ_TEST_FIXTURE_DIR"] = os.path.abspath(_FIXTURE_DIR)
        yield
        os.environ.pop("GZ_TEST_FIXTURE_DIR", None)


# ---------------------------------------------------------------------------
# Issue #2142: Core-Auth-Header zentral fuer jeden TestClient
# ---------------------------------------------------------------------------

CORE_AUTH_HEADER = "X-GZ-Core-Auth"
CORE_SECRET_ENV = "GZ_CORE_SHARED_SECRET"
# Nur fuer den Testlauf. Kein Produktivwert, steht bewusst im Repo.
_CORE_AUTH_TEST_SECRET = "pytest-core-shared-secret-0123456789abcdef"

# Beim IMPORT dieser conftest, nicht in einer Fixture: Testmodule werden vor
# dem ersten Fixture-Lauf eingesammelt, und ein dort auf Modulebene gebauter
# TestClient braucht das Geheimnis bereits. ``setdefault`` laesst einen von
# aussen gesetzten Wert (Server-.env, CI) unangetastet.
os.environ.setdefault(CORE_SECRET_ENV, _CORE_AUTH_TEST_SECRET)


def _patch_testclient_with_core_auth() -> None:
    """Versorgt JEDE ``TestClient``-Instanz mit dem gueltigen Auth-Header.

    Ohne das braechen die ~68 Bestands-Testdateien geschlossen mit 401, sobald
    ``api/main.py`` die Pruefung durchsetzt. Der Waechter selbst wird dabei
    NICHT abgeschaltet — es gibt keinen ``_in_pytest()``-Bypass: ein Test, der
    den Header aus seinem Client wieder entfernt, bekommt weiterhin 401
    (AC-11, ``tests/tdd/test_core_auth_enforcement.py``).

    Der Wert wird bei jeder Instanziierung frisch aus der Umgebung gelesen,
    damit ein Test, der das Geheimnis per ``monkeypatch.setenv`` aendert,
    danach auch einen dazu passenden Client bekommt.

    Gepatcht wird ``starlette.testclient.TestClient`` — ``fastapi.testclient``
    re-exportiert genau diese Klasse.
    """
    from starlette.testclient import TestClient

    if getattr(TestClient, "_gz_core_auth_patched", False):
        return

    original_init = TestClient.__init__

    def __init__(self, *args, **kwargs):  # noqa: ANN001, ANN202
        original_init(self, *args, **kwargs)
        secret = os.environ.get(CORE_SECRET_ENV, "")
        if secret:
            self.headers[CORE_AUTH_HEADER] = secret

    TestClient.__init__ = __init__
    TestClient._gz_core_auth_patched = True


_patch_testclient_with_core_auth()


@pytest.fixture(autouse=True)
def _dwd_raster_cache_leeren():
    """#2465: `providers.dwd._RASTER_CACHE` ist ein PROZESSWEITER Cache, keyed
    nach URL (Lauf/Parameter/Zeitschritt, also zeitabhaengig). Ohne Reset lesen
    zwei Tests mit unterschiedlichen Fake-Rastern zur selben URL je nach
    Reihenfolge und Stunde die Werte des anderen. Nur wenn das Modul ohnehin
    schon geladen ist — kein Import fuer Tests, die DWD nie beruehren."""
    def _leeren():
        modul = sys.modules.get("providers.dwd")
        cache = getattr(modul, "_RASTER_CACHE", None)
        if cache is not None:
            cache.clear()
    _leeren()
    yield
    _leeren()


@pytest.fixture(autouse=True)
def _telegram_herkunftsbeleg_leeren():
    """#1412 S4a: der Herkunftsbeleg ``_current_inbound_sender`` (Absender des
    laufenden Webhook-Updates) ist eine ContextVar im Haupt-Thread -- ein Test,
    der ihn per ``tests.helpers.telegram_empfaenger.antwort_im_update`` setzt,
    darf ihn nicht an den naechsten Test vererben."""
    def _leeren():
        modul = sys.modules.get("output.channels.recipient")
        if modul is not None:
            modul._current_inbound_sender.set(None)
    _leeren()
    yield
    _leeren()


@pytest.fixture(autouse=True)
def _core_auth_secret_configured():
    """Stellt fuer jeden Test sicher, dass ein Geheimnis konfiguriert ist.

    Fehlt es (weil ein vorheriger Test es ohne monkeypatch aus der Umgebung
    geraeumt hat), antwortete der Core mit 503 statt mit dem erwarteten
    Verhalten. Tests, die den unkonfigurierten Zustand BEWUSST herstellen
    wollen, ueberschreiben das per eigenem ``monkeypatch.delenv`` im Test —
    diese Fixture laeuft als autouse zuerst und wird danach ueberstimmt.

    BEWUSST OHNE ``monkeypatch``: als autouse-Fixture wuerde sie den
    function-scoped ``monkeypatch`` VOR ``_isolate_data_root`` aufbauen. Damit
    liefe ``monkeypatch.undo()`` erst NACH dessen Restore — ein Test, der
    ``loader._DATA_ROOT`` per ``monkeypatch.setattr`` umbiegt (z. B.
    ``tests/tdd/test_compare_dispatch_failed_tally.py``), setzte den Wert am
    Ende auf SEINEN tmp-Pfad zurueck statt auf den echten Baum. Alle folgenden
    ``@pytest.mark.real_data_root``-Tests lasen dann eine leere Wegwerf-Wurzel
    und scheiterten mit 404 ("Trip ... nicht gefunden"). Reines
    ``os.environ``-Setzen hat keine Fixture-Abhaengigkeit und verschiebt die
    Reihenfolge nicht.
    """
    if not os.environ.get(CORE_SECRET_ENV):
        os.environ[CORE_SECRET_ENV] = _CORE_AUTH_TEST_SECRET
    yield


_REPO_DATA_USERS = root / "data" / "users"

# Issue #1624: die frueher unter ``<repo>/data/users`` COMMITTETEN
# Referenz-Fixtures (gr221-mallorca, validator-issue110, GPX-Dateien) sind
# nach ``tests/fixtures/data_root/users/...`` umgezogen -- ``data/`` im
# Arbeitsbaum muss vollstaendig UNTRACKED bleiben (der Prod-Deploy scheiterte
# an genau diesen 13 getrackten Dateien: ``git stash create``/``reset
# --hard`` konnten sie wegen abweichender Verzeichnis-Rechte nicht
# handhaben; ``data/users/*`` ist seit #1602 ohnehin gitignored).
_REAL_DATA_FIXTURE_SRC = root / "tests" / "fixtures" / "data_root"

# Issue #2226 (Defekt 1 + 3): vor dem Fix gab es KEINE session-weite
# Umleitung -- ``app.loader._DATA_ROOT`` blieb den gesamten Lauf ueber
# unangetastet (None), bis eine funktionsweite Fixture sie kurzfristig
# setzte. Hoeher gescopte Fixtures (module/class/session) liefen deshalb
# VOR jeder Isolation direkt gegen den echten Baum. Die beiden Namen hier
# sind die einzige Quelle der Wahrheit fuer "echte Wurzel" bzw. "isolierte
# Session-Wurzel" -- von JEDER Redirect-Fixture unten gelesen/gesetzt,
# nirgends hartkodiert.
_ORIGINAL_DATA_ROOT: str | None = None
_SESSION_DATA_ROOT: str | None = None


@pytest.fixture(scope="session", autouse=True)
def _redirect_data_root_session(tmp_path_factory):
    """Leitet ``app.loader._DATA_ROOT`` SOFORT bei Sessionstart auf eine
    isolierte Wegwerf-Wurzel um -- laeuft vor JEDER hoeher gescopten
    Fixture (pytest-Scope-Rang: session > package > module > class >
    function), schliesst also Defekt 3 an der Wurzel.

    Sichert den Ausgangswert nach ``_ORIGINAL_DATA_ROOT``, BEVOR er
    ueberschrieben wird -- das ist die einzige Stelle, die diesen Wert je
    setzt. ``_materialize_real_data_root_fixtures`` (unten) haengt explizit
    von dieser Fixture ab, damit die Reihenfolge nicht dem Zufall der
    Definitionsreihenfolge ueberlassen bleibt.
    """
    global _ORIGINAL_DATA_ROOT, _SESSION_DATA_ROOT

    from app import loader

    _journal_festlegen(tmp_path_factory)

    _ORIGINAL_DATA_ROOT = getattr(loader, "_DATA_ROOT", None)
    _SESSION_DATA_ROOT = str(tmp_path_factory.mktemp("gz-data-root-session"))
    loader._DATA_ROOT = _SESSION_DATA_ROOT
    yield
    loader._DATA_ROOT = _ORIGINAL_DATA_ROOT


@pytest.fixture(scope="session", autouse=True)
def _importbindung_vorladen():
    """Issue #3209: ``services.position_fix`` bindet ``load_all_trips`` beim
    IMPORT (``from app.loader import load_all_trips``) und wird von
    ``trip_segments`` erst bei Bedarf importiert. Laeuft dieser Erstimport
    zufaellig waehrend eines Tests, der ``app.loader.load_all_trips`` per
    ``monkeypatch`` ersetzt (z. B. ``tests/unit/test_alert_channel_premium_sms.py``),
    behaelt das Modul den Ersatz fuer den REST des Prozesses -- und
    ``tests/unit/test_position_fix_snapping.py`` scheitert im selben Prozess.
    Seriell verdeckte die feste Reihenfolge das; unter xdist entscheidet die
    Verteilung (nachgemessen mit ``-n 4``). Einmal zu Sessionbeginn laden,
    damit die echte Funktion gebunden ist."""
    import services.position_fix  # noqa: F401
    yield


@pytest.fixture(scope="module", autouse=True)
def _isolate_data_root_module(request, _redirect_data_root_session):
    """Modul-scope Gegenstueck zu ``_isolate_data_root`` (Funktionsebene,
    unten). Noetig, weil ein modul-scope Fixture, das ``real_data_root``
    ueber ``pytestmark`` traegt, VOR der funktionsweiten Redirect-Fixture
    laeuft (Defekt 3) -- ohne dieses Gegenstueck wuerde das Opt-in fuer
    hoeher gescopte Fixtures wirkungslos bleiben, weil die Umleitung auf
    die echte Wurzel sonst erst zu spaet (auf Funktionsebene) griffe. Als
    Fixture in der ROOT-conftest wird sie vor modul-eigenen Fixtures
    DERSELBEN Testdatei gesetzt (pytest: Fixtures aus einer Vorfahren-
    conftest laufen vor gleich gescopten Fixtures der Testdatei selbst).
    """
    if request.node.get_closest_marker("real_data_root"):
        from app import loader

        loader._DATA_ROOT = _ORIGINAL_DATA_ROOT
        yield
        loader._DATA_ROOT = _SESSION_DATA_ROOT
        return
    yield


@pytest.fixture(scope="session", autouse=True)
def _guard_repo_data_users_session(_materialize_real_data_root_fixtures):
    """Session-weiter Waechter (Defekt 3): nimmt den Fingerprint des
    ECHTEN ``<repo>/data/users``-Baums NACH abgeschlossener Materialisierung
    (Abhaengigkeit oben) und vergleicht ihn am Ende der GESAMTEN Session
    erneut. Faengt damit JEDEN Schreibzugriff auf den echten Baum,
    unabhaengig vom Mechanismus (app.loader, CWD-relativ oder hartkodiert)
    und unabhaengig vom Fixture-Scope -- die funktionsweite Pruefung in
    ``_isolate_data_root`` sieht nur Schreibzugriffe INNERHALB einer
    einzelnen Testfunktion, nicht in hoeher gescopten Fixtures.

    WICHTIG: der ``before``-Schnappschuss darf NICHT vor der Materialisierung
    genommen werden -- sonst kopiert ``_materialize_real_data_root_fixtures``
    auf einem frischen (leeren) Checkout Dateien in den Baum, NACHDEM
    ``before`` schon leer war, und der Waechter meldet einen falschen
    Befund bei JEDEM Lauf auf einem frischen Checkout (z. B. CI). Deshalb
    haengt diese Fixture explizit von der Materialisierung ab, statt beide
    unabhaengig als Session-Fixtures zu deklarieren.

    Issue #3209 (xdist): in einem Worker sieht ein Session-Vergleich auch die
    Schreibzugriffe ANDERER Worker und koennte sie keinem Test zuordnen --
    der letzte Test jedes Workers wuerde faelschlich rot. Unter xdist macht
    deshalb der CONTROLLER denselben Netto-Vergleich ueber den ganzen Lauf
    (``pytest_sessionstart``/``pytest_sessionfinish`` unten), nachdem alle
    Worker fertig sind: gleich scharf (jede bleibende Aenderung ist ein
    Fehler, ohne Ausnahme), nur ohne falsche Zuordnung.
    """
    if _xdist_worker_id():
        yield
        return
    beginn = _echte_uhr()
    before = _detail_snapshot_repo_data_users()
    yield
    after = _detail_snapshot_repo_data_users()
    # Ohne Journal (normaler serieller Lauf) zaehlt jede Aenderung. Nur ein
    # Kind-Prozess eines xdist-Workers zieht Schreibzugriffe der parallel
    # laufenden Echtdaten-Gruppe des AEUSSEREN Laufs ab.
    if after != before and _unerklaerte_aenderungen(before, after, beginn):
        pytest.fail(_session_waechter_meldung(_aggregat(before), _aggregat(after)))


def _session_waechter_meldung(before: dict, after: dict) -> str:
    return (
        "Issue #2226: der echte "
        f"{_REPO_DATA_USERS}-Baum hat sich waehrend der GESAMTEN "
        f"Session veraendert (vorher: {before}, nachher: {after}). "
        "Ein Test/eine Fixture hat -- unabhaengig vom Scope -- direkt "
        "oder ueber app.loader in den echten Baum geschrieben, ohne "
        "@pytest.mark.real_data_root zu tragen, oder ein "
        "real_data_root-Test hat seine Spur nicht vollstaendig "
        "entfernt."
    )


@pytest.fixture(scope="session", autouse=True)
def _materialize_real_data_root_fixtures(_redirect_data_root_session) -> None:
    """Rematerialisiert die umgezogenen Referenz-Fixtures additiv (nie
    ueberschreibend) in den echten, gitignoreten ``<repo>/data/users``-Baum.

    ``@pytest.mark.real_data_root``-Tests (und mehrere Alt-Tests mit
    hartkodierten ``Path("data/users")``-Referenzen, u.a.
    ``test_alert_rules_model.py``, ``test_gpx_proxy.py``) lesen bewusst den
    ECHTEN Baum -- diese Session-Fixture stellt sicher, dass die Dateien dort
    trotz des Umzugs weiterhin physisch vorhanden sind. Laeuft als
    autouse-Session-Fixture in der ROOT-conftest, damit sie garantiert vor
    dem allerersten Test der gesamten Suite fertig ist (auch fuer
    tests/tdd/ und tests/unit/, nicht nur tests/integration/).

    Haengt explizit von ``_redirect_data_root_session`` ab (Issue #2226) --
    schreibt selbst ueber einen hartkodierten Pfad (``root / "data" / ...``,
    nicht ``loader._DATA_ROOT``) und ist damit vom Redirect unabhaengig,
    MUSS aber trotzdem vor dem session-weiten Waechter unten fertig sein.

    Zusaetzlich additiv gespiegelt: ``briefings/<id>.json`` aus jeder
    ``trips/<id>.json`` (Issue #1250 Scheibe 7a Cutover, ADR-0023) --
    ``load_trip``/``load_all_trips``/``get_briefings_dir`` lesen
    ausschliesslich ``briefings/``, nie ``trips/`` direkt. Ersetzt die
    fruehere, gleichwertige Fixture in ``tests/integration/conftest.py``
    (deren Quell-Glob nach dem Umzug leer gelaufen waere).

    Issue #3209: unter xdist starten mehrere Worker (und der Controller)
    gleichzeitig -- ``_materialisiere_echtdaten`` laeuft deshalb unter einer
    Dateisperre und schreibt jede Kopie atomar.
    """
    _materialisiere_echtdaten()


# Unter ``data/cache/`` (gitignored, ausserhalb von ``data/users``) -- taucht
# weder in ``git status`` noch im Waechter-Fingerprint auf.
_MATERIALISIERUNGS_SPERRE = root / "data" / "cache" / ".gz-materialisierung.lock"


def _materialisiere_echtdaten(
    quelle: Path | None = None,
    data_wurzel: Path | None = None,
    sperrdatei: Path | None = None,
) -> None:
    """Additive Materialisierung (Rumpf siehe Fixture oben), genau einmal je
    fehlender Datei ueber alle gleichzeitig startenden Prozesse hinweg.

    Die Parameter (Standard: committete Quelle, ``<repo>/data``, Sperre unter
    ``data/cache``) existieren nur, damit
    ``tests/tdd/test_xdist_materialisierung_parallel.py`` die Funktion aus
    mehreren gleichzeitigen Prozessen gegen ein Wegwerf-Ziel pruefen kann.

    * Dateisperre (``fcntl.flock``) auf ``data/cache/.gz-materialisierung.lock``
      (ausserhalb von ``data/users``, also nicht im Waechter-Fingerprint):
      der erste Prozess kopiert, alle weiteren warten und finden danach
      jede Datei vor -- kein Race "Ziel existiert schon, ist aber erst halb
      geschrieben".
    * Jede Kopie wird in eine Nachbardatei geschrieben und per
      ``os.replace`` atomar an ihren Platz gelegt -- ein Leser sieht nie eine
      halbe Datei, auch kein Prozess ohne Sperre.
    """
    import fcntl

    quelle = quelle or _REAL_DATA_FIXTURE_SRC
    data_wurzel = data_wurzel or (root / "data")
    sperrdatei = sperrdatei or _MATERIALISIERUNGS_SPERRE
    sperrdatei.parent.mkdir(parents=True, exist_ok=True)
    with open(sperrdatei, "a+") as sperre:
        fcntl.flock(sperre.fileno(), fcntl.LOCK_EX)
        try:
            for src_file in sorted(quelle.rglob("*")):
                if not src_file.is_file():
                    continue
                target = data_wurzel / src_file.relative_to(quelle)
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomar_schreiben(target, src_file.read_bytes())

            for trips_json in sorted((data_wurzel / "users").glob("*/trips/*.json")):
                briefings_dir = trips_json.parent.parent / "briefings"
                briefings_target = briefings_dir / trips_json.name
                if briefings_target.exists():
                    continue
                trip = json.loads(trips_json.read_text(encoding="utf-8"))
                trip.setdefault("kind", "route")
                briefings_dir.mkdir(parents=True, exist_ok=True)
                _atomar_schreiben(
                    briefings_target,
                    json.dumps(trip, indent=2, ensure_ascii=False).encode("utf-8"),
                )
        finally:
            fcntl.flock(sperre.fileno(), fcntl.LOCK_UN)


def _atomar_schreiben(ziel: Path, inhalt: bytes) -> None:
    zwischen = ziel.with_name(f".{ziel.name}.{os.getpid()}.tmp")
    try:
        zwischen.write_bytes(inhalt)
        os.replace(zwischen, ziel)
    finally:
        if zwischen.exists():
            zwischen.unlink()


def _snapshot_repo_data_users() -> dict[str, int]:
    """Issue #1265 Teil C (F003-Fix, Adversary Fix-Loop 1): rekursiver
    Aggregat-Fingerprint statt reiner Top-Level-mtime -- EIN ``os.walk`` pro
    Snapshot (Performance), erkennt aber auch In-Place-Content-Mutationen
    bestehender Dateien (die Top-Level-Verzeichnis-mtime ändert sich NICHT,
    wenn eine bestehende Datei per ``write_text``/``open(..., 'w')``
    überschrieben wird -- Adversary-Repro).

    Issue #3209: die Waechter vergleichen inzwischen den Fingerprint JE DATEI
    (``_detail_snapshot_repo_data_users``, strenger); diese Aggregat-Form
    bleibt fuer die Meldungen und ist daraus abgeleitet."""
    return _aggregat(_detail_snapshot_repo_data_users())


def _detail_snapshot_repo_data_users() -> dict[str, tuple[int, int]]:
    """Issue #3209: Fingerprint JE DATEI (relativer Pfad -> Groesse, mtime_ns).

    Strenger als der Aggregat-Fingerprint oben (jede einzelne Datei zaehlt)
    und Voraussetzung dafuer, unter xdist eine Aenderung einem Pfad -- und
    damit der seriellen Echtdaten-Gruppe oder eben NICHT -- zuzuordnen."""
    ergebnis: dict[str, tuple[int, int]] = {}
    if not _REPO_DATA_USERS.exists():
        return ergebnis
    basis = str(_REPO_DATA_USERS)
    try:
        for dirpath, _dirnames, filenames in os.walk(basis):
            for fname in filenames:
                voll = os.path.join(dirpath, fname)
                try:
                    st = os.stat(voll)
                except OSError:
                    continue
                ergebnis[os.path.relpath(voll, basis).replace(os.sep, "/")] = (
                    st.st_size, st.st_mtime_ns,
                )
    except OSError:
        return {}
    return ergebnis


def _aggregat(detail: dict[str, tuple[int, int]]) -> dict[str, int]:
    """Aggregat-Darstellung (wie ``_snapshot_repo_data_users``) fuer Meldungen."""
    if not detail:
        return {}
    return {
        "file_count": len(detail),
        "max_mtime_ns": max(m for _s, m in detail.values()),
        "total_size": sum(s for s, _m in detail.values()),
    }


# ---------------------------------------------------------------------------
# Issue #3209: parallele Laeufe (pytest-xdist, CI ``-n 4 --dist loadgroup``)
# ---------------------------------------------------------------------------
#
# Serielle Echtdaten-Gruppe: jeder ``real_data_root``-Test bekommt automatisch
# ``xdist_group("echtdaten")`` (``pytest_collection_modifyitems`` unten); mit
# ``--dist loadgroup`` laufen alle Gruppen-Tests nacheinander in EINEM Worker.
#
# Waechter worker-fest, nicht lockerer (Mechanismus "Gruppen-Journal"):
#
# * Der Worker der Gruppe protokolliert, WAEHREND ein Gruppen-Test laeuft
#   (Setup, Aufruf, Teardown), jeden Schreibzugriff auf den echten
#   ``data/users``-Baum VOR seiner Ausfuehrung in ein Journal des Laufs
#   (Python-Audit-Hook: ``open`` zum Schreiben, ``os.remove``, ``os.rename``,
#   ``os.replace``, ``os.utime``, ``os.truncate``, ``shutil.rmtree`` ...).
#   Kind-Prozesse eines Gruppen-Tests, die diese conftest laden (innere
#   pytest-Laeufe), erben das Journal ueber ``GZ_ECHTDATEN_JOURNALE`` und
#   protokollieren dort jeden ihrer Schreibzugriffe. Kind-Prozesse JEDES
#   Workers erben es zusaetzlich ueber ``GZ_ECHTDATEN_BEOBACHTUNG`` nur zum
#   Lesen (ein serieller innerer Lauf laeuft ja ebenfalls parallel zur
#   Gruppe); wer in ein Journal schreibt, liest es nie zur Entschuldigung.
# * Der Per-Test-Waechter eines Tests AUSSERHALB der Gruppe vergleicht den
#   Fingerprint je Datei und zieht nur die Pfade ab, die ein ANDERER Prozess
#   der Gruppe im Zeitfenster dieses Tests journalisiert hat. Jede andere
#   Aenderung bleibt ein Fehler -- auch wenn die Gruppe gerade gleichzeitig
#   schreibt (AC-3). Eigene Schreibzugriffe werden nie entschuldigt.
# * Der Session-Vergleich laeuft unter xdist im Controller nach dem Ende aller
#   Worker (Netto-Vergleich ohne jede Ausnahme).
# * Ohne xdist (lokaler Volllauf, Gate-Form) gibt es kein Journal: jede
#   Aenderung ist wie bisher ein Fehler (Fingerprint je Datei, also eher
#   strenger als der fruehere Aggregat-Vergleich).

_ECHTDATEN_GRUPPE = "echtdaten"
_JOURNAL_ENV = "GZ_ECHTDATEN_JOURNALE"
# Journale aeusserer Laeufe, die ein Kind-Prozess eines xdist-Workers nur
# LESEN darf (zum Abzug fremder Gruppen-Schreibzugriffe), siehe
# ``_erklaerende_journale``.
_BEOBACHTUNG_ENV = "GZ_ECHTDATEN_BEOBACHTUNG"
# [Journal, PID] des xdist-Workers, aus dem ein Kind-Prozess stammt (CI-Befund
# 2026-11-23, siehe ``_fremdlauf``).
_ELTERN_WORKER_ENV = "GZ_ECHTDATEN_ELTERN_WORKER"
# Karenz fuer die Reihenfolge "Journal-Eintrag" -> "Schreibzugriff" -> "Vorher-
# Fingerprint des Beobachters" (Eintrag liegt minimal VOR dem Testbeginn).
_JOURNAL_KARENZ_S = 1.0

# Eigenes Journal dieses Laufs (nur in einem xdist-Worker gesetzt, siehe
# ``_redirect_data_root_session``).
_EIGENES_JOURNAL: Path | None = None
# Von einem Gruppen-Test eines AEUSSEREN Laufs geerbte Journale:
# [(journal, quelle_pid), ...] -- hier wird JEDER Schreibzugriff dieses
# Prozesses auf den echten Baum protokolliert.
_GEERBTE_JOURNALE: list[tuple[str, int]] = []
_GRUPPE_AKTIV = False
_HOOK_INSTALLIERT = False

_SCHREIB_EVENTS = frozenset({
    "open", "os.remove", "os.rmdir", "os.rename", "os.replace", "os.utime",
    "os.truncate", "os.link", "os.symlink", "shutil.rmtree", "shutil.copyfile",
    "shutil.copytree", "shutil.move",
})
_SCHREIB_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def _echte_uhr() -> float:
    """Wanduhr, die freezegun NICHT verstellt (``time.time`` waere unter
    ``freeze_time`` eingefroren -- Journal-Zeitfenster zwischen Workern muessen
    aber auf derselben echten Uhr liegen)."""
    return time.clock_gettime(time.CLOCK_REALTIME)


# Wird in ``pytest_configure`` gesetzt: ``config.workerinput`` existiert nur im
# xdist-Worker selbst. NICHT ``PYTEST_XDIST_WORKER`` aus der Umgebung lesen --
# die Variable erbt jeder Kindprozess eines Workers (z. B. ein serieller
# innerer pytest-Lauf), der sich sonst faelschlich fuer einen Worker hielte
# und seinen Session-Waechter abschaltete.
_XDIST_WORKER_ID: str | None = None


def _xdist_worker_id() -> str | None:
    return _XDIST_WORKER_ID


def _ist_echtdaten_test(node) -> bool:
    if node.get_closest_marker("real_data_root"):
        return True
    for mark in node.iter_markers("xdist_group"):
        name = mark.args[0] if mark.args else mark.kwargs.get("name")
        if name == _ECHTDATEN_GRUPPE:
            return True
    return False


def _journal_festlegen(tmp_path_factory) -> None:
    """Gemeinsames Gruppen-Journal des Laufs, nur in einem xdist-Worker. Das
    basetemp eines Workers ist ``<basetemp des Controllers>/popen-gwN`` -- der
    Elternordner ist je Lauf eindeutig und allen Workern gemein."""
    global _EIGENES_JOURNAL
    if _EIGENES_JOURNAL is None and _xdist_worker_id():
        _EIGENES_JOURNAL = (
            tmp_path_factory.getbasetemp().parent / "gz-echtdaten-journal.jsonl"
        )
        # Kind-Prozesse dieses Workers (z. B. ein serieller innerer pytest-Lauf
        # eines Tests AUSSERHALB der Gruppe) laufen ebenfalls parallel zur
        # Gruppe und duerfen deren Schreibzugriffe nicht sich selbst anlasten.
        os.environ[_BEOBACHTUNG_ENV] = json.dumps(
            sorted({*_GEERBTE_BEOBACHTUNG, str(_EIGENES_JOURNAL)})
        )
        os.environ[_ELTERN_WORKER_ENV] = json.dumps([str(_EIGENES_JOURNAL), os.getpid()])


def _lies_geerbte_journale() -> list[tuple[str, int]]:
    roh = os.environ.get(_JOURNAL_ENV, "")
    if not roh:
        return []
    try:
        return [(str(j), int(q)) for j, q in json.loads(roh)]
    except (ValueError, TypeError):
        return []


def _pfad_text(wert) -> str | None:
    if isinstance(wert, int) or wert is None:
        return None
    try:
        return os.fsdecode(wert)
    except TypeError:
        return None


def _rel_im_echtbaum(wert, dir_fd=None) -> str | None:
    text = _pfad_text(wert)
    # Audit-Events melden "kein dir_fd" als -1 (bzw. AT_FDCWD -100), nicht None.
    ohne_dir_fd = dir_fd is None or dir_fd in (-1, -100)
    if text is None or (not ohne_dir_fd and not os.path.isabs(text)):
        return None
    voll = os.path.abspath(text)
    basis = str(_REPO_DATA_USERS)
    if voll == basis:
        return "."
    if voll.startswith(basis + os.sep):
        return voll[len(basis) + 1:].replace(os.sep, "/")
    return None


def _schreibziele(event: str, args: tuple) -> list[tuple[str, str]]:
    """[(art, relativer Pfad)] eines Audit-Events; art "datei" oder "baum"."""
    if event == "open":
        pfad, modus, flags = (tuple(args) + (None, None, None))[:3]
        schreibend = (
            any(c in modus for c in "wax+") if isinstance(modus, str)
            else isinstance(flags, int) and bool(flags & _SCHREIB_FLAGS)
        )
        if not schreibend:
            return []
        rel = _rel_im_echtbaum(pfad)
        return [("datei", rel)] if rel else []
    if event in ("os.remove", "os.utime", "os.truncate"):
        dir_fd = args[-1] if event != "os.truncate" and len(args) > 1 else None
        rel = _rel_im_echtbaum(args[0] if args else None, dir_fd)
        return [("datei", rel)] if rel else []
    if event == "os.rmdir":
        # Verzeichnisse zaehlen im Fingerprint nicht; ein (evtl. scheiterndes)
        # rmdir darf keinen ganzen Teilbaum entschuldigen.
        rel = _rel_im_echtbaum(args[0] if args else None, args[1] if len(args) > 1 else None)
        return [("datei", rel)] if rel else []
    if event == "shutil.rmtree":
        rel = _rel_im_echtbaum(args[0] if args else None, args[1] if len(args) > 1 else None)
        return [("baum", rel)] if rel else []
    # Zwei-Pfad-Events: Quelle und Ziel (os.rename/os.replace/os.link tragen
    # danach je ein dir_fd fuer Quelle und Ziel)
    ziele = []
    fds = list(args[2:4]) if event in ("os.rename", "os.replace", "os.link") else []
    fds += [None, None]
    for wert, dir_fd in zip(args[:2], fds):
        rel = _rel_im_echtbaum(wert, dir_fd)
        if rel:
            ziele.append(("baum" if event in ("shutil.copytree", "shutil.move") else "datei", rel))
    return ziele


_HOOK_ZUSTAND = threading.local()


def _journal_hook(event: str, args: tuple) -> None:
    if event not in _SCHREIB_EVENTS:
        return
    if not (_GRUPPE_AKTIV or _GEERBTE_JOURNALE):
        return
    if getattr(_HOOK_ZUSTAND, "drin", False):
        return
    _HOOK_ZUSTAND.drin = True
    try:
        ziele = _schreibziele(event, args)
        if not ziele:
            return
        jetzt = _echte_uhr()
        ausgaben = list(_GEERBTE_JOURNALE)
        if _GRUPPE_AKTIV and _EIGENES_JOURNAL is not None:
            ausgaben.append((str(_EIGENES_JOURNAL), os.getpid()))
        for journal, quelle in ausgaben:
            zeilen = "".join(
                json.dumps({"t": jetzt, "quelle": quelle, "art": art, "pfad": rel}) + "\n"
                for art, rel in ziele
            )
            try:
                fd = os.open(journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                try:
                    os.write(fd, zeilen.encode("utf-8"))
                finally:
                    os.close(fd)
            except OSError:
                pass
    except Exception:  # noqa: BLE001 -- ein Audit-Hook darf nie werfen
        pass
    finally:
        _HOOK_ZUSTAND.drin = False


def _hook_installieren() -> None:
    global _HOOK_INSTALLIERT
    if not _HOOK_INSTALLIERT:
        sys.addaudithook(_journal_hook)
        _HOOK_INSTALLIERT = True


# Kind-Prozess eines Gruppen-Tests (innerer pytest-Lauf): ab dem Import dieser
# conftest jeden Schreibzugriff auf den echten Baum ins aeussere Journal.
_GEERBTE_JOURNALE = _lies_geerbte_journale()
if _GEERBTE_JOURNALE:
    _hook_installieren()


def _lies_geerbte_beobachtung() -> list[str]:
    try:
        return [str(j) for j in json.loads(os.environ.get(_BEOBACHTUNG_ENV, "") or "[]")]
    except (ValueError, TypeError):
        return []


_GEERBTE_BEOBACHTUNG = _lies_geerbte_beobachtung()


def _lies_eltern_worker() -> tuple[str, int] | None:
    try:
        journal, pid = json.loads(os.environ.get(_ELTERN_WORKER_ENV, "") or "null")
        return str(journal), int(pid)
    except (ValueError, TypeError):
        return None


# Beim IMPORT lesen: ein innerer xdist-Worker ueberschreibt die Variable spaeter
# fuer seine eigenen Kinder (``_journal_festlegen``).
_ELTERN_WORKER = _lies_eltern_worker()


def _fremdlauf() -> bool:
    """CI-Befund 2026-11-23: dieser Prozess ist ein innerer pytest-Lauf, den
    ein Test AUSSERHALB der Echtdaten-Gruppe in einem xdist-Worker gestartet
    hat (``test_issue_1014_live_optin.py`` fuehrte so ``test_issue_1001``
    samt Budget-Spur unter ``data/users/default`` aus). Erkennbar daran, dass
    das Journal des startenden Workers NICHT unter den geerbten
    Gruppen-Journalen ist -- nur ein laufender Gruppen-Test vererbt es.
    Seine Schreibzugriffe stuenden in keinem Journal und liefen parallel zur
    seriellen Gruppe: der Waechter eines Unbeteiligten schluege an."""
    if _ELTERN_WORKER is None:
        return False
    return _ELTERN_WORKER[0] not in {j for j, _q in _GEERBTE_JOURNALE}


def _melde_fremdlauf(nodeid: str) -> None:
    """Meldung ins Journal des startenden Workers -- dessen Test wird rot,
    auch wenn er den Exit-Code seines inneren Laufs ignoriert."""
    journal, ziel = _ELTERN_WORKER
    zeile = json.dumps({
        "t": _echte_uhr(), "quelle": os.getpid(), "art": "fremdlauf",
        "ziel": ziel, "test": nodeid,
    }) + "\n"
    try:
        fd = os.open(journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, zeile.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def _fremdlauf_meldungen(seit: float) -> list[str]:
    """Tests, die ein Kind-Prozess DIESES Workers seit ``seit`` als
    Fremdlauf abgewiesen hat."""
    if _EIGENES_JOURNAL is None:
        return []
    try:
        zeilen = _EIGENES_JOURNAL.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tests = []
    for zeile in zeilen:
        try:
            eintrag = json.loads(zeile)
        except ValueError:
            continue
        if (eintrag.get("art") == "fremdlauf" and eintrag.get("ziel") == os.getpid()
                and eintrag.get("t", 0) >= seit):
            tests.append(str(eintrag.get("test")))
    return tests


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Vor JEDER Fixture (auch modul-scope): ein ``real_data_root``-Test laeuft
    in einem Fremdlauf nicht -- er schriebe ungeordnet neben der seriellen
    Gruppe in den echten Baum."""
    if item.get_closest_marker("real_data_root") and _fremdlauf():
        _melde_fremdlauf(item.nodeid)
        pytest.fail(
            "Issue #3209: real_data_root-Test in einem inneren pytest-Lauf, den "
            "ein Test AUSSERHALB der seriellen Echtdaten-Gruppe gestartet hat -- "
            "er wird nicht ausgefuehrt. Abhilfe: den startenden Test mit "
            '@pytest.mark.xdist_group("echtdaten") markieren.',
            pytrace=False,
        )


def _erklaerende_journale() -> list[str]:
    """Journale, deren Eintraege eine Aenderung am echten Baum erklaeren:
    das eigene Lauf-Journal (xdist-Worker) und die geerbten Beobachtungs-
    Journale -- AUSSER denen, in die dieser Prozess selbst schreibt (ein
    Kind-Prozess eines Gruppen-Tests darf seine eigenen Schreibzugriffe nie
    entschuldigen; er bleibt so streng wie ein serieller Lauf)."""
    selbst = {j for j, _q in _GEERBTE_JOURNALE}
    journale = [str(_EIGENES_JOURNAL)] if _EIGENES_JOURNAL is not None else []
    journale += [j for j in _GEERBTE_BEOBACHTUNG if j not in selbst and j not in journale]
    return journale


def _journal_erklaert(seit: float) -> tuple[set[str], list[str]]:
    """(exakte Pfade, Teilbaum-Praefixe), die ANDERE Prozesse einer
    Echtdaten-Gruppe seit ``seit`` (minus Karenz) journalisiert haben."""
    dateien: set[str] = set()
    baeume: list[str] = []
    grenze = seit - _JOURNAL_KARENZ_S
    eigene_pid = os.getpid()
    for journal in _erklaerende_journale():
        try:
            zeilen = Path(journal).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for zeile in zeilen:
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if eintrag.get("t", 0) < grenze or eintrag.get("quelle") == eigene_pid:
                continue
            if eintrag.get("art") == "baum":
                baeume.append(eintrag["pfad"])
            elif eintrag.get("art") == "datei":
                dateien.add(eintrag["pfad"])
    return dateien, baeume


def _unerklaerte_aenderungen(
    vorher: dict[str, tuple[int, int]], nachher: dict[str, tuple[int, int]], seit: float,
) -> list[str]:
    """Geaenderte Pfade, die NICHT der Echtdaten-Gruppe eines anderen Prozesses
    zuzuordnen sind. Ohne Journal (normaler serieller Lauf) ist jede Aenderung
    unerklaert."""
    geaendert = sorted(p for p in vorher.keys() | nachher.keys() if vorher.get(p) != nachher.get(p))
    if not geaendert or not _erklaerende_journale():
        return geaendert
    dateien, baeume = _journal_erklaert(seit)
    return [
        p for p in geaendert
        if p not in dateien
        and not any(b == "." or p == b or p.startswith(b + "/") for b in baeume)
    ]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Issue #3209: jeder ``real_data_root``-Test gehoert automatisch zur
    seriellen ``xdist_group("echtdaten")``. ``tryfirst``, damit xdist (das die
    Gruppe in die Knoten-ID schreibt) die Markierung bereits sieht. Eine
    zusaetzliche FREMDE Gruppe wuerde xdist zu einer eigenen Gruppe
    zusammensetzen und den Test aus der seriellen Gruppe holen -- das ist ein
    Widerspruch und bricht die Sammlung ab."""
    for item in items:
        if not item.get_closest_marker("real_data_root"):
            continue
        fremde = sorted({
            str(m.args[0] if m.args else m.kwargs.get("name", "default"))
            for m in item.iter_markers("xdist_group")
        } - {_ECHTDATEN_GRUPPE})
        if fremde:
            raise pytest.UsageError(
                f"Issue #3209: {item.nodeid} traegt real_data_root UND die "
                f"fremde xdist_group {fremde} -- real_data_root-Tests laufen "
                f"ausschliesslich in der seriellen Gruppe '{_ECHTDATEN_GRUPPE}'."
            )
        if not any(
            (m.args[0] if m.args else m.kwargs.get("name")) == _ECHTDATEN_GRUPPE
            for m in item.iter_markers("xdist_group")
        ):
            item.add_marker(pytest.mark.xdist_group(_ECHTDATEN_GRUPPE))


class _XdistGruppenSuffix:
    """Issue #3209: ``--dist loadgroup`` gruppiert nach dem Suffix ``@<gruppe>``
    in der Knoten-ID, den pytest-xdist (3.8.0) im Worker ueber
    ``item._nodeid`` setzt. Seit pytest 9 liest ``item.nodeid`` aber
    ``item._id`` (strukturierte ``NodeId``) -- die Zuweisung von xdist ist
    wirkungslos, JEDER Test wird zu einer eigenen Arbeitseinheit und
    ``xdist_group`` faellt still aus (nachgemessen: auch eine nackte Datei
    ohne diese conftest verteilt eine Gruppe auf zwei Worker).

    Dieses Plugin setzt den Suffix deshalb selbst -- ``trylast``, also nach
    allen Abwahlen (``--deselect``, ``-k``, ``-m``) und nach dem xdist-Hook.
    Traegt die Knoten-ID schon einen Suffix (aeltere pytest-Version, bei der
    xdist selbst greift), bleibt sie unveraendert."""

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config, items):
        if not getattr(config.option, "loadgroup", False):
            return
        for item in items:
            namen = sorted({
                str(m.args[0] if m.args else m.kwargs.get("name", "default"))
                for m in item.iter_markers("xdist_group")
            })
            if not namen:
                continue
            nodeid = item.nodeid
            if nodeid.rfind("@") > nodeid.rfind("]"):
                continue
            _knoten_id_setzen(item, f"{nodeid}@{'_'.join(namen)}")


def _knoten_id_setzen(item, neu: str) -> None:
    alt = getattr(item, "_id", None)
    if alt is None:  # pytest < 9
        item._nodeid = neu
        return
    kopie = dataclasses.replace(alt)
    # ``NodeId`` ist eingefroren; ``__str__`` liefert den zwischengespeicherten
    # Text, Vergleich/Hash ignorieren ihn (``compare=False``).
    object.__setattr__(kopie, "_str_cache", neu)
    item._id = kopie


def pytest_configure(config):
    global _XDIST_WORKER_ID
    workerinput = getattr(config, "workerinput", None)
    _XDIST_WORKER_ID = workerinput.get("workerid") if workerinput else None
    if not config.pluginmanager.has_plugin("gz-xdist-gruppen-suffix"):
        config.pluginmanager.register(_XdistGruppenSuffix(), "gz-xdist-gruppen-suffix")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Issue #3209: im xdist-Worker der Echtdaten-Gruppe das Journal waehrend
    des GESAMTEN Testprotokolls (Setup, Aufruf, Teardown) fuehren und an
    Kind-Prozesse vererben."""
    global _GRUPPE_AKTIV
    if not (_xdist_worker_id() and _ist_echtdaten_test(item)):
        yield
        return
    # Der erste Test eines Workers laeuft VOR jeder Session-Fixture -- das
    # Journal deshalb hier schon festlegen.
    _journal_festlegen(item.config._tmp_path_factory)
    _hook_installieren()
    alt = os.environ.get(_JOURNAL_ENV)
    os.environ[_JOURNAL_ENV] = json.dumps(
        [*_GEERBTE_JOURNALE, (str(_EIGENES_JOURNAL), os.getpid())]
    )
    _GRUPPE_AKTIV = True
    try:
        yield
    finally:
        _GRUPPE_AKTIV = False
        if alt is None:
            os.environ.pop(_JOURNAL_ENV, None)
        else:
            os.environ[_JOURNAL_ENV] = alt


def _ist_xdist_controller(config) -> bool:
    return (
        not hasattr(config, "workerinput")
        and config.pluginmanager.hasplugin("dsession")
    )


_CONTROLLER_VORHER: dict | None = None
_CONTROLLER_BEGINN = 0.0


def pytest_sessionstart(session):
    """Issue #3209: Session-Waechter des xdist-Controllers -- Materialisierung
    (unter Sperre) und Vorher-Fingerprint, bevor ein Worker einen Test
    ausfuehrt."""
    global _CONTROLLER_VORHER, _CONTROLLER_BEGINN
    if not _ist_xdist_controller(session.config):
        return
    _materialisiere_echtdaten()
    _CONTROLLER_BEGINN = _echte_uhr()
    _CONTROLLER_VORHER = _detail_snapshot_repo_data_users()


def pytest_sessionfinish(session, exitstatus):
    """Issue #3209: Netto-Vergleich nach dem Ende ALLER Worker; jede bleibende
    Aenderung am echten Baum laesst den Lauf scheitern (wie der serielle
    Session-Waechter ``_guard_repo_data_users_session``). Das eigene
    Gruppen-Journal des Laufs zaehlt hier NICHT (der Controller hat keins):
    auch eine Spur, die die Gruppe selbst hinterlassen hat, ist ein Fehler."""
    if _CONTROLLER_VORHER is None or not _ist_xdist_controller(session.config):
        return
    nachher = _detail_snapshot_repo_data_users()
    if nachher == _CONTROLLER_VORHER or not _unerklaerte_aenderungen(
        _CONTROLLER_VORHER, nachher, _CONTROLLER_BEGINN,
    ):
        return
    meldung = "ERROR (xdist-Controller) " + _session_waechter_meldung(
        _aggregat(_CONTROLLER_VORHER), _aggregat(nachher),
    )
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep("=", "Echtbaum-Waechter (Issue #2226/#3209)", red=True)
        reporter.write_line(meldung, red=True)
    else:
        print(meldung)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


_BUDGET_SPUR_MUSTER = "*/diagnostics/forecast_budget.json*"


@pytest.fixture(autouse=True)
def _raeume_budget_spur_bei_real_data_root(request):
    """Issue #2387: `ForecastBudgetGate` legt seit dem Kontingent je Nutzer
    einen Tageszaehler unter
    ``data/users/<user_id>/diagnostics/forecast_budget.json`` an -- also
    INNERHALB des von ``_guard_repo_data_users_session`` bewachten Baums
    (der globale Topf liegt weiterhin unter ``data/diagnostics/``, also
    ausserhalb). Ein ``real_data_root``-Test, der einen echten Wetterabruf
    ausloest (gemessen: ``test_issue_363_signal_telegram_preview.py``,
    51 Abrufe), hinterlaesst damit eine Spur, die der Waechter zu Recht
    meldet -- und die vor #2387 nicht entstehen konnte.

    Der Waechter nennt genau diesen Fall selbst als erwartete Ursache
    ("ein real_data_root-Test hat seine Spur nicht vollstaendig
    entfernt"). Die Spur wird deshalb hier zentral entfernt, statt den
    Waechter aufzuweichen: er misst jede Trip-, Briefing-, GPX- und
    Settings-Datei unveraendert scharf, und auch den Zaehler selbst, wenn
    ihn ein Test NICHT selbst angelegt hat.

    Zentral statt je Testdatei, weil es keine Eigenheit von #363 ist: JEDER
    kuenftige ``real_data_root``-Test mit Wetterabruf traefe dasselbe.

    Zwei Faelle, beide eng gefuehrt (Adversary Fix-Loop 1, F005):

    * Der Pfad entstand WAEHREND des Tests -> er wird entfernt.
    * Der Pfad bestand schon VOR dem Test (Rest einer abgebrochenen
      ``real_data_root``-Session) -> sein Byte-Inhalt wird vorher gemerkt
      und danach exakt wiederhergestellt -- samt ``mtime`` (der
      Fingerprint misst neben Inhalt und Groesse auch ``max_mtime_ns``,
      also genuegt das Zurueckschreiben des Inhalts allein nicht). Ohne
      das schlaegt der Waechter trotz aktiver Fixture an, weil der Test
      die Datei in-place ueberschreibt: der Pfad ist bekannt, der Inhalt
      und der Zeitstempel nicht.

    Beides gilt AUSSCHLIESSLICH fuer ``diagnostics/forecast_budget.json``
    (und deren Sidecar-Lock). Jede Trip-, Briefing-, GPX- und
    Settings-Datei faellt dem Waechter unveraendert auf.

    Verzeichnisse zaehlen im Fingerprint nicht
    (``_snapshot_repo_data_users`` laeuft nur ueber ``filenames``), ein
    leer zurueckbleibendes ``diagnostics/`` wird trotzdem aufgeraeumt.
    """
    if not request.node.get_closest_marker("real_data_root"):
        yield
        return
    vorher: dict[Path, tuple[bytes, int, int] | None] = {}
    if _REPO_DATA_USERS.exists():
        for pfad in _REPO_DATA_USERS.glob(_BUDGET_SPUR_MUSTER):
            try:
                st = pfad.stat()
                vorher[pfad.resolve()] = (
                    pfad.read_bytes(), st.st_atime_ns, st.st_mtime_ns,
                )
            except OSError:
                vorher[pfad.resolve()] = None
    yield
    if not _REPO_DATA_USERS.exists():
        return
    for pfad in list(_REPO_DATA_USERS.glob(_BUDGET_SPUR_MUSTER)):
        aufgeloest = pfad.resolve()
        if aufgeloest in vorher:
            # Adversary Fix-Loop 1 (F005): eine VORBESTEHENDE Zaehlerdatei
            # (Rest einer abgebrochenen `real_data_root`-Session) wird vom
            # Test in-place ueberschrieben -- ihr Pfad ist dann in `vorher`,
            # ihr INHALT aber veraendert, und der Waechter schlaegt trotz
            # aktiver Fixture an. Deshalb wird der Byte-Inhalt gemerkt und
            # exakt wiederhergestellt, statt nur die Existenz zu pruefen.
            # Ausschliesslich diese eine Datei; alles andere bleibt dem
            # Waechter ueberlassen.
            zustand = vorher[aufgeloest]
            if zustand is None:
                continue
            inhalt, atime_ns, mtime_ns = zustand
            try:
                if pfad.read_bytes() != inhalt:
                    pfad.write_bytes(inhalt)
                # Der Fingerprint misst NEBEN Inhalt und Groesse auch
                # `max_mtime_ns` -- ein blosses Zurueckschreiben des Inhalts
                # laesst den Waechter weiterhin anschlagen, weil der
                # Schreibvorgang selbst die mtime hebt.
                os.utime(pfad, ns=(atime_ns, mtime_ns))
            except OSError:
                pass
            continue
        try:
            pfad.unlink()
        except OSError:
            continue
        elternteil = pfad.parent
        if elternteil.name == "diagnostics" and not any(elternteil.iterdir()):
            try:
                elternteil.rmdir()
            except OSError:
                pass


@pytest.fixture(autouse=True)
def _isolate_data_root(request, tmp_path_factory):
    """Redirect ``app.loader._DATA_ROOT`` to an isolated temp root for every
    test (Issue #1133), so pytest runs never write into the real
    ``data/users/`` tree.

    Nur ``@pytest.mark.real_data_root`` schaltet die Isolation ab -- Tests
    opten damit bewusst gegen den echten Baum (Contract-Tests). Issue #2226
    (Defekt 1): ``@pytest.mark.live`` allein bedeutet laut ``pyproject.toml``
    nur Netz-Egress und schaltet die Isolation seither NICHT mehr ab; ein
    live-markierter Test durchlaeuft denselben isolierten Pfad wie jeder
    andere Test.

    Issue #1624: die fuer das Opt-in benoetigten, frueher direkt hier
    committeten Referenz-Fixtures (gr221-mallorca, validator-issue110,
    GPX-Dateien) sind nach ``tests/fixtures/data_root`` umgezogen (``data/``
    bleibt so vollstaendig untracked) und werden von der Session-Fixture
    ``_materialize_real_data_root_fixtures`` oben additiv wieder in diesen
    Baum kopiert -- fuer den echten Baum selbst aendert sich dadurch nichts.

    Issue #1265 Teil C / #2226: diese funktionsweite Pruefung sieht nur
    Schreibzugriffe INNERHALB der eigenen Testfunktion -- hoeher gescopte
    Fixtures (module/class/session) laufen VOR ihr und werden vom
    session-weiten Waechter (``_guard_repo_data_users_session`` oben)
    gefangen, nicht hier.
    """
    if request.node.get_closest_marker("real_data_root"):
        from app import loader

        loader._DATA_ROOT = _ORIGINAL_DATA_ROOT
        yield
        # Zurueck auf die Session-Wurzel, NICHT auf _ORIGINAL_DATA_ROOT --
        # sonst sickert die echte Wurzel in JEDEN nachfolgenden Test durch,
        # weil dessen eigene "before"-Erfassung dann faelschlich die echte
        # Wurzel als Ausgangswert saehe (Issue #2226).
        loader._DATA_ROOT = _SESSION_DATA_ROOT
        return

    from app import loader

    before = getattr(loader, "_DATA_ROOT", None)
    isolated_root = tmp_path_factory.mktemp("data_root")
    loader._DATA_ROOT = str(isolated_root)

    # Issue #3209: Fingerprint je Datei; Startzeit auf der echten Uhr fuer das
    # Zeitfenster im Gruppen-Journal (nur unter xdist relevant).
    beginn = _echte_uhr()
    before_snapshot = _detail_snapshot_repo_data_users()
    yield
    loader._DATA_ROOT = before

    abgewiesen = _fremdlauf_meldungen(beginn)
    if abgewiesen:
        pytest.fail(
            "Issue #3209: dieser Test startet einen inneren pytest-Lauf mit "
            f"real_data_root-Tests ({abgewiesen[:3]}), gehoert aber nicht zur "
            "seriellen Echtdaten-Gruppe -- unter xdist schrieben sie parallel zur "
            "Gruppe ohne Journal in den echten Baum. Abhilfe: "
            '@pytest.mark.xdist_group("echtdaten") an diesem Test.'
        )

    after_snapshot = _detail_snapshot_repo_data_users()
    if after_snapshot != before_snapshot:
        unerklaert = _unerklaerte_aenderungen(before_snapshot, after_snapshot, beginn)
        if unerklaert:
            pytest.fail(
                "Issue #1265 Teil C (F003-Fix): dieser Test hat unter dem "
                f"ECHTEN {_REPO_DATA_USERS} geschrieben (vorher: "
                f"{_aggregat(before_snapshot)}, nachher: "
                f"{_aggregat(after_snapshot)}; geaenderte Pfade: "
                f"{unerklaert[:10]}). "
                "Kern-Tests duerfen nur ueber die isolierte "
                "app.loader.get_data_dir()-Basis bzw. tmp_path schreiben. "
                "Abhilfe: Pfad-Quelle auf get_data_dir()/tmp_path umstellen, "
                "oder falls der Test bewusst den echten Baum braucht: "
                "@pytest.mark.real_data_root setzen."
            )


_EGRESS_SETTINGS = None


def _egress_guard_settings():
    """Ein einziges ``Settings(is_test_mode=True)`` fuer die gesamte Session
    zwischenspeichern -- pydantic ``BaseSettings`` liest sonst pro Test die
    ``.env`` neu (Overhead ueber ~5000 Tests). Nur die statischen Felder
    ``is_test_mode``/``env``/``test_smtp_host``/``imap_host`` werden vom Guard
    gelesen; diese sind pro Session konstant."""
    global _EGRESS_SETTINGS
    if _EGRESS_SETTINGS is None:
        from app.config import Settings

        _EGRESS_SETTINGS = Settings(is_test_mode=True)
    return _EGRESS_SETTINGS


@pytest.fixture(autouse=True)
def _egress_guard(request):
    """Issue #1337 Scheibe A: zentraler Egress-Waechter als Tripwire im
    deterministischen Kern-Testlauf aktiv -- faengt unbemerkten realen Egress
    an kostenpflichtige/nebenwirkungsbehaftete Dienste (seven.io, Telegram,
    Resend, undeklarierte Hosts). Nach jedem Test werden die drei
    Transport-Primitive auf ihre Original-Referenzen zurueckgesetzt
    (uninstall_egress_guard), damit kein Patch-Zustand in Folgetests leakt
    (Spec ``egress_guard.md`` Test 8).

    Ausnahmen (bewusst enger Scope, damit kein Bestandstest bricht und die
    Spec-Absicht -- Tripwire fuer den Kern -- erhalten bleibt):

    - ``live``/``email``/``staging``-Marker: das sind exakt die Schichten, in
      denen echte externe Aufrufe *gewollt* sind (Spec ``Known Limitations``:
      "@pytest.mark.live-Tests installieren den Guard bewusst nicht"). Der
      deterministische Kern ist genau ``not live and not staging and not
      email`` -- dort und nur dort greift der Waechter.
    - Das ``test_egress_guard``-Modul verwaltet den Guard selbst: es setzt
      eigene Sentinel-Transporte VOR ``install_egress_guard()``. Ein globaler
      Vor-Install wuerde per Idempotenz-Flag den Eigen-``install()`` zum No-Op
      machen, sodass der Guard die Sentinels nicht mehr umschliesst -- die
      Eigen-Tests wuerden falsch scheitern.
    """
    node = request.node
    if (
        node.get_closest_marker("live")
        or node.get_closest_marker("email")
        or node.get_closest_marker("staging")
        or "test_egress_guard" in node.nodeid
    ):
        yield
        return

    from app.egress_guard import install_egress_guard, uninstall_egress_guard

    install_egress_guard(_egress_guard_settings())
    try:
        yield
    finally:
        uninstall_egress_guard()


@pytest.fixture(autouse=True)
def _isolate_warn_calls_path(request, tmp_path_factory):
    """Issue #1348: die vom Warn-Egress-Zähler geschriebene JSONL-Datei
    ``services.official_alerts.warn_egress`` (real
    ``<Datenwurzel>/diagnostics/warn_service_calls.jsonl``) für JEDEN Test auf eine
    Wegwerf-Datei im tmp-Bereich umlenken, damit KEIN Test die echte
    Diagnose-Datei verschmutzt.

    Vorbild: ``_isolate_data_root`` oben (Save/Redirect/Restore). Der Zähler
    wird u.a. indirekt über ``get_official_alerts_for_location`` /
    ``MeteoAlarmSource.fetch`` aus vielen Suiten ausgelöst, nicht nur aus den
    beiden #1348-Testdateien — deshalb greift die Umlenkung global.

    Issue #1633: Seit der Pfad über ``warn_calls_path()`` zur LAUFZEIT aus
    ``app.loader.get_data_root()`` folgt, schützt bereits ``_isolate_data_root``
    oben jeden normalen Test. Diese Umlenkung ist dort nicht mehr nötig — und
    schädlich, weil sie verdecken würde, ob die Datenwurzel überhaupt beachtet
    wird. Sie bleibt genau für den Fall, in dem ``_isolate_data_root``
    aussteigt (``real_data_root`` -- seit Issue #2226 steigt ``live`` allein
    dort NICHT mehr aus): dort soll die reale Diagnose-Datei trotzdem NIE aus
    Tests wachsen. Der zusätzliche ``live``-Zweig im Marker-Check unten ist
    seit #2226 redundant, aber unschädlich: die Datenwurzel eines reinen
    ``live``-Tests ist ohnehin schon isoliert, dieser Override betrifft nur
    eine weitere, ebenfalls sichere tmp-Datei.

    Wichtig für die Rücklese-Tests (AC-7/8/9 in
    ``test_warn_service_egress.py`` sowie die MeteoAlarm-Suite): setzen diese
    ihren EIGENEN ``monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", ...)``,
    so läuft dieser Per-Test-Override IM Test-Body — also NACH dieser
    Fixture-Einrichtung — und gewinnt. Nach dem Test stellt monkeypatch auf
    den hier gesetzten tmp-Wert zurück, diese Fixture danach auf das Original.
    """
    from services.official_alerts import warn_egress

    if not (
        request.node.get_closest_marker("real_data_root")
        or request.node.get_closest_marker("live")
    ):
        yield  # Datenwurzel-Isolation oben genügt (#1633)
        return

    before = warn_egress.WARN_CALLS_PATH_OVERRIDE
    throwaway = tmp_path_factory.mktemp("warn_calls") / "warn_service_calls.jsonl"
    warn_egress.WARN_CALLS_PATH_OVERRIDE = throwaway
    try:
        yield
    finally:
        warn_egress.WARN_CALLS_PATH_OVERRIDE = before


@pytest.fixture(autouse=True)
def _reset_shared_radar_cache():
    """Issue #1329 C2: der Radar-Frame-Cache (`services.radar_cache`) ist
    ein Prozess-Singleton mit 300s-TTL. Ohne Reset zwischen Tests koennten
    zwei Testfaelle, die dieselbe (gerundete) Koordinate verwenden aber
    unterschiedliche `frame_source`-Fakes injizieren, sich innerhalb des
    TTL-Fensters gegenseitig kontaminieren (Cache-Hit liefert Frames eines
    ANDEREN Tests). Lazy-Import haelt Tests, die den Radar-Pfad nicht
    beruehren, frei von einer Import-Zeit-Abhaengigkeit."""
    from services.radar_cache import reset_shared_radar_cache_for_tests
    reset_shared_radar_cache_for_tests()
    yield
    reset_shared_radar_cache_for_tests()


@pytest.fixture(autouse=True)
def _reset_thunder_window_cache():
    """Issue #1457 S2a (AC-9): der geteilte Gewitter-Fensterspeicher
    (`providers.thunder_window_cache`) ist ein Prozess-Singleton mit 600s-TTL.
    Ohne Reset zwischen Testfaellen wuerde ein Test die Abrufe eines frueheren
    Tests erben — Abrufzaehler messen dann nicht mehr den eigenen Lauf, und ein
    Test mit anderer Aufzeichnung bekaeme die Daten des vorherigen. Analog
    `_reset_shared_radar_cache`."""
    from providers.thunder_window_cache import reset_thunder_window_cache_for_tests
    reset_thunder_window_cache_for_tests()
    yield
    reset_thunder_window_cache_for_tests()


@pytest.fixture(autouse=True)
def _reset_parallel_fetch():
    """Issue #3081 AC-5: der Parallelabruf (`services.parallel_fetch`) haelt
    prozessweit Executor und Semaphoren je Provider. Nachlaufende Worker eines
    frueheren Tests koennten sonst Slots (z. B. `official_alerts`) ueber das
    Testende hinaus belegen. Nach JEDEM Test zuruecksetzen (lazy neu angelegt)."""
    yield
    from services import parallel_fetch
    parallel_fetch._reset_for_tests()


@pytest.fixture(autouse=True)
def _reset_shared_weather_cache():
    """Issue #1557: der geteilte Wetter-Cache (`services.weather_cache`) ist
    ein Prozess-Singleton mit 600s-TTL, Treffer ueber "Fenster deckt ab".
    Ohne Reset zwischen Testfaellen bedient ein spaeterer Testfall still aus
    dem Cache-Eintrag eines frueheren -- ein absichtlich scheiternder
    Provider-Double wird dann nie aufgerufen, weil der Cache-Hit den Abruf
    gar nicht erst ausloest. Analog `_reset_shared_radar_cache` und
    `_reset_thunder_window_cache`."""
    from services.weather_cache import reset_shared_weather_cache_for_tests
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()


@pytest.fixture(autouse=True)
def _reset_telegram_rate_limit():
    """Issue #1370: die Telegram-Sende-Drossel fuehrt ihre Zeitstempel je Chat
    prozessweit auf Klassenebene (fuer JEDE Bubble wird eine frische
    ``TelegramOutput``-Instanz gebaut — ein Instanz-Attribut waere wirkungslos).
    Ohne Reset zwischen Testfaellen summieren sich die Sendungen vieler Tests,
    die dieselbe Chat-ID verwenden, im 60-Sekunden-Fenster auf und ein spaeterer
    Test laeuft in eine echte Wartezeit. Analog ``_reset_shared_radar_cache``."""
    from output.channels.telegram import reset_telegram_rate_limit_for_tests
    from services.inbound_telegram_reader import reset_registrierungshinweise_for_tests
    reset_telegram_rate_limit_for_tests()
    reset_registrierungshinweise_for_tests()  # #2961: Hinweis-Sperre je Chat
    yield
    reset_telegram_rate_limit_for_tests()
    reset_registrierungshinweise_for_tests()

# ---------------------------------------------------------------------------
# Issue #2096: gestellte Wanduhr fuer den GANZEN Lauf
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _gestellte_wanduhr():
    """Stellt die Uhr des gesamten Laufs auf ``GZ_TEST_WALL_CLOCK_UTC``.

    Nachweis-Werkzeug fuer die Zeitunabhaengigkeit (#2096 AC-10): dieselbe
    Testmenge muss um 12:00 UTC dasselbe Ergebnis liefern wie um 23:58 UTC.
    Ohne diesen Schalter liesse sich das nur belegen, indem man auf die
    entsprechende Tageszeit wartet oder die SYSTEMzeit des Servers verstellt —
    beides ist keine Option.

    Ohne gesetzte Variable passiert NICHTS: der Normallauf (CI, lokal) laeuft
    unveraendert auf der echten Wanduhr. Das ist Absicht — ein dauerhaft
    gestellter Lauf wuerde genau die Zeitabhaengigkeit verdecken, die hier
    gefunden werden soll.

    Format: ``HH:MM`` (heutiges Datum, UTC) oder ein vollstaendiger
    ISO-Zeitstempel. ``tick=True``, damit die Zeit waehrend des Laufs weiter
    voranschreitet — ein vollstaendig stehender Zaehler waere ein anderer
    Zustand als "der Lauf startet um 23:58".

    Session-Scope und damit AUSSERHALB jedes ``@freeze_time`` einzelner
    Testfaelle: freezegun stapelt, der innere Zeitpunkt gewinnt.

    Selbst bewacht durch ``tests/tdd/test_gestellte_wanduhr_schalter.py``:
    ein Nachweiswerkzeug ohne Selbsttest ist genau der blinde Waechter,
    gegen den dieses Ticket geschrieben ist -- legt man diese Fixture stumm,
    saehen die vier Uhrzeit-Laeufe weiterhin gruen aus und maessen nichts
    (Adversary-Finding F001 zu #2096).
    """
    from tests.helpers.wanduhr import anker_aus, roh_wert

    roh = roh_wert()
    if not roh:
        yield
        return

    anker = anker_aus(roh)

    # `pydantic.v1.types` leitet Klassen von `datetime.date`/`datetime`
    # AB. Wird das Modul erst WAEHREND des gefrorenen Fensters importiert,
    # sind die Basisklassen bereits freezeguns `FakeDate`/`FakeDatetime` und
    # die Klassendefinition scheitert mit "metaclass conflict" -- ein
    # Artefakt des Messwerkzeugs, kein Befund. Deshalb vorher laden.
    import pydantic.v1.types  # noqa: F401

    from freezegun import freeze_time

    with freeze_time(anker, tick=True):
        yield

# ---------------------------------------------------------------------------
# CI-Rot 2026-10-22, Familie A: freezegun-Stapel nach jedem Test pruefen
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _freezegun_stapel_waechter(request):
    """Ein Test darf den globalen freezegun-Stapel nicht tiefer hinterlassen,
    als er ihn vorgefunden hat.

    Warum: ``freeze_time().start()`` legt den Zeitpunkt auf den Stapel, BEVOR
    es die Module patcht. Faellt eine Ausnahme mitten in diese Schleife (im CI
    das SIGALRM von pytest-timeout), laeuft kein ``stop()`` -- und jeder
    spaetere ``freeze_time`` haelt sich fuer verschachtelt und patcht nichts
    mehr: bereits geladene Testmodule lesen fortan die echte Wanduhr. So
    wurden am 2026-10-22 (run 39747019320) aus EINEM Timeout 136 Folge-
    Fehlschlaege. Mechanik und Rueckbau: ``tests/helpers/freezegun_stapel.py``.

    Der Lauf wird repariert UND laut (Warnung mit Test-Kennung) -- der
    verursachende Test ist ohnehin rot; die Folgetests sollen es nicht sein.
    """
    import warnings

    from tests.helpers.freezegun_stapel import reparieren, tiefe

    vorher = tiefe()
    yield
    nachher = tiefe()
    if nachher != vorher:
        reparieren(vorher)
        warnings.warn(
            f"freezegun-Stapel nach {request.node.nodeid} bei Tiefe {nachher} "
            f"statt {vorher} (unterbrochener freeze_time-Start, z. B. durch "
            f"pytest-timeout) -- auf {vorher} repariert, damit die Folgetests "
            f"eine gestellte Uhr behalten.",
            RuntimeWarning,
            stacklevel=1,
        )


# ---------------------------------------------------------------------------
# CI-Rot 2026-10-22, Familie B: Stub-Server der AlarmPruefstrecke beenden
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _pruefstrecken_server_beenden():
    """Nach jedem Test alle Stub-Server der ``AlarmPruefstrecke`` herunterfahren.

    Ohne diese Abschaltung ueberlebten die ``serve_forever``-Threads den Test
    (CI-Thread-Dump: >= 56 lebende Stubs) und brachten als Leerlauf-Dreher den
    GIL-gebundenen Rest des Laufs in die 30-s-Schranke von pytest-timeout.
    Der Helfer wird NICHT importiert, solange ihn kein Test geladen hat --
    sonst zahlte jeder der ~16.000 Tests seinen Import."""
    yield
    modul = sys.modules.get("tests.helpers.alarm_pruefstrecke")
    if modul is not None:
        modul.offene_server_beenden()
