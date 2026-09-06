# doc-compliance-test
"""entity_id-Muster-Paritaet Python <-> Go (Issue #2140 Scheibe 2, AC-10).

Bauart wie tests/unit/test_user_id_pattern_parity.py (#1364): das
Zulassungsmuster fuer ENTITAETS-Kennungen (Trip/Ort/Vergleichs-Preset)
existiert zweimal — in der kanonischen Go-Quelle
(internal/store/pathsafe.go, ``ValidEntityIDRe``, analog dem bestehenden
``ValidUserIDRe`` daneben) und im Python-Core (``app.loader.VALID_ENTITY_ID_RE``).
Driften beide, akzeptiert eine Seite Kennungen, die die andere ablehnt —
genau die Asymmetrie, die Scheibe 1 fuer Nutzer-Kennungen bereits schliesst.

ANNAHME (an den Team-Lead zurueckgemeldet, siehe RED-Bericht): die Spec
(docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md) nennt fuer die
Go-Seite nur die Funktion ``ValidEntityID``, keinen expliziten Regex-Namen.
Dieser Test erwartet — analog zu ``ValidUserIDRe`` neben ``ValidUserID`` in
derselben Datei — eine begleitende Variable ``ValidEntityIDRe``. Waehlt die
Implementierung stattdessen eine reine Funktion ohne Regex-Variable, muss
dieser Test angepasst werden (das ist eine bewusste, im RED-Bericht
dokumentierte Schnittstellen-Entscheidung dieser TDD-Phase, keine
Fehlannahme).

Strukturregel auf Quelltext-als-Daten: das Go-Muster ist aus Python nur als
Text erreichbar (kein Go-Toolchain-Aufruf im Kernlauf) — gleiche
Werkzeug-Klasse wie test_user_id_pattern_parity.py; daher
``# doc-compliance-test``.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.loader import VALID_ENTITY_ID_RE

_REPO = Path(__file__).resolve().parents[2]
_PATHSAFE_GO = _REPO / "internal" / "store" / "pathsafe.go"


def test_python_muster_ist_deckungsgleich_mit_go():
    """Given das kanonische Go-Muster in store/pathsafe.go (ValidEntityIDRe)
    / When das Python-Muster (VALID_ENTITY_ID_RE) daneben gelegt wird / Then
    sind beide identisch — analog test_user_id_pattern_parity.py fuer
    Nutzer-Kennungen."""
    go_src = _PATHSAFE_GO.read_text(encoding="utf-8")
    m = re.search(
        r"ValidEntityIDRe\s*=\s*regexp\.MustCompile\(`([^`]+)`\)", go_src
    )
    assert m, (
        "ValidEntityIDRe nicht in pathsafe.go gefunden — entweder wurde die "
        "Guard-Regex anders benannt/verschoben, oder ValidEntityID ist als "
        "reine Funktion ohne begleitende Regex-Variable implementiert. In "
        "letzterem Fall muss dieser Paritaetstest neu gefasst werden (siehe "
        "Docstring-Hinweis oben, RED-Bericht #2140 Scheibe 2)."
    )
    assert VALID_ENTITY_ID_RE.pattern == m.group(1)


def test_python_muster_stimmt_mit_spec_beispielen_ueberein():
    """Given die in der Spec beschriebene Regel (nicht leer, kein '/', kein
    '\\', kein NUL-Byte, nicht '.' und nicht '..', kein fuehrender Punkt,
    Unicode-Buchstaben zulaessig) / When VALID_ENTITY_ID_RE gegen dieselbe
    Beispielmenge wie internal/store/entity_id_test.go laeuft / Then
    entscheidet es fuer jede Eingabe identisch — unabhaengig davon, ob die
    Go-Seite als Regex oder als Funktion implementiert ist (Bauart-Redundanz
    zur vorigen Pruefung)."""
    invalid = [
        "",
        "/",
        "a/b",
        "\\",
        "a\\b",
        "a\x00b",
        ".",
        "..",
        "../x",
        "../../bob/user",
        ".hidden",
    ]
    valid = [
        "trip123",
        "cp-a1b2c3d4",
        "hochfügen",
        "pollença",
        "übergangsjoch-zillertal-arena",
        "serfaus-schöngamp-berg",
        "mühlbach",
    ]
    for entity_id in invalid:
        assert not VALID_ENTITY_ID_RE.match(entity_id), (
            f"VALID_ENTITY_ID_RE akzeptiert unsicheres Segment {entity_id!r}"
        )
    for entity_id in valid:
        assert VALID_ENTITY_ID_RE.match(entity_id), (
            f"VALID_ENTITY_ID_RE lehnt gueltiges Unicode-Segment {entity_id!r} ab"
        )
