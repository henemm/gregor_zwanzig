"""Issue #2792 S1c-4b -- PO-Entscheid 2026-11-07 (Spec v1.6): Die Temperatur
faerbt in der Trip-Stundentabelle nach der Abo-Ampel GENAU WIE die anderen
Metriken.

Pruefgegenstand: eine eigene Gelbgrenze im Abo (Ampel-Abweichung wie AC-2)
wirkt fuer die Temperatur an denselben Stellen und auf dieselbe Art wie fuer
eine andere Metrik (Boeen): Stundentabelle, Kachel, 3-Tages-Ausblick, SMS und
Telegram-Kurzuebersicht. Zwei Abos (A mit Abweichung, B ohne, beide Vorlage
„allgemein"), beide Reihenfolgen im selben Prozess.

Werte: +22 °C bzw. Boeen 25 km/h um 11 Uhr, sonst 12 °C / 15 km/h. Bei
„allgemein" (Gelb ab 28 °C bzw. 30 km/h) gruen; mit A's Gelbgrenze 20 gelb.

Gemessen an der gerenderten Sendung (``format_email``) und am Ausblick-
Renderer mit der aus DERSELBEN Abo-Konfiguration aufgeloesten Ampel.
Kern-Schicht: echte Domaenenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from tests.tdd.test_s1c4b_fixloop1_findings import TZ, _hv, _segmente
from tests.tdd.test_s1c4b_fixloop2_findings import _kachel, _telegram_zeile

#: A's Abweichung: Gelb ab 20 statt 28 °C / 30 km/h, Orange und Rot wie die Vorlage.
_ABWEICHUNG = {"metrics": {
    "temperature": {"upper": {"yellow": 20, "orange": 31, "red": 34}},
    "gust": {"upper": {"yellow": 20, "orange": 45, "red": 60}},
}}

#: Metrik -> (Messfeld, Spitzenwert um 11 Uhr, Tabellen-Label, Kachel-Anfang,
#: SMS-Kuerzel gelb / gruen, Telegram-Kuerzel, Ausblick-Feld, Ausblick-Spalte)
_METRIKEN = {
    "temperature": ("t2m_c", 22.0, "Temp", "12–22", ("D22@11", "D22"), "T", "temp_hi", 2),
    "gust": ("gust_kmh", 25.0, "Gust", "Böen", ("G25@11", "G-"), "G", "gust_kmh", 6),
}

REIHENFOLGEN = [("A", "B"), ("B", "A")]


def _dc(abo: str):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id=f"abw-{abo}", preset_name="allgemein",
        ampel=_ABWEICHUNG if abo == "A" else None,
        metrics=[MetricConfig(metric_id=m, enabled=True)
                 for m in ("temperature", "temperature_day_high", "wind", "gust")])


def _sendung(abo: str):
    from app.models import TripReportConfig
    from output.renderers.trip_report import TripReportFormatter
    return TripReportFormatter().format_email(
        _segmente(je_stunde=lambda h: {"t2m_c": 22.0, "gust_kmh": 25.0} if h == 11 else {}),
        trip_name="ABW", report_type="morning", display_config=_dc(abo), stage_name="E1", tz=TZ,
        report_config=TripReportConfig(trip_id=f"abw-{abo}", email_format="full"))


def _gelb_bg() -> str:
    from output.renderers.email.design_tokens import tone_css
    return f"background:{tone_css('yellow')[0]};"


def _tabellen_zelle(html: str, stunde: str, label: str) -> str:
    tab = BeautifulSoup(html, "html.parser").find("table", attrs={"data-table": "resp"})
    assert tab is not None, "Vorbedingung: Stundentabelle fehlt"
    for tr in tab.find_all("tr"):
        tds = tr.find_all("td")
        if tds and tds[0].get_text(strip=True) == stunde:
            zelle = next((td for td in tds if td.get("data-label") == label), None)
            assert zelle is not None, f"Vorbedingung: Zelle {label} fehlt in Stunde {stunde}"
            return zelle.get("style") or ""
    raise AssertionError(f"Vorbedingung: Stundenzeile {stunde} fehlt")


def _ausblick_zelle(abo: str, spalte: int) -> str:
    from app.ampel import resolve_ampel
    from output.renderers.email.outlook import render_outlook_table
    zeile = dict(weekday="Mo", name="E", temp_lo=12, temp_hi=22, precip_mm=0.0,
                 # die Boeen-Zelle liest das Maximum aus hourly_gust (nicht gust_kmh)
                 wind_dir="W", wind_kmh=12, gust_kmh=25, thunder="NONE", note=None,
                 hourly_precip=(), hourly_wind=(), hourly_gust=_hv((11, 25.0)), hourly_thunder=(),
                 rain_probability_pct=10)
    html = render_outlook_table([zeile], show_acc=True,
                                ampel=resolve_ampel({"display_config": _dc(abo)}))
    tds = BeautifulSoup(html, "html.parser").find("tbody").find("tr").find_all("td")
    return tds[spalte].get("style") or ""


@pytest.mark.parametrize("metrik", list(_METRIKEN))
@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN)
def test_eigene_gelbgrenze_wirkt_an_allen_stellen_gleich(reihenfolge, metrik):
    """Mit A's Gelbgrenze 20 ist der Spitzenwert gelb -- in Stundentabelle,
    Kachel, Ausblick, SMS (Wert mit Stunde) und Telegram (``@11``); bei B
    (Vorlage ohne Abweichung) ueberall gruen bzw. ohne Hervorhebung. Die
    Temperatur verhaelt sich dabei genau wie die Boeen."""
    _feld, _wert, label, kachel, sms, tg, _af, spalte = _METRIKEN[metrik]
    gelb = _gelb_bg()
    for abo in reihenfolge:
        rep = _sendung(abo)
        ist_gelb = abo == "A"
        zelle = _tabellen_zelle(rep.email_html, "11", label)
        neutral = _tabellen_zelle(rep.email_html, "10", label)
        assert "background:" not in neutral, (abo, metrik, neutral)
        if ist_gelb:
            assert gelb in zelle, (abo, metrik, "Stundentabelle", zelle)
        else:
            assert zelle == neutral, (abo, metrik, "Stundentabelle", zelle)
        _text, ton = _kachel(rep.email_html, kachel)
        assert ton == ("ampel_yellow" if ist_gelb else "ampel_green"), (abo, metrik, "Kachel", _text, ton)
        aus = _ausblick_zelle(abo, spalte)
        if ist_gelb:
            assert aus.startswith(gelb), (abo, metrik, "Ausblick", aus[:60])
        else:
            assert not aus.startswith("background:"), (abo, metrik, "Ausblick", aus[:60])
        token = sms[0] if ist_gelb else sms[1]
        assert token in rep.sms_text.split(), (abo, metrik, "SMS", rep.sms_text)
        tg_zeile = _telegram_zeile(rep, tg)
        assert tg_zeile.endswith("@11") == ist_gelb, (abo, metrik, "Telegram", tg_zeile)
