"""TDD tests for Issue #384 — Hook-Infrastruktur fail-open härten.

Verifiziert, dass JEDER in `.claude/settings.json` registrierte
`${CLAUDE_PROJECT_DIR}`-Hook so eingebunden ist, dass eine **fehlende**
Hook-Datei das Tool ERLAUBT (fail-open), während eine **vorhandene**
Hook-Datei bei echtem Verstoß (Exit 2) weiterhin BLOCKT (fail-closed).

KEINE MOCKS: Die Tests lesen die echten Command-Strings aus settings.json
und führen sie als echte Subprozesse aus. `${CLAUDE_PROJECT_DIR}` wird auf
eine isolierte tmp-Sandbox gezeigt, in der die An-/Abwesenheit der Hook-Datei
gesteuert wird. Stub-Hooks (`sys.exit(0/2)`) ersetzen die echten Gates, damit
keine reale Gate-Logik mitläuft.

Exit-Code-Kontrakt (Claude Code PreToolUse):
- 0 -> Tool erlaubt
- 2 -> Tool blockiert

Spec: docs/specs/modules/issue_384_hook_fail_open.md
Test-Manifest: docs/specs/tests/issue_384_hook_fail_open_tests.md
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"

# Relativer Hook-Pfad innerhalb eines Command-Strings, z. B. ".claude/hooks/secrets_guard.py"
# NUR fuer Test-IDs und den Sandbox-Pfad der Laufzeit-Tests — NIE als Filter, ob ein
# Eintrag geprueft wird (genau das war Befund F003: `new-risky-gate.py` matcht nicht).
_HOOK_RE = re.compile(r"\.claude/hooks/[A-Za-z0-9_]+\.py")

# Ausdrueckliche Ausnahmen von der Fail-open-Pflicht. Greift NUR bei exakter
# Uebereinstimmung des ganzen Command-Strings — Teilstring-Vergleich wuerde die
# Umgehung sofort wieder oeffnen. Die Ausnahme verhindert nichts, sie macht die
# Entscheidung zitierbar (Muster: `gz-main-path`, #1409).
_GUARD_EXEMPT_COMMANDS = frozenset({
    # Externes Skript ausserhalb .claude/hooks/, kein Waechter dieses Repos: es kann
    # nichts blockieren, sein Fehlen loest keinen Tool-Lockout aus (#1307 A).
    "bash /home/hem/claude-mq/check-messages.sh",
})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def _hook_groups() -> list[dict]:
    """Alle Gruppen unter hooks.<Ereignis>[] mit ihrer Position."""
    settings = _load_settings()
    return [
        {"event": event, "gi": gi, "group": group}
        for event, groups in settings.get("hooks", {}).items()
        for gi, group in enumerate(groups)
    ]


def _iter_hook_entries():
    """Alle Hook-Eintraege der settings.json mit ihrer Position.

    Eine Gruppe ohne `hooks`-Schluessel liefert hier nichts — das bleibt aber NICHT
    unsichtbar: `test_every_hook_group_is_wellformed` macht genau diesen Fall zu
    einem eigenen roten Testfall (Befund F004).
    """
    for g in _hook_groups():
        for hi, hook in enumerate(g["group"].get("hooks", [])):
            yield {
                "event": g["event"], "gi": g["gi"], "hi": hi,
                "cmd": hook.get("command", ""),
            }


def _hook_commands() -> list[dict]:
    """JEDER Hook-Eintrag der settings.json — ohne jeden Muster-Filter.

    Die Frage ist bewusst umgedreht: NICHT "erkenne ich hier einen Wächter-Aufruf?"
    (dann rutscht jede unerkannte Schreibweise durch — Befund F002: absoluter Pfad
    statt ${CLAUDE_PROJECT_DIR}; Befund F003: Bindestrich im Dateinamen), sondern
    "bin ich sicher, dass dieser Eintrag KEINEN Wächter aufruft?". Sicher ist das
    nur bei den ausdruecklich aufgelisteten Ausnahmen in `_GUARD_EXEMPT_COMMANDS`.
    Alles andere wird geprueft. Vorbild: `hook_utils.is_git_subcommand` (#1431) und
    die `gz-main-path`-Ausnahmen (#1409).
    """
    return list(_iter_hook_entries())


def _project_dir_commands() -> list[dict]:
    """Teilmenge der Hook-Eintraege: nur Commands mit ${CLAUDE_PROJECT_DIR}.

    Diese Einschraenkung gilt ausschliesslich fuer die drei Laufzeit-Tests, die
    den Command wirklich ausfuehren. Sie steuern die An-/Abwesenheit der
    Hook-Datei ueber eine tmp-Sandbox, auf die ${CLAUDE_PROJECT_DIR} zeigt — ein
    absolut ausgeschriebener Pfad ignoriert die Variable und liesse sich von der
    Sandbox nicht kontrollieren (der Test wuerde die echte Datei am echten Ort
    treffen). Fachlich begruendete Grenze, keine Nachlaessigkeit: die FORM jedes
    Eintrags prueft `test_every_hook_is_fail_open_guarded` ueber `_hook_commands()`.
    """
    return [c for c in _hook_commands() if "CLAUDE_PROJECT_DIR" in c["cmd"]]


def _hook_relpath(cmd: str) -> str:
    m = _HOOK_RE.search(cmd)
    assert m, f"Kein .claude/hooks/<name>.py im Command gefunden: {cmd!r}"
    return m.group(0)


def _param_id(c: dict) -> str:
    """Test-ID; benennt den Eintrag auch dann, wenn kein Hook-Pfad erkennbar ist.

    Ohne Rueckfall wuerde ein Eintrag in unbekannter Schreibweise beim Sammeln
    knallen, statt als benannter Testfall aufzutauchen — AC-5 verlangt aber, dass
    der betroffene Eintrag benannt wird.
    """
    m = _HOOK_RE.search(c["cmd"])
    name = m.group(0).split("/")[-1] if m else "kein-erkannter-hook-pfad"
    return f"{name}-{c['event']}-{c['gi']}{c['hi']}"


def _is_fail_open_guarded(cmd: str) -> bool:
    """Fail-open-Muster: `if [ -f … ]; then python3 … ; fi`.

    Die naive Form `python3 … || exit 0` ist VERBOTEN (würde echte Blocks
    aufweichen) und matcht hier bewusst NICHT.
    """
    s = cmd.strip()
    return s.startswith("if [ -f ") and "; then " in s and s.endswith("fi")


def _run(cmd: str, project_dir: Path) -> int:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    proc = subprocess.run(
        cmd, shell=True, env=env, capture_output=True, timeout=30, text=True
    )
    return proc.returncode


def _sandbox(tmp_path: Path, hook_relpath: str, stub_exit: int | None) -> Path:
    """Isolierte CLAUDE_PROJECT_DIR-Sandbox.

    stub_exit is None  -> Hook-Datei FEHLT (leeres .claude/hooks-Verzeichnis).
    stub_exit == 0/2   -> Hook-Datei vorhanden, ein Stub der mit diesem Code endet.
    """
    (tmp_path / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    if stub_exit is not None:
        target = tmp_path / hook_relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"import sys\nsys.exit({stub_exit})\n", encoding="utf-8")
    return tmp_path


def _build_params(commands: list[dict]) -> list:
    """Baut die Parameter-Liste aus echten Command-Strings der settings.json.

    Ohne Ausnahme-Mechanik (#1307 Scheibe A): ein ungeschuetzt eingetragener
    Hook macht die Form-Pruefung sofort rot, statt als "bekannt offen" gruen
    durchzulaufen."""
    return [pytest.param(c["cmd"], id=_param_id(c)) for c in commands]


# Form-Pruefung: JEDER Hook-Eintrag, ohne Ausnahme-Filter beim Sammeln.
_PARAMS_ALL = _build_params(_hook_commands())
# Laufzeit-Tests: nur was die tmp-Sandbox ueber ${CLAUDE_PROJECT_DIR} steuern kann.
_PARAMS_SANDBOX = _build_params(_project_dir_commands())
# Struktur-Pruefung: jede Gruppe, damit kein Eintrag unbemerkt ins Leere laeuft.
_GROUP_PARAMS = [
    pytest.param(g, id=f"{g['event']}-{g['gi']}") for g in _hook_groups()
]

# Schluessel, die eine Hook-Gruppe tragen darf.
_ERLAUBTE_GRUPPEN_SCHLUESSEL = {"matcher", "hooks"}


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_settings_json_is_valid_json():
    """AC-6: settings.json bleibt valides JSON (auch mit eingebettetem if … fi)."""
    data = _load_settings()
    assert isinstance(data, dict)
    assert "hooks" in data


@pytest.mark.parametrize("g", _GROUP_PARAMS)
def test_every_hook_group_is_wellformed(g):
    """AC-5 auf Struktur-Ebene: eine Gruppe darf nicht ins Leere laufen.

    GIVEN eine Gruppe unter hooks.<Ereignis>[]
    WHEN ihre Schluessel geprüft werden
    THEN traegt sie einen `hooks`-Schluessel und keine unbekannten Schluessel.

    Schadensbild (Befund F004): Bei `"hook"` statt `"hooks"` fuehrt Claude Code den
    enthaltenen Eintrag NICHT aus. Es entsteht keine Totalblockade — es entsteht das
    Gegenteil und fuer dieses Ticket Schlimmere: ein Waechter, den jemand eintraegt
    und fuer aktiv haelt, tut stillschweigend nichts. Eine Regel, die dasteht und
    nicht beisst. Ohne diesen Test faellt der Eintrag aus JEDER Pruefung heraus,
    weil er gar nicht erst eingesammelt wird.
    """
    ort = f"hooks.{g['event']}[{g['gi']}]"
    unbekannt = set(g["group"]) - _ERLAUBTE_GRUPPEN_SCHLUESSEL
    assert "hooks" in g["group"], (
        f"Hook-Gruppe {ort} hat keinen 'hooks'-Schlüssel (vorhanden: "
        f"{sorted(g['group'])}). Claude Code ignoriert diese Gruppe stillschweigend "
        "— jeder darin eingetragene Wächter läuft NIE, ohne dass es auffällt. "
        "Vermutlich ein Tippfehler, z.B. 'hook' statt 'hooks'."
    )
    assert not unbekannt, (
        f"Hook-Gruppe {ort} hat unbekannte Schlüssel {sorted(unbekannt)} — erlaubt "
        f"sind nur {sorted(_ERLAUBTE_GRUPPEN_SCHLUESSEL)}. Was Claude Code nicht "
        "kennt, wertet es nicht aus; der Inhalt wirkt dann nur scheinbar."
    )


@pytest.mark.parametrize("cmd", _PARAMS_ALL)
def test_every_hook_is_fail_open_guarded(cmd):
    """AC-5: JEDER Hook-Eintrag muss fail-open-gewrappt sein — oder ausgenommen.

    GIVEN ein in settings.json registrierter Hook-Eintrag, gleich in welcher
          Schreibweise (${CLAUDE_PROJECT_DIR}, absoluter Pfad, Bindestrich im
          Dateinamen, Zwischenschale …)
    WHEN sein Command-String geprüft wird
    THEN entspricht er dem Muster `if [ -f … ]; then python3 … ; fi` — es sei denn,
         er steht wortgleich in `_GUARD_EXEMPT_COMMANDS`
         (Schutz gegen erneutes Aufreißen des Lockout-Lochs).
    """
    if cmd.strip() in _GUARD_EXEMPT_COMMANDS:
        return  # ausdrueckliche, im Code sichtbare Ausnahme
    assert _is_fail_open_guarded(cmd), (
        "Hook-Command ist NICHT fail-open-gewrappt — fehlende Datei würde das "
        f"Tool blockieren (Lockout): {cmd!r}. Entweder in die Form "
        "`if [ -f \"<pfad>\" ]; then python3 \"<pfad>\"; fi` bringen ODER wortgleich "
        "in _GUARD_EXEMPT_COMMANDS eintragen (mit Begründung)."
    )


@pytest.mark.parametrize("cmd", _PARAMS_SANDBOX)
def test_missing_hook_file_allows_tool(cmd, tmp_path):
    """AC-1 / AC-3: fehlende Hook-Datei -> Tool erlaubt (Exit 0), kein Lockout.

    GIVEN der echte Command-String aus settings.json
    WHEN er läuft, während die Hook-Datei im Working-Tree FEHLT
    THEN ist der Exit-Code 0 (fail-open) — nicht 2 (block).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=None)  # Datei fehlt
    rc = _run(cmd, sandbox)
    assert rc == 0, (
        f"Fehlende Hook-Datei führte zu Exit {rc} (erwartet 0). Genau dieser "
        f"fail-closed-Pfad löst den Total-Tool-Lockout aus: {cmd!r}"
    )


@pytest.mark.parametrize("cmd", _PARAMS_SANDBOX)
def test_present_blocking_hook_still_blocks(cmd, tmp_path):
    """AC-2: vorhandener Hook, der mit Exit 2 blockt -> Block bleibt wirksam.

    GIVEN der echte Command-String aus settings.json
    WHEN die Hook-Datei vorhanden ist und mit Exit 2 blockt
    THEN propagiert Exit 2 (kein Aufweichen durch die fail-open-Logik).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=2)  # Datei da, blockt
    rc = _run(cmd, sandbox)
    assert rc == 2, (
        f"Blockender Hook (Exit 2) ergab Exit {rc} — die fail-open-Logik darf "
        f"echte Blocks NICHT aufweichen: {cmd!r}"
    )


@pytest.mark.parametrize("cmd", _PARAMS_SANDBOX)
def test_present_ok_hook_allows(cmd, tmp_path):
    """AC-4: vorhandener Hook mit Exit 0 -> Tool erlaubt, unverändertes Verhalten.

    GIVEN der echte Command-String aus settings.json
    WHEN die Hook-Datei vorhanden ist und mit Exit 0 endet
    THEN ist der Exit-Code 0 (bestehende Gates verhalten sich unverändert).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=0)  # Datei da, erlaubt
    rc = _run(cmd, sandbox)
    assert rc == 0, (
        f"OK-Hook (Exit 0) ergab Exit {rc} — vorhandene Gates müssen unverändert "
        f"durchlassen: {cmd!r}"
    )
