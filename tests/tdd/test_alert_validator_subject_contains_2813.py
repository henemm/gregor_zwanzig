"""Issue #2813 Teil 3: ``--subject-contains`` fuer die beiden Alarm-Validatoren.

Spec: docs/specs/bugfix/e2e_verify_en_mailweg_2813.md (AC-4, AC-5, AC-6, AC-7)

Ohne den Filter greift ``fetch_latest_message`` die NEUESTE Mail des Typs -- im
geteilten Postfach kann das eine fremde oder aeltere sein. Die Test-Mails hier
kommen aus dem ECHTEN Gate-Skript (Renderer + EmailOutput, Fixture ``draht``),
das Postfach ist ein kleines IMAP-Double (Test-Seam ``imap=``, existiert).
"""
from __future__ import annotations

import email
import importlib.util
import re
import sys
from email.header import decode_header, make_header
from pathlib import Path

import pytest

from tests.tdd.test_gate_testmails_zweisprachig import _sende, draht  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"

try:
    _probe = importlib.util.spec_from_file_location("_gz_hook_utils_probe_2813",
                                                    HOOKS / "hook_utils.py")
    _probe.loader.exec_module(importlib.util.module_from_spec(_probe))
except ImportError as exc:  # CI ohne Plugin (Vorbild test_official_alert_mail_validator)
    pytest.skip(f"agent-os-openspec-Plugin fehlt ({exc})", allow_module_level=True)

PFADE = {
    "official": "official_alert_mail_validator",
    "radar": "radar_alert_mail_validator",
}


def _validator(name: str):
    sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(f"{name}_2813", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Postfach:
    """Minimales IMAP-Double: Mails (roh) in Eingangsreihenfolge, id = 1..n."""

    def __init__(self, rohmails: list[str]):
        self._roh = [r.encode() for r in rohmails]
        self.vollabrufe: list[int] = []

    def select(self, _box):
        return "OK", [b""]

    def search(self, _charset, _kriterium):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self._roh)))]

    def fetch(self, mid, teil):
        roh = self._roh[int(mid) - 1]
        if "HEADER" in teil:
            return "OK", [(b"", roh.split(b"\n\n", 1)[0] + b"\n\n")]
        self.vollabrufe.append(int(mid))
        return "OK", [(b"", roh)]

    def close(self):
        pass

    def logout(self):
        pass


def _betreff(roh: str) -> str:
    return str(make_header(decode_header(email.message_from_string(roh)["Subject"])))


def _zwei_laeufe(draht, capsys, pfad: str) -> tuple[str, str, str, str]:
    """Zwei Gate-Laeufe: erst die 'aeltere', dann die 'frische' Mail. -> (alt, tok_alt, neu, tok_neu)."""
    alt, tok_alt = _sende(draht, capsys, "--only", pfad)
    neu, tok_neu = _sende(draht, capsys, "--only", pfad)
    assert tok_alt != tok_neu
    return alt[0][1], tok_alt, neu[0][1], tok_neu


@pytest.mark.parametrize("pfad", list(PFADE))
def test_gate_mail_betreff_traegt_den_lauf_token(draht, capsys, pfad):
    """AC-7: am ECHTEN Betreffaufbau gelesen, nicht angenommen."""
    mails, token = _sende(draht, capsys, "--only", pfad)
    assert token in _betreff(mails[0][1]), _betreff(mails[0][1])


@pytest.mark.parametrize("pfad", list(PFADE))
def test_filter_waehlt_die_mail_mit_token_nicht_die_neueste(draht, capsys, pfad):
    """AC-4/AC-5: die ALTE Mail wird gewaehlt, obwohl eine neuere desselben Typs im Postfach liegt."""
    alt, tok_alt, neu, tok_neu = _zwei_laeufe(draht, capsys, pfad)
    val = _validator(PFADE[pfad])
    box = _Postfach([alt, neu])  # neu ist die neueste
    gewaehlt = val.fetch_latest_message(subject_contains=tok_alt, imap=box)
    assert tok_alt in _betreff(gewaehlt.as_string())
    assert tok_neu not in _betreff(gewaehlt.as_string())
    # ohne Filter bleibt es beim bisherigen Verhalten: die neueste Mail
    ohne = val.fetch_latest_message(imap=_Postfach([alt, neu]))
    assert tok_neu in _betreff(ohne.as_string())


@pytest.mark.parametrize("pfad", list(PFADE))
def test_kein_treffer_ist_technischer_fehler_ohne_ausweichen(draht, capsys, pfad):
    """AC-6: nur eine alte Mail im Postfach, fremder Token => Fehler, keine Vollabfrage der alten Mail."""
    alt, _tok_alt, _neu, _tok_neu = _zwei_laeufe(draht, capsys, pfad)
    val = _validator(PFADE[pfad])
    box = _Postfach([alt])
    with pytest.raises(ValueError) as exc:
        val.fetch_latest_message(subject_contains="gibtesnicht0", imap=box)
    assert "subject_contains" in str(exc.value)
    assert box.vollabrufe == [], "die aeltere Mail darf nicht als Ersatz geholt werden"


@pytest.mark.parametrize("pfad", list(PFADE))
def test_cli_kein_treffer_endet_mit_exit_2(draht, capsys, monkeypatch, pfad):
    """AC-6 ueber die Kommandozeile: Exit 2 (technischer Fehler), nicht 0/1."""
    alt, _t, _n, _tn = _zwei_laeufe(draht, capsys, pfad)
    val = _validator(PFADE[pfad])
    box = _Postfach([alt])
    monkeypatch.setattr(val, "_open_test_imap", lambda: box)
    monkeypatch.setattr(sys, "argv", ["validator", "--subject-contains", "gibtesnicht0"])
    with pytest.raises(SystemExit) as exc:
        val.main()
    assert exc.value.code == 2
    ausgabe = capsys.readouterr()
    # Exit 2 allein genuegt nicht: argparse lehnt ein unbekanntes Argument ebenfalls mit 2 ab.
    assert "TECHNISCHER FEHLER" in ausgabe.out and "subject_contains" in ausgabe.out, ausgabe
    assert box.vollabrufe == []


@pytest.mark.parametrize("pfad", list(PFADE))
@pytest.mark.parametrize("leer", ["", "   "])
def test_leeres_fragment_wird_abgelehnt(draht, capsys, monkeypatch, pfad, leer):
    """AC-6: ein leeres Fragment steckt in JEDEM Betreff und schaltete den Filter still ab."""
    val = _validator(PFADE[pfad])
    box = _Postfach([])
    monkeypatch.setattr(val, "_open_test_imap", lambda: box)
    monkeypatch.setattr(sys, "argv", ["validator", "--subject-contains", leer])
    with pytest.raises(SystemExit) as exc:
        val.main()
    assert exc.value.code == 2
    fehler = capsys.readouterr()
    assert re.search(r"leer", fehler.err + fehler.out, re.I), fehler.err + fehler.out
    with pytest.raises(ValueError):
        val.fetch_latest_message(subject_contains=leer, imap=box)


@pytest.mark.parametrize("pfad", list(PFADE))
def test_filter_bleibt_mit_sprache_und_empfaenger_verknuepft(draht, capsys, pfad):
    """Betreff UND Sprache UND Empfaenger (mail_waehlbar) gelten gemeinsam."""
    alt, tok_alt, _neu, _tok_neu = _zwei_laeufe(draht, capsys, pfad)
    val = _validator(PFADE[pfad])
    with pytest.raises(ValueError):  # Token passt, aber die Mail ist de, gefordert en
        val.fetch_latest_message(subject_contains=tok_alt, lang="en",
                                 to_contains="+en@", imap=_Postfach([alt]))
