"""Der Lagebericht in Trip-Briefing-Mail, Ortsvergleich-Mail und Telegram (AC-14, AC-15, AC-16, AC-19).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-14, AC-15, AC-16, AC-19
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 4

Alle Renderer sind die ECHTEN, geteilten Funktionen (`render_html`, `render_compare_html`,
`render_warn_block`, `render_official_alert_telegram`); die Alerts kommen aus dem echten Parser
auf aufgezeichneten Bulletins (Stufe 5: abgeleitete Datei, siehe README der Fixtures).
SMS-Anteil von AC-19: Zeilen mit `sms` im Namen; alle uebrigen SMS-Faelle in `test_avalanche_report_sms.py`.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from tests.helpers.avalanche_report_support import (
    P_MUENCHEN, P_TIROL_AT_07_28, FakeClock, FixtureTransport, alerts_with_status, day_file,
    make_source, notice, ok, only_source, parse_alert, render_compare_mail,
    render_trip_mail, source_label, wb_count_texts,
)

UTC = timezone.utc
HANDLUNGSWOERTER = ("meiden", "vermeiden", "Vorsicht", "empfohlen", "empfehlen", "sollten", "rate ", "Rückzug",
                    "Abstand halten", "Tour abbrechen")


def _stufe1():
    return parse_alert("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02", source="avalanche_report:AT-02")


def _stufe4():
    return parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25", source="avalanche_report:AT-07")


def _stufe5():
    return parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25",
                       source="avalanche_report:AT-07")


def _triebschnee_stufe4():
    """Stufe 4 oberhalb der Waldgrenze mit GENAU dem Problem Triebschnee (die Spec-Formulierung).
    Handgebaut aus den Werten des aufgezeichneten Bulletins 2026-02-20 (AT-07-25), weil dessen
    echtes Bulletin drei Probleme nennt."""
    from dataclasses import replace

    return replace(_stufe4(), problems=("wind_slab",))


def _telegram(alert) -> str:
    from output.renderers.alert.official_alerts import render_official_alert_telegram

    return render_official_alert_telegram([notice(alert)], prefix="Etappe 5", source_label=source_label(alert))


# ---------------------------------------------------------------- AC-14: Stufe 1 ist sichtbar
def test_ac14_trip_mail_zeigt_stufe_1_als_info():
    html = render_trip_mail([_stufe1()], lat=46.8947, lon=14.1901)

    assert "Lawinenstufe 1 (gering)" in html
    assert "Amtliche Warnung" in html


def test_ac14_ohne_bericht_zeigt_die_trip_mail_nichts_von_alledem():
    """Stufe 1 ist unterscheidbar von "kein Bericht"."""
    html = render_trip_mail([], lat=46.8947, lon=14.1901)

    assert "Lawinenstufe" not in html
    assert "Amtliche Warnung" not in html


def test_ac14_ortsvergleich_mail_zeigt_stufe_1_als_info_und_ohne_bericht_nichts():
    mit = render_compare_mail([_stufe1()])
    ohne = render_compare_mail([])

    assert "Lawinenstufe 1 (gering)" in mit
    assert "Lawinenstufe" not in ohne


def test_ac14_ortsvergleich_chip_fuer_stufe_1_ist_eine_info_und_kein_leerstrich():
    from output.renderers.email.compare_html import _render_warn_cell, _warn_short

    text, schwere = _warn_short(_stufe1())
    chip = _render_warn_cell([_stufe1()])

    assert text == "Lawine 1" and schwere not in ("danger", "warn")
    assert ">Lawine 1<" in chip
    assert ">Lawine 1<" not in _render_warn_cell([])


# ---------------------------------------------------------------- AC-15: Stufe 5
def test_ac15_trip_mail_nennt_stufe_5_im_wortlaut_ohne_leiter():
    html = render_trip_mail([_stufe5()])

    assert "Lawinenstufe 5 (sehr groß)" in html
    assert "0/3" not in html
    for zeile in wb_count_texts(html):
        assert not re.search(r"\d/3", zeile), f"Warnstufen-Leiter fuer die EAWS-Skala: {zeile!r}"


def test_ac15_ortsvergleich_mail_nennt_stufe_5_im_wortlaut_ohne_leiter():
    html = render_compare_mail([_stufe5()])

    assert "Lawinenstufe 5 (sehr groß)" in html
    assert "0/3" not in html
    assert "Warnstufe 0" not in html
    for zeile in wb_count_texts(html):
        assert not re.search(r"\d/3", zeile), f"Leiter im Ortsvergleich-Banner: {zeile!r}"


def test_ac15_ortsvergleich_schwere_von_stufe_5_ist_danger_und_nicht_schwaecher_als_4():
    from output.renderers.email.compare_html import _ALERT_LEVEL_CELL, _render_warn_cell, _warn_short

    text5, schwere5 = _warn_short(_stufe5())
    _text4, schwere4 = _warn_short(_stufe4())
    bg, fg = _ALERT_LEVEL_CELL[4]
    chip = _render_warn_cell([_stufe5()])

    assert text5 == "Lawine 5"
    assert schwere5 == "danger" and schwere4 == "danger"
    assert f"background:{bg};color:{fg}" in chip, "Stufe 5 hat die Farbe der hoechsten Stufe"


def test_ac15_telegram_nennt_stufe_5_im_wortlaut_ohne_leiter():
    text = _telegram(_stufe5())

    assert "Lawinenstufe 5 (sehr groß)" in text
    assert "0/3" not in text and "/3" not in text


def test_ac15_alarm_mail_standalone_nennt_stufe_5_im_wortlaut_ohne_leiter():
    from output.renderers.alert.official_alerts import render_warn_block

    a = _stufe5()
    html = render_warn_block([notice(a)], variant="standalone", source_label=source_label(a),
                             stand_at="20.02. 08:00")

    assert "Lawinenstufe 5 (sehr groß)" in html
    assert "0/3" not in html


def test_ac15_stufe_5_und_stufe_4_sind_im_text_unterscheidbar():
    assert "sehr groß" in render_trip_mail([_stufe5()])
    html4 = render_trip_mail([_stufe4()])
    assert "Lawinenstufe 4 (groß)" in html4 and "sehr groß" not in html4


# ---------------------------------------------------------------- AC-16: Wortlaut, Quelle, URL
def test_ac16_trip_mail_und_telegram_tragen_den_wortlaut_des_warndienstes():
    a = _triebschnee_stufe4()
    erwartet = "Lawinenstufe 4 (groß) oberhalb Waldgrenze · Triebschnee"

    html = render_trip_mail([a])
    telegram = _telegram(a)

    assert erwartet in html
    assert erwartet in telegram


def test_ac16_quellenname_und_bulletin_url_stehen_in_mail_und_telegram():
    """CC BY 4.0: Namensnennung + Link zur Quelle."""
    a = _triebschnee_stufe4()
    name = "Lawinenwarndienst Tirol, avalanche.report"
    url = "https://avalanche.report/bulletin/2026-02-20?region=AT-07-25"

    html = render_trip_mail([a])
    telegram = _telegram(a)

    assert name in html and url in html
    assert name in telegram and url in telegram


def test_ac16_keine_handlungsempfehlung_in_mail_und_telegram():
    a = _triebschnee_stufe4()
    for text in (render_trip_mail([a]), _telegram(a), render_compare_mail([a])):
        for wort in HANDLUNGSWOERTER:
            assert wort not in text, f"Handlungsempfehlung {wort!r} gefunden"


def test_ac16_echtes_bulletin_nennt_alle_probleme_des_warndienstes_unveraendert():
    a = _stufe4()
    erwartet = "Lawinenstufe 4 (groß) oberhalb Waldgrenze · Altschnee, Triebschnee, Neuschnee"

    assert erwartet in render_trip_mail([a])
    assert erwartet in _telegram(a)


def test_ac16_ortsvergleich_nennt_den_wortlaut_ebenfalls():
    assert "Lawinenstufe 4 (groß) oberhalb Waldgrenze" in render_compare_mail([_stufe4()])


@pytest.mark.parametrize("kwargs, erwartet", [
    (dict(native_level=1, level=1), "Lawinenstufe 1 (gering)"),
    (dict(native_level=3, level=3, elevation_value="2200", elevation_direction="above"),
     "Lawinenstufe 3 (erheblich) oberhalb 2200 m"),
    (dict(native_level=3, level=3, elevation_value="2200", elevation_direction="below",
          time_of_day="later", problems=("persistent_weak_layers", "wet_snow")),
     "Lawinenstufe 3 (erheblich) unterhalb 2200 m (nachmittags) · Altschnee, Nassschnee"),
    (dict(native_level=5, level=4, elevation_value="Waldgrenze", elevation_direction="above"),
     "Lawinenstufe 5 (sehr groß) oberhalb Waldgrenze"),
    (dict(native_level=2, level=2, elevation_value="1800", elevation_direction="below", time_of_day="earlier"),
     "Lawinenstufe 2 (mäßig) unterhalb 1800 m (vormittags)"),
])
def test_ac16_zentraler_text_helfer(kwargs, erwartet):
    from output.renderers.alert.official_alerts import avalanche_bulletin_text
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="avalanche_report:AT-07", hazard="avalanche_bulletin", label="x", scale="eaws", **kwargs,
    )

    assert avalanche_bulletin_text(alert) == erwartet


@pytest.mark.parametrize("code, name", [
    ("new_snow", "Neuschnee"), ("wind_slab", "Triebschnee"), ("persistent_weak_layers", "Altschnee"),
    ("wet_snow", "Nassschnee"), ("gliding_snow", "Gleitschnee"), ("cornices", "Wechten"),
    ("no_distinct_avalanche_problem", "kein ausgeprägtes Lawinenproblem"),
    ("favourable_situation", "günstige Situation"),
    ("brandneuer_code", "brandneuer_code"),
])
def test_ac16_problemnamen_deutsch_und_unbekannte_codes_gehen_nie_verloren(code, name):
    from output.renderers.alert.official_alerts import avalanche_bulletin_text
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(source="avalanche_report:AT-07", hazard="avalanche_bulletin", level=2, label="x",
                          scale="eaws", native_level=2, problems=(code,))

    assert avalanche_bulletin_text(alert) == f"Lawinenstufe 2 (mäßig) · {name}"


# ---------------------------------------------------------------- AC-19: zwei Nutzer
def _briefing_fuer(lat, lon, now, source_holder):
    from tests.tdd.test_sms_official_alert_tokens import _DISABLE_NEW_14, _segment, _TZ
    from output.renderers.sms_trip import SMSTripFormatter

    alerts, unavailable = alerts_with_status(lat, lon, now)
    html = render_trip_mail(alerts, lat=lat, lon=lon)
    seg = _segment(alerts)
    seg.official_alerts_unavailable = unavailable
    sms = SMSTripFormatter().format_sms([seg], stage_name="Etappe 5", tz=_TZ, disabled_specs=_DISABLE_NEW_14)
    return alerts, unavailable, html, sms


def test_ac19_nur_der_tirol_nutzer_bekommt_den_lagebericht_in_mail_und_sms(monkeypatch):
    now = datetime(2026, 1, 30, 8, 0, tzinfo=UTC)
    transport = FixtureTransport({"AT-07": ok(day_file("2026-01-30"))})
    source = make_source(transport, FakeClock(now))
    only_source(monkeypatch, source)

    a_alerts, a_unavail, a_html, a_sms = _briefing_fuer(*P_TIROL_AT_07_28, now, source)
    b_alerts, b_unavail, b_html, b_sms = _briefing_fuer(*P_MUENCHEN, now, source)
    a_alerts2, _u, a_html2, a_sms2 = _briefing_fuer(*P_TIROL_AT_07_28, now, source)

    # Nutzer A (Tirol): Lagebericht in Mail UND SMS
    assert len(a_alerts) == 1 and a_unavail is False
    assert "Lawinenstufe 3 (erheblich) oberhalb 2200 m" in a_html
    assert re.search(r"(?<![A-Za-z0-9])AV3(?![0-9A-Za-z:@])", a_sms.split("!", 1)[1]), a_sms
    # Nutzer B (Muenchen): weder Lagebericht noch Hinweis -- in Mail und SMS
    assert b_alerts == [] and b_unavail is False
    assert "Lawinen" not in b_html and "Amtliche Warnung" not in b_html and "nicht abrufbar" not in b_html
    assert "AV" not in b_sms and "!" not in b_sms, b_sms
    # kein Durchsickern ueber die Reihenfolge
    assert a_sms2 == a_sms and len(a_alerts2) == 1
    assert transport.served("AT-07") == 1, "Muenchen darf keinen Abruf ausloesen, Tirol nur einen (Cache)"
