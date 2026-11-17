"""#3096 (Phase 3a von #3047, Epic #3058): E-Mail liest direkt aus dem Resolver.

SPEC: docs/specs/modules/feat_3096_mail_resolver.md (AC-2 bis AC-6)

Trip: die Spaltenfolge der Mail-Stundentabelle kommt aus
``resolve_channel_lists(dc, "trip", report_type).email`` (Adapter
``email_col_order``), nicht mehr aus ``resolve_metric_col_order(dc)``.
Orte: der Stundenverlauf bekommt nie ``None``; die Vorgabe wird genau einmal in
``compare_hourly_metric_ids`` aufgeloest.

Zusicherungen am Mail-Ergebnis (HTML-Kopfzeile, Klartext), Soll von Hand.
Kein ``Mock()``/``patch()``.

ROT vor der Umstellung:
* ``test_adapter_*`` -- ``email_col_order`` existiert nicht.
* ``test_trip_mail_folgt_resolver_email_liste[update]`` -- ohne Kollabierung
  zeigt die Mail heute die Grundauswahl statt der E-Mail-Liste.
* ``test_orte_*_nie_none`` -- Resolver/Render-Optionen liefern heute ``None``.
* ``test_ac4_*`` -- Altpfade existieren noch.
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers.trip_report import TripReportFormatter
from tests.tdd import _min_temp_felt_fixtures as F

#: Vorgabe "nie eingestellt" von Hand (Golden ``orte_altbestand_ohne_grundauswahl``).
NEUN_VORGABE = (
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "uv_index", "thunder", "rain_probability", "visibility",
)
NEUN_VORGABE_DP = (
    "t2m_c", "wind_chill_c", "wind10m_kmh", "gust_kmh", "precip_1h_mm",
    "uv_index", "thunder_level", "pop_pct", "visibility_m",
)


# ---------------------------------------------------------------------------
# Trip
# ---------------------------------------------------------------------------

def _mc(mid: str, order: int, enabled: bool = True) -> MetricConfig:
    return MetricConfig(metric_id=mid, enabled=enabled, order=order)


def _trip_dc(global_ids, email_ids=None, trip_id="t3096") -> UnifiedWeatherDisplayConfig:
    dc = UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=[_mc(m, i) for i, m in enumerate(global_ids)],
    )
    if email_ids is not None:
        dc.per_channel_layouts = {"email": [_mc(m, i) for i, m in enumerate(email_ids)]}
    return dc


#: CAPE-Wert im Segment: ohne Ausblendung stuende er als Zelle in der Tabelle.
CAPE_JKG = 1234.0


def _segment_mit_cape():
    """Fixture-Segment, dessen Zeitreihe echte CAPE-Werte traegt (F001): die
    nicht auswaehlbare Metrik haette damit Daten fuer eine eigene Spalte."""
    seg = F.segment()
    data = [dataclasses.replace(dp, cape_jkg=CAPE_JKG) for dp in seg.timeseries.data]
    return dataclasses.replace(seg, timeseries=dataclasses.replace(seg.timeseries, data=data))


def _mail(dc, report_type: str, segment=None):
    return TripReportFormatter().format_email(
        [segment or F.segment()], trip_name="Issue3096", report_type=report_type,
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )


def _koepfe_html(html: str) -> list[str]:
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", html, re.S)
    assert head, "Stundentabelle ohne Kopfzeile"
    return [re.sub(r"<[^>]+>", "", th).strip()
            for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)]


def _koepfe_klartext(plain: str) -> list[str]:
    """Kopfzeile der ersten Segment-Stundentabelle im Klartext (Zeile vor der
    ``-----``-Trennlinie)."""
    zeilen = plain.splitlines()
    for i, z in enumerate(zeilen[1:], start=1):
        if z.strip().startswith("-----"):
            return zeilen[i - 1].split()
    raise AssertionError("Klartext ohne Stundentabelle")


def _html_koepfe(dc, report_type: str) -> list[str]:
    return _koepfe_html(_mail(dc, report_type).email_html)


# Grundauswahl: Temp, Wind, Gust, Rain, UV, CAPE (CAPE nicht auswaehlbar).
GLOBAL = ["temperature", "wind", "gust", "precipitation", "uv_index", "cape"]
# E-Mail-Liste: andere Folge, Teilmenge, CAPE mittendrin.
EMAIL = ["precipitation", "cape", "gust", "temperature"]


# report_type: Morgen/Abend (Briefing) sowie ``update`` und ``alert`` (Werte,
# die ``format_email`` ausserhalb von Morgen/Abend kennt: Betreff
# ``output/subject.py``, Kopf ``briefing_typ``/``mail.kopf.art_alert``).
# PO-Entscheidung 2026-11-17 (#3096): alle folgen der E-Mail-Auswahl.
@pytest.mark.parametrize("fmt", ["html", "klartext"])
@pytest.mark.parametrize("report_type", ["morning", "evening", "update", "alert"])
def test_trip_mail_folgt_resolver_email_liste(report_type, fmt):
    """AC-2: Spaltenfolge = E-Mail-Liste (Rain, Gust, Temp), Wind/UV abgewaehlt
    (nicht in der E-Mail-Liste), CAPE nie als Spalte, obwohl das Segment
    echte CAPE-Werte traegt -- fuer jeden report_type, HTML und Klartext."""
    mail = _mail(_trip_dc(GLOBAL, EMAIL), report_type, segment=_segment_mit_cape())
    koepfe = _koepfe_html(mail.email_html) if fmt == "html" else _koepfe_klartext(mail.email_plain)
    # Feste Rahmenspalten (Zeit; HTML zusaetzlich Risiko) sind keine Metriken.
    metriken = [k for k in koepfe if k not in ("Zeit", "Risiko")]
    assert metriken == ["Rain", "Gust", "Temp"], (
        f"{report_type}/{fmt}: Spalten folgen nicht der E-Mail-Auswahl: {koepfe}")


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_trip_mail_nicht_auswaehlbare_metrik_mit_daten_keine_spalte(fmt):
    """AC-2 (F001): CAPE in E-Mail-Liste UND Grundauswahl, Segment mit echten
    CAPE-Werten -- weder Spalte noch Wert erscheinen in der Stundentabelle."""
    mail = _mail(_trip_dc(GLOBAL, EMAIL), "evening", segment=_segment_mit_cape())
    text = mail.email_html if fmt == "html" else mail.email_plain
    koepfe = _koepfe_html(text) if fmt == "html" else _koepfe_klartext(text)
    assert "CAPE" not in koepfe and "cape" not in koepfe, koepfe
    assert str(int(CAPE_JKG)) not in text, f"{fmt}: CAPE-Wert in der Mail"


def test_trip_mail_ohne_email_liste_folgt_grundauswahl():
    """AC-2 Gegenprobe: ohne E-Mail-Liste gilt die Grundauswahl in ihrer Folge."""
    koepfe = _html_koepfe(_trip_dc(["gust", "wind", "precipitation", "temperature"]), "evening")
    rest = [k for k in koepfe if k in ("Gust", "Wind", "Rain")]
    assert rest == ["Gust", "Wind", "Rain"], koepfe


def test_adapter_email_col_order_folge_enabled_selectable():
    """AC-2/AC-4: Adapter bildet Resolver-Zeilen auf col_key ab, erhaelt die
    Folge, filtert ``enabled`` und ``selectable``, ueberspringt Unbekanntes."""
    from output.renderers.email.helpers import email_col_order
    from services.channel_list_resolver import ChannelRow

    rows = (
        ChannelRow("precipitation", True, None, 0),
        ChannelRow("cape", True, None, 1),
        ChannelRow("wind", False, None, 2),
        ChannelRow("gibt_es_nicht", True, None, 3),
        ChannelRow("gust", True, None, 4),
    )
    assert email_col_order(rows) == ["precip", "gust"]


def test_adapter_render_html_und_plain_folgen_uebergebenen_zeilen():
    """AC-2: ``render_email`` nimmt die E-Mail-Zeilen entgegen; weichen sie von
    ``dc.metrics`` ab, gewinnen die Zeilen (HTML und Klartext)."""
    import inspect

    from output.renderers.email import render_email
    from output.renderers.email.html import render_html
    from output.renderers.email.plain import render_plain

    for fn in (render_email, render_html, render_plain):
        assert "email_rows" in inspect.signature(fn).parameters, (
            f"{fn.__module__}.{fn.__name__} kennt keinen Parameter email_rows")


@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac6_zwei_nutzer_je_eigene_spaltenfolge(reihenfolge):
    """AC-6: zwei Nutzer, unterschiedliche E-Mail-Listen, beide Aufrufreihenfolgen."""
    a = _trip_dc(GLOBAL, ["gust", "precipitation"], trip_id="nutzer-a")
    b = _trip_dc(GLOBAL, ["precipitation", "wind", "gust"], trip_id="nutzer-b")
    folge = [("a", a), ("b", b)] if reihenfolge == "ab" else [("b", b), ("a", a)]
    ist = {name: [k for k in _html_koepfe(dc, "evening") if k in ("Gust", "Rain", "Wind")]
           for name, dc in folge}
    assert ist == {"a": ["Gust", "Rain"], "b": ["Rain", "Wind", "Gust"]}, ist


# ---------------------------------------------------------------------------
# Orte
# ---------------------------------------------------------------------------

GRUNDAUSWAHL_OHNE_STUNDE = [{"metric_id": "wind_direction", "aggregation": "avg"}]


@pytest.mark.parametrize("dc", [{}, {"active_metrics": GRUNDAUSWAHL_OHNE_STUNDE}],
                         ids=["ohne_grundauswahl", "grundauswahl_ohne_stundengroesse"])
def test_orte_resolver_hourly_nie_none(dc):
    """AC-3: Resolver liefert fuer Orte die konkrete Vorgabeliste statt None."""
    from services.channel_list_resolver import resolve_channel_lists

    hourly = resolve_channel_lists(dc, "compare").hourly
    assert hourly is not None, "Orte-hourly ist None (Vorgabe im Renderer statt im Resolver)"
    assert tuple(z.metric_id for z in hourly) == NEUN_VORGABE


@pytest.mark.parametrize("dc", [{}, {"active_metrics": GRUNDAUSWAHL_OHNE_STUNDE}],
                         ids=["ohne_grundauswahl", "grundauswahl_ohne_stundengroesse"])
def test_orte_render_options_hourly_nie_none(dc):
    """AC-3/AC-5: Versand- und Vorschaukette bekommen die konkrete Liste."""
    from services.report_config_resolver import resolve_compare_render_options

    opt = resolve_compare_render_options({"id": "p3096", "display_config": dc})
    assert opt.hourly_metrics is not None, "Renderer bekaeme None"
    assert tuple(opt.hourly_metrics) == NEUN_VORGABE_DP


@pytest.mark.parametrize("fmt", ["html", "klartext"])
def test_orte_mail_ohne_einstellung_neun_vorgabespalten(fmt):
    """AC-3 (Regression am Mail-Ergebnis): Altbestand ohne Grundauswahl zeigt
    im Stundenverlauf genau die neun Vorgabespalten in Vorgabefolge."""
    from tests.helpers.einstellung_gleich_mail_orte import (
        html_stundenverlauf, kennungen, klartext_stundenverlauf, preset_dict, sende_orte_mail,
    )

    mail = sende_orte_mail(preset_dict("altbestand_ohne_grundauswahl"))
    je_ort = html_stundenverlauf(mail.html) if fmt == "html" else klartext_stundenverlauf(mail.plain)
    assert je_ort, f"{fmt}: kein Stundenverlauf"
    for ort, koepfe in je_ort.items():
        assert tuple(kennungen(koepfe)) == NEUN_VORGABE, f"{fmt} {ort}: {koepfe}"


def test_orte_render_mit_konkreter_liste_gleich_vorgabe():
    """AC-3: der Renderer bekommt die konkrete Liste und zeigt dieselben Spalten."""
    from output.renderers.email.compare_html import _hour_zeilen, _visible_hour_metrics

    ist = [z["metric_id"] for z in _visible_hour_metrics(list(NEUN_VORGABE_DP), _hour_zeilen())]
    assert tuple(ist) == NEUN_VORGABE


# ---------------------------------------------------------------------------
# AC-4: Altpfade entfernt  # doc-compliance-test
# ---------------------------------------------------------------------------

def test_ac4_resolve_metric_col_order_entfernt():  # doc-compliance-test
    import output.renderers.email.helpers as helpers

    assert not hasattr(helpers, "resolve_metric_col_order"), (
        "Altpfad resolve_metric_col_order existiert noch")


def test_ac4_visible_hour_metrics_ohne_none_sonderpfad():  # doc-compliance-test
    from output.renderers.email.compare_html import _hour_zeilen, _visible_hour_metrics

    with pytest.raises(TypeError):
        _visible_hour_metrics(None, _hour_zeilen())


def test_ac4_renderer_ohne_eigene_vorgabeliste():  # doc-compliance-test
    import output.renderers.email.compare_html as compare_html

    assert not hasattr(compare_html, "HOURLY_DEFAULT_METRIC_IDS"), (
        "compare_html fuehrt die Vorgabeliste noch als zweite Quelle")


# ---------------------------------------------------------------------------
# AC-8: ADR-0121 Nachtrag 3a
# ---------------------------------------------------------------------------


def test_ac8_adr_0121_nachtrag_3a_vorhanden():  # doc-compliance-test
    from pathlib import Path

    adr = Path(__file__).resolve().parents[2] / "docs" / "adr" / "0121-kanonische-kanal-liste.md"
    text = adr.read_text(encoding="utf-8")
    start = text.find("## Nachtrag 3a")
    assert start != -1, "ADR-0121 hat keinen Abschnitt '## Nachtrag 3a'"
    rest = text[start + 5:]
    nxt = rest.find("\n## ")
    abschnitt = text[start:] if nxt == -1 else text[start:start + 5 + nxt]
    assert "#3096" in abschnitt
    assert "nie `None`" in abschnitt
    assert "Trip-`hourly`" in abschnitt
