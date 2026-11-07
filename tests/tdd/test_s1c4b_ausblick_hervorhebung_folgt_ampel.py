"""Issue #2792 S1c-4b — Ausblick-Spitzenwerte (``@h``) folgen der Abo-Ampel.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5, §5 „SMS,
Premium-SMS, Telegram @14" (``sms_threshold``/``DEFAULTS`` wirken nicht mehr,
Hervorhebung = erste Stunde gelb oder schlechter, beidseitig), AC-7, AC-19 (e),
AC-27 (ein Prädikat).

``format_trend_tokens`` (Ausblick-Zeilen in Telegram, Klartext-/Kompaktmail)
hob Regen/Wind/Böen bisher nach festen Werten (0,5 mm / 30 / 50 km/h) bzw.
der gespeicherten ``sms_threshold`` hervor. Geprüft wird an der Telegram-
Ausblick-Zeile (``narrow._outlook_lines``) und an den Token selbst.
Kern-Schicht: echte Renderer, keine Mocks.
"""
from __future__ import annotations

import pytest

from app.ampel import resolve_ampel


def _ampel(vorlage: str) -> dict:
    return resolve_ampel({"display_config": {"preset_name": vorlage}})


def _zeile(*, regen: float = 0.0, wind: float = 12.0, boeen: float = 15.0) -> dict:
    from output.tokens.dto import HourlyValue
    return {
        "weekday": "Mo", "temp_lo": 2, "temp_hi": 9, "precip_mm": regen,
        "wind_kmh": int(wind), "thunder": "NONE",
        "hourly_precip": (HourlyValue(9, 0.0), HourlyValue(10, regen)),
        "hourly_wind": (HourlyValue(9, 12.0), HourlyValue(10, wind)),
        "hourly_gust": (HourlyValue(9, 15.0), HourlyValue(10, boeen)),
        # eine gespeicherte Altschwelle darf nicht mehr wirken (E1)
        "sms_threshold_precip": 0.1, "sms_threshold_wind": 5.0, "sms_threshold_gust": 5.0,
    }


@pytest.mark.parametrize("vorlage,zeile,feld,hervorgehoben", [
    # Regen 1,5 mm: Allgemein gelb ab 1, Skitouren erst ab 2
    ("allgemein", _zeile(regen=1.5), "precip_token", True),
    ("skitouren", _zeile(regen=1.5), "precip_token", False),
    # Wind 3 km/h: Wassersport unten gelb unter 8 (beidseitig), Allgemein grün
    ("wassersport", _zeile(wind=3.0), "wind_token", True),
    ("allgemein", _zeile(wind=3.0), "wind_token", False),
    # Böen 35 km/h: Allgemein gelb ab 30, Skitouren erst ab 40
    ("allgemein", _zeile(boeen=35.0), "gust_token", True),
    ("skitouren", _zeile(boeen=35.0), "gust_token", False),
])
def test_ausblick_token_heben_nach_gelb_oder_schlechter_hervor(vorlage, zeile, feld, hervorgehoben):
    from output.renderers.email.helpers import format_trend_tokens
    tok = format_trend_tokens(zeile, ampel=_ampel(vorlage))
    assert (tok[feld] != "-") is hervorgehoben, (vorlage, feld, tok[feld])
    if hervorgehoben:
        assert tok[feld].endswith("@10"), tok[feld]


@pytest.mark.parametrize("reihenfolge", [("allgemein", "skitouren"), ("skitouren", "allgemein")])
def test_telegram_ausblick_zeile_folgt_der_abo_ampel(reihenfolge):
    """Die Telegram-Ausblick-Zeile zeigt Regen 1,5 mm nur bei Allgemein als
    Spitzenwert mit Stunde (``R1.5@10``), bei Skitouren die Tagessumme."""
    from output.renderers.narrow import _outlook_lines
    zeilen = {v: "\n".join(_outlook_lines([_zeile(regen=1.5)], ampel=_ampel(v)))
              for v in reihenfolge}
    assert "R1.5@10" in zeilen["allgemein"]
    assert "R1.5@10" not in zeilen["skitouren"]
