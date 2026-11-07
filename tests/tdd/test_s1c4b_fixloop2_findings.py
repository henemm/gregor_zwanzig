"""Issue #2792 S1c-4b, Fix-Loop 2 (Adversary F001-F004, Koordinator-Entscheide).

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5 (AC-3, AC-5, AC-7,
AC-27; §5 Punkt 9). Protokoll:
docs/artifacts/feat-2792-s1c4b-umschalten/adversary-dialog.md.

Gemessen wird dort, wo die Zusicherung WIRKT: gerenderte Ausblick-Zelle
(Trip-Renderer und Vergleichs-Mail), Mail-Kachel, SMS-Text und Telegram-
Kurzuebersicht aus DERSELBEN ``format_email``-Sendung. Kern-Schicht: echte
Domaenenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

import dataclasses
import re

import pytest
from bs4 import BeautifulSoup

from tests.tdd.test_s1c4b_fixloop1_findings import TZ, _ampel, _hv, _segmente, _sms_token

REIHENFOLGEN = [("wassersport", "allgemein"), ("allgemein", "wassersport")]


def _bg(stufe: str | None) -> str:
    """Erwarteter Zell-Hintergrund (``""`` = keine Toenung)."""
    from output.renderers.email.design_tokens import tone_css
    return "" if stufe in (None, "green") else f"background:{tone_css(stufe)[0]};"


def _zellen(tr) -> dict[str, str]:
    """Spaltenkopf -> style der Zelle (erste Datenzeile)."""
    return {kopf: td.get("style", "") for kopf, td in zip(_KOEPFE, tr.find_all("td"))}


_KOEPFE = ("Tag", "Temp Minimum", "Temp Maximum", "Rain", "Rain%", "Wind", "Gust", "Thdr", "ACC")


def _beginnt_mit(style: str, bg: str) -> bool:
    return style.startswith(bg) if bg else not style.startswith("background:")


# ---------------------------------------------------------------------------
# F001 + F004(1): 3-Tages-Ausblick, fester Zweig -- untere Seite und Gewitter
# ---------------------------------------------------------------------------

def _trip_ausblick(vorlage: str) -> dict[str, str]:
    from output.renderers.email.outlook import render_outlook_table
    zeile = dict(weekday="Mo", name="E", temp_lo=10, temp_hi=18, precip_mm=0.0,
                 wind_dir="W", wind_kmh=3, gust_kmh=5, thunder="MED", note=None,
                 hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
                 rain_probability_pct=10)
    html = render_outlook_table([zeile], show_acc=True, ampel=_ampel(vorlage))
    return _zellen(BeautifulSoup(html, "html.parser").find("tbody").find("tr"))


def _vergleich_ausblick(vorlage: str) -> dict[str, str]:
    from app.models import ThunderLevel
    from output.renderers.comparison import render_compare_email
    from tests.tdd.test_compare_outlook_metric_selection import _outlook_tables, _result
    res = _result()
    ort = res.locations[0]
    ort.outlook_hourly_data = [dataclasses.replace(p, wind10m_kmh=3.0, thunder_level=ThunderLevel.MED)
                               for p in ort.outlook_hourly_data]
    preset = {"id": "fl2", "name": "FL2", "location_ids": ["innsbruck"],
              "profil": "SUMMER_TREKKING", "display_config": {"ampel": {"template": vorlage}}}
    out = render_compare_email(res, outlook_enabled=True, preset=preset)
    html = out[0] if isinstance(out, tuple) else out
    tab = _outlook_tables(html)
    assert len(tab) == 1, "Vorbedingung: genau ein Vergleichs-Ausblick"
    return _zellen(tab[0].find("tbody").find("tr"))


@pytest.mark.parametrize("ausblick", [_trip_ausblick, _vergleich_ausblick], ids=["trip", "vergleich"])
@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN)
def test_ausblick_fester_zweig_wind_unten_und_gewitter_nach_abo_ampel(ausblick, reihenfolge):
    """AC-3: Wassersport-Mittelwind 3 km/h ist orange (untere Seite), bei
    Allgemein ungetoent. AC-5: Gewitter „mittel" Wassersport rot, Allgemein
    orange -- im festen Ausblick-Zweig von Trip UND Vergleich."""
    erwartet = {"wassersport": ("orange", "red"), "allgemein": (None, "orange")}
    for vorlage in reihenfolge:
        zellen = ausblick(vorlage)
        wind, gewitter = erwartet[vorlage]
        assert _beginnt_mit(zellen["Wind"], _bg(wind)), (vorlage, "Wind", zellen["Wind"][:60])
        assert _beginnt_mit(zellen["Thdr"], _bg(gewitter)), (vorlage, "Thdr", zellen["Thdr"][:60])


# ---------------------------------------------------------------------------
# F003: Klammer = schlimmster Wert der hervorgehobenen Stunden, je Seite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("werte, erwartet", [
    (((9, 7.0), (12, 3.0)), "7@9(3@12)"),      # unten: Minimum ist das Schlimmste
    (((9, 3.0), (12, 7.0)), "3@9"),            # erster Wert ist schon der schlimmste
    (((9, 6.0), (12, 5.0), (15, 15.0)), "6@9(5@12)"),  # gleiche Stufe gelb: weiter von Gruen
    # beidseitig, beide orange (3 < 4, 45 >= 40): weiter von Gruen gewinnt (45-30 > 8-3)
    (((9, 7.0), (12, 3.0), (14, 45.0)), "7@9(45@14)"),
])
def test_klammer_nennt_den_schlimmsten_wert_auch_unten(werte, erwartet):
    """F003 (Koordinator-Entscheid): schlimmster Wert unter den hervorgehobenen
    Stunden -- hoechste Ampelstufe, bei Gleichstand der weiter vom gruenen
    Bereich entfernte, dann die frueheste Stunde. Wassersport-Wind: unten gelb
    < 8, orange < 4; oben gelb ab 30, orange ab 40. SMS und Ausblick gleich."""
    from output.renderers.email.helpers import format_trend_tokens
    wasser = _ampel("wassersport")
    serie = _hv(*werte)
    assert _sms_token("W", "wind_hourly", serie, wasser) == erwartet
    assert format_trend_tokens({"hourly_wind": serie}, ampel=wasser)["wind_token"] == erwartet


# ---------------------------------------------------------------------------
# F002 + F004(2-4): Mail-Kacheln aus derselben Sendung wie SMS und Telegram
# ---------------------------------------------------------------------------

def _sendung(vorlage: str, je_stunde):
    from app.models import MetricConfig, ThunderLevel, TripReportConfig, UnifiedWeatherDisplayConfig
    from output.renderers.trip_report import TripReportFormatter
    dc = UnifiedWeatherDisplayConfig(trip_id="fl2", preset_name=vorlage, metrics=[
        MetricConfig(metric_id=m, enabled=True)
        for m in ("temperature", "wind", "thunder", "visibility")])
    return TripReportFormatter().format_email(
        _segmente(je_stunde=je_stunde, gewitter_11=ThunderLevel.MED), trip_name="FL2",
        report_type="morning", display_config=dc, stage_name="E1", tz=TZ,
        report_config=TripReportConfig(trip_id="fl2", email_format="full"))


def _kachel(html: str, anfang: str) -> tuple[str, str]:
    """(Text, Ton) der Kachel, deren Text mit ``anfang`` beginnt."""
    from output.renderers.email.helpers import _PILL_TAG_PALETTE, _PILL_TONE_MAP
    rand_zu_ton = {_PILL_TAG_PALETTE[tag]["border"]: ton for ton, tag in _PILL_TONE_MAP.items()}
    for span in BeautifulSoup(html, "html.parser").find_all(
            "span", style=lambda s: s and "padding:4px 10px" in s):
        text = span.get_text(" ", strip=True)
        if text.startswith(anfang):
            rand = re.search(r"border:1px solid (#[0-9a-f]{6})", span["style"]).group(1)
            return text, rand_zu_ton[rand]
    raise AssertionError(f"Vorbedingung: keine Kachel '{anfang}…'")


def _telegram_zeile(rep, kuerzel: str) -> str:
    bubble = next(b for b in rep.telegram_bubbles if "Kurzübersicht" in b)
    return next(z.split(" ", 1)[1] for z in bubble.splitlines() if z.startswith(kuerzel + " "))


_WIND_UNTEN = {9: 6.0, 12: 3.0}  # Rest 12 km/h; Wassersport: 6 gelb (< 8), 3 orange (< 4)


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN)
def test_wind_kachel_sms_und_telegram_tragen_dieselbe_untere_spitze(reihenfolge):
    """F002: loest die untere Grenze aus, nennt die Kachel die untere Grenze
    (``<8 km/h``), den Beginn der SMS (``ab 09:00`` = ``W6@9``), das Extrem
    dieser Seite (``min 3 (12:00)`` = SMS-Klammer ``(3@12)`` = Telegram
    ``3@12``) und den Ton des ausloesenden Werts (orange). Allgemein: keine
    Erwaehnung in keinem der drei Texte."""
    for vorlage in reihenfolge:
        rep = _sendung(vorlage, lambda h: {"wind10m_kmh": _WIND_UNTEN.get(h, 12.0)})
        text, ton = _kachel(rep.email_html, "Wind")
        sms_w = next(t for t in rep.sms_text.split() if t.startswith("W"))
        tg_unten = _telegram_zeile(rep, "W").split("-", 1)[0]
        if vorlage == "wassersport":
            assert text == "Wind <8 km/h ab 09:00 · min 3 (12:00)", text
            assert ton == "ampel_orange", ton
            assert sms_w == "W6@9(3@12)", rep.sms_text
            beginn = re.search(r"ab (\d\d):00", text).group(1)
            spitze, um = re.search(r"min (\d+) \((\d\d):00\)", text).groups()
            assert sms_w == f"W6@{int(beginn)}({spitze}@{int(um)})"
            assert tg_unten == f"{spitze}@{um}", tg_unten
        else:
            assert text.startswith("Wind max 12 km/h"), text
            assert sms_w == "W-", rep.sms_text
            assert "@" not in tg_unten, tg_unten


@pytest.mark.parametrize("reihenfolge", REIHENFOLGEN)
def test_gewitter_kachel_ton_und_beginn_nach_abo_ampel(reihenfolge):
    """F004 (2)+(4): Gewitter „mittel" ab 11 Uhr -- Kachel nennt den Beginn
    ``ab 11:00``; Ton Wassersport rot, Allgemein orange (AC-5)."""
    for vorlage in reihenfolge:
        text, ton = _kachel(_sendung(vorlage, lambda h: {}).email_html, "Gewitter")
        assert text.startswith("Gewitter mittel ab 11:00"), (vorlage, text)
        assert ton == {"wassersport": "ampel_red", "allgemein": "ampel_orange"}[vorlage], (vorlage, ton)


@pytest.mark.parametrize("reihenfolge", [("skitouren", "allgemein"), ("allgemein", "skitouren")])
def test_sicht_kachel_nennt_die_schwelle_der_vorlage(reihenfolge):
    """F004 (3): Sicht 800 m um 10 Uhr -- Skitouren gelb unter 1 km
    („Sicht <1 km"), Allgemein gelb unter 2 km („Sicht <2 km")."""
    for vorlage in reihenfolge:
        text, _ton = _kachel(
            _sendung(vorlage, lambda h: {"visibility_m": 800} if h == 10 else {}).email_html, "Sicht")
        schwelle = {"skitouren": "1", "allgemein": "2"}[vorlage]
        assert text.startswith(f"Sicht <{schwelle} km ab 10:00"), (vorlage, text)


# ---------------------------------------------------------------------------
# Nachtrag (Koordinator-Entscheid): Gewitter-Leser scheitern bei leerer Ampel laut
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("leer", [{}, None, {"metrics": {}}, {"template": "wassersport"}],
                         ids=["leer", "none", "metrics_leer", "unaufgeloest"])
def test_gewitter_leser_scheitern_bei_leerer_ampel_laut(leer):
    """AC-27 / §5 Punkt 4: eine leere, fehlende oder unaufgeloeste Ampel ist ein
    Programmierfehler -- auch fuer die Gewitterfarbe, an allen drei Lesern
    (zentrale Abbildung, Mail-Zelle/-Kachel, Telegram-Emoji) und fuer jede
    Stufe. Kein stiller Rueckfall auf die Gewitterfarben von „allgemein"."""
    from app.ampel import thunder_color
    from app.models import ThunderLevel
    from output.renderers.email.helpers import _thunder_band
    from services.trip_command_processor import _thunder_symbols
    for stufe in (ThunderLevel.NONE, ThunderLevel.LOW, ThunderLevel.MED, ThunderLevel.HIGH):
        with pytest.raises(ValueError, match="Profil-Ampel leer"):
            thunder_color(stufe, leer)
        with pytest.raises(ValueError, match="Profil-Ampel leer"):
            _thunder_band(stufe.name, ampel=leer)
    with pytest.raises(ValueError, match="Profil-Ampel leer"):
        _thunder_symbols(ampel=leer)


def test_gewitter_leser_unbekannte_stufe_bleibt_ohne_aussage():
    """Gegenprobe: ein unbekanntes Stufenwort bei gueltiger Ampel bleibt
    weiterhin ``None`` (keine Farbe) -- nur die leere Ampel scheitert."""
    from output.renderers.email.helpers import _thunder_band
    assert _thunder_band("gibtsnicht", ampel=_ampel("allgemein")) is None
    assert _thunder_band("MED", ampel=_ampel("wassersport")) == "red"
