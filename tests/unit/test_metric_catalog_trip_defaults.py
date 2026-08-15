"""Trip-Anlege-Standard im Register — Issue #1552.

Spec: docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md

Kern-Tests (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, keine
Live-Dienste, kein Mock/patch. Reine Registrierungs-Abfragen.

Prueft die Register-Ebene: genau die kuratierten Groessen tragen
`trip_default_rank`, alle sind `selectable=True`, in der dokumentierten
Reihenfolge. Die Liste ist bewusst AUFGEZAEHLT -- sie IST die Festlegung,
welche Groessen ein neuer Trip vorbelegt bekommt; eine unbeabsichtigte
Ergaenzung soll hier auffallen. Die Rang-LUECKENLOSIGKEIT dagegen wird
gerechnet, nicht aufgezaehlt (s.u.). Zusaetzlich
Regressionsschutz fuer AC-7: `default_enabled` (Orte/Abonnements-Vorbelegung)
bleibt fuer alle betroffenen Groessen unveraendert -- `trip_default_rank`
ist eine reine Zusatz-Markierung, kein Ersatz.
"""
from __future__ import annotations

from app.metric_catalog import get_all_metrics

EXPECTED_ORDER = [
    "temperature", "wind", "gust", "precipitation",
    "thunder", "freezing_level", "visibility",
    # Issue #1728 Scheibe 1 (DEC-7, PO „an"): die beiden gemessenen
    # Tagesrichtungen sind bei einem neuen Trip von Anfang an aktiv --
    # ANGEHAENGT als Rang 8/9, ohne Umnummerierung der bestehenden sieben.
    # Die gefuehlten Tagesrichtungen tragen bewusst KEINEN Rang (sie folgen
    # der heutigen Lage von "wind_chill").
    "temperature_day_low", "temperature_day_high",
]


def _ranked_metrics():
    return sorted(
        (m for m in get_all_metrics() if m.trip_default_rank is not None),
        key=lambda m: m.trip_default_rank,
    )


class TestTripDefaultRankRegister:
    def test_exactly_the_curated_metrics_carry_trip_default_rank(self):
        ranked = _ranked_metrics()
        assert [m.id for m in ranked] == EXPECTED_ORDER, (
            f"Erwartete genau die kuratierten Standard-Groessen in dieser "
            f"Reihenfolge, bekam: {[m.id for m in ranked]!r}"
        )

    def test_all_ranked_are_selectable(self):
        ranked = _ranked_metrics()
        assert all(m.selectable for m in ranked), (
            "Alle Trip-Anlege-Standardgroessen muessen selectable=True sein "
            "(sonst waeren sie nie im Anlege-Dialog waehlbar)"
        )

    def test_rank_values_are_consecutive_from_one_without_gaps(self):
        """Lueckenlos ab 1 -- GERECHNET aus dem Register, nicht aufgezaehlt:
        die Zusicherung ist „keine Luecke, kein Doppelrang", nicht „genau
        sieben". So bleibt sie bei jedem gewollten Katalog-Zuwachs gueltig
        und faellt trotzdem bei einem Rang-Fehler."""
        ranked = _ranked_metrics()
        raenge = [m.trip_default_rank for m in ranked]
        assert raenge == list(range(1, len(ranked) + 1)), (
            f"Raenge muessen lueckenlos ab 1 laufen: {raenge!r}"
        )

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
