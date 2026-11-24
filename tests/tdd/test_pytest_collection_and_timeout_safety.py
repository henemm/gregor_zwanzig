"""Meta-Tests: pytest-Suite terminiert zuverlaessig + sammelt korrekt (#1210, S1).

Nachweise laufen ueber echte `pytest --collect-only`-Subprozesse (kein Mock,
keine Dateiinhalt-Greps) plus einem synthetischen, netzfreien Haenger fuer AC-1.
Spec: docs/specs/modules/rework_1210_testsuite_s1.md

AC-6 hat bewusst KEINE eigene Testfunktion: `imaplib.IMAP4_SSL(..., timeout=3)`
gegen eine nicht routbare Adresse schlaegt schon heute (Python-Stdlib-Verhalten,
unabhaengig von den B1-Dateien) in ca. 3s fehl -- kein Nachweis fuer eine
Aenderung. AC-6 gilt als durch AC-2/AC-7 mitabgedeckt: die B1-Dateien zaehlen
dort erst, wenn Marker UND `timeout=`-Parameter an ihren echten Aufrufen sitzen.

Erweiterung Scheibe 2a (#1211a): 22 Staging-Dialer (Liste A) bekommen einen
modul-weiten `pytest.mark.staging`, der sie aus der Standard-Selektion nimmt.
Spec: docs/specs/modules/rework_1211a_staging_marker.md

Erweiterung Scheibe 2b Batch 3 (#1211b): 13 K3-Dateien bekommen einen
email/live/staging-Marker (3 modul-weit, 10 nur auf den real dialenden
Tests/Klassen). Spec: docs/specs/modules/rework_1211b_rot_triage.md

Erweiterung Scheibe 2c (#1211c): 10 Dateien mit bislang modul-weitem
`pytestmark = pytest.mark.live` werden test-genau feingeschnitten (74
Netz-Sperre-Probe-gruene Tests + 2 aus test_issue_338 kommen in die
Standard-Selektion zurueck); 6 Voll-Dialer-Dateien bleiben unveraendert
modul-live. Spec: docs/specs/modules/rework_1211c_live_feinschnitt.md

#2240 (2026-09-10): der einzelne Rolling-Trip-Dialer aus #937
(test_issue_937_staging_rolling_trip.py) bekommt denselben `staging`-Marker
wie Liste A -- zusaetzlich aber einen eigenen Collect-Zeit-Socket-Nachweis
per Bootstrap-Subprozess, weil sein `skipif`-Ausdruck bislang schon beim
Einsammeln einen echten POST auf den Versand-Endpunkt absetzte (Klasse
#1477). Spec: docs/specs/modules/fix_2240_rolling_trip_test_versandsperre.md

#1708 B1 (2026-08-16): test_bug_338_openmeteo_call_counter.py wandert von
den 6 Voll-Dialern (_C2_KEEP_MODULE_LIVE) nach _C2_SPLIT_FILES. Erste
Messung (nur `--disable-socket`) ergab faelschlich 5 live/1 offline -- nach
Ruecksprache und gezielter Nachmessung je Test (`@pytest.mark.disable_socket`
+ erzwungener echter Provider statt FixtureProvider) zeigte sich: 3 Tests
(ac2_trend, ac2_preview, ac4) bestehen offline beweiskraeftig, weil
`_build_stage_trend`/`_build_report` mit Default `enrich_ensemble=True`
einen Ensemble-Spread-Fallback ausloesen, dessen `except Exception` breiter
faengt als der primaere Forecast-Call und den Log-Eintrag liefert. Die
verbleibenden 3 (ac1, ac2_alarm, ac3) rufen mit `enrich_ensemble=False`
direkt/ohne diesen Fallback und bleiben live. Nur noch 5 Voll-Dialer-Dateien.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

# #2806: Die modulweiten Fixtures starten `pytest --collect-only`-Subprozesse
# mit eigenen Grenzen (30-90 s); ein Test loest bis zu drei davon nacheinander
# aus. Die globale 30-s-Grenze aus pyproject.toml bricht das Fixture-Setup
# sonst ab, sobald das Einsammeln der ganzen Suite laenger als 30 s dauert.
# Tests mit eigenem @pytest.mark.timeout behalten ihren (naeheren) Wert.
pytestmark = pytest.mark.timeout(300)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Fix-Loop 1 (F001/F002, Adversary): 10 Dateien tragen weiterhin einen
# vollstaendigen Modul-Marker (jeder Test dialt); 1147 ist jetzt
# GEMISCHT -- nur die real dialenden Tests/Klassen tragen `@pytest.mark.email`,
# die restlichen Guard-Tests bleiben im Standardlauf.
# 684 traegt seit der #1196-Vermessung bewusst modul-weit `pytestmark =
# pytest.mark.email` (gehoert per Marker in den /e2e-verify-Lauf).
_FULL_B1_FILES = (
    "tests/tdd/test_issue_1113_partial_outage_guard.py",
    "tests/tdd/test_issue_1007_heute_voll_briefing.py",
    "tests/tdd/test_issue_1012_no_data_guard.py",
    "tests/tdd/test_issue_1009_1019_inbound_robustness.py",
    "tests/tdd/test_773_alert_e2e.py",
    "tests/tdd/test_952_onset_alert_e2e.py",
    "tests/tdd/test_issue_1087_trip_official_alerts.py",
    "tests/tdd/test_issue_1169_compare_alert_consumer.py",
    "tests/tdd/test_issue_972_974_975_tooling.py",
    "tests/tdd/test_issue_684_alert_email_guard.py",
)
_MIXED_B1_FILES = (
    "tests/tdd/test_issue_1147_resend_recipient_invariant.py",
)
_B1_FILES = _FULL_B1_FILES + _MIXED_B1_FILES
_FRIENDLY_FORMAT_FOOTGUN = "tests/e2e/test_e2e_friendly_format_config.py"
_GEOSPHERE_FILES = ("tests/test_geosphere.py", "tests/test_providers_base.py")
_TRIPS_DIR = _REPO_ROOT / "data" / "users" / "default" / "trips"

# Scheibe 2a (#1211a), Spec Liste A: 22 Staging-/Prod-Dialer, die einen
# modul-weiten `pytestmark = pytest.mark.staging` bekommen -- Marker
# verschiebt sie aus der Standard-Selektion, loescht keinen Test.
_STAGING_DIALER_FILES = (
    "tests/tdd/test_674_aktivitaetstyp_fahrrad.py",
    "tests/tdd/test_701_alerts_metrik_sync.py",
    "tests/tdd/test_702_alerts_mobile_parity.py",
    "tests/tdd/test_794_mobile_metric_label.py",
    "tests/tdd/test_bug_691_autosave_trip_new.py",
    "tests/tdd/test_bundle_d_785_yesterday_toggle.py",
    "tests/tdd/test_bundle_h_908_973_987_staging_auth.py",
    "tests/tdd/test_fix_698_validator_user_sync.py",
    "tests/tdd/test_issue_1010_1006_stille_fehler.py",
    "tests/tdd/test_issue_1020_tmp_cookie_perms.py",
    "tests/tdd/test_issue_1068_tier_model_display.py",
    # #3207: tests/tdd/test_issue_496_layout.py entfernt (tot, ADR-0109 Nr. 6
    # "Keine Vorschau": channel-consequence-*/channel-preview-block weg).
    "tests/tdd/test_issue_576_token_values.py",
    "tests/tdd/test_issue_577_atoms_values.py",
    "tests/tdd/test_issue_675_stage_start_time.py",
    "tests/tdd/test_issue_692_telegram_disabled_unconfigured.py",
    "tests/tdd/test_issue_727_trips_null_safety.py",
    "tests/tdd/test_issue_830_radar_alert_validator.py",
    "tests/tdd/test_issue_846_alert_preset_e2e.py",
    "tests/tdd/test_prod_selftest_564.py",
    "tests/tdd/test_prod_selftest_730.py",
    "tests/tdd/test_ssr_cache_headers.py",
)

# #2240 (2026-09-10): einzelner Rolling-Trip-Dialer (Issue #937) -- eigener
# Eintrag statt Aufnahme in _STAGING_DIALER_FILES, weil er zusaetzlich einen
# Collect-Zeit-Socket-Nachweis (Bootstrap-Subprozess) braucht, den die 22
# Dateien aus Liste A nicht brauchen.
_ROLLING_TRIP_DIALER = "tests/tdd/test_issue_937_staging_rolling_trip.py"

# Batch 3 (#1211b), K3-Tabelle: 3 Dateien bekommen einen modul-weiten Marker
# (jeder Test dialt) -- je (Pfad, Marker)-Paar, 2x live + 1x staging.
_B3_MODULE_MARKED = (
    ("tests/tdd/test_account_page.py", "live"),
    ("tests/tdd/test_feature_770_inca_nowcast_fix.py", "live"),
    ("tests/tdd/test_issue_934_wizard_schedule.py", "staging"),
)

# Batch 3 (#1211b), K3-Tabelle: 9 Dateien bekommen nur auf den real
# dialenden Tests/Klassen einen Marker (Rest bleibt im Standardlauf) -- je
# (Pfad, Marker)-Paar. #2521 S2 (ADR-0092): test_channel_test_button.py entfernt
# -- der einzige email-dialende Test wurde durch einen netzfreien ersetzt.
_B3_PARTIAL_MARKED = (
    ("tests/tdd/test_issue_1069_tier_channel_gating.py", "staging"),
    ("tests/tdd/test_issue_1037_massif_closure.py", "live"),
    ("tests/tdd/test_issue_1142_geosphere_direct_fallback.py", "live"),
    ("tests/tdd/test_issue_645_telegram_outputerror_arity.py", "live"),
    ("tests/tdd/test_issue_731_unified_commands.py", "live"),
    ("tests/tdd/test_scheduler_triggers.py", "email"),
    ("tests/tdd/test_issue_608_sms_seven_io.py", "live"),
    ("tests/tdd/test_fix_853_842_837_tooling_gates.py", "live"),
    ("tests/tdd/test_issue_1035_vigilance_source.py", "live"),
)

# Spec Liste C: urspruenglich 6 Dateien OHNE echten Netzcall -- bleiben
# unveraendert in der Standard-Selektion (Regressions-Wächter gegen
# versehentliche Mit-Markierung). test_epic_404_phase2_ist_screenshots.py
# entfernt (#1211b Batch 1, Gruppe K6: komplett geloescht -- Datei existiert
# nicht mehr, stale Referenz auf diesen Wächter durch Batch 3 bereinigt).
_OFFLINE_KEEP_FILES = (
    "tests/tdd/test_prod_selftest_internal_url_skip.py",
    "tests/tdd/test_staging_gate.py",
    "tests/tdd/test_staging_gate_verdict_merge.py",
    "tests/tdd/test_issue_1148_prod_send_gate.py",
    "tests/tdd/test_issue_339_verify_timing.py",
)

# Scheibe 2c (#1211c): 10 Dateien mit bislang modul-weitem live-Marker
# werden test-genau feingeschnitten -- je (Pfad, min_standard, Marker)-Tripel.
# min_standard = grün-Probe-Anteil + ggf. Drift-Fixes (multi_day_trend 4,
# story3 5); test_issue_338 korrigiert auf 2 (nur ac4 + call_log kommen
# zurueck, ac2/ac3 bleiben live).
_C2_SPLIT_FILES = (
    # 19 statt 21 (#3237): test_trend_rendering_{html,plain}_two_lines als
    # reiner Altpfad (multi_day_trend_reports als Schalter) geloescht.
    ("tests/integration/test_multi_day_trend.py", 19, "live"),
    ("tests/integration/test_trip_segment_weather.py", 9, "live"),
    ("tests/tdd/test_forecast_confidence_backend.py", 16, "live"),
    ("tests/unit/test_openmeteo_endpoint_routing.py", 9, "live"),
    # 5 statt 7: zwei weitere fail-soft/vakuum-Tests nach Adversary-F001 live-markiert (Orchestrierer-Freigabe Fix-Loop 1, 2026-07-18)
    ("tests/unit/test_metric_availability_probe.py", 5, "live"),
    ("tests/unit/test_uv_air_quality.py", 1, "live"),
    # 13 statt 14 (2026-07-18): der live-Versandtest blieb email+live. #1405 S4b:
    # dieser Test (test_scheduler_send_reports) ist mit send_reports entfallen;
    # er war live-markiert und zaehlte NICHT zum Standardlauf -- gemessen
    # 2026-10-26: Standardlauf 13 (unveraendert), `-m live` 3 -> 2.
    ("tests/e2e/test_e2e_story3_reports.py", 13, "live"),
    ("tests/tdd/test_go_api_setup.py", 5, "live"),
    ("tests/tdd/test_snowgrid.py", 1, "live"),
    ("tests/tdd/test_issue_338_go_geosphere_counter.py", 2, "live"),
    # #1708 B1: von _C2_KEEP_MODULE_LIVE hierher verschoben -- die dortige
    # Begruendung ("Voll-Dialer, 100% Netzcall", #1211 Scheibe 2c) war
    # zirkulaer gemessen (unter dem eigenen live-Marker, der den
    # Offline-Fixture-Modus abschaltet, conftest.py:25-29).
    #
    # Erste Nachmessung (nur `--disable-socket -o addopts=`) ergab
    # faelschlich nur 1 offline-faehigen Test (ac4) -- diese Messung deckte
    # nicht auf, dass der Fixture-Modus die eigentliche Ursache war (siehe
    # #1708-B1-Ruecksprache). Zweite, gezielte Messung je Einzeltest (echter
    # Provider erzwungen via `monkeypatch.delenv("GZ_TEST_FIXTURE_DIR")` +
    # `@pytest.mark.disable_socket` statt globalem CLI-Flag) zeigt: 3 Tests
    # bestehen offline beweiskraeftig -- ac2_trend/ac2_preview (Default
    # `enrich_ensemble=True` loest zusaetzlich zum primaeren Forecast-Call
    # einen Ensemble-Spread-Fallback aus, dessen `except Exception` breiter
    # faengt als `except httpx.RequestError` und darum trotz gesperrtem
    # Socket protokolliert) sowie ac4 (reine Dateiarbeit). Die restlichen 3
    # (ac1, ac2_alarm, ac3) rufen mit `enrich_ensemble=False` (Bug #288,
    # Quotenschutz) OHNE diesen Fallback -- der primaere Call scheitert dort
    # ungeloggt (httpx erkennt die pytest-socket-Exception nicht als
    # `httpx.RequestError`) und bleibt live. Details je Test:
    # test_bug_338_openmeteo_call_counter.py.
    ("tests/tdd/test_bug_338_openmeteo_call_counter.py", 3, "live"),
)

# Scheibe 2c: 5 Voll-Dialer-Dateien (per Probe/Code 100% Netzcall) behalten
# ihren Modul-Marker unveraendert -- Regressions-Waechter gegen
# versehentliches Mit-Zurueckholen. test_bug_338_openmeteo_call_counter.py
# ist #1708 B1 nach _C2_SPLIT_FILES gewandert (dort feingeschnitten, ein
# Test bleibt im Standardlauf).
_C2_KEEP_MODULE_LIVE = (
    "tests/integration/test_snapshot_plausibility.py",
    "tests/tdd/test_geosphere_parsing.py",
    "tests/integration/test_segment_weather_metrics.py",
    "tests/integration/test_segment_weather_cache.py",
    "tests/integration/test_cli_wintersport.py",
)

# addopts liefert bereits ein "-q" -> Quiet-Level 2 -> kompaktes "pfad: N"-Format
# statt einzelner Test-IDs (empirisch verifiziert, kein Rateversuch).
_COLLECTED_LINE = re.compile(r"^(tests/\S+\.py): (\d+)$", re.MULTILINE)


# #2240: Bootstrap-Skript fuer einen eigenstaendigen Python-Prozess, der
# `socket.socket.connect`/`connect_ex` VOR `import pytest` patcht -- Nachweis,
# dass die Rolling-Trip-Collection keinen Socket oeffnet (AC-3/AC-4). Laeuft
# per `python -c <script> <pytest_args...>`; sys.argv[1:] sind dann die
# pytest_args. `{extra_setup}`/`{raise_expr}` werden je Variante gefuellt.
_SOCKET_BOOTSTRAP_TEMPLATE = """
import socket

{extra_setup}

def _blocked_connect(self, *a, **k):
    raise {raise_expr}

def _blocked_connect_ex(self, *a, **k):
    raise {raise_expr}

socket.socket.connect = _blocked_connect
socket.socket.connect_ex = _blocked_connect_ex

import sys
import pytest
sys.exit(pytest.main(sys.argv[1:]))
"""

# Variante A (AC-3): Collect-Zeit-Egress muss als Collection-Error sichtbar
# werden, nicht still geschluckt -- RuntimeError-Unterklasse statt OSError,
# damit httpx sie NICHT als httpx.ConnectError mappt.
_BOOTSTRAP_COLLECT_TIME_EGRESS = _SOCKET_BOOTSTRAP_TEMPLATE.format(
    extra_setup="class _CollectTimeEgress(RuntimeError):\n    pass",
    raise_expr='_CollectTimeEgress("kein Netzzugriff waehrend der Collection erlaubt")',
)

# Variante B (AC-4): OSError, die httpx zu httpx.ConnectError mappt --
# simuliert Port 8001 zu, der Testkoerper faengt das per pytest.skip() ab.
_BOOTSTRAP_CONNECTION_REFUSED = _SOCKET_BOOTSTRAP_TEMPLATE.format(
    extra_setup="",
    raise_expr='ConnectionRefusedError(111, "blocked")',
)


# #3317: Plugin fuer den Sammel-Kindprozess. Schreibt je Test (auch abgewaehlte)
# die Marker und die Auswahl nach `-m` mit -- nie im Testprozess, dort gaelten
# dessen eigene Optionen (CI: `--ignore`).
_PLUGIN = "gz_mitschreiber"
_PLUGIN_QUELLE = '''
import json
import os

_items = []


def pytest_itemcollected(item):
    _items.append(item)


def pytest_collection_finish(session):
    with open(os.environ["GZ_SAMMLUNG_ZIEL"], "w", encoding="utf-8") as ziel:
        json.dump({
            "marker": {i.nodeid: sorted({m.name for m in i.iter_markers()}) for i in _items},
            "gewaehlt": [i.nodeid for i in session.items],
        }, ziel)
'''

# Nutzer der einen Voll-Sammlung laufen unter `--dist loadgroup` im selben
# Worker. Nicht "echtdaten": die Sammlung allein dauert laenger als 20 s (Spec
# #3317) und hielte die serielle Echtdaten-Gruppe auf.
_sammlungsgruppe = pytest.mark.xdist_group("sammlung")


def _umgebung(**zusatz: str) -> dict[str, str]:
    """Ohne PYTEST_* des aeusseren Laufs (xdist-Worker, PYTEST_TIMEOUT, ...)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")} | zusatz


def _collect(*extra_args: str, timeout: int, **umgebung: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra_args]
    return subprocess.run(
        cmd, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=timeout,
        env=_umgebung(**umgebung),
    )


def _kindlauf(
    tmp_path: Path, rumpf: str, *optionen: str, konfiguration: Path = _PYPROJECT,
) -> subprocess.CompletedProcess:
    """Fuehrt einen einzelnen Wegwerf-Test mit der Konfiguration aus."""
    datei = tmp_path / "test_kind.py"
    datei.write_text(f"import time\n\n\ndef test_kind():\n    {rumpf}\n", encoding="utf-8")
    cmd = [sys.executable, "-m", "pytest", "-c", str(konfiguration), *optionen, str(datei)]
    return subprocess.run(
        cmd, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60, env=_umgebung(),
    )


def _wirksames_limit(konfiguration: Path, tmp_path: Path) -> float:
    """Das Limit, mit dem pytest-timeout im Kindprozess den Wecker stellt."""
    ziel = tmp_path / "limit.txt"
    ziel.unlink(missing_ok=True)
    (tmp_path / "conftest.py").write_text(
        "def pytest_timeout_set_timer(item, settings):\n"
        f"    open({str(ziel)!r}, 'w').write(str(settings.timeout))\n",
        encoding="utf-8",
    )
    res = _kindlauf(tmp_path, "pass", konfiguration=konfiguration)
    assert res.returncode == 0, res.stdout + res.stderr
    return float(ziel.read_text())


def _haenger_lauf(tmp_path: Path, *, limit_s: int, haenger_s: int) -> subprocess.CompletedProcess:
    return _kindlauf(tmp_path, f"time.sleep({haenger_s})", f"--timeout={limit_s}")


def _collected_counts(output: str) -> dict[str, int]:
    """Datei -> Anzahl gesammelter Tests (0 = Datei fehlt komplett)."""
    return {path: int(n) for path, n in _COLLECTED_LINE.findall(output)}


def _je_datei(kennungen) -> Counter:
    return Counter(k.split("::")[0] for k in kennungen)


@pytest.fixture(scope="module", autouse=True)
def prozessstarts():
    """#3317 AC-1: alle Prozessstarts dieser Datei mitschreiben (durchreichend)."""
    befehle: list[list[str]] = []

    class _Mitschreiber(subprocess.Popen):
        def __init__(self, args, *rest, **kwargs):
            if isinstance(args, (list, tuple)):
                befehle.append([str(a) for a in args])
            super().__init__(args, *rest, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess, "Popen", _Mitschreiber)
        yield befehle


def _voll_sammlungen(befehle: list[list[str]]) -> list[list[str]]:
    """Sammel-Laeufe ohne benannte Testdatei (= ganze Suite)."""
    return [
        b for b in befehle
        if "--collect-only" in b and not any(a.split("::")[0].endswith(".py") for a in b)
    ]


@pytest.fixture(scope="module")
def sammlung(tmp_path_factory) -> SimpleNamespace:
    """#3317: die EINE Voll-Sammlung (Standardauswahl) der Datei. Gesamt, Auswahl
    und Marker stammen aus dem Mitschreib-Plugin; fehlt dessen Ergebnis oder
    weicht es von pytests eigener Ausgabe ab, sind alle Nutzer rot."""
    ordner = tmp_path_factory.mktemp("sammlung")
    (ordner / f"{_PLUGIN}.py").write_text(_PLUGIN_QUELLE, encoding="utf-8")
    ziel = ordner / "ergebnis.json"
    lauf = _collect(
        "-p", _PLUGIN, timeout=90, GZ_SAMMLUNG_ZIEL=str(ziel),
        PYTHONPATH=os.pathsep.join(filter(None, [str(ordner), os.environ.get("PYTHONPATH")])),
    )
    assert ziel.exists(), lauf.stdout[-2000:] + lauf.stderr[-2000:]
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    marker, gewaehlt = daten["marker"], set(daten["gewaehlt"])
    assert gewaehlt and gewaehlt < set(marker), "Mitschrift leer oder ohne abgewaehlte Tests"
    assert _collected_counts(lauf.stdout) == _je_datei(gewaehlt)
    return SimpleNamespace(
        lauf=lauf, gesamt=set(marker), gewaehlt=gewaehlt,
        mit_marker=lambda name: {k for k, namen in marker.items() if name in namen},
    )


@pytest.fixture(scope="module")
def default_collect(sammlung) -> subprocess.CompletedProcess:
    """Der Standardlauf-Collect selbst: Exit-Code und pytests eigene Ausgabe."""
    return sammlung.lauf


@_sammlungsgruppe
def test_default_selection_excludes_b1_live_leak_files(default_collect, sammlung):
    """GIVEN 10 vollstaendig markierte B1-Dateien + 1 gemischt markierte
    (1147 -- nur real dialende Tests/Klassen) WHEN Standardlauf ohne `-m`
    sammelt THEN fehlen die 10 vollen Dateien komplett UND die gemischte
    partitioniert sich exakt in (Standardlauf-Rest, `-m email`-Dialer) --
    beide Teile nicht-leer, zusammen == marker-neutraler Gesamt-Count (AC-2)."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    leaked = {f: default_counts[f] for f in _FULL_B1_FILES if default_counts.get(f, 0) > 0}
    assert not leaked, f"Voll markierte B1-Dateien duerfen im Standardlauf nicht erscheinen: {leaked}"

    email_counts = _je_datei(sammlung.mit_marker("email"))
    total_counts = _je_datei(sammlung.gesamt)
    for f in _MIXED_B1_FILES:
        std_n, email_n, total_n = (
            default_counts.get(f, 0), email_counts.get(f, 0), total_counts.get(f, 0),
        )
        assert std_n > 0, f"{f}: gemischte Datei muss Rest-Tests im Standardlauf behalten, hat aber 0"
        assert email_n > 0, f"{f}: gemischte Datei muss dialende Tests unter `-m email` zeigen, hat aber 0"
        assert std_n + email_n == total_n, (
            f"{f}: Standardlauf ({std_n}) + `-m email` ({email_n}) muss den "
            f"marker-neutralen Gesamt-Count ({total_n}) exakt ergeben -- sonst "
            f"geht ein Test verloren oder wird doppelt gezaehlt."
        )


# Issue #3209: liest mtimes im ECHTEN data/users-Baum -- unter xdist in der
# seriellen Echtdaten-Gruppe (dort entfernt ein Gruppen-Test die
# materialisierten Kopien kurzzeitig).
@pytest.mark.xdist_group("echtdaten")
def test_friendly_format_footgun_not_collected_by_default():
    """GIVEN test_e2e_friendly_format_config.py (Docstring: NICHT als pytest)
    WHEN Standardselektion sammelt THEN keine Test-ID (AC-3, Collection-Teil)
    UND genau dieser Collect-Lauf veraendert keine mtime unter
    data/users/default/trips/*.json (AC-3, Mutations-Teil). Eigene Sammlung,
    weil nur die Gruppe "echtdaten" den Baum ungestoert sieht (#3317)."""
    def zeitstempel() -> dict[Path, float]:
        return {p: p.stat().st_mtime for p in sorted(_TRIPS_DIR.glob("*.json"))}

    before = zeitstempel()
    res = _collect("-p", f"no:{_PLUGIN}", timeout=90)  # fuer den Zaehler erkennbar
    after = zeitstempel()
    assert res.returncode == 0, res.stderr
    collected = _collected_counts(res.stdout)
    assert collected and _FRIENDLY_FORMAT_FOOTGUN not in collected, (
        f"{_FRIENDLY_FORMAT_FOOTGUN} darf im Standardlauf nicht erscheinen "
        f"(mutiert sonst data/users/default/trips/*.json)."
    )
    assert before == after, (
        f"Ein --collect-only-Lauf darf data/users/default/trips/*.json nicht "
        f"anfassen: vorher={before} nachher={after}"
    )
    if not before:
        pytest.skip(f"{_TRIPS_DIR} ohne *.json -- mtime-Nachweis uebersprungen")


@_sammlungsgruppe
def test_full_suite_collection_still_exits_zero(default_collect):
    """GIVEN Marker-Registry in pyproject.toml WHEN volle Suite per
    `--collect-only -q` sammelt THEN Exit 0, keine ERROR-Zeilen (Regressions-
    waechter -- darf als einziger heute schon gruen sein, AC-8)."""
    assert default_collect.returncode == 0, default_collect.stderr
    assert "ERROR" not in default_collect.stdout, default_collect.stdout


@_sammlungsgruppe
def test_email_marker_run_still_collects_b1_files(default_collect, sammlung):
    """GIVEN `-m email` wird bewusst aufgerufen WHEN alle 11 B1-Dateien
    (voll oder teilweise) markiert sind THEN erscheint jede mit mindestens
    einem Test -- Marker verschiebt, loescht nicht (AC-7)."""
    assert default_collect.returncode == 0, default_collect.stderr
    email_counts = _je_datei(sammlung.mit_marker("email"))
    missing = sorted(f for f in _B1_FILES if email_counts.get(f, 0) == 0)
    assert not missing, f"B1-Dateien fehlen unter `-m email`: {missing}"


@_sammlungsgruppe
def test_default_selection_excludes_staging_dialers(default_collect):
    """GIVEN 22 Staging-/Prod-Dialer aus Liste A (#1211a) WHEN die
    Standard-Selektion `-m 'not email and not live and not staging'` sammelt
    THEN erscheint KEINE der 22 Dateien mit einem gesammelten Test -- jede
    deselektiert (AC-1). Schlaegt heute fehl, weil die Dateien noch keinen
    `pytest.mark.staging` tragen."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    leaked = {
        f: default_counts[f] for f in _STAGING_DIALER_FILES if default_counts.get(f, 0) > 0
    }
    assert not leaked, f"Staging-Dialer duerfen im Standardlauf nicht erscheinen: {leaked}"


@_sammlungsgruppe
@pytest.mark.staging
def test_staging_marker_run_still_collects_dialers(default_collect, sammlung):
    """GIVEN `-m staging` wird bewusst aufgerufen WHEN alle 22 Dialer aus
    Liste A markiert sind THEN erscheint jede Datei mit mindestens einem
    gesammelten Test -- der Marker verschiebt sie nur, loescht keinen Test
    (AC-2). Schlaegt heute fehl, weil der Marker noch fehlt (0 gesammelt).
    Host-gebunden (#1196 Batch 6/7): 1010_1006 skippt modul-weit ohne
    validator.env -- die Invariante gilt nur auf dem Server (Staging-Lane)."""
    assert default_collect.returncode == 0, default_collect.stderr
    staging_counts = _je_datei(sammlung.mit_marker("staging"))
    missing = sorted(f for f in _STAGING_DIALER_FILES if staging_counts.get(f, 0) == 0)
    assert not missing, f"Staging-Dialer fehlen unter `-m staging`: {missing}"


@_sammlungsgruppe
@pytest.mark.staging
def test_offline_files_remain_in_default_selection(default_collect):
    """GIVEN 6 Offline-Kern-Dateien aus Liste C (kein echter Netzcall) WHEN
    die Standard-Selektion sammelt THEN bleiben alle 6 weiterhin gesammelt --
    keine wird versehentlich mit-markiert (AC-3). Regressions-Waechter --
    darf schon heute gruen sein (analog AC-8 im Bestand).
    Host-gebunden (#1196 Batch 6/7): 1148 skippt modul-weit, wenn das
    Hook-Plugin nicht importierbar ist -- die Invariante gilt nur auf dem
    Server (Staging-Lane)."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    missing = sorted(f for f in _OFFLINE_KEEP_FILES if default_counts.get(f, 0) == 0)
    assert not missing, f"Offline-Dateien fehlen im Standardlauf: {missing}"


@_sammlungsgruppe
def test_b3_module_files_excluded_from_default(default_collect, sammlung):
    """GIVEN 3 Batch-3-Dateien (#1211b) mit Modul-Marker (2x live, 1x staging)
    WHEN der Standardlauf sammelt THEN fehlen alle 3 komplett, erscheinen aber
    unter ihrem jeweiligen Marker mit mindestens einem Test (Muster Scheibe
    2a). Schlaegt heute fehl, weil die Dateien noch keinen Marker tragen --
    sie erscheinen also weiterhin im Standardlauf statt unter ihrem Marker."""
    assert default_collect.returncode == 0, default_collect.stderr

    default_counts = _collected_counts(default_collect.stdout)
    marker_counts = {m: _je_datei(sammlung.mit_marker(m)) for m in ("live", "staging")}

    leaked = {f: default_counts[f] for f, _ in _B3_MODULE_MARKED if default_counts.get(f, 0) > 0}
    assert not leaked, f"Modul-markierte Batch-3-Dateien duerfen im Standardlauf nicht erscheinen: {leaked}"

    missing = sorted(f for f, marker in _B3_MODULE_MARKED if marker_counts[marker].get(f, 0) == 0)
    assert not missing, f"Modul-markierte Batch-3-Dateien fehlen unter ihrem Marker: {missing}"


@_sammlungsgruppe
def test_b3_partial_files_partition(default_collect, sammlung):
    """GIVEN 9 Batch-3-Dateien (#1211b) mit Teil-Marker (nur real dialende
    Tests/Klassen) WHEN Standardlauf und markereigener Lauf gemeinsam
    betrachtet werden THEN hat jede Datei im Standardlauf WENIGER Tests als
    marker-neutral gesammelt (Partitionsnachweis) UND Standardlauf +
    eigener Marker == marker-neutraler Gesamt-Count (Muster
    test_default_selection_excludes_b1_live_leak_files). Schlaegt heute fehl,
    weil noch kein Teil-Marker sitzt -- Standardlauf-Count == Gesamt-Count."""
    assert default_collect.returncode == 0, default_collect.stderr

    default_counts = _collected_counts(default_collect.stdout)
    marker_counts = {m: _je_datei(sammlung.mit_marker(m)) for m in ("live", "email", "staging")}
    total_counts = _je_datei(sammlung.gesamt)

    for f, marker in _B3_PARTIAL_MARKED:
        std_n = default_counts.get(f, 0)
        marker_n = marker_counts[marker].get(f, 0)
        total_n = total_counts.get(f, 0)
        assert total_n > 0, f"{f}: marker-neutraler Gesamt-Count ist 0 -- Collect kaputt?"
        assert marker_n > 0, f"{f}: Teil-markierte Datei muss dialende Tests unter `-m {marker}` zeigen, hat aber 0"
        assert std_n < total_n, (
            f"{f}: Standardlauf ({std_n}) muss kleiner als der marker-neutrale "
            f"Gesamt-Count ({total_n}) sein -- sonst ist noch kein Teil-Marker wirksam."
        )
        assert std_n + marker_n == total_n, (
            f"{f}: Standardlauf ({std_n}) + `-m {marker}` ({marker_n}) muss den "
            f"marker-neutralen Gesamt-Count ({total_n}) exakt ergeben -- sonst "
            f"geht ein Test verloren oder wird doppelt gezaehlt."
        )


def test_1010_1006_keeps_timeout_marker_alongside_staging():
    """GIVEN test_issue_1010_1006_stille_fehler.py trug vor der Aenderung
    `pytestmark = pytest.mark.timeout(180)` WHEN der staging-Marker ergaenzt
    wird THEN bleibt der timeout(180)-Marker erhalten UND `staging` ist
    zusaetzlich aktiv -- pytestmark ist danach eine Liste beider Marker
    (AC-5). Echte Modul-Introspektion per importlib, kein Datei-Grep. Der
    Import selbst loest keinen Netzcall aus: alle `page.goto(...)`-Aufrufe
    liegen ausschliesslich in Funktionskoerpern (_ui_login etc.), Modulebene
    laedt nur eine lokale Datei (_load_validator_env())."""
    mod = importlib.import_module("tests.tdd.test_issue_1010_1006_stille_fehler")
    marks = mod.pytestmark
    if not isinstance(marks, (list, tuple)):
        marks = [marks]

    timeout_marks = [m for m in marks if m.name == "timeout"]
    assert timeout_marks, f"timeout-Marker fehlt komplett: {marks}"
    assert timeout_marks[0].args == (180,), f"timeout-Marker-Args veraendert: {timeout_marks[0].args}"

    staging_marks = [m for m in marks if m.name == "staging"]
    assert staging_marks, f"staging-Marker fehlt -- pytestmark hat nur: {marks}"


def test_geosphere_and_providers_base_pass_in_default_selection():
    """GIVEN beide Dateien laufen nachweislich ohne Netz WHEN Standardlauf sie
    ausfuehrt THEN alle Tests PASSED, keiner SKIPPED/DESELECTED (AC-5)."""
    res = subprocess.run(
        [sys.executable, "-m", "pytest", *_GEOSPHERE_FILES, "-v"],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, f"rc={res.returncode} {res.stdout[-1500:]}"
    assert "deselected" not in res.stdout, res.stdout[-800:]
    assert "skipped" not in res.stdout, res.stdout[-800:]


@pytest.mark.staging
def test_811_gate_test_skips_when_hook_missing(tmp_path):
    """GIVEN `.claude/hooks/renderer_mail_gate.py` ist nicht auffindbar (z. B.
    Plugin unter anderem OS-Nutzer unsichtbar) WHEN test_issue_811_renderer_gate.py
    gesammelt wird THEN kein Collection-Error, sondern erkennbarer Skip (AC-4).
    Host-gebunden (#1196 Batch 6/7): die Gegenprobe setzt einen importierbaren
    Hook voraus -- der ist nur auf dem Server gegeben (Staging-Lane)."""
    src = _REPO_ROOT / "tests" / "tdd" / "test_issue_811_renderer_gate.py"
    target_dir = tmp_path / "tests" / "tdd"
    target_dir.mkdir(parents=True)
    copy = target_dir / "test_issue_811_renderer_gate.py"
    shutil.copy(src, copy)  # bewusst OHNE .claude/hooks/renderer_mail_gate.py

    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(copy)],
        capture_output=True, text=True, timeout=30,
    )
    assert res.returncode in (0, 5), f"rc={res.returncode} {res.stdout} {res.stderr}"
    assert "ERROR" not in res.stdout, res.stdout

    control = _collect(str(src), timeout=30)  # Gegenprobe: Hook vorhanden
    assert control.returncode == 0, control.stderr


@_sammlungsgruppe
def test_c2_returned_tests_in_default_selection(default_collect, sammlung):
    """GIVEN die 11 Scheibe-2c/#1708-B1-teilgeschnittenen Dateien (74
    Netz-Sperre-Probe-gruene Tests + 2 aus test_issue_338 + 3 aus
    test_bug_338, je Datei feinsortiert) WHEN Standardlauf und `-m
    live`-Lauf gemeinsam betrachtet werden THEN zeigt jede Datei im
    Standardlauf EXAKT die erwartete Zahl (#1708 B1 Adversary F001: eine
    Untergrenze faengt eine Verkleinerung des Tabellenwerts nicht) UND
    Standardlauf + `-m live` == marker-neutraler Gesamt-Count
    (Partitionsnachweis, Muster test_b3_partial_files_partition) (AC-1/AC-5/AC-8).
    Schlaegt heute fehl, weil alle 11 Dateien noch den kompletten
    Modul-Marker tragen -- der Standardlauf zeigt fuer jede 0 Tests statt
    der erwarteten Zahl."""
    assert default_collect.returncode == 0, default_collect.stderr

    default_counts = _collected_counts(default_collect.stdout)
    marker_counts = {"live": _je_datei(sammlung.mit_marker("live"))}
    total_counts = _je_datei(sammlung.gesamt)

    for f, expected_standard, marker in _C2_SPLIT_FILES:
        std_n = default_counts.get(f, 0)
        marker_n = marker_counts[marker].get(f, 0)
        total_n = total_counts.get(f, 0)
        assert total_n > 0, f"{f}: marker-neutraler Gesamt-Count ist 0 -- Collect kaputt?"
        # #1708 B1 Adversary F001: EXAKT statt `>=` -- eine Untergrenze faengt
        # die eigentliche Mutation nicht (Tabellenwert runter auf 1 bei real 3
        # gesammelten Tests blieb gruen). Gemessen 2026-08-16: `==` haelt fuer
        # ALLE bestehenden Eintraege (kein zweiter, laxerer Waechter auf
        # derselben Konstante noetig) -- die Tabellenwerte SIND bereits die
        # exakten Standardlauf-Counts, nicht bloss Untergrenzen.
        assert std_n == expected_standard, (
            f"{f}: Standardlauf zeigt {std_n} Tests, erwartet EXAKT "
            f"{expected_standard} zurueckgeholte Tests."
        )
        assert std_n + marker_n == total_n, (
            f"{f}: Standardlauf ({std_n}) + `-m {marker}` ({marker_n}) muss den "
            f"marker-neutralen Gesamt-Count ({total_n}) exakt ergeben -- sonst "
            f"geht ein Test verloren oder wird doppelt gezaehlt."
        )


@_sammlungsgruppe
def test_c2_full_live_files_stay_excluded(default_collect):
    """GIVEN die 5 Voll-Dialer-Dateien (per Netz-Sperre-Probe bzw. Code-Beleg
    100% Netzcall: snapshot_plausibility, geosphere_parsing,
    segment_weather_metrics, segment_weather_cache, cli_wintersport)
    WHEN der Standardlauf sammelt THEN bleiben alle 5 unveraendert bei 0
    gesammelten Tests -- kein versehentliches Mit-Zurueckholen (AC-2,
    Regressions-Waechter, Muster test_offline_files_remain_in_default_selection).
    Darf schon heute gruen sein -- die Dateien tragen bereits ihren
    Modul-Marker und sind davon durch Scheibe 2c nicht betroffen. bug_338
    ist #1708 B1 nach _C2_SPLIT_FILES gewandert (test_c2_returned_tests_
    in_default_selection deckt sie jetzt ab)."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    leaked = {
        f: default_counts[f] for f in _C2_KEEP_MODULE_LIVE if default_counts.get(f, 0) > 0
    }
    assert not leaked, f"Voll-Dialer-Dateien duerfen im Standardlauf nicht auftauchen: {leaked}"


@_sammlungsgruppe
@pytest.mark.parametrize("marker,datei", [
    # Gemischte Dateien: nur ein Teil traegt den Marker, die Auswahl ist also
    # weder leer noch die ganze Datei.
    ("email", "tests/tdd/test_issue_1147_resend_recipient_invariant.py"),
    ("live", "tests/tdd/test_issue_608_sms_seven_io.py"),
    ("staging", "tests/tdd/test_issue_1069_tier_channel_gating.py"),
])
def test_marker_auswahl_der_ableitung_deckt_sich_mit_pytest(sammlung, marker, datei):
    """#3317 AC-2: Given die Ableitung aus der einen Sammlung, When pytest die
    Datei wirklich mit `-m <marker>` sammelt (addopts bleibt wirksam, die
    Kommandozeile ersetzt deren Auswahl), Then nennt es dieselben Kennungen.
    `-v` hebt ein `-q` auf, damit Kennungen statt Zahlen erscheinen. Nur sammeln,
    nie ausfuehren."""
    res = _collect("-v", "-m", marker, datei, timeout=90)
    assert res.returncode == 0, res.stdout + res.stderr
    von_pytest = {ln for ln in res.stdout.splitlines() if ln.startswith(f"{datei}::")}
    alle = {i for i in sammlung.gesamt if i.startswith(f"{datei}::")}
    abgeleitet = {i for i in sammlung.mit_marker(marker) if i.startswith(f"{datei}::")}
    assert von_pytest and von_pytest < alle, "Beleg-Datei muss gemischt markiert sein"
    assert abgeleitet == von_pytest


def test_wirksames_limit_aus_der_echten_konfiguration_ist_30(tmp_path):
    """#3317 AC-3 (a): Given die echte pyproject.toml, When ein Kindprozess
    einen Test ohne eigenen Marker startet, Then meldet pytest-timeout 30 s.
    Gegenprobe: eine Kopie mit 300 meldet 300 -- die Messung liest wirklich die
    Konfiguration und ist nicht fest verdrahtet."""
    assert _wirksames_limit(_PYPROJECT, tmp_path) == 30.0

    kopie = tmp_path / "pyproject.toml"
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert text.count("\ntimeout = 30\n") == 1
    kopie.write_text(text.replace("\ntimeout = 30\n", "\ntimeout = 300\n"), encoding="utf-8")
    assert _wirksames_limit(kopie, tmp_path) == 300.0


def test_haenger_wird_am_limit_nachweislich_abgebrochen(tmp_path):
    """#3317 AC-3 (b): Given ein Test haengt 60 s, When er mit Limit 3 s laeuft,
    Then bricht pytest-timeout ihn ab: Timeout-Meldung in der Ausgabe und
    Laufzeit deutlich unter der Haengerdauer, nicht nur ein Exit-Code."""
    start = time.monotonic()
    res = _haenger_lauf(tmp_path, limit_s=3, haenger_s=60)
    dauer = time.monotonic() - start
    ausgabe = res.stdout + res.stderr
    assert res.returncode != 0, ausgabe
    assert re.search(r"Timeout \(>\s*3(\.0)?s\)", ausgabe), ausgabe[-2000:]
    assert dauer < 40, f"Haenger lief {dauer:.1f}s trotz Limit 3 s"


def test_nutzer_der_sammlung_teilen_eine_worker_gruppe(request):
    """#3317 AC-1: unter `--dist loadgroup` entstehen Modul-Fixtures je Worker
    neu; nur eine gemeinsame Gruppe haelt die eine Voll-Sammlung."""
    gruppen: dict[str, set[str]] = {}
    for item in request.session.items:
        if item.path == Path(__file__) and "sammlung" in item.fixturenames:
            marker = item.get_closest_marker("xdist_group")
            gruppen.setdefault(str(marker.args[0]) if marker else "ohne", set()).add(item.name)
    assert len(gruppen) == 1 and "ohne" not in gruppen, gruppen


@_sammlungsgruppe
def test_rolling_trip_dialer_excluded_from_default(default_collect):
    """GIVEN der Rolling-Trip-Dialer aus #937 WHEN die Standard-Selektion
    (`not email and not live and not staging`) sammelt THEN erscheint die
    Datei mit 0 gesammelten Tests -- kein Versand-Risiko im Kernlauf (AC-1).
    Schlaegt heute fehl: die Datei traegt noch keinen Marker, 2 gesammelt."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    assert default_counts.get(_ROLLING_TRIP_DIALER, 0) == 0, (
        f"{_ROLLING_TRIP_DIALER} darf im Standardlauf nicht erscheinen: "
        f"{default_counts.get(_ROLLING_TRIP_DIALER)} gesammelt."
    )


@_sammlungsgruppe
@pytest.mark.staging
def test_rolling_trip_dialer_collected_under_staging(default_collect, sammlung):
    """GIVEN `-m staging` wird bewusst aufgerufen WHEN der Rolling-Trip-Dialer
    seinen Modul-Marker traegt THEN erscheint die Datei mit mindestens einem
    gesammelten Test -- der Marker verschiebt, loescht nicht (AC-2). Schlaegt
    heute fehl, weil der Marker noch fehlt (0 gesammelt unter `-m staging`)."""
    assert default_collect.returncode == 0, default_collect.stderr
    staging_counts = _je_datei(sammlung.mit_marker("staging"))
    assert staging_counts.get(_ROLLING_TRIP_DIALER, 0) > 0, (
        f"{_ROLLING_TRIP_DIALER} fehlt unter `-m staging`: "
        f"{staging_counts.get(_ROLLING_TRIP_DIALER, 0)} gesammelt."
    )


@pytest.mark.timeout(180)
def test_rolling_trip_collection_opens_no_socket():
    """GIVEN ein Python-Prozess, in dem `socket.socket.connect`/`connect_ex`
    vor dem pytest-Start jeden Verbindungsaufbau mit einer RuntimeError-
    Unterklasse abweisen WHEN pytest die Rolling-Trip-Datei nur sammelt
    (`--collect-only -o addopts=`) THEN endet die Collection mit Exit 0 und
    beiden Test-IDs, ohne Collection-Error -- kein Netzaufruf zur Collect-
    Zeit (AC-3). Subprozess statt `--disable-socket`: pytest-socket sperrt
    erst in `pytest_runtest_setup`, nicht waehrend der Collection -- ein
    reines `--disable-socket`-Collect waere hier kein Nachweis. Schlaegt
    heute fehl: der `skipif`-Ausdruck ruft `httpx.post` bereits beim
    Einsammeln auf, der gepatchte Socket wirft, pytest meldet einen
    Collection-Error (Exit 2)."""
    pytest_args = [
        "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider",
        _ROLLING_TRIP_DIALER,
    ]
    res = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP_COLLECT_TIME_EGRESS, *pytest_args],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    combined = res.stdout + res.stderr
    assert res.returncode == 0, f"rc={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}"
    for test_id in (
        f"{_ROLLING_TRIP_DIALER}::test_setup_script_exists_and_is_importable",
        f"{_ROLLING_TRIP_DIALER}::test_rolling_trip_send_returns_sent_true",
    ):
        assert test_id in res.stdout, f"{test_id} fehlt in der Collection: {res.stdout}"
    assert "ERROR" not in combined, combined


@pytest.mark.timeout(180)
def test_rolling_trip_send_skips_at_runtime_when_port_closed():
    """GIVEN derselbe Bootstrap, aber `connect` wirft `ConnectionRefusedError`
    (Port 8001 zu, von httpx zu `httpx.ConnectError` gemappt) WHEN der
    Send-Test gezielt ausgefuehrt wird (`-o addopts=` hebt den Marker-Filter
    auf) THEN wird er als skipped gemeldet (nicht passed, nicht failed,
    nicht error) und der Prozess endet mit Exit 0 (AC-4). Auf JEDEM Host
    sicher: der Socket ist gepatcht, es kann nichts versendet werden."""
    pytest_args = [
        "-q", "-o", "addopts=", "-p", "no:cacheprovider", "-rs",
        f"{_ROLLING_TRIP_DIALER}::test_rolling_trip_send_returns_sent_true",
    ]
    res = subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP_CONNECTION_REFUSED, *pytest_args],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert res.returncode == 0, f"rc={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}"
    assert "1 skipped" in res.stdout, res.stdout

    # Nur die pytest-eigene Summary-Zeile pruefen (nicht den gesamten
    # Output) -- Dateipfade/Skip-Gruende koennten sonst faelschlich "error"
    # o.ae. enthalten (Spec-Vorgabe).
    summary_match = re.search(r"(\d+ \w+(?:, \d+ \w+)* in [\d.]+s)", res.stdout)
    assert summary_match, f"Keine pytest-Zusammenfassungszeile gefunden: {res.stdout}"
    summary_line = summary_match.group(1).lower()
    assert "passed" not in summary_line, summary_line
    assert "failed" not in summary_line, summary_line
    assert "error" not in summary_line, summary_line


@_sammlungsgruppe
def test_genau_eine_voll_sammlung_je_dateilauf(sammlung, prozessstarts):
    """#3317 AC-1: Given alle Auswahlen (Standard, email, staging, live) sind
    abgerufen, When man die echten Sammel-Prozesse der ganzen Suite zaehlt, Then
    war es genau einer, dazu hoechstens die eigene Sammlung des mtime-Tests
    (Gruppe "echtdaten", je nach Verteilung im selben Prozess). Steht bewusst
    als letzter Test der Datei."""
    voll = _voll_sammlungen(prozessstarts)
    mtime_test = [b for b in voll if f"no:{_PLUGIN}" in b]
    assert len(mtime_test) <= 1 and len(voll) - len(mtime_test) == 1, (
        f"Voll-Sammlungen (erwartet eine, dazu hoechstens die des mtime-Tests): {voll}"
    )
