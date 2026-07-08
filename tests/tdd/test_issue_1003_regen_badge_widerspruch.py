"""
TDD RED — Issue #1003 (Duplikat #1126): Regen-Badge widerspricht Stundentabelle.

Das Metriken-Überblick-Badge (`_pill_for_metric`, Zweig `precipitation`,
`src/output/renderers/email/helpers.py`) zeigt pauschal "kein Regen", wenn
keine EINZELNE Stunde die SMS-Erwaehnungsschwelle (0.2 mm/h) erreicht — auch
wenn die bereits berechnete Tagessumme > 0 ist (z.B. Regen duenn ueber mehrere
Stunden verteilt: 0.1 + 0.1 = 0.2 mm gesamt, keine Einzelstunde >= 0.2). Die
Stundentabelle derselben Etappe zeigt in diesem Fall eine Regensumme > 0 —
Widerspruch fuer den Leser bei tourenrelevanten Wetterentscheidungen.

Mock-frei: echte render_html()/render_plain()-Aufrufe mit echten
ForecastDataPoint/SegmentWeatherData-Objekten (Muster aus #790/#795). Geprueft
wird der gerenderte Output (Produkt), kein Quelltext.

RED gegen Prod-Stand (7b3fc0bc): Fallback-Zweig in `_pill_for_metric()`
verwirft die Tagessumme `total` unbedingt bei `fp is None` und liefert immer
"kein Regen" zurueck.

SPEC: docs/specs/modules/issue_1003_regen_badge_widerspruch.md AC-1..AC-4
"""
from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tests.tdd.test_issue_795_briefing_quality import (  # noqa: E402
    _metrics_block_html, _metrics_block_plain, _render_html, _render_plain,
    _seg_with_hours,
)

TZ = ZoneInfo("Europe/Berlin")


# ===========================================================================
# AC-1: Duenn verteilter Regen (Summe > 0, keine Einzelstunde >= 0.2mm)
#       -> "Regen ges. X mm" statt "kein Regen"
# ===========================================================================

class TestAC1DuennVerteilterRegen:

    def _segs(self):
        # 0.1 + 0.1 mm = 0.2 mm Tagessumme; keine Einzelstunde erreicht die
        # SMS-Erwaehnungsschwelle von 0.2 mm/h einzeln (0.1 < 0.2 je Stunde).
        return [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "precip": 0.1, "pop": 20},
            {"hour": 7, "temp": 13, "wind": 3, "gust": 5, "precip": 0.1, "pop": 20},
            {"hour": 8, "temp": 14, "wind": 3, "gust": 5, "precip": 0.0, "pop": 0},
        ])]

    def test_html_shows_sum_not_kein_regen(self):
        html = _render_html(self._segs())
        block = _metrics_block_html(html)
        assert "kein Regen" not in block, (
            f"Badge zeigt 'kein Regen' trotz Tagessumme 0.2 mm (Widerspruch "
            f"zur Stundentabelle):\n{block}"
        )
        assert "Regen ges. 0.2 mm" in block, (
            f"Badge sollte 'Regen ges. 0.2 mm' zeigen (Tagessumme aus den "
            f"Stundenwerten), stattdessen:\n{block}"
        )

    def test_plain_shows_sum_not_kein_regen(self):
        plain = _render_plain(self._segs())
        block = _metrics_block_plain(plain)
        assert "kein Regen" not in block, (
            f"Plain-Badge zeigt 'kein Regen' trotz Tagessumme 0.2 mm:\n{block}"
        )
        assert "Regen ges. 0.2 mm" in block, (
            f"Plain-Badge sollte 'Regen ges. 0.2 mm' zeigen, stattdessen:\n{block}"
        )


# ===========================================================================
# AC-2: Wirklich kein Regen (alle Stunden precip=0) -> weiterhin "kein Regen"
#       (kein Regress)
# ===========================================================================

class TestAC2EchterNullfall:

    def test_no_rain_at_all_stays_kein_regen(self):
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "precip": 0, "pop": 0},
            {"hour": 7, "temp": 14, "wind": 4, "gust": 6, "precip": 0, "pop": 0},
            {"hour": 8, "temp": 16, "wind": 4, "gust": 6, "precip": 0, "pop": 0},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "kein Regen" in block, (
            f"Bei tatsaechlich 0 mm Regen sollte weiterhin 'kein Regen' "
            f"stehen (kein Regress):\n{block}"
        )
        assert "Regen ges." not in block, (
            f"Bei 0 mm sollte kein 'Regen ges.'-Text erscheinen:\n{block}"
        )


# ===========================================================================
# AC-3: Summe rundet exakt auf 0.0 (z.B. 0.02 + 0.02 = 0.04mm)
#       -> weiterhin "kein Regen" (kein neuer Widerspruch in umgekehrter
#       Richtung — Text und Tabellensumme runden beide auf 0.0)
# ===========================================================================

class TestAC3RundetAufNull:

    def test_tiny_residual_sum_stays_kein_regen(self):
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "precip": 0.02, "pop": 5},
            {"hour": 7, "temp": 13, "wind": 3, "gust": 5, "precip": 0.02, "pop": 5},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "kein Regen" in block, (
            f"Tagessumme 0.04mm rundet auf 0.0 — Text sollte 'kein Regen' "
            f"bleiben, nicht 'Regen ges. 0.0 mm' (neuer Widerspruch in "
            f"umgekehrter Richtung):\n{block}"
        )
        assert "Regen ges. 0.0 mm" not in block, (
            f"'Regen ges. 0.0 mm' waere ein neuer Widerspruch (Nullaussage "
            f"trotz Ereignis-Framing):\n{block}"
        )


# ===========================================================================
# AC-4: Regressionsschutz — bestehender Threshold-Fall (Einzelstunde >= 0.2mm)
#       bleibt im Format "Regen ab HH:00 · X mm" unveraendert
# ===========================================================================

class TestAC4BestehenderThresholdFallUnveraendert:

    def test_existing_threshold_case_unaffected(self):
        segs = [_seg_with_hours([
            {"hour": 6, "temp": 12, "wind": 3, "gust": 5, "precip": 0.1, "pop": 20},
            {"hour": 7, "temp": 13, "wind": 3, "gust": 5, "precip": 0.5, "pop": 60},
            {"hour": 8, "temp": 14, "wind": 3, "gust": 5, "precip": 0.0, "pop": 0},
        ])]
        html = _render_html(segs)
        block = _metrics_block_html(html)
        assert "Regen ab 09:00 · 0.6 mm" in block, (
            f"Bestehender Threshold-Fall (Einzelstunde >= 0.2mm) sollte "
            f"unveraendert 'Regen ab HH:00 · X mm' zeigen:\n{block}"
        )
