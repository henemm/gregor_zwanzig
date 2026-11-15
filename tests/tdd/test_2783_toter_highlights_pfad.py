"""#2783 AC-3: der tote Highlights-Pfad im Trip-Briefing ist zurueckgebaut.

SPEC: docs/specs/modules/i18n_p13_ratsche_renderer_2783.md AC-3.

``TripReportFormatter._compute_highlights`` erreichte seit #790 keine Ausgabe
(``render_email`` verwirft ``highlights`` in ``**_ignored``). Er wird entfernt
statt mit Markern stillgelegt oder uebersetzt. Ohne diesen Waechter koennte die
Ratsche auch durch ``# i18n-fest`` an toten Literalen gruen werden.
"""
from __future__ import annotations

from output.renderers.trip_report import TripReportFormatter


def test_compute_highlights_ist_entfernt():
    assert not hasattr(TripReportFormatter, "_compute_highlights"), (
        "_compute_highlights ist toter Code (#790) und gehoert entfernt (#2783)"
    )

