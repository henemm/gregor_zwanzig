"""entity_id-Muster-Paritaet Python <-> Go (Issue #2140 Scheibe 2, AC-10).

Das Zulassungsmuster fuer ENTITAETS-Kennungen (Trip/Ort/Vergleichs-Preset)
existiert zweimal — in der Go-Quelle (``internal/store/pathsafe.go``,
``ValidEntityID``) und im Python-Core (``app.loader.VALID_ENTITY_ID_RE``).
Driften beide, akzeptiert eine Seite Kennungen, die die andere ablehnt — genau
die Asymmetrie, die Scheibe 1 fuer Nutzer-Kennungen bereits schliesst.

Der Nachweis laeuft ueber VERHALTEN auf beiden Seiten, nicht ueber
Quelltext-Vergleich: beide Seiten pruefen dieselbe versionierte
Wahrheitstabelle (``tests/fixtures/entity_id_pattern_parity/faelle.json``).
Das Go-Pendant ist ``internal/store/entity_id_test.go``
(``TestValidEntityID_FolgtDerGeteiltenWahrheitstabelle``). Driftet eine der
beiden Seiten von der Tabelle ab, wird genau diese Seite rot — ohne dass ein
Test Produkt-Quelltext als Daten liest (CLAUDE.md: Dateiinhalt-Checks sind
kein Verhaltensnachweis).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.loader import VALID_ENTITY_ID_RE

# Relativ zur eigenen Testdatei aufgeloest (nie ueber den festen
# Hauptrepo-Pfad) — sonst misst ein Lauf aus dem Worktree die Fixture des
# Hauptrepos und wird falsch gruen.
_FALLTABELLE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "entity_id_pattern_parity"
    / "faelle.json"
)


def _lade_falltabelle() -> tuple[list[str], list[str]]:
    """Laedt die geteilte Wahrheitstabelle und weist leere Mengen ab.

    Eine fehlende oder leere Tabelle wuerde 'nichts gefunden, alles gruen'
    still durchwinken — der Paritaetsnachweis waere dann wirkungslos.
    """
    assert _FALLTABELLE.exists(), (
        f"Geteilte Wahrheitstabelle fehlt: {_FALLTABELLE} — ohne sie hat der "
        "Paritaetsnachweis keine Faelle und wuerde still gruen durchlaufen."
    )
    daten = json.loads(_FALLTABELLE.read_text(encoding="utf-8"))
    invalid = daten["invalid"]
    valid = daten["valid"]
    assert invalid and valid, (
        f"{_FALLTABELLE} enthaelt eine leere Fallmenge (invalid={len(invalid)}, "
        f"valid={len(valid)}) — leere Mengen sind stilles Gruen."
    )
    return invalid, valid


def test_python_muster_folgt_der_geteilten_wahrheitstabelle():
    """Given die geteilte Wahrheitstabelle, gegen die auch die Go-Seite
    (store.ValidEntityID) laeuft / When VALID_ENTITY_ID_RE gegen jeden Fall
    entscheidet / Then stimmt jedes Urteil mit der Tabelle ueberein — weicht
    eine der beiden Seiten ab, wird genau diese Seite rot."""
    invalid, valid = _lade_falltabelle()

    for entity_id in invalid:
        assert not VALID_ENTITY_ID_RE.match(entity_id), (
            f"VALID_ENTITY_ID_RE akzeptiert unsicheres Segment {entity_id!r} — "
            "die Go-Seite lehnt es laut geteilter Wahrheitstabelle ab."
        )
    for entity_id in valid:
        assert VALID_ENTITY_ID_RE.match(entity_id), (
            f"VALID_ENTITY_ID_RE lehnt gueltiges Unicode-Segment {entity_id!r} "
            "ab — die Go-Seite laesst es laut geteilter Wahrheitstabelle zu."
        )


def test_wahrheitstabelle_deckt_die_spec_regel_vollstaendig_ab():
    """Given die in der Spec beschriebene Regel (nicht leer, kein '/', kein
    '\\', kein NUL-Byte, nicht '.' und nicht '..', kein fuehrender Punkt,
    Unicode-Buchstaben zulaessig) / When die geteilte Wahrheitstabelle daneben
    gelegt wird / Then traegt sie zu jedem Regelteil mindestens einen Fall —
    sonst koennte die Paritaet an einem ungeprueften Regelteil auseinander
    driften, ohne dass ein Test rot wird (Selbstnachweis der Tabelle)."""
    invalid, valid = _lade_falltabelle()

    assert "" in invalid, "Regelteil 'nicht leer' hat keinen Fall"
    assert any("/" in x for x in invalid), "Regelteil 'kein /' hat keinen Fall"
    assert any("\\" in x for x in invalid), "Regelteil 'kein \\' hat keinen Fall"
    assert any("\x00" in x for x in invalid), "Regelteil 'kein NUL' hat keinen Fall"
    assert "." in invalid and ".." in invalid, "Punkt-Segmente haben keinen Fall"
    assert any(
        x.startswith(".") and x not in {".", ".."} for x in invalid
    ), "Regelteil 'kein fuehrender Punkt' hat keinen Fall"
    assert any(
        any(ord(c) > 127 for c in x) for x in valid
    ), "Positivkontrolle Unicode-Buchstaben hat keinen Fall"
