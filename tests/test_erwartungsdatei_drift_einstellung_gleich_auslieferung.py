"""TDD -- Issue #2422 S2a, AC-2 (Drift-Test der Erwartungsdateien).

SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-2).

Given eine eingefrorene Erwartungsdatei je Golden (A, B, C).
When der Drift-Test laeuft.
Then stimmt jede Erwartungsdatei exakt mit dem AKTUELLEN Ergebnis von
``erwartete_kaskade`` fuer das jeweilige Golden ueberein -- jede unbemerkte
Abweichung (z.B. durch eine spaetere Orakel-Aenderung) macht diesen Test
rot. Neu erzeugen: ``uv run python3 -m tests.helpers.erwartungsdateien_erzeugen``.

Dieser Test ist Commit-Gate-tauglich und bereits heute GRUEN (die
Erwartungsdateien sind fix-unabhaengig -- der B9-/K8-Fix aendert weder die
Orakel-Funktion selbst noch die davon abgeleiteten Erwartungsdateien).

Kein Mock()/patch()/MagicMock -- reiner Datenvergleich gegen das echte
Orakel.
"""
from __future__ import annotations

import json

import pytest

from tests.helpers.einstellung_auslieferung_orakel import erwartete_kaskade
from tests.helpers.erwartungsdateien_erzeugen import (
    GOLDEN_DIR, REPORT_TYPE, _REITER_ZU_ORAKEL_KANAL,
)
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict

_GOLDEN_NAMEN = ("golden_a", "golden_b", "golden_c")


@pytest.mark.parametrize("name", _GOLDEN_NAMEN)
def test_erwartungsdateien_entsprechen_dem_aktuellen_orakel(name: str) -> None:
    golden = golden_dict(name)
    ziel = GOLDEN_DIR / f"erwartung_{name}.json"
    assert ziel.exists(), (
        f"AC-2: {ziel} fehlt -- neu erzeugen: "
        f"uv run python3 -m tests.helpers.erwartungsdateien_erzeugen"
    )
    eingefroren = json.loads(ziel.read_text())
    assert eingefroren["report_type"] == REPORT_TYPE

    for reiter, orakel_kanal in _REITER_ZU_ORAKEL_KANAL.items():
        aktuell = [
            {"metric_id": mid, "friendly": friendly}
            for mid, friendly in erwartete_kaskade(golden, orakel_kanal, REPORT_TYPE)
        ]
        eingefroren_kanal = eingefroren["channels"][reiter]
        assert eingefroren_kanal == aktuell, (
            f"AC-2: {ziel.name}/{reiter!r} ist gegenueber dem aktuellen "
            f"Orakel-Ergebnis veraltet -- eingefroren={eingefroren_kanal}, "
            f"aktuell={aktuell}. Neu erzeugen: uv run python3 -m "
            f"tests.helpers.erwartungsdateien_erzeugen"
        )
