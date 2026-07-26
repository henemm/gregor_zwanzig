"""
TDD RED (Fix #1382): Deploy-Gate liest denselben Nachweis, den es schreibt.

Spec: docs/specs/modules/fix_1382_deploy_gate_evidence.md (AC-1..AC-13)
Context: docs/context/fix-1382-deploy-gate-nachweis.md (Sandkasten-Experiment,
Ursache A/B/C)

Mock-frei (Projektregel): alle Tests laufen gegen echte, per importlib
geladene Hook-Module und echte, temporäre Git-Repos in ``tmp_path``. Kein
Zugriff auf das echte Hauptrepo, insbesondere NIE auf
``/home/hem/gregor_zwanzig/.claude/e2e_verified.json`` oder
``.claude/e2e_verified/`` — jedes Repo baut sich seine eigene, isolierte
Attestations-Landschaft in ``tmp_path`` auf. ``REPO_DIR``/``CANONICAL_E2E_PATH``
werden per monkeypatch auf das Temp-Repo umgebogen (reale Pfade auf ein
echtes Repo, kein Mock) — Muster aus
``tests/tdd/test_e2e_commit_namespacing.py``.

Pfadauflösung repo-relativ (Falle vermeiden: zwei Bestandssuiten laden den
Prüfling über einen hartkodierten Hauptrepo-Pfad und testen damit im
Worktree den ALTEN Stand): ``REPO_ROOT``/``HOOKS_DIR`` werden ausschließlich
relativ zu dieser Testdatei aufgelöst, niemals ``/home/hem/gregor_zwanzig``
hartkodiert.

``prod_selftest._detect_committed_scope`` bindet ``repo_dir=REPO_DIR`` zur
Modul-Importzeit als Default — ein ``REPO_DIR``-Monkeypatch wirkt dort NICHT.
Alle ``run_selftest``-Aufrufe hier übergeben ``scope`` deshalb explizit.
``prod_selftest`` macht ab Phase 2 echte HTTP-Aufrufe gegen Produktion — die
``ps_mod``-Fixture patcht ``_check_health`` auf einen Erfolgsdummy, damit
kein Test ins Netz geht (nur Phase 1 — Commit-Attestation — ist hier Thema).

In der RED-Phase fehlt die vereinheitlichte Nachweis-Auflösung noch: einige
Tests scheitern an falschem Exit-Code, andere an fehlendem/falschem
Meldungstext. Erwartung laut Auftrag: alle Tests sind jetzt ROT. Grün
gewordene Einzeltests werden im Bericht ausdrücklich benannt statt
nachträglich passend gemacht.
"""

import importlib.util
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
STAGING_GATE = HOOKS_DIR / "staging_gate.py"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"


# ---------------------------------------------------------------------------
# Modul-Loader (echte Funktionen, keine Mocks)
# ---------------------------------------------------------------------------
def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_log_capture_safe(mod, monkeypatch) -> None:
    """Test-Verdrahtung (kein Verhaltens-Mock): `_log`s Erfolgsmeldungen
    nutzen den DEFAULT-Parameter ``stream=sys.stdout``, der einmalig beim
    Modul-Import gebunden wird — zu diesem Zeitpunkt kann pytests
    Capture-Fixture (``capfd``) ihre Umlenkung für DIESEN Test noch nicht
    aktiv haben, wodurch Erfolgsmeldungen an der Capture vorbeigeschrieben
    würden (Fehlermeldungen sind unbetroffen, da sie ``stream=sys.stderr``
    an jeder Aufrufstelle live übergeben, nicht per Default). Dieser Wrapper
    lässt jeden `_log`-Aufruf ohne explizites `stream` das JEWEILS AKTUELLE
    ``sys.stdout`` verwenden — gleicher Text, gleiches Ziel, nur ohne die
    Stale-Default-Bindung. Reine Test-Infrastruktur, keine Änderung an
    Nachrichtentext oder Kontrollfluss des Hooks."""
    import sys as _sys

    original_log = mod._log

    def _live_log(msg: str, stream=None) -> None:
        original_log(msg, stream=_sys.stdout if stream is None else stream)

    monkeypatch.setattr(mod, "_log", _live_log)


@pytest.fixture
def sg_mod(monkeypatch):
    mod = _load_module(STAGING_GATE, "staging_gate_evidence_resolution")
    _make_log_capture_safe(mod, monkeypatch)
    return mod


@pytest.fixture
def ps_mod(monkeypatch):
    mod = _load_module(PROD_SELFTEST, "prod_selftest_evidence_resolution")
    # AC-7/8/9/10/13: nur Phase 1 (Commit-Attestation) ist hier Thema.
    # Phase 2 (Health-Check gegen Produktion) wird auf einen Erfolgsdummy
    # umgebogen, damit kein Test ins Netz geht.
    monkeypatch.setattr(mod, "_check_health", lambda: (True, "gepatcht: kein Netzzugriff im Test"))
    _make_log_capture_safe(mod, monkeypatch)
    return mod


# ---------------------------------------------------------------------------
# Echte Git-Repo-Bausteine
# ---------------------------------------------------------------------------
def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    # Fixture-Reparatur (PO-Freigabe 2026-07-26, keine Aenderung an
    # Erwartungen/Asserts): im echten Projekt sind .claude/e2e_verified/ und
    # .claude/e2e_verified.json gitignored (.gitignore:42-43). Ohne dieses
    # Pendant wandert eine vor einem `_commit()`-Aufruf geschriebene
    # Attestations-Datei durch dessen `git add -A` versehentlich in den
    # Commit und wird bei einem spaeteren `git checkout` auf einen aelteren
    # Stand wieder von der Platte entfernt -- die Wegwerf-Repos bilden damit
    # dasselbe Ignorier-Verhalten wie das echte Projekt ab.
    (root / ".gitignore").write_text(".claude/e2e_verified/\n.claude/e2e_verified.json\n")
    return root


def _commit(root: Path, rel_path: str, content: str, message: str) -> str:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


def _tagged_path(root: Path, sha: str) -> Path:
    return root / ".claude" / "e2e_verified" / f"{sha}.json"


def _singleton_path(root: Path) -> Path:
    return root / ".claude" / "e2e_verified.json"


def _write_attestation(
    path: Path,
    verified_commit: str,
    verdict: str,
    verified_at: "str | None" = "now",
    scope: str = "backend",
    findings=None,
) -> None:
    """Schreibt eine echte Attestations-JSON-Datei.

    ``verified_at="now"`` (Default) schreibt einen frischen ISO-Timestamp.
    ``verified_at=None`` lässt das Feld ganz weg (reale Altlast-Form, s.
    AC-11). Ein expliziter ISO-String wird unverändert übernommen (Stale-Tests).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verified_commit": verified_commit,
        "staging_verdict": verdict,
        "findings": findings if findings is not None else [],
        "scope": scope,
        "environment": "staging",
    }
    if verified_at == "now":
        payload["verified_at"] = datetime.now(timezone.utc).isoformat()
    elif verified_at is not None:
        payload["verified_at"] = verified_at
    path.write_text(json.dumps(payload, indent=2))


def _patch_repo_dir(monkeypatch, mod, root: Path) -> None:
    """Biegt REPO_DIR/CANONICAL_E2E_PATH auf das Temp-Repo um.

    ``raising=False`` hält den CANONICAL_E2E_PATH-Patch sicher, auch nachdem
    das Attribut laut Spec entfernt wird (kein AttributeError in der
    GREEN-Phase) — die Konstante wird hier nur als Sicherheitsnetz gesetzt,
    damit ``_default_e2e_path`` (falls noch vorhanden) niemals auf das echte
    Hauptrepo zeigen kann.
    """
    monkeypatch.setattr(mod, "REPO_DIR", root)
    monkeypatch.setattr(
        mod, "CANONICAL_E2E_PATH", root / ".claude" / "e2e_verified.json", raising=False
    )


# ===========================================================================
# Scheibe 1 — Nachweis-Auflösung + fünf unterscheidbare Meldungen
# ===========================================================================


def test_ac1_no_evidence_for_target_names_target_not_foreign_commit(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-1: GIVEN für den Zielstand existiert weder eine commit-getaggte
    Nachweis-Datei noch ein verifizierter Vorfahre (nur eine unabhängige,
    nicht verwandte Fremd-Attestation liegt im selben Verzeichnis), WHEN der
    Deploy-Wächter mit --expected-commit <Zielstand> geprüft wird, THEN
    blockiert er (Exit 1), die Meldung nennt den Zielstand-Kurz-SHA — nicht
    den fremden Commit — und enthält nicht 'GZ_SKIP_E2E_GATE'."""
    root = _init_repo(tmp_path / "repo")
    _commit(root, "src/a.py", "a=1\n", "c1")
    _commit(root, "src/a.py", "a=2\n", "c2")
    target = _commit(root, "src/a.py", "a=3\n", "c3")

    foreign_sha = "d850421a" + "0" * 32  # unverwandter, nicht im Repo enthaltener Commit
    _write_attestation(_tagged_path(root, foreign_sha), foreign_sha, "VERIFIED: fremder Fix")

    _patch_repo_dir(monkeypatch, sg_mod, root)
    capfd.readouterr()

    rc = sg_mod.gate_check(None, "backend", expected_commit=target)
    combined = "".join(capfd.readouterr())

    assert rc == 1, "Fehlender Nachweis muss blockieren"
    assert target[:8] in combined, f"Meldung muss den Zielstand nennen: {combined!r}"
    assert foreign_sha[:8] not in combined, (
        f"Meldung darf den fremden, nicht verwandten Commit nicht nennen: {combined!r}"
    )
    assert "GZ_SKIP_E2E_GATE" not in combined


def test_ac2_non_verified_verdict_names_target_and_verdict(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-2: GIVEN eine Nachweis-Datei für den Zielstand existiert, deren
    staging_verdict nicht mit VERIFIED beginnt (AMBIGUOUS), WHEN der
    Deploy-Wächter geprüft wird, THEN blockiert er (Exit 1) und die Meldung
    nennt sowohl den Zielstand als auch das AMBIGUOUS-Verdict wörtlich."""
    root = _init_repo(tmp_path / "repo")
    target = _commit(root, "src/a.py", "a=1\n", "c1")
    verdict = "AMBIGUOUS: Login-Flow unklar"
    e2e_path = _tagged_path(root, target)
    _write_attestation(e2e_path, target, verdict)

    _patch_repo_dir(monkeypatch, sg_mod, root)
    capfd.readouterr()

    rc = sg_mod.gate_check(e2e_path, "backend", expected_commit=target)
    combined = "".join(capfd.readouterr())

    assert rc == 1
    assert target[:8] in combined, f"Meldung muss den Zielstand nennen: {combined!r}"
    assert verdict in combined, f"Meldung muss das vorgefundene Verdict nennen: {combined!r}"


def test_ac3_stale_verified_evidence_names_hours_and_target(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-3: GIVEN ein VERIFIED-Nachweis für den Zielstand ist älter als die
    Stale-Grenze (24h), WHEN der Deploy-Wächter geprüft wird, THEN blockiert
    er (Exit 1) und die Meldung nennt sowohl das Alter in Stunden (>24) als
    auch den Zielstand."""
    root = _init_repo(tmp_path / "repo")
    target = _commit(root, "src/a.py", "a=1\n", "c1")
    e2e_path = _tagged_path(root, target)
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    _write_attestation(e2e_path, target, "VERIFIED: alt", verified_at=stale_at)

    _patch_repo_dir(monkeypatch, sg_mod, root)
    capfd.readouterr()

    rc = sg_mod.gate_check(e2e_path, "backend", expected_commit=target)
    combined = "".join(capfd.readouterr())

    assert rc == 1
    hours_found = [float(h) for h in re.findall(r"(\d+(?:\.\d+)?)\s*h", combined)]
    assert any(h > 24 for h in hours_found), (
        f"Meldung muss eine Stundenzahl > 24 enthalten: {combined!r}"
    )
    assert target[:8] in combined, (
        f"Meldung muss den Zielstand nennen (heute fehlt das im Stale-Fall): {combined!r}"
    )


def test_ac4_ancestor_relaxation_blocked_by_code_diff_lists_changed_paths(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-4: GIVEN der Zielstand ist Nachfahre eines VERIFIED Standes und der
    Zuwachs enthält mindestens eine Datei unter src/, WHEN der Deploy-Wächter
    geprüft wird, THEN blockiert er (Exit 1) und die Meldung erklärt eine
    vermutlich parallele Sitzung und nennt den geänderten src/-Dateipfad
    wörtlich."""
    root = _init_repo(tmp_path / "repo")
    base = _commit(root, "docs/x.md", "base\n", "base")
    _write_attestation(_tagged_path(root, base), base, "VERIFIED: Basis gruen")
    target = _commit(root, "src/new_feature.py", "print('x')\n", "adds backend file")
    # Preflight-Semantik: HEAD ist noch der alte, geprüfte Stand.
    _git(["checkout", "-q", base], root)

    _patch_repo_dir(monkeypatch, sg_mod, root)
    capfd.readouterr()

    rc = sg_mod.gate_check(None, None, expected_commit=target)
    combined = "".join(capfd.readouterr())

    assert rc == 1
    assert "src/new_feature.py" in combined, (
        f"Meldung muss den geänderten Dateipfad nennen: {combined!r}"
    )


def test_ac5_corrupted_file_message_differs_from_missing_evidence_message(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-5: GIVEN die für den Zielstand erwartete Nachweis-Datei existiert
    physisch, aber ihr verified_commit-Feld weicht vom Dateinamen ab, WHEN
    der Deploy-Wächter geprüft wird, THEN blockiert er (Exit 1) mit einer
    Meldung, die erkennbar von 'kein Nachweis vorhanden' (AC-1) abweicht."""
    root = _init_repo(tmp_path / "repo")
    target = _commit(root, "src/a.py", "a=1\n", "c1")
    e2e_path = _tagged_path(root, target)
    other_sha = "1" * 40
    _write_attestation(e2e_path, other_sha, "VERIFIED: falscher commit im Inhalt")

    _patch_repo_dir(monkeypatch, sg_mod, root)

    capfd.readouterr()
    rc_corrupted = sg_mod.gate_check(e2e_path, "backend", expected_commit=target)
    corrupted_message = "".join(capfd.readouterr())

    e2e_path.unlink()  # Vergleichsfall: exakt derselbe Pfad, aber Datei fehlt komplett
    capfd.readouterr()
    rc_missing = sg_mod.gate_check(e2e_path, "backend", expected_commit=target)
    missing_message = "".join(capfd.readouterr())

    assert rc_corrupted == 1
    assert rc_missing == 1
    assert corrupted_message != missing_message, (
        "Meldung fuer 'Datei vorhanden, Inhalt passt nicht zum Namen' muss sich "
        "von der 'kein Nachweis vorhanden'-Meldung unterscheiden.\n"
        f"corrupted={corrupted_message!r}\nmissing={missing_message!r}"
    )


def test_ac6_full_short_and_origin_main_resolve_to_identical_result(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-6: GIVEN ein Nachweis wurde für einen Commit unter seiner vollen
    SHA geschrieben, WHEN derselbe Commit per Kurz-SHA und separat per
    origin/main als --expected-commit abgefragt wird, THEN liefern beide
    Aufrufe exakt dasselbe Ergebnis (Exit-Code UND OK-Meldung, d.h. dieselbe
    aufgelöste volle SHA) wie die Abfrage mit der vollen SHA.

    Reine Exit-Code-Gleichheit allein ist hier KEIN ausreichender Beweis:
    ein zweiter Pfad im heutigen Code (Ancestor-Relaxierung, #1197) kann für
    'origin/main'/Kurz-SHA zufällig denselben Exit-Code liefern, obwohl die
    SHA nie normalisiert wurde (der Commit ist über git rev-list sein
    eigener Vorfahre, der Zuwachs also ein Leer-Diff = 'docs-only'). Die
    OK-Meldung unterscheidet die Fälle: bei echter SHA-Normalisierung ist sie
    für alle drei Formen identisch (derselbe aufgelöste ref[:8]); bei
    zufälliger Ancestor-Relaxierung nennt sie für 'origin/main' abweichenden
    Text ('Ancestor-Relaxierung' statt 'Staging-Gate bestanden', bzw. ein
    anderes gekürztes ref)."""
    root = _init_repo(tmp_path / "repo")
    target = _commit(root, "src/a.py", "a=1\n", "c1")
    _write_attestation(_tagged_path(root, target), target, "VERIFIED: alle ACs gruen")

    bare = tmp_path / "origin.git"
    _git(["init", "-q", "--bare", str(bare)], tmp_path)
    _git(["remote", "add", "origin", str(bare)], root)
    _git(["push", "-q", "origin", "HEAD:refs/heads/main"], root)
    _git(["fetch", "-q", "origin"], root)
    assert _git(["rev-parse", "origin/main"], root).stdout.strip() == target

    _patch_repo_dir(monkeypatch, sg_mod, root)

    capfd.readouterr()
    rc_full = sg_mod.gate_check(None, "backend", expected_commit=target)
    msg_full = "".join(capfd.readouterr())

    capfd.readouterr()
    rc_short = sg_mod.gate_check(None, "backend", expected_commit=target[:8])
    msg_short = "".join(capfd.readouterr())

    capfd.readouterr()
    rc_origin = sg_mod.gate_check(None, "backend", expected_commit="origin/main")
    msg_origin = "".join(capfd.readouterr())

    assert rc_full == 0, "Die volle SHA muss den geschriebenen Nachweis finden"
    assert rc_short == rc_full, f"Kurz-SHA liefert ein anderes Ergebnis: {rc_short} != {rc_full}"
    assert rc_origin == rc_full, (
        f"origin/main liefert ein anderes Ergebnis: {rc_origin} != {rc_full}"
    )
    assert "Ancestor-Relaxierung" not in msg_full
    assert "Ancestor-Relaxierung" not in msg_short, (
        f"Kurz-SHA darf nicht zufällig über die Ancestor-Relaxierung laufen: {msg_short!r}"
    )
    assert "Ancestor-Relaxierung" not in msg_origin, (
        f"origin/main darf nicht zufällig über die Ancestor-Relaxierung laufen "
        f"(genau der SHA-Normalisierungs-Defekt aus der Spec): {msg_origin!r}"
    )
    assert msg_short == msg_full, (
        f"Kurz-SHA muss dieselbe Meldung wie die volle SHA erzeugen "
        f"(normalisierte SHA):\nkurz={msg_short!r}\nvoll={msg_full!r}"
    )
    assert msg_origin == msg_full, (
        f"origin/main muss dieselbe Meldung wie die volle SHA erzeugen "
        f"(normalisierte SHA):\norigin={msg_origin!r}\nvoll={msg_full!r}"
    )


def test_ac11_legacy_singleton_with_foreign_commit_is_ignored(
    tmp_path, monkeypatch, sg_mod, capfd
):
    """AC-11: Direkte Reproduktion des gemeldeten Fehlers #1382. GIVEN für
    den Zielstand existiert kein Nachweis, aber die alte Sammeldatei
    .claude/e2e_verified.json liegt daneben und trägt einen fremden, älteren
    Commit (nur zwei Felder — verified_commit, staging_verdict — exakt wie
    die reale Altlast, kein verified_at), WHEN der Deploy-Wächter mit
    --expected-commit <Zielstand> geprüft wird, THEN blockiert er (Exit 1),
    die Meldung nennt den fremden Commit aus der Sammeldatei NICHT, und das
    Ergebnis ist identisch zu einem Lauf, bei dem die Sammeldatei gar nicht
    existiert."""
    root = _init_repo(tmp_path / "repo")
    c1 = _commit(root, "src/a.py", "a=1\n", "c1")
    _commit(root, "src/a.py", "a=2\n", "c2")
    c3 = _commit(root, "src/a.py", "a=3\n", "c3")

    _patch_repo_dir(monkeypatch, sg_mod, root)

    # Lauf 1: ohne Sammeldatei
    capfd.readouterr()
    rc_without = sg_mod.gate_check(None, "backend", expected_commit=c3)
    without_message = "".join(capfd.readouterr())

    # Sammeldatei anlegen: nur zwei Felder, kein verified_at (reale Altlast-Form,
    # 2026-06-23, s. docs/context/fix-1382-deploy-gate-nachweis.md)
    singleton = _singleton_path(root)
    singleton.parent.mkdir(parents=True, exist_ok=True)
    singleton.write_text(json.dumps({
        "verified_commit": c1,
        "staging_verdict": "VERIFIED — backend-only SMS-Fix: ...",
    }))

    # Lauf 2: mit Sammeldatei
    capfd.readouterr()
    rc_with = sg_mod.gate_check(None, "backend", expected_commit=c3)
    with_message = "".join(capfd.readouterr())

    assert rc_without == 1
    assert rc_with == 1
    assert c3[:8] in without_message
    assert c3[:8] in with_message
    assert c1[:8] not in with_message, (
        "Die Sammeldatei-Altlast darf im blockierenden Text nicht mehr "
        f"auftauchen (genau der gemeldete Fehler #1382): {with_message!r}"
    )
    assert with_message == without_message, (
        "Ergebnis MUSS identisch sein, ob die Sammeldatei existiert oder nicht.\n"
        f"mit={with_message!r}\nohne={without_message!r}"
    )


def test_ac12_no_blocking_message_mentions_skip_override(tmp_path, monkeypatch, capfd):
    """AC-12: GIVEN der Deploy-Wächter blockiert aus einem der fünf Gründe
    (i) bis (v), WHEN die jeweilige Meldung ausgegeben wird, THEN enthält
    keine davon einen Hinweis auf den Notfall-Schalter GZ_SKIP_E2E_GATE."""
    messages = []

    # (i) kein Nachweis
    root1 = _init_repo(tmp_path / "r1")
    c1 = _commit(root1, "src/a.py", "1\n", "c1")
    sg1 = _load_module(STAGING_GATE, "sg_ac12_i")
    _patch_repo_dir(monkeypatch, sg1, root1)
    capfd.readouterr()
    rc1 = sg1.gate_check(None, "backend", expected_commit=c1)
    messages.append("".join(capfd.readouterr()))
    assert rc1 == 1

    # (ii) nicht VERIFIED
    root2 = _init_repo(tmp_path / "r2")
    c2 = _commit(root2, "src/a.py", "1\n", "c1")
    sg2 = _load_module(STAGING_GATE, "sg_ac12_ii")
    _patch_repo_dir(monkeypatch, sg2, root2)
    e2e2 = _tagged_path(root2, c2)
    _write_attestation(e2e2, c2, "AMBIGUOUS: unklar")
    capfd.readouterr()
    rc2 = sg2.gate_check(e2e2, "backend", expected_commit=c2)
    messages.append("".join(capfd.readouterr()))
    assert rc2 == 1

    # (iii) stale
    root3 = _init_repo(tmp_path / "r3")
    c3 = _commit(root3, "src/a.py", "1\n", "c1")
    sg3 = _load_module(STAGING_GATE, "sg_ac12_iii")
    _patch_repo_dir(monkeypatch, sg3, root3)
    e2e3 = _tagged_path(root3, c3)
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    _write_attestation(e2e3, c3, "VERIFIED: alt", verified_at=stale_at)
    capfd.readouterr()
    rc3 = sg3.gate_check(e2e3, "backend", expected_commit=c3)
    messages.append("".join(capfd.readouterr()))
    assert rc3 == 1

    # (iv) Zuwachs enthaelt Code
    root4 = _init_repo(tmp_path / "r4")
    base4 = _commit(root4, "docs/x.md", "b\n", "base")
    sg4 = _load_module(STAGING_GATE, "sg_ac12_iv")
    _patch_repo_dir(monkeypatch, sg4, root4)
    _write_attestation(_tagged_path(root4, base4), base4, "VERIFIED: Basis")
    target4 = _commit(root4, "src/new.py", "x\n", "code dazu")
    _git(["checkout", "-q", base4], root4)
    capfd.readouterr()
    rc4 = sg4.gate_check(None, None, expected_commit=target4)
    messages.append("".join(capfd.readouterr()))
    assert rc4 == 1

    # (v) Datei vorhanden, Inhalt passt nicht zum Namen
    root5 = _init_repo(tmp_path / "r5")
    c5 = _commit(root5, "src/a.py", "1\n", "c1")
    sg5 = _load_module(STAGING_GATE, "sg_ac12_v")
    _patch_repo_dir(monkeypatch, sg5, root5)
    e2e5 = _tagged_path(root5, c5)
    _write_attestation(e2e5, "9" * 40, "VERIFIED: falsch")
    capfd.readouterr()
    rc5 = sg5.gate_check(e2e5, "backend", expected_commit=c5)
    messages.append("".join(capfd.readouterr()))
    assert rc5 == 1

    for i, msg in enumerate(messages, start=1):
        assert "GZ_SKIP_E2E_GATE" not in msg, (
            f"Blockade-Meldung ({i}) darf den Notfall-Schalter nicht erwaehnen: {msg!r}"
        )


# ===========================================================================
# Scheibe 2 — Selbsttest so streng wie das Gate
# ===========================================================================


def test_ac7_selftest_blocks_when_code_deployed_without_any_evidence(
    tmp_path, monkeypatch, ps_mod
):
    """AC-7: GIVEN der Scope-Check hat bereits festgestellt, dass echter
    Programmcode ausgerollt wurde, und für den aktuellen Produktions-HEAD
    existiert weder ein exakter Nachweis noch ein verifizierter Vorfahre,
    WHEN der Post-Deploy-Selbsttest läuft, THEN blockiert er (Exit 1) statt
    wie bisher zu überspringen. Löst #564 AC-5 ab."""
    root = _init_repo(tmp_path / "repo")
    head = _commit(root, "src/a.py", "a=1\n", "code change")

    _patch_repo_dir(monkeypatch, ps_mod, root)
    head_path = _tagged_path(root, head)
    assert not head_path.exists()

    rc = ps_mod.run_selftest(head_path, "test-workflow", scope="backend")

    assert rc == 1, (
        "Fehlender Nachweis bei Code-Scope darf nicht mehr Exit 0 sein (bisheriges "
        "#564-AC-5-Verhalten war 'fehlende Datei -> Exit 0 + INFO')."
    )


def test_ac8_ancestor_with_broken_verdict_never_passes(tmp_path, monkeypatch, ps_mod):
    """AC-8: GIVEN der aktuelle HEAD ist Nachfahre eines Commits, dessen
    Nachweis-Datei existiert, aber staging_verdict mit BROKEN beginnt, WHEN
    der Post-Deploy-Selbsttest läuft, THEN ergibt er NICHT PASS, sondern
    blockiert (Exit 1) — die reine Vorfahren-Beziehung allein darf nie mehr
    zu Exit 0 führen (Sandkasten-Experiment zeigte hier vorher Exit 0)."""
    root = _init_repo(tmp_path / "repo")
    base = _commit(root, "src/a.py", "a=1\n", "base")
    _write_attestation(_tagged_path(root, base), base, "BROKEN — Staging kaputt")
    head = _commit(root, "src/a.py", "a=2\n", "head, kein eigener Nachweis")

    _patch_repo_dir(monkeypatch, ps_mod, root)
    head_path = _tagged_path(root, head)
    assert not head_path.exists()

    rc = ps_mod.run_selftest(head_path, "test-workflow", scope="backend")

    assert rc == 1, (
        "BROKEN-Vorfahre darf den Selbsttest nicht durchwinken, nur weil HEAD "
        "sein Nachfahre ist."
    )


def test_ac9_docs_only_ancestor_passes_gate_and_selftest_identically(
    tmp_path, monkeypatch, sg_mod, ps_mod
):
    """AC-9: GIVEN der aktuelle HEAD ist Nachfahre eines VERIFIED,
    nicht-stalen Vorfahren, und der Zuwachs ist ausschließlich Dokumentation,
    WHEN sowohl der Deploy-Wächter als auch der Post-Deploy-Selbsttest
    laufen, THEN liefern BEIDE Exit-Code 0 — der zulässige Ancestor-Durchlass
    ist für beide Aufrufer identisch."""
    root = _init_repo(tmp_path / "repo")
    base = _commit(root, "src/a.py", "a=1\n", "base code")
    _write_attestation(_tagged_path(root, base), base, "VERIFIED: Basis gruen")
    head = _commit(root, "docs/readme.md", "doku\n", "nur doku dazu")

    # Gate-Check in Preflight-Semantik: HEAD = alter Stand, expected = Ziel.
    _git(["checkout", "-q", base], root)
    _patch_repo_dir(monkeypatch, sg_mod, root)
    rc_gate = sg_mod.gate_check(None, None, expected_commit=head)

    # Selbsttest in Post-Deploy-Semantik: HEAD == Zielstand (Reset bereits erfolgt).
    _git(["checkout", "-q", head], root)
    _patch_repo_dir(monkeypatch, ps_mod, root)
    head_path = _tagged_path(root, head)
    rc_selftest = ps_mod.run_selftest(head_path, "test-workflow", scope="backend")

    assert rc_gate == 0, "Gate: docs-only-Zuwachs auf VERIFIED-Basis muss durchlassen"
    assert rc_selftest == 0, "Selftest: dieselbe Ancestor-Bedingung muss auch hier durchlassen"


def test_ac10_exact_match_verified_evidence_selftest_still_passes(
    tmp_path, monkeypatch, ps_mod
):
    """AC-10: GIVEN eine Nachweis-Datei für den exakten Zielstand existiert,
    ist VERIFIED und frisch, WHEN der Post-Deploy-Selbsttest läuft, THEN
    bleibt Exit 0 unverändert erhalten (keine Regression durch die
    Verschärfung)."""
    root = _init_repo(tmp_path / "repo")
    head = _commit(root, "src/a.py", "a=1\n", "code change")
    head_path = _tagged_path(root, head)
    _write_attestation(head_path, head, "VERIFIED: exakt")

    _patch_repo_dir(monkeypatch, ps_mod, root)

    rc = ps_mod.run_selftest(head_path, "test-workflow", scope="backend")

    assert rc == 0, "Exakter, frischer VERIFIED-Nachweis fuer HEAD darf keine Regression erleiden"


def test_ac13_stale_ancestor_blocks_selftest(tmp_path, monkeypatch, ps_mod):
    """AC-13: GIVEN der einzige auffindbare Nachweis stammt von einem
    Vorfahren, ist zwar VERIFIED, aber älter als die Stale-Grenze (24h),
    WHEN der Post-Deploy-Selbsttest läuft, THEN blockiert er (Exit 1) —
    heute prüft der Selbsttest das Alter überhaupt nicht."""
    root = _init_repo(tmp_path / "repo")
    base = _commit(root, "src/a.py", "a=1\n", "base code")
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    _write_attestation(_tagged_path(root, base), base, "VERIFIED: alt", verified_at=stale_at)
    head = _commit(root, "docs/readme.md", "doku\n", "nur doku")

    _patch_repo_dir(monkeypatch, ps_mod, root)
    head_path = _tagged_path(root, head)

    rc = ps_mod.run_selftest(head_path, "test-workflow", scope="backend")

    assert rc == 1, (
        "Ein staler VERIFIED-Vorfahre (>24h) darf den Selbsttest nicht mehr "
        "durchwinken (bisher: 'PASS (Ancestor)' ohne Alterspruefung)."
    )


def test_ac14_broken_evidence_in_chain_is_not_skipped_past(
    tmp_path, monkeypatch, sg_mod, ps_mod
):
    """AC-14 (Scheibe 2), PO-Entscheidung 2026-07-26 nach Adversary-Fund F001.

    GIVEN eine Commit-Kette c0 --VERIFIED--> c1 --BROKEN--> c2 (c2 traegt
    selbst keinen Nachweis), WHEN sowohl der Deploy-Waechter als auch der
    Post-Deploy-Selbsttest gegen c2 laufen, THEN blockieren BEIDE (Exit 1) —
    die Ancestor-Suche darf den ausdruecklichen BROKEN-Befund an c1 nicht per
    `continue` uebergehen und stattdessen den aelteren VERIFIED-Nachweis an c0
    als Basis verwenden. Vorher: `_nearest_verified_ancestor` sprang ueber c1
    hinweg zu c0 und lieferte faelschlich Exit 0 ('Ancestor-Relaxierung' bzw.
    'PASS (Ancestor)'), obwohl der Zuwachs c0..c2 rein pfadbasiert (nur
    docs/) als docs-only durchgeht und der BROKEN-Befund an c1 in keiner
    Meldung auftauchte.
    """
    root = _init_repo(tmp_path / "repo")
    c0 = _commit(root, "src/base.py", "a=1\n", "c0: verifizierte Basis")
    _write_attestation(_tagged_path(root, c0), c0, "VERIFIED: Basis gruen")
    c1 = _commit(root, "docs/note.md", "n1\n", "c1: staging kaputt")
    _write_attestation(_tagged_path(root, c1), c1, "BROKEN — Staging kaputt")
    c2 = _commit(root, "docs/note2.md", "n2\n", "c2: kein eigener Nachweis")

    # Deploy-Waechter in Preflight-Semantik (wie AC-9/AC-13): HEAD ist noch
    # der alte, bereits ausgerollte Stand (c0), expected_commit ist das Ziel.
    _git(["checkout", "-q", c0], root)
    _patch_repo_dir(monkeypatch, sg_mod, root)
    rc_gate = sg_mod.gate_check(None, "backend", expected_commit=c2)

    # Post-Deploy-Selbsttest: HEAD == Zielstand (Reset bereits erfolgt).
    _git(["checkout", "-q", c2], root)
    _patch_repo_dir(monkeypatch, ps_mod, root)
    c2_path = _tagged_path(root, c2)
    rc_selftest = ps_mod.run_selftest(c2_path, "test-workflow", scope="backend")

    assert rc_gate == 1, (
        "Deploy-Waechter darf den BROKEN-Befund an c1 nicht uebergehen und "
        "stattdessen den aelteren VERIFIED-Nachweis an c0 als Basis nehmen."
    )
    assert rc_selftest == 1, (
        "Post-Deploy-Selbsttest darf denselben BROKEN-Befund nicht uebergehen "
        "— beide Pruefer teilen sich _nearest_verified_ancestor."
    )
