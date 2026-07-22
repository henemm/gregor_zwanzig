# ensures the 'src' directory is on sys.path for imports like 'from app import ...'
import os
import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

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


_REPO_DATA_USERS = root / "data" / "users"


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

    Tests marked ``@pytest.mark.real_data_root`` or ``@pytest.mark.live``
    opt out — they deliberately read/write the real tree (contract tests).

    Issue #1265 Teil C (Verursacher-Befund): die Redirect-Fixture allein
    schützt nur Code-Pfade, die tatsächlich über ``app.loader`` gehen --
    direkte ``<repo>/data/users``-Pfade laufen vorbei. Der Wächter unten
    prüft deshalb zusätzlich am Test-Ende, dass unter dem ECHTEN
    ``<repo>/data/users`` keine neuen/geänderten Top-Level-Einträge
    entstanden sind, und FAILT den Test sonst mit Klartext-Hinweis.
    """
    if request.node.get_closest_marker(
        "real_data_root"
    ) or request.node.get_closest_marker("live"):
        yield
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
            "@pytest.mark.real_data_root / @pytest.mark.live setzen."
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
def _isolate_warn_calls_path(tmp_path_factory):
    """Issue #1348: die vom Warn-Egress-Zähler geschriebene JSONL-Datei
    ``services.official_alerts.warn_egress.WARN_CALLS_PATH`` (real
    ``data/diagnostics/warn_service_calls.jsonl``) für JEDEN Test auf eine
    Wegwerf-Datei im tmp-Bereich umlenken, damit KEIN Test die echte
    Diagnose-Datei verschmutzt.

    Vorbild: ``_isolate_data_root`` oben (Save/Redirect/Restore). Der Zähler
    wird u.a. indirekt über ``get_official_alerts_for_location`` /
    ``MeteoAlarmSource.fetch`` aus vielen Suiten ausgelöst, nicht nur aus den
    beiden #1348-Testdateien — deshalb greift die Umlenkung global und
    unbedingt (auch für ``live``/``staging``: die reale Diagnose-Datei soll
    NIE aus Tests wachsen).

    Wichtig für die Rücklese-Tests (AC-7/8/9 in
    ``test_warn_service_egress.py`` sowie die MeteoAlarm-Suite): setzen diese
    ihren EIGENEN ``monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", ...)``,
    so läuft dieser Per-Test-Override IM Test-Body — also NACH dieser
    Fixture-Einrichtung — und gewinnt. Nach dem Test stellt monkeypatch auf
    den hier gesetzten tmp-Wert zurück, diese Fixture danach auf das Original.
    """
    from services.official_alerts import warn_egress

    before = warn_egress.WARN_CALLS_PATH
    throwaway = tmp_path_factory.mktemp("warn_calls") / "warn_service_calls.jsonl"
    warn_egress.WARN_CALLS_PATH = throwaway
    try:
        yield
    finally:
        warn_egress.WARN_CALLS_PATH = before


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