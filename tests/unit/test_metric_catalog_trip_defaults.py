"""Trip-Anlege-Standard im Register — Issue #1552.

Spec: docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md

Kern-Tests (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, keine
Live-Dienste, kein Mock/patch. Reine Registrierungs-Abfragen.

Prueft die Register-Ebene: genau 7 Groessen tragen `trip_default_rank`,
alle sind `selectable=True`, in der dokumentierten Reihenfolge. Zusaetzlich
Regressionsschutz fuer AC-7: `default_enabled` (Orte/Abonnements-Vorbelegung)
bleibt fuer alle betroffenen Groessen unveraendert -- `trip_default_rank`
ist eine reine Zusatz-Markierung, kein Ersatz.
"""
from __future__ import annotations

from app.metric_catalog import get_all_metrics

EXPECTED_ORDER = [
    "temperature", "wind", "gust", "precipitation",
    "thunder", "freezing_level", "visibility",
]


def _ranked_metrics():
    return sorted(
        (m for m in get_all_metrics() if m.trip_default_rank is not None),
        key=lambda m: m.trip_default_rank,
    )


class TestTripDefaultRankRegister:
    def test_exactly_seven_metrics_carry_trip_default_rank(self):
        ranked = _ranked_metrics()
        assert [m.id for m in ranked] == EXPECTED_ORDER, (
            f"Erwartete genau die 7 Standard-Groessen in dieser Reihenfolge, "
            f"bekam: {[m.id for m in ranked]!r}"
        )

    def test_all_seven_are_selectable(self):
        ranked = _ranked_metrics()
        assert all(m.selectable for m in ranked), (
            "Alle 7 Trip-Anlege-Standardgroessen muessen selectable=True sein "
            "(sonst waeren sie nie im Anlege-Dialog waehlbar)"
        )

    def test_rank_values_are_1_to_7_without_gaps(self):
        ranked = _ranked_metrics()
        assert [m.trip_default_rank for m in ranked] == [1, 2, 3, 4, 5, 6, 7]

    def test_no_other_metric_carries_trip_default_rank(self):
        all_ids = {m.id for m in get_all_metrics()}
        ranked_ids = {m.id for m in _ranked_metrics()}
        others = all_ids - ranked_ids
        # Stichprobe: eine Groesse, die frueher (default_enabled) den
        # Anlege-Dialog fuellte, aber NICHT zu den 7 Ziel-Groessen gehoert,
        # darf jetzt kein trip_default_rank tragen.
        assert "cloud_total" in others
        assert "sunshine" in others

    def test_default_enabled_unchanged_for_ranked_metrics_ac7(self):
        # AC-7: default_enabled (Orte/Abonnements) bleibt unberuehrt.
        # freezing_level/visibility sind default_enabled=False (nie Teil der
        # Orte-Vorbelegung) -- das war schon vor #1552 so und muss es bleiben.
        by_id = {m.id: m for m in get_all_metrics()}
        assert by_id["freezing_level"].default_enabled is False
        assert by_id["visibility"].default_enabled is False
        assert by_id["temperature"].default_enabled is True
        assert by_id["wind"].default_enabled is True
        assert by_id["gust"].default_enabled is True
        assert by_id["precipitation"].default_enabled is True
        assert by_id["thunder"].default_enabled is True
