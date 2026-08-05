"""Zentrale user_id-Pruefung in get_data_dir() (#1364, Mandanten-Trennung).

Adversary-Beleg aus #1352: user_id="../users/bob" schrieb byte-genau in
bobs echten Ordner. Der GPX-Endpoint wurde lokal geflickt; die uebrigen
~27 Aufrufer von get_data_dir() blieben ungeprueft. Erwartung: get_data_dir()
weist jede user_id zurueck, die kein brauchbarer Ordnername ist — zentral,
damit alle Aufrufer gedeckt sind (ADR-0003: Isolation haengt nicht an einer
einzigen Schicht).
"""
from __future__ import annotations

import pytest

from app.loader import get_data_dir, get_data_root, get_locations_dir


@pytest.mark.parametrize(
    "malicious",
    [
        "../users/bob",
        "../../../tmp",
        "a/b",
        "a\\b",
        "",
        ".",
        "..",
        "a b",
        "a\x00b",
        "/etc",
        "bob@example.com",
    ],
)
def test_pfadanteile_und_unbrauchbare_kennungen_werden_zurueckgewiesen(malicious):
    """Given eine user_id mit Pfadanteilen oder Sonderzeichen / When
    get_data_dir sie aufloesen soll / Then ValueError statt Pfadausbruch."""
    with pytest.raises(ValueError):
        get_data_dir(malicious)


@pytest.mark.parametrize(
    "real_id", ["default", "henning", "steffi", "validator-issue110", "A_b-2"]
)
def test_reale_kennungen_bleiben_zugelassen(real_id):
    """Given die real existierenden Kennungen aus #1364 / When get_data_dir
    aufloest / Then liegt der Pfad unter <root>/users/<id> (niemand wird
    ausgesperrt)."""
    p = get_data_dir(real_id)
    assert p == get_data_root() / "users" / real_id
    resolved = p.resolve()
    assert resolved.name == real_id
    assert resolved.parent.name == "users"


def test_abgeleitete_verzeichnisse_sind_mitgedeckt():
    """Given ein Aufrufer nutzt einen abgeleiteten Helfer statt get_data_dir
    direkt / When die user_id Pfadanteile traegt / Then greift die zentrale
    Pruefung auch dort (ein Chokepoint, keine 27 Einzel-Flicken)."""
    with pytest.raises(ValueError):
        get_locations_dir("../users/bob")


def test_default_aufruf_ohne_argument_funktioniert():
    """Given der parameterlose Bestandsaufruf / When get_data_dir() laeuft /
    Then Standard-Kennung 'default' wie bisher."""
    assert get_data_dir().name == "default"
