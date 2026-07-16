"""RED-Tests: nebenbefund_gate False-Positives (#1197).

Deterministische Kern-Schicht, kein Netz, kein Mock der Gate-Logik. Der Gate
liest JSON von stdin (`tool_input.command`) und liefert einen Exit-Code
(0 = durchlassen, 2 = blockieren). Wir laden das Hook-Modul per importlib und
rufen `main()` mit echtem stdin-JSON auf. Ehrliche Seams:

  * stdin: `sys.stdin` wird auf ein `io.StringIO` mit echtem JSON gesetzt.
  * Zeit (AC-8): `mod.date` wird durch eine FakeDate mit fixem `today()` ersetzt.

Body-Dateien (AC-2/AC-3) werden real in `tmp_path` geschrieben und im Kommando
per `--body-file <pfad>` referenziert.

Erwartet (vor Fix): AC-2 und AC-4 sind ROT (Body-Datei ungelesen bzw.
Substring-Trigger im zitierten Text). AC-7 ist ggf. ROT, siehe Docstring dort.
"""
import importlib.util
import io
import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / ".claude" / "hooks" / "nebenbefund_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("nebenbefund_gate_under_test", GATE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gate():
    return _load_gate()


def _run(mod, monkeypatch, cmd):
    """Setzt echtes stdin-JSON und ruft main() auf. Gibt den Exit-Code zurueck."""
    payload = json.dumps({"tool_input": {"command": cmd}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    return mod.main()


# --- AC-1: Marker direkt im Befehl -> durchlassen (Guard, gruen) ---------------
def test_ac1_marker_in_command_passes(gate, monkeypatch):
    cmd = (
        "gh issue create --repo henemm/gregor_zwanzig "
        '--title x --body "Kaputt [triage:c] behoben"'
    )
    assert _run(gate, monkeypatch, cmd) == 0


# --- AC-2: Marker in --body-file, nicht im Befehl -> durchlassen (ROT) ----------
def test_ac2_marker_in_body_file_passes(gate, monkeypatch, tmp_path):
    body = tmp_path / "issue_body.md"
    body.write_text("Ausfuehrliche Beschreibung.\n\n[triage:b]\n")
    cmd = f"gh issue create --repo henemm/gregor_zwanzig --title x --body-file {body}"
    assert _run(gate, monkeypatch, cmd) == 0, (
        "Marker in der Body-Datei muss wie ein Marker im Befehl durchgelassen werden"
    )


# --- AC-3: kein Marker in Datei UND kein Marker im Befehl -> blocken (Guard) -----
def test_ac3_no_marker_anywhere_blocks(gate, monkeypatch, tmp_path):
    body = tmp_path / "issue_body.md"
    body.write_text("Beschreibung ohne jeden Triage-Marker.\n")
    cmd = f"gh issue create --repo henemm/gregor_zwanzig --title x --body-file {body}"
    assert _run(gate, monkeypatch, cmd) == 2, (
        "Ohne Marker (weder Datei noch Befehl) muss der Gate weiter blocken"
    )


# --- AC-4: 'gh issue create' nur als zitierter Text -> durchlassen (ROT) ---------
def test_ac4_quoted_phrase_is_not_a_create_call(gate, monkeypatch):
    cmd = (
        "gh issue comment 1197 --repo henemm/gregor_zwanzig "
        '--body "Wir erwaehnen die Phrase gh issue create nur als Zitat hier."'
    )
    assert _run(gate, monkeypatch, cmd) == 0, (
        "Zitierter Text 'gh issue create' ist kein echter create-Aufruf -> kein Block"
    )


# --- AC-5: echter create ohne Marker, ohne Body-File -> blocken (Guard) ----------
def test_ac5_real_create_without_marker_blocks(gate, monkeypatch):
    cmd = "gh issue create --repo henemm/gregor_zwanzig --title x --body Kurz"
    assert _run(gate, monkeypatch, cmd) == 2


# --- AC-6: anderes Repo ohne Marker -> durchlassen (Guard) -----------------------
def test_ac6_other_repo_passes(gate, monkeypatch):
    cmd = "gh issue create --repo henemm/henemm-infra --title x --body Kurz"
    assert _run(gate, monkeypatch, cmd) == 0


# --- AC-7: unbalancierte Quotes -> fail-open (ROT bzw. Guard) --------------------
def test_ac7_unbalanced_quotes_fail_open(gate, monkeypatch):
    # shlex kann diesen Befehl nicht parsen (offenes Anfuehrungszeichen).
    # Erwartet: fail-open (0). Aktuell greift der Substring-Trigger
    # ('gh issue create' vorhanden) und blockt -> ROT, dokumentiert.
    cmd = 'gh issue create --repo henemm/gregor_zwanzig --body "offen'
    assert _run(gate, monkeypatch, cmd) == 0, (
        "Ein von shlex nicht parsebarer Befehl darf niemals blockieren (fail-open)"
    )


# --- AC-5 (Adversary-Repro): Case-Variante des echten Repos -> blocken -----------
def test_ac5_case_variant_real_repo_blocks(gate, monkeypatch):
    # 'Gregor_Zwanzig' ist GitHub-identisch zum echten Repo (case-insensitiv).
    # Ohne Marker muss der Gate blocken; der case-sensitive Vergleich liess das
    # frueher durch (Bypass). Repro: vor Fix ROT (0), nach Fix GRUEN (2).
    cmd = "gh issue create --repo henemm/Gregor_Zwanzig --title x --body Kurz"
    assert _run(gate, monkeypatch, cmd) == 2, (
        "Gross-/Kleinschreibungs-Variante des echten Repos muss geblockt werden"
    )


# --- AC-6 (Gegen-Guard): wirklich fremdes Repo bleibt fremd, auch mixed-case -----
def test_ac6_mixed_case_org_only_still_foreign(gate, monkeypatch):
    cmd = "gh issue create --repo Henemm/Henemm-Infra --title x --body Kurz"
    assert _run(gate, monkeypatch, cmd) == 0, (
        "Ein echt fremdes Repo darf durch den case-insensitiven Vergleich nicht "
        "faelschlich geblockt werden"
    )


# --- AC-8: Pruefdatum ueberschritten -> Selbstdeaktivierung (Guard) --------------
def test_ac8_after_expiry_passes(gate, monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 10)  # > EXPIRY 2026-10-09

    monkeypatch.setattr(gate, "date", FakeDate)
    cmd = "gh issue create --repo henemm/gregor_zwanzig --title x --body Kurz"
    assert _run(gate, monkeypatch, cmd) == 0
