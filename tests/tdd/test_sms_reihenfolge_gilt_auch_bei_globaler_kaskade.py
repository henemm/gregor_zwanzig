"""TDD RED -- Issue #2422 S2a, AC-13: SMS-Reihenfolge gilt auch bei
Kaskadenquelle 'global'.

SPEC: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md (AC-13).

Loest DEC-2 aus ``docs/specs/modules/fix_1677_sms_reihenfolge.md`` ab: das
dortige Aktivierungs-Gate

    _sms_position_by_metric = (
        {m.metric_id: i for i, m in enumerate(_sms_metrics_ordered)}
        if _sms_cascade_source in ("per_report", "per_channel")
        else {}
    )

(``src/output/renderers/trip_report.py:337-346``) garantierte bislang
Byte-Identitaet der SMS-/Kurzform-Ausgabe bei Kaskadenquelle 'global'
(dortige AC-2). Der B9-Fix dieser Scheibe entfernt das Gate -- ``position``
wird IMMER aus der SMS-Kaskade abgeleitet, unabhaengig von der
Kaskadenquelle. Dieser Test sichert das NEUE Verhalten zu: zwei disjunkte
Permutationen derselben globalen Metrikmenge (KEIN ``channel_layouts.sms``
-> Kaskadenquelle 'global') muessen zu zwei unterschiedlichen SMS-
Reihenfolgen fuehren, die jeweils der globalen Editor-Reihenfolge folgen --
genau wie bei ``per_channel``/``per_report`` (siehe
``tests/tdd/test_sms_user_metric_order.py::
test_ac10_two_permutations_same_metric_set_different_order``, dort fuer
``per_channel``).

RED heute (Gate noch vorhanden): beide Permutationen fallen auf dieselbe
feste POSITIONAL-Standardreihenfolge zurueck -- der Test erwartet
stattdessen zwei UNTERSCHIEDLICHE Reihenfolgen.

Kein Mock()/patch()/MagicMock -- echter Renderer-Pfad wie
``test_sms_user_metric_order.py`` (``TripReportFormatter().format_email()``).
"""
from __future__ import annotations

from tests.tdd import _min_temp_felt_fixtures as F
from tests.tdd.test_sms_user_metric_order import _render_sms, _token_index


def test_position_wirkt_bei_globaler_kaskade_wie_bei_per_channel():
    """AC-13: zwei Permutationen derselben globalen Metrikmenge (kein
    eigenes SMS-Kanal-Layout -> Kaskadenquelle 'global' fuer sms/
    telegram_kurzform/premium_sms, ADR-0049) ergeben zwei unterschiedliche
    SMS-Reihenfolgen, die jeweils der globalen Editor-Reihenfolge folgen."""
    # Beide Permutationen bewusst UNGLEICH der alten festen POSITIONAL-
    # Reihenfolge (R,W,G) UND ungleich zueinander gewaehlt -- eine reine
    # Umkehrung (["precipitation","wind","gust"] -> R,W,G) waere zufaellig
    # mit der alten Standardreihenfolge identisch und wuerde die zweite
    # Haelfte der Zusicherung (sms_a != sms_b) schon beim kaputten Gate
    # unbemerkt bestehen lassen.
    order_a = ["gust", "wind", "precipitation"]  # -> G,W,R
    order_b = ["wind", "precipitation", "gust"]  # -> W,R,G

    dc_a = F.dc(*order_a)
    dc_b = F.dc(*order_b)

    # Vorbedingung: beide Konfigurationen loesen tatsaechlich 'global' aus
    # (kein channel_layouts.sms gesetzt) -- sonst waere die Zusicherung
    # unten wirkungslos (Vakuum-Schutz).
    assert dc_a.cascade_source_for_channel("sms", "evening") == "global", (
        "Testaufbau: dc_a muss ueber KEIN eigenes SMS-Kanal-Layout verfuegen "
        "(Kaskadenquelle 'global'), sonst prueft dieser Test AC-1 aus "
        "fix_1677, nicht AC-13 aus fix_2422_s2a."
    )
    assert dc_b.cascade_source_for_channel("sms", "evening") == "global"

    sms_a = _render_sms(dc_a)
    sms_b = _render_sms(dc_b)

    idx_a = (
        _token_index(sms_a, "G"), _token_index(sms_a, "W"), _token_index(sms_a, "R"),
    )
    idx_b = (
        _token_index(sms_b, "G"), _token_index(sms_b, "W"), _token_index(sms_b, "R"),
    )

    assert idx_a[0] < idx_a[1] < idx_a[2], (
        f"Permutation A (Editor-Reihenfolge G,W,R) muss dieser Reihenfolge "
        f"in der SMS folgen, obwohl kein eigenes SMS-Kanal-Layout gesetzt "
        f"ist (Kaskadenquelle 'global'): {sms_a!r}"
    )
    assert idx_b[1] < idx_b[2] < idx_b[0], (
        f"Permutation B (Editor-Reihenfolge W,R,G) muss dieser Reihenfolge "
        f"in der SMS folgen, obwohl kein eigenes SMS-Kanal-Layout gesetzt "
        f"ist (Kaskadenquelle 'global'): {sms_b!r}"
    )
    assert sms_a != sms_b, (
        "AC-13: zwei unterschiedliche globale Editor-Reihenfolgen muessen "
        "zwei unterschiedliche SMS-Texte ergeben. Mit dem noch aktiven "
        "Aktivierungs-Gate (DEC-2 aus fix_1677_sms_reihenfolge.md) sind "
        f"beide byte-identisch (POSITIONAL-Ruckfall): A={sms_a!r} B={sms_b!r}"
    )
