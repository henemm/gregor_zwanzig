"""Issue #2813 Teil 2: ``send_gate_test_mails.py --lang en`` bricht im Worktree laut ab.

Spec: docs/specs/bugfix/e2e_verify_en_mailweg_2813.md (AC-1, AC-2, AC-3)

Hintergrund: Die Herkunftssperre #1476 (``EmailOutput``) schreibt das To jeder
Mail aus einem Nicht-Prod/Staging-Checkout auf die Basisadresse um. Eine
``--lang en``-Mail aus dem Worktree kaeme daher NIE an ``gregor-test+en@`` an,
das Skript meldete aber "gesendet" -- ein Scheinbeleg. Kern-Schicht, kein Netz:
das Skript laeuft echt bis zum Draht (Fixture ``draht`` aus #2681).
"""
# ruff: noqa: F811
from __future__ import annotations

import pytest

from tests.tdd.test_gate_testmails_zweisprachig import (  # noqa: F401
    BASIS, _skript, draht,
)


def test_lang_en_im_worktree_bricht_vor_jedem_versand_ab(draht, capsys):
    """AC-1: echte Herkunftsklassifikation (Worktree => "test"), Exit != 0, nichts gesendet."""
    code = _skript().main(["--lang", "en", "--only", "official"])
    aus = capsys.readouterr()
    assert code != 0
    assert draht == [], "es darf VOR der Abbruchmeldung nichts eingeliefert worden sein"
    meldung = aus.err.lower()
    assert "herkunft" in meldung, aus.err
    assert "gregor_zwanzig_staging" in aus.err, aus.err


def test_abbruch_gibt_keine_scheinbelege_aus(draht, capsys):
    """AC-2: weder "gesendet" noch ein "An: ...+en@" noch der Lauf-Token auf stdout."""
    _skript().main(["--lang", "en"])
    aus = capsys.readouterr()
    assert "gesendet" not in aus.out + aus.err
    assert "An: " not in aus.out + aus.err
    assert "+en@" not in aus.out
    assert "Token fuer diesen Lauf" not in aus.out
    assert aus.err.strip(), "der Abbruch muss eine Meldung hinterlassen"


def test_lang_de_im_worktree_sendet_unveraendert(draht, capsys):
    """AC-3 (Gegenprobe): --lang de laeuft aus demselben Worktree wie bisher durch."""
    code = _skript().main(["--lang", "de", "--only", "official"])
    assert code == 0
    assert len(draht) == 1
    assert draht[0][0] == [BASIS]


def test_lang_en_aus_staging_herkunft_sendet_weiterhin(draht, capsys):
    """Der Test-Seam ``herkunft`` trennt Worktree von Staging: aus Staging geht EN durch."""
    code = _skript().main(["--lang", "en", "--only", "official"],
                          herkunft=lambda _root: "staging")
    assert code == 0
    assert len(draht) == 1
    assert draht[0][0] == ["gregor-test+en@henemm.com"]


@pytest.mark.parametrize("herkunft", ["test", "irgendwas"])
def test_lang_en_bricht_bei_jeder_nicht_prod_staging_herkunft_ab(draht, capsys, herkunft):
    code = _skript().main(["--lang", "en", "--only", "official"],
                          herkunft=lambda _root: herkunft)
    assert code != 0
    assert draht == []
