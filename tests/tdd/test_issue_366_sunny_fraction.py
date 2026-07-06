"""
TDD RED Tests für Issue #366 — Compare-Score Sonnenstunden-Neukalibrierung.

Nach #347 liefert calculate_sunny_hours() reale Werte; der Sonnen-Bonus im
Compare-Scoring wird auf den ANTEIL sonniger Stunden am Zeitfenster umgestellt
(window_hours), damit er fensterlängen-unabhängig ist.

Diese Tests MÜSSEN initial FEHLSCHLAGEN: calculate_score() akzeptiert den
Parameter `window_hours` noch nicht (TypeError), und die Engine reicht ihn
noch nicht durch.

KEINE MOCKS — AC-5 fährt einen echten ComparisonEngine.run() gegen Open-Meteo.

Spec: docs/specs/modules/issue_366_compare_score_recalibration.md
"""
from datetime import date, timedelta

import sys

sys.path.insert(0, "src")


# ---------------------------------------------------------------------------
# AC-1: Volles sonniges Fenster -> oberste Stufe (WANDERN +20)
# ---------------------------------------------------------------------------
class TestAC1FullSunnyWindow:
    def test_full_sunny_window_wandern_top_bonus(self):
        """
        GIVEN: sunny_hours == window_hours (Anteil 1.0), Profil WANDERN
        WHEN: calculate_score mit window_hours aufgerufen
        THEN: oberste Sonnen-Stufe greift -> Basis 50 + 20 = 70
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        score = calculate_score(
            {"sunny_hours": 8.0}, profile=ActivityProfile.WANDERN, window_hours=8.0
        )
        assert score == 70, f"Anteil 1.0 -> +20 erwartet (70), war {score}"


# ---------------------------------------------------------------------------
# AC-2: Fensterlängen-Unabhängigkeit bei gleichem Anteil
# ---------------------------------------------------------------------------
class TestAC2WindowIndependence:
    def test_same_fraction_same_bonus_across_windows(self):
        """
        GIVEN: Anteil 0.5 bei 8h-Fenster (4h Sonne) und 14h-Fenster (7h Sonne)
        WHEN: beide mit passendem window_hours gescort
        THEN: identischer Score (Stufe 2: WANDERN +12 -> 62), kein Kollaps
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        short = calculate_score(
            {"sunny_hours": 4.0}, profile=ActivityProfile.WANDERN, window_hours=8.0
        )
        long = calculate_score(
            {"sunny_hours": 7.0}, profile=ActivityProfile.WANDERN, window_hours=14.0
        )
        assert short == long == 62, f"Beide 62 erwartet, war short={short}, long={long}"


# ---------------------------------------------------------------------------
# AC-3: Differenzierung teils sonnig vs. sehr sonnig wiederhergestellt
# ---------------------------------------------------------------------------
class TestAC3Differentiation:
    def test_very_sunny_beats_partly_sunny(self):
        """
        GIVEN: Anteil 0.40 (4h/10h) vs. 0.85 (8.5h/10h), Profil WANDERN
        WHEN: beide gescort
        THEN: sehr sonniger Tag strikt höher (55 mit +5 vs. 70 mit +20)
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        partly = calculate_score(
            {"sunny_hours": 4.0}, profile=ActivityProfile.WANDERN, window_hours=10.0
        )
        very = calculate_score(
            {"sunny_hours": 8.5}, profile=ActivityProfile.WANDERN, window_hours=10.0
        )
        assert partly == 55, f"Anteil 0.40 -> +5 (55), war {partly}"
        assert very == 70, f"Anteil 0.85 -> +20 (70), war {very}"
        assert very > partly, "Sehr sonniger Tag muss strikt höher scoren"


# ---------------------------------------------------------------------------
# AC-4: Abwärtskompatibilität ohne window_hours (Legacy-Pfad unverändert)
# ---------------------------------------------------------------------------
class TestAC4BackwardCompat:
    def test_no_window_uses_absolute_thresholds(self):
        """
        GIVEN: calculate_score OHNE window_hours (Legacy-Aufrufer)
        WHEN: WANDERN, sunny_hours=7 (alte absolute Top-Schwelle)
        THEN: alte Absolut-Logik -> +20 (70), byte-gleiches Verhalten
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        score = calculate_score({"sunny_hours": 7}, profile=ActivityProfile.WANDERN)
        assert score == 70, f"Absolut-Fallback >=7h -> +20 (70), war {score}"


# ---------------------------------------------------------------------------
# AC-6: Quellen-agnostisch — gebrochene (Geosphere-Fallback-)Werte funktionieren
# ---------------------------------------------------------------------------
class TestAC6SourceAgnostic:
    def test_fractional_value_proportional(self):
        """
        GIVEN: gebrochener sunny_hours-Wert (wie Cloud-Fallback liefert), 3.7h/10h
        WHEN: WANDERN mit window_hours=10 gescort
        THEN: Anteil 0.37 -> Stufe 3 (+5) -> 55, unabhängig von der Datenquelle
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        score = calculate_score(
            {"sunny_hours": 3.7}, profile=ActivityProfile.WANDERN, window_hours=10.0
        )
        assert score == 55, f"Anteil 0.37 -> +5 (55), war {score}"


# ---------------------------------------------------------------------------
# AC-7: Konsistente Stufung über die drei Profile bei Anteil 0.60
# ---------------------------------------------------------------------------
class TestAC7ProfileConsistency:
    def test_fraction_060_stufe2_all_profiles(self):
        """
        GIVEN: Anteil 0.60 (6h/10h), nur sunny_hours gesetzt
        WHEN: alle drei Profile gescort
        THEN: jeweils Stufe-2-Bonus: WANDERN 50+12=62, WINTERSPORT 50+10=60, ALLGEMEIN 55+8=63
        """
        from app.profile import ActivityProfile
        from services.comparison_scoring import calculate_score

        m = {"sunny_hours": 6.0}
        wandern = calculate_score(m, profile=ActivityProfile.WANDERN, window_hours=10.0)
        winter = calculate_score(m, profile=ActivityProfile.WINTERSPORT, window_hours=10.0)
        allg = calculate_score(m, profile=ActivityProfile.ALLGEMEIN, window_hours=10.0)
        assert wandern == 62, f"WANDERN Stufe2 -> 62, war {wandern}"
        assert winter == 60, f"WINTERSPORT Stufe2 -> 60, war {winter}"
        assert allg == 63, f"ALLGEMEIN Stufe2 -> 63, war {allg}"


# ---------------------------------------------------------------------------
# AC-5: ComparisonEngine reicht window_hours = end - start + 1 durch (ECHTER Lauf)
# ---------------------------------------------------------------------------
class TestAC5EngineWiring:
    def test_engine_passes_window_hours(self):
        """
        GIVEN: realer Compare-Lauf (Innsbruck) mit time_window=(9, 16)
        WHEN: ComparisonEngine.run die WANDERN-Scores berechnet
        THEN: result.score == calculate_score(rekonstr. Metriken, WANDERN, window_hours=8)

        Beweist: die Engine übergibt window_hours = 16-9+1 = 8 und nutzt die
        Anteils-Logik. Metriken werden faithful aus den (echten) Result-Feldern
        + hourly_data rekonstruiert — kein Mock.
        """
        from app.loader import SavedLocation
        from app.profile import ActivityProfile
        from services.comparison_engine import ComparisonEngine
        from services.comparison_scoring import calculate_score

        loc = SavedLocation(
            id="test-366-innsbruck", name="Innsbruck",
            lat=47.27, lon=11.39, elevation_m=574,
        )
        target = date.today() + timedelta(days=1)
        result = ComparisonEngine.run(
            [loc], time_window=(9, 16), target_date=target,
            profile=ActivityProfile.WANDERN,
        )
        r = result.locations[0]
        assert r.error is None, f"Engine-Fehler: {r.error}"
        assert r.sunny_hours is not None, "sunny_hours muss gesetzt sein"

        # Faithful-Rekonstruktion der WANDERN-Metriken aus echten Result-Feldern.
        metrics = {
            "sunny_hours": r.sunny_hours,
            "wind_max": r.wind_max,
            "cloud_avg": r.cloud_avg,
            "temp_min": r.temp_min,
        }
        thunder_levels = [dp.thunder_level for dp in r.hourly_data if dp.thunder_level is not None]
        if thunder_levels:
            rank = {"NONE": 0, "MED": 1, "HIGH": 2}
            metrics["thunder_level"] = max(thunder_levels, key=lambda x: rank.get(x, 0))
        pops = [dp.pop_pct for dp in r.hourly_data if dp.pop_pct is not None]
        if pops:
            metrics["pop_max_pct"] = max(pops)

        window_hours = 16 - 9 + 1
        expected = calculate_score(
            metrics, profile=ActivityProfile.WANDERN, window_hours=window_hours
        )
        assert r.score == expected, (
            f"Engine-Score {r.score} != Anteils-Score mit window_hours={window_hours} "
            f"({expected}) -> window_hours wird nicht (korrekt) durchgereicht"
        )
