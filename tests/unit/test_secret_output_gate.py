"""Verhaltensnachweis fuer den Ausgabe-Waechter „Secret-Output-Sperre" (Stufe B).

Ein `PostToolUse`-Waechter durchsucht das ERGEBNIS jedes Werkzeugaufrufs nach dem
ausgeschriebenen Wert eines Geheimnisses aus der lokalen `.env` und ersetzt jeden Treffer
durch `***<SCHLUESSELNAME>***`, bevor Claude das Ergebnis sieht. Kein Fund heisst: Ergebnis
unveraendert und keinerlei Ausgabe. Jede eigene Stoerung heisst: Ergebnis unveraendert,
Exit 0 (durchgehend fail-open — der Waechter laeuft nach JEDEM Werkzeugaufruf in JEDER
Sitzung, ein Irrtum darf nie ein Ergebnis zerstoeren).

Kern-Schicht, deterministisch: jeder Fall baut ein eigenes Wegwerf-Projekt mit einer
SYNTHETISCHEN `.env` in `tmp_path` (nie die echte Projekt-`.env`) und ruft den Waechter als
echten Unterprozess mit stdin-JSON auf — kein Mock, kein patch(), kein Netz. `HOME` und
`CLAUDE_PROJECT_DIR` werden dabei bewusst auf Wegwerf-Pfade gezogen, damit die Suite unter
keinen Umstaenden gegen echte Zugangsdaten laeuft.

Pfadregel #1409: Der Pruefling wird relativ zu DIESER Datei aufgeloest, damit der Test aus
einem Worktree den Worktree-Stand prueft und nicht die Hauptrepo-Kopie.
"""
from __future__ import annotations

import importlib.util as _gz_ilu
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / ".claude" / "hooks"
# Ueberschreibbar fuer die Mutations-Gegenprobe: der Adversary mutiert eine EXTERNE Kopie im
# Scratchpad statt der geschuetzten Originaldatei — dafuer muss der Pruefling-Pfad umstellbar
# sein (Muster GZ_SECRET_GATE_PATH aus Scheibe 1). Ohne die Variable unveraendertes Verhalten.
GATE = Path(os.environ["GZ_SECRET_OUTPUT_GATE_PATH"]) \
    if os.environ.get("GZ_SECRET_OUTPUT_GATE_PATH") else HOOKS / "secret_output_gate.py"

# ------------------------------------------------------------------- Plugin-Sonde
# Der Waechter leiht sich die Geheimnis-Erkennung (collect_secrets, _is_secret_key,
# _is_secret_value) aus `core/hooks/secret_egress_guard.py` des Plugins agent-os-openspec.
# Ohne Plugin geht er fail-open — die Masking-Tests waeren dann strukturell rot. Sauber
# ueberspringen statt rot; auf dem Server (Plugin vorhanden) laeuft die Suite vollstaendig.
try:
    _gz_spec = _gz_ilu.spec_from_file_location("_gz_hook_utils_probe", HOOKS / "hook_utils.py")
    _gz_mod = _gz_ilu.module_from_spec(_gz_spec)
    _gz_spec.loader.exec_module(_gz_mod)
except ImportError as _gz_exc:
    pytest.skip(
        f"agent-os-openspec-Plugin fehlt ({_gz_exc}) — Hook-Suite braucht die "
        "installierten Server-Hooks (#1196)",
        allow_module_level=True,
    )


def _plugin_wurzel() -> Path | None:
    """Installationspfad des Plugins (gleicher Weg wie der Shim: die Registry)."""
    try:
        with open(os.path.expanduser("~/.claude/plugins/installed_plugins.json")) as fh:
            daten = json.load(fh)
        for schluessel, eintraege in daten.get("plugins", {}).items():
            if schluessel.startswith("agent-os-openspec@"):
                eintrag = next((e for e in eintraege if e.get("scope") == "user"), eintraege[0])
                return Path(eintrag.get("installPath", ""))
    except Exception:
        return None
    return None


_gz_wurzel = _plugin_wurzel()
if _gz_wurzel is None or not (_gz_wurzel / "core" / "hooks" / "secret_egress_guard.py").is_file():
    pytest.skip(
        "Plugin-Modul secret_egress_guard.py nicht auffindbar — der Waechter geht dann "
        "fail-open, die Masking-Faelle waeren strukturell rot",
        allow_module_level=True,
    )

# ------------------------------------------------------- synthetische Geheimnisse
# Frei erfunden, bewusst NICHT aus der echten Projekt-.env. Schluessel-Endung passt zur
# Erkennung, Wert lang genug (>= 8) und kein Platzhalter.
SCHLUESSEL = "GZ_FAKE_TEST_PASS"
WERT = "Zk8mQr2vLp9wXt4nBs6y"
ZWEITER_SCHLUESSEL = "GZ_FAKE_OTHER_TOKEN"
ZWEITER_WERT = "Hd3jWn7cVq1zRy5tKm8p"
KURZER_SCHLUESSEL = "GZ_FAKE_SHORT_KEY"
KURZER_WERT = "ab12cd"          # < 8 Zeichen -> nie ein Geheimnis
PLATZHALTER_SCHLUESSEL = "GZ_FAKE_DEMO_SECRET"
PLATZHALTER_WERT = "changeme"   # vom Platzhalter-Filter des Plugins erfasst

ERSATZ = f"***{SCHLUESSEL}***"
ZWEITER_ERSATZ = f"***{ZWEITER_SCHLUESSEL}***"


def _env_text() -> str:
    return (
        f"{SCHLUESSEL}={WERT}\n"
        f"{ZWEITER_SCHLUESSEL}={ZWEITER_WERT}\n"
        f"{KURZER_SCHLUESSEL}={KURZER_WERT}\n"
        f"{PLATZHALTER_SCHLUESSEL}={PLATZHALTER_WERT}\n"
    )


def _projekt(tmp_path: Path, mit_env: bool = True, zusatz_env: str = "") -> Path:
    ordner = tmp_path / "projekt"
    ordner.mkdir(exist_ok=True)
    if mit_env:
        (ordner / ".env").write_text(_env_text() + zusatz_env)
    return ordner


def _hook(tmp_path: Path, tool_name: str = "Bash", tool_response=None,
          tool_input: dict | None = None, roh_stdin: str | None = None,
          ohne_plugin: bool = False, zusatz_env: str = "") -> subprocess.CompletedProcess:
    """Ruft den Waechter wie die Hook-Schicht auf: stdin-JSON, cwd = Wegwerf-Projekt."""
    ordner = _projekt(tmp_path, zusatz_env=zusatz_env)
    eingabe = roh_stdin if roh_stdin is not None else json.dumps({
        "session_id": "wegwerf",
        "tool_name": tool_name,
        "tool_input": tool_input if tool_input is not None else {"command": "echo hallo"},
        "tool_response": tool_response,
    })
    env = dict(os.environ)
    # Der Waechter loest die .env ueber CLAUDE_PROJECT_DIR bzw. cwd auf — beide zeigen auf
    # das Wegwerf-Projekt, damit die echte Projekt-.env garantiert nie gelesen wird.
    env["CLAUDE_PROJECT_DIR"] = str(ordner)
    env.pop("CLAUDE_TOOL_INPUT", None)
    env.pop("CLAUDE_TOOL_NAME", None)
    if ohne_plugin:
        # Kein Mock: ein leeres HOME laesst die Plugin-Registry ins Leere laufen, der
        # importlib-Ladeweg scheitert echt.
        leeres_home = tmp_path / "leeres_home"
        leeres_home.mkdir(exist_ok=True)
        env["HOME"] = str(leeres_home)
    return subprocess.run(
        [sys.executable, str(GATE)], input=eingabe, cwd=str(ordner),
        capture_output=True, text=True, timeout=30, env=env,
    )


def _als_text(wert) -> str:
    return wert if isinstance(wert, str) else json.dumps(wert, ensure_ascii=False)


def _wirksames_ergebnis(r: subprocess.CompletedProcess, urspruenglich) -> str:
    """Das Ergebnis, das Claude NACH dem Waechter sieht — als Text.

    Die Ausgabeform steht in der RED-Phase noch nicht endgueltig fest (String vs.
    Originalstruktur unter `updatedToolOutput`; wird im Vorab-Experiment der
    Implementierungsphase geklaert). Dieser Leser ist deshalb bewusst tolerant und DARF
    in der Implementierungsphase nachgezogen werden — keine einzige Zusicherung der Tests
    aendert sich dadurch, weil hier nur "was sieht Claude am Ende" bestimmt wird.
    """
    roh = r.stdout.strip()
    if not roh:
        return _als_text(urspruenglich)   # keine Ausgabe = Ergebnis unveraendert
    try:
        daten = json.loads(roh)
    except json.JSONDecodeError:
        return roh
    if isinstance(daten, dict):
        hso = daten.get("hookSpecificOutput")
        if isinstance(hso, dict) and "updatedToolOutput" in hso:
            return _als_text(hso["updatedToolOutput"])
        for schluessel in ("updatedToolOutput", "tool_response", "toolOutput"):
            if schluessel in daten:
                return _als_text(daten[schluessel])
    return roh


def _gesamtausgabe(r: subprocess.CompletedProcess) -> str:
    return r.stdout + r.stderr


def _bash_erfolg(stdout: str) -> dict:
    """Gemessene Gestalt eines erfolgreichen Bash-Ergebnisses (33.681 Faelle)."""
    return {"stdout": stdout, "stderr": "", "interrupted": False,
            "isImage": False, "noOutputExpected": False}


# ------------------------------------------------------------------------ Faelle


def test_gate_silent_when_no_secret_found(tmp_path):
    """(AC-1) Kein Fund -> Ergebnis unveraendert und KEINERLEI Ausgabe."""
    antwort = _bash_erfolg("alles ganz normal, kein Geheimnis weit und breit\n")
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Ohne Fund darf nie etwas anderes als Exit 0 kommen: {_gesamtausgabe(r)}"
    assert r.stdout == "", f"Ohne Fund darf es keinerlei stdout geben, bekam: {r.stdout!r}"
    assert r.stderr == "", f"Ohne Fund darf es keinerlei stderr geben, bekam: {r.stderr!r}"


def test_gate_masks_secret_in_bash_success_stdout(tmp_path):
    """(AC-2) Geheimnis im stdout eines erfolgreichen Bash-Ergebnisses -> maskiert."""
    antwort = _bash_erfolg(f"SMTP-Login: {WERT}\n")
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Geheimniswert steht weiterhin im Klartext im Ergebnis: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt im Ergebnis: {wirksam!r}"


def test_gate_masks_secret_in_bash_failure_string_result(tmp_path):
    """(AC-3) Fehlschlag-Ergebnis kommt als REINER STRING zurueck (2.576 gemessene Faelle)."""
    antwort = f"Error: Exit code 1\nauth failed with password {WERT}\n"
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"String-Form (Fehlschlag) wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"
    assert "Error: Exit code 1" in wirksam, f"Fehlertext ging verloren: {wirksam!r}"


def test_gate_masks_secret_in_read_nested_file_content(tmp_path):
    """(AC-4) Read: Inhalt liegt VERSCHACHTELT unter `file.content` — der wahrscheinlichste
    Austrittsweg ueberhaupt (jede Datei, die ein Geheimnis im Klartext traegt)."""
    antwort = {"type": "text", "file": {
        "filePath": "/wegwerf/altes_skript.sh",
        "content": f"#!/bin/sh\nexport SMTP_PASS={WERT}\n",
        "numLines": 2, "startLine": 1, "totalLines": 2}}
    r = _hook(tmp_path, "Read", antwort, tool_input={"file_path": "/wegwerf/altes_skript.sh"})
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Verschachtelter Read-Inhalt wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def test_gate_masks_secret_in_write_content(tmp_path):
    """(AC-5) Write: Inhalt liegt auf OBERSTER Ebene unter `content`."""
    antwort = {"type": "create", "filePath": "/wegwerf/neu.txt",
               "content": f"passwort = {WERT}\n", "structuredPatch": []}
    r = _hook(tmp_path, "Write", antwort,
              tool_input={"file_path": "/wegwerf/neu.txt", "content": "..."})
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Write-content wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def _edit_antwort(feld: str) -> dict:
    """Gemessene Edit-Gestalt: oldString/newString/originalFile, KEIN stdout/content."""
    antwort = {"filePath": "/wegwerf/datei.py", "oldString": "alt", "newString": "neu",
               "originalFile": "unveraenderter Rest\n", "structuredPatch": [],
               "userModified": False, "replaceAll": False}
    antwort[feld] = f"zeile davor\n{WERT}\nzeile danach\n"
    return antwort


def test_gate_masks_secret_in_edit_old_string(tmp_path):
    """(AC-6) Geheimnis in `oldString` — einzeln geprueft, damit kein Feld durchrutscht."""
    antwort = _edit_antwort("oldString")
    r = _hook(tmp_path, "Edit", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Edit.oldString wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def test_gate_masks_secret_in_edit_new_string(tmp_path):
    """(AC-6) Geheimnis in `newString`."""
    antwort = _edit_antwort("newString")
    r = _hook(tmp_path, "Edit", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Edit.newString wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def test_gate_masks_secret_in_edit_original_file(tmp_path):
    """(AC-6) Geheimnis in `originalFile` — traegt den GESAMTEN Dateiinhalt vor der
    Aenderung und ist damit der ergiebigste der drei Edit-Wege."""
    antwort = _edit_antwort("originalFile")
    r = _hook(tmp_path, "Edit", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Edit.originalFile wurde nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def test_gate_ignores_short_values(tmp_path):
    """(AC-7) Ein zu kurzer .env-Wert ist KEIN Geheimnis — sonst traefe der Waechter
    staendig harmlosen Text."""
    antwort = _bash_erfolg(f"kurzwert={KURZER_WERT} — voellig harmlos\n")
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Kurzer Wert haette nichts ausloesen duerfen: {_gesamtausgabe(r)}"
    assert r.stdout == "" and r.stderr == "", (
        f"Kurzer Wert hat eine Maskierung/Meldung ausgeloest: {_gesamtausgabe(r)!r}"
    )


def test_gate_ignores_known_placeholder_values(tmp_path):
    """(AC-7) Bekannter Platzhalterwert (`changeme`) ist KEIN Geheimnis."""
    antwort = _bash_erfolg(f"password={PLATZHALTER_WERT} (Beispielkonfiguration)\n")
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Platzhalter haette nichts ausloesen duerfen: {_gesamtausgabe(r)}"
    assert r.stdout == "" and r.stderr == "", (
        f"Platzhalterwert hat eine Maskierung/Meldung ausgeloest: {_gesamtausgabe(r)!r}"
    )


def test_gate_fail_open_when_plugin_missing(tmp_path):
    """(AC-8) Plugin nicht ladbar -> Ergebnis unveraendert durchgereicht, Exit 0.

    Der Waechter laeuft nach JEDEM Werkzeugaufruf: eine eigene Stoerung darf niemals ein
    Ergebnis zerstoeren oder eine Sitzung blockieren.
    """
    antwort = _bash_erfolg(f"SMTP-Login: {WERT}\n")
    r = _hook(tmp_path, "Bash", antwort, ohne_plugin=True)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Eigene Stoerung haette nie blockieren duerfen: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert WERT in wirksam, (
        "Ohne Erkennung muss das Ergebnis UNVERAENDERT durchgereicht werden — "
        f"der Waechter hat es angetastet: {wirksam!r}"
    )
    assert ERSATZ not in wirksam, f"Ohne Plugin kann es keine echte Maskierung geben: {wirksam!r}"


def test_gate_fail_open_on_malformed_stdin_json(tmp_path):
    """(AC-8) Kaputtes JSON auf stdin -> Exit 0, kein veraendertes Ergebnis, kein Absturz.

    Seit F005 gehoert dazu die zweite Haelfte: fail-open heisst nicht mehr lautlos. Eine
    unlesbare Nutzlast bedeutet NICHT geprueft — und ungeprueft durchgereicht sieht sonst
    genauso aus wie geprueft und sauber. Der Wert im Kaputt-Text ist bewusst ein echtes
    Geheimnis: eine kaputte Nutzlast ist der wahrscheinlichste Ort, an dem ein Geheimnis in
    einen Fehlertext geraet, und der Waechter darf ihn deshalb nie mit ausgeben.
    """
    r = _hook(tmp_path, roh_stdin=f'{{ "tool_name": "Bash", {WERT} kein JSON')
    assert r.returncode == 0, f"Kaputtes stdin haette nie blockieren duerfen: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert "updatedToolOutput" not in r.stdout, (
        f"Ohne lesbare Nutzlast darf kein Ersatz-Ergebnis erzeugt werden: {r.stdout!r}"
    )
    assert r.stderr.strip() != "", (
        "Eine unlesbare Nutzlast wurde NICHT geprueft — das darf nicht lautlos aussehen wie "
        "'geprueft, nichts gefunden'"
    )
    assert WERT not in _gesamtausgabe(r), (
        "Der Waechter hat den Geheimniswert aus der kaputten Nutzlast in seine eigene "
        f"Meldung geschrieben: {_gesamtausgabe(r)!r}"
    )


def test_gate_fail_open_on_unexpected_tool_response_type(tmp_path):
    """(AC-8) `tool_response` von unerwartetem Typ (null, Zahl, Liste) -> Exit 0, kein Absturz."""
    for antwort in (None, 42, [1, 2, 3], True):
        r = _hook(tmp_path, "Bash", antwort)
        assert r.returncode == 0, (
            f"tool_response={antwort!r} haette nie blockieren duerfen: {_gesamtausgabe(r)}"
        )
        assert "Traceback" not in r.stderr, (
            f"tool_response={antwort!r} hat den Waechter abstuerzen lassen: {r.stderr}"
        )


def test_masking_message_never_contains_the_secret_value(tmp_path):
    """(AC-9) Wichtigste Einzelzusicherung: in KEINER Ausgabe des Waechters (stdout wie
    stderr) darf der rohe Wert auftauchen — nur der Schluesselname."""
    antwort = _bash_erfolg(f"login ok mit {WERT}\n")
    r = _hook(tmp_path, "Bash", antwort)
    gesamt = _gesamtausgabe(r)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {gesamt}"
    assert gesamt.strip() != "", "Ein echter Fund muss ueberhaupt eine Wirkung erzeugen"
    assert WERT not in gesamt, (
        "Der Geheimniswert selbst ist in der Ausgabe des Waechters aufgetaucht — das ist "
        f"die wichtigste verbotene Wirkung dieses Gates: {gesamt!r}"
    )
    assert SCHLUESSEL in gesamt, f"Der Schluesselname fehlt in der Ausgabe: {gesamt!r}"


def test_gate_masks_regardless_of_tool_name(tmp_path):
    """(AC-10) Es gibt keine Positivliste: auch ein unbekanntes (MCP-)Werkzeug wird maskiert."""
    antwort = {"result": f"Antwort des Dienstes: token={WERT}", "status": "ok"}
    r = _hook(tmp_path, "AnyMcpTool", antwort, tool_input={"frage": "irgendwas"})
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Unbekanntes Werkzeug wurde ausgenommen: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"


def test_gate_preserves_surrounding_text_and_other_fields(tmp_path):
    """(AC-11) Ausschliesslich der Wert wird ersetzt — alles andere kommt unversehrt an.

    Der einzige Test, der eine Umsetzung faengt, die das GESAMTE Ergebnis durch einen
    Platzhalter ersetzt: der Wert waere dann weg (ACs 2-6 gruen), aber auch jede nutzbare
    Ausgabe. Deshalb wird hier POSITIV geprueft: Text davor, Text danach und die uebrigen
    Felder muessen vorhanden sein.
    """
    davor = "zeile-davor-marker-4711: Verbindung wird aufgebaut"
    danach = "zeile-danach-marker-4712: Verbindung geschlossen"
    stderr_marker = "hinweis-marker-4713: nur ein Warnhinweis"
    antwort = {"stdout": f"{davor}\npass={WERT}\n{danach}\n", "stderr": stderr_marker,
               "interrupted": False, "isImage": False}
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, f"Wert nicht maskiert: {wirksam!r}"
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"
    assert davor in wirksam, f"Text VOR dem Wert ging verloren: {wirksam!r}"
    assert danach in wirksam, f"Text NACH dem Wert ging verloren: {wirksam!r}"
    assert stderr_marker in wirksam, f"Feld `stderr` ging verloren: {wirksam!r}"
    assert "interrupted" in wirksam, f"Feld `interrupted` ging verloren: {wirksam!r}"


def test_gate_masks_every_occurrence_and_multiple_secrets(tmp_path):
    """(AC-12) Derselbe Wert an DREI Stellen plus ein ZWEITES Geheimnis an einer vierten —
    kein einziges Vorkommen darf uebrig bleiben (faengt "nur der erste Treffer")."""
    antwort = {
        "stdout": f"erster: {WERT}\nzweiter: {WERT}\n",
        "stderr": f"dritter: {WERT}\n",
        "interrupted": False,
        "details": {"weiteres_geheimnis": f"vierter: {ZWEITER_WERT}"},
    }
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    gesamt = _gesamtausgabe(r)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {gesamt}"
    assert WERT not in wirksam, f"Nicht jedes Vorkommen wurde ersetzt: {wirksam!r}"
    assert ZWEITER_WERT not in wirksam, f"Das zweite Geheimnis blieb im Klartext: {wirksam!r}"
    assert wirksam.count(ERSATZ) >= 3, (
        f"Erwartet 3 Ersetzungen von {SCHLUESSEL}, gefunden {wirksam.count(ERSATZ)}: {wirksam!r}"
    )
    assert ZWEITER_ERSATZ in wirksam, f"Ersatzform {ZWEITER_ERSATZ} fehlt: {wirksam!r}"
    assert WERT not in gesamt and ZWEITER_WERT not in gesamt, (
        f"Ein Geheimniswert steht in der Gesamtausgabe des Waechters: {gesamt!r}"
    )


def test_replacement_keeps_every_original_key_and_is_not_a_string(tmp_path):
    """(AC-13) Der Ersatz hat die Gestalt, die die Plattform tatsaechlich annimmt.

    Gemessen (2026-08-07, neun Laeufe einer eigenstaendigen Sitzung mit Zufallsmarker):
    ein String oder ein unvollstaendiges Objekt als `updatedToolOutput` wird von der
    Plattform STILLSCHWEIGEND VERWORFEN — kein Fehler, kein Hinweis, Hook-Exit 0, auch
    unter `--debug hooks` keine Diagnosezeile. Ein Waechter mit falscher Gestalt ist von
    einem funktionierenden nicht unterscheidbar und waere in JEDEM anderen Test hier
    gruen, waehrend er nachweislich nichts bewirkt.

    Deshalb wird hier nicht der Inhalt geprueft (das tun die ACs 2-6, 10-12), sondern die
    GESTALT: der Ersatz traegt jeden Schluessel des urspruenglichen Ergebnisses und ist
    kein blosser Text.
    """
    antwort = _bash_erfolg(f"login ok mit {WERT}\n")   # die fuenf gemessenen Bash-Schluessel
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    roh = r.stdout.strip()
    assert roh != "", "Ein echter Fund muss ueberhaupt einen Ersatz erzeugen"

    daten = json.loads(roh)
    hso = daten.get("hookSpecificOutput")
    assert isinstance(hso, dict), f"`hookSpecificOutput` fehlt oder ist kein Objekt: {roh!r}"
    assert hso.get("hookEventName") == "PostToolUse", (
        f"Falscher hookEventName — die Plattform ordnet den Ersatz sonst nicht zu: {roh!r}"
    )
    assert "updatedToolOutput" in hso, f"`updatedToolOutput` fehlt: {roh!r}"

    ersatz = hso["updatedToolOutput"]
    assert not isinstance(ersatz, str), (
        "Der Ersatz ist ein String — gemessen: die Plattform verwirft das lautlos, der "
        f"Waechter waere wirkungslos: {ersatz!r}"
    )
    assert isinstance(ersatz, dict), (
        f"Ein Objekt-Ergebnis muss als Objekt ersetzt werden, bekam {type(ersatz).__name__}"
    )
    fehlend = set(antwort) - set(ersatz)
    assert not fehlend, (
        f"Dem Ersatz fehlen Schluessel des Originals {sorted(fehlend)} — gemessen: ein "
        f"unvollstaendiges Objekt wird lautlos verworfen. Ersatz-Schluessel: {sorted(ersatz)}"
    )


# ------------------------------------- Schluesselnamen und Verschachtelungstiefe
# Befunde der Adversary-Runden, alle scheiterten LAUTLOS — genau die Fehlerart, gegen die
# dieser Waechter ueberhaupt existiert:
#   F001: geprueft wurden nur dict-WERTE, nie dict-SCHLUESSEL.
#   F002/F003: die feste Tiefengrenze (`_MAX_TIEFE = 25`) liess tiefere Ebenen ungeprueft.
#     Die Meldung dieser Grenze verletzte zugleich AC-1 (stumm im Normalfall): sie erschien
#     auch bei voellig harmlosen tiefen Nutzlasten. Die Grenze ist deshalb ersatzlos
#     gefallen — die Traversierung laeuft iterativ, es gibt nichts mehr zu melden.


def test_gate_masks_secret_used_as_nested_key(tmp_path):
    """(F001) Ein Geheimnis als SCHLUESSELNAME unterhalb der obersten Ebene wird maskiert.

    Unterhalb der obersten Ebene prueft die Plattform die Schluesselmenge nicht — dort
    darf (und muss) umbenannt werden. Die uebrigen Felder bleiben dabei erhalten.
    """
    nachbar_marker = "nachbar-marker-4714"
    antwort = {
        "stdout": "Konfiguration geladen\n",
        "stderr": "",
        "interrupted": False,
        "details": {f"token_{WERT}": "gehoert zu diesem Dienst", "nachbar": nachbar_marker},
    }
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, (
        f"Geheimnis als verschachtelter SCHLUESSELNAME blieb im Klartext: {wirksam!r}"
    )
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt im Schluesselnamen: {wirksam!r}"
    assert nachbar_marker in wirksam, (
        f"Nachbarfeld ging beim Umbenennen des Schluessels verloren: {wirksam!r}"
    )
    daten = json.loads(r.stdout.strip())
    ersatz = daten["hookSpecificOutput"]["updatedToolOutput"]
    assert set(ersatz) == set(antwort), (
        "Die OBERSTE Schluesselmenge muss unangetastet bleiben (AC-13), auch wenn weiter "
        f"unten umbenannt wird. Original {sorted(antwort)}, Ersatz {sorted(ersatz)}"
    )
    assert set(ersatz["details"]) != set(antwort["details"]), (
        "Unterhalb der obersten Ebene wurde der Schluessel NICHT umbenannt: "
        f"{sorted(ersatz['details'])}"
    )


def test_gate_reports_secret_in_top_level_key_without_renaming_it(tmp_path):
    """(F001) Auf der OBERSTEN Ebene wird ein Geheimnis im Schluesselnamen gemeldet, aber
    nicht umbenannt.

    Gemessen (AC-13): fehlt dem Ersatz ein Schluessel des Originals, verwirft die Plattform
    den GESAMTEN Ersatz stillschweigend — dann blieben auch alle WERTE unmaskiert. Aus einer
    Teilluecke wuerde ein Totalausfall. Also: Schluesselmenge unveraendert lassen UND laut
    melden. Die Meldung nennt den Schluessel in MASKIERTER Form, nie den rohen Wert.
    """
    schluessel_mit_geheimnis = f"token_{WERT}_ende"
    antwort = {
        "stdout": f"login ok mit {ZWEITER_WERT}\n",
        "stderr": "",
        "interrupted": False,
        schluessel_mit_geheimnis: "harmloser Begleitwert",
    }
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"

    daten = json.loads(r.stdout.strip())
    ersatz = daten["hookSpecificOutput"]["updatedToolOutput"]
    assert set(ersatz) == set(antwort), (
        "Die Schluesselmenge auf oberster Ebene wurde veraendert — gemessen: die Plattform "
        f"verwirft den Ersatz dann komplett. Original {sorted(antwort)}, Ersatz {sorted(ersatz)}"
    )
    assert ZWEITER_WERT not in json.dumps(ersatz), (
        "Die Werte-Maskierung muss trotz des Sonderfalls unveraendert weiterlaufen"
    )

    assert r.stderr.strip() != "", (
        "Ein Geheimnis im obersten Schluesselnamen darf NICHT lautlos durchgehen"
    )
    assert f"token_{ERSATZ}_ende" in r.stderr, (
        f"Die Meldung nennt den (maskierten) Schluesselnamen nicht: {r.stderr!r}"
    )
    assert WERT not in r.stderr, (
        f"Der rohe Geheimniswert steht in der Meldung des Waechters: {r.stderr!r}"
    )
    assert "Bash" in r.stderr, f"Die Meldung nennt das Werkzeug nicht: {r.stderr!r}"


def _tief_verschachtelt(ebenen: int, blatt: str) -> dict:
    knoten: dict = {"ebene": "blatt", "inhalt": blatt}
    for i in range(ebenen):
        knoten = {"ebene": f"e{i}", "tiefer": knoten}
    return knoten


def test_gate_stays_silent_on_deeply_nested_harmless_payload(tmp_path):
    """(F003, AC-1) Eine tief verschachtelte, voellig HARMLOSE Nutzlast erzeugt keinerlei
    Ausgabe.

    Bauvorgabe 1 ist unbedingt: kein Fund heisst keinerlei stdout UND keinerlei stderr. Eine
    Meldung ueber die eigene Pruefgrenze verletzt das — sie erschien auch dann, wenn im
    gesamten Ergebnis kein einziger Geheimniswert steckt, und machte den Normalfall laut.
    """
    antwort = {"stdout": "nichts auffaelliges\n", "stderr": "", "interrupted": False,
               "details": _tief_verschachtelt(30, "voellig harmlos")}
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert r.stdout == "", (
        f"Ohne Fund darf es keinerlei stdout geben, bekam: {r.stdout!r}"
    )
    assert r.stderr == "", (
        "Ohne Fund darf es keinerlei stderr geben — auch nicht ueber die eigene "
        f"Pruefgrenze, bekam: {r.stderr!r}"
    )


def test_gate_main_runs_to_completion_without_swallowed_error(tmp_path):
    """Kein VERSCHLUCKTER Fehler in `main()` — von aussen sonst unsichtbar.

    Der Waechter faengt am Modulende JEDE Ausnahme ab (Bauvorgabe 2, fail-open) und endet
    dann mit Exit 0 und leerem stderr — also exakt so wie ein sauberer Durchlauf. Jeder
    andere Test hier kann deshalb gruen sein, waehrend `main()` in Wahrheit auf halber
    Strecke abbricht: gemessen am 2026-08-08, als ein Zugriff auf eine entfernte Notiz einen
    `KeyError` warf und die volle Suite trotzdem gruen blieb.

    Deshalb hier derselbe Aufruf OHNE den auffangenden `__main__`-Block: `runpy.run_path`
    laedt das Modul unter einem anderen Namen, `main()` wird direkt gerufen. Eine Ausnahme
    schlaegt dann als echter Traceback mit Exit != 0 durch. Kein Mock — echter Unterprozess,
    echtes stdin, Wegwerf-Projekt wie in `_hook`.
    """
    ordner = _projekt(tmp_path)
    eingabe = json.dumps({
        "session_id": "wegwerf", "tool_name": "Bash", "tool_input": {"command": "echo hallo"},
        # Gewoehnliches dict-Ergebnis ohne jeden Geheimniswert: der Normalfall, der bis ans
        # Ende von main() laeuft (ein frueher Rueckgabewert wuerde nichts beweisen).
        "tool_response": _bash_erfolg("alles ganz normal\n"),
    })
    ohne_auffang = (
        "import runpy, sys;"
        f"m = runpy.run_path({str(GATE)!r}, run_name='_probe_ohne_auffang');"
        "sys.exit(m['main']())"
    )
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(ordner)
    r = subprocess.run([sys.executable, "-c", ohne_auffang], input=eingabe, cwd=str(ordner),
                       capture_output=True, text=True, timeout=30, env=env)
    assert "Traceback" not in r.stderr, (
        f"Eine Ausnahme lief in main() bis nach oben — im echten Lauf verschluckt sie der "
        f"auffangende __main__-Block lautlos: {r.stderr}"
    )
    assert r.returncode == 0, f"main() endete nicht mit 0: {r.returncode}, {r.stderr!r}"
    assert r.stdout == "" and r.stderr == "", (
        f"Der Normalfall muss stumm bleiben: stdout={r.stdout!r} stderr={r.stderr!r}"
    )


def test_gate_masks_secret_far_below_former_depth_limit(tmp_path):
    """(F002/F003) Ein Geheimnis 40 Ebenen tief wird maskiert — es gibt keine eigene
    Tiefengrenze mehr.

    Frueher brach die Pruefung bei Ebene 25 ab: der Wert unterhalb blieb im Klartext und der
    Waechter kuendigte seinen eigenen blinden Fleck an. Beides faellt weg — die Traversierung
    laeuft iterativ ueber einen Stapel und erreicht jedes Blatt.
    """
    antwort = {"stdout": "nichts auffaelliges\n", "stderr": "", "interrupted": False,
               "details": _tief_verschachtelt(40, f"pass={WERT}")}
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert WERT not in wirksam, (
        f"Geheimnis 40 Ebenen tief blieb im Klartext — die Pruefung bricht ab: {wirksam!r}"
    )
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"
    meldung = r.stderr.lower()
    assert not ("tief" in meldung and "nicht mehr" in meldung), (
        f"Es darf keine Meldung ueber eine Tiefengrenze mehr geben: {r.stderr!r}"
    )
    assert WERT not in _gesamtausgabe(r), (
        f"Der rohe Geheimniswert steht in der Ausgabe des Waechters: {_gesamtausgabe(r)!r}"
    )


# ------------------------------------ Kopiergrenze, Listen und der Notfall-Pfad
# Drei Befunde der Adversary-Runde 3. Der erste ist der schwerste, den dieser Waechter
# ueberhaupt haben kann: er scheiterte STILL und liess dabei den Wert im Klartext stehen.
#   F005: `copy.deepcopy` warf ab Tiefe ~497 einen RecursionError. Der Notfall-Handler fing
#         ihn ab, bevor `main()` irgendetwas ausgegeben hatte -> von "kein Fund" nicht
#         unterscheidbar, waehrend die Plattform das Ergebnis MIT Geheimnis weiterreichte.
#   F006: kein Test legte je ein Geheimnis als blossen LISTENEINTRAG ab.
#   F007: den aeusseren Notfall-Handler loeste kein einziger Test je aus.


def test_gate_masks_secret_deeper_than_the_copy_recursion_limit(tmp_path):
    """(F005) Ein Geheimnis unterhalb der frueheren Kopier-Grenze (~497) wird maskiert.

    Der schwerste denkbare Fehler dieses Waechters: er bricht ab, BEVOR er etwas ausgegeben
    hat, und schweigt dabei — die Plattform reicht das Ergebnis dann unveraendert und mit dem
    Wert im Klartext weiter. Von aussen sieht das exakt aus wie "geprueft, nichts gefunden".
    """
    antwort = {"stdout": "nichts auffaelliges\n", "stderr": "", "interrupted": False,
               "details": _tief_verschachtelt(600, f"pass={WERT}")}
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert WERT not in wirksam, (
        "Geheimnis 600 Ebenen tief blieb im Klartext — die Kopie bricht ab und der Waechter "
        f"schweigt dazu: stdout={r.stdout[:120]!r} stderr={r.stderr!r}"
    )
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"
    assert WERT not in _gesamtausgabe(r), (
        f"Der rohe Geheimniswert steht in der Ausgabe des Waechters: {_gesamtausgabe(r)!r}"
    )


def test_gate_masks_secret_as_plain_list_element(tmp_path):
    """(F006) Ein Geheimnis als blosser LISTENEINTRAG — nicht als dict-Wert.

    Gemischte Form (Liste in dict in Liste), weil genau diese Kombination bisher von keinem
    Test beruehrt wurde: eine abgeschaltete Listen-Traversierung machte 0 von 23 Tests rot.
    Die Nachbareintraege muessen dabei an ihrer Stelle bleiben.
    """
    antwort = {
        "stdout": "Konfiguration geladen\n",
        "stderr": "",
        "interrupted": False,
        "eintraege": ["harmlos-vorher", {"weitere": [f"pass={WERT}", "harmlos-nachher"]}],
    }
    r = _hook(tmp_path, "Bash", antwort)
    wirksam = _wirksames_ergebnis(r, antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    assert WERT not in wirksam, (
        f"Geheimnis als reiner Listeneintrag blieb im Klartext: {wirksam!r}"
    )
    assert ERSATZ in wirksam, f"Ersatzform {ERSATZ} fehlt: {wirksam!r}"
    daten = json.loads(r.stdout.strip())
    ersatz = daten["hookSpecificOutput"]["updatedToolOutput"]
    assert ersatz["eintraege"][0] == "harmlos-vorher", (
        f"Der Eintrag VOR dem Treffer wurde veraendert: {ersatz['eintraege'][0]!r}"
    )
    assert ersatz["eintraege"][1]["weitere"][1] == "harmlos-nachher", (
        f"Der Eintrag NACH dem Treffer ging verloren: {ersatz['eintraege'][1]!r}"
    )
    assert ersatz["eintraege"][1]["weitere"][0] == f"pass={ERSATZ}", (
        f"Der Listeneintrag wurde nicht an Ort und Stelle ersetzt: {ersatz['eintraege'][1]!r}"
    )


# `extra_key_patterns` des Plugins wird zur Laufzeit als regulaerer Ausdruck ausgewertet
# (`_is_secret_key`). Ein unvollstaendiger Ausdruck laesst die Erkennung MITTEN im Lauf
# scheitern — ein echter, ohne Mock herstellbarer Ausloeser fuer den Notfall-Pfad.
KAPUTTE_KONFIG = 'secret_egress_guard:\n  extra_key_patterns:\n    - "("\n'
# Schluessel, den KEIN eingebautes Muster trifft — sonst greift `any()` schon vorher und der
# kaputte Ausdruck wird nie ausgewertet.
UNVERDAECHTIGE_ZEILE = "GZ_FAKE_NOTIZ=beliebiger_text\n"


def test_gate_reports_when_the_inspection_could_not_finish(tmp_path):
    """(F005 Teil 2 / F007) Bricht die Pruefung mit einem Fehler ab, SAGT der Waechter das.

    Bis hierher galt: jede eigene Stoerung endet lautlos mit Exit 0. Fuer eine Stoerung VOR
    der Maskierung heisst das aber, dass das Ergebnis MIT dem Geheimnis weitergereicht wird —
    und niemand erfaehrt davon. Fail-open bleibt (Exit 0, Ergebnis unangetastet), aber nicht
    mehr stumm. Ab jetzt gilt: stumm ist der Waechter nur, wenn er vollstaendig geprueft und
    nichts gefunden hat.

    Die Meldung darf ausschliesslich den Ausnahme-TYP nennen, nie deren Text: eine
    Fehlermeldung kann Bruchstuecke der Nutzlast tragen.
    """
    antwort = _bash_erfolg(f"SMTP-Login: {WERT}\n")
    ordner = tmp_path / "projekt"
    ordner.mkdir(exist_ok=True)
    (ordner / "openspec.yaml").write_text(KAPUTTE_KONFIG)
    r = _hook(tmp_path, "Bash", antwort, zusatz_env=UNVERDAECHTIGE_ZEILE)
    wirksam = _wirksames_ergebnis(r, antwort)

    assert r.returncode == 0, f"Eine eigene Stoerung darf nie blockieren: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert WERT in wirksam, (
        "Fail-open heisst: das Ergebnis wird UNVERAENDERT durchgereicht — der Waechter hat "
        f"es angetastet: {wirksam!r}"
    )
    assert r.stderr.strip() != "", (
        "Eine abgebrochene Pruefung darf NICHT lautlos bleiben — sonst ist sie von "
        "'geprueft, nichts gefunden' nicht zu unterscheiden, waehrend der Wert sichtbar bleibt"
    )
    assert "Bash" in r.stderr, f"Die Meldung nennt das Werkzeug nicht: {r.stderr!r}"
    assert "unterminated subpattern" not in r.stderr, (
        "Der TEXT der Ausnahme steht in der Meldung — er kann Bruchstuecke der Nutzlast "
        f"tragen. Erlaubt ist nur der Typ: {r.stderr!r}"
    )
    assert WERT not in _gesamtausgabe(r), (
        f"Der rohe Geheimniswert steht in der Ausgabe des Waechters: {_gesamtausgabe(r)!r}"
    )


def test_gate_masks_secret_close_to_the_parse_limit(tmp_path):
    """(F005) Auch dicht UNTER der neuen Obergrenze wird noch maskiert.

    Tiefe 600 (Test oben) beweist nur, dass die alte `deepcopy`-Schranke weg ist — nicht,
    dass wirklich nirgends mehr Rekursion steckt. Hier laeuft die volle Kette (Einlesen,
    Kopieren, Traversieren, Ausgeben) knapp unterhalb der gemessenen Grenze von 9997.
    """
    antwort = {"stdout": "nichts auffaelliges\n", "stderr": "", "interrupted": False,
               "details": _tief_verschachtelt(9_900, f"pass={WERT}")}
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {r.stderr[:300]}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr[:300]}"
    assert ERSATZ in r.stdout, (
        f"Knapp unter der Obergrenze wurde nicht maskiert: stderr={r.stderr[:300]!r}"
    )
    assert WERT not in _gesamtausgabe(r), (
        "Der rohe Geheimniswert steht in der Ausgabe des Waechters"
    )


def test_gate_reports_when_the_payload_cannot_be_parsed(tmp_path):
    """(F005 Teil 2) Dasselbe an der NEUEN Obergrenze: unlesbare Nutzlast wird gemeldet.

    Nach dem Wegfall von `copy.deepcopy` liegt die Grenze bei `json.loads` (gemessen: Tiefe
    9997 geht, 9998 wirft `RecursionError`). Bliebe der Waechter dort stumm, waere derselbe
    Fehler nur um vier Groessenordnungen verschoben: Wert sichtbar, niemand erfaehrt es.
    """
    tiefe = 10_000
    nutzlast = ('{"tool_name": "Bash", "tool_response": '
                + '{"a": ' * tiefe + f'"pass={WERT}"' + "}" * tiefe + "}")
    r = _hook(tmp_path, roh_stdin=nutzlast)
    assert r.returncode == 0, f"Eine eigene Stoerung darf nie blockieren: {_gesamtausgabe(r)}"
    assert "Traceback" not in r.stderr, f"Der Waechter ist abgestuerzt: {r.stderr}"
    assert "updatedToolOutput" not in r.stdout, (
        f"Ohne lesbare Nutzlast darf kein Ersatz-Ergebnis erzeugt werden: {r.stdout[:200]!r}"
    )
    assert r.stderr.strip() != "", (
        "Eine nicht lesbare Nutzlast bedeutet: NICHT geprueft. Das darf nicht lautlos "
        "aussehen wie 'geprueft, nichts gefunden'"
    )
    assert WERT not in _gesamtausgabe(r), (
        f"Der rohe Geheimniswert steht in der Ausgabe des Waechters: {_gesamtausgabe(r)!r}"
    )


# ------------------------------------------------------ Schluesselreihenfolge
# F009 (Runde 6): der Docstring von `_tiefe_kopie` sagte die Reihenfolge als
# Plattform-Anforderung zu, ohne dass ein Test sie hielt (Mutation: 0 von 27 rot).
#
# F008 aus derselben Runde ist BEWUSST NICHT behoben und hat deshalb hier auch keinen Test:
# der Werkzeugname aus `tool_name` wird ungeprueft in die Meldungen gedruckt. Die Luecke
# steht als bekannte Grenze in der Spec, nicht als dauerhaft roter Test im Korpus.


def test_replacement_keeps_the_original_key_order(tmp_path):
    """(F009) Die Schluesselreihenfolge des Originals bleibt erhalten — auch verschachtelt.

    Belegt ist als Plattform-Anforderung nur die Schluessel-MENGE (fehlt einer, wird der
    gesamte Ersatz verworfen; neun gemessene Laeufe). Ob die REIHENFOLGE zaehlt, ist nie
    gemessen worden. Sie kostet nichts, ist im Zweifel die naeherliegende Gestalt — und eine
    Zusage im Code, die kein Test haelt, ist genau das, was hier mehrfach schiefging.
    """
    antwort = {"zuerst": "eins", "stdout": f"pass={WERT}\n", "dann": "zwei",
               "interrupted": False, "zuletzt": {"b": "B", "a": "A", "c": "C"}}
    r = _hook(tmp_path, "Bash", antwort)
    assert r.returncode == 0, f"Der Waechter darf nie blockieren: {_gesamtausgabe(r)}"
    daten = json.loads(r.stdout.strip())
    ersatz = daten["hookSpecificOutput"]["updatedToolOutput"]
    assert list(ersatz) == list(antwort), (
        f"Die Schluesselreihenfolge auf oberster Ebene wurde veraendert: {list(ersatz)}"
    )
    assert list(ersatz["zuletzt"]) == list(antwort["zuletzt"]), (
        f"Die Schluesselreihenfolge weiter unten wurde veraendert: {list(ersatz['zuletzt'])}"
    )
