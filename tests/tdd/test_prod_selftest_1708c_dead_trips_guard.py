"""TDD RED — Issue #1708 Scheibe C: Prod-Selftest-Wächter gegen
Wiederauftauchen der toten trips-Ablage (AC-8).

Spec: docs/specs/modules/fix_1708_c_tote_ablage_loeschen.md, AC-8.

Muster wie `check_bot_menu` (Phase 4, test_issue_671_bot_menu_autoset.py):
eine eigenständige, per Parameter testbare Funktion statt vollem
`run_selftest`-Rundlauf (Commit-Attestation/Health wären sonst nötig, um sie
zu erreichen). Kein Mock -- echter `sudo -n find`-Subprozess gegen tmp_path
(NOPASSWD-sudo auf diesem Host bestätigt, #1708 Context-Dokument).

Abgedeckte Fälle (RED-Phase):
    FAIL   -- ein `trips`- oder `trips.TOT-legacy-...`-Ordner existiert noch.
    PASS   -- keiner der beiden Namen existiert.
    SKIPPED -- der Check selbst ist nicht durchführbar (hier: Root existiert
               nicht -> `find` liefert einen Fehler statt eines leeren
               Ergebnisses) -- fail-open, kein Verdict-Einfluss.

Heute ROT: `check_dead_trips_guard` existiert in prod_selftest.py noch
nicht -> AttributeError.
"""
from __future__ import annotations

from tests.tdd.conftest import (
    _init_evidence_free_repo,
    _load_prod_selftest_module,
    _make_e2e_verified,
)


def test_fail_when_legacy_trips_dir_still_exists(tmp_path):
    """Given `users/henning/trips.TOT-legacy-1250-nicht-lesen/` existiert
    noch / When der Wächter gegen diesen Root läuft / Then meldet er FAIL
    mit dem Fundpfad im Detail."""
    mod = _load_prod_selftest_module()
    assert hasattr(mod, "check_dead_trips_guard"), (
        "AC-8 verletzt: prod_selftest.check_dead_trips_guard fehlt"
    )

    users_root = tmp_path / "users"
    legacy = users_root / "henning" / "trips.TOT-legacy-1250-nicht-lesen"
    legacy.mkdir(parents=True)

    finding = mod.check_dead_trips_guard(users_root=users_root)

    assert finding.get("status") == "FAIL", f"erwartet FAIL, war: {finding!r}"
    assert "henning" in finding.get("detail", ""), (
        f"Fundpfad fehlt im Detail: {finding!r}"
    )


def test_fail_when_plain_trips_dir_still_exists(tmp_path):
    """Given `users/default/trips/` (Originalname, wie auf Staging/lokal)
    existiert noch / When der Wächter läuft / Then FAIL -- beide
    Namensmuster werden gleichwertig erkannt."""
    mod = _load_prod_selftest_module()

    users_root = tmp_path / "users"
    (users_root / "default" / "trips").mkdir(parents=True)

    finding = mod.check_dead_trips_guard(users_root=users_root)

    assert finding.get("status") == "FAIL", f"erwartet FAIL, war: {finding!r}"


def test_pass_when_neither_name_pattern_exists(tmp_path):
    """Given `users/default/` enthält nur `briefings/` (lebender Pfad) /
    When der Wächter läuft / Then PASS."""
    mod = _load_prod_selftest_module()

    users_root = tmp_path / "users"
    (users_root / "default" / "briefings").mkdir(parents=True)

    finding = mod.check_dead_trips_guard(users_root=users_root)

    assert finding.get("status") == "PASS", f"erwartet PASS, war: {finding!r}"


def test_skipped_when_check_itself_is_not_executable(tmp_path):
    """Given der übergebene Root existiert nicht (find kann nicht laufen) /
    When der Wächter läuft / Then SKIPPED statt FAIL -- eine unabhängige
    Nicht-Prüfbarkeit darf keinen Prod-Deploy blockieren (fail-open, analog
    `check_bot_menu` ohne Token)."""
    mod = _load_prod_selftest_module()

    nonexistent = tmp_path / "does-not-exist" / "users"

    finding = mod.check_dead_trips_guard(users_root=nonexistent)

    assert finding.get("status") == "SKIPPED", f"erwartet SKIPPED, war: {finding!r}"


def test_verdict_becomes_fail_when_guard_fails(tmp_path, monkeypatch):
    """Given `run_selftest` durchläuft die additive Phase 5 / When der
    Wächter FAIL meldet / Then wird das Gesamt-Verdict TATSÄCHLICH FAIL --
    echter End-to-End-Lauf von `run_selftest`, nicht nur eine
    `inspect.getsource`-String-Suche (Adversary-Finding F001, Runde 1: die
    reine Quelltext-Suche fängt nicht, wenn die Verdict-Zuweisungszeile
    entfernt wird -- der volle Regressionslauf blieb dabei komplett grün)."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(
        mod, "_http_get", lambda url, follow_redirects=False: (200, b'{"status": "ok"}', "")
    )
    monkeypatch.setattr(
        mod,
        "check_dead_trips_guard",
        lambda **kwargs: {
            "check": "dead_trips_guard",
            "status": "FAIL",
            "detail": "test-fund (F001-Gegenprobe)",
        },
    )

    e2e_path = _make_e2e_verified(tmp_path, verified_commit=head)
    workflow_name = "fix-1708c-ac8-verdict-fail"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

    rc = mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=True)

    assert rc == 1, f"FAIL-Fund des Wächters muss Exit 1 liefern, bekam {rc}"
    content = report_path.read_text()
    assert "**Verdict: FAIL**" in content, (
        f"Gesamt-Verdict muss FAIL sein, wenn check_dead_trips_guard FAIL meldet:\n{content}"
    )


def test_verdict_unchanged_when_guard_passes(tmp_path, monkeypatch):
    """Gegenprobe zu F001: meldet der Wächter PASS, bleibt das sonst
    erfolgreiche Gesamt-Verdict PASS -- Phase 5 darf keinen falschen FAIL
    erzeugen."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(
        mod, "_http_get", lambda url, follow_redirects=False: (200, b'{"status": "ok"}', "")
    )
    monkeypatch.setattr(
        mod,
        "check_dead_trips_guard",
        lambda **kwargs: {
            "check": "dead_trips_guard",
            "status": "PASS",
            "detail": "keine Funde (F001-Gegenprobe)",
        },
    )

    e2e_path = _make_e2e_verified(tmp_path, verified_commit=head)
    workflow_name = "fix-1708c-ac8-verdict-pass"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

    rc = mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=True)

    assert rc == 0, f"PASS-Wächter darf das Gesamt-Verdict nicht auf FAIL ziehen, bekam Exit {rc}"
    content = report_path.read_text()
    assert "**Verdict: PASS**" in content, (
        f"Gesamt-Verdict muss PASS bleiben, wenn check_dead_trips_guard PASS meldet:\n{content}"
    )
