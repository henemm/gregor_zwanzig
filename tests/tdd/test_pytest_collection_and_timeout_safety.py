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
"""
from __future__ import annotations

import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Fix-Loop 1 (F001/F002, Adversary): 9 Dateien tragen weiterhin einen
# vollstaendigen Modul-Marker (jeder Test dialt); 1147/684 sind jetzt
# GEMISCHT -- nur die real dialenden Tests/Klassen tragen `@pytest.mark.email`,
# die restlichen Guard-Tests bleiben im Standardlauf.
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
)
_MIXED_B1_FILES = (
    "tests/tdd/test_issue_1147_resend_recipient_invariant.py",
    "tests/tdd/test_issue_684_alert_email_guard.py",
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
    "tests/tdd/test_issue_496_layout.py",
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

# Spec Liste C: 6 Dateien OHNE echten Netzcall -- bleiben unveraendert in der
# Standard-Selektion (Regressions-Wächter gegen versehentliche Mit-Markierung).
_OFFLINE_KEEP_FILES = (
    "tests/tdd/test_epic_404_phase2_ist_screenshots.py",
    "tests/tdd/test_prod_selftest_internal_url_skip.py",
    "tests/tdd/test_staging_gate.py",
    "tests/tdd/test_staging_gate_verdict_merge.py",
    "tests/tdd/test_issue_1148_prod_send_gate.py",
    "tests/tdd/test_issue_339_verify_timing.py",
)

# addopts liefert bereits ein "-q" -> Quiet-Level 2 -> kompaktes "pfad: N"-Format
# statt einzelner Test-IDs (empirisch verifiziert, kein Rateversuch).
_COLLECTED_LINE = re.compile(r"^(tests/\S+\.py): (\d+)$", re.MULTILINE)


def _collect(*extra_args: str, timeout: int) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra_args]
    return subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=timeout)


def _collected_counts(output: str) -> dict[str, int]:
    """Datei -> Anzahl gesammelter Tests (0 = Datei fehlt komplett)."""
    return {path: int(n) for path, n in _COLLECTED_LINE.findall(output)}


def _full_id_counts(output: str, files: tuple[str, ...]) -> dict[str, int]:
    """Wie _collected_counts, aber fuer volle Test-IDs (`pfad::test`) --
    noetig, wenn `-o addopts=` die addopts-eigene "-q" entfernt und damit das
    kompakte "pfad: N"-Format nicht mehr greift."""
    lines = output.splitlines()
    return {f: sum(1 for ln in lines if ln.startswith(f"{f}::")) for f in files}


@pytest.fixture(scope="module")
def default_collect() -> subprocess.CompletedProcess:
    """Ein Standardlauf-Collect fuer AC-2/AC-3/AC-8 (ein Subprozess, geteilt)."""
    return _collect(timeout=90)


@pytest.fixture(scope="module")
def email_collect() -> subprocess.CompletedProcess:
    return _collect("-m", "email", timeout=60)


@pytest.fixture(scope="module")
def staging_collect() -> subprocess.CompletedProcess:
    """`-m staging`-Collect fuer AC-2 (ein Subprozess, geteilt)."""
    return _collect("-m", "staging", timeout=90)


@pytest.fixture(scope="module")
def mixed_total_collect() -> subprocess.CompletedProcess:
    """Marker-neutrale Collection NUR der 2 gemischten Dateien (`-o addopts=`
    schaltet die Marker-Filterung komplett ab) -- liefert den Gesamt-Count je
    Datei fuer den Partitionsnachweis (kein Test darf verloren gehen/doppelt
    zaehlen)."""
    return _collect("-o", "addopts=", *_MIXED_B1_FILES, timeout=30)


def test_default_selection_excludes_b1_live_leak_files(
    default_collect, email_collect, mixed_total_collect,
):
    """GIVEN 9 vollstaendig markierte B1-Dateien + 2 gemischt markierte
    (1147/684 -- nur real dialende Tests/Klassen) WHEN Standardlauf ohne `-m`
    sammelt THEN fehlen die 9 vollen Dateien komplett UND die 2 gemischten
    partitionieren sich exakt in (Standardlauf-Rest, `-m email`-Dialer) --
    beide Teile nicht-leer, zusammen == marker-neutraler Gesamt-Count (AC-2)."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    leaked = {f: default_counts[f] for f in _FULL_B1_FILES if default_counts.get(f, 0) > 0}
    assert not leaked, f"Voll markierte B1-Dateien duerfen im Standardlauf nicht erscheinen: {leaked}"

    assert mixed_total_collect.returncode == 0, mixed_total_collect.stderr
    email_counts = _collected_counts(email_collect.stdout)
    total_counts = _full_id_counts(mixed_total_collect.stdout, _MIXED_B1_FILES)
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


def test_friendly_format_footgun_not_collected_by_default(default_collect):
    """GIVEN test_e2e_friendly_format_config.py (Docstring: NICHT als pytest)
    WHEN Standardselektion sammelt THEN keine Test-ID (AC-3, Collection-Teil)
    UND ein zweiter Collect-Lauf veraendert keine mtime unter
    data/users/default/trips/*.json (AC-3, Mutations-Teil)."""
    collected = _collected_counts(default_collect.stdout)
    assert _FRIENDLY_FORMAT_FOOTGUN not in collected, (
        f"{_FRIENDLY_FORMAT_FOOTGUN} darf im Standardlauf nicht erscheinen "
        f"(mutiert sonst data/users/default/trips/*.json)."
    )

    if not _TRIPS_DIR.is_dir():
        pytest.skip(f"{_TRIPS_DIR} nicht vorhanden -- mtime-Nachweis uebersprungen")
    trip_files = sorted(_TRIPS_DIR.glob("*.json"))
    if not trip_files:
        pytest.skip(f"{_TRIPS_DIR} enthaelt keine *.json -- mtime-Nachweis uebersprungen")
    before = {p: p.stat().st_mtime for p in trip_files}
    second = _collect(timeout=90)
    assert second.returncode == 0, second.stderr
    after = {p: p.stat().st_mtime for p in trip_files}
    assert before == after, (
        f"Ein --collect-only-Lauf darf data/users/default/trips/*.json nicht "
        f"anfassen: vorher={before} nachher={after}"
    )


def test_full_suite_collection_still_exits_zero(default_collect):
    """GIVEN Marker-Registry in pyproject.toml WHEN volle Suite per
    `--collect-only -q` sammelt THEN Exit 0, keine ERROR-Zeilen (Regressions-
    waechter -- darf als einziger heute schon gruen sein, AC-8)."""
    assert default_collect.returncode == 0, default_collect.stderr
    assert "ERROR" not in default_collect.stdout, default_collect.stdout


def test_email_marker_run_still_collects_b1_files(email_collect):
    """GIVEN `-m email` wird bewusst aufgerufen WHEN alle 11 B1-Dateien
    (voll oder teilweise) markiert sind THEN erscheint jede mit mindestens
    einem Test -- Marker verschiebt, loescht nicht (AC-7)."""
    assert email_collect.returncode == 0, email_collect.stderr
    email_counts = _collected_counts(email_collect.stdout)
    missing = sorted(f for f in _B1_FILES if email_counts.get(f, 0) == 0)
    assert not missing, f"B1-Dateien fehlen unter `-m email`: {missing}"


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


def test_staging_marker_run_still_collects_dialers(staging_collect):
    """GIVEN `-m staging` wird bewusst aufgerufen WHEN alle 22 Dialer aus
    Liste A markiert sind THEN erscheint jede Datei mit mindestens einem
    gesammelten Test -- der Marker verschiebt sie nur, loescht keinen Test
    (AC-2). Schlaegt heute fehl, weil der Marker noch fehlt (0 gesammelt)."""
    assert staging_collect.returncode == 0, staging_collect.stderr
    staging_counts = _collected_counts(staging_collect.stdout)
    missing = sorted(f for f in _STAGING_DIALER_FILES if staging_counts.get(f, 0) == 0)
    assert not missing, f"Staging-Dialer fehlen unter `-m staging`: {missing}"


def test_offline_files_remain_in_default_selection(default_collect):
    """GIVEN 6 Offline-Kern-Dateien aus Liste C (kein echter Netzcall) WHEN
    die Standard-Selektion sammelt THEN bleiben alle 6 weiterhin gesammelt --
    keine wird versehentlich mit-markiert (AC-3). Regressions-Waechter --
    darf schon heute gruen sein (analog AC-8 im Bestand)."""
    assert default_collect.returncode == 0, default_collect.stderr
    default_counts = _collected_counts(default_collect.stdout)
    missing = sorted(f for f in _OFFLINE_KEEP_FILES if default_counts.get(f, 0) == 0)
    assert not missing, f"Offline-Dateien fehlen im Standardlauf: {missing}"


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


def test_811_gate_test_skips_when_hook_missing(tmp_path):
    """GIVEN `.claude/hooks/renderer_mail_gate.py` ist nicht auffindbar (z. B.
    Plugin unter anderem OS-Nutzer unsichtbar) WHEN test_issue_811_renderer_gate.py
    gesammelt wird THEN kein Collection-Error, sondern erkennbarer Skip (AC-4)."""
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


@pytest.mark.timeout(300)
def test_timeout_ini_default_kills_hanging_test(tmp_path):
    """GIVEN ein Test haengt unerwartet WHEN der Standardlauf laeuft THEN
    bricht er nach kurzer, fester Zeitschranke ab statt unbegrenzt zu
    blockieren (AC-1). `@pytest.mark.timeout(300)`: deklarierter Langlaeufer --
    dieser Meta-Test wartet selbst auf den verschachtelten Subprozess (bis zu
    ~30s ini-Timeout + Prozess-Overhead) und darf dabei nicht vom globalen
    ini-Timeout gekillt werden, den er gerade prueft.
    """
    scratch = tmp_path / "hang"
    scratch.mkdir()
    hang_file = scratch / "test_hangs.py"
    hang_file.write_text("import time\n\ndef test_hangs():\n    time.sleep(90)\n")

    cmd = [sys.executable, "-m", "pytest", "-c", str(_PYPROJECT), str(hang_file), "-q"]
    try:
        res = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        pytest.fail(
            "Kein Sicherheitsnetz: haengender Test lief volle 60s Wallclock "
            "ohne Abbruch durch einen ini-Timeout-Mechanismus."
        )
    assert res.returncode != 0, f"Haengender Test muss fehlschlagen: rc={res.returncode}"
