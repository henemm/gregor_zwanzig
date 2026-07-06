"""#641 RED: Toter SMS-Trend-Pfad muss entfernt werden.

Kein Datei-Text-Scan (kein read_text) — stattdessen Laufzeit-Introspektion des
echten Modul-/Callable-Vertrags. Vor dem Rückbau ROT (Param/Helfer existieren),
danach GRÜN.
"""
import inspect

import src.output.renderers.sms_trip as sms_mod
from src.output.renderers.sms_trip import SMSTripFormatter


def test_format_sms_has_no_multi_day_trend_param():
    """#641 AC-1: format_sms hat keinen multi_day_trend-Param mehr (toter SMS-Trend raus)."""
    params = inspect.signature(SMSTripFormatter.format_sms).parameters
    assert "multi_day_trend" not in params, (
        "Toter SMS-Trend-Pfad noch da: format_sms akzeptiert weiterhin multi_day_trend"
    )


def test_sms_peak_only_helper_removed():
    """#641 AC-1: _sms_peak_only (nur vom toten Trend-Block genutzt) ist entfernt."""
    assert not hasattr(sms_mod, "_sms_peak_only"), (
        "Toter Helfer _sms_peak_only noch vorhanden"
    )
