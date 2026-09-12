# ensures the 'src' directory is on sys.path for imports like 'from app import ...'
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

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

    _ORIGINAL_DATA_ROOT = getattr(loader, "_DATA_ROOT", None)
    _SESSION_DATA_ROOT = str(tmp_path_factory.mktemp("gz-data-root-session"))
    loader._DATA_ROOT = _SESSION_DATA_ROOT
    yield
    loader._DATA_ROOT = _ORIGINAL_DATA_ROOT


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
    """
    before = _snapshot_repo_data_users()
    yield
    after = _snapshot_repo_data_users()
    if after != before:
        pytest.fail(
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
    """
    for src_file in sorted(_REAL_DATA_FIXTURE_SRC.rglob("*")):
        if not src_file.is_file():
            continue
        target = root / "data" / src_file.relative_to(_REAL_DATA_FIXTURE_SRC)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_file, target)

    for trips_json in sorted(_REPO_DATA_USERS.glob("*/trips/*.json")):
        briefings_dir = trips_json.parent.parent / "briefings"
        briefings_target = briefings_dir / trips_json.name
        if briefings_target.exists():
            continue
        trip = json.loads(trips_json.read_text(encoding="utf-8"))
        trip.setdefault("kind", "route")
        briefings_dir.mkdir(parents=True, exist_ok=True)
        briefings_target.write_text(
            json.dumps(trip, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _snapshot_repo_data_users() -> dict[str, int]:
    """Issue #1265 Teil C (F003-Fix, Adversary Fix-Loop 1): rekursiver
    Aggregat-Fingerprint statt reiner Top-Level-mtime -- EIN ``os.walk`` pro
    Snapshot (Performance), erkennt aber auch In-Place-Content-Mutationen
    bestehender Dateien (die Top-Level-Verzeichnis-mtime ändert sich NICHT,
    wenn eine bestehende Datei per ``write_text``/``open(..., 'w')``
    überschrieben wird -- Adversary-Repro)."""
    if not _REPO_DATA_USERS.exists():
        return {}
    file_count = 0
    max_mtime_ns = 0
    total_size = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(_REPO_DATA_USERS):
            for fname in filenames:
                try:
                    st = (Path(dirpath) / fname).stat()
                except OSError:
                    continue
                file_count += 1
                max_mtime_ns = max(max_mtime_ns, st.st_mtime_ns)
                total_size += st.st_size
    except OSError:
        return {}
    return {"file_count": file_count, "max_mtime_ns": max_mtime_ns, "total_size": total_size}


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

    before_snapshot = _snapshot_repo_data_users()
    yield
    loader._DATA_ROOT = before

    after_snapshot = _snapshot_repo_data_users()
    if after_snapshot != before_snapshot:
        pytest.fail(
            "Issue #1265 Teil C (F003-Fix): dieser Test hat unter dem "
            f"ECHTEN {_REPO_DATA_USERS} geschrieben (vorher: "
            f"{before_snapshot}, nachher: {after_snapshot}). "
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
    reset_telegram_rate_limit_for_tests()
    yield
    reset_telegram_rate_limit_for_tests()

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
