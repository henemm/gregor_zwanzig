"""Telegram-Live-Messskript fuer /e2e-verify Schritt 3c (#2541).

Spec: docs/specs/modules/fix_2541_telegram_live_messskript.md (AC-1 .. AC-9)

Pruefling: ``.claude/tools/staging_telegram_live.py`` -- aufgeloest RELATIV zu
dieser Testdatei und in JEDEM Test per ``importlib`` geladen (fehlt das
Werkzeug, scheitert jeder Test einzeln mit klarer Meldung, kein Sammel-ERROR).
Dazu das Gate ``.claude/hooks/e2e_telegram_live.py`` und
``.claude/hooks/staging_gate.py`` (Verdict).

Kern-Schicht: deterministisch, ohne Netz, keine Mock()/patch()/MagicMock.
Echte Dateien in ``tmp_path``, echte junit-XML-Texte im pytest-Format, echte
git-Repos fuer das Verdict-Gate, ein echtes Ersatz-``uv``-Programm (Shell-
Skript) als Beleg, dass pytest bei Umgebungsfehlern NICHT gestartet wird.
Der echte Lauf gegen Staging gehoert in die Live-Schicht (/e2e-verify, AC-10).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / ".claude" / "tools" / "staging_telegram_live.py"
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
LIVE_686 = REPO_ROOT / "tests" / "tdd" / "test_issue_686_telegram_functional_live.py"
LIVE_ZWEISPRACHIG = REPO_ROOT / "tests" / "tdd" / "test_telegram_live_zweisprachig.py"

# Soll-Live-Tests laut Spec (Stand 2026-11-27), bewusst als Literal und nicht
# aus dem Werkzeug abgeleitet (sonst tautologisch).
SOLL_686 = (
    "test_ac3_all_seven_commands_produce_meaningful_content",
    "test_ac4_live_delivery_and_cleanup",
    "test_ac25_live_menu_entspricht_der_vollstaendigen_ac21_liste",
    "test_ac24_hilfe_bei_trip_und_vergleich_antwortet_sofort_live",
    "test_heute_ohne_namen_bei_trip_und_vergleich_fragt_live_zurueck",
)
SOLL_ZWEISPRACHIG = ("test_hilfe_englisch_dann_deutsch_live",)
SOLL = frozenset(SOLL_686 + SOLL_ZWEISPRACHIG)
_KLASSE = {
    **{n: "tests.tdd.test_issue_686_telegram_functional_live" for n in SOLL_686},
    **{n: "tests.tdd.test_telegram_live_zweisprachig" for n in SOLL_ZWEISPRACHIG},
}

# Platzhalter-Geheimnisse (erfunden, Token-Form wie Telegram-Bot-Token).
CHAT_ID = "8346977700"
BOT_TOKEN = "123456789:AAH-PlatzhalterTokenPlatzhalterTok12"
FREMD_TOKEN = "987654321:ZZZ_abcdefghijklmnopqrstuvwxyz0123"  # nur Regel-Treffer
TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}")

SHA_A = "a" * 40
SHA_B = "b" * 40


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _lade(pfad: Path, name: str):
    if not pfad.exists():
        pytest.fail(f"Datei fehlt: {pfad.relative_to(REPO_ROOT)} "
                    "(Modul staging_telegram_live noch nicht implementiert)")
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


def _werkzeug():
    return _lade(TOOL_PATH, "staging_telegram_live_2541")


def _gate_hook():
    return _lade(HOOKS_DIR / "e2e_telegram_live.py", "e2e_telegram_live_2541")


def _staging_gate():
    return _lade(HOOKS_DIR / "staging_gate.py", "staging_gate_2541")


# ---------------------------------------------------------------------------
# Hilfen: junit-XML (Format wie pytest --junitxml), Nachweis, git-Repo
# ---------------------------------------------------------------------------

def _case(name: str, inhalt: str = "") -> str:
    klasse = _KLASSE.get(name.split("[")[0], "tests.tdd.test_issue_686_telegram_functional_live")
    if inhalt:
        return (f'<testcase classname="{klasse}" name="{name}" time="1.234">'
                f"{inhalt}</testcase>")
    return f'<testcase classname="{klasse}" name="{name}" time="1.234" />'


def _junit(cases: list[str], *, errors=0, failures=0, skipped=0, tests=None) -> str:
    tests = len(cases) if tests is None else tests
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<testsuites>"
        f'<testsuite name="pytest" errors="{errors}" failures="{failures}" '
        f'skipped="{skipped}" tests="{tests}" time="12.345" '
        'timestamp="2026-11-27T10:00:00.000000+00:00" hostname="staging">'
        + "".join(cases)
        + "</testsuite></testsuites>"
    )


def _gruen_xml() -> str:
    return _junit([_case(n) for n in SOLL_686 + SOLL_ZWEISPRACHIG])


def _nachweis(ordner: Path, datei_sha: str, *, commit: str | None = None,
              skipped=0, failures=0, errors=0, tests=None) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    namen = sorted(SOLL) if tests is None else list(tests)
    pfad = ordner / f"{datei_sha}.json"
    pfad.write_text(json.dumps({
        "commit": commit if commit is not None else datei_sha,
        "passed": len(namen),
        "skipped": skipped,
        "failures": failures,
        "errors": errors,
        "tests": namen,
        "finished_at": "2026-11-27T10:00:00+00:00",
    }))
    return pfad


def _git(repo: Path, *args) -> str:
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, text=True).stdout.strip()


def _repo_mit_letztem_commit(tmp_path: Path, relpfad: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    datei = repo / relpfad
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("# geaendert\n")
    _git(repo, "add", relpfad)
    _git(repo, "commit", "-m", "aenderung")
    return repo


def _ersatz_uv(tmp_path: Path) -> tuple[Path, Path]:
    """Echtes ausfuehrbares Ersatz-uv: hinterlaesst eine Markierung, falls es
    gestartet wird (Beleg 'pytest nicht gestartet')."""
    marker = tmp_path / "uv_wurde_gestartet"
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n")
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return uv, marker


# ---------------------------------------------------------------------------
# AC-1 — Umgebung ohne Aufrufer-Telegram-Werte, Opt-in, Befehlszeile
# ---------------------------------------------------------------------------

def test_env_ohne_telegram_werte_und_live_opt_in(tmp_path):
    mod = _werkzeug()
    umgebung = {
        "PATH": "/usr/local/bin:/usr/bin",
        "HOME": "/home/hem",
        "GZ_TELEGRAM_BOT_TOKEN": BOT_TOKEN,
        "GZ_TELEGRAM_TEST_CHAT_ID": CHAT_ID,
        "GZ_TELEGRAM_TEST_BOT_TOKEN": FREMD_TOKEN,
        "GZ_TELEGRAM_LIVE": "0",
        "GZ_ANDERES": "bleibt",
    }
    vorher = dict(umgebung)
    env = mod.baue_env(umgebung)

    assert umgebung == vorher, "baue_env darf die Aufrufer-Umgebung nicht veraendern"
    tg = {k: v for k, v in env.items() if k.startswith("GZ_TELEGRAM_")}
    assert tg == {"GZ_TELEGRAM_LIVE": "1"}, f"Aufrufer-Telegram-Werte erreichen pytest: {tg}"
    assert env["PATH"] == "/usr/local/bin:/usr/bin"
    assert env["HOME"] == "/home/hem"
    assert env["GZ_ANDERES"] == "bleibt"
    assert CHAT_ID not in json.dumps(env) and BOT_TOKEN not in json.dumps(env)

    junit = tmp_path / "ergebnis.xml"
    befehl = mod.baue_befehl(junit)
    assert befehl[:3] == ["uv", "run", "pytest"], befehl
    i = befehl.index("-m")
    assert befehl[i + 1] == "live", f"-m live fehlt: {befehl}"
    assert "tests/tdd/test_issue_686_telegram_functional_live.py" in befehl
    assert "tests/tdd/test_telegram_live_zweisprachig.py" in befehl
    j = befehl.index("-p")
    assert befehl[j + 1] == "no:cacheprovider"
    assert f"--junitxml={junit}" in befehl
    assert not any(CHAT_ID in t or BOT_TOKEN in t for t in befehl)


# ---------------------------------------------------------------------------
# AC-2 — junit-Auswertung
# ---------------------------------------------------------------------------

_TEARDOWN_FEHLER = (
    '<error message="failed on teardown with &quot;AssertionError: '
    'data/users/tg-live-e2e veraendert (#2226)&quot;">AssertionError</error>'
)

_BEFUNDE = {
    "null_tests": _junit([], tests=0),
    "ein_skipped": _junit(
        [_case(n) for n in SOLL_686]
        + [_case(SOLL_ZWEISPRACHIG[0],
                 '<skipped type="pytest.skip" message="GZ_TELEGRAM_LIVE=1 nicht gesetzt">'
                 "tests/tdd/test_telegram_live_zweisprachig.py:88: GZ_TELEGRAM_LIVE=1 "
                 "nicht gesetzt</skipped>")],
        skipped=1),
    "teardown_error": _junit(
        [_case(n) for n in SOLL_686 + SOLL_ZWEISPRACHIG]
        + [_case(SOLL_686[-1], _TEARDOWN_FEHLER)],
        errors=1, tests=6),
    "ein_failure": _junit(
        [_case(n) for n in SOLL_686[1:] + SOLL_ZWEISPRACHIG]
        + [_case(SOLL_686[0],
                 '<failure message="AssertionError: glance leer">'
                 "def test_ac3...\nE   AssertionError: glance leer</failure>")],
        failures=1),
    "soll_test_fehlt": _junit([_case(n) for n in SOLL_686[:-1] + SOLL_ZWEISPRACHIG]),
}


def test_junit_auswertung_gruen_und_alle_befundfaelle():
    mod = _werkzeug()

    code, erg = mod.werte_junit_aus(_gruen_xml())
    assert code == 0, f"alle Soll-Tests passed muss Exit 0 sein: {erg}"
    for feld in ("passed", "skipped", "failures", "errors", "tests"):
        assert feld in erg, f"Feld {feld!r} fehlt im Ergebnis: {erg}"
    assert erg["passed"] == 6
    assert (erg["skipped"], erg["failures"], erg["errors"]) == (0, 0, 0)
    assert SOLL <= set(erg["tests"])

    for fall, xml in _BEFUNDE.items():
        code, erg = mod.werte_junit_aus(xml)
        assert code == 1, f"Befund {fall!r} muss Exit 1 ergeben, war {code}: {erg}"

    _, erg = mod.werte_junit_aus(_BEFUNDE["ein_skipped"])
    assert erg["skipped"] == 1
    _, erg = mod.werte_junit_aus(_BEFUNDE["teardown_error"])
    assert erg["errors"] >= 1
    _, erg = mod.werte_junit_aus(_BEFUNDE["ein_failure"])
    assert erg["failures"] == 1

    code, _ = mod.werte_junit_aus("<testsuites><testsuite")
    assert code == 2, "ungueltiges XML ist ein Umgebungsfehler (Exit 2)"


# ---------------------------------------------------------------------------
# AC-3 — Umgebungsfehler: Exit 2, kein pytest-Start, kein Nachweis
# ---------------------------------------------------------------------------

def test_umgebungsfehler_ergeben_exit_2(tmp_path, capsys):
    mod = _werkzeug()
    uv, marker = _ersatz_uv(tmp_path)

    staging_ok = tmp_path / "staging_ok"
    staging_ok.mkdir()
    (staging_ok / ".env").write_text(
        f"GZ_TELEGRAM_BOT_TOKEN={BOT_TOKEN}\nGZ_TELEGRAM_TEST_CHAT_ID={CHAT_ID}\n")

    staging_ohne_env = tmp_path / "staging_ohne_env"
    staging_ohne_env.mkdir()
    staging_env_ordner = tmp_path / "staging_env_ordner"
    (staging_env_ordner / ".env").mkdir(parents=True)

    faelle = {
        "checkout_fehlt": ([str(tmp_path / "gibt_es_nicht")], str(uv), "gibt_es_nicht"),
        "uv_fehlt_pfad": ([str(staging_ok)], str(tmp_path / "kein" / "uv"), "uv"),
        "uv_fehlt_name": ([str(staging_ok)], "uv-gibt-es-nicht-2541", "uv"),
        "env_fehlt": ([str(staging_ohne_env)], str(uv), ".env"),
        "env_nicht_lesbar": ([str(staging_env_ordner)], str(uv), ".env"),
    }
    for fall, (staging, uv_arg, stichwort) in faelle.items():
        nachweis_dir = tmp_path / f"nachweis_{fall}"
        nachweis_dir.mkdir()
        rc = mod.main(["--staging-dir", staging[0], "--nachweis-dir", str(nachweis_dir),
                       "--uv", uv_arg])
        out = capsys.readouterr()
        text = out.out + out.err
        assert rc == 2, f"{fall}: Exit 2 erwartet, war {rc}"
        assert stichwort in text, f"{fall}: Meldung nennt die Ursache nicht: {text!r}"
        assert list(nachweis_dir.iterdir()) == [], f"{fall}: Nachweis trotz Umgebungsfehler"
        assert not marker.exists(), f"{fall}: uv/pytest wurde trotz Umgebungsfehler gestartet"
        assert CHAT_ID not in text and BOT_TOKEN not in text


# ---------------------------------------------------------------------------
# AC-4 — Maskierung
# ---------------------------------------------------------------------------

def test_maskierung_werte_und_token_regex():
    mod = _werkzeug()
    text = (f"chat_id={CHAT_ID} token={BOT_TOKEN} url=https://api.telegram.org/bot"
            f"{FREMD_TOKEN}/sendMessage kurz=12345:abc Chat ok")

    maskiert = mod.maskiere(text, [CHAT_ID, BOT_TOKEN, ""])
    assert CHAT_ID not in maskiert
    assert BOT_TOKEN not in maskiert
    assert FREMD_TOKEN not in maskiert, "Token-Regel greift nicht ohne bekannten Wert"
    assert not TOKEN_RE.search(maskiert)
    assert "Chat ok" in maskiert and "kurz=12345:abc" in maskiert, maskiert

    # nur Regel-Treffer, keine bekannten Werte
    nur_regel = mod.maskiere(f"Fehler bei {FREMD_TOKEN} im Lauf", [])
    assert FREMD_TOKEN not in nur_regel and "Fehler bei" in nur_regel

    # leerer Geheimniswert zerstoert den Text nicht
    assert mod.maskiere("unveraendert", [""]) == "unveraendert"


def test_ausgabe_und_nachweis_ohne_geheimnisse(tmp_path):
    mod = _werkzeug()
    geheim = [CHAT_ID, BOT_TOKEN]

    # Lauf mit Geheimnissen in Testnamen (Param-ID) und Fehlertext
    xml = _junit(
        [_case(n) for n in SOLL_686 + SOLL_ZWEISPRACHIG]
        + [_case(f"{SOLL_686[0]}[{CHAT_ID}]",
                 f'<failure message="chat {CHAT_ID} token {BOT_TOKEN}">'
                 f"E RuntimeError: {FREMD_TOKEN}</failure>")],
        failures=1)
    code, erg = mod.werte_junit_aus(xml)
    assert code == 1
    erg = dict(erg)
    erg["fehler"] = f"RuntimeError: chat {CHAT_ID} token {BOT_TOKEN} {FREMD_TOKEN}"

    bericht = mod.formatiere_bericht(erg, geheim)
    assert CHAT_ID not in bericht and BOT_TOKEN not in bericht and FREMD_TOKEN not in bericht
    assert not TOKEN_RE.search(bericht)

    # gruener Bericht nennt jeden Soll-Test (je Test eine Zeile)
    _, gruen = mod.werte_junit_aus(_gruen_xml())
    bericht_gruen = mod.formatiere_bericht(gruen, geheim)
    for name in SOLL:
        assert name in bericht_gruen, f"Bericht nennt {name} nicht"

    # Nachweis: Geheimnisse in Testnamen werden maskiert
    gruen_geheim = dict(gruen)
    gruen_geheim["tests"] = list(gruen["tests"]) + [f"test_x[{CHAT_ID}]", f"test_y[{FREMD_TOKEN}]"]
    pfad = mod.schreibe_nachweis(tmp_path / "nachweis", SHA_A, gruen_geheim, geheim)
    roh = Path(pfad).read_text()
    assert CHAT_ID not in roh and BOT_TOKEN not in roh and FREMD_TOKEN not in roh
    assert not TOKEN_RE.search(roh)


# ---------------------------------------------------------------------------
# AC-5 — Nachweis nur bei Exit 0, Pflichtfelder
# ---------------------------------------------------------------------------

def test_nachweis_nur_bei_exit_0_mit_pflichtfeldern(tmp_path):
    mod = _werkzeug()
    _, gruen = mod.werte_junit_aus(_gruen_xml())

    ordner = tmp_path / "e2e_telegram_live"
    pfad = Path(mod.schreibe_nachweis(ordner, SHA_A, gruen, []))
    assert pfad == ordner / f"{SHA_A}.json"
    daten = json.loads(pfad.read_text())
    assert daten["commit"] == SHA_A
    assert daten["passed"] == 6
    assert (daten["skipped"], daten["failures"], daten["errors"]) == (0, 0, 0)
    assert SOLL <= set(daten["tests"])
    datetime.fromisoformat(daten["finished_at"])

    # abschluss: nur Exit 0 schreibt
    ordner_ok = tmp_path / "ok"
    erg_ok = mod.abschluss(0, ordner_ok, SHA_B, gruen, [])
    assert erg_ok is not None and Path(erg_ok) == ordner_ok / f"{SHA_B}.json"
    assert Path(erg_ok).exists()

    for code in (1, 2):
        ordner_rot = tmp_path / f"rot_{code}"
        assert mod.abschluss(code, ordner_rot, SHA_B, gruen, []) is None
        assert not ordner_rot.exists() or list(ordner_rot.iterdir()) == []

    # frueherer Nachweis desselben Commits wird bei Exit != 0 weder gemeldet
    # noch neu geschrieben
    vorher_bytes = Path(erg_ok).read_bytes()
    vorher_mtime = Path(erg_ok).stat().st_mtime_ns
    _, rot = mod.werte_junit_aus(_BEFUNDE["ein_skipped"])
    for code in (1, 2):
        assert mod.abschluss(code, ordner_ok, SHA_B, rot, []) is None
    assert Path(erg_ok).read_bytes() == vorher_bytes
    assert Path(erg_ok).stat().st_mtime_ns == vorher_mtime


# ---------------------------------------------------------------------------
# AC-6 — Gate verlangt Nachweis fuer genau den verifizierten Commit
# ---------------------------------------------------------------------------

_GATE_FAELLE = {
    "gueltig": (lambda d: _nachweis(d, SHA_A), {}, 0),
    "anderer_commit_datei": (lambda d: _nachweis(d, SHA_B), {}, 1),
    "anderer_commit_feld": (lambda d: _nachweis(d, SHA_A, commit=SHA_B), {}, 1),
    "skipped_gt_0": (lambda d: _nachweis(d, SHA_A, skipped=1), {}, 1),
    "failures_gt_0": (lambda d: _nachweis(d, SHA_A, failures=1), {}, 1),
    "errors_gt_0": (lambda d: _nachweis(d, SHA_A, errors=1), {}, 1),
    "soll_test_fehlt": (lambda d: _nachweis(d, SHA_A, tests=sorted(SOLL)[1:]), {}, 1),
    "datei_fehlt": (lambda d: d.mkdir(parents=True, exist_ok=True), {}, 1),
    "kaputtes_json": (lambda d: (d.mkdir(parents=True, exist_ok=True),
                                 (d / f"{SHA_A}.json").write_text("{kaputt")), {}, 1),
    "nur_env_variable": (lambda d: d.mkdir(parents=True, exist_ok=True),
                         {"GZ_TELEGRAM_TEST_CHAT_ID": CHAT_ID,
                          "GZ_TELEGRAM_BOT_TOKEN": BOT_TOKEN,
                          "GZ_TELEGRAM_LIVE": "1"}, 1),
}


@pytest.mark.parametrize("fall", list(_GATE_FAELLE))
def test_gate_verlangt_nachweis_fuer_verifizierten_commit(fall, tmp_path):
    mod = _gate_hook()
    vorbereiten, env, erwartet = _GATE_FAELLE[fall]
    ordner = tmp_path / "e2e_telegram_live"
    vorbereiten(ordner)
    rc = mod.gate(scope_touches_telegram=True, commit=SHA_A, nachweis_dir=ordner, env=env)
    assert rc == erwartet, f"{fall}: Gate {rc}, erwartet {erwartet}"


def test_write_verdict_verlangt_nachweis_fuer_head_commit(tmp_path, monkeypatch):
    """Echtes Close-Gate: Telegram-Scope ohne Nachweis verweigert, auch mit
    gesetzter Chat-ID; mit gueltigem Nachweis fuer HEAD geht es durch."""
    repo = _repo_mit_letztem_commit(tmp_path, "src/outputs/telegram.py")
    head = _git(repo, "rev-parse", "HEAD")
    gate_mod = _staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)
    findings = tmp_path / "findings.json"
    findings.write_text("[]")
    out = tmp_path / "out.json"

    monkeypatch.setenv("GZ_TELEGRAM_TEST_CHAT_ID", CHAT_ID)
    rc = gate_mod.write_verdict("VERIFIED: test", findings, e2e_path=out, langs=["de", "en"])
    assert rc == 1, "Chat-ID im Environment ersetzt den Nachweis nicht"
    assert not out.exists()

    # Nachweis fuer einen ANDEREN Commit genuegt nicht
    nachweis_dir = repo / ".claude" / "e2e_telegram_live"
    _nachweis(nachweis_dir, SHA_B)
    rc = gate_mod.write_verdict("VERIFIED: test", findings, e2e_path=out, langs=["de", "en"])
    assert rc == 1 and not out.exists()

    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    _nachweis(nachweis_dir, head)
    rc = gate_mod.write_verdict("VERIFIED: test", findings, e2e_path=out, langs=["de", "en"])
    assert rc == 0, "gueltiger Nachweis fuer HEAD muss das Verdict erlauben"
    assert out.exists()


# ---------------------------------------------------------------------------
# AC-7 — ohne Telegram-Scope unveraendert
# ---------------------------------------------------------------------------

def test_gate_ohne_telegram_scope_laesst_durch(tmp_path, monkeypatch):
    mod = _gate_hook()
    leer = tmp_path / "leer"
    leer.mkdir()
    assert mod.gate(scope_touches_telegram=False, commit=SHA_A, nachweis_dir=leer, env={}) == 0
    assert mod.gate(scope_touches_telegram=False) == 0

    repo = _repo_mit_letztem_commit(tmp_path, "src/app/wetter_modell.py")
    gate_mod = _staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    findings = tmp_path / "findings.json"
    findings.write_text("[]")
    out = tmp_path / "out.json"
    rc = gate_mod.write_verdict("VERIFIED: test", findings, e2e_path=out, langs=["de", "en"])
    assert rc == 0, "ohne Telegram-Scope darf kein Telegram-Nachweis verlangt werden"
    assert out.exists()
    assert not (repo / ".claude" / "e2e_telegram_live").exists()


def test_prune_erfasst_nachweis_ordner_nicht(tmp_path):
    """Review-Punkt: das Aufraeumen der Staging-Attestationen loescht keine
    Telegram-Nachweise (eigener Ordner)."""
    gate_mod = _staging_gate()
    ordner = tmp_path / ".claude" / "e2e_telegram_live"
    for i in range(5):
        _nachweis(ordner, f"{i:040x}")
    gate_mod.prune_old_attestations(ordner, retention=1)
    assert len(list(ordner.glob("*.json"))) == 5


# ---------------------------------------------------------------------------
# AC-8 — Fingerabdruck des zweiten Nutzers
# ---------------------------------------------------------------------------

def _zweiter_nutzer(basis: Path) -> Path:
    d = basis / "data" / "users" / "zweiter-nutzer"
    (d / "trips").mkdir(parents=True)
    (d / "settings.json").write_text('{"language": "de"}')
    (d / "trips" / "gr20.json").write_text('{"name": "GR20", "stages": []}')
    return d


def test_fingerabdruck_erkennt_jede_aenderung_am_zweiten_nutzer(tmp_path):
    mod = _werkzeug()

    def _neu(name: str) -> tuple[Path, dict]:
        d = _zweiter_nutzer(tmp_path / name)
        return d, mod.fingerabdruck(d)

    # unveraendert (auch nur mtime beruehrt) => gleich
    d, fp = _neu("unveraendert")
    assert mod.fingerabdruck(d) == fp
    os.utime(d / "settings.json", (1_000_000_000, 1_000_000_000))
    assert mod.fingerabdruck(d) == fp

    # Datei geaendert, gleiche Groesse
    d, fp = _neu("geaendert")
    (d / "settings.json").write_text('{"language": "en"}')
    assert mod.fingerabdruck(d) != fp

    # Datei im Unterordner geaendert
    d, fp = _neu("geaendert_tief")
    (d / "trips" / "gr20.json").write_text('{"name": "GR21", "stages": []}')
    assert mod.fingerabdruck(d) != fp

    # Datei hinzugefuegt
    d, fp = _neu("hinzugefuegt")
    (d / "trips" / "neu.json").write_text("{}")
    assert mod.fingerabdruck(d) != fp

    # Datei geloescht
    d, fp = _neu("geloescht")
    (d / "trips" / "gr20.json").unlink()
    assert mod.fingerabdruck(d) != fp


# ---------------------------------------------------------------------------
# Synchronitaet SOLL_TESTS <-> tatsaechlich live-gegatete Tests
# ---------------------------------------------------------------------------

def _ist_live_gate(deko: ast.expr) -> bool:
    for knoten in ast.walk(deko):
        if isinstance(knoten, ast.Call):
            f = knoten.func
            if isinstance(f, ast.Name) and f.id == "live_telegram_enabled":
                return True
            if isinstance(f, ast.Attribute) and f.attr == "live_telegram_enabled":
                return True
    return False


def _live_gegatete_tests(pfad: Path) -> set[str]:
    baum = ast.parse(pfad.read_text())
    return {
        k.name for k in ast.walk(baum)
        if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef))
        and k.name.startswith("test_")
        and any(_ist_live_gate(d) for d in k.decorator_list)
    }


def test_soll_tests_synchron_mit_live_gegateten_tests():
    mod = _werkzeug()
    ist = _live_gegatete_tests(LIVE_686) | _live_gegatete_tests(LIVE_ZWEISPRACHIG)
    assert ist == SOLL, f"Spec-Liste veraltet: {sorted(ist ^ SOLL)}"
    assert set(mod.SOLL_TESTS) == ist, (
        f"SOLL_TESTS im Werkzeug nicht synchron: {sorted(set(mod.SOLL_TESTS) ^ ist)}")


# ---------------------------------------------------------------------------
# AC-9 — Doku
# ---------------------------------------------------------------------------

def test_rezept_und_gate_doku_vorhanden():
    # doc-compliance-test: prueft nur Pflicht-Stichworte der Doku, kein Verhalten.
    rezept = (REPO_ROOT / ".claude" / "commands" / "e2e-verify.md").read_text()
    assert "python3 .claude/tools/staging_telegram_live.py" in rezept
    assert "GZ_TELEGRAM_TEST_CHAT_ID=<" not in rezept, "alte Handrezeptur noch vorhanden"
    assert "GZ_TELEGRAM_BOT_TOKEN=<" not in rezept, "alte Handrezeptur noch vorhanden"

    gates = (REPO_ROOT / "docs" / "reference" / "gates_und_ratschen.md").read_text()
    abschnitte = re.split(r"\n(?=#{2,3} )", gates)
    treffer = [a for a in abschnitte
               if "e2e_telegram_live" in a and "Nachweis" in a and "Restrisiko" in a
               and "staging_telegram_live.py" in a]
    assert treffer, ("gates_und_ratschen.md: kein Abschnitt beschreibt das "
                     "e2e_telegram_live-Nachweis-Gate samt Werkzeug und Restrisiko")
